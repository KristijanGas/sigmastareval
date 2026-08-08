import gzip
import json
from analytics.equity_point import EquityPoint
from analytics.performance_result import PerformanceResult
import matplotlib.pyplot as plt
from datetime import datetime
from bot.order_actions import OrderAction
from collections import deque
from statistics import mean, median
from analytics.graph_drawer import draw_graph

# performance analyzer for one market run
class PerformanceAnalyzer:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.analytics_path = None
        self.equity_curve = []
        self.closed_trades = []
        self.performance_result = None
        self.data = None

    def analyze(self):
        self.performance_result = PerformanceResult()
        if str(self.analytics_path).endswith(".gz"):
            with gzip.open(self.analytics_path, "rt", encoding="utf-8") as f:
                self.data = json.load(f)
                #print("used gzip.open")
        else:
            with open(self.analytics_path, "r", encoding="utf-8") as f:
                #print("used normal open")
                self.data = json.load(f)
        self.generate_equity_curve()
        self.build_closed_trades_fifo(self.data["transactions"], self.data["resolution"], include_fees=True)
        #self.plot_trade_pnl_bars()
        self.performance_result.pnl = self.pnl()
        self.performance_result.roi = self.roi()
        self.performance_result.max_drawdown = self.max_drawdown()
        self.performance_result.idle_time = self.idle_time()
        self.performance_result.profit_factor = self.profit_factor()
        self.performance_result.trade_count = self.trade_count()
        self.performance_result.final_cash = self.data["final_cash"]
        self.performance_result.total_fees_paid = self.total_fees_paid()
        self.performance_result.market_name = self.analytics_path.name
        self.performance_result.winrate = self.winrate()
        self.performance_result.avg_trade_profit = self.average_trade_profit()
        self.performance_result.median_trade_profit = self.median_trade_profit()
        self.performance_result.largest_gain = self.largest_gain()
        self.performance_result.largest_loss = self.largest_loss()
        self.performance_result.time_before_exp_min = self.time_before_expiration()
        self.performance_result.fees_to_balance = self.fees_to_initial_balance_ratio()
        self.performance_result.profit_lost_to_fees = self.profit_lost_to_fees()
        self.performance_result.fee_efficiency = self.fee_efficiency()
        self.performance_result.turnover = self.turnover()
        self.performance_result.total_traded_volume = self.total_traded_volume()
        self.performance_result.resolution = self.data["resolution"]
        #print("from analyzer (name):")
        #print(self.performance_result.market_name)


        #self.run_decision_quality_methods()
        #self.plot_equity_breakdown()
        #draw_graph(self.data, show=True)
        #self.plot_equity_curve()
        # analyze here
        return self.performance_result
    
    def generate_equity_curve(self):


        if "timestamps" not in self.data:
            timestamps_list = [item["timestamp"] for item in self.data["cash_history"]]

            # for item_list in self.data["mid_prices"].values():
            #     timestamps_list += [item["timestamp"] for item in item_list]

            timestamps = sorted(list(set(timestamps_list)))
            self.data["timestamps"] = timestamps
        else:
            timestamps = sorted(self.data["timestamps"])

        cash_lookup = {
            item["timestamp"]: item["cash"]
            for item in self.data["cash_history"]
        }

        holdings_lookup = {
            item["timestamp"]: item["holdings"]
            for item in self.data["holdings_history"]
        }

        mid_price_lookup = {
            asset_id: {
                item["timestamp"]: item["mid_price"]
                for item in price_history
            }
            for asset_id, price_history in self.data["mid_prices"].items()
        }


        current_cash = self.initial_balance
        current_holdings = {}

        for timestamp in timestamps:
            if timestamp in cash_lookup:
                current_cash = cash_lookup[timestamp]

            if timestamp in holdings_lookup:    #else: last known value
                current_holdings = holdings_lookup[timestamp]

            position_value = 0.0

            for asset_id, shares in current_holdings.items():
                price = mid_price_lookup.get(asset_id, {}).get(timestamp)

                if price is None:
                    price = 0.0

                position_value += shares * price

            self.equity_curve.append(
                EquityPoint(
                    timestamp=timestamp,
                    cash=current_cash,
                    position_value=position_value,
                    equity=current_cash + position_value,
                )
            )

    # largest drop from peak balance (percentage)
    def max_drawdown(self):
        peak = self.initial_balance
        max_dd = 0.0

        for point in self.equity_curve:
            equity = point.equity
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak
            max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def roi(self):
        #final_equity = self.equity_curve[-1].equity
        return (self.data["final_cash"] - self.initial_balance) / self.initial_balance
    
    # total profit/loss
    def pnl(self):
        return  self.data["final_cash"] - self.initial_balance
    
    # biggest winning trade (detects lucky spikes)
    def largest_gain(self):
        if not self.closed_trades:
            return None
        
        return max(trade["profit"] for trade in self.closed_trades)
    
    # biggest losing trade
    def largest_loss(self):
        if not self.closed_trades:
            return None
        
        return min(trade["profit"] for trade in self.closed_trades)
    
    # winning trades / total trades
    def winrate(self):
        if not self.closed_trades:
            return None
        
        wins = sum(trade["profit"] > 0 for trade in self.closed_trades)
        if len(self.closed_trades) > 0:
            return wins / len(self.closed_trades)
        else:
            return None
    
    def average_trade_profit(self):
        if not self.closed_trades:
            return None
        
        return mean(trade["profit"] for trade in self.closed_trades)
    
    # less sensitive to outliers
    def median_trade_profit(self):
        if not self.closed_trades:
            return None
        
        return median(trade["profit"] for trade in self.closed_trades)
    
    # percentage of simulation with no open positions
    def idle_time(self):
        holdings_history = self.data["holdings_history"]
        idle_time = 0
        for i in range(len(holdings_history) - 1):
            duration = holdings_history[i+1]["timestamp"] - holdings_history[i]["timestamp"]

            if all(shares == 0 for shares in holdings_history[i]["holdings"].values()):
                idle_time += duration
        if len(self.data["timestamps"]) < 1:
            return 1.0
        total_time = self.data["timestamps"][-1] - self.data["timestamps"][0]
        idle_fraction = idle_time / total_time
        return idle_fraction
    

    
    def avg_entry_probability(self):
        return None
    
    # average minutes remaining when entering
    def time_before_expiration(self):
        ts_end = self.data["timestamps"][-1]
        sum = 0
        count = 0
        for t in self.data["transactions"]:
            if t["order_action"] == OrderAction.BID:
                sum += ts_end - t["timestamp"]
                count += 1
        if count > 0:
            return sum / count / 1000 / 60
        else:
            return 0
    
    def trade_count(self):
        if not self.closed_trades:
            return 0

        return len(self.closed_trades)
    
    # total profit / total losses (for all trades in one market)
    def profit_factor(self):
        gross_wins = sum(trade["profit"] 
                         for trade in self.closed_trades
                         if trade["profit"] > 0)
        
        gross_losses = sum(trade["profit"] 
                         for trade in self.closed_trades
                         if trade["profit"] < 0)
        
        if gross_losses == 0:
            if gross_wins > 0:
                return float("inf")
            return None
        
        return gross_wins / abs(gross_losses)
        
    
    def total_fees_paid(self):
        return sum(t["fee"] for t in self.data["transactions"])
    
    # makes bots with different balances comparable
    def fees_to_initial_balance_ratio(self):
        return sum(t["fee"] for t in self.data["transactions"]) / self.initial_balance
    
    # ratio: total_fees_paid / gross_pnl (total profit without fees)
    def profit_lost_to_fees(self):
        total_fees = self.total_fees_paid()
        gross_pnl = self.pnl() + total_fees
        if gross_pnl > 0:
            return total_fees / gross_pnl

    # how much money did the bot earn for every dollar spent on fees
    def fee_efficiency(self):
        if self.total_fees_paid() > 0:
            return self.pnl() / self.total_fees_paid()
        else:
            return None
    
    # overtrading metric (how aggressively the bot trades relative to its capital)
    def turnover(self):
        total_traded_volume = sum(
            t["price"] * t["successful_matches"] 
            for t in self.data["transactions"])
        return total_traded_volume / self.initial_balance
    
    def total_traded_volume(self):
        return sum(t["price"] * t["successful_matches"] 
                    for t in self.data["transactions"])
    

    #used for trade related metrics
    def build_closed_trades_fifo(self, transactions, resolution, include_fees=True):
        """
        Converts raw BID/ASK transactions into closed trade records using FIFO.

        Trade definition used:
        - Each ASK transaction becomes one closed trade.
        - If an ASK closes shares from multiple BID lots, it is still one trade.
        - Remaining open shares can be closed at settlement using settlement_price_by_asset.

        settlement_price_by_asset example:
            {
                "asset_id_up": 1.0,
                "asset_id_down": 0.0,
            }
        """

        settlement_price_by_asset = {}  # share prices after resolution

        for asset_id, asset_label in self.data["asset_labels"].items():
            if asset_label == resolution:
                settlement_price_by_asset[asset_id] = 1.0
            else:
                settlement_price_by_asset[asset_id] = 0.0

        open_lots = {}

        for tx in sorted(transactions, key=lambda x: x["timestamp"]):
            asset_id = tx["asset_id"]
            action = tx["order_action"]
            qty = float(tx["successful_matches"])
            price = float(tx["price"])
            fee = float(tx.get("fee", 0.0))

            if asset_id not in open_lots:
                open_lots[asset_id] = deque()

            if action == "BID":
                open_lots[asset_id].append({
                    "qty": qty,
                    "price": price,
                    "timestamp": tx["timestamp"],
                    "fee_remaining": fee,
                })

            elif action == "ASK":
                remaining_to_sell = qty
                cost_basis = 0.0
                entry_fees = 0.0
                earliest_entry_timestamp = None

                while remaining_to_sell >= 0.01:    #0.01 smallest quantity
                    if not open_lots[asset_id]:
                        break
                    #    raise ValueError(f"ASK without enough open holdings for asset {asset_id}")

                    lot = open_lots[asset_id][0]
                    matched_qty = min(remaining_to_sell, lot["qty"])

                    if earliest_entry_timestamp is None:
                        earliest_entry_timestamp = lot["timestamp"]

                    cost_basis += matched_qty * lot["price"]

                    # Allocate BID fee proportionally to the matched quantity
                    fee_fraction = matched_qty / lot["qty"]
                    matched_entry_fee = lot["fee_remaining"] * fee_fraction
                    entry_fees += matched_entry_fee

                    lot["qty"] -= matched_qty
                    lot["fee_remaining"] -= matched_entry_fee
                    remaining_to_sell -= matched_qty

                    if lot["qty"] < 0.01:
                        open_lots[asset_id].popleft()

                proceeds = qty * price  #total money generated from transaction
                gross_profit = proceeds - cost_basis
                total_fees = entry_fees + fee
                net_profit = gross_profit - total_fees if include_fees else gross_profit    # profit (or loss) generated from transaction

                self.closed_trades.append({
                    "asset_id": asset_id,
                    "exit_timestamp": tx["timestamp"],
                    "entry_timestamp": earliest_entry_timestamp,
                    "quantity": qty,
                    "entry_price": cost_basis/qty,
                    "exit_price": price,
                    "proceeds": proceeds,
                    "cost_basis": cost_basis,
                    "gross_profit": gross_profit,
                    "fees": total_fees,
                    "profit": net_profit,
                    "closed_by": "ASK",
                })

        # Close remaining positions at settlement, if provided
        if settlement_price_by_asset is not None:
            for asset_id, lots in open_lots.items():
                settlement_price = settlement_price_by_asset.get(asset_id)

                if settlement_price is None:
                    continue

                total_qty = sum(lot["qty"] for lot in lots)

                if total_qty < 0.01:
                    continue

                cost_basis = 0.0
                entry_fees = 0.0
                earliest_entry_timestamp = None

                while lots:
                    lot = lots.popleft()

                    if earliest_entry_timestamp is None:
                        earliest_entry_timestamp = lot["timestamp"]

                    cost_basis += lot["qty"] * lot["price"]
                    entry_fees += lot["fee_remaining"]

                proceeds = total_qty * settlement_price
                gross_profit = proceeds - cost_basis
                net_profit = gross_profit - entry_fees if include_fees else gross_profit

                self.closed_trades.append({
                    "asset_id": asset_id,
                    "entry_timestamp": earliest_entry_timestamp,
                    "exit_timestamp": None,
                    "quantity": total_qty,
                    "entry_price": cost_basis/total_qty,
                    "exit_price": settlement_price,
                    "proceeds": proceeds,
                    "cost_basis": cost_basis,
                    "gross_profit": gross_profit,
                    "fees": entry_fees,
                    "profit": net_profit,
                    "closed_by": "SETTLEMENT",
                })   
    

    def plot_equity_curve(self):
        # Convert millisecond timestamps to datetime
        times = [
            datetime.fromtimestamp(point.timestamp / 1000)
            for point in self.equity_curve
        ]

        equities = [
            point.equity
            for point in self.equity_curve
        ]

        plt.figure(figsize=(12, 6))
        plt.plot(times, equities)

        plt.title("Equity Curve")
        plt.xlabel("Time")
        plt.ylabel("Equity")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def plot_equity_breakdown(self):
        times = [
            datetime.fromtimestamp(point.timestamp / 1000)
            for point in self.equity_curve
        ]

        equities = [point.equity for point in self.equity_curve]
        cash = [point.cash for point in self.equity_curve]
        position_values = [point.position_value for point in self.equity_curve]

        plt.figure(figsize=(12, 6))
        plt.plot(times, equities, label="Equity")
        plt.plot(times, cash, label="Cash")
        plt.plot(times, position_values, label="Position Value")

        plt.title("Equity Curve Breakdown")
        plt.xlabel("Time")
        plt.ylabel("Value")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()


    def plot_trade_pnl_bars(self):
        closed_trades = self.closed_trades

        profits = [trade["profit"] for trade in closed_trades]

        colors = [
            "green" if p >= 0 else "firebrick"
            for p in profits
        ]

        plt.figure(figsize=(10,4))

        plt.bar(
            range(len(profits)),
            profits,
            color=colors
        )

        plt.axhline(0, color="black")

        plt.xlabel("Trade")
        plt.ylabel("Profit")
        plt.title("Profit per Closed Trade")

        plt.show()


    # Decision quality metrics
    # ========================

    def get_price_window(self, asset_id, start_ts, end_ts=None):
        prices = self.data["mid_prices"].get(asset_id,[])
        
        window = []
        for p in prices:
            ts = p["timestamp"]
            if ts < start_ts:
                continue
            if end_ts is not None and ts > end_ts:
                continue

            window.append(p)
        return window

    # Maximum Adverse Excursion
    # how far price moved against the bot while trade was open
    def entry_mae(self, trade):
        prices = self.get_price_window(trade["asset_id"], trade["entry_timestamp"], trade["exit_timestamp"])

        if not prices:
            return None
        entry_price = trade["entry_price"]
        min_price = min(p["mid_price"] for p in prices)

        return entry_price - min_price
    
    # Maximum Favorable Excursion
    # how far price moved in favor of the bot while trade was open
    def entry_mfe(self, trade):
        prices = self.get_price_window(trade["asset_id"], trade["entry_timestamp"], trade["exit_timestamp"])
        if not prices:
            return None
        
        entry_price = trade["entry_price"]
        max_price = max(p["mid_price"] for p in prices)

        return max_price - entry_price        
    
    # Fraction of the best possible move captured
    def exit_efficiency(self, trade):
        """
        1.0 = exited at best price while trade was open
        0.5 = captured half of available move
        0.0 = no favorable move captured
        """
        prices = self.get_price_window(trade["asset_id"], trade["entry_timestamp"], trade["exit_timestamp"]) 
        if not prices:
            return None
        entry_price = trade["entry_price"]
        exit_price = trade["exit_price"]
        best_price = max(p["mid_price"] for p in prices)

        max_possible_gain = best_price - entry_price
        actual_gain = exit_price - entry_price
        
        if max_possible_gain <= 0:
            return None     # or maybe return 0
        
        return actual_gain / max_possible_gain
    
    # returns true if price improved by more than threshold after exit - exited too early
    # threshold=0.10 means 10 cents on a prediction-market contract
    def was_premature_exit(self, trade, threshold=0.10):
        if trade["exit_timestamp"] is None:     # doesn't count - no exit at all
            return False

        market_end_ts = self.data["timestamps"][-1]     # probably change later
        prices_after_exit = self.get_price_window(trade["asset_id"], trade["exit_timestamp"], market_end_ts)

        if not prices_after_exit:
            return False
        exit_price = trade["exit_price"]
        future_best = max(p["mid_price"] for p in prices_after_exit)

        return (future_best - exit_price >= threshold)
    
    def premature_exit_rate(self, threshold=0.10):
        exited_trades = [t for t in self.closed_trades if t["closed_by"] == "ASK"]  #trades that weren't closed automatically after resolving

        if not exited_trades:
            return None
        premature_count = sum (self.was_premature_exit(trade=t, threshold=threshold) for t in exited_trades)
        return premature_count / len(exited_trades)
    

    # false entry if price moves against the bot by adverse_threshold
    # before it ever moves in favor by favorable_threshold.
    def was_false_entry(self, trade, adverse_threshold=0.10, favorable_threshold=0.05):
        prices = self.get_price_window(trade["asset_id"], trade["entry_timestamp"], trade["exit_timestamp"])
        if not prices:
            return False
        
        entry_price = trade["entry_price"]
        for p in prices:
            move = p["mid_price"] - entry_price
            if move >= favorable_threshold:
                return False
            if move <= -adverse_threshold:
                return True
        return False
    
    def false_entry_rate(self, adverse_threshold=0.10, favorable_threshold=0.05):
        if not self.closed_trades:
            return None
        false_count = sum(self.was_false_entry(trade=t, adverse_threshold=adverse_threshold, favorable_threshold=favorable_threshold) 
                            for t in self.closed_trades)
        return false_count / len(self.closed_trades)
    
    def run_decision_quality_methods(self):
        for trade in self.closed_trades:
            trade["entry_mae"] = self.entry_mae(trade)
            print(trade["entry_mae"])
            trade["entry_mfe"] = self.entry_mfe(trade)
            trade["exit_efficiency"] = self.exit_efficiency(trade)

        summary = {
            "avg_entry_mae": mean_ignore_none(t["entry_mae"] for t in self.closed_trades),
            "avg_entry_mfe": mean_ignore_none(t["entry_mfe"] for t in self.closed_trades),
            "avg_exit_efficiency": mean_ignore_none(t["exit_efficiency"] for t in self.closed_trades),
            "premature_exit_rate": self.premature_exit_rate(threshold=0.10),
            "false_entry_rate": self.false_entry_rate(),
        }
        print(summary)
    

def mean_ignore_none(values):
    values = [v for v in values if v is not None]
    if not values:
        return None

    return sum(values) / len(values)

    
#analyzer = PerformanceAnalyzer(100)
#analyzer.analytics_path = "tmp/single_unit_test/bitcoin-up-or-down-july-4-2026-4am-et.analysis.json"
#analyzer.analytics_path = "tmp/single_unit_test/bitcoin-up-or-down-july-4-2026-4am-et.analysis.json"
#analyzer.analyze()