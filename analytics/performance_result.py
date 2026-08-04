

# performance analysis data for one market calculated from performance analyzers
class PerformanceResult:
    market_name: str
    roi: float
    pnl: float
    max_drawdown: float
    profit_factor: float
    trader: int
    trade_count: int
    idle_time: float
    equity_curve: list[tuple[int,float]]
    final_cash: float
    total_fees_paid: float
    winrate: float
    avg_trade_profit: float
    median_trade_profit: float
    largest_gain: float
    largest_loss: float
    time_before_exp_min: float
    fees_to_balance: float
    profit_lost_to_fees: float
    fee_efficiency: float
    turnover: float
    total_traded_volume: float
    #adding more later
