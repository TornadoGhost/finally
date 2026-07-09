"use client";

import { useState, useEffect, useCallback } from "react";
import Header from "@/components/Header";
import Watchlist from "@/components/Watchlist";
import MainChart from "@/components/MainChart";
import PortfolioHeatmap from "@/components/PortfolioHeatmap";
import PLChart from "@/components/PLChart";
import PositionsTable from "@/components/PositionsTable";
import TradeBar from "@/components/TradeBar";
import ChatPanel from "@/components/ChatPanel";
import { usePriceStream } from "@/hooks/usePriceStream";
import {
  fetchPortfolio,
  fetchPortfolioHistory,
  addToWatchlist,
} from "@/lib/api";
import { Portfolio, PortfolioSnapshot } from "@/lib/types";

export default function Home() {
  const { prices, connected } = usePriceStream();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<PortfolioSnapshot[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);

  const loadPortfolio = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([fetchPortfolio(), fetchPortfolioHistory()]);
      setPortfolio(p);
      setHistory(h);
    } catch (e) {
      console.error("Failed to load portfolio:", e);
    }
  }, []);

  useEffect(() => {
    loadPortfolio();
    const interval = setInterval(loadPortfolio, 5000);
    return () => clearInterval(interval);
  }, [loadPortfolio]);

  const handleAddTicker = async (ticker: string) => {
    try {
      await addToWatchlist(ticker);
    } catch (e) {
      console.error("Failed to add ticker:", e);
    }
  };

  const handleTradeExecuted = () => {
    loadPortfolio();
  };

  const handleAction = () => {
    loadPortfolio();
  };

  const totalValue = portfolio?.total_value ?? 0;
  const cashBalance = portfolio?.cash_balance ?? 0;
  const positions = portfolio?.positions ?? [];

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: "#0d1117" }}>
      <Header
        totalValue={totalValue}
        cashBalance={cashBalance}
        connected={connected}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left column: watchlist */}
        <div
          className="flex flex-col gap-2 p-2 overflow-hidden"
          style={{ width: 360, flexShrink: 0 }}
        >
          <div className="flex-1 overflow-hidden">
            <Watchlist
              prices={prices}
              selectedTicker={selectedTicker}
              onSelectTicker={setSelectedTicker}
              onAddTicker={handleAddTicker}
            />
          </div>
        </div>

        {/* Center column */}
        <div className="flex-1 flex flex-col gap-2 p-2 overflow-y-auto min-w-0">
          <MainChart ticker={selectedTicker} prices={prices} />
          <PortfolioHeatmap positions={positions} totalValue={totalValue} />
          <TradeBar
            selectedTicker={selectedTicker}
            cashBalance={cashBalance}
            onTradeExecuted={handleTradeExecuted}
          />
          <PLChart snapshots={history} />
          <PositionsTable positions={positions} prices={prices} />
        </div>

        {/* Right column: chat panel */}
        <div className="shrink-0 p-2 overflow-hidden" style={{ height: "100%" }}>
          <ChatPanel
            open={chatOpen}
            onToggle={() => setChatOpen((v) => !v)}
            onAction={handleAction}
            onChartRequest={setSelectedTicker}
            prices={prices}
          />
        </div>
      </div>
    </div>
  );
}
