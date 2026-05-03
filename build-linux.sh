#!/usr/bin/env bash
# build-linux.sh — Build OpenCowork as a self-contained Linux AppImage and .deb
# Run from the repo root. Requires: python3, npm, fakeroot (for .deb), curl.
# Output: dist/OpenCowork-x86_64.AppImage  and  dist/opencowork_<version>_amd64.deb

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${OPENCOWORK_VERSION:-0.1.0}"
DIST="$REPO_ROOT/dist"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   OpenCowork Linux build  v$VERSION     ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ── 1. Frontend ──────────────────────────────────────────────────────────────
echo "[1/6] Building frontend..."
cd "$REPO_ROOT/frontend"
npm install --silent
npm run build
cd "$REPO_ROOT"
echo "      Frontend built → frontend/dist/"

# ── 2. Python deps snapshot ───────────────────────────────────────────────────
echo "[2/6] Installing Python dependencies..."
python3 -m venv "$DIST/venv" --clear
"$DIST/venv/bin/pip" install --quiet --upgrade pip
"$DIST/venv/bin/pip" install --quiet -r backend/requirements.txt
echo "      Python venv ready → dist/venv/"

# ── 3. Assemble AppDir ────────────────────────────────────────────────────────
echo "[3/6] Assembling AppDir..."
APPDIR="$DIST/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib/opencowork"

# Copy source (excluding dev artifacts)
rsync -a --exclude='.venv' --exclude='.git' --exclude='node_modules' \
      --exclude='dist' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='frontend/node_modules' \
      "$REPO_ROOT/" "$APPDIR/usr/lib/opencowork/"

# Copy built frontend dist
cp -r "$REPO_ROOT/frontend/dist" "$APPDIR/usr/lib/opencowork/frontend/dist"

# Copy the venv
cp -r "$DIST/venv" "$APPDIR/usr/lib/opencowork/.venv"

# Desktop + icon
cp "$REPO_ROOT/opencowork.desktop" "$APPDIR/opencowork.desktop"
cp "$REPO_ROOT/opencowork.desktop" "$APPDIR/usr/share/applications/opencowork.desktop" 2>/dev/null || true

# Create a placeholder icon if none exists
if [ ! -f "$REPO_ROOT/opencowork.png" ]; then
  # Minimal 64x64 PNG (solid teal square — replace with real icon)
  python3 - <<'PYEOF'
import struct, zlib, base64
# 1x1 teal pixel PNG, scaled conceptually — minimal valid PNG
data = base64.b64decode(
  "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAABmJLR0QA/wD/AP+gvaeTAAAA"
  "AAAASUVORK5CYII="
)
import pathlib; pathlib.Path("opencowork.png").write_bytes(data)
PYEOF
fi
cp "$REPO_ROOT/opencowork.png" "$APPDIR/opencowork.png"

# AppRun launcher
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
APPLIB="$HERE/usr/lib/opencowork"
export PATH="$APPLIB/.venv/bin:$PATH"
export PYTHONPATH="$APPLIB"

# Auto-start Ollama if not running
if command -v ollama &>/dev/null && ! pgrep -x ollama &>/dev/null; then
  ollama serve &>/tmp/ollama.log &
  sleep 1
fi

cd "$APPLIB"
exec "$APPLIB/.venv/bin/python" -m backend.main "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "      AppDir assembled → dist/AppDir/"

# ── 4. Download appimagetool if needed ────────────────────────────────────────
echo "[4/6] Checking appimagetool..."
APPIMAGETOOL="$DIST/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
  echo "      Downloading appimagetool..."
  curl -sL "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
       -o "$APPIMAGETOOL"
  chmod +x "$APPIMAGETOOL"
fi

# ── 5. Build AppImage ─────────────────────────────────────────────────────────
echo "[5/6] Building AppImage..."
ARCH=x86_64 "$APPIMAGETOOL" --no-appstream "$APPDIR" "$DIST/OpenCowork-x86_64.AppImage" 2>&1 | sed 's/^/      /'
echo "      ✓  dist/OpenCowork-x86_64.AppImage"

# ── 6. Build .deb ─────────────────────────────────────────────────────────────
echo "[6/6] Building .deb package..."
DEB_ROOT="$DIST/deb"
DEB_NAME="opencowork_${VERSION}_amd64"
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_ROOT/$DEB_NAME/DEBIAN"
mkdir -p "$DEB_ROOT/$DEB_NAME/opt/opencowork"
mkdir -p "$DEB_ROOT/$DEB_NAME/usr/share/applications"
mkdir -p "$DEB_ROOT/$DEB_NAME/usr/local/bin"

# Copy payload (same as AppDir but to /opt/opencowork)
rsync -a --exclude='.venv' --exclude='.git' --exclude='node_modules' \
      --exclude='dist' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='frontend/node_modules' \
      "$REPO_ROOT/" "$DEB_ROOT/$DEB_NAME/opt/opencowork/"
cp -r "$REPO_ROOT/frontend/dist" "$DEB_ROOT/$DEB_NAME/opt/opencowork/frontend/dist"
cp -r "$DIST/venv" "$DEB_ROOT/$DEB_NAME/opt/opencowork/.venv"
cp "$REPO_ROOT/opencowork.png" "$DEB_ROOT/$DEB_NAME/opt/opencowork/opencowork.png"

# Launcher script
cat > "$DEB_ROOT/$DEB_NAME/usr/local/bin/opencowork" << 'LAUNCHER'
#!/bin/bash
APP=/opt/opencowork

# Auto-start Ollama if available and not running
if command -v ollama &>/dev/null && ! pgrep -x ollama &>/dev/null; then
  ollama serve &>/tmp/ollama.log &
  sleep 1
fi

cd "$APP"
exec "$APP/.venv/bin/python" -m backend.main "$@"
LAUNCHER
chmod +x "$DEB_ROOT/$DEB_NAME/usr/local/bin/opencowork"

# .desktop file (pointing to installed location)
sed "s|/opt/opencowork/opencowork|opencowork|g" \
    "$REPO_ROOT/opencowork.desktop" \
    > "$DEB_ROOT/$DEB_NAME/usr/share/applications/opencowork.desktop"

# DEBIAN/control
cat > "$DEB_ROOT/$DEB_NAME/DEBIAN/control" << CONTROL
Package: opencowork
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.11)
Recommends: ollama
Maintainer: OpenCowork <noreply@opencowork.local>
Description: Local-first AI co-working agent
 OpenCowork connects to Ollama (or any OpenAI-compatible provider) and exposes
 a React chat UI with tool use, task scheduling, personas, skills, and MCP
 server integration.
CONTROL

# Post-install: update desktop db
cat > "$DEB_ROOT/$DEB_NAME/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
update-desktop-database /usr/share/applications/ 2>/dev/null || true
POSTINST
chmod 0755 "$DEB_ROOT/$DEB_NAME/DEBIAN/postinst"

if command -v fakeroot &>/dev/null && command -v dpkg-deb &>/dev/null; then
  fakeroot dpkg-deb --build "$DEB_ROOT/$DEB_NAME" "$DIST/${DEB_NAME}.deb"
  echo "      ✓  dist/${DEB_NAME}.deb"
else
  echo "      ⚠  fakeroot/dpkg-deb not found — skipping .deb (install with: sudo apt install fakeroot dpkg)"
fi

echo ""
echo "  ✓  Build complete!"
echo ""
echo "  AppImage (portable, no install):  dist/OpenCowork-x86_64.AppImage"
echo "  Debian package:                   dist/${DEB_NAME}.deb"
echo ""
echo "  To install the .deb:"
echo "    sudo apt install ./dist/${DEB_NAME}.deb"
echo ""
echo "  To install the AppImage:"
echo "    cp dist/OpenCowork-x86_64.AppImage ~/Applications/"
echo "    ~/Applications/OpenCowork-x86_64.AppImage &"
echo ""
