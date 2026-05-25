"""Tiny Stock screener — small/micro-cap framework.

Combines proven frameworks adapted to the data we already collect for SEPA:

  - Tiny Titans (O'Shaughnessy)        : mcap $25M–$2B + P/S<1.5 + top-quintile RS
  - Insider cluster (Lakonishok–Lee)   : 2+ officers buying within 30d
  - Pre-frenzy signals                 : your Frenzy Radar's 6 signals
  - Low-float runner                   : float<20M + RVOL>3 + catalyst
  - CANSLIM-adapted                    : EPS growth + RS leadership
  - Catalyst proximity                 : earnings/FDA within 14d

Score 0-100, tiered TINY_STRONG / TINY_BUY / TINY_WATCH / IGNORE.
Each tier emits a calibration observation just like SEPA, so accuracy
tracks automatically in /track.
"""
from tiny_stocks import scorer  # noqa: F401
