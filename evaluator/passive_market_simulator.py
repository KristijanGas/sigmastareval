import json
import os
from pathlib import Path
import sys
import time
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
        print(f"Starting passive market simulator for {self.base_name} with starting cash: {self.current_cash}")
        while True:
            if market_type == "hourly":
                time_name = parse_time_name_hourly()["hourly_name"]
            elif market_type == "5m":
                time_name = parse_time_name_5m()
            while self.data_provider.current_market_name is None or self.data_provider.current_market_name != f"{self.base_name}-{time_name}":
                print("Waiting for live provider to set current market name...")
                time.sleep(0.1)
            while self.price_to_beat is None:
                self.price_to_beat = self.data_provider.get_price_to_beat()
                print(f"Waiting for price to beat to be set. Current value: {self.price_to_beat}")
                time.sleep(0.1)
            while self.clobTokenIds is None or self.outcomes is None:
                self.clobTokenIds = self.data_provider.get_market_asset_ids()
                self.outcomes = self.data_provider.get_outcomes()
                print(f"Waiting for market asset IDs and outcomes to be set. Current values: {self.clobTokenIds}, {self.outcomes}")
                time.sleep(0.1)
            print(f"Price to beat: {self.price_to_beat}, market initialized with starting cash: {self.current_cash}")
            print(f"Market asset IDs: {self.clobTokenIds}, Market outcomes: {self.outcomes}")
            while True:
                time.sleep(0.1)
                if market_type == "hourly":
                    time_name = parse_time_name_hourly()["hourly_name"]
                elif market_type == "5m":
                    time_name = parse_time_name_5m()
                if self.old_time_name is not None:
                    #print(f"Time name: {time_name}, Old time name: {self.old_time_name}, Price to beat: {self.price_to_beat}, Outcomes: {self.outcomes}, CLOB Token IDs: {self.clobTokenIds}")
                    if time_name != self.old_time_name:
                        final_price = self.data_provider.get_crypto_value()
                        print(f"Final price: {final_price}, Price to beat: {self.price_to_beat}, Outcomes: {self.outcomes}, CLOB Token IDs: {self.clobTokenIds}")
                        self.resolve_market(final_price, self.price_to_beat, self.outcomes, self.clobTokenIds)
                        self.price_to_beat = None
                        self.clobTokenIds = None
                        self.outcomes = None
                        self.store_analytics()
                        self.cash_history.clear()
                        self.holdings_history.clear()
                        self.old_time_name = time_name
                        break
                
                self.holdings_history.append(
                    {
                        "timestamp" : self.data_provider.get_current_timestamp(),
                        "holdings" : self.get_user_holdings()
                    }
                )
                self.cash_history.append(
                    {
                        "timestamp" : self.data_provider.get_current_timestamp(),
                        "cash" : self.get_user_cash()
                    }
                )
                self.old_time_name = time_name
                try:
                    self.process_orders()
                except Exception as e:
                    print(f"MARKET SIMULATOR: Error occurred while processing orders: {e}")
    
    def store_analytics(self):
        # Store the cash and holdings history in the analytics dictionary
        analytics = {}
        analytics["cash_history"] = self.cash_history
        analytics["holdings_history"] = self.holdings_history
        analytics["final_cash"] = self.current_cash
        analytics["order_placements"] = self.order_placements
        analytics["transactions"] = self.transactions
        self.order_placements.clear()
        self.transactions.clear()
        self.holdings_history.clear()
        self.cash_history.clear()

        store_path = REPO_ROOT / "live_runs" / "passive" / f"{self.base_name}" / f"{self.base_name}-{self.old_time_name}.json.gz"
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        with gzip.open(store_path, "wt", encoding="utf-8") as f:
            json.dump(analytics, f)