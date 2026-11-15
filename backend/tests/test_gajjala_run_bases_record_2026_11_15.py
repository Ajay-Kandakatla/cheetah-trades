"""📶 GG's base count — the RECORD side (WP-B be-record, spec 2026-11-15 rev 2 §3.3 / §4).

Ajay, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need that
tracked in to Gajjala's". GG verified rule E6 (single source). INFORMATION ONLY — no push, lane, gate, filter or sort.

Pinned here: the 🏁 ledger row carries the claim doc's `run_base_n` / `run_base_forming` stamp ONLY when well-formed
(never on a ⏪ replay); the served 🏁 row's `base_text` chip (BASE_TEXT / BASE_FORMING_TEXT, the key only when n ≥ 1 or
forming); `store.run_bases_of` (ONE projected find); the nightly "bases" snapshot (`run_bases|YYYY-MM-DD`). The claim
docs and read docs here are HAND-BUILT to the §3.3 key contract (the producer side is WP-A's).
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone

import pytest

from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_track_record_tab import (D16, _et, _rows, board, ledger_store, live_entry_doc, pot_doc,
                                                  shadow_doc)

S = date(2026, 10, 13)
NOW = datetime(2026, 10, 14, 0, 15, tzinfo=timezone.utc)      # 20:15 EDT


@pytest.fixture(autouse=True)
def _clean():
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    yield
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()


def _claim(n=2, forming=False, **kw):
    doc = live_entry_doc(D16, "PMI", "kiss_fly", _et(D16, 10, 56), trigger=2.40, stop=2.20, price=2.35)
    doc.update(run_base_n=n, run_base_forming=forming)
    doc.update(kw)
    return doc


def _plain():
    return live_entry_doc(D16, "PMI", "kiss_fly", _et(D16, 10, 56), trigger=2.40, stop=2.20, price=2.35)


# ── 1. the served words ─────────────────────────────────────────────────────────────────────────────────────────
def test_the_chip_words_are_frozen():
    assert LG.BASE_TEXT == "📶 base {n}"
    assert LG.BASE_FORMING_TEXT == "📶 base {n} forming"


@pytest.mark.parametrize("n,forming,text", [(1, False, "📶 base 1"), (2, False, "📶 base 2"),
                                            (3, False, "📶 base 3"), (4, False, "📶 base 4"),
                                            (5, False, "📶 base 5"), (0, True, "📶 base 1 forming"),
                                            (2, True, "📶 base 3 forming")])
def test_base_text_of_both_texts(n, forming, text):
    assert LG.base_text_of({"run_base_n": n, "run_base_forming": forming}) == text


def test_NEGATIVE_n_zero_and_not_forming_is_no_chip():
    assert LG.base_text_of({"run_base_n": 0, "run_base_forming": False}) is None
    assert LG.base_text_of({}) is None and LG.base_text_of(None) is None


# ── 2. alert_of: the stamp, keys only when well-formed ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("n,forming", [(0, False), (2, False), (2, True), (7, True)])
def test_alert_of_carries_the_stamp_on_live_and_shadow_claims(n, forming):
    live = LG.alert_of(_claim(n, forming), "aplus")
    assert live["line"] == "live" and (live["run_base_n"], live["run_base_forming"]) == (n, forming)
    sh = dict(shadow_doc(D16, "TGL", "kiss_fly", _et(D16, 10, 46), trigger=5.60, stop=5.30, price=5.50),
              run_base_n=n, run_base_forming=forming)
    r = LG.alert_of(sh, "aplus")
    assert r["line"] == "shadow" and (r["run_base_n"], r["run_base_forming"]) == (n, forming)


def test_alert_of_refusal_record_is_never_a_row_even_stamped():
    doc = _claim(2, False, _id=_plain()["_id"] + "#closed", state="closed")
    assert LG.alert_of(doc, "aplus") is None


@pytest.mark.parametrize("n,forming", [
    (True, False), (False, False), (True, True),          # a bool n is never an int count
    ("2", False), (2.0, False), (None, False), (-1, False), (-1, True),
    (2, None), (2, 1), (2, 0), (2, "yes"), (2, "True"),
])
def test_NEGATIVE_a_malformed_stamp_adds_no_key_and_the_row_is_byte_identical(n, forming):
    plain = LG.alert_of(_plain(), "aplus")
    bad = LG.alert_of(_claim(n, forming), "aplus")
    assert not {"run_base_n", "run_base_forming"} & set(bad)
    assert bad == plain


def test_NEGATIVE_one_key_alone_adds_nothing():
    plain = LG.alert_of(_plain(), "aplus")
    only_n = dict(_plain(), run_base_n=2)
    only_f = dict(_plain(), run_base_forming=True)
    assert LG.alert_of(only_n, "aplus") == plain and LG.alert_of(only_f, "aplus") == plain


def test_NEGATIVE_a_claim_without_the_keys_is_the_row_of_before():
    r = LG.alert_of(_plain(), "aplus")
    assert not {"run_base_n", "run_base_forming", "base_text"} & set(r)


def test_NEGATIVE_a_replay_doc_carrying_the_keys_is_never_read():
    from tests.test_gajjala_ledger_replay import replay_doc
    plain = LG.alert_of(replay_doc(), "aplus")
    doc = dict(replay_doc(), run_base_n=3, run_base_forming=False)
    doc["alert"] = dict(doc["alert"], run_base_n=3, run_base_forming=True)
    row = LG.alert_of(doc, "aplus")
    assert row is not None and row["line"] == LG.LINES[2]
    assert not {"run_base_n", "run_base_forming"} & set(row) and row == plain
    assert LG.base_text_of(row) is None


def test_the_stamp_reads_through_every_variant():
    d = date(2026, 11, 13)
    for v in (V.GG1, V.GGA):
        from chart_maps.gajjala import alerts as AL
        doc = {"_id": AL.claim_key(d, "AAA", "bull_flag", v), "date": d.isoformat(), "symbol": "AAA",
               "setup": "bull_flag", "state": "pushed", "trigger": 2.0, "stop": 1.8,
               "at": datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc).isoformat(),
               "run_base_n": 3, "run_base_forming": False}
        r = LG.alert_of(doc, "aplus", variant=v)
        assert r is not None and (r["run_base_n"], r["run_base_forming"]) == (3, False), v
        plain = LG.alert_of({k: x for k, x in doc.items() if not k.startswith("run_base")}, "aplus", variant=v)
        assert not {"run_base_n", "run_base_forming"} & set(plain)


def test_the_stamp_never_reaches_the_stored_alert_block():
    """The nightly grade stores `_alert_block(row)` — a closed key list: the stamp never enters gajjala_ledger."""
    blk = LG._alert_block(LG.alert_of(_claim(3, True), "aplus"))
    assert blk == LG._alert_block(LG.alert_of(_plain(), "aplus"))
    assert not {"run_base_n", "run_base_forming", "base_text"} & set(blk)


def test_a_potential_row_reads_a_stamp_only_when_its_doc_carries_one():
    plain = pot_doc(D16, "ZZZ", "bull_flag", _et(D16, 10, 12), trigger=2.2, stop=2.0, px=2.1)
    assert not {"run_base_n", "run_base_forming"} & set(LG.alert_of(plain, "potential"))


# ── 3. the served 🏁 row ────────────────────────────────────────────────────────────────────────────────────────
def _tr(extra_doc):
    st = ledger_store()
    if extra_doc is not None:
        st.coll(ST.ALERTS).docs[extra_doc["_id"]] = extra_doc
    return board(st, "today")["track_record"]


def test_the_served_row_carries_base_text_after_a_broke_base():
    r = _rows(_tr(_claim(2, False)))["2026-10-16|PMI|kiss_fly|aplus"]
    assert r["base_text"] == "📶 base 2"


def test_the_served_row_carries_the_forming_text():
    r = _rows(_tr(_claim(2, True)))["2026-10-16|PMI|kiss_fly|aplus"]
    assert r["base_text"] == "📶 base 3 forming"


def test_a_stamped_shadow_row_is_chipped_too():
    st = ledger_store()
    sid = [k for k, d in st.coll(ST.ALERTS).docs.items() if d.get("symbol") == "TGL"][0]
    st.coll(ST.ALERTS).docs[sid].update(run_base_n=1, run_base_forming=False)
    rows = _rows(board(st, "today")["track_record"])
    assert rows["2026-10-16|TGL|kiss_fly|aplus"]["base_text"] == "📶 base 1"
    assert "base_text" not in rows["2026-10-16|PMI|bull_flag|aplus"]          # NEGATIVE: an unstamped neighbour


def test_NEGATIVE_n_zero_not_forming_serves_no_key():
    r = _rows(_tr(_claim(0, False)))["2026-10-16|PMI|kiss_fly|aplus"]
    assert "base_text" not in r


@pytest.mark.parametrize("n,forming", [(True, False), ("2", True), (None, True), (-1, True), (2, None)])
def test_NEGATIVE_a_malformed_stamp_serves_no_chip(n, forming):
    r = _rows(_tr(_claim(n, forming)))["2026-10-16|PMI|kiss_fly|aplus"]
    assert "base_text" not in r


def test_NEGATIVE_the_stamp_moves_nothing_but_the_one_chip():
    """The whole served block with a stamped claim, minus its `base_text`, is byte-identical to the unstamped one —
    no count, %, bucket, order or other key moves (INFORMATION ONLY)."""
    plain = _tr(_plain())
    stamped = _tr(_claim(3, False))
    seen = []

    def strip(o):                       # the row is served on the days list AND the 🎯 A+ view — both carry the chip
        if isinstance(o, dict):
            if "base_text" in o:
                seen.append(o.pop("base_text"))
            for x in o.values():
                strip(x)
        elif isinstance(o, list):
            for x in o:
                strip(x)
    strip(stamped)
    assert seen and set(seen) == {"📶 base 3"}
    assert json.dumps(stamped, sort_keys=True, default=str) == json.dumps(plain, sort_keys=True, default=str)
    assert "base_text" not in json.dumps(plain)


# ── 4. store.run_bases_of ───────────────────────────────────────────────────────────────────────────────────────
class _Rec(FakeColl):
    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail)
        self.calls: list = []

    def find(self, q=None, projection=None):
        self.calls.append((copy.deepcopy(q), copy.deepcopy(projection)))
        return super().find(q, projection)


def _blk(n=2, forming=False, state="broke", as_of="2026-10-13 15:55", runs=None):
    if runs is None:
        runs = [{"from_t": "2026-10-13 09:40", "high_t": "2026-10-13 10:30", "state": state, "n": n,
                 "bases": [{"n": k + 1, "from_t": "2026-10-13 09:50", "to_t": "2026-10-13 10:00", "bars": 3,
                            "lo": 1.0, "hi": 1.2, "state": "broke", "broke_t": "2026-10-13 10:05",
                            "quiet": True, "shallow": False,
                            "leg": {"s_t": "2026-10-13 09:40", "e_t": "2026-10-13 09:45", "bars": 2}}
                           for k in range(n)]}]
    return {"version": 1, "frame": "5m", "from": "rth", "until": "rth", "restart": True, "depth_floor": False,
            "as_of_bar_t": as_of, "runs": runs, "n": n, "forming": forming, "state": state}


def test_run_bases_of_is_one_projected_find_and_never_loads_the_tile():
    rec = _Rec()
    st = fake_store(**{ST.READS: rec})
    st.upsert_read(S, "AAA", {"setups": {}, "tile": {"bars": [1, 2, 3]}, "run_bases": _blk()})
    rec.calls.clear()
    out = st.run_bases_of(S)
    assert len(rec.calls) == 1
    q, proj = rec.calls[0]
    assert q == {"date": S.isoformat()} and proj == {"symbol": 1, "run_bases": 1}
    assert "tile" not in proj and len(out) == 1 and out[0]["symbol"] == "AAA"


def test_NEGATIVE_run_bases_of_on_a_read_fault_is_empty_never_raises():
    st = fake_store(**{ST.READS: FakeColl(fail=True)})
    assert st.run_bases_of(S) == []
    assert ST.GajjalaStore(colls={ST.READS: None}).run_bases_of(S) == []


# ── 5. the nightly "bases" snapshot ─────────────────────────────────────────────────────────────────────────────
def test_the_bases_step_sits_before_grade_and_grade_stays_last():
    assert NG.STEPS[-1] == "grade" and NG.STEPS.index("bases") == NG.STEPS.index("grade") - 1
    assert NG.RUN_BASES_STATE_FMT == "run_bases|{date}"


def _bases_store():
    st = fake_store()
    st.upsert_read(S, "ZZZ", {"setups": {}, "run_bases": _blk(1, True, "forming", "2026-10-13 15:50")})
    st.upsert_read(S, "AAA", {"setups": {}, "run_bases": _blk(3, False, "broke")})
    st.upsert_read(S, "MMM", {"setups": {}, "run_bases": _blk(0, False, None, runs=[])})
    st.upsert_read(S, "NOB", {"setups": {}})                                  # no block → skipped
    st.upsert_read(S, "JNK", {"setups": {}, "run_bases": "junk"})             # not a dict → skipped
    st.upsert_read(date(2026, 10, 12), "OLD", {"setups": {}, "run_bases": _blk()})   # another session
    return st


def test_snapshot_shape_order_and_as_of_bar_t():
    st = _bases_store()
    out = NG.snapshot_bases(st, S, NOW)
    assert out == {"names": 3, "with_bases": 2}
    doc = st.get_state("run_bases|2026-10-13")
    assert doc["date"] == "2026-10-13" and doc["frame"] == "5m" and doc["version"] == 1
    assert doc["n_names"] == 3 and doc["at"] == NOW.isoformat()
    assert [r["symbol"] for r in doc["rows"]] == ["AAA", "MMM", "ZZZ"]
    for r in doc["rows"]:
        assert set(r) == {"symbol", "as_of_bar_t", "n", "forming", "state", "runs"}
        assert r["as_of_bar_t"]
    rows = {r["symbol"]: r for r in doc["rows"]}
    assert (rows["AAA"]["n"], rows["AAA"]["forming"], rows["AAA"]["state"]) == (3, False, "broke")
    assert (rows["ZZZ"]["n"], rows["ZZZ"]["forming"], rows["ZZZ"]["as_of_bar_t"]) == (1, True, "2026-10-13 15:50")
    assert rows["AAA"]["runs"] == _blk(3)["runs"]                       # every base stored, as counted
    assert rows["MMM"]["runs"] == [] and rows["MMM"]["state"] is None   # a counted 0 is recorded too
    assert "OLD" not in rows and "NOB" not in rows and "JNK" not in rows


def test_snapshot_is_idempotent():
    st = _bases_store()
    a = NG.snapshot_bases(st, S, NOW)
    doc1 = copy.deepcopy(st.get_state("run_bases|2026-10-13"))
    b = NG.snapshot_bases(st, S, NOW)
    assert a == b and st.get_state("run_bases|2026-10-13") == doc1
    assert len([k for k in st.coll(ST.STATE).docs if str(k).startswith("run_bases|")]) == 1


def test_NEGATIVE_no_read_docs_writes_nothing():
    st = fake_store()
    assert NG.snapshot_bases(st, S, NOW) == {"names": 0, "with_bases": 0}
    assert st.get_state("run_bases|2026-10-13") == {} and st.coll(ST.STATE).writes == 0


def test_NEGATIVE_read_docs_without_a_block_write_nothing():
    st = fake_store()
    st.upsert_read(S, "NOB", {"setups": {}})
    assert NG.snapshot_bases(st, S, NOW) == {"names": 0, "with_bases": 0}
    assert st.coll(ST.STATE).writes == 0


def test_NEGATIVE_a_read_fault_writes_nothing():
    st = fake_store(**{ST.READS: FakeColl(fail=True)})
    assert NG.snapshot_bases(st, S, NOW) == {"names": 0, "with_bases": 0}
    assert st.coll(ST.STATE).writes == 0


def _run(st, monkeypatch, **kw):
    from tests.test_gajjala_nightly import _run as nrun
    graded = []
    monkeypatch.setattr(LG, "grade_step", lambda store, now, **k: graded.append(now) or {"graded": True})
    return nrun(st, **kw), graded


def test_run_writes_the_snapshot_in_the_bases_step(monkeypatch):
    st = _bases_store()
    out, graded = _run(st, monkeypatch, steps=("bases", "grade"))
    assert out["bases"] == {"names": 3, "with_bases": 2} and out["errors"] == []
    assert out["grade"] == {"graded": True} and graded
    assert [r["symbol"] for r in st.get_state("run_bases|2026-10-13")["rows"]] == ["AAA", "MMM", "ZZZ"]


def test_NEGATIVE_a_raising_bases_step_is_named_and_grade_still_runs(monkeypatch):
    st = _bases_store()

    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(NG, "snapshot_bases", boom)
    out, graded = _run(st, monkeypatch, steps=("bases", "grade"))
    assert out["errors"] == ["bases: RuntimeError"] and "bases" not in out
    assert out["grade"] == {"graded": True} and graded


def test_NEGATIVE_steps_without_bases_never_write_the_snapshot(monkeypatch):
    st = _bases_store()
    out, _ = _run(st, monkeypatch, steps=("grade",))
    assert "bases" not in out and st.get_state("run_bases|2026-10-13") == {}


def test_main_accepts_the_bases_step(monkeypatch):
    seen = {}
    st = fake_store()
    monkeypatch.setattr("chart_maps.gajjala.store.default", lambda: st)
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: {"grade": {}})
    monkeypatch.setattr(NG, "grade_audited", lambda now, **k: {"grade": {}})

    def fake_run(session, *, store=None, steps=NG.STEPS):
        seen.setdefault("steps", []).append(steps)
        return {"errors": []}
    monkeypatch.setattr(NG, "run", fake_run)
    assert NG.main(["--steps", "bases"]) == 0 and seen["steps"][-1] == ("bases",)
    assert NG.main([]) == 0 and "bases" in seen["steps"][-1] and seen["steps"][-1][-1] == "grade"


def test_source_guards_no_gate_word_and_no_live_provider_in_the_step():
    import inspect
    src = inspect.getsource(NG.snapshot_bases)
    for bad in ("send", "push", "alert_gate", "requests", "massive", "yahoo", "b" + "ounce"):
        assert bad not in src.lower(), bad
    assert "b" + "ounce" not in (LG.BASE_TEXT + LG.BASE_FORMING_TEXT).lower()
