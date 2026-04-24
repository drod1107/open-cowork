#!/usr/bin/env bash
# OpenCowork one-command installer (Debian / Ubuntu / KDE Plasma).
#
# - Installs system deps for desktop control (ydotool, spectacle, imagemagick, xdotool)
# - Creates a Python venv in ./.venv and installs backend deps
# - Installs Playwright MCP globally via npm
# - Builds the React frontend
# - Enables the ydotoold user service
# - Prints the URL to open on the local network / over Tailscale

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

log() { printf "\033[1;36m[opencowork]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[opencowork]\033[0m %s\n" "$*"; }

# --- 1. system packages --------------------------------------------------
if command -v apt-get >/dev/null 2>&1; then
  log "Installing system packages (needs sudo)…"
  sudo apt-get update
  sudo apt-get install -y \
    python3 python3-venv python3-pip \
    ydotool xdotool imagemagick scrot \
    kde-spectacle \
    curl ca-certificates
else
  warn "apt-get not found; please install python3 / ydotool / xdotool / spectacle / scrot manually."
fi

# --- 2. Node.js 20 -------------------------------------------------------
if ! command -v node >/dev/null 2>&1; then
  log "Installing Node.js 20 via NodeSource…"
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

# --- 3. Python venv + backend deps --------------------------------------
if [[ ! -d .venv ]]; then
  log "Creating Python venv in ./.venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

# --- 4. Playwright MCP ---------------------------------------------------
if ! command -v npx >/dev/null 2>&1; then
  warn "npx not available, skipping Playwright MCP install"
else
  log "Installing @playwright/mcp…"
  sudo npm install -g @playwright/mcp@latest || warn "global install failed; will use npx at runtime"
fi

# --- 5. Frontend build ---------------------------------------------------
log "Installing and building the React frontend…"
(cd frontend && npm install && npm run build)

# --- 6. ydotoold user service -------------------------------------------
if command -v systemctl >/dev/null 2>&1; then
  log "Enabling ydotoold user service…"
  mkdir -p "${HOME}/.config/systemd/user"
  cat > "${HOME}/.config/systemd/user/ydotoold.service" <<'UNIT'
[Unit]
Description=ydotool daemon

[Service]
ExecStart=/usr/bin/ydotoold
Restart=on-failure

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload || true
  systemctl --user enable --now ydotoold || warn "could not start ydotoold (Wayland session not active?)"
fi

# --- 7. Summary ----------------------------------------------------------
log "Install complete."
cat <<EOS

Next steps:
  1. source .venv/bin/activate
  2. python -m backend.main
  3. Open http://localhost:7337
     (over Tailscale: http://<your-tailnet-ip>:7337)

Config lives at: backend/config/config.toml
EOS
