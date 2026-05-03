#!/usr/bin/env bash
# Start OpenCowork. Run ./install.sh first if you haven't already.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [[ ! -d .venv ]]; then
  echo "No .venv found. Run ./install.sh first." >&2
  exit 1
fi

if [[ ! -d frontend/dist ]]; then
  echo "Frontend not built. Running build now…"
  (cd frontend && npm run build)
fi

HOST="${OPENCOWORK_HOST:-0.0.0.0}"
PORT="${OPENCOWORK_PORT:-7337}"

echo "Starting OpenCowork on http://${HOST}:${PORT}"
exec .venv/bin/python -m backend.main
