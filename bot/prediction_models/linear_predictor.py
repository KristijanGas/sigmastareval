from collections import deque
from dataclasses import dataclass
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot, PricePrediction



class LinearPredictor:
    def __init__(self, lookback_ms=5000, horizon_ms=3000, alpha=0.5, max_lookup_delay_ms=5000):
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
        predicted_midpoint = snapshot.up_book.midpoint + self.alpha * momentum
        predicted_midpoint = min(1.0, max(0.0, predicted_midpoint)) # market prices should stay between 0 and 1

        return PricePrediction(
            prediction_timestamp=snapshot.timestamp,
            horizon_ms=self.horizon_ms,
            predicted_midpoint=predicted_midpoint,
            current_midpoint=snapshot.up_book.midpoint,
        )

        
        
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
    


    