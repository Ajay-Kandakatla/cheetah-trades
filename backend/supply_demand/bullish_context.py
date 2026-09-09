"""Things to SEE beside a demand-zone push — GEX, bullish patterns, sentiment.

Ajay 2026-09-09: "I need them to be looking at GEX and other bullish patterns to
see and also most recent sentiment", then "add on more things to see which ones
are bullish".

WHY THIS IS ITS OWN MODULE. `alert_gates` is a LEAF by contract — it imports
nothing but math and typing, and test_supply_demand_contracts pins that. Nothing
in here is a gate, so nothing in here belongs there, and keeping them apart makes
"context can never block a push" a fact about the import graph instead of a
promise in a docstring. The gate module cannot see this module.

Configured price-structure and third-party reads, S/D scope. No Minervini cites,
not advice.
"""
from __future__ import annotations

from typing import Optional


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


# THINGS TO SEE — Ajay 2026-09-09: "I need them to be looking at GEX and other
# bullish patterns to see and also most recent sentiment", then "add on more
# things to see which ones are bullish".
#
# These RIDE ALONG. They never block a push. That is not timidity — it is what
# his own ledger says. pattern_observations holds 760 resolved chart-pattern
# observations and NOT ONE of them beats the placebo over 21 sessions:
#
#     cup_with_handle          n=434   45% up   -0.12%
#     double_bottom            n=248   43% up   +0.35%
#     triple_bottom            n= 68   37% up   -0.98%
#     inverse_head_shoulders   n= 10   10% up   -4.78%
#     PLACEBO (all resolved)   n=659   50% up   -0.10%
#
# Gating on those would make the signal WORSE, which is the opposite of the ask.
# So every measured rate is printed beside its placebo and the reader decides.
# If one of these later separates on a real sample it can be promoted to a gate
# — with his sign-off, never on my own (the S&D research loop).
#
# flat_top is EXCLUDED outright: it fired on 120 of 120 random names. A pattern
# present on everything carries no information and would read as confirmation.

# Fires on 100% of names (measured, 120-name random sample) — noise, not evidence.
NOISE_PATTERNS = ("flat_top",)

# His ledger's measured 21-session record, for printing beside the name.
# n / % that closed up / mean forward %. Placebo: n=659, 50% up, -0.10%.
PATTERN_RECORD = {
    "cup_with_handle":        (434, 45, -0.12),
    "double_bottom":          (248, 43, +0.35),
    "triple_bottom":          (68, 37, -0.98),
    "inverse_head_shoulders": (10, 10, -4.78),
}
PATTERN_PLACEBO = (659, 50, -0.10)

_CTX_TTL = 900.0                 # seconds; zone_edge runs every minute
_CTX_CACHE: dict = {}


def gex_bullish_read(symbol) -> Optional[dict]:
    """The GEX board's own bullish/bearish/mixed read for this name, or None.

    Reuses options.gex_history.board_bucket verbatim rather than restating what
    the regime means: bullish = dealers net LONG gamma (pinning) with spot at or
    above the flip — dips get bought, moves dampened. bearish = net SHORT gamma
    (amplifying) below the flip — weakness gets amplified, which is the CASY
    shape. The ledger is written post-close, so the row is always a PRIOR
    session's and the date rides along; it is never same-day lookahead.

    Coverage is thin by construction (the snapshot walks ~200 names a day), so
    a missing row is normal and means nothing either way."""
    try:
        from options import gex_history as gh
        rows = gh.snapshot_for([str(symbol).upper()], max_age_days=7) or {}
        row = rows.get(str(symbol).upper())
        if not isinstance(row, dict):
            return None
        return {"read": gh.board_bucket(row), "date": row.get("date_et"),
                "regime": row.get("regime"), "spot": row.get("spot"),
                "put_wall": row.get("put_wall"), "call_wall": row.get("call_wall"),
                "net_gex": row.get("net_gex_dollars"),
                "reliability": row.get("reliability")}
    except Exception:                                # noqa: BLE001
        return None


def bullish_patterns_read(symbol, frame=None) -> Optional[list]:
    """Named bullish patterns on the daily frame, noise excluded, each carrying
    his ledger's measured record. [] = none found, None = could not look."""
    try:
        from patterns import timeframe as pt
        out = pt.scan(str(symbol).upper(), "daily", df=frame) or {}
        found = []
        for p in (out.get("patterns") or []):
            name = p.get("kind") or p.get("name")
            if not name or name in NOISE_PATTERNS:
                continue
            rec = PATTERN_RECORD.get(name)
            found.append({"name": name,
                          "record": {"n": rec[0], "up_pct": rec[1], "mean_pct": rec[2]}
                          if rec else None})
        return found
    except Exception:                                # noqa: BLE001
        return None


def sentiment_read(symbol) -> Optional[dict]:
    """Most recent retail sentiment: % of tagged StockTwits messages that are
    bullish, and how many landed in 24h. None when the feed is unavailable —
    an outage must never read as "0 chatter"."""
    try:
        from catalysts import chatter
        st = ((chatter.get_chatter(str(symbol).upper()) or {}).get("stocktwits")) or {}
        pct = st.get("sentiment_pct_bullish")
        if pct is None:
            return None
        return {"pct_bullish": int(pct), "n_24h": int(st.get("n_24h") or 0),
                "n_bullish": int(st.get("n_bullish") or 0),
                "n_bearish": int(st.get("n_bearish") or 0)}
    except Exception:                                # noqa: BLE001
        return None


def bullish_context(symbol, frame=None, with_sentiment: bool = True) -> dict:
    """Everything he asked to SEE beside a push, in one call. Never raises,
    never blocks, cached briefly because zone_edge runs every minute.

    `with_sentiment=False` skips the only network hop, for callers on a tight
    per-minute budget."""
    import time as _t
    key = (str(symbol).upper(), bool(with_sentiment))
    hit = _CTX_CACHE.get(key)
    if hit and (_t.time() - hit[0]) < _CTX_TTL:
        return hit[1]
    ctx = {"gex": gex_bullish_read(symbol),
           "patterns": bullish_patterns_read(symbol, frame),
           "sentiment": sentiment_read(symbol) if with_sentiment else None}
    _CTX_CACHE[key] = (_t.time(), ctx)
    return ctx


def context_txt(ctx: Optional[dict]) -> str:
    """The see-it fragment for a push body. "" when nothing can be said.

    e.g. "GEX bullish (pinning, 09-08) · double_bottom (43% up vs 50% placebo)
          · 71% bullish on 128 msgs" """
    if not isinstance(ctx, dict):
        return ""
    bits = []
    g = ctx.get("gex")
    if isinstance(g, dict) and g.get("read"):
        wall = f", put wall ${g['put_wall']:g}" if _f(g.get("put_wall")) else ""
        bits.append(f"GEX {g['read']} ({g.get('regime') or '?'}{wall}, {g.get('date') or '?'})")
    pats = ctx.get("patterns")
    if pats:
        for p in pats[:2]:
            rec = p.get("record")
            if rec:
                bits.append("%s (%d%% up vs %d%% placebo, n=%d)"
                            % (p["name"], rec["up_pct"], PATTERN_PLACEBO[1], rec["n"]))
            else:
                bits.append(str(p["name"]))
    s = ctx.get("sentiment")
    if isinstance(s, dict) and s.get("pct_bullish") is not None:
        bits.append("%d%% bullish on %d msgs/24h" % (s["pct_bullish"], s.get("n_24h") or 0))
    return " · ".join(bits)
