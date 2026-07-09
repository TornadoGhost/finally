"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, DB_PATH
from db.repositories import (
    get_profile,
    update_cash_balance,
    get_watchlist as db_get_watchlist,
    add_watchlist_ticker,
    remove_watchlist_ticker,
    get_positions as db_get_positions,
    upsert_position,
    delete_position,
    record_trade,
    record_snapshot,
    get_snapshots,
)
from app.market import PriceCache, create_market_data_source, create_stream_router

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


@asynccontextmanager
async def _default_lifespan(app: FastAPI):
    """Default production lifespan."""
    await init_db()

    price_cache = PriceCache()
    app.state.price_cache = price_cache

    source = create_market_data_source(price_cache)
    await source.start(DEFAULT_TICKERS)
    app.state.market_source = source

    app.include_router(create_stream_router(price_cache))

    yield

    await source.stop()


app = FastAPI(lifespan=_default_lifespan, title="FinAlly API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files for the frontend (Next.js static export)
static_path = os.path.join(os.path.dirname(__file__), "..", "static")
_has_static = os.path.isdir(static_path)
if _has_static:
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/static/index.html", status_code=307)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


@app.get("/api/watchlist")
async def get_watchlist(request: Request):
    """Return current watchlist with live prices."""
    cache: PriceCache = request.app.state.price_cache
    async with aiosqlite.connect(DB_PATH) as db:
        tickers = await db_get_watchlist(db)
    tickers_data = []
    for ticker in tickers:
        pu = cache.get(ticker)
        if pu:
            tickers_data.append(pu.to_dict())
        else:
            tickers_data.append({
                "ticker": ticker,
                "price": None,
                "previous_price": None,
                "timestamp": None,
                "change": None,
                "change_percent": None,
                "direction": "flat",
            })
    return {"tickers": tickers_data}


@app.post("/api/watchlist")
async def post_watchlist(body: dict, request: Request):
    """Add a ticker to the watchlist."""
    ticker = (body.get("ticker") or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    async with aiosqlite.connect(DB_PATH) as db:
        await add_watchlist_ticker(db, ticker)
    await request.app.state.market_source.add_ticker(ticker)

    return {"added": ticker}


@app.delete("/api/watchlist/{ticker}")
async def delete_watchlist(ticker: str, request: Request):
    """Remove a ticker from the watchlist."""
    ticker = ticker.strip().upper()

    async with aiosqlite.connect(DB_PATH) as db:
        await remove_watchlist_ticker(db, ticker)
    await request.app.state.market_source.remove_ticker(ticker)
    request.app.state.price_cache.remove(ticker)

    return {"removed": ticker}


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


@app.get("/api/portfolio")
async def get_portfolio(request: Request):
    """Return current portfolio: cash, positions enriched with live prices, totals."""
    cache: PriceCache = request.app.state.price_cache
    async with aiosqlite.connect(DB_PATH) as db:
        profile = await get_profile(db)
        cash_balance = profile["cash_balance"]
        rows = await db_get_positions(db)

        positions = []
        unrealized_pnl = 0.0

        for row in rows:
            ticker = row["ticker"]
            quantity = row["quantity"]
            avg_cost = row["avg_cost"]
            pu = cache.get(ticker)
            current_price = pu.price if pu else avg_cost
            pnl = (current_price - avg_cost) * quantity
            pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0
            unrealized_pnl += pnl
            positions.append({
                "ticker": ticker,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "unrealized_pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
            })

        total_value = cash_balance + sum(p["current_price"] * p["quantity"] for p in positions)

        return {
            "cash_balance": cash_balance,
            "positions": positions,
            "total_value": round(total_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
        }


@app.post("/api/portfolio/trade")
async def post_trade(body: dict, request: Request):
    """Execute a market order (buy or sell)."""
    cache: PriceCache = request.app.state.price_cache

    ticker = (body.get("ticker") or "").strip().upper()
    quantity = body.get("quantity")
    side = (body.get("side") or "").lower()

    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be a positive number")
    if side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")

    pu = cache.get(ticker)
    if not pu:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found in price cache")

    price = pu.price
    updated_pos = None

    async with aiosqlite.connect(DB_PATH) as db:
        profile = await get_profile(db)
        cash_balance = profile["cash_balance"]
        positions = await db_get_positions(db)

        if side == "buy":
            cost = round(price * quantity, 2)
            if cost > cash_balance:
                raise HTTPException(status_code=400, detail="Insufficient cash")

            await update_cash_balance(db, -cost)

            existing = next((p for p in positions if p["ticker"] == ticker), None)
            if existing:
                old_qty = existing["quantity"]
                old_avg = existing["avg_cost"]
                new_qty = old_qty + quantity
                new_avg = round((old_avg * old_qty + price * quantity) / new_qty, 4)
            else:
                new_qty = quantity
                new_avg = price

            await upsert_position(db, ticker, new_qty, new_avg)

        else:  # sell
            existing = next((p for p in positions if p["ticker"] == ticker), None)
            if not existing:
                raise HTTPException(status_code=400, detail="No position to sell")

            if quantity > existing["quantity"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient shares: have {existing['quantity']}, tried to sell {quantity}"
                )

            proceeds = round(price * quantity, 2)
            await update_cash_balance(db, proceeds)

            new_qty = round(existing["quantity"] - quantity, 4)
            if new_qty <= 0:
                await delete_position(db, ticker)
            else:
                await upsert_position(db, ticker, new_qty, existing["avg_cost"])

        await record_trade(db, ticker, side, quantity, price)

        # Snapshot total portfolio value after trade
        profile_after = await get_profile(db)
        positions_after = await db_get_positions(db)
        total = profile_after["cash_balance"] + sum(
            p["quantity"] * (cache.get(p["ticker"]).price if cache.get(p["ticker"]) else p["avg_cost"])
            for p in positions_after
        )
        await record_snapshot(db, round(total, 2))

        # Build position response
        updated_pos_row = next((p for p in positions_after if p["ticker"] == ticker), None)
        if updated_pos_row:
            updated_pos = {
                "ticker": updated_pos_row["ticker"],
                "quantity": updated_pos_row["quantity"],
                "avg_cost": updated_pos_row["avg_cost"],
                "current_price": price,
                "unrealized_pnl": round((price - updated_pos_row["avg_cost"]) * updated_pos_row["quantity"], 2),
                "pnl_percent": round(
                    ((price - updated_pos_row["avg_cost"]) / updated_pos_row["avg_cost"] * 100)
                    if updated_pos_row["avg_cost"] else 0.0,
                    2,
                ),
            }

        return {
            "success": True,
            "cash_balance": profile_after["cash_balance"],
            "position": updated_pos,
        }


@app.get("/api/portfolio/history")
async def get_portfolio_history(request: Request):
    """Return portfolio value snapshots for P&L chart."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await get_snapshots(db)
    return {"snapshots": [{"total_value": r["total_value"], "recorded_at": r["recorded_at"]} for r in rows]}


# ---------------------------------------------------------------------------
# Chat (LLM)
# ---------------------------------------------------------------------------

from app.llm import chat_with_llm


@app.post("/api/chat")
async def post_chat(body: dict, request: Request):
    """Chat endpoint — calls the LLM with portfolio context and auto-executes actions."""
    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    return await chat_with_llm(request, message)
