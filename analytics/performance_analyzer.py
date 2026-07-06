import json
from analytics.equity_point import EquityPoint
from analytics.performance_result import PerformanceResult

# performance analyzer for one market run
class PerformanceAnalyzer:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.analytics_path = None
        self.equity_curve = []
        self.performance_result = None
        self.data = None

    def analyze(self):
        self.performance_result = PerformanceResult()
        with open(self.analytics_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.generate_equity_curve()
        print(self.max_drawdown())
        #print(self.data.get("order_placements", []) or [])
        #print("ROI:")
        #print(self.roi())
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
    
    def largest_gain(self):
        return None
    
    def largest_loss(self):
        return None
    
    # winning trades / total trades
    def win_rate(self):
        return None
    
    def average_trade_profit(self):
        return None
    
    # less sensitive to outliers
    def median_trade_profit(self):
        return None
    
    # percentage of simulation with no open positions
    def idle_time(self):
        return None
    
    # how close was the entry price to the best available price later?
    def entry_timing(self):
        return None
    
    # average entry price relative to subsequent price movement
    def entry_quality(self):
        return None
    
    # how close was the selling price to the best available price later?
    def exit_timing(self):
        return None
    
    # average exit price relative to subsequent price movement
    def exit_quality(self):
        return None
    
    def false_entries(self):
        return None
    
    def premature_exits(self):
        return None
    
    def avg_entry_probability(self):
        return None
    
    # average minutes remaining when entering
    def time_before_expiration(self):
        return None
    

    
