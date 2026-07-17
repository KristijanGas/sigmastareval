import os
import sys
import time
import urllib.request
import urllib.parse
import json
from pathlib import Path
from websocket import WebSocketApp
from data_interface import parse_time_name_5m, parse_time_name_hourly
from datetime import datetime
from zoneinfo import ZoneInfo
import gzip
import threading

from evaluator.replay_engine import load_bot

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

REPO_ROOT = Path(__file__).resolve().parents[1]

class PassiveTradingEngine:
    def __init__(self, bot_path, market_slug, market_binance, market_type):
        self.bot = load_bot(bot_path)
        self.market_slug = market_slug
        self.market_binance = market_binance
        self.market_type = market_type


def main():
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "python passive_trading_engine.py bots.my_bot.MyBot <market_slug> <market_binance> <market_type>"
        )
        sys.exit(1)

    passiveEngine = PassiveTradingEngine(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

if __name__ == "__main__":
    main()