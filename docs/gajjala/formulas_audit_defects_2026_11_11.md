# Formulas audit defects D1–D13 — the fixes (2026-11-11)

## His words (verbatim)

Ajay 2026-11-11 08:18 ET: **"Can you fix the defects please"**

"The defects" = section 3 of the formulas audit, `eod-audits/research/2026-11-10_formulas_audit.md` (13 confirmed
defects, D1–D13; outside the repo). The audit's own lead: the fixes for the section-3 defects need his word — this is it.
Scope = D1–D13 only: no drift (W1–W14 / S1–S9), no Q item, no threshold, no K-number, no constant changed.

## Two ship sets

- **Ship-now (FIXED 2026-11-11): D3, D9, D10, D12, D13.** None of them changes which A+ rings: D3 is a 🌙 list / ☀️ carry
  clock, D9 a grade word on a read that is never carded or pushed, D10 words only, D12 a Kell list row, D13 a replay
  only. Each is its own commit. D3 ships no later than **2026-11-25** (the next half day is 2026-11-27).
- **Count-gated (BUILT LATER): D1, D2, D4, D5, D6, D7, D8, D11.** These change WHO qualifies (an A+ can be added or
  removed, a SEPA score or a Kell row moves). They are not in this change. Each ships only after the before/after count
  (a replay after 16:00 ET, never in market hours) is in front of him — **NOT MEASURED yet**.

## D1–D13, before → after

| # | Defect (audit §3) | Before | After | Status |
|---|---|---|---|---|
| D1 | 🌀 K7 "cycle low" has two definitions | a completed cycle's low = the lowest confirmed PIVOT low; the last cycle's = the lowest BAR (demo: an A+ with a true low 1.5% under the 21 EMA; a real 0.40x contraction read "B, missed ratio"; two contractions read "1 of 2") | — (planned: every cycle's low = the lowest BAR between its high and the next cycle high) | BUILT LATER · count-gated · NOT MEASURED |
| D2 | 🎾 K8 running high moves before the drop test | a bar that makes a new high AND drops 8% finds no tennis ball | — (planned: test the bar against the running high as it stood before it, then move the high) | BUILT LATER · count-gated · NOT MEASURED |
| D3 | 🌙 K10 clock ignores half days | fixed 15:59 / 16:01 / 20:00 clock; demo 2026-11-27: close_pos 0.40 (house calendar: 0.90), after-hours volume 148,117 (600,000); 13:05 / 15:30 read "rth" | the clock comes from the house calendar (`alerts._closes`): 15:59 / 16:01–19:59 on a normal day, 12:59 / 13:01–16:59 on a half day; the tape session reads 13:00–17:05 as after-hours and 17:06 on as "closed" on a half day; a normal day reads exactly as before, minute by minute | **FIXED 2026-11-11** |
| D4 | K1 body exactly +3.00% fails | 15.00 → 15.45 fails (float) | — (planned: one rounding-safe compare, `ledger._D`) | BUILT LATER · count-gated · NOT MEASURED |
| D5 | K3 pullback low exactly at half-way fails | 148 of 1,296 cent-grid cases read invalid | — (planned: the same compare) | BUILT LATER · count-gated · NOT MEASURED |
| D6 | K1 range exactly 1.5x the average fails | an exact 1.5x range fails | — (planned: the same compare) | BUILT LATER · count-gated · NOT MEASURED |
| D7 | SEPA 16:30 fast scan gives the textbook-VCP +2 without the volume test | +2 on the fast scan, none on the full scan for the same stock | — (planned: one helper for both scans) | BUILT LATER · count-gated · NOT MEASURED |
| D8 | Kell: a failed longest base falls through to a shorter one | close under the 15-bar base high → listed on a 12-bar base | — (planned: the longest valid base decides) | BUILT LATER · count-gated · NOT MEASURED |
| D9 | 🌀 B grade decided before "waiting for cycle 2" | a 1-cycle read with its low under the 21 EMA read `invalid`, then `B — imperfect` once cycle 2 printed (same bars, two answers) | "waiting" (no break yet, fewer than `K4_VCP_MIN_CYCLES` cycles) is decided BEFORE the grade: that read now reads what it reads once cycle 2 prints (`partial · B — imperfect`, missed K7 21-EMA only); a BROKEN 1-cycle read stays `invalid`; never carded, never pushed | **FIXED 2026-11-11** |
| D10 | K11 refusal not remembered — the card claims an A+ | 900,000 shares at the break: no alert; next pass 1,050,000: "triggered 1 bar ago — A+ on the 10:20 bar", 🌙 recap "A+ (triggered)" | on 🚩 Gajjala's and the 1-minute page (live pushes), when the 🏁's own read of the rang alerts holds no A+ for that stock and setup that day: "triggered 1 bar ago — broke on the 10:20 bar, no alert rang · UNMEASURED", recap "broke (no alert rang)" / "broke, then stopped (no alert rang)", 🧠 track "broke (no alert rang)"; an alert that rang, a read fault, or 🧪 Audited → today's words | **FIXED 2026-11-11** |
| D11 | Scanner lines tested in float math | a name exactly on +25% / +10% / +5% lists one pass later | — (planned: the same rounding-safe compare; one `_at_least`) | BUILT LATER · count-gated · NOT MEASURED |
| D12 | Kell: a missing volume passes the dry test | one NaN volume made the 50-bar average NaN; every NaN compare is False, so a full-volume base was LISTED | missing = not dry (fail closed): `_detect` returns None when the 50-bar average or the breakout volume multiple is not finite; it can only remove a name, never add one | **FIXED 2026-11-11** |
| D13 | Replay only: the 1-minute frame not cut at `--now` | a `--now` replay read later minutes into ☀️ / 🌙 (demo: a 16:10 replay listed RPLY on 600,000 after-hours shares) | `run._upto` cuts the frame at the pass clock in the three 1-minute reads of `run.py` — ONLY on a replay (`--now` given; cut at 16:10 the demo reads 22,594); a live pass is never cut and is byte-identical | **FIXED 2026-11-11** |

Where each fix lives (ship-now):
- D3 — `chart_maps/gajjala/context.py` `_post_clock(session)` (the 🌙 minute clock; stored key `close_1559` kept = the
  last regular minute's close, 12:59 on a half day) and `scanner.pass_tape_session` (the grace = `PASS_CLOSE_ET` −
  `ET_AFTERHOURS_CLOSE`, derived, never typed). Doc `docs/gajjala/context_reads_2026_10_13.md`. Tests
  `backend/tests/test_gajjala_defects_clock_lines_2026_11_11.py`.
- D9 — `chart_maps/gajjala/detectors.py` `_vcp_leg`. Doc `docs/gajjala/detectors_2026_10_13.md`. Tests
  `backend/tests/test_gajjala_defects_detectors_2026_11_11.py`.
- D10 — `chart_maps/gajjala/tab.py` (`NO_RING_TEXT`, `NO_RING_RECAP`, ONE alert-row read per build). Same words for every
  reader. Doc `docs/gajjala/card_labels_2026_11_08.md`. Tests `backend/tests/test_gajjala_defects_k11_words_2026_11_11.py`.
- D12 — `kell/base_n_break.py`. Doc `docs/KELL_CONTRACTS.md`. Tests `backend/tests/test_kell_base_n_break_defects_2026_11_11.py`.
- D13 — `chart_maps/gajjala/run.py` `_upto` (cut = `now` only when `--now` was given). Tests
  `backend/tests/test_gajjala_defects_replay_cut_2026_11_11.py`.

## The count (NOT MEASURED yet)

Runs after 16:00 ET in a throwaway container (never the live api, never `--write`), on the sessions the replay accepts:
`before` (origin/main) → `shipnow` (+ D3, D9, D10, D12, D13: **zero** kept-A+ rows may move, else stop) → each
count-gated step. Rows he will see, each COUNTED or NOT MEASURED: 5-minute A+ added / removed / moved by name; 🧠
potentials as reads (the 🧠 push gate is not replayed); the 1-minute page's A+ and 🧠 pushes — **NOT MEASURED** (the
replay is 5-minute only); D11 only if the study path reaches `scanner._at_least`; SEPA fast-scan rows losing 2 and the
juggernaut watchlist names that would drop (adds later not counted); Kell names dropped. Counts of rings only — never a
win rate. Nothing in this table yet.

## NOT fixed (on purpose)

- **The same float pattern elsewhere** (scope lock, not D1–D13): K7 ratio and K7 21-EMA compares, the K8 drop / recover
  levels, the K6 tolerances, the K3 volume cap, ENTRY `hi > trigger`, STOP `l < stop`, the ☀️ K9 premarket volume line.
- **Other fixed 16:00 / 20:00 clocks** (display / ledger clocks, not D3): the `squeeze_marks.py` after-hours stretch,
  `RS_TILE_PRIOR_TO_ET`, `LEDGER_FILL_TO_ET`.
- **Half-day passes 17:06–20:05** still run (`run.in_window` unchanged); after D3 they read tape "closed" and change
  nothing (no carry change, no 🌙, no push).
- **The chart's "A+" marker** on a triggered break that never rang (D10 changed the words, not the marker).
- **Luk's 🥇 triggered card** still says "A+ on the …" (`chart_maps/luk/tab.py`, its own `state_label`) — not in D1–D13.
- **K7 demo case C** (a first pullback low inside `VCP_PIVOT_WINDOW` of the demand bar's lower low is never a pivot →
  two real contractions read "1 of 2") — D1's smallest fix does not cover it; fixing it changes the pivot rule.
- **"Volume came later"** is not printed on D10 cards — no-ring also comes from the window, a missed pass, the no-risk
  guard or the dedupe, and stored data cannot tell them apart. The late K11 pass is still NOT allowed to ring.

## HIS CALLs (never decided here)

0. Provenance: this build ran on the main session's relay of his 08:18 ET words, quoted above.
1. **Ship the count-gated set (D1, D2, D4–D6, D11 Gajjala; D7 SEPA; D8 Kell) BEFORE or AFTER the count?** Recommended:
   after — the count tonight after 16:00 ET, the table to him, deploy on his word.
2. **Ship-now set: deploy as soon as green?** Recommended: yes, on its own deploy, after the `shipnow` replay shows zero
   kept-A+ movement; **D3 no later than 2026-11-25 whatever #1 says.**
3. **D11 is a scanner line** — the fix enforces his "25% or more" exactly and lists an exactly-on-the-line name one pass
   earlier. Confirm.
4. **D10 words and readers** — built as above on live-push pages only, served to EVERY reader (the 🏁 already shows
   non-owners which alerts rang; owner-only words would break the nothing-hidden rule). Confirm, give his words, or say
   non-owners keep today's words.
5. **The chart's "A+" marker** on a triggered break that never rang — change it too?
6. **K7 demo case C** — a pivot-rule change, his rule.
7. **D2 same-bar case** — the fix measures the drop and the recovery from the PRIOR running high, not the bar's own high.
   Confirm, or keep the bar's own high when the minutes prove the order.
8. **Kell nightly push `setup_base_n_break`** — D8 / D12 only remove names; whether the push should exist is not in scope.
9. **Half-day passes 17:06–20:05** — end the half-day pass window at the extended close + the `PASS_CLOSE_ET` grace
   instead? A pass-schedule change; recommended: leave it (inert).
10. **Massive's day bar on a half day is unmeasured** — the 2026-11-27 ≈13:05 ET check: if `day.c` tracks the last trade,
    Monday's ☀️ carry is unreliable; the remedy is his, nothing is built ahead of the check.
11. **Luk's 🥇 triggered card** "A+ on the …" — fix it the same way in a later ask?
