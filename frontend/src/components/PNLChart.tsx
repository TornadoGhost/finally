"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from "recharts";
import { fetchHistory } from "@/lib/api";
import type { HistorySnapshot } from "@/lib/types";

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0 }).format(n);
}

function formatTime(ts: string) {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return ts;
  }
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-bg-2 border border-border px-3 py-2 rounded text-xs shadow-lg">
      <div className="text-muted mb-1">{label ? formatTime(label) : ""}</div>
      <div className="font-bold" style={{ fontFamily: "JetBrains Mono, monospace", color: "#209dd7" }}>
        {fmt(payload[0].value)}
      </div>
    </div>
  );
}

export default function PNLChart() {
  const [snapshots, setSnapshots] = useState<HistorySnapshot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory()
      .then((data) => {
        setSnapshots(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  // Refresh periodically
  useEffect(() => {
    const id = setInterval(() => {
      fetchHistory()
        .then(setSnapshots)
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  const chartData = snapshots.map((s) => ({
    time: s.recorded_at,
    value: s.total_value,
  }));

  const minVal = chartData.length ? Math.min(...chartData.map((d) => d.value)) : 0;
  const maxVal = chartData.length ? Math.max(...chartData.map((d) => d.value)) : 0;

  return (
    <div className="flex flex-col h-full">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Portfolio Value</h2>
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-muted text-sm">Loading…</div>
      ) : chartData.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted text-sm">
          No history yet — make some trades!
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#209dd7" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#209dd7" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="time"
              tickFormatter={formatTime}
              tick={{ fill: "#8b949e", fontSize: 10 }}
              axisLine={{ stroke: "#21262d" }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[minVal * 0.998, maxVal * 1.002]}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              tick={{ fill: "#8b949e", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={52}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="value"
              stroke="transparent"
              fill="url(#pnlGradient)"
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#209dd7"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#ecad0a" }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
