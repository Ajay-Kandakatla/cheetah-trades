# Turning Bullish — KC Coiled and AMD Raided

**Both boards were measured against a placebo on 2026-09-13 and BOTH CAME BACK
INVERTED on their own claim.** Not null — inverted. Read §3 before §2.

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

2,660 names, **1,200,755 closed daily bars**, 2024-09-12 → 2026-09-11. Walked
bar by bar from index 41; every series recomputed vectorised and proved
prefix-stable against the real `keltner.channel()/squeeze()` at 12 checkpoints
(0 mismatches). CIs are **symbol-clustered** bootstraps — bars inside one name
are autocorrelated and 21-day windows overlap, so an iid bar bootstrap would
print intervals several times too tight.

Fire rate **5.39% of bars** (144 names on the last close, 142 after two stale
frames). 98% of names fire at least once in two years: recurring, not rare.

Forward close-to-close, coiled minus placebo (every non-firing bar of the same
names in the same window):

| Horizon | Coiled median | Placebo median | Lift | 95% CI |
|---|---|---|---|---|
| 5d | −0.08% | +0.12% | **−0.20pp** | −0.27 … −0.12 |
| 10d | +0.04% | +0.27% | **−0.23pp** | −0.33 … −0.10 |
| 21d | +0.14% | +0.47% | **−0.33pp** | −0.57 … −0.12 |

Win rate 49.0% vs 50.9% at 5d. **Every horizon negative, every CI clear of
zero.**

The **matched control** — same `position ≥ 0.5`, same rising EMA-20, squeeze
**off** (n = 376,498) — is what separates "the squeeze does something" from
"buying the upper half does something":

* coiled − matched: 5d −0.05pp [−0.12, +0.03] · 10d −0.00pp [−0.13, +0.15] ·
  21d +0.11pp [−0.17, +0.41]. **The squeeze contributes nothing.**
* The negative lift is entirely the "upper half + rising EMA" selection, which
  by itself underperforms (matched 21d median +0.02% vs placebo +0.47%).

**The claim itself, inverted.** Does a coiled bar precede a close above the
upper band within 21 sessions?

| Pool | Rate | 95% CI |
|---|---|---|
| Coiled | 40.04% | 38.95 … 41.14 |
| Non-coiled, all bars | 36.75% | 36.29 … 37.25 |
| **Matched control** | **55.04%** | 54.47 … 55.61 |

Against a random bar it looks like +3.41pp [+2.40, +4.49] — and that entire
gain is the `position ≥ 0.5` term. Against the honest control the coiled bar is
**14.83pp LESS likely** [−15.87, −13.72] to break its upper band. The module's
own sentence, measured: compression is compression, and it persists.

**The one positive cell.** Pre-registered split on coil length:

| Coil bars | n | 21d vs matched | 95% CI |
|---|---|---|---|
| 1–5 | 35,826 | −0.02pp | −0.25 … +0.28 |
| 6–10 | 14,266 | −0.02pp | −0.34 … +0.30 |
| 11–20 | 8,895 | +0.42pp | −0.07 … +0.81 |
| **21+** | **2,538** | **+1.34pp** | **+0.39 … +2.33** |

21+ bars beats the matched control at all three horizons with CIs clear of
zero. **This is why the board sorts longest-coil-first.** It is also 1 of 4
buckets, 471 names, disagreeing with the other three, and **four names** on
today's board (BCAL, BUR, MD, PIPR). Exploratory, not a rule.

### AMD (`turning_bullish_amd_study.py`)

2,666 names, **1,150,446 evaluated bars**, 441 sessions each after a 60-bar
warm-up. The real `amd.find_cycle` called on `df.iloc[:t+1]` at **every** bar —
no reimplementation, no sampling, no lookahead. CIs are the **wider** of
symbol-clustered and date-block-clustered bootstraps.

Fire rate **30.3% of all bars**; 1,201 of 2,621 names (45.8%) on the last close
at `bars_ago ≤ 10`. The cause is visible in the phase mix over 1.15M bars:
manipulation 60.1%, distribution 39.1%, accumulation 0.8%. The module almost
never says "accumulation", so the recency bound is the only thing cutting it.

Forward returns: **null leaning negative** — 5d lift −0.43% [−0.98, +0.05],
10d −0.53% [−1.53, +0.26], 21d −0.25% [−1.30, +0.72]. Every interval spans
zero; every mean lift is negative. Weaker than the ICT tab's +0.03R null: that
one was flat, this one leans down.

**The claim itself, inverted.** Does a fresh raid precede a close above that
bar's own base top within 21 sessions?

| Placebo | Signal | Placebo | Lift | 95% CI |
|---|---|---|---|---|
| Literal (all non-firing) | 42.7% | 63.97% | −21.2pp | −26.5 … −15.5 |
| "Edge still above price" | 42.7% | 35.4% | +7.3pp | +4.2 … +10.9 |
| **Like-for-like** (bar also inside its own base, distance-matched) | **42.7%** | **51.6%** | **−8.92pp** | **−11.42 … −5.91** |

The +7.3pp is **the number that would have shipped, and it is an artifact**:
that pool is stuffed with names that collapsed far below their base and never
climb back. By distance the signal *loses* in every near bucket (0–1% −1.1pp,
1–2% −1.1pp, 2–3.5% −2.8pp, 3.5–5% −4.2pp) and only "wins" at 8–15% (+6.8pp)
and >15% (+11.8pp) — entirely off broken placebo names.

The honest control is negative in **all seven** distance buckets and gets
monotonically worse: 0–1% −1.3pp → >15% −15.0pp. Three narrower placebo pools
(never distributed, stale raid, already distributing) are all still negative.
The module's own phase agrees: it reads "distribution" within 21 bars on 48.1%
of firing bars vs 65.7% of non-firing ones.

**Recency rescues nothing.** Fresh (0–3) vs stale (4–10): 5d −0.05%
[−0.54, +0.35], 10d −0.27% [−0.80, +0.30], 21d −0.36% [−1.16, +0.41]; fresh
leans *worse*. Against the matched placebo both are underwater (fresh −7.28pp,
stale −10.45pp). So `MAX_RAID_BARS_AGO = 3` is a **board-size cut, never an
accuracy gain**, and the source says so.

**Overlap.** On the same bar Keltner fires 146, AMD 1,210, both 51 — *below*
the 66.2 expected under independence. The two verdicts are not measuring the
same thing, and neither confirms the other.

### What the pages are allowed to say

Not allowed anywhere: "coiled to run", "markup next", "accumulation complete",
any bare reach rate without its placebo, any framing where a raid or a coil is
a reason to buy, and the +7.3pp "edge-still-above-price" number.

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
backend/tests/test_turning_bullish.py         24 tests
frontend/src/lib/chartMaps.ts                 CmCurve, curveLabels, CM_TABS, TAB_META
frontend/src/lib/chartOverlays.ts             tabFamily, hiddenForTab, curve+badge gating
frontend/src/components/PatternChart.tsx      polyline rendering with gaps
frontend/src/components/OverlayLegend.tsx     locked family
frontend/src/lib/turningBullish.test.ts
```
