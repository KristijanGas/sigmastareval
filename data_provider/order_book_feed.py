import json
import time
import websocket

class OrderBookFeed:
    def __init__(self, asset_ids, order_book=None, lock=None):
        self._lock = lock
        self.asset_ids = asset_ids
        self.order_book = order_book
        self.stopped = False
        self.ws = None

    def _update_shared_book(self, market_data):
        """Safely updates or appends to the shared structure using your exact list layout."""
        found = False
        asset_id = market_data.get("asset_id")
        with self._lock:
            for i in range(len(self.order_book)):
                if self.order_book[i][0] == asset_id:
                    self.order_book[i] = [asset_id, market_data]
                    found = True
                    break
            
            if not found:
                self.order_book.append([asset_id, market_data])
        #print(self.order_book)

    def handle_price_changes(self, price_change):
        new_price = round(float(price_change["price"]), 5)
        new_size = round(float(price_change["size"]), 5)
        with self._lock:
            for i in range(len(self.order_book)):
                if self.order_book[i][0] == price_change["asset_id"]:
                    found = False
                    
                    if price_change["side"] == 'SELL':
                        all_asks = self.order_book[i][1].setdefault("asks", [])
                        for j in range(len(all_asks)):
                            ask_price = round(float(all_asks[j]["price"]), 5)
                            prev_ask_price = round(float(all_asks[j - 1]["price"]), 5) if j > 0 else 1.0
                            if ask_price == new_price:
                                if new_size > 0.0:
                                    all_asks[j]["size"] = new_size
                                else:
                                    all_asks.pop(j)
                                found = True
                                break
                            elif new_price > prev_ask_price and new_price < ask_price:
                                if new_size > 0.0:
                                    all_asks.insert(j, {"price": new_price, "size": new_size})
                                    found = True
                                break
                                
                        if not found and new_size > 0.0:
                            all_asks.append({"price": new_price, "size": new_size})

                    else:  # BUY Side
                        all_bids = self.order_book[i][1].setdefault("bids", [])
                        for j in range(len(all_bids)):
                            bid_price = round(float(all_bids[j]["price"]), 5)
                            prev_bid_price = round(float(all_bids[j - 1]["price"]), 5) if j > 0 else 0.0
                            if bid_price == new_price:
                                if new_size > 0.0:
                                    all_bids[j]["size"] = new_size
                                else:
                                    all_bids.pop(j)
                                found = True
                                break
                            elif new_price > prev_bid_price and new_price < bid_price:
                                if new_size > 0.0:
                                    all_bids.insert(j, {"price": new_price, "size": new_size})
                                found = True
                                break
                                
                        if not found and new_size > 0.0:
                            all_bids.append({"price": new_price, "size": new_size})
                    
                    break 


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
                    asset_id = event.get("asset_id")
                    if asset_id in self.asset_ids:
                        self._update_shared_book(event)
                elif event_type == "price_change":
                    for price_change in event.get("price_changes", []):
                        if price_change["asset_id"] in self.asset_ids:
                            self.handle_price_changes(price_change)

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
