"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { sendChat } from "@/lib/api";
import type { ChatResponse, TradeAction, WatchlistChange } from "@/lib/types";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  trades?: TradeAction[];
  watchlist_changes?: WatchlistChange[];
  errors?: string[];
  timestamp: Date;
}

function TradeBadge({ trade }: { trade: TradeAction }) {
  const color = trade.side === "buy" ? "text-profit" : "text-loss";
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded border ${color} border-current/30`}>
      <span>{trade.side === "buy" ? "BUY" : "SELL"}</span>
      <span>{trade.quantity}</span>
      <span className="font-mono">{trade.ticker}</span>
    </span>
  );
}

function WatchlistBadge({ change }: { change: WatchlistChange }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded border text-blue border-blue/30`}>
      <span>{change.action === "add" ? "+" : "-"}</span>
      <span className="font-mono">{change.ticker}</span>
    </span>
  );
}

interface ChatPanelProps {
  onTradeExecuted?: () => void;
}

export default function ChatPanel({ onTradeExecuted }: ChatPanelProps) {
  const [open, setOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response: ChatResponse = await sendChat(text);

      const assistantMsg: ChatMessage = {
        id: response.id,
        role: "assistant",
        content: response.message,
        trades: response.trades,
        watchlist_changes: response.watchlist_changes,
        errors: response.actions?.trades ? [] : undefined,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (response.trades?.length || response.watchlist_changes?.length) {
        onTradeExecuted?.();
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Something went wrong";
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: `Error: ${errMsg}`,
          errors: [errMsg],
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const toggleOpen = () => setOpen((o) => !o);

  return (
    <div
      className="flex flex-col border-t"
      style={{ borderColor: "#21262d", backgroundColor: "#0d1117" }}
    >
      {/* Panel header */}
      <button
        className="flex items-center justify-between px-3 py-2 w-full text-left hover:bg-bg-2 transition-colors"
        onClick={toggleOpen}
      >
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 3a2 2 0 1 1 0 4 2 2 0 0 1 0-4zm0 14.5a7.5 7.5 0 0 1-6.5-6.5h13A7.5 7.5 0 0 1 12 19.5z" fill="#ecad0a"/>
          </svg>
          <span className="text-xs font-semibold uppercase tracking-wider text-accent">AI Assistant</span>
        </div>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
        >
          <path d="M7 10l5 5 5-5" stroke="#8b949e" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {/* Chat content */}
      {open && (
        <div className="flex flex-col" style={{ height: 280 }}>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
            {messages.length === 0 && (
              <div className="text-center text-muted text-xs py-4">
                Ask FinAlly about your portfolio, request analysis, or execute trades naturally.
              </div>
            )}
            {messages.map((msg) => (
              <div key={msg.id} className="flex flex-col gap-1">
                {msg.role === "user" && (
                  <div className="flex justify-end">
                    <div
                      className="max-w-[80%] rounded-lg px-3 py-2 text-sm"
                      style={{ backgroundColor: "#209dd7", color: "#fff" }}
                    >
                      {msg.content}
                    </div>
                  </div>
                )}
                {msg.role === "assistant" && (
                  <div className="flex justify-start">
                    <div className="max-w-[85%] flex flex-col gap-1">
                      {/* AI avatar */}
                      <div className="flex items-center gap-1.5">
                        <div
                          className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: "#753991" }}
                        >
                          <span className="text-[9px] font-bold text-white">AI</span>
                        </div>
                        <span className="text-xs text-muted">
                          {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>

                      {/* Message text */}
                      <div
                        className="rounded-lg px-3 py-2 text-sm"
                        style={{ backgroundColor: "#161b22", border: "1px solid #21262d" }}
                      >
                        {msg.content}
                      </div>

                      {/* Trade confirmations */}
                      {msg.trades && msg.trades.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {msg.trades.map((t, i) => (
                            <TradeBadge key={i} trade={t} />
                          ))}
                        </div>
                      )}

                      {/* Watchlist changes */}
                      {msg.watchlist_changes && msg.watchlist_changes.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {msg.watchlist_changes.map((w, i) => (
                            <WatchlistBadge key={i} change={w} />
                          ))}
                        </div>
                      )}

                      {/* Errors */}
                      {msg.errors && msg.errors.length > 0 && (
                        <div className="flex flex-col gap-0.5">
                          {msg.errors.map((e, i) => (
                            <span key={i} className="text-xs text-loss">Error: {e}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Loading indicator */}
            {loading && (
              <div className="flex justify-start">
                <div
                  className="rounded-lg px-3 py-2 text-sm flex items-center gap-2"
                  style={{ backgroundColor: "#161b22", border: "1px solid #21262d" }}
                >
                  <div className="spinner" />
                  <span className="text-muted text-xs">FinAlly is thinking…</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-3 py-2 border-t" style={{ borderColor: "#21262d" }}>
            <form onSubmit={handleSubmit} className="flex gap-2">
              <textarea
                ref={inputRef}
                className="input-field resize-none flex-1"
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask FinAlly…"
                disabled={loading}
                style={{ maxHeight: 80 }}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="btn-accent flex-shrink-0 flex items-center gap-1"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M22 2L11 13" stroke="white" strokeWidth="2" strokeLinecap="round" />
                  <path d="M22 2L15 22 11 13 2 9l20-7z" stroke="white" strokeWidth="2" strokeLinejoin="round" />
                </svg>
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
