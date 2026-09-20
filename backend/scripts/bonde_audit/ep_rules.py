"""Bonde audit — the Episodic Pivot ENTRY rules, pure and importable.

WHY THIS FILE EXISTS (2026-09-20). Ajay's D#5: *"RE-MEASURE the Episodic Pivot
at Bonde's published numbers before any gate talk."* The 2026-09-13 audit
(`lane1.py`, README "The headline") reconstructed EPs at the SHIPPED detector's
thresholds — 8% gap on 5x volume — which are **ours**, not Bonde's. His
published entry is a different, looser gate. `lane1_published.py` runs all
three rules over the SAME cached panel, the SAME placebo and the SAME
bootstrap so the difference is a number instead of an argument.

This module is PURE on purpose [spec §3.9, fixed: C10]: no Mongo, no
`core.py`, no panel loading, no `sys.path` surgery — the panel is injected by
the caller. `backend/tests/test_bonde_ep_published_rule.py` loads it by path
(`importlib.util.spec_from_file_location`) and pins every rule on synthetic
bars. `lane1_published.py` execs `core.py` at the top and is therefore NEVER
imported by a test.

NOTHING HERE CHANGES A SHIPPED RULE (Rule #10). `setups/episodic_pivot.py` is
read, never written; its three constants are imported by name, never retyped.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

# ── the rules ────────────────────────────────────────────────────────────────
# Bonde's published entry, transcribed ONCE from the cited line. `strict=True`
# is his text's own comparison (`>` on price and volume, `>=` on shares), not a
# threshold of ours.
PUBLISHED = dict(
    name="bonde_published",
    close_ratio_min=1.04,
    vol_mult_min=3.0,
    min_shares=300_000,
    avg_window=50,
    strict=True,
    cite=(
        "stockbee.blogspot.com — `c/c1>1.04 and v>3*avgv50.1 and v>=300000` "
        "(docs/sepa/sales_confidence_methodology.md:40)"
    ),
)

# SENSITIVITY variant. The 2026-09-20 ask paraphrased his rule as "a 4% gap";
# his text is close/close. Same volume and share legs as PUBLISHED (derived
# from it, never retyped) so the ONLY difference measured is gap vs close.
PUBLISHED_GAP = {k: v for k, v in PUBLISHED.items() if k != "close_ratio_min"}
PUBLISHED_GAP.update(
    name="published_gap_variant",
    gap_pct_min=4.0,
    cite=(
        "SENSITIVITY: the 2026-09-20 ask paraphrased his rule as '4% gap'; his "
        "text is close/close. Not his rule."
    ),
)


def shipped() -> dict:
    """The rule the app actually scans, read from the enforcing constants.

    Never retype these numbers here — a change in `setups/episodic_pivot.py`
    must change this rule (pinned by the monkeypatch test).
    """
    from setups.episodic_pivot import (  # noqa: PLC0415 — deliberately lazy/pure
        _AVG_VOL_WINDOW,
        _MIN_GAP_PCT,
        _MIN_VOL_MULT,
    )

    return dict(
        name="shipped",
        gap_pct_min=float(_MIN_GAP_PCT),
        vol_mult_min=float(_MIN_VOL_MULT),
        min_shares=None,
        avg_window=int(_AVG_VOL_WINDOW),
        strict=False,
        cite=(
            "backend/setups/episodic_pivot.py _MIN_GAP_PCT / _MIN_VOL_MULT / "
            "_AVG_VOL_WINDOW — imported, never retyped"
        ),
    )


RULES = ("shipped", PUBLISHED["name"], PUBLISHED_GAP["name"])


# ── detection ────────────────────────────────────────────────────────────────
def _cumsum(v: Sequence[float]) -> list:
    """Sequential float64 cumulative sum — the SAME accumulation order as
    lane1.py's `np.cumsum`, so the shipped rule reproduces its event set bit for
    bit."""
    cs = [0.0]
    t = 0.0
    for x in v:
        t += float(x)
        cs.append(t)
    return cs


def detect(o: Sequence[float], c: Sequence[float], v: Sequence[float],
           rule: dict, dedup: int = 5) -> list:
    """Bar indices where `rule` fires on one symbol's bars.

    The trailing volume average is the prior `avg_window` bars EXCLUDING bar i
    (that is Bonde's `avgv50.1`, and it is what lane1.py measured): a bar can
    never lift its own baseline. The first testable bar is `avg_window + 1`,
    exactly lane1.py's loop start. At most one event per `dedup` bars.

    A rule carrying `close_ratio_min` is a CLOSE/close rule (his text); one
    carrying `gap_pct_min` is an OPEN-gap rule (the shipped detector). `strict`
    picks `>` over `>=` on the price and volume legs; the share leg is always
    `>=` (`v>=300000`).
    """
    w = int(rule["avg_window"])
    strict = bool(rule.get("strict", False))
    vol_mult_min = float(rule["vol_mult_min"])
    min_shares = rule.get("min_shares")
    n = len(c)
    out: list = []
    if n < w + 2:
        return out
    cs = _cumsum(v)
    last = -(10 ** 9)
    for i in range(w + 1, n):
        if i - last < dedup:
            continue
        av = (cs[i] - cs[i - w]) / w
        if av <= 0:
            continue
        pc = float(c[i - 1])
        if pc <= 0:
            continue
        if "close_ratio_min" in rule:
            lhs = float(c[i]) / pc
            rhs = float(rule["close_ratio_min"])
        else:
            lhs = (float(o[i]) - pc) / pc * 100.0
            rhs = float(rule["gap_pct_min"])
        price_ok = (lhs > rhs) if strict else (lhs >= rhs)
        if not price_ok:
            continue
        vm = float(v[i]) / av
        if not ((vm > vol_mult_min) if strict else (vm >= vol_mult_min)):
            continue
        if min_shares is not None and float(v[i]) < float(min_shares):
            continue
        out.append(i)
        last = i
    return out


def events(panel: dict, rule: dict, dedup: int = 5) -> list:
    """Every (symbol, date_iso, bar_index) the rule fires on, over an INJECTED
    panel `{sym: {"o", "c", "v", "dates"}}` (the cached audit pickle's `"d"` key
    is accepted too, so `lane1_published.py` can pass its rows straight
    through). Panel order is preserved — lane1.py's placebo draws depend on it.

    The tuple carries the date AND the bar index: `cells()` needs the date for
    the point-in-time sales state, the caller needs the index for forward
    returns.
    """
    out: list = []
    for sym, bars in panel.items():
        d = bars.get("dates")
        if d is None:
            d = bars["d"]
        for i in detect(bars["o"], bars["c"], bars["v"], rule, dedup=dedup):
            out.append((sym, d[i], i))
    return out


def cells(evts: Sequence[tuple], state_fn: Callable[[str, str], Optional[str]]) -> dict:
    """Split events by the point-in-time Bonde sales state.

    `state_fn(sym, date_iso)` returns `"pass"`, `"fail"` or None (not
    classifiable — no financials, or fewer than five quarters available on that
    date). Returns::

        {"A": [...],            # rule AND sales gate passed
         "B": [...],            # rule, sales gate failed
         "AB": [...],           # the rule ALONE — every event, classified or not
         "unclassified": n}

    An unclassified event is counted and stays in AB (the rule-alone cell is
    fundamentals-independent by definition); it is placed in neither A nor B.
    """
    A: list = []
    B: list = []
    AB: list = []
    unclassified = 0
    for ev in evts:
        sym, dt = ev[0], ev[1]
        AB.append(ev)
        st = state_fn(sym, dt)
        if st is None:
            unclassified += 1
            continue
        if st == "pass":
            A.append(ev)
        elif st == "fail":
            B.append(ev)
        else:
            raise ValueError(f"state_fn returned {st!r}; expected 'pass', 'fail' or None")
    return {"A": A, "B": B, "AB": AB, "unclassified": unclassified}
