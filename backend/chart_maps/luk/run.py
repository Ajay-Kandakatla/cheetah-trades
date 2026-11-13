"""🥇 Luk's — the pass, the detached child, the switch (BUILD_SPEC §3.8, WP-A4, 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources. ... I need something like Gajjlala that is exposed"

HOW IT RUNS. ONE Luk pass per 5-minute cron tick, as a DETACHED child of 🚩 Gajjala's cron pass: `gajjala/run.py`'s
`_spawn_luk()` (the ONE fenced GG edit, cron path only) calls `spawn_child()` when `enabled()` and `in_window()`; the
child is `python -m chart_maps.luk.run --child` started through `gajjala.run_1m._popen` (a new session, no inherited
descriptors) — never in-process: supercronic runs without -overlapping, and anything long inside the 🚩 job would make
it SKIP the next live 🚩 pass. The child re-checks `enabled()`, `in_window()` and `fits()` (start + LUK_PASS_BUDGET_SEC
+ LUK_SLOT_MARGIN_SEC ≤ the next tick of the gajjala.run_1m.slot_of grid) and writes a "skipped" state doc otherwise.

THE PASS (run_pass, 17 steps — 13b added 2026-11-12). 1 window → 2 lease (luk_state, Luk's own numbers) → 3 ONE whole-market snapshot →
4 the stored type map (READ only) → 5 universe = CS/ADRC rows with a numeric price → 6 caps (cache only) → 7 daily facts
(daily.warm: the TRUST rule decides cache hit vs fetch, ≤ LUK_DAILY_MAX_NEW_PER_PASS fetches, LUK_DAILY_WARM_BUDGET_SEC)
→ 8 his three screens → luk_screens → 9 QQQ / IWM state words (Luk's own fetch, ONCE per session: luk_state
LUK_STATE_INDEX, REFIX 2026-11-01) → 10 the shortlist (+ names carried in forming / triggered) → 11 closed 1m / 5m / 60m frames (the pass budget left) → 12 the three detectors, the 1-minute A+ clock =
the PREVIOUS pass's bars-through read off luk_state ([fixed: C1]) → luk_reads → 13 the A+ gate (alerts.run_pass — live since 2026-11-01)
→ 13b the board re-read (2026-11-12, display only — see below) → 14 the 🏁 grade step (ledger.grade_step; skipped on a dry run) → 15 this pass's bars-through written to luk_state
(the next pass's clock) → 16 the pass doc + the /alerts PASS-HEALTH row (LUK_KIND) → the lease released.
Every provider dependency is counted in the summary's `calls` block (the cost arithmetic of §3.15 is measured, never
typed). Since 2026-11-01 every fresh, in-session 🥇 A+ rings his phone by his word (Ajay 2026-11-01: "Lets make it
live. also alerts too." — alerts.run_pass's live branch, the default sender and owner); any other LUK_PUSH_MODE records
in shadow, never sent. UNMEASURED: nothing here trades, sizes or enters a lane.

CLI: `--child` (the cron child), `--dry-run` (dry store + dry deps: every write recorded, nothing lands; prints `calls`),
`--json`, `--now ISO` (refused without --dry-run, exit 2; a naive stamp is ET), `--symbols A,B` (narrow the names read).

🥇 13b THE BOARD RE-READ (2026-11-12). Ajay 2026-11-12: "Luks scan is not realtime I see all dated values can you make it
realtime". After the push gate, every card the board shows by default (luk.tab.tiles_for + luk.tab._clip_focus — the
board's own engine — over today's reads with THIS pass's ring reads overlaid in memory, interleaved across the setup
subs, at most LC.LUK_REREAD_MAX) and every card a 🥇 alert opened today, minus the names this pass already read, is
re-read with ONE more bars.frames_for call on the pass budget left (LUK_PASS_BUDGET_SEC − LUK_GRADE_BUDGET_SEC −
elapsed) and the SAME 1-minute clock. A re-read is DISPLAY ONLY: it is never handed to the push gate, never counted in
`n_read` / `states` / `aplus`, never moves the 1-minute clock, and its doc carries `refresh_only` + `cron_setups` (the
on-demand rule), so `_carried` — and therefore the shortlist and what can ring — is exactly what it was. A re-read A+
whose gate claim ids (GA.shadow_key / GA.claim_key under LUK) are both absent carries `not_rung` (one find_one; a read
fault → no flag, fails closed). The whole step sits in ONE try: `_Superseded` is re-raised (the on-demand A8 stop),
any other fault is `errors += ["refresh"]` + `refresh.skipped = "error"` and the 🏁 grade and the clock still run.
LC.LUK_REREAD_SHOWN False or `--symbols` → no re-read (`refresh.skipped` says why). COST: + ≤ LUK_REREAD_MAX (+ today's
alerted names) minute loads per pass, counted in `calls.minute_today` / `calls.minute_prior` like every other load.

🔄 THE ON-DEMAND PASS (2026-11-11). Ajay 2026-11-11: "Can you put an ondeman scan button for Luk' scans too". `--on-demand`
= `run_on_demand()` = run_pass(on_demand=True), spawned by chart_maps/luk/on_demand.py when he taps 🔄 scan now (never by
the cron, never inside the api process). It reads like a cron pass and writes its screens and reads, but it NEVER:
(1) rings, claims or records an alert (the push gate runs dry), (2) runs the 🏁 grade step, (3) writes the 1-minute
clock (luk_state LUK_STATE_BARS_THROUGH — the next cron pass keeps the previous CRON pass's clock, so a 1-minute break the
tap saw is still fresh for the cron pass that rings it), (4) writes the /alerts PASS-HEALTH row, (5) moves "latest_cron".
Its lease claim is on_demand (free only; it never stamps the cron gap clock); its pass doc is "{date}|{HH:MM:SS}|on_demand"
with `on_demand` and `finished_at`; "latest" moves only forward and only on an ok pass. Each read it writes carries
`on_demand` and `cron_setups` (the last CRON pass's setups), and `_carried` reads `cron_setups` off such a doc — the next
cron pass's shortlist is exactly what the cron passes alone would have made. The cron claim takes over a running
on-demand holder (`take_over=True`, 🚩's rule): a dead or slow on-demand child never costs a cron pass; the on-demand pass
checks it still owns the lease (`mine()`, 🚩's A8) before every write of its tail and stops writing once taken over.
The child re-checks only the switch and the window (the parent decided the slot once). `--on-demand --dry-run` records
every write and lands nothing; `--on-demand --child` is refused (exit 2).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import run as GR

from . import constants as LC

log = logging.getLogger("chart_maps.luk.run")

ET = ZoneInfo("America/New_York")
ARGV_CHILD = (sys.executable, "-m", "chart_maps.luk.run", "--child")
PROC_NAME = "luk-pass"
CHILD_STATE_ID = "child"                              # the luk_state doc a refused --child writes ("skipped" + reason)
_CALLS_LOCK = threading.Lock()
CALL_KEYS = ("snapshot", "daily_fetch", "minute_today", "minute_prior", "index", "caps")
STATE_KEYS = ("aplus", "triggered", "forming", "listed", "stopped", "none")
CARRY_STATES = ("forming", "triggered")
SKIP_OFF = "off (LUK_ENABLED)"
SKIP_WINDOW = "outside its window"
SKIP_SLOT = "no time left in the slot"
_LEASE_REASON = {"held": "lease held — another Luk pass is running",
                 "gap": "lease held — a Luk pass started under its minimum gap ago",
                 "error": "lease held — the lease could not be claimed (store error)"}
ON_DEMAND_PASS_SUFFIX = "on_demand"                   # the on-demand pass doc id "{date}|{HH:MM:SS}|on_demand"
_SUPERSEDED = "superseded — a 5-minute 🥇 pass took the lease over; this on-demand pass stopped writing"
_BODY_KEYS = ("ran", "dry", "errors", "lease", "snapshot", "screens", "shortlist", "bars", "n_read", "states", "aplus",
              "alerts", "market_state", "ledger", "calls", "bars_through", "wall_s", "status", "refresh")
# 2026-11-12 13b the board re-read (Ajay 2026-11-12: "Luks scan is not realtime I see all dated values can you make it
# realtime") — the pass doc's `refresh` block
REFRESH_KEYS = ("on", "board_n", "board_read_n", "asked", "asked_n", "read_n", "not_read", "bars",
                "aplus_not_rung", "budget_s", "wall_s", "skipped")
SKIP_REFRESH_OFF = "off (LUK_REREAD_SHOWN)"
SKIP_REFRESH_SYMBOLS = "--symbols"
SKIP_REFRESH_ERROR = "error"
_BARS_KEYS = ("loaded", "no_bars", "failed", "over_budget")


class _Superseded(Exception):
    """Raised inside an on-demand pass whose lease a cron Luk pass took over (🚩's A8): nothing more is written."""


# ── the switch, the window, the slot ──────────────────────────────────────────────────────────────────────────────
def enabled() -> bool:
    """The kill switch: LC.LUK_ENABLED AND the env LUK_ENABLED is not "0" (read at call time)."""
    return bool(LC.LUK_ENABLED) and os.environ.get("LUK_ENABLED", "1") != "0"


def in_window(now: Optional[datetime] = None) -> bool:
    """LUK_PASS_OPEN_ET ≤ ET ≤ LUK_PASS_CLOSE_ET on a market day (the house calendar). `now` None → the wall clock
    (the GG hook calls it bare). [fixed: C11]"""
    from catalysts.medical.reaction import is_market_day
    et = GR._utc(now).astimezone(ET)
    t = et.time().replace(second=0, microsecond=0)
    return (is_market_day(et.date()) and dtime.fromisoformat(LC.LUK_PASS_OPEN_ET) <= t
            <= dtime.fromisoformat(LC.LUK_PASS_CLOSE_ET))


def fits(start, next_tick) -> bool:
    """start + LUK_PASS_BUDGET_SEC + LUK_SLOT_MARGIN_SEC ≤ next_tick — a Luk pass never runs into the next 🚩 tick."""
    return (GR._utc(start) + timedelta(seconds=LC.LUK_PASS_BUDGET_SEC + LC.LUK_SLOT_MARGIN_SEC)
            <= GR._utc(next_tick))


def slot_of(now) -> tuple:
    """(tick, next_tick) — gajjala.run_1m.slot_of (the crontab "1-56/5" grid), imported, never re-derived."""
    from chart_maps.gajjala import run_1m as R1
    return R1.slot_of(now)


# ── dependencies (real by default; tests and --dry-run replace them) ─────────────────────────────────────────────
def _types() -> dict:
    """{SYM: instrument type} off GG5's stored reference map — a READ, never a fetch or a write. The doc's shape is
    the one `gajjala.scanner.ensure_type_map` writes and reads: `pairs` = [[SYM, type], …] (no `types` key). A missing
    doc, a read fault or a junk pair → that entry absent ({} at worst: an empty universe, never a raise)."""
    from chart_maps.gajjala import store as GS
    try:
        doc = GS.default().types_map() or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk pass: type map read failed: %s", type(exc).__name__)
        return {}
    if not isinstance(doc, dict):
        return {}
    return {str(p[0]).upper(): p[1] for p in doc.get("pairs") or []
            if isinstance(p, (list, tuple)) and len(p) == 2 and p[0]}


def _caps(tickers: list, last_prices: dict) -> dict:
    """Market caps, CACHE ONLY (cap=0: no provider lookup). None = unknown."""
    from catalysts.promo_circuit import market_caps_for
    return market_caps_for(list(tickers), dict(last_prices), cap=0)


def _cached(sym, session, *, now):
    from . import daily as DA
    return DA.cached_frame(sym, session, now=now)


def _fetch(sym, session):
    from . import daily as DA
    return DA.fetch_frame(sym, session)


def _grade_load_day(sym, day):
    from chart_maps.gajjala import ledger as GL
    return GL._default_load_day(sym, day)


def _record_status(counts: dict, now: datetime, reason: Optional[str] = None) -> bool:
    """The /alerts PASS-HEALTH row — its kind string from the Luk constants (never a push kind)."""
    from supply_demand import alert_status as AS
    return AS.record_pass(LC.LUK_KIND, counts, now, reason=reason)


@dataclass
class Deps:
    snapshot: Callable = GR._snapshot             # () -> (rows, meta) — the house whole-market snapshot
    types: Callable = _types                      # () -> {SYM: type}
    caps: Callable = _caps                        # (tickers, last_prices) -> {SYM: cap | None}
    cached: Callable = _cached                    # daily.cached_frame (the trust rule)
    fetch: Optional[Callable] = _fetch            # daily.fetch_frame (None in a dry run → deferred)
    load_day: Callable = GR._load_day             # the minute loader (sym, day, force=, include_premarket=, …)
    index_loader: Optional[Callable] = None       # daily.index_state's loader (None = daily.default_index_loader)
    record_status: Callable = _record_status      # (counts, now, reason) -> bool
    grade_load_day: Callable = _grade_load_day    # 🏁 (sym, day) -> (bars, failed); the daily close = ledger's own fetch
    clock: Callable = time.monotonic
    sleep: Callable = time.sleep


def _dry_index_loader(sym):
    """A dry run's index loader: the same fresh provider read `load_prices(sym, "1y", force=True)` makes
    (`prices._fetch` + its two read-time cuts) WITHOUT the house-cache write — a dry run lands nothing anywhere."""
    from sepa import prices
    df = prices._fetch(sym, "1y")
    if df is None or df.empty:
        return None
    return prices._drop_phantom_tail(prices._cut_foreign_head(df, sym))


def dry_deps() -> Deps:
    """No cache write anywhere: the minute loader fetches without the cache write, no daily fetch (deferred), the
    index words fetched without the cache write, the /alerts row a recorder."""
    status: list = []
    d = Deps(load_day=GR._dry_load_day, fetch=None, index_loader=_dry_index_loader,
             record_status=lambda counts, now, reason=None: (status.append(counts), False)[1])
    d.status = status                                           # type: ignore[attr-defined]
    return d


# ── the counted dependencies ─────────────────────────────────────────────────────────────────────────────────────
def _counted(fn: Optional[Callable], calls: dict, key) -> Optional[Callable]:
    """`fn` wrapped so each call adds 1 to calls[key(args) if callable(key) else key]. None stays None."""
    if fn is None:
        return None

    def wrapped(*a, **k):
        with _CALLS_LOCK:                                       # bars.frames_for loads in a thread pool
            calls[key(a, k) if callable(key) else key] += 1
        return fn(*a, **k)
    return wrapped


def _day_of(a, k):
    d = k.get("day", a[1] if len(a) > 1 else None)
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        try:
            return date.fromisoformat(d[:10])
        except ValueError:
            return None
    return d


# ── the pass ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _price(row: dict) -> Optional[float]:
    """The last print (extended_print) else the day close — the screens' price rule."""
    from sepa import prices
    try:
        ep = prices.extended_print(row)
    except Exception:                                           # noqa: BLE001
        ep = None
    px = _num((ep or {}).get("price"))
    if px is None or px <= 0:
        px = _num(row.get("close"))
    return px if px is not None and px > 0 else None


def _et_dt(v) -> Optional[datetime]:
    """A stored stamp → an aware ET datetime: a datetime (naive = UTC, the Mongo client) or an ET "YYYY-MM-DD HH:MM"."""
    if isinstance(v, datetime):
        return GR._utc(v).astimezone(ET)
    if isinstance(v, str) and len(v) >= 16:
        try:
            dt = datetime.fromisoformat(v)
        except ValueError:
            try:
                dt = datetime.strptime(v[:16], "%Y-%m-%d %H:%M")
            except ValueError:
                return None
        return dt.replace(tzinfo=ET) if dt.tzinfo is None else dt.astimezone(ET)
    return None


def prev_bars_through(state: Optional[dict], session_iso: str) -> tuple:
    """(t1, t5) of the PREVIOUS pass of THIS session (luk_state LUK_STATE_BARS_THROUGH), ET-aware; (None, None) when
    absent or another session's — the first pass of a day reads every 1-minute break as fresh. [fixed: C1]"""
    if not isinstance(state, dict) or state.get("session") != session_iso:
        return None, None
    return _et_dt(state.get("t1")), _et_dt(state.get("t5"))


def _later(a: Optional[datetime], b: Optional[datetime]) -> Optional[datetime]:
    return a if b is None else (b if a is None else max(a, b))


def _hhmm(t: Optional[datetime]) -> Optional[str]:
    return t.astimezone(ET).strftime("%H:%M") if isinstance(t, datetime) else None


def _cron_setups(doc) -> Optional[dict]:
    """The setups the CRON shortlist last judged: `cron_setups` on a doc that an on-demand pass OR a board re-read wrote
    (`on_demand` / `refresh_only` True), else `setups`. None for a non-dict."""
    if not isinstance(doc, dict):
        return None
    return doc.get("cron_setups") if (doc.get("on_demand") or doc.get("refresh_only")) else doc.get("setups")


def _carried(st, session, today_docs: Optional[list] = None) -> set:
    """Today's and the previous market day's reads with a setup in forming / triggered. A read an on-demand pass wrote
    (`on_demand` True, 2026-11-11) or a board re-read wrote (`refresh_only` True, 2026-11-12) counts by its
    `cron_setups` — the last CRON pass's setups — so neither ever adds or drops a carried name. `today_docs` (the
    pass's ONE read of today's docs) stands in for `st.reads(session)` when given; the previous day is still read."""
    from catalysts.medical.reaction import prev_market_day
    out: set = set()
    for d in (session, prev_market_day(session)):
        docs = today_docs if (today_docs is not None and d == session) else (st.reads(d) or [])
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            setups = _cron_setups(doc)
            if isinstance(setups, dict) and any(isinstance(r, dict) and r.get("state") in CARRY_STATES
                                                for r in setups.values()):
                if doc.get("symbol"):
                    out.add(str(doc["symbol"]).upper())
    return out


def _overlay(today_docs: list, ring_docs: dict) -> list:
    """today_docs with each symbol in ring_docs ({SYM: the doc this pass just upserted, in the store's shape
    dict(body, date, symbol, updated_at=now, at=now)}) REPLACED by that doc, and ring symbols absent from today_docs
    appended (sorted). Pure; never mutates its arguments. [C4]"""
    ring = {str(k).upper(): v for k, v in (ring_docs or {}).items()}
    out, seen = [], set()
    for d in today_docs or []:
        if not isinstance(d, dict):
            continue
        sym = str(d.get("symbol") or "").upper()
        if sym and sym in ring:
            out.append(ring[sym])
            seen.add(sym)
        else:
            out.append(d)
    out.extend(ring[s] for s in sorted(ring) if s not in seen)
    return out


def _board_names(today_docs: list, alert_rows: Optional[list]) -> list:
    """Every card the board shows by default — luk.tab.tiles_for(docs, setup, caps={}) split by luk.tab.live_tiles
    (the board's own live/ended split, 2026-11-12: with no ctx only a `stopped` card is ended, so a stopped card is
    not re-read; no chart_maps.live_card import) and cut by luk.tab._clip_focus(…, "", GC.TILE_LIMIT_DEFAULT) per
    LC.SETUPS sub (the board's own engine, imported), interleaved by position (card 1 of each sub, then card 2, …) —
    cut to LC.LUK_REREAD_MAX; then today's alert symbols (alert_rows: `at` desc, symbol asc) not already listed — a
    stopped card's alert name is still appended. Upper-cased, de-duplicated, in that order. Reads its arguments
    only."""
    from chart_maps.gajjala import constants as GC
    from . import tab as TB
    docs = [d for d in today_docs or [] if isinstance(d, dict)]
    per = [[str(t.get("symbol") or "").upper() for t in
            TB._clip_focus(TB.live_tiles(TB.tiles_for(docs, setup, caps={})), "", GC.TILE_LIMIT_DEFAULT)]
           for setup in LC.SETUPS]
    shown: list = []
    for i in range(max((len(p) for p in per), default=0)):
        for p in per:
            if i < len(p) and p[i] and p[i] not in shown:
                shown.append(p[i])
    out = shown[:max(0, int(LC.LUK_REREAD_MAX))]
    rows = [r for r in alert_rows or [] if isinstance(r, dict) and r.get("symbol")]
    rows.sort(key=lambda r: str(r["symbol"]).upper())
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)     # stable: `at` desc, then symbol asc
    for r in rows:
        sym = str(r["symbol"]).upper()
        if sym not in out:
            out.append(sym)
    return out


def _rang(coll, session, sym: str, setup: str) -> Optional[bool]:
    """Did the gate ever claim this (sym, setup) today? ONE coll.find_one over the gate's own ids
    (GA.shadow_key / GA.claim_key under LUK — luk/alerts.py run_pass). True = a claim doc exists (shadow, claimed,
    pushed, failed, no_target); False = neither id (a `#state` refusal never matches); None = unknown (coll None, or the
    find raised) → no pill (fails CLOSED — never GA._exists, which fails open). [C2]"""
    from chart_maps.gajjala import alerts as GA
    from .variant import LUK
    if coll is None:
        return None
    ids = [GA.shadow_key(session, sym, setup, LUK), GA.claim_key(session, sym, setup, LUK)]
    try:
        return coll.find_one({"_id": {"$in": ids}}) is not None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk pass: claim read failed for %s %s: %s", sym, setup, type(exc).__name__)
        return None


def _refresh_skipped(reason: str) -> dict:
    """The `refresh` block of a pass that did not re-read: every REFRESH_KEYS key, on False, counts 0, lists [],
    bars {loaded, no_bars, failed, over_budget: 0}, budget_s / wall_s 0.0, skipped = reason."""
    return {"on": False, "board_n": 0, "board_read_n": 0, "asked": [], "asked_n": 0, "read_n": 0, "not_read": [],
            "bars": {k: 0 for k in _BARS_KEYS}, "aplus_not_rung": [], "budget_s": 0.0, "wall_s": 0.0,
            "skipped": reason}


def _read_body(sym: str, F, setups: dict, facts_of_sym, rank: dict, rows_by: dict) -> dict:
    """One read doc's body (the ring loop and the board re-read write the same shape)."""
    from chart_maps.gajjala.bars import tile_payload
    try:
        tile = tile_payload(F, "5m")
    except Exception as exc:                                    # noqa: BLE001
        log.debug("luk pass: tile failed for %s: %s", sym, exc)
        tile = {}
    fct = facts_of_sym or {}
    row = rows_by.get(sym) or {}
    return {
        "as_of_bar_t5": F.as_of_bar_t.get("5m"), "as_of_bar_t1": F.as_of_bar_t.get("1m"),
        "as_of_bar_t60": F.as_of_bar_t.get("60m"), "setups": setups, "facts": fct,
        "tile": {"bars5": tile.get("bars"), "curves5": tile.get("curves"), "vol_avg5": tile.get("vol_avg")},
        "screens_rank": rank.get(sym, {}), "tier": fct.get("tier"), "cap_text": row.get("cap_text")}


def _board_reread(st, session, now, *, today_docs: list, ring_docs: dict, names: list, facts: dict, rows_by: dict,
                  rank: dict, prev_t1, load_day, deps, t0: float, on_demand: bool, mine, errors: list) -> dict:
    """Step 13b — the board re-read (display only; rings nothing). -> the `refresh` block (REFRESH_KEYS). Raises only
    _Superseded (through mine()); any other fault is the caller's (run_pass) — see the step-13b wrapper."""
    from . import bars as BA
    from . import detectors as DT
    start = deps.clock()
    iso = session.isoformat() if hasattr(session, "isoformat") else str(session)
    board = _board_names(_overlay(today_docs, ring_docs), st.alert_rows([session]))
    ring = {str(s).upper() for s in names or []}
    asked = [s for s in board if s not in ring]
    budget = max(0.0, LC.LUK_PASS_BUDGET_SEC - LC.LUK_GRADE_BUDGET_SEC - (deps.clock() - t0))
    rstats: dict = {k: 0 for k in _BARS_KEYS}
    rframes: dict = {}
    if asked and budget > 0:
        rframes = BA.frames_for(asked, session, now, load_day=load_day, budget_sec=budget, stats=rstats) or {}
    elif asked:
        rstats["over_budget"] = len(asked)
    prior = {str(d["symbol"]).upper(): d for d in today_docs or [] if isinstance(d, dict) and d.get("symbol")}
    coll = st.alerts_coll()
    written: list = []
    not_rung_all: list = []
    for sym in asked:
        F = rframes.get(sym)
        if F is None:
            continue
        pd_ = prior.get(sym) or {}
        f = facts.get(sym)
        if not f:                                               # absent, or a falsy daily.Pending
            pf = pd_.get("facts")
            if isinstance(pf, dict) and pf and not pf.get("pending"):
                f = pf                                          # the same session's stored facts (never a pending)
        try:
            setups = DT.read_all(F, f, iso, prev_through_1m=prev_t1) or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk pass: re-read failed for %s: %s", sym, type(exc).__name__)
            errors.append(f"reread:{sym}")
            continue
        body = _read_body(sym, F, setups, f, rank, rows_by)
        body["refresh_only"] = True
        body["cron_setups"] = _cron_setups(pd_)
        if on_demand:
            body["on_demand"] = True
        nr: list = []
        for setup, r in setups.items():
            if (r or {}).get("state") == "aplus" and _rang(coll, session, sym, setup) is False:
                nr.append(setup)
                not_rung_all.append(f"{sym}|{setup}")
        body["not_rung"] = nr
        mine()
        st.upsert_read(session, sym, body, now=now)
        written.append(sym)
    got = set(written) | {str(s).upper() for s in (ring_docs or {})}
    return {"on": True, "board_n": len(board), "board_read_n": sum(1 for s in board if s in got),
            "asked": list(asked), "asked_n": len(asked), "read_n": len(written),
            "not_read": [s for s in asked if s not in set(written)],
            "bars": {k: rstats.get(k, 0) for k in _BARS_KEYS}, "aplus_not_rung": not_rung_all,
            "budget_s": round(budget, 3), "wall_s": round(deps.clock() - start, 3), "skipped": None}


def _new_out(now: datetime, dry: bool) -> dict:
    et = now.astimezone(ET)
    return {"ran": False, "session": et.date().isoformat(), "at_et": et.isoformat(), "dry": bool(dry), "errors": [],
            "calls": {k: 0 for k in CALL_KEYS}}


def run_pass(now: Optional[datetime] = None, *, store=None, deps: Optional[Deps] = None, dry: bool = False,
             symbols: Optional[list] = None, on_demand: bool = False) -> dict:
    """One Luk pass (the 17 steps of the module docstring — 13b the board re-read, 2026-11-12). Never raises past a step: a failure is logged, named in
    `errors`, and the pass still records. -> the summary (also the pass doc's body).

    `on_demand=True` (2026-11-11 — call it through `run_on_demand`): the owner's on-demand pass — an on_demand lease,
    the push gate dry, no 🏁 grade, no 1-minute clock write, reads tagged `on_demand` + `cron_setups`, its own pass doc,
    no /alerts row, and the A8 owner check before every write of its tail (see the module docstring)."""
    from chart_maps.gajjala import store as GS
    from . import alerts as AL
    from . import bars as BA
    from . import daily as DA
    from . import detectors as DT
    from . import market_state as MS
    from . import screens as SC
    from . import store as ST

    deps = deps or Deps()
    now = GR._utc(now)
    out = _new_out(now, dry)
    on_demand = bool(on_demand)
    if on_demand:
        out["on_demand"] = True                                 # the cron summary keys stay as they were
    calls = out["calls"]
    session = now.astimezone(ET).date()
    iso = session.isoformat()
    if not in_window(now):                                      # 1 the window
        out["reason"] = "outside the pass window"
        return out
    st = store or (ST.dry_store() if dry else ST.default())
    if on_demand:                                               # 2 the lease (LukStore._lease_nums)
        claim = st.claim_lease(now, source=GS.LEASE_ON_DEMAND)  # free only; never stamps the cron gap clock
    else:                                                       # a running on-demand holder never costs a cron pass
        claim = st.claim_lease(now, source=GS.LEASE_CRON, take_over=True)
    out["lease"] = {"why": getattr(claim, "why", "claimed" if claim else "held"),
                    "held_by": getattr(claim, "held_by", None)}
    if not claim:
        out["reason"] = _LEASE_REASON.get(out["lease"]["why"], _LEASE_REASON["held"])
        return out
    token = getattr(claim, "token", None)
    guard_on = on_demand and not getattr(st, "dry", False)

    def mine() -> None:
        """A8 (🚩's pattern): before every write of an on-demand pass's tail — raise _Superseded once the token is not
        ours. A raising owner read fails closed (the pass stops writing)."""
        if not guard_on:
            return
        try:
            ok = st.lease_owner_is(token)
        except Exception:                                       # noqa: BLE001
            ok = False
        if not ok:
            raise _Superseded()

    t0 = deps.clock()
    load_day = _counted(deps.load_day, calls,
                        lambda a, k: "minute_today" if _day_of(a, k) == session else "minute_prior")
    fetch = _counted(deps.fetch, calls, "daily_fetch")
    try:
        out["ran"] = True
        calls["snapshot"] += 1                                  # 3 ONE whole-market snapshot
        rows, meta = deps.snapshot()
        rows = rows or {}
        out["snapshot"] = {"http": (meta or {}).get("http"), "wall_s": (meta or {}).get("wall_s"), "n": len(rows)}
        types = deps.types() or {}                              # 4 the stored type map (READ only)
        universe = {}                                           # 5 CS / ADRC with a numeric price
        for sym, row in rows.items():
            if isinstance(row, dict) and types.get(sym) in LC.LUK_INSTRUMENT_TYPES:
                px = _price(row)
                if px is not None:
                    universe[str(sym).upper()] = row
        want = [s.strip().upper() for s in (symbols or []) if s and s.strip()]
        prices_by = {s: _price(r) for s, r in universe.items()}
        calls["caps"] += 1                                      # 6 caps, cache only
        caps = deps.caps(list(universe), prices_by) or {}
        priority = sorted(universe, key=lambda s: (-abs(_num(universe[s].get("change_pct")) or 0.0), s))
        warm = DA.warm(st, session, priority, now=now, cap_new=LC.LUK_DAILY_MAX_NEW_PER_PASS,   # 7 daily facts
                       budget_sec=LC.LUK_DAILY_WARM_BUDGET_SEC, clock=deps.clock, cached=deps.cached, fetch=fetch)
        facts = warm.get("facts") or {}
        rows_by = {s: SC.row_of(s, universe[s], facts.get(s), caps.get(s), iso) for s in universe}   # 8 screens
        lists = {"premarket": SC.premarket(list(rows_by.values())), "leader": SC.leader(list(rows_by.values())),
                 "potent": SC.potent(list(rows_by.values()))}
        screened = sum(1 for s in universe if facts.get(s))
        out["screens"] = {"premarket_n": len(lists["premarket"]), "leader_n": len(lists["leader"]),
                          "potent_n": len(lists["potent"]), "screened_n": screened,
                          "not_screened_n": len(universe) - screened,
                          "daily": {k: warm.get(k) for k in ("doc_hits", "computed", "fetched", "deferred",
                                                             "untrusted", "no_frame")}}
        mine()
        st.upsert_screens(session, now, dict(lists, counts=dict(out["screens"])))
        mine()                                                  # the index step caches LUK_STATE_INDEX in `st`
        try:                                                    # 9 the index state words (a fault is no strip)
            loader = _counted(deps.index_loader or DA.default_index_loader(session), calls, "index")
            out["market_state"] = MS.block(DA.index_state(session, loader=loader, store=st, now=now))
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk pass: market state failed: %s", type(exc).__name__)
            out["errors"].append("market_state")
            out["market_state"] = None
        today_docs = [d for d in (st.reads(session) or []) if isinstance(d, dict)]   # read ONCE per pass (2026-11-12)
        names, capped_n = SC.shortlist(lists, _carried(st, session, today_docs=today_docs))   # 10 the shortlist
        if want:
            names, capped_n = want, 0
        out["shortlist"] = {"n": len(names), "capped_n": capped_n, "symbols": list(names)}
        stats: dict = {}                                        # 11 closed frames, the pass budget left
        budget = max(0.0, LC.LUK_PASS_BUDGET_SEC - (deps.clock() - t0))
        frames = BA.frames_for(names, session, now, load_day=load_day, budget_sec=budget, stats=stats) or {}
        out["bars"] = {k: stats.get(k, 0) for k in ("loaded", "no_bars", "failed", "over_budget")}
        prev_t1, prev_t5 = prev_bars_through(st.get_state(LC.LUK_STATE_BARS_THROUGH), iso)   # 12 the reads
        reads: dict = {}
        states = {k: 0 for k in STATE_KEYS}
        aplus: list = []
        rank = {}
        for key, lst in lists.items():
            for r in lst:
                if isinstance(r, dict) and r.get("symbol"):
                    rank.setdefault(str(r["symbol"]).upper(), {})[key] = r.get("rank")
        t1 = t5 = None
        prior: dict = {}
        ring_docs: dict = {}                                    # 2026-11-12 [C4]: this pass's ring reads, in memory
        if on_demand:                                           # the last CRON setups each on-demand read carries
            prior = {str(d["symbol"]).upper(): d for d in today_docs if d.get("symbol")}
        for sym, F in frames.items():
            try:
                setups = DT.read_all(F, facts.get(sym), iso, prev_through_1m=prev_t1) or {}
            except Exception as exc:                            # noqa: BLE001
                log.warning("luk pass: read failed for %s: %s", sym, type(exc).__name__)
                out["errors"].append(f"read:{sym}")
                continue
            reads[sym] = setups
            for setup, r in setups.items():
                s = (r or {}).get("state")
                if s in states:
                    states[s] += 1
                if s == "aplus":
                    aplus.append({"symbol": sym, "setup": setup, "entry_bar_t": r.get("entry_bar_t")})
            t1 = _later(t1, BA.latest_closed_t(F, "1m"))
            t5 = _later(t5, BA.latest_closed_t(F, "5m"))
            body = _read_body(sym, F, setups, facts.get(sym), rank, rows_by)
            if on_demand:
                pd_ = prior.get(sym) or {}
                body["on_demand"] = True
                body["cron_setups"] = _cron_setups(pd_)
            mine()
            st.upsert_read(session, sym, body, now=now)
            ring_docs[sym] = dict(body, date=iso, symbol=sym, updated_at=now, at=now)   # memory only [C4]
        out["n_read"] = len(reads)
        out["states"] = states
        out["aplus"] = aplus
        try:                                                    # 13 the SHADOW gate
            out["alerts"] = AL.run_pass(reads, frames, now, session, store=st, dry=dry or on_demand,
                                        ctx={s: {"price": prices_by.get(s)} for s in reads})
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk pass: shadow gate failed: %s", type(exc).__name__)
            out["errors"].append("alerts")
        try:                                                    # 13b the board re-read (display only — rings nothing)
            if not LC.LUK_REREAD_SHOWN:
                out["refresh"] = _refresh_skipped(SKIP_REFRESH_OFF)
            elif want:
                out["refresh"] = _refresh_skipped(SKIP_REFRESH_SYMBOLS)
            else:
                out["refresh"] = _board_reread(st, session, now, today_docs=today_docs, ring_docs=ring_docs,
                                               names=names, facts=facts, rows_by=rows_by, rank=rank, prev_t1=prev_t1,
                                               load_day=load_day, deps=deps, t0=t0, on_demand=on_demand, mine=mine,
                                               errors=out["errors"])
        except _Superseded:
            raise                                               # the on-demand A8 stop — never swallowed (critique C1)
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk pass: board re-read failed: %s", type(exc).__name__)
            out["errors"].append("refresh")
            out["refresh"] = _refresh_skipped(SKIP_REFRESH_ERROR)
        out["ledger"] = None                                    # 14 the 🏁 grade step (none on a dry / on-demand run)
        if not dry and not on_demand:
            try:
                from . import ledger as LG
                out["ledger"] = LG.grade_step(st, now, load_day=deps.grade_load_day, fetch_daily=None,
                                              max_loads=LC.LUK_GRADE_MAX_LOADS, budget_sec=LC.LUK_GRADE_BUDGET_SEC,
                                              clock=deps.clock)
            except Exception as exc:                            # noqa: BLE001
                log.warning("luk pass: grade step failed: %s", type(exc).__name__)
                out["errors"].append("ledger")
        t1, t5 = _later(prev_t1, t1), _later(prev_t5, t5)      # 15 the next pass's 1-minute clock (never backwards)
        if not on_demand:                                       # an on-demand pass never moves the cron's clock
            st.set_state(LC.LUK_STATE_BARS_THROUGH, {"session": iso, "t1": t1, "t5": t5, "at": now})
        out["bars_through"] = {"t1_et": _hhmm(t1), "t5_et": _hhmm(t5)}
        out["status"] = "ok" if (out["snapshot"].get("http") == 200 and rows) else "failed"
    except _Superseded:
        out["superseded"] = 1
        out["status"] = "superseded"
        out["reason"] = _SUPERSEDED
        log.info("luk on-demand pass: %s", _SUPERSEDED)
    except Exception as exc:                                    # noqa: BLE001
        log.exception("luk pass failed")
        out["errors"].append(type(exc).__name__)
        out["status"] = "error"
    finally:
        out["wall_s"] = round(deps.clock() - t0, 3)
        _finish(st, now, session, out, deps, token, on_demand=on_demand)   # 16 the pass doc + the /alerts row → release
    return out


def run_on_demand(now: Optional[datetime] = None, *, store=None, deps: Optional[Deps] = None,
                  dry: bool = False) -> dict:
    """CONTRACT — 🔄 the owner's on-demand pass (Ajay 2026-11-11: "Can you put an ondeman scan button for Luk' scans
    too") = run_pass(on_demand=True). Runs ONLY in its own process (`python -m chart_maps.luk.run --on-demand`, spawned by
    chart_maps/luk/on_demand.py). `dry` = `--on-demand --dry-run` (the summary then says `dry` True, as a cron dry run
    does). -> the run_pass summary (+ `on_demand`)."""
    return run_pass(now, store=store, deps=deps, dry=dry, on_demand=True)


def _finish(st, now: datetime, session: date, out: dict, deps: Deps, token: Optional[str], *,
            on_demand: bool = False) -> None:
    if on_demand:
        _finish_on_demand(st, now, session, out, token)
        return
    body = {k: out.get(k) for k in _BODY_KEYS}
    try:
        st.record_pass(session, now, body)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk pass: pass doc failed: %s", exc)
    counts = dict(out.get("alerts") or {})
    counts.update({"candidates": out.get("n_read") or 0, "shortlist": (out.get("shortlist") or {}).get("n") or 0})
    reason = None if out.get("status") == "ok" else (
        "snapshot failed" if out.get("status") == "failed" else "pass error: " + ", ".join(out.get("errors") or []))
    try:
        deps.record_status(counts, now, reason)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk pass: /alerts row failed: %s", exc)
    try:
        st.release_lease(now, token)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk pass: lease release failed: %s", exc)


def _finish_on_demand(st, now: datetime, session: date, out: dict, token: Optional[str]) -> None:
    """An on-demand pass's end (2026-11-11): the A8 owner check again before the pass doc (a body that raised after a
    take-over never reached its last `mine()`); superseded → NO pass doc. Else its OWN doc "{date}|{HH:MM:SS}|on_demand"
    (+ `on_demand`, `finished_at`), source on_demand (never "latest_cron"), "latest" moved only forward and only on an ok
    pass; NO /alerts row. The release is token-guarded and stamps the real finish (`done_at` = start + wall — the
    trigger's reuse check reads it): after a real take-over it frees nothing; after a failed owner read it frees its own
    lease."""
    from chart_maps.gajjala import store as GS
    finished = now + timedelta(seconds=float(out.get("wall_s") or 0))
    if not out.get("superseded") and not getattr(st, "dry", False):
        try:
            ok = st.lease_owner_is(token)
        except Exception:                                       # noqa: BLE001
            ok = False
        if not ok:
            out["superseded"] = 1
            out["status"] = "superseded"
            out["reason"] = _SUPERSEDED
            log.info("luk on-demand pass: %s", _SUPERSEDED)
    if not out.get("superseded"):
        body = {k: out.get(k) for k in _BODY_KEYS}
        body.update(on_demand=True, finished_at=finished)
        try:
            st.record_pass(session, now, body,
                           hhmm=now.astimezone(ET).strftime("%H:%M:%S") + "|" + ON_DEMAND_PASS_SUFFIX,
                           source=GS.LEASE_ON_DEMAND, latest_if_newer=True, move_latest=(out.get("status") == "ok"))
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk on-demand pass: pass doc failed: %s", exc)
    try:
        st.release_lease(finished, token)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk on-demand pass: lease release failed: %s", exc)


# ── the child ────────────────────────────────────────────────────────────────────────────────────────────────────
def spawn_child(spawn: Optional[Callable] = None) -> bool:
    """Start `python -m chart_maps.luk.run --child` DETACHED (`spawn(argv, name)`, default gajjala.run_1m._popen —
    a new session, close_fds). True when started; never raises (False)."""
    try:
        if spawn is None:
            from chart_maps.gajjala import run_1m as R1
            spawn = R1._popen
        proc = spawn(list(ARGV_CHILD), PROC_NAME)
        log.debug("luk pass: %s pid %s", PROC_NAME, getattr(proc, "pid", None))
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.debug("luk pass: spawn raised %s", type(exc).__name__)
        return False


def child_refusal(now: Optional[datetime] = None) -> Optional[str]:
    """Why a --child must not run now (None = run): the switch, the window, the slot."""
    if not enabled():
        return SKIP_OFF
    if not in_window(now):
        return SKIP_WINDOW
    start = GR._utc(now)
    if not fits(start, slot_of(start)[1]):
        return SKIP_SLOT
    return None


def _skip(store, now: datetime, reason: str) -> None:
    try:
        store.set_state(CHILD_STATE_ID, {"state": "skipped", "reason": reason, "at": GR._utc(now)})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk pass: skipped-state write failed: %s", exc)


def main(argv=None, *, store=None, deps: Optional[Deps] = None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.luk.run", description=__doc__.split("\n")[0])
    ap.add_argument("--child", action="store_true", help="the cron child (gajjala.run._spawn_luk spawns this)")
    ap.add_argument("--dry-run", action="store_true", help="record every write; touch nothing; prints `calls`")
    ap.add_argument("--json", action="store_true", help="print the pass summary as JSON")
    ap.add_argument("--now", help="ISO clock to replay (a naive stamp is ET); refused without --dry-run")
    ap.add_argument("--symbols", help="comma list: narrow the names read")
    ap.add_argument("--on-demand", action="store_true",
                    help="the owner's on-demand pass: push gate dry, no 🏁 grade, no 1-minute clock write — 2026-11-11")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ET)                            # a naive --now is ET (the house rule), never UTC
    if args.now and not args.dry_run:
        log.warning("luk pass: a --now replay records on the real store unless --dry-run; refusing")
        return 2
    if args.on_demand and args.child:
        log.warning("luk pass: --on-demand and --child are two different passes; refusing")
        return 2
    syms = [s.strip() for s in (args.symbols or "").split(",") if s.strip()] or None
    from . import store as ST
    if args.dry_run:
        st = store if store is not None else ST.dry_store()
        if args.on_demand:
            out = run_on_demand(now, store=st, deps=deps or dry_deps(), dry=True)
        else:
            out = run_pass(now, store=st, deps=deps or dry_deps(), dry=True, symbols=syms)
        out["writes"] = sorted({w[0] for w in (getattr(st, "writes", None) or [])})
        if not args.json:
            print(json.dumps(out.get("calls"), default=str))
    else:
        st = store if store is not None else ST.default()
        if args.child:
            why = child_refusal(now)
            if why:
                log.info("luk pass: child skipped — %s", why)
                _skip(st, now or GR._utc(None), why)
                return 0
        if args.on_demand:                                      # the switch and the window ONLY — never `fits` (the
            why = SKIP_OFF if not enabled() else SKIP_WINDOW if not in_window(now) else None   # parent decided the slot)
            if why:
                log.info("luk on-demand: skipped — %s", why)    # no lease, no child state doc (that one is the cron's)
                return 0
        try:
            st.ensure_indexes()
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk pass: indexes failed: %s", type(exc).__name__)
        if args.on_demand:
            out = run_on_demand(now, store=st, deps=deps or Deps())
        else:
            out = run_pass(now, store=st, deps=deps or Deps(), symbols=syms)
    if args.json:
        print(json.dumps(out, default=str))
    elif args.on_demand:
        log.info("luk on-demand pass: %s", {k: out.get(k) for k in ("ran", "status", "n_read", "wall_s", "lease",
                                                                    "reason")})
    else:
        log.info("luk pass: %s", {k: out.get(k) for k in ("ran", "status", "n_read", "alerts", "wall_s", "lease",
                                                          "reason")})
    return 1 if out.get("status") == "error" else 0


__all__ = ["ARGV_CHILD", "PROC_NAME", "CALL_KEYS", "enabled", "in_window", "fits", "slot_of", "Deps", "dry_deps",
           "run_pass", "run_on_demand", "prev_bars_through", "spawn_child", "child_refusal", "main",
           "REFRESH_KEYS", "SKIP_REFRESH_OFF", "SKIP_REFRESH_SYMBOLS", "SKIP_REFRESH_ERROR"]


if __name__ == "__main__":
    sys.exit(main())
