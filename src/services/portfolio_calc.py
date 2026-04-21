from bisect import bisect_right
from datetime import date
from typing import List, Optional

from src.models.trade import Trade, Price
from src.models.portfolio import Portfolio, Holding, ProfitRecord


def _price_on_or_before(
    prices_by_ticker: dict[str, List[Price]], ticker: str, as_of: date
) -> Optional[float]:
    """Return the most recent closing price on or before as_of, using binary search."""
    series = prices_by_ticker.get(ticker, [])
    if not series:
        return None
    # Series must be sorted ascending by date (repositories return them that way).
    dates = [p.date for p in series]
    idx = bisect_right(dates, as_of) - 1
    return series[idx].close if idx >= 0 else None


def calculate_portfolio(
    trades: List[Trade],
    prices_by_ticker: dict[str, List[Price]],
    as_of: date,
    use_filing_date: bool = False,
) -> Portfolio:
    """
    Reconstruct a politician's portfolio from their trade history.
    Shares are fixed at the reference-date price (trade_date or filing_date)
    so the calculation remains arithmetically correct across different as_of windows.
    """
    holdings: dict[str, dict] = {}
    realized_pnl = 0.0
    profit_records: List[ProfitRecord] = []

    for trade in sorted(trades, key=lambda t: t.trade_date):
        ref_date = trade.filing_date if use_filing_date else trade.trade_date
        if ref_date > as_of:
            continue

        ticker = trade.ticker
        trade_price = _price_on_or_before(prices_by_ticker, ticker, ref_date)
        if not trade_price or trade_price <= 0:
            continue

        shares = trade.midpoint / trade_price

        if trade.trade_type == "BUY":
            if ticker not in holdings:
                holdings[ticker] = {"shares": 0.0, "total_cost": 0.0}
            holdings[ticker]["shares"] += shares
            holdings[ticker]["total_cost"] += trade.midpoint

        elif trade.trade_type == "SELL" and ticker in holdings and holdings[ticker]["shares"] > 0:
            avg_cost = holdings[ticker]["total_cost"] / holdings[ticker]["shares"]
            shares_sold = min(shares, holdings[ticker]["shares"])
            pnl = (trade_price - avg_cost) * shares_sold
            realized_pnl += pnl
            profit_records.append(
                ProfitRecord(
                    ticker=ticker,
                    realized_pnl=pnl,
                    trade_date=ref_date,
                )
            )
            holdings[ticker]["shares"] -= shares_sold
            holdings[ticker]["total_cost"] -= avg_cost * shares_sold
            if holdings[ticker]["shares"] <= 0:
                del holdings[ticker]

    holding_objects: List[Holding] = []
    total_cost = 0.0
    current_value = 0.0
    unrealized_pnl = 0.0

    for ticker, data in holdings.items():
        if data["shares"] <= 0:
            continue
        cp = _price_on_or_before(prices_by_ticker, ticker, as_of) or 0.0
        avg_cost = data["total_cost"] / data["shares"]
        h = Holding(ticker=ticker, shares=data["shares"], avg_cost=avg_cost, current_price=cp)
        holding_objects.append(h)
        total_cost += h.cost_basis
        current_value += h.current_value
        unrealized_pnl += h.unrealized_pnl

    total_invested = total_cost
    return_pct = (
        (current_value - total_invested) / total_invested * 100 if total_invested > 0 else 0.0
    )

    return Portfolio(
        politician_id=trades[0].politician_id if trades else 0,
        current_value=current_value,
        total_cost=total_cost,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        return_pct=return_pct,
        holdings=holding_objects,
        profit_records=profit_records,
    )


def calculate_portfolio_daily_series(
    trades: List[Trade],
    prices_by_ticker: dict[str, List[Price]],
    start_date: date,
    end_date: date,
    use_filing_date: bool = False,
) -> List[dict]:
    """
    Build a daily time-weighted return (TWR) series for a politician's portfolio.

    TWR isolates stock-picking performance from the size of contributions:
    BUY/SELL trades add or remove shares at their reference-date price and
    do NOT register as growth. Only price movements of held positions
    contribute to the return. This makes the series directly comparable
    to a benchmark index (S&P 500, etc.).

    The per-day return is (V_pre_trade_today - V_post_trade_yesterday) /
    V_post_trade_yesterday; daily returns are chained geometrically.
    Returns [{date, value}] where value is cumulative TWR % from the first
    day the portfolio has an open position.
    """
    events: list[tuple[date, str, float]] = []  # (ref_date, ticker, delta_shares)
    for trade in trades:
        ref_date = trade.filing_date if use_filing_date else trade.trade_date
        trade_price = _price_on_or_before(prices_by_ticker, trade.ticker, ref_date)
        if not trade_price or trade_price <= 0:
            continue
        shares = trade.midpoint / trade_price
        delta = -shares if trade.trade_type == "SELL" else shares
        events.append((ref_date, trade.ticker, delta))
    events.sort(key=lambda e: e[0])

    all_dates = sorted({
        p.date
        for series in prices_by_ticker.values()
        for p in series
        if start_date <= p.date <= end_date
    })
    if not all_dates:
        return []

    def mark_to_market(holdings: dict[str, float], d: date) -> float:
        return sum(
            shares * cp
            for ticker, shares in holdings.items()
            if shares > 0 and (cp := _price_on_or_before(prices_by_ticker, ticker, d))
        )

    holdings: dict[str, float] = {}
    event_idx = 0
    cumulative_growth = 1.0
    prev_value_post = 0.0
    has_started = False
    series: list[dict] = []

    for d in all_dates:
        value_pre = mark_to_market(holdings, d)

        if prev_value_post > 0:
            daily_return = (value_pre - prev_value_post) / prev_value_post
            cumulative_growth *= 1.0 + daily_return

        while event_idx < len(events) and events[event_idx][0] <= d:
            _, ticker, delta = events[event_idx]
            holdings[ticker] = holdings.get(ticker, 0.0) + delta
            event_idx += 1

        value_post = mark_to_market(holdings, d)

        if value_post > 0 or has_started:
            has_started = True
            series.append({
                "date": d.isoformat(),
                "value": round((cumulative_growth - 1.0) * 100, 4),
            })

        prev_value_post = value_post

    return series


def calculate_return_for_range(
    trades: List[Trade],
    prices_by_ticker: dict[str, List[Price]],
    start_date: date,
    end_date: date,
    use_filing_date: bool = False,
) -> float:
    """Calculate return % for a politician over a specific date range."""
    start_port = calculate_portfolio(
        trades, prices_by_ticker, as_of=start_date, use_filing_date=use_filing_date
    )
    end_port = calculate_portfolio(
        trades, prices_by_ticker, as_of=end_date, use_filing_date=use_filing_date
    )
    if start_port.current_value <= 0:
        return 0.0
    return (end_port.current_value - start_port.current_value) / start_port.current_value * 100
