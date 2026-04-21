"""
Unit tests for data models (Pydantic schemas).
"""

from datetime import date

import pytest


# These tests will work once we implement the models
# For now, they define the expected API


def test_politician_model_valid():
    """Politician can be created with required fields"""
    from src.models.politician import Politician

    p = Politician(name="Nancy Pelosi", party="D", chamber="House")
    assert p.name == "Nancy Pelosi"
    assert p.party == "D"
    assert p.chamber == "House"


def test_politician_party_enum():
    """Party must be one of: D, R, I"""
    from src.models.politician import Politician

    p = Politician(name="Nancy Pelosi", party="D", chamber="House")
    assert p.party in ("D", "R", "I")

    # Invalid party should raise error
    with pytest.raises(ValueError):
        Politician(name="John Doe", party="X", chamber="House")


def test_politician_chamber_enum():
    """Chamber must be one of: House, Senate"""
    from src.models.politician import Politician

    p = Politician(name="Nancy Pelosi", party="D", chamber="House")
    assert p.chamber in ("House", "Senate")

    # Invalid chamber should raise error
    with pytest.raises(ValueError):
        Politician(name="John Doe", party="D", chamber="Invalid")


def test_trade_model_valid():
    """Trade stores ticker, type, amount range, dates"""
    from src.models.trade import Trade

    t = Trade(
        politician_id=1,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250000,
        amount_to=500000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )
    assert t.ticker == "NVDA"
    assert t.trade_type == "BUY"
    assert t.amount_from == 250000
    assert t.amount_to == 500000


def test_trade_midpoint_calculation():
    """Trade.midpoint calculates (amount_from + amount_to) / 2"""
    from src.models.trade import Trade

    t = Trade(
        politician_id=1,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250000,
        amount_to=500000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )
    assert t.midpoint == 375000  # (250K + 500K) / 2


def test_trade_type_enum():
    """Trade type must be BUY or SELL"""
    from src.models.trade import Trade

    t = Trade(
        politician_id=1,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250000,
        amount_to=500000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )
    assert t.trade_type in ("BUY", "SELL")

    # Invalid type should raise error
    with pytest.raises(ValueError):
        Trade(
            politician_id=1,
            ticker="NVDA",
            trade_type="INVALID",
            amount_from=250000,
            amount_to=500000,
            trade_date=date(2026, 4, 15),
            filing_date=date(2026, 4, 17),
        )


def test_trade_deduplication_key():
    """dedup_key matches the DB UNIQUE constraint columns."""
    from src.models.trade import Trade

    t = Trade(
        politician_id=1,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250_000,
        amount_to=500_000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )
    assert isinstance(t.dedup_key, tuple)
    assert t.dedup_key == (1, "NVDA", date(2026, 4, 15), 250_000, 500_000, "BUY")


def test_holding_computed_fields_serialized():
    """Holding computed fields appear in model_dump() output."""
    from src.models.portfolio import Holding

    h = Holding(ticker="AAPL", shares=10, avg_cost=150.0, current_price=180.0)
    d = h.model_dump()
    assert d["current_value"] == pytest.approx(1800.0)
    assert d["cost_basis"] == pytest.approx(1500.0)
    assert d["unrealized_pnl"] == pytest.approx(300.0)
    assert d["return_pct"] == pytest.approx(20.0)


def test_profit_record_trade_date_is_date_type():
    """ProfitRecord.trade_date should be a date, not a string."""
    from src.models.portfolio import ProfitRecord

    pr = ProfitRecord(ticker="NVDA", realized_pnl=500.0, trade_date=date(2026, 1, 15))
    assert isinstance(pr.trade_date, date)


def test_price_model_valid():
    """Price stores ticker, date, close price"""
    from src.models.trade import Price

    p = Price(ticker="NVDA", date=date(2026, 4, 15), close=875.50)
    assert p.ticker == "NVDA"
    assert p.date == date(2026, 4, 15)
    assert p.close == 875.50


def test_portfolio_model_valid():
    """Portfolio stores portfolio metrics"""
    from src.models.portfolio import Portfolio, Holding

    holdings = [
        Holding(ticker="NVDA", shares=10, avg_cost=875.50, current_price=880.00)
    ]

    portfolio = Portfolio(
        politician_id=1,
        current_value=8800.00,
        total_cost=8755.00,
        realized_pnl=100.00,
        unrealized_pnl=45.00,
        return_pct=0.05,
        holdings=holdings,
    )

    assert portfolio.politician_id == 1
    assert portfolio.current_value == 8800.00
    assert len(portfolio.holdings) == 1


def test_subscription_model_valid():
    """Subscription stores politician and Telegram info"""
    from src.models.subscription import TelegramSubscription

    sub = TelegramSubscription(
        politician_id=1,
        telegram_chat_id="123456789",
        active=True,
    )

    assert sub.politician_id == 1
    assert sub.telegram_chat_id == "123456789"
    assert sub.active is True
