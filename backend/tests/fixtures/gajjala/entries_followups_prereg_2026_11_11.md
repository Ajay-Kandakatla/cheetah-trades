# 🚩 Gajjala entries follow-ups #5 / #6 / #7 — pre-registration (2026-11-11, frozen before any run)

Frozen 2026-11-11 11:48 ET (RTH), BEFORE any script was written or any number read. Nothing here is built in the lane.
Source: the 9-row table "Proposals — every one is HIS CALL" in
/Users/ajay/clinet-test/eod-audits/research/2026-11-11_entries_followthrough.md:234-246; #5 / #6 / #7 are studies, so
they are pre-registered here and run in a separate turn after 16:00 ET.

## His words (verbatim, Ajay 2026-11-11)

"Also apply your proposal too.

Here is how he enters please tell me to enter based on this

Can you check for any mistakes"

## The three studies (every variant from GG's own rules; no invented number)

- S5 GG-style exits (paper replay). Cohort: every 5-min 🚩 A+ that rang live (🏁 rows, GG5). Entry = the 🏁 ledger fill.
  Variants (3): P1 = 1/2 off at the close of the 3rd 5-min bar after the fill when that close is above the fill (E5
  "after ~15 min / 3 bars when strong"), rest out on the first 5-min close under the 9 EMA; P2 = the same with 1/3 off;
  P3 = no partial, out on the first 5-min close under the 9 EMA. All: the alert's stop; break-even after +
  `STUDY_BE_AFTER_R` (1.0, constants.py:166 — E4); flat at the lane's flatten minute (`gajjala_entry.flatten_et`).
  Baseline = the ledger's +1R/stop. Split: sessions by date, first two-thirds in-sample (pick one of P1–P3), last third
  SEALED, read once.
- S6 wider stop. Cohort: the same A+ rows. Variants (3, all GG-sourced): the alert's stop (baseline); BF7 careful = the
  lower of the last two pullback/base bars' lows; C1 = the base low. Target +1R of each stop (ledger math). The
  hypothesis came FROM the 2026-10-13…11-10 sessions ("tight stops lose more") → FORWARD HOLDOUT ONLY: sessions from
  2026-11-11 on, read once at ≥ 30 rings.
- S7 🎾 "dipped under the base, then broke". Cohort: 5-min 🎾 ARMED 🧠 rings. Arm A = a regular print under the ring's
  stop before the first break of its trigger that session; arm B = broke without the dip. Entry at the break (ledger
  fill), +1R / stop. No variants. Post-hoc origin (19 W / 10 L vs 8 W / 14 L) → FORWARD HOLDOUT ONLY, ≥ 30 per arm.
- For all three: outcome = R per trade after 10 bps/side; report expectancy, win % and the stop-out rate side by side;
  placebo = the same rule on random entry minutes in the same names and sessions, 1,000 draws; POSITIVE = the strategy
  lab's rule (OOS mean R > 0 with the 95 % bootstrap CI excluding 0, placebo beaten, DSR ≥ 0.95 over all 9 trials).
  A positive read is a HIS CALL for a PAPER variant — never a gate, never the 🚩 lane by itself.
- Runs: after 16:00 ET only, read-only Mongo in a throwaway `--rm` container, no broker import, no Massive fetch;
  scripts + logs under /Users/ajay/clinet-test/eod-audits/research/2026-11-11_entries_followups/ (the script ships to
  the repo with any claim).

## Provenance notes (not part of the frozen rules)

- `STUDY_BE_AFTER_R` = 1.0 is the constant by name; on the tree this file was frozen against it sits at
  backend/chart_maps/gajjala/constants.py:172 (the ":166" above is the spec's citation, kept verbatim).
- `LEDGER_R_MULT` = 1.0 (constants.py:219) is the "+1R" of the ledger math above.
