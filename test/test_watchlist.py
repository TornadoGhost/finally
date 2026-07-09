"""Watchlist CRUD E2E tests."""

from uuid import uuid4


def test_get_watchlist(api):
    """GET /api/watchlist returns a list."""
    r = api.get("/api/watchlist")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_add_ticker(api):
    """POST /api/watchlist adds a ticker and it appears in the list."""
    new_ticker = f"TEST{uuid4().hex[:4].upper()}"
    r = api.post("/api/watchlist", json={"ticker": new_ticker})
    assert r.status_code == 200

    # Verify it appears in the watchlist
    r = api.get("/api/watchlist")
    tickers = {item["ticker"] for item in r.json()}
    assert new_ticker in tickers

    # Clean up
    api.delete(f"/api/watchlist/{new_ticker}")


def test_remove_ticker(api):
    """DELETE /api/watchlist/{ticker} removes it from the list."""
    new_ticker = f"RMT{uuid4().hex[:4].upper()}"
    api.post("/api/watchlist", json={"ticker": new_ticker})

    # Confirm it exists
    r = api.get("/api/watchlist")
    tickers_before = {item["ticker"] for item in r.json()}
    assert new_ticker in tickers_before

    # Remove it
    r = api.delete(f"/api/watchlist/{new_ticker}")
    assert r.status_code == 200

    # Confirm it's gone
    r = api.get("/api/watchlist")
    tickers_after = {item["ticker"] for item in r.json()}
    assert new_ticker not in tickers_after


def test_add_duplicate_ticker_idempotent(api):
    """Adding an already-watched ticker should not raise an error."""
    existing_ticker = "AAPL"
    r = api.post("/api/watchlist", json={"ticker": existing_ticker})
    # Should succeed (idempotent) or return 200/409 without crashing
    assert r.status_code in (200, 409)


def test_remove_nonexistent_ticker(api):
    """Removing a ticker that is not in the watchlist should not crash."""
    r = api.delete("/api/watchlist/NOTATICKERXYZ")
    # 404 is acceptable; 200 with idempotent semantics is also fine
    assert r.status_code in (200, 204, 404)
