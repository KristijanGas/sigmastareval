



class market_simulator:
    def __init__(self, data_provider, starting_cash):
        self.orders = {}
        self.data_provider = data_provider
        self.starting_cash = starting_cash

        # user tracking
        self.current_cash = starting_cash
        self.user_orders = []
        self.order_id_counter = 0
        self.user_holdings = {}

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


    def get_asset_orders(self, asset_id):
        return self.orders.get(asset_id, None)

    def get_all_orders(self):
        return self.orders
    
    def get_user_holdings(self):
        return self.user_holdings
    
    def get_user_cash(self):
        return self.current_cash
