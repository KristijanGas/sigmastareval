
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

@dataclass
class OrderBookLevel:
    price: float
    size: float


@dataclass
class OrderBookState:
    asset_id: str
    timestamp: int
    bids: list[Any]
    asks: list[Any]

    best_bid: float | None
    best_ask: float | None
    best_bid_size: float | None
    best_ask_size: float | None
    midpoint: float | None
    spread: float | None

    
@dataclass
class MarketSnapshot:
    timestamp: int
    up_book: OrderBookState | None
    down_book: OrderBookState | None

    crypto_price: float | None
    crypto_price_timestamp: int | None

    market_end_timestamp: int | None
    time_to_end_ms: int | None = None
    price_to_beat: float | None = None


@dataclass
class MarketMetadata:
    market_id: str | None = None
    slug: str | None = None

    up_asset_id: str | None = None
    down_asset_id: str | None = None

    event_start_timestamp: int | None = None
    end_timestamp: int | None = None

    price_to_beat: float | None = None
    final_price: float | None = None
    resolved_outcome: str | None = None



@dataclass
class PredictionObservation:
    prediction_timestamp: int
    requested_target_timestamp: int #current_timestamp + lookahead
    actual_timestamp: int
    target_name: str

    predicted_value: float
    actual_value: float
    current_value: float | None
    current_midpoint: float | None

    context: dict[str, Any] | None = None


# make more flexible later
@dataclass
class NumericPrediction:
    prediction_timestamp: int   #timestamp at which the prediction is computed
    horizon_ms: int
    target: str     #make enum later
    predicted_value: float   #predicted value
    current_value: float   #value at prediction time
    context: dict[str, Any] | None = None

    @property
    def target_timestamp(self): #timestamp for which the prediction is intended
        return self.prediction_timestamp + self.horizon_ms
    

    
@dataclass
class CryptoPrice:
    timestamp: int
    price: float
    symbol: str


@dataclass
class MarketAssets:
    up_asset_id: str
    down_asset_id: str

@dataclass
class EvaluationRunResult:
    task_type: str
    metrics: dict[str, float | None]
    raw_metrics: dict[str, float | None] | None
    calibrated_metrics: dict[str, float | None] | None
    y_true: np.ndarray
    predictions: np.ndarray
    raw_predictions: np.ndarray | None
    calibrated_predictions: np.ndarray | None
    selected_prediction_mode: str
    has_calibration: bool
    figures: dict[str, Any]
    sample_count: int
    model_path: Path