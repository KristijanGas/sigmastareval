import subprocess
import sys
import time


#markets = ["bitcoin-up-or-down"]
#https://gamma-api.polymarket.com/events?slug=bitcoin-up-or-down-june-30-2026-2pm-et
#https://clob.polymarket.com/book?token_id=54723568072009946861830956098453721516917366403655545781627131273815785194717 # token moras izvadit iz ovog prvog i onda koristit

#https://gamma-api.polymarket.com/markets?closed=false&limit=1000
#


markets = [("bitcoin-up-or-down","BTCUSDT", "hourly"),("ethereum-up-or-down","ETHUSDT", "hourly"),
           ("solana-up-or-down","SOLUSDT", "hourly"),("xrp-up-or-down","XRPUSDT", "hourly"),
           #("btc-updown-5m","BTCUSDT", "5m"),("eth-updown-5m","ETHUSDT", "5m")
           ]

processes = []

for market in markets:
    market_name, market_binance, market_type = market
    process = subprocess.Popen([sys.executable, "data/data_scraper.py", market_name, market_binance, market_type])
    processes.append(process)

try:
    while True:

        print("Updating metadata...")
        subprocess.run([sys.executable, "data/data_meta_fill.py"], check=True)
        time.sleep(5000)
except KeyboardInterrupt:
    print("Terminating all scraper processes...")
    for process in processes:
        process.terminate()
    for process in processes:
        process.wait()
    print("All scraper processes terminated.")

    