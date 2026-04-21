from datetime import date
from typing import List

from fastapi import APIRouter, HTTPException, Query, Request

from config import RISK_FREE_RATE
from src.db.repositories import PoliticianRepository, PriceRepository, TradeRepository
from src.models.trade import Price
from src.services import metrics as metrics_svc
from src.services.index_compare import benchmark_return_pct, get_date_range, normalize_returns
from src.services.portfolio_calc import (
    calculate_portfolio,
    calculate_portfolio_daily_series,
    calculate_return_for_range,
)

router = APIRouter()


def _price_fetch_start(trades, start_date: date) -> date:
    """Return the earliest date we need prices from to correctly price all trades."""
    if not trades:
        return start_date
    earliest = min(t.trade_date for t in trades)
    return min(earliest, start_date)


def _portfolio_prices(politician_id: int, daily_series: List[dict]) -> List[Price]:
    return [
        Price(
            ticker=f"POL_{politician_id}",
            date=date.fromisoformat(d["date"]),
            close=100.0 + d["value"],
        )
        for d in daily_series
    ]


def _politician_metrics(
    politician_id: int,
    daily_series: List[dict],
    benchmark_prices: List[Price],
) -> dict:
    port_prices = _portfolio_prices(politician_id, daily_series)
    if len(port_prices) < 2:
        return {"volatility": 0.0, "sharpe": 0.0, "max_drawdown_pct": 0.0, "beta": 0.0, "alpha": 0.0}

    port_returns = metrics_svc.daily_returns(port_prices)
    b = 0.0
    if len(benchmark_prices) >= 2:
        aligned_port, aligned_bench = metrics_svc.align_series(port_prices, benchmark_prices)
        if len(aligned_port) >= 2:
            b = metrics_svc.beta(
                metrics_svc.daily_returns(aligned_port),
                metrics_svc.daily_returns(aligned_bench),
            )

    return {
        "volatility": round(metrics_svc.volatility_annualized(port_returns), 4),
        "sharpe": round(metrics_svc.sharpe_ratio(port_returns, RISK_FREE_RATE), 4),
        "max_drawdown_pct": round(metrics_svc.max_drawdown_pct(port_prices), 4),
        "beta": round(b, 4),
        "alpha": round(
            metrics_svc.alpha_annualized(port_prices, benchmark_prices, RISK_FREE_RATE), 4
        ),
    }


def _benchmark_metrics(benchmark_prices: List[Price]) -> dict:
    if len(benchmark_prices) < 2:
        return {"volatility": 0.0, "sharpe": 0.0, "max_drawdown_pct": 0.0}
    bench_returns = metrics_svc.daily_returns(benchmark_prices)
    return {
        "volatility": round(metrics_svc.volatility_annualized(bench_returns), 4),
        "sharpe": round(metrics_svc.sharpe_ratio(bench_returns, RISK_FREE_RATE), 4),
        "max_drawdown_pct": round(metrics_svc.max_drawdown_pct(benchmark_prices), 4),
    }


@router.get("/leaderboard")
async def leaderboard(
    request: Request,
    range: str = Query(default="1Y", description="Time range: 1D 5D 1M 6M YTD 1Y 5Y MAX"),
    benchmark: str = Query(default="^GSPC"),
    mode: str = Query(default="trade", pattern="^(trade|filing)$"),
):
    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    trade_repo = TradeRepository(db)
    price_repo = PriceRepository(db)

    start_date, end_date = get_date_range(range)
    use_filing_date = mode == "filing"
    politicians = await pol_repo.get_all()

    results = []
    for pol in politicians:
        trades = await trade_repo.get_by_politician(pol.id)
        if not trades:
            continue

        prices_by_ticker: dict = {}
        price_start = _price_fetch_start(trades, start_date)
        for ticker in {t.ticker for t in trades}:
            series = await price_repo.get_range(ticker, price_start, end_date)
            if series:
                prices_by_ticker[ticker] = series

        if not prices_by_ticker:
            continue

        portfolio = calculate_portfolio(
            trades, prices_by_ticker, as_of=end_date, use_filing_date=use_filing_date
        )
        ret_pct = calculate_return_for_range(
            trades, prices_by_ticker, start_date, end_date, use_filing_date=use_filing_date
        )

        results.append({
            "politician_id": pol.id,
            "name": pol.name,
            "party": pol.party,
            "chamber": pol.chamber,
            "return_pct": round(ret_pct, 2),
            "current_value": round(portfolio.current_value, 2),
            "trade_count": len(trades),
        })

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


@router.get("/comparison")
async def comparison(
    request: Request,
    ticker: str = Query(default="^GSPC", description="Benchmark ticker"),
    range: str = Query(default="1Y"),
    politician_ids: str = Query(default="", description="Comma-separated politician IDs"),
    mode: str = Query(default="trade", pattern="^(trade|filing)$"),
):
    db = request.app.state.db
    price_repo = PriceRepository(db)
    trade_repo = TradeRepository(db)
    pol_repo = PoliticianRepository(db)

    start_date, end_date = get_date_range(range)
    use_filing_date = mode == "filing"

    benchmark_prices = await price_repo.get_range(ticker, start_date, end_date)
    benchmark_series = normalize_returns(benchmark_prices)
    bench_ret = benchmark_return_pct(benchmark_prices)

    politician_series = []
    ids = [int(i) for i in politician_ids.split(",") if i.strip().isdigit()]
    for pol_id in ids:
        pol = await pol_repo.get_by_id(pol_id)
        if pol is None:
            continue
        trades = await trade_repo.get_by_politician(pol_id)
        if not trades:
            continue

        prices_by_ticker = {}
        price_start = _price_fetch_start(trades, start_date)
        for t in {tr.ticker for tr in trades}:
            series = await price_repo.get_range(t, price_start, end_date)
            if series:
                prices_by_ticker[t] = series

        ret_pct = calculate_return_for_range(
            trades, prices_by_ticker, start_date, end_date, use_filing_date=use_filing_date
        )
        daily_series = calculate_portfolio_daily_series(
            trades, prices_by_ticker, start_date, end_date, use_filing_date=use_filing_date
        )

        politician_series.append({
            "politician_id": pol_id,
            "name": pol.name,
            "party": pol.party,
            "return_pct": round(ret_pct, 2),
            "series": daily_series,
            "metrics": _politician_metrics(pol_id, daily_series, benchmark_prices),
        })

    return {
        "benchmark": {
            "ticker": ticker,
            "series": benchmark_series,
            "return_pct": round(bench_ret, 2),
            "metrics": _benchmark_metrics(benchmark_prices),
        },
        "politicians": politician_series,
        "range": range,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


@router.get("/politicians/{politician_id}/metrics")
async def politician_metrics(
    politician_id: int,
    request: Request,
    benchmark: str = Query(default="^GSPC"),
    range: str = Query(default="1Y"),
    mode: str = Query(default="trade", pattern="^(trade|filing)$"),
):
    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    trade_repo = TradeRepository(db)
    price_repo = PriceRepository(db)

    pol = await pol_repo.get_by_id(politician_id)
    if pol is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    trades = await trade_repo.get_by_politician(politician_id)
    if not trades:
        raise HTTPException(status_code=404, detail="No trades found for politician")

    start_date, end_date = get_date_range(range)
    use_filing_date = mode == "filing"

    prices_by_ticker: dict = {}
    price_start = _price_fetch_start(trades, start_date)
    for ticker_sym in {t.ticker for t in trades}:
        series = await price_repo.get_range(ticker_sym, price_start, end_date)
        if series:
            prices_by_ticker[ticker_sym] = series

    benchmark_prices = await price_repo.get_range(benchmark, start_date, end_date)

    daily_series = calculate_portfolio_daily_series(
        trades, prices_by_ticker, start_date, end_date, use_filing_date=use_filing_date
    )
    port_prices = _portfolio_prices(politician_id, daily_series)

    bench_out: dict = {}
    if len(benchmark_prices) >= 2:
        bench_returns = metrics_svc.daily_returns(benchmark_prices)
        bench_out = {
            "ticker": benchmark,
            "total_return_pct": round(metrics_svc.total_return_pct(benchmark_prices), 4),
            "cagr": round(metrics_svc.cagr(benchmark_prices), 4),
            "volatility": round(metrics_svc.volatility_annualized(bench_returns), 4),
            "sharpe": round(metrics_svc.sharpe_ratio(bench_returns, RISK_FREE_RATE), 4),
            "max_drawdown_pct": round(metrics_svc.max_drawdown_pct(benchmark_prices), 4),
        }

    port_out: dict = {}
    if len(port_prices) >= 2:
        port_returns = metrics_svc.daily_returns(port_prices)
        b = 0.0
        if len(benchmark_prices) >= 2:
            aligned_port, aligned_bench = metrics_svc.align_series(port_prices, benchmark_prices)
            if len(aligned_port) >= 2:
                b = metrics_svc.beta(
                    metrics_svc.daily_returns(aligned_port),
                    metrics_svc.daily_returns(aligned_bench),
                )
        port_out = {
            "total_return_pct": round(metrics_svc.total_return_pct(port_prices), 4),
            "cagr": round(metrics_svc.cagr(port_prices), 4),
            "volatility": round(metrics_svc.volatility_annualized(port_returns), 4),
            "sharpe": round(metrics_svc.sharpe_ratio(port_returns, RISK_FREE_RATE), 4),
            "max_drawdown_pct": round(metrics_svc.max_drawdown_pct(port_prices), 4),
            "beta": round(b, 4),
            "alpha": round(
                metrics_svc.alpha_annualized(port_prices, benchmark_prices, RISK_FREE_RATE), 4
            ),
        }

    return {
        "politician_id": politician_id,
        "name": pol.name,
        "range": range,
        "mode": mode,
        "benchmark": bench_out,
        "portfolio": port_out,
    }
