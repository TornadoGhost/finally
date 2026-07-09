# ─── Stage 1: Build frontend ────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Copy only package files first (for Docker layer caching)
COPY frontend/package.json frontend/package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source and build
COPY frontend/ ./
RUN npm run build

# ─── Stage 2: Serve with FastAPI ────────────────────────────────────────────
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN chmod +x /usr/local/bin/uv

WORKDIR /app

# Copy Python source into /app/backend/
COPY backend/ ./backend/

WORKDIR /app/backend

# Install Python dependencies (base only, no dev)
RUN uv sync --frozen

# Copy built frontend (static export) into the app directory.
# main.py looks 3 levels up from backend/app/main.py -> /app, then checks /app/frontend/out
WORKDIR /app
COPY --from=frontend-builder /app/frontend/out ./frontend/out

ENV FINALLY_DB_DIR=/app/db
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

EXPOSE 8000

WORKDIR /app/backend
CMD ["/app/backend/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
