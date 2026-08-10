


'''
File used for model training related logic, model specific helpers and dataclasses.
'''

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from evaluator.prediction_evaluator.feature_extractor import MarketFeatureExtractor
from evaluator.prediction_evaluator.model_training_utils import DatasetSplit
from evaluator.prediction_evaluator.prediction_evaluator import compute_metrics, prepare_training_data
from evaluator.prediction_evaluator.training_targets import OUTCOME_PROBABILITY_TARGET, TrainingTarget
from sklearn.base import BaseEstimator
import inspect

import hashlib
import json
from pathlib import Path



ARTIFACT_VERSION = 2
TASK_REGRESSION = "regression"
TASK_BINARY_CLASSIFICATION = "binary_classification"
PREDICTION_MODE_RAW = "raw"
PREDICTION_MODE_CALIBRATED = "calibrated"


@dataclass(frozen=True)
class ValidationRunResult:
    task_type: str
    validation_metrics: dict[str, float | None]
    split_summary: list[dict[str, Any]]
    configuration_signature: str
    selected_max_iter: int
    early_stopping_source: str
    train_sample_count: int
    validation_sample_count: int
    validated_at: str


def build_feature_extractor(config: dict[str, Any]) -> MarketFeatureExtractor:
    return MarketFeatureExtractor(
        binance_lookbacks_ms=tuple(config.get("binance_lookbacks_ms", (1000, 10000, 30000))),
        crypto_range_windows_ms=tuple(config.get("crypto_range_windows_ms", (5000, 15000, 30000))),
    )


def get_task_type(target: TrainingTarget) -> str:
    if target.name == OUTCOME_PROBABILITY_TARGET.name:
        return TASK_BINARY_CLASSIFICATION
    return TASK_REGRESSION

def predict_raw(model: BaseEstimator, task_type: str, X: np.ndarray) -> np.ndarray:
    if task_type == TASK_BINARY_CLASSIFICATION:
        index = 1
        return np.asarray(model.predict_proba(X)[:, index], dtype=float)
    return np.asarray(model.predict(X), dtype=float)


def create_estimator(task_type: str, params: dict[str, Any]) -> BaseEstimator:
    common = dict(
        learning_rate=float(params["learning_rate"]),
        max_iter=int(params["max_iter"]),
        max_leaf_nodes=int(params["max_leaf_nodes"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        l2_regularization=float(params["l2_regularization"]),
        early_stopping=bool(params["early_stopping"]),
        n_iter_no_change=int(params["n_iter_no_change"]),
        tol=float(params["tol"]),
        random_state=int(params["random_state"]),
    )

    # Never create a random row-level validation holdout. Newer sklearn versions
    # accept X_val/y_val in fit(), which validate_model_configuration uses below.
    # Older versions fall back to early stopping on training loss.
    if common["early_stopping"]:
        common["validation_fraction"] = None

    if task_type == TASK_BINARY_CLASSIFICATION:
        return HistGradientBoostingClassifier(**common)
    if task_type == TASK_REGRESSION:
        return HistGradientBoostingRegressor(**common)
    raise ValueError(f"Unsupported task type: {task_type}")


#Fit a candidate and use explicit market-level validation for early stopping when supported.
def fit_candidate(
    model: BaseEstimator,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    early_stopping_requested: bool,
) -> str:
    
    fit_parameters = inspect.signature(model.fit).parameters # check if function definition allows explicit validation sets
    supports_explicit_validation = "X_val" in fit_parameters and "y_val" in fit_parameters

    if early_stopping_requested and supports_explicit_validation:
        model.fit(X_train, y_train, X_val=X_val, y_val=y_val)
        return "explicit validation markets"

    model.fit(X_train, y_train)
    if early_stopping_requested:
        return "training loss fallback (sklearn version has no X_val/y_val fit support)"
    return "disabled"


# Train only a candidate base-estimator and score it on chronological validation markets.
def validate_model_configuration(
    split: DatasetSplit,
    target: TrainingTarget,
    feature_names: Sequence[str],
    feature_extractor_config: dict[str, Any],
    horizon_ms: int,
    max_target_delay_ms: int | None,
    sample_interval_ms: int | None,
    estimator_params: dict[str, Any],
    progress: Callable[[str], None] | None = None,
) -> ValidationRunResult:

    task_type = get_task_type(target)
    feature_names = tuple(feature_names)

    if not feature_names:
        raise ValueError("Select at least one feature")
    if not split.train_paths:
        raise ValueError("Training split is empty")
    if not split.validation_paths:
        raise ValueError("Validation split is empty")

    #used to display progress messages in streamlit
    def notify(message: str):
        if progress is not None:
            progress(message)

    notify("Preparing training samples…")
    X_train, y_train = prepare_training_data(
        train_paths=split.train_paths,
        feature_extractor=build_feature_extractor(feature_extractor_config),
        feature_names=feature_names,
        horizon_ms=horizon_ms,
        target=target,
        max_target_delay_ms=max_target_delay_ms,
        sample_interval_ms=sample_interval_ms,
    )

    notify("Preparing validation samples…")
    X_val, y_val = prepare_training_data(
        train_paths=split.validation_paths,
        feature_extractor=build_feature_extractor(feature_extractor_config),
        feature_names=feature_names,
        horizon_ms=horizon_ms,
        target=target,
        max_target_delay_ms=max_target_delay_ms,
        sample_interval_ms=sample_interval_ms,
    )

    if len(X_train) == 0:
        raise ValueError("No training samples were produced")
    if len(X_val) == 0:
        raise ValueError("No validation samples were produced")

    if task_type == TASK_BINARY_CLASSIFICATION:
        y_train = y_train.astype(int)
        y_val = y_val.astype(int)
        if len(np.unique(y_train)) < 2:
            raise ValueError("Training data must contain both UP and DOWN labels")
        if len(np.unique(y_val)) < 2:
            raise ValueError("Validation data must contain both UP and DOWN labels")

    notify("Fitting candidate model…")
    candidate_model = create_estimator(task_type, estimator_params)
    early_stopping_source = fit_candidate(
        candidate_model,
        X_train,
        y_train,
        X_val,
        y_val,
        early_stopping_requested=bool(estimator_params.get("early_stopping", False)),
    )

    validation_predictions = predict_raw(candidate_model, task_type, X_val)
    validation_metrics = compute_metrics(task_type, y_val, validation_predictions)
    selected_max_iter = int(getattr(candidate_model, "n_iter_", estimator_params["max_iter"]))

    signature = build_validation_signature(
        split=split,
        target=target,
        feature_names=feature_names,
        feature_extractor_config=feature_extractor_config,
        horizon_ms=horizon_ms,
        max_target_delay_ms=max_target_delay_ms,
        sample_interval_ms=sample_interval_ms,
        estimator_params=estimator_params,
    )

    split_summary = [
        data_summary("Train", split.train_paths, y_train),
        data_summary("Validation", split.validation_paths, y_val),
        data_summary("Calibration", split.calibration_paths, None),
        data_summary("Reserved test", split.test_paths, None),
    ]

    return ValidationRunResult(
        task_type=task_type,
        validation_metrics=validation_metrics,
        split_summary=split_summary,
        configuration_signature=signature,
        selected_max_iter=selected_max_iter,
        early_stopping_source=early_stopping_source,
        train_sample_count=len(y_train),
        validation_sample_count=len(y_val),
        validated_at=datetime.now().isoformat(timespec="seconds"),
    )


# creates a signature for everything that affects base estimator validation
# signature is used to compare changes in model and training configuration
def build_validation_signature(
    split: DatasetSplit,
    target: TrainingTarget,
    feature_names: Sequence[str],
    feature_extractor_config: dict[str, Any],
    horizon_ms: int,
    max_target_delay_ms: int | None,
    sample_interval_ms: int | None,
    estimator_params: dict[str, Any],
) -> str:
    payload = {
        "train_paths": [str(Path(p)) for p in split.train_paths],
        "validation_paths": [str(Path(p)) for p in split.validation_paths],
        "target_name": target.name,
        "feature_names": list(feature_names),
        "feature_extractor_config": feature_extractor_config,
        "horizon_ms": int(horizon_ms),
        "max_target_delay_ms": max_target_delay_ms,
        "sample_interval_ms": sample_interval_ms,
        "estimator_params": estimator_params,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def data_summary(
    name: str,
    paths: Sequence[Path],
    y: np.ndarray | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "split": name,
        "markets": len(paths),
        "samples": int(len(y)) if y is not None else None,
        "start_market": paths[0].name if paths else None,
        "end_market": paths[-1].name if paths else None,
    }
    if y is not None and len(y) > 0 and set(np.unique(y)).issubset({0, 1, 0.0, 1.0}):
        row["UP samples %"] = float(np.mean(y.astype(int)) * 100)
    else:
        row["UP samples %"] = None
    return row