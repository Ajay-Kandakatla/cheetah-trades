"""👀 Gajjala's Watch step 0 (2026-11-15) — constants.py names its numbers by import; colls.py reads the owner list
fenced, the env switch at call time, and `loop_reads_soon` is the ONE window definition (spec §3.1 / §3.2)."""
from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import colls as WCO
from chart_maps.gajjala_watch import constants as C

ET = ZoneInfo("America/New_York")


class _Coll:
    def __init__(self, doc=None, raises=False):
        self.doc, self.raises, self.calls = doc, raises, []

    def find_one(self, q, *a, **k):
        self.calls.append(q)
        if self.raises:
            raise RuntimeError("mongo down")
        return self.doc


class _DB:
    def __init__(self, list_coll=None, raises=False):
        self.list_coll, self.raises, self.names = list_coll or _Coll(), raises, []

    def __getitem__(self, name):
        if self.raises:
            raise RuntimeError("no db")
        self.names.append(name)
        return self.list_coll if name == C.COLL_LIST else _Coll()


# ── constants ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_push_numbers_are_imported_not_retyped():
    assert C.PUSH_MODES is GC.FADE_CROSS_PUSH_MODES
    assert C.PUSH_KIND is GC.FADE_CROSS_PUSH_KIND
    assert C.PUSH_MODE in C.PUSH_MODES
    assert C.LATCH in C.LATCHES and C.UPTREND_FILTER in C.UPTREND_FILTERS


def test_frames_and_caps():
    assert [tf for tf, _ in C.FRAMES] == ["1m", "3m", "5m"]
    assert set(C.FRAME_WORDS) == {tf for tf, _ in C.FRAMES}
    assert C.AXIS_FRAME == C.FRAMES[0][0]
    assert set(C.PUSH_FRAMES) <= set(C.FRAME_WORDS)
    assert C.MAX_SYMBOLS >= 9
    from daytrading import signal_lab
    # RE-PINNED 2026-11-18 — his answer "18 (Recommended)" after "All the watch button are not working": GG's own 18, no
    # longer signal_lab's 12. NEGATIVE: the ⚡ Signals list keeps its own 12 — the two caps are independent now.
    assert C.MAX_SYMBOLS == GC.GG_WATCH_N == 18
    assert signal_lab.MAX_SYMBOLS == 12 and C.MAX_SYMBOLS != signal_lab.MAX_SYMBOLS


def test_ids_and_argv():
    assert C.API_SYMBOL_PATH == C.API_PATH + "/symbols/{symbol}"
    assert not C.CLAIM_PREFIX.startswith("GG:")
    assert len({C.COLL_LIST, C.COLL_TILES, C.COLL_ALERTS, C.COLL_STATE}) == 4
    assert C.ARGV_LOOP[0] == sys.executable and C.ARGV_LOOP[1:] == ("-m", "chart_maps.gajjala_watch.loop", "--loop")
    assert C.ARGV_BUILD[1:] == ("-m", "chart_maps.gajjala_watch.loop", "--build")
    assert C.ARGV_LOOP != C.ARGV_BUILD


# ── colls / owner_symbols ──────────────────────────────────────────────────────────────────────────────────────────
def test_colls_keys_and_none_without_db(monkeypatch):
    c = WCO.colls(_DB())
    assert set(c) == {"list", "tiles", "alerts", "state"}
    monkeypatch.setattr(WCO, "_db", lambda: None)
    assert WCO.colls() is None
    assert WCO.colls(_DB(raises=True)) is None


def test_owner_symbols_strings_only_dedup_in_order():
    lc = _Coll({"_id": C.LIST_DOC_ID, "symbols": ["OMH", "NVDA", 5, None, "", "OMH", "AMD", {"x": 1}, "NVDA"]})
    assert WCO.owner_symbols(_DB(lc)) == ["OMH", "NVDA", "AMD"]
    assert lc.calls == [{"_id": C.LIST_DOC_ID}]


@pytest.mark.parametrize("doc", [None, {}, {"symbols": None}, {"symbols": "OMH"}, {"symbols": 7}, "junk"])
def test_owner_symbols_bad_doc_is_empty(doc):
    assert WCO.owner_symbols(_DB(_Coll(doc))) == []


def test_owner_symbols_never_raises(monkeypatch):
    assert WCO.owner_symbols(_DB(_Coll(raises=True))) == []
    assert WCO.owner_symbols(_DB(raises=True)) == []
    monkeypatch.setattr(WCO, "_db", lambda: None)
    assert WCO.owner_symbols() == []


# ── enabled / loop_reads_soon ──────────────────────────────────────────────────────────────────────────────────────
def test_enabled_reads_env_at_call_time(monkeypatch):
    monkeypatch.delenv(C.ENV_ENABLED, raising=False)
    assert WCO.enabled() is True
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    assert WCO.enabled() is False
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    assert WCO.enabled() is True
    monkeypatch.setattr(C, "ENABLED", False)
    assert WCO.enabled() is False


def test_loop_reads_soon_in_window(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    assert WCO.loop_reads_soon(datetime(2026, 11, 13, 10, 0, 10, tzinfo=ET)) is True
    assert WCO.loop_reads_soon(datetime(2026, 11, 13, 19, 58, 0, tzinfo=ET)) is True


@pytest.mark.parametrize("now", [
    datetime(2026, 11, 15, 12, 0, tzinfo=ET),     # Sunday
    datetime(2026, 11, 13, 3, 50, tzinfo=ET),     # before 04:00
    datetime(2026, 11, 13, 20, 4, 30, tzinfo=ET), # in the pass window, but the next read is past the extended close
    datetime(2026, 11, 13, 20, 30, tzinfo=ET),    # after the pass window
    datetime(2026, 11, 27, 17, 2, tzinfo=ET),     # half day: past the 17:00 extended close
])
def test_loop_reads_soon_negatives(monkeypatch, now):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    assert WCO.loop_reads_soon(now) is False


def test_loop_reads_soon_off_when_disabled(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    assert WCO.loop_reads_soon(datetime(2026, 11, 13, 10, 0, 10, tzinfo=ET)) is False
