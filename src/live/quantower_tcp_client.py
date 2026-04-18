import socket
import json
import logging

class QuantowerTCPClient:
    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port
        self.logger = logging.getLogger("QuantowerBridge")
        logging.basicConfig(level=logging.INFO)

    def send_order(self, symbol, side, qty, comment="Live AI Trade"):
        """
        Sends an order signal to the C# Bridge.
        Format: "ORDER_SEND,SYMBOL,SIDE,QTY,COMMENT"
        """
        try:
            # Construct the simple comma-separated message
            message = f"ORDER_SEND,{symbol},{side},{qty},{comment}"
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((self.host, self.port))
                s.sendall(message.encode('utf-8'))
                
            self.logger.info(f"Successfully sent {side} {qty} {symbol} to Quantower")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send order to Quantower: {e}")
            return False

if __name__ == "__main__":
    # Test call
    client = QuantowerTCPClient()
    client.send_order("NQ H4", "Buy", 1, "Python Test Trade")
