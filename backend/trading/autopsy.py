"""Failed-trade AUTOPSY — every losing Auto-Pilot round-trip gets a
numbers-first post-mortem plus ONE feedback line, so the rules learn on paper
before real money goes into the Supply & Demand concept.

Ajay (2026-09-03): "We have alpaca setup you try paper trading on that account
with live execution. I wanna put some money eventually on the supply demand
concept. Please make a rule to add feedback and analysis of failed trades."

SCOPE — closed trade_journal round-trips with a NEGATIVE realized gain, any
strategy. The journal's explicit lane tag (entry.strategy, written by
entries.enter since 2026-09-05 — "journal it appropriately") is read FIRST:
  demand_zone / breakout -> zone_edge (band + side from the matched state
              doc when there is one, else from entry.entry_reason)
  catalyst    -> its own strategy label; the anchoring band (proximity or
              bounce band in entry_reason) is the floor, kind demand
  minervini   -> pivot floor as below
Untagged / manual rows keep the inference:
  zone_edge   a zone_edge_entry_state doc matches (symbol + ET day of the
              entry; client_order_id / order_id preferred when both sides
              carry one)
  minervini   entry.trigger.path is set (trading/auto_entry.py funnel);
              the pivot is the floor, band = {lo: pivot, hi: pivot}
  manual      everything else (POST /trading/enter by hand)

EVERY classification rule and threshold in this module is an OWNER RULE for
the Supply & Demand strategy (docs/supply_demand/trade_autopsy.md). There is
no book behind them and none is cited. The only book-derived number this
module ever touches is the PLACED stop it reads back from the journal — the
trading/risk_rules.py contract applied at entry (FROZEN, untouched here).

Safety invariants:
  * READ-ONLY over the journal, the zone state, the ledger, prices and the
    gauge; the broker is never imported. Writes ONLY `trade_autopsies`
    (+ one `autopsy` ledger row per trade, the first time it is classified
    on complete inputs).
  * FAILS SOFT: a missing input leaves that field None and the doc
    'incomplete' (re-tried up to MAX_RETRIES, recorded in the doc); a
    re-check that LOSES an input keeps the previous preliminary doc (numbers
    are never replaced by None — `last_miss` records the hiccup); a
    malformed journal doc is skipped or lands incomplete; nothing here
    raises past run(), and run() is fenced AGAIN in exit_engine.tick()
    step (i) so it can never break stop protection.
  * BOUNDED: at most MAX_PER_RUN trades per run (ONE minute-bar fetch each);
    SPY / RSP daily frames load once per run; a doc is re-checked at most
    every RECHECK_SEC until it is 'final'. No work at all when nothing is
    pending (no price or snapshot call).
  * IDEMPOTENT: _id = trade_id, upserts in place; a 'final' doc is never
    recomputed or downgraded.
  * Import-light: stdlib + trading.exit_engine helpers. pandas-bearing
    modules (daytrading.data, sepa.prices, trading.auto_entry) are imported
    lazily INSIDE their seams, and frames are converted to plain records at
    the seam so every number below is pure Python (host-testable without
    pandas, every seam monkeypatchable).

CLI:  python -m trading.autopsy            (one INFO line)
"""
from __future__ import annotations

import logging
import math
import time
import statistics
import sys
from datetime import date, datetime, time as dtime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from trading.exit_engine import _db, _utc_iso, ledger

log = logging.getLogger("trading.autopsy")

ET = ZoneInfo("America/New_York")

COLL = "trade_autopsies"
STATE_COLL = "zone_edge_entry_state"      # owned by trading/zone_edge_entry.py — read only

# ──────────────────────────────────────────────────────────────────────────────
# OWNER RULES — classification thresholds for the Supply & Demand paper trial.
# NOT book numbers (no book exists for this strategy). Locked verbatim in
# tests/test_trading_contracts.py; changing any needs Ajay's sign-off.
# ──────────────────────────────────────────────────────────────────────────────
# Trades autopsied per run — one minute-bar fetch each.
MAX_PER_RUN = 3
# Backlog bound: only losers whose EXIT is within this many days are ever
# autopsied, so the first deploy does not spend 3 Massive minute fetches per
# tick walking every historical paper loser (owner choice, 2026-09-03).
BACKLOG_DAYS = 60
# An 'incomplete' doc (missing input) is re-tried at most this many times.
MAX_RETRIES = 5
# A non-final doc is re-checked at most once per this many seconds.
RECHECK_SEC = 3600
# 'final' once this many CLOSED sessions after the exit day exist; also the
# window for reclaimed_within_2.
SESSIONS_AFTER_EXIT = 2
# Placed stop tighter than the requested stop by more than this many
# percentage points = the risk contract clamped the owner's stop.
CLAMP_TOLERANCE_PT = 0.1
# SPY or RSP down at least this much on the exit day = the tape, not the band.
MARKET_DOWN_PCT = -1.0
# MFE below this many R = the trade never followed through.
FOLLOW_THROUGH_R = 0.5
# Entry more than this far above the band ceiling = chased.
CHASE_DEMAND_PCT = 1.0
CHASE_BREAKOUT_PCT = 2.0
# Session geometry for the timing tags (9:30-16:00 ET).
SESSION_MINUTES = 390
FIRST_MINUTES = 30            # tag first_30_min_entry when entered before this
LATE_MINUTES = 330            # tag late_day_entry when entered after this
# Entry-day open at least this far under the prior close = gap_down_open tag.
GAP_DOWN_PCT = -1.0
# Band with at most this many touches = thin_band tag.
THIN_BAND_TOUCHES = 2
# Placed stop wider than this = wide_stop tag.
WIDE_STOP_PCT = 7.0
# ATR window (daily, closed bars up to the entry day) quoted in the feedback.
ATR_DAYS = 14
# Daily-frame period requested from sepa.prices.load_prices. MUST stay the
# cache-wide default ("2y"): load_prices WRITES a cache miss back into the
# shared price_cache (Mongo + parquet, 20 h TTL) and the SEPA scanner /
# zone store / gauge read that same frame without a period — a shorter
# frame written here would feed a 3-month history to the 200-DMA and the
# 52-week range for the rest of the day (reviewer fix 2026-09-03).
DAILY_PERIOD = "2y"

CLASSES = ("stop_clamped", "shakeout", "band_failed", "market_down",
           "chased", "no_follow_through", "unclassified")
STRATEGIES = ("zone_edge", "minervini", "catalyst", "manual")
STATUSES = ("preliminary", "final", "incomplete")

CITE = ("autopsy: Supply & Demand OWNER RULES, no book "
        "(docs/supply_demand/trade_autopsy.md)")


# ── Small pure helpers ───────────────────────────────────────────────────────

def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (math.inf, -math.inf):
        return None
    return v


def _i(x) -> Optional[int]:
    v = _f(x)
    return None if v is None else int(v)


def _num(x, nd: int = 4):
    """JSON-safe number: None for NaN/inf/non-numeric, else a rounded float."""
    v = _f(x)
    return None if v is None else round(v, nd)


def _to_dt(v) -> Optional[datetime]:
    """Aware datetime from an epoch (UTC), an ISO string ('Z' / offset; naive
    = UTC), or a datetime (naive = UTC; pandas Timestamps qualify). None when
    unreadable."""
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        if isinstance(v, datetime):
            dt = v
        elif isinstance(v, (int, float)):
            if v != v:
                return None
            dt = datetime.fromtimestamp(float(v), timezone.utc)
        else:
            s = str(v).strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _to_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _json_safe(o):
    """Recursive scrub: NaN/inf -> None, numpy scalars -> Python, dates ->
    ISO, anything exotic -> str. bool before int (bool is an int)."""
    if o is None or isinstance(o, (bool, str)):
        return o
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, int):
        return o
    if isinstance(o, float):
        return None if (o != o or o in (math.inf, -math.inf)) else o
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    item = getattr(o, "item", None)              # numpy scalar
    if callable(item):
        try:
            return _json_safe(item())
        except Exception:                        # noqa: BLE001
            pass
    return str(o)


def _s(v, nd: int = 2) -> str:
    """Number for a feedback line: 'n/a' when None, trailing zeros trimmed."""
    f = _f(v)
    if f is None:
        return "n/a"
    if f == int(f) and abs(f) < 1e12:
        return str(int(f))
    return ("%.*f" % (nd, f)).rstrip("0").rstrip(".")


def _pct(a, b) -> Optional[float]:
    """(a / b - 1) * 100, None on missing / zero base."""
    a, b = _f(a), _f(b)
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100.0


def _median(vals: list):
    xs = [float(v) for v in vals if _f(v) is not None]
    return _num(statistics.median(xs)) if xs else None


def _records(df, index_key: str) -> list:
    """Duck-typed DataFrame -> list of dicts, NO pandas import. Every row
    carries `index_key` (the raw index value) plus each column as a float
    (NaN -> None); a `session` column stays a string. [] for None / empty /
    anything that is not frame-shaped."""
    if df is None:
        return []
    try:
        n = len(df)
        if n == 0:
            return []
        idx = list(df.index)
        cols = {str(c): list(df[c]) for c in df.columns}
    except Exception:                            # noqa: BLE001
        return []
    out = []
    for k in range(n):
        row = {index_key: idx[k]}
        for c, vals in cols.items():
            v = vals[k]
            row[c] = (None if v is None else str(v)) if c == "session" else _f(v)
        out.append(row)
    return out


# ── Mongo seams (monkeypatchable) ───────────────────────────────────────────

def _coll(name: str):
    db = _db()
    if db is None:
        return None
    try:
        return getattr(db, name)
    except Exception as exc:                     # noqa: BLE001
        log.warning("autopsy: collection %s unavailable: %s", name, exc)
        return None


def _sub(doc, key: str) -> dict:
    """A journal sub-doc as a dict — {} when absent OR malformed (a string /
    list under `entry` must never raise)."""
    v = doc.get(key) if isinstance(doc, dict) else None
    return v if isinstance(v, dict) else {}


def _gain_pct(trade: dict) -> Optional[float]:
    """Realized gain of a journal doc — journal.py stores it under
    `realized`; `exit.gain_pct` is accepted too. None when unreadable."""
    try:
        g = _f(_sub(trade, "realized").get("gain_pct"))
        if g is None:
            g = _f(_sub(trade, "exit").get("gain_pct"))
        return g
    except Exception:                            # noqa: BLE001
        return None


def _losers(now=None) -> list:
    """Closed journal round-trips with gain_pct < 0 whose exit is within
    BACKLOG_DAYS of `now` (datetime, epoch, or None = wall clock), newest
    entry first. A malformed doc is skipped, never fatal for the run."""
    from trading import journal
    if now is None:
        ref = time.time()
    elif isinstance(now, (int, float)):
        ref = float(now)
    else:
        try:
            ref = float(now.timestamp())
        except Exception:                        # noqa: BLE001
            ref = time.time()
    cutoff = ref - BACKLOG_DAYS * 86400.0
    out = []
    for d in journal.load(status="closed") or []:
        try:
            if not isinstance(d, dict) or d.get("status") != "closed":
                continue
            if not d.get("trade_id") or not d.get("symbol"):
                continue
            g = _gain_pct(d)
            if g is None or g >= 0:
                continue
            ex = _f(_sub(d, "exit").get("epoch"))
            if ex is not None and ex < cutoff:
                continue                         # older than the backlog window
            out.append(d)
        except Exception as exc:                 # noqa: BLE001
            log.warning("autopsy: skipping malformed journal doc: %s", exc)
    return out


def _entry_ids(symbol: str, epoch) -> tuple:
    """(order_id, client_order_id) from the 'entry' ledger row written at
    the journal entry's epoch (±1 s). (None, None) when unknown."""
    ep = _f(epoch)
    db = _db()
    if db is None or ep is None:
        return None, None
    try:
        for d in db.trade_ledger.find({"kind": "entry", "symbol": symbol}):
            e = _f(d.get("epoch"))
            if e is not None and abs(e - ep) < 1.0:
                det = d.get("detail") or {}
                return det.get("order_id"), det.get("client_order_id")
    except Exception as exc:                     # noqa: BLE001
        log.debug("autopsy: entry ids lookup failed %s: %s", symbol, exc)
    return None, None


def _state_doc(symbol: str, day: str, order_id=None,
               client_order_id=None) -> Optional[dict]:
    """The zone_edge_entry_state row that BOUGHT `symbol` on ET day `day`
    (entered=True). client_order_id, then order_id, decide when both sides
    carry one; otherwise the (single) entered row for that symbol/day. None
    = not a zone-edge trade (or the state is unreadable — soft)."""
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        rows = [d for d in coll.find({"symbol": symbol, "date": day,
                                      "entered": True})
                if isinstance(d, dict)]
    except Exception as exc:                     # noqa: BLE001
        log.warning("autopsy: zone state read failed %s: %s", symbol, exc)
        return None
    if not rows:
        return None
    if client_order_id:
        for r in rows:
            if r.get("client_order_id") == client_order_id:
                return r
    if order_id:
        for r in rows:
            if r.get("order_id") == order_id:
                return r
    if client_order_id or order_id:
        # Both sides carry ids and none match: only trust the row when it
        # carries no id at all (older state docs), never a foreign order.
        for r in rows:
            if not r.get("client_order_id") and not r.get("order_id"):
                return r
        return None
    return rows[0]


# ── Price seams (lazy pandas imports; monkeypatchable) ──────────────────────

def _minute_bars(symbol: str, from_day: date, to_day: date) -> Optional[list]:
    """1-min bars for [from_day, to_day] as records {ts (aware UTC), open,
    high, low, close, volume, session} — ONE daytrading.data.
    _fetch_massive_minute call. None = unavailable."""
    try:
        from daytrading.data import _fetch_massive_minute
        df = _fetch_massive_minute(symbol, from_day, to_day)
    except Exception as exc:                     # noqa: BLE001
        log.warning("autopsy: minute bars failed %s: %s", symbol, exc)
        return None
    rows = _records(df, "ts")
    out = []
    for r in rows:
        ts = _to_dt(r.get("ts"))
        if ts is None:
            continue
        r["ts"] = ts.astimezone(timezone.utc)
        out.append(r)
    return out or None


def _daily_bars(symbol: str) -> Optional[list]:
    """Daily OHLCV records {date, open, high, low, close, volume, live} via
    sepa.prices.load_prices(DAILY_PERIOD) with the live bar overlaid
    (with_today_bar); the overlay row carries live=True so it never counts
    as a closed session. None = unavailable."""
    try:
        from sepa.prices import load_prices, with_today_bar
        df = load_prices(symbol, DAILY_PERIOD)
        if df is None or len(df) == 0:
            return None
        appended = False
        try:
            df, info = with_today_bar(df, symbol)
            appended = bool((info or {}).get("appended"))
        except Exception as exc:                 # noqa: BLE001
            log.debug("autopsy: with_today_bar failed %s: %s", symbol, exc)
    except Exception as exc:                     # noqa: BLE001
        log.warning("autopsy: daily bars failed %s: %s", symbol, exc)
        return None
    rows = _records(df, "date")
    out = []
    for r in rows:
        d = _to_date(r.get("date"))
        if d is None:
            continue
        r["date"] = d
        r["live"] = False
        out.append(r)
    if out and appended:
        out[-1]["live"] = True
    return out or None


def _gauge_now() -> Optional[str]:
    """RAW Market Gauge state at RUN time ('constructive'|'caution'|
    'risk_off'), labelled 'now' in the doc — auto_entry._gauge_state, soft."""
    try:
        from trading.auto_entry import _gauge_state
        g = _gauge_state()
        return str(g) if g else None
    except Exception as exc:                     # noqa: BLE001
        log.debug("autopsy: gauge unavailable: %s", exc)
        return None


# ── Pure numbers over records ───────────────────────────────────────────────

def _bar_on(bars: Optional[list], day: Optional[date]) -> Optional[dict]:
    if not bars or day is None:
        return None
    for b in bars:
        if b.get("date") == day:
            return b
    return None


def _prev_bar(bars: Optional[list], day: Optional[date]) -> Optional[dict]:
    if not bars or day is None:
        return None
    prev = None
    for b in bars:
        d = b.get("date")
        if d is None:
            continue
        if d >= day:
            break
        prev = b
    return prev


def daily_change_pct(bars: Optional[list], day: Optional[date]) -> Optional[float]:
    """close(day) / close(previous bar) - 1, in %."""
    cur, prev = _bar_on(bars, day), _prev_bar(bars, day)
    if cur is None or prev is None:
        return None
    return _pct(cur.get("close"), prev.get("close"))


def gap_open_pct(bars: Optional[list], day: Optional[date]) -> Optional[float]:
    """open(day) / close(previous bar) - 1, in %."""
    cur, prev = _bar_on(bars, day), _prev_bar(bars, day)
    if cur is None or prev is None:
        return None
    return _pct(cur.get("open"), prev.get("close"))


def sessions_after(bars: Optional[list], day: Optional[date]) -> list:
    """CLOSED daily bars strictly after `day`, in order (the live overlay
    never counts as a session)."""
    if not bars or day is None:
        return []
    return [b for b in bars
            if b.get("date") is not None and b["date"] > day and not b.get("live")]


def atr_pct(bars: Optional[list], day: Optional[date], ref_px,
            n: int = ATR_DAYS) -> Optional[float]:
    """Average true range of the last `n` CLOSED bars strictly BEFORE `day`
    (the entry day's own bar is still forming at entry time and carries the
    trade's stop print), as a % of `ref_px`. None when fewer than n bars or
    no reference."""
    ref = _f(ref_px)
    if not bars or day is None or not ref:
        return None
    hist = [b for b in bars
            if b.get("date") is not None and b["date"] < day and not b.get("live")]
    if len(hist) < n + 1:
        return None
    hist = hist[-(n + 1):]
    trs = []
    for prev, cur in zip(hist[:-1], hist[1:]):
        h, l, pc = _f(cur.get("high")), _f(cur.get("low")), _f(prev.get("close"))
        if h is None or l is None or pc is None:
            return None
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) / ref * 100.0


def excursion(bars: Optional[list], entry_dt: Optional[datetime],
              exit_dt: Optional[datetime], entry_px) -> dict:
    """{mfe_pct, mae_pct, n_bars} over the RTH minute bars from the entry's
    minute through the exit's minute (both inclusive — the exit bar carries
    the stop print). Bars without a session tag are accepted. All None when
    nothing is in the window."""
    out = {"mfe_pct": None, "mae_pct": None, "n_bars": 0}
    px = _f(entry_px)
    if not bars or entry_dt is None or exit_dt is None or not px:
        return out
    start = entry_dt.astimezone(timezone.utc).replace(second=0, microsecond=0)
    end = exit_dt.astimezone(timezone.utc)
    hi = lo = None
    n = 0
    for b in bars:
        ts = b.get("ts")
        if not isinstance(ts, datetime):
            continue
        if ts < start or ts > end:
            continue
        if b.get("session") not in (None, "rth"):
            continue
        h, l = _f(b.get("high")), _f(b.get("low"))
        if h is None or l is None:
            continue
        n += 1
        hi = h if hi is None else max(hi, h)
        lo = l if lo is None else min(lo, l)
    out["n_bars"] = n
    if n == 0:
        return out
    out["mfe_pct"] = (hi / px - 1.0) * 100.0
    out["mae_pct"] = (lo / px - 1.0) * 100.0
    return out


def session_frac(entry_dt: Optional[datetime]) -> Optional[float]:
    """Minutes since 9:30 ET / 390, clamped to [0, 1]."""
    if entry_dt is None:
        return None
    et = entry_dt.astimezone(ET)
    mins = et.hour * 60 + et.minute + et.second / 60.0 - (9 * 60 + 30)
    return max(0.0, min(1.0, mins / float(SESSION_MINUTES)))


def entry_lag_sec(first_seen, entry_day: Optional[date],
                  entry_dt: Optional[datetime]) -> Optional[float]:
    """Seconds from the board's first_seen ('HH:MM' ET on the entry day) to
    the entry timestamp."""
    if entry_day is None or entry_dt is None or not first_seen:
        return None
    try:
        hh, mm = str(first_seen).split(":")[:2]
        seen = datetime.combine(entry_day, dtime(int(hh), int(mm)), tzinfo=ET)
    except (TypeError, ValueError, AttributeError):
        return None
    return (entry_dt - seen).total_seconds()


# ── Strategy detection ──────────────────────────────────────────────────────

def _band(raw) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    lo, hi = _f(raw.get("lo")), _f(raw.get("hi"))
    if lo is None or hi is None:
        return None
    return {"kind": raw.get("kind"), "lo": lo, "hi": hi,
            "touches": _i(raw.get("touches"))}


def _minervini_det(pivot) -> dict:
    pivot = _f(pivot)
    band = ({"kind": "pivot", "lo": pivot, "hi": pivot, "touches": None}
            if pivot is not None else None)
    return {"strategy": "minervini", "side": "pivot", "kind": "breakout",
            "band": band, "tier": None, "first_seen": None,
            "stop_requested_pct": None}


def _tagged_det(tag: str, entry: dict, state: Optional[dict]) -> Optional[dict]:
    """The explicit journal lane tag (2026-09-05). None when the tag does not
    decide (manual / unknown) so the caller falls back to inference."""
    reason = entry.get("entry_reason")
    reason = reason if isinstance(reason, dict) else {}
    st = state if (isinstance(state, dict) and state) else {}
    if tag in ("demand_zone", "breakout"):
        kind = "demand" if tag == "demand_zone" else "breakout"
        side = st.get("side") or reason.get("side") or ("demand" if kind == "demand" else "supply")
        band = _band(st.get("band")) or _band(reason.get("band"))
        return {"strategy": "zone_edge", "side": side, "kind": kind, "band": band,
                "tier": st.get("tier") or reason.get("tier"),
                "first_seen": st.get("first_seen") or reason.get("first_seen"),
                "stop_requested_pct": _f(st.get("stop_pct")) or _f(reason.get("stop_pct"))}
    if tag == "catalyst":
        prox = reason.get("proximity") if isinstance(reason.get("proximity"), dict) else {}
        bounce = reason.get("bounce") if isinstance(reason.get("bounce"), dict) else {}
        band = _band(prox.get("band")) or _band(bounce.get("band"))
        return {"strategy": "catalyst", "side": reason.get("side") or "demand",
                "kind": "demand", "band": band, "tier": None, "first_seen": None,
                "stop_requested_pct": _f(reason.get("stop_pct"))}
    if tag == "minervini":
        trig = entry.get("trigger") if isinstance(entry.get("trigger"), dict) else {}
        pivot = trig.get("pivot") if trig.get("pivot") is not None else reason.get("pivot")
        return _minervini_det(pivot)
    return None


def detect(entry: dict, state: Optional[dict]) -> dict:
    """{strategy, side, kind, band, tier, first_seen, stop_requested_pct}.
    The explicit journal tag decides first (see _tagged_det); otherwise
    zone_edge when a state doc matched; minervini when the journal trigger
    carries a path (pivot = floor, band lo=hi=pivot); else manual."""
    entry = entry or {}
    tagged = _tagged_det(entry.get("strategy"), entry, state)
    if tagged is not None:
        return tagged
    if isinstance(state, dict) and state:
        side = state.get("side")
        kind = state.get("kind") or ("demand" if side == "demand" else "breakout")
        return {"strategy": "zone_edge", "side": side, "kind": kind,
                "band": _band(state.get("band")), "tier": state.get("tier"),
                "first_seen": state.get("first_seen"),
                "stop_requested_pct": _f(state.get("stop_pct"))}
    trig = entry.get("trigger")
    if isinstance(trig, dict) and trig.get("path"):
        return _minervini_det(trig.get("pivot"))
    return {"strategy": "manual", "side": None, "kind": None, "band": None,
            "tier": None, "first_seen": None, "stop_requested_pct": None}


def floor_of(kind: Optional[str], band: Optional[dict]) -> Optional[float]:
    """The level the thesis rests on: band.lo for demand entries, band.hi
    for breakouts (the cleared ceiling / the pivot). None without a band."""
    if not band or kind not in ("demand", "breakout"):
        return None
    return band["lo"] if kind == "demand" else band["hi"]


# ── Classification (OWNER RULES — first match wins) ─────────────────────────

def chase_limit(kind: Optional[str]) -> Optional[float]:
    if kind == "demand":
        return CHASE_DEMAND_PCT
    if kind == "breakout":
        return CHASE_BREAKOUT_PCT
    return None


def classify(n: dict) -> str:
    """First matching class over the computed numbers `n` (see compute()).
    A rule whose inputs are None never fires."""
    exit_px, req_level = _f(n.get("exit_price")), _f(n.get("stop_requested_level"))
    if n.get("clamped") is True and exit_px is not None and req_level is not None \
            and exit_px >= req_level:
        return "stop_clamped"
    if n.get("leg") == "stop" and n.get("reclaimed_within_2") is True:
        return "shakeout"
    if n.get("band_close_held") is False:
        return "band_failed"
    spy, rsp, mfe_r = _f(n.get("spy_pct_exit_day")), _f(n.get("rsp_pct_exit_day")), _f(n.get("mfe_r"))
    down = ((spy is not None and spy <= MARKET_DOWN_PCT)
            or (rsp is not None and rsp <= MARKET_DOWN_PCT))
    if down and mfe_r is not None and mfe_r < FOLLOW_THROUGH_R:
        return "market_down"
    chase, lim = _f(n.get("chase_pct")), chase_limit(n.get("kind"))
    if chase is not None and lim is not None and chase > lim:
        return "chased"
    if mfe_r is not None and mfe_r < FOLLOW_THROUGH_R:
        return "no_follow_through"
    return "unclassified"


def tags_for(n: dict, status: str) -> list:
    tags = []
    frac = _f(n.get("session_frac"))
    if frac is not None and frac < FIRST_MINUTES / float(SESSION_MINUTES):
        tags.append("first_30_min_entry")
    if frac is not None and frac > LATE_MINUTES / float(SESSION_MINUTES):
        tags.append("late_day_entry")
    gap = _f(n.get("gap_open_pct"))
    if gap is not None and gap <= GAP_DOWN_PCT:
        tags.append("gap_down_open")
    touches = (n.get("band") or {}).get("touches")
    if touches is not None and int(touches) <= THIN_BAND_TOUCHES:
        tags.append("thin_band")
    placed = _f(n.get("stop_placed_pct"))
    if placed is not None and placed > WIDE_STOP_PCT:
        tags.append("wide_stop")
    if status == "incomplete":
        tags.append("partial_data")
    return tags


def feedback(cls: str, n: dict) -> str:
    """One mechanical line per class, filled with the trade's numbers. Never
    advice: a statement of what the numbers say + the owner decision it
    points at."""
    band = n.get("band") or {}
    if cls == "stop_clamped":
        return ("requested stop %s%% was clamped to %s%% at entry (risk "
                "contract); exit %s printed above the requested level %s — "
                "the clamp took the trade out, not the band; the contract's "
                "line is fixed, so entry width vs the band is an owner decision"
                % (_s(n.get("stop_requested_pct")), _s(n.get("stop_placed_pct")),
                   _s(n.get("exit_price")), _s(n.get("stop_requested_level"))))
    if cls == "shakeout":
        return ("stop %s%% under the floor %s sat inside the noise: MAE %s%% vs "
                "ATR %s%%; close back above the floor within %d session(s) "
                "after the exit; a wider buffer is an owner decision"
                % (_s(n.get("stop_below_floor_pct")), _s(n.get("floor")),
                   _s(n.get("mae_pct")), _s(n.get("atr_pct_14")),
                   SESSIONS_AFTER_EXIT))
    if cls == "band_failed":
        return ("band floor %s did not hold: exit-day close %s sat %s%% under "
                "it, MFE %sR; the band was the thesis and it broke; band "
                "selection (touches %s, tier %s) is an owner decision"
                % (_s(n.get("floor")), _s(n.get("exit_day_close")),
                   _s(n.get("close_below_floor_pct")), _s(n.get("mfe_r")),
                   _s(band.get("touches")), n.get("tier") or "n/a"))
    if cls == "market_down":
        return ("SPY %s%% / RSP %s%% on the exit day with MFE %sR (< %sR): "
                "the tape took it, not the band; an index filter on entries "
                "is an owner decision"
                % (_s(n.get("spy_pct_exit_day")), _s(n.get("rsp_pct_exit_day")),
                   _s(n.get("mfe_r")), _s(FOLLOW_THROUGH_R)))
    if cls == "chased":
        return ("entry %s printed %s%% above the band ceiling %s (limit %s%%): "
                "the fill paid for the move already made, stop %s%% below; an "
                "entry-distance cap is an owner decision"
                % (_s(n.get("entry_price")), _s(n.get("chase_pct")),
                   _s(band.get("hi")), _s(chase_limit(n.get("kind"))),
                   _s(n.get("stop_placed_pct"))))
    if cls == "no_follow_through":
        return ("MFE %sR (< %sR) in %s min before the %s: no follow-through "
                "after the touch; a time stop or a confirmation wait is an "
                "owner decision"
                % (_s(n.get("mfe_r")), _s(FOLLOW_THROUGH_R),
                   _s(n.get("time_to_exit_min"), 1), n.get("leg") or "exit"))
    return ("no rule matched: MFE %sR, MAE %s%%, band held %s, SPY %s%% on the "
            "exit day; stays as data — any new rule is an owner decision"
            % (_s(n.get("mfe_r")), _s(n.get("mae_pct")),
               n.get("band_close_held"), _s(n.get("spy_pct_exit_day"))))


def rules_list() -> list:
    """The rule table as data, in priority order — the API returns THIS so
    the page can never drift from the code. Owner rules, no book."""
    return [
        {"class": "stop_clamped",
         "rule": "placed stop tighter than the requested stop by more than the "
                 "tolerance AND the exit printed at/above the requested level "
                 "(the risk contract's clamp fired, not the band)",
         "threshold": "placed < requested - %g pt" % CLAMP_TOLERANCE_PT},
        {"class": "shakeout",
         "rule": "stopped out, then a close back above the floor within the "
                 "sessions after the exit day",
         "threshold": "leg = stop AND reclaimed within %d sessions" % SESSIONS_AFTER_EXIT},
        {"class": "band_failed",
         "rule": "exit-day close under the floor (band.lo for demand, band.hi "
                 "/ pivot for breakouts)",
         "threshold": "band_close_held = false"},
        {"class": "market_down",
         "rule": "SPY or RSP down on the exit day and the trade never reached "
                 "the follow-through R",
         "threshold": "SPY or RSP <= %g%% AND MFE < %gR" % (MARKET_DOWN_PCT, FOLLOW_THROUGH_R)},
        {"class": "chased",
         "rule": "entry above the band ceiling by more than the limit",
         "threshold": "demand > %g%%, breakout > %g%%" % (CHASE_DEMAND_PCT, CHASE_BREAKOUT_PCT)},
        {"class": "no_follow_through",
         "rule": "the trade never reached the follow-through R before the exit",
         "threshold": "MFE < %gR" % FOLLOW_THROUGH_R},
        {"class": "unclassified", "rule": "no rule matched — kept as data",
         "threshold": "—"},
    ]


# ── The autopsy of ONE trade (pure over its inputs) ─────────────────────────

def compute(trade: dict, state: Optional[dict], minute_bars: Optional[list],
            daily_bars: Optional[list], spy_bars: Optional[list],
            rsp_bars: Optional[list], gauge_now: Optional[str] = None,
            ids: tuple = (None, None), prev: Optional[dict] = None,
            now: Optional[datetime] = None) -> dict:
    """Build the trade_autopsies doc for one closed losing round-trip from
    already-loaded inputs. Pure: no I/O, never raises on missing pieces —
    every unavailable number is None and lands in `missing`."""
    entry = _sub(trade, "entry")
    exit_ = _sub(trade, "exit")
    realized = _sub(trade, "realized")
    sym = str(trade.get("symbol") or "").upper()
    entry_epoch = _f(entry.get("epoch"))
    trade_id = trade.get("trade_id") or "%s-%d" % (sym, int(round(entry_epoch or 0)))
    missing = []

    entry_dt = _to_dt(entry_epoch) or _to_dt(entry.get("ts"))
    exit_dt = _to_dt(_f(exit_.get("epoch"))) or _to_dt(exit_.get("ts"))
    if entry_dt is None:
        missing.append("entry_ts")
    if exit_dt is None:
        missing.append("exit_ts")
    entry_day = entry_dt.astimezone(ET).date() if entry_dt else None
    exit_day = exit_dt.astimezone(ET).date() if exit_dt else None

    entry_px, exit_px = _f(entry.get("price")), _f(exit_.get("price"))
    if not entry_px:
        missing.append("entry_price")
    if exit_px is None:
        missing.append("exit_price")
    stop_price = _f(entry.get("stop_price"))
    stop_placed_pct = _f(entry.get("stop_pct"))
    if stop_placed_pct is None and stop_price is not None and entry_px:
        stop_placed_pct = (entry_px - stop_price) / entry_px * 100.0
    if stop_price is None and stop_placed_pct is not None and entry_px:
        stop_price = entry_px * (1.0 - stop_placed_pct / 100.0)
    if stop_placed_pct is None:
        missing.append("stop_placed")
    gain_pct = _gain_pct(trade)
    r_multiple = _f(realized.get("r_multiple"))
    if r_multiple is None and gain_pct is not None and stop_placed_pct:
        r_multiple = gain_pct / stop_placed_pct
    leg = exit_.get("leg")

    det = detect(entry, state)
    kind, band = det["kind"], det["band"]
    floor = floor_of(kind, band)
    req_pct = det["stop_requested_pct"]
    req_level = (entry_px * (1.0 - req_pct / 100.0)
                 if (req_pct is not None and entry_px) else None)
    clamped = None
    if req_pct is not None and stop_placed_pct is not None:
        clamped = (req_pct - stop_placed_pct) > CLAMP_TOLERANCE_PT
    stop_below_floor_pct = None
    if floor and stop_price is not None:
        stop_below_floor_pct = (floor - stop_price) / floor * 100.0
    chase_pct = _pct(entry_px, band["hi"]) if (band and entry_px) else None

    # Minute-bar excursion.
    exc = excursion(minute_bars, entry_dt, exit_dt, entry_px)
    if exc["n_bars"] == 0:
        missing.append("minute_bars")
    mfe_pct, mae_pct = exc["mfe_pct"], exc["mae_pct"]
    mfe_r = (mfe_pct / stop_placed_pct
             if (mfe_pct is not None and stop_placed_pct) else None)
    reached_1r = None if mfe_r is None else bool(mfe_r >= 1.0)
    time_to_exit_min = ((exit_dt - entry_dt).total_seconds() / 60.0
                        if (entry_dt and exit_dt) else None)

    # Daily-frame structure.
    if not daily_bars:
        missing.append("daily_bars")
    exit_bar = _bar_on(daily_bars, exit_day)
    exit_close = _f(exit_bar.get("close")) if exit_bar else None
    if exit_close is None:
        missing.append("exit_day_bar")
    band_close_held = None
    close_below_floor_pct = None
    if floor and exit_close is not None:
        band_close_held = bool(exit_close >= floor)
        close_below_floor_pct = (floor - exit_close) / floor * 100.0
    after = sessions_after(daily_bars, exit_day)[:SESSIONS_AFTER_EXIT]
    reclaimed = None
    if floor and after:
        closes = [_f(b.get("close")) for b in after]
        if any(c is not None and c >= floor for c in closes):
            reclaimed = True
        elif len(after) >= SESSIONS_AFTER_EXIT:
            reclaimed = False
    gap = gap_open_pct(daily_bars, entry_day)
    if gap is None:
        missing.append("entry_day_bar")
    atr = atr_pct(daily_bars, entry_day, entry_px)

    # Index context.
    spy_in, spy_out = daily_change_pct(spy_bars, entry_day), daily_change_pct(spy_bars, exit_day)
    rsp_in, rsp_out = daily_change_pct(rsp_bars, entry_day), daily_change_pct(rsp_bars, exit_day)
    if spy_in is None or spy_out is None:
        missing.append("spy_daily")
    if rsp_in is None or rsp_out is None:
        missing.append("rsp_daily")

    n = {
        "entry_price": entry_px, "exit_price": exit_px, "leg": leg,
        "kind": kind, "band": band, "tier": det["tier"], "floor": floor,
        "stop_requested_pct": req_pct, "stop_requested_level": req_level,
        "stop_placed_pct": stop_placed_pct, "clamped": clamped,
        "stop_below_floor_pct": stop_below_floor_pct, "chase_pct": chase_pct,
        "session_frac": session_frac(entry_dt),
        "mfe_pct": mfe_pct, "mfe_r": mfe_r, "mae_pct": mae_pct,
        "time_to_exit_min": time_to_exit_min,
        "band_close_held": band_close_held, "exit_day_close": exit_close,
        "close_below_floor_pct": close_below_floor_pct,
        "reclaimed_within_2": reclaimed, "gap_open_pct": gap, "atr_pct_14": atr,
        "spy_pct_exit_day": spy_out, "rsp_pct_exit_day": rsp_out,
    }
    if missing:
        status = "incomplete"
    elif len(after) >= SESSIONS_AFTER_EXIT:
        status = "final"
    else:
        status = "preliminary"
    cls = classify(n)
    tags = tags_for(n, status)
    prev = prev if isinstance(prev, dict) else {}
    retries = int(prev.get("retries") or 0) + (1 if status == "incomplete" else 0)
    now_dt = _to_dt(now)
    computed_at = _utc_iso(now_dt.astimezone(timezone.utc) if now_dt else None)

    doc = {
        "_id": trade_id, "trade_id": trade_id, "symbol": sym,
        "strategy": det["strategy"], "side": det["side"], "kind": kind,
        "status": status, "computed_at": computed_at, "retries": retries,
        "ledgered": bool(prev.get("ledgered")),
        "missing": missing,
        "entry": {
            "ts": entry.get("ts"), "epoch": _num(entry_epoch), "price": _num(entry_px),
            "qty": _i(entry.get("qty")), "stop_price": _num(stop_price),
            "stop_requested_pct": _num(req_pct), "stop_placed_pct": _num(stop_placed_pct),
            "clamped": clamped, "first_seen": det["first_seen"],
            "entry_lag_sec": _num(entry_lag_sec(det["first_seen"], entry_day, entry_dt), 1),
            "session_frac": _num(n["session_frac"]), "chase_pct": _num(chase_pct),
            "band": band, "tier": det["tier"],
            "mode": entry.get("mode"), "regime": entry.get("regime"),
            "day": entry_day.isoformat() if entry_day else None,
        },
        "exit": {
            "ts": exit_.get("ts"), "epoch": _num(_f(exit_.get("epoch"))),
            "price": _num(exit_px), "leg": leg, "gain_pct": _num(gain_pct),
            "r_multiple": _num(r_multiple),
            "time_to_exit_min": _num(time_to_exit_min, 1),
            "day": exit_day.isoformat() if exit_day else None,
        },
        "excursion": {"mfe_pct": _num(mfe_pct), "mfe_r": _num(mfe_r),
                      "mae_pct": _num(mae_pct), "reached_1r": reached_1r,
                      "n_bars": exc["n_bars"]},
        "structure": {"floor": _num(floor), "band_close_held": band_close_held,
                      "exit_day_close": _num(exit_close),
                      "reclaimed_within_2": reclaimed,
                      "sessions_after_exit": len(after),
                      "gap_open_pct": _num(gap), "atr_pct_14": _num(atr),
                      "stop_below_floor_pct": _num(stop_below_floor_pct)},
        "market": {"spy_pct_entry_day": _num(spy_in), "rsp_pct_entry_day": _num(rsp_in),
                   "spy_pct_exit_day": _num(spy_out), "rsp_pct_exit_day": _num(rsp_out),
                   "gauge_now": gauge_now},
        "classification": cls, "tags": tags, "feedback": feedback(cls, n),
        "ids": {"order_id": ids[0] if ids else None,
                "client_order_id": ids[1] if ids else None},
    }
    return _json_safe(doc)


# ── Per-run orchestration ───────────────────────────────────────────────────

class _RunCtx:
    """Per-run cache: SPY / RSP daily frames load once, the gauge reads once."""

    def __init__(self):
        self._daily = {}
        self._gauge = False

    def index_bars(self, symbol: str) -> Optional[list]:
        if symbol not in self._daily:
            self._daily[symbol] = _daily_bars(symbol)
        return self._daily[symbol]

    def gauge(self) -> Optional[str]:
        if self._gauge is False:
            self._gauge = _gauge_now()
        return self._gauge


def _autopsy_one(trade: dict, prev: Optional[dict], ctx: _RunCtx,
                 now: datetime) -> dict:
    """Gather every input for one trade (soft) and compute its doc."""
    entry, exit_ = _sub(trade, "entry"), _sub(trade, "exit")
    sym = str(trade.get("symbol") or "").upper()
    entry_dt = _to_dt(_f(entry.get("epoch"))) or _to_dt(entry.get("ts"))
    exit_dt = _to_dt(_f(exit_.get("epoch"))) or _to_dt(exit_.get("ts"))
    entry_day = entry_dt.astimezone(ET).date() if entry_dt else None
    exit_day = exit_dt.astimezone(ET).date() if exit_dt else None

    ids = _entry_ids(sym, entry.get("epoch"))
    state = None
    if entry_day is not None:
        state = _state_doc(sym, entry_day.isoformat(), order_id=ids[0],
                           client_order_id=ids[1])
    minute = None
    if entry_day is not None and exit_day is not None and exit_day >= entry_day:
        minute = _minute_bars(sym, entry_day, exit_day)
    daily = _daily_bars(sym) if sym else None
    return compute(trade, state, minute, daily, ctx.index_bars("SPY"),
                   ctx.index_bars("RSP"), gauge_now=ctx.gauge(), ids=ids,
                   prev=prev, now=now)


def _ledger_detail(doc: dict) -> dict:
    return {"classification": doc.get("classification"),
            "strategy": doc.get("strategy"), "side": doc.get("side"),
            "status": doc.get("status"), "feedback": doc.get("feedback"),
            "tags": doc.get("tags"),
            "gain_pct": (doc.get("exit") or {}).get("gain_pct"),
            "r_multiple": (doc.get("exit") or {}).get("r_multiple"),
            "mfe_r": (doc.get("excursion") or {}).get("mfe_r"),
            "mae_pct": (doc.get("excursion") or {}).get("mae_pct"),
            "chase_pct": (doc.get("entry") or {}).get("chase_pct"),
            "stop_requested_pct": (doc.get("entry") or {}).get("stop_requested_pct"),
            "stop_placed_pct": (doc.get("entry") or {}).get("stop_placed_pct"),
            "band_close_held": (doc.get("structure") or {}).get("band_close_held"),
            "reclaimed_within_2": (doc.get("structure") or {}).get("reclaimed_within_2"),
            "spy_pct_exit_day": (doc.get("market") or {}).get("spy_pct_exit_day"),
            "rsp_pct_exit_day": (doc.get("market") or {}).get("rsp_pct_exit_day"),
            "time_to_exit_min": (doc.get("exit") or {}).get("time_to_exit_min")}


def _keep_previous(prev: dict, fresh: dict) -> dict:
    """A re-check that LOST an input (provider hiccup, circuit breaker) never
    replaces numbers already computed: the previous preliminary doc is kept
    as is, stamped with the miss (`last_miss`), `retries` bumped so the loss
    stays visible, `computed_at` refreshed so the throttle still applies."""
    kept = dict(prev)
    kept["_id"] = prev.get("_id") or fresh.get("_id")
    kept["trade_id"] = prev.get("trade_id") or fresh.get("trade_id")
    kept["computed_at"] = fresh.get("computed_at")
    kept["retries"] = int(prev.get("retries") or 0) + 1
    kept["last_miss"] = {"at": fresh.get("computed_at"),
                         "missing": list(fresh.get("missing") or [])}
    return _json_safe(kept)


def _store(doc: dict, out: dict) -> None:
    """Upsert by _id FIRST; only a stored doc is ledgered — ONE 'autopsy' row
    the first time the trade is classified on complete inputs (status
    preliminary / final). Ledgering after the store means a failed store can
    never leave a feed row whose `ledgered` flag was not persisted (which
    would re-ledger the same trade on every re-check)."""
    first = doc.get("status") != "incomplete" and not doc.get("ledgered")
    if first:
        doc["ledgered"] = True
    coll = _coll(COLL)
    if coll is None:
        out["errors"].append("%s: trade_autopsies unavailable (not stored)"
                             % doc.get("trade_id"))
        return
    try:
        body = {k: v for k, v in doc.items() if k != "_id"}
        coll.update_one({"_id": doc["_id"]}, {"$set": body}, upsert=True)
    except Exception as exc:                     # noqa: BLE001
        out["errors"].append("%s: store failed: %s" % (doc.get("trade_id"), exc))
        return
    if first:
        ledger("autopsy", symbol=doc.get("symbol"), detail=_ledger_detail(doc),
               dry_run=False, cite=CITE)
        out["classified"].append({"trade_id": doc["trade_id"],
                                  "symbol": doc.get("symbol"),
                                  "classification": doc.get("classification")})


def _existing(trade_ids: list) -> dict:
    coll = _coll(COLL)
    if coll is None or not trade_ids:
        return {}
    try:
        return {d.get("_id"): d for d in coll.find({"_id": {"$in": list(trade_ids)}})
                if isinstance(d, dict)}
    except Exception as exc:                     # noqa: BLE001
        log.warning("autopsy: read failed: %s", exc)
        return {}


def _due(prev: Optional[dict], now: datetime, recheck_sec) -> bool:
    """A trade is due when it has no doc; a non-final doc is due again once
    older than recheck_sec, unless it is 'incomplete' past MAX_RETRIES."""
    if not prev:
        return True
    st = prev.get("status")
    if st == "final":
        return False
    if st == "incomplete" and int(prev.get("retries") or 0) >= MAX_RETRIES:
        return False
    at = _to_dt(prev.get("computed_at"))
    if at is None:
        return True
    return (now - at).total_seconds() >= float(recheck_sec)


def run(now=None, max_per_run: int = MAX_PER_RUN,
        recheck_sec=RECHECK_SEC) -> dict:
    """Autopsy up to `max_per_run` due losing trades (new trades first, then
    non-final docs older than recheck_sec). Returns a summary; never raises."""
    now_dt = (_to_dt(now) or datetime.now(timezone.utc)).astimezone(timezone.utc)
    out = {"ok": True, "losers": 0, "pending": 0, "checked": 0, "stored": 0,
           "final": 0, "preliminary": 0, "incomplete": 0, "classified": [],
           "errors": []}
    try:
        losers = _losers(now)
    except Exception as exc:                     # noqa: BLE001
        out["ok"] = False
        out["errors"].append("journal: %s" % exc)
        return out
    out["losers"] = len(losers)
    if not losers:
        return out
    existing = _existing([t["trade_id"] for t in losers])
    todo = []
    for t in losers:                             # newest entry first
        prev = existing.get(t["trade_id"])
        if _due(prev, now_dt, recheck_sec):
            todo.append((0 if prev is None else 1, t, prev))
    todo.sort(key=lambda x: x[0])                # stable: new trades first
    out["pending"] = len(todo)
    if not todo:
        return out
    ctx = _RunCtx()
    try:
        cap = max(0, int(max_per_run))
    except (TypeError, ValueError):
        cap = MAX_PER_RUN
    for _, t, prev in todo[:cap]:
        out["checked"] += 1
        try:
            doc = _autopsy_one(t, prev, ctx, now_dt)
        except Exception as exc:                 # noqa: BLE001
            out["ok"] = False
            out["errors"].append("%s: %s" % (t.get("trade_id"), exc))
            continue
        if (doc.get("status") == "incomplete" and isinstance(prev, dict)
                and prev.get("status") in ("preliminary", "final")):
            doc = _keep_previous(prev, doc)
        n_err = len(out["errors"])
        _store(doc, out)
        if len(out["errors"]) == n_err:
            out["stored"] += 1
        out[doc["status"]] = out.get(doc["status"], 0) + 1
    return out


# ── Report (GET /trading/autopsies) ─────────────────────────────────────────

def report(days: int = 30, now=None) -> dict:
    """{rows (newest exit first, _id dropped), summary, rules, days}.
    JSON-safe; medians None when there are no rows."""
    try:
        days = 30 if days is None else int(days)
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    now_dt = _to_dt(now) or datetime.now(timezone.utc)
    cutoff = now_dt.timestamp() - days * 86400.0
    coll = _coll(COLL)
    rows = []
    if coll is not None:
        try:
            for d in coll.find({}):
                if not isinstance(d, dict):
                    continue
                ep = _f((d.get("exit") or {}).get("epoch"))
                if ep is not None and ep < cutoff:
                    continue
                rows.append(_json_safe({k: v for k, v in d.items() if k != "_id"}))
        except Exception as exc:                 # noqa: BLE001
            log.warning("autopsy: report read failed: %s", exc)
    rows.sort(key=lambda r: (_f((r.get("exit") or {}).get("epoch")) or 0.0,
                             str(r.get("trade_id") or "")), reverse=True)
    by_class, by_strategy = {}, {}
    for r in rows:
        c = str(r.get("classification") or "unclassified")
        by_class[c] = by_class.get(c, 0) + 1
        s = str(r.get("strategy") or "manual")
        by_strategy[s] = by_strategy.get(s, 0) + 1
    summary = {
        "n": len(rows),
        "by_class": by_class,
        "by_strategy": by_strategy,
        "n_final": sum(1 for r in rows if r.get("status") == "final"),
        "n_preliminary": sum(1 for r in rows if r.get("status") == "preliminary"),
        "n_incomplete": sum(1 for r in rows if r.get("status") == "incomplete"),
        "median_mfe_r": _median([(r.get("excursion") or {}).get("mfe_r") for r in rows]),
        "median_time_to_exit_min": _median(
            [(r.get("exit") or {}).get("time_to_exit_min") for r in rows]),
    }
    return {"rows": rows, "summary": summary, "rules": rules_list(), "days": days}


# ── CLI ─────────────────────────────────────────────────────────────────────

def _main(argv) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    summary = run()
    log.info("AUTOPSY run: %s", summary)
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
