"""🩳 sishares — the four verifier misses of 2026-11-26 (spec sishares §3.2 / §3.5 / §5.2), negatives first.

1. A held `none_6k` full-text answer a later pass could not re-ask (flagged `error`) never says "no 6-K filed".
2. The stored-reads-only backfill run never charges a deferred 1-minute load to the cap (`loads` stays 0).
3. `--night` exits 1 on ANY named read fault, not only the index read.
4. The --modes probe counts only real 🩳 list flips as enter / leave and prints the attempted write methods.
Hermetic (fake stores / fake db, no outside call). Display / ops only; UNMEASURED. Not advice.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from short_interest import basis_math as BM
from tests.test_si_share_count_verdict_2026_11_26 import POM_CHECK, TODAY, pom_doc, pom_rec, ver


# ═════════════════════════════════════════════ miss 1 — a flagged none_6k in the check sentence
def _check_with(words):
    return POM_CHECK[:-1] + BM.TEXT_CHECK_FTS % words + "."


def test_NEGATIVE_flagged_none_6k_blocked_says_paused_never_no_6k_filed():
    fts = {"status": "none_6k", "error": "blocked", "error_at": "2026-11-27T03:10:00Z",
           "read_at": "2026-11-27T02:40:00Z"}
    v = BM.verdict(copy.deepcopy(pom_rec()), copy.deepcopy(pom_doc(fts=fts)), TODAY)
    assert v["check_text"] == _check_with("not read — paused")
    assert "no 6-K filed in the window" not in v["check_text"]


def test_NEGATIVE_flagged_none_6k_failed_says_the_failed_try_never_paused_or_no_6k():
    fts = {"status": "none_6k", "error": "http 500", "error_at": "2026-11-27T03:00:00Z",
           "read_at": "2026-11-27T02:40:00Z"}
    v = ver(pom_rec(), pom_doc(fts=fts))
    assert v["check_text"] == _check_with("not read — last try failed 11/26 22:00 ET")
    assert "paused" not in v["check_text"] and "no 6-K filed" not in v["check_text"]


@pytest.mark.parametrize("err", [None, ""])
def test_an_unflagged_none_6k_still_says_no_6k_filed(err):
    v = ver(pom_rec(), pom_doc(fts={"status": "none_6k", "error": err, "read_at": "2026-11-27T02:40:00Z"}))
    assert v["check_text"] == _check_with("no 6-K filed in the window")


@pytest.fixture
def _fts_iso(monkeypatch):
    from short_interest import sec_fts as SF
    from short_interest import share_basis as SB
    from short_interest import ssr_corp as SC
    monkeypatch.setattr(SB, "_sec_stop", {"until": None})
    monkeypatch.setattr(SB, "_fts_stop", {"until": None})
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: None)
    monkeypatch.setattr(SC, "_key", lambda: "TESTKEY")
    monkeypatch.setattr(SF, "FTS_WHEN", "on")
    return SB


def test_NEGATIVE_end_to_end_none_6k_under_the_stop_with_6ks_listed_reads_paused(_fts_iso):
    """The verifier's p1: pass 1 no 6-K → none_6k; pass 2 the stop is on and POM's 6-Ks are listed → flagged."""
    from tests.test_si_sec_fts_2026_11_26 import HTTP, NOW, pom_db, run, sub_without_6k
    SB = _fts_iso
    rec = dict(pom_rec(), _id="POM")
    db = pom_db(rec=rec)
    first = run(db, HTTP(sub=sub_without_6k()))
    assert first["sec"]["fts"]["status"] == "none_6k"
    assert ver(pom_rec(), first)["check_text"].endswith(BM.TEXT_CHECK_FTS % "no 6-K filed in the window" + ".")
    SB._fts_stop["until"] = NOW + timedelta(hours=1)
    http = HTTP()
    doc = run(db, http, now=NOW + timedelta(minutes=30))
    assert http.efts() == [] and doc["sec"]["fts"]["error"] == "blocked"
    text = BM.verdict(copy.deepcopy(rec), copy.deepcopy(doc), TODAY)["check_text"]
    assert text.endswith(BM.TEXT_CHECK_FTS % "not read — paused" + ".")
    assert "no 6-K filed in the window" not in text


# ═════════════════════════════════════════════ miss 2 — the stored-reads-only run never spends the cap on a load
def _follow_world(pins):
    from chart_maps.gajjala import si_follow as SF
    import tests.test_gajjala_si_follow_2026_11_26 as T
    st = T._recorded()
    for p in pins:
        assert SF.pin(st, p, T.S.isoformat(), T.utc(T.N, "20:30"))["ok"]
    return st, T


def _stored_only_run(monkeypatch, cap, pins):
    from chart_maps.gajjala import si_follow as SF
    from chart_maps.gajjala import si_track as SIT
    from scripts import gajjala_si_follow_backfill as BF
    st, T = _follow_world(pins)
    monkeypatch.setattr(SIT, "MAX_LOADS", cap)
    asked = []
    boom = lambda s, d: pytest.fail("the 1-minute seam was asked")    # noqa: E731
    buf = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(buf):
        out = BF.run(st, T.utc(T.N, "20:30"), end=T.S.isoformat(), load_1m=boom,
                     split_lookup=lambda s, lo, hi: asked.append(s) or False)
    total = json.loads(buf.getvalue().strip().splitlines()[-1])["total"]
    facts = SF.read_facts(st, [T.S.isoformat()])[T.S.isoformat()]
    return st, T, out, total, facts, asked


@pytest.mark.parametrize("pins", [["ZZZ"], ["MMM", "ZZZ"]])
def test_NEGATIVE_stored_only_run_reports_zero_loads_and_fills_every_complete_stored_read(monkeypatch, pins):
    from chart_maps.gajjala import si_track as SIT
    st, T, out, total, facts, asked = _stored_only_run(monkeypatch, 1, pins)
    assert total["loads"] == 0 and all(x.get("loads", 0) == 0 for x in out)
    assert total["deferred_cap"] == 0 and total["split_calls"] == 1 and asked == ["ZZZ"]
    z = facts["ZZZ"]
    assert z["state"] == "ok" and z["retry"] is False and z["load"] == "reads"
    for sym, f in facts.items():                                       # every complete stored read is filled
        if SIT.complete(st.get_read(T.S, sym), T.S):
            assert f["retry"] is False, sym


def test_NEGATIVE_stored_only_run_still_caps_the_split_checks(monkeypatch):
    st, T, out, total, facts, asked = _stored_only_run(monkeypatch, 0, ["ZZZ"])
    assert total["loads"] == 0 and total["split_calls"] == 0 and asked == []
    assert total["deferred_cap"] >= 1 and facts["ZZZ"]["retry"] is True     # refused → retried, never terminal


def test_splits_only_budget_counts_split_checks_only():
    from chart_maps.gajjala import si_track as SIT
    from scripts import gajjala_si_follow_backfill as BF
    b = BF.splits_only_budget(1)
    assert isinstance(b, SIT.Budget)
    assert all(b.take("load") for _ in range(5)) and b.loads == 0 and b.deferred == 0
    assert b.take("split") is True and b.take("split") is False
    assert (b.split_calls, b.deferred, b.loads) == (1, 1, 0)
    assert b.take("load") is True and b.deferred == 1                   # a stored-only load stays free past the cap


def test_NEGATIVE_the_load_run_still_charges_loads(monkeypatch):
    from scripts import gajjala_si_follow_backfill as BF
    import tests.test_gajjala_si_follow_2026_11_26 as T
    st = T._recorded()
    out = BF.run(st, T.utc(T.N, "20:30"), load=True, max_loads=3, load_1m=lambda s, d: T._minutes(d),
                 split_lookup=lambda s, lo, hi: False)
    assert out[-1]["loads"] > 0 and out[-1]["loads"] + out[-1]["split_calls"] == 3


# ═════════════════════════════════════════════ miss 3 — --night exits 1 on any read fault
def test_NEGATIVE_script_night_exits_1_when_follow_docs_cannot_be_read(monkeypatch, capsys):
    from chart_maps.gajjala import si_track as SIT
    from scripts import gajjala_si_follow_backfill as BF
    import tests.test_gajjala_si_follow_2026_11_26 as T
    st = T._recorded()
    now = T.utc(T.N, "20:30")
    assert BF.main(["--night"], store=st, now=now) == 0
    clean = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert clean["faults"] == []
    real = SIT.state_read
    monkeypatch.setattr(SIT, "state_read", lambda s, sid: None if sid.startswith("si_follow|") else real(s, sid))
    assert BF.main(["--night"], store=st, now=now) == 1
    p = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert p["faults"] and all(f.startswith("read:") for f in p["faults"]) and "index_read" not in p["faults"]


# ═════════════════════════════════════════════ miss 4 — the --modes probe
@pytest.mark.parametrize("pair,flip", [
    ([[False, "a"], [False, "b"]], False), ([[True, "a"], [True, "b"]], False),
    ([[False, "a"], [True, "a"]], True), ([[True, "x"], [False, "y"]], True),
    ([None, None], False), (None, False), ([[False, "a"], None], False), ([[], [True]], False), ("xx", False),
])
def test_list_flip_is_only_a_listed_true_false_flip(pair, flip):
    from scripts import si_share_basis_probe as PR
    assert PR._list_flip(pair) is flip


def test_NEGATIVE_a_changed_reason_off_the_list_both_ways_is_a_mover_not_a_list_move(monkeypatch):
    from scripts import si_share_basis_probe as PR
    from tests.test_si_share_count_verdict_2026_11_26 import _no_refresh, _probe_db
    monkeypatch.setattr(PR, "_listed", lambda block, rd: None if rd is None else [False, str(block.get("tier"))])
    out = PR.modes_run(db=_probe_db(), now=datetime(2026, 11, 27, 3, tzinfo=timezone.utc), today=TODAY,
                       refresh=_no_refresh, reads={"POM": {"symbol": "POM"}})
    d = out["movers"]["issuance_before_float"]
    assert [r["symbol"] for r in d] == ["POM"] and d[0]["listed"] == [[False, "None"], [False, "moderate"]]
    assert out["list_moves"]["issuance_before_float"] == []


def _modes_out():
    return {"built_mode": BM.FLOAT_FRESH_WHEN, "n_docs": 0, "n_read": 0, "refreshed": [], "movers": {},
            "list_moves": {}, "refresh_errors": {}}


def test_main_modes_prints_the_attempted_write_methods(monkeypatch, tmp_path, capsys):
    from scripts import si_share_basis_probe as PR
    monkeypatch.setattr(PR, "session_reads", lambda *a, **k: {})
    monkeypatch.setattr(PR, "modes_run", lambda **k: _modes_out())
    args = argparse.Namespace(symbols="", with_fts=False, out=str(tmp_path))
    rc = PR._main_modes(args, db=None, now=datetime(2026, 11, 27, 3, tzinfo=timezone.utc), today=TODAY, key="k",
                        attempted=["update_one", "insert_one", "update_one"])
    assert rc == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last == 'attempted writes: 3 {"update_one": 2, "insert_one": 1}'
    saved = json.loads((tmp_path / "si_share_basis_modes.json").read_text(encoding="utf-8"))
    assert saved["attempted_write_methods"] == {"update_one": 2, "insert_one": 1}


def test_NEGATIVE_main_modes_with_no_attempted_write_prints_zero_and_an_empty_map(monkeypatch, tmp_path, capsys):
    from scripts import si_share_basis_probe as PR
    monkeypatch.setattr(PR, "session_reads", lambda *a, **k: {})
    monkeypatch.setattr(PR, "modes_run", lambda **k: _modes_out())
    args = argparse.Namespace(symbols="", with_fts=False, out=str(tmp_path))
    assert PR._main_modes(args, db=None, now=datetime(2026, 11, 27, 3, tzinfo=timezone.utc), today=TODAY,
                          key="k", attempted=[]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "attempted writes: 0 {}"
