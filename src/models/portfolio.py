from datetime import date
from typing import List, Optional

from pydantic import BaseModel, computed_field


class Holding(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    current_price: float

    @computed_field
    @property
    def current_value(self) -> float:
        return self.shares * self.current_price

    @computed_field
    @property
    def cost_basis(self) -> float:
        return self.shares * self.avg_cost

    @computed_field
    @property
    def unrealized_pnl(self) -> float:
        return self.current_value - self.cost_basis

    @computed_field
    @property
    def return_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100


class ProfitRecord(BaseModel):
    ticker: str
    realized_pnl: float
    trade_date: date


class Portfolio(BaseModel):
    politician_id: int
    current_value: float
    total_cost: float
    realized_pnl: float
    unrealized_pnl: float
    return_pct: float
    holdings: List[Holding] = []
    profit_records: Optional[List[ProfitRecord]] = None
