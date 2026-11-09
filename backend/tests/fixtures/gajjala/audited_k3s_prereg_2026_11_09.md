# 🧪 Gajjala · Audited — pre-registration: K3S, "K3 volume-dry not binding on the 🎾 Reversal Squeeze base"

Frozen 2026-11-09 ~01:10 ET, BEFORE any code. The repo pins this file's sha256 (`audited_rules.PREREG3_SHA256`) and a
byte copy lives at `backend/tests/fixtures/gajjala/audited_k3s_prereg_2026_11_09.md`; a test refuses a drift.

## His words

Ajay 2026-11-09 (after the 11-04 / 11-05 lane-miss read): "yes change the audit as per you like that is yours I need
you to make it successful and earn money that is the goal". HIS CALL #1 of the 11-09 read, decided: the modification
is mine to shape; it ships to the 🧪 Audited tab (shadow pushes, own 🏁) and nowhere else.

## Motivating observation (a cohort, NOT a result)

Over 2026-11-04 and 2026-11-05 every 🎾 Reversal Squeeze break stored at the end of the day on the 🚩 5-min tab —
nine reads: VCIG, SEGG, CHSN (11-04); LABT, AEHL, HUHU (18:05 break), BDMD, CHSN, EHGO (11-05) — was state "partial —
broke, not A+" with `missed == ["k3_vol"]` exactly: every other criterion met, the one refusal the K3 volume-dry cap
("K3 base volume ≤ 0.50× the squeeze-back run", `constants.K3_VOL_FRAC`, Ajay's K3 number applied to the squeeze base in
`detectors.reversal_squeeze`). GG's own words for the squeeze pullback are qualitative only: "the pullback is very
gradual, all at the top of this bar with gradual decrease in volume" (S8 36:12–38:18). Two sessions prove nothing;
they are why the question is asked.

## Hypothesis

H1: 🎾 breaks that 🚩 refuses SOLELY on `k3_vol`, graded by GG's trade math exactly as the 🏁 grades a 🚩 A+ (+1R before
the stop, fill at max(trigger, next minute's open), same column), win no less often and carry no worse expectancy in R
than 🚩's own 🎾 A+ rings over the same sessions. H0: they are worse (the cap earns its place on the squeeze).

## The rule, exactly (registry entry `K3S`, status ON on 🧪 only — his word 2026-11-09)

- Setup: `reversal_squeeze` only. Nothing changes for 💋 🌀 ➖ 🚩 Bull Flag.
- Input: the 🚩 5-min pass's own read for the name on the same pass (the GG5 path is byte-identical — goldens pin it).
- Fires when: the 🚩 read's state is "partial", its break bar is identified (`entry_bar_t` set), and `missed` is exactly
  `["k3_vol"]` — i.e. K8 tennis ball ✓, K8 failed attempt ✓, quiet base ≥ H4 ✓, red-closes chip not a criterion refusal,
  the float gate passed, and K11 session volume as 🚩 applies it at the break. Any second missed rule → K3S does not
  fire (no loosening beyond K3).
- Output: a 🧪 A+ ring at that break bar with 🚩's OWN plan unchanged — trigger, stop, R, risk % — no new number anywhere.
  The ring then passes through every other 🧪 rule that is ON (T1 daily cap 2 · T2 before 10:30 · A1 after 11:59 ·
  H1 regular hours only · T4 quiet-day regime · A2 10× volume spike) exactly as a 🚩 A+ would; a hold is recorded with
  the holding rule's words, as today.
- Push: SHADOW, `GAJJALA_AUDITED_PUSH_MODE` untouched. `OWNER_KEEP_SET` stays exactly seven.
- Grade: the 🧪 🏁 nightly (`nightly.grade_audited`) grades K3S rings with GG's math; one count per stock per day
  (`ledger.dedupe_trades`) applies; the per-rule winners/losers table gains a `K3S` row; the 🚩-vs-🧪 compare block lists
  every K3S ring as "🧪 only".
- Card: the 🧪 card for such a read says in words that the A+ is 🧪's by K3S and that 🚩 reads it "broke — not A+";
  the K3 criterion row stays visible with its ✗.

## Outcomes, pre-specified

Primary: K3S rings — W / L / unfilled, win rate with a Wilson 95% interval, mean R per ring (fill → +1R or the stop),
beside 🚩's 🎾 A+ rings over the same sessions (same grader, same columns).
Secondary: best_pct distribution; stop-out rate; share of K3S rings held by H1 (rang outside 09:30–16:00) and by T1/T2/A1.
Placebos (same grader, same sessions): (a) 🚩 🎾 "partial" breaks that missed a rule OTHER than `k3_vol`;
(b) 🎾 🧠 potentials that armed and never broke A+.
Minimum before any word: n ≥ 30 K3S rings (MINE). Out-of-sample: the first half of the sessions by date vs the second.

## What does NOT change

The 🚩 tab, its detectors on the GG5 path (byte-identical goldens), `K3_VOL_FRAC`, `verified_rules.json`, the pushes,
the paper lane (it trades 🚩 A+ only), the 1-minute page.

## Decision rule

Positive at n ≥ 30 with the interval clear of 🚩's rate → a paper-lane variant ONLY on HIS CALL, never a 🚩 change from
this file. Null or negative → K3S is turned OFF on 🧪 and the row stays on the 🏁 as a record.
