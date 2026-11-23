"""📐 Daily supply & demand zones on the 👀 Watch (spec vwapzones §3.6, WP be-zones, 2026-11-23).

Ajay 2026-11-23, verbatim: "can you add vwap and supply demand zone in the daily time frame on the watch list please"
· "Add vwap and supply demand too".

Pins: the ONE engine (zone_store.build_doc / price_zones.compute + zone_geom) and its own N-nearest cut; the served
band shape (six keys, the two BOARD kinds, `ctx`); [C3] a lo == hi band kept and printed as ONE price; [C5] the fresh
read (use_cache=False, period = C.ZONES_PERIOD = zone_store / index_zones' loader period) and the NOT-latched retry
behind never-read names inside the cap; warm order / cap / serial / no upsert; [C4] the swing-window sentence and the
engine fact behind it; for_card never waits on a provider (single-flight + memo + slot rule); the coverage script's
inline `near` == levels.near. NEGATIVES throughout.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import levels as LV
from scripts import gajjala_watch_levels_coverage as COV
from supply_demand import index_zones, price_zones as PZ, zone_store as ZS
from supply_demand.demand_reentry import zone_geom
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
SESSION = "2026-11-20"                                    # a Friday market day
DAY = date(2026, 11, 20)
NOW = datetime(2026, 11, 20, 10, 2, tzinfo=ET)            # inside the window
ROOT = Path(__file__).resolve().parents[2]
SRC = Path(LV.__file__).read_text()


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    LV._reset_card_state()
    yield
    LV._reset_card_state()


def daily(n=300, end=date(2026, 11, 19), base=10.0, amp=2.0, today=False):
    """A deterministic closed daily frame (business days ending `end`) with swings; `today` adds a row on SESSION."""
    idx = list(pd.bdate_range(end=pd.Timestamp(end), periods=n))
    if today:
        idx.append(pd.Timestamp(DAY))
    i = np.arange(len(idx))
    close = base + amp * np.sin(i / 7.0) + 0.004 * i
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                         "volume": 1_000_000 + 10 * i}, index=pd.DatetimeIndex(idx))


def _db(symbols, tiles=()):
    return {C.COLL_LIST: FakeColl([{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}]),
            C.COLL_TILES: FakeColl(list(tiles)), C.COLL_ALERTS: FakeColl([]), C.COLL_STATE: FakeColl([])}


def _tile(sym, levels=None, session=SESSION, close=10.0):
    d = {"_id": sym, "symbol": sym, "session": session, "status": "loaded",
         "frames": {"1m": {"tf": "1m", "bars": [{"t": f"{session} 10:01", "o": close, "h": close, "l": close,
                                                  "c": close, "v": 1}]}}}
    if levels is not None:
        d["levels"] = levels
    return d


class Loader:
    """The daily loader's signature (sym, *, now); records calls and the max concurrency. `frames`: {sym: df | None |
    Exception}."""

    def __init__(self, frames=None, default="frame"):
        self.frames, self.default, self.calls, self.threads = dict(frames or {}), default, [], []
        self.live = self.max_live = 0
        self.lock = threading.Lock()

    def __call__(self, sym, *, now):
        with self.lock:
            self.live += 1
            self.max_live = max(self.max_live, self.live)
        try:
            self.calls.append((sym, now))
            self.threads.append(threading.get_ident())
            v = self.frames.get(sym, daily() if self.default == "frame" else None)
            if isinstance(v, Exception):
                raise v
            return v
        finally:
            with self.lock:
                self.live -= 1


def _strict(obj):
    return json.loads(json.dumps(obj, allow_nan=False, default=str))


# ── the ONE engine ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_stored_bands_are_build_doc_bands_and_near_is_the_engines_own_cut():
    F = daily()
    doc = LV.levels_doc("ABC", F, SESSION, NOW)
    ref = ZS.build_doc("ABC", F, DAY)
    assert doc["state"] == "ok" and doc["bands"] == ref["bands"] and doc["geom"] == ZS.GEOM_TAG
    assert doc["through"] == "2026-11-19" and doc["n_bars"] == len(F) and doc["prev_close"] == ref["prev_close"]
    closed = ZS.drop_today(F, DAY)
    for P in (8.5, 10.0, 11.3, 12.9, float(closed["close"].iloc[-1])):
        z = PZ.compute(closed, last_price=P, **zone_geom())
        got = LV.near(doc["bands"], P)
        for kind, key in (("demand", "demand_zones"), ("supply", "supply_zones")):
            assert [(b["lo"], b["hi"]) for b in got if b["kind"] == kind] == [(b["lo"], b["hi"]) for b in z[key]], P


def test_NEGATIVE_a_row_dated_on_the_session_never_counts():
    a = LV.levels_doc("ABC", daily(), SESSION, NOW)
    b = LV.levels_doc("ABC", daily(today=True), SESSION, NOW)
    assert {k: v for k, v in a.items() if k != "at"} == {k: v for k, v in b.items() if k != "at"}


def _bands(kind, n, start, step=1.0, width=0.2):
    return [{"kind": kind, "lo": round(start + i * step, 4), "hi": round(start + i * step + width, 4),
             "touches": 2, "strength": 0.5, "pad_lo": 1.0} for i in range(n)]


def test_NEGATIVE_the_fifth_nearest_is_not_served_the_band_price_is_in_always_is():
    bands = _bands("demand", 6, 1.0) + _bands("supply", 6, 7.5)
    lv = {"session": SESSION, "state": "ok", "bands": bands, "prev_close": 5.0, "through": "2026-11-19"}
    P = 3.1                                                   # inside demand 3.0–3.2
    blk = LV.block(lv, SESSION, P, "ABC", in_window=True, now=NOW)
    served = blk["bands"]
    assert sum(1 for b in served if b["kind"] == "board_demand") == PZ.MAX_ZONES_PER_SIDE
    assert sum(1 for b in served if b["kind"] == "board_supply") == PZ.MAX_ZONES_PER_SIDE
    assert any(b["lo"] <= P <= b["hi"] for b in served)
    assert (6.0, 6.2) not in {(b["lo"], b["hi"]) for b in served}       # the 5th-nearest demand band: cut
    assert {b["kind"] for b in served} <= set(C.ZONE_BAND_KIND.values())
    for b in served:
        assert tuple(b) == LV.BAND_KEYS and "pad_lo" not in b and b["ctx"] is True
    assert [b["hi"] for b in served] == sorted((b["hi"] for b in served), reverse=True)
    ts = (ROOT / "frontend" / "src" / "lib" / "chartMaps.ts").read_text()
    m = re.search(r"export type CmBand\s*=\s*\{\s*kind:\s*([^;]+);", ts, re.S)
    assert m and all(f"'{k}'" in m.group(1) for k in C.ZONE_BAND_KIND.values())     # [C9] both in the CmBand union


def test_per_side_count_follows_the_constant(monkeypatch):
    bands = _bands("demand", 6, 1.0)
    monkeypatch.setattr(C, "ZONES_PER_SIDE", 2)
    assert len(LV.near(bands, 3.1)) == 2
    monkeypatch.setattr(C, "ZONES_PER_SIDE", None)
    monkeypatch.setattr(PZ, "MAX_ZONES_PER_SIDE", 3)
    assert len(LV.near(bands, 3.1)) == 3


# ── [C5] the fresh read ────────────────────────────────────────────────────────────────────────────────────────────
def test_default_loader_is_the_fresh_closed_daily_read(monkeypatch):
    from sepa import prices
    seen = {}

    def spy(sym, **kw):
        seen.update(kw, sym=sym)
        return None
    monkeypatch.setattr(prices, "closed_daily_frame", spy)
    LV.default_loader("ABC", now=datetime(2026, 11, 20))
    assert seen == {"sym": "ABC", "now": datetime(2026, 11, 20), "period": C.ZONES_PERIOD, "use_cache": False}


def test_zones_period_equals_the_zone_store_and_index_zones_loader_periods():
    zs = inspect.getsource(ZS.warm)
    m = re.search(r'load_prices\(sym, period="([^"]+)"\)', zs)
    assert m and m.group(1) == C.ZONES_PERIOD
    iz = Path(index_zones.__file__).read_text()
    m = re.search(r'closed_daily_frame\(sym, now=now, period="([^"]+)", use_cache=False\)', iz)
    assert m and m.group(1) == C.ZONES_PERIOD


def test_retry_is_not_latched_and_is_read_again_behind_a_never_read_name(monkeypatch):
    db = _db(["AAA", "BBB", "CCC"], [_tile("AAA"), _tile("BBB"), _tile("CCC")])
    ld = Loader({"AAA": None})
    out = LV.warm(NOW, db=db, loader=ld, cap=2)
    assert out["read"] == ["AAA", "BBB"] and out["retry"] == 1 and out["ok"] == 1
    lv = db[C.COLL_TILES].docs["AAA"]["levels"]
    assert lv["state"] == "retry" and lv["tries"] == 1 and lv["why"] == "no_daily" and lv["session"] == SESSION
    blk = LV.block(lv, SESSION, 10.0, "AAA", in_window=True, now=NOW)
    assert blk["state"] == "retry" and blk["bands"] == []
    assert blk["text"] == LV.LEVELS_RETRY_TEXT.format(sym="AAA", n=1, at=NOW.strftime("%H:%M"))
    assert "no daily bars on file" not in json.dumps(_strict(blk)) + SRC
    out2 = LV.warm(NOW, db=db, loader=ld, cap=2)                 # CCC never read → first; AAA again behind it
    assert out2["read"] == ["CCC", "AAA"]
    assert db[C.COLL_TILES].docs["AAA"]["levels"]["tries"] == 2
    ld.frames["AAA"] = daily()                                    # a later good frame → ok
    out3 = LV.warm(NOW, db=db, loader=ld, cap=2)
    assert out3["read"] == ["AAA"] and db[C.COLL_TILES].docs["AAA"]["levels"]["state"] == "ok"
    out4 = LV.warm(NOW, db=db, loader=ld, cap=2)                  # NEGATIVE: ok is never re-read in the session
    assert out4["read"] == []


def test_NEGATIVE_cap_counts_retries_and_new_reads_together_and_first_is_uncapped():
    syms = [f"N{i}" for i in range(12)]
    tiles = [_tile(s) for s in syms]
    for t in tiles[:6]:
        t["levels"] = {"session": SESSION, "state": "retry", "why": "no_daily", "tries": 3, "at": NOW}
    db = _db(syms, tiles)
    ld = Loader()
    out = LV.warm(NOW, db=db, loader=ld, first=["N11", "N10"])
    nonfirst = [s for s in out["read"] if s not in ("N11", "N10")]
    assert out["read"][:2] == ["N11", "N10"] and len(nonfirst) == C.ZONES_MAX_NEW
    assert nonfirst[:4] == ["N6", "N7", "N8", "N9"]               # never-read names first, then retries
    db2 = _db(syms, [_tile(s) for s in syms])
    out = LV.warm(NOW, db=db2, loader=Loader(), first=syms)      # first: uncapped, each once
    assert out["read"] == syms


def test_NEGATIVE_short_and_none_are_latched_and_short_names_the_constant(monkeypatch):
    db = _db(["SHO", "NON"], [_tile("SHO"), _tile("NON")])
    rising = daily()
    up = np.linspace(5.0, 50.0, len(rising))                      # strictly rising → no swing → engine finds none
    rising["open"], rising["close"], rising["high"], rising["low"] = up, up, up * 1.001, up * 0.999
    ld = Loader({"SHO": daily(n=50), "NON": rising})
    LV.warm(NOW, db=db, loader=ld)
    sho, non = db[C.COLL_TILES].docs["SHO"]["levels"], db[C.COLL_TILES].docs["NON"]["levels"]
    assert (sho["state"], sho["why"], sho["n_bars"]) == ("none", "short", 50)
    assert (non["state"], non["why"]) == ("none", "none")
    assert LV.warm(NOW, db=db, loader=ld)["read"] == [] and len(ld.calls) == 2
    blk = LV.block(sho, SESSION, 10.0, "SHO", in_window=True, now=NOW)
    assert blk["text"] == LV.LEVELS_SHORT_TEXT.format(n=50, sym="SHO", min=ZS.MIN_BARS) and str(ZS.MIN_BARS) in blk["text"]
    monkeypatch.setattr(ZS, "MIN_BARS", 40)
    assert "needs 40" in LV.block(sho, SESSION, 10.0, "SHO", in_window=True, now=NOW)["text"]
    assert LV.levels_doc("SHO", daily(n=50), SESSION, NOW).get("why") != "short"   # the floor is read by name


# ── warm ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_warm_rest_false_reads_only_first_and_never_upserts_a_missing_tile():
    db = _db(["AAA", "BBB"], [_tile("AAA"), _tile("BBB")])
    ld = Loader()
    out = LV.warm(NOW, db=db, loader=ld, first=["BBB", "ZZZ"], rest=False)
    assert out["read"] == ["BBB"] and [c[0] for c in ld.calls] == ["BBB"]
    assert "ZZZ" not in db[C.COLL_TILES].docs and "levels" not in db[C.COLL_TILES].docs["AAA"]
    assert ld.calls[0][1] == datetime(2026, 11, 20)              # the session date 00:00, naive = ET


def test_NEGATIVE_a_raising_loader_is_a_retry_and_reads_are_serial():
    db = _db(["AAA", "BBB", "CCC"], [_tile("AAA"), _tile("BBB"), _tile("CCC")])
    ld = Loader({"BBB": RuntimeError("429")})
    out = LV.warm(NOW, db=db, loader=ld)
    assert out["read"] == ["AAA", "BBB", "CCC"] and ld.max_live == 1
    assert db[C.COLL_TILES].docs["BBB"]["levels"]["state"] == "retry"


def test_NEGATIVE_no_store_no_loader_call_and_off_reads_nothing(monkeypatch):
    ld = Loader()
    monkeypatch.setattr(LV.CO, "colls", lambda db=None: None)
    assert LV.warm(NOW, loader=ld) == {"reason": "no_store", "read": []} and ld.calls == []
    monkeypatch.setattr(C, "ZONES_ON", False)
    assert LV.warm(NOW, db=_db(["AAA"], [_tile("AAA")]), loader=ld)["read"] == [] and ld.calls == []


def test_NEGATIVE_source_never_names_the_zone_store_collection_or_upsert():
    assert "upsert=" not in SRC and "ZS.COLL" not in SRC and "zone_store.COLL" not in SRC
    assert "insert_" not in SRC and "replace_one" not in SRC and "bounce" not in SRC.lower()
    assert SRC.count(".update_one(") == 1


def test_spawn_runs_warm_on_a_daemon_thread(monkeypatch):
    seen = []
    monkeypatch.setattr(LV, "warm", lambda now=None, **k: seen.append(now))
    t = LV.spawn(NOW)
    t.join(2)
    assert t.daemon and seen == [NOW]
    monkeypatch.setattr(LV, "warm", lambda now=None, **k: (_ for _ in ()).throw(RuntimeError("x")))
    t = LV.spawn(NOW)
    t.join(2)
    assert not t.is_alive()                                        # a raising warm never escapes


# ── block / blocks ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_another_sessions_levels_are_pending_with_both_window_words():
    lv = LV.levels_doc("ABC", daily(), "2026-11-19", NOW)
    on = LV.block(lv, SESSION, 10.0, "ABC", in_window=True, now=NOW)
    off = LV.block(lv, SESSION, 10.0, "ABC", in_window=False, now=NOW)
    assert on["state"] == off["state"] == "pending" and on["bands"] == off["bands"] == []
    assert on["text"] == LV.LEVELS_PENDING_TEXT[True].format(cap=C.ZONES_MAX_NEW, min=GC.PASS_CADENCE_SEC // 60,
                                                             sym="ABC", open=GC.PASS_OPEN_ET)
    assert off["text"] == LV.LEVELS_PENDING_TEXT[False].format(open=GC.PASS_OPEN_ET, cap=0, min=0, sym="ABC")
    assert str(C.ZONES_MAX_NEW) in on["text"] and GC.PASS_OPEN_ET in off["text"]
    assert LV.block(None, SESSION, 10.0, "ABC", in_window=True, now=NOW)["state"] == "pending"


def test_blocks_take_p_from_the_1m_last_close_and_drop_junk():
    bands = [{"kind": "demand", "lo": 9.0, "hi": 9.5}, {"kind": "supply", "lo": 11.0, "hi": 11.5},
             {"kind": "demand", "lo": float("nan"), "hi": 3.0}, {"kind": "supply", "lo": 14.0, "hi": 13.0},
             {"kind": "fvg", "lo": 1.0, "hi": 2.0}, {"kind": "demand", "lo": "x", "hi": 2.0}, "junk"]
    lv = {"session": SESSION, "state": "ok", "bands": bands, "prev_close": 20.0, "through": "2026-11-19"}
    tile = _tile("ABC", levels=lv, close=10.0)
    tile["frames"]["5m"] = {"bars": [{"t": "x", "c": 99.0}]}
    out = LV.blocks(["ABC", "NOPE"], {"ABC": tile}, SESSION, NOW, True)
    blk = out["ABC"]
    assert [(b["lo"], b["hi"]) for b in blk["bands"]] == [(11.0, 11.5), (9.0, 9.5)]
    assert "next below demand 9.00–9.50 (5.0% under)" in blk["text"]
    assert "next above supply 11.00–11.50 (10.0% over)" in blk["text"]
    assert blk["text"].startswith("📐 Daily zones (bars through 2026-11-19): ") and blk["as_of"] == "2026-11-19"
    assert out["NOPE"]["state"] == "pending"
    _strict(out)
    no_p = LV.block(lv, SESSION, None, "ABC", in_window=True, now=NOW)              # P None → prev_close 20.0
    assert "none above" in no_p["text"] and "next below supply" in no_p["text"]


def test_C3_a_zero_width_band_is_served_and_prints_one_price():
    lv = {"session": SESSION, "state": "ok", "through": "2026-11-19", "prev_close": 0.12,
          "bands": [{"kind": "demand", "lo": 0.12, "hi": 0.12, "touches": 1, "strength": 0.1}]}
    blk = LV.block(lv, SESSION, 0.12, "HXHX", in_window=True, now=NOW)
    assert len(blk["bands"]) == 1 and blk["bands"][0]["lo"] == blk["bands"][0]["hi"] == 0.12
    assert blk["bands"][0]["label"] == "Daily demand 0.12"
    assert "inside demand 0.12" in blk["text"] and "0.12–0.12" not in json.dumps(blk, ensure_ascii=False)
    _strict(blk)
    assert "bounce" not in json.dumps(blk).lower()


def test_none_states_words():
    for why, words in (("none", LV.LEVELS_EMPTY_TEXT), ("error", LV.LEVELS_ERROR_TEXT)):
        blk = LV.block({"session": SESSION, "state": "none", "why": why, "n_bars": 300}, SESSION, 1.0, "ABC",
                       in_window=True, now=NOW)
        assert blk["text"] == words.format(sym="ABC") and blk["bands"] == []


def test_NEGATIVE_zones_off_serves_nothing(monkeypatch):
    monkeypatch.setattr(C, "ZONES_ON", False)
    assert LV.blocks(["ABC"], {"ABC": _tile("ABC")}, SESSION, NOW, True) == {}
    assert LV.legend() == [] and LV.rules_line() == ""
    assert LV.for_card("ABC", SESSION, NOW, price=1.0, loader=Loader()) is None


def test_section_is_fail_soft(monkeypatch):
    monkeypatch.setattr(LV, "blocks", lambda *a, **k: 1 / 0)
    assert LV.section(["ABC"], {}, SESSION, NOW, True) == {}


# ── [C4] the words ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_C4_rules_line_carries_the_constants_by_name(monkeypatch):
    s = LV.rules_line()
    w = zone_geom()["swing_window"]
    assert f"last {w} closed sessions" in s and f"the {PZ.MAX_ZONES_PER_SIDE} nearest" in s
    assert f"fewer than {ZS.MIN_BARS} daily bars" in s and "UNMEASURED" in s and C.TAB_LABEL in s
    assert "bounce" not in s.lower()
    from supply_demand import demand_reentry as DR
    monkeypatch.setattr(DR, "SWING_WINDOW", 7)
    monkeypatch.setattr(C, "ZONES_PER_SIDE", 2)
    monkeypatch.setattr(ZS, "MIN_BARS", 99)
    s2 = LV.rules_line()
    assert "last 7 closed sessions" in s2 and "the 2 nearest" in s2 and "fewer than 99" in s2
    assert [e["title"] for e in LV.legend()] == [s2, s2] and [e["tone"] for e in LV.legend()] == ["zone_demand",
                                                                                                   "zone_supply"]


def test_rules_line_and_words_type_no_digit():
    tree = ast.parse(inspect.getsource(LV.rules_line))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            assert not isinstance(node.value, (int, float)), node.value
            if isinstance(node.value, str):
                assert not re.search(r"\d", node.value), node.value
    for name in ("RULES_TEXT", "LEVELS_TEXT", "LEVELS_IN_TEXT", "LEVELS_BELOW_TEXT", "LEVELS_ABOVE_TEXT",
                 "LEVELS_RETRY_TEXT", "LEVELS_SHORT_TEXT", "LEVELS_EMPTY_TEXT", "LEVELS_ERROR_TEXT",
                 "LEVELS_CARD_PENDING_TEXT", "ZONE_LABEL_TEXT"):
        assert not re.search(r"\d", getattr(LV, name)), name
    assert not any(re.search(r"\d", v) for v in LV.LEVELS_PENDING_TEXT.values())


def _spike(k: int, n: int = 200) -> tuple:
    idx = pd.bdate_range(end=pd.Timestamp(date(2026, 11, 19)), periods=n)
    i = np.arange(n)
    close = 10.0 + 0.3 * np.sin(i / 3.0)
    df = pd.DataFrame({"open": close, "high": close + 0.05, "low": close - 0.05, "close": close,
                       "volume": 1_000_000.0}, index=idx)
    df.iloc[n - k, df.columns.get_loc("high")] = 20.0              # k = 1 → the last closed session
    return df, 20.0


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 6])
def test_C4_a_high_of_the_last_swing_window_sessions_is_never_a_zone(k):
    w = zone_geom()["swing_window"]
    df, top = _spike(k)
    doc = LV.levels_doc("SPK", df, SESSION, NOW)
    at = [b for b in doc.get("bands") or [] if b["kind"] == "supply" and b["lo"] <= top <= b["hi"]]
    assert bool(at) is (k > w), k


# ── for_card: never waits on a provider ────────────────────────────────────────────────────────────────────────────
def test_for_card_serves_the_stored_watch_levels_with_no_loader_call():
    lv = LV.levels_doc("ABC", daily(), SESSION, NOW)
    ld = Loader()
    blk = LV.for_card("ABC", DAY, NOW, price=10.0, levels=lv, tile_session=SESSION, loader=ld)
    assert blk["state"] == "ok" and blk["bands"] and ld.calls == []


def test_for_card_miss_queues_once_and_never_reads_on_the_calling_thread():
    gate = threading.Event()

    class Slow(Loader):
        def __call__(self, sym, *, now):
            gate.wait(5)
            return super().__call__(sym, now=now)
    ld = Slow()
    me = threading.get_ident()
    blks = [LV.for_card("ABC", DAY, NOW, price=10.0, loader=ld) for _ in range(10)]
    assert all(b["state"] == "pending" and b["text"] == LV.LEVELS_CARD_PENDING_TEXT and b["bands"] == [] for b in blks)
    assert ld.calls == []
    gate.set()
    for _ in range(100):
        if ("2026-11-20", "ABC") in LV._MEMO:
            break
        time.sleep(0.02)
    assert len(ld.calls) == 1 and me not in ld.threads
    nxt = LV.for_card("ABC", DAY, NOW, price=10.0, loader=ld)
    assert nxt["state"] == "ok" and nxt["bands"] and len(ld.calls) == 1


def test_for_card_retry_is_reread_in_a_later_slot_only():
    ld = Loader({"ABC": None})
    run = lambda job: job()                                         # noqa: E731
    assert LV.for_card("ABC", DAY, NOW, price=10.0, loader=ld, run=run)["state"] == "pending"
    assert len(ld.calls) == 1
    same = NOW + timedelta(seconds=60)
    assert R1.slot_of(same)[0] == R1.slot_of(NOW)[0]
    assert LV.for_card("ABC", DAY, same, price=10.0, loader=ld, run=run)["state"] == "retry"
    assert len(ld.calls) == 1                                        # NEGATIVE: not inside the same slot
    later = R1.slot_of(NOW)[1] + timedelta(seconds=30)
    ld.frames["ABC"] = daily()
    assert LV.for_card("ABC", DAY, later, price=10.0, loader=ld, run=run)["state"] == "pending"
    assert len(ld.calls) == 2
    assert LV._MEMO[(SESSION, "ABC")]["doc"]["state"] == "ok"
    ok = LV.for_card("ABC", DAY, later + timedelta(days=0, seconds=600), price=10.0, loader=ld, run=run)
    assert ok["state"] == "ok" and len(ld.calls) == 2               # NEGATIVE: ok is never re-read in the session


def test_for_card_new_session_clears_the_memo():
    ld = Loader()
    run = lambda job: job()                                         # noqa: E731
    LV.for_card("ABC", DAY, NOW, price=10.0, loader=ld, run=run)
    assert LV.for_card("ABC", DAY, NOW, price=10.0, loader=ld, run=run)["state"] == "ok"
    nxt = date(2026, 11, 23)
    later = datetime(2026, 11, 23, 10, 0, tzinfo=ET)
    assert LV.for_card("ABC", nxt, later, price=10.0, loader=ld, run=run)["state"] == "pending"
    assert (SESSION, "ABC") not in LV._MEMO and len(ld.calls) == 2


def test_NEGATIVE_for_card_without_a_loader_serves_nothing_and_queues_nothing():
    assert LV.for_card("ABC", DAY, NOW, price=10.0) is None
    assert LV._INFLIGHT == set() and LV._MEMO == {}
    stale = LV.levels_doc("ABC", daily(), "2026-11-19", NOW)          # another session's stored levels
    assert LV.for_card("ABC", DAY, NOW, price=10.0, levels=stale, tile_session="2026-11-19") is None
    retry = {"session": SESSION, "state": "retry", "tries": 1, "at": NOW}
    assert LV.for_card("ABC", DAY, NOW, price=10.0, levels=retry, tile_session=SESSION) is None


def test_NEGATIVE_a_raising_loader_never_kills_the_worker():
    ld = Loader({"BAD": RuntimeError("down")})
    LV.for_card("BAD", DAY, NOW, price=10.0, loader=ld)
    LV.for_card("ABC", DAY, NOW, price=10.0, loader=ld)
    for _ in range(100):
        if ("2026-11-20", "ABC") in LV._MEMO and ("2026-11-20", "BAD") in LV._MEMO:
            break
        time.sleep(0.02)
    assert LV._MEMO[(SESSION, "BAD")]["doc"]["state"] == "retry"
    assert LV._MEMO[(SESSION, "ABC")]["doc"]["state"] == "ok" and LV._STATE["worker"].is_alive()


# ── the coverage script ────────────────────────────────────────────────────────────────────────────────────────────
def test_coverage_inline_near_equals_levels_near_and_reads_only_main_modules():
    doc = LV.levels_doc("ABC", daily(), SESSION, NOW)
    for P in (8.0, 10.0, 12.5, 0.5, 30.0):
        assert COV.near(doc["bands"], P, PZ.MAX_ZONES_PER_SIDE) == LV.near(doc["bands"], P)
    assert COV.ZONE_KINDS == C.ZONE_KINDS
    src = Path(COV.__file__).read_text()
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            mods |= {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
    main_only = {"__future__.annotations", "argparse", "json", "sys", "time", "datetime.date", "typing.Optional",
                 "supply_demand.price_zones", "supply_demand.zone_store", "chart_maps.gajjala_watch.colls",
                 "sepa.prices"}
    assert mods <= main_only, mods - main_only                     # never the new levels / constants names
    assert "C.ZONE" not in src and "LV." not in src
    assert not re.search(r"update_one|insert|upsert|replace_one|delete_|load_prices|closed_daily_frame|_fetch", src)
    assert src.count(".find(") == 1 and "bulk_cached_frames(" in src


def test_coverage_summarize_counts_a_zero_width_sub_dollar_band():
    F = daily(base=0.12, amp=0.0)
    F["high"] = 0.12
    F["low"] = 0.12
    docs = [{"_id": "HX", "session": SESSION,
             "frames": {"1m": {"bars": [{"h": 0.125, "l": 0.115, "c": 0.12}]}}},
            {"_id": "NC", "session": SESSION, "frames": {"1m": {"bars": [{"h": 2.0, "l": 1.0, "c": 1.5}]}}},
            {"_id": "NB", "session": SESSION}]
    t = COV.summarize(docs, {"HX": F})
    assert t["names"] == 3 and t["no_bars"] == 1 and t["not_cached"] == 1 and t["under_1"] == 1
    assert "| Read | Count |" in COV.table(t)


def test_coverage_widest_sub1_band_is_width_over_its_own_mid_not_the_name_price():
    far = {"kind": "supply", "lo": 0.40, "hi": 0.44}                # mid 0.42 → 9.5 %
    tight = {"kind": "demand", "lo": 0.10, "hi": 0.101}             # mid 0.1005 → 1.0 %
    assert COV.widest_sub1_pct([far, tight]) == 9.5
    assert COV.widest_sub1_pct([tight]) == 1.0
    assert COV.widest_sub1_pct([{"kind": "demand", "lo": 0.12, "hi": 0.12}]) == 0.0
    # NEGATIVES: a band whose mid is $1 or more never counts, however wide; zero / no bands → None
    assert COV.widest_sub1_pct([{"kind": "supply", "lo": 0.9, "hi": 3.0}]) is None
    assert COV.widest_sub1_pct([{"kind": "supply", "lo": 0.98, "hi": 1.02}, tight]) == 1.0
    assert COV.widest_sub1_pct([{"kind": "demand", "lo": 0.0, "hi": 0.0}]) is None
    assert COV.widest_sub1_pct([]) is None


def test_coverage_summarize_widest_sub1_pct_ignores_the_name_last_price(monkeypatch):
    from supply_demand import zone_store as ZS
    bands = [{"kind": "supply", "lo": 0.40, "hi": 0.44, "touches": 1},
             {"kind": "demand", "lo": 0.10, "hi": 0.101, "touches": 1}]
    monkeypatch.setattr(ZS, "build_doc", lambda sym, df, day: {"bands": [dict(b) for b in bands]})
    monkeypatch.setattr(ZS, "drop_today", lambda df, day: df)
    F = daily(base=0.12, amp=0.0)
    docs = [{"_id": "LOW", "session": SESSION,
             "frames": {"1m": {"bars": [{"h": 0.0011, "l": 0.0009, "c": 0.001}]}}}]
    t = COV.summarize(docs, {"LOW": F})
    assert t["ok"] == 1 and t["under_1"] == 1
    assert t["widest_sub1_pct"] == 9.5                               # the old "/ P" read gave 4000.0
    assert "| widest served sub-$1 band, % of its own mid | 9.5 % |" in COV.table(t)
    # NEGATIVE: a name above $1 carrying the same sub-$1 bands still reports them (band price, not the name's)
    docs2 = [{"_id": "HI", "session": SESSION, "frames": {"1m": {"bars": [{"h": 5.1, "l": 4.9, "c": 5.0}]}}}]
    t2 = COV.summarize(docs2, {"HI": F})
    assert t2["under_1"] == 0 and t2["widest_sub1_pct"] == 9.5
    monkeypatch.setattr(ZS, "build_doc", lambda sym, df, day: {"bands": [{"kind": "supply", "lo": 2.0, "hi": 9.0}]})
    assert COV.summarize(docs, {"LOW": F})["widest_sub1_pct"] is None


def test_levels_read_for_a_LATER_session_than_the_tile_say_waiting_not_in_line():
    for state in ("ok", "none"):
        out = LV.block({"session": "2026-11-23", "state": state}, "2026-11-20", 0.3, "HXHX", in_window=True,
                       now=None)
        assert out["state"] == "pending" and out["bands"] == []
        assert out["text"] == LV.LEVELS_WAITING_TEXT.format(sym="HXHX")
        assert "in line" not in out["text"]


def test_NEGATIVE_levels_for_an_EARLIER_session_stay_not_read_yet():
    out = LV.block({"session": "2026-11-19", "state": "ok"}, "2026-11-20", 0.3, "HXHX", in_window=True, now=None)
    assert out["text"] != LV.LEVELS_WAITING_TEXT.format(sym="HXHX") and out["bands"] == []
    retry = LV.block({"session": "2026-11-23", "state": "retry"}, "2026-11-20", 0.3, "HXHX", in_window=True,
                     now=None)
    assert retry["text"] != LV.LEVELS_WAITING_TEXT.format(sym="HXHX")
