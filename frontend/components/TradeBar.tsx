"use client";

import { useState } from "react";
import { executeTrade } from "@/lib/api";

interface TradeBarProps {
  selectedTicker: string | null;
  cashBalance: number;
  onTradeExecuted: () => void;
}

export default function TradeBar({ selectedTicker, cashBalance, onTradeExecuted }: TradeBarProps) {
  const [ticker, setTicker] = useState(selectedTicker || "");
  const [quantity, setQuantity] = useState("");
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const handle = async (side: "buy" | "sell") => {
    const t = ticker.trim().toUpperCase();
    const q = parseFloat(quantity);
    if (!t || isNaN(q) || q <= 0) {
      setFeedback({ type: "error", msg: "Enter a valid ticker and quantity." });
      return;
    }
    setLoading(true);
    setFeedback(null);
    try {
      await executeTrade({ ticker: t, quantity: q, side });
      setFeedback({ type: "success", msg: `${side === "buy" ? "Bought" : "Sold"} ${q} ${t}.` });
      setQuantity("");
      onTradeExecuted();
    } catch (err) {
      setFeedback({ type: "error", msg: String(err) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-lg"
      style={{ backgroundColor: "#161b22", border: "1px solid #30363d" }}
    >
      <span className="text-xs uppercase tracking-widest font-bold" style={{ color: "#8b949e" }}>
        Trade
      </span>

      <input
        type="text"
        placeholder="TICKER"
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        className="w-24 px-2 py-1.5 text-xs font-bold rounded"
        style={{
          backgroundColor: "#0d1117",
          border: "1px solid #30363d",
          color: "#e6edf3",
          outline: "none",
        }}
      />

      <input
        type="number"
        placeholder="Qty"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        min="0"
        step="any"
        className="w-20 px-2 py-1.5 text-xs rounded"
        style={{
          backgroundColor: "#0d1117",
          border: "1px solid #30363d",
          color: "#e6edf3",
          outline: "none",
        }}
      />

      <button
        onClick={() => handle("buy")}
        disabled={loading}
        className="px-4 py-1.5 text-xs font-bold rounded transition-opacity"
        style={{ backgroundColor: "#753991", color: "#fff", opacity: loading ? 0.5 : 1 }}
      >
        Buy
      </button>

      <button
        onClick={() => handle("sell")}
        disabled={loading}
        className="px-4 py-1.5 text-xs font-bold rounded transition-opacity"
        style={{ backgroundColor: "#209dd7", color: "#fff", opacity: loading ? 0.5 : 1 }}
      >
        Sell
      </button>

      <div className="text-xs" style={{ color: "#8b949e" }}>
        Cash:{" "}
        <span className="font-bold" style={{ color: "#e6edf3" }}>
          ${cashBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </div>

      {feedback && (
        <span
          className="text-xs font-bold ml-auto"
          style={{ color: feedback.type === "success" ? "#22c55e" : "#ef4444" }}
        >
          {feedback.msg}
        </span>
      )}
    </div>
  );
}
