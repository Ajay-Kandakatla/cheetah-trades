# Tomorrow Bias — overnight / after-hours → next-session lean

**What it is:** for one ticker (the options-flow tab) or the whole market (the
Overnight page) we combine three *independent* reads into a single
`LEAN_UP / LEAN_DOWN / NEUTRAL` plus a confluence-gated confidence.

**What it is NOT:** a prediction. The standing caveat is baked into every
payload and rendered on every card:

> This TILTS probability for reacting at the open — it does not predict the
> overnight. React at the open; don't bet the overnight guess.

This is the Minervini stance verbatim in spirit (*Trade Like a Stock Market
Wizard*, Ch. 6 on buying the confirmed move, and the Ch. 13 discipline of
deciding **before** you act): an overnight gap is low-information until the open
confirms it. So the model's honest default is **NEUTRAL**, and **HIGH**
conviction is reachable only when all three pillars independently agree on
real, fresh data.

Implementation: `backend/options/tomorrow_bias.py` (pure scorers
`score_bias` / `score_market_bias` + thin network gatherers),
`GET /options/bias/{symbol}` and `GET /options/market-bias`,
`frontend/src/components/TomorrowBias.tsx`. Tests:
`backend/tests/test_tomorrow_bias.py`, `frontend/src/lib/tomorrowBias.test.ts`.

No new data feeds — everything is read off modules we already run:
`daytrading.data` (session-tagged extended-hours bars), `options.soir`
(SOIR put/call OI + volume + expected move + IV), `sepa.market_regime`
(regime label + VIX). Index futures (ES/NQ) are **not** entitled, so SPY/QQQ
extended-hours bars are used as the futures proxy.

---

## Per-ticker: three pillars

Each pillar yields a signed score in `[-1, +1]` (sign = direction, magnitude =
strength). Blend `raw = 0.45·stock + 0.30·options + 0.25·backdrop`;
`raw ≥ +0.20 → LEAN_UP`, `≤ −0.20 → LEAN_DOWN`, else `NEUTRAL`.

1. **Stock extended-hours move (0.45) — the anchor.** The name's after-hours
   (or premarket) move vs the most recent regular close, measured in units of
   its own ATM-straddle implied move. Scaled by how *real* the move is (bar
   count) and whether the gap is **holding** near its extreme.
2. **Options flow (0.30).** Today's put/call **volume** read as fresh
   positioning (non-contrarian) blended with the SOIR **OI** percentile read
   contrarian (Schaeffer). When the two disagree, the pillar contributes **0**.
3. **Market backdrop (0.25).** SPY/QQQ extended-hours gap (the ES/NQ proxy)
   plus the regime label (`confirmed_uptrend` tailwind / `market_in_correction`
   headwind).

**Confidence** is earned from *agreement*, not magnitude: count the pillars
whose sign matches the lean with `|score| ≥ 0.25`. **HIGH (≥70)** requires all
3 agreeing on real volume with a holding gap and VIX < 30. A stack of
governors only ever *lowers* confidence (see below).

## Market panel

`G = 0.6·bucket(SPY gap) + 0.4·bucket(QQQ gap)`. The two indices **must share
sign** (outside the noise band) or the lean is forced NEUTRAL. A **fading**
gap halves the weight and caps confidence at LOW. Confidence climbs only as
independent confirmers — VIX (real two-close delta), overnight breadth, regime
— agree with the gap.

---

## Why several "obvious" confluences are deliberately *not* counted

The scoring was pressure-tested by an adversarial review (2026-06-26) whose
whole job was to find places the model would show confidence that fades by the
open. Each fix below is a regression-tested guardrail (`test_tomorrow_bias.py`):

| Trap caught | Fix | Test |
|---|---|---|
| Regime compared to `"correction"` — the real enum is `market_in_correction`, so the don't-fight-the-tape penalty would never fire | exact-enum match only | `test_regime_enum_must_match_exactly_not_substring` |
| A pure-**beta** gap rewarded twice — in the stock pillar **and** the backdrop — faking idiosyncratic confluence | stock pillar is the **beta residual** (`gap − β·SPY gap`) | `test_beta_residual_neutralises_a_pure_beta_move` |
| A **thin** after-hours print (a few prints) read as a real move | thin print caps confidence ≤ 40, can never be HIGH | `test_thin_print_can_never_be_high` |
| Earnings veto trusting a news **keyword** alone (silently fails when no article scraped yet) | an abnormal implied move / IV also forces EVENT MODE (range, not direction) | `test_event_mode_from_abnormal_iv_forces_neutral_band` |
| Fast (volume) and slow (contrarian OI) options reads **opposing** but one manufacturing a sign | conflict → options pillar contributes 0 | `test_options_conflict_zeroes_the_pillar` |
| `soir_percentile = None` (single-symbol path) counting as a full confluence pillar | half-data → can't unlock HIGH (cap 50) | `test_options_partial_when_percentile_missing_cannot_be_high` |
| A faded gap (retraced >50% off its extreme) still scoring full weight | lose the ×1.0 real-volume multiplier when not holding | (folded into stock-pillar logic) |
| Market VIX confirmer derived from the SPY gap inverse — auto-agreeing with the spine it came from | VIX counts only with a real two-close ^VIX delta; else neutral | `test_market_vix_proxy_only_is_not_a_confirmer` |
| Stale extended-hours data (premarket read carried into midday) showing a confident lean | staleness from the **last EH bar timestamp**; premarket invalid after ~09:35 ET → NEUTRAL | `test_stale_eh_window_is_neutral` |

Plus standing governors that cap confidence: **fighting-the-tape** (stock vs
backdrop oppose), **inside expected move** (the options market already priced
it), **high VIX** (gaps fill more often in stress).

## Known limitations

- The earnings/event gate is **IV-inferred**, not a confirmed calendar. It will
  occasionally over-suppress a high-IV name or, rarely, miss a low-IV report.
  `earnings_source` is surfaced in `flags` so the read is auditable.
- Thin-print thresholds are global (bar count + holding), not yet calibrated to
  each symbol's own trailing extended-hours volume profile.
- Market-panel **breadth** is best-effort: when not wired for a run it reads
  `neutral` and is flagged `breadth_unavailable` rather than guessed.
- Beta defaults to 1.0 when the daily-returns estimate is unavailable, which
  *under*-subtracts market push on high-beta names (a conservative direction —
  it can only make the stock pillar smaller, never larger).

**Never auto-trade off this panel.** It informs sizing and open-react posture
only — consistent with `market_regime.py`'s own "regime descriptor, not a
return predictor" caveat.
