import logging
from datetime import date, timedelta
from typing import List, Optional

from src.models.trade import Price

logger = logging.getLogger(__name__)

POPULAR_BENCHMARKS = [
    {"ticker": "^GSPC", "label": "S&P 500"},
    {"ticker": "^IXIC", "label": "NASDAQ Composite"},
    {"ticker": "QQQ", "label": "Nasdaq-100 ETF"},
    {"ticker": "DIA", "label": "Dow Jones ETF"},
    {"ticker": "^RUT", "label": "Russell 2000"},
    {"ticker": "SPY", "label": "S&P 500 ETF"},
]

TIME_RANGE_DAYS = {
    "1D": 1,
    "5D": 5,
    "1M": 30,
    "6M": 182,
    "1Y": 365,
    "5Y": 1825,
}


def get_date_range(range_str: str, reference: Optional[date] = None) -> tuple[date, date]:
    end = reference or date.today()
    if range_str == "MAX":
        start = date(2010, 1, 1)
    elif range_str == "YTD":
        start = date(end.year, 1, 1)
    else:
        days = TIME_RANGE_DAYS.get(range_str)
        if days is None:
            logger.warning("Unknown range %r — falling back to 1Y", range_str)
            days = 365
        start = end - timedelta(days=days)
    return start, end


def normalize_returns(prices: List[Price]) -> List[dict]:
    """
    Normalize a price series to percentage return from the first data point.
    Returns list of {date, value} where value is cumulative % return.
    """
    if not prices:
        return []
    base = prices[0].close
    if base == 0:
        return []
    return [
        {"date": p.date.isoformat(), "value": round((p.close / base - 1) * 100, 4)}
        for p in prices
    ]


def benchmark_return_pct(prices: List[Price]) -> float:
    if len(prices) < 2:
        return 0.0
    start = prices[0].close
    end = prices[-1].close
    if start == 0:
        return 0.0
    return ((end - start) / start) * 100


