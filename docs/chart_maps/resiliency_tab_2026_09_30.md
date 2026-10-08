# 🛡️ Resiliency tab on Chart Maps (2026-09-30)

**MEASURED 2026-10-01 — no box predicts the next data day.** T1 box names held +4.33pp [+0.72, +7.83] more often
than peers on the next T1 day and +2.87pp [−1.28, +7.47] on the next ordinary day; the difference, +1.46pp
[−4.53, +7.18], cannot tell the two apart (NO_SIGNAL). T2 box names still held +1.43pp [−0.30, +3.19] more on data
days, but kept less of their ordinary-day margin (−3.33pp [−5.75, −1.01], INVERTED): the T2 box is weaker on data
days — it is not a sell read. The volume-confirmed EOD close did not lead the next session (NO_SIGNAL). Nothing here gates a scan, pushes a phone,
sizes a position or enters a lane (`resiliency_tab.MEASURED = False` stays — the verdict only changes the served
sentences; any gate is his call). Study `backend/scripts/resiliency_study.py`, artifact
`backend/scripts/resiliency_measured.json`, literal `chart_maps/resiliency_measured.py`.

## Result — the persistence study (run 2026-10-01, as of the 2026-09-30 close)

Prereg `docs/research/resiliency_2026_09_30_prereg.md`, commit `20d84110` (pushed before the run). 2,749 of 2,750
names priced. Ran in a throwaway `cheetah-api` container (cache volume mounted read-only, Mongo writes stubbed —
one blocked `price_cache.create_index`), 168 s. Bootstrap over event dates, 2,000 draws, seed 20260930.

| Read | Verdict | Data-day lift | Ordinary-day (placebo) lift | **Event-specific** (the verdict CI) | Events |
|---|---|---|---|---|---|
| T1 🛡️ | **NO_SIGNAL** (general) | +4.33pp [+0.72, +7.83] | +2.87pp [−1.28, +7.47] | **+1.46pp [−4.53, +7.18]** | 42 |
| T2 🛡️ | **INVERTED** | +1.43pp [−0.30, +3.19] | +4.77pp [+2.96, +6.57] | **−3.33pp [−5.75, −1.01]** | 66 |
| EOD tape | **NO_SIGNAL** | next session +0.046pp [−0.011, +0.093] | label-shuffle band [−0.024, +0.024] | — | 450 days |
| Pre-market | UNMEASURED | ≤ 31 patchy intraday sessions | | | |

- 52% of T1 box rows (69% for T2) sit in the lowest volatility quintile (base rate 20%). The lifts are compared
  within σ quintile × β tercile, but that stratification may not remove the quiet-name effect — unmeasured.
- Halves (stratified lift): T1 first +5.29pp [+1.32, +9.42], second +3.26pp [−3.05, +8.71]; T2 first −0.07pp
  [−1.87, +1.73], second +3.15pp [+0.04, +6.24]. Not tested against each other.
- T1 event-day return difference +0.14pp [−0.04, +0.31] (the expectancy line): no edge in return either.
- EOD: the observed +0.046pp sits outside every label shuffle, but the pre-registered read is the stratified CI, which
  spans zero. Size for scale: +0.05pp a session. Next open→close −0.001pp [−0.043, +0.035].
- No stop exists in these reads, so there is no stop-out rate.

Re-run (outside 09:00–16:30 ET, never inside the live api). `--events-json` replays this run's event list; the price
cache and the universe are live, so a re-run drifts from these numbers as bars and names change:

```bash
docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default --env-file <file holding FRED_API_KEY> -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e SEPA_UNIVERSE_MODE=full -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v <main tree>/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v <out dir>:/out -w /out cheetah-api:latest python -u /app/scripts/resiliency_study.py --prereg-commit 20d84110 --as-of 2026-09-30 --events-json /app/scripts/resiliency_measured.json --out /out/resiliency_measured.json
```

## The ask, verbatim

Ajay 2026-09-30:

> "Can you build me a new tab- Resileincy.
>
> This is to help me with
> #1 - Stocks that are not going to by more than 0.5% during a T1 event like FOMC or any others like todays Inflation and GDP track T2s as well.
> #3 - Tape is positive and bullish EOD or Pre market. but volume has to be accounted for. We have all of this data already."

"Today" (Wed 2026-09-30) = Personal Income and Outlays (Core PCE, **T1**) + GDP and ADP (**T2**) on FRED's calendar.
The ask numbers #1 and #3 — **was there a #2?** (his call #20).

## What each box reads

| box | key | definition (constants in `backend/chart_maps/resiliency_tab.py`) |
|---|---|---|
| 🛡️ Held on T1 | `t1` | a close on EVERY T1 session of the last `HOLD_WINDOW_DAYS` (365) days, and on at least `HOLD_RATE_MIN_PCT` (75%) of them the close was no more than `HOLD_MAX_DROP_PCT` (0.5%) under the prior session's close |
| 🛡️ Held on T2 | `t2` | the same on T2-only sessions (`T2_EXCLUDES_T1_DAYS = True`) |
| 📈 Bullish tape EOD | `eod` | `sepa.volume.accumulation_day` on the last closed session: up close, close in the upper half of the range, volume above `momentum_burst.avg_volume_before` (the last `VOL_AVG_BARS` = 50 closed sessions); after the close-confirm minute (16:05, half days 13:05) today's snapshot day bar when it is dated the session with o/h/l/c/v > 0 |
| 🌅 Bullish tape pre-market | `pre` | **volume leg OFF until his call (`PM_VOLUME_VERIFIED = False`, fix round 2026-09-30 — see OPEN below): the read serves `volume_unverified`, `bullish` None, the box passes none.** When turned on: a FRESH pre-market print (`KL.fresh_print`) above the VERIFIED prior close AND the snapshot's accumulated pre-market shares (`min_av`) ≥ `PM_RVOL_MIN` (= `momentum_burst.BURST_RVOL_MIN`, 1.5) × the name's own mean cumulative pre-market volume by the same ET minute over its cached `intraday_cache` sessions (at least `PM_BASELINE_MIN_SESSIONS` = 5, from the last 50 market sessions). 04:00–09:30 ET only |

- Event-day return = prior session close → event session close on closed bars (`pct_ret`, rounded to `PCT_DP` = 2 — the
  % he reads is the % that decides); `held` is inclusive (−0.50 holds, −0.51 does not). No gap-bridging: a missing
  close on the event day or the day before is "no close" and the name is **not rated** (hidden when the box is ticked,
  counted `partial_t1` / `partial_t2`).
- A data day maps to the FIRST trading day on or after its release date (a Good-Friday jobs report reacts on Monday),
  on the benchmark's (`sepa.universe.BENCHMARK`, SPY) closed-bar calendar; today's session never rates itself.
- "SPY fell" = SPY's own event-day close-to-close < 0 (the `down_*` subset and the 🛡️ T1 on SPY-down days order).
- σ = sample stdev of the last 50 daily % returns; β = cov/var against SPY over the last `KL.YEAR_BARS` (252) returns;
  both None unless every return in the window is read.
- 📅 Today (every session since 2026-10-07 — live / after the close / the last session when closed; see the
  2026-10-07 section): `KL.anchor_read` (after the close: the snapshot day bar's regular-session close) against the
  verified prior close (`KL.verify_last`); basis `last_close` is NEVER a read — no print today = `no_print`, never
  "holding +0.00%". A stale cache (the snapshot's prior close disagrees, or the cached bars end before the prior
  market day) = `stale`. **Official prior close (2026-10-07 critic fix)**: in live and after-close reads the move is
  measured against the snapshot's `prev_day_close` when that snapshot's day bar is dated the session
  (`drop10_tab.day_from_snapshot`) and it agrees with the cached close within `drop10_tab.PREV_CLOSE_TOL_PCT` (1%,
  imported); otherwise against the cached close (`resiliency_tab.official_prev_close`). Real case: NNBR's cached
  10-06 close 4.025 vs the official 4.04 — the card said -0.12%, the real move was -0.50%; `verify_last` passed
  because 4.025 is within half a cent of the day's close. `KL.verify_last` itself is unchanged (other tabs use it);
  closed mode (`last_session`) and a data day's pre-market keep the cached closes; the MEASURED study lines are
  byte-identical (golden test).
- The data days are `macro_calendar.past_events` (FRED per-release dates + the Fed's FOMC calendar; see
  `docs/sepa/macro_event_overlay.md` "2026-09-30 — past_events"). Today's events come from `get_macro_calendar()` —
  read ONLY in the background build, never on a request.

## Flow

`board.resiliency_tiles` (the 🏔️ ATH memo pattern): `resiliency_tab.cached_or_warm` (key = session ISO + universe;
stale-while-revalidate; a failed build is served as `error` and retried every `FAIL_RETRY_SEC` = 5 min) → ONE
`_bulk_snaps_fanout(syms + [SPY, RSP])` (the turnover rows from `scanner.load_latest_shared()`, read-only, one
parse per scan write) → in the `pre` phase `pm_cached_or_warm` (ONE `intraday_cache` aggregate + ONE
find on the shared price-cache client's database — never `daytrading.data._get_mongo_coll`, which writes an index on
every call) → `rank` (counts over the whole pool, then the boxes via `dual_momentum_tab.passes` / `parse_mode`, then
`order_key`) → the liquidity floor (`passes_liquidity`, turnover = scan row else `quick_bounce.avg_dollar_vol`) → the
first `LIMIT_MAX × TAPE_POOL_MULT` (240) → `_finish`. `resiliency_tab` never imports `board`.

Sorts (tab-scoped, since 2026-10-07: five tab sorts plus `default`; any other key on this tab → `default`):
`res_today` 📅 Today's move (reads first, biggest gain first) · `res_t1` 🛡️ T1 hold rate (rated first, rate, SPY-down
rate, the smaller worst day, symbol) · `res_t2` 🛡️ T2 hold rate · `res_down` 🛡️ T1 on SPY-down days · `res_growth`
🚀 Sales + EPS growth. `default` is RESOLVED per request (`resolve_sort`): `res_today` when the session is live or
after the close and at least one name has a print, else `res_t1`; the served `sort` is always the explicit key. An
ordinary (non-data) day gets NO `sort_unavailable`; it is set only when an explicit `res_today` has no read
(`TODAY_SORT_NO_READ` → T1 order) or an explicit `res_growth` has nothing ranked (`GROWTH_SORT_UNAVAILABLE`).

## Payload (`GET /chart-maps?tab=resiliency[&sort=][&res=t1,eod][&res_mode=all][&min_tier=]`)

Top level: the generic `board()` keys + `sort`, `sorts` (4; 6 since 2026-10-07 — see the 2026-10-07 section for the
resolved `sort`, `market_line` and `growth`), `note`, `sort_unavailable`, `matched`, `warming` (only
while warming), `resiliency_board`, `tiles`.

`resiliency_board` = `{state: ready|warming|error, session, phase: pre|rth|close|null, market_closed:
null|"weekend"|"holiday YYYY-MM-DD", sort, header, today_line, events_line, rules{hold_max_drop_pct,
hold_rate_min_pct, window_days, t2_excludes_t1, pre_rvol_min, pre_min_sessions, vol_avg_bars, benchmark, lines[]},
events{available, window_days, first, last, t1_sessions, t1_spy_down, t2_sessions, t2_spy_down, t1_by_kind,
t2_by_kind, sources, unsourced, errors}, today{event_day, session, t1, t2, tier, spy_move_pct, spy_tape,
spy_as_of_et, read, holding, down, no_print} | {event_day: false, session, next_t1}, counts{scanned, no_bars,
stale, rated_t1, partial_t1, t1_pass, rated_t2, partial_t2, t2_pass, eod_read, eod_pass, pre_read, pre_pass,
pre_no_baseline, eod_session, no_turnover, dropped_thin, shown}, filters (the Dual Momentum shape, keys t1/t2/eod/pre,
`mode_param` "res_mode"), study{status, run_date, t1|t2|eod|pre: {verdict, text}}, note, measured, built_at}`.

Tile: `symbol, name, theme, href, last_close, bars, lines [], bands [], markers [], badges, stats, why,
resiliency{t1, t2, today, eod, pre, sigma_pct, beta, adv50}, res_filter{t1, t2, eod, pre}` + `published_metrics`;
no `enterable` (🎯 n/a — `enterable.KIND_BY_TAB` untouched). Badges: `🛡️ T1 held {held}/{n} ({rate}%)` (good when
the 🛡️ T1 box passes, else muted) · `📅 T{tier} today · holding {+x.xx}%` (good) / `· down {x.xx}%` (warn) on an event
session · one `{label, tone good, res_filter: key}` per ticked box it passes. Stats: `T1 held`, `T2 held`, `EOD tape`,
`Pre-market`, `Today` (event session only), `T1 worst`, `Last T1`, `σ · β`.

Every number reaching JSON passes a finite-float guard and plain `int`/`float` (Starlette raises on NaN).

## Frontend (WP-FE)

`CM_TABS` gains `resiliency` right after `ath`; `ResiliencyBoardNote` prints the served `header`, `today_line`,
`events_line`, `rules.lines`, box notes, study texts and `note` verbatim; the 4-button sort toggle and the boxes are
the Dual Momentum filter component generalised (`res` / `res_mode`). The card ladder files 🛡️ T1/T2 held on IDENT,
📅 T1/T2 today on PRICE. ✨ entry `chart-maps-resiliency-2026-09-30`.

## HIS CALL (defaults shipped)

1. "not going to by more than 0.5%" read as **DOWN more than 0.5%** (down-only). Alternatives: quiet either way, or vs SPY.
2. Event-day move = **prior close → event-day close**; an intraday dip that recovers counts as held.
3. **Absolute** move, not relative to SPY.
4. Window = **last 365 days**.
5. 🛡️ box = held on **≥ 75%** of the window's sessions.
6. "Rated" needs a close on **every** window session.
7. T2 sessions **exclude** T1 sessions; **PPI counts as T2**; weekly claims are about half of T2 (measured below: 36 of 68).
   Since 2025 every GDP print in the window shared its day with Core PCE, so GDP-only T2 days = 0 (measured below).
8. ISM and Fed-speaker remarks **not counted** (no dated source).
9. FRED **revision-date rows** count as event sessions (retail 2026-09-28, GDP 2024-10-02).
10. "SPY fell" = SPY close-to-close **< 0**; benchmark **SPY**, not RSP.
11. 📈 EOD = the app's **accumulation day** (volume > 1.0× the 50-day average) — or the 1.5× bar?
12. 🌅 = print **> prior close (any %)** AND pre-market shares **≥ 1.5×** own same-minute baseline over **≥ 5** sessions.
13. 🌅 is **live 04:00–09:30 only** (storing the last pre-market read would be a Mongo write — not built).
14. EOD after **16:05** reads today's snapshot day bar; before that the last closed session.
15. "Tape" = **per stock** — or the market's tape gating the list?
16. Tab slot = **right after 🏔️ ATH**.
17. Default order = **T1 hold rate**; boxes combine **ANY** by default; liquidity floor "ok".
18. No push / alert (display only).
19. Study verdict rule: `separates` only when the 95% CI lower bound > 0 **of the event-specific contrast** (lift on
    the data day minus lift on the next ordinary day, same resampled dates) — fix round 2026-09-30, see below.
20. Your ask lists **#1 and #3 — was there a #2?**
21. **OWNER'S CALL (critic 2026-09-30):** the default T1 order is led by near-motionless names — several may be
    pending-takeover pins, unverified (SLAB σ 0.24%/day, DBRG 0.17%, AES 0.23%, TXNM 0.34%, LXP 0.21%, PEN 0.39%) — plus ETFs
    (SMH, GLD) and the benchmark itself (SPY, #9). Options: a σ floor, and/or excluding ETFs and the benchmark from
    the pool. **Not built** — no floor constant exists (Rule #1); the full-universe table below is the evidence.
22. **🌅 volume source:** turn the pre-market volume leg back on with `min.av` as is (and say so on the page), or build
    today's pre-market volume from the same 1-minute bars as the baseline. Until then the 🌅 box passes none.

## OPEN — `min.av` does not equal the 1-min bars (spec WP-BE step 3: STOP-and-report) → volume leg OFF

The 🌅 read compared today's `min.av` (Massive snapshot, accumulated shares) with a baseline summed from the
`intraday_cache` 1-minute bars. Read-only probe 2026-09-30 09:19 ET, `min.av` vs the sum of today's pre-market
1-min bars up to `min.t` (`daytrading.data._fetch_massive_minute`), same process, key never printed:

| name | `min.av` | Σ pre-market 1-min | `min.av` over Σ |
|---|---|---|---|
| NVDA | 1,985,749 | 1,768,105 | +12.3% |
| AAPL | 422,539 | 380,451 | +11.1% |
| SPY | 1,175,571 | 1,147,657 | +2.4% |
| TSLA | 1,255,461 | 1,192,904 | +5.2% |
| MU | 1,091,466 | 967,971 | +12.8% |
| RSP | 50,573 | 49,620 | +1.9% |

The spec's bar was "within 2%": **5 of 6 fail**, always high; the cause is not established. **Fix round 2026-09-30:**
the box had shipped anyway, so `resiliency_tab.PM_VOLUME_VERIFIED = False` now turns the volume leg OFF until Ajay
decides (his call #22): `pre_read` serves state `volume_unverified` with the move and the raw pre-market shares but no
ratio, `bullish` None (a ticked 🌅 box shows nothing), the header, the rules line and the box note say why, and
`board.resiliency_tiles` skips the `intraday_cache` aggregation. Tests: `test_NEG_pre_volume_leg_off_until_his_call`,
`test_NEG_board_skips_the_baseline_while_the_volume_leg_is_off`; the ratio math stays pinned with the leg forced on.

## Fix round 2026-09-30 — the pre-market baseline skipped regular-session-only days

`pm_slots` used to count EVERY cached `intraday_cache` day as a baseline session, so a day cached from the 09:30 open
(no pre-market bars) counted as a ZERO-volume pre-market. Read-only probe: 10,893 of 55,334 docs in the 50-session
window have no pre-market bars, many of them complete regular sessions (BNY 2026-07-28: 390 bars, first 13:30 UTC =
09:30 ET); 816 of the 2,221 names with ≥ 5 sessions carry at least one; the median share of their sessions zeroed was
18% (p90 53%) → the usual volume shrank and `pm_rvol` read ~1.21× high at the median, ~2.1× at p90. Now a day counts
only when it holds pre-market rows or its first bar (`{"$min": "$bars.ts_utc"}` in the one `find`) is before the
09:30 ET open; a regular-only day — or one with no stamp — is skipped, never a zero. Test:
`test_NEG_pm_slots_skip_regular_session_only_days` (pre-fix count 5 → 2 on the BNY-shaped case).

## Fix round 2026-09-30 — the study's primary verdict is the event-specific contrast

σ quintile × β tercile does NOT remove the low-volatility confound. On the critic's synthetic universe with no
persistence at all (800 names, iid returns, holding set only by σ and β, 52 T1 events) the stratified lift read
`separates` in 3 of 3 seeds (+5.78pp [4.26, 7.77], +3.36pp [1.61, 5.26], +2.17pp [0.91, 3.52]) while the ordinary-day
placebo lift was just as large and the event-specific CI spanned 0 every time. The prereg (not yet committed) now makes
the Q1/Q2 verdict read the **event-specific CI** (lift − P1 placebo, same resampled dates); `specific` becomes
`event_specific` (the verdict separates) / `general` (the stratified lift alone clears 0 — a quiet-name trait) /
`unclear`. The served sentence prints the event-specific number and CI and no longer says "same-volatility, same-beta
names". Tests: `test_NEG_synthetic_null_through_run_study_is_no_signal` (160-name version of the critic's null through
`run_study`: stratified CI > 0, verdict `no_signal`) and `test_NEG_no_persistence_never_separates_across_seeds` (30
seeded nulls: the stratified CI clears 0 in ≥ 15, the verdict never separates).

## Full-universe capture (2026-09-30 10:00 ET, branch tree in the api container, read-only; replaces the 11-name smoke)

Source: `scripts/resiliency_tab_cost_probe.py --dump-fixture` run by the critic (before this fix round's changes; the
T1/T2/σ/β reads are unchanged by it). 2,750 names scanned, 2,671 rated on T1, **58 pass the 🛡️ T1 box**, 222 the T2
box, 353 bullish EOD tape; 472 under the liquidity floor; 80 shown. T1 days: 41 (jobs 11, CPI 11, Core PCE 11, FOMC 8),
SPY fell on 19; T2-only: 68 (claims 36, ADP 12, JOLTS 11, PPI 10, retail 9). Build 187 s cold; pre-market aggregate
13.4 s; snapshot fan-out 1.35 s; rank 0.15–0.20 s per sort.

Top 25 of the default (🛡️ T1 hold rate) order, as served:

| # | name | σ %/day | β | T1 held | on SPY-down days | T2 rate |
|---|---|---|---|---|---|---|
| 1 | SLAB | 0.24 | 0.54 | 38/41 (93%) | 18/19 | 93% |
| 2 | DBRG | 0.17 | 0.53 | 38/41 (93%) | 17/19 | 94% |
| 3 | AES | 0.23 | 0.40 | 37/41 (90%) | 17/19 | 85% |
| 4 | TXNM | 0.34 | 0.04 | 37/41 (90%) | 15/19 | 96% |
| 5 | CCO | 0.83 | 0.63 | 35/41 (85%) | 16/19 | 84% |
| 6 | VTR | 1.57 | −0.20 | 33/41 (80%) | 15/19 | 72% |
| 7 | NEE | 0.92 | 0.20 | 33/41 (80%) | 13/19 | 71% |
| 8 | BNTX | 3.82 | 0.92 | 33/41 (80%) | 13/19 | 54% |
| 9 | SPY (benchmark) | 0.73 | 1.00 | 33/41 (80%) | 11/19 | 78% |
| 10 | AIPO | 2.48 | 2.12 | 33/41 (80%) | 11/19 | 62% |
| 11 | SMH (ETF) | 2.47 | 2.37 | 33/41 (80%) | 11/19 | 63% |
| 12 | MPWR | 3.26 | 2.51 | 33/41 (80%) | 11/19 | 57% |
| 13 | DTM | 1.40 | 0.13 | 32/41 (78%) | 16/19 | 71% |
| 14 | BHF | 1.67 | 0.08 | 32/41 (78%) | 16/19 | 84% |
| 15 | EIX | 4.24 | 0.07 | 32/41 (78%) | 15/19 | 69% |
| 16 | LXP | 0.21 | 0.36 | 32/41 (78%) | 14/19 | 79% |
| 17 | MPC | 2.19 | −0.15 | 32/41 (78%) | 14/19 | 65% |
| 18 | PEN | 0.39 | 0.01 | 32/41 (78%) | 14/19 | 81% |
| 19 | UMH | 1.24 | 0.11 | 32/41 (78%) | 13/19 | 63% |
| 20 | PBF | 4.32 | −0.47 | 32/41 (78%) | 13/19 | 49% |
| 21 | CLH | 1.50 | 0.28 | 32/41 (78%) | 13/19 | 66% |
| 22 | KLAC | 3.52 | 2.76 | 32/41 (78%) | 13/19 | 65% |
| 23 | PNTG | 2.01 | 0.23 | 32/41 (78%) | 12/19 | 65% |
| 24 | NTB | 1.10 | 0.41 | 32/41 (78%) | 11/19 | 81% |
| 25 | GLD (ETF) | 1.62 | 0.77 | 32/41 (78%) | 11/19 | 66% |

**The low-σ confound IS visible** (this corrects the 11-name smoke's "not visible"): the top four move 0.17–0.34% a day
— under the 0.5% hold line on an ordinary day — and several may be pending-takeover pins (unverified); ETFs and the benchmark
itself sit in the top 25. Whether to floor σ or drop ETFs / the benchmark is his call #21. The median σ of the 80
cards shown is 1.62%/day.

## Prior measurements (the prior on a new signal is null)

- **Green-on-a-red-day 2026-09-28 — NO_SIGNAL** (branch only): green close + RVOL ≥ 1.5 + upper-half close on a red
  day → −0.30pp vs same-day red twins at 10 sessions [−0.76, +0.15]. The closest prior to #3's "bullish EOD tape with
  volume". Quoted here, never on the served surface.
- Momentum burst UNMEASURED; 🧨 explosiveness, 🎯 enterable, sector heat, ICT, KC/AMD turning: MEASURED null/inverted.
  No study in the repo measures event-day holding or its persistence.

## Verification record (WP-BE)

- `backend/tests/test_resiliency_tab.py` — 64 tests: pure functions (boundaries, Good Friday, T2-excludes-T1, no gap
  bridging, tier stats, the 75% cut, σ/β, EOD states, DST pre-market slots, the 1.5× boundary, today's read), build,
  rank, words, memo, the board payload shape, the api `Query`-object coercion, `min_av` parsing; NEGATIVE: FRED
  all-fail, calendar failure, non-event day, closed Saturday / holiday, stale cache, bars behind, `last_close` never a
  read, NaN/inf frames serialize with `allow_nan=False` and no numpy scalar, memo never mutated, the calendar never
  read on a request, a raising build → error + back-off, no bounce/fake/forecast words, no import from trading/ or push/,
  no `enterable` kind.
- `backend/tests/test_macro_calendar_history_2026_09_30.py` — 17 (see the overlay doc).
- `backend/tests/test_volume_accumulation_day_2026_09_30.py` — 18: golden `_count_accum_dist_days` counts captured on
  the unedited code (flat bars, equal closes, volume == average) unchanged after the extraction.
- Predicted pins updated: `test_ath_tab.py` (TABS ends `ath`, `resiliency`), `test_dual_momentum_tab.py` (exclusion set),
  `test_key_levels.py` (ALLOWED += `chart_maps/resiliency_tab.py`), `test_momentum_burst_2026_09_24.py` (mention set).

## Follow-ups 2026-09-30 — honest 🌅 box, GDP named, the intraday day bar

1. **The 🌅 volume check is OFF, and every surface says so.** While `PM_VOLUME_VERIFIED = False` (the snapshot's
   `min.av` and the cached 1-minute baseline disagree), no served sentence names the 1.5× pre-market bar: the note tail,
   the rules line, the 🌅 box note and the non-pre-market header clause all carry `PRE_OFF_REASON` ("volume check off
   until the two volume sources are reconciled"). `filters_block` serves the 🌅 item with `off: true` + `off_reason`;
   the shared `DualMomentumFilters` greys that box (disabled unless already ticked, so a stale URL can untick it) and
   prints the served reason in place of its count — Dual Momentum serves no `off`, so it is unchanged. The ✨ entry and
   the `TAB_META` blurb no longer promise the volume leg; they say "volume check is OFF". Pinned while the flag is False
   by `tests/test_resiliency_followups_2026_09_30.py`, `src/components/ResiliencyPreOff.test.tsx` (reads the flag from
   `resiliency_tab.py`) and the Resiliency contract. Flip the flag and the 1.5× wording returns (pinned the other way).
2. **GDP is named, not dropped.** A T2 print on a T1 session counts as T1 only (`T2_EXCLUDES_T1_DAYS`); every GDP print
   in the window sat on a Core PCE day, so T2 counted GDP 0 and the header dropped it. `events_summary` now serves
   `t2_on_t1_by_kind` (`t2_on_t1()`), and the header adds e.g. "GDP 0 — every GDP print in the window landed on a T1
   Core PCE day and is counted there". A kind that still counts in T2 (a standalone GDP day) is never explained away.
3. **"day bar (intraday)" during RTH.** A card (and SPY in the 📅 line) with no fresh print is priced off the
   snapshot's day bar; during RTH (`KL.phase == "rth"`) that bar is still forming, so `today.basis` is served as
   `day_bar` and reads "day bar (intraday)"; "day close" only once the phase is `close`. `today.spy_basis` is served.

## 2026-10-07 — 📅 today on every session, biggest gainers first, 🚀 Sales + EPS growth

Ajay 2026-10-07, a red day, verbatim: *"Can you do a scan for me on the reseliency tab.. Is it working? Today is a
very red day.. I wanna see which stocks were reselient cuz Vista was very reselient"* (Vista = VST, Vistra), then,
after being told 📅 only read on T1/T2 data days: *"I want the highest growth stocks on top like Vistra for
example"*. Branch `feat/resiliency-today-every-session-2026-10-07`.

**UNMEASURED — these are orders, not forecasts.** The MEASURED T1/T2/EOD lines above are about data days only and are
byte-identical (pinned against a golden captured from origin/main before the edit). The green-on-a-red-day study
(NO_SIGNAL, above) is not served.

### The 📅 clock — one function (`today_read`) on the 🔻 tab's clock (`drop10_tab.mode_for`)

| mode | when (ET) | 📅 read | pill |
|---|---|---|---|
| `live` | 09:30–16:00 | today's print (`KL.anchor_read`, unchanged) vs the verified prior close | `📅 today · +x.xx%` (T1/T2 day: `📅 T1 today · holding …`, unchanged bytes) |
| `after_close` | 16:00–20:00 (half day: from 13:00) | the snapshot day bar's regular-session close (`drop10_tab.day_from_snapshot`) — never the after-hours print, on data days too | same words, stat `… · day close` |
| `closed` | pre-market on an ordinary day, overnight, weekend, holiday | the LAST closed session's close vs the one before it off the closed bars, only when the cached last bar is that session and `KL.verify_last` says it is final | `📅 last session Wed 10-07 · +x.xx%` — never "today", never a tier, no `Today` stat |
| data-day pre-market | 04:00–09:30 on a T1/T2 day | the live pre-market print (unchanged) | `📅 T1 today · …` |

No print / no trade in today's session / bars behind / a partial cached bar → not read, no pill, never `+0.00%`.
00:00–04:00 and after 20:00 before a data day, the data-day sentence prints "The session has not opened." instead of
the last session's numbers.

### Default order

`default` RESOLVES per request (`resiliency_tab.resolve_sort`): `res_today` (biggest gain first; no read last; ties by
the T1 hold rate) when the mode is live / after_close and at least one name has a read, else `res_t1` (the old T1
order). The served `sort` is the resolved explicit key; `sorts` = six entries, `default` first labelled
"<resolved> (default)" for the generic Sort select; the toggle draws the five explicit keys. `?sort=res_t1` keeps the
T1 order reachable. `TODAY_SORT_UNAVAILABLE` ("not a T1 or T2 data day") is gone — a guard test greps for it.
`res_today` with zero reads → T1 order + `TODAY_SORT_NO_READ`; `res_growth` with nothing ranked → the default
resolution + `GROWTH_SORT_UNAVAILABLE`.

### 🚀 Sales + EPS growth

Per card chip `Sales {s} · EPS {e} YoY ({period})` (IDENT rung) + a `Growth` fold sentence, built ONCE per memo build
in the warm thread from `research.decision_snapshot` (the same projected Mongo read 🔥 Hottest and 🚀 breakouts use —
no request-path read). Sales = `sales.growth_yoy_pct`, falling back to `rev_growth_q_pct` (the Hottest precedent);
EPS = `q_eps_growth_pct` (latest quarter vs the same quarter a year earlier). Quarters not four apart
(`qoq.period_ok` False) → both blank. A leg RANKS only off a material year-ago base: EPS `qoq.MIN_EPS_BASE` ($0.10)
through `qoq._seq_pct`, and the stored figure must agree with its own quarterly series (±0.011, a 2-dp tolerance);
sales `bonde._rev_base` (`MIN_MATERIAL_BASE_REV` $1M). A year-ago loss or a base under the floor shows blank. The 🚀
order = `qoq.score_board` (equal-weight percentile blend, a one-leg name scored on that leg), names with a ranked EPS
leg first, unknown last.

**Data-spine finding (not fixed here):** 116 snapshot names' stored `q_eps_growth_pct` disagrees with
`qoq.yoy_pct(eps_q_series)` (e.g. AAON +26.32% stored vs +257.89% from the series; AMCR +1,483.33% vs +380.00%) —
shown, NOT ranked, the fold says "disagree". Research cache age p50 9.8 d / max 16 d: the fold says "figures cached
{date}".

### Market line (served `market_line`)

`📅 {when}: SPY {x} · RSP {y} · median name {m} ({down|up|flat}) · {up} of {n} names read are up.` — every universe name
read, before the boxes and the floor; the word comes only from the median's sign. RSP = `rotation.tracker.BENCHMARK`,
read off the same ONE snapshot fan-out and the memo's frames.

### Also

`resiliency_tiles` now reads `scanner.load_latest_shared()` (READ-ONLY, one parse per scan write) instead of
parsing the full scan file per request.

### Real capture (throwaway container, `block_writes()`, branch tree read-only)

Wed 2026-10-07 16:03 ET (`after_close`; not a data day — next T1 CPI 10-14). Re-run:
`scripts/resiliency_tab_cost_probe.py --dump-fixture` under `scripts.resiliency_study.block_writes()`.
Attempted writes: `create_index` only. Memo build 44.4 s cold (2,736 names, 2,736 reads); per-request rank 0.15–0.20 s;
fundamentals `decision_snapshot` 2,610 names; 🚀 ranked 2,226, EPS-ranked 1,448.

**Market line (served):** `📅 Today's close (16:00 ET): SPY -0.24% · RSP -0.81% · median name -1.06% (down) · 708 of
2,729 names read are up.` (his intraday read was SPY −0.2 / RSP −0.63 / median −0.84 / 864 of 2,729 — the close was
weaker). 7 names no print, 0 stale.

**Default** → `sort = res_today`, `sort_unavailable` null; reads first, moves non-increasing; no `T1 today` pill.
Tradeable top 15: PENG +13.08 · AVBP +11.93 · PRME +11.43 · BRZE +8.05 · EVH +7.81 · PSIX +7.72 · BKV +7.39 · NWE +7.33 ·
BKH +7.21 · CCOI +6.77 · JANX +6.73 · VSTM +6.65 · GKOS +6.55 · PGNY +6.33 · BCRX +5.66.
**VST** `📅 today · +3.88%` — **#38 of 2,268 Tradeable** names; chip `Sales -5.5% · EPS -6.2% YoY (FY2026 Q2)` (#1,100 on 🚀).

**🚀 `res_growth`** top 10 (all EPS-ranked, score non-increasing): MU `Sales +345.7% · EPS +1,368.5% YoY (FY2026 Q3)` ·
DBRG `Sales — · EPS +1,050.0%` (year-ago revenue ≤ 0, scored on its EPS leg alone) · LPG · BHF · INSW · HCC · KLIC · TER ·
CRDO · VSEC. PBF `Sales +56.2% · EPS — YoY (FY2026 Q2)` (#1,335) and CRI `Sales +5.2% · EPS — YoY (FY2027 Q2)` (#1,656)
never reach the EPS block; TWLO (+4,671.4% off $0.14) #65; NVDA #28.

**`res_t1`** top 24 == the live origin/main default top 24 (GET at 16:05 ET), symbol for symbol: SLAB AES TXNM CCO NEE
BNTX SPY SMH …

The FE fixture `frontend/src/components/__fixtures__/resiliency_tab_2026_10_07.json` is this capture TRIMMED (6
payloads, the first 8 tiles each in served order, bars / curves to their last 30 points); the 13.6 MB original stayed
in the session scratchpad.

### HIS CALL (shipped defaults)

1. "Highest growth" = today's move: the default order is today's biggest gain first whenever the session has a print
   (data days included); fundamentals are the opt-in 🚀 order (VST by fundamentals is negative).
2. Before a session read (pre-market, after 20:00, weekends, holidays) the default stays 🛡️ T1 hold rate, though the
   pill shows the last session's move.
3. After 16:00 the 📅 read is the 16:00 close, not the after-hours print — on T1/T2 days too (16:05–20:00 used to follow
   AH prints).
4. Ordinary-day pre-market 📅 = the last session (dated), not the live pre-market print (🌅 still shows it).
5. The 0.5% hold line colours every day's pill (green at or above −0.5%, amber below).
6. EPS materiality = `qoq.MIN_EPS_BASE` ($0.10) applied to the YEAR-AGO quarter; sales = `bonde.MIN_MATERIAL_BASE_REV`
   ($1M).
7. A stored EPS YoY that disagrees with its own series is shown, not ranked (fixing the spine is separate).
8. 🚀 rank = `qoq.score_board` blend, EPS-ranked block first. **Amended 2026-10-07 b (his YES):** both ranked legs first, then one
   ranked leg (an EPS leg before a sales leg — the EPS-first rule kept inside the one-leg block), then none.
9. Market line population = every universe name read (his "864 of 2,729" framing).
10. ETF / no-filing cards read `no quarterly figures on file` rather than hiding the chip. **Amended 2026-10-07 b:** an ETF now reads
    `Sales · EPS: ETF/fund, no filings`; a doc with no figures still reads `no quarterly figures on file`.
11. (executor) The data-day sentence before 04:00 / after 20:00 says "The session has not opened." rather than print
    the last session's numbers as the data day's.

### Payload deltas

`sort` ∈ `res_today | res_t1 | res_t2 | res_down | res_growth` (never `default` from this tab); `sorts` = 6;
`resiliency_board.market_line`; `today` = always `{event_day, session, t1, t2, tier, next_t1, mode, day, data_pre,
half_day, spy_move_pct, spy_tape, spy_as_of_et, spy_basis, rsp_move_pct, median_move_pct, up, read, holding, down,
no_print, stale}`; `counts` += `today_read, today_up, today_stale, growth_ranked, growth_eps_ranked`; `rules` += 3
lines + `eps_min_base`, `rev_min_base`; tile `resiliency.today` += `mode, day, for_today` (basis `last_session`),
`resiliency.growth` (GrowthRead); badges + the growth chip (last); stats + `Growth` (last).

Tests: `backend/tests/test_resiliency_today_growth_2026_10_07.py` (31), predicted pins in `test_resiliency_tab.py`;
FE `ResiliencyBoardNote.test.tsx`, `cardLadder.test.ts`, `ResiliencyTab.payload.test.tsx` (the real capture
`__fixtures__/resiliency_tab_2026_10_07.json`), `ChartMapsResiliency.test.tsx`; contracts. Mutation spot-checks
(bytecode off): the event gate, `EPS_MIN_BASE`, the after-close branch and re-serving the retired sentence each fail
the new tests.

### Critic fixes 2026-10-07 (same branch)

- **Official prior close** for live / after-close moves — `official_prev_close` (rule in "What each box reads" →
  📅 Today): the snapshot's `prev_day_close` when its day bar is dated the session and within
  `drop10_tab.PREV_CLOSE_TOL_PCT` of the cached close, else the cached close; `prev_close` serves that value.
  Closed mode and a data day's pre-market unchanged; MEASURED lines golden.
- **Market line with the bars behind** (host sleep, closed mode): `today` now serves `spy_state` / `rsp_state`; a
  stale benchmark prints `daily bars behind — not read` (the existing stale wording), never `no print`; with no read
  and stale names the line is `📅 {when}: daily bars behind — not read ({n} names).` (`MARKET_STALE_FMT`), never
  "no name has a print to read yet". `today.stale` is the stale count.
- Tests: `backend/tests/test_resiliency_critic_fixes_2026_10_07.py` (12) — also the sales-without-a-revenue-series
  NEG (never `sales_ranked`, no score when EPS is unranked) and `rank()`'s median + `up` (> 0 only) on a skewed pool;
  FE payload test gains a synthetic closed-mode payload (`last_session` dated pill). Revert checks in a scratch copy:
  nine mutations, each fails its test.

## 2026-10-07 b — 🚀 two legs first + every growth gap says why

Ajay, 2026-10-07, replying to "say if you want DBRG-style one-leg names out of the top block": *"yes please also no #s
for SNDK can you do a deep analysis of data and make sure you do a sanity chcek fo missing data pieces over all."*
The universe-wide audit behind this section is `docs/sepa/missing_data_audit_2026_10_07.md`.

### Order (`order_key`, `SORT_GROWTH`)

`(block, not eps_ranked, -score) + T1 tie-break + symbol`, where `block` = 0 for legs ≥ 2, 1 for one ranked leg, 2 for
none (`legs` counts only when `score` is not None). DBRG (EPS only, score 99.4, sales base −$3.2M) was #2 before; it is
now DELISTED (`sepa/symbols.py`) and, had it stayed, would sit in block 1.

### Reason codes (`growth_read`, PURE; `today=` the build session, `is_etf=`)

Card states: `read`, `no_doc` (was `no_figures` for a missing doc), `no_figures`, `period_mismatch`,
`stale_filings`, `etf`. Per leg (`sales_reason` / `eps_reason`; None = ranked): `stored_missing`, `stored_disagrees`,
`no_series` (all three = PENDING, shown with `*`), `year_ago_loss`, `year_ago_too_small` (BY RULE), `year_ago_missing`,
`not_filed`, or the card state copied in. Evaluation order: ETF → no doc → `qoq.period_ok` False → a latest index
`STALE_FILING_QUARTERS` (= `qoq.YOY_GAP`, 4) or more behind `period_freshness.expected_13f_quarter(today)` (8105 = Q2
2026 on 10-07) → sales → EPS. Sales compares `rev_growth_q_pct` (2 dp, `PCT_AGREE_TOL`) first and falls back to
`sales.growth_yoy_pct` (1 dp, `PCT_AGREE_TOL_1DP` = 0.05 + `PCT_AGREE_TOL`) against `qoq.yoy_pct(rev_q_series)`.
EPS keeps `_yoy_base(eps_q_series, EPS_MIN_BASE)`; a base `unknown` with `ni_q_series[YOY_GAP] <= 0` is
`year_ago_loss` (DISPLAY ONLY — `eps_year_ago_ni`, never a %, never ranked). Executor ordering inside an unknown EPS
base: the NI loss first, then a stored figure (`no_series`), then `year_ago_missing`.

`coverage_class` (first match): two_legs, one_leg, etf, new_listing (no doc and bars < `research.MIN_RESEARCH_BARS`)
/ not_researched, period_gap, stale_filings, pending, by_rule, year_ago_missing, no_filings.

### Words (served; the FE composes none)

- Chip: `Sales {s} · EPS {e} YoY ({period})` with `+x.x%` (half away from zero), `+x.x%*` (shown, not ranked),
  `yr-ago loss`, `yr-ago <$0.10`, `yr-ago <$1M`, `yr-ago n/a`, `not filed`; card states use
  `GROWTH_CHIP_NONE_FMT` = `Sales · EPS: {reason}` (`ETF/fund, no filings`, `new listing, {bars} bars, not
  researched`, `not researched in 16 days`, `no research on file`, `no quarterly figures on file`, `latest filing
  {period}, a year or more past due`, `quarters not a year apart on file`). **No chip contains `—`.**
- Fold (`_growth_stat`): one clause per leg with the exact reason; money via `_usd_short` (`$8.97B`, `-$23.0M`).
- Board (`_block`): `growth_coverage` on every ready block; `growth_line` + `growth_gaps` only when the served sort is
  `res_growth` (Rule #5), None while warming / on error.
- Rules: `growth_rule_line()` from the constants; `rules` += `stale_filing_quarters`, `sales_agree_required`.

### HIS CALL (shipped defaults, one constant each)

1. `SALES_AGREE_REQUIRED = True` — his rule #7 on the sales leg. 151 stored sales figures that disagree with their
   own series (JPM 27.69 vs 17.89, BAC 19.25 vs 3.67, GS…) are shown with `*`, not ranked. (2026-10-07 c: in 141 of
   them the STORED figure is the one that matches the filing — see below.)
2. An ETF never ranks; `STALE_FILING_QUARTERS = qoq.YOY_GAP` (AIQ-class recycled tickers, MRX, GLIBA, SE, ASML, DOX).
   A stricter one-cadence cut would also unrank OPCH, HUBG, PI — his number.
3. The SNDK class (stored % missing, own filings support one) is shown with `*`, not ranked, until a research refresh
   stores it (H1). The alternative — rank the series figure now — changes shipped #7.
4. Inside the one-leg block an EPS-only leg sorts before a sales-only leg (shipped #8 kept).

### Real capture (V3, 2026-10-07 19:01 ET, throwaway container, branch tree read-only, `block_writes()`)

`scripts/resiliency_tab_cost_probe.py --dump-fixture` (MEASURED; the FE fixture `__fixtures__/resiliency_tab_2026_10_07.json`
was regenerated from it, same trim as before + `_sndk_tile`):

- Universe 2,732 (2,736 − DBRG/QRVO/GBTG/PSKY), 0 no-bar; identity `sum(classes) == scanned − no_bars` **True**;
  growth chips containing `—`: **0**; `res_growth` legs non-increasing: **True**.
- Served line: `🚀 Growth on file: 1,342 both legs · 821 one leg · 109 pending refresh · 105 blank by rule · no
  figure 355 (43 ETF/fund, 61 new listing, 57 not researched, 144 no quarterly figures, 7 a year past due, 31 quarters
  not a year apart, 12 year-ago quarter missing) · of 2,732 · 357 figures marked * wait on a research refresh · most
  figures cached 2026-09-27.`
- SNDK: chip `Sales +371.6%* · EPS yr-ago loss YoY (FY2026 Q4)`, gap `pending`, `sales_series_pct` 371.59,
  `eps_year_ago_ni` −23,000,000; position 2,190 of 2,732 on 🚀. DBRG: absent (DELISTED landed).
- Stale: MRX / GLIBA / SE / ASML / DOX `stale_filings`, score None. AIQ reads `etf` (it is in `PINNED_ETFS`, and the ETF
  check runs first), score None. ETF: SPY, QQQ, DRAM `etf`. Disagreement: BAC / JPM / GS `sales_reason
  stored_disagrees` (JPM and GS keep their EPS leg → one-leg; BAC's EPS also disagrees → pending).
- Top 15 Tradeable on 🚀: MU, LPG, BHF, INSW, HCC, KLIC, TER, CRDO, VSEC, PARR, TECK, PLTR, SM, AVGO, ALAB — all on two
  ranked legs, but NOT all clean: KLIC (#6) and CRDO (#8) compare quarters 273 and 455 days apart (2026-10-07 c below). `counts.growth_ranked` 2,163, `growth_eps_ranked` 1,443.

### Payload deltas

`resiliency_board` += `growth_coverage` (`n, classes, top, pending_legs, pending_top, asof, asof_n, n_doc, min_bars,
ttl_days`), `growth_line`, `growth_gaps` (`summary`, `lines`); `rules` += `stale_filing_quarters`,
`sales_agree_required`; `resiliency.growth` += `sales_series_pct, eps_series_pct, sales_agrees, sales_latest,
sales_reason, eps_reason, eps_year_ago_ni, latest_idx, expected_idx, etf, gap, bars`. `COUNT_KEYS` unchanged.

Tests: `backend/tests/test_resiliency_growth_sanity_2026_10_07.py`, `backend/tests/test_qoq_backfill_vintage_2026_10_07.py`;
predicted pins in `test_resiliency_today_growth_2026_10_07.py`, `test_resiliency_tab.py` (`BOARD_KEYS` +3),
`test_breakout_qoq_rank.py`, `test_russell_universe_refresh_2026_09_29.py` (GBTG left the live list); FE
`ResiliencyBoardNote.test.tsx`, `ResiliencyTab.payload.test.tsx` (`_sndk_tile`), contracts (`growth_line` served iff
read). Mutation spot-checks in a scratch copy (V2): the old order tuple, `SALES_AGREE_REQUIRED = False`,
`STALE_FILING_QUARTERS = 99`, dropping `q_period_series` from `BACKFILL_PROJ`, removing `backfill_skip_reason`,
`PCT_AGREE_TOL_1DP = PCT_AGREE_TOL` — each turns a named test red.

## 2026-10-07 c — critic round (8 findings, each with a test that fails without it)

Tests: `backend/tests/test_resiliency_growth_critic_2026_10_07.py`; predicted pins `test_resiliency_today_growth_2026_10_07.py`
(sales token), `test_qoq_backfill_vintage_2026_10_07.py` (the backfill `$set` may carry `q_end_series`). Real-data
re-verification: `<scratch>/data_audit/fix_c/verify_c.py` (throwaway container, `block_writes()`, 0 Massive calls,
the raw vX snapshot mounted read-only). All MEASURED 2026-10-07 after the close unless marked.

1. **Labels four apart, quarters not a year apart.** `qoq.period_ok` compared fiscal LABELS only. Matching each doc's
   `rev_q_series[0]` and `[4]` to the raw vX rows by value (2,007 docs matched): **8** compare quarters that are not a
   year apart — CRDO 455 days (two-leg 96.6, #8; chip +181.7%, the true year-ago quarter gives +114.7%), KLIC 273 (#6;
   the true year-ago EPS is −$0.06, a loss), CAKE 728, MCFT 184, FUBO 273, NCMI 280, NRIX 90, XERS 90. Fix: canslim
   stores `q_end_series` (each report's `end_date`, parallel to the aligned keys); `research.decision_snapshot` serves
   it; `qoq.backfill` / `qoq.realign` move it WITH the keys; `qoq.period_ok(periods, ends=)` is False when
   `qoq.ends_year_apart` is False — `YEAR_DAYS` (365) ± `capital_returns.SAME_QUARTER_DAYS` (45, the existing
   nearest-quarter rounding, reused by name; on this data every good pair sits at 364–371 days and every bad one ≥ 90
   days off, so the window choice moves nothing). Only the 🛡️ 🚀 growth read passes `ends`; every other caller gets the
   label-only answer unchanged. **Until a refresh stores the end dates the 8 still rank** (served today: KLIC #6, CRDO
   #8) — they are in the H1 list. Simulated with the reconstructed end dates: two-leg 1,342 → **1,338**, one-leg 821
   → **817**, quarters-not-a-year-apart 31 → **39**; CRDO → #1,896, KLIC → #1,829; the new top 15: MU, LPG, BHF, INSW,
   HCC, TER, VSEC, PARR, TECK, PLTR, SM, AVGO, ALAB, REPX, MPC (all two-leg).
2. **"Disagrees with the company's own filings" was false for 141 of 151.** Against the raw vX `revenues` rows the
   STORED figure matches the filing in 141 cases and the v1 series in 7 (DDOG, NKE, CPRT, LEN, MKC, SCI, AAON); 2
   neither (BRK-B, DPZ), 1 no vX row (FERG). BAC: stored 19.25 = vX 19.25; the v1 series reads 3.67 off gross revenue.
   The clause now reads `sales +19.25% stored vs +3.67% from the quarterly series on file — the stored figure and the
   quarterly series disagree; not ranked until they agree`; the pending fold no longer says "filings" and no longer
   promises a refresh "realigns them". The ranking gate is unchanged. The 141 are HELD OUT of H1 (a refresh recomputes
   the % from v1 and would rank BAC at +3.7%) — **HIS CALL**: v1 `revenue` for banks and energy names.
3. **"No quarterly figures" split.** 141 of the 144 cards were yfinance-fallback docs with empty series (86 of them have
   Massive quarterly filings in the vX snapshot — SEI, FOUR, MOG-A, HEI-A, PJT, YOU, FIGR; 55 do not — VIK, ONON, AU,
   mostly foreign). No doc records `_massive_error`, so the served read cannot tell the two apart: a `_source ==
   "yfinance"` doc with no figure is the new gap `massive_unused` — chip `Sales · EPS: Massive not used at research
   time, pending refresh`, fold "the research run fell back to yfinance, which had none; Massive's quarterly figures
   were not used on that run — pending a research refresh (a domestic filer usually fills; a foreign filer may stay
   empty)". The remaining 3 (VIAV, BNL, AX — hybrid docs whose latest slots are empty) keep "no quarterly figures";
   "neither provider" is gone from every text.
4. **A year-ago revenue at or under $0 is not a loss.** The sales token is `yr-ago rev ≤$0` (`SALES_NO_REV_TOKEN`);
   `yr-ago loss` stays EPS-only. OKLO: `Sales yr-ago rev ≤$0 · EPS yr-ago loss YoY (FY2026 Q2)`; APLD (−$33.3M, a
   derived-Q4 artifact) reads the same. The by-rule fold says "lost money or had no revenue".
5. **`_etf_set` → `etf_info.cached_etf_set` had no test** (a mutation to `pass` kept all 164 green). Two tests now:
   the cache's ETF is in the set, and `build()` without `etf_fn` reads it and the card is `etf`.
6. **QoQ-rank lag** documented in `docs/sepa/breakout_qoq_rank.md` (HIS CALL).
7. **PSKY = HIS CALL 12** in its `DELISTED` evidence. One Massive reference search by name (`Paramount`, active=true):
   only PZG (Paramount Gold Nevada) — no successor listed under that name. WBD's bars stop the same day; any successor
   is not spliced.
8. **SNDK's expected chip after H1** is `Sales +371.6% · EPS yr-ago loss YoY (FY2026 Q4)` — its fiscal label when
   Massive serves the refresh (only the yfinance fallback reads `Q2 2026`).

Served line after this round (MEASURED, the branch memo, before any refresh): `🚀 Growth on file: 1,342 both legs ·
821 one leg · 109 pending refresh · 105 blank by rule · no figure 355 (43 ETF/fund, 61 new listing, 57 not researched,
141 Massive not used at research time, 3 no quarterly figures, 7 a year past due, 31 quarters not a year apart, 12
year-ago quarter missing) · of 2,732 · 357 figures marked * wait on a research refresh · most figures cached
2026-09-27.` Identity True, 0 chips with `—`. SNDK: `Sales +371.6%* · EPS yr-ago loss YoY (FY2026 Q4)`, pending.
DBRG absent. `growth_coverage.classes` += `massive_unused`; `growth` += `massive_unused` (bool).

## 2026-10-08 — the revenue line: banks rank on the 10-Q's net revenue

Ajay 2026-10-08, asked "Want those ranked?" about the 141 held-out names: *"update them please"*. **Supersedes** the
"HIS CALL: v1 `revenue` for banks and energy names" above (the 141 held out of H1, and HIS CALL 1's "141 of them the
STORED figure matches the filing"). Corrected, MEASURED on the R-file face of each latest 10-Q
(`docs/sepa/revenue_lines_2026_10_08.csv`): the stored figure matches the 10-Q for **62 of 139**, plain v1 `revenue`
for 68 of 139.

- The line is chosen in ONE place, `massive_fundamentals.revenue_line` (semantic change 7): financial template →
  revenue − cost_of_revenue (2026-10-08 critic round 2: other income is NOT added; C's CIK pick adds it); other
  templates → v1 `revenue`; 8 CIK picks; a 39-name hold ledger. It rides to the doc as `fundamentals.rev_line`, `rev_line_series`, `rev_line_note`, `rev_line_mixed`
  (`canslim._one_revenue_line`; `research.DECISION_FIELDS`).
- `growth_read` (sales step, after the rule reasons, which keep priority): a ledger note or an `undetermined`
  latest / year-ago slot (read PER SLOT from `rev_line_series` — `rev_line` is the newest FILED slot's line and is
  never `undetermined` on a written doc; 2026-10-08 critic round 2) → `sales_reason = "line_unverified"`, shown with `*`, **never ranked — even when the stored figure agrees
  with its series**; a mixed series whose year-ago slot is holed → `line_mixed`. New keys `sales_line`,
  `sales_line_words`, `sales_line_note`. A legacy doc (no `rev_line*`) reads exactly as before.
- Coverage class `revenue_line` (`REVENUE_LINE_CLASS`, after `by_rule`); the 🚀 line adds
  `· n revenue line not the 10-Q's` ONLY when n > 0 (the 0-count line is byte-identical); the fold adds
  `revenue line not the 10-Q's (n): …` names by adv50. Chip unchanged (`+27.4%*`, or `line n/a` with no figure);
  the line words live in the Growth stat only (`sales +14.99% (total revenue net of interest expense)`).
- Dry run on the real v1 rows (0 Massive calls, branch tree, `block_writes()`): **107 of 141 rank, all 107 match the
  10-Q** (99 on % and both levels; CI PAYX CNC STZ MOH EVR on % only; CB, YUM on levels only); **0 ranked on a figure
  the 10-Q contradicts**; 34 `line_unverified` each with its ledger note; `rev_growth_q_pct == yoy_pct(rev_q_series)`
  151 of 151. BAC 19.25 → **14.99**, JPM 27.69, GS 39.46, C 14.30, NEE 4.69 → 12.45, GE 24.73 → 21.10; SOFI +27.35*
  and CVX +51.43* held with their reasons.
- HIS CALLs (shipped defaults): the 8 sub-line names stay `*` (H1); the 7 revenue + interest-income picks and PGR not
  promoted (H2); the rule applies universe-wide (H3); a bank quarter with no interest-expense line is a hole (H4);
  the monthly audit cron line (H5). See `docs/sepa/revenue_lines_2026_10_08.md`.
- Tests: `tests/test_resiliency_revenue_line_2026_10_08.py`, `frontend/src/components/ResiliencyRevenueLine.test.tsx`
  (fixture built by `backend/scripts/resiliency_revenue_line_fixture.py` from the real builders).

### 2026-10-08 b — critic round 2 (the hole is read per slot)

The `undetermined` branch could never fire: `canslim._one_revenue_line` takes `rev_line` from the newest slot with a
value, and a hole has none. A bank quarter with no cost line at slot 0 read `Sales not filed` / "sales: no figure on
file"; at slot 4 `Sales yr-ago n/a` / "the year-ago quarter is not on file (a spin-off, an IPO's first year, …)" —
both false reasons (no gross revenue leaked; no gate moved). Now `growth_read` reads `rev_line_series[0]` and
`rev_line_series[4]`: either one `undetermined` → `line_unverified`, chip `Sales line n/a`, fold "sales: not ranked —
no revenue line for a quarter compared (the provider's bank-template row has no interest-expense line to net)". A hole
in a MIDDLE slot does not hold the leg. Reach today 0 on slots 0/4 (STT 2024-06-30 sits in slot 8). Tests:
`tests/test_revenue_line_critic_2026_10_08.py` (real BAC rows with the STT shape → `canslim._fetch_massive_financials`
→ `growth_read`, slot 0 and slot 4; the old hand-built `rev_line="undetermined"` doc is gone); the FE fixture is
rebuilt from the same production-shaped doc (`ResiliencyRevenueLine.test.tsx`).
