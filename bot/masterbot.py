


from pyparsing import abstractmethod


class masterbot:
    def __init__(self, in_production = False, market = None, data_provider = None):
        self.in_production = in_production
        self.market = market
        self.data_provider = data_provider
    @abstractmethod
    def run(self):
        """
        This method should be implemented by the user.
        It will be called when the bot is started.
        """
        pass
