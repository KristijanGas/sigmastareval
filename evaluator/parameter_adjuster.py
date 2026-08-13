from random import shuffle
import sys
import json
from statistics import geometric_mean
from matplotlib.pyplot import step
import utils.utils
import replay_engine
from pathlib import Path


#finds the best possible parameters that maximize ROI over all combinations of allowed parameters

def build_combinations(config_file):
    all_combinations = [{}]
    with open(config_file, "r") as f:
        config = json.load(f)
        config_metadata = config.get("parameters_metadata", {})

        for param, values in config_metadata.items():
            min_value = values["min"]
            max_value = values["max"]
            step = values["step"]

            new_combinations = []

            current_value = min_value
            print((max_value - min_value) / step, param)
            while current_value <= max_value:
                for combination in all_combinations:
                    new_combination = combination.copy()
                    new_combination[param] = current_value
                    new_combinations.append(new_combination)

                current_value += step

            all_combinations = new_combinations
    if len(all_combinations) == 0:
        print("No parameter combinations found. Please check the config file.")
        sys.exit(1)
    print(len(all_combinations), "parameter combinations found.")
    if len(all_combinations) > 2000:
        print(f"Too many parameter combinations found. Please refine the config file. {len(all_combinations)}, max 2000")
        sys.exit(1)
    return all_combinations

def build_files(dataset_path, from_optional):
    files = []

    for data_file in Path(dataset_path).glob("*.gz"):
        file = data_file.resolve()
        if not utils.utils.is_newer_than(file, from_optional):
            #print(f"  Skipping {gz_file} (too old)")
            continue
        print(f"Found data file: {data_file}")
        files.append(file)
    return files

def main():
    if len(sys.argv) < 5:
        print("Usage: python parameter_adjuster.py <path_to_strategy> <path_to_config> <dataset_path> <from_optional>")
        sys.exit(1)

    strategy_path = sys.argv[1]
    config_file = sys.argv[2]
    dataset_path = sys.argv[3]
    from_optional = "august-5-2000-9am-et"
    if len(sys.argv) > 4:
        from_optional = sys.argv[4]

    files = build_files(dataset_path, from_optional)
    combinations = build_combinations(config_file)
    shuffle(combinations)
    best_roi = -1.0
    for combination in combinations:
        bot = replay_engine.load_bot(strategy_path)
        engine = replay_engine.replay_engine(bot, reset_bot_between_runs=False, save_analytics=False, step_ms=126, custom_config=combination)
        outcomes = engine.evaluate_dataset(files)
        final_cash_list = [outcome[0] for outcome in outcomes]
        geometric_ROI = geometric_mean(final_cash_list) / 100.0 - 1.0
        if geometric_ROI > best_roi:
            best_roi = geometric_ROI
            print(f"New best ROI: {best_roi:.4%} with parameters:")
            for param, value in combination.items():
                print(f"  \"{param}\": {value},")



if __name__ == "__main__":
    main()