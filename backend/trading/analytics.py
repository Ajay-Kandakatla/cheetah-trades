"""Auto-Pilot trade ANALYTICS — Minervini's OWN prescription, reported over
the closed round-trips in trade_journal. These are DESCRIPTIVE statistics
(they report the book's metrics on Ajay's real fills); they are NOT new gating
formulas and they change no trading logic.

Every metric traces to a printed page of Minervini, *Trade Like a Stock Market
Wizard* (2013), Chapter 13 (backend/sepa/minervini.pdf, printed page = PDF page
- 15):

  p.298  batting average = winners / closed trades ("correct on winning trades
         only about 50 percent of the time"); a positive mathematical
         expectation is required ("your reward/risk ratio must be greater than
         one to one"); the Buffett expectancy quote.
  p.299  average gain (winners) and average loss (losers); cut losses at
         one-half the average gain ("15 percent on average -> 7.5 percent");
         the CARDINAL SIN — never let a loss grow larger than your average
         gain ("how can you be profitable if your losses are bigger than your
         gains?").
  p.301  win/loss ratio target: "at least a 2:1 win/loss ratio ... I shoot
         for 3:1."

Derived here, all guarding n=0:
  * win_loss_ratio   = avg_gain_pct / avg_loss_pct      (p.301 target >= 2.0)
  * expectancy_pct   = batting*avg_gain_pct - (1-batting)*avg_loss_pct  (p.298)
  * expectancy_dollars = avg per-trade realized P&L in $
  * avg_r            = mean realized R multiple (gain_pct / initial stop_pct)
  * half_avg_gain_stop_pct = avg_gain_pct / 2, capped 10 (p.299) — the same
    quantity risk_rules.initial_stop consumes once there are >= 20 closed
    trades; surfaced here as "your data says your stop should be X%".

SMALL SAMPLE: under 10 closed trades every ratio is flagged provisional
(n=X) — consistent with the app's existing MIN_RECORD_N=10 convention in
sepa/chart_analysis.py. A batting average / expectancy on a handful of trades
is noise and must not be presented as reliable.

Pure compute: no I/O, no Mongo, no broker, no pandas. compute() takes the
closed journal docs (+ optional open marks) and returns a JSON-ready dict; it
never raises on empty input.
"""
from __future__ import annotations

# Book numbers (page-cited above). LOCKED in tests/test_trading_contracts.py.
TARGET_RATIO = 2.0        # p.301 "at least a 2:1 win/loss ratio"
STRETCH_RATIO = 3.0       # p.301 "I shoot for 3:1"
BATTING_REF = 0.5         # p.298 "about 50 percent of the time"
HALF_AVG_GAIN_CAP = 10.0  # p.299 "not allow any stock to fall more than 10%"
# Small-sample floor — mirrors sepa/chart_analysis.py MIN_RECORD_N.
MIN_RECORD_N = 10


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _r2(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


def _r4(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return 0.0


def _gain_pct(trade):
    return (trade.get("realized") or {}).get("gain_pct")


def _gain_dollars(trade):
    return (trade.get("realized") or {}).get("gain_dollars")


def _r_multiple(trade):
    return (trade.get("realized") or {}).get("r_multiple")


def _holding_days(trade):
    return (trade.get("realized") or {}).get("holding_days")


def _trigger_path(trade):
    """intraday | close_confirm | manual (a closed trade's entry trigger)."""
    trig = (trade.get("entry") or {}).get("trigger")
    if not trig or not trig.get("path"):
        return "manual"
    p = trig.get("path")
    return p if p in ("intraday", "close_confirm") else "manual"


def _source(trade):
    """sim | paper | live — the venue this fill happened on. Fills predating
    the Alpaca cutover carry no `mode` (the journal only began stamping it
    then); every one of those was the sim, so None -> 'sim'."""
    mode = (trade.get("entry") or {}).get("mode")
    m = str(mode).lower() if mode else "sim"
    return m if m in ("sim", "paper", "live") else "sim"


def _empty():
    """Zeroed shape returned on empty input (no exceptions, ever)."""
    return {
        "n_closed": 0, "n_open": 0, "provisional": True,
        "batting_avg": 0.0, "avg_gain_pct": 0.0, "avg_loss_pct": 0.0,
        "win_loss_ratio": 0.0, "expectancy_pct": 0.0,
        "expectancy_dollars": 0.0, "avg_r": 0.0,
        "total_pnl_dollars": 0.0, "total_pnl_pct_on_risk": 0.0,
        "best": None, "worst": None, "avg_holding_days": 0.0,
        "equity_curve": [], "by_trigger": {}, "by_source": {},
        "open_risk_dollars": 0.0,
        "vs_book": {
            "target_ratio": TARGET_RATIO, "stretch_ratio": STRETCH_RATIO,
            "your_ratio": 0.0, "batting_ref": BATTING_REF,
            "half_avg_gain_stop_pct": 0.0, "flags": [],
        },
    }


def _subset_stats(trades):
    """Batting / avg gain / avg loss / win-loss / expectancy / avg-R for a
    subset (used both overall and per-trigger). Guards every divide."""
    gains = [g for g in (_gain_pct(t) for t in trades) if g is not None]
    n = len(gains)
    if n == 0:
        return {"n": 0, "batting_avg": 0.0, "avg_gain_pct": 0.0,
                "avg_loss_pct": 0.0, "win_loss_ratio": 0.0,
                "expectancy_pct": 0.0, "avg_r": 0.0}
    winners = [g for g in gains if g > 0]
    losers = [g for g in gains if g <= 0]
    batting = len(winners) / n
    avg_gain = _mean(winners)                       # p.299 average gain
    avg_loss = abs(_mean(losers))                   # p.299 average loss (mag)
    wl = (avg_gain / avg_loss) if avg_loss > 0 else 0.0
    # p.298 expectancy: batting*avg_gain - (1-batting)*avg_loss.
    expectancy = batting * avg_gain - (1 - batting) * avg_loss
    rs = [r for r in (_r_multiple(t) for t in trades) if r is not None]
    return {
        "n": n,
        "batting_avg": _r4(batting),
        "avg_gain_pct": _r2(avg_gain),
        "avg_loss_pct": _r2(avg_loss),
        "win_loss_ratio": _r2(wl),
        "expectancy_pct": _r2(expectancy),
        "avg_r": _r2(_mean(rs)) if rs else 0.0,
    }


def _flags(avg_gain, avg_loss, wl, n):
    """Page-cited red flags. Empty list = nothing wrong (or nothing yet)."""
    flags = []
    if n == 0:
        return flags
    # The cardinal sin (p.299): average loss exceeds average gain.
    if avg_loss > avg_gain and avg_gain >= 0:
        flags.append(
            "Average loss %.1f%% exceeds average gain %.1f%% — the cardinal "
            "sin (TLSW p.299)" % (avg_loss, avg_gain))
    # Win/loss below the 2:1 floor (p.301). Only meaningful once both legs
    # have data (a positive avg_loss).
    if avg_loss > 0 and 0 < wl < TARGET_RATIO:
        flags.append(
            "Win/loss %.1f:1 is below the 2:1 floor (TLSW p.301)" % wl)
    return flags


def compute(trades, open_marks=None) -> dict:
    """Compute the book analytics over CLOSED journal docs.

    trades      : iterable of closed trade_journal docs (realized populated).
    open_marks  : optional list of {qty, last, stop, entry_price?} for OPEN
                  positions, used only for open_risk_dollars (the still-at-risk
                  amount = sum qty*(last-stop) when last > stop). Open trades do
                  NOT enter the batting/expectancy math — those are realized
                  only — keeping the analytics historical/pure.

    Never raises on empty input: returns a zeroed shape with provisional=True.
    """
    trades = [t for t in (trades or []) if _gain_pct(t) is not None]
    open_marks = list(open_marks or [])
    if not trades:
        out = _empty()
        out["n_open"] = len(open_marks)
        out["open_risk_dollars"] = _open_risk(open_marks)
        return out

    n_closed = len(trades)
    stats = _subset_stats(trades)
    avg_gain = stats["avg_gain_pct"]
    avg_loss = stats["avg_loss_pct"]
    wl = stats["win_loss_ratio"]

    # Dollar totals + expectancy in $.
    pnl_dollars = [d for d in (_gain_dollars(t) for t in trades) if d is not None]
    total_pnl = round(sum(pnl_dollars), 2)
    expectancy_dollars = _r2(_mean(pnl_dollars)) if pnl_dollars else 0.0

    # Total P&L as % on risk = sum of realized R multiples (each trade's gain
    # measured in units of its own initial stop, p.299 R).
    rs = [r for r in (_r_multiple(t) for t in trades) if r is not None]
    total_pnl_pct_on_risk = _r2(sum(rs))

    # Holding period.
    holds = [h for h in (_holding_days(t) for t in trades) if h is not None]
    avg_hold = _r2(_mean(holds)) if holds else 0.0

    # Best / worst by gain_pct.
    best_t = max(trades, key=lambda t: _gain_pct(t))
    worst_t = min(trades, key=lambda t: _gain_pct(t))
    best = {"trade_id": best_t.get("trade_id"), "symbol": best_t.get("symbol"),
            "gain_pct": _r2(_gain_pct(best_t))}
    worst = {"trade_id": worst_t.get("trade_id"),
             "symbol": worst_t.get("symbol"),
             "gain_pct": _r2(_gain_pct(worst_t))}

    # Equity curve = cumulative realized P&L over closed trades in time order.
    ordered = sorted(
        trades,
        key=lambda t: (t.get("exit") or {}).get("epoch")
        or (t.get("entry") or {}).get("epoch") or 0.0)
    curve = []
    cum = 0.0
    for t in ordered:
        d = _gain_dollars(t)
        if d is not None:
            cum += d
        epoch = (t.get("exit") or {}).get("epoch") \
            or (t.get("entry") or {}).get("epoch") or 0.0
        curve.append({"epoch": epoch, "cum_pnl_dollars": round(cum, 2)})

    # By trigger path.
    by_trigger = {}
    buckets = {"intraday": [], "close_confirm": [], "manual": []}
    for t in trades:
        buckets[_trigger_path(t)].append(t)
    for path, group in buckets.items():
        s = _subset_stats(group)
        if s["n"]:
            by_trigger[path] = s

    # By source venue (sim vs live paper). The combined stats above stay the
    # CONTINUOUS track record across the sim -> paper cutover; this split lets
    # the dashboard watch the live-paper batting average accrue in parallel.
    by_source = {}
    src_buckets = {}
    for t in trades:
        src_buckets.setdefault(_source(t), []).append(t)
    for src, group in src_buckets.items():
        s = _subset_stats(group)
        if s["n"]:
            by_source[src] = s

    # half-average-gain stop (p.299), capped 10.
    half_stop = min(round(avg_gain / 2.0, 2), HALF_AVG_GAIN_CAP) if avg_gain > 0 else 0.0

    flags = _flags(avg_gain, avg_loss, wl, n_closed)

    out = {
        "n_closed": n_closed,
        "n_open": len(open_marks),
        "provisional": n_closed < MIN_RECORD_N,
        "batting_avg": stats["batting_avg"],
        "avg_gain_pct": avg_gain,
        "avg_loss_pct": avg_loss,
        "win_loss_ratio": wl,
        "expectancy_pct": stats["expectancy_pct"],
        "expectancy_dollars": expectancy_dollars,
        "avg_r": stats["avg_r"],
        "total_pnl_dollars": total_pnl,
        "total_pnl_pct_on_risk": total_pnl_pct_on_risk,
        "best": best,
        "worst": worst,
        "avg_holding_days": avg_hold,
        "equity_curve": curve,
        "by_trigger": by_trigger,
        "by_source": by_source,
        "open_risk_dollars": _open_risk(open_marks),
        "vs_book": {
            "target_ratio": TARGET_RATIO,
            "stretch_ratio": STRETCH_RATIO,
            "your_ratio": wl,
            "batting_ref": BATTING_REF,
            "half_avg_gain_stop_pct": half_stop,
            "flags": flags,
        },
    }
    return out


def _open_risk(open_marks) -> float:
    """Still-at-risk dollars on OPEN positions: sum qty*(last-stop) when
    last > stop (the amount that would be lost if every open stop filled now;
    a stop ratcheted above last contributes 0, not a negative)."""
    total = 0.0
    for m in open_marks or []:
        try:
            qty = float(m.get("qty") or 0)
            last = float(m.get("last") or 0)
            stop = float(m.get("stop") or 0)
        except (TypeError, ValueError):
            continue
        if qty > 0 and last > stop > 0:
            total += qty * (last - stop)
    return round(total, 2)
