from datetime import date
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, computed_field


class TradeType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Trade(BaseModel):
    id: Optional[int] = None
    politician_id: int
    politician_name: Optional[str] = None
    party: Optional[str] = None
    chamber: Optional[str] = None
    ticker: str
    asset_name: Optional[str] = None
    trade_type: Literal["BUY", "SELL"]
    amount_from: float
    amount_to: float
    trade_date: date
    filing_date: date

    @computed_field
    @property
    def midpoint(self) -> float:
        return (self.amount_from + self.amount_to) / 2

    @computed_field
    @property
    def dedup_key(self) -> tuple:
        return (
            self.politician_id,
            self.ticker,
            self.trade_date,
            self.amount_from,
            self.amount_to,
            self.trade_type,
        )


class Price(BaseModel):
    ticker: str
    date: date
    close: float
