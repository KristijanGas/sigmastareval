from collections.abc import Callable
from dataclasses import dataclass
from evaluator.prediction_evaluator.feature_extractor import ExtractedMarketState, MarketFeatureExtractor
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot
from typing import Generic, TypeVar


#used in context and target functions to distinguish between using no context on purpose and
# context being None
NO_CONTEXT = object() 

TargetContext = TypeVar("TargetContext")

@dataclass
class PendingTrainingRow(Generic[TargetContext]):
    prediction_timestamp: int
    feature_values: tuple[float, ...]
    target_context: TargetContext


# Defines how one model's training label is constructed
# create_context: saves information available at prediciton time (function)
# create_target: uses the saved context and the future snapshot to calculate y (function)
@dataclass
class TrainingTarget(Generic[TargetContext]):
    name: str
    create_context: Callable[[ExtractedMarketState, MarketSnapshot], TargetContext | None]
    create_target: Callable[[TargetContext, MarketSnapshot], float | None]





# CRYPTO CHANGE TARGET
# -------------------------------------

def create_crypto_price_context(extracted: ExtractedMarketState, snapshot: MarketSnapshot):
    current_price = snapshot.crypto_price
    if current_price is None or current_price <= 0:
        return None
    return float(current_price)

def create_crypto_price_target(current_price: float, future_snapshot: MarketSnapshot):
    future_price = future_snapshot.crypto_price
    if future_price is None or future_price <= 0:
        return None
    return float(future_price - current_price)


# y = P_t+h - P_t
CRYPTO_CHANGE_TARGET = TrainingTarget[float](
    name="crypto_change",
    create_context=create_crypto_price_context,
    create_target=create_crypto_price_target,
)



# MIDPOINT CHANGE TARGET
# ---------------------------------------

MIDPOINT_CHANGE_TARGET = TrainingTarget[float](
    name="midpoint_change",
    create_context=lambda extracted, snapshot: (extracted.current_midpoint),
    create_target=lambda current_midpoint, future_snapshot: (
        None if future_snapshot.up_book.midpoint is None
        else future_snapshot.up_book.midpoint - current_midpoint
    )
)


# OUTCOME PROBABILITY TARGET 
# ---------------------------------------
# (probability that resolution is UP)



