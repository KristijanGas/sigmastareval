



class market_simulator:
    def __init__(self, data_provider, starting_cash):
        self.orders = {}
        self.data_provider = data_provider
        self.starting_cash = starting_cash
        self.current_cash = starting_cash
        self.user_orders = []
        self.order_id_counter = 0

    def place_order(self, order_type, asset_id, order_action, order_size, price):
        self.order_id_counter += 1
        self.orders.append(
            {
            "order_id": self.order_id_counter,
            "asset_id": asset_id,
            "order_type": order_type,
            "order_action": order_action,
            "order_size": order_size,
            "price": price,
            "timestamp": self.data_provider.get_current_timestamp()
            }
        )
        return self.order_id_counter

    def cancel_order(self, order_id):
        for order in self.orders:
            if order["order_id"] == order_id:
                self.orders.remove(order)
                return True
        return False


    def get_order(self, asset_id):
        return self.orders.get(asset_id, None)

    def get_all_orders(self):
        return self.orders

    def set_order_book(self, order_book):
        self.data_provider.set_order_book(order_book)
    def set_crypto_value(self, crypto_value):
        self.data_provider.set_crypto_value(crypto_value)
    def set_timestamp(self, timestamp):
        self.data_provider.set_timestamp(timestamp)
