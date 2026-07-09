import math
from collections import deque

from math import erf, sqrt
import numpy as np

from bot.order_actions import OrderAction
from bot.order_types import OrderType

from bot.masterbot import masterbot
from bot.order_actions import OrderAction
from bot.order_types import OrderType

class KStrategy(masterbot):
    def __init__(self, in_production=False, market=None, data_provider=None):
        super().__init__(in_production, market, data_provider)
        self.order_library = []
        self.first_run = True
        self.starting_cash = None
        self.clob_token_ids = None
        self.unusable_cash = 0.0
        self.price_to_beat = None
        self.up_token_id = None
        self.down_token_id = None
        self.money_reserved_for_up = 0.0
        self.money_reserved_for_down = 0.0
        self.up_shares = 0.0
        self.down_shares = 0.0
        self.past_crypto_predictions = []

        #parameters
        self.time_volatility_alpha = 500
        self.past_window_size = 30 * 1000 # 5 seconds
        self.polynomial_degree = 2
        self.investment_cash_percent = 0.1
        self.lookahead_time = 500
        self.trend_alpha = 1
        self.price_difference_threshold = 0.05
        self.crypto_price_stdev = {"bitcoin-up-or-down": 50, "ethereum-up-or-down": 1.5, "solana-up-or-down": 0.0664, "xrp-up-or-down": 0.00164}  # Example values for standard deviation of crypto prices

    
    def get_usable_cash(self):
        return self.market.get_user_cash() - self.unusable_cash
    
    def first_run_setup(self):
            self.starting_cash = self.market.get_user_cash()
            self.unusable_cash = self.starting_cash * (1-self.investment_cash_percent)
            self.clob_token_ids = self.data_provider.get_market_asset_ids()
            self.price_to_beat = self.data_provider.get_price_to_beat()
            self.up_token_id = self.data_provider.get_up_token_id()
            self.down_token_id = self.data_provider.get_down_token_id()
            self.past_crypto_values = deque()
            self.past_crypto_rel_timestamps = deque()
            self.first_run = False
            self.past_crypto_predictions.clear()
    def actual_value(self, time_volatility, percentage_towards):
        return percentage_towards * time_volatility

    def update_cash_reservations(self):
        orders = self.market.get_asset_orders(self.up_token_id, OrderAction.BID)
        self.money_reserved_for_up = 0.0
        for order in orders:
            order_size = order["order_size"]
            price = order["price"]
            self.money_reserved_for_up += order_size * price

        orders = self.market.get_asset_orders(self.down_token_id, OrderAction.BID)
        self.money_reserved_for_down = 0.0
        for order in orders:
            order_size = order["order_size"]
            price = order["price"]
            self.money_reserved_for_down += order_size * price

    def print_dequque(self, dq):
        print("Deque contents:")
        for item in dq:
            print(item)

    def update_past_crypto_values(self):
        current_timestamp = (self.data_provider.get_current_timestamp() - self.data_provider.get_end_timestamp()) # Convert to seconds
        #print(f"Current timestamp: {current_timestamp}, Past crypto timestamps: {list(self.past_crypto_rel_timestamps)}, Past crypto values: {list(self.past_crypto_values)}")
        self.past_crypto_rel_timestamps.append(current_timestamp)
        self.past_crypto_values.append(self.data_provider.get_crypto_value())
        # Remove old values outside the past window size
        #print(len(self.past_crypto_rel_timestamps), len(self.past_crypto_values))
        while self.past_crypto_rel_timestamps and (current_timestamp - self.past_window_size) > self.past_crypto_rel_timestamps[0]:
            self.past_crypto_rel_timestamps.popleft()
            self.past_crypto_values.popleft()

    def predict_future_crypto_value(self, future_timestamp):
        scaled_timestamps = []
        relative_crypto_values = []
        for x in self.past_crypto_rel_timestamps:
            scaled_timestamps.append(round((x - self.past_crypto_rel_timestamps[0]) / 1000.0, 6))  # Scale timestamps to seconds
        future_timestamp = (future_timestamp - self.past_crypto_rel_timestamps[0]) / 1000.0  # Scale future difference to seconds
        future_timestamp = round(future_timestamp, 6)
        for y in self.past_crypto_values:
            relative_crypto_values.append(round(y - self.price_to_beat, 6))
        #print(f"Scaled timestamps: {scaled_timestamps}, Relative crypto values: {relative_crypto_values}")

        coefficients = np.polyfit(scaled_timestamps, relative_crypto_values, self.polynomial_degree)
        prediction = np.polyval(coefficients, future_timestamp)
        #print(f"Predicted future crypto value at timestamp {future_timestamp}: {prediction}")
        return prediction

    def run(self):
        
        order_book = self.data_provider.get_order_book()
        self.order_library.append(order_book)
        if self.first_run:
            self.first_run_setup()

        self.update_cash_reservations()
        self.update_past_crypto_values()
        if len(self.past_crypto_rel_timestamps) < 10:
            return  # Not enough data to make predictions yet
        self.up_shares = self.market.get_user_holdings().get(self.up_token_id, 0)
        self.down_shares = self.market.get_user_holdings().get(self.down_token_id, 0)
        
        up_price = self.data_provider.get_mid_price(self.up_token_id)
        down_price = self.data_provider.get_mid_price(self.down_token_id)

        time_remaining = (self.data_provider.get_end_timestamp() - self.data_provider.get_current_timestamp()) / 1000.0
        time_factor = (1 - (self.time_volatility_alpha / (time_remaining + self.time_volatility_alpha)))
        #print(f"Time remaining: {time_remaining:.2f} seconds, Time volatility: {time_volatility:.6f}")
        if time_remaining <= 0:
            time_factor = 0.00001
        crypto_current_stdev = (self.past_crypto_values[-1] - self.price_to_beat) / self.crypto_price_stdev.get(self.market.base_name)
        crypto_current_stdev /= time_factor

        current_rel_timestamp = (self.data_provider.get_current_timestamp() - self.data_provider.get_end_timestamp())

        lookahead_timestamp = self.lookahead_time  + current_rel_timestamp # 5 minutes in milliseconds
        crypto_prediction = self.predict_future_crypto_value(lookahead_timestamp)
        self.past_crypto_predictions.append({"timestamp": self.data_provider.get_current_timestamp() + self.lookahead_time, "prediction": crypto_prediction})

        crypto_trend_stdev = crypto_prediction / self.crypto_price_stdev.get(self.market.base_name)
        #print(f"Crypto trend stdev: {crypto_trend_stdev:.6f}")
        final_crypto_estimate = crypto_current_stdev + crypto_trend_stdev * self.trend_alpha

        projected_value_up = 0.5 * (1 + erf(final_crypto_estimate / sqrt(2)))
        projected_value_down = 1 - projected_value_up
        #print(f"Crypto current stdev: {crypto_current_stdev:.6f}")

        #print(f"Projected value up: {projected_value_up:.6f}, Price up: {up_price:.6f}, Projected value down: {projected_value_down:.6f}, Price down: {down_price:.6f}, Time left: {time_remaining:.2f} seconds", "time_factor", time_factor)

        
        if projected_value_up > up_price + self.price_difference_threshold:
            if self.market.get_asset_orders(self.up_token_id, OrderAction.BID) == []:
                self.market.place_order(
                    OrderType.GTD,
                    self.up_token_id,
                    OrderAction.BID,
                    5,
                    up_price,
                    timeout=self.data_provider.get_current_timestamp() + 1000 * 60,
                )
        if projected_value_down > down_price + self.price_difference_threshold:
            if self.market.get_asset_orders(self.down_token_id, OrderAction.BID) == []:
                self.market.place_order(
                    OrderType.GTD,
                    self.down_token_id,
                    OrderAction.BID,
                    5,
                down_price,
                timeout=self.data_provider.get_current_timestamp() + 1000 * 60,
            )
        if projected_value_up < up_price and self.up_shares > 5:
            self.market.place_order(
                OrderType.GTD,
                self.up_token_id,
                OrderAction.ASK,
                self.up_shares,
                max(projected_value_up, up_price),
                timeout=self.data_provider.get_current_timestamp() + 1000 * 60,
            )
        if projected_value_down < down_price and self.down_shares > 5:
            self.market.place_order(
                OrderType.GTD,
                self.down_token_id,
                OrderAction.ASK,
                self.down_shares,
                max(projected_value_down, down_price),
                timeout=self.data_provider.get_current_timestamp() + 1000 * 60,
            )
        


        



