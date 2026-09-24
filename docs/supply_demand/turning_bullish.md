# Turning Bullish — KC Coiled and AMD Raided

**Both boards were measured against a placebo on 2026-09-13 and BOTH CAME BACK INVERTED on their own claim — and re-measured on 2026-09-14 on the wide list (~3,700 names) with the AMD detector that can fail a cycle: Keltner harder (−16.2pp on its break claim), AMD −4.2pp instead of −8.9pp, still inverted.** Not null — inverted. Read §3 before §2.

See also: [`amd_all_raids_2026_09_24.md`](amd_all_raids_2026_09_24.md) — every AMD raid (past on closed bars, today provisional) listed and numbered on the daily Support tile; display only, the 🌀 tab and its grades unchanged.

Ajay 2026-09-13: *"I want you to build a page for something that is very close
to bullish in keltners and AMD"*, *"AMD is accumulation manipulation indicator
we have in charts"*, *"I need two tabs in chart maps for me to look at where
stocks are bullish in the recent 6 months where they are turning bullish"*, and
*"give me a Kelner base verdict and AMD based verdict of stocks when I check
those boxes in the charts as well"*.

---

## 1. What shipped

| Surface | What it is |
|---|---|
| Chart Maps tab `keltner` — 🌀 KC Coiled | Board of names coiled and leaning up |
| Chart Maps tab `amd` — 🌀 AMD Raided | Board of names whose base low was just swept |
| Verdict badge on any chart tile | `KC coiled up · squeeze 4b` / `AMD raided · 2d ago`, when the Keltner / AMD checkbox is ticked |
| `supply_demand/turning_bullish.py` | The verdicts, the nightly sweep, the two boards |
| Cron `20 17 * * 1-5` | `market_hours.gate supply_demand.turning_bullish warm` |
| `backend/scripts/turning_bullish_{keltner,amd}_study.py` | The measurements, re-runnable verbatim |

Nothing here pushes, gates a scan, or buys in any lane, and `keltner.CITED` and
`amd.CITED` are both `False`.

---

## 2. The two verdicts

Both are taken from the existing study modules' **own** mechanics —
`keltner.channel/squeeze` and `amd.find_cycle` are *called*, never
reimplemented, so a name's board row and its chart can never disagree.

### Keltner — `coiled_up`

All three, or it is not the state:

1. `squeeze.on` **or** `squeeze.released` — the Bollinger(20, 2) band sits
   inside a `SQUEEZE_MULT` (1.5×) Keltner channel, or left it on the last bar;
2. `channel.position ≥ COILED_MIN_POSITION` (0.5) — the upper half of the 2×
   channel. The channel's own midpoint is the only non-arbitrary line in it;
3. `EMA(EMA_LEN)` higher than it was `MID_SLOPE_BARS` (20) bars ago.

Grades, widest first: `breaking_up` (position > 1.0) · **`coiled_up`** ·
`upper_half` · `none`. `_mid_rising` returns `None`, never `False`, when there
is not enough history — "cannot tell" must not render as "no".

### AMD — `raided`

`amd.find_cycle(direction="bullish").phase == "manipulation"` with
`manipulation.bars_ago <= MAX_RAID_BARS_AGO` (3). No new threshold was
invented: the phase is the module's own. The base low was traded through and
the bar **closed back inside** — a close *beyond* the edge is a breakout and
means the opposite thing, which is the entire test.

Grades: `marked_up` (distribution) · **`raided`** · `basing` · `none`.

`WINDOW_SESSIONS = 126` is his "recent 6 months" in trading sessions.

---

## 3. The measurement — and why the pages say "INVERTED"

### Keltner (`turning_bullish_keltner_study.py`)

**Re-measured 2026-09-14** on the wide list (`full` ∪ `broad`, 3,704 names,
Ajay: "about 4k is what we discussed"), **1,662,135 eligible closed daily
bars**, two years to 2026-09-14. Walked bar by bar from index 41; every series
recomputed vectorised and proved prefix-stable against the real
`keltner.channel()/squeeze()` at 12 checkpoints (0 mismatches). CIs are
**symbol-clustered** bootstraps — bars inside one name are autocorrelated and
21-day windows overlap, so an iid bar bootstrap would print intervals several
times too tight. The 2026-09-13 run (2,660 names) is kept in the table for
comparison; the wider list made every number **worse**, not better.

Fire rate **5.50% of bars** (240 names on the last close of the wide list; 154
of the 2,686 the board draws from, on the 2026-09-14 nightly sweep). 97% of names fire at least once in two
years: recurring, not rare.

Forward close-to-close, coiled minus placebo (every non-firing bar of the same
names in the same window):

| Horizon | Coiled median | Placebo median | Lift | 95% CI | 2026-09-13 lift |
|---|---|---|---|---|---|
| 5d | −0.14% | +0.08% | **−0.22pp** | −0.27 … −0.17 | −0.20pp |
| 10d | −0.11% | +0.20% | **−0.30pp** | −0.40 … −0.20 | −0.23pp |
| 21d | −0.17% | +0.37% | **−0.55pp** | −0.72 … −0.37 | −0.33pp |

Win rate 48.3% vs 50.7% at 5d. **Every horizon negative, every CI clear of
zero.**

The **matched control** — same `position ≥ 0.5`, same rising EMA-20, squeeze
**off** (n = 510,721 at 21d) — is what separates "the squeeze does something"
from "buying the upper half does something":

* coiled − matched: 5d −0.14pp [−0.18, −0.06] · 10d −0.16pp [−0.25, −0.03] ·
  21d −0.25pp [−0.47, −0.06]. On 2026-09-13 this read "the squeeze contributes
  nothing" (+0.11pp, CI spanning zero); on the wide list **the squeeze itself
  subtracts**, every CI clear of zero.
* The rest of the negative lift is the "upper half + rising EMA" selection,
  which by itself underperforms (matched 21d median +0.07% vs placebo +0.37%).

**The claim itself, inverted.** Does a coiled bar precede a close above the
upper band within 21 sessions?

| Pool | Rate | 95% CI |
|---|---|---|
| Coiled | 38.63% | 37.77 … 39.55 |
| Non-coiled, all bars | 36.74% | 36.28 … 37.17 |
| **Matched control** | **55.42%** | 54.87 … 55.94 |

Against a random bar it looks like +2.38pp [+1.42, +3.27] — and that entire
gain is the `position ≥ 0.5` term. Against the honest control the coiled bar is
**16.20pp LESS likely** [−17.15, −15.27] to break its upper band (2026-09-13:
−14.83pp). The module's own sentence, measured: compression is compression,
and it persists.

**The one positive cell did not survive.** Pre-registered split on coil
length, 21d median vs the matched control:

| Coil bars | n | names | 21d vs matched | 95% CI | 2026-09-13 |
|---|---|---|---|---|---|
| 1–5 | 48,954 | 3,553 | −0.31pp | −0.50 … −0.13 | −0.02pp |
| 6–10 | 19,879 | 2,961 | −0.38pp | −0.61 … −0.13 | −0.02pp |
| 11–20 | 13,263 | 2,060 | −0.07pp | −0.40 … +0.32 | +0.42pp |
| 21+ | 4,754 | 752 | **+0.23pp** | **−0.44 … +0.88** | **+1.34pp [+0.39, +2.33]** |

On 2,660 names the 21+ cell beat the control at all three horizons with CIs
clear of zero and was the stated reason the board sorts longest-coil-first. On
3,704 names it is a null at every horizon (5d +0.07pp [−0.10, +0.24], 10d
+0.15pp [−0.08, +0.63]). **The sort stays as an order — a longer coil is a
tighter, longer-watched level — and is no longer described as measured.**
13 names on the wide list's last close carry a 21+ bar coil.

### AMD (`turning_bullish_amd_study.py`)

**Re-measured 2026-09-14, twice.** The 2026-09-13 run (2,666 names, `full`)
walked a detector that could not FAIL a cycle: after a raid it only looked for
a close above the top, so every bar within 10 sessions of a raid whose base
had already broken still counted as "raided" — **237,802 bars, as many as the
real fires (240,461)**. Both fixes from §6 (the failed phase; a base formed
after a failure is the live read) are in the detector this run walked, on the
wide list (`full` ∪ `broad`, 3,712 names). 1,592,057 evaluated bars, 441
sessions each after a 60-bar warm-up, 2024-12-09 → 2026-09-14. The real
`amd.find_cycle` called on `df.iloc[:t+1]` at **every** bar — no
reimplementation, no sampling, no lookahead (the failure scan runs to the end
of the slice, never past `t`). CIs are the **wider** of symbol-clustered and
date-block-clustered bootstraps.

Fire rate **15.1% of all bars** (30.3% on 2026-09-13 with the old detector);
759 of 3,634 names (20.9%) on the
last close at `bars_ago ≤ 10`, 589 (16.2%) at the board's 3. Phase mix over
1.59M bars: accumulation 33.8%, distribution 24.5%, failed 24.5%,
manipulation 16.8%.

Forward returns against every other bar of the same names: 5d −0.36%
[−0.77, −0.06], 10d −0.48% [−1.07, −0.02], 21d −0.41% [−1.11, +0.15];
medians span zero; win rate 49.2% vs 50.7% at 5d. Against the like-for-like
bar below: 5d −0.34% [−0.63, −0.09], 10d −0.42% [−0.81, −0.07], 21d −0.47%
[−1.39, +0.28].

**The claim itself, still inverted.** Does a fresh raid precede a close above
that bar's own base top within 21 sessions?

| Placebo | Signal | Placebo | Lift | 95% CI | 2026-09-13 |
|---|---|---|---|---|---|
| Literal (all non-firing) | 51.96% | 64.13% | −12.2pp | −15.3 … −9.2 | −21.2pp |
| "Edge still above price", gap-matched | 51.9% | 49.5% | +2.4pp | +0.2 … +4.2 | +7.3pp |
| **Like-for-like** (bar inside its own LIVE base, distance-matched) | **51.9%** | **56.1%** | **−4.20pp** | **−6.92 … −1.89** | −8.92pp |

The +2.4pp is the same artifact as last time, smaller: that pool is names
sitting far below a base and never climbing back. By distance the signal
**loses in all four near buckets** (0–1% −1.2pp, 1–2% −1.0pp, 2–3.5% −4.0pp,
3.5–5% −4.5pp) and only "wins" from 5% out (+1.2, +8.8, +16.1pp) — entirely
off broken placebo names.

The honest control is negative in **all seven** distance buckets: −2.0, −2.3,
−5.0, −6.8, −5.1, −3.2, −1.5pp. Four narrower placebo pools agree — never
distributed −4.1pp [−6.47, −1.44], stale raid −2.9pp [−4.86, −0.66], already
distributing −5.3pp [−8.05, −2.60], **live base only −5.3pp [−7.72, −2.71]**
(the pool added 2026-09-14 so the placebo is asked the same question the
signal's own definition asks).

**Why the first re-run that day printed a null.** Run with the failed phase
but *without* the age-out, 57% of all bars sat in a dead base and the
like-for-like placebo was two-thirds dead-base bars (315,627 vs 513,007 now);
it measured −2.1pp [−4.27, +0.08]. That run is superseded; nothing quotes it.

**Recency rescues nothing.** Fresh (0–3) vs stale (4–10) on returns: 5d
−0.17% [−0.64, +0.27], 10d −0.20% [−0.72, +0.28], 21d −0.05% [−0.65, +0.64].
Against the like-for-like placebo the **fresh cut is the one further under
water** (−5.58pp [−8.97, −2.69]) while stale is −1.29pp [−3.12, +0.30]. So
`MAX_RAID_BARS_AGO = 3` is a **board-size cut, never an accuracy gain**, and
the source says so.

The module's own-phase secondary ("reads distribution within 21 bars") is no
longer like-for-like — a failed base cannot read distribution without a whole
new cycle — and is not quoted.

**Overlap, by the two boards' own grades** (`coiled_up` and `raided ≤ 3`) on
the last close of the wide list: KC Coiled 235, AMD Raided 593, both 32 —
*below* the 37.5 expected under independence (the verdict grades differ by a
few names from the studies' own vectorised last-bar counts, 240 and 589; the
overlap is deliberately the boards' predicate). The two verdicts are not
measuring the same thing, and neither confirms the other.

### What the pages are allowed to say

Not allowed anywhere: "coiled to run", "markup next", "accumulation complete",
any bare reach rate without its placebo, any framing where a raid or a coil is
a reason to buy, the "edge-still-above-price" number (+7.3pp on 2026-09-13,
+2.4pp on 2026-09-14 — an artifact both times), the 21+-bar coil cell as a
measured edge (it did not survive the wide list), and any 2026-09-13 AMD number
as a CURRENT value (it was measured on a detector that could not fail a cycle;
as a dated comparison beside the 2026-09-14 number it is fine).

---

## 4. Defects found and fixed on the way

1. **`keltner.reading().where` said "lower half" for an unknown.** `position`
   is `None` when the channel has no span (ATR collapsed to zero — a halted or
   one-price name) and the branch chain fell through to a *concrete* string. An
   unknown rendered as a definite state. Now `"unknown"`.
2. **`board()` gated on `if studies:`, not `studies is True`.** FastAPI
   resolves `Query(...)` defaults at request time, so every direct in-container
   call — the smoke-test path — hands `board()` a truthy `Query` object and
   silently ran with studies ON. Same bug shipped twice on the demand board
   (2026-08-14). Guarded by a test.
3. **The verdict moved with the zoom dropdown.** `_attach_studies` sliced the
   frame to `days` *before* computing, and `amd.LOOKBACK` is 180 bars — so a
   base plainly visible on the 1-year chart vanished on the 6-month one, and at
   `days=20` both modules returned `None` with nothing said. The verdict is now
   read on the **full frame**; only the drawing follows the zoom.
4. **Ticking any overlay refetched the whole board.** `load` depended on the
   `hiddenOverlays` Set and `toggleOverlay` builds a new Set per click, so all
   twelve families — including pure client-side filters — triggered a 24-tile
   refetch. It now depends on `studiesWanted(...)`, a boolean, which is what
   the 2026-09-12 note already claimed.
5. **The Keltner channel was drawn as three flat lines** (Ajay, MU: *"it
   should flat horizontal. Are they accurate?"*). The values were accurate at
   the last bar — verified to the cent against an independent EMA-20 + 2×Wilder
   ATR-10 computation — and drawn across every bar, so the picture asserted the
   band sat at 1056.21 all window when the midline was 921.60 sixty bars back
   against 960.61 now. Now a **curve**: `keltner.channel_series` per bar,
   aligned to the tile's bars **by date** (a positional tail would shift the
   whole channel when the tile carries today's live extended-hours bar), with
   `None` rendered as a gap rather than joined through.
6. **Both study families are off by default**, so the tabs would have opened as
   bare candles. A tab's own family is forced visible on that tab only
   (`hiddenForTab`), and its ledger checkbox shows ticked-and-disabled rather
   than unticked-but-drawn.

---

## 5. Files

```
backend/supply_demand/turning_bullish.py      verdicts, sweep, boards, CLI
backend/supply_demand/keltner.py              + channel_series, where:"unknown"
backend/chart_maps/board.py                   turning_bullish_tiles, _keltner_curves,
                                              _attach_verdicts, _verdict_badges, _turning_note
backend/supply_demand/rules_info.py           "turning_bullish" section
backend/crontab                               20 17 * * 1-5
backend/scripts/turning_bullish_keltner_study.py
backend/scripts/turning_bullish_amd_study.py
backend/tests/test_turning_bullish.py         25 tests
backend/tests/test_amd_chips_2026_09_21.py    the in-flight read before the open (30)
backend/tests/test_board_snapshot_2026_09_21.py  one live-quote call per request (29)
backend/scripts/snapshot_cost_probe.py        what the whole-sweep count costs (re-runnable)
frontend/src/lib/chartMaps.ts                 CmCurve, curveLabels, CM_TABS, TAB_META
frontend/src/lib/chartOverlays.ts             tabFamily, hiddenForTab, curve+badge gating
frontend/src/components/PatternChart.tsx      polyline rendering with gaps
frontend/src/components/OverlayLegend.tsx     locked family
frontend/src/lib/turningBullish.test.ts
```

---

## 6. Verification 2026-09-14 — what his own holdings exposed

Ajay: *"I would [like] the AMD, KC logic and also supply demand logic on all
charts of Chart Maps to be verified. Also make it a lil more sophisticated."*
Reproduced on the seven names on his Portfolio page before anything was
changed. Tests: `backend/tests/test_chart_studies_verified_2026_09_14.py`.

### The AMD cycle never failed

`find_cycle` scanned the bars after a raid for ONE thing: a close above the
top of the base (the markup). A close **below the raided edge** was invisible.

| Name | Base | Raid | Closed under the base | Read on 09-14 |
|---|---|---|---|---|
| CRDO | 229.18–286.24 (9 bars) | 08-20 at 226.58 | 08-24 (222.61) | "manipulation", price 150 (−35%) |
| GLW | 149.25–176.94 (13) | 08-21 at 148.05 | 08-24 (145.55) | "manipulation" |
| ALAB | 285.68–367.85 (8) | 08-19 at 278.18 | 08-21 (284.97) | "manipulation" |

Three of his seven holdings drew a dead base and a raid line as a live read.
Worse for the board: GLW on 08-24 had `raid_bars_ago == 1`, so it was
**"AMD raided · 1d ago"** on the Raided tab the day after its base gave way.

**Now:** a close through the raided edge before any markup ends the cycle in
`phase == "failed"` (no bar limit — a base that broke three months ago is not
a live read), the verdict grades it `failed` ("AMD base failed · Nd ago",
warn tone), the band label says `base FAILED`, and a red ✗ marks the bar. A
collapse *after* a completed markup is the next story and leaves
`distribution` alone.

### Words that contradicted the picture

* `KC no read` for CRDO at position −0.24. "Below the lower band" is the
  channel's own definition of a downside expansion; it now has a name
  (`below_band`, warn) and so does `lower_half`. `none` means only "no
  channel".
* `AMD no cycle · 16d ago` — a stale raid graded `none` with the raid's age
  appended. Now `stale` → "AMD raid stale · 16d ago"; `none` carries no age.

### Both the curve AND the flat lines

The 2026-09-13 curve fix added the bending channel but `_study_overlays`
kept emitting the three flat `KC upper/mid/lower` lines, so any tile with
the Keltner box ticked drew both, with duplicate right-edge labels. The flat
lines are dropped whenever the tile carries the curve (backend), and
`filterTile` drops them client-side too for cached docs.

### Ticking any study box on the 🌀 tabs drew everything twice

`_attach_studies` re-attached the tab's own family on tiles that already
carried it from the stored row: two base rects at double opacity, two raid
lines, six curves, "AMD raided · 1d ago" ×2. Bands, lines, markers and
badges are now de-duplicated on the way in.

### Sophistication (description, never a gate)

* The raid carries `depth_pct` (how far through the edge the wick went) and
  `vol_ratio` (the raid bar against the 20 bars before it); the label reads
  `AMD M — raid 226.58 (−1.1%, 1.8× vol)`.
* Every stage carries its bar `date`, and the drawing marks **A** on the
  base's first bar, **M** on the raid bar, **D** on the markup bar, **✗** on
  the failure bar. The stored nightly row carries the same dates, so the
  Raided board marks its bars without a second frame read.
* `keltner.squeeze_series` — the TTM dot row, one dot under every bar the
  Bollinger band sits inside the channel — rides with the curve; the badge
  says how tight (`squeeze 6b · 0.71× wide`).

### Second pass the same evening: the age-out, the wide list, the re-measure

Adding the failed phase with **no bar limit** created its own defect, caught by
a read-only review of the study against the detector: `find_cycle` walks back
from the latest bar and returns the first base that has a raid, so a base that
raided and then failed months ago kept winning over a fresher base that had
not raided yet. Measured on the 2,673 `full` names: **699 read "base failed ·
Nd ago" over a live base**, 330 of them 31–90 sessions old (probe:
`backend/scripts/amd_failed_age_probe.py`, run before and after). Fix: a base that
forms *entirely after* the failure bar is the read and the failed cycle is
history (a base that spans the breakdown does not count; a completed markup
still wins over a bare base, as on 2026-09-13). After it: 686 read `basing`,
885 stay `failed`, all but a dozen with no fresher base to show.

Ajay: *"there should be more names, about 4k is what we discussed."* Both
studies now walk `full` ∪ `broad` (3,729 names in the container that day) via
one `study_universe()` helper; the 🌀 boards still draw from `full` (2,686), a
subset, and the tab blurbs say so. Both were re-run on the shipped detector;
§3 carries the numbers. Keltner hardened (−16.2pp on its break claim, the 21+
coil cell gone); AMD stayed inverted at −4.2pp instead of −8.9pp — the
difference is the 237,802 dead-base bars the old detector counted as raids.

Study hygiene from the same review: the AMD walk's phase table is exhaustive
against `amd.PHASES` (a test pins it — an unknown phase used to fold into "no
cycle" and land in every placebo); the walk also records the failure's age;
the subsets stage has a *live-base* placebo; the overlap stage uses the two
boards' own verdict grades instead of a hand re-implementation; and the study
constant `BARS_AGO_MAX = 10` is labelled as the study's bound, not the board's
(`MAX_RAID_BARS_AGO = 3` — the fresh 0–3 cells are the board).

---

## 7. The in-flight read before the open (2026-09-21)

Ajay, 09:05 ET, a screenshot of the 🌀 AMD Raided tab:

> These chips are not working

`🔄 Reclaimed today · 43`, `🛡️ Holding the edge · 0`. Three separate defects,
all visible in that one row of chips.

### D2 — a zero is not a low

Before the first regular-session print the Massive day aggregate is all zeros.
The row measured in-container that morning, ANAB at **09:30:09 ET**:

```
{"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "vwap": 0,
 "date": "2026-09-21", "change_pct": 1.449,
 "last_trade_price": 56, "last_trade_ts_ms": 1789997401449470877,
 "prev_day_close": 55.2}
```

`_f(0)` is `0.0`, not `None`, so `day_low < base_lo` was true for every name
that had a base: ANAB (base floor 53.41, print 55.35) read **reclaimed**, and
so did 42 others. `holding` read 0 for the same reason — nothing can be above
a floor of zero. Note the clock on that row: 09:30:09 is inside regular hours.
**The zero outlives the bell**, so nothing in this read may key on the time of
day.

### The other pre-session shape — the phantom echo

`prices._drop_phantom_tail` documents it (caught 2026-09-14 09:22 ET, when
every Hot Sectors member printed +0.1%): the feed echoes the **previous
session's completed aggregate** into a row stamped with today's date. That row
has a positive, real `low` — Friday's — and a value-only guard reads it as
today's and serves `reclaimed` / `holding` with full confidence.

### The rule that separates them

A **session low** exists only when the aggregate holds a positive low AND the
row's own print stamp says that low belongs to the session being read.
`prices.extended_print(snap)` is the only field that says which session a row
is from: the ET date and session of the **last trade**. Not `snap["date"]` —
that falls back to today-ET whenever `day.t` is absent, so on a Saturday it
stamps Friday's aggregate Saturday — and not the wall clock.

`_amd_flight(v, snap, *, low_session=...)`, with `low_session` from
`board._session_day()` (the shipped `market_hours.reminder` calendar, never a
second copy of it):

| the row | `extended_print` session / date | session low? |
|---|---|---|
| RTH, real low, print today | rth / today | yes |
| ANAB 09:30:09, low 0 | rth / today | **no** — the value |
| Monday 08:00, Friday's echo, pre-market print | premarket / today | **no** — the stamp |
| Monday 08:00, Friday's echo, no pre-market print yet | afterhours / Friday ≠ Monday | **no** — the date |
| Saturday, Friday's final aggregate | closed or afterhours / Friday == `low_session` Friday | yes — Friday's low, labelled Friday |
| Holiday Monday, Friday's aggregate | rth or afterhours / Friday == `low_session` Friday | yes |
| After-hours today, real low | afterhours / today | yes |
| a row with no stamped trade (the 09-17 fixtures) | `None` | by value only — unchanged |

Without a session low the state is **`unknown`** (`board.AMD_FLIGHT_UNKNOWN`)
and the block carries `reason = board.NO_SESSION_LOW_REASON`, `day_low: null`,
`pierce_pct: null`, `swept_today: null`, `low_session: null`, plus
`print_session` / `print_date` so the row can be read back. `above_edge` and
`to_edge_pct` are still served — the live print against the stored edge is a
fact that needs no low.

**`sweeping` never needed one.** The print is under the edge right now; it is
read from the print alone and it survives both the zero and the echo. That is
why 🔻 Sweeping stayed truthful on his screenshot while the other two lied.

`"unknown"` is deliberately **NOT** a member of `AMD_FLIGHT_STATES`: the chip
row and `parse_flight` both iterate that tuple, so it is never a chip and
never a selectable filter. `parse_flight("unknown")` is `None` (fails open).

### D3 — the count and the click are now the same population

The counts were built over the page (80 names) while a chip click searched the
whole sweep at `TB_FLIGHT_SCAN_LIMIT` — so the number changed the moment he
clicked it (43 → 14 tiles, chips → `{sweeping 14, reclaimed 207}`).
`TB.board` sorts and *then* slices, so asking for the sweep and cutting to
`limit` is byte-identically the page it always served. Every AMD request now
takes the whole grade set, counts over it, and cuts. One rule for the counts:

> each key counts the pool rows whose **served** `amd_flight.state` equals it;
> a row with no served block at all (no print, no base) is in **no** key.

so `sum(flight_counts.values()) == flight_scope.priced`, always. The served
`flight_scope` block says the rest:

```
counted        pool rows the live read covered (the grade set)
priced         rows that got a served block  (== the sum of flight_counts)
no_print       counted - priced
no_session_low rows served "unknown"          (== flight_counts.unknown)
low_session    the ISO session date the lows belong to, or null
unknowable     ["reclaimed","holding"] when no priced row has a session low
reason         NO_SESSION_LOW_REASON | "no live quotes came back" | null
reason_line    "44 of 46 priced names have …"  — built here, never in TSX
note           FLIGHT_COST_NOTE (the measured cost, below)
```

On his surface the two unknowable chips read `· —` and carry `reason_line` as
their hover line. They stay **clickable and dimmed**, the same rule a
zero-count grade chip already follows.

`low_session` is what makes a weekend read honest: on Saturday 2026-09-19 the
board serves `low_session: "2026-09-18"` and every tile's low is labelled
Friday, not "today".

### What the count costs — MEASURED, re-runnable

`backend/scripts/snapshot_cost_probe.py` (read-only; prints the dict that fills
`board.FLIGHT_COST_MEASURED`). Run in-container 2026-09-21 ~10:05 ET, tape
`rth`, with the keep-alive session of §D1:

| set | names | chunks | median of 3 |
|---|---|---|---|
| default grades | 422 | 2 | **0.651 s** |
| `grades=all` | 2,681 | 11 | **3.879 s** |

On the bare `requests.get` the same two were 1.715 s and 9.764 s. Re-run the
probe before quoting either number (memory `feedback_ship_the_backtest`).

### What did NOT change

The AMD detector, `find_cycle`, the grades and every threshold are untouched,
and the read is still **MEASURED INVERTED** against its placebo (−4.2pp,
2026-09-14, 3,712 names). Nothing here gates, alerts or enters. When a real
session low exists, all three states mean exactly what they meant on
2026-09-17.

### Open — HIS CALL

1. `matched` while a flight filter is on is still the grade-set size (422)
   while the board shows 14. Option: make it the filtered count so the footer
   reads "Showing 14 of 14".
2. A real pre-market low from 1-min aggregates (one call per name, 422–2,681
   per request) — **not built**; it is a new data path and a new semantic.
3. The ✅ Already reached / 🎯 Approaching buttons render on the AMD tab and do
   nothing (`board()` never passes `phase` to this builder). Out of scope here.
4. The unknown count reaches him through the `· —` chips' hover line. The
   alternative is a fourth non-clickable `❔ Unknown · 44` label on an already
   dense row (Rule #5).
