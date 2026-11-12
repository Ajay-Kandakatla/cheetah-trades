"""🥇 Luk's 🏁 — the R of a stop measured from the ACTUAL fill (spec rec157 WP-1, 2026-11-11).

Ajay 2026-11-11 (relayed by the main session): "Do your receommendations" — a stopped row's r = (stop − fill) / R, the
SAME arithmetic as the walk's r_of at the 9 EMA close exit; exit_px stays the alert's stop (no slippage model, no new
number). Already-graded docs are corrected at serve time by ONE helper (`luk.ledger.stop_r`), never by a Mongo write;
`walk()` writes the same value for new grades. Win / loss buckets never move (fill ≥ trigger > stop → R ≤ −1.0).

Every store is the in-memory FakeColl set; every bar is SYNTHETIC except the six plans of the worst live stops, read
once read-only from luk_ledger on 2026-11-12 (trigger / stop / fill_px as stored). NEGATIVES are marked.
"""
from __future__ import annotations

import ast
import inspect
import json
import math
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.luk import constants as LC
from chart_maps.luk import ledger as LL
from chart_maps.luk import store as LS
from chart_maps.luk import tape as LT
from scripts import luk_stop_r_before_after as S
from tests.test_luk_ledger import (B_WORD, D, D2, D4, EDGE, FILL, Fetch, Loader, _ledger_doc, _walk, alert_doc, bar,
                                   cache, et, flat, make_store, merge, pushed_doc, row_for)

SCRIPT = Path(S.__file__)
LEDGER_SRC = Path(LL.__file__)

# the six worst live stops from the fill (spec rec157 §1.2), stored plan + fill read 2026-11-12 (read-only):
# (id, trigger, stop, fill_px, R from the fill as the critic's probe measured it)
LIVE_WORST = [
    ("2026-11-06|RC|opening_range_high|aplus", 1.11, 1.105, 1.1898, -16.96),
    ("2026-11-09|FFTT|opening_range_high|aplus", 3.71, 3.7, 3.85, -15.0),
    ("2026-11-05|PRCT|opening_range_high|aplus", 21.76, 21.5201, 23.575, -8.5657),
    ("2026-11-02|HIHO|opening_range_high|aplus", 0.85, 0.8392, 0.924501, -7.8982),
    ("2026-11-02|RSI|pullback_reversal|aplus", 11.56, 11.5, 11.79, -4.8333),
    ("2026-11-10|CVM|opening_range_high|aplus", 1.44, 1.43, 1.475, -4.5),
]


def _fill(px, hh=10, mm=5):
    return dict(FILL, fill_px=px, fill_t=et(D, hh, mm).isoformat())


def _stop_walk(r=-1.0, hh=10, mm=12):
    return _walk(exit="stop", state="stopped", exit_t=et(D, hh, mm).isoformat(), exit_date=D.isoformat(), r=r,
                 sessions=1)


def _one(f, w, sym="STP", trig=10.0, stop=9.5):
    a = alert_doc(sym=sym, trig=trig, stop=stop)
    return make_store([a], [_ledger_doc(a, f, w)]), row_for(a)


def _block(st, span="all"):
    return LL.served_block(st, D4, et(D4, 20, 0), span=span)


def _row(b, sym="STP"):
    return next(r for dd in b["days"] for r in dd["rows"] if r["symbol"] == sym)


def day(d, bars, close=None, ema9=None):
    return {"date": d.isoformat(), "bars": bars, "close": close, "ema9_close": ema9}


# ── the helper ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_fill_on_the_trigger_is_exactly_minus_one_r_helper_walk_and_served():
    assert LL.stop_r(10.0, 9.5, 10.0) == -1.0
    w = LL.walk(row_for(alert_doc()), FILL, [day(D, [bar(D, 10, 5, 10, 10.1, 9.9, 10), bar(D, 10, 12, 9.8, 9.8, 9.4,
                                                                                         9.5)], 9.6, 9.0)])
    assert (w["exit"], w["r"], w["exit_px"]) == ("stop", -1.0, 9.5)
    st, _r = _one(FILL, _stop_walk())
    row = _row(_block(st))
    assert row["r"] == -1.0 and row["exit_text"] == "stopped 10:12 · −1.0R" and row["bucket"] == "loss"


def test_fill_above_the_trigger_loses_more_than_one_r_the_same_arithmetic_as_r_of():
    want = round((9.5 - 10.3) / (10.0 - 9.5), 4)
    assert LL.stop_r(10.0, 9.5, 10.3) == want == -1.6
    # a NEW stop: walk writes stop_r, exit_px stays the alert's stop
    row = row_for(alert_doc())
    f = _fill(10.3)
    ws = LL.walk(row, f, [day(D, [bar(D, 10, 5, 10.3, 10.4, 10.1, 10.3), bar(D, 10, 30, 9.8, 9.8, 9.4, 9.5)], 9.6,
                              9.0)])
    assert (ws["exit"], ws["state"], ws["exit_px"], ws["r"]) == ("stop", "stopped", 9.5, want)
    # the 9 EMA exit at a close EQUAL to the stop on the same plan + fill → r_of(9.5): the same number
    we = LL.walk(row, f, [day(D, [bar(D, 10, 5, 10.3, 10.4, 10.1, 10.3)], 9.5, 10.0)])
    assert we["exit"] == "ema9_close" and we["r"] == ws["r"]


def test_grade_step_on_a_new_stop_stores_the_r_from_the_fill(cache):
    st = make_store([alert_doc()])
    bars = merge(flat(D, (9, 30), (10, 5), 9.95), [bar(D, 10, 6, 10.3, 10.4, 10.2, 10.3)],
                 flat(D, (10, 7), (10, 59), 10.2), [bar(D, 11, 0, 9.8, 9.8, 9.4, 9.5)])
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: bars}), fetch_daily=Fetch(), clock=lambda: 0.0)
    assert out["written"] == 1
    doc = st.coll(GS.LEDGER).find_one({})
    assert doc["fill"]["fill_px"] == 10.3 and doc["walk"]["exit"] == "stop"
    assert doc["walk"]["r"] == LL.stop_r(10.0, 9.5, 10.3) == -1.6 and doc["walk"]["exit_px"] == 9.5


# ── legacy docs served corrected ─────────────────────────────────────────────────────────────────────────────────
def test_a_legacy_doc_is_served_from_the_fill_row_counts_and_text():
    st, _r = _one(_fill(12.41, 9, 47), _stop_walk(-1.0))
    b = _block(st)
    row = _row(b)
    assert row["r"] == -5.82 and row["exit_text"] == "stopped 10:12 · −5.8R"
    assert row["exit"]["text"] == row["exit_text"] and row["bucket"] == "loss"
    assert b["counts"]["mean_r_closed"] == -5.82 and b["counts"]["closed_negative"] == 1
    assert "mean -5.82R over 1 closed" in b["counts_text"]


def test_the_tape_read_line_reads_the_corrected_r():
    from tests.test_luk_tape import Loader as TapeLoader
    from tests.test_luk_tape import _bars
    a = alert_doc()
    st = make_store([a], [_ledger_doc(a, _fill(10.3), _walk(exit="stop", state="stopped",
                                                           exit_t=et(D, 10, 40).isoformat(), exit_date=D.isoformat(),
                                                           r=-1.0, sessions=1))])
    LT._MEMO.clear()
    try:
        p = LT.entry_tape(row_for(a)["id"], now=et(D2, 12, 0), store=st, load_day=TapeLoader({D: _bars()}),
                          today_load=lambda s, d: ([], False))
    finally:
        LT._MEMO.clear()
    assert "stopped 10:40 · −1.6R" in p["read"] and "−1.0R" not in p["read"]


def test_NEGATIVE_the_stored_walk_r_is_never_served_for_a_stop():
    st, _r = _one(_fill(10.3), _stop_walk(+9.0))
    row = _row(_block(st))
    assert row["r"] == LL.stop_r(10.0, 9.5, 10.3) == -1.6 and row["bucket"] == "loss"
    st2, _r = _one(FILL, _stop_walk(-3.3))
    assert _row(_block(st2))["r"] == -1.0


def test_NEGATIVE_a_9_ema_exit_row_is_unchanged_and_reads_its_stored_r():
    w = _walk(exit="ema9_close", state="ema9_close", exit_date=D2.isoformat(), r=2.3, sessions=2)
    for px in (10.0, 10.3):                                  # the fill never re-derives a 9 EMA row's R
        st, _r = _one(_fill(px), w)
        row = _row(_block(st))
        assert row["r"] == 2.3 and row["exit_text"] == "closed below the 9 EMA on 11-03 · +2.3R · 2 sessions"
        assert row["bucket"] == "win"


def test_NEGATIVE_open_pending_and_no_entry_rows_keep_their_r():
    st, _r = _one(FILL, _walk(r_now=0.8, sessions=1))
    row = _row(_block(st))
    assert row["state"] == "open" and row["r"] is None and row["r_now"] == 0.8
    a1, a2 = alert_doc(sym="PND"), alert_doc(sym="NOE")
    st2 = make_store([a1, a2], [_ledger_doc(a2, {"entry": "no_entry"}, None)])
    b = _block(st2)
    assert _row(b, "PND")["state"] == "pending" and _row(b, "PND")["r"] is None
    assert _row(b, "NOE")["state"] == "no_entry" and _row(b, "NOE")["r"] is None


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), True, False, "abc", "", [1]])
def test_NEGATIVE_a_bad_fill_is_none_never_minus_one_never_nan(bad):
    assert LL.stop_r(10.0, 9.5, bad) is None
    assert S.probe_stop_r(10.0, 9.5, bad) is None
    f = dict(FILL)
    f["fill_px"] = bad
    st, _r = _one(f, _stop_walk(float("nan")))
    b = _block(st)
    row = _row(b)
    assert row["state"] == "stopped" and row["r"] is None and row["bucket"] == "loss"
    assert row["exit_text"] == LL.EXIT_STOP_NO_R_TEXT.format(hhmm="10:12")
    assert row["exit_text"] == "stopped 10:12 · R not known — the fill is missing"
    assert b["counts"]["mean_r_closed"] is None and b["counts"]["closed_negative"] == 0
    assert "no closed row yet" in b["counts_text"]
    json.dumps(b, allow_nan=False, default=str)              # no NaN anywhere in the served block


def test_NEGATIVE_a_missing_fill_dict_serves_the_no_r_words():
    a = alert_doc(sym="STP")
    st = make_store([a], [dict(_ledger_doc(a, FILL, _stop_walk()), fill={"entry": "filled"})])
    row = _row(_block(st))
    assert row["r"] is None and row["exit_text"].endswith("R not known — the fill is missing")


@pytest.mark.parametrize("trig,stop,fill_px", [
    (10.0, 9.5, 9.5), (10.0, 9.5, 9.0),                      # fill at / under the stop
    (9.5, 9.5, 10.0), (9.0, 9.5, 10.0),                      # no risk / stop above the trigger
    (None, 9.5, 10.0), (10.0, None, 10.0), (0, 0, 1.0), (-1.0, -2.0, 1.0), (10.0, -0.5, 10.0),
    (float("nan"), 9.5, 10.0), (True, 0.5, 1.0), ("x", 9.5, 10.0),
])
def test_NEGATIVE_a_plan_that_is_not_ok_or_a_fill_at_or_under_the_stop_is_none(trig, stop, fill_px):
    assert LL.stop_r(trig, stop, fill_px) is None
    assert S.probe_stop_r(trig, stop, fill_px) is None


def test_NEGATIVE_buckets_never_move_over_a_grid_of_fills():
    a_stp, a_win = alert_doc(sym="STP"), alert_doc(sym="WIN", setup="inside_day_pdh")
    win_w = _walk(exit="ema9_close", state="ema9_close", exit_date=D2.isoformat(), r=2.3, sessions=2)
    base = None
    for px in (10.0, 10.0001, 10.01, 10.3, 11.0, 15.0, 123.45):
        st = make_store([a_stp, a_win], [_ledger_doc(a_stp, _fill(px), _stop_walk()), _ledger_doc(a_win, FILL, win_w)])
        b = _block(st)
        row = _row(b)
        assert row["bucket"] == "loss" and row["r"] <= -1.0, px
        c = b["counts"]
        ex = b["charts"]["counts"]["exit"]
        got = (c["closed_positive"], c["closed_negative"], c["stopped"], ex["win"], ex["loss"], ex["pct"],
               [k["n"] for k in b["categories"]])
        base = base or got
        assert got == base == (1, 1, 1, 1, 1, 50, got[-1]), px


def test_NEGATIVE_a_duplicate_stopped_row_stays_out_of_the_mean():
    a1 = pushed_doc(sym="VG", setup="pullback_reversal", at=et(D, 9, 41), trig=14.50, stop=13.96)
    a2 = pushed_doc(sym="VG", setup="opening_range_high", at=et(D, 9, 46), trig=14.80, stop=13.96)
    w = _walk(exit="stop", state="stopped", exit_t=et(D, 10, 6).isoformat(), exit_date=D.isoformat(), r=-1.0,
              sessions=1)
    led = [_ledger_doc(a1, dict(FILL, fill_px=14.50, fill_t=et(D, 9, 43).isoformat()), w),
           _ledger_doc(a2, dict(FILL, fill_px=15.50, fill_t=et(D, 9, 48).isoformat()), w)]
    b = _block(make_store([a1, a2], led))
    rows = {r["setup"]: r for dd in b["days"] for r in dd["rows"]}
    dup = rows["opening_range_high"]
    assert dup["dup_of"] == rows["pullback_reversal"]["id"]
    assert dup["r"] == LL.stop_r(14.80, 13.96, 15.50) < -1.0          # listed with its own R ...
    assert b["counts"]["mean_r_closed"] == -1.0 and b["counts"]["dup"] == 1   # ... never in the mean


# ── the read-only before / after script ──────────────────────────────────────────────────────────────────────────
def test_probe_stop_r_equals_the_helper_over_a_grid_and_the_six_worst_live_stops():
    grid = [(t, s, f) for t in (0.85, 1.11, 3.71, 10.0, 21.76, 123.4567)
            for s in (t * 0.5, t - 0.01, t * 0.995, t * 0.9)
            for f in (t, t + 0.0001, t * 1.0072, t * 1.0719, t * 1.1011, t * 2)]
    for t, s, f in grid:
        assert S.probe_stop_r(t, s, f) == LL.stop_r(t, s, f), (t, s, f)
    for _id, t, s, f, measured in LIVE_WORST:
        assert S.probe_stop_r(t, s, f) == LL.stop_r(t, s, f) == measured, _id


def test_fill_over_trigger_pct():
    assert S.fill_over_trigger_pct(10.0, 10.0) == 0.0
    assert S.fill_over_trigger_pct(1.11, 1.1898) == pytest.approx(7.1892, abs=1e-4)
    for t, f in ((None, 1.0), (1.0, None), (float("nan"), 1.0), (1.0, float("inf")), (True, 1.0), (1.0, False),
                 (0, 1.0), (-1.0, 1.0), ("x", 1.0)):
        assert S.fill_over_trigger_pct(t, f) is None, (t, f)                 # NEGATIVE


def test_quartiles_split_by_index_with_ties_broken_by_id():
    rows68 = [{"id": f"r{i:02d}", "pct": float(i % 7), "r": -1.0} for i in range(68)]
    assert [q["n"] for q in S.quartiles(rows68)] == [17, 17, 17, 17]
    rows10 = [{"id": f"r{i}", "pct": 1.0, "r": float(-i)} for i in range(10)]
    q = S.quartiles(list(reversed(rows10)))
    assert [x["n"] for x in q] == [2, 3, 2, 3]
    assert q[0]["sum_r"] == -1.0 and q[1]["sum_r"] == -9.0               # r0 + r1, then r2 + r3 + r4: by id
    assert S.quartiles(rows10) == q                                       # deterministic whatever the input order
    assert [x["n"] for x in S.quartiles([{"id": "a", "pct": None, "r": -1.0}])] == [0, 0, 0, 0]   # NEGATIVE


def _drow(i, r, pct, r_pct, frr):
    return {"id": f"x{i}", "r": r, "pct": pct, "r_pct": r_pct, "fill_risk_r": frr}


def test_decompose_bands_partition_and_the_cuts_are_the_named_constants():
    nc, thin = LC.LUK_NO_CHASE_PCT, GC.LEDGER_MIN_R_PCT
    rows = [_drow(0, -1.0, 0.0, 2.0, -1.0), _drow(1, -1.2, nc / 10, 1.0, -1.0),
            _drow(2, -2.0, nc, thin, -1.0),                  # exactly at the no-chase cut → "at most"; R% == cut → not thin
            _drow(3, -9.0, nc * 2, thin / 2, -1.0),          # thin
            _drow(4, 2.0, 0.0, 3.0, 1.5), _drow(5, None, 9.0, 1.0, -1.0)]          # r None → out of every sum
    d = S.decompose(rows, nc, thin)
    assert d["all"] == {"n": 5, "sum_r": -11.2, "mean_r": -2.24}
    parts = (d["on_trigger"], d["at_most_no_chase"], d["over_no_chase"])
    assert [p["n"] for p in parts] == [2, 2, 1]
    assert sum(p["sum_r"] for p in parts) == pytest.approx(d["all"]["sum_r"]) and d["pct_missing"] == 0
    assert d["thin"] == ["x3"] and d["without_thin"] == {"n": 4, "sum_r": -2.2, "mean_r": -0.55}
    assert d["no_chase_pct"] == nc and d["thin_cut"] == thin
    assert d["fill_risk_mean_r"] == pytest.approx((-1.0 * 4 + 1.5) / 5)
    assert d["top2_share_pct"] == round((-9.0 - 2.0) / -11.2 * 100, 2)
    assert S.fill_risk_r("stopped", 9.5, 12.0, 9.5) == -1.0                 # every stop −1.0 in that display
    assert S.fill_risk_r("ema9_close", 11.0, 10.0, 9.5) == 2.0
    assert S.fill_risk_r("ema9_close", 11.0, 9.5, 9.5) is None              # NEGATIVE: no risk
    assert S.fill_risk_r("open", 11.0, 10.0, 9.5) is None                   # NEGATIVE: not closed


def test_NEGATIVE_the_script_reads_the_cuts_by_name_and_never_the_capped_days():
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    floats = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert 3.0 not in floats and 0.5 not in floats and float(LC.LUK_NO_CHASE_PCT) not in floats
    assert float(GC.LEDGER_MIN_R_PCT) not in floats
    attrs = {(n.value.id, n.attr) for n in ast.walk(tree) if isinstance(n, ast.Attribute)
             and isinstance(n.value, ast.Name)}
    assert ("LC", "LUK_NO_CHASE_PCT") in attrs and ("GC", "LEDGER_MIN_R_PCT") in attrs
    subs = [n.slice.value for n in ast.walk(tree) if isinstance(n, ast.Subscript)
            and isinstance(n.slice, ast.Constant)]
    assert "days" not in subs and '"days"' not in src and "'days'" not in src
    assert ("LL", "stop_r") not in attrs and "import stop_r" not in src     # the container runs origin/main
    head = src.split("def main(")[0]                                         # import-safe: no Mongo at import
    assert "pymongo" not in src and "chart_maps" not in "".join(
        ast.unparse(n) for n in ast.parse(head).body if isinstance(n, (ast.Import, ast.ImportFrom)))


def _fake_dry_store(monkeypatch, st):
    st.writes = []
    monkeypatch.setattr(LS, "dry_store", lambda *a, **k: st)


def test_the_script_main_runs_the_uncapped_pipeline_and_asserts_the_served_counts(monkeypatch, capsys):
    a1, a2 = alert_doc(sym="STP"), alert_doc(sym="EMA", setup="inside_day_pdh")
    led = [_ledger_doc(a1, _fill(12.41, 9, 47), _stop_walk()),
           _ledger_doc(a2, FILL, _walk(exit="ema9_close", state="ema9_close", exit_date=D2.isoformat(), r=2.3,
                                       sessions=2))]
    _fake_dry_store(monkeypatch, make_store([a1, a2], led))
    monkeypatch.setattr(LL, "stop_r", lambda *a: -1.0)      # what origin/main serves today: the stored −1.0
    assert S.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["served_counts_equal"] is True and out["writes"] == []
    assert out["before"]["sum_r"] == 1.3 and out["after"]["sum_r"] == pytest.approx(2.3 - 5.82)
    assert out["before"]["n_closed"] == out["after"]["n_closed"] == 2
    assert (out["after"]["wins"], out["after"]["losses"]) == (out["before"]["wins"], out["before"]["losses"]) == (1, 1)
    assert out["stops"] == 1 and out["stops_exactly_minus_one"] == 0 and out["buckets_changed"] == 0
    assert out["served_equals_fill_based"] is False and out["worst"][0]["after"] == -5.82
    assert out["decomposition"]["no_chase_pct"] == LC.LUK_NO_CHASE_PCT
    assert out["after"]["per_session"] == {D.isoformat(): {"n": 2, "sum_r": pytest.approx(-3.52)}}
    md = S.md_table(out)
    assert "| sum R (derived from rows) | +1.30 | -3.52 |" in md and "HIS CALL" in md


def test_after_the_deploy_the_served_r_equals_the_fill_based_r(monkeypatch, capsys):
    st, _r = _one(_fill(12.41, 9, 47), _stop_walk())
    _fake_dry_store(monkeypatch, st)
    assert S.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["served_equals_fill_based"] is True and out["before"] == out["after"]


def test_NEGATIVE_a_counts_mismatch_exits_1(monkeypatch, capsys):
    st, _r = _one(FILL, _stop_walk())
    _fake_dry_store(monkeypatch, st)
    real = LL.served_block
    monkeypatch.setattr(LL, "served_block", lambda *a, **k: dict(real(*a, **k), counts={"n": -1}))
    assert S.main() == 1
    cap = capsys.readouterr()
    assert json.loads(cap.out)["served_counts_equal"] is False and "counts" in cap.err


def test_NEGATIVE_an_attempted_write_exits_1(monkeypatch, capsys):
    st, _r = _one(FILL, _stop_walk())
    _fake_dry_store(monkeypatch, st)
    st.writes.append(("luk_ledger", "update_one"))
    assert S.main() == 1



def test_NEGATIVE_md_table_prints_failed_when_the_served_counts_assert_failed(monkeypatch, capsys):
    st, _r = _one(_fill(12.41, 9, 47), _stop_walk())
    _fake_dry_store(monkeypatch, st)
    assert S.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert "served-block counts assert: held" in S.md_table(out)
    out["served_counts_equal"] = False
    md = S.md_table(out)
    assert "served-block counts assert: FAILED" in md and "assert: held" not in md


DOC = Path(__file__).resolve().parents[2] / "docs" / "luk" / "stop_r_from_fill_2026_11_11.md"


def test_the_doc_carries_the_live_run_after_the_close_and_names_the_moved_rows():
    doc = DOC.read_text(encoding="utf-8")
    assert "PENDING" not in doc                                               # NEGATIVE: step 7 is done
    assert "served-block counts assert: held" in doc
    assert "| fill above the trigger by more than LC.LUK_NO_CHASE_PCT % | 28 | -95.25 | -3.402 |" in doc
    assert "carry\n−95.25R of −138.48R" in doc or "carry −95.25R of −138.48R" in doc
    assert "| all | 88 | -138.48 | -1.574 |" in doc
    for sym in ("NXT", "DNUT", "ATGL", "EMBJ", "TH", "AVX", "BLZE", "CORZ", "ELMT", "EPRX", "NVTS", "SKHY", "VSH",
                "WOLF", "WULF", "ASST", "FLD", "GDS", "ASX", "FLX"):           # the 20 rows that closed since 11-11
        assert re.search(rf"\b{sym}\b", doc), sym
    live = doc.split("### The script's run after the close")[1].split("## Every reader")[0]
    assert "−70.55R of −107.59R" in live and "At the 11-11 close" in live    # the old line kept only as history
    assert "carry −70.55R" not in doc.replace("\n", " ")                    # NEGATIVE: not the live claim any more


# ── source pins ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_ledger_holds_no_minus_one_literal_and_cells_never_reads_the_stored_stop_r():
    src = LEDGER_SRC.read_text(encoding="utf-8")
    assert not re.search(r"\br\s*=\s*-1\.0\b", src)
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "cells")
    stopped = next(n for n in ast.walk(fn) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                   and isinstance(n.test.comparators[0], ast.Constant) and n.test.comparators[0].value == "stopped")
    body = "\n".join(ast.unparse(s) for s in stopped.body)
    assert "w['r']" not in body and 'w["r"]' not in body and "stop_r(" in body
    assert "stop_r" in LL.__all__ and inspect.signature(LL.stop_r).parameters.keys() == {"trigger", "stop", "fill_px"}


def test_the_served_words_no_longer_say_every_stop_is_one_r():
    words = " ".join([LL.RULE_TEXT, LL.CHARTS_HONESTY, LL.EXIT_STOP_NO_R_TEXT, LL.__doc__, LL.bucket_of.__doc__,
                      LL.walk.__doc__])
    assert "every stop is one R down" not in words and "r = −1.0 exactly" not in words
    assert "(every stop is −1.0)" not in words
    assert "the R of a stop is measured from the actual fill" in LL.rule_text()
    assert "a stop is one R down or more, measured from the actual fill" in LL.CHARTS_HONESTY
    for s in (LL.RULE_TEXT, LL.CHARTS_HONESTY, LL.EXIT_STOP_NO_R_TEXT):
        assert not B_WORD.search(s) and not EDGE.search(s)
    assert not re.search(r"\d", LL.EXIT_STOP_NO_R_TEXT.replace("{hhmm}", ""))   # MINE words carry no number


def test_NEGATIVE_no_nan_in_a_stop_r():
    for t, s, f in ((1e-9, 0.0, 1.0), (1e9, 1.0, 2e9), (0.0001, 0.00005, 0.0002)):
        v = LL.stop_r(t, s, f)
        assert v is None or math.isfinite(v)
