import os
import time
import urllib.request
import urllib.parse
import json
from data_interface import parse_time_name_hourly
from datetime import datetime
from zoneinfo import ZoneInfo
import gzip

markets = [("bitcoin-up-or-down","BTCUSDT"),("ethereum-up-or-down","ETHUSDT"),("solana-up-or-down","SOLUSDT"),("xrp-up-or-down","XRPUSDT")]
#markets = ["bitcoin-up-or-down"]
#https://gamma-api.polymarket.com/events?slug=bitcoin-up-or-down-june-30-2026-2pm-et
#https://clob.polymarket.com/book?token_id=54723568072009946861830956098453721516917366403655545781627131273815785194717 # token moras izvadit iz ovog prvog i onda koristit

#https://gamma-api.polymarket.com/markets?closed=false&limit=1000
#https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT



def get_current_market_names(time_name):
    
    markets_metadata = {}
    for market_binancelookup in markets:
        market, market_binance = market_binancelookup
        
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
        with urllib.request.urlopen(request, timeout=20) as url:
            market_metadata = json.loads(url.read().decode())
        #print(market_metadata)
        markets_metadata[market] = market_metadata
    return markets_metadata

def get_clob_data(market_metadata):
    clob_token_ids = market_metadata[0]["markets"][0]["clobTokenIds"].split(", ")
    clobs = []
    for i in range(len(clob_token_ids)):
        token_id = "".join(c for c in clob_token_ids[i] if c.isdigit())
        path = f"https://clob.polymarket.com/book?token_id={token_id}"
        
        request = urllib.request.Request(
            path,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://polymarket.com/",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as url:
            market_data = json.loads(url.read().decode())
        clobs.append((token_id,market_data))
    return clobs

def get_price_data(market_binance):
    path = f"https://api.binance.com/api/v3/ticker/price?symbol={market_binance}"
    request = urllib.request.Request(
        path,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://polymarket.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as url:
        market_data = json.loads(url.read().decode())

    timestamp = datetime.now(ZoneInfo("America/New_York")).timestamp()
    market_data["timestamp"] = timestamp
    #print(f"Fetched price data for {market_binance}: {market_data}")
    return market_data

def store_data(data, time_name):
    for market_binancelookup in markets:
        market, market_binance = market_binancelookup
        store_path = f"datasets/{market}/{market}-{time_name}.gz"
        # create file

#reading it badck
#with gzip.open("data.json.gz", "rt", encoding="utf-8") as f:
#    data = json.load(f)
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        with gzip.open(store_path, "wt", encoding="utf-8") as f:
            json.dump(data[market], f)
        print(f"Stored data for {market} at {store_path}")


def __main__():
    old_time_name = parse_time_name_hourly()["hourly_name"]
    markets_metadata = get_current_market_names(old_time_name)
    print(old_time_name)
    data = {}
    for market_binancelookup in markets:
        market, market_binance = market_binancelookup
        data[market] = {"metadata_start": markets_metadata[market], "all_clobs": [], "all_prices": [], "metadata_end": None}
    ind = 0
    while 1:
        time_name = parse_time_name_hourly()["hourly_name"]
        if time_name != old_time_name:
            markets_metadata_old = get_current_market_names(old_time_name)
            data[market]["metadata_end"] = markets_metadata_old[market]
            #print(data[market]["metadata_end"])
            store_data(data,old_time_name)

            #new batch

            data = {}
            markets_metadata = get_current_market_names(time_name)
            for market_binancelookup in markets:
                market, market_binance = market_binancelookup
                data[market] = {"metadata_start": markets_metadata[market], "all_clobs": [], "all_prices": [], "metadata_end": None}
        #print(len(data[market]["all_clobs"]))
        old_time_name = time_name

        for market_binancelookup in markets:
            market, market_binance = market_binancelookup
            market_metadata = data[market]["metadata_start"]

            clobs = get_clob_data(market_metadata)
            #print(clobs)
            data[market]["all_clobs"].append(clobs)

            # Fetch price data for each market
            prices = get_price_data(market_binance)
            data[market]["all_prices"].append(prices)
        ind += 1
        print(time_name)
        


        time.sleep(0.5)

__main__()