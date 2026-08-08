from dataclasses import dataclass
from datetime import date
from analytics.performance_result import PerformanceResult
from statistics import geometric_mean, mean, median, stdev
import matplotlib.pyplot as plt
import math
import numpy as np

from evaluator.utils.utils import extract_market_date

#analyzes data from the whole dataset
class AggregateAnalyzer:
    def __init__(self):
        self.results: list[PerformanceResult] = []  #list of results from each performance analyzer


    def analyze(self):
        #print(self.profitable_markets())
        self.output_table()
        self.output_daily_summaries()
        #self.plot_final_cash_distribution()
        return None

    def add_result(self, result: PerformanceResult):
        self.results.append(result)


    def average_roi(self, results=None):
        if results is None:
            results = self.results

        if len(results) == 0:
            return 0
        rois = [r.roi + 1 for r in results]
        for i in range(len(rois)):
            if rois[i] <= 0:
                rois[i] = 1e-10  # Replace non-positive values with a small positive number
        return geometric_mean(rois) - 1

    def median_roi(self):
        if len(self.results) == 0:
            return 0
        return median(r.roi for r in self.results)
    
    def stdev_roi(self):
        if self.markets_tested() > 1:
            return stdev(r.roi for r in self.results) #function requires at least two data points
        else:
            return None
        
    def min_roi(self):
        if len(self.results) == 0:
            return 0
        return min(r.roi for r in self.results)
    
    def max_roi(self):
        if len(self.results) == 0:
            return 0
        return max(r.roi for r in self.results)
    

    def average_pnl(self, results=None):
        if results is None:
            results = self.results
        if len(results) == 0:
            return 0
        return mean(r.pnl for r in results)
    
    def median_pnl(self):
        if len(self.results) == 0:
            return 0
        return median(r.pnl for r in self.results)
    
    def stdev_pnl(self):
        if self.markets_tested() > 1:
            return stdev(r.pnl for r in self.results)
        else:
            return None
    
    def min_pnl(self):
        if len(self.results) == 0:
            return 0
        return min(r.pnl for r in self.results)
    
    def max_pnl(self):
        if len(self.results) == 0:
            return 0
        return max(r.pnl for r in self.results)

    def total_pnl(self):
        if len(self.results) == 0:
            return 0
        return sum(r.pnl for r in self.results)
    

    def average_max_drawdown(self):
        if len(self.results) == 0:
            return 0
        return mean(r.max_drawdown for r in self.results)
    
    def median_max_drawdown(self):
        if len(self.results) == 0:
            return 0
        return median(r.max_drawdown for r in self.results)
    
    def stdev_max_drawdown(self):
        if self.markets_tested() > 1:
            return stdev(r.max_drawdown for r in self.results)
        else:
            return None
        
    #area between the curve and y=0
    def negative_sum(self):
        losing_markets = [r.pnl for r in self.results if r.pnl < 0]
        if len(losing_markets) == 0:
            return 0
        else:
            return sum(losing_markets)
    
    # highest max drawdown (across all tested markets)
    def worst_drawdown(self):
        if len(self.results) == 0:
            return 0
        return max(r.max_drawdown for r in self.results)
    
    def minimal_max_drawdown(self):
        if len(self.results) == 0:
            return 0
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
        if len(self.results) == 0:
            return 0
        return mean(r.idle_time for r in self.results)
    
    def median_idle_time(self):
        if len(self.results) == 0:
            return 0
        return median(r.idle_time for r in self.results)
    
    def stdev_idle_time(self):
        if self.markets_tested() > 1:
            return stdev(r.idle_time for r in self.results)
        else:
            return None
    
    def min_idle_time(self):
        if len(self.results) == 0:
            return 0
        return min(r.idle_time for r in self.results)
    
    def max_idle_time(self):
        if len(self.results) == 0:
            return 0
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
        if len(self.results) == 0:
            return 0
        return sum(r.pnl > 0 for r in self.results) / self.markets_tested()
    
    def losing_markets(self):
        if len(self.results) == 0:
            return 0
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

    # (profitable, not-profitable) x (up won, down won)
    def profit_vs_resolution_matrix(self):
        matrix = []
        first_row = [0,0]
        second_row = [0,0]
        for r in self.results:
            if r.pnl > 0 and r.resolution == "Up":
                first_row[0] += 1
            elif r.pnl > 0 and r.resolution == "Down":
                first_row[1] += 1
            elif r.pnl <= 0 and r.resolution == "Up":
                second_row[0] += 1
            elif r.pnl <= 0 and r.resolution == "Down":
                second_row[1] += 1

        matrix.append(first_row)
        matrix.append(second_row)

        return matrix


    
    def get_daily_summaries(self):
        daily_results: dict[date, list] = {}
        for r in self.results:
            market_date = extract_market_date(r.market_name)
            if daily_results.get(market_date) is None:
                daily_results[market_date] = []
            daily_results[market_date].append(r)
        
        daily_summaries: list[DailySummary] = []
        for market_date in sorted(daily_results.keys()):
            results = daily_results[market_date]

            markets_tested = len(results)
            profitable_markets = sum(r.pnl > 0 for r in results)
            daily_summary = DailySummary(
                market_date=market_date,
                markets_tested=markets_tested,
                total_pnl=sum(r.pnl for r in results),
                average_pnl=self.average_pnl(results),
                average_roi=self.average_roi(results),
                median_roi=median(r.roi for r in results),
                profitable_markets=profitable_markets,
                profitable_market_rate=profitable_markets/markets_tested,
                average_max_drawdown=mean(r.max_drawdown for r in results)
            )
            daily_summaries.append(daily_summary)
        return daily_summaries
            
            
        

    
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
            [round(self.average_roi() * 100,3), round(self.median_roi() * 100,3), stdev_roi, round(self.min_roi() * 100,3), round(self.max_roi() * 100,3)],
            [round(self.average_pnl(),2), round(self.median_pnl(),2), stdev_pnl, round(self.min_pnl(),2), round(self.max_pnl(),2)],
            [round(self.average_max_drawdown() * 100,2), round(self.median_max_drawdown() * 100,2), stdev_max_dd, round(self.minimal_max_drawdown() * 100,2), round(self.worst_drawdown() * 100,2)],
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
            f"Profitable:           {sum(r.pnl > 0 for r in self.results)} ({round(self.profitable_markets()*100,2)}%)\n"
            f"Losing:               {sum(r.pnl < 0 for r in self.results)} ({round(self.losing_markets()*100,2)}%)\n"
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
            f"Best ROI:          {round(self.max_roi()*100,2)}%\n"
            f"Worst ROI:         {round(self.min_roi()*100,2)}%\n"
            f"Largest Profit:    {round(self.max_pnl(),2)}\n"
            f"Largest Loss:      {round(self.min_pnl(),2)}\n"
            f"Highest Drawdown:  {round(self.worst_drawdown()*100,2)}%\n"
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

        cash_fee_pairs = [(r.final_cash, r.total_fees_paid) for r in self.results]
        cash_fee_pairs.sort(key=lambda x: x[0])
        cash = [x[0] for x in cash_fee_pairs]
        fee = [x[1] for x in cash_fee_pairs]
        #print(cash_fee_pairs)
        #cash = np.sort([r.final_cash for r in self.results])
        x = np.linspace(0, 100, len(cash_fee_pairs))

        initial_balance = 100
        ax_curve.plot(x, cash, linewidth=2, label="final cash")
        #ax_curve.plot(x, fee, linewidth=2, label="Total fees paid")
        ax_curve.axhline(initial_balance, linestyle="--", color="gray",
                        label="Initial balance")

        ax_curve.set_title("Final Cash Distribution")
        ax_curve.set_xlabel("Market Percentile")
        ax_curve.set_ylabel("Final Cash")
        ax_curve.grid(alpha=0.3)
        ax_curve.legend()

        ax_curve_twin = ax_curve.twinx()
        ax_curve_twin.plot(
            x,
            fee,
            color="#A31414",
            linewidth=1.2,
            alpha=0.8,
            label="Total fees paid",
        )
        ax_curve_twin.set_ylabel("Total fees paid")
        ax_curve_twin.tick_params(axis="y", labelcolor="#000000")
        ax_curve_twin.legend()

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


    def output_daily_summaries(self):
        daily_summaries = self.get_daily_summaries()

        daily_columns = [
            "Date",
            "Markets",
            "Total PnL",
            "Avg PnL",
            "Avg ROI",
            "Median ROI",
            "Profitable",
            "Avg Drawdown",
        ]

        daily_values = [
            [
                summary.market_date.strftime("%B %d, %Y"),
                summary.markets_tested,
                f"{summary.total_pnl:.2f}",
                f"{summary.average_pnl:.2f}",
                f"{summary.average_roi:.2%}",
                f"{summary.median_roi:.2%}",
                (
                    f"{summary.profitable_markets}/{summary.markets_tested} "
                    f"({summary.profitable_market_rate:.1%})"
                ),
                f"{summary.average_max_drawdown:.2%}",
            ]
            for summary in daily_summaries
        ]


        fig = plt.figure(figsize=(11, 10))
        gs = fig.add_gridspec(
            nrows=2,
            ncols=1,
            height_ratios=[7,3]
        )

        fig.suptitle("Daily Summaries", fontsize=18, fontweight="bold")

        ax_table = fig.add_subplot(gs[0, :])
        ax_table.axis("off")
        daily_table = ax_table.table(
            cellText=daily_values,
            colLabels=daily_columns,
            cellLoc="center",
            bbox=[0.0, 0.02, 1.0, 0.6],
        )

        # daily_table.auto_set_font_size(False)
        # daily_table.set_fontsize(12)
        # daily_table.scale(1, 1.5)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()



@dataclass
class DailySummary:
    market_date: date
    markets_tested: int
    total_pnl: float
    average_pnl: float
    average_roi: float
    median_roi: float
    profitable_markets: int
    profitable_market_rate: float
    average_max_drawdown: float