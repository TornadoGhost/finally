"""FinAlly FastAPI application."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from . import db
from .market import PriceCache, create_market_data_source, create_stream_router, register_price_cache
from .routes import health, portfolio, watchlist, chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Shared State (module-level so routers can reference it at startup) ─────────

price_cache: PriceCache = PriceCache()
register_price_cache(price_cache)
stream_router = create_stream_router(price_cache)

# ── App Lifespan ──────────────────────────────────────────────────────────────

_market_source = None
_snapshot_task: asyncio.Task | None = None


async def _snapshot_loop() -> None:
    """Record portfolio total value every 30 seconds."""
    while True:
        try:
            async for conn in db.get_db():
                cash = await db.get_cash_balance(conn)
                positions = await db.get_positions(conn)
                total_mv = sum(
                    (price_cache.get_price(p["ticker"]) or p["avg_cost"]) * p["quantity"]
                    for p in positions
                )
                total_value = cash + total_mv
                await db.record_snapshot(conn, total_value)
                break
        except Exception:
            logger.exception("Snapshot recording failed")
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _market_source, _snapshot_task

    # 1. Init database (creates schema + seeds if needed)
    db.init_db()
    logger.info("Database initialized")

    # 2. Start market data source
    source = create_market_data_source(price_cache)
    _market_source = source

    try:
        async for conn in db.get_db():
            wl = await db.get_watchlist(conn)
            tickers = [w["ticker"] for w in wl]
            break
        if tickers:
            await source.start(tickers)
            logger.info("Market data source started with tickers: %s", tickers)
    except Exception:
        logger.warning("Could not load watchlist tickers, using defaults")
        await source.start(["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                           "NVDA", "META", "JPM", "V", "NFLX"])

    # 3. Start snapshot background task
    _snapshot_task = asyncio.create_task(_snapshot_loop())

    yield

    # Shutdown
    if _snapshot_task:
        _snapshot_task.cancel()
    if _market_source:
        await _market_source.stop()
    logger.info("FinAlly shutdown complete")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(title="FinAlly API", version="1.0.0", lifespan=lifespan)

# Mount API routes — ALL before StaticFiles so they take precedence
app.include_router(health.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(chat.router)
app.include_router(stream_router)


# ── Static File Serving (Next.js export) ─────────────────────────────────────

_build_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          "frontend", ".next", "standalone")
_static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                           "frontend", "out")

if os.path.isdir(_static_dir):
    app.mount("/out", StaticFiles(directory=_static_dir, html=True), name="static")
elif os.path.isdir(_build_dir):
    app.mount("/out", StaticFiles(directory=_build_dir, html=True), name="static")

# SPA fallback for root access
@app.get("/")
async def root():
    return RedirectResponse(url="/out/index.html")
