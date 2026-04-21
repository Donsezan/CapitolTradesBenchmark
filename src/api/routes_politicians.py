from datetime import date
from fastapi import APIRouter, HTTPException, Query, Request

from src.db.repositories import PoliticianRepository, PriceRepository, TradeRepository
from src.services.portfolio_calc import calculate_portfolio

router = APIRouter()


@router.get("/politicians")
async def list_politicians(request: Request):
    db = request.app.state.db
    repo = PoliticianRepository(db)
    return await repo.get_all_with_trade_counts()


@router.get("/politicians/{politician_id}/trades")
async def get_politician_trades(politician_id: int, request: Request):
    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    politician = await pol_repo.get_by_id(politician_id)
    if politician is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    trade_repo = TradeRepository(db)
    trades = await trade_repo.get_by_politician(politician_id)
    return [t.model_dump() for t in trades]


@router.get("/politicians/{politician_id}/portfolio")
async def get_politician_portfolio(politician_id: int, request: Request):
    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    politician = await pol_repo.get_by_id(politician_id)
    if politician is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    trade_repo = TradeRepository(db)
    price_repo = PriceRepository(db)
    trades = await trade_repo.get_by_politician(politician_id)

    if not trades:
        return {"politician_id": politician_id, "holdings": [], "current_value": 0, "return_pct": 0}

    tickers = list({t.ticker for t in trades})
    today = date.today()
    earliest = min(t.trade_date for t in trades)
    prices_by_ticker: dict = {}
    for ticker in tickers:
        series = await price_repo.get_range(ticker, earliest, today)
        if series:
            prices_by_ticker[ticker] = series

    if not prices_by_ticker:
        return {"politician_id": politician_id, "holdings": [], "current_value": 0, "return_pct": 0}

    portfolio = calculate_portfolio(trades, prices_by_ticker, as_of=today)
    return portfolio.model_dump()


@router.get("/leaderboard")
async def get_leaderboard(
    request: Request,
    sort_by: str = Query(
        "return_pct",
        pattern="^(return_pct|current_value|realized_pnl|unrealized_pnl)$",
    ),
    limit: int = Query(20, ge=1, le=100),
):
    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    trade_repo = TradeRepository(db)
    price_repo = PriceRepository(db)

    politicians = await pol_repo.get_all()
    today = date.today()
    results = []

    for politician in politicians:
        if politician.id is None:
            continue
        trades = await trade_repo.get_by_politician(politician.id)
        if not trades:
            continue

        tickers = list({t.ticker for t in trades})
        earliest = min(t.trade_date for t in trades)
        prices_by_ticker: dict = {}
        for ticker in tickers:
            series = await price_repo.get_range(ticker, earliest, today)
            if series:
                prices_by_ticker[ticker] = series

        if not prices_by_ticker:
            continue

        portfolio = calculate_portfolio(trades, prices_by_ticker, as_of=today)
        if portfolio.current_value <= 0:
            continue

        results.append({
            "politician_id": politician.id,
            "name": politician.name,
            "party": politician.party,
            "chamber": politician.chamber,
            "current_value": round(portfolio.current_value, 2),
            "total_cost": round(portfolio.total_cost, 2),
            "realized_pnl": round(portfolio.realized_pnl, 2),
            "unrealized_pnl": round(portfolio.unrealized_pnl, 2),
            "return_pct": round(portfolio.return_pct, 2),
        })

    results.sort(key=lambda x: x[sort_by], reverse=True)
    return results[:limit]
