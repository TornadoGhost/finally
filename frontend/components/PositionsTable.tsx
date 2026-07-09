"use client";

import { Position, PriceUpdate } from "@/lib/types";

interface PositionsTableProps {
  positions: Position[];
  prices: Map<string, PriceUpdate>;
}

export default function PositionsTable({ positions, prices }: PositionsTableProps) {
  if (!positions.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg"
        style={{ height: 80, backgroundColor: "#0d1117" }}
      >
        <span className="text-sm" style={{ color: "#8b949e" }}>
          No open positions.
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-lg flex flex-col" style={{ backgroundColor: "#0d1117", height: 220, overflow: "hidden" }}>
      <div className="px-4 py-2 border-b shrink-0" style={{ borderColor: "#30363d" }}>
        <span className="text-xs uppercase tracking-widest font-bold" style={{ color: "#8b949e" }}>
          Positions
        </span>
      </div>
      <div className="overflow-x-auto flex-1 min-h-0" style={{ maxHeight: "unset" }}>
        <table className="w-full text-xs">
          <thead>
            <tr style={{ borderBottom: "1px solid #30363d", color: "#8b949e" }}>
              <th className="text-left px-4 py-2 font-semibold">Ticker</th>
              <th className="text-right px-4 py-2 font-semibold">Qty</th>
              <th className="text-right px-4 py-2 font-semibold">Avg Cost</th>
              <th className="text-right px-4 py-2 font-semibold">Current</th>
              <th className="text-right px-4 py-2 font-semibold">Unrealized P&L</th>
              <th className="text-right px-4 py-2 font-semibold">% Chg</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos) => {
              const livePrice = prices.get(pos.ticker)?.price ?? pos.current_price;
              const livePnl = (livePrice - pos.avg_cost) * pos.quantity;
              const livePnlPct = pos.avg_cost > 0 ? ((livePrice - pos.avg_cost) / pos.avg_cost) * 100 : 0;
              const pnlColor = livePnl >= 0 ? "#22c55e" : "#ef4444";

              return (
                <tr
                  key={pos.ticker}
                  className="transition-colors"
                  style={{ borderBottom: "1px solid #1c2128" }}
                >
                  <td className="px-4 py-2 font-bold" style={{ color: "#e6edf3" }}>
                    {pos.ticker}
                  </td>
                  <td className="px-4 py-2 text-right" style={{ color: "#e6edf3" }}>
                    {pos.quantity}
                  </td>
                  <td className="px-4 py-2 text-right" style={{ color: "#8b949e" }}>
                    ${pos.avg_cost.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right font-bold" style={{ color: "#e6edf3" }}>
                    ${livePrice.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right font-bold" style={{ color: pnlColor }}>
                    {livePnl >= 0 ? "+" : ""}${livePnl.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right font-bold" style={{ color: pnlColor }}>
                    {livePnlPct >= 0 ? "+" : ""}
                    {livePnlPct.toFixed(2)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
