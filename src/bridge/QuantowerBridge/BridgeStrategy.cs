using System;
using System.Collections.Generic;
using System.Linq;
using Fleck;
using Newtonsoft.Json;
using TradingPlatform.BusinessLayer;

namespace QuantowerBridge
{
    [StrategyAttribute("Quantower API Bridge", ShortName = "PYBR", Version = "1.0")]
    public class BridgeStrategy : Strategy, ICurrentAccount, ICurrentSymbol
    {
        // These properties are required by ICurrentAccount and ICurrentSymbol 
        // and will be automatically populated by Quantower
        [InputParameter("Account", 0)]
        public Account CurrentAccount { get; set; }

        [InputParameter("Symbol", 1)]
        public Symbol CurrentSymbol { get; set; }

        private WebSocketServer _server;
        private List<IWebSocketConnection> _allSockets = new List<IWebSocketConnection>();

        public BridgeStrategy()
        {
            // Metadata
            this.Name = "Strategy API Bridge";
            this.Description = "Exposes Quantower API via WebSocket for Python/Node.js strategies.";
        }

        protected override void OnRun()
        {
            try 
            {
                _server = new WebSocketServer("ws://127.0.0.1:8080");
                _server.Start(socket =>
                {
                    socket.OnOpen = () =>
                    {
                        this.Log("Bridge: Client connected", StrategyLoggingLevel.Info);
                        _allSockets.Add(socket);
                    };
                    socket.OnClose = () =>
                    {
                        this.Log("Bridge: Client disconnected", StrategyLoggingLevel.Info);
                        _allSockets.Remove(socket);
                    };
                    socket.OnMessage = message => HandleMessage(socket, message);
                });

                this.Log("Bridge: WebSocket server started on ws://127.0.0.1:8080", StrategyLoggingLevel.Info);
            }
            catch (Exception ex)
            {
                this.Log($"Bridge error on startup: {ex.Message}", StrategyLoggingLevel.Error);
            }
        }

        protected override void OnStop()
        {
            _server?.Dispose();
            _allSockets.Clear();
            this.Log("Bridge: WebSocket server stopped", StrategyLoggingLevel.Info);
        }

        private void HandleMessage(IWebSocketConnection socket, string message)
        {
            try
            {
                var command = JsonConvert.DeserializeObject<TradeCommand>(message);
                if (command == null) return;

                switch (command.Action)
                {
                    case "ORDER_SEND":
                        ExecuteOrder(command);
                        break;
                    default:
                        this.Log($"Bridge: Unknown action {command.Action}", StrategyLoggingLevel.Warning);
                        break;
                }
            }
            catch (Exception ex)
            {
                this.Log($"Bridge message processing error: {ex.Message}", StrategyLoggingLevel.Error);
                socket.Send(JsonConvert.SerializeObject(new { status = "error", message = ex.Message }));
            }
        }

        private void ExecuteOrder(TradeCommand cmd)
        {
            // Use the account from the UI or fall back to first available
            var account = this.CurrentAccount ?? Core.Instance.Trading.Accounts.FirstOrDefault();
            
            if (account == null)
            {
                this.Log("Bridge: No trading account found!", StrategyLoggingLevel.Error);
                return;
            }

            // Use the symbol from the message
            var symbol = Core.Instance.Symbols.GetSymbol(cmd.Params.Symbol);
            if (symbol == null)
            {
                this.Log($"Bridge: Symbol {cmd.Params.Symbol} not found!", StrategyLoggingLevel.Error);
                return;
            }

            var side = cmd.Params.Side.Equals("Buy", StringComparison.OrdinalIgnoreCase) ? Side.Buy : Side.Sell;

            var request = new PlaceOrderRequestParameters()
            {
                Account = account,
                Symbol = symbol,
                OrderSide = side,
                OrderType = OrderType.Market,
                Quantity = cmd.Params.Qty,
                Comment = cmd.Params.Comment ?? "Bridge Order"
            };
            
            var result = Core.Instance.Trading.PlaceOrder(request);
            this.Log($"Bridge: Order placed for {symbol.Name}. Status: {result.Status}", StrategyLoggingLevel.Info);
        }
    }

    public class TradeCommand
    {
        [JsonProperty("client_id")]
        public string ClientId { get; set; }

        [JsonProperty("action")]
        public string Action { get; set; }

        [JsonProperty("params")]
        public OrderParams Params { get; set; }
    }

    public class OrderParams
    {
        [JsonProperty("symbol")]
        public string Symbol { get; set; }

        [JsonProperty("side")]
        public string Side { get; set; }

        [JsonProperty("qty")]
        public double Qty { get; set; }

        [JsonProperty("comment")]
        public string Comment { get; set; }
    }
}
