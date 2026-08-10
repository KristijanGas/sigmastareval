
import gc
from importlib.metadata import files
from pathlib import Path
import json
import sys
import gzip
import time
import zlib
import joblib
import ast
import math
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score




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
from evaluator.utils.utils import extract_market_date, extract_timestamp, sort_paths_chronologically

from evaluator.prediction_evaluator.future_target_matcher import FutureTargetMatcher
from evaluator.prediction_evaluator.snapshot_builder import SnapshotBuilder
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketMetadata, MarketSnapshot, PredictionObservation, MarketAssets

# bot.prediction_models.linear_predictor import LinearPredictor
#from bot.prediction_models.multi_window_linear_predictor import MultiWindowLinearPredictor
# bot.prediction_models.linear_regression_predictor import LinearRegressionPredictor
#from bot.prediction_models.multi_window_regression_predictor import MultiWindowRegressionPredictor
from bot.prediction_models.gradient_boosting_predictor import GradientBoostingPredictor
from evaluator.prediction_evaluator.feature_extractor import MarketFeatureExtractor
from evaluator.prediction_evaluator.training_targets import CRYPTO_CHANGE_TARGET, OUTCOME_PROBABILITY_TARGET, PendingTrainingRow, TrainingTarget

class PredictionEvaluator:
    def __init__(self, predictor, target_matcher: FutureTargetMatcher):
        self.predictor = predictor
        self.target_matcher = target_matcher

    def evaluate_market(self, snapshots: list[MarketSnapshot], observation_interval_ms=0):
        self.predictor.reset()
        self.target_matcher.reset()

        observations: list[PredictionObservation] = []

        last_training_sample_timestamp = None

        for snapshot in snapshots:
            resolved = self.target_matcher.process_snapshot(snapshot)

            observations.extend(resolved)

            prediction = self.predictor.update_and_predict(snapshot) #creates a new prediction using only data available up to this snapshot

            if (observation_interval_ms is not None
                and last_training_sample_timestamp is not None
                and snapshot.timestamp - last_training_sample_timestamp
                < observation_interval_ms):
                continue

            if prediction is not None:
                self.target_matcher.add_prediction(prediction)

            last_training_sample_timestamp = snapshot.timestamp

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

def extract_final_price(metadata_end: list[dict[str,Any]]):
    if not metadata_end:
        return None
    event = metadata_end[0]
    event_metadata = event.get("eventMetadata")
    if not isinstance(event_metadata, dict):
        return None
    value = event_metadata.get("finalPrice")
    if value is None:
        return None
    
    #print(value)
    return float(value)

def get_resolved_outcome(metadata_end):
    price_to_beat = extract_price_to_beat(metadata_end)
    final_price = extract_final_price(metadata_end)

    if price_to_beat is None or final_price is None:
        event = metadata_end[0]
        markets = event.get("markets")
        market = markets[0]
        outcome_prices_string = market.get("outcomePrices")    
        outcome_prices = ast.literal_eval(outcome_prices_string)
        if outcome_prices:  # outcomePrices is sometimes ["0.001", "0.999"], but finalPrice missing
            #print(outcome_prices)
            #print(outcome_prices[0])
            up_price = float(outcome_prices[0])
            if up_price < 0.005:
                return "DOWN"
            elif up_price > 0.995:
                return "UP"
        return None
    if final_price >= price_to_beat:
        return "UP"
    else:
        return "DOWN"


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

# mathematically same as MSE
def brier_score(observations: list[PredictionObservation]):
    if not observations:
        return None
    
    errors = []
    for observation in observations:
        if observation.actual_value is None or observation.predicted_value is None:
            continue
        errors.append(math.pow((observation.actual_value - observation.predicted_value),2))

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
        #observation.actual_value
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
    ax.set_ylabel("Value")
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


# Generic function for creating training samples for any numerical target
def create_training_samples(
    snapshots: Sequence[MarketSnapshot],
    feature_extractor: MarketFeatureExtractor,
    feature_names: Sequence[str],
    horizon_ms: int,
    target: TrainingTarget,
    max_target_delay_ms: int | None = None,
    sample_interval_ms: int | None = 5000,  #minimum space between two training samples
    market_metadata: MarketMetadata | None = None,
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

            actual_target = target.create_target(oldest.target_context, snapshot, market_metadata)
            if actual_target is None:
                continue
           #print(actual_target)

            if not np.isfinite(actual_target):
                continue

            
            X_rows.append(oldest.feature_values)
            y_values.append(float(actual_target))

        extracted = feature_extractor.update_and_extract(snapshot)
        #print(extracted)

        if extracted is None:
            continue
        #print(extracted.current_crypto_price)
        #print(extracted)

        if not extracted.features.has_all(feature_names):
            continue

        # skipping timestamps that are two close to each other to reduce
        #  many dependent rows
        if (sample_interval_ms is not None
            and last_training_sample_timestamp is not None
            and extracted.timestamp - last_training_sample_timestamp
            < sample_interval_ms):
            continue

        target_context = target.create_context(extracted, snapshot)
        if target_context is None:
            continue

        feature_values = extracted.features.select_values(feature_names)
        pending.append(
            PendingTrainingRow(
                prediction_timestamp=extracted.timestamp,
                target_context=target_context,
                feature_values=feature_values,
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




# creates snapshots and training samples for one market at a time
#   optimized memory usage
def prepare_training_data(
    train_paths: Sequence[Path],
    feature_extractor: MarketFeatureExtractor,
    feature_names: Sequence[str],
    horizon_ms: int,
    target: TrainingTarget,
    max_target_delay_ms: int | None = None,
    sample_interval_ms: int | None = 5000,
) -> tuple[np.ndarray, np.ndarray]:
    X_markets: list[np.ndarray] = []
    y_markets: list[np.ndarray] = []

    total_samples = 0
    markets_tested = 0
    resolved_up = 0

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
        except (gzip.BadGzipFile, zlib.error, EOFError) as e:
            print(f"Could not decompress {file}: {e}. Skipping the file.")
            continue

        market_snapshots = prepare_market_snapshots(data)
        #print(len(market_snapshots))

        metadata_start = data["metadata_start"]
        metadata_end = data["metadata_end"]
        metadata = extract_market_metadata(metadata_start=metadata_start, metadata_end=metadata_end)
        #print(metadata)
        del data

        X_market, y_market = create_training_samples(
            snapshots=market_snapshots,
            feature_extractor=feature_extractor,
            feature_names=feature_names,
            horizon_ms=horizon_ms,
            max_target_delay_ms=max_target_delay_ms,
            target=target,
            sample_interval_ms=sample_interval_ms,
            market_metadata=metadata,
        )

        del market_snapshots

        if len(X_market) > 0: 
            X_markets.append(np.asarray(X_market, dtype=np.float32))
            y_markets.append(np.asarray(y_market, dtype=np.float32))
            total_samples += len(y_market)
            markets_tested += 1
            if metadata.resolved_outcome == "UP":
                resolved_up += 1

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
    print(f"Resolved UP in {resolved_up/markets_tested} markets")

    return X_train, y_train


def extract_market_metadata(
        metadata_start: list[dict[str, Any]],
        metadata_end: list[dict[str, Any]],
        ) -> MarketMetadata:
    if not metadata_start:
        print("metadata_start is empty")
        return None
    if not metadata_end:
        print("metadata_end is empty")
        return None
    event = metadata_start[0]
    
    assets = extract_market_assets(metadata_start)
    price_to_beat = extract_price_to_beat(metadata_end)
    final_price = extract_final_price(metadata_end)
    resolved_outcome = get_resolved_outcome(metadata_end)

    #markets = event.get("markets")
    #market = markets[0]
    #event_start = market.get("eventStartTime")
    #end_date = market.get("endDate")

    return MarketMetadata(
        up_asset_id=assets.up_asset_id,
        down_asset_id=assets.down_asset_id,
        final_price=final_price,
        price_to_beat=price_to_beat,
        resolved_outcome=resolved_outcome,
    )


def get_paths_by_dates(dataset_paths, start_datetime=datetime(2026,7,6), end_datetime=datetime(2026,7,24)):
    train_paths = []
    
    for dataset in dataset_paths:
        for data_file in Path(dataset).glob("*.gz"):
            file_creation_date = extract_timestamp(filename=data_file.name)

            if file_creation_date < end_datetime.timestamp() and file_creation_date > start_datetime.timestamp():
                train_paths.append(data_file)

    return train_paths



def start_evaluation(predictor, test_paths, max_target_delay_ms, observation_interval_ms=0):
    for data_file in test_paths:
        print(f"Found data file: {data_file}")
        file = data_file.resolve()
        with gzip.open(file, "rt", encoding="utf-8") as f:
            data = json.load(f)

            metadata_start = data["metadata_start"]
            metadata_end = data["metadata_end"]
            #print(metadata_end)
            metadata = extract_market_metadata(metadata_start=metadata_start, metadata_end=metadata_end)
            #print(metadata)

            target_matcher = FutureTargetMatcher(market_metadata=metadata, max_target_delay_ms=max_target_delay_ms)
            evaluator = PredictionEvaluator(
                predictor=predictor,
                target_matcher=target_matcher
            )
            market_snapshots = prepare_market_snapshots(data)

            del data

            observations = evaluator.evaluate_market(market_snapshots, observation_interval_ms=observation_interval_ms)

            print("Observations:", len(observations))
            print("Resolved:", metadata.resolved_outcome)
            print("MAE:", mae(observations))
            print("MSE (Brier Score):", brier_score(observations))

            # try:
            #     for i in range(5):
            #         observation = observations[i]
            #         print(
            #             f"Prediction at {observation.prediction_timestamp}: "
            #             #f"current={observation.current_value:.4f}, "
            #             f"predicted={observation.predicted_value:.4f}, "
            #             f"actual={observation.actual_value:.4f}, "
            #             f"actual timestamp={observation.actual_timestamp}, "
            #         )
            # except IndexError:
            #     print("No observations in this market. There was a problem with something.")

    #plot_prediction_observations(observations)
    #plot_prediction_accuracy(observations)


def compute_metrics(task_type: str, y_true: np.ndarray, predictions: np.ndarray) -> dict[str, float | None]:
    y_true = np.asarray(y_true)
    predictions = np.asarray(predictions, dtype=float)

    if len(y_true) == 0:
        return {}

    # if task_type == TASK_REGRESSION:
    #     return {
    #         "MAE": float(mean_absolute_error(y_true, predictions)),
    #         "RMSE": float(np.sqrt(mean_squared_error(y_true, predictions))),
    #         "R²": float(r2_score(y_true, predictions)) if len(y_true) > 1 else None,
    #     }

    # for now - only binary classifier
    y_int = y_true.astype(int)
    clipped = np.clip(predictions, 1e-9, 1 - 1e-9) #clips close-zero to zero and close-to-one to one
    metrics: dict[str, float | None] = {
        "Brier score": float(brier_score_loss(y_int, clipped)),
        "Log loss": float(log_loss(y_int, clipped, labels=[0, 1])),
        "Accuracy @ 0.5": float(accuracy_score(y_int, clipped >= 0.5)), #measures how often predicted probability gives the correct binary UP/DOWN outcome when using 0.5 as the decision threshold
    }
    metrics["ROC AUC"] = (
        float(roc_auc_score(y_int, clipped)) if len(np.unique(y_int)) == 2 else None
    )
    return metrics


def train_model(
    train_paths: Sequence[Path],
    feature_extractor: MarketFeatureExtractor,
    feature_names: Sequence[str],
    horizon_ms: int,
    target: TrainingTarget,
    max_target_delay_ms: int | None = None,
    sample_interval_ms: int | None = 5000,
):

    training_samples = prepare_training_data(
        train_paths=train_paths,
        feature_extractor=feature_extractor,
        feature_names=feature_names,
        target=target,
        horizon_ms=horizon_ms,
        max_target_delay_ms=max_target_delay_ms,
    )

    if target.name == "outcome_probability":
        print("using a classifier model")
        model = HistGradientBoostingClassifier(
        learning_rate=0.03,
        max_iter=1000,
        max_leaf_nodes=3,
        min_samples_leaf=100,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.15,
        n_iter_no_change=30,
        tol=1e-6,
        random_state=42,
        )
    else:
        model = HistGradientBoostingRegressor(
        learning_rate=0.03,
        max_iter=1000,
        max_leaf_nodes=3,
        min_samples_leaf=100,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.15,
        n_iter_no_change=30,
        tol=1e-6,
        random_state=42,
        )

    X_train, y_train = training_samples
    model.fit(X_train, y_train)
    print("Training complete")
    print(model)

    model.predictor_feature_names_ = feature_names
    model.horizon_ms_ = horizon_ms

    return model


def main():
    print("start")
    GRADIENT_BOOSTING_FEATURES = (
        "current_midpoint",
        #"binance_range_position_30000"

        #"midpoint_momentum_3000",
        #"midpoint_momentum_10000",
        #"midpoint_momentum_30000",

        #"spread",

        #"imbalance_top_1",
        #"imbalance_top_3",
        #"imbalance_top_5",

        "bid_volume_top_5",
        "ask_volume_top_5",

        #"binance_return_3000",
        #"binance_return_10000",
        #"binance_return_30000",
        #"binance_return_volatility_15000",

        #"relative_distance_to_price_to_beat",
        "seconds_remaining",
    )

    # GRADIENT_BOOSTING_FEATURES = (
    #     "binance_return_1000",
    #     "binance_return_3000",
    #     #"binance_range_position_5000",
    #     #"binance_range_position_15000",
    #     #"binance_range_position_30000",
    #     #"binance_return_volatility_10000",
    #     #"binance_return_volatility_20000",
    #     #"binance_relative_high_distance_5000",
    #     #"binance_relative_low_distance_5000",
    #     #"binance_range_position_7000"
    #     #"binance_return_3500",
    #     #"binance_acceleration_1s_5s",
    # )


    predictor_path = sys.argv[1]
    dataset_paths = sys.argv[2:]

    training_required = True
    horizon_ms = 0
    target = OUTCOME_PROBABILITY_TARGET
    max_target_delay_ms = None #1000 normally, None for outcome_probability
    observation_interval_ms=5000 #min distance between two evaluated observations (used in testing/evaluation)

    if training_required:
        #test_paths, train_snapshots = generate_test_and_train_data(dataset_paths)
        train_paths = get_paths_by_dates(dataset_paths=dataset_paths, start_datetime=datetime(2026,8,5), end_datetime=datetime(2026,8,8))
        #train_paths = get_paths_by_dates(dataset_paths=dataset_paths, start_datetime=datetime(2026,7,5), end_datetime=datetime(2026,7,10))
        train_paths = sort_paths_chronologically(train_paths)
        #print(train_paths)

        test_paths = get_paths_by_dates(dataset_paths=dataset_paths, start_datetime=datetime(2026,7,30), end_datetime=datetime(2026,8,2))
        test_paths = sort_paths_chronologically(test_paths)
        #print(test_paths)

        #training_samples = None
        # training_samples = prepare_training_data(
        #     train_paths=train_paths,
        #     feature_extractor=MarketFeatureExtractor(binance_lookbacks_ms=(1000,10000,30000),
        #                                              crypto_range_windows_ms=(5000,15000,30000)),
        #     #feature_extractor=MarketFeatureExtractor(),
        #     feature_names=GRADIENT_BOOSTING_FEATURES,
        #     target=target,
        #     horizon_ms=horizon_ms,
        #     max_target_delay_ms=max_target_delay_ms,
        # )

        feature_extractor = MarketFeatureExtractor(binance_lookbacks_ms=(1000,10000,30000),
                                                     crypto_range_windows_ms=(5000,15000,30000))

        model = train_model(
            train_paths=train_paths,
            feature_extractor=feature_extractor,
            feature_names=GRADIENT_BOOSTING_FEATURES,
            horizon_ms=horizon_ms,
            target=target,
            max_target_delay_ms=max_target_delay_ms
        )
        joblib.dump(model, "bot/trained_models/model_name.joblib")

        #model = joblib.load("bot/trained_models/trend_model_btc2.joblib")
        #model = joblib.load("bot/trained_models/trend_model_btc.joblib")
        predictor = GradientBoostingPredictor(
            model=model,
            feature_extractor=feature_extractor,
            horizon_ms=horizon_ms,
            #target_name="normalized_crypto_trend",
            target_name=target.name,
            gradient_boosting_features=GRADIENT_BOOSTING_FEATURES,
            training_samples=None,
            market_name="bitcoin-up-or-down",
        )
        
        start_evaluation(predictor, test_paths=test_paths, max_target_delay_ms=max_target_delay_ms, observation_interval_ms=observation_interval_ms)
    else:
        # test_paths=get_test_paths(dataset_paths=dataset_paths)
        # start_evaluation(predictor=None, test_paths=test_paths)
        print("nothing for now")

    

if __name__ == "__main__":
    main()