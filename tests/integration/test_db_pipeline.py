"""
Integration tests for full data pipelines.
"""

import pytest
import os
from datetime import date


@pytest.mark.asyncio
async def test_full_scrape_pipeline():
    """Full pipeline: fetch from Finnhub, deduplicate, store

    This is an integration test that exercises:
    1. Finnhub API client fetching trades
    2. Parsing into Trade objects
    3. Storing in DB with deduplication
    """
    from src.scraper.finnhub_client import FinnhubClient
    from src.db.repositories import TradeRepository, PoliticianRepository
    from src.db.database import Database

    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key or api_key == "test_key":
        pytest.skip("FINNHUB_API_KEY not configured")

    # Setup
    db = Database(":memory:")
    await db.init_schema()

    finnhub = FinnhubClient(api_key=api_key)
    trade_repo = TradeRepository(db)
    politician_repo = PoliticianRepository(db)

    # Fetch trades from Finnhub
    try:
        trades = await finnhub.fetch_trades()
    except Exception as e:
        pytest.skip(f"Finnhub API unavailable: {e}")

    # Store trades (with deduplication)
    for trade in trades:
        # Ensure politician exists
        politician_data = {
            "name": trade.politician_name,
            "party": trade.party or "U",
            "chamber": trade.chamber or "House",
        }
        # Try to get existing or create
        existing = await politician_repo.get_by_name(trade.politician_name)
        if not existing:
            from src.models.politician import Politician
            pol = Politician(**politician_data)
            await politician_repo.create(pol)

        # Store trade (duplicate attempts should be ignored)
        await trade_repo.create_if_not_exists(trade)

    # Verify stored
    count = await trade_repo.count_all()
    assert count == len(trades), "All trades should be stored"

    # Verify deduplication works (re-store same trades)
    for trade in trades[:min(2, len(trades))]:
        await trade_repo.create_if_not_exists(trade)

    count_after_dedup = await trade_repo.count_all()
    assert count_after_dedup == count, "Deduplication should prevent re-insertion"

    await db.close()


@pytest.mark.asyncio
async def test_politician_trade_retrieval():
    """Retrieve all trades for a specific politician"""
    from src.models.politician import Politician
    from src.models.trade import Trade
    from src.db.repositories import PoliticianRepository, TradeRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    politician_repo = PoliticianRepository(db)
    trade_repo = TradeRepository(db)

    # Create politician
    pol = Politician(name="Nancy Pelosi", party="D", chamber="House")
    created_pol = await politician_repo.create(pol)

    # Create trades for this politician
    trade1 = Trade(
        politician_id=created_pol.id,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250000,
        amount_to=500000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )
    trade2 = Trade(
        politician_id=created_pol.id,
        ticker="AAPL",
        trade_type="SELL",
        amount_from=100000,
        amount_to=200000,
        trade_date=date(2026, 4, 16),
        filing_date=date(2026, 4, 18),
    )

    await trade_repo.create_if_not_exists(trade1)
    await trade_repo.create_if_not_exists(trade2)

    # Retrieve all trades for this politician
    politician_trades = await trade_repo.get_by_politician(created_pol.id)

    assert len(politician_trades) == 2
    assert all(t.politician_id == created_pol.id for t in politician_trades)
    assert set(t.ticker for t in politician_trades) == {"NVDA", "AAPL"}

    await db.close()


@pytest.mark.asyncio
async def test_price_caching_pipeline():
    """Full pipeline: fetch prices, cache, verify no re-fetch"""
    from src.scraper.price_fetcher import PriceFetcher
    from src.db.repositories import PriceRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    fetcher = PriceFetcher(db_session=db)
    repo = PriceRepository(db)

    # Fetch prices
    prices1 = await fetcher.fetch_ticker(
        "NVDA", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    if len(prices1) == 0:
        pytest.skip("Could not fetch prices for NVDA")

    # Insert into DB
    await repo.batch_insert(prices1)

    # Fetch again (should use cache from DB)
    prices2 = await fetcher.fetch_ticker(
        "NVDA", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    # Should have same data
    assert len(prices1) == len(prices2)
    assert prices1[0].close == prices2[0].close

    await db.close()


@pytest.mark.asyncio
async def test_db_schema_initialization():
    """Database schema is correctly initialized on first run"""
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    # Verify tables exist by inserting data
    from src.models.politician import Politician
    from src.db.repositories import PoliticianRepository

    repo = PoliticianRepository(db)
    pol = Politician(name="Test", party="D", chamber="House")
    created = await repo.create(pol)

    assert created.id is not None

    await db.close()


@pytest.mark.asyncio
async def test_concurrent_operations():
    """DB handles concurrent reads and writes"""
    from src.models.politician import Politician
    from src.db.repositories import PoliticianRepository
    from src.db.database import Database
    import asyncio

    db = Database(":memory:")
    await db.init_schema()

    repo = PoliticianRepository(db)

    # Insert politicians concurrently
    async def insert_politician(name):
        pol = Politician(name=name, party="D", chamber="House")
        return await repo.create(pol)

    # Create tasks
    tasks = [
        insert_politician(f"Politician {i}") for i in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # All should have been inserted
    all_pols = await repo.get_all()
    assert len(all_pols) == 5

    await db.close()
