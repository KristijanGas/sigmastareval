import math
from collections import deque

from bot.masterbot import masterbot
from bot.order_actions import OrderAction
from bot.order_types import OrderType


class ProfitBot(masterbot):
	def __init__(self, in_production=False, market=None, data_provider=None):
		super().__init__(in_production, market, data_provider)
		self.crypto_window = 24
		self.mid_window = 32
		self.max_inventory = 20.0
		self.min_trade_size = 5.0
		self.max_trade_size = 5.0
		self.crypto_scale = 300.0
		self.reversion_scale = 2.0
		self.requote_delta = 0.02
		self.entry_threshold = 0.12
		self.crypto_prices = deque(maxlen=self.crypto_window)
		self.asset_mid_history = {}
		self._last_timestamp = None
		self._last_asset_ids = None
		self._last_price_to_beat = None

	def _reset_state(self):
		self.crypto_prices.clear()
		self.asset_mid_history.clear()
		self._last_timestamp = None
		self._last_asset_ids = None
		self._last_price_to_beat = None

	def _clamp(self, value, low, high):
		return max(low, min(high, value))

	def _mean(self, values):
		if not values:
			return 0.0
		return sum(values) / len(values)

	def _std(self, values):
		if len(values) < 2:
			return 0.0
		mean_value = self._mean(values)
		variance = sum((value - mean_value) ** 2 for value in values) / len(values)
		return math.sqrt(variance)

	def _round_to_tick(self, price, tick_size):
		tick_size = max(float(tick_size), 0.01)
		rounded = round(round(price / tick_size) * tick_size, 2)
		return max(0.01, min(0.99, rounded))

	def _normalize_size(self, desired_size, minimum_size):
		if desired_size < minimum_size:
			return 0.0
		steps = math.floor(desired_size / minimum_size)
		return round(steps * minimum_size, 8)

	def _cancel_orders(self, asset_id, order_action):
		if self.market is None:
			return
		for order in list(self.market.get_asset_orders(asset_id, order_action)):
			self.market.cancel_order(order["order_id"])

	def _current_mid(self, asset_id):
		mid_price = self.data_provider.get_mid_price(asset_id)
		if mid_price is None:
			return None
		history = self.asset_mid_history.setdefault(asset_id, deque(maxlen=self.mid_window))
		history.append(float(mid_price))
		return float(mid_price)

	def _target_size(self, score, minimum_size):
		normalized = self._clamp(score, 0.0, 1.0)
		desired = self.max_inventory * normalized
		desired = min(desired, self.max_trade_size)
		return self._normalize_size(desired, minimum_size)

	def _sync_order(self, asset_id, order_action, price, desired_size, minimum_size, tick_size):
		existing_orders = list(self.market.get_asset_orders(asset_id, order_action))
		if desired_size < minimum_size:
			if existing_orders:
				self._cancel_orders(asset_id, order_action)
			return

		desired_price = self._round_to_tick(price, tick_size)
		if existing_orders:
			current_order = max(existing_orders, key=lambda order: order["order_id"])
			current_price = float(current_order["price"])
			current_size = float(current_order["order_size"])
			if (
				len(existing_orders) == 1
				and abs(current_price - desired_price) <= self.requote_delta
				and current_size <= desired_size
			):
				return
			self._cancel_orders(asset_id, order_action)

		self.market.place_order(OrderType.GTC, asset_id, order_action, desired_size, desired_price, None)
    
    def run(self):

        if self.market is None or self.data_provider is None:                                                                                                                         
            raise ValueError("Market and data provider must be set before running the bot.")                                                                                          
                                                                                                                                                                                      
        asset_ids = self.data_provider.get_market_asset_ids()                                                                                                                         
        if not asset_ids:                                                                                                                                                             
            return                                                                                                                                                                    
                                                                                                                                                                                      
        current_timestamp = self.data_provider.get_current_timestamp()                                                                                                                
        asset_signature = tuple(asset_ids)                                                                                                                                            
        if (                                                                                                                                                                          
            self._last_timestamp is not None                                                                                                                                          
            and current_timestamp < self._last_timestamp                                                                                                                              
        ) or (                                                                                                                                                                        
            self._last_asset_ids is not None                                                                                                                                          
            and asset_signature != self._last_asset_ids                                                                                                                               
        ):                                                                                                                                                                            
            self._reset_state()                                                                                                                                                       
                                                                                                                                                                                      
        self._last_timestamp = current_timestamp                                                                                                                                      
        self._last_asset_ids = asset_signature                                                                                                                                        
                                                                                                                                                                                      
        crypto_price = float(self.get_crypto_value())                                                                                                                                 
        price_to_beat = float(self.data_provider.get_price_to_beat())                                                                                                                 
        if self._last_price_to_beat is not None and abs(price_to_beat - self._last_price_to_beat) > 1e-9:                                                                             
            self._reset_state()                                                                                                                                                       
        self._last_price_to_beat = price_to_beat                                                                                                                                      
        self.crypto_prices.append(crypto_price)                                                                                                                                       
        crypto_history = list(self.crypto_prices)                                                                                                                                     
        crypto_mean = self._mean(crypto_history)                                                                                                                                      
        crypto_std = self._std(crypto_history)                                                                                                                                        
        if crypto_std <= 0:                                                                                                                                                           
            crypto_std = max(50.0, self.crypto_scale / 4.0)                                                                                                                           
        crypto_reversion = (crypto_mean - crypto_price) / (crypto_std * 1.5)                                                                                                          
        crypto_reversion = self._clamp(crypto_reversion, -1.0, 1.0)                                                                                                                   
                                                                                                                                                                                      
        mid_by_asset = {}                                                                                                                                                             
        for asset_id in asset_ids:                                                                                                                                                    
            mid_price = self._current_mid(asset_id)                                                                                                                                   
            if mid_price is not None:                                                                                                                                                 
                mid_by_asset[asset_id] = mid_price                                                                                                                                    
                                                                                                                                                                                      
        if len(mid_by_asset) < 2:                                                                                                                                                     
            return                                                                                                                                                                    
                                                                                                                                                                                      
        ordered_assets = sorted(mid_by_asset.items(), key=lambda item: item[1])                                                                                                       
        lower_asset_id, lower_mid = ordered_assets[0]                                                                                                                                 
        upper_asset_id, upper_mid = ordered_assets[-1]                                                                                                                                
                                                                                                                                                                                      
        price_gap = crypto_price - price_to_beat                                                                                                                                      
        direction_confidence = self._clamp(abs(price_gap) / self.crypto_scale, 0.0, 1.0)                                                                                              
                                                                                                                                                                                      
        if abs(price_gap) <= price_to_beat * 0.001:                                                                                                                                   
            favored_asset_id = None                                                                                                                                                   
        elif price_gap > 0:                                                                                                                                                           
            favored_asset_id = upper_asset_id                                                                                                                                         
        else:                                                                                                                                                                         
            favored_asset_id = lower_asset_id                                                                                                                                         
                                                                                                                                                                                      
        holdings = self.market.get_user_holdings()                                                                                                                                    
        asset_positions = {asset_id: float(holdings.get(asset_id, 0.0)) for asset_id in asset_ids}                                                                                    
                                                                                                                                                                                      
        for asset_id in asset_ids:                                                                                                                                                    
            asset = self.data_provider.get_asset(asset_id)                                                                                                                            
            tick_size = float(asset["tick_size"])                                                                                                                                     
            minimum_size = float(asset["min_order_size"])                                                                                                                             
            best_bid = float(self.data_provider.get_best_bid(asset_id))                                                                                                               
            best_ask = float(self.data_provider.get_best_ask(asset_id))                                                                                                               
            mid_price = mid_by_asset[asset_id]                                                                                                                                        
            history = self.asset_mid_history.get(asset_id, deque())                                                                                                                   
            history_values = list(history)                                                                                                                                            
            rolling_mean = self._mean(history_values)                                                                                                                                 
            rolling_std = self._std(history_values)                                                                                                                                   
            if rolling_std <= 0:                                                                                                                                                      
                rolling_std = max(tick_size, 0.02)                                                                                                                                    
                                                                                                                                                                                      
            current_holding = asset_positions[asset_id]                                                                                                                               
            buy_order_size = 0.0                                                                                                                                                      
            sell_order_size = 0.0                                                                                                                                                     
                                                                                                                                                                                      
            if asset_id == favored_asset_id and favored_asset_id is not None:                                                                                                         
                direction_sign = 1.0 if price_gap > 0 else -1.0                                                                                                                       
                signal_score = 0.85 * direction_confidence + direction_sign * crypto_reversion                                                                                        
                if signal_score >= self.entry_threshold:                                                                                                                              
                    desired_size = self._target_size(signal_score, minimum_size)                                                                                                      
                    if desired_size > current_holding:                                                                                                                                
                        buy_order_size = self._normalize_size(desired_size - current_holding, minimum_size)                                                                           
                elif current_holding > 0:                                                                                                                                             
                    buy_order_size = 0.0                                                                                                                                              
            elif current_holding > 0:                                                                                                                                                 
                sell_order_size = self._normalize_size(current_holding, minimum_size)                                                                                                 
                                                                                                                                                                                      
            if buy_order_size > 0:                                                                                                                                                    
                buy_price = max(best_bid, min(best_ask - tick_size, rolling_mean - tick_size))                                                                                        
                if best_ask <= best_bid:                                                                                                                                              
                    buy_price = best_bid                                                                                                                                              
                self._sync_order(asset_id, OrderAction.BID, buy_price, buy_order_size, minimum_size, tick_size)                                                                       
            else:                                                                                                                                                                     
                self._cancel_orders(asset_id, OrderAction.BID)                                                                                                                        
                                                                                                                                                                                      
            if sell_order_size > 0 and current_holding > 0:                                                                                                                           
                sell_price = min(best_ask, max(best_bid + tick_size, rolling_mean + tick_size))                                                                                       
                if best_ask <= best_bid:                                                                                                                                              
                    sell_price = best_ask                                                                                                                                             
                self._sync_order(asset_id, OrderAction.ASK, sell_price, sell_order_size, minimum_size, tick_size)                                                                     
            else:                                                                                                                                                                     
                self._cancel_orders(asset_id, OrderAction.ASK)                                                                                                                        
                                                               