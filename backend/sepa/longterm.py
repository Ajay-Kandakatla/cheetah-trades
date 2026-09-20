"""Long-term fundamentals — the ten metrics, and a sector-relative quality score.

Ajay 2026-09-14, with a screenshot of a ten-row checklist (OPM / EPS / D/E /
ROE / ROCE / Net Profit / Promoter Holding / Cash Flow / Balance Sheet /
10 Year Sales, Profit Growth):
*"Can you add these metric, I know some of the stocks may not have 10 years."*
then, when I pushed back on putting ten more chips on an already-dense tile:
*"Move them to fundamentals tab in the individual ticker and give a score on
the fundamentals ranking for longterm."*

WHERE THE NUMBERS COME FROM
───────────────────────────
One endpoint: Massive `/vX/reference/financials?timeframe=annual`. It returns
the income statement, balance sheet and cash-flow statement per fiscal year,
as filed. AAPL answers with 17 years (2009-2025); NTSK, which IPO'd
2025-09-18, answers with one. That spread is the whole reason `coverage` is a
first-class field on every response — see SHORT HISTORY below.

Nothing here is scraped and nothing is estimated. If a line item is absent the
metric is None and says so; it is never back-filled, interpolated, or carried
forward from a prior year.

"PROMOTER HOLDING" HAS NO US EQUIVALENT — READ THIS BEFORE CHANGING IT
─────────────────────────────────────────────────────────────────────
Promoter holding is an Indian disclosure: the founding/controlling group's
stake, reported quarterly to the exchanges. US issuers file nothing of the
kind. The nearest things are insider ownership (Form 4 / DEF 14A) and
institutional ownership (13F).

Ajay's call when I raised it: *"Yeah check for any institutional volume
yourself."* So the slot is filled by INSTITUTIONAL, from two independent
readings that are deliberately kept apart rather than blended:

  * `inst_ownership_pct` — the STOCK of institutional holding, via
    `canslim.fundamentals_for` (yfinance `heldPercentInstitutions`; Massive's
    plan does not expose it). A level, updated on the 13F cadence, and by
    Rule #7 a level is never a flow.
  * `block_share_pct` — the FLOW: prints of 5,000+ shares as a share of
    volume, straight off the consolidated tape. This is the "institutional
    volume" half of what he asked for, and it is the only one of the two that
    moves daily.

They are reported side by side and neither is called "promoter holding" on any
surface he reads, because it would not be true.

THE SCORE IS MINE, NOT A BOOK'S
───────────────────────────────
I asked whether the checklist came from a source I should build to. He said
no — design it. So the weights below are MY construction and every surface
says so. This matters because of the hard boundary in `feedback_sepa_book_scope`:
Minervini's SEPA, O'Neil's CANSLIM and Kell each own their own cited formulas,
and NONE of them is the authority for a long-term quality score. This module
cites nobody and claims nobody's backing.

It is also why `SCORE_IS_MEASURED` exists below. A score labelled "long-term"
makes a forward claim, and his standing rule is that any measured number on a
board he trades ships its re-runnable script and a confidence interval, never a
bare point estimate. Until that study exists and says something, the frontend
renders this as a DESCRIPTION of the fundamentals, not a prediction about them.

RANKED AGAINST SECTOR PEERS, BY HIS CHOICE
──────────────────────────────────────────
ROCE and D/E are not comparable across sectors — a bank carries leverage that
would be a red flag in software, and a capital-light SaaS name posts a ROCE an
industrial can never reach. Ranking everything in one pool would score the
sector, not the company. So every metric is percentiled WITHIN its GICS sector
(from Mongo `companies`, 3,826 names carry one) and the composite is built from
those percentiles.

A sector needs `MIN_SECTOR_N` priced peers before it can rank anything. Below
that the response carries `ranked=False` and the raw metrics only — a
percentile against four other names is noise wearing a number.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Optional

log = logging.getLogger(__name__)

COLL = "longterm_fundamentals"
DOC_ID = "latest"

# Massive returns the full filed history; we keep at most this many fiscal
# years. Ajay asked for ten and knows many names cannot supply them.
MAX_YEARS = 12
GROWTH_YEARS = 10

# A CAGR needs a start and an end. Fewer than three points is an anecdote, so
# the growth metrics go None rather than annualising two numbers.
MIN_YEARS_FOR_CAGR = 3

# Below this, a within-sector percentile is noise. 20 keeps every real GICS
# sector in (the smallest, Utilities, has 74 names in `companies`).
MIN_SECTOR_N = 20

# Institutional "volume": prints at or above this size, as a share of tape.
BLOCK_SHARE_MIN = 5_000

# FLIP THIS ONLY WHEN A STUDY EXISTS.
# False = the frontend must present the score as a description of what the
# filings say, never as a forecast. See the module docstring.
SCORE_IS_MEASURED = False

# My weights. Named, summed and asserted so they cannot drift silently, and
# deliberately flat-ish rather than tuned — tuning them before the study exists
# would be fitting a curve to nothing.
WEIGHTS = {
    "roce": 0.18,          # return on capital employed — the compounding engine
    "roe": 0.12,           # return on equity, reported beside ROCE not merged
    "opm": 0.12,           # operating margin — pricing power
    "sales_cagr": 0.14,    # 10y revenue growth — the thing being compounded
    "profit_cagr": 0.14,   # 10y net-income growth
    "de": 0.12,            # debt/equity, INVERTED (less is better)
    "cash_conv": 0.10,     # operating cash flow / net income — is the profit real
    "inst": 0.08,          # institutional ownership + block flow
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "longterm WEIGHTS must sum to 1"

# Metrics where a LOWER raw value is better, so the percentile is flipped.
LOWER_IS_BETTER = ("de",)

# A score is only comparable to another score if a comparable amount of
# evidence voted. 0.70 was chosen from the real distribution on a 70-name
# Technology pool: the median name covers 1.00 and 97% cover >= 0.70, so this
# excludes the genuinely thin (DDOG scored 74.2 on 0.34 — third in the sector
# on a third of the evidence) without gutting the board.
MIN_COVERED_WEIGHT = 0.70

# ABSENCE IS NOT ALWAYS IGNORANCE — the trap this module would otherwise have.
#
# `profit_cagr` and `cash_conv` can be None for two completely different
# reasons, and treating them the same FLATTERS loss-making companies:
#
#   (a) the company has no history yet (NTSK: one filed year). Genuinely
#       unknown. Drop the weight and renormalise — anything else invents a
#       fact about a company nobody has data on.
#   (b) the company LOST MONEY, so there is no CAGR to compute and no earnings
#       for cash to convert. That is not missing data, it is the answer. If it
#       is renormalised away, the name is scored only on the metrics it happens
#       to be good at, and a cash-burning story ranks beside a compounder.
#
# So (b) scores at LOSS_PERCENTILE instead of dropping out. It is not zero:
# a loss-making company is not categorically worse on this axis than the worst
# profitable one in its sector, and several of these names are deliberately
# reinvesting. It is low, and it votes.
LOSS_PERCENTILE = 10.0


# ---------------------------------------------------------------------------
# Pulling and normalising the filings
# ---------------------------------------------------------------------------
def _num(v) -> Optional[float]:
    """Massive wraps each line item as {"value": x, "unit": ..., "label": ...}."""
    if isinstance(v, dict):
        v = v.get("value")
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def annual_financials(symbol: str, years: int = MAX_YEARS) -> list[dict]:
    """Filed annual statements, newest first. [] when the provider has none.

    Never raises — a fundamentals tab must degrade to "no filings" rather than
    500 a page he opens on every ticker.
    """
    try:
        import requests
        from massive_keys import stocks_key
        r = requests.get(
            "https://api.massive.com/vX/reference/financials",
            params={"ticker": str(symbol).upper(), "timeframe": "annual",
                    "limit": int(years), "apiKey": stocks_key()},
            timeout=30,
        )
        if r.status_code != 200:
            log.debug("longterm: %s financials HTTP %s", symbol, r.status_code)
            return []
        results = (r.json() or {}).get("results") or []
    except Exception as exc:                                   # noqa: BLE001
        log.debug("longterm: %s financials failed: %s", symbol, exc)
        return []

    out = []
    for row in results:
        f = row.get("financials") or {}
        inc = f.get("income_statement") or {}
        bal = f.get("balance_sheet") or {}
        cfs = f.get("cash_flow_statement") or {}
        fy = row.get("fiscal_year")
        try:
            fy = int(fy)
        except (TypeError, ValueError):
            continue
        out.append({
            "fiscal_year": fy,
            "end_date": row.get("end_date"),
            "filing_date": row.get("filing_date"),
            "revenues": _num(inc.get("revenues")),
            "operating_income": _num(inc.get("operating_income_loss")),
            "gross_profit": _num(inc.get("gross_profit")),
            "net_income": _num(inc.get("net_income_loss_attributable_to_parent"))
                          or _num(inc.get("net_income_loss")),
            "eps_diluted": _num(inc.get("diluted_earnings_per_share")),
            "eps_basic": _num(inc.get("basic_earnings_per_share")),
            "assets": _num(bal.get("assets")),
            "liabilities": _num(bal.get("liabilities")),
            "equity": _num(bal.get("equity_attributable_to_parent"))
                      or _num(bal.get("equity")),
            "current_assets": _num(bal.get("current_assets")),
            "current_liabilities": _num(bal.get("current_liabilities")),
            "long_term_debt": _num(bal.get("long_term_debt")),
            "ocf": _num(cfs.get("net_cash_flow_from_operating_activities")),
            "net_cash_flow": _num(cfs.get("net_cash_flow")),
        })
    out.sort(key=lambda r: r["fiscal_year"], reverse=True)
    return out


def _safe_div(a, b, *, pct: bool = False) -> Optional[float]:
    """a/b, or None. Guards the two ways this silently lies:

    a zero denominator, and a NEGATIVE denominator — a company with negative
    equity would otherwise post a cheerful positive ROE off a loss.
    """
    if a is None or b is None or b == 0:
        return None
    if b < 0:
        return None
    v = a / b
    if not math.isfinite(v):
        return None
    return round(v * 100, 2) if pct else round(v, 3)


def _cagr(series: list[Optional[float]]) -> Optional[float]:
    """Compound annual growth, oldest->newest, as a percent.

    None when there are too few points, or when the START is <= 0: you cannot
    annualise growth from a loss or from zero, and every library that pretends
    otherwise produces a number that reverses sign for the wrong reason.
    """
    # The span is measured in CALENDAR periods between the first and last
    # reported year, NOT in the count of non-null points. Filtering the holes
    # out first and then using len()-1 silently COMPRESSES the timeline: a
    # company with one missing filing across 100 -> [gap] -> 121 -> 133.1 would
    # annualise over 2 periods instead of 3 and report 15.4% where the truth is
    # 10.0%. Caught by test_cagr_ignores_none_holes, 2026-09-14.
    idx = [i for i, v in enumerate(series) if v is not None]
    if len(idx) < MIN_YEARS_FOR_CAGR:
        return None, "no_history"
    start, end = series[idx[0]], series[idx[-1]]
    n = idx[-1] - idx[0]
    if n <= 0 or start is None or end is None:
        return None, "no_history"
    if start <= 0 or end <= 0:
        # Loss at either end. Not a CAGR, and not ignorance either — see
        # LOSS_PERCENTILE.
        return None, "loss"
    return round(((end / start) ** (1.0 / n) - 1.0) * 100, 2), None


def metrics(symbol: str, *, rows: Optional[list[dict]] = None) -> dict:
    """The ten metrics for one symbol, plus the history behind each.

    `rows` lets the warm pass hand in an already-fetched history instead of
    paying for the same HTTP call twice.
    """
    sym = str(symbol).upper()
    rows = annual_financials(sym) if rows is None else rows
    if not rows:
        return {"symbol": sym, "ok": False, "reason": "no filed annual financials",
                "years": 0, "coverage": {}, "metrics": {}, "history": []}

    latest = rows[0]
    asc = list(reversed(rows))                    # oldest -> newest, for CAGRs

    equity = latest.get("equity")
    assets = latest.get("assets")
    curr_liab = latest.get("current_liabilities")
    capital_employed = (assets - curr_liab) if (assets is not None
                                                and curr_liab is not None) else None

    # Debt/equity: total liabilities, not just long-term debt. A name funded by
    # payables and leases is levered whether or not it issued a bond, and using
    # only `long_term_debt` grades that name as pristine.
    de = _safe_div(latest.get("liabilities"), equity)

    m = {
        "opm": _safe_div(latest.get("operating_income"), latest.get("revenues"), pct=True),
        "eps": latest.get("eps_diluted") if latest.get("eps_diluted") is not None
               else latest.get("eps_basic"),
        "de": de,
        "roe": _safe_div(latest.get("net_income"), equity, pct=True),
        "roce": _safe_div(latest.get("operating_income"), capital_employed, pct=True),
        "net_profit": latest.get("net_income"),
        "ocf": latest.get("ocf"),
        # Cash conversion is the lie detector on net profit: reported earnings
        # that never arrive as cash are the single most common way a "quality"
        # screen picks up an accrual story.
        "cash_conv": _safe_div(latest.get("ocf"), latest.get("net_income")),
        "current_ratio": _safe_div(latest.get("current_assets"), curr_liab),
    }
    sales_cagr, sales_why = _cagr([r.get("revenues") for r in asc[-GROWTH_YEARS:]])
    profit_cagr, profit_why = _cagr([r.get("net_income") for r in asc[-GROWTH_YEARS:]])
    m["sales_cagr"] = sales_cagr
    m["profit_cagr"] = profit_cagr

    # Why each absent metric is absent, so the scorer can tell "we do not know"
    # apart from "the answer is bad". Read by `score_from_percentiles`.
    ni = latest.get("net_income")
    absent = {"sales_cagr": sales_why, "profit_cagr": profit_why,
              "cash_conv": ("loss" if (ni is not None and ni <= 0)
                            else (None if m["cash_conv"] is not None else "no_history"))}
    absent = {k: v for k, v in absent.items() if v}

    growth_rows = asc[-GROWTH_YEARS:]
    coverage = {
        "years_available": len(rows),
        "years_for_growth": len(growth_rows),
        "growth_span": (f"{growth_rows[0]['fiscal_year']}–{growth_rows[-1]['fiscal_year']}"
                        if growth_rows else None),
        # Said plainly so the tab can print it rather than implying ten.
        "has_10y": len(rows) >= GROWTH_YEARS,
        "latest_fiscal_year": latest.get("fiscal_year"),
        "filing_date": latest.get("filing_date"),
    }

    return {
        "symbol": sym, "ok": True, "reason": None, "absent_because": absent,
        "years": len(rows), "coverage": coverage, "metrics": m,
        "history": [
            {"fy": r["fiscal_year"], "revenues": r.get("revenues"),
             "net_income": r.get("net_income"), "eps": r.get("eps_diluted"),
             "opm": _safe_div(r.get("operating_income"), r.get("revenues"), pct=True),
             "roe": _safe_div(r.get("net_income"), r.get("equity"), pct=True),
             "ocf": r.get("ocf"), "equity": r.get("equity"),
             "assets": r.get("assets"), "liabilities": r.get("liabilities")}
            for r in asc
        ],
    }


# ---------------------------------------------------------------------------
# The institutional slot (what stands in for "promoter holding")
# ---------------------------------------------------------------------------
def institutional(symbol: str) -> dict:
    """The two institutional readings, kept apart on purpose.

    `ownership_pct` is a 13F-cadence LEVEL; `block_share_pct` is today's FLOW.
    Rule #7: a level is never a flow, so they never get averaged into one
    number before the score's own weighting sees them.
    """
    sym = str(symbol).upper()
    own = None
    try:
        from sepa import canslim
        own = (canslim.fundamentals_for(sym) or {}).get("inst_ownership_pct")
    except Exception as exc:                                   # noqa: BLE001
        log.debug("longterm: %s inst ownership failed: %s", sym, exc)

    block = None
    try:
        block = _block_share(sym)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("longterm: %s block share failed: %s", sym, exc)

    return {"ownership_pct": own, "block_share_pct": block,
            "block_min_size": BLOCK_SHARE_MIN,
            "note": "US issuers file no promoter holding; these are the two "
                    "institutional readings that exist."}


def _block_share(symbol: str, *, day: Optional[str] = None) -> Optional[float]:
    """Share of the last completed session's volume printed in 5,000+ blocks.

    Measured off the consolidated trade tape, not inferred from daily bars.
    """
    try:
        import requests
        from massive_keys import stocks_key
        from sepa import prices
        if day is None:
            df = prices.load_prices(symbol)
            if df is None or not len(df):
                return None
            day = str(df.index[-1].date())
        total = blocks = 0
        url = (f"https://api.massive.com/v3/trades/{str(symbol).upper()}")
        params = {"timestamp": day, "limit": 50000, "apiKey": stocks_key()}
        for _ in range(20):                       # bounded: never page forever
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200:
                return None
            j = r.json() or {}
            for t in (j.get("results") or []):
                s = t.get("size") or 0
                total += s
                if s >= BLOCK_SHARE_MIN:
                    blocks += s
            nxt = j.get("next_url")
            if not nxt:
                break
            url, params = nxt, {"apiKey": stocks_key()}
        if not total:
            return None
        return round(blocks / total * 100, 2)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("longterm: %s block share failed: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Sector-relative scoring
# ---------------------------------------------------------------------------
def percentile(value: Optional[float], pool: list[float], *,
               lower_is_better: bool = False) -> Optional[float]:
    """Where `value` sits in `pool`, 0-100. None in, None out.

    Ties take the MIDPOINT of the tied block rather than the bottom, so a
    sector where forty names all post a D/E of 0.00 does not hand thirty-nine
    of them a zero and one of them a 100.
    """
    if value is None:
        return None
    clean = [p for p in pool if p is not None and math.isfinite(p)]
    if len(clean) < MIN_SECTOR_N:
        return None
    below = sum(1 for p in clean if p < value)
    equal = sum(1 for p in clean if p == value)
    pct = (below + equal / 2.0) / len(clean) * 100.0
    if lower_is_better:
        pct = 100.0 - pct
    return round(pct, 1)


def score_from_percentiles(pcts: dict, absent_because: Optional[dict] = None) -> dict:
    """Weighted composite of the percentiles, renormalised over what voted.

    `covered_weight` reports the weight that actually voted, so a 71 backed by
    a third of the weights can be told apart from a 71 backed by all of them —
    and `ranked` is False below MIN_COVERED_WEIGHT, because those two 71s are
    not the same number and should not sit in one ranking.

    `absent_because` carries the reason codes from `metrics()`. A metric absent
    for reason "loss" is NOT renormalised away — it scores LOSS_PERCENTILE and
    votes. Without that, a company that lost money every year is scored purely
    on the metrics it is good at. See the comment on LOSS_PERCENTILE.
    """
    absent_because = absent_because or {}
    num = den = 0.0
    used, imputed = [], []
    for key, w in WEIGHTS.items():
        p = pcts.get(key)
        if p is None:
            if absent_because.get(key) == "loss":
                p = LOSS_PERCENTILE
                imputed.append(key)
            else:
                continue
        else:
            used.append(key)
        num += w * p
        den += w
    if den <= 0:
        return {"score": None, "covered_weight": 0.0, "used": [], "imputed": [],
                "ranked": False, "reason": "no metric had a sector percentile"}
    covered = round(den, 3)
    return {"score": round(num / den, 1),
            "covered_weight": covered,
            "used": sorted(used),
            "imputed": sorted(imputed),
            "ranked": covered >= MIN_COVERED_WEIGHT,
            "reason": None if covered >= MIN_COVERED_WEIGHT
                      else f"only {covered:.2f} of the weights could be scored "
                           f"(floor {MIN_COVERED_WEIGHT})"}


# ---------------------------------------------------------------------------
# The cross-section: one cron walks the universe, the ticker page reads it
# ---------------------------------------------------------------------------
# Same shape as `turning_bullish.warm` and `zone_store.warm`. NEVER on the
# request path: one HTTP call per name against 2,685 names is a cron job, not
# something to do while he waits for a tab.
#
# `_block_share` is deliberately NOT called here. It pages the raw trade tape,
# and doing that for the whole universe would hammer a provider we have already
# watched refuse connections under burst load today (297 chunk failures in one
# rotation rebuild, 2026-09-14). It is a per-symbol read on the ticker page.
DEFAULT_WORKERS = 6


def _db():
    try:
        from sepa import prices
        return prices._get_mongo().database
    except Exception as exc:                                   # noqa: BLE001
        log.warning("longterm: mongo unavailable: %s", exc)
        return None


def _sector_map(db=None) -> dict:
    """symbol -> GICS sector, from Mongo `companies`. Missing sectors stay out."""
    db = db if db is not None else _db()
    if db is None:
        return {}
    from companies.sector_overrides import apply as _fix_sector
    out = {}
    for c in db["companies"].find({}, {"symbol": 1, "sector": 1, "industry": 1}):
        # THIS READ BYPASSES companies.store, so it must heal for itself
        # (Ajay 2026-09-19). It is also the read with the most damage: the
        # peer POOL is built from it, so a miner filed under Capital Markets
        # was scored against 406 banks and asset managers on ROCE, ROE and D/E.
        s = ((_fix_sector(c) or c).get("sector") or "").strip()
        if s:
            out[str(c.get("symbol", "")).upper()] = s
    return out


def warm(universe=None, max_workers: int = DEFAULT_WORKERS, db=None) -> dict:
    """Compute every name's metrics, percentile within sector, store one doc."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if universe is None:
        try:
            from sepa.universe import load_universe
            universe = load_universe()
        except Exception as exc:                               # noqa: BLE001
            log.warning("longterm: universe failed: %s", exc)
            return {"ok": False, "reason": "no universe"}

    syms = sorted({str(s).upper() for s in universe})
    sectors = _sector_map(db)
    rows, failed = {}, 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(metrics, s): s for s in syms}
        for fut in as_completed(futs):
            s = futs[fut]
            try:
                r = fut.result()
            except Exception:                                  # noqa: BLE001
                failed += 1
                continue
            if not r.get("ok"):
                failed += 1
                continue
            rows[s] = {"m": r["metrics"], "coverage": r["coverage"],
                       "absent_because": r.get("absent_because") or {},
                       "sector": sectors.get(s)}

    # Institutional OWNERSHIP joins the cross-section; the block-share half does
    # not (it pages the raw tape — see the note above this function).
    #
    # This runs on the pool, not in a for-loop. It is a yfinance round-trip per
    # name, and serially over ~2,685 names that is hours, not minutes — it would
    # quietly turn a 35-minute cron into one that never finishes inside its
    # window.
    def _inst(sym):
        try:
            from sepa import canslim
            return sym, (canslim.fundamentals_for(sym) or {}).get("inst_ownership_pct")
        except Exception:                                      # noqa: BLE001
            return sym, None

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sym, val in ex.map(_inst, list(rows)):
            rows[sym]["m"]["inst"] = val

    pools: dict[str, dict[str, list]] = {}
    for s, row in rows.items():
        sec = row.get("sector")
        if not sec:
            continue
        p = pools.setdefault(sec, {})
        for key in WEIGHTS:
            p.setdefault(key, []).append(row["m"].get(key))

    ranked = 0
    for s, row in rows.items():
        sec = row.get("sector")
        pool = pools.get(sec or "", {})
        pcts = {}
        for key in WEIGHTS:
            pcts[key] = percentile(row["m"].get(key), pool.get(key, []),
                                   lower_is_better=(key in LOWER_IS_BETTER))
        row["pcts"] = pcts
        row["score"] = score_from_percentiles(pcts, row.get("absent_because"))
        if row["score"].get("ranked"):
            ranked += 1

    doc = {
        "_id": DOC_ID,
        "built_at": time.time(),
        "built_at_iso": _et_iso(),
        "n_scanned": len(syms),
        "n_rows": len(rows),
        "n_failed": failed,
        "n_ranked": ranked,
        "sector_n": {sec: len(v.get("roce", [])) for sec, v in pools.items()},
        "weights": dict(WEIGHTS),
        "score_is_measured": SCORE_IS_MEASURED,
        "rows": rows,
    }
    db = db if db is not None else _db()
    if db is not None:
        db[COLL].replace_one({"_id": DOC_ID}, doc, upsert=True)
    return {"ok": True, "scanned": len(syms), "rows": len(rows),
            "failed": failed, "ranked": ranked, "sectors": len(pools)}


def _et_iso() -> str:
    import datetime
    import zoneinfo
    return datetime.datetime.now(zoneinfo.ZoneInfo("America/New_York")).isoformat(timespec="seconds")


def stored(db=None) -> dict:
    db = db if db is not None else _db()
    if db is None:
        return {}
    return db[COLL].find_one({"_id": DOC_ID}) or {}


def score_for(symbol: str, db=None) -> dict:
    """Everything the ticker page's Fundamentals tab needs for one name.

    Answers 200-shaped even when the name has never been warmed: a tab that
    500s on a thin ticker is worse than one that says "not scored yet".
    """
    sym = str(symbol).upper()
    doc = stored(db)
    row = ((doc.get("rows") or {}).get(sym)) or {}
    live = metrics(sym)
    inst = institutional(sym)

    sec = row.get("sector")
    sector_n = (doc.get("sector_n") or {}).get(sec or "", 0)
    sc = row.get("score") or {}
    ranked = bool(sc.get("ranked"))

    return {
        "symbol": sym,
        "ok": live.get("ok", False),
        "reason": live.get("reason"),
        "sector": sec,
        "sector_n": sector_n,
        "ranked": ranked,
        "rank_basis": "sector peers" if ranked else None,
        "min_sector_n": MIN_SECTOR_N,
        "score": sc.get("score"),
        "covered_weight": sc.get("covered_weight"),
        "min_covered_weight": MIN_COVERED_WEIGHT,
        "score_used": sc.get("used") or [],
        "score_imputed": sc.get("imputed") or [],
        "score_reason": sc.get("reason"),
        "absent_because": live.get("absent_because") or {},
        "percentiles": row.get("pcts") or {},
        "weights": dict(WEIGHTS),
        "metrics": live.get("metrics") or {},
        "coverage": live.get("coverage") or {},
        "history": live.get("history") or [],
        "institutional": inst,
        # The frontend reads THIS, not a hardcoded string, to decide whether it
        # may use forward-looking language about the score.
        "score_is_measured": SCORE_IS_MEASURED,
        "score_origin": "Cheetah's own composite — not from any book or "
                        "published methodology. Weights are stated in `weights`.",
        "built_at_iso": doc.get("built_at_iso"),
        "stale": (time.time() - float(doc.get("built_at") or 0)) > 8 * 24 * 3600
                 if doc.get("built_at") else True,
    }


if __name__ == "__main__":                                     # pragma: no cover
    # `python -m sepa.longterm warm` — the Sunday cron entry point.
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "warm":
        print(warm())
    else:
        print("usage: python -m sepa.longterm warm")
