"""Pytest fixtures for API tests."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import aiosqlite

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.market import PriceCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def price_cache():
    """PriceCache pre-seeded with test prices."""
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("GOOGL", 175.0)
    cache.update("MSFT", 415.0)
    cache.update("AMZN", 185.0)
    return cache


@pytest.fixture
def mock_market_source():
    """Mock MarketDataSource that does nothing."""
    source = AsyncMock()
    source.start = AsyncMock()
    source.stop = AsyncMock()
    source.add_ticker = AsyncMock()
    source.remove_ticker = AsyncMock()
    return source


@pytest.fixture
def test_db(tmp_path):
    """Create and seed a temporary SQLite DB synchronously."""
    db_path = tmp_path / "test.db"

    async def _init():
        async with aiosqlite.connect(str(db_path)) as db:
            schema = Path(__file__).parent.parent.parent / "db" / "schema.sql"
            await db.executescript(schema.read_text())
            await db.commit()

            from datetime import datetime, timezone
            from uuid import uuid4
            ts = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES ('default', 10000.0, ?)",
                (ts,),
            )
            for ticker in ["AAPL", "GOOGL", "MSFT"]:
                await db.execute(
                    "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', ?, ?)",
                    (str(uuid4()), ticker, ts),
                )
            await db.commit()

    asyncio.run(_init())
    return str(db_path)


@pytest.fixture
def client(test_db, price_cache, mock_market_source):
    """Synchronous test client backed by a fresh FastAPI app per test."""
    # Patch DB_PATH in all modules so routes use the temp DB
    import db as db_module
    import app.main as main_module
    import app.llm.chat as chat_module

    original_main = main_module.DB_PATH
    original_chat = chat_module.DB_PATH
    original_db = db_module.DB_PATH

    main_module.DB_PATH = test_db
    chat_module.DB_PATH = test_db
    db_module.DB_PATH = test_db

    from app.main import (
        get_watchlist, post_watchlist, delete_watchlist,
        get_portfolio, post_trade, get_portfolio_history, post_chat, health,
    )

    @asynccontextmanager
    async def test_lifespan(test_app):
        test_app.state.price_cache = price_cache
        test_app.state.market_source = mock_market_source
        from app.market import create_stream_router
        test_app.include_router(create_stream_router(price_cache))
        yield

    test_app = FastAPI(lifespan=test_lifespan)
    test_app.add_api_route("/api/health", health, methods=["GET"])
    test_app.add_api_route("/api/watchlist", get_watchlist, methods=["GET"])
    test_app.add_api_route("/api/watchlist", post_watchlist, methods=["POST"])
    test_app.add_api_route("/api/watchlist/{ticker}", delete_watchlist, methods=["DELETE"])
    test_app.add_api_route("/api/portfolio", get_portfolio, methods=["GET"])
    test_app.add_api_route("/api/portfolio/trade", post_trade, methods=["POST"])
    test_app.add_api_route("/api/portfolio/history", get_portfolio_history, methods=["GET"])
    test_app.add_api_route("/api/chat", post_chat, methods=["POST"])

    with TestClient(test_app) as test_client:
        yield test_client

    # Restore original paths
    main_module.DB_PATH = original_main
    chat_module.DB_PATH = original_chat
    db_module.DB_PATH = original_db
