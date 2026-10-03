"""📉 Down 40%+ tab on Chart Maps (Ajay 2026-10-02).

The asks, verbatim:
  1. "Can you build me a tab in chart maps about stocks that dropped more than
     40% lowers from like app loving company as an example whcih si 60% low.
     But I also need you to capture informations about sales like Bondes and
     other indicators based on Bondes formula please."
  2. "Scan the universe and bring me these stocks"
  3. (mid-build) "also add things like possible catalyst that made is drop
     like that."

THE LIST. Every universe name whose last CLOSED close sits `THRESHOLD_PCT` or
more under its 52-week high — the highest intraday HIGH of the last
`KL.YEAR_BARS` closed sessions, read by `key_levels.period_levels` (never the
close max). Closed bars only: `KL.closed_frame` drops any bar dated the
session, and the session rolls at `KL.ROLL_AT` (the 🔑 / 🏔️ rule).

HELD OUT, COUNTED, NAMED. ETFs ("stocks"), delisted fates, stale bars, names
with fewer than `YEAR_BARS` sessions, and names whose last year carries a
one-session close move the price layer itself calls impossible
(`prices._is_scale_glitch`, `GLITCH_RATIO`) — those are named under the grid,
since a real collapse can trip that guard too.

BONDE, NEVER RETYPED. The sales numbers and his pick legs are the 📈 Bonde
tab's own: `bonde._row` (which calls `bonde_picks.legs_from_scan_row`) on the
scan row, then `bonde_picks.attach` for the cache legs; the legend is
`bonde_picks.legend()` served once. No criterion, threshold or quote of his is
written in this module.

💥 WHAT HIT IT is `chart_maps.fallen_catalysts` — possible, never proof.

THE MEMO. The whole read is built in a background thread, keyed by (session,
universe, scan generation), and served stale-while-revalidate; a request only
filters and orders the held rows. `MEMO_TTL_SEC` is cache freshness, never a
rule. WRITES NOTHING.

UNMEASURED: no study in this app measures a name this far under its 52-week
high forward, with any count of Bonde's legs. Display only — nothing here
gates a scan, pushes a phone, sizes a position or enters a lane.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from datetime import date, datetime
from typing import Optional

from chart_maps import dual_momentum_tab as DMT
from chart_maps import fallen_catalysts as FC
from chart_maps import key_levels_tab as KLT
from sepa import bonde as B
from sepa import bonde_picks as BP
from sepa import buyable_verdict as BV
from sepa import prices
from sepa import qoq as Q
from supply_demand import key_levels as KL

log = logging.getLogger("chart_maps.fallen_tab")

MARK = "\U0001F4C9"                      # 📉 (no VS16; FE literal must match)
TAB_KEY = "fallen"
MEASURED = False
REFERENCE = "52w"                        # HIS CALL #2 — the 52-week high (not all-time)
THRESHOLD_PCT = 40.0                     # HIS CALL #3 — his number: "dropped more than 40%" (listed at >= )
YEAR_BARS = KL.YEAR_BARS                 # imported, never typed
DEPTH_STEPS = (40, 50, 60, 70)           # HIS CALL #4 — a VIEW over the listed set; DEPTH_STEPS[0] == THRESHOLD_PCT
DEPTH_PARAM = "depth"
INCLUDE_ETFS = False                     # HIS CALL #5 — "stocks"
LIST_SHORT_HISTORY = False               # HIS CALL #6 — < YEAR_BARS sessions: counted, not listed
GLITCH_RATIO = prices._SCALE_GLITCH_RATIO  # imported — HIS CALL #7
# HIS CALL #23 (critic 2026-10-03) — the card's cap is the DM 💰 cap (shares x
# last close); when the shares doc's OWN market_cap disagrees by this ratio or
# more, the card leaves the cap badge off (a pre-reverse-split share count x a
# split-adjusted close: BYND read $4.2B vs its own $215M). The price layer's
# guard ratio, imported, never typed. Display only — gates nothing.
CAP_DISAGREE_RATIO = GLITCH_RATIO
MEMO_TTL_SEC = 60 * 60                   # cache freshness, NOT a rule
FAIL_RETRY_SEC = 5 * 60                  # the DMT precedent — retry cadence, NOT a rule
SORT_DEPTH = "fallen_depth"
SORT_SALES = "fallen_sales"
TAB_SORTS = (SORT_DEPTH, SORT_SALES) + DMT.CAP_SORTS
DEFAULT_SORT = "default"
DEFAULT_SORT_LABEL = "\U0001F4CB Most Bonde criteria first"     # 📋  — HIS CALL #1
DEPTH_SORT_LABEL = f"{MARK} Deepest below the high first"
SALES_SORT_LABEL = "\U0001F4C8 Sales growth first"              # 📈
TAB_LABEL = f"{MARK} Down {THRESHOLD_PCT:g}%+"                   # == TAB_META.fallen.label (contract)
GATED_KEYS = tuple(k for k in BP.COMPUTED_KEYS if k not in BP.FACT_KEYS)   # derived, never typed
COUNT_KEYS = ("scanned", "no_bars", "delisted", "etf", "stale", "short_history",
              "under_threshold", "data_suspect", "fallen", "at_depth", "in_scan",
              "dropped_thin", "no_turnover", "shown")
# The statuses `classify` hands out; `scanned` is their sum (test-pinned).
STATUSES = ("no_bars", "delisted", "etf", "stale", "short_history", "under_threshold",
            "data_suspect", "fallen")
SUSPECT_LINES_MAX = 40                   # display cap on the named list (count is always whole)

_MINUS = "−"

_memo: dict = {}                # (session_iso, ukey, scan_key) -> entry
_warming: set = set()
_failures: dict = {}            # key -> (ts, reason)
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# served words (constants)
# ---------------------------------------------------------------------------
NOTE = (f"{MARK} UNMEASURED — no study in this app says a stock {THRESHOLD_PCT:g}% or "
        "more under its 52-week high, with any count of Bonde's legs, does anything next. "
        "The order is a count and a distance, not a ranking of setups; nothing here gates a "
        "scan, pushes a phone, sizes a position or enters a lane. "
        f"{FC.HIT_MARK} items are what this app has on file within a session of the drop "
        "— possible, never proof of cause. Not advice.")
WARMING_NOTE = (f"{MARK} Reading every name's 52-week high from the cached daily bars and "
                "Bonde's legs from the last scan — the charts appear here as soon as it "
                "lands; you don't need to refresh.")
EMPTY_NOTE_FMT = (f"{MARK} No name sits {{depth}}% or more under its 52-week high right now "
                  "— the line above says what was not listed.")
ERROR_NOTE_FMT = (f"{MARK} The Down {{threshold}}%+ list could not be built ({{reason}}). It is "
                  "retried every {mins} minutes — this is not a warming state.")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    return KL._f(v)


def _m(s: str) -> str:
    return s.replace("-", _MINUS)


def _n(x) -> str:
    return f"{int(x or 0):,}"


def _usd(v) -> str:
    x = _f(v)
    if x is None:
        return "—"
    for div, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            return f"${x / div:g}{unit}"
    return f"${x:g}"


def _safe_reason(exc: BaseException) -> str:
    s = str(exc)
    if not s or "api_key" in s or "apikey" in s.lower() or "token" in s.lower():
        return type(exc).__name__
    return s[:200]


def session_for(now: datetime) -> date:
    return KL.levels_session(now)


def _ukey(universe) -> str:
    return KLT._ukey(universe)


def _scan_key() -> str:
    from sepa import scanner
    try:
        return str(scanner.latest_key())
    except Exception:                                           # noqa: BLE001
        return "None"


def _static_etfs() -> set:
    """The static ETF lists (no fetch): the broad ETF universe, the demand
    board's pinned ETFs and the RS anchors."""
    from sepa import universe as U
    from sepa.etf_universe import etf_universe
    from supply_demand import demand_reentry as D
    return {str(s).upper() for s in list(etf_universe()) + list(D.PINNED_ETFS)
            + list(U.RS_ANCHORS)}


# ---------------------------------------------------------------------------
# the closed read (PURE)
# ---------------------------------------------------------------------------
def _suspect(closed) -> Optional[dict]:
    """The worst adjacent-close pair in the last YEAR_BARS sessions that the
    price layer's own guard calls impossible, else None."""
    tail = closed.tail(YEAR_BARS)
    idx = KL._norm_index(tail)
    cl = [_f(v) for v in tail["close"].tolist()]
    worst = None
    for i in range(1, len(cl)):
        a, b = cl[i], cl[i - 1]
        if a is None or b is None or not prices._is_scale_glitch(a, b):
            continue
        r = a / b
        score = max(r, 1.0 / r)
        if worst is None or score > worst[0]:
            worst = (score, {"date": idx[i].date().isoformat(), "prev_close": round(b, 4),
                             "close": round(a, 4), "ratio": round(r, 4)})
    return None if worst is None else worst[1]


def closed_read(sym: str, df, session: date) -> Optional[dict]:
    """The closed-bar half for one name. None = no closed bars."""
    from supply_demand import quick_bounce as QB
    sym = str(sym or "").upper()
    closed = KL.closed_frame(df, session) if df is not None else None
    if closed is None or len(closed) == 0:
        return None
    idx = KL._norm_index(closed)
    close = _f(closed["close"].iloc[-1])
    if close is None or close <= 0:
        return None
    last_d = idx[-1].date()
    high = high_date = low = low_date = None
    for mem in KL.period_levels(closed, session, ("year",)):
        if mem.get("kind") == "high":
            high, high_date = float(mem["price"]), mem.get("set_on")
        elif mem.get("kind") == "low":
            low, low_date = float(mem["price"]), mem.get("set_on")
    if last_d < KL.prev_market_day(session):
        status = "stale"
    elif len(closed) < YEAR_BARS or high is None:
        status = "short_history"
    else:
        status = "ok"
    pct_below = round((1 - close / high) * 100, 2) if high else None
    pct_above_low = round((close / low - 1) * 100, 2) if low else None
    return {"symbol": sym, "close": round(close, 4), "close_date": last_d.isoformat(),
            "n_bars": int(len(closed)), "adv50": QB.avg_dollar_vol(closed), "status": status,
            "high": high, "high_date": high_date, "low": low, "low_date": low_date,
            "pct_below": pct_below, "pct_above_low": pct_above_low,
            "suspect": _suspect(closed) if status == "ok" else None}


def top_drops(closed, read: dict) -> list:
    """The `FC.TOP_DROPS` most negative close-to-close sessions strictly AFTER
    the 52-week high's day, through the last closed bar (ties: the later date
    first). PURE."""
    from supply_demand import momentum_burst as MB
    if closed is None or len(closed) < 2 or not read or not read.get("high_date"):
        return []
    idx = KL._norm_index(closed)
    days = [d.date().isoformat() for d in idx]
    cl = [_f(v) for v in closed["close"].tolist()]
    op = [_f(v) for v in closed["open"].tolist()]
    vo = [_f(v) for v in closed["volume"].tolist()]
    hd = str(read["high_date"])[:10]
    high, last = _f(read.get("high")), _f(read.get("close"))
    total_fall = (high - last) if (high is not None and last is not None) else None
    cands = []
    for i in range(1, len(days)):
        if days[i] <= hd:
            continue
        prev, cur = cl[i - 1], cl[i]
        if prev is None or cur is None or prev <= 0:
            continue
        c2c = (cur / prev - 1) * 100
        if c2c >= 0:
            continue
        cands.append((c2c, -date.fromisoformat(days[i]).toordinal(), i))
    cands.sort()
    out = []
    n = len(days)
    for c2c, _o, i in cands[:FC.TOP_DROPS]:
        prev, cur, o = cl[i - 1], cl[i], op[i]
        gap = (o / prev - 1) * 100 if (o is not None and o > 0) else None
        intra = (cur / o - 1) * 100 if (o is not None and o > 0) else None
        leg = None if gap is None or intra is None else ("gap" if gap < intra else "intraday")
        avg = MB.avg_volume_before(closed, days[i])
        vx = (vo[i] / avg) if (avg and vo[i] is not None) else None
        share = ((prev - cur) / total_fall * 100) if (total_fall and total_fall > 0) else None
        out.append({"date": days[i], "c2c_pct": round(c2c, 2),
                    "gap_pct": None if gap is None else round(gap, 2),
                    "intraday_pct": None if intra is None else round(intra, 2),
                    "larger_leg": leg, "vol_x50": None if vx is None else round(vx, 2),
                    "share_of_fall_pct": None if share is None else round(share, 2),
                    "prev_close": round(prev, 4), "close": round(cur, 4),
                    "window": {"lo": days[max(0, i - FC.WINDOW_BEFORE)],
                               "hi": days[min(n - 1, i + FC.WINDOW_AFTER)]}})
    return out


def classify(sym: str, frame, scan_row: Optional[dict], etf_set, session: date) -> tuple:
    """(status, read). First match: no_bars -> delisted -> etf -> stale ->
    short_history -> under_threshold -> data_suspect -> fallen.

    A delisted name or an ETF is counted as such only when it sits
    `THRESHOLD_PCT` or more under its high — otherwise it is `under_threshold`
    like any other name, so "Not listed: N ETFs" counts ETFs that WOULD have
    been listed, never every ETF in the universe (critic 2026-10-03)."""
    from sepa import symbols
    sym = str(sym or "").upper()
    read = closed_read(sym, frame, session) if frame is not None else None
    if read is None:
        return "no_bars", None
    deep = read["pct_below"] is not None and read["pct_below"] >= THRESHOLD_PCT
    if symbols.is_delisted(sym):
        return ("delisted" if deep else "under_threshold"), read
    if not INCLUDE_ETFS and (sym in (etf_set or ()) or bool((scan_row or {}).get("is_etf"))):
        return ("etf" if deep else "under_threshold"), read
    if read["status"] == "stale":
        return "stale", read
    if read["status"] == "short_history" and not LIST_SHORT_HISTORY:
        return "short_history", read
    if read["pct_below"] is None or read["pct_below"] < THRESHOLD_PCT:
        return "under_threshold", read
    if read.get("suspect") is not None:
        return "data_suspect", read
    return "fallen", read


def scan_part(scan_row: dict) -> dict:
    """The 📈 Bonde tab's own row for this scan row (sales numbers + the scan
    legs), the board's pair guard applied, plus the sales q/q. Never mutates
    the shared scan row."""
    pillar = BV._bonde_pillar(scan_row)
    row = B._row(scan_row, pillar, None)
    row["pair_blanked"] = False
    if B._pair_mismatch(scan_row):
        # exactly as the 📈 Bonde board blanks a held-out row's growth claim
        row["tier"] = None
        row["growth_yoy_pct"] = None
        row["prior_yoy_pct"] = None
        row["accelerating"] = None
        row["pair_blanked"] = True
    f = scan_row.get("fundamentals") or {}
    f = f if isinstance(f, dict) else {}
    q = Q.compute(rev_series=f.get("rev_q_series"), eps_series=f.get("eps_q_series"),
                  periods=f.get("q_period_series"))
    row["qoq_pct"] = q.get("growth_qoq_pct")
    row["qoq_base"] = q.get("growth_base")
    row["sector"] = scan_row.get("sector")
    row["name"] = scan_row.get("name")
    return row


def scan_note(in_scan: bool) -> Optional[str]:
    return None if in_scan else ("no SEPA scan row — Bonde's scan legs and the sales "
                                 "numbers are not read")


def checked_cap(cap, doc_cap) -> Optional[float]:
    """The DM 💰 cap, or None when the shares doc's own `market_cap` disagrees
    with it by `CAP_DISAGREE_RATIO` or more (either direction). No doc cap ->
    the cap stands. PURE."""
    c, m = _f(cap), _f(doc_cap)
    if c is None or c <= 0:
        return None
    if m is None or m <= 0:
        return c
    return None if max(c, m) / min(c, m) >= CAP_DISAGREE_RATIO else c


class _HeldDocs:
    """The shares docs already read, handed to `market_caps_for` as its coll
    (so its formula stays the ONE cap engine and the cache is read once)."""

    def __init__(self, docs: dict):
        self._docs = docs

    def find(self, q):
        want = ((q or {}).get("_id") or {}).get("$in") or []
        return [self._docs[s] for s in want if s in self._docs]


def shares_caps(names, last: dict, *, coll=None) -> dict:
    """{SYM: cap or None} — `promo_circuit.market_caps_for(..., cap=0)` (the DM
    💰 cap, zero provider calls) off ONE shares-cache read, each through
    `checked_cap`. I/O: the background build only."""
    from catalysts.promo_circuit import market_caps_for
    names = [str(s) for s in (names or [])]
    if coll is None:
        try:
            from sepa import volume_movers as vm
            coll = vm._shares_coll()
        except Exception:                                       # noqa: BLE001
            coll = None
    docs: dict = {}
    if coll is not None and names:
        for d in coll.find({"_id": {"$in": names}}):
            if isinstance(d, dict) and d.get("_id"):
                docs[d["_id"]] = d
    caps = market_caps_for(names, last or {}, coll=_HeldDocs(docs), cap=0) or {}
    return {s: checked_cap(caps.get(s), (docs.get(s) or {}).get("market_cap")) for s in names}


# ---------------------------------------------------------------------------
# build (I/O, the background thread only)
# ---------------------------------------------------------------------------
def _fallback_drops(drops: list) -> list:
    return [{**d, "line": FC.drop_line(d), "items": [], "group": FC.group_day(
        "", d.get("date"), None, {}), "empty": FC.empty_kinds([])} for d in drops]


def build(universe, session: date, *, universe_fn=None, frames_fn=None, scan_fn=None,
          scan_key_fn=None, attach_fn=None, caps_fn=None, profiles_fn=None,
          catalysts_fn=None) -> dict:
    """ONE cached-frames read, ONE shared scan read, ONE Bonde cache attach,
    ONE cap read, ONE profile read, ONE catalysts read. Raises on an empty
    frames read (never memoised)."""
    from chart_maps.board import tile_metrics
    ukey = _ukey(universe)
    if universe_fn is None:
        from supply_demand import demand_reentry as D
        syms_raw = D._resolve_universe(ukey)[0]
    else:
        syms_raw = universe_fn(ukey)
    syms: list = []
    seen: set = set()
    for s in syms_raw or []:
        s = str(s or "").strip().upper()
        if s and s not in seen:
            seen.add(s)
            syms.append(s)
    if frames_fn is None:
        frames_fn = prices.bulk_cached_frames
    frames = frames_fn(syms) or {}
    if syms and not frames:
        raise RuntimeError(f"fallen tab: the price-cache read returned no frames for "
                           f"{len(syms):,} names — not memoising an empty read")
    if scan_fn is None:
        from sepa import scanner
        scan_fn = scanner.load_latest_shared
    if scan_key_fn is None:
        from sepa import scanner
        scan_key_fn = scanner.latest_key
    scan = scan_fn() or {}
    scan_by = {}
    for r in (scan.get("all_results") or []):
        if isinstance(r, dict) and r.get("symbol"):
            scan_by[str(r["symbol"]).upper()] = r
    etf_set = _static_etfs()

    counts = {k: 0 for k in COUNT_KEYS}
    rows: dict = {}
    closed_by: dict = {}
    suspects: list = []
    for sym in syms:
        counts["scanned"] += 1
        df = frames.get(sym)
        srow = scan_by.get(sym)
        try:
            status, read = classify(sym, df, srow, etf_set, session)
        except Exception as exc:                                # noqa: BLE001
            log.debug("fallen tab: %s read failed: %s", sym, exc)
            status, read = "no_bars", None
        counts[status] += 1
        if status == "data_suspect":
            suspects.append({"symbol": sym, **read["suspect"], "pct_below": read["pct_below"]})
        if status != "fallen":
            continue
        part = scan_part(srow) if srow else {"symbol": sym, "pick": {"legs": {}}}
        fr = {**part, **read}
        fr["in_scan"] = bool(srow)
        fr["scan_note"] = scan_note(bool(srow))
        fr["metrics"] = tile_metrics(srow or {})
        if not isinstance(fr.get("pick"), dict):
            fr["pick"] = {"legs": {}}
        rows[sym] = fr
        counts["in_scan"] += int(bool(srow))
        closed_by[sym] = KL.closed_frame(df, session)

    fallen = list(rows.values())
    try:
        (attach_fn or BP.attach)(fallen, db=None)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("fallen tab: Bonde cache legs unavailable: %s", exc)
    for r in fallen:
        if "n_pass" not in (r.get("pick") or {}):
            BP._count(r)

    fsyms = sorted(rows)
    closes = {s: rows[s]["close"] for s in fsyms}
    if caps_fn is None:
        caps_fn = shares_caps
    try:
        caps = (caps_fn(fsyms, closes) or {}) if fsyms else {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("fallen tab: cap read failed: %s", exc)
        caps = {}
    try:
        profiles = ((profiles_fn or FC.company_profiles)(fsyms) or {}) if fsyms else {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("fallen tab: profile read failed: %s", exc)
        profiles = {}
    for s in fsyms:
        r = rows[s]
        cap = _f(caps.get(s)) if isinstance(caps, dict) else None
        r["market_cap"] = cap if (cap is not None and cap > 0) else None
        prof = profiles.get(s) or {}
        if r.get("sector"):
            r["sector_source"] = "scan"
        elif prof.get("sector"):
            r["sector"], r["sector_source"] = prof["sector"], "profile"
        else:
            r["sector"], r["sector_source"] = None, None
        r["name"] = r.get("name") or prof.get("name")
        r["drops"] = top_drops(closed_by.get(s), r)

    reads = {s: rows[s]["drops"] for s in fsyms}
    try:
        cat = (catalysts_fn or FC.attach_all)(
            reads, sectors={s: rows[s]["sector"] for s in fsyms},
            names={s: rows[s].get("name") for s in fsyms}, frames=frames)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("fallen tab: catalysts read failed: %s", exc)
        cat = None
    if not isinstance(cat, dict):
        n_d = sum(len(v) for v in reads.values())
        cat = {"by_sym": {}, "coverage": {"drops_total": n_d, "drops_nothing": n_d,
                                          "names_with_item": 0, "names": len(fsyms)},
               "src_meta": {}}
    by_sym = cat.get("by_sym") or {}
    for s in fsyms:
        r = rows[s]
        r["drops"] = by_sym.get(s) if s in by_sym else _fallback_drops(r["drops"])
        shares = [d.get("share_of_fall_pct") for d in r["drops"]
                  if d.get("share_of_fall_pct") is not None]
        r["top3_share_pct"] = round(sum(shares), 2) if shares else None
    del frames, closed_by

    dates = Counter(r["close_date"] for r in fallen)
    as_of = max(dates.items(), key=lambda kv: (kv[1], kv[0]))[0] if dates else None
    suspects.sort(key=lambda d: d["symbol"])
    now_ts = time.time()
    cov = cat.get("coverage") or {}
    return {"syms": syms, "rows": rows, "counts": counts, "suspects": suspects,
            "session": session.isoformat(), "as_of": as_of, "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=KL.ET).isoformat(timespec="seconds"),
            "ukey": ukey, "scan_key": str(scan_key_fn()),
            "scan_generated_at": (scan.get("generated_at") or scan.get("finished_at")
                                  or scan.get("started_at")),
            "in_scan": counts["in_scan"],
            "sources": FC.sources_block(cat.get("src_meta") or {}, cov),
            "drops_total": int(cov.get("drops_total") or 0),
            "drops_nothing": int(cov.get("drops_nothing") or 0)}


# ---------------------------------------------------------------------------
# memo — the ATH shape, keyed on the scan generation too
# ---------------------------------------------------------------------------
def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _store(key: tuple, entry: dict) -> bool:
    """Under `_lock`. A late older-session build is dropped; storing evicts
    older sessions and older scan keys of the same (session, universe)."""
    newest = max((k[0] for k in _memo), default=key[0])
    if key[0] < newest:
        log.info("fallen tab: dropped a late %s build (memo holds %s)", key[0], newest)
        return False
    for k in [k for k in _memo if k[0] < key[0] or (k[:2] == key[:2] and k != key)]:
        _memo.pop(k, None)
    _memo[key] = entry
    _failures.pop(key, None)
    return True


def _warm(key: tuple, universe: str, session: date) -> None:
    def _work():
        try:
            entry = build(universe, session)
            with _lock:
                _store(key, entry)
        except Exception as exc:                                # noqa: BLE001
            log.warning("fallen tab: build failed for %s: %s", key[:2], type(exc).__name__)
            with _lock:
                _failures[key] = (time.time(), _safe_reason(exc))
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"fallen-tab-{key[0]}-{key[1]}")


def cached_or_warm(universe, *, now: datetime, sync: bool = False) -> dict:
    """{"state": "ready"|"warming"|"error", "entry", "reason", "stale_scan"}.
    Fresh exact entry -> ready. `sync=True` builds inline (never spawns).
    Otherwise ONE background build (unless one failed under FAIL_RETRY_SEC
    ago) and the newest held entry of the same (session, universe) is served."""
    session = session_for(now)
    ukey = _ukey(universe)
    key = (session.isoformat(), ukey, _scan_key())
    with _lock:
        entry = _memo.get(key)
    fresh = entry is not None and (time.time() - float(entry.get("built_ts") or 0)) < MEMO_TTL_SEC
    if fresh:
        return {"state": "ready", "entry": entry, "reason": None, "stale_scan": False}
    if sync:
        try:
            built = build(ukey, session)
        except Exception as exc:
            with _lock:
                _failures[key] = (time.time(), _safe_reason(exc))
            raise
        with _lock:
            _store(key, built)
        return {"state": "ready", "entry": built, "reason": None, "stale_scan": False}
    with _lock:
        failed = _failures.get(key)
    backing_off = failed is not None and (time.time() - float(failed[0])) < FAIL_RETRY_SEC
    if not backing_off:
        _warm(key, ukey, session)
    with _lock:
        held_key = key if key in _memo else max(
            (k for k in _memo if k[:2] == key[:2]),
            key=lambda k: float(_memo[k].get("built_ts") or 0), default=None)
        held = _memo.get(held_key) if held_key is not None else None
    if held is not None:
        return {"state": "ready", "entry": held, "reason": None,
                "stale_scan": held_key != key}
    if failed is not None:
        return {"state": "error", "entry": None, "reason": failed[1] or "unknown",
                "stale_scan": False}
    return {"state": "warming", "entry": None, "reason": None, "stale_scan": False}


# ---------------------------------------------------------------------------
# per request: depth + order (PURE)
# ---------------------------------------------------------------------------
def parse_depth(raw) -> int:
    """A served depth step, else DEPTH_STEPS[0] (never below the threshold)."""
    try:
        v = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEPTH_STEPS[0]
    return v if (v in DEPTH_STEPS and str(raw).strip() == str(v)) else DEPTH_STEPS[0]


def bonde_key(r: dict) -> tuple:
    return (-int((r.get("pick") or {}).get("n_pass") or 0), -float(r["pct_below"]), r["symbol"])


def rank(entry: dict, *, sort: str, depth: int, caps_order_rank: bool = True) -> tuple:
    """(rows at `depth` in the asked order, counts). Rows are the memo's own
    dicts — READ-ONLY; the board copies the ones it uses."""
    rows = [r for r in (entry.get("rows") or {}).values()
            if r.get("pct_below") is not None and r["pct_below"] >= depth]
    rows.sort(key=bonde_key)
    if sort == SORT_DEPTH:
        rows.sort(key=lambda r: (-float(r["pct_below"]), r["symbol"]))
    elif sort == SORT_SALES:
        rows.sort(key=B._sales_key)
    elif sort in DMT.CAP_SORTS:
        pos = {r["symbol"]: i for i, r in enumerate(rows)}
        largest = sort == DMT.SORT_MARKET_CAP
        rows.sort(key=lambda r: DMT.market_cap_key(
            r.get("market_cap"), pos[r["symbol"]] if caps_order_rank else 0, r["symbol"],
            largest_first=largest))
    counts = {k: 0 for k in COUNT_KEYS}
    counts.update({k: v for k, v in (entry.get("counts") or {}).items() if k in counts})
    counts["at_depth"] = len(rows)
    return rows, counts


def served_sorts() -> list:
    return [{"key": DEFAULT_SORT, "label": DEFAULT_SORT_LABEL},
            {"key": SORT_DEPTH, "label": DEPTH_SORT_LABEL},
            {"key": SORT_SALES, "label": SALES_SORT_LABEL},
            {"key": DMT.SORT_MARKET_CAP, "label": DMT.MARKET_CAP_LABEL},
            {"key": DMT.SORT_MARKET_CAP_ASC, "label": DMT.MARKET_CAP_ASC_LABEL}]


def depths_block(depth: int) -> list:
    return [{"key": str(d), "label": f"≥{d}%", "on": d == depth,
             "default": d == DEPTH_STEPS[0]} for d in DEPTH_STEPS]


# ---------------------------------------------------------------------------
# words (every number from a constant or a count)
# ---------------------------------------------------------------------------
def header_text(counts: dict, *, depth: int, as_of) -> str:
    c = counts or {}
    text = (f"{MARK} {_n(c.get('fallen'))} of {_n(c.get('scanned'))} names closed "
            f"{THRESHOLD_PCT:g}% or more under their 52-week high on {as_of or '—'} "
            f"— the highest intraday high of the last {YEAR_BARS} closed sessions.")
    if depth > DEPTH_STEPS[0]:
        text += (f" {_n(c.get('at_depth'))} of them are {depth}% or more under it — the "
                 "depth you picked.")
    return text


def order_line(sort: str) -> str:
    if sort == SORT_DEPTH:
        return "Order: deepest under the 52-week high first."
    if sort == SORT_SALES:
        return ("Order: sales growth first — names whose year-ago quarter can carry a "
                "percentage first (the \U0001F4C8 Bonde tab's own order), names with no sales "
                "read last.")
    if sort in DMT.CAP_SORTS:
        largest = sort == DMT.SORT_MARKET_CAP
        return (f"Order: market cap, {'largest' if largest else 'smallest'} first — the "
                "shares-cache cap at the last close; a name with no cap sits last.")
    return ("Order: most of Bonde's pick legs read as PASS first — a count over the legs "
            "this app could read, an order and not a score (nothing has measured it); the "
            "deeper drop breaks a tie.")


def count_line(counts: dict, *, min_tier_label: str, need_date) -> str:
    c = counts or {}
    text = (f"Showing {_n(c.get('shown'))} — {_n(c.get('dropped_thin'))} under the "
            f"liquidity floor ({min_tier_label})")
    if int(c.get("no_turnover") or 0):
        text += f", {_n(c.get('no_turnover'))} with no turnover to check"
    text += (f". Not listed: {_n(c.get('etf'))} ETFs, {_n(c.get('data_suspect'))} with a "
             f"one-session close move of {GLITCH_RATIO:g}× or more in the last {YEAR_BARS} "
             "sessions (named below — check before trusting), "
             f"{_n(c.get('short_history'))} with fewer than {YEAR_BARS} sessions of history, "
             f"{_n(c.get('stale'))} whose cached bars end before {need_date}, "
             f"{_n(c.get('delisted'))} delisted, {_n(c.get('no_bars'))} with no cached bars. "
             f"Bonde's scan legs read on {_n(c.get('in_scan'))} of {_n(c.get('fallen'))} — "
             "the rest have no SEPA scan row (under the scan's liquidity floor or its history "
             "minimum).")
    return text


def suspects_block(suspects) -> dict:
    s = [x for x in (suspects or []) if isinstance(x, dict)]
    n = len(s)
    head = (f"{n:,} names held out — a one-session close move of {GLITCH_RATIO:g}× or "
            "more, the price layer's own split / decimal-shift guard. A real collapse can trip "
            "it too; check the chart.")
    lines = [f"{x['symbol']} — {float(x['prev_close']):.2f} → {float(x['close']):.2f} "
             f"on {x['date']} ({float(x['ratio']):.2f}× in one session)"
             for x in s[:SUSPECT_LINES_MAX]]
    return {"n": n, "head": head, "lines": lines}


def error_note(reason) -> str:
    return ERROR_NOTE_FMT.format(threshold=f"{THRESHOLD_PCT:g}", reason=str(reason or "unknown"),
                                 mins=int(FAIL_RETRY_SEC // 60))


def bonde_read(row: dict) -> dict:
    pick = (row or {}).get("pick") or {}
    n_pass = int(pick.get("n_pass") or 0)
    n_read = n_pass + int(pick.get("n_fail") or 0)
    n_not = max(0, len(GATED_KEYS) - n_read)
    if (row or {}).get("in_scan"):
        line = (f"\U0001F4CB Bonde: {n_pass} of the {n_read} legs read pass · "
                f"{n_not} not read")
    else:
        line = (f"\U0001F4CB Bonde: {n_pass} of the {n_read} legs read pass · the "
                f"{len(BP.SCAN_KEYS)} scan legs not read — no SEPA scan row")
    return {"n_pass": n_pass, "n_read": n_read, "n_not_read": n_not, "line": line}


def bonde_line(row: dict) -> str:
    return bonde_read(row)["line"]


def sales_line(row: dict) -> str:
    r = row or {}
    if r.get("pair_blanked"):
        return "Sales — the fiscal pair is not a year apart (the Bonde tab blanks it too)"
    yoy, prior = _f(r.get("growth_yoy_pct")), _f(r.get("prior_yoy_pct"))
    qoq = _f(r.get("qoq_pct")) if r.get("qoq_base") == Q.BASE_OK else None
    parts = []
    if yoy is not None:
        parts.append(_m(f"{yoy:+.1f}% y/y"))
    if qoq is not None:
        parts.append(_m(f"{qoq:+.1f}% q/q"))
    if prior is not None:
        parts.append(_m(f"prior {prior:+.1f}% y/y"))
    if not parts:
        return "Sales — not read"
    if r.get("period"):
        parts.append(str(r["period"]))
    text = "Sales " + " · ".join(parts)
    if yoy is not None and r.get("base_state") == "non_positive":
        text += " · year-ago revenue ≤ 0 — the % is a sign flip"
    elif yoy is not None and r.get("base_state") == "too_small":
        text += (f" · year-ago revenue under {_usd(B.MIN_MATERIAL_BASE_REV)} — the % "
                 "is arithmetic")
    return text


def sales_block(row: dict) -> dict:
    r = row or {}
    return {"yoy_pct": _f(r.get("growth_yoy_pct")), "prior_yoy_pct": _f(r.get("prior_yoy_pct")),
            "qoq_pct": _f(r.get("qoq_pct")), "qoq_base": r.get("qoq_base"),
            "period": r.get("period"), "period_ok": r.get("period_ok"),
            "base_state": r.get("base_state"), "pair_blanked": bool(r.get("pair_blanked")),
            "line": sales_line(r)}


# ---------------------------------------------------------------------------
# envelopes
# ---------------------------------------------------------------------------
def _block(state: str, *, session_iso: str, sort: str, depth: int, header: str,
           entry: Optional[dict] = None, counts: Optional[dict] = None, rows=None,
           stale_scan: bool = False, min_tier_label: Optional[str] = None) -> dict:
    ready = state == "ready" and entry is not None
    need = KL.prev_market_day(date.fromisoformat(session_iso)).isoformat()
    return {"state": state, "session": session_iso,
            "as_of": (entry or {}).get("as_of") if ready else None,
            "built_at": (entry or {}).get("built_at") if ready else None,
            "stale_scan": bool(stale_scan) if ready else False,
            "measured": MEASURED, "threshold_pct": THRESHOLD_PCT, "year_bars": YEAR_BARS,
            "glitch_ratio": GLITCH_RATIO, "depth_pct": depth, "depth_param": DEPTH_PARAM,
            "depths": depths_block(depth), "sort": sort, "header": header,
            "order_line": order_line(sort),
            "count_line": (count_line(counts, min_tier_label=min_tier_label or "—",
                                      need_date=need) if ready else None),
            "note": NOTE,
            "counts": dict(counts) if ready else None,
            "suspects": suspects_block((entry or {}).get("suspects")) if ready else None,
            "pick_legend": BP.legend() if ready else None,
            "pick_coverage": BP.coverage(list(rows or [])) if ready else None,
            "catalysts": (entry or {}).get("sources") if ready else None}


def ready_block(counts: dict, *, entry: dict, sort: str, depth: int, min_tier_label: str,
                rows=None, stale_scan: bool = False) -> dict:
    return _block("ready", session_iso=str(entry["session"]), sort=sort, depth=depth,
                  header=header_text(counts, depth=depth, as_of=entry.get("as_of")),
                  entry=entry, counts=counts, rows=rows, stale_scan=stale_scan,
                  min_tier_label=min_tier_label)


def warming_block(*, now: datetime, sort: str, depth: int) -> dict:
    return _block("warming", session_iso=session_for(now).isoformat(), sort=sort, depth=depth,
                  header=WARMING_NOTE)


def error_block(reason, *, now: datetime, sort: str, depth: int) -> dict:
    return _block("error", session_iso=session_for(now).isoformat(), sort=sort, depth=depth,
                  header=error_note(reason))


# ---------------------------------------------------------------------------
# tile words (served; the FE prints them verbatim)
# ---------------------------------------------------------------------------
def tile_badges(r: dict) -> list:
    return [{"text": f"{MARK} {float(r['pct_below']):.2f}% below the 52-week high",
             "tone": "warn"}]


def tile_stats(r: dict) -> list:
    low_v = "—"
    if r.get("low") is not None:
        low_v = f"{float(r['low']):.2f} · {r.get('low_date')}"
        if r.get("pct_above_low") is not None:
            low_v += " · " + _m(f"{float(r['pct_above_low']):+.2f}%")
    return [{"k": "52w high", "v": f"{float(r['high']):.2f} · {r.get('high_date')}"},
            {"k": "52w low", "v": low_v},
            {"k": "Sector", "v": r.get("sector") or "—"},
            {"k": "Sales", "v": sales_line(r)}]


def tile_marker(r: dict) -> Optional[dict]:
    drops = (r or {}).get("drops") or []
    if not drops or drops[0].get("c2c_pct") is None:
        return None
    d = drops[0]
    return {"date": d["date"], "label": _m(f"{float(d['c2c_pct']):+.1f}%")}


def why_text(r: dict, zone_text: str) -> str:
    return f"{MARK} {float(r['pct_below']):.2f}% under its 52-week high · {zone_text}"


def drops_head(r: dict) -> str:
    drops = (r or {}).get("drops") or []
    share = (r or {}).get("top3_share_pct")
    if not drops:
        return "No down day since the high in the cached bars"
    head = ("The biggest down day since the high" if len(drops) == 1
            else f"{len(drops)} biggest down days since the high")
    if share is None:
        return head
    if float(share) > 100:
        # it rallied between the drops: a share above 100% reads as impossible
        what = "its drop is" if len(drops) == 1 else "their drops add up to"
        return head + f" — {what} more than the high-to-close fall (it rallied in between)"
    return head + f" — {float(share):.1f}% of the fall"


def hit_block(r: dict) -> dict:
    drops = (r or {}).get("drops") or []
    if not drops:
        return {"text": f"{FC.HIT_MARK} What hit it: no down day since the high in the cached "
                        "bars", "class": "nothing", "date": None}
    d = drops[0]
    items = d.get("items") or []
    return {"text": FC.hit_text(d, items, d.get("group")), "class": FC.hit_class(items),
            "date": d.get("date")}


def tile_block(r: dict) -> dict:
    """The served `tile.fallen` (the board adds `zone`)."""
    return {"pct_below": r["pct_below"], "high": r["high"], "high_date": r.get("high_date"),
            "low": r.get("low"), "low_date": r.get("low_date"),
            "pct_above_low": r.get("pct_above_low"),
            "close": r["close"], "close_date": r.get("close_date"),
            "market_cap": r.get("market_cap"), "sector": r.get("sector"),
            "sector_source": r.get("sector_source"),
            "in_scan": bool(r.get("in_scan")), "scan_note": r.get("scan_note"),
            "bonde": bonde_read(r), "sales": sales_block(r), "hit": hit_block(r),
            "drops_head": drops_head(r),
            "drops": [dict(d) for d in (r.get("drops") or [])],
            "top3_share_pct": r.get("top3_share_pct")}
