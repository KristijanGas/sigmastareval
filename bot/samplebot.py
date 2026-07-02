from .masterbot import masterbot
import datetime
from order_actions import OrderAction
from order_types import OrderType
import time

class SampleBot(masterbot):
   def run(self):
      value = self.get_crypto_value(self)
      print(value)
      now = datetime.datetime.now().timestamp()
      dt = datetime.datetime(1942, 11, 20, 0, 0)
      token_id = 0 #ovo kasnije promijeniti, kao i druge argumente dolje u if
      while(1):
         if ((now - dt)*int(value) % 513 < 67):
            self.market.place_order(self, OrderType.GTC, token_id, OrderAction.ASK, order_size=10, price=1)
         time.sleep(1)
   