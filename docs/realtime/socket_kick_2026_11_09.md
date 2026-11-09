# 📡 The socket kick — detection recipe, suspects, canary (2026-11-09)

**Status:** recipe + canary written (GG LIVE spec §3.1, WP-A). **The canary has NOT been run.** Running it is HIS
CALL #10: it opens deliberate second sockets on the prod key.

## What we see
Since 2026-11-08 ~11:00 ET the api's Massive socket has been kicked (`max_connections`, close 1008) about every
5.5 min. Before that it was 3–4/h; after, ~11/h. There were 157 kicks in 17 h, and each kick costs ≥ 30 s with no
prints.

The kick is not from cron, the `ajay-admin*` stack, any host python/uvicorn process, or another container/stack.
Only two socket clients exist in the repo: `live_feed.py`, and Finnhub (`main.py`, off when Massive is on). The dev
compose would open one if started; it is now pinned off (`MASSIVE_WS_ENABLED: "false"`, and `enabled()` refuses
`auto` on `CHEETAH_ENV=dev`).

A ~5.5 min period matches our 30 s cooldown plus a client that reconnects ~5 min after WE kick it back. That points
to either a fight with a persistent client or a connect scheduled every 5 minutes.

## Massive's documented rule (fetched 2026-11-09)
- Connections are counted **per cluster**, and every key on the account shares the allowance. Individual plans get
  ONE connection per cluster.
- On Stocks, the **older** connection is closed and the new one keeps streaming.
- After a kick, reconnecting kicks the other client.

## Detection recipe (read-only, from `live_feed_events` — written since the WP-A deploy)
1. **Inter-arrival histogram** of `kind: "status", status: "max_connections"` rows (`ts`).
2. **Phase** of each kick:
   - measured against OUR last `kind: "auth"` row: a stable ≈ 300 s means a client that fights back on a timer;
   - measured against the wall clock: kicks on `:x0` / `:x5` plus a constant mean a scheduled connect.
3. **Only with HIS CALL #10**, for one closed-day hour: set `MASSIVE_WS_KICK_COOLDOWN_SEC=600` and restart the api.
   - If the kicks stop, it is a persistent fighter.
   - If they continue on schedule, it is a scheduled job.

Nothing on our side identifies the other client.

Admin read of the timeline: `GET /live/feed-status?events=1` (last 50 rows; admins only; the key is never served).

## Suspects he can check (§7 #11)
- (a) Massive dashboard → API keys / active connections.
- (b) Any device, app, notebook, charting tool or person that has the key.
- (c) The key was printed in plaintext 2026-09-12 and never rotated.
- (d) Any other machine running a cheetah checkout or the dev compose.
- (e) Whatever started 2026-11-08 ~11:00 ET.

If the client cannot be found: **rotate the stocks key** (HIS CALL #12). That is his dashboard step, then
`backend/.env` → `./deploy-cheetah-main.sh api cron`.

## The canary — `backend/scripts/live_feed_canary.py` (NOT run)
- **Step (a):** open B and authenticate. Measure when the api's socket (A) logs `max_connections` after B's
  `auth_success`, read from the api's own timeline. Then close B cleanly.
- **Step (b):** open B and authenticate, then hard-drop the TCP connection (no close frame). Open C at once. Measure
  C's `auth_success` and first frame, and whether C is refused while B's ghost is still counted. Then close C.
- **Safety:** each step ends `CANARY_MARGIN_SEC` (5 s) before `KICK_COOLDOWN_SEC`, so the api's own reconnect lands
  after it. Steps are ≥ `CANARY_STEP_GAP_SEC` (60 s) apart. It refuses on a market day 04:00–20:05 ET unless
  `--force`. It writes nothing and never prints the key.

```bash
docker exec -i -w /app cheetah-market-app-api-1 python scripts/live_feed_canary.py --email <admin email>
```

## Canary results
_Not run — HIS CALL #10._
