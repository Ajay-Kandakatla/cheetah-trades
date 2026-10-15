"""🎢 High Beta tab on Chart Maps (Ajay 2026-10-14).

The ask, verbatim (the parts this tab builds): "Can you build me a category or
filter for High Beta stocks in Resilient and make a scan there were all down
today especially a qqq series. Can you please make sure you do a full scan."
— then "I am rethinking the ask now, I think Resielient and high beta will not
go hand in hand. Can you create a new tab for High Beta stocks" — then "in the
High Beta tab.I wanna able to sort my most volatile stocks".

THE LIST. Every stock of the `full` universe ∪ the Nasdaq-100 that sits in at
least one of his three categories (his answer: "give me all 3 categories"):
  b15    β ≥ `B15_MIN`;
  b20    β ≥ `B20_MIN`;
  top20  the top `TOP_PCT`% of every RATED stock by β (k = ceil(n × pct / 100),
         ties at the k-th β included).
The list is the UNION; each name carries every category it is in. β is the
house beta, `sepa.beta.beta_from_frame` (cov / var of `BETA_LOOKBACK` daily log
returns against SPY), over the cached bars STRICTLY before the session — never
today's in-progress bar. σ is 🛡️'s `sigma_pct` (sample stdev of the last
`SIGMA_BARS` daily % returns on the SPY calendar), on every row. A name with no
β (under `BETA_LOOKBACK` + 1 sessions) is not rated and is counted.

TODAY'S MOVE, by the 🔻 clock (`drop10_tab.mode_for`): live / after the close
off ONE snapshot over the listed names, read only when its own stamp is dated
the session (`drop10_tab.day_from_snapshot`), against 🛡️'s official prior close
(`resiliency_tab.official_prev_close`); a live prior close more than
`drop10_tab.PREV_CLOSE_TOL_PCT` off the cached one, or a scale glitch, is held
out and named (`drop10_tab.suspect_reason`). Outside the session it is the last
closed session off the cached bars. A name with no print is never "+0.00%".

THE VIEW (his ask: "all down today"): the red names by default; `hb_all=1`
lists every name, green and unread after the red ones. `rows` carries a
compact row for every listed name in the view; the charts are the top of it.

THREE ORDERS: β × today's drop (default), today's drop, σ (most volatile
first). An order, not a forecast.

THE MEMO. The 🔻 shape: a per-session base (β, σ, prior close, categories)
memoised for `BASE_TTL_SEC`, the live half rebuilt per `LIVE_TTL_SEC` /
`CLOSED_TTL_SEC` (cache freshness, never rules) by ONE background thread per
key, served stale-while-revalidate. WRITES NOTHING. Imports no board module at
module level.

UNMEASURED until `chart_maps.high_beta_measured.MEASURED` carries the study
verdict (`scripts/high_beta_study.py`, pre-registered in
`docs/research/high_beta_2026_10_14_prereg.md`). Display only — nothing here
gates a scan, sizes a position or enters a lane.
"""
from __future__ import annotations

import copy
import logging
import math
import statistics
import threading
import time
from datetime import date, datetime
from typing import Optional

from chart_maps import drop10_tab as D10
from chart_maps import dual_momentum_tab as DMT
from chart_maps import resiliency_tab as RES
from rotation import tracker as RT
from sepa import beta as BETA
from sepa import levered_etf as LE
from sepa import prices, universe

log = logging.getLogger("chart_maps.high_beta_tab")

# The session calendar (prev_market_day, ET, _day_mmdd) is 🔻's own module
# handle: one clock for the three memo tabs.
KL = D10.KL

MARK = "\U0001F3A2"                      # 🎢 (no VS16 — FE literals must match byte for byte)
DROP_MARK = "\U0001F4C9"                 # 📉
VOL_MARK = "\U0001F30A"                  # 🌊 (sort LABEL only) # MINE (AMENDMENTS §8)
TAB_KEY = "high_beta"
TAB_LABEL = f"{MARK} High Beta"          # == TAB_META.high_beta.label (contract)
B15_MIN = 1.5                            # Ajay 2026-10-14 ("give me all 3 categories")
B20_MIN = 2.0                            # Ajay 2026-10-14
TOP_PCT = 20.0                           # Ajay 2026-10-14 — top 20% of the rated universe by β
DOWN_CHIP_PCT = 5.0                      # Ajay 2026-10-14 ("down like 5 to 10%") — the d5 chip, at <= -5.00%
SIGMA_BARS = RES.VOL_AVG_BARS            # Ajay 2026-10-14 (K3a: the house 50-day σ, VOL_AVG_BARS)
CAT_KEYS = ("b15", "b20", "top20")
FILTER_PARAM, FILTER_MODE_PARAM = "hb", "hb_mode"
VIEW_PARAM = "hb_all"
FILTER_KEYS = ("b15", "b20", "top20", "qqq", "d5")      # canonical order; FE HB_FILTER_KEYS pinned equal
FILTER_LABELS = {"b15": f"{MARK} β ≥ {B15_MIN:.1f}", "b20": f"{MARK} β ≥ {B20_MIN:.1f}",
                 "top20": f"{MARK} Top {TOP_PCT:g}% by β", "qqq": "QQQ · Nasdaq-100",
                 "d5": f"{DROP_MARK} Down {DOWN_CHIP_PCT:g}%+ today"}
CAT_SHORT = {"b15": f"≥{B15_MIN:.1f}", "b20": f"≥{B20_MIN:.1f}", "top20": f"top {TOP_PCT:g}%"}
QQQ_ETF = "QQQ"                          # the ticker for the QQQ move line (a symbol, not a threshold)
BENCH = universe.BENCHMARK               # "SPY"
EW_BENCH = RT.BENCHMARK                  # "RSP"
BETA_LOOKBACK = BETA.BETA_LOOKBACK       # 252
INCLUDE_ETFS = D10.INCLUDE_ETFS          # False — "stocks"; leveraged ETFs would own the top 20%
LIVE_TTL_SEC, CLOSED_TTL_SEC = D10.LIVE_TTL_SEC, D10.CLOSED_TTL_SEC
BASE_TTL_SEC, FAIL_RETRY_SEC = D10.BASE_TTL_SEC, D10.FAIL_RETRY_SEC
MODE_LIVE, MODE_AFTER, MODE_CLOSED = D10.MODE_LIVE, D10.MODE_AFTER, D10.MODE_CLOSED
LAST_BASIS = RES.LAST_BASIS              # "last_session"
DEFAULT_SORT = "default"                 # == board.DEFAULT_SORT (test-pinned; no board import here)
SORT_SWING = "hb_swing"
SORT_DROP = "hb_drop"
SORT_VOL = "hb_vol"
TAB_SORTS = (SORT_SWING, SORT_DROP, SORT_VOL)
SWING_SORT_LABEL = f"{MARK} β × today's drop"
DROP_SORT_LABEL = f"{DROP_MARK} Today's drop"
VOL_SORT_LABEL = f"{VOL_MARK} Most volatile (σ {SIGMA_BARS}d)"
SUSPECT_LINES_MAX = D10.SUSPECT_LINES_MAX
STATES = ("read", "no_print", "no_snapshot", "stale", "suspect")
BASE_STATUSES = ("no_bars", "stale", "etf", "delisted", "short_history", "rated")
COUNT_KEYS = ("scanned", "ndx_added", "etf", "delisted", "no_bars", "stale", "short_history",
              "rated", "listed", "b15", "b20", "top20", "qqq", "read", "red", "up", "flat",
              "down5", "no_print", "no_snapshot", "today_stale", "suspect")
# The wording guard's list (tests, rules_info and the tape kinds reuse it). The
# AST guard in tests/test_high_beta_tab.py skips exactly this tuple's literals.
FORBIDDEN_WORDS = ("bounce", "fake", "rebound", "will reverse", "poised", "expected to",
                   "likely to", "potential to", "won't drop", "won’t drop", "predict")
MEASURED_DEFAULT = {"state": "unmeasured"}
STAT_SIGMA = f"σ ({SIGMA_BARS}d)"         # the σ stat key + table head (on the card face, K3a)
STAT_BETA, STAT_TODAY, STAT_SWING = "β", "Today", "β × drop"
# The A1 dense table: (column key, served head) in display order. The heads are
# the card's own stat keys, so the table and the card name a number the same
# way; the FE prints them verbatim and composes none.
# 🔗 (2026-10-14, "Can you add a short tag on these stocks for their Leverage
# equivalents like IRE for IREN, VSTL for VST"): the leveraged-ETF column sits
# right after Symbol (position = HIS CALL #8); its head is LE.STAT_KEY, the
# card's fold stat key.
TABLE_COLUMNS = (("symbol", "Symbol"), ("levered", LE.STAT_KEY), ("today", STAT_TODAY), ("beta", STAT_BETA),
                 ("swing", STAT_SWING), ("sigma", STAT_SIGMA), ("cats", MARK),
                 ("qqq", QQQ_ETF))

_MINUS = "−"

_memo: dict = {}                # (mode, session_iso, ukey) -> entry
_base_memo: dict = {}           # (session_iso, ukey) -> {"ts", "base"}
_warming: set = set()
_failures: dict = {}            # key -> (ts, reason)
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# served words (constants)
# ---------------------------------------------------------------------------
NOTE_PENDING = (f"{MARK} UNMEASURED — no study in this app says what a High-Beta stock does in "
                "the sessions after a down day. β × today's drop is an order, not a forecast: "
                "largest β × today's drop first. β is the app's 1-year beta against SPY "
                f"({BETA_LOOKBACK} daily log returns before this session); σ is the stdev of the "
                f"last {SIGMA_BARS} daily returns. Nothing here gates a scan, sizes a position or "
                f"enters a lane; the {MARK} tape-burst push watches these names for tape bursts — "
                "a description of prints, not this order. Not advice.")
MEASURED_FMT = (f"{MARK} MEASURED {{run_date}} (as of {{as_of}}, prereg {{prereg}}, survivors-only "
                f"cohort): names with β ≥ {{b15}} that closed {{cut}}%+ down closed {{pp:+.2f}} pp "
                "against same-β names that did not, over the next {h} sessions — CI "
                "[{lo:+.2f}, {hi:+.2f}], {n} sessions: {words}. SPY-red days only: {red_pp} "
                "({red_words}). Their {h}-session low sat {mae:+.2f}% under that close on "
                "average. β × today's drop stays an order, not a forecast.")
VERDICT_WORDS = {"separates": "on this record they reversed more",
                 "no_signal": "no difference this study can separate from zero",
                 "inverted": "on this record they did worse",
                 "too_small": "too few sessions to read"}
WARMING_NOTE = (f"{MARK} Rating every stock's 1-year beta against SPY and reading today's move — "
                "the charts appear here as soon as it lands; you don't need to refresh.")
EMPTY_NOTE = (f"{MARK} No stock is in a High-Beta category right now — the line above says what "
              "was not rated.")
EMPTY_VIEW_NOTE = (f"{MARK} No High-Beta name is red right now — tick “include green names” to "
                   "list every one.")
ERROR_NOTE_FMT = (f"{MARK} The High Beta list could not be built ({{reason}}). It is retried "
                  "every {mins} minutes — this is not a warming state.")
VIEW_LABEL = "include green names"
QQQ_OFF_REASON = "the Nasdaq-100 list could not be read this build"
FILTERS_NOTE_ALL = ("Ticked boxes narrow the list — every ticked box must pass. They sort "
                    "nothing, push nothing, gate nothing and enter no lane.")
FILTERS_NOTE_ANY = ("Ticked boxes narrow the list — a name passing ANY ticked box shows, with a "
                    "badge for each ticked box it passes; tick “must match all” to need "
                    "every one. They sort nothing, push nothing, gate nothing and enter no lane.")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    return D10._f(v)


def _pos(v) -> Optional[float]:
    return D10._pos(v)


def _n(x) -> str:
    return D10._n(x)


def _m(s: str) -> str:
    return D10._m(s)


def _safe_reason(exc: BaseException) -> str:
    return D10._safe_reason(exc)


def _ukey(universe_key) -> str:
    return D10._ukey(universe_key)


def mode_for(now: datetime) -> tuple:
    """(mode, session, tape, half_day) — 🔻's clock, re-exported (one clock)."""
    return D10.mode_for(now)


def ttl_for(mode: str) -> int:
    return D10.ttl_for(mode)


def _hhmm(ms) -> Optional[str]:
    x = _f(ms)
    if x is None or x <= 0:
        return None
    try:
        return datetime.fromtimestamp(x / 1000.0, tz=KL.ET).strftime("%H:%M")
    except (OverflowError, OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# the Nasdaq-100 + the universe (never raise)
# ---------------------------------------------------------------------------
def qqq_members(qqq_fn=None) -> tuple:
    """(frozenset of Nasdaq-100 names, block). An exception or an empty list
    -> (frozenset(), available False): no badge, the box passes no name."""
    err = None
    try:
        got = list((qqq_fn or universe.fetch_nasdaq100)() or [])
    except Exception as exc:                                    # noqa: BLE001
        got, err = [], _safe_reason(exc)
    syms = frozenset(str(s).strip().upper() for s in got if str(s or "").strip())
    src = None
    if qqq_fn is None:
        try:
            src = universe.last_source("nasdaq100")
        except Exception:                                       # noqa: BLE001
            src = None
    src = src if isinstance(src, dict) else {}
    if not syms and err is None:
        err = "the list came back empty"
    age = _f(src.get("age_days"))
    return syms, {"available": bool(syms), "n": len(syms),
                  "source": src.get("source") if syms else None,
                  "age_days": round(age, 1) if (age is not None and syms) else None,
                  "error": None if syms else err}


def resolve_symbols(universe_key, qqq, universe_fn=None) -> tuple:
    """(symbols, n added by the Nasdaq-100): the universe (🔻's resolver) then
    the Nasdaq-100 names not already in it — upper-cased, deduped, order-stable."""
    syms = D10._resolve(universe_key, universe_fn)
    seen = set(syms)
    added = [s for s in sorted(qqq or ()) if s not in seen]
    return syms + added, len(added)


# ---------------------------------------------------------------------------
# the per-name rating (PURE)
# ---------------------------------------------------------------------------
def rate_one(sym: str, df, *, session: date, bench_lr, trading_days, etf_set,
             is_delisted) -> tuple:
    """(status, row | None). First match: no_bars -> stale -> etf -> delisted
    -> short_history (β None) -> rated."""
    from supply_demand import zone_store
    sym = str(sym or "").upper()
    base = D10.base_read(df, session) if df is not None else None
    if base is None:
        return "no_bars", None
    if base.get("prev_date") != KL.prev_market_day(session).isoformat():
        return "stale", None
    if not INCLUDE_ETFS and sym in (etf_set or ()):
        return "etf", None
    if is_delisted(sym):
        return "delisted", None
    past = zone_store.drop_today(df, session)
    b = BETA.beta_from_frame(past, bench_lr)
    if b is None:
        return "short_history", None
    sg = RES.sigma_pct(RES.closes_by_day(past), trading_days)
    return "rated", {"symbol": sym, "beta": float(b), "sigma_pct": sg,
                     "prev_close": base["prev_close"], "prev_date": base["prev_date"],
                     "adv50": base.get("adv50"), "bar": base.get("bar"),
                     "n_bars": base.get("n_bars")}


def categories(rated: dict) -> tuple:
    """({sym: [cat keys]}, block). b15 / b20 by the cut; top20 = the k = ceil(n
    × TOP_PCT / 100) highest β, ties at the k-th β included; n = 0 -> no top20."""
    items = [(s, float(b)) for s, b in (rated or {}).items() if _f(b) is not None]
    n = len(items)
    cut, k = None, 0
    if n:
        k = max(1, math.ceil(n * TOP_PCT / 100.0))
        ordered = sorted(items, key=lambda x: (-x[1], x[0]))
        cut = ordered[min(k, n) - 1][1]
    cats: dict = {}
    nb = {"b15": 0, "b20": 0, "top20": 0}
    for s, b in items:
        c = []
        if b >= B15_MIN:
            c.append("b15")
        if b >= B20_MIN:
            c.append("b20")
        if cut is not None and b >= cut:
            c.append("top20")
        for key in c:
            nb[key] += 1
        if c:
            cats[s] = c
    block = {"b15": {"label": FILTER_LABELS["b15"], "min_beta": B15_MIN, "n": nb["b15"]},
             "b20": {"label": FILTER_LABELS["b20"], "min_beta": B20_MIN, "n": nb["b20"]},
             "top20": {"label": FILTER_LABELS["top20"], "pct": TOP_PCT, "cut_beta": cut,
                       "k": k, "of": n, "n": nb["top20"]},
             "rated": n, "union": len(cats)}
    return cats, block


# ---------------------------------------------------------------------------
# the base half — once per session (warm thread)
# ---------------------------------------------------------------------------
def build_base(universe_key, session: date, *, universe_fn=None, frames_fn=None, qqq_fn=None,
               etf_fn=None, is_delisted=None) -> dict:
    """ONE frames read over the universe ∪ the Nasdaq-100 + SPY / RSP / QQQ,
    then pure per-name math. Raises (never memoised) on an empty frames read
    or no SPY bars before the session."""
    from supply_demand import zone_store
    ukey = _ukey(universe_key)
    qqq, qblock = qqq_members(qqq_fn)
    syms, n_added = resolve_symbols(ukey, qqq, universe_fn)
    want = sorted(set(syms) | {BENCH, EW_BENCH, QQQ_ETF})
    frames = (frames_fn or prices.bulk_cached_frames)(want) or {}
    if syms and not frames:
        raise RuntimeError(f"high_beta tab: the price-cache read returned no frames for "
                           f"{len(want):,} names — not memoising an empty read")
    spy_past = zone_store.drop_today(frames.get(BENCH), session)
    bench_lr = BETA.log_returns(spy_past)
    if bench_lr is None:
        raise RuntimeError(f"high_beta tab: no {BENCH} bars before {session.isoformat()} — "
                           "no beta can be rated")
    trading_days = sorted(RES.closes_by_day(spy_past))
    if etf_fn is None:
        from chart_maps import fallen_tab as FAL
        etf_fn = FAL._static_etfs
    etf_set = etf_fn()
    if is_delisted is None:
        from sepa import symbols
        is_delisted = symbols.is_delisted

    counts = {k: 0 for k in COUNT_KEYS}
    counts["ndx_added"] = n_added
    rated: dict = {}
    for s in syms:
        counts["scanned"] += 1
        try:
            status, row = rate_one(s, frames.get(s), session=session, bench_lr=bench_lr,
                                   trading_days=trading_days, etf_set=etf_set,
                                   is_delisted=is_delisted)
        except Exception as exc:                                # noqa: BLE001
            log.debug("high_beta tab: %s rating failed: %s", s, exc)
            status, row = "no_bars", None
        counts[status] += 1
        if row is not None:
            rated[s] = row
    cats, cblock = categories({s: r["beta"] for s, r in rated.items()})
    rows = {}
    for s in sorted(cats):
        rows[s] = {**rated[s], "cats": list(cats[s]), "qqq": s in qqq}
    counts["listed"] = len(rows)
    for k in CAT_KEYS:
        counts[k] = cblock[k]["n"]
    counts["qqq"] = sum(1 for r in rows.values() if r["qqq"])
    bench = {}
    for b in (BENCH, EW_BENCH, QQQ_ETF):
        try:
            bench[b] = D10.base_read(frames.get(b), session)
        except Exception:                                       # noqa: BLE001
            bench[b] = None
    del frames
    now_ts = time.time()
    return {"session": session.isoformat(), "ukey": ukey, "rows": rows, "bench": bench,
            "counts": counts, "categories": cblock, "qqq": qblock,
            "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=KL.ET).isoformat(timespec="seconds")}


def _base_for(key: tuple, universe_key, session: date, **fns) -> dict:
    with _lock:
        held = _base_memo.get(key)
    if held is not None and (time.time() - held["ts"]) < BASE_TTL_SEC:
        return held["base"]
    base = build_base(universe_key, session, **fns)
    with _lock:
        for k in [k for k in _base_memo if k[0] < key[0]]:
            _base_memo.pop(k, None)
        _base_memo[key] = {"ts": time.time(), "base": base}
    return base


# ---------------------------------------------------------------------------
# today's move (PURE)
# ---------------------------------------------------------------------------
def _today(state: str, *, mode: str, session_iso: str, reason=None) -> dict:
    return {"state": state, "move_pct": None, "prev_close": None, "print": None,
            "basis": None, "mode": mode, "day": session_iso, "reason": reason}


def today_read(row: Optional[dict], raw: Optional[dict], *, mode: str, session: date,
               answered: bool = True) -> tuple:
    """(today dict, as_of_ms | None). Closed: the cached session bar against
    the cached prior close. Live / after the close: the snapshot day bar dated
    the session, against the official prior close; a disagreeing prior close or
    a scale glitch is `suspect` (held out, named)."""
    s_iso = session.isoformat()
    row = row if isinstance(row, dict) else {}
    if not row.get("prev_close"):
        return _today("stale" if mode == MODE_CLOSED else "no_print", mode=mode,
                      session_iso=s_iso), None
    if mode == MODE_CLOSED:
        day = D10.day_from_bar(row)
        if day is None:
            return _today("stale", mode=mode, session_iso=s_iso), None
        prev, basis = float(row["prev_close"]), LAST_BASIS
    else:
        if not answered or not isinstance(raw, dict):
            return _today("no_snapshot", mode=mode, session_iso=s_iso), None
        day = D10.day_from_snapshot(raw, session)
        if day is None:
            return _today("no_print", mode=mode, session_iso=s_iso), None
        prev = RES.official_prev_close(raw, row["prev_close"], session)
        basis = "live" if mode == MODE_LIVE else "day_close"
    why = D10.suspect_reason({}, day, row)
    if why:
        out = _today("suspect", mode=mode, session_iso=s_iso, reason=why)
        out.update(print=round(day["last"], 4), prev_close=round(float(row["prev_close"]), 4))
        return out, day.get("as_of_ms")
    mv = D10._pct(day["last"], prev)
    if mv is None:
        return _today("no_print", mode=mode, session_iso=s_iso), None
    out = _today("read", mode=mode, session_iso=s_iso)
    out.update(move_pct=mv, prev_close=round(float(prev), 4), print=round(day["last"], 4),
               basis=basis)
    return out, day.get("as_of_ms")


def swing(beta, move_pct) -> Optional[float]:
    """β × |today's drop| (0 for an up or flat name); None if either is None."""
    b, m = _f(beta), _f(move_pct)
    if b is None or m is None:
        return None
    return round(b * max(-m, 0.0), 2)


def is_red(r: dict) -> bool:
    td = (r or {}).get("today") or {}
    mv = _f(td.get("move_pct"))
    return td.get("state") == "read" and mv is not None and mv < 0


def tile_filter(r: dict, *, qqq_available: bool) -> dict:
    """The five boxes: True / False, None = not read (never passes a box)."""
    cats = set((r or {}).get("cats") or ())
    td = (r or {}).get("today") or {}
    mv = _f(td.get("move_pct"))
    d5 = (mv <= -DOWN_CHIP_PCT) if (td.get("state") == "read" and mv is not None) else None
    return {"b15": "b15" in cats, "b20": "b20" in cats, "top20": "top20" in cats,
            "qqq": bool(r.get("qqq")) if qqq_available else None, "d5": d5}


# ---------------------------------------------------------------------------
# the live half
# ---------------------------------------------------------------------------
def _levered_state(now: datetime, levered_fn=None) -> dict:
    """The 🔗 map (sepa.levered_etf.load: ONE Mongo doc read, memoised; the
    day's reference refresh runs on its own thread, never here). A raise ->
    the `error` state — the board builds, no tag."""
    try:
        lev = (levered_fn or LE.load)(now=now)
        return lev if isinstance(lev, dict) else {"state": "error", "reason": "no map"}
    except Exception as exc:                                    # noqa: BLE001
        return {"state": "error", "reason": _safe_reason(exc)}


def build_live(base: dict, now: datetime, *, snap_fn=None, levered_fn=None) -> dict:
    """ONE snapshot over the listed names + SPY / RSP / QQQ (live / after the
    close only), missing names asked ONCE more. Base rows are copied, never
    mutated. Each row carries its 🔗 leveraged-ETF items + chip (display
    only: they sort, filter and gate nothing)."""
    mode, session, _tape, half = mode_for(now)
    s_iso = session.isoformat()
    listed = sorted((base.get("rows") or {}))
    benches = (BENCH, EW_BENCH, QQQ_ETF)
    snaps: dict = {}
    if mode != MODE_CLOSED:
        if snap_fn is None:
            from chart_maps.board import _bulk_snaps_fanout as snap_fn
        want = sorted(set(listed) | set(benches))
        snaps = dict(snap_fn(want) or {})
        if listed and not snaps:
            raise RuntimeError(f"high_beta tab: the live snapshot returned nothing for "
                               f"{len(listed):,} names — not memoising an empty read")
        missing = [s for s in want if s not in snaps]
        if missing:
            try:
                snaps.update(snap_fn(missing) or {})
            except Exception as exc:                            # noqa: BLE001
                log.debug("high_beta tab: snapshot retry failed: %s", exc)

    qqq_ok = bool((base.get("qqq") or {}).get("available"))
    counts = {k: 0 for k in COUNT_KEYS}
    counts.update({k: v for k, v in (base.get("counts") or {}).items() if k in counts})
    rows: dict = {}
    suspects: list = []
    moves: list = []
    as_ofs: list = []
    lev = _levered_state(now, levered_fn)
    n_lev = 0
    for s in listed:
        b = base["rows"][s]
        td, ms = today_read(b, snaps.get(s), mode=mode, session=session,
                            answered=(mode == MODE_CLOSED or s in snaps))
        r = {k: v for k, v in b.items() if k != "bar"}
        r["today"] = td
        r["swing"] = swing(r.get("beta"), td.get("move_pct"))
        r["hb_filter"] = tile_filter(r, qqq_available=qqq_ok)
        full = LE.items_for(lev, s)
        r["levered"] = [{"etf": x["etf"], "factor": float(x.get("factor") or 0),
                         "direction": x.get("direction")} for x in full]
        r["levered_chip"] = LE.chip(full)
        n_lev += int(bool(full))
        rows[s] = r
        st = td["state"]
        if st == "read":
            counts["read"] += 1
            mv = float(td["move_pct"])
            moves.append(mv)
            counts["red" if mv < 0 else ("up" if mv > 0 else "flat")] += 1
            counts["down5"] += int(mv <= -DOWN_CHIP_PCT)
            if ms:
                as_ofs.append(ms)
        elif st == "stale":
            counts["today_stale"] += 1
        else:
            counts[st] += 1
        if st == "suspect":
            suspects.append({"symbol": s, "reason": td.get("reason"), "print": td.get("print"),
                             "prev_close": td.get("prev_close")})

    bench_today = {}
    for bsym in benches:
        td, ms = today_read((base.get("bench") or {}).get(bsym), snaps.get(bsym), mode=mode,
                            session=session, answered=(mode == MODE_CLOSED or bsym in snaps))
        bench_today[bsym] = (td, ms)
    spy_td, spy_ms = bench_today[BENCH]
    summary = {"mode": mode, "day": s_iso, "half_day": bool(half),
               "read": counts["read"], "up": counts["up"], "red": counts["red"],
               "flat": counts["flat"], "down5": counts["down5"],
               "stale": counts["today_stale"],
               "median_move_pct": round(statistics.median(moves), 2) if moves else None,
               "spy_move_pct": spy_td.get("move_pct"), "spy_state": spy_td.get("state"),
               "rsp_move_pct": bench_today[EW_BENCH][0].get("move_pct"),
               "rsp_state": bench_today[EW_BENCH][0].get("state"),
               "qqq_move_pct": bench_today[QQQ_ETF][0].get("move_pct"),
               "qqq_state": bench_today[QQQ_ETF][0].get("state"),
               "spy_as_of_et": _hhmm(spy_ms) if mode == MODE_LIVE else None}
    as_of = (datetime.fromtimestamp(max(as_ofs) / 1000.0, tz=KL.ET).isoformat(timespec="minutes")
             if as_ofs else s_iso)
    suspects.sort(key=lambda x: x["symbol"])
    now_ts = time.time()
    return {"rows": rows, "counts": counts, "summary": summary,
            "categories": dict(base.get("categories") or {}), "qqq": dict(base.get("qqq") or {}),
            "suspects": suspects, "mode": mode, "session": s_iso, "as_of": as_of,
            "half_day": bool(half), "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=KL.ET).isoformat(timespec="seconds"),
            "base_built_at": base.get("built_at"), "ukey": base.get("ukey"),
            "levered": LE.status_block(lev, n_on=n_lev, listed=len(listed))}


def build(universe_key, now: datetime, *, universe_fn=None, frames_fn=None, qqq_fn=None,
          etf_fn=None, is_delisted=None, snap_fn=None, levered_fn=None) -> dict:
    """The memo's entry: the session's base (memoised) + today's read."""
    _mode, session, _t, _h = mode_for(now)
    ukey = _ukey(universe_key)
    base = _base_for((session.isoformat(), ukey), ukey, session, universe_fn=universe_fn,
                     frames_fn=frames_fn, qqq_fn=qqq_fn, etf_fn=etf_fn,
                     is_delisted=is_delisted)
    return build_live(base, now, snap_fn=snap_fn, levered_fn=levered_fn)


# ---------------------------------------------------------------------------
# memo — the 🔻 shape verbatim
# ---------------------------------------------------------------------------
def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _store(key: tuple, entry: dict) -> bool:
    """Under `_lock`. A late older-session build is dropped; storing evicts
    older sessions and the other modes of the same (session, universe)."""
    newest = max((k[1] for k in _memo), default=key[1])
    if key[1] < newest:
        log.info("high_beta tab: dropped a late %s build (memo holds %s)", key[1], newest)
        return False
    for k in [k for k in _memo if k[1] < key[1] or (k[1:] == key[1:] and k != key)]:
        _memo.pop(k, None)
    _memo[key] = entry
    _failures.pop(key, None)
    return True


def _warm(key: tuple, universe_key: str, now: datetime) -> None:
    def _work():
        try:
            entry = build(universe_key, now)
            with _lock:
                _store(key, entry)
        except Exception as exc:                                # noqa: BLE001
            log.warning("high_beta tab: build failed for %s: %s", key, type(exc).__name__)
            with _lock:
                _failures[key] = (time.time(), _safe_reason(exc))
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"high-beta-tab-{key[1]}-{key[2]}")


def cached_or_warm(universe_key, *, now: datetime, sync: bool = False) -> dict:
    """{"state": "ready"|"warming"|"error", "entry", "reason", "stale"}. A
    fresh exact entry -> ready. `sync=True` builds inline. Otherwise ONE
    background build per key (unless one failed under FAIL_RETRY_SEC ago)
    while the newest held entry of the same session + universe is served."""
    mode, session, _tape, _half = mode_for(now)
    ukey = _ukey(universe_key)
    key = (mode, session.isoformat(), ukey)
    with _lock:
        entry = _memo.get(key)
    fresh = entry is not None and (time.time() - float(entry.get("built_ts") or 0)) < ttl_for(mode)
    if fresh:
        return {"state": "ready", "entry": entry, "reason": None, "stale": False}
    if sync:
        try:
            built = build(ukey, now)
        except Exception as exc:
            with _lock:
                _failures[key] = (time.time(), _safe_reason(exc))
            raise
        with _lock:
            _store(key, built)
        return {"state": "ready", "entry": built, "reason": None, "stale": False}
    with _lock:
        failed = _failures.get(key)
    backing_off = failed is not None and (time.time() - float(failed[0])) < FAIL_RETRY_SEC
    if not backing_off:
        _warm(key, ukey, now)
    with _lock:
        held_key = key if key in _memo else max(
            (k for k in _memo if k[1:] == key[1:]),
            key=lambda k: float(_memo[k].get("built_ts") or 0), default=None)
        held = _memo.get(held_key) if held_key is not None else None
    if held is not None:
        return {"state": "ready", "entry": held, "reason": None, "stale": True}
    if failed is not None:
        return {"state": "error", "entry": None, "reason": failed[1] or "unknown",
                "stale": False}
    return {"state": "warming", "entry": None, "reason": None, "stale": False}


# ---------------------------------------------------------------------------
# per request: sort, view, filters (PURE)
# ---------------------------------------------------------------------------
def resolve_sort(sort) -> str:
    """The served key: `default` (and any unknown key) -> β × today's drop."""
    return sort if sort in TAB_SORTS else SORT_SWING


def parse_filters(spec) -> tuple:
    """`?hb=` -> the known keys in canonical order; junk dropped."""
    if not isinstance(spec, str):
        return ()
    toks = {t.strip().lower() for t in spec.replace("+", ",").split(",") if t.strip()}
    return tuple(k for k in FILTER_KEYS if k in toks)


def parse_mode(v) -> str:
    return DMT.parse_mode(v)


def _bucket(r: dict) -> int:
    td = r.get("today") or {}
    mv = _f(td.get("move_pct"))
    if td.get("state") != "read" or mv is None:
        return 2
    return 0 if mv < 0 else 1


def sort_key(sort: str):
    def key(r):
        sym = r["symbol"]
        beta = float(r.get("beta") or 0.0)
        if sort == SORT_VOL:
            sg = _f(r.get("sigma_pct"))
            return (sg is None, -(sg or 0.0), sym)
        b = _bucket(r)
        if b == 2:
            return (2, 0.0, -beta, sym)
        mv = float(r["today"]["move_pct"])
        if b == 1:
            return (1, mv, -beta, sym)
        if sort == SORT_DROP:
            return (0, mv, -beta, sym)
        return (0, -float(r.get("swing") or 0.0), mv, sym)
    return key


def filter_note(k: str, qqq: dict) -> str:
    if k == "b15":
        return (f"β ≥ {B15_MIN:.1f} — the app's 1-year beta against SPY. UNMEASURED.")
    if k == "b20":
        return (f"β ≥ {B20_MIN:.1f} — the app's 1-year beta against SPY. UNMEASURED.")
    if k == "top20":
        return (f"The top {TOP_PCT:g}% of every rated stock by β (ties at the cut included). "
                "UNMEASURED.")
    if k == "qqq":
        q = qqq if isinstance(qqq, dict) else {}
        if not q.get("available"):
            return f"Nasdaq-100 member — {QQQ_OFF_REASON}; ticked, this box passes no name."
        age = _f(q.get("age_days"))
        return (f"Nasdaq-100 member (Wikipedia list, {q.get('source') or 'source unknown'}"
                + (f", {age:.0f} d old" if age is not None else "") + ").")
    return (f"Today's move {DOWN_CHIP_PCT:g}% or more under the official prior close. "
            "UNMEASURED.")


def filter_line(items, passed_all, pool, *, mode, shown) -> Optional[str]:
    """DMT's line with "name(s)" in place of "leader(s)"."""
    on = [i for i in (items or []) if isinstance(i, dict) and i.get("on")]
    if not on:
        return None
    if parse_mode(mode) == DMT.MODE_ANY:
        bits = []
        for i in on:
            b = f"{i['label']}: {_n(i.get('pass'))} pass"
            if int(i.get("no_read") or 0) > 0:
                b += f" ({_n(i.get('no_read'))} not read)"
            bits.append(b)
        n_shown, n_pool = int(shown or 0), int(pool or 0)
        return (f"Filters on (any ticked box) — {'; '.join(bits)}. {_n(n_shown)} of {_n(n_pool)} "
                f"pass at least one ticked box, {_n(max(n_pool - n_shown, 0))} hidden (they pass "
                "none of them; a name passing several shows once, with a badge for each).")
    bits = []
    for i in on:
        b = f"{i['label']}: {_n(i.get('pass'))} pass, {_n(i.get('hidden'))} hidden"
        if int(i.get("no_read") or 0) > 0:
            b += f" ({_n(i.get('no_read'))} not read)"
        bits.append(b)
    return (f"Filters on ({DMT.MODE_ALL_LABEL}) — {'; '.join(bits)}. {_n(passed_all)} of "
            f"{_n(pool)} pass every ticked box (each count is over all {_n(pool)} names in "
            "view; a name can fail more than one).")


def filters_block(tfs, active, *, pool: int, mode, qqq: dict) -> dict:
    """Per-box counts over every name in the view (each box independently),
    the served line when any is ticked, and the QQQ box `off` when the
    Nasdaq-100 list could not be read."""
    tfs = [t if isinstance(t, dict) else {} for t in (tfs or [])]
    act = tuple(k for k in FILTER_KEYS if k in (active or ()))
    md = parse_mode(mode)
    q_ok = bool((qqq or {}).get("available"))
    items = []
    for k in FILTER_KEYS:
        vals = [t.get(k) for t in tfs]
        n_pass = sum(1 for v in vals if v is True)
        n_fail = sum(1 for v in vals if v is False)
        n_none = len(vals) - n_pass - n_fail
        on = k in act
        it = {"key": k, "label": FILTER_LABELS[k], "on": on, "pass": n_pass, "fail": n_fail,
              "no_read": n_none, "hidden": (n_fail + n_none) if on else 0,
              "note": filter_note(k, qqq)}
        if k == "qqq" and not q_ok:
            it.update(off=True, off_reason=QQQ_OFF_REASON)
        items.append(it)
    passed_all = sum(1 for t in tfs if DMT.passes(t, act, DMT.MODE_ALL)) if act else None
    passed_any = sum(1 for t in tfs if DMT.passes(t, act, DMT.MODE_ANY)) if act else None
    shown = (passed_all if md == DMT.MODE_ALL else passed_any) if act else None
    return {"keys": list(FILTER_KEYS), "active": list(act), "pool": int(pool or 0),
            "mode": md, "mode_param": FILTER_MODE_PARAM, "mode_all_label": DMT.MODE_ALL_LABEL,
            "passed_all": passed_all, "passed_any": passed_any, "shown": shown,
            "hidden": (len(tfs) - shown) if act else 0, "items": items,
            "line": filter_line(items, passed_all, pool, mode=md, shown=shown) if act else None,
            "note": FILTERS_NOTE_ALL if md == DMT.MODE_ALL else FILTERS_NOTE_ANY,
            "measured": False}


def rank(entry: dict, *, sort: str, active=(), mode=DMT.MODE_ANY,
         include_green: bool = False) -> tuple:
    """(rows in the asked order after the view + the ticked boxes, counts,
    filters block). Rows are the memo's own dicts — READ-ONLY."""
    srt = resolve_sort(sort)
    every = list((entry.get("rows") or {}).values())
    every.sort(key=sort_key(srt))
    view = every if include_green else [r for r in every if is_red(r)]
    act = parse_filters(",".join(active)) if not isinstance(active, str) else parse_filters(active)
    filters = filters_block([r.get("hb_filter") for r in view], act, pool=len(view), mode=mode,
                            qqq=entry.get("qqq") or {})
    kept = [r for r in view if DMT.passes(r.get("hb_filter"), act, mode)]
    counts = {k: 0 for k in COUNT_KEYS}
    counts.update({k: v for k, v in (entry.get("counts") or {}).items() if k in counts})
    counts.update(in_view=len(view), hidden_by_view=len(every) - len(view),
                  hidden_by_filters=len(view) - len(kept))
    return kept, counts, filters


def qqq_available(entry: dict) -> bool:
    """Was the Nasdaq-100 list read for this build? False = every `qqq` is
    served None (unknown), never False (not a member)."""
    return bool(((entry or {}).get("qqq") or {}).get("available"))


def compact_row(r: dict, *, qqq_available: bool, thin: bool = False) -> dict:
    """The A1 row (EVERY name in the view, under the liquidity floor too —
    `thin` True, no chart): no chart, no zone. `qqq` None = the Nasdaq-100
    list was not read. `text` = the card's own stat values (tile_stats), so a
    name reads the same in the table and on its card; `red` = is_red."""
    td = r.get("today") or {}
    st = {s["k"]: s["v"] for s in tile_stats(r)}
    return {"symbol": r["symbol"], "beta": r.get("beta"), "cats": list(r.get("cats") or []),
            "qqq": bool(r.get("qqq")) if qqq_available else None,
            "move_pct": td.get("move_pct"), "state": td.get("state"),
            "swing": r.get("swing"), "sigma_pct": r.get("sigma_pct"),
            "prev_close": td.get("prev_close") or r.get("prev_close"), "basis": td.get("basis"),
            "thin": thin is True, "red": is_red(r),
            "levered": [dict(x) for x in (r.get("levered") or [])],
            "levered_chip": copy.deepcopy(r.get("levered_chip")),
            "text": {"beta": st[STAT_BETA], "today": st[STAT_TODAY], "swing": st[STAT_SWING],
                     "sigma": st[STAT_SIGMA]}}


def table_block() -> dict:
    """`high_beta_board.table` (A1): the served heads and the badge words."""
    return {"columns": [{"key": k, "label": lbl} for k, lbl in TABLE_COLUMNS],
            "cat_labels": dict(CAT_SHORT), "qqq_label": QQQ_ETF}


def served_sorts() -> list:
    return [{"key": SORT_SWING, "label": SWING_SORT_LABEL},
            {"key": SORT_DROP, "label": DROP_SORT_LABEL},
            {"key": SORT_VOL, "label": VOL_SORT_LABEL}]


# ---------------------------------------------------------------------------
# the study verdict (lazy; the literal lives in high_beta_measured)
# ---------------------------------------------------------------------------
def _measured() -> dict:
    try:
        from chart_maps import high_beta_measured as HBM
        m = HBM.load()
        return m if isinstance(m, dict) else dict(MEASURED_DEFAULT)
    except (ImportError, AttributeError):
        return dict(MEASURED_DEFAULT)


def is_measured() -> bool:
    return _measured().get("status") == "measured"


def study_block() -> dict:
    m = _measured()
    prereg = "docs/research/high_beta_2026_10_14_prereg.md"
    script = "backend/scripts/high_beta_study.py"
    if m.get("status") != "measured":
        return {"status": "unmeasured", "text": NOTE_PENDING, "verdict": None,
                "prereg": prereg, "script": script}
    p = m.get("primary") or {}
    red = m.get("spy_red") or {}
    ci = p.get("ci") or [None, None]
    try:
        rci = red.get("ci") or [None, None]
        red_pp = (f"{float(red['contrast_pp']):+.2f} pp, CI [{float(rci[0]):+.2f}, "
                  f"{float(rci[1]):+.2f}]") if red.get("contrast_pp") is not None else "—"
        text = MEASURED_FMT.format(
            run_date=m.get("run_date"), as_of=m.get("as_of"), prereg=m.get("prereg_commit"),
            b15=f"{B15_MIN:.1f}", cut=f"{DOWN_CHIP_PCT:g}", pp=float(p["contrast_pp"]),
            h=int(p.get("horizon") or 0), lo=float(ci[0]), hi=float(ci[1]),
            n=_n(p.get("n_sessions")), words=VERDICT_WORDS.get(p.get("verdict"), "—"),
            red_pp=red_pp, red_words=VERDICT_WORDS.get(red.get("verdict"), "—"),
            mae=float(p.get("mae_mean_pct") or 0.0))
    except (KeyError, TypeError, ValueError, IndexError):
        return {"status": "unmeasured", "text": NOTE_PENDING, "verdict": None,
                "prereg": prereg, "script": script}
    return {"status": "measured", "text": text, "verdict": p.get("verdict"),
            "prereg": prereg, "script": script}


def note_text() -> str:
    return study_block()["text"]


# ---------------------------------------------------------------------------
# words (every number from a constant or a count)
# ---------------------------------------------------------------------------
def session_words(mode: str, session_iso: str, as_of, half_day: bool = False) -> str:
    return D10.session_words(mode, session_iso, as_of, half_day)


def header_text(counts: dict, categories_block: dict, *, mode: str, session_iso: str, as_of,
                half_day: bool = False, charts: int = 0) -> str:
    c = counts or {}
    top = (categories_block or {}).get("top20") or {}
    cut = _f(top.get("cut_beta"))
    cut_txt = f"β ≥ {cut:.2f}" if cut is not None else "none rated"
    return (f"{MARK} {_n(c.get('red'))} red of {_n(c.get('listed'))} High-Beta names · charts "
              f"for the top {_n(charts)} — {_n(c.get('rated'))} rated of {_n(c.get('scanned'))} "
              f"scanned (the full universe + the Nasdaq-100). β ≥ {B15_MIN:.1f}: "
              f"{_n(c.get('b15'))} · β ≥ {B20_MIN:.1f}: {_n(c.get('b20'))} · top {TOP_PCT:g}% "
              f"({cut_txt}): {_n(c.get('top20'))}. {_n(c.get('red'))} of {_n(c.get('read'))} read "
              f"are red, {session_words(mode, session_iso, as_of, half_day)}; "
              f"{_n(c.get('down5'))} down {DOWN_CHIP_PCT:g}%+.")


def categories_line(block: dict, counts: dict) -> str:
    top = (block or {}).get("top20") or {}
    cut = _f(top.get("cut_beta"))
    tie = f" (ties at β {cut:.2f} included)" if cut is not None else ""
    return (f"Each name carries every category it is in. β = cov/var of {BETA_LOOKBACK} daily log "
            f"returns against {BENCH} before this session (sepa/beta.py). Top {TOP_PCT:g}% = the "
            f"{_n(top.get('k'))} highest of {_n(top.get('of'))} rated stocks{tie}. Not rated: "
            f"{_n((counts or {}).get('short_history'))} with under {BETA_LOOKBACK + 1} sessions of "
            "history (no β).")


def qqq_line(qqq: dict, summary: dict, rows: dict) -> str:
    q = qqq if isinstance(qqq, dict) else {}
    if not q.get("available"):
        return (f"The Nasdaq-100 list could not be read ({q.get('error') or 'unknown'}) — no QQQ "
                "badge this build; the QQQ box passes no name.")
    s = summary if isinstance(summary, dict) else {}
    mv = _f(s.get("qqq_move_pct"))
    when = {MODE_LIVE: "today, live", MODE_AFTER: "today's session"}.get(s.get("mode"),
                                                                        "the last session")
    on = [r for r in (rows or {}).values() if r.get("qqq")]
    red = sum(1 for r in on if is_red(r))
    head = (f"QQQ {_m(f'{mv:+.2f}')}% {when}" if mv is not None else f"QQQ not read {when}")
    return (f"{head} · {_n(len(on))} of {_n(q.get('n'))} Nasdaq-100 names are on this list, "
            f"{_n(red)} red.")


def market_line(summary: dict) -> Optional[str]:
    line = RES.market_line(summary)
    return (line + " Over the High-Beta list.") if line else None


def order_line(sort: str) -> str:
    srt = resolve_sort(sort)
    if srt == SORT_DROP:
        return ("Order: today's drop, deepest first; names up or flat follow (smallest move "
                "first); names with no read last.")
    if srt == SORT_VOL:
        return (f"Order: most volatile first — σ, the stdev of the last {SIGMA_BARS} daily "
                "returns; a name with no σ sits last.")
    return ("Order: β × today's drop, largest first, over the red names; names up or flat today "
            "follow (smallest move first); names with no read last.")


def view_line(include_green: bool, counts: dict) -> str:
    c = counts or {}
    if include_green:
        return (f"Every High-Beta name is listed — {_n(c.get('red'))} red, {_n(c.get('up'))} up, "
                f"{_n(c.get('flat'))} flat, the rest not read today.")
    return (f"Red names only — {_n(c.get('hidden_by_view'))} up, flat or not read today are "
            f"hidden; tick “{VIEW_LABEL}” to list them.")


def count_line(counts: dict, *, min_tier_label: str, need_date) -> str:
    c = counts or {}
    text = (f"Showing {_n(c.get('shown'))} charts of {_n(c.get('rows'))} names — "
            f"{_n(c.get('dropped_thin'))} under the liquidity floor ({min_tier_label}), "
            "listed in the table as thin, no chart")
    if int(c.get("no_turnover") or 0):
        text += f", {_n(c.get('no_turnover'))} with no turnover to check"
    text += (f". Not rated: {_n(c.get('etf'))} ETFs, {_n(c.get('delisted'))} delisted, "
             f"{_n(c.get('stale'))} whose cached bars end before {need_date}, "
             f"{_n(c.get('no_bars'))} with no cached bars. Not read today: "
             f"{_n(c.get('no_print'))} no print, {_n(c.get('no_snapshot'))} no snapshot answer "
             f"(asked twice), {_n(c.get('suspect'))} held out (named below — check the chart)")
    if int(c.get("today_stale") or 0):
        text += f", {_n(c.get('today_stale'))} with no closed bar for the session"
    return text + "."


def suspects_block(suspects) -> dict:
    s = [x for x in (suspects or []) if isinstance(x, dict)]
    n = len(s)
    head = (f"{n:,} names held out — today's move may be a data artifact (a split, a bad print, "
            "a decimal shift). A real move can look the same; check the chart.")
    lines = []
    for x in s[:SUSPECT_LINES_MAX]:
        px = _f(x.get("print"))
        pv = _f(x.get("prev_close"))
        lines.append(f"{x['symbol']} — print {px:.2f} vs prior close {pv:.2f}: "
                     f"{x.get('reason') or ''}" if (px is not None and pv is not None)
                     else f"{x['symbol']} — {x.get('reason') or ''}")
    return {"n": n, "head": head, "lines": lines}


def error_note(reason) -> str:
    return ERROR_NOTE_FMT.format(reason=str(reason or "unknown"), mins=int(FAIL_RETRY_SEC // 60))


# ---------------------------------------------------------------------------
# tile pieces (PURE)
# ---------------------------------------------------------------------------
def category_pill(r: dict) -> str:
    bits = [f"{MARK} β {float(r['beta']):.2f}"]
    bits += [CAT_SHORT[k] for k in CAT_KEYS if k in (r.get("cats") or ())]
    if r.get("qqq"):
        bits.append(QQQ_ETF)
    return " · ".join(bits)


def today_text(td: dict) -> str:
    td = td or {}
    st = td.get("state")
    if st == "read":
        return _m(f"{float(td['move_pct']):+.2f}% vs {float(td['prev_close']):.2f}")
    if st == "suspect":
        return f"held out — {td.get('reason') or 'the data cannot be trusted'}"
    if st == "no_snapshot":
        return "no snapshot answer (asked twice) — not read"
    by_mode = RES._TODAY_TEXT_BY_MODE.get((td.get("mode"), st))
    return by_mode or RES._TODAY_TEXT.get(st, "not read")


def tile_badges(r: dict, active=()) -> list:
    """① the category pill (IDENT) ② the today pill (PRICE; absent unread)
    ③ one badge per ticked box the name passes. The board adds the zone."""
    out = [{"text": category_pill(r), "tone": "muted"}]
    lc = r.get("levered_chip")
    if isinstance(lc, dict) and lc.get("text"):
        out.append({"text": str(lc["text"]), "tone": "muted", "levered": True})
    td = r.get("today") or {}
    if td.get("state") == "read":
        mv = float(td["move_pct"])
        if td.get("mode") == MODE_CLOSED:
            text = RES.TODAY_LAST_FMT.format(day=KL._day_mmdd(td.get("day"), weekday=True), move=mv)
        else:
            text = RES.TODAY_PLAIN_FMT.format(move=mv)
        out.append({"text": text, "tone": "warn" if mv < 0 else "good"})
    tf = r.get("hb_filter") or {}
    act = set(active or ())
    out.extend({"text": FILTER_LABELS[k], "tone": "good", "hb_filter": k}
               for k in FILTER_KEYS if k in act and tf.get(k) is True)
    return out


def tile_stats(r: dict) -> list:
    td = r.get("today") or {}
    sw = r.get("swing")
    if td.get("state") != "read":
        sw_txt = "—"
    elif float(td.get("move_pct") or 0.0) >= 0:
        sw_txt = "— (up or flat today)"
    else:
        sw_txt = f"{float(sw):.2f}"
    sg = _f(r.get("sigma_pct"))
    out = [{"k": STAT_BETA, "v": f"{float(r['beta']):.2f}"},
           {"k": STAT_TODAY, "v": today_text(td)},
           {"k": STAT_SWING, "v": sw_txt},
           {"k": STAT_SIGMA, "v": f"{sg:.2f}%" if sg is not None else "—"}]
    lv = LE.stat_value(r.get("levered"))
    if lv:
        out.append({"k": LE.STAT_KEY, "v": lv})
    return out


def tile_marker(r: dict) -> Optional[dict]:
    return None


def why_text(r: dict, zone_text: str) -> str:
    td = r.get("today") or {}
    if td.get("state") == "read":
        today = _m(f"today {float(td['move_pct']):+.2f}%")
        sw = r.get("swing")
        tail = f" · β × drop {float(sw):.2f}" if (sw and float(td["move_pct"]) < 0) else ""
    else:
        today, tail = "today not read", ""
    return f"{MARK} β {float(r['beta']):.2f} · {today}{tail} · " + str(zone_text or "")


def tile_block(r: dict, *, qqq_available: bool) -> dict:
    """The served `tile.high_beta` (the board adds `zone`). `qqq` None = the
    Nasdaq-100 list was not read (§3.3 true|false|null)."""
    return {"beta": r.get("beta"), "cats": list(r.get("cats") or []),
            "qqq": bool(r.get("qqq")) if qqq_available else None,
            "sigma_pct": r.get("sigma_pct"),
            "swing": r.get("swing"), "today": dict(r.get("today") or {}),
            "adv50": r.get("adv50"),
            "levered": [dict(x) for x in (r.get("levered") or [])],
            "levered_chip": copy.deepcopy(r.get("levered_chip"))}


def last_print(r: dict) -> Optional[float]:
    td = r.get("today") or {}
    return _f(td.get("print")) or _f(r.get("prev_close"))


# ---------------------------------------------------------------------------
# envelopes
# ---------------------------------------------------------------------------
def _block(state: str, *, mode: str, session_iso: str, sort: str, header: str,
           entry: Optional[dict] = None, counts: Optional[dict] = None, stale: bool = False,
           min_tier_label: Optional[str] = None, filters: Optional[dict] = None,
           include_green: bool = False) -> dict:
    ready = state == "ready" and entry is not None
    need = KL.prev_market_day(date.fromisoformat(session_iso)).isoformat()
    e = entry or {}
    study = study_block()
    return {"state": state, "mode": mode, "session": session_iso,
            "as_of": e.get("as_of") if ready else None,
            "built_at": e.get("built_at") if ready else None,
            "base_built_at": e.get("base_built_at") if ready else None,
            "stale": bool(stale) if ready else False,
            "measured": study["status"] == "measured",
            "refresh_sec": LIVE_TTL_SEC if mode == MODE_LIVE else None,
            "sort": resolve_sort(sort), "header": header,
            "market_line": market_line(e.get("summary")) if ready else None,
            "qqq_line": qqq_line(e.get("qqq"), e.get("summary"), e.get("rows")) if ready else None,
            "order_line": order_line(sort),
            "view_line": view_line(include_green, counts) if ready else None,
            "count_line": (count_line(counts, min_tier_label=min_tier_label or "—",
                                      need_date=need) if ready else None),
            "categories_line": categories_line(e.get("categories"), counts) if ready else None,
            "categories": dict(e.get("categories") or {}) if ready else None,
            "qqq": ({**(e.get("qqq") or {}),
                     "note": filter_note("qqq", e.get("qqq") or {})} if ready else None),
            "filters": filters if ready else None,
            "view": {"param": VIEW_PARAM, "on": bool(include_green), "label": VIEW_LABEL},
            "table": table_block() if ready else None,
            "levered": dict(e.get("levered") or {}) if ready else None,
            "note": study["text"], "study": study,
            "counts": dict(counts) if ready else None,
            "suspects": suspects_block(e.get("suspects")) if ready else None}


def ready_block(counts: dict, *, entry: dict, sort: str, min_tier_label: str, filters: dict,
                include_green: bool = False, stale: bool = False, charts: int = 0) -> dict:
    return _block("ready", mode=str(entry.get("mode")), session_iso=str(entry["session"]),
                  sort=sort, header=header_text(counts, entry.get("categories"),
                                                mode=entry.get("mode"),
                                                session_iso=entry["session"],
                                                as_of=entry.get("as_of"),
                                                half_day=bool(entry.get("half_day")),
                                                charts=charts),
                  entry=entry, counts=counts, stale=stale, min_tier_label=min_tier_label,
                  filters=filters, include_green=include_green)


def warming_block(*, now: datetime, sort: str, include_green: bool = False) -> dict:
    mode, session, _t, _h = mode_for(now)
    return _block("warming", mode=mode, session_iso=session.isoformat(), sort=sort,
                  header=WARMING_NOTE, include_green=include_green)


def error_block(reason, *, now: datetime, sort: str, include_green: bool = False) -> dict:
    mode, session, _t, _h = mode_for(now)
    return _block("error", mode=mode, session_iso=session.isoformat(), sort=sort,
                  header=error_note(reason), include_green=include_green)
