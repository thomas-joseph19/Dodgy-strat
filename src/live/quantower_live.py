import socket
import threading
import time
import logging

class QuantowerLive:
    def __init__(self, host="127.0.0.1", port=8081):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.last_price = None
        self.last_bid = None
        self.last_ask = None
        self.on_quote_callback = None
        
        self.logger = logging.getLogger("QuantowerLive")
        logging.basicConfig(level=logging.INFO)

    def start(self):
        """Connects to the bridge and starts the listening thread."""
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()

    def _listen_loop(self):
        while self.running:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.host, self.port))
                self.logger.info("Connected to Quantower Bridge")
                
                # Buffer for incomplete lines
                buffer = ""
                
                while self.running:
                    data = self.socket.recv(4096).decode('utf-8')
                    if not data:
                        break
                        
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        self._process_line(line)
                        
            except Exception as e:
                self.logger.error(f"Bridge Connect Error: {e}. Retrying in 5s...")
                time.sleep(5)

    def _process_line(self, line):
        parts = line.split(",")
        if parts[0] == "QUOTE":
            try:
                # Format: QUOTE,SYMBOL,BID,ASK,LAST
                symbol, bid, ask, last = parts[1], float(parts[2]), float(parts[3]), float(parts[4])
                self.last_bid = bid
                self.last_ask = ask
                self.last_price = last
                
                if self.on_quote_callback:
                    self.on_quote_callback(symbol, bid, ask, last)
            except:
                pass

    def send_order(self, symbol, side, qty, comment="Python AI"):
        if not self.socket:
            return False
        try:
            message = f"ORDER_SEND,{symbol},{side},{qty},{comment}\n"
            self.socket.sendall(message.encode('utf-8'))
            return True
        except Exception as e:
            self.logger.error(f"Send Order Error: {e}")
            return False

if __name__ == "__main__":
    def my_handler(symbol, bid, ask, last):
        print(f"Price Update: {symbol} - {last}")

    q = QuantowerLive()
    q.on_quote_callback = my_handler
    q.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        q.stop()
