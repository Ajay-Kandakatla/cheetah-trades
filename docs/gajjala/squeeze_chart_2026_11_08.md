# 🎾 GG's marks on the Reversal Squeeze chart — 2026-11-08

**The ask (Ajay, 2026-11-08, verbatim, with GG's own annotated TPST 5-minute chart attached):** "I need something like
this but that big of circle for reversal squeen mainly on the cart itself also increase the width of the reversal
sqeeze chart to show more bars" / "This is from Gajjals". Clarified the same morning: "They don't have to be circles
but indicators did you build them already?"

**What ships:** every 🎾 Reversal Squeeze card (🚩 Gajjala's, the 1-minute page, 🧪 Audited — the shared tile builder)
(1) spans the whole grid row, (2) on the 5-minute tabs draws the PRIOR session from 15:00 ET through its after-hours
ahead of today's bars, and (3) carries served marks on the chart itself around what the detector already found, in
GG's colours and his words. Display only. Nothing here lists, gates, pushes or trades; every K rule, state, trigger,
stop and push is byte-identical (the goldens' delta below). **UNMEASURED.**

## 1. Structure stamps on the stored read — `detectors.reversal_squeeze`
`setups.reversal_squeeze.structure = {tennis, run, base, attempts}`, each a box `{from_t, to_t, lo, hi, bars}` built by
`_box` from the indices the detector already had (drop bar d → recovery bar k; the squeeze-back run d+1..p; the quiet
base p+1..j−1; the PAIRED earlier attempts a..f, contiguous spans merged by `_merge_spans`). `_paired` is now
`bool(_pairs(...))` — identity pinned under both `K8_FAIL_EVENT_RULE` values. Present on aplus / triggered / stopped /
forming / partial / invalid reads that found a tennis ball (invalid is never carded); absent on `none` and float-gated
reads. No rule reads it (source guard).

## 2. The prior-session tail — `bars.tile_prior_payload`, `run.py`, `constants.py`
| constant | value | provenance |
|---|---|---|
| `RS_TILE_PRIOR_FROM_ET` | 15:00 ET | Cheetah default (MINE) — the first bar of his TPST chart (HIS CALL #3) |
| `RS_TILE_PRIOR_TO_ET` | 20:00 ET | MINE — = `daytrading.data.ET_AFTERHOURS_CLOSE` (test pins equality) |
| `RS_TILE_PRIOR_BARS_MAX` | 60 | derived: (20 − 15) h × 60 ÷ 5-minute bars |
| `RS_TILE_TODAY_BARS_MAX` | 192 | derived: one 16-hour session in 5-minute bars (= the 1-minute page's cap expression) |
| `RS_TILE_BARS_MAX` | 252 | derived: the most bars a 🎾 card ever serves |

The GG5 pass stores `tile.bars5_prior / curves5_prior / vol_avg5_prior` for EVERY name (one rule, ~5 KB/name/day —
HIS CALL #11); `bars5` itself is byte-identical. Measured cost of `tile_prior_payload`: 0.57 ms per call on the
test_gajjala_run frames, 2.68 ms on a full 04:00→20:00 prior day (~0.1–0.5 s per pass at ~170 names). `run_1m.py` is
untouched: the 1-minute page's 🎾 card keeps its 1-minute bars, 192 cap, no prior tail (HIS CALL #4).

## 3. Served marks — `squeeze_marks.ellipses`, `tab.setup_tile`
Items `{kind, from_t, to_t, lo, hi, label, note, tone}` served under `ellipses` on 🎾 cards only, in the order
ah · attempt · tennis · run · base · entry. A mark is served only when BOTH its stamps are served bars (`_on_bars`'
rule), and only when the drawn frame is the read's frame (the 15-minute toggle and the 1-minute page's 5-minute toggle
serve `[]`). The AH mark covers the prior-day after-hours bars whose high clears the K9 carry line
(`scanner._at_least`, `K9_AH_CARRY_PCT` — the predicate that put the name in the carry; no new number); if none does, the
whole after-hours stretch. The entry mark rides the A+ marker's own rule: it exists iff the "A+" / "A+ (original)" marker
exists (aplus / triggered / stopped, 🧪 held) — never on a partial read that broke.

| kind | chart label | hover (GG's words) | tone |
|---|---|---|---|
| ah | AH spike | GG: "AH - Price spike with good volume" | structure (magenta) |
| attempt | earlier try | GG: "it has tried to squeeze in earlier bars and been sold" (S9 2:01:42) | structure |
| tennis | tennis ball | GG: "Tennis ball action, quick dump and reclaim" | structure |
| run | demand | GG: "Demand picks up" | structure |
| base | quiet base | GG S8 36:12: "the pullback is very gradual, all at the top of this bar with gradual decrease in volume" | structure |
| entry | entry | GG: "ENTRY OPPORTUNITY" (his chart's label, quoted) | entry (house green) |

NOT built: "PM - Held its AH price level" (needs a hold rule = a threshold, Rule #1 — HIS CALL #2) and the red "CLOSE OR
ADD OPPORTUNITY" (his exits are discretionary, verified_rules E3/E5; Ajay 2026-11-06 "keep it" — HIS CALL #1).

## 4. The chart primitive — `lib/ggEllipses.ts`, `PatternChart.tsx`
`CmEllipse` on `CmTile.ellipses?`. One layer `g.pc-gg-ellipses`, drawn after the candles and before the leaders and
gutter labels, clipped to the price pane. Geometry from the served stamps: x from `stampIndex` (full stamp first, then
the date-only join) ± `ELLIPSE_PAD_X_BARS` 0.6 bars, y from lo/hi ± `ELLIPSE_PAD_Y` 3 px, `ELLIPSE_MIN_R` 5 px, label
`ELLIPSE_LABEL_FS` 8 px clamped into the plot — drawing constants, MINE, not market numbers. Stroke by tone: magenta
`#e879f9` structure (GG's colour), the house green for entry; no red tone exists. The `<title>` on each mark's group is
the served note. Refix 2026-11-08: the layer carries NO `pointer-events: none` — with it every `<title>` was unreachable
and GG's words never showed; a mouse move still reaches the svg's hover readout and a click still opens the card link.
Where a mark overlaps a band the mark's tooltip wins (owner's call).

**`markerIndex` fix (HIS CALL #13):** the served A+ tag stamps a full bar timestamp; `markerIndex` joined on the date
only, so the tag never drew on an intraday card. It now matches the full stamp first, then the date — the A+ tag draws
for the first time on 🚩, the 1-minute page, 🧪 Audited AND 🥇 Luk's cards (`luk/tab.py:387` serves the same shape).
Daily cards unchanged (pinned).

## 5. The wide card — `GajjalaBoard.tsx`, `gajjala.css`
`gg-card gg-wide` when `t.gajjala?.setup === 'reversal_squeeze'` (🎾 sub and a 🧠 card of a 🎾 read); `.gg-card.gg-wide
{ grid-column: 1 / -1; }` AFTER the pinned `.gg-card` rule — full row at every column count. Never `span 2`: on the
one-column auto-fill grid between 641 and ~860 px it forces a second column and the card overflows. At ≤ 640 px `.cm-grid`
is one column, so the phone card is the width it was; the 620×190 viewBox simply renders larger on a wide card.

## 6. Goldens (regenerated by recipe 2026-11-08, delta proved path by path, copies in the session scratchpad)
- `gg5_writes_2026_10_27.json`: ADDED 18 keys — `tile.bars5_prior / curves5_prior / vol_avg5_prior` on each of the 6 read
  docs; nothing changed, nothing removed. No `structure` key appears: the 2026-10-27 fixture's 🎾 reads found no tennis
  ball (the new structure tests pin it on their own fixture).
- `gg5_board_2026_10_27.json`: byte-identical (the fixture carries no 🎾 tile).
- `gajjala_potential_golden_2026_10_15.json` (FE): `/boards/potential/tiles[1]/ellipses: []` only.
- `gajjala_1m_board_2026_10_27.json`, `gajjala_on_open_golden_2026_10_15.json`: unchanged (their tests pass untouched).

## 7. Tests
BE `test_gajjala_squeeze_structure_2026_11_08.py` (40), `test_gajjala_squeeze_prior_tail_2026_11_08.py` (15),
`test_gajjala_squeeze_marks_2026_11_08.py` (49) — negatives: no structure without a tennis ball / float-gated / other
setups; the literal guard; no rule reads `structure` or `_prior`; the 1-minute pass stores no prior tail; the window
never reaches today; a 15-minute frame serves `[]`; a stamp off the drawn window draws nothing; no mark on non-🎾 tiles;
no red tone. FE `ggEllipses.test.ts` (23), `PatternChart.ggEllipses.test.tsx` (17 + the hover describe),
`GajjalaBoard.squeeze_wide.test.tsx` (10), `GajjalaBoard.phone.test.tsx` (+7: the base rule unchanged, `1 / -1` never
`span 2`, the ≤ 640 px one-column rule stays).

## 8. HIS CALLs (defaults built as stated; never decided here)
1. RED "CLOSE OR ADD OPPORTUNITY" mark — NOT built (discretionary exit; his 11-06 "keep it").
2. "PM - Held its AH price level" — NOT built (a hold threshold would be a new number).
3. Prior-tail window starts at the prior session's 15:00 ET (his chart's first bar); alternatives 16:00 or the whole prior session.
4. The 1-minute page's 🎾 card keeps 1-minute bars, 192 cap, no prior tail.
5. Full-width card on every 🎾 card incl. the 🧠 sub; viewBox kept (renders larger); chart height is his.
6. Attempts drawn = the detector's own PAIRED attempts, merged; alternatives nearest-only or all (ZNB had 21 on 11-06).
7. Entry mark rides the A+ marker rule, never a partial broke read.
8. Colours / words: GG magenta #e879f9 structure, house green entry; labels "AH spike · earlier try · tennis ball · demand · quiet base · entry" with his quotes on hover — wording his.
9. No card legend line (the chart label + hover carry the words).
10. Price scale fits every served bar (a prior-AH spike flattens today's candles, as on his chart); alternative: scale on today only.
11. Prior tail stored for EVERY name (~5 KB/name/day); alternative only alive 🎾 names.
12. The 15 pre-existing host-venv red tests — untouched.
13. The `markerIndex` full-stamp fix ships here and makes the A+ tag draw on all four card surfaces incl. 🥇 Luk's; alternatives: separate fix, leave it, keep it off Luk.
14. The AH mark spans the after-hours bars clearing the K9 carry line, whole-stretch fallback.
15. Phone (≤ 640 px): same card width, up to 252 bars (~1.6 px per bar at 430 px, labels unreadable) — default draws what is served; alternatives FE-slice the prior bars on the phone, or a taller phone chart.

## 9. Verification
Suites on the worktree: backend 0 new failures (the 15 pre-existing host-venv reds identical on HEAD; `.env` absent in a
worktree fails the two env tests there only), frontend 6608 pass, tsc clean, contracts 172. Live: the first 🎾 card with
marks and the prior tail appears on the first GG5 pass that writes `structure` and `bars5_prior` (Monday 2026-11-09
04:01 ET); Friday's stored reads carry neither, so tonight the wide card and the SI label show and `ellipses` serves `[]`.
