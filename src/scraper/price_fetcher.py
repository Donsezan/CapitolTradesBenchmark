import asyncio
import logging
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd
import yfinance as yf

from src.models.trade import Price

logger = logging.getLogger(__name__)


class PriceFetcher:
    def __init__(self, db_session=None):
        self._db = db_session
        self._mem_cache: dict = {}

    async def fetch_ticker(self, ticker: str, start_date: date, end_date: date) -> List[Price]:
        if start_date > end_date:
            raise ValueError(f"start_date {start_date} is after end_date {end_date}")

        cache_key = (ticker, start_date, end_date)

        # Check in-process memory cache first to avoid a DB round-trip.
        if cache_key in self._mem_cache:
            return self._mem_cache[cache_key]

        if self._db is not None:
            from src.db.repositories import PriceRepository
            repo = PriceRepository(self._db)
            cached = await repo.get_range(ticker, start_date, end_date)
            if cached:
                self._mem_cache[cache_key] = cached
                return cached

        loop = asyncio.get_running_loop()
        prices = await loop.run_in_executor(
            None, lambda: self._download(ticker, start_date, end_date)
        )
        self._mem_cache[cache_key] = prices
        return prices

    async def fetch_tickers(self, tickers: List[str], start_date: date, end_date: date) -> List[Price]:
        if start_date > end_date:
            raise ValueError(f"start_date {start_date} is after end_date {end_date}")

        loop = asyncio.get_running_loop()
        prices = await loop.run_in_executor(
            None, lambda: self._download_multi(tickers, start_date, end_date)
        )
        return prices

    def _download(self, ticker: str, start_date: date, end_date: date) -> List[Price]:
        end_inclusive = end_date + timedelta(days=1)
        # auto_adjust=True → values returned are split- & dividend-adjusted close.
        # Do not change without updating metrics.py calculations.
        df = yf.download(
            ticker,
            start=start_date.isoformat(),
            end=end_inclusive.isoformat(),
            auto_adjust=True,
            progress=False,
        )
        if df is None or df.empty:
            return []
        return self._df_to_prices(df, ticker)

    def _download_multi(self, tickers: List[str], start_date: date, end_date: date) -> List[Price]:
        end_inclusive = end_date + timedelta(days=1)
        df = yf.download(
            tickers,
            start=start_date.isoformat(),
            end=end_inclusive.isoformat(),
            auto_adjust=True,
            progress=False,
        )
        if df is None or df.empty:
            return []

        prices: List[Price] = []
        if len(tickers) == 1:
            return self._df_to_prices(df, tickers[0])

        close_df = df["Close"] if "Close" in df.columns else df
        for ticker in tickers:
            if ticker not in close_df.columns:
                continue
            series = close_df[ticker].dropna()
            for idx, val in series.items():
                d = idx.date() if hasattr(idx, "date") else idx
                prices.append(Price(ticker=ticker, date=d, close=float(val)))

        prices.sort(key=lambda p: (p.ticker, p.date))
        return prices

    def _df_to_prices(self, df: pd.DataFrame, ticker: str) -> List[Price]:
        if "Close" in df.columns:
            col = df["Close"]
        else:
            col = df.iloc[:, 0]

        # yfinance may return a DataFrame (multi-level) for a single ticker
        if isinstance(col, pd.DataFrame):
            col = col.iloc[:, 0]

        series = col.dropna()

        prices = []
        for idx, val in series.items():
            d = idx.date() if hasattr(idx, "date") else idx
            prices.append(Price(ticker=ticker, date=d, close=float(val)))

        prices.sort(key=lambda p: p.date)
        return prices
