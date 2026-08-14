"""Does retail order imbalance predict anything? — walk-forward test.

Ajay 2026-08-14, after noticing SWKS fell 1.2% on a session whose flow read
buy-side: "lets [test] it before you lean on this at all."

Right instinct. `orderflow/retail.py` is a MEASUREMENT — it says which side
retail was on. Whether that is worth money is a separate question, and every
other thing measured this week (the sweep strategy, demand-zone re-entry,
per-name bounce persistence) came back at or near zero. The null hypothesis
here is live and this test is built to be able to fail.

WHAT IT TESTS
-------------
For each (symbol, day): identify retail flow from that day's COMPLETE tape,
sign it on the quote midpoint, then measure the forward return from that day's
CLOSE. The tape for day D is finished at D's close, so entering at that close
uses nothing unknowable — no lookahead.

Two competing priors, and the test can distinguish them:
  * BJZZ (2021) reported retail imbalance POSITIVELY predicts next-week returns.
  * The folk view is that retail is the wrong-way side (buying into
    distribution), which would give a NEGATIVE relationship.
  * Barber et al. (2024) undercut both by showing the original signing
    mis-signs 28% of trades — we use their midpoint fix, so this is a cleaner
    test of the same question than BJZZ ran.

COST
----
One tape fetch plus one NBBO fetch per symbol-day (~6s), so this is scoped by
construction rather than run over everything. Read `n` before the effect size.

Not advice. A measured relationship on a few hundred symbol-days is a hint,
not an edge.
"""
from __future__ import annotations

import logging
from datetime import date as _date, timedelta
from typing import Optional

log = logging.getLogger("orderflow.retail_backtest")

HORIZONS = (1, 3, 5)
MIN_RETAIL_TRADES = 50       # below this the imbalance is noise (retail.py's floor)


def _forward_returns(closes: list, dates: list, day: _date) -> dict:
    """Close-to-close returns from `day` forward. PURE."""
    try:
        i = dates.index(day)
    except ValueError:
        return {}
    base = float(closes[i])
    if base <= 0:
        return {}
    out = {}
    for h in HORIZONS:
        j = i + h
        out[f"fwd_{h}d"] = round((float(closes[j]) / base - 1) * 100, 3) if j < len(closes) else None
    return out


def run(symbols: list, days_back: int = 15, end: Optional[_date] = None) -> dict:
    """Collect (retail imbalance, forward return) pairs and score them."""
    from sepa import prices
    from . import quotes as quotes_mod, retail as retail_mod, tape as tape_mod

    end = end or (_date.today() - timedelta(days=1))
    obs, skipped = [], 0

    for sym in symbols:
        df = None
        try:
            df = prices.load_prices(sym, period="2y")
        except Exception:
            pass
        if df is None or len(df) < 60:
            skipped += 1
            continue
        df = df.rename(columns={c: str(c).lower() for c in df.columns})
        closes = [float(c) for c in df["close"]]
        dates = [d.date() if hasattr(d, "date") else d for d in df.index]

        day = end
        checked = 0
        while checked < days_back and day > end - timedelta(days=days_back * 3):
            if day.weekday() < 5 and day in dates:
                checked += 1
                try:
                    tr = tape_mod.fetch_trades(sym, day)
                    qt = quotes_mod.fetch_quotes(sym, day)
                    r = retail_mod.identify(tr, qt)
                except Exception as exc:
                    log.debug("retail-bt: %s %s failed: %s", sym, day, exc)
                    r = None
                if (r and r.get("signed") and r.get("imbalance_pct") is not None
                        and r.get("retail_trades", 0) >= MIN_RETAIL_TRADES):
                    fwd = _forward_returns(closes, dates, day)
                    if fwd.get(f"fwd_{HORIZONS[-1]}d") is not None:
                        obs.append({"symbol": sym, "day": str(day),
                                    "imbalance": r["imbalance_pct"],
                                    "retail_pct": r.get("retail_pct_of_volume"),
                                    **fwd})
            day -= timedelta(days=1)

    return {"observations": obs, "n": len(obs), "symbols": len(symbols),
            "skipped": skipped, "summary": summarize(obs)}


def summarize(obs: list) -> dict:
    """Quintile spread + rank correlation per horizon.

    Quintiles rather than a raw correlation because the relationship need not
    be linear, and the tradeable question is "does the top group beat the
    bottom group", not "is there a slope"."""
    if len(obs) < 25:
        return {"verdict": "too few observations to score", "n": len(obs)}

    ranked = sorted(obs, key=lambda o: o["imbalance"])
    q = max(1, len(ranked) // 5)
    bottom, top = ranked[:q], ranked[-q:]

    out = {"n": len(obs), "quintile_size": q, "horizons": {}}
    for h in HORIZONS:
        k = f"fwd_{h}d"
        tv = [o[k] for o in top if o.get(k) is not None]
        bv = [o[k] for o in bottom if o.get(k) is not None]
        if not tv or not bv:
            continue
        t_avg, b_avg = sum(tv) / len(tv), sum(bv) / len(bv)

        # Spearman on ranks (no scipy in this image).
        pairs = [(o["imbalance"], o[k]) for o in obs if o.get(k) is not None]
        n = len(pairs)
        r1 = {id(p): i for i, p in enumerate(sorted(pairs, key=lambda p: p[0]))}
        r2 = {id(p): i for i, p in enumerate(sorted(pairs, key=lambda p: p[1]))}
        d2 = sum((r1[id(p)] - r2[id(p)]) ** 2 for p in pairs)
        rho = round(1 - (6 * d2) / (n * (n * n - 1)), 3) if n > 2 else None

        out["horizons"][f"{h}d"] = {
            "top_quintile_avg_pct": round(t_avg, 3),      # most retail BUYING
            "bottom_quintile_avg_pct": round(b_avg, 3),   # most retail SELLING
            "spread_pct": round(t_avg - b_avg, 3),
            "rank_correlation": rho,
            "all_avg_pct": round(sum(v for _, v in pairs) / n, 3),
        }

    spreads = [v["spread_pct"] for v in out["horizons"].values()]
    rhos = [v["rank_correlation"] or 0 for v in out["horizons"].values()]
    consistent = all(s > 0 for s in spreads) or all(s < 0 for s in spreads)
    strong = any(abs(s) >= 0.5 for s in spreads) and any(abs(r) >= 0.1 for r in rhos)
    out["verdict"] = ("predictive — consistent sign across horizons" if consistent and strong
                      else "no usable signal — spreads are small and/or flip sign by horizon")
    return out
