# 🎯 ENTERABLE — the one read that says whether a name can be entered right now

Ajay 2026-09-15, verbatim: *"We really need to figure out the entries, I only
wanna see the stocks that are enterable. i don't know if its volume burst or
candle stick patterns we need to read. Research the best strategy and make sure
its applicable across all chart maps. I do not want to see not enterable alerts
or stocks in any of the chart maps. ... look for any good tested entry methods or
strategies and apply them. across board.."*

Code: `backend/supply_demand/enterable.py` (the read — ONE function, kind-aware),
`backend/scripts/entry_trigger_study.py` (the measurement of the entry TRIGGER
question), `backend/scripts/entry_trigger_measured.json` (what the run wrote —
the dict is pasted from it, never typed), `frontend/src/lib/enterable.ts` +
`components/EnterableChip.tsx` / `EnterableOnlyToggle.tsx` / `HiddenCount.tsx`
(the mirror, the chip, the filter, the count line).

**Owner rules on price structure. No book, no cites — Supply & Demand scope,
never Minervini (`CITED = False`). Nothing here buys, sizes, arms a lane or
touches a broker.** Every threshold in the read is IMPORTED from the module that
already enforces it; the read invents none.

> **STATUS: `no_signal`** (run 2026-09-15). See §7 for every number; nothing here is typed.

---

## 1. The ask

Three separable things sit inside that paragraph, and they are answered in three
different ways:

| what he asked | how it is answered |
|---|---|
| "only wanna see the stocks that are enterable" | a **filter** on every Chart Maps tab, default ON, that hides only `BLOCKED` rows and always prints how many it hid and why |
| "I do not want to see not enterable alerts" | the verdict is **recorded on every pushed row** and shown on the Alerts page; the 🪃 kind gets the standing floor gate it was missing |
| "volume burst or candle stick patterns ... look for any good tested entry methods" | **measured**, not chosen — `backend/scripts/entry_trigger_study.py` (§5). A trigger ships only if it beats the rows that survived to the same bar without it |

"Tested" here means MEASURED on his own cached universe with the explosive
study's rule of reading (date-clustered CI, date-block placebo, three
out-of-sample splits, a minimum detectable lift, a room×risk reweight,
one-per-date and one-per-symbol checks). No book formula, no internet stat, no
invented threshold. Anything that does not clear that bar is reported as a null
**with its number** and gates nothing.

---

## 2. What this is, and what it is NOT

**It is a read, a filter and a recorded verdict.** Three verdicts —
`READY` / `WATCH` / `BLOCKED` — from `premarket_entry.GRADE_READY/WATCH/BLOCKED`,
the grader that already shipped on the ⚡ Signals "Ready to enter" section. There
is exactly ONE grader: `enterable.grade()` wraps `premarket_entry.grade_row()`
and adds the floor state; it does not re-implement it.

**It is not a new gate on your phone.** On all four demand push kinds
(`demand_alert`, the zone-edge demand lane, the 🚀 growth demand push and — once
§9.5 is answered — 🪃 `zone_bounce_alert`) every input the read grades has
ALREADY gated before the read runs: proximity and room (the two standing gates),
direction = reversing, floor = intact (`floor_held_gate`). The gates are passed
THROUGH to `assess()`, not recomputed, so `BLOCKED` on a push path is literally
unreachable. `skipped_not_enterable` is a **divergence guard, expected to stay
0** — a non-zero count is a bug to report, never the explanation for a quiet
phone. Read the quiet-phone counters in
[`alerts_page.md`](alerts_page.md) §4 as before.

What the phone actually GAINS:

1. the verdict persisted on every pushed row (the Alerts page chip), and
2. on 🪃, the standing floor gate the other three kinds have had since
   2026-09-09 (§9.5 — his call; measured swept 22.7% / broken 21.5% vs intact
   30.7%).

**It buys nothing.** No lane reads it, no order is sized by it, no LIVE switch,
no broker key, no crontab change. It gates one thing only: what a Chart Maps tab
SHOWS, and one click (`?show=all`) puts everything back.

**It is not a per-strategy entry rule.** The read is a demand-reversal read. A
VCP pivot, a 52-week-high winner, a topping structure, an earnings event, a
0DTE row or a value screen is not a demand reversal, so those tabs are `n/a`
(§4) — an "enterable" verdict for a pivot needs its own measured basis
(Rule #1), not this one dressed up.

---

## 3. The verdict — every reason code, with the constant that enforces it

`enterable.grade(kind, room_ok, prox_ok, floor_state, drags, survivor)` returns
`(verdict, reasons)`. Mood is **not** a parameter (it is context, never a gate —
same rule as `premarket_entry.grade_row`, pinned by an AST test).

### 3.1 Kind — the read is kind-aware

| kind | rows | what decides it |
|---|---|---|
| `demand` | a name in / near a demand band (the 🧲 read) | the two standing gates + the floor + the two measured drags |
| `supply_break` | 🚀 Breaking rows | room to the NEXT lid only (`zone_edge.next_lids` — the ONE next-lid list, extracted from the supply lane so there is no second copy) |
| `n/a` | tabs whose rows are not demand reversals | no verdict at all; the chip says so, the filter goes inert |

### 3.2 Demand rows — the reason codes

`BLOCKED` codes are appended in this order — `no_band`, `proximity`, `room`,
`floor_<state>` — and the fixture pins the order so the frontend can key on
`reason_short[0]`.

| code | what it means | enforcing constant / source measurement |
|---|---|---|
| `no_band` | no demand band at or below the print | `bounce_room.demand_read` returned None |
| `proximity` | the print is more than 1% above the band's top (or below its floor) | `alert_gates.demand_proximity_gate`, `ALERT_MAX_ABOVE_DEMAND_PCT` (1.0) — the standing push gate |
| `room` | less than 5% to the first proven lid, or standing IN a supply band | `alert_gates.room_gate`, `ALERT_MIN_ROOM_PCT` (5.0), `LID_MIN_TOUCHES` (2) — the standing push gate |
| `floor_<state>` | the band floor did not hold in the session | `alert_gates.sweep_read` state ∉ `alert_gates.FLOOR_HELD_STATES`. **The state word is never typed in the source** — it comes out of the sweep read, so a sweep state nobody has seen before reads BLOCKED, never READY (the failure mode this rule exists to prevent) |

`WATCH` codes — shown, never hidden:

| code | what it means | source measurement |
|---|---|---|
| `reclaim` | the print reclaimed the band from BELOW | `premarket_entry.approach_drag` reading `approach_read`'s `dir` (never the display `tag` — that bug graded every reclaim READY once); `RECLAIM_STOP_PCT` 66.0 vs `ARRIVAL_STOP_PCT` 11.0 floor-stop, autopsy 2026-09-08, n=286 |
| `weak_day` | the day is between −8% and −3% | `premarket_entry.day_change_drag`; `WEAK_DAY_LO_PCT` / `WEAK_DAY_HI_PCT`, `WEAK_DAY_UP_PCT` 22.0 vs `NORMAL_DAY_UP_PCT` 57.0, same autopsy |
| `floor_unknown` | there is no closed-bar tail yet, so the floor state could not be read | unknown ≠ swept. On BOARDS unknown is WATCH and stays visible (§9.3). On PUSHES the standing gate fails CLOSED and drops it — the two are deliberately different, and the doc says which is which |
| `survivor_<key>` | the study's trigger has not fired at a close yet | §5. **Empty today**: the 2026-09-15 run measured `no_signal` and `MEASURED["survivor"]` is `none`, so no `survivor_<key>` code is served by any surface. The code exists for the day a trigger clears (a)-(f) — not because a study is still running |

`READY` = the two gates pass, the floor is in `FLOOR_HELD_STATES`, no drag, and
(when a survivor is wired) the trigger has fired at a close.

### 3.3 Supply-break rows

`READY` when room to the next lid passes `room_gate`, `BLOCKED ["room"]`
otherwise. Drags, floor and the survivor are ignored by construction: the
existing gate IS the rule, and adding anything to it would be a new gate (§9.6).

The two "no break" codes in `EN.BLOCK_CODES` — they say **opposite** things and
the doc has to name both, because `read_breaking` returns `None` for each:

| code | when it fires | served text (`REASON_TEXT` / `REASON_SHORT`) | verdict |
|---|---|---|---|
| `no_break` | the print is not breaking a lid at all | "not breaking a lid at this print" · short `no lid break` | BLOCKED |
| `break_extended` | the print HAS cleared a lid (the highest supply band yesterday's close sat at or under) and is now further through it than `zone_edge.BROKE_MAX_PCT` — the lane's own break window, read lazily by `_broke_max_pct()`, never typed in this module | "the print is N% above the lid ($lo–$hi) it cleared — more than the \<window\>% through the lid this read follows, so the break is extended" · short `break > <window>%`, and `break extended` with no number when the constant cannot be read | BLOCKED — **his call, §7.6**: a chase past the window is not an entry |

`break_extended` returns `None` (so the row falls back to `no_break`) when the
previous close is unknown — the same limit the lane has, since it cannot tell
"broke today" either.

### 3.4 Two shapes that look the same and are not

**CLEAR vs unreadable.** `alert_gates.room_read` returns `None` twice: once for
CLEAR (open sky overhead — the best case) and once for an unusable print (the
worst). The served block tells them apart: `room_ok` True with no room block →
`{"state": "CLEAR", "room_pct": null, "target": null}` (READY is possible); an
unusable print → `room: null`, `room_ok` False, BLOCKED. Nothing downstream has
to guess.

**Which print.** The tile read keys on the **LIVE print and the session low**
from the same `prices.bulk_live_prices` fan-out the now-lines already use — an
"enterable" verdict computed on yesterday's close would call a name READY that
swept its floor this morning. When the tape is down or the name has no
snapshot, the read falls back to the closed scan print and SAYS so:
`print.source` is served, and the chip title reads "closed-bar read (no live
print)" (§9.17). The 🧨 explosive read keeps its own pinned choice (the scan
print) — ENTERABLE does not inherit it.

**Board band vs push band.** A tile grades the BOARD's band
(`bounce_room.demand_read`, the highest-`hi` band at or below the print); a push
grades the band the alert itself fired on. They can differ on a name with two
bands. The Alerts page shows the PUSH-TIME verdict on the push's own band; the
tile shows the board band's. That is intentional, and it is why the Alerts page
does not join client-side.

---

## 4. Where the read shows

### 4.1 Chart Maps tiles

`chart_maps/board.py` makes ONE live snapshot for the shown tiles, feeds it to
the now-line overlay AND to `attach_enterable`, which writes `t["enterable"]`.
The read therefore covers the tiles that are SHOWN (after the `limit` cut) —
the count line says "of the N shown", and reading the tiles before the cut is
§9.15, his call. The payload also carries `enterable_kind` and
`enterable_study`.

### 4.2 The filter and the count line

* Toggle **🎯 Enterable only**, default **ON** on Chart Maps (`?show=all` turns
  it off; URL only — no localStorage, so it never silently persists into
  tomorrow).
* It hides **BLOCKED only**. READY and WATCH are both shown (§9.1).
* Rows with **no read** (pending doc, legacy doc, warming store) are **never
  hidden** — they are placed last and counted separately as "without a read".
  Unknown is not "not enterable".
* The count line **always renders when the filter is on, even at 0 hidden**,
  with the top-3 reasons: `30 hidden (22 no band · 8 room < 5%) · show all`.
  Nothing is ever lost silently. One click restores.
* On a big list (a 2,500-name board) the first ~30 seconds after load every row
  is unread while the read poll fills, so the line reads
  `0 hidden · 1,800 without a read (shown last)`. That is expected, not a bug.
* **📁 My holdings never partitions** — a position is never hidden by an entry
  filter. The **Support** tab is one symbol and is chip-only. **🔥 Hot sectors**
  filters the rows the server already cut, and its count line says so.
* On the `n/a` tabs the toggle is disabled and the line says
  *"no demand read for this tab · filter off"*.

### 4.3 The `n/a` tabs, by name

`vcp`, `winners`, `topping`, `earnings`, `zero_dte`, `undervalue` — pivots,
highs, lids, events, options and value screens. Every other tab is `demand`
except `breaking`, which is `supply_break`. The per-tab hide rate measured on
the live payload goes to him with §9.16, and he moves tabs between `demand` and
`n/a` with those numbers in hand.

### 4.4 Rows, pushes, the Alerts page, the rules panel

* Every `POST /supply-demand/bounce-room` row carries `enterable`; the payload
  carries `enterable_study`. Contract in [`bounce_room.md`](bounce_room.md).
* Every demand push carries the slim read (`kind`, `verdict`, `reasons`,
  `reason_text`, `reason_short`), persisted by `push/history.record` and passed
  through `/notifications/recent`, so the Alerts page shows the verdict the row
  had AT PUSH TIME.
* `GET /alerts/status` → `gate.enterable_status`; the counters
  `skipped_not_enterable` and (on 🪃) `skipped_floor` ride the pass counts.
  Labels in [`alerts_page.md`](alerts_page.md) §4.
* `GET /supply-demand/rules?section=enterable` builds every line from the
  enforcing constants — who is READY, what makes it WATCH, what the pushes
  already do, which tabs have no demand read, the study's own status, and
  "NOTHING HERE BUYS".

---

## 5. The study — `backend/scripts/entry_trigger_study.py`

The question is NOT "which stock" (measured null on 2026-09-15: RSI, relative
volume, ATR, Keltner coil, the AMD raid, CMF, dollar volume and the 52-week box
all came in under the 2.2pp resolution of that study). The question is **WHEN
inside the episode**: does an entry TRIGGER or a CONFIRMATION lift the read?

**Event.** The touch bar `j` from `studies/bounce_quality_study.events()` —
point-in-time bands, closed bars, the same replay the explosive study ran. The
band, the stop (band floor − `STOP_BUFFER_PCT`) and the target (the first proven
lid at `j`) are the event's own and never move with the entry.

**Conventions (each has its own entry, and therefore its own room and risk):**

| key | fires when | entry |
|---|---|---|
| `P` | always — the engine baseline | close of the touch bar |
| `N` | the next open is above the stop | the next open |
| `PC` | always — the same-close twin of P, **print-only** | close of the touch bar |
| `D1…D3` | unconditional delay, skipped if the stop is hit first | that close |
| `C1` | first close above the touch bar's high, within the window | that close |
| `C2` | first close back above the band top, within the window | that close |
| `HL` | a confirmed higher low that no later bar undercut | that close |
| `L1` | the first close at or above +1% (`premarket_entry.CONFIRM_MAX_LIFT_PCT`) — the autopsy's "after the lift", re-measured | that close |

Candle-shape and volume families ride on top: close position in the bar's range,
lower-wick share, body share, up-close, close above the prior high, engulfing,
inside bar, gap-up next open, relative volume at the bar and before it,
up-vs-down volume over the prior 10 bars. These are DATA columns — no book is
cited for any of them.

**The trap this study was rewritten around.** A trigger that fires at bar `k`
IS a delay-`k` entry on that same row: same entry price, same stop, same target,
same forward bars, therefore the same outcome by identity. A "matched delay"
placebo is 0 by construction. That identity is now PINNED by a test so nobody
reintroduces it, and the deciding lift is a **conditional contrast**: rows where
the trigger fired at `k` against OTHER rows that reached `k` unstopped and did
not fire, pooled across fire bars with one shared date resample. Beside it the
report prints what WAITING alone buys, so the reader can see how much of the raw
difference is survival rather than signal.

**What it takes to ship.** A convention ships as the `survivor` only if all of:
the conditional lift clears its own minimum detectable lift with a CI above
zero; stop-outs do not get worse; the room×risk reweight keeps the sign;
entering only when it fires does not cost expectancy against entering at the
print AND beats the matched waiting policy; one-per-date and one-per-symbol both
positive; and every one of the three out-of-sample splits agrees. `PC` is
**print-only and never ship-eligible** — a bar's shape is not knowable when a
market-on-close order is placed, so it is reported to show what a same-close read
WOULD have said and can never be selected.

**The interaction table is context, and says so.** The family-5 cells (floor
intact × the top candle bucket, floor intact × a fired `C1`) have no reweight and
no policy column, so a cell can clear the first condition and nothing else.
`select_survivor` never reads them, and since 2026-09-15 they print `cushion` or
`not selected` — never `separates`, which in this study means the full (a)-(f)
guard passed. Same for the fire rates: every convention is reported over the
whole episode cohort, so an episode a convention could not enter (`gap_N`,
`no_bars`) shows up in `n_skipped` instead of shrinking the denominator.

**Windows are the brief's numbers, not his** — confirmation within 3 bars, a
higher low within 10, delays 1/2/3, a 120-row cell floor. They are labelled
"brief 2026-09-15 — unconfirmed" in the code, the JSON, the report and here;
§9.11 asks him to confirm or replace them, and the 1/2/3/5 window sweep prints
beside them.

**How a survivor plugs in, and the precondition.** The paste script sets
`MEASURED["survivor"]`; `enterable.status()` then reads `separates`, and
`assess()` calls `survivor_read()`, which **replays the study's own `event_at`
and `trigger_*` functions on CLOSED bars** — there is no third definition of the
touch anywhere in the app, and the live print is never the trigger. If the
replayed event lands on a different band than the one served, the reader refuses
and returns unknown rather than guessing. A survivor is wired live ONLY after
its mirror test (backend read vs the study's own function, on the same synthetic
tail) is green.

---

## 6. Verify in the container (read-only)

Smoke the study first (never during RTH — the hourly cache patch rewrites frames
from ~10:00 ET). Both scripts are piped to `/tmp` because the container runs
`origin/main`, which has neither:

```
docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/explosive_study.py' < backend/scripts/explosive_study.py
docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/entry_trigger_study.py' < backend/scripts/entry_trigger_study.py
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u /tmp/entry_trigger_study.py --stage both --universe broad --floor 120 --stride 18 --out /tmp/entry_smoke.csv --json /tmp/entry_smoke.json'
```

Every line of a `--stride` / `--names` run prints under the banner
`NOT QUOTABLE — smoke` and the JSON carries `quotable: false`. The full run:

```
docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u /tmp/entry_trigger_study.py --stage replay --universe broad --floor 120 --out /tmp/entry_events.csv > /tmp/entry_broad.log 2>&1'
docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u /tmp/entry_trigger_study.py --stage replay --universe cache --floor 120 --out /tmp/entry_events_cache.csv > /tmp/entry_cache.log 2>&1'
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u /tmp/entry_trigger_study.py --stage stats --from-csv /tmp/entry_events.csv --cache-csv /tmp/entry_events_cache.csv --json /tmp/entry_measured.json --emit-measured'
```

The cache-universe (survivorship) replay is a **separate** run, and it is a
precondition, not a footnote: `quotable` is true only when BOTH halves hold — no
`--stride` / `--names` subsample AND the survivorship line in hand — and
`quotable_reasons` names each reason it is false, so the flag can never disagree
with the report's own "NO NUMBER ABOVE IS QUOTABLE WITHOUT THE CACHE LINE"
banner. The first stats run given `--cache-csv` parks its computed block at
`<cache-csv>.survivorship.json`, and a later run MERGES it without re-reading the
events cache — either explicitly or from that sidecar:

```
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u /tmp/entry_trigger_study.py --stage stats --from-csv /tmp/entry_events.csv --survivorship /tmp/entry_events_cache.csv.survivorship.json --json /tmp/entry_measured.json --emit-measured'
```

`d_hit5_vs_broad` is always RECOMPUTED against the broad base of the run doing
the merge — nothing about the broad cohort is carried over from the file — and a
sidecar with no `cache_hit5_20` is refused rather than half-merged.

Then the numbers reach the repo **mechanically, never by hand** — the paste
script writes the JSON beside the script, the `MEASURED` literal in
`supply_demand/enterable.py`, the study's `RESULTS` docstring, §7 of this file
and the ✨ label, and round-trips the literal through `ast.literal_eval` to prove
it equals the JSON:

```
python3 <scratch>/enterable/paste_measured.py <scratch>/enterable/entry_measured.json
python3 <scratch>/enterable/paste_measured.py <scratch>/enterable/entry_measured.json --apply
```

(the first is a dry run that prints the diff and touches nothing).
`test_measured_dict_equals_the_shipped_json` fails on any drift, so no number is
ever retyped — not into the module, not into this doc, not into TSX.

The live read, on a store doc (worktree code needs the `/tmp/wt` overlay — keep
`alert_gates.py` in it; container main's `sweep_read` has an older signature):

```
docker exec -w /tmp/wt cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -c "
from supply_demand import zone_store, enterable
day, docs = zone_store.load_latest([\"CRDO\"])
d = docs.get(\"CRDO\")
r = enterable.read(doc=d, px=d[\"prev_close\"], print_source=\"scan\")
print(r[\"verdict\"], r[\"reasons\"], r[\"reason_text\"])
print(enterable.measured_verdict()[\"headline\"])"'
```

Branch API on :8001 (his surface, not a localhost link for him —
the app is https://pounce.ajaykandakatla.dev):

```
curl -s -H "X-User-Email: <his address>" 'http://127.0.0.1:8001/chart-maps?tab=zones&limit=24'
curl -s -H "X-User-Email: <his address>" 'http://127.0.0.1:8001/chart-maps?tab=vcp&limit=24'
curl -s -H "X-User-Email: <his address>" 'http://127.0.0.1:8001/alerts/status'
```

Tests: `backend/tests/test_enterable.py` (the read + the mirror fixture),
`backend/tests/test_enterable_wiring.py` (every surface it is served on),
`backend/tests/test_entry_trigger_study.py` (the study),
`frontend/src/lib/enterable.test.ts` (the same fixture, the same partition),
`EnterableChip.test.tsx`, `HiddenCount.test.tsx`, `ChartMaps.test.tsx`,
`Alerts.test.tsx`, and the contract in `frontend/scripts/contracts.mjs`.

---

## 7. MEASURED

**Run 2026-09-15 · status `no_signal`** — every number below is read from
`backend/scripts/entry_trigger_measured.json` (committed beside the script) and
pinned equal to `enterable.MEASURED` by `test_measured_dict_equals_the_shipped_json`.
Nothing here is typed; the paste script wrote it.

| | value |
|---|---|
| cohort | 3,585 names · 92,732 reversal events · **24,922 episodes** · 361 dates · 2025-03-10 -> 2026-08-14 |
| base rate P (enter at the print) | HIT5@20 **34.2 %** · stop@20 74.5 % · HIT_LID@20 21.2 % · R20 0.288 |
| windows (brief 2026-09-15 — unconfirmed, §9.11) | confirmation 3 bars · higher low 10 bars · delays [1, 2, 3] |
| cell floor | 120 rows — a smaller cell is not shown |
| intact reconciliation | {'d_hit5_P': 8.297637442664257, 'n_intact': 7166, 'expected_2026_09_15': 8.3} |
| survivorship (cache universe) | 5,277 names · 37,317 episodes · HIT5@20 32.7 % · stop@20 77.0 % · Δ vs broad -1.48pp (cache-csv:/tmp/ets_cache_events.csv) |
| **survivor** | none — no trigger is wired into the read; fallback P — enter at the print; the READY read is unchanged |
| selected · fallback | [] · P — enter at the print; the READY read is unchanged |
| quotable | True |

> `quotable` is the sample test **and** the survivorship replay, never one of them
> (fixed 2026-09-15). A run that has not merged its cache-universe line reads `false`
> with the reason named, and `--stage stats` merges that line from a separate
> `--cache-csv` run via `--survivorship <json>` or the sidecar beside the events cache
> (§6). A `true` sitting beside a `pending the cache replay` survivorship row means the
> committed `entry_trigger_measured.json` predates that fix: re-run and re-paste before
> quoting anything in this section. The null verdict itself does not depend on it.

The conventions — `n fired`, the fire rate, the hit rate from that entry, the
**conditional lift** (fired rows against UNFIRED rows that reached the same bar
unstopped) with its date-clustered CI and its own minimum detectable lift, the
policy expectancy against entering at the print, and the pre-registered verdict:

| convention | n fired | fire rate | HIT5@20 | conditional lift | Δ policy R | verdict |
|---|---|---|---|---|---|---|
| `N` | 22,884 | 0.918 | 35.0 % | **n/a** CI n/a (MDL n/a) | -0.100 | no_signal |
| `PC` | 24,922 | 1.000 | 34.2 % | **n/a** CI n/a (MDL n/a) | 0.000 | no_signal |
| `D1` | 15,059 | 0.604 | 44.6 % | **n/a** CI n/a (MDL n/a) | -0.169 | no_signal |
| `D2` | 12,243 | 0.491 | 48.3 % | **n/a** CI n/a (MDL n/a) | -0.198 | no_signal |
| `D3` | 10,615 | 0.426 | 51.0 % | **n/a** CI n/a (MDL n/a) | -0.245 | no_signal |
| `C1` | 7,876 | 0.316 | 53.6 % | **+7.03pp** CI [+5.75, +8.36] (MDL 0.93) | -0.271 | no_signal |
| `C2` | 6,467 | 0.259 | 52.2 % | **+6.32pp** CI [+5.00, +7.60] (MDL 1.07) | -0.265 | no_signal |
| `HL` | 5,905 | 0.237 | 57.4 % | **+8.00pp** CI [+6.48, +9.53] (MDL 1.28) | -0.284 | no_signal |
| `L1` | 10,390 | 0.417 | 52.3 % | **+6.40pp** CI [+5.49, +7.37] (MDL 0.79) | -0.255 | no_signal |

Per-feature top buckets, convention N (ship-eligible) and PC (print-only — a
bar-j shape is not knowable when a market-on-close order is placed, so PC can
never be selected):

```
    rvol20_pre           top=Q1    ΔHIT5@20 +0.33pp   CI [-1.20, +1.83]     Δstop +0.85pp   reweighted +0.03pp   → inert
    rvol50_pre           top=Q1    ΔHIT5@20 +0.28pp   CI [-1.11, +1.60]     Δstop +0.96pp   reweighted -0.06pp   → inert
    updn_vol10_pre       top=Q1    ΔHIT5@20 +0.95pp   CI [-0.55, +2.43]     Δstop -0.64pp   reweighted +0.62pp   → inert
    above_sma50_pre      top=no    ΔHIT5@20 +0.42pp   CI [-0.46, +1.34]     Δstop +0.89pp   reweighted +2.29pp   → inert
    close_pos_at         top=Q1    ΔHIT5@20 +0.35pp   CI [-1.46, +2.19]     Δstop +2.01pp   reweighted +0.19pp   → inert
    lower_wick_at        top=Q1    ΔHIT5@20 +1.13pp   CI [-0.32, +2.63]     Δstop -0.20pp   reweighted +0.32pp   → inert
    body_at              top=Q5    ΔHIT5@20 +0.20pp   CI [-1.48, +1.85]     Δstop -0.04pp   reweighted -0.20pp   → inert
    up_close_at          top=yes   ΔHIT5@20 +0.43pp   CI [-1.13, +1.99]     Δstop -2.08pp   reweighted -0.49pp   → inert
    close_gt_prev_high_at top=yes   ΔHIT5@20 +1.07pp   CI [-1.71, +3.92]     Δstop -3.77pp   reweighted -1.33pp   → inert
    engulf_at            top=yes   ΔHIT5@20 +3.33pp   CI [-2.67, +9.57]     Δstop -5.96pp   reweighted -0.02pp   → inert
    inside_at            top=no    ΔHIT5@20 +0.09pp   CI [-0.20, +0.36]     Δstop -0.17pp   reweighted -1.09pp   → inert
    rvol20_at            top=Q5    ΔHIT5@20 -0.46pp   CI [-2.09, +1.12]     Δstop -1.13pp   reweighted -0.97pp   → inert
    gap_up_next          top=yes   ΔHIT5@20 +10.90pp  CI [+7.94, +14.06]    Δstop -18.20pp  reweighted +0.65pp   → selects smaller trades
    weak_day_at          top=yes   ΔHIT5@20 +0.34pp   CI [-1.31, +2.00]     Δstop +2.20pp   reweighted +0.48pp   → inert
    intact_at            top=yes   ΔHIT5@20 +6.90pp   CI [+5.44, +8.41]     Δstop -7.99pp   reweighted +3.19pp   → selects smaller trades
```

```
    rvol20_pre           top=Q1    ΔHIT5@20 -0.41pp   CI [-1.96, +1.08]     Δstop +1.25pp   reweighted -1.03pp   → inert  [PRINT-ONLY]
    rvol50_pre           top=Q1    ΔHIT5@20 +0.29pp   CI [-1.07, +1.64]     Δstop +1.15pp   reweighted -0.05pp   → inert  [PRINT-ONLY]
    updn_vol10_pre       top=Q1    ΔHIT5@20 +1.59pp   CI [+0.08, +3.10]     Δstop -0.83pp   reweighted +1.88pp   → selects wider stops  [PRINT-ONLY]
    above_sma50_pre      top=no    ΔHIT5@20 +0.32pp   CI [-0.60, +1.29]     Δstop +0.97pp   reweighted +2.40pp   → inert  [PRINT-ONLY]
    close_pos_at         top=Q1    ΔHIT5@20 +0.77pp   CI [-1.13, +2.68]     Δstop +1.99pp   reweighted +1.87pp   → inert  [PRINT-ONLY]
    lower_wick_at        top=Q1    ΔHIT5@20 +1.06pp   CI [-0.44, +2.65]     Δstop -0.12pp   reweighted +0.85pp   → inert  [PRINT-ONLY]
    body_at              top=Q5    ΔHIT5@20 -0.16pp   CI [-1.91, +1.56]     Δstop +0.08pp   reweighted +0.01pp   → inert  [PRINT-ONLY]
    up_close_at          top=yes   ΔHIT5@20 +0.33pp   CI [-1.27, +1.93]     Δstop -2.32pp   reweighted -1.43pp   → inert  [PRINT-ONLY]
    close_gt_prev_high_at top=yes   ΔHIT5@20 +0.60pp   CI [-2.29, +3.55]     Δstop -4.88pp   reweighted -4.07pp   → inert  [PRINT-ONLY]
    engulf_at            top=yes   ΔHIT5@20 +3.71pp   CI [-2.45, +10.20]    Δstop -7.14pp   reweighted +0.16pp   → inert  [PRINT-ONLY]
    inside_at            top=no    ΔHIT5@20 +0.20pp   CI [-0.08, +0.47]     Δstop -0.21pp   reweighted +0.40pp   → inert  [PRINT-ONLY]
    rvol20_at            top=Q5    ΔHIT5@20 -0.31pp   CI [-2.10, +1.42]     Δstop -0.92pp   reweighted +0.22pp   → inert  [PRINT-ONLY]
    weak_day_at          top=yes   ΔHIT5@20 +0.03pp   CI [-1.62, +1.72]     Δstop +2.74pp   reweighted +1.02pp   → inert  [PRINT-ONLY]
    intact_at            top=yes   ΔHIT5@20 +8.30pp   CI [+6.66, +9.93]     Δstop -9.16pp   reweighted +3.79pp   → selects smaller trades  [PRINT-ONLY]
```

Stratifiers (the rule of reading carried over from the 2026-09-15 explosive study):

```
    intact_at            top=yes   ΔHIT5@20 +8.30pp   CI [+6.66, +9.93]     Δstop -9.16pp   reweighted +3.79pp   → selects smaller trades
    weak_day_at          top=yes   ΔHIT5@20 +0.03pp   CI [-1.62, +1.72]     Δstop +2.74pp   reweighted +1.02pp   → inert
    above_sma200_pre     top=yes   ΔHIT5@20 +0.69pp   CI [-1.02, +2.32]     Δstop -2.41pp   reweighted +0.05pp   → inert
    rs20_pre             top=Q1    ΔHIT5@20 +1.91pp   CI [+0.10, +3.68]     Δstop +3.03pp   reweighted +2.28pp   → selects wider stops
    above_sma200_pre     top=yes   ΔHIT5@20 +0.41pp   CI [-1.22, +1.92]     Δstop -2.25pp   reweighted -0.42pp   → inert
    rs20_pre             top=Q1    ΔHIT5@20 +1.99pp   CI [+0.21, +3.71]     Δstop +2.91pp   reweighted +1.51pp   → selects wider stops
    above_sma200_pre     top=yes   ΔHIT5@20 +0.69pp   CI [-1.02, +2.32]     Δstop -2.41pp   reweighted +0.05pp   → inert  [PRINT-ONLY]
    rs20_pre             top=Q1    ΔHIT5@20 +1.91pp   CI [+0.10, +3.68]     Δstop +3.03pp   reweighted +2.28pp   → selects wider stops  [PRINT-ONLY]
```

What the read stood on BEFORE this run, and still does — every one of these was
measured, none is retyped into any gate:

| read | number | source |
|---|---|---|
| base rate, reversal episodes at board demand bands | 34.2% make +5% before the floor within 20 sessions; 74.5% hit the stop first | explosive study 2026-09-15 (24,922 episodes, 3,585 names, 361 dates) |
| the ONE separator | floor intact **+8.30pp** hit CI [+6.66, +9.93], stop-outs **−9.16pp** | same run, confirming 2026-09-09 |
| reclaim from below | 66% floor-stop vs 11% | autopsy 2026-09-08, n=286 |
| a −3..−8% day | 22% up vs 57% | same autopsy |
| buying after the +1% lift | wins 23% (≈ the base) | same autopsy — re-measured here as `L1` |

## 8. Limits

1. **The read is only as good as the gates it wraps.** Two of the three inputs
   (room, proximity) were never themselves measured against a placebo — they are
   his standing rule, and this work does not re-litigate them. The floor was
   measured, twice.
2. **No placebo for the verdict itself.** We know reclaims and weak days are
   worse and that an intact floor is better; we do not yet know that a READY
   name beats a random name at a level. That is the same limit
   [`premarket_entry.md`](premarket_entry.md) carries, and the entry-trigger
   study does not close it — it answers WHEN, not WHETHER.
3. **The filter counts the SHOWN tiles.** 24 tiles with 20 hidden leaves 4. The
   count line says so; raise `limit`, or §9.15.
4. **Tile verdict and push verdict can differ** on a name with two bands (§3.4).
5. **Day one every doc without a closed-bar tail reads `floor unknown`** until
   the 04:05 warm — WATCH, shown, explicitly labelled.
6. **Pre-market there is no session low.** The floor read takes its closed-window
   path, which pre-market IS the truth; `gates.session_low` is served false so
   the chip title can say so.
7. **`PremarketEntry` (⚡ Signals ▸ Ready to enter) is untouched** and can say
   READY where this read says BLOCKED on a swept floor — it has no floor input.
   Unifying them is §9.13.
8. **The study is a study.** Until §7 says `separates` with a key, no trigger
   gates anything, and the honest sentence is "no lift larger than the study's
   resolution", not "nothing works".

---

## 9. HIS CALLS — listed, not decided (spec defaults in brackets)

1. **What "Enterable only" hides** — [hide BLOCKED only; READY + WATCH shown] vs
   READY only.
2. **Rows without a read** (pending / legacy docs / no band read yet) — [shown,
   placed last, counted "without a read"] vs hidden.
3. **Floor unknown on BOARDS** (no closed-bar tail yet) — [WATCH
   `floor_unknown`, shown] vs BLOCKED. (On pushes the standing gate fails closed
   — unchanged.)
4. **WATCH rows and the phone** — [WATCH pushes, the drag named in the body;
   BLOCKED never pushes] vs WATCH = no push (= autopsy proposal A: skip the
   −3..−8% day).
5. **🪃 `zone_bounce_alert` gets the standing floor gate** (the identical
   `sweep_read` + `floor_held_gate` call, fails closed; today un-gated on the
   floor; measured swept 22.7% / broken 21.5% vs intact 30.7%) — [apply, counted
   `skipped_floor`] vs leave that kind alone (then the read on 🪃 rows is
   informational WATCH `floor_unknown`).
6. **🚀 supply-break read = room ≥ 5% to the next lid only** (the existing gate)
   — any extra condition is a new gate.
7. **An un-fired study survivor** — [WATCH `survivor_<key>`] vs BLOCKED; whether
   a survivor should ALSO gate pushes [no — boards + push body only]; a survivor
   is wired live ONLY after its mirror test is green.
8. **Default ON off Chart Maps** (`/catalysts`, `/patterns`, `/signal-lab`
   standalone) — [OFF there, unchanged] vs ON everywhere.
9. **Hot sectors** — [client-side filter on the server-cut rows, count says so]
   vs a server-side enterable cut.
10. **Labels**: chip words [`🎯 READY` / `🎯 WATCH · reason` / `⛔ reason` /
    `n/a`], toggle label [`🎯 Enterable only`], rules-section title, the ✨ label
    text.
11. **Study windows from the brief** (NOT in the verbatim ask): confirmation
    within 3 bars, higher-low within 10, delays 1/2/3, cell floor 120 — confirm
    or replace; the C1 window sweep 1/2/3/5 prints beside them; the doc calls
    them "brief numbers, unconfirmed".
12. **Study primary outcome** [HIT5 from the entry price] vs HIT5B (from the band
    top) vs HIT_LID — all three are in the JSON.
13. **PremarketEntry (⚡ Signals ▸ Ready to enter) unification** — [untouched] vs
    route its grade through `enterable.assess` so READY there also requires the
    floor intact.
14. **📁 holdings chip** — [chip shown, never hides] vs no chip on positions.
15. **Read the tiles BEFORE the limit cut** so a 24-tile page fills with
    enterable names — [no: post-cut on the shown tiles, one fan-out, the count
    line says "of the N shown"; raise `limit` to see more] vs a second live
    fan-out before the cut (the cost the 🧨 comment rejected) — and with it a
    server-side "Enterable first" sort (dropped: it cannot exist post-cut).
16. **Which tabs the filter applies to** — the default map in §4.3: `n/a` on
    vcp, winners, topping, earnings, zero_dte, undervalue; `demand` on every
    other tab INCLUDING the watchlist boards (bonde, growth, gnt, catalysts, hot
    sectors) and the study boards (keltner, amd, gabbar, ict) where a large share
    WILL hide, because Gabbar levels and ICT structures are not `price_zones`
    bands. The per-tab hide rate is measured on the live payload and handed to
    him; he moves tabs with the numbers.
17. **Chip title says "closed-bar read (no live print)"** when the tape is down —
    [yes] vs hide the chip.
