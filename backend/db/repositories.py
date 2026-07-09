"""Repository functions for FinAlly database operations.

All functions operate on a provided aiosqlite connection and use
user_id='default' (single-user mode).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiosqlite

# Hardcoded single-user identity.
USER_ID = "default"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


async def get_profile(conn: aiosqlite.Connection) -> dict[str, Any]:
    """Return the user profile row as a dict."""
    cursor = await conn.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
        (USER_ID,),
    )
    row = await cursor.fetchone()
    if row is None:
        return {"id": USER_ID, "cash_balance": 10000.0, "created_at": None}
    return {"id": row[0], "cash_balance": row[1], "created_at": row[2]}


async def update_cash_balance(conn: aiosqlite.Connection, amount: float) -> None:
    """Add `amount` (positive or negative) to the user's cash balance."""
    await conn.execute(
        "UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = ?",
        (amount, USER_ID),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


async def get_watchlist(conn: aiosqlite.Connection) -> list[str]:
    """Return all tickers in the user's watchlist, oldest first."""
    cursor = await conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
        (USER_ID,),
    )
    rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def add_watchlist_ticker(conn: aiosqlite.Connection, ticker: str) -> None:
    """Insert a ticker into the watchlist. Idempotent (UPSERT)."""
    ts = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """INSERT INTO watchlist (id, user_id, ticker, added_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id, ticker) DO NOTHING""",
        (str(uuid4()), USER_ID, ticker.upper(), ts),
    )
    await conn.commit()


async def remove_watchlist_ticker(conn: aiosqlite.Connection, ticker: str) -> None:
    """Remove a ticker from the user's watchlist. Silent if not present."""
    await conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker.upper()),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


async def get_positions(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    """Return all positions for the user."""
    cursor = await conn.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ?",
        (USER_ID,),
    )
    rows = await cursor.fetchall()
    return [
        {
            "id": row[0],
            "user_id": row[1],
            "ticker": row[2],
            "quantity": row[3],
            "avg_cost": row[4],
            "updated_at": row[5],
        }
        for row in rows
    ]


async def upsert_position(
    conn: aiosqlite.Connection,
    ticker: str,
    quantity: float,
    avg_cost: float,
) -> None:
    """Insert or update a position. Quantity <= 0 deletes the row."""
    ts = datetime.now(timezone.utc).isoformat()
    if quantity <= 0:
        await conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
            (USER_ID, ticker.upper()),
        )
    else:
        await conn.execute(
            """INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, ticker) DO UPDATE
                 SET quantity = excluded.quantity, avg_cost = excluded.avg_cost,
                     updated_at = excluded.updated_at""",
            (str(uuid4()), USER_ID, ticker.upper(), quantity, avg_cost, ts),
        )
    await conn.commit()


async def delete_position(conn: aiosqlite.Connection, ticker: str) -> None:
    """Delete a position by ticker."""
    await conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker.upper()),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


async def record_trade(
    conn: aiosqlite.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
) -> None:
    """Append a trade record."""
    ts = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid4()), USER_ID, ticker.upper(), side.lower(), quantity, price, ts),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Portfolio Snapshots
# ---------------------------------------------------------------------------


async def record_snapshot(conn: aiosqlite.Connection, total_value: float) -> None:
    """Record a portfolio value snapshot."""
    ts = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
        (str(uuid4()), USER_ID, total_value, ts),
    )
    await conn.commit()


async def get_snapshots(
    conn: aiosqlite.Connection, limit: int = 500
) -> list[dict[str, Any]]:
    """Return recent portfolio snapshots, newest last."""
    cursor = await conn.execute(
        """SELECT id, user_id, total_value, recorded_at
           FROM portfolio_snapshots
           WHERE user_id = ?
           ORDER BY recorded_at ASC
           LIMIT ?""",
        (USER_ID, limit),
    )
    rows = await cursor.fetchall()
    return [
        {
            "id": row[0],
            "user_id": row[1],
            "total_value": row[2],
            "recorded_at": row[3],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Chat Messages
# ---------------------------------------------------------------------------


async def save_chat_message(
    conn: aiosqlite.Connection,
    role: str,
    content: str,
    actions: dict | None,
) -> None:
    """Persist a chat message."""
    ts = datetime.now(timezone.utc).isoformat()
    actions_json = json.dumps(actions) if actions is not None else None
    await conn.execute(
        """INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (str(uuid4()), USER_ID, role, content, actions_json, ts),
    )
    await conn.commit()


async def get_chat_history(
    conn: aiosqlite.Connection, limit: int = 50
) -> list[dict[str, Any]]:
    """Return chat history, oldest first."""
    cursor = await conn.execute(
        """SELECT id, role, content, actions, created_at
           FROM chat_messages
           WHERE user_id = ?
           ORDER BY created_at ASC
           LIMIT ?""",
        (USER_ID, limit),
    )
    rows = await cursor.fetchall()
    result = []
    for row in rows:
        actions = json.loads(row[3]) if row[3] is not None else None
        result.append(
            {
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "actions": actions,
                "created_at": row[4],
            }
        )
    return result
