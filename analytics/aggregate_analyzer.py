from analytics.performance_result import PerformanceResult
from statistics import mean, median, stdev
import matplotlib.pyplot as plt

#analyzes data from the whole dataset
class AggregateAnalyzer:
    def __init__(self,):
        self.results: list[PerformanceResult] = []  #list of results from each performance analyzer


    def analyze(self):
        #print(self.profitable_markets())
        #self.output_table()
        return None

    def add_result(self, result: PerformanceResult):
        self.results.append(result)


    def average_roi(self):
        return mean(r.roi for r in self.results)
    
    def median_roi(self):
        return median(r.roi for r in self.results)
    
    def stdev_roi(self):
        if self.markets_tested() > 1:
            return stdev(r.roi for r in self.results) #function requires at least two data points
        else:
            return None
        
    def min_roi(self):
        return min(r.roi for r in self.results)
    
    def max_roi(self):
        return max(r.roi for r in self.results)
    
    def average_pnl(self):
        return mean(r.pnl for r in self.results)
    
    def median_pnl(self):
        return median(r.pnl for r in self.results)
    
    def stdev_pnl(self):
        if self.markets_tested() > 1:
            return stdev(r.pnl for r in self.results)
        else:
            return None
    
    def min_pnl(self):
        return min(r.pnl for r in self.results)
    
    def max_pnl(self):
        return max(r.pnl for r in self.results)

    def total_pnl(self):
        return sum(r.pnl for r in self.results)
    
    def average_max_drawdown(self):
        return mean(r.max_drawdown for r in self.results)
    
    def median_max_drawdown(self):
        return median(r.max_drawdown for r in self.results)
    
    def stdev_max_drawdown(self):
        if self.markets_tested() > 1:
            return stdev(r.max_drawdown for r in self.results)
        else:
            return None
    
    # highest max drawdown (across all tested markets)
    def worst_drawdown(self):
        return max(r.max_drawdown for r in self.results)
    
    def minimal_max_drawdown(self):
        return min(r.max_drawdown for r in self.results)
    
    # ratio
    def profitable_markets(self):
        return sum(r.pnl > 0 for r in self.results) / self.markets_tested()
    
    def average_profit_factor(self):
        return None
        
    def average_trades_count(self):
        return None    

    def sharpe_ratio(self):
        return None
        
    def average_time_before_exp(self):
        return None
    
    # bot's evaluated score
    def composite_score(self):
        return None
    
    def markets_tested(self):
        return len(self.results)
    
    #just for testing
    def output_table(self):
        stdev_roi = "-"
        stdev_pnl = "-"
        stdev_max_dd = "-"
        if self.stdev_roi() is not None:
            stdev_roi = round(self.stdev_roi(),2)
        if self.stdev_pnl() is not None:
            stdev_pnl = round(self.stdev_pnl(),2)
        if self.stdev_max_drawdown() is not None:
            stdev_max_dd = round(self.stdev_max_drawdown(),2)

        values = [
            [round(self.average_roi(),2), round(self.median_roi(),2), stdev_roi, round(self.min_roi(),2), round(self.max_roi(),2)],
            [round(self.average_pnl(),2), round(self.median_pnl(),2), stdev_pnl, round(self.min_pnl(),2), round(self.max_pnl(),2)],
            [round(self.average_max_drawdown(),2), round(self.median_max_drawdown(),2), stdev_max_dd, round(self.minimal_max_drawdown(),2), round(self.worst_drawdown(),2)],
        ]
        columns = ["Mean", "Median", "Std Dev", "Min", "Max"]
        rows = ["ROI (%)", "Pnl ($)", "Max Drawdown (%)"]

        fig, ax = plt.subplots()
        ax.axis("off")

        table = ax.table(
            cellText=values,
            colLabels=columns,
            rowLabels=rows,
            loc="center",
        )

        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1, 1.5)

        plt.tight_layout()
        plt.show()
