# Catalyst-lane Auto-Pilot — `backend/trading/catalyst_entry.py`

**Ask (Ajay 2026-09-05, verbatim):** *"What ever rules I created for the alerts
are the ideal conditions for a stock to be bough in Autopilot. Keep the
minervini entries but also make sure you have demand zone and catalyst based
entries time to time and journal it appropriately."*

**PAPER ONLY.** The engine trades the Alpaca **paper** account. This lane adds
no live-mode default, touches no broker key, and is **OFF by default in every
mode** (`catalyst_entry: false`); arming is still required on top, like every
other buy path.

---

## 1. Honesty note — what is a book rule and what is not

| Layer | Source | Where it lives |
|---|---|---|
| **Entry rules** (which catalyst names, the level gate, the requested stop, the daily cap) | **Owner rules / owner settings** for the Supply & Demand + Catalysts board strategy. **No book.** Nothing here is Minervini and no SEPA page is cited (`feedback_sepa_book_scope`). Two numbers are **builder defaults, NOT from Ajay** (marked below). | `trading/catalyst_entry.py` (constants locked in `tests/test_trading_contracts.py`) |
| **Signal** (the catalyst scan: quadrant, review grade, pump warning, offering read) | The Catalysts board's own pipeline (`catalysts/scanner.py → scorer.py → evidence.py → gemma_review.py`), read from its **cache only** | `catalysts.api._cache_get()` (Mongo `catalysts_cache`, `_id scan_latest`) |
| **Level + room** (bands, bounce read, first unbroken band overhead) | `supply_demand/bounce_room.py` + `supply_demand/alert_gates.py` — the same reads the phone uses (`docs/supply_demand/bounce_room.md`, `alert_gates`). Zone docs are **read from Mongo only** (`bounce_room.load_docs`); the print is the cached scan's own price, read through the pure `bounce_room.read_symbol` | `bounce_room.load_docs`, `bounce_room.read_symbol`, `alert_gates.room_gate`, `alert_gates.demand_proximity_gate`, `zone_bounce_alerts.STALE_PRINT_SEC` |
| **Risk math** (stop clamp to the engine's absolute line, target ≥ the engine's reward:risk floor, sizing, streak multiplier, never average down, earnings shield, MAX_POSITIONS) | The engine-wide risk contract, `trading/risk_rules.py` — **book, FROZEN, unchanged** | applied by `trading/entries.enter()`, the **only** buy path |

The module only *requests* a stop; `risk_rules` decides. It never places an
order at the broker itself and never triggers a catalyst scan (contract test
greps it for `submit_` / `replace_order` / `cancel_order` / `close_position` /
`_full_scan(` / `scan_catalysts(`).

## 2. Signal source — the cached scan, never a scan

`catalysts.api._cache_get()` returns the payload the Catalysts board last
built (a user's page visit or the board's poll), or `None` when there is none
or it has expired (5 min in RTH, 30 min after hours, 1 h weekends). The lane
reads it once per tick. **It never calls the scan pipeline** — a 30-45 s
pipeline with an LLM review does not belong inside a 60 s engine tick, and a
tick that could trigger network fan-out is a tick that can stall stop
protection. No cache = tick summary `reason: "no cached catalyst scan"`,
nothing bought. Honest consequence: on a day nobody opens the Catalysts board
the lane buys nothing.

**The tick reaches neither the tape nor the zone builder** (review
2026-09-05). Until that review the lane called `bounce_room.api_payload` from
inside `exit_engine.tick` — a synchronous provider snapshot plus, for every
funnel survivor without a store doc (most catalyst names), an on-demand
2-year price load and zone build on the board's worker thread. Now the tick
reads zone docs from Mongo only (`bounce_room.load_docs`: the 9:20
`zone_store` warm plus the `bounce_room_zones` on-demand cache that the
**Catalysts board's own bounce-room call** fills) and prices the read off the
scan's own row (`snap_from_scan` → `bounce_room.read_symbol`, both pure). A
name with no doc is skipped *"no zone doc yet (a Catalysts board visit builds
it; retried next tick)"* — a skip, never a build, never assumed clear.
Contract: `test_catalyst_entry_tick_never_reaches_the_tape_or_the_ondemand_
zone_builder` greps the module for the payload builder, the queue, the
provider snapshot and the price/zone build calls.

Each candidate row: `{ticker, price, prev_close, day_low, day_high,
dollar_volume, change_pct, market_cap, quadrant, composite_score, review:
{catalyst_summary, evidence_grade, is_pump_warning}, evidence: {sec_filings:
{has_offering}}}`. `price` is the print the zone gate reads; `day_low` /
`day_high` / `prev_close` give the touch read its session bar; the payload's
`as_of` is the print's timestamp.

## 3. Rules (owner rules / owner settings)

| Constant | Value | Source | Meaning |
|---|---|---|---|
| `MAX_CATALYST_ENTRIES_PER_DAY` | 1 | Ajay 2026-09-05 *"time to time"* | one catalyst buy per ET day, counted from `catalyst_entry_state` successes |
| `CATALYST_MIN_EV_USD` | `$700M` | **owner rule (Ajay 2026-09-06: ">700 mil enterprise value")** | enterprise value from the scan row (`catalysts/scanner._enrich_with_yfinance` reads `enterpriseValue` on the `.info` call it already makes — the tick never reaches yfinance); EV unknown → the scan's market cap stands in (his 2026-09-03 promo-tab floor was market cap at the same number); both unknown → skip |
| sales intact | Bonde tier `steady` / `strong` / `explosive` (`SALES_PASS_TIERS` = `sepa.sales.BONDE_PASS_TIERS`) | **owner rule (Ajay 2026-09-06: "Sales are intact")** | `catalysts.promo_circuit.sales_for` CACHE-ONLY in the tick (`cap=0`: SEPA research cache, then `promo_sales_cache`); the `--warm` cron (`WARM_CRON`) fetches for the scan's candidates; unknown fails closed and is counted (`skipped_sales`) |
| `QUADRANTS_OK` | `REAL`, `OVERLOOKED` | owner setting (builder default, **NOT from Ajay**) | evidence-backed moves only; `PUMP_RISK` / `DEAD` never |
| `GRADES_OK` | `A`, `B` | owner setting (builder default, **NOT from Ajay**) | the review's evidence grade |
| pump warning | `review.is_pump_warning is False` | owner setting (builder default, **NOT from Ajay**) | unknown fails closed |
| offering | `evidence.sec_filings.has_offering is False` | owner setting (builder default, **NOT from Ajay**) | S-1 / S-3 / 424B5 / FWP in the last 7 days of filings = no buy; unknown fails closed |
| `CATALYST_MIN_PRICE` | 2.0 | **conservative builder default, NOT from Ajay** | never a sub-$2 name |
| `CATALYST_MIN_DOLLAR_VOL` | 2,000,000 | **conservative builder default, NOT from Ajay** | never a thin tape (session dollar volume from the scan row) |
| market cap | *(no floor)* | — | the scan is sub-$500M by construction (`scanner max_market_cap`); a cap gate would be a tautology, so none is invented |
| `alert_gates.ALERT_MIN_ROOM_PCT` | 5.0 | Ajay 2026-09-05 *"atleast 5% to Supply"* (imported, never redefined) | room to the first **unbroken** band overhead |
| `alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT` | 1.0 | Ajay 2026-09-05 *"<1% bounce from demand zone"* (imported) | the proximity line — applied to the **bounce band too** (review 2026-09-05: a bounce anchor with no proximity check bought 4% above the top while the phone stayed silent) |
| `zone_bounce_alerts.STALE_PRINT_SEC` | 600 | the 🪃 push's own stale line (imported, reused — not a new number) | the print is the cached scan's price; older than this the lane does not act, as the phone would not ring |
| zone docs | Mongo read only | owner rule (review 2026-09-05) | `bounce_room.load_docs` (store warm + on-demand cache); a missing doc is a skip, never a build |
| `STOP_BUFFER_PCT` | `zone_edge_entry.STOP_BUFFER_PCT` (0.5) | owner buffer, reused from the zone-edge lane | requested stop under the anchoring demand band's floor |
| `LAST_ENTRY_ET` | `zone_edge_entry.LAST_ENTRY_ET` (15:45) | reused | no new entries at/after this |
| `SUMMARY_MAX_CHARS` | 160 | housekeeping | the review's one-liner as journaled |
| `STATE_COLL` | `catalyst_entry_state` | — | one attempt per `(symbol, ET day)` |

### Quality funnel (pure, `qualify` / `read_candidates`)

quadrant in `QUADRANTS_OK` → review present with grade in `GRADES_OK` → no pump
warning → offering read present and `false` → `price ≥ 2` → `dollar_volume ≥
$2M`. **Every missing field fails closed.** Survivors are ordered by the scan's
own `composite_score` (desc). Rejections land in the status block's
`skipped[]` with the reason.

### Level gate = the phone's alert rules (`zone_gate`)

Per tick: `_store_day` (the zone store's latest stored session ≤ today, else
the last weekday — Mongo, one query), `_zone_docs` (`bounce_room.load_docs`
for the survivors — Mongo, read only), then `zone_rows` (pure): each
survivor's scan row shaped as a snapshot (`snap_from_scan`) and read through
`bounce_room.read_symbol`, exactly as the board reads it, plus
`print_age_sec` = now − the scan's `as_of`. Then per name, on that row and
its zone doc:

1. **Coverage.** No doc → **skip** *"no zone doc yet (a Catalysts board visit
   builds it; retried next tick)"* (counted `skipped_pending`), never assumed
   CLEAR. A tombstone (`unavailable`) → skip.
2. **Print age.** `print_age_sec` unknown → skip (`alert gate: print age
   unknown`); older than `zone_bounce_alerts.STALE_PRINT_SEC` (600 s, the 🪃
   push's own line) → skip (`alert gate: print stale (scan 720s old > 600s,
   …)`). In RTH the scan cache expires at 300 s, so this bites only on a
   scan the board itself would not trust.
3. **Room.** `alert_gates.room_gate(print, doc.bands, doc.prev_close)`:
   ≥ 5% to the first unbroken band overhead (supply bands with `hi ≥ print`
   that did **not** close broken yesterday, plus demand bands above the print
   = broken support). **CLEAR** passes; **IN_BAND** fails (`alert gate: inside
   supply band …`); under 5% fails, quoted **raw at 2 dp** (`alert gate: room
   3.00% < 5% (supply 5.15-5.3)`) — the 1-dp display number can read
   "5.0% < 5%" at the 4.995% boundary, and `room_gate` itself now compares the
   unrounded pct (it used to rebuild it from a cents-rounded target and let
   4.995% through).
4. **Level.** Either the row's **bounce** read (`bounce_room.bounce_read`:
   touched a demand band or a broken-supply shelf within 5 sessions and lifted
   ≥ max(3%, 1 ATR) off it) **whose band still satisfies**
   `alert_gates.demand_proximity_gate(print, bounce.band)` — a bounce that
   already ran past 1% above the top lists on the board but is neither pushed
   nor bought (`alert gate: print 4.1% above bounce band top 97 (max 1%)`) —
   **or**, with no bounce read, a demand band that satisfies the proximity
   gate on its own (the highest such band anchors). Neither → skip `alert
   gate: not at a demand level (…)`. The journaled `proximity` carries
   `anchor: "bounce" | "band"`.
4. **Stop.** Anchoring **demand** band: `stop = band.lo × (1 − 0.5%)`; a pure
   bounce off a **broken-supply shelf** (no demand band under the read):
   `stop = shelf.lo`. `stop_pct = (print − stop) / print × 100`; `≤ 0` or past
   `risk_rules.ABS_MAX_STOP_PCT` → skip (never clamped). The stop is handed to
   `entries.enter` as the **absolute level** (`stop_price=`), so it rests at
   the band whatever the tape printed since; `entries` refuses on drift, never
   clamps.

Everything before the state write is a **skip** (re-read next tick), not an
attempt; the tick summary counts `skipped_alert_gate` and `skipped_pending`.

### Attempts, cap, held

Skips that are not attempts: flag off / disarmed / not configured / market
closed (one `catalyst_entry_disabled` ledger row per ET day), at/after 15:45,
no cached scan, symbol already held, daily cap reached, no position slot
(`risk_rules.MAX_POSITIONS`), same symbol already attempted today, every gate
failure above, a `market closed` veto from `entries`.

**Attempts** — one per `(symbol, ET day)`, written to `catalyst_entry_state`
**before** `entries.enter` is called, blocked / error attempts too. The store
**fails closed**: unreadable → the tick sits out (`state_unavailable`);
unwritable → no order. The `try/except` wraps only `entries.enter`; once it
returns an order exists and is always recorded `entered`.

`entries.enter(sym, limit_price=None, stop_pct=…, strategy="catalyst",
reason={quadrant, grade, catalyst_summary, room, bounce, proximity, side,
price, dollar_volume, print, print_basis: "catalyst scan price",
print_age_sec, stop_pct}, stop_price=stop, allow_earnings=False)`
— the journal lane tag (`docs/sepa/journal_analytics_methodology.md` §2a).

Ledger kinds: `catalyst_entry` (`dry_run=false`), `catalyst_entry_blocked`
(`dry_run=true`), `catalyst_entry_error` ("verify at the broker whether an
order exists"), `catalyst_entry_disabled` (once a day). Push on a buy:
owner-only, title `🗞️ Catalyst paper buy {SYM}` (the mode word follows the
broker: paper / sim / LIVE), body with the quadrant/grade, shares, print,
stop, band, room and the catalyst one-liner.

## 4. Wiring

- `exit_engine.get_config()` → `catalyst_entry` (default **False**) and
  `last_catalyst_entry_disabled_day`.
- `POST /trading/config {"catalyst_entry": true|false|null}` — strict boolean;
  `null` resets to **OFF**. Admin-gated like every trading route.
- `exit_engine.tick()` step **(j)**, right after (h) `zone_edge_entry` and
  before (g) `journal.reconcile`, fenced in its own `try/except` — a lane
  crash can never break stop protection.
- `GET /trading/status .catalyst_entry` (see §5).
- Autopsy: a losing catalyst round-trip is classified under strategy
  `catalyst` (its anchoring band is the floor, kind `demand`).

## 5. Reading the status block

```
catalyst_entry: {
  enabled, paper_only,   # DERIVED from the broker mode (false only in LIVE), never asserted
  entries_today, max_per_day: 1, last_entry_et: "15:45",
  as_of,            # the cached scan's as_of (null = no cached scan right now)
  scan: {cached, cache_age_sec, n_total} | null,
  rules: [{rule, value, source}],   # the table above, as data — the FE renders THIS
  candidates: [...],  # quality-funnel survivors: {symbol, quadrant, grade, catalyst_summary,
                      #  price, dollar_volume, change_pct, market_cap, composite_score,
                      #  day_low, day_high, prev_close} — the zone gate runs at tick time
  skipped:    [{symbol, reason}],   # funnel rejections
  attempts:   [...]   # today's catalyst_entry_state rows (pending/entered/blocked/error)
}
```

`candidates` is **not** "about to buy": it is the funnel's output from the
cached scan; the level gate (coverage, print age, room, bounce/proximity,
stop) runs at tick time and its skips show in the tick summary (`skipped[]`,
`skipped_alert_gate`, `skipped_pending`); the only place a **room read** lives
in this block is `attempts[]` (today's `catalyst_entry_state` rows, attempted
names only). `as_of: null` means the board has no fresh cached scan — the lane
is idle until someone opens the Catalysts board (and a name gets a zone doc
only once that board's bounce-room call has built it). Every `source` in
`rules[]` says whether the rule is Ajay's (dated quote), a builder default
(**NOT from Ajay**), or the shared risk contract.

The Trading page's `CatalystEntryCard` renders it as: Symbol (+ scan price) ·
Room (from today's attempt for that symbol, else an honest "—" whose tooltip
says the gate runs at tick time) · Why (= `catalyst_summary`) · State (=
`quadrant/grade`, plus `· entered|blocked|error` when attempted). Its one
write is the switch (`POST /trading/config {catalyst_entry}`); ON asks first
and names the account; the pill says "(paper)" unless the mode is LIVE.
`JournalByStrategy` on the same page shows `summary.by_strategy` per lane
(📈 minervini · 🧲 demand_zone · 🚀 breakout · 🗞️ catalyst · ✋ manual) with the
small-n honesty note, and every trade card wears its lane chip.

## 6. Ops recipe (paper)

```
POST /trading/arm?armed=true
POST /trading/config  {"catalyst_entry": true}
GET  /trading/status                        # .catalyst_entry.as_of non-null in RTH
GET  /trading/journal                       # summary.by_strategy.catalyst
```

Turn it off with `POST /trading/config {"catalyst_entry": false}` (or `null`).
Disarming stops every buy path at once.

## 7. Tests

- `tests/test_catalyst_entry.py` — owner settings locked; gates (flag,
  armed, configured, clock, 15:45); no-cache never scans; every funnel
  negative + the two positives; no-doc skip then enters next tick;
  `snap_from_scan` / `zone_rows` pure on a real doc (scan price = print,
  bounce read, `print_age_sec`); **run() with the payload builder, queue and
  provider seams rigged to raise still buys** (`test_run_never_reaches_the_
  tape_or_the_ondemand_queue`); stale-print skip at the phone's line (and
  exactly-at passes; unknown age fails closed); unavailable coverage; room
  IN_BAND / under-floor (raw 2 dp) / broken-lid / CLEAR / wide; **bounce
  anchor still needs the 1% proximity line** (95-97 band, print 101 skipped;
  97.5 bought; broken-supply shelf the same); demand-band proximity;
  stop from demand band vs broken shelf; stop past the engine max; one per
  day; held; state-before-enter (error), veto, market-closed, unreadable /
  unwritable state; status block shape; `paper_only` follows the broker mode
  (live → false); engine status degrade; config route (true / null / bad
  type / 403); tick step (j) fence; no direct broker call; no tape / no
  builder tokens in the source.
- `tests/test_trading_contracts.py` — constants verbatim, no book cites,
  `NOT from Ajay` present, fenced + configurable, `entries.enter(` +
  `_cache_get()` present, no `_full_scan(`; **the tick never reaches the
  tape or the on-demand builder** (source grep + `load_docs` / `read_symbol`
  / `snap_from_scan` / `zone_rows` / `STALE_PRINT_SEC` present).
- Frontend: `src/components/CatalystEntryCard.test.tsx` renders the exact
  backend shape (why ← `catalyst_summary`, state ← `quadrant/grade · result`,
  room ← today's attempt, "—" otherwise, never NaN).


## Warm cron (2026-09-05)

The tick never scans, never touches the tape and never builds zone docs (stop protection
stays fast). `python -m trading.catalyst_entry --warm` runs from the cron at `12,42 9-15 * *
1-5` (owner setting `WARM_CRON`, pinned to `backend/crontab` by a test) and keeps the lane's
two inputs populated: the Catalysts scan (the board's cache when fresh, else the board's own
`_full_scan(with_gemma=True)` written to the same cache, so the board and the lane read one
payload) and the `bounce_room` zone docs for every candidate missing one (synchronous
`compute_batch`, bounce_room's own budget). Returns counts (`scan`, `candidates`,
`docs_have`, `docs_built`, `docs_missing`, `error`); never raises. Without it the lane could
only fire on a day someone had opened the Catalysts board.
