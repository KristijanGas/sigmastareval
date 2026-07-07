from dataclasses import dataclass


@dataclass
class EquityPoint:
    timestamp: int
    cash: float
    position_value: float
    equity: float