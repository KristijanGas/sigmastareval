

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
    #adding more later
