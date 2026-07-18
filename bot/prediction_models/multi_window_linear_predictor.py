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



class MultiWindowLinearPredictor:
    def __init__(self, horizon_ms=3000, lookback_weights=None, max_lookup_delay_ms=5000):
        self.past_snapshots = deque()
        if lookback_weights is None:
            self.lookback_weights = {3000:0.18, 8000:0.08, 18000:0.04}
        else:
            self.lookback_weights = lookback_weights
        self.horizon_ms = horizon_ms
        self.max_lookup_delay_ms = max_lookup_delay_ms
        self.maximum_lookback_ms = max(self.lookback_weights)

    def update(self, snapshot: MarketSnapshot):

        if snapshot.up_book.midpoint is None:
            return None

        self.validate_snapshot(snapshot)
        self.past_snapshots.append(snapshot)
        

        oldest_required_timestamp = snapshot.timestamp - self.maximum_lookback_ms
        self.remove_old_timestamps(oldest_required_timestamp)
        
        window_results: list[WindowMomentum] = []

        for lookback_ms, weight in (self.lookback_weights.items()):
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
                    weight=weight,
                )
            )

        if not window_results:
            return None
        
        weights = [window.weight for window in window_results]
        predicted_change = sum(weight * window.momentum
                               for window, weight in zip(window_results, weights))
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