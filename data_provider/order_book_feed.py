from datetime import datetime, timedelta
import json
import threading
import time
from zoneinfo import ZoneInfo

import urllib

class OrderBookFeed:
    def __init__(self, asset_id, order_book=None):
        self._lock = threading.Lock()
        self.asset_id = asset_id
        self.order_book = order_book

    def query_order_book(self, token_id):
        path = f"https://clob.polymarket.com/book?token_id={token_id}"
        #print(f"Fetching order book for token_id {token_id} from {path}")
        request = urllib.request.Request(
            path,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://polymarket.com/",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as url:
                market_data = json.loads(url.read().decode())
        except Exception as e:
            print(f"Error fetching CLOB data for token_id {token_id}: {e}")
            market_data = None
        return (token_id, market_data)
    
    def run(self):
        while True:
            try:
                order_book_for_asset = self.query_order_book(self.asset_id)
            except Exception as e:
                print(f"Error in OrderBookFeed WebSocket: {e}")
                time.sleep(5)  # Wait before trying to reconnect
            found = 0

            for i in range(len(self.order_book)):
                if self.order_book[i][0] == self.asset_id:
                    with self._lock:
                        self.order_book[i] = order_book_for_asset
                    found = 1
                    break

            if found == 0:
                with self._lock:
                    self.order_book.append([self.asset_id, order_book_for_asset])
