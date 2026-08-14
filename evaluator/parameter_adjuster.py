from random import shuffle
import random
import sys
import json
from statistics import geometric_mean
import utils.utils
import replay_engine
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

#finds the best possible parameters that maximize ROI over all combinations of allowed parameters
def try_config(args):
    strategy_path, combination, files, step = args

    roi = calculate_roi(strategy_path, combination, files, step)

    return roi, combination

def calculate_roi(strategy_path, combination, files, step):
    bot = replay_engine.load_bot(strategy_path)
    engine = replay_engine.replay_engine(bot, reset_bot_between_runs=False, save_analytics=False, step_ms=step, custom_config=combination)
    outcomes = engine.evaluate_dataset(files)
    final_cash_list = [outcome[0] for outcome in outcomes]
    geometric_ROI = geometric_mean(final_cash_list) / 100.0 - 1.0
    return geometric_ROI

def load_cfg(config_file):
    with open(config_file, "r") as f:
        config_data = json.load(f)
    return config_data

def store_new_params(config_path, config_data):
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=4)

def mutate_cfg(current_config, parameters_metadata, count):
    mutations = []
    
    for i in range(count):
        mutation_count = random.randint(1, min(len(parameters_metadata), 4))
        mutation = current_config.copy()
        for _ in range(mutation_count):
            param_to_mutate = random.choice(list(parameters_metadata.keys()))
            param_info = parameters_metadata[param_to_mutate]
            current_value = mutation[param_to_mutate]
            current_value += param_info["step"] * random.choice([-1, 1])
            current_value = round(current_value, 6)
            current_value = min(current_value, param_info["max"])
            current_value = max(current_value, param_info["min"])
            mutation[param_to_mutate] = current_value
        mutations.append(mutation)

    print(mutations)
    return mutations

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
    config_data = load_cfg(config_file)
    best_roi = config_data.get("best_roi", -1.0)
    current_parameters = config_data.get("parameters", {})
    parameters_metadata = config_data.get("parameters_metadata", {})
    thread_count = 10
    step = 51
    should_store = True
    while True:
        combinations = mutate_cfg(current_parameters, parameters_metadata, thread_count)

        jobs = [
            (strategy_path, combination, files, step)
            for combination in combinations
        ]
        with ProcessPoolExecutor(max_workers=thread_count) as executor:
            try:
                futures = [
                    executor.submit(try_config, job)
                    for job in jobs
                ]

                for future in as_completed(futures):
                    geometric_ROI, combination = future.result()
                    print(geometric_ROI,best_roi)
                    if geometric_ROI > best_roi:
                        best_roi = geometric_ROI
                        current_parameters = combination
                        config_data["best_roi"] = best_roi
                        config_data["step_used"] = step
                        config_data["parameters"] = current_parameters
                        if should_store:
                            store_new_params(config_file, config_data)
                        print(f"New best ROI: {best_roi:.4%} with parameters:")
                        for param, value in combination.items():
                            print(f"  \"{param}\": {value},")
            except KeyboardInterrupt:
                print("Terminating all parameter adjustment processes...")
                executor.shutdown(wait=False, cancel_futures=True)
                print("All parameter adjustment processes terminated.")
                return

if __name__ == "__main__":
    main()
#python evaluator/parameter_adjuster.py bot/k_strategy.py bot/configs/KStrategy/bitcoin-up-or-down.cfg datasets/bitcoin-up-or-down august-3-2026-12pm-et