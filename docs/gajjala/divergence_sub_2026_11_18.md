# 🧨 Divergence sub on 🚩 Gajjala's 5-min tab + its 🏁 record — 2026-11-18

**A record, not a signal. No push, no gate, no trade. UNMEASURED live; in-sample the rule lost money.**

## His words (verbatim)

2026-11-18, two messages:

1. ~01:30 ET — "Do we still capture divergence alerts? Can you add a tab for in in Gajjals 5 min please"
2. ~02:00 ET, after being told the 11-16 study found no money in it, with four 🎬 replay screenshots (PAVS, GIPR, AMST,
   FRTT — each running well after the 9 EMA crossed above the 21 EMA):
   "yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish
   Cuz I am missing A+ i can chase the divergency atleast like in these cases
   I would caught a good chunk of returns"

His 11-16 words (study REPORT.md): "Is there a way to calculate the divergence percentage between 9 EMA and 21 EMA... I
feel like after EMA cross over when the divergence is wider gap is the best entry.." · "They don't have to be absolute but
some what relative" · "I mean I entere on reuglar or after hours not pre market" · "Then also look for volume I guess.."

## What shipped

| Piece | Where | What it does |
|---|---|---|
| 🧨 sub chip | `constants.SUBS` (after 🎾, index 6); `GG5_ONLY_SUBS` | 12 chips on the 5-min tab; the 1-minute and 🧪 strips never show it |
| Served block | `chart_maps/gajjala/divergence_tab.py` → `board.divergence` | title, his words, the rule, the honesty line, the in-sample lines, the OOS note, the cohort / window words, counts, order note |
| Cards | same module, `tiles` | one house card per record of the board's session: 9 / 21 EMA, the 🧨 bar, the cross marks, the exit mark, ENTRY line, three criteria rows (gap in ATRs, the bullish cross, volume), plan line, chips |
| 🏁 fold | `board.divergence.track_record` | every record on the span (today / yesterday / 5d / 10d / all), graded by the study's exit, net of costs, one count per stock per day (`ledger.dedupe_trades`) |
| Route | `tab.build` (sub branch, `resolve_sub` fail-open) | `GET /chart-maps/gajjala?sub=divergence[&span=…]` — no new route |
| ℹ️ Rules | `rules_info._gg_divergence_clause` | one row in the 🚩 section note, built from the constants |
| Record + grade | `chart_maps/gajjala/divergence.py` (the engine; WP-A) | the pass hook (Deps-gated) writes the live record; the 20:15 ET nightly re-detects the whole day and grades |

Three independent fences in the served block: the panel words are pure; every record's card is in its own try (a missing
read doc → a "chart not stored" line; a malformed tile or a raising card → the same line plus `faults_text`; never a tile,
always a 🏁 row); the 🏁 fold is in its own try (`track_record_fault_text`). Only the record read itself failing blanks
the sub ("🧨 The divergence record could not be read this time — the next re-read tries again.").

## The rule, in words (built from `GC.DIVERGENCE_*` on the page — never retyped)

Listed when a closed 5-minute bar between 09:35 and 15:55 ET (or 16:05–19:55 after hours; never pre-market) is the first
of the session with the 9 EMA at least 0.555 ATRs (14-bar ATR) over the 21 EMA, after the name rang a 🚩 A+ or 🧠 push on
this tab, and its last 3 bars' volume is rising with their mean at or above the 12 bars before. Entry = the next 5-minute
bar's open. Exit = the close of the first 5-minute bar whose 9 EMA crosses back under the 21, else the regular-close mark
(the 20:00 mark for an after-hours listing). Net % = gross minus 0.10% and $0.01 a share, each side — the study's costs.
One listing per stock per session. (The level constant is 0.5552257708108612, the study's q60; the page prints three
decimals.)

## In-sample prior (the study, `results.json` — served on the page)

| Window | Trades | Net per trade | 95% CI | Won | Median | Word |
|---|---|---|---|---|---|---|
| RTH (the registered pick) | 56 | −3.09% | [−6.73, +1.06] | 26.8% | −6.41% | NOT SHOWN |
| RTH vs listed names never rung | 35 | +3.28 | [−1.80, +8.90] | — | — | NOT SHOWN (p 0.2207) |
| After hours (description only) | 32 | −8.93% | [−15.60, −3.13] | 21.9% | −8.73% | LOST MONEY |

RTH exits 38 down-cross / 18 at the mark; 28 of 56 fills under $1.

## The OOS window — sealed totals

OOS_SPEC (sha `9da1ab8e…`) registered 2026-11-17 → 2026-11-30 (8 sessions; 11-26 closed, 11-27 half day dropped) before
any read. On this tab every listing's own grade cells show as they land, but **totals over rows dated on those sessions
are withheld until 2026-11-30 20:00 ET** (`GC.DIVERGENCE_OOS_SEAL_ET`): the counts line says "N OOS listing(s) not
totalled until 2026-11-30 20:00 ET" and `oos_progress_text` reads "OOS session k of 8 · sealed read after … — not this
tab". After the seal the rows count and `oos_counts_text` serves the OOS RTH line (one read over all eight sessions, not
the span). The ask day 11-16 is never sealed. This tab is NOT the registered read.

The counts line always prints net % beside the win rate ("… {pct}% won · net {±x.xx}% per trade (median …) …"); a half-day
row (11-27) is tagged "half day · outside the registered read" and kept out of the totals.

## Storage and the nightly (WP-A's engine)

`gajjala_divergence`, one doc per (session, SYM), kept (no TTL), GG5 only. The cron pass hook (`Deps.divergence`) writes
the live record; the existing 20:15 ET nightly (`nightly.main`, no crontab change) grades and re-detects the full day —
the full-day read is authoritative over the pass's bar (`live_alert` keeps the pass's). This module only reads.

## Goldens moved (2026-11-18, key-for-key, by recipe)

- BOARD `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json`: 13487 → 14351 leaves — 864 ADDED, 440 CHANGED, 0
  removed. Every one under `subs` (the 🧨 entry inserted at subs/6 on every board, count 0; the old subs/6..10 shift to
  7..11 = the 440 changed leaves) or the new `divergence` board per mode (its block = the empty shape, `tiles` []).
  Dropping `subs` and the new board, the files are identical (checked by script).
- WRITES `gg5_writes_2026_10_27.json`: byte-identical (sha1 7d857dc9…). 1-minute golden: byte-identical.
- FE fixtures, `subs` only (🧨 at index 6): on_open 2261 → 2276, potential 3884 → 3894, track_record 2877 → 2892.

## Not built

No push / keep-set kind, no gate, no Auto-Pilot use, no new route, no new crontab line, no backfill run (script exists;
running it = his call), no 13th 🏁 chip (the record is a fold under 🧨), no "cross today" listing requirement.

## HIS CALLs (nothing decided for him; the built default marked)

1. Cohort — BUILT: the study's units (today's 🚩 A+ shadow/live + 🧠 pushes with a plan, from the ring; yesterday's
   after-close ring from 04:00), GG5's store only. Two of his four screenshots (GIPR 💋 1-min A+, AMST 🎾 1-min potential)
   were 1-MINUTE page rings: this record would NOT have listed them. Alternatives: add the 1-min page's rings; or every
   listed 5-min name from its listing time (neither is the registered OOS cohort).
2. Costs — BUILT: the study's 0.10% + $0.01/share per side. The QUEUE.md 10/25 bps + 5 bps model needs a $-volume tier and
   breaks comparability with the −3.09 line.
3. One record per stock per session across RTH → AH (BUILT) vs a separate after-hours row.
4. Chip position after 🎾 (BUILT) vs elsewhere / a two-row phone strip.
5. "After a bullish 9/21 cross today" as a listing requirement: NOT built (a new gate); served as information (the cross
   time, or "already over the 21 EMA at 04:00 — no cross today"). In-sample 215 of 626 units were already over at the open;
   12 of the 56 alerts came after such a run.
6. Backfill 11-17 / 11-18 from the stored reads (script built, not run; reads TTL 14 d → before 12-01).
7. Half day 11-27 — BUILT: recorded, tagged, out of the totals; skip entirely = his.
8. After-hours exit — BUILT: the study's next-print open after the down-cross bar, else the 20:00 mark.
9. Live card words from the pass frames during the day (BUILT) vs nightly-only words.
10. GG5-only sub (BUILT).
11. No push, no keep-set kind (STANDING). A "🧨 listed" push = a 9th kind = his.
12. The 🏁 as a fold under 🧨 (BUILT) vs a 13th chip.
13. Entry = the next 5-min bar's open (BUILT; equals the OOS fill under a drop-empty resampler).
14. Three-session warm-up for prior-date-rung units (study) vs the house two-session frame (BUILT).
15. Records start the first session the hook runs.
16. The served IS line quotes the RTH pick AND the AH description; dropping the AH line = his.
17. OOS seal — BUILT: per-listing grades always show; totals over 11-17 → 11-30 rows withheld until 2026-11-30 20:00 ET.
    Showing running totals daily = his (it IS the registered read, taken eight times instead of once).
18. The nightly's full-day re-detect is authoritative over the pass's bar (BUILT); grading the bar he SAW on the card
    instead = his.

Tests: `backend/tests/test_gajjala_divergence_tab_2026_11_18.py` (served block, cards, fences, fold, seal, rules row,
NEGATIVES).
