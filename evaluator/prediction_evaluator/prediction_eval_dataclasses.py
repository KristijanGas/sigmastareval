
from dataclasses import dataclass
from typing import Any

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

    time_to_end_ms: int | None = None
    price_to_beat: float | None = None



@dataclass
class PredictionObservation:
    prediction_timestamp: int
    requested_target_timestamp: int #current_timestamp + lookahead
    actual_timestamp: int
    predicted_midpoint: float  #make more flexible later (for all types of predictions)
    actual_midpoint: float
    current_midpoint: float


# make more flexible later
@dataclass
class PricePrediction:
    prediction_timestamp: int   #timestamp at which the prediction is computed
    horizon_ms: int
    predicted_midpoint: float   #predicted value of midpoint
    current_midpoint: float   #midpoint at prediction time

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