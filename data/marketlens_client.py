import os
from pathlib import Path

import marketlens


def load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv_file(Path(__file__).resolve().parents[1] / ".env")

client = marketlens.MarketLens()


walk = client.orderbook.walk(
    "btc-up-or-down-5m",
    after="2026-04-15T01:45:00Z",
    before="2026-04-15T01:50:00Z",
)

for market, book in walk:
    print(book.as_of, book.best_bid, book.best_ask, book.midpoint)