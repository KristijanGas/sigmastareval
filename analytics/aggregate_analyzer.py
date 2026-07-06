from analytics.performance_result import PerformanceResult
from statistics import mean, median, stdev

#analyzes data from the whole dataset
class AggregateAnalyzer:
    def __init__(self,):
        self.results: list[PerformanceResult] = []  #list of results from each performance analyzer


    def add_result(self, result: PerformanceResult):
        self.results.append(result)


    def average_roi(self):
        return None
    
    def median_roi(self):
        return None
    
    def stdev_roi(self):
        return None
    
    def average_pnl(self):
        return None
    
    def average_max_drawdown(self):
        return None
    
    def worst_drawdown(self):
        return None
    
    # ratio
    def profitable_markets(self):
        return None
    
    def profit_factor(self):
        return None
        
    def sharpe_ratio(self):
        return None
        
    def average_time_before_exp(self):
        return None
    
    # bot's evaluated score
    def composite_score(self):
        return None