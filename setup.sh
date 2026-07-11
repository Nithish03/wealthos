#!/bin/bash
set -e

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║         WealthOS Finance Tracker Setup         ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is required. Install from https://python.org"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(sys.version_info.minor)")
echo "✅ Python 3.$PYTHON_VERSION found"

# Check Node.js
if ! command -v node &>/dev/null; then
    echo "❌ Node.js is required. Install from https://nodejs.org"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "✅ Node.js $NODE_VERSION found"

# Check npm
if ! command -v npm &>/dev/null; then
    echo "❌ npm is required. Install Node.js from https://nodejs.org"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo ""
echo "📂 Project dir: $SCRIPT_DIR"

# ── Backend Setup ──────────────────────────────────────
echo ""
echo "🐍 Setting up Python backend..."
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   Created virtual environment"
fi

source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✅ Python dependencies installed"

# ── Frontend Setup ─────────────────────────────────────
echo ""
echo "⚛️  Setting up React frontend..."
cd "$SCRIPT_DIR/frontend"
npm install --silent
echo "✅ Node modules installed"

# ── Create .env if missing ─────────────────────────────
if [ ! -f "$SCRIPT_DIR/backend/.env" ]; then
    cat > "$SCRIPT_DIR/backend/.env" << 'ENV'
DB_PATH=./finance_tracker.db
PORT=8000
ENV
fi

# ── Launch ─────────────────────────────────────────────
echo ""
echo "🚀 Starting WealthOS..."
echo ""

# Start backend
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "✅ Backend started (PID $BACKEND_PID) → http://localhost:8000"

sleep 2

# Start frontend
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo "✅ Frontend started (PID $FRONTEND_PID) → http://localhost:3000"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║   🌐 Open http://localhost:3000 in browser    ║"
echo "║   Press Ctrl+C to stop both servers           ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# Open browser (macOS / Linux)
sleep 3
if command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:3000 &>/dev/null || true
elif command -v open &>/dev/null; then
    open http://localhost:3000 &>/dev/null || true
fi

# Trap to clean up on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo "✅ Stopped. Goodbye!"
}
trap cleanup EXIT INT TERM

wait
