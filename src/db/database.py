import aiosqlite
from pathlib import Path


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS politicians (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    party    TEXT NOT NULL,
    chamber  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    politician_id   INTEGER NOT NULL,
    politician_name TEXT,
    ticker          TEXT NOT NULL,
    asset_name      TEXT,
    trade_type      TEXT NOT NULL,
    amount_from     REAL NOT NULL,
    amount_to       REAL NOT NULL,
    trade_date      TEXT NOT NULL,
    filing_date     TEXT NOT NULL,
    FOREIGN KEY (politician_id) REFERENCES politicians(id),
    UNIQUE (politician_id, ticker, trade_date, amount_from, amount_to, trade_type)
);

CREATE TABLE IF NOT EXISTS daily_prices (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker  TEXT NOT NULL,
    date    TEXT NOT NULL,
    close   REAL NOT NULL,
    UNIQUE (ticker, date)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    politician_id    INTEGER NOT NULL,
    telegram_chat_id TEXT NOT NULL,
    active           INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (politician_id) REFERENCES politicians(id)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    status     TEXT NOT NULL,
    message    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    def __init__(self, path: str = ":memory:"):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self._conn is not None:
            return
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.commit()

    async def init_schema(self) -> None:
        await self.connect()
        # executescript handles multi-statement DDL safely; it issues an implicit COMMIT first.
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected — call init_schema() or connect() first")
        return self._conn
