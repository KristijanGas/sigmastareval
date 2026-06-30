import marketlens

client = marketlens.MarketLens()


walk = client.orderbook.walk(
    "btc-up-or-down-5m",
    after="2026-04-15T01:45:00Z",
    before="2026-04-15T01:50:00Z",
)

for market, book in walk:
    print(book.as_of, book.best_bid, book.best_ask, book.midpoint)