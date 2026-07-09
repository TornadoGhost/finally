# Stage 1: Build frontend (already done, but ensure consistency)
FROM node:20-slim AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Run the application
FROM python:3.12-slim

# Install uv for fast Python package management
RUN pip install uv

WORKDIR /app

# Copy backend source
COPY backend/ ./backend/

# Copy pre-built frontend static files to backend/static (matches main.py path)
COPY frontend/out/ ./backend/static/

# Install Python dependencies
RUN uv sync --directory backend

# Environment variables
ENV PYTHONPATH=/app
ENV FINALLY_DB_PATH=/app/db/finally.db

# Expose port
EXPOSE 8000

# Start uvicorn via uv run (uses the venv from uv sync)
CMD ["uv", "run", "--directory", "backend", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
