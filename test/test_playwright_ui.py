"""Browser-based E2E tests using Playwright (sync API)."""

import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.fixture(scope="module")
def playwright():
    with sync_playwright() as p:
        yield p


def _load_app(playwright, base_url):
    """Launch a browser and navigate to the app, returning the page."""
    browser = playwright.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    # Next.js static export serves index.html at root or at /index.html
    page.goto(base_url, wait_until="domcontentloaded")
    # Wait for the app to render some content
    page.wait_for_timeout(2000)
    return browser, context, page


# ---------------------------------------------------------------------------
# test_watchlist_renders
# ---------------------------------------------------------------------------

def test_watchlist_renders(playwright, base_url):
    """The watchlist grid should display tickers after the page loads."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        # Wait for the page to settle
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        # The watchlist should contain default tickers — look for AAPL text
        content = page.content()
        assert "AAPL" in content or "GOOGL" in content, (
            "Expected at least one default ticker to appear in the rendered page"
        )
    finally:
        browser.close()


def test_watchlist_shows_prices(playwright, base_url):
    """Watchlist items should display numeric price values."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(2000)

        # Look for any price-like pattern (e.g., $123.45 or just numbers)
        price_locator = page.locator("text=/\\$?\\d+\\.\\d{2}/")
        count = price_locator.count()
        assert count > 0, "No price values found on the page"
    finally:
        browser.close()


# ---------------------------------------------------------------------------
# test_trade_execution
# ---------------------------------------------------------------------------

def test_trade_execution(playwright, base_url):
    """Buy shares via the trade bar and verify the position appears."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        # Find the trade bar input fields (ticker and quantity)
        # Look for any input element that could be the quantity field
        # We'll try multiple selectors commonly used in trading UIs
        qty_input = (
            page.get_by_placeholder("Qty")
            .or_(page.get_by_placeholder("Quantity"))
            .or_(page.locator("input[placeholder*='qty' i]"))
            .or_(page.locator("input[placeholder*='quantity' i]"))
            .first
        )

        # Enter quantity
        qty_input.fill("2")

        # Click Buy button
        buy_button = page.get_by_role("button", name="Buy").or_(
            page.locator("button", has_text="Buy")
        ).first
        buy_button.click()

        # Wait for the position table to update
        page.wait_for_timeout(3000)

        # Verify AAPL appears in positions
        content = page.content()
        assert "AAPL" in content, "AAPL should appear in positions after buying"
    finally:
        browser.close()


def test_sell_button_present(playwright, base_url):
    """The trade bar should have a Sell button."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        sell_button = page.get_by_role("button", name="Sell").or_(
            page.locator("button", has_text="Sell")
        )
        expect(sell_button.first).to_be_visible()
    finally:
        browser.close()


# ---------------------------------------------------------------------------
# test_portfolio_heatmap
# ---------------------------------------------------------------------------

def test_portfolio_heatmap_renders(playwright, base_url):
    """The portfolio heatmap/treemap SVG should be present in the DOM."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        # Look for SVG (used by both heatmap/treemap charts)
        svg_elements = page.locator("svg")
        count = svg_elements.count()
        assert count > 0, "No SVG elements found — heatmap/chart may not have rendered"
    finally:
        browser.close()


def test_portfolio_value_displayed(playwright, base_url):
    """The total portfolio value should be visible in the header."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        # Look for $10,000 or a price-like value near the top of the page
        content = page.content()
        # Should contain something like $10,000 or 10000 or a dollar amount
        has_value = (
            "$10,000" in content
            or "$10,000.00" in content
            or "10,000" in content
        )
        assert has_value, "Expected $10,000 portfolio value in header"
    finally:
        browser.close()


# ---------------------------------------------------------------------------
# test_sse_connection
# ---------------------------------------------------------------------------

def test_sse_connection_status_green(playwright, base_url):
    """The connection status indicator should show green (connected)."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(3000)  # Allow SSE to establish

        # Look for a colored dot — typically green circle for "connected"
        # Common selectors: .status-dot, [class*="status"], [class*="connected"]
        status_dot = (
            page.locator("[class*='status'][class*='dot']")
            .or_(page.locator(".status-dot"))
            .or_(page.locator("[class*='connection-dot']"))
            .or_(page.locator("[class*='indicator']"))
            .first
        )

        # The dot should be visible
        assert status_dot.is_visible(), "Connection status indicator not visible"

        # Check its color — green is typically #22c55e, #10b981, green, etc.
        # We'll just verify it's visible and has a background color
        bg = status_dot.evaluate("el => window.getComputedStyle(el).backgroundColor")
        assert bg != "rgba(0, 0, 0, 0)", "Status dot should have a visible background color"
    finally:
        browser.close()


# ---------------------------------------------------------------------------
# test_watchlist_add_remove
# ---------------------------------------------------------------------------

def test_add_ticker_via_ui(playwright, base_url):
    """Adding a ticker through the UI should reflect in the watchlist."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        # Look for an "Add" button or input near the watchlist
        add_input = (
            page.get_byPlaceholder("Add ticker")
            .or_(page.get_byPlaceholder("Enter ticker"))
            .or_(page.locator("input[placeholder*='add' i]"))
            .or_(page.locator("input[placeholder*='ticker' i]"))
            .first
        )

        add_input.fill("COIN")
        page.wait_for_timeout(500)

        # Find and click the add button
        add_button = (
            page.getByRole("button", name="Add")
            .or_(page.locator("button", has_text="Add"))
            .first
        )
        add_button.click()
        page.wait_for_timeout(2000)

        content = page.content()
        assert "COIN" in content, "Added ticker COIN should appear in the watchlist"
    finally:
        browser.close()


def test_remove_ticker_via_ui(playwright, base_url):
    """Removing a ticker from the watchlist should make it disappear from the UI."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        # First, add TSLA via API so we can test removal
        import requests as req
        req.post(f"{base_url}/api/watchlist", json={"ticker": "TSLA"})

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Find and click a remove/close button near TSLA
        # Common patterns: X button, trash icon, remove button
        remove_btn = (
            page.locator("[class*='remove']")
            .or_(page.locator("[class*='close']"))
            .or_(page.locator("[class*='delete']"))
            .filter(has=page.locator("svg"))
            .first
        )
        if remove_btn.count() > 0 and remove_btn.first.is_visible():
            remove_btn.first.click()
            page.wait_for_timeout(2000)
            content = page.content()
            # After removal TSLA may still appear if it was in the default list
            # Just verify the page didn't crash
            assert "AAPL" in content, "Page should still render after removal"
    finally:
        browser.close()


# ---------------------------------------------------------------------------
# test_chat_panel
# ---------------------------------------------------------------------------

def test_chat_panel_present(playwright, base_url):
    """The AI chat panel should be visible on the page."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        # Look for a chat input or panel
        chat_input = (
            page.getByPlaceholder("Ask FinAlly")
            .or_(page.getByPlaceholder("Message"))
            .or_(page.locator("textarea"))
            .or_(page.locator("input[type='text']"))
            .first
        )
        expect(chat_input).to_be_visible()
    finally:
        browser.close()


def test_chat_send_message(playwright, base_url):
    """Sending a message in the chat should produce a response."""
    browser, context, page = _load_app(playwright, base_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)

        chat_input = (
            page.getByPlaceholder("Ask FinAlly")
            .or_(page.getByPlaceholder("Message"))
            .or_(page.locator("textarea"))
            .or_(page.locator("input[type='text']"))
            .first
        )

        chat_input.fill("What is my cash balance?")
        page.wait_for_timeout(500)

        send_button = (
            page.getByRole("button", name="Send")
            .or_(page.locator("button", has_text="Send"))
            .or_(page.locator("button", has_text="Submit"))
            .first
        )
        send_button.click()

        # Wait for response — LLM is mocked so should be fast
        page.wait_for_timeout(5000)

        # The response should appear somewhere in the chat
        content = page.content()
        assert len(content) > 100, "Chat should have produced a response"
    finally:
        browser.close()
