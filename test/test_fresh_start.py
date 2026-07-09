"""Fresh-start E2E tests: verify a fresh instance loads with correct defaults."""

DEFAULT_TICKERS = {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}
INITIAL_CASH = 10000.0


def test_health_endpoint(api):
    """The app should respond to /api/health."""
    r = api.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data or "message" in data


def test_default_watchlist(api):
    """On first launch, the watchlist should contain 10 default tickers."""
    r = api.get("/api/watchlist")
    assert r.status_code == 200
    data = r.json()
    tickers = {item["ticker"] for item in data}
    assert tickers == DEFAULT_TICKERS, f"Expected {DEFAULT_TICKERS}, got {tickers}"


def test_initial_cash_balance(api):
    """New user should have exactly $10,000 in cash."""
    r = api.get("/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert data["cash_balance"] == INITIAL_CASH


def test_initial_portfolio_no_positions(api):
    """New user should have no open positions."""
    r = api.get("/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert data["positions"] == []


def test_watchlist_prices_stream(api):
    """Watchlist items should have price data."""
    r = api.get("/api/watchlist")
    assert r.status_code == 200
    data = r.json()
    for item in data:
        assert "price" in item, f"Missing price for {item.get('ticker')}"
        assert item["price"] > 0, f"Price should be positive for {item.get('ticker')}"
