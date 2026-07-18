import numpy as np
from sklearn.linear_model import LinearRegression
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from collections import deque
from dataclasses import dataclass
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot, PricePrediction


class LinearRegressionPredictor:
    def __init__(self, training_data: list[list[MarketSnapshot]], model: LinearRegression = None, lookback_ms=3000, horizon_ms=3000, alpha=0.5, max_lookup_delay_ms=5000):
        model = self.train_momentum_regression(training_data)
        print("Intercept:", model.intercept_)
        print("Momentum coefficient:", model.coef_[0])

        if not hasattr(model, "coef_"):
            raise ValueError(
                "The regression model must be fitted before "
                "creating the predictor."
            )
        
        self.model = model
        self.past_snapshots = deque()
        self.alpha = alpha
        self.lookback_ms = lookback_ms
        self.horizon_ms = horizon_ms
        self.max_lookup_delay_ms = max_lookup_delay_ms

    def update(self, snapshot: MarketSnapshot):
        #snapshot = Snapshot(timestamp=current_timestamp, midpoint=current_midpoint)

        if snapshot.up_book.midpoint is None:
            return None
        self.validate_snapshot(snapshot)

        self.past_snapshots.append(snapshot)

        target_timestamp = snapshot.timestamp - self.lookback_ms
        self.remove_old_timestamps(target_timestamp)

        past_snapshot = self.find_snapshot_at_or_before(target_timestamp)
        if past_snapshot is None:
            return None
        if past_snapshot.up_book.midpoint is None:
            return None
        
        lookup_delay = target_timestamp - past_snapshot.timestamp
        if (lookup_delay > self.max_lookup_delay_ms):      # found snapshot is too old
            return None
        
        # if snapshot.up_book.midpoint is None or past_snapshot.up_book.midpoint is None:
        #     predicted_midpoint = None
        # else:
        momentum = snapshot.up_book.midpoint - past_snapshot.up_book.midpoint

        features = np.array([[momentum]], dtype=float)
        predicted_change = float(self.model.predict(features)[0])

        predicted_midpoint = snapshot.up_book.midpoint + predicted_change
        predicted_midpoint = min(1.0, max(0.0, predicted_midpoint)) # market prices should stay between 0 and 1

        return PricePrediction(
            prediction_timestamp=snapshot.timestamp,
            horizon_ms=self.horizon_ms,
            predicted_midpoint=predicted_midpoint,
            current_midpoint=snapshot.up_book.midpoint,
        )
    
    def create_momentum_training_samples(self,
        snapshots: Sequence[MarketSnapshot],
        lookback_ms= 3000,
        horizon_ms= 3000,
        max_lookup_delay_ms=5000,
    ) -> tuple[np.ndarray, np.ndarray]:
        if not snapshots:
            return (
                np.empty((0, 1), dtype=float),
                np.empty((0,), dtype=float),
            )

        timestamps = [snapshot.timestamp for snapshot in snapshots]

        features: list[list[float]] = []
        targets: list[float] = []

        for current_index, current in enumerate(snapshots):
            if current is None or current.up_book.midpoint is None:
                continue

            requested_past_timestamp = current.timestamp - lookback_ms

            # Latest snapshot at or before requested past time.
            past_index = bisect_right(timestamps, requested_past_timestamp, 0,current_index) - 1
            
                

            if past_index < 0:
                continue

            past = snapshots[past_index]
            if past is None or past.up_book.midpoint is None:
                continue

            lookup_delay_ms = requested_past_timestamp - past.timestamp


            if (max_lookup_delay_ms is not None
                and lookup_delay_ms > max_lookup_delay_ms):
                continue

            requested_target_timestamp = current.timestamp + horizon_ms
               

            # first snapshot at or after requested future time.
            future_index = bisect_left(
                timestamps,
                requested_target_timestamp,
                current_index + 1,
            )

            if future_index >= len(snapshots):
                continue

            future = snapshots[future_index]

            if future is None or future.up_book.midpoint is None:
                continue

            # target_delay_ms = future.timestamp - requested_target_timestamp

            # if (max_target_delay_ms is not None
            #     and target_delay_ms > max_target_delay_ms):
            #     continue

            momentum = current.up_book.midpoint - past.up_book.midpoint
                
            future_change = future.up_book.midpoint - current.up_book.midpoint
                

            features.append([momentum])
            targets.append(future_change)

        return (
            np.asarray(features, dtype=float),
            np.asarray(targets, dtype=float),
        )
    

    def train_momentum_regression(self,
        markets: list[list[MarketSnapshot]],
        lookback_ms=3000,
        horizon_ms=3000,
        max_lookup_delay_ms=5000,
    ) -> LinearRegression:
        feature_parts: list[np.ndarray] = []
        target_parts: list[np.ndarray] = []

        for snapshots in markets:
            X_market, y_market = (
                self.create_momentum_training_samples(
                    snapshots=snapshots,
                    lookback_ms=lookback_ms,
                    horizon_ms=horizon_ms,
                    max_lookup_delay_ms=max_lookup_delay_ms)
                )

            if len(X_market) == 0:
                continue

            feature_parts.append(X_market)
            target_parts.append(y_market)

        if not feature_parts:
            raise ValueError(
                "No valid training samples were generated."
            )

        X = np.concatenate(feature_parts, axis=0)
        y = np.concatenate(target_parts, axis=0)

        model = LinearRegression(fit_intercept=True)

        model.fit(X, y)

        return model

        
        
    # removes snapshots older than the last snapshot that could still be selected as valid lookback target
    def remove_old_timestamps(self, target_timestamp):
        while (len(self.past_snapshots) > 1 and self.past_snapshots[1].timestamp <= target_timestamp):
            self.past_snapshots.popleft()


    def find_snapshot_at_or_before(self, target_timestamp):
        candidate = None
        for snapshot in self.past_snapshots:
            if snapshot.timestamp <= target_timestamp:
                candidate = snapshot
            else:
                break

        return candidate
        
    # clears history before starting a new market
    def reset(self):
        self.past_snapshots.clear()
    
    def validate_snapshot(
        self,
        snapshot: MarketSnapshot,
    ) -> None:
        if not 0.0 <= snapshot.up_book.midpoint <= 1.0:
            raise ValueError(
                "Snapshot midpoint must be between 0 and 1"
            )

        if (
            self.past_snapshots
            and snapshot.timestamp
            < self.past_snapshots[-1].timestamp
        ):
            print(snapshot.timestamp)
            print(self.past_snapshots[-1].timestamp)
            raise ValueError(
                "Snapshots must be provided in strictly "
                "increasing timestamp order"
            )