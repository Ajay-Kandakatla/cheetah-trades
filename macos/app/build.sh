#!/usr/bin/env bash
# Build Pounce.app — a proper bundled macOS app with bundle id com.pounce.mac.
#
# Usage:
#   ./build.sh          → build into ./Pounce.app, launch it (kills running instance first)
#   ./build.sh install  → also copy to /Applications/Pounce.app
#   ./build.sh clean    → remove ./Pounce.app and exit
#
# Logs end up at ~/Library/Logs/Pounce/pounce.log — `tail -F` it to watch.

set -euo pipefail
cd "$(dirname "$0")"

ACTION="${1:-run}"
APP="Pounce.app"

if [[ "$ACTION" == "clean" ]]; then
    rm -rf "$APP"
    echo "removed $APP"
    exit 0
fi

# Kill running instance so the rebuilt binary is what launches.
pkill -x Pounce 2>/dev/null || true
sleep 0.4

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp Info.plist "$APP/Contents/Info.plist"

# Build/refresh the app icon if either the source code changed or the
# packaged .icns is missing.
if [[ ! -f AppIcon.icns || icon/generate.swift -nt AppIcon.icns ]]; then
    echo "==> Building AppIcon.icns"
    (cd icon && ./build.sh) > /dev/null
fi
cp AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"

echo "==> Compiling Pounce.swift"
swiftc -O \
    -target arm64-apple-macos13.0 \
    -framework Cocoa \
    -framework WebKit \
    -framework UserNotifications \
    -framework ServiceManagement \
    -o "$APP/Contents/MacOS/Pounce" \
    Pounce.swift

# Strip quarantine attrs so unsigned bundle launches without right-click → Open.
xattr -cr "$APP" || true

if [[ "$ACTION" == "install" ]]; then
    echo "==> Installing to /Applications"
    rm -rf /Applications/Pounce.app
    cp -R "$APP" /Applications/Pounce.app
    APP="/Applications/Pounce.app"
fi

echo "==> Launching $APP"
open "$APP"

LOG="$HOME/Library/Logs/Pounce/pounce.log"
mkdir -p "$(dirname "$LOG")"
touch "$LOG"
echo "==> Tailing $LOG (Ctrl-C stops tail; app keeps running)"
sleep 1
exec tail -F "$LOG"
