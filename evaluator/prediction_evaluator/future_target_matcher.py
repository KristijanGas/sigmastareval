
from prediction_eval_dataclasses import PricePrediction, MarketSnapshot, PredictionObservation
from collections import deque


class FutureTargetMatcher:
    def __init__(self):
        self.pending: deque[PricePrediction] = deque()
        self.max_target_delay_ms = 3000

    def reset(self):
        self.pending.clear()
    
    def add_prediction(self, prediction: PricePrediction):
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

            observation = PredictionObservation(
                prediction_timestamp = prediction.prediction_timestamp,
                requested_target_timestamp = prediction.target_timestamp,
                actual_timestamp = snapshot.timestamp,
                predicted_midpoint = prediction.predicted_midpoint,
                actual_midpoint = snapshot.up_book.midpoint,
                current_midpoint = prediction.current_midpoint,
                )
            
            observations.append(observation)

        return observations





    