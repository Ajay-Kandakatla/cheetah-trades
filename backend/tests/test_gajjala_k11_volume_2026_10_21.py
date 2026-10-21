"""K11 — today's volume on the A+ claim (2026-10-21, BUILD_SPEC22 Part B).

Ajay 2026-10-21: "keep what ever Gajjala says for these" on "Whether an A+ should also require today's volume to clear
GG's 1M floor (NIXX rang on 288K shares)". GG VR 0.4: "Volume: 1M is a floor … it must SUSTAIN and INCREASE (one 1M bar
then a fade = not interested)".

Pinned here: (1) ONE number — K11_MIN_SESSION_VOLUME IS the scanner floor (an alias, never a second literal); (2) a read
that broke with K1–K10 met is A+ only when the session volume the pass passes in is ≥ the floor; under it the read
takes the K3 path ("broke — not A+", the k11_volume row in `missed`, trigger and stop kept) — no candidate, no claim,
no push, the card prints TRIGGER; (3) FAIL-CLOSED: no figure / a non-number → "today's volume unknown", ok False;
(4) a 🧠 forming potential is never judged (K11 is judged at the ring); (5) a 🏁 claim doc grades as before; (6) the
mutation guard — without the gate the 999,999 read is A+ and rings, so the 999,999 test bites; (7) the run.py seam:
the pass must hand the scanner's session volume to read_all at BOTH call sites (WP-B does not own run.py — this test
waits for that line).
UNMEASURED — his rule applied to the claim, not a measured edge.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import playbook as PB
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import tab as GT
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_alerts import S, at, live, one, shadow   # noqa: F401 — the fixtures ride along
from tests.test_gajjala_store import fake_store

B_WORD = re.compile("b" + "ounc", re.I)
FLOOR = GC.K11_MIN_SESSION_VOLUME
UNDER = FLOOR - 1                                                # 999,999
NOW = at(10, 11)                                                 # 90 s after the bf_aplus entry bar (10:10 ET) closed


def _reads(volume=..., frame=None):
    ctx = {"symbol": "GGA", "float_read": None}
    if volume is not ...:
        ctx[D.K11_CTX_KEY] = volume
    return D.read_all({"5m": frame if frame is not None else FX.bf_aplus(), "15m": None}, ctx)


def _k11(r):
    rows = [c for c in r["criteria"] if c["key"] == D.K11_KEY]
    assert len(rows) <= 1
    return rows[0] if rows else None


# ── (1) one number ───────────────────────────────────────────────────────────────────────────────────────────────
def test_the_floor_is_his_scanner_floor_one_number():
    assert FLOOR == GC.SCAN_MIN_VOLUME == 1_000_000
    src = pathlib.Path(GC.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") ==
                "K11_MIN_SESSION_VOLUME")
    assert isinstance(node.value, ast.Name) and node.value.id == "SCAN_MIN_VOLUME"     # an alias, no literal
    line = src.splitlines()[node.lineno - 1]
    assert "GG VR 0.4" in line and "one 1M bar then a fade = not interested" in line
    assert "Ajay 2026-10-21" in line and "keep what ever Gajjala says" in line and "NIXX rang on 288K shares" in line


def test_NEGATIVE_no_second_volume_literal_in_the_detectors():
    tree = ast.parse(inspect.getsource(D))
    nums = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool) and n.value not in (0, 1, 2, 100)]
    assert nums == []
    assert "GC.K11_MIN_SESSION_VOLUME" in inspect.getsource(D.k11_criterion)


# ── (2) the gate on the read ─────────────────────────────────────────────────────────────────────────────────────
def test_at_the_floor_the_read_is_aplus_with_the_k11_row_met():
    base = _reads()["bull_flag"]
    r = _reads(FLOOR)["bull_flag"]
    assert r["state"] == "aplus" and r["missed"] == []
    row = _k11(r)
    assert row["ok"] is True and row["label"] == "K11 today's volume 1,000,000 ≥ 1,000,000"
    assert (r["trigger"], r["stop"], r["entry_bar_t"]) == (base["trigger"], base["stop"], base["entry_bar_t"])
    assert [c["key"] for c in r["criteria"]] == [c["key"] for c in base["criteria"]] + [D.K11_KEY]


def test_one_share_under_the_floor_is_broke_not_aplus_and_keeps_its_levels():
    base = _reads()["bull_flag"]
    r = _reads(UNDER)["bull_flag"]
    assert base["state"] == "aplus"
    assert r["state"] == "partial" and r["reason"] == D.NOT_APLUS_REASON == "broke — not A+"
    assert r["broke"] is True and r["ready"] is False
    assert (r["trigger"], r["stop"], r["entry_bar_t"], r["leg"], r["base"]) == \
        (base["trigger"], base["stop"], base["entry_bar_t"], base["leg"], base["base"])
    row = _k11(r)
    assert row["ok"] is False and r["missed"] == [D.K11_KEY]
    assert row["label"] == "K11 today's volume 999,999 < 1,000,000 (GG: one 1M bar then a fade = not interested)"
    assert AL._candidates({"GGA": {"bull_flag": r}}) == []


def test_the_nixx_shape_prints_his_words():
    r = _reads(288_000)["bull_flag"]
    assert r["state"] == "partial"
    assert _k11(r)["label"] == "K11 today's volume 288,000 < 1,000,000 (GG: one 1M bar then a fade = not interested)"
    pill = GT.state_label(r)
    assert pill.startswith("broke — not A+ · missed: K11 today's volume 288,000 < 1,000,000 (GG: one 1M bar then a "
                           "fade = not interested)")
    assert "UNMEASURED" in pill and not B_WORD.search(pill)


def test_the_card_prints_trigger_never_buy_under_the_floor():
    under = GT._tile_lines(_reads(UNDER)["bull_flag"])
    met = GT._tile_lines(_reads(FLOOR)["bull_flag"])
    assert under[0]["label"].startswith("TRIGGER ") and under[0]["tone"] == "buy"
    assert met[0]["label"].startswith("BUY > ")
    assert under[1] == met[1] and under[1]["label"].startswith("STOP ")


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -5, "1000000", True, [], {}])
def test_fail_closed_no_figure_is_unknown_never_aplus(bad):
    r = _reads(bad)["bull_flag"]
    row = _k11(r)
    assert r["state"] == "partial" and row["ok"] is False and r["missed"] == [D.K11_KEY]
    assert row["label"] == "K11 today's volume unknown (needs ≥ 1,000,000)" and D.K11_UNKNOWN in row["label"]
    assert r["unjudged"] == []                                   # unknown is a FAILED rule, never "not judgeable"


def test_a_triggered_and_a_stopped_read_are_judged_too():
    trig = FX.frame(FX.bf_bars(after=[FX.quiet(11.25)]))
    assert _reads(frame=trig)["bull_flag"]["state"] == "triggered"
    assert _reads(UNDER, trig)["bull_flag"]["state"] == "partial"
    assert _reads(FLOOR, trig)["bull_flag"]["state"] == "triggered"
    stp = FX.frame(FX.bf_bars(after=[(11.0, 11.0, 10.5, 10.6, 100_000)]))
    assert _reads(frame=stp)["bull_flag"]["state"] == "stopped"
    assert _reads(UNDER, stp)["bull_flag"]["state"] == "partial"
    assert _reads(FLOOR, stp)["bull_flag"]["state"] == "stopped"


def test_every_setup_runs_through_the_one_gate():
    frames = {"5m": FX.kf_frame(), "15m": None}
    k = D.read_all(frames, {"symbol": "GGA", D.K11_CTX_KEY: UNDER})["kiss_fly"]
    assert D.kiss_fly(FX.kf_frame())["state"] == "aplus"
    assert k["state"] == "partial" and k["missed"] == [D.K11_KEY]
    assert D.read_all(frames, {"symbol": "GGA", D.K11_CTX_KEY: FLOOR})["kiss_fly"]["state"] == "aplus"


def test_the_floor_is_read_at_call_time(monkeypatch):
    monkeypatch.setattr(GC, "K11_MIN_SESSION_VOLUME", 2_000_000)
    r = _reads(1_500_000)["bull_flag"]
    assert r["state"] == "partial" and "1,500,000 < 2,000,000" in _k11(r)["label"]


def test_a_second_gate_never_stacks_a_second_row():
    r = D.k11_gate(D.k11_gate(_reads()["bull_flag"], UNDER), UNDER)
    assert [c["key"] for c in r["criteria"]].count(D.K11_KEY) == 1


# ── NEGATIVES: what K11 never touches ────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_forming_potential_with_100k_is_still_a_potential():
    F = FX.frame(FX.bf_bars(entry=None))
    r = _reads(100_000, F)["bull_flag"]
    assert r["state"] == "forming" and _k11(r) is None
    assert PT.potential_kind(r) in GC.POTENTIAL_KINDS
    assert r == _reads(frame=F)["bull_flag"]


def test_NEGATIVE_none_invalid_and_partial_reads_get_no_k11_row():
    for st in ("none", "invalid", "partial", "forming"):
        r = {"state": st, "criteria": [], "reason": "x"}
        assert D.k11_gate(dict(r), UNDER) == r


def test_NEGATIVE_a_caller_without_the_key_reads_k1_to_k10_as_before():
    r = _reads()["bull_flag"]
    assert r["state"] == "aplus" and _k11(r) is None


# ── the claim: no candidate, no claim, no push ───────────────────────────────────────────────────────────────────
def test_under_the_floor_nothing_is_claimed_or_sent(live):
    st = fake_store()
    r = _reads(UNDER)["bull_flag"]
    counts, send = one(st, r, now=NOW)
    assert counts["aplus"] == 0 and counts["pushed"] == 0 and send.calls == []
    assert st.alerts_coll().docs == {}


def test_at_the_floor_it_rings_once_and_the_track_record_row_grades(live):
    st = fake_store()
    counts, send = one(st, _reads(FLOOR)["bull_flag"], now=NOW)
    assert counts["aplus"] == 1 and counts["pushed"] == 1 and len(send.calls) == 1
    doc = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]
    assert doc["state"] == "pushed" and "criteria" not in doc     # the claim never carried criteria — rows unchanged
    row = LG.alert_of(doc, "aplus")
    assert row is not None and row["plan"] == "ok" and row["line"] == "live" and row["r"] > 0


def test_shadow_mode_records_nothing_under_the_floor(shadow):
    st = fake_store()
    counts, send = one(st, _reads(UNDER)["bull_flag"], now=NOW)
    assert counts["shadow"] == 0 and send.calls == [] and st.alerts_coll().docs == {}


def test_MUTATION_without_the_gate_the_999999_read_is_aplus_and_rings(live, monkeypatch):
    """The guard bites: drop K11 from read_all and the 999,999 read is A+ and pushes — so the test above fails."""
    monkeypatch.setattr(D, "k11_gate", lambda r, volume: r)
    r = _reads(UNDER)["bull_flag"]
    assert r["state"] == "aplus"
    counts, send = one(fake_store(), r, now=NOW)
    assert counts["pushed"] == 1 and len(send.calls) == 1


def test_read_all_runs_the_gate_on_every_setup_when_the_key_is_passed():
    src = inspect.getsource(D.read_all)
    assert "K11_CTX_KEY in ctx" in src and "k11_gate(r, vol)" in src
    assert D.K11_STATES == ("aplus", "triggered", "stopped") and D.K11_CTX_KEY == "session_volume"


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_words_are_his_and_the_only_digit_is_in_his_sentence():
    assert D.K11_WHY == "GG: one 1M bar then a fade = not interested"
    assert re.findall(r"\d", D.K11_WHY) == ["1"] and "one 1M bar" in D.K11_WHY
    for s in (D.K11_WHY, D.K11_UNKNOWN, D.NOT_APLUS_REASON):
        assert not B_WORD.search(s)
    assert not any(ch.isdigit() for ch in D.K11_UNKNOWN)


def test_the_playbook_k11_knob_is_built_from_the_constant(monkeypatch):
    k = {r["key"]: r for r in PB.knobs()}
    assert k["K11"]["text"] == "today's volume ≥ 1,000,000 shares at the ring (his scanner floor; 'it must sustain')"
    assert k["K11"]["value"] == PB.AJAY_K11 and "Ajay 2026-10-21" in PB.AJAY_K11
    keys = [r["key"] for r in PB.knobs()]
    assert keys.index("K11") == keys.index("K10") + 1
    monkeypatch.setattr(GC, "K11_MIN_SESSION_VOLUME", 1_500_000)
    assert "1,500,000" in {r["key"]: r for r in PB.knobs()}["K11"]["text"]


# ── (7) the run.py seam (not in WP-B's files) ────────────────────────────────────────────────────────────────────
def test_SEAM_the_pass_hands_the_session_volume_to_both_read_all_calls():
    """run.py must pass `session_volume` (the pass's own scanner row: the qualifier row, else the snapshot row —
    scanner._volume) in the ctx of BOTH deps.read_all calls (the first read and the 🎾 float re-read). Until it does,
    the pass reads K1–K10 only and K11 never fires on the live board."""
    from chart_maps.gajjala import run as RUN
    src = inspect.getsource(RUN.run_pass)
    calls = re.findall(r"deps\.read_all\([^\n]*\n?[^\n]*", src)
    assert len(calls) == 2
    assert all(D.K11_CTX_KEY in c or "K11_CTX_KEY" in c for c in calls), calls


# ── (7b) the run.py seam, end to end (critic 2026-10-21: the pass handed read_all no session volume) ───────────────
def _recording(deps):
    seen = []
    real = deps.read_all

    def rec(frames, ctx):
        seen.append(dict(ctx))
        return real(frames, ctx)
    deps.read_all = rec
    return seen


def test_SEAM_a_qualifier_pass_hands_its_own_scanner_volume_and_still_rings(monkeypatch):
    from tests import test_gajjala_run as TR
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = fake_store()
    deps, _snap, send, _status = TR.make_deps()
    seen = _recording(deps)
    out = TR.RUN.run_pass(TR.NOW, store=st, deps=deps)
    gga = [c for c in seen if c["symbol"] == "GGA"]
    assert gga and all(c[D.K11_CTX_KEY] == 3_000_000 for c in gga)
    assert "GGA:bull_flag" in out["aplus"] and send.calls


def test_SEAM_NEGATIVE_a_carried_name_on_288K_never_reads_aplus(monkeypatch):
    """The NIXX case: listed earlier on a qualifying row, this pass's snapshot says 288K for the session — the read
    gets 288,000 (not the stored qualifying row) and the break is 'broke — not A+'."""
    from datetime import timedelta
    from tests import test_gajjala_run as TR
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = fake_store()
    deps, *_ = TR.make_deps()
    TR.RUN.run_pass(TR.NOW, store=st, deps=deps)                      # GGA qualifies on 3M
    later = TR.NOW + timedelta(seconds=GC.PASS_CADENCE_SEC)
    deps2, _s, send2, _st = TR.make_deps(rows={"GGA": TR.snap_row(11.2, 8.0, vol=288_000, when=later)})
    seen = _recording(deps2)
    out = TR.RUN.run_pass(later, store=st, deps=deps2)
    assert "GGA" not in out["qualifiers"]
    gga = [c for c in seen if c["symbol"] == "GGA"]
    assert gga and all(c[D.K11_CTX_KEY] == 288_000 for c in gga)
    assert not [k for k in out["aplus"] if k.startswith("GGA:")] and send2.calls == []
    bf = st.get_read(TR.S, "GGA")["setups"]["bull_flag"]
    assert bf["state"] != "aplus"
    assert any(c["key"] == D.K11_KEY and c["ok"] is False for c in bf["criteria"])


def test_SEAM_NEGATIVE_a_carried_name_with_no_snapshot_row_fails_closed(monkeypatch):
    """No row for the name this pass → session_volume None (never the stored qualifying row) → K11 unknown."""
    from datetime import timedelta
    from tests import test_gajjala_run as TR
    st = fake_store()
    deps, *_ = TR.make_deps()
    TR.RUN.run_pass(TR.NOW, store=st, deps=deps)
    later = TR.NOW + timedelta(seconds=GC.PASS_CADENCE_SEC)
    deps2, *_ = TR.make_deps(rows={"NOPE": TR.snap_row(1.0, 0.95, when=later)})
    seen = _recording(deps2)
    TR.RUN.run_pass(later, store=st, deps=deps2)
    gga = [c for c in seen if c["symbol"] == "GGA"]
    assert gga and all(D.K11_CTX_KEY in c and c[D.K11_CTX_KEY] is None for c in gga)
