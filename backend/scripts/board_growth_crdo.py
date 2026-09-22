"""Study D — the CRDO fact dump (board-growth research, 2026-09-21).

NOT A SIGNAL, NOT A GATE — research only (Rule #10).

Ajay, 2026-09-21: *"I felt like all the explosive growth stocks and Bondes
stocks have grown a great extent I exited the CRDO today but can you look in
to this more?"*

This script answers the CRDO half of that sentence with FACTS ONLY. It prints
what the app stored about the name, what each board served, what the trailing
windows did against RSP, where CRDO sits inside every cohort the members CSV
carries, and the dates at which the two screens FIRST became true given only
the filings available on each date. **There is no verdict line: whether the
exit was right is not measured here and is not stated here.**

Everything it touches is read-only: `find` / `find_one` with projections, the
stored board docs, the audit financial cache, and the price cache through
`sepa.prices.load_prices` (which may warm a cold symbol's parquet — the
LEDGERS `growth_seen` / `bonde_seen` / `growth_board` are never written).

RUN (in the api container; the three research scripts live in /tmp/scripts and
`scripts` is a PEP 420 namespace package, so BOTH portions must be on the path)

    docker exec -i cheetah-market-app-api-1 \
      sh -c 'mkdir -p /tmp/scripts && cat > /tmp/scripts/board_growth_crdo.py' \
      < backend/scripts/board_growth_crdo.py

    docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app \
      python -u -m scripts.board_growth_crdo --symbol CRDO \
      --members-csv /tmp/board_growth_members.csv \
      --json /tmp/board_growth_crdo.json'

A bare `python /tmp/scripts/board_growth_crdo.py` puts `/tmp/scripts` (not
`/tmp`) on `sys.path[0]`, the sibling scripts do not resolve, and this script
FAILS LOUD with a RuntimeError naming the run form above — Study D cannot
function without `screen_asof`, so it must never run a different way silently.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

HEADER = "NOT A SIGNAL, NOT A GATE — research only (Rule #10)"

RUN_FORM = ("run from /tmp/scripts with PYTHONPATH=/tmp:/app "
            "(docker exec -w /app cheetah-market-app-api-1 sh -c "
            "'PYTHONPATH=/tmp:/app python -u -m scripts.board_growth_crdo …')")

REPLAY_IMPORT_ERROR = "board_growth_replay not importable — " + RUN_FORM
STUDY_IMPORT_ERROR = "board_growth_study not importable — " + RUN_FORM

# The day-one backfill caveat, printed on every `first_seen` line.
BACKFILL_CAVEAT = ("09-14 / 09-12 = day-one backfill: 'present on that day', "
                   "not 'arrived'.")

FIN_DEFAULT = "/root/.cheetah/audit_fin_v1.json.gz"

# An ISO timestamp starts YYYY-MM-DD. `push_history.ts` is an epoch stored as a
# STRING — `ts_iso` is the readable one — so anything that is not date-shaped is
# refused rather than silently mis-parsed.
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ].*)?$")


# ── pure helpers ─────────────────────────────────────────────────────────────
def _f(v: Any) -> Optional[float]:
    """float(v) or None — never raises, never returns NaN."""
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def parse_iso(s: Any) -> datetime:
    """Parse a ledger timestamp string into an aware UTC datetime.

    `first_seen` / `last_seen` / `tracking_since` are ISO STRINGS
    (`sepa/first_seen.py:56-80`). `push_history.ts` is an epoch stored as a
    string — passing it here is a bug, so it is REFUSED loudly; use `ts_iso`.
    """
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    if not isinstance(s, str):
        raise ValueError("parse_iso: not a timestamp: %r" % (s,))
    t = s.strip()
    if not _ISO_RE.match(t):
        raise ValueError(
            "parse_iso: not an ISO timestamp: %r — push_history.ts is an epoch "
            "string, read ts_iso instead" % (s,))
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    out = datetime.fromisoformat(t)
    return out if out.tzinfo else out.replace(tzinfo=timezone.utc)


def band_containing(bands: Optional[Sequence[dict]], price: Optional[float],
                    kind: Optional[str] = "demand") -> Optional[dict]:
    """The first band whose `lo <= price <= hi`, or None.

    Edges are INCLUSIVE, exactly as `growth/tracker.py:456` reads `zone_store`.
    """
    px = _f(price)
    if px is None:
        return None
    for b in bands or []:
        if kind is not None and b.get("kind") != kind:
            continue
        lo, hi = _f(b.get("lo")), _f(b.get("hi"))
        if lo is None or hi is None:
            continue
        if lo <= px <= hi:
            return b
    return None


def pnl_pct(entry: Optional[float], exit_px: Optional[float]) -> Optional[float]:
    """(exit/entry − 1) * 100, rounded to 2dp. None on a non-positive entry."""
    e, x = _f(entry), _f(exit_px)
    if e is None or x is None or e <= 0:
        return None
    return round((x / e - 1.0) * 100.0, 2)


# `portfolio_supply_alerts` is the ledger the STOP push is written from: one doc
# per (user, symbol, band floor, stage, date). Only `stage == "STOP"` is the stop
# alert — `NEAR` / `NEAR_STOP` are different alerts on different bands (CRDO's
# NEAR rows carry the SUPPLY band 156.09–156.89, which is NOT the stop band).
STOP_STAGE = "STOP"


def stop_alert_facts(
        alert_rows: Optional[Sequence[dict]]) -> Tuple[int, Optional[dict]]:
    """(how many times the STOP alert fired, the band it fired on).

    Counting push titles that merely CONTAIN "stop" over-counts — "⚠️ CRDO 0.9%
    above the stop" is a NEAR_STOP alert, not a STOP — and taking the first row
    that happens to carry a `band` returns whichever stage sorted first. Both
    reads are therefore restricted to `stage == "STOP"`.
    """
    stops = [a for a in (alert_rows or [])
             if str(a.get("stage") or "") == STOP_STAGE]
    band = None
    for a in stops:
        if a.get("band"):
            band = a.get("band")
            break
    return len(stops), band


_EXPLOSIVE_TIER: Optional[str] = None


def explosive_tier() -> str:
    """The tier label `sepa.sales.compute` gives at the explosive boundary.

    Derived from the shipped engine at `SALES_EXPLOSIVE_PCT` rather than
    retyped, so a tier rename cannot drift this script silently (Rule #1).
    """
    global _EXPLOSIVE_TIER
    if _EXPLOSIVE_TIER is None:
        from sepa import sales
        base = 100.0
        top = base * (1.0 + sales.SALES_EXPLOSIVE_PCT / 100.0)
        revs = [top, None, None, None, base, None, None, None]
        _EXPLOSIVE_TIER = sales.compute(revs, None)["tier"]
    return _EXPLOSIVE_TIER


def _screen_predicates() -> List[Tuple[str, Callable[[dict], bool]]]:
    """The three screens whose FIRST pass date Study D reports."""
    expl = explosive_tier()
    return [
        ("passes_100_100", lambda st: bool(st.get("passes_100_100"))),
        ("passes_100_100_epsbase",
         lambda st: bool(st.get("passes_100_100_epsbase"))),
        ("bonde_explosive",
         lambda st: bool(st.get("bonde_pass")) and st.get("tier") == expl),
    ]


def avail_dates(rec: Sequence[Sequence[Any]]) -> List[Tuple[str, bool]]:
    """Distinct availability dates in `core.prep_fin`'s rec, ASCENDING.

    A rec row is `(avail_iso, period_index, rev, eps, filed_bool)`
    (`scripts/bonde_audit/core.py:52-80`). A date is flagged `derived=True`
    when every row carrying it came from the `end+90d` assumption.
    """
    seen: Dict[str, bool] = {}
    for row in rec or []:
        a = row[0]
        filed = bool(row[4]) if len(row) > 4 else True
        if a in seen:
            seen[a] = seen[a] and not filed
        else:
            seen[a] = not filed
    return [(a, seen[a]) for a in sorted(seen)]


def first_pass_dates(rec: Sequence[Sequence[Any]],
                     screen_asof: Callable[..., Optional[dict]],
                     dates: Sequence[str],
                     close: Sequence[float],
                     first_close_after: Callable[..., Optional[Tuple[str, float]]],
                     ) -> dict:
    """When each screen FIRST became true, given only what was filed by then.

    Walks every distinct availability date in `rec` in ASCENDING order and
    evaluates `screen_asof(rec, avail, strict=False)` — the state that exists
    once THAT filing is in (`strict=True` would exclude the very filing whose
    availability date we are standing on). Because the walk is ascending and
    the first True wins, a later-filed EARLIER fiscal period can never move a
    first-pass date backwards.

    The price is anchored at the first bar STRICTLY AFTER `avail` — the filing
    itself lands after that day's close — and both dates are returned so the
    report prints `filed` and `anchor_date` side by side.
    """
    walked = avail_dates(rec)
    last_date = dates[-1] if len(dates) else None
    last_close = _f(close[-1]) if len(close) else None

    out: Dict[str, Any] = {
        "avail_dates_walked": [a for a, _d in walked],
        "n_avail_dates": len(walked),
        "strict": False,
        "last_date": last_date,
        "last_close": last_close,
        "screens": {},
    }
    pending = _screen_predicates()
    found: Dict[str, Any] = {name: None for name, _p in pending}

    for avail, derived in walked:
        if all(found[name] is not None for name, _p in pending):
            break
        state = screen_asof(rec, avail, strict=False)
        if not state:
            continue
        for name, pred in pending:
            if found[name] is not None:
                continue
            try:
                hit = bool(pred(state))
            except Exception:                                  # noqa: BLE001
                hit = False
            if not hit:
                continue
            anchor = first_close_after(dates, close, avail)
            a_date, a_close = (anchor if anchor else (None, None))
            a_close = _f(a_close)
            found[name] = {
                "filed": avail,
                "avail_derived": bool(derived),
                "anchor_date": a_date,
                "anchor_close": a_close,
                "return_to_last_pct": pnl_pct(a_close, last_close),
                "legs": {k: state.get(k) for k in (
                    "sales_yoy", "prior_yoy", "eps_yoy", "base_ok",
                    "eps_base_negative", "tier", "bonde_pass", "cleared_floor",
                    "character", "stale_days", "newest_avail")},
            }
    out["screens"] = found
    return out


# ── the members CSV (written by scripts/board_growth_study.py) ───────────────
_RET_CANDIDATES = ("ret_{0}", "ret_{0}_pct", "{0}_pct", "trailing_{0}_pct",
                   "return_{0}_pct")


def resolve_return_column(header: Sequence[str], label: str) -> str:
    """The members-CSV column holding the raw trailing return for `label`.

    Fails loud rather than guessing: the CSV is WP1's output and a renamed
    column must surface as an error, not as a silently missing percentile.
    """
    cols = list(header or [])
    for pat in _RET_CANDIDATES:
        name = pat.format(label)
        if name in cols:
            return name
    raise ValueError(
        "members CSV has no trailing-return column for window %r; tried %s; "
        "header = %s" % (label, [p.format(label) for p in _RET_CANDIDATES], cols))


def load_members_csv(path: str) -> Tuple[List[dict], List[str]]:
    """(rows, header) from WP1's `--stage members` CSV."""
    with open(path, "r", newline="") as fh:
        rdr = csv.DictReader(fh)
        header = list(rdr.fieldnames or [])
        rows = [dict(r) for r in rdr]
    return rows, header


def cohort_percentiles(rows: Sequence[dict], header: Sequence[str], symbol: str,
                       windows: Sequence[Tuple[str, int]],
                       percentile_of: Callable[[Sequence[float], float], float],
                       ) -> dict:
    """Where `symbol` sits inside every cohort it belongs to, per window.

    `universe_pctile_<window>` is read straight from the row WP1 wrote (the
    member's rank inside the 2,090-name scan universe); the cohort percentile
    is computed over that cohort's own members.
    """
    sym = (symbol or "").upper()
    cohorts: Dict[str, List[dict]] = {}
    for r in rows:
        cohorts.setdefault(str(r.get("cohort") or ""), []).append(r)

    out: Dict[str, Any] = {}
    for cohort, crows in cohorts.items():
        mine = [r for r in crows if str(r.get("symbol") or "").upper() == sym]
        if not mine:
            continue
        me = mine[0]
        entry: Dict[str, Any] = {"cohort_n": len(crows), "windows": {}}
        for label, _k in windows:
            col = resolve_return_column(header, label)
            vals = [v for v in (_f(r.get(col)) for r in crows) if v is not None]
            x = _f(me.get(col))
            entry["windows"][label] = {
                "value_pct": x,
                "n_scored": len(vals),
                "cohort_pctile": (round(percentile_of(vals, x), 1)
                                  if x is not None and vals else None),
                "universe_pctile": _f(me.get("universe_pctile_%s" % label)),
            }
        out[cohort] = entry
    return out


# ── exit reference (numbers only — no verdict) ───────────────────────────────
def exit_reference(entry: Optional[float], shares: Optional[float],
                   last_date: Optional[str], last_close: Optional[float],
                   week_pct: Optional[float],
                   pct_below_high_v: Optional[float],
                   high_close: Optional[float], high_date: Optional[str],
                   stop_pushes: int, stop_band: Optional[dict]) -> dict:
    """The numbers around the exit. No judgement is formed here or anywhere."""
    sh = _f(shares)
    pnl = pnl_pct(entry, last_close)
    e = _f(entry)
    return {
        "entry": e,
        "shares": sh,
        "reference_date": last_date,
        "reference_close": _f(last_close),
        "note": ("his fill today is not stored in the app — the reference is "
                 "the close on the date above"),
        "pnl_pct_entry_to_reference": pnl,
        "value_at_reference": (round(sh * _f(last_close), 2)
                               if sh is not None and _f(last_close) is not None
                               else None),
        "pnl_dollars_entry_to_reference": (
            round(sh * (_f(last_close) - e), 2)
            if sh is not None and e is not None and _f(last_close) is not None
            else None),
        "week_gave_pct": _f(week_pct),
        "off_52w_high_pct": _f(pct_below_high_v),
        "high_52w_close": _f(high_close),
        "high_52w_date": high_date,
        "stop_pushes": int(stop_pushes),
        "stop_band": stop_band,
    }


# ── lazy imports of the sibling scripts (fail loud, never silently different) ─
def load_replay():
    """`scripts.board_growth_replay` — Study D cannot function without it."""
    try:
        return importlib.import_module("scripts.board_growth_replay")
    except ImportError as exc:
        raise RuntimeError(REPLAY_IMPORT_ERROR) from exc


def load_study():
    """`scripts.board_growth_study` — the trailing/percentile helpers."""
    try:
        return importlib.import_module("scripts.board_growth_study")
    except ImportError as exc:
        raise RuntimeError(STUDY_IMPORT_ERROR) from exc


# ── Mongo (read-only) ────────────────────────────────────────────────────────
def get_db():
    """A read-only handle. `sepa.first_seen._db` builds a plain client and
    creates no indexes; `sepa.history._get_db` would create some."""
    from sepa import first_seen as FS
    return FS._db(None)


def _find(db, coll: str, queries: Sequence[dict], projection: Optional[dict] = None,
          limit: int = 0, sort: Optional[list] = None) -> Tuple[List[dict], Optional[dict]]:
    """First query that returns anything. (docs, matched_query) — never writes."""
    if db is None:
        return [], None
    for q in queries:
        try:
            cur = db[coll].find(q, projection)
            if sort:
                cur = cur.sort(sort)
            if limit:
                cur = cur.limit(limit)
            docs = [_clean(d) for d in cur]
        except Exception as exc:                               # noqa: BLE001
            return [], {"error": "%s: %s" % (coll, exc)}
        if docs:
            return docs, q
    return [], None


def _clean(doc: Any) -> Any:
    """JSON-safe: ObjectId / datetime → str, recursively."""
    if isinstance(doc, dict):
        return {str(k): _clean(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_clean(v) for v in doc]
    if isinstance(doc, datetime):
        return doc.isoformat()
    if isinstance(doc, (str, int, float, bool)) or doc is None:
        return doc
    return str(doc)


def ledger_facts(db, sym: str) -> dict:
    """Every stored trace of `sym`, read-only, exactly as §1.5 lists them."""
    s = sym.upper()
    out: Dict[str, Any] = {"caveat_first_seen": BACKFILL_CAVEAT}

    for coll in ("growth_seen", "bonde_seen"):
        docs, _q = _find(db, coll, [{"_id": s}])
        meta, _q2 = _find(db, coll, [{"_id": "__meta__"}])
        out[coll] = {
            "doc": docs[0] if docs else None,
            "tracking_since": (meta[0].get("tracking_since") if meta else None),
        }

    pushes, _q = _find(db, "push_history", [{"ticker": s}, {"tickers": s}],
                       {"kind": 1, "ticker": 1, "title": 1, "body": 1,
                        "ts": 1, "ts_iso": 1},
                       sort=[("ts", -1)], limit=200)
    out["push_history"] = {"n": len(pushes), "rows": pushes,
                           "by_kind": _count(pushes, "kind")}

    runs, _q = _find(db, "demand_board_runs", [{"symbols": s}], {"et_date": 1}, limit=200)
    try:
        n_runs = int(db["demand_board_runs"].count_documents({})) if db is not None else None
    except Exception:                                          # noqa: BLE001
        n_runs = None
    out["demand_board_runs"] = {"n_with_symbol": len(runs), "n_runs_total": n_runs,
                                "et_dates": [r.get("et_date") for r in runs]}

    zones, _q = _find(db, "zone_store", [{"symbol": s}], None,
                      sort=[("date", -1)], limit=1)
    zdoc = zones[0] if zones else None
    out["zone_store"] = {
        "date": (zdoc or {}).get("date"),
        "prev_close": _f((zdoc or {}).get("prev_close")),
        "demand_bands": [b for b in ((zdoc or {}).get("bands") or [])
                         if b.get("kind") == "demand"],
    }

    for coll in ("promo_circuit_tags", "promo_sales_cache"):
        docs, _q = _find(db, coll, [{"_id": s}, {"symbol": s}, {"ticker": s}], limit=20)
        out[coll] = {"n": len(docs), "rows": docs}

    diag, _q = _find(db, "portfolio_diagnosis",
                     [{"_id": {"$regex": "^%s\\|" % re.escape(s)}}, {"symbol": s}],
                     limit=20)
    out["portfolio_diagnosis"] = {"n": len(diag), "rows": diag}

    snaps, _q = _find(db, "portfolio_snapshots", [{"symbol": s}, {"ticker": s}],
                      None, sort=[("date", 1)], limit=200)
    out["portfolio_snapshots"] = {"n": len(snaps), "rows": snaps}

    alerts, _q = _find(db, "portfolio_supply_alerts",
                       [{"_id": {"$regex": ":%s:" % re.escape(s)}}, {"symbol": s}],
                       limit=50)
    out["portfolio_supply_alerts"] = {"n": len(alerts), "rows": alerts}

    for coll in ("paper_trades", "trade_ledger"):
        docs, _q = _find(db, coll, [{"symbol": s}, {"ticker": s}], limit=50)
        out[coll] = {"n": len(docs), "rows": docs}

    holdings, _q = _find(db, "portfolio_holdings", [{"symbol": s}, {"ticker": s}], limit=20)
    out["portfolio_holdings"] = {"n": len(holdings), "rows": holdings}

    comp, _q = _find(db, "companies", [{"_id": s}, {"symbol": s}],
                     {"sector": 1, "industry": 1, "name": 1}, limit=1)
    out["companies"] = comp[0] if comp else None
    return out


def _count(rows: Sequence[dict], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        out[str(r.get(key))] = out.get(str(r.get(key)), 0) + 1
    return out


def served_rows(sym: str, no_write_db) -> dict:
    """The row each board SERVED, with its flags — boards read, never built."""
    s = sym.upper()
    out: Dict[str, Any] = {}

    from growth import tracker as GT
    doc = GT.board() or {}
    rows = [r for r in (doc.get("rows") or []) if str(r.get("symbol", "")).upper() == s]
    out["growth_board"] = {
        "built_at": doc.get("built_at"),
        "n": doc.get("n"),
        "screen": doc.get("screen"),
        "row": _clean(rows[0]) if rows else None,
    }

    from sepa import bonde as B
    bd = B.board(db=no_write_db) or {}
    hit = None
    for section, srows in (bd.get("sections") or {}).items():
        for r in srows or []:
            if str(r.get("symbol", "")).upper() == s:
                hit = dict(_clean(r))
                hit["section"] = section
                break
        if hit:
            break
    out["bonde_board"] = {
        "counts": bd.get("counts"),
        "n_pass": bd.get("n_pass"),
        "generated_at": bd.get("generated_at"),
        "row": hit,
    }
    return out


def trailing_table(study, dates: Sequence[str], close, bench_dates, bench_close) -> List[dict]:
    """Per window: the raw return, RSP over the IDENTICAL calendar dates, and
    the percentage-point difference rotation's own `_relativize` would print."""
    out = []
    last = dates[-1] if len(dates) else None
    for label, k in study.WINDOWS:
        start = dates[-1 - k] if len(dates) > k else None
        raw = study.trailing_return_pct(close, k)
        bench = (study.calendar_window_return_pct(bench_dates, bench_close, start, last)
                 if start and last else None)
        out.append({"window": label, "bars": k, "start_date": start,
                    "end_date": last, "ret_pct": raw, "bench_pct": bench,
                    "rel_pp": study.relative_pp(raw, bench)})
    return out


# ── rendering (NO verdict — the section ends with the numbers) ───────────────
def _n(v: Any, unit: str = "") -> str:
    return "n/a" if v is None else ("%s%s" % (v, unit))


def render_summary(payload: dict) -> str:
    """The printed fact dump. Numbers only; the report's D section ends here."""
    L: List[str] = [HEADER, ""]
    sym = payload.get("symbol", "?")
    L.append("Study D — %s fact dump (%s)" % (sym, payload.get("run_started")))
    L.append("")

    srv = payload.get("served") or {}
    g = srv.get("growth_board") or {}
    L.append("🚀 growth_board  built_at %s  n %s  screen %s"
             % (_n(g.get("built_at")), _n(g.get("n")), _n(g.get("screen"))))
    L.append("   row: %s" % (_n(g.get("row")),))
    b = srv.get("bonde_board") or {}
    L.append("📈 bonde board   counts %s  n_pass %s" % (_n(b.get("counts")), _n(b.get("n_pass"))))
    L.append("   row: %s" % (_n(b.get("row")),))
    L.append("")

    L.append("Trailing (close-to-close) vs %s" % _n(payload.get("benchmark")))
    L.append("  window  bars  start        end          ret%    bench%   rel pp")
    for r in payload.get("trailing") or []:
        L.append("  %-6s  %-4s  %-11s  %-11s  %-7s %-8s %s"
                 % (r.get("window"), r.get("bars"), _n(r.get("start_date")),
                    _n(r.get("end_date")), _n(r.get("ret_pct")),
                    _n(r.get("bench_pct")), _n(r.get("rel_pp"))))
    hi = payload.get("high_52w") or {}
    L.append("  52w high (close, trend-template arithmetic) %s on %s → below by %s%%"
             % (_n(hi.get("close")), _n(hi.get("date")), _n(hi.get("pct_below"))))
    L.append("  52w high (intraday, secondary column only)  %s → below by %s%%"
             % (_n(hi.get("intraday_high")), _n(hi.get("pct_below_intraday"))))
    zb = payload.get("zone_band_at_close") or {}
    _band = zb.get("band")
    if _band:
        L.append("  %s close %s sits INSIDE the stored demand band %s–%s (zone_store %s)"
                 % (_n(zb.get("close_date")), _n(zb.get("close")), _n(_band.get("lo")),
                    _n(_band.get("hi")), _n(zb.get("zone_date"))))
    else:
        L.append("  %s close %s sits inside no stored demand band (zone_store %s)"
                 % (_n(zb.get("close_date")), _n(zb.get("close")), _n(zb.get("zone_date"))))
    L.append("")

    pcts = payload.get("percentiles") or {}
    if pcts:
        L.append("Percentile inside each cohort, and inside universe_all")
        for cohort, entry in sorted(pcts.items()):
            for label, w in (entry.get("windows") or {}).items():
                L.append("  %-26s %-3s n %-5s value %-8s cohort p%-6s universe p%s"
                         % (cohort, label, entry.get("cohort_n"), _n(w.get("value_pct")),
                            _n(w.get("cohort_pctile")), _n(w.get("universe_pctile"))))
    else:
        L.append("Percentiles: no members CSV supplied (--members-csv).")
    L.append("")

    fp = payload.get("first_pass") or {}
    L.append("First date each screen became true (strict=%s at each availability date;"
             % _n(fp.get("strict")))
    L.append("  %s availability dates walked; price anchored at the first bar AFTER filed)"
             % _n(fp.get("n_avail_dates")))
    for name, hit in (fp.get("screens") or {}).items():
        if not hit:
            L.append("  %-24s never true in the panel" % name)
            continue
        L.append("  %-24s filed %s → anchor %s @ %s → %s%% to %s @ %s"
                 % (name, _n(hit.get("filed")), _n(hit.get("anchor_date")),
                    _n(hit.get("anchor_close")), _n(hit.get("return_to_last_pct")),
                    _n(fp.get("last_date")), _n(fp.get("last_close"))))
        L.append("      legs %s" % (_n(hit.get("legs")),))
    L.append("")

    ex = payload.get("exit_reference") or {}
    L.append("Exit reference numbers")
    L.append("  entry %s × %s shares → %s close %s = %s%% (%s)"
             % (_n(ex.get("entry")), _n(ex.get("shares")), _n(ex.get("reference_date")),
                _n(ex.get("reference_close")), _n(ex.get("pnl_pct_entry_to_reference")),
                _n(ex.get("pnl_dollars_entry_to_reference"))))
    L.append("  %s" % _n(ex.get("note")))
    L.append("  the week gave %s%% · off the 52w high by %s%% (high %s on %s)"
             % (_n(ex.get("week_gave_pct")), _n(ex.get("off_52w_high_pct")),
                _n(ex.get("high_52w_close")), _n(ex.get("high_52w_date"))))
    L.append("  STOP pushes on the name: %s · stored stop band %s"
             % (_n(ex.get("stop_pushes")), _n(ex.get("stop_band"))))
    L.append("")

    led = payload.get("ledgers") or {}
    L.append("Ledgers (read-only). %s" % _n(led.get("caveat_first_seen")))
    for coll in ("growth_seen", "bonde_seen"):
        L.append("  %-14s %s" % (coll, _n(led.get(coll))))
    for coll in ("push_history", "demand_board_runs", "zone_store",
                 "promo_circuit_tags", "promo_sales_cache", "portfolio_diagnosis",
                 "portfolio_snapshots", "portfolio_supply_alerts", "paper_trades",
                 "trade_ledger", "portfolio_holdings"):
        v = led.get(coll) or {}
        if isinstance(v, dict) and "n" in v:
            L.append("  %-24s n %s" % (coll, v.get("n")))
        else:
            L.append("  %-24s %s" % (coll, _n(v)))
    L.append("  companies                %s" % _n(led.get("companies")))
    return "\n".join(L)


# ── stage ────────────────────────────────────────────────────────────────────
def run(symbol: str = "CRDO", members_csv: Optional[str] = None,
        fin_path: str = FIN_DEFAULT, bench: Optional[str] = None) -> dict:
    """The whole dump. Container-only: Mongo + the audit fin + the price cache."""
    S = load_study()
    R = load_replay()
    import gzip

    sym = symbol.upper()
    started = datetime.now(timezone.utc).isoformat()
    bench = bench or S.BENCHMARK

    db = get_db()
    payload: Dict[str, Any] = {
        "header": HEADER,
        "symbol": sym,
        "benchmark": bench,
        "run_started": started,
        "fin_path": fin_path,
        "members_csv": members_csv,
    }

    payload["ledgers"] = ledger_facts(db, sym)
    payload["served"] = served_rows(sym, S.NoWriteDB())

    frame = S.load_close(sym)
    bench_frame = S.load_close(bench)
    dates: Sequence[str] = []
    close: Sequence[float] = []
    if frame is None:
        payload["error"] = "no price frame for %s" % sym
        payload["trailing"] = []
        payload["high_52w"] = {}
    else:
        dates, close, high = frame
        b_dates, b_close = (bench_frame[0], bench_frame[1]) if bench_frame else ([], [])
        payload["trailing"] = trailing_table(S, dates, close, b_dates, b_close)
        window = list(close)[-252:]
        hi_val = max(window) if window else None
        hi_idx = (len(close) - len(window)) + window.index(hi_val) if window else None
        hwin = list(high)[-252:]
        payload["high_52w"] = {
            "close": hi_val,
            "date": dates[hi_idx] if hi_idx is not None else None,
            "pct_below": S.pct_below_high(close),
            "intraday_high": (max(hwin) if hwin else None),
            "pct_below_intraday": S.pct_below_intraday_high(high, close),
        }

    # Does the last close sit inside a stored demand band? (§1.5 — a fact from
    # the SAME `zone_store` doc the ledger block already read; no new read.)
    _zs = (payload["ledgers"].get("zone_store") or {})
    _last_close = _f(close[-1]) if len(close) else None
    payload["zone_band_at_close"] = {
        "zone_date": _zs.get("date"),
        "close_date": (dates[-1] if len(dates) else None),
        "close": _last_close,
        "band": band_containing(_zs.get("demand_bands"), _last_close),
    }

    # First-pass dates — the audit fin, prepped by the SAME core the replay uses.
    core = R.load_core()
    with gzip.open(fin_path, "rt") as fh:
        fin = json.loads(fh.read())
    recs = core.prep_fin(fin, "plus90")
    rec = recs.get(sym)
    if rec and frame is not None:
        payload["first_pass"] = first_pass_dates(
            rec, R.screen_asof, frame[0], frame[1], S.first_close_after)
    else:
        payload["first_pass"] = {"error": "no fin rec for %s in %s" % (sym, fin_path)}

    # Percentiles from WP1's members CSV.
    if members_csv and os.path.exists(members_csv):
        rows, header = load_members_csv(members_csv)
        payload["percentiles"] = cohort_percentiles(
            rows, header, sym, S.WINDOWS, S.percentile_of)
    else:
        payload["percentiles"] = {}

    # Exit reference.
    diag_rows = (payload["ledgers"].get("portfolio_diagnosis") or {}).get("rows") or []
    pos = {}
    for d in diag_rows:
        pos = d.get("position") or {}
        if pos:
            break
    alert_rows = (payload["ledgers"].get("portfolio_supply_alerts") or {}).get("rows") or []
    stop_pushes, stop_band = stop_alert_facts(alert_rows)
    tr = {r["window"]: r for r in (payload.get("trailing") or [])}
    hi = payload.get("high_52w") or {}
    payload["exit_reference"] = exit_reference(
        entry=pos.get("entry"), shares=pos.get("shares"),
        last_date=(tr.get("1w") or {}).get("end_date"),
        last_close=(_f(close[-1]) if frame is not None else None),
        week_pct=(tr.get("1w") or {}).get("ret_pct"),
        pct_below_high_v=hi.get("pct_below"),
        high_close=hi.get("close"), high_date=hi.get("date"),
        stop_pushes=stop_pushes, stop_band=stop_band)

    payload["run_finished"] = datetime.now(timezone.utc).isoformat()
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Study D — CRDO fact dump (research only)")
    ap.add_argument("--symbol", default="CRDO")
    ap.add_argument("--members-csv", default=None)
    ap.add_argument("--fin", default=FIN_DEFAULT)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(list(argv) if argv is not None else None)

    payload = run(symbol=args.symbol, members_csv=args.members_csv,
                  fin_path=args.fin, bench=args.bench)
    text = render_summary(payload)
    print(text)
    if args.json_out:
        payload["summary_text"] = text
        with open(args.json_out, "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print("\nwrote %s" % args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
