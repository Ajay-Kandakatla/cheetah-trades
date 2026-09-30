# 🛡️ Resiliency tab on Chart Maps (2026-09-30)

**UNMEASURED.** No study in this app says a name that held on past T1 days holds on the next one, and a quiet,
low-volatility name holds most days by construction — its typical daily move (σ) and beta (β) are on every card.
The tape reads are the app's own definitions (the accumulation day; the 1.5× volume bar). Nothing here gates a scan,
pushes a phone, sizes a position or enters a lane (`resiliency_tab.MEASURED = False`; the persistence study is
`backend/scripts/resiliency_study.py`, its verdict literal `chart_maps/resiliency_measured.py`, read lazily).

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
- 📅 Today (a T1/T2 session only): `KL.anchor_read` against the verified prior close (`KL.verify_last`); basis
  `last_close` is NEVER a read — no print today = `no_print`, never "holding +0.00%". A stale cache (the snapshot's
  prior close disagrees, or the cached bars end before the prior market day) = `stale`.
- The data days are `macro_calendar.past_events` (FRED per-release dates + the Fed's FOMC calendar; see
  `docs/sepa/macro_event_overlay.md` "2026-09-30 — past_events"). Today's events come from `get_macro_calendar()` —
  read ONLY in the background build, never on a request.

## Flow

`board.resiliency_tiles` (the 🏔️ ATH memo pattern): `resiliency_tab.cached_or_warm` (key = session ISO + universe;
stale-while-revalidate; a failed build is served as `error` and retried every `FAIL_RETRY_SEC` = 5 min) → ONE
`_bulk_snaps_fanout(syms + [SPY])` → in the `pre` phase `pm_cached_or_warm` (ONE `intraday_cache` aggregate + ONE
find on the shared price-cache client's database — never `daytrading.data._get_mongo_coll`, which writes an index on
every call) → `rank` (counts over the whole pool, then the boxes via `dual_momentum_tab.passes` / `parse_mode`, then
`order_key`) → the liquidity floor (`passes_liquidity`, turnover = scan row else `quick_bounce.avg_dollar_vol`) → the
first `LIMIT_MAX × TAPE_POOL_MULT` (240) → `_finish`. `resiliency_tab` never imports `board`.

Sorts (tab-scoped, exactly these four served; any other key on this tab → `default`): `default` 🛡️ T1 hold rate
(rated first, rate, SPY-down rate, the smaller worst day, symbol) · `res_t2` 🛡️ T2 hold rate · `res_down` 🛡️ T1 on
SPY-down days · `res_today` 📅 Today's move (reads first, biggest move first; on a non-event session
`sort_unavailable` = "Today is not a T1 or T2 data day — the board is in T1 hold-rate order.").

## Payload (`GET /chart-maps?tab=resiliency[&sort=][&res=t1,eod][&res_mode=all][&min_tier=]`)

Top level: the generic `board()` keys + `sort`, `sorts` (4), `note`, `sort_unavailable`, `matched`, `warming` (only
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
