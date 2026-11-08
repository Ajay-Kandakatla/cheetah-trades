"""🎾 Reversal Squeeze — the stored `structure` display stamps (2026-11-08, WP be-structure).

Ajay 2026-11-08: "I need something like this but that big of circle for reversal squeen mainly on the cart itself also
increase the width of the reversal sqeeze chart to show more bars" (GG's own annotated TPST chart attached).

`read["structure"]` = {tennis, run, base, attempts} boxes ({from_t, to_t, lo, hi, bars}) set in
`detectors.reversal_squeeze` right after `r["base"]`; read by no rule. `_paired` became `bool(_pairs(...))` — the
identity of that refactor is pinned here under both K8_FAIL_EVENT_RULE values.

Hermetic: pure detector calls on tests/fixtures/gajjala/detector_frames.py; no Mongo, no network, no clock.
Stamps are typed as literals (never `F.t[9]` — that is a prior-day warm-up bar).
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from tests.fixtures.gajjala import detector_frames as FX

SRC = pathlib.Path(D.__file__)
FR = FX.float_read(5_000_000)
BOX_KEYS = {"from_t", "to_t", "lo", "hi", "bars"}
STRUCTURE_KEYS = {"tennis", "run", "base", "attempts"}


def _rs(F=None, float_read=FR):
    return D.reversal_squeeze(F if F is not None else FX.rs_frame(), float_read=float_read)


def _old_paired(tb, attempts):
    """The pre-2026-11-08 `_paired` body, verbatim — the reference for the refactor identity."""
    r, _, k = tb
    if any(f < r for _, f in attempts):
        return True
    return GC.K8_FAIL_EVENT_RULE == "same_ok" and any(a <= r and f <= k for a, f in attempts)


CALM = FX.rs_replace(r3=(5.875, 5.875, 5.75, 5.8125, 100_000), r4=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                     r5=(5.8125, 5.84375, 5.75, 5.8125, 100_000), r6=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                     r7=(5.8125, 5.84375, 5.75, 5.8125, 100_000))
DEEP = FX.rs_replace(r12=(6.15625, 6.1875, 6.0, 6.125, 50_000))
LOUD = FX.rs_replace(r11=(6.1875, 6.21875, 6.125, 6.15625, 0.51 * FX.RS_BARS[10][4]))
UP = FX.rs_replace(r11=(6.1875, 6.3125, 6.15625, 6.28125, 60_000))
SLOW = FX.rs_replace(r10=(5.75, 6.0, 5.75, 5.875, 400_000), r11=(5.875, 6.0, 5.8125, 5.9375, 60_000),
                     r12=(5.9375, 6.0625, 5.875, 6.0, 50_000))
SNES = [(5.0, 5.125, 4.875, 5.0, 100_000), (5.0, 8.0, 5.0, 7.75, 3_000_000), (7.75, 7.75, 6.5, 6.6, 2_000_000),
        (6.6, 6.7, 5.75, 5.8, 1_500_000), (5.8, 6.0, 5.5, 5.6, 900_000), (5.6, 5.75, 5.25, 5.3, 600_000)]
SASI = [(8.0 - 0.125 * i, 8.0625 - 0.125 * i, 7.875 - 0.125 * i, 7.875 - 0.125 * i, 300_000) for i in range(14)]
SGD = [(3.0, 3.0625, 2.96875, 3.0, 100_000), (3.0, 4.0, 3.0, 3.9375, 2_000_000)] + [
    (3.9375 - 0.0625 * i, 3.96875 - 0.0625 * i, 3.875 - 0.0625 * i, 3.875 - 0.0625 * i, 80_000) for i in range(12)]
GREEN = [(5.0, 5.125, 4.875, 5.0, 100_000), (5.0, 5.5, 5.0, 5.5, 900_000)] + [FX.quiet(5.5)] * 3


def _frames():
    """Every 🎾 fixture of test_gajjala_detectors.py (A+, triggered, stopped, forming, forming-empty-base, partial K8,
    partial K3 vol, the moved top, S8 36:12, the 7.99% drop, the 4th-bar recovery, SNES, SASI, SGD, the wide green
    bar, the K3-depth shape)."""
    return {
        "aplus": FX.rs_frame(),
        "triggered": FX.rs_frame(after=[(6.4, 6.6, 6.3, 6.5, 300_000)] * 3),
        "stopped": FX.rs_frame(after=[(6.4, 6.4, 6.0, 6.05, 300_000)]),
        "forming": FX.rs_frame(entry=None),
        "forming_empty": FX.rs_frame(FX.RS_BARS[:11], entry=None),
        "partial_k8": FX.rs_frame(CALM),
        "partial_k3": FX.rs_frame(LOUD),
        "moved_top": FX.rs_frame(UP[:12], entry=None),
        "s8": FX.rs_frame(FX.RS_S8_BARS, entry=FX.RS_S8_E),
        "drop_799": FX.rs_frame(FX.rs_replace(r9=(6.1875, 6.25, 6.25 * (1 - 0.0799), 5.8, 500_000))),
        "slow": FX.rs_frame(SLOW, entry=(6.0, 6.25, 6.0, 6.1875, 400_000)),
        "snes": FX.rs_frame(SNES, entry=None),
        "sasi": FX.rs_frame(SASI, entry=None),
        "sgd": FX.rs_frame(SGD, entry=None),
        "green": FX.rs_frame(GREEN, entry=None),
        "deep": FX.rs_frame(DEEP),
    }


# ── RS_BARS A+ — the literal stamps ───────────────────────────────────────────────────────────────────────────
def test_rs_bars_aplus_structure_literal_stamps():
    F = FX.rs_frame()
    T = F.today.start
    assert T == 20 and len(F.t) == 34
    last = len(F.t) - 1
    assert D.tennis_balls(F, last) == [(T + 8, T + 9, T + 10)]
    assert D.failed_attempts(F, last) == [(T + 3, T + 4)]
    r = _rs(F)
    assert r["state"] == "aplus" and r["entry_bar_t"] == "2026-10-13 05:10"
    s = r["structure"]
    assert set(s) == STRUCTURE_KEYS
    assert s["tennis"] == {"from_t": "2026-10-13 04:50", "to_t": "2026-10-13 04:55", "lo": 5.6875, "hi": 6.25,
                           "bars": 2}
    assert (s["tennis"]["from_t"], s["tennis"]["to_t"]) == (F.t[T + 9], F.t[T + 10])
    assert s["run"] == {"from_t": "2026-10-13 04:55", "to_t": "2026-10-13 04:55", "lo": 5.8125, "hi": 6.25,
                        "bars": 1}
    assert r["leg"]["bars"] == 1                                         # R = [p], p == d + 1
    assert s["base"] == {"from_t": "2026-10-13 05:00", "to_t": "2026-10-13 05:05", "lo": 6.09375, "hi": 6.21875,
                         "bars": 2}
    assert s["base"]["lo"] == r["stop"] == 6.09375
    assert (s["base"]["from_t"], s["base"]["to_t"], s["base"]["bars"]) == (
        r["base"]["from_t"], r["base"]["to_t"], r["base"]["bars"])       # the box is _span + lo/hi
    assert s["attempts"] == [{"from_t": "2026-10-13 04:20", "to_t": "2026-10-13 04:25", "lo": 5.375,
                              "hi": 5.96875, "bars": 2}]


def test_the_stamps_are_not_the_prior_day_warm_up_bar():
    """NEGATIVE: index 9 of the frame is a prior-day warm-up stamp, never a structure stamp."""
    F = FX.rs_frame()
    assert F.t[9] == "2026-10-12 15:50"
    stamps = _stamps(_rs(F)["structure"])
    assert F.t[9] not in stamps and all(t.startswith("2026-10-13") for t in stamps)


# ── states: present on every read that found a tennis ball ────────────────────────────────────────────────────
@pytest.mark.parametrize("kind,state", [("aplus", "aplus"), ("triggered", "triggered"), ("stopped", "stopped"),
                                        ("forming", "forming"), ("forming_empty", "forming"),
                                        ("partial_k8", "partial"), ("partial_k3", "partial"),
                                        ("moved_top", "forming")])
def test_structure_present_on_every_tennis_ball_state(kind, state):
    r = _rs(_frames()[kind])
    assert r["state"] == state
    assert set(r["structure"]) == STRUCTURE_KEYS
    assert set(r["structure"]["tennis"]) == BOX_KEYS and set(r["structure"]["run"]) == BOX_KEYS


def test_forming_read_has_base_and_no_entry():
    r = _rs(FX.rs_frame(entry=None))
    assert r["state"] == "forming" and r["entry_bar_t"] is None
    assert r["structure"]["base"] == {"from_t": "2026-10-13 05:00", "to_t": "2026-10-13 05:05", "lo": 6.09375,
                                      "hi": 6.21875, "bars": 2}


def test_forming_read_with_an_empty_base_has_base_none():
    """p == last (the squeeze-back bar is the latest closed bar) → B empty → structure.base None, stop None."""
    r = _rs(FX.rs_frame(FX.RS_BARS[:11], entry=None))
    assert r["state"] == "forming" and r["base"] is None and r["stop"] is None
    assert r["structure"]["base"] is None
    assert r["structure"]["tennis"]["to_t"] == "2026-10-13 04:55"


def test_partial_without_a_failed_attempt_draws_no_attempt():
    r = _rs(FX.rs_frame(CALM))
    assert r["state"] == "partial" and r["missed"] == ["k8_failed"]
    assert r["structure"]["attempts"] == []


def test_k3_depth_invalid_read_still_carries_structure(monkeypatch):
    """[C6] `_invalid` runs after r["base"]: the K3-depth invalid read carries the stamps (never carded — tab
    TILE_STATES has no `invalid`). Pinned, not special-cased."""
    monkeypatch.setattr(GC, "K3_DEPTH_SETUPS", GC.K3_DEPTH_SETUPS + ("reversal_squeeze",))
    r = _rs(FX.rs_frame(DEEP))
    assert r["state"] == "invalid" and r["reason"] == "base sank below half the top bar"
    s = r["structure"]
    assert s["tennis"]["from_t"] == "2026-10-13 04:50" and s["run"]["to_t"] == "2026-10-13 04:55"
    assert s["base"] == {"from_t": "2026-10-13 05:00", "to_t": "2026-10-13 05:05", "lo": 6.0, "hi": 6.21875,
                         "bars": 2}


# ── the _pairs refactor: identity under both K8_FAIL_EVENT_RULE values ────────────────────────────────────────
@pytest.mark.parametrize("rule", ["distinct", "same_ok"])
def test_paired_is_bool_of_pairs_on_every_fixture(monkeypatch, rule):
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", rule)
    checked = 0
    for F in _frames().values():
        last = len(F.t) - 1
        attempts = D.failed_attempts(F, last)
        for tb in D.tennis_balls(F, last):
            pairs = D._pairs(tb, attempts)
            assert D._paired(tb, attempts) == bool(pairs) == _old_paired(tb, attempts)
            assert set(pairs) <= set(attempts)
            checked += 1
    assert checked >= 10


@pytest.mark.parametrize("rule", ["distinct", "same_ok"])
def test_pairs_truth_table_on_synthetic_spans(monkeypatch, rule):
    """Every (a, f) placement around tb = (r=5, d=6, k=7): the list is exactly the attempts the old predicate counts."""
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", rule)
    tb = (5, 6, 7)
    for a in range(9):
        for f in range(a + 1, 10):
            assert bool(D._pairs(tb, [(a, f)])) == _old_paired(tb, [(a, f)])
            assert D._pairs(tb, [(a, f)]) in ([], [(a, f)])


def test_s8_attempts_follow_the_rule(monkeypatch):
    """RS_S8_BARS (a = r): under "distinct" the try does not pair → no attempt drawn, partial; under "same_ok" it
    pairs → drawn, aplus."""
    F = FX.rs_frame(FX.RS_S8_BARS, entry=FX.RS_S8_E)
    T = F.today.start
    last = len(F.t) - 1
    assert D.tennis_balls(F, last) == [(T + 4, T + 5, T + 6)] and D.failed_attempts(F, last) == [(T + 4, T + 5)]
    r = _rs(F)
    assert r["state"] == "partial" and r["structure"]["attempts"] == []
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", "same_ok")
    r = _rs(F)
    assert r["state"] == "aplus"
    assert r["structure"]["attempts"] == [{"from_t": "2026-10-13 04:25", "to_t": "2026-10-13 04:30", "lo": 5.5,
                                           "hi": 6.125, "bars": 2}]


@pytest.mark.parametrize("rule", ["distinct", "same_ok"])
def test_read_minus_structure_is_identical_to_the_old_paired(monkeypatch, rule):
    """IDENTITY: every 🎾 fixture read with the old `_paired` body patched in equals today's read minus `structure`."""
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", rule)
    new = {k: _rs(F) for k, F in _frames().items()}
    monkeypatch.setattr(D, "_paired", _old_paired)
    old = {k: _rs(F) for k, F in _frames().items()}
    for k in new:
        a, b = dict(new[k]), dict(old[k])
        a.pop("structure", None)
        b.pop("structure", None)
        assert a == b, k


def test_read_key_set_is_blank_plus_structure():
    blank = set(D._blank("reversal_squeeze", None, -1))
    assert "structure" not in blank
    for k, F in _frames().items():
        r = _rs(F)
        assert set(r) - {"structure"} == blank, k


def test_pinned_values_unchanged():
    """The values test_gajjala_detectors pins on the 🎾 A+ read, re-asserted beside the new key."""
    r = _rs()
    assert (r["state"], r["trigger"], r["stop"]) == ("aplus", 6.25, 6.09375)
    assert r["leg"] == {"s_t": "2026-10-13 04:50", "e_t": "2026-10-13 04:55", "bars": 1}
    assert r["base"] == {"from_t": "2026-10-13 05:00", "to_t": "2026-10-13 05:05", "bars": 2}
    assert {c["key"] for c in r["criteria"]} == {"k8_tennis", "k8_failed", "k3_vol", "k8_base_len"}
    assert next(c for c in r["criteria"] if c["key"] == "k8_tennis")["value"] == "drop 2026-10-13 04:50 · back 2026-10-13 04:55"
    assert r["missed"] == [] and r["red_closes"] == 2                  # two lower closes in the 2-bar base


# ── _merge_spans / _box ────────────────────────────────────────────────────────────────────────────────────────
def test_merge_spans():
    assert D._merge_spans([(3, 4), (4, 6), (8, 9)]) == [(3, 6), (8, 9)]
    assert D._merge_spans([(3, 4), (5, 6)]) == [(3, 6)]                     # touching
    assert D._merge_spans([]) == []
    assert D._merge_spans([(8, 9), (4, 6), (3, 4)]) == [(3, 6), (8, 9)]     # order-insensitive
    assert D._merge_spans([(3, 9), (4, 5)]) == [(3, 9)]                     # contained


def test_merge_spans_keeps_a_gap_apart():
    """NEGATIVE: a one-bar gap (next a = f + 2) is two spans."""
    assert D._merge_spans([(3, 4), (6, 7)]) == [(3, 4), (6, 7)]


def test_box_of_an_empty_span_is_none():
    F = FX.rs_frame()
    assert D._box(F, []) is None and D._box(F, range(5, 5)) is None
    T = F.today.start
    assert D._box(F, [T + 9]) == {"from_t": "2026-10-13 04:50", "to_t": "2026-10-13 04:50", "lo": 5.6875,
                                  "hi": 6.25, "bars": 1}


def _stamps(s: dict) -> list:
    boxes = [s["tennis"], s["run"], s["base"]] + list(s["attempts"])
    return [t for b in boxes if b for t in (b["from_t"], b["to_t"])]


def test_every_structure_stamp_is_a_frame_stamp():
    for k, F in _frames().items():
        r = _rs(F)
        if "structure" in r:
            assert set(_stamps(r["structure"])) <= set(F.t), k


# ── NEGATIVES: absent on none / float-gated / the other four setups ───────────────────────────────────────────
@pytest.mark.parametrize("kind", ["snes", "sasi", "sgd", "drop_799", "slow", "green"])
def test_no_tennis_ball_read_has_no_structure(kind):
    r = _rs(_frames()[kind])
    assert r["state"] == "none" and "structure" not in r


@pytest.mark.parametrize("fr", [None, FX.float_read(None), FX.float_read(GC.K8_MAX_FLOAT + 1),
                                FX.float_read(1_314_047, suspect="float_exceeds_shares_out")])
def test_float_gated_read_drops_structure(fr):
    r = D.reversal_squeeze(FX.rs_frame(), float_read=fr)
    assert r["state"] == "none" and r["meta"]["structure_alive"] is True
    assert "structure" not in r


def test_other_four_setups_carry_no_structure():
    reads = [D.bull_flag(FX.bf_aplus()), D.kiss_fly(FX.kf_frame()), D.fade_on(FX.hf_frame()),
             D.intraday_vcp(FX.vcp_frame())]
    for r in reads:
        assert "structure" not in r, r["setup"]
    out = D.read_all({"5m": FX.rs_frame()}, {"float_read": FR})
    assert set(out) == {"bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze"}
    assert "structure" in out["reversal_squeeze"]
    assert [s for s, r in out.items() if s != "reversal_squeeze" and "structure" in r] == []


def test_no_new_numeric_literal_in_detectors():
    """The literal guard (test_gajjala_detectors :894) stays green with the structure code in."""
    tree = ast.parse(SRC.read_text())
    bad = [(n.lineno, n.value) for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)
           and n.value not in (0, 1, 2, 100)]
    assert bad == []


def test_structure_is_read_by_no_rule():
    """NEGATIVE: `structure` is written once (the read) and never read back inside detectors.py."""
    text = SRC.read_text()
    assert text.count('["structure"]') == 1 and 'r["structure"] = {' in text
    assert '.get("structure")' not in text
