# 🎬 Replays — where the videos live and how the api sees them (2026-11-17)

Ajay 2026-11-17, verbatim: **"Can you store the videos in to the app please"**

**Verdict: the videos stay on the host disk; the api gets two READ-ONLY bind mounts. Nothing is copied into the image, Mongo or git.**

## The host folder (outside the repo, never in git)

- Root `/Users/ajay/clinet-test/eod-audits/replays/` — written ONLY by `run.sh` on the host (nightly).
- `videos/<YYYY-MM-DD>/<name>.mp4` + sidecar `<name>.json`. About **1.0 GB** on 2026-11-17, growing ~170 MB a night.
- `rs_potentials/ledger.csv` (the 🎾 Reversal Squeeze tracker; `<date>.md` beside it is prose and is not served). Descriptive — UNMEASURED, not an edge.
- `videos/` root also holds `jobs.json`, `run_log.tsv` and two study reels; the listing engine never serves them (backend doc `replays_tab_2026_11_17.md`).
- run.sh writes `<name>.part.mp4` then `mv`s it to `<name>.mp4`; the sidecar can appear first. Only the full-session window (`04:00-20:00 ET`, his 11-16 rule) is ever listed.

## The mount (`docker-compose.yml`, service `api` only)

```yaml
    environment:
      REPLAYS_DIR: /data/replays
    volumes:
      - ../eod-audits/replays/videos:/data/replays/videos:ro
      - ../eod-audits/replays/rs_potentials:/data/replays/rs_potentials:ro
```

- **READ-ONLY (`:ro`)** — the api lists and streams; it can never delete or rewrite a video.
- **Api only** — `cron`, `frontend`, `mongo`, `oauth2-proxy` get nothing.
- `REPLAYS_DIR` equals the backend default `chart_maps/replays/constants.py ROOT_DEFAULT` (`/data/replays`).
- **Why relative `../eod-audits`:** compose resolves a relative bind against the compose file's folder. Every tree that runs compose — `cheetah-market-app` (PRIMARY), `cheetah-deploy`, `.wt-*` — is a sibling of `eod-audits` under the same parent, so the same two lines resolve to the same host folder from all of them. No absolute `/Users/...` path goes in the file.
- `/Users` is already shared with the Docker VM (the existing `./backend/fidelity` and `oauth2-emails.txt` binds resolve there).

Read-only proof from the worktree, 2026-11-17 (`docker compose -f docker-compose.yml config --no-interpolate`; plain `config` stops on the worktree's missing `backend/.env`):

```
read_only: true
source: /Users/ajay/clinet-test/eod-audits/replays/videos
target: /data/replays/videos
read_only: true
source: /Users/ajay/clinet-test/eod-audits/replays/rs_potentials
target: /data/replays/rs_potentials
```

Compose sets `create_host_path: true` on short-form binds: if a host folder were missing, Docker would create it empty. Both exist today.

## Pinned by

`backend/tests/test_replays_compose_2026_11_17.py` — both binds on `api`, both `:ro`, both under `../eod-audits/replays/`; `REPLAYS_DIR == ROOT_DEFAULT` (falls back to the literal `/data/replays` until the backend package lands). NEGATIVES: no replays mount or env on `cron` / `frontend` / any other service, no replays bind `rw` or mode-less, no `/Users` literal in the file; each checker is also run against a mutated copy of the file and must fail.

## Deploy precondition (HIS CALL #13)

`deploy-cheetah-main.sh` BUILDS images from `cheetah-deploy` but RECREATES containers with `docker compose -f "$PRIMARY/docker-compose.yml" … up -d --force-recreate --no-build`, `PRIMARY=/Users/ajay/clinet-test/cheetah-market-app`. **The live api gets the mount only if PRIMARY's working-copy `docker-compose.yml` carries these lines.** On 2026-11-17 PRIMARY is on `fix/admintodos-email-leak` with an uncommitted compose edit. Before the deploy:

```bash
git -C /Users/ajay/clinet-test/cheetah-market-app diff origin/main -- docker-compose.yml
```

must print nothing. Getting it there is a git write in his main tree — his call. Without it the api deploys with no mount and the tab answers its `no_folder` sentence (safe, but empty).

After the deploy, check the mount, not the script's "Done" line:

```bash
docker inspect cheetah-market-app-api-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} rw={{.RW}}{{"\n"}}{{end}}'
```

→ the two replays lines with `rw=false`.

## The path to the phone: nginx and Cloudflare

- nginx (`frontend/nginx.conf` `location /api/`) proxies to `api:8000` with `proxy_buffering off` and `proxy_cache off`; no `gzip` directive; the static-file regex does not match `.mp4`. `Range` passes through.
- The api's `GZipMiddleware(minimum_size=1024)` would gzip a partial over 1 KB and corrupt it; the video response carries `Content-Encoding: identity` (backend doc).
- **Cloudflare sits in front** (`server: cloudflare`, `cf-cache-status: DYNAMIC` on the live site). `.mp4` is on Cloudflare's default cacheable list: a cached 200 would reach anyone with the URL without passing the owner gate. The video response carries `Cache-Control: private, no-transform`, which Cloudflare does not cache. Edge check after deploy: an unauthenticated `curl -sI` of a video URL must answer 401/404, never 200/206, and `cf-cache-status` must never be `HIT`.
- The api port stays loopback-only (`127.0.0.1:8000`).

## Rollback

Delete the two `../eod-audits/replays/...:ro` lines (and `REPLAYS_DIR`) from `docker-compose.yml`, then `./deploy-cheetah-main.sh api`. The host folder is untouched either way.
