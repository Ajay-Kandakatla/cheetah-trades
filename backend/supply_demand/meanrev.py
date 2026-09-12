"""Mean reversion — a least-squares channel over whatever window is on screen.

Ajay 2026-09-12: *"Also mean reversion please on 1 year charts"*, then
*"Basically any chart time frame add this newly please"* — so the window is not
fixed at a year. Every level here is computed from **the bars it is handed**,
which is what makes one implementation serve 1y / 2y / 3y / 5y and intraday
without a mode flag.

WHY A SLOPED MEAN AND NOT A FLAT ONE
────────────────────────────────────
He was offered a flat 1-year average with sigma bands and did not pick one, so
this is my call and worth stating: **a flat mean marks every leader as "rich"
for its entire run.** A name up 100% on the year sits above its own 252-day
average every single day, and an overlay that is permanently red on exactly the
stocks the rest of the app is built to find is worse than no overlay. The
least-squares fit removes the drift first and measures the deviation AROUND the
trend, so "stretched" means stretched versus where this name has actually been
going. One constant (`SLOPED = False`) flips it if he disagrees.

SOURCE STATUS
─────────────
A regression channel is chart convention. **No cited source, never measured
forward, and it gates nothing** — display only, like `fib.py` and `amd.py`.
`CITED = False`. Sigma here is the dispersion of closes about the fit; it is
NOT a probability statement, because daily returns are not normal and the fit
is estimated on the same bars it is scored against.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.meanrev")

SIGMAS = (1.0, 2.0)        # channel lines drawn each side of the fit
MIN_BARS = 40              # below this the fit is noise with a slope
SLOPED = True              # False = flat mean of the window instead
STRETCHED_SIGMA = 2.0      # what the label calls "stretched"
# Dispersion below this fraction of price is not a channel, it is rounding.
# Without the floor a near-perfect line gives sigma ~1e-14 and every z becomes
# astronomical — "stretched high" on a name that has not moved. Pinned by
# test_NEGATIVE_a_near_zero_sigma_reports_no_stretch.
MIN_SIGMA_PCT = 0.02

CITED = False
SOURCE_NOTE = ("Least-squares mean-reversion channel — chart convention, no "
               "cited source, never measured forward. Display only: nothing "
               "in the app gates on it. Sigma is dispersion about the fit, "
               "NOT a probability.")


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def fit(df, *, sloped: bool = SLOPED, min_bars: int = MIN_BARS) -> Optional[dict]:
    """{"intercept","slope","sigma","n","last_fit","z"} or None.

    `last_fit` is the mean's value at the LAST bar — the number the channel is
    centred on today — and `z` is how many sigma the last close sits from it.
    """
    if df is None or len(df) < min_bars:
        return None
    try:
        import numpy as np
        y = np.asarray(df["close"], dtype=float)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("meanrev: close column unreadable: %s", exc)
        return None
    y = y[np.isfinite(y)]                    # a NaN poisons the whole fit
    n = len(y)
    if n < min_bars:
        return None
    x = np.arange(n, dtype=float)
    if sloped:
        slope, intercept = np.polyfit(x, y, 1)
    else:
        slope, intercept = 0.0, float(y.mean())
    resid = y - (intercept + slope * x)
    sigma = float(resid.std(ddof=1)) if n > 1 else 0.0
    last_fit = float(intercept + slope * (n - 1))
    last = float(y[-1])
    # A channel narrower than MIN_SIGMA_PCT of price is rounding error, not
    # dispersion; z is then meaningless and is reported as 0 rather than as a
    # spurious "stretched" reading.
    floor = abs(last_fit) * (MIN_SIGMA_PCT / 100.0)
    z = (last - last_fit) / sigma if sigma > floor else 0.0
    out = {"intercept": float(intercept), "slope": float(slope),
           "sigma": sigma, "n": int(n), "last_fit": last_fit,
           "last": last, "z": round(float(z), 2)}
    return out if all(_f(out[k]) is not None for k in ("last_fit", "sigma")) else None


def levels(df, *, sigmas=SIGMAS, **kw) -> list:
    """The channel at the LAST bar: [{label, price, sigma, side}].

    A chart tile draws horizontal lines, so the sloped channel is reported at
    its current value. The slope still did its job — it is what the deviation
    was measured AROUND — and `reading()` carries it so the caller can say
    which way the mean itself is going."""
    f = fit(df, **kw)
    if not f or f["sigma"] <= 0:
        return []
    out = [{"label": "mean", "price": round(f["last_fit"], 4),
            "sigma": 0.0, "side": "mid"}]
    for s in sigmas:
        out.append({"label": "+%gσ" % s, "sigma": s, "side": "upper",
                    "price": round(f["last_fit"] + s * f["sigma"], 4)})
        out.append({"label": "-%gσ" % s, "sigma": -s, "side": "lower",
                    "price": round(f["last_fit"] - s * f["sigma"], 4)})
    return [x for x in out if x["price"] > 0]


def reading(df, **kw) -> Optional[dict]:
    """The one-line verdict: where price sits in its own channel.

    `state` is "stretched high" / "stretched low" / "in range", and `trend`
    says whether the MEAN is rising or falling — the two together are the
    whole read, because stretched-high in a rising channel and stretched-high
    in a falling one are not the same situation."""
    f = fit(df, **kw)
    if not f:
        return None
    z = f["z"]
    state = ("stretched high" if z >= STRETCHED_SIGMA else
             "stretched low" if z <= -STRETCHED_SIGMA else "in range")
    per_bar = f["slope"]
    trend = "rising" if per_bar > 0 else "falling" if per_bar < 0 else "flat"
    return {"z": z, "state": state, "trend": trend, "sigma": f["sigma"],
            "mean": round(f["last_fit"], 4), "bars": f["n"],
            "slope_pct_per_100_bars": (round(100.0 * per_bar * 100.0 / f["last_fit"], 2)
                                       if f["last_fit"] else None)}


def chart_lines(df, **kw) -> list:
    """Channel lines for a tile: {price, label, tone}.

    Tone is always "meanrev" so `chartOverlays` routes the family to one
    checkbox, never "buy"/"target" — these are not instructions."""
    r = reading(df, **kw)
    out = []
    for lv in levels(df, **kw):
        lab = ("mean %.2f" % lv["price"] if lv["side"] == "mid"
               else "mean %s %.2f" % (lv["label"], lv["price"]))
        out.append({"price": lv["price"], "label": lab, "tone": "meanrev",
                    "sigma": lv["sigma"], "side": lv["side"]})
    if r:
        for o in out:
            o["z"] = r["z"]
            o["state"] = r["state"]
    return out
