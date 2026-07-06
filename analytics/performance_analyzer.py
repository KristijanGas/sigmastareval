import json
from analytics.performance_result import PerformanceResult

# performance analyzer for one market run
class PerformanceAnalyzer:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.analytics_path = None
        self.equity_curve = []
        self.performance_result = None

    def analyze(self):
        self.performance_result = PerformanceResult()
        with open(self.analytics_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        #print(data.get("order_placements", []) or [])
        # analyze here
        return self.performance_result

    def max_drawdown(self):
        return None
    
    def roi(self):
        return None
    
    # total profit/loss
    def pnl(self):
        return None
    
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
    

    
