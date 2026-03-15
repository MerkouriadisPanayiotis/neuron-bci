#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

VENV_DIR="$DIR/.venv"

# Find Python 3.10+ (required by claude-agent-sdk)
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" > /dev/null 2>&1; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "[NEURON] Error: Python 3.10+ is required. Install via: brew install python@3.12"
    exit 1
fi
echo "[NEURON] Using $PYTHON ($("$PYTHON" --version))"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "[NEURON] Creating Python virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install/update Python dependencies
echo "[NEURON] Installing Python dependencies..."
pip install -q -r requirements.txt

# Install frontend dependencies if needed
if [ ! -d "$DIR/frontend/node_modules" ]; then
    echo "[NEURON] Installing frontend dependencies..."
    (cd "$DIR/frontend" && npm install)
fi

# Load .env if present
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

# Start backend — this will block waiting for Muse data stream,
# then start serving once the headband is connected
echo "[NEURON] Starting backend — waiting for Muse headband connection..."
uvicorn web.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready (Muse connected + server up)
echo "[NEURON] Waiting for backend to come up..."
until curl -sf http://localhost:8000/api/health > /dev/null 2>&1; do
    # Exit if backend process died
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "[NEURON] Backend failed to start."
        exit 1
    fi
    sleep 1
done

echo "[NEURON] Backend ready. Starting frontend..."
(cd "$DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

# Clean up both processes on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

echo "[NEURON] Running on http://localhost:3000 — Press Ctrl+C to stop."
wait
