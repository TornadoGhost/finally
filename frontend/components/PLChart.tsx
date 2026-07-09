"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { PortfolioSnapshot } from "@/lib/types";

interface PLChartProps {
  snapshots: PortfolioSnapshot[];
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export default function PLChart({ snapshots }: PLChartProps) {
  const snapshotsArr = Array.isArray(snapshots) ? snapshots : [];
  const data = snapshotsArr.map((s) => ({
    time: formatTime(s.recorded_at),
    value: s.total_value,
  }));

  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg"
        style={{ height: 180, backgroundColor: "#0d1117" }}
      >
        <span className="text-sm" style={{ color: "#8b949e" }}>
          No portfolio history yet.
        </span>
      </div>
    );
  }

  const minVal = Math.min(...data.map((d) => d.value));
  const maxVal = Math.max(...data.map((d) => d.value));

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ backgroundColor: "#0d1117" }}
    >
      <div className="px-4 py-2 border-b" style={{ borderColor: "#30363d" }}>
        <span className="text-xs uppercase tracking-widest font-bold" style={{ color: "#8b949e" }}>
          Portfolio P&L Over Time
        </span>
        <span className="ml-3 text-xs font-bold" style={{ color: "#e6edf3" }}>
          ${minVal.toFixed(0)} — ${maxVal.toFixed(0)}
        </span>
      </div>
      <div style={{ height: 180, padding: "8px 0" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis
              dataKey="time"
              tick={{ fill: "#8b949e", fontSize: 10 }}
              axisLine={{ stroke: "#30363d" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#8b949e", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
              width={50}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#161b22",
                border: "1px solid #30363d",
                color: "#e6edf3",
                fontSize: 12,
              }}
              labelStyle={{ color: "#8b949e" }}
              formatter={(v) => [`$${Number(v).toFixed(2)}`, "Portfolio Value"] as [string, string]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#209dd7"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#209dd7" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
