from bisect import bisect_right
from typing import Any
from data_provider.historical_provider import historical_provider
from evaluator.prediction_evaluator.prediction_eval_dataclasses import OrderBookState, CryptoPrice, MarketSnapshot

class SnapshotBuilder:
    def __init__(
        self,
        up_asset_id: str,
        down_asset_id: str,
        market_end_timestamp: int | None = None,
        price_to_beat: float | None = None,
        ):

        self.up_asset_id = up_asset_id
        self.down_asset_id = down_asset_id
        self.market_end_timestamp = market_end_timestamp
        self.price_to_beat = price_to_beat

    def build(self, raw_clobs: list[Any], raw_prices: list[dict[str, Any]]):
        books = self.prepare_books(raw_clobs)

        crypto_prices = self.prepare_prices(raw_prices)

        crypto_timestamps = [price.timestamp for price in crypto_prices]
        
        snapshots: list[MarketSnapshot] = []

        latest_up = None
        latest_down = None

        index = 0

        while index < len(books):
            timestamp = books[index].timestamp
            #print(books[index])

            # Process every book update with this timestamp before
            # creating a snapshot.
            while (
                index < len(books)
                and books[index].timestamp == timestamp
            ):
                book = books[index]

                if book.asset_id == self.up_asset_id:
                    latest_up = book
                elif book.asset_id == self.down_asset_id:
                    latest_down = book

                index += 1


            timestamp = book.timestamp
            crypto_price = self.latest_crypto_price(
                crypto_prices=crypto_prices,
                crypto_timestamps=crypto_timestamps,
                timestamp=timestamp
                )
            if self.market_end_timestamp is None:
                time_to_end_ms = None
            else:
                time_to_end_ms = max(0, self.market_end_timestamp - timestamp)
            
            snapshots.append(
                MarketSnapshot(
                    timestamp=timestamp,
                    up_book=latest_up,
                    down_book=latest_down,
                    crypto_price=(
                        crypto_price.price
                        if crypto_price is not None
                        else None
                    ),
                    crypto_price_timestamp=(
                        crypto_price.timestamp
                        if crypto_price is not None
                        else None
                    ),
                    time_to_end_ms=time_to_end_ms,
                    price_to_beat=self.price_to_beat,
                    market_end_timestamp=self.market_end_timestamp,
                )
            )
        return snapshots



    def prepare_books(self, raw_clobs: list[Any]):
        books: list[OrderBookState] = []

        for entry in raw_clobs:

            #raw_book = unwrap_clob_entry(entry)
            up_book, up_asset_id = unwrap_clob_entry(entry[0])
            down_book, down_asset_id = unwrap_clob_entry(entry[1])
            
            if up_book is not None:
                #print(type(up_book))
                book = parse_order_book(up_book, up_asset_id)
                books.append(book)

            if down_book is not None:
                book = parse_order_book(down_book, down_asset_id)
                books.append(book)

        books.sort(key=lambda book: book.timestamp)
        return books
    

    def prepare_prices(self, raw_prices:list[dict[str, Any]]):
        prices = []

        for raw_price in raw_prices:
            try:
                price = self.parse_crypto_price(raw_price)
            except (KeyError, TypeError, ValueError):
                continue
            prices.append(price)
        prices.sort(key=lambda price: price.timestamp)
        return prices

    def parse_crypto_price(self, raw_price: dict[str, Any]):
        timestamp_seconds = float(raw_price["timestamp"])
        return CryptoPrice(
            timestamp=round(timestamp_seconds*1000),
            price=float(raw_price["price"]),
            symbol=str(raw_price["symbol"]),
        )
    
    def latest_crypto_price(
            self,
            crypto_prices: list[CryptoPrice],
            crypto_timestamps: list[int],
            timestamp: int,
    ):
        index = bisect_right(crypto_timestamps, timestamp) - 1
        if index < 0:
            return None
        price = crypto_prices[index] #latest Binance price at or before the book timestamp (later ones would cause future leakage)
        return price
        

def parse_order_book(raw_book: dict[str, Any], book_asset_id):

    #print(raw_book)
    timestamp = int(raw_book["timestamp"])
    if "asset_id" in raw_book:
        asset_id = str(raw_book["asset_id"])
    elif book_asset_id is not None:
        asset_id = book_asset_id
    else:
        asset_id = None

    bids = raw_book.get("bids")
    asks = raw_book.get("asks")

    # print("bids:")
    # print(bids)
    #exit()

    if not bids:
        best_bid_level = None
        best_bid = None
        best_bid_size = None
    else:
        best_bid_level = bids[-1]
        best_bid = float(best_bid_level["price"])
        best_bid_size = float(best_bid_level["size"])
    
    if not asks:
        best_ask_level = None
        best_ask = None
        best_ask_size = None
    else:
        best_ask_level = asks[-1]
        best_ask = float(best_ask_level["price"])
        best_ask_size = float(best_ask_level["size"])

    
    if best_bid is not None and best_ask is not None:
        midpoint = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
    else:
        midpoint = None
        spread = None

    return OrderBookState(
        asset_id=asset_id,
        timestamp=timestamp,
        bids=bids,
        asks=asks,
        best_bid=best_bid,
        best_ask=best_ask,
        best_bid_size=best_bid_size,
        best_ask_size=best_ask_size,
        midpoint=midpoint,
        spread=spread,
    )


def prepare_order_book(raw_clob):
    up_book, up_asset_id = unwrap_clob_entry(raw_clob[0])
    down_book, down_asset_id = unwrap_clob_entry(raw_clob[1])
    if up_book is not None:
        #print(type(up_book))
        up_book = parse_order_book(up_book, up_asset_id)

    if down_book is not None:
        down_book = parse_order_book(down_book, down_asset_id)
    return up_book, down_book


def unwrap_clob_entry(entry):
    #entry[0] is asset_id and entry[1] is orderbook dict
    return entry[1], entry[0]

def create_snapshot(data_provider: historical_provider):
    timestamp = data_provider.get_current_timestamp()
    end_timestamp = data_provider.get_end_timestamp()
    if end_timestamp is None:
        time_to_end_ms = None
    else:
        time_to_end_ms = max(0, end_timestamp - timestamp)



    #up_book, down_book = prepare_order_book(data_provider.get_order_book())
    up_book, down_book = load_order_books(data_provider, timestamp)
    return MarketSnapshot(
        timestamp=timestamp,
        up_book=up_book,
        down_book=down_book,
        crypto_price=data_provider.get_crypto_value(),
        crypto_price_timestamp=timestamp,
        time_to_end_ms=time_to_end_ms,
        price_to_beat=data_provider.get_price_to_beat(),
        market_end_timestamp=end_timestamp,
    )

def load_order_books(data_provider: historical_provider, timestamp):
    up_asset_id = data_provider.get_up_token_id()
    down_asset_id = data_provider.get_down_token_id()

    raw_up_book = {}
    raw_up_book["bids"] = data_provider.get_asset(up_asset_id, "bids")
    raw_up_book["asks"] = data_provider.get_asset(up_asset_id, "asks")
    raw_up_book["asset_id"] = up_asset_id
    raw_up_book["timestamp"] = timestamp
    up_book = parse_order_book(raw_up_book)

    raw_down_book = {}
    raw_down_book["bids"] = data_provider.get_asset(down_asset_id, "bids")
    raw_down_book["asks"] = data_provider.get_asset(down_asset_id, "asks")
    raw_down_book["asset_id"] = down_asset_id
    raw_down_book["timestamp"] = timestamp
    down_book = parse_order_book(raw_down_book)

    return up_book, down_book





