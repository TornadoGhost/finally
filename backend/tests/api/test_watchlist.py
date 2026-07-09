"""Watchlist API endpoint tests."""

from __future__ import annotations

import pytest


def test_get_watchlist_returns_default_tickers(client):
    """GET /api/watchlist returns seeded tickers with prices from cache."""
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    data = resp.json()
    assert "tickers" in data
    tickers_list = data["tickers"]
    assert len(tickers_list) == 3  # seeded: AAPL, GOOGL, MSFT

    tickers_found = {t["ticker"] for t in tickers_list}
    assert tickers_found == {"AAPL", "GOOGL", "MSFT"}

    for entry in tickers_list:
        assert entry["ticker"] in tickers_found
        assert entry["price"] is not None
        assert entry["direction"] in ("up", "down", "flat")


def test_post_watchlist_adds_ticker(client):
    """POST /api/watchlist adds a new ticker and returns it."""
    resp = client.post("/api/watchlist", json={"ticker": "NVDA"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["added"] == "NVDA"

    resp2 = client.get("/api/watchlist")
    tickers = {t["ticker"] for t in resp2.json()["tickers"]}
    assert "NVDA" in tickers


def test_post_watchlist_uppercases_ticker(client):
    """POST /api/watchlist normalizes ticker to uppercase."""
    resp = client.post("/api/watchlist", json={"ticker": "nvda"})
    assert resp.status_code == 200
    assert resp.json()["added"] == "NVDA"


def test_post_watchlist_rejects_missing_ticker(client):
    """POST /api/watchlist returns 400 for missing ticker field."""
    resp = client.post("/api/watchlist", json={})
    assert resp.status_code == 400  # Our handler raises HTTPException(400) for missing/blank ticker


def test_delete_watchlist_removes_ticker(client):
    """DELETE /api/watchlist/{ticker} removes the ticker."""
    resp = client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 200
    assert resp.json()["removed"] == "AAPL"

    resp2 = client.get("/api/watchlist")
    tickers = {t["ticker"] for t in resp2.json()["tickers"]}
    assert "AAPL" not in tickers


def test_delete_watchlist_idempotent(client):
    """DELETE /api/watchlist/{ticker} succeeds even if ticker already gone."""
    client.delete("/api/watchlist/AAPL")
    resp = client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 200  # No 404
