"""🚩 Gajjala's 1-minute page — the GG1 pass (BUILD_SPEC27 §3.6 / WP-B, 2026-10-27).

Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
please." / "do everything and also add the track record for it from today.."

ONE pipeline (variant.py): the same detectors (his five setups, K1–K11), the same A+ claim, the same 🧠 potentials, read
on CLOSED 1-minute bars (the ➖ Fade on 5-minute first), over the SAME list as 🚩 Gajjala's — GG1 never scans. Each
iteration: run.in_window → the GG1 lease (its own `gajjala_1m_state` doc) → the names (GG5's listed names, top change
first, cut to GG1M_MAX_NAMES) → closed 1m + 5m frames (budget GG1M_MINUTE_BUDGET_SEC from the iteration's start; the
prior day's minutes memoised per process) → per name GG5's stored ctx (float, halts, psych … nothing recomputed) + K11 on
`bars.session_volume` (HIS CALL #4) → `detectors.read_all(primary="1m", slow="5m")` → `gajjala_1m_reads` → the A+ gate
(alerts.run_pass) and the 🧠 gate (potential.run_pass), each in its own try, both on the GG1 store (SHADOW:
GAJJALA_1M_PUSH_MODE — recorded, never sent, HIS CALL #1) → the pass doc `"{date}|{HH:MM:SS}"` on `gajjala_1m_passes`
(+ GG5's latest strip / counts / ☀️ / 🌙 copied verbatim with `from_pass`) → the two /alerts rows (cron only) → release.

GG1 NEVER calls the market snapshot, the type map, record_scan, the ah-carry commit, the halts read, floats_for or the 🎾
squeeze history: what it does not compute it reads off GG5's store. It WRITES only `gajjala_1m_*` collections.

CADENCE (§6 the supercronic trap). The 5-minute cron job (`run.main`) SPAWNS `python -m chart_maps.gajjala.run_1m
--loop` as a DETACHED child (new session, no inherited descriptors) and returns at once — supercronic runs without
`-overlapping`, so anything long inside the 🚩 job would make it SKIP the next live 🚩 pass. The loop reads one closed
1-minute bar per iteration: iteration 0 right after GG5's pass, then :30 of each following minute, while
start + GG1M_MINUTE_BUDGET_SEC + GG1M_SLOT_MARGIN_SEC ≤ the next cron tick (≤ 5 per slot) and the bar closes by the
session's extended close (alerts._closes). A straggler that overlaps the next slot is refused by the GG1 lease (a cron
holder), never doubled. `--on-demand` = the owner's on-open iteration (on_demand.request(variant=GG1)): both gates dry,
no /alerts row, its own pass doc `"{date}|{HH:MM:SS}|open"`.

Every number is a constants.py name (the MINE block, 2026-10-27); GG's own constants are never touched. A Cheetah
variant — GG trades these setups on 5-minute bars. UNMEASURED: nothing here trades, sizes or enters a lane.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC
from . import run as RUN
from . import variant as V

log = logging.getLogger("chart_maps.gajjala.run_1m")

ET = ZoneInfo("America/New_York")
ARGV_LOOP = (sys.executable, "-m", "chart_maps.gajjala.run_1m", "--loop")
ARGV_ON_DEMAND = (sys.executable, "-m", "chart_maps.gajjala.run_1m", "--on-demand")
PROC_NAME_LOOP = "gajjala-1m-loop"
LOOP_STATE_ID = "loop"                                 # the GG1 `gajjala_1m_state` doc the loop's end writes
LOOP_REASONS = ("no time left in the slot", "after the extended close", "off", "lease held")
LEASE_HELD = "lease held — another 1-minute iteration is running"
# the GG5 pass doc keys an iteration copies verbatim (the ☀️ / 🌙 subs and the strip serve unchanged) + `from_pass`
G5_COPY_KEYS = ("strip", "counts", "tape_session", "premarket", "postmarket", "ah_carry")
PASS_KEYS = ("n_listed", "n_capped", "n_read", "bars", "alerts", "potential", "status", "errors", "wall_s",
             "bars_through_et", "lease", "on_demand", "slot")


# ── the switch ────────────────────────────────────────────────────────────────────────────────────────────────────
def enabled() -> bool:
    """The kill switch: GC.GAJJALA_1M_ENABLED AND the env GAJJALA_1M_ENABLED is not "0" (read at call time)."""
    return bool(GC.GAJJALA_1M_ENABLED) and os.environ.get("GAJJALA_1M_ENABLED", "1") != "0"


# ── the slot clock ────────────────────────────────────────────────────────────────────────────────────────────────
def _et(now: datetime) -> datetime:
    return RUN._utc(now).astimezone(ET)


def slot_of(now) -> tuple:
    """(tick, next_tick) as ET datetimes: the latest cron tick ≤ `now` on the PASS_MINUTE_OFFSET / PASS_CADENCE_SEC
    grid (the crontab "1-56/5"), and the one after it. Robust to a late start (a tick that fired 58 s late is still
    that tick)."""
    et = _et(now)
    cad_min = max(1, int(GC.PASS_CADENCE_SEC) // 60)
    base = et.replace(second=0, microsecond=0)
    mins = et.hour * 60 + et.minute
    tick = base - timedelta(minutes=(mins - int(GC.PASS_MINUTE_OFFSET)) % cad_min)
    return tick, tick + timedelta(seconds=int(GC.PASS_CADENCE_SEC))


def _floor_minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


def next_start(prev) -> datetime:
    """The next iteration's start: the minute after the bar `prev` read closes, + BAR_SETTLE_SEC —
    floor_minute(prev − BAR_SETTLE_SEC) + GG1M_CADENCE_SEC + BAR_SETTLE_SEC."""
    p = _et(prev)
    return (_floor_minute(p - timedelta(seconds=GC.BAR_SETTLE_SEC)) + timedelta(seconds=GC.GG1M_CADENCE_SEC)
            + timedelta(seconds=GC.BAR_SETTLE_SEC))


def fits(start, next_tick) -> bool:
    """start + GG1M_MINUTE_BUDGET_SEC + GG1M_SLOT_MARGIN_SEC ≤ next_tick — an iteration never runs into the next 🚩
    tick."""
    return (RUN._utc(start) + timedelta(seconds=GC.GG1M_MINUTE_BUDGET_SEC + GC.GG1M_SLOT_MARGIN_SEC)
            <= RUN._utc(next_tick))


def _bar_label(start) -> datetime:
    """The 1-minute bar an iteration starting at `start` reads: the newest label settled by then (ET)."""
    return _floor_minute(_et(start) - timedelta(seconds=GC.BAR_SETTLE_SEC))


def _after_extended_close(start) -> bool:
    from . import alerts as AL
    label = _bar_label(start)
    _rth, ah_close = AL._closes(label.date())
    return label > datetime.combine(label.date(), ah_close, tzinfo=ET)


# ── the names: GG5's listed names, never a scan ───────────────────────────────────────────────────────────────────
def _names(shared, session) -> tuple:
    """(names, n_capped, listed) — see names_for."""
    from . import scanner as SC
    listed = SC.listed_symbols(shared, session)
    iso = session.isoformat() if isinstance(session, (date, datetime)) else str(session)
    change: dict = {}
    for d in shared.scan_docs([session]):
        s = d.get("symbol")
        if s and d.get("date") == iso:
            try:
                change[s] = max(change.get(s, float("-inf")), float(d.get("max_change_pct") or 0.0))
            except (TypeError, ValueError):
                change.setdefault(s, 0.0)
    ordered = sorted(listed, key=lambda s: (0, -change[s], s) if s in change else (1, 0.0, s))
    cap = int(GC.GG1M_MAX_NAMES)
    return ordered[:cap], max(0, len(ordered) - cap), listed


def names_for(shared, session) -> tuple:
    """(names, n_capped): scanner.listed_symbols(shared, session) — today's qualifiers ordered by their scan doc's
    max_change_pct (desc), the carried names after them, symbol ascending on ties — cut to GG1M_MAX_NAMES (HIS CALL #3);
    n_capped = the names past the cut."""
    names, n_capped, _listed = _names(shared, session)
    return names, n_capped


# ── dependencies ──────────────────────────────────────────────────────────────────────────────────────────────────
def _record_status(counts: dict, now: datetime, reason: Optional[str] = None) -> bool:
    from supply_demand import alert_status as AS
    return AS.record_pass(V.GG1.push_kind_setup, counts, now, reason=reason)


def _record_potential_status(counts: dict, now: datetime, reason: Optional[str] = None) -> bool:
    from supply_demand import alert_status as AS
    return AS.record_pass(V.GG1.push_kind_potential, counts, now, reason=reason)


def _wall() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Deps1m:
    load_day: Callable = RUN._load_day             # (sym, day, force=, include_premarket=, include_afterhours=) -> df
    send: Optional[Callable] = None                # A+ (owner, payload) (None = the variant's hook — never called in shadow)
    send_potential: Optional[Callable] = None      # 🧠 (owner, payload) (None = the variant's hook)
    owner: Optional[str] = None
    record_status: Callable = _record_status       # (counts, now, reason) -> bool — the gajjala_1m_setup /alerts row
    record_potential_status: Callable = _record_potential_status
    clock: Callable = time.monotonic               # the budget clock
    wall: Callable = _wall                         # the loop's wall clock (UTC-aware)
    sleep: Callable = time.sleep


# the prior market day's minutes, per process (a loop's second iteration fetches today only)
_PREV_MEMO: dict = {}
_MEMO_LOCK = threading.Lock()


def _memo_prev(load: Callable) -> Callable:
    """`load` with the PRIOR day (any call without force=True) memoised per process; today (force=True) always
    fetched. A None / empty answer is never memoised (the next iteration asks again). Only one day is kept."""
    def fn(sym, day, force=False, include_premarket=True, include_afterhours=False):
        if force:
            return load(sym, day, force=True, include_premarket=include_premarket,
                        include_afterhours=include_afterhours)
        iso = day.isoformat() if isinstance(day, (date, datetime)) else str(day)
        k = (sym, iso, bool(include_premarket), bool(include_afterhours))
        with _MEMO_LOCK:
            if k in _PREV_MEMO:
                return _PREV_MEMO[k]
        df = load(sym, day, force=False, include_premarket=include_premarket, include_afterhours=include_afterhours)
        if df is not None and len(df):
            with _MEMO_LOCK:
                for old in [x for x in _PREV_MEMO if x[1] != iso]:
                    _PREV_MEMO.pop(old, None)
                _PREV_MEMO[k] = df
        return df
    return fn


def dry_deps() -> Deps1m:
    """Every writer and sender a recorder; the minute loader without the cache write (run._dry_load_day)."""
    sent: list = []
    status: list = []
    sent_potential: list = []
    status_potential: list = []
    d = Deps1m(load_day=RUN._dry_load_day,
               send=lambda owner, payload: (sent.append(payload), {"sent": 0, "failed": 0, "total_targets": 0})[1],
               send_potential=lambda owner, payload: (sent_potential.append(payload),
                                                      {"sent": 0, "failed": 0, "total_targets": 0})[1],
               record_status=lambda counts, now, reason=None: (status.append(counts), False)[1],
               record_potential_status=lambda counts, now, reason=None: (status_potential.append(counts), False)[1])
    d.sent, d.status = sent, status                             # type: ignore[attr-defined]
    d.sent_potential, d.status_potential = sent_potential, status_potential   # type: ignore[attr-defined]
    return d


# ── one iteration ─────────────────────────────────────────────────────────────────────────────────────────────────
class _Superseded(Exception):
    """An on-open iteration whose lease a cron iteration took over: nothing more is written."""


def _shared_of(st):
    from . import store as ST
    return getattr(st, "shared", None) or ST.default()


def _bars_through(frames: dict) -> Optional[str]:
    """"HH:MM" — the newest closed PRIMARY (1-minute) bar label any name was read through; None when none."""
    ts = [fr.as_of_primary for fr in (frames or {}).values() if getattr(fr, "as_of_primary", None)]
    return max(ts)[11:16] if ts else None


def _last_close(fr) -> Optional[float]:
    try:
        c = fr.fprimary.c
        return float(c[-1]) if c else None
    except Exception:                                           # noqa: BLE001
        return None


def run_iteration(now: Optional[datetime] = None, *, store=None, deps: Optional[Deps1m] = None, dry: bool = False,
                  on_demand: bool = False, slot: Optional[dict] = None) -> dict:
    """One GG1 iteration (§3.6 order). -> the summary (also the pass doc's body). Never raises past a step: a step that
    breaks is named in `errors` and the iteration still records. `on_demand=True` = the owner's on-open iteration (both
    gates dry, no /alerts row, its own pass doc). `slot` = {"tick", "i"} from the loop (None → this clock's tick)."""
    from . import bars as B
    from . import alerts as AL
    from . import potential as PT
    from . import scanner as SC
    from . import store as ST
    from . import detectors as D
    from . import trader_names as TN

    v = V.GG1
    deps = deps or Deps1m()
    now = RUN._utc(now)
    on_demand = bool(on_demand)
    if on_demand:
        dry = False                                             # an open writes the GG1 store; its gates are dry
    et = now.astimezone(ET)
    session = et.date()
    session_iso = session.isoformat()
    tick = (slot or {}).get("tick") or slot_of(now)[0]
    out: dict = {"ran": False, "session": session_iso, "at_et": et.isoformat(), "dry": bool(dry), "errors": [],
                 "on_demand": on_demand, "variant": v.key,
                 "slot": {"tick": RUN._utc(tick), "i": (slot or {}).get("i")}}
    if not RUN.in_window(now):
        out["reason"] = "outside the pass window"
        return out
    st = store or (RUN.dry_store(ST.for_variant(v)) if dry else ST.for_variant(v))
    shared = _shared_of(st)
    if on_demand:
        claim = st.claim_lease(now, source=ST.LEASE_ON_DEMAND)
    else:
        claim = st.claim_lease(now, source=ST.LEASE_CRON, take_over=True, cron_start=now)
    out["lease"] = {"why": getattr(claim, "why", "claimed" if claim else "held"), "waited_s": 0.0,
                    "held_by": getattr(claim, "held_by", None)}
    if not claim:
        out["reason"] = RUN._ON_DEMAND_REFUSED if on_demand else LEASE_HELD
        return out
    token = getattr(claim, "token", None)
    guard_on = on_demand and not getattr(st, "dry", False)

    def mine() -> None:
        if guard_on and not st.lease_owner_is(token):
            raise _Superseded()

    t0 = deps.clock()
    frames: dict = {}
    g5_pass: dict = {}
    try:
        out["ran"] = True
        try:
            g5_pass = shared.latest_pass() or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala 1m: GG5 pass read failed: %s", type(exc).__name__)
            g5_pass = {}
            out["errors"].append("g5_pass")
        names, n_capped, listed = _names(shared, session)
        out.update({"n_listed": len(listed), "n_capped": n_capped})
        bar_stats: dict = {}
        left = max(0.0, float(GC.GG1M_MINUTE_BUDGET_SEC) - (deps.clock() - t0))
        frames = B.frames_for(names, session, now, load_day=_memo_prev(deps.load_day), budget_sec=left,
                              stats=bar_stats, variant=v)
        today_rows = {d["symbol"]: (d.get("last") or {}) for d in shared.scan_docs([session]) if d.get("symbol")}
        try:                                                    # 📌 adds: the potential hold reads their volume (A2)
            trader_adds = TN.added_symbols(shared.scan_docs(SC._window(session)))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala 1m: trader adds unreadable: %s", type(exc).__name__)
            trader_adds = set()
        reads: dict = {}
        sv: dict = {}
        alert_ctx: dict = {}
        pot_ctx: dict = {}
        for s, fr in frames.items():
            g5 = shared.get_read(session, s) or {}
            ctx = dict(g5.get("ctx") or {})                     # GG5's stored ctx — nothing recomputed
            float_read = ctx.get("float")
            sv[s] = B.session_volume(fr)                        # K11 on the 1-minute page (HIS CALL #4)
            reads[s] = D.read_all(fr.detector_frames(), {"symbol": s, "float_read": float_read,
                                                         D.K11_CTX_KEY: sv[s]}, primary=v.primary, slow=v.slow)
            prior = st.get_read(session, s) or {}
            stopped = dict(prior.get("stopped_today") or {})
            for setup, r in (reads.get(s) or {}).items():
                if (r or {}).get("state") == "stopped" and setup not in stopped:
                    stopped[setup] = r.get("entry_bar_t") or et.isoformat()
            tile: dict = {}
            as_of: dict = {}
            for tf in v.tfs:
                suf = str(V.frame_minutes(tf, v))
                p = B.tile_payload(fr, tf, max_bars=GC.GG1M_TILE_BARS_MAX)
                tile.update({f"bars{suf}": p["bars"], f"curves{suf}": p["curves"], f"vol_avg{suf}": p["vol_avg"]})
                as_of[f"as_of_bar_t{suf}"] = fr.as_of_bar_t.get(tf)
            mine()
            st.upsert_read(session, s, dict(as_of, setups=reads.get(s) or {}, ctx=ctx, tile=tile,
                                            listed=listed.get(s), stopped_today=stopped), now=now)
            alert_ctx[s] = {"float_text": (float_read or {}).get("text"), "price": _last_close(fr),
                            "last_halt_resume_et": ctx.get("last_halt_resume_et"),
                            "reg_gain_pct": ctx.get("reg_gain_pct")}
            if ctx.get("trader"):
                alert_ctx[s].update(trader=ctx["trader"], trader_text=ctx.get("trader_text"))
            pot_ctx[s] = ctx

        push_dry = bool(dry or on_demand)
        al_failed = False
        try:
            alerts = AL.run_pass(reads, frames, now, session, store=st, send=deps.send, owner=deps.owner,
                                 dry=push_dry, ctx=alert_ctx)
        except Exception:                                       # noqa: BLE001 — never silences the 🧠 gate
            log.exception("gajjala 1m: the A+ gate failed")
            alerts, al_failed = {}, True
            out["errors"].append("alerts")
        out.update({"n_read": len(reads), "bars": bar_stats, "alerts": alerts,
                    "status": "error" if al_failed else "ok", "bars_through_et": _bars_through(frames),
                    "aplus": sorted(f"{s}:{k}" for s, rs in reads.items() for k, r in rs.items()
                                    if (r or {}).get("state") == "aplus")})
        try:
            out["potential"] = PT.run_pass(reads, frames, now, session, store=st, ctx=pot_ctx, rows=today_rows,
                                           send=deps.send_potential, owner=deps.owner, dry=push_dry,
                                           tape=g5_pass.get("tape_session"), live_rows={},
                                           trader_hold={s: sv.get(s) for s in trader_adds if s in frames})
        except Exception:                                       # noqa: BLE001
            log.exception("gajjala 1m: the potential gate failed")
            out["errors"].append("potential")
            out["potential"] = {}
        if on_demand:
            mine()
    except _Superseded:
        out["superseded"] = 1
        out["status"] = "superseded"
        out["reason"] = RUN._SUPERSEDED
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala 1m iteration failed")
        out["errors"].append(type(exc).__name__)
        out["status"] = "error"
    finally:
        out["wall_s"] = round(deps.clock() - t0, 3)
        _finish(st, now, session, out, deps, g5_pass, on_demand=on_demand, token=token)
    if getattr(st, "dry", False):
        out["writes"] = list(getattr(st, "writes", []) or [])
        out["sent"] = list(getattr(deps, "sent", []) or []) + list(getattr(deps, "sent_potential", []) or [])
    return out


def _finish(st, now: datetime, session: date, out: dict, deps: Deps1m, g5_pass: dict, *, on_demand: bool,
            token: Optional[str]) -> None:
    """The GG1 pass doc, the two /alerts rows (cron only), the release — each best-effort."""
    from . import store as ST
    if (on_demand and not out.get("superseded") and not getattr(st, "dry", False)
            and not st.lease_owner_is(token)):
        out["superseded"] = 1
        out["status"] = "superseded"
        out["reason"] = RUN._SUPERSEDED
    if out.get("superseded"):
        try:
            st.release_lease(now, token)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala 1m: lease release failed: %s", exc)
        return
    body = {k: out.get(k) for k in PASS_KEYS}
    body.update({k: (g5_pass or {}).get(k) for k in G5_COPY_KEYS})
    body["from_pass"] = (g5_pass or {}).get("pass_id")
    body["finished_at"] = now + timedelta(seconds=float(out.get("wall_s") or 0))
    hms = now.astimezone(ET).strftime("%H:%M:%S")
    try:
        if on_demand:
            st.record_pass(session, now, body, hhmm=hms + "|" + ST.ON_DEMAND_PASS_SUFFIX, source=ST.LEASE_ON_DEMAND,
                           latest_if_newer=True, move_latest=bool(out.get("n_read")))
        else:
            st.record_pass(session, now, body, hhmm=hms)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 1m: pass doc failed: %s", exc)
    if not on_demand:
        counts = dict(out.get("alerts") or {})
        counts.update({"candidates": out.get("n_read") or 0, "listed": out.get("n_listed") or 0})
        errs = out.get("errors") or []
        reason = None if out.get("status") == "ok" else "pass error: " + ", ".join(errs)
        try:
            deps.record_status(counts, now, reason)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala 1m: /alerts row failed: %s", exc)
        if "potential" in errs:
            pot_reason = "pass error: potential"
        elif "potential" in out:
            pot_reason = None
        else:
            pot_reason = reason
        try:
            deps.record_potential_status(dict(out.get("potential") or {}), now, pot_reason)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala 1m: /alerts potential row failed: %s", exc)
    try:
        st.release_lease(now, token)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 1m: lease release failed: %s", exc)


def run_on_demand(now: Optional[datetime] = None, *, store=None, deps: Optional[Deps1m] = None) -> dict:
    """The owner's on-open GG1 iteration (on_demand.request(variant=GG1) spawns `run_1m --on-demand`): both gates dry,
    no /alerts row, the pass doc `"{date}|{HH:MM:SS}|open"`; its lease claim needs only "not held"."""
    return run_iteration(now, store=store, deps=deps, on_demand=True)


# ── the loop (a DETACHED child of the 5-minute cron job) ──────────────────────────────────────────────────────────
def _end(st, tick, n: int, reason: str, ended_at) -> None:
    try:
        st.set_state(LOOP_STATE_ID, {"tick": RUN._utc(tick), "n": int(n), "reason": reason,
                                     "ended_at": RUN._utc(ended_at)})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 1m loop: state write failed: %s", exc)


def loop(now: Optional[datetime] = None, *, store=None, deps: Optional[Deps1m] = None) -> dict:
    """One slot's iterations: while `fits(start, next_tick)` and the bar to read closes by the extended close — sleep
    to `start`, one iteration, `start = max(wall, next_start(start))`. Ends with the GG1 state doc "loop" {tick, n,
    reason, ended_at}. -> {tick, n, reason, iterations}."""
    from . import store as ST
    deps = deps or Deps1m()
    start = RUN._utc(now) if now is not None else RUN._utc(deps.wall())
    tick, next_tick = slot_of(start)
    out: dict = {"tick": tick.isoformat(), "n": 0, "reason": None, "iterations": []}
    st = store or ST.for_variant(V.GG1)
    if not enabled():
        out["reason"] = "off"
        _end(st, tick, 0, out["reason"], deps.wall())
        return out
    i = 0
    while True:
        if not fits(start, next_tick):
            out["reason"] = "no time left in the slot"
            break
        if _after_extended_close(start):
            out["reason"] = "after the extended close"
            break
        delay = (start - RUN._utc(deps.wall())).total_seconds()
        if delay > 0:
            deps.sleep(delay)
        wall = RUN._utc(deps.wall())
        res = run_iteration(max(wall, start), store=st, deps=deps, slot={"tick": tick, "i": i})
        out["iterations"].append({k: res.get(k) for k in ("at_et", "ran", "status", "reason", "n_read", "wall_s")})
        if not res.get("ran") and str(res.get("reason") or "").startswith("lease held"):
            out["reason"] = "lease held"
            break
        i += 1
        start = max(RUN._utc(deps.wall()), next_start(start))
    out["n"] = i
    _end(st, tick, i, out["reason"], deps.wall())
    log.info("gajjala 1m loop: tick %s — %d iteration(s), %s", tick.strftime("%H:%M"), i, out["reason"])
    return out


def _popen(argv: list, name: str):
    """The real spawn: a NEW session, no inherited descriptors — stdin from /dev/null and stdout / stderr to the
    container's PID 1 (its docker log) when writable, else /dev/null: the cron job's own pipes are never held open by
    the child, so supercronic sees the 🚩 job end when run.main returns (§6)."""
    from .on_demand import _BACKEND_DIR
    sink = None
    try:
        sink = open("/proc/1/fd/1", "ab", buffering=0)          # noqa: SIM115 — closed right after the spawn
    except OSError:
        sink = None
    try:
        out = sink if sink is not None else subprocess.DEVNULL
        proc = subprocess.Popen(list(argv), cwd=_BACKEND_DIR, start_new_session=True, close_fds=True,
                                stdin=subprocess.DEVNULL, stdout=out, stderr=out)
    finally:
        if sink is not None:
            sink.close()
    return proc


def spawn_loop(spawn: Optional[Callable] = None) -> bool:
    """Start `python -m chart_maps.gajjala.run_1m --loop` DETACHED (`spawn(argv, name)`, default the real Popen with
    start_new_session=True, close_fds=True). True when started; never raises (False)."""
    try:
        proc = (spawn or _popen)(list(ARGV_LOOP), PROC_NAME_LOOP)
        log.debug("gajjala 1m loop: %s pid %s", PROC_NAME_LOOP, getattr(proc, "pid", None))   # run.main logs the line
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala 1m loop: spawn raised %s", type(exc).__name__)
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.gajjala.run_1m", description=__doc__.split("\n")[0])
    ap.add_argument("--loop", action="store_true", help="the slot's iterations (run.main spawns this, detached)")
    ap.add_argument("--on-demand", action="store_true", help="the owner's on-open iteration (both gates dry)")
    ap.add_argument("--dry-run", action="store_true", help="one iteration; record every write and send; touch nothing")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    ap.add_argument("--now", help="ISO clock to replay (a naive stamp is ET)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ET)                            # a naive --now is ET (the house rule), never UTC
    if not args.dry_run and not enabled():
        log.info("gajjala 1m: off (GAJJALA_1M_ENABLED) — nothing to do")
        return 0
    if not RUN.in_window(RUN._utc(now)):
        log.info("gajjala 1m: outside %s–%s ET on a market day — nothing to do", GC.PASS_OPEN_ET, GC.PASS_CLOSE_ET)
        return 0
    if args.now and not args.dry_run and not args.on_demand:
        log.warning("gajjala 1m: a --now replay records on the real store unless --dry-run; refusing")
        return 2
    from . import store as ST
    if args.dry_run:
        deps = dry_deps()
        st = RUN.dry_store(ST.for_variant(V.GG1))
        out = run_iteration(now, store=st, deps=deps, dry=True, on_demand=args.on_demand)   # + writes / sent
    else:
        st = ST.for_variant(V.GG1)
        st.ensure_indexes()
        if args.on_demand:
            out = run_on_demand(now, store=st, deps=Deps1m())
        elif args.loop:
            out = loop(now, store=st, deps=Deps1m())
        else:
            out = run_iteration(now, store=st, deps=Deps1m())
    if args.json:
        print(json.dumps(out, default=str))
    elif not args.loop:
        log.info("gajjala 1m: %s", {k: out.get(k) for k in ("ran", "status", "n_listed", "n_capped", "n_read", "bars",
                                                            "wall_s", "lease", "reason")})
    return 1 if out.get("status") == "error" else 0


__all__ = ["enabled", "slot_of", "next_start", "fits", "names_for", "Deps1m", "run_iteration", "loop", "spawn_loop",
           "run_on_demand", "main", "ARGV_LOOP", "ARGV_ON_DEMAND"]


if __name__ == "__main__":
    sys.exit(main())
