from enum import Enum

# targets can be used in strategies both as a string or Enum, for example PredictionTarget.MIDPOINT_CHANGE or "midpoint_change" are both
#   correct, but the first style is recommended for safety
class PredictionTarget(str, Enum):
    MIDPOINT_CHANGE = "midpoint_change"
    OUTCOME_PROBABILITY = "outcome_probability"
    NORMALIZED_CRYPTO_TREND = "normalized_crypto_trend"