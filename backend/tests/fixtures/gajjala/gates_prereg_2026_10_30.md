# 🚩 Gajjala gates: pre-registration (2026-10-30, frozen before any run)

Ajay 2026-10-29, verbatim: "For the missing gaps please idenfity solutions that you fit appropriate for all … I would like you to take control of the startegy an ideal one".
This delegates HIS CALLs on the four gaps to Claude. The rules below are MY calls. Every number is frozen here. A gate ships only if the replay says it does.

## The four gaps and the rule chosen for each

| Gap | Rule (variants frozen) | Source |
|---|---|---|
| G1 break-bar proof | A+ only when the 5-min break bar CLOSES above the trigger AND its volume ≥ k × the mean volume of the base bars. k ∈ {1.0, 1.5, 2.0} | GG: "I want the price and volume to prove it"; "a breakout back into its range = out" |
| G2 red closes | not A+ when the base's last run has > 3 consecutive red 5-min closes. No variants (GG's own number) | GG X6: "more than 3 red closes is red flag to me => wait more" |
| G3 stale / missed (#9) | no lane entry when the ring is older than m minutes at the tick, m ∈ {10, 20, 30}; MISSED_R ∈ {0.5, 1.0} | Losers study 10-13..10-29: C3 fill ≥ 60 min after the ring = 47 losers vs 28 winners; 10-29 PRCH filled 59 min late after host sleep |
| G4 stop-distance cap | not A+ when (trigger − stop)/trigger > c, c ∈ {8 %, 10 %, 12 %}; 🎾 stop frozen at the first armed read | GG S8 32:27 "tight risk-reward entries always"; the app's own ABS_MAX_STOP_PCT 10 on every other lane |

Total trials: 3 + 1 + 6 + 3 = 13 single-gate trials, plus 1 combined (each gate's in-sample winner) = 14. DSR counts all 14.

## Method

- Cohort: every 🚩 A+ alert that RANG (live 🏁 grade docs) plus the ⏪ replay rows where the record has none, 5-minute page only (GG5). The 1-minute page is excluded because GG rejects that frame.
- Outcome: the 🏁 ledger's own `grade()` R per alert (GG trade math), with a conservative 10 bps/side cost added.
- Split: sessions ordered by date; the first two-thirds are in-sample (pick k, m, c), the last third is SEALED and read ONCE for the combined rule.
- Placebo: the same filter-pass rate drawn at random from the same cohort, 1,000 draws. The gate must beat ≥ 95 % of them on mean R.
- POSITIVE (per the strategy lab, eod-audits/research/2026-10-29_strategy_lab.md): the OOS mean R after costs > 0 with the 95 % bootstrap CI excluding 0, the placebo fails, and DSR ≥ 0.95 over all 14 trials.
- Ship rule (weaker than POSITIVE, since these are FILTERS on an existing paper lane): a gate ships to the paper lane when its OOS mean R is ≥ the baseline's OOS mean R AND it beats ≥ 80 % of the placebo draws. Anything else stays OFF and goes in the ledger.
- Runs: outside 09:30–16:00 ET, in a throwaway --rm container, Mongo read-only, no broker import.

## Not code (host)

The 10-29 blind spot was the lid closed on BATTERY at 21 % ('Clamshell Sleep' 06:39 CDT; `pmset -b sleep 1`). `pmset -c sleep 0` only covers AC. The fix is a physical/system step for Ajay: keep it plugged in, or `sudo pmset -b sleep 0` (clamshell on battery still sleeps without an external display). G3 makes the lane safe when it happens anyway.
