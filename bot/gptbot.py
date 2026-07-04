import math
from collections import deque

from bot.masterbot import masterbot
from bot.order_actions import OrderAction
from bot.order_types import OrderType


class ProfitBot(masterbot):

    def __init__(self, in_production=False, market=None, data_provider=None):
        super().__init__(in_production, market, data_provider)
        self.tick = 0
        self.price_history = deque(maxlen=24)
        self.asset_roles = None
        self.initial_price = None

    def _clamp(self, value, minimum, maximum):
        return max(minimum, min(maximum, value))

    def _get_asset_limits(self, asset_id):
        asset = self.data_provider.get_asset(asset_id)
        return float(asset["min_order_size"]), float(asset["tick_size"])

    def _round_down_to_tick(self, value, tick_size):
        if value <= 0:
            return 0.0
        steps = math.floor(value / tick_size + 1e-9)
        return round(steps * tick_size, 10)

    def _normalize_order_size(self, asset_id, size):
        min_order_size, tick_size = self._get_asset_limits(asset_id)
        size = self._round_down_to_tick(size, tick_size)
        if size < min_order_size:
            return 0.0
        return size

    def _estimated_fee(self, price, size):
        if self.market is None:
            return 0.0
        fee_rate = float(getattr(self.market, "fee_percent", 0.0))
        return size * price * (1 - price) * fee_rate

    def _sigmoid(self, value):
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    def _estimate_up_probability(self, current_price, price_to_beat):
        volatility_scale = max(25.0, price_to_beat * 0.00035)
        price_component = (current_price - price_to_beat) / volatility_scale

        momentum_component = 0.0
        if len(self.price_history) >= 6:
            short_window = list(self.price_history)[-6:]
            long_window = list(self.price_history)
            short_slope = short_window[-1] - short_window[0]
            long_slope = long_window[-1] - long_window[0]
            momentum_component = (0.7 * short_slope + 0.3 * long_slope) / max(volatility_scale * 2.0, 1.0)

        return self._clamp(self._sigmoid((1.75 * price_component) + (1.10 * momentum_component)), 0.02, 0.98)

    def _build_market_snapshot(self, asset_ids):
        snapshot = []
        for asset_id in asset_ids:
            bid = self.data_provider.get_best_bid(asset_id)
            ask = self.data_provider.get_best_ask(asset_id)
            if bid is None or ask is None or bid <= 0 or ask <= 0:
                return None

            snapshot.append(
                {
                    "asset_id": asset_id,
                    "bid": bid,
                    "ask": ask,
                    "mid_price": (bid + ask) / 2,
                    "tick_size": float(self.data_provider.get_asset(asset_id)["tick_size"]),
                }
            )

        if len(snapshot) != 2:
            return None
        return snapshot

    def _buy_both_if_underpriced(self, market_data):
        up_asset = market_data[0]
        down_asset = market_data[1]
        ask_sum = up_asset["ask"] + down_asset["ask"]
        fee_buffer = self._estimated_fee(up_asset["ask"], up_asset["tick_size"]) + self._estimated_fee(down_asset["ask"], down_asset["tick_size"])

        if ask_sum + fee_buffer >= 0.985:
            return False

        up_liquidity = self.data_provider.can_buy_with(up_asset["asset_id"], self.data_provider.get_user_cash())
        if up_liquidity < up_asset["tick_size"]:
            return False

        down_liquidity = self.data_provider.can_buy_with(down_asset["asset_id"], self.data_provider.get_user_cash())
        if down_liquidity < down_asset["tick_size"]:
            return False

        budget = self.data_provider.get_user_cash() * 0.20
        if budget < ask_sum:
            return False

        contract_count = min(
            up_asset["tick_size"] * math.floor(up_liquidity / up_asset["tick_size"]),
            down_asset["tick_size"] * math.floor(down_liquidity / down_asset["tick_size"]),
            math.floor(budget / ask_sum),
        )

        contract_count = self._normalize_order_size(up_asset["asset_id"], contract_count)
        if contract_count <= 0:
            return False

        projected_cost = (up_asset["ask"] + down_asset["ask"]) * contract_count
        projected_fee = self._estimated_fee(up_asset["ask"], contract_count) + self._estimated_fee(down_asset["ask"], contract_count)
        if projected_cost + projected_fee > self.data_provider.get_user_cash() * 0.20:
            return False

        self.market.place_order(
            OrderType.FAK,
            up_asset["asset_id"],
            OrderAction.BID,
            contract_count,
            up_asset["ask"],
            None,
        )
        self.market.place_order(
            OrderType.FAK,
            down_asset["asset_id"],
            OrderAction.BID,
            contract_count,
            down_asset["ask"],
            None,
        )
        return True

    def _get_roles(self, asset_ids):
        if self.asset_roles is None or len(self.asset_roles) != 2:
            self.asset_roles = {
                asset_ids[0]: "up",
                asset_ids[1]: "down",
            }
        return self.asset_roles

    def _trend_score(self):
        if self.initial_price is None or len(self.price_history) < 6:
            return 0.0

        current_price = self.price_history[-1]
        short_window = list(self.price_history)[-6:]
        medium_window = list(self.price_history)[-12:] if len(self.price_history) >= 12 else list(self.price_history)

        long_component = (current_price - self.initial_price) / max(self.initial_price, 1.0)
        short_component = (current_price - short_window[0]) / max(short_window[0], 1.0)
        medium_component = (current_price - medium_window[0]) / max(medium_window[0], 1.0)

        return (2.2 * long_component) + (1.4 * short_component) + (1.0 * medium_component)

    def _signal_strength(self):
        if self.initial_price is None or len(self.price_history) < 2:
            return 0.0

        current_price = self.price_history[-1]
        return (current_price - self.initial_price) / max(self.initial_price, 1.0)

    def run(self):
        self.tick += 1

        asset_ids = self.data_provider.get_market_asset_ids()
        if len(asset_ids) < 2:
            return

        current_price = float(self.data_provider.get_crypto_value())
        price_to_beat = float(self.data_provider.get_price_to_beat() or current_price)
        if self.initial_price is None:
            self.initial_price = current_price
        self.price_history.append(current_price)

        market_data = self._build_market_snapshot(asset_ids[:2])
        if market_data is None:
            return

        self._buy_both_if_underpriced(market_data)