"""Portfolio API endpoint tests."""

from __future__ import annotations

import pytest


def test_get_portfolio_empty(client):
    """GET /api/portfolio returns correct structure with no positions."""
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cash_balance"] == 10000.0
    assert data["positions"] == []
    assert data["total_value"] == 10000.0
    assert "unrealized_pnl" in data


def test_buy_succeeds_with_sufficient_cash(client):
    """POST /api/portfolio/trade buy succeeds and updates cash and positions."""
    resp = client.post("/api/portfolio/trade", json={
        "ticker": "AAPL",
        "quantity": 10,
        "side": "buy",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["cash_balance"] == 10000.0 - (190.0 * 10)  # 8100
    assert data["position"]["ticker"] == "AAPL"
    assert data["position"]["quantity"] == 10


def test_buy_fails_insufficient_cash(client):
    """POST /api/portfolio/trade buy fails with 400 when cash insufficient."""
    resp = client.post("/api/portfolio/trade", json={
        "ticker": "AAPL",
        "quantity": 1000,  # 190000 > 10000 cash
        "side": "buy",
    })
    assert resp.status_code == 400
    assert "Insufficient cash" in resp.json()["detail"]


def test_buy_then_sell_succeeds(client):
    """Buy shares then sell some — both succeed."""
    r1 = client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "quantity": 10, "side": "buy",
    })
    assert r1.status_code == 200

    r2 = client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "quantity": 5, "side": "sell",
    })
    assert r2.status_code == 200
    data = r2.json()
    assert data["position"]["quantity"] == 5
    assert data["cash_balance"] == 10000.0 - (190.0 * 10) + (190.0 * 5)  # 8500


def test_sell_fails_no_position(client):
    """POST /api/portfolio/trade sell fails with 400 when no position held."""
    resp = client.post("/api/portfolio/trade", json={
        "ticker": "AAPL",
        "quantity": 5,
        "side": "sell",
    })
    assert resp.status_code == 400
    assert "No position to sell" in resp.json()["detail"]


def test_sell_fails_insufficient_shares(client):
    """POST /api/portfolio/trade sell fails with 400 when not enough shares."""
    client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "quantity": 5, "side": "buy",
    })
    resp = client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "quantity": 10, "side": "sell",
    })
    assert resp.status_code == 400
    assert "Insufficient shares" in resp.json()["detail"]


def test_buy_ticker_not_in_cache(client, price_cache):
    """POST /api/portfolio/trade returns 404 for unknown ticker."""
    resp = client.post("/api/portfolio/trade", json={
        "ticker": "UNKNOWN", "quantity": 5, "side": "buy",
    })
    assert resp.status_code == 404


def test_get_portfolio_with_position(client):
    """GET /api/portfolio includes position with correct P&L."""
    client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "quantity": 10, "side": "buy",
    })
    resp = client.get("/api/portfolio")
    data = resp.json()
    assert len(data["positions"]) == 1
    pos = data["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 190.0
    assert pos["current_price"] == 190.0
    assert pos["unrealized_pnl"] == 0.0


def test_get_portfolio_history_empty(client):
    """GET /api/portfolio/history returns empty snapshots list initially."""
    resp = client.get("/api/portfolio/history")
    assert resp.status_code == 200
    assert "snapshots" in resp.json()


def test_get_portfolio_history_after_trade(client):
    """GET /api/portfolio/history returns snapshots including post-trade snapshot."""
    client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "quantity": 10, "side": "buy",
    })
    resp = client.get("/api/portfolio/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["snapshots"]) >= 1
    snap = data["snapshots"][-1]
    assert "total_value" in snap
    assert "recorded_at" in snap
