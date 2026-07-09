"use client";

import { useEffect, useRef } from "react";
import { usePrices } from "@/lib/priceContext";
import type { IChartApi, ISeriesApi, LineData, Time } from "lightweight-charts";

function priceToChartTime(ts: number): Time {
  return (ts / 1000) as Time;
}

export default function MainChart() {
  const { selectedTicker, prices, priceHistory } = usePrices();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const initializedRef = useRef(false);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current || initializedRef.current) return;

    let chart: IChartApi;

    (async () => {
      const { createChart, CrosshairMode } = await import("lightweight-charts");
      if (!containerRef.current) return;

      chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight || 320,
        layout: {
          background: { color: "#161b22" },
          textColor: "#8b949e",
        },
        grid: {
          vertLines: { color: "#21262d" },
          horzLines: { color: "#21262d" },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: "#ecad0a", width: 1, style: 2 },
          horzLine: { color: "#ecad0a", width: 1, style: 2 },
        },
        rightPriceScale: {
          borderColor: "#21262d",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
          borderColor: "#21262d",
          timeVisible: true,
          secondsVisible: false,
        },
        handleScroll: true,
        handleScale: true,
      });

      const lineSeries = chart.addLineSeries({
        color: "#209dd7",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
      });

      chartRef.current = chart;
      seriesRef.current = lineSeries;
      initializedRef.current = true;

      // Resize handling
      const ro = new ResizeObserver(() => {
        if (containerRef.current && chart) {
          chart.applyOptions({
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight || 320,
          });
        }
      });
      ro.observe(containerRef.current);
      resizeObserverRef.current = ro;
    })();

    return () => {
      if (chart) {
        chart.remove();
        chartRef.current = null;
        seriesRef.current = null;
        initializedRef.current = false;
      }
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
        resizeObserverRef.current = null;
      }
    };
  }, []);

  // Update data when selected ticker or prices change
  useEffect(() => {
    if (!seriesRef.current) return;

    const hist = priceHistory.current.get(selectedTicker) ?? [];
    if (hist.length === 0) {
      // Try to use the live price as a starting point
      const live = prices[selectedTicker];
      if (live) {
        const now = Math.floor(Date.now() / 1000);
        const bar: LineData = { time: now as Time, value: live.price };
        seriesRef.current.setData([bar]);
        seriesRef.current.update(bar);
      }
      return;
    }

    // Build chart data from accumulated history
    const nowSec = Math.floor(Date.now() / 1000);
    const startSec = nowSec - hist.length * 0.5; // 0.5s per tick
    const data: LineData[] = hist.map((price, i) => ({
      time: (startSec + i * 0.5) as Time,
      value: price,
    }));

    seriesRef.current.setData(data);
    // Update to latest
    if (data.length > 0) {
      seriesRef.current.update(data[data.length - 1]);
    }
  }, [selectedTicker, prices, priceHistory]);

  const currentPrice = prices[selectedTicker]?.price;
  const direction = prices[selectedTicker]?.direction;

  return (
    <div className="flex flex-col h-full">
      {/* Chart header */}
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="flex items-center gap-3">
          <h2 className="font-bold text-base" style={{ color: "#c9d1d9" }}>{selectedTicker}</h2>
          {currentPrice != null && (
            <span
              className="font-bold text-lg"
              style={{ fontFamily: "JetBrains Mono, monospace", color: direction === "up" ? "#3fb950" : direction === "down" ? "#f85149" : "#c9d1d9" }}
            >
              ${currentPrice.toFixed(2)}
            </span>
          )}
        </div>
        <span className="text-xs text-muted">Live</span>
      </div>

      {/* Chart container */}
      <div ref={containerRef} className="flex-1 min-h-0 rounded-md overflow-hidden" style={{ border: "1px solid #21262d" }} />
    </div>
  );
}
