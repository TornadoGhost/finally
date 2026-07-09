"use client";

import { Portfolio } from "@/lib/types";

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  connected: boolean;
}

export default function Header({ totalValue, cashBalance, connected }: HeaderProps) {
  const statusColor = connected ? "#22c55e" : "#ef4444";

  return (
    <header
      className="flex items-center justify-between px-4 py-3 border-b"
      style={{ backgroundColor: "#161b22", borderColor: "#30363d" }}
    >
      <div className="flex items-center gap-2">
        <span
          className="text-xl font-bold tracking-wider"
          style={{ color: "#ecad0a" }}
        >
          FinAlly
        </span>
        <span className="text-xs" style={{ color: "#8b949e" }}>
          AI Trading Workstation
        </span>
      </div>

      <div className="flex items-center gap-8">
        <div className="text-center">
          <div className="text-xs uppercase tracking-wide" style={{ color: "#8b949e" }}>
            Portfolio Value
          </div>
          <div className="text-lg font-bold" style={{ color: "#e6edf3" }}>
            ${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs uppercase tracking-wide" style={{ color: "#8b949e" }}>
            Cash Available
          </div>
          <div className="text-lg font-bold" style={{ color: "#209dd7" }}>
            ${cashBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: statusColor }}
            title={connected ? "Connected" : "Disconnected"}
          />
          <span className="text-xs" style={{ color: "#8b949e" }}>
            {connected ? "Live" : "Reconnecting"}
          </span>
        </div>
      </div>
    </header>
  );
}
