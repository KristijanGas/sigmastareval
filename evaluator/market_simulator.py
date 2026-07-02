



class market_simulator:
    def __init__(self, data_provider, starting_cash):
        self.orders = {}
        self.data_provider = data_provider
        self.starting_cash = starting_cash
        self.current_cash = starting_cash

    def place_order(self, order_type, token_id, order_action, order_size, price):
        self.orders[token_id] = {
            "type": order_type,
            "action": order_action,
            "size": order_size,
            "remaining": order_size,
            "price": price
        }
        

    def cancel_order(self, token_id):
        if token_id in self.orders:
            del self.orders[token_id]

    def get_order(self, token_id):
        return self.orders.get(token_id, None)

    def get_all_orders(self):
        return self.orders

    def set_order_book(self, order_book):
        self.data_provider.set_order_book(order_book)
    def set_crypto_value(self, crypto_value):
        self.data_provider.set_crypto_value(crypto_value)
    def set_timestamp(self, timestamp):
        self.data_provider.set_timestamp(timestamp)
