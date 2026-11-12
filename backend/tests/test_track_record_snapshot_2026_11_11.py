"""Track-record row snapshot (spec rec157 WP-3, 2026-11-11) — the merge, the store, the crash points, the probe's pure
parts and the source guards. Hermetic: every store lives under tmp_path; the probe is fed an in-memory Mongo stand-in.
Record only — nothing here is served."""
from __future__ import annotations

import ast
import copy
import gzip
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import track_record_snapshot as TS
from scripts import track_record_snapshot_probe as P

BACKEND = Path(__file__).resolve().parents[1]
CLI_SRC = (BACKEND / "scripts" / "track_record_snapshot.py").read_text(encoding="utf-8")
PROBE_SRC = (BACKEND / "scripts" / "track_record_snapshot_probe.py").read_text(encoding="utf-8")
DOC = BACKEND.parent / "docs" / "gajjala" / "track_record_snapshot_2026_11_11.md"


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def gg5_row(sym="ABCD", d="2026-11-11", setup="squeeze", kind="aplus", **kw):
    row = {"variant": "gajjala", "id": f"{d}|{sym}|{setup}|{kind}", "date": d, "symbol": sym, "setup": setup,
           "kind": kind, "line": "live", "at_utc": f"{d}T15:01:00+00:00", "trigger": 2.0, "stop": 1.8,
           "same": {"outcome": "win", "r": 1.0}, "next": None, "state_same": "win", "state_next": "pending",
           "bucket": "win", "dup_of": None,
           "ctx_eod": {"float_shares": 1_000_000, "rotation_x": 3.1}, "audit": {"aplus": True, "failed": []},
           "avg_vol_50": 250000.0, "avg_vol_50_date": d, "bars": {"cached": True, "n_before": 30},
           "src_present": {"ctx_eod": True, "audit": True, "avg_vol_50": True, "bars": True}}
    row.update(kw)
    return row


def gg1_row(sym="ABCD", d="2026-11-11", setup="squeeze", kind="aplus", **kw):
    row = gg5_row(sym, d, setup, kind)
    row["variant"] = "gajjala_1m"
    row["audit"] = None
    row["src_present"] = {"ctx_eod": True, "audit": False, "avg_vol_50": True, "bars": True}
    row.update(kw)
    return row


def gga_row(sym="ABCD", d="2026-11-11", setup="squeeze", **kw):
    row = {"id": f"{d}|{sym}|{setup}|aplus", "date": d, "symbol": sym, "setup": setup, "kind": "aplus",
           "at_utc": f"{d}T15:01:00+00:00", "audit_raw": {"aplus": True, "failed": [], "rules": ["K3"]},
           "audit_cell": {"state": "passed", "text": "passed", "sub_text": None}, "src_present": {"audit": True}}
    row.update(kw)
    return row


def luk_row(sym="IONR", d="2026-11-11", setup="opening_range_high", **kw):
    row = {"id": f"{d}|{sym}|{setup}|aplus", "date": d, "symbol": sym, "setup": setup,
           "at_utc": f"{d}T14:35:00+00:00", "trigger": 5.0, "stop": 4.8, "fill_px": 5.1, "exit_px": 4.8,
           "cell": {"state": "loss", "r": -1.5}, "fill": {"entry": "filled", "fill_px": 5.1},
           "walk": {"exit": "stop", "exit_px": 4.8, "r": -1.0}, "version": 1,
           "bars": {"cached": True}, "ctx_eod": {"facts": {"ema9": 5.0}, "tier": "lead", "tile": "x" * 20},
           "daily": {"facts": {"adr20_pct": 6.1}, "source": "cache", "daily_cached_at": "2026-11-11T21:00:00"},
           "src_present": {"bars": True, "ctx_eod": True, "daily": True}}
    row.update(kw)
    return row


def mk_dump(gg5=None, gg1=None, gga=None, luk=None, today="2026-11-12"):
    pages = {"gg5": list(gg5 or []), "gg1": list(gg1 or []), "gga": list(gga or []), "luk": list(luk or [])}
    return {"generated_utc": f"{today}T21:30:00+00:00", "today_et": today,
            "constants": {"ledger_r_mult": 1.0, "ledger_min_r_pct": 0.5, "fill_from_et": "09:45:00",
                          "fill_to_et": "16:00:00", "luk_grade_version": 1},
            "pages": pages, "sessions": {p: sorted({r["date"] for r in pages[p]}) for p in pages}, "faults": []}


def base_dump(today="2026-11-12"):
    return mk_dump(gg5=[gg5_row(), gg5_row(kind="potential"), gg5_row("WXYZ", "2026-11-10", "vcp")],
                   gg1=[gg1_row()], gga=[gga_row()], luk=[luk_row()], today=today)


def state(d: Path) -> dict:
    """{relpath: (bytes, mtime_ns)} of every file under d (byte-equal + not rewritten)."""
    out = {}
    if not d.exists():
        return out
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d))] = (p.read_bytes(), p.stat().st_mtime_ns)
    return out


def lines_of(out: Path) -> list:
    p = out / "merged.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def run_ok(dump, out, sd=None):
    code, summ = TS.run(dump, out, sd)
    assert code == 0, summ
    return summ


def cli(argv, capsys):
    code = TS.main(argv)
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return code, json.loads(out)


def write_json(tmp_path, dump, name="probe.json"):
    p = tmp_path / name
    p.write_text(json.dumps(dump), encoding="utf-8")
    return str(p)


# ── the key [C6] ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_key_is_page_and_the_engine_row_id():
    assert TS.key_of("gg5", gg5_row()) == "gg5|2026-11-11|ABCD|squeeze|aplus"
    assert TS.key_of("luk", luk_row()) == "luk|2026-11-11|IONR|opening_range_high|aplus"


def test_a_potential_and_its_aplus_are_two_keys(tmp_path):
    run_ok(mk_dump(gg5=[gg5_row(kind="aplus"), gg5_row(kind="potential")]), tmp_path)
    keys = {ln["key"] for ln in lines_of(tmp_path)}
    assert keys == {"gg5|2026-11-11|ABCD|squeeze|aplus", "gg5|2026-11-11|ABCD|squeeze|potential"}


def test_negative_a_restamped_alert_time_is_version_2_of_one_key_never_a_second_key(tmp_path):
    run_ok(mk_dump(gg5=[gg5_row()]), tmp_path)
    s = run_ok(mk_dump(gg5=[gg5_row(at_utc="2026-11-11T15:02:00+00:00")]), tmp_path)
    ls = lines_of(tmp_path)
    assert [(ln["key"], ln["v"]) for ln in ls] == [("gg5|2026-11-11|ABCD|squeeze|aplus", 1),
                                                    ("gg5|2026-11-11|ABCD|squeeze|aplus", 2)]
    assert s["appended"]["gg5"] == 1
    assert ls[1]["row"]["at_utc"] == "2026-11-11T15:02:00+00:00"


def test_latest_rows_returns_one_row_per_dump_key_with_the_carried_blocks_and_leaves_out_kept_only_keys(tmp_path):
    run_ok(mk_dump(gg5=[gg5_row(), gg5_row("GONE")]), tmp_path)
    expired = gg5_row(ctx_eod=None, src_present={"ctx_eod": False, "audit": True, "avg_vol_50": True, "bars": True},
                      same={"outcome": "loss", "r": -1.0})
    d2 = mk_dump(gg5=[expired])
    run_ok(d2, tmp_path)
    lat = TS.latest_rows(lines_of(tmp_path), TS.dump_keys(d2))
    assert list(lat) == ["gg5|2026-11-11|ABCD|squeeze|aplus"]
    assert lat["gg5|2026-11-11|ABCD|squeeze|aplus"]["ctx_eod"] == gg5_row()["ctx_eod"]
    assert lat["gg5|2026-11-11|ABCD|squeeze|aplus"]["same"]["outcome"] == "loss"
    assert "gg5|2026-11-11|GONE|squeeze|aplus" in TS.latest_rows(lines_of(tmp_path))


@pytest.mark.parametrize("bad, why", [
    ({"id": None}, "without an id"), ({"id": ""}, "without an id"), ("dup", "duplicate ids"),
])
def test_negative_a_row_without_an_id_or_a_duplicate_id_is_refused_and_nothing_is_written(tmp_path, bad, why):
    rows = [gg5_row(), gg5_row(**bad)] if bad != "dup" else [gg5_row(), gg5_row()]
    code, summ = TS.run(mk_dump(gg5=rows), tmp_path)
    assert code == 2 and why in summ["refused"]
    assert state(tmp_path) == {}


# ── the merge rule ───────────────────────────────────────────────────────────────────────────────────────────────
def test_a_row_that_left_the_dump_is_kept_byte_equal(tmp_path):
    run_ok(base_dump("2026-11-11"), tmp_path, "2026-11-11")
    before = (tmp_path / "merged.jsonl").read_bytes()
    d = base_dump()
    d["pages"]["gg5"] = [r for r in d["pages"]["gg5"] if r["symbol"] != "WXYZ"]
    d["pages"]["gg5"][0]["same"] = {"outcome": "loss", "r": -1.0}
    run_ok(d, tmp_path)
    after = (tmp_path / "merged.jsonl").read_bytes()
    assert after.startswith(before)
    kept = [ln for ln in lines_of(tmp_path) if "WXYZ" in ln["key"]]
    assert len(kept) == 1 and kept[0]["v"] == 1
    v = TS.verify(None, d, None, tmp_path)
    assert v["kept_not_in_mongo"]["gg5"] == 1


def test_a_changed_grade_appends_version_2_with_the_new_snapshot_date_and_keeps_version_1(tmp_path):
    run_ok(mk_dump(gg5=[gg5_row()], today="2026-11-11"), tmp_path, "2026-11-11")
    run_ok(mk_dump(gg5=[gg5_row(same={"outcome": "loss", "r": -1.0})], today="2026-11-12"), tmp_path)
    ls = lines_of(tmp_path)
    assert [(ln["v"], ln["snapshot_date"], ln["row"]["same"]["outcome"]) for ln in ls] == [
        (1, "2026-11-11", "win"), (2, "2026-11-12", "loss")]


def test_the_same_row_twice_is_one_version_and_a_third_run_writes_nothing(tmp_path):
    d = base_dump()
    s1 = run_ok(d, tmp_path)
    assert sum(s1["appended"].values()) == 6
    s2 = run_ok(copy.deepcopy(d), tmp_path)
    assert sum(s2["appended"].values()) == 0
    st = state(tmp_path)
    s3 = run_ok(copy.deepcopy(d), tmp_path)
    assert sum(s3["appended"].values()) == 0 and s3["recovered"] == {"dumps": [], "lines": 0}
    assert state(tmp_path) == st
    assert len(lines_of(tmp_path)) == 6


TTL_CASES = [("gg5", gg5_row, b) for b in ("ctx_eod", "audit", "avg_vol_50", "bars")] + \
            [("gg1", gg1_row, b) for b in ("ctx_eod", "avg_vol_50", "bars")] + \
            [("luk", luk_row, b) for b in ("ctx_eod", "daily", "bars")]


def _page_dump(page, row):
    return mk_dump(**{page: [row]})


@pytest.mark.parametrize("page, mk, block", TTL_CASES, ids=[f"{p}-{b}" for p, _, b in TTL_CASES])
def test_an_expired_ttl_block_is_carried_and_makes_no_new_version(tmp_path, page, mk, block):
    run_ok(_page_dump(page, mk()), tmp_path)
    r = mk(**{block: None})
    r["src_present"] = dict(r["src_present"], **{block: False})
    s = run_ok(_page_dump(page, r), tmp_path)
    assert s["appended"][page] == 0
    assert len(lines_of(tmp_path)) == 1
    lat = TS.latest_rows(lines_of(tmp_path))
    assert list(lat.values())[0][block] == mk()[block]


@pytest.mark.parametrize("page, mk, block", TTL_CASES, ids=[f"{p}-{b}" for p, _, b in TTL_CASES])
def test_negative_a_none_with_its_source_present_is_a_real_change(tmp_path, page, mk, block):
    run_ok(_page_dump(page, mk()), tmp_path)
    run_ok(_page_dump(page, mk(**{block: None})), tmp_path)
    ls = lines_of(tmp_path)
    assert [ln["v"] for ln in ls] == [1, 2] and ls[1]["row"][block] is None and ls[1]["carried"] == []


@pytest.mark.parametrize("page, mk, block", TTL_CASES, ids=[f"{p}-{b}" for p, _, b in TTL_CASES])
def test_negative_none_then_a_value_is_a_new_version(tmp_path, page, mk, block):
    r = mk(**{block: None})
    r["src_present"] = dict(r["src_present"], **{block: False})
    run_ok(_page_dump(page, r), tmp_path)
    run_ok(_page_dump(page, mk()), tmp_path)
    ls = lines_of(tmp_path)
    assert [ln["v"] for ln in ls] == [1, 2] and ls[1]["row"][block] == mk()[block]


def test_gga_expired_overlay_is_carried_on_both_audit_blocks(tmp_path):
    run_ok(mk_dump(gga=[gga_row()]), tmp_path)
    run_ok(mk_dump(gga=[gga_row(audit_raw=None, src_present={"audit": False})]), tmp_path)
    assert len(lines_of(tmp_path)) == 1


def test_a_carried_block_is_named_when_a_new_version_is_written_for_another_reason(tmp_path):
    run_ok(mk_dump(luk=[luk_row()]), tmp_path)
    r = luk_row(ctx_eod=None, daily=None, cell={"state": "loss", "r": -2.0})
    r["src_present"] = {"bars": True, "ctx_eod": False, "daily": False}
    run_ok(mk_dump(luk=[r]), tmp_path)
    ls = lines_of(tmp_path)
    assert ls[1]["v"] == 2 and ls[1]["carried"] == ["ctx_eod", "daily"]
    assert ls[1]["row"]["ctx_eod"] == luk_row()["ctx_eod"] and ls[1]["row"]["daily"] == luk_row()["daily"]
    assert ls[1]["row"]["cell"]["r"] == -2.0


def test_avg_vol_50_date_expires_with_its_block_and_is_carried_with_it(tmp_path):
    run_ok(mk_dump(gg5=[gg5_row()]), tmp_path)
    r = gg5_row(avg_vol_50=None, avg_vol_50_date=None)
    r["src_present"]["avg_vol_50"] = False
    s = run_ok(mk_dump(gg5=[r]), tmp_path)
    assert s["appended"]["gg5"] == 0


def test_merge_row_is_pure_and_src_present_alone_is_never_content():
    prev = gg5_row()
    row = gg5_row(src_present={"ctx_eod": False, "audit": False, "avg_vol_50": False, "bars": False})
    stored, carried, new = TS.merge_row(prev, row, "gg5")
    assert (new, carried) == (False, []) and stored is prev
    assert TS.merge_row(None, row, "gg5") == (row, [], True)


# ── the dump file ────────────────────────────────────────────────────────────────────────────────────────────────
def test_deterministic_gzip_two_writes_of_one_dump_give_one_sha():
    a, b = TS.dump_bytes(base_dump()), TS.dump_bytes(copy.deepcopy(base_dump()))
    assert a == b
    d2 = base_dump()
    d2["generated_utc"] = "2030-01-01T00:00:00+00:00"
    assert TS.dump_bytes(d2) == a                                    # generated_utc is not content
    assert "generated_utc" not in json.loads(gzip.decompress(a))


def test_a_same_date_dump_with_other_content_lands_on_r2_and_the_first_file_is_byte_kept(tmp_path):
    s1 = run_ok(base_dump(), tmp_path)
    first = (tmp_path / s1["dump_file"]).read_bytes()
    d = base_dump()
    d["pages"]["gg5"][0]["same"] = {"outcome": "loss", "r": -1.0}
    s2 = run_ok(d, tmp_path)
    assert s1["dump_file"] == "dumps/2026-11-12.json.gz" and s2["dump_file"] == "dumps/2026-11-12.r2.json.gz"
    assert (tmp_path / s1["dump_file"]).read_bytes() == first
    s3 = run_ok(copy.deepcopy(d), tmp_path)
    assert s3["dump_file"] == "dumps/2026-11-12.r2.json.gz"
    assert not (tmp_path / "dumps" / "2026-11-12.r3.json.gz").exists()


def test_negative_a_snapshot_date_after_the_probe_session_is_refused(tmp_path):
    code, summ = TS.run(base_dump(), tmp_path, "2026-11-13")
    assert code == 2 and "after the probe" in summ["refused"]
    assert state(tmp_path) == {}


# ── the manifest + null counts [C7] ──────────────────────────────────────────────────────────────────────────────
def test_the_manifest_lists_rows_per_session_shas_and_hand_counted_nulls(tmp_path):
    d = base_dump()
    d["pages"]["gg5"][1]["avg_vol_50"] = None
    d["pages"]["gg5"][2]["avg_vol_50"] = None
    d["pages"]["gg5"][2]["bars"] = None
    run_ok(d, tmp_path)
    man = json.loads((tmp_path / "manifest.json").read_text())
    e = man["dumps"][0]
    assert e["rows"] == {"gg5": {"2026-11-10": 1, "2026-11-11": 2}, "gg1": {"2026-11-11": 1},
                         "gga": {"2026-11-11": 1}, "luk": {"2026-11-11": 1}}
    assert e["sha256"] == TS._sha((tmp_path / "dumps" / e["file"]).read_bytes())
    assert e["bytes"] == (tmp_path / "dumps" / e["file"]).stat().st_size
    assert e["generated_utc"] == d["generated_utc"]
    assert e["nulls"]["gg5"] == {"ctx_eod": [0, 3], "audit": [0, 3], "avg_vol_50": [2, 3], "bars": [1, 3]}
    raw = (tmp_path / "merged.jsonl").read_bytes()
    assert man["merged"]["bytes"] == len(raw) and man["merged"]["sha256"] == TS._sha(raw)
    assert man["merged"]["lines"] == 6 and man["merged"]["keys"] == 6
    assert man["merged"]["versions_by_page"] == {"gg5": 3, "gg1": 1, "gga": 1, "luk": 1}


def test_all_null_names_a_block_none_on_every_row_and_not_one_none_on_all_but_one():
    d = mk_dump(gg5=[gg5_row(avg_vol_50=None), gg5_row("B", avg_vol_50=None), gg5_row("C", bars=None),
                     gg5_row("D", bars=None)])
    d["pages"]["gg5"][0]["bars"] = None
    nulls = TS.null_counts(d)
    assert nulls["gg5"]["avg_vol_50"] == [2, 4] and nulls["gg5"]["bars"] == [3, 4]
    assert TS.all_null(nulls) == []
    d["pages"]["gg5"][2]["avg_vol_50"] = None
    d["pages"]["gg5"][3]["avg_vol_50"] = None
    assert TS.all_null(TS.null_counts(d)) == [["gg5", "avg_vol_50"]]
    assert ["gg1", "ctx_eod"] not in TS.all_null(TS.null_counts(d))       # an empty page is never "all null"


def test_never_captured_counts_a_key_whose_every_version_held_none_and_not_one_that_held_a_value_once(tmp_path):
    a = gg5_row("A", avg_vol_50=None)
    b = gg5_row("B")
    run_ok(mk_dump(gg5=[a, b]), tmp_path)
    b2 = gg5_row("B", avg_vol_50=None, same={"outcome": "loss"})
    a2 = gg5_row("A", avg_vol_50=None, same={"outcome": "loss"})
    run_ok(mk_dump(gg5=[a2, b2]), tmp_path)
    nc = json.loads((tmp_path / "manifest.json").read_text())["merged"]["never_captured"]
    assert nc["gg5"]["avg_vol_50"] == 1 and nc["gg5"]["ctx_eod"] == 0


# ── the probe dump's shape ───────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("mut, why", [
    (lambda d: d["pages"].__setitem__("gga", None), "page gga is null"),
    (lambda d: d["pages"].pop("luk"), "page luk is missing"),
    (lambda d: d.pop("pages"), "no 'pages'"),
    (lambda d: d["pages"]["gg5"][0].pop("src_present"), "no src_present"),
    (lambda d: d["pages"].__setitem__("zzz", []), "unknown pages"),
])
def test_negative_a_dump_that_is_not_the_probe_shape_is_refused_and_nothing_is_written(tmp_path, mut, why):
    run_ok(base_dump("2026-11-11"), tmp_path, "2026-11-11")
    before = state(tmp_path)
    d = base_dump()
    mut(d)
    code, summ = TS.run(d, tmp_path)
    assert code == 2 and why in summ["refused"]
    assert state(tmp_path) == before


# ── crash points [C2] ────────────────────────────────────────────────────────────────────────────────────────────
def _raise_on(monkeypatch, name):
    real = os.replace

    def fake(src, dst):
        if Path(dst).name == name:
            raise OSError("killed")
        return real(src, dst)
    monkeypatch.setattr(TS.os, "replace", fake)


def test_crash_point_1_killed_after_the_dump_write_the_next_run_adopts_the_dump(tmp_path, monkeypatch):
    run_ok(mk_dump(gg5=[gg5_row()], today="2026-11-11"), tmp_path, "2026-11-11")
    d = base_dump()
    _raise_on(monkeypatch, "merged.jsonl")
    with pytest.raises(OSError):
        TS.run(d, tmp_path)
    monkeypatch.undo()
    assert (tmp_path / "dumps" / "2026-11-12.json.gz").exists()
    assert len(lines_of(tmp_path)) == 1
    s = run_ok(copy.deepcopy(d), tmp_path)
    assert s["recovered"]["dumps"] == ["2026-11-12.json.gz"] and s["exit"] == 0
    man = json.loads((tmp_path / "manifest.json").read_text())
    listed = {e["file"]: e for e in man["dumps"]}
    assert set(listed) == {"2026-11-11.json.gz", "2026-11-12.json.gz"}
    assert listed["2026-11-12.json.gz"]["sha256"] == TS._sha((tmp_path / "dumps/2026-11-12.json.gz").read_bytes())
    assert len(lines_of(tmp_path)) == 6
    assert TS.verify(None, d, None, tmp_path)["ok"] is True


def test_crash_point_2_killed_after_the_merged_write_the_next_run_accepts_the_tail(tmp_path, monkeypatch):
    run_ok(mk_dump(gg5=[gg5_row()], today="2026-11-11"), tmp_path, "2026-11-11")
    d = base_dump()
    _raise_on(monkeypatch, "manifest.json")
    with pytest.raises(OSError):
        TS.run(d, tmp_path)
    monkeypatch.undo()
    n_after_kill = len(lines_of(tmp_path))
    assert n_after_kill == 6
    v = TS.verify(None, d, None, tmp_path)
    assert v["ok"] is False and v["integrity"].startswith("recoverable")
    s = run_ok(copy.deepcopy(d), tmp_path)
    assert s["recovered"]["lines"] == 5 and sum(s["appended"].values()) == 0
    assert len(lines_of(tmp_path)) == n_after_kill                    # no line appended twice
    man = json.loads((tmp_path / "manifest.json").read_text())
    assert man["merged"]["lines"] == 6
    assert TS.verify(None, d, None, tmp_path)["ok"] is True


def test_a_missing_manifest_with_a_well_formed_merged_store_is_accepted(tmp_path):
    d = base_dump()
    run_ok(d, tmp_path)
    (tmp_path / "manifest.json").unlink()
    s = run_ok(copy.deepcopy(d), tmp_path)
    assert s["recovered"]["lines"] == 6 and s["recovered"]["dumps"] == ["2026-11-12.json.gz"]
    assert len(lines_of(tmp_path)) == 6
    assert TS.verify(None, d, None, tmp_path)["ok"] is True


def _seed(tmp_path):
    run_ok(mk_dump(gg5=[gg5_row()], today="2026-11-11"), tmp_path, "2026-11-11")
    run_ok(base_dump(), tmp_path)


def _flip_prefix(tmp_path):
    p = tmp_path / "merged.jsonl"
    b = bytearray(p.read_bytes())
    i = b.index(b"ABCD")
    b[i] = ord("X")
    p.write_bytes(bytes(b))


def _torn_tail(tmp_path):
    p = tmp_path / "merged.jsonl"
    p.write_bytes(p.read_bytes() + b'{"key":"gg5|x","page":"gg5"')


def _bad_unlisted(tmp_path):
    (tmp_path / "dumps" / "2026-11-13.json.gz").write_bytes(b"not a gzip")


def _moved_listed(tmp_path):
    p = tmp_path / "dumps" / "2026-11-11.json.gz"
    d = json.loads(gzip.decompress(p.read_bytes()))
    d["faults"] = ["x"]
    p.write_bytes(gzip.compress(json.dumps(d).encode()))


def _corrupt_line(tmp_path):
    p = tmp_path / "merged.jsonl"
    p.write_bytes(p.read_bytes() + b"{not json}\n")


def _gap_v(tmp_path):
    p = tmp_path / "merged.jsonl"
    ln = json.loads(p.read_text().splitlines()[0])
    ln["v"] = 3
    p.write_bytes(p.read_bytes() + (json.dumps(ln) + "\n").encode())


def _cut_last(tmp_path):
    p = tmp_path / "merged.jsonl"
    p.write_bytes(p.read_bytes()[:-1])


CORRUPT = [("prefix_flipped", _flip_prefix, "prefix sha"), ("torn_tail", _torn_tail, "torn"),
           ("unlisted_not_gzip", _bad_unlisted, "does not gunzip"), ("listed_moved", _moved_listed, "sha moved"),
           ("corrupt_line", _corrupt_line, "does not parse"), ("non_contiguous_v", _gap_v, "not contiguous"),
           ("cut_last_line", _cut_last, "")]


@pytest.mark.parametrize("name, mut, why", CORRUPT, ids=[c[0] for c in CORRUPT])
def test_negative_a_corrupt_store_is_refused_exit_2_and_every_file_is_byte_equal(tmp_path, capsys, name, mut, why):
    _seed(tmp_path)
    mut(tmp_path)
    before = state(tmp_path)
    code, out = cli(["--out", str(tmp_path), "--from-json", write_json(tmp_path.parent, base_dump(),
                                                                         f"{name}.json")], capsys)
    assert code == 2 and out["exit"] == 2 and why in out["refused"]
    assert state(tmp_path) == before
    vcode, vout = cli(["--out", str(tmp_path), "--verify", "--from-json",
                       str(tmp_path.parent / f"{name}.json")], capsys)
    assert vcode == 1 and vout["integrity"] != "ok"
    assert state(tmp_path) == before


def test_negative_verify_on_a_recoverable_store_exits_1_and_writes_nothing(tmp_path, capsys):
    d = base_dump()
    run_ok(d, tmp_path)
    (tmp_path / "manifest.json").unlink()
    before = state(tmp_path)
    code, out = cli(["--out", str(tmp_path), "--verify", "--from-json", write_json(tmp_path.parent, d)], capsys)
    assert code == 1 and out["integrity"].startswith("recoverable")
    assert state(tmp_path) == before


# ── --verify / --dry-run ─────────────────────────────────────────────────────────────────────────────────────────
def test_verify_passes_right_after_a_merge(tmp_path, capsys):
    d = base_dump()
    f = write_json(tmp_path.parent, d)
    code, out = cli(["--out", str(tmp_path), "--from-json", f], capsys)
    assert code == 0 and out["exit"] == 0 and out["dump_file"] == "dumps/2026-11-12.json.gz"
    code, out = cli(["--out", str(tmp_path), "--verify", "--from-json", f], capsys)
    assert code == 0 and out["integrity"] == "ok" and out["not_covered"] == []
    assert out["covered"] == {"gg5": 3, "gg1": 1, "gga": 1, "luk": 1}
    assert out["kept_not_in_mongo"] == {"gg5": 0, "gg1": 0, "gga": 0, "luk": 0}


@pytest.mark.parametrize("change", ["new_row", "grade_moved"])
def test_negative_verify_fails_when_a_mongo_row_is_not_in_the_store_or_a_grade_moved(tmp_path, change):
    run_ok(base_dump(), tmp_path)
    d = base_dump()
    if change == "new_row":
        d["pages"]["luk"].append(luk_row("NEWX"))
        want = "luk|2026-11-11|NEWX|opening_range_high|aplus"
    else:
        d["pages"]["gg1"][0]["same"] = {"outcome": "loss", "r": -1.0}
        want = "gg1|2026-11-11|ABCD|squeeze|aplus"
    before = state(tmp_path)
    v = TS.verify(None, d, None, tmp_path)
    assert v["ok"] is False and v["not_covered"] == [want] and v["integrity"] == "ok"
    assert state(tmp_path) == before


def test_negative_verify_fails_on_a_tampered_dump(tmp_path):
    run_ok(base_dump(), tmp_path)
    _moved_listed_any(tmp_path)
    v = TS.verify(None, base_dump(), None, tmp_path)
    assert v["ok"] is False and "sha moved" in v["integrity"]


def _moved_listed_any(tmp_path):
    p = tmp_path / "dumps" / "2026-11-12.json.gz"
    p.write_bytes(p.read_bytes() + b"\x00")


def test_verify_and_dry_run_write_nothing(tmp_path, capsys):
    f = write_json(tmp_path.parent, base_dump())
    code, out = cli(["--out", str(tmp_path), "--dry-run", "--from-json", f], capsys)
    assert code == 0 and out["dry_run"] is True and sum(out["appended"].values()) == 6
    assert state(tmp_path) == {}
    run_ok(base_dump(), tmp_path)
    before = state(tmp_path)
    d = base_dump()
    d["pages"]["gg5"][0]["same"] = {"outcome": "loss"}
    f2 = write_json(tmp_path.parent, d, "p2.json")
    assert cli(["--out", str(tmp_path), "--dry-run", "--from-json", f2], capsys)[0] == 0
    assert cli(["--out", str(tmp_path), "--verify", "--from-json", f2], capsys)[0] == 1
    assert state(tmp_path) == before


def test_negative_an_unreadable_from_json_is_refused_exit_2(tmp_path, capsys):
    bad = tmp_path.parent / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    code, out = cli(["--out", str(tmp_path), "--from-json", str(bad)], capsys)
    assert code == 2 and state(tmp_path) == {}


# ── the probe's pure parts [C7] ──────────────────────────────────────────────────────────────────────────────────
def test_prev_session_skips_a_holiday_and_a_weekend():
    assert P.prev_session("2026-11-27") == "2026-11-25"               # 11-26 Thanksgiving is closed
    assert P.prev_session("2026-11-16") == "2026-11-13"               # Monday → Friday
    assert P.prev_session(date(2026, 11, 12)) == "2026-11-11"


def test_prev_session_equals_the_house_prev_market_day_over_every_2026_date():
    from supply_demand.key_levels import prev_market_day
    d = date(2026, 1, 1)
    while d.year == 2026:
        assert P.prev_session(d.isoformat()) == prev_market_day(d).isoformat(), d
        d += timedelta(days=1)


class _Coll:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, flt, proj=None, sort=None):
        if "_id" in flt:
            return next((d for d in self.docs if d.get("_id") == flt["_id"]), None)
        hits = [d for d in self.docs if d.get("symbol") == flt.get("symbol")]
        dflt = flt.get("date")
        if isinstance(dflt, dict):
            hits = [d for d in hits if d["date"] <= dflt["$lte"] and (d.get("avg_vol_50") or 0) > 0]
            hits.sort(key=lambda d: d["date"], reverse=True)
        else:
            hits = [d for d in hits if d.get("date") == dflt]
        return hits[0] if hits else None


class _DB:
    def __init__(self, **colls):
        self.colls = {k: _Coll(v) for k, v in colls.items()}

    def __getattr__(self, name):
        return self.colls.setdefault(name, _Coll([]))

    def __getitem__(self, name):
        return getattr(self, name)


def _bars(d, closes, session="rth"):
    t0 = datetime.fromisoformat(f"{d}T14:30:00")
    return [{"ts_utc": (t0 + timedelta(minutes=i)).isoformat(), "open": c, "high": c + 0.1, "low": c - 0.1,
             "close": c, "volume": 100.0, "session": session} for i, c in enumerate(closes)]


def test_bar_feats_reads_the_previous_close_from_the_previous_MARKET_day_never_the_holiday():
    db = _DB(intraday_cache=[{"symbol": "ABCD", "date": "2026-11-27", "bars": _bars("2026-11-27", [3.0, 3.1, 3.2])},
                             {"symbol": "ABCD", "date": "2026-11-25", "bars": _bars("2026-11-25", [2.0, 2.5])},
                             {"symbol": "ABCD", "date": "2026-11-26", "bars": _bars("2026-11-26", [9.9])}])
    p = P.Probe(db, datetime(2026, 11, 27, 21, 0, tzinfo=timezone.utc))
    f = p.bar_feats("ABCD", "2026-11-27", datetime(2026, 11, 27, 14, 32, tzinfo=timezone.utc))
    assert f["prev_close"] == 2.5 and f["n_before"] == 2 and f["last_close_before"] == 3.1
    assert p.bar_feats("NONE", "2026-11-27", datetime(2026, 11, 27, 14, 32, tzinfo=timezone.utc)) is None


def test_avg_vol_50_reads_the_latest_known_average_on_or_before_the_date():
    db = _DB(gajjala_daily=[{"symbol": "A", "date": "2026-11-10", "avg_vol_50": 10.0},
                            {"symbol": "A", "date": "2026-11-11"},
                            {"symbol": "A", "date": "2026-11-13", "avg_vol_50": 30.0}])
    p = P.Probe(db, datetime(2026, 11, 13, tzinfo=timezone.utc))
    assert p.avg_vol_50("A", "2026-11-11") == (10.0, "2026-11-10")
    assert p.avg_vol_50("A", "2026-11-09") == (None, None)


def test_the_luk_page_carries_ctx_eod_from_luk_reads_and_daily_from_luk_daily(monkeypatch):
    from chart_maps.luk import ledger as LL
    from chart_maps.luk import store as LS
    at = datetime(2026, 11, 11, 14, 35, tzinfo=timezone.utc)
    rows = [{"id": "2026-11-11|IONR|opening_range_high|aplus", "date": "2026-11-11", "symbol": "IONR",
             "setup": "opening_range_high", "at_utc": at, "trigger": 5.0, "stop": 4.8},
            {"id": "2026-11-11|ZZZ|pullback_reversal|aplus", "date": "2026-11-11", "symbol": "ZZZ",
             "setup": "pullback_reversal", "at_utc": at, "trigger": 1.0, "stop": 0.9}]

    class _St:
        def ledger_docs(self, record):
            return [{"_id": rows[0]["id"], "fill": {"entry": "filled", "fill_px": 5.1}, "walk": {"exit_px": 4.8},
                     "version": 1, "graded_at": "g", "graded_from": {"date": "2026-11-11"}}]
    monkeypatch.setattr(LS, "default", lambda: _St())
    monkeypatch.setattr(LL, "record_sessions", lambda today: [date(2026, 11, 11)])
    monkeypatch.setattr(LL, "rows_for", lambda record, store: [dict(r) for r in rows])
    monkeypatch.setattr(LL, "track_row", lambda r, doc: {"id": r["id"], "date": r["date"], "state": "loss"})
    monkeypatch.setattr(LL, "mark_dups", lambda served, docs, by_id: {})
    reads = {"_id": "2026-11-11|IONR", "facts": {"ema9": 5.0}, "tier": "lead", "tile": {"bars": [1]},
             "screens_rank": 3, "cap_text": "small", "as_of_bar_t1": "a", "as_of_bar_t5": "b", "as_of_bar_t60": "c",
             "setups": {"opening_range_high": {"aplus": True}, "pullback_reversal": {"aplus": False}}}
    daily = {"_id": "2026-11-11|IONR", "facts": {"adr20_pct": 6.0}, "source": "cache", "daily_cached_at": "t"}
    p = P.Probe(_DB(luk_reads=[reads], luk_daily=[daily]), datetime(2026, 11, 11, 22, tzinfo=timezone.utc))
    out, sessions = p.luk()
    assert sessions == ["2026-11-11"]
    a, b = out
    assert a["ctx_eod"] == {"facts": {"ema9": 5.0}, "tier": "lead", "tile": {"bars": [1]}, "screens_rank": 3,
                            "cap_text": "small", "as_of_bar_t1": "a", "as_of_bar_t5": "b", "as_of_bar_t60": "c",
                            "setup_read": {"aplus": True}}
    assert a["daily"] == {"facts": {"adr20_pct": 6.0}, "source": "cache", "daily_cached_at": "t"}
    assert a["src_present"] == {"bars": False, "ctx_eod": True, "daily": True}
    assert (a["fill_px"], a["exit_px"], a["version"], a["trigger"], a["stop"]) == (5.1, 4.8, 1, 5.0, 4.8)
    assert a["at_utc"] == at.isoformat() and a["cell"]["state"] == "loss"
    assert b["ctx_eod"] is None and b["daily"] is None                       # NEGATIVE: no doc → None, src False
    assert b["src_present"] == {"bars": False, "ctx_eod": False, "daily": False}
    assert b["fill_px"] is None and b["version"] is None


def test_the_gga_page_is_one_row_per_original_aplus_with_the_served_cell_and_the_raw_overlay(monkeypatch):
    from chart_maps.gajjala import audited_tab as AT
    from chart_maps.gajjala import store as ST
    orig = [{"id": "2026-11-11|AB|squeeze|aplus", "date": "2026-11-11", "symbol": "AB", "setup": "squeeze",
             "kind": "aplus", "at_utc": datetime(2026, 11, 11, 15, tzinfo=timezone.utc)},
            {"id": "2026-11-10|CD|vcp|aplus", "date": "2026-11-10", "symbol": "CD", "setup": "vcp",
             "kind": "aplus", "at_utc": None}]
    seen = {}

    def fake_read(st, today, now, span=""):
        seen["span"] = span
        return {"span": span, "sessions": ["2026-11-10", "2026-11-11"], "sides": {"original": orig},
                "exits_by_id": {}}
    monkeypatch.setattr(ST, "for_variant", lambda v=None: object())
    monkeypatch.setattr(AT, "read_span", fake_read)
    monkeypatch.setattr(AT, "row_audits", lambda sides, ex: {orig[0]["id"]: {"state": "held", "text": "held by K3",
                                                                              "sub_text": None, "provisional": False}})
    ov = {"_id": "2026-11-11|AB", "setups": {"squeeze": {"aplus": False, "original_aplus": True,
                                                         "failed": [{"id": "K3"}], "rules": ["K3"]}}}
    p = P.Probe(_DB(gajjala_audited_overlay=[ov]), datetime(2026, 11, 11, 22, tzinfo=timezone.utc))
    out, sessions = p.gga()
    assert seen["span"] == "all" and sessions == ["2026-11-10", "2026-11-11"]
    assert out[0]["audit_raw"] == {"aplus": False, "original_aplus": True, "failed": ["K3"], "rules": ["K3"]}
    assert out[0]["audit_cell"] == {"state": "held", "text": "held by K3", "sub_text": None}
    assert out[0]["src_present"] == {"audit": True}
    assert out[1]["audit_raw"] is None and out[1]["audit_cell"] is None and out[1]["src_present"] == {"audit": False}


# ── static pins + source guards ──────────────────────────────────────────────────────────────────────────────────
WRITE_METHODS = re.compile(r"^(insert_\w+|update_\w+|replace_\w+|delete_\w+|bulk_write|drop\w*|create_index\w*|"
                           r"find_one_and_\w+|rename|ensure_indexes|upsert_\w+|save)$")
BANNED_PROBE_IMPORTS = re.compile(r"^(trading|daytrading|massive\w*|finnhub\w*|yfinance|requests|httpx|alpaca\w*|"
                                  r"urllib\.request|curl_cffi|\w*broker\w*)(\.|$)")
B_WORD = re.compile("b" + "ounc", re.I)


def _imports(src: str) -> list:
    out = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            out.append(n.module or "")
            out += [f"{n.module}.{a.name}" for a in n.names]
    return out


def _attr_calls(src: str) -> set:
    return {n.func.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)}


def test_the_probe_names_all_four_pages_imports_chart_maps_luk_and_reads_luk_reads_and_luk_daily():
    assert P.PAGES == TS.PAGES == ("gg5", "gg1", "gga", "luk")
    for page in TS.PAGES:
        assert f'"{page}"' in PROBE_SRC
    assert any(m.startswith("chart_maps.luk") for m in _imports(PROBE_SRC))
    assert "luk_reads" in PROBE_SRC and "luk_daily" in PROBE_SRC
    assert "read_span" in PROBE_SRC and "row_audits" in PROBE_SRC


def test_the_probe_holds_no_weekday_walk_and_no_row_key_named_ctx():
    assert "prev_weekday" not in PROBE_SRC
    for n in ast.walk(ast.parse(PROBE_SRC)):
        if isinstance(n, ast.Dict):
            keys = {k.value for k in n.keys if isinstance(k, ast.Constant)}
            if "id" in keys:
                assert "ctx" not in keys


def test_negative_the_row_key_guard_catches_a_ctx_key():
    bad = 'x = {"id": 1, "ctx": 2}'
    hits = [n for n in ast.walk(ast.parse(bad)) if isinstance(n, ast.Dict)
            and {"id", "ctx"} <= {k.value for k in n.keys if isinstance(k, ast.Constant)}]
    assert hits


@pytest.mark.parametrize("src, label", [(PROBE_SRC, "probe"), (CLI_SRC, "cli")])
def test_no_mongo_write_method_is_called(src, label):
    assert {m for m in _attr_calls(src) if WRITE_METHODS.match(m)} == set(), label


def test_negative_the_write_guard_catches_a_write():
    assert {m for m in _attr_calls("db.x.update_one({}, {})\ndb.x.create_index('a')") if WRITE_METHODS.match(m)} \
        == {"update_one", "create_index"}


def test_the_probe_imports_no_trading_daytrading_broker_or_provider_module():
    assert [m for m in _imports(PROBE_SRC) if BANNED_PROBE_IMPORTS.match(m)] == []
    assert [m for m in _imports("from daytrading import data\nimport trading.broker")
            if BANNED_PROBE_IMPORTS.match(m)]                               # NEGATIVE: the guard bites


STDLIB = {"argparse", "ast", "gzip", "hashlib", "json", "math", "os", "subprocess", "sys", "tempfile", "datetime",
          "decimal", "typing", "zoneinfo", "collections", "__future__", "io", "re", "pathlib"}


def _top_imports(src):
    tops = set()
    for n in ast.walk(ast.parse(src, feature_version=(3, 9))):
        if isinstance(n, ast.Import):
            tops |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            tops.add((n.module or "").split(".")[0])
    return tops


def test_the_cli_parses_as_python_3_9_and_imports_the_stdlib_only():
    assert _top_imports(CLI_SRC) - STDLIB == set()
    assert _top_imports("import pymongo\nfrom requests import get\nimport json\n") - STDLIB \
        == {"pymongo", "requests"}                                       # NEGATIVE: a third-party import is caught
    with pytest.raises(SyntaxError):                                     # NEGATIVE: 3.10 grammar is caught
        ast.parse("match x:\n    case 1:\n        pass\n", feature_version=(3, 9))


def test_nothing_outside_scripts_and_tests_imports_either_file():
    hits = []
    skip = {"scripts", "tests", ".venv", "node_modules", "__pycache__", ".git"}
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in skip and not (Path(root) / d).is_symlink()]
        for f in files:
            if not f.endswith(".py"):
                continue
            try:
                txt = (Path(root) / f).read_text(encoding="utf-8")
            except Exception:                                           # noqa: BLE001
                continue
            if "track_record_snapshot" in txt:
                hits.append(str(Path(root) / f))
    assert hits == []


def test_the_crontab_names_neither_file():
    cron = (BACKEND / "crontab").read_text(encoding="utf-8")
    assert "track_record_snapshot" not in cron


def test_no_b_word_in_any_file_of_the_package():
    files = [CLI_SRC, PROBE_SRC, Path(__file__).read_text(encoding="utf-8")]
    if DOC.exists():
        files.append(DOC.read_text(encoding="utf-8"))
    assert [f for f in files if B_WORD.search(f)] == []


def test_the_default_store_dir_is_the_eod_audits_folder_outside_the_repo():
    assert TS.DEFAULT_OUT == "/Users/ajay/clinet-test/eod-audits/track-record-snapshots"
    assert "cheetah-market-app" not in TS.DEFAULT_OUT and ".wt-" not in TS.DEFAULT_OUT
