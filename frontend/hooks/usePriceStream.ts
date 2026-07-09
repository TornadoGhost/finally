import { useEffect, useRef, useState, useCallback } from "react";
import { PriceUpdate } from "@/lib/types";

const BASE = "http://localhost:8000";

interface PriceHistoryPoint {
  price: number;
  timestamp: number;
}

export function usePriceStream() {
  const [prices, setPrices] = useState<Map<string, PriceUpdate>>(new Map());
  const [connected, setConnected] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const historyRef = useRef<Map<string, PriceHistoryPoint[]>>(new Map());
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }

    const es = new EventSource(`${BASE}/api/stream/prices`);

    es.onopen = () => {
      setConnected(true);
      setLastError(null);
    };

    es.onmessage = (event) => {
      try {
        const update: PriceUpdate = JSON.parse(event.data);
        setPrices((prev) => {
          const next = new Map(prev);
          next.set(update.ticker, update);
          return next;
        });
        // Accumulate history for sparklines
        const hist = historyRef.current;
        const points = hist.get(update.ticker) || [];
        points.push({ price: update.price, timestamp: update.timestamp });
        // Keep last 200 points for sparkline
        if (points.length > 200) points.shift();
        hist.set(update.ticker, points);
      } catch {
        // ignore malformed messages
      }
    };

    es.onerror = () => {
      setConnected(false);
      setLastError("Connection lost. Reconnecting...");
      es.close();
      // EventSource auto-reconnects, but we also track state
      setTimeout(connect, 2000);
    };

    esRef.current = es;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
    };
  }, [connect]);

  const getHistory = useCallback((ticker: string): PriceHistoryPoint[] => {
    return historyRef.current.get(ticker) || [];
  }, []);

  return { prices, connected, lastError, getHistory };
}
