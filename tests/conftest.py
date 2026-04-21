"""Pytest configuration and shared fixtures."""

import pytest
from datetime import date

from src.models.politician import Politician
from src.models.trade import Price, Trade

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def sample_politician() -> Politician:
    return Politician(name="Nancy Pelosi", party="D", chamber="House")


@pytest.fixture
def sample_trade() -> Trade:
    return Trade(
        politician_id=1,
        ticker="NVDA",
        trade_type="BUY",
        amount_from=250_000,
        amount_to=500_000,
        trade_date=date(2026, 4, 15),
        filing_date=date(2026, 4, 17),
    )


@pytest.fixture
def sample_prices() -> list[Price]:
    return [
        Price(ticker="NVDA", date=date(2026, 4, 15), close=875.50),
        Price(ticker="NVDA", date=date(2026, 4, 16), close=878.20),
    ]


@pytest.fixture
def sample_benchmark_prices() -> list[Price]:
    return [
        Price(ticker="^GSPC", date=date(2026, 1, 1), close=4700.0),
        Price(ticker="^GSPC", date=date(2026, 4, 18), close=4850.0),
    ]
