"""🔄 Scan on OPEN — Ajay 2026-10-15 (verbatim): "When ever I open Gajjala's intiate a new scan of stocks.  In that
moment and if there are any enterable stocks on the top which I see in potential i guess". DECISIONS5 K2 / K4, C1–C7;
BUILD_SPEC5 §3.4; AMENDMENTS5 A1 / A5 / A12.

POST /chart-maps/gajjala/scan → `request()`: answers at once (started | reused | waiting | closed | refused) and, on
"started", ONE pass runs in a SUBPROCESS (`python -m chart_maps.gajjala.run --on-demand`, the cron's own entry) — the
api process does no pass work: it never imports or calls the pass, it reads Mongo (the pass doc, the lease) and spawns.
That pass runs BOTH push gates dry, so an open rings no device (K2). One child per api process (the module lock + the
child's `poll()`); the Mongo lease keeps it one pass across processes. The board then re-reads the existing GET until
`pass.at` moves.

Order of `request()` (every step soft; it never raises; no pass runs in it):
  1. closed — a closed day (market_hours.gate.closed_reason) or outside the pass window (run.in_window): no child, no
     lease read (C6);
  2. waiting — this process's child is still alive (two opens within a second → ONE child);
  3. waiting — the pass lease is held (a cron or an on-open pass is in flight: K4 waits for it, never a second one);
  4. waiting — the session's first 5-minute pass has not landed yet (A12: the cron tick does the type map once). The
     gate reads the "latest_cron" pointer ONLY — never the `latest` fallback the banner keeps: only a cron of this
     image writes that pointer, and only a cron of this image waits for an open's lease; a cron of the old image
     reads an open's lease as held and skips its tick (final critic 2026-10-16), so no pointer → no spawn;
  5. reused — the latest pass finished under ON_DEMAND_REUSE_SEC ago (Ajay K4), or a scan on open released the lease
     under that long ago (an open that re-read nothing leaves `latest` alone — A13 — yet still counts; final critic
     2026-10-16, W11b);
  6. started — the child is spawned (a spawn that raises → refused).
No number is typed here (constants.py). UNMEASURED — nothing here trades.

🚩 The 1-minute page (2026-10-27, BUILD_SPEC27 §3.6 — Ajay "do the same logic of Gajjalas but on 1 min candles"):
`request(variant=GG1)` runs the SAME order on the GG1 store (`store.for_variant(GG1)` — its own lease, pass docs and
"latest_cron" pointer), spawns `python -m chart_maps.gajjala.run_1m --on-demand` (PROC_NAME_1M) in its OWN child slot
(a live 🚩 child never makes the 1-minute page "waiting", and back), and words its texts on the variant's cadence
(variant.cadence_sec — "the 1-minute pass …"). A GG5 call (no variant) answers byte for byte as before.

2026-11-11 — `profile`: another package's pass driven through THIS order (Ajay 2026-11-11 asked for an on-demand scan
button on another champion's tab "too" — "too" = this module's button; his words verbatim live in the caller). A
frozen `Profile` names what differs: the child's argv and log name, the closed check, a kill-switch refusal checked
right after it, ONE extra gate after the reuse check (it may answer waiting, with or without a poll plan), and the
package's own words. The order itself — closed → own child alive → lease held → no cron pass this session → reused
→ spawned — stays ONE, here. `profile=None` (every 🚩 / 1-minute / audited call) runs the statements above byte for
byte; the answers are pinned against literals captured before this parameter landed
(tests/test_*_scan_now_2026_11_11.py). No number is typed for it.
"""
from __future__ import annotations

import logging
import math
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC
from . import variant as V

log = logging.getLogger("chart_maps.gajjala.on_demand")

ET = ZoneInfo("America/New_York")
_LOCK = threading.Lock()
_STATE: dict = {"proc": None, "started_at": None}
PROC_NAME = "gajjala-on-open"
PROC_NAME_1M = "gajjala-1m-on-open"                                # 2026-10-27 — the 1-minute page's on-open child
_STATES: dict = {}                                                  # 2026-10-27 — {variant key: {proc, started_at}} (non-GG5)
# the directory that holds the `chart_maps` package (the api's /app) — the child's cwd, so `-m` resolves the same tree
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARGV = (sys.executable, "-m", "chart_maps.gajjala.run", "--on-demand")
RESPONSE_KEYS = ("state", "latest_at", "eta_sec", "poll_sec", "wait_max_sec", "text")
STATES = ("started", "reused", "waiting", "closed", "refused")
HOLDERS = ("cron", "on_demand")                                    # = store.LEASE_SOURCES (strings, not numbers)


@dataclass(frozen=True)
class Profile:
    """A pass of another package driven through THIS module's order (2026-11-11): its child, its closed check, its
    kill switch, one extra gate after the reuse check, and its own words. None = this module's passes, byte for byte.
    `gate` answers None (go on to the spawn) or {"state", "why", "when", "eta", "plan"} — `plan` False = a waiting
    answer with NO poll plan (eta / poll / wait_max None: the board does not poll for it)."""
    argv: tuple                                   # the child's argv (python -m <pkg>.run --on-demand)
    proc_name: str                                # the child's log name
    closed: Callable                              # (now) -> bool — replaces _closed
    text: Callable                                # (state, latest, now, **kw) -> str — replaces _text
    refusal: Optional[Callable] = None            # (now) -> Optional[str why] — checked right after `closed`
    gate: Optional[Callable] = None               # (now, st, latest, cron) -> Optional[dict] — after reuse, before spawn


def _spawn(argv: list, name: str):
    """Start the on-open pass as its own process (A1): a new session (an api restart never signals it), no inherited
    descriptors, stdout / stderr INHERITED (its one log line lands in the api's docker log). -> the Popen."""
    proc = subprocess.Popen(list(argv), cwd=_BACKEND_DIR, start_new_session=True, close_fds=True)
    log.info("gajjala on-open: spawned %s (pid %s)", name, getattr(proc, "pid", None))
    return proc


def _alive(proc) -> bool:
    if proc is None:
        return False
    try:
        return proc.poll() is None                                  # poll() also reaps a finished child
    except Exception:                                               # noqa: BLE001
        return False


def _utc(v):
    from . import store as ST
    return ST._utc(v)


def _stamp(v) -> Optional[datetime]:
    """A stamp read back from Mongo → UTC-aware through store._utc (naive = UTC, A5); not a datetime → None."""
    return _utc(v) if isinstance(v, datetime) else None


def _finite(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _finished_at(latest: Optional[dict]) -> Optional[datetime]:
    """When the latest pass finished (A5: every stamp through store._utc): its `finished_at`, else `at` + `wall_s`,
    else `at`. None when there is no pass doc or no stamp."""
    if not isinstance(latest, dict):
        return None
    fin = _stamp(latest.get("finished_at"))
    if fin is not None:
        return fin
    at = _stamp(latest.get("at"))
    if at is None:
        return None
    wall = _finite(latest.get("wall_s"))
    return at + timedelta(seconds=wall) if wall is not None and wall > 0 else at


def _cron_pass(st) -> Optional[dict]:
    """The A12 gate's CRON pass: the "latest_cron" pointer ONLY (store.latest_cron_pass) — no fallback to `latest`.
    The pointer is written only by the cron code that waits for an open (run._claim); a cron of the old image writes
    `latest` alone and its claim reads an open's lease as "held" and skips the tick, so an open never spawns until a
    cron that waits has run (final critic 2026-10-16). The banner keeps its own fallback (tab._cron_ref). A read that
    raises → None (waiting)."""
    fn = getattr(st, "latest_cron_pass", None)
    if not callable(fn):
        return None
    try:
        lc = fn()
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala on-open: cron pass read failed: %s", exc)
        return None
    return lc if isinstance(lc, dict) else None


def _hms(t: Optional[datetime]) -> Optional[str]:
    return t.astimezone(ET).strftime("%H:%M:%S") if isinstance(t, datetime) else None


def _slot(v) -> dict:
    """The variant's child slot: GG5 → the module's `_STATE` (read at call time); another variant → its own."""
    if V.is_gg5(v):
        return _STATE
    return _STATES.setdefault(v.key, {"proc": None, "started_at": None})


def _argv(v) -> tuple:
    """(argv, name) the variant's on-open child runs: GG5 `run --on-demand`; GG1 `run_1m --on-demand`."""
    if V.is_gg5(v):
        return ARGV, PROC_NAME
    from . import run_1m as R1                                      # ARGV only — the pass never runs here
    return R1.ARGV_ON_DEMAND, PROC_NAME_1M


def _ticks(now: datetime, cadence_sec: Optional[int] = None) -> tuple:
    """(first, next) cron tick of `now`'s ET day as ET datetimes: PASS_OPEN_ET + PASS_MINUTE_OFFSET, then every
    PASS_CADENCE_SEC (the crontab step, pinned by the run tests). `cadence_sec` (2026-10-27): the variant's cadence
    (None = PASS_CADENCE_SEC at call time)."""
    cad = GC.PASS_CADENCE_SEC if cadence_sec is None else cadence_sec
    et = now.astimezone(ET)
    h, m = (int(x) for x in GC.PASS_OPEN_ET.split(":"))
    first = et.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(minutes=GC.PASS_MINUTE_OFFSET)
    if et <= first:
        return first, first
    steps = math.ceil((et - first).total_seconds() / cad)
    return first, first + timedelta(seconds=cad * steps)


def _clamp_eta(sec: float) -> int:
    return int(max(GC.ON_DEMAND_POLL_SEC, min(GC.ON_DEMAND_WAIT_MAX_SEC, math.ceil(sec))))


def _text(state: str, latest: Optional[dict], now: datetime, *, holder=None, started=None, age=None,
          first_wait=None, via_open: bool = False, variant=None) -> str:
    """W10–W14 (BUILD_SPEC5 §3.7) + W12c (A12) + W11b (final critic 2026-10-16: reused on an open's release).
    2026-10-27: the cadence word is the variant's (V.cadence_sec — GG5 = PASS_CADENCE_SEC at call time)."""
    cad = V.cadence_sec(variant) // 60
    at = _stamp((latest or {}).get("at")) if isinstance(latest, dict) else None
    hhmm = at.astimezone(ET).strftime("%H:%M") if at is not None else None
    if state == "started":
        return f"🔄 scanning on open — started {_hms(started or now)} ET; the board below stays until it lands"   # W10
    if state == "reused" and via_open:
        return (f"🔄 a scan on open finished {int(age or 0)} s ago — reused (a pass under "
                f"{GC.ON_DEMAND_REUSE_SEC} s old is not re-run)")                                                 # W11b
    if state == "reused":
        return (f"🔄 the {hhmm} ET pass finished {int(age or 0)} s ago — reused (a pass under "
                f"{GC.ON_DEMAND_REUSE_SEC} s old is not re-run)")                                                 # W11
    if state == "waiting" and first_wait is not None:
        first, nxt = first_wait
        if now.astimezone(ET) <= first:
            return (f"🔄 the first {cad}-minute pass of the session runs at {first.strftime('%H:%M')} ET — showing it "
                    "when it lands")                                                                              # W12c
        return (f"🔄 no {cad}-minute pass has landed this session yet — the next runs at {nxt.strftime('%H:%M')} ET; "
                "showing it when it lands")                                                                       # W12c
    if state == "waiting":
        when = f" at {_hms(started)} ET" if started is not None else ""
        if holder == "on_demand":
            return f"🔄 a pass started on open{when} is still running — showing it when it lands"                   # W12
        return f"🔄 the {cad}-minute pass started{when} is still running — showing it when it lands"               # W12
    if state == "closed":
        return (f"market closed — no scan on open; last pass {hhmm} ET {at.astimezone(ET).date().isoformat()}"
                if at is not None else "market closed — no scan on open; no pass on file")                        # W13
    return "🔄 the scan could not start (store error) — the board shows the last pass"                               # W14


def _resp(state: str, latest: Optional[dict], now: datetime, *, holder=None, started=None, age=None,
          eta: Optional[int] = None, first_wait=None, via_open: bool = False, variant=None, why=None, when=None,
          profile: Optional[Profile] = None, plan: bool = True) -> dict:
    """EXACTLY RESPONSE_KEYS. `latest_at` = tab.pass_stamp(latest) — the SAME stamp the GET serves as `pass.at`.
    started / waiting carry the poll plan (eta clamped to [ON_DEMAND_POLL_SEC, ON_DEMAND_WAIT_MAX_SEC]: the last
    pass's wall time minus the time it has run, else the on-open budget); reused / closed / refused carry none.
    2026-11-11: a `profile` words the answer (`why` / `when` are its gate's); `plan=False` (only ever a profile gate's)
    leaves a waiting answer with no poll plan."""
    from . import tab as GT
    out = {"state": state, "latest_at": GT.pass_stamp(latest), "eta_sec": None, "poll_sec": None,
           "wait_max_sec": None,
           "text": (_text(state, latest, now, holder=holder, started=started, age=age, first_wait=first_wait,
                          via_open=via_open, variant=variant) if profile is None else
                    profile.text(state, latest, now, holder=holder, started=started, age=age, first_wait=first_wait,
                                 via_open=via_open, why=why, when=when))}
    if state in ("started", "waiting") and plan:
        if eta is None:
            prev = _finite((latest or {}).get("wall_s")) if isinstance(latest, dict) else None
            prev = prev if prev is not None and prev > 0 else GC.ON_DEMAND_BUDGET_SEC
            elapsed = max(0.0, (now - started).total_seconds()) if isinstance(started, datetime) else 0.0
            eta = _clamp_eta(prev - elapsed)
        out.update({"eta_sec": int(eta), "poll_sec": GC.ON_DEMAND_POLL_SEC,
                    "wait_max_sec": GC.ON_DEMAND_WAIT_MAX_SEC})
    return out


def _closed(now: datetime) -> bool:
    from market_hours.gate import closed_reason
    from . import run as RUN                                        # in_window only — the pass never runs here
    try:
        if closed_reason(now.astimezone(ET)) is not None:
            return True
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala on-open: closed-day check failed: %s", exc)
        return True
    return not RUN.in_window(now)


def request(now: Optional[datetime] = None, *, store=None, spawn: Optional[Callable] = None, variant=None,
            profile: Optional[Profile] = None) -> dict:
    """CONTRACT — the POST's answer (see the module docstring for the order). `store` / `spawn` are injectable (tests);
    `spawn(argv, name)` returns a process-like object with `poll()`. Never raises. `variant` (2026-10-27): None / GG5 =
    today's tab, byte for byte; GG1 = the 1-minute page (its store, child, argv and cadence words). `profile`
    (2026-11-11): another package's pass — its closed check, its refusal right after, its gate after the reuse check,
    its child and its words; the caller hands its own `store` and `variant` (the child slot). None = as before."""
    v = V.of(variant)
    gg5 = V.is_gg5(v)
    rv = None if gg5 else v                                         # GG5's _resp / _text calls stay as they were
    try:
        from . import store as ST
        st = store if store is not None else (ST.default() if gg5 else ST.for_variant(v))
        slot = _slot(v)
        now = _utc(now)
        try:
            latest = st.latest_pass()
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala on-open: latest pass read failed: %s", exc)
            latest = None
        latest = latest if isinstance(latest, dict) else None
        if (_closed(now) if profile is None else profile.closed(now)):
            return _resp("closed", latest, now, variant=rv, profile=profile)
        if profile is not None and profile.refusal is not None:
            why = profile.refusal(now)
            if why:
                return _resp("refused", latest, now, variant=rv, why=why, profile=profile)
        with _LOCK:
            if _alive(slot.get("proc")):
                started = slot.get("started_at")
                return _resp("waiting", latest, now, holder="on_demand", started=started, variant=rv,
                             profile=profile)
            try:
                lease = st.lease_state(now) or {}
            except Exception as exc:                                # noqa: BLE001
                log.warning("gajjala on-open: lease read failed: %s", exc)
                lease = {}
            if lease.get("held"):
                started = _stamp(lease.get("holder_started_at")) or _stamp(lease.get("claimed_at"))
                holder = lease.get("held_by") if lease.get("held_by") in HOLDERS else "cron"
                return _resp("waiting", latest, now, holder=holder, started=started, variant=rv, profile=profile)
            cron = _cron_pass(st)
            session = now.astimezone(ET).date().isoformat()
            if not (isinstance(cron, dict) and cron.get("date") == session):
                first, nxt = _ticks(now) if gg5 else _ticks(now, V.cadence_sec(v))   # A12: the 04:01 tick first
                return _resp("waiting", latest, now, eta=_clamp_eta((nxt - now).total_seconds()),
                             first_wait=(first, nxt), variant=rv, profile=profile)
            fin = _finished_at(latest)
            od_done = None                                          # final critic 2026-10-16: an open that re-read
            if lease.get("held_by") == "on_demand" and lease.get("status") == "done":   # nothing left `latest` alone
                od_done = _stamp(lease.get("done_at"))              # (A13) — its release still counts for K4's reuse,
            ref = max([x for x in (fin, od_done) if x is not None], default=None)       # else every open re-spawns
            if ref is not None:
                age = max(0.0, (now - ref).total_seconds())         # a negative age reads 0
                if age < GC.ON_DEMAND_REUSE_SEC:
                    return _resp("reused", latest, now, age=age, via_open=(od_done is not None and ref == od_done
                                                                              and (fin is None or od_done > fin)),
                                 variant=rv, profile=profile)
            if profile is not None and profile.gate is not None:
                g = profile.gate(now, st, latest, cron)             # 2026-11-11 — the profile's own gate
                if isinstance(g, dict):
                    return _resp(g.get("state") or "waiting", latest, now, eta=g.get("eta"), why=g.get("why"),
                                 when=g.get("when"), plan=bool(g.get("plan", True)), variant=rv, profile=profile)
            try:
                argv, name = _argv(v) if profile is None else (profile.argv, profile.proc_name)
                proc = (spawn or _spawn)(list(argv), name)
            except Exception as exc:                                # noqa: BLE001
                log.warning("gajjala on-open: spawn failed: %s", exc)
                return _resp("refused", latest, now, variant=rv, profile=profile)
            slot.update(proc=proc, started_at=now)
        return _resp("started", latest, now, started=now, variant=rv, profile=profile)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala on-open: request failed: %s", exc)
        try:
            return _resp("refused", None, _utc(None), variant=rv, profile=profile)
        except Exception:                                           # noqa: BLE001
            return {"state": "refused", "latest_at": None, "eta_sec": None, "poll_sec": None, "wait_max_sec": None,
                    "text": "🔄 the scan could not start (store error) — the board shows the last pass"}


__all__ = ["request", "Profile", "RESPONSE_KEYS", "STATES", "PROC_NAME", "PROC_NAME_1M", "ARGV"]
