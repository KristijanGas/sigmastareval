from bisect import bisect_right
from typing import Any
from prediction_eval_dataclasses import OrderBookState, CryptoPrice, MarketSnapshot

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
                )
            )
        return snapshots



    def prepare_books(self, raw_clobs: list[Any]):
        books: list[OrderBookState] = []

        for entry in raw_clobs:

            #raw_book = unwrap_clob_entry(entry)
            up_book = unwrap_clob_entry(entry[0])
            down_book = unwrap_clob_entry(entry[1])
            
            if up_book is not None:
                #print(type(up_book))
                book = self.parse_order_book(up_book)
                books.append(book)

            if down_book is not None:
                book = self.parse_order_book(down_book)
                books.append(book)

        books.sort(key=lambda book: book.timestamp)
        return books
    
    def parse_order_book(self, raw_book: dict[str, Any]):

        timestamp = int(raw_book["timestamp"])
        asset_id = str(raw_book["asset_id"])

        bids = raw_book.get("bids")
        asks = raw_book.get("asks")

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
        




def unwrap_clob_entry(entry):

    # for value in entry:
    #     if (
    #         isinstance(value, dict)
    #         and "timestamp" in value
    #         and "asset_id" in value
    #     ):
    #         return value
    return entry[1]