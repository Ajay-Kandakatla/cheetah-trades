"""🥇 Luk's tab — the served 🔄 `scan` block (SPEC lukscan §3.4 / WP-LUK-TAB, 2026-11-11).

Ajay 2026-11-11, verbatim: "Can you put an ondeman scan button for Luk' scans too".

`luk.tab.build` over the fixture LukStore of tests/test_luk_tab.py: the `scan` block is served on every sub and in
PAYLOAD_KEYS (the fault payload serves None); its words LS1–LS5 / LS2b / LS3 / LS9 for every state (closed, idle after a
cron pass, idle after an on-demand pass, scanning by the cron, scanning by an on-demand pass, another session, no pass);
the label is 🚩's RESCAN_LABEL; the title's numbers are constants names read at call time and its latency sentence is
`latency_text()` verbatim; an on-demand latest serves PASS_TEXT_ON_DEMAND. NEGATIVES: a cron latest keeps PASS_TEXT
byte for byte; `stale` still reads the cron pass; a raising lease read / scan block never takes the board down; owner
and non-owner payloads are identical; no forbidden word in any scan string; a lease claimed ≥ LUK_LEASE_SEC ago never
shows "scanning".
"""
from __future__ import annotations

import re
import string
from datetime import datetime, timedelta, timezone

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.luk import constants as LC
from chart_maps.luk import tab as T
from chart_maps.luk.variant import LUK
from tests.test_luk_tab import BWORD, EDGE, NOW, PASS_AT, S, _pass_body, fixture_store

OD_AT = datetime(2026, 11, 3, 15, 11, 40, tzinfo=timezone.utc)          # 10:11:40 ET — after the 10:11:07 cron pass
CLOSED_NOW = datetime(2026, 11, 3, 21, 30, tzinfo=timezone.utc)          # 16:30 ET — past LUK_PASS_CLOSE_ET
NEXT_DAY = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)             # 10:00 ET the next market day
NOTHING = re.compile(r"nothing (rings|reaches|is sent)", re.I)           # contracts.mjs NOTHING (A13)
SCAN_KEYS = {"state", "on_demand", "started_at_et", "bars_through_et", "as_of_text", "scanning_text", "text", "note",
             "rescan_label", "rescan_title"}
PASS_TEXT_LITERAL = ("pass {hhmm} ET · bars through {through} · {n_read} read of {shortlist} shortlisted · {screened} "
                     "screened · {not_screened} not screened yet")


def _cad():
    return V.cadence_sec(LUK) // 60


def _od_store(*, cron=True, body=None):
    st = fixture_store(passes=cron)
    st.record_pass(S, OD_AT, dict(body if body is not None else _pass_body(), on_demand=True),
                   hhmm="10:11:40|on_demand", source=GS.LEASE_ON_DEMAND, latest_if_newer=True)
    return st


def _lease(st, **doc):
    st.coll(GS.STATE).docs[GS.LEASE_ID] = dict(doc, _id=GS.LEASE_ID)
    return st


def _cron_held(st, ago=30):
    at = NOW - timedelta(seconds=ago)
    return _lease(st, status="running", held_by=GS.LEASE_CRON, claimed_at=at, started_at=at,
                  last_cron_started_at=at)


def _od_held(st, ago=20):
    at = NOW - timedelta(seconds=ago)
    return _lease(st, status="running", held_by=GS.LEASE_ON_DEMAND, claimed_at=at, od_started_at=at)


def _scan(st=None, now=NOW, sub=""):
    return T.build(sub, now=now, store=st if st is not None else fixture_store())["scan"]


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)


def _all_scans():
    return [_scan(), _scan(_od_store()), _scan(_cron_held(fixture_store())), _scan(_od_held(_od_store())),
            _scan(now=CLOSED_NOW), _scan(fixture_store(passes=False), now=CLOSED_NOW), _scan(now=NEXT_DAY),
            _scan(fixture_store(passes=False)), _scan(_cron_held(fixture_store(passes=False)))]


# ── served everywhere ──────────────────────────────────────────────────────────────────────────────────────────────
def test_scan_is_a_payload_key_and_the_fault_payload_serves_none():
    assert "scan" in T.PAYLOAD_KEYS
    out = T.build("", now=NOW, store=fixture_store())
    assert set(out) == set(T.PAYLOAD_KEYS) and set(out["scan"]) == SCAN_KEYS
    f = T.fault_payload()
    assert set(f) == set(T.PAYLOAD_KEYS) and f["scan"] is None


@pytest.mark.parametrize("sub", list(T.SUB_KEYS))
def test_scan_is_served_on_every_sub(sub):
    assert len(T.SUB_KEYS) == 8
    st = fixture_store()
    sc = T.build(sub, now=NOW, store=st)["scan"]
    assert isinstance(sc, dict) and set(sc) == SCAN_KEYS
    assert sc == T.build("", now=NOW, store=st)["scan"]                       # one line, whatever the sub


def test_the_label_is_the_house_rescan_label():
    for sc in _all_scans():
        assert sc["rescan_label"] == GT.RESCAN_LABEL == "🔄 scan now"


# ── words, state by state ──────────────────────────────────────────────────────────────────────────────────────────
def test_idle_after_a_cron_pass_LS2():
    sc = _scan()
    assert sc["state"] == "idle" and sc["on_demand"] is False
    assert sc["as_of_text"] == sc["text"] == "last pass 10:11 ET · bars through 10:10"
    assert sc["bars_through_et"] == "10:10" and sc["started_at_et"] == "10:11"
    assert sc["scanning_text"] is None and sc["note"] is None


def test_idle_after_an_on_demand_pass_LS1():
    sc = _scan(_od_store())
    assert sc["state"] == "idle" and sc["on_demand"] is True
    assert sc["as_of_text"] == sc["text"] == "🔄 scanned on demand 10:11 ET · bars through 10:10"


def test_an_on_demand_pass_with_no_bars_through_drops_the_tail():
    body = _pass_body()
    body.pop("bars_through")
    sc = _scan(_od_store(body=body))
    assert sc["as_of_text"] == "🔄 scanned on demand 10:11 ET" and sc["bars_through_et"] is None


def test_scanning_by_the_cron_LS5():
    sc = _scan(_cron_held(fixture_store()))
    want = (f"scanning… the {_cad()}-minute 🥇 pass started at 10:11:30 ET — the board below is the 10:11 ET read "
            "until it lands")
    assert sc["state"] == "scanning" and sc["scanning_text"] == sc["text"] == want
    assert sc["started_at_et"] == "10:11:30"
    assert sc["as_of_text"] == "last pass 10:11 ET · bars through 10:10"


def test_scanning_by_an_on_demand_pass_LS4():
    sc = _scan(_od_held(fixture_store()))
    assert sc["state"] == "scanning"
    assert sc["text"] == sc["scanning_text"] == ("scanning… an on-demand pass started at 10:11:40 ET — the board below "
                                                 "is the 10:11 ET read until it lands")


def test_scanning_with_no_pass_on_file_says_the_board_fills():
    sc = _scan(_cron_held(fixture_store(passes=False)))
    assert sc["text"] == f"scanning… the {_cad()}-minute 🥇 pass started at 10:11:30 ET — the board fills when it lands"
    assert sc["as_of_text"] == "no pass on file yet"


def test_closed_LS3():
    sc = _scan(now=CLOSED_NOW)
    assert sc["state"] == "closed" and sc["scanning_text"] is None
    assert sc["text"] == sc["as_of_text"] == "outside 🥇 Luk's pass window — last pass 10:11 ET 2026-11-03"
    sc = _scan(fixture_store(passes=False), now=CLOSED_NOW)
    assert sc["state"] == "closed" and sc["text"] == "outside 🥇 Luk's pass window — no pass on file"


def test_NEGATIVE_closed_never_says_scanning_even_with_the_lease_held():
    sc = _scan(_lease(fixture_store(), status="running", held_by=GS.LEASE_CRON,
                      claimed_at=CLOSED_NOW - timedelta(seconds=10)), now=CLOSED_NOW)
    assert sc["state"] == "closed" and sc["scanning_text"] is None


def test_another_session_and_no_pass_LS2b():
    sc = _scan(now=NEXT_DAY)
    assert sc["state"] == "idle"
    assert sc["text"] == "last pass 2026-11-03 10:11 ET — none yet this session"
    assert sc["bars_through_et"] is None                                     # NEGATIVE: never yesterday's bars
    assert sc["started_at_et"] == "2026-11-03 10:11"
    sc = _scan(fixture_store(passes=False))
    assert sc["text"] == "no pass on file yet" and sc["started_at_et"] is None and sc["on_demand"] is False


# ── the title ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_rescan_title_LS9_verbatim():
    cad = _cad()
    want = (f"Run one 🥇 pass now — its push gate runs dry, so it rings no device; the {cad}-minute pass rings as always: "
            f"{T.latency_text()}. A pass that finished under {GC.ON_DEMAND_REUSE_SEC} s ago is reused; a scan starts "
            f"only after this slot's {cad}-minute pass landed (or skipped itself) and when it can end "
            f"{LC.LUK_SLOT_MARGIN_SEC} s before the next one")
    assert _scan()["rescan_title"] == want == T.rescan_title()
    assert T.latency_text() in want


def test_rescan_title_follows_the_constants(monkeypatch):
    monkeypatch.setattr(GC, "ON_DEMAND_REUSE_SEC", 77)
    monkeypatch.setattr(LC, "LUK_SLOT_MARGIN_SEC", 33)
    monkeypatch.setattr(GC, "PASS_CADENCE_SEC", 600)
    t = _scan()["rescan_title"]
    assert "under 77 s ago" in t and "end 33 s before" in t and "the 10-minute pass rings" in t
    assert "60 s" not in t and "20 s" not in t and "5-minute" not in t


def test_rescan_title_splices_the_latency_sentence(monkeypatch):
    monkeypatch.setattr(T, "LATENCY_TEXT", "LATENCY {one}/{cad}")
    t = _scan()["rescan_title"]
    assert f"always: LATENCY 1/{_cad()}. A pass" in t


def test_NEGATIVE_no_scan_template_types_a_digit():
    fmt = string.Formatter()
    for name in ("RESCAN_TITLE", "SCAN_AS_OF_CLOSED", "SCAN_AS_OF_CLOSED_NONE", "SCAN_AS_OF_ON_DEMAND",
                 "SCAN_AS_OF_CRON", "SCAN_AS_OF_OTHER", "SCAN_AS_OF_NONE", "SCAN_BARS_TAIL", "SCAN_SCANNING_ON_DEMAND",
                 "SCAN_SCANNING_CRON", "SCAN_WHEN", "SCAN_TAIL", "SCAN_TAIL_NONE", "PASS_TEXT_ON_DEMAND"):
        literal = "".join(lit for lit, _f, _s, _c in fmt.parse(getattr(T, name)))
        assert not re.search(r"\d", literal), (name, literal)


# ── the pass line ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_an_on_demand_latest_serves_PASS_TEXT_ON_DEMAND():
    p = T.build("", now=NOW, store=_od_store())["pass"]
    assert p["text"] == ("🔄 on-demand pass 10:11 ET · bars through 10:10 · 4 read of 6 shortlisted · 1200 screened · "
                         "37 not screened yet")
    assert p["on_demand"] is True


def test_NEGATIVE_a_cron_latest_keeps_PASS_TEXT_byte_for_byte():
    assert T.PASS_TEXT == PASS_TEXT_LITERAL
    p = T.build("", now=NOW, store=fixture_store())["pass"]
    assert p["text"] == PASS_TEXT_LITERAL.format(hhmm="10:11", through="10:10", n_read=4, shortlist=6, screened=1200,
                                                 not_screened=37)
    assert "on-demand" not in p["text"] and "🔄" not in p["text"]


def test_NEGATIVE_stale_still_reads_the_cron_pass():
    """An on-demand pass alone never clears `stale` (GT._pass_block A10): no cron pass this session → stale; an old
    cron pass + a fresh on-demand pass → still stale."""
    p = T.build("", now=NOW, store=_od_store(cron=False))["pass"]
    assert p["stale"] is True and p["on_demand"] is True
    late = PASS_AT + timedelta(seconds=V.stale_after_sec(LUK) + 120)
    st = fixture_store()
    st.record_pass(S, late - timedelta(seconds=30), dict(_pass_body(), on_demand=True), hhmm="x|on_demand",
                   source=GS.LEASE_ON_DEMAND, latest_if_newer=True)
    p = T.build("", now=late, store=st)["pass"]
    assert p["on_demand"] is True and p["stale"] is True
    assert T.build("", now=NOW, store=fixture_store())["pass"]["stale"] is False      # the cron pass fresh → not stale


# ── NEGATIVES: faults, owner, words, a stale lease ─────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_raising_lease_read_never_takes_the_board_down(monkeypatch):
    st = fixture_store()
    monkeypatch.setattr(st, "lease_state", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("mongo down")))
    out = T.build("", now=NOW, store=st)
    assert out["fault"] is False and out["scan"]["state"] == "idle"
    assert out["scan"]["text"] == "last pass 10:11 ET · bars through 10:10"


def test_NEGATIVE_a_raising_scan_block_serves_none_never_500(monkeypatch):
    monkeypatch.setattr(T, "scan_block", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = T.build("", now=NOW, store=fixture_store())
    assert out["fault"] is False and out["scan"] is None and out["tiles"]


def test_NEGATIVE_owner_and_non_owner_payloads_are_identical():
    for st in (fixture_store(), _od_held(_od_store())):
        for sub in ("", "premarket", T.TRACK_SUB):
            assert T.build(sub, now=NOW, store=st, owner=True) == T.build(sub, now=NOW, store=st, owner=False)


def test_NEGATIVE_no_forbidden_word_in_any_scan_string():
    texts = [t for sc in _all_scans() for t in _strings(sc)]
    assert texts
    for t in texts:
        low = t.lower()
        assert "on open" not in low and "enterable" not in low and "fresh bar" not in low, t
        assert "every fresh a+" not in low, t
        assert not BWORD.search(t) and not EDGE.search(t) and not NOTHING.search(t), t


def test_NEGATIVE_a_lease_claimed_LUK_LEASE_SEC_ago_never_shows_scanning():
    st = _cron_held(fixture_store(), ago=LC.LUK_LEASE_SEC)
    sc = _scan(st)
    assert sc["state"] == "idle" and sc["scanning_text"] is None
    assert _scan(_cron_held(fixture_store(), ago=LC.LUK_LEASE_SEC - 1))["state"] == "scanning"
    assert _scan(_od_held(fixture_store(), ago=LC.LUK_LEASE_SEC + 60))["state"] == "idle"


def test_NEGATIVE_the_stale_lease_rule_reads_luks_own_lease_number(monkeypatch):
    monkeypatch.setattr(LC, "LUK_LEASE_SEC", 10)
    assert _scan(_cron_held(fixture_store(), ago=30))["state"] == "idle"


def test_NEGATIVE_a_released_lease_is_idle():
    st = _lease(fixture_store(), status="done", held_by=GS.LEASE_CRON, claimed_at=NOW - timedelta(seconds=5),
                done_at=NOW - timedelta(seconds=5))
    assert _scan(st)["state"] == "idle"


def test_scan_block_reads_its_arguments_only():
    """Called directly (no store): junk lease / latest never raise."""
    sc = T.scan_block(None, None, NOW, S, True)
    assert sc["state"] == "idle" and sc["text"] == "no pass on file yet"
    sc = T.scan_block("junk", "junk", NOW, S, False)
    assert sc["state"] == "closed" and sc["text"] == "outside 🥇 Luk's pass window — no pass on file"
