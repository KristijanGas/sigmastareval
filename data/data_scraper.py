import os
import time
import urllib.request
import urllib.parse
import json
from data_interface import parse_time_name_hourly
from datetime import datetime
from zoneinfo import ZoneInfo

markets = ["bitcoin-up-or-down","ethereum-up-or-down","solana-up-or-down","xrp-up-or-down"]
#markets = ["bitcoin-up-or-down"]
#https://gamma-api.polymarket.com/events?slug=bitcoin-up-or-down-june-30-2026-2pm-et
#https://clob.polymarket.com/book?token_id=54723568072009946861830956098453721516917366403655545781627131273815785194717 # token moras izvadit iz ovog prvog i onda koristit

#https://gamma-api.polymarket.com/markets?closed=false&limit=1000
#https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT



def get_current_market_names(time_name):
    
    markets_metadata = {}
    for market in markets:
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

def store_data(data, time_name):
    for market in markets:
        market_data = data[market]
        metadata = market_data["metadata"]
        all_clobs = market_data["all_clobs"]
        store_path = f"datasets/{market}/{market}-{time_name}.json"
        # create file

        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        with open(store_path, "w") as f:
            json.dump({"metadata": metadata, "all_clobs": all_clobs}, f)
        print(f"Stored data for {market} at {store_path}")


def __main__():
    old_time_name = parse_time_name_hourly()["hourly_name"]
    markets_metadata = get_current_market_names(old_time_name)
    print(old_time_name)
    data = {}
    for market in markets:
        data[market] = {"metadata": markets_metadata[market], "all_clobs": []}
    ind = 0
    while 1:
        time_name = parse_time_name_hourly()["hourly_name"]
        if time_name != old_time_name:
            store_data(data,old_time_name)
        old_time_name = time_name
        for market in markets:
            market_metadata = data[market]["metadata"]
            clobs = get_clob_data(market_metadata)
            #print(clobs)
            data[market]["all_clobs"].append(clobs)
        ind += 1
        print(time_name)
        


        time.sleep(0.5)

__main__()