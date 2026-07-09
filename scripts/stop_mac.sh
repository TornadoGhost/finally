#!/bin/bash
cd "$(dirname "$0")/.."
docker compose down
echo "FinAlly stopped (data persists in 'finally-data' and 'ollama-data' volumes)"
