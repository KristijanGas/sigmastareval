import sys
import gzip
import json
from pathlib import Path
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
import json


if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[1]

from bot.masterbot import masterbot
from market_simulator import market_simulator
from data_provider.historical_provider import historical_provider


class replay_engine:
    def __init__(self, bot: masterbot):
        self.bot = bot

    def initialize_environment(self, starting_cash, data):
        """
        Initializes the environment for the bot to run in.
        """
        self.data_provider = historical_provider()
        self.market = market_simulator(self.data_provider, starting_cash)
        self.data_provider.market = self.market
        self.bot.market = self.market
        self.bot.data_provider = self.data_provider
        self.eventMetadata = data["metadata_end"][0]["eventMetadata"]
        self.data_provider.set_price_to_beat(data["metadata_end"][0]["markets"][0]["priceToBeat"])


    def evaluate_datapoint(self, data):
        """
        Evaluates a single data point. (usually an hour in an hourly market or 5 mins in a 5 min market)
        """
        self.initialize_environment(100, data)
        order_library_size = len(data["all_clobs"])
        binance_lookups_size = len(data["all_prices"])
        print(f"Order library size: {order_library_size}, Binance lookups size: {binance_lookups_size}")
        if order_library_size != binance_lookups_size:
            print("Warning: Order library size and Binance lookups size do not match. This may indicate a problem with the dataset.")
            return None
        
        outcomes = json.loads(data["metadata_end"][0]["markets"][0]["outcomes"])
        if len(outcomes) != 2:
            print("Warning: More than 2 outcomes in the market. This may indicate a problem with the dataset.")
            return None
        
        if self.eventMetadata is None:
            print("Warning: No event metadata found in the dataset. This may indicate a problem with the dataset.")
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
        for i in range(order_library_size):
            self.data_provider.set_order_book(data["all_clobs"][i])
            self.data_provider.set_crypto_value(data["all_prices"][i])
            self.bot.run()
            self.market.process_orders()

        self.market.resolve_market(self.eventMetadata,outcomes)
        
        return self.market.get_user_cash()


    def evaluate_dataset(self, dataset_path: Path):

        outcomes = []

        for gz_file in dataset_path.rglob("*.gz"):
            with gzip.open(gz_file, "rt", encoding="utf-8") as f:
                data = json.load(f)

            final_cash = self.evaluate_datapoint(data)
            outcomes.append(final_cash)
        print(f"Final cash outcomes for dataset {dataset_path}: {outcomes}")

    def run(self, dataset_paths):
        for dataset_path in dataset_paths:
            print(f"Evaluating {dataset_path}")
            self.evaluate_dataset(Path(dataset_path))


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
            "python evaluator.py bots.my_bot.MyBot datasets/set1 datasets/set2 ..."
        )
        sys.exit(1)

    bot = load_bot(sys.argv[1])
    dataset_paths = sys.argv[2:]
    print(f"Loaded bot: {bot.__class__.__name__}")
    evaluator = replay_engine(bot)
    evaluator.run(dataset_paths)


if __name__ == "__main__":
    main()