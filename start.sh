#!/bin/bash
# Single-server mode: build the frontend once, then serve app + API from
# one port. Open http://<this-machine>:8000 from your phone (same Wi-Fi,
# or from anywhere via Tailscale).
# First-time setup (venv + node_modules): run ./setup.sh once before this.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "⚛️  Building frontend..."
cd "$SCRIPT_DIR/frontend"
npm run build

cd "$SCRIPT_DIR/backend"
source venv/bin/activate

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$LAN_IP" ] && LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || true)

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  🚀 WealthOS — single-server mode                  ║"
echo "║                                                    ║"
echo "║  This machine:  http://localhost:8000              ║"
[ -n "$LAN_IP" ] && \
echo "║  Your phone:    http://$LAN_IP:8000"
echo "║  (same Wi-Fi, or Tailscale from anywhere)          ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

exec uvicorn main:app --host 0.0.0.0 --port 8000
