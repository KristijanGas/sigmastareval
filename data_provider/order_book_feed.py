import json
import time
import websocket

class OrderBookFeed:
    def __init__(self, asset_id, order_book=None, lock=None):
        self._lock = lock
        self.asset_id = str(asset_id)  # Ensure asset ID is string-formatted
        self.order_book = order_book
        self.stopped = False
        self.ws = None

    def _update_shared_book(self, market_data):
        """Safely updates or appends to the shared structure using your exact list layout."""
        found = False
        with self._lock:
            for i in range(len(self.order_book)):
                if self.order_book[i][0] == self.asset_id:
                    self.order_book[i] = [self.asset_id, market_data]
                    found = True
                    break
            
            if not found:
                self.order_book.append([self.asset_id, market_data])
        #print(self.order_book)

    def handle_price_changes(self, price_change):
        with self._lock:
            for i in range(len(self.order_book)):
                if self.order_book[i][0] == price_change["asset_id"]:
                    print(self.order_book[i][1], price_change)



    def _on_message(self, ws, message):
        """Processes real-time book frames directly from Polymarket."""
        try:
            data = json.loads(message)

            # Polymarket often sends a list of events
            if isinstance(data, list):
                events = data
            else:
                events = [data]

            for event in events:
                event_type = event.get("event_type")

                if event_type in ("book", "tick_size_change"):
                    self._update_shared_book(event)
                elif event_type == "price_change":
                    for price_change in event.get("price_changes", []):
                        self.handle_price_changes(price_change)

        except Exception as e:
            print(message)
            print(f"Error parsing Polymarket WS frame: {e}")

    def _on_open(self, ws):
        """Sends the exact subscription payload format required by Polymarket CLOB."""
        subscribe_payload = {
            "type": "market",
            "assets_ids": [self.asset_id],
            "custom_feature_enabled": True
        }
        ws.send(json.dumps(subscribe_payload))
        print(f"Subscription frame sent for asset: {self.asset_id}")

    def _on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket closed: {close_status_code} - {close_msg}")

    def run(self):
        """Executes the connection loop safely over the background thread."""
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
                time.sleep(5) 

    def stop(self):
        """Kills the active connection gracefully."""
        self.stopped = True
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
