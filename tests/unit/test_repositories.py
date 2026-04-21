"""
Unit tests for database repositories (CRUD operations).
"""

import pytest
from datetime import date


@pytest.mark.asyncio
async def test_create_politician():
    """Politicians can be inserted and retrieved"""
    from src.models.politician import Politician
    from src.db.repositories import PoliticianRepository
    from src.db.database import Database

    # Create in-memory DB for testing
    db = Database(":memory:")
    await db.init_schema()

    repo = PoliticianRepository(db)
    p = Politician(name="Nancy Pelosi", party="D", chamber="House")
    created = await repo.create(p)

    # Should return the created politician with an ID
    assert created.id is not None
    assert created.name == "Nancy Pelosi"

    # Should be able to retrieve it
    result = await repo.get_by_name("Nancy Pelosi")
    assert result is not None
    assert result.name == "Nancy Pelosi"

    await db.close()


@pytest.mark.asyncio
async def test_get_all_politicians():
    """Get all politicians from DB"""
    from src.models.politician import Politician
    from src.db.repositories import PoliticianRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = PoliticianRepository(db)

    # Insert multiple politicians
    p1 = Politician(name="Nancy Pelosi", party="D", chamber="House")
    p2 = Politician(name="Mitch McConnell", party="R", chamber="Senate")

    await repo.create(p1)
    await repo.create(p2)

    # Get all
    all_pols = await repo.get_all()
    assert len(all_pols) == 2

    await db.close()


@pytest.mark.asyncio
async def test_trade_deduplication():
    """Duplicate trades are not re-inserted"""
    from src.models.trade import Trade
    from src.db.repositories import TradeRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = TradeRepository(db)

    t = Trade(
        politician_id=1,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250000,
        amount_to=500000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )

    # Insert same trade twice
    await repo.create_if_not_exists(t)
    await repo.create_if_not_exists(t)

    # Should only have one trade
    count = await repo.count_by_politician(1)
    assert count == 1

    await db.close()


@pytest.mark.asyncio
async def test_get_trades_by_politician():
    """Retrieve all trades for a politician"""
    from src.models.trade import Trade
    from src.db.repositories import TradeRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = TradeRepository(db)

    # Insert trades for politician 1
    t1 = Trade(
        politician_id=1,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250000,
        amount_to=500000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )
    t2 = Trade(
        politician_id=1,
        ticker="AAPL",
        trade_type="SELL",
        amount_from=100000,
        amount_to=200000,
        trade_date=date(2026, 4, 16),
        filing_date=date(2026, 4, 18),
    )

    await repo.create_if_not_exists(t1)
    await repo.create_if_not_exists(t2)

    # Get all trades for politician 1
    trades = await repo.get_by_politician(1)
    assert len(trades) == 2
    assert trades[0].ticker in ("NVDA", "AAPL")

    await db.close()


@pytest.mark.asyncio
async def test_batch_price_insert():
    """Multiple prices inserted efficiently"""
    from src.models.trade import Price
    from src.db.repositories import PriceRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = PriceRepository(db)

    prices = [
        Price(ticker="NVDA", date=date(2026, 4, 15), close=875.50),
        Price(ticker="NVDA", date=date(2026, 4, 16), close=878.20),
        Price(ticker="AAPL", date=date(2026, 4, 15), close=150.25),
    ]

    # Batch insert
    await repo.batch_insert(prices)

    # Verify all were inserted
    count = await repo.count()
    assert count == 3

    await db.close()


@pytest.mark.asyncio
async def test_get_latest_price():
    """Get latest price for a ticker"""
    from src.models.trade import Price
    from src.db.repositories import PriceRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = PriceRepository(db)

    # Insert multiple prices for same ticker (different dates)
    prices = [
        Price(ticker="NVDA", date=date(2026, 4, 15), close=875.50),
        Price(ticker="NVDA", date=date(2026, 4, 16), close=878.20),
        Price(ticker="NVDA", date=date(2026, 4, 17), close=882.00),
    ]

    await repo.batch_insert(prices)

    # Get latest
    latest = await repo.get_latest("NVDA")
    assert latest.close == 882.00
    assert latest.date == date(2026, 4, 17)

    await db.close()


@pytest.mark.asyncio
async def test_price_cache_avoids_duplicates():
    """Same price for same ticker/date is not re-inserted"""
    from src.models.trade import Price
    from src.db.repositories import PriceRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = PriceRepository(db)

    # Insert same price twice
    p = Price(ticker="NVDA", date=date(2026, 4, 15), close=875.50)
    await repo.insert_if_not_exists(p)
    await repo.insert_if_not_exists(p)

    # Should only have one price
    count = await repo.count()
    assert count == 1

    await db.close()


@pytest.mark.asyncio
async def test_create_subscription():
    """Subscription can be created and retrieved"""
    from src.models.subscription import TelegramSubscription
    from src.db.repositories import SubscriptionRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = SubscriptionRepository(db)

    sub = TelegramSubscription(
        politician_id=1,
        telegram_chat_id="123456789",
        active=True,
    )

    created = await repo.create(sub)
    assert created.id is not None
    assert created.politician_id == 1

    # Retrieve it
    result = await repo.get_by_id(created.id)
    assert result.telegram_chat_id == "123456789"

    await db.close()


@pytest.mark.asyncio
async def test_get_active_subscriptions():
    """Get only active subscriptions"""
    from src.models.subscription import TelegramSubscription
    from src.db.repositories import SubscriptionRepository
    from src.db.database import Database

    db = Database(":memory:")
    await db.init_schema()

    repo = SubscriptionRepository(db)

    # Create active and inactive subscriptions
    sub1 = TelegramSubscription(
        politician_id=1, telegram_chat_id="111", active=True
    )
    sub2 = TelegramSubscription(
        politician_id=2, telegram_chat_id="222", active=False
    )

    await repo.create(sub1)
    await repo.create(sub2)

    # Get active only
    active = await repo.get_active()
    assert len(active) == 1
    assert active[0].politician_id == 1

    await db.close()
