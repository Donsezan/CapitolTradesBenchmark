import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from src.db.database import Database
from src.scraper.price_fetcher import PriceFetcher
from src.db.repositories import TradeRepository, PriceRepository
from src.services.trade_service import TradeService
from src.services.alert_service import AlertService
from src.telegram.bot import TelegramBot

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, db: Database, bot: TelegramBot):
        self.db = db
        self.bot = bot
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self._scheduler.add_job(
            self._scrape_trades,
            "interval",
            hours=1,
            id="scrape_trades",
            replace_existing=True,
            next_run_time=datetime.now(tz=timezone.utc),
        )
        self._scheduler.add_job(
            self._update_prices,
            "interval",
            minutes=30,
            id="update_prices",
            replace_existing=True,
            next_run_time=datetime.now(tz=timezone.utc) + timedelta(seconds=30),
        )
        self._scheduler.start()
        logger.info("Scheduler started (initial scrape triggered immediately)")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    async def trigger_price_update(self) -> None:
        await self._update_prices()

    async def _scrape_trades(self) -> None:
        logger.info("Running trade scrape job (House PTR)")
        trade_service = TradeService(db=self.db)
        alert_service = AlertService(db=self.db, telegram_bot=self.bot)

        try:
            new_trades = await trade_service.fetch_and_store(
                from_date=date.today() - timedelta(days=14),
                to_date=date.today(),
            )
            await alert_service.process_new_trades(new_trades)
        except Exception as exc:
            logger.error("Trade scrape job failed: %s", exc)

    async def _update_prices(self) -> None:
        logger.info("Running price update job")
        try:
            trade_repo = TradeRepository(self.db)
            price_repo = PriceRepository(self.db)
            fetcher = PriceFetcher(db_session=self.db)

            all_trades = await trade_repo.get_recent(limit=5000)
            tickers = list({t.ticker for t in all_trades})

            benchmark_tickers = ["^GSPC", "^IXIC", "QQQ", "DIA", "SPY", "^RUT"]
            all_tickers = list(set(tickers + benchmark_tickers))

            if not all_tickers:
                return

            # Fetch 2 years of history so 1Y/YTD/6M chart ranges have full coverage.
            # INSERT OR IGNORE makes repeat runs cheap — only new rows are written.
            start = date.today() - timedelta(days=730)
            end = date.today()
            prices = await fetcher.fetch_tickers(all_tickers, start_date=start, end_date=end)
            await price_repo.batch_insert(prices)
            logger.info("Updated %d price records for %d tickers", len(prices), len(all_tickers))
        except Exception as exc:
            logger.error("Price update job failed: %s", exc)
