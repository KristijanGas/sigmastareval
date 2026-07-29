from datetime import datetime, timedelta
import json
import sys
import threading
import time
from zoneinfo import ZoneInfo

import urllib.request
import urllib.parse
from pathlib import Path

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[1]


from data_provider.binance_price_feed import BinancePriceFeed
from data.data_interface import parse_time_name_5m, parse_time_name_hourly
from data_provider.order_book_feed import OrderBookFeed
from data_provider.historical_provider import historical_provider


class live_provider(historical_provider):
    def __init__(self, market_slug_base, binance_symbol, market_type , market):
        self.binance_feed = BinancePriceFeed(binance_symbol, correct_timestamps=True)
        self.binance_feed.start()
        self.market = market
        self.market_slug_base = market_slug_base
        self.market_type = market_type

        self.last_time_name = None
        self.order_book = None
        self.crypto_value = None
        self.price_to_beat = None
        self.end_timestamp = None
        self.metadata = None
        self.up_token_id = None
        self.down_token_id = None
        self.token_ids = None
        self.fair_value_down = None
        self.fair_value_up = None
        self.order_book_feed = None
        self.current_market_name = None
        self.moving_mean_time = 60000

        self.moving_mean_sum = 0.0
        self.moving_mean = None

        self.moving_mean_l = 0
        self.moving_mean_r = 0
        self.moving_mean_l_time = 0
        self.moving_mean_r_time = 0
        #self.run()

    def run(self):
        while True:
            #try:
                if self.market_type == "hourly":
                    time_name = parse_time_name_hourly()["hourly_name"]
                elif self.market_type == "5m":
                    time_name = parse_time_name_5m()

                if self.last_time_name is None or time_name != self.last_time_name:
                    self.last_time_name = time_name
                    self.order_book = []
                    self.price_to_beat = None
                    self.end_timestamp = None
                    self.metadata = None
                    self.up_token_id = None
                    self.down_token_id = None
                    self.token_ids = None
                    if self.order_book_feed is not None and self.order_book_feed.is_alive():
                        self.order_book_feed.stop()
                        self.order_book_feed.join()

                    self.set_market(time_name)
                    #self.binance_feed.consume()
                
                self.metadata = self.get_metadata(time_name, self.market_slug_base)
                try:
                    self.set_price_to_beat(self.metadata[0]["eventMetadata"]["priceToBeat"])
                except Exception as e:
                    #print(f"Error setting price to beat: {e}")
                    #print(self.metadata[0])
                    pass
                self.update_moving_mean()
                #time.sleep(0.1)  # Sleep for a second before the next iteration
                #print(self.get_best_bid(self.up_token_id), self.get_best_bid(self.down_token_id), self.get_best_ask(self.up_token_id), self.get_best_ask(self.down_token_id), self.get_crypto_value(), self.get_price_to_beat(), self.get_current_timestamp(), self.get_end_timestamp())
            #except Exception as e:
            #    print(f"Error in live_provider run loop: {e}")
            #    time.sleep(1)

    def get_metadata(self, time_name, market_slug_base):
        
        #print(f"Fetching market metadata for {market} at {time_name}")
        full_name = f"{market_slug_base}-{time_name}"
        path = f"https://gamma-api.polymarket.com/events?slug={full_name}"
        #print(path)
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
                market_metadata = json.loads(url.read().decode())
        except Exception as e:
            print(f"Error fetching market metadata for {full_name} at {time_name}: {e}")
            market_metadata = None
        return market_metadata

    def set_market(self, time_name):
        self.set_price_to_beat(self.get_crypto_value())
        self.moving_mean_sum = 0.0
        self.moving_mean = None
        self.moving_mean_l = 0
        self.moving_mean_r = 0
        self.moving_mean_l_time = 0
        self.moving_mean_r_time = 0
        while self.metadata is None:
            try:
                self.metadata = self.get_metadata(time_name, self.market_slug_base)
            except Exception as e:
                #print(f"Error fetching metadata for {self.market_slug_base} at {time_name}: {e}")
                time.sleep(1)

        self.set_end_timestamp(self.metadata[0]["endDate"])

        outcome_name_list = json.loads(self.metadata[0]["markets"][0]["outcomes"])
        self.token_ids = json.loads(self.metadata[0]["markets"][0]["clobTokenIds"])
        for i in range(len(outcome_name_list)):
            if outcome_name_list[i] == "Up":
                self.up_token_id = self.token_ids[i]
            elif outcome_name_list[i] == "Down":
                self.down_token_id = self.token_ids[i]
        for token_id in self.token_ids:
            self.market.set_min_order_size(token_id, self.metadata[0]["markets"][0]["orderMinSize"])

        self.order_book_lock = threading.Lock()
        self.order_book_feed = OrderBookFeed([self.up_token_id, self.down_token_id], self.order_book, self.order_book_lock)

        # start threads
        self.order_book_feed = threading.Thread(target=self.order_book_feed.run, daemon=True)
        self.order_book_feed.start()
        while self.order_book is None or len(self.order_book) < 2:
            time.sleep(0.1)
        print(f"Set live provider with Up token ID: {self.up_token_id}, Down token ID: {self.down_token_id}, End timestamp: {self.end_timestamp}")
        self.current_market_name = f"{self.market_slug_base}-{time_name}"

    def get_current_timestamp(self):
        current_time = datetime.now(ZoneInfo("America/New_York"))
        current_time = int(current_time.timestamp() * 1000)
        return current_time

    def get_past_crypto_values(self):
        return self.binance_feed.read_buffer()
    
    def get_outcomes(self):
        if self.metadata is not None:
            return json.loads(self.metadata[0]["markets"][0]["outcomes"])
        else:
            return None
    
    def get_crypto_value(self):
        return self.binance_feed.get_current_price()

    def consume_crypto_values(self):
        return self.binance_feed.consume()

    def set_end_timestamp(self, end_date):
        dt = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
        dt -= timedelta(hours=4)
        timestamp_ms = int(dt.timestamp() * 1000)
        self.end_timestamp = timestamp_ms
    
    def update_bids(self, asset_id, updated_bids):
        asset = self.get_asset(asset_id)
        for price, size in updated_bids.items():
            for level in asset.get("bids", []):
                if float(level["price"]) == price:
                    level["size"] = size
                    break
    def update_asks(self, asset_id, updated_asks):
        asset = self.get_asset(asset_id)
        for price, size in updated_asks.items():
            for level in asset.get("asks", []):
                if float(level["price"]) == price:
                    level["size"] = size
                    break
    
    
if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python live_provider.py <market_slug_base> <binance_symbol> <market_type>")
        sys.exit(1)
    market_slug_base = sys.argv[1]
    binance_symbol = sys.argv[2]
    market_type = sys.argv[3]
    provider = live_provider(market_slug_base, binance_symbol, market_type, None)
    provider.run()