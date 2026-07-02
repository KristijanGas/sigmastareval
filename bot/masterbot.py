


from abc import ABC, abstractmethod


class masterbot(ABC):
    def __init__(self, in_production = False, market = None, data_provider = None):
        self.in_production = in_production
        self.market = market
        self.data_provider = data_provider

    def get_current_timestamp(self):
        return self.data_provider.get_current_timestamp()
    
    def get_crypto_value(self):
        return self.data_provider.get_crypto_value()
    
    def get_order_book(self):
        return self.data_provider.get_order_book()
    
    @abstractmethod
    def run(self):
        """
        This method should be implemented by the user.
        It will be called when the bot is started.
        """
        pass
