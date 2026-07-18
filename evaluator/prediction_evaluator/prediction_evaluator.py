
#from predictors import MultiWindowMomentumPredictor, RegressionMomentumPredictor, MultiWindowRegressionPredictor

from prediction_eval_dataclasses import MarketSnapshot, PredictionObservation, MarketAssets
from future_target_matcher import FutureTargetMatcher
from snapshot_builder import SnapshotBuilder
from typing import Any
from datetime import datetime
from pathlib import Path
import json
import sys
import gzip

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[2]

from bot.prediction_models.linear_predictor import LinearPredictor
from bot.prediction_models.multi_window_linear_predictor import MultiWindowLinearPredictor
from bot.prediction_models.linear_regression_predictor import LinearRegressionPredictor
from bot.prediction_models.multi_window_regression_predictor import MultiWindowRegressionPredictor

class PredictionEvaluator:
    def __init__(self, predictor, target_matcher: FutureTargetMatcher):
        self.predictor = predictor
        self.target_matcher = target_matcher

    def evaluate_market(self, snapshots: list[MarketSnapshot]):
        self.predictor.reset()
        self.target_matcher.reset()

        observations: list[PredictionObservation] = []

        for snapshot in snapshots:
            resolved = self.target_matcher.process_snapshot(snapshot)

            observations.extend(resolved)

            prediction = self.predictor.update(snapshot) #creates a new prediction using only data available up to this snapshot
            if prediction is not None:
                self.target_matcher.add_prediction(prediction)

        return observations






def extract_price_to_beat(metadata_end: list[dict[str, Any]]):
    if not metadata_end:
        print("metadata_end doesn't exist")
        return None

    event = metadata_end[0]
    event_metadata = event.get("eventMetadata")

    value = event_metadata.get("priceToBeat")

    if value is None:
        return None
    
    return float(value)


def parse_json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed


def extract_market_assets(metadata_start: list[dict[str, Any]], market_index: int = 0):
    if not metadata_start:
        raise ValueError("metadata_start is empty")
    
    event = metadata_start[0]
    markets = event.get("markets")
    market = markets[market_index]
    outcomes = parse_json_list(market.get("outcomes"))
    token_ids = parse_json_list(market.get("clobTokenIds"))

    outcome_to_token = {
        str(outcome).strip().lower(): str(token_id)
        for outcome, token_id in zip(outcomes, token_ids)
    }

    up_asset_id = outcome_to_token["up"]
    down_asset_id = outcome_to_token["down"]

    return MarketAssets(
        up_asset_id=up_asset_id,
        down_asset_id=down_asset_id,
    )


#OBAVEZNO PROVJERITI PRIJE JE LI DAJE DOBAR TIMESTAMP
def iso_to_timestamp_ms(value: str):
    dt = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    return round(dt.timestamp() * 1000)


# will move to separate metrics file later - here while testing
def mae(observations: list[PredictionObservation]):
    if not observations:
        return None
    
    errors = []
    for observation in observations:
        if observation.actual_midpoint is None or observation.predicted_midpoint is None:
            continue
        errors.append(abs(observation.actual_midpoint - observation.predicted_midpoint))

    return(sum(errors) / len(observations))


import matplotlib.pyplot as plt


def plot_prediction_observations(observations):
    if not observations:
        raise ValueError("observations cannot be empty")

    # Sort chronologically in case the input list is unordered
    observations = sorted(
        observations,
        key=lambda observation: observation.actual_timestamp
    )

    timestamps = [
        datetime.fromtimestamp(
            observation.actual_timestamp / 1000
        )
        for observation in observations
    ]

    predicted = [
        observation.predicted_midpoint
        for observation in observations
    ]

    actual = [
        observation.actual_midpoint
        for observation in observations
    ]

    fig, ax = plt.subplots(figsize=(11, 5))

    ax.plot(
        timestamps,
        predicted,
        label="Predicted midpoint",
        linewidth=2
    )

    ax.plot(
        timestamps,
        actual,
        label="Actual midpoint",
        linewidth=2
    )

    ax.set_title("Predicted vs Actual Midpoints")
    ax.set_xlabel("Actual timestamp")
    ax.set_ylabel("Midpoint")
    ax.set_ylim(0, 1)

    ax.grid(alpha=0.3)
    ax.legend()

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()


def plot_prediction_accuracy(observations):
    valid = [
        observation
        for observation in observations
        if (
            observation.predicted_midpoint is not None
            and observation.actual_midpoint is not None
        )
    ]

    predicted = [
        observation.predicted_midpoint
        for observation in valid
    ]

    actual = [
        observation.actual_midpoint
        for observation in valid
    ]

    fig, ax = plt.subplots(figsize=(6, 6))

    ax.scatter(predicted, actual, alpha=0.6)
    ax.plot([0, 1], [0, 1], linestyle="--", label="Perfect prediction")

    ax.set_title("Prediction Accuracy")
    ax.set_xlabel("Predicted midpoint")
    ax.set_ylabel("Actual midpoint")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend()

    plt.tight_layout()
    plt.show()

def prepare_market_snapshots(data):
    metadata_start = data["metadata_start"]
    all_clobs = data["all_clobs"]
    all_prices = data["all_prices"]
    metadata_end = data["metadata_end"]
    assets = extract_market_assets(metadata_start)

    event = metadata_start[0]
    markets = event.get("markets")
    market = markets[0]

    market_end_timestamp = iso_to_timestamp_ms(market.get("endDate"))
    price_to_beat = extract_price_to_beat(metadata_end)

    builder = SnapshotBuilder(
        up_asset_id=assets.up_asset_id,
        down_asset_id=assets.down_asset_id,
        market_end_timestamp=market_end_timestamp,
        price_to_beat=price_to_beat,
    )

    return builder.build(raw_clobs=all_clobs, raw_prices=all_prices)


def generate_test_and_train_data(dataset_paths):
    train_snapshots = []
    test_paths = []
    count = 0
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            if count % 2 == 0:
                test_paths.append(data_file)
                count += 1
            else:
                file = data_file.resolve()
                with gzip.open(file, "rt", encoding="utf-8") as f:
                    data = json.load(f)
                    market_snapshots = prepare_market_snapshots(data)
                    train_snapshots.append(market_snapshots)
                    count += 1
    return test_paths, train_snapshots

def start_training_and_evaluation(training_dataset, test_paths):
    for data_file in test_paths:
        print(f"Found data file: {data_file}")
        file = data_file.resolve()
        with gzip.open(file, "rt", encoding="utf-8") as f:
            data = json.load(f)

            #predictor = LinearPredictor()
            predictor = MultiWindowRegressionPredictor(training_dataset)
            target_matcher = FutureTargetMatcher()
            evaluator = PredictionEvaluator(
                predictor=predictor,
                target_matcher=target_matcher
            )
            market_snapshots = prepare_market_snapshots(data)

            observations = evaluator.evaluate_market(market_snapshots)

            print("Observations:", len(observations))
            print("MAE:", mae(observations))

            # for i in range(5):
            #     observation = observations[i]
            #     print(
            #         f"Prediction at {observation.prediction_timestamp}: "
            #         f"current={observation.current_midpoint:.4f}, "
            #         f"predicted={observation.predicted_midpoint:.4f}, "
            #         f"actual={observation.actual_midpoint:.4f}, "
            #         f"actual timestamp={observation.actual_timestamp}, "
            #     )
    plot_prediction_observations(observations)
    plot_prediction_accuracy(observations)


def start_evaluation(dataset_paths):
    files = []
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            print(f"Found data file: {data_file}")
            file = data_file.resolve()
            with gzip.open(file, "rt", encoding="utf-8") as f:
                data = json.load(f)

                predictor = LinearPredictor()
                target_matcher = FutureTargetMatcher()
                evaluator = PredictionEvaluator(
                    predictor=predictor,
                    target_matcher=target_matcher
                )
                market_snapshots = prepare_market_snapshots(data)

                observations = evaluator.evaluate_market(market_snapshots)

                print("Observations:", len(observations))
                print("MAE:", mae(observations))


                # for i in range(5):
                #     observation = observations[i]
                #     print(
                #         f"Prediction at {observation.prediction_timestamp}: "
                #         f"current={observation.current_midpoint:.4f}, "
                #         f"predicted={observation.predicted_midpoint:.4f}, "
                #         f"actual={observation.actual_midpoint:.4f}, "
                #         f"actual timestamp={observation.actual_timestamp}, "
                #     )
        plot_prediction_observations(observations)
        plot_prediction_accuracy(observations)


def main():

    predictor_path = sys.argv[1]
    dataset_paths = sys.argv[2:]

    training_required = True

    if training_required:
        test_paths, train_data = generate_test_and_train_data(dataset_paths)
        start_training_and_evaluation(training_dataset=train_data, test_paths=test_paths)
    else:
        start_evaluation(dataset_paths=dataset_paths)

    


main()