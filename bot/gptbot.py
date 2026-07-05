import math
from collections import deque

from bot.masterbot import masterbot
from bot.order_actions import OrderAction
from bot.order_types import OrderType


class ProfitBot(masterbot):

    def __init__(self, in_production=False, market=None, data_provider=None):
        super().__init__(in_production, market, data_provider)
        self.tick = 0
        self.price_history = deque(maxlen=48)
        self.short_window_size = 5
        self.long_window_size = 20
        self.stop_loss_percentage = 0.97  # 3% stop loss
        self.take_profit_percentage = 1.03  # 3% take profit
        self.asset_ids = None

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
        price_to_beat = max(float(price_to_beat), 1.0)
        relative_delta = (current_price - price_to_beat) / price_to_beat
        price_component = relative_delta * 18.0

        momentum_component = 0.0
        if len(self.price_history) >= 6:
            short_window = list(self.price_history)[-6:]
            long_window = list(self.price_history)
            short_return = (short_window[-1] - short_window[0]) / max(short_window[0], 1.0)
            long_return = (long_window[-1] - long_window[0]) / max(long_window[0], 1.0)
            momentum_component = (8.0 * short_return) + (4.0 * long_return)

        return self._clamp(self._sigmoid(price_component + momentum_component), 0.20, 0.80)

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

    def _calculate_moving_average(self, window_size):
        if len(self.price_history) < window_size:
            return None
        return sum(self.price_history[-window_size:]) / window_size

    def _place_order(self, asset_id, order_action, price):
        min_order_size, tick_size = self._get_asset_limits(asset_id)
        budget = self.data_provider.get_user_cash() * 0.1  # Allocate 10% of cash for each trade
        contract_count = self._normalize_order_size(asset_id, budget / price)

        if contract_count <= 0:
            return

        self.market.place_order(
            OrderType.GTC,
            asset_id,
            order_action,
            contract_count,
            price,
            timeout=None,
        )

    def _manage_existing_orders(self):
        for order in self.market.get_all_orders():
            current_price = self.data_provider.get_mid_price(order["asset_id"])
            if order["order_action"] == OrderAction.BID:
                stop_loss_price = order["price"] * self.stop_loss_percentage
                take_profit_price = order["price"] * self.take_profit_percentage

                if current_price <= stop_loss_price or current_price >= take_profit_price:
                    self.market.cancel_order(order["order_id"])
            elif order["order_action"] == OrderAction.ASK:
                stop_loss_price = order["price"] * self.take_profit_percentage
                take_profit_price = order["price"] * self.stop_loss_percentage

                if current_price >= stop_loss_price or current_price <= take_profit_price:
                    self.market.cancel_order(order["order_id"])


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

        market_data = self._build_market_snapshot(asset_ids[:2])
        if market_data is None:
            return

        current_price_up = market_data[0]["mid_price"]
        current_price_down = market_data[1]["mid_price"]

        self.price_history.append(current_price_up)

        short_ma = self._calculate_moving_average(self.short_window_size)
        long_ma = self._calculate_moving_average(self.long_window_size)

        if short_ma is not None and long_ma is not None:
            if short_ma > long_ma:  # Buy signal
                self._place_order(asset_ids[0], OrderAction.BID, market_data[0]["ask"])
            elif short_ma < long_ma:  # Sell signal
                self._place_order(asset_ids[1], OrderAction.BID, market_data[1]["ask"])

        self._manage_existing_orders()
