from datetime import date, timedelta

import pytest

from src.models.trade import Price
from src.services.metrics import (
    align_series,
    alpha_annualized,
    beta,
    cagr,
    daily_returns,
    max_drawdown_pct,
    sharpe_ratio,
    total_return_pct,
    volatility_annualized,
)


def _prices(closes, start=date(2024, 1, 2)):
    return [
        Price(ticker="X", date=start + timedelta(days=i), close=c)
        for i, c in enumerate(closes)
    ]


# ── daily_returns ────────────────────────────────────────────────────────────


def test_daily_returns_basic():
    prices = _prices([100.0, 110.0, 99.0])
    returns = daily_returns(prices)
    assert len(returns) == 2
    assert returns[0] == pytest.approx(0.10, rel=1e-4)
    assert returns[1] == pytest.approx(99.0 / 110.0 - 1, rel=1e-4)


def test_daily_returns_empty_or_single():
    assert daily_returns([]) == []
    assert daily_returns(_prices([100.0])) == []


# ── total_return_pct ─────────────────────────────────────────────────────────


def test_total_return_pct():
    assert total_return_pct(_prices([100.0, 150.0])) == pytest.approx(50.0)


def test_total_return_pct_edge_cases():
    assert total_return_pct([]) == 0.0
    assert total_return_pct(_prices([100.0])) == 0.0
    assert total_return_pct(_prices([0.0, 100.0])) == 0.0


# ── cagr ─────────────────────────────────────────────────────────────────────


def test_cagr_one_year():
    start = date(2023, 1, 2)
    end = start + timedelta(days=365)
    prices = [
        Price(ticker="X", date=start, close=100.0),
        Price(ticker="X", date=end, close=110.0),
    ]
    assert cagr(prices) == pytest.approx(0.10, rel=0.01)


# ── volatility ───────────────────────────────────────────────────────────────


def test_volatility_zero_on_flat_series():
    prices = _prices([100.0, 100.0, 100.0, 100.0])
    assert volatility_annualized(daily_returns(prices)) == pytest.approx(0.0)


# ── sharpe ───────────────────────────────────────────────────────────────────


def test_sharpe_zero_when_flat():
    prices = _prices([100.0, 100.0, 100.0])
    assert sharpe_ratio(daily_returns(prices)) == pytest.approx(0.0)


# ── max_drawdown ─────────────────────────────────────────────────────────────


def test_max_drawdown():
    prices = _prices([100.0, 120.0, 80.0, 110.0])
    dd = max_drawdown_pct(prices)
    assert dd == pytest.approx((80.0 - 120.0) / 120.0 * 100, rel=1e-4)


def test_max_drawdown_empty_or_single():
    assert max_drawdown_pct([]) == 0.0
    assert max_drawdown_pct(_prices([100.0])) == 0.0


# ── beta ─────────────────────────────────────────────────────────────────────


def test_beta_of_benchmark_against_itself_is_one():
    prices = _prices([100.0, 105.0, 103.0, 108.0, 107.0])
    returns = daily_returns(prices)
    assert beta(returns, returns) == pytest.approx(1.0, abs=1e-10)


# ── align_series ─────────────────────────────────────────────────────────────


def test_align_series_intersects_dates():
    a = [
        Price(ticker="A", date=date(2024, 1, 1), close=100.0),
        Price(ticker="A", date=date(2024, 1, 2), close=101.0),
        Price(ticker="A", date=date(2024, 1, 3), close=102.0),
    ]
    b = [
        Price(ticker="B", date=date(2024, 1, 2), close=200.0),
        Price(ticker="B", date=date(2024, 1, 3), close=201.0),
        Price(ticker="B", date=date(2024, 1, 4), close=202.0),
    ]
    aligned_a, aligned_b = align_series(a, b)
    assert len(aligned_a) == 2
    assert len(aligned_b) == 2
    assert [p.date for p in aligned_a] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert [p.date for p in aligned_b] == [date(2024, 1, 2), date(2024, 1, 3)]


# ── alpha ─────────────────────────────────────────────────────────────────────


def test_alpha_is_zero_when_portfolio_equals_benchmark():
    prices = _prices([100.0, 102.0, 104.0, 103.0, 106.0])
    assert alpha_annualized(prices, prices) == pytest.approx(0.0, abs=1e-10)


def test_alpha_positive_when_portfolio_outperforms_market_neutrally():
    # Flat benchmark → zero returns → var == 0 → beta returns 0.0
    # Portfolio grows steadily → CAGR >> rf → alpha = CAGR - rf > 0
    benchmark = _prices([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    portfolio = _prices([100.0, 102.0, 104.0, 106.0, 108.0, 110.0])
    assert alpha_annualized(portfolio, benchmark) > 0
