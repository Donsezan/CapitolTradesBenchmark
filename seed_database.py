"""
Seed the database with real congressional trade data from the House clerk.

Source : disclosures-clerk.house.gov (official, free, no API key)
Data   : House STOCK Act Periodic Transaction Reports (PTRs)
Coverage: House members only; date range is configurable below.

Run: python seed_database.py
"""

import asyncio
import sys
import logging
from datetime import date, timedelta

# ── Config ─────────────────────────────────────────────────────────────────
DB_PATH    = "data/capitol_trades.db"
FROM_DATE  = date(2024, 1, 1)      # go back to start of 2024
TO_DATE    = date.today()
MAX_PDFS   = 1000                  # cover all filings in range

# ── Logging (show progress) ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("seed")


async def main() -> None:
    import config  # noqa: F401 — ensures .env is loaded
    from src.db.database import Database
    from src.db.repositories import PoliticianRepository, TradeRepository
    from src.models.politician import Politician
    from src.scraper.house_scraper import HouseScraper

    # ── Init DB ──────────────────────────────────────────────────────────
    db = Database(path=DB_PATH)
    await db.init_schema()
    pol_repo   = PoliticianRepository(db)
    trade_repo = TradeRepository(db)

    logger.info("DB ready at %s", DB_PATH)
    logger.info("Scraping House PTRs from %s to %s (max %d PDFs)", FROM_DATE, TO_DATE, MAX_PDFS)
    logger.info("-" * 60)

    # ── Scrape ───────────────────────────────────────────────────────────
    scraper = HouseScraper()
    ptr_results = await scraper.fetch_trades(
        from_date=FROM_DATE,
        to_date=TO_DATE,
        max_pdfs=MAX_PDFS,
    )

    # ── Store ────────────────────────────────────────────────────────────
    total_trades   = 0
    total_new      = 0
    politicians_seen: set[str] = set()

    for politician_name, doc_id, trades in ptr_results:
        # Ensure politician exists in DB
        existing = await pol_repo.get_by_name(politician_name)
        if existing:
            pol_id = existing.id
        else:
            pol = Politician(
                name=politician_name,
                party=trades[0].party if trades else "I",
                chamber=trades[0].chamber if trades else "House",
            )
            created = await pol_repo.create(pol)
            pol_id = created.id

        politicians_seen.add(politician_name)

        for trade in trades:
            trade.politician_id = pol_id
            before = await trade_repo.count_by_politician(pol_id)
            await trade_repo.create_if_not_exists(trade)
            after  = await trade_repo.count_by_politician(pol_id)
            total_trades += 1
            if after > before:
                total_new += 1

    # ── Summary ──────────────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("PDFs processed  : %d", len(ptr_results))
    logger.info("Politicians seen: %d", len(politicians_seen))
    logger.info("Trades parsed   : %d", total_trades)
    logger.info("New rows stored : %d", total_new)

    # Final DB counts
    all_trades = await trade_repo.get_recent(limit=10000)
    tickers = sorted({t.ticker for t in all_trades})
    logger.info("Total trades in DB : %d", len(all_trades))
    logger.info("Unique tickers     : %d  %s", len(tickers), tickers[:20])

    if all_trades:
        dates = sorted(t.trade_date for t in all_trades)
        logger.info("Date range in DB   : %s -> %s", dates[0], dates[-1])

    all_politicians = await pol_repo.get_all_with_trade_counts()
    logger.info("Politicians in DB  : %d", len(all_politicians))
    logger.info("-" * 60)
    logger.info("Top 10 by trade count:")
    for p in sorted(all_politicians, key=lambda x: -x["trade_count"])[:10]:
        logger.info("  %3d trades  %s (%s)", p["trade_count"], p["name"], p["party"])

    await db.close()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
