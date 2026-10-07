# Cheetah SEPA launchd jobs

Two macOS launchd agents drive the automated SEPA pipeline on your laptop.

| File | When | What it does |
|---|---|---|
| `com.cheetah.sepa.scan.plist` | **Mon-Fri 5:00pm** local | Full universe scan → `~/.cheetah/scans/latest.json` |
| `com.cheetah.sepa.brief.plist` | **Mon-Fri 8:30am** local | Morning brief from latest scan → `~/.cheetah/scans/brief.json` |
| `com.cheetah.docker-watchdog.plist` | **every 2 min** | Docker forwarder / backend / battery → ops push (`ops/docker_watchdog.py`, 2026-10-06) |

## Install

```bash
cp launchd/com.cheetah.sepa.scan.plist  ~/Library/LaunchAgents/
cp launchd/com.cheetah.sepa.brief.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.cheetah.sepa.scan.plist
launchctl load ~/Library/LaunchAgents/com.cheetah.sepa.brief.plist
```

### Docker watchdog (2026-10-06)

Runs from the deploy worktree, so install it after a main deploy. Runbook: `ops/README.md`.

```bash
mkdir -p ~/.cheetah/watchdog
chmod 700 ~/.cheetah/watchdog
cp /Users/ajay/clinet-test/cheetah-deploy/launchd/com.cheetah.docker-watchdog.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cheetah.docker-watchdog.plist
```

Uninstall:

```bash
launchctl bootout gui/$(id -u)/com.cheetah.docker-watchdog
rm ~/Library/LaunchAgents/com.cheetah.docker-watchdog.plist
```

## Verify

```bash
launchctl list | grep cheetah
# trigger a one-off run immediately:
launchctl start com.cheetah.sepa.scan
tail -f ~/.cheetah/sepa-scan.log
```

## Manual one-off

```bash
cd backend
./.venv/bin/python -m sepa.cli scan          # or --no-catalyst for speed
./.venv/bin/python -m sepa.cli brief
```

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.cheetah.sepa.scan.plist
launchctl unload ~/Library/LaunchAgents/com.cheetah.sepa.brief.plist
rm ~/Library/LaunchAgents/com.cheetah.sepa.{scan,brief}.plist
```

## Polygon upgrade

Add `POLYGON_API_KEY` to `backend/.env`. Catalyst + insider modules will
auto-route through Polygon (higher quality news/earnings, faster). No code
changes required.
