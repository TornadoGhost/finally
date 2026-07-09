"use client";

import { useCallback, useState } from "react";
import { PriceProvider, usePrices } from "@/lib/priceContext";
import Header from "@/components/Header";
import Watchlist from "@/components/Watchlist";
import MainChart from "@/components/MainChart";
import TradeBar from "@/components/TradeBar";
import PortfolioHeatmap from "@/components/PortfolioHeatmap";
import PNLChart from "@/components/PNLChart";
import PositionsTable from "@/components/PositionsTable";
import ChatPanel from "@/components/ChatPanel";

function TradingTerminal() {
  const { setSelectedTicker } = usePrices();
  const [refreshKey, setRefreshKey] = useState(0);

  const handleTradeExecuted = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const handleSelectTicker = useCallback(
    (ticker: string) => {
      setSelectedTicker(ticker);
    },
    [setSelectedTicker]
  );

  return (
    <div className="flex flex-col" style={{ height: "100dvh", backgroundColor: "#0d1117" }}>
      {/* Header */}
      <Header />

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Watchlist */}
        <aside
          className="flex flex-col overflow-hidden"
          style={{ width: 220, minWidth: 200, borderRight: "1px solid #21262d" }}
        >
          <div className="flex-1 overflow-y-auto p-3">
            <Watchlist />
          </div>
        </aside>

        {/* Center: Main chart + bottom charts */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Main chart area */}
          <div className="flex-1 min-h-0 p-3 overflow-hidden">
            <div
              className="h-full panel p-3 flex flex-col"
              style={{ backgroundColor: "#161b22" }}
            >
              <MainChart />
            </div>
          </div>

          {/* Bottom panels: Heatmap + P&L chart */}
          <div
            className="flex gap-3 px-3 pb-3"
            style={{ height: 220, minHeight: 200 }}
          >
            {/* Portfolio Heatmap */}
            <div
              className="flex-1 panel p-3 overflow-hidden flex flex-col"
              style={{ backgroundColor: "#161b22" }}
            >
              <PortfolioHeatmap onSelectTicker={handleSelectTicker} />
            </div>

            {/* P&L Chart */}
            <div
              className="flex-1 panel p-3 overflow-hidden flex flex-col"
              style={{ backgroundColor: "#161b22" }}
            >
              <PNLChart />
            </div>
          </div>
        </main>

        {/* Right: Trade bar + Positions table */}
        <aside
          className="flex flex-col overflow-hidden"
          style={{ width: 280, minWidth: 240, borderLeft: "1px solid #21262d" }}
        >
          {/* Trade bar */}
          <div className="p-3" style={{ borderBottom: "1px solid #21262d" }}>
            <TradeBar onTradeExecuted={handleTradeExecuted} />
          </div>

          {/* Positions table */}
          <div key={refreshKey} className="flex-1 overflow-y-auto p-3">
            <PositionsTable onSelectTicker={handleSelectTicker} />
          </div>
        </aside>
      </div>

      {/* AI Chat Panel */}
      <ChatPanel onTradeExecuted={handleTradeExecuted} />
    </div>
  );
}

export default function HomePage() {
  return (
    <PriceProvider>
      <TradingTerminal />
    </PriceProvider>
  );
}
