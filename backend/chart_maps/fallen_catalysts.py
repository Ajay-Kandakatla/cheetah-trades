"""💥 What hit it — the "possible catalyst" read of the 📉 Down 40%+ tab (2026-10-02).

Ajay 2026-10-02, mid-build, verbatim: "also add things like possible catalyst
that made is drop like that."

WHAT THIS IS. For each listed name, its biggest down days since the 52-week
high (`fallen_tab.top_drops`) and, for each day, whatever this app ALREADY
holds on file inside a small window around it (`WINDOW_BEFORE` sessions before
to `WINDOW_AFTER` after): the latest earnings report, a promo-circuit 8-K or
shelf filing, a medical event, an index deletion, a cached headline, an analyst
action, a cached model read — plus what the name's sector ETF, its theme's
median member and RSP did that same session.

EVERY ITEM IS "POSSIBLE". It is a date that lines up — co-occurrence, never
proof. "nothing on file" means this app holds nothing for that day, not that
nothing happened. Text is the STORED text (a headline's own title, a filing's
own item codes); no reason is ever composed here. A model's words appear only
when the app already cached them, labelled as the model's read.

CACHE ONLY. ONE bulk read per source, each in its own try (a failing source is
`available: False` for itself only), called from the 📉 tab's background build
— never on a request. No provider is called from this module. Left out on
purpose (HIS CALL #13): Form 4 / 144 / 13D/G, the catalyst one-liner cache,
`macro_context`, and the frozen `bonde_fin` study file.

WRITES NOTHING. UNMEASURED: nothing here has been measured against anything.
"""
from __future__ import annotations

import logging
import statistics
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from supply_demand.demand_alerts import SESSION_CLOSE   # 16:00 ET, imported, never typed

log = logging.getLogger("chart_maps.fallen_catalysts")

ET = ZoneInfo("America/New_York")

HIT_MARK = "\U0001F4A5"                 # 💥 — HIS CALL #9 (🧨 is the explosive read's mark)
TOP_DROPS = 3                           # HIS CALL #10 — the drop days read per name
WINDOW_BEFORE = 1                       # HIS CALL #10 — sessions before the drop day
WINDOW_AFTER = 1                        # HIS CALL #10 — sessions after the drop day
# HIS CALL #11 — the 💥 line's "most specific item", first kind present wins.
PRIORITY = ("earnings", "medical", "filing", "index", "news", "analyst", "model")
GROUP_DAY_CUT = None                    # HIS CALL #11b — no "sector-wide day" verdict until he gives a cut
MODEL_READ_CHARS = 200                  # display cap on a cached model read
NOTHING = "nothing on file"
NOT_STORED = "guidance: this app stores none"
INDEX_READ_DAYS = 400                   # read window of the change log (a read limit, not a rule)
INDEX_READ_LIMIT = 1000
# An item on file inside the window but NOT public by the drop's close (dated
# after the drop day, or an after-the-close report on it) is kept in the fold
# with this label and never becomes the 💥 "possible" item (critic 2026-10-03).
# A headline stamped at or after SESSION_CLOSE (ET) on the drop day is after
# the drop too (critic 2026-10-03, round 2: LQDA's 19:29 ET headline).
AFTER_DROP = "after the drop"
# Analyst tie-break inside one kind and day: a rating change (or a new
# coverage) before a maintained / reiterated rating — display order only.
ANALYST_CHANGE_ACTIONS = ("up", "down", "init")

KIND_LABELS = {"earnings": "earnings", "filing": "8-K / offering", "medical": "medical",
               "index": "index deletion", "news": "news", "analyst": "analyst action",
               "model": "model read"}
SOURCE_LABELS = {"earnings": "Earnings report", "filing": "8-K / offering filing",
                 "medical": "Medical event", "index": "Index deletion", "news": "News headline",
                 "analyst": "Analyst action", "model": "Model read (cached)"}
SOURCE_KEYS = PRIORITY
# The order the "nothing on file" line names the sources in (the ask's own
# order: earnings, then the SEC filing, ...); the 💥 pick order is PRIORITY.
EMPTY_ORDER = ("earnings", "filing", "medical", "index", "news", "analyst", "model")

POSSIBLE_NOTE = (f"{HIT_MARK} Possible = on file within {WINDOW_BEFORE} session before to "
                 f"{WINDOW_AFTER} after the drop. A date that lines up, never proof of cause; "
                 "\"nothing on file\" means this app holds nothing for that day, not that "
                 "nothing happened.")

# The per-symbol headline caches already on file — (collection, symbol field,
# rows path, field map, provider). Symbol field "@tickers" = each row's own
# `tickers` list (a market-wide cache); "@selector" = the audit doc's
# `selector.value`. Rows path None = the document itself is the item. A field
# map renames the stored keys into `news_search.core.normalise`'s input; None =
# the stored item already has that shape. Provider "@row" = the item's own
# `provider` field. Ported from the scout's reader (scratchpad catalysts_now.py).
NEWS_CACHES = (
    ("finnhub_cache_v2", "symbol", "data.rows",
     {"title": "headline", "url": "url", "source": "source", "published": "datetime",
      "summary": "summary"}, "finnhub"),
    ("product_launches", "symbol", None,
     {"title": "title", "url": "url", "published_utc": "published_at"}, "massive"),
    ("pioneer_news_cache", "_id", "headlines", None, "google"),
    ("med_catalyst_articles", "ticker", None,
     {"title": "title", "url": "url", "source": "source", "published": "published",
      "provider": "provider"}, "@row"),
    ("supply_demand_edge_news", "@tickers", "headlines", None, "massive"),
    ("news_search_audit", "@selector", "items", None, "@row"),
    ("news_two_sided", "symbol", "headlines", None, "@row"),
    ("sector_day_tags", "symbol", "headlines", None, "@row"),
    ("promo_news_cache", "_id", "catalyst.top", None, "massive"),
    ("candidate_snapshots", "symbol", "catalyst.top_news", None, "google"),
    ("ipo_upcoming_cache", "_id", "headlines", None, "google"),
)
# Extra filters some caches need (the scout's queries, verbatim).
_EXTRA_QUERY = {"finnhub_cache_v2": {"endpoint": "news"},
                "candidate_snapshots": {"catalyst": {"$ne": None}},
                "news_search_audit": {"selector.kind": "ticker"}}
# The two cached model reads (labelled as the model's, never as a fact).
MODEL_CACHES = ("news_two_sided", "sector_day_tags")

_MINUS = "−"


# ---------------------------------------------------------------------------
# small helpers (PURE)
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def _m(s: str) -> str:
    """Real minus signs in a served number string."""
    return s.replace("-", _MINUS)


def _pct_txt(v, dp: int = 2) -> str:
    return _m(f"{float(v):+.{dp}f}%")


def _get(doc, path: Optional[str]):
    cur = doc
    for part in (path or "").split("."):
        if not part:
            continue
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def et_date(v) -> Optional[str]:
    """epoch s / ms, datetime, ISO -> the ET calendar date (the scout's
    `_et_date_of_any`). None when it cannot be read."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        dt = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (int, float)):
        ts = _f(v)
        if ts is None or ts <= 0:
            return None
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(ET).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    s = str(v).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            return date.fromisoformat(s).isoformat()
        except ValueError:
            return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).date().isoformat()


def _epoch_s(v) -> Optional[float]:
    """A published epoch (s or ms) -> seconds; None when it cannot be read."""
    if isinstance(v, bool):
        return None
    ts = _f(v)
    if ts is None or ts <= 0:
        return None
    return ts / 1000.0 if ts > 1e12 else ts


def _epoch_any(v) -> Optional[float]:
    """A published TIME -> epoch seconds: epoch s/ms, a datetime (naive = UTC,
    how pymongo returns med_catalyst_events.published_at) or an ISO string WITH
    a time. A date-only value has no time of day -> None (the date rule only)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        dt = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    if isinstance(v, date):
        return None
    if isinstance(v, (int, float)):
        return _epoch_s(v)
    s = str(v).strip()
    if len(s) <= 10:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _after_close_on(ts, day: str) -> bool:
    """Is this epoch at or after SESSION_CLOSE (ET) on the ET date `day`?"""
    t = _epoch_s(ts)
    if t is None:
        return False
    try:
        dt = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(ET)
    except (OverflowError, OSError, ValueError):
        return False
    return dt.date().isoformat() == day and dt.time() >= SESSION_CLOSE


def _num_txt(v) -> Optional[str]:
    x = _f(v)
    return None if x is None else _m(f"{x:g}")


# ---------------------------------------------------------------------------
# item templates — the STORED text, never a composed reason (PURE)
# ---------------------------------------------------------------------------
def earnings_item(rep: dict) -> Optional[dict]:
    d = et_date((rep or {}).get("date"))
    if not d:
        return None
    when = rep.get("when")
    sess = " before the open" if when == "BMO" else (" after the close" if when == "AMC" else "")
    text = f"earnings report {d}{sess}"
    act, est = _num_txt(rep.get("eps_actual")), _num_txt(rep.get("eps_estimate"))
    if act is not None:
        eps = f"EPS {act}"
        if est is not None:
            eps += f" vs {est} est"
        sp = _f(rep.get("surprise_pct"))
        if sp is not None:
            eps += f" ({_pct_txt(sp)} surprise)"
        text += f" · {eps}"
    return {"kind": "earnings", "date": d, "text": text, "url": None,
            "source": "earnings_calendar", "when": when if when in ("BMO", "AMC") else None}


def filing_items(row: dict) -> list:
    out = []
    ek = (row or {}).get("eightk")
    if isinstance(ek, dict):
        d = et_date(ek.get("filing_date"))
        if d:
            codes = [str(c) for c in (ek.get("items") or []) if str(c).strip()]
            text = f"8-K {d}" + (f" items {', '.join(codes)}" if codes else "")
            out.append({"kind": "filing", "date": d, "text": text, "url": ek.get("url") or None,
                        "source": "promo_circuit_cache"})
    sh = ((row or {}).get("edgar") or {}).get("shelf")
    if isinstance(sh, dict):
        d = et_date(sh.get("filing_date"))
        if d:
            form = str(sh.get("form") or "").strip()
            text = f"offering / shelf filing {form} {d}".replace("  ", " ")
            out.append({"kind": "filing", "date": d, "text": text, "url": sh.get("url") or None,
                        "source": "promo_circuit_cache"})
    return out


def medical_item(ev: dict) -> Optional[dict]:
    d = et_date((ev or {}).get("published_at"))
    what = (ev or {}).get("label") or (ev or {}).get("headline")
    if not d or not what:
        return None
    url = ev.get("url")
    if not url:
        srcs = ev.get("sources") if isinstance(ev.get("sources"), list) else []
        url = next((s.get("url") for s in srcs if isinstance(s, dict) and s.get("url")), None)
    # critic r3 2026-10-03: keep the published TIME, as news_item does, so an
    # event out after 16:00 ET on the drop day is never "public by that close"
    return {"kind": "medical", "date": d, "text": f"medical event {d}: {what}",
            "url": url or None, "source": "med_catalyst_events",
            "ts": _epoch_any(ev.get("published_at"))}


def index_item(row: dict) -> Optional[dict]:
    d = et_date((row or {}).get("date"))
    idx = (row or {}).get("index")
    if not d or not idx:
        return None
    return {"kind": "index", "date": d, "text": f"removed from {idx} (detected {d})",
            "url": None, "source": "universe_changes"}


def news_item(n: dict) -> Optional[dict]:
    d = (n or {}).get("et_date")
    title = ((n or {}).get("title") or "").strip()
    if not d or not title:
        return None
    src = n.get("source")
    text = f"headline {d}: “{title}”" + (f" — {src}" if src else "")
    return {"kind": "news", "date": d, "text": text, "url": (n.get("url") or None),
            "source": n.get("cache") or "news", "ts": _epoch_s(n.get("published"))}


def analyst_item(a: dict) -> Optional[dict]:
    d = et_date((a or {}).get("date"))
    if not d:
        return None
    head = " ".join(str(x) for x in (a.get("firm"), a.get("action")) if x)
    parts = [f"analyst {d}:" + (f" {head}" if head else "")]
    fg, tg = a.get("from_grade"), a.get("to_grade")
    if fg or tg:
        parts.append(f"{fg or ''}→{tg or ''}".strip())
    # a target stored as 0 (or below) is a MISSING target, never a number
    pp = _num_txt(a.get("prior_pt")) if (_f(a.get("prior_pt")) or 0) > 0 else None
    npt = _num_txt(a.get("new_pt")) if (_f(a.get("new_pt")) or 0) > 0 else None
    if pp is not None or npt is not None:
        parts.append(f"PT {pp or ''}→{npt or ''}".strip())
    text = parts[0] + (" " + ", ".join(parts[1:]) if len(parts) > 1 else "")
    act = str(a.get("action") or "").strip().lower() or None
    return {"kind": "analyst", "date": d, "text": text, "url": None, "source": "analyst_pulse",
            "action": act}


def model_item(doc: dict, cache: str) -> Optional[dict]:
    d = et_date((doc or {}).get("date"))
    said = ((doc or {}).get("bear") or (doc or {}).get("why_positive") or "")
    said = str(said).strip()
    if not d or not said:
        return None
    by = doc.get("read_by") or "model"
    text = f"model's read (cached, {by}, {d}): {said}"[:MODEL_READ_CHARS]
    return {"kind": "model", "date": d, "text": text, "url": None, "source": cache}


# ---------------------------------------------------------------------------
# readers — ONE bulk read per source (I/O; every one replaceable in tests)
# ---------------------------------------------------------------------------
def _db(db=None):
    if db is not None:
        return db
    from sepa import history
    return history._get_db()


def company_profiles(syms, *, db=None) -> dict:
    """{SYM: {"name", "sector"}} — ONE `companies` find (the growth/api read)."""
    syms = sorted({str(s or "").strip().upper() for s in (syms or []) if s})
    if not syms:
        return {}
    d = _db(db)
    if d is None:
        return {}
    out = {}
    for doc in d.companies.find({"symbol": {"$in": syms}}, {"symbol": 1, "name": 1, "sector": 1}):
        s = str(doc.get("symbol") or "").upper()
        if s:
            out[s] = {"name": doc.get("name"), "sector": doc.get("sector")}
    return out


def _read_earnings(syms, names, db):
    from sepa import earnings_watch
    return earnings_watch.last_report_map(syms) or {}


def _read_analyst(syms, names, db):
    from sepa import analyst_pulse
    coll = analyst_pulse._coll()
    if coll is None:
        raise RuntimeError("analyst_pulse store unavailable")
    return {str(d.get("_id") or "").upper(): d
            for d in coll.find({"_id": {"$in": list(syms)}}, {"actions": 1})}


def _read_filing(syms, names, db):
    from catalysts import promo_circuit
    coll = promo_circuit._coll("promo_circuit_cache")
    if coll is None:
        raise RuntimeError("promo circuit cache unavailable")
    doc = coll.find_one({"_id": "latest"}) or {}
    want = set(syms)
    out = {}
    for r in ((doc.get("payload") or {}).get("rows") or []):
        t = str((r or {}).get("ticker") or "").upper()
        if t in want:
            out[t] = r
    return out


def _read_medical(syms, names, db):
    from catalysts.medical import store
    coll = store.colls()[store.EVENTS]
    if coll is None:
        raise RuntimeError("medical events store unavailable")
    out: dict = {}
    for ev in store.events_for_tickers(coll, syms):
        out.setdefault(str(ev.get("ticker") or "").upper(), []).append(ev)
    return out


def _read_index(syms, names, db):
    from sepa import universe_changes
    return list(universe_changes.recent(days=INDEX_READ_DAYS, limit=INDEX_READ_LIMIT) or [])


def _cache_query(coll_name: str, symf: str, syms: list) -> dict:
    q = dict(_EXTRA_QUERY.get(coll_name) or {})
    if not symf.startswith("@"):
        q[symf] = {"$in": list(syms)}
    return q


def _read_news(syms, names, db):
    """{SYM: [normalised item + cache]} over every cache in NEWS_CACHES — one
    find per cache, each in its own try (a missing cache costs only itself)."""
    from news_search import core as NS
    d = _db(db)
    if d is None:
        raise RuntimeError("no database")
    want = set(syms)
    out: dict = {}

    def add(sym, raw, provider, cache, fmap):
        sym = str(sym or "").upper()
        if sym not in want or not isinstance(raw, dict):
            return
        item = {k: raw.get(v) for k, v in fmap.items()} if fmap else dict(raw)
        # `normalise` reads an epoch `published` or an ISO `published_utc`;
        # a stored datetime / ISO string under either key is handed over as ISO.
        for k in ("published", "published_utc"):
            v = item.get(k)
            if isinstance(v, datetime):
                item["published_utc"] = (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
                if k == "published":
                    item.pop("published", None)
            elif k == "published" and isinstance(v, str):
                item["published_utc"] = v
                item.pop("published", None)
        prov = (raw.get("provider") or item.get("provider")) if provider == "@row" else provider
        n = NS.normalise(item, prov)
        n["cache"] = cache
        out.setdefault(sym, []).append(n)

    for coll_name, symf, rows_path, fmap, provider in NEWS_CACHES:
        try:
            for doc in d[coll_name].find(_cache_query(coll_name, symf, syms)):
                rows = doc if rows_path is None else _get(doc, rows_path)
                if isinstance(rows, dict):
                    rows = [rows]
                if not isinstance(rows, list):
                    continue
                for r in rows:
                    if symf == "@tickers":
                        for t in (r or {}).get("tickers") or []:
                            add(t, r, provider, coll_name, fmap)
                    elif symf == "@selector":
                        add((doc.get("selector") or {}).get("value"), r, provider, coll_name, fmap)
                    else:
                        add(doc.get(symf), r, provider, coll_name, fmap)
        except Exception as exc:                                # noqa: BLE001
            log.debug("fallen catalysts: news cache %s unreadable: %s", coll_name, exc)
    return out


def _read_model(syms, names, db):
    d = _db(db)
    if d is None:
        raise RuntimeError("no database")
    out: dict = {}
    for cache in MODEL_CACHES:
        for doc in d[cache].find({"symbol": {"$in": list(syms)}},
                                 {"symbol": 1, "date": 1, "read_by": 1, "bear": 1, "bull": 1,
                                  "why_positive": 1}):
            out.setdefault(str(doc.get("symbol") or "").upper(), []).append((cache, doc))
    return out


def _read_frames(syms):
    from sepa import prices
    return prices.bulk_cached_frames(syms) or {}


_READERS = {"earnings": _read_earnings, "analyst": _read_analyst, "filing": _read_filing,
            "medical": _read_medical, "index": _read_index, "news": _read_news,
            "model": _read_model}


# ---------------------------------------------------------------------------
# load — every source into dated items by symbol
# ---------------------------------------------------------------------------
def _items_of(kind: str, raw, syms: list, names: dict) -> dict:
    """{SYM: [item]} for one source's raw read. PURE."""
    out: dict = {}
    if kind == "earnings":
        for s, rep in (raw or {}).items():
            it = earnings_item(rep)
            if it:
                out.setdefault(str(s).upper(), []).append(it)
    elif kind == "filing":
        for s, row in (raw or {}).items():
            its = filing_items(row)
            if its:
                out.setdefault(str(s).upper(), []).extend(its)
    elif kind == "medical":
        for s, evs in (raw or {}).items():
            for ev in evs or []:
                it = medical_item(ev)
                if it:
                    out.setdefault(str(s).upper(), []).append(it)
    elif kind == "index":
        want = set(syms)
        for row in raw or []:
            if not isinstance(row, dict) or row.get("sane") is not True:
                continue          # the seed row and any unchecked diff never count
            for s in row.get("removed") or []:
                s = str(s or "").upper()
                if s in want:
                    it = index_item(row)
                    if it:
                        out.setdefault(s, []).append(it)
    elif kind == "news":
        from news_search import core as NS
        for s, items in (raw or {}).items():
            s = str(s).upper()
            kept = NS.relevance_filter(items or [], ticker=s, company=names.get(s))
            for n in NS.dedupe(kept):
                n = {**n, "et_date": et_date(n.get("published"))}
                it = news_item(n)            # undated -> None, never matched
                if it:
                    out.setdefault(s, []).append(it)
    elif kind == "analyst":
        for s, doc in (raw or {}).items():
            for a in ((doc or {}).get("actions") or []):
                it = analyst_item(a)
                if it:
                    out.setdefault(str(s).upper(), []).append(it)
    elif kind == "model":
        for s, docs in (raw or {}).items():
            for cache, doc in docs or []:
                it = model_item(doc, cache)
                if it:
                    out.setdefault(str(s).upper(), []).append(it)
    return out


def load(syms, *, names=None, db=None, readers=None) -> dict:
    """{kind: {"available", "error", "by_sym", "names", "first", "last"}} for
    every source in PRIORITY. ONE read per source, each in its own try."""
    syms = sorted({str(s or "").strip().upper() for s in (syms or []) if s})
    names = {str(k).upper(): v for k, v in (names or {}).items()}
    readers = readers or {}
    out: dict = {}
    for kind in SOURCE_KEYS:
        fn = readers.get(kind) or _READERS[kind]
        try:
            raw = fn(syms, names, db) if syms else {}
            by_sym = _items_of(kind, raw, syms, names)
            dates = [it["date"] for v in by_sym.values() for it in v]
            out[kind] = {"available": True, "error": None, "by_sym": by_sym,
                         "names": len(by_sym), "first": min(dates) if dates else None,
                         "last": max(dates) if dates else None}
        except Exception as exc:                                # noqa: BLE001
            log.debug("fallen catalysts: %s source unavailable: %s", kind, exc)
            out[kind] = {"available": False, "error": str(exc)[:200], "by_sym": {},
                         "names": 0, "first": None, "last": None}
    return out


# ---------------------------------------------------------------------------
# per drop (PURE)
# ---------------------------------------------------------------------------
def _in_window(day: Optional[str], drop: dict) -> bool:
    w = (drop or {}).get("window") or {}
    return bool(day) and bool(w.get("lo")) and bool(w.get("hi")) and w["lo"] <= day <= w["hi"]


def public_by_close(it: dict, drop_day: str) -> bool:
    """Was this item out by the drop session's close? Dated before the drop
    day, or ON it and neither an after-the-close (AMC) report nor stamped at
    or after SESSION_CLOSE (ET) that day. PURE."""
    d = str((it or {}).get("date") or "")
    if not d or not drop_day:
        return False
    if d < drop_day:
        return True
    return (d == drop_day and (it or {}).get("when") != "AMC"
            and not _after_close_on((it or {}).get("ts"), drop_day))


def items_for(sym: str, drop: dict, src: dict) -> list:
    """Every on-file item dated inside the drop's window, in PRIORITY order,
    the one nearest the drop day first inside a kind; on a tie, an analyst
    rating change before a maintained one, then the earliest published time
    (an item with none after the timed ones), then the source's own order. An
    item not public by the drop's close carries `after_drop: True` and the
    `AFTER_DROP` label on its text (kept in the fold, never the 💥 pick)."""
    sym = str(sym or "").upper()
    d0 = (drop or {}).get("date") or ""
    got = []
    for kind in PRIORITY:
        for it in ((src or {}).get(kind) or {}).get("by_sym", {}).get(sym, []):
            if _in_window(it.get("date"), drop):
                got.append(dict(it))
    try:
        o0 = date.fromisoformat(d0).toordinal()
    except ValueError:
        o0 = 0

    def key(pair):
        seq, it = pair
        try:
            dist = abs(date.fromisoformat(it["date"]).toordinal() - o0)
        except ValueError:
            dist = 10 ** 6
        change = 0 if (it["kind"] != "analyst"
                       or it.get("action") in ANALYST_CHANGE_ACTIONS) else 1
        ts = _epoch_s(it.get("ts"))
        return (PRIORITY.index(it["kind"]), dist, it["date"], change,
                ts is None, ts or 0.0, seq)
    got = [it for _seq, it in sorted(enumerate(got), key=key)]
    for it in got:
        it["after_drop"] = not public_by_close(it, d0)
        if it["after_drop"]:
            it["text"] = f"{AFTER_DROP}: {it['text']}"
    return got


def _public(items) -> list:
    return [it for it in (items or []) if not (it or {}).get("after_drop")]


def hit_class(items) -> str:
    """The 💥 class: the first PRIORITY kind among the items public by the
    drop's close ("nothing" when none is)."""
    kinds = {(it or {}).get("kind") for it in _public(items)}
    for k in PRIORITY:
        if k in kinds:
            return k
    return "nothing"


def empty_kinds(items) -> str:
    have = {(it or {}).get("kind") for it in (items or [])}
    missing = [KIND_LABELS[k] for k in EMPTY_ORDER if k not in have]
    head = f"{NOTHING}: {', '.join(missing)}" if missing else f"{NOTHING}: —"
    return f"{head}; {NOT_STORED}"


def day_returns(frames: dict, symbols, days) -> dict:
    """{SYM: {iso_day: close-to-close % that session}} for the given days, off
    cached daily frames. PURE."""
    want = set(days or ())
    out: dict = {}
    for s in symbols or []:
        df = (frames or {}).get(s)
        if df is None or len(df) < 2 or not want:
            continue
        try:
            import pandas as pd
            idx = pd.to_datetime(df.index)
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_convert("America/New_York").tz_localize(None)
            isos = [t.date().isoformat() for t in idx]
            cl = [_f(v) for v in df["close"].tolist()]
        except Exception:                                       # noqa: BLE001
            continue
        m = {}
        for i in range(1, len(isos)):
            if isos[i] in want and cl[i] is not None and cl[i - 1] and cl[i - 1] > 0:
                m[isos[i]] = (cl[i] / cl[i - 1] - 1.0) * 100
        if m:
            out[s] = m
    return out


def group_day(sym: str, day: str, sector: Optional[str], rets: dict) -> dict:
    """What the name's sector ETF, its theme's median member (the name left
    out) and RSP did that session. `rets` = `day_returns` output. No verdict
    word while GROUP_DAY_CUT is None."""
    from rotation import tracker as T
    from sepa import universe as U
    sym = str(sym or "").upper()
    rets = rets or {}
    etf = T.SECTOR_ETF.get(sector) if sector else None
    etf_pct = (rets.get(etf) or {}).get(day) if etf else None
    theme = U.THEME_BY_TICKER.get(sym)
    vals = []
    if theme:
        for m in U.THEME_UNIVERSE.get(theme) or []:
            m = str(m).upper()
            if m == sym:
                continue
            v = (rets.get(m) or {}).get(day)
            if v is not None:
                vals.append(v)
    theme_med = statistics.median(vals) if vals else None
    rsp = (rets.get(T.BENCHMARK) or {}).get(day)
    parts = []
    if etf and etf_pct is not None:
        parts.append(f"{etf} {_pct_txt(etf_pct)}")
    if theme and theme_med is not None:
        parts.append(f"theme {theme} median {_pct_txt(theme_med)} (n={len(vals)})")
    if rsp is not None:
        parts.append(f"{T.BENCHMARK} {_pct_txt(rsp)}")
    return {"sector": sector, "sector_etf": etf,
            "sector_etf_pct": None if etf_pct is None else round(etf_pct, 2),
            "theme": theme, "theme_median_pct": None if theme_med is None else round(theme_med, 2),
            "theme_n": len(vals), "rsp_pct": None if rsp is None else round(rsp, 2),
            "line": (" · ".join(parts) + " that day") if parts else ""}


def drop_line(drop: dict) -> str:
    """"−19.68% on 2026-02-12 · gap −11.56%, intraday −9.18% · 3.62× volume · 19.28% of the fall"."""
    d = drop or {}
    out = f"{_pct_txt(d.get('c2c_pct'))} on {d.get('date')}"
    legs = []
    if d.get("gap_pct") is not None:
        legs.append(f"gap {_pct_txt(d['gap_pct'])}")
    if d.get("intraday_pct") is not None:
        legs.append(f"intraday {_pct_txt(d['intraday_pct'])}")
    if legs:
        out += " · " + ", ".join(legs)
    if d.get("vol_x50") is not None:
        out += f" · {float(d['vol_x50']):.2f}× volume"
    if d.get("share_of_fall_pct") is not None:
        share = float(d["share_of_fall_pct"])
        if share > 100:
            # the drops_head wording: a share above 100% reads as impossible
            out += " · more than the high-to-close fall (it rallied in between)"
        else:
            out += f" · {share:.2f}% of the fall"
    return out


def hit_text(drop: dict, items, group: Optional[dict]) -> str:
    d = drop or {}
    cls = hit_class(items)
    best = next((it for it in _public(items) if it.get("kind") == cls), None)
    later = len(_public(items)) < len(items or [])
    leg = d.get("larger_leg")
    leg_pct = d.get("gap_pct") if leg == "gap" else d.get("intraday_pct")
    inner = ""
    if leg and leg_pct is not None:
        inner = f"{leg} {_pct_txt(leg_pct, 1)}"
    vol = d.get("vol_x50")
    if vol:
        inner += (", " if inner else "") + f"{float(vol):.1f}× its 50-day volume"
    head = f"{HIT_MARK} What hit it: {_pct_txt(d.get('c2c_pct'), 1)} on {d.get('date')}"
    if inner:
        head += f" ({inner})"
    gl = (group or {}).get("line") or ""
    if best:
        what = best["text"]
    else:
        what = f"{NOTHING} by that close" if later else NOTHING
    return (f"{head} — possible: {what}"
            + (f" · {gl}" if gl else ""))


# ---------------------------------------------------------------------------
# attach_all — the build's ONE call
# ---------------------------------------------------------------------------
def attach_all(reads: dict, *, sectors=None, names=None, frames=None, db=None,
               readers=None) -> dict:
    """`reads` = {SYM: [drop]} (from `fallen_tab.top_drops`). Returns
    {"by_sym": {SYM: [drop + items, group, line, empty]}, "coverage",
    "src_meta"}. ONE read per source + ONE cached-frames read for the group
    symbols the universe frames do not hold. Never raises on a source."""
    from rotation import tracker as T
    from sepa import universe as U
    reads = {str(k).upper(): list(v or []) for k, v in (reads or {}).items()}
    sectors = {str(k).upper(): v for k, v in (sectors or {}).items()}
    names = {str(k).upper(): v for k, v in (names or {}).items()}
    frames = frames or {}
    readers = readers or {}
    syms = sorted(reads)
    src = load(syms, names=names, db=db, readers=readers)

    days = {d.get("date") for v in reads.values() for d in v if d.get("date")}
    group_syms = {T.BENCHMARK}
    for s in syms:
        etf = T.SECTOR_ETF.get(sectors.get(s)) if sectors.get(s) else None
        if etf:
            group_syms.add(etf)
        th = U.THEME_BY_TICKER.get(s)
        if th:
            group_syms |= {str(m).upper() for m in (U.THEME_UNIVERSE.get(th) or [])}
    missing = sorted(g for g in group_syms if g not in frames)
    extra: dict = {}
    if missing and days:
        try:
            extra = (readers.get("frames") or _read_frames)(missing) or {}
        except Exception as exc:                                # noqa: BLE001
            log.debug("fallen catalysts: group frames unavailable: %s", exc)
            extra = {}
    gframes = {g: (frames.get(g) if g in frames else extra.get(g)) for g in group_syms}
    rets = day_returns(gframes, sorted(group_syms), days)

    by_sym: dict = {}
    total = nothing = 0
    with_item = 0
    for s in syms:
        rows = []
        any_item = False
        for d in reads[s]:
            items = items_for(s, d, src)
            grp = group_day(s, d.get("date"), sectors.get(s), rets)
            rows.append({**d, "line": drop_line(d), "items": items, "group": grp,
                         "empty": empty_kinds(items)})
            total += 1
            if items:
                any_item = True
            else:
                nothing += 1
        with_item += int(any_item)
        by_sym[s] = rows
    coverage = {"drops_total": total, "drops_nothing": nothing, "names_with_item": with_item,
                "names": len(syms)}
    src_meta = {k: {kk: v.get(kk) for kk in ("available", "error", "names", "first", "last")}
                for k, v in src.items()}
    return {"by_sym": by_sym, "coverage": coverage, "src_meta": src_meta}


def sources_block(src: dict, coverage: dict) -> dict:
    """The served 💥 sources line: what each source can hold, and how many of
    the listed names it holds anything for. Horizons cited from the readers:
    `earnings_watch.last_report_map` keeps the LATEST report only
    (earnings_watch.py:151); the promo circuit's 8-K / shelf windows are its
    own `_EIGHTK_WINDOW_DAYS` / `_SEC_WINDOW_DAYS` (promo_circuit.py:554,594)."""
    from catalysts import promo_circuit as PC
    s = src or {}
    cov = coverage or {}

    def n(k):
        return f"{int((s.get(k) or {}).get('names') or 0):,}"

    def first(k):
        f = (s.get(k) or {}).get("first")
        return f"earliest item on a listed name {f}" if f else "none on file"

    line = (f"On file — earnings: the latest report per name only ({n('earnings')}); "
            f"8-K / offering: promo-circuit names, the last {PC._EIGHTK_WINDOW_DAYS} / "
            f"{PC._SEC_WINDOW_DAYS} days ({n('filing')}); medical: {first('medical')} "
            f"({n('medical')}); index deletions: {first('index')}; news: {len(NEWS_CACHES)} "
            f"caches, mostly days to weeks ({n('news')}); analyst actions: {first('analyst')} "
            f"({n('analyst')}); model reads: news two-sided / sector tags ({n('model')}); "
            "guidance: not stored.")
    total = int(cov.get("drops_total") or 0)
    none = int(cov.get("drops_nothing") or 0)
    return {"note": POSSIBLE_NOTE, "line": line,
            "sources": [{"key": k, "label": SOURCE_LABELS[k],
                         "available": bool((s.get(k) or {}).get("available")),
                         "names": int((s.get(k) or {}).get("names") or 0),
                         "first": (s.get(k) or {}).get("first"),
                         "last": (s.get(k) or {}).get("last")} for k in SOURCE_KEYS],
            "drops": total, "nothing_on_file": none,
            "nothing_line": f"{none:,} of {total:,} drop days have nothing dated on file."}
