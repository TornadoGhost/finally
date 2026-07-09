"use client";

import { useEffect, useState } from "react";
import { usePrices } from "@/lib/priceContext";
import { fetchPortfolio } from "@/lib/api";
import type { ConnectionStatus } from "@/lib/types";

function StatusDot({ status }: { status: ConnectionStatus }) {
  const cls =
    status === "connected"
      ? "status-connected"
      : status === "reconnecting"
      ? "status-reconnecting"
      : "status-disconnected";
  const label =
    status === "connected" ? "Live" : status === "reconnecting" ? "Reconnecting" : "Disconnected";
  return (
    <div className="flex items-center gap-1.5">
      <div className={`status-dot ${cls}`} />
      <span className="text-xs text-muted">{label}</span>
    </div>
  );
}

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export default function Header() {
  const { connectionStatus, prices } = usePrices();
  const [portfolioValue, setPortfolioValue] = useState<number>(0);
  const [cash, setCash] = useState<number>(0);

  useEffect(() => {
    fetchPortfolio()
      .then((p) => {
        setPortfolioValue(p.total_value);
        setCash(p.cash);
      })
      .catch(() => {});
  }, []);

  // Refresh portfolio value when prices change
  useEffect(() => {
    if (Object.keys(prices).length === 0) return;
    fetchPortfolio()
      .then((p) => {
        setPortfolioValue(p.total_value);
        setCash(p.cash);
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prices]);

  return (
    <header
      className="flex items-center justify-between px-4 py-2 border-b"
      style={{ backgroundColor: "#161b22", borderColor: "#21262d" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <rect x="2" y="2" width="20" height="20" rx="4" fill="#ecad0a" />
          <path d="M7 16l3-5 3 3 4-6" stroke="#0d1117" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="font-bold text-lg tracking-tight" style={{ color: "#ecad0a" }}>
          FinAlly
        </span>
        <span className="text-xs text-muted ml-1 hidden sm:inline">AI Trading Workstation</span>
      </div>

      {/* Portfolio Summary */}
      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="text-xs text-muted">Portfolio Value</div>
          <div className="font-bold text-base" style={{ fontFamily: "JetBrains Mono, monospace" }}>
            {portfolioValue > 0 ? fmt(portfolioValue) : "—"}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-muted">Cash</div>
          <div className="font-medium text-sm" style={{ fontFamily: "JetBrains Mono, monospace" }}>
            {cash > 0 ? fmt(cash) : "—"}
          </div>
        </div>
        <StatusDot status={connectionStatus} />
      </div>
    </header>
  );
}
