from __future__ import annotations

from math import sqrt
from statistics import mean, stdev, variance
from typing import List, Tuple

from src.models.trade import Price

TRADING_DAYS_PER_YEAR = 252
DEFAULT_RISK_FREE_RATE = 0.04  # 4% annual; override via RISK_FREE_RATE env var


def daily_returns(prices: List[Price]) -> List[float]:
    """Simple daily returns: (P_t / P_{t-1}) - 1. Length = len(prices) - 1."""
    if len(prices) < 2:
        return []
    return [(prices[i].close / prices[i - 1].close) - 1 for i in range(1, len(prices))]


def align_series(a: List[Price], b: List[Price]) -> Tuple[List[Price], List[Price]]:
    """Return two price lists restricted to the intersection of their trading dates."""
    dates_a = {p.date for p in a}
    common = sorted(d for d in (p.date for p in b) if d in dates_a)
    a_map = {p.date: p for p in a}
    b_map = {p.date: p for p in b}
    return [a_map[d] for d in common], [b_map[d] for d in common]


def total_return_pct(prices: List[Price]) -> float:
    """(last/first - 1) * 100. Returns 0.0 if <2 points or first price is 0."""
    if len(prices) < 2 or prices[0].close == 0:
        return 0.0
    return (prices[-1].close / prices[0].close - 1) * 100


def cagr(prices: List[Price]) -> float:
    """Compound annual growth rate using calendar days / 365.25."""
    if len(prices) < 2 or prices[0].close == 0:
        return 0.0
    years = (prices[-1].date - prices[0].date).days / 365.25
    if years <= 0:
        return 0.0
    return (prices[-1].close / prices[0].close) ** (1 / years) - 1


def volatility_annualized(returns: List[float]) -> float:
    """stdev(daily returns) * sqrt(252). Uses sample stdev (ddof=1)."""
    if len(returns) < 2:
        return 0.0
    sd = stdev(returns)
    return sd * sqrt(TRADING_DAYS_PER_YEAR)


def sharpe_ratio(
    returns: List[float], risk_free_rate: float = DEFAULT_RISK_FREE_RATE
) -> float:
    """((mean_daily - rf_daily) / stdev_daily) * sqrt(252). Returns 0.0 if stdev is 0."""
    if len(returns) < 2:
        return 0.0
    sd = stdev(returns)
    if sd == 0:
        return 0.0
    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    return (mean(returns) - rf_daily) / sd * sqrt(TRADING_DAYS_PER_YEAR)


def max_drawdown_pct(prices: List[Price]) -> float:
    """Largest peak-to-trough percent drop. Always <= 0. Returns 0.0 if <2 points."""
    if len(prices) < 2:
        return 0.0
    running_peak = prices[0].close
    max_dd = 0.0
    for p in prices[1:]:
        running_peak = max(running_peak, p.close)
        if running_peak > 0:
            dd = (p.close - running_peak) / running_peak
            max_dd = min(max_dd, dd)
    return max_dd * 100


def beta(portfolio_returns: List[float], benchmark_returns: List[float]) -> float:
    """cov(p, b) / var(b). Inputs must be aligned and equal length. Returns 0.0 if var(b) == 0."""
    if len(portfolio_returns) < 2 or len(portfolio_returns) != len(benchmark_returns):
        return 0.0
    var_b = variance(benchmark_returns)
    if var_b == 0:
        return 0.0
    n = len(portfolio_returns)
    p_mean = mean(portfolio_returns)
    b_mean = mean(benchmark_returns)
    cov = (
        sum((portfolio_returns[i] - p_mean) * (benchmark_returns[i] - b_mean) for i in range(n))
        / (n - 1)
    )
    return cov / var_b


def alpha_annualized(
    portfolio_prices: List[Price],
    benchmark_prices: List[Price],
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float:
    """CAPM alpha, annualized. Returns as a decimal (0.05 = 5%)."""
    aligned_port, aligned_bench = align_series(portfolio_prices, benchmark_prices)
    if len(aligned_port) < 2:
        return 0.0
    pr = daily_returns(aligned_port)
    br = daily_returns(aligned_bench)
    b = beta(pr, br)
    port_cagr = cagr(aligned_port)
    bench_cagr = cagr(aligned_bench)
    return port_cagr - (risk_free_rate + b * (bench_cagr - risk_free_rate))
