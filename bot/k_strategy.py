import math
from collections import deque

from math import erf, sqrt
import numpy as np
import time

from bot.order_actions import OrderAction
from bot.order_types import OrderType

from bot.masterbot import masterbot
from bot.order_actions import OrderAction
from bot.order_types import OrderType
from bot.prediction_models.polynomial_predictor import polynomial_predictor
from data_provider.historical_provider import historical_provider

# from evaluator.prediction_evaluator.snapshot_builder import create_snapshot
# from bot.prediction_models.gradient_boosting_predictor import initialize_predictor

class KStrategy(masterbot):
    def __init__(self, in_production=False, market=None, data_provider: historical_provider = None):
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
        self.trend_alpha = 1.0
        self.first_different_estimate_timestamp = None
        self.estimation_direction = 0
        self.predictor = None
        self.prob_predictor = None
        self.last_logged_timestamp = None
        self.predictor = polynomial_predictor()

        #parameters
        self.investment_cash_percent = 0.2
        # rest come from config loading
        self.time_volatility_alpha = None
        self.correction_treshold = None
        self.correction_time_window = None
        self.lookahead_time = None
        self.edge_threshold = None
        self.crypto_price_stdev = None

    def first_run_setup(self):
        super().first_run_setup()
        self.predictor = polynomial_predictor()

        # uncomment if using probability predictor
        # if self.prob_predictor is None:
        #     self.prob_predictor = initialize_predictor(market_name=self.market.base_name,
        #                                     lookahead_time=self.lookahead_time)
        # else:
        #     self.prob_predictor.reset()

        self.predictor.price_to_beat = self.price_to_beat
        self.trend_alpha = 1.0
    
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
        
    def manage_desired_inventory(self, wanted_up_shares, wanted_down_shares, projected_up_value=None, projected_down_value=None):
        dif_up_shares = wanted_up_shares - self.up_shares
        dif_down_shares = wanted_down_shares - self.down_shares
        if dif_up_shares > 0:
            dif_up_shares = min(dif_up_shares, self.data_provider.can_buy_with(self.up_token_id, self.get_usable_cash()))
            self.place_order_with_cash_check(OrderType.GTD, self.up_token_id, OrderAction.BID, dif_up_shares, self.up_price + 0.03, timeout=1000)
        if dif_down_shares > 0:
            dif_down_shares = min(dif_down_shares, self.data_provider.can_buy_with(self.down_token_id, self.get_usable_cash()))
            self.place_order_with_cash_check(OrderType.GTD, self.down_token_id, OrderAction.BID, dif_down_shares, self.down_price + 0.03, timeout=1000)
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

    def update_estimation_alpha(self, current_timestamp, up_price, projected_up_value):
        up_from_mid = abs(0.5 - up_price)
        projected_up_from_mid = abs(0.5 - projected_up_value)
        difference = projected_up_from_mid - up_from_mid

        if abs(difference) > self.correction_treshold:
            if difference > self.correction_treshold:
                if self.estimation_direction != 1:
                    self.first_different_estimate_timestamp = current_timestamp
                self.estimation_direction = 1
                
            elif difference < -self.correction_treshold:
                if self.estimation_direction != -1:
                    self.first_different_estimate_timestamp = current_timestamp
                self.estimation_direction = -1
        else:
            self.estimation_direction = 0
            self.first_different_estimate_timestamp = None
        
        if self.first_different_estimate_timestamp is not None and (current_timestamp - self.first_different_estimate_timestamp) > self.correction_time_window:
            #print(f"Consistent estimation difference detected. Adjusting trend_alpha. Current trend_alpha: {self.trend_alpha}, Estimation direction: {self.estimation_direction}")
            if self.estimation_direction == 1:
                self.trend_alpha *= 1.1
            elif self.estimation_direction == -1:
                self.trend_alpha *= 0.9
            #print(f"Updated trend_alpha to {self.trend_alpha} based on consistent estimation difference.")
            self.trend_alpha = max(0.1, min(self.trend_alpha, 10.0))
            self.first_different_estimate_timestamp = current_timestamp

    def estimate_share_value(self, crypto_value, time_factor, predicted_trend):
        current_updown_value = (crypto_value - self.price_to_beat) / (self.crypto_price_stdev * self.trend_alpha)
        current_updown_value /= (time_factor)**2
        projected_up_value = 0.5 * (1 + erf((predicted_trend + current_updown_value) / sqrt(2)))
        projected_down_value = 1 - projected_up_value
        return projected_up_value, projected_down_value

    def run(self):
        order_book = self.data_provider.get_order_book()
        if order_book is None:
            print("Order book is None. Cannot proceed with strategy.")
            return False
        crypto_value = self.data_provider.get_crypto_value()
        if crypto_value is None:
            print("Crypto value is None. Cannot proceed with strategy.")
            return False
        self.price_to_beat = self.data_provider.get_price_to_beat()
        if self.price_to_beat is None:
            print("Price to beat is None. Cannot proceed with strategy.")
            return False
        if self.data_provider.get_end_timestamp() is None:
            print("End timestamp is None. Cannot proceed with strategy.")
            return False
        if self.data_provider.get_market_asset_ids() is None or len(self.data_provider.get_market_asset_ids()) < 2:
            print("Market asset IDs are None or insufficient. Cannot proceed with strategy.")
            return False
        self.up_token_id = self.data_provider.get_up_token_id()
        self.down_token_id = self.data_provider.get_down_token_id()
        self.update_cash_reservations()
        current_timestamp = self.data_provider.get_current_timestamp()
        #self.predictor.update_past_crypto_values(crypto_value, current_timestamp, self.data_provider.get_end_timestamp())
        self.up_shares = self.market.get_user_holdings().get(self.up_token_id, 0)
        self.down_shares = self.market.get_user_holdings().get(self.down_token_id, 0)
        try:
            self.up_price = self.data_provider.get_mid_price(self.up_token_id)
            self.down_price = self.data_provider.get_mid_price(self.down_token_id)
        except Exception as e:
            print(f"Error fetching mid price: {e}")
            return False

        time_remaining = (self.data_provider.get_end_timestamp() -current_timestamp) / 1000.0
        time_factor = (1 - (self.time_volatility_alpha / (time_remaining + self.time_volatility_alpha)))
        predicted_trend = 0.0
        '''
        predicted_trend = self.predictor.predict_trend(
            self.lookahead_time,
            current_timestamp, 
            self.data_provider.get_end_timestamp(), 
            self.crypto_price_stdev,
            crypto_value
            )
        '''
        #print(predicted_trend)

        #uncomment this if using probability prediction
        # snapshot = create_snapshot(self.data_provider)
        # self.prob_predictor.update(snapshot=snapshot)
        # predicted_prob = self.prob_predictor.predict_up_probability(snapshot=snapshot)


        
        if time_factor < 0.01:
            time_factor = 0.01
        projected_up_value, projected_down_value = self.estimate_share_value(crypto_value, time_factor, predicted_trend)
        moving_mean = self.data_provider.get_moving_mean()
        if self.last_logged_timestamp is None or current_timestamp - self.last_logged_timestamp >= 20:
            self.past_crypto_predictions.append({"timestamp": current_timestamp,
                                                "up_prediction": projected_up_value,
                                                "down_prediction": projected_down_value,
                                                "moving_mean": moving_mean
                                                })
            self.data_provider.set_fair_value_up(projected_up_value)
            self.data_provider.set_fair_value_down(projected_down_value)
            self.last_logged_timestamp = current_timestamp

        edge_up = projected_up_value - self.up_price
        edge_down = projected_down_value - self.down_price
        desired_shares = int(self.get_usable_cash() / 20) * 5
        #desired_shares = min(desired_shares, self.data_provider.can_buy_with(self.up_token_id, self.get_usable_cash()))
        #desired_shares = min(desired_shares, self.data_provider.can_buy_with(self.down_token_id, self.get_usable_cash()))
        desired_shares = max(desired_shares, 5)
        if edge_up > self.edge_threshold * (1 + 2 * time_factor):
            self.manage_desired_inventory(desired_shares, 0, projected_up_value, projected_down_value)
        elif edge_down > self.edge_threshold * (1 + 2 * time_factor):
            self.manage_desired_inventory(0, desired_shares, projected_up_value, projected_down_value)
        self.update_estimation_alpha(current_timestamp, self.up_price, projected_up_value)

        return True