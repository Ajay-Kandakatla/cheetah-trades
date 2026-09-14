"""Board fundamentals — dilution, cash vs debt, EV/Sales, FCF yield.

Ajay 2026-09-13: *"In the explosive growth and breakout can you add few more
columns to the table ... 3. Debt ... Or any other value added metrics to check
company valuation. Think like a CPA analyst and stock valuation."*

WHY A BOARD-SCOPED CACHE AND NOT THE WEEKLY RESEARCH CACHE
──────────────────────────────────────────────────────────
The app already had one debt number — `moat.components.capital.net_debt_ebitda`
in `sepa_research_cache` — and it is **blank for 60% of both boards**: measured
2026-09-13 at 99/250 breakout rows (39.6%) and 11/29 growth rows (37.9%).

That is not missing data, it is a refresh-time fetch failure. The weekly research
cron walks 3,738 symbols at 6 workers and gets rate-limited. Fetched serially for
the ~279 names that ACTUALLY APPEAR on the two boards, the same provider answers
98.8%. So this module caches per-BOARD, not per-universe.

The bar it has to clear is the repo's own, written at `sepa/research.py:154`:
*"a column blank for a third of the board is worse than no column"* — which is
why `moat` (64.7%) was kept off the Hottest Sectors table. Measured coverage of
what ships here, on the live boards:

    shares_yoy        growth  86%   breakout  91%
    cash_minus_debt   growth 100%   breakout  99%
    ev_sales          growth 100%   breakout  99%
    fcf_yield         growth  90%   breakout  89%

WHAT THE DILUTION COLUMN IMMEDIATELY SHOWED, measured the day it was built:
the two boards are opposites. Explosive Growth runs a MEDIAN +11.8% share
growth with 16 of 25 diluting more than 5% and only 2 buying back; Breakouts
runs a median of -0.2% with 119 of 228 buying back. The +100%/+100% screen is
selecting companies funding their growth with stock, and nothing on that board
said so before this column.

TWO SOURCES, SPLIT BY WHAT EACH CAN ACTUALLY ANSWER
───────────────────────────────────────────────────
**Massive** `/vX/reference/financials` → `income_statement.diluted_average_shares`.
It is the only source with a share-count HISTORY, which dilution needs. Its
balance sheet is useless here: measured `cash` at 1.2-3.4% and `long_term_debt`
at 27.6-39.6%, so it cannot produce net debt at any usable rate.

**yfinance `.info`** → `totalCash`, `totalDebt`, `enterpriseToRevenue`,
`freeCashflow`, `marketCap`, `sector`. 98-100% on board-sized lists.

THE DERIVED-Q4 TRAP, AND WHY THE GUARD IS NOT A MAGNITUDE THRESHOLD
───────────────────────────────────────────────────────────────────
23.8% of Massive's quarterly rows are DERIVED Q4s — annual minus the three
reported quarters — and they carry `filing_date: None`. That subtraction is
arithmetic nonsense for an AVERAGE share count, and the damage is not subtle.
Measured live 2026-09-13:

    NVDA  Q4 FY2026  filed=None  diluted_average_shares =    -28,000,000
    MU    Q4 FY2025  filed=None  diluted_average_shares =      2,000,000   (real: ~1,140,000,000)
    SM    Q4 FY2025  filed=None  diluted_average_shares =         10,000   (real: ~115,000,000)
    SM    Q4 FY2024  filed=None  diluted_average_shares =       -168,000

The tempting guard is "drop anything implausibly small". **That guard is wrong**,
and MU is the proof: its corrupt value is 2,000,000, which is a perfectly
ordinary share count for a real microcap. A magnitude floor would pass MU's
garbage and reject genuine small names. `filing_date is None` separates derived
from reported exactly, with no invented number, so that is the whole test.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

log = logging.getLogger("sepa.board_metrics")

COLL = "board_metrics"

# 36h: the growth board rebuilds weekly and the breakout board every scan, but
# balance-sheet facts move quarterly. A day and a half means a board loaded any
# time today reads numbers fetched at most one refresh ago, and the cron below
# keeps it warm without re-hammering a provider for data that has not changed.
TTL_SEC = 36 * 3600

# Serial-ish on purpose. The measured failure mode of the weekly research cron
# is exactly this: 6 workers over thousands of symbols gets rate-limited into a
# 40% fill. Board-sized lists are ~279 names, so a small pool finishes in well
# under a minute and actually returns data.
DEFAULT_WORKERS = 3

QUARTERS_FETCHED = 12
YOY_GAP = 4                 # fiscal quarters between a quarter and its year-ago self

# A diluted-average-share count more than this factor away from the CURRENT
# shares outstanding means something structural happened between the two — a
# reverse split is the common one, and it would otherwise print as a −90%
# "dilution" that is really a 1:10 consolidation. The cell goes BLANK rather
# than reporting a number that is arithmetically true and economically false.
#
# This is a sanity bound, NOT a measured threshold, and it is deliberately loose
# so it only catches structural breaks and never an ordinary capital raise.
SPLIT_SUSPECT_RATIO = 3.0

# THE RKT DEFECT, caught on the live board 2026-09-13 before this shipped.
#
# Rocket Companies measured +1,559% dilution. It is not diluting. Its reported
# diluted-average-share series OSCILLATES:
#
#     Q2 2026  2,843,538,118      Q1 2026  2,846,974,742
#     Q3 2025  2,106,227,188      Q2 2025    171,438,105   <-- 12x lower
#     Q1 2025  2,001,936,379      Q3 2024  2,003,296,515
#     Q2 2024    139,647,845      Q1 2024  1,991,982,680
#
# Rocket has an up-C structure, and in the quarters where the Class D units are
# ANTI-dilutive they drop out of the EPS denominator entirely. So a Q2-vs-Q2
# comparison silently measures a near-basic denominator against a fully-diluted
# one. The arithmetic is perfect and the number is meaningless.
#
# `SPLIT_SUSPECT_RATIO` did NOT catch it: live shares 980,550,267 over
# 2,843,538,118 is 0.345, and the floor is 0.333. It missed by a hair, which is
# exactly how much to trust a single cross-check.
#
# The general form of the bug is a denominator whose BASIS changes between
# quarters, whatever the cause. Genuine dilution is smooth quarter to quarter —
# even SM, the most diluted real name on the board at +109% YoY, never moves
# more than 1.73x between adjacent quarters. A basis flip moves 12x.
#
# So: if any adjacent pair in the recent reported quarters differs by more than
# this factor, the basis is unstable and the cell goes BLANK with a reason. Like
# SPLIT_SUSPECT_RATIO this is a loose SANITY bound, not a measured threshold —
# it is set where a real capital raise cannot reach it, and its failure mode is
# a blank cell rather than a wrong number.
BASIS_FLIP_RATIO = 4.0
BASIS_CHECK_QUARTERS = 5

# Sectors where a balance sheet does not mean what it means elsewhere. A bank's
# deposits are liabilities; a mortgage REIT is levered by design and carries
# no meaningful revenue line, which is why ARR and NLY measure EV/Sales at 41x
# and 44x and report no free cash flow at all. Rendering those as ordinary
# numbers would invite exactly the wrong read, so the cell says "n/a" and says
# why. Measured share of the boards: growth 6/29 (20.7%), breakout 45/250 (18%).
NON_OPERATING_SECTORS = ("Financial Services", "Real Estate")


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _db(db=None):
    if db is not None:
        return db
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL") or "mongodb://mongo:27017"
        name = os.getenv("MONGO_DB") or "cheetah"
        return MongoClient(url, serverSelectionTimeoutMS=3000)[name]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("board_metrics: mongo unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Dilution
# ---------------------------------------------------------------------------
def _period_index(report: dict) -> Optional[int]:
    """A fiscal quarter as one comparable integer: year*4 + (quarter-1).

    Same construction `sepa/qoq.py` uses, and for the same reason — it makes
    "exactly one year earlier" a subtraction instead of a date guess, so a
    company whose fiscal year does not match the calendar (MU, NVDA, HNI all
    differ) is compared against its OWN prior-year quarter.
    """
    try:
        fy = int(report.get("fiscal_year"))
    except (TypeError, ValueError):
        return None
    fp = str(report.get("fiscal_period") or "").upper().strip()
    if not fp.startswith("Q") or len(fp) < 2 or not fp[1].isdigit():
        return None
    q = int(fp[1])
    if not 1 <= q <= 4:
        return None
    return fy * 4 + (q - 1)


def _reported_quarters(results: list) -> list:
    """Only quarters the company actually FILED, newest first.

    `filing_date is None` marks a DERIVED Q4 — annual minus the three reported
    quarters. For a flow item that subtraction is fine; for an AVERAGE share
    count it is meaningless, and it produces negative and off-by-500x values
    (see the module docstring). This one test is the entire guard.
    """
    out = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        if not r.get("filing_date"):
            continue                    # derived, not reported
        idx = _period_index(r)
        if idx is None:
            continue
        ist = ((r.get("financials") or {}).get("income_statement") or {})
        shares = _f((ist.get("diluted_average_shares") or {}).get("value"))
        if shares is None:
            shares = _f((ist.get("basic_average_shares") or {}).get("value"))
        if shares is None or shares <= 0:
            continue                    # a non-positive share count is corrupt
        out.append({"idx": idx, "shares": shares,
                    "period": "%s %s" % (r.get("fiscal_period"), r.get("fiscal_year")),
                    "filed": r.get("filing_date"), "end": r.get("end_date")})
    out.sort(key=lambda x: -x["idx"])
    return out


def shares_yoy(results: list, live_shares: Optional[float] = None) -> Optional[dict]:
    """Diluted share count vs the SAME fiscal quarter a year earlier.

    THE COLUMN THIS MODULE EXISTS FOR. A name doubling revenue while doubling
    its share count has flat revenue per share, and neither board could say so:
    measured on the live growth board the median is +11.8%, with SM at +109%,
    DX +98% and HNI +53%, while NVDA and TER are buying back.

    Returns None rather than a guess whenever the comparison cannot be made
    honestly — no reported year-ago quarter, or a structural break.
    """
    qs = _reported_quarters(results)
    if len(qs) < 2:
        return None
    now = qs[0]
    then = next((q for q in qs[1:] if q["idx"] == now["idx"] - YOY_GAP), None)
    if then is None:
        # No year-ago quarter at that exact fiscal offset. Do NOT fall back to
        # "the oldest one we have" — that silently compares across a different
        # number of quarters and reports it as a year of dilution.
        return {"pct": None, "reason": "no_year_ago_quarter",
                "period": now["period"], "shares": now["shares"]}

    # Basis stability BEFORE the arithmetic — see BASIS_FLIP_RATIO. Checked
    # across the window that actually feeds the comparison, so a flip anywhere
    # between the two endpoints disqualifies it too.
    window = qs[:max(2, BASIS_CHECK_QUARTERS)]
    for a, b in zip(window, window[1:]):
        hi, lo = max(a["shares"], b["shares"]), min(a["shares"], b["shares"])
        if lo > 0 and hi / lo > BASIS_FLIP_RATIO:
            return {"pct": None, "reason": "unstable_share_basis",
                    "period": now["period"], "shares": now["shares"],
                    "flip": [a["period"], b["period"]]}

    if live_shares and now["shares"] > 0:
        ratio = live_shares / now["shares"]
        if ratio > SPLIT_SUSPECT_RATIO or ratio < 1.0 / SPLIT_SUSPECT_RATIO:
            # A reverse split or a structural recapitalisation sits between the
            # filing and today. The percentage would be arithmetically true and
            # economically false, so it is withheld.
            return {"pct": None, "reason": "split_suspected",
                    "period": now["period"], "shares": now["shares"],
                    "live_shares": live_shares}

    pct = 100.0 * (now["shares"] - then["shares"]) / then["shares"]
    return {"pct": round(pct, 1), "reason": None,
            "period": now["period"], "prior_period": then["period"],
            "shares": now["shares"], "prior_shares": then["shares"],
            "filed": now["filed"]}


def _fetch_quarters(symbol: str) -> list:
    """Massive quarterly financials, newest first. [] on any failure."""
    try:
        import requests
        from massive_keys import stocks_key
    except Exception as exc:                                   # noqa: BLE001
        log.debug("board_metrics: massive import failed: %s", exc)
        return []
    key = stocks_key()
    if not key:
        return []
    try:
        r = requests.get("https://api.massive.com/vX/reference/financials",
                         params={"ticker": symbol.upper(),
                                 "limit": QUARTERS_FETCHED,
                                 "timeframe": "quarterly", "apiKey": key},
                         timeout=12)
        if r.status_code != 200:
            return []
        return (r.json() or {}).get("results") or []
    except Exception as exc:                                   # noqa: BLE001
        # Never let a provider string reach a log line — the key rides in the
        # query string and this repo has leaked one that way before.
        log.debug("board_metrics: quarters %s failed: %s",
                  symbol, type(exc).__name__)
        return []


# ---------------------------------------------------------------------------
# Balance sheet + valuation
# ---------------------------------------------------------------------------
def balance_metrics(symbol: str) -> dict:
    """Cash, debt, EV/Sales and FCF yield for one name, from yfinance .info.

    Every value is returned as-is or as None; nothing here is estimated, and a
    sector where the numbers mislead is FLAGGED rather than silently rendered.
    """
    out = {"cash": None, "debt": None, "cash_minus_debt": None,
           "ev_sales": None, "fcf_yield": None, "market_cap": None,
           "sector": None, "balance_meaningful": True}
    try:
        from sepa import symbols as S
        info = (S.yf_ticker(symbol).info) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.debug("board_metrics: info %s failed: %s", symbol, type(exc).__name__)
        return out

    cash, debt = _f(info.get("totalCash")), _f(info.get("totalDebt"))
    cap = _f(info.get("marketCap"))
    fcf = _f(info.get("freeCashflow"))
    sector = info.get("sector")

    out["sector"] = sector if isinstance(sector, str) else None
    out["cash"], out["debt"], out["market_cap"] = cash, debt, cap
    if cash is not None and debt is not None:
        out["cash_minus_debt"] = round(cash - debt, 2)
    out["ev_sales"] = _f(info.get("enterpriseToRevenue"))
    if fcf is not None and cap and cap > 0:
        out["fcf_yield"] = round(100.0 * fcf / cap, 2)

    if out["sector"] in NON_OPERATING_SECTORS:
        # Keep the raw numbers — the drill-in can still show them — but tell
        # the board not to rank or colour them as if they were comparable.
        out["balance_meaningful"] = False
    return out


def _live_shares(symbol: str, db=None) -> Optional[float]:
    """Current shares outstanding from the app's existing `shares_cache`.

    Used ONLY as a structural-break cross-check for dilution, never as a
    numerator — it is a point-in-time snapshot with no history.
    """
    d = _db(db)
    if d is None:
        return None
    try:
        doc = d["shares_cache"].find_one({"_id": symbol.upper()}) or {}
        return _f(doc.get("shares_outstanding"))
    except Exception:                                          # noqa: BLE001
        return None


def for_symbol(symbol: str, db=None) -> dict:
    """Every metric for one name. Never raises."""
    sym = symbol.upper()
    row = {"symbol": sym, "fetched_at": time.time()}
    row.update(balance_metrics(sym))
    try:
        row["shares_yoy"] = shares_yoy(_fetch_quarters(sym), _live_shares(sym, db))
    except Exception as exc:                                   # noqa: BLE001
        log.debug("board_metrics: dilution %s failed: %s", sym, type(exc).__name__)
        row["shares_yoy"] = None
    return row


# ---------------------------------------------------------------------------
# Warm + read
# ---------------------------------------------------------------------------
def warm(symbols: list, max_workers: int = DEFAULT_WORKERS, db=None,
         only_missing: bool = True) -> dict:
    """Fetch and store metrics for the names that are actually on the boards."""
    d = _db(db)
    syms = [str(s).upper() for s in (symbols or []) if s]
    syms = sorted(set(syms))
    if not syms:
        return {"n": 0, "written": 0}

    if only_missing and d is not None:
        cutoff = time.time() - TTL_SEC
        try:
            fresh = {doc["_id"] for doc in d[COLL].find(
                {"_id": {"$in": syms}, "fetched_at": {"$gte": cutoff}}, {"_id": 1})}
            syms = [s for s in syms if s not in fresh]
        except Exception as exc:                               # noqa: BLE001
            log.debug("board_metrics: freshness check failed: %s", exc)

    written = 0
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
        futs = {ex.submit(for_symbol, s, d): s for s in syms}
        for fut in as_completed(futs):
            try:
                rows.append(fut.result())
            except Exception as exc:                           # noqa: BLE001
                log.debug("board_metrics: %s failed: %s", futs[fut], exc)

    if d is not None:
        for r in rows:
            try:
                d[COLL].replace_one({"_id": r["symbol"]}, {**r, "_id": r["symbol"]},
                                    upsert=True)
                written += 1
            except Exception as exc:                           # noqa: BLE001
                log.debug("board_metrics: write %s failed: %s", r.get("symbol"), exc)
    return {"n": len(syms), "written": written}


def snapshot(symbols: list, db=None, max_age_sec: int = TTL_SEC) -> dict:
    """{SYM: metrics} for the board, ONE Mongo read.

    Omits a symbol it cannot answer for rather than returning zeros — the board
    renders an em-dash for a miss, and a blank must never pass a sort or a
    filter. Same discipline as `research.decision_snapshot`.
    """
    d = _db(db)
    syms = [str(s).upper() for s in (symbols or []) if s]
    if d is None or not syms:
        return {}
    cutoff = time.time() - max_age_sec
    try:
        out = {}
        for doc in d[COLL].find({"_id": {"$in": syms},
                                 "fetched_at": {"$gte": cutoff}}):
            sy = doc.pop("_id")
            out[sy] = doc
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("board_metrics: snapshot failed: %s", exc)
        return {}


def attach(rows: list, db=None) -> list:
    """Flatten the metrics onto board rows, in place, and return them.

    Flat keys, because both boards' row types are flat and the frontend cells
    read one field each. `shares_yoy_pct` is None whenever the comparison could
    not be made honestly, and `shares_yoy_reason` says which refusal it was so
    the tooltip can explain a blank instead of leaving it mysterious.
    """
    syms = [r.get("symbol") for r in (rows or []) if r.get("symbol")]
    snap = snapshot(syms, db=db)
    for r in rows or []:
        m = snap.get(str(r.get("symbol", "")).upper())
        if not m:
            continue
        dil = m.get("shares_yoy") or {}
        r["shares_yoy_pct"] = dil.get("pct")
        r["shares_yoy_reason"] = dil.get("reason")
        r["shares_yoy_period"] = dil.get("period")
        for k in ("cash", "debt", "cash_minus_debt", "ev_sales", "fcf_yield",
                  "sector", "balance_meaningful"):
            r[k] = m.get(k)
    return rows


def _main(argv=None) -> int:
    """`python -m sepa.board_metrics warm|show` — what the cron runs.

    `warm` refreshes the union of the two boards' names, which is the whole
    point of this module: ~279 symbols answer at 98-100%, the full universe
    answers at 40%.
    """
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = (args[0] if args else "warm").lower()
    d = _db()

    if cmd == "show":
        if d is None:
            print("board_metrics: no db")
            return 1
        n = d[COLL].estimated_document_count()
        fresh = d[COLL].count_documents({"fetched_at": {"$gte": time.time() - TTL_SEC}})
        print("board_metrics: %d docs, %d fresh (<%dh)" % (n, fresh, TTL_SEC // 3600))
        return 0

    syms: list = []
    try:
        from sepa import breakout
        syms += [r["symbol"] for r in (breakout.board(top=250).get("rows") or [])
                 if r.get("symbol")]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("board_metrics: breakout names unavailable: %s", exc)
    try:
        if d is not None:
            doc = d["growth_board"].find_one({"_id": "latest"}) or {}
            syms += [r["symbol"] for r in (doc.get("rows") or []) if r.get("symbol")]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("board_metrics: growth names unavailable: %s", exc)

    only_missing = "--all" not in args
    res = warm(syms, db=d, only_missing=only_missing)
    print("board_metrics: %d symbols, %d fetched, %d written"
          % (len(set(syms)), res["n"], res["written"]))
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_main())
