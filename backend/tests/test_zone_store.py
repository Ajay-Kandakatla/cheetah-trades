"""supply_demand/zone_store — the 9:20 per-symbol band store.

Ajay 2026-09-03 (NTAP): the shelf the low bounced off was a one-touch
broken-supply band the demand board never keeps, so the bounce watcher
needs every band, both kinds, drawn BEFORE today. Synthetic frames only.
"""
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import zone_store as ZS  # noqa: E402

ET = ZoneInfo("America/New_York")
TODAY = date(2026, 9, 3)


class FakeColl:
    def __init__(self):
        self.docs = {}

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)

    def find(self, q):
        for d in self.docs.values():
            if "date" in q and d.get("date") != q["date"]:
                continue
            if "symbol" in q and d.get("symbol") not in q["symbol"]["$in"]:
                continue
            yield dict(d)


def _frame(n=200, end=TODAY, seed=1, today_low=None):
    """Daily OHLCV ending on `end` (inclusive). `today_low` plants a low on
    the last (today) row far below everything else."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    close = 100 + np.cumsum(rng.normal(0, 1.0, n))
    high = close + rng.uniform(0.5, 2.0, n)
    low = close - rng.uniform(0.5, 2.0, n)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                       "volume": rng.integers(1_000_000, 5_000_000, n).astype(float)},
                      index=idx)
    df.index.name = "date"
    if today_low is not None:
        df.iloc[-1, df.columns.get_loc("low")] = today_low
    return df


# ── today's rows are dropped before anything is computed ────────────────────
def test_build_doc_drops_todays_rows_before_compute_and_reads_prev_close_from_the_truncated_frame():
    df = _frame(today_low=50.0)                     # today's low would be its own band
    seen = {}

    def fake_compute(frame):
        seen["frame"] = frame
        return {"demand_zones": [{"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2,
                                  "strength": 40.0}], "supply_zones": []}

    doc = ZS.build_doc("XYZ", df, TODAY, compute=fake_compute, atr=lambda f: 1.25,
                       now=datetime(2026, 9, 3, 9, 20, tzinfo=ET))
    assert pd.Timestamp(TODAY) not in seen["frame"].index
    assert seen["frame"].index.max() < pd.Timestamp(TODAY)
    assert len(seen["frame"]) == len(df) - 1
    assert doc["prev_close"] == float(df["close"].iloc[-2]), "yesterday's close, not today's partial"
    assert float(seen["frame"]["low"].min()) > 50.0, "today's planted low never reached compute"


def test_drop_today_is_a_no_op_when_the_frame_already_ends_yesterday():
    df = _frame(end=date(2026, 9, 2))
    out = ZS.drop_today(df, TODAY)
    assert len(out) == len(df)
    assert ZS.drop_today(None, TODAY) is None
    assert len(ZS.drop_today(df.iloc[0:0], TODAY)) == 0


# ── doc shape ────────────────────────────────────────────────────────────────
def test_doc_shape_keeps_both_kinds_slimmed_to_kind_lo_hi_touches_strength():
    def fake_compute(frame):
        return {"demand_zones": [{"kind": "demand", "lo": 153.53, "hi": 158.99, "mid": 156.2,
                                  "touches": 1, "strength": 15.0, "volume": 9, "in_price": False}],
                "supply_zones": [{"kind": "supply", "lo": 161.78, "hi": 167.54, "mid": 164.6,
                                  "touches": 1, "strength": 18.0, "volume": 9},
                                 {"kind": "supply", "lo": None, "hi": 1.0}]}      # garbage dropped

    doc = ZS.build_doc("NTAP", _frame(), TODAY, compute=fake_compute, atr=lambda f: 6.907,
                       now=datetime(2026, 9, 3, 9, 20, tzinfo=ET))
    assert doc["_id"] == "NTAP:2026-09-03" and doc["symbol"] == "NTAP"
    assert doc["date"] == "2026-09-03" and doc["geom"] == "board"
    assert doc["atr14"] == 6.907 and doc["computed_at"].startswith("2026-09-03T09:20")
    assert doc["bands"] == [
        {"kind": "demand", "lo": 153.53, "hi": 158.99, "touches": 1, "strength": 15.0},
        {"kind": "supply", "lo": 161.78, "hi": 167.54, "touches": 1, "strength": 18.0}]
    assert set(doc) == {"_id", "symbol", "date", "geom", "bands", "atr14", "prev_close", "high_252",
                        "computed_at"}


def test_build_doc_with_the_real_geometry_returns_only_the_two_kinds():
    doc = ZS.build_doc("SYN", _frame(n=300, seed=7), TODAY)
    assert doc is not None and doc["bands"], "300 synthetic bars must yield structure"
    assert {b["kind"] for b in doc["bands"]} <= {"demand", "supply"}
    assert all(b["lo"] <= b["hi"] and b["touches"] >= 1 for b in doc["bands"])
    assert doc["atr14"] and doc["atr14"] > 0


def test_build_doc_refuses_missing_or_short_frames_and_a_crashing_compute():
    assert ZS.build_doc("X", None, TODAY) is None
    assert ZS.build_doc("X", _frame(n=ZS.MIN_BARS), TODAY) is None, \
        "MIN_BARS rows INCLUDING today is one short after the drop"

    def boom(frame):
        raise RuntimeError("no")
    assert ZS.build_doc("X", _frame(), TODAY, compute=boom) is None


# ── universe filter ──────────────────────────────────────────────────────────
def test_big_cap_universe_keeps_known_caps_at_or_above_a_billion_only():
    caps = {"BIG": 37e9, "EDGE": 1e9, "SMALL": 999_999_999, "UNK": None, "BAD": "x"}
    out = ZS.big_cap_universe(["big", "EDGE", "SMALL", "UNK", "BAD", "MISSING"], caps)
    assert out == ["BIG", "EDGE"]


# ── warm + load ──────────────────────────────────────────────────────────────
def test_warm_tolerates_a_none_frame_and_persists_by_symbol_date(monkeypatch):
    coll = FakeColl()
    frames = {"AAA": _frame(seed=2), "BBB": None, "CCC": _frame(seed=3)}

    def loader(sym):
        if sym == "CCC":
            raise ConnectionError("provider down")
        return frames[sym]

    def fake_compute(frame):
        return {"demand_zones": [{"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2,
                                  "strength": 40.0}], "supply_zones": []}

    out = ZS.warm(universe=["AAA", "BBB", "CCC"], caps={"AAA": 2e9, "BBB": 2e9, "CCC": 2e9},
                  loader=loader, coll=coll, today=TODAY, compute=fake_compute, atr=lambda f: 1.0)
    assert out["universe"] == 3 and out["stored"] == 1 and out["skipped"] == 2
    assert out["failed"] == 0 and out["timed_out"] is False
    assert list(coll.docs) == ["AAA:2026-09-03"]
    assert coll.docs["AAA:2026-09-03"]["bands"][0]["hi"] == 92.0


def test_load_reads_one_date_and_optionally_a_symbol_subset():
    coll = FakeColl()
    for sym, day in (("AAA", "2026-09-03"), ("BBB", "2026-09-03"), ("AAA", "2026-09-02")):
        coll.replace_one({"_id": f"{sym}:{day}"}, {"_id": f"{sym}:{day}", "symbol": sym,
                                                  "date": day, "bands": []}, upsert=True)
    today = ZS.load(None, date(2026, 9, 3), coll=coll)
    assert set(today) == {"AAA", "BBB"} and today["AAA"]["_id"] == "AAA:2026-09-03"
    assert set(ZS.load(["aaa"], date(2026, 9, 3), coll=coll)) == {"AAA"}
    assert ZS.load(None, date(2026, 9, 1), coll=coll) == {}


# ── source guard: the cron line ──────────────────────────────────────────────
def test_crontab_warms_the_store_at_nine_twenty_before_the_board():
    cron = (Path(__file__).resolve().parents[2] / "backend/crontab").read_text()
    lines = [l for l in cron.splitlines() if "supply_demand.zone_store" in l and not l.startswith("#")]
    assert len(lines) == 1 and lines[0].split()[:5] == ["20", "9", "*", "*", "1-5"]
    board = [l for l in cron.splitlines() if "demand-reentry warm full (am)" in l and not l.startswith("#")]
    assert board and board[0].split()[:2] == ["25", "9"], "board warms at 9:25, the store must be first"


# ── high_252: the 52-week high as of yesterday's close (zone_edge "→ new highs") ─
def test_high_252_is_the_max_high_of_the_last_252_rows_excluding_today():
    df = _frame(n=300, seed=5)
    df.iloc[-1, df.columns.get_loc("high")] = 999.0          # today's partial bar: never counted
    df.iloc[-260, df.columns.get_loc("high")] = 500.0        # older than 252 sessions: never counted
    df.iloc[-100, df.columns.get_loc("high")] = 250.0        # inside the window: the answer

    def fake_compute(frame):
        return {"demand_zones": [], "supply_zones": []}

    doc = ZS.build_doc("XYZ", df, TODAY, compute=fake_compute, atr=lambda f: 1.0,
                       now=datetime(2026, 9, 3, 9, 20, tzinfo=ET))
    assert doc["high_252"] == 250.0
    assert isinstance(doc["high_252"], float)
    truncated = ZS.drop_today(df, TODAY)
    assert doc["high_252"] == float(truncated["high"].tail(252).max())


def test_high_252_is_none_when_the_frame_has_no_high_column_or_the_max_is_garbage():
    df = _frame().drop(columns=["high"])

    def fake_compute(frame):
        return {"demand_zones": [], "supply_zones": []}

    doc = ZS.build_doc("XYZ", df, TODAY, compute=fake_compute, atr=lambda f: 1.0)
    assert doc is not None and doc["high_252"] is None
    df2 = _frame()
    df2["high"] = np.nan
    doc2 = ZS.build_doc("XYZ", df2, TODAY, compute=fake_compute, atr=lambda f: 1.0)
    assert doc2["high_252"] is None, "an all-NaN column is unknown, not NaN"
    doc3 = ZS.build_doc("SYN", _frame(n=300, seed=7), TODAY)
    assert doc3["high_252"] > 0 and doc3["high_252"] >= max(b["hi"] for b in doc3["bands"]) * 0.5
