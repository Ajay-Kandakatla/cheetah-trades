#!/usr/bin/env bash
# uninstall.sh — remove the dev.pounce.autoupdate LaunchAgent.
set -euo pipefail

LABEL="dev.pounce.autoupdate"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [[ -f "$PLIST" ]]; then
    launchctl bootout "$DOMAIN" "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "removed $PLIST"
else
    echo "no plist at $PLIST (already uninstalled)"
fi
