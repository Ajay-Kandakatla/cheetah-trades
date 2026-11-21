"""🔢 the float on EVERY 👀 Gajjala's Watch row (spec watchfloat §3.2-§3.4 / §4 WP be-float, 2026-11-21).

Ajay 2026-11-21, verbatim: "can you add the current float value also to the tickers on the watch list."

`gajjala_watch/float_read.py` serves `row["float"]`: the carded name's 🏷️ chip (pass) → the 7-day `shares_cache` row
through the ONE engine on the store's long-lived handle (cache) → the 🚩 pass's daily memo (memo) → None. Display only.
UNMEASURED, not a signal.

NEGATIVES: no network (traps on every fetch / Massive / Yahoo path, the REAL engine on an expired row), zero new
clients (`_shares_coll` never touched, every lookup carries the injected handle), read counts (ONE daily find of the
misses only, ZERO when every name hit the cache, nothing at all for []), faults (memo fault keeps cache + pass chips;
a raising lookup / no handle / a raising or missing module → None everywhere, the board answers), NaN, suspect words,
the stale boundary, static source checks, the row key set.
"""
from __future__ import annotations

import json
import logging
import math
import re
import sys
import time
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import float_read as FR
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import tags as TG
from sepa import volume_movers as VM
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN, SESSION, _db, _doc, _strict
from tests.test_gajjala_watch_tags_2026_11_18 import Rec, _broker_doc, _pot, _r, _read, _scan

FRI = date(2026, 11, 13)
UTC = timezone.utc
SRC = Path(FR.__file__)
PROBE = Path(__file__).resolve().parents[1] / "scripts" / "watch_float_probe.py"
B_WORD = re.compile("b" + "ounc", re.I)
# 2026-11-12 09:06 UTC = 04:06 ET the day before the board's FRI_IN (10:30 ET)
AS_OF_TS = datetime(2026, 11, 12, 9, 6, tzinfo=UTC).timestamp()
VALS = {"shares_outstanding": 8_100_000, "float_shares": 1_800_000, "market_cap": 9_000_000, "as_of": AS_OF_TS}
MEMO_FLOAT = {"shares": 2_500_000, "src": "float", "as_of": "2026-11-13T13:05:00+00:00"}
MASSIVE_AT = "2026-11-13T14:01:00+00:00"


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build",
                        types.SimpleNamespace(uptrend_rule=lambda: "STUB-UPTREND-RULE"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "STUB-PUSH-TEXT"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.auto",
                        types.SimpleNamespace(read_doc=lambda cs: {}, rules_line=lambda: "STUB-AUTO",
                                              dismiss=lambda symbol, by=None: {"state": "absent"}))


@pytest.fixture(autouse=True)
def traps(monkeypatch):
    """Every network / new-client path raises on touch; the list must end empty."""
    hits = []

    def trap(name):
        def _t(*a, **k):
            hits.append(name)
            raise AssertionError(f"{name} must never run at serve time")
        return _t
    import short_interest.client as SIC
    for mod, name in ((VM, "_shares_coll"), (VM, "_fetch_shares_status"), (VM, "_fetch_shares_yf"),
                      (CX, "_default_massive_lookup"), (CX, "_massive_once"), (CX, "floats_for"),
                      (SIC, "_shares_outstanding")):
        monkeypatch.setattr(mod, name, trap(name))
    return hits


class Lookup:
    """The engine stand-in: records every call; raises unless the call is cache-only on an injected handle."""

    def __init__(self, table=None, fail=False):
        self.table = dict(table or {})
        self.calls = []
        self.fail = fail

    def __call__(self, sym, **kw):
        self.calls.append((sym, kw))
        if kw.get("fetch") is not False:
            raise AssertionError("a fetch at serve time")
        if kw.get("coll") is None:
            raise AssertionError("a None handle opens a new client")
        if self.fail:
            raise RuntimeError("cache down")
        return self.table.get(sym, (None, "missing"))

    def syms(self):
        return [s for s, _ in self.calls]


class CountStore(ST.GajjalaStore):
    def __init__(self, colls=None):
        super().__init__(colls)
        self.coll_calls = []

    def coll(self, name):
        self.coll_calls.append(name)
        return super().coll(name)


def _daily(sym, **fields):
    return dict({"_id": ST.key(SESSION, sym), "date": SESSION, "symbol": sym}, **fields)


def _world(daily=(), shares=None, *, daily_fail=False, no_daily=False, no_shares=False, reads=(), **kw):
    d = Rec(list(daily), fail=daily_fail)
    sh = shares if shares is not None else FakeColl()
    colls = {ST.READS: Rec(list(reads)), ST.POTENTIALS: Rec(list(kw.get("pots", ()))), ST.ALERTS: Rec(),
             ST.SCAN: Rec(list(kw.get("scan", ()))), ST.STATE: Rec(list(kw.get("state", ())))}
    colls[ST.DAILY] = None if no_daily else d
    colls[VM.SHARES_COLL] = None if no_shares else sh
    return CountStore(colls), d, sh


def _wire(monkeypatch, st, lookup=None):
    monkeypatch.setattr(FR, "_store", lambda: st)
    monkeypatch.setattr(TG, "_store", lambda: st)
    if lookup is not None:
        monkeypatch.setattr(FR, "_status_lookup", lambda: lookup)


def _rows(db=None, only=None, now=FRI_IN):
    out = PL.build(now, db=db or _db(["OMH", "NVDA"]), only=only)
    assert out["state"] == "ok"
    return {r["symbol"]: r for r in out["rows"]}, out


def _sec(names, lookup, st, tags_by=None, now=FRI_IN, monkeypatch=None):
    return FR.blocks(names, FRI, now, tags_by, st=st, lookup=lookup)


def _msgs(caplog, needle):
    return [r for r in caplog.records if needle in r.getMessage()]


# ── 1. a cache hit ───────────────────────────────────────────────────────────────────────────────────────────────
def test_cache_hit_serves_the_engines_chip_with_a_not_realtime_title(traps):
    st, daily, sh = _world()
    lk = Lookup({"OMH": (dict(VALS), "cached")})
    out = _sec(["OMH"], lk, st)
    f = out["OMH"]
    fr = CX._yf_read(dict(VALS), "cached", FRI_IN)
    assert f["text"] == tab._float_chip(fr)["text"] and f["read_from"] == "cache"
    assert set(f) == set(FR.FLOAT_KEYS) and len(FR.FLOAT_KEYS) == len(set(FR.FLOAT_KEYS))
    assert isinstance(f["shares"], float) and f["shares"] == 1_800_000.0           # C8 — the _f float, no coercion
    want = FR.FLOAT_TITLE_TEXT.format(text=f["text"], source=FR.FLOAT_SOURCE_WORDS["float"].format(days=7),
                                      as_of="2026-11-12 04:06 ET")
    assert f["title"] == want
    assert "not realtime" in f["title"] and "kept up to 7 days" in f["title"] and "04:06 ET" in f["title"]
    assert f["suspect"] is False and f["suspect_text"] is None
    assert daily.finds == [] and traps == []                                        # NEGATIVE: no memo read on a hit
    assert lk.calls == [("OMH", {"fetch": False, "coll": sh})]


# ── 2. stale words [C6] ──────────────────────────────────────────────────────────────────────────────────────────
def test_stale_served_keeps_the_stale_text_and_says_older_than():
    old = datetime(2026, 11, 3, 15, 0, tzinfo=UTC).timestamp()
    st, _d, _s = _world()
    f = _sec(["OMH"], Lookup({"OMH": (dict(VALS, as_of=old), "stale_served")}), st)["OMH"]
    assert "(stale, as of" in f["text"]
    assert FR.FLOAT_STALE_SOURCE_WORDS["float"].format(days=7) in f["title"] and "older than 7 days" in f["title"]
    assert "kept up to" not in f["title"]                                             # NEGATIVE


def test_a_pass_chip_older_than_the_ttl_gets_stale_words_too():
    st, _d, _s = _world()
    chip = tab._float_chip({"shares": 3_000_000, "src": "float", "as_of": "2026-11-01T15:00:00+00:00"})
    lk = Lookup()
    f = _sec(["OMH"], lk, st, {"OMH": {"float": chip}})["OMH"]
    assert f["read_from"] == "pass" and "older than 7 days" in f["title"] and "kept up to" not in f["title"]
    assert lk.calls == []                                                             # NEGATIVE: a pass chip reads nothing


def test_the_stale_boundary_is_the_engines_fresh_rule_exactly():
    ttl = timedelta(seconds=VM._SHARES_TTL_SEC)
    fresh = {"shares": 1e6, "src": "float", "text": "Float 1M", "as_of": (FRI_IN - ttl + timedelta(seconds=1)).isoformat()}
    edge = dict(fresh, as_of=(FRI_IN - ttl).isoformat())
    assert FR.is_stale(fresh, FRI_IN) is False and "kept up to 7 days" in FR.title(fresh, FRI_IN)
    assert FR.is_stale(edge, FRI_IN) is True and "older than 7 days" in FR.title(edge, FRI_IN)
    yf = dict(edge, src="shares_out_yf")
    assert FR.is_stale(yf, FRI_IN) is True


def test_NEGATIVE_a_massive_memo_chip_is_never_stale_worded():
    old_at = "2026-10-01T14:00:00+00:00"
    st, _d, _s = _world(daily=[_daily("OMH", float_massive={"shares": 9_000_000, "at": old_at})])
    f = _sec(["OMH"], Lookup(), st)["OMH"]
    assert f["src"] == "shares_out_massive" and f["read_from"] == "memo"
    assert FR.is_stale(f, FRI_IN) is False
    assert "older than" not in f["title"] and FR.FLOAT_SOURCE_WORDS["shares_out_massive"] in f["title"]


# ── 3. cache miss → memo ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("status", ["missing", "stale", "tombstone", "rl_marker"])
def test_a_cache_miss_falls_to_the_memo_float(status):
    st, _d, _s = _world(daily=[_daily("OMH", float=dict(MEMO_FLOAT))])
    f = _sec(["OMH"], Lookup({"OMH": (None, status)}), st)["OMH"]
    want = tab._float_chip({"shares": MEMO_FLOAT["shares"], "src": "float", "as_of": MEMO_FLOAT["as_of"],
                            "suspect": None})
    assert f["read_from"] == "memo" and f["text"] == want["text"] and f["as_of"] == MEMO_FLOAT["as_of"]
    assert "kept up to 7 days" in f["title"]


@pytest.mark.parametrize("status", ["missing", "stale", "tombstone", "rl_marker"])
def test_a_cache_miss_falls_to_the_massive_memo_dated_when_asked(status):
    st, _d, _s = _world(daily=[_daily("OMH", float_massive={"shares": 9_000_000, "at": MASSIVE_AT})])
    f = _sec(["OMH"], Lookup({"OMH": (None, status)}), st)["OMH"]
    assert "(Massive)" in f["text"] and f["as_of"] == MASSIVE_AT                     # never serve time
    assert f["title"].endswith("read 09:01 ET")


@pytest.mark.parametrize("bad", [0, 0.0, -5, float("nan")])
def test_NEGATIVE_a_zero_or_negative_memo_float_is_nothing_on_file_never_Float_0(bad):
    """The verifier's surviving mutation (2026-11-21): `shares > 0` loosened to `is not None` would print "Float 0"."""
    st, _d, _s = _world(daily=[_daily("OMH", float={"shares": bad, "src": "float", "as_of": MEMO_FLOAT["as_of"]})])
    assert _sec(["OMH"], Lookup(), st) == {}


def test_NEGATIVE_a_failed_massive_memo_serves_nothing():
    st, _d, _s = _world(daily=[_daily("OMH", float_massive={"failed_at": 1.0})])
    assert _sec(["OMH"], Lookup(), st) == {}


def test_a_massive_none_memo_is_float_unknown_with_no_title():
    st, _d, _s = _world(daily=[_daily("OMH", float_massive={"shares": None, "at": MASSIVE_AT})])
    f = _sec(["OMH"], Lookup(), st)["OMH"]
    assert f["text"] == "float unknown" == CX.unknown_float(FRI_IN)["text"]
    assert f["shares"] is None and f["title"] is None and f["read_from"] == "memo"


def test_the_memo_float_wins_over_the_massive_memo():
    st, _d, _s = _world(daily=[_daily("OMH", float=dict(MEMO_FLOAT),
                                      float_massive={"shares": 9_000_000, "at": MASSIVE_AT})])
    f = _sec(["OMH"], Lookup(), st)["OMH"]
    assert f["src"] == "float" and "(Massive)" not in f["text"]


# ── 4. nothing on file ───────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_cache_and_no_memo_serves_no_key_and_the_row_serves_none(monkeypatch):
    st, _d, _s = _world()
    assert _sec(["OMH"], Lookup(), st) == {}
    _wire(monkeypatch, st, Lookup())
    rows, _ = _rows()
    assert "float" in rows["OMH"] and rows["OMH"]["float"] is None and rows["NVDA"]["float"] is None


def test_a_build_serves_the_cache_float_on_an_uncarded_row(monkeypatch):
    st, _d, _s = _world()
    _wire(monkeypatch, st, Lookup({"OMH": (dict(VALS), "cached")}))
    rows, _ = _rows()
    assert rows["OMH"]["tags"] is None and rows["OMH"]["float"]["read_from"] == "cache"
    assert rows["NVDA"]["float"] is None


# ── 5. no network, no new client ─────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_network_path_is_ever_touched(monkeypatch, traps):
    st, _d, sh = _world(daily=[_daily("NVDA", float_massive={"shares": 9_000_000, "at": MASSIVE_AT})])
    lk = Lookup({"OMH": (dict(VALS), "cached")})
    _wire(monkeypatch, st, lk)
    rows, _ = _rows()
    assert rows["OMH"]["float"]["read_from"] == "cache" and rows["NVDA"]["float"]["read_from"] == "memo"
    assert traps == []
    assert all(kw == {"fetch": False, "coll": sh} for _s, kw in lk.calls)


def test_NEGATIVE_the_real_engine_on_an_expired_row_never_fetches(monkeypatch, traps):
    expired = {"_id": "OMH", **{k: v for k, v in VALS.items() if k != "as_of"},
               "as_of": int(time.time()) - VM._SHARES_TTL_SEC - 60}
    st, _d, sh = _world(daily=[_daily("OMH", float=dict(MEMO_FLOAT))], shares=FakeColl([expired]))
    monkeypatch.setattr(FR, "_store", lambda: st)                                    # the REAL VM.shares_status
    out = FR.section(["OMH"], FRI, FRI_IN)
    assert out["OMH"]["read_from"] == "memo" and traps == [] and sh.writes == 0


def test_NEGATIVE_the_real_engine_reads_a_fresh_row_on_the_injected_handle(monkeypatch, traps):
    fresh = {"_id": "OMH", **{k: v for k, v in VALS.items() if k != "as_of"}, "as_of": int(time.time()) - 60}
    st, _d, sh = _world(shares=FakeColl([fresh]))
    monkeypatch.setattr(FR, "_store", lambda: st)
    assert FR.section(["OMH"], FRI, FRI_IN)["OMH"]["read_from"] == "cache" and traps == []


def test_NEGATIVE_36_names_open_zero_clients(traps):
    names = [f"N{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(36)]
    st, _d, sh = _world()
    lk = Lookup({n: (dict(VALS), "cached") for n in names})
    out = _sec(names, lk, st)
    assert len(out) == 36 and traps == []                                             # _shares_coll touched 0 times
    assert len(lk.calls) == 36 and all(kw["coll"] is sh for _s, kw in lk.calls)
    assert st.coll_calls == [VM.SHARES_COLL]                                          # ONE handle, asked once


# ── 6. read counts ───────────────────────────────────────────────────────────────────────────────────────────────
def test_exactly_one_daily_find_of_the_misses_only():
    st, daily, _s = _world(daily=[_daily("NVDA", float=dict(MEMO_FLOAT))])
    lk = Lookup({"OMH": (dict(VALS), "cached")})
    out = _sec(["OMH", "NVDA", "AMD"], lk, st)
    assert daily.finds == [({"_id": {"$in": [ST.key(SESSION, "NVDA"), ST.key(SESSION, "AMD")]}}, FR.DAILY_FIELDS)]
    assert set(out) == {"OMH", "NVDA"} and lk.syms() == ["OMH", "NVDA", "AMD"]


def test_NEGATIVE_zero_daily_finds_when_every_name_hit_the_cache():
    st, daily, _s = _world()
    _sec(["OMH", "NVDA"], Lookup({"OMH": (dict(VALS), "cached"), "NVDA": (dict(VALS), "cached")}), st)
    assert daily.finds == [] and daily.find_ones == []


def test_NEGATIVE_no_names_reads_nothing(monkeypatch):
    st, daily, _s = _world()
    lk = Lookup()
    _wire(monkeypatch, st, lk)
    assert FR.section([], FRI, FRI_IN) == {} and FR.blocks([], FRI, FRI_IN, st=st, lookup=lk) == {}
    assert lk.calls == [] and daily.finds == [] and st.coll_calls == []


def test_NEGATIVE_a_pending_poll_reads_only_its_name(monkeypatch):
    st, daily, _s = _world()
    lk = Lookup()
    _wire(monkeypatch, st, lk)
    rows, _ = _rows(only=["OMH"])
    assert list(rows) == ["OMH"] and lk.syms() == ["OMH"]
    assert daily.finds == [({"_id": {"$in": [ST.key(SESSION, "OMH")]}}, FR.DAILY_FIELDS)]


# ── 7. a carded name: the pass's own chip ────────────────────────────────────────────────────────────────────────
FLOAT_CTX = {"shares": 4_200_000, "src": "float", "as_of": "2026-11-12T15:00:00+00:00"}


def _carded(**kw):
    return _world(reads=[_read("OMH", {"reversal_squeeze": _r("forming", at=None)}, ctx_float=FLOAT_CTX)],
                  pots=[_pot("OMH", "reversal_squeeze")], scan=[_scan("OMH")], state=[_broker_doc("OMH")], **kw)


def test_a_carded_name_serves_the_pass_chip_and_reads_nothing_for_it(monkeypatch):
    st, _d, _s = _carded()
    lk = Lookup({"NVDA": (dict(VALS), "cached")})
    _wire(monkeypatch, st, lk)
    rows, _ = _rows()
    omh = rows["OMH"]
    assert omh["tags"]["float"] == tab._float_chip(FLOAT_CTX)                         # the tags block unchanged
    assert omh["float"]["read_from"] == "pass" and omh["float"]["text"] == omh["tags"]["float"]["text"]
    assert {k: omh["float"][k] for k in ("shares", "src", "text", "as_of", "suspect")} == omh["tags"]["float"]
    assert "OMH" not in lk.syms() and lk.syms() == ["NVDA"]                          # NEGATIVE: zero lookups for OMH
    assert rows["NVDA"]["float"]["read_from"] == "cache"


def test_a_carded_name_with_no_tags_float_falls_to_the_chain(monkeypatch):
    st, _d, _s = _world(reads=[_read("OMH", {"reversal_squeeze": _r("forming", at=None)}, ctx_float=None)],
                        pots=[_pot("OMH", "reversal_squeeze")], scan=[_scan("OMH")])
    lk = Lookup({"OMH": (dict(VALS), "cached")})
    _wire(monkeypatch, st, lk)
    rows, _ = _rows()
    assert rows["OMH"]["tags"]["float"] is None and rows["OMH"]["float"]["read_from"] == "cache"
    assert "OMH" in lk.syms()


# ── 8. faults [C10] ──────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_raising_daily_find_keeps_cache_and_pass_chips(caplog):
    st, _d, _s = _world(daily_fail=True)
    lk = Lookup({"OMH": (dict(VALS), "cached")})
    chip = tab._float_chip(FLOAT_CTX)
    with caplog.at_level(logging.WARNING):
        out = _sec(["OMH", "AMD", "NVDA"], lk, st, {"AMD": {"float": chip}})
    assert set(out) == {"OMH", "AMD"} and out["AMD"]["read_from"] == "pass" and out["OMH"]["read_from"] == "cache"
    assert len(_msgs(caplog, "float memo unavailable")) == 1 and _msgs(caplog, "float unavailable:") == []


def test_NEGATIVE_no_daily_handle_keeps_cache_chips(caplog):
    st, _d, _s = _world(no_daily=True)
    with caplog.at_level(logging.WARNING):
        out = _sec(["OMH", "NVDA"], Lookup({"OMH": (dict(VALS), "cached")}), st)
    assert set(out) == {"OMH"} and len(_msgs(caplog, "float memo unavailable")) == 1


def test_NEGATIVE_a_raising_lookup_blanks_the_section_with_one_warning(monkeypatch, caplog):
    st, _d, _s = _world()
    _wire(monkeypatch, st, Lookup(fail=True))
    with caplog.at_level(logging.WARNING):
        assert FR.section(["OMH", "NVDA"], FRI, FRI_IN) == {}
    assert len(_msgs(caplog, "gajjala_watch: float unavailable")) == 1


def test_NEGATIVE_no_shares_handle_blanks_the_section_and_never_passes_none(monkeypatch, caplog, traps):
    st, _d, _s = _world(no_shares=True)
    lk = Lookup()
    _wire(monkeypatch, st, lk)
    with caplog.at_level(logging.WARNING):
        assert FR.section(["OMH"], FRI, FRI_IN) == {}
    assert lk.calls == [] and traps == [] and len(_msgs(caplog, "gajjala_watch: float unavailable")) == 1


@pytest.mark.parametrize("stub", ["raises", "missing", "non_dict"])
def test_NEGATIVE_a_broken_float_module_serves_none_and_the_board_answers(monkeypatch, stub):
    st, _d, _s = _world()
    _wire(monkeypatch, st, Lookup({"OMH": (dict(VALS), "cached")}))
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    good_rows, good = _rows(db=db)
    assert good_rows["OMH"]["float"] is not None

    def boom(*a, **k):
        raise RuntimeError("float engine down")
    mod = {"raises": types.SimpleNamespace(section=boom), "missing": None,
           "non_dict": types.SimpleNamespace(section=lambda *a, **k: ["not", "a", "dict"])}[stub]
    monkeypatch.setitem(sys.modules, PL.FLOAT_MODULE, mod)
    rows, out = _rows(db=db)
    assert out["state"] == "ok" and list(rows) == list(good_rows)
    for s, r in rows.items():
        assert r["float"] is None
        assert {k: v for k, v in r.items() if k != "float"} == {k: v for k, v in good_rows[s].items() if k != "float"}
    assert {k: v for k, v in out.items() if k != "rows"} == {k: v for k, v in good.items() if k != "rows"}


# ── 9. suspect ───────────────────────────────────────────────────────────────────────────────────────────────────
SUSPECT_VALS = {"shares_outstanding": 1_299_391, "float_shares": 1_314_047, "market_cap": None, "as_of": AS_OF_TS}


def test_a_suspect_cache_float_serves_the_numbered_words():
    st, _d, _s = _world()
    f = _sec(["FCHL"], Lookup({"FCHL": (dict(SUSPECT_VALS), "cached")}), st)["FCHL"]
    fr = CX._yf_read(dict(SUSPECT_VALS), "cached", FRI_IN)
    assert GC.FLOAT_SUSPECT_POLICY == "ineligible"
    assert f["suspect"] is True and f["text"].startswith("Float ")
    assert f["suspect_text"] == fr["suspect_text"] and f["suspect_text"]                # NEGATIVE: never dropped


def test_C5_a_carded_suspect_chip_takes_the_cache_rows_numbered_words():
    st, _d, _s = _world()
    chip = tab._float_chip({"shares": 1_314_047, "src": "float", "as_of": "2026-11-12", "suspect": "x"})
    lk = Lookup({"FCHL": (dict(SUSPECT_VALS), "cached")})
    f = _sec(["FCHL"], lk, st, {"FCHL": {"float": chip}})["FCHL"]
    fr = CX._yf_read(dict(SUSPECT_VALS), "cached", FRI_IN)
    assert f["read_from"] == "pass" and f["suspect_text"] == fr["suspect_text"]
    assert lk.syms() == ["FCHL"]                                                       # EXACTLY one lookup


@pytest.mark.parametrize("table", [{"FCHL": (dict(VALS), "cached")}, {}])
def test_C5_a_carded_suspect_chip_with_no_suspect_cache_row_takes_the_generic_words(table):
    st, _d, _s = _world()
    chip = tab._float_chip({"shares": 1_314_047, "src": "float", "as_of": "2026-11-12", "suspect": "x"})
    lk = Lookup(table)
    f = _sec(["FCHL"], lk, st, {"FCHL": {"float": chip}})["FCHL"]
    assert f["suspect_text"] == tab._float_suspect_text({}, chip) and f["suspect_text"]
    assert "exceeds shares out" in f["suspect_text"] and lk.syms() == ["FCHL"]


def test_NEGATIVE_a_carded_non_suspect_chip_reads_nothing():
    st, _d, _s = _world()
    lk = Lookup()
    f = _sec(["OMH"], lk, st, {"OMH": {"float": tab._float_chip(FLOAT_CTX)}})["OMH"]
    assert lk.calls == [] and f["suspect"] is False and f["suspect_text"] is None


# ── 10. NaN ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_nan_float_and_nan_shares_serve_no_key():
    st, _d, _s = _world()
    nan = dict(VALS, float_shares=float("nan"), shares_outstanding=float("nan"))
    assert _sec(["OMH"], Lookup({"OMH": (nan, "cached")}), st) == {}


def test_nan_float_with_real_shares_out_serves_shares_out(monkeypatch):
    st, _d, _s = _world()
    lk = Lookup({"OMH": (dict(VALS, float_shares=float("nan")), "cached")})
    f = _sec(["OMH"], lk, st)["OMH"]
    assert f["text"].startswith("shares out") and f["src"] == "shares_out_yf"
    assert math.isfinite(f["shares"])
    _wire(monkeypatch, st, lk)
    out = PL.build(FRI_IN, db=_db(["OMH", "NVDA"]))
    _strict(json.dumps(out, allow_nan=False, default=str))


# ── 11. the row key set ──────────────────────────────────────────────────────────────────────────────────────────
def test_every_row_his_auto_aplus_pending_carries_float(monkeypatch):
    st, _d, _s = _world()
    _wire(monkeypatch, st, Lookup({"AUTOX": (dict(VALS), "cached")}))
    monkeypatch.setattr(PL, "auto_section", lambda cs, symbols, siso, **kw: ({"AUTOX": {"why": "potential"}}, None,
                                                                             {"AUTOX": None}))
    monkeypatch.setattr(PL, "aplus_section", lambda names, siso: {"OMH": {"text": "🎯 A+"}})
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    rows, _ = _rows(db=db)
    assert set(rows) == {"OMH", "NVDA", "AUTOX"}
    assert rows["NVDA"]["state"] == "pending" and rows["OMH"]["aplus"] and rows["AUTOX"]["auto"]
    assert all("float" in r for r in rows.values())
    assert rows["AUTOX"]["float"]["read_from"] == "cache"


# ── 12. static source checks ─────────────────────────────────────────────────────────────────────────────────────
HARD_NO = ("fetch=True", "floats_for", "_massive_once", "_default_massive_lookup", "_default_status_lookup",
           "_shares_coll", "MongoClient", "short_interest.client", "yfinance", "requests", "httpx", "datetime.now",
           "time.time", "date.today")
WRITE_CALL = re.compile(r"\.\s*(update|insert|upsert|set_state|replace|delete)\w*\s*\(")


def test_NEGATIVE_float_read_source_carries_no_hard_no_token():
    src = SRC.read_text()
    for tok in HARD_NO:
        assert tok not in src, tok
    assert src.count("fetch=False") == 1
    assert not WRITE_CALL.search(src)
    assert not B_WORD.search(src)
    assert not re.search("fidelity|not eligible", src, re.I)
    assert "can you add the current float value also to the tickers on the watch list." in src


def test_NEGATIVE_the_probe_never_writes_or_fetches():
    src = PROBE.read_text()
    assert not WRITE_CALL.search(src) and "fetch=True" not in src and "docker cp" not in src
    assert "fetch=False" in src and "coll=" in src


# ── 13. words ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_source_words_cover_exactly_the_srcs_context_serves():
    ctx_src = Path(CX.__file__).read_text()
    emitted = set(re.findall(r'src="(\w+)"', ctx_src)) | set(re.findall(r'"src": "(\w+)"', ctx_src))
    assert set(FR.FLOAT_SOURCE_WORDS) == emitted == {"float", "shares_out_yf", "shares_out_massive"}
    assert set(FR.FLOAT_STALE_SOURCE_WORDS) <= {"float", "shares_out_yf"}
    assert FR.ttl_days() == timedelta(seconds=VM._SHARES_TTL_SEC).days == 7
    assert set(FR.READ_FROM) == {"pass", "cache", "memo"}


@pytest.mark.parametrize("mod", ["auto.py", "loop.py", "cross_alerts.py"])
def test_NEGATIVE_the_loop_side_never_imports_float_read(mod):
    assert "float_read" not in (SRC.parent / mod).read_text()
