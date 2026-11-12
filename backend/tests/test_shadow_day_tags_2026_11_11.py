"""Shadow day tags (rec157 WP-2, 2026-11-11) — the pin, the read times, the MISSING rules, the store, the gaps, the
killed run, the market-day walk, the copied engine and the source guards. Hermetic: every write goes under tmp_path,
no Mongo, no docker, no network (the probe's Mongo reads are fed fake collections).

The pin: the study's 22 sessions × 8 tag-forms (STUDY/days.csv, copied verbatim into
fixtures/gajjala/shadow_day_tags_days_2026_11_11.csv) recomputed from fixtures/gajjala/shadow_day_tags_inputs_2026_11_11
.json (the study's own inputs reduced to the probe's shape by `shadow_day_tags.py --build-fixture`)."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import os
import re
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import shadow_day_tags as CLI
from scripts import shadow_day_tags_lib as LIB

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
FIX = BACKEND / "tests" / "fixtures" / "gajjala"
INPUTS_FIX = FIX / "shadow_day_tags_inputs_2026_11_11.json"
DAYS_FIX = FIX / "shadow_day_tags_days_2026_11_11.csv"
PREREG = FIX / "shadow_day_tags_prereg_2026_11_11.md"
PREREG_SHA = FIX / "shadow_day_tags_prereg_2026_11_11.md.sha256"
DOC = REPO / "docs" / "gajjala" / "shadow_day_tags_2026_11_11.md"
STUDY = Path("/Users/ajay/clinet-test/eod-audits/research/2026-11-11_track_record_patterns")
PKG_FILES = [BACKEND / "scripts" / "shadow_day_tags_probe.py", BACKEND / "scripts" / "shadow_day_tags_lib.py",
             BACKEND / "scripts" / "shadow_day_tags.py", BACKEND / "tests" / "test_shadow_day_tags_2026_11_11.py",
             INPUTS_FIX, DAYS_FIX, PREREG, PREREG_SHA, DOC]
ET = ZoneInfo("America/New_York")
UTC = timezone.utc


def _probe():
    from scripts import shadow_day_tags_probe as PR             # pymongo + chart_maps: host venv and api image
    return PR


def _consts():
    from chart_maps.gajjala import audited_rules as AR, constants as GC
    from trading import gajjala_entry as GE
    return {"T2_FIRST_HOUR_END_ET": AR.T2_FIRST_HOUR_END_ET.strftime("%H:%M"), "LEDGER_MIN_R_PCT": GC.LEDGER_MIN_R_PCT,
            "GG_LOSS_RISK_CUT": GE.GG_LOSS_RISK_CUT, "ET_RTH_OPEN": "09:30",
            "MEASURE_FLOOR_WEEKS": AR.MEASURE_FLOOR_WEEKS}


@pytest.fixture(scope="module")
def fixture_inputs():
    return json.loads(INPUTS_FIX.read_text())


# ── synthetic inputs ────────────────────────────────────────────────────────────────────────────────────────────────
def weekdays(a: str, b: str, closed=("2026-11-26",)) -> list:
    """weekdays a … b minus the given closed days (what the probe's is_market_day walk hands the lib)."""
    out, d = [], date.fromisoformat(a)
    while d <= date.fromisoformat(b):
        if d.weekday() < 5 and d.isoformat() not in closed:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def utc_of(d: str, h: int, m: int, s: int = 0) -> str:
    return datetime.combine(date.fromisoformat(d), dtime(h, m, s), tzinfo=ET).astimezone(UTC).isoformat()


def mk_inputs(sessions, closed=None, rows=None, passes=None, intra=None, iwm_rows=None, pillars=None, today=None):
    return {"generated_utc": "2026-11-30T22:00:00+00:00", "today_et": today or (closed or sessions[-1]),
            "sessions": list(sessions), "last_closed_session": closed or sessions[-1], "constants": _consts(),
            "gg5_rows": [] if rows is None else rows, "gg5_rows_error": None, "passes": passes or {},
            "index_intraday": intra or {}, "iwm_daily": {"rows": iwm_rows or [], "cached_at": 1.0},
            "pillars": pillars or {}, "asof": {"gg5_last_graded_at": None}}


def row(d, kind="aplus", bucket="loss", outcome="loss", fill_t=None, exit_t=None, line="live", thin=False,
        dup_of=None, plan="ok", at_utc=None, fill_px=10.0, trigger=10.0, stop=9.0, state_same=None, state_next="pending"):
    same = {"fill_t": fill_t or utc_of(d, 10, 0), "exit_t": exit_t or utc_of(d, 10, 5), "end_t": utc_of(d, 16, 0),
            "outcome": outcome, "fill_px": fill_px, "close_pct": 0.0}
    return {"id": "%s|X|s|%s" % (d, kind), "date": d, "symbol": "X", "setup": "s", "kind": kind, "line": line,
            "at_utc": at_utc or utc_of(d, 9, 50), "trigger": trigger, "stop": stop, "thin": thin, "plan": plan,
            "same": same, "next": None, "state_same": state_same or outcome, "state_next": state_next,
            "bucket": bucket, "dup_of": dup_of}


def pas(d, hm, n=100):
    return {"id": "%s|%s" % (d, hm), "date": d, "at": None, "strip": {"n_population": n}}


def bars(d, opn, last, extra=()):
    """two rth bars: 09:30 opens at `opn`; 10:29 (closes 10:30) closes at `last`."""
    b = [[utc_of(d, 9, 30)[:19], opn, opn, opn, opn, 1.0, "rth"], [utc_of(d, 10, 29)[:19], last, last, last, last, 1.0, "rth"]]
    return b + [list(x) for x in extra]


def run_cli(tmp_path, inputs, *extra):
    p = tmp_path / ("in_%d.json" % len(list(tmp_path.glob("in_*.json"))))
    p.write_text(json.dumps(inputs))
    out = tmp_path / "store"
    args = ["--from-json", str(p), "--out", str(out)] + list(extra)
    rc = CLI.main(args)
    return rc, out


def summary(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


# ── the pin ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_pin_22_sessions_x_8_forms_equal_days_csv(fixture_inputs):
    res = LIB.compute_all(fixture_inputs, fixture_inputs["sessions"])
    rows = list(csv.DictReader(DAYS_FIX.open(newline="")))
    assert [r["date"] for r in rows] == fixture_inputs["sessions"] and len(rows) == 22
    n_ok = n_missing = 0
    for r in rows:
        for f in LIB.TAG_FORMS:
            t, v, o = res[r["date"]][f], r[f + "_value"], r[f + "_on"]
            if v == "" and o == "":
                assert t["status"] == "missing" and t["on"] is None and t["value"] is None, (r["date"], f, t)
                n_missing += 1
            else:
                assert t["status"] == "ok", (r["date"], f, t)
                assert t["on"] is (o == "1"), (r["date"], f, t)
                assert str(t["value"]) == v, (r["date"], f, t["value"], v)
                n_ok += 1
    assert n_ok + n_missing == 22 * 8 and n_missing > 0 and n_ok > 0


def test_fixture_is_the_study_reduced_and_names_its_sources(fixture_inputs):
    assert fixture_inputs["sessions"][0] == "2026-10-13" and fixture_inputs["last_closed_session"] == "2026-11-11"
    assert set(fixture_inputs["fixture_sources"]) == {"rows.json", "gg5_strip_snapshot_2026-11-11.json",
                                                      "day_probe.json"}
    assert INPUTS_FIX.stat().st_size < 700_000
    if STUDY.is_dir():
        for n, sha in fixture_inputs["fixture_sources"].items():
            assert hashlib.sha256((STUDY / n).read_bytes()).hexdigest() == sha, n


def test_fixture_constants_equal_the_repo_by_name(fixture_inputs):
    from chart_maps.gajjala import audited_rules as AR, constants as GC
    from chart_maps.luk import constants as LC
    from trading import gajjala_entry as GE
    c = fixture_inputs["constants"]
    assert c["T2_FIRST_HOUR_END_ET"] == AR.T2_FIRST_HOUR_END_ET.strftime("%H:%M")
    assert c["GG_LOSS_RISK_CUT"] == GE.GG_LOSS_RISK_CUT
    assert c["LEDGER_MIN_R_PCT"] == GC.LEDGER_MIN_R_PCT
    assert c["MEASURE_FLOOR_WEEKS"] == AR.MEASURE_FLOOR_WEEKS == LC.MEASURE_FLOOR_WEEKS


# ── read times [C9] ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_gd4_pre_cut_equals_et_rth_open_read_by_ast():
    PR = _probe()
    v = PR.ast_constant(str(BACKEND / "daytrading" / "data.py"), "ET_RTH_OPEN")
    assert v == "09:30" == LIB.hm_text(LIB.GD4_PRE_CUT)
    assert PR.ast_constant(str(BACKEND / "trading" / "gajjala_entry.py"), "GG_LOSS_RISK_CUT") == _consts()["GG_LOSS_RISK_CUT"]
    assert LIB.hm_text(LIB.PRE_CUT) == "09:29" == PR.PRE_CUT.strftime("%H:%M")
    with pytest.raises(KeyError):
        PR.ast_constant(str(BACKEND / "daytrading" / "data.py"), "NOT_A_NAME")


def test_upper_median():
    assert LIB.upper_median([1, 2, 3, 4]) == 3          # NOT 2.5
    assert LIB.upper_median([1, 2, 3]) == 2
    assert LIB.upper_median([4, 1, 3, 2]) == 3


def _gd4_inputs(exit_hms):
    ss = weekdays("2026-11-12", "2026-11-13")
    d = ss[1]
    return mk_inputs(ss, rows=[row(d, exit_t=utc_of(d, *exit_hms), fill_t=utc_of(d, 9, 0))]), d


def test_gd4_pre_exit_at_092930_counts_093000_does_not():
    inp, d = _gd4_inputs((9, 29, 30))
    t = LIB.compute(inp, d)
    assert t["GD4_pre"]["value"] == 0.5 and t["GD4_pre"]["on"] is True
    inp, d = _gd4_inputs((9, 30, 0))
    t = LIB.compute(inp, d)
    assert t["GD4_pre"]["value"] == 1.0 and t["GD4_pre"]["on"] is False       # strict: an exit AT the cut never counts
    assert t["GD4_by1030"]["value"] == 0.5


def test_gd4_exit_after_the_cut_never_moves_the_tag():
    inp, d = _gd4_inputs((10, 30, 0))
    t = LIB.compute(inp, d)
    assert t["GD4_pre"]["value"] == 1.0 and t["GD4_by1030"]["value"] == 1.0


def test_gd4_loss_halves_win_resets_flat_keeps_open_never_counts():
    ss = weekdays("2026-11-12", "2026-11-17")
    d0, d1, d2, d3 = ss[0], ss[1], ss[2], ss[3]
    rows = [row(d0, exit_t=utc_of(d0, 11, 0)), row(d1, exit_t=utc_of(d1, 11, 0))]
    t = LIB.compute(mk_inputs(ss, rows=rows), d2)["GD4_pre"]
    assert t["value"] == 0.25 and t["on"] is True and t["detail"]["events"] == 2
    rows.append(row(d2, bucket="win", outcome="win", exit_t=utc_of(d2, 11, 0)))
    t = LIB.compute(mk_inputs(ss, rows=rows), d3)["GD4_pre"]
    assert t["value"] == 1.0 and t["on"] is False                                  # a win resets
    rows2 = rows[:2] + [row(d2, bucket="flat", outcome="flat", state_same="flat", exit_t=utc_of(d2, 11, 0)),
                        row(d2, bucket="open", outcome=None, state_same="open", exit_t=utc_of(d2, 11, 0))]
    t = LIB.compute(mk_inputs(ss, rows=rows2), d3)["GD4_pre"]
    assert t["value"] == 0.25 and t["detail"]["events"] == 2                       # flat / open A+ never fold
    assert LIB.risk_after_copy(0.25, 0.0, 0.5) == 0.25                              # a flat keeps


def test_gd4_potentials_shadow_and_dups_never_fold():
    ss = weekdays("2026-11-12", "2026-11-13")
    d0, d1 = ss
    rows = [row(d0, kind="potential", exit_t=utc_of(d0, 11, 0)), row(d0, line="shadow", exit_t=utc_of(d0, 11, 0)),
            row(d0, dup_of="x", exit_t=utc_of(d0, 11, 0)), row(d0, plan="no", exit_t=utc_of(d0, 11, 0))]
    assert LIB.compute(mk_inputs(ss, rows=rows), d1)["GD4_pre"]["value"] == 1.0


# ── GD6b ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _gd6_inputs(target_hm="09:29", n_hist=5, target_n=50, hist_n=(10, 20, 30, 40, 60), strip=True):
    ss = weekdays("2026-11-02", "2026-11-13")
    d = ss[-1]
    passes = {}
    for x, n in zip(ss[-1 - n_hist:-1], hist_n):
        passes[x] = {"09:29": pas(x, "09:29", n), "10:30": pas(x, "10:30", n)}
    tp = pas(d, target_hm, target_n)
    if not strip:
        tp["strip"] = None
    passes[d] = {"09:29": tp, "10:30": pas(d, "10:30", target_n)}
    return mk_inputs(ss, passes=passes), d


def test_gd6b_pass_31_minutes_old_is_missing_30_is_ok():
    inp, d = _gd6_inputs(target_hm="08:58")
    t = LIB.compute(inp, d)["GD6b_pre"]
    assert t["status"] == "missing" and t["on"] is None and "31 min" in t["why"]
    inp, d = _gd6_inputs(target_hm="08:59")
    assert LIB.compute(inp, d)["GD6b_pre"]["status"] == "ok"


def test_gd6b_no_population_is_missing_never_false():
    inp, d = _gd6_inputs(target_n=0)
    t = LIB.compute(inp, d)["GD6b_pre"]
    assert t["status"] == "missing" and t["on"] is None
    inp, d = _gd6_inputs(strip=False)
    assert LIB.compute(inp, d)["GD6b_pre"]["status"] == "missing"
    inp, d = _gd6_inputs()
    inp["passes"][d]["09:29"] = None
    t = LIB.compute(inp, d)["GD6b_pre"]
    assert t["status"] == "missing" and "no pass" in t["why"]


def test_gd6b_four_history_values_missing_five_ok_and_median_is_upper_strict():
    inp, d = _gd6_inputs(n_hist=4, hist_n=(10, 20, 30, 40))
    assert LIB.compute(inp, d)["GD6b_pre"]["status"] == "missing"
    inp, d = _gd6_inputs(n_hist=5, hist_n=(10, 20, 30, 40, 60), target_n=29)
    t = LIB.compute(inp, d)["GD6b_pre"]
    assert t["status"] == "ok" and t["detail"]["median"] == 30 and t["on"] is True
    inp, d = _gd6_inputs(n_hist=5, hist_n=(10, 20, 30, 40, 60), target_n=30)
    assert LIB.compute(inp, d)["GD6b_pre"]["on"] is False                      # v == median → off
    inp, d = _gd6_inputs(n_hist=6, hist_n=(10, 20, 30, 40, 60, 70), target_n=39)
    t = LIB.compute(inp, d)["GD6b_pre"]
    assert t["detail"]["median"] == 40 and t["on"] is True                      # the UPPER middle of six


class _Cur(list):
    def sort(self, *a, **k):
        return self

    def limit(self, *a):
        return self


class _Coll:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q=None, proj=None):
        q = q or {}
        return _Cur([d for d in self.docs if all(d.get(k) == v for k, v in q.items() if not isinstance(v, dict))])

    def find_one(self, q=None, proj=None):
        r = self.find(q, proj)
        return r[0] if r else None


class _DB(dict):
    def __getitem__(self, k):
        return self.get(k) or _Coll([])

    def __getattr__(self, k):
        return self[k]


def test_probe_reads_the_last_pass_at_or_before_the_cut_never_a_pointer():
    PR = _probe()
    d = "2026-11-13"
    docs = [{"_id": "%s|09:29" % d, "date": d, "at": "a1", "strip": {"n_population": 11}},
            {"_id": "%s|09:30" % d, "date": d, "at": "a2", "strip": {"n_population": 22}},
            {"_id": "%s|09:31:05|open" % d, "date": d, "at": "a3", "strip": {"n_population": 33}},
            {"_id": "latest", "date": d, "at": "a9", "strip": {"n_population": 99}},
            {"_id": "latest_cron", "date": d, "at": "a9", "pointer": "x", "strip": {"n_population": 98}},
            {"_id": "%s|10:31" % d, "date": d, "at": "a4", "strip": {"n_population": 44}}]
    out, last = PR.passes_of(_DB({"gajjala_passes": _Coll(docs)}), [d])
    assert out[d]["09:29"]["id"] == "%s|09:29" % d and out[d]["09:29"]["strip"] == {"n_population": 11}
    assert out[d]["10:30"]["id"] == "%s|09:31:05|open" % d                        # 10:31 is after the cut
    assert last == "%s|10:31" % d
    out, _ = PR.passes_of(_DB({"gajjala_passes": _Coll(docs[1:])}), [d])
    assert out[d]["09:29"] is None                                               # 09:30 is NOT read at 09:29


# ── GD7 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _gd7(q, i):
    ss = weekdays("2026-11-12", "2026-11-13")
    d = ss[1]
    intra = {}
    if q is not None:
        intra["QQQ|" + d] = bars(d, 100.0, q)
    if i is not None:
        intra["IWM|" + d] = bars(d, 100.0, i)
    return LIB.compute(mk_inputs(ss, intra=intra), d)["GD7_by1030"]


def test_gd7_missing_both_red_on_one_green_off():
    t = _gd7(None, 99.0)
    assert t["status"] == "missing" and t["on"] is None and "QQQ" in t["why"]
    t = _gd7(99.0, 99.5)
    assert t["on"] is True and t["value"] == "QQQ -1.00% IWM -0.50%"
    assert _gd7(99.0, 100.5)["on"] is False
    assert _gd7(100.0, 99.0)["on"] is False                                      # flat is not red


def test_gd7_a_bar_starting_at_1030_is_never_read():
    ss = weekdays("2026-11-12", "2026-11-13")
    d = ss[1]
    late = [utc_of(d, 10, 30)[:19], 50.0, 50.0, 50.0, 50.0, 1.0, "rth"]
    intra = {"QQQ|" + d: bars(d, 100.0, 101.0, [late]), "IWM|" + d: bars(d, 100.0, 101.0, [late])}
    t = LIB.compute(mk_inputs(ss, intra=intra), d)["GD7_by1030"]
    assert t["on"] is False and t["value"] == "QQQ +1.00% IWM +1.00%"
    PR = _probe()
    doc = {"symbol": "QQQ", "date": d, "bars": [
        {"ts_utc": utc_of(d, 9, 30)[:19], "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "session": "rth"},
        {"ts_utc": utc_of(d, 10, 29)[:19], "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "session": "rth"},
        {"ts_utc": utc_of(d, 10, 30)[:19], "open": 3, "high": 3, "low": 3, "close": 3, "volume": 1, "session": "rth"},
        {"ts_utc": utc_of(d, 9, 0)[:19], "open": 4, "high": 4, "low": 4, "close": 4, "volume": 1,
         "session": "premarket"}]}
    out = PR.index_intraday(_DB({"intraday_cache": _Coll([doc])}), [d])
    assert [b[4] for b in out["QQQ|" + d]] == [1, 2]
    assert out["IWM|" + d] is None                                              # an absent doc → None


# ── GD3w ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _gd3w_rows(ss, outcomes, **kw):
    return [row(ss[k], kind="potential", outcome=o, bucket=o, **kw) for k, o in enumerate(outcomes)]


def test_gd3w_fewer_than_five_prior_sessions_missing():
    ss = weekdays("2026-11-12", "2026-11-19")
    t = LIB.compute(mk_inputs(ss, rows=_gd3w_rows(ss, ["loss"] * 4)), ss[4])["GD3w_pre"]
    assert t["status"] == "missing" and t["on"] is None
    t = LIB.compute(mk_inputs(ss, rows=_gd3w_rows(ss, ["loss"] * 5)), ss[5])["GD3w_pre"]
    assert t["status"] == "ok" and t["value"] == 1.0 and t["on"] is True


def test_gd3w_no_decided_rows_missing_and_exactly_half_is_off():
    ss = weekdays("2026-11-12", "2026-11-19")
    t = LIB.compute(mk_inputs(ss, rows=[]), ss[5])["GD3w_pre"]
    assert t["status"] == "missing" and "== 0" in t["why"]
    t = LIB.compute(mk_inputs(ss, rows=_gd3w_rows(ss, ["loss", "win", "loss", "win", "flat"])), ss[5])["GD3w_pre"]
    assert t["value"] == 0.5 and t["on"] is False                                 # 0.5 is not > 0.5


def test_gd3w_excludes_thin_shadow_and_dups():
    ss = weekdays("2026-11-12", "2026-11-19")
    base = _gd3w_rows(ss, ["win"] * 5)
    noise = (_gd3w_rows(ss, ["loss"] * 5, thin=True) + _gd3w_rows(ss, ["loss"] * 5, line="shadow")
             + _gd3w_rows(ss, ["loss"] * 5, line="replayed") + _gd3w_rows(ss, ["loss"] * 5, dup_of="y"))
    t = LIB.compute(mk_inputs(ss, rows=base + noise), ss[5])["GD3w_pre"]
    assert t["value"] == 0.0 and t["detail"] == {"failed": 0, "held": 5, "window": ss[:5]}


def test_gg5_rows_unreadable_is_missing():
    ss = weekdays("2026-11-12", "2026-11-19")
    inp = mk_inputs(ss)
    inp["gg5_rows"] = None
    t = LIB.compute(inp, ss[5])
    assert t["GD3w_pre"]["status"] == t["GD4_pre"]["status"] == t["GD4_by1030"]["status"] == "missing"


# ── LD3i / LD9 ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ld3i_frame_older_than_the_previous_session_missing_and_equal_emas_off():
    ss = weekdays("2026-11-12", "2026-11-16")
    t = LIB.compute(mk_inputs(ss, iwm_rows=[["2026-11-12", 1.0, 2.0, 3.0]]), ss[2])["LD3i_pre"]
    assert t["status"] == "missing" and t["on"] is None                         # prev = 11-13, frame ends 11-12
    t = LIB.compute(mk_inputs(ss, iwm_rows=[["2026-11-13", 1.0, 2.0, 3.0]]), ss[2])["LD3i_pre"]
    assert t["value"] == -1.0 and t["on"] is True
    t = LIB.compute(mk_inputs(ss, iwm_rows=[["2026-11-13", 1.0, 2.0, 2.0]]), ss[2])["LD3i_pre"]
    assert t["on"] is False and t["value"] == 0.0
    t = LIB.compute(mk_inputs(ss, iwm_rows=[["2026-11-12", 1.0, 2.0, 3.0]]), ss[0])["LD3i_pre"]
    assert t["status"] == "missing"                                             # the first session has no prev


def _pillars(n, weak, prev="2026-11-13", before="2026-11-12"):
    out = {}
    for k, sym in enumerate(LIB.PILLARS[:n]):
        if k < weak:
            out[sym] = [[before, 10.0, 12.0, 12.0, 0.0], [prev, 9.0, 11.0, 11.0, 0.0]]   # under both, 9 falling
        else:
            out[sym] = [[before, 10.0, 9.0, 9.0, 0.0], [prev, 11.0, 10.0, 10.0, 0.0]]
    return out


def test_ld9_five_pillars_missing_six_ok_three_weak_off_four_on():
    ss = weekdays("2026-11-12", "2026-11-16")
    d = ss[2]
    assert LIB.compute(mk_inputs(ss, pillars=_pillars(5, 4)), d)["LD9_pre"]["status"] == "missing"
    t = LIB.compute(mk_inputs(ss, pillars=_pillars(6, 3)), d)["LD9_pre"]
    assert t["status"] == "ok" and t["value"] == "3/6" and t["on"] is False
    t = LIB.compute(mk_inputs(ss, pillars=_pillars(8, 4)), d)["LD9_pre"]
    assert t["value"] == "4/8" and t["on"] is True
    p = _pillars(8, 4)
    for sym in p:
        p[sym] = p[sym][1:]                                                     # the prev row is the first: skipped
    assert LIB.compute(mk_inputs(ss, pillars=p), d)["LD9_pre"]["status"] == "missing"


# ── record hygiene ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_no_missing_tag_holds_on_false_and_no_nan_in_a_record(tmp_path, capsys, fixture_inputs):
    rc, out = run_cli(tmp_path, fixture_inputs, "--recompute", "2026-10-13..2026-11-11")
    assert rc == 0
    recs = LIB.load_store(out / LIB.STORE_NAME)
    assert len(recs) == 22 and all(r["in_sample"] for r in recs)
    for r in recs:
        assert not LIB.has_nan(r)
        for t in r["tags"].values():
            assert (t["status"] == "missing") == (t["on"] is None)
            assert t["status"] != "missing" or t["value"] is None
    raw = (out / LIB.STORE_NAME).read_text()
    assert "NaN" not in raw and "Infinity" not in raw
    assert LIB.has_nan({"a": [1.0, float("nan")]}) and not LIB.has_nan({"a": [1.0]})


def test_a_nan_value_reads_missing():
    ss = weekdays("2026-11-12", "2026-11-16")
    t = LIB.compute(mk_inputs(ss, iwm_rows=[["2026-11-13", 1.0, float("nan"), 3.0]]), ss[2])["LD3i_pre"]
    assert t["status"] == "missing" and t["on"] is None


# ── gaps / late [C3] ────────────────────────────────────────────────────────────────────────────────────────────────
def _seed(out, inputs, sessions):
    os.makedirs(out, exist_ok=True)
    recs = []
    tags = LIB.compute_all(inputs, sessions)
    for d in sessions:
        rec = LIB.plan_append(recs, d, tags[d], {"late": False, "inputs_file": "inputs/seed.json.gz"})
        recs.append(rec)
    LIB.append_many(str(out / LIB.STORE_NAME), recs)
    (out / "inputs").mkdir(exist_ok=True)
    (out / "inputs" / "seed.json.gz").write_bytes(b"seed")


def test_gaps_are_computed_late_rev0_and_the_target_is_not_late(tmp_path, capsys):
    ss = weekdays("2026-11-02", "2026-11-30")
    inp = mk_inputs(ss, closed="2026-11-18")
    _seed(tmp_path / "store", inp, ["2026-11-12", "2026-11-16"])
    rc, out = run_cli(tmp_path, inp)
    s = summary(capsys)
    assert rc == 0 and s["session"] == "2026-11-18"
    assert s["gap_sessions"] == ["2026-11-13", "2026-11-17"]
    got = {(a["session"], a["rev"], a["late"]) for a in s["appended"]}
    assert ("2026-11-13", 0, True) in got and ("2026-11-17", 0, True) in got and ("2026-11-18", 0, False) in got
    recs = LIB.latest_by_session(LIB.load_store(out / LIB.STORE_NAME))
    assert recs["2026-11-13"]["tags"]["GD6b_pre"]["status"] == "missing"          # passes expired → MISSING, kept
    assert "2026-11-10" not in recs and "2026-11-11" not in recs                   # before FORWARD_FROM: never auto
    assert recs["2026-11-18"]["late"] is False and recs["2026-11-18"]["in_sample"] is False


def test_a_weekend_and_thanksgiving_are_never_gaps(tmp_path, capsys):
    ss = weekdays("2026-11-02", "2026-12-01")
    assert "2026-11-26" not in ss
    plan = LIB.sessions_to_compute([], mk_inputs(ss, closed="2026-11-30"), "2026-11-30")
    assert "2026-11-26" not in plan["gaps"] and "2026-11-21" not in plan["gaps"] and "2026-11-22" not in plan["gaps"]
    assert plan["gaps"][0] == LIB.FORWARD_FROM and "2026-11-30" not in plan["gaps"]


# ── the store ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _small(closed="2026-11-13", q=99.0, i=99.0):
    ss = weekdays("2026-11-02", "2026-11-30")
    intra = {}
    if q is not None:
        intra["QQQ|2026-11-12"] = bars("2026-11-12", 100.0, q)
        intra["IWM|2026-11-12"] = bars("2026-11-12", 100.0, i)
    return mk_inputs(ss, closed=closed, intra=intra)


def test_equal_values_twice_is_one_line(tmp_path, capsys):
    inp = _small(closed="2026-11-12")
    assert run_cli(tmp_path, inp)[0] == 0
    capsys.readouterr()
    rc, out = run_cli(tmp_path, inp)
    assert rc == 0 and summary(capsys)["appended"] == []
    assert len(LIB.load_store(out / LIB.STORE_NAME)) == 1


def test_a_changed_value_is_rev1_and_the_first_line_is_byte_kept(tmp_path, capsys):
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12"))
    first = (out / LIB.STORE_NAME).read_bytes()
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12", q=101.0))
    raw = (out / LIB.STORE_NAME).read_bytes()
    assert raw.startswith(first) and len(raw) > len(first)
    recs = LIB.load_store(out / LIB.STORE_NAME)
    assert [r["rev"] for r in recs] == [0, 1] and recs[1]["changed"] == ["GD7_by1030"]
    assert recs[1]["tags"]["GD7_by1030"]["on"] is False and recs[0]["changed"] is None


def test_missing_to_ok_on_an_older_session_is_appended(tmp_path, capsys):
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12", q=None))
    assert LIB.load_store(out / LIB.STORE_NAME)[0]["tags"]["GD7_by1030"]["status"] == "missing"
    capsys.readouterr()
    rc, out = run_cli(tmp_path, _small(closed="2026-11-13"))
    s = summary(capsys)
    assert s["missing_retry"] == ["2026-11-12"]
    recs = LIB.load_store(out / LIB.STORE_NAME)
    r12 = [r for r in recs if r["session"] == "2026-11-12"]
    assert [r["rev"] for r in r12] == [0, 1] and r12[1]["changed"] == ["GD7_by1030"]
    assert r12[1]["tags"]["GD7_by1030"]["status"] == "ok"


def test_a_retry_takes_only_missing_to_ok(tmp_path, capsys):
    first = _small(closed="2026-11-12", q=None)
    first["iwm_daily"]["rows"] = [["2026-11-11", 1.0, 2.0, 3.0]]
    rc, out = run_cli(tmp_path, first)
    assert LIB.load_store(out / LIB.STORE_NAME)[0]["tags"]["LD3i_pre"]["value"] == -1.0
    inp = _small(closed="2026-11-13")
    inp["iwm_daily"]["rows"] = [["2026-11-11", 1.0, 1.0, 3.0], ["2026-11-12", 1.0, 2.0, 3.0]]   # ok → ok moved
    capsys.readouterr()
    run_cli(tmp_path, inp)
    r12 = [r for r in LIB.load_store(out / LIB.STORE_NAME) if r["session"] == "2026-11-12"]
    assert r12[-1]["changed"] == ["GD7_by1030"] and r12[-1]["tags"]["LD3i_pre"]["value"] == -1.0


def test_ok_to_missing_is_not_appended_on_a_plain_run_only_under_recompute(tmp_path, capsys):
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12"))
    capsys.readouterr()
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12", q=None))
    assert summary(capsys)["appended"] == [] and len(LIB.load_store(out / LIB.STORE_NAME)) == 1
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12", q=None), "--recompute", "2026-11-12..2026-11-12")
    recs = LIB.load_store(out / LIB.STORE_NAME)
    assert rc == 0 and recs[-1]["rev"] == 1 and recs[-1]["tags"]["GD7_by1030"]["status"] == "missing"
    assert recs[-1]["tags"]["GD7_by1030"]["why"]


@pytest.mark.parametrize("bad", [b'{"session":"2026-11-12","rev":0}\nnot json\n',
                                 b'{"session":"2026-11-12","rev":0}\n{"session":"2026-11-12","rev":1}',
                                 b'{"session":"2026-11-12","rev":0}\n{"session":"2026-11-12","rev":2}\n',
                                 b'{"session":"2026-11-12","rev":1}\n'])
def test_a_corrupt_store_exits_2_and_the_bytes_are_unchanged(tmp_path, capsys, bad):
    out = tmp_path / "store"
    out.mkdir()
    (out / LIB.STORE_NAME).write_bytes(bad)
    rc, _ = run_cli(tmp_path, _small(closed="2026-11-12"))
    s = summary(capsys)
    assert rc == 2 and s["exit"] == 2 and "corrupt" in s["why"]
    assert (out / LIB.STORE_NAME).read_bytes() == bad
    assert not (out / "inputs").exists()
    with pytest.raises(LIB.StoreCorrupt):
        LIB.load_store(out / LIB.STORE_NAME)


def test_an_unclosed_or_closed_market_session_is_refused(tmp_path, capsys):
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12"), "--session", "2026-11-13")
    assert rc == 2 and "not closed" in summary(capsys)["why"] and not out.exists()
    rc, out = run_cli(tmp_path, _small(closed="2026-11-30"), "--session", "2026-11-26")
    assert rc == 2 and "not a market day" in summary(capsys)["why"] and not out.exists()
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12"), "--recompute", "2026-11-10..2026-11-13")
    assert rc == 2 and "past the last closed" in summary(capsys)["why"] and not out.exists()


def test_dry_run_writes_nothing(tmp_path, capsys):
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12"), "--dry-run")
    s = summary(capsys)
    assert rc == 0 and s["dry_run"] is True and s["appended"] and not out.exists()


def test_default_out_is_outside_the_repo_and_never_used_by_a_test():
    assert CLI.DEFAULT_OUT == "/Users/ajay/clinet-test/eod-audits/shadow-day-tags"
    assert not CLI.DEFAULT_OUT.startswith(str(BACKEND)) and "cheetah-market-app" not in CLI.DEFAULT_OUT
    assert ".wt-" not in CLI.DEFAULT_OUT


# ── killed run [C2] ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_killed_run_leaves_an_orphan_the_next_run_lists_it_and_writes_r2(tmp_path, capsys, monkeypatch):
    real = LIB._atomic_write

    def boom(path, data):
        if str(path).endswith(".jsonl"):
            raise OSError("killed")
        return real(path, data)

    monkeypatch.setattr(LIB, "_atomic_write", boom)
    with pytest.raises(OSError):
        run_cli(tmp_path, _small(closed="2026-11-12"))
    monkeypatch.setattr(LIB, "_atomic_write", real)
    out = tmp_path / "store"
    orphan = out / "inputs" / "2026-11-12.json.gz"
    assert orphan.exists() and not (out / LIB.STORE_NAME).exists()
    before = orphan.read_bytes()
    capsys.readouterr()
    rc, _ = run_cli(tmp_path, _small(closed="2026-11-12"))
    s = summary(capsys)
    assert rc == 0 and s["orphan_inputs"] == ["inputs/2026-11-12.json.gz"]
    assert s["inputs_file"] == "inputs/2026-11-12.r2.json.gz"
    assert orphan.read_bytes() == before
    recs = LIB.load_store(out / LIB.STORE_NAME)
    assert len(recs) == 1 and recs[0]["inputs_file"] == "inputs/2026-11-12.r2.json.gz"
    assert hashlib.sha256((out / recs[0]["inputs_file"]).read_bytes()).hexdigest() == recs[0]["inputs_sha256"]


def test_a_referenced_inputs_file_is_never_overwritten(tmp_path, capsys):
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12"))
    ref = out / "inputs" / "2026-11-12.json.gz"
    before = ref.read_bytes()
    rc, out = run_cli(tmp_path, _small(closed="2026-11-12", q=101.0))
    assert ref.read_bytes() == before and (out / "inputs" / "2026-11-12.r2.json.gz").exists()
    with pytest.raises(FileExistsError):
        LIB.write_run(str(out), "inputs/2026-11-12.json.gz", b"x", [])
    assert ref.read_bytes() == before
    assert LIB.orphan_inputs(str(out), LIB.load_store(out / LIB.STORE_NAME)) == []


def test_the_inputs_blob_is_deterministic():
    inp = _small()
    assert LIB.inputs_blob(inp) == LIB.inputs_blob(json.loads(json.dumps(inp)))


# ── sessions ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_probe_market_day_walk_equals_prev_market_day_over_2026_and_the_study_list(fixture_inputs):
    PR = _probe()
    from supply_demand.key_levels import prev_market_day, _is_market_day
    days = PR.market_days(date(2025, 12, 20), date(2026, 12, 31))
    assert "2026-11-26" not in days and "2026-11-21" not in days and "2026-11-27" in days
    d = date(2026, 1, 1)
    while d <= date(2026, 12, 31):
        assert (d.isoformat() in days) == _is_market_day(d), d
        if d.isoformat() in days:
            i = days.index(d.isoformat())
            assert prev_market_day(d).isoformat() == days[i - 1], d
        d += timedelta(days=1)
    assert PR.market_days(date(2026, 10, 13), date(2026, 11, 11)) == fixture_inputs["sessions"]


def test_probe_last_closed_waits_for_the_close_plus_settle():
    PR = _probe()
    ss = ["2026-11-11", "2026-11-12"]
    at = datetime.combine(date(2026, 11, 12), dtime(16, 0), tzinfo=ET)
    assert PR.last_closed(ss, at + timedelta(seconds=29)) == "2026-11-11"
    assert PR.last_closed(ss, at + PR.L.SETTLE) == "2026-11-12"
    assert PR.last_closed(ss, datetime.combine(date(2026, 11, 11), dtime(12, 0), tzinfo=ET)) is None


# ── the copied engine ───────────────────────────────────────────────────────────────────────────────────────────────
def test_risk_after_copy_equals_the_lane_engine_over_a_grid():
    from trading import gajjala_entry as GE
    grid = [None, 0, 0.0, 1, -1, 2.5, -0.01, 0.01, float("nan"), "x", True]
    for m in (None, 1.0, 0.5, 0.25, 0.125, 0.0625, 3, "x"):
        for p in grid:
            assert LIB.risk_after_copy(m, p, GE.GG_LOSS_RISK_CUT) == GE.risk_after(m, p), (m, p)
    a = b = 1.0
    for p in (-1, -2, 0, -3, 4, -1, None, -0.5):
        a, b = LIB.risk_after_copy(a, p, GE.GG_LOSS_RISK_CUT), GE.risk_after(b, p)
        assert a == b


def test_trade_of_is_the_study_function():
    if not STUDY.is_dir():
        pytest.skip("the study folder is not mounted here")
    src = (STUDY / "analyze.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "trade_of")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "analyze.py", "exec"), ns)
    for r in json.loads(INPUTS_FIX.read_text())["gg5_rows"][:400]:
        a, b = ns["trade_of"](r), LIB.trade_of(r)
        assert (a is None) == (b is None) and (a is None or (a["R"], a["bucket"], a["filled"], a["thin"]) ==
                                                (b["R"], b["bucket"], b["filled"], b["thin"]))


# ── the prereg ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_prereg_is_frozen_and_its_bytes_match_the_sha_file():
    assert PREREG.is_file() and PREREG_SHA.is_file()
    sha = PREREG_SHA.read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{64}", sha)
    assert hashlib.sha256(PREREG.read_bytes()).hexdigest() == sha


def test_NEGATIVE_one_changed_byte_breaks_the_prereg_pin():
    b = bytearray(PREREG.read_bytes())
    i = bytes(b).index(b"0.0025")
    b[i + 5] = ord("8")
    assert hashlib.sha256(bytes(b)).hexdigest() != PREREG_SHA.read_text().strip()


def test_prereg_settles_20_reads_at_alpha_0_05_over_20():
    t = PREREG.read_text()
    assert len(LIB.READS) == 20
    assert math.isclose(0.05 / len(LIB.READS), 0.0025)
    assert "Total 20 reads" in t
    assert "alpha = 0.05 / 20 = 0.0025" in t
    assert "BOTH placebo p < 0.05 / 20 = 0.0025" in t
    assert "EVERY page of the 20 reads" in t


def test_NEGATIVE_prereg_is_not_a_draft_and_never_tests_at_0_05_over_18():
    t = PREREG.read_text()
    assert not re.search(r"\bOPEN\b", t) and "DRAFT" not in t and "NOT frozen" not in t
    assert "p < 0.05 / 18" not in t and "p < alpha" not in t
    lines18 = [ln for ln in t.splitlines() if "0.05 / 18" in ln]
    assert len(lines18) == 1 and "the spec's" in lines18[0]


def test_the_circular_shift_floor_stays_above_the_settled_alpha():
    from chart_maps.gajjala import audited_rules as AR
    sessions_at_floor = AR.MEASURE_FLOOR_WEEKS * LIB.WEEK
    assert 1 / sessions_at_floor > 0.05 / len(LIB.READS)
    assert "1 / n ≈ 0.0067" in PREREG.read_text()


def test_prereg_names_the_floor_the_correction_both_placebos_and_the_draws():
    t = PREREG.read_text()
    for w in ("MEASURE_FLOOR_WEEKS", "NPERM_FWD", "20000", "run-order", "free shuffle", "two-sided",
              "0.05 / ", "FORWARD_FROM", "late"):
        assert w in t, w
    for f in LIB.TAG_FORMS:
        assert f in t, f


def test_prereg_holds_the_three_frozen_study_shas():
    t = PREREG.read_text()
    shas = {"day_indicators.py": "9bef2f1b8462aa5252664ae87cce862c501828cf11f02de327dae1e86530dcbc",
            "analyze.py": "2bbf60f7fd3a52dd3e4de2dc60c696dd314e8e6a5165acab5d251dc44e20d233",
            "days.csv": "795c43775f4bab2d01e071b56991037817cef9d77f6b476a6fe938ecc99ecaeb"}
    for n, sha in shas.items():
        assert sha in t, n
        if STUDY.is_dir():
            assert hashlib.sha256((STUDY / n).read_bytes()).hexdigest() == sha, n


def test_the_reads_are_every_tag_form_on_its_study_pages():
    assert len(LIB.TAG_FORMS) == 8 and len(set(LIB.READS)) == len(LIB.READS)
    assert sum(1 for f, _ in LIB.READS if f.startswith("GD")) == 6 * 2
    assert sum(1 for f, _ in LIB.READS if f.startswith("LD")) == 2 * 4
    assert set(LIB.SOURCE_TAGS) == set(LIB.TAG_FORMS)


# ── source guards ───────────────────────────────────────────────────────────────────────────────────────────────────
WRITE_METHODS = re.compile(r"^(insert_\w*|update_\w*|replace_\w*|delete_\w*|bulk_write|drop\w*|create_index\w*|"
                           r"find_one_and_\w*|rename|save|remove)$")
BANNED_IMPORT = re.compile(r"^(trading|daytrading|massive_keys|massive|finnhub|yfinance|alpaca|requests|httpx|"
                           r"curl_cffi|urllib\.request|aiohttp|plaid)(\.|$)")
STDLIB = {"argparse", "ast", "gzip", "hashlib", "json", "math", "os", "subprocess", "sys", "tempfile", "datetime",
          "decimal", "typing", "zoneinfo", "collections", "__future__"}


def _imports(tree, skip_fn=None):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            out.append((node.module or "", node))
    return out


def test_nothing_outside_scripts_and_tests_imports_the_package():
    hits = []
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).parts
        if rel[0] in (".venv", "scripts", "tests") or "node_modules" in rel:
            continue
        if "shadow_day_tags" in p.read_text(errors="ignore"):
            hits.append(str(p))
    assert hits == []


def test_the_probe_holds_no_mongo_write_and_no_banned_import():
    tree = ast.parse((BACKEND / "scripts" / "shadow_day_tags_probe.py").read_text())
    calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert [c for c in calls if WRITE_METHODS.match(c)] == []
    mods = [m for m, _ in _imports(tree)]
    assert [m for m in mods if BANNED_IMPORT.match(m)] == []
    assert "chart_maps.gajjala" in mods and "market_hours.reminder" in mods


def test_the_guard_catches_a_planted_write_and_a_planted_import():
    tree = ast.parse("db.x.update_one({}, {})\nimport trading.broker\nfrom daytrading import data\n")
    calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert [c for c in calls if WRITE_METHODS.match(c)] == ["update_one"]
    assert [m for m, _ in _imports(tree) if BANNED_IMPORT.match(m)] == ["trading.broker", "daytrading"]


@pytest.mark.parametrize("name", ["shadow_day_tags_lib.py", "shadow_day_tags.py"])
def test_lib_and_cli_parse_as_python_39_and_import_the_stdlib_only(name):
    src = (BACKEND / "scripts" / name).read_text()
    tree = ast.parse(src, feature_version=(3, 9))
    lazy = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == "build_fixture":
            lazy |= {id(n) for n in ast.walk(fn)}
    bad = []
    for m, node in _imports(tree):
        if id(node) in lazy:
            continue
        top = m.split(".")[0]
        if top not in STDLIB and m not in ("scripts", "shadow_day_tags_lib"):
            bad.append(m)
    assert bad == []
    anns = [a.annotation for a in ast.walk(tree) if isinstance(a, ast.arg) and a.annotation is not None]
    anns += [f.returns for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and f.returns is not None]
    assert not [a for a in anns for n in ast.walk(a) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr)]


def test_the_crontab_names_none_of_the_files():
    tab = (BACKEND / "crontab").read_text()
    assert "shadow_day_tags" not in tab


def test_no_b_word_in_any_file_of_the_package():
    bw = re.compile("b" + "ounc", re.I)
    for p in PKG_FILES:
        if p.exists():
            assert not bw.search(p.read_text(errors="ignore")), p


# ── the live-proof sequence (step 6, run on the api container 2026-11-12 after the close) replayed hermetically ─────
def _fixture_closed_1112(fixture_inputs):
    inp = json.loads(json.dumps(fixture_inputs))
    inp["sessions"] = list(inp["sessions"]) + ["2026-11-12"]
    inp["last_closed_session"] = inp["today_et"] = "2026-11-12"
    return inp


def test_live_proof_sequence_recompute_then_plain_appends_the_target_only(tmp_path, capsys, fixture_inputs):
    inp = _fixture_closed_1112(fixture_inputs)
    rc, out = run_cli(tmp_path, inp, "--recompute", "2026-10-13..2026-11-11")
    s1 = summary(capsys)
    assert rc == 0 and s1["session"] == "2026-11-12" and s1["gap_sessions"] == [] and s1["missing_retry"] == []
    assert [a["session"] for a in s1["appended"]] == fixture_inputs["sessions"]
    assert all(a["rev"] == 0 and a["late"] is True and a["changed"] is None for a in s1["appended"])
    store = out / LIB.STORE_NAME
    first = store.read_bytes()
    recs = LIB.load_store(store)
    assert len(recs) == 22 and all(r["in_sample"] and r["inputs_file"] == "inputs/2026-11-12.json.gz" for r in recs)
    rows = {r["date"]: r for r in csv.DictReader(DAYS_FIX.open(newline=""))}
    for r in recs:
        for f in LIB.TAG_FORMS:
            t, v = r["tags"][f], rows[r["session"]][f + "_value"]
            assert (t["status"] == "missing") == (v == ""), (r["session"], f)
            assert t["status"] == "missing" or str(t["value"]) == v, (r["session"], f)

    rc, out = run_cli(tmp_path, inp)
    s2 = summary(capsys)
    assert rc == 0 and s2["gap_sessions"] == [] and s2["orphan_inputs"] == []
    assert s2["missing_retry"] == []
    assert s2["appended"] == [{"session": "2026-11-12", "rev": 0, "late": False, "changed": None}]
    assert s2["inputs_file"] == "inputs/2026-11-12.r2.json.gz"
    assert store.read_bytes()[:len(first)] == first
    last = LIB.load_store(store)[-1]
    assert last["session"] == "2026-11-12" and last["in_sample"] is False and last["late"] is False


def test_live_proof_negative_in_sample_missing_is_never_retried_and_an_equal_rerun_writes_nothing(
        tmp_path, capsys, fixture_inputs):
    inp = _fixture_closed_1112(fixture_inputs)
    run_cli(tmp_path, inp, "--recompute", "2026-10-13..2026-11-11")
    run_cli(tmp_path, inp)
    capsys.readouterr()
    out = tmp_path / "store"
    recs = LIB.load_store(out / LIB.STORE_NAME)
    assert any(t["status"] == "missing" for r in recs if r["in_sample"] for t in r["tags"].values())
    store_before = (out / LIB.STORE_NAME).read_bytes()
    inputs_before = sorted(p.name for p in (out / "inputs").iterdir())
    rc, _ = run_cli(tmp_path, inp)
    s = summary(capsys)
    assert rc == 0 and s["appended"] == [] and s["missing_retry"] == [] and s["gap_sessions"] == []
    assert "inputs_file" not in s
    assert (out / LIB.STORE_NAME).read_bytes() == store_before
    assert sorted(p.name for p in (out / "inputs").iterdir()) == inputs_before
    assert LIB.sessions_to_compute(recs, inp, "2026-11-12")["missing_retry"] == []


# ── no create_index from the probe (refix 2026-11-12, as track_record_snapshot_probe.py) ────────────────────────────
class _RecCur(list):
    def sort(self, *a, **k):
        return self

    def limit(self, *a):
        return self


class _RecColl:
    """A fake collection that answers the plain reads and RECORDS every other method called on it."""

    def __init__(self, name, docs, log):
        self.name, self.docs, self.log = name, docs, log

    def find(self, q=None, proj=None, *a, **k):
        q = q or {}
        return _RecCur([d for d in self.docs if all(d.get(f) == v for f, v in q.items() if not isinstance(v, dict))])

    def find_one(self, q=None, proj=None, *a, **k):
        r = self.find(q, proj)
        return r[0] if r else None

    def distinct(self, key, *a, **k):
        return sorted({d.get(key) for d in self.docs if d.get(key)})

    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        self.log.append("%s.%s" % (self.name, k))
        return lambda *a, **kw: None


class _RecDB:
    def __init__(self, docs, log):
        self._docs, self._log = docs, log

    def __getitem__(self, k):
        return _RecColl(k, self._docs.get(k, []), self._log)

    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        return self[k]

    def command(self, *a, **k):
        self._log.append("admin.command")
        return {"ok": 1}


class _RecClient:
    def __init__(self, docs, log):
        self.db = _RecDB(docs, log)
        self.admin = self.db

    def __getitem__(self, k):
        return self.db


def _price_doc(sym, n=40, cached_at=1.7e9, start="2026-08-03", tail_echo=False):
    d0 = date.fromisoformat(start)
    bars = [{"date": (d0 + timedelta(days=i)).isoformat(), "open": 10.0 + i, "high": 11.0 + i, "low": 9.0 + i,
             "close": 10.5 + i, "volume": 1000.0 + i} for i in range(n)]
    if tail_echo:
        last = dict(bars[-1])
        last["date"] = (d0 + timedelta(days=n)).isoformat()
        bars.append(last)
    return {"symbol": sym, "bars": bars, "cached_at": cached_at}


def _house_store(monkeypatch):
    """The REAL portfolio/store.py. On the host venv (Python 3.9) the `portfolio` package __init__ pulls api.py, whose
    pydantic models use `str | None` and fail to import, so the module file alone is loaded under its own name (it
    imports only the stdlib); in the api image the package imports and is used as is. sys.modules is restored."""
    import importlib.util
    import sys
    import types
    try:
        import portfolio.store as PS
        return PS
    except Exception:                                           # noqa: BLE001 — the host-venv 3.9 case
        pass
    pkg = types.ModuleType("portfolio")
    pkg.__path__ = [str(BACKEND / "portfolio")]
    spec = importlib.util.spec_from_file_location("portfolio.store", BACKEND / "portfolio" / "store.py")
    PS = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.store", PS)
    spec.loader.exec_module(PS)
    pkg.store = PS
    return PS


def _write_calls(log):
    return [c for c in log if WRITE_METHODS.match(c.split(".", 1)[1])]


@pytest.mark.parametrize("doc", [
    _price_doc("IWM"),
    _price_doc("IWM", tail_echo=True),                                     # the phantom tail is dropped by both
    _price_doc("IWM", cached_at=True),                                     # a bool cached_at → None
    _price_doc("IWM", cached_at="1.7e9"),                                  # a non-numeric cached_at → None
    _price_doc("IWM", cached_at=None),
    {"symbol": "IWM", "bars": [], "cached_at": 1.7e9},                      # no bars → None
    None,                                                                  # no doc → None
])
def test_probe_frame_meta_equals_cached_frame_meta(monkeypatch, doc):
    PR = _probe()
    from sepa import prices as P
    log = []
    docs = {"price_cache": [doc] if doc else []}
    monkeypatch.setattr(P, "_mongo_coll", _RecColl("price_cache", docs["price_cache"], log))
    monkeypatch.setattr(P, "_mongo_disabled", False)                       # an earlier host test may have latched it
    want = P.cached_frame_meta("IWM")
    got = PR.frame_meta(_RecDB(docs, log), "IWM")
    assert (want is None) == (got is None)
    if want is not None:
        assert got["cached_at"] == want["cached_at"] and got["frame"].equals(want["frame"])
    if doc and doc.get("bars") and isinstance(doc.get("cached_at"), float):
        assert got is not None and len(got["frame"]) == 40                 # the echo bar never reaches the EMAs
    assert PR.frame_meta(_RecDB(docs, log), "") is None and PR.frame_meta(_RecDB(docs, log), "QQQ") is None
    assert _write_calls(log) == []


def test_probe_main_presets_both_handles_and_calls_no_create_index_or_write(monkeypatch, capsys):
    PR = _probe()
    import pymongo
    PS = _house_store(monkeypatch)
    from sepa import prices as P
    log = []
    docs = {"price_cache": [_price_doc("IWM", n=330)] + [_price_doc(s, n=70) for s in LIB.PILLARS]}
    client = _RecClient(docs, log)
    monkeypatch.setattr(PS, "_db", None)
    monkeypatch.setattr(PS, "_disabled", False)
    monkeypatch.setattr(P, "_mongo_coll", None)
    monkeypatch.setattr(P, "_mongo_disabled", False)
    monkeypatch.setattr(pymongo, "MongoClient", lambda *a, **k: client)   # a missed pre-set would land here, logged
    monkeypatch.setattr(PR, "MongoClient", lambda *a, **k: client)
    monkeypatch.setattr(PR, "APP", str(BACKEND))
    PR.main([])
    out = json.loads(capsys.readouterr().out)
    assert PS._db is client.db and P._mongo_coll.name == "price_cache"
    assert _write_calls(log) == [] and "admin.command" not in log           # no create_index, no ping, no write
    assert len(out["iwm_daily"]["rows"]) == PR.IWM_ROWS_OUT and out["asof"]["iwm_daily_cached_at"] == 1.7e9
    assert sorted(out["pillars"]) == sorted(LIB.PILLARS)


def test_the_recorder_catches_the_house_helpers_create_index(monkeypatch):
    import pymongo
    PS = _house_store(monkeypatch)
    from sepa import prices as P
    log = []
    client = _RecClient({"price_cache": [_price_doc("IWM")]}, log)
    monkeypatch.setattr(pymongo, "MongoClient", lambda *a, **k: client)
    monkeypatch.setattr(P, "_mongo_coll", None)
    monkeypatch.setattr(P, "_mongo_disabled", False)
    monkeypatch.setattr(PS, "_db", None)
    monkeypatch.setattr(PS, "_disabled", False)
    assert P.cached_frame_meta("IWM") is not None                         # the OLD probe path
    PS._get_db()
    assert _write_calls(log) == ["price_cache.create_index", "portfolio_holdings.create_index"]


def test_the_probe_never_calls_cached_frame_meta_and_presets_before_any_read():
    src = (BACKEND / "scripts" / "shadow_day_tags_probe.py").read_text()
    tree = ast.parse(src)
    calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert "cached_frame_meta" not in calls and "_get_mongo" not in calls and "_get_db" not in calls
    main = src[src.index("def main("):]
    assert main.index("PS._db = db") < main.index("gg5_rows(") and main.index("P._mongo_coll = db.price_cache") < \
        main.index("iwm_daily(db)")
