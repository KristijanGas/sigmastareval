import json
import os
from pathlib import Path
import sys
import time
import gzip
import uuid


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
    def __init__(self, data_provider, starting_cash, base_name, bot):
        super().__init__(data_provider, starting_cash, base_name)
        self.old_time_name = None
        self.price_to_beat = None
        self.clobTokenIds = None
        self.outcomes = None
        self.bot = bot
        self.holdings_history = []
        self.cash_history = []
        self.mid_prices = {}

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
                time.sleep(0.05)
                if market_type == "hourly":
                    time_name = parse_time_name_hourly()["hourly_name"]
                elif market_type == "5m":
                    time_name = parse_time_name_5m()
                if self.old_time_name is not None:
                    #print(f"Time name: {time_name}, Old time name: {self.old_time_name}, Price to beat: {self.price_to_beat}, Outcomes: {self.outcomes}, CLOB Token IDs: {self.clobTokenIds}")
                    if time_name != self.old_time_name:
                        final_price = self.data_provider.get_crypto_value()
                        print(f"Final price: {final_price}, Price to beat: {self.price_to_beat}, Outcomes: {self.outcomes}, CLOB Token IDs: {self.clobTokenIds}")
                        resolution = self.resolve_market(final_price, self.price_to_beat, self.outcomes, self.clobTokenIds)
                        self.store_analytics(resolution)
                        self.old_time_name = time_name
                        break
                #print(self.get_user_holdings())
                current_timestamp = self.data_provider.get_current_timestamp()
                asset_ids = self.data_provider.get_market_asset_ids()
                self.holdings_history.append(
                    {
                        "timestamp": current_timestamp,
                        "holdings": {
                            asset_id: self.get_user_holdings().get(asset_id, 0)
                            for asset_id in asset_ids
                        },
                    }
                )
                self.cash_history.append(
                    {
                        "timestamp": current_timestamp,
                        "cash": self.get_user_cash()
                    }
                )
                mid_price_updates = []

                try:
                    for asset_id in asset_ids:
                        mid_price = self.data_provider.get_mid_price(asset_id)
                        mid_price_updates.append((asset_id, mid_price))

                    # Commit only after all fetches succeeded
                    for asset_id, mid_price in mid_price_updates:
                        self.mid_prices.setdefault(asset_id, []).append({
                            "mid_price": mid_price,
                            "timestamp": current_timestamp,
                        })
                except Exception as e:
                    print(f"Error occurred while fetching mid price for {asset_id}: {e}")

                self.old_time_name = time_name
                try:
                    self.process_orders()
                except Exception as e:
                    print(f"MARKET SIMULATOR: Error occurred while processing orders: {e}")
    
    def store_analytics(self, resolution):
        # Store the cash and holdings history in the analytics dictionary
        asset_labels = {
            self.clobTokenIds[index]: self.outcomes[index]
            for index in range(min(len(self.outcomes), len(self.clobTokenIds)))
        }
        analytics = {}
        analytics["resolution"] = resolution
        analytics["cash_history"] = self.cash_history
        analytics["holdings_history"] = self.holdings_history
        analytics["final_cash"] = self.current_cash
        analytics["order_placements"] = self.order_placements
        analytics["transactions"] = self.transactions
        analytics["matching_delay"] = self.matching_delay
        analytics["on_chain_delay"] = self.on_chain_delay
        analytics["order_timeout"] = self.order_timeout
        analytics["past_crypto_predictions"] = self.bot.past_crypto_predictions
        analytics["on_chain_order_matches"] = self.order_matches
        analytics["mid_prices"] = self.mid_prices
        analytics["crypto_prices"] = self.data_provider.consume_crypto_values()
        analytics["price_to_beat"] = self.price_to_beat
        analytics["asset_labels"] = asset_labels
        unique_hash = uuid.uuid4().hex
        store_path = REPO_ROOT / "live_runs" / "passive" / f"{self.base_name}" / f"{self.base_name}-{self.old_time_name}_{unique_hash}.json.gz"
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        with gzip.open(store_path, "wt", encoding="utf-8") as f:
            json.dump(analytics, f)
        self.order_placements.clear()
        self.transactions.clear()
        self.holdings_history.clear()
        self.cash_history.clear()
        self.mid_prices.clear()
        self.bot.past_crypto_predictions.clear()
        self.price_to_beat = None
        self.clobTokenIds = None
        self.outcomes = None