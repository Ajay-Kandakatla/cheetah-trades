#!/usr/bin/env bash
# Build the Pounce Web Push prototype as a proper .app bundle and launch it.
# Bundle ID matters: macOS keys notification permission grants by bundle ID,
# so a loose `swiftc` executable would not behave the same as a real app.
#
# Usage: ./build-and-run.sh
#
# After it launches:
#   1. Log in via Google OAuth in the window
#   2. Click "Run probe" in the top toolbar
#   3. Click "Open log" to inspect ~/Desktop/pounce-probe.log

set -euo pipefail

cd "$(dirname "$0")"

APP="Pounce.app"
EXE="$APP/Contents/MacOS/Pounce"
RES="$APP/Contents/Resources"
PLIST="$APP/Contents/Info.plist"

# Kill any previously-launched instance so the new bundle is what runs.
# `open` won't relaunch an app that's already running under the same bundle
# id — it just activates it, leaving you with a stale binary + Info.plist.
pkill -x Pounce 2>/dev/null || true
sleep 0.4

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$RES"
cp Info.plist "$PLIST"

echo "==> Compiling Pounce.swift"
swiftc -O \
    -target arm64-apple-macos13.0 \
    -framework Cocoa \
    -framework WebKit \
    -o "$EXE" \
    Pounce.swift

# Strip quarantine so first-launch doesn't block the unsigned bundle.
xattr -cr "$APP" || true

echo "==> Launching $APP"
open "$APP"

LOG="$HOME/Desktop/pounce-probe.log"
echo "==> Tailing $LOG (Ctrl-C to stop tailing; app keeps running)"
sleep 1
touch "$LOG"
exec tail -F "$LOG"
