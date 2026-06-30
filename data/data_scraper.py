import time
import requests
markets = ["bitcoin-up-or-down","ethereum-up-or-down"]

def get_current_market_names():
    live_markets = requests.get(
        "https://gamma-api.polymarket.com/markets",
        params={
            "question_contains": "BitfAWIKONHFOWAjbnkcoin",
            "limit": 100,
        },
    ).json()
    print(live_markets)

def __main__():
    get_current_market_names()
    #while 1:
        
    #    time.sleep(1)

__main__()