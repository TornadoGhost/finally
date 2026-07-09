#!/bin/bash
# stop_mac.sh — Stop and remove the FinAlly container.
# The named volume (finally-data) is preserved so data persists across restarts.

set -e

CONTAINER_NAME="finally-app"

EXISTING=$(docker ps -aq -f "name=^${CONTAINER_NAME}$")
if [ -z "$EXISTING" ]; then
    echo "No running FinAlly container found."
    exit 0
fi

echo "Stopping FinAlly container..."
docker stop "$CONTAINER_NAME"
docker rm "$CONTAINER_NAME"
echo "FinAlly stopped. Database volume (finally-data) is preserved."
echo "Run ./scripts/start_mac.sh to start again."
