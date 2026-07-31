import os
import sys
import time
import urllib.request
import urllib.parse
import json
from pathlib import Path
from websocket import WebSocketApp
from datetime import datetime
from zoneinfo import ZoneInfo
import gzip
import threading

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[1]

from data_provider.live_provider import live_provider
from data.data_interface import parse_time_name_5m, parse_time_name_hourly
from evaluator.replay_engine import load_bot
from evaluator.passive_market_simulator import passive_market_simulator
from data.data_interface import parse_time_name_5m, parse_time_name_hourly
from live_dashboard import LiveDashboard

class PassiveTradingEngine:
    def __init__(self, bot_path, market_slug, market_binance, market_type):
        self.bot = load_bot(bot_path)
        self.market_slug = market_slug
        self.market_binance = market_binance
        self.market_type = market_type
        self.old_time_name = None
        self.market = passive_market_simulator(None, 100, market_slug, self.bot)
        self.live_provider = live_provider(self.market_slug, self.market_binance, self.market_type, self.market)
        self.live_thread = threading.Thread(target=self.live_provider.run, daemon=True)
        self.live_thread.start()
        while True:
            if hasattr(self.live_provider, 'metadata') and self.live_provider.metadata is not None:
                break
        self.market.data_provider = self.live_provider

        self.market_thread = threading.Thread(target=self.market.run, args=(self.market_type,), daemon=True)
        self.market_thread.start()
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()
        self.live_dashboard = LiveDashboard(self.live_provider, history=30000)
        self.live_dashboard.run()
        
    def run_bot(self):
        while True:
            if hasattr(self.live_provider, 'metadata') and self.live_provider.metadata is not None:
                break
        self.bot.market = self.market
        self.bot.data_provider = self.live_provider
        while True:
            if self.market_type == "hourly":
                time_name = parse_time_name_hourly()["hourly_name"]
            elif self.market_type == "5m":
                time_name = parse_time_name_5m()
            if self.old_time_name is None or time_name != self.old_time_name:
                self.bot.first_run_setup()
                self.old_time_name = time_name
            if self.live_provider.current_market_name is not None and self.live_provider.current_market_name == f"{self.market_slug}-{time_name}":
                ran_correctly = self.bot.run()
                time.sleep(0.0001) # there's a bug where if you remove this, dashboard lags like hell
                if not ran_correctly:
                    time.sleep(0.1)
            #print("cash: ", self.market.get_user_cash())
            #print("holdings: ", self.market.get_user_holdings())

def main():
    if len(sys.argv) < 4:
        print(
            "Usage:\n"
            "python passive_trading_engine.py bots.my_bot.MyBot <market_slug> <market_binance> <market_type>"
        )
        sys.exit(1)

    passiveEngine = PassiveTradingEngine(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    passiveEngine.run_bot()
if __name__ == "__main__":
    main()
# python3 evaluator/passive_trading_engine.py bot/k_strategy.py bitcoin-up-or-down BTCUSDT hourly