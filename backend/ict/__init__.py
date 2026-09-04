"""ICT strategy — price-action-only structure for the Chart Maps ICT tab.

Ajay 2026-09-03 (late): "create a new chart maps tab for ICT Strategy,
replace supply tab with this new tab."

SOURCE STATUS — read before touching a threshold
------------------------------------------------
The concepts come from Ajay's own spec and from Jesse Rogers' video
https://www.youtube.com/watch?v=Q7Ryv1M7CvI :

    02:39  lack of displacement — the manipulation wicks past a key low but
           does not close strongly below it
    03:57  two or more sideways consolidations as price moves toward a
           higher-timeframe fair value gap; the manipulation sweeps under them
    05:30  Power of 3 — find the accumulation range first; the manipulation
           is the move below its lows (bullish bias)
    plus   "confirm with opposite displacement creating a new FVG"

Every numeric threshold the spec does NOT give (what counts as a tight
consolidation, how many bars, tap tolerance, stop buffer, ...) is an OWNER
CONSTANT: named, defaulted, and marked "owner rule — not from the video" in
code and in docs/ict/ict_chart_maps.md. This package borrows nothing from the
SEPA methodology and cites no book. No moving averages of any kind: purely
price action, as Ajay asked.

Layout
------
    structure.py  pure primitives (frames in, dicts out, no I/O)
    engine.py     macro (daily) key levels, the dormant micro (60m) loop,
                  scan / persist / cached_or_warm, `python -m ict.engine`
    board.py      rows -> Chart Maps tile geometry (pure)

Decision support, not advice.
"""
