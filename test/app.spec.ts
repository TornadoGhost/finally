/**
 * FinAlly E2E Tests
 *
 * Prerequisites:
 *   - The FinAlly app must be running (via docker-compose.test.yml or locally on port 8000)
 *   - LLM_MOCK=true so chat tests are deterministic
 *
 * Run locally (outside Docker):
 *   npm install
 *   npx playwright install chromium
 *   BASE_URL=http://localhost:8000 npx playwright test
 *
 * Run via Docker Compose:
 *   cd test && docker compose -f docker-compose.test.yml up --abort-on-container-exit
 */

import { test, expect, request } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:8000";
const API = `${BASE_URL}/api`;

// ── Helper ────────────────────────────────────────────────────────────────
async function apiFetch(path: string, options?: RequestInit) {
  const ctx = await request.newContext({ baseURL: BASE_URL });
  const res = await ctx.fetch(path, options);
  return { status: res.status(), body: await res.json().catch(() => ({})) };
}

// ── Fresh Start ───────────────────────────────────────────────────────────

test("health check returns 200", async () => {
  const { status, body } = await apiFetch("/api/health");
  expect(status).toBe(200);
  expect(body).toHaveProperty("status", "ok");
});

test("fresh portfolio starts with $10,000 cash and empty positions", async () => {
  const { status, body } = await apiFetch("/api/portfolio");
  expect(status).toBe(200);
  expect(body.cash_balance).toBe(10000);
  expect(body.positions).toEqual([]);
  expect(body.total_value).toBe(10000);
  expect(body.unrealized_pnl).toBe(0);
});

test("watchlist has 10 default tickers", async () => {
  const { status, body } = await apiFetch("/api/watchlist");
  expect(status).toBe(200);
  expect(body).toHaveProperty("tickers");
  expect(body.tickers).toHaveLength(10);
  const symbols = body.tickers.map((t: { ticker: string }) => t.ticker);
  expect(symbols).toContain("AAPL");
  expect(symbols).toContain("GOOGL");
  expect(symbols).toContain("MSFT");
  expect(symbols).toContain("TSLA");
  expect(symbols).toContain("NVDA");
  expect(symbols).toContain("META");
  expect(symbols).toContain("AMZN");
  expect(symbols).toContain("JPM");
  expect(symbols).toContain("V");
  expect(symbols).toContain("NFLX");
});

test("SSE stream endpoint responds and yields valid price events", async ({ page }) => {
  const events: string[] = [];

  const response = await page.evaluate(() => {
    return new Promise<string[]>((resolve) => {
      const es = new EventSource("/api/stream/prices");
      const buf: string[] = [];
      let count = 0;

      es.onmessage = (e) => {
        buf.push(e.data);
        count++;
        // Collect 3 events then close
        if (count >= 3) {
          es.close();
          resolve(buf);
        }
      };

      es.onerror = () => {
        es.close();
        resolve(buf);
      };

      // Safety timeout
      setTimeout(() => {
        es.close();
        resolve(buf);
      }, 5000);
    });
  });

  expect(response.length).toBeGreaterThanOrEqual(1);

  // Each event should be parseable JSON with a ticker and price
  for (const raw of response) {
    const event = JSON.parse(raw);
    expect(event).toHaveProperty("ticker");
    expect(event).toHaveProperty("price");
    expect(event).toHaveProperty("timestamp");
    expect(typeof event.price).toBe("number");
    expect(event.price).toBeGreaterThan(0);
  }
});

// ── Buy Shares ────────────────────────────────────────────────────────────

test("buy shares: cash decreases and position appears", async () => {
  // Get initial portfolio state
  const { body: initial } = await apiFetch("/api/portfolio");
  const initialCash = initial.cash_balance;

  // Buy 10 shares of AAPL
  const res = await apiFetch("/api/portfolio/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "AAPL", quantity: 10, side: "buy" }),
  });

  expect(res.status).toBe(200);
  expect(res.body).toHaveProperty("success", true);
  expect(res.body).toHaveProperty("trade");

  // Verify portfolio updated
  const { body: updated } = await apiFetch("/api/portfolio");
  expect(updated.cash_balance).toBeLessThan(initialCash);
  expect(updated.cash_balance).toBeGreaterThan(initialCash - 10000); // sanity check

  const aaplPos = updated.positions.find((p: { ticker: string }) => p.ticker === "AAPL");
  expect(aaplPos).toBeDefined();
  expect(aaplPos.quantity).toBe(10);
  expect(updated.total_value).toBeCloseTo(10000, -2); // ≈ 10k total (cash + position value)
});

test("buy with insufficient cash returns error", async () => {
  const res = await apiFetch("/api/portfolio/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "AAPL", quantity: 100000, side: "buy" }),
  });

  expect(res.status).toBe(200);
  expect(res.body).toHaveProperty("success", false);
  expect(res.body.error).toMatch(/insufficient|cash|not enough/i);
});

// ── Sell Shares ───────────────────────────────────────────────────────────

test("sell shares: cash increases and position reduces or disappears", async () => {
  // First buy some shares
  await apiFetch("/api/portfolio/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "TSLA", quantity: 5, side: "buy" }),
  });

  // Get position before selling
  const { body: before } = await apiFetch("/api/portfolio");
  const teslaBefore = before.positions.find((p: { ticker: string }) => p.ticker === "TSLA");
  const cashBefore = before.cash_balance;

  // Sell 2 shares
  const res = await apiFetch("/api/portfolio/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "TSLA", quantity: 2, side: "sell" }),
  });

  expect(res.status).toBe(200);
  expect(res.body).toHaveProperty("success", true);

  const { body: after } = await apiFetch("/api/portfolio");
  expect(after.cash_balance).toBeGreaterThan(cashBefore);

  const teslaAfter = after.positions.find((p: { ticker: string }) => p.ticker === "TSLA");
  expect(teslaAfter.quantity).toBe(3);
});

test("sell more than owned returns error", async () => {
  // Try to sell shares we don't own
  const res = await apiFetch("/api/portfolio/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "NVDA", quantity: 1, side: "sell" }),
  });

  expect(res.status).toBe(200);
  expect(res.body).toHaveProperty("success", false);
  expect(res.body.error).toMatch(/not enough|no position|insufficient/i);
});

// ── Watchlist ─────────────────────────────────────────────────────────────

test("add a ticker to the watchlist", async () => {
  const res = await apiFetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "AMD" }),
  });

  expect(res.status).toBe(200);
  expect(res.body).toHaveProperty("success", true);

  // Verify it's in the list
  const { body: list } = await apiFetch("/api/watchlist");
  const symbols = list.tickers.map((t: { ticker: string }) => t.ticker);
  expect(symbols).toContain("AMD");
});

test("remove a ticker from the watchlist", async () => {
  // Add then remove
  await apiFetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "COIN" }),
  });

  const res = await apiFetch("/api/watchlist/COIN", { method: "DELETE" });
  expect(res.status).toBe(200);
  expect(res.body).toHaveProperty("success", true);

  // Verify it's gone
  const { body: list } = await apiFetch("/api/watchlist");
  const symbols = list.tickers.map((t: { ticker: string }) => t.ticker);
  expect(symbols).not.toContain("COIN");
});

test("adding duplicate ticker returns appropriate response", async () => {
  const res = await apiFetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: "AAPL" }),
  });

  // Should either succeed (idempotent) or return a graceful error
  expect([200, 400, 409]).toContain(res.status);
});

test("cannot remove a ticker not in the watchlist", async () => {
  const res = await apiFetch("/api/watchlist/NONEXIST", { method: "DELETE" });
  expect(res.status).toBeGreaterOrEqual(400);
});

// ── Chat ──────────────────────────────────────────────────────────────────

test("chat with LLM_MOCK=true returns structured response", async () => {
  const res = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "Hello, what's my portfolio worth?" }),
  });

  expect(res.status).toBe(200);
  expect(res.body).toHaveProperty("message");
  expect(typeof res.body.message).toBe("string");
  // Structured fields may or may not be present depending on mock
  expect(["trades", "watchlist_changes"]).toContain(
    Object.keys(res.body).find((k) => ["trades", "watchlist_changes"].includes(k))
  );
});

test("chat validates message is a non-empty string", async () => {
  const res = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "" }),
  });

  // Should reject empty message
  expect(res.status).toBeGreaterOrEqual(400);
});

// ── Portfolio History ──────────────────────────────────────────────────────

test("portfolio history returns snapshots array", async () => {
  const { status, body } = await apiFetch("/api/portfolio/history");
  expect(status).toBe(200);
  expect(body).toHaveProperty("snapshots");
  expect(Array.isArray(body.snapshots)).toBe(true);
});
