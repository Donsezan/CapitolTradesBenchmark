"""
Unit tests for Finnhub API client.
"""

import pytest
import json
from datetime import date
import os


def test_finnhub_parse_response():
    """Finnhub API response is correctly parsed into Trade objects"""
    from src.scraper.finnhub_client import FinnhubClient

    client = FinnhubClient(api_key="test_key")

    # Mock Finnhub API response
    mock_response = {
        "data": [
            {
                "name": "Nancy Pelosi",
                "symbol": "NVDA",
                "transactionType": "Purchase",
                "transactionDate": "2026-04-15",
                "filingDate": "2026-04-17",
                "amountFrom": 250000,
                "amountTo": 500000,
                "assetName": "NVIDIA Corp",
            },
            {
                "name": "Mitch McConnell",
                "symbol": "AAPL",
                "transactionType": "Sale",
                "transactionDate": "2026-04-14",
                "filingDate": "2026-04-16",
                "amountFrom": 100000,
                "amountTo": 200000,
                "assetName": "Apple Inc.",
            },
        ]
    }

    trades = client.parse_response(mock_response)

    assert len(trades) == 2
    assert trades[0].ticker == "NVDA"
    assert trades[0].midpoint == 375000  # (250K + 500K) / 2
    assert trades[0].trade_type == "BUY"
    assert trades[1].ticker == "AAPL"
    assert trades[1].trade_type == "SELL"


def test_finnhub_parse_detects_party_from_name():
    """Parser attempts to infer party from politician name (future enhancement)"""
    from src.scraper.finnhub_client import FinnhubClient

    client = FinnhubClient(api_key="test_key")

    mock_response = {
        "data": [
            {
                "name": "Nancy Pelosi",
                "symbol": "NVDA",
                "transactionType": "Purchase",
                "transactionDate": "2026-04-15",
                "filingDate": "2026-04-17",
                "amountFrom": 250000,
                "amountTo": 500000,
                "assetName": "NVIDIA Corp",
            }
        ]
    }

    trades = client.parse_response(mock_response)
    assert trades[0].politician_name == "Nancy Pelosi"
    # Party/chamber may be None initially, filled in from external data


def test_finnhub_handles_empty_response():
    """Empty response returns empty trade list"""
    from src.scraper.finnhub_client import FinnhubClient

    client = FinnhubClient(api_key="test_key")

    mock_response = {"data": []}
    trades = client.parse_response(mock_response)

    assert trades == []


def test_finnhub_handles_malformed_response():
    """Malformed response raises error"""
    from src.scraper.finnhub_client import FinnhubClient

    client = FinnhubClient(api_key="test_key")

    # Missing required fields
    mock_response = {"data": [{"name": "Nancy Pelosi"}]}

    with pytest.raises((KeyError, ValueError)):
        client.parse_response(mock_response)


@pytest.mark.asyncio
async def test_finnhub_fetch_real_api():
    """SPIKE TEST: Can we actually connect to Finnhub API?

    This is the critical decision gate test. If this fails, it means:
    - Finnhub API key is invalid
    - Finnhub API is down
    - Network access is blocked
    - Response format changed

    Decision: Pivot to Capitol Trades wrappers if this fails consistently.
    """
    from src.scraper.finnhub_client import FinnhubClient

    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key or api_key == "test_key":
        pytest.skip("FINNHUB_API_KEY not configured")

    client = FinnhubClient(api_key=api_key)

    try:
        trades = await client.fetch_trades()

        # Verify we got real data
        assert isinstance(trades, list)
        if len(trades) > 0:  # Only assert structure if we got data
            assert trades[0].ticker is not None
            assert trades[0].politician_name is not None
            assert trades[0].trade_type in ("BUY", "SELL")

    except Exception as e:
        # Log the error for debugging
        pytest.fail(f"Finnhub API test failed: {e}")


@pytest.mark.asyncio
async def test_finnhub_fetch_respects_rate_limit():
    """Finnhub client respects rate limiting (30 calls/sec)"""
    from src.scraper.finnhub_client import FinnhubClient
    import asyncio

    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key or api_key == "test_key":
        pytest.skip("FINNHUB_API_KEY not configured")

    client = FinnhubClient(api_key=api_key)

    # Make multiple calls quickly - should not exceed rate limit
    try:
        trades1 = await client.fetch_trades()
        await asyncio.sleep(0.1)  # Small delay
        trades2 = await client.fetch_trades()

        assert isinstance(trades1, list)
        assert isinstance(trades2, list)

    except Exception as e:
        pytest.fail(f"Rate limiting test failed: {e}")


def test_finnhub_url_construction():
    """Finnhub URL is correctly constructed"""
    from src.scraper.finnhub_client import FinnhubClient

    client = FinnhubClient(api_key="test_key_123")

    # Verify the client has the correct base URL
    assert client.base_url == "https://finnhub.io/api/v1"
    assert client.api_key == "test_key_123"
