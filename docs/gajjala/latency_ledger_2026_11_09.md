# ⏱ Speed — the 🚩 A+ latency ledger (GG LIVE P4, 2026-11-09)

Ajay 2026-11-09 ~01:00 ET: *"I would like the autopilot to be continously monitored or live tracked and changed as if
Gallalas makes the trades can you modify and make it more live with websockets or something else where there is a low
latency monitoring on the prices action changes please? same for reuglar Gajjlas tab as well need it to be more live"*

This ledger measures how many seconds after the 5-minute entry bar CLOSED each step of the 🚩 A+ path happened. It
changes no rule, no gate, no push — it reads records that already exist. A timing, not a result: no placebo, no claim
about outcomes.

## What it reads

| source | rows | steps |
|---|---|---|
| `gajjala_alerts` | every LIVE `GG:` claim in state `pushed` (never `SHADOW:GG:`, `GG1:`, `GGA:`, never a `…#state` refusal row) | Read = `at` − close · Rang = `claimed_at` − close |
| `gajjala_lane` (same `_id`) | the lane doc | Lane saw = `first_seen` − close · Ordered = `ordered_at` − close · Filled = `fill_t` − close · order → fill · `order_source` (absent = `tick`) · `enter_ms` |
| `gajjala_lane_stream` (P1, SHADOW) | `{id}|seen`, `{id}|trigger`, `{id}|trigger_lot`, `{id}|stop` | would-have-seen / would-have-ordered seconds, print lag; the stream-vs-1-minute check |
| `gajjala_bar_final` (P2 probe) | one row per name per closed 5-minute bar | the bar-finality line |

An unfilled or skipped lane doc shows "—" for Ordered / Filled and still counts in Read / Rang.

## The clock trap (critique C4)

`entry_bar_t` is a **naive ET** string (`"2026-10-19 18:10"`), the bar's RIGHT label = its close. It is parsed with
`trading/gajjala_entry._parse_et`, never shifted by the frame (a 15-minute row is not moved 15 minutes). Every other stamp
is UTC ISO, parsed with `gajjala_entry._parse`. Reading `entry_bar_t` as UTC adds 14,400 s+ (EDT) — on the 2026-11-09
probe the ring p50 reads **14,472.7 s instead of 70.6 s**. `tests/test_gajjala_latency_2026_11_09.py`
(`test_neg_entry_bar_t_is_naive_et_never_utc`) pins it.

## Baseline (§1.4 — every pushed live `GG:` A+ since 2026-10-01, read-only, re-run 2026-11-09)

Percentile = numpy linear interpolation (the method the ledger serves; pinned on a 5-value fixture).

| step (seconds after the 5-minute entry bar CLOSED) | n | p50 | p90 | min | max |
|---|---|---|---|---|---|
| pass start (`at`) — **Read** | 47 | 61.0 | 62.4 | 60.6 | 176.1 |
| phone ring (`claimed_at`) — **Rang** | 47 | 70.6 | 78.0 | 65.4 | 203.5 |
| lane first saw it (`first_seen`) — **Lane saw** | 26 | 122.0 | 550.0 | 121.0 | 2,480 |
| lane market order (`ordered_at`) — **Ordered** | 15 | 124.0 | 855.8 | 122.0 | 3,603 |
| lane fill (`fill_t`) — **Filled** | 15 | 127.0 | 860.2 | 123.0 | 3,605 |
| order → fill | 15 | 3.0 | 5.6 | 1.0 | 6.0 |

Worked example (HUHU): close 14:45:00 ET, ring 14:46:10.16 ET → 70.2 s; order 14:47:02 ET → 122 s.

Where the time goes today: 60 s = the cron's `:x1` minute vs `BAR_SETTLE_SEC` 30 (30 s of it pure wait); ~10 s pass
wall before the ring; ~51 s = the lane's next minute tick; ~2 s order; ~3 s fill.

## What the 🏁 ⏱ block serves

`GET /trading/gajjala/latency?span=` (owner only; the 🏁's span keys `GC.LEDGER_SPANS`, default
`GC.LEDGER_SPAN_DEFAULT`) → `chart_maps/gajjala/latency.payload`:

- title "⏱ Speed — seconds after the 5-minute bar closed"; columns Read · Rang · Lane saw · Ordered · Filled; each cell
  `p50 · p90 (n)`; rows `before {date}` / `since {date}` split at `latency.GG_LIVE_FROM` (MINE — **"2026-11-09"**, the deploy landed
  ~02:30 ET 11-09 before the pre-market, so 11-09 is the first full session on the new code; a row dated before it is "before", on/after it "since"; None or a value that is not an
  ISO date = no split, one row named after the span, never an error).
- per column, a seeded bootstrap 95% interval of the p50 difference (`LATENCY_BOOT_N` 2000, `LATENCY_BOOT_SEED` 7); fewer
  than `LATENCY_CI_MIN_N` (5) on a side → "no interval".
- "Stream vs 1-minute check — same outcome {a} · different {d}" (only when stream rows exist): stream side = the earliest
  `trigger` / `stop` print (else none); 1-minute side = ordered · stop printed first (`unfilled`+`never_triggered` WITH
  a `last`) · missed · skipped (other) · never traded the trigger by the cut-off (`unfilled`+`never_triggered` WITHOUT a
  `last` — `_expire_waiting` writes none). Same outcome = trigger↔ordered, stop↔stop-first, none↔cut-off. A doc still
  waiting is not counted. Plus the 1-minute fill vs the stream's trigger print in R (fill above the print = positive)
  and the odd-lot-only trigger count (a doc with a `trigger_lot` row is not odd-lot-only).
- "Bar finality: {c} of {n} closed 5-minute bars changed between 30 s and 60 s after close (volume on {v})." with
  regular / extended lines (only when `gajjala_bar_final` has rows).
- footnote "From the alert and lane records: p50 · p90 (n). A timing, not a result."; empty span "No 🚩 A+ rang in this
  span."

## Re-run (read-only; the main session runs it once)

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.gajjala_latency_report --span all
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.gajjala_latency_report --span 10d --json
```

The script prints `latency.payload(span)` — the same function the endpoint serves (`test_script_prints_the_endpoints_numbers`).
`--span all` reads every pushed live `GG:` claim on file; the 🚩 A+ pushes started after 2026-10-01, so it is the §1.4
cohort. The container runs `origin/main` — the script exists there only after the deploy.

## Mount (main session, after the merges)

In `frontend/src/components/GajjalaBoard.tsx`, under the A+ charts on the 🏁 view:

```tsx
<GajjalaLatency span={span} />
```

(`import { GajjalaLatency } from './GajjalaLatency';`) — the component fetches itself, renders nothing for a non-owner
or on a 403, a table on desktop and stacked `label: p50 · p90 (n)` lines at ≤ 430 px.

## Proposed targets (HIS CALL #14 — not decided here)

Rang p50 ≤ 40 s after close (now 70.6; needs #5 on); lane order ≤ ring + 2 s (now +53.4; needs #1); a waiting doc ordered
≤ 1 s after the first qualifying print (now up to 60 s; needs #1); a finished pass on the tab ≤ 2 s (now 0–300 s); card
price ≤ 2 s old while live (now ≤ 30 s).
