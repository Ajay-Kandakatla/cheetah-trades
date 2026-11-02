"""🥇 Luk's tab — the served board (BUILD SPEC luk-tab §3.10, WP-C, 2026-11-01). Reads Mongo ONLY (the `luk_*`
collections the Luk pass writes); the route adds the ONE live fan-out for the shown tiles.

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources. ... I need something like Gajjlala that is exposed".

Every served sentence is composed HERE or in the module that owns it (ledger.py's 🏁 words, screens.py's screen titles,
playbook.py's Playbook, market_state.py's index words, detectors.py's listing reasons) — the FE prints what it is given.
Every number in a template is a constants name read at call time (chart_maps.luk.constants, or GC's cadence through the
LUK variant). The word is "reversal", never the b-word; the word "edge" is never served. Every 🥇 A+ rings his phone
since LC.LUK_LIVE_SINCE by his word (Ajay 2026-11-01: "Lets make it live. also alerts too."); the push / honesty words
follow luk.variant.push_mode() at call time (anything but "live" serves the shadow words: recorded, never sent).
UNMEASURED: nothing here trades, sizes or enters a lane.

Reused by import (one engine per concept): gajjala.tab's formatters (`_px`, `_pct`, `_hhmm`, `_et`, `_plain`, `_f`),
its `_session_block` (minus GG's first-15-minutes keys — Luk trades the first candle), `_pass_block` (as_of / stale /
warming over the LUK variant's cadence), `_tile_lines` and `_on_bars` (the PatternChart BUY / TRIGGER / STOP lines and
markers); chart_maps.board `_href`; luk.ledger.served_block (🏁), luk.playbook.playbook (📓), luk.screens titles,
luk.market_state.block (🧭). Never gajjala.variant.served_block / word (they read GG's constants).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time as dtime
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V

from . import constants as LC
from . import market_state as MS
from . import tiers as TI
from . import variant as VL
from .variant import LUK

log = logging.getLogger("chart_maps.luk.tab")

# ── the board's own words (every number a constants name, formatted at call time) ──────────────────────────────────
TITLE = ("🥇 Luk's — Martin Luk's published pullback / opening-range method, built from his own words · UNMEASURED")
_HONESTY = ("2025 US Investing Championship winner (+969.8%, $20k+ stock division; 2026 leader +785.8% through Sep "
            "30). He sells nothing; every rule here is his own words in free sources, cited line by line on the 📓 "
            "Playbook; his selling and exposure are discretionary by his own admission, so what is computed here is "
            "the entry, the stop and one exit he stated. {mode} Nothing here is measured, trades, sizes or enters a "
            "lane.")
HONESTY_LIVE = _HONESTY.replace("{mode}", "Every alert here rings your phone since {since} by your call (\"{words}\").")
HONESTY_SHADOW = _HONESTY.replace("{mode}", "Every alert is recorded in shadow, never sent.")
FAULT_TEXT = "🥇 The board could not be read this time — the next re-read tries again."
PASS_TEXT = ("pass {hhmm} ET · bars through {through} · {n_read} read of {shortlist} shortlisted · {screened} screened "
             "· {not_screened} not screened yet")
PASS_NONE_TEXT = "no 🥇 pass on file for this session yet — it runs every {cad} minutes, {open}–{close} ET"
THROUGH_NONE = "—"
LATENCY_TEXT = ("a {one}-minute trigger is read on the next {cad}-minute pass — up to {cad} minutes after its bar closed — "
                "and still rings when no later bar touched the stop")
PUSH_TEXT_LIVE = ("📲 Every 🥇 A+ rings your phone since {since} by your call (\"{words}\") — once per name, setup and "
                  "session, only when the entry bar is inside the regular session; a 1-minute trigger can ring up to "
                  "{cad} minutes after its bar closed. UNMEASURED.")
PUSH_TEXT_SHADOW = "📵 Every 🥇 A+ is recorded in shadow, never sent, until you say so. UNMEASURED."
RECORD_TEXT = ("🏁 The Track record starts {from_}: every 🥇 A+ recorded here is graded by Luk's trade math — the stop "
               "or the first daily close below the {ema} EMA.")
EXTERNAL_TEXT = ("External backtests of his entry (rootchunhe/martin-luk-backtesting; zongfan2/TradingAgents) are quoted "
                 "verbatim with their links on the 📓 Playbook — EXTERNAL, not re-run here.")
COST_TEXT = ("Per pass, every {cad} minutes {open}–{close} ET: one whole-market snapshot, at most {daily} daily fetches, "
             "at most {shortlist} names' minute bars (prior sessions loaded once per name, up to {hourly} each), at "
             "most {grade} 🏁 grade loads.")
COST_LAST_TEXT = " Last pass: {calls}."
CALL_WORDS = (("snapshot", "snapshot"), ("daily_fetch", "daily"), ("minute_today", "minute today"),
              ("minute_prior", "minute prior"), ("index", "index"), ("caps", "caps"))
COUNTS_TEXT = ("{aplus} A+ · {triggered} triggered earlier · {forming} forming · {listed} listed · {stopped} stopped — "
               "over {shortlist} shortlisted of {screened} screened")
COUNTS_LEGEND = (
    ("aplus", "A+", "every rule of the setup met and the trigger bar traded through and closed — on the 1-minute frame "
                    "closed since the previous pass with no stop touch since, on the 5-minute frame the latest closed "
                    "bar"),
    ("triggered", "triggered earlier", "the trigger traded earlier today and no later bar touched the stop"),
    ("forming", "forming", "the context is met and the level is armed; no bar has taken it out yet"),
    ("listed", "listed", "broke, but one of his listing rules says not A+ — the reason is on the card"),
    ("stopped", "stopped", "broke, then a later closed bar traded at or under the stop"),
    ("none", "no setup", "no context for the setup today — never carded"),
)
ORDER_NOTE = "A+ first, then triggered earlier, forming, listed, stopped — the newest break first within a state"
STATE_LABEL = {
    "aplus": "A+ — every rule met, the trigger bar traded through and closed",
    "triggered": "triggered earlier",
    "forming": "forming — {level_text} armed",
    "listed": "listed — {listed_why}",
    "stopped": "stopped",
}
LEVEL_TEXT = "trigger {px}"
TRIGGER_TEXT = "trigger {px}"
TRIGGER_BROKE_TEXT = "trigger {px} · broke on the {frame_text} closing {hhmm} ET"
STOP_TEXT = "stop {stop} (−{pct:.1f}%) · R ${r}"
STOP_SWITCH_TAIL = " · stop = the {five}-minute entry candle low (entry-to-LOD > {pct:g}%)"
FRAME_TEXT = {"1m": "1-minute candle", "5m": "5-minute candle"}
ADR_OVER_TEXT = ">{pref:g}% ADR ({adr:.1f}%) — his preference, not a hard rule"
ADR_UNDER_TEXT = "ADR {adr:.1f}% — under his {pref:g}% preference (not a rule)"
FLUSH_TEXT = "flushed {d:.1f}% below the hourly {ema} EMA at {hhmm}"
FLUSH_TOUCH_TEXT = "touched the hourly {ema} EMA at {hhmm}"
FLUSH_NONE_TEXT = "no touch of the hourly {ema} EMA today"
READ_AT_TEXT = "read at {hhmm} ET"
SCREENS_RANK_TEXT = "{emoji} #{rank}"
SCREEN_SORTED_BY = {"premarket": "sorted by pre-market % change", "leader": "sorted by 1-month % change",
                    "potent": "sorted by % change"}
NOT_SCREENED_TEXT = ("{not_screened} names not screened yet — their daily facts are pending (at most {daily} new daily "
                     "fetches per pass); {screened} screened on the last pass")
NOT_SCREENED_NONE_TEXT = "no 🥇 pass on file for this session yet — nothing screened"
CONSIDERATIONS_TEXT = ("He is considering a $100M dollar-volume floor and filtering biotechs and buyouts/mergers out "
                       "(iMBI3ZcQ6sU 1:17:58–1:18:43) — listed, not applied: HIS CALL")
SCREENS_HONESTY = ("His settings applied to the house snapshot and the cached daily bars; the 1-week, 1-month and ADR "
                   "formulas are Cheetah's (HIS CALL #10) and a cap the house cache lacks is kept, not filtered (HIS "
                   "CALL #12). A screen lists names — it is not a buy list. UNMEASURED.")
SCREEN_HEADS = {
    "premarket": (("rank", "#"), ("symbol", "Symbol"), ("price_text", "Price"), ("pm_chg_text", "Pre-market %"),
                  ("cap_text", "Cap"), ("avg_vol_text", "10-day avg vol"), ("px_vol_text", "Price × vol"),
                  ("vol_1w_text", "1-week volatility"), ("tier_text", "Tier"), ("adr_text", "ADR")),
    "leader": (("rank", "#"), ("symbol", "Symbol"), ("price_text", "Price"), ("perf_1m_text", "1-month %"),
               ("cap_text", "Cap"), ("avg_vol_text", "10-day avg vol"), ("px_vol_1w_text", "1-week price × vol"),
               ("tier_text", "Tier"), ("adr_text", "ADR")),
    "potent": (("rank", "#"), ("symbol", "Symbol"), ("price_text", "Price"), ("chg_text", "% change"),
               ("chg_from_open_text", "From open"), ("cap_text", "Cap"), ("px_vol_text", "Price × vol"),
               ("vol_1w_text", "1-week volatility"), ("tier_text", "Tier"), ("adr_text", "ADR")),
}

TILE_STATES = ("aplus", "triggered", "forming", "listed", "stopped")       # `none` is never carded
COUNT_STATES = ("aplus", "triggered", "forming", "listed", "stopped", "none")
SETUP_SUBS = tuple(LC.SETUPS)
SCREEN_SUBS = ("premarket", "leader", "potent")
PLAYBOOK_SUB = "playbook"
TRACK_SUB = "track_record"
SUB_KEYS = tuple(k for k, _e, _l in LC.SUBS)
SUB_META = {k: (e, label) for k, e, label in LC.SUBS}
PAYLOAD_KEYS = ("tab", "label", "title", "honesty", "variant", "session", "pass", "strip", "subs", "sub", "counts",
                "counts_text", "counts_legend", "tiles", "order_note", "screens", "playbook", "track_record", "focus",
                "fault", "fault_text")
UNIT_SEC_PER_MIN = 60                                                       # a unit, not a rule

_STATE_RANK = {s: i for i, s in enumerate(TILE_STATES)}


# ── small helpers ──────────────────────────────────────────────────────────────────────────────────────────────────
def _cad_min() -> int:
    """The Luk pass cadence in minutes — the LUK variant's cadence constant (GC.PASS_CADENCE_SEC), never typed."""
    return int(V.cadence_sec(LUK)) // UNIT_SEC_PER_MIN


def _store(store):
    if store is not None:
        return store
    from . import store as LS
    return LS.default()


def _soft(what: str, fn, *a, default=None, **kw):
    """One block's fault never takes the board down: logged, the default served."""
    try:
        return fn(*a, **kw)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("luk tab: %s failed: %s", what, type(exc).__name__)
        return default


def _hm(stamp) -> Optional[str]:
    return GT._hhmm(stamp)


def _is_market_day(d: date) -> bool:
    from catalysts.medical.reaction import is_market_day
    return is_market_day(d)


def _prev_market_day(d: date) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(d)


def session_for(now: Optional[datetime] = None) -> tuple:
    """(session, is_today, in_window) on LUK's window (LUK_PASS_OPEN_ET–LUK_PASS_CLOSE_ET): today from the first pass
    time on a market day; before it, or on a closed day, the last market day."""
    et = GT._et(now)
    today = et.date()
    if _is_market_day(today) and et.time() >= dtime.fromisoformat(LC.LUK_PASS_OPEN_ET):
        return today, True, et.time() <= dtime.fromisoformat(LC.LUK_PASS_CLOSE_ET)
    return _prev_market_day(today), False, False


# ── blocks ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def variant_block() -> dict:
    return {"key": LUK.key, "tab": LUK.tab, "label": LUK.label, "api_base": LUK.api_base,
            "record_from": LC.LUK_RECORD_FROM, "push_mode": VL.push_mode(), "tfs": list(LUK.tfs),
            "primary": LUK.primary}


def session_block(now, session: date, is_today: bool, in_window: bool) -> dict:
    """gajjala.tab._session_block over the LUK variant, minus GG's first-15-minutes keys (GG doesn't trade the first
    15 minutes; Luk trades the first candle — serving GG's quote here would be wrong)."""
    out = GT._session_block(now, session, is_today, in_window, v=LUK)
    out.pop("first15", None)
    out.pop("first15_text", None)
    return out


def honesty() -> str:
    """The board's honesty line of the mode (luk.variant.push_mode(), read at call time)."""
    if VL.push_mode() == "live":
        return HONESTY_LIVE.format(since=LC.LUK_LIVE_SINCE, words=LC.LUK_LIVE_WORDS)
    return HONESTY_SHADOW


def push_text() -> str:
    """The strip's push line of the mode; {cad} = the served pass cadence (_cad_min), never a typed number."""
    if VL.push_mode() == "live":
        return PUSH_TEXT_LIVE.format(since=LC.LUK_LIVE_SINCE, words=LC.LUK_LIVE_WORDS, cad=_cad_min())
    return PUSH_TEXT_SHADOW


def latency_text() -> str:
    return LATENCY_TEXT.format(one=V.frame_minutes("1m", LUK), cad=_cad_min())


def pass_block(latest: Optional[dict], cron: Optional[dict], now, session: date, in_window: bool) -> dict:
    """gajjala.tab._pass_block (as_of / stale / warming on the LUK variant's cadence and stale numbers) + the Luk
    pass's own facts: bars through, wall, the read / shortlist / screened counts and the latency fact [C1]."""
    out = GT._pass_block(latest, now, session, in_window, cron=cron, v=LUK)
    this = isinstance(latest, dict) and latest.get("date") == session.isoformat()
    bt = (latest or {}).get("bars_through") if this else None
    bt = bt if isinstance(bt, dict) else {}
    through = bt.get("t1_et") or bt.get("t5_et") or THROUGH_NONE
    out.update(bars_through_et=(bt.get("t1_et") or bt.get("t5_et")) if this else None,
               wall_s=GT._f((latest or {}).get("wall_s")) if this else None,
               latency_text=latency_text())
    if this:
        scr = latest.get("screens") if isinstance(latest.get("screens"), dict) else {}
        sl = latest.get("shortlist") if isinstance(latest.get("shortlist"), dict) else {}
        at = GT._at_utc(latest)
        out["text"] = PASS_TEXT.format(hhmm=GT._et(at).strftime("%H:%M") if at else THROUGH_NONE, through=through,
                                       n_read=int(latest.get("n_read") or 0), shortlist=int(sl.get("n") or 0),
                                       screened=int(scr.get("screened_n") or 0),
                                       not_screened=int(scr.get("not_screened_n") or 0))
    else:
        out["text"] = PASS_NONE_TEXT.format(cad=_cad_min(), open=LC.LUK_PASS_OPEN_ET, close=LC.LUK_PASS_CLOSE_ET)
    return out


def cost_text(latest: Optional[dict] = None) -> str:
    txt = COST_TEXT.format(cad=_cad_min(), open=LC.LUK_PASS_OPEN_ET, close=LC.LUK_PASS_CLOSE_ET,
                           daily=LC.LUK_DAILY_MAX_NEW_PER_PASS, shortlist=LC.LUK_SHORTLIST_MAX,
                           hourly=LC.LUK_HOURLY_SESSIONS, grade=LC.LUK_GRADE_MAX_LOADS)
    calls = (latest or {}).get("calls") if isinstance(latest, dict) else None
    if isinstance(calls, dict) and calls:
        parts = [f"{word} {int(calls.get(k) or 0)}" for k, word in CALL_WORDS if k in calls]
        if parts:
            txt += COST_LAST_TEXT.format(calls=" · ".join(parts))
    return txt


def strip_block(latest: Optional[dict], session: date) -> dict:
    """Folded by default: the 🧭 index words (the pass's market_state block; none on file → every row WORD_NONE), the
    push / record / external / cost / latency lines."""
    this = isinstance(latest, dict) and latest.get("date") == session.isoformat()
    ms = (latest or {}).get("market_state") if this else None
    if not (isinstance(ms, dict) and isinstance(ms.get("rows"), list)):
        ms = MS.block({})
    return {"folded": True, "market_state": ms, "push_text": push_text(),
            "record_text": RECORD_TEXT.format(from_=LC.LUK_RECORD_FROM, ema=LC.LUK_PULLBACK_DAILY_EMA),
            "external_text": EXTERNAL_TEXT, "cost_text": cost_text(latest if this else None),
            "latency_text": latency_text()}


def _listed_kind(why) -> Optional[str]:
    """chase | window | stop_wide — by the detector's own served reason (detectors.chase_why / window_why; every other
    listing reason is the stop-width rule)."""
    if not isinstance(why, str) or not why:
        return None
    from . import detectors as DT
    if why == DT.chase_why():
        return "chase"
    if why == DT.window_why():
        return "window"
    return "stop_wide"


def counts_block(reads: list, latest: Optional[dict], session: date) -> tuple:
    """(counts, counts_text) over every setup read of the session's reads (each setup counted once per symbol)."""
    c = {k: 0 for k in COUNT_STATES}
    c.update(listed_chase=0, listed_stop_wide=0, listed_window=0)
    for doc in reads:
        for setup in SETUP_SUBS:
            r = ((doc.get("setups") or {}) if isinstance(doc, dict) else {}).get(setup)
            st = r.get("state") if isinstance(r, dict) else None
            if st in c:
                c[st] += 1
            if st == "listed":
                k = _listed_kind(r.get("listed_why"))
                if k:
                    c[f"listed_{k}"] += 1
    this = isinstance(latest, dict) and latest.get("date") == session.isoformat()
    scr = (latest.get("screens") if this and isinstance(latest.get("screens"), dict) else {}) or {}
    sl = (latest.get("shortlist") if this and isinstance(latest.get("shortlist"), dict) else {}) or {}
    c["screened"] = int(scr.get("screened_n") or 0)
    c["shortlist"] = int(sl.get("n") or 0)
    return c, COUNTS_TEXT.format(**c)


def counts_legend() -> list:
    return [{"key": k, "word": w, "text": t} for k, w, t in COUNTS_LEGEND]


# ── one card ───────────────────────────────────────────────────────────────────────────────────────────────────────
def state_label(read: dict) -> Optional[str]:
    st = read.get("state")
    tpl = STATE_LABEL.get(st)
    if tpl is None:
        return None
    return tpl.format(level_text=LEVEL_TEXT.format(px=GT._px(read.get("trigger"))),
                      listed_why=read.get("listed_why") or "")


def trigger_text(read: dict) -> Optional[str]:
    if GT._f(read.get("trigger")) is None:
        return None
    px = GT._px(read["trigger"])
    hhmm = _hm(read.get("entry_bar_t"))
    if read.get("state") in ("aplus", "triggered", "stopped", "listed") and hhmm:
        return TRIGGER_BROKE_TEXT.format(px=px, frame_text=FRAME_TEXT.get(read.get("frame"), FRAME_TEXT["5m"]),
                                         hhmm=hhmm)
    return TRIGGER_TEXT.format(px=px)


def stop_text(read: dict) -> Optional[str]:
    stop, risk, r = GT._f(read.get("stop")), GT._f(read.get("risk_pct")), GT._f(read.get("r_usd"))
    if stop is None or risk is None or r is None:
        return None
    from . import detectors as DT
    txt = STOP_TEXT.format(stop=GT._px(stop), pct=risk, r=f"{r:.2f}")
    if read.get("stop_src") == DT.SRC_ENTRY_5M:
        txt += STOP_SWITCH_TAIL.format(five=V.frame_minutes("5m", LUK), pct=LC.LUK_LOD_SWITCH_PCT)
    return txt


def adr_text(adr) -> Optional[str]:
    a = GT._f(adr)
    if a is None:
        return None
    pref = LC.LUK_ADR_PREF_PCT
    return (ADR_OVER_TEXT if a > pref else ADR_UNDER_TEXT).format(pref=pref, adr=a)


def flush_text(setup: str, read: dict) -> Optional[str]:
    if setup != "pullback_reversal":
        return None
    ema = LC.LUK_HOURLY_EMAS[0]
    f = read.get("facts") if isinstance(read.get("facts"), dict) else {}
    d, t = GT._f(f.get("flush_depth_pct")), _hm(f.get("touch_bar_t"))
    if t is None:
        return FLUSH_NONE_TEXT.format(ema=ema)
    if d is None:
        return FLUSH_TOUCH_TEXT.format(ema=ema, hhmm=t)
    return FLUSH_TEXT.format(d=d, ema=ema, hhmm=t)


def screens_text(rank: dict) -> Optional[str]:
    if not isinstance(rank, dict):
        return None
    parts = [SCREENS_RANK_TEXT.format(emoji=SUB_META[k][0], rank=rank[k]) for k in SCREEN_SUBS
             if isinstance(rank.get(k), int) and not isinstance(rank.get(k), bool)]
    return " · ".join(parts) or None


def _crit(c: dict) -> dict:
    """One criterion in the served shape {key, label, ok, value, need} (the screens module's `value_text` /
    `need_text` folded onto the detectors' names)."""
    return {"key": c.get("key"), "label": c.get("label"), "ok": c.get("ok"),
            "value": c.get("value", c.get("value_text")), "need": c.get("need", c.get("need_text"))}


def tile_of(doc: dict, setup: str, *, caps: dict) -> dict:
    """One card in the tile shape PatternChart draws off a 🚩 tile (symbol, href, tf, bars, curves, vol_avg, lines,
    markers, bands, badges, stats, why) + Luk's own read in words. `bars5/curves5/vol_avg5` are the stored names."""
    from chart_maps import board as board_mod
    read = dict((doc.get("setups") or {}).get(setup) or {})
    sym = str(doc.get("symbol") or "").upper()
    tile = doc.get("tile") if isinstance(doc.get("tile"), dict) else {}
    bars = list(tile.get("bars5") or [])
    curves = list(tile.get("curves5") or [])
    vol_avg = tile.get("vol_avg5") if isinstance(tile.get("vol_avg5"), dict) else None
    st = read.get("state")
    markers = GT._on_bars([{"date": read.get("entry_bar_t"), "kind": "buy", "label": "A+"}]
                          if st in ("aplus", "triggered", "stopped") and read.get("entry_bar_t") else [], bars)
    facts = doc.get("facts") if isinstance(doc.get("facts"), dict) else {}
    rf = read.get("facts") if isinstance(read.get("facts"), dict) else {}
    cap = caps.get(sym)
    at = GT._stamp_utc(doc.get("updated_at") or doc.get("at"))
    chips = {"tier_text": TI.tier_text(doc.get("tier") or facts.get("tier")),
             "adr_text": adr_text(facts.get("adr20_pct")),
             "cap_text": doc.get("cap_text"),
             "small_cap_text": TI.small_cap_text(cap),
             "confluence_text": rf.get("confluence_text"),
             "flush_text": flush_text(setup, read),
             "window_text": rf.get("window_text"),
             "screens_text": screens_text(doc.get("screens_rank"))}
    return {"symbol": sym, "name": doc.get("name"), "href": board_mod._href(sym), "tf": LUK.primary,
            "bars": bars, "curves": curves, "vol_avg": vol_avg, "bands": [], "badges": [], "stats": [],
            "lines": GT._tile_lines(read), "markers": markers,
            "why": read.get("listed_why") or read.get("reason") or None,
            "setup": setup, "state": st, "state_label": state_label(read),
            "frame_text": FRAME_TEXT.get(read.get("frame")),
            "trigger": GT._f(read.get("trigger")), "stop": GT._f(read.get("stop")),
            "risk_pct": GT._f(read.get("risk_pct")), "r_usd": GT._f(read.get("r_usd")),
            "trigger_text": trigger_text(read), "stop_text": stop_text(read),
            "listed_why": read.get("listed_why"),
            "criteria": [_crit(c) for c in read.get("criteria") or [] if isinstance(c, dict)],
            "chips": chips,
            "bars5": bars, "curves5": curves, "vol_avg5": vol_avg,
            "as_of_bar_t5": doc.get("as_of_bar_t5"), "entry_bar_t": read.get("entry_bar_t"),
            "read_at_text": READ_AT_TEXT.format(hhmm=GT._et(at).strftime("%H:%M")) if at else None,
            "gajjala": {"setup": setup, "state": st}}


def _order_key(t: dict) -> tuple:
    digits = "".join(ch for ch in str(t.get("entry_bar_t") or "") if ch.isdigit())
    newest = -float(digits) if digits else float("inf")
    return (_STATE_RANK.get(t.get("state"), len(TILE_STATES)),
            newest if t.get("state") != "forming" else 0.0, t.get("symbol") or "")


def tiles_for(reads: list, setup: str, *, caps: dict) -> list:
    """Every card of one setup: reads in a TILE_STATE (a `none` read is never carded), in the served order."""
    out = []
    for doc in reads:
        r = ((doc.get("setups") or {}) if isinstance(doc, dict) else {}).get(setup)
        if isinstance(r, dict) and r.get("state") in TILE_STATES and doc.get("symbol"):
            out.append(tile_of(doc, setup, caps=caps))
    out.sort(key=_order_key)
    return out


# ── the three screens ──────────────────────────────────────────────────────────────────────────────────────────────
def _pct_text(v) -> Optional[str]:
    return GT._pct(v)


def screen_row(r: dict) -> dict:
    from chart_maps import board as board_mod
    from . import screens as SC
    sym = str(r.get("symbol") or "").upper()
    return {"rank": r.get("rank"), "symbol": sym, "href": board_mod._href(sym),
            "price_text": GT._px(r.get("price")) if GT._f(r.get("price")) is not None else None,
            "pm_chg_text": _pct_text(r.get("pm_chg_pct")), "chg_text": _pct_text(r.get("chg_pct")),
            "perf_1m_text": _pct_text(r.get("perf_1m_pct")),
            "chg_from_open_text": _pct_text(r.get("chg_from_open_pct")),
            "cap_text": r.get("cap_text") or SC.CAP_UNKNOWN_TEXT,
            "avg_vol_text": SC.count(r.get("avg_vol_10d")), "px_vol_text": SC.money(r.get("px_vol")),
            "px_vol_1w_text": SC.money(r.get("px_vol_1w")), "vol_1w_text": SC.pct(r.get("vol_1w_pct")),
            "tier_text": r.get("tier_text") or TI.tier_text(r.get("tier")),
            "adr_text": adr_text(r.get("adr20_pct")),
            "small_cap_text": r.get("small_cap_text"),
            "pending_text": r.get("pending_text"),
            "criteria": [_crit(c) for c in r.get("criteria") or [] if isinstance(c, dict)]}


def screen_block(key: str, screens_doc: Optional[dict], latest: Optional[dict], session: date) -> dict:
    from . import screens as SC
    rows = (screens_doc or {}).get(key) if isinstance(screens_doc, dict) else None
    rows = [screen_row(r) for r in rows or [] if isinstance(r, dict)]
    this = isinstance(latest, dict) and latest.get("date") == session.isoformat()
    scr = (latest.get("screens") if this and isinstance(latest.get("screens"), dict) else None)
    if scr is None and isinstance(screens_doc, dict) and isinstance(screens_doc.get("counts"), dict):
        scr = screens_doc["counts"]
    if isinstance(scr, dict):
        nst = NOT_SCREENED_TEXT.format(not_screened=int(scr.get("not_screened_n") or 0),
                                       daily=LC.LUK_DAILY_MAX_NEW_PER_PASS,
                                       screened=int(scr.get("screened_n") or 0))
    else:
        nst = NOT_SCREENED_NONE_TEXT
    return {"key": key, "title": SC.title(key), "sorted_by_text": SCREEN_SORTED_BY[key],
            "heads": [{"key": k, "label": lab} for k, lab in SCREEN_HEADS[key]], "rows": rows,
            "not_screened_text": nst, "considerations_text": CONSIDERATIONS_TEXT, "honesty": SCREENS_HONESTY}


def _caps_from(screens_doc: Optional[dict]) -> dict:
    """{SYM: cap} from the session's screen rows (the read doc carries only the cap's text)."""
    out = {}
    for key in SCREEN_SUBS:
        for r in ((screens_doc or {}).get(key) or []) if isinstance(screens_doc, dict) else []:
            if isinstance(r, dict) and r.get("symbol") and GT._f(r.get("cap")) is not None:
                out[str(r["symbol"]).upper()] = GT._f(r.get("cap"))
    return out


# ── the sub ────────────────────────────────────────────────────────────────────────────────────────────────────────
def resolve_sub(sub: str, focus: str, *, tiles_by: dict, screens_doc: Optional[dict]) -> str:
    """A known sub → it. Empty with a `focus` symbol → the setup sub where that symbol's card has the best state, else
    the first screen listing it. Anything else → DEFAULT_SUB."""
    s = (sub or "").strip().lower() if isinstance(sub, str) else ""
    if s in SUB_KEYS:
        return s
    f = (focus or "").strip().upper() if isinstance(focus, str) else ""
    if not s and f:
        best = None
        for setup in SETUP_SUBS:
            for t in tiles_by.get(setup) or []:
                if t["symbol"] == f:
                    k = (_STATE_RANK.get(t.get("state"), len(TILE_STATES)), SETUP_SUBS.index(setup))
                    if best is None or k < best[0]:
                        best = (k, setup)
        if best:
            return best[1]
        for key in SCREEN_SUBS:
            if any(isinstance(r, dict) and str(r.get("symbol") or "").upper() == f
                   for r in ((screens_doc or {}).get(key) or [])):
                return key
    return LC.DEFAULT_SUB


def sub_title(key: str) -> str:
    emoji, label = SUB_META[key]
    if key in SETUP_SUBS:
        from . import alerts as AL
        return f"{emoji} {label} — {AL.ENTRY_WORDS[key]}"
    if key in SCREEN_SUBS:
        from . import screens as SC
        return SC.title(key)
    if key == PLAYBOOK_SUB:
        from . import playbook as PB
        return PB.TITLE
    from . import ledger as LG
    return LG.title_text()


def _clip_focus(tiles: list, focus: str, limit: int) -> list:
    """The focused symbol's card first, then the served order, cut to `limit` (the focus is never cut)."""
    f = (focus or "").strip().upper() if isinstance(focus, str) else ""
    if f:
        head = [t for t in tiles if t["symbol"] == f]
        tiles = head + [t for t in tiles if t["symbol"] != f]
    return tiles[:max(1, int(limit))]


def fault_payload(sub: str = "") -> dict:
    """The board when building it raised: 200 with the fault note (the route never 500s)."""
    s = (sub or "").strip().lower() if isinstance(sub, str) else ""
    return {"tab": LC.LUK_TAB, "label": LC.LUK_TAB_LABEL, "title": TITLE, "honesty": honesty(),
            "variant": variant_block(), "session": None, "pass": None, "strip": None, "subs": [],
            "sub": s if s in SUB_KEYS else LC.DEFAULT_SUB, "counts": None, "counts_text": None,
            "counts_legend": counts_legend(), "tiles": [], "order_note": ORDER_NOTE, "screens": None,
            "playbook": None, "track_record": None, "focus": None, "fault": True, "fault_text": FAULT_TEXT}


def build(sub: str = "", *, span: str = "", focus: str = "", limit: int = GC.TILE_LIMIT_DEFAULT,
          now: Optional[datetime] = None, store=None, owner: bool = False) -> dict:
    """The served board (Mongo only). `sub` = one of LC.SUBS' keys (unknown → DEFAULT_SUB; empty + `focus` → the
    server picks); `span` = the 🏁 day picker (ignored elsewhere); `focus` = a symbol to put first; `owner` is
    accepted for the route's shape and changes nothing yet."""
    st = _store(store)
    now = GT._et(now or GT._clock())
    session, is_today, in_window = session_for(now)
    latest = _soft("latest pass", st.latest_pass)
    cron = _soft("latest cron pass", st.latest_cron_pass)
    reads = [d for d in (_soft("reads", st.reads, session, default=[]) or []) if isinstance(d, dict)]
    screens_doc = _soft("screens", st.latest_screens, session)
    caps = _caps_from(screens_doc)
    tiles_by = {s: tiles_for(reads, s, caps=caps) for s in SETUP_SUBS}
    sub_k = resolve_sub(sub, focus, tiles_by=tiles_by, screens_doc=screens_doc)
    lim = limit if isinstance(limit, int) and not isinstance(limit, bool) else GC.TILE_LIMIT_DEFAULT
    lim = max(1, min(lim, GC.TILE_LIMIT_MAX))
    shown = {s: _clip_focus(t, focus, lim) for s, t in tiles_by.items()}
    screens_by = {k: screen_block(k, screens_doc, latest, session) for k in SCREEN_SUBS}
    from . import ledger as LG
    from . import playbook as PB
    pb = _soft("playbook", PB.playbook)
    tr = _soft("track record", LG.served_block, st, session, now, span=span if isinstance(span, str) else "")
    pb_n = sum(len(s.get("items") or []) for s in (pb or {}).get("sections") or [])
    n_of = {**{s: len(shown[s]) for s in SETUP_SUBS}, **{k: len(screens_by[k]["rows"]) for k in SCREEN_SUBS},
            PLAYBOOK_SUB: pb_n, TRACK_SUB: int((tr or {}).get("n_rows") or 0)}
    subs = [{"key": k, "emoji": e, "label": lab, "n": n_of.get(k, 0), "title": _soft("sub title", sub_title, k,
                                                                                    default=f"{e} {lab}")}
            for k, e, lab in LC.SUBS]
    counts, counts_text = counts_block(reads, latest, session)
    f = (focus or "").strip().upper() if isinstance(focus, str) else ""
    out = {"tab": LC.LUK_TAB, "label": LC.LUK_TAB_LABEL, "title": TITLE, "honesty": honesty(),
           "variant": variant_block(), "session": session_block(now, session, is_today, in_window),
           "pass": pass_block(latest, cron, now, session, in_window), "strip": strip_block(latest, session),
           "subs": subs, "sub": sub_k, "counts": counts, "counts_text": counts_text,
           "counts_legend": counts_legend(),
           "tiles": shown[sub_k] if sub_k in SETUP_SUBS else [], "order_note": ORDER_NOTE,
           "screens": screens_by[sub_k] if sub_k in SCREEN_SUBS else None,
           "playbook": pb if sub_k == PLAYBOOK_SUB else None,
           "track_record": tr if sub_k == TRACK_SUB else None,
           "focus": f or None, "fault": False, "fault_text": None}
    return GT._plain(out)


__all__ = ["TITLE", "HONESTY_LIVE", "HONESTY_SHADOW", "PUSH_TEXT_LIVE", "PUSH_TEXT_SHADOW", "honesty", "push_text",
           "FAULT_TEXT", "PAYLOAD_KEYS", "TILE_STATES", "build", "fault_payload", "session_for",
           "tile_of", "tiles_for", "resolve_sub", "counts_block", "pass_block", "strip_block", "screen_block",
           "latency_text", "cost_text"]
