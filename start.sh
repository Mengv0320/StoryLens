#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.9+."
    exit 1
fi

# Build frontend if dist doesn't exist
if [ ! -d "$SCRIPT_DIR/gui/dist" ]; then
    echo "[start.sh] gui/dist not found, building frontend..."
    if ! command -v npm &>/dev/null; then
        echo "ERROR: npm not found. Please install Node.js."
        exit 1
    fi
    cd "$SCRIPT_DIR/gui" && npm run build
    cd "$SCRIPT_DIR"
fi

echo "[start.sh] Starting server..."
echo "[start.sh] Access: http://localhost:8765"
cd "$SCRIPT_DIR"
python3 -m src.api_server
