# Gajjala's tab — context reads, nightly, and four shared-module fixes (WP2, 2026-10-13)

The reads beside the five detectors (`backend/chart_maps/gajjala/context.py`), the 20:15 ET job
(`backend/chart_maps/gajjala/nightly.py`), and the four shared-module bugs Ajay said to fix (round C, R1-11 "fix all four").
Nothing here decides a setup except the float, and only for 🎾 (DECISIONS K8 — the detector applies the gate). Every number
is a constant from `constants.py` (or a house constant reused by name). **UNMEASURED** — none of these reads is a forecast.
They run inside the cron pass and the nightly only, never on a page load.

## 1. Float chain (spec C7, HIS CALL 28)
`floats_for(symbols, *, priority, state, now, status_lookup, massive_lookup, sleep, store, session, max_new, refine)`
→ `{SYM: FloatRead}`; FloatRead = `{shares, src, text, as_of, status, refined, suspect, suspect_text}`.

| Step | Source | Label | Notes |
|---|---|---|---|
| 1 | `shares_cache` row (`volume_movers.shares_status(sym, fetch=False)`) | "Float 3.1M" / "shares out 8.1M" | fresh rows only (+ the expired values served while a 429 marker stands) |
| 2 | Massive `share_class_shares_outstanding` | "shares out 8.1M (Massive)" | once per (session, symbol): the answer, even None, is kept in `gajjala_daily.float_massive`; runs during a Yahoo back-off |
| 3 | Yahoo refinement (`fetch=True`) | as step 1, `refined: true` | ≤ `FLOAT_MAX_NEW_PER_PASS` per pass, 1 s apart (`moat_backfill.DEFAULT_INTERVAL_SEC`) |
| — | nothing | "float unknown" | 🎾 reads none ("float unknown") |

- Refinement order: (a) names whose 🎾 structure is alive this pass with the float unknown or a Massive shares-out above
  `K8_MAX_FLOAT` (a yfinance float could admit them), then (b) the rest; each by `change_pct` DESC.
- A Yahoo 429 stops the step: `n += 1`, `until = now + min(300 × 2^(n−1), 900)` s → 300, 600, 900, 900…
  (`FLOAT_BACKOFF_START_SEC = PASS_CADENCE_SEC`, `FLOAT_BACKOFF_MAX_SEC = moat_backfill.BACKOFF_MAX_SEC`). Any answer resets
  `n`. State = `gajjala_state` doc `"float_backoff"` `{until (epoch s), n}`.
- Shares out ≥ float, so a shares-out ≤ 10M can never admit a float > 10M — the Massive fallback is the conservative side.
- Float on file > shares out (FCHL 2026-10-13: 1,314,047 > 1,299,391, trap T10): flagged with the house check
  (`short_interest.read._float_suspect`, its float-exceeds-shares branch). `FLOAT_SUSPECT_POLICY = "ineligible"` (shipped):
  the read keeps the float + the flag, the 🎾 gate reads it as unknown, rotation is None, text "float on file 1.31M exceeds
  shares out 1.30M — treated as unknown". `"shares_out"`: shares outstanding is served instead.
- Rotation: `rotation(volume, float_read)` = scanner shares today ÷ the read's shares → "🔄 float ×4.2" (label "shares out"
  when the source is shares out); None when unknown / 0 / suspect-ineligible.

## 2. Chips
- ⏸ `halts_chip(sym, get_today_halts())` → "⏸ halted ×2 (LUDP, T1)", `first_halt_time`, `last_resume_et` (ET ISO from the
  feed's ResumptionDate + ResumptionTradeTime; None while still halted). The feed's `BRK.B` maps to our `BRK-B`.
  `record_live_halts(store, session, halts)` upserts today's halted tickers into `gajjala_halts` (source "live") — only when
  the feed's ET date IS the pass's session. `HALT_CALM_BARS` stays OFF: nothing reads `last_resume_et` for a push yet.
- 🧱 `psych_chips(price)`: $1 / $5 / $10 (GG S9 1:09:11, 1:21:19, 1:39:13) strictly above the price and within
  `PSY_NEAR_PCT` (5% — a **Cheetah default**, Ajay's number): "🧱 $5 · 4.2% above", `why` "his profit-taking / climax level,
  not an entry". Written `level <= price × 1.05`.
- Red closes: `red_closes_chip(n)` from the detector's `red_closes` count — "4 red closes in a row — he waits (“more than 3
  red closes is red flag to me”)" when n > `RED_CLOSES_WAIT` (GG X 1733882105204011109). Chip only (`RED_CLOSES_MODE`).
- 🎾 `squeeze_history(daily_df, halt_dates, *, session, ledger_dates)` — "🎾 squeeze history: N of last 30 sessions (≥50%
  range or a halt)" over the 30 market days BEFORE the session (today's partial bar never counts): `high ≥ low × 1.5` OR a
  `gajjala_halts` row that date. While the halt ledger misses part of the window: " · halt list from <date>". No daily bars →
  halts only, said so. A CHIP, never a criterion (DECISIONS K8). `warm_squeeze_history(symbols, session, store, cap, loader)`
  serves `gajjala_daily.squeeze_history` or computes it from `prices.closed_daily_frame` (never a cache write, trap T5); the
  pass caps new computes at `DAILY_MAX_NEW_PER_PASS`, the nightly does the rest.

## 3. ☀️ / 🌙 lists
- ☀️ `premarket_list(scan_today, carry_prev, *, pm_levels, sort)` (DECISIONS K9): today's qualifiers first seen in a premarket
  pass with premarket volume ≥ `K9_PM_MIN_VOLUME` (the 1-minute premarket sum via `pm_levels_for(raw, session)` =
  `daytrading.indicators.premarket_levels` + the last premarket close; else the scanner's own number while the print is still
  premarket), volume DESC (GG S8 1:21:56) or `sort="change"`; then the previous session's after-hours carry set (the one the
  LAST after-hours pass wrote), by its move DESC, "🌙 carried from yesterday's after-hours +12.3% (last after-hours pass
  20:01)". A carried name that also qualifies is listed once (`carried` on today's row). `off_pm_high_pct` = display only.
- 🌙 `postmarket_confirm(candidates, checked, minutes_loader, snapshot_rows, *, cap, session, now, store)` (DECISIONS K10):
  regular close in the top 30% of the RTH range (`close − low ≥ 0.70 × (high − low)`, multiplication) AND after-hours volume
  ≥ 250,000 (minutes starting 16:01–19:59 — the 16:00 closing-cross minute EXCLUDED, trap T7) AND the CURRENT gain ≥ +5% vs
  the regular close (snapshot day.c, else the 15:59 minute, flagged). `close_pos` is computed once and kept. Rotation:
  never-checked first (gain DESC), then the oldest `checked_at`; ≤ `AH_CONFIRM_MAX_PER_PASS` per pass; every check is written
  to `gajjala_post`; `unchecked_n` (incl. failed minute reads) → "N after-hours gainers not checked yet — next pass".
  `reg_gain_pct` is served, display only (`AH_EXHAUSTION_MAX_PCT` OFF).

## 4. Nightly (20:15 ET, `python -m chart_maps.gajjala.nightly [--session D] [--steps floats,halts,history]`)
For tomorrow's names (scanner.listed_symbols of the next market day + tonight's after-hours carry):
1. **floats** — the chain above, every name, still paced and still stopped by the first 429 (shared back-off state).
2. **halts** — every session of the window (30 market days ending today) not yet read in full from Nasdaq Trader's dated
   list `get_halts_for_date(d)`: 30 GETs the first night, then 1. The read set lives in `gajjala_state` `"halt_backfill"`
   `{done}`; a failed read is not marked and is retried the next night. A session the live passes recorded is read once more
   in full (a host-sleep gap in the live rows would otherwise stay) — the one deviation from "missing from gajjala_halts".
3. **history** — the 🎾 chip for every name, stored under TOMORROW's date.
Idempotent; a raising step is logged and the others still run (exit 1).

### The probe behind the backfill (re-run before quoting)
`backend/scripts/gajjala_halts_history_probe.py --date YYYY-MM-DD` (read-only, one GET each; `--file` for a saved body):

| Run | Date asked | Items | HaltDate values | Mkt |
|---|---|---|---|---|
| 2026-10-13 ~09:12 EDT (spec §1.6) | 2026-10-09 | 72 | all 10/09/2026 | Q 69, N 3 |
| 2026-10-13 ~09:12 EDT (spec §1.6) | 2026-09-02 | 28 | all 09/02/2026 | Q 25, Z 3 |
| 2026-10-13 11:18 EDT (WP2 re-run) | 2026-10-09 | 72 | all 10/09/2026 | Q 69, N 3 |
| 2026-10-13 11:18 EDT (WP2 re-run) | 2026-10-12 | 95 | all 10/12/2026 | Q 87, N 3, A 3, B 1, Z 1 |

The 10/09 body is the test fixture `backend/tests/fixtures/gajjala/halts_10092026.xml` (72 halts / 32 tickers parsed).

## 5. The four shared-module fixes (Ajay round C, R1-11)
| # | Module | Bug | Fix | Tests |
|---|---|---|---|---|
| T1 | `daytrading/data.py` | "today" = UTC date → 19:00–20:00 EST partial days cached forever | ET date (`_today_et`) | WP1: `test_daytrading_data_et_today.py` |
| T2 | `daytrading/data.py` | HTTP 429 retried with no cap | gives up after `_CB_TRIP_AFTER` consecutive 429s, one breaker failure | WP1: same file |
| T3 | `catalysts/halts.py` | halts filtered by the UTC date → every halt vanished after 20:00 EDT / 19:00 EST | ET date (`_now_et`); + `get_halts_for_date(d)` (same parser, `&haltdate=`, no cache, `{}` on a failed read) | `test_halts_et_date.py`, `test_halts_for_date.py` |
| T4 | `sepa/volume_movers.py` | one Yahoo 429 wrote the 7-day null tombstone | `_fetch_shares_status` classifies (`sepa.moat._is_rate_limit`); a 429 writes ONLY `rl_until = now + moat_backfill.BACKOFF_START_SEC` (60 s); inside it the expired values are served ("stale_served") or None ("rl_marker") with NO fetch — the stampede guard kept; "no data"/"error" keep the 7-day tombstone; `_fetch_shares_yf` and `shares_for` keep their signatures | `test_volume_movers_rate_limit.py` |

Not fixed here (separate ask, spec §6): `sepa/cap_warm.py` still writes a null row with `as_of` when its fetcher returns None —
which a 429 produces — the same tombstone class on the weekly cap warm.

## 6. Review fixes (2026-10-13, after the WP2 review)
- **A 200 is not a read.** `halts.get_halts_for_date(d)` now returns `{}` (failed) when the body has no items or ANY item is
  dated another day; `nightly.backfill_halts` also counts a zero-halt answer as failed (probed sessions: 28 to 95 halts —
  a calm day is not plausible in this tape). Before: a feed ignoring `&haltdate` (every GET = the 10/09 body) gave
  `read 30, failed 0` and 29 sessions were marked "no halts" for good, so `ledger_complete` flipped and the chip's
  "halt list from …" caveat vanished. Now `read 1, failed 29`, retried next night
  (`test_NEGATIVE_feed_ignoring_haltdate_marks_only_the_real_day`).
- **The float's `as_of` is the data's age.** `volume_movers.shares_status` serves the row's `as_of` (epoch s; the fetch time
  on "fetched") inside `vals`; `shares_for` strips it, so `/sepa/shares`, russell_watch and promo_circuit are unchanged.
  `FloatRead.as_of` (and the stored `gajjala_daily.float.as_of`) come from it; a "stale_served" read says
  `Float 3.1M (stale, as of 2026-10-04)`.
- **A raising Massive lookup is asked once a pass.** The failure is kept in `gajjala_daily.float_massive` as `{failed_at}`
  and honoured for `PASS_CADENCE_SEC` (run.py's two `floats_for` calls share `now`); the next pass asks again, and a
  landed answer is kept for the session as before.

### Integration (2026-10-13): the cap warm's 429 tombstone is gone too

DECISIONS R1-11 asked for the 7-day blank float on one Yahoo 429 to be fixed everywhere. `sepa/cap_warm.py` was the
last writer of that tombstone: on a fetcher None it stamped an all-null row with `as_of`. The default warm now reads
`volume_movers._fetch_shares_status`; a `"rate_limited"` answer writes ONLY `rl_until` (the same
`moat_backfill.BACKOFF_START_SEC` marker `shares_status` honours) and counts `failed`. A real no-data answer still writes
the 7-day null row. Tests: `tests/test_cap_warm.py` (`test_NEGATIVE_a_429_writes_only_the_rl_marker_never_as_of_or_nulls`
and two more).
