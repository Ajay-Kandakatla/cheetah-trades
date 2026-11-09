"""🧪 Gajjala · Audited — the K3S ADMIT rule: the detector flag, the registry entry, the pure predicates, judge(admit=)
(SPEC gg-k3s REV 2 §3.1 / §3.2, WP-A gg-k3s-rules, 2026-11-09).

Ajay 2026-11-09: "yes change the audit as per you like that is yours I need you to make it successful and earn money
that is the goal".

K3S admits a 🚩 "broke — not A+" 🎾 Reversal Squeeze read whose ONLY miss is K3 (base volume ≤ K3_VOL_FRAC × the
squeeze-back run) ON ITS BREAK BAR (`bars_since_entry == 0`) as a 🧪 A+ with 🚩's own plan. The re-read is the ONE
detector with `k3_binding=False`; K11 is re-applied by the caller (a partial read never carries the K11 row — C1).
Frozen before any code in eod-audits/research/2026-11-09_gajjala_audited_k3s_prereg.md (byte copy
tests/fixtures/gajjala/audited_k3s_prereg_2026_11_09.md, sha256 PREREG3_SHA256). UNMEASURED. NEGATIVE cases are named
NEGATIVE.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import inspect
import json
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import store as ST
from tests.fixtures.gajjala import detector_frames as FX

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
FIX = BACKEND / "tests" / "fixtures" / "gajjala" / "audited_k3s_prereg_2026_11_09.md"
HOST_ROOT = Path("/Users/ajay/clinet-test")
HOST_LEDGER = HOST_ROOT / AUD.LEDGER_PATH
DOC = REPO / "docs" / "gajjala" / "audited_k3s_2026_11_09.md"
SRC = Path(AUD.__file__).read_text(encoding="utf-8")
DSRC = Path(D.__file__).read_text(encoding="utf-8")
EDGE = re.compile(r"\bedge\b", re.I)
B_WORD = re.compile("b" + "ounc", re.I)
HIS_WORDS = ("yes change the audit as per you like that is yours I need you to make it successful and earn money that "
             "is the goal")
JUDGE_IDS = ["G1", "G2", "G4", "T2", "A1", "H1", "T4", "A2"]
CTX = {"session": FX.TODAY, "best_change_pct": 55.0, "best_symbol": "RUNR"}
FR = FX.float_read(5_000_000)
LOUD = FX.rs_replace(r11=(6.1875, 6.21875, 6.125, 6.15625, 0.51 * FX.RS_BARS[10][4]))   # test_gajjala_detectors :847
CALM = FX.rs_replace(r3=(5.875, 5.875, 5.75, 5.8125, 100_000), r4=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                     r5=(5.8125, 5.84375, 5.75, 5.8125, 100_000), r6=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                     r7=(5.8125, 5.84375, 5.75, 5.8125, 100_000))                          # test_gajjala_detectors :825
CALM_LOUD = FX.rs_replace(CALM, r11=LOUD[11])                                              # K8 failed AND K3 missed
AFTER = (6.4375, 6.5, 6.375, 6.4375, 300_000)                                              # one bar after the break, above the stop


def _rs(F, **kw):
    return D.reversal_squeeze(F, float_read=FR, **kw)


def _in_window(bars, entry=FX.RS_E):
    """The 🎾 frame with its break bar at 11:00 ET (start 10:55 — inside T2 / A1 / H1) so judge can pass."""
    return FX.frame(list(bars) + [entry], prior=FX.warm(5.0), start="09:55")


def _row(read, key):
    return next((c for c in read.get("criteria") or [] if c.get("key") == key), None)


# ── the detector flag (§3.1) ─────────────────────────────────────────────────────────────────────────────────────
def test_k3_not_binding_reads_the_loud_base_aplus_with_the_same_plan():
    F = FX.rs_frame(LOUD)
    base, re_ = _rs(F), _rs(F, k3_binding=False)
    assert base["state"] == "partial" and base["missed"] == ["k3_vol"] and base["reason"] == D.NOT_APLUS_REASON
    assert re_["state"] == "aplus"
    assert _row(re_, D.K3_VOL_KEY)["ok"] is False and "k3_vol" in re_["missed"]          # the K3 row stays ✗
    assert re_["bars_since_entry"] == 0 == base["bars_since_entry"]
    for k in ("trigger", "stop", "risk_pct", "entry_bar_t", "leg", "base", "structure", "red_closes"):
        assert re_[k] == base[k], k
    assert (re_["trigger"], re_["stop"]) == (6.25, 6.09375)


def test_NEGATIVE_the_default_read_is_byte_equal_with_and_without_the_flag():
    for bars in (LOUD, CALM, CALM_LOUD, FX.RS_BARS):
        for after in (None, [AFTER]):
            F = FX.rs_frame(bars, after=after)
            a, b = _rs(F), _rs(F, k3_binding=True)
            assert a == b and json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    sig = inspect.signature(D.reversal_squeeze).parameters
    assert sig["k3_binding"].default is True and sig["k3_binding"].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(D._resolve_break).parameters["exempt"].default == ()
    assert "k3_binding: bool = True" in DSRC


def test_NEGATIVE_the_flag_never_moves_a_clean_aplus_or_a_forming_read():
    F = FX.rs_frame()
    assert _rs(F) == _rs(F, k3_binding=False) and _rs(F)["state"] == "aplus"
    F = FX.rs_frame(LOUD, entry=None)                                                       # no break yet
    assert _rs(F) == _rs(F, k3_binding=False) and _rs(F)["state"] != "aplus"


def test_the_k3_key_is_the_detectors_own_name():
    assert D.K3_VOL_KEY == "k3_vol" and AUD.K3S_MISSED == (D.K3_VOL_KEY,)
    assert "criterion(K3_VOL_KEY," in DSRC
    assert GC.K3_VOL_FRAC == 0.50 and AUD.K3S.params["frac"] is GC.K3_VOL_FRAC              # untouched, by name


def test_k11_reapplied_on_the_reread_at_the_floor_keeps_it_aplus():
    re_ = _rs(FX.rs_frame(LOUD), k3_binding=False)
    out = D.k11_gate(copy.deepcopy(re_), GC.K11_MIN_SESSION_VOLUME)
    assert out["state"] == "aplus" and _row(out, D.K11_KEY)["ok"] is True
    assert (out["trigger"], out["stop"], out["entry_bar_t"]) == (re_["trigger"], re_["stop"], re_["entry_bar_t"])


def test_NEGATIVE_k11_refuses_the_reread_below_the_floor_or_unknown():
    re_ = _rs(FX.rs_frame(LOUD), k3_binding=False)
    lo = D.k11_gate(copy.deepcopy(re_), GC.K11_MIN_SESSION_VOLUME - 1)
    assert lo["state"] == "partial" and D.K11_KEY in lo["missed"] and lo["reason"] == D.NOT_APLUS_REASON
    unk = D.k11_gate(copy.deepcopy(re_), None)
    assert unk["state"] == "partial" and D.K11_KEY in unk["missed"]
    assert D.K11_UNKNOWN in _row(unk, D.K11_KEY)["label"]
    assert AUD.k3s_candidate(dict(lo, bars_since_entry=0)) is False                       # two misses now


def test_NEGATIVE_the_partial_read_never_carries_the_k11_row():
    """C1: k11_gate leaves a partial read untouched — `missed == ["k3_vol"]` says nothing about K11."""
    base = _rs(FX.rs_frame(LOUD))
    out = D.k11_gate(copy.deepcopy(base), 100)
    assert out == base and _row(out, D.K11_KEY) is None


def test_NEGATIVE_one_bar_after_the_break_is_not_a_candidate_and_the_reread_is_triggered():
    F = FX.rs_frame(LOUD, after=[AFTER])
    base = dict(_rs(F), setup="reversal_squeeze")
    assert base["state"] == "partial" and base["missed"] == ["k3_vol"] and base["bars_since_entry"] == 1
    assert AUD.k3s_candidate(base) is False and AUD.k3s_partial(base) is False
    re_ = _rs(F, k3_binding=False)
    assert re_["state"] == "triggered" and re_["state"] != "aplus"


def test_NEGATIVE_a_second_miss_is_never_a_candidate_but_is_a_partial():
    F = FX.rs_frame(CALM_LOUD)
    base = _rs(F)
    assert base["state"] == "partial" and sorted(base["missed"]) == ["k3_vol", "k8_failed"]
    assert AUD.k3s_candidate(base) is False and AUD.k3s_partial(base) is True              # placebo (a)
    re_ = _rs(F, k3_binding=False)
    assert re_["state"] == "partial" and re_["missed"] == base["missed"]
    calm = _rs(FX.rs_frame(CALM))
    assert calm["missed"] == ["k8_failed"] and AUD.k3s_partial(calm) is True and AUD.k3s_candidate(calm) is False


def test_NEGATIVE_other_setups_are_never_candidates_and_take_no_flag():
    cap = GC.K3_VOL_FRAC * (FX.D1[4] + FX.D2[4]) / 2
    bf = D.bull_flag(FX.frame(FX.bf_bars([FX.P1[:4] + (cap * 1.02,), FX.P2])))
    kf = D.kiss_fly(FX.kf_frame(pull_v=GC.K3_VOL_FRAC * FX.KF_D[4] * 1.02))
    for r in (bf, kf):
        assert r["state"] == "partial" and r["missed"] == ["k3_vol"]
        assert AUD.k3s_candidate(r) is False and AUD.k3s_partial(r) is False
        assert AUD.k3s_candidate(dict(r, bars_since_entry=0)) is False
    for fn in (D.bull_flag, D.kiss_fly, D.horizontal_fade, D.intraday_vcp):
        assert "k3_binding" not in inspect.signature(fn).parameters
    rs = _rs(FX.rs_frame(LOUD))
    assert AUD.k3s_candidate(dict(rs, setup="bull_flag")) is False


# ── the pure predicates (§3.2) ──────────────────────────────────────────────────────────────────────────────────
def test_the_default_loud_read_is_a_candidate_and_a_partial():
    r = _rs(FX.rs_frame(LOUD))
    assert r["setup"] == "reversal_squeeze" and AUD.k3s_partial(r) is True and AUD.k3s_candidate(r) is True
    json.dumps(r)                                                                          # the stored shape


@pytest.mark.parametrize("change", [
    {"state": "aplus"}, {"state": "triggered"}, {"broke": False}, {"broke": None}, {"entry_bar_t": None},
    {"entry_bar_t": ""}, {"bars_since_entry": 1}, {"bars_since_entry": None}, {"bars_since_entry": False},
    {"bars_since_entry": "0"}, {"missed": []}, {"missed": None}, {"missed": "k3_vol"}, {"unjudged": ["k3_vol"]},
    {"variant": "near_kiss"}, {"grade": {"r": 1}}, {"setup": "kiss_fly"}, {"setup": None},
])
def test_NEGATIVE_the_predicates_refuse_any_other_shape(change):
    r = dict(_rs(FX.rs_frame(LOUD)), **change)
    assert AUD.k3s_candidate(r) is False and AUD.k3s_partial(r) is False


def test_NEGATIVE_junk_is_never_a_candidate():
    for junk in (None, "x", 7, [], {}):
        assert AUD.k3s_partial(junk) is False and AUD.k3s_candidate(junk) is False


def test_k3s_partial_row_state_is_invisible_to_the_ledger_and_the_held_reader():
    assert AUD.K3S_PARTIAL_ROW_STATE == "partial_break"
    assert AUD.K3S_PARTIAL_ROW_STATE not in ST.LEDGER_ALERT_STATES                       # NEGATIVE: never a 🏁 row
    assert AUD.K3S_PARTIAL_ROW_STATE != AUD.HELD_ROW_STATE                                # NEGATIVE: never a held row


# ── the registry (§3.2) ─────────────────────────────────────────────────────────────────────────────────────────
def test_k3s_is_the_last_entry_an_on_admit_under_prereg3():
    assert AUD.REGISTRY[-1] is AUD.K3S and AUD.by_id("K3S") is AUD.K3S
    k = AUD.K3S
    assert (k.kind, k.status, k.applies, k.prereg, k.date_added) == (
        AUD.KIND_ADMIT, AUD.STATUS_ON, True, AUD.PREREG3_PATH, "2026-11-09")
    assert k.verdict == AUD.VERDICT_UNMEASURED and k.verdict_source.startswith("LEDGER.md row '🧪 K3S' 2026-11-09: "
                                                                                "UNMEASURED")
    assert k.name == "K3 volume-dry not binding on the 🎾 base"
    assert [r.id for r in AUD.on_rules()] == ["G1", "G2", "G4", "T1", "T2", "A1", "H1", "T4", "A2", "T3", "T5", "K3S"]
    assert AUD.admit_rules() == (AUD.K3S,) and AUD.k3s_on() is True
    assert AUD.KINDS == ("filter", "exit", "admit") and AUD.AUDIT_VERSION == 3
    assert k.params["setups"] == AUD.K3S_SETUPS == ("reversal_squeeze",)


def test_NEGATIVE_k3s_never_enters_the_filter_judge_or_exit_views():
    assert [r.id for r in AUD.filter_rules()] == ["G1", "G2", "G4", "T1", "T2", "A1", "H1", "T4", "A2"]
    assert [r.id for r in AUD.judge_rules()] == JUDGE_IDS
    assert [r.id for r in AUD.exit_rules()] == ["T3", "T5"]


def test_NEGATIVE_k3s_off_is_not_on_and_judge_refuses_its_admit(monkeypatch):
    off = dataclasses.replace(AUD.K3S, status=AUD.STATUS_OFF)
    monkeypatch.setattr(AUD, "REGISTRY", tuple(off if r.id == "K3S" else r for r in AUD.REGISTRY))
    assert AUD.admit_rules() == () and AUD.k3s_on() is False
    F = _in_window(LOUD)
    re_ = _rs(F, k3_binding=False)
    with pytest.raises(ValueError):
        AUD.judge(re_, F, [], ctx=CTX, admit="K3S")
    monkeypatch.undo()
    monkeypatch.setattr(AUD, "K3S", off)                                                    # the module name patched
    assert AUD.k3s_on() is False


def test_registry_row_k3s_carries_the_prereg3_sha_and_words_only():
    row = AUD.registry_rows()[-1]
    assert row["id"] == "K3S" and row["kind"] == "admit" and row["status"] == "on"
    assert "sha256 be966681e317…" in row["source_text"] and AUD.PREREG3_PATH in row["source_text"]
    assert 'GG: "gradual decrease in volume"' in row["source_text"]
    assert "UNMEASURED" in row["verdict_text"] and "{" not in row["rule"]
    assert "≤ 0.5× the squeeze-back run" in row["rule"] and "K11 session volume re-applied" in row["rule"]
    assert row["params_text"] == ("🎾 only · fires when K3 (0.5× the squeeze-back run) is the ONLY miss on the break "
                                  "bar · K11 re-applied · 🚩's plan unchanged")
    for v in row.values():
        if isinstance(v, str):
            assert "None" not in v and not EDGE.search(v) and not B_WORD.search(v), v[:60]   # NEGATIVE
    json.dumps(row)


def test_the_clause_names_k3s_after_the_exit_grades():
    txt = AUD.rules_clause()
    ex = txt.index("Exit grades on its 🏁 beside GG's math:")
    ad = txt.index("Admits on the A+ read — a 🧪 A+ 🚩 never rings, with 🚩's own plan: K3S K3 volume-dry not binding "
                   "on the 🎾 base (")
    assert ex < ad < txt.index("G3 ring age")
    assert not EDGE.search(txt) and not B_WORD.search(txt) and "None" not in txt         # NEGATIVE


# ── the frozen prereg3 ──────────────────────────────────────────────────────────────────────────────────────────
def test_prereg3_fixture_is_the_frozen_bytes_and_the_host_file_equals_it():
    raw = FIX.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == AUD.PREREG3_SHA256 == (
        "be966681e31703f9bba2761d6dd28c0d135108ef93076be000ec8ec516b6ef54")
    host = HOST_ROOT / AUD.PREREG3_PATH
    if host.exists():
        assert host.read_bytes() == raw
    assert hashlib.sha256(raw + b" ").hexdigest() != AUD.PREREG3_SHA256                  # NEGATIVE: one byte moves it
    line = next(ln for ln in SRC.splitlines() if ln.startswith("PREREG3_SHA256 ="))
    assert AUD.PREREG3_SHA256 in line
    assert AUD.PREREG_SHA_BY_PATH[AUD.PREREG3_PATH] == AUD.PREREG3_SHA256


def test_both_k3s_source_quotes_are_single_lines_of_the_prereg():
    lines = FIX.read_text(encoding="utf-8").splitlines()
    assert len(AUD.K3S.source) == 2
    for path, quote in AUD.K3S.source:
        assert path == AUD.PREREG3_PATH and "\n" not in quote
        assert any(quote in ln for ln in lines), quote
    pre = FIX.read_text(encoding="utf-8")
    assert f'"{HIS_WORDS}"' in " ".join(pre.split()) and "Setup: `reversal_squeeze` only." in pre   # his words wrap
    assert "`missed` is exactly" in pre and '`["k3_vol"]`' in pre


def test_the_ledger_has_one_unmeasured_k3s_row():
    """RED until the main session writes the LEDGER.md row (SPEC §4 main-session); skips without the host file."""
    if not HOST_LEDGER.exists():
        pytest.skip("the host LEDGER.md lives outside the repo")
    rows = [ln for ln in HOST_LEDGER.read_text(encoding="utf-8").splitlines()
            if ln.startswith("| 2026-11-09 | none | 🧪 K3S")]
    assert len(rows) == 1
    assert "UNMEASURED" in rows[0] and AUD.PREREG3_SHA256[:12] in rows[0]
    assert "2026-11-09_gajjala_audited_k3s_prereg.md" in rows[0]


# ── judge(admit=) / _finish / with_t1 (§3.2) ────────────────────────────────────────────────────────────────────
def test_judge_admit_k3s_all_pass_block():
    F = _in_window(LOUD)
    assert _rs(F)["state"] == "partial" and _rs(F)["missed"] == ["k3_vol"]
    re_ = _rs(F, k3_binding=False)
    assert re_["state"] == "aplus"
    b = AUD.judge(re_, F, [], ctx=CTX, admit="K3S")
    assert b["aplus"] is True and b["admit"] == "K3S" and b["original_aplus"] is False
    assert b["rules"] == JUDGE_IDS == b["passed"] and b["failed"] == []
    assert b["text"] == AUD.ADMIT_TEXT_OK.format(admit="K3S", reason=D.NOT_APLUS_REASON, ids=" · ".join(JUDGE_IDS),
                                                 unmeasured="UNMEASURED")
    assert b["text"] == ("🧪 A+ by K3S — 🚩 reads it 'broke — not A+' · G1 · G2 · G4 · T2 · A1 · H1 · T4 · A2 pass · "
                         "UNMEASURED")
    assert set(b) == set(AUD.AUDIT_SERVED_KEYS) and b["version"] == AUD.AUDIT_VERSION == 3
    json.dumps(b)


def test_judge_admit_k3s_held_block_says_who_held_it():
    F = FX.rs_frame(LOUD)                                                                   # break bar 05:10 ET
    re_ = _rs(F, k3_binding=False)
    b = AUD.judge(re_, F, [], ctx=CTX, admit="K3S")
    assert b["aplus"] is False and b["admit"] == "K3S" and b["original_aplus"] is False
    assert {f["id"] for f in b["failed"]} >= {"T2", "H1"}
    assert b["text"].startswith("🧪 A+ by K3S (🚩 reads it 'broke — not A+'), held here by: ")
    assert b["text"].endswith(" · UNMEASURED") and "T2 — the break bar started" in b["text"]
    assert set(b) == set(AUD.AUDIT_SERVED_KEYS)


def test_with_t1_keeps_the_admit_and_its_words():
    F = _in_window(LOUD)
    b = AUD.judge(_rs(F, k3_binding=False), F, [], ctx=CTX, admit="K3S")
    a = AUD.with_t1(b, True, "", {"slot": 1})
    assert a["admit"] == "K3S" and a["original_aplus"] is False and a["aplus"] is True
    assert a["text"] == ("🧪 A+ by K3S — 🚩 reads it 'broke — not A+' · G1 · G2 · G4 · T2 · A1 · H1 · T4 · A2 · T1 "
                         "pass · UNMEASURED")
    h = AUD.with_t1(b, False, "daily cap of 2 reached — the slots went to AAA 10:45, BBB 10:50", {"slot": None})
    assert h["admit"] == "K3S" and h["aplus"] is False
    assert h["text"] == ("🧪 A+ by K3S (🚩 reads it 'broke — not A+'), held here by: T1 — daily cap of 2 reached — the "
                         "slots went to AAA 10:45, BBB 10:50 · UNMEASURED")
    assert set(a) == set(h) == set(AUD.AUDIT_SERVED_KEYS)


def test_NEGATIVE_a_normal_block_carries_admit_none_and_todays_words():
    F = FX.rs_frame()                                                                       # a 🚩 A+ (not admitted)
    r = _rs(F)
    b = AUD.judge(r, F, [], ctx=CTX)
    assert b["admit"] is None and b["original_aplus"] is True
    assert b["text"].startswith("🚩 A+ on the original, held here by: ") and b["text"].endswith(" · UNMEASURED")
    F2 = _in_window(FX.RS_BARS)
    ok = AUD.judge(_rs(F2), F2, [], ctx=CTX)
    assert ok["aplus"] is True and ok["admit"] is None and ok["original_aplus"] is True
    assert ok["text"] == "audited A+ — G1 · G2 · G4 · T2 · A1 · H1 · T4 · A2 pass · UNMEASURED"
    t1 = AUD.with_t1(ok, True, "", {"slot": 1})
    assert t1["admit"] is None and t1["text"] == ("audited A+ — G1 · G2 · G4 · T2 · A1 · H1 · T4 · A2 · T1 pass · "
                                                  "UNMEASURED")


@pytest.mark.parametrize("junk", ["junk", "T1", "G1", "", 7, True, ["K3S"]])
def test_NEGATIVE_judge_refuses_a_junk_admit(junk):
    F = _in_window(LOUD)
    with pytest.raises(ValueError, match="admit must name an ON admit rule"):
        AUD.judge(_rs(F, k3_binding=False), F, [], ctx=CTX, admit=junk)


def test_NEGATIVE_judge_of_the_partial_read_with_admit_is_none():
    F = _in_window(LOUD)
    assert AUD.judge(_rs(F), F, [], ctx=CTX, admit="K3S") is None
    assert AUD.judge(None, F, [], ctx=CTX, admit="K3S") is None


def test_NEGATIVE_with_t1_ignores_a_junk_admit_on_the_block():
    F = _in_window(FX.RS_BARS)
    ok = AUD.judge(_rs(F), F, [], ctx=CTX)
    for junk in (7, "", None, ["K3S"]):
        a = AUD.with_t1(dict(ok, admit=junk), True, "", {"slot": 1})
        assert a["admit"] is None and a["text"].startswith("audited A+ — ")


def test_the_admit_words_carry_the_one_reason_and_no_banned_word():
    for tpl in (AUD.ADMIT_TEXT_OK, AUD.ADMIT_TEXT_HELD):
        s = tpl.format(admit="K3S", reason=D.NOT_APLUS_REASON, ids="G1", fails="G1 — x", unmeasured="UNMEASURED")
        assert D.NOT_APLUS_REASON in s and "UNMEASURED" in s
        assert not EDGE.search(s) and not B_WORD.search(s) and not re.search(r"\d", tpl)   # NEGATIVE
    k = AUD.K3S
    for s in (k.name, k.rule.format(**k.params), k.verdict_source, k.changes, k.note, AUD.rules_clause(),
              AUD.K3S_PARTIAL_ROW_STATE):
        assert not EDGE.search(s) and not B_WORD.search(s) and "None" not in s, s[:60]


# ── the doc ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_doc_carries_his_words_the_prereg_and_the_his_calls():
    txt = DOC.read_text(encoding="utf-8")
    assert f'"{HIS_WORDS}' in txt and AUD.PREREG3_SHA256 in txt and "UNMEASURED" in txt
    assert "k11_gate" in txt and "bars_since_entry == 0" in txt and "#partial_break" in txt
    for n in range(37, 50):
        assert f"\n{n}. " in txt, n                                                     # the numbered HIS CALL list
    assert not EDGE.search(txt) and not B_WORD.search(txt)                                # NEGATIVE
