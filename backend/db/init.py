"""Database initialization and seed data."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

HERE = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(HERE, "schema.sql")
DB_PATH = os.path.join(os.environ.get("FINALLY_DB_DIR", "/app/db"), "finally.db")

DEFAULT_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

DEFAULT_CASH = 10_000.0


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    try:
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())

        row = conn.execute(
            "SELECT COUNT(*) as c FROM users_profile WHERE id = 'default'"
        ).fetchone()
        if row["c"] == 0:
            _seed_default(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_default(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        ("default", DEFAULT_CASH, now),
    )
    import uuid
    for ticker in DEFAULT_TICKERS:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", ticker, now),
        )


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
