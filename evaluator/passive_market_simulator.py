import json
import os
from pathlib import Path
import sys
from time import time
import gzip


if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[1]


from bot.order_actions import OrderAction
from bot.order_types import OrderType
from evaluator.market_simulator import market_simulator
from data.data_interface import parse_time_name_5m, parse_time_name_hourly

class passive_market_simulator(market_simulator):
    def __init__(self, data_provider, starting_cash, base_name):
        super().__init__(data_provider, starting_cash, base_name)
        self.old_time_name = None
        self.price_to_beat = None
        self.clobTokenIds = None
        self.outcomes = None
        self.holdings_history = []
        self.cash_history = []
    
    def run(self, market_type):
        while True:
            while self.price_to_beat is None:
                self.price_to_beat = self.data_provider.get_price_to_beat()
                time.sleep(0.1)
            while self.clobTokenIds is None or self.outcomes is None:
                self.clobTokenIds = self.data_provider.get_market_asset_ids()
                self.outcomes = self.data_provider.get_outcomes()
                time.sleep(0.1)
            print(f"Price to beat: {self.price_to_beat}, market initialized with starting cash: {self.current_cash}")
            print(f"Market asset IDs: {self.clobTokenIds}, Market outcomes: {self.outcomes}")
            while True:
                if market_type == "hourly":
                    time_name = parse_time_name_hourly()["hourly_name"]
                elif market_type == "5m":
                    time_name = parse_time_name_5m()
                if self.old_time_name is not None:
                    self.clobTokenIds = self.data_provider.get_market_asset_ids()
                    self.outcomes = self.data_provider.get_outcomes()
                    if time_name != self.old_time_name:
                        final_price = self.data_provider.get_crypto_value()
                        print("Final price: ", final_price, self.price_to_beat, self.outcomes, self.clobTokenIds)
                        self.resolve_market(final_price, self.price_to_beat, self.outcomes, self.clobTokenIds)
                        self.price_to_beat = None
                        self.clobTokenIds = None
                        self.outcomes = None
                        self.store_analytics()
                        self.cash_history.clear()
                        self.holdings_history.clear()
                        self.old_time_name = time_name
                        break
                time.sleep(0.1)
                self.holdings_history.append(
                    {
                        "timestamp" : self.data_provider.get_current_timestamp(),
                        "holdings" : self.data_provider.get_holdings()
                    }
                )
                self.cash_history.append(
                    {
                        "timestamp" : self.data_provider.get_current_timestamp(),
                        "cash" : self.data_provider.get_cash()
                    }
                )
                self.old_time_name = time_name
                self.process_orders()
    
    def store_analytics(self, analytics):
        # Store the cash and holdings history in the analytics dictionary
        analytics["cash_history"] = self.cash_history
        analytics["holdings_history"] = self.holdings_history
        analytics["final_cash"] = self.current_cash
        analytics["order_placements"] = self.order_placements
        analytics["transactions"] = self.transactions

        store_path = REPO_ROOT / "live_runs" / "passive" / f"{self.base_name}" / f"{self.base_name}-{self.old_time_name}.json.gz"
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        with gzip.open(store_path, "wt", encoding="utf-8") as f:
            json.dump(analytics, f)