

class historical_provider:
    def __init__(self):
        self.timestamp = 0
        self.order_book = None
        self.crypto_value = None

    def get_current_timestamp(self):
        return self.timestamp
    
    def get_crypto_value(self):
        return self.crypto_value
    
    def get_order_book(self):
        return self.order_book

    def set_order_book(self, order_book):
        self.order_book = order_book

    def set_crypto_value(self, crypto_value):
        self.crypto_value = crypto_value
        
    def set_timestamp(self, timestamp):
        self.timestamp = timestamp