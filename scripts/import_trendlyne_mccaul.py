"""
Import Michael McCaul trades from mccaul_trades_raw.json (scraped from Trendlyne)
into the local SQLite database.

Usage:
    python scripts/import_trendlyne_mccaul.py
"""

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.db.database import Database
from src.db.repositories import PoliticianRepository, TradeRepository
from src.models.politician import Politician
from src.models.trade import Trade
from datetime import date

RAW_FILE = Path(__file__).parent.parent / "mccaul_trades_raw.json"

_AMOUNT_RE = re.compile(r"([\d.]+)([KMB]?)")

def _parse_amount_str(s: str) -> float:
    """Parse Trendlyne size string like '1K', '15K', '1M' into a float."""
    m = _AMOUNT_RE.match(s.strip().replace(",", ""))
    if not m:
        return 0.0
    val = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "K":
        val *= 1_000
    elif suffix == "M":
        val *= 1_000_000
    elif suffix == "B":
        val *= 1_000_000_000
    return val

def parse_amount_range(size: str):
    """
    Parse '15K-50K' → (15000.0, 50000.0).
    Returns (0, 0) if unparseable.
    """
    parts = size.split("-")
    if len(parts) != 2:
        return 0.0, 0.0
    return _parse_amount_str(parts[0]), _parse_amount_str(parts[1])

TX_MAP = {
    "purchase": "BUY",
    "sale": "SELL",
}

async def main():
    with open(RAW_FILE, encoding="utf-8") as f:
        raw_trades = json.load(f)

    db = Database(config.DB_PATH)
    await db.init_schema()

    pol_repo = PoliticianRepository(db)
    trade_repo = TradeRepository(db)

    # Ensure politician exists
    pol = await pol_repo.get_by_name("Michael T. McCaul")
    if pol is None:
        pol = await pol_repo.create(
            Politician(name="Michael T. McCaul", party="R", chamber="House")
        )
    print(f"Politician: {pol.name} (id={pol.id})")

    imported = 0
    skipped_no_ticker = 0
    skipped_unknown_type = 0

    for raw in raw_trades:
        ticker = raw["stock_asset"]["stockcode"]
        if not ticker:
            skipped_no_ticker += 1
            continue

        tx_raw = raw["transaction_type"]["type"].lower()
        trade_type = TX_MAP.get(tx_raw)
        if trade_type is None:
            skipped_unknown_type += 1
            continue

        amount_from, amount_to = parse_amount_range(raw["amount"]["size"])

        trade = Trade(
            politician_id=pol.id,
            politician_name=pol.name,
            ticker=ticker,
            asset_name=raw["stock_asset"]["fullname"] or ticker,
            trade_type=trade_type,
            amount_from=amount_from,
            amount_to=amount_to,
            trade_date=date.fromisoformat(raw["transaction_date"]),
            filing_date=date.fromisoformat(raw["notification_date"]),
            party="R",
            chamber="House",
        )

        before = await trade_repo.count_by_politician(pol.id)
        await trade_repo.create_if_not_exists(trade)
        after = await trade_repo.count_by_politician(pol.id)
        if after > before:
            imported += 1

    total_in_db = await trade_repo.count_by_politician(pol.id)
    print(f"Imported {imported} new trades")
    print(f"Skipped {skipped_no_ticker} (no ticker), {skipped_unknown_type} (unknown type)")
    print(f"McCaul now has {total_in_db} trades in DB")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
