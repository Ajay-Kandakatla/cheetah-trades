# Cheetah — Mac mini deployment

Runs four containers: `frontend` (nginx + built SPA), `api` (FastAPI), `cron`
(supercronic running the SEPA scan + brief on weekdays), and `mongo`
(scan history). Everything is wired together by `docker-compose.yml`.

## 0. One-time setup on the mini

Install Docker Desktop for Mac (or Colima + Docker CLI). Confirm:

```sh
docker version
docker compose version
```

## 1. Clone and configure

```sh
git clone <repo> cheetah && cd cheetah/cheetah-market-app
cp backend/.env.example backend/.env   # if you don't already have one
```

`backend/.env` must contain at minimum:

```
MASSIVE_API_KEY=...
FINNHUB_API_KEY=...
PRICE_PROVIDER=massive
```

> **Rotate the Massive key first** — the previously used key was shared in chat
> and should be considered compromised.

## 2. Build and launch

```sh
docker compose build
docker compose up -d
```

Verify:

```sh
docker compose ps
curl -s http://localhost:8000/sepa/scan | head -c 200    # api
open http://localhost:5173                                # frontend
```

The frontend talks to the api through nginx's `/api/*` proxy, so the SPA works
the same whether you load it on the mini itself or from another LAN machine
(`http://<mini-host>.local:5173`).

## 3. Cron schedule

Defined in [`backend/crontab`](backend/crontab). Times are
`America/New_York` (set via `TZ` env on the cron container):

| When | Command |
| --- | --- |
| 16:30 ET, Mon–Fri | `python -m sepa.cli scan` (full scan, catalyst on) |
| 08:30 ET, Mon–Fri | `python -m sepa.cli brief` |

To trigger a run by hand:

```sh
docker compose exec cron python -m sepa.cli scan
```

To follow cron logs:

```sh
docker compose logs -f cron
```

## 4. Persistence

| Volume | Holds |
| --- | --- |
| `mongo-data` | All scan history (`scan_runs`, `candidate_snapshots`) |
| `cheetah-scans` | `~/.cheetah/scans/latest.json` shared by api + cron |

Backups: `docker run --rm -v cheetah-market-app_mongo-data:/d -v $PWD:/b alpine tar czf /b/mongo-$(date +%F).tgz -C /d .`

## 5. Updating

```sh
git pull
docker compose build
docker compose up -d
```

## 6. Auto-start on reboot

`restart: unless-stopped` on every service handles container-level restarts. To
auto-start the whole stack at boot, enable Docker Desktop's "Start at login"
setting on the mini's user account.

## 7. LAN exposure / hardening notes

- API is bound to `0.0.0.0:8000` so other LAN machines can hit it directly if
  they want raw JSON. If you only want browser access, restrict the api port
  to loopback in `docker-compose.yml` (`127.0.0.1:8000:8000`) — the frontend
  reaches it over the internal compose network either way.
- No auth is currently in front of the api. For remote access, put it behind
  Tailscale or a reverse proxy with a bearer token before exposing externally.
- Mongo is loopback-only by default.
