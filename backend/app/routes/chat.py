"""LLM chat integration using LiteLLM."""

from __future__ import annotations

import json
import logging
import os
import random
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..market import get_price_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


MOCK_RESPONSES = [
    "Based on your portfolio, you're well-diversified across tech. Your AAPL position has strong momentum. Any specific questions?",
    "Your current cash position of $10,000 keeps you flexible. I can help you analyze positions or execute trades when you're ready.",
    "I've reviewed your portfolio. The overall allocation looks balanced. Let me know if you'd like me to suggest any rebalancing.",
]


async def _db():
    async for conn in db.get_db():
        yield conn


async def _build_context(conn, cache: PriceCache) -> str:
    cash = await db.get_cash_balance(conn)
    positions = await db.get_positions(conn)
    watchlist = await db.get_watchlist(conn)

    lines = [f"Cash: ${cash:.2f}", "Positions:"]
    if not positions:
        lines.append("  (no positions)")
    for pos in positions:
        cur = cache.get_price(pos["ticker"]) or pos["avg_cost"]
        pnl = (cur - pos["avg_cost"]) * pos["quantity"]
        lines.append(
            f"  {pos['ticker']}: {pos['quantity']} shares @ avg ${pos['avg_cost']:.2f}, "
            f"current ${cur:.2f}, P&L ${pnl:.2f}"
        )

    lines.append("Watchlist:")
    for w in watchlist:
        p = cache.get_price(w["ticker"])
        lines.append(f"  {w['ticker']}: ${p:.2f}" if p else f"  {w['ticker']}: N/A")

    total_mv = sum(
        (cache.get_price(p["ticker"]) or p["avg_cost"]) * p["quantity"]
        for p in positions
    )
    lines.append(f"\nTotal portfolio value: ${cash + total_mv:.2f}")
    return "\n".join(lines)


async def _call_llm(message: str, context: str, history: list[dict]) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key or api_key == "your-openrouter-api-key-here":
        return {
            "message": "LLM is not configured. Set OPENROUTER_API_KEY in your .env file to enable AI chat.",
            "trades": [],
            "watchlist_changes": [],
        }

    try:
        import litellm
    except ImportError:
        return {
            "message": "LiteLLM not installed. Run: uv add litellm",
            "trades": [],
            "watchlist_changes": [],
        }

    system_prompt = (
        'You are FinAlly, an AI trading assistant. Respond with valid JSON only. '
        'Schema: {"message": string, "trades": [{"ticker": string, "side": "buy"|"sell", "quantity": number}], '
        '"watchlist_changes": [{"ticker": string, "action": "add"|"remove"}]}. '
        "If no trades or watchlist changes, use empty arrays. "
        "Be concise and data-driven. Only execute trades if the user explicitly asks or agrees."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"Portfolio context:\n{context}"},
    ]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        response = litellm.completion(
            model="openrouter/openai/gpt-oss-120b",
            api_key=api_key,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as exc:
        logger.exception("LLM call failed: %s", exc)
        return {
            "message": f"I had trouble generating a response. Please try again. ({exc})",
            "trades": [],
            "watchlist_changes": [],
        }


async def _execute_trades(conn, trades: list[dict], cache: PriceCache) -> tuple[list[dict], list[str]]:
    executed = []
    errors = []
    for t in trades:
        ticker = t.get("ticker", "").upper()
        qty = float(t.get("quantity", 0))
        side = t.get("side", "").lower()
        if not ticker or qty <= 0 or side not in ("buy", "sell"):
            errors.append(f"Invalid trade: {t}")
            continue

        price = cache.get_price(ticker)
        if not price:
            errors.append(f"Unknown ticker: {ticker}")
            continue

        positions = await db.get_positions(conn)
        current = next((p for p in positions if p["ticker"] == ticker), None)
        cur_qty = current["quantity"] if current else 0.0
        cash = await db.get_cash_balance(conn)

        if side == "buy":
            cost = qty * price.price
            if cost > cash:
                errors.append(f"Insufficient cash for {ticker}: need ${cost:.2f}, have ${cash:.2f}")
                continue
            new_avg = (
                (cur_qty * (current["avg_cost"] if current else price.price) + cost) / (cur_qty + qty)
                if cur_qty > 0 else price.price
            )
            await db.update_cash(conn, "default", -cost)
            await db.upsert_position(conn, ticker, cur_qty + qty, new_avg)
        else:
            if qty > cur_qty:
                errors.append(f"Insufficient shares of {ticker}: asked {qty}, have {cur_qty}")
                continue
            await db.update_cash(conn, "default", qty * price.price)
            await db.upsert_position(conn, ticker, cur_qty - qty, current["avg_cost"])

        trade = await db.record_trade(conn, ticker, side, qty, price.price)
        executed.append(trade)

    return executed, errors


async def _apply_watchlist_changes(conn, changes: list[dict]) -> tuple[list[dict], list[str]]:
    applied = []
    errors = []
    for c in changes:
        ticker = c.get("ticker", "").upper()
        action = c.get("action", "").lower()
        if action == "add":
            result = await db.add_to_watchlist(conn, ticker)
            applied.append(result)
        elif action == "remove":
            removed = await db.remove_from_watchlist(conn, ticker)
            if removed:
                applied.append({"ticker": ticker, "action": "removed"})
            else:
                errors.append(f"{ticker} was not in watchlist")
    return applied, errors


@router.post("")
async def chat(req: ChatRequest, request: Request, conn=Depends(_db)) -> dict[str, Any]:
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    cache = get_price_cache()

    # Mock mode
    if os.environ.get("LLM_MOCK", "").lower() == "true":
        response_text = random.choice(MOCK_RESPONSES)
        await db.save_chat_message(conn, "user", message)
        saved = await db.save_chat_message(conn, "assistant", response_text)
        return {
            "message": response_text,
            "trades": [],
            "watchlist_changes": [],
            "actions": None,
            "id": saved["id"],
        }

    context = await _build_context(conn, cache)
    history = await db.get_chat_history(conn, limit=10)
    await db.save_chat_message(conn, "user", message)

    llm_response = await _call_llm(message, context, history)

    executed_trades, trade_errors = await _execute_trades(conn, llm_response.get("trades", []), cache)
    applied_watchlist, watchlist_errors = await _apply_watchlist_changes(conn, llm_response.get("watchlist_changes", []))

    all_errors = trade_errors + watchlist_errors
    actions = None
    if executed_trades or applied_watchlist or all_errors:
        actions = {
            "trades": executed_trades,
            "watchlist_changes": applied_watchlist,
            "errors": all_errors,
        }

    saved = await db.save_chat_message(conn, "assistant", llm_response.get("message", ""), actions)

    return {
        "message": llm_response.get("message", ""),
        "trades": executed_trades,
        "watchlist_changes": applied_watchlist,
        "actions": actions,
        "id": saved["id"],
    }
