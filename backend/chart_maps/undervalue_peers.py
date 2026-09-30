"""🏷️ Under Value → "vs peers" view (Ajay 2026-09-29).

The ask, verbatim: "create me another tab where valuations are wrong based on
analytics, this is purely driven by wrong valuation of the stocks in the whole
universe we have.. What I am looking for is great sales growth, annual review
but Market cap and stock price is very low at least 50% low compared to
peers." — then "Use the same tab actually".

So this is a served, URL-persisted TOGGLE on the existing 💎 Under Value tab
(`?uv=peers`). The 💎 P/S ÷ growth board stays the default and is not touched
(`board.undervalue_tiles` is byte-identical, pinned by a golden captured before
this module existed).

What this view reads, once per scan and ET date:
  * population  = the latest scan's `all_results` rows (sector, industry, close)
  * revenue     = the last QUARTERS_FOR_TTM ADJACENT reported quarters from
                  `research.decision_snapshot` (never `rev_ttm`: two revenue
                  sources inside one median would be two answers)
  * market cap  = `promo_circuit.market_caps_for(..., cap=0)` — stored share
                  count × the scan's close, no provider call
  * peers       = same (industry, sector), else the sector when the industry has
                  under MIN_PEERS readable peers; the name is NEVER in its own
                  median (`capital_quality._median`). Round 2 (2026-09-29): a
                  peer must itself clear MIN_TTM_REVENUE_USD (positive revenue
                  and cap by construction) — a $20M name at 80x sales no longer
                  lifts the median a $1B name is measured against
  * red flags   = `capital_quality.for_row` definitional FAILs on
                  `board_metrics.attach` rows

UNMEASURED (`MEASURED = False`): no study in this app says a name at half its
peers' sales multiple does better afterwards. Display only — nothing here
gates, pushes, sizes or enters a trade. The share price itself is never
compared across companies; only what the whole company is valued at per
dollar of sales.

Every threshold below is HIS CALL (docs/chart_maps/undervalue_peers_2026_09_29.md).
"""
from __future__ import annotations

import logging
import math
import threading
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from growth.capital_quality import _median
from sepa import qoq
from sepa.board_metrics import NON_OPERATING_SECTORS, QUARTERS_FOR_TTM
from sepa.cap_warm import DERIVED_FLOAT

log = logging.getLogger("chart_maps.undervalue_peers")

ET = ZoneInfo("America/New_York")

MARK = "\U0001F3F7️"            # 🏷️ (VS16 included — FE literal must match)
MEASURED = False
VIEW_PARAM = "uv"
VIEW_PSG = "psg"                     # the existing 💎 board, default
VIEW_PEERS = "peers"
VIEWS = (VIEW_PSG, VIEW_PEERS)
PSG_VIEW_LABEL = "\U0001F48E P/S ÷ growth"         # 💎 P/S ÷ growth
PEERS_VIEW_LABEL = MARK + " vs peers"               # 🏷️ vs peers
PEER_PS_MAX_FRACTION = 0.50          # HIS 50% — P/S at most half the peer median (inclusive). HIS CALL
MIN_PEERS = 5                        # usable P/S peers, self excluded, for a group. HIS CALL
MIN_SALES_YOY_Q_PCT = 20.0           # latest quarter vs a year earlier. HIS CALL
MIN_SALES_TTM_GROWTH_PCT = 20.0      # last 4 quarters vs the 4 before. HIS CALL
MIN_TTM_REVENUE_USD = 100_000_000.0  # HIS CALL
MEMO_TTL_SEC = 30 * 60               # cache freshness, NOT a rule
GROUP_INDUSTRY, GROUP_SECTOR = "industry", "sector"

COUNT_KEYS = ("scanned", "no_sector", "no_fundamentals", "currency_unverified",
              "no_ttm_revenue", "nonpositive_revenue", "no_cap", "cap_lower_bound",
              "usable", "no_peer_group", "not_cheap", "under_revenue_floor",
              "q_growth_not_read", "q_growth_short", "ttm_growth_not_read",
              "ttm_growth_short", "passed", "sector_fallback", "ev_compared",
              "cpa_not_read", "dropped_thin")
NOT_READ_KEYS = ("no_sector", "no_fundamentals", "currency_unverified",
                 "no_ttm_revenue", "no_cap", "cap_lower_bound")

# The four definitional capital-quality cuts (sign tests, no chosen constant).
CPA_KEYS = ("net_cash", "positive_fcf", "no_dilution", "positive_roce")

NOTE = (f"{MARK} UNMEASURED — no study in this app says a name valued at half its peers' "
        f"sales multiple does better afterwards. Cheap is often cheap for a reason — margins, "
        f"debt, dilution, a one-off quarter — and the chips on each card are there to show it. "
        f"Valuation is market cap ÷ the last four reported quarters of revenue, against the "
        f"median of the name's industry peers (its sector when the industry has fewer than "
        f"{MIN_PEERS} readable peers); peers count only when they too have at least "
        f"${MIN_TTM_REVENUE_USD / 1e6:.0f}M of revenue, and a name is never part of its own "
        f"median. The share price "
        f"itself is never compared across companies — only what the whole company is valued at "
        f"per dollar of sales. Revenue is as of the last reported quarter; market cap is the "
        f"stored share count (dated by when it was fetched) × the scan's close (dated by when "
        f"the scan ran), both on each card. The 💎 view ranks P/S ÷ "
        f"growth inside the fast-growth list; this view ranks the discount to peers across the "
        f"whole scan. Nothing here gates, pushes, sizes or enters a trade.")
EMPTY_NOTE = f"{MARK} No name passes all four legs right now — the line above says where each fell out."

# Round 2 (2026-09-29): an outage must never read as "no name passes". A build
# that could not compare anything carries one of these `error` keys (or an
# exception's type name), is never memoised, and the header says so.
ERR_NO_SCAN = "no_scan"
ERR_NO_SECTOR = "no_sector"
ERR_NO_FUNDAMENTALS = "no_fundamentals"
ERR_NO_USABLE = "no_usable"
_PHASE_WORDS = {"reached": "in the demand band only",
                "approaching": "approaching the band only"}

_memo: dict = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    """A finite float, or None. NaN / inf / bool never leave."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or math.isinf(f)) else f


def _zero_counts() -> dict:
    return {k: 0 for k in COUNT_KEYS}


def parse_view(v) -> str:
    """VIEW_PEERS iff the value reads 'peers'; anything else (None, '', a
    FastAPI Query object from a direct in-container call) is the 💎 view."""
    if isinstance(v, str) and v.strip().lower() == VIEW_PEERS:
        return VIEW_PEERS
    return VIEW_PSG


def ttm_revenue(rev_q_series, periods=None, offset: int = 0) -> Optional[float]:
    """Sum of QUARTERS_FOR_TTM reported quarters starting at `offset`.

    None unless every slot is a finite number AND the first and last slots are
    exactly QUARTERS_FOR_TTM-1 fiscal quarters apart (`qoq._adjacent` — Massive
    OMITS a quarter it does not have, so list position is not adjacency). The
    sum may be <= 0; the caller decides what that means."""
    rev = list(rev_q_series or [])
    if len(rev) < offset + QUARTERS_FOR_TTM:
        return None
    vals = [_f(x) for x in rev[offset:offset + QUARTERS_FOR_TTM]]
    if any(v is None for v in vals):
        return None
    if not qoq._adjacent(periods, offset, offset + QUARTERS_FOR_TTM - 1,
                         gap=QUARTERS_FOR_TTM - 1):
        return None
    return float(sum(vals))


def ttm_growth_pct(rev_q_series, periods=None) -> Optional[float]:
    """Trailing-year revenue vs the trailing year before it, in %. None when
    either year cannot be read, the prior year is <= 0, or the eight quarters
    are not contiguous."""
    a = ttm_revenue(rev_q_series, periods, 0)
    b = ttm_revenue(rev_q_series, periods, QUARTERS_FOR_TTM)
    if a is None or b is None or b <= 0:
        return None
    if not qoq._adjacent(periods, 0, 2 * QUARTERS_FOR_TTM - 1,
                         gap=2 * QUARTERS_FOR_TTM - 1):
        return None
    return round((a - b) / b * 100.0, 1)


def q_yoy_pct(snap) -> Optional[float]:
    """The latest quarter's YoY sales growth (`sales.growth_yoy_pct`), or None
    when the headline pair is not four quarters apart or the year-ago quarter
    is <= 0 (growth/tracker E4 precedent)."""
    snap = snap if isinstance(snap, dict) else {}
    g = _f((snap.get("sales") or {}).get("growth_yoy_pct"))
    if g is None:
        return None
    if not qoq.yoy_pairs_ok(snap.get("q_period_series"), pairs=(qoq.HEADLINE_PAIR,)):
        return None
    rev = list(snap.get("rev_q_series") or [])
    j = qoq.HEADLINE_PAIR[1]
    if len(rev) > j:
        base = _f(rev[j])
        if base is not None and base <= 0:
            return None
    return g


def _group_index(labels: dict, usable: dict) -> dict:
    """{("i", industry, sector): [syms]} and {("s", sector): [syms]} over the
    usable names only."""
    idx: dict = {}
    for s in sorted(usable):
        sec, ind = (labels.get(s) or (None, None))
        if not sec:
            continue
        if ind:
            idx.setdefault(("i", str(ind), str(sec)), []).append(s)
        idx.setdefault(("s", str(sec)), []).append(s)
    return idx


def peer_group(sym, labels: dict, usable: dict, *, _index: Optional[dict] = None
               ) -> tuple:
    """(group_kind, group_label, peers) for `sym`, self excluded.

    `usable` is the PEER POOL {SYM: ps} — build() passes only names that clear
    MIN_TTM_REVENUE_USD. Industry peers = pool names with the same (industry, sector); at least
    MIN_PEERS → the industry. Else the sector's usable names (self excluded) at
    least MIN_PEERS → the sector. Else (None, None, []). A name with a sector
    but no industry goes straight to the sector test. `_index` is a
    precomputed `_group_index` (build() passes one; the answer is identical)."""
    idx = _index if _index is not None else _group_index(labels, usable)
    sec, ind = (labels.get(sym) or (None, None))
    if not sec:
        return None, None, []
    if ind:
        peers = [p for p in idx.get(("i", str(ind), str(sec)), []) if p != sym]
        if len(peers) >= MIN_PEERS:
            return GROUP_INDUSTRY, str(ind), peers
    peers = [p for p in idx.get(("s", str(sec)), []) if p != sym]
    if len(peers) >= MIN_PEERS:
        return GROUP_SECTOR, str(sec), peers
    return None, None, []


def _et_date(ts) -> Optional[str]:
    """ET calendar date (iso) of an epoch number or a datetime; None if unreadable."""
    try:
        if isinstance(ts, datetime):
            d = ts if ts.tzinfo else ts.replace(tzinfo=ZoneInfo("UTC"))
            return d.astimezone(ET).date().isoformat()
        f = _f(ts)
        if f is None or f <= 0:
            return None
        return datetime.fromtimestamp(f, tz=ET).date().isoformat()
    except Exception:                                          # noqa: BLE001
        return None


def _peer_growth(peers: list, info: dict, key: str) -> tuple:
    vals = [info[p][key] for p in peers if info.get(p, {}).get(key) is not None]
    n = len(vals)
    return (_median(vals) if n >= MIN_PEERS else None), n


# ---------------------------------------------------------------------------
# build — the funnel, one bucket per name
# ---------------------------------------------------------------------------
def build(rows: list, snaps: dict, caps: dict, cap_meta: dict,
          generation=None, scan_generated_at=None) -> dict:
    """PURE. The per-name funnel (docs §3.3). Every scan name lands in exactly
    one bucket; `passed` rows are ordered deepest discount first, ties by
    symbol.

    `generation` is the scan FILE's mtime — a memo key only: any later rewrite
    of the file (an insider sweep after midnight) moves it. The card's "close
    {date}" is the ET date of the scan's OWN `generated_at` (round 2,
    2026-09-29 — the mtime read 2026-09-30, a session not yet traded)."""
    counts = _zero_counts()
    snaps = snaps if isinstance(snaps, dict) else {}
    caps = caps if isinstance(caps, dict) else {}
    cap_meta = cap_meta if isinstance(cap_meta, dict) else {}
    scanned_at_date = _et_date(scan_generated_at)

    labels: dict = {}
    info: dict = {}           # usable names only
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or "").strip().upper()
        if not sym:
            continue
        counts["scanned"] += 1
        sec = r.get("sector")
        if not sec:
            counts["no_sector"] += 1
            continue
        ind = r.get("industry") or None
        labels[sym] = (str(sec), str(ind) if ind else None)
        snap = snaps.get(sym)
        if not isinstance(snap, dict):
            counts["no_fundamentals"] += 1
            continue
        if snap.get("_source") == "yfinance":
            counts["currency_unverified"] += 1
            continue
        rev = snap.get("rev_q_series")
        periods = snap.get("q_period_series")
        ttm = ttm_revenue(rev, periods, 0)
        if ttm is None:
            counts["no_ttm_revenue"] += 1
            continue
        if ttm <= 0:
            counts["nonpositive_revenue"] += 1
            continue
        cap = _f(caps.get(sym))
        if cap is None or cap <= 0:
            counts["no_cap"] += 1
            continue
        meta = cap_meta.get(sym) or {}
        if meta.get("cap_source") == DERIVED_FLOAT:
            counts["cap_lower_bound"] += 1
            continue
        counts["usable"] += 1
        plist = list(periods or [])
        info[sym] = {
            "ps": cap / ttm, "ttm": ttm, "cap": cap,
            "q_yoy": q_yoy_pct(snap), "ttm_g": ttm_growth_pct(rev, periods),
            "periods": plist, "source": snap.get("_source"),
            "sales": snap.get("sales") or {}, "row": r, "meta": meta,
        }

    usable_ps = {s: v["ps"] for s, v in info.items()}
    # The peer pool: usable names (positive revenue, positive full cap) that
    # ALSO clear the same revenue floor a pass needs. The candidate itself is
    # still measured whatever its size (a sub-floor name lands in
    # `under_revenue_floor` below); self is excluded inside peer_group.
    peer_ps_pool = {s: v["ps"] for s, v in info.items()
                    if v["ttm"] >= MIN_TTM_REVENUE_USD}
    idx = _group_index(labels, peer_ps_pool)
    passed = []
    for sym in sorted(info):
        it = info[sym]
        kind, label, peers = peer_group(sym, labels, peer_ps_pool, _index=idx)
        if kind is None:
            counts["no_peer_group"] += 1
            continue
        peer_ps = _median([usable_ps[p] for p in peers])
        if peer_ps is None or peer_ps <= 0:
            counts["no_peer_group"] += 1
            continue
        ratio = it["ps"] / peer_ps
        if ratio > PEER_PS_MAX_FRACTION:
            counts["not_cheap"] += 1
            continue
        if it["ttm"] < MIN_TTM_REVENUE_USD:
            counts["under_revenue_floor"] += 1
            continue
        if it["q_yoy"] is None:
            counts["q_growth_not_read"] += 1
            continue
        if it["q_yoy"] < MIN_SALES_YOY_Q_PCT:
            counts["q_growth_short"] += 1
            continue
        if it["ttm_g"] is None:
            counts["ttm_growth_not_read"] += 1
            continue
        if it["ttm_g"] < MIN_SALES_TTM_GROWTH_PCT:
            counts["ttm_growth_short"] += 1
            continue
        counts["passed"] += 1
        if kind == GROUP_SECTOR:
            counts["sector_fallback"] += 1
        q_med, q_n = _peer_growth(peers, info, "q_yoy")
        g_med, g_n = _peer_growth(peers, info, "ttm_g")
        sec, ind = labels[sym]
        meta = it["meta"]
        periods = it["periods"]
        passed.append({
            "symbol": sym, "sector": sec, "industry": ind,
            "group_kind": kind, "group_label": label, "peer_n": len(peers),
            "peers": list(peers),
            "ps": it["ps"], "peer_ps_median": peer_ps, "ratio": ratio,
            "discount_pct": round((1.0 - ratio) * 100.0, 1),
            "ttm_revenue": it["ttm"],
            "revenue_period": (qoq.period_label(periods[0], it["source"])
                               if periods else None),
            "market_cap": it["cap"],
            "cap_as_of": _et_date(meta.get("as_of")),
            "cap_basis": "shares" if meta.get("has_shares") else "stored",
            "scanned_at_date": scanned_at_date,
            "q_yoy_pct": it["q_yoy"], "q_yoy_peer_median": q_med, "q_yoy_peer_n": q_n,
            "ttm_growth_pct": it["ttm_g"], "ttm_growth_peer_median": g_med,
            "ttm_growth_peer_n": g_n,
            "non_operating": sec in NON_OPERATING_SECTORS,
            "sales": it["sales"], "scan_row": it["row"],
        })
    passed.sort(key=lambda p: (p["ratio"], p["symbol"]))
    return {"passed": passed, "counts": counts, "generation": generation,
            "scanned_at_date": scanned_at_date}


def build_failure(counts: dict) -> Optional[str]:
    """PURE. The `error` key when a build compared nothing because an INPUT was
    missing (no scan rows, no sector labels, no fundamentals, no readable P/S
    at all) — None for a real answer, including a real zero-pass answer."""
    c = {k: int((counts or {}).get(k) or 0) for k in COUNT_KEYS}
    if c["scanned"] <= 0:
        return ERR_NO_SCAN
    if c["no_sector"] >= c["scanned"]:
        return ERR_NO_SECTOR
    if c["no_fundamentals"] >= c["scanned"] - c["no_sector"]:
        return ERR_NO_FUNDAMENTALS
    if c["usable"] <= 0:
        return ERR_NO_USABLE
    return None


# ---------------------------------------------------------------------------
# enrich — EV/Sales, CPA red flags, next ER (PURE)
# ---------------------------------------------------------------------------
def enrich(entry: dict, bm_rows: dict, er_map: dict) -> dict:
    """PURE: a new entry with EV/Sales vs peers, the CPA definitional fails and
    the next earnings date on each passed row; peer lists stripped."""
    from growth import capital_quality as cq

    bm_rows = bm_rows if isinstance(bm_rows, dict) else {}
    er_map = er_map if isinstance(er_map, dict) else {}
    counts = dict((entry or {}).get("counts") or _zero_counts())
    out_rows = []
    for src in (entry or {}).get("passed") or []:
        row = dict(src)
        sym = row["symbol"]
        peers = row.pop("peers", None) or []
        bm = bm_rows.get(sym)

        ev, ev_na = None, None
        if isinstance(bm, dict):
            if bm.get("balance_meaningful") is False:
                ev_na = row.get("sector")
            else:
                ev = _f(bm.get("ev_sales"))
        pv = []
        for p in peers:
            pb = bm_rows.get(p)
            if not isinstance(pb, dict) or pb.get("balance_meaningful") is False:
                continue
            v = _f(pb.get("ev_sales"))
            if v is not None:
                pv.append(v)
        ev_n = len(pv)
        ev_med = _median(pv) if ev_n >= MIN_PEERS else None
        below = (ev < ev_med) if (ev is not None and ev_med is not None) else None
        if below is not None:
            counts["ev_compared"] = counts.get("ev_compared", 0) + 1
        row.update({"ev_sales": ev, "ev_peer_median": ev_med, "ev_peer_n": ev_n,
                    "ev_below_peers": below, "ev_na_sector": ev_na})

        if not isinstance(bm, dict):
            row.update({"cpa_read": False, "cpa_fails": []})
            counts["cpa_not_read"] = counts.get("cpa_not_read", 0) + 1
        else:
            comps = (cq.for_row(bm) or {}).get("components") or {}
            fails = [k for k in CPA_KEYS
                     if (comps.get(k) or {}).get("verdict") == cq.FAIL]
            row.update({"cpa_read": True, "cpa_fails": fails})
            for k in ("cash", "debt", "fcf_yield", "shares_yoy_pct", "roce_pct"):
                row[k] = _f(bm.get(k))

        er = er_map.get(sym) if isinstance(er_map.get(sym), dict) else {}
        nd = er.get("next_date")
        row["next_er"] = str(nd) if nd else None
        wh = er.get("when")
        row["er_when"] = str(wh) if wh else None
        out_rows.append(row)
    new = dict(entry or {})
    new["passed"] = out_rows
    new["counts"] = counts
    return new


# ---------------------------------------------------------------------------
# served words
# ---------------------------------------------------------------------------
def _usd(v) -> str:
    from chart_maps.board import _usd_short
    return _usd_short(v)


def failure_why(error, counts: Optional[dict] = None) -> str:
    """Plain words for a failed read's `error` key."""
    c = {k: int((counts or {}).get(k) or 0) for k in COUNT_KEYS}
    if error == ERR_NO_SCAN:
        return "no scan rows on disk (the latest scan file is missing, unreadable or empty)"
    if error == ERR_NO_SECTOR:
        return f"none of the {c['scanned']} scan rows carried a sector label"
    if error == ERR_NO_FUNDAMENTALS:
        return (f"no fundamentals came back for any of the {c['scanned']} scan names "
                f"(the research cache read returned nothing)")
    if error == ERR_NO_USABLE:
        return (f"none of the {c['scanned']} scan names had a readable P/S "
                f"(market caps or revenue did not come back)")
    return f"{error or 'an unknown error'} while reading the inputs"


def header(counts: dict, error: Optional[str] = None) -> str:
    """The served funnel line, built only from counts + constants. With an
    `error` it says the READ failed and why — never the empty-list wording."""
    c = {k: int((counts or {}).get(k) or 0) for k in COUNT_KEYS}
    if error:
        return (f"{MARK} The vs-peers read failed — {failure_why(error, c)}. Nothing was "
                f"compared, so an empty board here does NOT mean no name is cheap; it "
                f"retries on the next load.")
    return (f"{MARK} {c['passed']} at ≤ {PEER_PS_MAX_FRACTION:.0%} of their peers' P/S with "
            f"sales ≥ +{MIN_SALES_YOY_Q_PCT:.0f}% (latest quarter) and ≥ "
            f"+{MIN_SALES_TTM_GROWTH_PCT:.0f}% (trailing year) on ≥ "
            f"{_usd(MIN_TTM_REVENUE_USD)} revenue — {c['usable']} of {c['scanned']} scan "
            f"names had a readable P/S. Not read: {c['no_fundamentals']} no fundamentals, "
            f"{c['currency_unverified']} revenue currency unverified, {c['no_ttm_revenue']} "
            f"no four clean quarters, {c['no_cap']} no market cap, {c['cap_lower_bound']} cap "
            f"only a float lower bound, {c['no_sector']} no sector. Among the cheap ones, "
            f"{c['q_growth_not_read']} quarterly and {c['ttm_growth_not_read']} trailing-year "
            f"growth not read. {c['sector_fallback']} compared with their sector; EV/Sales vs "
            f"peers read for {c['ev_compared']} of {c['passed']}.")


def hidden_note(passed: int, *, phase: str = "all", phase_hidden: int = 0,
                no_prices: int = 0, min_tier: str = "", dropped_thin: int = 0,
                no_bars: int = 0) -> str:
    """The empty-board line when names DID pass the four legs but a board
    filter (or missing price data) hid every one of them."""
    parts = []
    if phase_hidden:
        parts.append(f"{phase_hidden} hidden by the phase filter "
                     f"({_PHASE_WORDS.get(phase, phase)})")
    if dropped_thin:
        parts.append(f"{dropped_thin} under the liquidity floor ({min_tier})")
    if no_prices:
        parts.append(f"{no_prices} with no price history on file")
    if no_bars:
        parts.append(f"{no_bars} whose chart bars did not load")
    why = "; ".join(parts) if parts else "hidden by the board's filters"
    return (f"{MARK} {passed} passed all four legs, but none is on the board: {why}. "
            f"Widen the filter to see them.")


def _growth_v(g, med) -> str:
    peers = f"peers {med:+.0f}%" if med is not None else "peers n/r"
    return f"{g:+.0f}% · {peers}"


def tile_parts(row: dict) -> dict:
    """{"stats", "badges", "why"} for one passed row — every word and number
    served (no maths in the TSX). The 🟢 sales badge is NOT here: the board
    builder slots the shared `_sales_badge` in after badge 0."""
    ps, med = row["ps"], row["peer_ps_median"]
    disc, n = row["discount_pct"], row["peer_n"]
    sector, industry = row.get("sector"), row.get("industry")
    is_sector = row.get("group_kind") == GROUP_SECTOR
    ev, ev_med = row.get("ev_sales"), row.get("ev_peer_median")
    q, qm = row.get("q_yoy_pct"), row.get("q_yoy_peer_median")
    g, gm = row.get("ttm_growth_pct"), row.get("ttm_growth_peer_median")

    if row.get("ev_na_sector"):
        ev_v = f"n/a · {row['ev_na_sector']}"
    elif ev is not None and ev_med is not None:
        ev_v = f"{ev:.1f}x vs {ev_med:.1f}x"
    elif ev is not None:
        ev_v = f"{ev:.1f}x · peers not read ({row.get('ev_peer_n', 0)} of {n})"
    else:
        ev_v = "not read"

    cap = row["market_cap"]
    if row.get("cap_basis") == "shares":
        cap_v = (f"{_usd(cap)} · shares fetched {row.get('cap_as_of') or 'undated'} × close "
                 f"{row.get('scanned_at_date') or 'undated'}")
    else:
        cap_v = f"{_usd(cap)} · stored {row.get('cap_as_of') or 'undated'}"

    er_v = (f"{row['next_er']} {row.get('er_when') or ''}".strip()
            if row.get("next_er") else "not on file")

    stats = [
        {"k": "P/S", "v": f"{ps:.1f}x"},
        {"k": "Peer P/S", "v": f"{med:.1f}x"},
        {"k": "vs peers", "v": f"{disc:.0f}% below"},
        {"k": "Peers", "v": (f"{sector} (sector) · {n}" if is_sector
                             else f"{row['group_label']} · {n}")},
        {"k": "EV/Sales", "v": ev_v},
        {"k": "Sales YoY Q", "v": _growth_v(q, qm)},
        {"k": "Sales TTM", "v": _growth_v(g, gm)},
        {"k": "TTM rev", "v": f"{_usd(row['ttm_revenue'])} · "
                              f"{row.get('revenue_period') or 'quarter n/r'}"},
        {"k": "Mkt cap", "v": cap_v},
        {"k": "Next ER", "v": er_v},
    ]
    if row.get("cpa_read") is False:
        stats.append({"k": "CPA", "v": "not read"})

    badges = [{"text": f"{MARK} {ps:.1f}x sales vs peers' {med:.1f}x — {disc:.0f}% below",
               "tone": "good"}]
    if row.get("ev_below_peers") is False:
        badges.append({"text": f"⚠️ EV/Sales {ev:.1f}x is not below peers' {ev_med:.1f}x",
                       "tone": "warn"})
    if is_sector:
        badges.append({"text": f"⚖️ Sector peers — {industry or 'no industry'} had under "
                               f"{MIN_PEERS} readable", "tone": "warn"})
    if row.get("non_operating"):
        badges.append({"text": f"⚖️ {sector}: sales multiples read differently here",
                       "tone": "warn"})
    fails = row.get("cpa_fails") or []
    if "net_cash" in fails:
        badges.append({"text": f"🏦 Net debt — cash {_usd(row.get('cash'))} vs debt "
                               f"{_usd(row.get('debt'))}", "tone": "warn"})
    if "positive_fcf" in fails and row.get("fcf_yield") is not None:
        badges.append({"text": f"🔥 Burning cash — FCF yield {row['fcf_yield']:+.1f}%",
                       "tone": "warn"})
    if "no_dilution" in fails and row.get("shares_yoy_pct") is not None:
        badges.append({"text": f"🩸 Diluting — shares {row['shares_yoy_pct']:+.1f}% YoY",
                       "tone": "warn"})
    if "positive_roce" in fails and row.get("roce_pct") is not None:
        badges.append({"text": f"📉 Negative ROCE {row['roce_pct']:+.1f}%", "tone": "warn"})

    group_word = f"{sector} sector" if is_sector else str(row.get("group_label"))
    why = (f"Valued at {ps:.1f}x sales, {disc:.0f}% below the median of {n} {group_word} "
           f"peers ({med:.1f}x), while sales grew {q:+.0f}% in the latest quarter and "
           f"{g:+.0f}% over the trailing year.")
    return {"stats": stats, "badges": badges, "why": why}


def view_block(view: str, entry: Optional[dict] = None) -> dict:
    """The served toggle block every undervalue payload carries."""
    v = VIEW_PEERS if view == VIEW_PEERS else VIEW_PSG
    blk = {
        "param": VIEW_PARAM, "view": v, "default": VIEW_PSG,
        "options": [{"key": VIEW_PSG, "label": PSG_VIEW_LABEL},
                    {"key": VIEW_PEERS, "label": PEERS_VIEW_LABEL}],
        "measured": MEASURED,
        "header": None, "note": None, "counts": None, "constants": None,
        "error": None,
    }
    if v == VIEW_PEERS:
        counts = {k: int(((entry or {}).get("counts") or {}).get(k) or 0)
                  for k in COUNT_KEYS}
        err = (entry or {}).get("error") or None
        blk.update({
            "header": header(counts, err), "note": NOTE, "counts": counts,
            "error": (str(err) if err else None),
            "constants": {"peer_ps_max_fraction": PEER_PS_MAX_FRACTION,
                          "min_peers": MIN_PEERS,
                          "min_sales_yoy_q_pct": MIN_SALES_YOY_Q_PCT,
                          "min_sales_ttm_growth_pct": MIN_SALES_TTM_GROWTH_PCT,
                          "min_ttm_revenue_usd": MIN_TTM_REVENUE_USD},
        })
    return blk


# ---------------------------------------------------------------------------
# I/O (read-only; each stubbable)
# ---------------------------------------------------------------------------
def _generation():
    from chart_maps import dual_momentum_tab
    return dual_momentum_tab.scan_generation()


def _load_inputs() -> dict:
    from catalysts.promo_circuit import market_caps_for
    from sepa import research, scanner
    from sepa import volume_movers

    scan = scanner.load_latest() or {}
    rows = scan.get("all_results") or []
    syms = sorted({str(r.get("symbol") or "").strip().upper()
                   for r in rows if isinstance(r, dict) and r.get("symbol")})
    snaps = research.decision_snapshot(syms) if syms else {}
    closes = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        s = str(r.get("symbol") or "").strip().upper()
        px = _f(r.get("last_close"))
        if s and px:
            closes[s] = px
    caps = market_caps_for(syms, closes, cap=0) if syms else {}
    cap_meta: dict = {}
    # A failed meta read must fail the build: without `cap_source` the
    # lower-bound (derived-float) caps would pass as real and read cheap.
    coll = volume_movers._shares_coll() if syms else None
    if coll is not None:
        for d in coll.find({"_id": {"$in": syms}},
                           {"as_of": 1, "cap_source": 1, "shares_outstanding": 1}):
            cap_meta[d["_id"]] = {"as_of": d.get("as_of"),
                                  "cap_source": d.get("cap_source"),
                                  "has_shares": bool(d.get("shares_outstanding"))}
    return {"rows": rows, "snaps": snaps, "caps": caps, "cap_meta": cap_meta,
            "generation": _generation(), "scan_generated_at": scan.get("generated_at")}


def _load_enrichment(passed_syms: list, peer_syms: list) -> tuple:
    bm_rows: dict = {}
    er_map: dict = {}
    syms = sorted(set(passed_syms or []) | set(peer_syms or []))
    if syms:
        try:
            from sepa import board_metrics
            for r in board_metrics.attach([{"symbol": s} for s in syms]):
                if len(r) > 1:               # an unmatched row stays {"symbol"}
                    bm_rows[str(r["symbol"]).upper()] = r
        except Exception as exc:                               # noqa: BLE001
            log.warning("undervalue peers: board_metrics read failed: %s", exc)
    if passed_syms:
        try:
            from rotation import hottest
            er_map = hottest._earnings_map(list(passed_syms))
        except Exception as exc:                               # noqa: BLE001
            log.warning("undervalue peers: earnings read failed: %s", exc)
    return bm_rows, er_map


def read(now: Optional[datetime] = None) -> dict:
    """The view's entry, memoised per (scan generation, ET date) for
    MEMO_TTL_SEC. The build runs OUTSIDE the lock. Never raises.

    A build that compared nothing (`build_failure`) or raised comes back with
    an `error` key and is NEVER memoised — the next load retries."""
    try:
        now_et = (now or datetime.now(ET))
        now_et = (now_et if now_et.tzinfo else now_et.replace(tzinfo=ET)).astimezone(ET)
        key = (_generation(), now_et.date().isoformat())
        with _lock:
            m = dict(_memo)
        if m.get("key") == key and time.time() - float(m.get("ts") or 0) < MEMO_TTL_SEC:
            return m["entry"]
        base = build(**_load_inputs())
        err = build_failure(base.get("counts"))
        if err:
            log.warning("undervalue peers: nothing compared (%s)", err)
            return {"passed": [], "counts": dict(base.get("counts") or _zero_counts()),
                    "error": err}
        passed = [p["symbol"] for p in base["passed"]]
        peers = sorted({q for p in base["passed"] for q in p.get("peers") or []})
        entry = enrich(base, *_load_enrichment(passed, peers))
        entry["built_at"] = time.time()
        with _lock:
            _memo.clear()
            _memo.update({"key": key, "ts": time.time(), "entry": entry})
        return entry
    except Exception as exc:                                   # noqa: BLE001
        log.warning("undervalue peers: read failed: %s", exc)
        return {"passed": [], "counts": _zero_counts(), "error": type(exc).__name__}
