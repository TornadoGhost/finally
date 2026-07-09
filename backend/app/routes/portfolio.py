"""Portfolio API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..market import get_price_cache

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def get_cache(request: Request) -> Any:
    return get_price_cache()


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str  # "buy" or "sell"


async def _db():
    async for conn in db.get_db():
        yield conn


@router.get("")
async def get_portfolio(request: Request, conn=Depends(_db)) -> dict[str, Any]:
    cache = get_price_cache()
    cash = await db.get_cash_balance(conn)
    positions = await db.get_positions(conn)

    enriched = []
    total_market_value = 0.0
    total_cost_basis = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        current_price = cache.get_price(ticker)
        if current_price is None:
            continue
        qty = pos["quantity"]
        cost = pos["avg_cost"]
        market_value = current_price * qty
        cost_basis = cost * qty
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
        enriched.append({
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": cost,
            "current_price": current_price,
            "market_value": market_value,
            "pnl": pnl,
            "pnl_pct": round(pnl_pct, 2),
        })
        total_market_value += market_value
        total_cost_basis += cost_basis

    unrealized = total_market_value - total_cost_basis

    return {
        "cash": round(cash, 2),
        "positions": enriched,
        "total_value": round(cash + total_market_value, 2),
        "unrealized_pnl": round(unrealized, 2),
    }


@router.post("/trade")
async def execute_trade(req: TradeRequest, request: Request, conn=Depends(_db)) -> dict[str, Any]:
    ticker = req.ticker.upper()
    quantity = req.quantity
    side = req.side.lower()
    cache = get_price_cache()

    if side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    price = cache.get_price(ticker)
    if price is None:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found in price cache")

    positions = await db.get_positions(conn)
    position = next((p for p in positions if p["ticker"] == ticker), None)
    current_qty = position["quantity"] if position else 0.0
    cost = quantity * price

    if side == "buy":
        cash = await db.get_cash_balance(conn)
        if cost > cash:
            raise HTTPException(status_code=400, detail="Insufficient cash")
        new_avg_cost = (
            (current_qty * position["avg_cost"] + cost) / (current_qty + quantity)
            if current_qty > 0 else price
        )
        await db.update_cash(conn, "default", -cost)
        await db.upsert_position(conn, ticker, current_qty + quantity, new_avg_cost)
    else:
        if quantity > current_qty:
            raise HTTPException(status_code=400, detail="Insufficient shares")
        await db.update_cash(conn, "default", cost)
        new_qty = current_qty - quantity
        await db.upsert_position(conn, ticker, new_qty, position["avg_cost"])

    trade = await db.record_trade(conn, ticker, side, quantity, price)

    return {
        "trade": trade,
        "message": f"{side.title()} {quantity} {ticker} at ${price:.2f}",
    }


@router.get("/history")
async def get_history(conn=Depends(_db)) -> dict[str, Any]:
    snapshots = await db.get_snapshots(conn)
    return {"snapshots": snapshots}
