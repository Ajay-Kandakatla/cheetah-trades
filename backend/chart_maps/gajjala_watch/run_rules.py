"""▶ run Gajjala's rules on ONE Watch name (2026-11-24, spec ggrun rev 2 §3.1, WP be-run).

Ajay 2026-11-24, verbatim: "On the Watch list I need a run button to run against Gajjalas rules of a stock to see for
patterns of 5 patterns he has especially reversal squeeze.. so can check for patterns mid day when I can add a small
slide in in the chart window for giving verbatim of passed rules and failed rules of that stock like you do in other
tabs.."

ONE tap = the 🚩 pass's own three calls for ONE listed Watch name (his names + today's 🤖 names), nothing else:
`bars.frames_for([sym], …)` (GG5: closed 5m + 15m, the settle rule) → `Frames.detector_frames()` →
`detectors.read_all(frames, {"symbol", "float_read", K11_CTX_KEY})` (run.py's detect path). The five reads are served
in the 🚩 card's own words (`tab.state_label`, `tab.plan_text`, `tab.variant_label`, `tab.grade_label`,
`tab.vol_dried_text`, `tab._setup_label`) with the rule rows exactly as the detector wrote them, 🎾 Reversal Squeeze
first, then the GC.SETUPS order.

Inputs, each the existing engine's:
  * bars — `load_day`: the minute loader's cache rule (a prior day from the 1-minute day cache, today fetched) WITHOUT
    its cache write, on the Watch's OWN breaker (`gajjala_watch.rest.breaker()`, one definition). The cache reader's
    handle ensures its EXISTING index once per process — no document is written.
  * K11 — `bars.session_volume(frames)`: today's 1-minute volumes before the last closed 5-minute bar (the Watch's own
    1M-floor number); the 🚩 pass reads the scanner's day volume instead, usually a little higher.
  * float — the 🚩 pass's stored read (`tab._float_read`) when today's read doc has one, else the pass's own float
    chain steps 1–2 computed now (`context.floats_for(refine=False)`: the shares cache on the store's long-lived handle,
    then Massive shares outstanding), store None → nothing kept. Yahoo is never asked on a run (HIS CALL 10).

It rings nothing, records nothing and changes no rule: no push, no alert row, no potential, no auto seat, no tile, no
read doc, no cache row. Every sentence below is mine (HIS CALL 9); every number is formatted from its constant at call
time. Display only — UNMEASURED.
"""
from __future__ import annotations

import copy
import importlib
import logging
import threading
import time
from typing import Callable, Optional

import pandas as pd

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import store as GST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from daytrading import data as dt
from sepa import volume_movers as VM

from . import build as BLD
from . import colls as CO
from . import constants as C
from . import float_read as WF
from . import payload as PL
from . import rest as WR
from . import sections as SEC
from . import store as WST

log = logging.getLogger("chart_maps.gajjala_watch.run_rules")

STATES = ("ok", "closed", "not_listed", "bad_symbol", "no_prints", "no_bars", "failed", "busy", "off", "error")
ANSWER_KEYS = C.RUN_ANSWER_KEYS
SETUP_KEYS = ("setup", "label", "state", "state_label", "gate_text", "plan_text", "variant_label", "grade_label",
              "vol_dried_text", "frame", "as_of_bar_t", "criteria", "tally_text")
CRITERION_KEYS = ("key", "label", "ok", "value", "need")      # == detectors.criterion's keys (a test pins it)
MEMO_STATES = ("ok", "no_prints", "no_bars")                  # `failed` / `busy` are never kept: the next tap retries
FLOAT_ORIGINS = ("pass", "run")                               # the 🚩 pass's stored read | the chain run now

# ── words (all MINE — HIS CALL 9) ────────────────────────────────────────────────────────────────────────────────
TITLE_TEXT = "▶ Gajjala's rules on {sym}"
TITLE_NO_SYM = C.RUN_TITLE_TEXT
NOTE_TEXT = C.RUN_NOTE_TEXT
AS_OF_TEXT = "🕐 graded through the {t5} ET {w5} bar{slow} · read {at} ET · closed bars only"
AS_OF_SLOW_TEXT = " ({w15}: {t15} ET)"
REUSED_TEXT = ("🔁 the same read from {at} ET — no new {w5} bar has closed since, and a read under {sec} s old is not "
               "re-run")
BUSY_TEXT = "Another run of {sym} is still reading its bars — tap ▶ again."
CLOSED_TEXT = "Market closed — Gajjala's rules read closed bars {open}–{close} ET on a market day. Nothing was run."
NOT_LISTED_TEXT = "{sym} is not on your Watch — add it first, then run its rules."
NO_PRINTS_TEXT = "No prints yet today for {sym} — nothing to grade."
NO_BARS_TEXT = "No minute bars for {sym} today or the session before — check the ticker."
FAILED_TEXT = "The minute bars could not be read just now — tap ▶ again."
OFF_TEXT = "Running Gajjala's rules from the Watch is switched off."
ERROR_TEXT = "The rules could not be run: {why}"
LIST_ERROR_WHY = "your Watch list could not be read"
SCANNER_ON_TEXT = "📋 on the 🚩 pass's list today — {listed}"      # the pass also reads 📌 trader adds, so never "GG's scanner"
SCANNER_ON_BARE_TEXT = "📋 on the 🚩 pass's list today"
SCANNER_OFF_TEXT = "📋 not on the 🚩 pass's list today — these are the setup rules alone"
VOLUME_TEXT = ("today's volume {vol:,} — the sum of today's {w1} bars before the {t5} ET bar closed. The 🚩 pass reads "
               "the scanner's day volume instead; this sum stops at the last closed bar, so near {floor:,} it is "
               "usually the lower of the two.")
TALLY_TEXT = "{f} failed · {p} passed"
TALLY_UNJUDGED_TEXT = " · {u} not judged yet"
FLOAT_RUN_SOURCE_WORDS = {"shares_out_massive": "Massive's shares outstanding, asked by this server for a run — "
                                                "nothing stored"}
FLOAT_RUN_TEXT = "{text} — not realtime: {source}"
FLOAT_NOT_FLOAT_TEXT = "not a float figure — Yahoo's float is not on file"
GATE_ALIVE_TEXT = ("{label}: the setup's structure IS on the chart today — the float gate stopped this read, and the "
                   "detector keeps no rule rows behind a failed float gate.")
GATE_SHARES_OUT_TEXT = ("The gate read {text} — shares outstanding, not a float; the float can be smaller. The 🚩 pass "
                        "asks Yahoo for the float (names with this structure first) before it trusts this gate. A run "
                        "never asks Yahoo.")
GATE_NO_FLOAT_TEXT = ("No float is on file for this name. The 🚩 pass asks Yahoo for it (names with this structure "
                      "first). A run never asks Yahoo.")

# ── the memo and the per-symbol locks (per process; `_GUARD` is never held across I/O) ─────────────────────────────
_GUARD = threading.Lock()
_MEMO: dict = {}                 # SYM -> {"session", "t", "closable", "at", "answer"}
_LOCKS: dict = {}                # SYM -> threading.Lock


def _reset() -> None:
    """Tests: forget the memo and the per-symbol locks (never the Watch's breaker)."""
    with _GUARD:
        _MEMO.clear()
        _LOCKS.clear()


def _lock_for(sym: str) -> threading.Lock:
    with _GUARD:
        lk = _LOCKS.get(sym)
        if lk is None:
            lk = _LOCKS[sym] = threading.Lock()
        return lk


# ── small pure helpers ───────────────────────────────────────────────────────────────────────────────────────────
def setup_order() -> tuple:
    """🎾 first (sections.RS_SETUP, read by name), then every other GC.SETUPS member in GC.SETUPS order."""
    return (SEC.RS_SETUP,) + tuple(s for s in GC.SETUPS if s != SEC.RS_SETUP)


def load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
    """The minute loader's cache rule WITHOUT its cache write: a day that is not the loader's ET "today" (and not
    forced) reads the 1-minute day cache; anything else is fetched on the Watch's OWN breaker. Nothing is written."""
    if not force and day != dt._today_et():
        cached = dt._mongo_get_day(sym, day)
        if cached is not None and not cached.empty:
            return dt._filter_sessions(cached, include_premarket, include_afterhours)
    df = dt._fetch_massive_minute(sym, day, day, cb=WR.breaker())
    if df is None or df.empty:
        return None
    return dt._filter_sessions(df, include_premarket, include_afterhours)


def watch_names(db=None, now=None) -> list:
    """His names (strict: a fault RAISES) + today's 🤖 names (the auto engine, imported lazily — any fault → his names
    only, ONE log line) + (2026-11-24, spec watchall §3.4) the ✅ all-rules names LAST (the all-rules engine, imported
    lazily — any fault → skipped, ONE log line; the same listing as levels._listed)."""
    names = list(CO.owner_symbols(db, strict=True))
    keys = {CO.fold(s) for s in names}
    for module, what in ((PL.AUTO_MODULE, "auto"), (PL.RULES_MODULE, "all-rules")):
        try:
            more = importlib.import_module(module).current_symbols(CO.colls(db), PL.session_iso(now))
            for s in more or []:
                if isinstance(s, str) and s.strip() and CO.fold(s) not in keys:
                    keys.add(CO.fold(s))
                    names.append(s)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch run rules: %s names unavailable: %s", what, type(exc).__name__)
    return names


def listed_as(symbol, names) -> Optional[str]:
    """The listed spelling whose colls.fold equals fold(symbol), else None."""
    want = CO.fold(symbol)
    if not want:
        return None
    return next((s for s in names or [] if isinstance(s, str) and CO.fold(s) == want), None)


def closable_t5(now) -> str:
    """The newest primary (5-minute) label that CAN be closed at `now` — bars.closed_only's own rule (label ≤ now −
    GC.BAR_SETTLE_SEC), in the frame stamp's spelling."""
    cutoff = B._utc_naive(now) - pd.Timedelta(seconds=GC.BAR_SETTLE_SEC)
    return B._intraday_stamp(cutoff.floor(B.RULE_OF[V.GG5.primary]))


def shares_lookup(st) -> Callable:
    """The float chain's cache lookup on the store's long-lived handle: ALWAYS fetch=False (a run never reaches Yahoo),
    never a new client — no handle answers (None, "error") and the chain goes on to Massive."""
    try:
        handle = st.coll(VM.SHARES_COLL) if st is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch run rules: shares handle unavailable: %s", type(exc).__name__)
        handle = None

    def lookup(s, *, fetch=True):
        if handle is None:
            return None, "error"
        return VM.shares_status(s, fetch=False, coll=handle)
    return lookup


def float_for(sym, now, doc, st) -> tuple:
    """(FloatRead, origin): the read the 🚩 pass handed its detectors ("pass"), else the chain's steps 1–2 now ("run",
    store None and session None → nothing kept); any fault → (context.unknown_float(now), "run")."""
    fr = GT._float_read(doc if isinstance(doc, dict) else {}, None)
    if isinstance(fr, dict):
        return fr, "pass"
    try:
        out = CX.floats_for([sym], now=now, refine=False, status_lookup=shares_lookup(st))
        fr = (out or {}).get(str(sym).upper().strip())
        if isinstance(fr, dict):
            return fr, "run"
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch run rules: float chain failed: %s", type(exc).__name__)
    return CX.unknown_float(now), "run"


def yahoo_could_admit(fl) -> bool:
    """context.refine_order's `could_admit` — the pass's own "a Yahoo float could admit it": shares unknown, or
    Massive's shares outstanding above GC.K8_MAX_FLOAT (a test pins the two together)."""
    r = fl if isinstance(fl, dict) else {}
    return r.get("shares") is None or (r.get("src") == "shares_out_massive" and r["shares"] > GC.K8_MAX_FLOAT)


def _chip(fl, now) -> dict:
    return GT._float_chip(fl) or GT._float_chip(CX.unknown_float(now))


def float_text(fl, now, origin) -> str:
    chip = _chip(fl, now)
    if origin == "run" and chip.get("src") in FLOAT_RUN_SOURCE_WORDS and chip.get("shares") is not None:
        out = FLOAT_RUN_TEXT.format(text=chip["text"], source=FLOAT_RUN_SOURCE_WORDS[chip["src"]])
    else:
        out = WF.title(chip, now) or chip["text"]
    sus = GT._float_suspect_text({}, fl)
    if sus:
        out += " · " + sus
    if yahoo_could_admit(fl) and chip.get("shares") is not None:
        out += " · " + FLOAT_NOT_FLOAT_TEXT
    return out


def gate_text(setup, read, fl) -> Optional[str]:
    """🎾 only: a `none` read whose structure the detector saw (`meta.structure_alive`) — the float gate replaced it."""
    if setup != SEC.RS_SETUP or not isinstance(read, dict) or read.get("state") != "none":
        return None
    meta = read.get("meta") if isinstance(read.get("meta"), dict) else {}
    if meta.get("structure_alive") is not True:
        return None
    out = GATE_ALIVE_TEXT.format(label=GT._setup_label(setup))
    if yahoo_could_admit(fl):
        chip = GT._float_chip(fl) or {}
        if chip.get("shares") is None:
            out += " " + GATE_NO_FLOAT_TEXT
        else:
            out += " " + GATE_SHARES_OUT_TEXT.format(text=chip["text"])
    return out


def scanner_block(doc) -> dict:
    if not isinstance(doc, dict):
        return {"listed": False, "text": SCANNER_OFF_TEXT}
    blk = GT._listed_block(doc.get("listed"))
    txt = blk.get("text") if isinstance(blk, dict) else None
    return {"listed": True, "text": SCANNER_ON_TEXT.format(listed=txt) if txt else SCANNER_ON_BARE_TEXT}


def _hhmm(stamp) -> Optional[str]:
    return stamp[11:16] if isinstance(stamp, str) and len(stamp) >= 16 else None


def as_of_block(frames, now) -> dict:
    t5, t15 = frames.as_of_bar_t5, frames.as_of_bar_t15
    at = now.strftime("%H:%M:%S")
    slow = AS_OF_SLOW_TEXT.format(w15=C.FRAME_WORDS[V.GG5.slow], t15=_hhmm(t15)) if _hhmm(t15) else ""
    text = AS_OF_TEXT.format(t5=_hhmm(t5) or "—", w5=C.FRAME_WORDS[V.GG5.primary], slow=slow, at=at)
    return {"bar_t5": t5, "bar_t15": t15, "read_at_et": at, "text": text}


def volume_text(sv, frames) -> str:
    v = D._k11_volume(sv)
    if v is None:
        return D.K11_UNKNOWN
    return VOLUME_TEXT.format(vol=int(v), w1=C.FRAME_WORDS["1m"], t5=_hhmm(frames.as_of_bar_t5) or "—",
                              floor=int(GC.K11_MIN_SESSION_VOLUME))


def tally_text(read) -> Optional[str]:
    rows = [c for c in (read or {}).get("criteria") or [] if isinstance(c, dict)]
    if not rows:
        return None
    f = sum(1 for c in rows if c.get("ok") is False)
    p = sum(1 for c in rows if c.get("ok") is True)
    u = len(rows) - f - p
    return TALLY_TEXT.format(f=f, p=p) + (TALLY_UNJUDGED_TEXT.format(u=u) if u > 0 else "")


def setup_block(setup, read, rang, fl) -> dict:
    """EXACTLY SETUP_KEYS — every word the 🚩 card's own function; rows in detector order, never re-sorted."""
    read = read if isinstance(read, dict) else {}
    return {"setup": setup, "label": GT._setup_label(setup), "state": read.get("state"),
            "state_label": GT.state_label(read, rang), "gate_text": gate_text(setup, read, fl),
            "plan_text": GT.plan_text(read), "variant_label": GT.variant_label(read),
            "grade_label": GT.grade_label(read), "vol_dried_text": GT.vol_dried_text(read),
            "frame": read.get("frame"), "as_of_bar_t": read.get("as_of_bar_t"),
            "criteria": [{k: c.get(k) for k in CRITERION_KEYS} for c in read.get("criteria") or []
                         if isinstance(c, dict)],
            "tally_text": tally_text(read)}


def grade(frames, ctx) -> dict:
    """The pass's call, nothing else."""
    return D.read_all(frames.detector_frames(), ctx)


def answer(state, sym, **body) -> dict:
    """EXACTLY ANSWER_KEYS; `title` and `note` are always strings, `setups` always a list."""
    out = {k: None for k in ANSWER_KEYS}
    out.update(state=state, symbol=sym, title=TITLE_TEXT.format(sym=sym) if sym else TITLE_NO_SYM, note=NOTE_TEXT,
               setups=[])
    for k, v in body.items():
        if k in out:
            out[k] = v
    return out


# ── the memo ─────────────────────────────────────────────────────────────────────────────────────────────────────
def memo_get(sym, session_iso, now, clock) -> Optional[dict]:
    """A deep copy of the kept answer + `reused_text` — only for the same symbol and session, younger than
    C.RUN_REUSE_SEC, AND while no newer 5-minute bar can have closed. No I/O."""
    closable = closable_t5(now)
    t = clock()
    with _GUARD:
        m = _MEMO.get(sym)
        if (not m or m["session"] != session_iso or not (t - m["t"] < C.RUN_REUSE_SEC)
                or m["closable"] != closable):
            return None
        out = copy.deepcopy(m["answer"])
        at = m["at"]
    out["reused_text"] = REUSED_TEXT.format(at=at, w5=C.FRAME_WORDS[V.GG5.primary], sec=C.RUN_REUSE_SEC)
    return out


def _memo_put(sym, session_iso, now, clock, ans) -> None:
    if ans.get("state") not in MEMO_STATES:
        return
    t = clock()
    entry = {"session": session_iso, "t": t, "closable": closable_t5(now), "at": now.strftime("%H:%M:%S"),
             "answer": copy.deepcopy(ans)}
    with _GUARD:
        for k in [k for k, m in _MEMO.items() if not (t - m["t"] < C.RUN_REUSE_SEC)]:
            del _MEMO[k]
        _MEMO[sym] = entry


# ── one read ─────────────────────────────────────────────────────────────────────────────────────────────────────
_NOT_LOADED_TEXT = {"no_prints": NO_PRINTS_TEXT, "no_bars": NO_BARS_TEXT}


def _read(sym, now, *, store, load) -> dict:
    session = now.date()
    pn: dict = {}
    frames = B.frames_for([sym], session, now, load_day=load or load_day, budget_sec=C.RUN_BUDGET_SEC, stats={},
                          per_name=pn)
    status = BLD.status_of(pn.get(sym, {}))
    fr = frames.get(sym)
    if fr is None or status != "loaded":
        state = status if status in _NOT_LOADED_TEXT else "failed"
        text = _NOT_LOADED_TEXT[state].format(sym=sym) if state in _NOT_LOADED_TEXT else FAILED_TEXT
        return answer(state, sym, text=text)
    st = store if store is not None else GST.default()
    try:
        doc = st.get_read(session, sym)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch run rules: read doc unavailable: %s", type(exc).__name__)
        doc = None
    doc = doc if isinstance(doc, dict) else None
    fl, origin = float_for(sym, now, doc, st)
    sv = B.session_volume(fr)
    reads = grade(fr, {"symbol": sym, "float_read": fl, D.K11_CTX_KEY: sv})
    try:
        entries = GT._entry_times(st, [session], V.GG5)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch run rules: entry times unavailable: %s", type(exc).__name__)
        entries = None
    setups = [setup_block(k, reads.get(k), GT._rang(entries, session, sym, k), fl) for k in setup_order()]
    return answer("ok", sym, as_of=as_of_block(fr, now), scanner=scanner_block(doc),
                  float_text=float_text(fl, now, origin), volume_text=volume_text(sv, fr), setups=setups)


def run(symbol, now=None, *, db=None, store=None, load=None, clock=time.monotonic) -> dict:
    """The ONE answer (EXACTLY ANSWER_KEYS). Never raises. Order: bad symbol → off → the Watch list → not listed →
    closed → the memo (no lock) → the per-symbol lock (busy) → the memo again → one read."""
    sym = None
    try:
        now = PL._now(now)
        sym0 = WST.normalize(symbol)
        if sym0 is None:
            return answer("bad_symbol", None, text=PL.store_text("bad_symbol", None))
        sym = sym0
        if not C.RUN_RULES_ON:
            return answer("off", sym0, text=OFF_TEXT)
        try:
            names = watch_names(db, now)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch run rules: watch list unreadable: %s", type(exc).__name__)
            return answer("error", sym0, text=ERROR_TEXT.format(why=LIST_ERROR_WHY))
        listed = listed_as(sym0, names)
        if listed is None:
            return answer("not_listed", sym0, text=NOT_LISTED_TEXT.format(sym=sym0))
        sym = listed
        if OD._closed(now):
            return answer("closed", sym, text=CLOSED_TEXT.format(open=GC.PASS_OPEN_ET, close=GC.PASS_CLOSE_ET))
        siso = now.date().isoformat()
        hit = memo_get(sym, siso, now, clock)
        if hit is not None:
            return hit
        lock = _lock_for(sym)
        if not lock.acquire(timeout=float(C.RUN_BUDGET_SEC)):
            return answer("busy", sym, text=BUSY_TEXT.format(sym=sym))
        try:
            hit = memo_get(sym, siso, now, clock)
            if hit is not None:
                return hit
            out = _read(sym, now, store=store, load=load)
            _memo_put(sym, siso, now, clock, out)
            return out
        finally:
            lock.release()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch run rules failed: %s", type(exc).__name__)
        return answer("error", sym, text=ERROR_TEXT.format(why=type(exc).__name__))
