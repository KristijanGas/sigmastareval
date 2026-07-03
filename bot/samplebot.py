from .masterbot import masterbot
import datetime
from .order_actions import OrderAction
from .order_types import OrderType
import time

class SampleBot(masterbot):

   def run(self):
      if self.market is None or self.data_provider is None:
         raise ValueError("Market and data provider must be set before running the bot.")
      asset_ids = self.data_provider.get_market_asset_ids()
      print(self.data_provider.get_mid_price(asset_ids[0]))
   