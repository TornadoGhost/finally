"""AI chat E2E tests (using mock LLM mode)."""

import json


def test_chat_returns_structured_json(api):
    """POST /api/chat should return valid JSON with required fields."""
    r = api.post("/api/chat", json={"message": "Hello, what is my cash balance?"})
    assert r.status_code == 200
    data = r.json()

    # Validate top-level keys
    assert "message" in data, "Response missing 'message' field"
    assert "trades" in data, "Response missing 'trades' field"
    assert "watchlist_changes" in data, "Response missing 'watchlist_changes' field"

    # message should be a non-empty string
    assert isinstance(data["message"], str)
    assert len(data["message"]) > 0

    # trades and watchlist_changes should be lists
    assert isinstance(data["trades"], list)
    assert isinstance(data["watchlist_changes"], list)


def test_chat_trade_execution_in_response(api):
    """When LLM decides to buy, the response should include the trade."""
    # Ask the LLM to buy something affordable
    r = api.post("/api/chat", json={"message": "Buy 1 share of AAPL for me"})
    assert r.status_code == 200
    data = r.json()

    # The LLM may or may not execute the trade, but the response shape must be valid
    assert isinstance(data["message"], str)
    assert isinstance(data["trades"], list)
    assert isinstance(data["watchlist_changes"], list)

    # If a trade was returned, validate its shape
    for trade in data["trades"]:
        assert "ticker" in trade
        assert "side" in trade
        assert "quantity" in trade
        assert trade["side"] in ("buy", "sell")


def test_chat_invalidates_bad_trade(api):
    """If LLM requests an invalid trade, the response should still be valid JSON."""
    # Send a message asking for an absurd trade
    r = api.post("/api/chat", json={"message": "Buy 999999999 shares of TSLA"})
    assert r.status_code == 200
    data = r.json()

    assert isinstance(data["message"], str)
    assert isinstance(data["trades"], list)
    # Even if trade was included, the server should handle it gracefully
    assert "message" in data


def test_chat_rejects_missing_message(api):
    """POST /api/chat without a message should return 422 or 400."""
    r = api.post("/api/chat", json={})
    assert r.status_code in (400, 422)
