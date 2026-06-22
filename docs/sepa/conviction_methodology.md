# Conviction Rank — "which buyable name has the most return potential"

**Module:** `backend/sepa/conviction.py`
**Shipped:** 2026-06-22 (Ajay)
**Contract:** `docs/SEPA_CONTRACTS.md` §9d · locked in `backend/tests/test_sepa_contracts.py::test_conviction_weights_locked`
**Behavioral tests:** `backend/tests/test_sepa_conviction.py`

## What it is

A single 0–100 number that ranks the SEPA page, the Leaderboard and the Breakouts
board by how closely a name matches Minervini's highest-expectancy launchpad,
built from the three signals Ajay named — **volume, dried volume, momentum** —
plus a reward:risk closer. It is the new **default sort** on all three surfaces.

It is a **conviction / reward-to-risk rank, NOT a predicted % return.** The book
gives leading indicators of explosive moves, not a return forecast, so we rank by
fit to the ideal and surface the sub-scores ("why ranked here"), rather than
inventing a percentage. No new market math — every input is a field the scanner
already computes.

## Why momentum-led (the ranking question)

Minervini's own ranking is relative-strength leadership first:

- **The SEPA ranking process** screens on *earnings, sales, margin growth,
  **relative strength**, and price volatility*, then matches the **Leadership
  Profile** — TLSW p.34.
- **Trend Template** wants RS ≥ 70, *"preferably in the 80s or 90s, which will
  generally be the case with the better selections"* — TLSW p.79.
- Leaders *"power up the most percentagewise … move into new high ground first"*
  (TLSW p.96); top RS leaders *"show the greatest appreciation"* (p.111); Ch.9 is
  *Follow the Leaders* (p.161–165).

The VCP volume dry-up is the **entry-timing / risk** layer, not the ranker — VCP's
*"main role … is establishing a precise entry point at the line of least
resistance"* (TLSW p.198). So a pure coil-led or demand-led sort would be
backwards: momentum picks the name, coil + demand grade the entry.

## The four legs (each 0–100)

| Leg | Weight | Inputs | Book |
|---|---|---|---|
| **Momentum / leadership** | **0.35** | `rs_rank` (spine), Antonacci absolute-momentum gate (`abs_mom_pass`), beats-SPY winner filter | TLSW p.34, p.79, p.96, p.111, Ch.9 |
| **Coil / volume dry-up** | **0.30** | `vcp.tightness`, `volume.vol_dryup` (drier = more credit), `vcp.has_base` | TLSW p.198, p.203, p.206, p.226 |
| **Demand / confirmation** | **0.25** | `accumulation_strength`, `cmf_signal`, `up_down_vol_ratio`, `high_vol_breakout`/`pocket_pivot` | TLSW p.203 |
| **Reward : risk** | **0.10** | `risk_to_stop_pct` (tighter = better), `ext_from_pivot_pct` (chasing > 3% halves it) | TLSW p.224 |

`conviction = 0.35·momentum + 0.30·coil + 0.25·demand + 0.10·reward_risk`, clamped
0–100. Weights are locked in the contract test; momentum is the heaviest leg by
design (`w["momentum"] == max(w.values())`).

## Suppression — the AMAT case

A **climax-top distribution** (`climax_distribution.is_distribution`, TTLAC
pp.186–188) or a **late-stage MVP exhaustion** (`mvp_exhaustion`, TTLAC §9 p.199)
is a **SELL, not a buy** — Minervini's instruction is to *"sell aggressively into
strength,"* not initiate. Such a name can carry a high RS and still be the worst
thing to buy, so its conviction is multiplied by `SUPPRESS_MULT = 0.15` and
flagged `suppressed: true` with a reason. This keeps the rank in lock-step with:

- the `is_buyable` gate (already excludes distribution, §5b clause 9), and
- the **climax-aware ENTER verdict** — `entry_exit._decide` now returns **AVOID**
  (red) for a climax-top distribution at **any** stage, and **HOLD_WATCH** (amber)
  for the weaker churn-breakout tell, instead of letting a Stage-2 climax fall
  through to ENTER. See `backend/sepa/entry_exit.py` and
  `tests/test_entry_decision_stage2.py::test_stage2_climax_distribution_avoids_not_enters`.

A climax name re-qualifies only after it builds a **fresh base** (TLSW p.82,
Stryker: *"topped after a climax run; five years later a new base developed during
a renewed stage 2"*). It stays on the watchlist (`setup_ready`) to catch that, but
is excluded from Top Picks and sinks to the bottom of every sorted list.

## Where it sorts

| Surface | Default order |
|---|---|
| SEPA page (`Sepa.tsx`) | `is_buyable` first, then `conviction` desc |
| Breakouts board (`Breakouts.tsx`) | `is_buyable` first, then `conviction` desc (new **Conv.** column) |
| Rank leaderboard (`SepaRankLeaderboard.tsx`) | `conviction` desc (🏆 sort) |
| Top Picks (`top_picks.py`) | actionability tier, then `conviction` desc within tier; climax names excluded from the backfill |

## Citations

- Minervini, *Trade Like a Stock Market Wizard* (2013): pp.34, 79, 82, 96, 111,
  161–165, 198, 203, 206, 224, 226.
- Minervini, *Think & Trade Like a Champion* (2016): pp.186–188 (climax top, §9
  "When to Sell"), §9 p.199 (MVP exhaustion).
- Antonacci, *Dual Momentum* — absolute-momentum gate + beats-SPY filter
  (`backend/sepa/dual_momentum.py`).
