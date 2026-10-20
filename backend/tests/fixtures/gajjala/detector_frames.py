"""Synthetic closed-bar frames for the Gajjala detectors (tests/test_gajjala_detectors.py).

Every price and range is binary-exact (multiples of 1/64) so no decimal literal sits on a `>=` / `<=` edge; an edge
fixture is built with the detector's OWN expression (the K1 body edge is `o * (1 + K1_BODY_GAIN_PCT / 100)`).

Shapes on HIS invalid examples (FIRST_HAND + STRATEGY_SPEC §1.3) are reproduced by the defect they describe, not by
the real tape: OCX (first up bar 10× the candle before), RKDA (two sudden bars, the pullback gives back too much),
NVCT (one big candle), ZYNE (5-bar flag), HKD (9-bar Kiss & Fly), NEXI (never touches the 9 EMA), BWV (impatient break
before the base), LQR (heavy selling after the main bar), AYLA (sharp pullback), SNES (spike + violent decline),
SASI (steady fade), SGD (no demand after the open), FCHL (float on file above shares out).

Layout: 20 prior-session warm-up bars (range 0.25 each → K1's average starts at exactly 0.25), then today's bars.
`frame()` returns a bars.Frame (the detectors' input); `today_index(F, k)` maps a today-offset to the frame index.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala.bars import Frame
from orderflow.signals import ema as _ema

PRIOR_DAY = "2026-10-12"
TODAY = "2026-10-13"
WARM_N = 20
Q = 0.125                                   # half of the 0.25 warm-up range


def quiet(p: float, v: float = 100_000) -> tuple:
    """A doji-ish quiet bar at p, range 0.25."""
    return (p, p + Q, p - Q, p, v)


def warm(p: float = 10.0, n: int = WARM_N, v: float = 100_000) -> list:
    return [quiet(p, v) for _ in range(n)]


def _stamps(day: str, start: str, n: int, step_min: int) -> list:
    t0 = datetime.strptime(f"{day} {start}", "%Y-%m-%d %H:%M")
    return [(t0 + timedelta(minutes=step_min * i)).strftime("%Y-%m-%d %H:%M") for i in range(n)]


def _masked_ema(closes: list, span: int) -> list:
    s = _ema(pd.Series(closes, dtype=float), span)
    return [None if i < span - 1 else float(x) for i, x in enumerate(s)]


def frame(today: list, *, prior: list | None = None, ema9: list | None = None, ema21: list | None = None,
          minutes: dict | None = None, tf: str = "5m", start: str = "09:35") -> Frame:
    """today / prior = [(o, h, l, c, v)]. ema9 / ema21 = TODAY-only explicit values (the prior part repeats the first
    value) or None → the masked 9/21 EMA of the closes (the bars.py rule). minutes = {today_offset: [(o,h,l,c,v)]}."""
    prior = warm() if prior is None else prior
    bars = list(prior) + list(today)
    step = 15 if tf == "15m" else 5
    t = _stamps(PRIOR_DAY, "15:05" if tf == "5m" else "11:15", len(prior), step) + _stamps(TODAY, start, len(today),
                                                                                       step)
    closes = [b[3] for b in bars]

    def series(explicit, span):
        if explicit is None:
            return _masked_ema(closes, span)
        assert len(explicit) == len(today)
        return [explicit[0]] * len(prior) + list(explicit)

    F = Frame(o=[b[0] for b in bars], h=[b[1] for b in bars], l=[b[2] for b in bars], c=closes,
              v=[b[4] for b in bars], t=t, session=[PRIOR_DAY] * len(prior) + [TODAY] * len(today),
              ema9=series(ema9, GC.EMA_FAST), ema21=series(ema21, GC.EMA_SLOW),
              today=range(len(prior), len(bars)), df=pd.DataFrame({"high": [b[1] for b in bars],
                                                                   "low": [b[2] for b in bars]}), frame=tf)
    F.minutes = {t[len(prior) + k]: list(v) for k, v in (minutes or {}).items()}
    return F


def today_index(F: Frame, k: int) -> int:
    return F.today.start + k


def prefix(F: Frame, k: int) -> Frame:
    """The frame as it stood when frame bar k was the latest closed bar."""
    G = Frame(o=F.o[:k + 1], h=F.h[:k + 1], l=F.l[:k + 1], c=F.c[:k + 1], v=F.v[:k + 1], t=F.t[:k + 1],
              session=F.session[:k + 1], ema9=F.ema9[:k + 1], ema21=F.ema21[:k + 1],
              today=range(F.today.start, max(F.today.start, k + 1)),
              df=pd.DataFrame({"high": F.h[:k + 1], "low": F.l[:k + 1]}), frame=F.frame)
    G.minutes = {s: m for s, m in F.minutes.items() if s in set(G.t)}
    return G


# ── 🚩 Bull Flag ─────────────────────────────────────────────────────────────────────────────────────────────────
D1 = (10.0, 10.5, 10.0, 10.5, 200_000)       # K1: +5% body, range 0.5 ≥ 1.5 × 0.25
D2 = (10.5, 11.0, 10.5, 11.0, 300_000)       # K1 vs avg 0.2625; K2 step 1.5×
P1 = (11.0, 11.0, 10.875, 10.9375, 100_000)  # floor = 11.0 − 0.5 × 0.5 = 10.75; vol cap = 0.5 × 250k = 125k
P2 = (10.9375, 10.96875, 10.8125, 10.875, 80_000)
P3 = (10.875, 10.9375, 10.8125, 10.84375, 80_000)
BF_E = (10.875, 11.25, 10.84375, 11.2, 250_000)   # breaks P2's high; not itself a K1 bar (11.2 < 10.875 × 1.03)


_DEFAULT = object()


def bf_bars(pull: list | None = None, *, entry=_DEFAULT, after: list | None = None, leg: tuple = (D1, D2)) -> list:
    """quiet ×3 + the leg + the pullback + (entry) + after. The default entry is BF_E on the default pullback, else a
    bar that clears the last pullback bar's high by 0.25 and stays above its low (not itself a K1 bar)."""
    default_pull = pull is None
    pull = [P1, P2] if pull is None else pull
    out = [quiet(10.0)] * 3 + list(leg) + list(pull)
    if entry is _DEFAULT:
        last = out[-1]
        entry = BF_E if default_pull else (last[3], last[1] + 0.25, last[3], last[1] + 0.1875, 250_000)
    if entry is not None:
        out.append(entry)
    return out + list(after or [])


def flat_pull(n: int, top: float = 11.0, v: float = 80_000) -> list:
    """n quiet pullback bars, each high at or under the one before (no break), lows well above the K3 floor."""
    out = []
    for i in range(n):
        h = top - 0.015625 * i
        out.append((h, h, h - 0.0625, h - 0.03125, v))
    return out


def bf_aplus(**kw) -> Frame:
    return frame(bf_bars(), **kw)


# ── 💋 EMA Kiss & Fly ─────────────────────────────────────────────────────────────────────────────────────────────
KF_D = (10.0, 10.5, 10.0, 10.5, 300_000)      # one demand bar is enough (GG S8 31:33)


def kf_frame(n_pull: int = 3, *, kiss_above_pct: float | None = None, e21_rise: float = 0.0625,
             e21_over: float | None = None, pull_v: float = 100_000, red: int = 0, entry: bool = True,
             minutes: dict | None = None, honor_fail_at: int | None = None, doji: int = 0,
             one_print_kiss: bool = False) -> Frame:
    """Leg = KF_D, then n_pull pullback bars with descending highs; the LAST pullback bar kisses the 9 EMA (its low sits
    1/128 above the EMA — inside K5's tolerance). `kiss_above_pct` instead puts that low x% above the EMA (no kiss).
    `red` = the last `red` pullback bars close under their open; `doji` = the first `doji` close AT their open but
    under the bar before. `e21_over` puts the 21 EMA ABOVE the 9 EMA at the kiss bar; `e21_rise` = 0 flattens the 21.
    `honor_fail_at` = a pullback offset whose close sits under its 9 EMA (still above the K3 floor).
    `one_print_kiss` (2026-10-20, the MMA shape) = the kiss bar is ONE print: open = high = low = close, so the trigger
    (its high) equals the stop (its low); the 9 EMA still sits 1/128 under it (a kiss by K5's tolerance)."""
    pre = [quiet(10.0)] * 4
    pull = []
    for i in range(n_pull):
        h = 10.5 - 0.0078125 * i
        lo = h - 0.0625
        if one_print_kiss and i == n_pull - 1:
            o = lo = c = h                                       # one print: no range at all
        elif i >= n_pull - red:
            o, c = h - 0.015625, h - 0.03125                     # red close
        elif i < doji:
            o = c = h - 0.03125 - 0.0078125 * i                  # close == open, lower than the bar before
        else:
            o, c = lo + 0.0078125, h - 0.0078125                 # green close
        pull.append((o, h, lo, c, pull_v))
    bars = pre + [KF_D] + pull
    kiss_low = pull[-1][2]
    kiss_e9 = kiss_low / (1 + kiss_above_pct / 100) if kiss_above_pct is not None else kiss_low - 0.0078125
    e9 = [9.75] * len(pre) + [9.875]
    for i in range(n_pull):
        e9.append(9.875 + (kiss_e9 - 9.875) * (i + 1) / n_pull)
    e21 = [9.5 + e21_rise * i / (len(bars) - 1) for i in range(len(bars))]
    if e21_over is not None:
        e21[-1] = e9[-1] + e21_over
    if honor_fail_at is not None:
        k = len(pre) + 1 + honor_fail_at
        e9[k] = bars[k][3] + 0.0078125
    if entry:
        last = bars[-1]
        bars.append((last[3], last[1] + 0.125, last[2] + 0.015625, last[1] + 0.09375, 200_000))
        e9.append(e9[-1] + 0.015625)
        e21.append(e21[-1] + 0.015625)
    return frame(bars, ema9=e9, ema21=e21, minutes=minutes)


def kf_near_kiss(*, allow_touch_close_eq: bool = False) -> Frame:
    """NEXI-shaped: the pullback never reaches the 9 EMA, then a bar breaks the prior bar's high."""
    pre = [quiet(10.0)] * 4
    pull = [(10.5, 10.5, 10.4375, 10.46875, 100_000), (10.46875, 10.484375, 10.421875, 10.453125, 90_000)]
    br = (10.453125, 10.625, 10.4375, 10.59375, 200_000)
    bars = pre + [KF_D] + pull + [br]
    e9 = [9.75] * 4 + [9.875, 10.0, 10.0625, 10.125]
    if allow_touch_close_eq:                                  # bar P2 touches with close == EMA9 (honors, not a kiss)
        e9[6] = pull[1][3]
    e21 = [9.5 + 0.015625 * i for i in range(len(bars))]
    return frame(bars, ema9=e9, ema21=e21)


# ── ➖ Horizontal Fade ────────────────────────────────────────────────────────────────────────────────────────────
HF_BASE = [(11.0, 10.9375, 10.8125, 10.875, 100_000), (10.875, 10.90625, 10.78125, 10.84375, 100_000),
           (10.84375, 10.9375, 10.8125, 10.90625, 100_000), (10.90625, 10.875, 10.8125, 10.84375, 50_000),
           (10.84375, 10.90625, 10.8125, 10.875, 50_000), (10.875, 10.875, 10.8125, 10.84375, 50_000)]
HF_E = (10.84375, 11.125, 10.84375, 11.0625, 250_000)


def hf_frame(base: list | None = None, *, entry: tuple | None = HF_E, merged: bool = True, gap_frac: float | None = None,
             tf: str = "15m", after: list | None = None, merge_from: int | None = None) -> Frame:
    """Leg D1+D2 (2 demand bars), a tight base at the top on halving volume, EMAs merged at the bar before the entry.
    `gap_frac` = |EMA9 − EMA21| as a fraction of the close at every base bar (None → 0.02 absolute, merged).
    `merge_from` = base offset from which the EMAs are merged (earlier base bars 2% apart)."""
    base = HF_BASE if base is None else base
    bars = [quiet(10.0)] * 3 + [D1, D2] + list(base) + ([entry] if entry is not None else []) + list(after or [])
    e9, e21 = [], []
    for i, b in enumerate(bars):
        e9.append(b[3] - 0.0625)
        k = i - 5                                              # base offset
        if gap_frac is not None and k >= 0:
            gap = b[3] * gap_frac
        elif merge_from is not None and 0 <= k < merge_from:
            gap = b[3] * 0.02
        elif merged or k < 0:
            gap = 0.015625
        else:
            gap = b[3] * 0.02
        e21.append(e9[-1] - gap)
    return frame(bars, ema9=e9, ema21=e21, tf=tf, start="09:45" if tf == "15m" else "09:35")


# ── 🌀 Intraday VCP ──────────────────────────────────────────────────────────────────────────────────────────────
VCP_BARS = [quiet(10.0)] * 3 + [
    (10.0, 10.5, 10.0, 10.5, 300_000),            # 3  D1 — the leg (one bar is enough, H3 = 1)
    (10.5, 10.75, 10.4375, 10.6875, 150_000),     # 4
    (10.6875, 11.0, 10.625, 10.875, 150_000),     # 5  H1 = 11.0
    (10.875, 10.9375, 10.375, 10.4375, 80_000),   # 6
    (10.4375, 10.5, 10.0, 10.0625, 70_000),       # 7
    (10.0625, 10.125, 9.75, 10.0, 60_000),        # 8  L1 = 9.75   → r1 = 1.25
    (10.0, 10.375, 9.875, 10.25, 60_000),         # 9
    (10.25, 10.5625, 10.125, 10.5, 60_000),       # 10
    (10.5, 10.75, 10.375, 10.625, 60_000),        # 11 H2 = 10.75
    (10.625, 10.6875, 10.125, 10.1875, 50_000),   # 12
    (10.1875, 10.25, 9.875, 10.125, 40_000),      # 13 L2 = 9.875  → r2 = 0.875 (0.70×)
]
VCP_E = (10.5625, 10.875, 10.0625, 10.8125, 150_000)  # 14 breaks H2 → trigger 10.75, stop 9.875 (not itself a K1 bar)


def vcp_frame(bars: list | None = None, *, entry: tuple | None = VCP_E, after: list | None = None,
              e21_at: dict | None = None, minutes: dict | None = None) -> Frame:
    """21 EMA under the 1st cycle low; the 2nd low 9.875 sits 0.25% UNDER a 9.90 21 EMA — inside the 0.5% K7 tolerance
    ("not completely honors the 21 EMA … but it does these higher lows", GG). The break comes right after the 2nd
    low, so a pivot window of 3 cannot confirm the 2nd cycle high (H5 sweep)."""
    bars = list(VCP_BARS if bars is None else bars) + ([entry] if entry is not None else []) + list(after or [])
    e21 = [9.5 + 0.03125 * i for i in range(len(bars))]
    if len(bars) > 13:
        e21[13] = 9.90
    for k, val in (e21_at or {}).items():
        e21[k] = val
    e9 = [b[3] for b in bars]
    return frame(bars, ema9=e9, ema21=e21, minutes=minutes)


def vcp_replace(**rows) -> list:
    """VCP_BARS with today-offset rows replaced: vcp_replace(r13=(…))."""
    out = list(VCP_BARS)
    for k, v in rows.items():
        out[int(k[1:])] = v
    return out


# ── 🎾 Reversal Squeeze ──────────────────────────────────────────────────────────────────────────────────────────
RS_BARS = [
    (5.0, 5.125, 4.875, 5.0, 100_000),            # 0  04:05 premarket
    (5.0, 5.5, 5.0, 5.5, 200_000),                # 1
    (5.5, 6.0, 5.5, 5.875, 300_000),              # 2  premarket high 6.0
    (5.875, 5.96875, 5.625, 5.75, 200_000),       # 3  attempt: within 2% of 6.0, closes under it
    (5.75, 5.75, 5.375, 5.5, 200_000),            # 4  …and fails: 8%+ under 5.96875 (a plain sell-off, no recovery)
    (5.5, 5.625, 5.4375, 5.5625, 150_000),        # 5
    (5.5625, 5.75, 5.5, 5.6875, 150_000),         # 6
    (5.6875, 5.8125, 5.625, 5.75, 150_000),       # 7
    (5.75, 6.25, 5.8125, 6.1875, 400_000),        # 8  new high 6.25 = the tennis ball's reference bar r
    (6.1875, 6.25, 5.6875, 5.75, 500_000),        # 9  d: low 9% under 6.25
    (5.75, 6.25, 5.8125, 6.1875, 400_000),        # 10 k = p: closes back within 2% of 6.25
    (6.1875, 6.21875, 6.125, 6.15625, 60_000),    # 11 quiet base at the top
    (6.15625, 6.1875, 6.09375, 6.125, 50_000),    # 12
]
RS_E = (6.125, 6.5, 6.125, 6.4375, 400_000)       # 13 breaks the top bar's high 6.25 → stop = base low 6.09375

RS_S8_BARS = [                                    # S8 36:12 shape: the try at the highs IS the tennis-ball start
    (5.0, 5.125, 4.875, 5.0, 100_000),
    (5.0, 5.5, 5.0, 5.5, 200_000),
    (5.5, 6.0, 5.5, 5.875, 300_000),              # premarket high 6.0
    (5.875, 5.9375, 5.75, 5.875, 150_000),
    (5.875, 6.125, 5.8125, 5.875, 400_000),       # 4 the open: takes 6.0 intrabar, closes under it (a = r)
    (5.875, 5.875, 5.5, 5.625, 500_000),          # 5 sells off 10%
    (5.625, 6.0625, 5.625, 6.03125, 400_000),     # 6 squeezes back (k = p)
    (6.03125, 6.0625, 5.96875, 6.0, 60_000),      # 7 quiet base
    (6.0, 6.03125, 5.9375, 6.0, 50_000),          # 8
]
RS_S8_E = (6.0, 6.25, 5.96875, 6.1875, 400_000)


def rs_frame(bars: list | None = None, *, entry: tuple | None = RS_E, after: list | None = None,
             minutes: dict | None = None) -> Frame:
    bars = list(RS_BARS if bars is None else bars) + ([entry] if entry is not None else []) + list(after or [])
    return frame(bars, prior=warm(5.0), start="04:05", minutes=minutes)


def rs_replace(base: list | None = None, **rows) -> list:
    out = list(RS_BARS if base is None else base)
    for k, v in rows.items():
        out[int(k[1:])] = v
    return out


def float_read(shares, text: str | None = None, suspect=None) -> dict:
    if text is None:
        text = "float unknown" if shares is None else f"Float {shares / 1e6:.1f}M"
    return {"shares": shares, "src": "float", "text": text, "as_of": TODAY, "suspect": suspect}
