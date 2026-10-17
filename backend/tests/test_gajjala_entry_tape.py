"""🕰️ chart_maps/gajjala/tape.py + GET /chart-maps/gajjala/entry-tape (BUILD_SPEC11 §3.3–§3.5 / §4 WP-A, AMENDMENTS11
F8 / F9 / F19 / F20 — 2026-10-16 night).

Ajay 2026-10-16 ~22:00 ET, verbatim: "We have a Promo Circuit tab in Catalyst tab. Can you use the graph component from
 that to show what happened to Entries alert of Gajjala with all the 100% criteria satisfier. One you alert it from the
alert system you built please"

UNMEASURED — the tape is a picture of what each A+ alert did, graded by the ledger's own math. Every store is the
in-memory FakeColl set (tests/conftest.py refuses a real MongoClient); every loader is injected or monkeypatched — the
network is NEVER touched (an autouse guard makes the minute fetch and the ledger's today loader raise unless a test
swaps them). The REAL tape is tests/fixtures/gajjala/xlab_2026_10_16_1m.json; the 10-15 tapes are the SYNTHETIC ones of
tests/test_gajjala_track_record_tab.py (named so there). NEGATIVES are mandatory and marked.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
import threading
import time as _time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from catalysts import promo_tape as PROMO
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tape as TP
from daytrading import data as dt_data
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import _walk_strings, run_route
from tests.test_gajjala_track_record_tab import (D15, D16, NOW, _et, _flat, _real_tape, _xlab_15_synthetic, board,
                                                 golden_entry_doc, ledger_store, live_entry_doc, no_split,
                                                 shadow_doc, tape_loader)

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D13, D14, D19 = date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 19)
MON_NIGHT = datetime(2026, 10, 19, 22, 0, tzinfo=ET)          # every 10-15 / 10-16 day is a COMPLETED day
B_WORD = re.compile("b" + "ounc", re.I)
NAMES = re.compile(r"\bSEPA\b|minervini|bonde|\bTLSW\b|\bTTLAC\b", re.I)
XLAB15_ID = "2026-10-15|XLAB|intraday_vcp|aplus"
GOLDEN_ID = "2026-10-16|XLAB|intraday_vcp|aplus"
OLD_ID = "2026-10-13|OLDX|bull_flag|aplus"


class Rec:
    """A call recorder: returns `ret` (or `ret(*a, **k)` when callable), raises `exc` when given."""

    def __init__(self, ret=None, exc=None):
        self.calls, self.ret, self.exc = [], ret, exc

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.exc is not None:
            raise self.exc
        return self.ret(*a, **k) if callable(self.ret) else self.ret


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """Memos cleared; the network refused: the minute fetch and the ledger's forced today loader RAISE unless a test
    swaps them; intraday_cache is an empty in-memory dict (no Mongo)."""
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    for m in (LG._TODAY_MEMO, LG._TODAY_SPLIT, TP._MEMO):
        m.clear()
    net = Rec(exc=AssertionError("network: the minute fetch was called"))
    monkeypatch.setattr(dt_data, "_fetch_massive_minute", net)
    monkeypatch.setattr(LG, "_today_load", Rec(exc=AssertionError("network: the forced today loader was called")))
    cache = {}
    monkeypatch.setattr(dt_data, "_mongo_get_day", lambda sym, day: (cache.get((sym.upper(), str(day))).copy()
                                                                     if (sym.upper(), str(day)) in cache else None))
    monkeypatch.setattr(dt_data, "_mongo_put_day", lambda sym, day, df: cache.__setitem__((sym.upper(), str(day)), df))
    yield {"net": net, "cache": cache}
    for m in (LG._TODAY_MEMO, LG._TODAY_SPLIT, TP._MEMO):
        m.clear()


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def frame(bars, vol=1000.0) -> pd.DataFrame:
    """The loader's DataFrame shape (naive-UTC minute STARTS, session tagged) from ledger tuples."""
    idx = pd.DatetimeIndex([b[0].astimezone(UTC).replace(tzinfo=None) for b in bars], name="ts_utc")
    df = pd.DataFrame({"open": [b[1] for b in bars], "high": [b[2] for b in bars], "low": [b[3] for b in bars],
                       "close": [b[4] for b in bars], "volume": vol}, index=idx)
    df["session"] = [dt_data._classify_session(ts) for ts in df.index]
    return df


def ms(dt_et: datetime) -> int:
    return int(dt_et.astimezone(UTC).timestamp() * 1000)


def xlab15_store(*, stop_out=False):
    """A SHADOW A+ XLAB 🌀 10-15 15:11 row (the AMENDMENTS9 E1 plan 1.22 / 1.16) graded by the REAL nightly step on the
    SYNTHETIC 10-15 tape: WIN (fill 1.22 at 15:21, +1R 1.28 at 15:22). `stop_out`: the 15:22 minute instead trades
    down to 1.15 — a LOSS on the stop at 15:22."""
    doc = shadow_doc(D15, "XLAB", "intraday_vcp", _et(D15, 15, 11), trigger=1.22, stop=1.16, price=1.20)
    st = fake_store(**{ST.ALERTS: FakeColl([doc])})
    load = tape_loader() if not stop_out else (lambda s, d: (stop_tape(), False))
    out = LG.grade_step(st, _et(D15, 20, 15, 30), load_day=load, split_lookup=lambda *a: False)
    assert out["read_fault"] is False and out["written"] == 1, out
    return st


def stop_tape() -> list:
    out = []
    for b in _xlab_15_synthetic():
        et = b[0].astimezone(ET)
        if (et.hour, et.minute) == (15, 22):
            b = (b[0], 1.21, 1.22, 1.15, 1.16)
        elif et >= _et(D15, 15, 23):
            b = (b[0], 1.16, 1.16, 1.16, 1.16)
        out.append(b)
    return out


def load15(log=None, tape=None):
    """load_day for the tape: the 10-15 synthetic tuples, the 10-16 real tape; every call logged."""
    def load(sym, day):
        if log is not None:
            log.append((sym, day))
        if day == D15:
            return list(tape or _xlab_15_synthetic())
        if day == D16:
            return _real_tape()
        return None
    return load


def today_real(log=None):
    def tb(sym, day, **k):
        if log is not None:
            log.append((sym, day, k.get("load")))
        return _real_tape(), k.get("now")
    return tb


def old_store(**over):
    """A SHADOW A+ row of 2026-10-13 11:00 ET (SYNTHETIC plan 4.00 / 3.80) — both its days are completed whatever the
    wall clock says, so the route (which cannot take a `now`) reads only intraday_cache."""
    doc = shadow_doc(D13, "OLDX", "bull_flag", _et(D13, 11, 0), trigger=4.0, stop=3.8, price=3.9)
    doc.update(over)
    return fake_store(**{ST.ALERTS: FakeColl([doc])})


def cache_old(env):
    env["cache"][("OLDX", "2026-10-13")] = frame(_flat(D13, 3.9))
    env["cache"][("OLDX", "2026-10-14")] = frame(_flat(D14, 3.95))


def _route(monkeypatch, st):
    from chart_maps import api as API
    monkeypatch.setattr(ST, "default", lambda: st)
    return API


def _call(API, **kw):
    return run_route(API.chart_maps_gajjala_entry_tape(**kw))


def _served_row(st, rid, now, span="5d", today=None):
    from chart_maps.gajjala import tab as GT
    session, is_today, _ = GT.session_for(now)
    b = LG.served_block(st, session, now, span=span, is_today=is_today, today=today)
    return {r["id"]: r for d in b["days"] for r in d["rows"]}[rid]


def _txt(c):
    return c["text"] + (" · " + c["sub_text"] if c.get("sub_text") else "")


# ── 1. the route ─────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["2026-10-13|ZZZZ|bull_flag|aplus", "2026-10-13|OLDX|bull_flag|potential", "junk", "",
                                 None, "2026-10-13|oldx|bull_flag|aplus", "2026-13-40|OLDX|bull_flag|aplus",
                                 "REPLAY:2026-10-12|RPL|bull_flag"])
def test_NEGATIVE_route_an_unknown_potential_junk_or_empty_id_is_404(monkeypatch, _clean, bad):
    cache_old(_clean)
    API = _route(monkeypatch, old_store())
    resp = _call(API, id=bad, lite=0)
    assert resp.status_code == 404 and json.loads(resp.body) == {"detail": TP.ENTRY_TAPE_WORDS["not_found"]}, bad
    assert TP.ENTRY_TAPE_WORDS["not_found"] == "No A+ entry with that id on the 🏁 Track record."


def test_NEGATIVE_route_the_query_objects_themselves_are_coerced_to_404(monkeypatch, _clean):
    cache_old(_clean)
    API = _route(monkeypatch, old_store())
    resp = run_route(API.chart_maps_gajjala_entry_tape())            # a direct call: both args are Query OBJECTS
    assert resp.status_code == 404


def test_route_a_known_id_serves_the_frozen_payload_and_lite_the_lite_keys(monkeypatch, _clean):
    cache_old(_clean)
    API = _route(monkeypatch, old_store())
    full = _call(API, id=OLD_ID, lite=0)
    body = json.loads(full.body)
    assert full.status_code == 200 and set(body) == set(TP.PAYLOAD_KEYS) and body["lite"] is False
    assert body["ticker"] == "OLDX" and body["n_bars"] == len(body["bars"]) > 0 and body["note"] is None
    lite = _call(API, id=OLD_ID, lite=1)
    lb = json.loads(lite.body)
    assert lite.status_code == 200 and set(lb) == set(TP.LITE_KEYS) and lb["lite"] is True
    assert all(set(x) == {"t", "c", "s"} for x in lb["bars"])
    assert _clean["net"].calls == []                                 # both days were cached: no fetch at all
    for junk in (True, 2, "1", None):                                # NEGATIVE: only the int 1 means lite
        b = json.loads(_call(API, id=OLD_ID, lite=junk).body)
        assert set(b) == set(TP.PAYLOAD_KEYS), junk


def test_route_F20_the_span_description_lists_10d():
    from chart_maps import api as API
    desc = inspect.signature(API.chart_maps_gajjala).parameters["span"].default.description
    assert "today | yesterday | 5d (default) | 10d | all" in desc


def test_route_F19_a_raising_build_serves_200_with_the_fault_payload_never_a_500(monkeypatch, _clean):
    API = _route(monkeypatch, old_store())
    monkeypatch.setattr(TP, "entry_tape", Rec(exc=RuntimeError("boom")))
    for lt in (0, 1):
        resp = _call(API, id=OLD_ID, lite=lt)
        body = json.loads(resp.body)
        assert resp.status_code == 200 and set(body) == set(TP.PAYLOAD_KEYS), lt
        assert body["note"] == TP.ENTRY_TAPE_WORDS["fault"] and body["bars"] == [] and body["n_bars"] == 0
        assert (body["ticker"], body["hlines"], body["rules"], body["dots"], body["axis"]) == (None, [], [], [], None)
        assert body["lite"] is bool(lt) and body["id"] == OLD_ID and body["as_of"]


def test_route_the_handler_sits_after_the_scan_post_never_inside_the_board_gets_slice():
    from chart_maps import api as API
    src = Path(API.__file__).read_text(encoding="utf-8")
    get_at = src.index("async def chart_maps_gajjala(")
    nxt = src.index("\n@router.", get_at)
    assert "entry_tape" not in src[get_at:nxt]
    assert src.index('@router.post("/chart-maps/gajjala/scan")') < src.index('@router.get("/chart-maps/gajjala/entry-tape")')


# ── 2. a completed day's shadow WIN: lines, rules, dots, read = the 🏁 cells ───────────────────────────────────────
def test_a_completed_shadow_win_draws_its_lines_rules_dots_and_reads_the_track_records_own_cells():
    st = xlab15_store()
    p = TP.entry_tape(XLAB15_ID, now=NOW, store=st, load_day=load15(), today_bars=today_real())
    assert set(p) == set(TP.PAYLOAD_KEYS) and p["note"] is None and p["ticker"] == "XLAB"
    assert [(h["key"], h["px"], h["tone"], h["label"]) for h in p["hlines"]] == [
        ("trigger", 1.22, "buy", "trigger 1.22"), ("stop", 1.16, "stop", "stop 1.16"),
        ("target", pytest.approx(1.28), "target", "+1R 1.28")]
    assert [(r["key"], r["style"], r["tone"], r["label"]) for r in p["rules"]] == [
        ("alert", "solid", "alert", "alert 15:11 ET"), ("fill", "dashed", "fill", "fill 15:21")]
    assert p["rules"][0]["at"] == _et(D15, 15, 11).astimezone(UTC).isoformat()
    assert [(d["key"], d["tone"], d["label"]) for d in p["dots"]] == [("fill", "fill", "fill 1.22 at 15:21"),
                                                                      ("exit", "target", "+1R 15:22")]
    assert p["dots"][0]["px"] == 1.22 and p["dots"][1]["px"] == pytest.approx(1.28)
    r = _served_row(st, XLAB15_ID, NOW)
    want = f"Same session: {_txt(r['same'])}; Through next session: {_txt(r['next'])}"
    assert p["read"] == want and r["same"]["state"] == "win"                     # one engine: the 🏁 cells
    assert p["title"] == want + "\n📈 click for the full tape"
    assert p["tf"] == "5min · pre/post market" and p["aria"] == "XLAB 5-minute tape around the A+ entry"
    assert p["legend"] == ("5-minute closes · shaded = pre / post market · solid line = the alert · dashed = the fill · "
                           "levels = trigger / stop / +1R")
    assert p["bars"][0]["t"] == ms(_et(D15, 4, 5)) and p["tone"] in ("up", "dn")
    assert p["axis"]["bl"] == "Oct 15 · 4:05a ET" and p["axis"]["br"].startswith("Oct 16 · ")


# ── 3. C1: a cached completed day never fetches; a miss fetches exactly once ─────────────────────────────────────
def _spy_loader(monkeypatch):
    real = dt_data.load_intraday
    spy = Rec(ret=lambda *a, **k: real(*a, **k))
    monkeypatch.setattr(dt_data, "load_intraday", spy)
    monkeypatch.setattr(dt_data, "_today_et", lambda: D19)
    return spy


def test_C1_a_cached_completed_day_never_fetches_and_the_loader_is_never_forced(monkeypatch, _clean):
    st = xlab15_store()
    _clean["cache"][("XLAB", "2026-10-15")] = frame(_xlab_15_synthetic())
    _clean["cache"][("XLAB", "2026-10-16")] = frame(_real_tape())
    spy = _spy_loader(monkeypatch)
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st)
    assert _clean["net"].calls == []                                               # NEGATIVE: 0 fetches
    assert len(spy.calls) == 2 and all(not k.get("force") for _a, k in spy.calls)
    assert all(k.get("include_premarket") and k.get("include_afterhours") for _a, k in spy.calls)
    b = LG._bounds_of(LG.alert_of(st.alert_rows([D15])[0], "aplus"))
    assert p["bars"][0]["t"] == ms(_et(D15, 4, 5)) and p["bars"][-1]["t"] <= int(b["next_end"].timestamp() * 1000)
    assert p["note"] is None and len(p["bars"]) <= GC.LEDGER_TAPE_BARS_MAX


def test_C1_a_cache_miss_fetches_once_per_symbol_day_then_reads_the_cache(monkeypatch, _clean):
    st = xlab15_store()
    _clean["cache"][("XLAB", "2026-10-15")] = frame(_xlab_15_synthetic())
    _spy_loader(monkeypatch)
    fetch = Rec(ret=lambda sym, a, b: frame(_real_tape()))
    monkeypatch.setattr(dt_data, "_fetch_massive_minute", fetch)
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st)
    assert [a for a, _k in fetch.calls] == [("XLAB", D16, D16)] and p["n_bars"] > 0
    TP._MEMO.clear()
    TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st)
    assert len(fetch.calls) == 1                                                    # the loader cached it


def test_F8_the_full_path_fetches_a_miss_exactly_once_from_two_threads(monkeypatch, _clean):
    st = xlab15_store()
    _clean["cache"][("XLAB", "2026-10-15")] = frame(_xlab_15_synthetic())
    _spy_loader(monkeypatch)

    def slow(sym, a, b):
        _time.sleep(0.05)
        return frame(_real_tape())
    fetch = Rec(ret=slow)
    monkeypatch.setattr(dt_data, "_fetch_massive_minute", fetch)
    go, outs = threading.Barrier(2), []

    def worker():
        go.wait()
        outs.append(TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st))
    ts = [threading.Thread(target=worker) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(5)
    assert len(outs) == 2 and all(o["n_bars"] > 0 for o in outs)
    assert len(fetch.calls) == 1, fetch.calls


# ── 4. today through the ONE ledger memo ─────────────────────────────────────────────────────────────────────────
def _golden_only_store():
    return fake_store(**{ST.ALERTS: FakeColl([golden_entry_doc()])})


def _count_today_load(monkeypatch):
    rec = Rec(ret=lambda sym, day: ((_real_tape() if (sym, day) == ("XLAB", D16) else []), False))
    monkeypatch.setattr(LG, "_today_load", rec)
    return rec


def test_today_goes_through_the_shared_memo_once_and_today_read_then_loads_nothing(monkeypatch):
    st = _golden_only_store()
    rec = _count_today_load(monkeypatch)
    p = TP.entry_tape(GOLDEN_ID, now=NOW, store=st)
    TP._MEMO.clear()
    p2 = TP.entry_tape(GOLDEN_ID, now=NOW, store=st)
    assert len(rec.calls) == 1 and ("2026-10-16", "XLAB") in LG._TODAY_MEMO
    assert p2["read"] == p["read"] and p["n_bars"] > 0
    today = LG.today_read(NOW, span="today", store=st, split_lookup=no_split)
    assert len(rec.calls) == 1 and today["stats"]["memo"] == 1                    # the 🏁 GET's read: 0 more loads
    r = _served_row(st, GOLDEN_ID, NOW, span="today", today=today)
    assert p["read"] == f"Same session: {_txt(r['same'])}; Through next session: {_txt(r['next'])}"
    assert r["same"]["provisional"] is True and r["same"]["state"] == "win"
    assert [d["label"] for d in p["dots"]] == ["fill 1.85 at 09:46", "+1R 09:47"]


def test_the_reverse_order_today_read_first_then_the_tape_loads_nothing(monkeypatch):
    st = _golden_only_store()
    rec = _count_today_load(monkeypatch)
    LG.today_read(NOW, span="today", store=st, split_lookup=no_split)
    assert len(rec.calls) == 1
    p = TP.entry_tape(GOLDEN_ID, now=NOW, store=st)
    assert len(rec.calls) == 1 and p["n_bars"] > 0 and p["note"] is None


def test_NEGATIVE_no_minute_that_has_not_closed_and_settled_is_drawn(monkeypatch):
    st = _golden_only_store()
    _count_today_load(monkeypatch)
    early = datetime(2026, 10, 16, 11, 10, 45, tzinfo=ET)       # 11:10 has not closed + settled (11:11:00 + 30 s)
    p = TP.entry_tape(GOLDEN_ID, now=early, store=st)
    assert p["bars"][-1]["t"] == ms(_et(D16, 11, 10))          # the 11:05–11:09 bucket; the 11:10 minute is out
    LG._TODAY_MEMO.clear()
    TP._MEMO.clear()
    p2 = TP.entry_tape(GOLDEN_ID, now=NOW, store=st)
    assert p2["bars"][-1]["t"] == ms(_et(D16, 11, 15))         # 11:11:30: the 11:10 minute has settled


# ── 5. lite = the Promo engine and its constant (F8: the mini never fetches) ──────────────────────────────────────
def test_lite_is_the_promo_lite_engine_on_the_full_bars_and_reads_the_stride_at_call_time(monkeypatch):
    st = xlab15_store()
    kw = dict(now=NOW, store=st, load_day=load15(), today_bars=today_real())
    full = TP.entry_tape(XLAB15_ID, **kw)
    lite = TP.entry_tape(XLAB15_ID, lite=True, **kw)
    assert lite["bars"] == PROMO.lite_payload({"bars": full["bars"]}, stride=PROMO.LITE_STRIDE)["bars"]
    assert set(lite) == set(TP.LITE_KEYS) and all(set(b) == {"t", "c", "s"} for b in lite["bars"])
    assert [r["key"] for r in lite["rules"]] == ["alert"] and lite["n_bars"] == full["n_bars"]
    assert lite["title"] == full["title"] and lite["tone"] == full["tone"]
    monkeypatch.setattr(PROMO, "LITE_STRIDE", 2)                                   # mutation: never a typed 3
    two = TP.lite_of(full)
    assert two["bars"] != lite["bars"] and two["bars"] == PROMO.lite_payload({"bars": full["bars"]}, stride=2)["bars"]
    TP._MEMO.clear()
    assert TP.entry_tape(XLAB15_ID, lite=True, **kw)["bars"] == two["bars"]


def test_F8_NEGATIVE_the_lite_tape_never_fetches_cache_and_memo_only(_clean):
    """`_fetch_massive_minute` and `_today_load` RAISE (the autouse guard): the lite reads intraday_cache for the
    completed day and the ledger memo for today — a memo miss is the lite_today note (AMENDMENTS11 A6: it is not a
    failed read, the 📈 full tape loads it), never a load; NEGATIVE: never the today_failed word."""
    st = xlab15_store()
    _clean["cache"][("XLAB", "2026-10-15")] = frame(_xlab_15_synthetic())
    p = TP.entry_tape(XLAB15_ID, lite=True, now=NOW, store=st)
    assert _clean["net"].calls == [] and LG._today_load.calls == []
    assert p["note"] == TP.ENTRY_TAPE_WORDS["lite_today"] and p["bars"]            # 10-15 from the cache only
    assert p["note"] != TP.ENTRY_TAPE_WORDS["today_failed"] and "📈" in p["note"]
    assert max(b["t"] for b in p["bars"]) < ms(_et(D16, 0, 0))
    assert TP._MEMO == {}                                                          # a failed read is not memoised
    bars, at = LG.today_bars("XLAB", D16, now=NOW, load=lambda s, d: (_real_tape(), False))
    assert bars and at == NOW.astimezone(UTC)
    p2 = TP.entry_tape(XLAB15_ID, lite=True, now=NOW, store=st)
    assert p2["note"] is None and max(b["t"] for b in p2["bars"]) > ms(_et(D16, 0, 0))   # today from the memo
    assert _clean["net"].calls == [] and LG._today_load.calls == []


def test_F8_NEGATIVE_a_lite_cache_miss_is_no_bars_never_a_fetch(_clean):
    st = old_store()
    p = TP.entry_tape(OLD_ID, lite=True, now=MON_NIGHT, store=st)
    assert _clean["net"].calls == [] and p["bars"] == []
    assert p["note"] == "No 5-minute bars on file for OLDX on 2026-10-13 yet."


def test_F8_the_route_lite_with_the_fetch_and_the_today_loader_raising_is_200_from_the_cache(monkeypatch, _clean):
    cache_old(_clean)
    API = _route(monkeypatch, old_store())
    resp = _call(API, id=OLD_ID, lite=1)
    body = json.loads(resp.body)
    assert resp.status_code == 200 and body["n_bars"] > 0 and set(body) == set(TP.LITE_KEYS)
    assert _clean["net"].calls == [] and LG._today_load.calls == []


def test_a_full_build_refreshes_the_lite_memo_entry():
    st = xlab15_store()
    kw = dict(now=NOW, store=st, load_day=load15(), today_bars=today_real())
    full = TP.entry_tape(XLAB15_ID, **kw)
    assert set(TP._MEMO) == {(XLAB15_ID, "full"), (XLAB15_ID, "lite")}
    assert TP._MEMO[(XLAB15_ID, "lite")][1] == TP.lite_of(full)


# ── 6. faults: never a 500 ───────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_raising_completed_day_loader_is_the_fault_note():
    st = xlab15_store()
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=Rec(exc=RuntimeError("down")))
    assert p["bars"] == [] and p["note"] == TP.ENTRY_TAPE_WORDS["fault"] and set(p) == set(TP.PAYLOAD_KEYS)
    assert p["read"].startswith("Same session: WIN")                               # the grades still read
    assert TP._MEMO == {}                                                          # never memoised


def test_NEGATIVE_a_raising_today_read_is_today_failed_and_the_other_days_stand():
    st = xlab15_store()
    p = TP.entry_tape(XLAB15_ID, now=NOW, store=st, load_day=load15(), today_bars=Rec(exc=RuntimeError("down")))
    assert p["note"] == TP.ENTRY_TAPE_WORDS["today_failed"] and p["bars"]
    p2 = TP.entry_tape(GOLDEN_ID, now=NOW, store=_golden_only_store(), today_bars=Rec(exc=RuntimeError("down")))
    assert p2["bars"] == [] and p2["note"] == TP.ENTRY_TAPE_WORDS["today_failed"]


def test_NEGATIVE_an_unreadable_alert_ledger_is_the_fault_note_and_an_unknown_id_None(monkeypatch):
    st = xlab15_store()
    monkeypatch.setattr(st, "alert_rows", lambda sessions: None)
    p = TP.entry_tape(XLAB15_ID, now=NOW, store=st, load_day=load15(), today_bars=today_real())
    assert p["note"] == TP.ENTRY_TAPE_WORDS["fault"] and p["bars"] == [] and set(p) == set(TP.PAYLOAD_KEYS)
    lp = TP.entry_tape(XLAB15_ID, lite=True, now=NOW, store=st)
    assert set(lp) == set(TP.LITE_KEYS) and lp["note"] == TP.ENTRY_TAPE_WORDS["fault"]
    assert TP.entry_tape("2026-10-15|XLAB|bull_flag|aplus", now=NOW, store=xlab15_store()) is None


def test_NEGATIVE_the_route_serves_200_when_the_house_loader_raises(monkeypatch, _clean):
    API = _route(monkeypatch, old_store())
    monkeypatch.setattr(TP, "_completed_day", Rec(exc=RuntimeError("massive down")))
    resp = _call(API, id=OLD_ID, lite=0)
    body = json.loads(resp.body)
    assert resp.status_code == 200 and body["note"] == TP.ENTRY_TAPE_WORDS["fault"] and body["bars"] == []


# ── 7. the per-id memo ───────────────────────────────────────────────────────────────────────────────────────────
def test_the_payload_is_memoised_per_id_for_the_memo_window(monkeypatch):
    st = xlab15_store()
    reads = Rec(ret=st.alert_rows)
    monkeypatch.setattr(st, "alert_rows", reads)
    clk = Clock()
    kw = dict(now=NOW, store=st, clock=clk, load_day=load15(), today_bars=today_real())
    a = TP.entry_tape(XLAB15_ID, **kw)
    clk.t += GC.LEDGER_TAPE_MEMO_SEC - 1
    assert TP.entry_tape(XLAB15_ID, **kw) is a and len(reads.calls) == 1
    clk.t += 1
    TP.entry_tape(XLAB15_ID, **kw)
    assert len(reads.calls) == 2
    assert GC.LEDGER_TAPE_MEMO_SEC == GC.PASS_CADENCE_SEC


# ── 8. NEGATIVES: what is not on file is not drawn ───────────────────────────────────────────────────────────────
def _one_row_store(doc, tape):
    st = fake_store(**{ST.ALERTS: FakeColl([doc])})
    LG.grade_step(st, _et(D15, 20, 15, 30), load_day=lambda s, d: (tape, False), split_lookup=lambda *a: False)
    return st


def test_NEGATIVE_no_fill_no_fill_rule_no_dots_no_target_line():
    doc = shadow_doc(D15, "PMI", "bull_flag", _et(D15, 10, 36), trigger=2.40, stop=2.20, price=2.35)
    st = _one_row_store(doc, _flat(D15, 2.10))
    p = TP.entry_tape("2026-10-15|PMI|bull_flag|aplus", now=MON_NIGHT, store=st,
                      load_day=lambda s, d: _flat(d, 2.10))
    assert [h["key"] for h in p["hlines"]] == ["trigger", "stop"] and p["dots"] == []
    assert [r["key"] for r in p["rules"]] == ["alert"] and p["read"].startswith("Same session: no entry")
    assert p["tone"] == "dn"                                                       # under the trigger


def test_a_stop_out_puts_the_exit_dot_on_the_stop():
    st = xlab15_store(stop_out=True)
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load15(tape=stop_tape()))
    ex = p["dots"][-1]
    assert (ex["key"], ex["px"], ex["tone"], ex["label"]) == ("exit", 1.16, "stop", "stop 15:22")
    assert p["read"].startswith("Same session: LOSS")


def test_NEGATIVE_no_alert_time_no_alert_rule():
    doc = shadow_doc(D13, "OLDX", "bull_flag", _et(D13, 11, 0), trigger=4.0, stop=3.8, price=3.9)
    doc.pop("at")
    st = fake_store(**{ST.ALERTS: FakeColl([doc])})
    p = TP.entry_tape(OLD_ID, now=MON_NIGHT, store=st, load_day=lambda s, d: _flat(d, 3.9))
    assert p["rules"] == [] and p["dots"] == [] and p["read"].startswith("Same session: no alert time")


def test_NEGATIVE_no_plan_no_lines():
    doc = shadow_doc(D13, "OLDX", "bull_flag", _et(D13, 11, 0), trigger=4.0, stop=3.8, price=3.9)
    doc["trigger"] = None
    st = fake_store(**{ST.ALERTS: FakeColl([doc])})
    p = TP.entry_tape(OLD_ID, now=MON_NIGHT, store=st, load_day=lambda s, d: _flat(d, 3.9))
    assert p["hlines"] == [] and p["dots"] == [] and p["tone"] is None and p["bars"]


def test_F9_a_split_on_file_draws_no_levels_and_no_dots_and_says_so():
    st = xlab15_store()
    doc = st.ledger_docs([D15])[0]
    nxt = dict(LG._blank("next"), reason="split", split_on="2026-10-16", version=GC.LEDGER_GRADE_VERSION)
    st.upsert_ledger(XLAB15_ID, {"next": nxt, "same": doc["same"]})
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load15())
    assert p["hlines"] == [] and p["dots"] == [] and p["note"] == TP.ENTRY_TAPE_WORDS["split"]
    assert TP.ENTRY_TAPE_WORDS["split"] == ("A split is on file after this alert — the bars are adjusted, the alert's "
                                            "levels are as printed; the levels are not drawn.")
    assert p["bars"] and "split" in p["read"]
    TP._MEMO.clear()
    clean = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=xlab15_store(), load_day=load15())
    assert clean["hlines"] and clean["dots"] and clean["note"] is None              # control: no split, lines drawn


def test_NEGATIVE_every_served_string_is_clean():
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    payloads = [TP.entry_tape(XLAB15_ID, now=NOW, store=xlab15_store(), load_day=load15(), today_bars=today_real()),
                TP.entry_tape(XLAB15_ID, lite=True, now=MON_NIGHT, store=xlab15_store(stop_out=True)),
                TP.fault_payload(OLD_ID), TP.views_block(),
                TP.entry_tape(OLD_ID, now=MON_NIGHT, store=old_store(), load_day=Rec(exc=RuntimeError("x")))]
    for p in payloads:
        json.dumps(p, allow_nan=False)
        for s in _walk_strings(p):
            low = s.lower()
            assert s not in ("None", "nan", "NaN", "undefined", "null"), s
            assert "None" not in s.split() and "NaN" not in s and "undefined" not in low and "nan" not in low.split(), s
            assert not B_WORD.search(s) and "fake" not in low and not NAMES.search(s), s
            assert not [w for w in FORBIDDEN_WORDS if w in low], s
    for w in TP.ENTRY_TAPE_WORDS.values():
        assert not B_WORD.search(w) and not NAMES.search(w) and not [x for x in FORBIDDEN_WORDS if x in w.lower()]


# ── 9. the ET stamp and the 5-minute bars ────────────────────────────────────────────────────────────────────────
def test_stamp_is_promotagtapes_etstamp():
    assert TP._stamp(int(datetime(2026, 9, 2, 13, 0, tzinfo=UTC).timestamp() * 1000)) == "Sep 2 · 9:00a ET"
    assert TP._stamp(ms(_et(D15, 16, 0))) == "Oct 15 · 4:00p ET" and TP._stamp(ms(_et(D15, 0, 5))) == "Oct 15 · 12:05a ET"


def test_bars5_labels_the_right_edge_and_tags_the_session():
    bars = [(_et(D15, 9, 25 + i).astimezone(UTC), 1.0 + i, 2.0 + i, 0.5, 1.5 + i) for i in range(15)]
    df = frame(bars).drop(columns=["session"])
    out = TP.bars5(df)
    assert [b["t"] for b in out] == [ms(_et(D15, 9, 30)), ms(_et(D15, 9, 35)), ms(_et(D15, 9, 40))]
    assert [b["s"] for b in out] == ["premarket", "rth", "rth"]
    b35 = out[1]                                                    # 09:35 holds 09:30–09:34
    assert (b35["o"], b35["h"], b35["l"], b35["c"], b35["v"]) == (6.0, 11.0, 0.5, 10.5, 5000.0)
    no_vol = TP.bars5(TP._frame_of(bars))
    assert all(b["v"] is None for b in no_vol) and [b["t"] for b in no_vol] == [b["t"] for b in out]
    assert TP.bars5(None) == [] and TP.bars5(pd.DataFrame()) == []
    assert f"{GC.LEDGER_TAPE_TF_MIN}min" in inspect.getsource(PROMO.bars_for)       # the Promo tape's own frame


def test_parse_id_reads_only_an_aplus_ledger_id():
    assert TP.parse_id(XLAB15_ID) == (D15, "XLAB", "intraday_vcp")
    for bad in ("2026-10-15|XLAB|intraday_vcp|potential", "2026-10-15|XLAB|intraday_vcp", "GG:2026-10-15|XLAB|x",
                None, 5, "", "2026-10-15||intraday_vcp|aplus", "2026-10-15|XLAB| |aplus", "x|XLAB|intraday_vcp|aplus"):
        assert TP.parse_id(bad) is None, bad


# ── 10. the served view block ────────────────────────────────────────────────────────────────────────────────────
def test_views_block_is_the_frozen_dict_and_the_track_record_serves_it():
    want = {"param": "view", "default": "all",
            "items": [{"key": "all", "label": "📋 all alerts"}, {"key": "timeline", "label": "🕰️ entries timeline"}],
            "kinds": ["aplus"], "empty_text": "No A+ entry in this span — the 🧠 alerts are under 📋 all alerts.",
            "tape_head": "Tape", "tape_toggle": "📈",
            "tape_toggle_title": "the full tape — the alert, the fill, the trigger / stop / +1R"}
    assert TP.views_block() == want
    st = ledger_store()
    for span in GC.LEDGER_SPANS:
        assert board(st, span)["track_record"]["views"] == want, span


# ── the source: one engine, no second fetch, no typed numbers ───────────────────────────────────────────────────
def test_NEGATIVE_the_tape_source_keeps_the_cost_rules():
    src = Path(TP.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = "\n".join(ln.split("#", 1)[0] for ln in code.splitlines())
    assert "force=True" not in code and "_today_load(" not in code and "LG.today_bars" in code
    assert "stride=PROMO.LITE_STRIDE" in code and not re.search(r"%\s*3\b|::3\b|\"5min\"|'5min'", code)
    assert not re.search(r"^\s*(from|import)\s+scripts\b", src, re.M)
    assert not B_WORD.search(src) and "fake" not in src.lower()
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not [m for m in mods if m and m.startswith("scripts")]


def test_live_entry_rows_draw_the_same_way_as_shadow_rows():
    """A pushed `GG:` A+ claim (line live) is served exactly like a shadow row — the kind is aplus either way."""
    doc = live_entry_doc(D15, "XLAB", "intraday_vcp", _et(D15, 15, 11), trigger=1.22, stop=1.16, price=1.20)
    st = fake_store(**{ST.ALERTS: FakeColl([doc])})
    LG.grade_step(st, _et(D15, 20, 15, 30), load_day=tape_loader(), split_lookup=lambda *a: False)
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load15())
    assert [d["label"] for d in p["dots"]] == ["fill 1.22 at 15:21", "+1R 15:22"]


# ── FIX ROUND 1 (critic A): the exit column, the split on file, the provider failure, the empty-volume bucket ─────
def _tuples(day, spec):
    return [(_et(day, h, mi).astimezone(UTC), o, hi, lo, c) for (h, mi, o, hi, lo, c) in spec]


def _ovn_store(d16_spec):
    """A SHADOW A+ OVN 10-15 15:50 row (SYNTHETIC plan 2.00 / 1.90): filled 2.00 at 15:51, still OPEN at the 16:00
    close; the next session decides it on `d16_spec`. Graded by the REAL nightly step of 10-16."""
    doc = shadow_doc(D15, "OVN", "bull_flag", _et(D15, 15, 50), trigger=2.00, stop=1.90, price=1.98)
    st = fake_store(**{ST.ALERTS: FakeColl([doc])})
    d15 = _tuples(D15, [(15, 50, 1.98, 1.99, 1.97, 1.98), (15, 51, 1.99, 2.01, 1.98, 2.00)]
                  + [(15, mi, 2.0, 2.02, 1.97, 2.0) for mi in range(52, 60)])
    d16 = _tuples(D16, d16_spec)

    def ld(s, d):
        return d15 if d == D15 else d16 if d == D16 else None
    LG.grade_step(st, _et(D16, 20, 15, 30), load_day=lambda s, d: (ld(s, d), False), split_lookup=lambda *a: False)
    return st, ld, "2026-10-15|OVN|bull_flag|aplus"


def test_a_same_open_next_win_puts_the_exit_dot_on_the_next_sessions_target():
    st, ld, rid = _ovn_store([(9, 30, 2.0, 2.05, 1.98, 2.04), (9, 50, 2.05, 2.20, 2.04, 2.15)])
    doc = st.ledger_docs([D15])[0]
    assert doc["same"]["outcome"] == "open" and doc["next"]["outcome"] == "win"
    p = TP.entry_tape(rid, now=MON_NIGHT, store=st, load_day=ld)
    assert [x["key"] for x in p["dots"]] == ["fill", "exit"]
    ex = p["dots"][-1]
    assert (ex["px"], ex["tone"], ex["label"]) == (doc["next"]["target_px"], "target", "+1R Fri 09:50")
    assert ex["at"] == doc["next"]["exit_t"] and p["dots"][0]["label"] == "fill 2.00 at 15:51"   # the fill stays same's
    assert "WIN" in p["read"]


def test_NEGATIVE_a_same_open_next_still_open_has_no_exit_dot():
    st, ld, rid = _ovn_store([(9, 30, 2.0, 2.05, 1.98, 2.04)] + [(9, mi, 2.0, 2.05, 1.95, 2.0) for mi in range(31, 60)])
    doc = st.ledger_docs([D15])[0]
    assert doc["same"]["outcome"] == "open" and doc["next"]["outcome"] not in LG.DECIDED
    p = TP.entry_tape(rid, now=MON_NIGHT, store=st, load_day=ld)
    assert [x["key"] for x in p["dots"]] == ["fill"]


def test_F9_a_decided_column_copied_across_a_split_split_on_draws_no_levels():
    st = xlab15_store()
    doc = st.ledger_docs([D15])[0]
    nxt = dict(doc["same"], horizon="next", split_on="2026-10-16", best_through="same")
    st.upsert_ledger(XLAB15_ID, {"same": doc["same"], "next": nxt})
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load15())
    assert p["hlines"] == [] and p["dots"] == [] and p["note"] == TP.ENTRY_TAPE_WORDS["split"] and p["bars"]


def test_NEGATIVE_a_copy_with_an_unread_split_check_is_not_a_split_on_file():
    st = xlab15_store()
    doc = st.ledger_docs([D15])[0]
    nxt = dict(doc["same"], horizon="next", split_unchecked=True, best_through="same")
    st.upsert_ledger(XLAB15_ID, {"same": doc["same"], "next": nxt})
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load15())
    assert p["hlines"] and p["dots"] and p["note"] is None


def _failing_loader(failed: bool):
    def load(sym, day, **k):
        dt_data._LAST_FETCH.failed = failed
        return None
    return load


def test_NEGATIVE_a_provider_failure_on_a_completed_day_is_the_fault_note_never_memoised(monkeypatch):
    monkeypatch.setattr(dt_data, "load_intraday", _failing_loader(True))
    p = TP.entry_tape(OLD_ID, now=MON_NIGHT, store=old_store())
    assert p["bars"] == [] and p["note"] == TP.ENTRY_TAPE_WORDS["fault"] and TP._MEMO == {}


def test_an_empty_answer_without_the_failed_flag_is_no_bars_not_a_fault(monkeypatch):
    dt_data._LAST_FETCH.failed = True                                              # stale flag: cleared first
    monkeypatch.setattr(dt_data, "load_intraday", _failing_loader(False))
    p = TP.entry_tape(OLD_ID, now=MON_NIGHT, store=old_store())
    assert p["bars"] == [] and p["note"] == "No 5-minute bars on file for OLDX on 2026-10-13 yet."


def test_bars5_a_bucket_with_no_printed_volume_is_None_never_zero():
    a = [(_et(D15, 9, 30 + i).astimezone(UTC), 1.0, 1.1, 0.9, 1.0) for i in range(5)]
    b = [(_et(D15, 9, 35 + i).astimezone(UTC), 1.0, 1.1, 0.9, 1.0) for i in range(5)]
    mixed = frame(a, vol=100.0).drop(columns=["session"])
    mixed.iloc[1, mixed.columns.get_loc("volume")] = float("nan")                  # one NaN minute in a printed bucket
    out = TP.bars5(pd.concat([mixed, TP._frame_of(b)]))
    assert [x["v"] for x in out] == [400.0, None]


def test_today_tuples_joined_to_a_completed_day_serve_v_None():
    st = xlab15_store()
    p = TP.entry_tape(XLAB15_ID, now=NOW, store=st, load_day=lambda s, d: frame(_xlab_15_synthetic()) if d == D15
                      else None, today_bars=today_real())
    today = [x for x in p["bars"] if x["t"] > ms(_et(D16, 0, 0))]
    old = [x for x in p["bars"] if x["t"] < ms(_et(D16, 0, 0))]
    assert today and {x["v"] for x in today} == {None} and all(isinstance(x["v"], float) for x in old)


# ── FIX ROUND 2 (critic A): yesterday's after-close row and today_read's split check (E1); split tone; split memo ──
AH_ID = "2026-10-15|XLAB|intraday_vcp|aplus"


def _ah_store():
    """A SHADOW A+ XLAB row at 10-15 16:05 ET (after the close: its same session is 10-16, graded on today's bars)."""
    doc = shadow_doc(D15, "XLAB", "intraday_vcp", _et(D15, 16, 5), trigger=1.85, stop=1.75, price=1.80)
    return fake_store(**{ST.ALERTS: FakeColl([doc])})


def _read_of(row):
    h = dict(LG.HEADS)
    return TP._w("read", same_head=h["same"], same=_txt(row["same"]), next_head=h["next"], next=_txt(row["next"]))


def _ah_load(s, d):
    return frame(_xlab_15_synthetic()) if d == D15 else None


def test_E1_NEGATIVE_a_split_held_after_close_row_is_never_graded_on_the_tape_and_reads_the_track_records_cells(
        monkeypatch):
    monkeypatch.setattr(LG, "_today_load", lambda s, d: (_real_tape(), False))
    st = _ah_store()
    today = LG.today_read(NOW, span="5d", store=st, split_lookup=lambda *a: "2026-10-16")
    assert today["stats"]["split_held"] == 1
    row = _served_row(st, AH_ID, NOW, today=today)
    p = TP.entry_tape(AH_ID, now=NOW, store=st, load_day=_ah_load)
    assert p["read"] == _read_of(row)
    assert "WIN" not in p["read"] and "not final" not in p["read"]
    assert p["dots"] == [] and p["hlines"] == [] and p["tone"] is None
    assert p["note"] == TP.ENTRY_TAPE_WORDS["split"] and p["bars"]
    assert [r["key"] for r in p["rules"]] == ["alert"]                               # no fill rule either


def test_E1_NEGATIVE_an_unread_split_check_grades_nothing_and_draws_no_split_note(monkeypatch):
    monkeypatch.setattr(LG, "_today_load", lambda s, d: (_real_tape(), False))
    st = _ah_store()
    held = _served_row(st, AH_ID, NOW,
                       today=LG.today_read(NOW, span="5d", store=st, split_lookup=lambda *a: "2026-10-16"))
    LG._TODAY_SPLIT.clear()                                                          # today_read never asked
    p = TP.entry_tape(AH_ID, now=NOW, store=st, load_day=_ah_load)
    assert p["read"] == _read_of(held) and p["dots"] == []
    assert p["note"] is None and [h["key"] for h in p["hlines"]] == ["trigger", "stop"]


def test_E1_control_a_no_split_answer_grades_the_same_provisional_win_as_the_track_record(monkeypatch):
    monkeypatch.setattr(LG, "_today_load", lambda s, d: (_real_tape(), False))
    st = _ah_store()
    today = LG.today_read(NOW, span="5d", store=st, split_lookup=no_split)
    assert today["stats"]["split_held"] == 0
    row = _served_row(st, AH_ID, NOW, today=today)
    p = TP.entry_tape(AH_ID, now=NOW, store=st, load_day=_ah_load)
    assert p["read"] == _read_of(row) and "WIN" in p["read"] and "not final" in p["read"]
    assert [x["key"] for x in p["dots"]] == ["fill", "exit"] and p["note"] is None and p["tone"] in ("up", "dn")


def test_E1_the_split_check_is_read_from_the_memo_never_fetched_by_the_tape(monkeypatch):
    monkeypatch.setattr(LG, "_today_load", lambda s, d: (_real_tape(), False))
    monkeypatch.setattr(LG, "_default_split_lookup", Rec(exc=AssertionError("the tape asked for a split check")))
    p = TP.entry_tape(AH_ID, now=NOW, store=_ah_store(), load_day=_ah_load)
    assert p["dots"] == [] and "WIN" not in p["read"]


def test_F9_NEGATIVE_a_split_on_file_has_no_tone():
    st = xlab15_store()
    doc = st.ledger_docs([D15])[0]
    nxt = dict(LG._blank("next"), reason="split", split_on="2026-10-16", version=GC.LEDGER_GRADE_VERSION)
    st.upsert_ledger(XLAB15_ID, {"next": nxt, "same": doc["same"]})
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load15())
    assert p["note"] == TP.ENTRY_TAPE_WORDS["split"] and p["bars"] and p["tone"] is None
    TP._MEMO.clear()
    assert TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=xlab15_store(), load_day=load15())["tone"] in ("up", "dn")


def test_NEGATIVE_a_split_note_over_a_failed_day_load_is_never_memoised():
    st = xlab15_store()
    doc = st.ledger_docs([D15])[0]
    nxt = dict(LG._blank("next"), reason="split", split_on="2026-10-16", version=GC.LEDGER_GRADE_VERSION)
    st.upsert_ledger(XLAB15_ID, {"next": nxt, "same": doc["same"]})

    def load(sym, day):
        if day == D16:
            raise RuntimeError("provider down")
        return load15()(sym, day)
    p = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load)
    assert p["note"] == TP.ENTRY_TAPE_WORDS["split"] and TP._MEMO == {}
    TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=st, load_day=load15())          # control: a whole read memoises
    assert set(TP._MEMO) == {(XLAB15_ID, "full"), (XLAB15_ID, "lite")}


def test_NEGATIVE_a_split_note_over_a_failed_today_read_is_never_memoised(monkeypatch):
    monkeypatch.setattr(LG, "_today_load", lambda s, d: (_real_tape(), False))
    st = _ah_store()
    LG.today_read(NOW, span="5d", store=st, split_lookup=lambda *a: "2026-10-16")
    LG._TODAY_MEMO.clear()                                                           # the lite mini: memo only, empty
    p = TP.entry_tape(AH_ID, lite=True, now=NOW, store=st, load_day=_ah_load)
    assert p["note"] == TP.ENTRY_TAPE_WORDS["split"] and TP._MEMO == {}
