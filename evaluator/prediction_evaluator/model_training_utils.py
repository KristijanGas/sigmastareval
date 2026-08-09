from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import date, datetime, time, timedelta
from typing import Sequence
from evaluator.utils.utils import extract_timestamp, sort_paths_chronologically



'''
For now mostly data preparation functions for model training
'''



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