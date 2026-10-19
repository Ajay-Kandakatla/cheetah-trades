"""🌙 Overnight session read (BUILD_SPEC16 §3.2, 2026-10-19) — the engine.

Ajay 2026-10-19: "Can you do an over night scan for all the stocks they are all
growing over night" — "Massive is what we use probably we don't have the
subscription". Massive carries no overnight prints (probe 2026-10-19), so:

  * BASE = the last regular close from the ONE whole-market engine
    `sepa.prices.market_snapshot_with_meta()` (`close` = `day.c`), pinned ONCE
    per session at its first pass (doc `overnight_base`) and never re-pulled:
    the snapshot resets ~03:30 ET. Prior-session % = `close / prev_day_close`,
    never `todaysChangePerc` (it carries after-hours prints, measured).
  * NOW = Alpaca `feed=overnight` snapshots in batches of 200 (AMENDMENTS16 A1):
    the live bid/ask midpoint when the quote printed this session, is at most
    QUOTE_FRESH_SEC old and its spread is at most QUOTE_SPREAD_MAX of the mid
    (src "q"); else the latest overnight trade if it printed this session
    (src "t" — Alpaca's indicative Blue Ocean prints, delayed ~15 minutes,
    measured 900–1,044 s); else the name is dropped (`no_price`). Every row
    serves its `price_age_sec`.
  * Leverage = the fund's own name in the Massive reference list, parsed with
    `sepa.levered_etf`'s constants (`fund_flags`).

The cron container runs `python -m overnight.scan` every 10 minutes through
the session; the api never does (it serves the stored read, overnight.board).
The module gates itself on the SESSION's trade date (`overnight.session`) —
never `market_hours.gate`, which reads TODAY (Sunday 20:00 = a weekend).

Every logged / stored error string goes through `broker_alpaca._scrub` (Alpaca)
or `prices._scrub_key` (Massive). UNMEASURED — what moved overnight, never what
to buy. Not advice.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from datetime import time as dtime
from typing import Optional

import requests

from sepa import levered_etf
from sepa import symbols
from trading import broker_alpaca
from trading.safety_floor import MIN_SHARE_PRICE, _f

from . import session as S

log = logging.getLogger("overnight.scan")

FEED = "overnight"                          # Alpaca data feed name
SNAPSHOTS_URL = broker_alpaca._DATA_URL + "/v2/stocks/snapshots"
ALPACA_BATCH = 200                          # TRANSPORT — measured 32 calls / 7.2 s for 6,267 names
ALPACA_TIMEOUT_SEC = 30                     # TRANSPORT
RETRY_SLEEP_SEC = 3                         # TRANSPORT — one retry on 429 (Retry-After honored, capped 10 s)
RETRY_AFTER_CAP_SEC = 10                    # TRANSPORT — the 10 s cap of the line above
PASS_BUDGET_SEC = 240                       # MINE — batches past it are skipped and counted
CADENCE_SEC = 600                           # == the crontab */10 step (test-pinned)
UNIVERSE_MIN_PRICE = MIN_SHARE_PRICE        # house $2 floor, by name
UNIVERSE_MIN_DOLLAR_VOL = 1_000_000         # MINE — base-session close × volume
BOARD_MIN_ON_DOLLAR = 25_000                # MINE — rows stored/listed; thinner names counted
REF_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")  # served first, in this order, regardless of any floor
BASE_PIN_LATEST_ET = dtime(3, 30)           # Massive snapshot reset (Polygon doc; OPEN O2)
REF_BUDGET_SEC = 120                        # MINE — reference pull budget at pin time
KEEP_SESSIONS = 2                           # MINE — reads/base docs older than the 2 newest trade dates pruned
QUOTE_FRESH_SEC = 300                       # MINE (AMENDMENTS16 A1) — a quote older than this never prices
QUOTE_SPREAD_MAX = 0.015                    # MINE (AMENDMENTS16 A1) — (ask − bid) / mid above this never prices
READS_COLL, BASE_COLL, PASS_COLL = "overnight_reads", "overnight_base", "overnight_pass"

_ERRORS_KEPT = 5                            # scrubbed transport errors kept on the stats (diagnostics only)
_clock = time.monotonic                     # one seam for the budget clocks (tests advance it)
_TS_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|z|[+-]\d{2}:?\d{2})?$")
_INVERSE_NOFACTOR = frozenset({"bear", "bearish", "inverse"})   # CHANGED 2026-10-19: + "bearish" (UDN)
_INVERSE_EXTRA_WITH_FACTOR = frozenset({"bearish"})              # CHANGED 2026-10-19: "2X Bearish" is inverse too
# "Bullish" needs no word of its own: it only ever rides a stated multiple, which already tags (UUP / USDU stay plain).
INVERSE_TICKER_OVERRIDES = frozenset({"EMTY"})  # MINE — ProShares Decline of the Retail Store ETF: inverse by product, no direction word in its name
# CHANGED 2026-10-19 (critic findings 1–2): the name rules below were widened / narrowed.
_PROSHARES_RE = re.compile(r"^ProShares\b", re.I)
_PROSHARES_SHORT_RE = re.compile(r"^ProShares\s+(?:Trust\s+)?(?:Ultra(?:Pro)?\s+)?Short\b", re.I)
_ULTRA_RE = re.compile(r"^ProShares\b(?:\s+Trust)?\b.*?\b(Ultr?a(?:Pro|Short)?)\b", re.I)  # CHANGED 2026-10-19: Massive spells SAA "Ulta"
_GLUED_FACTOR_RE = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)[xX](?=[A-Za-z])")   # "2xLeveraged"
_PCT_STACK_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)%\s+\S+(?:\s+\S+)*?\s+(?:AND|&)\s+(\d+(?:\.\d+)?)%",
                           re.I)                                                    # "100% TSLA AND 100% SPCX"
_X_STACK_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*[xX]\s+\S+(?:\s+\S+)*?\s+(?:AND|&)\s+(\d+(?:\.\d+)?)\s*[xX](?!\w)",
                         re.I)                                                      # "1x Bitcoin & 1x Gold"
_MULT_WORD_RE = re.compile(r"\b(Double|Triple)\s+(?:Long|Short|Leveraged|Bull|Bear)\b", re.I)
_MULT_WORDS = {"double": 2.0, "triple": 3.0}
_LEVERAGED_RE = re.compile(r"\bLeverage[d]?\b(?!\s+Loans?\b)", re.I)   # "Leverage(d) Loan" funds hold loans
# CHANGED 2026-10-19 (coordinator): the noun "Leverage" counts too (MVPL, MGOL).
# "Short" is a duration word, not a direction, when one of these follows it.
SHORT_DURATION_NEXT = frozenset({"term", "-term", "duration", "maturity", "treasury", "bond", "government",
                                 "municipal", "corporate", "income", "credit",
                                 "muni", "high", "horizon"})          # MINE (2026-10-19): the critic's list + 3 seen on the 10-19 list


# ---------------------------------------------------------------------------
# PURE helpers
# ---------------------------------------------------------------------------
def parse_ts(s) -> Optional[datetime]:
    """RFC3339 → aware UTC. 'Z' or an offset; 0–9 fraction digits (Alpaca
    sends nanoseconds) truncated to 6 — py3.9's fromisoformat reads neither
    'Z' nor 9 digits. No offset = UTC. Anything else → None."""
    if not isinstance(s, str):
        return None
    m = _TS_RE.match(s.strip())
    if not m:
        return None
    day, hms, frac, tz = m.groups()
    frac = ((frac or "") + "000000")[:6]
    if tz is None or tz in ("Z", "z"):
        off = "+00:00"
    else:
        off = tz if ":" in tz else tz[:3] + ":" + tz[3:]
    try:
        dt = datetime.fromisoformat(f"{day}T{hms}.{frac}{off}")
    except ValueError:
        return None
    return dt.astimezone(timezone.utc)


def _short_is_direction(tokens: list, proshares: bool) -> bool:
    """A standalone "Short" token that names a direction: not followed by a
    duration word (Short Term / Duration / Maturity / Treasury …) and not
    preceded by Ultra outside ProShares ("Ultra Short Income" is a bond fund)."""
    low = [t.lower() for t in tokens]
    for i, w in enumerate(low):
        if w != "short":
            continue
        nxt = low[i + 1] if i + 1 < len(low) else ""
        prv = low[i - 1] if i > 0 else ""
        if nxt in SHORT_DURATION_NEXT or nxt.startswith("-"):
            continue
        if prv in ("ultra", "ultra-") and not proshares:
            continue
        if prv == "long":                      # "Long Short" = a long/short fund, not an inverse one
            continue
        return True
    return False


def fund_flags(name: str, type_: Optional[str], symbol: Optional[str] = None) -> tuple:
    """(leveraged, lev_label) from the fund's own name (§3.3). PURE.

    Not a fund type → (False, None) — a CS named "Ultra Clean Holdings" is
    never classified; type unknown → (None, None). Leveraged: a stated
    multiple above `MIN_FACTOR_EXCLUSIVE` (also glued to a word, "2xLeveraged"),
    a stacked "N% … AND M% …" / "Nx … & Mx …" exposure above 1×, Double / Triple Long|Short,
    Ultra / UltraPro / UltraShort on a ProShares name, or the word Leverage /
    Leveraged (not "Leverage(d) Loan"). Inverse: a negative multiple or a short word WITH a
    multiple; else Bear / Inverse / "ProShares [Trust] [Ultra|UltraPro] Short" /
    UltraShort on a ProShares name / a standalone directional "Short". A 1×
    inverse fund is tagged "inverse ETF" (HIS CALL #15).
    CHANGED 2026-10-19 (critic findings 1–2): glued factors, the % stack,
    Double / Triple, Leveraged, directional Short, ProShares-only Ultra; later the
    "Ulta" misspelling (ProShares only), "Bearish", and `INVERSE_TICKER_OVERRIDES`
    (by `symbol`, before any name rule)."""
    if type_ is None:
        return None, None
    if type_ not in levered_etf.FUND_TYPES:
        return False, None
    name = str(name or "")
    tw = "ETN" if type_ == "ETN" else "ETF"
    if symbol is not None and str(symbol).strip().upper() in INVERSE_TICKER_OVERRIDES:
        return True, f"inverse {tw}"                 # CHANGED 2026-10-19: by ticker, before the name rules
    tokens = [w.strip(levered_etf.TOKEN_STRIP) for w in name.split()]
    tokens = [w for w in tokens if w]
    words = {w.lower() for w in tokens}
    proshares = bool(_PROSHARES_RE.match(name))
    facs = levered_etf.FACTOR_RE.findall(name) + _GLUED_FACTOR_RE.findall(name)
    if facs:
        inverse = (any(x.startswith("-") for x in facs) or bool(words & levered_etf.SHORT_WORDS)
                   or bool(words & _INVERSE_EXTRA_WITH_FACTOR))
    else:
        inverse = (bool(words & _INVERSE_NOFACTOR) or bool(_PROSHARES_SHORT_RE.match(name))
                   or ("ultrashort" in words and proshares) or _short_is_direction(tokens, proshares))
    sign = "\u2212" if inverse else ""
    mags = [abs(float(x)) for x in facs]
    factor = max(mags) if mags else None
    pm = _PCT_STACK_RE.search(name)
    if pm:
        factor = max(factor or 0.0, (float(pm.group(1)) + float(pm.group(2))) / 100.0)
    xm = _X_STACK_RE.search(name)
    if xm:
        factor = max(factor or 0.0, float(xm.group(1)) + float(xm.group(2)))
    if factor is None:
        mm = _MULT_WORD_RE.search(name)
        if mm:
            factor = _MULT_WORDS[mm.group(1).lower()]
    if factor is not None and factor > levered_etf.MIN_FACTOR_EXCLUSIVE:
        return True, f"{sign}{factor:g}\u00d7 {tw}"
    um = _ULTRA_RE.search(name)
    if um:
        word = re.sub(r"^ultr?a", "Ultra", um.group(1), flags=re.I)   # "Ulta" / "ultrashort" → "Ultra…"
        return True, f"{sign}{word} {tw}"
    if not facs and _LEVERAGED_RE.search(name):   # a stated multiple (e.g. "1X Short") governs the word
        return True, f"{sign}leveraged {tw}"
    if inverse:
        return True, f"inverse {tw}"
    return False, None


def _et_words(dt: datetime) -> str:
    """'Mon 0:47 ET' for one aware instant."""
    t = dt.astimezone(S.ET)
    return f"{t:%a} {t.hour}:{t.minute:02d} ET"


def _coll(name: str):
    try:
        from portfolio.store import _get_db
        db = _get_db()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("overnight: Mongo unavailable (%s)", type(exc).__name__)
        return None
    return db[name] if db is not None else None


def _iso(d) -> Optional[str]:
    return d.isoformat() if d is not None else None


# ---------------------------------------------------------------------------
# the base (Massive, pinned once per session)
# ---------------------------------------------------------------------------
def _fallback_keep(sym: str) -> bool:
    """The probe's filter when the reference list is incomplete: drop a "."
    symbol and a 5-letter symbol ending W / U / R (warrants, units, rights)."""
    if "." in sym:
        return False
    return not (len(sym) == 5 and sym.endswith(("W", "U", "R")))


def pin_base(sess: dict, now: datetime, *, coll=None, http=None, dry_run=False) -> tuple:
    """(base doc, None) or (None, reason). Called only when no pin exists."""
    now_et = S.et_now(now)
    if BASE_PIN_LATEST_ET <= now_et.time() < S.SESSION_CLOSE_ET:
        return None, "base not pinned before the 03:30 ET snapshot reset"
    from sepa import prices
    rows, meta = prices.market_snapshot_with_meta()
    meta = meta or {}
    if meta.get("http") != 200:
        return None, f"Massive snapshot refused (HTTP {meta.get('http')}) — not pinned"
    spy = (rows or {}).get("SPY") or {}
    spy_c, spy_pc = _f(spy.get("close")), _f(spy.get("prev_day_close"))
    if not spy_c or spy_c <= 0 or not spy_pc or spy_pc <= 0:
        return None, "Massive snapshot carries no close for SPY — not pinned"

    ref: dict = {}
    calls = 0
    incomplete: list = []
    t0 = _clock()
    for t in levered_etf.FUND_TYPES + levered_etf.STOCK_TYPES:
        if _clock() - t0 > REF_BUDGET_SEC:
            incomplete.append(t)
            continue
        try:
            got, complete, n = levered_etf.fetch_reference(t, http=http)
        except Exception as exc:                                # noqa: BLE001
            log.warning("overnight: reference %s failed: %s", t, prices._scrub_key(exc))
            got, complete, n = [], False, 0
        calls += n or 0
        if not complete:
            incomplete.append(t)
        for r in got or []:
            tk = symbols.for_yahoo(str(r.get("ticker") or "").strip().upper())
            if tk and tk not in ref:
                ref[tk] = (str(r.get("name") or ""), str(r.get("type") or t))
    ref_complete = not incomplete
    kinds = levered_etf.STOCK_TYPES + levered_etf.FUND_TYPES

    out: dict = {}
    for sym, r in (rows or {}).items():
        c, v, pc = _f(r.get("close")), _f(r.get("volume")), _f(r.get("prev_day_close"))
        name, type_ = ref.get(sym, (None, None))
        if sym not in REF_SYMBOLS:
            if c is None or v is None or c < UNIVERSE_MIN_PRICE or c * v < UNIVERSE_MIN_DOLLAR_VOL:
                continue
            if ref_complete:
                if type_ not in kinds:
                    continue
            elif not _fallback_keep(sym):
                continue
        if ref_complete:
            lev, ll = fund_flags(name or "", type_, sym)
        else:
            lev, ll = None, None
        out[sym] = {"c": c, "v": v, "pc": pc, "t": type_, "n": name, "lev": lev, "ll": ll}

    td = sess["trade_date"].isoformat()
    doc = {
        "_id": td,
        "trade_date": td,
        "base_date": _iso(sess.get("base_date")),
        "pinned_at": now_et.isoformat(),
        "snapshot": {"http": meta.get("http"), "wall_s": meta.get("wall_s"), "n": meta.get("n")},
        "ref": {"complete": ref_complete, "calls": calls, "types_incomplete": incomplete},
        "n_universe": len(out),
        "rows": out,
    }
    if not dry_run:
        coll = coll if coll is not None else _coll(BASE_COLL)
        if coll is not None:
            try:
                coll.replace_one({"_id": td}, doc, upsert=True)
                _prune(coll)
            except Exception as exc:                            # noqa: BLE001
                log.warning("overnight: base not stored: %s", type(exc).__name__)
    return doc, None


def load_base(trade_date: str, coll=None) -> Optional[dict]:
    coll = coll if coll is not None else _coll(BASE_COLL)
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": trade_date})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("overnight: base unreadable: %s", type(exc).__name__)
        return None


# ---------------------------------------------------------------------------
# now (Alpaca feed=overnight)
# ---------------------------------------------------------------------------
def _retry_after(resp) -> float:
    try:
        v = float((getattr(resp, "headers", None) or {}).get("Retry-After"))
    except (TypeError, ValueError):
        return float(RETRY_SLEEP_SEC)
    if v != v or v < 0:
        return float(RETRY_SLEEP_SEC)
    return min(v, float(RETRY_AFTER_CAP_SEC))


def alpaca_snapshots(symbols_: list, *, t0: float, sleep=time.sleep) -> tuple:
    """({OUR_SYMBOL: snapshot}, stats). Batches of ALPACA_BATCH, wire symbols
    in Massive's dot spelling (BRK.B answers), keys mapped back through the
    asked map (a key we did not ask for is dropped). One retry on 429; a
    401 / 403 stops the pass (`stats.refused`); a batch past PASS_BUDGET_SEC
    (from `t0`, on `_clock`) is skipped and counted."""
    stats = {"batches": 0, "batches_failed": 0, "batches_skipped": 0, "calls": 0, "retries": 0,
             "refused": None, "errors": []}
    out: dict = {}
    headers = {"APCA-API-KEY-ID": os.getenv("ALPACA_KEY_ID") or "",
               "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY") or "",
               "Accept": "application/json"}
    syms = list(symbols_ or [])
    for i in range(0, len(syms), ALPACA_BATCH):
        batch = syms[i:i + ALPACA_BATCH]
        stats["batches"] += 1
        if stats["refused"] is not None or _clock() - t0 > PASS_BUDGET_SEC:
            stats["batches_skipped"] += 1
            continue
        asked = {symbols.for_massive(s): s for s in batch}
        params = {"symbols": ",".join(asked), "feed": FEED}
        resp = None
        for attempt in (0, 1):
            stats["calls"] += 1
            try:
                resp = requests.get(SNAPSHOTS_URL, params=params, headers=headers,
                                    timeout=ALPACA_TIMEOUT_SEC)
            except Exception as exc:                            # noqa: BLE001
                msg = broker_alpaca._scrub(exc)
                log.warning("overnight: alpaca batch %d failed: %s", stats["batches"], msg)
                if len(stats["errors"]) < _ERRORS_KEPT:
                    stats["errors"].append(msg)
                resp = None
                break
            if resp.status_code == 429 and attempt == 0:
                stats["retries"] += 1
                sleep(_retry_after(resp))
                continue
            break
        if resp is None:
            stats["batches_failed"] += 1
            continue
        code = resp.status_code
        if code in (401, 403):
            stats["refused"] = code
            stats["batches_failed"] += 1
            log.warning("overnight: alpaca overnight feed refused (HTTP %s)", code)
            continue
        if code != 200:
            stats["batches_failed"] += 1
            log.warning("overnight: alpaca batch %d HTTP %s", stats["batches"], code)
            continue
        try:
            body = resp.json() or {}
        except Exception as exc:                                # noqa: BLE001
            stats["batches_failed"] += 1
            log.warning("overnight: alpaca batch %d bad body: %s", stats["batches"], type(exc).__name__)
            continue
        if not isinstance(body, dict):
            stats["batches_failed"] += 1
            continue
        for k, snap in body.items():
            ours = asked.get(k)
            if ours is not None and isinstance(snap, dict):
                out[ours] = snap
    return out, stats


# ---------------------------------------------------------------------------
# one row, one read
# ---------------------------------------------------------------------------
def build_row(sym: str, b: dict, snap: Optional[dict], sess: dict, now: datetime) -> tuple:
    """(row, None) or (None, drop reason) — §3.2 + AMENDMENTS16 A1."""
    b = b or {}
    c = _f(b.get("c"))
    if c is None or c <= 0:
        return None, "no_base"
    if not snap:
        return None, "not_on_feed"
    now_et = S.et_now(now)
    opens_at = sess["opens_at"]
    lt = snap.get("latestTrade") or {}
    lq = snap.get("latestQuote") or {}
    db = snap.get("dailyBar") or {}

    price = src = ptime = spread = None
    qt = parse_ts(lq.get("t"))
    bp, ap = _f(lq.get("bp")), _f(lq.get("ap"))
    if (qt is not None and qt >= opens_at and (now_et - qt).total_seconds() <= QUOTE_FRESH_SEC
            and bp is not None and ap is not None and 0 < bp < ap):
        mid = (bp + ap) / 2
        if (ap - bp) / mid <= QUOTE_SPREAD_MAX:
            price, src, ptime, spread = mid, "q", qt, 100 * (ap - bp) / mid
    if price is None:
        tt = parse_ts(lt.get("t"))
        tp = _f(lt.get("p"))
        if tt is not None and tt >= opens_at and tp is not None and tp > 0:
            price, src, ptime = tp, "t", tt
    if price is None:
        return None, "no_price"

    td = sess["trade_date"].isoformat()
    on_bar = str(db.get("t") or "")[:10] == td
    bv = _f(db.get("v"))
    on_volume = (bv or 0.0) if on_bar else 0.0
    on_dollar = _f(on_volume * (_f(db.get("vw")) or _f(db.get("c")) or price))
    bn = _f(db.get("n"))
    on_trades = int(bn) if (on_bar and bn is not None) else 0
    pct = _f(100 * (price / c - 1))
    if pct is None:
        return None, "no_price"
    pc = _f(b.get("pc"))
    prior_pct = _f(100 * (c / pc - 1)) if pc is not None and pc > 0 else None
    v = _f(b.get("v"))
    pt_et = ptime.astimezone(S.ET)
    row = {
        "symbol": sym,
        "name": b.get("n"),
        "type": b.get("t"),
        "base_close": c,
        "base_date": _iso(sess.get("base_date")),
        "price": _f(price),
        "src": src,
        "price_time": pt_et.isoformat(),
        "price_time_et": _et_words(pt_et),
        "price_age_sec": max(0, int(round((now_et - ptime).total_seconds()))),
        "spread_pct": _f(spread),
        "pct": pct,
        "on_volume": _f(on_volume),
        "on_dollar": on_dollar,
        "on_trades": on_trades,
        "on_bar": on_bar,
        "prior_pct": prior_pct,
        "prior_dollar_vol": _f(c * v) if v is not None else None,
        "leveraged": b.get("lev"),
        "lev_label": b.get("ll"),
        "ref": sym in REF_SYMBOLS,
    }
    return row, None


def _counts_zero() -> dict:
    return {k: 0 for k in ("universe", "batches", "batches_failed", "batches_skipped", "calls",
                           "retries", "not_on_feed", "no_price", "no_base", "priced", "on_trade",
                           "on_quote", "listed", "thin", "leveraged_tagged", "lev_unknown")}


def build_read(base: dict, snaps: dict, sess: dict, now: datetime) -> dict:
    """The `overnight_reads` doc for one pass (`counts` transport keys and
    `secs` are filled by `read_once`)."""
    now_et = S.et_now(now)
    td = sess["trade_date"].isoformat()
    counts = _counts_zero()
    counts["ref_complete"] = bool(((base or {}).get("ref") or {}).get("complete"))
    brows = (base or {}).get("rows") or {}
    counts["universe"] = len(brows)
    priced: list = []
    for sym in sorted(brows):
        row, why = build_row(sym, brows[sym], (snaps or {}).get(sym), sess, now_et)
        if row is None:
            counts[why] = counts.get(why, 0) + 1
            continue
        priced.append(row)
    counts["priced"] = len(priced)
    counts["on_trade"] = sum(1 for r in priced if r["src"] == "t")
    counts["on_quote"] = sum(1 for r in priced if r["src"] == "q")
    counts["leveraged_tagged"] = sum(1 for r in priced if r["leveraged"] is True)
    counts["lev_unknown"] = sum(1 for r in priced if r["leveraged"] is None)
    ages = [r["price_age_sec"] for r in priced if r["src"] == "t"]
    counts["trade_age_median_sec"] = int(round(statistics.median(ages))) if ages else None
    by_sym = {r["symbol"]: r for r in priced}
    refs = [by_sym[s] for s in REF_SYMBOLS if s in by_sym]
    rows = [r for r in priced if (r["on_dollar"] or 0) >= BOARD_MIN_ON_DOLLAR]
    counts["listed"] = len(rows)
    counts["thin"] = len(priced) - len(rows)
    return {
        "_id": f"{td}T{now_et:%H%M}",
        "trade_date": td,
        "base_date": (base or {}).get("base_date") or _iso(sess.get("base_date")),
        "as_of": now_et.isoformat(),
        "as_of_ts": now_et.timestamp(),
        "as_of_et": _et_words(now_et),
        "session_open": bool(sess.get("open")),
        "complete": True,
        "reason": None,
        "counts": counts,
        "refs": refs,
        "rows": rows,
        "secs": None,
    }


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------
def _prune(coll) -> None:
    """Delete docs whose trade date is older than the KEEP_SESSIONS newest."""
    dates = sorted({d.get("trade_date") for d in coll.find({}, {"trade_date": 1})
                    if d.get("trade_date")}, reverse=True)
    keep = dates[:KEEP_SESSIONS]
    if len(dates) > KEEP_SESSIONS:
        coll.delete_many({"trade_date": {"$nin": keep}})


def store(doc: dict, coll=None) -> Optional[str]:
    coll = coll if coll is not None else _coll(READS_COLL)
    if coll is None:
        return None
    try:
        try:
            coll.create_index([("trade_date", 1), ("as_of_ts", -1)])
        except Exception:                                       # noqa: BLE001
            pass
        coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        _prune(coll)
        return doc["_id"]
    except Exception as exc:                                    # noqa: BLE001
        log.warning("overnight: read not stored: %s", type(exc).__name__)
        return None


def load_latest(trade_date: Optional[str] = None, coll=None) -> Optional[dict]:
    """The newest stored read (of `trade_date` when given) by `as_of_ts` —
    never by `_id` ("…T2350" sorts after "…T0100")."""
    coll = coll if coll is not None else _coll(READS_COLL)
    if coll is None:
        return None
    q = {"trade_date": trade_date} if trade_date else {}
    try:
        for d in coll.find(q).sort("as_of_ts", -1).limit(1):
            return d
    except Exception as exc:                                    # noqa: BLE001
        log.warning("overnight: reads unreadable: %s", type(exc).__name__)
    return None


def load_pass(coll=None) -> Optional[dict]:
    coll = coll if coll is not None else _coll(PASS_COLL)
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": "latest"})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("overnight: pass doc unreadable: %s", type(exc).__name__)
        return None


# ---------------------------------------------------------------------------
# one pass
# ---------------------------------------------------------------------------
def read_once(now=None, *, dry_run=False, reads_coll=None, base_coll=None, pass_coll=None,
              http=None) -> dict:
    t_start = _clock()
    sess = S.session_for(now)
    if not sess["open"]:
        return {"ran": False, "reason": sess["reason"]}
    now_et = S.et_now(now)
    td = sess["trade_date"].isoformat()
    out = {"ran": True, "ok": False, "trade_date": td, "as_of": now_et.isoformat(),
           "as_of_ts": now_et.timestamp(), "as_of_et": _et_words(now_et), "stored_id": None,
           "reason": None, "counts": None}

    def _finish(res: dict) -> dict:
        if not dry_run:
            pc = pass_coll if pass_coll is not None else _coll(PASS_COLL)
            if pc is not None:
                doc = {"_id": "latest", **{k: res.get(k) for k in
                       ("as_of", "as_of_ts", "as_of_et", "trade_date", "ran", "ok",
                        "stored_id", "reason", "counts")}}
                try:
                    pc.replace_one({"_id": "latest"}, doc, upsert=True)
                except Exception as exc:                        # noqa: BLE001
                    log.warning("overnight: pass doc not stored: %s", type(exc).__name__)
        return res

    base = load_base(td, base_coll)
    if base is None:
        base, why = pin_base(sess, now_et, coll=base_coll, http=http, dry_run=dry_run)
        if base is None:
            out["reason"] = why
            return _finish(out)

    if not broker_alpaca.configured():
        out["reason"] = "Alpaca keys not configured — nothing read"
        return _finish(out)
    snaps, st = alpaca_snapshots(sorted((base.get("rows") or {}).keys()), t0=t_start)
    if st.get("refused") is not None:
        out["reason"] = f"Alpaca overnight feed refused (HTTP {st['refused']})"
        return _finish(out)

    read = build_read(base, snaps, sess, now_et)
    for k in ("batches", "batches_failed", "batches_skipped", "calls", "retries"):
        read["counts"][k] = st.get(k, 0)
    if st.get("batches_failed") or st.get("batches_skipped"):
        read["complete"] = False
        read["reason"] = (f"{st.get('batches_failed', 0)} of {st.get('batches', 0)} batches failed, "
                          f"{st.get('batches_skipped', 0)} skipped past the pass budget")
    read["secs"] = round(_clock() - t_start, 2)
    out["counts"] = read["counts"]
    out["reason"] = read["reason"]
    if read["counts"]["priced"] <= 0:
        # CHANGED 2026-10-19 (critic finding 4): a batch failure is the reason when it is why
        # nothing priced ("N of N batches failed …"), never the generic line.
        out["reason"] = read["reason"] or "no name priced this session — nothing stored"
        return _finish(out)
    out["ok"] = True
    if dry_run:
        out["read"] = read
        return out
    out["stored_id"] = store(read, reads_coll)
    if out["stored_id"] is None:
        out["ok"] = False
        out["reason"] = "Mongo unavailable — read not stored"
    return _finish(out)


def main(argv=None) -> int:
    """python -m overnight.scan [--dry-run] [--json]"""
    ap = argparse.ArgumentParser(prog="overnight.scan")
    ap.add_argument("--dry-run", action="store_true", help="read and build, write nothing")
    ap.add_argument("--json", action="store_true", help="print the pass result as JSON")
    args = ap.parse_args(argv)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    try:
        res = read_once(dry_run=args.dry_run)
    except Exception as exc:                                    # noqa: BLE001
        log.error("overnight.scan failed: %s", broker_alpaca._scrub(exc))
        return 1
    if not res.get("ran"):
        log.info("overnight.scan: not run — %s", res.get("reason"))
    else:
        c = res.get("counts") or {}
        log.info("overnight.scan: ok=%s stored=%s priced=%s listed=%s reason=%s",
                 res.get("ok"), res.get("stored_id"), c.get("priced"), c.get("listed"),
                 res.get("reason"))
    if args.json:
        print(json.dumps(res, default=str, allow_nan=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
