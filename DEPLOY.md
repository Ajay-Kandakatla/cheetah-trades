# Cheetah / Pounce — Deploy Guide

Backend + cron + Mongo run as Docker containers on the **Mac mini**. The
**native macOS Pounce.app** runs on the **laptop**. They talk through HTTPS
+ SSE via Tailscale Funnel at `https://ajays-macbook-pro.tailb3dc79.ts.net`.

| Where you run it | Touches |
| --- | --- |
| Mac mini (SSH or in person) | `docker compose` for `api`, `cron`, `frontend`, `mongo` |
| Laptop (Pounce.app build) | `macos/app/build.sh` — compiles Swift, drops the bundle in `/Applications` |
| Either | `git pull`, env vars |

---

## 1. Quick deploys (the commands you actually run day-to-day)

### 1a. Full backend redeploy (most common)

After any change in `backend/`:

```sh
cd /Users/ajay/clinet-test/cheetah-market-app
git add backend/ macos/ && git commit -m "<message>" && git push origin main
ssh ajay@ajays-mac-mini "cd ~/cheetah-market-app \
  && git pull --ff-only \
  && docker compose build api cron \
  && docker compose up -d api cron"
```

### 1b. Cron-only change (touched `backend/crontab`)

```sh
ssh ajay@ajays-mac-mini "cd ~/cheetah-market-app \
  && git pull --ff-only \
  && docker compose build cron \
  && docker compose up -d cron \
  && docker compose logs --tail 50 cron"
```

### 1c. Frontend-only change (touched `frontend/`)

```sh
ssh ajay@ajays-mac-mini "cd ~/cheetah-market-app \
  && git pull --ff-only \
  && docker compose build frontend \
  && docker compose up -d frontend"
```

### 1d. macOS Pounce.app — laptop side, no Docker

```sh
cd /Users/ajay/clinet-test/cheetah-market-app/macos/app
./build.sh install
killall Dock
```

To pick up backend changes inside the running Pounce.app: ⌘Q, relaunch.

### 1e. Both at once (backend + Pounce.app)

```sh
cd /Users/ajay/clinet-test/cheetah-market-app
git add backend/ macos/ && git commit -m "<message>" && git push origin main

ssh ajay@ajays-mac-mini "cd ~/cheetah-market-app \
  && git pull --ff-only \
  && docker compose build api cron frontend \
  && docker compose up -d api cron frontend"

cd macos/app && ./build.sh install && killall Dock
```

---

## 2. One-time setup

### 2a. Mac mini — Docker stack

```sh
docker version && docker compose version

git clone <repo> ~/cheetah-market-app
cd ~/cheetah-market-app
cp backend/.env.example backend/.env

docker compose --profile oauth build
docker compose --profile oauth up -d
```

`backend/.env` needs (no quotes):

```
MASSIVE_API_KEY=...
FINNHUB_API_KEY=...
PRICE_PROVIDER=massive
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
OAUTH2_PROXY_CLIENT_ID=...
OAUTH2_PROXY_CLIENT_SECRET=...
OAUTH2_PROXY_COOKIE_SECRET=<32-byte url-safe base64>
OAUTH2_PROXY_REDIRECT_URL=https://ajays-macbook-pro.tailb3dc79.ts.net/oauth2/callback
DEFAULT_USER_EMAIL=ajaykandakatla@gmail.com
HOUSE_OWNER_EMAILS=ajaykandakatla@gmail.com,vineetha@example.com
```

Enable Docker Desktop → Settings → "Start at login" so the stack survives
reboots. Containers have `restart: unless-stopped`.

### 2b. Laptop — Pounce.app

```sh
cd /Users/ajay/clinet-test/cheetah-market-app/macos/app
./build.sh install
open /Applications/Pounce.app
```

First launch: sign in via Google in the WebView; grant notification
permission when macOS asks (or System Settings → Notifications → Pounce →
Allow). Without it the Mac SSE channel silently no-ops.

### 2c. Laptop — auto-update LaunchAgent (optional)

```sh
cd /Users/ajay/clinet-test/cheetah-market-app/macos/autoupdate
./install.sh
```

Default: checks once per login. `INTERVAL=86400 ./install.sh` to also poll
once a day. `./uninstall.sh` to remove.

---

## 3. What needs rebuilding when

| Change | Build | Restart | Why |
| --- | --- | --- | --- |
| `backend/main.py` | `docker compose build api` | `docker compose up -d api` | API server |
| `backend/sepa/*`, `backend/push/*`, `backend/food/*` etc. | `docker compose build api cron` | `docker compose up -d api cron` | Both API + cron import these |
| `backend/crontab` | `docker compose build cron` | `docker compose up -d cron` | supercronic schedule |
| `backend/requirements.txt` | `docker compose build api cron` | `docker compose up -d api cron` | Pip layer invalidated |
| `frontend/src/**` | `docker compose build frontend` | `docker compose up -d frontend` | nginx serves built assets |
| `frontend/public/sw.js` | `docker compose build frontend` | `docker compose up -d frontend` + Reload + check `Application → Service Workers` | New SW must take over |
| `docker-compose.yml` | `docker compose build` | `docker compose up -d` | Recreates with new env/ports |
| `macos/app/Pounce.swift` | `./build.sh install` (laptop) | ⌘Q + relaunch | Native shell |
| `macos/app/icon/generate.swift` | `./build.sh install` (laptop) | `killall Dock` | Dock + Finder icon cache |
| `macos/app/Info.plist` | `./build.sh install` (laptop) | ⌘Q + relaunch | Bundle metadata |

---

## 4. Verify after deploy

### Backend health

```sh
ssh ajay@ajays-mac-mini bash -lc '"
  cd ~/cheetah-market-app
  docker compose ps
  docker compose logs --tail 20 api
  docker compose logs --tail 20 cron
"'
```

External smoke test:

```sh
curl -sI https://ajays-macbook-pro.tailb3dc79.ts.net/api/health
curl -s  https://ajays-macbook-pro.tailb3dc79.ts.net/api/push/public-key | head
```

### Cron schedule loaded

```sh
ssh ajay@ajays-mac-mini "docker compose -f ~/cheetah-market-app/docker-compose.yml exec -T cron cat /app/crontab | head -30"
```

### Juggernaut detector — one-shot dry run

```sh
ssh ajay@ajays-mac-mini "docker compose -f ~/cheetah-market-app/docker-compose.yml exec -T cron python -m sepa.cli juggernauts --dry-run"
```

Expected:

```
JUGGERNAUT — N current · 0 new · pushed=0 (2026-05-08)
```

Force a real push:

```sh
ssh ajay@ajays-mac-mini "docker compose -f ~/cheetah-market-app/docker-compose.yml exec -T cron python -m sepa.cli juggernauts --force"
```

### Mac SSE channel live

```sh
ls -la ~/Library/Application\ Support/Pounce/device_id
tail -n 50 ~/Library/Logs/Pounce/pounce.log | grep '\[sse\]'
```

End-to-end push test:

1. Open `https://ajays-macbook-pro.tailb3dc79.ts.net/notifications`
2. Find the row with `kind: mac` and your hostname label
3. Click that row's **Test** button (calls `/push/mac-test`)
4. Notification appears in Notification Center within ~200ms

---

## 5. Common operations

### Trigger a SEPA fast-scan immediately

```sh
docker compose exec cron python -m sepa.cli fast-scan
```

### Send a test push to one subscription

```sh
curl -s https://ajays-macbook-pro.tailb3dc79.ts.net/api/push/subscriptions
curl -X POST https://ajays-macbook-pro.tailb3dc79.ts.net/api/push/test \
  -H 'Content-Type: application/json' \
  -d '{"endpoint":"<endpoint-from-above>"}'
```

### Tail cron output

```sh
docker compose logs -f cron
```

### Tail Pounce.app native logs (laptop)

```sh
tail -F ~/Library/Logs/Pounce/pounce.log
```

### Force the laptop auto-updater to check now

```sh
~/clinet-test/cheetah-market-app/macos/autoupdate/check-and-build.sh
```

---

## 6. Rollback

### Backend (Docker compose)

```sh
ssh ajay@ajays-mac-mini "cd ~/cheetah-market-app \
  && git log --oneline -5 \
  && git reset --hard <prior-sha> \
  && docker compose build api cron \
  && docker compose up -d api cron"
```

### macOS app — back to a saved binary

```sh
mv /Applications/Pounce.app /Applications/Pounce.app.bad
cp -R ~/Pounce.app.backup /Applications/Pounce.app
killall Dock && open /Applications/Pounce.app
```

### macOS app — rebuild from a prior commit

```sh
cd /Users/ajay/clinet-test/cheetah-market-app
git log --oneline -- macos/app/
git checkout <sha> -- macos/app/
cd macos/app && ./build.sh install
```

### Mongo — restore from backup

```sh
docker compose stop api cron
docker run --rm -v cheetah-market-app_mongo-data:/d -v $PWD:/b alpine \
  sh -c 'rm -rf /d/* && tar xzf /b/mongo-<date>.tgz -C /d'
docker compose up -d api cron
```

---

## 7. Env vars worth knowing

| Var | Default | Controls |
| --- | --- | --- |
| `ALERT_SCOPE` | `top5_watchlist` | Push gating: `top5_watchlist`, `watchlist`, `universe` |
| `ALERT_TOP_N` | `5` | How many SEPA candidates count as "top" |
| `JUGGER_UD_VOL_MIN` | `1.5` | Juggernaut accumulation threshold |
| `JUGGER_TODAY_VOL_MULT` | `1.2` | Juggernaut today-volume threshold |
| `JUGGER_RS_CLIMB_MIN` | `5` | Juggernaut RS-climb threshold |
| `JUGGER_SCORE_CLIMB_MIN` | `3` | Juggernaut score-climb threshold |
| `JUGGER_LOOKBACK_DAYS` | `5` | Juggernaut momentum window |
| `JUGGER_DAY_PCT_BURST` | `3.0` | Juggernaut intraday-burst threshold |
| `MAC_OUTBOX_POLL_MS` | `200` | `mac_stream` drain interval |
| `DEFAULT_USER_EMAIL` | `ajay@example.com` | Fallback owner for unauthed calls (cron) |
| `OAUTH2_REQUIRED` | `0` | Set `1` to 401 unauthed requests instead of falling back |
| `SEPA_UNIVERSE_MODE` | `russell1000` | Default for scan/research-refresh/vcp-watch |

---

## 8. Persistence + backup

| Volume | Holds | Backup |
| --- | --- | --- |
| `cheetah-market-app_mongo-data` | scan history, subscriptions, alerts, juggernaut state, food/house/todos | `docker run --rm -v cheetah-market-app_mongo-data:/d -v $PWD:/b alpine tar czf /b/mongo-$(date +%F).tgz -C /d .` |
| `cheetah-market-app_cheetah-scans` | `~/.cheetah/scans/latest.json`, `watchlist.json` | Same `tar` pattern; small enough to snapshot frequently |
| `~/Library/Application Support/Pounce/device_id` (laptop) | stable Mac device UUID used by `/push/mac-stream` | Plain text — copy if re-imaging the laptop |

---

## 9. Troubleshooting

| Symptom | Where to look | Likely cause |
| --- | --- | --- |
| WebView shows "Could not connect" | `curl -sI https://...ts.net/` from laptop | oauth2-proxy 302ing to `http://`; WKWebView handler upgrades `*.ts.net` automatically — check the build is current |
| No Mac notifications even with stream live | System Settings → Notifications → Pounce | Permission set to None |
| Juggernaut cron runs, nothing fires | `docker compose logs cron \| grep juggernaut` | Watchlist empty, or no `scan_runs` in last `LOOKBACK_DAYS` |
| Web Push works on iPhone but not Mac | `tail -F ~/Library/Logs/Pounce/pounce.log` | SSE disconnected, cookie expired, or app force-quit |
| Icon didn't change after rebuild | `killall Dock; killall Finder` | Icon cache stale |
| `git pull --ff-only` fails on the mini | SSH in, `git status` | Local edit drift — resolve before re-running |
| oauth2-proxy redirects to `http://...` | `curl -sI https://...ts.net/` | Add `OAUTH2_PROXY_FORCE_HTTPS=true` to `backend/.env` (see spawned task) |

Log locations:

```
~/Library/Logs/Pounce/pounce.log          # native Mac app (laptop)
~/Library/Logs/Pounce/autoupdate.log      # laptop auto-update LaunchAgent
docker compose logs api                    # FastAPI requests
docker compose logs cron                   # SEPA scans, juggernaut, alerts
docker compose logs frontend               # nginx + oauth2 proxying
```
