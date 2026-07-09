#!/bin/bash
# start_mac.sh — Build and run the FinAlly Docker container on macOS/Linux.
# Usage: ./scripts/start_mac.sh [--build]
#   --build   Force a fresh image build before starting.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

CONTAINER_NAME="finally-app"
IMAGE_NAME="finally"
VOLUME_NAME="finally-data"

# ── Check Docker is running ────────────────────────────────────────────────
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# ── Stop any existing container with the same name ─────────────────────────
EXISTING=$(docker ps -aq -f "name=^${CONTAINER_NAME}$")
if [ -n "$EXISTING" ]; then
    echo "Stopping existing container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" > /dev/null
    docker rm "$CONTAINER_NAME" > /dev/null
fi

# ── Build image ────────────────────────────────────────────────────────────
BUILD_FLAG=""
if [ "$1" = "--build" ] || [ -z "$(docker images -q "$IMAGE_NAME")" ]; then
    echo "Building Docker image..."
    docker build --tag "$IMAGE_NAME" .
    BUILD_FLAG=" (fresh build)"
fi

# ── Run container ──────────────────────────────────────────────────────────
echo "Starting container: $CONTAINER_NAME"
docker run \
    --name "$CONTAINER_NAME" \
    --detach \
    --publish 8000:8000 \
    --env-file .env \
    --volume "${VOLUME_NAME}:/app/db" \
    --restart unless-stopped \
    "$IMAGE_NAME"

# ── Wait for the app to be ready ───────────────────────────────────────────
echo "Waiting for FinAlly to be ready..."
for i in $(seq 1 30); do
    if curl -s --max-time 2 http://localhost:8000/api/health > /dev/null 2>&1; then
        echo ""
        echo "================================================"
        echo "  FinAlly is ready!"
        echo "  Open http://localhost:8000 in your browser"
        echo "================================================"
        exit 0
    fi
    sleep 1
done

echo ""
echo "Timed out waiting for FinAlly to start."
echo "Check logs with: docker logs $CONTAINER_NAME"
exit 1
