from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import date, datetime, time, timedelta
from typing import Any, Sequence

import joblib
import numpy as np
from evaluator.prediction_evaluator.feature_extractor import MarketFeatureExtractor
from evaluator.utils.utils import extract_timestamp, sort_paths_chronologically



'''
For now mostly data preparation functions for model training
'''


TASK_REGRESSION = "regression"
TASK_BINARY_CLASSIFICATION = "binary_classification"
PREDICTION_MODE_RAW = "raw"
PREDICTION_MODE_CALIBRATED = "calibrated"


def collect_market_paths(
    dataset_dirs: Sequence[str | Path],
    start_date: date,
    end_date: date,
) -> list[Path]:
    """Collect .gz markets by filename timestamp, inclusive of both selected dates."""
    start_dt = datetime.combine(start_date, time.min)
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)

    paths: list[Path] = []
    for dataset_dir in dataset_dirs:
        dataset_path = Path(dataset_dir).expanduser()
        if not dataset_path.exists():
            continue

        for data_file in dataset_path.glob("*.gz"):
            try:
                ts = extract_timestamp(filename=data_file.name)
            except (ValueError, TypeError):
                continue

            if start_dt.timestamp() <= ts < end_dt_exclusive.timestamp():
                paths.append(data_file)

    return sort_paths_chronologically(paths)


@dataclass(frozen=True)
class DatasetSplit:
    train_paths: list[Path]
    validation_paths: list[Path]
    calibration_paths: list[Path]
    test_paths: list[Path]


# splits a list of paths into sets for training, validation, calibration (optional) and testing
def split_paths_chronologically(paths: Sequence[Path],
    train_fraction: float,
    validation_fraction: float,
    calibration_fraction: float) -> DatasetSplit:
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    if not 0 <= validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    if not 0 <= calibration_fraction < 1:
        raise ValueError("calibration_fraction must be between 0 and 1")

    used_fraction = train_fraction + validation_fraction + calibration_fraction
    if used_fraction >= 1:
        raise ValueError("Train + validation + calibration fractions must total less than 1")

    n = len(paths)
    if n < 4:
        raise ValueError("At least 4 markets are required for train/validation/test splitting")

    n_train = max(1, int(n * train_fraction))
    n_validation = max(1, int(n * validation_fraction)) if validation_fraction > 0 else 0
    n_calibration = max(1, int(n * calibration_fraction)) if calibration_fraction > 0 else 0

    while n_train + n_validation + n_calibration >= n:
        if n_calibration > 0:
            n_calibration -= 1
        elif n_validation > 1:
            n_validation -= 1
        elif n_train > 1:
            n_train -= 1
        else:
            raise ValueError("Not enough markets to create the requested split")

    train_end = n_train
    validation_end = train_end + n_validation
    calibration_end = validation_end + n_calibration

    return DatasetSplit(
        train_paths=list(paths[:train_end]),
        validation_paths=list(paths[train_end:validation_end]),
        calibration_paths=list(paths[validation_end:calibration_end]),
        test_paths=list(paths[calibration_end:]),
    )


def data_summary(name: str, paths: Sequence[Path], y: np.ndarray | None = None):
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


def build_feature_extractor(config: dict[str, Any]) -> MarketFeatureExtractor:
    return MarketFeatureExtractor(
        binance_lookbacks_ms=tuple(config.get("binance_lookbacks_ms", (1000, 10000, 30000))),
        crypto_range_windows_ms=tuple(config.get("crypto_range_windows_ms", (5000, 15000, 30000))),
    )

def load_model_artifact(path):
    path = Path(path).expanduser()
    loaded = joblib.load(path)

    artifact = dict(loaded)
    artifact.setdefault("calibration_method", "none")
    artifact.setdefault("calibrator", None)
    artifact.setdefault("has_calibrator", artifact.get("calibrator") is not None)
    artifact.setdefault("base_estimator_type", type(artifact["base_estimator"]).__name__)
    if artifact.get("calibrator") is not None:
        artifact.setdefault("calibrator_type", type(artifact["calibrator"]).__name__)
    else:
        artifact.setdefault("calibrator_type", None)
        
    return artifact