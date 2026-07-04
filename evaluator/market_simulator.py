from bot.order_actions import OrderAction
from bot.order_types import OrderType



class market_simulator:
    def __init__(self, data_provider, starting_cash):
        
        self.data_provider = data_provider
        self.starting_cash = starting_cash
        self.min_order_size = {}
        self.fee_percent = 0.07
        self.new_order = {}
        # user tracking
        self.current_cash = starting_cash
        self.orders = []
        self.order_id_counter = 0
        self.user_holdings = {}

    def set_min_order_size(self, asset_id, min_order_size):
        self.min_order_size[asset_id] = min_order_size

    def calculate_fee(self, price, shares):
        return shares * price * (1 - price) * self.fee_percent


    def place_order(self, order_type, asset_id, order_action, order_size, price, timeout):
        if order_type not in [OrderType.GTC, OrderType.GTD, OrderType.FOK, OrderType.FAK]:
            raise ValueError(f"Invalid order type: {order_type}")
        if order_action not in [OrderAction.BID, OrderAction.ASK]:
            raise ValueError(f"Invalid order action: {order_action}")
        if order_size <= 0:
            raise ValueError(f"Order size must be positive: {order_size}")
        if price <= 0:
            raise ValueError(f"Price must be positive: {price}")
        if order_type == OrderType.GTD and timeout <= self.data_provider.get_current_timestamp():
            raise ValueError(f"GTD order timeout must be in the future: {timeout}")
        if order_size < float(self.min_order_size[asset_id]):
            raise ValueError(f"Order size must be greater than or equal to the minimum order size: {self.set_min_order_size}")
        
        self.order_id_counter += 1
        self.orders.append(
            {
            "order_id": self.order_id_counter,
            "asset_id": asset_id,
            "order_type": order_type,
            "order_action": order_action,
            "order_size": order_size,
            "price": price,
            "timestamp": self.data_provider.get_current_timestamp(),
            "timeout": timeout
            }
        )
        self.new_order[self.order_id_counter] = True
        return self.order_id_counter

    def cancel_order(self, order_id):
        for order in self.orders:
            if order["order_id"] == order_id:
                self.orders.remove(order)
                return True
        return False

    def match_buy(self, asset_id, amount, wanted_price, available_cash):
        asks = self.data_provider.get_asset(asset_id)["asks"]
        successful_matches = 0
        remaining = amount
        cost = 0.0

        pointer = len(asks) - 1
        update_asks = {}
        while pointer >= 0:
            level = asks[pointer]

            price = float(level["price"])
            if price > wanted_price:
                return (cost, successful_matches, update_asks)
            size = float(level["size"])

            traded = min(size, remaining)
            if cost + traded * price > available_cash:
                affordable = (available_cash - cost) / price
                traded = min(traded, affordable)
            cost += traded * price
            remaining -= traded
            successful_matches += traded
            update_asks[price] = size - traded
            if remaining == 0:
                return (cost, successful_matches, update_asks)

            pointer -= 1
        return (cost, successful_matches, update_asks)

    def match_sell(self, asset_id, amount, wanted_price):
        bids = self.data_provider.get_asset(asset_id)["bids"]
        successful_matches = 0
        remaining = amount
        gain = 0.0
        update_bids = {}
        pointer = len(bids) - 1

        while pointer >= 0:
            level = bids[pointer]

            price = float(level["price"])
            if price < wanted_price:
                return (gain, successful_matches, update_bids)
            size = float(level["size"])

            traded = min(size, remaining)
            gain += traded * price
            remaining -= traded
            successful_matches += traded
            update_bids[price] = size - traded
            if remaining == 0:
                return (gain, successful_matches, update_bids)

            pointer -= 1
        return (gain, successful_matches, update_bids)

    def process_orders(self):
        orderIDs_to_remove = []
        if len(self.orders) > 500:
            print(f"Warning: More than 500 orders in the system, bot might be making mistakes. Current order count: {len(self.orders)}")
        for order in self.orders:
            asset_id = order["asset_id"]
            order_type = order["order_type"]
            order_action = order["order_action"]
            order_size = order["order_size"]
            price = order["price"]
            timeout = order["timeout"]
            update_asks = None
            update_bids = None

            
            if order_type == OrderType.GTC or order_type == OrderType.GTD or order_type == OrderType.FAK:
                if  order_type == OrderType.GTD and self.data_provider.get_current_timestamp() > timeout: # gtd expires while gtc does not
                    orderIDs_to_remove.append(order["order_id"])
                    continue

                if order_action == OrderAction.BID:
                    money_spent, successful_matches, update_asks = self.match_buy(asset_id, order_size, price, self.current_cash)
                    self.current_cash -= money_spent
                    self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) + successful_matches
                elif order_action == OrderAction.ASK:
                    money_earned, successful_matches, update_bids = self.match_sell(asset_id, min(order_size, self.user_holdings.get(asset_id, 0)), price)
                    self.current_cash += money_earned
                    self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) - successful_matches
                else:
                    raise ValueError(f"Unknown order action: {order_action}")
                order["order_size"] -= successful_matches
                if order["order_size"] == 0 or order_type == OrderType.FAK: # FAK fills as much as possible and then dies
                    #self.orders.remove(order)
                    orderIDs_to_remove.append(order["order_id"])

            if order_type == OrderType.FOK:
                if order_action == OrderAction.BID:
                    money_spent, successful_matches, potential_update_asks = self.match_buy(asset_id, order_size, price, self.current_cash)
                    successful_matches = round(successful_matches, 2)
                    if successful_matches == order_size:
                        self.current_cash -= money_spent
                        self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) + successful_matches
                        orderIDs_to_remove.append(order["order_id"])
                        update_asks = potential_update_asks
                elif order_action == OrderAction.ASK:
                    money_earned, successful_matches, potential_update_bids = self.match_sell(asset_id, min(order_size, self.user_holdings.get(asset_id, 0)), price)
                    if successful_matches == order_size:
                        self.current_cash += money_earned
                        self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) - successful_matches
                        orderIDs_to_remove.append(order["order_id"])
                        update_bids = potential_update_bids
                else:
                    raise ValueError(f"Unknown order action: {order_action}")
                #self.orders.remove(order) # fills entirely or dies instantly
                orderIDs_to_remove.append(order["order_id"])
            if self.new_order.get(order["order_id"], False):
                self.current_cash -= self.calculate_fee(price, order_size)
                
            if update_bids is not None:
                self.data_provider.update_bids(asset_id, update_bids)
            if update_asks is not None:
                self.data_provider.update_asks(asset_id, update_asks)
        for order_id in orderIDs_to_remove:
            self.cancel_order(order_id)

        self.new_order.clear()

    def resolve_market(self,eventMetadata,outcomes, clobTokenIds):
        
        if eventMetadata["finalPrice"] >= eventMetadata["priceToBeat"]:
            winning_asset = "Up"
        else:
            winning_asset = "Down"
        for i in range(len(outcomes)):
            if outcomes[i] == winning_asset:
                winning_asset_id = i
                break
        winning_token_id = clobTokenIds[winning_asset_id]
        #print(f"Winning asset: {winning_asset}, Winning asset ID: {winning_token_id}, Final price: {eventMetadata['finalPrice']}")
        if self.user_holdings.get(winning_token_id, 0) > 0:
            self.current_cash += self.user_holdings[winning_token_id]
            self.user_holdings[winning_token_id] = 0
        
        

    def get_asset_orders(self, asset_id):
        return [
            order
            for order in self.orders
            if order["asset_id"] == asset_id
        ]

    def get_all_orders(self):
        return self.orders
    
    def get_user_holdings(self):
        return self.user_holdings
    
    def get_user_cash(self):
        return self.current_cash
