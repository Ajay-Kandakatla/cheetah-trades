"""⏱ Bar close + settle — a bar-finality PROBE now, the early pass only on his word (GG LIVE spec §3.4, WP-C, 2026-11-09).

Ajay 2026-11-09: "I would like the autopilot to be continously monitored or live tracked and changed as if Gallalas makes
the trades can you modify and make it more live with websockets or something else where there is a low latency monitoring
on the prices action changes please?" / "same for reuglar Gajjlas tab as well need it to be more live"

Today the 🚩 pass reads the 5-minute bar that closed at :00 / :05 on the crontab's `:x1` minute (PASS_MINUTE_OFFSET) —
60 s after the close, of which BAR_SETTLE_SEC (30 s) is the closed-bar definition and the other 30 s pure wait. Moving the
pass to close + BAR_SETTLE_SEC would take ~30 s off every ring, but nobody has measured whether the last minute bar is
FINAL 30 s after it closed. So this module ships in `probe` mode (GC.GAJJALA_BAR_CLOSE_MODE, HIS CALL #5):

  the cron pass (run.main, cron path only) spawns ONE detached child per tick (`run_1m._popen`, the one spawn engine)
  → `python -m chart_maps.gajjala.run --at-bar-close` → `wait_and_run()`:
     target = the next 5-minute boundary + BAR_SETTLE_SEC strictly after now (ET grid, PASS_CADENCE_SEC)
     refuse (exit 0, one log line "gajjala bar-close: <reason>") when the mode is off, the day is closed
     (market_hours.gate.closed_reason), the target is outside the pass window (run.in_window, and the 1-minute loop's
     own extended-close check run_1m._after_extended_close — see the doc), or the child woke more than
     BAR_CLOSE_LATE_MAX_SEC after the target (host sleep)
  probe: ≤ GG1M_MAX_NAMES names (run_1m.names_for — the house "names that matter most" order), today's minute bars
     fetched with force=True at the target (at30) and again at the cron pass's own read moment (close +
     PASS_MINUTE_OFFSET minutes → at60), each resampled by timeframes.resample_ohlcv and cut by bars.closed_only — only
     the bar right-labelled target − BAR_SETTLE_SEC is read, NEVER the forming one (the live-bar overlay trap) — one
     gajjala_bar_final row per name: changed / fields_changed / v_delta. A failed fetch = no row, never a retry. No lease,
     no pass, no push. At most GAJJALA_BAR_FINAL_PROBE_WORKERS fetches at once (the real pass fetches beside it). A
     child that wakes > BAR_CLOSE_LATE_MAX_SEC late for the SECOND read skips it: its rows are marked `late`, never
     `changed`. One child per target (a first-wins `claim|…` doc — a pass that ended after :x5:30 spawns a second child
     aimed at the same target; it refuses). After GAJJALA_BAR_FINAL_PROBE_SESSIONS session dates of rows the
     `probe_complete` marker is written WITHOUT `at` (the rows' 30-day TTL never deletes it) and read FIRST:
     "probe complete — HIS CALL #5" for good.
  on (HIS CALL #5 only): `run.run_pass(None, store=ST.default(), deps=run._cron_deps())` — the cron path's own call on
     the wall clock and the CRON lease, never `now=target` (a given clock flips run_pass into replay semantics). The
     `:x1` tick 30 s later is gap-refused; a dead child leaves the gap open and the tick runs today's pass. The child
     never spawns another child.

The env GAJJALA_BAR_CLOSE_MODE can only LOWER the mode (on → probe → off), never raise it. UNMEASURED: this measures an
operational timing (bar finality), never an outcome; nothing here trades, sizes or rings.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.bar_close")

ET = ZoneInfo("America/New_York")
MODES = ("off", "probe", "on")                 # ascending — an env value may only pick an EARLIER one
MODE_ENV = "GAJJALA_BAR_CLOSE_MODE"
ARGV_CHILD = (sys.executable, "-m", "chart_maps.gajjala.run", "--at-bar-close")
PROC_NAME = "gajjala-bar-close"
COLL = "gajjala_bar_final"
LOG_PREFIX = "gajjala bar-close:"
OHLCV = (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"), ("v", "volume"))
SESSION_PARTS = ("regular", "extended")        # §3.7 ordering: regular then extended
# the refusal words (served nowhere — one log line each)
R_OFF = "off (GAJJALA_BAR_CLOSE_MODE)"
R_WINDOW = "outside the pass window"
R_LATE = "woke late"
R_COMPLETE = "probe complete — HIS CALL #5"
R_OWNED = "another child owns this target"
R_CLAIM_FAILED = "the target claim failed (store error)"
COMPLETE_ID = "probe_complete"                 # the completion marker: NO `at` (the TTL never deletes it), NO `date`
CLAIM_PREFIX = "claim|"                        # per-target first-wins docs: `at` (TTL) but NO `date` (never a session)


def _wall() -> datetime:
    return datetime.now(timezone.utc)


def _utc(t: datetime) -> datetime:
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def _et(t: datetime) -> datetime:
    return _utc(t).astimezone(ET)


# ── the switch ────────────────────────────────────────────────────────────────────────────────────────────────────
def mode() -> str:
    """GC.GAJJALA_BAR_CLOSE_MODE, LOWERED (never raised) by the env GAJJALA_BAR_CLOSE_MODE (read at call time). An unknown
    constant reads as "off"; an unknown env value changes nothing."""
    const = str(GC.GAJJALA_BAR_CLOSE_MODE or "").strip().lower()
    if const not in MODES:
        return MODES[0]
    env = os.environ.get(MODE_ENV, "").strip().lower()
    if env in MODES and MODES.index(env) < MODES.index(const):
        return env
    return const


# ── the clock ─────────────────────────────────────────────────────────────────────────────────────────────────────
def next_target(now: Optional[datetime] = None) -> datetime:
    """The first 5-minute boundary + BAR_SETTLE_SEC STRICTLY after `now` (ET grid, cadence PASS_CADENCE_SEC) — an ET
    datetime. 10:03:12 → 10:05:30; 10:05:29.9 → 10:05:30; 10:05:30.1 → 10:10:30; 10:05:30 itself → 10:10:30."""
    et = _et(now if now is not None else _wall())
    wall = et.replace(tzinfo=None)
    midnight = wall.replace(hour=0, minute=0, second=0, microsecond=0)
    cad, settle = int(GC.PASS_CADENCE_SEC), int(GC.BAR_SETTLE_SEC)
    secs = (wall - midnight).total_seconds()
    k = int((secs - settle) // cad) + 1
    return (midnight + timedelta(seconds=k * cad + settle)).replace(tzinfo=ET)


def bar_label(target: datetime) -> datetime:
    """The 5-minute bar a target reads: right-labelled target − BAR_SETTLE_SEC (ET)."""
    return _et(target) - timedelta(seconds=GC.BAR_SETTLE_SEC)


def at60_moment(target: datetime) -> datetime:
    """The second read: target + PASS_MINUTE_OFFSET minutes − BAR_SETTLE_SEC = the bar's close + the `:x1` offset — the
    moment the cron pass reads that same bar today."""
    return _et(target) + timedelta(seconds=int(GC.PASS_MINUTE_OFFSET) * 60 - int(GC.BAR_SETTLE_SEC))


def refusal(target: datetime) -> Optional[str]:
    """Why a child aimed at `target` does nothing (before it sleeps), or None. Mode, closed day, pass window."""
    if mode() == "off":
        return R_OFF
    from market_hours.gate import closed_reason
    why = closed_reason(_et(target))
    if why:
        return why
    from . import run as RUN
    from . import run_1m as R1
    if not RUN.in_window(target) or R1._after_extended_close(target):
        return R_WINDOW
    return None


# ── the spawn (the cron path of run.main) ─────────────────────────────────────────────────────────────────────────
def spawn_child(spawn: Optional[Callable] = None) -> bool:
    """Start `python -m chart_maps.gajjala.run --at-bar-close` DETACHED through run_1m._popen (one spawn engine: a new
    session, no inherited descriptors). True when started; never raises (False). With no injected `spawn`, a pytest run
    never starts a real process (False) — the test suite's RUN.main([]) calls would otherwise fork a sleeping child."""
    try:
        if spawn is None and os.environ.get("PYTEST_CURRENT_TEST"):
            log.debug("%s not spawned under pytest", LOG_PREFIX)
            return False
        from . import run_1m as R1
        proc = (spawn or R1._popen)(list(ARGV_CHILD), PROC_NAME)
        log.debug("%s %s pid %s", LOG_PREFIX, PROC_NAME, getattr(proc, "pid", None))
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.debug("%s spawn raised %s", LOG_PREFIX, type(exc).__name__)
        return False


# ── the probe's store ─────────────────────────────────────────────────────────────────────────────────────────────
def _default_coll():
    from . import store as ST
    return ST._coll(COLL)


def ensure_index(coll) -> None:
    """TTL GC.LEDGER_TTL_DAYS on `at` (best-effort)."""
    try:
        coll.create_index([("at", 1)], expireAfterSeconds=int(GC.LEDGER_TTL_DAYS) * 86400)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("%s index failed: %s", LOG_PREFIX, type(exc).__name__)


def probe_dates(coll) -> list:
    """The distinct session dates gajjala_bar_final holds (a failed read → [] — the probe runs, never stops on a fault)."""
    try:
        return sorted(d for d in (coll.distinct("date") or []) if d)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("%s date read failed: %s", LOG_PREFIX, type(exc).__name__)
        return []


def marker_present(coll) -> bool:
    """The completion marker (a failed read → False: the date count still decides)."""
    try:
        return coll.find_one({"_id": COMPLETE_ID}) is not None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("%s marker read failed: %s", LOG_PREFIX, type(exc).__name__)
        return False


def mark_complete_if_due(coll, wall: Callable = None) -> bool:
    """When GAJJALA_BAR_FINAL_PROBE_SESSIONS dates are in, write the completion marker ONCE — with no `at`, so the
    30-day TTL on the rows never brings the probe back. True when the marker is (now) present."""
    dates = probe_dates(coll)
    if len(dates) < int(GC.GAJJALA_BAR_FINAL_PROBE_SESSIONS):
        return False
    try:
        coll.update_one({"_id": COMPLETE_ID}, {"$setOnInsert": {
            "kind": "marker", "dates": dates, "complete_at": _utc((wall or _wall)())}}, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("%s marker write failed: %s", LOG_PREFIX, type(exc).__name__)
    return True


def probe_complete(coll, wall: Callable = None) -> bool:
    """The marker FIRST (the rows expire after LEDGER_TTL_DAYS; the marker never does), then the date count (which writes
    the marker when it is due)."""
    return marker_present(coll) or mark_complete_if_due(coll, wall)


def claim_target(coll, target: datetime, wall: Callable = None) -> Optional[bool]:
    """First-wins on one target: an upsert of `claim|{target ISO}` — True = this child owns it, False = another child
    already did, None = the store failed (the child refuses: a missed slot costs nothing)."""
    try:
        res = coll.update_one({"_id": f"{CLAIM_PREFIX}{_utc(target).isoformat()}"},
                              {"$setOnInsert": {"kind": "claim", "pid": os.getpid(), "at": _utc((wall or _wall)())}},
                              upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("%s claim failed: %s", LOG_PREFIX, type(exc).__name__)
        return None
    return getattr(res, "upserted_id", None) is not None


# ── the read ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _load_default(sym, day, force=False, include_premarket=True, include_afterhours=False):
    from . import run as RUN
    return RUN._load_day(sym, day, force=force, include_premarket=include_premarket,
                         include_afterhours=include_afterhours)


def read_bar(raw, label_et: datetime, wall: datetime) -> Optional[dict]:
    """The 5-minute bar right-labelled `label_et` out of today's raw minute bars — resampled by the house resampler
    (timeframes.resample_ohlcv, LEFT-closed RIGHT-labelled) and cut by bars.closed_only(…, wall): a bar whose right
    label is later than wall − BAR_SETTLE_SEC is never read. -> {o, h, l, c, v, session} or None (no such closed bar)."""
    from supply_demand.timeframes import resample_ohlcv
    from . import bars as B
    if raw is None or len(raw) == 0:
        return None
    res = resample_ohlcv(raw, B.RULES["5m"])
    closed = B.closed_only(res, wall) if res is not None else None
    if closed is None or len(closed) == 0:
        return None
    key = B._utc_naive(label_et)
    if key not in closed.index:
        return None
    row = closed.loc[key]
    out = {}
    for short, col in OHLCV:
        val = row.get(col) if col in closed.columns else (0.0 if col == "volume" else None)
        try:
            out[short] = float(val)
        except (TypeError, ValueError):
            return None
        if out[short] != out[short]:                            # NaN
            return None
    out["session"] = str(row.get("session")) if "session" in closed.columns else None
    return out


def _session_part(bar: dict, label_et: datetime) -> str:
    """"regular" for an RTH bucket, else "extended" — the minute loader's own session tag (daytrading.data); an untagged
    frame is tagged by the loader's classifier on the bucket's first minute."""
    s = bar.get("session")
    if not s or s == "None":
        import pandas as pd
        from daytrading.data import _classify_session
        from . import bars as B
        start = B._utc_naive(label_et) - pd.Timedelta(B.RULES["5m"])
        s = _classify_session(start)
    return SESSION_PARTS[0] if s == "rth" else SESSION_PARTS[1]


def _fetch_all(names: list, session: date, label_et: datetime, load_day: Callable, wall: Callable) -> dict:
    """{SYM: bar dict + read_at} for every name whose fetch answered with the closed bar; a raise / None / empty / a
    missing bar = absent (counted by the caller). At most GAJJALA_BAR_FINAL_PROBE_WORKERS at once (the cron pass's own
    ~150-frame fetch runs beside the second read with its own 429 breaker — the probe never crowds it); Massive's
    spelling for the ask."""
    from sepa.symbols import for_massive

    def one(sym: str):
        try:
            raw = load_day(for_massive(sym), session, force=True, include_premarket=True, include_afterhours=True)
            read_at = _utc(wall())
            bar = read_bar(raw, label_et, read_at)
            if bar is None:
                return sym, None
            bar["read_at"] = read_at
            return sym, bar
        except Exception as exc:                                # noqa: BLE001
            log.debug("%s %s fetch failed: %s", LOG_PREFIX, sym, type(exc).__name__)
            return sym, None

    out: dict = {}
    if not names:
        return out
    with ThreadPoolExecutor(max_workers=max(1, min(int(GC.GAJJALA_BAR_FINAL_PROBE_WORKERS), len(names)))) as ex:
        for sym, bar in ex.map(one, names):
            if bar is not None:
                out[sym] = bar
    return out


def compare(at30: dict, at60: dict) -> tuple:
    """(changed, fields_changed, v_delta) — exact compare of o / h / l / c / v (the same provider both times)."""
    fields = [short for short, _col in OHLCV if at30.get(short) != at60.get(short)]
    v_delta = float(at60.get("v") or 0.0) - float(at30.get("v") or 0.0)
    return bool(fields), fields, v_delta


def _sleep_until(when: datetime, sleep: Callable, wall: Callable) -> None:
    left = (_utc(when) - _utc(wall())).total_seconds()
    if left > 0:
        sleep(left)


def probe(target: datetime, *, coll=None, shared=None, load_day: Optional[Callable] = None,
          sleep: Callable = time.sleep, wall: Callable = _wall) -> dict:
    """The finality probe for one target (the caller already slept to it). -> a summary dict. No lease, no pass, no
    push: the only write is gajjala_bar_final."""
    from . import run_1m as R1
    from . import store as ST
    coll = coll if coll is not None else _default_coll()
    label = bar_label(target)
    session = label.date()
    out: dict = {"mode": "probe", "target": _utc(target), "bar_t": label.strftime("%Y-%m-%d %H:%M"),
                 "names": 0, "rows": 0, "failed_at30": 0, "failed_at60": 0, "changed": 0, "late": False}
    if coll is None:
        out["reason"] = "no store"
        return out
    shared = shared if shared is not None else ST.default()
    names, _n_capped = R1.names_for(shared, session)
    names = list(names)[: int(GC.GG1M_MAX_NAMES)]
    out["names"] = len(names)
    load = load_day or _load_default
    first = _fetch_all(names, session, label, load, wall)
    out["failed_at30"] = len(names) - len(first)
    second_at = at60_moment(target)
    _sleep_until(second_at, sleep, wall)
    late_s = (_utc(wall()) - _utc(second_at)).total_seconds()
    late = late_s > float(GC.BAR_CLOSE_LATE_MAX_SEC)            # host sleep: a later read would inflate `changed`
    out["late"] = late
    if late:
        second: dict = {}                                       # no second fetch: the row says late, never changed
        log.info("%s second read %.0f s late — rows marked late", LOG_PREFIX, late_s)
    else:
        second = _fetch_all([s for s in names if s in first], session, label, load, wall)
        out["failed_at60"] = len(first) - len(second)
    if first:
        ensure_index(coll)
    hhmm = label.strftime("%H:%M")
    iso = session.isoformat()
    for sym in names:
        a, b = first.get(sym), second.get(sym)
        if a is None or (b is None and not late):
            continue                                            # a failed fetch = no row, never a retry
        doc = {"date": iso, "symbol": sym, "bar_t": out["bar_t"], "session_part": _session_part(a, label),
               "at30": {k: a[k] for k in ("o", "h", "l", "c", "v", "read_at")}, "late": late}
        if late:
            doc.update({"at60": None, "changed": None, "fields_changed": [], "v_delta": None})
        else:
            changed, fields, v_delta = compare(a, b)
            doc.update({"at60": {k: b[k] for k in ("o", "h", "l", "c", "v", "read_at")}, "changed": changed,
                        "fields_changed": fields, "v_delta": v_delta})
        doc["at"] = _utc(wall())
        try:
            coll.replace_one({"_id": f"{iso}|{hhmm}|{sym}"}, doc, upsert=True)
            out["rows"] += 1
            out["changed"] += int(bool(doc["changed"]))
        except Exception as exc:                                # noqa: BLE001
            log.warning("%s row %s failed: %s", LOG_PREFIX, sym, type(exc).__name__)
    if out["rows"]:
        out["complete"] = mark_complete_if_due(coll, wall)      # the 5th date landed → the marker, once
    return out


# ── the child ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _refuse(out: dict, reason: str) -> dict:
    out["reason"] = reason
    log.info("%s %s", LOG_PREFIX, reason)
    return out


def wait_and_run(now: Optional[datetime] = None, *, sleep: Callable = time.sleep, wall: Callable = _wall,
                 coll=None, shared=None, load_day: Optional[Callable] = None, run_pass: Optional[Callable] = None,
                 store=None, deps=None) -> dict:
    """The child's whole life (run.main --at-bar-close). -> a summary; never raises past a refusal. `now` = the start
    clock (None = the wall clock); every other clock read is `wall()`."""
    start = _utc(now) if now is not None else _utc(wall())
    target = next_target(start)
    m = mode()
    out: dict = {"ran": False, "mode": m, "target": _utc(target)}
    why = refusal(target)
    if why:
        return _refuse(out, why)
    if m == "probe":
        coll = coll if coll is not None else _default_coll()
        if coll is not None and probe_complete(coll, wall):
            return _refuse(out, R_COMPLETE)
        if coll is not None:
            owned = claim_target(coll, target, wall)
            if owned is None:
                return _refuse(out, R_CLAIM_FAILED)
            if not owned:
                return _refuse(out, R_OWNED)                    # a pass that ended after :x5:30 → two children, one read
    _sleep_until(target, sleep, wall)
    late = (_utc(wall()) - _utc(target)).total_seconds()
    if late > float(GC.BAR_CLOSE_LATE_MAX_SEC):
        return _refuse(out, f"{R_LATE} — {late:.0f} s after {_et(target).strftime('%H:%M:%S')} ET "
                            f"(> {GC.BAR_CLOSE_LATE_MAX_SEC} s); the `:x1` pass reads this bar")
    if m == "on":
        from . import run as RUN
        from . import store as ST
        rp = run_pass or RUN.run_pass
        res = rp(None, store=store if store is not None else ST.default(),
                 deps=deps if deps is not None else RUN._cron_deps())
        out.update({"ran": True, "pass": res, "status": (res or {}).get("status"), "reason": (res or {}).get("reason")})
        log.info("%s pass at %s ET: %s", LOG_PREFIX, _et(target).strftime("%H:%M:%S"),
                 {k: (res or {}).get(k) for k in ("ran", "status", "n_read", "wall_s", "lease", "reason")})
        return out
    res = probe(target, coll=coll, shared=shared, load_day=load_day, sleep=sleep, wall=wall)
    out.update({"ran": True, "probe": res})
    log.info("%s probe %s ET: %s", LOG_PREFIX, res.get("bar_t"),
             {k: res.get(k) for k in ("names", "rows", "changed", "late", "failed_at30", "failed_at60", "reason")})
    return out


__all__ = ["MODES", "mode", "next_target", "bar_label", "at60_moment", "refusal", "spawn_child", "read_bar",
           "compare", "probe", "probe_complete", "probe_dates", "marker_present", "mark_complete_if_due", "claim_target", "wait_and_run", "ARGV_CHILD", "PROC_NAME", "COLL"]
