"""🩳 Short interest column on the 📋 All strategies table (SPEC REV 2 2026-11-16 §3.1–§3.3, WP-A, tests S1–S15).

Ajay 2026-11-16 (screenshot of the 📋 table on 🚩 Gajjala's tab), verbatim: "Add a short interest colume fo this table
when available".

all_table.HEADS gains ("si", "Short interest") LAST; every row serves si_text / si_title / si_stale / si_asof, worded by
the ONE house read (short_interest.read.si_block via read.si_map — never re-derived). tab.build's table branch hands
all_table.block an injected reader: None when no short-interest store is reachable (the fault — SI_FAULT_TEXT served,
rows kept), else SR.si_map(syms, db=db, today=_et(now).date()). DISPLAY ONLY — GG's verified rule U10: nothing ranks,
gates or alerts on it.

The hermetic suite refuses MongoClient (tests/conftest.py) → client._get_db() is None → the reader returns None. Every
test that wants the read to RUN patches short_interest.client._get_db to a truthy stub. NEGATIVES are mandatory:
no record ≠ fault (S3, S7c), a raising read (S7), no handle (S7b), the clock (S6b), 🧪 never (S9), the source guard
(S10), the case join (S14), the golden carries no live chip (S15).
"""
from __future__ import annotations

import ast
import inspect
import json
import random
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import all_table as TBL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from short_interest import client as SIC
from short_interest import read as SR
from tests.test_gajjala_all_table_2026_11_13 import (BF, NOW, T1_ORDER, _get, _walk_keys, board, fake_tile, rows_of,
                                                     store, t1_docs, table)

BACKEND = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "gg5_board_2026_10_27.json"
TODAY = date(2026, 10, 13)                          # NOW = 2026-10-13 14:31 UTC = 10:31 ET
STUB_DB = object()


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────
def si_doc(sym, *, settled="2026-09-30", si=1_200_000, fl=4_000_000, so=5_000_000, dtc=2.3):
    """A v2 short-INTEREST cache doc in the warm's shape (client.py:769-781)."""
    return {"symbol": sym, "v": 2, "short_interest": si, "settlement_date": settled, "prev_settlement_date": None,
            "prev_short_interest": None, "si_change_pct": None, "avg_daily_volume": 500_000, "days_to_cover": dtc,
            "float_shares": fl, "float_asof": "2026-10-01", "float_source": "massive", "shares_outstanding": so,
            "shares_asof": "2026-10-01", "shares_source": "massive", "fetched_at": datetime(2026, 10, 2, tzinfo=timezone.utc)}


def miss_doc(sym):
    """A remembered miss (client.py:951): no settlement on file."""
    return {"symbol": sym, "v": 2, "short_interest": None, "settlement_date": None,
            "fetched_at": datetime(2026, 10, 2, tzinfo=timezone.utc)}


def with_db(monkeypatch, db=STUB_DB):
    """A reachable short-interest handle (else the reader returns None under the conftest refusal)."""
    calls = []

    def _get_db():
        calls.append(1)
        return db
    monkeypatch.setattr(SIC, "_get_db", _get_db)
    return calls


def with_docs(monkeypatch, docs: dict):
    """The real si_map / si_block over these cache docs — the ONE-engine path (only the Mongo find is faked)."""
    seen = []

    def fake_map(symbols, db=None):
        seen.append((list(symbols), db))
        return {s: dict(docs[s]) for s in symbols if s in docs}
    monkeypatch.setattr(SIC, "short_interest_map", fake_map)
    return seen


def counting_map(monkeypatch, ret=None):
    calls = []

    def fake(symbols, db=None, today=None):
        calls.append({"symbols": list(symbols), "db": db, "today": today})
        return {} if ret is None else ret
    monkeypatch.setattr(SR, "si_map", fake)
    return calls


def counting_hs(monkeypatch):
    """🩳 2026-11-23 (spec highsi §3.3, risk 14): the 🩳 sub's ONE evaluation per GG5 build makes ONE more short-interest
    read through high_si.si_blocks (the strip count) — counted apart, so the table branch keeps its ONE read pin."""
    calls = []

    def fake(symbols, *, today):
        calls.append({"symbols": list(symbols), "today": today})
        return {}
    monkeypatch.setattr(HS, "si_blocks", fake)
    return calls


def core(t):
    return [(r["symbol"], r["setup"], r["tier"], r["rank"], r["near_rank"], r["in_watch"]) for r in t["rows"]]


def by_sym(t):
    return {r["symbol"]: r for r in t["rows"]}


def all_syms():
    return sorted({s for s, _su, _t in T1_ORDER})


# ── S1 heads ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_S1_si_head_is_last_right_after_float_with_its_served_hover():
    keys = [k for k, _ in TBL.HEADS]
    assert keys[-1] == "si" and keys[-2] == "float"
    assert dict(TBL.HEADS)["si"] == "Short interest"
    t = table(store(t1_docs()))
    assert t["heads"][-1] == {"key": "si", "label": "Short interest"}
    assert t["si_head_title"] == TBL.SI_HEAD_TITLE
    src = Path(TBL.__file__).read_text(encoding="utf-8")
    m = re.search(r"^HEADS = \(([\s\S]*?)\)\n([A-Z]\w*)", src, re.M)              # the contracts regex precondition
    assert m and m.group(2) == "TITLE"
    assert '("si", "Short interest")' in m.group(1)


# ── S2 a fresh record — the ONE engine ────────────────────────────────────────────────────────────────────────────
def test_S2_a_fresh_record_is_the_house_chip_verbatim(monkeypatch):
    with_db(monkeypatch)
    doc = si_doc("A1")
    with_docs(monkeypatch, {"A1": doc})
    t = table(store(t1_docs()))
    r = by_sym(t)["A1"]
    house = SR.si_block(dict(doc), TODAY)
    # 2026-11-18 sitier: si_text carries the served tier word (30.0% of float, 24.0% of shares out — confirmed).
    assert r["si_text"] == house["chip"] == "🩳 SI EXTREME 30.0% float · 2.3d · 9/30"
    assert r["si_stale"] is False and r["si_asof"] == "2026-09-30"
    assert r["si_title"] == house["title"] and r["si_title"].startswith("🩳 Short interest — FINRA settlement 2026-09-30")
    assert t["si_fault_text"] is None


# ── S3 NEGATIVE no record ────────────────────────────────────────────────────────────────────────────────────────
def test_S3_NEGATIVE_no_record_and_a_remembered_miss_print_nothing(monkeypatch):
    with_db(monkeypatch)
    with_docs(monkeypatch, {"A1": si_doc("A1"), "K1": miss_doc("K1")})
    t = table(store(t1_docs()))
    by = by_sym(t)
    assert by["A1"]["si_text"]                                                     # the check can pass
    for sym in ("K1", "V1"):                                                        # a remembered miss / absent
        r = by[sym]
        assert all(r[k] is None for k in TBL.SI_KEYS), sym
        assert "0" not in str(r["si_text"] or "") and r["si_text"] != "—"
        assert "not read" not in json.dumps(r, ensure_ascii=False)
    assert t["si_fault_text"] is None                                               # nothing on file ≠ a fault


def test_S3_si_cell_blank_for_every_chipless_block():
    blank = {k: None for k in TBL.SI_KEYS}
    for blk in (None, {}, "x", {"chip": None}, {"chip": ""}, {"chip": 3}, SR.si_block(miss_doc("Z"), TODAY)):
        assert TBL.si_cell(blk) == blank, blk
    got = TBL.si_cell({"chip": "🩳 SI 1.0M sh · 9/30", "title": 7, "stale": "true", "settlement_date": "2026-09-30"})
    assert got == {"si_text": "🩳 SI 1.0M sh · 9/30", "si_title": None, "si_stale": None, "si_asof": "2026-09-30"}


# ── S4 stale ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_S4_a_stale_record_says_stale(monkeypatch):
    with_db(monkeypatch)
    doc = si_doc("A1", settled="2026-08-14")
    with_docs(monkeypatch, {"A1": doc})
    r = by_sym(table(store(t1_docs())))["A1"]
    assert r["si_stale"] is True and r["si_text"].endswith("stale")
    assert r["si_text"] == SR.si_block(dict(doc), TODAY)["chip"] and r["si_asof"] == "2026-08-14"


# ── S5 the float-suspect rule and the third basis — inside the house chip ─────────────────────────────────────────
@pytest.mark.parametrize("kw,head", [
    (dict(fl=6_000_000, so=5_000_000), "24.0% shs out"),                          # FLOAT_EXCEEDS_SHARES
    (dict(si=3_000_000, fl=2_000_000, so=10_000_000), "30.0% shs out"),           # S5b SHORT_EXCEEDS_FLOAT
], ids=["float_exceeds_shares", "short_exceeds_float"])
def test_S5_a_suspect_float_never_heads_the_cell(monkeypatch, kw, head):
    with_db(monkeypatch)
    doc = si_doc("A1", **kw)
    with_docs(monkeypatch, {"A1": doc})
    r = by_sym(table(store(t1_docs())))["A1"]
    house = SR.si_block(dict(doc), TODAY)
    assert house["float_suspect"] in (SR.FLOAT_EXCEEDS_SHARES, SR.SHORT_EXCEEDS_FLOAT)
    assert "float" not in r["si_text"] and "shs out" in r["si_text"] and head in r["si_text"]
    assert r["si_text"] == house["chip"]


def test_S5c_the_third_basis_shares_short_count(monkeypatch):
    with_db(monkeypatch)
    doc = si_doc("A1", fl=None, so=None)
    with_docs(monkeypatch, {"A1": doc})
    r = by_sym(table(store(t1_docs())))["A1"]
    assert " sh ·" in r["si_text"] and "%" not in r["si_text"]
    assert r["si_text"] == SR.si_block(dict(doc), TODAY)["chip"]


# ── S6 ONE bulk read per build ───────────────────────────────────────────────────────────────────────────────────
def test_S6_one_bulk_read_per_table_build_and_none_elsewhere(monkeypatch):
    # 🩳 2026-11-23 (spec highsi, OWNER'S CALL — reverses "no other sub reads"): every GG5 build now also makes the 🩳
    # strip count's ONE read (high_si.si_blocks, counted in `hs`). The table branch keeps exactly ONE; nothing else joins.
    with_db(monkeypatch)
    hs = counting_hs(monkeypatch)
    calls = counting_map(monkeypatch)
    t = table(store(t1_docs()))
    assert len(calls) == 1 and len(hs) == 1                                         # table ONE + the 🩳 strip ONE
    assert hs[0]["today"] == TODAY
    c = calls[0]
    assert c["today"] == TODAY and c["db"] is STUB_DB
    assert c["symbols"] == sorted({r["symbol"].upper() for r in t["rows"]})
    assert len(c["symbols"]) <= SR.MAP_MAX_SYMBOLS and GC.TILE_LIMIT_MAX <= SR.MAP_MAX_SYMBOLS
    calls.clear()
    hs.clear()
    assert board(store(t1_docs()), variant=V.GG1)["table"]["rows"]
    assert len(calls) == 1 and hs == []                                             # the 1-minute table: one; no 🩳
    calls.clear()
    board(store(t1_docs()), BF)
    board(store(t1_docs()), GC.POTENTIAL_SUB)
    assert calls == []                                                              # NEGATIVE: no other sub's table reads
    assert len(hs) == 2                                                             # the 🩳 strip: ONE per GG5 build
    hs.clear()
    board(store(t1_docs()), variant=V.GGA)
    assert calls == [] and hs == []                                                 # NEGATIVE: 🧪 never


def test_S6_unsplit_a_gg5_table_build_makes_exactly_two_reads_and_a_card_sub_one(monkeypatch):
    # 🩳 2026-11-23: the real total through SR.si_map, no high_si stub — table ONE + 🩳 strip ONE; a card sub ONE.
    with_db(monkeypatch)
    calls = counting_map(monkeypatch)
    table(store(t1_docs()))
    assert len(calls) == 2
    calls.clear()
    board(store(t1_docs()), BF)
    assert len(calls) == 1
    calls.clear()
    board(store(t1_docs()), variant=V.GG1)
    board(store(t1_docs()), variant=V.GGA)
    assert len(calls) == 1                                                          # NEGATIVE: 1-minute table only


@pytest.mark.parametrize("now,want", [
    (datetime(2026, 10, 14, 3, 30), date(2026, 10, 13)),                          # naive = UTC → 23:30 ET 10-13
    (datetime(2026, 10, 14, 3, 30, tzinfo=timezone.utc), date(2026, 10, 13)),     # the same instant, aware
    (datetime(2026, 10, 14, 4, 30, tzinfo=timezone.utc), date(2026, 10, 14)),     # 00:30 ET 10-14
], ids=["naive_utc", "aware_same_instant", "after_et_midnight"])
def test_S6b_NEGATIVE_today_is_the_et_date_of_the_build_clock(monkeypatch, now, want):
    with_db(monkeypatch)
    hs = counting_hs(monkeypatch)                                                   # 🩳 2026-11-23 — counted apart
    calls = counting_map(monkeypatch)
    t = board(store(t1_docs()), now=now)["table"]
    assert t["rows"] and len(calls) == 1 and len(hs) == 1
    assert calls[0]["today"] == want and hs[0]["today"] == want


# ── S7 faults ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_S7_NEGATIVE_a_raising_read_keeps_every_row(monkeypatch):
    base = table(store(t1_docs()))
    with_db(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("mongo blip")
    monkeypatch.setattr(SR, "si_map", boom)
    t = table(store(t1_docs()))
    assert rows_of(t) == rows_of(base) and core(t) == core(base) and len(t["rows"]) == len(T1_ORDER)
    assert all(r[k] is None for r in t["rows"] for k in TBL.SI_KEYS)
    assert t["si_fault_text"] == TBL.SI_FAULT_TEXT
    assert t["fault_text"] is None and t["faults_n"] == 0                           # no row counted as a fault


def test_S7b_NEGATIVE_no_handle_is_the_fault_and_never_reads(monkeypatch):
    monkeypatch.setattr(SIC, "_db", None)
    assert SIC._get_db() is None                                                    # the un-stubbed hermetic state
    calls = counting_map(monkeypatch)                                               # the REAL high_si.si_blocks: no
    # 🩳 2026-11-23 handle → it returns None before si_map too, so `calls` stays [] for BOTH readers here.
    t = table(store(t1_docs()))
    assert calls == []
    assert all(r[k] is None for r in t["rows"] for k in TBL.SI_KEYS)
    assert t["si_fault_text"] == TBL.SI_FAULT_TEXT
    with_db(monkeypatch)
    counting_hs(monkeypatch)                                                        # 🩳 2026-11-23 — counted apart
    ok = table(store(t1_docs()))
    assert len(calls) == 1 and ok["si_fault_text"] is None                          # the check can pass
    assert core(t) == core(ok) and rows_of(t) == rows_of(ok)


def test_S7c_NEGATIVE_reachable_but_empty_is_not_a_fault(monkeypatch):
    with_db(monkeypatch)
    counting_hs(monkeypatch)                                                        # 🩳 2026-11-23 — counted apart
    seen = with_docs(monkeypatch, {})
    t = table(store(t1_docs()))
    assert len(seen) == 1 and seen[0][1] is STUB_DB                                 # the handle passed through, ONE read
    assert all(r[k] is None for r in t["rows"] for k in TBL.SI_KEYS)
    assert t["si_fault_text"] is None


def test_S7_block_reader_contract_none_vs_dict():
    tiles = [fake_tile("A1"), fake_tile("B1")]
    reads = {s: {"symbol": s, "setups": {BF: {"setup": BF, "state": "forming"}}} for s in ("A1", "B1")}

    def run(si_read):
        return TBL.block({BF: tiles}, [], reads_by=reads, flags=frozenset(), sess={"label": "today"}, in_window=True,
                         now=NOW, v=None, scan_row=lambda s: {}, cad_min=5, si_read=si_read)
    assert run(lambda syms: None)["si_fault_text"] == TBL.SI_FAULT_TEXT
    assert run(lambda syms: {})["si_fault_text"] is None
    assert run(lambda syms: [1, 2])["si_fault_text"] is None                        # a non-dict answer = read, nothing
    no = run(None)
    assert no["si_fault_text"] is None and all(r[k] is None for r in no["rows"] for k in TBL.SI_KEYS)
    called = []
    empty = TBL.block({}, [], reads_by={}, flags=frozenset(), sess={"label": "today"}, in_window=True, now=NOW,
                      v=None, scan_row=lambda s: {}, cad_min=5, si_read=lambda s: called.append(s))
    assert called == [] and empty["si_fault_text"] is None                          # NEGATIVE: no rows → no read


# ── S8 rank invariance ───────────────────────────────────────────────────────────────────────────────────────────
def test_S8_si_never_moves_a_rank(monkeypatch):
    with_db(monkeypatch)
    with_docs(monkeypatch, {})
    none = table(store(t1_docs()))
    docs = {s: si_doc(s, si=(i + 1) * 900_000, settled="2026-08-14" if i % 2 else "2026-09-30")
            for i, s in enumerate(all_syms())}
    with_docs(monkeypatch, docs)
    full = table(store(t1_docs()))
    assert all(r["si_text"] for r in full["rows"])                                  # the check can fail
    assert core(full) == core(none)
    assert full["sorts"] == none["sorts"] and full["watch"] == none["watch"]
    rng = random.Random(7)
    perm = list(range(len(none["rows"])))
    rng.shuffle(perm)                                                               # the same input order on both sides
    plain = [dict(none["rows"][i]) for i in perm]
    wild = [dict(r, si_text="".join(rng.choice("0123456789%· ") for _ in range(12)),
                 si_stale=rng.choice([True, False]), si_asof="1999-01-01") for r in plain]
    assert [(r["symbol"], r["setup"]) for r in TBL.near_order(wild)] == \
        [(r["symbol"], r["setup"]) for r in TBL.near_order(plain)]


# ── S9 🧪 Audited ────────────────────────────────────────────────────────────────────────────────────────────────
def test_S9_NEGATIVE_audited_has_no_table_and_never_reads(monkeypatch):
    db_calls = with_db(monkeypatch)
    calls = counting_map(monkeypatch)
    out = board(store(t1_docs()), variant=V.GGA)
    assert "table" not in out and calls == [] and db_calls == []


# ── S10 source guard ─────────────────────────────────────────────────────────────────────────────────────────────
SI_WORDS = ("short_interest", "si_map", "si_block", "si_text", "si_read", "pct_of_float", "days_to_cover")


def _src(rel):
    return (BACKEND / rel).read_text(encoding="utf-8")


def test_S10_no_rule_gate_or_alert_reads_short_interest():
    gj = BACKEND / "chart_maps" / "gajjala"
    # 🩳 2026-11-23 (spec highsi §3.2 / §3.5, OWNER'S CALL — the tier is now a list and push input): high_si.py (the
    # 🩳 sub's ONE read) and high_si_cross.py (the 🩳 cross push, reads only via high_si.si_blocks) join the allowlist;
    # pinned by test_S10_high_si_modules_read_short_interest_only_through_the_one_reader. Nothing else may join.
    # WIDENED 2026-11-24 (SPEC sissr §3.3, WP be-pass — Ajay "Days past little bit like AKAN is what I am mainly looking
    # for many were so confident on SSR.."): si_ssr_names.py (the ⛔🔒🩳 name source) imports short_interest.ssr +
    # short_interest.reg_sho and reads the 🩳 block only via high_si.si_blocks; pinned by
    # test_S10_si_ssr_names_reads_short_interest_only_through_ssr_reg_sho_and_high_si. Nothing else may join.
    others = [p for p in sorted(gj.glob("*.py"))
              if p.name not in ("all_table.py", "tab.py", "context.py", "high_si.py", "high_si_cross.py",
                                "si_ssr_names.py")]
    others += [BACKEND / "trading" / n for n in ("gajjala_entry.py", "gajjala_stream.py", "gajjala_untraded.py")]
    others += [BACKEND / "push" / "hooks.py"]
    assert len(others) > 10
    for p in others:
        s = p.read_text(encoding="utf-8")
        if p.name == "run.py":
            s = _run_py_minus_ssr_import(s)
        assert not [w for w in SI_WORDS if w in s], p.name
    ctx = _src("chart_maps/gajjala/context.py")
    assert "_float_suspect" in ctx                                                  # its float chain import stays
    assert not [w for w in ("si_map", "si_block", "si_text", "si_read", "pct_of_float") if w in ctx]


# ⛔ 2026-11-24 (Ajay "ship ssr too" + "SSR is informational"): run.py wires the SSR read's pass step — it RECORDS the
# Rule 201 restriction for the ⛔ tag (display only; never a rule, gate or alert). Exactly ONE line may name the
# package: the fenced import inside _cron_deps. A second mention anywhere still trips S10.
SSR_IMPORT_LINE = "        from short_interest import ssr as SSR"


def _run_py_minus_ssr_import(src: str) -> str:
    lines = src.split("\n")
    assert lines.count(SSR_IMPORT_LINE) == 1, "run.py must import the SSR engine exactly once"
    i = lines.index(SSR_IMPORT_LINE)
    assert lines[i - 1].strip().startswith("try:"), "the SSR import must sit inside its own try"
    fn = max(k for k in range(i) if lines[k].startswith("def "))
    assert lines[fn].startswith("def _cron_deps("), "the SSR import must live inside _cron_deps"
    return "\n".join(lines[:i] + lines[i + 1:])


def test_S10_NEGATIVE_a_second_short_interest_mention_in_run_py_still_trips():
    src = _src("chart_maps/gajjala/run.py")
    assert not [w for w in SI_WORDS if w in _run_py_minus_ssr_import(src)]
    planted = src + "\nfrom short_interest import read as SR\n"
    assert [w for w in SI_WORDS if w in _run_py_minus_ssr_import(planted)]
    with pytest.raises(AssertionError):
        _run_py_minus_ssr_import(src.replace(SSR_IMPORT_LINE, SSR_IMPORT_LINE + "\n" + SSR_IMPORT_LINE))


def test_S10_high_si_modules_read_short_interest_only_through_the_one_reader():
    # 🩳 2026-11-23: high_si.py calls SR.si_map ONCE, inside si_blocks; high_si_cross.py never imports short_interest.read
    # and never calls si_map — it reads through HS.si_blocks only (its reg_sho read is pinned in test_reg_sho_*).
    hs = _src("chart_maps/gajjala/high_si.py")
    assert hs.count("SR.si_map(") == 1
    body = inspect.getsource(HS.si_blocks)
    assert "SR.si_map(" in body and "SR.SIC._get_db()" in body
    tree = ast.parse(hs)
    sr_calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "SR"}
    assert "si_map" in sr_calls and not sr_calls & {"si_block", "si_text", "refresh", "warm"}
    hx = _src("chart_maps/gajjala/high_si_cross.py")
    assert "si_map" not in hx and "short_interest import read" not in hx and "short_interest.read" not in hx
    assert hx.count("HS.si_blocks(") == 1
    tree = ast.parse(hx)
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not [m for m in mods if m.startswith("short_interest") and m != "short_interest"]
    froms = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "short_interest"
             for a in n.names}
    assert froms == {"reg_sho"}


def test_S10_si_ssr_names_reads_short_interest_only_through_ssr_reg_sho_and_high_si():
    # ⛔🔒🩳 2026-11-24 (SPEC sissr §3.3): the only short_interest modules si_ssr_names.py imports are ssr and reg_sho
    # (lazy, inside functions); it never imports short_interest.read / client and never calls si_map — the 🩳 block
    # comes through HS.si_blocks only.
    src = _src("chart_maps/gajjala/si_ssr_names.py")
    tree = ast.parse(src)
    froms = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "short_interest"
             for a in n.names}
    assert froms == {"ssr", "reg_sho"}
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not [m for m in mods if m.startswith("short_interest.")]
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not [n for n in top if "short_interest" in ast.dump(n)]                  # lazy only
    for banned in ("si_map", "short_interest import read", "short_interest.read", "short_interest import client",
                   "SIC."):
        assert banned not in src, banned
    assert not re.search(r"(?<![\w.])SR\.", src)                                     # HS.SR.* / SSR.* only
    assert src.count("HS.si_blocks(") == 1


def test_S10_NEGATIVE_a_direct_si_map_call_in_si_ssr_names_would_trip():
    src = _src("chart_maps/gajjala/si_ssr_names.py")
    planted = src + "\nfrom short_interest import read as SR\nSR.si_map([])\n"
    tree = ast.parse(planted)
    froms = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "short_interest"
             for a in n.names}
    assert froms != {"ssr", "reg_sho"} and "si_map" in planted
    assert re.search(r"(?<![\w.])SR\.", planted) and not re.search(r"(?<![\w.])SR\.", "SSR.x HS.SR.y")


def test_S10_tab_reads_short_interest_only_in_the_table_branch():
    s = _src("chart_maps/gajjala/tab.py")
    i = s.index("elif table_sub:")
    j = s.index("elif ", i + len("elif table_sub:"))
    inside, outside = s[i:j], s[:i] + s[j:]
    for needle in ("si_read=", "SR.si_map(", "SR.SIC._get_db()", "_et(now).date()"):
        assert inside.count(needle) == 1, needle
    assert not [w for w in ("short_interest", "si_map", "si_read", "_get_db") if w in outside]
    assert "si_read=" in "x si_read=y" and "elif table_sub:" in s                   # the matcher can fail


def test_S10_all_table_order_keys_never_read_si_and_import_no_short_interest():
    assert "si_" not in inspect.getsource(TBL.near_order)
    assert "si_" not in inspect.getsource(TBL.tier_of)
    tree = ast.parse(Path(TBL.__file__).read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
        elif isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
    assert mods and not [m for m in mods if m.startswith("short_interest")]


# ── S11 the 1-minute page ────────────────────────────────────────────────────────────────────────────────────────
def test_S11_the_1_minute_table_carries_the_column(monkeypatch):
    with_db(monkeypatch)
    with_docs(monkeypatch, {"A1": si_doc("A1")})
    t1 = board(store(t1_docs()), variant=V.GG1)["table"]
    t5 = table(store(t1_docs()))
    assert t1["heads"] == t5["heads"] and t1["heads"][-1]["key"] == "si"
    assert all(set(TBL.SI_KEYS) <= set(r) for r in t1["rows"])
    # 2026-11-18 sitier: the served tier word leads the chip
    assert by_sym(t1)["A1"]["si_text"] == by_sym(t5)["A1"]["si_text"] == "🩳 SI EXTREME 30.0% float · 2.3d · 9/30"


# ── S12 NaN / private keys ───────────────────────────────────────────────────────────────────────────────────────
def test_S12_no_nan_and_no_private_key_with_si_docs(monkeypatch):
    with_db(monkeypatch)
    with_docs(monkeypatch, {s: si_doc(s, dtc=float("nan")) for s in all_syms()})
    t = table(store(t1_docs()))
    json.dumps(t, allow_nan=False)
    assert not [p for p, k in _walk_keys(t) if k.startswith("_")]
    assert all(r["si_text"] for r in t["rows"])


# ── S13 the routes ───────────────────────────────────────────────────────────────────────────────────────────────
def test_S13_the_gg5_route_serves_the_column(monkeypatch):
    with_db(monkeypatch)
    with_docs(monkeypatch, {"A1": si_doc("A1")})
    body = _get(monkeypatch, store(t1_docs()))
    t = body["table"]
    assert t["heads"][-1] == {"key": "si", "label": "Short interest"} and t["si_fault_text"] is None
    by = by_sym(t)
    # 2026-11-18 sitier: the served tier word leads the chip
    assert by["A1"]["si_text"] == "🩳 SI EXTREME 30.0% float · 2.3d · 9/30"
    assert by["K1"]["si_text"] is None                                              # NEGATIVE: no record → null


def test_S13_the_1_minute_route_serves_the_column(monkeypatch):
    from chart_maps import api as API
    from chart_maps import board as board_mod
    from chart_maps.gajjala import store as ST
    from tests.test_gajjala_tab import run_route
    st = store(t1_docs())
    monkeypatch.setattr(ST, "for_variant", lambda v=None: st)
    monkeypatch.setattr(GT, "_clock", lambda: NOW)
    monkeypatch.setattr(board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: None)
    with_db(monkeypatch)
    with_docs(monkeypatch, {"A1": si_doc("A1")})
    body = json.loads(run_route(API.chart_maps_gajjala_1m(sub=GC.TABLE_SUB, tf="", focus="", sort="",
                                                          limit=GC.TILE_LIMIT_DEFAULT, span="", email=None)).body)
    t = body["table"]
    assert t["heads"][-1]["key"] == "si" and t["si_fault_text"] is None
    # 2026-11-18 sitier: the served tier word leads the chip
    assert by_sym(t)["A1"]["si_text"] == "🩳 SI EXTREME 30.0% float · 2.3d · 9/30"
    assert by_sym(t)["K1"]["si_text"] is None


# ── S14 the case join ────────────────────────────────────────────────────────────────────────────────────────────
def _lower_block(si_by):
    seen = []
    tiles = [fake_tile("gga")]
    reads = {"GGA": {"symbol": "GGA", "setups": {BF: {"setup": BF, "state": "forming"}}}}

    def si_read(syms):
        seen.append(list(syms))
        return si_by
    t = TBL.block({BF: tiles}, [], reads_by=reads, flags=frozenset(), sess={"label": "today"}, in_window=True,
                  now=NOW, v=None, scan_row=lambda s: {}, cad_min=5, si_read=si_read)
    return t, seen


def test_S14_a_lower_case_tile_symbol_joins_the_upper_case_map():
    blk = SR.si_block(si_doc("GGA"), TODAY)
    t, seen = _lower_block({"GGA": blk})
    assert seen == [["GGA"]]
    r = t["rows"][0]
    assert r["symbol"] == "gga" and r["si_text"] == blk["chip"]


def test_S14_NEGATIVE_a_lower_case_map_key_is_never_matched():
    blk = SR.si_block(si_doc("GGA"), TODAY)
    t, _seen = _lower_block({"gga": blk})
    assert all(t["rows"][0][k] is None for k in TBL.SI_KEYS)
    rows = [{"symbol": "Aa1"}, "junk", {"symbol": None}]
    TBL.attach_si(rows, {"AA1": blk})
    assert rows[0]["si_text"] == blk["chip"] and rows[1] == "junk" and rows[2]["si_text"] is None
    TBL.attach_si(None, None)                                                       # never raises


# ── S15 the golden carries no live chip ──────────────────────────────────────────────────────────────────────────
def test_S15_the_board_golden_carries_no_short_interest_text():
    text = GOLDEN.read_text(encoding="utf-8")
    doc = json.loads(text)
    for mode in ("live", "shadow"):
        t = doc[mode]["all_strategies"]["table"]
        assert t["rows"]
        assert all(r[k] is None for r in t["rows"] for k in TBL.SI_KEYS), mode
        assert t["si_fault_text"] == TBL.SI_FAULT_TEXT, mode
    assert "🩳 SI " not in text


# ── 2026-11-18 sitier: the tier words arrive through si_text — no new served key ─────────────────────────────────
def test_NEGATIVE_sitier_adds_no_served_key_to_the_table():
    # the gg5 BOARD golden carries exactly these four si_* leaves; a fifth (e.g. si_tier) would move it.
    assert TBL.SI_KEYS == ("si_text", "si_title", "si_stale", "si_asof")
    assert not any("tier" in k or "float_check" in k for k in TBL.SI_KEYS)
