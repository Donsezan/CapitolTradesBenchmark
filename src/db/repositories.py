from datetime import date
from typing import List, Optional

from src.db.database import Database
from src.models.politician import Politician
from src.models.trade import Trade, Price
from src.models.subscription import TelegramSubscription


class PoliticianRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(self, politician: Politician) -> Politician:
        async with self.db.conn.execute(
            "INSERT OR IGNORE INTO politicians (name, party, chamber) VALUES (?, ?, ?)",
            (politician.name, politician.party, politician.chamber),
        ):
            pass
        await self.db.conn.commit()
        return await self.get_by_name(politician.name)

    async def get_by_name(self, name: str) -> Optional[Politician]:
        async with self.db.conn.execute(
            "SELECT id, name, party, chamber FROM politicians WHERE name = ?", (name,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return Politician(id=row["id"], name=row["name"], party=row["party"], chamber=row["chamber"])

    async def get_by_id(self, politician_id: int) -> Optional[Politician]:
        async with self.db.conn.execute(
            "SELECT id, name, party, chamber FROM politicians WHERE id = ?", (politician_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return Politician(id=row["id"], name=row["name"], party=row["party"], chamber=row["chamber"])

    async def get_all(self) -> List[Politician]:
        async with self.db.conn.execute(
            "SELECT id, name, party, chamber FROM politicians ORDER BY name"
        ) as cur:
            rows = await cur.fetchall()
        return [Politician(id=r["id"], name=r["name"], party=r["party"], chamber=r["chamber"]) for r in rows]

    async def update_party_chamber(self, politician_id: int, party: str, chamber: str) -> None:
        await self.db.conn.execute(
            "UPDATE politicians SET party = ?, chamber = ? WHERE id = ?",
            (party, chamber, politician_id),
        )
        await self.db.conn.commit()

    async def get_all_with_trade_counts(self) -> List[dict]:
        async with self.db.conn.execute(
            """
            SELECT p.id, p.name, p.party, p.chamber, COUNT(t.id) AS trade_count
            FROM politicians p
            LEFT JOIN trades t ON t.politician_id = p.id
            GROUP BY p.id
            ORDER BY p.name
            """
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]


class TradeRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create_if_not_exists(self, trade: Trade) -> tuple[Trade, bool]:
        """Insert trade if it doesn't exist. Returns (trade, was_inserted)."""
        async with self.db.conn.execute(
            """
            INSERT OR IGNORE INTO trades
                (politician_id, politician_name, ticker, asset_name, trade_type,
                 amount_from, amount_to, trade_date, filing_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.politician_id,
                trade.politician_name,
                trade.ticker,
                trade.asset_name,
                trade.trade_type,
                trade.amount_from,
                trade.amount_to,
                trade.trade_date.isoformat(),
                trade.filing_date.isoformat(),
            ),
        ) as cur:
            inserted = cur.rowcount > 0
        await self.db.conn.commit()
        return trade, inserted

    async def get_by_politician(self, politician_id: int) -> List[Trade]:
        async with self.db.conn.execute(
            """
            SELECT id, politician_id, politician_name, ticker, asset_name,
                   trade_type, amount_from, amount_to, trade_date, filing_date
            FROM trades WHERE politician_id = ?
            ORDER BY trade_date DESC
            """,
            (politician_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._row_to_trade(r) for r in rows]

    async def get_recent(self, limit: int = 50) -> List[Trade]:
        async with self.db.conn.execute(
            """
            SELECT id, politician_id, politician_name, ticker, asset_name,
                   trade_type, amount_from, amount_to, trade_date, filing_date
            FROM trades ORDER BY filing_date DESC, trade_date DESC LIMIT ?
            """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._row_to_trade(r) for r in rows]

    async def count_by_politician(self, politician_id: int) -> int:
        async with self.db.conn.execute(
            "SELECT COUNT(*) FROM trades WHERE politician_id = ?", (politician_id,)
        ) as cur:
            row = await cur.fetchone()
        return row[0]

    async def count_all(self) -> int:
        async with self.db.conn.execute("SELECT COUNT(*) FROM trades") as cur:
            row = await cur.fetchone()
        return row[0]

    def _row_to_trade(self, row) -> Trade:
        return Trade(
            id=row["id"],
            politician_id=row["politician_id"],
            politician_name=row["politician_name"],
            ticker=row["ticker"],
            asset_name=row["asset_name"],
            trade_type=row["trade_type"],
            amount_from=row["amount_from"],
            amount_to=row["amount_to"],
            trade_date=date.fromisoformat(row["trade_date"]),
            filing_date=date.fromisoformat(row["filing_date"]),
        )


class PriceRepository:
    def __init__(self, db: Database):
        self.db = db

    async def insert_if_not_exists(self, price: Price) -> None:
        await self.db.conn.execute(
            "INSERT OR IGNORE INTO daily_prices (ticker, date, close) VALUES (?, ?, ?)",
            (price.ticker, price.date.isoformat(), price.close),
        )
        await self.db.conn.commit()

    async def batch_insert(self, prices: List[Price], chunk_size: int = 500) -> None:
        rows = [(p.ticker, p.date.isoformat(), p.close) for p in prices]
        for i in range(0, len(rows), chunk_size):
            await self.db.conn.executemany(
                "INSERT OR IGNORE INTO daily_prices (ticker, date, close) VALUES (?, ?, ?)",
                rows[i : i + chunk_size],
            )
            await self.db.conn.commit()

    async def get_latest(self, ticker: str) -> Optional[Price]:
        async with self.db.conn.execute(
            "SELECT ticker, date, close FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return Price(ticker=row["ticker"], date=date.fromisoformat(row["date"]), close=row["close"])

    async def get_range(self, ticker: str, start: date, end: date) -> List[Price]:
        async with self.db.conn.execute(
            """
            SELECT ticker, date, close FROM daily_prices
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (ticker, start.isoformat(), end.isoformat()),
        ) as cur:
            rows = await cur.fetchall()
        return [Price(ticker=r["ticker"], date=date.fromisoformat(r["date"]), close=r["close"]) for r in rows]

    async def count(self) -> int:
        async with self.db.conn.execute("SELECT COUNT(*) FROM daily_prices") as cur:
            row = await cur.fetchone()
        return row[0]


class SubscriptionRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(self, sub: TelegramSubscription) -> TelegramSubscription:
        async with self.db.conn.execute(
            "INSERT INTO subscriptions (politician_id, telegram_chat_id, active) VALUES (?, ?, ?)",
            (sub.politician_id, sub.telegram_chat_id, 1 if sub.active else 0),
        ) as cur:
            row_id = cur.lastrowid
        await self.db.conn.commit()
        return await self.get_by_id(row_id)

    async def get_by_id(self, sub_id: int) -> Optional[TelegramSubscription]:
        async with self.db.conn.execute(
            "SELECT id, politician_id, telegram_chat_id, active FROM subscriptions WHERE id = ?",
            (sub_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return TelegramSubscription(
            id=row["id"],
            politician_id=row["politician_id"],
            telegram_chat_id=row["telegram_chat_id"],
            active=bool(row["active"]),
        )

    async def get_active(self) -> List[TelegramSubscription]:
        async with self.db.conn.execute(
            "SELECT id, politician_id, telegram_chat_id, active FROM subscriptions WHERE active = 1"
        ) as cur:
            rows = await cur.fetchall()
        return [
            TelegramSubscription(
                id=r["id"],
                politician_id=r["politician_id"],
                telegram_chat_id=r["telegram_chat_id"],
                active=bool(r["active"]),
            )
            for r in rows
        ]

    async def get_all(self) -> List[TelegramSubscription]:
        async with self.db.conn.execute(
            "SELECT id, politician_id, telegram_chat_id, active FROM subscriptions"
        ) as cur:
            rows = await cur.fetchall()
        return [
            TelegramSubscription(
                id=r["id"],
                politician_id=r["politician_id"],
                telegram_chat_id=r["telegram_chat_id"],
                active=bool(r["active"]),
            )
            for r in rows
        ]

    async def deactivate(self, sub_id: int) -> bool:
        await self.db.conn.execute(
            "UPDATE subscriptions SET active = 0 WHERE id = ?", (sub_id,)
        )
        await self.db.conn.commit()
        return True

    async def delete(self, sub_id: int) -> bool:
        await self.db.conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        await self.db.conn.commit()
        return True
