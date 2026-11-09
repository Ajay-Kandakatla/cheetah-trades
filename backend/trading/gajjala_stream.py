"""🛰 Stream entries for the 🚩 Gajjala lane — P1 of GG LIVE (2026-11-09), ships SHADOW.

THE ASK (Ajay 2026-11-09, verbatim): "I would like the autopilot to be continously monitored or live tracked and changed
as if Gallalas makes the trades can you modify and make it more live with websockets or something else where there is a
low latency monitoring on the prices action changes please?"

WHAT IT DOES. The api's live hub (`live_hub`, one Massive socket, one print filter `live_hub.PRINT_KINDS`) hands every
filtered print on a lane / A+ symbol to `on_print`, every newly pushed live 🚩 A+ to `on_new_aplus`, and every closed
5-minute bar (+ `BAR_SETTLE_SEC`) to `on_bar_close`. Nothing here changes a lane rule or number: the A+ is still "the
5-minute bar CLOSED through the trigger" (the pass decides it), the entry is still `gajjala_entry`'s ("a market order at
first sight when the last trade is at or over the trigger … or the stop prints first"), sizes, caps, the window, the
cut-off, the flatten and the paper gate are untouched. P1 changes only how fast the lane reacts after the push.

MODES (HIS CALL #1, GG LIVE spec §7):
  shadow (BUILT) — the first regular print at/over the trigger of a waiting lane doc, the first one at/under its stop,
                   and the moment a new A+ reached the hub are RECORDED in `gajjala_lane_stream` (insert-once rows).
                   ZERO broker calls, ever. Orders still go on the 1-minute exit_engine tick.
  live           — the same rows, then `gajjala_entry.run_stream` (the lane's own gate + the lane-run mutex + the
                   lane's own `_try_waiting`) on the print; the bar-close lane run (HIS CALL #17). Only on his word.
  off            — nothing.
The env `GG_STREAM_MODE` may only LOWER the built mode (live → shadow → off), never raise it.

Memo: `written` / `pending` keyed `"{doc_id}|{event}"` — a print whose event is already recorded costs no Mongo and no
broker (the read loop never waits on this module: rows are written on ONE worker thread).

UNMEASURED — a timing record, not a result. Paper only. Not advice.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from trading import gajjala_entry as GL

log = logging.getLogger("trading.gajjala_stream")

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# ── OWNER NUMBERS (GG LIVE spec §3.3; pinned in tests/test_gajjala_lane_stream_2026_11_09.py) ───────────────────────
GG_STREAM_MODES = ("off", "shadow", "live")             # low → high; the env may only move DOWN this list
GG_STREAM_MODE = "shadow"                               # HIS CALL #1 (spec §7): SHADOW records, the 1-minute tick orders — LIVE only on his word
GG_STREAM_RECHECK_SEC = 15.0                            # MINE — spec §3.3: after a LIVE attempt, no new stream attempt on that doc for 15 s (the tick still runs every 60 s)
GG_STREAM_ALPACA_PER_MIN = 60                           # MINE — spec §3.3 / §5.1: token bucket on LIVE attempts (≈ 4 Alpaca calls each) ≤ 30 % of Alpaca's 200/min
GG_STREAM_FRESH_POLLS = 2                               # spec §3.3 (derived): GG_STREAM_FRESH_SEC = 2 × live_hub.HUB_POLL_SEC — a print this fresh is "the last" for a new A+
GG_STREAM_ROW_MAX_TRIES = 2                             # MINE — critic 2026-11-09: a row whose Mongo write FAILED is retried on the next qualifying print, at most this many tries a day (no per-print retry storm)
ODD_LOT_CONDITION = 37                                  # orderflow.tape.KEPT_DESPITE_FLAGS "37 Odd Lot Trade" (kept as regular flow; HIS CALL #2) — pinned equal in the tests
STREAM_COLL = "gajjala_lane_stream"
EVENTS = ("trigger", "trigger_lot", "stop", "seen")
STREAM_WORDS = {
    "shadow": ("🛰 Stream entries: SHADOW — the first regular print at or over the trigger is recorded; orders still go "
               "on the 1-minute check."),
    "live": "🛰 Stream entries: LIVE — a market order on the first regular print at or over the trigger.",
    "off": "🛰 Stream entries: off.",
}
STREAM_SOURCE = "stream:T"                              # the lane doc's last_source on a stream entry (the T channel)


def mode() -> str:
    """The built GG_STREAM_MODE, lowered (never raised) by env GG_STREAM_MODE."""
    built = GG_STREAM_MODE if GG_STREAM_MODE in GG_STREAM_MODES else "off"
    env = str(os.environ.get("GG_STREAM_MODE") or "").strip().lower()
    if env in GG_STREAM_MODES and GG_STREAM_MODES.index(env) < GG_STREAM_MODES.index(built):
        return env
    return built


# ── seams (patched in tests) ─────────────────────────────────────────────────────────────────────────────────────
def _mono() -> float:
    return time.monotonic()


def _wall() -> float:
    return time.time()


def _hub():
    """The api's live hub (WP-A), imported lazily; None when absent."""
    try:
        import live_hub                                         # noqa: WPS433 — lazy on purpose (consumers are lazy)
        return live_hub
    except Exception:                                           # noqa: BLE001
        return None


def _print_kinds() -> tuple:
    """THE one print filter (`live_hub.PRINT_KINDS`, HIS CALL #2) — no hub → nothing passes (never a retyped list)."""
    hub = _hub()
    kinds = getattr(hub, "PRINT_KINDS", None) if hub is not None else None
    return tuple(kinds) if kinds else ()


def fresh_sec() -> float:
    """GG_STREAM_FRESH_SEC = GG_STREAM_FRESH_POLLS × live_hub.HUB_POLL_SEC; no hub → 0 (never fresh → one REST read)."""
    hub = _hub()
    try:
        return float(GG_STREAM_FRESH_POLLS) * float(getattr(hub, "HUB_POLL_SEC"))
    except Exception:                                           # noqa: BLE001
        return 0.0


def _kind_of(conditions) -> str:
    from orderflow.tape import print_kind                       # the ONE print classifier
    return print_kind(conditions)


_WORKER: Optional[ThreadPoolExecutor] = None


def _submit(fn, *args) -> None:
    """The hub's ONE worker (`live_hub.submit`, spec §3.2: hub lane jobs never overlap each other; the read loop never
    waits on Mongo or the broker). No hub (never in the api) → a module-own single worker, same property."""
    global _WORKER
    sub = getattr(_hub(), "submit", None)
    if callable(sub):
        sub(fn, *args)
        return
    if _WORKER is None:
        _WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gg-stream")
    _WORKER.submit(fn, *args)


def _coll():
    return GL._coll(STREAM_COLL)


# ── memo (in memory; one lock — on_print runs on the socket's read loop, jobs on the worker) ─────────────────────
_LOCK = threading.Lock()


class _Memo:
    def __init__(self):
        self.day: Optional[str] = None
        self.rebuilt: Optional[str] = None
        self.written: set = set()
        self.pending: set = set()
        self.attempting: set = set()
        self.recheck: dict = {}
        self.failed: dict = {}
        self.last: dict = {}
        self.prints = 0
        self.bucket = float(GG_STREAM_ALPACA_PER_MIN)
        self.bucket_t: Optional[float] = None


_M = _Memo()


def _reset() -> None:
    """Tests only: a fresh memo."""
    global _M
    with _LOCK:
        _M = _Memo()


def _day_of_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch), tz=UTC).astimezone(ET).date().isoformat()


def _roll(day: str) -> None:
    """Under _LOCK: a new ET day starts a new memo (doc ids carry the date, so nothing of yesterday can match)."""
    if _M.day != day:
        _M.day = day
        _M.written, _M.pending, _M.attempting = set(), set(), set()
        _M.recheck, _M.last, _M.prints, _M.failed = {}, {}, 0, {}


def rebuild(day: Optional[str] = None) -> int:
    """Rebuild `written` from today's `gajjala_lane_stream` ids (the hub's start; also the first worker job of a day).
    Worker-side only (one Mongo read). Returns the count."""
    day = day or datetime.now(ET).date().isoformat()
    c = _coll()
    ids: list = []
    if c is not None:
        try:
            ids = [str(d.get("_id")) for d in c.find({"_id": {"$gte": f"GG:{day}|", "$lt": f"GG:{day}}}"}})]
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala stream: memo rebuild failed: %s", type(exc).__name__)
    with _LOCK:
        _roll(day)
        _M.written |= set(ids)
        _M.rebuilt = day
    return len(ids)


def _ensure_rebuilt(day: str) -> None:
    with _LOCK:
        done = _M.rebuilt == day
    if not done:
        rebuild(day)


# ── pure pieces ──────────────────────────────────────────────────────────────────────────────────────────────────
def _conds(c) -> list:
    out = []
    for x in c or []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _iso_ms(epoch: Optional[float]) -> Optional[str]:
    if epoch is None:
        return None
    return datetime.fromtimestamp(float(epoch), tz=UTC).isoformat(timespec="milliseconds")


def events_for(price, trigger, stop, conditions) -> list:
    """The stream events one print makes on a WAITING doc (Decimal compares, the lane's rule): at/over the trigger →
    `trigger` (+ `trigger_lot` when it is not an odd lot); at/under the stop → `stop`."""
    p = GL._f(price)
    if p is None:
        return []
    out = []
    t, s = GL._f(trigger), GL._f(stop)
    if t is not None and GL._D(p) >= GL._D(t):
        out.append("trigger")
        if ODD_LOT_CONDITION not in _conds(conditions):
            out.append("trigger_lot")
    if s is not None and GL._D(p) <= GL._D(s):
        out.append("stop")
    return out


def _take_token() -> bool:
    """Under _LOCK: the LIVE attempt bucket (GG_STREAM_ALPACA_PER_MIN, refilled continuously over 60 s)."""
    now = _mono()
    cap = float(GG_STREAM_ALPACA_PER_MIN)
    if _M.bucket_t is None:
        _M.bucket_t, _M.bucket = now, cap
    _M.bucket = min(cap, _M.bucket + (now - _M.bucket_t) * cap / 60.0)
    _M.bucket_t = now
    if _M.bucket >= 1.0:
        _M.bucket -= 1.0
        return True
    return False


# ── the hub's three entry points ─────────────────────────────────────────────────────────────────────────────────
def on_print(pr: dict, doc_view: dict, gate_ok: bool) -> None:
    """One filtered print (sync on the socket's read loop: O(docs of the symbol), no Mongo, no broker, never raises).
    `pr` = {"sym", "p", "s", "c", "t_ms", "recv", "trfi"[, "kind"]}; `doc_view` = {doc_id: {symbol, trigger, stop,
    state, updated_at}}; `gate_ok` = the hub's gate snapshot (switch, paper, local market clock, entry window)."""
    try:
        m = mode()
        if m == "off" or not isinstance(pr, dict):
            return
        kind = pr.get("kind") or _kind_of(pr.get("c"))
        if kind not in _print_kinds():
            return
        sym = str(pr.get("sym") or "").upper()
        p = GL._f(pr.get("p"))
        if not sym or p is None or p <= 0:
            return
        recv = GL._f(pr.get("recv"))
        recv = _wall() if recv is None else recv
        day = _day_of_epoch(recv)
        with _LOCK:
            _roll(day)
            _M.last[sym] = (p, recv)
            _M.prints += 1
        if not gate_ok:
            return
        mine = [(k, d) for k, d in list((doc_view or {}).items())
                if isinstance(d, dict) and str(d.get("symbol") or "").upper() == sym and d.get("state") == "waiting"]
        # spec §3.7: hub lane attempts by doc alert_at, then the GC.SUBS setup index, then the symbol (= _try_waiting)
        mine.sort(key=lambda kd: (str(kd[1].get("alert_at") or "9999"), GL._setup_idx(kd[1].get("setup")), sym))
        for doc_id, d in mine:
            evs = events_for(p, d.get("trigger"), d.get("stop"), pr.get("c"))
            if not evs:
                continue
            with _LOCK:
                new = [e for e in evs if f"{doc_id}|{e}" not in _M.written and f"{doc_id}|{e}" not in _M.pending]
                for e in new:
                    _M.pending.add(f"{doc_id}|{e}")
                attempt = False
                if m == "live" and doc_id not in _M.attempting and _mono() >= _M.recheck.get(doc_id, float("-inf")):
                    attempt = _take_token()
                    if attempt:
                        _M.attempting.add(doc_id)
            if new or attempt:
                _submit(_job_print, str(doc_id), dict(d), dict(pr), new, attempt, m)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala stream: print dropped: %s", exc)


def _row(doc_id: str, d: dict, pr: dict, event: str, m: str) -> dict:
    conds = _conds(pr.get("c"))
    t_ms = GL._f(pr.get("t_ms"))
    recv = GL._f(pr.get("recv"))
    return {"_id": f"{doc_id}|{event}", "doc_id": doc_id, "symbol": str(pr.get("sym") or d.get("symbol") or "").upper(),
            "event": event, "print_px": GL._f(pr.get("p")), "print_size": GL._f(pr.get("s")), "conditions": conds,
            "odd_lot": ODD_LOT_CONDITION in conds, "print_t": _iso_ms(t_ms / 1000.0) if t_ms is not None else None,
            "recv_t": _iso_ms(recv), "lag_ms": (int(round(recv * 1000.0 - t_ms))
                                                if (t_ms is not None and recv is not None) else None),
            "mode": m}


def _insert_once(row: dict) -> str:
    """Insert-once → "written" (this call wrote it) | "dup" (already on file) | "error" (not written: no store or a
    failed write — the memo stays clear so a later print retries, GG_STREAM_ROW_MAX_TRIES)."""
    c = _coll()
    if c is None:
        return "error"
    try:
        c.insert_one(dict(row))
        return "written"
    except GL._dup_error():
        return "dup"
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala stream: row %s not written: %s", row.get("_id"), type(exc).__name__)
        return "error"


def _settle(key: str, status: str) -> None:
    """Under _LOCK: pending → written on a write or a duplicate; a failed write leaves the memo clear until its
    GG_STREAM_ROW_MAX_TRIES-th try, then the row is given up for the day (logged)."""
    _M.pending.discard(key)
    if status != "error":
        _M.written.add(key)
        _M.failed.pop(key, None)
        return
    n = _M.failed.get(key, 0) + 1
    _M.failed[key] = n
    if n >= GG_STREAM_ROW_MAX_TRIES:
        _M.written.add(key)
        log.warning("gajjala stream: row %s given up after %d failed writes", key, n)


def _job_print(doc_id: str, d: dict, pr: dict, events: list, attempt: bool, m: str) -> None:
    """Worker: the new rows (insert-once), then — LIVE only — one `run_stream` attempt. Never raises."""
    try:
        recv = GL._f(pr.get("recv"))
        _ensure_rebuilt(_day_of_epoch(recv if recv is not None else _wall()))
        for e in events:
            key, status = f"{doc_id}|{e}", "error"
            try:
                with _LOCK:
                    done = key in _M.written                    # the day's rebuild already holds it (a restart)
                status = "dup" if done else _insert_once(_row(doc_id, d, pr, e, m))
            finally:
                with _LOCK:
                    _settle(key, status)
        if attempt and m == "live":
            t_ms = GL._f(pr.get("t_ms"))
            GL.run_stream(doc_id, last=GL._f(pr.get("p")), source=STREAM_SOURCE,
                          print_t=_iso_ms(t_ms / 1000.0) if t_ms is not None else None)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala stream: job %s failed: %s", doc_id, type(exc).__name__)
    finally:
        if attempt:
            with _LOCK:
                _M.attempting.discard(doc_id)
                _M.recheck[doc_id] = _mono() + GG_STREAM_RECHECK_SEC


def _price_of(brk, sym: str) -> tuple:
    """A new A+'s "last": the stream print when it is fresh (≤ fresh_sec), else ONE REST read (`_live_last`)."""
    s = str(sym or "").upper()
    with _LOCK:
        lp = _M.last.get(s)
    if lp is not None and (_wall() - lp[1]) <= fresh_sec():
        return lp[0], STREAM_SOURCE
    return GL._live_last(brk, s)


def on_new_aplus(rows: list, now: Optional[datetime] = None) -> dict:
    """Worker (the hub submits it): today's newly pushed live 🚩 A+ rows ({_id, symbol, trigger, stop, setup,
    claimed_at}). SHADOW → one `{id}|seen` row each (when the lane WOULD have claimed it). LIVE → the lane's claim of
    exactly those ids + an entry attempt priced stream-if-fresh-else-REST. Never raises."""
    out = {"mode": mode(), "seen": 0, "attempted": False}
    try:
        m = out["mode"]
        ids = []
        for r in rows or []:
            _id = str((r or {}).get("_id") or (r or {}).get("id") or "")
            if _id.startswith("GG:"):
                ids.append((_id, r))
        if m == "off" or not ids:
            return out
        wall = now.timestamp() if isinstance(now, datetime) else _wall()
        if m == "shadow":
            day = _day_of_epoch(wall)
            with _LOCK:
                _roll(day)
            _ensure_rebuilt(day)
            for _id, r in ids:
                key = f"{_id}|seen"
                with _LOCK:
                    if key in _M.written or key in _M.pending:
                        continue
                    _M.pending.add(key)
                status = "error"
                try:
                    status = _insert_once({"_id": key, "doc_id": _id, "symbol": str(r.get("symbol") or "").upper(),
                                           "event": "seen", "recv_t": _iso_ms(wall), "mode": m})
                    if status == "written":
                        out["seen"] += 1
                finally:
                    with _LOCK:
                        _settle(key, status)
            return out
        with _LOCK:
            ok = _take_token()
        if not ok:
            return out                                          # bucket empty: the minute tick claims it
        out["attempted"] = True
        out["run"] = GL.run_stream(None, claim_ids=[i for i, _ in ids], price_of=_price_of, source=STREAM_SOURCE)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala stream: new A+ failed: %s", type(exc).__name__)
    return out


def on_bar_close(now: Optional[datetime] = None) -> Optional[dict]:
    """Worker: LIVE only → the lane's own run() (management at close + settle; HIS CALL #17). SHADOW / OFF → nothing."""
    if mode() != "live":
        return None
    try:
        return GL.run(None, None, now, source="bar_close")
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala stream: bar-close run failed: %s", type(exc).__name__)
        return None


def status() -> dict:
    """The lane tab's 🛰 line (served verbatim): mode + word + today's counts (in memory, this process)."""
    m = mode()
    today = datetime.now(ET).date().isoformat()
    with _LOCK:
        same = _M.day == today
        prints = _M.prints if same else 0
        firsts = sum(1 for k in _M.written if k.endswith("|trigger")) if same else 0
    return {"mode": m, "word": STREAM_WORDS[m], "prints_today": prints, "first_prints_today": firsts}
