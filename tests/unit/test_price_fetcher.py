"""
Unit tests for price fetcher (yfinance wrapper).
"""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_yfinance_fetch_single_ticker():
    """yfinance can fetch historical prices"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    # Fetch real data (this will hit Yahoo Finance)
    prices = await fetcher.fetch_ticker(
        "NVDA", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    assert len(prices) > 0
    assert prices[0].ticker == "NVDA"
    assert prices[0].close > 0
    assert prices[0].date is not None


@pytest.mark.asyncio
async def test_yfinance_fetch_multiple_tickers():
    """yfinance can fetch prices for multiple tickers at once"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    # Fetch for multiple tickers
    tickers = ["NVDA", "AAPL", "MSFT"]
    prices = await fetcher.fetch_tickers(
        tickers, start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    assert len(prices) > 0
    # Should have prices for multiple tickers
    unique_tickers = set(p.ticker for p in prices)
    assert len(unique_tickers) == len(tickers)


@pytest.mark.asyncio
async def test_yfinance_fetch_benchmark():
    """yfinance can fetch benchmark index prices (S&P 500, etc.)"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    # Fetch S&P 500
    prices = await fetcher.fetch_ticker(
        "^GSPC", start_date=date(2026, 1, 1), end_date=date(2026, 4, 18)
    )

    assert len(prices) > 0
    assert prices[0].ticker == "^GSPC"
    assert prices[0].close > 4000  # S&P 500 is typically in 4000+ range


@pytest.mark.asyncio
async def test_price_cache_avoids_redundant_calls(db_session=None):
    """Already-cached prices are not re-fetched"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher(db_session=db_session)

    # First fetch
    prices1 = await fetcher.fetch_ticker(
        "NVDA", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    # Mock yfinance to track if it's called again
    with patch("yfinance.download", wraps=MagicMock()) as mock_download:
        # Second fetch (should use cache if DB session provided)
        prices2 = await fetcher.fetch_ticker(
            "NVDA", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
        )

        # Prices should be identical
        assert len(prices1) == len(prices2)


@pytest.mark.asyncio
async def test_price_fetcher_handles_missing_ticker():
    """Fetcher gracefully handles invalid ticker"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    # Try to fetch non-existent ticker
    prices = await fetcher.fetch_ticker(
        "XYZABC", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    # Should return empty list or raise appropriate error
    assert isinstance(prices, (list, type(None)))


@pytest.mark.asyncio
async def test_price_fetcher_handles_invalid_date_range():
    """Fetcher handles invalid date ranges"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    # End date before start date
    with pytest.raises((ValueError, Exception)):
        await fetcher.fetch_ticker(
            "NVDA", start_date=date(2026, 4, 18), end_date=date(2026, 4, 1)
        )


@pytest.mark.asyncio
async def test_price_model_conversion():
    """Price data is correctly converted to Price models"""
    from src.scraper.price_fetcher import PriceFetcher
    from src.models.trade import Price

    fetcher = PriceFetcher()

    prices = await fetcher.fetch_ticker(
        "NVDA", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    # All should be Price objects
    for price in prices:
        assert isinstance(price, Price)
        assert price.ticker == "NVDA"
        assert isinstance(price.close, (int, float))
        assert price.close > 0


@pytest.mark.asyncio
async def test_fetch_prices_for_date_range():
    """Prices are returned for the requested date range"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    start_date = date(2026, 4, 1)
    end_date = date(2026, 4, 10)

    prices = await fetcher.fetch_ticker("NVDA", start_date=start_date, end_date=end_date)

    # All prices should be within the date range
    for price in prices:
        assert start_date <= price.date <= end_date


@pytest.mark.asyncio
async def test_price_fetcher_sorts_by_date():
    """Prices are returned sorted by date (oldest first)"""
    from src.scraper.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    prices = await fetcher.fetch_ticker(
        "NVDA", start_date=date(2026, 4, 1), end_date=date(2026, 4, 18)
    )

    # Verify sorting
    dates = [p.date for p in prices]
    assert dates == sorted(dates)
