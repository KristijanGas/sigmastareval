from dataclasses import dataclass
from typing import Iterable, Sequence
from collections import deque
import statistics

from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot

@dataclass
class ExtractedFeatures:
   values: dict[str, float]

   def has_all(self, names: Iterable[str]) -> bool:
        return all(name in self.values for name in names)

   def missing(self, names: Iterable[str]) -> tuple[str, ...]:
        return tuple(name for name in names
               if name not in self.values)

   #Select features in exactly the requested order.
   def select_values(self, names: Sequence[str]) -> tuple[float, ...]:
      missing = self.missing(names)

      if missing:
         raise ValueError(f"Missing required features: {missing}")

      return tuple(self.values[name] for name in names)


   def select_row(self, names: Sequence[str]) -> list[list[float]]:
      """
      Shape expected by sklearn model.predict():
      one row containing N features.
      """
      return [list(self.select_values(names))]


@dataclass
class ExtractedMarketState:
    timestamp: int
    current_midpoint: float
    current_crypto_price: float | None
    features: ExtractedFeatures


class MarketFeatureExtractor:
   def __init__(
      self,
      midpoint_lookbacks_ms: Sequence[int] = (3000, 10000, 30000),
      binance_lookbacks_ms: Sequence[int] = (3000, 10000, 30000),
      imbalance_levels: Sequence[int] = (2,3,5),
      crypto_range_windows_ms: Sequence[int] = (10000, 30000),
      binance_volatility_windows_ms=(10000, 15000),

      max_lookup_delay_ms = 5000):
         self.midpoint_lookbacks_ms = self._validate_windows(
               midpoint_lookbacks_ms,
               "midpoint_lookbacks_ms",
         )

         self.binance_lookbacks_ms = self._validate_windows(
               binance_lookbacks_ms,
               "binance_lookbacks_ms",
         )

         self.imbalance_levels = tuple(sorted(set(imbalance_levels)))

         if any(level <= 0 for level in self.imbalance_levels):
               raise ValueError("All imbalance levels must be positive.")
         
         self.crypto_range_windows_ms = self._validate_windows(
            crypto_range_windows_ms,
            "crypto_range_windows_ms",
         )

         self.binance_volatility_windows_ms = self._validate_windows(
               binance_volatility_windows_ms,
               "binance_volatility_windows_ms",
         )

         if (max_lookup_delay_ms is not None and max_lookup_delay_ms < 0):
               raise ValueError("max_lookup_delay_ms cannot be negative.")

         self.max_lookup_delay_ms = max_lookup_delay_ms
         all_lookbacks = (self.midpoint_lookbacks_ms + self.binance_lookbacks_ms
               + self.crypto_range_windows_ms + self.binance_volatility_windows_ms)

         self.maximum_lookback_ms = (max(all_lookbacks) if all_lookbacks else 0)

         self.past_snapshots: deque[MarketSnapshot] = deque()

   @staticmethod
   def _validate_windows(windows: Sequence[int], name: str) -> tuple[int, ...]:
      result = tuple(sorted(set(windows)))
      if any(window <= 0 for window in result):
            raise ValueError(f"All {name} values must be positive.")
      
      return result
   
   def reset(self) -> None:
      self.past_snapshots.clear()

   # Store one chronological snapshot and extract every feature currently available.
   def update(self, snapshot: MarketSnapshot):
      current_midpoint = snapshot.up_book.midpoint

      if current_midpoint is None:
         return None

      try:
         self._validate_snapshot(snapshot)
      except ValueError:
         return None
      self.past_snapshots.append(snapshot)

      if self.maximum_lookback_ms > 0:
         oldest_required_timestamp = (snapshot.timestamp - self.maximum_lookback_ms)
         self._remove_old_snapshots(oldest_required_timestamp)

      # values: dict[str, float] = {"current_midpoint": current_midpoint}

      # self._add_midpoint_features(snapshot=snapshot, values=values)
      # self._add_orderbook_features(snapshot=snapshot, values=values)
      # self._add_binance_features(snapshot=snapshot, values=values)
      # self._add_market_context_features(snapshot=snapshot, values=values)

      # return ExtractedMarketState(
      #    timestamp=snapshot.timestamp,
      #    current_midpoint=current_midpoint,
      #    current_crypto_price=snapshot.crypto_price,
      #    features=ExtractedFeatures(values=values),
      # )
   
   def extract_market_features(self, snapshot: MarketSnapshot):
      current_midpoint = snapshot.up_book.midpoint
      values: dict[str, float] = {"current_midpoint": current_midpoint}

      self._add_midpoint_features(snapshot=snapshot, values=values)
      self._add_orderbook_features(snapshot=snapshot, values=values)
      self._add_binance_features(snapshot=snapshot, values=values)
      self._add_market_context_features(snapshot=snapshot, values=values)

      return ExtractedMarketState(
         timestamp=snapshot.timestamp,
         current_midpoint=current_midpoint,
         current_crypto_price=snapshot.crypto_price,
         features=ExtractedFeatures(values=values),
      )
   
   def update_and_extract(self, snapshot: MarketSnapshot):
      if snapshot is None:
         return None
      
      if snapshot.up_book is None:
         return None
      
      current_midpoint = snapshot.up_book.midpoint

      if current_midpoint is None:
         return None

      try:
         self._validate_snapshot(snapshot)
      except ValueError:
         return None
      self.past_snapshots.append(snapshot)

      if self.maximum_lookback_ms > 0:
         oldest_required_timestamp = (snapshot.timestamp - self.maximum_lookback_ms)
         self._remove_old_snapshots(oldest_required_timestamp)

      values: dict[str, float] = {"current_midpoint": current_midpoint}

      self._add_midpoint_features(snapshot=snapshot, values=values)
      self._add_orderbook_features(snapshot=snapshot, values=values)
      self._add_binance_features(snapshot=snapshot, values=values)
      self._add_market_context_features(snapshot=snapshot, values=values)

      return ExtractedMarketState(
         timestamp=snapshot.timestamp,
         current_midpoint=current_midpoint,
         current_crypto_price=snapshot.crypto_price,
         features=ExtractedFeatures(values=values),
      )
   
   def _add_midpoint_features(self, snapshot: MarketSnapshot, values: dict[str, float]):
      current_midpoint = snapshot.up_book.midpoint
      if current_midpoint is None:
         return

      for lookback_ms in self.midpoint_lookbacks_ms:
         past_snapshot = self._lookup_past_snapshot(
               current_timestamp=snapshot.timestamp,
               lookback_ms=lookback_ms,
         )

         if (past_snapshot is None or past_snapshot.up_book.midpoint is None):
               continue

         past_midpoint = past_snapshot.up_book.midpoint
         values[f"midpoint_momentum_{lookback_ms}"] = current_midpoint - past_midpoint

   def _add_orderbook_features(self, snapshot: MarketSnapshot, values: dict[str, float]):
      bids = snapshot.up_book.bids
      asks = snapshot.up_book.asks

      if not bids or not asks:
         return

      # These assume:
      # - bids sorted highest price first
      # - asks sorted lowest price first
      best_bid = float(bids[0]["price"])
      best_ask = float(asks[0]["price"])

      spread = best_ask - best_bid

      if spread >= 0:
         values["best_bid"] = float(best_bid)
         values["best_ask"] = float(best_ask)
         values["spread"] = float(spread)

      for levels in self.imbalance_levels:
         bid_volume = sum(float(level["size"])
               for level in bids[:levels])

         ask_volume = sum(float(level["size"])
               for level in asks[:levels])

         total_volume = bid_volume + ask_volume

         if total_volume <= 0:
            continue

         values[f"bid_volume_top_{levels}"] = float(bid_volume)
         values[f"ask_volume_top_{levels}"] = float(ask_volume)
         values[f"imbalance_top_{levels}"] = float((bid_volume - ask_volume) / total_volume)

         if ask_volume > 0:
            values[f"depth_ratio_top_{levels}"] = float(bid_volume / ask_volume)

   def _add_binance_features(self, snapshot: MarketSnapshot, values: dict[str, float]):
      current_binance_price = snapshot.crypto_price

      if (current_binance_price is None or current_binance_price <= 0):
         return

      values["binance_price"] = float(current_binance_price)

      for lookback_ms in self.binance_lookbacks_ms:
         past_snapshot = self._lookup_past_snapshot(
               current_timestamp=snapshot.timestamp,
               lookback_ms=lookback_ms,
         )

         if past_snapshot is None:
               continue

         past_binance_price = past_snapshot.crypto_price
         if (past_binance_price is None or past_binance_price <= 0):
               continue

         simple_return = (current_binance_price - past_binance_price) / past_binance_price
         absolute_change = (current_binance_price - past_binance_price)

         values[f"binance_return_{lookback_ms}"] = float(simple_return)
         values[f"binance_change_{lookback_ms}"] = float(absolute_change)


      short_return = values.get("binance_return_1000")
      long_return = values.get("binance_return_5000")
      #print(short_return)
      if short_return is not None and long_return is not None:
         values["binance_acceleration_1s_5s"] = (
            short_return - long_return
         )

      self.add_crypto_range_features(snapshot=snapshot, 
                                     current_price=current_binance_price,
                                     values=values)
      self._add_crypto_volatility_features(
         snapshot=snapshot,
         values=values,
      )

   def _crypto_observations_in_window(self, current_timestamp: int,
      window_ms: int) -> list[tuple[int, float]]:
      start_timestamp = current_timestamp - window_ms
      observations: list[tuple[int, float]] = []

      for historical_snapshot in self.past_snapshots:
         if historical_snapshot.timestamp < start_timestamp:
               continue

         if historical_snapshot.timestamp > current_timestamp:
               break

         price = historical_snapshot.crypto_price
         if price is None or price <= 0:
               continue

         observations.append((historical_snapshot.timestamp, float(price)))
               
      return observations




   def _add_crypto_volatility_features(self, snapshot: MarketSnapshot,
      values: dict[str, float]) -> None:
      for window_ms in self.binance_volatility_windows_ms:
         observations = self._crypto_observations_in_window(
               current_timestamp=snapshot.timestamp,
               window_ms=window_ms)

         # at least three prices needed for two changes
         if len(observations) < 3:
               continue

         prices = [price for _, price in observations]

         absolute_changes = [
               prices[index] - prices[index - 1]
               for index in range(1, len(prices))
         ]

         returns = [
               (
                  prices[index] - prices[index - 1]
               ) / prices[index - 1]
               for index in range(1, len(prices))
         ]
         #print(len(absolute_changes))
         if len(absolute_changes) >= 2:
               values[
                  f"binance_change_volatility_{window_ms}"
               ] = float(
                  statistics.stdev(absolute_changes)
               )

               values[
                  f"binance_return_volatility_{window_ms}"
               ] = float(
                  statistics.stdev(returns)
               )
      

   def add_crypto_range_features(self, snapshot:MarketSnapshot, current_price:float,
         values: dict[str, float]):
      for window_ms in self.crypto_range_windows_ms:
         prices = self._crypto_prices_in_window(
               current_timestamp=snapshot.timestamp,
               window_ms=window_ms,
         )
         if not prices:
               continue

         recent_high = max(prices)
         recent_low = min(prices)
         values[f"binance_recent_high_{window_ms}"] = float(recent_high)
         values[f"binance_recent_low_{window_ms}"] = float(recent_low)
         # values[f"binance_recent_high_distance_{window_ms}"
         #    ] = float(current_price - recent_high)
         # values[f"binance_recent_low_distance_{window_ms}"
         #    ] = float(current_price - recent_low)
         if recent_high > 0:
            values[f"binance_relative_high_distance_{window_ms}"
            ] = float((current_price - recent_high) / recent_high)
         
         if recent_low > 0:
            values[f"binance_relative_low_distance_{window_ms}"
            ] = float((current_price - recent_low) / recent_low)

         recent_range = recent_high - recent_low
         if recent_range > 0:
               values[f"binance_range_position_{window_ms}"
               ] = float((current_price - recent_low) / recent_range)

   def _crypto_prices_in_window(self, current_timestamp: int,
      window_ms: int,) -> list[float]:

      start_timestamp = current_timestamp - window_ms
      prices: list[float] = []

      for historical_snapshot in self.past_snapshots:
         if historical_snapshot.timestamp < start_timestamp:
               continue

         if historical_snapshot.timestamp > current_timestamp:
               break

         price = historical_snapshot.crypto_price
         if price is None or price <= 0:
               continue

         prices.append(float(price))

      return prices


   def _add_market_context_features(self, snapshot: MarketSnapshot, values: dict[str, float]):
      binance_price = snapshot.crypto_price
      price_to_beat = snapshot.price_to_beat

      if (binance_price is not None and price_to_beat is not None):
         distance = binance_price - price_to_beat

         values["distance_to_price_to_beat"] = float(distance)

         if price_to_beat > 0:
               values["relative_distance_to_price_to_beat"] = float(distance / price_to_beat)

      remaining_ms = snapshot.time_to_end_ms

      if remaining_ms is not None:
         values["seconds_remaining"] = remaining_ms / 1000.0

   def _lookup_past_snapshot(self, current_timestamp: int, lookback_ms: int,):
      requested_timestamp = current_timestamp - lookback_ms

      candidate = self._find_snapshot_at_or_before(requested_timestamp)
      if candidate is None:
         return None

      lookup_delay_ms = requested_timestamp - candidate.timestamp
      if lookup_delay_ms < 0:
         return None

      if (self.max_lookup_delay_ms is not None
            and lookup_delay_ms > self.max_lookup_delay_ms):
         return None

      return candidate
   

   def _find_snapshot_at_or_before(self, target_timestamp: int) -> MarketSnapshot | None:
      candidate: MarketSnapshot | None = None

      for snapshot in self.past_snapshots:
         if snapshot.timestamp <= target_timestamp:
               candidate = snapshot
         else:
               break

      return candidate
   
   # Keep the newest observation at or before the oldest requested timestamp
   def _remove_old_snapshots(self, oldest_required_timestamp: int):
      
      while (len(self.past_snapshots) >= 2
            and self.past_snapshots[1].timestamp <= oldest_required_timestamp):
         self.past_snapshots.popleft()

   def _validate_snapshot(self, snapshot: MarketSnapshot):
      midpoint = snapshot.up_book.midpoint

      if midpoint is None:
         raise ValueError("Snapshot midpoint cannot be None.")

      if not 0.0 <= midpoint <= 1.0:
         raise ValueError(f"Midpoint must be between 0 and 1, got {midpoint}.")

      #if (self.past_snapshots
            #and snapshot.timestamp < self.past_snapshots[-1].timestamp):
      if (self.past_snapshots
            and self.past_snapshots[-1].timestamp - snapshot.timestamp > 80):
         print(snapshot.timestamp)
         print(self.past_snapshots[-1].timestamp)
         raise ValueError("Snapshots must arrive in chronological order.")


      