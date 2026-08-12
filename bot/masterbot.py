


from abc import ABC, abstractmethod
from collections import deque
import json


class masterbot(ABC):
    def __init__(self, in_production = False, market = None, data_provider = None):
        self.in_production = in_production
        self.market = market
        self.data_provider = data_provider
        self.past_crypto_predictions = []

    
    def first_run_setup(self):
            self.market_base_name = self.market.base_name
            self.starting_cash = self.market.get_user_cash()
            self.unusable_cash = self.starting_cash * (1 - self.investment_cash_percent)
            self.clob_token_ids = self.data_provider.get_market_asset_ids()
            self.price_to_beat = self.data_provider.get_price_to_beat()
            predictor = getattr(self, "predictor", None)
            if predictor is not None:
                self.predictor.price_to_beat = self.price_to_beat
            self.up_token_id = self.data_provider.get_up_token_id()
            self.down_token_id = self.data_provider.get_down_token_id()
            self.first_run = False
            #self.past_crypto_predictions = []
            self.order_library = []
            self.load_config()

    def load_config(self):
         class_name = self.__class__.__name__
         path_to_cfg = f"bot/configs/{class_name}/{self.market_base_name}.cfg"
         with open(path_to_cfg, "r") as f:
            config = json.load(f).get("parameters")
            for key, value in config.items():
                setattr(self, key, value)

    @abstractmethod
    def run(self):
        """
        This method should be implemented by the user.
        It will be called when the bot is started.
        """
        pass