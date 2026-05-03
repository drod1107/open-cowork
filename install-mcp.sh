#!/usr/bin/env bash
# install-mcp.sh — Install an MCP server from a GitHub URL or local path.
#
# Usage:
#   ./install-mcp.sh <github-url-or-local-path> [--name <name>]
#
# Examples:
#   ./install-mcp.sh https://github.com/example/my-mcp-server
#   ./install-mcp.sh /home/user/Downloads/my-mcp-server.zip
#   ./install-mcp.sh /home/user/Code/my-mcp-server --name custom-name

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVERS_DIR="$SCRIPT_DIR/backend/mcp/servers"
CONFIG_FILE="$SCRIPT_DIR/backend/config/mcp_servers.toml"

# ------------------------------------------------------------------ helpers
die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[install-mcp] $*"; }

require_cmd() {
  command -v "$1" &>/dev/null || die "'$1' is required but not installed."
}

# ------------------------------------------------------------------ args
SOURCE="${1:-}"
CUSTOM_NAME="${3:-}"  # --name value (arg 3 when arg 2 is --name)

[[ $# -ge 1 ]] || die "Usage: $0 <github-url-or-path> [--name <name>]"
[[ "${2:-}" == "--name" && -n "${3:-}" ]] && CUSTOM_NAME="$3"

# ------------------------------------------------------------------ derive name
if [[ -z "$CUSTOM_NAME" ]]; then
  # Strip trailing .git and take the last path segment
  CUSTOM_NAME=$(basename "$SOURCE" .git)
  CUSTOM_NAME=$(basename "$CUSTOM_NAME" .zip)
fi

INSTALL_DIR="$SERVERS_DIR/$CUSTOM_NAME"

info "Installing MCP server '$CUSTOM_NAME' from: $SOURCE"
info "Destination: $INSTALL_DIR"

# ------------------------------------------------------------------ obtain source
mkdir -p "$SERVERS_DIR"

if [[ "$SOURCE" == http* ]]; then
  require_cmd git
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Directory exists, pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only
  else
    info "Cloning..."
    git clone "$SOURCE" "$INSTALL_DIR"
  fi
elif [[ "$SOURCE" == *.zip ]]; then
  require_cmd unzip
  info "Extracting zip..."
  TMP_DIR=$(mktemp -d)
  unzip -q "$SOURCE" -d "$TMP_DIR"
  # Find the actual content (zip may have a top-level folder)
  INNER=$(ls "$TMP_DIR")
  INNER_COUNT=$(echo "$INNER" | wc -l)
  if [[ "$INNER_COUNT" -eq 1 && -d "$TMP_DIR/$INNER" ]]; then
    mv "$TMP_DIR/$INNER" "$INSTALL_DIR"
  else
    mv "$TMP_DIR" "$INSTALL_DIR"
  fi
elif [[ -d "$SOURCE" ]]; then
  if [[ "$SOURCE" == "$INSTALL_DIR" ]]; then
    info "Source is already at destination, skipping copy."
  else
    info "Copying from local path..."
    cp -r "$SOURCE" "$INSTALL_DIR"
  fi
else
  die "Source '$SOURCE' is not a URL, zip file, or directory."
fi

# ------------------------------------------------------------------ detect type & install deps
RUNTIME=""
ENTRY_POINT=""

if [[ -f "$INSTALL_DIR/package.json" ]]; then
  require_cmd node
  require_cmd npm
  RUNTIME="node"
  info "Detected Node.js project, running npm install..."
  (cd "$INSTALL_DIR" && npm install --silent)
  # Determine entry point from package.json
  if command -v node &>/dev/null; then
    ENTRY_POINT=$(node -e "const p=require('./package.json'); console.log(p.main||p.bin&&Object.values(p.bin)[0]||'index.js')" 2>/dev/null || echo "index.js")
  else
    ENTRY_POINT="index.js"
  fi
  COMMAND="node $INSTALL_DIR/$ENTRY_POINT"

elif [[ -f "$INSTALL_DIR/pyproject.toml" || -f "$INSTALL_DIR/requirements.txt" || -f "$INSTALL_DIR/setup.py" ]]; then
  VENV_DIR="$SCRIPT_DIR/.venv"
  RUNTIME="python"
  info "Detected Python project, installing into .venv..."
  if [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
    "$VENV_DIR/bin/pip" install -e "$INSTALL_DIR" --quiet
  else
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
  fi
  # Look for a server.py or __main__.py as entry point
  if [[ -f "$INSTALL_DIR/server.py" ]]; then
    ENTRY_POINT="server.py"
  elif [[ -f "$INSTALL_DIR/__main__.py" ]]; then
    ENTRY_POINT="__main__.py"
  else
    ENTRY_POINT=$(find "$INSTALL_DIR" -maxdepth 1 -name "*.py" | head -1 | xargs basename 2>/dev/null || echo "server.py")
  fi
  COMMAND="$VENV_DIR/bin/python $INSTALL_DIR/$ENTRY_POINT"

else
  info "WARNING: Could not detect project type (no package.json or requirements.txt found)."
  info "You will need to manually configure the command in $CONFIG_FILE"
  COMMAND="# TODO: set command for $CUSTOM_NAME"
  RUNTIME="unknown"
fi

# ------------------------------------------------------------------ update config
mkdir -p "$(dirname "$CONFIG_FILE")"
touch "$CONFIG_FILE"

# Check if already registered
if grep -q "name = \"$CUSTOM_NAME\"" "$CONFIG_FILE" 2>/dev/null; then
  info "Server '$CUSTOM_NAME' already registered in $CONFIG_FILE, updating command..."
  # Replace the command line for this server (simple sed approach)
  sed -i "/name = \"$CUSTOM_NAME\"/,/^\[\[/{s|command = .*|command = \"$COMMAND\"|}" "$CONFIG_FILE"
else
  info "Registering in $CONFIG_FILE..."
  cat >> "$CONFIG_FILE" << TOML

[[mcp_servers]]
name = "$CUSTOM_NAME"
runtime = "$RUNTIME"
command = "$COMMAND"
transport = "stdio"
enabled = true
TOML
fi

# ------------------------------------------------------------------ done
info ""
info "✓ MCP server '$CUSTOM_NAME' installed successfully."
info ""
info "Next steps:"
info "  1. Review the entry in $CONFIG_FILE"
info "  2. Restart OpenCowork: ./run.sh"
info "  3. The server's tools will appear automatically in the agent's tool list."
info ""
if [[ "$RUNTIME" == "unknown" ]]; then
  info "  ⚠ You need to set the 'command' field in $CONFIG_FILE manually."
fi
