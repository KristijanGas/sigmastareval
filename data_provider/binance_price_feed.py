from datetime import datetime, timedelta
import json
import threading
import time
from zoneinfo import ZoneInfo
from websocket import WebSocketApp


class BinancePriceFeed:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()

        self._lock = threading.Lock()
        self._buffer = []

    def _on_message(self, ws, message):
        data = json.loads(message)

        price = (float(data["b"]) + float(data["a"])) / 2

        tick = {
            "symbol": self.symbol,
            "price": price,
            "timestamp": datetime.now(ZoneInfo("America/New_York")).timestamp()
        }
        
        with self._lock:
            if len(self._buffer) == 0 or price != self._buffer[-1]["price"]:
                self._buffer.append(tick)

    def start(self):
        url = (
            f"wss://stream.binance.com:9443/ws/"
            f"{self.symbol.lower()}@bookTicker"
        )

        self.ws = WebSocketApp(
            url,
            on_message=self._on_message,
        )
        thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        thread.start()

    def consume(self):
        with self._lock:
            data = self._buffer
            self._buffer = []
        return data
    
    def get_current_price(self):
        with self._lock:
            if len(self._buffer) == 0:
                return None
            return self._buffer[-1]["price"]

    def _run(self):
        while True:
            try:
                self.ws.run_forever()
            except Exception as e:
                print(f"Websocket error: {e}")

            print("Disconnected. Reconnecting in 3 seconds...")
            time.sleep(3)