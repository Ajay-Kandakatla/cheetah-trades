"""🧲 Dealer-gamma (GEX) read for every Chart Maps tile — nightly + just in time.

Ajay 2026-09-27: "Can you add gex exposure bullish or bearish signal to the
stocks in our chartmaps and make it sorted by bullish gex please.." — then
"Checkbox, ON by default", "GEX vs the stock's size", "Only Chart Maps names
nightly", "Also just in time GEX read too." and "One tab open both".

ONE builder of the served tile block `gex` (chips, titles, sort keys) for both
reads:
  * NIGHTLY — the latest post-close ledger row (options.gex_history, the 17:50
    ET sweep), attached to every tile by board.attach_gex.
  * LIVE — options.opex.compute_opex at the current spot, fetched once per
    symbol through a process-wide single-flight cache when a tab opens
    (POST /chart-maps/gex-live). The live read is shaped with the ledger's
    own pure slim_row and is NEVER written to the ledger — the ledger stays
    the post-close book that alerts context, the Desk report and the GEX
    Board read.

The bucket is gex_history.board_bucket, verbatim — the GEX Board page's own
read. Strength = signed net dealer gamma per 1% move ÷ the stock's 50-day
average $ volume (sepa.adr.liquidity_check over closed bars).

DISPLAY ONLY and UNMEASURED: no study says this predicts the next move. It
orders the Chart Maps grid client-side; it never hides, gates, sizes, alerts
or buys anything, and no alert, gate or Auto-Pilot path imports this module.
"""
from __future__ import annotations

import functools
import inspect
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("chart_maps.gex_read")

ET = ZoneInfo("America/New_York")

# Constants bound from their owners at import (never retyped here).
from options import gex_history as _GH_BOUND  # noqa: E402

NIGHTLY_MAX_AGE = _GH_BOUND.NIGHTLY_MAX_AGE_DAYS
LIVE_WORKERS = _GH_BOUND.SWEEP_WORKERS



def LIVE_TTL_SEC() -> int:
    """options.zero_dte.CACHE_TTL_SEC, read at call time."""
    from options import zero_dte
    return int(zero_dte.CACHE_TTL_SEC)


def _board():
    from chart_maps import board as B
    return B


def __getattr__(name):
    # Lazy by-reference constants from chart_maps.board (board imports this
    # module, so a top-level import the other way would be a cycle).
    if name == "LIVE_BUDGET_SEC":
        return _board().TAPE_BUDGET_SEC
    if name == "MAX_SYMBOLS":
        return _board().LIMIT_MAX
    raise AttributeError(name)


def _adv_period() -> int:
    from sepa.adr import liquidity_check
    return int(inspect.signature(liquidity_check).parameters["period"].default)


GROUP = {"bullish": 0, "mixed": 1, "bearish": 2}
NO_READ_GROUP = 3
LEGEND = {"no_read_group": NO_READ_GROUP,
          "groups": [{"group": 0, "key": "bullish", "label": "bullish"},
                     {"group": 1, "key": "mixed", "label": "mixed"},
                     {"group": 2, "key": "bearish", "label": "bearish"},
                     {"group": 3, "key": "none", "label": "no read"}]}
TONE = {"bullish": "good", "bearish": "warn", "mixed": "muted"}
SORT_OFF = {"zero_dte": {
    "label": "0DTE keeps its own order",
    "title": ("On 0DTE a dealer pin is the RISK for a premium buyer — this tab's own "
              "Pinned badge is a warning — so 🧲 does not order this tab and its chips "
              "are muted. The tab's Pinned / Amplifying badge reads the 0DTE chain; "
              "🧲 reads the nearest expiry.")}}
SCOPE_NOTE = ("🧲 orders the tiles this page is showing — the tab's own top names after "
              "its cut — not the whole universe behind it.")
RULE_TEXT = ("🧲 Bullish GEX first: bullish names (dealers net long gamma, price at or above "
             "the flip — dips get bought) strongest first, then mixed, then bearish (net short "
             "gamma, price under the flip — moves amplified) weakest first, then names with no "
             "read. Strength = net dealer gamma per 1% move ÷ the stock's 50-day average $ "
             "volume; it runs larger when the nearest expiry is a day out, so those names rank "
             "higher by construction. A read whose nearest expiry has already settled counts as "
             "no read. Inside a group, and for mixed / no read, the tab's own order holds. "
             "UNMEASURED — no study says this predicts the next move. It re-orders only; it "
             "hides, gates, sizes and alerts nothing.")
UNMEASURED_LINE = ("UNMEASURED — no study says this predicts the next move. It orders the "
                   "board only; it hides, gates, sizes and alerts nothing.")
VERDICT = {
    "bullish": "dealers net LONG gamma with price at/above the flip — dips get bought, moves damped",
    "bearish": "dealers net SHORT gamma with price under the flip — moves amplified",
    "mixed": "regime and flip disagree — no directional read",
}
RELIABILITY = {
    "index": ("Index / ETF chain — where the gamma-sign read is most reliable."),
    "single_name": ("Single-name chain — the gamma sign is a heuristic "
                    "(SqueezeMetrics) and can invert on single-name leaders."),
}
_REGIMES = ("pinning", "amplifying")


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------
def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _date(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _session(et: datetime) -> str:
    """sepa.prices.trade_session — the one session clock. Imported at call
    time: binding sepa.prices at board-import time would change which module
    `from sepa import prices` resolves to under the suites' price stubs."""
    from sepa import prices as _p
    return _p.trade_session(et)


def _day_text(d) -> str:
    dd = _date(d)
    if dd is None:
        return "—"
    return f"{dd.strftime('%a')} {dd.month}/{dd.day}"


def adv_before(frame, as_of) -> Optional[float]:
    """50-day average $ volume over CLOSED bars (any bar dated `as_of` or later
    is dropped first). None under 50 bars, zero or non-finite."""
    try:
        if frame is None:
            return None
        from sepa.adr import liquidity_check
        from supply_demand.zone_store import drop_today
        lc = liquidity_check(drop_today(frame, _date(as_of)))
        if lc.get("reason") == "insufficient history":
            return None
        v = _num(lc.get("avg_dollar_vol"))
        return v if v is not None and v > 0 else None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_read: adv failed: %s", exc)
        return None


def strength(net, adv) -> Optional[float]:
    n, a = _num(net), _num(adv)
    if n is None or a is None or a <= 0:
        return None
    return n / a


def strength_text(s) -> Optional[str]:
    v = _num(s)
    if v is None:
        return None
    p = abs(v) * 100
    return f"{p:.2f}%" if p < 1 else f"{p:.1f}%"


def settled(expiration_date, read_at_et: Optional[datetime], read_date) -> bool:
    """True when the read's nearest expiry had already settled when it was
    read: expiry before the read's date, or ON it with the read taken after the
    16:00 close (sepa.prices.trade_session afterhours / closed). A legacy row
    with no read time on its expiry date counts as settled (ledger rows are
    post-close). A pre-04:00 read on an expiry day also counts — conservative:
    it yields no read, never a wrong one."""
    exp = _date(expiration_date)
    rd = _date(read_date)
    if exp is None or rd is None:
        return False
    if exp < rd:
        return True
    if exp > rd:
        return False
    if read_at_et is None:
        return True
    return _session(read_at_et) in ("afterhours", "closed")


def nightly_as_of_text(date_et) -> str:
    return f"{_day_text(date_et)} close"


def live_as_of_text(ts) -> str:
    t = _num(ts)
    if t is None:
        return "live"
    return "live " + datetime.fromtimestamp(t, ET).strftime("%H:%M") + " ET"


def fresh(row: Optional[dict], today) -> bool:
    if not row:
        return False
    d = _date(row.get("date_et"))
    td = _date(today)
    if d is None or td is None:
        return False
    return d >= td - timedelta(days=NIGHTLY_MAX_AGE)


def usable(r: Optional[dict]) -> bool:
    return r is not None and r.get("void") is None


def read_block(row: dict, kind: str, adv, now_et: Optional[datetime] = None) -> dict:
    """One ledger-shaped row (nightly, or a live slim_row) → GexRead.

    `now_et` (the moment the read is SHOWN) voids a read whose nearest expiry
    has settled since it was taken — a Thursday row on a Friday expiry is gone
    from Friday 16:00 on, whatever it said on Thursday. Same `settled` rule,
    applied to (now_et, its date) as well as to the read's own time."""
    from options import gex_history as GH
    rec = _num(row.get("recorded_at"))
    read_at = datetime.fromtimestamp(rec, ET) if rec is not None else (
        now_et if kind == "live" else None)
    read_date = row.get("date_et")
    exp = row.get("expiration_date")
    regime = str(row.get("regime") or "").lower() or None
    if regime not in _REGIMES:
        regime = None
    if settled(exp, read_at, read_date) or (
            now_et is not None and settled(exp, now_et, now_et.date())):
        void = "settled"
    elif regime is None:
        void = "no_gamma"
    else:
        void = None
    bucket = GH.board_bucket(row) if void is None else None
    net = _num(row.get("net_gex_dollars"))
    a = _num(adv)
    exp_d, rd = _date(exp), _date(read_date)
    if kind == "live":
        ts = rec if rec is not None else (read_at.timestamp() if read_at else None)
        as_of = (datetime.fromtimestamp(ts, timezone.utc).isoformat()
                 if ts is not None else None)
        as_of_text = live_as_of_text(ts)
    else:
        as_of = str(read_date) if read_date else None
        as_of_text = nightly_as_of_text(read_date)
    rel = row.get("reliability")
    return {
        "kind": kind,
        "bucket": bucket,
        "void": void,
        "regime": regime,
        "spot": _num(row.get("spot")),
        "flip_strike": _num(row.get("flip_strike")),
        "put_wall": _num(row.get("put_wall")),
        "call_wall": _num(row.get("call_wall")),
        "net_gex_dollars": net,
        "adv_dollars_50": a,
        "strength": strength(net, a) if void is None else None,
        "expiration_date": exp_d.isoformat() if exp_d else None,
        "days_to_expiry": (exp_d - rd).days if exp_d and rd else None,
        "reliability": rel if rel in RELIABILITY else None,
        "as_of": as_of,
        "as_of_text": as_of_text,
    }


def _px(v) -> str:
    n = _num(v)
    return f"${n:,.2f}" if n is not None else "—"


def _levels_line(r: dict) -> str:
    return (f"spot {_px(r.get('spot'))} · flip {_px(r.get('flip_strike'))} · "
            f"put wall {_px(r.get('put_wall'))} · call wall {_px(r.get('call_wall'))}")


def _chip_text(r: dict, prefix: Optional[str] = None) -> str:
    b = r["bucket"]
    base = f"🧲 {prefix}: {b}" if prefix else f"🧲 GEX {b}"
    st = strength_text(r.get("strength"))
    if b in ("bullish", "bearish") and st is not None:
        base += f" · {st}"
    return base


def _strength_line(symbol: str, r: dict) -> Optional[str]:
    if r.get("bucket") not in ("bullish", "bearish"):
        return None
    txt = strength_text(r.get("strength"))
    if txt is None:
        return None
    try:
        adv_txt = _board()._usd_short(r.get("adv_dollars_50"))
    except Exception:                                           # noqa: BLE001
        adv_txt = "—"
    line = (f"Strength {txt}: dealer hedging per 1% move ≈ {txt} of {symbol}'s "
            f"average day ({adv_txt}/day, {_adv_period()} closed sessions)")
    n = r.get("days_to_expiry")
    if r.get("expiration_date") and isinstance(n, int):
        out = ("expires that day" if n == 0 else
               f"{n} day out" if n == 1 else f"{n} days out")
        line += (f" · nearest expiry {_day_text(r['expiration_date'])} ({out}) — "
                 "near-expiry chains read stronger, so a name with an expiry a day "
                 "out ranks higher by construction")
    return line


def _void_line(r: dict, symbol: str) -> Optional[str]:
    who = "Live" if r.get("kind") == "live" else "Last close"
    if r.get("void") == "settled":
        return (f"{who} read used the {_day_text(r.get('expiration_date'))} expiry, "
                "which settled that afternoon — that dealer book is gone; the next "
                "live read in market hours, or the next 17:50 ET sweep, reads the "
                "new chain.")
    if r.get("void") == "no_gamma":
        return (f"{who} read had no usable gamma (no spot or no greeks) — no read.")
    return None


def compose(symbol: str, nightly: Optional[dict], live: Optional[dict],
            live_status: str, *, tab: Optional[str] = None) -> dict:
    """The ONLY builder of the tile block: chips, one shared title, sort."""
    sym = str(symbol or "").upper()
    eff = live if usable(live) else (nightly if usable(nightly) else None)
    disagree = (usable(live) and usable(nightly)
                and live["bucket"] != nightly["bucket"])
    muted = tab in SORT_OFF

    lines = []
    if disagree:
        lines.append(f"Last close: {nightly['bucket']} — {VERDICT[nightly['bucket']]}")
        lines.append(f"Now: {live['bucket']} — {VERDICT[live['bucket']]} "
                     "(the order uses the live read)")
    elif eff is not None:
        lines.append(f"🧲 GEX {eff['bucket']} — {VERDICT[eff['bucket']]}")
    if usable(live):
        lines.append(f"Now ({live['as_of_text']}): {_levels_line(live)}")
    if usable(nightly):
        lines.append(f"Last close ({nightly['as_of_text']} — the 17:50 ET post-close "
                     f"dealer book): {_levels_line(nightly)}")
    if eff is not None:
        sl = _strength_line(sym, eff)
        if sl:
            lines.append(sl)
        rel = RELIABILITY.get(eff.get("reliability") or "")
        if rel:
            lines.append(rel)
    for r in (nightly, live):
        if r is not None:
            vl = _void_line(r, sym)
            if vl:
                lines.append(vl)
    if live_status == "no_options":
        lines.append(f"Massive returned no options chain for {sym} on this read (no "
                     "listed options, or the request was refused) — it retries after "
                     f"{LIVE_TTL_SEC()}s.")
    elif live_status == "pending":
        lines.append("Live read still running — it lands on the next request.")
    elif live_status == "failed":
        lines.append("Live read failed — the last close's read is shown.")
    elif live_status == "market_closed":
        lines.append("Market closed — the last close's dealer book is shown; no live read.")
    if muted:
        lines.append(SORT_OFF[tab]["title"])
    lines.append(UNMEASURED_LINE)
    title = "\n".join(lines)

    def _tone(t: str) -> str:
        return "muted" if muted else t

    if disagree:
        chips = [{"kind": "close", "text": _chip_text(nightly, "close"),
                  "tone": _tone(TONE[nightly["bucket"]]), "title": title},
                 {"kind": "now", "text": _chip_text(live, "now"),
                  "tone": _tone(TONE[live["bucket"]]), "title": title}]
    elif eff is not None:
        chips = [{"kind": "single", "text": _chip_text(eff),
                  "tone": _tone(TONE[eff["bucket"]]), "title": title}]
    elif live_status == "no_options":
        chips = [{"kind": "none", "text": "🧲 no options read", "tone": "muted",
                  "title": title}]
    else:
        chips = [{"kind": "none", "text": "🧲 no GEX read", "tone": "muted",
                  "title": title}]

    group = GROUP[eff["bucket"]] if eff is not None else NO_READ_GROUP
    key = eff.get("strength") if (eff is not None and group in (0, 2)) else None
    return {
        "symbol": sym,
        "live_status": live_status,
        "nightly": nightly,
        "live": live,
        "chips": chips,
        "sort": {"group": group, "key": key,
                 "source": eff["kind"] if eff is not None else None},
    }


def counts(blocks) -> dict:
    by_group = {g["group"]: g["key"] for g in LEGEND["groups"]}
    out = {g["key"]: 0 for g in LEGEND["groups"]}
    for b in blocks or []:
        try:
            g = (b.get("sort") or {}).get("group")
        except AttributeError:
            continue
        out[by_group.get(g, "none")] += 1
    return out


def _norm(symbols, cap: Optional[int] = None) -> list:
    out = []
    for s in symbols or []:
        t = str(s or "").strip().upper()
        if t and t not in out:
            out.append(t)
            if cap is not None and len(out) >= cap:
                break
    return out


def _et_now(now: Optional[datetime] = None) -> datetime:
    n = now if now is not None else datetime.now(ET)
    if n.tzinfo is None:
        n = n.replace(tzinfo=ET)
    return n.astimezone(ET)


# ---------------------------------------------------------------------------
# nightly (board path)
# ---------------------------------------------------------------------------
def nightly_blocks(symbols, frames: Optional[dict] = None, today=None,
                   tab: Optional[str] = None,
                   now: Optional[datetime] = None) -> dict:
    """{SYM: GexTileRead} from ONE ledger read + ONE cached-frames read.
    `now` (default: the clock) voids a row whose expiry has settled since.
    Never raises — any failure → every symbol reads no read."""
    syms = _norm(symbols)
    if not syms:
        return {}
    try:
        from options import gex_history as GH
        now_et = _et_now(now)
        td = _date(today) or now_et.date()
        snaps = GH.snapshot_for(syms) or {}
        if frames is None:
            frames = _board()._burst_frames(syms)
        frames = frames or {}
        out = {}
        for s in syms:
            row = snaps.get(s)
            nightly = None
            if row and fresh(row, td):
                nightly = read_block(row, "nightly", adv_before(frames.get(s), td),
                                     now_et=now_et)
            out[s] = compose(s, nightly, None, "not_asked", tab=tab)
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gex_read: nightly blocks failed: %s", exc)
        return {s: compose(s, None, None, "not_asked", tab=tab) for s in syms}


# ---------------------------------------------------------------------------
# live machinery — own pool, single flight, TTL cache; never writes the ledger
# ---------------------------------------------------------------------------
_POOL: Optional[ThreadPoolExecutor] = None
_POOL_LOCK = threading.Lock()
_LOCK = threading.Lock()          # non-reentrant; nothing runs while it is held
_CACHE: dict = {}
_INFLIGHT: dict = {}
_now = time.time


def _pool() -> ThreadPoolExecutor:
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = ThreadPoolExecutor(max_workers=max(1, int(LIVE_WORKERS)),
                                       thread_name_prefix="gex-live")
        return _POOL


def _live_one(sym: str, today_iso: str) -> tuple:
    """(status, row). compute_opex → the ledger's PURE slim_row, stamped with
    this read's own time. The row is returned, never stored in the ledger."""
    try:
        from options import opex
        from options import gex_history as GH
        row = GH.slim_row(sym, opex.compute_opex(sym), today_iso)
        if row is None:
            return ("no_options", None)
        row["recorded_at"] = _now()
        return ("ok", row)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_read: live %s failed: %s", sym, exc)
        return ("failed", None)


def _land(sym: str, fut, day: Optional[str] = None) -> None:
    """Done-callback: cache ok / no_options (a failure is never cached) and
    clear the in-flight slot only if it still holds THIS job."""
    try:
        status, row = fut.result()
    except Exception:                                           # noqa: BLE001
        status, row = "failed", None
    with _LOCK:
        if status in ("ok", "no_options"):
            _CACHE[sym] = {"ts": _now(),
                           "date_et": (row or {}).get("date_et") or day,
                           "status": status, "row": row}
        if _INFLIGHT.get(sym) is fut:
            del _INFLIGHT[sym]


def _claim(sym: str, today_iso: str, repoll: bool = False) -> tuple:
    """("hit", entry) or ("wait", future). The done-callback is registered
    AFTER the lock is released: on an already-finished future it runs on this
    thread, and running `_land` under `_LOCK` would deadlock."""
    new = False
    with _LOCK:
        e = _CACHE.get(sym)
        if e and e.get("date_et") == today_iso and (
                repoll or _now() - e["ts"] < LIVE_TTL_SEC()):
            return ("hit", e)
        fut = _INFLIGHT.get(sym)
        if fut is None:
            fut = _pool().submit(_live_one, sym, today_iso)
            _INFLIGHT[sym] = fut
            new = True
    if new:
        fut.add_done_callback(functools.partial(_land, sym, day=today_iso))
    return ("wait", fut)


def _reset_for_tests() -> None:
    global _POOL, _LOCK
    if _LOCK.acquire(timeout=2):
        try:
            _CACHE.clear()
            _INFLIGHT.clear()
        finally:
            _LOCK.release()
    else:                         # a test left the lock held (a deadlock bug)
        _LOCK = threading.Lock()
        _CACHE.clear()
        _INFLIGHT.clear()
    with _POOL_LOCK:
        pool, _POOL = _POOL, None
    if pool is not None:
        pool.shutdown(wait=False)


def _closed(now_et: datetime) -> Optional[str]:
    try:
        from market_hours import gate
        reason = gate.closed_reason(now_et)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_read: closed_reason failed: %s", exc)
        reason = None
    if reason:
        return reason
    return "overnight" if _session(now_et) == "closed" else None


def live_payload(symbols, *, tab: Optional[str] = None, repoll: bool = False,
                 now: Optional[datetime] = None,
                 budget_sec: Optional[float] = None) -> dict:
    """The POST /chart-maps/gex-live answer: one row per requested symbol
    (capped at board.LIMIT_MAX, the rest counted in `truncated`)."""
    B = _board()
    tab = tab if tab in B.TABS else None
    cap = B.LIMIT_MAX
    from supply_demand.bounce_room import normalize_symbols
    raw = list(symbols or [])
    all_syms = normalize_symbols(raw, cap=max(1, len(raw)))
    syms = all_syms[:cap]
    truncated = len(all_syms) - len(syms)
    budget = float(B.TAPE_BUDGET_SEC if budget_sec is None else budget_sec)
    now_et = _et_now(now)
    session = _session(now_et)
    closed = _closed(now_et)
    today = now_et.date()
    today_iso = today.isoformat()

    try:
        from options import gex_history as GH
        snaps = GH.snapshot_for(syms) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_read: live snapshot_for failed: %s", exc)
        snaps = {}
    try:
        frames = B._burst_frames(syms) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_read: live frames failed: %s", exc)
        frames = {}

    results: dict = {}
    if closed:
        results = {s: ("market_closed", None) for s in syms}
    else:
        claims = {}
        for s in syms:
            try:
                claims[s] = _claim(s, today_iso, repoll)
            except Exception as exc:                            # noqa: BLE001
                log.debug("gex_read: claim %s failed: %s", s, exc)
                claims[s] = ("failed", None)
        futs = [v for k, v in claims.values() if k == "wait"]
        if futs:
            wait(futs, timeout=max(0.0, budget))
        for s, (k, v) in claims.items():
            if k == "hit":
                results[s] = (v["status"], v.get("row"))
            elif k == "wait":
                if v.done():
                    try:
                        results[s] = v.result()
                    except Exception:                           # noqa: BLE001
                        results[s] = ("failed", None)
                else:
                    results[s] = ("pending", None)
            else:
                results[s] = ("failed", None)

    rows = {}
    for s in syms:
        adv = adv_before(frames.get(s), today)
        row = snaps.get(s)
        nightly = (read_block(row, "nightly", adv, now_et=now_et)
                   if row and fresh(row, today) else None)
        status, lrow = results.get(s, ("failed", None))
        live = None
        if status == "ok" and lrow:
            live = read_block(lrow, "live", adv, now_et=now_et)
        elif status == "ok":
            status = "failed"
        rows[s] = compose(s, nightly, live, status, tab=tab)

    pending = sum(1 for r in rows.values() if r["live_status"] == "pending")
    if closed:
        note = f"Market closed ({closed}) — last close's dealer book shown; no live read."
    elif pending:
        note = f"{pending} names still reading live — they land on the next request."
    else:
        note = ("Live dealer book read for the names on screen; this read is never "
                "stored in the post-close ledger.")
    return {
        "as_of": now_et.astimezone(timezone.utc).isoformat(),
        "as_of_text": live_as_of_text(now_et.timestamp()),
        "session": session,
        "market_closed": closed,
        "rows": rows,
        "pending": pending,
        "counts": counts(rows.values()),
        "legend": LEGEND,
        "scope": SCOPE_NOTE,
        "sort_off": SORT_OFF.get(tab) if tab else None,
        "ttl_sec": LIVE_TTL_SEC(),
        "budget_sec": budget,
        "truncated": truncated,
        "rule": RULE_TEXT,
        "note": note,
    }
