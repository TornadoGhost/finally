# FinAlly Project - the Finance Ally

All project documentation is in the `planning` directory. The key document is `planning/PLAN.md`.

The full platform is now complete:
- Market data: `backend/app/market/` — GBM simulator + Massive API, SSE streaming
- Database: `backend/db/` — SQLite lazy init, 6 tables, async repositories
- API: `backend/app/main.py` — all REST endpoints wired to DB + market data
- LLM: `backend/app/llm/chat.py` — LiteLLM with OpenRouter + local Ollama fallback
- Frontend: `frontend/` — Next.js static export, all terminal components
- Docker: `Dockerfile`, `docker-compose.yml`, `scripts/`
- Tests: `backend/tests/` (unit), `test/` (Playwright E2E)
