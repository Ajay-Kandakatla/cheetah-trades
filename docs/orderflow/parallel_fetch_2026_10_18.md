# ⚡ Tape scan: windowed parallel Massive paging (2026-10-18)

**READ THIS FIRST** — Ajay 2026-10-18, on the Tape · Order Flow panel: *"I see a big lag in Tap reading its 30 secs
this feature. Can we make it fast."*

Decisions: `DECISIONS14` D1–D12. Code: `backend/orderflow/massive_pages.py` (the pager), `tape.fetch_trades`,
`quotes.fetch_quotes`, `quotes.covered_mask`. Tests: `backend/tests/test_tape_parallel_fetch_2026_10_18.py`.
A speed change. Not a methodology number beyond the MINE rules below (D4, D5, D10, D11, D12). No edge is claimed
anywhere.

## Why it was slow

One 50k-row Massive page (IREN, gzip 11 MB) costs 1.8–2.2 s before the first byte, 0.26 s to download and
0.06–0.11 s to parse. The cost is Massive's per-page server latency, and the old pager paid it one page after another:
page N+1 needs page N's `next_url`. Bandwidth and parsing are noise.

## Method

- **D1 — one shared pager.** The ET day is cut into contiguous, exclusive `[gte, lt)` nanosecond windows. Each window
  follows its own `next_url` chain. The windows run at the same time in a thread pool. Page frames come back in window
  order (ascending time) and the fetchers' existing `sort_values("ts_utc")` runs unchanged. Both `tape.fetch_trades` and
  `quotes.fetch_quotes` use it. HTTP stays `requests.get`. Signatures, columns, index and `attrs["truncated"]` keep their
  shape, so every caller (engine, tape_control, retail_history, retail_backtest, demand_reentry) is untouched.
- **D2 — window edges (MINE).** `WINDOW_EDGES_ET`, 14 edges:

  | window (ET) | why |
  |---|---|
  | 04:00–09:30 | pre-market, thin — one window |
  | 09:30–09:45, 09:45–10:00 | the open, the densest tape of the day — 15-minute windows |
  | 10:00–10:30, 10:30–11:00 | still heavy after the open — 30-minute windows |
  | 11:00–12:00, 12:00–13:00, 13:00–14:00, 14:00–15:00 | midday — hourly |
  | 15:00–15:30 | the run-in to the close |
  | 15:30–15:45, 15:45–16:00 | the close, dense again — 15-minute windows |
  | 16:00–20:00 | post-market, thin — one window |

  Trades read the 13 windows over 04:00–20:00. Quotes read the windows inside the regular session 09:30–16:00
  (`SESSION_START` / `SESSION_END` unchanged): the 12 edges inside it bound 11 windows. A half day simply returns
  empty afternoon windows.
- **D3 — `FETCH_WORKERS = 8` (MINE)** windows in flight per pull. Massive Stocks Advanced bills no per-call quota. The
  HTTP 429 path stays: sleep 2 s, retry.
- **D4 — the page cap is per window (MINE; the numbers are D12's, below).** `truncated` = any window hit its cap. A
  heavy tape loses the tail of a CAPPED window, not the whole afternoon, and the panel says when a window was capped.
  `fetch_quotes(max_pages=N)` keeps N as a TOTAL budget: `max(1, ceil(N / windows))` pages per window
  (demand_reentry's `VENUE_QUOTE_PAGES = 4` → 1 page per window).
- **D5 — the quote rule classifies only inside covered windows.** `fetch_quotes` sets `attrs["covered"]`: per window,
  the span actually held. A window that completed is fully known whatever its row count (zero NBBO updates means the
  prior quote stayed prevailing), so its span runs to the window end; a window that stopped early ends at its last
  quote + 1 ns; a window adds nothing only when it did NOT complete and held no rows. A span starts at the window start
  for the first window or when the previous span reached its window end; after a capped / failed window ANY window —
  complete, truncated or partial — starts at its OWN first quote (critic LOW, widened): the gap is not held. A
  completed window with no rows right after such a gap has no first quote to start from, so it adds nothing and the
  gap carries on. The window's own status decides only where its span ends.
- **D13 — degenerate quotes go per page (MINE).** The quotes `compact` drops zero / locked / crossed quotes (bid > 0,
  ask > 0, ask > bid) on every page, so a window's first / last timestamp and every span edge come from VALID quotes;
  a page of only degenerate quotes counts as a page with no rows. A print during a locked market is classified against
  the prior valid quote, as the serial code always did. `quote_rule_sides`' own degenerate-quote rule only matters for
  frames that did not come from `fetch_quotes`. `quotes.quote_rule_sides` gives any print outside those spans the tick-rule side (counted in
  `n_fallback` and the new `n_uncovered`), and `retail.identify` leaves it unsigned, instead of matching it to a stale
  earlier quote. A quotes frame WITHOUT the `covered` attr (hand-built, or any caller that is not `fetch_quotes`) keeps
  the legacy behaviour: no restriction, `merge_asof(backward)` alone decides (so a print before the first quote still
  falls back). An empty `covered` list classifies nothing.
- **D6 — 429s.** Every caller retries 429s without a cap, as before. `max_429` (tape_control only) now counts per
  WINDOW: a window's `(max_429 + 1)`-th 429 stops the whole pull (the other windows end after their in-flight request),
  `fetch_trades` returns None, and `last_fetch_fault()` says `rate_limited` on the caller's thread. The workers never
  touch that thread-local.
- **D7 — errors.** Trades: any window ending in a non-429 HTTP status or an exception makes the pull None, as the
  serial code did on its first failure. Quotes: that window keeps what it got, the other windows stand, and `covered`
  says exactly what is held.
- **D11 — every page is compacted as it arrives (MINE).** `massive_pages.fetch_windowed` takes a required
  `compact(results) -> DataFrame`. Each worker turns each 50k-row page into a small frame at once and drops the raw
  list of dicts: ≈ 700 B/row as Python objects → ≈ 60 B/row for trades (the trade columns only, `kind` labelled on the
  page, `conditions` / `correction` dropped) and ≈ 24 B/row for quotes (timestamps + bid + ask). `PullResult.frames`
  (window order) replaces the rows list; the fetchers `pd.concat` the frames and run their unchanged tail. The frame
  equals the serial reference (a test pins it).
- **D12 — caps that never refuse a day the old pager read (MINE).**

  | constant | value | why |
  |---|---|---|
  | `tape.TRADE_PAGES_PER_WINDOW` | 24 (× 50k prints) | equals the OLD whole-day cap, so a window is capped only on a day the serial pager would have truncated too; a realistic dense window holds 2–6 pages |
  | `tape.MAX_TRADE_PAGES` | 312 = 13 windows × 24 | derived; a ceiling, never a target |
  | `quotes.QUOTE_PAGES_PER_WINDOW` | 8 (× 50k NBBO rows = 400k per window) | IREN-class days fit whole (IREN 10-15's 10:00 window held ≈ 210k); a megacap's open window (≈ 1M+ quotes) is capped and `coverage_pct` says so (D10) |
  | `quotes.MAX_QUOTE_PAGES` | 88 = 11 session windows × 8 | derived from the edges |

  **Why (critic HIGH, confirmed with live read-only probes):** the first build's 2-page trade cap truncated IREN
  2026-10-15 (711,757 prints; 10:00–10:30 held > 100k) and IREN 2026-10-07 (387,668 prints; 11:00–12:00 held > 100k) —
  two days the serial pager read in FULL — and `tape_control.read_tape` refuses a truncated tape, so the 🎚️ push would
  have gone silent on those sessions. A cap tighter than the old one anywhere is a regression. The caps were tight only
  because of memory; D11 removes that reason. Quotes never gate a push.

## The coverage rule and `coverage_pct`

Before this change two holes were open even though the module docstring promised they were closed: after-hours prints
(16:00–20:00 ET) were classified against the 15:59:59 quote, and prints past a truncated pull against the last quote
held. Both now keep the tick rule. **UNMEASURED** as a change to the Tape verdict; the forward ledger
(`GET /orderflow/ledger/accuracy`) keeps grading verdicts.

### D10 — what `coverage_pct` means (amended after the first build, MINE)

With D5 alone, IREN 2026-10-16 flipped from `quote 63.6%` (trustworthy) to `mixed 59.9%` (not trustworthy) with
nothing truncated. The old number mixed two things: it counted after-hours prints classified against the stale
15:59:59 NBBO as covered, and it subtracted every print exactly at the midpoint. From D10 on, `coverage_pct` is the
share of prints WITH a prevailing quote we hold: 100 × (n − `n_uncovered`) / n, where `n_uncovered` = prints before
the first quote or outside the covered spans. `method` / `trustworthy` keep the 60% threshold
(`MIN_USEFUL_COVERAGE_PCT`, unchanged) on that number. `n_quote_classified` (held, off the midpoint, ±1),
`n_at_mid` (held, at the midpoint → tick side) and `n_fallback` = `n_at_mid` + `n_uncovered` keep their meanings as
counts. The served keys are unchanged, and no print's side changes.

| IREN 2026-10-16 read | method | coverage_pct |
|---|---|---|
| before this change | quote | 63.6% |
| D5 alone (nothing truncated) | mixed | 59.9% |
| D5 + D10 (measured 2026-10-18, same day, same sides) | quote · trustworthy | 88.1% — 264,346 quote-classified, 124,766 at the midpoint (tick side, held), 52,520 outside the quotes held (after hours / pre-market, tick side) |

## Measured

Reads only, throwaway compose containers, `gg_tape/profile_scan.py`, the same symbols and day before and after.

| name | when | fetch_trades | fetch_quotes | analyze + rest | TOTAL |
|---|---|---|---|---|---|
| NVDA 2026-10-16 | BEFORE (serial) | 53.92 s (560,176 rows, 24 pages, truncated) | 86.48 s (1,990,922 rows, 40 pages, truncated) | < 2.5 s | 142.86 s |
| IREN 2026-10-16 | BEFORE (serial) | 20.88 s (451,718 rows) | 34.28 s (779,864 rows) | < 2.1 s | 57.20 s |
| NVDA 2026-10-16 | AFTER, first build (2 / 4 pages per window, commit 4b1873a5) | 12.09 s (796,540 rows, truncated — was 560,176 under the prefix cap) | 19.24 s (1,913,358 rows, truncated; 5 of 11 session windows capped mid-window) | 2.84 s (TOTAL − the two fetches) | 34.17 s |
| IREN 2026-10-16 | AFTER, first build | 4.67 s (451,718 rows) | 7.09 s (779,864 rows, nothing truncated) | 2.58 s (TOTAL − the two fetches) | 14.34 s |
| NVDA 2026-10-16 | AFTER, FINAL (D11 / D12: 24 / 8 pages per window) | 19.72 s (1,197,259 rows — the WHOLE day, nothing capped) | 17.24 s (2,445,502 rows, nothing capped; coverage 93.2%, quote, trustworthy) | 3.10 s (TOTAL − the two fetches) | 40.06 s |
| IREN 2026-10-16 | AFTER, FINAL | 3.90 s (451,718 rows) | 5.89 s (779,864 rows, nothing capped; coverage 88.1%, quote, trustworthy, the same sides) | 1.97 s (TOTAL − the two fetches) | 11.76 s |
| IREN 2026-10-15 | FINAL (the critic's probe day: 10:00–10:30 > 100k prints) | 3.03 s (719,777 rows, nothing capped) | 4.10 s (1,131,847 rows, nothing capped) | 2.34 s | 9.47 s |
| IREN 2026-10-07 | FINAL (the critic's probe day: 11:00–12:00 > 100k prints) | 2.59 s (394,967 rows, nothing capped) | 3.33 s (719,855 rows, nothing capped) | 1.85 s | 7.77 s |

The first-build rows are kept for the record: under 2 / 4 pages per window NVDA was still truncated and the critic's live
probes showed IREN 2026-10-15 and 2026-10-07 — both read in full by the serial pager — would have been truncated too (and the
🎚️ tape_control push refuses a truncated tape). The FINAL rows are the shipped caps (D11 / D12): every row above is read whole;
NVDA's remaining cost is the densest window's own page chain (≈ 8 pages at ≈ 2 s each), bounded by Massive's per-page latency.
Nothing here is an edge claim — seconds and row counts only.

These are seconds and row counts. They say nothing about whether any read makes money.

## HIS CALL (out of scope, follow-ups)

- **Q1** Raise the per-window caps further (the quote cap above 8 pages). Before D11 the raw rows list peaked around
  ≈ 300–400 MB per 2M rows; after D11 a page costs ≈ 60 B/row (trades) / ≈ 24 B/row (quotes) once compacted.
- **Q2** `requests.Session` connection reuse (about 0.3 s per page).
- **Q3** Start the NBBO pull at the same time as the trades pull in `engine.compute` (saves the smaller of the two).
- **Q4** A 16:05 ET precompute cron for the pinned / watchlist names so the panel opens warm.
- **Q5** A Massive flat-file (S3 day file) path for whole-day history.
- **Q6** More windows in flight (`FETCH_WORKERS` above 8).
