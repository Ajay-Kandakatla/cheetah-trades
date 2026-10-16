# 🎢 High-Beta + 🗺️ Chart Maps tape bursts — two push kinds (2026-10-14)

## The ask

> "I need a tape burst notification specific for High Beta stocks from the reselinet separately and also other tape
> bursts from the Chart Maps page"

Knob answer (K4): "High-Beta tab names + all Chart Maps names".

Ajay killed tape bursts on his phone on 2026-09-08 ("Also kill the tape burst …"). That is why `trade_flash` is not in
`OWNER_KEEP_SET`. This ask brings two NEW kinds back to his phone. `trade_flash` itself stays muted
(`test_push_owner_keepset.py`).

**Status: LIVE, owner-only, ON for him. UNMEASURED.** A tape burst describes prints, not a signal. No study in this app
measures what happens after one (`trade_flash.py`: "NOT a signal with a measured record"). Not advice.

## The two kinds

| kind | mark | watches | cap |
|---|---|---|---|
| `tape_burst_highbeta` | 🎢 | every name on the 🎢 High Beta tab, biggest drop first (`GET /chart-maps/high-beta/watch`) | `HIGHBETA_MAX_SYMBOLS = 150` # Ajay 2026-10-14 |
| `tape_burst_chartmaps` | 🗺️ | the names served on every Chart Maps tab (`chart_maps_membership`), minus the zone names ⚡ `trade_flash` watches, minus the 🎢 list; round-robin by each tab's rank | `CHARTMAPS_MAX_SYMBOLS = 150` # Ajay 2026-10-14 |

Both kinds:

- **Burst rule:** the ⚡ trade-flash rule, read from `orderflow/tape.py` and never retyped. A `BURST_WINDOW_SEC` (10 s) window holding ≥ `BURST_MIN_DOLLARS` ($250K) traded, ≥ `BURST_ONE_SIDED` (75%) on one side and ≥ `BURST_MIN_TRADES` (15) prints. The opening and closing auction crosses (`trade_flash.AUCTION_CROSS_ET`), average-price and busted prints are out (`tape.print_kind`).
- **Location-free:** anywhere in the day's range, not only at a zone.
- **When:** every 5 min, `trade_flash.WATCH_OPEN_ET`–`WATCH_CLOSE_ET` (09:32–16:00 ET), on trading days. Both are `MARKET_ALERT_KINDS`, so they are silent on closed days.
- **Push:** one consolidated push per kind per poll, to the owner only (`trade_flash._owner_email()`). The phone shows the first `PUSH_BODY_LINES`; **every** burst is listed on /alerts with a per-ticker link to `/sepa/{SYM}?tab=tape&from=chart-maps` (`push/recent.ITEM_URL_BY_KIND`).
- **Prefs:** `default_prefs` False for everyone; both in `OWNER_KEEP_SET` (AMENDMENTS A12). After the deploy the main session runs `scripts/owner_prefs_apply.py`, which turns both ON on his registered phones. That run is authorised by his ask and K4.

## Precedence and dedupe (AMENDMENTS A3, A5)

- **A burst on a High-Beta name rings as 🎢 `tape_burst_highbeta`, at a zone or not.** ⚡ `trade_flash` is muted on his phone, so leaving a zone burst on a High-Beta name to ⚡ would mean it never rings.
- A zone burst on any other name stays ⚡ `trade_flash` (muted on his phone, still listed on /alerts). /alerts shows the count as "{n} recorded as ⚡ trade flash (muted on your phone)" (A4, fresh bursts only).
- 🗺️ never watches a zone name or a 🎢 name. Precedence for it: High-Beta first, then Chart Maps.
- **One burst = one /alerts row.** The event `_id` is `trade_flash.event_id` = `SYM:day:time_et`.
  - Both new kinds upsert `$setOnInsert` into `tape_burst_events` and store `kind` on the doc.
  - Both check `trade_flash_events` first.
  - The zone pass also checks `tape_burst_events` before it records, so the dedupe runs both ways.
  - On an existing `_id` the kind is read: `dup_same` = the same kind re-seen inside `LOOKBACK_MIN`; `dup_kind` = another kind already holds it.
  - The counters served on /alerts count FRESH bursts only.
- New kinds never write `trade_flash_events`. The S&D zone strip (`trade_flash.today_events`) and `push/recent`'s old-row rebuild read that collection.

## Where it runs

- On the **existing** `2-57/5 9-15 * * 1-5 … sepa.cli trade-flash-watch` crontab line, in the same process, after the zone pass. There is NO new crontab line: the host-mounted crontab is not shipped by a deploy. The comment block over that line says it carries both kinds.
- The `cron` service must be redeployed to carry the code.
- The same trade-flash line also carries 🎚️ `tape_control` since 2026-10-16 ([`tape_control_2026_10_16.md`](tape_control_2026_10_16.md)).
- `--kinds` (default `all`) and `--dry-run` (no write, no push, clock gate bypassed; prints both watch lists and the candidates).
- An exception in the kinds never touches the zone pass or its push (`kinds_error`).
- Per poll: `FETCH_WORKERS = 4` and a `KINDS_BUDGET_SEC = 200` wall budget for both kinds (MINE, AMENDMENTS §8). Names not reached are counted `skipped_budget`.
- **Cold watch list (A9):** the 🎢 list lives in the api's memo. The cron process reads it over HTTP only and never warms in-process. A `warming` answer = an empty list for THAT poll; the warm starts on the server and the next poll (09:37) gets the list.
- Chart Maps freshness: a tab's names count only when its membership doc was built today or on the last market day (`tabs_old` otherwise). Only tabs that keep a membership doc are covered (board tabs + Bonde), and only their served top 80 after a default page load.

## /alerts, heartbeats, health

- Both kinds are in `alert_status.PASS_KINDS` with `CADENCE_SEC` 300 (derived from the trade-flash line's minute field). Each pass carries a served `window` built from `WATCH_OPEN_ET` / `WATCH_CLOSE_ET`.
- The Alerts page shows them in their own TAPE strip, judged stale only inside that window. That keeps the "all 6 passes" line unchanged.
- Chip counts (`tape_burst_kinds._served`, fresh bursts only): `at_zone` (High-Beta bursts at a zone that rang as 🎢, A5), `dup_trade_flash`, `dup_kind`, `no_tape`, `skipped_budget`, `tabs_old`.
- `engine_heartbeat.beat(kind)` after a real run.
- `health_audit` WARNs when a kind's heartbeat is older than 20 min inside 09:45–16:00 ET (the `trade_flash` check, shared).
- ℹ️ Rules panel: the alerts list of the `high_beta` section, built from `tape.py` / `trade_flash` / `tape_burst_kinds` / `alert_status` constants. It reads ON from `push.subs.owner_prefs()`, never claimed.

## Load and volume (risks)

- Tail fetches go from ≤ 60 to ≤ 360 per 5 minutes on the shared Massive key (spec §7 #10).
- Up to 2 more consolidated pushes per 5 minutes on a busy tape, with no daily cap (spec §7 #8). "A spammy kind is how kinds get retired" (`trade_flash.py`).
- `push/history.MAX_ITEMS = 100`: a poll with more than 100 bursts stores the first 100 items.
- Half days: the watch keeps polling to 16:00 on a 13:00 close (unchanged trade_flash behaviour).

## His calls (open)

1. The watch-list floor: the house $2 share-price floor (`trading.safety_floor.MIN_SHARE_PRICE`, A13) on the 🎢 list and on every tail both kinds read (`under_floor`).
2. Round-robin ~6 names per tab under the 150 cap vs names on several tabs / tabs he opens most.
3. A zone burst on a non-High-Beta name stays under the muted ⚡: keep it, or turn ⚡ back on?
4. A daily push cap.
5. Watching tabs not opened since the last session.
6. The 🗺️ emoji.
7. Up to 360 tape reads per poll on the shared key.

## Files

- `backend/orderflow/tape_burst_kinds.py`, `backend/orderflow/trade_flash.py` (kind-parameterised `record_and_push`, `WATCH_OPEN_ET` / `WATCH_CLOSE_ET`, `fmt_dollars`)
- `backend/sepa/cli.py`, `backend/crontab` (comment only), `backend/push/subs.py`, `backend/push/recent.py`, `backend/market_hours/gate.py`, `backend/supply_demand/alert_status.py`, `backend/observability/health_audit.py`
- `backend/tests/test_tape_burst_kinds.py` + the pin updates
- FE: `lib/alertKinds.ts`, `pages/Alerts.tsx` (TAPE strip, chips), `pages/Notifications.tsx` (two rows, Essentials)

Deploy `api frontend cron`, then run `scripts/owner_prefs_apply.py`.
