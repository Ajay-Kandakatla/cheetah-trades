"""🧪 Gajjala · Audited — K3S in the overlay step (SPEC REV 2 2026-11-09 §3.3, WP-B `gg-k3s-pass`).

Ajay 2026-11-09: "yes change the audit as per you like that is yours I need you to make it successful and earn money
that is the goal"

The world: the detectors' own loud-base 🎾 (test_gajjala_detectors.py — base bar 0.51× the squeeze-back run → 🚩 reads
it "partial", missed == ["k3_vol"]) restamped so the break bar is an in-window 10:40 bar. 🚩's read comes from
`D.read_all` WITH K11 in ctx (the live pass). Pins: the K3S re-read goes through the SAME refusal → judge(admit) → T1 →
shadow claim / #held chain as a 🚩 A+, on 🚩's OWN plan; K11 is re-applied with the pass's own volume, fail-closed [C1];
the break pass only [C2]; one first-wins `#partial_break` marker per 🎾 partial break [C5]; durable per-session counts;
T4's session count ignores admitted markers. NEGATIVES throughout: under the K11 floor / no volume / no float / one bar
later / not a 🎾 / K3S OFF / push_dry → nothing rings; the sender is never called; the marker is never a row.
"""
from __future__ import annotations

import copy
import dataclasses
from datetime import datetime

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import audited_pass as AP
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_audited_pass import GGA_OWN, STRIP_OK, _aplus, _Fr, _ok_audit, _reads, _scenario_one_pass
from tests.test_gajjala_run import S, at
from tests.test_gajjala_store import FakeColl, fake_store

SQ = "reversal_squeeze"
SYM = "SQZ"
BAR = "2026-10-13 10:40"
NOW = at(10, 41)
FLOOR = GC.K11_MIN_SESSION_VOLUME
FLOAT = FX.float_read(5_000_000)
LOUD = FX.rs_replace(r11=(6.1875, 6.21875, 6.125, 6.15625, 0.51 * FX.RS_BARS[10][4]))   # detectors test :847
CALM = FX.rs_replace(r3=(5.875, 5.875, 5.75, 5.8125, 100_000), r4=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                     r5=(5.8125, 5.84375, 5.75, 5.8125, 100_000), r6=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                     r7=(5.8125, 5.84375, 5.75, 5.8125, 100_000))                           # detectors test :825
CALM_LOUD = FX.rs_replace(CALM, r11=LOUD[11])                    # two misses: k8_failed AND k3_vol (placebo (a))
AFTER = (6.4375, 6.5, 6.375, 6.45, 300_000)                     # one bar after the break


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def _restamp(F, last: str):
    fmt = "%Y-%m-%d %H:%M"
    shift = datetime.strptime(last, fmt) - datetime.strptime(F.t[-1], fmt)
    return dataclasses.replace(F, t=[(datetime.strptime(x, fmt) + shift).strftime(fmt) for x in F.t])


class _Frames:
    """A Frames stand-in: `.frame(tf)` → the one 5-minute Frame; `as_of_bar_t` = its latest closed bar."""

    def __init__(self, F):
        self.F = F
        self.as_of_bar_t = {"5m": F.t[-1], "15m": None}

    def frame(self, tf):
        return self.F


def _world(bars=LOUD, last=BAR, after=None, vol=FLOOR):
    """-> (frames_obj, 🚩's stored 🎾 read) — the read as the live pass makes it (read_all with K11 in ctx)."""
    F = _restamp(FX.rs_frame(bars, after=after), last)
    r = D.read_all({"5m": F, "15m": None}, {"symbol": SYM, "float_read": FLOAT, D.K11_CTX_KEY: vol})[SQ]
    return _Frames(F), r


def gga_store():
    return ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=fake_store())


def _pass_judge(monkeypatch):
    """The REAL judge (it sets `admit`), every rule then forced passed — T1 is still judged by the step."""
    real = AUD.judge

    def j(r, F, fz=None, **kw):
        a = real(r, F, fz, **kw)
        return dict(a, aplus=True, failed=[], passed=list(a["rules"]))
    monkeypatch.setattr(AUD, "judge", j)


def _step(gga, reads, frames, *, now=NOW, floats=None, sv=None, push_dry=False, strip=STRIP_OK, spy=None):
    sent: list = []
    real_send = AP.refuse_send
    AP.refuse_send = lambda owner, payload: sent.append(payload) or real_send(owner, payload)
    try:
        real_rp = AL.run_pass

        def rp(rs, *a, **k):
            if spy is not None:
                spy.append(copy.deepcopy(rs))
            return real_rp(rs, *a, **k)
        AL.run_pass = rp
        try:
            out = AP.run_step(gga.shared, gga, reads, frames, now, S, alert_ctx={}, owner="o", dry=False,
                              push_dry=push_dry, strip=strip, floats=floats, session_volume=sv)
        finally:
            AL.run_pass = real_rp
    finally:
        AP.refuse_send = real_send
    latest = gga.get_state(AP.LATEST_ID)
    assert latest["ok"] is True, latest
    assert sent == []                                                   # NEGATIVE: the sender is never called
    return out, latest


def _docs(gga) -> dict:
    return gga.coll(ST.ALERTS).docs


def _claims(gga) -> dict:
    return {k: v for k, v in _docs(gga).items() if k.startswith("SHADOW:GGA:")}


def _held(gga) -> dict:
    return {k: v for k, v in _docs(gga).items() if k.endswith(f"#{AUD.HELD_ROW_STATE}")}


def _marks(gga) -> dict:
    return {k: v for k, v in _docs(gga).items() if k.endswith(f"#{AUD.K3S_PARTIAL_ROW_STATE}")}


MARK_ID = f"{AL.claim_key(S, SYM, SQ, V.GGA)}#{AUD.K3S_PARTIAL_ROW_STATE}"
CLAIM_ID = AL.shadow_key(S, SYM, SQ, V.GGA)


# ── the precondition is the detectors' own ──────────────────────────────────────────────────────────────────────
def test_the_world_is_a_k3s_candidate_on_its_break_bar():
    fr, r = _world()
    assert r["state"] == "partial" and r["missed"] == ["k3_vol"] and r["bars_since_entry"] == 0
    assert r["entry_bar_t"] == BAR and AUD.k3s_candidate(dict(r, setup=SQ))
    assert D.K11_KEY not in [c["key"] for c in r["criteria"]]          # C1: a partial read never carries K11
    assert AUD.k3s_on()


def test_k3s_read_keeps_the_plan_and_re_applies_k11_with_the_pass_volume():
    fr, r = _world()
    r2 = AP.k3s_read(fr, r, FLOAT, FLOOR)
    assert r2["state"] == "aplus"
    for k in ("trigger", "stop", "risk_pct", "entry_bar_t"):
        assert r2[k] == r[k], k
    assert r2["bars_since_entry"] == 0 and "k3_vol" in r2["missed"]
    crit = {c["key"]: c for c in r2["criteria"]}
    assert crit["k3_vol"]["ok"] is False                                # the K3 row stays visible ✗
    assert crit[D.K11_KEY]["ok"] is True                                # C1: K11 PRESENT and passed at the floor
    assert r["state"] == "partial"                                      # NEGATIVE: the stored 🚩 read is untouched


@pytest.mark.parametrize("vol", [FLOOR - 1, None])
def test_k3s_read_under_the_floor_or_unknown_is_partial_on_k11(vol):
    fr, r = _world()
    r2 = AP.k3s_read(fr, r, FLOAT, vol)
    assert r2["state"] == "partial" and D.K11_KEY in r2["missed"]       # NEGATIVE: fail-closed, never a skip


def test_k3s_read_source_applies_k11_gate():
    import inspect
    src = inspect.getsource(AP.k3s_read)
    assert "k11_gate" in src and "k3_binding=False" in src


# ── the K3S ring ────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_k3s_candidate_rings_in_shadow_on_the_partial_reads_own_plan(monkeypatch):
    _pass_judge(monkeypatch)
    fr, r = _world()
    gga = gga_store()
    seen: list = []
    out, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR}, spy=seen)
    claim = _claims(gga)[CLAIM_ID]
    assert claim["trigger"] == r["trigger"] and claim["stop"] == r["stop"]
    assert claim["audit"]["admit"] == "K3S"
    assert set(claim["audit"]) == {"passed", "failed", "values", "version", "frame", "rules", "admit"}
    rung = seen[0][SYM][SQ]                                             # what alerts.run_pass was handed
    assert rung["state"] == "aplus" and {c["key"]: c["ok"] for c in rung["criteria"]}[D.K11_KEY] is True
    ov = gga.get_overlay(S, SYM)["setups"][SQ]
    assert ov["admit"] == "K3S" and ov["aplus"] is True and ov["trigger"] == r["trigger"]
    assert latest["k3s"] == {"candidates": 1, "rang": 1, "held": 0, "not_aplus": 0, "k11_refused": 0,
                             "unjudged": {}}
    assert latest["k3s_session"] == {"candidates": 1, "placebo_a": 0, "rang": 1, "held": 0, "k11_refused": 0,
                                     "read_fault": False}
    assert latest["n_aplus_original"] == 0 and out["aplus_original"] == 0     # NEGATIVE: never a 🚩 A+
    assert latest["n_aplus_audited"] == 1 and _held(gga) == {}
    marks = _marks(gga)
    assert list(marks) == [MARK_ID] and MARK_ID == f"GGA:{S.isoformat()}|{SYM}|{SQ}#partial_break"
    m = marks[MARK_ID]
    assert m["missed"] == ["k3_vol"] and m["k3s"] is True and m["k3s_result"] == "rang"
    assert m["session_volume"] == FLOOR and m["state"] == AUD.K3S_PARTIAL_ROW_STATE and m["mode"] == "shadow"
    assert m["trigger"] == r["trigger"] and m["stop"] == r["stop"] and m["entry_bar_t"] == BAR
    assert "push" not in m and "kind" not in m                          # NEGATIVE: never a push, never a claim


def test_the_real_judge_admits_with_the_admit_text_or_holds_never_both(monkeypatch):
    fr, r = _world()
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    ov = gga.get_overlay(S, SYM)["setups"][SQ]
    assert ov["admit"] == "K3S" and ov["original_aplus"] is False and D.NOT_APLUS_REASON in ov["text"]
    k = latest["k3s"]
    assert k["candidates"] == 1 and k["rang"] + k["held"] == 1
    if ov["aplus"]:
        assert CLAIM_ID in _claims(gga) and _held(gga) == {}
    else:
        assert CLAIM_ID not in _claims(gga) and len(_held(gga)) == 1


def test_a_k3s_read_held_by_h1_writes_one_held_marker_and_no_claim(monkeypatch):
    fr, r = _world(last="2026-10-13 16:05")
    real = AUD.judge

    def j(rr, F, fz=None, **kw):                                        # every rule but H1 forced passed
        a = real(rr, F, fz, **kw)
        h1 = [f for f in a["failed"] if f["id"] == "H1"]
        assert h1, a["failed"]                                          # H1 holds an after-hours bar (RTH only)
        return dict(a, aplus=False, failed=h1, passed=[i for i in a["rules"] if i != "H1"])
    monkeypatch.setattr(AUD, "judge", j)
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, now=at(16, 6), floats={SYM: FLOAT}, sv={SYM: FLOOR})
    held = _held(gga)
    assert len(held) == 1
    row = next(iter(held.values()))
    assert row["audit"]["admit"] == "K3S" and [f["id"] for f in row["audit"]["failed"]] == ["H1"]
    assert row["trigger"] == r["trigger"] and row["stop"] == r["stop"]
    assert _claims(gga) == {}                                           # NEGATIVE: a held admit never rings
    assert latest["k3s"]["held"] == 1 and latest["k3s"]["rang"] == 0
    assert latest["held"] == [{"symbol": SYM, "setup": SQ, "failed": ["H1"], "admit": "K3S"}]
    assert _marks(gga)[MARK_ID]["k3s_result"] == "held"
    assert latest["k3s_session"]["held"] == 1 and latest["k3s_session"]["rang"] == 0
    assert latest["t4_session"] == {"fired": 0, "fired_alone": 0}       # T4's count = 🚩 bars only


def test_t1_cap_reached_holds_the_k3s_candidate_after_two_aplus_today(monkeypatch):
    real = AUD.judge
    monkeypatch.setattr(AUD, "judge", lambda rr, F, fz=None, **kw: _ok_audit(rr.get("frame") or "5m"))
    gga = gga_store()
    pre = _reads(("AAA", _aplus(bar="2026-10-13 10:35")), ("BBB", _aplus(bar="2026-10-13 10:35")))
    AP.run_step(gga.shared, gga, pre, {s: _Fr("2026-10-13 10:35") for s in pre}, at(10, 36), S, alert_ctx={},
                owner="o", dry=False, push_dry=False, strip=STRIP_OK)
    assert len(_claims(gga)) == 2 == AUD.T1_DAILY_CAP
    monkeypatch.setattr(AUD, "judge", real)
    _pass_judge(monkeypatch)
    fr, r = _world()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    ov = gga.get_overlay(S, SYM)["setups"][SQ]
    assert ov["aplus"] is False and [f["id"] for f in ov["failed"]] == ["T1"] and ov["admit"] == "K3S"
    assert CLAIM_ID not in _claims(gga) and latest["k3s"]["held"] == 1
    assert _marks(gga)[MARK_ID]["k3s_result"] == "held"


def test_wants_overlay_for_the_candidate_and_for_a_partial_on_another_rule():
    _f, r = _world()
    _f2, rb = _world(bars=CALM_LOUD)
    _f3, r1 = _world(after=[AFTER])
    assert AP.wants_overlay({SQ: r}) is True
    assert rb["missed"] == ["k8_failed", "k3_vol"] and AP.wants_overlay({SQ: rb}) is True
    assert r1["bars_since_entry"] == 1 and AP.wants_overlay({SQ: r1}) is False     # NEGATIVE [C2]
    assert AP.wants_overlay({"bull_flag": dict(r, setup="bull_flag")}) is False   # NEGATIVE: not a 🎾


def test_a_partial_on_another_rule_leaves_a_placebo_marker_and_no_candidate(monkeypatch):
    calls: list = []
    real = D.reversal_squeeze
    monkeypatch.setattr(D, "reversal_squeeze", lambda *a, **k: calls.append(k) or real(*a, **k))
    fr, rb = _world(bars=CALM_LOUD)
    calls.clear()
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: rb}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    m = _marks(gga)[MARK_ID]
    assert m["k3s"] is False and m["k3s_result"] is None and m["missed"] == ["k8_failed", "k3_vol"]
    assert latest["k3s"]["candidates"] == 0 and latest["k3s_session"]["placebo_a"] == 1
    assert latest["k3s_session"]["candidates"] == 0
    assert calls == [] and _claims(gga) == {} and _held(gga) == {}     # NEGATIVE: never re-read, never rings


def test_t4_session_ignores_an_admitted_held_marker():
    gga = gga_store()
    coll = gga.alerts_coll()
    base = {"date": S.isoformat(), "state": AUD.HELD_ROW_STATE, "setup": "bull_flag"}
    coll.update_one({"_id": "a#held"}, {"$set": dict(base, symbol="AAA", audit={"failed": [{"id": "T4"}]})},
                    upsert=True)
    coll.update_one({"_id": "b#held"}, {"$set": dict(base, symbol="BBB",
                                                     audit={"failed": [{"id": "T4"}], "admit": "K3S"})}, upsert=True)
    assert AP.t4_session(gga, S) == {"fired": 1, "fired_alone": 1}


# ── NEGATIVES ───────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sv", [{SYM: FLOOR - 1}, None, {}])
def test_under_the_k11_floor_or_no_volume_is_refused_by_k11_and_never_rings(monkeypatch, sv):
    _pass_judge(monkeypatch)
    fr, r = _world()
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv=sv)
    assert latest["k3s"]["k11_refused"] == 1 and latest["k3s"]["candidates"] == 1
    assert latest["k3s"]["rang"] == latest["k3s"]["held"] == 0
    assert _claims(gga) == {} and _held(gga) == {}
    assert _marks(gga)[MARK_ID]["k3s_result"] == "k11"
    assert latest["k3s_session"]["k11_refused"] == 1
    assert gga.get_overlay(S, SYM) is None or gga.get_overlay(S, SYM)["setups"] == {}


def test_no_float_reads_not_aplus_and_never_rings(monkeypatch):
    _pass_judge(monkeypatch)
    fr, r = _world()
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats=None, sv={SYM: FLOOR})
    assert latest["k3s"]["not_aplus"] == 1 and latest["k3s"]["k11_refused"] == 0
    assert _claims(gga) == {} and _held(gga) == {}
    m = _marks(gga)[MARK_ID]
    assert m["k3s_result"] == "not_aplus" and not m["_id"].startswith("SHADOW:")     # a marker is never a claim


def test_one_bar_after_the_break_is_no_candidate_no_marker_no_re_read(monkeypatch):
    calls: list = []
    real = D.reversal_squeeze
    monkeypatch.setattr(D, "reversal_squeeze", lambda *a, **k: calls.append(k) or real(*a, **k))
    fr, r1 = _world(after=[AFTER], last="2026-10-13 10:45")
    assert r1["state"] == "partial" and r1["missed"] == ["k3_vol"] and r1["bars_since_entry"] == 1
    calls.clear()
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: r1}}, {SYM: fr}, now=at(10, 46), floats={SYM: FLOAT}, sv={SYM: FLOOR})
    assert latest["k3s"]["candidates"] == 0 and _marks(gga) == {} and _claims(gga) == {}
    assert not [k for k in calls if k.get("k3_binding") is False]       # [C2] never re-read


def test_a_non_squeeze_partial_is_never_a_candidate_or_a_marker(monkeypatch):
    _f, r = _world()
    bf = dict(r, setup="bull_flag")
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {"bull_flag": bf}}, {SYM: _f}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    assert latest["k3s"]["candidates"] == 0 and _docs(gga) == {}


def test_k3s_off_judges_nothing_and_writes_no_marker(monkeypatch):
    off = dataclasses.replace(AUD.K3S, status=AUD.STATUS_OFF)
    monkeypatch.setattr(AUD, "REGISTRY", tuple(off if x.id == "K3S" else x for x in AUD.REGISTRY))
    monkeypatch.setattr(AUD, "K3S", off)
    assert AUD.k3s_on() is False
    calls: list = []
    monkeypatch.setattr(AUD, "judge", lambda *a, **k: calls.append(k) or _ok_audit())
    fr, r = _world()
    assert AP.wants_overlay({SQ: r}) is False
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    assert calls == [] and _docs(gga) == {}
    assert latest["k3s"]["candidates"] == 0 and latest["k3s_session"]["candidates"] == 0


def test_the_push_mode_and_the_keep_set_never_move(monkeypatch):
    from push import subs
    before = GC.GAJJALA_AUDITED_PUSH_MODE
    _pass_judge(monkeypatch)
    fr, r = _world()
    _step(gga_store(), {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    assert GC.GAJJALA_AUDITED_PUSH_MODE == before == "shadow"
    assert len(subs.OWNER_KEEP_SET) == 7


def test_claimed_before_is_unjudged_and_the_marker_says_so(monkeypatch):
    calls: list = []
    real = AUD.judge
    monkeypatch.setattr(AUD, "judge", lambda *a, **k: calls.append(k) or real(*a, **k))
    gga = gga_store()
    gga.alerts_coll().update_one({"_id": CLAIM_ID}, {"$set": {"state": "shadow", "date": S.isoformat(),
                                                              "symbol": SYM, "setup": SQ}}, upsert=True)
    fr, r = _world()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    assert latest["k3s"]["unjudged"] == {"claimed_before": 1} and calls == []
    assert _marks(gga)[MARK_ID]["k3s_result"] == "unjudged:claimed_before"
    assert latest["n_unjudged"] == {}                                   # 🚩's own unjudged count is 🚩 A+ only


def test_the_marker_is_first_wins_across_a_repeated_pass(monkeypatch):
    _pass_judge(monkeypatch)
    fr, r = _world()
    gga = gga_store()
    _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR})
    first = copy.deepcopy(_marks(gga)[MARK_ID])
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, now=at(10, 42), floats={SYM: FLOAT}, sv={SYM: FLOOR - 1})
    assert _marks(gga)[MARK_ID] == first and first["k3s_result"] == "rang"
    assert latest["k3s_session"]["candidates"] == 1 and latest["k3s_session"]["rang"] == 1    # durable, no double


def test_the_marker_is_never_a_row_and_only_its_own_reader_sees_it(monkeypatch):
    _pass_judge(monkeypatch)
    fr, r = _world()
    gga = gga_store()
    _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR - 1})
    m = _marks(gga)[MARK_ID]
    assert LG.alert_of(m, LG.KINDS[1], variant=V.GGA) is None and LG.alert_of(m, LG.KINDS[0], variant=V.GGA) is None
    assert AP.session_claims(gga, S) == (set(), False)
    assert gga.held_rows([S]) == [] and gga.alert_rows([S]) == []
    assert [d["_id"] for d in gga.k3s_partial_rows([S])] == [MARK_ID]
    assert AUD.K3S_PARTIAL_ROW_STATE not in ST.LEDGER_ALERT_STATES and AUD.K3S_PARTIAL_ROW_STATE != AUD.HELD_ROW_STATE


def test_k3s_partial_rows_is_none_on_a_fault_and_the_session_says_read_fault():
    gga = gga_store()
    gga.k3s_partial_rows = lambda sessions: None
    assert AP.k3s_session(gga, S) == {"candidates": None, "placebo_a": None, "rang": 0, "held": 0,
                                      "k11_refused": None, "read_fault": True}
    assert ST.GajjalaStore(colls={}, variant=V.GGA).k3s_partial_rows([S]) is None


def test_push_dry_writes_no_marker_and_no_claim(monkeypatch):
    _pass_judge(monkeypatch)
    fr, r = _world()
    gga = gga_store()
    _o, latest = _step(gga, {SYM: {SQ: r}}, {SYM: fr}, floats={SYM: FLOAT}, sv={SYM: FLOOR}, push_dry=True)
    assert _docs(gga) == {}
    assert latest["k3s"]["candidates"] == 1 and latest["k3s_session"]["candidates"] == 0


def test_an_old_caller_without_the_kwargs_never_rings(monkeypatch):
    _pass_judge(monkeypatch)
    fr, r = _world()
    gga = gga_store()
    AP.run_step(gga.shared, gga, {SYM: {SQ: r}}, {SYM: fr}, NOW, S, alert_ctx={}, owner="o", dry=False,
                push_dry=False, strip=STRIP_OK)
    latest = gga.get_state(AP.LATEST_ID)
    assert latest["ok"] is True and latest["k3s"]["rang"] == 0 and _claims(gga) == {}
    assert latest["k3s"]["not_aplus"] + latest["k3s"]["k11_refused"] == 1


def test_run_pass_hands_the_floats_and_the_session_volume_to_the_step(monkeypatch):
    seen: list = []
    real = AP.run_step

    def spy(*a, **k):
        seen.append({n: copy.deepcopy(k.get(n)) for n in ("floats", "session_volume")})
        return real(*a, **k)
    monkeypatch.setattr(AP, "run_step", spy)
    _st, gga, _d, _o = _scenario_one_pass(monkeypatch)
    assert len(seen) == 1 and isinstance(seen[0]["floats"], dict) and isinstance(seen[0]["session_volume"], dict)
    assert "GGA" in seen[0]["session_volume"] and seen[0]["session_volume"]["GGA"] is not None
    latest = gga.get_state(AP.LATEST_ID)
    assert {"k3s", "k3s_session"} <= set(latest) and latest["k3s"]["candidates"] == 0
