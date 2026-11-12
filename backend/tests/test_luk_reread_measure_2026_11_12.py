"""🥇 Luk — scripts/luk_reread_measure.py (luk realtime cards spec WP-A, 2026-11-12).

Ajay 2026-11-12: "Luks scan is not realtime I see all dated values can you make it realtime"

The report over fake pass docs (before / after the first pass that carries `refresh`), the probe over the pass's own
board engine, and the NEGATIVE: the script never writes (a recording store sees no write).
"""
from __future__ import annotations

import copy

from chart_maps.gajjala import store as GS
from chart_maps.luk import bars as BA
from chart_maps.luk import constants as LC
from chart_maps.luk import detectors as DT
from chart_maps.luk import run as LR
from chart_maps.luk import store as ST
from scripts import luk_reread_measure as M
from tests.test_luk_reread_pass_2026_11_12 import D, OLD, PBR, _r, seed
from tests.test_luk_run import DAY, FakeF, at, mk_store


def _passes(st):
    for hhmm, wall, rf in (("09:31", 8.0, None), ("09:36", 10.0, None), ("09:41", 12.0, LR._refresh_skipped("x")),
                           ("09:46", 14.0, dict(LR._refresh_skipped("y"), on=True, skipped=None, asked_n=3,
                                                read_n=2, not_read=["ZZZ"]))):
        body = {"status": "ok", "wall_s": wall}
        if rf is not None:
            body["refresh"] = rf
        st.record_pass(D, at(hhmm, 7), body)
    st.record_pass(D, at("09:48", 7), {"status": "ok", "wall_s": 99.0, "on_demand": True,
                                       "refresh": LR._refresh_skipped("z")},
                   hhmm="09:48:07|on_demand", source=GS.LEASE_ON_DEMAND)
    st.record_pass(D, at("09:51", 7), {"status": "error", "wall_s": 50.0, "refresh": LR._refresh_skipped("e")})


def test_report_splits_before_and_after_the_first_refresh_pass():
    st, _colls = mk_store()
    _passes(st)
    r = M.report(st, DAY)
    assert [row["id"] for row in r["rows"]] == [f"{DAY}|09:31", f"{DAY}|09:36", f"{DAY}|09:41", f"{DAY}|09:46",
                                                f"{DAY}|09:48:07|on_demand", f"{DAY}|09:51"]
    assert r["first_refresh_at"].startswith(f"{DAY}T09:41")
    assert r["before"] == {"n": 2, "p50": 9.0, "p90": 8.0}
    assert r["after"] == {"n": 2, "p50": 13.0, "p90": 12.0}                     # NEGATIVE: OD + error passes out
    row = r["rows"][3]["refresh"]
    assert row["asked_n"] == 3 and row["read_n"] == 2 and row["not_read"] == ["ZZZ"] and row["skipped"] is None
    assert r["rows"][0]["refresh"] is None
    text = M.render_report(r)
    assert "before: ok cron passes 2" in text and "not_read=[\"ZZZ\"]" in text


def test_NEGATIVE_report_with_no_refresh_pass_is_all_before():
    st, _colls = mk_store()
    st.record_pass(D, at("09:31", 7), {"status": "ok", "wall_s": 8.0})
    r = M.report(st, DAY)
    assert r["first_refresh_at"] is None and r["before"]["n"] == 1 and r["after"] == {"n": 0, "p50": None, "p90": None}
    assert M.report(st, "2026-11-04")["rows"] == []


def test_NEGATIVE_the_script_never_writes(monkeypatch, capsys):
    real, colls = mk_store()
    _passes(real)
    seed(colls, "CCC", _r(PBR, "forming"))
    before = {k: c.writes for k, c in colls.items()}
    dry = ST.dry_store(real)
    assert M.main(["--report", "--date", DAY], store=dry) == 0
    assert "first pass carrying refresh" in capsys.readouterr().out

    def frames_for(names, session, now, *, load_day, budget_sec, stats):
        stats.update(loaded=len(names))
        out = {}
        for s in names:
            out[s] = FakeF(at("09:40"), at("09:40"))
        return out
    monkeypatch.setattr(BA, "frames_for", frames_for)
    monkeypatch.setattr(DT, "read_all", lambda F, facts, iso, prev_through_1m=None: _r(PBR, "stopped"))
    p = M.probe(dry, D, load_day=lambda *a, **k: None, now=at("09:52"))
    assert p["asked_n"] == 1 and p["changes"] == [f"CCC:{PBR}:forming->stopped"]
    assert dry.writes == [] and {k: c.writes for k, c in colls.items()} == before
    assert colls[GS.READS].docs[f"{DAY}|CCC"]["updated_at"] == OLD


def test_probe_reads_the_pass_engine_and_skips_the_shortlist(monkeypatch):
    st, colls = mk_store()
    seed(colls, "AAA", _r(PBR, "forming"))
    seed(colls, "CCC", _r(PBR, "forming"))
    st.record_pass(D, at("09:36", 7), {"status": "ok", "shortlist": {"symbols": ["AAA"]}})
    seen = {}

    def frames_for(names, session, now, *, load_day, budget_sec, stats):
        seen["names"], seen["budget"] = list(names), budget_sec
        return {}
    monkeypatch.setattr(BA, "frames_for", frames_for)
    p = M.probe(st, D, load_day=lambda *a, **k: None, now=at("09:52"))
    assert seen["names"] == ["CCC"] and p["board_n"] == 2 and p["asked_n"] == 1
    assert seen["budget"] == LC.LUK_PASS_BUDGET_SEC - LC.LUK_GRADE_BUDGET_SEC
    assert copy.deepcopy(p["changes"]) == []
