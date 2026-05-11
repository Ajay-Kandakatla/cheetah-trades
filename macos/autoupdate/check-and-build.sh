#!/usr/bin/env bash
# check-and-build.sh — invoked by the dev.pounce.autoupdate LaunchAgent.
#
# Polling cycle:
#   1. git fetch origin
#   2. compare local HEAD vs origin/main
#   3. if up-to-date, exit
#   4. if local working-tree has uncommitted changes under macos/app/, skip
#      (so we never blow over your in-progress work)
#   5. fast-forward pull
#   6. rebuild + reinstall Pounce.app ONLY if macos/app/** actually changed
#      (backend / frontend / web changes don't need a Mac rebuild)
#   7. macOS notification on success or failure
#
# Designed to be safe to run on every cron tick — does nothing if there's
# nothing to do.

set -euo pipefail

REPO="/Users/ajay/clinet-test/cheetah-market-app"
LOG_DIR="$HOME/Library/Logs/Pounce"
LOG="$LOG_DIR/autoupdate.log"
mkdir -p "$LOG_DIR"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >>"$LOG"; }

cd "$REPO"

# --- 1. fetch ---
if ! git fetch origin --quiet 2>>"$LOG"; then
    log "git fetch failed — skipping cycle"
    exit 0
fi

# --- 2. compare ---
LOCAL=$(git rev-parse HEAD 2>/dev/null || echo "")
REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "")
if [[ -z "$REMOTE" || "$LOCAL" == "$REMOTE" ]]; then
    exit 0
fi

# --- 3. local-edit guard ---
if [[ -n "$(git status --porcelain macos/app/)" ]]; then
    log "macos/app/ has uncommitted edits, refusing to pull (LOCAL=$LOCAL REMOTE=$REMOTE)"
    exit 0
fi

# --- 4. detect macos changes BEFORE the pull (we can compare HEAD vs origin/main) ---
MACOS_CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE" -- macos/app/ | head)
log "remote ahead: $LOCAL → $REMOTE; macos/app/ changes: ${MACOS_CHANGED:-none}"

# --- 5. fast-forward pull ---
if ! git pull --ff-only --quiet 2>>"$LOG"; then
    log "git pull --ff-only failed (manual merge needed); aborting"
    osascript -e 'display notification "Pounce auto-update: pull failed (merge needed)" with title "Pounce" sound name "Basso"' || true
    exit 1
fi

# --- 6. conditional rebuild ---
if [[ -z "$MACOS_CHANGED" ]]; then
    log "no macos/app/ changes; nothing to rebuild (web/backend updates land via Docker)"
    exit 0
fi

log "rebuilding Pounce.app (changed: $MACOS_CHANGED)"
if (cd macos/app && ./build.sh install) >>"$LOG" 2>&1; then
    log "rebuild + install OK"
    osascript -e 'display notification "Pounce.app rebuilt. Quit + relaunch to apply." with title "Pounce auto-update" sound name "Glass"' || true
else
    log "rebuild FAILED (see above)"
    osascript -e 'display notification "Pounce auto-update: build failed. See ~/Library/Logs/Pounce/autoupdate.log" with title "Pounce" sound name "Basso"' || true
    exit 1
fi
