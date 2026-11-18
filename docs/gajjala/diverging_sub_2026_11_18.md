# 🌱 Diverging sub on 🚩 Gajjala's 5-min tab — 2026-11-18

A forming read, served only. **UNMEASURED.** No push, no gate, no record, no trade, no fetch.

## His words (verbatim)

Ajay 2026-11-18 ~11:50 ET: "For the divergence thing create a separate tab that are potentially diverging with uptrend
and volume breakout." Then: "Are you building that now?"

His two picks (the option text, verbatim, is the rule):

1. **"Fresh cross, gap widening"**: "The 9 EMA crossed above the 21 EMA and the gap between them has widened for 2+
   bars in a row, but is not yet wide enough to make the 🧨 Divergence record." (Question frame: 5-min bars, uptrend
   = price above a rising 21 EMA.)
2. **"GG's day floor + bar spike"**: "The name has traded GG's daily volume floor (the same one his pushes use), and the
   latest 5-min bar's volume is at least 2× its last 20 bars' average."

## What shipped (backend, WP-A)

| Piece | Where |
|---|---|
| 13th sub `("diverging", "🌱", "Diverging")` right after 🧨, GG5 only (`GG5_ONLY_SUBS`) | `backend/chart_maps/gajjala/constants.py` |
| Three constants (his picks) + one of mine: `DIVERGING_WIDEN_BARS = 2`, `DIVERGING_BAR_VOL_MULT = 2.0`, `DIVERGING_BAR_VOL_LOOKBACK = 20`, `DIVERGING_EMA21_RISE_BARS = 1` (MINE, HIS CALL #4) | constants.py |
| The read, the block, the card | `backend/chart_maps/gajjala/diverging_tab.py` (new) |
| Wiring: `resolve_sub` fails open off GG5 for every GG5-only sub; ONE `DGT.evaluate` per build (chip + block); the sub branch | `backend/chart_maps/gajjala/tab.py` |
| ℹ️ rules row `_gg_diverging_clause()` | `backend/supply_demand/rules_info.py` |
| Tests | `backend/tests/test_gajjala_diverging_2026_11_18.py` (53) |

The read runs on the GET over the stored `gajjala_reads` docs the tab already holds. It goes through the 🧨 engine
(`divergence.from_tile`, `atr_series`, `r1_series`, `eligible`, `up_cross_before`, `_on`) and uses
`divergence_tab.window_text` / `WINDOW_WORDS` for the window words. It has no EMA, cross, ATR, gap or window code of its
own.

## The rule, in words (built from the constants on the page — never retyped)

A name lists when its latest closed 5-minute bar meets every condition below:

- It closes in the 🧨 windows: RTH 09:35–15:55 ET, after hours 16:05–19:55 (`DIVERGENCE_WINDOWS`). Pre-market bars never list.
- 9 EMA > 21 EMA, the close is above the 21 EMA, and the 21 EMA is above its value 1 closed bar earlier.
- A bullish 9/21 cross happened today (on the session from 04:00 ET, `up_cross_before`). A name that has been over the 21 since yesterday never lists.
- The 9−21 gap, in 14-bar ATRs (`DIVERGENCE_ATR_PERIOD`), got strictly wider on each of the last 2 closed bars.
- That gap stayed under the 🧨 cut (`DIVERGENCE_R1_LEVEL`) on **every** bar since this cross. If it reached the cut once, the name is 🧨's by rule. A new up cross starts a fresh count. A bar whose ATR is unknown cannot be judged and is skipped.
- The bar's volume is at least 2.0× the mean of the 20 bars before it.
- Today's volume is at least GG's 1,000,000-share floor (`K11_MIN_SESSION_VOLUME`, the floor his pushes use). An unknown volume fails.
- The tile has at least `DIVERGENCE_MIN_BARS` bars, counting the prior tail (inherited from `eligible`).

Card order: today's volume first, then the wider gap, then the symbol. This is display only (HIS CALL #6).

The card shows only the 9/21 cross marks. It has no buy marker, no ENTRY line and no plan. It carries 5 criteria rows: gap (with the "peak since the cross" figure), widening (with the path), uptrend (with the cross time), bar volume (with the pre-market count) and the K11 row, served exactly as `detectors.k11_criterion` returns it.

## Open bias of pick (2)

Probe: 2026-11-18 12:15 ET, 73 stored reads, read-only, origin/main container. It counted names whose bar volume was
≥ 2× the prior 20 bars:

| Bar | Names ≥ 2× |
|---|---|
| 09:35 | 59 / 69 |
| 09:40 | 48 / 69 |
| 10:00 | 19 / 70 |
| 11:00 | 4 / 71 |

**Why:** at 09:35 the 20-bar mean is made of 20 pre-market bars, so most names clear 2× on the first RTH bars. This is
his verbatim pick, not a defect. The surface says so in two places:

- The honesty sentence: "Early in the session the 20-bar volume mean is mostly pre-market bars, so most names clear
  2.0× on the first bars — each card says how many of its mean bars closed before 09:35 ET."
- A per-card fact on the bar-volume row: "N of the 20 bars in the mean closed before 09:35 ET (pre-market or the prior
  session)". It is printed only when N > 0.

No served sentence types a clock or names an hour.

Re-runnable script: `/Users/ajay/clinet-test/eod-audits/research/2026-11-18_diverging_open_bias_probe.py`. The main
session copies it there (WP-M); it lives outside the repo. That run predates the since-the-cross clause, and the §5.3
re-run adds its own table beside this one. The fix "lookback on RTH bars only" is HIS CALL #16.

## One pass, two bars

At 12:15, 5 of the 73 stored tiles sat one bar behind (12:10 vs 12:15), from a slow pass or a skipped re-read. Each
name is read on its OWN latest stored bar, so the chip counts what is true "now" per name. When the last stamps differ,
the block serves `bars_text` ("Latest stored bar HH:MM ET · n of N name(s) last read on an earlier bar — each card
names its bar"); it is null when they are all the same. Every card's state label names its bar. A GET never fetches to
line them up. HIS CALL #18.

## Runtime

Critique probe, 12:15 ET: `from_tile` took 20 ms and the evaluation 11 ms over 73 reads, with 4 ATR calls of about
1.1 ms each. The cheap checks (session floor → bar spike → uptrend → cross) run before the pandas ATR. Because of the
open bias, the ATR count is highest on the first bars: about 59 of 69 at 09:35, roughly 65 ms worst case. The §5.3
re-run's numbers replace these before deploy.

## Fresh cross has no age

A 04:05 pre-market cross still reads "fresh" at 15:55 if the gap only now widens under the cut. Every card's uptrend
row prints the cross time. A max age would be a new threshold (his number). HIS CALL #19.

## Half days

`DIVERGENCE_WINDOWS` RTH 09:35–15:55 is a stamp range. On a half day (11-27) the 13:05–15:55 bars read as "rth". This
is inherited from 🧨 and shows only as the window word here.

## Phone

13 chips. The strip scrolls sideways, as it does today. A two-row strip is HIS CALL #2.

## Not built

No push or keep-set kind, no gate, no record or 🏁, no pass hook, no nightly, no new route, no fetch, no crontab line,
no Auto-Pilot use. No buy marker, ENTRY line or plan on the card. No measured number of worth anywhere: the open-bias
counts above describe runtime and shape, not the read's worth.

## Goldens moved (2026-11-18, by recipe, key-for-key)

**BOARD** (`backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json`, regenerated with
`GG_WRITE_GOLDEN=1 … -k test_gg5_board_is_byte_identical`):

- 584 leaves added: 464 are each mode's new `diverging` board (count 0 on the fixture day; `bars_text` served because
  the two stored tiles end on different bars) and 120 are the 🌱 chip in every other board's `subs`.
- 480 leaves changed: the `subs` entries from index 7 on shift one slot.
- 0 removed.

With every `subs` and every `<mode>/diverging` dropped, the old and new files are identical.

**WRITES** (`gg5_writes_2026_10_27.json`): byte-identical, sha1 `7d857dc9…`, no regen.

**FE goldens** (`gajjala_on_open_golden_2026_10_15.json`, `gajjala_potential_golden_2026_10_15.json`,
`gajjala_track_record_golden_2026_10_16.json`, each regenerated by its backend `-k golden` recipe): only `subs` moved
(15 / 10 / 15 leaves added; 60 / 44 / 57 changed; 0 removed). With `subs` dropped, each file is identical.

## Tests

`backend/tests/test_gajjala_diverging_2026_11_18.py` (53 tests), grouped as:

- **Positive** (canonical, after hours)
- **Every single-flip negative:** cut exactly (partition proof via `first_crossing`), over the cut, over the cut earlier
  since the cross, the per-cross twin, an unknown-ATR bar skipped, widened 1 bar, a tie, the 21 EMA flat or falling,
  close under the 21, 9 under 21, no cross today, the session floor (−1, None, "1e6", NaN, True, exact), 1.99× / 2.0×,
  a zero mean, 19 prior bars, `DIVERGENCE_MIN_BARS − 1` with `prior_tail=0` (asserts `eligible` is the reason) plus its
  twin, bars at 09:30 / 08:00 / 16:00 / 20:00, a stale tile, ragged input
- **Open bias:** `pre_bars` 20 / 15 / 0, honesty with no clock
- **Words:** constants-only numbers, the numbers move with the constants, `not hasattr(DGT, "WINDOW_TEXT")`,
  `window_text` identity
- **One pass, two bars**
- **Board:** chip `subs[7]`, card shape, other subs, GG1 / GGA fail open, volume order, no b-word
- **Faults:** evaluation fault, malformed tile, raising card
- **`rules_info`**

Pins widened (each marked `WIDENED 2026-11-18 — 🌱`):

- `test_gajjala_constants.py`: the SUBS order and the contracts-regex count, 12 → 13
- `test_gajjala_counts_legend_2026_10_18.py`: 12 → 13 and 11 → 12
- `test_gajjala_variant_gg5_identity.py`: 12 → 13
- `test_gajjala_divergence_tab_2026_11_18.py`: 12 → 13; GG1 `len(SUBS) − 1` → `− 2`; the 🧨 rules NEGATIVE now reads
  the 🧨 clause's head, because the 🌱 clause names "the 🧨 cut"
- `test_gajjala_divergence_2026_11_18.py`: the GG5_ONLY_SUBS three-tuple

## HIS CALLs (nothing decided for him; the built default marked)

1. Label / emoji: BUILT `🌱 Diverging`. Alternatives: `🌿 Widening`, `🧨➕ Pre-divergence`, `🔀 Fresh cross`, or his own word.
2. Chip position: BUILT right after 🧨 (13 chips; the phone strip scrolls sideways). Alternatives: before 🧨; a two-row strip.
3. "Widened for 2+ bars": BUILT strictly wider on each of the last 2 closed bars with the 9 over the 21 on all three bars (the cross bar itself is not a widening bar; a tie is not wider). Alternative: count the cross bar (signed gap from negative to positive) as the first widening bar.
4. "Rising 21 EMA": BUILT = above its value on the previous closed bar (`DIVERGING_EMA21_RISE_BARS = 1`, MINE). Alternative: above its value `K5_SLOPE_BARS` (3) bars earlier — his K5 lookback.
5. "Fresh cross": BUILT = a 9-over-21 up cross on today's session from 04:00 (pre-market crosses count; a name over the 21 since yesterday never lists). Alternatives: RTH/AH crosses only; or no cross-today requirement.
6. Card order: BUILT today's volume DESC (his 2026-11-09 word for every Gajjala card), then the wider gap. Alternative: widest gap (closest to the 🧨 cut) first; or loudest bar first.
7. No ENTRY line, no plan, no buy marker on the card (a forming read): BUILT. Alternative: a plan line like the setup subs (would need a trigger/stop rule = a new rule).
8. "Price above the 21 EMA": BUILT = the latest bar's CLOSE above it. Alternative: the bar's LOW above it.
9. No record / 🏁 for this read: BUILT (a record = a new engine; the ask said NOT this round). When he wants it: the 🧨 engine's shape (pass hook + nightly grade) with its own exit rule = his.
10. Cohort: BUILT = every stored read of the pass (the whole 🚩 list). Alternative: today's rung names only (the 🧨 cohort).
11. Pre-market bars never list (the 🧨 windows reused): BUILT. Alternative: list on pre-market bars too (a new window).
12. After-hours bars list (16:05–19:55) with the window word: BUILT. Alternative: RTH only.
13. "Fewer than 20 prior bars" / "fewer than 30 bars" = not listed, silently (no per-name reason served): BUILT. Alternative: a served "not enough bars yet" line per name.
14. A push for a 🌱 listing: NOT built, STANDING (a 9th OWNER_KEEP_SET kind = his word).
15. The chained GG5-only strip filter in GajjalaBoard (keeps the contracts pin) vs folding it into one filter + re-pinning (main session's choice).
16. The 20-bar volume mean at the open: BUILT = his verbatim pick (2), the last 20 stored bars whatever session they belong to (so at 09:35 the mean is pre-market volume and most names clear 2× — 59/69 on 11-18; the surface says so and each card counts its pre-market bars). Alternative: the mean over on-session RTH bars only (needs 20 RTH bars → the first possible listing is the 11:15 bar; nothing lists in the first 100 minutes) — a rewrite of his option text, so his word.
17. "Not yet wide enough to make the 🧨 record": BUILT = under `DIVERGENCE_R1_LEVEL` on EVERY on-session bar since this up cross (a name that touched the cut at 10:30 and fell back is 🧨's for that cross; a new up cross starts over; a bar with an unknown ATR cannot be judged and is skipped). Alternative: the latest bar only (lists a name that was 🧨's earlier today).
18. When tiles sit on different last bars (a slow pass): BUILT = each name read on its own latest stored bar, one served line "Latest stored bar HH:MM ET · n of N name(s) last read on an earlier bar" only when it happens, every card names its bar. Alternatives: silent (no line); or hide the names a bar behind (fewer listings, a gate).
19. "Fresh" has no max age: BUILT = any up cross on the session from 04:00 (a 04:05 cross still "fresh" at 15:55 if the gap only now widens under the cut; the card prints the cross time). Alternative: a max age in bars (his number — no Cheetah constant exists for it; it would be a NEW threshold).
