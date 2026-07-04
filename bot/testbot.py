from .masterbot import masterbot
import datetime
from .order_actions import OrderAction
from .order_types import OrderType
import time
from bot.order_actions import OrderAction
from bot.order_types import OrderType

class SampleBot(masterbot):

    def __init__(self, in_production = False, market = None, data_provider = None):
      super().__init__(in_production, market, data_provider)
      self.once = 0
    def _estimated_fee(self, price, size):
        if self.market is None:
            return 0.0
        fee_rate = float(getattr(self.market, "fee_percent", 0.0))
        return size * price * (1 - price) * fee_rate
    
    def run(self):
      asset_ids = self.data_provider.get_market_asset_ids()
      for asset_id in asset_ids:
        best_bid = self.data_provider.get_best_bid(asset_id)
        best_ask = self.data_provider.get_best_ask(asset_id)
        mid_price = self.data_provider.get_mid_price(asset_id)
        spread = self.data_provider.get_spread(asset_id)
        if best_bid is not None and best_bid < 0.2 and best_bid > 0.05:
            #print(self.market.get_asset_orders(asset_id))
            if self.market.get_asset_orders(asset_id, OrderAction.BID) == []:
                self.market.place_order(OrderType.GTC, asset_id, OrderAction.BID, 100, best_bid, None)
        if best_bid is not None and best_bid > 0.8 and best_bid < 0.95:
            #print(self.market.get_asset_orders(asset_id))
            if self.market.get_asset_orders(asset_id, OrderAction.ASK) == []:
                self.market.place_order(OrderType.GTC, asset_id, OrderAction.ASK, 100, best_bid, None)