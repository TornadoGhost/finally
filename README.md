# FinAlly — AI Trading Workstation

An AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container on port 8000:

- **Frontend**: Next.js (static export), TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python/uv), SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM — OpenRouter (if API key set) or local Ollama (GPU-free)
- **Market data**: Built-in GBM simulator (default) or Massive API (optional)

## Quick Start

```bash
cp .env.example .env
./scripts/start_mac.sh
```

First run pulls the Ollama model (qwen2.5:0.5b, ~400MB) automatically. Open http://localhost:8000

Stop: `./scripts/stop_mac.sh`

## AI Models

LLM provider priority: **OpenRouter → Ollama → mock mode**

| Provider | Setup | Model |
|---|---|---|
| OpenRouter | Set `OPENROUTER_API_KEY` in `.env` | GPT-OSS-120B via Cerebras |
| Ollama (Docker) | Built into docker-compose | Haiku (default) |

To use a different Ollama model, add to `.env` and run again:
```bash
echo "OLLAMA_MODEL=llama3.2" >> .env
./scripts/start_mac.sh
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | No | OpenRouter API key; omit to use Ollama |
| `OLLAMA_MODEL` | No | Ollama model name (default: `haiku`) |
| `MASSIVE_API_KEY` | No | Real market data via Massive (Polygon.io) |
| `LLM_MOCK` | No | `true` for deterministic mock responses (testing/CI) |

## Project Structure

```
finally/
├── frontend/    # Next.js static export
├── backend/     # FastAPI uv project
├── planning/    # Project documentation and agent contracts
├── test/        # Playwright E2E tests
└── db/          # SQLite volume mount (runtime)
```

## License

See [LICENSE](LICENSE).
