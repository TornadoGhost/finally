"""Unit tests for the database layer."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

import aiosqlite


@pytest.fixture
def fresh_db(tmp_path):
    """Provide an isolated temp DB path and patch db/__init__.state before each test."""
    db_path = str(tmp_path / "test.db")

    # Patch DB_PATH in the db module and reset _seeded so init_db() re-runs.
    import db as _db_module
    _db_module.DB_PATH = db_path
    _db_module._seeded = False

    return db_path


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_schema_creates_all_tables(fresh_db):
    """All six tables exist after init_db."""
    from db import init_db

    await init_db()

    async with aiosqlite.connect(fresh_db) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = []
        while (row := await cursor.fetchone()) is not None:
            rows.append(row)

    table_names = {r[0] for r in rows}
    assert "users_profile" in table_names
    assert "watchlist" in table_names
    assert "positions" in table_names
    assert "trades" in table_names
    assert "portfolio_snapshots" in table_names
    assert "chat_messages" in table_names


@pytest.mark.asyncio
async def test_init_db_seeds_default_cash_and_watchlist(fresh_db):
    """Seeding creates $10k cash and 10 tickers."""
    from db import init_db

    await init_db()

    async with aiosqlite.connect(fresh_db) as db:
        cash_cursor = await db.execute(
            "SELECT cash_balance FROM users_profile WHERE id='default'"
        )
        cash_row = await cash_cursor.fetchone()

        ticker_cursor = await db.execute(
            "SELECT ticker FROM watchlist WHERE user_id='default' ORDER BY added_at"
        )
        ticker_rows = []
        while (row := await ticker_cursor.fetchone()) is not None:
            ticker_rows.append(row)

    assert cash_row is not None
    assert cash_row[0] == 10000.0
    assert len(ticker_rows) == 10
    tickers = {r[0] for r in ticker_rows}
    assert tickers == {
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
        "NVDA", "META", "JPM", "V", "NFLX",
    }


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_profile_returns_cash_balance(fresh_db):
    from db import init_db
    from db.repositories import get_profile

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        profile = await get_profile(conn)

    assert profile["cash_balance"] == 10000.0
    assert profile["id"] == "default"


@pytest.mark.asyncio
async def test_update_cash_balance_adds_and_subtracts(fresh_db):
    from db import init_db
    from db.repositories import get_profile, update_cash_balance

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await update_cash_balance(conn, 500.0)
        profile = await get_profile(conn)
        assert profile["cash_balance"] == 10500.0

        await update_cash_balance(conn, -200.0)
        profile = await get_profile(conn)
        assert profile["cash_balance"] == 10300.0


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_watchlist_returns_tickers(fresh_db):
    from db import init_db
    from db.repositories import get_watchlist

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        tickers = await get_watchlist(conn)

    assert len(tickers) == 10
    assert "AAPL" in tickers


@pytest.mark.asyncio
async def test_add_watchlist_ticker_upsert(fresh_db):
    from db import init_db
    from db.repositories import add_watchlist_ticker, get_watchlist

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await add_watchlist_ticker(conn, "TSLA")   # no-op (already exists)
        await add_watchlist_ticker(conn, "AMD")
        tickers = await get_watchlist(conn)

    assert "AMD" in tickers
    assert "TSLA" in tickers


@pytest.mark.asyncio
async def test_remove_watchlist_ticker(fresh_db):
    from db import init_db
    from db.repositories import get_watchlist, remove_watchlist_ticker

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await remove_watchlist_ticker(conn, "TSLA")
        tickers = await get_watchlist(conn)

    assert "TSLA" not in tickers


@pytest.mark.asyncio
async def test_remove_nonexistent_ticker_is_idempotent(fresh_db):
    from db import init_db
    from db.repositories import remove_watchlist_ticker

    await init_db()

    # Must not raise.
    async with aiosqlite.connect(fresh_db) as conn:
        await remove_watchlist_ticker(conn, "NOTEXIST")


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_position_insert_and_update(fresh_db):
    from db import init_db
    from db.repositories import get_positions, upsert_position

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await upsert_position(conn, "aapl", 10, 150.0)
        positions = await get_positions(conn)

    assert len(positions) == 1
    assert positions[0]["ticker"] == "AAPL"
    assert positions[0]["quantity"] == 10
    assert positions[0]["avg_cost"] == 150.0

    async with aiosqlite.connect(fresh_db) as conn:
        await upsert_position(conn, "AAPL", 20, 160.0)
        positions = await get_positions(conn)

    assert len(positions) == 1
    assert positions[0]["quantity"] == 20
    assert positions[0]["avg_cost"] == 160.0


@pytest.mark.asyncio
async def test_upsert_position_deletes_when_quantity_zero(fresh_db):
    from db import init_db
    from db.repositories import get_positions, upsert_position

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await upsert_position(conn, "NVDA", 5, 800.0)
        await upsert_position(conn, "NVDA", 0, 0.0)
        positions = await get_positions(conn)

    assert not any(p["ticker"] == "NVDA" for p in positions)


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_trade_appends_row(fresh_db):
    from db import init_db
    from db.repositories import record_trade

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await record_trade(conn, "msft", "buy", 5, 420.0)
        cursor = await conn.execute(
            "SELECT ticker, side, quantity, price FROM trades WHERE ticker='MSFT'"
        )
        row = await cursor.fetchone()

    assert row == ("MSFT", "buy", 5, 420.0)


# ---------------------------------------------------------------------------
# Portfolio Snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_and_get_snapshots(fresh_db):
    from db import init_db
    from db.repositories import get_snapshots, record_snapshot

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await record_snapshot(conn, 10000.0)
        await record_snapshot(conn, 10200.0)
        snapshots = await get_snapshots(conn)

    assert len(snapshots) == 2
    assert snapshots[0]["total_value"] == 10000.0
    assert snapshots[1]["total_value"] == 10200.0


@pytest.mark.asyncio
async def test_get_snapshots_respects_limit(fresh_db):
    from db import init_db
    from db.repositories import get_snapshots, record_snapshot

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        for i in range(10):
            await record_snapshot(conn, float(10000 + i))
        snapshots = await get_snapshots(conn, limit=3)

    assert len(snapshots) == 3


# ---------------------------------------------------------------------------
# Chat Messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_and_get_chat_history(fresh_db):
    from db import init_db
    from db.repositories import get_chat_history, save_chat_message

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        await save_chat_message(conn, "user", "Hello, FinAlly!", None)
        await save_chat_message(conn, "assistant", "Hi there!", {"trades": []})
        history = await get_chat_history(conn)

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello, FinAlly!"
    assert history[0]["actions"] is None
    assert history[1]["role"] == "assistant"
    assert history[1]["actions"] == {"trades": []}


@pytest.mark.asyncio
async def test_get_chat_history_respects_limit(fresh_db):
    from db import init_db
    from db.repositories import get_chat_history, save_chat_message

    await init_db()

    async with aiosqlite.connect(fresh_db) as conn:
        for i in range(10):
            await save_chat_message(conn, "user", f"Message {i}", None)
        history = await get_chat_history(conn, limit=3)

    assert len(history) == 3
