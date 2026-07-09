"""LLM chat integration for FinAlly using LiteLLM.

Provider priority:
  1. OpenRouter (OPENROUTER_API_KEY set)
  2. Local Ollama  (OLLAMA_BASE_URL reachable)
  3. Mock mode     (LLM_MOCK=true)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
import aiosqlite
from fastapi import Request
from litellm import acompletion
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from db import DB_PATH
from db.repositories import (
    get_profile,
    get_positions as db_get_positions,
    get_watchlist as db_get_watchlist,
    get_chat_history,
    save_chat_message,
    upsert_position,
    update_cash_balance,
    delete_position,
    record_trade,
    record_snapshot,
    add_watchlist_ticker,
    remove_watchlist_ticker,
)


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------


class TradeAction(BaseModel):
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    side: str = Field(description="'buy' or 'sell'")
    quantity: float = Field(description="Number of shares")


class WatchlistAction(BaseModel):
    ticker: str = Field(description="Stock ticker symbol")
    action: str = Field(description="'add' or 'remove'")


class ChartAction(BaseModel):
    ticker: str = Field(description="Stock ticker symbol to show chart for")


class ChatResponseSchema(BaseModel):
    message: str = Field(description="Conversational response to the user")
    action_type: str | None = Field(
        default=None,
        description="Semantic action: 'buy_all_watchlist', 'buy_all_watchlist_evenly', or None for single-ticker trades",
    )
    trades: list[TradeAction] = Field(default_factory=list, description="Single-ticker trades to execute")
    watchlist_changes: list[WatchlistAction] = Field(
        default_factory=list, description="Watchlist changes to make"
    )
    charts: list[ChartAction] = Field(
        default_factory=list, description="Tickers to display a chart for"
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant in a simulated trading app.

Portfolio: $10,000 cash. You can suggest/execute trades, manage the watchlist, and show charts.

## GOLDEN RULE: "buy" → TRADES, "show chart" → CHARTS ##

These two actions are COMPLETELY DIFFERENT. You must never confuse them.

- User says "buy", "purchase", "order", "invest", "get" → put in TRADES array with side="buy"
- User says "show chart", "show me the chart", "display chart", "chart for", "show [ticker]" (without buy) → put in CHARTS array

NEVER put a ticker in "charts" if the user wants to BUY it.

## BUYING RULES

### Single ticker buy:
- "buy TSLA" / "buy 1 TSLA" / "purchase TSLA" → 1 trade with that ticker
- "buy 5 shares of TSLA" / "buy TSLA 5 shares" → 1 trade with quantity 5
- "invest 1000 in TSLA" → calculate shares: floor(1000/price), 1 trade

### All-watchlist buy — use action_type field, NOT trades array:
CRITICAL — these two are different, choose carefully:
- "invest all my cash" / "put all money in watchlist" / "buy everything" / "spend all my money"
  → set action_type="buy_all_watchlist", leave trades=[], system divides cash evenly across all watchlist tickers
- "buy 1 share of each" / "1 share of everything" / "1 of each" / "one of each stock"
  → set action_type="buy_one_of_each", leave trades=[], system buys exactly 1 share of every ticker
- "buy 2 shares of each" → set action_type="buy_one_of_each", system buys exactly 2 shares of every ticker

## EXACT JSON EXAMPLES (copy this format exactly)

User: "buy TSLA"
Response: {"message": "Buying 1 share of TSLA.", "trades": [{"ticker": "TSLA", "side": "buy", "quantity": 1}], "watchlist_changes": [], "charts": []}

User: "buy 5 shares of TSLA"
Response: {"message": "Buying 5 shares of TSLA.", "trades": [{"ticker": "TSLA", "side": "buy", "quantity": 5}], "watchlist_changes": [], "charts": []}

User: "buy 1 share of each stock in my watchlist"
Response: {"message": "Buying 1 share of each watchlist ticker.", "action_type": "buy_one_of_each", "trades": [], "watchlist_changes": [], "charts": []}

User: "invest all my cash in the watchlist, divide evenly"
Response: {"message": "Investing all cash across the watchlist, dividing evenly.", "action_type": "buy_all_watchlist", "trades": [], "watchlist_changes": [], "charts": []}

User: "buy everything in my watchlist" (with $10000 and 10 tickers = $1000 each)
AAPL ~$190, GOOGL ~$175, MSFT ~$410, AMZN ~$195, TSLA ~$250, NVDA ~$130, META ~$500, JPM ~$200, V ~$280, NFLX ~$700
Response: {"message": "Dividing $10000 across all 10 watchlist tickers.", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}, {"ticker": "GOOGL", "side": "buy", "quantity": 5}, {"ticker": "MSFT", "side": "buy", "quantity": 2}, {"ticker": "AMZN", "side": "buy", "quantity": 5}, {"ticker": "TSLA", "side": "buy", "quantity": 4}, {"ticker": "NVDA", "side": "buy", "quantity": 7}, {"ticker": "META", "side": "buy", "quantity": 2}, {"ticker": "JPM", "side": "buy", "quantity": 5}, {"ticker": "V", "side": "buy", "quantity": 3}, {"ticker": "NFLX", "side": "buy", "quantity": 1}], "watchlist_changes": [], "charts": []}

User: "show TSLA chart"
Response: {"message": "Here's the TSLA chart.", "trades": [], "watchlist_changes": [], "charts": [{"ticker": "TSLA"}]}

Respond ONLY with valid JSON in this exact shape (no markdown, no extra text):
{"message": "...", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}], "watchlist_changes": [{"ticker": "TSLA", "action": "add"}], "charts": [{"ticker": "AAPL"}]}
If no action needed: {"message": "...", "trades": [], "watchlist_changes": [], "charts": []}
"""


# ---------------------------------------------------------------------------
# Portfolio context
# ---------------------------------------------------------------------------


async def build_portfolio_context(db: Any, price_cache: Any) -> str:
    """Build a text summary of the portfolio for the LLM context."""
    profile = await get_profile(db)
    cash = profile["cash_balance"]

    positions = await db_get_positions(db)
    watchlist_rows = await db_get_watchlist(db)

    lines = [f"Cash balance: ${cash:.2f}", ""]

    if positions:
        lines.append("Positions:")
        for p in positions:
            pu = price_cache.get(p["ticker"])
            cur = pu.price if pu else p["avg_cost"]
            pnl = (cur - p["avg_cost"]) * p["quantity"]
            pnl_pct = ((cur - p["avg_cost"]) / p["avg_cost"] * 100) if p["avg_cost"] else 0.0
            lines.append(
                f"  {p['ticker']}: {p['quantity']} shares @ avg ${p['avg_cost']:.2f}, "
                f"current ${cur:.2f}, P&L ${pnl:.2f} ({pnl_pct:+.2f}%)"
            )
    else:
        lines.append("No open positions.")

    total_pos_value = sum(
        (price_cache.get(p["ticker"]).price if price_cache.get(p["ticker"]) else p["avg_cost"])
        * p["quantity"]
        for p in positions
    )
    total_value = cash + total_pos_value
    lines.append(f"Total portfolio value: ${total_value:.2f}")

    watchlist_tickers = watchlist_rows  # list of ticker strings
    if watchlist_tickers:
        lines.append(f"Watchlist: {', '.join(watchlist_tickers)}")
        lines.append("Watchlist prices:")
        for ticker in watchlist_tickers:
            pu = price_cache.get(ticker)
            if pu:
                lines.append(f"  {ticker}: ${pu.price:.2f} ({pu.direction} {pu.change_percent:+.2f}%)")
            else:
                lines.append(f"  {ticker}: (price unavailable)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_mock_mode() -> bool:
    return os.environ.get("LLM_MOCK", "false").lower() == "true"


def _is_ollama_available() -> bool:
    """Check if Ollama is reachable at OLLAMA_BASE_URL (default: http://ollama:11434 for Docker)."""
    url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{url}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")


async def _call_ollama(messages: list[dict[str, str]]) -> dict[str, Any] | None:
    """Call local Ollama directly via its REST API. Returns parsed JSON or None on failure."""
    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.7,
                    "num_predict": 512,
                },
            }
            response = await client.post(f"{url}/api/chat", json=payload)
            if response.status_code != 200:
                logger.warning("Ollama returned %s: %s", response.status_code, response.text)
                return None
            raw = response.json()
            content = raw.get("message", {}).get("content", "")
            # Strip markdown code fences if present
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else content
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content.strip())
            # Ollama may wrap the JSON response as a string inside "content"
            if isinstance(parsed, dict) and "message" in parsed and isinstance(parsed.get("content"), str):
                inner = parsed["content"]
                try:
                    parsed = json.loads(inner)
                except Exception:
                    pass  # keep original if not parseable JSON
            return parsed
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None


async def _execute_trade(
    db: Any,
    cache: Any,
    ticker: str,
    side: str,
    quantity: float,
) -> dict[str, Any]:
    """Execute a single trade, returning success/failure info."""
    try:
        ticker = ticker.strip().upper()
        if side not in ("buy", "sell"):
            return {"ticker": ticker, "side": side, "quantity": quantity, "success": False, "error": "Invalid side"}

        pu = cache.get(ticker)
        if not pu:
            return {"ticker": ticker, "side": side, "quantity": quantity, "success": False, "error": f"Ticker '{ticker}' not found in price cache"}

        price = pu.price
        profile = await get_profile(db)
        cash_balance = profile["cash_balance"]
        positions = await db_get_positions(db)

        if side == "buy":
            cost = round(price * quantity, 2)
            if cost > cash_balance:
                return {
                    "ticker": ticker, "side": side, "quantity": quantity,
                    "success": False, "error": f"Insufficient cash (need ${cost:.2f}, have ${cash_balance:.2f})",
                }
            await update_cash_balance(db, -cost)
            existing = next((p for p in positions if p["ticker"] == ticker), None)
            if existing:
                new_qty = existing["quantity"] + quantity
                new_avg = round((existing["avg_cost"] * existing["quantity"] + price * quantity) / new_qty, 4)
            else:
                new_qty = quantity
                new_avg = price
            await upsert_position(db, ticker, new_qty, new_avg)
        else:
            existing = next((p for p in positions if p["ticker"] == ticker), None)
            if not existing:
                return {"ticker": ticker, "side": side, "quantity": quantity, "success": False, "error": "No position to sell"}
            if quantity > existing["quantity"]:
                return {
                    "ticker": ticker, "side": side, "quantity": quantity,
                    "success": False,
                    "error": f"Insufficient shares (have {existing['quantity']}, tried to sell {quantity})",
                }
            proceeds = round(price * quantity, 2)
            await update_cash_balance(db, proceeds)
            new_qty = round(existing["quantity"] - quantity, 4)
            if new_qty <= 0:
                await delete_position(db, ticker)
            else:
                await upsert_position(db, ticker, new_qty, existing["avg_cost"])

        await record_trade(db, ticker, side, quantity, price)

        # Snapshot after trade
        profile_after = await get_profile(db)
        positions_after = await db_get_positions(db)
        total = profile_after["cash_balance"] + sum(
            (cache.get(p["ticker"]).price if cache.get(p["ticker"]) else p["avg_cost"]) * p["quantity"]
            for p in positions_after
        )
        await record_snapshot(db, round(total, 2))

        return {"ticker": ticker, "side": side, "quantity": quantity, "success": True}

    except Exception as exc:
        return {"ticker": ticker, "side": side, "quantity": quantity, "success": False, "error": str(exc)}


async def _apply_watchlist_change(
    db: Any,
    market_source: Any,
    price_cache: Any,
    ticker: str,
    action: str,
) -> dict[str, Any]:
    """Apply a watchlist add or remove."""
    try:
        ticker = ticker.strip().upper()
        if action == "add":
            await add_watchlist_ticker(db, ticker)
            market_source.add_ticker(ticker)
            return {"ticker": ticker, "action": "add", "success": True}
        elif action == "remove":
            await remove_watchlist_ticker(db, ticker)
            market_source.remove_ticker(ticker)
            price_cache.remove(ticker)
            return {"ticker": ticker, "action": "remove", "success": True}
        else:
            return {"ticker": ticker, "action": action, "success": False, "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"ticker": ticker, "action": action, "success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def chat_with_llm(request: Request, message: str) -> dict[str, Any]:
    """Process a user chat message, call the LLM, auto-execute actions, return the response."""
    cache: Any = request.app.state.price_cache
    market_source: Any = request.app.state.market_source

    # 1. Load chat history and build context (read from DB)
    async with aiosqlite.connect(DB_PATH) as db:
        chat_history = await get_chat_history(db, limit=50)
        portfolio_ctx = await build_portfolio_context(db, cache)

    # 2. Build messages array
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Portfolio context:\n{portfolio_ctx}"},
    ]
    for entry in chat_history:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": message})

    # 3. Get LLM response (mock or real)
    if _is_mock_mode():
        response_data: dict[str, Any] = {
            "message": "Mock response: I'm analyzing your portfolio and ready to assist with trades.",
            "trades": [],
            "watchlist_changes": [],
        }
    else:
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        response_data = None

        if openrouter_key:
            try:
                response = await acompletion(
                    model="openrouter/openai/gpt-oss-120b",
                    api_base="https://openrouter.ai/api/v1",
                    api_key=openrouter_key,
                    messages=messages,
                    response_format=ChatResponseSchema,
                    timeout=60,
                )
                raw = response.choices[0].message.content
                if raw.startswith("```"):
                    parts = raw.split("```")
                    raw = parts[1] if len(parts) > 1 else raw
                    if raw.startswith("json"):
                        raw = raw[4:]
                response_data = json.loads(raw.strip())
                logger.debug("LLM raw response: %s", raw[:500])
            except Exception as exc:
                logger.warning("OpenRouter call failed: %s", exc)

        if response_data is None and _is_ollama_available():
            logger.info("OpenRouter unavailable, falling back to Ollama")
            response_data = await _call_ollama(messages)

    if isinstance(response_data, ChatResponseSchema):
        response_data = response_data.model_dump()

    # 4. Auto-execute trades and watchlist changes
    trade_results: list[dict[str, Any]] = []
    watchlist_results: list[dict[str, Any]] = []
    errors: list[str] = []

    async with aiosqlite.connect(DB_PATH) as db:
        # Handle "buy all watchlist" — LLM returns action_type, we expand to all tickers
        action_type = response_data.get("action_type")
        # Fallback: if LLM didn't set action_type but also returned no explicit trades,
        # infer from message content which strategy the user wants
        if action_type is None and not response_data.get("trades"):
            message = response_data.get("message", "").lower()
            invest_keywords = {"invest", "all cash", "all my cash", "all the cash", "divide evenly", "evenly across"}
            if any(kw in message for kw in invest_keywords):
                action_type = "buy_all_watchlist"
            else:
                action_type = "buy_one_of_each"

        if action_type in ("buy_all_watchlist", "buy_one_of_each"):
            profile = await get_profile(db)
            cash_balance = profile["cash_balance"]
            watchlist = await db_get_watchlist(db)

            if watchlist:
                if action_type == "buy_one_of_each":
                    # Buy exactly 1 share of every ticker
                    for ticker in watchlist:
                        pu = cache.get(ticker)
                        price = pu.price if pu else None
                        if price and price > 0:
                            result = await _execute_trade(db, cache, ticker, "buy", 1)
                            trade_results.append(result)
                            if not result["success"]:
                                errors.append(f"Trade failed for {result['ticker']}: {result.get('error', 'unknown error')}")
                        else:
                            trade_results.append({"ticker": ticker, "side": "buy", "quantity": 0, "success": False, "error": "Price unavailable"})
                elif action_type == "buy_all_watchlist":
                    # Divide cash evenly across all watchlist tickers
                    if cash_balance > 0:
                        cash_per_ticker = cash_balance / len(watchlist)
                        for ticker in watchlist:
                            pu = cache.get(ticker)
                            price = pu.price if pu else None
                            if price and price > 0:
                                quantity = int(cash_per_ticker / price)
                                if quantity > 0:
                                    result = await _execute_trade(db, cache, ticker, "buy", quantity)
                                    trade_results.append(result)
                                    if not result["success"]:
                                        errors.append(f"Trade failed for {result['ticker']}: {result.get('error', 'unknown error')}")
                            else:
                                trade_results.append({"ticker": ticker, "side": "buy", "quantity": 0, "success": False, "error": "Price unavailable"})
                    else:
                        errors.append("No watchlist tickers or zero cash balance.")
            else:
                errors.append("Watchlist is empty.")
        else:
            # Single-ticker trades from LLM response
            for trade in response_data.get("trades", []):
                result = await _execute_trade(db, cache, trade["ticker"], trade["side"], trade["quantity"])
                trade_results.append(result)
                if not result["success"]:
                    errors.append(f"Trade failed for {result['ticker']}: {result.get('error', 'unknown error')}")

        for wc in response_data.get("watchlist_changes", []):
            result = await _apply_watchlist_change(db, market_source, cache, wc["ticker"], wc["action"])
            watchlist_results.append(result)
            if not result["success"]:
                errors.append(f"Watchlist change failed for {result['ticker']}: {result.get('error', 'unknown error')}")

        final_message = response_data.get("message", "")
        if errors:
            final_message += "\n\nNote: " + " ".join(errors)

        actions_dict = {
            "trades": trade_results,
            "watchlist_changes": watchlist_results,
        }
        await save_chat_message(db, "assistant", final_message, actions_dict)

    return {
        "message": final_message,
        "trades": trade_results,
        "watchlist_changes": watchlist_results,
        "charts": response_data.get("charts", []),
    }
