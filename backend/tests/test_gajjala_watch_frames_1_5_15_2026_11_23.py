"""👀 Gajjala's Watch — frames 1 / 5 / 15, the served placeholders, the loop hooks (spec vwapzones rev 2, be-watch).

Ajay, verbatim (2026-11-23): "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board" ·
"Add vwap and supply demand too".

GOLDENS (step 0): the 1-min cross push (`XA.run` counts + the sent payload + the claim doc + `XA.compose`) and the served
1m + 5m frame blocks of one fixed doc were digested on main's code (7b618467) BEFORE any edit — they must stay
byte-equal. NEGATIVES are the point: no "3m" anywhere served, an old 1m/3m/5m doc never breaks the board, a 15-min cross
never rings, a `no_prints` name is fetched once per build child.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import logging
import math
import sys
import types
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import NOW, PREV, S, at, raw_day, stamp
from tests.test_gajjala_watch_run_bases_2026_11_15 import END as RB_END
from tests.test_gajjala_watch_run_bases_2026_11_15 import NOW as RB_NOW
from tests.test_gajjala_watch_run_bases_2026_11_15 import raw as rb_raw
from tests.test_gajjala_watch_run_bases_2026_11_15 import three_bases_price

OWNER = "owner@example.com"
GOLD_RULES = (("1m", "1min"), ("3m", "3min"), ("5m", "5min"), ("15m", "15min"))   # every tf main OR the new code reads
GOLD_PUSH_RULES = (("1m", "1min"), ("5m", "5min"))                                  # the frames both versions judge


def dig(o) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def gold_doc() -> dict:
    fr = B.build_frames("OMH", S, NOW, raw_day(PREV), raw_day(S, end=(10, 41), seed=3.0), rules=GOLD_RULES)
    _f, upd = BLD.tile_update("OMH", fr, S, NOW, "loaded")
    return upd["$set"]


def gold_bases_doc() -> dict:
    """The 📶 three-bases day (test_gajjala_watch_run_bases_2026_11_15) — its 5-min frame carries run_bases + ellipses."""
    fr = B.build_frames("OMH", S, RB_NOW, rb_raw(PREV, (20, 0), lambda ts: 10.0),
                        rb_raw(S, (RB_END[0], RB_END[1] + 1), three_bases_price), rules=GOLD_RULES)
    _f, upd = BLD.tile_update("OMH", fr, S, RB_NOW, "loaded")
    return upd["$set"]


def gold_blocks(doc=None, tfs=("1m", "5m")) -> dict:
    frames = (doc or gold_doc())["frames"]
    up = PL._latest_up_t(frames["1m"].get("ema_cross"))
    held = {"1m": {"bar_t": up, "reason": "under_floor"}} if up else None
    out = {}
    for tf in tfs:
        blk = PL.frame_block("OMH", tf, frames[tf], held)
        tile = blk["tile"]
        out[tf] = {"bars": tile["bars"], "curves": tile["curves"][:2], "markers": tile["markers"],
                   "vol_avg": tile["vol_avg"], "lines": tile["lines"], "axis": blk["axis"],
                   "ema_cross": blk["ema_cross"], "uptrend": blk["uptrend"], "held": blk["held"],
                   "ema_blink": blk["ema_blink"], "ema_tail": blk["ema_tail"], "run_bases": blk.get("run_bases"),
                   "ellipses": blk.get("ellipses")}
    return out


def gold_cross_frames():
    def price(ts):
        mm = ts.hour * 60 + ts.minute
        return 14.0 if mm >= 10 * 60 + 5 else 10.0 - 0.002 * (mm - 4 * 60)
    return B.build_frames("OMH", S, at(S, 10, 6, 30), raw_day(PREV, price=lambda ts: 10.0),
                          raw_day(S, end=(10, 7), price=price, volume=5000.0), rules=GOLD_PUSH_RULES)


def gold_xa() -> dict:
    coll, sent, held = FakeColl(), [], {}

    def send(owner, payload):
        sent.append((owner, payload))
        return {"sent": 1, "failed": 0, "total_targets": 1}
    counts = XA.run({"OMH": gold_cross_frames()}, at(S, 10, 6, 30), S, coll=coll, send=send, owner=OWNER,
                    seen=None, held=held)
    comp = XA.compose("omh", "1m", {"ts": stamp(S, 10, 6), "close": 14.0}, True, False)
    docs = {k: {f: v for f, v in d.items() if f != "claimed_at"} for k, d in coll.docs.items()}   # wall clock
    return {"counts": counts, "sent": sent, "docs": docs, "held": held, "compose": comp}


# the pre-edit engine's output (computed on main 7b618467 BEFORE any be-watch edit — scratchpad bewatch/gold.py)
DIGEST_BLOCKS = "9b805e9013212a9125cf3d954561447d5401d08c6d7b7403ab7eb9acf5e14f98"
DIGEST_BASES = "21f1006f39b28ab5229f2bc6437be69cd67ec4facc65f026450238d39de99ae7"
DIGEST_XA = "df43ccebc5ed28d272dd226edacbd4469efce573890904f081988ff83b923969"
# cross_alerts.py with its module docstring stripped — ast.dump digest of main's file == this file's (code untouched)
DIGEST_XA_CODE = "670b982e6a621ee47ce84d7c7909771558c870e3ab52dee98136403bccfe83d9"

ET = ZoneInfo("America/New_York")
SESSION = S.isoformat()
FRI_IN = datetime(2026, 11, 13, 10, 30, tzinfo=ET)
SUN = datetime(2026, 11, 15, 12, 0, tzinfo=ET)
PKG = Path(BLD.__file__).resolve().parent
MAIN_FRAMES = (("1m", "1min"), ("3m", "3min"), ("5m", "5min"))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture()
def no_levels(monkeypatch):
    """The levels module (be-zones) as an EMPTY stub — these tests pin the serve, not the zone engine."""
    stub = types.SimpleNamespace(section=lambda *a, **k: {}, legend=lambda: [], rules_line=lambda: "",
                                 warm=lambda *a, **k: {"read": []}, spawn=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, stub)
    return stub


def _db(symbols):
    docs = [{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}]
    return {C.COLL_LIST: FakeColl(docs), C.COLL_TILES: FakeColl(), C.COLL_ALERTS: FakeColl(), C.COLL_STATE: FakeColl()}


def _store(db, sym, fr, session=S, now=NOW, held=None):
    flt, upd = BLD.tile_update(sym, fr, session, now, "loaded", held)
    BLD.write(db[C.COLL_TILES], [(flt, upd)])
    return db[C.COLL_TILES].docs[sym]


def _real(now=NOW, end=(10, 41), d=S, prev=PREV):
    return B.build_frames("OMH", d, now, raw_day(prev), raw_day(d, end=end, seed=3.0), rules=C.FRAMES)


def _old_doc(sym="OLD"):
    """A tile doc written by main (frames 1m / 3m / 5m) — what every live doc holds right after the deploy."""
    fr = B.build_frames(sym, S, NOW, raw_day(PREV), raw_day(S, end=(10, 41), seed=3.0), rules=MAIN_FRAMES)
    with pytest.MonkeyPatch.context() as mp:                     # main's constants, for this write only
        mp.setattr(C, "FRAMES", MAIN_FRAMES)
        mp.setattr(C, "FRAME_WORDS", {"1m": "1-min", "3m": "3-min", "5m": "5-min"})
        frames = BLD.tile_update(sym, fr, S, NOW, "loaded")[1]["$set"]["frames"]
    for t in frames.values():
        t.pop("vwap", None)                                      # main wrote no VWAP
    assert list(frames) == ["1m", "3m", "5m"]
    return {"_id": sym, "symbol": sym, "status": "loaded", "session": SESSION, "at": datetime(2026, 11, 13, 15, 30),
            "loaded_at": datetime(2026, 11, 13, 15, 30), "seen_bar_t": stamp(S, 10, 39), "frames": frames}


# ── step-0 goldens: byte-equal to main ───────────────────────────────────────────────────────────────────────────
def test_golden_served_1m_and_5m_blocks_are_byte_equal_to_main():
    got = gold_blocks()
    assert dig(got) == DIGEST_BLOCKS
    for tf in ("1m", "5m"):
        assert [c["tone"] for c in got[tf]["curves"]] == ["ema9", "ema21"]          # curves[:2] are the two EMAs
    assert got["1m"]["held"] is not None and got["1m"]["markers"]                    # the golden is not vacuous


def test_golden_5m_run_bases_and_ellipses_are_byte_equal_to_main():
    got = gold_blocks(gold_bases_doc(), tfs=("5m",))
    assert dig(got) == DIGEST_BASES
    assert got["5m"]["run_bases"]["text"] and len(got["5m"]["ellipses"]) == 3


def test_golden_the_1m_cross_push_is_byte_equal_to_main():
    got = gold_xa()
    assert dig(got) == DIGEST_XA
    assert got["counts"]["pushed"] == 1 and len(got["sent"]) == 1


def test_cross_alerts_code_is_main_s_code_only_the_docstring_word_moved():
    src = (PKG / "cross_alerts.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    assert "5- and 15-minute crosses are drawn only" in doc and "3- and 5-minute" not in doc.replace("was 3- and 5-", "")
    tree.body = tree.body[1:]
    assert hashlib.sha256(ast.dump(tree).encode()).hexdigest() == DIGEST_XA_CODE


# ── frames 1 / 5 / 15 ────────────────────────────────────────────────────────────────────────────────────────────
def test_frames_are_1_5_15_in_served_order_and_the_push_frame_stays_1m():
    assert C.FRAMES == (("1m", "1min"), ("5m", "5min"), ("15m", "15min"))
    assert C.FRAME_WORDS == {"1m": "1-min", "5m": "5-min", "15m": "15-min"} and C.AXIS_FRAME == "1m"
    assert C.PUSH_FRAMES == ("1m",)
    assert "15m" in AL.FRAME_MINUTES                                   # the fence is PUSH_FRAMES alone (spec §6)
    assert B.RULE_OF["15m"] == "15min" and "3m" not in dict(C.FRAMES)


def test_NEGATIVE_no_3m_anywhere_in_the_served_board_and_the_words_say_1_5_15(no_levels):
    db = _db(["OMH", "OLD"])
    _store(db, "OMH", _real())
    db[C.COLL_TILES].docs["OLD"] = _old_doc()
    out = PL.build(FRI_IN, db=db)
    txt = json.dumps(out, default=str, ensure_ascii=False)
    assert out["state"] == "ok"
    for bad in ('"3m"', "3-min", "3-minute", "1-, 3-"):
        assert bad not in txt, bad
    assert "1-, 5- and 15-minute" in out["title"] and "1-, 5- and 15-minute" in out["empty_text"]
    line = XA.rules_line()
    assert "1-, 5- and 15-min charts" in line and "5- and 15-min crosses are marked only" in line
    json.dumps(out, default=str, allow_nan=False)


@pytest.mark.parametrize("now,in_window", [(FRI_IN, True), (SUN, False)])
def test_NEGATIVE_an_old_1m_3m_5m_doc_serves_1m_5m_and_a_15m_placeholder(no_levels, now, in_window):
    db = _db(["OLD"])
    db[C.COLL_TILES].docs["OLD"] = _old_doc()
    out = PL.build(now, db=db)
    r = out["rows"][0]
    assert out["state"] == "ok" and r["state"] == "ok"
    assert [f["tf"] for f in r["frames"]] == ["1m", "5m", "15m"]
    one, five, fifteen = r["frames"]
    assert one["tile"]["bars"] and five["tile"]["bars"] and "empty_text" not in one and "empty_text" not in five
    want = PL.FRAME_PENDING_TEXT[in_window].format(frame="15-min", open=GC.PASS_OPEN_ET)
    assert fifteen["empty_text"] == want and fifteen["tile"]["bars"] == [] and fifteen["tile"]["curves"] == []
    assert fifteen["axis"] is None and fifteen["ema_cross"] is None and fifteen["uptrend"] is None
    assert fifteen["held"] is None and fifteen["ema_blink"] is None and fifteen["ema_tail"] is None
    assert set(fifteen["tile"]) == set(one["tile"]) and fifteen["label"] == "15-min"
    assert '"3m"' not in json.dumps(r, default=str)
    if in_window:
        assert "reading now" in want
    else:
        assert "next read" in want and GC.PASS_OPEN_ET in want


def test_NEGATIVE_a_doc_holding_only_3m_is_never_served_as_a_chart(no_levels):
    db = _db(["ODD"])
    doc = _old_doc("ODD")
    doc["frames"] = {"3m": doc["frames"]["3m"]}
    db[C.COLL_TILES].docs["ODD"] = doc
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["frames"] == [] and r["state"] == "pending"                               # no tf of C.FRAMES stored


def _labels(F):
    return [datetime.strptime(F.t[i], "%Y-%m-%d %H:%M").replace(tzinfo=ET) for i in F.today]


def test_15m_bars_sit_on_the_quarter_hours_and_each_is_the_aggregate_of_its_minutes():
    p, t = raw_day(PREV), raw_day(S, end=(10, 41), seed=3.0)
    F = B.build_frames("OMH", S, NOW, p, t, rules=C.FRAMES).frame("15m")
    assert F.frame == "15m" and len(F.today)
    et = t.copy()
    et.index = et.index.tz_localize("UTC").tz_convert(ET)
    for k, lab in zip(F.today, _labels(F)):
        assert lab.minute in (0, 15, 30, 45)
        mins = et[(et.index >= lab - timedelta(minutes=15)) & (et.index < lab)]
        assert len(mins) == 15
        assert F.o[k] == pytest.approx(float(mins["open"].iloc[0])) and F.c[k] == pytest.approx(float(mins["close"].iloc[-1]))
        assert F.h[k] == pytest.approx(float(mins["high"].max())) and F.l[k] == pytest.approx(float(mins["low"].min()))
        assert F.v[k] == pytest.approx(float(mins["volume"].sum()))
    assert F.t[F.today.start] == stamp(S, 4, 15) and F.t[-1] == stamp(S, 10, 30)    # 10:30–10:44 still printing


def test_NEGATIVE_the_15m_settle_rule_and_the_still_printing_bucket():
    lab = at(S, 10, 30)
    before = _real(now=lab + timedelta(seconds=GC.BAR_SETTLE_SEC - 1)).frame("15m")
    after = _real(now=lab + timedelta(seconds=GC.BAR_SETTLE_SEC)).frame("15m")
    assert stamp(S, 10, 30) not in before.t and before.t[-1] == stamp(S, 10, 15)
    assert after.t[-1] == stamp(S, 10, 30)


def test_the_first_15m_bar_of_a_quiet_premarket_holds_the_first_prints():
    fr = B.build_frames("OMH", S, at(S, 9, 0), raw_day(PREV), raw_day(S, start=(7, 3), end=(9, 0)), rules=C.FRAMES)
    F = fr.frame("15m")
    assert F.t[F.today.start] == stamp(S, 7, 15)                                     # 07:03–07:14, labelled 07:15
    k = F.today.start
    assert F.v[k] == pytest.approx(sum(1000 + (i * 37) % 900 for i in range(12)))


@pytest.mark.parametrize("end,now,slots", [((10, 41), NOW, 48), ((16, 20), at(S, 16, 20, 30), 64)])
def test_the_15m_axis_slots_frame_min_shade_and_the_fe_bucket_formula(end, now, slots):
    fs = BLD.tile_update("OMH", _real(now=now, end=end), S, now, "loaded")[1]["$set"]["frames"]
    ax = fs["15m"]["axis"]
    assert ax["slots"] == slots and ax["frame_min"] == 15 and ax["shade"][0] == {"from_slot": 0, "to_slot": 22,
                                                                                  "kind": "pre"}
    for b, x in zip(fs["15m"]["bars"], ax["x"]):
        opened = AL.bar_close_et(b["t"]).timestamp() - 900
        assert math.floor((opened - ax["start_epoch"]) / 900) == x                   # ggwBucket over the served keys


def test_a_frame_with_no_closed_bar_serves_words_and_frames_with_bars_carry_none(no_levels):
    now = at(S, 4, 10, 30)                                       # 1m bars printed; no 15m bucket closed yet
    fr = B.build_frames("OMH", S, now, raw_day(PREV), raw_day(S, end=(4, 11)), rules=C.FRAMES)
    db = _db(["OMH"])
    _store(db, "OMH", fr, now=now)
    r = PL.build(now, db=db)["rows"][0]
    by = {f["tf"]: f for f in r["frames"]}
    assert by["15m"]["tile"]["bars"] == []
    assert by["15m"]["empty_text"] == PL.FRAME_NO_BARS_TEXT.format(frame="15-min", minutes=15)
    assert by["1m"]["tile"]["bars"] and "empty_text" not in by["1m"]
    for f in r["frames"]:
        assert f["tile"]["lines"] == []
    json.dumps(r, default=str, allow_nan=False)


def test_every_served_frame_has_empty_lines_and_frames_with_bars_no_empty_text(no_levels):
    db = _db(["OMH"])
    _store(db, "OMH", _real())
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert [f["tf"] for f in r["frames"]] == ["1m", "5m", "15m"]
    for f in r["frames"]:
        assert f["tile"]["lines"] == [] and f["tile"]["bars"] and "empty_text" not in f


# ── the push fence ───────────────────────────────────────────────────────────────────────────────────────────────
class _SF:
    def __init__(self, t, f9, f21, frame):
        self.t, self.ema9, self.ema21, self.frame = list(t), list(f9), list(f21), frame
        self.c = [1.0 + i / 100 for i in range(len(t))]
        self.today = range(len(t))

    def __len__(self):
        return len(self.t)


def test_NEGATIVE_a_15m_up_cross_on_its_own_latest_bar_never_rings(monkeypatch):
    monkeypatch.setattr(B, "session_volume", lambda fr: 5_000_000)
    flat1 = _SF([stamp(S, 9, 57), stamp(S, 9, 58), stamp(S, 9, 59), stamp(S, 10, 0)], [3] * 4, [2] * 4, "1m")
    F15 = _SF([stamp(S, 9, 15), stamp(S, 9, 30), stamp(S, 9, 45), stamp(S, 10, 0)], [1, 1, 1, 3], [2] * 4, "15m")
    by = {"1m": flat1, "15m": F15}
    fr = types.SimpleNamespace(by=by, frame=lambda tf: by.get(tf, flat1), session=SESSION)
    coll, held, sent = FakeColl(), {}, []
    c = XA.run({"OMH": fr}, at(S, 10, 0, 30), S, coll=coll, send=lambda o, p: sent.append(p), owner=OWNER,
               held=held)
    assert c["cross"] == 1 and c["not_push_frame"] == 1 and c["pushed"] == 0
    assert sent == [] and coll.docs == {} and held == {}


# ── the minute loop's cost: no new fetch ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("shape", ["main", "new"])
def test_loader_calls_per_iteration_are_two_per_name_before_and_after(monkeypatch, shape):
    if shape == "main":
        monkeypatch.setattr(C, "FRAMES", MAIN_FRAMES)
        monkeypatch.setattr(C, "FRAME_WORDS", {"1m": "1-min", "3m": "3-min", "5m": "5-min"})
        monkeypatch.setattr(C, "VWAP_ON", False)
    calls = []

    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        calls.append((sym, day, force))
        return raw_day(S, end=(10, 41), seed=3.0) if day == S else raw_day(PREV)
    monkeypatch.setattr(L.AUTO, "step", lambda *a, **k: {"symbols": [], "reason": None})
    db = _db(["OMH", "AMD", "NVDA"])
    out = L.run_iteration(NOW, db=db, deps=L.Deps(load_day=load, send=lambda o, p: {"sent": 0, "total_targets": 0}))
    assert out["ran"] is True and len(calls) == 2 * 3
    assert sorted(c[2] for c in calls) == [False] * 3 + [True] * 3                   # today forced, prior day cached
    tile = db[C.COLL_TILES].docs["OMH"]
    assert list(tile["frames"]) == [tf for tf, _r in C.FRAMES]
    assert ("vwap" in tile["frames"]["1m"]) is (shape == "new")


# ── 📐 the zones hook in the board ───────────────────────────────────────────────────────────────────────────────
def _levels_stub(blk):
    return types.SimpleNamespace(
        section=lambda names, tiles, siso, now, in_window: {n: blk for n in names if n in tiles},
        legend=lambda: [{"tone": "zone_demand", "label": "Daily demand zone (dashed)", "title": "Z"}],
        rules_line=lambda: "ZONES RULE")


BAND = {"kind": "board_demand", "lo": 9.5, "hi": 9.7, "label": "Daily demand 9.50–9.70", "gutter": "demand",
        "ctx": True}


def test_the_levels_block_lands_on_the_row_and_its_bands_on_frames_with_bars_only(monkeypatch):
    blk = {"state": "ok", "text": "📐 Daily zones (bars through 2026-11-12): inside demand 9.50–9.70", "title": "T",
           "as_of": "2026-11-12", "bands": [BAND]}
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, _levels_stub(blk))
    db = _db(["OLD", "NONE"])
    db[C.COLL_TILES].docs["OLD"] = _old_doc()
    out = PL.build(FRI_IN, db=db)
    old, none = out["rows"]
    assert old["levels"] == {"state": "ok", "text": blk["text"], "title": "T", "as_of": "2026-11-12"}
    one, five, fifteen = old["frames"]
    assert one["tile"]["bands"] == [BAND] and five["tile"]["bands"] == [BAND]
    assert fifteen["tile"]["bands"] == []                                            # a placeholder draws nothing
    assert none["levels"] is None and none["state"] == "pending"                     # no tile doc → no block
    assert out["legend"][-1]["tone"] == "zone_demand" and out["info"]["zones_text"] == "ZONES RULE"


def test_NEGATIVE_a_raising_levels_module_leaves_the_board_answering(monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("zones down")
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, types.SimpleNamespace(section=boom, legend=boom,
                                                                            rules_line=boom))
    db = _db(["OMH"])
    _store(db, "OMH", _real())
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala_watch.payload"):
        out = PL.build(FRI_IN, db=db)
    assert out["state"] == "ok" and all(r["levels"] is None for r in out["rows"])
    assert [e["tone"] for e in out["legend"]] == ["ema9", "ema21", C.VWAP_TONE]
    assert out["info"]["zones_text"] is None
    assert all(f["tile"]["bands"] == [] for f in out["rows"][0]["frames"])
    assert sum("zones section unavailable" in r.getMessage() for r in caplog.records) == 1


def test_NEGATIVE_zones_off_reads_nothing_and_serves_none(monkeypatch):
    monkeypatch.setattr(C, "ZONES_ON", False)
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, types.SimpleNamespace(
        section=lambda *a, **k: pytest.fail("off → no section"), legend=lambda: pytest.fail("off → no legend"),
        rules_line=lambda: pytest.fail("off → no sentence")))
    db = _db(["OMH"])
    _store(db, "OMH", _real())
    out = PL.build(FRI_IN, db=db)
    assert out["rows"][0]["levels"] is None and out["info"]["zones_text"] is None
    assert [e["tone"] for e in out["legend"]] == ["ema9", "ema21", C.VWAP_TONE]


def test_the_levels_section_reads_no_store_of_its_own(monkeypatch):
    seen = []
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, types.SimpleNamespace(
        section=lambda names, tiles, siso, now, in_window: seen.append((list(names), sorted(tiles), siso,
                                                                        in_window)) or {},
        legend=lambda: [], rules_line=lambda: ""))
    db = _db(["OMH"])
    _store(db, "OMH", _real())
    PL.build(FRI_IN, db=db)
    assert seen == [(["OMH"], ["OMH"], SESSION, True)]


def test_source_guard_payload_and_loop_import_the_levels_module_lazily_only():
    for name in ("payload.py", "loop.py", "build.py"):
        src = (PKG / name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                text = ast.unparse(node)
                assert "levels" not in text, (name, text)
    assert C.LEVELS_MODULE == "chart_maps.gajjala_watch.levels"
    assert "importlib.import_module(C.LEVELS_MODULE)" in (PKG / "loop.py").read_text(encoding="utf-8")
    assert "import payload" not in (PKG / "loop.py").read_text(encoding="utf-8")


# ── [C1] the add-time build child ────────────────────────────────────────────────────────────────────────────────
def _child(monkeypatch, db, *, levels=None, status="loaded"):
    """L.build_pending (the list read) + BLD.frames (the fetch) + L._levels recorded; every call lands in `order`."""
    order, fetched, lv = [], [], []
    real_bp = L.build_pending

    def bp(*a, **k):
        order.append(("bp", None))
        if len(order) > 40:                                      # a re-fetch loop fails here instead of hanging
            raise AssertionError("the build child never ends")
        return real_bp(*a, **k)

    def frames(symbols, session, now, **k):
        fetched.extend(symbols)
        for s in symbols:
            k["per_name"][s] = ({"status": "no_bars", "prev": True} if status == "no_prints"
                                else {"status": "failed", "prev": True})
        return {}

    def _levels(now, *, thread=False, first=None, rest=True):
        lv.append({"thread": thread, "first": list(first or []), "rest": rest})
        order.append(("lv", list(first or [])))
        return levels(len(lv), first, rest) if levels else 0
    monkeypatch.setattr(BLD, "frames", frames)
    monkeypatch.setattr(L, "build_pending", bp)
    monkeypatch.setattr(L, "_levels", _levels)
    monkeypatch.setattr(L.CO, "_db", lambda: db)
    return order, fetched, lv


def test_C1_an_add_that_lands_during_the_zones_read_is_built_by_the_same_child(monkeypatch):
    db = _db(["A"])

    def levels(n, first, rest):
        if n == 1:                                               # he adds B while the zones of A are read
            db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] = ["A", "B"]
        return len(first or [])
    order, fetched, lv = _child(monkeypatch, db, levels=levels)
    out = L.build_all(at(S, 20, 30))
    assert out["built"] == ["A", "B"] and fetched == ["A", "B"]
    assert lv[0] == {"thread": False, "first": ["A"], "rest": True}
    assert lv[1] == {"thread": False, "first": ["B"], "rest": False}
    assert order[-1][0] == "bp"                                                      # the list re-read is LAST


def test_C1_NEGATIVE_a_no_prints_name_is_fetched_once_per_child_however_many_rounds(monkeypatch):
    db = _db(["A"])
    adds = iter(["B", "C", "D"])

    def levels(n, first, rest):                                  # a new add lands during each of three zones reads
        nxt = next(adds, None)
        if nxt:
            db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"].append(nxt)
        return len(first or []) + (3 if rest else 0)
    order, fetched, lv = _child(monkeypatch, db, levels=levels, status="no_prints")
    out = L.build_all(at(S, 20, 30))
    assert fetched == ["A", "B", "C", "D"] and out["built"] == ["A", "B", "C", "D"]  # each ONCE — A stays no_prints
    assert {db[C.COLL_TILES].docs[s]["status"] for s in "ABCD"} == {"no_prints"}
    assert [o[0] for o in order].count("bp") == 5 and order[-1][0] == "bp"


def test_C1_nothing_to_build_and_nothing_read_is_exactly_one_list_read(monkeypatch):
    db = _db([])
    calls = []
    monkeypatch.setattr(L, "build_pending", lambda now=None, **k: calls.append(k) or {"built": []})
    monkeypatch.setattr(L, "_levels", lambda *a, **k: 0)
    out = L.build_all(at(S, 20, 30))
    assert len(calls) == 1 and out["built"] == []


def test_C1_new_only_never_runs_the_rest_pass_and_the_cli_loops_through_build_all(monkeypatch):
    got, lv = [], []
    rounds = iter([["A"], [], []])
    monkeypatch.setattr(L, "build_pending", lambda now=None, **k: got.append(k) or {"built": next(rounds)})
    monkeypatch.setattr(L, "_levels", lambda now, **k: lv.append(k) or len(k.get("first") or []))
    assert L.main(["--build", "--new-only"]) == 0
    assert len(got) == 2 and all(k["new_only"] is True for k in got)
    assert got[0]["tried"] is got[1]["tried"]                                        # ONE shared set
    assert lv == [{"first": ["A"], "rest": False}]                                   # never rest on --new-only


def test_C1_build_pending_tried_none_is_byte_identical_and_a_given_set_is_filled_in_place(monkeypatch):
    def run(**kw):
        db = _db(["A", "B"])
        finds = []
        real = db[C.COLL_TILES].find
        db[C.COLL_TILES].find = lambda q=None, p=None: finds.append((q, p)) or real(q, p)
        monkeypatch.setattr(BLD, "frames", lambda symbols, session, now, **k: {})
        out = L.build_pending(at(S, 20, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None), **kw)
        return out, finds, db[C.COLL_TILES].docs
    base = run()
    assert run(tried=None) == base
    mine = set()
    got = run(tried=mine)
    assert got[0] == base[0] and got[1] == base[1] and mine == {"A", "B"}
    skip = run(tried={"A"})
    assert skip[0]["built"] == ["B"]                                                 # a shared name is never re-tried


def test_build_pending_rebuilds_a_doc_lacking_15m_and_new_only_does_not(monkeypatch):
    old = _old_doc("OLD")
    full = dict(old, _id="NEW", symbol="NEW", frames={tf: {"tf": tf} for tf, _r in C.FRAMES})
    calls = []
    monkeypatch.setattr(BLD, "frames", lambda symbols, session, now, **k: calls.append(list(symbols)) or {})
    db = _db(["OLD", "NEW"])
    db[C.COLL_TILES].docs.update({"OLD": old, "NEW": full})
    out = L.build_pending(at(S, 12, 0), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert calls == [["OLD"]] and out["built"] == ["OLD"]
    calls.clear()
    db = _db(["OLD"])
    db[C.COLL_TILES].docs["OLD"] = dict(old, at=datetime(2026, 11, 13, 17, 0))
    db[C.COLL_LIST].docs[C.LIST_DOC_ID]["added"] = {"OLD": "2026-11-13T15:00:00+00:00"}
    out = L.build_pending(at(S, 12, 0), db=db, deps=L.Deps(load_day=lambda *a, **k: None), new_only=True)
    assert calls == [] and out["built"] == []                                        # --new-only reads `added` only


def test_build_pending_projection_names_every_frame_tf():
    src = inspect.getsource(L.build_pending)
    assert 'proj.update({f"frames.{tf}.tf": 1 for tf, _r in C.FRAMES})' in src


# ── the loop hooks ───────────────────────────────────────────────────────────────────────────────────────────────
def test_source_guard_run_iteration_never_names_the_zones():
    src = inspect.getsource(L.run_iteration)
    assert "levels" not in src and "_levels" not in src and "LEVELS" not in src


def test_levels_is_fenced_and_counts_the_daily_reads(monkeypatch):
    seen = []
    mod = types.SimpleNamespace(warm=lambda now, first=None, rest=True: seen.append((first, rest)) or
                                {"read": ["A", "B"]}, spawn=lambda now: seen.append("spawn"))
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, mod)
    assert L._levels(NOW, first=["A"], rest=False) == 2 and seen == [(["A"], False)]
    assert L._levels(NOW, thread=True) == 0 and seen[-1] == "spawn"
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, types.SimpleNamespace(
        warm=lambda *a, **k: {"reason": "no_store", "read": []}))
    assert L._levels(NOW) == 0


@pytest.mark.parametrize("mod", [types.SimpleNamespace(), None, types.SimpleNamespace(warm=lambda *a, **k: 1 / 0),
                                 types.SimpleNamespace(warm=lambda *a, **k: "junk")])
def test_NEGATIVE_a_broken_levels_module_is_zero_and_nothing_else_changes(monkeypatch, mod):
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, mod)                           # None → ImportError
    assert L._levels(NOW) == 0 and L._levels(NOW, thread=True) == 0


def test_NEGATIVE_zones_off_never_imports_the_module(monkeypatch):
    monkeypatch.setattr(C, "ZONES_ON", False)
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, types.SimpleNamespace(
        warm=lambda *a, **k: pytest.fail("off"), spawn=lambda *a, **k: pytest.fail("off")))
    assert L._levels(NOW) == 0 and L._levels(NOW, thread=True) == 0


def test_NEGATIVE_dry_run_never_calls_the_zones(monkeypatch):
    monkeypatch.setattr(L, "_levels", lambda *a, **k: pytest.fail("--dry-run read the zones"))
    monkeypatch.setattr(L, "run_iteration", lambda *a, **k: {"ran": True})
    assert L.main(["--dry-run", "--symbols", "OMH"]) == 0
    assert L.main(["--dry-run"]) == 0


def test_loop_cli_starts_the_zones_thread_before_the_slot(monkeypatch):
    order = []
    monkeypatch.setattr(L.RUN, "in_window", lambda now: True)
    monkeypatch.setattr(L, "_levels", lambda now, **k: order.append(("levels", k)) or 0)
    monkeypatch.setattr(L, "loop", lambda now=None, **k: order.append(("loop", None)) or {})
    monkeypatch.setattr(L, "run_iteration", lambda *a, **k: order.append(("iteration", None)) or {})
    assert L.main(["--loop"]) == 0
    assert order == [("levels", {"thread": True}), ("loop", None)]
    order.clear()
    assert L.main([]) == 0 and order == [("iteration", None)]                         # a bare run: no thread
