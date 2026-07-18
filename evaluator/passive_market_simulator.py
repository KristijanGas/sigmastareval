from pathlib import Path
import sys


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
    
    def run(self, market_type):
        while self.price_to_beat is None:
            self.price_to_beat = self.data_provider.get_price_to_beat()
            #print(f"Waiting for price to beat. Current value: {self.price_to_beat}")
        self.clobTokenIds = self.data_provider.get_market_asset_ids()
        self.outcomes = self.data_provider.get_outcomes()
        print(f"Price to beat: {self.price_to_beat}, market initialized with starting cash: {self.current_cash}")
        while True:
            if market_type == "hourly":
                time_name = parse_time_name_hourly()["hourly_name"]
            elif market_type == "5m":
                time_name = parse_time_name_5m()
            if self.old_time_name is not None:
                if time_name != self.old_time_name:
                    final_price = self.data_provider.get_crypto_value()
                    self.resolve_market(final_price, self.price_to_beat, self.outcomes, self.clobTokenIds)
                    self.price_to_beat = None
                    while self.price_to_beat is None:
                        self.price_to_beat = self.data_provider.get_price_to_beat()
                    self.clobTokenIds = self.data_provider.get_market_asset_ids()
                    self.outcomes = self.data_provider.get_outcomes()
            self.old_time_name = time_name
            self.process_orders()