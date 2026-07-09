"""Watchlist API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..market import get_price_cache

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    ticker: str


async def _db():
    async for conn in db.get_db():
        yield conn


@router.get("")
async def get_watchlist(request: Request, conn=Depends(_db)) -> dict[str, Any]:
    items = await db.get_watchlist(conn)
    cache = get_price_cache()
    result = []
    for item in items:
        ticker = item["ticker"]
        price_update = cache.get(ticker)
        result.append({
            "ticker": ticker,
            "added_at": item["added_at"],
            "price": price_update.price if price_update else None,
            "previous_price": price_update.previous_price if price_update else None,
            "change": price_update.change if price_update else None,
            "change_percent": price_update.change_percent if price_update else None,
            "direction": price_update.direction if price_update else None,
            "timestamp": price_update.timestamp if price_update else None,
        })
    return {"watchlist": result}


@router.post("")
async def add_ticker(req: AddTickerRequest, request: Request, conn=Depends(_db)) -> dict[str, Any]:
    ticker = req.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker cannot be empty")
    if len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    result = await db.add_to_watchlist(conn, ticker)
    cache = get_price_cache()
    price_update = cache.get(ticker)
    return {
        "ticker": ticker,
        "added": True,
        "price": price_update.price if price_update else None,
    }


@router.delete("/{ticker}")
async def remove_ticker(ticker: str, request: Request, conn=Depends(_db)) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    removed = await db.remove_from_watchlist(conn, ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not in watchlist")
    return {"ticker": ticker, "removed": True}
