"""🥇 Luk realtime cards — the served board words (SPEC lukrt §3.3 / §4 WP-B, 2026-11-12).

Ajay 2026-11-12, verbatim: "Luks scan is not realtime I see all dated values can you make it realtime".

luk.tab serves what luk.run's step 13b (the board re-read after the push gate — display only) wrote: the pass-line
tail "{read} of {board} board cards re-read" (only on a pass doc whose `refresh.on`), the cost clause (at most
LUK_REREAD_MAX) + the last pass's re-read COUNT (critique C6: a count, never a name list), the push tail (live mode
only), `pass.next_read_sec` (critique C3: falls back to the cadence once the next cron pass is overdue by more than one
cadence), per card `live_level` (aplus / triggered / forming / listed) and `not_rung_text` (critique C2: only a
`refresh_only` doc whose `not_rung` names that setup AND that reads aplus), and the 📓 / ℹ️ cadence line's tail.
NEGATIVES throughout: a doc without `refresh` keeps PASS_TEXT byte for byte; the switch off restores today's words.
"""
from __future__ import annotations

import re
import string
from datetime import datetime, timedelta, timezone

import pytest

from chart_maps import live_card as LCARD
from chart_maps.gajjala import store as GS
from chart_maps.gajjala import variant as V
from chart_maps.luk import constants as LC
from chart_maps.luk import playbook as PB
from chart_maps.luk import tab as T
from chart_maps.luk.variant import LUK
from tests.test_luk_tab import (BWORD, EDGE, NOW, PASS_AT, S, _pass_body, _read, _read_doc, fixture_store)

PR, ORH, IDP = LC.SETUPS
PASS_TEXT_LITERAL = ("pass {hhmm} ET · bars through {through} · {n_read} read of {shortlist} shortlisted · {screened} "
                     "screened · {not_screened} not screened yet")
PASS_LINE = PASS_TEXT_LITERAL.format(hhmm="10:11", through="10:10", n_read=4, shortlist=6, screened=1200,
                                     not_screened=37)
OD_AT = datetime(2026, 11, 3, 15, 11, 40, tzinfo=timezone.utc)          # 10:11:40 ET — after the 10:11:07 cron pass
NEW_TEMPLATES = ("PASS_REREAD_TAIL", "COST_REREAD_TEXT", "COST_REREAD_LAST_TEXT", "COST_MISSED_TEXT",
                 "PUSH_REREAD_TAIL", "NOT_RUNG_TEXT")


def _refresh(**kw):
    r = {"on": True, "board_n": 46, "board_read_n": 44, "asked": ["ZZQA", "YYQB"], "asked_n": 32, "read_n": 30,
         "not_read": ["ZZQA", "YYQB"], "bars": {"loaded": 30, "no_bars": 0, "failed": 0, "over_budget": 2},
         "aplus_not_rung": [], "budget_s": 80.0, "wall_s": 5.1, "skipped": None}
    r.update(kw)
    return r


def _store(refresh=None, *, on_demand=False):
    """The test_luk_tab fixture store; `refresh` (when given) rides the cron pass body — or an on-demand pass's."""
    st = fixture_store()
    if refresh is not None and not on_demand:
        st.record_pass(S, PASS_AT, dict(_pass_body(), refresh=refresh))
    if on_demand:
        body = dict(_pass_body(), on_demand=True)
        if refresh is not None:
            body["refresh"] = refresh
        st.record_pass(S, OD_AT, body, hhmm="10:11:40|on_demand", source=GS.LEASE_ON_DEMAND, latest_if_newer=True)
    return st


def _build(st=None, sub="", now=NOW):
    return T.build(sub, now=now, store=st if st is not None else fixture_store())


def _walk(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


# ── the constants this package reads ──────────────────────────────────────────────────────────────────────────────
def test_next_read_is_the_card_poll_period():
    assert LC.LUK_NEXT_READ_SEC == LCARD.CARD_LIVE_SEC


# ── the pass line ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_pass_that_re_read_serves_the_tail():
    p = _build(_store(_refresh()))["pass"]
    assert p["text"] == PASS_LINE + " · 44 of 46 board cards re-read"


def test_the_on_demand_pass_line_carries_the_tail_too():
    p = _build(_store(_refresh(board_n=12, board_read_n=12), on_demand=True))["pass"]
    assert p["text"].startswith("🔄 on-demand pass 10:11 ET") and p["text"].endswith(" · 12 of 12 board cards re-read")


@pytest.mark.parametrize("refresh", [None, _refresh(on=False, skipped="off (LUK_REREAD_SHOWN)"),
                                     _refresh(on=False, skipped="error"), "junk", _refresh(on="yes")])
def test_NEGATIVE_no_refresh_or_refresh_off_keeps_PASS_TEXT_byte_for_byte(refresh):
    st = fixture_store()
    if refresh is not None:
        st.record_pass(S, PASS_AT, dict(_pass_body(), refresh=refresh))
    p = _build(st)["pass"]
    assert T.PASS_TEXT == PASS_TEXT_LITERAL and p["text"] == PASS_LINE
    assert "re-read" not in p["text"]


# ── the cost line ──────────────────────────────────────────────────────────────────────────────────────────────────
def _cost_today():
    """The cost line exactly as 2026-11-11 served it for the fixture pass doc (base + "Last pass:" tail)."""
    base = T.COST_TEXT.format(cad=T._cad_min(), open=LC.LUK_PASS_OPEN_ET, close=LC.LUK_PASS_CLOSE_ET,
                              daily=LC.LUK_DAILY_MAX_NEW_PER_PASS, shortlist=LC.LUK_SHORTLIST_MAX,
                              hourly=LC.LUK_HOURLY_SESSIONS, grade=LC.LUK_GRADE_MAX_LOADS)
    return base + (" Last pass: snapshot 1 · daily 3 · minute today 6 · minute prior 12 · index 2 · caps 1.")


def test_the_cost_clause_names_the_most_cards_read_at_call_time(monkeypatch):
    c = _build()["strip"]["cost_text"]
    clause = T.COST_REREAD_TEXT.format(most=LC.LUK_REREAD_MAX)
    assert clause in c and f"(at most {LC.LUK_REREAD_MAX})" in c and "a re-read rings nothing" in c
    monkeypatch.setattr(LC, "LUK_REREAD_MAX", 61)
    assert "(at most 61)" in _build()["strip"]["cost_text"]


def test_the_last_pass_clause_counts_the_cards_not_re_read():
    c = _build(_store(_refresh()))["strip"]["cost_text"]
    assert c.endswith(" Re-read last pass: 30 of 32 — 2 not re-read (each says so on its card).")


def test_NEGATIVE_no_ticker_of_not_read_appears_in_the_cost_line():
    names = ["ZZQA", "YYQB", "XXQC"]
    c = _build(_store(_refresh(not_read=names, asked=names)))["strip"]["cost_text"]
    assert "3 not re-read" in c
    assert not any(n in c for n in names)


def test_NEGATIVE_an_empty_not_read_says_no_not_re_read():
    c = _build(_store(_refresh(not_read=[], read_n=32)))["strip"]["cost_text"]
    assert c.endswith(" Re-read last pass: 32 of 32.") and "not re-read" not in c


def test_NEGATIVE_a_pass_without_refresh_has_no_last_pass_re_read_clause():
    c = _build()["strip"]["cost_text"]
    assert "Re-read last pass" not in c
    assert c == _cost_today().replace(" Last pass:", T.COST_REREAD_TEXT.format(most=LC.LUK_REREAD_MAX) + " Last pass:")


def test_NEGATIVE_the_switch_off_serves_todays_cost_line(monkeypatch):
    monkeypatch.setattr(LC, "LUK_REREAD_SHOWN", False)
    assert _build()["strip"]["cost_text"] == _cost_today()
    assert _build(_store(_refresh()))["strip"]["cost_text"] == _cost_today()


# ── the push line ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_push_tail_rides_the_live_line():
    s = _build()["strip"]["push_text"]
    base = T.PUSH_TEXT_LIVE.format(since=LC.LUK_LIVE_SINCE, words=LC.LUK_LIVE_WORDS, cad=T._cad_min())
    assert s == base + T.PUSH_REREAD_TAIL and s.endswith("its A+ says so on the card.")


def test_NEGATIVE_the_shadow_line_has_no_push_tail(monkeypatch):
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "shadow")
    assert _build()["strip"]["push_text"] == T.PUSH_TEXT_SHADOW
    assert T.PUSH_REREAD_TAIL not in T.push_text()


def test_NEGATIVE_the_switch_off_has_no_push_tail(monkeypatch):
    monkeypatch.setattr(LC, "LUK_REREAD_SHOWN", False)
    assert T.push_text() == T.PUSH_TEXT_LIVE.format(since=LC.LUK_LIVE_SINCE, words=LC.LUK_LIVE_WORDS,
                                                    cad=T._cad_min())


# ── not_rung_text (critique C2) ────────────────────────────────────────────────────────────────────────────────────
def _aplus_doc(sym="RRQA", setup=PR, state="aplus", **kw):
    d = _read_doc(sym, {setup: _read(setup, state, frame="1m", trigger=12.4, stop=11.98, risk_pct=3.39, r_usd=0.42,
                                     entry_bar_t="2026-11-03 10:05")})
    d.update(kw)
    return d


def test_a_re_read_aplus_that_never_rang_says_so():
    t = T.tile_of(_aplus_doc(refresh_only=True, not_rung=[PR]), PR, caps={})
    assert t["not_rung_text"] == T.NOT_RUNG_TEXT


def test_the_pill_is_served_on_the_board_card():
    st = fixture_store()
    d = _aplus_doc(refresh_only=True, not_rung=[PR], cron_setups={})
    st.coll(_reads_coll()).docs[d["_id"]] = d
    tiles = _build(st, sub=PR)["tiles"]
    pill = {t["symbol"]: t["not_rung_text"] for t in tiles}
    assert pill["RRQA"] == T.NOT_RUNG_TEXT and pill["AAA"] is None


def _reads_coll():
    return GS.READS


@pytest.mark.parametrize("kw,setup,state", [
    ({}, PR, "aplus"),                                                      # a ring A+ (no refresh_only)
    ({"not_rung": [PR]}, PR, "aplus"),                                      # not_rung without refresh_only
    ({"refresh_only": True, "not_rung": []}, PR, "aplus"),                  # a re-read A+ that rang
    ({"refresh_only": True}, PR, "aplus"),                                  # no not_rung key (unknown / older doc)
    ({"refresh_only": True, "not_rung": [PR]}, PR, "triggered"),            # now reads triggered
    ({"refresh_only": True, "not_rung": [ORH]}, PR, "aplus"),               # names another setup
    ({"refresh_only": "true", "not_rung": [PR]}, PR, "aplus"),              # refresh_only not literally True
    ({"refresh_only": True, "not_rung": PR}, PR, "aplus"),                  # a string, never a substring match
])
def test_NEGATIVE_no_pill_unless_a_re_read_aplus_with_its_setup_in_not_rung(kw, setup, state):
    t = T.tile_of(_aplus_doc(setup=setup, state=state, **kw), setup, caps={})
    assert t["not_rung_text"] is None


# ── live_level ─────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("state", ["aplus", "triggered", "forming", "listed"])
def test_live_level_for_every_card_that_can_still_move(state):
    t = T.tile_of(_aplus_doc(state=state), PR, caps={})
    assert t["live_level"] == {"trigger": 12.4, "stop": 11.98, "tf": LUK.primary}


def test_live_level_with_one_level_only():
    d = _read_doc("OOQA", {PR: _read(PR, "forming", trigger=9.5)})
    assert T.tile_of(d, PR, caps={})["live_level"] == {"trigger": 9.5, "stop": None, "tf": LUK.primary}


def test_NEGATIVE_a_stopped_card_gets_no_live_level():
    assert T.tile_of(_aplus_doc(state="stopped"), PR, caps={})["live_level"] is None


@pytest.mark.parametrize("trig,stop", [(None, None), (float("nan"), None), ("x", float("inf"))])
def test_NEGATIVE_no_finite_level_no_live_level(trig, stop):
    d = _read_doc("NNQA", {PR: _read(PR, "forming", trigger=trig, stop=stop)})
    assert T.tile_of(d, PR, caps={})["live_level"] is None


def test_the_board_serves_live_levels_on_its_cards():
    tiles = _build(sub=ORH)["tiles"]
    by = {t["symbol"]: t["live_level"] for t in tiles}
    assert by["AAA"] == {"trigger": 12.6, "stop": 11.98, "tf": LUK.primary}            # forming
    assert by["CCC"] is None                                                             # stopped


# ── next_read_sec (critique C3) ───────────────────────────────────────────────────────────────────────────────────
CAD = V.cadence_sec(LUK)


def _cron(wall=10.0, at=PASS_AT, date_=None):
    return {"date": (date_ or S).isoformat(), "at": at, "wall_s": wall}


def _nr(since_sec: float, wall=10.0, in_window=True):
    return T.next_read_sec(_cron(wall), PASS_AT + timedelta(seconds=since_sec), S, in_window)


def test_next_read_due_in_200_s_is_230():
    assert _nr(CAD + 10 - 200) == 200 + LC.LUK_NEXT_READ_SEC == 230


def test_next_read_due_in_400_s_is_clamped_to_the_cadence():
    assert T.next_read_sec(_cron(wall=110.0), PASS_AT + timedelta(seconds=10), S, True) == CAD == 300


def test_next_read_overdue_by_50_s_retries_in_30():
    assert _nr(6 * 60) == LC.LUK_NEXT_READ_SEC == 30                      # 6 min since a pass with wall 10


@pytest.mark.parametrize("minutes", [30, 120])
def test_next_read_falls_back_to_the_cadence_once_passes_stopped(minutes):
    got = _nr(minutes * 60)
    assert got == CAD
    assert got != LC.LUK_NEXT_READ_SEC                                    # NEGATIVE: never 30 there


def test_next_read_is_always_within_its_bounds():
    for since in range(0, 3 * CAD, 7):
        for wall in (0.0, 8.4, 24.2, 119.0):
            got = _nr(since, wall=wall)
            assert LC.LUK_NEXT_READ_SEC <= got <= CAD, (since, wall, got)


def test_next_read_naive_utc_stamp_reads_as_utc():
    naive = PASS_AT.replace(tzinfo=None)
    assert T.next_read_sec(_cron(at=naive), PASS_AT + timedelta(seconds=CAD + 10 - 200), S, True) == 230


def test_next_read_on_the_board():
    p = _build()["pass"]
    assert p["next_read_sec"] == CAD                    # 10:12 ET, pass 10:11:07 + wall 41.2 → due in 288 s → clamped
    late = PASS_AT + timedelta(seconds=CAD + 41.2 + 50)
    assert _build(now=late)["pass"]["next_read_sec"] == LC.LUK_NEXT_READ_SEC


def test_NEGATIVE_next_read_outside_the_window_or_without_a_cron_pass_is_none():
    assert _nr(100, in_window=False) is None
    assert T.next_read_sec(None, NOW, S, True) is None
    assert T.next_read_sec(_cron(date_=S - timedelta(days=1)), NOW, S, True) is None
    assert T.next_read_sec({"date": S.isoformat(), "at": None}, NOW, S, True) is None
    closed = datetime(2026, 11, 3, 21, 30, tzinfo=timezone.utc)          # 16:30 ET — past LUK_PASS_CLOSE_ET
    assert _build(now=closed)["pass"]["next_read_sec"] is None
    assert _build(fixture_store(passes=False))["pass"]["next_read_sec"] is None


def test_NEGATIVE_an_on_demand_pass_alone_never_sets_the_next_read():
    st = fixture_store(passes=False)
    st.record_pass(S, OD_AT, dict(_pass_body(), on_demand=True), hhmm="10:11:40|on_demand",
                   source=GS.LEASE_ON_DEMAND, latest_if_newer=True)
    assert _build(st)["pass"]["next_read_sec"] is None


def test_next_read_reads_the_cron_pass_not_a_newer_on_demand_one():
    od = _build(_store(on_demand=True))["pass"]["next_read_sec"]
    assert od == _build()["pass"]["next_read_sec"]


# ── the 📓 / ℹ️ cadence line ──────────────────────────────────────────────────────────────────────────────────────
def _cadence_line():
    return next(ln for ln in PB.rules_lines() if ln.startswith("One pass every"))


def test_the_cadence_line_carries_the_re_read_clause():
    ln = _cadence_line()
    assert ln.endswith("hourly bars" + PB.REREAD_CLAUSE % LC.LUK_REREAD_MAX)
    assert f"(at most {LC.LUK_REREAD_MAX})" in ln and "a re-read rings nothing." in ln


def test_NEGATIVE_the_switch_off_restores_the_cadence_line(monkeypatch):
    monkeypatch.setattr(LC, "LUK_REREAD_SHOWN", False)
    ln = _cadence_line()
    assert ln.endswith("hourly bars.") and "re-read" not in ln


def test_the_cadence_line_number_moves_with_the_constant(monkeypatch):
    monkeypatch.setattr(LC, "LUK_REREAD_MAX", 57)
    assert "(at most 57)" in _cadence_line()


# ── words ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_new_templates_type_no_digit():
    fmt = string.Formatter()
    for name in NEW_TEMPLATES:
        literal = "".join(lit for lit, _f, _s, _c in fmt.parse(getattr(T, name)))
        assert not re.search(r"\d", literal), (name, literal)
    assert not re.search(r"\d", PB.REREAD_CLAUSE.replace("%d", ""))


def test_NEGATIVE_the_new_words_carry_no_b_word_and_no_edge():
    words = [getattr(T, n) for n in NEW_TEMPLATES] + [PB.REREAD_CLAUSE]
    st = _store(_refresh())
    d = _aplus_doc(refresh_only=True, not_rung=[PR])
    st.coll(_reads_coll()).docs[d["_id"]] = d
    words += list(_walk(_build(st, sub=PR)))
    assert [w for w in words if BWORD.search(w) or EDGE.search(w)] == []


def test_NEGATIVE_the_guard_catches_a_planted_word(monkeypatch):
    monkeypatch.setattr(T, "NOT_RUNG_TEXT", "A+ with an edge")
    t = T.tile_of(_aplus_doc(refresh_only=True, not_rung=[PR]), PR, caps={})
    assert EDGE.search(t["not_rung_text"])


def test_NEGATIVE_no_new_top_level_key():
    out = _build(_store(_refresh()))
    assert set(out) == set(T.PAYLOAD_KEYS)
