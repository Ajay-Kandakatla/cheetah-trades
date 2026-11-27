"""📅 Runners kept on the 👀 Watch for two weeks — the ONE seating engine (2026-11-26, spec watchrun rev 2 §3.2, WP-1).

Ajay 2026-11-26 ~21:40 ET, verbatim: "Ok then add them to our watch list and track them please.. I know he tracks them
for two weeks sometimes.. before he discards them.. Can you do that please" · ~21:50 ET (asked whether A+ names belong in
the section too): "Make it 30% please after A+".

WHAT. Once a minute, at the END of the Watch loop's iteration (after the frames, the tile writes and the `latest` state
write, on what is left of the minute budget), `step` keeps a FOURTH doc `{_id: C.RUNNERS_DOC_ID}` in the list collection
(the owner, 🤖 and ✅ docs are never written here). Every COMPLETED session of `keep_window` is judged once under the live
reading (`reading()`; `processed` is keyed by reading, so a flip re-reads the window and only ADDS):
  * a name with no 🚩 A+ related to that session → `runners.ran_of` at `day_cut()` (+40% vs the prior close, the peak
    not premarket) — and only when the prior close is a traded one: no listed split that day (the scanner's stored
    check, else the house split lookup) and a daily bar before that session (the scanner's stored daily record);
  * a 🚩 A+ (the 5-minute or the retired 1-minute page — C.RUNNERS_SEAT_PAGES) → a 1-minute high at or over the trigger
    × (1 + C.RUNNERS_SEAT_APLUS_PCT/100) between max(ring + SETTLE, 09:45 ET) and 20:00 ET of the session the Track record
    grades it on (`from_trigger` — the app twin of the pipeline's replay_win30.measure, pinned by a test), never across a
    split between the ring and the day its 1-minute bars were fetched.
Kept C.RUNNERS_KEEP_SESSIONS sessions from the run day (run day = day 1); a new qualifying day restarts the count
(C.RUNNERS_SEAT_RESTART); then "aged". Uncapped, never rings, 🚫 names kept and sorted last.

PROVIDER. Stored reads first; a 1-minute day that is not cached and a split check the scanner's record cannot answer are
provider reads, bounded per step by `_Provider` (C.RUNNERS_SEAT_PROVIDER_MAX started reads, the time left in the minute,
stop at the first failure, this module's OWN breaker). A pending item that failed is asked again only on a later session.

HIS ×. The roster's own × (`dismiss`, its own route) blocks that run day and that session in THIS doc only. A tile × (the
plain DELETE) never touches this doc; its pairs (the ✅ doc's and the 🤖 doc's) block a run of the same day, and that run
is written to `removed` with reason "blocked" so the nightly record still follows it.

Any read fault writes nothing. ONE compare-and-set per step. Display / tracking only. UNMEASURED.
"""
from __future__ import annotations

import copy
import functools
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as L
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import variant as V

from . import allrules as RULES
from . import auto as AUTO
from . import colls as CO
from . import constants as C
from . import runners as RN
from .store import _CAS_TRIES

log = logging.getLogger("chart_maps.gajjala_watch.runseat")
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

_UNREAD = object()                                             # step: "read the auto doc yourself"
BY_LOOP = AUTO.BY_LOOP
FROM_TRIGGER_KEYS = ("measured", "passed", "trigger", "from_et", "to_et", "high_px", "high_et", "run_pct", "why")
_LOCK = threading.Lock()
_BREAKER: Optional[dict] = None


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _as_date(x) -> Optional[date]:
    return RULES._as_date(x)


def _u(t) -> Optional[datetime]:
    return RULES._u(t)


def _norm(x):
    """A deep copy with every datetime as aware UTC cut to the millisecond (what Mongo keeps) — so a doc read back
    compares equal to the one it was written from."""
    if isinstance(x, datetime):
        return _u(x)
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    return copy.deepcopy(x)


def _next(d: date) -> date:
    return L._next_market_day(d)


def _prev(d: date) -> date:
    return L._prev_market_day(d)


def _hhmm_et(t: Optional[datetime]) -> Optional[str]:
    return t.astimezone(ET).strftime("%H:%M") if isinstance(t, datetime) else None


def _today_et(now) -> date:
    return RUN._utc(now).astimezone(ET).date()


def _dayword(d: date) -> str:
    return f"{RN._dayword(d)} {RN._md(d)}"


def _px(x) -> str:
    try:
        return L._px(x)
    except Exception:                                           # noqa: BLE001
        return f"{x:g}" if isinstance(x, (int, float)) else str(x)


# ── the cut and the split by reading ─────────────────────────────────────────────────────────────────────────────
def reading() -> str:
    """C.RUNNERS_SEAT_READING when it is one of C.RUNNERS_SEAT_READINGS, else the first (fail closed to his 11-26
    reading). Read at CALL time."""
    r = C.RUNNERS_SEAT_READING
    return r if isinstance(r, str) and r in C.RUNNERS_SEAT_READINGS else C.RUNNERS_SEAT_READINGS[0]


def day_cut() -> float:
    """float(C.RUNNERS_SEAT_APLUS_PCT) under "seat_cut", else C.RUNNERS_SEAT_DAY_PCT."""
    return float(C.RUNNERS_SEAT_APLUS_PCT) if reading() == C.RUNNERS_SEAT_READINGS[1] else float(C.RUNNERS_SEAT_DAY_PCT)


def aplus_rule_on() -> bool:
    return reading() in (C.RUNNERS_SEAT_READINGS[0], C.RUNNERS_SEAT_READINGS[2])


def day_rule_skips_related() -> bool:
    return reading() == C.RUNNERS_SEAT_READINGS[0]


def day_counts(r, cut=None) -> bool:
    """r = runners.ran_of(...): run_pct >= cut and the peak not premarket. At cut == C.RAN_MIN_PCT it EQUALS
    r["counts"] (a test pins it)."""
    if not isinstance(r, dict):
        return False
    c = day_cut() if cut is None else float(cut)
    p = RN._fin(r.get("run_pct"))
    return p is not None and p >= c and not r.get("premarket_peak")


# ── the run from the A+ trigger (PURE — no split knowledge; the guard sits in the step) ─────────────────────────────
def play_day(ring_date, at_utc) -> date:
    """The session the Track record grades the ring on (ledger.session_bounds same_date; the pipeline's play_day)."""
    return L.session_bounds(_as_date(ring_date), at_utc)["same_date"]


def measure_start(day: date, at_utc: datetime) -> datetime:
    """max(ring + ledger.SETTLE, the fill window's start (09:45 ET) of `day`) — aware UTC (replay_gif.measure_start)."""
    opens = datetime.combine(day, L.fill_window(day)[0], tzinfo=ET).astimezone(UTC)
    at = at_utc if at_utc.tzinfo else at_utc.replace(tzinfo=UTC)
    return max(at.astimezone(UTC) + L.SETTLE, opens)


def measure_end(day: date) -> datetime:
    """20:00 ET of `day` (daytrading.data.ET_AFTERHOURS_CLOSE) — aware UTC."""
    from daytrading.data import ET_AFTERHOURS_CLOSE
    return datetime.combine(day, ET_AFTERHOURS_CLOSE, tzinfo=ET).astimezone(UTC)


def reaches(high, trigger, pct=None) -> bool:
    """high >= trigger × (1 + pct/100), exact on decimals (0.9 → 1.17 passes). `pct` None = C.RUNNERS_SEAT_APLUS_PCT
    read at call time (replay_win30.reaches)."""
    p = C.RUNNERS_SEAT_APLUS_PCT if pct is None else pct
    return Decimal(repr(float(high))) * 100 >= Decimal(repr(float(trigger))) * (100 + Decimal(str(p)))


def from_trigger(bars_1m, day, at_utc, trigger, *, pct=None) -> dict:
    """The run from the A+ trigger on `day` (its play day). `bars_1m` = ledger.bars_from_frame rows (t_utc START, o, h,
    l, c). Window = bars with start <= t < end; the high = the FIRST minute printing the max. Keys FROM_TRIGGER_KEYS;
    every number finite or None."""
    out = {k: None for k in FROM_TRIGGER_KEYS}
    out.update(measured=False, passed=False, why="")
    t = RN._fin(trigger)
    if t is None or t <= 0:
        out["why"] = "aplus_no_trigger"
        return out
    out["trigger"] = t
    d = _as_date(day)
    if not isinstance(at_utc, datetime) or d is None:
        out["why"] = "aplus_no_time"
        return out
    from daytrading.data import ET_AFTERHOURS_CLOSE
    start, end = measure_start(d, at_utc), measure_end(d)
    out.update(from_et=_hhmm_et(start), to_et=ET_AFTERHOURS_CLOSE.strftime("%H:%M"))
    best = None
    for b in bars_1m or []:
        try:
            ts, hi = b[0], RN._fin(b[2])
        except (TypeError, IndexError):
            continue
        if not isinstance(ts, datetime) or hi is None:
            continue
        ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        if start <= ts < end and (best is None or hi > best[0] or (hi == best[0] and ts < best[1])):
            best = (hi, ts)
    if best is None:
        out["why"] = "aplus_no_bars"
        return out
    hp, ht = best
    out.update(measured=True, passed=reaches(hp, t, pct), high_px=hp, high_et=_hhmm_et(ht),
               run_pct=RN._fin(round((hp / t - 1) * 100, 1)))
    out["_raw_pct"] = RN._fin(round((hp / t - 1) * 100, C.RAN_PCT_ROUND))   # the run's stored value + the floored
    #   prints' source: the house rounding (scanner change_pct, [D5]) only, so 0.9 → 1.17 stays 30.0 and 34.96 is never 35.0
    return out


# ── the guards (house engines only, no new number) ──────────────────────────────────────────────────────────────
def split_look(st) -> Callable:
    """ledger._default_split_lookup(st): look(sym, after, through) → True | "YYYY-MM-DD" | False | None."""
    return L._default_split_lookup(st)


def split_is_stored(checks_by_day, sym, after, through) -> bool:
    """True when the house lookup answers from the scanner's stored record with NO provider read — its own rule
    (ledger.py: a one-session window and a stored "ok" / "held")."""
    a, t = _as_date(after), _as_date(through)
    if a is None or t is None or _next(a) != t:
        return False
    try:
        rec = (checks_by_day(t) or {}).get(str(sym).upper())
    except Exception:                                           # noqa: BLE001
        return False
    return rec in ("ok", "held")


def fetched_on(stamp, now) -> date:
    """The ET date a cached day was fetched (its `cached_at`); no stamp (a day loaded this step, an unstamped doc) →
    now's ET date (the widest window)."""
    t = CO.stamp_utc(stamp)
    return t.astimezone(ET).date() if t is not None else _today_et(now)


def prior_bar(st, sym, S) -> str:
    """"ok" | "no_prior_bar" | "prior_unknown" — the scanner's stored daily record ONLY (never a provider read)."""
    try:
        doc = st.get_daily(_as_date(S), str(sym).upper())
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 📅: daily record unreadable: %s", type(exc).__name__)
        return "prior_unknown"
    sh = doc.get("squeeze_history") if isinstance(doc, dict) else None
    if not isinstance(sh, dict):
        return "prior_unknown"
    return "ok" if sh.get("daily_ok") is True else "no_prior_bar"


# ── the provider budget ──────────────────────────────────────────────────────────────────────────────────────────
class _Provider:
    """Provider reads of ONE step: cap = C.RUNNERS_SEAT_PROVIDER_MAX started reads; deadline = clock() + budget_sec
    (None or <= 0 → NO provider read); the first failure stops every further read."""

    def __init__(self, budget_sec, clock=time.monotonic):
        self.clock = clock
        b = RN._fin(budget_sec)
        self.off = b is None or b <= 0
        self.deadline = clock() + (b if not self.off else 0.0)
        self.started = 0
        self.failed = False                                     # a provider read failed this step
        self.stopped = False                                    # no further read this step (a failure or the clock)
        self.over_budget = 0

    def may(self) -> bool:
        if self.off or self.stopped or self.started >= int(C.RUNNERS_SEAT_PROVIDER_MAX):
            return False
        return self.clock() <= self.deadline

    def left(self) -> float:
        return max(0.0, self.deadline - self.clock()) if not self.off else 0.0

    def used(self, ok: bool) -> None:
        self.started += 1
        if not ok:
            self.failed = self.stopped = True

    def ran_out(self) -> None:
        """load_days' over_budget on a cold day: spec §3.2 — "failed" / "over_budget" → used(False). Counted in
        `started`, marks the step failed (no further read), and the item is stamped `tried` (asked next session)."""
        self.over_budget += 1
        self.used(False)

    def summary(self) -> dict:
        return {"started": self.started, "failed": self.failed, "over_budget": self.over_budget}


def _breaker() -> dict:
    """This module's OWN breaker (the runchart.breaker() / rest.breaker() shape): built once under _LOCK with
    daytrading.data.new_breaker(). Never the module breaker, never the Watch's, never the chart's."""
    global _BREAKER
    b = _BREAKER
    if b is not None:
        return b
    with _LOCK:
        if _BREAKER is None:
            from daytrading import data as dt_data
            _BREAKER = dt_data.new_breaker()
        return _BREAKER


def _default_load_1m(sym, day: date, budget_sec: float) -> tuple:
    """(bars | None, status) — runchart.load_days on ONE day with this module's own breaker, then
    ledger.bars_from_frame. status ∈ loaded | no_bars | failed | over_budget."""
    from daytrading import data as dt_data
    from . import runchart as RC
    parts, status = RC.load_days(sym, [day], budget_sec=budget_sec,
                                 load_day=functools.partial(dt_data.load_intraday, cb=_breaker()))
    st = status.get(day.isoformat(), "failed")
    if st != "loaded":
        return None, st
    bars = L.bars_from_frame(parts.get(day.isoformat()))
    return (bars, "loaded") if bars else (None, "no_bars")


def _default_cached_at(sym, isos) -> dict:
    from . import runchart as RC
    return RC.cached_at(sym, isos)


# ── the window and the doc ───────────────────────────────────────────────────────────────────────────────────────
def keep_window(session) -> list:
    """The last C.RUNNERS_KEEP_SESSIONS market sessions, today included, oldest first —
    context.history_window(next_market_day(d), N) (the ✅ engine's rule, this engine's number)."""
    d = _as_date(session)
    if d is None:
        return []
    from catalysts.medical.reaction import next_market_day
    from chart_maps.gajjala import context as CX
    return list(CX.history_window(next_market_day(d), C.RUNNERS_KEEP_SESSIONS))


def _win_isos(session) -> list:
    return [d.isoformat() for d in keep_window(session)]


def day_n(run_day, session) -> Optional[int]:
    """1 + market sessions after `run_day` through `session`; None when run_day is outside keep_window(session)."""
    isos = _win_isos(session)
    rd = _as_date(run_day)
    if rd is None or rd.isoformat() not in isos:
        return None
    return len(isos) - isos.index(rd.isoformat())


def window_last(run_day) -> Optional[date]:
    """The last session of a run's window (run day = day 1, C.RUNNERS_KEEP_SESSIONS days in all)."""
    d = _as_date(run_day)
    if d is None:
        return None
    for _ in range(max(0, int(C.RUNNERS_KEEP_SESSIONS) - 1)):
        d = _next(d)
    return d


def read_doc(cs) -> Optional[dict]:
    """The runners doc ({} when missing); None on a read fault. Never raises."""
    c = cs.get("list") if isinstance(cs, dict) else None
    if c is None:
        return None
    try:
        d = c.find_one({"_id": C.RUNNERS_DOC_ID})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 📅: runners doc unreadable: %s", type(exc).__name__)
        return None
    return d if isinstance(d, dict) else {}


def _entries(doc) -> list:
    out, keys = [], set()
    for e in (doc.get("entries") if isinstance(doc, dict) else None) or []:
        if not (isinstance(e, dict) and isinstance(e.get("symbol"), str) and e["symbol"].strip()
                and isinstance(e.get("run_day"), str)):
            continue
        k = CO.fold(e["symbol"])
        if k in keys:
            continue
        keys.add(k)
        out.append(_norm(e))
    return out


def _list(doc, key) -> list:
    return [_norm(r) for r in ((doc.get(key) if isinstance(doc, dict) else None) or [])
            if isinstance(r, dict) and isinstance(r.get("symbol" if key != "pending" else "key"), str)]


def _map(doc, key) -> dict:
    m = doc.get(key) if isinstance(doc, dict) else None
    return {k: _norm(v) for k, v in m.items() if isinstance(k, str) and isinstance(v, dict)} if isinstance(m, dict) else {}


def entries_in_window(doc, session) -> list:
    isos = set(_win_isos(session))
    return [e for e in _entries(doc) if e.get("run_day") in isos]


def current_symbols(cs, session) -> list:
    if not C.RUNNERS_SEAT_ON:
        return []
    doc = read_doc(cs)
    return [CO.house(e["symbol"]) for e in entries_in_window(doc, session)] if doc else []


def blocked(doc, rules_doc, auto_prior, session) -> set:
    """{(FOLD, ISO)}: this doc's `dismissed` → (fold, session) AND (fold, run_day); ∪ the ✅ doc's `dismissed` pairs
    (it already carries the 🤖 × with via "auto"); ∪ the 🤖 doc's `dismissed` of ITS session. Window-pruned."""
    win = set(_win_isos(session))
    out = set()
    for r in _list(doc, "dismissed"):
        for k in ("session", "run_day"):
            s = r.get(k)
            if isinstance(s, str) and s in win:
                out.add((CO.fold(r["symbol"]), s))
    for r in RULES._pairs_list(rules_doc if isinstance(rules_doc, dict) else {}, "dismissed"):
        s = r.get("session")
        if isinstance(s, str) and s in win:
            out.add((CO.fold(r["symbol"]), s))
    ps = auto_prior.get("session") if isinstance(auto_prior, dict) else None
    if isinstance(ps, str) and ps in win:
        for s in auto_prior.get("dismissed") or []:
            if isinstance(s, str) and s.strip():
                out.add((CO.fold(s), ps))
    return out


# ── the rings ────────────────────────────────────────────────────────────────────────────────────────────────────
def _default_stores() -> dict:
    """{page: store} — GG5 → store.default(), the retired 1-minute page → store.for_variant(V.GG1) (its rings still
    count — HIS CALL #7)."""
    from chart_maps.gajjala import store as GST
    return {V.GG5.key: GST.default(), V.GG1.key: GST.for_variant(V.GG1)}


def aplus_rings(dates, *, stores) -> list:
    """Every 🚩 A+ ring (kind aplus, lines live / shadow) of `dates` on each page of C.RUNNERS_SEAT_PAGES —
    {id, page, date, symbol, setup, at_utc, at_et, trigger, play_day, gg_like} (🧘 gg_like = the row's ring stamp or
    None, 2026-11-27 — a passthrough, read by nothing here). RAISES on a LedgerReadError."""
    vs = {v.key: v for v in V.VARIANTS}
    out = []
    for page in C.RUNNERS_SEAT_PAGES:
        st = (stores or {}).get(page)
        if st is None:
            raise L.LedgerReadError(f"no store for {page}")
        rows = L.rows_for(list(dates), st, variant=vs.get(page))
        for r in rows:
            if r.get("kind") != L.KINDS[1] or r.get("line") not in L.LINES[:2]:
                continue
            d = _as_date(r.get("date"))
            if d is None or not r.get("symbol"):
                continue
            at = r.get("at_utc") if isinstance(r.get("at_utc"), datetime) else None
            pd_ = play_day(d, at) if at is not None else d
            out.append({"id": r.get("id"), "page": page, "date": d.isoformat(), "symbol": str(r["symbol"]).upper(),
                        "setup": r.get("setup"), "at_utc": at, "at_et": r.get("at_et"), "trigger": r.get("trigger"),
                        "play_day": pd_.isoformat(),
                        "gg_like": r.get("gg_like")})          # 🧘 2026-11-27: the ring's frozen 🧘 block (passthrough)
    return out


# ── the minute step ──────────────────────────────────────────────────────────────────────────────────────────────
def _why_text(why, sym, iso, **kw) -> str:
    f = C.RUNNERS_SEAT_WHY.get(why)
    if not f:
        return ""
    try:
        return f.format(sym=sym, date=iso, ap=C.RUNNERS_SEAT_APLUS_PCT, **kw)
    except (KeyError, IndexError, ValueError):
        return ""


def _early(reason, symbols=(), provider=None) -> dict:
    syms = list(symbols or [])
    return {"n": len(syms), "added": [], "removed": [], "restarted": [], "processed": [], "partial": [], "pending": 0,
            "skipped": {k: 0 for k in C.RUNNERS_SEAT_SKIPS}, "not_seated": 0, "blocked": [],
            "provider": provider or {"started": 0, "failed": False, "over_budget": 0}, "reason": reason,
            "symbols": syms, "changed": False}


def _day_run(r: dict, iso: str) -> dict:
    return {"date": iso, "rule": C.RUNNERS_SEAT_RULES[0], "run_pct": r.get("run_pct"), "prev_close": r.get("prev_close"),
            "high": r.get("high"), "peak_et": r.get("peak_et"), "pm_high_pct": r.get("pm_high_pct"),
            "reg_close": r.get("reg_close"), "timing": r.get("timing")}


class _Ctx:
    """One step's reads, memoised: the scanner's split checks per day, the day reads, the provider and the answers."""

    def __init__(self, st, look, cached, load, provider, answers, stored_pending, siso, now):
        self.st, self.look, self.cached, self.load, self.provider = st, look, cached, load, provider
        self.answers, self.stored_pending, self.siso, self.now = answers, stored_pending, siso, now
        self._checks: dict = {}
        self._days: dict = {}

    def checks(self, d) -> dict:
        iso = _as_date(d).isoformat()
        if iso not in self._checks:
            try:
                self._checks[iso] = self.st.split_checks(_as_date(d)) or {}
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch 📅: split checks unreadable: %s", type(exc).__name__)
                self._checks[iso] = {}
        return self._checks[iso]

    def day(self, iso) -> tuple:
        if iso not in self._days:
            self._days[iso] = RN.read_day(self.st, iso)        # RAISES — the step answers boards_unreadable
        return self._days[iso]

    def tried_now(self, key) -> bool:
        p = self.stored_pending.get(key)
        return isinstance(p, dict) and p.get("tried") == self.siso

    def split(self, sym, after: date, through: date) -> tuple:
        """(answer, key, failed) — answer True | iso | False | None (None = not answered: pending)."""
        key = f"split|{sym}|{after.isoformat()}|{through.isoformat()}"
        if through <= after:
            return False, key, False
        hit = self.answers.get(key)
        if isinstance(hit, dict) and "v" in hit and hit["v"] is not None:
            return hit["v"], key, False
        if split_is_stored(self.checks, sym, after, through):
            try:
                return self.look(sym, after, through), key, False
            except Exception:                                   # noqa: BLE001
                return None, key, False
        if self.tried_now(key) or not self.provider.may():
            return None, key, False
        try:
            v = self.look(sym, after, through)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch 📅: split check failed for %s: %s", sym, type(exc).__name__)
            v = None
        self.provider.used(v is not None)
        if v is not None:
            self.answers[key] = {"v": v, "at": self.now, "session": None}
            return v, key, False
        return None, key, True


def _judge(S: date, ctx: _Ctx, rings: list) -> dict:
    """One completed session → {candidates: {FOLD: (sym, run)}, pending: [item], not_seated: [rec], skipped: {},
    n_scan, n_reads}."""
    iso = S.isoformat()
    scan_by, reads_by = ctx.day(iso)
    skipped = {k: 0 for k in C.RUNNERS_SEAT_SKIPS}
    pending: list = []
    not_seated: list = []
    cands: dict = {}
    related = {CO.fold(r["symbol"]) for r in rings if r["date"] == iso or r["play_day"] == iso}
    ran_by: dict = {}

    def ran(sym):
        k = CO.fold(sym)
        if k not in ran_by:
            doc = next((d for s, d in scan_by.items() if CO.fold(s) == k), None)
            s0 = next((s for s in scan_by if CO.fold(s) == k), sym)
            ran_by[k] = RN.ran_of(doc, reads_by.get(s0), S) if doc is not None else None
        return ran_by[k]

    def pend(kind, key, sym, why, failed):
        prev = ctx.stored_pending.get(key) or {}
        tried = ctx.siso if failed else (prev.get("tried") if prev.get("tried") == ctx.siso else None)
        pending.append({"kind": kind, "key": key, "symbol": sym, "session": iso, "why": why, "tried": tried})
        skipped[why] += 1

    def ns(sym, why, **kw):
        not_seated.append({"symbol": sym, "session": iso, "why": why, "text": _why_text(why, sym, iso, **kw)})
        skipped[why] += 1

    # 1. the A+ rule — every ring whose play day is S
    best: dict = {}
    under: dict = {}
    if aplus_rule_on():
        for r in rings:
            if r["play_day"] != iso:
                continue
            sym = r["symbol"]
            t = RN._fin(r.get("trigger"))
            if t is None or t <= 0:
                ns(sym, "aplus_no_trigger")
                continue
            if not isinstance(r.get("at_utc"), datetime):
                ns(sym, "aplus_no_time")
                continue
            stamp = None
            try:
                stamp = (ctx.cached(sym, [iso]) or {}).get(iso)
            except Exception:                                   # noqa: BLE001
                stamp = None
            fetched = fetched_on(stamp, ctx.now)
            v, key, failed = ctx.split(sym, _as_date(r["date"]), fetched)
            if v is None:
                pend("aplus", key, sym, "aplus_split_unchecked" if failed or ctx.tried_now(key) else "aplus_pending",
                     failed)
                continue
            if v is not False:
                on = v if isinstance(v, str) else fetched.isoformat()
                not_seated.append({"symbol": sym, "session": iso, "why": "aplus_split",
                                   "text": _why_text("aplus_split", sym, r["date"], on=on)})
                skipped["aplus_split"] += 1
                continue
            bkey = f"bars|{sym}|{iso}"
            cached = stamp is not None
            if not cached and (ctx.tried_now(bkey) or not ctx.provider.may()):
                pend("aplus", bkey, sym, "aplus_pending", False)
                continue
            try:
                bars, status = ctx.load(sym, S, ctx.provider.left() if not cached else float(GC.GG1M_MINUTE_BUDGET_SEC))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch 📅: 1-minute load failed for %s: %s", sym, type(exc).__name__)
                bars, status = None, "failed"
            if not cached:
                if status == "over_budget":
                    ctx.provider.ran_out()
                else:
                    ctx.provider.used(status in ("loaded", "no_bars"))
            if status in ("failed", "over_budget"):
                pend("aplus", bkey, sym, "aplus_pending", not cached)
                continue
            if status == "no_bars" or not bars:
                ns(sym, "aplus_no_bars")
                continue
            m = from_trigger(bars, S, r["at_utc"], t)
            if m["why"] == "aplus_no_bars":
                ns(sym, "aplus_no_bars")
                continue
            if m["passed"]:
                run = {"date": iso, "rule": C.RUNNERS_SEAT_RULES[1], "run_pct": m["_raw_pct"], "trigger": t,
                       "high_px": m["high_px"], "high_et": m["high_et"], "from_et": m["from_et"], "to_et": m["to_et"],
                       "ring_id": r.get("id"), "ring_date": r["date"], "ring_at_et": r.get("at_et"),
                       "setup": r.get("setup"), "page": r.get("page"), "fetched": fetched.isoformat(),
                       "reg_close": None, "day": None}
                k = CO.fold(sym)
                if k not in best or (run["run_pct"] or 0) > (best[k][1]["run_pct"] or 0):
                    best[k] = (sym, run)
            else:
                k = CO.fold(sym)
                if k not in under or (m.get("_raw_pct") or 0) > (under[k][1] or 0):
                    under[k] = (sym, m.get("_raw_pct"), t, r["date"])
    # 2. the day rule — every scan name (minus the A+-related ones under "after_aplus")
    skip_rel = day_rule_skips_related()
    cut = day_cut()
    day_c: dict = {}
    for sym in scan_by:
        k = CO.fold(sym)
        if skip_rel and k in related:
            continue
        r = ran(sym)
        if r is None:
            skipped["no_bars"] += 1
            continue
        if not day_counts(r, cut):
            skipped["premarket_peak" if r.get("premarket_peak") and RN._fin(r.get("run_pct")) is not None
                    and r["run_pct"] >= cut else "under_day"] += 1
            continue
        rec = (ctx.checks(S) or {}).get(sym.upper())
        if rec != "ok":
            v, key, failed = ctx.split(sym, _prev(S), S)
            if v is None:
                pend("day", key, sym, "split_unchecked", failed)
                continue
            if v is not False:
                ns(sym, "split_day")
                continue
        pb = prior_bar(ctx.st, sym, S)
        if pb != "ok":
            ns(sym, pb)
            continue
        day_c[k] = (sym, _day_run(r, iso))
    # 3. one run per (symbol, S): an "aplus" candidate wins and keeps the day facts
    for k, (sym, run) in best.items():
        r = ran(sym)
        if r is not None:
            run["reg_close"] = r.get("reg_close")
        if k in day_c:
            run["day"] = day_c.pop(k)[1]
        cands[k] = (sym, run)
    for k, v in day_c.items():
        cands[k] = v
    # 4. not seated: an A+-related name that ran at C.RAN_MIN_PCT with no seat (its ring under the bar)
    for k, (sym, raw, trig, rdate) in under.items():
        if k in cands:
            continue
        r = ran(sym)
        counted = isinstance(r, dict) and r.get("counts")
        if not counted and rdate != iso:
            try:
                sb, rb = ctx.day(rdate)
                doc = next((d for s, d in sb.items() if CO.fold(s) == k), None)
                s0 = next((s for s in sb if CO.fold(s) == k), sym)
                r0 = RN.ran_of(doc, rb.get(s0), _as_date(rdate)) if doc is not None else None
                counted = isinstance(r0, dict) and r0.get("counts")
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch 📅: ring-day reads unreadable: %s", type(exc).__name__)
        if counted:
            ns(sym, "aplus_under", trigger=_px(trig), pct=RN.pct_show(raw) or "—")
        else:
            skipped["aplus_under"] += 1
    n_reads = sum(1 for s in scan_by if s in reads_by)
    return {"candidates": cands, "pending": pending, "not_seated": not_seated, "skipped": skipped,
            "n_scan": len(scan_by), "n_reads": n_reads}


def _removed_rec(entry: dict, now, iso, reason, text=None) -> dict:
    return {"symbol": entry["symbol"], "at": now, "at_et": _hhmm_et(now), "session": iso, "reason": reason,
            "text": text, "entry": copy.deepcopy(entry)}


def _removed_keys(removed) -> set:
    return {(CO.fold(r["symbol"]), (r.get("entry") or {}).get("run_day")) for r in removed}


def _apply(doc, now, siso, judged: dict, blk: set, read_isos: list, win: list, answers: dict, future=()) -> tuple:
    """Steps 6–7 + the prune → (result, new fields)."""
    winset = set(win)
    entries = _entries(doc)
    dismissed = _list(doc, "dismissed")
    removed = _list(doc, "removed")
    processed = _map(doc, "processed")
    pend0 = _list(doc, "pending")
    ns0 = _list(doc, "not_seated")
    stored = _norm({"entries": entries, "dismissed": dismissed, "removed": removed, "processed": processed,
                    "pending": pend0, "answers": _map(doc, "answers"), "not_seated": ns0})
    by = {CO.fold(e["symbol"]): e for e in entries}
    rk = _removed_keys(removed)
    added, restarted, blocked_now, gone = [], [], [], []
    skipped = {k: 0 for k in C.RUNNERS_SEAT_SKIPS}
    new_pending, new_ns, done = [], [], []
    partial = []
    rd = reading()
    for iso in read_isos:
        j = judged[iso]
        for k2, v in j["skipped"].items():
            skipped[k2] += v
        new_pending += j["pending"]
        new_ns += j["not_seated"]
        for k, (sym, run) in sorted(j["candidates"].items()):
            if (k, iso) in blk:
                skipped["dismissed"] += 1
                if (k, iso) not in rk:
                    would = {"symbol": CO.house(sym), "rule": run["rule"], "run_day": iso, "first_run_day": iso,
                             "runs": [run], "added_at": None, "seated_session": None, "reading": rd}
                    removed.append(_removed_rec(would, now, siso, C.RUNNERS_SEAT_REASONS[2]))
                    rk.add((k, iso))
                    blocked_now.append(CO.house(sym))
                continue
            e = by.get(k)
            if e is None:
                e = {"symbol": CO.house(sym), "rule": run["rule"], "run_day": iso, "first_run_day": iso,
                     "runs": [run], "added_at": now, "seated_session": siso, "reading": rd}
                entries.append(e)
                by[k] = e
                added.append(e["symbol"])
                continue
            runs = [x for x in e.get("runs") or [] if isinstance(x, dict)]
            same = [i for i, x in enumerate(runs) if x.get("date") == iso]
            if same:
                i = same[0]
                if runs[i].get("rule") == C.RUNNERS_SEAT_RULES[0] and run["rule"] == C.RUNNERS_SEAT_RULES[1]:
                    runs[i] = run
                    e["runs"] = runs
                    if e.get("run_day") == iso:
                        e["rule"] = run["rule"]
                continue
            runs.append(run)
            runs.sort(key=lambda x: str(x.get("date")))
            e["runs"] = runs
            if iso < str(e.get("first_run_day") or iso):
                e["first_run_day"] = iso
            if iso > str(e.get("run_day")) and C.RUNNERS_SEAT_RESTART:
                e["run_day"], e["rule"] = iso, run["rule"]
                restarted.append(e["symbol"])
        if not j["pending"]:
            processed[iso] = {"reading": rd, "n_scan": j["n_scan"], "n_reads": j["n_reads"],
                              "partial": j["n_scan"] - j["n_reads"] > 0, "at": now}
            done.append(iso)
        if j["n_scan"] - j["n_reads"] > 0:
            partial.append(iso)
    kept = []
    for e in entries:
        if e.get("run_day") not in winset:
            if (CO.fold(e["symbol"]), e.get("run_day")) not in rk:
                removed.append(_removed_rec(e, now, siso, C.RUNNERS_SEAT_REASONS[0]))
                rk.add((CO.fold(e["symbol"]), e.get("run_day")))
            gone.append({"symbol": e["symbol"], "reason": C.RUNNERS_SEAT_REASONS[0]})
            continue
        kept.append(e)
    entries = kept
    read = set(read_isos)
    pending, pkeys = [], set()
    for p in [p for p in pend0 if p.get("session") not in read and p.get("session") in winset] + new_pending \
            + list(future):
        if p["key"] not in pkeys:
            pkeys.add(p["key"])
            pending.append(p)
    not_seated = [r for r in ns0 if r.get("session") not in read and r.get("session") in winset] + new_ns
    for a in answers.values():
        if a.get("session") is None:
            a["session"] = siso
    new = {"entries": entries,
           "dismissed": [r for r in dismissed if r.get("session") in winset],
           "removed": [r for r in removed if (r.get("entry") or {}).get("run_day") in winset],
           "processed": {k: v for k, v in processed.items() if k in winset},
           "pending": pending,
           "answers": {k: v for k, v in answers.items() if v.get("session") in winset},
           "not_seated": not_seated}
    new = _norm(new)
    res = {"n": len(entries), "added": added, "removed": gone + [{"symbol": s, "reason": C.RUNNERS_SEAT_REASONS[2]}
                                                                for s in blocked_now],
           "restarted": restarted, "processed": done, "partial": partial, "pending": len(pending),
           "skipped": skipped, "not_seated": len(not_seated), "blocked": blocked_now, "reason": None,
           "symbols": [CO.house(e["symbol"]) for e in entries]}
    res["changed"] = new != stored
    return res, new


def step(now, session, *, db=None, dry: bool = False, stores: Optional[dict] = None, auto_prior=_UNREAD,
         budget_sec=None, clock=time.monotonic, load_1m=None, cached_at=None, split_lookup=None) -> dict:
    """THE minute step (spec §3.2 steps 1–8) → C.RUNNERS_SEAT_OUT_KEYS + symbols, changed (+ writes when dry).
    `budget_sec` None → stored reads only, no provider read. Never raises on a read fault (nothing is written)."""
    now = _u(RUN._utc(now))
    sd = _as_date(session)
    siso = sd.isoformat() if sd else ""
    provider = _Provider(budget_sec, clock)
    if not C.RUNNERS_SEAT_ON:
        return _early(C.RUNNERS_SEAT_STEP_REASONS[0])
    cs = CO.colls(db)
    if not RUN.in_window(now):
        return _early(C.RUNNERS_SEAT_STEP_REASONS[1])
    doc = read_doc(cs)
    if doc is None:
        return _early(C.RUNNERS_SEAT_STEP_REASONS[2])
    win_d = keep_window(sd)
    win = [d.isoformat() for d in win_d]
    syms0 = [CO.house(e["symbol"]) for e in entries_in_window(doc, siso)]
    processed = _map(doc, "processed")
    rd = reading()
    todo = [d for d in win_d if d < sd and (processed.get(d.isoformat()) or {}).get("reading") != rd]
    to_age = [e for e in _entries(doc) if e.get("run_day") not in set(win)]
    if not todo and not to_age:
        return _early(None, syms0)
    rules_doc = RULES.read_doc(cs) if C.RULES_ON else {}
    prior = AUTO.read_doc(cs) if auto_prior is _UNREAD else auto_prior
    if rules_doc is None or not isinstance(prior, dict):
        return _early(C.RUNNERS_SEAT_STEP_REASONS[5], syms0)
    stores = stores if stores is not None else _default_stores()
    st = (stores or {}).get(V.GG5.key)
    rings: list = []
    if todo:
        dates = sorted({d for d in todo} | {_prev(d) for d in todo})
        try:
            rings = aplus_rings(dates, stores=stores)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch 📅: A+ rings unreadable: %s", type(exc).__name__)
            return _early(C.RUNNERS_SEAT_STEP_REASONS[4], syms0)
    answers = _map(doc, "answers")
    stored_pending = {p["key"]: p for p in _list(doc, "pending")}
    ctx = _Ctx(st, split_lookup or split_look(st), cached_at or _default_cached_at, load_1m or _default_load_1m,
               provider, answers, stored_pending, siso, now)
    judged: dict = {}
    try:
        for S in todo:
            judged[S.isoformat()] = _judge(S, ctx, rings)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 📅: stored reads unreadable: %s", type(exc).__name__)
        return _early(C.RUNNERS_SEAT_STEP_REASONS[3], syms0, provider.summary())
    # an A+ that rang after the last completed session's close plays TODAY: listed pending until today is over
    future = [{"kind": "aplus", "key": f"bars|{r['symbol']}|{r['play_day']}", "symbol": r["symbol"],
               "session": r["play_day"], "why": "aplus_pending", "tried": None}
              for r in rings if aplus_rule_on() and r["play_day"] >= siso and r["play_day"] in set(win)]
    res: dict = {}
    for _ in range(_CAS_TRIES):
        blk = blocked(doc, rules_doc, prior, siso)             # per try: a × that lands between read and write counts
        res, new = _apply(doc, now, siso, judged, blk, [S.isoformat() for S in todo], win, answers, future)
        res["provider"] = provider.summary()
        if dry:
            res["writes"] = new
            return res
        if not res["changed"]:
            return res
        try:
            if AUTO._cas(cs["list"], doc, dict(new, updated_at=now, by=BY_LOOP), doc_id=C.RUNNERS_DOC_ID):
                return res
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch 📅: runners write failed: %s", type(exc).__name__)
            break
        doc = read_doc(cs)
        if doc is None:
            break
    log.warning("gajjala watch 📅: the runners write did not land")
    syms = current_symbols(cs, siso)
    out = _early(C.RUNNERS_SEAT_STEP_REASONS[6], syms, provider.summary())
    return out


# ── the roster's own × (its own route — never the plain DELETE) ──────────────────────────────────────────────────
def _x_answer(state, sym) -> dict:
    return {"state": state, "symbol": sym, "text": C.RUNNERS_SEAT_X_TEXT[state].format(sym=sym or "")}


def dismiss(symbol, *, by, db=None, now=None) -> dict:
    """The roster's × ONLY: pulls the entry (removed "dismissed", its `entry` kept) and records {symbol, session: today,
    run_day, via: C.RUNNERS_SEAT_VIA}. A name not seated → "absent", NOTHING written. Reads and writes ONLY the runners
    doc. Never raises (a fault → "error")."""
    from . import build as BLD
    from .store import normalize
    sym = normalize(symbol)
    if sym is None:
        return _x_answer("absent", None)
    if not C.RUNNERS_SEAT_ON:
        return _x_answer("error", sym)
    try:
        now = _u(RUN._utc(now) if now is not None else datetime.now(UTC))
        cs = CO.colls(db)
        if cs is None:
            return _x_answer("error", sym)
        iso = BLD.session_of(now)[0].isoformat()
        win = set(_win_isos(iso))
        k = CO.fold(sym)
        for _ in range(_CAS_TRIES):
            doc = read_doc(cs)
            if doc is None:
                return _x_answer("error", sym)
            entries = _entries(doc)
            hit = [e for e in entries if CO.fold(e["symbol"]) == k and e.get("run_day") in win]
            if not hit:
                return _x_answer("absent", sym)
            e = hit[0]
            removed = _list(doc, "removed")
            dismissed = _list(doc, "dismissed")
            if (k, e.get("run_day")) not in _removed_keys(removed):
                removed.append(_removed_rec(e, now, iso, C.RUNNERS_SEAT_REASONS[1],
                                           C.RUNNERS_SEAT_X_TEXT["dismissed"].format(sym=e["symbol"])))
            dismissed.append({"symbol": sym, "session": iso, "run_day": e.get("run_day"), "at": now,
                              "via": C.RUNNERS_SEAT_VIA})
            new = _norm({"entries": [x for x in entries if CO.fold(x["symbol"]) != k],
                         "removed": [r for r in removed if (r.get("entry") or {}).get("run_day") in win],
                         "dismissed": [r for r in dismissed if r.get("session") in win]})
            if AUTO._cas(cs["list"], doc, dict(new, updated_at=now, by=by if isinstance(by, str) else None),
                         doc_id=C.RUNNERS_DOC_ID):
                return _x_answer("dismissed", sym)
        log.warning("gajjala watch 📅: dismiss %s lost the compare-and-set %d times", sym, _CAS_TRIES)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 📅: dismiss %s failed: %s", sym, type(exc).__name__)
    return _x_answer("error", sym)


# ── served ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _run_of(entry: dict) -> Optional[dict]:
    runs = [x for x in entry.get("runs") or [] if isinstance(x, dict)]
    hit = [x for x in runs if x.get("date") == entry.get("run_day")]
    return hit[-1] if hit else (runs[-1] if runs else None)


def tag_of(entry, session, *, flags=None) -> Optional[dict]:
    """{day_n, keep, day_text, seat_text, seat_title, rule, run_day} — the two chips of a seated runner; None when the
    entry is outside the window or has no run. `flags` is accepted for the roster's call shape (the 🚫 word is the
    roster row's, never the chip's)."""
    if not isinstance(entry, dict):
        return None
    n = day_n(entry.get("run_day"), session)
    run = _run_of(entry)
    if n is None or run is None:
        return None
    w = RN.clock_words()
    rd = _as_date(entry.get("run_day"))
    last = window_last(rd)
    keep = C.RUNNERS_KEEP_SESSIONS
    pct = RN._fin(run.get("run_pct"))
    if run.get("rule") == C.RUNNERS_SEAT_RULES[1]:
        seat_text = C.RUNNERS_SEAT_CHIP_APLUS.format(pct=RN.pct_show(pct, 0) or "—")
        rdate = _as_date(run.get("ring_date"))
        seat_title = C.RUNNERS_SEAT_TITLE_APLUS.format(
            ring_date=_dayword(rdate) if rdate else "—", ring_at=run.get("ring_at_et") or "—",
            trigger=_px(run.get("trigger")), high=_px(run.get("high_px")), at=run.get("high_et") or "—",
            date=_dayword(rd), pct=RN.pct_show(pct) or "—", frm=run.get("from_et") or "—", to=run.get("to_et") or "—",
            keep=keep, last=_dayword(last) if last else "—")
    else:
        seat_text = C.RUNNERS_SEAT_CHIP_DAY.format(pct=RN._run_text(pct) if pct is not None else "—")
        seat_title = C.RUNNERS_SEAT_TITLE_DAY.format(date=_dayword(rd), open=w["open"], end=w["end"],
                                                     pct=RN.pct_show(pct) or "—", at=run.get("peak_et") or "—",
                                                     keep=keep, last=_dayword(last) if last else "—")
    return {"day_n": n, "keep": keep, "day_text": C.RUNNERS_SEAT_DAY_CHIP.format(n=n, keep=keep),
            "seat_text": seat_text, "seat_title": seat_title, "rule": run.get("rule"), "run_day": entry.get("run_day")}


def rule_sentence() -> str:
    """The LIVE reading's one sentence (C.RUNNERS_SEAT_HINT_RULE), every number from the constants at CALL time."""
    w = RN.clock_words()
    return C.RUNNERS_SEAT_HINT_RULE[reading()].format(open=w["open"], end=w["end"], day=C.RUNNERS_SEAT_DAY_PCT,
                                                      ap=C.RUNNERS_SEAT_APLUS_PCT)


def _hint(doc, session) -> str:
    win = set(_win_isos(session))
    ns = [r for r in _list(doc, "not_seated") if r.get("session") in win]
    pend = [p for p in _list(doc, "pending") if p.get("session") in win]
    parts = []
    for iso, p in sorted(_map(doc, "processed").items()):
        if iso in win and p.get("partial"):
            n_scan, n_reads = int(p.get("n_scan") or 0), int(p.get("n_reads") or 0)
            parts.append(C.RUNNERS_SEAT_PARTIAL.format(date=iso, n=n_scan - n_reads, of=n_scan))
    return C.RUNNERS_SEAT_HINT.format(rule=rule_sentence(), keep=C.RUNNERS_KEEP_SESSIONS,
                                      not_seated=C.RUNNERS_SEAT_NOT_SEATED.format(n=len(ns)) if ns else "",
                                      pending=C.RUNNERS_SEAT_PENDING.format(n=len(pend)) if pend else "",
                                      partial="".join(parts))


def roster(cs, session, now, *, on_watch=(), flags=None) -> Optional[dict]:
    """The 📅 roster block (spec §3.2) — None when the doc is readable and holds no entry in the window (the board gains
    NO key); {"state": "unreadable", …} on a read fault. `flags` = the 🚫 list (None → read once, only when rows)."""
    if not C.RUNNERS_SEAT_ON:
        return None
    doc = read_doc(cs)
    if doc is None:
        return {"state": "unreadable", "text": C.RUNNERS_SEAT_UNREADABLE, "rows": []}
    siso = _as_date(session).isoformat()
    entries = entries_in_window(doc, siso)
    if not entries:
        return None
    if flags is None:
        flags = RN._broker_flags(RN._store())
    from chart_maps.gajjala import tab as GT
    watch = {CO.fold(s) for s in on_watch or () if isinstance(s, str)}
    rows = []
    for e in entries:
        tag = tag_of(e, siso)
        if tag is None:
            continue
        sym = CO.house(e["symbol"])
        run = _run_of(e) or {}
        ow = CO.fold(sym) in watch
        btext = GT.broker_text_for(sym, flags)
        rows.append({"symbol": sym, "day_n": tag["day_n"], "day_text": tag["day_text"], "seat_text": tag["seat_text"],
                     "seat_title": tag["seat_title"], "rule": tag["rule"], "run_day": tag["run_day"],
                     "broker_text": btext, "on_watch": ow, "on_watch_text": C.RUNNERS_SEAT_ON_WATCH if ow else None,
                     "remove_title": C.RUNNERS_SEAT_REMOVE_TITLE.format(sym=sym),
                     "_k": (btext is not None, -_as_date(e["run_day"]).toordinal(),
                            -(RN._fin(run.get("run_pct")) or 0.0), sym)})
    rows.sort(key=lambda x: x["_k"])
    for r in rows:
        r.pop("_k", None)
    win = set(_win_isos(siso))
    ns = sorted([{k: r.get(k) for k in ("symbol", "session", "why", "text")} for r in _list(doc, "not_seated")
                 if r.get("session") in win], key=lambda r: (str(r["session"]), str(r["symbol"])), reverse=True)
    return {"state": "ok", "title": C.RUNNERS_SEAT_TITLE, "text": C.RUNNERS_SEAT_HEAD.format(title=C.RUNNERS_SEAT_TITLE,
                                                                                            n=len(rows)),
            "n": len(rows), "keep_sessions": C.RUNNERS_KEEP_SESSIONS, "hint": _hint(doc, siso),
            "folded_default": True, "fold_at": C.RUNNERS_FOLD_AT, "more_text": C.RUNNERS_MORE_TEXT,
            "less_text": C.RUNNERS_LESS_TEXT, "track_path": C.API_RUNTRACK_PATH, "not_seated": ns, "rows": rows}


def tags_for(cs, session) -> dict:
    """{FOLD: tag_of(entry)} for every entry in the window ({} on a fault / off)."""
    if not C.RUNNERS_SEAT_ON:
        return {}
    doc = read_doc(cs)
    out = {}
    for e in entries_in_window(doc, session) if doc else []:
        t = tag_of(e, session)
        if t is not None:
            out[CO.fold(e["symbol"])] = t
    return out


def push_mode() -> str:
    """C.RUNNERS_PUSH_MODE when it is one of C.AUTO_PUSH_MODES, else "off" (fail closed)."""
    m = C.RUNNERS_PUSH_MODE
    return m if isinstance(m, str) and m in C.AUTO_PUSH_MODES else C.AUTO_PUSH_MODES[0]


def rules_line() -> str:
    """The ℹ️ clause — the LIVE reading's sentence and every number from the constants at CALL time."""
    return (f"{C.RUNNERS_SEAT_TITLE} on 👀 Gajjala's Watch (owner only): every name on Gajjala's scanner that ran. "
            + rule_sentence()
            + f" Seated the next session, kept {C.RUNNERS_KEEP_SESSIONS} sessions from the run day (the run day "
            f"included); a new qualifying day restarts the count; a split that day or between an A+ and the day its "
            f"minute bars were read, or no daily bar before that session, is never seated; 🚫 names last, never "
            f"dropped; it leaves after day {C.RUNNERS_KEEP_SESSIONS} or on its own ×; no cap; this list never rings "
            f"(mode {push_mode()}). UNMEASURED.")


__all__ = ["reading", "day_cut", "aplus_rule_on", "day_rule_skips_related", "day_counts", "play_day", "measure_start",
           "measure_end", "reaches", "from_trigger", "split_look", "split_is_stored", "fetched_on", "prior_bar",
           "keep_window", "day_n", "read_doc", "entries_in_window", "current_symbols", "blocked", "aplus_rings", "step",
           "dismiss", "tag_of", "roster", "tags_for", "push_mode", "rules_line"]
