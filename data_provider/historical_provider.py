

class historical_provider:
    def __init__(self):
        self.order_book = None
        self.crypto_value = None

    def get_current_timestamp(self):
        return max(int(self.crypto_value["timestamp"]), int(self.order_book[0][1]["timestamp"]))
    
    def get_crypto_value(self):
        return self.crypto_value["price"]
    
    def get_order_book(self):
        return self.order_book

    def get_market_asset_ids(self):
        asset_ids = []
        for asset in self.order_book:
            asset_ids.append(asset[1]["asset_id"])
        return asset_ids
    
    def get_asset(self, asset_id):
        for _, asset in self.order_book:
            if asset["asset_id"] == asset_id:
                return asset
        raise KeyError(f"Asset {asset_id} not found")

    def get_best_bid(self, asset_id):
        bids = self.get_asset(asset_id)["bids"]
        if not bids:
            return None
        return float(bids[-1]["price"])


    def get_best_ask(self, asset_id):
        asks = self.get_asset(asset_id)["asks"]
        if not asks:
            return None
        return float(asks[-1]["price"])


    def get_spread(self, asset_id): # get_spread returns the spread of an asset, based on the current order book
        bid = self.get_best_bid(asset_id)
        ask = self.get_best_ask(asset_id)

        if bid is None or ask is None:
            return None

        return ask - bid

    def get_mid_price(self, asset_id): # get_mid_price returns the mid price of an asset, based on the current order book
        bid = self.get_best_bid(asset_id)
        ask = self.get_best_ask(asset_id)

        if bid is None or ask is None:
            return None

        return (bid + ask) / 2

    def sell_gain(self, asset_id, amount_to_sell): # sell_gain returns the gain of selling a given amount of shares, based on the current order book
        bids = self.get_asset(asset_id)["bids"]

        remaining = amount_to_sell
        gain = 0.0

        pointer = len(bids) - 1

        while remaining > 0 and pointer >= 0:
            level = bids[pointer]

            price = float(level["price"])
            size = float(level["size"])

            traded = min(size, remaining)

            gain += traded * price
            remaining -= traded

            pointer -= 1

        if remaining > 0:
            raise ValueError("Not enough bid liquidity.")

        return gain


    def buy_cost(self, asset_id, amount_to_buy): # buy_cost returns the cost of buying a given amount of shares, based on the current order book
        asks = self.get_asset(asset_id)["asks"]

        remaining = amount_to_buy
        cost = 0.0

        pointer = len(asks) - 1

        while remaining > 0 and pointer >= 0:
            level = asks[pointer]

            price = float(level["price"])
            size = float(level["size"])

            traded = min(size, remaining)

            cost += traded * price
            remaining -= traded

            pointer -= 1

        if remaining > 0:
            raise ValueError("Not enough ask liquidity.")

        return cost


    def can_buy_with(self, asset_id, investment): # can buy_with returns the amount of shares that can be bought with a given investment, based on the current order book
        asks = self.get_asset(asset_id)["asks"]

        remaining_money = investment
        shares = 0.0
        tick_size = float(self.order_book[0][1]["tick_size"])
        pointer = len(asks) - 1

        while remaining_money > 0 and pointer >= 0:
            level = asks[pointer]

            price = float(level["price"])
            size = float(level["size"])

            affordable = remaining_money / price
            bought = min(size, affordable)

            shares += bought
            remaining_money -= bought * price

            pointer -= 1
        shares = int(shares / tick_size)
        shares = shares * tick_size
        return shares

    def total_bid_liquidity(self, asset_id): # total_bid_liquidity returns the total bid liquidity of an asset, based on the current order book
        bids = self.get_asset(asset_id)["bids"]
        return sum(float(level["size"]) for level in bids)

    def total_ask_liquidity(self, asset_id): # total_ask_liquidity returns the total ask liquidity of an asset, based on the current order book
        asks = self.get_asset(asset_id)["asks"]
        return sum(float(level["size"]) for level in asks)


    def can_sell(self, asset_id, amount): # can_sell returns whether there is enough bid liquidity to sell a given amount of shares
        return self.total_bid_liquidity(asset_id) >= amount

    def can_buy(self, asset_id, amount): # can_buy returns whether there is enough ask liquidity to buy a given amount of shares
        return self.total_ask_liquidity(asset_id) >= amount

    def volume_weighted_buy_price(self, asset_id, amount):
        return self.buy_cost(asset_id, amount) / amount

    def volume_weighted_sell_price(self, asset_id, amount):
        return self.sell_gain(asset_id, amount) / amount

    def set_order_book(self, order_book):
        self.order_book = order_book

    def set_crypto_value(self, crypto_value):
        self.crypto_value = crypto_value
        # current data is stored in seconds with 6 decimal places, convert directly to int with miliseconds
        self.crypto_value["timestamp"] = int(self.crypto_value["timestamp"] * 1000)
    