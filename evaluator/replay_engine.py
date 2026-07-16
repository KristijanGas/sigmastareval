import os
import sys
import gzip
import json
from pathlib import Path
from enum import Enum
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
import json
import threading

from utils.utils import sort_paths_chronologically



if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[1]


def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return str(value)

from bot.masterbot import masterbot
from market_simulator import market_simulator
from data_provider.historical_provider import historical_provider
from bot.prediction_models.nostradamus import nostradamus

class replay_engine:
    def __init__(self, bot: masterbot, reset_bot_between_runs=True):
        self.bot = bot
        self.reset_bot_between_runs = reset_bot_between_runs
        self.strategy_only_evaluation = False


    def initialize_environment(self, starting_cash, data, filename):
        """
        Initializes the environment for the bot to run in.
        """
        if self.reset_bot_between_runs:
            self.bot = load_bot(sys.argv[1])
        self.data_provider = historical_provider(data["metadata_start"])
        base_name = None
        filename_string = str(str(filename).split("/")[-1])
        if filename_string[:18] == "bitcoin-up-or-down":
            base_name = "bitcoin-up-or-down"
        elif filename_string[:19] == "ethereum-up-or-down":
            base_name = "ethereum-up-or-down"
        elif filename_string[:17] == "solana-up-or-down":
            base_name = "solana-up-or-down"
        elif filename_string[:14] == "xrp-up-or-down":
            base_name = "xrp-up-or-down"
        elif filename_string[:13] == "btc-updown-5m":
            base_name = "btc-updown-5m"
        elif filename_string[:13] == "eth-updown-5m":
            base_name = "eth-updown-5m"
        else:
            print(f"Warning: Unrecognized market type in filename {filename}. This may indicate a problem with the dataset.")
            return False
        self.market = market_simulator(self.data_provider, starting_cash, base_name)
        self.data_provider.market = self.market
        self.bot.market = self.market
        self.bot.data_provider = self.data_provider
        try:
            self.eventMetadata = data["metadata_end"][0]["eventMetadata"]
        except (TypeError, KeyError, IndexError):
            print(f"Warning: No event metadata found in the dataset. This may indicate a problem with the dataset. File: {filename}")
            self.eventMetadata = None
            return False
        predictor = getattr(self.bot, "predictor", None)
        if predictor is None or predictor.__class__.__name__ == "nostradamus":
            self.bot.predictor = nostradamus(data)
            self.strategy_only_evaluation = True

        self.data_provider.set_end_timestamp(data["metadata_end"][0]["endDate"])
        self.data_provider.set_price_to_beat(data["metadata_end"][0]["eventMetadata"]["priceToBeat"])

        return True


    def evaluate_datapoint(self, data, filename, starting_cash=100):
        """
        Evaluates a single data point. (usually an hour in an hourly market or 5 mins in a 5 min market)
        """
        correctly_initialized = self.initialize_environment(starting_cash, data, filename)
        if not correctly_initialized:
            return None
        order_library_size = len(data["all_clobs"])
        binance_lookups_size = len(data["all_prices"])
        #print(f"Order library size: {order_library_size}, Binance lookups size: {binance_lookups_size}")
        outcomes = json.loads(data["metadata_end"][0]["markets"][0]["outcomes"])
        clobTokenIds = json.loads(data["metadata_end"][0]["markets"][0]["clobTokenIds"])
        if len(outcomes) != 2:
            print(f"Warning: More than 2 outcomes in the market. This may indicate a problem with the dataset. File: {filename}")
            return None
        asset_labels = {
            clobTokenIds[index]: outcomes[index]
            for index in range(min(len(outcomes), len(clobTokenIds)))
        }
        
        if self.eventMetadata is None or self.eventMetadata.get("priceToBeat") is None or self.eventMetadata.get("finalPrice") is None:
            print(f"Warning: Incomplete event metadata found in the dataset. This may indicate a problem with the dataset. File: {filename}")
            return None
        
        '''
        self.data_provider.set_order_book(data["all_clobs"][0])
        self.data_provider.set_crypto_value(data["all_prices"][0])
        self.bot.run()
        self.market.process_orders()
        print(f"User cash after processing: {self.data_provider.get_user_cash()}")
        print(f"User holdings after processing: {self.data_provider.get_user_holdings()}")
        print(f"Orders after processing: {self.data_provider.get_all_orders()}")
        print(f"Order book after processing: {self.data_provider.get_asset(self.data_provider.get_market_asset_ids()[0])}")
        '''
        mid_prices = {}
        crypto_prices = []
        holdings_history = []
        cash_history = []
        timestamps = []
        for i in range(len(data["all_prices"])):
            if data["all_prices"][i] is not None:
                data["all_prices"][i]["timestamp"] = int(data["all_prices"][i]["timestamp"] * 1000)

        for asset_id in clobTokenIds:
            mid_prices[asset_id] = []
        crypto_index = 0
        crypto_never_set = True
        for i in range(order_library_size):
            if i == 0:
                self.bot.first_run_setup()
            if data["all_clobs"][i] is None:
                print(f"Warning: Missing data at index {i}. Skipping this datapoint. File: {filename}")
                continue
            self.data_provider.set_order_book(data["all_clobs"][i])
            order_book_timestamp = None
            if data["all_clobs"][i][0][1] is not None:
                order_book_timestamp = data["all_clobs"][i][0][1]["timestamp"]
            if data["all_clobs"][i][1][1] is not None:
                if order_book_timestamp is not None:
                    order_book_timestamp = max(order_book_timestamp, data["all_clobs"][i][1][1]["timestamp"])
                else:
                    order_book_timestamp = data["all_clobs"][i][1][1]["timestamp"]
            if order_book_timestamp is None:
                print(f"Warning: Missing order book timestamp at index {i}. Skipping this datapoint. File: {filename}")
                continue
            while crypto_index < len(data["all_prices"]):
                
                if data["all_prices"][crypto_index] is None:
                    crypto_index += 1
                    continue

                crypto_value_timestamp = data["all_prices"][crypto_index]["timestamp"]
                
                if crypto_value_timestamp > int(order_book_timestamp):
                    break
                else:
                    crypto_prices.append(data["all_prices"][crypto_index])
                    self.data_provider.set_crypto_value(data["all_prices"][crypto_index])
                    crypto_never_set = False
                    crypto_index += 1
            
            if crypto_never_set:
                continue
            order_book = self.data_provider.get_order_book()
            skip = 0
            for asset in order_book:
                if asset[1] is None:
                    skip = 1
                    print(f"Warning: Missing asset data in order book at index {i}. Skipping this datapoint. File: {filename}")
                    break
            if skip:
                continue
            for j in range(len(data["all_clobs"][i])):
                self.market.set_min_order_size(data["all_clobs"][i][j][0], data["all_clobs"][i][j][1]["min_order_size"])

            asset_ids = self.data_provider.get_market_asset_ids()
            current_timestamp = self.data_provider.get_current_timestamp()
            for asset_id in asset_ids:
                mid_price = self.data_provider.get_mid_price(asset_id)
                if mid_price is not None:
                    mid_prices[asset_id].append({"mid_price": mid_price, "timestamp": current_timestamp})
                else:
                    print(f"Warning: Mid price is None for asset {asset_id} at index {i}. File: {filename}")

            self.bot.run()
            self.market.process_orders()
            current_timestamp = self.data_provider.get_current_timestamp()
            holdings_history.append(
                {
                    "timestamp": current_timestamp,
                    "holdings": {
                        asset_id: self.market.get_user_holdings().get(asset_id, 0)
                        for asset_id in asset_ids
                    },
                }
            )
            cash_history.append(
                {
                    "timestamp": current_timestamp,
                    "cash": self.market.get_user_cash(),
                }
            )
            timestamps.append(current_timestamp)

        resolution = self.market.resolve_market(self.eventMetadata,outcomes, clobTokenIds)
        analytics = {
            "transactions" : self.market.transactions,
            "order_placements": self.market.order_placements,
            "holdings_history": holdings_history,
            "cash_history": cash_history,
            "timestamps": timestamps,
            "asset_labels": asset_labels,
            "price_to_beat": self.eventMetadata.get("priceToBeat"),
            "final_cash" : self.data_provider.get_user_cash(),
            "resolution" : resolution,
            "mid_prices" : mid_prices,
            "crypto_prices" : crypto_prices,
            "past_crypto_predictions" : self.bot.past_crypto_predictions if hasattr(self.bot, 'past_crypto_predictions') else []
        }
        return analytics
    @staticmethod
    def get_analysis_path(gz_path):
        gz_path = Path(gz_path)

        return (
            Path("tmp")
            / gz_path.parent.name
            / f"{gz_path.stem}.analysis.json"
        )

    def evaluate_dataset(self, dataset_path: list[Path]):

        starting_cash = 100
        dataset_path = sort_paths_chronologically(dataset_path)
        for gz_file in dataset_path:
            with gzip.open(gz_file, "rt", encoding="utf-8") as f:
                data = json.load(f)
                analytics = self.evaluate_datapoint(data, gz_file, starting_cash)
                if analytics is not None:
                    #starting_cash = analytics["final_cash"]
                    analytics_path = self.get_analysis_path(gz_file)
                    analytics_path.parent.mkdir(parents=True, exist_ok=True)
                    analytics_path.write_text(json.dumps(analytics, indent=2, default=_json_default), encoding="utf-8")
                    print(f"Saved analytics to {analytics_path}, final cash: {analytics['final_cash']}")
                    #outcomes.append((round(analytics["final_cash"], 2), analytics_path))
                f.close()
        #for outcome, analytics_path in outcomes:
        #    print(f"Final cash outcome: {outcome}, analytics saved at: {analytics_path}")
        #print(f"Average final cash outcome for dataset {dataset_path}: {sum(cash for cash, _ in outcomes) / len(outcomes) if outcomes else 0}")


def load_bot(class_path: str) -> masterbot:
    """
    class_path example:
        bots.my_bot.MyBot
    """
    if class_path.endswith(".py"):
        bot_path = Path(class_path)
        if not bot_path.is_absolute():
            bot_path = Path.cwd() / bot_path

        try:
            module_name = bot_path.resolve().relative_to(REPO_ROOT).with_suffix("").as_posix().replace("/", ".")
        except ValueError:
            module_name = bot_path.stem

        spec = spec_from_file_location(module_name, bot_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load bot module from {class_path}")

        module = module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        bot_classes = [
            value
            for value in module.__dict__.values()
            if isinstance(value, type)
            and issubclass(value, masterbot)
            and value is not masterbot
        ]
        if not bot_classes:
            raise TypeError(f"No masterbot subclass found in {class_path}")
        if len(bot_classes) > 1:
            raise TypeError(f"Multiple masterbot subclasses found in {class_path}")

        cls = bot_classes[0]
    else:
        module_name, class_name = class_path.rsplit(".", 1)

        module = import_module(module_name)
        cls = getattr(module, class_name)

    if not issubclass(cls, masterbot):
        raise TypeError(f"{class_path} is not a subclass of MasterBot")

    return cls(False)


def main():
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "python evaluator.py bots.my_bot.MyBot datafile1 datafile 2 ..."
        )
        sys.exit(1)

    bot = load_bot(sys.argv[1])
    datafile_paths = sys.argv[2:]
    print(f"Loaded bot: {bot.__class__.__name__}")
    evaluator = replay_engine(bot, reset_bot_between_runs=False)
    evaluator.evaluate_dataset(datafile_paths)

if __name__ == "__main__":
    main()