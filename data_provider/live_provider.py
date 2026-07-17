from datetime import datetime, timedelta
import json
import sys
import threading
import time
from zoneinfo import ZoneInfo
from data_provider import historical_provider
from pathlib import Path

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[1]


from data_provider.binance_price_feed import BinancePriceFeed
from data.data_interface import parse_time_name_5m, parse_time_name_hourly


class live_provider(historical_provider):
    def __init__(self, binance_symbol, market_slug_base, market_type , market):
        self.binance_feed = BinancePriceFeed(binance_symbol)
        self.binance_feed.on_price_change = self.set_crypto_value
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
        self.run()

    def run(self):
        while True:
            try:
                if self.market_type == "hourly":
                    time_name = parse_time_name_hourly()["hourly_name"]
                elif self.market_type == "5m":
                    time_name = parse_time_name_5m()
                if self.last_time_name is None or time_name != self.last_time_name:
                    self.last_time_name = time_name
                    self.order_book = None
                    self.price_to_beat = None
                    self.end_timestamp = None
                    self.metadata = None
                    self.up_token_id = None
                    self.down_token_id = None
                    self.set_market()
                time.sleep(1)  # Sleep for a second before the next iteration
            except Exception as e:
                print(f"Error in live_provider run loop: {e}")
                time.sleep(1)



    def set_market(self):
        self.set_price_to_beat(self.get_crypto_value())
        
        outcome_name_list = json.loads(self.metadata[0]["markets"][0]["outcomes"])
        self.token_ids = json.loads(self.metadata[0]["markets"][0]["clobTokenIds"])
        for i in range(len(outcome_name_list)):
            if outcome_name_list[i] == "Up":
                self.up_token_id = self.token_ids[i]
            elif outcome_name_list[i] == "Down":
                self.down_token_id = self.token_ids[i]

    def get_current_timestamp(self):
        current_time = datetime.now(ZoneInfo("America/New_York"))
        current_time = int(current_time.timestamp() * 1000)
        return current_time
    
    def get_end_timestamp(self):
        return self.end_timestamp
    
    def get_crypto_value(self):
        return self.binance_feed.get_current_price()

    def set_order_book(self, order_book):
        self.order_book = order_book

    def set_end_timestamp(self, end_date):
        dt = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
        dt -= timedelta(hours=4)
        timestamp_ms = int(dt.timestamp() * 1000)
        self.end_timestamp = timestamp_ms
    
    def update_bids(self, asset_id, updated_bids):
        asset = self.get_asset(asset_id)
        for price, size in updated_bids.items():
            for level in asset["bids"]:
                if float(level["price"]) == price:
                    level["size"] = size
                    break
    def update_asks(self, asset_id, updated_asks):
        asset = self.get_asset(asset_id)
        for price, size in updated_asks.items():
            for level in asset["asks"]:
                if float(level["price"]) == price:
                    level["size"] = size
                    break
    