import math
from collections import deque

from math import erf, sqrt
import numpy as np

from bot.order_actions import OrderAction
from bot.order_types import OrderType

from bot.masterbot import masterbot
from bot.order_actions import OrderAction
from bot.order_types import OrderType
from bot.prediction_models.polynomial_predictor import polynomial_predictor

class KStrategy(masterbot):
    def __init__(self, in_production=False, market=None, data_provider=None):
        super().__init__(in_production, market, data_provider)
        self.order_library = []
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
        self.past_weighted_trends = deque()
        self.past_trends_windowsize = 20000

        #parameters
        self.time_volatility_alpha = 1000
        self.investment_cash_percent = 0.2
        self.lookahead_time = 0
        self.trend_alpha = 1
        self.edge_treshold = 0.05
        self.crypto_price_stdev = {"bitcoin-up-or-down": 320, "ethereum-up-or-down": 10.4, "solana-up-or-down": 0.65, "xrp-up-or-down": 0.007}  # Example values for standard deviation of crypto prices

    def first_run_setup(self):
        super().first_run_setup()
        self.predictor = polynomial_predictor()
        self.past_weighted_trends.clear()
        self.predictor.price_to_beat = self.price_to_beat
    
    def place_order_with_cash_check(self, order_type, token_id, order_action, order_size, price, timeout):
        if order_size < 5:
            return False
        usable_cash = self.get_usable_cash()
        if order_action == OrderAction.BID:
            required_cash = order_size * price
            if required_cash > usable_cash:
                #print(f"Not enough usable cash to place the order. Required: {required_cash}, Usable: {usable_cash}")
                return False
        timeout = None if timeout is None else timeout + self.data_provider.get_current_timestamp()
        self.market.place_order(
            order_type,
            token_id,
            order_action,
            order_size,
            price,
            timeout=timeout,
        )
        self.update_cash_reservations()
        return True
    
    def get_usable_cash(self):
        return self.market.get_user_cash() - self.unusable_cash - self.money_reserved_for_up - self.money_reserved_for_down
    
    def update_past_trends(self, new_trend, current_timestamp):
        self.past_weighted_trends.append({"timestamp": current_timestamp, "trend": new_trend})
        while self.past_weighted_trends[0]["timestamp"] + self.past_trends_windowsize < current_timestamp:
            self.past_weighted_trends.popleft()
        
    def manage_desired_inventory(self, wanted_up_shares, wanted_down_shares, projected_up_value=None, projected_down_value=None):
        dif_up_shares = wanted_up_shares - self.up_shares
        dif_down_shares = wanted_down_shares - self.down_shares
        if dif_up_shares > 0:
            dif_up_shares = min(dif_up_shares, self.data_provider.can_buy_with(self.up_token_id, self.get_usable_cash()))
            self.place_order_with_cash_check(OrderType.GTD, self.up_token_id, OrderAction.BID, dif_up_shares, projected_up_value, timeout=1000)
        if dif_down_shares > 0:
            dif_down_shares = min(dif_down_shares, self.data_provider.can_buy_with(self.down_token_id, self.get_usable_cash()))
            self.place_order_with_cash_check(OrderType.GTD, self.down_token_id, OrderAction.BID, dif_down_shares, projected_down_value, timeout=1000)
        if dif_up_shares < 0:
            self.place_order_with_cash_check(OrderType.GTD, self.up_token_id, OrderAction.ASK, -dif_up_shares, max(projected_up_value,0.01), timeout=1000)
        if dif_down_shares < 0:
            self.place_order_with_cash_check(OrderType.GTD, self.down_token_id, OrderAction.ASK, -dif_down_shares, max(projected_down_value,0.01), timeout=1000)

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


    def run(self):
        order_book = self.data_provider.get_order_book()
        self.order_library.append(order_book)
        self.update_cash_reservations()
        crypto_value = self.data_provider.get_crypto_value()
        current_timestamp = self.data_provider.get_current_timestamp()
        self.predictor.update_past_crypto_values(crypto_value, current_timestamp, self.data_provider.get_end_timestamp())
        self.up_shares = self.market.get_user_holdings().get(self.up_token_id, 0)
        self.down_shares = self.market.get_user_holdings().get(self.down_token_id, 0)
        
        up_price = self.data_provider.get_mid_price(self.up_token_id)
        down_price = self.data_provider.get_mid_price(self.down_token_id)

        time_remaining = (self.data_provider.get_end_timestamp() -current_timestamp) / 1000.0
        time_factor = (1 - (self.time_volatility_alpha / (time_remaining + self.time_volatility_alpha)))

        predicted_trend = self.predictor.predict_trend(
            self.lookahead_time,
            current_timestamp, 
            self.data_provider.get_end_timestamp(), 
            self.crypto_price_stdev[self.market.base_name],
            crypto_value
            )
        if time_factor == 0:
            time_factor = 0.0000001
        current_updown_value = (crypto_value - self.price_to_beat) / self.crypto_price_stdev.get(self.market.base_name)
        current_updown_value /= (time_factor)**2
        projected_up_value = 0.5 * (1 + erf((predicted_trend + current_updown_value) / sqrt(2)))
        projected_down_value = 1 - projected_up_value
        self.past_crypto_predictions.append({"timestamp": self.data_provider.get_current_timestamp(),
                                              "up_prediction": projected_up_value,
                                              "down_prediction": projected_down_value})
        
        edge = projected_up_value - up_price
        #desired_shares = (edge * 100)**2 * time_factor
        desired_shares = 20
        if edge > self.edge_treshold:
            self.manage_desired_inventory(desired_shares, 0, projected_up_value, projected_down_value)
        elif edge < -self.edge_treshold:
            self.manage_desired_inventory(0, desired_shares, projected_up_value, projected_down_value)