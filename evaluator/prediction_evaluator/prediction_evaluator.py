
#from predictors import MultiWindowMomentumPredictor, RegressionMomentumPredictor, MultiWindowRegressionPredictor
import gc
from importlib.metadata import files
from pathlib import Path
import json
import sys
import gzip
import time
import joblib




if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    
REPO_ROOT = Path(__file__).resolve().parents[2]
from collections import deque
from dataclasses import dataclass

from typing import Any, Iterable, Sequence
from datetime import datetime

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from evaluator.utils.utils import extract_timestamp, sort_paths_chronologically

from evaluator.prediction_evaluator.future_target_matcher import FutureTargetMatcher
from evaluator.prediction_evaluator.snapshot_builder import SnapshotBuilder

from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot, PredictionObservation, MarketAssets

# bot.prediction_models.linear_predictor import LinearPredictor
#from bot.prediction_models.multi_window_linear_predictor import MultiWindowLinearPredictor
# bot.prediction_models.linear_regression_predictor import LinearRegressionPredictor
#from bot.prediction_models.multi_window_regression_predictor import MultiWindowRegressionPredictor
from bot.prediction_models.gradient_boosting_predictor import GradientBoostingPredictor
from evaluator.prediction_evaluator.feature_extractor import MarketFeatureExtractor

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

            prediction = self.predictor.update_and_predict(snapshot) #creates a new prediction using only data available up to this snapshot
            if prediction is not None:
                self.target_matcher.add_prediction(prediction)

        return observations






def extract_price_to_beat(metadata_end: list[dict[str, Any]]):
    if not metadata_end:
        print("metadata_end doesn't exist")
        return None

    event = metadata_end[0]
    event_metadata = event.get("eventMetadata")
    if event_metadata is None:
        return None
    
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
        if observation.actual_value is None or observation.predicted_value is None:
            continue
        errors.append(abs(observation.actual_value - observation.predicted_value))

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
        observation.predicted_value
        for observation in observations
    ]

    actual = [
        observation.actual_value
        for observation in observations
    ]

    fig, ax = plt.subplots(figsize=(11, 5))

    ax.plot(
        timestamps,
        predicted,
        label="Predicted value",
        linewidth=2
    )

    ax.plot(
        timestamps,
        actual,
        label="Actual value",
        linewidth=2
    )

    ax.set_title("Predicted vs Actual Values")
    ax.set_xlabel("Actual timestamp")
    ax.set_ylabel("Value") #make dynamic names
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
            observation.predicted_value is not None
            and observation.actual_value is not None
        )
    ]

    predicted = [
        observation.predicted_value
        for observation in valid
    ]

    actual = [
        observation.actual_value
        for observation in valid
    ]

    fig, ax = plt.subplots(figsize=(6, 6))

    ax.scatter(predicted, actual, alpha=0.6)
    ax.plot([0, 1], [0, 1], linestyle="--", label="Perfect prediction")

    ax.set_title("Prediction Accuracy")
    ax.set_xlabel("Predicted value")
    ax.set_ylabel("Actual value")
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

@dataclass
class PendingTrainingRow:
    prediction_timestamp: int
    current_value: float
    feature_values: tuple[float, ...]

def create_training_samples_trend(
    snapshots: Sequence[MarketSnapshot],
    feature_extractor: MarketFeatureExtractor,
    feature_names: Sequence[str],
    horizon_ms: int,
    max_target_delay_ms: int | None = None,
    sample_interval_ms: int | None = 5000,  #space between two training samples
) -> tuple[np.ndarray, np.ndarray]:
    feature_names = tuple(feature_names)
    feature_extractor.reset()
    pending: deque[PendingTrainingRow] = deque()

    X_rows: list[tuple[float, ...]] = []
    y_values: list[float] = []

    last_training_sample_timestamp = None

    for snapshot in snapshots:
        
        current_crypto_price = snapshot.crypto_price
        if current_crypto_price is None:
            continue

        # Resolve previous feature rows whose targets have arrived
        while pending:
            oldest = pending[0]

            requested_target_timestamp = oldest.prediction_timestamp + horizon_ms
            if snapshot.timestamp < requested_target_timestamp:
                break

            pending.popleft()

            target_delay_ms = snapshot.timestamp - requested_target_timestamp

            if (max_target_delay_ms is not None
                and target_delay_ms > max_target_delay_ms):
                continue

            #actual value
            future_change = current_crypto_price - oldest.current_value
            
            X_rows.append(oldest.feature_values)
            y_values.append(future_change)

        extracted = feature_extractor.update_and_extract(snapshot)

        if extracted is None:
            continue

        if not extracted.features.has_all(feature_names):
            continue

        # skipping timestamps that are two close to each other to reduce
        #  many dependent rows
        if (sample_interval_ms is not None
            and last_training_sample_timestamp is not None
            and extracted.timestamp - last_training_sample_timestamp
            < sample_interval_ms):
            continue

        pending.append(
            PendingTrainingRow(
                prediction_timestamp=extracted.timestamp,
                current_value=extracted.current_crypto_price,
                feature_values=extracted.features.select_values(feature_names),
            )
        )
        last_training_sample_timestamp = extracted.timestamp

    feature_count = len(feature_names)

    if not X_rows:
        return (
            np.empty(shape=(0, feature_count), dtype=float,),
            np.empty(shape=(0,), dtype=float,),
        )

    return (
        np.asarray(X_rows, dtype=float),
        np.asarray(y_values, dtype=float),
    )


def create_training_samples(
    snapshots: Sequence[MarketSnapshot],
    feature_extractor: MarketFeatureExtractor,
    feature_names: Sequence[str],
    horizon_ms: int,
    max_target_delay_ms: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    feature_names = tuple(feature_names)
    feature_extractor.reset()
    pending: deque[PendingTrainingRow] = deque()

    X_rows: list[tuple[float, ...]] = []
    y_values: list[float] = []

    for index, snapshot in enumerate(snapshots):
        type(snapshot)
        if not isinstance(snapshot, MarketSnapshot):
            print(index)
            print(len(snapshot))
            print(type(snapshot).__name__)
            # raise TypeError(
            #     f"Expected MarketSnapshot at index {index}, "
            #     f"got {type(snapshot).__name__}: "
            #     f"{snapshot!r}"
            # )
        
        current_midpoint = snapshot.up_book.midpoint

        if current_midpoint is None:
            continue

        # Resolve previous feature rows whose targets have arrived
        while pending:
            oldest = pending[0]

            requested_target_timestamp = oldest.prediction_timestamp + horizon_ms
            if snapshot.timestamp < requested_target_timestamp:
                break

            pending.popleft()

            target_delay_ms = snapshot.timestamp - requested_target_timestamp

            if (max_target_delay_ms is not None
                and target_delay_ms > max_target_delay_ms):
                continue

            #actual value
            future_change = current_midpoint - oldest.current_value

            X_rows.append(oldest.feature_values)
            y_values.append(future_change)

        extracted = feature_extractor.update_and_extract(snapshot)

        if extracted is None:
            continue
        else:
            print(extracted)

        if not extracted.features.has_all(feature_names):
            continue

        pending.append(
            PendingTrainingRow(
                prediction_timestamp=extracted.timestamp,
                current_value=extracted.current_midpoint,
                feature_values=extracted.features.select_values(feature_names),
            )
        )

    feature_count = len(feature_names)

    if not X_rows:
        return (
            np.empty(shape=(0, feature_count), dtype=float,),
            np.empty(shape=(0,), dtype=float,),
        )

    return (
        np.asarray(X_rows, dtype=float),
        np.asarray(y_values, dtype=float),
    )

def create_training_dataset(
    markets: Sequence[Sequence[MarketSnapshot]],
    feature_extractor,
    feature_names: Sequence[str],
    horizon_ms: int,
    max_target_delay_ms: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    X_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []

    for snapshots in markets:
        extractor = feature_extractor

        # X_market, y_market = create_training_samples(
        #     snapshots=snapshots,
        #     feature_extractor=extractor,
        #     feature_names=feature_names,
        #     horizon_ms=horizon_ms,
        #     max_target_delay_ms=max_target_delay_ms
        # )

        X_market, y_market = create_training_samples_trend(
            snapshots=snapshots,
            feature_extractor=extractor,
            feature_names=feature_names,
            horizon_ms=horizon_ms,
            max_target_delay_ms=max_target_delay_ms
        )

        if len(X_market) == 0:
            continue
            
        X_parts.append(X_market)
        y_parts.append(y_market)
        print("samples ready")

    if not X_parts:
        raise ValueError("No valid training samples were created.")

    return (np.concatenate(X_parts, axis=0), np.concatenate(y_parts, axis=0))

def generate_test_and_train_data(dataset_paths):
    train_snapshots = []
    test_paths = []
    length = 0.0
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            length += 1
    
    count = 0.0
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            if count/length >= 0.2:
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


# creates snapshots and training samples for one market at a time
#   optimized memory usage
def prepare_training_data(
    train_paths: Sequence[Path],
    feature_extractor: MarketFeatureExtractor,
    feature_names: Sequence[str],
    horizon_ms: int,
    max_target_delay_ms: int | None = None,
    sample_interval_ms: int | None = 5000,
) -> tuple[np.ndarray, np.ndarray]:
    X_markets: list[np.ndarray] = []
    y_markets: list[np.ndarray] = []

    total_samples = 0

    for data_file in train_paths:
        try:
            file = data_file.resolve()
            with gzip.open(file, "rt", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as error:
            print(
                f"Skipping {data_file.name}: "
                f"invalid JSON at position {error.pos}: "
                f"{error.msg}"
            )
            continue

        market_snapshots = prepare_market_snapshots(data)
        del data

        X_market, y_market = create_training_samples_trend(
            snapshots=market_snapshots,
            feature_extractor=feature_extractor,
            feature_names=feature_names,
            horizon_ms=horizon_ms,
            max_target_delay_ms=max_target_delay_ms
        )

        del market_snapshots

        if len(X_market) > 0: 
            X_markets.append(np.asarray(X_market, dtype=np.float32))
            y_markets.append(np.asarray(y_market, dtype=np.float32))
            total_samples += len(y_market)

        print(
            f"{data_file.name}: "
            f"{len(y_market):,} samples, "
            f"{total_samples:,} total"
        )
        
        gc.collect()
        print(f"done: {data_file.name}")

    if not X_markets:
        return (np.empty((0, len(feature_names)),dtype=np.float32,),
            np.empty((0,), dtype=np.float32))

    X_train = np.concatenate(X_markets, axis=0)
    y_train = np.concatenate(y_markets, axis=0)

    return X_train, y_train

def get_test_paths(dataset_paths):
    test_paths = []
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            test_paths.append(data_file)
            
    return test_paths

def get_train_paths(dataset_paths):
    train_paths = []
    days = 5
    older_than_time = days * 24 * 60 * 60  # 10 days in
    newer_than_timestamp = 1783286309.0 # 5.7.2026.
    
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            #print(f"Found data file: {data_file}")
            #print(data_file.name)
            
            file_creation_date = extract_timestamp(filename=data_file.name)
            if file_creation_date < 1785365568.3137162 - older_than_time and file_creation_date > newer_than_timestamp:
                train_paths.append(data_file)
                #print(f"Added data file: {data_file}")
    return train_paths

def get_new_test_paths(dataset_paths):
    test_paths = []
    days = 3
    newer_than_time = days * 24 * 60 * 60  # 10 days in seconds
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            #print(f"Found data file: {data_file}")
            
            file_creation_date = extract_timestamp(filename=data_file.name)
            if newer_than_time is not None and file_creation_date > 1785365568.3137162 - newer_than_time:
                test_paths.append(data_file)
                #print(f"Added data file: {data_file}")
    return test_paths

def prepare_train_snapshots(train_paths):
    train_snapshots = []
    for data_file in train_paths:
        file = data_file.resolve()
        with gzip.open(file, "rt", encoding="utf-8") as f:
            data = json.load(f)
            market_snapshots = prepare_market_snapshots(data)
            train_snapshots.append(market_snapshots)
        del market_snapshots
        del data
        gc.collect()

    return train_snapshots

def start_evaluation(predictor, test_paths):
    for data_file in test_paths:
        print(f"Found data file: {data_file}")
        file = data_file.resolve()
        with gzip.open(file, "rt", encoding="utf-8") as f:
            data = json.load(f)

            target_matcher = FutureTargetMatcher()
            evaluator = PredictionEvaluator(
                predictor=predictor,
                target_matcher=target_matcher
            )
            market_snapshots = prepare_market_snapshots(data)

            observations = evaluator.evaluate_market(market_snapshots)

            print("Observations:", len(observations))
            print("MAE:", mae(observations))

            for i in range(5):
                observation = observations[i]
                print(
                    f"Prediction at {observation.prediction_timestamp}: "
                    #f"current={observation.current_value:.4f}, "
                    f"predicted={observation.predicted_value:.4f}, "
                    f"actual={observation.actual_value:.4f}, "
                    f"actual timestamp={observation.actual_timestamp}, "
                )
    plot_prediction_observations(observations)
    plot_prediction_accuracy(observations)


def main():
    print("start")
    # GRADIENT_BOOSTING_FEATURES = (
    #     "current_midpoint",

    #     "midpoint_momentum_3000",
    #     "midpoint_momentum_8000",
    #     "midpoint_momentum_18000",

    #     "spread",

    #     "imbalance_top_1",
    #     "imbalance_top_3",
    #     "imbalance_top_5",

    #     "bid_volume_top_5",
    #     "ask_volume_top_5",

    #     "binance_return_3000",
    #     "binance_return_10000",
    #     "binance_return_30000",

    #     "relative_distance_to_price_to_beat",
    #     "seconds_remaining",
    # )

    GRADIENT_BOOSTING_FEATURES = (
        "binance_return_1000",
        "binance_return_3000",
        #"binance_range_position_5000",
        #"binance_range_position_15000",
        #"binance_range_position_30000",
        #"binance_return_volatility_10000",
        #"binance_return_volatility_20000",
        #"binance_relative_high_distance_5000",
        #"binance_relative_low_distance_5000",
        #"binance_range_position_7000"
        #"binance_return_3500",
        #"binance_acceleration_1s_5s",
    )  

    predictor_path = sys.argv[1]
    dataset_paths = sys.argv[2:]

    training_required = True

    if training_required:
        #test_paths, train_snapshots = generate_test_and_train_data(dataset_paths)
        train_paths = get_train_paths(dataset_paths=dataset_paths)
        train_paths = sort_paths_chronologically(train_paths)
        #print(train_paths)
        #train_snapshots = prepare_train_snapshots(train_paths=train_paths)
        #print("snapshots done")

        test_paths = get_new_test_paths(dataset_paths=dataset_paths)
        test_paths = sort_paths_chronologically(test_paths)
        #print(test_paths)

        #training_samples = None
        training_samples = prepare_training_data(
            train_paths=train_paths,
            feature_extractor=MarketFeatureExtractor(binance_lookbacks_ms=(1000,3000,5000),
                                                     crypto_range_windows_ms=(5000,15000, 30000)),
            #feature_extractor=MarketFeatureExtractor(),
            feature_names=GRADIENT_BOOSTING_FEATURES,
            horizon_ms=3000,
            max_target_delay_ms=1000,
        )

        # training_samples = create_training_dataset(
        #     markets=train_snapshots,
        #     feature_extractor=MarketFeatureExtractor(binance_lookbacks_ms=(1000,3000,5000),
        #                                              crypto_range_windows_ms=(5000,15000, 30000)),
        #     #feature_extractor=MarketFeatureExtractor(),
        #     feature_names=GRADIENT_BOOSTING_FEATURES,
        #     horizon_ms=3000,
        #     max_target_delay_ms=1000,
        # )
        #model = joblib.load("bot/trained_models/trend_model_btc2.joblib")
        #model = joblib.load("bot/trained_models/trend_model_btc.joblib")
        predictor = GradientBoostingPredictor(
            model=None,
            feature_extractor=MarketFeatureExtractor(binance_lookbacks_ms=(1000,3000,5000),
                                                     crypto_range_windows_ms=(5000,15000,30000)),
            #feature_extractor=MarketFeatureExtractor(),
            horizon_ms=3000,
            #target_name="midpoint_change",
            target_name="normalized_crypto_trend",
            gradient_boosting_features=GRADIENT_BOOSTING_FEATURES,
            training_samples=training_samples,
            market_name="ethereum-up-or-down",
        )
        joblib.dump(predictor.model, "bot/trained_models/trend_model_eth_2.joblib")
        start_evaluation(predictor, test_paths=test_paths)
    else:
        test_paths=get_test_paths(dataset_paths=dataset_paths)
        start_evaluation(predictor=None, test_paths=test_paths)

    

if __name__ == "__main__":
    main()