# The bull-regime gate on the setup scanners

Ajay 2026-08-31: *"there is a problem with setup tab and Supply demand tab..
Can you make sure logic is intact"*.

## The bug

`setups/universe.is_bull_regime()` imported
`sepa.market_regime.classify_regime`. **That function has never existed** — the
module's public entry point is `regime()`. The resulting `ImportError` was
caught by a bare `except` that returns `None`, and `None` means *"can't
determine — go ahead"*.

Every scanner gated on this:

```python
if universe.is_bull_regime() is False:      # never True of None
    return []
```

So the gate returned `None` on every call since it was written, and the
sit-out-bear-markets rule Ajay explicitly asked for **had never once fired**.
The scanners ran wide open through every correction.

It fails silently in both directions, which is why nothing surfaced it: a
bearish tape produced setups (no error), and a bullish tape produced setups
(correct, by accident).

## The fix

Import `regime()`. It returns `label` and `score`; it has no `safe_to_long` key
today, so the label decides. The three labels `_label_from_score` can emit are
now mapped **explicitly**:

| label | longs allowed | why |
|---|---|---|
| `confirmed_uptrend` | yes | trend, breadth and stress aligned |
| `uptrend_under_pressure` | yes | cracks forming is not a bear |
| `market_in_correction` | **no** | ≥6 distribution days, or composite < 40 |

The explicit table replaces a substring heuristic that got
`uptrend_under_pressure` right **by accident**: it tested `"uptrend" in label`
before the bear words, and "uptrend" is a substring of
"uptrend_under_pressure". The answer is unchanged; it is now a decision. For
labels outside the table the guess remains, but the bear words are tested
**first** — when guessing, caution has to win.

`safe_to_long` still outranks any label read, because that is the field this
should key off if the regime module ever publishes it.

Verified after the fix: `regime()` = `confirmed_uptrend`, score 72.5,
`is_bull_regime()` = **True** (was `None`).

## Tests

`backend/tests/test_setups_regime_gate.py`. The load-bearing one is
`test_is_bull_regime_calls_a_function_that_actually_exists`, a **source guard**:
it reads the function's own source and resolves every name it imports from
`sepa.market_regime`. A behavioural test could not have caught the original bug,
because a gate that always fails open still returns a legal value. Confirmed to
fail on the pre-fix code (6 of 8 tests red).

## Separately: the Setup tab was stale when Ajay asked

Every evening scanner last produced rows on **Thu 2026-08-27** at its scheduled
minute (cheat 18:40, bull_flag 18:45, episodic_pivot 18:50, post_earnings_drift
19:00 — exactly the crontab). Friday 2026-08-28 produced **zero rows from all
eight**, while `orb` ran normally that morning at 09:46.

A scan that finds nothing writes nothing, so the absence cannot by itself
distinguish "the jobs ran and found nothing after the selloff" from "the jobs
did not run". The candidate feed was healthy when checked (80 candidates, 68
Stage-2), so starvation is ruled out. Not diagnosed further; flagged here so the
next Friday gap is read against this note rather than rediscovered.

*Decision-support only. Not investment advice.*
