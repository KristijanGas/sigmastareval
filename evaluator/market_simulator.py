from bot.order_actions import OrderAction
from bot.order_types import OrderType



class market_simulator:
    def __init__(self, data_provider, starting_cash, base_name):
        
        self.data_provider = data_provider
        self.starting_cash = starting_cash
        self.base_name = base_name
        #self.slug = slug
        #self.market_name = market_name
        self.min_order_size = {}
        self.fee_percent = 0.07
        self.on_chain_delay = 2000
        self.matching_delay = 270
        self.new_order = {}
        self.should_update_order_book = True
        # order control
        self.last_placed_order_type = {}
        self.order_timeout = 1000
        # user tracking
        self.current_cash = starting_cash
        self.orders = []
        self.pending_orders = []
        self.order_id_counter = 0
        self.user_holdings = {}
        self.order_matches = []
        # analytics
        self.transactions = []
        self.order_placements = []

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
        if order_size < float(self.min_order_size.get(asset_id, 5)):
            raise ValueError(f"Order size must be greater than or equal to the minimum order size: {self.set_min_order_size}")
        if asset_id not in self.data_provider.get_market_asset_ids():
            raise ValueError(f"Invalid asset ID: {asset_id}")
        
        if order_action == OrderAction.BID and self.current_cash < order_size * price:
            return None  # Not enough cash to place the order
        if order_action == OrderAction.ASK and self.user_holdings.get(asset_id, 0) < order_size:
            return None  # Not enough holdings to place the order

        if self.last_placed_order_type.get((asset_id, order_action)) is not None:
            time_since_last_order = self.data_provider.get_current_timestamp() - self.last_placed_order_type[(asset_id, order_action)]
            if time_since_last_order < self.order_timeout:
                return None  # Not enough time has passed since the last order of this type for this asset
            
        self.last_placed_order_type[(asset_id, order_action)] = self.data_provider.get_current_timestamp()
        self.order_id_counter += 1
        self.pending_orders.append(
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
        self.order_placements.append(
            {
                "timestamp": self.data_provider.get_current_timestamp(),
                "asset_id": asset_id,
                "order_type": order_type,
                "order_action": order_action,
                "order_size": order_size,
                "price": price,
                "timeout": timeout,
            }
        )
        return self.order_id_counter

    def cancel_order(self, order_id):
        for order in self.orders:
            if order["order_id"] == order_id:
                self.orders.remove(order)
                return True
        return False

    def match_buy(self, asset_id, amount, wanted_price, available_cash):
        asks = self.data_provider.get_asset(asset_id, "asks")
        successful_matches = 0
        total_fee = 0.0
        remaining = amount
        cost = 0.0

        pointer = len(asks) - 1
        update_asks = {}
        while pointer >= 0:
            level = asks[pointer]

            price = float(level["price"])
            if price > wanted_price:
                return (cost, successful_matches, update_asks, total_fee)
            size = float(level["size"])

            traded = min(size, remaining)
            if cost + traded * price > available_cash:
                affordable = (available_cash - cost) / price
                traded = min(traded, affordable)
            cost += traded * price
            remaining -= traded
            successful_matches += traded
            total_fee += self.calculate_fee(price, traded)
            update_asks[price] = size - traded
            if remaining == 0:
                return (cost, successful_matches, update_asks, total_fee)

            pointer -= 1
        return (cost, successful_matches, update_asks, total_fee)

    def match_sell(self, asset_id, amount, wanted_price):
        bids = self.data_provider.get_asset(asset_id, "bids")
        successful_matches = 0
        total_fee = 0.0
        remaining = amount
        gain = 0.0
        update_bids = {}
        pointer = len(bids) - 1

        while pointer >= 0:
            level = bids[pointer]

            price = float(level["price"])
            if price < wanted_price:
                return (gain, successful_matches, update_bids, total_fee)
            size = float(level["size"])

            traded = min(size, remaining)
            gain += traded * price
            remaining -= traded
            successful_matches += traded
            total_fee += self.calculate_fee(price, traded)
            update_bids[price] = size - traded
            if remaining == 0:
                return (gain, successful_matches, update_bids, total_fee)

            pointer -= 1
        return (gain, successful_matches, update_bids, total_fee)

    def accept_orders(self):
        current_timestamp = self.data_provider.get_current_timestamp()
        new_pending_orders = []
        for pending_order in self.pending_orders:
            order_timestamp = pending_order["timestamp"]
            if current_timestamp - order_timestamp >= self.matching_delay:
                self.orders.append(pending_order)
                self.new_order[pending_order["order_id"]] = True
            else:
                new_pending_orders.append(pending_order)

        self.pending_orders = new_pending_orders

    def process_orders(self):
        orderIDs_to_remove = []
        if len(self.orders) > 500:
            print(f"Warning: More than 500 orders in the system, bot might be making mistakes. Current order count: {len(self.orders)}")
        self.accept_orders()
        for order in self.orders:
            asset_id = order["asset_id"]
            order_type = order["order_type"]
            order_action = order["order_action"]
            order_size = order["order_size"]
            price = order["price"]
            timeout = order["timeout"]
            update_asks = None
            update_bids = None
            cash_before_this_order = self.current_cash
            on_chain_update = {
                "order_id": order["order_id"], 
                "order_action": order_action, 
                "asset_id": asset_id, 
                "price": 0, "size": 0,
                "timestamp": self.data_provider.get_current_timestamp()
            } # delayed payout

            if order_type == OrderType.GTC or order_type == OrderType.GTD or order_type == OrderType.FAK:
                if  order_type == OrderType.GTD and self.data_provider.get_current_timestamp() > timeout: # gtd expires while gtc does not
                    orderIDs_to_remove.append(order["order_id"])
                    continue

                if order_action == OrderAction.BID:
                    money_spent, successful_matches, update_asks, total_fee = self.match_buy(asset_id, order_size, price, self.current_cash)
                    successful_matches = round(successful_matches, 2)
                    money_spent = round(money_spent, 8)
                    self.current_cash -= money_spent
                    #self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) + successful_matches
                    on_chain_update["size"] = successful_matches
                    if successful_matches > 0:
                        self.order_matches.append(on_chain_update)

                elif order_action == OrderAction.ASK:
                    money_earned, successful_matches, update_bids, total_fee = self.match_sell(asset_id, min(order_size, self.user_holdings.get(asset_id, 0)), price)
                    successful_matches = round(successful_matches, 2)
                    money_earned = round(money_earned, 8)
                    #self.current_cash += money_earned
                    on_chain_update["price"] = money_earned
                    self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) - successful_matches
                    if successful_matches > 0:
                        self.order_matches.append(on_chain_update)
                else:
                    raise ValueError(f"Unknown order action: {order_action}")
                order["order_size"] -= successful_matches
                if order["order_size"] == 0 or order_type == OrderType.FAK: # FAK fills as much as possible and then dies
                    #self.orders.remove(order)
                    orderIDs_to_remove.append(order["order_id"])

            if order_type == OrderType.FOK:
                if order_action == OrderAction.BID:
                    money_spent, successful_matches, potential_update_asks, total_fee = self.match_buy(asset_id, order_size, price, self.current_cash)
                    successful_matches = round(successful_matches, 2)
                    if successful_matches == order_size:
                        self.current_cash -= money_spent
                        #self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) + successful_matches
                        on_chain_update["size"] = successful_matches
                        orderIDs_to_remove.append(order["order_id"])
                        update_asks = potential_update_asks
                        if successful_matches > 0:
                            self.order_matches.append(on_chain_update)
                    else:
                        successful_matches = 0
                        total_fee = 0

                elif order_action == OrderAction.ASK:
                    money_earned, successful_matches, potential_update_bids, total_fee = self.match_sell(asset_id, min(order_size, self.user_holdings.get(asset_id, 0)), price)
                    if successful_matches == order_size:
                        #self.current_cash += money_earned
                        on_chain_update["price"] = money_earned
                        self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) - successful_matches
                        orderIDs_to_remove.append(order["order_id"])
                        update_bids = potential_update_bids
                        if successful_matches > 0:
                            self.order_matches.append(on_chain_update)
                    else:
                        successful_matches = 0
                        total_fee = 0
                else:
                    raise ValueError(f"Unknown order action: {order_action}")
                #self.orders.remove(order) # fills entirely or dies instantly
                orderIDs_to_remove.append(order["order_id"])
            self.user_holdings[asset_id] = round(self.user_holdings.get(asset_id, 0), 2)

            successful_matches = round(successful_matches, 2)
            if successful_matches > 0:
                if self.new_order.get(order["order_id"], False):
                    self.current_cash -= total_fee
                #print(f"Order {order['order_id']} matched {successful_matches} shares of asset {asset_id} at price {price}. Current cash: {self.current_cash:.2f}, User holdings: {self.user_holdings.get(asset_id, 0)}")
                self.transactions.append(
                    {
                        "timestamp": self.data_provider.get_current_timestamp(),
                        "asset_id": asset_id,
                        "order_action": order_action,
                        "order_type": order_type,
                        "successful_matches": successful_matches,
                        "money_change": self.current_cash - cash_before_this_order,
                        "fee": total_fee,
                        "price": price,
                        "money_after_order": self.current_cash,
                        "user_holdings_after_order": self.user_holdings.get(asset_id, 0),
                        "on_chain_update": on_chain_update
                    }
                )
            if self.should_update_order_book:
                if update_bids is not None:
                    self.data_provider.update_bids(asset_id, update_bids)
                if update_asks is not None:
                    self.data_provider.update_asks(asset_id, update_asks)
        for order_id in orderIDs_to_remove:
            self.cancel_order(order_id)

        self.new_order.clear()
        self.on_chain_update()

    def on_chain_update(self):
        still_pending_order_matches = []
        for update in self.order_matches:
            asset_id = update["asset_id"]
            order_action = update["order_action"]
            price = update["price"]
            size = update["size"]
            timestamp = update["timestamp"]
            if self.data_provider.get_current_timestamp() - timestamp >= self.on_chain_delay:
                if order_action == OrderAction.BID:
                    self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) + size
                elif order_action == OrderAction.ASK:
                    self.current_cash += price
                else:
                    raise ValueError(f"Unknown order action: {order_action}")
            else:
                still_pending_order_matches.append(update)
        self.order_matches = still_pending_order_matches

    def resolve_market(self, final_price, price_to_beat, outcomes, clobTokenIds):
        for order_match in self.order_matches:
            asset_id = order_match["asset_id"]
            order_action = order_match["order_action"]
            price = order_match["price"]
            size = order_match["size"]
            if order_action == OrderAction.BID:
                self.user_holdings[asset_id] = self.user_holdings.get(asset_id, 0) + size
            elif order_action == OrderAction.ASK:    
                self.current_cash += price
            else:
                raise ValueError(f"Unknown order action: {order_action}")

        if final_price >= price_to_beat:
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
        self.user_holdings = {}
        self.orders = []
        self.pending_orders = []
        self.order_matches = []
        
        self.order_id_counter = 0
        self.new_order = {}
        print(f"Market resolved. Winning asset: {winning_asset}, Winning asset ID: {winning_token_id}, Final price: {final_price}. User cash: {self.current_cash}")
        return winning_asset
        
        

    def get_asset_orders(self, asset_id, order_action):
        return [
            order
            for order in self.orders
            if order["asset_id"] == asset_id and order["order_action"] == order_action
        ]

    def get_all_orders(self):
        return self.orders
    
    def get_user_holdings(self):
        return self.user_holdings
    
    def get_user_cash(self):
        return self.current_cash
