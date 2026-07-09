"use client";

import { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, LineSeries, Time } from "lightweight-charts";
import { PriceUpdate } from "@/lib/types";

interface MainChartProps {
  ticker: string | null;
  prices: Map<string, PriceUpdate>;
}

export default function MainChart({ ticker, prices }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const historyRef = useRef<{ time: Time; value: number }[]>([]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#0d1117" },
        textColor: "#8b949e",
      },
      grid: {
        vertLines: { color: "#1c2128" },
        horzLines: { color: "#1c2128" },
      },
      width: containerRef.current.clientWidth,
      height: 300,
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: {
          time: true,
          price: true,
        },
        pinch: true,
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: {
          labelBackgroundColor: "#209dd7",
        },
        horzLine: {
          labelBackgroundColor: "#209dd7",
        },
      },
    });

    // Coarser scroll zoom — intercept wheel, adjust visible range
    const wheelHandler = (e: WheelEvent) => {
      e.preventDefault();
      const ts = chart.timeScale();
      const range = ts.getVisibleRange();
      if (!range) return;
      const from = range.from as number;
      const to = range.to as number;
      const factor = e.deltaY > 0 ? 1.18 : 0.85;
      const delta = to - from;
      ts.setVisibleRange({
        from: (from + delta * (1 - factor) / 2) as Time,
        to: (to - delta * (1 - factor) / 2) as Time,
      });
    };
    containerRef.current.addEventListener("wheel", wheelHandler, { passive: false });

    const series = chart.addSeries(LineSeries, {
      color: "#209dd7",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(containerRef.current);

    return () => {
      containerRef.current?.removeEventListener("wheel", wheelHandler);
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      historyRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (!ticker) return;
    historyRef.current = [];
    if (seriesRef.current) {
      seriesRef.current.setData([]);
    }
  }, [ticker]);

  useEffect(() => {
    if (!ticker) return;
    const update = prices.get(ticker);
    if (!update || !seriesRef.current) return;

    const point: { time: Time; value: number } = {
      time: (update.timestamp / 1000) as Time,
      value: update.price,
    };
    historyRef.current.push(point);

    if (historyRef.current.length > 500) {
      historyRef.current = historyRef.current.slice(-500);
    }

    seriesRef.current.update(point);
  }, [prices, ticker]);

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ backgroundColor: "#0d1117" }}
    >
      <div className="px-4 py-2 border-b" style={{ borderColor: "#30363d" }}>
        <span className="font-bold text-sm" style={{ color: "#ecad0a" }}>
          {ticker ? `${ticker} — Price Chart` : "Select a ticker to view chart"}
        </span>
        {ticker && prices.get(ticker) && (
          <span className="ml-3 text-sm font-bold" style={{ color: "#e6edf3" }}>
            ${prices.get(ticker)!.price.toFixed(2)}
          </span>
        )}
      </div>
      <div ref={containerRef} className="w-full chart-container" style={{ height: 300, paddingRight: 40 }} />
    </div>
  );
}
