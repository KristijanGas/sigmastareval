



class market_simulator:
    def __init__(self):
        self.orders = {}

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
