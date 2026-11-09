"""🧪 Gajjala · Audited — 🚩's own A+ rows on the 🧪 🏁, each with the audit's call (SPEC gg-track-parity WP-A, 2026-11-05).

Ajay 2026-11-05, verbatim: "Can you make both Gajjala's track record and Gajjalas 1 min and Gajjalas AUDIT HAVE similar
track record. It looks like our Gajjals 5 min had better win yesterday and today... I would like you to audit but its
hard to tell which ones won in Gajjlas Audit page" — trigger: "Why are the other winners not having charts?"

Covers audited_tab.read_span / track_block / row_audits / _audit_cell / _exit_line / EXIT_STATE_TEXT / NOT_READ_CELL,
the `ok` verdict [C6], the tab's ONE read [C1], the GGA route's no-today-read [C2], the session union [C5], ids-only
held cells [C7]. NEGATIVES are marked: fail-visible faults (a)–(e), no audit key on GG5 / GG1, no provisional cell,
no pending word for a decided exit state, the duplicate still listed + celled but never counted, no b-word / "edge".
UNMEASURED — the rows measure nothing; the ✅ / ❌ are 🚩's grade of the original (the ONE ledger).
"""
from __future__ import annotations

import inspect
import json
import re
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import audited_tab as AT
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_audited_tab import (B1040, B1115, NOW_C, SETUP, VCP, _aud, _claim, _exit_doc, _grade, _held,
                                            _mk, _world, base_world, stores, strings, walk)
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
S4 = date(2026, 11, 4)                         # tab.session_for(NOW_C)
D2 = date(2026, 11, 2)
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
KISS = GC.SETUPS[1]
NEW_WORDS = ("ledger_audit_head", "row_audit_passed", "row_audit_passed_none_on", "row_audit_held",
             "row_audit_not_judged", "row_audit_not_judged_sub", "row_audit_not_read", "row_exit_t3", "row_exit_t5",
             "row_exit_pending", "row_exit_no_plan", "row_exit_no_risk", "row_exit_split")


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def ok_aud(failed=(), **kw):
    """A claim audit as audited_rules._finish stores it: `aplus` = not failed (the ONE stored verdict)."""
    a = _aud(failed, **kw)
    a["aplus"] = not failed
    return a


def gga_tr(st, span="5d"):
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st, span=span)
    return b, b["track_record"]


def rows_of(tr, key="days"):
    blk = tr if key == "days" else tr["aplus"]
    return [r for d in blk.get("days") or [] for r in d["rows"]]


def by_sym(tr, setup=SETUP):
    return {r["symbol"]: r for r in rows_of(tr) if r["setup"] == setup}


def mixed_world(exits=()):
    return _world(_mk("PAS", outcome="win", claim=(B1040, ok_aud())),
                  _mk("HLD", outcome="loss", marker=(B1040, _aud(("G1", "G4"), t1=False))),
                  _mk("NON", outcome="no_entry"),
                  _mk("OFF", outcome="win", claim=(B1115, ok_aud())),
                  exits=exits)


# ── the rows: 🚩's own, byte-equal cells ──────────────────────────────────────────────────────────────────────────
def test_the_rows_are_the_originals_with_flag_and_cells_byte_equal_to_flag_tabs_own():
    st = mixed_world()
    _b, tr = gga_tr(st)
    read = AT.read_span(st, S4, NOW_C, span="5d", is_today=True)
    assert [r["id"] for r in rows_of(tr)] and {r["id"] for r in rows_of(tr)} == {
        o["id"] for o in read["sides"]["original"]}
    g5 = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st.shared, span="5d")["track_record"]
    mine = {r["id"]: r for r in rows_of(g5)}
    for r in rows_of(tr):
        o = mine[r["id"]]
        for k in ("same", "next", "flag_text", "bucket", "bucket_text", "dup_of", "dup_text", "symbol", "setup"):
            assert r[k] == o[k], (r["id"], k)
        assert "tab=gajjala_audited" in r["href"] and r["href"] == o["href"].replace("tab=gajjala&",
                                                                                     "tab=gajjala_audited&")
    flags = {r["symbol"]: r["flag_text"] for r in rows_of(tr)}
    assert flags["PAS"] == LG.BUCKET_TEXT["win"] and flags["HLD"] == LG.BUCKET_TEXT["loss"]
    # the trigger's answer [C8]: the winners are rows now, so the 🎯 charts have counts to draw
    assert tr["aplus"]["charts"] and tr["aplus"]["total"] == len(rows_of(tr))


def test_the_aplus_rows_are_the_same_dicts_and_carry_the_cell():
    st = mixed_world()
    tr = AT.track_block(st, S4, NOW_C, span="5d", is_today=True, read=AT.read_span(st, S4, NOW_C, span="5d"))
    days = {id(r) for r in rows_of(tr)}
    ap = rows_of(tr, "aplus")
    assert ap and all(id(r) in days and "audit" in r for r in ap)                # set in place — never a copy
    _b, served = gga_tr(st)                                                     # the served (plain) copy keeps it
    assert [r["audit"] for r in rows_of(served, "aplus")] == [r["audit"] for r in ap]


def test_heads_put_the_audit_column_right_after_the_ticker():
    _b, tr = gga_tr(mixed_world())
    h = tr["heads"]
    assert h[0]["key"] == LG.HEADS[0][0] == "symbol"
    assert h[1] == {"key": AT.AUDIT_HEAD_KEY, "label": V.word("ledger_audit_head", V.GGA)} == {"key": "audit",
                                                                                                 "label": "🧪 Audit"}
    assert h[2:] == [{"key": k, "label": lab} for k, lab in LG.HEADS[1:]]


# ── the cells ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_cells_held_passed_not_judged_and_a_record_on_another_bar():
    st = mixed_world()
    b, tr = gga_tr(st)
    rows = by_sym(tr)
    held = rows["HLD"]["audit"]
    assert held == {"state": "held", "text": "🧪 held by G1, G4", "sub_text": None, "provisional": False}
    assert held["text"] == V.word("row_audit_held", V.GGA, ids="G1, G4")
    # NEGATIVE [C7]: no why sentence in the cell — the compare's held list keeps the row
    hrow = next(r for r in b["audited_compare"]["held"]["rows"] if r["symbol"] == "HLD")
    assert hrow["held_by"] == ["G1", "G4"]
    assert rows["PAS"]["audit"] == {"state": "passed", "text": V.word("row_audit_passed", V.GGA), "sub_text": None,
                                    "provisional": False}                       # no exits doc → no sub-line
    nj = {"state": "not_judged", "text": V.word("row_audit_not_judged", V.GGA),
          "sub_text": V.word("row_audit_not_judged_sub", V.GGA), "provisional": False}
    assert rows["NON"]["audit"] == nj                                           # no record at all
    assert rows["OFF"]["audit"] == nj                                           # NEGATIVE: a pass on ANOTHER bar
    assert {r["audit"]["state"] for r in rows_of(tr)} <= set(AT.AUDIT_STATES)


def test_c6_the_stored_aplus_is_the_verdict():
    none_on = ok_aud()
    none_on.update(passed=[], rules=[])                                         # judged with every rule OFF
    no_verdict = dict(_aud(), aplus=False)                                      # no failed id, not a pass
    st = _world(_mk("ZRO", outcome="win", claim=(B1040, none_on)),
                _mk("NOV", outcome="win", claim=(B1040, no_verdict)),
                _mk("OLD", outcome="win", claim=(B1040, None)))                 # written before the audit key
    _b, tr = gga_tr(st)
    rows = by_sym(tr)
    assert rows["ZRO"]["audit"]["state"] == "passed"
    assert rows["ZRO"]["audit"]["sub_text"] == V.word("row_audit_passed_none_on", V.GGA)
    assert rows["NOV"]["audit"]["state"] == "not_judged"                        # NEGATIVE: never a pass by default
    assert rows["OLD"]["audit"]["state"] == "not_judged"
    assert AT._verdicts(none_on)["ok"] is True and AT._verdicts(no_verdict)["ok"] is False
    assert AT._verdicts({"failed": []})["ok"] is False                          # NEGATIVE: no `aplus` → not ok
    assert AT._rec_verdicts("m", {"held_by": [], "passed_by": ["G1"]})["ok"] is False   # a marker never passed


# ── the exit sub-line [C4] ────────────────────────────────────────────────────────────────────────────────────────
def test_a_passed_vcp_row_carries_the_t3_and_t5_exit_words_built_from_the_constants():
    k2, k3 = (AUD.exit_col_key("T3", m) for m in AUD.T3_R_MULTS)
    exits = [_exit_doc("VCP", VCP, {k2: {"entry": "filled", "outcome": "win", "r": 2.0},
                                    AUD.exit_col_key("T5"): {"entry": "filled", "outcome": "loss", "r": -1.0}}),
             _exit_doc("BFL", SETUP, {AUD.exit_col_key("T5"): {"entry": "filled", "outcome": "win", "r": 0.5}})]
    st = _world(_mk("VCP", setup=VCP, claim=(B1040, ok_aud()), gga_outcome="win"),
                _mk("BFL", claim=(B1040, ok_aud()), gga_outcome="win"), exits=exits)
    _b, tr = gga_tr(st)
    vcp = by_sym(tr, VCP)["VCP"]["audit"]
    assert vcp["state"] == "passed"
    assert vcp["sub_text"] == "T3 +2R: ✅ winner +2.0R · T3 +3R: not graded yet · T5 21 EMA trail: ❌ loser -1.0R"
    labels = [b.split(": ")[0] for b in vcp["sub_text"].split(" · ")]
    assert labels == [f"T3 +{m:g}R" for m in AUD.T3_R_MULTS] + [f"T5 {AUD.T5_EMA} EMA trail"]
    assert labels == ([V.word("row_exit_t3", V.GGA, k=m) for m in AUD.T3_R_MULTS]
                      + [V.word("row_exit_t5", V.GGA, ema=AUD.T5_EMA)])
    bfl = by_sym(tr)["BFL"]["audit"]
    assert bfl["sub_text"] == f"{V.word('row_exit_t5', V.GGA, ema=AUD.T5_EMA)}: {LG.BUCKET_TEXT['win']} +0.5R"
    assert "T3" not in bfl["sub_text"]                                          # NEGATIVE: T3 reads VCP only


def test_c4_every_cell_state_has_an_exit_word_equal_to_the_ledgers_own():
    assert set(AT.EXIT_STATE_TEXT) == set(LG.CELL_STATES)
    row = {"date": "2026-11-03", "at_utc": NOW_C, "plan": LG.PLANS[0]}
    t5 = V.word("row_exit_t5", V.GGA, ema=AUD.T5_EMA)
    pending = AT.EXIT_STATE_TEXT["pending"]
    cases = [{"entry": s} for s in ("no_plan", "no_risk", "no_time")] + [{"reason": "split", "entry": "filled"}]
    for g in cases:
        line = AT._exit_line("X", SETUP, {"X": {AUD.exit_col_key("T5"): g}})
        want = LG._cell(row, "same", g, False, NOW_C, S4, False)["text"]
        assert line == f"{t5}: {want}", g
        assert pending not in line, g                                           # NEGATIVE: never the pending word
    assert AT._exit_line("X", SETUP, {}) is None                                # no exits doc → no line at all
    assert AT._exit_line("X", SETUP, {"X": {}}) == f"{t5}: {pending}"           # a doc with no column → pending


# ── 🔁 duplicates: listed, celled, never counted; per_rule unmoved by the refactor ────────────────────────────────────
def dedupe_world():
    return _world(_mk("AAA", outcome="win", claim=(B1040, ok_aud())),
                  _mk("DUP", outcome="win", claim=(B1040, ok_aud())),
                  _mk("DUP", setup=KISS, outcome="loss", marker=(B1040, _aud(("G1", "G4"), t1=False))),
                  _mk("BBB", outcome="loss", marker=(B1040, _aud(("G4",), t1=False))),
                  _mk("GGG", outcome="win", claim=(B1115, dict(_aud(("G2",)), aplus=False))))


# (with n, with n_dup, other n, other n_dup, with no_original, other no_original, not_judged) — copied from the
# PRE-refactor audited_tab (HEAD aac85a67) on dedupe_world(); the extraction of _record_of must not move a count
PER_RULE_BEFORE = {"G1": (3, 0, 0, 0, 1, 0, 1), "G2": (3, 0, 0, 0, 0, 1, 1), "G4": (2, 0, 1, 0, 1, 0, 1),
                   "T1": (2, 0, 0, 0, 1, 0, 2), "T2": (3, 0, 0, 0, 1, 0, 1), "A1": (3, 0, 0, 0, 1, 0, 1),
                   "H1": (3, 0, 0, 0, 1, 0, 1), "T4": (3, 0, 0, 0, 1, 0, 1), "A2": (3, 0, 0, 0, 1, 0, 1),
                   "T3_2R": (0, 0, 0, 0, 0, 0, 0), "T3_3R": (0, 0, 0, 0, 0, 0, 0), "T5": (3, 0, 3, 0, 0, 0, 0),
                   "K3S": (0, 0, 0, 0, 0, 0, 0)}


def test_a_duplicate_keeps_its_chip_and_its_cell_and_the_counts_equal_flag_tabs():
    st = dedupe_world()
    b, tr = gga_tr(st)
    dup = by_sym(tr, KISS)["DUP"]
    assert dup["dup_of"] == LG.ledger_id("2026-11-03", "DUP", SETUP, LG.KINDS[1]) and dup["dup_text"]
    assert dup["audit"]["state"] == "held" and dup["audit"]["text"] == "🧪 held by G1, G4"
    g5 = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st.shared, span="5d")["track_record"]
    assert tr["entries_text"] == g5["entries_text"] and tr["shadow_text"] == g5["shadow_text"]
    assert tr["aplus"]["n_dup"] == g5["aplus"]["n_dup"] == 1
    assert tr["aplus"]["counts"] == g5["aplus"]["counts"]
    pr = {r["key"]: (r["with"]["n"], r["with"]["n_dup"], r["other"]["n"], r["other"]["n_dup"],
                     r["with"][AT.NO_ORIGINAL], r["other"][AT.NO_ORIGINAL], r["not_judged"])
          for r in b["audited_compare"]["per_rule"]}
    assert pr == PER_RULE_BEFORE
    # NEGATIVE: _attribute still skips the duplicate original (only 4 counted pairs) and still takes its record
    read = AT.read_span(st, S4, NOW_C, span="5d", is_today=True)
    pairs, loose = AT._attribute(read["sides"])
    assert [o["symbol"] + "/" + o["setup"] for o, _v in pairs] == [
        o["symbol"] + "/" + o["setup"] for o in read["sides"]["original"] if not o.get("dup_of")]
    assert len(loose) == 1 and loose[0]["failed"] == ["G2"]                    # GGG's off-bar claim, once


def test_record_of_is_the_attribute_rule():
    m = {"id": "x", "entry_bar_t": B1040}
    c = {"id": "x", "entry_bar_t": B1115}
    assert AT._record_of({"id": "x", "entry_bar_t": B1040}, {"x": m}, {"x": c}) == ("m", m)
    assert AT._record_of({"id": "x", "entry_bar_t": B1115}, {"x": m}, {"x": c}) == ("c", c)
    assert AT._record_of({"id": "x", "entry_bar_t": "2026-11-03 12:00"}, {"x": m}, {"x": c}) is None   # NEGATIVE
    assert AT._record_of({"id": "x"}, {"x": m}, {"x": c}) == ("m", m)           # no bar: the marker, then the claim
    assert AT._record_of({"id": "x"}, {}, {"x": c}) == ("c", c)
    assert AT._record_of({"id": "x"}, {}, {}) is None


# ── [C1] the ONE read, fail-visible ───────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def reads(monkeypatch):
    calls = []
    real = AT.read_span

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)
    monkeypatch.setattr(AT, "read_span", counting)
    return calls


def _not_read(b):
    tr = b["track_record"]
    assert tr is not None and b["empty_note"] is None
    rows = rows_of(tr)
    assert rows and all(r["audit"] == AT.NOT_READ_CELL for r in rows)
    assert all(r["audit"] is not AT.NOT_READ_CELL for r in rows)               # a copy per row, never the constant
    assert AT.NOT_READ_CELL["text"] == V.word("row_audit_not_read", V.GGA)


def test_fault_a_a_raising_side_read_lists_the_rows_with_not_read_cells(monkeypatch, reads):
    def boom(*_a, **_k):
        raise ValueError("a malformed stored grade")
    monkeypatch.setattr(AT, "_read_sides", boom)
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=mixed_world(), span="5d")
    _not_read(b)
    assert b["audited_compare"] is None and len(reads) == 1                    # (e) read once, never re-run


def test_fault_b_a_failed_gga_claims_read_is_the_same(reads):
    st = mixed_world()
    st._injected[ST.ALERTS] = FakeColl(fail=True)
    with pytest.raises(LG.LedgerReadError):
        AT.read_span(st, S4, NOW_C, span="5d")
    reads.clear()
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st, span="5d")
    _not_read(b)
    assert b["audited_compare"] is None and len(reads) == 1                    # (e)


def test_fault_c_raising_row_audits_keep_the_rows_and_the_compare(monkeypatch, reads):
    def boom(*_a, **_k):
        raise KeyError("x")
    monkeypatch.setattr(AT, "row_audits", boom)
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=mixed_world(), span="5d")
    _not_read(b)
    assert b["audited_compare"] is not None and b["audited_compare"]["sides"][0]["n"] == 4   # its read succeeded
    assert len(reads) == 1


def test_fault_d_the_shared_ledger_failing_is_the_track_record_fault():
    st = mixed_world()
    st.shared._injected[ST.LEDGER] = FakeColl(fail=True)
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st, span="5d")
    assert b["track_record"] is None and b["empty_note"] == GT.TRACK_RECORD_FAULT
    assert b["audited_compare"] is None


def test_fault_e_the_happy_path_reads_once_and_hands_the_read_to_both(monkeypatch, reads):
    seen = []
    real_cb, real_tb = AT.compare_block, AT.track_block

    def cb(*a, **k):
        seen.append(("compare", k.get("read")))
        return real_cb(*a, **k)

    def tb(*a, **k):
        seen.append(("track", k.get("read")))
        return real_tb(*a, **k)
    monkeypatch.setattr(AT, "compare_block", cb)
    monkeypatch.setattr(AT, "track_block", tb)
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=mixed_world(), span="5d")
    assert len(reads) == 1 and b["audited_compare"] is not None
    assert [w for w, _r in seen] == ["track", "compare"] and seen[0][1] is seen[1][1] is not None
    assert {r["audit"]["state"] for r in rows_of(b["track_record"])} == {"passed", "held", "not_judged"}


def test_track_block_never_reads_the_audit(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("track_block read the audit")
    monkeypatch.setattr(AT, "read_span", boom)
    monkeypatch.setattr(AT, "_read_sides", boom)
    tr = AT.track_block(mixed_world(), S4, NOW_C, span="5d", is_today=True, read=None)
    assert rows_of(tr) and all(r["audit"]["state"] == "not_read" for r in rows_of(tr))


# ── [C5] sessions: the shared store's ∪ the GGA store's own ───────────────────────────────────────────────────────────
def test_c5_an_overlay_silent_flag_session_lists_and_counts_original_only_on_all():
    st = base_world(extra_g5=[_claim("SIL", d=D2)], extra_g5l=[_grade("SIL", "win", d=D2)])
    old = LG._clip(LG._sessions_for("all", S4, st, [], V.GGA), V.GGA)
    assert D2 not in old                                                        # the GGA store alone never saw D2
    read = AT.read_span(st, S4, NOW_C, span="all", is_today=True)
    assert D2 in read["sessions"]
    b, tr = gga_tr(st, "all")
    sil = by_sym(tr)["SIL"]
    assert sil["audit"]["state"] == "not_judged" and sil["flag_text"] == LG.BUCKET_TEXT["win"]
    assert b["audited_compare"]["recon"]["original_only"] == 1                 # NEGATIVE: never silently missing
    # GGA-only claim date: still counted audited_only
    st2 = base_world(extra_a=[_claim("ZZZ", variant=V.GGA, d=D2)])
    c2 = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st2, span="all")["audited_compare"]
    assert c2["recon"]["audited_only"] == 1


@pytest.mark.parametrize("span", GC.LEDGER_SPANS)
def test_c5_the_served_sessions_are_inside_the_read_on_every_span(span):
    st = base_world(extra_g5=[_claim("SIL", d=D2), _claim("TDY", d=S4)], extra_g5l=[_grade("SIL", "win", d=D2)],
                    extra_a=[_claim("ZZZ", variant=V.GGA, d=D2)])
    _b, tr = gga_tr(st, span)
    read = AT.read_span(st, S4, NOW_C, span=span, is_today=True)
    served = {d["date"] for d in tr["days"]}
    assert served <= {s.isoformat() for s in read["sessions"]}, span
    assert read["span"] == span


def test_a_flag_aplus_before_the_record_start_never_lists():
    start = date.fromisoformat(GC.GGA_RECORD_FROM)
    before = LG._prev_market_day(start)
    st = base_world(extra_g5=[_claim("OLD", d=before)], extra_g5l=[_grade("OLD", "win", d=before)])
    _b, tr = gga_tr(st, "all")
    assert "OLD" not in {r["symbol"] for r in rows_of(tr)}
    assert all(s >= start for s in AT.read_span(st, S4, NOW_C, span="all")["sessions"])
    g5 = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st.shared, span="all")["track_record"]
    assert "OLD" in {r["symbol"] for r in rows_of(g5)}                         # NEGATIVE: the plant IS a 🚩 row


# ── [C2] today: the ledger's own pending words, no live read ──────────────────────────────────────────────────────────
def test_c2_todays_row_reads_not_read_yet_and_the_tab_never_reads_today(monkeypatch):
    called = []
    monkeypatch.setattr(LG, "today_read", lambda *a, **k: called.append(1))
    st = base_world(extra_g5=[_claim("TDY", d=S4)])
    b, tr = gga_tr(st)
    tdy = by_sym(tr)["TDY"]
    at = GC.LEDGER_GRADE_AT_ET
    assert tdy["same"] == {"state": "pending", "text": "not read yet", "sub_text": f"graded tonight {at} ET",
                           "provisional": False}
    assert tr["today_text"] == f"Today · not read on this open — graded tonight {at} ET"
    assert not [p for p, k, v in walk(tr) if k == "provisional" and v is True]   # NEGATIVE: no provisional cell
    assert called == []                                                         # NEGATIVE: never a today read
    # the pass-through: a future HIS CALL #28 flip is one route line
    rid = tdy["id"]
    g = {"entry": "filled", "outcome": "win", "best_pct": 1.5}
    tr2 = AT.track_block(st, S4, NOW_C, span="5d", is_today=True, today={"grades": {rid: g}}, read=None)
    assert by_sym(tr2)["TDY"]["same"]["provisional"] is True


# ── the dropped keys and the kept ones ────────────────────────────────────────────────────────────────────────────
def test_the_dropped_and_the_kept_keys():
    st = mixed_world()
    _b, tr = gga_tr(st)
    assert tr["counts_text"] is None and tr["kinds"] is None and tr["kind_empty_text"] is None
    raw = LG.served_block(st.shared, S4, NOW_C, span="5d", is_today=True, variant=V.GGA)
    for k in ("categories", "sorts", "views", "spans", "title", "honesty", "entries_text", "rule_text"):
        assert tr[k] == raw[k], k
    assert tr["aplus"]["charts"] == raw["aplus"]["charts"]
    assert raw["counts_text"] is not None and raw["kinds"] is not None         # NEGATIVE: dropped on 🧪 only
    assert tr["title"] == V.word("ledger_title", V.GGA)


def test_the_empty_span_reads_the_new_empty_words():
    st = stores([], [], [], [])
    _b, tr = gga_tr(st)
    assert rows_of(tr) == [] and tr["empty_text"] == V.word("ledger_empty", V.GGA)
    assert tr["empty_text"] == f"No 🚩 A+ on this span (the record starts {GC.GGA_RECORD_FROM})."


# ── NEGATIVE: GG5 / GG1 serve no byte of it ───────────────────────────────────────────────────────────────────────
def _no_audit(tr, where):
    assert tr is not None, where
    assert "audit" not in [h["key"] for h in tr["heads"]], where
    assert not [r for r in rows_of(tr) + rows_of(tr, "aplus") if "audit" in r], where
    assert tr["counts_text"] is not None and tr["kinds"] is not None, where


def test_NEGATIVE_gg5_and_gg1_track_records_carry_no_audit_key():
    st = mixed_world()
    _no_audit(GT.build(GC.LEDGER_SUB, now=NOW_C, store=st.shared, span="5d")["track_record"], "GG5")
    g1 = ST.GajjalaStore(colls={n: FakeColl(st.shared._injected[ST.ALERTS].docs.values()
                                            if n == ST.ALERTS else None) for n in ST.OWN},
                         variant=V.GG1, shared=st.shared)
    _no_audit(GT.build(GC.LEDGER_SUB, now=NOW_C, store=g1, variant=V.GG1, span="5d")["track_record"], "GG1")
    assert "audit" not in inspect.getsource(LG.served_block)                   # the shared engine is untouched
    assert "audited_compare" not in GT.build(GC.LEDGER_SUB, now=NOW_C, store=st.shared, span="5d")


# ── C13 · words ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_c13_json_native_no_decimal_no_b_word_and_no_edge_in_the_new_words():
    k2 = AUD.exit_col_key("T3", AUD.T3_R_MULTS[0])
    st = _world(_mk("VCP", setup=VCP, claim=(B1040, ok_aud()), gga_outcome="win"),
                _mk("HLD", outcome="loss", marker=(B1040, _aud(("G1",), t1=False))),
                exits=[_exit_doc("VCP", VCP, {k2: {"entry": "filled", "outcome": "win", "r": Decimal("2.0")}})])
    b, tr = gga_tr(st)
    json.dumps(GT._plain(b), allow_nan=False)
    assert not [p for p, _k, v in walk(b) if isinstance(v, Decimal)]
    assert not [s for s in strings(b) if B_WORD.search(s)]
    for k in NEW_WORDS + ("ledger_title", "ledger_honesty", "ledger_empty"):
        w = V.word(k, V.GGA, ids="G1, A1", k=AUD.T3_R_MULTS[0], ema=AUD.T5_EMA)
        assert w and not EDGE.search(w) and not B_WORD.search(w) and "{" not in w, k
    cells = [r["audit"] for r in rows_of(tr)]
    assert not [s for s in strings(cells) if EDGE.search(s)]


def test_the_new_words_exactly():
    g = V.GGA
    assert V.word("ledger_title", g) == ("🏁 Track record — every 🚩 A+ since 2026-11-01, each with the audit's call, "
                                         "graded by GG's trade math · UNMEASURED")
    assert V.word("ledger_honesty", g).endswith(V.DUP_RULE_TEXT)
    assert "held list below" in V.word("ledger_honesty", g) and "graded tonight" in V.word("ledger_honesty", g)
    assert [V.word(k, g) for k in ("ledger_audit_head", "row_audit_passed", "row_audit_passed_none_on",
                                   "row_audit_not_judged", "row_audit_not_judged_sub", "row_audit_not_read",
                                   "row_exit_pending")] == [
        "🧪 Audit", "🧪 passed every rule", "no rule was on when it was judged", "🧪 not judged",
        "no audit record on this bar", "🧪 audit not read this time — the next re-read tries again", "not graded yet"]
    assert V.word("row_audit_held", g, ids="G1, A1") == "🧪 held by G1, A1"
    assert V.word("row_exit_t3", g, k=AUD.T3_R_MULTS[0]) == f"T3 +{AUD.T3_R_MULTS[0]:g}R"
    assert V.word("row_exit_t5", g, ema=AUD.T5_EMA) == f"T5 {AUD.T5_EMA} EMA trail"
    # NEGATIVE: GG5 / GG1 have none of them (no GG1 word moves — the 1-minute golden stays)
    for k in NEW_WORDS:
        assert V.word(k, V.GG5) is None and k not in V.WORDS_1M, k
