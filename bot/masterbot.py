


from abc import ABC, abstractmethod
from collections import deque


class masterbot(ABC):
    def __init__(self, in_production = False, market = None, data_provider = None):
        self.in_production = in_production
        self.market = market
        self.data_provider = data_provider
        self.past_crypto_predictions = []

    def get_current_timestamp(self):
        return self.data_provider.get_current_timestamp()
    
    def get_crypto_value(self):
        return self.data_provider.get_crypto_value()
    
    def get_order_book(self):
        return self.data_provider.get_order_book()
    
    
    def first_run_setup(self):
            self.starting_cash = self.market.get_user_cash()
            self.unusable_cash = self.starting_cash * (1-self.investment_cash_percent)
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


    @abstractmethod
    def run(self):
        """
        This method should be implemented by the user.
        It will be called when the bot is started.
        """
        pass