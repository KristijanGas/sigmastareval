from analytics.performance_result import PerformanceResult
from statistics import mean, median, stdev
import matplotlib.pyplot as plt
import math
import numpy as np

#analyzes data from the whole dataset
class AggregateAnalyzer:
    def __init__(self):
        self.results: list[PerformanceResult] = []  #list of results from each performance analyzer


    def analyze(self):
        #print(self.profitable_markets())
        self.output_table()
        #self.plot_final_cash_distribution()
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
    

    def average_trade_count(self):
        values = [r.trade_count for r in self.results]
        clean_values = self.clean(values)
        if len(clean_values) == 0:
            return 0
        return mean(clean_values)
    
    def median_trade_count(self):
        values = [r.trade_count for r in self.results]
        clean_values = self.clean(values)
        if len(clean_values) == 0:
            return 0
        return median(clean_values)
    
    def stdev_trade_count(self):
        values = [r.trade_count for r in self.results]
        clean_values = self.clean(values)
        if self.markets_tested() > 1 and len(clean_values) > 1:
            return stdev(clean_values)
        else:
            return None
    
    def min_trade_count(self):
        values = [r.trade_count for r in self.results]
        clean_values = self.clean(values)
        if len(clean_values) == 0:
            return 0
        return min(clean_values)
    
    def max_trade_count(self):
        values = [r.trade_count for r in self.results]
        clean_values = self.clean(values)
        if len(clean_values) == 0:
            return 0
        return max(clean_values)
    

    def average_idle_time(self):
        return mean(r.idle_time for r in self.results)
    
    def median_idle_time(self):
        return median(r.idle_time for r in self.results)
    
    def stdev_idle_time(self):
        if self.markets_tested() > 1:
            return stdev(r.idle_time for r in self.results)
        else:
            return None
    
    def min_idle_time(self):
        return min(r.idle_time for r in self.results)
    
    def max_idle_time(self):
        return max(r.idle_time for r in self.results)


    def clean(self, values):
        return [v for v in values if v is not None and math.isfinite(v)]
    
    def clean_none(self, values):
        return [v for v in values if v is not None]

    def average_profit_factor(self):
        valid_profit_factors = self.clean([r.profit_factor for r in self.results])
        if len(valid_profit_factors) == 0:
            return 0
        return mean(valid_profit_factors)
    
    def median_profit_factor(self):
        valid_profit_factors = self.clean([r.profit_factor for r in self.results])
        if len(valid_profit_factors) == 0:
            return 0
        return median(valid_profit_factors)
    
    def stdev_profit_factor(self):
        values = [r.profit_factor for r in self.results]
        valid_profit_factors = self.clean(values)
        if self.markets_tested() > 1 and len(valid_profit_factors) > 1:
            return stdev(valid_profit_factors)
        else:
            return None
    
    def min_profit_factor(self):
        valid_profit_factors = self.clean([r.profit_factor for r in self.results])
        if len(valid_profit_factors) == 0:
            return 0
        return min(valid_profit_factors)
    
    def max_profit_factor(self):
        values = [r.profit_factor for r in self.results]
        clean_values = self.clean_none(values)
        if len(clean_values) == 0:
            return 0
        return max(clean_values)
    
    # ratio
    def profitable_markets(self):
        return sum(r.pnl > 0 for r in self.results) / self.markets_tested()
    
    def losing_markets(self):
        return sum(r.pnl < 0 for r in self.results) / self.markets_tested()

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
        stdev_trades = "-"
        stdev_idle_time = "-"
        stdev_profit_factor = "-"
        if self.stdev_roi() is not None:
            stdev_roi = round(self.stdev_roi(),2)
        if self.stdev_pnl() is not None:
            stdev_pnl = round(self.stdev_pnl(),2)
        if self.stdev_max_drawdown() is not None:
            stdev_max_dd = round(self.stdev_max_drawdown(),2)
        if self.stdev_trade_count() is not None:
            stdev_trades = round(self.stdev_trade_count(), 2)
        if self.stdev_idle_time() is not None:
            stdev_idle_time = round(self.stdev_idle_time(), 2) 
        if self.stdev_profit_factor() is not None:
            stdev_profit_factor = round(self.stdev_profit_factor(), 2) 

        values = [
            [round(self.average_roi(),2), round(self.median_roi(),2), stdev_roi, round(self.min_roi(),2), round(self.max_roi(),2)],
            [round(self.average_pnl(),2), round(self.median_pnl(),2), stdev_pnl, round(self.min_pnl(),2), round(self.max_pnl(),2)],
            [round(self.average_max_drawdown(),2), round(self.median_max_drawdown(),2), stdev_max_dd, round(self.minimal_max_drawdown(),2), round(self.worst_drawdown(),2)],
            [round(self.average_trade_count(),2), round(self.median_trade_count(),2), stdev_trades, round(self.min_trade_count(),2), round(self.max_trade_count(),2)],
            [round(self.average_idle_time(),2), round(self.median_idle_time(),2), stdev_idle_time, round(self.min_idle_time(),2), round(self.max_idle_time(),2)],
            [round(self.average_profit_factor(),2), round(self.median_profit_factor(),2), stdev_profit_factor, round(self.min_profit_factor(),2), round(self.max_profit_factor(),2)],
        ]
        columns = ["Mean", "Median", "Std Dev", "Min", "Max"]
        rows = ["ROI (%)", "Pnl ($)", "Max Drawdown (%)", "Trades", "Idle Time (%)", "Profit Factor"]


        fig = plt.figure(figsize=(11, 10))
        gs = fig.add_gridspec(
            nrows=4,
            ncols=2,
            height_ratios=[4, 0.9, 0.9, 3]
        )

        fig.suptitle("Bot Analysis", fontsize=18, fontweight="bold")

        # ---------------- Table ----------------
        ax_table = fig.add_subplot(gs[0, :])
        ax_table.axis("off")

        table = ax_table.table(
            cellText=values,
            colLabels=columns,
            rowLabels=rows,
            loc="center",
            cellLoc="center"
        )

        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1, 1.5)

        # Success statistics
        success_text = (
            "Success Statistics\n"
            "──────────────────────────────\n"
            f"Markets Tested:       {self.markets_tested()}\n"
            f"Profitable:           {sum(r.pnl > 0 for r in self.results)} ({round(self.profitable_markets(),2)*100}%)\n"
            f"Losing:               {sum(r.pnl < 0 for r in self.results)} ({round(self.losing_markets(),2)*100}%)\n"
            f"No Trades:            {sum(r.trade_count == 0 for r in self.results)}\n"
        )       


        ax_success = fig.add_subplot(gs[1, 0])
        ax_success.axis("off")
        ax_success.text(
            0, 1,
            success_text,
            family="monospace",
            fontsize=11,
            va="top"
        )

        # Extreme cases
        extreme_text = (
            "Extreme Cases\n"
            "──────────────────────────────\n"
            f"Best ROI:          {round(self.max_roi(),2)}%\n"
            f"Worst ROI:         {round(self.min_roi(),2)}%\n"
            f"Largest Profit:    {round(self.max_pnl(),2)}\n"
            f"Largest Loss:      {round(self.min_pnl(),2)}\n"
            f"Highest Drawdown:  {round(self.worst_drawdown(),2)}%\n"
        )

        ax_extreme = fig.add_subplot(gs[1, 1])
        ax_extreme.axis("off")
        ax_extreme.text(
            0, 1,
            extreme_text,
            family="monospace",
            fontsize=11,
            va="top"
        )

        #ax_curve = fig.add_subplot(gs[3, :])

        ax_curve = fig.add_axes([
            0.18,   # left
            0.06,   # bottom
            0.64,   # width
            0.25    # height
        ])

        cash = np.sort([r.final_cash for r in self.results])
        x = np.linspace(0, 100, len(cash))

        initial_balance = 100
        ax_curve.plot(x, cash, linewidth=2, label="Final cash")
        ax_curve.axhline(initial_balance, linestyle="--", color="gray",
                        label="Initial balance")

        ax_curve.set_title("Final Cash Distribution")
        ax_curve.set_xlabel("Market Percentile")
        ax_curve.set_ylabel("Final Cash")
        ax_curve.grid(alpha=0.3)
        ax_curve.legend()

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()


    def plot_final_cash_distribution(self, initial_balance=100):
        # Sort outcomes
        final_cash_values = [r.final_cash for r in self.results]
        cash = np.sort(np.asarray(final_cash_values))

        # X-axis is simply the market rank
        x = np.arange(1, len(cash) + 1)

        plt.figure(figsize=(9, 5))
        plt.plot(x, cash, linewidth=2, label="Final cash")

        # Optional: show initial balance
        if initial_balance is not None:
            plt.axhline(
                initial_balance,
                color="gray",
                linestyle="--",
                label="Initial balance"
            )

        plt.xlabel("Markets (sorted by final cash)")
        plt.ylabel("Final cash")
        plt.title("Distribution of Final Cash Across Markets")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()