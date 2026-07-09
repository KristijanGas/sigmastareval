import json
from analytics.equity_point import EquityPoint
from analytics.performance_result import PerformanceResult
import matplotlib.pyplot as plt
from datetime import datetime
from bot.order_actions import OrderAction
from collections import deque
from statistics import mean, median

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
        with open(self.analytics_path, "r", encoding="utf-8") as f:
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
        #self.plot_equity_breakdown()
        #self.plot_equity_curve()
        # analyze here
        return self.performance_result
    
    def generate_equity_curve(self):

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
        return wins / len(self.closed_trades)
    
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
        
        total_time = self.data["timestamps"][-1] - self.data["timestamps"][0]
        idle_fraction = idle_time / total_time
        return idle_fraction
    
    # how close was the entry price to the best available price later?
    def entry_timing(self):
        return None
    
    # average entry price relative to subsequent price movement
    # how good the entry price was compared with future prices
    def entry_quality(self):
        return None
    
    # how close was the selling price to the best available price later?
    # did a bot exit near a local best price
    def exit_timing(self):
        return None
    
    # average exit price relative to subsequent price movement
    # how good the exit price was compared with prices before/after exit
    def exit_quality(self):
        return None
    
    # entries that quickly moved against the bot and never recovered much
    def false_entries(self):
        return None
    
    # exits followed by a significantly better price soon after
    def premature_exits(self):
        return None
    
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
            return None

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
        return total_fees / gross_pnl

    # how much money did the bot earn for every dollar spent on fees
    def fee_efficiency(self):
        return self.pnl() / self.total_fees_paid()
    
    # overtrading metric (how aggressively the bot trades relative to its capital)
    def turnover(self):
        total_traded_volume = sum(
            t["price"] * t["successful_matches"] 
            for t in self.data["transactions"])
        return total_traded_volume / self.initial_balance
    

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
                        raise ValueError(f"ASK without enough open holdings for asset {asset_id}")

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

    
#analyzer = PerformanceAnalyzer(100)
#analyzer.analytics_path = "tmp/single_unit_test/bitcoin-up-or-down-july-4-2026-4am-et.analysis.json"
#analyzer.analytics_path = "tmp/single_unit_test/bitcoin-up-or-down-july-4-2026-4am-et.analysis.json"
#analyzer.analyze()