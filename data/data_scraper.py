import time
import urllib.request
import urllib.parse
import json
markets = ["bitcoin-up-or-down","ethereum-up-or-down"]
#https://gamma-api.polymarket.com/events?slug=bitcoin-up-or-down-june-30-2026-2pm-et
#https://clob.polymarket.com/book?token_id=54723568072009946861830956098453721516917366403655545781627131273815785194717 # token moras izvadit iz ovog prvog i onda koristit

#https://gamma-api.polymarket.com/markets?closed=false&limit=1000
#https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT
def get_current_market_names():
    base = "https://gamma-api.polymarket.com/markets"
    params = {
        "question_contains": "BitfAWIKONHFOWAjbnkcoin",
        "limit": 100,
    }
    url = base + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        data = resp.read().decode()
    live_markets = json.loads(data)
    print(live_markets)

def __main__():
    get_current_market_names()
    #while 1:
        
    #    time.sleep(1)

__main__()