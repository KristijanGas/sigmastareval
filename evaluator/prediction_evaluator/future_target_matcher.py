
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketMetadata, NumericPrediction, MarketSnapshot, PredictionObservation
from collections import deque


class FutureTargetMatcher:
    def __init__(self, market_metadata: MarketMetadata = None, max_target_delay_ms: int = 1000):
        self.pending: deque[NumericPrediction] = deque()
        self.max_target_delay_ms = max_target_delay_ms
        self.market_metadata: MarketMetadata = market_metadata

    def reset(self):
        self.pending.clear()
    
    def add_prediction(self, prediction: NumericPrediction):
        self.pending.append(prediction)

    def process_snapshot(self, snapshot: MarketSnapshot):
        observations: list[PredictionObservation] = []

        while self.pending:
            prediction = self.pending[0]

            #print(snapshot.timestamp)
            #print(prediction.horizon_ms)
            #print(prediction.target_timestamp)
            if snapshot.timestamp < prediction.target_timestamp:
                break

            self.pending.popleft()

            target_delay_ms = snapshot.timestamp - prediction.target_timestamp #always: snapshot.timestamp >= prediction.target_timestamp
            if (self.max_target_delay_ms is not None and target_delay_ms > self.max_target_delay_ms):
                continue

            actual_value = self.get_actual_value(prediction=prediction, snapshot=snapshot)
            #print(actual_value)
            if actual_value is None:
                continue

            observation = PredictionObservation(
                prediction_timestamp = prediction.prediction_timestamp,
                requested_target_timestamp = prediction.target_timestamp,
                actual_timestamp = snapshot.timestamp,
                target_name=prediction.target,
                predicted_value = prediction.predicted_value,
                #predicted_value = prediction.context["predicted_crypto_change"],
                actual_value = actual_value,
                current_value = prediction.current_value,
                current_midpoint=snapshot.up_book.midpoint,
                )
            
            observations.append(observation)

        return observations
    
    def get_actual_value(
        self,
        prediction: NumericPrediction,
        snapshot: MarketSnapshot,
    ) -> float | None:
        if prediction.target == "midpoint_change":
            return snapshot.up_book.midpoint

        if prediction.target == "crypto_price":
            return snapshot.crypto_price

        if prediction.target == "crypto_change":
            future_price = snapshot.crypto_price
            current_price = prediction.context.get("current_crypto_price")

            if future_price is None or current_price is None:
                return None

            return float(future_price - current_price)

        if prediction.target == "normalized_crypto_trend":
            future_price = snapshot.crypto_price
            current_price = prediction.context.get("current_crypto_price")
            volatility = prediction.context.get("volatility")

            if (
                future_price is None
                or current_price is None
                or volatility is None
                or volatility <= 0
            ):
                return None

            return float(
                (future_price - current_price) / volatility
            )

        if prediction.target == "outcome_probability":
            resolved_outcome = self.market_metadata.resolved_outcome
            if resolved_outcome is None:
                return None
            if resolved_outcome == "UP":
                return 1
            if resolved_outcome == "DOWN":
                return 0


        raise ValueError(
            f"Unsupported prediction target: {prediction.target}"
        )





    