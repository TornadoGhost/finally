"use client";

import { useEffect, useRef, useState } from "react";
import { PriceUpdate } from "@/lib/types";

interface WatchlistProps {
  prices: Map<string, PriceUpdate>;
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
  onAddTicker: (ticker: string) => void;
}

function Sparkline({ points }: { points: { price: number }[] }) {
  if (points.length < 2) return <div className="w-16 h-6" />;

  const prices = points.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const w = 64;
  const h = 24;
  const step = w / (points.length - 1);

  const pts = points.map((p, i) => {
    const x = i * step;
    const y = h - ((p.price - min) / range) * h;
    return `${x},${y}`;
  });

  const color = points[points.length - 1].price >= points[0].price ? "#22c55e" : "#ef4444";

  return (
    <svg width={w} height={h} className="inline-block">
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TickerCard({
  ticker,
  price,
  change,
  changePercent,
  direction,
  sparklinePoints,
  selected,
  onClick,
}: {
  ticker: string;
  price: number;
  change: number;
  changePercent: number;
  direction: "up" | "down" | "flat";
  sparklinePoints: { price: number }[];
  selected: boolean;
  onClick: () => void;
}) {
  const [flashClass, setFlashClass] = useState("");
  const prevPriceRef = useRef(price);

  useEffect(() => {
    if (price !== prevPriceRef.current) {
      setFlashClass(direction === "up" ? "price-up" : direction === "down" ? "price-down" : "");
      prevPriceRef.current = price;
      const t = setTimeout(() => setFlashClass(""), 600);
      return () => clearTimeout(t);
    }
  }, [price, direction]);

  const color =
    direction === "up"
      ? "#22c55e"
      : direction === "down"
      ? "#ef4444"
      : "#8b949e";

  return (
    <div
      onClick={onClick}
      className={`p-3 rounded-lg cursor-pointer transition-colors ${flashClass}`}
      style={{
        backgroundColor: selected ? "#1c2128" : "#161b22",
        border: `1px solid ${selected ? "#ecad0a" : "#30363d"}`,
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="font-bold text-sm" style={{ color: "#e6edf3" }}>
          {ticker}
        </span>
        <span className="text-sm font-bold" style={{ color }}>
          ${price.toFixed(2)}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <span className="text-xs" style={{ color }}>
            {change >= 0 ? "+" : ""}
            {change.toFixed(2)}
          </span>
          <span className="text-xs" style={{ color }}>
            ({changePercent >= 0 ? "+" : ""}
            {changePercent.toFixed(2)}%)
          </span>
        </div>
        <Sparkline points={sparklinePoints} />
      </div>
    </div>
  );
}

export default function Watchlist({
  prices,
  selectedTicker,
  onSelectTicker,
  onAddTicker,
}: WatchlistProps) {
  const [history, setHistory] = useState<Map<string, { price: number }[]>>(new Map());
  const [newTicker, setNewTicker] = useState("");

  useEffect(() => {
    setHistory((prev) => {
      const next = new Map(prev);
      prices.forEach((update, ticker) => {
        const existing = next.get(ticker) || [];
        const last = existing[existing.length - 1];
        if (!last || last.price !== update.price) {
          const updated = [...existing, { price: update.price }];
          if (updated.length > 200) updated.shift();
          next.set(ticker, updated);
        }
      });
      return next;
    });
  }, [prices]);

  const tickers = Array.from(prices.keys()).sort();

  const handleAdd = () => {
    const t = newTicker.trim().toUpperCase();
    if (t) {
      onAddTicker(t);
      setNewTicker("");
    }
  };

  return (
    <div
      className="flex flex-col p-3 rounded-lg overflow-hidden"
      style={{ backgroundColor: "#0d1117", height: "100%" }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs uppercase tracking-widest font-bold" style={{ color: "#8b949e" }}>
          Watchlist
        </span>
        <div className="flex gap-1">
          <input
            type="text"
            placeholder="TICKER"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            className="w-16 px-1 py-0.5 text-xs rounded"
            style={{
              backgroundColor: "#161b22",
              border: "1px solid #30363d",
              color: "#e6edf3",
              outline: "none",
            }}
          />
          <button
            onClick={handleAdd}
            className="px-2 py-0.5 text-xs rounded font-bold"
            style={{ backgroundColor: "#209dd7", color: "#fff" }}
          >
            +
          </button>
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto grid gap-2"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", alignContent: "start" }}
      >
        {tickers.map((ticker) => {
          const update = prices.get(ticker)!;
          return (
            <TickerCard
              key={ticker}
              ticker={ticker}
              price={update.price}
              change={update.change}
              changePercent={update.change_percent}
              direction={update.direction}
              sparklinePoints={history.get(ticker) || []}
              selected={selectedTicker === ticker}
              onClick={() => onSelectTicker(ticker)}
            />
          );
        })}
      </div>
    </div>
  );
}
