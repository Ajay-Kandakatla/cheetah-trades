"""Self-learning calibration loop for the app's signals.

The premise: every signal that drives a prediction (SEPA tier, catalyst tier,
sentiment score, frenzy flag, insider cluster, etc.) is logged as an
``observation`` with a baseline price and a horizon. After the horizon expires,
a resolver fetches the actual price, scores the observation hit/miss/partial,
and a daily aggregator rolls observations into per-source accuracy stats.

This lets us answer two questions that were impossible before:

1. Out of all signals fired, what % were right? — single headline number.
2. How is that number trending over time? — daily snapshots in
   ``signal_calibration_history`` so we can plot accuracy decay / improvement.

See ``observations.py`` for the schema, ``resolver.py`` for the grading rules,
``calibrator.py`` for the rollup, ``backfill.py`` for the one-shot retroactive
grade against existing SEPA snapshots.
"""

from learning import observations, resolver, calibrator, backfill  # noqa: F401
