"""Scalping — intraday strategy detectors with an honest net-of-cost overlay.

Built 2026-06-09 from a vetted research pass (see docs/scalping_methodology.md).
Phase-1 detectors, each tied to a NAMED, cited source:

  • Stocks-in-Play 5-min ORB   — Zarattini, Barbon & Aziz (2024), SSRN 4729284
  • Volatility-normalized fade  — Zawadowski, Andor & Kertesz (2004), arXiv cond-mat/0406696
  • Intraday-momentum regime    — Gao, Han, Li & Zhou (2018), JFE 129(2) — a DIRECTION gate, not a scalp

Every signal carries a GROSS read beside a NET-of-cost reality (spread + fees +
slippage + borrow) and the win rate it would need just to break even. The page
is EDUCATIONAL, not advice — and the weight of the account-level evidence is that
the activity these detectors enable is net-losing for the large majority of
retail traders. Nothing here changes that base rate.

Reuses the existing intraday stack (daytrading.data / daytrading.indicators) and
the Massive snapshot NBBO for the live spread gate.
"""
