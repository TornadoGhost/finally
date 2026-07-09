"use client";

import { useEffect, useState } from "react";
import { usePrices } from "@/lib/priceContext";
import { fetchPortfolio } from "@/lib/api";
import type { Position } from "@/lib/types";

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}
function fmtPct(n: number) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

interface PositionRow {
  ticker: string;
  quantity: number;
  avg_cost: number;
  price: number;
  marketValue: number;
  pnl: number;
  pnlPct: number;
}

interface PositionsTableProps {
  onSelectTicker: (ticker: string) => void;
}

export default function PositionsTable({ onSelectTicker }: PositionsTableProps) {
  const { prices } = usePrices();
  const [rows, setRows] = useState<PositionRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPortfolio()
      .then((p) => {
        setRows(
          p.positions.map((pos: Position) => {
            const price = prices[pos.ticker]?.price ?? pos.avg_cost;
            const marketValue = price * pos.quantity;
            const costBasis = pos.avg_cost * pos.quantity;
            const pnl = marketValue - costBasis;
            const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
            return { ...pos, price, marketValue, pnl, pnlPct };
          })
        );
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [prices]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-2 flex-shrink-0">Positions</h2>
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-muted text-sm">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted text-sm">No open positions</div>
      ) : (
        <div className="overflow-y-auto flex-1">
          <table className="data-table">
            <thead className="sticky top-0" style={{ backgroundColor: "#161b22" }}>
              <tr>
                <th>Ticker</th>
                <th>Qty</th>
                <th>Avg Cost</th>
                <th>Price</th>
                <th>Mkt Value</th>
                <th>P&amp;L ($)</th>
                <th>P&amp;L (%)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.ticker} onClick={() => onSelectTicker(row.ticker)}>
                  <td>
                    <span className="font-bold text-accent">{row.ticker}</span>
                  </td>
                  <td style={{ fontFamily: "JetBrains Mono, monospace" }}>
                    {row.quantity.toFixed(4).replace(/\.?0+$/, "")}
                  </td>
                  <td style={{ fontFamily: "JetBrains Mono, monospace" }}>{fmt(row.avg_cost)}</td>
                  <td style={{ fontFamily: "JetBrains Mono, monospace" }}>{fmt(row.price)}</td>
                  <td style={{ fontFamily: "JetBrains Mono, monospace" }}>{fmt(row.marketValue)}</td>
                  <td style={{ fontFamily: "JetBrains Mono, monospace" }} className={row.pnl >= 0 ? "text-profit" : "text-loss"}>
                    {row.pnl >= 0 ? "+" : ""}{fmt(row.pnl)}
                  </td>
                  <td style={{ fontFamily: "JetBrains Mono, monospace" }} className={row.pnlPct >= 0 ? "text-profit" : "text-loss"}>
                    {fmtPct(row.pnlPct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
