"""🥇 Luk's daily facts (spec §3.5) — the closed daily bars behind his three screens, the pullback's daily 9 EMA, the
inside day, the tier and the 🏁 grade's 9-EMA exit.

THE TRUST RULE (spec C2, HIS CALL #27; REFIX 2026-11-01). The house price cache (`sepa.prices`, doc `{symbol,
cached_at, bars}`) holds today's PARTIAL bar under a 20 h TTL — `load_prices` writes it intraday, and the house
reader's own docstring in `sepa.prices` names the trap. Judging the doc's `cached_at` stamp does NOT close it:
`patch_latest_closes` (`$push` the newest bar + `$set cached_at=now`, called by the intraday SEPA scanner and
patterns/scan.py) RE-STAMPS a doc whose earlier rows it never rewrites — a bar for `d` written half-session at 15:00 ET
on `d` carries a `cached_at` of `d+1` after the next scan. So NO house doc is a close proof. A closed day reaches Luk
ONLY through Luk's OWN post-close fetch: `load_prices(sym, "1y", force=True)` made at or after `d` ET_RTH_CLOSE
(16:00 ET) + LC.LUK_DAILY_TRUST_AFTER_SEC (= GC.BAR_SETTLE_SEC, the house "closed 30 s after its right label" rule
applied to the daily bar), its facts stored in luk_daily (`source` = SOURCE_FETCH, `daily_cached_at` = the fetch
time) — ≈ 1 fetch per name per session (HIS CALL: the cost). The QQQ / IWM state words come from the SAME own-fetch
rule, ONCE per session (`index_state`: LC.LUK_INDEX_SYMBOLS fetches on the session's first pass, the words kept in
luk_state under LC.LUK_STATE_INDEX and served to every later pass of that session). Luk never reads a closed day — nor
an index word — through `prices._mongo_get`, `load_prices(force=False)`, `prices.closed_daily_frame` or
`prices.cached_frame_meta`.

Formulas (HIS CALL #10 — TradingView field formulas built here; "10D" is his): EMAs = `orderflow.signals.ema`
(the one definition) at the last closed day, None under `n` bars; ADR = `sepa.adr.adr_pct` over LC.LUK_ADR_SESSIONS;
10-day average volume = mean of the last LC.LUK_AVG_VOL_SESSIONS volumes; price×volume = the last close × its volume;
1-week price×volume = the sum over LC.LUK_PX_VOL_1W_SESSIONS; 1-week volatility = the mean of (high − low) / close × 100
over LC.LUK_VOL_1W_SESSIONS; 1-month % = the close vs the close LC.LUK_PERF_1M_SESSIONS sessions earlier. A window with
fewer bars than it names is None (the `sepa.adr` rule) — a None fact fails its screen criterion, never a guess.
Inside day = strict inequalities (HIS CALL #17).
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from . import constants as LC
from . import tiers as TI

log = logging.getLogger("chart_maps.luk.daily")

ET = ZoneInfo("America/New_York")
FACT_KEYS = ("close", "ema9", "ema21", "ema50", "ema150", "adr20_pct", "avg_vol_10d", "px_vol", "px_vol_1w",
             "vol_1w_pct", "perf_1m_pct", "prev_high", "prev_low", "prev2_high", "prev2_low", "inside_day", "tier",
             "n_bars", "as_of")
# the daily EMA spans are the spec's FACT_KEYS names (ema9 / ema21 / ema50 / ema150 — E8's confluence set); no second
# copy of the numbers. 9 = LC.LUK_PULLBACK_DAILY_EMA, (21, 50) = LC.LUK_POTENT_EMAS (a test pins both)
EMA_SPANS = tuple(int(k[3:]) for k in FACT_KEYS if k.startswith("ema"))
PENDING_TEXT = "daily facts pending — Luk's own post-close fetch not made yet"
SOURCE_FETCH = "fetch"                      # the ONLY luk_daily source a later pass trusts (Luk's own post-close fetch)


class Pending(dict):
    """The facts slot of a name whose daily facts were DEFERRED by the trust rule: Luk's own post-close fetch has NOT
    been made yet for it (the per-pass cap LC.LUK_DAILY_MAX_NEW_PER_PASS or the warm budget spent, a dry run, or `now`
    before the settle) — never a statement about the house cache. FALSY — every
    `if facts` reads it as "no facts" (the pass counts it in not_screened_n) — while `screens.row_of` tells it from
    an absent frame (None) and serves PENDING_TEXT instead of "no daily bars cached"."""

    def __bool__(self) -> bool:
        return False


def pending() -> Pending:
    return Pending(pending=True, pending_text=PENDING_TEXT)


def is_pending(facts) -> bool:
    return isinstance(facts, Pending)


# ── frames ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _as_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


def _dates(df) -> pd.DatetimeIndex:
    """The frame's index as naive ET midnights (an aware index is converted to ET first)."""
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert(ET).tz_localize(None)
    return idx.normalize()


def closed_before(df, session):
    """Rows dated strictly BEFORE `session` (ET dates) — today's bar, partial or not, never reaches a fact."""
    if df is None or len(df) == 0:
        return df
    return df[_dates(df) < pd.Timestamp(_as_date(session))]


def _through(df, d):
    """Rows dated on or before `d`."""
    if df is None or len(df) == 0:
        return df
    return df[_dates(df) <= pd.Timestamp(_as_date(d))]


def _holds(df, d) -> bool:
    return df is not None and len(df) > 0 and pd.Timestamp(_as_date(d)) in set(_dates(df))


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def facts_from_frame(df) -> Optional[dict]:
    """The FACT_KEYS of the LAST row of a CLOSED daily frame (the caller cut it); None on no rows."""
    if df is None or len(df) == 0:
        return None
    from orderflow.signals import ema
    from sepa.adr import adr_pct
    df = df.sort_index()
    close, vol = df["close"].astype(float), df["volume"].astype(float)
    high, low = df["high"].astype(float), df["low"].astype(float)
    n = len(df)
    out = {"close": _f(close.iloc[-1])}
    for span in EMA_SPANS:
        out[f"ema{span}"] = _f(ema(close, span).iloc[-1]) if n >= span else None
    out["adr20_pct"] = adr_pct(df, LC.LUK_ADR_SESSIONS)
    k = LC.LUK_AVG_VOL_SESSIONS
    out["avg_vol_10d"] = _f(vol.iloc[-k:].mean()) if n >= k else None
    out["px_vol"] = _f(close.iloc[-1] * vol.iloc[-1])
    k = LC.LUK_PX_VOL_1W_SESSIONS
    out["px_vol_1w"] = _f((close * vol).iloc[-k:].sum()) if n >= k else None
    k = LC.LUK_VOL_1W_SESSIONS
    rng = ((high - low) / close * 100).iloc[-k:]
    out["vol_1w_pct"] = _f(rng.mean()) if n >= k and (close.iloc[-k:] > 0).all() else None
    k = LC.LUK_PERF_1M_SESSIONS
    base = close.iloc[-1 - k] if n >= k + 1 else None
    out["perf_1m_pct"] = _f((close.iloc[-1] / base - 1) * 100) if base else None
    out["prev_high"], out["prev_low"] = _f(high.iloc[-1]), _f(low.iloc[-1])
    if n >= 2:
        out["prev2_high"], out["prev2_low"] = _f(high.iloc[-2]), _f(low.iloc[-2])
        out["inside_day"] = bool(out["prev_high"] < out["prev2_high"] and out["prev_low"] > out["prev2_low"])
    else:
        out["prev2_high"] = out["prev2_low"] = out["inside_day"] = None
    out["tier"] = TI.tier_of(out.get("ema9"), out.get("ema21"), out.get("ema50"))
    out["n_bars"] = n
    out["as_of"] = _dates(df)[-1].date().isoformat()
    return {k: out.get(k) for k in FACT_KEYS}


# ── the trust rule ─────────────────────────────────────────────────────────────────────────────────────────────
def close_epoch(d) -> float:
    """Epoch seconds of `d` at ET_RTH_CLOSE (16:00 ET, DST-aware)."""
    from daytrading.data import ET_RTH_CLOSE
    dd = _as_date(d)
    return datetime(dd.year, dd.month, dd.day, ET_RTH_CLOSE.hour, ET_RTH_CLOSE.minute, tzinfo=ET).timestamp()


def trusted_through(cached_at, d) -> bool:
    """PURE — a cache doc written at `cached_at` (epoch s) holds a CLOSED bar for `d`: cached_at ≥ `d` 16:00 ET +
    LC.LUK_DAILY_TRUST_AFTER_SEC. None / junk → False."""
    c = _f(cached_at)
    if c is None or isinstance(cached_at, bool):
        return False
    return c >= close_epoch(d) + float(LC.LUK_DAILY_TRUST_AFTER_SEC)


def _epoch(now) -> float:
    if now is None:
        return time.time()
    if isinstance(now, (int, float)) and not isinstance(now, bool):
        return float(now)
    ts = pd.Timestamp(now)
    if ts.tzinfo is None:
        ts = ts.tz_localize(timezone.utc)
    return ts.timestamp()


def _prev_market_day(session) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(_as_date(session))


def cached_frame(sym: str, session, *, now=None):
    """ALWAYS None (REFIX 2026-11-01): no house cache doc is a close proof — `patch_latest_closes` re-stamps
    `cached_at` without rewriting the rows under it, so a stamp after `d`'s close says nothing about the bar dated
    `d`. Reads nothing, never fetches, never writes. Kept so `run.Deps.cached` resolves; `warm` never calls it."""
    return None


def fetch_frame(sym: str, session):
    """`prices.load_prices(sym, "1y", force=True)` cut to rows before `session` (force: an untrusted row inside the
    TTL would otherwise be served again; the house cache receives the fresh fetch, as load_prices always does)."""
    from sepa import prices
    df = prices.load_prices(sym, "1y", force=True)
    return closed_before(df, session) if df is not None and len(df) else None


def _daily_docs(store, session) -> dict:
    """{SYM: luk_daily doc} of the session — ONE find on luk_daily ({} on a fault or no handle)."""
    from chart_maps.gajjala import store as GS
    out: dict = {}
    iso = _as_date(session).isoformat()
    try:
        c = store.coll(GS.DAILY)
        if c is not None:
            for d in c.find({"date": iso}):
                if isinstance(d, dict) and d.get("symbol"):
                    out[str(d["symbol"]).upper()] = d
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk.daily: luk_daily read failed: %s", exc)
    return out


def _own_doc_facts(doc, prev) -> Optional[dict]:
    """The facts of a luk_daily doc ONLY when Luk's own post-close fetch wrote it: source == SOURCE_FETCH, its
    `daily_cached_at` (the fetch time) trusted through `prev`, and its facts dated `prev`. Anything else → None."""
    if not isinstance(doc, dict) or not isinstance(doc.get("facts"), dict):
        return None
    if doc.get("source") != SOURCE_FETCH or not trusted_through(doc.get("daily_cached_at"), prev):
        return None
    if str(doc["facts"].get("as_of") or "") != prev.isoformat():
        return None
    return doc["facts"]


def warm(store, session, priority: list, *, now, cap_new: int, budget_sec: float, clock: Callable = time.monotonic,
         cached: Optional[Callable] = None, fetch: Optional[Callable] = fetch_frame) -> dict:
    """The session's daily facts for `priority` (the snapshot |change| order). Per name, in order:
      1. a luk_daily doc of (session, SYM) written by Luk's OWN post-close fetch (`_own_doc_facts`) → `doc_hits`
      2. else `untrusted` += 1 (no house doc is a close proof — REFIX 2026-11-01); with `fetch`, fewer than `cap_new`
         fetches made and `now` past the last market day's close + the settle → `fetched` += 1, the frame is used
         when it holds the last market day → `computed` + ONE luk_daily doc (source SOURCE_FETCH, daily_cached_at =
         `now`); a fetch that brings no such frame → `no_frame`
      3. else Luk's own post-close fetch is NOT made for the name this pass (cap spent, budget spent, no fetch in a
         dry run, or `now` before the settle) → `deferred`: the facts slot is `Pending` (PENDING_TEXT; the row is
         KEPT on the screens and counted not screened).
    `cached` is accepted for the caller's signature (`run.Deps.cached`) and NEVER called: the house cache is never
    trusted. `budget_sec` (on `clock`) bounds the loop: every name after it runs out is deferred. Never raises per
    name."""
    out = {"facts": {}, "doc_hits": 0, "computed": 0, "fetched": 0, "deferred": 0, "untrusted": 0, "no_frame": 0}
    names = [str(s).upper() for s in dict.fromkeys(priority or []) if s]
    docs = _daily_docs(store, session)
    t0 = clock()
    prev = _prev_market_day(session)
    now_epoch = _epoch(now)
    settled = trusted_through(now_epoch, prev)
    for sym in names:
        own = _own_doc_facts(docs.get(sym), prev)
        if own is not None:
            out["facts"][sym] = own
            out["doc_hits"] += 1
            continue
        if clock() - t0 > float(budget_sec):
            out["facts"][sym] = pending()
            out["deferred"] += 1
            continue
        out["untrusted"] += 1
        if fetch is None or not settled or out["fetched"] >= int(cap_new):
            out["facts"][sym] = pending()
            out["deferred"] += 1
            continue
        out["fetched"] += 1
        try:
            df = fetch(sym, session)
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk.daily: fetch failed for %s: %s", sym, type(exc).__name__)
            df = None
        df = closed_before(df, session) if df is not None and len(df) else None
        if df is None or not _holds(df, prev):
            out["no_frame"] += 1
            continue
        source, stamp = SOURCE_FETCH, now_epoch
        facts = facts_from_frame(df)
        if not facts:
            out["no_frame"] += 1
            continue
        out["facts"][sym] = facts
        out["computed"] += 1
        try:
            store.upsert_daily(session, sym, {"facts": facts, "daily_cached_at": stamp, "source": source}, now=now)
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk.daily: luk_daily write failed for %s: %s", sym, type(exc).__name__)
    return out


# ── the 🏁 grade path ──────────────────────────────────────────────────────────────────────────────────────────
def _close_facts(df, d, stamp) -> Optional[dict]:
    from orderflow.signals import ema
    df = _through(df, d)
    if df is None or not _holds(df, d):
        return None
    df = df.sort_index()
    close = df["close"].astype(float)
    span = LC.LUK_PULLBACK_DAILY_EMA
    return {"close": _f(close.iloc[-1]), "ema9_close": _f(ema(close, span).iloc[-1]) if len(close) >= span else None,
            "n_bars": len(df), "daily_cached_at": stamp}


def closed_through(sym: str, d, *, now, fetch: Callable, loads: dict) -> Optional[dict]:
    """{close, ema9_close, n_bars, daily_cached_at} of session `d` for the grader (spec C2, C9; REFIX 2026-11-01):
    ONLY Luk's own post-close fetch — no house cache doc is read (its `cached_at` is re-stamped by
    `patch_latest_closes`, so it proves nothing about the bar dated `d`). ONE counted fetch (`loads["daily"]` += 1),
    made only when `now` is past `d`'s close + the settle, refused (None) when loads["daily"] + loads["minute"]
    ≥ LC.LUK_GRADE_MAX_LOADS; the frame must hold `d`; else None ("not graded yet", retried next pass — never a
    half-session close). `daily_cached_at` = the fetch time. `fetch(sym)` → a daily frame."""
    now_epoch = _epoch(now)
    if not trusted_through(now_epoch, d):                       # `d` has not closed + settled: nothing to fetch yet
        return None
    loads.setdefault("daily", 0)
    loads.setdefault("minute", 0)
    if loads["daily"] + loads["minute"] >= int(LC.LUK_GRADE_MAX_LOADS):
        return None
    loads["daily"] += 1
    try:
        df = fetch(sym)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk.daily: grade fetch failed for %s: %s", sym, type(exc).__name__)
        return None
    if df is None or len(df) == 0:
        return None
    return _close_facts(df, d, now_epoch)


# ── market state ───────────────────────────────────────────────────────────────────────────────────────────────
def default_index_loader(session) -> Callable:
    """The index words' loader: Luk's OWN fetch, `fetch_frame(sym, session)` (= `prices.load_prices(sym, "1y",
    force=True)` cut to rows before `session`) — the trust rule of the module docstring, never a house cache read."""
    return lambda sym: fetch_frame(sym, session)


def _stored_index(store, iso: str) -> Optional[dict]:
    """The luk_state LC.LUK_STATE_INDEX words when they belong to session `iso` (else None; a read fault → None)."""
    try:
        doc = store.get_state(LC.LUK_STATE_INDEX) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk.daily: index state read failed: %s", type(exc).__name__)
        return None
    states = doc.get("states") if isinstance(doc, dict) else None
    if doc.get("session") != iso or not isinstance(states, dict):
        return None
    if set(states) != set(LC.LUK_INDEX_SYMBOLS):
        return None
    return {sym: states[sym] for sym in LC.LUK_INDEX_SYMBOLS}


def index_state(session, *, loader: Optional[Callable] = None, store=None, now=None) -> dict:
    """{sym: {"ema9", "ema21", "close", "dist_9_pct"} | None} for LC.LUK_INDEX_SYMBOLS, cut to rows before `session`.
    A state word, never a gate (market_state.py). ONCE PER SESSION: with `store`, luk_state LC.LUK_STATE_INDEX holding
    this session's words → served with NO load; else every symbol goes through `loader(sym)` (default
    `default_index_loader` — Luk's own fetch) and, with `store`, the words are written back as {session, states, at}
    ONLY when every symbol produced a word (a failed or short load is retried by the next pass, never kept for the
    day). A dry store records that write and lands nothing."""
    iso = _as_date(session).isoformat()
    if store is not None:
        kept = _stored_index(store, iso)
        if kept is not None:
            return kept
    if loader is None:
        loader = default_index_loader(session)
    from orderflow.signals import ema
    fast, slow = LC.LUK_INDEX_EMAS
    out: dict = {}
    for sym in LC.LUK_INDEX_SYMBOLS:
        try:
            df = closed_before(loader(sym), session)
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk.daily: index %s failed: %s", sym, type(exc).__name__)
            df = None
        if df is None or len(df) < slow:
            out[sym] = None
            continue
        close = df.sort_index()["close"].astype(float)
        e9, e21, c = _f(ema(close, fast).iloc[-1]), _f(ema(close, slow).iloc[-1]), _f(close.iloc[-1])
        out[sym] = {"ema9": e9, "ema21": e21, "close": c,
                    "dist_9_pct": ((c / e9 - 1) * 100) if (c is not None and e9) else None}
    if store is not None and all(out.get(sym) is not None for sym in LC.LUK_INDEX_SYMBOLS):
        try:
            store.set_state(LC.LUK_STATE_INDEX, {"session": iso, "states": out,
                                                 "at": datetime.fromtimestamp(_epoch(now), timezone.utc)})
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk.daily: index state write failed: %s", type(exc).__name__)
    return out
