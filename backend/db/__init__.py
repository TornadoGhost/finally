"""Database initialization and lazy schema setup."""

from __future__ import annotations

import os
from pathlib import Path

import aiosqlite

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DB_PATH = os.environ.get("FINALLY_DB_PATH", str(Path(__file__).parent / "finally.db"))

DEFAULT_TICKERS = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
]

_seeded: bool = False


async def init_db() -> None:
    """Lazily initialize the database: create schema and seed default data if needed."""
    global _seeded
    schema_sql = SCHEMA_PATH.read_text()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema_sql)
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) FROM users_profile")
        row = await cursor.fetchone()
        if row is None or row[0] == 0:
            await _seed(db)
            _seeded = True
        else:
            _seeded = True


async def _seed(db: aiosqlite.Connection) -> None:
    """Insert default seed data into a freshly initialized database."""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()

    await db.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES ('default', 10000.0, ?)",
        (ts,),
    )

    from uuid import uuid4

    for ticker in DEFAULT_TICKERS:
        await db.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', ?, ?)",
            (str(uuid4()), ticker, ts),
        )

    await db.commit()
