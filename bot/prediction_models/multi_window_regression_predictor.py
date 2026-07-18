import numpy as np
from sklearn.linear_model import LinearRegression
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from collections import deque
from dataclasses import dataclass
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot, PricePrediction


@dataclass(frozen=True)
class WindowMomentum:
    lookback_ms: int
    requested_timestamp: int
    actual_timestamp: int
    past_midpoint: float
    momentum: float
    weight: float

    @property
    def lookup_delay_ms(self) -> int:
        return self.requested_timestamp - self.actual_timestamp

class MultiWindowRegressionPredictor:
    def __init__(self, training_data: list[list[MarketSnapshot]], model: LinearRegression = None, horizon_ms=3000, lookback_windows_ms: list[int]=None, max_lookup_delay_ms=5000):
        self.past_snapshots = deque()
        if lookback_windows_ms is None:
            lookback_windows_ms = [3000, 8000, 18000]
        model = self.train_momentum_regression(markets=training_data, lookback_windows_ms=lookback_windows_ms)

        sorted_windows = tuple(sorted(lookback_windows_ms))
    
        print("Intercept:", model.intercept_)
        for lookback_ms, coefficient in zip(sorted_windows, model.coef_,):
            print(
                f"{lookback_ms} ms coefficient: "
                f"{coefficient}")
            

        self.model = model
        self.lookback_windows_ms = tuple(sorted(lookback_windows_ms))
        self.horizon_ms = horizon_ms
        self.max_lookup_delay_ms = max_lookup_delay_ms
        self.maximum_lookback_ms = max(self.lookback_windows_ms)

    def update(self, snapshot: MarketSnapshot):

        if snapshot.up_book.midpoint is None:
            return None

        self.validate_snapshot(snapshot)
        self.past_snapshots.append(snapshot)
        

        oldest_required_timestamp = snapshot.timestamp - self.maximum_lookback_ms
        self.remove_old_timestamps(oldest_required_timestamp)
        
        window_results: list[WindowMomentum] = []

        for lookback_ms in self.lookback_windows_ms:
            requested_timestamp = snapshot.timestamp - lookback_ms
            past_snapshot = self.find_snapshot_at_or_before(requested_timestamp)

            if past_snapshot is None or past_snapshot.up_book.midpoint is None:
                return None
            

            lookup_delay_ms = requested_timestamp - past_snapshot.timestamp
            if self.max_lookup_delay_ms is not None and lookup_delay_ms > self.max_lookup_delay_ms:
                return None
            
            momentum = snapshot.up_book.midpoint - past_snapshot.up_book.midpoint

            window_results.append(
                WindowMomentum(
                    lookback_ms=lookback_ms,
                    requested_timestamp=requested_timestamp,
                    actual_timestamp=past_snapshot.timestamp,
                    past_midpoint=past_snapshot.up_book.midpoint,
                    momentum=momentum,
                    weight=None,
                )
            )

        features = np.array([[window.momentum for window in window_results]], dtype=float,)
        
       
        predicted_change = float(self.model.predict(features)[0])
        predicted_midpoint = snapshot.up_book.midpoint + predicted_change
        predicted_midpoint = min(1.0, max(0.0, predicted_midpoint)) # market prices should stay between 0 and 1
        
        return PricePrediction(
            prediction_timestamp=snapshot.timestamp,
            horizon_ms=self.horizon_ms,
            predicted_midpoint=predicted_midpoint,
            current_midpoint=snapshot.up_book.midpoint,
        ) 

    def remove_old_timestamps(self, oldest_required_timestamp):
        while (len(self.past_snapshots) >= 2 and self.past_snapshots[1].timestamp <= oldest_required_timestamp):
            self.past_snapshots.popleft()


    def find_snapshot_at_or_before(self, target_timestamp):
        candidate = None
        for snapshot in self.past_snapshots:
            if snapshot.timestamp <= target_timestamp:
                candidate = snapshot
            else:
                break

        return candidate


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
        

    def create_momentum_training_samples(self,
        snapshots: Sequence[MarketSnapshot],
        lookback_windows_ms: Sequence[int],
        horizon_ms= 3000,
        max_lookup_delay_ms=5000,
    ) -> tuple[np.ndarray, np.ndarray]:
        if not snapshots:
            return (
                np.empty((0, 1), dtype=float),
                np.empty((0,), dtype=float),
            )

        lookback_windows = tuple(sorted(lookback_windows_ms))
        timestamps = [snapshot.timestamp for snapshot in snapshots]
        feature_count = len(lookback_windows)

        if not snapshots:
            return (
                np.empty(
                    shape=(0, feature_count),
                    dtype=float,
                ),
                np.empty(
                    shape=(0,),
                    dtype=float,
                ),
            )
        timestamps = [snapshot.timestamp for snapshot in snapshots]
        
        features: list[list[float]] = []
        targets: list[float] = []

        for current_index, current in enumerate(snapshots):
            if current is None or current.up_book.midpoint is None:
                continue

            row: list[float] = []
            valid_row = True

            for lookback_ms in lookback_windows:
                requested_past_timestamp = current.timestamp - lookback_ms

                # Latest snapshot at or before requested past time.
                past_index = bisect_right(timestamps, requested_past_timestamp, 0,current_index) - 1
                
                
                if past_index < 0:
                    valid_row = False
                    break

                past = snapshots[past_index]
                if past is None or past.up_book.midpoint is None:
                    valid_row = False
                    break

                lookup_delay_ms = requested_past_timestamp - past.timestamp

                if (max_lookup_delay_ms is not None
                    and lookup_delay_ms > max_lookup_delay_ms):
                    valid_row = False
                    break

                momentum = current.up_book.midpoint - past.up_book.midpoint
                row.append(momentum)

            if not valid_row:
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

                
                
            future_change = future.up_book.midpoint - current.up_book.midpoint
                

            features.append(row)
            targets.append(future_change)

        if not features:
            return (
                np.empty(
                    shape=(0, feature_count),
                    dtype=float,
                ),
                np.empty(
                    shape=(0,),
                    dtype=float,
                ),
            )

        return (
            np.asarray(features, dtype=float),
            np.asarray(targets, dtype=float),
        )
    
    def train_momentum_regression(self,
        markets: list[list[MarketSnapshot]],
        lookback_windows_ms: Sequence[int],
        horizon_ms=3000,
        max_lookup_delay_ms=5000,
        fit_intercept:bool = True
    ) -> LinearRegression:
        
        lookback_windows = tuple(sorted(lookback_windows_ms))

        feature_parts: list[np.ndarray] = []
        target_parts: list[np.ndarray] = []


        for snapshots in markets:
            X_market, y_market = (
                self.create_momentum_training_samples(
                    snapshots=snapshots,
                    lookback_windows_ms=lookback_windows,
                    horizon_ms=horizon_ms,
                    max_lookup_delay_ms=max_lookup_delay_ms)
                )

            if len(X_market) == 0:
                continue

            feature_parts.append(X_market)
            target_parts.append(y_market)

        if not feature_parts:
            raise ValueError("No valid training samples were generated.")
                
        X = np.concatenate(feature_parts, axis=0)
        y = np.concatenate(target_parts, axis=0)

        if X.shape[1] != len(lookback_windows):
            raise RuntimeError(
                "Training feature count does not match the number of lookback windows.")


        model = LinearRegression(fit_intercept=fit_intercept)

        model.fit(X, y)

        return model