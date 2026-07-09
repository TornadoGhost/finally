"use client";

import { useState, useRef, useEffect } from "react";
import { sendChat } from "@/lib/api";
import { ChatResponse } from "@/lib/types";

interface ChartAction {
  ticker: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  trades?: {
    ticker: string;
    quantity: number;
    side: "buy" | "sell";
    price?: number;
    success?: boolean;
    error?: string;
  }[];
  watchlistChanges?: { ticker: string; action: "add" | "remove" }[];
  charts?: ChartAction[];
}

interface ChatPanelProps {
  open: boolean;
  onToggle: () => void;
  onAction: () => void;
  onChartRequest?: (ticker: string) => void;
  prices: Map<string, { ticker: string; price: number }>;
}

export default function ChatPanel({ open, onToggle, onAction, onChartRequest, prices }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm FinAlly, your AI trading assistant. Ask me to analyze your portfolio, suggest trades, or manage your watchlist.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Extract ticker from chart request before sending to LLM
    const chartPattern = /(?:show|display|chart|plot|view)\s+(?:me\s+)?(?:the\s+)?(?:chart\s+(?:for|of)?\s*)?(\b[A-Z]{2,5}\b)/i;
    const match = text.match(chartPattern);
    if (match) {
      const ticker = match[1].toUpperCase();
      onChartRequest?.(ticker);
    }

    try {
      const resp: ChatResponse = await sendChat(text);
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: resp.message,
        trades: resp.trades,
        watchlistChanges: resp.watchlist_changes,
        charts: resp.charts,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (resp.trades?.length || resp.watchlist_changes?.length) {
        onAction();
      }
      if (resp.charts?.length) {
        for (const chart of resp.charts) {
          onChartRequest?.(chart.ticker);
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${String(err)}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex flex-col rounded-lg overflow-hidden"
      style={{
        backgroundColor: "#161b22",
        border: "1px solid #30363d",
        width: open ? 300 : 48,
        minWidth: open ? 300 : 48,
        transition: "width 0.2s, min-width 0.2s",
        height: "100%",
      }}
    >
      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="flex items-center justify-center pl-2 py-2 border-b shrink-0"
        style={{ borderColor: "#30363d", backgroundColor: "#0d1117" }}
        title={open ? "Close chat" : "Open chat"}
      >
        <span className="text-xs font-bold pl-2" style={{ color: "#ecad0a" }}>
          {open ? "AI Chat" : "AI"}
        </span>
        <span className="ml-auto mr-2 text-xs" style={{ color: "#8b949e" }}>
          {open ? "<" : ">"}
        </span>
      </button>

      {open && (
        <>
          {/* Messages */}
          <div
            className="flex-1 overflow-y-auto p-3 flex flex-col gap-2"
            style={{ minHeight: 0 }}
          >
            {messages.map((msg, i) => (
              <div
                key={i}
                className="rounded-lg p-2 text-xs"
                style={{
                  backgroundColor: msg.role === "user" ? "#209dd7" : "#0d1117",
                  color: msg.role === "user" ? "#fff" : "#e6edf3",
                  border: msg.role === "assistant" ? "1px solid #30363d" : "none",
                  alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "90%",
                }}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.trades && msg.trades.length > 0 && (
                  <div className="mt-1 pt-1" style={{ borderTop: "1px solid #30363d" }}>
                    {msg.trades.map((t, j) => (
                      <div key={j} className="text-xs font-bold" style={{ color: t.success ? "#ecad0a" : "#f85149" }}>
                        {t.side === "buy" ? "Bought" : "Sold"} {t.quantity} {t.ticker}
                        {t.success && t.price != null ? ` @ $${t.price.toFixed(2)}` : t.error ? ` — ${t.error}` : ""}
                      </div>
                    ))}
                  </div>
                )}
                {msg.watchlistChanges && msg.watchlistChanges.length > 0 && (
                  <div className="mt-1 pt-1" style={{ borderTop: "1px solid #30363d" }}>
                    {msg.watchlistChanges.map((w, j) => (
                      <div key={j} className="text-xs font-bold" style={{ color: "#ecad0a" }}>
                        {w.action === "add" ? "Added" : "Removed"} {w.ticker} {w.action === "add" ? "to" : "from"} watchlist
                      </div>
                    ))}
                  </div>
                )}
                {msg.charts && msg.charts.length > 0 && (
                  <div className="mt-1 pt-1" style={{ borderTop: "1px solid #30363d" }}>
                    {msg.charts.map((c, j) => (
                      <div key={j} className="text-xs font-bold" style={{ color: "#209dd7" }}>
                        Showing chart for {c.ticker}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div
                className="rounded-lg p-2 text-xs animate-pulse"
                style={{ backgroundColor: "#0d1117", border: "1px solid #30363d", alignSelf: "flex-start" }}
              >
                <span style={{ color: "#8b949e" }}>Thinking...</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div
            className="flex gap-2 p-2 border-t shrink-0"
            style={{ borderColor: "#30363d" }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask FinAlly..."
              className="flex-1 px-2 py-1.5 text-xs rounded"
              style={{
                backgroundColor: "#0d1117",
                border: "1px solid #30363d",
                color: "#e6edf3",
                outline: "none",
              }}
            />
            <button
              onClick={handleSend}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-bold rounded"
              style={{ backgroundColor: "#753991", color: "#fff", opacity: loading ? 0.5 : 1 }}
            >
              Send
            </button>
          </div>
        </>
      )}
    </div>
  );
}
