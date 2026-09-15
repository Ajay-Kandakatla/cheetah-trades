"""Back in Demand — 2026-09-14 review fixes (backend side).

Seven findings were verified on live data; the four with a backend half are
pinned here. None changes which names qualify for a board or an alert (Rule
#10): these are a measurement window, a stale-benchmark guard, an ordering
inconsistency, and wording.

  1. Track record 'vs SPY' started its window on the OBSERVATION day while the
     trade starts at the NEXT open — one session of SPY the trade never held.
  2. SPY's cached frame was a session stale at the 17:40 resolve, and
     `benchmark_return` clamped the window to the frame's end instead of
     saying it could not measure — excess against a truncated benchmark.
  3. 'One ordering rule' was two: the backend put a reversal INTO supply
     first; the page and the ℹ️ Rules panel put it third. The backend now
     mirrors the page, and a fixture BOTH test suites read pins the order.
  4. The ℹ️ Rules panel said "Bouncing =" to him. He reads "reversal".

Frontend halves: frontend/src/components/DemandReentryPanel.test.tsx and
frontend/src/lib/bounceRoom.test.ts ("2026-09-14 review fixes" blocks).
Docs: docs/supply_demand/{demand_track_record,zone_backtest,bounce_room,
demand_reentry_methodology}.md, dated paragraphs.

No Mongo, no network: the demand_history stand-ins are reused from
tests/test_demand_history.py.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")

from supply_demand import alert_gates as AG          # noqa: E402
from supply_demand import bounce_room as BR          # noqa: E402
from supply_demand import demand_history as DH       # noqa: E402
from supply_demand import rules_info as RI           # noqa: E402
from supply_demand import zone_backtest as ZB        # noqa: E402
from tests.test_demand_history import (              # noqa: E402,F401  (db / prices are fixtures)
    _eps, _frame, _resolved, _seed, db, prices,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bounce_room_order_mirror_2026_09_14.json"


def _bench(rows):
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({"open": [r[1] for r in rows], "high": [r[2] for r in rows],
                         "low": [r[3] for r in rows], "close": [r[4] for r in rows],
                         "volume": [1_000_000] * len(rows)}, index=idx)


# ── 1. the SPY window starts at the ENTRY open ──────────────────────────────
def test_track_record_spy_window_starts_at_the_entry_open_not_the_observation_day(db, prices):
    """SPY +10% on the observation day, flat after. The trade is entered the
    NEXT open, so the SPY it 'competed with' is 0.0 — the number
    zone_backtest scores for the same trade (`_date_at(df, i + 1)`). The old
    window (first_seen) read +10 and turned a flat benchmark into a 10-point
    handicap."""
    _seed(db)                                                  # first_seen 2026-08-17
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    prices["SPY"] = _frame([100.0] + [110.0] * 40)
    DH.resolve_open()
    ep = list(_eps(db).values())[0]
    assert ep["outcome"] == DH.OUTCOME_WIN and ep["entry_date"] == "2026-08-18"
    assert ep["spy_pct"] == pytest.approx(0.0)
    assert ep["spy_pct"] == ZB.benchmark_return(prices["SPY"], ep["entry_date"], ep["bars_to_outcome"])
    assert ep["excess_pct"] == pytest.approx(ep["net_pct"], abs=1e-3)
    # NEGATIVE: the observation-day window is a different number — the bug.
    assert ZB.benchmark_return(prices["SPY"], ep["first_seen"], ep["bars_to_outcome"]) == pytest.approx(10.0)


def test_resolve_open_passes_the_entry_date_it_stores_to_the_benchmark():
    """Source pin: the window start IS the stored entry_date, not first_seen."""
    src = inspect.getsource(DH.resolve_open)
    assert "ZB.benchmark_return(bench, entry_date, bars)" in src
    assert 'benchmark_return(bench, str(ep.get("first_seen")' not in src
    assert '"entry_date": entry_date' in src


# ── 2. a benchmark that cannot cover the window says so ─────────────────────
def test_benchmark_return_refuses_a_window_that_runs_past_the_frame():
    bench = _bench([("2020-01-01", 100.0, 100.0, 100.0, 100.0),
                    ("2020-01-02", 100.0, 100.0, 100.0, 102.0),
                    ("2020-01-03", 102.0, 102.0, 102.0, 104.0),
                    ("2020-01-06", 104.0, 104.0, 104.0, 110.0)])
    assert ZB.benchmark_return(bench, "2020-01-02", 2) == pytest.approx(10.0)   # ends ON the last bar
    assert ZB.benchmark_return(bench, "2020-01-06", 0) == pytest.approx(5.769, abs=1e-3)
    # NEGATIVE: one bar past the frame is None, never the clamped 10.0 / 5.769.
    assert ZB.benchmark_return(bench, "2020-01-02", 3) is None
    assert ZB.benchmark_return(bench, "2020-01-06", 1) is None
    assert ZB.benchmark_return(bench, "2020-01-01", 40) is None


def test_a_spy_frame_that_stops_short_of_the_exit_yields_no_excess_not_a_clamped_one(db, prices):
    """The 17:40 case: the trade resolved 13 bars after entry, the cached SPY
    frame ends after 2. Before the fix this scored SPY over the 2 bars it had
    (+9.09%) and called the difference excess."""
    _seed(db)
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    prices["SPY"] = _frame([100.0, 110.0, 120.0])
    DH.resolve_open()
    ep = list(_eps(db).values())[0]
    assert ep["resolved"] is True and ep["outcome"] == DH.OUTCOME_WIN
    assert ep["bars_to_outcome"] > 2
    assert ep["spy_pct"] is None and ep["excess_pct"] is None


def test_accuracy_skips_an_unmeasured_spy_window_never_counts_it_as_zero(db):
    """finding 2 leans on this: a None excess must drop out of the mean and
    the beat rate, not pull them toward zero."""
    _resolved(db, "sp1500:AAA:2026-08-17", DH.OUTCOME_WIN, 3.0, spy=1.0)
    _resolved(db, "sp1500:BBB:2026-08-17", DH.OUTCOME_WIN, 9.0, spy=1.0,
              spy_pct=None, excess_pct=None)
    a = DH.accuracy()
    assert a["raced"] == 2 and a["expectancy_pct"] == pytest.approx(6.0)
    assert a["excess_vs_spy_pct"] == pytest.approx(2.0)          # the measured one only
    assert a["beat_spy_pct"] == pytest.approx(100.0)             # 1 of 1 measured, not 1 of 2


def _recording_prices(monkeypatch, frames: dict, refetch_fails: bool):
    calls: list = []

    class _P:
        @staticmethod
        def load_prices(sym, *a, **k):
            calls.append((sym, dict(k)))
            if sym == ZB.BENCHMARK and k.get("force") and refetch_fails:
                raise RuntimeError("provider down")
            return frames.get(sym)

    monkeypatch.setitem(sys.modules, "sepa.prices", _P())
    import sepa
    monkeypatch.setattr(sepa, "prices", _P(), raising=False)
    return calls


def test_resolve_refetches_spy_ONCE_per_run_not_per_episode(db, monkeypatch):
    frames = {"CIEN": _frame([71.5] + [72 + i for i in range(40)]),
              "AAA": _frame([71.5] + [72 + i for i in range(40)]),
              "SPY": _frame([100.0] + [110.0] * 40)}
    calls = _recording_prices(monkeypatch, frames, refetch_fails=False)
    _seed(db)
    _seed(db, _id="sp1500:AAA:2026-08-17", symbol="AAA")
    assert DH.resolve_open()["resolved"] == 2
    assert [k for s, k in calls if s == "SPY"] == [{"force": True}], "one refetch, no cache read"
    assert all(ep["spy_pct"] == pytest.approx(0.0) for ep in _eps(db).values())


def test_resolve_falls_back_to_the_cached_spy_when_the_refetch_fails(db, monkeypatch):
    """NEGATIVE: a provider hiccup on the refetch must not cost the excess
    column (the cached frame is still a benchmark — the clamp guard above is
    what keeps a stale one honest)."""
    frames = {"CIEN": _frame([71.5] + [72 + i for i in range(40)]),
              "SPY": _frame([100.0] + [110.0] * 40)}
    calls = _recording_prices(monkeypatch, frames, refetch_fails=True)
    _seed(db)
    assert DH.resolve_open()["resolved"] == 1
    assert [k for s, k in calls if s == "SPY"] == [{"force": True}, {}]
    assert list(_eps(db).values())[0]["spy_pct"] == pytest.approx(0.0)


# ── 3. ONE ordering rule — the backend mirrors the page ─────────────────────
def _fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_bounce_room_key_orders_the_shared_fixture_exactly_as_the_frontend_does():
    """The same JSON is sorted by frontend/src/lib/bounceRoom.test.ts through
    compareBounceRoom. Both must land on `expected_order`."""
    fx = _fixture()
    rows = [r["row"] for r in fx["rows"]]
    assert [r["symbol"] for r in sorted(rows, key=BR.bounce_room_key)] == fx["expected_order"]
    assert [r["symbol"] for r in sorted(reversed(rows), key=BR.bounce_room_key)] == fx["expected_order"]
    for r in fx["rows"]:
        assert BR.room_group(r["row"]) == r["group"], (r["row"]["symbol"], r["why"])
    # the fixture actually exercises every tier and every coverage state
    assert {r["group"] for r in fx["rows"]} == {0, 1, 2, 3}
    assert {r["row"]["coverage"] for r in fx["rows"]} >= {"store", "ondemand", "pending", "unavailable"}
    assert len(fx["expected_order"]) == len(rows) == len(set(fx["expected_order"]))


def test_a_reversal_INTO_supply_sorts_under_every_room_ok_name_never_first():
    """THE finding (TRU 2026-09-05: 0.3% under its lid, on top of the board).
    Third tier: under room-ok names, above the under-floor rest."""
    into = {"symbol": "TRU", "coverage": "store", "bounce": {"bounce_pct": 9.0},
            "room": {"state": "ROOM", "room_pct": 0.3, "atr_days": 0.1, "band": None, "at_highs": False}}
    room_only = {"symbol": "CLYM", "coverage": "store", "bounce": None,
                 "room": {"state": "ROOM", "room_pct": 17.0, "atr_days": 3.1, "band": None, "at_highs": False}}
    clear = {"symbol": "EOSE", "coverage": "store", "bounce": None,
             "room": {"state": "CLEAR", "room_pct": None, "atr_days": None, "band": None, "at_highs": True}}
    under = {"symbol": "UNDR", "coverage": "store", "bounce": None,
             "room": {"state": "ROOM", "room_pct": 4.9, "atr_days": 1.0, "band": None, "at_highs": False}}
    pend = {"symbol": "PEND", "coverage": "pending"}
    assert BR.room_group(into) == 2 and BR.room_group(room_only) == 1 and BR.room_group(clear) == 1
    order = [r["symbol"] for r in sorted([pend, into, under, room_only, clear], key=BR.bounce_room_key)]
    assert order == ["EOSE", "CLYM", "TRU", "UNDR", "PEND"]
    # NEGATIVE: the biggest bounce on the board does not buy a lead.
    assert BR.bounce_room_key(into) > BR.bounce_room_key(room_only)
    assert BR.bounce_room_key(into) > BR.bounce_room_key(clear)


def test_room_group_the_four_tiers():
    b = {"bounce_pct": 4.2}
    room = lambda state, pct: {"state": state, "room_pct": pct, "atr_days": None,   # noqa: E731
                               "band": None, "at_highs": False}
    row = lambda bounce, r: {"symbol": "X", "coverage": "store", "bounce": bounce, "room": r}   # noqa: E731
    assert BR.room_group(row(b, room("CLEAR", None))) == 0
    assert BR.room_group(row(b, room("ROOM", 5.0))) == 0
    assert BR.room_group(row(None, room("CLEAR", None))) == 1
    assert BR.room_group(row(None, room("ROOM", 5.0))) == 1
    assert BR.room_group(row(b, room("ROOM", 4.9))) == 2
    assert BR.room_group(row(b, room("IN_BAND", 0.0))) == 2
    assert BR.room_group(row(b, room("NEAR", 1.4))) == 2
    assert BR.room_group(row(None, room("ROOM", 4.9))) == 3
    assert BR.room_group(row(None, room("IN_BAND", 0.0))) == 3
    assert BR.room_group(row(b, None)) == 3, "a bounce with an unknown room is not a lead"
    assert BR.room_group({"symbol": "P", "coverage": "pending"}) == 3
    assert BR.room_group({"symbol": "U", "coverage": "unavailable"}) == 3
    assert BR.room_group(None) == 3 and BR.room_group({}) == 3


def test_room_ok_and_into_supply_boundaries_mirror_the_frontend():
    floor = AG.ALERT_MIN_ROOM_PCT
    room = lambda **k: {"symbol": "X", "coverage": "store", "room": {           # noqa: E731
        "state": "ROOM", "room_pct": None, "atr_days": None, "band": None, "at_highs": False, **k}}
    assert BR.room_ok(room(state="CLEAR")) is True
    assert BR.room_ok(room(room_pct=floor)) is True
    assert BR.room_ok(room(room_pct=17.0)) is True
    assert BR.room_ok(room(room_pct=floor - 0.1)) is False
    assert BR.room_ok(room(state="IN_BAND", room_pct=0.0)) is False
    assert BR.room_ok(room(state="NEAR", room_pct=1.4)) is False
    # the 4.995 boundary: display 5.0, the server compared raw and said NEAR
    assert BR.room_ok(room(state="NEAR", room_pct=5.0, room_pct_raw=4.995)) is False
    assert BR.room_ok(room(room_pct=5.0, room_pct_raw=5.04)) is True
    assert BR.room_ok(room(room_pct=5.0, room_pct_raw=4.96)) is False, "raw wins over the rounded display"
    assert BR.room_ok(room(room_pct=17.0, room_pct_raw="x")) is True, "garbage raw falls back to room_pct"
    # NEGATIVE: an unknown room is not room
    assert BR.room_ok({"symbol": "P", "coverage": "pending"}) is False
    assert BR.room_ok({"symbol": "U", "coverage": "unavailable"}) is False
    assert BR.room_ok(None) is False and BR.room_ok({}) is False
    assert BR.room_ok(room(room_pct=None)) is False
    assert BR.room_ok({"symbol": "X", "room": "garbage"}) is False
    # into_supply: a MEASURED read under the floor, never an absent one
    assert BR.into_supply(room(room_pct=4.9)) is True
    assert BR.into_supply(room(state="IN_BAND", room_pct=0.0)) is True
    assert BR.into_supply(room(state="NEAR", room_pct=5.0, room_pct_raw=4.995)) is True
    assert BR.into_supply(room(room_pct=5.0)) is False
    assert BR.into_supply(room(state="CLEAR")) is False
    assert BR.into_supply(room(room_pct=None)) is False
    assert BR.into_supply({"symbol": "P", "coverage": "pending"}) is False
    assert BR.into_supply(None) is False and BR.into_supply({}) is False


def test_bounce_room_key_shape_room_group_leads_and_bouncing_alone_is_no_longer_a_key():
    row = {"symbol": "B_R5_A", "coverage": "store", "bounce": {"bounce_pct": 4.0},
           "room": {"state": "ROOM", "room_pct": 5.0, "atr_days": None, "band": None, "at_highs": False}}
    assert BR.bounce_room_key(row) == (0, 1, -5.0, -4.0, "B_R5_A")
    assert BR.bounce_room_key({"symbol": "PEND", "coverage": "pending"}) == (3, 2, 0.0, 0.0, "PEND")
    assert BR.bounce_room_key(None) == (3, 2, 0.0, 0.0, "")
    src = inspect.getsource(BR.bounce_room_key)
    assert "bouncing = 0 if bounce else 1" not in src, "the old first key"
    assert "(room_group(row),) + tuple(room_rank(row))" in src
    assert "-bounce_pct" in src and 'str((row or {}).get("symbol")' in src


def test_the_sorts_floor_is_the_phone_gates_constant_never_retyped():
    assert BR.ALERT_MIN_ROOM_PCT is AG.ALERT_MIN_ROOM_PCT
    src = inspect.getsource(BR)
    assert "from .alert_gates import ALERT_MIN_ROOM_PCT" in src
    assert "\nALERT_MIN_ROOM_PCT =" not in src
    body = "".join(inspect.getsource(f) for f in (BR.room_ok, BR.into_supply, BR.room_group))
    code = re.sub(r'"""[\s\S]*?"""', "", body)          # the docstrings may quote the boundary
    assert not re.search(r"\b5(\.0)?\b", code), "the floor must be read from alert_gates, not typed"


# ── 4. the ℹ️ Rules panel says reversal ─────────────────────────────────────
def test_the_rules_panel_reversal_read_says_reversal_not_bouncing():
    secs = RI.sections()
    for key in ("sepa_bounce", "catalysts"):
        first = secs[key]["picks"][0]
        assert first.startswith("Reversal off demand = a session low"), (key, first)
        assert "bounc" not in first.lower()
        # still built from the enforcing constants, never retyped
        assert ("%d sessions" % BR.LOOKBACK_SESSIONS) in first
        assert RI._pct(BR.BOUNCE_MIN_PCT) in first
    order_line = secs["sepa_bounce"]["picks"][-1]
    assert order_line.startswith("Order: a reversal off demand with")
    assert "then a reversal heading ⛔ into supply, then the rest" in order_line
    assert RI._pct(AG.ALERT_MIN_ROOM_PCT) in order_line
    # NEGATIVE: the wording moved; the read behind it did not.
    assert BR.LOOKBACK_SESSIONS == 5 and BR.BOUNCE_MIN_PCT == 3.0
