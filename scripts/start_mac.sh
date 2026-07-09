#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Build if needed or if --build flag passed
if [ "$1" = "--build" ]; then
  echo "Building FinAlly image..."
  docker compose build finally
fi

# Start FinAlly + Ollama via docker compose
echo "Starting FinAlly + Ollama..."
docker compose up -d

# Wait for Ollama to be healthy
echo "Waiting for Ollama..."
for i in $(seq 1 30); do
  if docker exec finally-ollama ollama list > /dev/null 2>&1; then
    break
  fi
  echo "  waiting ($i/30)..."
  sleep 1
done

# Pull model if not already downloaded
MODEL="${OLLAMA_MODEL:-qwen2.5:0.5b}"
if ! docker exec finally-ollama ollama list | grep -q "$MODEL"; then
  echo "Pulling Ollama model: $MODEL (first run only, ~500MB for haiku)..."
  docker exec finally-ollama ollama pull "$MODEL"
else
  echo "Ollama model '$MODEL' already present."
fi

# Wait for FinAlly to be healthy
echo "Waiting for FinAlly..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "FinAlly is ready at http://localhost:8000"
    exit 0
  fi
  sleep 1
done

echo "FinAlly took too long to start. Check: docker compose logs"
