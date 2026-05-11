#!/usr/bin/env bash
# install.sh — register the dev.pounce.autoupdate LaunchAgent.
#
# Default: runs once at login (laptop boot / first wake of the day). That's
# enough for a personal app where pushes are rare. No background polling
# during the day.
#
# Override with INTERVAL=<seconds> to enable recurring polling instead:
#   INTERVAL=21600 ./install.sh   # also every 6 hours
#   INTERVAL=86400 ./install.sh   # also once a day on top of login
# Or run check-and-build.sh by hand any time you push and want it now.
#
# Idempotent — re-running just reloads the agent.

set -euo pipefail
cd "$(dirname "$0")"

LABEL="dev.pounce.autoupdate"
SCRIPT_PATH="$(cd "$(dirname check-and-build.sh)" && pwd)/check-and-build.sh"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/Pounce"

[[ -x "$SCRIPT_PATH" ]] || chmod +x "$SCRIPT_PATH"
mkdir -p "$PLIST_DIR" "$LOG_DIR"

# Optional StartInterval block — only emitted if the user explicitly opts in
# via the INTERVAL env var. Default is login-only.
INTERVAL_BLOCK=""
if [[ -n "${INTERVAL:-}" ]]; then
    INTERVAL_BLOCK=$(cat <<XML
    <key>StartInterval</key>
    <integer>$INTERVAL</integer>
XML
    )
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>$SCRIPT_PATH</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
$INTERVAL_BLOCK
    <key>StandardOutPath</key>
    <string>$LOG_DIR/autoupdate.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/autoupdate.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# Modern API: bootout the old one (if any), then bootstrap the new one.
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true

echo "installed: $PLIST"
if [[ -n "${INTERVAL:-}" ]]; then
    echo "schedule:  at login + every $INTERVAL seconds"
else
    echo "schedule:  at login only (no daytime polling)"
fi
echo "log:       $LOG_DIR/autoupdate.log"
echo
echo "first run is happening now (RunAtLoad=true). Tail the log:"
echo "  tail -F $LOG_DIR/autoupdate.log"
echo
echo "to force a check any other time:"
echo "  $SCRIPT_PATH"
