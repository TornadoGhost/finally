"use client";

import { useCallback, useEffect, useState } from "react";
import { usePrices } from "@/lib/priceContext";
import { fetchPortfolio } from "@/lib/api";

interface HeatmapEntry {
  ticker: string;
  marketValue: number;
  pnlPct: number;
  weight: number;
}

interface HeatmapRect {
  ticker: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fill: string;
  marketValue: number;
  pnlPct: number;
  weight: number;
  label: string;
}

function pnlColor(pnlPct: number): string {
  if (pnlPct > 10) return "#27c45a";
  if (pnlPct > 5) return "#3fb950";
  if (pnlPct > 0) return "#2ea043";
  if (pnlPct > -5) return "#b5544d";
  if (pnlPct > -10) return "#d4543e";
  return "#f85149";
}

function computeLayout(entries: HeatmapEntry[], containerW: number, containerH: number): HeatmapRect[] {
  if (!entries.length) return [];

  // Sort by market value descending for better layout
  const sorted = [...entries].sort((a, b) => b.marketValue - a.marketValue);
  const total = sorted.reduce((s, e) => s + e.marketValue, 0) || 1;

  const rects: HeatmapRect[] = [];
  let usedW = 0;
  let usedH = 0;
  let col = 0;
  const cols = Math.max(2, Math.floor(Math.sqrt(sorted.length * (containerW / containerH))));
  const colW = containerW / cols;

  sorted.forEach((entry, i) => {
    const relW = entry.marketValue / total;
    const w = Math.max(60, colW * relW * 2);
    const h = Math.max(40, containerH * 0.4);

    const x = (i % cols) * colW;
    const y = Math.floor(i / cols) * (containerH / Math.ceil(sorted.length / cols));

    rects.push({
      ticker: entry.ticker,
      x,
      y,
      width: colW - 2,
      height: containerH / Math.ceil(sorted.length / cols) - 2,
      fill: pnlColor(entry.pnlPct),
      marketValue: entry.marketValue,
      pnlPct: entry.pnlPct,
      weight: entry.weight,
      label: `${entry.ticker}\n${entry.marketValue > 0 ? ((entry.marketValue / total) * 100).toFixed(1) : 0}%`,
    });
  });

  return rects;
}

interface HeatmapProps {
  onSelectTicker: (ticker: string) => void;
}

export default function PortfolioHeatmap({ onSelectTicker }: HeatmapProps) {
  const { prices } = usePrices();
  const [entries, setEntries] = useState<HeatmapEntry[]>([]);
  const [containerSize, setContainerSize] = useState({ w: 300, h: 160 });
  const containerRef = useCallback((node: HTMLDivElement | null) => {
    if (!node) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        setContainerSize({ w: e.contentRect.width, h: e.contentRect.height });
      }
    });
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    fetchPortfolio()
      .then((p) => {
        const positions = p.positions.map((pos) => {
          const price = prices[pos.ticker]?.price ?? 0;
          const marketValue = price * pos.quantity;
          const costBasis = pos.avg_cost * pos.quantity;
          const pnlPct = costBasis > 0 ? ((marketValue - costBasis) / costBasis) * 100 : 0;
          return { ticker: pos.ticker, marketValue, pnlPct, weight: 0 };
        });
        const totalValue = positions.reduce((s, e) => s + e.marketValue, 0);
        const withWeight = positions.map((e) => ({
          ...e,
          weight: totalValue > 0 ? e.marketValue / totalValue : 0,
        }));
        setEntries(withWeight);
      })
      .catch(() => {});
  }, [prices]);

  const rects = computeLayout(entries, containerSize.w, containerSize.h);

  return (
    <div className="flex flex-col h-full">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Portfolio Heatmap</h2>
      {entries.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted text-sm">No positions</div>
      ) : (
        <div ref={containerRef} className="flex-1 relative" style={{ minHeight: 120 }}>
          <svg width="100%" height="100%" style={{ display: "block" }}>
            {rects.map((rect) => (
              <g key={rect.ticker} onClick={() => onSelectTicker(rect.ticker)} style={{ cursor: "pointer" }}>
                <rect
                  x={rect.x}
                  y={rect.y}
                  width={rect.width}
                  height={rect.height}
                  fill={rect.fill}
                  fillOpacity={0.85}
                  rx={4}
                  style={{ transition: "fill-opacity 0.15s" }}
                />
                <rect
                  x={rect.x}
                  y={rect.y}
                  width={rect.width}
                  height={rect.height}
                  fill="transparent"
                  stroke="rgba(255,255,255,0.08)"
                  strokeWidth={1}
                  rx={4}
                />
                {/* Label */}
                <text
                  x={rect.x + rect.width / 2}
                  y={rect.y + rect.height / 2 - 6}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="white"
                  fontSize={Math.max(10, Math.min(14, rect.width / 5))}
                  fontWeight="700"
                  fontFamily="JetBrains Mono, monospace"
                >
                  {rect.ticker}
                </text>
                <text
                  x={rect.x + rect.width / 2}
                  y={rect.y + rect.height / 2 + 10}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="rgba(255,255,255,0.75)"
                  fontSize={10}
                  fontFamily="JetBrains Mono, monospace"
                >
                  {rect.pnlPct >= 0 ? "+" : ""}{rect.pnlPct.toFixed(1)}%
                </text>
              </g>
            ))}
          </svg>
        </div>
      )}
    </div>
  );
}
