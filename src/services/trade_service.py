import asyncio
import logging
from datetime import date, timedelta
from typing import List, Optional

from src.db.database import Database
from src.db.repositories import PoliticianRepository, TradeRepository
from src.models.politician import Politician
from src.models.trade import Trade
from src.scraper.fmp_enrichment import LegislatorLookup, build_lookup

logger = logging.getLogger(__name__)


class TradeService:
    def __init__(self, db: Database):
        self.db = db
        self._politician_repo = PoliticianRepository(db)
        self._trade_repo = TradeRepository(db)

    async def fetch_and_store(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[Trade]:
        """Fetch trades from House PTR scraper, deduplicate, store, return new ones."""
        from src.scraper.house_scraper import HouseScraper

        if from_date is None:
            from_date = date.today() - timedelta(days=30)
        if to_date is None:
            to_date = date.today()

        scraper = HouseScraper()
        try:
            ptr_results = await scraper.fetch_trades(from_date=from_date, to_date=to_date)
        except Exception as exc:
            logger.error("House PTR scrape failed: %s", exc)
            return []

        # Build GovTrack lookup once so new politicians get the correct party/chamber
        # on first insert rather than defaulting to Independent.
        loop = asyncio.get_running_loop()
        lookup, err = await loop.run_in_executor(None, build_lookup)
        if lookup is None:
            logger.warning("GovTrack lookup unavailable (%s) — party will default to I", err)

        new_trades: List[Trade] = []
        for politician_name, doc_id, trades in ptr_results:
            for trade in trades:
                politician_id = await self._ensure_politician(trade, lookup)
                trade.politician_id = politician_id

                _, was_inserted = await self._trade_repo.create_if_not_exists(trade)
                if was_inserted:
                    new_trades.append(trade)

        logger.info(
            "House PTR: processed %d politicians, %d new trades",
            len(ptr_results),
            len(new_trades),
        )
        return new_trades

    async def _ensure_politician(
        self, trade: Trade, lookup: Optional[LegislatorLookup] = None
    ) -> int:
        name = trade.politician_name or "Unknown"
        existing = await self._politician_repo.get_by_name(name)
        if existing:
            return existing.id

        party = "I"
        chamber = "House"
        if lookup:
            result = lookup.get(name)
            if result:
                party, chamber = result

        pol = Politician(name=name, party=party, chamber=chamber)
        created = await self._politician_repo.create(pol)
        return created.id
