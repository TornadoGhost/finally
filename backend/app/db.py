"""Async SQLite database layer using aiosqlite."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import aiosqlite

DATABASE = os.path.join(os.environ.get("FINALLY_DB_DIR", "/app/db"), "finally.db")

DEFAULT_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]


def init_db() -> None:
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
        with open(schema_path) as f:
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
        ("default", 10_000.0, now),
    )
    for ticker in DEFAULT_TICKERS:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", ticker, now),
        )


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = await aiosqlite.connect(DATABASE)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── User / Cash ──────────────────────────────────────────────────────────────

async def get_cash_balance(conn: aiosqlite.Connection, user_id: str = "default") -> float:
    cursor = await conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return float(row["cash_balance"]) if row else 10_000.0


async def update_cash(conn: aiosqlite.Connection, user_id: str, delta: float) -> float:
    await conn.execute(
        "UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = ?",
        (delta, user_id),
    )
    await conn.commit()
    return await get_cash_balance(conn, user_id)


# ── Watchlist ────────────────────────────────────────────────────────────────

async def get_watchlist(
    conn: aiosqlite.Connection, user_id: str = "default"
) -> list[dict[str, Any]]:
    cursor = await conn.execute(
        "SELECT id, ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def add_to_watchlist(
    conn: aiosqlite.Connection, ticker: str, user_id: str = "default"
) -> dict[str, Any]:
    now = _now()
    row_id = str(uuid.uuid4())
    try:
        await conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (row_id, user_id, ticker.upper(), now),
        )
        await conn.commit()
    except aiosqlite.IntegrityError:
        pass  # already exists
    return {"id": row_id, "user_id": user_id, "ticker": ticker.upper(), "added_at": now}


async def remove_from_watchlist(
    conn: aiosqlite.Connection, ticker: str, user_id: str = "default"
) -> bool:
    cursor = await conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    )
    await conn.commit()
    return cursor.rowcount > 0


# ── Positions ────────────────────────────────────────────────────────────────

async def get_positions(
    conn: aiosqlite.Connection, user_id: str = "default"
) -> list[dict[str, Any]]:
    cursor = await conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ?",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def upsert_position(
    conn: aiosqlite.Connection,
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = "default",
) -> None:
    now = _now()
    cursor = await conn.execute(
        "SELECT id, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    existing = await cursor.fetchone()

    if existing:
        if quantity <= 0:
            await conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
        else:
            await conn.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                "WHERE user_id = ? AND ticker = ?",
                (quantity, avg_cost, now, user_id, ticker),
            )
    else:
        row_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row_id, user_id, ticker, quantity, avg_cost, now),
        )
    await conn.commit()


# ── Trades ──────────────────────────────────────────────────────────────────

async def record_trade(
    conn: aiosqlite.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = "default",
) -> dict[str, Any]:
    now = _now()
    trade_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade_id, user_id, ticker, side, quantity, price, now),
    )
    await conn.commit()
    return {
        "id": trade_id,
        "user_id": user_id,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": now,
    }


# ── Portfolio Snapshots ──────────────────────────────────────────────────────

async def record_snapshot(
    conn: aiosqlite.Connection, total_value: float, user_id: str = "default"
) -> None:
    await conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, total_value, _now()),
    )
    await conn.commit()


async def get_snapshots(
    conn: aiosqlite.Connection, user_id: str = "default"
) -> list[dict[str, Any]]:
    cursor = await conn.execute(
        "SELECT total_value, recorded_at FROM portfolio_snapshots "
        "WHERE user_id = ? ORDER BY recorded_at ASC",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Chat Messages ────────────────────────────────────────────────────────────

async def save_chat_message(
    conn: aiosqlite.Connection,
    role: str,
    content: str,
    actions: list[dict] | None = None,
    user_id: str = "default",
) -> dict[str, Any]:
    now = _now()
    msg_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, user_id, role, content, json.dumps(actions) if actions else None, now),
    )
    await conn.commit()
    return {"id": msg_id, "role": role, "content": content, "actions": actions, "created_at": now}


async def get_chat_history(
    conn: aiosqlite.Connection, limit: int = 20, user_id: str = "default"
) -> list[dict[str, Any]]:
    cursor = await conn.execute(
        "SELECT role, content, actions, created_at FROM chat_messages "
        "WHERE user_id = ? ORDER BY created_at ASC LIMIT ?",
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "actions": json.loads(r["actions"]) if r["actions"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]
