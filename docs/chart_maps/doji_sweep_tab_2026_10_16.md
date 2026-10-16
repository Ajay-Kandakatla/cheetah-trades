# 🕯️ Doji Sweep tab (2026-10-16)

**Status: UNMEASURED.** The tab is a scanner, not an entry. The line on top of the board says what the pre-registered
backtest read; until its result is pasted into `backend/chart_maps/doji_sweep_measured.py` that line says UNMEASURED. No
accuracy number exists until then, and none is quoted here.

## The ask, verbatim

Ajay 2026-10-16:

> "create me a new tab for Doji candle after a sweep. For any stocks after a down trend. May be from all chart maps
> especially on the 60% 70% down stocks"

His knob answers (DECISIONS6, 2026-10-16 ~00:3x–00:4x ET, his words in quotes):

- **K1** Source: "I heard but do some research and back test please on accuracy". No named source. The definitions were
  researched (scratchpad `doji/RESEARCH_doji_sweep.md`) and the read is backtested by the app before any number is quoted.
- **K2** Timeframe: daily candles. One closed daily candle; the tab updates after each close.
- **K3** Downtrend: "All of them" + "Yes, any read; chips narrow". A name qualifies on ANY of three reads; the chips
  narrow; every card says which reads it meets; the study reports each read separately.
- **K4** "Sweep 5%" → "Within 5% either side counts as a test". The candle's LOW within ±5% of the reference low, above or
  below. The close back above the reference low is a chip ("undercut and reclaimed"), never a gate.
- **K5** Doji: "Research". The body threshold from the research; default the house 5%; the study also reads 10%.

## What fires

ONE engine in `backend/chart_maps/doji_sweep_tab.py`: `frame_features()` (every per-bar column, each reading bars at or
before the candle only) and `row_statuses()` (the one classifier). The tab reads the LAST closed bar; the study
(`backend/scripts/doji_sweep_study.py`) reads every bar with the same two functions.

A candle fires when all three hold:

1. **A doji.** The body is under `DOJI_BODY_PCT` of the day's range. `DOJI_BODY_PCT` is imported from
   `scalping/candles.DOJI_BODY_PCT` (0.05), the house doji that `scalping/candles.anatomy` and the 📐 page already use,
   with the house STRICT `<` (DECISIONS6 wrote "≤"; the house rule wins so the ledger and the 📐 page agree on what a
   doji is — HIS CALL Q2). A switch shows bodies under `DOJI_BODY_WIDE_PCT` (0.10 — Cheetah default, PivotBoss / Liberated
   Stock Trader).
2. **A test of the prior low.** The candle's low sits within `SWEEP_TEST_PCT` (5.0, Ajay 2026-10-16) either side of the
   lowest low of the `SWEEP_REF_SESSIONS` (20) sessions before it, and that low was set at least `SWEEP_REF_MIN_AGE` (4)
   sessions before the candle. 20 and 4 are Turtle Soup's (Connors & Raschke, *Street Smarts*, 1995 — read through
   secondary write-ups; Cheetah default, HIS CALL Q4). A fresher lower low means no fire. Equal lows: the most recent one
   sets the age (HIS CALL Q18). The test compares the percentage rounded to `TEST_ROUND_DP` (2) places — the served
   number (AMENDMENTS6 B9: 7.3 × 1.05 would otherwise read 5.000000000000003).
3. **A downtrend read** — ANY of the three below.

Closed bars only: `KL.closed_frame` drops every bar dated the session (the price cache patches today's in-progress bar
hourly); the session rolls at `KL.ROLL_AT` (20:00 ET), so a session's candle joins the tab after 20:00 ET.

## The three downtrend reads

- 📉 **52-week**: `DOWN_PCT` (60, Ajay — "especially on the 60% 70% down stocks") or more under the highest intraday high
  of the last `YEAR_BARS` (252) closed sessions — `fallen_tab.closed_read`, the 📉 Down 40%+ tab's own read.
- 🏔️ **All-time**: `DOWN_PCT` or more under the all-time high — `ath_tab.closed_read`, the 🏔️ ATH tab's own read (the
  stored monthly history to the listing plus the cached daily bars). **Honesty rule:** a name whose history does not reach
  its listing is read against its "high since" its first bar, so the true distance is at least the one shown — a name can
  be missed, never falsely included. The tab never writes the ATH history (`ath_tab._maybe_fill` / `ath_history.fill` are
  never called).
- **Averages**: the close below both the `SMA_FAST` (50) and `SMA_SLOW` (200) day simple averages.

Every card says "Reads met: …" (never "Downtrend" alone — AMENDMENTS6 B16: some names qualify only by the ATH read while
above both averages).

## The board

- **Memo, Mongo only.** ONE `sepa.prices.bulk_cached_frames` find, ONE `ath_history.read_many`, ONE
  `ipo_age.listing_dates_map`, in a background memo thread (the 📉 tab's shape; first answer "warming", `MEMO_TTL_SEC`
  imported from the 📉 tab). Never a provider call on the read. The card charts go through the board's shared
  `_attach_bars → bars_for → prices.load_prices` path that every board tab uses, which refreshes a `price_cache` doc older
  than 20 h (AMENDMENTS6 B10, HIS CALL Q22). The board keeps the ONE shared `_bulk_snaps` live now-line over the shown
  tiles, like every board tab.
- **Request path** only filters and orders the held rows:
  - the body switch `dj_body` = 5 (default) | 10;
  - the chips `dj` — `w52_40`, `w52_60`, `w52_70` (40 / 60 / 70% off the 52-week high, picked from `fallen_tab.DEPTH_STEPS`),
    `ath_60`, `mas`, `reclaimed`; every ticked chip must pass (K3 "chips narrow" — no ANY mode);
  - three orders: `default` (the newest candle, then the deepest under the 52-week high — MINE, HIS CALL Q14),
    `doji_test` (the low closest to the prior low, either side), `doji_ath` (deepest under the all-time high);
  - the house "ok" liquidity floor (HIS CALL Q6).
- **Held out, counted, never listed**: ETFs, delisted, stale cached bars, fewer than `YEAR_BARS` sessions, scale glitches
  (`FAL.GLITCH_RATIO`, named in the suspects fold), a flat or unreadable bar in the reference window (`bad_bars`, HIS CALL
  Q23 in the module docstring), no cached bars.
- **Writes nothing.** No alert, no push.

### Every served string (W-table families, BUILD_SPEC6 §3.5)

All built in `doji_sweep_tab.py` from the constants; the FE (`DojiSweepBoardNote.tsx`, `lib/dojiSweep.ts`) prints them
verbatim and composes none (contract-pinned: no `toFixed`, no `Math.`, no `UNMEASURED` in their code).

- Labels: `TAB_LABEL` (W1), the three sort labels (W2–W4), the order lines (W5–W7).
- Header (W8), warming note (W9), error note (W10), empty note (W11), the display-only `NOTE` (W12), the count line (W13).
- Chips: `FILTER_LABELS` (W14), `FILTER_NOTES` (W15), `FILTERS_NOTE` (W16), the chip line (W17).
- Body switch: `BODY_LABELS` (W18), `BODY_TITLES` (W19). Reads fold: `READS_LEGEND` (W20). Suspects: the 📉 tab's
  `suspects_block` (W21).
- Cards: `VARIANT_WORDS` (W22 — dragonfly, gravestone, long-legged, plain), the two badges (W23, W24), the stats (W25),
  `reads_text` (W26), `why_text` (W27), the dashed `REF_LINE_LABEL` line (W28), the 🕯️ marker on the doji bar.
- Study line: `NOTE_PENDING` (W29, UNMEASURED, with Bulkowski's claim and the house `CAVEAT`) until measured; the measured
  format (W30) and verdict words (W31) after.
- TAB_META blurb (W32, AMENDMENTS6 B14: "a scanner, not an entry", never "until the backtest lands"), the ✨ entry (W33),
  the ℹ️ Rules section `doji_sweep` (W34, right before 🎢 in `rules_info.SECTION_KEYS`), the api Query descriptions (W35).

## The ledger (and why it is not on the 📐 page)

The existing 17:20 ET weekday cron (`python -m patterns.history`, no crontab change) records every fired candle of the last
`LEDGER_BACKFILL_SESSIONS` (3) closed sessions through `record_doji_sweeps` — kind `doji_sweep`, read
`bullish_reversal_setup`, `_id` `SYM:doji_sweep:<date>` (idempotent, so a late or missed run loses no session) — AFTER
`resolve_pending` and the existing kinds, so a failure in the new read never stops the grading of the others
(AMENDMENTS6 B8). It is graded by the existing candle grader on the next `CANDLE_HORIZON` (5) sessions (HIS CALL Q13).

Why `bullish_reversal_setup`: `_grade_candle` grades every read other than that string as BEARISH; a "nicer" word would
silently invert every grade (contract-pinned).

`GET /patterns/accuracy` serves it under its own top-level `doji_sweep` key: the headline counts the 5%-body fires at or
above the floor (the tab's default view); `doji_sweep_10pct` and `doji_sweep_thin` are sub-blocks, never pooled into it
(AMENDMENTS6 B7). The 📐 Chart Patterns page reads `patterns` / `candles` only, so it does not show the new kind — HIS
CALL Q3 (default: ledger only).

Why the cron and not the tab's memo build: a record written when someone opens the tab would depend on someone opening it.

## The study

Pre-registered BEFORE it runs: `docs/research/doji_sweep_study_2026_10_16.md`; script `backend/scripts/doji_sweep_study.py`
(`--no-fetch` is the only mode; Mongo read-only, every write method stubbed to raise — AMENDMENTS6 B18). Point-in-time over
the `full` universe's cached bars with the same engine. Matched placebo days (same name, same read set, k = 5, never inside
any outcome window of the same name — B1). Every outcome also net of SPY over the same sessions (B2). CIs by a 10-session
date-block bootstrap (binding) and by name; a verdict word only when both agree (B2). Verdict words for exactly three
pre-registered cells, Holm-corrected: the primary (≥ 60% under the 52-week high, 5% body, the 5% test, 10 sessions,
SPY-adjusted — B4), the any-read cell, and a test of the low WITHOUT a doji (the doji's control — B5). Every other cell is
"exploratory — no verdict"; the ≥ 70% cell is pre-declared too small (B4, B6). Survivors-only, one market regime (~2 years
of cached bars) — said in the served line. The result is pasted into `doji_sweep_measured.py` by its own work package
(WP-R), which appends a `## Result` section here; the served line changes only through that literal.

Prior (the sources' claims, not ours): Bulkowski counts a doji in a downtrend as a 52% reversal (rank 78/103), the
dragonfly — the shape a sweep-and-reclaim doji tends to make — 50% (rank 98/103); Marshall, Young & Rose (DJIA 1992–2002)
found nothing significant after the bootstrap; George & Hwang (2004) found names far from their 52-week high do worse. No
source tests "doji + sweep" as one rule.

## The 🗺️ tape-burst watch

**Out by default.** `orderflow/tape_burst_kinds.chartmaps_watch` reads every Chart Maps membership snapshot except
`OWNED_TABS` and, since this build, `EXCLUDED_TABS = ("doji_sweep",)` (AMENDMENTS6 B3). Without it ~12 names a day would join
the LIVE owner-only 🗺️ `tape_burst_chartmaps` watch and thin the other tabs' share of its 150-name cap — and this build
pushes nothing. So the display-only note ("Nothing here … pushes a phone"), the ℹ️ Rules line and the ✨ "Pushes nothing"
are true. HIS CALL Q15: turn the ride-along on (one line).

## Sizing probe (counts only — nothing quotable)

Planner, 2026-10-16, read-only over the first 600 `price_cache` docs: 791 candles on 260 dates met doji < 5% + the ±5% test
of a ≥ 4-session-old prior-20 low + (≥ 60% under the 252-bar high OR below both averages); ≥ 60% under 52w: 173, ≥ 70%: 116,
below the averages: 778; only 82 undercut the prior low (61 reclaimed) — about 90% of his "test" candles never undercut.
The spec critic's probe (2,803 ATH-universe names, $10M floor): 3,169 primary events on 253 dates. No outcome was read.

## HIS CALLS (BUILD_SPEC6 §7, verbatim; AMENDMENTS6 notes in brackets)

From DECISIONS6:
- Q1 Tab name / emoji / slot: "🕯️ Doji Sweep", right after 🚩 Gajjala's — DEFAULT; he can rename or move it.
- Q2 Doji body: under 5% of the range, the house STRICT `<` (`scalping/candles.DOJI_BODY_PCT`) — DEFAULT; vs under 10% (the
  switch already shows it). DECISIONS6 wrote "≤"; the house `<` is used so the ledger and the 📐 page agree on what a doji is.
- Q3 The 📐 Chart Patterns page lists `doji_sweep`: no — ledger only, its own `/patterns/accuracy` key — DEFAULT; vs yes.
- Q4 Reference low: the prior-20-session lowest low, ≥ 4 sessions old (Turtle Soup) — DEFAULT; vs the smc swing low (the
  study's `swing_sweep` cell reads it beside).
- Q5 Depth: ≥ 60% (his "60% 70%"), chips 40 / 60 / 70 — keep.
- Q6 Liquidity floor on open: the house "ok" floor ($10M/day) — DEFAULT; vs none (the 🎢 way).
- Q7 Sessions a candle stays listed: 1 (the latest closed candle) — DEFAULT; vs 3.
- Q8 ATH history depth: the 🏔️ tab's monthly history to the listing — DEFAULT; vs 5 years.

Added by the spec (MINE unless tagged):
- Q9 Volume words: quiet ≤ 1.0× (MINE), heavy ≥ 1.5× (the house line), against the prior 50 sessions (the house average) —
  DEFAULT; vs a 20-session average. Display only. [B15: the 1.5× is borrowed from the 5-minute candle module
  (`scalping/candles.py:30`), not a daily house line.]
- Q10 `MIN_CELL_EVENTS` = 100 (MINE): a study cell with fewer events reads "too_small" — DEFAULT; vs 30 (MIN_BUCKET_N only).
- Q11 Placebo: k = 5 days of the SAME name with the SAME read set, never a 10%-body fire — DEFAULT; vs same-day cross-section.
  [B1: a placebo day never sits inside any outcome window of the same name.]
- Q12 ATH point-in-time: the stored high counts only after its month; before it the frame's running max (a lower bound) —
  DEFAULT; vs dropping the ATH read before the stored month.
- Q13 Ledger grading: the existing candle grader (a hit = the close 5 sessions on above the doji close) — DEFAULT; vs a new
  grader keyed to the doji's high / low (a grader change, out of this build).
- Q14 Default order: the newest candle, then the deepest under the 52-week high (MINE) — DEFAULT; vs closest test first.
- Q15 The 🗺️ tape-burst watch reads the tab's names. [B3 changed the default: OFF — `EXCLUDED_TABS = ("doji_sweep",)`;
  his call to turn the ride-along ON.]
- Q16 Study primary = the tab's default view incl. the floor — DEFAULT; vs all liquidity (reported beside). [B4: the
  primary is the ≥ 60%-under-the-52-week-high cell, SPY-adjusted; the any-read cell is served beside it.]
- Q17 Primary horizon 10 sessions from the next open (Bulkowski's 10-day move) — DEFAULT; 5 / 20 beside it.
- Q18 Equal lows: the MOST RECENT one sets the reference age (stricter — fewer fires) — DEFAULT; vs the oldest.
- Q19 Confirmation window 5 sessions and the 0.5% round-trip cost line (MINE) — DEFAULT.
- Q20 Minimum history: 252 sessions for every read (the 📉 rule) — DEFAULT; vs a per-read minimum (200 for the averages, the
  listing for the ATH read) so young 60-70%-down names can list. [B16: 80 of the 2,803 universe names have < 252 bars.]
- Q21 After the result: whatever the verdict, the tab stays display-only and nothing is removed or promoted — the result
  only changes the served line; any change to the rule, the order, the chips or the floor is his.
- Q22 The live overlay: keep the board's ONE shared snapshot over the shown tiles (every board tab's now-line) — DEFAULT; vs a
  Mongo-only tab with no live price / 🎯 chip on its cards. [B10: the card charts use the shared `load_prices` path.]
- Q23 (the engine's docstring) `bad_bars` also counts an unreadable bar in the reference window, wider than B13's "a flat
  candle today" — DEFAULT (MINE): keep the wider read.
- Q24 (final critic, 2026-10-16) B5's words: B5 asked for "the doji adds / does not add to the test alone". The build
  serves the control (`test_no_doji`) as NUMBERS beside the primary and never makes that claim
  (`doji_sweep_tab.CONTRAST_WORDS`, fix round 2) — the control is measured against its OWN matched days, and the
  own-pool rule changes its population, so the two contrasts are not one comparison. DEFAULT (MINE): numbers only; vs
  B5's literal "adds / does not add" sentence.

## Files

Backend: `backend/chart_maps/doji_sweep_tab.py` (engine, board read, words), `backend/chart_maps/doji_sweep_measured.py`
(the study literal), `backend/scripts/doji_sweep_study.py`, `backend/chart_maps/board.py` (`TABS`, `doji_sweep_tiles`,
dispatch, sorts, the membership hook's `dj` / `dj_body`), `backend/chart_maps/membership.py` (`MEMO_BLOCK_KEY`),
`backend/chart_maps/api.py` (`dj`, `dj_body`), `backend/patterns/history.py` (`DOJI_SWEEP_KIND`, `record_doji_sweeps`, the
accuracy block), `backend/supply_demand/rules_info.py` (section `doji_sweep`), `backend/orderflow/tape_burst_kinds.py`
(`EXCLUDED_TABS`). Tests: `backend/tests/test_doji_sweep_tab.py`, `test_doji_sweep_board.py`, `test_doji_sweep_study.py`,
`test_pattern_history_doji_sweep.py`, `test_rules_info_doji_sweep.py`, plus the widened tab-tail pins, and
`backend/tests/test_key_levels.py` (its `supply_demand.key_levels` import guard widened for
`chart_maps/doji_sweep_tab.py` and `scripts/doji_sweep_study.py`, each with a dated WIDENED note — the key-levels trap
rule; BUILD_SPEC6 §1.4 did not list this pin, so it is recorded here for the main session's sign-off).

Frontend: `frontend/src/lib/dojiSweep.ts`, `frontend/src/components/DojiSweepBoardNote.tsx`, `frontend/src/lib/chartMaps.ts`
(`CmTab`, `CM_TABS`, `TAB_META`, `tabSearch`, `boardQuery`), `frontend/src/pages/ChartMaps.tsx`,
`frontend/src/lib/newFeatures.ts` (✨ `chart-maps-doji-sweep-2026-10-16`), `frontend/scripts/contracts.mjs` (the "🕯️ Doji
Sweep tab" block + the widened board-tab pins). Tests: `src/lib/dojiSweep.test.ts`,
`src/components/DojiSweepBoardNote.test.tsx` (the backend golden), `src/components/DojiSweepBoardNote.live.test.tsx` (skips
until the live fixture `src/components/__fixtures__/doji_sweep_live_2026_10_16.json` is captured),
`src/pages/ChartMapsDojiSweep.test.tsx`, `src/lib/chartMaps.test.ts`.

Docs: this file, `docs/research/doji_sweep_study_2026_10_16.md`, `SPECS.md` § "Chart Maps — 🕯️ Doji Sweep tab".

## Verification

Backend, hermetic (the api image, the worktree mounted at /repo, no network):

```bash
docker run --rm --network none --name cheetah-tmp-pytest-doji-check -v /Users/ajay/clinet-test/wt-doji:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_doji_sweep_tab.py tests/test_doji_sweep_board.py tests/test_doji_sweep_study.py tests/test_pattern_history_doji_sweep.py tests/test_rules_info_doji_sweep.py tests/test_tape_burst_kinds.py
```

Frontend:

```bash
cd /Users/ajay/clinet-test/wt-doji/frontend
rtk proxy npx vitest run --reporter=dot
rtk proxy npx tsc --noEmit -p tsconfig.json
rtk proxy node scripts/contracts.mjs
```

The board, once deployed (one open, never more):

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8000/chart-maps?tab=doji_sweep" | python3 -c 'import json,sys; b=json.load(sys.stdin); d=b["doji_sweep_board"]; print(d["state"], d["study"]["status"], len(b["tiles"]))'
```

Deploy (final-critic fix 2026-10-16): the ledger is written by `record_doji_sweeps` inside the 17:20 ET
`python -m patterns.history` job, which runs in the CRON container (the api image). Deploying only `api frontend` leaves
the cron container on the old `main()`: it records nothing, and the new api still serves a `doji_sweep` block with
`n` 0. So the deploy names all three:

```bash
./deploy-cheetah-main.sh api frontend cron
```

The ledger, after the first 17:20 ET weekday run past the deploy on a day the tab lists fires:

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" http://127.0.0.1:8000/patterns/accuracy | python3 -c 'import json,sys; a=json.load(sys.stdin); d=a.get("doji_sweep") or {}; t=sum(int(b.get("pending",0))+int(b.get("n",0)) for b in [d]+[v for v in d.values() if isinstance(v,dict) and "pending" in v]); print("doji_sweep" in a, "doji_sweep" in a.get("candles",{}), t)'
```

Expected: `True False <N>` with N above 0 — its own key, never inside the 📐 candles, and holding records. `True False 0`
after such a run means the ledger is dead (the cron container was not redeployed); the key alone proves nothing.


## Result (2026-10-16)

The one pre-registered outcome run (head `2845fe2458bdead69d1db1c2b96245e80f4d6b06`, prereg blob `77cd374b966631fbb95bc9e60231e912bff76c3b`, events
2025-10-10 → 2026-10-15, survivors-only):

| cell | verdict | net of SPY (pp) | CI by 10-session block | CI by name | CI level (%) | Holm p |
|---|---|---|---|---|---|---|
| primary (60%+ under the 52-week high) | `no_signal` | -3.85 | [-7.23, 0.72] | [-6.41, 0.68] | 98.33 | 0.129 |
| any downtrend read | `axes_disagree` | -0.5 | [-1.75, 0.68] | [-0.89, -0.13] | 97.5 | 0.612 |
| control: a test without a doji | `no_signal` | 0.17 | [-2.07, 2.88] | [-1.09, 2.0] | 95.0 | 0.832 |

No edge in any of the three. The served header line (verbatim):

> 🕯️ MEASURED 2026-10-16 (prereg 2845fe2458bdead69d1db1c2b96245e80f4d6b06, survivors-only, candles 2025-10-10 to 2026-10-15): 145 dojis testing the prior low 60%+ under the 52-week high, on 98 sessions across 102 names. Bought at the next open and held 10 sessions, net of SPY over the same sessions: median −3.32% against +0.54% on 770 matched days of the same names in the same downtrend (13 with a short placebo pool, 14 with none) — −3.85 pp (before SPY −3.10 pp), 98.33% CI by 10-session block [−7.23, +0.72], by name [−6.41, +0.68]: no difference this study can separate from zero. Any downtrend read: 2,802 dojis, −0.50 pp, 97.5% CI [−1.75, +0.68] / [−0.89, −0.13]: no verdict — the session-block CI and the by-name CI disagree (AMENDMENTS6: a verdict needs both). The control — a test of the low without a doji, against its own matched days: 2,563 tests, +0.17 pp, 95% CI [−2.07, +2.88] / [−1.09, +2.00]: the tests without a doji show no difference from their matched days that this study can separate from zero. Under the 52-week high by 70%+: 53 dojis on 47 sessions — too few to read (pre-declared). Verdicts are Holm-corrected across these three pre-registered reads (Holm p 0.129 / 0.612 / 0.832); every other cell is exploratory — no verdict. Closed above the doji's high within 5 sessions before closing under its low 46% vs 48% (difference CI by block [−11.78, +8.40] pp); closed under its low within 10 sessions 79% vs 67%. Mean −0.63% (before SPY) against +1.72% on the matched days (difference CI by block [−6.55, +2.46] pp), before costs; −1.13% after a 0.5% round trip. Not advice.

Full per-cell tables: `docs/research/doji_sweep_study_2026_10_16_results.md`. Artifact:
`backend/scripts/doji_sweep_measured.json`. The tab stays a scanner, not an entry.
