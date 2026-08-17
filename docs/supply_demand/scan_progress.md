# Live scan progress — and why both demand tabs watch one job

Ajay 2026-08-17, looking at the Back in Demand tab mid-scan:

> *"Are you updating both pages when supply demand is getting updated I am
> looking at this and its hard to tell if its scanning or now"*

Two questions in one sentence. The first has an answer already in the code; the
second was a real defect.

Code: `backend/supply_demand/demand_reentry.py`, `backend/supply_demand/api.py`,
`backend/chart_maps/board.py`, `frontend/src/lib/demandScanProgress.ts`,
`frontend/src/components/DemandScanProgress.tsx`,
`frontend/src/hooks/useDemandScanProgress.ts`.
Tests: `backend/tests/test_demand_reentry.py` (+16),
`frontend/src/lib/demandScanProgress.test.ts` (23),
`frontend/src/components/DemandScanProgress.test.tsx` (13).

---

## 1. "Are you updating both pages?" — yes, by construction

There is exactly **one** demand scan. `chart_maps.board.zone_tiles` does not run
its own; it reads the same cache the Back in Demand tab reads:

```python
# chart_maps/board.py :: zone_tiles
data = D.cached_or_warm(universe, limit=LIMIT_MAX)
rows = [r for r in (data.get("rows") or []) if r.get("is_reentry")]
```

So any change to the rule lands on both surfaces in the same instant. Verified
against the live containers after today's broken-band guard shipped:

```
demand-reentry rows: AIG ARE DPZ DUK HOOD HRL IDXX MSCI NKE TJX WRB
chart-maps tiles   : AIG ARE DPZ DUK HOOD HRL IDXX MSCI NKE TJX WRB
SWKS on either     : False False
```

Locked by `test_chart_maps_shows_the_SAME_counter_not_its_own`, which asserts
`zone_tiles` reads `cached_or_warm` and **forwards** the shared counter rather
than deriving one of its own. Two independently-computed readings of one job is
precisely how two pages start disagreeing.

## 2. "Hard to tell if it's scanning" — it genuinely was

The screenshot showed:

```
0 in demand · 0/0 scanned
Scanning S&P 1500 (500 + 400 mid + 600 small) in the background — this page
will fill in by itself (usually 2-3 minutes on a cold start, instant after).
```

Both counters (`n`, `scanned`) only exist in the **final** payload. Until the
scan finished there was nothing to count, so the page showed `0/0` under a
static sentence for the full ~2-3 minutes of a cold S&P 1500 pass. That state is
byte-for-byte identical to a scan that died in its first second.

### Why the SEPA progress panel could not just be reused

Chart Maps already has a live progress panel — but it watches
**`/sepa/scan/stream`**, a *different* scan over a different universe, which
feeds the VCP tab. The Back in Demand board runs its own pass. It needed its own
counter.

### The counter

`scan()` publishes a snapshot as it goes; `progress_for(universe)` reads it.

| phase | when |
|---|---|
| `universe` | resolving the constituent lists — 3 network calls for sp1500 |
| `scanning` | one publish **per symbol**, carrying the ticker and the live hit count |
| `enriching` | the time-boxed tape + NBBO pull for the top rows |
| `done` / `failed` | terminal |
| `idle` | nothing running — still answered, so the page has one shape to render |

Measured on a warm S&P 500 pass:

```
('universe',   0,   0, None,   0,  None,  None)
('scanning',  89, 503, 'CASY',  2, 17.7,   1.9)
('scanning', 192, 503, 'FAST',  4, 38.2,   1.3)
('scanning', 401, 503, 'ROST',  9, 79.7,   0.4)
('done',     503, 503, None,   11, 100.0, None)
```

Four decisions worth writing down:

* **A fresh dict is swapped in, never mutated.** The scan thread writes while
  the request thread reads, and the read path takes **no lock** — a progress
  poll must never be able to block the scan it is watching. Reference assignment
  is atomic in CPython, so a reader can never see a half-updated record.
  Pinned by `test_a_snapshot_is_swapped_wholesale_never_mutated_in_place`.
* **Published every symbol, not every Nth.** The publish is one small dict; the
  price frame just analysed cost far more. Sampling would only make the bar
  stutter.
* **The ETA is projected from the measured rate**, not a per-symbol constant. A
  warm price cache runs an order of magnitude faster than a cold one, so any
  constant would be wrong on one of the two paths.
* **A failed scan is published as `failed`.** Without it the bar freezes wherever
  it died and the page says "scanning" forever — the original complaint,
  reintroduced by the fix for it.

### Two things the tests caught while building this

1. **`progress_for` crashed on a junk field.** The publisher was hardened and the
   reader was not, even though the reader is the one on the request path. A
   progress endpoint that 500s is worse than no progress endpoint, because it
   fails for the user who is already unsure anything is working.
   → `test_publishing_never_raises_on_junk`.
2. **The panel rendered nothing for the first 1.5 seconds.** The board payload
   arrives with the page; the first progress poll is a poll-interval behind it
   and may never land. A silent gap is the original complaint in miniature, so
   the board's own `warming` flag now drives a "starting" state.
   → `the board flag beats the poll — never go silent`.

### What it shows now

```
[ SCANNING ]  Scanning S&P 1500 for demand-zone pullbacks…   412 / 1,500 · ~1m 50s left
████████░░░░░░░░░░░░░░░░░░░░░░
6 in demand so far      now: NVDA      27.5%
```

Both tabs render the same component off the same counter.

---

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| Chart Maps forwards the shared counter, never its own | `test_chart_maps_shows_the_SAME_counter_not_its_own` |
| Phases actually fire in order from the real loop | `test_a_real_scan_publishes_universe_then_scanning_then_done` |
| A failing ticker still advances the bar | `test_a_symbol_that_throws_still_advances_the_bar` |
| A failed scan is reported, not left frozen | `test_a_failed_scan_is_reported_not_left_frozen` |
| No % before the universe size is known | `test_no_percentage_until_the_universe_size_is_known` |
| No ETA before the first symbol finishes | `test_no_eta_before_the_first_symbol_finishes` |
| ETA measured, not a constant | `test_the_eta_is_projected_from_the_measured_rate_not_a_constant` |
| Each universe keeps its own counter | `test_each_universe_keeps_its_own_counter` |
| Snapshots swapped, never mutated | `test_a_snapshot_is_swapped_wholesale_never_mutated_in_place` |
| The reader survives junk | `test_publishing_never_raises_on_junk` |
| The panel never goes silent while warming | `the board flag beats the poll — never go silent` |
| An indeterminate bar, never a confident 0% | `renders an INDETERMINATE bar, not 0%, before the universe resolves` |
| Every phase maps to a CSS class that exists | `maps every phase onto a CSS modifier that actually exists` |
