# 🔔 Alerts page — what pushed, and why the phone was quiet

**Ask (Ajay 2026-09-05, verbatim):** *"Do we have the same logic in back end demand for the
ones that I get alerts. Would it be the same list of stocks.. Also can I go to a
dedicated page to see the list of alerts? May be add it to recent alerts or something?"*

Two questions. The honest answer to the first is **no**, which is exactly why the second needed
a page of its own rather than a filter on /notifications.

Configured price-structure heuristic (zone_store bands), **not a book method** — decision
support, not a buy signal, not advice. S/D scope only.

## 1. Why the Demand board and the phone are NOT the same list

| | Demand board (`/supply-demand` Demand tab) | Phone pushes (🧲 🪃 🚀) |
|---|---|---|
| Bars | **closed** daily bars (`demand_reentry` scan; the board never uses the live print) | **live** last trade, every 1 / 5 min in RTH (`prices.bulk_snapshot` / `bulk_live_prices`) |
| Universe | the full SEPA universe (~1,746 names), every cap | names in today's `zone_store` (warmed 9:20) or on the board — **known cap ≥ $1B only**; unknown cap is skipped and counted |
| Filter | MIN_TOUCHES / zone strength, falling-knife guard, `trend_ok`, the 5-bar drift predicate, and the **R:R floor** ([rr_floor.md](rr_floor.md)) | the **phone gate** ([alert_gates.py](../../backend/supply_demand/alert_gates.py)): **≥ 5% room** from the print to the first unbroken band overhead **and** print **≤ 1% above** the demand band's top (Ajay 2026-09-05: *"atleast 5% to Supply and also <1% bounce from demand zone"*) |
| Dedupe | none — a row lists as long as it qualifies | **once per (symbol, band, day[, tier])**; a name that rang at 9:33 does not ring again |
| Digest | n/a | first `MAX_SINGLES_PER_PASS` ring individually, the rest ride **one digest** push |

So a name can sit on the board all day and never push (too close to a lid, under $1B, already
rang, print 1.4% above the band), and a name can push that is not on the board (a zone-edge 🚀
breaking supply toward new highs has nothing to do with the Demand tab). The overlap is real but
partial — which is what the **🔔 alerted today** chip on the Demand board and the zone-edge board
rows makes visible: it means *this exact symbol pushed today*, nothing more.

## 2. What the page answers

1. **What pushed** — every `demand_alert` / `zone_bounce_alert` / `supply_break_alert` row from
   `push_history`, newest first, with title + full body (the lock screen clips at ~180 chars),
   ticker link, and delivery (`sent` / `failed` / `total` devices). Times are shown in **ET**
   (`ts` is a UTC epoch, `ts_iso` UTC — the page formats in America/New_York).
2. **Why it was quiet** — one status card per pass with the last pass's counters (section 4).
   "Quiet" has four different causes and the counters tell them apart: nothing qualified, every
   candidate was gated (room / cap / proximity), the pass never ran (outside RTH, store empty,
   snapshot failed), or the push was muted / no device (`total = 0` in the row).

Coverage honesty on every label: the list is **push_history** (90-day TTL, what the sender
recorded), not the boards; the counters are **the last pass of each cron**, not a full-universe
truth; a pass doc from another day is stale and labelled so (`date` vs today).

Page rules worth knowing (all pinned in `frontend/src/pages/Alerts.test.tsx`):

* **Delivery line** per row: `delivered to n/m devices`; `total = 0` → *"not delivered — no device
  targeted (muted kind or no subscription)"*; `sent = 0, total > 0` → *"not delivered — 0/m devices
  reached"* + the failed count. A recorded send is not a ring.
* **🔔 alerted-today chip** (Demand board + zone-edge rows, `useAlertedToday`): marks a symbol only
  from rows with **`sent > 0`** — a muted `demand_alert` records `total 0` rows all day and must not
  decorate the board as "pushed to your phone" (review 2026-09-05). Chip poll 60 s, cache TTL 45 s
  (a TTL equal to the poll made every tick skip).
* **Window picker**: Today / **Yesterday (that ET day only** — the endpoint has no `until`, the
  page cuts `ts >= 00:00 ET today` from the ≤ 500 rows fetched) / 5 days / 30 days. The skip note
  under an empty list is today's and only the Today window claims it.
* **Ticker box** is debounced 300 ms (Enter / blur commit at once) — typing AVGO is one query.

## 3. Endpoints

### `GET /notifications/recent` (push/recent.py — lifted out of main.py 2026-09-05)

Unchanged default (no params = the old feed: `list_recent(email, limit)` + every
`sepa_breakouts` row, merged ts-desc). New optional params:

| param | meaning |
|---|---|
| `kinds` | comma list, e.g. `demand_alert,zone_bounce_alert,supply_break_alert` → push rows filtered to those kinds; **breakout rows ride along only when the list names `volume_breakout` / `rising_momentum` / `stage_breakdown_*`** (otherwise the sepa_breakouts source is not read at all) |
| `since` | unix seconds → rows with `ts >= since` (the page passes today's 00:00 ET) |
| `ticker` | one symbol, upper-cased before matching |
| `limit` | 1..**500** (was 100) — `push.history.list_recent` caps at 500 internally too |

Row shape unchanged: `{_id, ts, ts_iso, title, body, kind, ticker, url, source, sent, failed,
total, dismissed?}`.

### `GET /alerts/status` (supply_demand/api.py → alert_status.status_payload)

```json
{
  "in_session": true, "now_et": "2026-09-05T10:31:00-04:00",
  "gate": {"min_room_pct": 5.0, "max_above_demand_pct": 1.0},
  "passes": {
    "zone_edge":         {"as_of": "…-04:00", "date": "2026-09-05",
                          "counts": {"candidates": 1124, "priced": 1100, "stale_print": 24,
                                     "breaking": 6, "near_demand": 9, "skipped_room": 3,
                                     "skipped_cap": 2, "unknown_cap": 5, "pushed": 1}},
    "zone_bounce_alert": {"as_of": "…", "date": "…",
                          "counts": {"candidates": 1124, "priced": 1100, "stale_print": 24,
                                     "hits": 4, "skipped_room": 2, "skipped_proximity": 1,
                                     "skipped_cap": 0, "unknown_cap": 1, "unknown_prev": 0,
                                     "pushed": 0}},
    "demand_alert":      {"as_of": "…", "date": "…",
                          "counts": {"candidates": 40, "hits": 3, "at": 1, "at_singles": 1,
                                     "near": 2, "skipped_room": 1, "skipped_proximity": 2,
                                     "skipped_cap": 0, "unknown_cap": 0, "unknown_prev": 0,
                                     "unknown_room": 0, "pushed": 0}}
  },
  "disclaimer": "…"
}
```

* `in_session` is evaluated at **request time** (zone_edge's clock: RTH 9:31–16:00 on NYSE
  trading days, holiday-aware). `as_of` / `now_et` are ET ISO strings. **`in_session` is the
  clock, not proof the crons are alive** (review 2026-09-05: a cron dead since 10:02 read as
  "passes running" at 14:30). Each pass carries **`cadence_sec`** (`alert_status.CADENCE_SEC`,
  pinned to `backend/crontab` by `test_cadence_sec_matches_the_crontab`: zone_edge 60, the two
  5-minute passes 300); the page compares `as_of` with `now_et` and calls a same-day stamp
  **stale** past `max(300, 3 × cadence_sec)` seconds (5 min / 15 min) while in session. The
  header says "reported within cadence" only when all three are fresh; otherwise "Session open
  (clock) — ⚠ N of 3 passes not reporting on cadence".
* A pass that ran and read nothing carries a **`reason`** which the page renders as an amber
  chip. zone_edge's cold-store self-heal write keeps `as_of` null on purpose (that key means "a
  real pass with rows" to the board header, `_latest_is_todays_pass` and the paper engine's
  freshness read) and stamps **`ran_at`** instead; `read_zone_edge` reports `ran_at` as the
  pass time so the page can say "last pass 09:35 ET · ⚠ zone store empty for today". A doc
  from before 2026-09-05 (as_of null, reason, today's date) reads "ran today — no pass time
  recorded", never "no pass yet today".
* A missing pass doc → `as_of: null`, `counts: {}` — the page says "no pass recorded", never
  zeros it did not measure. A pass that ran but read nothing carries a `reason`
  (`"zone store empty for today"`, `"board empty or warming"`, `"snapshot failed: …"`).
* `zone_edge` comes from the existing `zone_edge_latest` doc (`_id: 'latest'`), whose stored
  `counts` now include `skipped_room / skipped_cap / unknown_cap / pushed` (`pushed` is known
  only after the sends, so the payload is built last). A doc written before 2026-09-05 lacks
  those keys and they are **passed through as absent**, not invented.
* `zone_bounce_alert` / `demand_alert` come from the new **`alert_pass_latest`** collection
  (`{_id: kind, as_of, date, counts, reason?}`, one doc per kind, **replaced every pass**),
  written by `alert_status.record_result` at the end of each `check_once`. Best-effort: a dead
  Mongo never blocks a push and never raises. The `pass_coll` kwarg is injectable for tests.

## 4. Reading the counters — how a quiet phone happened

| counter | pass | meaning |
|---|---|---|
| `candidates` | all | names the pass looked at (zone_store names for zone_edge / bounce; board rows for demand_alert) |
| `priced` / `stale_print` | zone_edge, bounce | names with a fresh last trade (≤ 10 min) / dropped as stale — a snapshot outage shows here first |
| `breaking` / `near_demand` | zone_edge | rows **listed** on the zone-edge board (every known-cap name near/broke a lid or in/near a demand band) |
| `hits` | bounce, demand_alert | bands touched-and-bouncing / at-or-near — the pre-gate set |
| `at` / `near` | demand_alert | tier split of the hits (NEAR is never pushed since the gate; it is listed and counted) |
| `skipped_room` | all | **listed but < 5% room** to the first unbroken band overhead (the gate's first half) |
| `skipped_proximity` | bounce, demand_alert | **listed but > 1% above** the demand band's top (the gate's second half) |
| `skipped_cap` | all | listed, cap known and **< $1B** |
| `unknown_cap` | all | cap **unknown** (shares cache never saw it) — not a known-big name, skipped |
| `unknown_prev` | bounce, demand_alert | no previous close in the live read — cannot judge an arrival, skipped |
| `unknown_room` | demand_alert | no zone_store doc for the name — nobody measured its supply, silent |
| `pushed` | all | **send calls that terminated** — delivered, **or nobody targeted** (muted kind / dead subscription: `_terminal` treats `total_targets = 0` as done, so a muted `demand_alert` still counts here). Singles + digests; a digest of 6 names counts 1. The page labels it **"push calls"** and each row's delivery line says what actually reached a device |

Rules of thumb: `pushed = 0` with big `skipped_room` = the gate did its job (everything near
demand had a lid inside 5%); `pushed = 0` with `candidates = 0` + a `reason` = the pass had
nothing to read (store not warmed / board warming); `as_of` from yesterday = today's cron has
not run (holiday, container down); a push row with `total = 0` = muted pref or no device
(`/notifications`), not a scanner problem.

## 5. Feature flag

`access/store.py`: `{"id": "alerts", "label": "🔔 Alerts", "group": "tools", "added_in": 23}`,
`CATALOG_VERSION = 23` — owner-on on next load; route `/alerts` (build_menu derives it from the id).

## 6. Tests

* `tests/test_push_history_filters.py` — kinds `$in`, since `$gte`, ticker upper-casing, limit
  cap 500, default query byte-for-byte unchanged.
* `tests/test_notifications_recent.py` — the route through TestClient: default read unchanged,
  breakout source excluded unless a breakout kind is named, since/ticker on both sources, 501 → 422.
* `tests/test_alert_status.py` — counts hygiene, record/read, contract-B shape, request-time
  `in_session`, route offload, leaf/cycle guards, this doc's existence.
* `tests/test_zone_edge.py::test_stored_counts_explain_a_quiet_phone_skip_buckets_and_pushed`,
  `tests/test_zone_bounce_alerts.py` / `tests/test_demand_alerts.py` "every pass records its
  counters" + "best-effort, never outside RTH", `tests/test_access_menu.py` alerts feature.
