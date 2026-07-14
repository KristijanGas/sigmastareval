import gzip
import json
from pathlib import Path
import sys
#from graph_drawer import draw_graph

#analyzes data for a market/markets with no bots
class MarketAnalyzer:
    def __init__(self, dataset_path: Path):
        self.dataset_path = dataset_path

    def analyze(self):
        self.orders_for_x_achieved(0.4)
                
    
    def orders_for_x_achieved(self, x):
        count = 0
        total = 0
        for gz_file in self.dataset_path.rglob("*.gz"):
            total += 1
            achieved = {}
            with gzip.open(gz_file, "rt", encoding="utf-8") as f:
                data = json.load(f)
                #output_dir = Path("tmp") / self.dataset_path.name
                #analytics_path = output_dir / f"{gz_file.stem}.analytics.json"
                #with open(analytics_path, "r", encoding="utf-8") as f:
                #    analythics = json.load(f)
                #draw_graph(analytics=analythics,output_path=None,show=True)
                out = False
                for clob in data["all_clobs"]:
                    for market in clob:
                        asset_id = market[0]
                        if asset_id not in achieved:
                            achieved[asset_id] = False
                        if market[1] and market[1]["asks"] and float(market[1]["asks"][-1]["price"]) <= x:
                            #print(float(market[1]["asks"][-1]["price"]))
                            achieved[asset_id] = True
                        if all(outcome is True for outcome in achieved.values()):                           
                            count += 1
                            out = True
                            break
                    if out:
                        break
        print(str(count) + " out of " + str(total)+ " markets had both prices <= " + str(x))
        print("Percentage: " + str(count / total))

    def stdev_from_pricetobeat(self):
        stdevs = {}
        for gz_file in self.dataset_path.rglob("*.gz"):
            with gzip.open(gz_file, "rt", encoding="utf-8") as f:
                data = json.load(f)
                try: 
                    price_to_beat = data["metadata_end"][0]["eventMetadata"]["priceToBeat"]
                except KeyError:
                    print(f"Warning: 'priceToBeat' not found in metadata_end for file {gz_file}. Skipping this file.")
                    continue
                for price in data["all_prices"]:
                    if price is not None:
                        stdev = abs(float(price["price"]) - price_to_beat)
                        if gz_file.name not in stdevs:
                            stdevs[gz_file.name] = []
                        stdevs[gz_file.name].append(stdev)
        for filename, stdev_list in stdevs.items():
            if stdev_list:
                average_stdev = sum(stdev_list) / len(stdev_list)
                print(f"Average standard deviation from priceToBeat for {filename}: {average_stdev}")
            else:
                print(f"No valid prices found for {filename} to calculate standard deviation.")
# run example: python analytics/market_analyzer.py datasets/bitcoin-up-or-down/
path = Path(sys.argv[1])
market_analyzer = MarketAnalyzer(path)
market_analyzer.stdev_from_pricetobeat()