"""🔻 Down 10%+ intraday tab on Chart Maps (Ajay 2026-10-03).

The ask, verbatim: "I would like to know about stocks that falled intraday
more than 10% new tab please."

THE LIST. Every universe stock whose session LOW sits `THRESHOLD_PCT` or more
under the PRIOR session's close. Two states, both listed:
  down       — the print is still `THRESHOLD_PCT` or more under the prior close;
  reclaimed  — the low hit it, the print has come back above it.
The prior close is the cached daily frame's last closed bar before the session
(`zone_store.drop_today`); a name whose cached bars end before the prior market
day is counted `stale`, never read off a guess.

WHICH SESSION, by the tape clock (`zone_edge.session_state`):
  rth         -> LIVE: today's Massive snapshot day bar (one bulk call over the
                 universe, fanned out, off the request path);
  afterhours  -> today's snapshot day bar, the regular session over (its
                 `close` is the 16:00 close — probe 2026-10-05: IART 12.68 =
                 the cached close while the last after-hours trade was 12.89);
  premarket / closed -> the LAST CLOSED session off the cached daily frames
                 (closed bars only — the 🔑 / 📉 rule).
A snapshot row is read only when its own minute stamp is dated the session:
overnight the snapshot still carries the last session's bar under TODAY's date
(no `day.t`), so `bulk_snapshot`'s `date` is never trusted here.

HELD OUT, COUNTED, NAMED. ETFs and delisted fates (counted only when they WOULD
have been listed); a low or print the price layer's own guard calls impossible
(`prices._is_scale_glitch`); a live prior close that disagrees with the cached
one by more than `PREV_CLOSE_TOL_PCT` (a split or a bad print); a split Massive
lists as executed on the session (`fetch_splits_strict` — Massive
/v3/reference/splits, read once per listed name per session; unlike
`portfolio.corporate_actions.fetch_splits` it RAISES on a non-200, so an
outage is counted `split_unchecked`, never read as "no split"). Named under the grid — a real collapse can
look like any of them; check the chart.

VOLUME vs normal is `momentum_burst.rvol_leg` — today's shares against the 50
closed sessions before it, projected to a full session on the intraday curve
in RTH once the projection start has passed. 💥 is `fallen_catalysts` for a
one-session drop: what this app has on file from the session before through
the session, and the sector ETF / theme median / RSP that session — possible,
never proof.

THE MEMO. A background thread builds the read, keyed (state, session,
universe), served stale-while-revalidate. `LIVE_TTL_SEC` / `CLOSED_TTL_SEC`
are cache freshness, never rules. The per-session base (prior close, 50-day
averages) is memoised separately for `BASE_TTL_SEC`. WRITES NOTHING.

UNMEASURED: no study in this app measures what a stock that fell
`THRESHOLD_PCT` intraday does next, reclaimed or not. Display only — nothing
here gates a scan, pushes a phone, sizes a position or enters a lane.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from datetime import time as dtime
from typing import Optional

from chart_maps import fallen_catalysts as FC
from chart_maps import key_levels_tab as KLT
from sepa import prices
from supply_demand import key_levels as KL
from supply_demand import momentum_burst as MB

log = logging.getLogger("chart_maps.drop10_tab")

MARK = "\U0001F53B"                      # 🔻 (no VS16; FE literal must match)
TAB_KEY = "drop10"
MEASURED = False
THRESHOLD_PCT = 10.0                     # HIS number: "falled intraday more than 10%" (listed at >=)
INCLUDE_ETFS = False                     # "stocks"
GLITCH_RATIO = prices._SCALE_GLITCH_RATIO  # imported — the price layer's own guard
PREV_CLOSE_TOL_PCT = 1.0                 # data guard: live vs cached prior close (NOT a rule)
LIVE_TTL_SEC = 60                        # cache freshness in RTH, NOT a rule
CLOSED_TTL_SEC = 30 * 60                 # cache freshness outside RTH, NOT a rule
BASE_TTL_SEC = 60 * 60                   # the per-session base, NOT a rule
FAIL_RETRY_SEC = 2 * 60                  # retry cadence, NOT a rule
SPLIT_WORKERS = 8                        # parallel split reads (listed names only)
STATE_DOWN = "down"
STATE_RECLAIMED = "reclaimed"
MODE_LIVE = "live"
MODE_AFTER = "after_close"
MODE_CLOSED = "closed"
ZE_CLOSE = dtime(16, 0)                  # the regular close the words print (a half day: MB.HALF_DAY_CLOSE_ET)
SORT_NOW = "drop10_now"
SORT_RECLAIM = "drop10_reclaim"
SORT_RVOL = "drop10_rvol"
TAB_SORTS = (SORT_NOW, SORT_RECLAIM, SORT_RVOL)
DEFAULT_SORT = "default"
DEFAULT_SORT_LABEL = f"{MARK} Deepest at the low first"
NOW_SORT_LABEL = "\U0001F4C9 Deepest now first"                    # 📉
RECLAIM_SORT_LABEL = "\U0001F504 Most reclaimed off the low first"  # 🔄
RVOL_SORT_LABEL = "\U0001F4CA Volume vs normal first"              # 📊
TAB_LABEL = f"{MARK} Down {THRESHOLD_PCT:g}%+ today"                # == TAB_META.drop10.label (contract)
COUNT_KEYS = ("scanned", "no_bars", "stale", "no_print", "no_snapshot", "under_threshold",
              "delisted", "etf", "data_suspect", "listed", "down", "reclaimed",
              "split_unchecked")
SUSPECT_LINES_MAX = 40                   # display cap on the named list (count is always whole)

_MINUS = "−"

_memo: dict = {}                # (mode, session_iso, ukey) -> entry
_base_memo: dict = {}           # (session_iso, ukey) -> base
_splits_memo: dict = {}         # (sym, session_iso) -> list | None (None = read failed)
_warming: set = set()
_failures: dict = {}            # key -> (ts, reason)
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# served words (constants)
# ---------------------------------------------------------------------------
NOTE = (f"{MARK} UNMEASURED — no study in this app says what a stock that fell "
        f"{THRESHOLD_PCT:g}% or more under its prior close does next, reclaimed or not. "
        "The order is a distance, not a ranking of setups; nothing here gates a scan, "
        "pushes a phone, sizes a position or enters a lane. "
        f"{FC.HIT_MARK} items are what this app has on file from the session before through "
        "this one — possible, never proof of cause. Not advice.")
WARMING_NOTE = (f"{MARK} Reading every name's session low against its prior close — the "
                "charts appear here as soon as it lands; you don't need to refresh.")
EMPTY_NOTE = (f"{MARK} No stock's session low sits {THRESHOLD_PCT:g}% or more under its prior "
              "close — the line above says what was not listed.")
ERROR_NOTE_FMT = (f"{MARK} The Down {{threshold}}%+ list could not be built ({{reason}}). It is "
                  "retried every {mins} minutes — this is not a warming state.")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    return KL._f(v)


def _pos(v) -> Optional[float]:
    x = _f(v)
    return x if (x is not None and x > 0) else None


def _m(s: str) -> str:
    return s.replace("-", _MINUS)


def _n(x) -> str:
    return f"{int(x or 0):,}"


def _pct(a, b) -> Optional[float]:
    """(a / b - 1) * 100 at 2 dp, None unless both are positive."""
    a, b = _pos(a), _pos(b)
    if a is None or b is None:
        return None
    return round((a / b - 1.0) * 100.0, 2)


def _safe_reason(exc: BaseException) -> str:
    s = str(exc)
    if not s or "api_key" in s or "apikey" in s.lower() or "token" in s.lower():
        return type(exc).__name__
    return s[:200]


def _ukey(universe) -> str:
    return KLT._ukey(universe)


def _et_day_of_ms(ms) -> Optional[str]:
    x = _f(ms)
    if x is None or x <= 0:
        return None
    if x > 1e15:                       # nanoseconds (lastTrade.t)
        x = x / 1e6
    try:
        return datetime.fromtimestamp(x / 1000.0, tz=KL.ET).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# which session (PURE but for the clock)
# ---------------------------------------------------------------------------
def mode_for(now: datetime) -> tuple:
    """(mode, session date, tape session for the RVOL leg, half_day)."""
    from supply_demand import zone_edge as ZE
    et = now.astimezone(KL.ET) if now.tzinfo is not None else now
    tape, half = MB.burst_session(ZE.session_state(et), et)
    if tape == "rth":
        return MODE_LIVE, et.date(), "rth", half
    if tape == "afterhours":
        return MODE_AFTER, et.date(), "afterhours", half
    return MODE_CLOSED, KL.prev_market_day(KL.levels_session(et)), "closed", False


# ---------------------------------------------------------------------------
# the per-name reads (PURE)
# ---------------------------------------------------------------------------
def base_read(df, session: date) -> Optional[dict]:
    """The cached-frame half: the prior close (last closed bar BEFORE the
    session), the 50-bar dollar volume and share volume before the session,
    and the session's own closed bar when the frame holds one. None = no
    usable bars before the session."""
    from supply_demand import quick_bounce as QB
    from supply_demand import zone_store
    if df is None or len(df) == 0:
        return None
    past = zone_store.drop_today(df, session)
    if past is None or len(past) == 0:
        return None
    idx = KL._norm_index(past)
    prev = _pos(past["close"].iloc[-1])
    if prev is None:
        return None
    bar = None
    try:
        nidx = KL._norm_index(df)
        iso = session.isoformat()
        hits = [i for i, t in enumerate(nidx) if t.date().isoformat() == iso]
        if hits:
            row = df.iloc[hits[-1]]
            bar = {k: _f(row.get(k)) for k in ("open", "high", "low", "close", "volume")}
    except Exception:                                           # noqa: BLE001
        bar = None
    return {"prev_close": round(prev, 4), "prev_date": idx[-1].date().isoformat(),
            "adv50": QB.avg_dollar_vol(past),
            "avg_vol50": MB.avg_volume_before(df, session.isoformat()),
            "n_bars": int(len(past)), "bar": bar}


def day_from_snapshot(raw: Optional[dict], session: date) -> Optional[dict]:
    """The snapshot day bar as {open, high, low, last, volume, prev_close,
    as_of_ms} — only when its own minute (else last-trade) stamp is dated the
    session and open / high / low / close / prior close are all positive."""
    raw = raw if isinstance(raw, dict) else {}
    day = _et_day_of_ms(raw.get("min_t_ms")) or _et_day_of_ms(raw.get("last_trade_ts_ms"))
    if day != session.isoformat():
        return None
    o, h, lo, c = (_pos(raw.get(k)) for k in ("open", "high", "low", "close"))
    pv = _pos(raw.get("prev_day_close"))
    if None in (o, h, lo, c, pv):
        return None
    ms = _f(raw.get("min_t_ms"))
    return {"open": o, "high": h, "low": lo, "last": c, "volume": _f(raw.get("volume")),
            "prev_close": pv, "as_of_ms": int(ms) if ms else None}


def day_from_bar(base: Optional[dict]) -> Optional[dict]:
    """The closed session bar off the cached frame, the same shape."""
    bar = (base or {}).get("bar") or {}
    o, h, lo, c = (_pos(bar.get(k)) for k in ("open", "high", "low", "close"))
    if None in (o, h, lo, c):
        return None
    return {"open": o, "high": h, "low": lo, "last": c, "volume": _f(bar.get("volume")),
            "prev_close": (base or {}).get("prev_close"), "as_of_ms": None}


def rvol_read(day: dict, base: dict, *, tape: str, frac, half_day: bool) -> dict:
    """Volume vs normal off `momentum_burst.rvol_leg`. That leg is a GATE: once
    the volume so far passes its bar it returns the so-far multiple and drops
    the projection. Here the number is a SORT key, so the full-session
    projection is used whenever one exists (critic 2026-10-05: 2.0M so far at
    11:00 read 2.00× while 1.4M read 4.85× projected — the order inverted)."""
    leg = MB.rvol_leg((day or {}).get("volume"), (base or {}).get("avg_vol50"), tape, frac,
                      half_day=half_day)
    rvol, basis = leg.get("rvol"), leg.get("basis")
    if leg.get("projected") is not None:
        rvol, basis = leg.get("projected"), "projected"
    return {"rvol": rvol, "basis": basis, "actual": leg.get("actual"),
            "projected": leg.get("projected"), "session_pct": leg.get("session_pct"),
            "code": leg.get("code")}


def classify(sym: str, base: Optional[dict], day: Optional[dict], *, session: date,
             mode: str, etf_set, is_delisted=None) -> tuple:
    """(status, row). First match: no_bars -> stale -> no_print ->
    under_threshold -> delisted -> etf -> data_suspect -> listed.

    A delisted name or an ETF is counted as such only when its low WOULD have
    listed it (the 📉 critic rule) — never every ETF in the universe."""
    sym = str(sym or "").upper()
    if base is None:
        return "no_bars", None
    if base.get("prev_date") != KL.prev_market_day(session).isoformat():
        return "stale", None
    if day is None:
        return ("stale" if mode == MODE_CLOSED else "no_print"), None
    prev = base["prev_close"]
    low_pct = _pct(day["low"], prev)
    now_pct = _pct(day["last"], prev)
    if low_pct is None or now_pct is None:
        return "no_print", None
    if low_pct > -THRESHOLD_PCT:
        return "under_threshold", None
    if is_delisted is None:
        from sepa import symbols
        is_delisted = symbols.is_delisted
    if is_delisted(sym):
        return "delisted", None
    if not INCLUDE_ETFS and sym in (etf_set or ()):
        return "etf", None
    row = {"symbol": sym, "session": session.isoformat(), "mode": mode,
           "prev_close": prev, "prev_date": base["prev_date"],
           "open": round(day["open"], 4), "high": round(day["high"], 4),
           "low": round(day["low"], 4), "last": round(day["last"], 4),
           "volume": day.get("volume"), "as_of_ms": day.get("as_of_ms"),
           "low_pct": low_pct, "now_pct": now_pct,
           "gap_pct": _pct(day["open"], prev),
           "open_to_low_pct": _pct(day["low"], day["open"]),
           "open_to_now_pct": _pct(day["last"], day["open"]),
           "off_low_pct": _pct(day["last"], day["low"]),
           "state": STATE_DOWN if now_pct <= -THRESHOLD_PCT else STATE_RECLAIMED,
           "adv50": base.get("adv50"), "n_bars": base.get("n_bars")}
    why = suspect_reason(row, day, base)
    if why:
        row["suspect"] = why
        return "data_suspect", row
    return "listed", row


def suspect_reason(row: dict, day: dict, base: dict) -> Optional[str]:
    """Why the price layer cannot trust this drop, else None."""
    prev = base.get("prev_close")
    if prices._is_scale_glitch(day["low"], prev) or prices._is_scale_glitch(day["last"], prev):
        return (f"a {GLITCH_RATIO:g}× or larger move against the prior close — the price "
                "layer's own split / decimal-shift guard")
    live_prev = _pos(day.get("prev_close"))
    if live_prev is not None and prev:
        gap = abs(live_prev / float(prev) - 1.0) * 100.0
        if gap > PREV_CLOSE_TOL_PCT:
            return (f"the live prior close {live_prev:.2f} disagrees with the cached "
                    f"{float(prev):.2f} by {gap:.1f}% — a split or a bad print")
    return None


def fetch_splits_strict(sym: str, since_iso: str) -> list:
    """Every split Massive lists for `sym` executed on/after `since_iso`.
    [] = Massive answered with none. RAISES on no key, a non-200 or a
    transport error (the caller counts it; the URL carries the key, so the
    exception is never logged)."""
    from massive_keys import stocks_key
    from sepa import symbols
    key = stocks_key()
    if not key:
        raise RuntimeError("no stocks key")
    r = prices._http().get(
        "https://api.massive.com/v3/reference/splits",
        params={"ticker": symbols.for_massive(symbols.resolve(str(sym).upper())),
                "execution_date.gte": since_iso, "order": "asc", "limit": 50, "apiKey": key},
        timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"splits HTTP {r.status_code}")
    return [{"execution_date": x.get("execution_date"),
             "split_from": _f(x.get("split_from")) or 1.0,
             "split_to": _f(x.get("split_to")) or 1.0}
            for x in ((r.json() or {}).get("results") or []) if isinstance(x, dict)]


def split_on(splits, session_iso: str) -> Optional[dict]:
    for s in splits or []:
        if str((s or {}).get("execution_date") or "")[:10] == session_iso:
            return s
    return None


# ---------------------------------------------------------------------------
# catalysts — one-session drops through `fallen_catalysts` (PURE but for src)
# ---------------------------------------------------------------------------
def drop_of(row: dict) -> dict:
    """The one-session drop in `fallen_catalysts`' shape: the FALL to the
    session low (`c2c_pct` = the low against the prior close), its two legs —
    the gap and open -> low, so the larger leg names what did the falling even
    on a reclaimed name (critic 2026-10-05) — volume vs normal, and the window =
    the session before through this one."""
    gap, intra = row.get("gap_pct"), row.get("open_to_low_pct")
    leg = None if gap is None or intra is None else ("gap" if gap < intra else "intraday")
    s = date.fromisoformat(row["session"])
    return {"date": row["session"], "c2c_pct": row.get("low_pct"), "gap_pct": gap,
            "intraday_pct": intra, "larger_leg": leg,
            "vol_x50": (row.get("rvol") or {}).get("rvol"),
            "share_of_fall_pct": None, "prev_close": row.get("prev_close"),
            "close": row.get("last"),
            "window": {"lo": KL.prev_market_day(s).isoformat(), "hi": row["session"]}}


def group_symbols(syms) -> set:
    """RSP + every sector ETF + every theme member of the listed names."""
    from rotation import tracker as T
    from sepa import universe as U
    out = {T.BENCHMARK} | set(T.SECTOR_ETF.values())
    for s in syms or []:
        th = U.THEME_BY_TICKER.get(str(s).upper())
        if th:
            out |= {str(m).upper() for m in (U.THEME_UNIVERSE.get(th) or [])}
    return out


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def _resolve(universe, universe_fn) -> list:
    ukey = _ukey(universe)
    if universe_fn is None:
        from supply_demand import demand_reentry as D
        raw = D._resolve_universe(ukey)[0]
    else:
        raw = universe_fn(ukey)
    out, seen = [], set()
    for s in raw or []:
        s = str(s or "").strip().upper()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def build_base(syms, session: date, *, frames_fn=None) -> dict:
    """{SYM: base_read} over the universe + the group symbols. Raises on an
    empty frames read (never memoised)."""
    from rotation import tracker as T
    want = sorted(set(syms) | {T.BENCHMARK} | set(T.SECTOR_ETF.values()))
    frames = (frames_fn or prices.bulk_cached_frames)(want) or {}
    if syms and not frames:
        raise RuntimeError(f"drop10 tab: the price-cache read returned no frames for "
                           f"{len(want):,} names — not memoising an empty read")
    out = {}
    for s in want:
        try:
            out[s] = base_read(frames.get(s), session)
        except Exception as exc:                                # noqa: BLE001
            log.debug("drop10 tab: %s base read failed: %s", s, exc)
            out[s] = None
    del frames
    return out


def _base_for(key: tuple, syms, session: date, frames_fn=None) -> dict:
    with _lock:
        held = _base_memo.get(key)
    if held is not None and (time.time() - held["ts"]) < BASE_TTL_SEC:
        return held["base"]
    base = build_base(syms, session, frames_fn=frames_fn)
    with _lock:
        for k in [k for k in _base_memo if k[0] < key[0]]:
            _base_memo.pop(k, None)
        _base_memo[key] = {"ts": time.time(), "base": base}
    return base


def _splits_for(syms, session_iso: str, splits_fn=None) -> dict:
    """{SYM: list | None} — one Massive splits read per (name, session),
    memoised; None = the read failed (counted `split_unchecked`)."""
    if splits_fn is None:
        splits_fn = fetch_splits_strict
    out, todo = {}, []
    with _lock:
        for s in syms:
            k = (s, session_iso)
            if k in _splits_memo and _splits_memo[k] is not None:
                out[s] = _splits_memo[k]
            else:
                todo.append(s)

    def _one(s):
        try:
            got = splits_fn(s, session_iso)
            return s, list(got) if isinstance(got, list) else None
        except Exception:                                       # noqa: BLE001
            return s, None

    if todo:
        with ThreadPoolExecutor(max_workers=min(SPLIT_WORKERS, len(todo))) as pool:
            for s, got in pool.map(_one, todo):
                out[s] = got
        with _lock:
            for k in [k for k in _splits_memo if k[1] < session_iso]:
                _splits_memo.pop(k, None)
            for s in todo:
                _splits_memo[(s, session_iso)] = out[s]
    return out


def build(universe, now: datetime, *, universe_fn=None, frames_fn=None, snap_fn=None,
          profiles_fn=None, catalysts_load_fn=None, splits_fn=None, etf_fn=None,
          is_delisted=None) -> dict:
    """ONE base read (memoised per session), ONE snapshot over the universe
    (live / after the close only), ONE split read per candidate (memoised),
    ONE profile read and ONE catalysts read over the listed names."""
    mode, session, tape, half = mode_for(now)
    s_iso = session.isoformat()
    ukey = _ukey(universe)
    syms = _resolve(universe, universe_fn)
    base = _base_for((s_iso, ukey), syms, session, frames_fn=frames_fn)
    gsyms = group_symbols(syms)

    snaps: dict = {}
    if mode != MODE_CLOSED:
        if snap_fn is None:
            from chart_maps.board import _bulk_snaps_fanout as snap_fn
        snaps = dict(snap_fn(sorted(set(syms) | gsyms)) or {})
        if syms and not snaps:
            raise RuntimeError(f"drop10 tab: the live snapshot returned nothing for "
                               f"{len(syms):,} names — not memoising an empty read")
        # a chunk the fan-out swallowed comes back as missing names: ask ONCE more
        missing = sorted(s for s in set(syms) | gsyms if s not in snaps)
        if missing:
            try:
                snaps.update(snap_fn(missing) or {})
            except Exception as exc:                            # noqa: BLE001
                log.debug("drop10 tab: snapshot retry failed: %s", exc)

    def day_for(s):
        if mode == MODE_CLOSED:
            return day_from_bar(base.get(s))
        return day_from_snapshot(snaps.get(s), session)

    if etf_fn is None:
        from chart_maps import fallen_tab as FAL
        etf_fn = FAL._static_etfs
    etf_set = etf_fn()
    frac = MB.session_frac(tape, now.astimezone(KL.ET), half_day=half)

    counts = {k: 0 for k in COUNT_KEYS}
    rows: dict = {}
    suspects: list = []
    rets: dict = {}
    for s in sorted(set(syms) | gsyms):
        b, d = base.get(s), day_for(s)
        if b and d and b.get("prev_date") == KL.prev_market_day(session).isoformat():
            r = _pct(d["last"], b["prev_close"])
            if r is not None:
                rets[s] = {s_iso: r}
    for s in syms:
        counts["scanned"] += 1
        b = base.get(s)
        try:
            status, row = classify(s, b, day_for(s), session=session, mode=mode,
                                   etf_set=etf_set, is_delisted=is_delisted)
        except Exception as exc:                                # noqa: BLE001
            log.debug("drop10 tab: %s read failed: %s", s, exc)
            status, row = "no_print", None
        if status == "no_print" and mode != MODE_CLOSED and s not in snaps:
            status = "no_snapshot"          # the snapshot never answered for it (counted apart)
        if row is not None:
            row["rvol"] = rvol_read(day_for(s), b, tape=tape, frac=frac, half_day=half)
        if status == "data_suspect":
            suspects.append(row)
        elif status == "listed":
            rows[s] = row
        counts[status] += 1

    # a split Massive lists as executed on the session -> held out, named
    splits = _splits_for(sorted(rows), s_iso, splits_fn=splits_fn) if rows else {}
    for s in sorted(rows):
        got = splits.get(s)
        if got is None:
            counts["split_unchecked"] += 1
            continue
        hit = split_on(got, s_iso)
        if hit:
            r = rows.pop(s)
            r["suspect"] = (f"Massive lists a {_f(hit.get('split_to')) or 0:g}-for-"
                            f"{_f(hit.get('split_from')) or 0:g} split executed {s_iso}")
            suspects.append(r)
            counts["listed"] -= 1
            counts["data_suspect"] += 1

    lsyms = sorted(rows)
    for s in lsyms:
        counts[rows[s]["state"]] += 1
    try:
        profiles = ((profiles_fn or FC.company_profiles)(lsyms) or {}) if lsyms else {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("drop10 tab: profile read failed: %s", exc)
        profiles = {}
    names = {}
    for s in lsyms:
        prof = profiles.get(s) or {}
        rows[s]["sector"] = prof.get("sector")
        rows[s]["name"] = prof.get("name")
        names[s] = prof.get("name")
    try:
        src = ((catalysts_load_fn or FC.load)(lsyms, names=names) or {}) if lsyms else {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("drop10 tab: catalysts read failed: %s", exc)
        src = {}
    with_item = 0
    for s in lsyms:
        r = rows[s]
        d = drop_of(r)
        items = FC.items_for(s, d, src)
        grp = FC.group_day(s, s_iso, r.get("sector"), rets)
        r["drop"] = {**d, "line": FC.drop_line(d), "items": items, "group": grp,
                     "empty": FC.empty_kinds(items)}
        with_item += int(bool(items))
    src_meta = {k: {kk: v.get(kk) for kk in ("available", "error", "names", "first", "last")}
                for k, v in (src or {}).items()}
    cov = {"drops_total": len(lsyms), "drops_nothing": len(lsyms) - with_item,
           "names_with_item": with_item, "names": len(lsyms)}

    as_ofs = [r["as_of_ms"] for r in rows.values() if r.get("as_of_ms")]
    as_of = (datetime.fromtimestamp(max(as_ofs) / 1000.0, tz=KL.ET).isoformat(timespec="minutes")
             if as_ofs else s_iso)
    suspects.sort(key=lambda r: r["symbol"])
    now_ts = time.time()
    return {"rows": rows, "counts": counts, "suspects": suspects, "mode": mode,
            "session": s_iso, "as_of": as_of, "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=KL.ET).isoformat(timespec="seconds"),
            "ukey": ukey, "rsp_pct": (rets.get("RSP") or {}).get(s_iso), "half_day": bool(half),
            "sources": FC.sources_block(src_meta, cov) if lsyms else None}


# ---------------------------------------------------------------------------
# memo — the 📉 shape, a short TTL in RTH
# ---------------------------------------------------------------------------
def ttl_for(mode: str) -> int:
    return LIVE_TTL_SEC if mode == MODE_LIVE else CLOSED_TTL_SEC


def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _store(key: tuple, entry: dict) -> bool:
    """Under `_lock`. A late older-session build is dropped; storing evicts
    older sessions and the other modes of the same (session, universe)."""
    newest = max((k[1] for k in _memo), default=key[1])
    if key[1] < newest:
        log.info("drop10 tab: dropped a late %s build (memo holds %s)", key[1], newest)
        return False
    for k in [k for k in _memo if k[1] < key[1] or (k[1:] == key[1:] and k != key)]:
        _memo.pop(k, None)
    _memo[key] = entry
    _failures.pop(key, None)
    return True


def _warm(key: tuple, universe: str, now: datetime) -> None:
    def _work():
        try:
            entry = build(universe, now)
            with _lock:
                _store(key, entry)
        except Exception as exc:                                # noqa: BLE001
            log.warning("drop10 tab: build failed for %s: %s", key, type(exc).__name__)
            with _lock:
                _failures[key] = (time.time(), _safe_reason(exc))
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"drop10-tab-{key[1]}-{key[2]}")


def cached_or_warm(universe, *, now: datetime, sync: bool = False) -> dict:
    """{"state": "ready"|"warming"|"error", "entry", "reason", "stale"}.
    A fresh exact entry -> ready. `sync=True` builds inline. Otherwise ONE
    background build (unless one failed under FAIL_RETRY_SEC ago) while the
    newest held entry of the same session + universe is served."""
    mode, session, _tape, _half = mode_for(now)
    ukey = _ukey(universe)
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
# per request: order (PURE)
# ---------------------------------------------------------------------------
def _low_key(r: dict) -> tuple:
    return (float(r["low_pct"]), r["symbol"])


def rank(entry: dict, *, sort: str) -> tuple:
    """(rows in the asked order, counts). Rows are the memo's own dicts —
    READ-ONLY; the board copies the ones it uses."""
    rows = list((entry.get("rows") or {}).values())
    rows.sort(key=_low_key)
    if sort == SORT_NOW:
        rows.sort(key=lambda r: (float(r["now_pct"]), r["symbol"]))
    elif sort == SORT_RECLAIM:
        rows.sort(key=lambda r: (-(r.get("off_low_pct") or 0.0), r["symbol"]))
    elif sort == SORT_RVOL:
        def rk(r):
            v = _f((r.get("rvol") or {}).get("rvol"))
            return (v is None, -(v or 0.0), r["symbol"])
        rows.sort(key=rk)
    counts = {k: 0 for k in COUNT_KEYS}
    counts.update({k: v for k, v in (entry.get("counts") or {}).items() if k in counts})
    return rows, counts


def served_sorts() -> list:
    return [{"key": DEFAULT_SORT, "label": DEFAULT_SORT_LABEL},
            {"key": SORT_NOW, "label": NOW_SORT_LABEL},
            {"key": SORT_RECLAIM, "label": RECLAIM_SORT_LABEL},
            {"key": SORT_RVOL, "label": RVOL_SORT_LABEL}]


# ---------------------------------------------------------------------------
# words (every number from a constant or a count)
# ---------------------------------------------------------------------------
def session_words(mode: str, session_iso: str, as_of, half_day: bool = False) -> str:
    if mode == MODE_LIVE:
        t = str(as_of or "")
        hhmm = t[11:16] if len(t) >= 16 else None
        return (f"live today ({session_iso}), the snapshot as of {hhmm} ET" if hhmm
                else f"live today ({session_iso})")
    if mode == MODE_AFTER:
        close = MB.HALF_DAY_CLOSE_ET if half_day else ZE_CLOSE
        return f"today's regular session ({session_iso}), closed at {close:%H:%M} ET"
    return f"the last closed session ({session_iso})"


def header_text(counts: dict, *, mode: str, session_iso: str, as_of, rsp_pct=None,
                half_day: bool = False) -> str:
    c = counts or {}
    text = (f"{MARK} {_n(c.get('listed'))} of {_n(c.get('scanned'))} stocks traded "
            f"{THRESHOLD_PCT:g}% or more under their prior close at the low — "
            f"{session_words(mode, session_iso, as_of, half_day)}. "
            f"{_n(c.get('down'))} still {THRESHOLD_PCT:g}%+ down, "
            f"{_n(c.get('reclaimed'))} reclaimed above it.")
    if rsp_pct is not None:
        text += _m(f" RSP {float(rsp_pct):+.2f}% the same session.")
    return text


def order_line(sort: str) -> str:
    if sort == SORT_NOW:
        return "Order: deepest under the prior close at the print first."
    if sort == SORT_RECLAIM:
        return "Order: most reclaimed off the session low first — the print against the low."
    if sort == SORT_RVOL:
        return ("Order: volume vs normal first — the session's shares against the 50 sessions "
                "before it (projected to a full session in RTH); a name with no read sits last.")
    return "Order: deepest at the session low first, against the prior close."


def count_line(counts: dict, *, min_tier_label: str, need_date) -> str:
    c = counts or {}
    text = (f"Showing {_n(c.get('shown'))} — {_n(c.get('dropped_thin'))} under the "
            f"liquidity floor ({min_tier_label})")
    if int(c.get("no_turnover") or 0):
        text += f", {_n(c.get('no_turnover'))} with no turnover to check"
    text += (f". Not listed: {_n(c.get('etf'))} ETFs, {_n(c.get('delisted'))} delisted, "
             f"{_n(c.get('data_suspect'))} the data cannot be trusted on (named below — "
             f"check the chart), {_n(c.get('stale'))} whose cached bars end before "
             f"{need_date}, {_n(c.get('no_print'))} with no print this session, "
             f"{_n(c.get('no_bars'))} with no cached bars.")
    if int(c.get("no_snapshot") or 0):
        text += (f" {_n(c.get('no_snapshot'))} names got no answer from the live snapshot "
                 "(asked twice) — not read, not listed.")
    if int(c.get("split_unchecked") or 0):
        text += (f" {_n(c.get('split_unchecked'))} listed names could not be checked for a "
                 "split today (the read failed).")
    return text


def suspects_block(suspects) -> dict:
    s = [x for x in (suspects or []) if isinstance(x, dict)]
    n = len(s)
    head = (f"{n:,} names held out — the drop may be a data artifact (a split, a bad print, a "
            "decimal shift). A real collapse can look the same; check the chart.")
    lines = [f"{x['symbol']} — " + _m(f"low {float(x['low_pct']):+.2f}%") + " vs prior close "
             f"{float(x['prev_close']):.2f}: " + str(x.get("suspect") or "")
             for x in s[:SUSPECT_LINES_MAX]]
    return {"n": n, "head": head, "lines": lines}


def error_note(reason) -> str:
    return ERROR_NOTE_FMT.format(threshold=f"{THRESHOLD_PCT:g}", reason=str(reason or "unknown"),
                                 mins=int(FAIL_RETRY_SEC // 60))


def rvol_text(rv: Optional[dict]) -> str:
    rv = rv or {}
    v = _f(rv.get("rvol"))
    if v is None:
        return "—"
    if rv.get("basis") == "projected":
        return f"{v:.2f}× projected to a full session ({rv.get('session_pct')}% done)"
    if rv.get("basis") == "actual":
        if rv.get("session_pct") is not None:
            return f"{v:.2f}× so far ({rv.get('session_pct')}% of the session done)"
        return f"{v:.2f}× so far — the session is not over"
    return f"{v:.2f}× its 50-day volume"


def state_text(r: dict) -> str:
    if r.get("state") == STATE_DOWN:
        return _m(f"still {THRESHOLD_PCT:g}%+ down — {float(r['now_pct']):+.2f}% now")
    return _m(f"reclaimed — {float(r['now_pct']):+.2f}% now, "
              f"{float(r.get('off_low_pct') or 0):+.2f}% off the low")


def legs_text(r: dict) -> str:
    """"gap −8.50% · open → low −6.30%" — which leg did the falling."""
    parts = []
    if r.get("gap_pct") is not None:
        parts.append(f"gap {float(r['gap_pct']):+.2f}%")
    if r.get("open_to_low_pct") is not None:
        parts.append(f"open → low {float(r['open_to_low_pct']):+.2f}%")
    return _m(" · ".join(parts)) if parts else "—"


def hit_block(r: dict) -> dict:
    d = (r or {}).get("drop") or {}
    items = d.get("items") or []
    return {"text": FC.hit_text(d, items, d.get("group")), "class": FC.hit_class(items),
            "date": d.get("date")}


def tile_badges(r: dict) -> list:
    """ONE pill (Rule #5): the low and the state — `🔻 −21.50% at the low ·
    still down` / `🔻 −14.01% at the low · reclaimed to −6.93%`."""
    tail = ("still down" if r.get("state") == STATE_DOWN
            else f"reclaimed to {float(r['now_pct']):+.2f}%")
    return [{"text": _m(f"{MARK} {float(r['low_pct']):+.2f}% at the low · {tail}"),
             "tone": "warn"}]


def tile_stats(r: dict) -> list:
    grp = ((r.get("drop") or {}).get("group") or {}).get("line") or "—"
    return [{"k": "Prior close", "v": f"{float(r['prev_close']):.2f} · {r.get('prev_date')}"},
            {"k": "Low", "v": _m(f"{float(r['low']):.2f} · {float(r['low_pct']):+.2f}%")},
            {"k": "Now", "v": _m(f"{float(r['last']):.2f} · {float(r['now_pct']):+.2f}%")},
            {"k": "Legs", "v": legs_text(r)},
            {"k": "Volume", "v": rvol_text(r.get("rvol"))},
            {"k": "Group", "v": grp}]


def tile_marker(r: dict) -> Optional[dict]:
    return {"date": r["session"], "label": _m(f"low {float(r['low_pct']):+.1f}%")}


def why_text(r: dict, zone_text: str) -> str:
    return _m(f"{MARK} {float(r['low_pct']):+.2f}% at the low vs the prior close · "
              f"{state_text(r)} · ") + zone_text


def tile_block(r: dict) -> dict:
    """The served `tile.drop10` (the board adds `zone`)."""
    d = r.get("drop") or {}
    return {"session": r["session"], "mode": r.get("mode"), "state": r.get("state"),
            "state_text": state_text(r), "prev_close": r["prev_close"],
            "prev_date": r.get("prev_date"), "open": r["open"], "high": r["high"],
            "low": r["low"], "last": r["last"], "low_pct": r["low_pct"],
            "now_pct": r["now_pct"], "gap_pct": r.get("gap_pct"),
            "open_to_low_pct": r.get("open_to_low_pct"),
            "off_low_pct": r.get("off_low_pct"), "legs_text": legs_text(r),
            "rvol": dict(r.get("rvol") or {}), "rvol_text": rvol_text(r.get("rvol")),
            "sector": r.get("sector"), "hit": hit_block(r),
            "items": [dict(i) for i in (d.get("items") or [])],
            "empty": d.get("empty"), "group": dict(d.get("group") or {})}


# ---------------------------------------------------------------------------
# envelopes
# ---------------------------------------------------------------------------
def _block(state: str, *, mode: str, session_iso: str, sort: str, header: str,
           entry: Optional[dict] = None, counts: Optional[dict] = None,
           stale: bool = False, min_tier_label: Optional[str] = None) -> dict:
    ready = state == "ready" and entry is not None
    need = KL.prev_market_day(date.fromisoformat(session_iso)).isoformat()
    return {"state": state, "mode": mode, "session": session_iso,
            "as_of": (entry or {}).get("as_of") if ready else None,
            "built_at": (entry or {}).get("built_at") if ready else None,
            "stale": bool(stale) if ready else False,
            "measured": MEASURED, "threshold_pct": THRESHOLD_PCT,
            "refresh_sec": LIVE_TTL_SEC if mode == MODE_LIVE else None,
            "glitch_ratio": GLITCH_RATIO, "sort": sort, "header": header,
            "order_line": order_line(sort),
            "count_line": (count_line(counts, min_tier_label=min_tier_label or "—",
                                      need_date=need) if ready else None),
            "note": NOTE,
            "counts": dict(counts) if ready else None,
            "suspects": suspects_block((entry or {}).get("suspects")) if ready else None,
            "catalysts": (entry or {}).get("sources") if ready else None}


def ready_block(counts: dict, *, entry: dict, sort: str, min_tier_label: str,
                stale: bool = False) -> dict:
    return _block("ready", mode=str(entry.get("mode")), session_iso=str(entry["session"]),
                  sort=sort, header=header_text(counts, mode=entry.get("mode"),
                                                session_iso=entry["session"],
                                                as_of=entry.get("as_of"),
                                                rsp_pct=entry.get("rsp_pct"),
                                                half_day=bool(entry.get("half_day"))),
                  entry=entry, counts=counts, stale=stale, min_tier_label=min_tier_label)


def warming_block(*, now: datetime, sort: str) -> dict:
    mode, session, _t, _h = mode_for(now)
    return _block("warming", mode=mode, session_iso=session.isoformat(), sort=sort,
                  header=WARMING_NOTE)


def error_block(reason, *, now: datetime, sort: str) -> dict:
    mode, session, _t, _h = mode_for(now)
    return _block("error", mode=mode, session_iso=session.isoformat(), sort=sort,
                  header=error_note(reason))
