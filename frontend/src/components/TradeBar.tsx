"use client";

import { useState, useEffect, useCallback } from "react";
import { usePrices } from "@/lib/priceContext";
import { executeTrade } from "@/lib/api";

interface TradeBarProps {
  onTradeExecuted?: () => void;
}

export default function TradeBar({ onTradeExecuted }: TradeBarProps) {
  const { prices, selectedTicker, setSelectedTicker } = usePrices();
  const [ticker, setTicker] = useState(selectedTicker);
  const [quantity, setQuantity] = useState("");
  const [loading, setLoading] = useState<"buy" | "sell" | null>(null);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  // Sync ticker with selected watchlist ticker
  useEffect(() => {
    setTicker(selectedTicker);
  }, [selectedTicker]);

  const clearMsg = useCallback(() => setMessage(null), []);

  const handleTrade = async (side: "buy" | "sell") => {
    const qty = parseFloat(quantity);
    if (!ticker.trim()) { setMessage({ text: "Enter a ticker", ok: false }); return; }
    if (!qty || qty <= 0) { setMessage({ text: "Enter a valid quantity", ok: false }); return; }
    const price = prices[ticker]?.price;
    if (!price) { setMessage({ text: "Price not available", ok: false }); return; }

    setLoading(side);
    setMessage(null);
    try {
      const result = await executeTrade(ticker.toUpperCase(), qty, side);
      setMessage({ text: result.message, ok: true });
      setQuantity("");
      onTradeExecuted?.();
    } catch (err: unknown) {
      const text = err instanceof Error ? err.message : "Trade failed";
      setMessage({ text, ok: false });
    } finally {
      setLoading(null);
    }

    // Auto-clear message after 4s
    setTimeout(clearMsg, 4000);
  };

  const currentPrice = prices[ticker]?.price;

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Trade</h2>

      {/* Ticker input */}
      <div>
        <label className="text-xs text-muted mb-1 block">Ticker</label>
        <input
          className="input-field font-mono font-bold"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="AAPL"
          maxLength={10}
        />
      </div>

      {/* Quantity input */}
      <div>
        <label className="text-xs text-muted mb-1 block">Quantity (shares)</label>
        <input
          className="input-field font-mono"
          type="number"
          min="0.001"
          step="any"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="0"
        />
      </div>

      {/* Estimated cost */}
      {currentPrice != null && quantity && parseFloat(quantity) > 0 && (
        <div className="text-xs text-muted">
          Est. total: <span className="text-text-primary font-medium">${(currentPrice * parseFloat(quantity)).toFixed(2)}</span>
        </div>
      )}

      {/* Buy / Sell buttons */}
      <div className="flex gap-2">
        <button
          className="btn-buy flex-1"
          onClick={() => handleTrade("buy")}
          disabled={loading !== null}
        >
          {loading === "buy" ? <span className="spinner" /> : "BUY"}
        </button>
        <button
          className="btn-sell flex-1"
          onClick={() => handleTrade("sell")}
          disabled={loading !== null}
        >
          {loading === "sell" ? <span className="spinner" /> : "SELL"}
        </button>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`text-xs px-2 py-1.5 rounded border ${message.ok ? "border-profit/40 text-profit bg-profit/10" : "border-loss/40 text-loss bg-loss/10"}`}
        >
          {message.text}
        </div>
      )}
    </div>
  );
}
