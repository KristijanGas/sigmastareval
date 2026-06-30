import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import matplotlib.pyplot as plt
import marketlens


class marketlens_client:

    def load_dotenv_file(self, dotenv_path: Path) -> None:
        if not dotenv_path.exists():
            return

        for line in dotenv_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    def __init__(self):
        self.load_dotenv_file(Path(".env"))
        self.client = marketlens.MarketLens()
        self.walk = None
        self.walk_df = None
        self.walk_length = 0
        
    #after="2026-04-15T01:45:00Z",
    #before="2026-04-15T01:50:00Z",
    def query(self, market_slug: str, after: str, before: str):
        walk = self.client.orderbook.walk(
            market_slug,
            after=after,
            before=before,
        )
        self.walk = walk
        self.walk_df = walk.to_dataframe()
        self.walk_length = len(self.walk_df)
        return walk

    def _coerce_to_ms(self, value):
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, datetime):
            return int(value.timestamp() * 1000)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000)

    def _fetch_btc_history(self, start_ms: int, end_ms: int):
        params = urlencode({
            "symbol": "BTCUSDT",
            "interval": "1s",
            "startTime": start_ms,
            "endTime": end_ms,
        })
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urlopen(url, timeout=20) as response:
            rows = json.loads(response.read().decode())

        history = []
        for row in rows:
            open_time = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
            history.append({
                "time": open_time,
                "open": float(row[1]),
                "close": float(row[4]),
            })
        return history

    def dbg_draw_graph(self):
        if self.walk is None:
            raise ValueError("call query() before dbg_draw_graph()")

        walk_df = self.walk_df if self.walk_df is not None else self.walk.to_dataframe()
        if walk_df.empty:
            raise ValueError("walk returned no data")

        walk_df = walk_df.sort_index()
        walk_df = walk_df.loc[~walk_df.index.duplicated(keep="last")]

        fair_up = walk_df["weighted_midpoint"] if "weighted_midpoint" in walk_df.columns else walk_df["midpoint"]
        fair_down = 1 - fair_up

        start_ms = self._coerce_to_ms(walk_df.index.min())
        end_ms = self._coerce_to_ms(walk_df.index.max())
        btc_history = self._fetch_btc_history(start_ms, end_ms)
        if not btc_history:
            raise ValueError("could not load BTC price history for the walk window")

        target_price = btc_history[0]["open"]
        btc_times = [row["time"] for row in btc_history]
        btc_relative = [row["close"] - target_price + 50 for row in btc_history]

        print(btc_history[0]["time"], btc_history[0]["open"], btc_history[0]["close"])
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(walk_df.index, fair_up * 100, label="Fair price Up", color="#2563eb", linewidth=2)
        ax.plot(walk_df.index, fair_down * 100, label="Fair price Down", color="#dc2626", linewidth=2)
        ax.plot(btc_times, btc_relative, label="BTC price / target", color="#111827", linewidth=2)
        ax.axhline(50, color="#6b7280", linestyle="--", linewidth=1, label="Target price")

        ax.set_title(f"{self.walk_length} points | BTC Up/Down walk")
        ax.set_ylabel("Percent of target")
        ax.set_xlabel("Time")
        ax.grid(True, alpha=0.2)
        ax.legend(loc="best")
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.show()
        return fig, ax
        

if __name__ == "__main__":
    cl = marketlens_client()
    cl.query("btc-up-or-down-5m", after="2026-06-30T08:50:00Z", before="2026-06-30T08:55:00Z")
    cl.dbg_draw_graph()
