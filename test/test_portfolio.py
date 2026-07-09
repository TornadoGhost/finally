"""Portfolio trade execution E2E tests."""

import pytest

INITIAL_CASH = 10000.0


def test_portfolio_initial_state(api):
    """GET /api/portfolio returns cash and empty positions."""
    r = api.get("/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert "cash_balance" in data
    assert "positions" in data
    assert data["cash_balance"] == pytest.approx(INITIAL_CASH)
    assert data["positions"] == []


def test_buy_shares_decreases_cash(api):
    """Buying shares should decrease cash balance."""
    ticker = "AAPL"
    quantity = 5

    # Get current cash
    r = api.get("/api/portfolio")
    cash_before = r.json()["cash_balance"]

    # Get current price
    r = api.get("/api/watchlist")
    prices = {item["ticker"]: item["price"] for item in r.json()}
    price = prices[ticker]

    # Execute buy
    r = api.post("/api/portfolio/trade", json={"ticker": ticker, "quantity": quantity, "side": "buy"})
    assert r.status_code == 200, f"Trade failed: {r.text}"

    # Cash should have decreased by approximately price * quantity
    r = api.get("/api/portfolio")
    cash_after = r.json()["cash_balance"]
    expected_cost = price * quantity
    assert cash_after < cash_before
    assert cash_before - cash_after == pytest.approx(expected_cost, rel=0.01)


def test_buy_creates_position(api):
    """Buying shares should create a position."""
    ticker = "GOOGL"
    quantity = 2

    r = api.post("/api/portfolio/trade", json={"ticker": ticker, "quantity": quantity, "side": "buy"})
    assert r.status_code == 200

    r = api.get("/api/portfolio")
    positions = r.json()["positions"]
    pos = next((p for p in positions if p["ticker"] == ticker), None)
    assert pos is not None, f"Position for {ticker} not found"
    assert pos["quantity"] == quantity


def test_buy_with_insufficient_cash(api):
    """Buying more shares than cash allows should return 400."""
    ticker = "AAPL"
    quantity = 999999
    r = api.post("/api/portfolio/trade", json={"ticker": ticker, "quantity": quantity, "side": "buy"})
    assert r.status_code == 400


def test_sell_shares(api):
    """Selling shares should increase cash and update position."""
    ticker = "MSFT"
    buy_qty = 3
    sell_qty = 2

    # Buy first
    r = api.post("/api/portfolio/trade", json={"ticker": ticker, "quantity": buy_qty, "side": "buy"})
    assert r.status_code == 200

    # Get cash before sell
    r = api.get("/api/portfolio")
    cash_before = r.json()["cash_balance"]

    # Get price
    r = api.get("/api/watchlist")
    prices = {item["ticker"]: item["price"] for item in r.json()}
    price = prices[ticker]

    # Sell partial
    r = api.post("/api/portfolio/trade", json={"ticker": ticker, "quantity": sell_qty, "side": "sell"})
    assert r.status_code == 200

    r = api.get("/api/portfolio")
    data = r.json()
    cash_after = data["cash_balance"]
    pos = next((p for p in data["positions"] if p["ticker"] == ticker), None)

    assert cash_after > cash_before
    assert cash_after - cash_before == pytest.approx(price * sell_qty, rel=0.01)
    assert pos is not None
    assert pos["quantity"] == buy_qty - sell_qty


def test_sell_with_insufficient_shares(api):
    """Selling more shares than owned should return 400."""
    ticker = "AMZN"
    r = api.post("/api/portfolio/trade", json={"ticker": ticker, "quantity": 1000, "side": "sell"})
    assert r.status_code == 400


def test_sell_nonexistent_position(api):
    """Selling a ticker with no position should return 400."""
    # NVDA — try to sell without owning
    r = api.post("/api/portfolio/trade", json={"ticker": "NVDA", "quantity": 1, "side": "sell"})
    assert r.status_code == 400
