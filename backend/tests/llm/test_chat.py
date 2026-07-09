"""Tests for LLM chat integration."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.llm.chat import (
    build_portfolio_context,
    chat_with_llm,
    ChatResponseSchema,
    TradeAction,
    WatchlistAction,
    _is_mock_mode,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    pu = MagicMock()
    pu.price = 190.0
    pu.direction = "flat"
    pu.change_percent = 0.0
    cache.get.return_value = pu
    return cache


@pytest.fixture
def mock_market_source():
    return MagicMock()


@pytest.fixture
def mock_request(mock_db, mock_cache, mock_market_source):
    request = MagicMock()
    request.app.state.db = mock_db
    request.app.state.price_cache = mock_cache
    request.app.state.market_source = mock_market_source
    return request


# ---------------------------------------------------------------------------
# Tests: build_portfolio_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_portfolio_context_empty(mock_db, mock_cache):
    """Portfolio context shows no positions when portfolio is empty."""
    with patch("app.llm.chat.get_profile", new_callable=AsyncMock) as m_profile, \
         patch("app.llm.chat.db_get_positions", new_callable=AsyncMock) as m_positions, \
         patch("app.llm.chat.db_get_watchlist", new_callable=AsyncMock) as m_watchlist:

        m_profile.return_value = {"cash_balance": 10000.0}
        m_positions.return_value = []
        m_watchlist.return_value = []

        ctx = await build_portfolio_context(mock_db, mock_cache)

        assert "Cash balance: $10000.00" in ctx
        assert "No open positions" in ctx
        assert "Total portfolio value: $10000.00" in ctx


@pytest.mark.asyncio
async def test_build_portfolio_context_with_positions(mock_db, mock_cache):
    """Portfolio context includes position details when positions exist."""
    with patch("app.llm.chat.get_profile", new_callable=AsyncMock) as m_profile, \
         patch("app.llm.chat.db_get_positions", new_callable=AsyncMock) as m_positions, \
         patch("app.llm.chat.db_get_watchlist", new_callable=AsyncMock) as m_watchlist:

        m_profile.return_value = {"cash_balance": 8500.0}

        pu_aapl = MagicMock()
        pu_aapl.price = 195.0
        pu_aapl.direction = "up"
        pu_aapl.change_percent = 2.5
        pu_tsla = MagicMock()
        pu_tsla.price = 250.0
        pu_tsla.direction = "down"
        pu_tsla.change_percent = -1.2
        mock_cache.get.side_effect = lambda t: {"AAPL": pu_aapl, "TSLA": pu_tsla, "GOOGL": pu_aapl}.get(t)

        m_positions.return_value = [
            {"ticker": "AAPL", "quantity": 10, "avg_cost": 180.0},
            {"ticker": "TSLA", "quantity": 5, "avg_cost": 220.0},
        ]
        m_watchlist.return_value = ["AAPL", "TSLA", "GOOGL"]

        ctx = await build_portfolio_context(mock_db, mock_cache)

        assert "Cash balance: $8500.00" in ctx
        assert "AAPL" in ctx
        assert "TSLA" in ctx
        assert "Watchlist:" in ctx
        assert "AAPL, TSLA, GOOGL" in ctx
        # AAPL: (195-180)*10 = 150, TSLA: (250-220)*5 = 150, total = 10900+8500
        assert "Total portfolio value:" in ctx


# ---------------------------------------------------------------------------
# Tests: mock mode
# ---------------------------------------------------------------------------

def test_is_mock_mode_true(monkeypatch):
    """_is_mock_mode returns True when LLM_MOCK=true."""
    monkeypatch.setenv("LLM_MOCK", "true")
    assert _is_mock_mode() is True


def test_is_mock_mode_false(monkeypatch):
    """_is_mock_mode returns False when LLM_MOCK is not set."""
    monkeypatch.delenv("LLM_MOCK", raising=False)
    assert _is_mock_mode() is False


def test_is_mock_mode_case_insensitive(monkeypatch):
    """_is_mock_mode is case-insensitive."""
    monkeypatch.setenv("LLM_MOCK", "TRUE")
    assert _is_mock_mode() is True


# ---------------------------------------------------------------------------
# Tests: chat_with_llm saves messages to history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_saves_messages_to_history(mock_request):
    """chat_with_llm saves user message and assistant response to chat history."""
    with patch("app.llm.chat.get_chat_history", new_callable=AsyncMock) as m_history, \
         patch("app.llm.chat.build_portfolio_context", new_callable=AsyncMock) as m_ctx, \
         patch("app.llm.chat._is_mock_mode", return_value=True), \
         patch("app.llm.chat.save_chat_message", new_callable=AsyncMock) as m_save, \
         patch("app.llm.chat.get_profile", new_callable=AsyncMock) as m_profile, \
         patch("app.llm.chat.db_get_positions", new_callable=AsyncMock) as m_positions, \
         patch("app.llm.chat.db_get_watchlist", new_callable=AsyncMock) as m_watchlist:

        m_history.return_value = []
        m_ctx.return_value = "Cash: $10000"
        m_profile.return_value = {"cash_balance": 10000.0}
        m_positions.return_value = []
        m_watchlist.return_value = []

        result = await chat_with_llm(mock_request, "Hello, what should I buy?")

        # Save is called once for the assistant response (not the user message)
        assert m_save.call_count == 1
        # Result should be the mock response
        assert "Mock response" in result["message"]


# ---------------------------------------------------------------------------
# Tests: trade execution in chat response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_executes_trades_from_llm_response(mock_request):
    """Trades in the LLM response are executed and included in the result."""
    with patch("app.llm.chat.get_chat_history", new_callable=AsyncMock) as m_history, \
         patch("app.llm.chat.build_portfolio_context", new_callable=AsyncMock) as m_ctx, \
         patch("app.llm.chat._is_mock_mode", return_value=False), \
         patch("app.llm.chat._is_ollama_available", return_value=False), \
         patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), \
         patch("app.llm.chat.save_chat_message", new_callable=AsyncMock) as m_save, \
         patch("app.llm.chat.get_profile", new_callable=AsyncMock) as m_profile, \
         patch("app.llm.chat.db_get_positions", new_callable=AsyncMock) as m_positions, \
         patch("app.llm.chat.db_get_watchlist", new_callable=AsyncMock) as m_watchlist, \
         patch("app.llm.chat.acompletion", new_callable=AsyncMock) as m_complete, \
         patch("app.llm.chat.update_cash_balance", new_callable=AsyncMock), \
         patch("app.llm.chat.upsert_position", new_callable=AsyncMock), \
         patch("app.llm.chat.record_trade", new_callable=AsyncMock), \
         patch("app.llm.chat.record_snapshot", new_callable=AsyncMock):

        m_history.return_value = []
        m_ctx.return_value = "Cash: $10000"

        pu = MagicMock()
        pu.price = 190.0
        mock_request.app.state.price_cache.get.return_value = pu

        m_profile.return_value = {"cash_balance": 10000.0}
        m_positions.return_value = []
        m_watchlist.return_value = []

        # Simulate LLM returning a buy trade
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "message": "Buying 10 shares of AAPL.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [],
        })
        m_complete.return_value = mock_response

        result = await chat_with_llm(mock_request, "Buy 10 shares of AAPL")

        assert result["trades"][0]["ticker"] == "AAPL"
        assert result["trades"][0]["success"] is True
        assert "Buy 10 shares of AAPL" in result["message"] or "AAPL" in result["message"]


# ---------------------------------------------------------------------------
# Tests: watchlist change in chat response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_applies_watchlist_changes(mock_request):
    """Watchlist changes in the LLM response are applied and included in the result."""
    with patch("app.llm.chat.get_chat_history", new_callable=AsyncMock) as m_history, \
         patch("app.llm.chat.build_portfolio_context", new_callable=AsyncMock) as m_ctx, \
         patch("app.llm.chat._is_mock_mode", return_value=False), \
         patch("app.llm.chat._is_ollama_available", return_value=False), \
         patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), \
         patch("app.llm.chat.save_chat_message", new_callable=AsyncMock) as m_save, \
         patch("app.llm.chat.get_profile", new_callable=AsyncMock) as m_profile, \
         patch("app.llm.chat.db_get_positions", new_callable=AsyncMock) as m_positions, \
         patch("app.llm.chat.db_get_watchlist", new_callable=AsyncMock) as m_watchlist, \
         patch("app.llm.chat.acompletion", new_callable=AsyncMock) as m_complete, \
         patch("app.llm.chat.add_watchlist_ticker", new_callable=AsyncMock) as m_add, \
         patch("app.llm.chat.remove_watchlist_ticker", new_callable=AsyncMock) as m_rem:

        m_history.return_value = []
        m_ctx.return_value = "Cash: $10000"
        m_profile.return_value = {"cash_balance": 10000.0}
        m_positions.return_value = []
        m_watchlist.return_value = []

        # Simulate LLM returning a watchlist add
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "message": "Adding AMD to your watchlist.",
            "trades": [],
            "watchlist_changes": [{"ticker": "AMD", "action": "add"}],
        })
        m_complete.return_value = mock_response

        result = await chat_with_llm(mock_request, "Add AMD to my watchlist")

        m_add.assert_awaited_once()
        assert result["watchlist_changes"][0]["ticker"] == "AMD"
        assert result["watchlist_changes"][0]["success"] is True


# ---------------------------------------------------------------------------
# Tests: buy all watchlist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_portfolio_context_shows_watchlist_prices(mock_db, mock_cache):
    """Portfolio context includes live prices for all watchlist tickers."""
    with patch("app.llm.chat.get_profile", new_callable=AsyncMock) as m_profile, \
         patch("app.llm.chat.db_get_positions", new_callable=AsyncMock) as m_positions, \
         patch("app.llm.chat.db_get_watchlist", new_callable=AsyncMock) as m_watchlist:

        m_profile.return_value = {"cash_balance": 10000.0}
        m_positions.return_value = []

        pu_aapl = MagicMock()
        pu_aapl.price = 190.50
        pu_aapl.direction = "up"
        pu_aapl.change_percent = 1.25
        pu_googl = MagicMock()
        pu_googl.price = 175.00
        pu_googl.direction = "down"
        pu_googl.change_percent = -0.50
        mock_cache.get.side_effect = lambda t: {"AAPL": pu_aapl, "GOOGL": pu_googl}.get(t)

        m_watchlist.return_value = ["AAPL", "GOOGL"]

        ctx = await build_portfolio_context(mock_db, mock_cache)

        assert "Watchlist prices:" in ctx
        assert "AAPL: $190.50" in ctx
        assert "GOOGL: $175.00" in ctx
        assert "(up +1.25%)" in ctx
        assert "(down -0.50%)" in ctx


@pytest.mark.asyncio
async def test_chat_buy_all_watchlist_expands_to_all_tickers(mock_request):
    """When LLM returns action_type=buy_all_watchlist, system expands to all watchlist tickers."""
    with patch("app.llm.chat.get_chat_history", new_callable=AsyncMock) as m_history, \
         patch("app.llm.chat.build_portfolio_context", new_callable=AsyncMock) as m_ctx, \
         patch("app.llm.chat._is_mock_mode", return_value=False), \
         patch("app.llm.chat._is_ollama_available", return_value=False), \
         patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), \
         patch("app.llm.chat.save_chat_message", new_callable=AsyncMock) as m_save, \
         patch("app.llm.chat.get_profile", new_callable=AsyncMock) as m_profile, \
         patch("app.llm.chat.db_get_positions", new_callable=AsyncMock) as m_positions, \
         patch("app.llm.chat.db_get_watchlist", new_callable=AsyncMock) as m_watchlist, \
         patch("app.llm.chat.acompletion", new_callable=AsyncMock) as m_complete, \
         patch("app.llm.chat.update_cash_balance", new_callable=AsyncMock) as m_cash, \
         patch("app.llm.chat.upsert_position", new_callable=AsyncMock) as m_upsert, \
         patch("app.llm.chat.record_trade", new_callable=AsyncMock), \
         patch("app.llm.chat.record_snapshot", new_callable=AsyncMock):

        m_history.return_value = []
        m_ctx.return_value = "Cash: $10000\nWatchlist: AAPL, GOOGL, MSFT"

        # Simulate watchlist prices
        pu_aapl = MagicMock()
        pu_aapl.price = 200.0
        pu_googl = MagicMock()
        pu_googl.price = 150.0
        pu_msft = MagicMock()
        pu_msft.price = 100.0
        mock_request.app.state.price_cache.get.side_effect = lambda t: {
            "AAPL": pu_aapl, "GOOGL": pu_googl, "MSFT": pu_msft
        }.get(t)

        m_profile.return_value = {"cash_balance": 10000.0}
        m_positions.return_value = []
        m_watchlist.return_value = ["AAPL", "GOOGL", "MSFT"]

        # Simulate LLM returning action_type=buy_one_of_each
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "message": "Buying 1 share of each watchlist ticker.",
            "action_type": "buy_one_of_each",
            "trades": [],
            "watchlist_changes": [],
            "charts": [],
        })
        m_complete.return_value = mock_response

        result = await chat_with_llm(mock_request, "Buy 1 share of each stock in my watchlist")

        # All 3 watchlist tickers should be expanded into trades
        assert len(result["trades"]) == 3
        tickers = {t["ticker"] for t in result["trades"]}
        assert tickers == {"AAPL", "GOOGL", "MSFT"}
        # All should succeed (sufficient cash)
        for trade in result["trades"]:
            assert trade["success"] is True
        # upsert_position called 3 times
        assert m_upsert.await_count == 3
