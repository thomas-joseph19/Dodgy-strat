using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using TradingPlatform.BusinessLayer;

namespace QuantowerBridge
{
    public class BridgeScript : Strategy, ICurrentSymbol
    {
        [InputParameter("Server Port", 10)]
        public int Port = 8081;

        public Symbol CurrentSymbol { get; set; }

        private TcpListener _listener;
        private Thread _serverThread;
        private bool _isRunning;
        private List<TcpClient> _subscribedClients = new List<TcpClient>();

        public override string Name => "Dodgy API Bridge (v2)";

        public BridgeScript()
        {
            this.Description = "Bi-directional TCP bridge for Data & Execution.";
        }

        protected override void OnRun()
        {
            if (this.CurrentSymbol == null)
            {
                this.Log("Bridge: Please select a symbol in the strategy settings!", StrategyLoggingLevel.Error);
                return;
            }

            // Subscribe to real-time quotes
            this.CurrentSymbol.NewQuote += CurrentSymbol_NewQuote;

            _isRunning = true;
            _serverThread = new Thread(StartServer);
            _serverThread.IsBackground = true;
            _serverThread.Start();
            
            this.Log("Bridge: Bi-directional Server starting on port " + Port, StrategyLoggingLevel.Info);
        }

        protected override void OnStop()
        {
            _isRunning = false;
            
            if (this.CurrentSymbol != null)
                this.CurrentSymbol.NewQuote -= CurrentSymbol_NewQuote;

            _listener?.Stop();
            _serverThread?.Join(500);

            lock(_subscribedClients)
            {
                foreach(var client in _subscribedClients)
                    client.Close();
                _subscribedClients.Clear();
            }

            this.Log("Bridge: TCP Server stopped", StrategyLoggingLevel.Info);
        }

        private void CurrentSymbol_NewQuote(Symbol symbol, Quote quote)
        {
            // Broadcast price to all connected clients
            // Format: "QUOTE,SYMBOL,BID,ASK,LAST"
            string msg = $"QUOTE,{symbol.Name},{quote.Bid},{quote.Ask},{quote.Last}\n";
            byte[] data = Encoding.UTF8.GetBytes(msg);

            lock(_subscribedClients)
            {
                for (int i = _subscribedClients.Count - 1; i >= 0; i--)
                {
                    try {
                        var client = _subscribedClients[i];
                        if (client.Connected)
                            client.GetStream().Write(data, 0, data.Length);
                        else
                            _subscribedClients.RemoveAt(i);
                    } catch {
                        _subscribedClients.RemoveAt(i);
                    }
                }
            }
        }

        private void StartServer()
        {
            try
            {
                _listener = new TcpListener(IPAddress.Loopback, Port);
                _listener.Start();

                while (_isRunning)
                {
                    var client = _listener.AcceptTcpClient();
                    lock(_subscribedClients) {
                        _subscribedClients.Add(client);
                    }
                    
                    // Spawn a thread to handle this client's incoming commands
                    var t = new Thread(() => HandleClient(client));
                    t.IsBackground = true;
                    t.Start();
                }
            }
            catch (Exception ex)
            {
                if (_isRunning)
                    this.Log("Bridge Server Error: " + ex.Message, StrategyLoggingLevel.Error);
            }
        }

        private void HandleClient(TcpClient client)
        {
            try {
                using (var stream = client.GetStream())
                {
                    var buffer = new byte[4096];
                    while (_isRunning && client.Connected)
                    {
                        if (stream.DataAvailable) {
                            int bytesRead = stream.Read(buffer, 0, buffer.Length);
                            string message = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                            HandleSignal(message);
                        }
                        Thread.Sleep(50);
                    }
                }
            } catch { }
            finally {
                lock(_subscribedClients) { _subscribedClients.Remove(client); }
            }
        }

        private void HandleSignal(string message)
        {
            try
            {
                var lines = message.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries);
                foreach(var line in lines) {
                    var parts = line.Split(',');
                    if (parts[0] == "ORDER_SEND")
                    {
                        ExecuteOrder(parts[1], parts[2], double.Parse(parts[3]), parts.Length > 4 ? parts[4] : "Bridge Order");
                    }
                }
            }
            catch (Exception ex)
            {
                this.Log("Bridge Parsing Error: " + ex.Message, StrategyLoggingLevel.Error);
            }
        }

        private void ExecuteOrder(string symbolCode, string sideStr, double qty, string comment)
        {
            var account = Core.Instance.Trading.Accounts.FirstOrDefault();
            if (account == null) return;

            var symbol = Core.Instance.Symbols.GetSymbol(symbolCode);
            if (symbol == null) return;

            var side = sideStr.Equals("Buy", StringComparison.OrdinalIgnoreCase) ? Side.Buy : Side.Sell;

            var request = new PlaceOrderRequestParameters()
            {
                Account = account,
                Symbol = symbol,
                OrderSide = side,
                OrderType = OrderType.Market,
                Quantity = qty,
                Comment = comment
            };

            Core.Instance.Trading.PlaceOrder(request);
        }
    }
}
