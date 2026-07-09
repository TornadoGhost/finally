"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePrices } from "@/lib/priceContext";
import { fetchWatchlist, addToWatchlist, removeFromWatchlist } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return <div className="w-16 h-6" />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 64;
  const h = 24;
  const step = w / (data.length - 1);
  const points = data
    .map((v, i) => `${i * step},${h - ((v - min) / range) * h}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="flex-shrink-0">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

interface FlashState {
  [ticker: string]: "up" | "down" | null;
}
const PREV_KEY = (t: string) => `prev_${t}`;

function WatchlistCard({
  item,
  isSelected,
  onSelect,
  onRemove,
}: {
  item: WatchlistItem;
  isSelected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const { prices, priceHistory } = usePrices();
  const price = prices[item.ticker]?.price ?? item.price;
  const direction = prices[item.ticker]?.direction ?? item.direction;
  const changePercent = prices[item.ticker]?.change_percent ?? item.change_percent;
  const history = priceHistory.current.get(item.ticker) ?? [];

  // Flash state
  const [flashClass, setFlashClass] = useState<string>("");
  const prevPrice = useRef<number | null>(null);

  useEffect(() => {
    if (price == null) return;
    const prev = prevPrice.current;
    if (prev !== null && prev !== price) {
      const cls = price > prev ? "flash-green" : "flash-red";
      setFlashClass(cls);
      const t = setTimeout(() => setFlashClass(""), 550);
      prevPrice.current = price;
      return () => clearTimeout(t);
    }
    prevPrice.current = price;
  }, [price]);

  const isUp = direction === "up";
  const isDown = direction === "down";
  const changeColor = isUp ? "text-profit" : isDown ? "text-loss" : "text-muted";
  const sparkColor = isUp ? "#3fb950" : isDown ? "#f85149" : "#8b949e";

  return (
    <div
      className={`flex items-center justify-between px-3 py-2 rounded-md cursor-pointer border ticker-card ${flashClass} ${isSelected ? "selected" : ""}`}
      style={{
        borderColor: isSelected ? "#ecad0a" : "#21262d",
        backgroundColor: isSelected ? "#1a2332" : "transparent",
      }}
      onClick={onSelect}
    >
      <div className="flex flex-col min-w-0">
        <span className="font-bold text-sm text-text-primary">{item.ticker}</span>
        <span className="text-lg font-bold" style={{ fontFamily: "JetBrains Mono, monospace", color: "#c9d1d9" }}>
          {price != null ? `$${price.toFixed(2)}` : "—"}
        </span>
        <span className={`text-xs font-medium ${changeColor}`}>
          {changePercent != null ? `${changePercent >= 0 ? "+" : ""}${changePercent.toFixed(2)}%` : "—"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Sparkline data={history} color={sparkColor} />
        <button
          className="opacity-0 group-hover:opacity-100 text-loss hover:text-loss text-xs px-1 rounded"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          title="Remove ticker"
        >
          ×
        </button>
      </div>
    </div>
  );
}

function AddTickerForm({ onAdded }: { onAdded: () => void }) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    setLoading(true);
    setError("");
    try {
      await addToWatchlist(value.trim().toUpperCase());
      setValue("");
      onAdded();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-2">
      <div className="flex gap-1">
        <input
          className="input-field flex-1"
          value={value}
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          placeholder="ADD TICKER"
          maxLength={10}
        />
        <button type="submit" disabled={loading || !value.trim()} className="btn-accent text-xs px-2">
          {loading ? "…" : "+"}
        </button>
      </div>
      {error && <p className="text-xs text-loss mt-1">{error}</p>}
    </form>
  );
}

export default function Watchlist() {
  const { selectedTicker, setSelectedTicker } = usePrices();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    fetchWatchlist()
      .then(setWatchlist)
      .catch(() => {});
  }, [refreshKey]);

  const handleRemove = async (ticker: string) => {
    try {
      await removeFromWatchlist(ticker);
      setWatchlist((prev) => prev.filter((w) => w.ticker !== ticker));
    } catch {
      // silently fail
    }
  };

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2 px-1">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Watchlist</h2>
        <span className="text-xs text-muted">{watchlist.length}</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {watchlist.map((item) => (
          <div key={item.ticker} className="group">
            <WatchlistCard
              item={item}
              isSelected={item.ticker === selectedTicker}
              onSelect={() => setSelectedTicker(item.ticker)}
              onRemove={() => handleRemove(item.ticker)}
            />
          </div>
        ))}
      </div>

      <AddTickerForm onAdded={refresh} />
    </div>
  );
}
