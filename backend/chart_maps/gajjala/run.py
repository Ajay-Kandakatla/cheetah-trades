"""The 5-minute Gajjala pass — `python -m market_hours.gate chart_maps.gajjala.run` (BUILD_SPEC §3.10 / WP4, 2026-10-13).

ONE pass, every 5 minutes 04:01–20:01 ET on trading days (minute 1, so the bucket that closed at :00 / :05 has settled):
  window → lease → ONE whole-market Massive snapshot → his scanner (scanner.scan_rows) → split hold-out for the names new
  this session → `gajjala_scan` → after-hours: the ☀️ carry set REPLACED (only on a good snapshot) → today's halts into
  the ledger → the listed set (today + STAY_LISTED_SESSIONS carry) → float chain steps 1–2 (cache, Massive) → 🎾 squeeze
  history for new names (bounded) → closed 5/15-minute frames (budgeted) → the five detectors → the paced Yahoo float
  refinement (🎾-alive names first) and a 🎾 re-read for every float that changed → ☀️ premarket levels / 🌙 K10 confirm
  (rotation) → `gajjala_reads` → the push gate (alerts.run_pass: SHADOW until Ajay flips GAJJALA_PUSH_MODE) → 🧠 potentials
  (potential.run_pass: the tracker + the LIVE gajjala_potential push) → the pass doc + the /alerts rows
  (supply_demand.alert_status, kinds gajjala_setup and gajjala_potential) → lease released.

🧠 2026-10-15 (Ajay: "Give me an alert all continous tracker on these specifically when I get alert I will jump on to
ride the wave"). The potential gate rides THIS pass — no crontab line of its own (a deploy never ships the crontab). The
A+ gate and the potential gate each run in their own try (AMENDMENTS4 D1): one raising never silences the other, and
each /alerts row carries its own reason. The pass runs 04:01–20:01; the potential window is 04:00–20:00 ET with
09:30–09:45 muted (potential.window_reason) — so the ringing passes are 04:01 … 19:56 minus the three muted ones.

The module refuses to run outside PASS_OPEN_ET–PASS_CLOSE_ET on a market day (exit 0, no snapshot call): the crontab hour
field 4-20 also fires 20:06–20:56, and those ticks must do nothing.

`--dry-run` (an agent's probe from a THROWAWAY container): every writer is a recorder — the store's collections are read
through and every write is captured, the sender and the /alerts row are recorders, the minute loader fetches without the
1-minute cache write, the float chain reads the cache and Massive only (no Yahoo, no 429 marker). Nothing reaches Mongo or
a phone. `--json` prints the pass summary; `--now ISO` replays a clock (a naive stamp is ET, the house rule);
`--symbols A,B` narrows the names read (in a dry run they are read even when not listed — a hand check).

🔄 2026-10-15 — the on-open pass (Ajay: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if
there are any enterable stocks on the top which I see in potential i guess"; DECISIONS5 K2/K4, C1–C7, AMENDMENTS5).
`--on-demand` runs `run_on_demand` = run_pass(on_demand=True): the api spawns it as a SUBPROCESS (A1 — never a thread in
the api; this module is the cron's own entry). The real store, the short bar budget ON_DEMAND_BUDGET_SEC, no Yahoo
float refinement, BOTH push gates dry — an open never rings a device, claims nothing, writes no tracker doc and no
/alerts row (K2) — and its own pass doc `"{date}|{HH:MM:SS}|open"` (`on_demand: True`) that moves "latest" (never
backwards, never when it re-read no name — A13) and never "latest_cron" (A10). The lease is split (store.py): the cron
min gap counts cron starts only, stamped with the TICK clock (A6); an on-open claim needs only "not held"; a cron tick
that finds an on-open pass holding the lease waits (ON_DEMAND_POLL_SEC polls, at most CRON_WAIT_ON_DEMAND_SEC) and then
takes it over — an open never makes a cron tick skip or refuse (C1). A taken-over on-open pass checks its token before
every write of its tail and stops writing (status "superseded", exit 0 — A8). Closed bars only: an open between two
passes reads the same closed bars; it adds the fresh snapshot (new scanner names), never a newer bar (C3).

Every dependency is injected (`Deps`), so the tests run the real scanner, bars and detectors on fixture rows. UNMEASURED:
nothing here trades, sizes or enters a lane.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from types import SimpleNamespace
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.run")

ET = ZoneInfo("America/New_York")


# ── the clock ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _utc(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def in_window(now: datetime) -> bool:
    """PASS_OPEN_ET ≤ now ≤ PASS_CLOSE_ET (ET) on a market day (the house calendar)."""
    from catalysts.medical.reaction import is_market_day
    et = _utc(now).astimezone(ET)
    t = et.time().replace(second=0, microsecond=0)
    return (is_market_day(et.date()) and dtime.fromisoformat(GC.PASS_OPEN_ET) <= t
            <= dtime.fromisoformat(GC.PASS_CLOSE_ET))


# ── dependencies (real by default; the tests and --dry-run replace them) ──────────────────────────────────────────
def _snapshot():
    from sepa import prices
    return prices.market_snapshot_with_meta(include_otc=GC.SCAN_INCLUDE_OTC)


def _load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
    from daytrading.data import load_intraday
    return load_intraday(sym, day, force=force, include_premarket=include_premarket,
                         include_afterhours=include_afterhours)


def _dry_load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
    """The minute loader WITHOUT the cache write (`_mongo_put_day` never runs) — a dry run writes nothing."""
    from daytrading.data import _fetch_massive_minute, _filter_sessions
    df = _fetch_massive_minute(sym, day, day)
    if df is None or df.empty:
        return None
    return _filter_sessions(df, include_premarket, include_afterhours)


def _read_all(frames, ctx):
    from . import detectors
    return detectors.read_all(frames, ctx)


def _halts():
    from catalysts.halts import get_today_halts
    return get_today_halts()


def _dry_status_lookup(sym, *, fetch=True):
    """The cache read only — never a Yahoo call, never a 429 marker write."""
    from sepa.volume_movers import shares_status
    return shares_status(sym, fetch=False)


def _record_status(counts: dict, now: datetime, reason: Optional[str] = None) -> bool:
    from supply_demand import alert_status as AS
    return AS.record_pass(AS.GAJJALA_KIND, counts, now, reason=reason)


def _record_potential_status(counts: dict, now: datetime, reason: Optional[str] = None) -> bool:
    """The 🧠 /alerts row — its kind string from constants (no dependency on alert_status's own constant)."""
    from supply_demand import alert_status as AS
    return AS.record_pass(GC.POTENTIAL_PUSH_KIND, counts, now, reason=reason)


@dataclass
class Deps:
    snapshot: Callable = _snapshot                 # () -> (rows, meta)
    load_day: Callable = _load_day                 # (sym, day, force=, include_premarket=, include_afterhours=) -> df
    read_all: Callable = _read_all                 # (frames {"5m","15m"}, ctx) -> {setup: Read}
    halts: Callable = _halts                       # () -> catalysts.halts payload
    status_lookup: Optional[Callable] = None       # float chain step 1 (None = context's default)
    massive_lookup: Optional[Callable] = None      # float chain step 2
    fetch_splits: Optional[Callable] = None        # scanner.hold_out_splits (None = drop10_tab.fetch_splits_strict)
    fetch_types: Optional[Callable] = None         # scanner.ensure_type_map (None = scanner.fetch_type_map)
    daily_loader: Optional[Callable] = None        # 🎾 history (None = prices.closed_daily_frame)
    send: Optional[Callable] = None                # (owner, payload) -> result (None = push.hooks.notify_gajjala_setup)
    owner: Optional[str] = None                    # None = portfolio.alerts._resolve_owner() at send time
    record_status: Callable = _record_status       # (counts, now, reason) -> bool — the /alerts row
    send_potential: Optional[Callable] = None      # 🧠 (owner, payload) -> result (None = push.hooks.notify_gajjala_potential)
    record_potential_status: Callable = _record_potential_status   # 🧠 (counts, now, reason) -> bool — its /alerts row
    sleep: Callable = time.sleep
    refine_floats: bool = True                     # the Yahoo step (off in a dry run)
    clock: Callable = time.monotonic               # the budget clock


# ── the dry-run store: read through, record every write ──────────────────────────────────────────────────────────
class _RecordingColl:
    """A collection that reads through to the real one (or reads nothing) and RECORDS every write instead of making it."""
    _WRITES = ("update_one", "update_many", "replace_one", "insert_one", "insert_many", "delete_one", "delete_many",
               "find_one_and_update", "create_index", "bulk_write")

    def __init__(self, name: str, real, log_: list):
        self._name, self._real, self._log = name, real, log_

    def find(self, *a, **k):
        return list(self._real.find(*a, **k)) if self._real is not None else []

    def find_one(self, *a, **k):
        return self._real.find_one(*a, **k) if self._real is not None else None

    def distinct(self, *a, **k):
        return self._real.distinct(*a, **k) if self._real is not None else []

    def count_documents(self, *a, **k):
        return self._real.count_documents(*a, **k) if self._real is not None else 0

    def __getattr__(self, attr):
        if attr in self._WRITES:
            def _rec(*a, **k):
                self._log.append((self._name, attr))
                return SimpleNamespace(upserted_id=None, matched_count=0, modified_count=0)
            return _rec
        raise AttributeError(attr)


def dry_store(real_store=None):
    """A GajjalaStore whose every collection reads through and records writes; `.writes` lists them."""
    from . import store as ST
    real = real_store or ST.GajjalaStore()
    writes: list = []
    st = ST.GajjalaStore(colls={n: _RecordingColl(n, real.coll(n), writes) for n in ST.ALL})
    st.writes = writes
    st.dry = True                                               # run_pass skips the A8 owner check (nothing lands)
    return st


# ── one pass ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _row_from_snapshot(sym: str, row: Optional[dict], session_iso: str) -> dict:
    """A carried name that did not qualify this pass: its row off the snapshot (dated the session — trap T6)."""
    from sepa import prices
    from . import scanner as SC
    if not isinstance(row, dict):
        return {}
    ep = prices.extended_print(row)
    prev = _num(row.get("prev_day_close"))
    if not ep or ep["date"] != session_iso or not prev or prev <= 0:
        return {}
    vol, src = SC._volume(row, session_iso)
    return {"symbol": sym, "price": float(ep["price"]), "prev_close": prev,
            "change_pct": round((float(ep["price"]) / prev - 1) * 100, 4), "volume": vol, "vol_src": src,
            "day_c": _num(row.get("close")), "tape_session": ep["session"]}


def _reg_gain_pct(row: dict) -> Optional[float]:
    c, p = _num(row.get("day_c")), _num(row.get("prev_close"))
    return round((c / p - 1) * 100, 2) if (c and p and p > 0) else None


# ── 🔄 the lease, split (2026-10-15 — DECISIONS5 C1, AMENDMENTS5 A5–A8) ─────────────────────────────────────────────
_LEASE_REASON = {"held": "lease held — another pass is running",
                 "gap": (f"lease held — a {GC.PASS_CADENCE_SEC // 60}-minute pass started under "
                         f"{GC.LEASE_MIN_GAP_SEC} s ago"),
                 "held_on_demand": "lease held — an on-open pass is still running",
                 "error": "lease held — the lease could not be claimed (store error)"}
_ON_DEMAND_REFUSED = "lease held — a pass is in flight (the open waits for it)"
_SUPERSEDED = "superseded — a 5-minute pass took the lease over; this on-open pass stopped writing"


class _Superseded(Exception):
    """Raised inside an on-open pass whose lease a cron took over (A8): nothing more is written."""


def _claim(st, now: datetime, deps: Deps, *, on_demand: bool, now_given: bool) -> tuple:
    """(claim, now, waited_s) — DECISIONS5 C1. An on-open claim never waits (it needs only "not held"). A cron claim
    that finds an ON-OPEN pass holding the lease sleeps ON_DEMAND_POLL_SEC and retries, at most
    CRON_WAIT_ON_DEMAND_SEC // ON_DEMAND_POLL_SEC times, then claims with take_over=True — a cron is never refused
    because of an open. Inside that wait an "error" verdict (the on-open released between the attempt and the classify
    read) RETRIES on the next poll (A7); the same race on the FIRST attempt retries ONCE at once (no sleep) — an open
    that ends just as the tick lands never costs the tick (C1); a second "error" is a real store fault → refused. Every
    cron claim stamps the gap clock with the TICK clock `base` (A6). `now` after a wait = the wall clock (cron) or the
    given clock + the time waited (tests / replays). `getattr` keeps a monkeypatched `claim_lease = lambda …: True`
    working."""
    from . import store as ST
    if on_demand:
        return st.claim_lease(now, source=ST.LEASE_ON_DEMAND), now, 0.0
    base, waited = now, 0.0
    claim = st.claim_lease(now, source=ST.LEASE_CRON, cron_start=base)
    if not claim and getattr(claim, "why", None) == "error":
        claim = st.claim_lease(now, source=ST.LEASE_CRON, cron_start=base)
    waiting = getattr(claim, "why", None) == "held_on_demand"
    for _ in range(int(GC.CRON_WAIT_ON_DEMAND_SEC // GC.ON_DEMAND_POLL_SEC)):
        if claim or not waiting:
            break
        deps.sleep(GC.ON_DEMAND_POLL_SEC)
        waited += GC.ON_DEMAND_POLL_SEC
        now = _utc(None) if not now_given else base + timedelta(seconds=waited)
        claim = st.claim_lease(now, source=ST.LEASE_CRON, cron_start=base)
        waiting = getattr(claim, "why", None) in ("held_on_demand", "error")
    if waiting and not claim:
        claim = st.claim_lease(now, source=ST.LEASE_CRON, take_over=True, cron_start=base)
    return claim, now, waited


def _bars_through(frames: dict) -> Optional[str]:
    """"HH:MM" — the newest closed 5-minute bar label any name was read through (C3: the served copy says "bars
    through", never "fresh bars"); None when no frame was read."""
    ts = [fr.as_of_bar_t5 for fr in (frames or {}).values() if getattr(fr, "as_of_bar_t5", None)]
    return max(ts)[11:16] if ts else None


def run_pass(now: Optional[datetime] = None, *, store=None, deps: Optional[Deps] = None, dry: bool = False,
             symbols: Optional[list] = None, on_demand: bool = False) -> dict:
    """One pass. -> the summary (also the pass doc's body). Never raises past a per-step failure: a step that breaks
    is logged and named in `errors`, and the pass still records.

    `on_demand=True` (2026-10-15 — call it through `run_on_demand`): the owner's on-open pass — the real store, the
    ON_DEMAND_BUDGET_SEC bar budget, no Yahoo, BOTH push gates dry, no /alerts row, its own pass doc, and the A8 token
    check before every write of its tail (a cron that took the lease over owns the board from then on)."""
    from . import bars as B
    from . import context as CX
    from . import scanner as SC
    from . import alerts as AL
    from . import potential as PT
    from . import store as ST

    deps = deps or Deps()
    now_given = now is not None
    now = _utc(now)
    on_demand = bool(on_demand)
    if on_demand:
        dry = False                                             # an open always writes the store; its gates are dry
    et = now.astimezone(ET)
    session = et.date()
    session_iso = session.isoformat()
    out: dict = {"ran": False, "session": session_iso, "at_et": et.isoformat(), "dry": bool(dry), "errors": [],
                 "on_demand": on_demand}
    if not in_window(now):
        out["reason"] = "outside the pass window"
        return out
    st = store or (dry_store() if dry else ST.default())
    claim, now, waited = _claim(st, now, deps, on_demand=on_demand, now_given=now_given)
    out["lease"] = {"why": getattr(claim, "why", "claimed" if claim else "held"), "waited_s": waited,
                    "held_by": getattr(claim, "held_by", None)}
    if not claim:
        out["reason"] = (_ON_DEMAND_REFUSED if on_demand
                         else _LEASE_REASON.get(out["lease"]["why"], _LEASE_REASON["held"]))
        return out
    token = getattr(claim, "token", None)
    if waited:
        et = now.astimezone(ET)
        session = et.date()
        session_iso = session.isoformat()
        out.update({"at_et": et.isoformat(), "session": session_iso})
    guard_on = on_demand and not getattr(st, "dry", False)

    def mine() -> None:
        """A8: before every write of an on-open pass's tail — raise _Superseded once the token is not ours."""
        if guard_on and not st.lease_owner_is(token):
            raise _Superseded()

    t0 = deps.clock()
    frames: dict = {}
    try:
        out["ran"] = True
        rows, meta = deps.snapshot()
        rows = rows or {}
        good = (meta or {}).get("http") == 200 and bool(rows)
        out["snapshot"] = {k: (meta or {}).get(k) for k in ("http", "wall_s", "bytes", "n", "error")}
        mine()
        types = SC.ensure_type_map(st, session, fetch=deps.fetch_types, now=now)
        # The funnel says whether today's type filter ran on a COMPLETE map (a partial one keeps yesterday's types).
        tdoc = st.types_map() or {}
        out["types_meta"] = {"complete": bool(tdoc.get("complete")), "as_of": tdoc.get("as_of"), "n": tdoc.get("n")}
        result = SC.scan_rows(rows, now, session, types=types)
        mine()
        SC.record_scan(st, session, now, result, fetch_splits=deps.fetch_splits)
        mine()
        out["ah_carry"] = SC.commit_ah_carry(st, session, now, result, meta)
        try:
            halts = deps.halts() or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala pass: halts read failed: %s", type(exc).__name__)
            halts = {}
            out["errors"].append("halts")
        mine()
        CX.record_live_halts(st, session, halts)

        listed = SC.listed_symbols(st, session)
        for q in result["qualifiers"]:                          # a dry run recorded (not wrote) today's scan
            listed.setdefault(q["symbol"], {"since": session_iso, "last_qualified": session_iso, "day_n": 1,
                                            "of": GC.STAY_LISTED_SESSIONS + 1})
        names = sorted(listed)
        if symbols:
            want = [s.upper() for s in symbols]
            names = want if dry else [s for s in names if s in set(want)]
        q_rows = {q["symbol"]: q for q in result["qualifiers"]}
        stored = {d["symbol"]: (d.get("last") or {}) for d in st.scan_docs([session]) if d.get("symbol")}
        row_by = {s: (q_rows.get(s) or stored.get(s) or _row_from_snapshot(s, rows.get(s), session_iso))
                  for s in names}

        # float chain steps 1–2 (cache + Massive; no Yahoo yet — the 🎾 structure decides who goes first)
        mine()
        floats = CX.floats_for(names, now=now, status_lookup=deps.status_lookup, massive_lookup=deps.massive_lookup,
                               store=st, session=session, refine=False)
        mine()
        hist = CX.warm_squeeze_history(names, session, st, cap=GC.DAILY_MAX_NEW_PER_PASS, loader=deps.daily_loader)
        bar_stats: dict = {}
        # C2: the open's budget is short. A cron that WAITED for an open spends the wait out of its own budget, so it
        # still ends inside its tick's window (names past it keep their last read) — never overruns into the next tick.
        budget = GC.ON_DEMAND_BUDGET_SEC if on_demand else max(0.0, GC.PASS_BUDGET_SEC - waited)
        left = max(0.0, budget - (deps.clock() - t0))
        frames = B.frames_for(names, session, now, load_day=deps.load_day, budget_sec=left, stats=bar_stats)
        reads = {s: deps.read_all(fr.detector_frames(), {"symbol": s, "float_read": floats.get(s)})
                 for s, fr in frames.items()}

        # float chain step 3 — paced Yahoo, 🎾-alive names first; a changed float re-reads ONLY the 🎾 setup.
        # Never on an on-open pass (C7: one snapshot + the minute fetches, like a cron pass — no Yahoo).
        yahoo: dict = {}
        if deps.refine_floats and not dry and not on_demand and frames:
            priority = {s: {"structure_alive": bool(((reads.get(s) or {}).get("reversal_squeeze") or {})
                                                    .get("meta", {}).get("structure_alive")),
                            "change_pct": (row_by.get(s) or {}).get("change_pct")} for s in names}
            state = {k: v for k, v in (st.get_state(CX.FLOAT_STATE_ID) or {}).items() if k in ("until", "n")}
            refined = CX.floats_for(names, priority=priority, state=state, now=now, status_lookup=deps.status_lookup,
                                    massive_lookup=deps.massive_lookup, sleep=deps.sleep, store=st, session=session,
                                    max_new=GC.FLOAT_MAX_NEW_PER_PASS, refine=True)
            yahoo = dict(state.get("yahoo") or {})
            for s, fr_read in refined.items():
                if fr_read.get("refined") or (fr_read.get("shares") != (floats.get(s) or {}).get("shares")):
                    floats[s] = fr_read
                    if s in frames:
                        reads[s]["reversal_squeeze"] = deps.read_all(
                            frames[s].detector_frames(), {"symbol": s, "float_read": fr_read})["reversal_squeeze"]

        # ☀️ premarket levels (the 1-minute sum the board prefers) / 🌙 K10 confirm (after-hours passes)
        pm_levels = {}
        for s, fr in frames.items():
            try:
                lv = CX.pm_levels_for(fr.raw, session)
            except Exception:                                   # noqa: BLE001
                lv = None
            if lv:
                pm_levels[s] = lv
        post = None
        if result.get("tape_session") == "afterhours":
            checked = {d["symbol"]: d for d in st.post_docs(session) if d.get("symbol")}

            def minutes(sym):
                if sym in frames:
                    return frames[sym].raw
                # Massive's spelling for class shares (MOG-A → MOG.A), as `bars.frames_for` does.
                from sepa.symbols import for_massive
                return deps.load_day(for_massive(sym), session, force=True, include_premarket=True,
                                     include_afterhours=True)
            mine()
            p_rows, unchecked = CX.postmarket_confirm(result.get("k10_candidates") or [], checked, minutes,
                                                      cap=GC.AH_CONFIRM_MAX_PER_PASS, session=session, now=now,
                                                      store=st)
            post = {"rows": p_rows, "unchecked_n": unchecked}

        # the read docs the board serves
        alert_ctx: dict = {}
        pot_ctx: dict = {}
        for s, fr in frames.items():
            row = row_by.get(s) or {}
            fr_read = floats.get(s)
            chip = CX.halts_chip(s, halts)
            ctx = {"float": fr_read, "float_suspect": (fr_read or {}).get("suspect_text"),
                   "rotation": CX.rotation(row.get("volume"), fr_read), "halts": chip,
                   "psych": CX.psych_chips(row.get("price")), "squeeze_history": (hist.get("chips") or {}).get(s),
                   "last_halt_resume_et": (chip or {}).get("last_resume_et"), "reg_gain_pct": _reg_gain_pct(row)}
            prior = st.get_read(session, s) or {}
            stopped = dict(prior.get("stopped_today") or {})
            for setup, r in (reads.get(s) or {}).items():
                if (r or {}).get("state") == "stopped" and setup not in stopped:
                    stopped[setup] = r.get("entry_bar_t") or et.isoformat()
            tile = {}
            for tf, suf in (("5m", "5"), ("15m", "15")):
                p = B.tile_payload(fr, tf)
                tile.update({f"bars{suf}": p["bars"], f"curves{suf}": p["curves"], f"vol_avg{suf}": p["vol_avg"]})
            mine()
            st.upsert_read(session, s, {"as_of_bar_t5": fr.as_of_bar_t5, "as_of_bar_t15": fr.as_of_bar_t15,
                                        "setups": reads.get(s) or {}, "ctx": ctx, "tile": tile,
                                        "listed": listed.get(s), "stopped_today": stopped}, now=now)
            alert_ctx[s] = {"float_text": (fr_read or {}).get("text"), "price": row.get("price"),
                            "last_halt_resume_et": ctx["last_halt_resume_et"], "reg_gain_pct": ctx["reg_gain_pct"]}
            pot_ctx[s] = ctx                                    # 🧠 the SAME dict the read doc stores (tab reads it)

        push_dry = bool(dry or on_demand)                       # K2: an open never sends, claims or records a row
        al_failed = False
        try:
            alerts = AL.run_pass(reads, frames, now, session, store=st, send=deps.send, owner=deps.owner,
                                 dry=push_dry, ctx=alert_ctx)
        except Exception:                                       # noqa: BLE001 — D1: never silences the 🧠 gate
            log.exception("gajjala pass: the A+ gate failed")
            alerts, al_failed = {}, True
            out["errors"].append("alerts")
        out.update({"tape_session": result.get("tape_session"), "counts": result["counts"],
                    "strip": result["strip"], "n_listed": len(names), "n_read": len(reads), "bars": bar_stats,
                    "alerts": alerts, "floats": yahoo, "status": "ok" if good else "failed",
                    "qualifiers": [q["symbol"] for q in result["qualifiers"]],
                    "premarket": {"pm_levels": pm_levels}, "postmarket": post,
                    "bars_through_et": _bars_through(frames),
                    "aplus": sorted(f"{s}:{k}" for s, rs in reads.items() for k, r in rs.items()
                                    if (r or {}).get("state") == "aplus")})
        if al_failed:
            out["status"] = "error"

        # 🧠 potentials — AFTER the pass summary, in its OWN try (AMENDMENTS4 D1). D2: the price is the 5-minute
        # frame's latest close first, else THIS pass's row (a qualifier or the live snapshot) — never the stored row.
        live_rows = {s: (q_rows.get(s) or _row_from_snapshot(s, rows.get(s), session_iso)) for s in frames}
        try:
            out["potential"] = PT.run_pass(reads, frames, now, session, store=st, ctx=pot_ctx, rows=row_by,
                                           send=deps.send_potential, owner=deps.owner, dry=push_dry,
                                           tape=result.get("tape_session"), live_rows=live_rows)
        except Exception:                                       # noqa: BLE001
            log.exception("gajjala pass: the potential gate failed")
            out["errors"].append("potential")
            out["potential"] = {}
        if on_demand:
            mine()                                              # the pass doc is the tail's last write
    except _Superseded:
        out["superseded"] = 1
        out["status"] = "superseded"
        out["reason"] = _SUPERSEDED
        log.info("gajjala on-open pass: %s", _SUPERSEDED)
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala pass failed")
        out["errors"].append(type(exc).__name__)
        out["status"] = "error"
    finally:
        out["wall_s"] = round(deps.clock() - t0, 3)
        _finish(st, now, session, out, deps, on_demand=on_demand, token=token)
    return out


def run_on_demand(now: Optional[datetime] = None, *, store=None, deps: Optional[Deps] = None) -> dict:
    """CONTRACT — 🔄 the owner's on-open pass (Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.
    In that moment and if there are any enterable stocks on the top which I see in potential i guess"; DECISIONS5 K2,
    C1–C7). = run_pass(on_demand=True): the real store, the ON_DEMAND_BUDGET_SEC bar budget (names past it keep their
    last read — C2), no Yahoo (C7), BOTH push gates dry (an open never rings: no send, no claim, no tracker write, no
    shadow row), no /alerts row (K2), the pass doc `"{date}|{HH:MM:SS}|open"` with `on_demand: True` and `finished_at`
    (C5), "latest" moved only forward and only when a name was re-read (A13), "latest_cron" never (A10). The lease: an
    on-open claim needs only "not held" (refused → `reason` = "lease held — a pass is in flight …", no snapshot); a cron
    that took it over makes this pass stop writing (`status` "superseded", A8). Runs ONLY in its own process —
    `python -m chart_maps.gajjala.run --on-demand`, which chart_maps/gajjala/on_demand.py spawns (A1); never by the cron
    and never inside the api process. -> the run_pass summary (+ `on_demand`, `lease`, `bars_through_et`)."""
    return run_pass(now, store=store, deps=deps or Deps(refine_floats=False), on_demand=True)


def _finish(st, now: datetime, session: date, out: dict, deps: Deps, *, on_demand: bool = False,
            token: Optional[str] = None) -> None:
    """The pass doc (the board's as_of / strip / ☀️ / 🌙), the /alerts row, the lease — each best-effort. An on-open
    pass (2026-10-15) writes its OWN pass doc and NO /alerts row; a superseded one (A8) writes no doc — it only sends
    its token-guarded release: after a real take-over the token matches nothing and nothing changes; after a FAILED
    owner read (lease_owner_is fails closed) it frees the open's own lease, so the next cron never waits on it.
    The A8 owner check runs here too, before the pass doc: a body that raised an ordinary exception after a take-over
    never reached its last `mine()`, and its error doc is still a write (final critic 2026-10-16)."""
    from . import store as ST
    if (on_demand and not out.get("superseded") and not getattr(st, "dry", False)
            and not st.lease_owner_is(token)):
        out["superseded"] = 1
        out["status"] = "superseded"
        out["reason"] = _SUPERSEDED
        log.info("gajjala on-open pass: %s", _SUPERSEDED)
    if out.get("superseded"):
        try:
            st.release_lease(now, token)                        # token-guarded: never frees the cron's lease
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala pass: lease release failed: %s", exc)
        return
    body = {k: out.get(k) for k in ("tape_session", "counts", "strip", "n_listed", "n_read", "bars", "alerts",
                                    "status", "errors", "wall_s", "premarket", "postmarket", "ah_carry", "potential",
                                    "on_demand", "bars_through_et", "lease")}
    body["snapshot_meta"] = out.get("snapshot")
    body["types_meta"] = out.get("types_meta")
    body["finished_at"] = now + timedelta(seconds=float(out.get("wall_s") or 0))
    try:
        if on_demand:
            st.record_pass(session, now, body,
                           hhmm=now.astimezone(ET).strftime("%H:%M:%S") + "|" + ST.ON_DEMAND_PASS_SUFFIX,
                           source=ST.LEASE_ON_DEMAND, latest_if_newer=True,
                           move_latest=bool(out.get("n_read")))   # A13: nothing re-read → "latest" stays put
        else:
            st.record_pass(session, now, body)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala pass: pass doc failed: %s", exc)
    if not on_demand:
        # K2: the /alerts rows stay the cron's "what pushed / why quiet" — an open writes neither
        counts = dict(out.get("alerts") or {})
        counts.update({"candidates": out.get("n_read") or 0, "listed": out.get("n_listed") or 0,
                       "qualifiers": len(out.get("qualifiers") or [])})
        reason = None if out.get("status") == "ok" else (
            "snapshot failed — listed names read off the stored scan" if out.get("status") == "failed"
            else "pass error: " + ", ".join(out.get("errors") or []))
        try:
            deps.record_status(counts, now, reason)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala pass: /alerts row failed: %s", exc)
        # 🧠 its own row and its own reason: a failed A+ gate never marks it, a failed potential gate always does (D1)
        errs = out.get("errors") or []
        if "potential" in errs:
            pot_reason = "pass error: potential"
        elif "potential" in out:
            pot_reason = ("snapshot failed — listed names read off the stored scan" if out.get("status") == "failed"
                          else None)
        else:
            pot_reason = reason
        try:
            deps.record_potential_status(dict(out.get("potential") or {}), now, pot_reason)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala pass: /alerts potential row failed: %s", exc)
    try:
        st.release_lease(now, token)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala pass: lease release failed: %s", exc)


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def dry_deps() -> Deps:
    """Every writer and sender a recorder (the store side is `dry_store`)."""
    sent: list = []
    status: list = []
    sent_potential: list = []
    status_potential: list = []
    d = Deps(load_day=_dry_load_day, status_lookup=_dry_status_lookup, refine_floats=False,
             send=lambda owner, payload: (sent.append(payload), {"sent": 0, "failed": 0, "total_targets": 0})[1],
             record_status=lambda counts, now, reason=None: (status.append(counts), False)[1],
             send_potential=lambda owner, payload: (sent_potential.append(payload),
                                                    {"sent": 0, "failed": 0, "total_targets": 0})[1],
             record_potential_status=lambda counts, now, reason=None: (status_potential.append(counts), False)[1])
    d.sent, d.status = sent, status                             # type: ignore[attr-defined]
    d.sent_potential, d.status_potential = sent_potential, status_potential   # type: ignore[attr-defined]
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.gajjala.run", description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="record every write and send; touch nothing")
    ap.add_argument("--json", action="store_true", help="print the pass summary as JSON")
    ap.add_argument("--now", help="ISO clock to replay (default: now)")
    ap.add_argument("--symbols", help="comma list: narrow the names read (a dry run reads them even when not listed)")
    ap.add_argument("--on-demand", action="store_true",
                    help="the owner's on-open pass (run_on_demand: push gates dry, short budget, no Yahoo) — 2026-10-15")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ET)                            # a naive --now is ET (the house rule), never UTC
    syms = [s.strip() for s in (args.symbols or "").split(",") if s.strip()] or None
    if not in_window(_utc(now)):                                # C6: the window check stays first (on-open too)
        log.info("gajjala pass: outside %s–%s ET on a market day — nothing to do", GC.PASS_OPEN_ET, GC.PASS_CLOSE_ET)
        return 0
    if args.dry_run:
        if args.on_demand:
            out = run_on_demand(now, store=dry_store(), deps=dry_deps())
        else:
            out = run_pass(now, store=dry_store(), deps=dry_deps(), dry=True, symbols=syms)
    else:
        from . import store as ST
        st = ST.default()
        st.ensure_indexes()
        if args.on_demand:
            out = run_on_demand(now, store=st, deps=Deps())
        else:
            out = run_pass(now, store=st, deps=Deps(), symbols=syms)
    if args.json:
        print(json.dumps(out, default=str))
    elif args.on_demand:
        log.info("gajjala on-open pass: %s", {k: out.get(k) for k in ("ran", "status", "n_listed", "n_read", "bars",
                                                                        "wall_s", "lease", "reason")})
    else:
        log.info("gajjala pass: %s", {k: out.get(k) for k in ("ran", "status", "n_listed", "n_read", "alerts",
                                                                "wall_s", "lease", "reason")})
    return 1 if out.get("status") == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
