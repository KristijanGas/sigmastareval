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
   def run(self):
      if self.market is None or self.data_provider is None:
         raise ValueError("Market and data provider must be set before running the bot.")
      asset_ids = self.data_provider.get_market_asset_ids()
      if self.once == 0:
         self.once = 1
         self.market.place_order(OrderType.GTC, asset_ids[1], OrderAction.BID, 100, 0.7, None)