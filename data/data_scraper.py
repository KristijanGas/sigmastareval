import os
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
import json
from websocket import WebSocketApp
from data_interface import parse_time_name_5m, parse_time_name_hourly
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
#markets = ["bitcoin-up-or-down"]
#https://gamma-api.polymarket.com/events?slug=bitcoin-up-or-down-june-30-2026-2pm-et
#https://clob.polymarket.com/book?token_id=54723568072009946861830956098453721516917366403655545781627131273815785194717 # token moras izvadit iz ovog prvog i onda koristit

#https://gamma-api.polymarket.com/markets?closed=false&limit=1000
#https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT



def get_current_market_names(time_name,market):
    
    #print(f"Fetching market metadata for {market} at {time_name}")
    full_name = f"{market}-{time_name}"
    path = f"https://gamma-api.polymarket.com/events?slug={full_name}"
    #print(path)
    request = urllib.request.Request(
        path,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://polymarket.com/",
        },
    )
    try: 
        with urllib.request.urlopen(request, timeout=20) as url:
            market_metadata = json.loads(url.read().decode())
    except Exception as e:
        print(f"Error fetching market metadata for {market} at {time_name}: {e}")
        market_metadata = None
    return market_metadata

def get_clob_data(market_metadata, provider):
    clob_token_ids = json.loads(market_metadata[0]["markets"][0]["clobTokenIds"])
    clobs = []
    for i in range(len(clob_token_ids)):
        token_id = clob_token_ids[i]
        market_data = {}
        market_data["bids"] = provider.get_asset(token_id, "bids")
        market_data["asks"] = provider.get_asset(token_id, "asks")
        clobs.append((token_id,market_data))
    return clobs


def store_data(data, time_name, market):

    store_path = f"datasets/{market}/{market}-{time_name}.gz"
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    with gzip.open(store_path, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"Stored data for {market} at {store_path}")


def __main__():
    if len(sys.argv) < 4:
        print("Usage: python data_scraper.py <market_slug> <market_binance> <market_type>")
        sys.exit(1)
    market = sys.argv[1]
    market_binance = sys.argv[2]
    market_type = sys.argv[3]
    print(f"Starting data scraper for market: {market}, Binance symbol: {market_binance}, Type: {market_type}")
    if market_type == "hourly":
        old_time_name = parse_time_name_hourly()["hourly_name"]
    elif market_type == "5m":
        old_time_name = parse_time_name_5m()
    markets_metadata = get_current_market_names(old_time_name, market)
    print(old_time_name)
    data = {"metadata_start": markets_metadata, "all_clobs": [], "all_prices": [], "metadata_end": None}
    ind = 0

    provider = live_provider(market, market_binance, market_type, None)
    provider_thread = threading.Thread(target=provider.run, daemon=True)
    provider_thread.start()
    if market_type == "hourly":
        time_name = parse_time_name_hourly()["hourly_name"]
    elif market_type == "5m":
        time_name = parse_time_name_5m()
    provider.set_market(time_name)

    while 1:
        if market_type == "hourly":
            time_name = parse_time_name_hourly()["hourly_name"]
        elif market_type == "5m":
            time_name = parse_time_name_5m()

        if (time_name != old_time_name):
            markets_metadata_old = get_current_market_names(old_time_name, market)
            data["metadata_end"] = markets_metadata_old
            data["all_prices"] = provider.consume_crypto_values()
            store_data(data,old_time_name,market)
            provider.set_market(time_name)

            #new batch
            markets_metadata = get_current_market_names(time_name, market)
            data = {"metadata_start": markets_metadata, "all_clobs": [], "all_prices": [], "metadata_end": None}

        #print(len(data[market]["all_clobs"]))
        old_time_name = time_name

        market_metadata = data["metadata_start"]
        try:
            clobs = get_clob_data(market_metadata, provider)
            if len(data["all_clobs"]) == 0 or data["all_clobs"][-1] != clobs:
                data["all_clobs"].append(clobs)
        except Exception as e:
            print(f"Error occurred while fetching CLOB data for {market}: {e}")
        time.sleep(0.05)
        ind += 1
        if ind % 100 == 0:
            print(time_name, market_binance)

__main__()