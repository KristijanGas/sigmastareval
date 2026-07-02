import sys
import gzip
import json
from pathlib import Path
from importlib import import_module

from bot.masterbot import masterbot



class Evaluator:
    def __init__(self, bot: masterbot):
        self.bot = bot

    def evaluate_datapoint(self, data):
        """
        Evaluate a single dataset.
        Implement your evaluation logic here.
        """
        # Example:
        # self.bot.on_market(data)
        pass

    def evaluate_dataset(self, dataset_path: Path):
        for gz_file in dataset_path.rglob("*.gz"):
            with gzip.open(gz_file, "rt", encoding="utf-8") as f:
                data = json.load(f)

            self.evaluate_datapoint(data)

    def run(self, dataset_paths):
        for dataset_path in dataset_paths:
            print(f"Evaluating {dataset_path}")
            self.evaluate_dataset(Path(dataset_path))


def load_bot(class_path: str) -> masterbot:
    """
    class_path example:
        bots.my_bot.MyBot
    """
    module_name, class_name = class_path.rsplit(".", 1)

    module = import_module(module_name)
    cls = getattr(module, class_name)

    if not issubclass(cls, masterbot):
        raise TypeError(f"{class_path} is not a subclass of MasterBot")

    return cls()


def main():
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "python evaluator.py bots.my_bot.MyBot datasets/set1 datasets/set2 ..."
        )
        sys.exit(1)

    bot = load_bot(sys.argv[1])
    dataset_paths = sys.argv[2:]

    evaluator = Evaluator(bot)
    evaluator.run(dataset_paths)


if __name__ == "__main__":
    main()