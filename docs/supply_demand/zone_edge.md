# Zone edge — breaking resistance → new highs (`supply_break_alert`) + near demand (`demand_alert`), every minute

**Ask (Ajay 2026-09-03 ~5pm ET, verbatim):** *"1. Oh I need stocks that are <1% away from
breaking supply zones which are going for new highs... 2. and stocks that are just <1% away
from Demand zones. I need you to give me an alert and also to track these min on min. Actually
can you add #1 stocks in to Demand zone too ones breaking resistance and also in to deep demand
zones. I wanna keep track of these."*

Configured price-structure heuristic, S/D scope, **NOT a book method, no Minervini cites**.
Decision support, not a buy signal, not advice.

Module: `backend/supply_demand/zone_edge.py` · route: `GET /supply-demand/zone-edge` ·
cron: `* 9-16 * * 1-5 python -m supply_demand.zone_edge` (module refuses outside **09:31–16:00
ET**) · tests: `backend/tests/test_zone_edge.py`, `test_zone_store.py` (`high_252`).

## What it reads

Same inputs as `zone_bounce_alerts.py`, once per minute, **no per-symbol network call**:

| | |
|---|---|
| Bands | `zone_store.load(None, today)` — every supply + demand band per $1B+ name, board geometry, drawn BEFORE today (9:20 warm). New field **`high_252`** = `frame["high"].tail(252).max()` on the truncated frame (the 52-week high as of yesterday's close; `None` on failure). |
| Print | `sepa.prices.bulk_snapshot(sorted(store))` → `zone_bounce_alerts.print_from_snapshot(snap, now, STALE_PRINT_SEC=180)`. A last trade older than **3 minutes** is stale on a one-minute cadence — skipped and counted. |
| Prev close | `snap.prev_day_close`, falling back to the store doc's `prev_close`. |
| Cap | `catalysts.promo_circuit.market_caps_for(list(prints), prints)`. **Unknown cap = not on the board** (a known-big name or nothing, like zone_bounce). |
| Names | the `company_names_cache` coll in **one `$in` read** for the listed rows (`_names_for`). Never `name_for` per row: its memo is per process and the cron is a fresh process every minute, so per row it was one Mongo round trip per listed name. |
| Owner | `portfolio.alerts._resolve_owner()`; `push.sender.send_to_user(owner, payload, kind=...)`; every payload carries `"kind"`. |

## Side A — "breaking" (`read_breaking(px, bands, prev_close, high_252)`)

| step | rule | constant |
|---|---|---|
| resistance | supply bands with `hi >= px` **that yesterday did not close above** (`hi >= prev_close` when known; a band with `hi < prev_close` is Side B's broken supply = support, never resistance — fix 2026-09-05, before it a pullback INTO such a shelf read `near` and pushed 🚀 five minutes after the same band pushed 🧲). Unknown prev close: geometry only. Take the **smallest `hi`** | |
| **near** | `0 <= (hi − px) / px × 100 <= EDGE_PCT` | `EDGE_PCT = 1.0` |
| **broke** | no near band, and some supply band has `hi < px <= hi × (1 + BROKE_MAX_PCT%)` **and** `prev_close <= hi` (it broke **today** — yesterday still closed at/under the ceiling). Take the **highest** such band. `dist_pct = −(px − hi)/px × 100` (negative = above). Unknown prev close → cannot say → nothing. | `BROKE_MAX_PCT = 3.0` |
| new_highs | `overhead_bands == 0` **or** (`high_252` known and `band.hi >= 0.98 × high_252`) | `NEW_HIGH_TOL = 0.98` |
| overhead_bands | count of **other** supply bands with `hi > band.hi` — an **overlapping** lid (`lo <= band.hi < hi`) counts (integrator 2026-09-05, Ajay: *"yes please fix the bugs"*; was `lo > band.hi`, which made a 99–104 band invisible over a 96–99.5 break at 100: `new_highs` read true with the print **inside** a supply band, the 🚀 gate read CLEAR, and `zone_edge_entry._needs_room_check` skipped the room check on the same fact) | |
| pct_to_52w | `(high_252 − px) / px × 100` (None when unknown) | |

Near beats broke on purpose: a name 1% under the *next* ceiling after breaking one reads as
`near` that ceiling (with `overhead_bands` telling the rest).

## Side B — "near_demand" (`read_near_demand(px, bands, change_pct, prev_close)`)

| step | rule |
|---|---|
| support | demand bands, **plus supply bands yesterday CLOSED above (`hi < prev_close`)** — `zone_bounce_alerts.is_eligible`, the house definition of broken supply = support, role `broken supply` (the NTAP shelf of 09-03). A shelf being broken **today** (`prev_close <= hi`) is Side A's fact and never support here: with `hi < px` alone one breakout was two pushes (🚀 broke + 🧲 "above demand", same band, same minute — review 2026-09-03). Unknown prev close: supply bands are never support; demand bands still list (resident). |
| **in** | a demand band with `lo <= px <= hi` → `dist_pct 0` (the one with the greatest top when nested) |
| **near** | else the support band with the **greatest `hi <= px`**, when `(px − hi) / px × 100 <= EDGE_PCT` |
| arrival | `demand_alerts.read(px, band, change_pct, prev_close) is not None` — the **identical** rule the 5-min pass uses: yesterday closed outside the 1% ring, or under the floor (a reclaim). Unknown prev close = resident (counted `unknown_prev`). |

A demand band entirely *above* the print is not support; inside a supply band is not "in demand".

## Board vs phone

**Board** (`zone_edge_latest`, `GET /supply-demand/zone-edge`): every near/broke/in name with a
**known** cap, every band with its touch count, arrivals and residents tagged, `new_highs` and
`overhead_bands` shown. Cap < $1B rows stay listed (`skipped_cap` counted), never pushed.

**Phone** — strict subset, both sides, at most `MAX_SINGLES_PER_PASS = 3` singles per side per
pass (strongest first) and the rest in **one digest** (≤ `DIGEST_MAX = 6` lines, then `+N more`).
Digest names are recorded in state too — nothing repeats. State is written only on a terminal
send (delivered, or nobody targeted — muted pref / no device); a transport failure retries next
minute.

| side | pushed when | kind | state coll · key |
|---|---|---|---|
| breaking | `new_highs` **and** `band.touches >= MIN_TOUCHES_PUSH (2)` **and** cap ≥ $1B **and** the phone gate (below) | `supply_break_alert` (**new**, default on in `push/subs.py`) | `supply_break_state` · `SYM:lo-hi:YYYY-MM-DD:tier` — once per (symbol, band, day, tier); `near` then `broke` on the same band are two facts |
| near demand | `arrival` **and** touches ≥ 2 **and** cap ≥ $1B **and** the phone gate (below) | `demand_alert` (**reused**, no new kind) | `demand_alert_state` · `demand_alerts.state_key(sym, band, day, 'at')` — the same key the 5-min `demand_alerts.py` writes, so **neither module can double-fire the same band on the same day** (locked both directions in the tests) |

Singles order: breaking → broke rows first (furthest through first), then nearest to the
ceiling; near demand → closest first.

### Phone gate (2026-09-05)

**Ajay 2026-09-05 (verbatim, mid-fix):** *"When alert I need the same logic. Need only alerts on
stocks that have atleast 5% to Supply and also <1% bounce from demand zone"*. One shared module,
`backend/supply_demand/alert_gates.py`, called by every S/D push path (this module, zone_bounce_alerts,
demand_alerts). **Boards unchanged** — the near/broke/in rows list exactly as before; only the phone
tightens.

| owner setting | value | from his sentence |
|---|---|---|
| `ALERT_MIN_ROOM_PCT` | **5.0** | "atleast 5% to Supply" |
| `ALERT_MAX_ABOVE_DEMAND_PCT` | **1.0** | "<1% bounce from demand zone" |

* `room_gate(print, bands, prev_close)` — the first band price meets going up, the same rule as
  `bounce_room.first_overhead` / the fixed `zone_bounce_alerts.room_for`: unbroken supply bands with
  `hi >= print` (a band with `hi < prev_close` is support, skipped), plus demand bands with `lo > print`
  (broken support). CLEAR passes; inside a band (`IN_BAND`) fails; room `< 5%` fails.
  * 🚀 breaking: measured from the print to the **next band above the one being broken** — every
    band whose top clears this one's (`hi > band.hi`, an overlapping lid included; integrator
    2026-09-05, was `lo > band.hi`) — new-highs rows are usually CLEAR and pass. "At least 5% to
    supply" applies to every phone kind.
  * 🧲 near demand: measured against the store's bands. The in/near tier **is** the "<1% above
    demand" rule (`EDGE_PCT == ALERT_MAX_ABOVE_DEMAND_PCT`, locked in the contracts) — reused, not
    duplicated.
* Push bodies gain the read: `· room +8.4% -> $110 ·` or `· room: clear runway ·` (the wording
  `zone_bounce_alerts` pushes already used), before the cap.
* Skips are counted: `skipped_room` in the pass result and the `ZONE-EDGE:` log line, so a quiet
  phone is explainable.

### Message formats

| | |
|---|---|
| near single | `🚀 AAA 0.49% under resistance $100–102 → new highs` |
| broke single | `🚀 AAA broke resistance $100–102 (+1.0%) → new highs` |
| body | `$101.5 · tested 3x · 52w high $103 (+1.5%) · room: clear runway · $5.0B · Alpha` — the 52w piece is dropped when unknown, the name when None; the room piece is the phone gate's read (2026-09-05) |
| url | `/sepa/AAA?tab=supply` (also `data.url`) |
| break digest | title `🚀 Breaking resistance — N1 0.49% +1 more` (a broke lead reads `B1 broke +1.0%`); one line per name `N1 $101.5 · 0.49% under $100–102 · tested 3x · $5.0B` (broke lines: `B1 $103 · broke $100–102 (+1.0%) · tested 3x · $3.0B`); url `/chart-maps?tab=deep_demand` |
| demand single | `demand_alerts.at_message` — `🧲 AAA in demand $90–92` / `🧲 D1 0.22% above demand $90–92`, body `$91 · tested 2x · room +5.5% -> $96 · $5.0B · Alpha` |
| demand digest | `demand_alerts.digest_message` — `🧲 Demand zone — D3 +1 more` |

## Tracking ("min on min")

Every pass (`track=True`):

* upserts **`zone_edge_latest`** `_id 'latest'` = the API payload without `track`;
* inserts one **`zone_edge_track`** row per listed board row
  `{symbol, date, ts (ET ISO), side ('supply'|'demand'), tier, px, dist_pct, band: {lo, hi}}`;
* deletes track rows dated before `today − TRACK_KEEP_DAYS (2)`;
* ensures the track index `(date, symbol, ts)` (idempotent; `ensure_track_index`) so the
  windowed read and the purge stay index-bound as rows pile up;
* `first_seen` per (symbol, side, band, date) = the first minute that key was listed today
  (== the earliest track row for it, since every listing writes a row), kept as **one per-day
  map doc** `zone_edge_latest/_id 'first_seen'` `{date, rows: [[key, "HH:MM"], ...]}` with
  `key = SYM:side:lo-hi` (**fixed 2 dp since 2026-09-05**, e.g. `AAA:supply:100.00-102.00`) — one `find_one` + one `replace_one` per pass, never a re-read of the
  day's rows. A name that drops off the board and returns keeps its first clock. A dry run
  (`track=False`) shows the clocks it finds and starts none.

The API attaches `track["supply:SYM"]` / `track["demand:SYM"]` = the `[HH:MM, dist_pct]` points
stamped within the last `TRACK_POINTS (30)` **minutes** up to `as_of`, chronological (`read_track`
with `ts >= as_of − 30 min`). Rows are one per minute per key, so for a continuously listed name
that is the last 30 points, and the read is bounded by 30 rows per listed key instead of the whole
day — hundreds of rows a minute reach ~100k by mid-afternoon, and the FE polls every 60 s.

## API payload — `GET /supply-demand/zone-edge`

```
{"as_of": "2026-09-03T10:00:00-04:00" | null, "date": "2026-09-03",
 "in_session": bool (evaluated at REQUEST time — the stored flag is the pass's own clock),
 "pass_sec": 2.1,
 "params": {"edge_pct": 1.0, "broke_max_pct": 3.0, "min_cap_usd": 1e9, "min_touches_push": 2},
 "counts": {"breaking", "near_demand", "candidates", "priced", "stale_print"},
 "breaking": [row], "near_demand": [row],
 "track": {"supply:AAA": [["10:00", 0.49], ...], "demand:BBB": [...]},
 "disclaimer": "..."}
row = {"symbol", "name", "last", "dist_pct", "tier" ('near'|'broke'|'in'), "side", "role"
       ('resistance'|'demand'|'broken supply'), "band": {"kind","lo","hi","touches","strength"},
       "cap", "new_highs", "high_252", "pct_to_52w", "overhead_bands", "arrival", "first_seen", "url"}
```

Ordering: `breaking` → broke rows first, then near; within each `new_highs` first, then
`dist_pct` ascending. `near_demand` → arrivals first, then `dist_pct` ascending. No pass yet →
`{"as_of": null, "in_session": false, "breaking": [], "near_demand": [], "track": {}, "reason":
"no pass yet"}`. JSON-safe: plain float/int/str/bool/None only (`_clean` strips numpy scalars,
NaN/inf → None).

**A doc from another day is never live (fix 2026-09-05).** `api_payload` compares the stored doc's
`date` with today (ET): when they differ, `in_session` is `false` and `reason` is
`"last pass 2026-09-03; no pass yet today"`. The rows and track stay, so the evening/weekend board
still shows the last pass, but nothing claims live. Before this a cold `zone_store` (warm failed)
left Thursday's rows under a live header all Friday. And a cold store now **writes** an empty payload
`{"as_of": null, "date": <today>, "reason": "zone store empty for today", ...}` each minute (unless
`track=False`), so the board self-heals instead of serving yesterday. **Except** when the stored
`latest` is already a real pass from **today** (`date` = today and `as_of` set): `zone_store.load`
swallows a Mongo read error into `{}`, so a transient failed read at 10:30 must not blank the day's
board for a minute (integrator 2026-09-05; the pass result says `latest_written: false` and the log
warns "kept (transient read?)"). A missing, stale-day or already-empty doc still gets the write. The FE (`ZoneEdgeBoard.tsx`)
renders the `as_of` stamp as HH:MM only and does **not** render `reason` — a stale-day doc shows as
"market closed — last pass HH:MM" (honest, not live), and the cold-store doc as "no pass yet today".

## Ops

Log line per pass: `ZONE-EDGE: ran=… candidates=… priced=… stale_print=… breaking=…
near_demand=… pushed=… skipped_room=… seconds=…` — `docker logs cheetah-market-app-cron-1 | grep ZONE-EDGE`.

Dry run in the cron container (reads everything, pushes nothing, writes nothing):

```
cat > /tmp/ze_dry.py <<'EOF'
import json, logging
logging.basicConfig(level=logging.INFO)
from supply_demand import zone_edge as ZE
out = ZE.check_once(push=False, force=True, track=False)
print({k: v for k, v in out.items() if k not in ("breaking", "near_demand", "payload")})
print(json.dumps(out.get("breaking", [])[:5], indent=1))
print(json.dumps(out.get("near_demand", [])[:5], indent=1))
EOF
docker cp /tmp/ze_dry.py cheetah-market-app-cron-1:/tmp/ze_dry.py
docker exec -w /app cheetah-market-app-cron-1 sh -c 'PYTHONPATH=/app python /tmp/ze_dry.py'
```

`check_once(push=False, force=True)` (track on) also writes `zone_edge_latest`/`zone_edge_track`
— use it to seed the board after a deploy outside RTH; the UI will then say "market closed —
last pass HH:MM".

## Traps

* **Holidays (fix 2026-09-05):** `in_session` (here, `zone_bounce_alerts`, `demand_alerts`) is weekday
  AND `market_hours.reminder.is_market_day` — the house NYSE full-closure list (`HOLIDAYS_2026/2027`,
  hand-maintained yearly, that module's own documented choice over pandas-market-calendars). Before
  this the passes ran on Labor Day, warmed the store with the holiday's date and the board said
  "refreshes every minute" over an empty list. Known limitation: early-close days are not modelled
  (the passes run to 16:00 on a 13:00 close; every print is stale after the close, so nothing lists).
* **Keys changed format on 2026-09-05** (a weekend deploy, so no same-day re-push): state, first_seen
  and dedupe keys are fixed 2 dp (`AAA:100.00-102.00:2026-09-05:near`) instead of `:g` (6 significant
  digits, which collapsed two bands on a $10,000+ name into one key and deduped the second for the
  day). Display text (`$100–102`) keeps the short form. `demand_alerts.state_key` — shared with the
  near-demand side — changed the same way.
* `zone_store` cold (warm failed / first day) → `zone store empty for today`, nothing listed.
  Store docs from before this change have no `high_252` → the 52w rule is simply off for them
  (`new_highs` falls back to "nothing overhead"); the next 9:20 warm fills it.
* `supply_break_alert` **must** stay in `push/subs.py::default_prefs` — a kind missing there
  silently drops for every device (the 2026-06-24 chokepoint).
* The near-demand side deliberately has **no kind of its own**: it is the same fact as
  `demand_alert`, read every minute from the store instead of every 5 from the board, and shares
  that module's state key so the two never stack.
* `dist_pct` is **negative** for broke rows (above the ceiling) — sort ascending puts the
  furthest-through first, which is what "strongest" means on that side.
* `first_seen` is per band: a name that steps from one shelf to the next gets a new clock.
* The pass loop is **pure** — no I/O per symbol. Names come from one `$in` read
  (`_names_for`), dedupe state from one `$in` read per state coll (`_existing_keys`),
  `first_seen` from one doc. `test_pass_never_goes_to_mongo_per_symbol_one_bulk_read_each`
  counts the calls; `name_for` / `find_one(` inside `check_once` fail the source guard.
* Cross-module dedupe assumes the board's `entry_zone` and the store's band carry the same
  `lo`/`hi` (both come from `price_zones.compute`, rounded to 2 dp). The board's frame may
  include today's partial bar and the store's never does, so a band that shifts by a cent
  between the two is two keys — each module could then fire once for it. Accepted.
