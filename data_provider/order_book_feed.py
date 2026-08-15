import json
import threading
import time
import websocket
import queue

class OrderBookFeed:
    def __init__(self, asset_ids, order_book=None):
        self.asset_ids = asset_ids
        self.change_queue = queue.SimpleQueue()
        for asset_id in asset_ids:
            order_book[asset_id] = {"bids": {}, "asks": {}, "best_bid": None, "best_ask": None}
        self.order_book = order_book
        self.stopped = False
        self.socket_thread = None
        self.ws = None

    def _on_message(self, ws, message):
        """Processes real-time book frames directly from Polymarket."""
        try:
            data = json.loads(message)

            # Polymarket often sends a list of events
            if isinstance(data, dict):
                data = [data]

            for event in data:
                event_type = event.get("event_type")
                if event_type in ("price_change", "book", "tick_size_change"):
                    self.change_queue.put(event)

        except Exception as e:
            print(message)
            print(f"Error parsing Polymarket WS frame: {e}")

    def _on_open(self, ws):
        """Sends the exact subscription payload format required by Polymarket CLOB."""
        subscribe_payload = {
            "type": "market",
            "assets_ids": self.asset_ids,
            "custom_feature_enabled": True
        }
        ws.send(json.dumps(subscribe_payload))
        print(f"Subscription frame sent for assets: {self.asset_ids}")

    def _on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket closed: {close_status_code} - {close_msg}")

    def process_book_updates(self):
        while not self.stopped:
            try:
                update = self.change_queue.get(timeout=10.0)
            except queue.Empty:
                continue
            if self.stopped:
                return
            try:
                if update["event_type"] == "price_change":
                    for price_change in update["price_changes"]:
                        asset_id = price_change["asset_id"]
                        working_copy = {"bids": self.order_book[asset_id]["bids"], 
                                        "asks": self.order_book[asset_id]["asks"], 
                                        "best_bid": float(price_change["best_bid"]), 
                                        "best_ask": float(price_change["best_ask"])
                                        }
                        self.order_book[asset_id] = working_copy
                        size = float(price_change["size"])
                        price = float(price_change["price"])
                        if price_change["side"] == "BUY":
                            if size > 0:
                                self.order_book[asset_id]["bids"][price] = size
                            else:
                                self.order_book[asset_id]["bids"].pop(price, None)

                        else:
                            if size > 0:
                                self.order_book[asset_id]["asks"][price] = size
                            else:
                                self.order_book[asset_id]["asks"].pop(price, None)
                else:
                    asset_id = update["asset_id"]
                    working_copy = {"bids": {}, "asks": {}}
                    best_bid = 0
                    best_ask = 1
                    for bid in update.get("bids", []):
                        size = float(bid["size"])
                        price = float(bid["price"])
                        working_copy["bids"][price] = size
                        best_bid = max(best_bid, price)
                    for ask in update.get("asks", []):
                        size = float(ask["size"])
                        price = float(ask["price"])
                        working_copy["asks"][price] = size
                        best_ask = min(best_ask, price)
                    working_copy["best_bid"] = best_bid
                    working_copy["best_ask"] = best_ask
                    self.order_book[asset_id] = working_copy
            except Exception as e:
                print(f"Error processing order book update for {asset_id}: {e}")

        return

    def run(self):
        """Executes the connection loop safely over the background thread."""
        self.socket_thread = threading.Thread(target=self.websocket_listen)
        self.socket_thread.start()
        self.process_book_updates()

    def websocket_listen(self):

        websocket_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        while not self.stopped:
            try:
                self.ws = websocket.WebSocketApp(
                    websocket_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                self.ws.run_forever(
                    ping_interval=10,
                    ping_timeout=5
                )
                
            except Exception as e:
                print(f"Reconnecting after socket failure: {e}")
            
            if not self.stopped:
                time.sleep(0.2)
        return

    def stop(self):
        """Kills the active connection gracefully."""
        self.stopped = True
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        if self.socket_thread:
            self.socket_thread.join()
