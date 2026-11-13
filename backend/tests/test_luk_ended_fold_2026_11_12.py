"""🏁 Luk's — an ended trade leaves the cards he reads as live, in real time (SPEC lukend §3.1–3.3 / §3.9, WP-A,
2026-11-12).

Ajay 2026-11-12, verbatim: "Is this still good ro enter? From Luks" → "I shouldn't be seeing this" → "I want it to be
realtime".

luk.ledger.card_trades (READ ONLY, fails closed) + luk.tab's fold: rule 1 the read says `stopped`; rule 2 the 🏁 graded
the exit of a TRADE card (C5); rule 3 the card-close test, built but OFF (CARD_CLOSE_EXIT_ON = False — HIS CALL #1, C1);
rule 4 the served `live_fold` rule the FE's 30 s card poll folds by (C6: chart_maps.live_card imported only inside that
branch), and the window words. `build` splits each setup sub into the live `tiles` and ONE served `ended` block.
NEGATIVES throughout (each named test_NEGATIVE_…). Display only: nothing here rings, grades or writes.
"""
from __future__ import annotations

import ast
import inspect
import json
import random
import re
import string
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import chart_maps
from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.gajjala import tab as GT
from chart_maps.luk import constants as LC
from chart_maps.luk import daily as DL
from chart_maps.luk import ledger as LG
from chart_maps.luk import store as LS
from chart_maps.luk import tab as T
from chart_maps.luk.variant import LUK
from tests.test_gajjala_store import FakeColl
from tests.test_luk_tab import (BWORD, EDGE, NOW, PASS_AT, S, _crit, _pass_body, _read, _read_doc, _reads,
                                _screens_doc)

PR, ORH, IDP = LC.SETUPS
UTC = timezone.utc
TAB_PATH = Path(T.__file__)
LEDGER_PATH = Path(LG.__file__)
HEAD_LEDGER_DEFS = {   # ledger.py's top-level defs at HEAD 037dc4bb (before this package)
    'LedgerReadError', '_alert_block', '_as_date', '_blank_walk', '_chart_cell', '_chart_counts', '_days_capped',
    '_default_fetch', '_ema_n', '_flag_key', '_hhmm', '_lag_min', '_md', '_parse_at', '_r_text', '_rth_bars',
    '_sort_key', '_static_keys', '_trade_facts', '_write', 'bucket_of', 'cells', 'charts_block', 'clip', 'close_utc',
    'counts_of', 'empty_text', 'entry_weeks', 'fill', 'fill_window', 'flags_text', 'grade_step', 'honesty',
    'honesty_text', 'mark_dups', 'partials_text', 'plan_text', 'rang_text', 'record_from', 'record_sessions', 'row_id',
    'row_of', 'rows_for', 'rule_text', 'served_block', 'setup_label', 'span_sessions', 'state_of', 'stop_r',
    'title_text', 'track_row', 'views_block', 'walk'}
NEW_TEMPLATES = ("ENDED_HEAD_TEXT", "ENDED_WHEN_TODAY", "ENDED_WHEN_DAY", "ENDED_TOGGLE_TEXT", "ENDED_NOTE_TEXT",
                 "ENDED_MORE_TEXT", "ENDED_SUB_TAIL", "ENDED_STOP_READ_TEXT", "ENDED_LEDGER_TEXT", "ENDED_LEDGER_TAIL",
                 "ENDED_CLOSE_TEXT", "LIVE_FOLD_TEXT", "WINDOW_CLOSED_TEXT", "OPEN_TRADE_TEXT", "ENDED_EMOJI")
WIN = [_crit("trigger_break"), _crit("in_window")]            # a ↩️ / 🔔 read: the detectors serve `in_window`


def et(d: date, hh: int, mm: int, ss: int = 0) -> datetime:
    """An ET wall time on `d` as aware UTC (November 2026 = EST, UTC−5)."""
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=GT.ET).astimezone(UTC)


def _ctx(now, *, session=S, is_today=True, trades=None):
    return {"trades": trades or {}, "now": GT._et(now), "session": session, "is_today": is_today}


def _doc(sym, setup, state, **kw):
    return _read_doc(sym, {setup: _read(setup, state, **kw)})


def _claim(sym, setup, trigger, stop, *, d=S, at=None, state="shadow"):
    key = GA.shadow_key(d, sym, setup, LUK) if state == "shadow" else GA.claim_key(d, sym, setup, LUK)
    return {"_id": key, "state": state, "symbol": sym, "setup": setup, "date": d.isoformat(),
            "at": (at or datetime(d.year, d.month, d.day, 14, 40, tzinfo=UTC)).isoformat(),
            "trigger": trigger, "stop": stop}


def _ledger(sym, setup, *, d=S, exit_=None, through=None, fill_t="2026-11-03T14:42:00+00:00", fill_px=None,
            version=None, entry=LG.FILLED, walk=True, r=None, exit_t=None, exit_date=None, sessions=1):
    w = LG._blank_walk()
    w.update(exit=exit_, through_date=through, exit_t=exit_t, exit_date=exit_date, r=r, sessions=sessions,
             state=("stopped" if exit_ == "stop" else exit_ or LG.OPEN))
    return {"_id": LG.row_id(d.isoformat(), sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "kind": "aplus", "version": LG.GRADE_VERSION if version is None else version,
            "fill": {"entry": entry, "fill_px": fill_px, "fill_t": fill_t, "fill_date": d.isoformat()},
            "walk": w if walk else None}


def make_store(docs=(), claims=(), ledger=(), *, passes=True, screens=True, fail_alerts=False, fail_ledger=False):
    colls = {n: FakeColl() for n in LS.LOGICAL}
    colls[GS.ALERTS] = FakeColl(fail=fail_alerts)
    colls[GS.LEDGER] = FakeColl(fail=fail_ledger)
    colls[LS.SCREENS_KEY] = FakeColl()
    st = LS.LukStore(colls=colls)
    if passes:
        st.record_pass(S, PASS_AT, _pass_body())
    for d in docs:
        colls[GS.READS].docs[d["_id"]] = d
    if screens:
        sd = _screens_doc()
        colls[LS.SCREENS_KEY].docs[sd["_id"]] = sd
    for c in claims:
        colls[GS.ALERTS].docs[c["_id"]] = c
    for g in ledger:
        colls[GS.LEDGER].docs[g["_id"]] = g
    st._test_colls = colls
    return st


def build(sub="", *, store=None, now=NOW, **kw):
    return T.build(sub, now=now, store=store if store is not None else make_store(_reads()), **kw)


def _walk(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _exit_text(claim, ledger_doc):
    return LG.cells(LG.row_of(claim), ledger_doc)["exit_text"]


# ── 1. a stopped read folds ────────────────────────────────────────────────────────────────────────────────────────
def test_a_stopped_read_folds_out_of_the_live_cards():
    out = build(ORH)
    assert "CCC" not in {t["symbol"] for t in out["tiles"]}
    e = out["ended"]
    assert set(e) == set(T.ENDED_KEYS) and e["n"] == 1 and [t["symbol"] for t in e["tiles"]] == ["CCC"]
    c = e["tiles"][0]
    assert c["ended"] is True and c["ended_why"] == LG.EXITS[0] == "stop"
    assert c["ended_text"] == T.ENDED_STOP_READ_TEXT.format(stop="50.10") == (
        "🏁 ended — a closed bar after the trigger traded at or under the stop 50.10 (Luk's exit)")
    assert c["trade_text"] is None and c["live_fold"] is None
    sub = {s["key"]: s for s in out["subs"]}[ORH]
    assert sub["n"] == 2 == len(out["tiles"])
    assert sub["title"].endswith(" · 1 ended — folded under the cards")
    assert e["emoji"] == "🏁" and e["head_text"] == "ended today — stopped or closed below the daily 9 EMA (Luk's exit)"
    assert e["toggle_text"] == T.ENDED_TOGGLE_TEXT and e["note_text"] == T.ENDED_NOTE_TEXT
    assert e["more_text"] is None and e["open"] is False


def test_a_stopped_read_with_a_ledger_stop_exit_carries_the_ledger_tail():
    cl = _claim("CCC", ORH, 51.0, 50.1)
    lg = _ledger("CCC", ORH, exit_="stop", fill_px=51.0, exit_t="2026-11-03T14:50:00+00:00", exit_date=S.isoformat(),
                 r=-1.0, through=S.isoformat())
    out = build(ORH, store=make_store(_reads(), claims=[cl], ledger=[lg]))
    c = out["ended"]["tiles"][0]
    tail = _exit_text(cl, lg)
    assert tail.strip()
    assert c["ended_text"] == T.ENDED_STOP_READ_TEXT.format(stop="50.10") + " · 🏁 " + tail


# ── 2. NEGATIVE no ended card / not a setup sub / the fault payload [C4] ─────────────────────────────────────────
def test_NEGATIVE_no_ended_card_serves_an_empty_block_and_other_subs_none():
    e = build(PR)["ended"]
    assert e["n"] == 0 and e["tiles"] == [] and e["more_text"] is None and e["open"] is False
    assert e["head_text"] and e["emoji"] == T.ENDED_EMOJI                        # the FE needs the words for a fold
    assert not {s["key"]: s for s in build(PR)["subs"]}[PR]["title"].endswith("folded under the cards")
    for k in list(T.SCREEN_SUBS) + [T.PLAYBOOK_SUB, T.TRACK_SUB]:
        assert build(k)["ended"] is None, k


def test_NEGATIVE_the_fault_payload_serves_ended_none():
    f = T.fault_payload()
    assert f["ended"] is None and set(f) == set(T.PAYLOAD_KEYS) and "ended" in T.PAYLOAD_KEYS


# ── 3. live_fold [C7] ──────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("state", ["aplus", "triggered"])
@pytest.mark.parametrize("hhmm", [(10, 12), (9, 29), (8, 0)])
def test_live_fold_on_a_trade_card_before_the_close(state, hhmm):
    from chart_maps import live_card as LCARD
    d = _doc("AAA", PR, state, trigger=12.40, stop=11.98, criteria=WIN)
    t = T.tile_of(d, PR, caps={}, ctx=_ctx(et(S, *hhmm)))
    assert t["live_fold"] == {"kind": LCARD.VS_KINDS[1], "session": T.LIVE_FOLD_SESSION,
                              "until_epoch": LG.close_utc(S).timestamp(),
                              "text": ("🏁 ended — the live price traded at or under the stop 11.98 (Luk's exit) · the "
                                       "next pass reads it on the closed bar")}
    assert t["ended"] is False and t["ended_why"] is None and t["ended_text"] is None


# ── 4. NEGATIVE live_fold None ─────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("state", ["forming", "listed", "stopped"])
def test_NEGATIVE_no_live_fold_on_a_card_that_is_not_a_trade(state):
    d = _doc("AAA", PR, state, trigger=12.40, stop=11.98)
    assert T.tile_of(d, PR, caps={}, ctx=_ctx(et(S, 10, 12)))["live_fold"] is None


@pytest.mark.parametrize("now", [et(S, 16, 0, 0), et(S, 16, 30)])
def test_NEGATIVE_no_live_fold_at_or_after_the_close(now):
    d = _doc("AAA", PR, "triggered", trigger=12.40, stop=11.98)
    assert T.tile_of(d, PR, caps={}, ctx=_ctx(now))["live_fold"] is None


def test_NEGATIVE_no_live_fold_on_a_past_session():
    d = _doc("AAA", PR, "aplus", trigger=12.40, stop=11.98)
    ctx = _ctx(et(S + timedelta(days=1), 3, 0), is_today=False)
    assert T.tile_of(d, PR, caps={}, ctx=ctx)["live_fold"] is None


@pytest.mark.parametrize("stop", [None, float("nan"), float("inf"), 0.0, -1.0, "x"])
def test_NEGATIVE_no_live_fold_without_a_finite_positive_stop(stop):
    d = _doc("AAA", PR, "aplus", trigger=12.40, stop=stop)
    assert T.tile_of(d, PR, caps={}, ctx=_ctx(et(S, 10, 12)))["live_fold"] is None


def test_NEGATIVE_no_live_fold_without_ctx():
    d = _doc("AAA", PR, "aplus", trigger=12.40, stop=11.98)
    t = T.tile_of(d, PR, caps={})
    assert t["live_fold"] is None and t["trade_text"] is None and t["ended"] is False


# ── 5. one engine: the house live compare and the house session word ──────────────────────────────────────────────
def test_live_fold_kind_is_the_house_live_vs_kind():
    from chart_maps import live_card as LCARD
    from supply_demand import zone_edge
    d = _doc("AAA", PR, "triggered", trigger=12.40, stop=11.98)
    t = T.tile_of(d, PR, caps={}, ctx=_ctx(et(S, 10, 12)))
    now_et = GT._et(et(S, 10, 12))
    lvl = t["live_level"]
    for px in (11.98, 11.5, 11.9849):
        assert LCARD.live_vs(px, lvl, now_et)["kind"] == t["live_fold"]["kind"]
    for px in (12.0, 12.39, 12.40, 13.0):                                       # NEGATIVE between / over_trigger
        assert LCARD.live_vs(px, lvl, now_et)["kind"] != t["live_fold"]["kind"]
    assert zone_edge.session_state(GT._et(et(S, 10, 0))) == T.LIVE_FOLD_SESSION
    assert LCARD.VS_KINDS[1] == "under_stop"


# ── 6. window words ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", [PR, ORH])
def test_after_his_window_a_triggered_card_says_so_and_stays(setup):
    d = _doc("AAA", setup, "triggered", trigger=12.40, stop=11.98, criteria=WIN)
    t = T.tile_of(d, setup, caps={}, ctx=_ctx(et(S, 10, 31)))
    assert t["trade_text"] == "entry window closed 10:30 ET — not an entry"
    assert t["ended"] is False and t["live_fold"] is not None


@pytest.mark.parametrize("hhmm", [(10, 30, 0), (10, 12, 0)])
def test_NEGATIVE_inside_his_window_no_window_words(hhmm):
    d = _doc("AAA", PR, "triggered", trigger=12.40, stop=11.98, criteria=WIN)
    assert T.tile_of(d, PR, caps={}, ctx=_ctx(et(S, *hhmm)))["trade_text"] is None


def test_NEGATIVE_an_aplus_card_never_gets_window_words_or_folds_by_time():
    d = _doc("AAA", PR, "aplus", trigger=12.40, stop=11.98, criteria=WIN)
    t = T.tile_of(d, PR, caps={}, ctx=_ctx(et(S, 10, 31)))
    assert t["trade_text"] is None and t["ended"] is False


@pytest.mark.parametrize("state", ["forming", "listed"])
def test_NEGATIVE_forming_and_listed_cards_get_no_window_words(state):
    d = _doc("AAA", PR, state, trigger=12.40, stop=11.98, criteria=WIN)
    t = T.tile_of(d, PR, caps={}, ctx=_ctx(et(S, 10, 31)))
    assert t["trade_text"] is None and t["ended"] is False


# ── 7. 📦 inside day: the window is the regular session ─────────────────────────────────────────────────────────────
def test_inside_day_window_is_the_regular_session():
    d = _doc("CCC", IDP, "triggered", trigger=49.0, stop=48.0)                   # no in_window criterion served
    assert T.window_end(d["setups"][IDP], S).strftime("%H:%M") == "16:00"
    assert T.tile_of(d, IDP, caps={}, ctx=_ctx(et(S, 14, 0)))["trade_text"] is None
    assert T.tile_of(d, IDP, caps={}, ctx=_ctx(et(S, 16, 30)))["trade_text"] == (
        "entry window closed 16:00 ET — not an entry")
    half = date(2026, 11, 27)
    d2 = dict(d, date=half.isoformat())
    t = T.tile_of(d2, IDP, caps={}, ctx=_ctx(et(half, 13, 30), session=half))
    assert t["trade_text"] == "entry window closed 13:00 ET — not an entry"


def test_the_window_end_is_the_constant_not_a_typed_time(monkeypatch):
    r = _read(PR, "triggered", trigger=12.4, stop=11.98, criteria=WIN)
    assert T.window_end(r, S).strftime("%H:%M") == "10:30"
    monkeypatch.setattr(LC, "LUK_TRIGGER_WINDOW_END_MIN", 45)
    assert T.window_end(r, S).strftime("%H:%M") == "10:15"


# ── 8. an open 🏁 trade after the close ───────────────────────────────────────────────────────────────────────────
def test_an_open_ledger_trade_after_the_close_says_open_trade_since():
    d = _doc("OPN", PR, "triggered", trigger=12.40, stop=11.98, criteria=WIN)
    cl = _claim("OPN", PR, 12.40, 11.98)
    lg = _ledger("OPN", PR, exit_=None, through=S.isoformat(), fill_t="2026-11-03T14:42:00+00:00", fill_px=12.40)
    out = build(PR, store=make_store([d], claims=[cl], ledger=[lg]), now=et(S, 17, 10))
    t = next(x for x in out["tiles"] if x["symbol"] == "OPN")
    assert t["ended"] is False and t["trade_text"] == "open trade since 09:42 ET, not a new entry"
    assert t["live_fold"] is None                                               # after the close


def test_NEGATIVE_in_session_the_same_card_says_window_closed():
    d = _doc("OPN", PR, "triggered", trigger=12.40, stop=11.98, criteria=WIN)
    cl = _claim("OPN", PR, 12.40, 11.98)
    out = build(PR, store=make_store([d], claims=[cl]), now=et(S, 10, 31))     # no 🏁 doc in-session
    t = next(x for x in out["tiles"] if x["symbol"] == "OPN")
    assert t["trade_text"] == "entry window closed 10:30 ET — not an entry" and t["ended"] is False


# ── 9. the 🏁 exits fold a TRADE card; never a listed / forming card [C5] ──────────────────────────────────────────
def _ema9_ledger(sym, setup):
    return _ledger(sym, setup, exit_=LG.EXITS[1], through=S.isoformat(), fill_px=12.40, r=-0.5,
                   exit_date=S.isoformat())


def _stop_ledger(sym, setup):
    return _ledger(sym, setup, exit_="stop", through=S.isoformat(), fill_px=12.40, r=-1.0,
                   exit_t="2026-11-03T15:10:00+00:00", exit_date=S.isoformat())


@pytest.mark.parametrize("state", ["triggered", "aplus"])
@pytest.mark.parametrize("which", ["ema9", "stop"])
def test_a_ledger_exit_folds_a_trade_card(state, which):
    d = _doc("LGX", PR, state, trigger=12.40, stop=11.98, criteria=WIN)
    cl = _claim("LGX", PR, 12.40, 11.98)
    lg = _ema9_ledger("LGX", PR) if which == "ema9" else _stop_ledger("LGX", PR)
    out = build(PR, store=make_store([d], claims=[cl], ledger=[lg]), now=et(S + timedelta(days=1), 3, 0))
    assert "LGX" not in {t["symbol"] for t in out["tiles"]}
    t = out["ended"]["tiles"][0]
    assert t["ended"] is True and t["ended_why"] == (LG.EXITS[1] if which == "ema9" else LG.EXITS[0])
    assert t["ended_text"] == T.ENDED_LEDGER_TEXT.format(exit=_exit_text(cl, lg))
    assert t["ended_text"].startswith("🏁 ended — ") and "as graded on the 🏁 Track record" in t["ended_text"]


@pytest.mark.parametrize("state", ["listed", "forming"])
@pytest.mark.parametrize("which", ["ema9", "stop"])
def test_NEGATIVE_a_listed_or_forming_card_with_a_ledger_row_never_folds(state, which):
    d = _doc("LGX", PR, state, trigger=12.40, stop=11.98, criteria=WIN, listed_why="x")
    cl = _claim("LGX", PR, 12.40, 11.98)
    lg = _ema9_ledger("LGX", PR) if which == "ema9" else _stop_ledger("LGX", PR)
    out = build(PR, store=make_store([d], claims=[cl], ledger=[lg]), now=et(S, 17, 10))
    assert "LGX" in {t["symbol"] for t in out["tiles"]} and out["ended"]["n"] == 0


def test_card_trades_reads_the_ledgers_own_answer():
    cl = _claim("LGX", PR, 12.40, 11.98)
    lg = _ema9_ledger("LGX", PR)
    got = LG.card_trades(make_store(claims=[cl], ledger=[lg]), S)
    assert got == {("LGX", PR): {"state": LG.EXITS[1], "exit_text": _exit_text(cl, lg),
                                 "fill_t": "2026-11-03T14:42:00+00:00", "through_date": S.isoformat()}}


def test_NEGATIVE_card_trades_another_version_reads_pending():
    cl = _claim("LGX", PR, 12.40, 11.98)
    lg = _ledger("LGX", PR, exit_=LG.EXITS[1], through=S.isoformat(), fill_px=12.4, r=-0.5, version=-1)
    got = LG.card_trades(make_store(claims=[cl], ledger=[lg]), S)[("LGX", PR)]
    assert got["state"] == "pending" and got["fill_t"] is None and got["through_date"] is None


# ── 10. MSTR tonight [C1] ─────────────────────────────────────────────────────────────────────────────────────────
M = date(2026, 11, 12)
MSTR_EMA9 = 129.3691139331359
MSTR_SENTENCE = ("🏁 ended — the 15:55–16:00 ET bar closed 114.31 under the daily 9 EMA (129.37 at the prior close; the "
                 "official close can differ) — Luk's exit")


def _mstr_doc(*, close=114.31, ema=MSTR_EMA9, as_of="2026-11-11", last_t="2026-11-12 16:00", s_flag=None,
              facts=None, sym="MSTR"):
    bars = [{"t": "2026-11-12 15:50", "o": 114.5, "h": 114.9, "l": 114.0, "c": 114.4, "v": 1000},
            {"t": "2026-11-12 15:55", "o": 114.4, "h": 114.6, "l": 114.1, "c": 114.2, "v": 1000}]
    if last_t is not None:
        b = {"t": last_t, "o": 114.2, "h": 114.5, "l": 114.0, "c": close, "v": 1000}
        if s_flag:
            b["s"] = s_flag
        bars.append(b)
    pr = dict(_read(PR, "triggered", frame="1m", trigger=114.3114, stop=112.32, risk_pct=1.74, r_usd=1.99,
                    entry_bar_t="2026-11-12 09:36", criteria=WIN), as_of_bar_t="2026-11-12 16:00")
    orh = dict(_read(ORH, "triggered", frame="5m", trigger=114.61, stop=112.32, risk_pct=2.0, r_usd=2.29,
                     entry_bar_t="2026-11-12 09:40", criteria=WIN), as_of_bar_t="2026-11-12 16:00")
    fx = {"ema9": ema, "as_of": as_of, "close": 120.0, "tier": "lead"} if facts is None else facts
    at = et(M, 16, 1, 43)
    return {"_id": f"{M.isoformat()}|{sym}", "date": M.isoformat(), "symbol": sym, "at": at, "updated_at": at,
            "as_of_bar_t5": "2026-11-12 16:00", "setups": {PR: pr, ORH: orh}, "facts": fx,
            "tile": {"bars5": bars, "curves5": [], "vol_avg5": None}, "screens_rank": {}, "tier": "lead",
            "cap_text": "$30B", "refresh_only": True}


def _mstr_store(doc=None, ledger=()):
    claims = [_claim("MSTR", s, t, 112.32, d=M, at=datetime(2026, 11, 12, 14, 41, tzinfo=UTC), state="pushed")
              for s, t in ((PR, 114.3114), (ORH, 114.61))]
    return make_store([doc or _mstr_doc()], claims=claims, ledger=ledger, passes=False, screens=False)


MSTR_NOW = et(M, 17, 10)


def test_NEGATIVE_mstr_by_default_stays_live_with_the_window_words():
    for setup in (PR, ORH):
        out = build(setup, store=_mstr_store(), now=MSTR_NOW)
        t = next(x for x in out["tiles"] if x["symbol"] == "MSTR")
        assert t["ended"] is False and t["ended_text"] is None and out["ended"]["n"] == 0
        assert t["trade_text"] == "entry window closed 10:30 ET — not an entry"


def test_mstr_folds_by_its_close_bar_only_with_the_switch_on(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    for setup in (PR, ORH):
        out = build(setup, store=_mstr_store(), now=MSTR_NOW)
        assert "MSTR" not in {x["symbol"] for x in out["tiles"]}
        t = out["ended"]["tiles"][0]
        assert t["ended"] is True and t["ended_why"] == LG.EXITS[1] and t["ended_text"] == MSTR_SENTENCE


# ── 11. NEGATIVES of the close test (switch ON) + the ARRY words [C2] ────────────────────────────────────────────
def _fold_mstr(doc, now=MSTR_NOW, trade=None, setup=PR):
    trades = {("MSTR", setup): trade} if trade else {}
    return T.fold_of(doc, setup, doc["setups"][setup], _ctx(now, session=M, trades=trades))


@pytest.mark.parametrize("kw", [
    {"close": MSTR_EMA9},                                                         # close == ema
    {"close": 130.0},                                                              # close > ema
    {"last_t": None},                                                              # the read's last bar 15:55
    {"as_of": "2026-11-10"},                                                       # facts two sessions back
    {"facts": DL.pending()},                                                       # a Pending
    {"facts": {"pending": True, "pending_text": DL.PENDING_TEXT}},                 # a stored Pending
    {"ema": None}, {"ema": float("nan")},
    {"s_flag": "ah"},                                                              # the 16:00 bar flagged
    {"close": float("nan")}, {"close": 0.0},
])
def test_NEGATIVE_the_close_test_does_not_fold(monkeypatch, kw):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    assert _fold_mstr(_mstr_doc(**kw))["ended"] is False


def test_NEGATIVE_the_close_test_waits_for_the_close(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    assert _fold_mstr(_mstr_doc(last_t=None), now=et(M, 15, 58))["ended"] is False
    settle = LG.close_utc(M) + timedelta(seconds=GC.BAR_SETTLE_SEC)
    assert _fold_mstr(_mstr_doc(), now=settle - timedelta(seconds=1))["ended"] is False
    assert _fold_mstr(_mstr_doc(), now=settle)["ended"] is True                  # positive tail


def test_NEGATIVE_facts_none_never_folds(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    d = _mstr_doc()
    d["facts"] = None
    assert _fold_mstr(d)["ended"] is False


def test_NEGATIVE_the_ledger_open_through_today_wins(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    tr = {"state": LG.OPEN, "exit_text": "open", "fill_t": "2026-11-12T14:42:00+00:00", "through_date": M.isoformat()}
    assert _fold_mstr(_mstr_doc(), trade=tr)["ended"] is False


def test_a_deferred_ledger_doc_lets_the_card_test_run(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    tr = {"state": LG.OPEN, "exit_text": LG.PENDING_TEXT, "fill_t": "2026-11-12T14:42:00+00:00",
          "through_date": None}                                                   # filled + walk None (deferred)
    f = _fold_mstr(_mstr_doc(), trade=tr)
    assert f["ended"] is True and f["ended_text"] == MSTR_SENTENCE


def test_the_arry_words_print_both_numbers_apart(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    assert T._px_apart(4.725, 4.725080181218225) == ("4.7250", "4.7251")
    f = _fold_mstr(_mstr_doc(close=4.725, ema=4.725080181218225))
    assert f["ended"] is True
    assert "closed 4.7250 under" in f["ended_text"] and "(4.7251 at the prior close" in f["ended_text"]


def test_NEGATIVE_near_ties_never_print_the_same_two_numbers(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    rng = random.Random(20261112)
    for _ in range(200):
        a = rng.choice([rng.uniform(0.05, 0.99), rng.uniform(1.0, 900.0)])
        step = 0.0001 if a < 1 else 0.01
        b = a + rng.uniform(1e-13, step / 2)
        if not a < b:
            continue
        pa, pb = T._px_apart(a, b)
        assert pa != pb, (a, b)
        f = _fold_mstr(_mstr_doc(close=a, ema=b))
        assert f["ended"] is True and f"closed {pa} under" in f["ended_text"] and f"({pb} at the prior" in \
            f["ended_text"]


def test_a_far_pair_keeps_the_plain_price_words():
    assert T._px_apart(114.31, MSTR_EMA9) == (GT._px(114.31), GT._px(MSTR_EMA9)) == ("114.31", "129.37")


# ── 12. the identity [C8]: the prior close's 9 EMA answers the walk's test, two loaders apart ─────────────────────
def _frame(closes, dates):
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": np.full(len(c), 1e6)},
                        index=pd.DatetimeIndex(dates))


def test_the_prior_ema_identity_over_two_year_long_frames():
    span = LC.LUK_PULLBACK_DAILY_EMA
    for seed in range(200):
        rng = np.random.default_rng(seed)
        n_year, lag = 252, 30 + int(rng.integers(0, 20))
        n = n_year + lag
        closes = 50.0 * np.exp(np.cumsum(rng.normal(0, 0.03, n)))
        dates = pd.bdate_range("2025-01-02", periods=n)
        a = _frame(closes[:n_year], dates[:n_year])                              # fetched on day d
        b = _frame(closes[lag:], dates[lag:])                                    # fetched `lag` sessions later
        d = dates[n_year - 1].date()
        close_d = float(closes[n_year - 1])
        walk_ema = DL._close_facts(a, d, 0)["ema9_close"]
        card = DL.facts_from_frame(DL.closed_before(b, d))
        assert card["as_of"] == dates[n_year - 2].date().isoformat()
        assert (close_d < walk_ema) == (close_d < card[f"ema{span}"]), seed
        prior_a = DL.facts_from_frame(DL.closed_before(a, d))[f"ema{span}"]
        assert abs(prior_a - card[f"ema{span}"]) <= 1e-9 * abs(prior_a), seed
        assert (dates[lag] - dates[0]).days >= 30


# ── 13. focus on an ended card ────────────────────────────────────────────────────────────────────────────────────
def test_focus_on_an_ended_card_opens_the_fold_and_picks_its_sub():
    docs = _reads() + [_doc("ZZZ", ORH, "stopped", frame="1m", trigger=9.0, stop=8.5, risk_pct=5.0, r_usd=0.5,
                            entry_bar_t="2026-11-03 09:34")]
    st = make_store(docs)
    out = build("", focus="zzz", store=st)
    assert out["sub"] == ORH
    e = out["ended"]
    assert e["open"] is True and e["tiles"][0]["symbol"] == "ZZZ" and e["n"] == 2
    assert "ZZZ" not in {t["symbol"] for t in out["tiles"]}


def test_NEGATIVE_focus_on_a_live_card_keeps_the_fold_closed():
    out = build(ORH, focus="AAA")
    assert out["ended"]["open"] is False and out["tiles"][0]["symbol"] == "AAA"


# ── 14. more ended cards than the limit ───────────────────────────────────────────────────────────────────────────
def test_more_ended_cards_than_the_limit_are_cut_and_counted():
    docs = [_doc(f"S{i}Q", ORH, "stopped", frame="1m", trigger=9.0, stop=8.5, risk_pct=5.0, r_usd=0.5,
                 entry_bar_t=f"2026-11-03 09:3{i}") for i in range(3)]
    out = build(ORH, store=make_store(docs), limit=2)
    e = out["ended"]
    assert e["n"] == 3 and len(e["tiles"]) == 2
    assert e["more_text"] == "+1 more ended — the count covers all 3"
    assert {s["key"]: s for s in out["subs"]}[ORH]["title"].endswith(" · 3 ended — folded under the cards")
    assert out["tiles"] == [] and {s["key"]: s["n"] for s in out["subs"]}[ORH] == 0


# ── 15. the 🏁 unchanged ──────────────────────────────────────────────────────────────────────────────────────────
def test_the_track_record_is_unchanged():
    st = make_store(_reads(), claims=[_claim("AAA", PR, 12.40, 11.98)])
    assert build(T.TRACK_SUB, store=st)["track_record"] == GT._plain(LG.served_block(st, S, GT._et(NOW)))


def test_ledger_gains_only_card_trades():
    tree = ast.parse(LEDGER_PATH.read_text(encoding="utf-8"))
    defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert defs == HEAD_LEDGER_DEFS | {"card_trades"}
    assert "card_trades" in LG.__all__


# ── 16. pushes unchanged: no writer, no sender in the fold ────────────────────────────────────────────────────────
FORBIDDEN = ("AL.", "alerts", "notify", "send", "push", "update_one", "insert", "upsert")


@pytest.mark.parametrize("fn", [T.fold_of, T.close_exit, T._px_apart, T.ended_block, T.live_tiles, T.window_end,
                                T.window_closed_hhmm, LG.card_trades])
def test_the_fold_never_rings_or_writes(fn):
    src = inspect.getsource(fn)
    assert [w for w in FORBIDDEN if w in src] == []


def test_NEGATIVE_the_source_guard_catches_a_planted_word():
    assert [w for w in FORBIDDEN if w in inspect.getsource(T.fold_of) + "\n    AL.run_pass()\n"] != []


def test_a_fixture_build_makes_zero_store_writes():
    cl = _claim("LGX", PR, 12.40, 11.98)
    st = make_store(_reads() + [_doc("LGX", PR, "triggered", trigger=12.4, stop=11.98, criteria=WIN)],
                    claims=[cl], ledger=[_ema9_ledger("LGX", PR)])
    before = {k: c.writes for k, c in st._test_colls.items()}
    for k in T.SUB_KEYS:
        build(k, store=st)
    assert {k: c.writes for k, c in st._test_colls.items()} == before


# ── 17. NaN is never served; card_trades fails closed ─────────────────────────────────────────────────────────────
def test_NEGATIVE_nan_is_never_served_in_the_fold(monkeypatch):
    monkeypatch.setattr(T, "CARD_CLOSE_EXIT_ON", True)
    nan = float("nan")
    docs = [_doc("NNA", ORH, "stopped", frame="1m", trigger=9.0, stop=nan, risk_pct=5.0, r_usd=0.5,
                 entry_bar_t="2026-11-03 09:34"),
            _doc("NNB", PR, "triggered", trigger=9.0, stop=nan, criteria=WIN)]
    for sub in (PR, ORH):
        out = build(sub, store=make_store(docs), now=et(S, 10, 31))
        assert "nan" not in json.dumps(out)
        texts = [x for t in out["tiles"] + out["ended"]["tiles"] for x in _walk({k: t[k] for k in T.FOLD_KEYS})]
        assert not any("nan" in x.lower() for x in texts)
    for kw in ({"ema": nan}, {"close": nan}):
        f = _fold_mstr(_mstr_doc(**kw))
        assert f["ended"] is False and "nan" not in json.dumps(f).lower()


def test_NEGATIVE_card_trades_fails_closed():
    cl = _claim("LGX", PR, 12.40, 11.98)
    assert LG.card_trades(make_store(claims=[cl], ledger=[_ema9_ledger("LGX", PR)], fail_alerts=True), S) == {}
    assert LG.card_trades(make_store(claims=[cl], ledger=[_ema9_ledger("LGX", PR)], fail_ledger=True), S) == {}
    st = make_store(claims=[cl])
    st.alert_rows = lambda *_a, **_k: None
    assert LG.card_trades(st, S) == {}
    st = make_store(claims=[cl])
    st.ledger_docs = lambda *_a, **_k: None
    assert LG.card_trades(st, S) == {}
    assert LG.card_trades(make_store(), S) == {}                                 # no rows → nothing


def test_NEGATIVE_a_ledger_read_fault_folds_nothing_by_the_ledger():
    d = _doc("LGX", PR, "triggered", trigger=12.40, stop=11.98, criteria=WIN)
    cl = _claim("LGX", PR, 12.40, 11.98)
    out = build(PR, store=make_store([d], claims=[cl], ledger=[_ema9_ledger("LGX", PR)], fail_ledger=True),
                now=et(S, 17, 10))
    assert out["fault"] is False and "LGX" in {t["symbol"] for t in out["tiles"]} and out["ended"]["n"] == 0


# ── 18. the new templates ─────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_new_template_types_a_digit_outside_its_fields():
    fmt = string.Formatter()
    for name in NEW_TEMPLATES:
        tpl = getattr(T, name)
        literal = "".join(lit for lit, _f, _s, _c in fmt.parse(tpl))
        assert not re.search(r"\d", literal), (name, literal)


def test_NEGATIVE_no_b_word_and_no_edge_in_the_fold_words():
    words = [getattr(T, n) for n in NEW_TEMPLATES]
    out = build(ORH)
    words += list(_walk(out["ended"])) + [x for t in out["tiles"] for x in _walk({k: t[k] for k in T.FOLD_KEYS})]
    assert [w for w in words if BWORD.search(w) or EDGE.search(w)] == []


# ── 19. [C6] live_card imported only inside the ctx-given live-fold branch ───────────────────────────────────────
def _block_live_card(monkeypatch):
    monkeypatch.setitem(sys.modules, "chart_maps.live_card", None)
    monkeypatch.delattr(chart_maps, "live_card", raising=False)


def test_without_ctx_the_cards_never_import_live_card(monkeypatch):
    _block_live_card(monkeypatch)
    for setup in LC.SETUPS:
        tiles = T.tiles_for(_reads(), setup, caps={})
        assert all(t["live_fold"] is None for t in tiles)
        assert T.live_tiles(tiles) == [t for t in tiles if t["state"] != "stopped"]


def test_NEGATIVE_the_bite_build_with_a_trade_card_imports_live_card(monkeypatch):
    _block_live_card(monkeypatch)
    with pytest.raises(ImportError):
        build(PR)                                                                 # AAA aplus at 10:12 ET


def test_tab_has_no_module_level_live_card_import():
    tree = ast.parse(TAB_PATH.read_text(encoding="utf-8"))
    names = []
    for n in tree.body:
        if isinstance(n, ast.Import):
            names += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            names += [n.module or ""] + [a.name for a in n.names]
    assert not any("live_card" in x for x in names)
    src = inspect.getsource(T.fold_of)
    assert src.count("import live_card") == 1
    assert src.index("ctx.get(\"is_today\")") < src.index("import live_card")
    assert '"under_stop"' not in TAB_PATH.read_text(encoding="utf-8") and "VS_KINDS[1]" in src


# ── 20. HIS CALL #1 pinned OFF ────────────────────────────────────────────────────────────────────────────────────
def test_the_card_close_switch_is_off_his_call_1():
    """HIS CALL #1 (spec lukend §7): flipping CARD_CLOSE_EXIT_ON moves this pin, with his words quoted."""
    assert T.CARD_CLOSE_EXIT_ON is False
