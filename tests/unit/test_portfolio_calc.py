from datetime import date

import pytest

from src.models.trade import Price, Trade
from src.services.portfolio_calc import calculate_portfolio, calculate_return_for_range


def _trade(ticker, trade_date, filing_date, amount_from=40_000, amount_to=60_000, trade_type="BUY"):
    return Trade(
        politician_id=1,
        ticker=ticker,
        trade_type=trade_type,
        amount_from=amount_from,
        amount_to=amount_to,
        trade_date=date.fromisoformat(trade_date),
        filing_date=date.fromisoformat(filing_date),
    )


def _prices(ticker, date_close_pairs):
    return [Price(ticker=ticker, date=date.fromisoformat(d), close=c) for d, c in date_close_pairs]


# ── §1 bug fix: shares fixed at trade-date price ──────────────────────────────


def test_shares_fixed_at_trade_date_price_not_current():
    """Shares must be computed at trade-date price, not current/as-of price."""
    trade = _trade("NVDA", "2024-01-02", "2024-01-10")
    prices = {
        "NVDA": _prices("NVDA", [("2024-01-02", 500.0), ("2024-06-01", 1000.0)])
    }
    p = calculate_portfolio([trade], prices, as_of=date(2024, 6, 1))
    # midpoint $50k / $500 trade-date price = 100 shares; now worth $1000 → $100k
    assert p.holdings[0].shares == pytest.approx(100.0)
    assert p.current_value == pytest.approx(100_000, rel=0.001)
    assert p.unrealized_pnl == pytest.approx(50_000, rel=0.001)


# ── §3 filing-date mode ───────────────────────────────────────────────────────


def test_filing_date_mode_uses_filing_date_price():
    """use_filing_date=True fixes shares at filing_date price, not trade_date price."""
    trade = _trade("AAPL", "2024-01-02", "2024-01-10")
    prices = {
        "AAPL": _prices("AAPL", [
            ("2024-01-02", 100.0),   # trade-date price
            ("2024-01-10", 200.0),   # filing-date price (2x higher)
            ("2024-06-01", 200.0),   # as-of price
        ])
    }
    # trade-date: shares = 50k/100 = 500 → value = 500 * 200 = 100k
    p_trade = calculate_portfolio([trade], prices, as_of=date(2024, 6, 1), use_filing_date=False)
    # filing-date: shares = 50k/200 = 250 → value = 250 * 200 = 50k
    p_filing = calculate_portfolio([trade], prices, as_of=date(2024, 6, 1), use_filing_date=True)

    assert p_trade.holdings[0].shares == pytest.approx(500.0)
    assert p_filing.holdings[0].shares == pytest.approx(250.0)
    assert p_trade.current_value != pytest.approx(p_filing.current_value)


def test_use_filing_date_excludes_undisclosed_trade():
    """A trade with filing_date > start_date is invisible in filing-date mode."""
    # trade_date=2024-01-10, filing_date=2024-01-25; check window starts 2024-01-15
    trade = _trade("MSFT", "2024-01-10", "2024-01-25")
    prices = {
        "MSFT": _prices("MSFT", [
            ("2024-01-10", 400.0),
            ("2024-01-25", 420.0),
            ("2024-06-01", 440.0),
        ])
    }
    # start=2024-01-15 is after trade_date but before filing_date
    ret_trade = calculate_return_for_range(
        [trade], prices, date(2024, 1, 15), date(2024, 6, 1), use_filing_date=False
    )
    ret_filing = calculate_return_for_range(
        [trade], prices, date(2024, 1, 15), date(2024, 6, 1), use_filing_date=True
    )
    # trade-date mode: trade is visible → non-zero return
    # filing-date mode: trade not yet disclosed → no holdings → 0%
    assert ret_trade != pytest.approx(0.0)
    assert ret_filing == pytest.approx(0.0)
