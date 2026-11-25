"""🧠 from every tab — `pot_all.block` and its wiring on the 🧠 sub (SPEC potall REV 2 §3.1 / §3.2, WP be-potall).

Ajay 2026-11-24 ~22:00 ET, verbatim: "I need a common place to see all the potnetials from all tabs" · "I mean all
Gajjala's tabs". One list under the 🧠 cards: every forming card of the five setup subs the 🧠 cards do not show, every
🌱 row, and every setup whose 🧭 stages show a 🎯 A+ this session ("✅ broke HH:MM" — stages.steps ONLY). Display only.

NEGATIVES are mandatory and lead: BAK (stopped, no A+ → no ✅, no row), partial, 🌀 with 1 contraction, a covered
potential, the previous session's entries, NaN, the GG1 / 🧪 boards carrying no key, and the push path pinned by source.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import diverging_tab as DGT
from chart_maps.gajjala import pot_all as PA
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import stages as SG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_potential_tab import S as PS, day_store
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import NOW, R, S, latest, read_doc, store_with, utc

ET = ZoneInfo("America/New_York")
ISO = S.isoformat()
PREV_ISO = date(2026, 10, 12).isoformat()
FRI, SAT = date(2026, 10, 16), date(2026, 10, 17)
RS, KF, BF, HF, VCP = "reversal_squeeze", "kiss_fly", "bull_flag", "horizontal_fade", "intraday_vcp"
PASS_OK = {"status": "ok", "stale": False, "warming": False, "as_of_et": "10:31 ET"}

# step 1 of WP be-potall: sha256 of inspect.getsource on the UNTOUCHED tree (origin/main 5dec3c6b), recorded BEFORE any edit
PUSH_PATH_SHA = {
    "potential.run_pass": "957892da2c550f362684644c8ae4f9039773bf2207c5e93cac772ef8b38cc712",
    "potential.potential_kind": "ac772217dc447021e13cec40c418c5d8f06cdc0790efac2ea98ae396348ac3d9",
    "potential.eligible": "819f8d4f8eed7cd2f03a22a5f582e0b97cfa707a9bee2e6de69a48b53193e107",
    "potential.track": "ade129f8ddada031c79991c378f2cbfc8bfe9113842035970f7052cf7448d9db",
    "potential.compose": "c7d3a3fc3c920cc4df3e92fda0d01ae8eba147a195d73467db6d98cb6e3075be",
    "alerts.run_pass": "d2ded91a11f4fecd41deb023adb6ca4104ba9fcebbea8c808ebb8fff9acbc778",
    "stages.steps": "73110327d1518ea04868e97cdcd58f7b86f5e960c416a3d047b0781058c3f291",
}


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────
def fm(setup, *, base=0, ready=False, **kw):
    """A forming read; base 0 = no sideways bar yet (never a potential, P0)."""
    return R(setup, "forming", base={"bars": base}, ready=ready, **kw)


def pot(setup, *, ready=True, **kw):
    return fm(setup, base=2, ready=ready, **kw)


def trk(sym, setup, *path):
    return {"date": ISO, "symbol": sym, "setup": setup,
            "state_path": [{"state": s, "kind": k, "at_et": at} for s, k, at in path]}


def carded_of(reads_by):
    """build's own carded rule: TILE_STATES and the 🌀 2-contraction listing rule."""
    out = {}
    for setup in GC.SETUPS:
        for sym, doc in reads_by.items():
            r = (doc.get("setups") or {}).get(setup) or {}
            if r.get("state") in GT.TILE_STATES and GT._vcp_listed(setup, r):
                out.setdefault(setup, []).append(sym)
    return out


def blk(reads=None, **kw):
    reads_by = {s: read_doc(s, setups) for s, setups in (reads or {}).items()}
    args = dict(reads_by=reads_by, carded=carded_of(reads_by), covered=set(), trackers={}, entries={},
                session_iso=ISO, dvg=None, hsi=None, scan_by={}, rang=lambda s, k: None, flags=frozenset(),
                sess={"label": "today"}, in_window=True, pass_info=dict(PASS_OK), pass_at=NOW, pot_ok=True, v=None)
    args.update(kw)
    return PA.block(**args)


def keys(b):
    return [(r["symbol"], r["setup"]) for r in b["rows"]]


def row_of(b, sym, setup):
    hit = [r for r in b["rows"] if (r["symbol"], r["setup"]) == (sym, setup)]
    assert len(hit) == 1, (sym, setup, keys(b))
    return hit[0]


def dvg_row(sym, **kw):
    read = dict({"gap_atr": 0.42, "bar_t": f"{ISO} 10:25", "widen_bars": 3, "bar_vol_mult": 2.6}, **kw)
    return {"symbol": sym, "read": read, "read_doc": read_doc(sym, {})}


# ── NEGATIVES first ──────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_bak_stopped_with_no_aplus_step_and_no_entry_is_never_broke_and_no_row():
    """BAK 💋 2026-11-24: read stopped (entry_bar_t 09:55), path forming/armed > partial > stopped, no rang A+."""
    bak = R(KF, "stopped", entry_bar_t="2026-11-24 09:55", broke=True)
    tr = {("BAK", KF): trk("BAK", KF, ("forming", "armed", "09:41"), ("partial", None, "09:56"),
                           ("stopped", None, "13:11"))}
    b = blk({"BAK": {KF: bak}}, trackers=tr, entries={})
    assert b["rows"] == [] and b["counts"]["broke"] == 0
    assert all("09:55" not in json.dumps(r) for r in b["rows"])
    # the same with a TRIGGERED read: no aplus step, no entry → no ✅ and no row (triggered is not in LIST_STATES)
    trig = R(KF, "triggered", entry_bar_t="2026-11-24 09:55", bars_since_entry=2, broke=True)
    tr2 = {("BAK", KF): trk("BAK", KF, ("forming", "armed", "09:41"), ("triggered", None, "09:56"))}
    b2 = blk({"BAK": {KF: trig}}, trackers=tr2, entries={})
    assert b2["rows"] == [] and "triggered" not in PA.LIST_STATES


def test_NEGATIVE_partial_invalid_none_are_never_rows():
    b = blk({"PPP": {BF: R(BF, "partial", missed=["k3_vol"])}, "III": {KF: R(KF, "invalid", reason="died")},
             "NNN": {HF: R(HF, "none")}})
    assert b["rows"] == [] and b["counts"] == {"potential": 0, "forming": 0, "broke": 0}
    assert PA.LIST_STATES == (GC.POTENTIAL_STATE,)                  # HIS CALL #1: partial is not listed (K1)


def test_NEGATIVE_previous_session_entry_is_never_a_broke_today():
    b = blk({"OLD": {BF: R(BF, "partial")}}, entries={(PREV_ISO, "OLD", BF): "10:00"})
    assert b["rows"] == [] and b["counts"]["broke"] == 0


def test_NEGATIVE_a_covered_potential_has_no_row_but_counts():
    b = blk({"JZ": {RS: pot(RS)}}, covered={("JZ", RS)})
    assert b["rows"] == [] and b["counts"]["potential"] == 1
    # a ✅ on a covered (symbol, setup) is skipped too — its card's 🧭 tag already shows the A+
    b2 = blk({"JZ": {RS: pot(RS)}}, covered={("JZ", RS)},
             trackers={("JZ", RS): trk("JZ", RS, ("forming", "armed", "09:00"), ("aplus", None, "09:05"))})
    assert b2["rows"] == []


def test_NEGATIVE_broke_tier_rows_carry_no_no_alert_tag():
    tr = {("LVWR", VCP): trk("LVWR", VCP, ("forming", "armed", "14:26"), ("aplus", None, "14:36"))}
    b = blk({"LVWR": {VCP: R(VCP, "partial", cycles=2)}}, trackers=tr)
    r = row_of(b, "LVWR", VCP)
    assert r["tier"] == "broke" and r["alert_text"] is None and r["broke_text"] == "✅ broke 14:36"


def test_NEGATIVE_keep_broke_off_lists_no_broke(monkeypatch):
    tr = {("LVWR", VCP): trk("LVWR", VCP, ("forming", "armed", "14:26"), ("aplus", None, "14:36"))}
    monkeypatch.setattr(PA, "KEEP_BROKE", False)
    b = blk({"LVWR": {VCP: R(VCP, "partial", cycles=2)}}, trackers=tr)
    assert b["rows"] == [] and b["counts"]["broke"] == 0


def test_NEGATIVE_a_hsi_name_with_no_forming_read_is_no_row():
    hsi = {"rows": [{"symbol": "SHO", "read": {}, "read_doc": read_doc("SHO", {})}]}
    b = blk({"SHO": {RS: R(RS, "partial")}}, hsi=hsi)
    assert b["rows"] == []


def test_NEGATIVE_nan_everywhere_serves_finite_json():
    nan = float("nan")
    reads = {"NAN": {BF: fm(BF, trigger=nan, stop=nan, risk_pct=nan)}, "NA2": {RS: pot(RS, trigger=nan)}}
    scan_by = {"NAN": {"last": {"volume": nan}}, "NA2": {"last": {"volume": float("inf")}}}
    b = blk(reads, scan_by=scan_by, dvg={"rows": [dvg_row("NA3", gap_atr=nan, bar_vol_mult=nan)]})
    json.dumps(b, allow_nan=False)
    assert {k for k in keys(b)} == {("NAN", BF), ("NA2", RS), ("NA3", GC.DIVERGING_SUB)}
    assert b["faults_n"] == 0


def test_NEGATIVE_one_malformed_read_is_a_fault_the_rest_stand():
    bad = fm(VCP, cycles=2, grade=GC.VCP_B_GRADE, missed=5)          # grade_label iterates `missed` → raises
    b = blk({"BAD": {VCP: bad}, "OK1": {KF: fm(KF)}})
    assert keys(b) == [("OK1", KF)]
    assert b["faults_n"] == 1 and b["fault_text"] == "1 row(s) could not be built this read — skipped, never hidden by a rule"


# ── rows: one per (symbol, setup) ────────────────────────────────────────────────────────────────────────────────
def test_a_name_only_forming_on_reversal_squeeze_is_one_row_with_the_no_alert_tag():
    b = blk({"ZZZ": {RS: fm(RS)}})
    assert keys(b) == [("ZZZ", RS)]                                  # NEGATIVE: nowhere else in the block
    r = b["rows"][0]
    assert r["tier"] == "forming" and r["alert_text"] == PA.NO_ALERT_TEXT == "listed · no 🧠 alert"
    assert r["text"] == "ZZZ · 🎾 Reversal Squeeze · forming — no sideways bar yet"
    assert r["state_word"] == PT.FORMING_NOT_POTENTIAL and r["kind"] is None and r["state"] == "forming"
    assert r["state_label"] == GT.state_label(read_doc("ZZZ", {RS: fm(RS)})["setups"][RS], None)
    assert r["href"] == PT.deep_link("ZZZ", RS) and r["broke_text"] is None and r["read_at_text"] is None
    assert b["counts"] == {"potential": 0, "forming": 1, "broke": 0}


def test_a_name_forming_on_two_setups_is_two_rows_and_vcp_plus_diverging_too():
    b = blk({"TWO": {VCP: fm(VCP, cycles=2), KF: fm(KF)}})
    assert sorted(keys(b)) == sorted([("TWO", VCP), ("TWO", KF)])
    b2 = blk({"NUR": {VCP: fm(VCP, cycles=2)}}, dvg={"rows": [dvg_row("NUR")]})
    assert sorted(keys(b2)) == sorted([("NUR", VCP), ("NUR", GC.DIVERGING_SUB)])


def test_the_squeeze_row_also_on_high_si_is_one_row_with_the_high_si_tag():
    hsi = {"rows": [{"symbol": "JZ", "read": {}, "read_doc": read_doc("JZ", {})}]}
    b = blk({"JZ": {RS: fm(RS)}}, hsi=hsi)
    assert keys(b) == [("JZ", RS)]
    r = b["rows"][0]
    e, label = GT.SUB_META[GC.HIGH_SI_SUB]
    assert r["also"] == [{"key": GC.HIGH_SI_SUB, "emoji": e, "label": label}]
    assert r["text"] == f"JZ · 🎾 Reversal Squeeze {e} · forming — no sideways bar yet"
    # NEGATIVE: a 🩳 name forming on another setup gets no 🩳 tag (the tag rides the 🎾 read only)
    b2 = blk({"JZ": {KF: fm(KF)}}, hsi=hsi)
    assert b2["rows"][0]["also"] == []


def test_uncovered_potential_is_tier_potential_with_no_tag_and_a_tracker_fault_says_so():
    b = blk({"JZ": {RS: pot(RS)}})
    r = row_of(b, "JZ", RS)
    assert r["tier"] == "potential" and r["kind"] == "armed" and r["alert_text"] is None
    assert r["state_word"] == PT.KIND_LABEL["armed"]
    assert b["fault_text"] is None
    bf = blk({"JZ": {RS: pot(RS)}}, pot_ok=False)
    rf = row_of(bf, "JZ", RS)
    assert rf["tier"] == "potential" and bf["counts"]["potential"] == 1        # from potential_kind, never "forming"
    assert bf["fault_text"] == PA.TRACK_FAULT_TEXT


def test_variant_and_vcp_grade_b_reads_serve_their_own_labels_with_the_tag():
    b = blk({"LFL": {BF: fm(BF, variant="long_flag")}, "VCB": {VCP: fm(VCP, cycles=2, grade=GC.VCP_B_GRADE)}})
    lf, vb = row_of(b, "LFL", BF), row_of(b, "VCB", VCP)
    assert lf["state_word"] == GT.variant_label(fm(BF, variant="long_flag")) and lf["alert_text"] == PA.NO_ALERT_TEXT
    assert vb["state_word"] == GT.grade_label(fm(VCP, grade=GC.VCP_B_GRADE)) and vb["alert_text"] == PA.NO_ALERT_TEXT
    assert vb["state_word"].startswith("B — imperfect")


def test_every_diverging_row_carries_the_tag_and_its_own_label():
    b = blk(dvg={"rows": [dvg_row("NUR"), dvg_row("DKI", gap_atr=0.3)]})
    assert {r["symbol"] for r in b["rows"]} == {"NUR", "DKI"}
    for r in b["rows"]:
        assert r["setup"] == GC.DIVERGING_SUB and r["alert_text"] == PA.NO_ALERT_TEXT and r["tier"] == "forming"
        assert r["state"] == DGT.STATE
        assert r["href"] == PT.deep_link(r["symbol"], GC.DIVERGING_SUB)
    nur = row_of(b, "NUR", GC.DIVERGING_SUB)
    assert nur["state_word"] == DGT.state_label(dvg_row("NUR")["read"]) == nur["state_label"]
    assert nur["text"] == f"NUR · 🌱 Diverging · {nur['state_word']}"


# ── ✅ broke: stages.steps only ──────────────────────────────────────────────────────────────────────────────────
def test_aplus_kept_from_the_tracker_path_over_a_partial_read():
    tr = {("LVWR", VCP): trk("LVWR", VCP, ("forming", "armed", "14:26"), ("aplus", None, "14:36"),
                             ("partial", None, "14:46"))}
    b = blk({"LVWR": {VCP: R(VCP, "partial", cycles=2, missed=["k3_vol"])}}, trackers=tr)
    r = row_of(b, "LVWR", VCP)
    assert (r["tier"], r["broke_at"], r["broke_text"]) == ("broke", "14:36", "✅ broke 14:36")
    assert r["state_word"] == PT.state_word("partial", None) == "partial — a rule failed"
    assert r["href"] == PT.deep_link("LVWR", VCP)                    # carded partial → its card exists
    assert b["counts"]["broke"] == 1


def test_aplus_kept_from_a_rang_entry_with_no_tracker_doc():
    b = blk({"GMM": {KF: R(KF, "invalid")}}, entries={(ISO, "GMM", KF): "12:26"})
    r = row_of(b, "GMM", KF)
    assert r["broke_text"] == "✅ broke 12:26" and r["tier"] == "broke"
    assert r["href"] is None                                         # invalid → no card on 💋 → plain text


def test_the_tracker_aplus_clock_wins_over_the_entry_clock():
    tr = {("BENF", RS): trk("BENF", RS, ("forming", "armed", "10:56"), ("aplus", None, "12:11"))}
    b = blk({"BENF": {RS: R(RS, "partial")}}, trackers=tr, entries={(ISO, "BENF", RS): "12:12"})
    assert row_of(b, "BENF", RS)["broke_at"] == "12:11"


def test_broke_at_is_the_first_aplus_of_the_stages_tag_for_the_same_card():
    doc = trk("ONFO", VCP, ("forming", "armed", "13:21"), ("aplus", None, "13:31"), ("triggered", None, "13:36"),
              ("aplus", None, "14:01"))
    entries = {(ISO, "ONFO", VCP): "13:32"}
    b = blk({"ONFO": {VCP: R(VCP, "partial", cycles=2)}}, trackers={("ONFO", VCP): doc}, entries=entries)
    by = SG.by_symbol({S: [doc]}, board_session=S, is_today=True, symbols={"ONFO"}, cadence_min=5, entries=entries)
    steps = by["ONFO"]["groups"][0]["tags"][0]["steps"]
    first = next(s["at_et"] for s in steps if s["stage"] == "aplus")
    assert row_of(b, "ONFO", VCP)["broke_at"] == first == "13:31"    # two A+ steps → the FIRST


def test_a_forming_row_that_also_broke_keeps_its_tier_and_gains_the_tag():
    tr = {("FFR", HF): trk("FFR", HF, ("aplus", None, "11:00"), ("forming", None, "11:30"))}
    b = blk({"FFR": {HF: fm(HF)}}, trackers=tr)
    r = row_of(b, "FFR", HF)
    assert r["tier"] == "forming" and r["broke_text"] == "✅ broke 11:00" and r["alert_text"] == PA.NO_ALERT_TEXT


def test_a_tracker_only_name_off_the_reads_is_plain_text_with_its_last_path_word():
    tr = {("GONE", BF): trk("GONE", BF, ("forming", "armed", "09:50"), ("aplus", None, "10:00"),
                            ("stopped", None, "10:20"))}
    b = blk({}, trackers=tr)
    r = row_of(b, "GONE", BF)
    assert r["href"] is None and r["state"] == "stopped" and r["state_word"] == PT.state_word("stopped", None)
    assert r["state_label"] is None and r["read_at_text"] is None and r["broke_text"] == "✅ broke 10:00"


def test_benf_vcp_zero_contraction_read_breaks_with_no_card_link():
    tr = {("BENF", VCP): trk("BENF", VCP, ("forming", "armed", "14:31"), ("aplus", None, "14:41"))}
    b = blk({"BENF": {VCP: fm(VCP, cycles=0)}}, trackers=tr)
    r = row_of(b, "BENF", VCP)
    assert r["tier"] == "broke" and r["href"] is None                 # not carded (< 2 contractions)


def test_a_broke_step_with_no_clock_says_broke_today_and_sorts_last():
    tr = {("NCK", BF): trk("NCK", BF, ("aplus", None, None)),
          ("CLK", KF): trk("CLK", KF, ("aplus", None, "09:40"))}
    b = blk({}, trackers=tr)
    assert keys(b) == [("CLK", KF), ("NCK", BF)]
    assert row_of(b, "NCK", BF)["broke_text"] == PA.BROKE_TEXT_NOCLOCK and row_of(b, "NCK", BF)["broke_at"] is None


def test_the_pill_is_rang_aware_like_the_setup_sub():
    trig = R(BF, "triggered", entry_bar_t=f"{ISO} 10:25", bars_since_entry=1, broke=True)
    tr = {("TRG", BF): trk("TRG", BF, ("forming", "armed", "10:20"), ("aplus", None, "10:26"))}
    b = blk({"TRG": {BF: trig}}, trackers=tr, rang=lambda s, k: False)
    assert row_of(b, "TRG", BF)["state_label"] == GT.state_label(trig, False)
    assert GT.NO_RING_TEXT in row_of(b, "TRG", BF)["state_label"]


# ── read_at, liveness, order, cap ────────────────────────────────────────────────────────────────────────────────
def test_read_at_text_is_the_cards_own_stale_read_word():
    doc_old = read_doc("OLD", {KF: fm(KF)}, updated_at=utc(10, 1))
    reads_by = {"OLD": doc_old}
    b = blk(reads_by=reads_by, carded=carded_of(reads_by))
    assert row_of(b, "OLD", KF)["read_at_text"] == GT._read_at_text(doc_old, NOW) == "read at the 10:01 ET pass"
    assert row_of(blk({"NEW": {KF: fm(KF)}}), "NEW", KF)["read_at_text"] is None    # NEGATIVE: the pass's own read


@pytest.mark.parametrize("info,live", [
    (PASS_OK, True),
    (dict(PASS_OK, status="error"), False), (dict(PASS_OK, status="failed"), False),
    (dict(PASS_OK, stale=True), False), (dict(PASS_OK, warming=True), False), ({}, False)])
def test_live_needs_an_ok_current_pass_in_the_window(info, live):
    b = blk({"ZZZ": {RS: fm(RS)}}, pass_info=info)
    assert b["live"] is live
    assert blk({"ZZZ": {RS: fm(RS)}}, pass_info=info, in_window=False)["live"] is False


def test_as_of_text_never_prints_none():
    assert blk({"ZZZ": {RS: fm(RS)}})["as_of_text"] == "as of the 10:31 ET pass · today"
    assert blk({"ZZZ": {RS: fm(RS)}}, pass_info=dict(PASS_OK, as_of_et=None))["as_of_text"] is None
    assert blk({}, pass_info=PASS_OK)["as_of_text"] is None          # no rows → no stamp
    assert "None" not in json.dumps(blk({"ZZZ": {RS: fm(RS)}}, pass_info=dict(PASS_OK, as_of_et=None)))


def test_order_potential_then_forming_by_order_key_then_broke_newest_first_and_his_names_last():
    reads = {"ARM": {BF: pot(BF, ready=True)}, "BLD": {KF: pot(KF, ready=False)},
             "LOV": {RS: fm(RS)}, "HIV": {HF: fm(HF)}, "UNK": {BF: fm(BF)}, "FID": {KF: fm(KF)}}
    scan_by = {"LOV": {"last": {"volume": 1e6}}, "HIV": {"last": {"volume": 5e6}}, "FID": {"last": {"volume": 9e6}},
               "BLD": {"last": {"volume": 9e6}}, "ARM": {"last": {"volume": 1e5}}}
    tr = {("OLD", BF): trk("OLD", BF, ("aplus", None, "09:40")), ("NEW", BF): trk("NEW", BF, ("aplus", None, "15:10")),
          ("FBK", KF): trk("FBK", KF, ("aplus", None, "16:00"))}
    b = blk(reads, scan_by=scan_by, trackers=tr, flags=frozenset({"FID", "FBK"}))
    assert keys(b) == [("ARM", BF), ("BLD", KF),                       # potential tier: armed first
                       ("HIV", HF), ("LOV", RS), ("UNK", BF), ("FID", KF),   # forming by volume, unknown last, 🚫 last
                       ("NEW", BF), ("OLD", BF), ("FBK", KF)]            # ✅ newest first, 🚫 last in its group
    assert [r["tier"] for r in b["rows"]] == ["potential"] * 2 + ["forming"] * 4 + ["broke"] * 3
    assert b["title"] == "🧠 from every tab — 4 other forming · 3 ✅ broke today · 2 🧠 potential on the cards above"
    assert b["order_text"] == PA.ORDER_TEXT and b["n"] == 9 and b["more_n"] == 0 and b["more_text"] is None


def test_more_than_the_transport_cap_is_cut_with_more_text():
    reads = {f"S{i:03d}": {KF: fm(KF)} for i in range(GC.TILE_LIMIT_MAX + 3)}
    b = blk(reads)
    assert len(b["rows"]) == GC.TILE_LIMIT_MAX and b["n"] == GC.TILE_LIMIT_MAX + 3 and b["more_n"] == 3
    assert b["more_text"] == f"3 more rows below the {GC.TILE_LIMIT_MAX}-row transport cap — not shown this read"
    assert b["counts"]["forming"] == GC.TILE_LIMIT_MAX + 3


def test_rule_text_is_built_from_the_served_emojis():
    t = PA.rule_text()
    for s in GC.SETUPS + (GC.DIVERGING_SUB, GC.DIVERGENCE_SUB, GC.HIGH_SI_SUB, "premarket", "postmarket"):
        assert GT.SUB_META[s][0] in t, s
    assert PA.NO_ALERT_TEXT in t and SG.STAGE_WORDS["aplus"] in t and t.endswith(GT.UNMEASURED + ".")
    assert "b" + "ounc" not in t.lower()


def test_covered_reads_the_primary_and_every_also_setup():
    tiles = [{"symbol": "aaa", "gajjala": {"potential": {"setup": BF, "also": [{"setup": KF}, "junk"]}}},
             {"symbol": "BBB", "gajjala": {}}, "junk", {"symbol": "CCC", "gajjala": {"potential": {"setup": RS}}}]
    assert PA.covered(tiles) == {("AAA", BF), ("AAA", KF), ("CCC", RS)}
    assert PA.covered(None) == set()


# ── the board: wiring on 🧠, GG5 only ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def pstore():
    return day_store()


def pbuild(sub, st, **kw):
    return GT.build(sub, now=kw.pop("now", datetime(PS.year, PS.month, PS.day, 10, 31, tzinfo=ET)), store=st, **kw)


def test_the_potential_board_lists_the_baseless_forming_card_and_the_aplus_kept(pstore):
    out = pbuild(GC.POTENTIAL_SUB, pstore)
    b = out["all_potentials"]
    assert keys(b) == [("GGG", BF), ("BBB", KF)]
    ggg, bbb = b["rows"]
    assert ggg["alert_text"] == PA.NO_ALERT_TEXT and ggg["state_word"] == PT.FORMING_NOT_POTENTIAL
    assert bbb["broke_text"] == "✅ broke 10:31" and bbb["tier"] == "broke"
    # NEGATIVE: every 🧠 card's (symbol, setup) is covered — never a row twice
    cov = PA.covered(out["tiles"])
    assert not cov & set(keys(b)) and b["counts"]["potential"] == len(cov)
    assert "GGG" not in [t["symbol"] for t in out["tiles"]]
    assert b["live"] is True and b["as_of_text"] == "as of the 10:31 ET pass · today"
    assert all("trader_text" in r and "broker_text" in r for r in b["rows"])   # the three tag walks reach it
    json.dumps(out, allow_nan=False)


def test_NEGATIVE_no_other_sub_carries_the_key(pstore):
    for k, _e, _l in GC.SUBS:
        if k == GC.POTENTIAL_SUB:
            continue
        assert "all_potentials" not in pbuild(k, pstore), k


def test_NEGATIVE_gg1_and_audited_boards_carry_no_key(pstore):
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GG1, shared=pstore)
    assert "all_potentials" not in pbuild(GC.POTENTIAL_SUB, g1, variant=V.GG1)
    gga = ST.GajjalaStore(colls={n: FakeColl() for n in (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY, ST.EXITS)},
                          variant=V.GGA, shared=pstore)
    assert "all_potentials" not in pbuild(GC.POTENTIAL_SUB, gga, variant=V.GGA)


def test_a_raising_block_serves_none_and_the_rest_of_the_board_is_byte_identical(pstore, monkeypatch):
    good = pbuild(GC.POTENTIAL_SUB, pstore)
    assert good.pop("all_potentials") is not None

    def boom(**_kw):
        raise RuntimeError("pot_all down")
    monkeypatch.setattr(PA, "block", boom)
    bad = pbuild(GC.POTENTIAL_SUB, pstore)
    assert bad.pop("all_potentials") is None
    assert json.dumps(good, sort_keys=True, default=str) == json.dumps(bad, sort_keys=True, default=str)
    for k in ("tiles", "track", "watch", "empty_note", "order_note", "subs"):
        assert good[k] == bad[k], k


def test_owner_rows_carry_the_broker_word_and_minus_the_tags_equal_the_non_owner(pstore, monkeypatch):
    monkeypatch.setattr(ST, "broker_flags", lambda _st: (("GGG",), False))
    own = pbuild(GC.POTENTIAL_SUB, pstore, owner=True)["all_potentials"]
    non = pbuild(GC.POTENTIAL_SUB, pstore)["all_potentials"]
    g = row_of(own, "GGG", BF)
    assert g["broker_text"] == GT.BROKER_FLAG_TEXT and row_of(non, "GGG", BF)["broker_text"] is None
    strip = copy.deepcopy(own)
    for r in strip["rows"]:
        r["broker_text"] = None
    assert strip == non


def test_build_writes_nothing(pstore):
    before = {n: copy.deepcopy(pstore.coll(n).docs) for n in ST.ALL if hasattr(pstore.coll(n), "docs")}
    pbuild(GC.POTENTIAL_SUB, pstore, owner=True)
    after = {n: pstore.coll(n).docs for n in before}
    assert before == after


def _store_reads(day, reads, pass_at):
    docs = [read_doc(s, setups, day=day, updated_at=pass_at) for s, setups in reads.items()]
    return store_with(reads=docs, passes=[latest(at=pass_at, day=day)])


def test_closed_day_serves_fridays_rows_not_live_with_fridays_pass_named():
    st = _store_reads(FRI, {"GGG": {BF: fm(BF)}}, utc(19, 56, FRI))
    out = GT.build(GC.POTENTIAL_SUB, now=utc(12, 0, SAT), store=st)
    b = out["all_potentials"]
    assert keys(b) == [("GGG", BF)] and b["live"] is False
    assert b["as_of_text"] == f"as of the 19:56 ET pass · last session {FRI.isoformat()}"


def test_NEGATIVE_no_reads_no_pass_serves_no_rows_and_todays_empty_note():
    out = GT.build(GC.POTENTIAL_SUB, now=NOW, store=store_with())
    b = out["all_potentials"]
    assert b["rows"] == [] and b["as_of_text"] is None and b["live"] is False
    assert out["empty_note"] == f"Nothing forming on his list right now — the next pass is at most {GT._mins(GT._cad(None))} away."


def test_NEGATIVE_vcp_with_one_contraction_and_an_awaiting_setup_are_no_rows(monkeypatch):
    assert GC.vcp_list_min_cycles() == 2
    st = _store_reads(S, {"ONE": {VCP: fm(VCP, cycles=1, base=2, ready=True)}, "TWO": {VCP: fm(VCP, cycles=2)},
                          "AWT": {KF: fm(KF)}}, NOW)
    assert sorted(keys(GT.build(GC.POTENTIAL_SUB, now=NOW, store=st)["all_potentials"])) == [("AWT", KF), ("TWO", VCP)]
    real = GT._awaiting
    monkeypatch.setattr(GT, "_awaiting", lambda s: {"setup": s, "text": "awaiting"} if s == KF else real(s))
    assert keys(GT.build(GC.POTENTIAL_SUB, now=NOW, store=st)["all_potentials"]) == [("TWO", VCP)]


# ── the push path is untouched ───────────────────────────────────────────────────────────────────────────────────
def test_push_path_sources_are_byte_identical_to_the_untouched_tree():
    fns = {"potential.run_pass": PT.run_pass, "potential.potential_kind": PT.potential_kind,
           "potential.eligible": PT.eligible, "potential.track": PT.track, "potential.compose": PT.compose,
           "alerts.run_pass": AL.run_pass, "stages.steps": SG.steps}
    got = {k: hashlib.sha256(inspect.getsource(f).encode()).hexdigest() for k, f in fns.items()}
    assert got == PUSH_PATH_SHA


def test_potential_run_pass_still_rings_the_fixture_days_sightings(pstore):
    docs = {(d["symbol"], d["setup"]): d for d in pstore.potentials(PS)}
    assert set(docs) == {("AAA", BF), ("AAA", KF), ("BBB", KF), ("JJJ", BF), ("CCC", HF), ("DDD", RS), ("EEE", BF)}
    assert docs[("EEE", BF)]["push"]["state"] == "pushed" and docs[("DDD", RS)]["push"]["state"] == "pushed"
    assert "push" not in docs[("CCC", HF)]


def test_alerts_run_pass_still_rings_two_setups_on_one_name(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    from tests.test_gajjala_alerts import Spy, at as aat, frames_at, read as aread
    st, send = fake_store(), Spy()
    r1, r2 = aread(BF), aread(KF)
    counts = AL.run_pass({"GGA": {BF: r1, KF: r2}}, {"GGA": frames_at(r1["entry_bar_t"])}, aat(10, 6), S,
                         store=st, send=send, owner="o")
    assert counts["pushed"] == 2 and [p["tag"] for _o, p in send.calls] == ["gg-bull_flag-GGA", "gg-kiss_fly-GGA"]


def test_pot_all_imports_nothing_that_writes_or_rings():
    tree = ast.parse(Path(PA.__file__).read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
            mods.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    banned = ("store", "push", "alerts", "run", "on_demand", "pymongo", "requests", "httpx")
    for m in mods:
        assert not any(part in banned for part in m.split(".")), m
    src = Path(PA.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in src and "_clock(" not in src and "SG.steps" in src
    assert "b" + "ounc" not in src.lower()
