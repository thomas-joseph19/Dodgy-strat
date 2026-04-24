// ============================================================================
//  PythonSignalStrategy.cs  —  NinjaTrader 8  NinjaScript Strategy
//
//  PURPOSE
//  -------
//  Bridges NinjaTrader 8 ↔ the Python LiveEngine running in dodgy/live/.
//
//  DATA FLOW
//  ---------
//  1. This strategy attaches to an NQ Futures 1-Minute chart.
//  2. On every bar close it sends the OHLC bar to Python over a local TCP socket.
//  3. Python runs the ORB + Dodgy signal logic and replies with SIGNAL or CLOSE.
//  4. On SIGNAL: this strategy submits a Limit entry order with a Stop-Loss and
//     Profit-Target bracket via NinjaTrader's Managed Order API.
//  5. On CLOSE: any open position is flattened at market.
//
//  INSTALLATION (do this once)
//  ---------------------------
//  1. In NinjaTrader 8:  Tools → NinjaScript Editor
//  2. File → New → Strategy  (just to open the editor)
//  3. File → Open → navigate to this .cs file  — OR —
//     copy this file to:
//       Documents\NinjaTrader 8\bin\Custom\Strategies\PythonSignalStrategy.cs
//     NinjaTrader compiles every .cs file in that folder automatically.
//  4. Press F5 (or Build → Build NinjaScript Assembly) to compile.
//  5. Fix any red error lines before proceeding.
//
//  RUNNING THE STRATEGY
//  --------------------
//  1. Start the Python server first:
//       cd dodgy
//       python -m live.run_live
//     Wait until you see: "Waiting for NinjaTrader on 127.0.0.1:6789 …"
//
//  2. In NinjaTrader: open a chart for NQ futures (Continuous or front-month),
//     set the bar period to 1 Minute.
//
//  3. On the chart: right-click → Strategies → Add Strategy
//     → select PythonSignalStrategy → configure parameters → Enable
//
//  PARAMETERS (visible in NT strategy dialog)
//  -------------------------------------------
//  PythonHost  : Python server address (default 127.0.0.1)
//  PythonPort  : Python server port    (default 6789)
//  Contracts   : number of contracts per trade (default 1)
//
//  IMPORTANT NOTES FOR MYFUNDEDFUTURES
//  ------------------------------------
//  • Add the strategy in "Real-Time" mode, not simulation/backtest.
//  • Select your MFF account in the strategy dialog.
//  • MFFU rules: max 10 contracts on NQ eval, no HFT.  Keep Contracts = 1.
//  • Do NOT enable "Auto-trade" unless you have reviewed a full day of paper
//    trading first.  Use NT's "Strategy Analyzer" or Sim account to verify.
//  • Roll the front-month contract before expiry (e.g. NQM5 → NQU5 in June).
//    Update RITHMIC_SYMBOL in your .env and re-attach this strategy.
// ============================================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class PythonSignalStrategy : Strategy
    {
        // ── Parameters ───────────────────────────────────────────────────────
        private string  pythonHost  = "127.0.0.1";
        private int     pythonPort  = 6789;
        private int     contracts   = 1;

        // ── TCP state ────────────────────────────────────────────────────────
        private TcpClient        _tcp;
        private StreamWriter     _writer;
        private StreamReader     _reader;
        private Thread           _readerThread;
        private volatile bool    _running;
        private readonly object  _tcpLock = new object();

        // ── Active trade state ───────────────────────────────────────────────
        // _activeSignalName/Stop/Target are read+written only on the NT dispatch
        // thread (inside Dispatcher.InvokeAsync or OnBarUpdate), so no lock needed.
        private string  _activeSignalName = null;   // null = no open trade
        private double  _activeStop       = 0;
        private double  _activeTarget     = 0;

        // ── Trade visualization state ────────────────────────────────────────
        private int     _tradeCount       = 0;
        private int     _entryBar         = 0;
        private double  _entryPrice       = 0;
        private string  _entryAction      = "";

        // ── NinjaScript lifecycle ─────────────────────────────────────────────

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name                          = "PythonSignalStrategy";
                Description                   = "Executes signals from Python LiveEngine over TCP.";
                Calculate                     = Calculate.OnBarClose;
                EntriesPerDirection           = 1;
                EntryHandling                 = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy  = true;
                ExitOnSessionCloseSeconds     = 30;
                IsFillLimitOnTouch            = false;
                MaximumBarsLookBack           = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution           = OrderFillResolution.Standard;
                StartBehavior                 = StartBehavior.WaitUntilFlat;
                TimeInForce                   = TimeInForce.Day;
                TraceOrders                   = false;
                RealtimeErrorHandling         = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling            = StopTargetHandling.PerEntryExecution;
            }
            else if (State == State.Configure)
            {
                // Managed approach: SL and TP are set dynamically per-signal.
                // We call SetStopLoss/SetProfitTarget in OnBarUpdate before each entry.
            }
            else if (State == State.Realtime)
            {
                ConnectToPython();
            }
            else if (State == State.Terminated)
            {
                DisconnectFromPython();
            }
        }

        // ── Parameters as NinjaScript properties ─────────────────────────────

        [NinjaScriptProperty]
        [Display(Name = "Python Host", Order = 1, GroupName = "Parameters")]
        public string PythonHost
        {
            get { return pythonHost; }
            set { pythonHost = value; }
        }

        [NinjaScriptProperty]
        [Display(Name = "Python Port", Order = 2, GroupName = "Parameters")]
        public int PythonPort
        {
            get { return pythonPort; }
            set { pythonPort = value; }
        }

        [NinjaScriptProperty]
        [Display(Name = "Contracts", Order = 3, GroupName = "Parameters")]
        public int Contracts
        {
            get { return contracts; }
            set { contracts = value; }
        }

        // ── Main bar update loop ──────────────────────────────────────────────

        protected override void OnBarUpdate()
        {
            // Only act on real-time bars
            if (State != State.Realtime)
                return;

            // Signals and closes arrive via Dispatcher.InvokeAsync from the reader
            // thread and execute immediately — nothing to dequeue here.

            // ── Re-apply SL/TP every bar while a position is open ────────────
            // This is required by the Managed approach — NT needs to see these
            // called each bar to keep the bracket orders active.
            // All access to _activeSignalName is on the NT dispatch thread — no lock needed.
            if (_activeSignalName != null && Position.MarketPosition != MarketPosition.Flat)
            {
                SetStopLoss(_activeSignalName,   CalculationMode.Price, _activeStop,   false);
                SetProfitTarget(_activeSignalName, CalculationMode.Price, _activeTarget);
            }

            {
                // If the position closed on the exchange side, clear our tracking state
                if (_activeSignalName != null && Position.MarketPosition == MarketPosition.Flat)
                {
                    _activeSignalName = null;
                }
            }

            // ── 3. Send this completed bar to Python ──────────────────────────
            SendBarToPython();
        }

        // ── Order execution (always called on NT dispatch thread) ────────────

        private void ExecuteSignal(PendingSignal sig)
        {
            // Safety: don't enter if already in a position
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                Print("[PythonSignal] Signal ignored — already in a position: " + sig.Id);
                return;
            }

            Print(string.Format("[PythonSignal] {0} {1}  entry={2}  stop={3}  target={4}  qty={5}",
                sig.Action, sig.Id, sig.Entry, sig.Stop, sig.Target, sig.Qty));

            _activeSignalName = sig.Id;
            _activeStop       = sig.Stop;
            _activeTarget     = sig.Target;

            // Set bracket prices BEFORE submitting entry (required by managed approach)
            SetStopLoss(sig.Id,   CalculationMode.Price, sig.Stop,   false);
            SetProfitTarget(sig.Id, CalculationMode.Price, sig.Target);

            if (sig.Action == "LONG")
                EnterLongLimit(0, true, sig.Qty, sig.Entry, sig.Id);
            else
                EnterShortLimit(0, true, sig.Qty, sig.Entry, sig.Id);

            // Store for visualization (drawn on fill via OnExecutionUpdate)
            _entryAction = sig.Action;
        }

        private void FlattenPosition()
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                Print("[PythonSignal] CLOSE — ExitLong at market");
                ExitLong();
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                Print("[PythonSignal] CLOSE — ExitShort at market");
                ExitShort();
            }

            _activeSignalName = null;
        }

        // ── Trade fill / exit visualization ────────────────────────────────────

        protected override void OnExecutionUpdate(Execution execution,
            string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order == null) return;

            string orderName = execution.Order.Name;

            // ── ENTRY FILL ────────────────────────────────────────────────────
            if (orderName == _activeSignalName
                && (execution.Order.OrderAction == OrderAction.Buy
                    || execution.Order.OrderAction == OrderAction.SellShort))
            {
                _tradeCount++;
                _entryBar   = CurrentBar;
                _entryPrice = price;

                bool isLong = execution.Order.OrderAction == OrderAction.Buy;
                string tag   = "trade" + _tradeCount;

                // Entry arrow
                if (isLong)
                    Draw.ArrowUp(this, tag + "_entry", false, 0, price - 2 * TickSize, Brushes.DodgerBlue);
                else
                    Draw.ArrowDown(this, tag + "_entry", false, 0, price + 2 * TickSize, Brushes.OrangeRed);

                // Entry text label
                Draw.Text(this, tag + "_entryTxt",
                    string.Format("{0} @ {1:F2}", isLong ? "LONG" : "SHORT", price),
                    0, isLong ? price + 4 * TickSize : price - 4 * TickSize,
                    isLong ? Brushes.DodgerBlue : Brushes.OrangeRed);

                // Stop-Loss line (red dashed)
                Draw.HorizontalLine(this, tag + "_sl", _activeStop, Brushes.Red, DashStyleHelper.Dash, 1);
                Draw.Text(this, tag + "_slTxt",
                    string.Format("SL {0:F2}", _activeStop),
                    0, _activeStop, Brushes.Red);

                // Take-Profit line (green dashed)
                Draw.HorizontalLine(this, tag + "_tp", _activeTarget, Brushes.LimeGreen, DashStyleHelper.Dash, 1);
                Draw.Text(this, tag + "_tpTxt",
                    string.Format("TP {0:F2}", _activeTarget),
                    0, _activeTarget, Brushes.LimeGreen);

                // Entry horizontal line (blue thin)
                Draw.HorizontalLine(this, tag + "_entryLine", price, Brushes.DodgerBlue, DashStyleHelper.Dot, 1);
            }

            // ── EXIT FILL (SL, TP, or market close) ───────────────────────────
            if (execution.Order.OrderAction == OrderAction.Sell
                || execution.Order.OrderAction == OrderAction.BuyToCover)
            {
                if (_tradeCount > 0 && marketPosition == MarketPosition.Flat)
                {
                    string tag  = "trade" + _tradeCount;
                    bool isWin  = (price > _entryPrice && _entryAction == "LONG")
                              || (price < _entryPrice && _entryAction == "SHORT");

                    // Exit marker
                    Draw.Diamond(this, tag + "_exit", false, 0, price,
                        isWin ? Brushes.LimeGreen : Brushes.Red);

                    // Exit text
                    double pnlPts = _entryAction == "LONG"
                        ? price - _entryPrice
                        : _entryPrice - price;
                    Draw.Text(this, tag + "_exitTxt",
                        string.Format("Exit {0:F2} ({1}{2:F1}pts)",
                            price, pnlPts >= 0 ? "+" : "", pnlPts),
                        0, price, isWin ? Brushes.LimeGreen : Brushes.Red);

                    // Remove the global SL/TP/Entry horizontal lines (they span the entire chart)
                    RemoveDrawObject(tag + "_sl");
                    RemoveDrawObject(tag + "_tp");
                    RemoveDrawObject(tag + "_entryLine");

                    // Draw bounded SL/TP lines only within the trade's bar range
                    int barsInTrade = CurrentBar - _entryBar;
                    if (barsInTrade < 1) barsInTrade = 1;

                    Draw.Line(this, tag + "_slRange", false,
                        barsInTrade, _activeStop, 0, _activeStop,
                        Brushes.Red, DashStyleHelper.Dash, 1);
                    Draw.Line(this, tag + "_tpRange", false,
                        barsInTrade, _activeTarget, 0, _activeTarget,
                        Brushes.LimeGreen, DashStyleHelper.Dash, 1);
                    Draw.Line(this, tag + "_entryRange", false,
                        barsInTrade, _entryPrice, 0, _entryPrice,
                        Brushes.DodgerBlue, DashStyleHelper.Dot, 1);

                    // Connecting line from entry to exit
                    Draw.Line(this, tag + "_connector", false,
                        barsInTrade, _entryPrice, 0, price,
                        isWin ? Brushes.LimeGreen : Brushes.Red,
                        DashStyleHelper.Solid, 2);
                }
            }
        }

        // ── TCP: connect ──────────────────────────────────────────────────────

        private void ConnectToPython()
        {
            _running = true;
            try
            {
                _tcp    = new TcpClient(pythonHost, pythonPort);
                var ns  = _tcp.GetStream();
                _writer = new StreamWriter(ns, Encoding.UTF8) { AutoFlush = true };
                _reader = new StreamReader(ns, Encoding.UTF8);
                Print("[PythonSignal] Connected to Python at " + pythonHost + ":" + pythonPort);
            }
            catch (Exception ex)
            {
                Print("[PythonSignal] Could not connect to Python: " + ex.Message);
                Print("[PythonSignal] → Make sure 'python -m live.run_live' is running first.");
                return;
            }

            // Start background thread to read incoming messages from Python
            _readerThread = new Thread(ReaderLoop) { IsBackground = true, Name = "PythonReader" };
            _readerThread.Start();
        }

        private void DisconnectFromPython()
        {
            _running = false;
            try { _writer?.Close(); } catch { }
            try { _reader?.Close(); } catch { }
            try { _tcp?.Close();   } catch { }
            _readerThread?.Join(2000);
        }

        // ── TCP: background reader thread ─────────────────────────────────────

        private void ReaderLoop()
        {
            // This runs on a background thread.
            // We MUST NOT call NinjaScript order methods here.
            // Instead, store the signal and execute it in OnBarUpdate (NT's thread).
            try
            {
                while (_running)
                {
                    string line = _reader.ReadLine();
                    if (line == null) break;   // connection closed
                    line = line.Trim();
                    if (string.IsNullOrEmpty(line)) continue;

                    ParseAndDispatchMessage(line);
                }
            }
            catch (Exception ex)
            {
                if (_running)
                    Print("[PythonSignal] Reader thread error: " + ex.Message);
            }
            Print("[PythonSignal] Reader thread exited.");
        }

        private void ParseAndDispatchMessage(string json)
        {
            // Simple manual JSON parsing — avoids needing Newtonsoft.Json DLL.
            // Messages are flat single-level objects so this is safe.
            string type = ExtractString(json, "type");

            if (type == "SIGNAL")
            {
                var sig = new PendingSignal
                {
                    Action = ExtractString(json, "action"),
                    Entry  = ExtractDouble(json, "entry"),
                    Stop   = ExtractDouble(json, "stop"),
                    Target = ExtractDouble(json, "target"),
                    Qty    = (int)ExtractDouble(json, "qty"),
                    Id     = ExtractString(json, "id"),
                };

                if (string.IsNullOrEmpty(sig.Action) || sig.Entry == 0)
                {
                    Print("[PythonSignal] Malformed SIGNAL: " + json);
                    return;
                }

                // Marshal order submission onto NT's dispatch thread immediately —
                // do NOT wait for the next OnBarUpdate (that adds up to 60s delay).
                Dispatcher.InvokeAsync(() => ExecuteSignal(sig));
                Print("[PythonSignal] Dispatching SIGNAL: " + sig.Action + " " + sig.Id);
            }
            else if (type == "CLOSE")
            {
                Dispatcher.InvokeAsync(() => FlattenPosition());
                Print("[PythonSignal] Dispatching CLOSE");
            }
            else
            {
                Print("[PythonSignal] Unknown message type: " + type);
            }
        }

        // ── TCP: send bar ─────────────────────────────────────────────────────

        private void SendBarToPython()
        {
            if (_writer == null) return;
            try
            {
                // Send the just-closed bar (index 0 = current confirmed bar on OnBarClose)
                string ts   = Time[0].ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ");
                string json = string.Format(
                    "{{\"type\":\"BAR\",\"ts\":\"{0}\",\"open\":{1},\"high\":{2},\"low\":{3},\"close\":{4}}}",
                    ts,
                    Open[0].ToString("F2"),
                    High[0].ToString("F2"),
                    Low[0].ToString("F2"),
                    Close[0].ToString("F2")
                );
                lock (_tcpLock)
                    _writer.WriteLine(json);
            }
            catch (Exception ex)
            {
                Print("[PythonSignal] Failed to send bar: " + ex.Message);
                _writer = null;
            }
        }

        // ── Simple JSON field extractors ──────────────────────────────────────
        // These handle the flat JSON objects our Python sends.
        // They are NOT a general JSON parser — only use for known flat messages.

        private static string ExtractString(string json, string key)
        {
            // Looks for  "key":"value"  and returns value
            string search = "\"" + key + "\":\"";
            int start = json.IndexOf(search);
            if (start < 0) return "";
            start += search.Length;
            int end = json.IndexOf("\"", start);
            if (end < 0) return "";
            return json.Substring(start, end - start);
        }

        private static double ExtractDouble(string json, string key)
        {
            // Looks for  "key":number  and returns the number
            string search = "\"" + key + "\":";
            int start = json.IndexOf(search);
            if (start < 0) return 0;
            start += search.Length;
            int end = start;
            while (end < json.Length && (char.IsDigit(json[end]) || json[end] == '.' || json[end] == '-'))
                end++;
            if (end == start) return 0;
            double result;
            return double.TryParse(json.Substring(start, end - start),
                System.Globalization.NumberStyles.Any,
                System.Globalization.CultureInfo.InvariantCulture,
                out result) ? result : 0;
        }

        // ── Helper types ──────────────────────────────────────────────────────

        private class PendingSignal
        {
            public string Action;
            public double Entry;
            public double Stop;
            public double Target;
            public int    Qty;
            public string Id;
        }
    }
}
