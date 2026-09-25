# ⚡ Momentum burst checkbox on Chart Maps (2026-09-24)

**UNMEASURED.** It pins and badges on the Chart Maps boards; it gates nothing, pushes nothing, sizes nothing
and enters no lane.

## The ask, verbatim

Ajay 2026-09-24:

> "I need you to verify and build somethin if we don;t have it. For any stocks on chart maps, wanted to rank them by most
> explosive capable but now I want us to check for momentum burst possibility or give them special attention. Like ORCL was
> going to In deman it had very big momemtum and we were capturing it, Can you add this as a check box in our filters please.."

Asked to define it:

> "volume and ? <1% reversal if its already greator >1.5% is not enough runway for me to catch the upside potential.. is of no use to me"

Direction: "Up moves only". Checkbox behaviour: "Pin + badge, hide nothing". Numbers: "Use the app's numbers".
Asked whether 1.0–1.5% counts: "yes", so there is ONE threshold, 1.5% inclusive.

**Interpretation (not widened).** ⚡ = (a) relative volume ≥ 1.5×, measured fairly for the time of day (never a
partial day against a full-day average), AND (b) the print MORE than 0% and AT MOST 1.5% above TODAY'S session low
(1.5% passes, 1.51% fails), AND (c) up moves only = the print above that low, which (b) already enforces. "Up on the
day" is NOT required: it would have excluded his own ORCL example (below). The day's change is shown in the hover.

## Verify: what already existed

None of these is his read:

- 🧨 explosive read + "🧨 Burst first" sort (`chart_maps/board.py` `attach_explosive`, `supply_demand/explosive.py`):
  closed bars only, MEASURED `no_signal` on 24,922 episodes. The ⚡ module never imports it.
- "📊 Relative volume" sort: the producer row's rvol, which is not fair for the time of day mid-session.
- The canonical time-of-day-fair RVOL: `sepa/intraday_volume.py` `projected_relvol` (front-loaded curve), used by the
  ticker page and the Auto-Pilot gate. It was NOT used on Chart Maps before this.
- The same-day reversal off the low: `alert_gates.approach_read` measures from TODAY'S session low (the 🎯 chip).
  `bounce_room.bounce_read` measures from a touch low up to 5 sessions back and requires ≥ 3% (or ATR%) — always past
  his 1.5% by construction, so it is not the reference.
- The ticker page's "Momentum burst (≥8% in a week)" (`cheetahVerdict.ts` `BONDE_MOM_BURST_1W_PCT`): a different,
  already-moved read. The ⚡ hover says so.

Nothing combined a live, fair RVOL with a ≤1.5% reversal off today's low, and there was no checkbox. Built.

## The rule (`backend/supply_demand/momentum_burst.py`, pure)

| Leg | Pass | Fail | Unknown |
|---|---|---|---|
| Volume | RVOL ≥ `BURST_RVOL_MIN` (1.5, inclusive) | `rvol_low` | `no_volume`, `no_avg`, `rvol_early`, `rvol_half_day` |
| Off the low | 0 < `round((print/low − 1)·100, 2)` ≤ `BURST_MAX_OFF_LOW_PCT` (1.5) | `at_low` (≤ 0), `runway_used` (> 1.5) | `no_print`, `no_low` |
| Session | — | — | `premarket` (short-circuit) |

Any FAIL → `no` (fails listed first); else any UNKNOWN → `unknown`; else `burst`. Judged at 2 decimals: 1.504% → 1.50
passes; 0.004% → 0.00 = at the low; 10.15 over 10 passes (the raw float would not).
RVOL is judged at 2 decimals too, the rounding the canonical `projected_relvol` already returns (and the
Auto-Pilot gate compares): a raw 1.4951× shows 1.50× and passes; a raw 1.4949× shows 1.49× and fails (pinned by
`test_rvol_is_judged_at_two_decimals_like_the_projected_relvol_engine`).

Constants are reused, never retyped: `BURST_RVOL_MIN` mirrors `trading.auto_entry.AUTO_RELVOL_MIN` and the frontend's
`BONDE_BREAKOUT_RVOL` (text-locked by test; auto_entry builds the broker at import, so it is never imported).
`VOL_AVG_BARS` (50) from `sepa.breakout_audit`, `SESSION_MINUTES` / `RVOL_MIN_FRACTION` / `_session_fraction` from
`demand_reentry`, `HALF_DAYS` from `timeframes`, `drop_today` from `zone_store`.

## The RVOL engine, its start, and the 120-minute warning

- Average: the last 50 closed sessions BEFORE the session day (`drop_today` first — the price cache holds today's
  in-progress bar hourly). One `prices.bulk_cached_frames` find per board, never a fetch.
- In RTH: PASS if today's ACTUAL shares already beat 1.5× the full 50-session average (any time); otherwise, once
  `BURST_PROJECTION_MIN_FRAC` (= `RVOL_MIN_FRACTION`, 0.08 ≈ 31 min) of the session has passed, today's volume is
  projected to a full session on `projected_relvol`'s curve. Before 31 min with actual under 1.5× → `rvol_early`.
- Until `LANE_VOL_CONFIRM_MIN_FRAC` (mirrors `auto_entry.VOL_CONFIRM_MIN_FRAC`, 120 min) the hover warns: "Early
  projection: it runs high this soon after the open — the Auto-Pilot does not trust it before 120 min." Wording only.
- Day volume includes pre-market prints (the snapshot counts them); the hover says so.

## Which low

**Today's session low on every board** — the snapshot's day `low`, the same low the 🎯 reversal read
(`alert_gates.approach_read`) measures from. `low_kind = "session_low"` on every read.

## Sessions

| Session | Print | Volume | Day |
|---|---|---|---|
| Pre-market 04:00–09:30 | — | — | every read `unknown` ["premarket"] (Massive's day low is 0) |
| RTH | the last trade, ONLY if it is dated today (else `no_print`: halted / not traded / stale snapshot) | actual, or curve-projected | `_session_day(now)` |
| After hours / closed | the day's CLOSING print (`snap.price`); the after-hours trade is `ext_print`, shown not read | the session's volume, basis `session` | the last trade's date, else the frame's last bar — never the wall clock (00:00–04:00 trap) |
| Weekend / holiday (snapshot zeros) | the cached daily bar's close / low / volume, `print_source = "daily_bar"` | that bar's volume | the frame's last bar |
| Half day (`HALF_DAYS`) | before 13:00 ET no projection (actual only, else `rvol_half_day`); after 13:00 read as after hours | | |

## Payload

- Tile: `burst` = the read with keys exactly `READ_KEYS`: `state, on, reasons, reason_text, rvol, rvol_basis,
  rvol_actual, rvol_projected, session_pct, projection_early, today_vol, avg_vol_50, session_day, off_low_pct, low,
  low_kind, print, print_session, print_source, as_of, ext_print, ext_as_of, prev_close, day_chg_pct, session,
  half_day, badge, title, measured`. `None` only if that tile's build raised.
- Board: `burst_rule` (the rule sentence), `burst_note` (the session line), `burst_counts` `{burst, no, unknown}`
  summing to the served tiles.
- `board()` attaches it LAST (after 🪜), on the board's ONE live map (`_live`, never refetched) plus ONE
  `bulk_cached_frames`. It never reorders, drops or raises. Every number goes through `_f` (the API serializes with
  `allow_nan=False`). ℹ️ rules panel: section `momentum_burst`, built from the constants.

## Frontend behaviour (WP-FE)

`?burst=1` checkbox "⚡ Momentum burst" on every board tab, default OFF, URL only, no refetch. ON = a stable
partition of the tiles the page already shows: ⚡ names first in their served order, then the rest in theirs; a ⚡
badge on each; NOTHING hidden. The count on the checkbox equals the names it pins; "N unknown" and "N behind 🎯"
suffixes when non-zero. The hover prints the served `title` plus a line that it is not the ticker page's ≥8%/week
check and not 🧨 Burst first.

## Exemptions

The 15 tile-board tabs carry it (zones, deep_demand, quick_bounce, breaking, keltner, amd, ipo, gabbar, vcp, topping,
ict, undervalue, zero_dte, earnings, winners). IPO names under 50 sessions read "unknown · fewer than 50 closed
sessions" — honest, not exempt. Exempt, in writing: support (one symbol per view), news (no ticker rows), hot_sectors
(server-cut rows), potus (fixed editorial order), holdings (never re-ordered), and the 10 row boards (ema_frames,
bonde, growth, hot_pullback, patterns, session, signals, catalysts, overnight, gnt: own renderer fed by the per-row
read route — not wired in this build; his call).

## UNMEASURED, and the priors

No study stands behind ⚡. The closest measured reads are null: `explosive_measured.json` (2026-09-15, 24,922 demand
arrivals, HIT5@20): `rvol20_at` top quintile d_hit5 CI [−2.09, +1.12]; `rvol50_at` [−2.24, +1.03]; `day_ret_at`
[+0.06, +3.90] but it FAILED the outside-date placebo. The entry-trigger study (2026-09-15): no volume-burst read moved
it. The flag claims no edge.

## Replay probe 2026-09-24 (one day, 72 names; a probe, NOT a study)

Model: day volume cumulative from 04:00 (pre-market included), low = RTH low, print = minute close, avg = 50 sessions
before the day.

| Projection start | Names ever ⚡ | ⚡ minutes | …of those, up on the day | …full-day RVOL ended < 1.5× |
|---|---|---|---|---|
| 31 min (`RVOL_MIN_FRACTION`) | **8** | 229 | 1 | 4 (ABNB, AMR, ORKA, SYRE) |
| 120 min (`VOL_CONFIRM_MIN_FRAC`) | **4** | 165 | 0 | 2 (ORKA, SYRE) |

| Name | 31-min start | 120-min start | Full-day RVOL |
|---|---|---|---|
| **ORCL** (prev 144.56, low 133.48 in the first 30 min, close 139.53) | **19 min, 10:01–10:20** | **0** | 1.72× |
| RAPP | 12 min | 0 | 2.28× |
| AMD | 0 (volume projected 2.04× at 10:00; 3.21% off the low → runway failed it) | 0 | 0.95× |

Reproduce (outside RTH; read-only — `_mongo_get_day` or an unwritten Massive fetch, never `load_intraday`):

```bash
docker exec -i -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u scripts/momentum_burst_replay_2026_09_24.py --day 2026-09-24 --symbols ORCL,AMD,RAPP --start display'
docker exec -i -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u scripts/momentum_burst_replay_2026_09_24.py --day 2026-09-24 --symbols ORCL,AMD,RAPP --start lane'
```

(The container runs `origin/main`; the script exists there only after the branch is promoted.)

## His call

1. Projection start: built at 31 min with the "early projection" warning until 120 min. Moving to the Auto-Pilot's
   120 min is one line, but on 09-24 it drops ORCL (19 → 0 minutes) and RAPP (12 → 0).
2. "Up moves only" is built as "the print above today's low" (a red day turning up counts — ORCL). Add "up on the day"
   back? 09-24: ORCL 19 → 0 minutes; 8 → 1 names.
3. After the close ⚡ reads the day's closing print (the after-hours trade is shown, not read). Read the after-hours
   trade instead? 4 of 71 names change at 23:51 ET (NBIX 1.42% → 0.13%, RLAY 1.84% → 1.17%).
4. Row tabs: extend ⚡ to the 10 row boards?
5. Edges: RVOL exactly 1.50× counts, and RVOL is judged at 2 decimals (a raw 1.4951× → 1.50× passes); % above the
   low judged at 2 decimals.
6. Label "⚡ Momentum burst" collides with the ticker page's ≥8%/week check and sits next to "🧨 Burst first" — rename?
7. The 1.5× is test-locked to `AUTO_RELVOL_MIN` and `BONDE_BREAKOUT_RVOL` — keep them tied?
8. Half days: after 13:00 read as closed; before 13:00 no projection. OK?
9. UNMEASURED. A study needs a 1-min replay across many days (the shipped script is the start). Want one?
