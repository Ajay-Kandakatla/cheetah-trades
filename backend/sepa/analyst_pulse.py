"""Analyst Pulse — estimate revisions, price targets, broker actions.

Built 2026-06-12. Encodes TLSW Ch.7 "Analysts' Revisions of Estimates"
(p.124-125) as a per-symbol read on the SEPA cards, with the Ch.5 stage
gating (p.86 "Trust what you see, not what you hear. Tune out the analyst";
p.89 "Brokerage House Opinions": valuation upgrades on broken stocks "turn
out to be good short candidates" — an upgrade on a non-Stage-2 name is a
TRAP signal, never bullish).

What the book actually says (backend/sepa/minervini.pdf, quotes verified
against the PDF 2026-06-12):
  * p.124: "when estimates are revised upward by 5 percent or more, stocks
    tend to show better-than-average performance. Conversely, with downward
    revisions of 5 percent or more, stocks exhibit lower than average
    performance."  -> REVISION_BIG_PCT.
  * p.125: "I like to see the current fiscal year or the next year's
    estimates trending higher from 30 days earlier; if both are trending
    higher, that is even better." / "large downward estimate revisions are
    definitely a red flag." -> TREND_WINDOW_DAYS + the trending_higher /
    red_flag reads.
  * p.121: "the bigger the earnings surprise, the better" — the surprise
    itself is joined from sepa.earnings_watch's cache (no refetch).
  * Ch.4 p.41/p.44 ("Value Comes at a Price" / "High Growth Baffles the
    Analysts"): "what looks expensive or too high may turn out to be the
    next superperformance stock"; "the really great companies are almost
    always going to appear expensive." This is the FRAMING for price
    targets: implied upside vs the mean target is DATA with Ch.4 context,
    NOT a Minervini formula — the UI must not present it as methodology.

HONESTY NOTE: the book does NOT state the lookback window for the p.124
5%-revision study. We compute BOTH 30d and 90d windows and key the big_up /
red_flag badges off 30d (the only window the book names, p.125), with 90d
as separate context (big_up_90d). Stated in
docs/sepa/analyst_pulse_methodology.md.

NOT in the composite score: display + tracking only. sepa/scanner.py never
imports this module (locked in tests/test_sepa_contracts.py).

Source: yfinance (analyst_price_targets / eps_trend / eps_revisions /
upgrades_downgrades) — thin coverage throws per property, so every read is
individually guarded. Cached in Mongo `analyst_pulse` (one doc per symbol),
refreshed by cron weekdays 17:25 ET (`python -m sepa.analyst_pulse refresh`)
+ a stale-kick on the detail endpoint (>18h -> background refresh, stale doc
returned immediately — house pattern from earnings_picks/giants).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import timedelta
from typing import Dict, List, Optional

log = logging.getLogger("sepa.analyst_pulse")

# ── Book constants (TLSW 2013 — see module docstring for the verbatim quotes)
# p.124: estimate revisions of ±5% or more drive above/below-average
# performance. The badge keys off the 30d window (book leaves the study's
# window unstated — documented ambiguity); the 90d window ships as context.
REVISION_BIG_PCT = 5.0
# p.125: current-FY / next-FY estimates "trending higher from 30 days earlier".
TREND_WINDOW_DAYS = 30
# Broker-action lookback — ENGINE PARAM, not a book number (the book gives no
# window for upgrade/target history; 90d keeps the feed recent and small).
ACTIONS_WINDOW_DAYS = 90

_STALE_AFTER_SEC = 18 * 3600    # refresh skips docs fresher than this
_FETCH_SLEEP_SEC = 0.4          # polite pause between yfinance symbols

_LOCK = threading.Lock()
_REFRESH: dict = {"running": False}


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].analyst_pulse
    except Exception:
        return None


def _today_et():
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now().astimezone()


def _f(x) -> Optional[float]:
    """float or None — NaN-safe (yfinance hands back NaN for missing cells)."""
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _i(x) -> Optional[int]:
    """int or None — NaN-safe (revision counts arrive as float cells)."""
    v = _f(x)
    return int(v) if v is not None else None


def _s(x) -> Optional[str]:
    """non-empty str or None — NaN-safe (Firm/grade cells can be NaN)."""
    if x is None or (isinstance(x, float) and x != x):
        return None
    s = str(x).strip()
    return s or None


def rev_pct(cur: Optional[float], base: Optional[float]) -> Optional[float]:
    """Signed-EPS revision % — (cur - base) / abs(base) * 100.

    EPS estimates can be NEGATIVE: a -1.00 -> -0.50 move is an UPWARD
    revision (+50%), but the naive (cur/base - 1) reads it as -50%. Dividing
    the signed delta by abs(base) keeps the direction honest on both sides
    of zero. None when either side is missing or base is 0 (no defined %).
    """
    cur, base = _f(cur), _f(base)
    if cur is None or base is None or base == 0:
        return None
    return (cur - base) / abs(base) * 100.0


# ── Fetch (network — one symbol, every yfinance property guarded) ───────────

_TREND_PERIODS = ("0q", "0y", "+1y")    # current quarter / current FY / next FY


def fetch_one(symbol: str) -> dict:
    """Full analyst doc for one symbol via yfinance. Thin-coverage names
    throw per PROPERTY, so each read is individually try/except'd — missing
    pieces land as None and the doc still ships (never crash a refresh)."""
    sym = (symbol or "").strip().upper()
    doc: dict = {"symbol": sym, "fetched_at": int(time.time()),
                 "targets": None, "eps_trend": None, "rev_counts": None,
                 "actions": [], "error": None}
    errors: List[str] = []
    try:
        import yfinance as yf
        t = yf.Ticker(sym)
    except Exception as exc:
        doc["error"] = "yfinance: %s" % exc
        return doc

    # Price targets — {current, mean, median, high, low}, keys may be missing.
    try:
        pt = t.analyst_price_targets or {}
        targets = {k: _f(pt.get(k))
                   for k in ("mean", "median", "high", "low", "current")}
        doc["targets"] = targets if any(v is not None
                                        for v in targets.values()) else None
    except Exception as exc:
        errors.append("targets: %s" % exc)

    # EPS estimate trend — current vs 30d/90d-ago per period (p.124-125).
    try:
        df = t.eps_trend
        if df is not None and len(df):
            out = {}
            for period in _TREND_PERIODS:
                if period not in df.index:
                    continue
                row = df.loc[period]
                cur = _f(row.get("current"))
                d30 = _f(row.get("30daysAgo"))
                d90 = _f(row.get("90daysAgo"))
                out[period] = {"current": cur, "d30": d30, "d90": d90,
                               "rev_pct_30d": rev_pct(cur, d30),
                               "rev_pct_90d": rev_pct(cur, d90)}
            doc["eps_trend"] = out or None
    except Exception as exc:
        errors.append("eps_trend: %s" % exc)

    # Analyst up/down revision counts per period (context for the chips).
    try:
        df = t.eps_revisions
        if df is not None and len(df):
            out = {}
            for period in _TREND_PERIODS:
                if period not in df.index:
                    continue
                row = df.loc[period]
                out[period] = {"up30": _i(row.get("upLast30days")),
                               "down30": _i(row.get("downLast30days"))}
            doc["rev_counts"] = out or None
    except Exception as exc:
        errors.append("rev_counts: %s" % exc)

    # Broker actions, last ACTIONS_WINDOW_DAYS only, newest-first (p.89 raw
    # material — the trap/bullish call happens in read(), with stage context).
    try:
        df = t.upgrades_downgrades
        if df is not None and len(df):
            cutoff = _today_et().date() - timedelta(days=ACTIONS_WINDOW_DAYS)
            acts = []
            for ts, row in df.iterrows():
                try:
                    if ts.date() < cutoff:
                        continue
                    acts.append({
                        "date": ts.date().isoformat(),
                        "firm": _s(row.get("Firm")),
                        "action": (_s(row.get("Action")) or "").lower() or None,
                        "from_grade": _s(row.get("FromGrade")),
                        "to_grade": _s(row.get("ToGrade")),
                        "prior_pt": _f(row.get("priorPriceTarget")),
                        "new_pt": _f(row.get("currentPriceTarget")),
                    })
                except Exception:
                    continue
            acts.sort(key=lambda a: a["date"], reverse=True)
            doc["actions"] = acts
    except Exception as exc:
        errors.append("actions: %s" % exc)

    doc["error"] = "; ".join(errors) if errors else None
    return doc


# ── The PURE book verdict (no network, no Mongo — fully unit-tested) ────────

def read(doc: Optional[dict], live_price: Optional[float] = None,
         in_uptrend: Optional[bool] = None) -> dict:
    """Book read of a cached analyst doc. PURE — testable on fixtures.

    in_uptrend: True = scan qualifier (confirmed Stage 2 trend, p.79);
    False = in the scan but NOT a qualifier (broken / Stage 3-4 context —
    p.86/89: upgrades and target raises here are a TRAP signal, not
    bullish); None = not in the scan (context unknown, no trap call).
    """
    doc = doc or {}
    et = doc.get("eps_trend") or {}
    fy = et.get("0y") or {}
    nfy = et.get("+1y") or {}
    q = et.get("0q") or {}
    fy30, fy90 = _f(fy.get("rev_pct_30d")), _f(fy.get("rev_pct_90d"))
    nfy30, nfy90 = _f(nfy.get("rev_pct_30d")), _f(nfy.get("rev_pct_90d"))
    q30 = _f(q.get("rev_pct_30d"))

    # p.125: "current fiscal year or the next year's estimates trending
    # higher from 30 days earlier; if both ... even better."
    fy_up = fy30 is not None and fy30 > 0
    nfy_up = nfy30 is not None and nfy30 > 0
    trending = ("both" if fy_up and nfy_up
                else "fy" if fy_up
                else "next_fy" if nfy_up
                else None)

    # p.124 ±5% — badge keyed off the 30d window (book window unstated;
    # see module docstring); 90d ships as separate context.
    big_up = any(v is not None and v >= REVISION_BIG_PCT
                 for v in (fy30, nfy30))
    big_up_90d = any(v is not None and v >= REVISION_BIG_PCT
                     for v in (fy90, nfy90))
    # p.124-125: "large downward estimate revisions are definitely a red flag."
    red_flag = any(v is not None and v <= -REVISION_BIG_PCT
                   for v in (fy30, nfy30))

    # Implied upside vs the mean target — DATA, not a book formula (Ch.4
    # p.41/p.44 framing: analysts systematically underestimate winners).
    implied = None
    mean_target = (doc.get("targets") or {}).get("mean")
    lp = _f(live_price)
    if _f(mean_target) and lp and lp > 0:
        implied = round((_f(mean_target) / lp - 1) * 100.0, 2)

    raises = cuts = ups = downs = 0
    for a in doc.get("actions") or []:
        pp, np_ = _f(a.get("prior_pt")), _f(a.get("new_pt"))
        if pp is not None and np_ is not None:
            if np_ > pp:
                raises += 1
            elif np_ < pp:
                cuts += 1
        act = (a.get("action") or "").lower()
        if act == "up":
            ups += 1
        elif act == "down":
            downs += 1

    # p.89: upgrades/target raises on a NON-uptrend name are often
    # valuation calls on a broken chart — "good short candidates."
    context = ("unknown" if in_uptrend is None
               else "uptrend" if in_uptrend else "broken")
    p89_trap = (in_uptrend is False) and (ups + raises > 0)

    # p.86 "trust what you see, not what you hear. Tune out the analyst":
    # bullish VERDICTS never fire on a broken (non-Stage-2) name, even when
    # the estimate data alone looks bullish and no broker action tripped the
    # p.89 trap. The raw big_up / trending fields still ship as data — only
    # the call is gated. 'unknown' (not in the scan) keeps the bullish read.
    bullish_ok = in_uptrend is not False

    if red_flag:                      # red_flag beats everything, incl. trap
        verdict = "red_flag"
    elif p89_trap:                    # trap beats any bullish read
        verdict = "p89_trap"
    elif big_up and bullish_ok:
        verdict = "revisions_up_big"
    elif trending and bullish_ok:
        verdict = "trending_higher"
    else:
        verdict = "neutral"

    return {
        "fy_rev_30d": fy30, "next_fy_rev_30d": nfy30,
        "fy_rev_90d": fy90, "next_fy_rev_90d": nfy90,
        "q_rev_30d": q30,
        "trending_higher": trending,
        "big_up": big_up, "big_up_90d": big_up_90d,
        "red_flag": red_flag,
        "implied_upside_pct": implied,
        "target_raises_90d": raises, "target_cuts_90d": cuts,
        "upgrades_90d": ups, "downgrades_90d": downs,
        "p89_trap": p89_trap,
        "context": context,
        "verdict": verdict,
    }


# ── Universe + uptrend context (cached scan + Mongo, no network) ────────────

def _universe() -> List[str]:
    """Decision universe: latest-scan qualifiers + buyables + portfolio
    holdings + watchlist tickers (dedup). Mirrors earnings_watch but keeps
    only scan names worth an analyst read (qualifier/buyable), not all 6k."""
    syms: set = set()
    try:
        from . import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            if not r.get("symbol"):
                continue
            if r.get("qualifier") or r.get("is_candidate") or r.get("is_buyable"):
                syms.add(r["symbol"].upper())
    except Exception as exc:
        log.debug("universe: scan rows unavailable: %s", exc)
    try:
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                         serverSelectionTimeoutMS=2000)[os.getenv("MONGO_DB", "cheetah")]
        for d in db.portfolio_holdings.find({}, {"ticker": 1, "symbol": 1}):
            s = (d.get("ticker") or d.get("symbol") or "").upper()
            if s:
                syms.add(s)
        for d in db.watchlist.find({}, {"ticker": 1}):
            if d.get("ticker"):
                syms.add(d["ticker"].upper())
    except Exception as exc:
        log.debug("universe: holdings/watchlist unavailable: %s", exc)
    return sorted(syms)


def _uptrend_map() -> Dict[str, bool]:
    """{SYM: qualifier?} from the cached latest scan. In the map = the scan
    analyzed it (True -> confirmed uptrend, False -> broken/non-Stage-2);
    absent = unknown context (read() then never calls the p.89 trap)."""
    out: Dict[str, bool] = {}
    try:
        from . import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            s = (r.get("symbol") or "").upper()
            if s:
                out[s] = bool(r.get("qualifier") or r.get("is_candidate"))
    except Exception as exc:
        log.debug("uptrend map: scan rows unavailable: %s", exc)
    return out


# ── Store / refresh / serve ─────────────────────────────────────────────────

def refresh(symbols: Optional[List[str]] = None, force: bool = False) -> dict:
    """Fetch/update analyst docs for the decision universe. Sequential with
    a polite _FETCH_SLEEP_SEC pause (Yahoo rate-limits bursts); skips docs
    fresher than 18h unless force. Returns counts."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    syms = [s.upper() for s in (symbols or _universe())]
    now = int(time.time())

    existing = {d["_id"]: d for d in coll.find({"_id": {"$in": syms}})}
    todo = [s for s in syms
            if force
            or s not in existing
            or now - (existing[s].get("fetched_at") or 0) > _STALE_AFTER_SEC]

    fetched = with_errors = 0
    for i, sym in enumerate(todo):
        doc = fetch_one(sym)
        try:
            coll.replace_one({"_id": sym}, {"_id": sym, **doc}, upsert=True)
            fetched += 1
            if doc.get("error"):
                with_errors += 1
        except Exception as exc:
            log.debug("analyst upsert failed %s: %s", sym, exc)
        if i < len(todo) - 1:
            time.sleep(_FETCH_SLEEP_SEC)

    log.info("analyst_pulse: universe=%d refreshed=%d skipped_fresh=%d errors=%d",
             len(syms), fetched, len(syms) - len(todo), with_errors)
    return {"ok": True, "universe": len(syms), "refreshed": fetched,
            "skipped_fresh": len(syms) - len(todo), "with_errors": with_errors}


def _bulk_live(symbols: List[str]) -> dict:
    """ONE batched live-quote call (sepa.prices.bulk_live_prices)."""
    if not symbols:
        return {}
    try:
        from .prices import bulk_live_prices
        return bulk_live_prices(list(symbols)) or {}
    except Exception as exc:
        log.warning("analyst_pulse: bulk live prices failed: %s", exc)
        return {}


def _live_px(q: dict) -> Optional[float]:
    """Best available price from a bulk_live_prices entry — regular close,
    else extended-hours print, else previous close (closed-market UX)."""
    return _f(q.get("price") or q.get("last_trade_price")
              or q.get("prev_day_close"))


def get_map(symbols: List[str]) -> dict:
    """Slim per-symbol read for the cards — CACHED docs only (no fetch).
    read() runs at request time against ONE bulk live-price call + the
    cached scan's qualifier context, so the verdict tracks today's tape."""
    syms = []
    for s in symbols or []:
        s = (s or "").strip().upper()
        if s and s not in syms:
            syms.append(s)
    coll = _coll()
    if coll is None:
        return {"ok": False, "map": {}, "n": 0}
    docs = {}
    try:
        docs = {d["_id"]: d for d in coll.find({"_id": {"$in": syms}})}
    except Exception as exc:
        log.warning("analyst map read failed: %s", exc)
    live = _bulk_live(sorted(docs)) if docs else {}
    up = _uptrend_map() if docs else {}

    out: Dict[str, dict] = {}
    for sym, doc in docs.items():
        r = read(doc, _live_px(live.get(sym) or {}), up.get(sym))
        out[sym] = {"verdict": r["verdict"],
                    "implied_upside_pct": r["implied_upside_pct"],
                    "fy_rev_30d": r["fy_rev_30d"],
                    "trending_higher": r["trending_higher"],
                    "big_up": r["big_up"],
                    "red_flag": r["red_flag"],
                    "p89_trap": r["p89_trap"],
                    "n_actions": len(doc.get("actions") or []),
                    "mean_target": (doc.get("targets") or {}).get("mean")}
    return {"ok": True, "map": out, "n": len(out),
            "source": "yfinance (Yahoo Finance) analyst data, cached <=18h",
            "note": ("Display + tracking only — never feeds the composite "
                     "score. Implied upside is DATA, not Minervini "
                     "methodology (Ch.4 p.41/p.44). Upgrades on non-Stage-2 "
                     "names are the p.89 trap signal, not bullish.")}


def get_detail(symbol: str) -> dict:
    """Full doc + book read + last-report surprise join for the drill modal.
    Stale (>18h) kicks ONE background refresh of this symbol and returns
    the cached doc immediately (house pattern: earnings_picks/giants)."""
    sym = (symbol or "").strip().upper()
    coll = _coll()
    doc = None
    if coll is not None:
        try:
            doc = coll.find_one({"_id": sym})
        except Exception:
            doc = None
    stale = (doc is None
             or int(time.time()) - (doc.get("fetched_at") or 0) > _STALE_AFTER_SEC)
    if stale:
        with _LOCK:
            if not _REFRESH["running"]:
                _REFRESH["running"] = True

                def run():
                    try:
                        refresh([sym], force=True)
                    finally:
                        _REFRESH["running"] = False
                threading.Thread(target=run, name="analyst-pulse",
                                 daemon=True).start()

    up = _uptrend_map()
    in_uptrend = up.get(sym)
    context_payload = {
        "ok": True, "symbol": sym, "stale": stale,
        "refreshing": _REFRESH["running"],
        "in_uptrend": in_uptrend,
        "source": "yfinance (Yahoo Finance) analyst data",
        "note": ("Estimate revisions per TLSW p.124-125; broker actions are "
                 "p.89-gated by trend context; price targets are DATA, not "
                 "book methodology (Ch.4 p.41/p.44). Not in the composite "
                 "score. Not advice."),
    }
    if doc is None:
        context_payload.update(doc=None, read=read(None, None, in_uptrend),
                               last_report=None)
        return context_payload

    doc.pop("_id", None)
    live = _bulk_live([sym])
    live_price = _live_px(live.get(sym) or {})

    # p.121-123 surprise context — join earnings_watch's cache, no refetch.
    last_report = None
    try:
        from . import earnings_watch
        ec = earnings_watch._coll()
        if ec is not None:
            last_report = (ec.find_one({"_id": sym}) or {}).get("last_report")
    except Exception as exc:
        log.debug("analyst detail: last_report join failed %s: %s", sym, exc)

    context_payload.update(doc=doc, live_price=live_price,
                           read=read(doc, live_price, in_uptrend),
                           last_report=last_report)
    return context_payload


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = sys.argv[1:]
    if not args or args[0] == "refresh":
        r = refresh(force="--force" in args)
        log.info("ANALYST-PULSE: %s", r)
        sys.exit(0 if r.get("ok") else 1)
    print("usage: python -m sepa.analyst_pulse refresh [--force]")
    sys.exit(2)
