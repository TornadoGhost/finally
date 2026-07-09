"use client";

import { Position } from "@/lib/types";

interface PortfolioHeatmapProps {
  positions: Position[];
  totalValue: number;
}

interface TreemapRect {
  ticker: string;
  x: number;
  y: number;
  w: number;
  h: number;
  value: number;
  pnl: number;
}

function layoutTreemap(
  items: { ticker: string; value: number; pnl: number }[],
  x: number,
  y: number,
  w: number,
  h: number
): TreemapRect[] {
  if (!items.length) return [];

  const total = items.reduce((s, i) => s + i.value, 0);
  if (total === 0) return [];

  const result: TreemapRect[] = [];

  if (items.length === 1) {
    return [{ ...items[0], x, y, w, h }];
  }

  const sorted = [...items].sort((a, b) => b.value - a.value);

  let remaining: typeof sorted = [];
  let used = 0;

  for (let i = 0; i < sorted.length; i++) {
    const item = sorted[i];
    const ratio = item.value / total;
    const area = w * h * ratio;

    let placed = false;
    if (w >= h) {
      const targetW = area / h;
      if (targetW > 0 && used < w) {
        const px = x + used;
        result.push({ ...item, x: px, y, w: Math.min(targetW, w - used), h });
        used += Math.min(targetW, w - used);
        placed = true;
      }
    } else {
      const targetH = area / w;
      if (targetH > 0) {
        const py = y + (h - used);
        result.push({ ...item, x, y: py, w, h: Math.min(targetH, h - (py - y)) });
        used += Math.min(targetH, h - (py - y));
        placed = true;
      }
    }

    if (!placed) {
      remaining.push(item);
    }
  }

  return result;
}

export default function PortfolioHeatmap({ positions, totalValue }: PortfolioHeatmapProps) {
  if (!positions.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg"
        style={{ height: 180, backgroundColor: "#0d1117" }}
      >
        <span className="text-sm" style={{ color: "#8b949e" }}>
          No positions yet. Buy some shares to see your portfolio heatmap.
        </span>
      </div>
    );
  }

  const items = positions.map((p) => ({
    ticker: p.ticker,
    value: p.quantity * p.current_price,
    pnl: p.unrealized_pnl,
  }));

  const totalPnL = positions.reduce((s, p) => s + p.unrealized_pnl, 0);
  const containerW = 800;
  const containerH = 180;
  const rects = layoutTreemap(items, 0, 0, containerW, containerH);

  const maxAbsPnl = Math.max(...positions.map((p) => Math.abs(p.unrealized_pnl)), 1);

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ backgroundColor: "#0d1117", width: "100%" }}
    >
      <div className="px-4 py-2 border-b" style={{ borderColor: "#30363d" }}>
        <span className="text-xs uppercase tracking-widest font-bold" style={{ color: "#8b949e" }}>
          Portfolio Heatmap
        </span>
        <span className="ml-3 text-xs" style={{ color: totalPnL >= 0 ? "#22c55e" : "#ef4444" }}>
          {totalPnL >= 0 ? "+" : ""}${totalPnL.toFixed(2)} total
        </span>
      </div>
      <div style={{ height: containerH }}>
        <svg width="100%" height={containerH} viewBox={`0 0 ${containerW} ${containerH}`} preserveAspectRatio="none">
          {rects.map((rect) => {
            const intensity = Math.abs(rect.pnl) / maxAbsPnl;
            const color =
              rect.pnl >= 0
                ? `rgba(34, 197, 94, ${0.15 + intensity * 0.6})`
                : `rgba(239, 68, 68, ${0.15 + intensity * 0.6})`;
            const borderColor = rect.pnl >= 0 ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.4)";
            const weight = totalValue > 0 ? ((rect.value / totalValue) * 100).toFixed(1) : "0.0";
            return (
              <g key={rect.ticker}>
                <rect
                  x={rect.x + 1}
                  y={rect.y + 1}
                  width={Math.max(rect.w - 2, 0)}
                  height={Math.max(rect.h - 2, 0)}
                  fill={color}
                  stroke={borderColor}
                  strokeWidth={1}
                  rx={3}
                />
                {rect.w > 50 && rect.h > 30 && (
                  <>
                    <text
                      x={rect.x + rect.w / 2}
                      y={rect.y + rect.h / 2 - 6}
                      textAnchor="middle"
                      fontSize={Math.min(14, rect.w / 6)}
                      fontWeight="bold"
                      fill="#e6edf3"
                    >
                      {rect.ticker}
                    </text>
                    <text
                      x={rect.x + rect.w / 2}
                      y={rect.y + rect.h / 2 + 8}
                      textAnchor="middle"
                      fontSize={Math.min(11, rect.w / 8)}
                      fill="#e6edf3"
                    >
                      {weight}%
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
