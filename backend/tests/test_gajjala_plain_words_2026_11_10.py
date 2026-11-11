"""🚩 Gajjala rule rows in plain words (K1–K11), 2026-11-10 — WORDING ONLY.

Ajay 2026-11-10: "Also please use common vocabuluary like volume dried: "K3 base volume ≤ 0.5× the squeeze-back run —
max 98933 (≤ 36008)"" and "not jus k3 please up date what he means in simple terms acroos k1 to k10".

The proof that only words moved: `plain_words_stripped_2026_11_10.json` was written on the UNTOUCHED tree (every
detector on every frame below, at every prefix of today, plus the K11 gate variants) with the criteria reduced to
(key, ok) and the reason dropped. The edited tree must reproduce it byte for byte: no state, trigger, stop, missed,
grade, variant, count or key moved. Spec: docs/gajjala/plain_words_2026_11_10.md.

Hermetic: pure detector calls on tests/fixtures/gajjala/detector_frames.py; no Mongo, no network, no clock.
Regenerate the snapshot ONLY on an untouched tree:
GG_WRITE_GOLDEN=1 GG_PLAIN_WORDS_SNAPSHOT=1 pytest tests/test_gajjala_plain_words_2026_11_10.py -k stripped
"""
from __future__ import annotations

import copy
import json
import os
import pathlib

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from tests.fixtures.gajjala import detector_frames as FX

SNAPSHOT = pathlib.Path(__file__).parent / "fixtures" / "gajjala" / "plain_words_stripped_2026_11_10.json"
FR5M = FX.float_read(5_000_000)
BF_AMBIG = (10.875, 11.25, 10.75, 11.2, 250_000)          # the entry bar trades under the stop (P2 low 10.8125)
BF_AMBIG_MIN = {7: [(10.875, 11.25, 10.75, 11.2, 250_000)]}   # ONE minute above the trigger AND under the stop


def _frames() -> dict:
    """Every named frame the snapshot reads (built from the shared fixture module, never retyped shapes)."""
    vcp76 = FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000))
    return {
        "quiet": FX.frame([FX.quiet(10.0)] * 6),
        "bf_aplus": FX.bf_aplus(),
        "bf5": FX.frame(FX.bf_bars(FX.flat_pull(5))),
        "bf6": FX.frame(FX.bf_bars(FX.flat_pull(6))),
        "bf_rkda": FX.frame(FX.bf_bars([(11.0, 11.0, 10.6, 10.9, 100_000), FX.P2])),
        "bf_ocx": FX.frame(FX.bf_bars([FX.P1[:4] + (400_000,), FX.P2[:4] + (300_000,)],
                                      leg=(FX.D1[:4] + (1_000_000,), FX.D2[:4] + (1_200_000,)), entry=FX.BF_E)),
        "bf_heavy": FX.frame(FX.bf_bars([FX.P1[:4] + (130_000,), FX.P2], entry=FX.BF_E)),
        "bf_forming": FX.frame(FX.bf_bars([], entry=None)),
        "bf_ambig_nomin": FX.frame(FX.bf_bars([FX.P1, FX.P2], entry=BF_AMBIG)),
        "bf_ambig_min": FX.frame(FX.bf_bars([FX.P1, FX.P2], entry=BF_AMBIG), minutes=BF_AMBIG_MIN),
        "kf": FX.kf_frame(),
        "kf_honor": FX.kf_frame(honor_fail_at=1),
        "kf_near": FX.kf_near_kiss(),
        "kf_near_eq": FX.kf_near_kiss(allow_touch_close_eq=True),
        "kf_red": FX.kf_frame(5, red=4),
        "kf_doji": FX.kf_frame(5, doji=4),
        "kf_above": FX.kf_frame(kiss_above_pct=0.6, entry=False),
        "kf_e21_over": FX.kf_frame(e21_over=0.0078125, entry=False),
        "kf_long": FX.kf_frame(10),
        "kf_heavy": FX.kf_frame(pull_v=200_000),
        "kf_one_print": FX.kf_frame(one_print_kiss=True),
        "hf": FX.hf_frame(),
        "hf_5m": FX.hf_frame(tf="5m"),
        "hf_unmerged": FX.hf_frame(merged=False),
        "hf_noentry": FX.hf_frame(entry=None),
        "vcp": FX.vcp_frame(),
        "vcp_noentry": FX.vcp_frame(entry=None),
        "vcp76": FX.vcp_frame(vcp76, e21_at={13: 9.8}),
        "vcp_one_broke": FX.vcp_frame(FX.VCP_BARS[:11] + [(10.5, 11.125, 10.4375, 10.75, 150_000)], entry=None),
        "vcp_lower_low": FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.6875, 10.125, 40_000))),
        "rs": FX.rs_frame(),
        "rs_noentry": FX.rs_frame(entry=None),
        "rs_s8": FX.rs_frame(FX.RS_S8_BARS, entry=FX.RS_S8_E),
        "rs_heavy": FX.rs_frame(FX.rs_replace(r11=(6.1875, 6.21875, 6.125, 6.15625, 300_000))),
    }


PREFIXED = ("bf_aplus", "kf", "hf", "vcp", "rs", "rs_s8")   # read at every prefix of today; the rest at the last bar

DETECTORS = (
    ("bull_flag", lambda F, last: D.bull_flag(F, last=last)),
    ("kiss_fly", lambda F, last: D.kiss_fly(F, last=last)),
    ("horizontal_fade", lambda F, last: D.fade_on(F, last=last)),
    ("intraday_vcp", lambda F, last: D.intraday_vcp(F, last=last)),
    ("reversal_squeeze", lambda F, last: D.reversal_squeeze(F, float_read=FR5M, last=last)),
)


def all_reads():
    """[(id, read)] — every detector on every frame (the PREFIXED ones at every prefix of today), plus the K11 gate
    on each broke read (volume unknown / one share under the floor / at the floor)."""
    out = []
    floor = int(GC.K11_MIN_SESSION_VOLUME)
    for name, F in _frames().items():
        lasts = range(F.today.start, len(F.c)) if name in PREFIXED else (len(F.c) - 1,)
        for last in lasts:
            for setup, fn in DETECTORS:
                r = fn(F, last)
                rid = f"{name}@{last}:{setup}"
                out.append((rid, r))
                if r.get("state") in D.K11_STATES:
                    for tag, vol in (("none", None), ("under", floor - 1), ("over", floor)):
                        out.append((f"{rid}:k11_{tag}", D.k11_gate(copy.deepcopy(r), vol)))
    return out


def strip(r: dict) -> dict:
    s = copy.deepcopy(r)
    s["criteria"] = [{"key": c["key"], "ok": c["ok"]} for c in s.get("criteria") or []]
    s.pop("reason", None)
    s.pop("why", None)
    return s


def snapshot_text() -> str:
    """Valid JSON, one read per line: {"<id>": <the stripped read, sorted compact JSON>, …}."""
    rows = [json.dumps(rid) + ":" + json.dumps(strip(r), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            for rid, r in all_reads()]
    return "{\n" + ",\n".join(rows) + "\n}\n"


# ── the wording-only proof ──────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_stripped_snapshot_is_byte_identical_to_the_untouched_tree():
    text = snapshot_text()
    if os.environ.get("GG_WRITE_GOLDEN") == "1" and os.environ.get("GG_PLAIN_WORDS_SNAPSHOT") == "1":
        SNAPSHOT.write_text(text, encoding="utf-8")
    assert SNAPSHOT.read_text(encoding="utf-8") == text


# ── shared helpers for the word pins ────────────────────────────────────────────────────────────────────────────────
import hashlib  # noqa: E402
import re  # noqa: E402

import pytest  # noqa: E402

from chart_maps.gajjala import alerts as AL  # noqa: E402
from chart_maps.gajjala import audited_rules as AUD  # noqa: E402
from chart_maps.gajjala import playbook as PB  # noqa: E402
from chart_maps.gajjala import potential as PT  # noqa: E402
from chart_maps.gajjala import squeeze_marks as SM  # noqa: E402
from chart_maps.gajjala import tab as GT  # noqa: E402
from scripts import gajjala_examples as EX  # noqa: E402
from supply_demand import rules_info as RI  # noqa: E402

BANNED = re.compile(r"boun|fake", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
UNNUMBERED = ("entry", "red_closes", "k8_base_len", "k8_tennis", "k8_failed")


def _rows(r: dict) -> list:
    return [(c["key"], c["label"], c["value"], c["need"]) for c in r["criteria"]]


def _row(r: dict, key: str) -> dict:
    return next(c for c in r["criteria"] if c["key"] == key)


def _knob(key: str) -> str:
    return next(k["text"] for k in PB.knobs() if k["key"] == key)


def _panel() -> dict:
    return RI._gajjala_section()


def _bf():
    return D.bull_flag(FX.bf_aplus())


def _kf_forming():
    return D.kiss_fly(FX.kf_frame(kiss_above_pct=0.6, entry=False))


def _hf():
    return D.fade_on(FX.hf_frame())


def _vcp_b():
    return D.intraday_vcp(FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000)), e21_at={13: 9.8}))


def _rs():
    return D.reversal_squeeze(FX.rs_frame(), float_read=FR5M)


def _rs_s8():
    return D.reversal_squeeze(FX.rs_frame(FX.RS_S8_BARS, entry=FX.RS_S8_E), float_read=FR5M)


# ── every row, exact: built from GC.* AND the literal at the shipped values ─────────────────────────────────────────
def test_bull_flag_rows_exact():
    r = _bf()
    k3 = f"every bar must be ≤ {D._vol(D.k3_vcap(FX.bf_aplus(), range(23, 25)))}: {D.part_words(GC.K3_VOL_FRAC)} " \
         f"the average bar of the run up"
    assert _rows(r) == [
        ("k2", "K2 volume building on the run up", "2 big green bars",
         f"inside the run up each bar at least the volume of the bar before and no more than "
         f"{GC.K2_MAX_VOL_STEP:g}× it"),
        ("k3_vol", "K3 volume dried up on the pullback", "busiest bar 100,000", k3),
        ("k4", "K4 short pullback", "2 bars", f"{GC.K4_BF_PULL_MIN} to {GC.K4_BF_PULL_MAX} bars"),
    ]
    assert _rows(r) == [
        ("k2", "K2 volume building on the run up", "2 big green bars",
         "inside the run up each bar at least the volume of the bar before and no more than 5× it"),
        ("k3_vol", "K3 volume dried up on the pullback", "busiest bar 100,000",
         "every bar must be ≤ 125,000: half the average bar of the run up"),
        ("k4", "K4 short pullback", "2 bars", "1 to 5 bars"),
    ]


def test_kiss_fly_rows_exact_forming():
    r = _kf_forming()
    assert r["reason"] == "low 0.6% above the 9 EMA — waiting for the kiss"
    assert _rows(r) == [
        ("k2", "K2 volume building on the run up", "1 big green bar",
         "inside the run up each bar at least the volume of the bar before and no more than 5× it"),
        ("k3_vol", "K3 volume dried up on the pullback", "busiest bar 100,000",
         "every bar must be ≤ 150,000: half the average bar of the run up"),
        ("k5_uptrend", "K5 uptrend", "9 EMA 10.36 · 21 EMA 9.56", "9 EMA above the 21 EMA and both higher than 3 bars ago"),
        ("k4", "K4 short pullback", "3 bars", "at most 9 bars"),
        ("k5a_honor", "K5a pullback honors the 9 EMA", "3 pullback bars",
         "every pullback bar closes at or above the 9 EMA"),
        ("k5_kiss", "K5 pullback touched the 9 EMA (the kiss)", "low 0.6% above the 9 EMA",
         "a low no more than 0.5% above the 9 EMA and a close above it"),
    ]
    assert _row(r, "k5_uptrend")["need"] == f"9 EMA above the 21 EMA and both higher than {GC.K5_SLOPE_BARS} bars ago"
    assert _row(r, "k5_kiss")["need"] == (f"a low no more than {GC.K5_KISS_TOL_PCT:g}% above the 9 EMA and a close "
                                         f"above it")


def test_kiss_fly_near_and_broke_rows():
    near = D.kiss_fly(FX.kf_near_kiss())
    assert (_row(near, "k5_kiss")["label"], _row(near, "k5_kiss")["value"], _row(near, "k5_kiss")["need"]) == (
        "K5 pullback touched the 9 EMA (the kiss)", "flew without touching the 9 EMA",
        f"a low no more than {GC.K5_KISS_TOL_PCT:g}% above the 9 EMA")
    assert _row(near, "k5_kiss")["need"] == "a low no more than 0.5% above the 9 EMA"
    broke = D.kiss_fly(FX.kf_frame())
    k = _row(broke, "k5_kiss")
    assert k["label"] == "K5 pullback touched the 9 EMA (the kiss)" and k["need"] == "a touch and a close above"
    assert k["value"].startswith("kiss bar ")


def test_fade_rows_exact():
    r = _hf()
    assert _rows(r) == [
        ("k4", "K4 sideways base length", "6 bars", f"{GC.K4_HF_BASE_MIN} to {GC.K4_HF_BASE_MAX} bars"),
        ("k3_vol", "K3 volume dried up in the base", "busiest bar 100,000",
         f"every bar must be ≤ 125,000: {D.part_words(GC.K3_VOL_FRAC)} the average bar of the run up"),
        ("k6_tight", "K6 tight base", "1.4% from high to low", f"at most {GC.K6_TIGHT_PCT:g}% of the price"),
        ("k6_merge", "K6 9 and 21 EMA merged", "EMAs 0.14% apart", f"at most {GC.K6_MERGE_PCT:g}% apart"),
        ("k6_decay", "K6 selling drying up", "second half 50% of the first half's volume",
         f"under {GC.K6_SELL_DECAY * 100:g}%"),
    ]
    assert [x[3] for x in _rows(r)] == ["6 to 24 bars", "every bar must be ≤ 125,000: half the average bar of the run up",
                                        "at most 8% of the price", "at most 0.5% apart", "under 70%"]


def test_vcp_rows_exact_and_the_grade_b_reason_names_the_label():
    r = _vcp_b()
    assert (r["state"], r["grade"], r["missed"]) == ("partial", "B", ["k7_ratio"])
    assert r["reason"] == "B — imperfect · missed K7 each contraction tighter than the last"
    assert r["reason"] == "B — imperfect · missed " + _row(r, "k7_ratio")["label"]
    assert _rows(r) == [
        ("k4_cycles", "K4 at least 2 contractions", "2 contractions", f"{GC.K4_VCP_MIN_CYCLES} or more"),
        ("k7_ratio", "K7 each contraction tighter than the last", "high to low 1.25 → 0.95",
         f"each at most {D.part_words(GC.K7_CONTRACTION)} the one before"),
        ("k7_ema21", "K7 contraction lows hold the 21 EMA", "lows 9.75 · 9.80",
         f"every low no more than {GC.K7_EMA21_TOL_PCT:g}% under the 21 EMA"),
        ("k3_vol", "K3 volume dried up on the pullbacks", "busiest bar 80,000",
         "every bar must be ≤ 150,000: half the average bar of the run up"),
    ]
    assert _row(r, "k7_ratio")["need"] == "each at most 75% of the one before"
    assert _row(r, "k7_ema21")["need"] == "every low no more than 0.5% under the 21 EMA"


def test_vcp_three_b_reason_names_the_ema21_label():
    from tests.test_gajjala_detectors import VCP_THIRD
    r = D.intraday_vcp(FX.vcp_frame(FX.VCP_BARS + VCP_THIRD, entry=None))
    assert (r["state"], r["grade"], r["missed"]) == ("partial", "B", ["k7_ema21"])
    assert r["reason"] == "B — imperfect · missed K7 contraction lows hold the 21 EMA"


def test_squeeze_rows_exact():
    r = _rs()
    assert r["state"] == "aplus"
    assert _rows(r) == [
        ("k8_tennis", "tennis ball action", "drop 2026-10-13 04:50 · back 2026-10-13 04:55",
         f"a drop of {GC.K8_DROP_PCT:g}% or more that closed back within {GC.K8_RECOVER_PCT:g}% of the high on the "
         f"drop bar or in the next {D._count(GC.K8_RECOVER_BARS, 'bar')}"),
        ("k8_failed", "tried the highs earlier and got sold", "1 failed try today",
         f"within {GC.K8_FAIL_NEAR_PCT:g}% of the day's high then {GC.K8_FAIL_DROP_PCT:g}% under that try's high: "
         f"{D.FAIL_RULE_WORDS[GC.K8_FAIL_EVENT_RULE]}"),
        ("k3_vol", "K3 volume dried up in the base", "busiest bar 60,000",
         "every bar must be ≤ 200,000: half the average bar of the run back up"),
        ("k8_base_len", "quiet base", "2 bars", f"at least {D._count(GC.RS_BASE_MIN_BARS, 'bar')}"),
    ]
    assert [x[3] for x in _rows(r)] == [
        "a drop of 8% or more that closed back within 2% of the high on the drop bar or in the next 3 bars",
        "within 2% of the day's high then 8% under that try's high: a separate sell-off that ends before the tennis "
        "ball",
        "every bar must be ≤ 200,000: half the average bar of the run back up",
        "at least 1 bar"]


def test_his_k3_row_renders_his_example_exactly():
    """His row, 2026-11-10: the 🎾 K3 need template for cap 36,008 and a busiest bar of 98,933."""
    need = D._k3_need(36008, "the run back up")
    assert need == "every bar must be ≤ 36,008: half the average bar of the run back up"
    row = f"✗ K3 volume dried up in the base — busiest bar {D._vol(98933)} ({need})"
    assert row == ("✗ K3 volume dried up in the base — busiest bar 98,933 (every bar must be ≤ 36,008: half the "
                   "average bar of the run back up)")


def test_entry_row_on_both_ambiguous_branches():
    frames = _frames()
    for name in ("bf_ambig_nomin", "bf_ambig_min"):
        r = D.bull_flag(frames[name])
        e = _row(r, "entry")
        assert r["state"] == "partial" and e["ok"] is False, name
        assert (e["label"], e["value"], e["need"]) == (
            "the break came before the stop", "trigger and stop both hit in the same bar, order unknown",
            "the break first"), name


# ── reasons ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_new_reasons_exact():
    q = FX.frame([FX.quiet(10.0)] * 6)
    assert D.bull_flag(q)["reason"] == "no run of 2 big green bars today"
    assert D.kiss_fly(q)["reason"] == "no big green bar today"
    assert D.fade_on(q)["reason"] == "no run of 2 big green bars today"
    assert D.intraday_vcp(q)["reason"] == "no big green bar today"
    assert D.reversal_squeeze(FX.rs_frame(FX.RS_BARS[:3], entry=None), float_read=FR5M)["reason"] == (
        "no tennis ball action today (a drop of 8% or more that closes back up on the drop bar or in the next 3 bars)")
    deep = (11.0, 11.0, 10.71875, 10.9375, 100_000)
    assert D.bull_flag(FX.frame(FX.bf_bars([deep, FX.P2])))["reason"] == "pulled back more than half the last big green bar"
    assert D.intraday_vcp(FX.vcp_frame(FX.VCP_BARS[:6], entry=None))["reason"] == "no pullback yet — still making new highs"
    assert D.intraday_vcp(FX.vcp_frame(FX.VCP_BARS[:11], entry=None))["reason"] == "1 of 2 contractions"
    assert D.intraday_vcp(FX.vcp_frame(entry=None))["reason"] == "the last contraction is still making its low"
    assert D.intraday_vcp(FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.6875, 10.125, 40_000))))["reason"] == \
        "lower low — the pullbacks must make higher lows"


def test_squeeze_forming_reason_and_the_potential_body_stays_short():
    reason = None
    F = _frames()["rs"]
    for last in range(F.today.start, len(F.c)):
        r = D.reversal_squeeze(F, float_read=FR5M, last=last)
        if r["state"] == "forming" and r["reason"]:
            reason = r["reason"]
    assert reason == "running back up — the quiet base has not started"
    body = f"GGB · building — {reason} · trigger 11.00 (not armed yet) · stop 10.88 (−1.1%)"
    assert len(body) <= 160


def test_no_pullback_before_the_break_and_contraction_low_reasons(monkeypatch):
    monkeypatch.setattr(GC, "VCP_B_READS", False)
    assert D.intraday_vcp(FX.vcp_frame(e21_at={13: 10.0}))["reason"] == "contraction low under the 21 EMA"
    src = pathlib.Path(D.__file__).read_text(encoding="utf-8")
    assert 'return _invalid(r, "no pullback before the break")' in src
    assert EX.first_failing_rule({"state": "invalid", "reason": "no pullback before the break"}) == "k4_cycles"


def test_no_pullback_before_the_break_rendered_on_a_frame():
    """Refix 2026-11-10: the reason pinned on a RENDERED read, not only by the source grep. Bar 6 is an outside bar:
    the first pivot low prints a high over H1 = 11.0, so the break comes right after the cycle high (j == H + 1)."""
    bars = FX.vcp_replace(r6=(10.875, 11.125, 9.5, 10.0, 80_000))
    for n in (9, len(bars)):
        r = D.intraday_vcp(FX.vcp_frame(bars[:n], entry=None))
        assert (r["state"], r["reason"]) == ("invalid", "no pullback before the break"), n
        assert EX.first_failing_rule(r) == "k4_cycles"


def test_NEGATIVE_no_pullback_before_the_break_only_when_the_break_follows_the_high():
    """The untouched VCP frame (bar 6 an inside pullback bar) never reads the reason, at any prefix of today."""
    F = FX.vcp_frame()
    reasons = {D.intraday_vcp(F, last=last)["reason"] for last in range(F.today.start, len(F.c))}
    assert "no pullback before the break" not in reasons
    assert "no pullback in the last cycle" not in reasons


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_helpers():
    assert D.part_words(0.5) == "half" and D.part_words(0.4) == "40% of" and D.part_words(0.7) == "70% of"
    assert D._vol(98933) == "98,933" and D._vol(None) == "—" and D._vol(36008.4) == "36,008"
    assert D._count(1, "bar") == "1 bar" and D._count(2, "bar") == "2 bars"
    assert D._count(0, "failed try", "failed tries") == "0 failed tries"
    assert D._no_run(1) == "no big green bar today" and D._no_run(2) == "no run of 2 big green bars today"
    assert D._decay_text(None, 5) == "base too short to compare" and D._decay_text(5, None) == "base too short to compare"
    assert D._decay_text(0, 5) == "first half of the base traded no volume"
    assert D._decay_text(1000, 704).endswith("70.4% of the first half's volume")
    assert D._decay_text(1000, 696) == "second half 69.6% of the first half's volume"
    assert D._decay_text(1000, 640) == "second half 64% of the first half's volume"
    assert D._tries_text(2, True) == "2 failed tries today" and D._tries_text(1, True) == "1 failed try today"
    assert D._tries_text(0, False) == "no failed try today"
    assert D._tries_text(1, False) == "1 failed try today, none that counts"
    assert D._busiest(FX.bf_aplus(), []) == "no bar yet"
    assert GC.K2_CHECK_FIRST_BAR is False and D.k2_first_words() == ""


# ── C5: the failed-try row counts every try, ticks only a paired one ───────────────────────────────────────────────
def test_failed_try_value_on_the_critics_case(monkeypatch):
    assert GC.K8_FAIL_EVENT_RULE == "distinct"
    r = _rs_s8()
    f = _row(r, "k8_failed")
    assert r["state"] == "partial" and f["ok"] is False and f["value"] == "1 failed try today, none that counts"
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", "same_ok")
    f = _row(_rs_s8(), "k8_failed")
    assert f["ok"] is True and f["value"] == "1 failed try today"


# ── C6: ONE map for the fail-event rule ─────────────────────────────────────────────────────────────────────────────
def test_one_map_for_the_fail_event_rule(monkeypatch):
    assert set(D.FAIL_RULE_WORDS) == set(GC.K8_FAIL_EVENT_RULES)
    for rule, words in D.FAIL_RULE_WORDS.items():
        monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", rule)
        assert _row(_rs(), "k8_failed")["need"].endswith(": " + words)
        assert _knob("H2") == "failed try vs the tennis ball: " + words
        assert ("that try's high; %s)" % words) in _panel()["picks"][6]


def test_NEGATIVE_the_old_fail_rule_words_are_gone_from_the_sources():
    for mod in (PB, RI):
        src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        assert "a separate, earlier sell-off (it must end" not in src and "the same drop may count" not in src


def test_NEGATIVE_unset_fail_rule_keeps_each_readers_fallback(monkeypatch):
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", None)
    assert "waiting for your number (H2)" in _knob("H2")
    assert "waiting for your number (H2)" in _panel()["picks"][6]
    assert D.read_all({"5m": FX.rs_frame(), "15m": None}, {"float_read": FR5M})["reversal_squeeze"]["reason"] \
        .startswith("awaiting")


# ── C1c: K2_SETUPS names exactly the setups whose rows carry k2 ────────────────────────────────────────────────────
def test_k2_setups_match_the_rows_on_every_fixture_read():
    seen = set()
    for rid, r in all_reads():
        if not r["criteria"]:
            continue
        seen.add(r["setup"])
        assert ("k2" in [c["key"] for c in r["criteria"]]) == (r["setup"] in D.K2_SETUPS), rid
    assert seen == set(GC.SETUPS)                                           # not vacuous: every setup has rows
    assert "(%s only)" % PB._setup_names(D.K2_SETUPS) in _knob("K2")
    assert " and ".join(RI._gg_label(k) for k in D.K2_SETUPS) + " only: inside the run up" in _panel()["picks"][1]


def test_k2_first_bar_clause_follows_its_switch(monkeypatch):
    clause = "the first bar is held to the same step"
    assert clause not in _row(_bf(), "k2")["need"] and clause not in _knob("K2")
    assert clause not in _panel()["picks"][1]
    monkeypatch.setattr(GC, "K2_CHECK_FIRST_BAR", True)
    assert clause in _row(D.bull_flag(FX.bf_aplus()), "k2")["need"]
    assert clause in _knob("K2") and clause in _panel()["picks"][1]


# ── C1d / C1a / C1b / C1e: the panel says what the code does ───────────────────────────────────────────────────────
def test_stop_one_names_the_fade_entry_only_on_base_high(monkeypatch):
    assert GC.HF_TRIGGER == "base_high"
    assert "(Fade: the base's high; VCP: the last contraction's high; squeeze: the top of the run back up)" in \
        _panel()["stops"][0]
    monkeypatch.setattr(GC, "HF_TRIGGER", "prior_bar")
    assert "Fade:" not in _panel()["stops"][0]


def test_squeeze_pick_has_no_at_the_top_and_its_depth_rider_follows_the_setups(monkeypatch):
    pick = _panel()["picks"][6]
    assert "at the top" not in pick and "(no depth limit: the stop is the base low, so read the card's risk %)" in pick
    assert all("at the top" not in k["text"] for k in PB.knobs())
    assert all("at the top" not in c["label"] for c in _rs()["criteria"])
    monkeypatch.setattr(GC, "K3_DEPTH_SETUPS", GC.K3_DEPTH_SETUPS + ("reversal_squeeze",))
    assert "no depth limit" not in _panel()["picks"][6]


def test_that_try_s_high_everywhere():
    for text in (_row(_rs(), "k8_failed")["need"], _knob("H1"), _panel()["picks"][6]):
        assert "under that try's high" in text
        assert "under it;" not in text and "then down" not in text


def test_tennis_window_and_kiss_entry_words():
    reason = D.reversal_squeeze(FX.rs_frame(FX.RS_BARS[:3], entry=None), float_read=FR5M)["reason"]
    for text in (_row(_rs(), "k8_tennis")["need"], reason, _knob("K8"), _panel()["picks"][6]):
        assert "on the drop bar or" in text
    assert "the very next bar" in _panel()["picks"][3]
    assert hashlib.sha256(repr(AL.ENTRY_WORDS).encode()).hexdigest() == \
        "66eb452dcabc4dec8b7ef5f387a1fded4f92150b7b59a776131af12220351550"          # NEGATIVE: not a target


# ── the other sentences ───────────────────────────────────────────────────────────────────────────────────────────
def test_tab_potential_and_registry_sentences(monkeypatch):
    legend = " ".join(r["text"] for r in GT.count_legend())
    assert "a run up alone is not a potential" in legend               # 2026-11-10: the 🧠 base clause says "run up"
    assert not any("demand leg" in r["text"] for r in GT.count_legend())               # NEGATIVE: one word per idea
    src = pathlib.Path(GT.__file__).read_text(encoding="utf-8")
    assert "Forming, not triggered: the run up is in and the quiet sideways part has started" in src
    c1 = PT.defaults_clauses()[0][2]
    assert c1.startswith("the base must hold at least one sideways bar — a run up alone is not a potential")
    assert not any("demand leg" in c for _, _, c in PT.defaults_clauses())             # NEGATIVE
    monkeypatch.setattr(GC, "POTENTIAL_NEEDS_BASE", False)                # the other branch, read at call time
    c1_off = PT.defaults_clauses()[0][2]
    assert c1_off.startswith("no sideways bar is needed — a run up alone counts")
    assert "demand leg" not in c1_off                                                   # NEGATIVE
    assert not any("demand leg" in c for _, _, c in PT.defaults_clauses())             # NEGATIVE: False branch
    assert not any("demand leg" in r["text"] for r in GT.count_legend())               # NEGATIVE: False branch
    monkeypatch.undo()
    row = next(x for x in AUD.registry_rows() if x["id"] == "K3S")
    assert row["rule"] == ("a 🎾 Reversal Squeeze break that 🚩 refuses ONLY on K3 (volume dried up in the base: no base "
                           "bar above 0.5× the average bar of the run back up) is a 🧪 A+ at that break bar with 🚩's "
                           "own trigger, stop and R; K11 session volume re-applied; every other 🧪 rule then applies")
    assert row["params_text"] == ("🎾 only · fires when K3 volume dried up in the base (no bar above 0.5× the average "
                                  "bar of the run back up) is the ONLY miss on the break bar · K11 re-applied · 🚩's "
                                  "plan unchanged")
    assert "{" not in row["rule"] and AUD.K3S.params["frac"] is GC.K3_VOL_FRAC
    assert set(AUD.K3S.params) == {"frac", "setups", "missed"}                 # NEGATIVE: no new param key
    assert "squeeze-back" not in row["rule"] + row["params_text"]


def test_the_ten_reworded_knobs_exact():
    want = {
        "K1": "big green bar (his demand bar): close ≥ open +3%, range ≥ 1.5× the prior 20 bars' average",
        "K2": "volume building on the run up (Bull Flag and EMA Kiss & Fly only): inside the run up each big green "
              "bar at least the volume of the bar before, no step over 5×",
        "K3": "pullback gives back no more than half the last big green bar's range (Bull Flag and EMA Kiss & Fly "
              "only); volume dried up: no pullback or base bar above half the average bar of the run up (🎾: of the "
              "run back up)",
        "K5": "kiss = a pullback low no more than 0.5% above the 9 EMA and a close above it; uptrend = 9 EMA over the "
              "21, both higher than 3 bars back; every pullback bar closes at or above the 9 EMA",
        "K6": "9 and 21 EMA merged (within 0.5%), tight base (at most 8% of the price from high to low), selling "
              "drying up (second half of the base under 70% of the first half's volume)",
        "K7": "each contraction (pullback) at most 75% of the one before, every contraction low no more than 0.5% "
              "under the 21 EMA, higher lows",
        "K8": "float ≤ 10,000,000; tennis ball action = a drop ≥ 8% that closes back within 2% of the high on the "
              "drop bar or in the next 3 bars; squeeze-history chip: last 30 sessions, ≥ 50% range or a halt",
        "H1": "failed try at the highs: within 2% of today's high, then 8% under that try's high",
        "H2": "failed try vs the tennis ball: a separate sell-off that ends before the tennis ball",
        "H3": "big green bars on the left side: Fade ≥ 2, VCP ≥ 1",
    }
    for k, text in want.items():
        assert _knob(k) == text, k


def test_NEGATIVE_the_untouched_knobs_are_byte_identical():
    want = {
        "Scanner": "price $0.10–$100, 1,000,000+ shares today, up 25%+ on the prior regular close; common stock + ADRs",
        "Stays listed": "2 sessions after it last qualified",
        "K4": "Bull Flag 1–5 bars · Kiss & Fly ≤ 9 · Fade base 6–24 · VCP ≥ 2 contractions",
        "K9": "premarket 1,000,000+ shares; yesterday's after-hours movers up 10%+",
        "K10": "regular close in the top 30% of the day's range, 250,000+ after-hours shares, up 5%+ on the close",
        "K11": "today's volume ≥ 1,000,000 shares at the ring (his scanner floor; 'it must sustain')",
        "H4": "squeeze quiet base ≥ 1 bars",
        "H5": "VCP pivots confirmed by 2 bars each side",
        "🧱 Psych chip": "$1 / $5 / $10 within 5% above the price",
    }
    for k, text in want.items():
        assert _knob(k) == text, k


def test_the_part_knobs_follow_their_constant(monkeypatch):
    monkeypatch.setattr(GC, "K3_VOL_FRAC", 0.4)
    assert "no pullback or base bar above 40% of the average bar" in _knob("K3")
    monkeypatch.setattr(GC, "K6_SELL_DECAY", 0.6)
    assert "under 60% of the first half's volume" in _knob("K6")


PICKS = [
    "Big green bar (his demand bar): close ≥ open +3% and range ≥ 1.5× the prior 20 bars' average. Run up = big green "
    "bars in a row. 🚩 Bull Flag and 💋 EMA Kiss & Fly only: inside the run up each bar trades at least the volume of "
    "the bar before, no step over 5×. Pullback: gives back no more than half the last big green bar's range (🚩 Bull "
    "Flag and 💋 EMA Kiss & Fly only) and the volume dries up: no bar above half the average bar of the run up.",
    "🚩 Bull Flag: a run up of ≥2 big green bars, then a 1–5 bar quiet pullback (longer = invalid); entry over the "
    "pullback bar's high, stop its low.",
    "💋 EMA Kiss & Fly: ≥1 big green bar(s), uptrend (9 EMA over the 21, both higher than 3 bars back), a pullback of "
    "at most 9 bars where every pullback bar closes at or above the 9 EMA, one bar touches it (the kiss: low within "
    "0.5%) and closes above it, with the same dried-up pullback volume; no kiss but everything else = “near-kiss”, "
    "listed, never A+; entry when the very next bar trades over the kiss bar's high.",
    "➖ Horizontal Fade (15m bars first, 5m fallback): a run up of ≥2 big green bars, a sideways 6–24 bar base no "
    "wider than 8% of the price, 9 and 21 EMA merged (within 0.5%), selling drying up (the second half of the base "
    "trades under 70% of the first half's volume); entry over the base's high, stop the prior bar's low.",
    "🌀 Intraday VCP: ≥1 big green bar(s), then ≥2 contractions (pullbacks), each at most 75% of the one before, every "
    "contraction low no more than 0.5% under the 21 EMA, higher lows, pivots confirmed by 2 closed bars each side, "
    "carded from 2 contractions (fewer are counted, not listed); exactly one of those two missed = “B — imperfect”, "
    "listed, never pushed; entry over the last contraction's high, stop its low.",
    "🎾 Reversal Squeeze (float ≤ 10,000,000): tennis ball action (a drop ≥8% off a bar's high that closes back within "
    "2% of that high on the drop bar or one of the next 3 bars), AND an earlier try at today's high that got sold "
    "(within 2%, then 8% under that try's high; a separate sell-off that ends before the tennis ball), then a quiet "
    "base of ≥1 bar(s) after the run back up (no depth limit: the stop is the base low, so read the card's risk %), "
    "its volume dried up: no base bar above half the average bar of the run back up; entry over the top, stop the "
    "base low. 🎾 squeeze-history chip: last 30 sessions, ≥50% range or a halt — a chip, not a rule.",
]


def test_panel_picks_two_to_seven_and_stop_one_exact():
    sec = _panel()
    assert len(sec["picks"]) == 8 and len(sec["stops"]) == 6
    assert sec["picks"][1:7] == PICKS
    assert sec["stops"][0].startswith(
        "Entry = the break of the prior bar's high (Fade: the base's high; VCP: the last contraction's high; squeeze: "
        "the top of the run back up); stop = that bar's low (VCP: the last contraction's low; squeeze: the base low). "
        "A reference bar with no range puts the stop at the trigger")
    assert "Never the first %d minutes after the open" % GC.NO_TRADE_AFTER_OPEN_MIN in sec["stops"][0]


def test_NEGATIVE_panel_drops_the_jargon():
    sec = _panel()
    lines = sec["picks"][1:7] + [sec["stops"][0]]
    for line in lines:
        for word in ("demand leg", "demand bars", "leg's mean", "squeeze-back", "cycle"):
            assert word not in line, (word, line[:60])
    assert sum(line.count("(his demand bar)") for line in sec["picks"] + sec["stops"]) == 1
    assert "carded from" in sec["picks"][5]


# ── NEGATIVES on every served string ──────────────────────────────────────────────────────────────────────────────
def _served_strings() -> list:
    out = []
    for _rid, r in all_reads():
        out.append(r["reason"])
        for c in r["criteria"]:
            out += [c["label"], c["value"], c["need"]]
    out += [k["text"] for k in PB.knobs()]
    sec = _panel()
    out += sec["picks"][1:7] + [sec["stops"][0]]
    out += [x["rule"] + " " + x["params_text"] for x in AUD.registry_rows() if x["id"] == "K3S"]
    return [s for s in out if s]


def test_NEGATIVE_no_banned_word_in_any_reworded_string():
    for s in _served_strings():
        assert not BANNED.search(s) and not EDGE.search(s), s


def test_NEGATIVE_labels_hold_no_comma_or_dash_and_keep_their_k_id():
    for rid, r in all_reads():
        for c in r["criteria"]:
            if c["key"] == D.K11_KEY:
                continue
            assert "," not in c["label"] and "—" not in c["label"], (rid, c["label"])
            if c["key"] in UNNUMBERED:
                assert not re.match(r"K\d", c["label"]), (rid, c["label"])
            else:
                kid = re.match(r"k(\d+a?)", c["key"]).group(1).upper().replace("A", "a")
                assert c["label"].startswith(f"K{kid} "), (rid, c["label"])


def test_NEGATIVE_no_raw_key_after_missed_and_no_dash_percent():
    """C8: no row value prints "—%". Refix 2026-11-10: k6_tight is no longer exempt (an empty base reads "no base
    yet"); only k6_merge keeps its byte-identical value, "EMAs —% apart" on an empty base included (spec 3.2, the
    tab's _EMA_GAP_RE reader), listed in the doc."""
    n = tight = 0
    for rid, r in all_reads():
        assert not re.search(r"missed k\d", r.get("reason") or ""), rid
        for c in r["criteria"]:
            if c["key"] != "k6_merge":
                n += 1
                tight += c["key"] == "k6_tight"
                assert "—%" not in c["value"], (rid, c["value"])
    assert n and tight


def test_k6_tight_empty_base_reads_no_base_yet():
    """Refix 2026-11-10 (owner's wording): the empty-base Fade row, e.g. bf_aplus@24:horizontal_fade."""
    reads = dict(all_reads())
    empty = [reads[rid] for rid in ("bf_aplus@24:horizontal_fade", "bf_forming@24:horizontal_fade",
                                    "hf@24:horizontal_fade", "rs@22:horizontal_fade", "rs_s8@22:horizontal_fade")]
    for r in empty:
        row = _row(r, "k6_tight")
        assert (row["label"], row["value"], row["need"], row["ok"]) == (
            "K6 tight base", "no base yet", f"at most {GC.K6_TIGHT_PCT:g}% of the price", None)
        assert row["need"] == "at most 8% of the price"


def test_NEGATIVE_k6_tight_measured_base_keeps_its_figure():
    """A measured base never reads "no base yet"; it prints the figure, and "no base yet" only ever sits with ok None."""
    assert _row(_hf(), "k6_tight")["value"] == "1.4% from high to low"
    seen = 0
    for rid, r in all_reads():
        for c in r["criteria"]:
            if c["key"] == "k6_tight":
                if c["value"] == "no base yet":
                    assert c["ok"] is None, rid
                else:
                    seen += 1
                    assert re.fullmatch(r"\d+(\.\d)?% from high to low", c["value"]), (rid, c["value"])
    assert seen


def test_NEGATIVE_k6_merge_value_still_parses():
    n = 0
    for rid, r in all_reads():
        for c in r["criteria"]:
            if c["key"] == "k6_merge":
                n += 1
                assert GT._EMA_GAP_RE.fullmatch(c["value"]) or c["value"] == "EMAs —% apart", (rid, c["value"])
    assert n


def test_NEGATIVE_awaiting_prefix_holds_with_a_placeholder_unset(monkeypatch):
    monkeypatch.setattr(GC, "HF_LEG_MIN_BARS", None)
    out = D.read_all({"5m": FX.hf_frame(tf="5m"), "15m": None}, {"symbol": "X"})
    assert out["horizontal_fade"]["state"] == "none" and out["horizontal_fade"]["reason"].startswith("awaiting")


def test_NEGATIVE_half_is_never_retyped(monkeypatch):
    monkeypatch.setattr(GC, "K3_VOL_FRAC", 0.4)
    need = _row(_bf(), "k3_vol")["need"]
    assert "40% of the average bar" in need and "half" not in need
    monkeypatch.undo()
    monkeypatch.setattr(GC, "K3_DEPTH_FRAC", 0.4)
    deep = (11.0, 11.0, 10.6, 10.9375, 100_000)
    r = D.bull_flag(FX.frame(FX.bf_bars([deep, FX.P2])))
    assert r["state"] == "invalid" and r["reason"] == "pulled back more than 40% of the last big green bar"


def test_NEGATIVE_kiss_text_is_sign_aware():
    F = FX.kf_frame(kiss_above_pct=0.6, entry=False)
    k = len(F.c) - 1
    e9 = F.ema9[k]
    for low, want in ((e9 * (1 - 0.014), "low 1.4% under the 9 EMA"), (e9 * (1 - 0.0004), "low at the 9 EMA"),
                      (e9 * (1 + 0.0004), "low at the 9 EMA"), (e9 * (1 + 0.006), "low 0.6% above the 9 EMA")):
        F.l[k] = low
        txt = D._kiss_text(F, k)
        assert txt == want
        assert not re.search(r"-\d.*% above", txt) and "0.0% under" not in txt and "0.0% above" not in txt


def test_NEGATIVE_cycle_count_reader_and_invalid_map_read_old_and_new_words():
    assert D.intraday_vcp(FX.vcp_frame())["criteria"][0]["value"] == "2 contractions"
    old = {"leg": {"bars": 1}, "criteria": [{"key": "k4_cycles", "value": "1 cycles"}]}
    new = {"leg": {"bars": 1}, "criteria": [{"key": "k4_cycles", "value": "1 contraction"}]}
    assert EX.read_count("intraday_vcp", old) == EX.read_count("intraday_vcp", new) == 1
    pairs = [("pulled back more than half the last demand bar", "pulled back more than half the last big green bar"),
             ("base sank below half the last demand bar", "base sank below half the last big green bar"),
             ("no pullback in the last cycle", "no pullback before the break"),
             ("lower low — not contracting up", "lower low — the pullbacks must make higher lows"),
             ("cycle low under the 21 EMA", "contraction low under the 21 EMA")]
    for old_r, new_r in pairs:
        a = EX.first_failing_rule({"state": "invalid", "reason": old_r})
        b = EX.first_failing_rule({"state": "invalid", "reason": new_r})
        assert a == b and not a.startswith("invalid:"), (old_r, a, b)
    assert EX.first_failing_rule({"state": "invalid", "reason": "pulled back more than 40% of the last big green bar"}) \
        == "k3_depth"


def test_NEGATIVE_red_closes_and_k11_labels_are_todays_words(monkeypatch):
    monkeypatch.setattr(GC, "RED_CLOSES_MODE", "criterion")
    rc = _row(D.kiss_fly(FX.kf_frame(5, red=4)), "red_closes")
    assert rc["label"] == "no more than 3 red closes in a row"
    assert D.k11_criterion(None)["label"] == "K11 today's volume unknown (needs ≥ 1,000,000)"
    assert D.k11_criterion(1_000_000)["label"] == "K11 today's volume 1,000,000 ≥ 1,000,000"
    assert D.k11_criterion(288_000)["label"] == \
        "K11 today's volume 288,000 < 1,000,000 (GG: one 1M bar then a fade = not interested)"


def test_NEGATIVE_the_squeeze_chart_words_are_left():
    assert hashlib.sha256(repr(SM.WORDS).encode()).hexdigest() == \
        "2a5cacee801729ad70c1b0417223bcb6dc1f8488c0651dac83a96965c5a569d4"


def test_NEGATIVE_long_flag_label_keeps_its_bracket(monkeypatch):
    monkeypatch.setattr(GC, "K4_BF_PULL_MAX", 2)
    monkeypatch.setattr(GC, "K4_BF_LONG_FLAG_MAX", 5)
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(5))))
    assert _row(r, "k4")["label"] == "K4 short pullback (3–5 = long flag)"


def test_NEGATIVE_a_stored_read_keeps_its_old_words_through_the_serve_path():
    """Stored rows are never relabelled at serve time: an old-words row comes out byte for byte."""
    from tests.test_gajjala_tab import R, latest, read_doc, scan_doc, store_with, NOW
    old = [{"key": "k2", "label": "K2 leg volume rising, each step ≤ 5×", "ok": True, "value": "2 demand bars",
            "need": "rising, no step above the cap"},
           {"key": "k3_vol", "label": "K3 pullback volume ≤ 0.5× leg mean", "ok": False,
            "value": "max 130000 vs cap 125000", "need": "≤ 125000"},
           {"key": "k4", "label": "K4 pullback 1–5 bars", "ok": True, "value": "2 bars", "need": "1–5"}]
    r = R("bull_flag", "partial", broke=True, criteria=copy.deepcopy(old), missed=["k3_vol"],
          reason="broke — not A+", entry_bar_t="2026-10-13 10:20", leg={"s_t": "a", "e_t": "b", "bars": 2},
          base={"bars": 2})
    st = store_with(reads=[read_doc("OLDW", {"bull_flag": r})], scans=[scan_doc("OLDW")], passes=[latest()])
    out = GT.build("bull_flag", now=NOW, store=st)
    tile = next(t for t in out["tiles"] if t["symbol"] == "OLDW")
    assert tile["gajjala"]["criteria"] == old
    assert "K3 pullback volume ≤ 0.5× leg mean" in tile["gajjala"]["state_label"]           # the pill: old words
    assert "volume dried up" not in json.dumps(tile, ensure_ascii=False)


def test_decay_text_never_prints_exponent_form_refix_2026_11_10():
    """REFIX: `:g` went to exponent form at extreme ratios; thousands separators instead, small ratios unchanged."""
    assert D._decay_text(100, 1_500_000) == "second half 1,500,000% of the first half's volume"
    assert D._decay_text(1000, 12345) == "second half 1,234.5% of the first half's volume"
    assert D._decay_text(100, 1000) == "second half 1,000% of the first half's volume"
    assert D._decay_text(1000, 704) == "second half 70.4% of the first half's volume"
    assert D._decay_text(1000, 1000) == "second half 100% of the first half's volume"
    assert D._decay_text(1000, 0) == "second half 0% of the first half's volume"
    for m1, m2 in ((100, 1_500_000), (1, 10 ** 9), (3, 7), (1000, 999_999)):
        text = D._decay_text(m1, m2)
        assert "e+" not in text and "e-" not in text and ".0%" not in text


def test_k3_need_without_a_cap_says_no_volume_yet_refix_2026_11_10():
    """REFIX: a None cap printed "every bar must be ≤ —"; it now says the run has no volume yet."""
    assert D._k3_need(None, "the run up") == "no volume yet on the run up"
    assert D._k3_need(None, "the run back up") == "no volume yet on the run back up"
    assert "—" not in D._k3_need(None, "the run up") and "≤" not in D._k3_need(None, "the run up")
    assert D._k3_need(0, "the run up") == "every bar must be ≤ 0: half the average bar of the run up"
    assert D._k3_need(36008, "the run up").startswith("every bar must be ≤ 36,008")


def test_NEGATIVE_the_row_needs_follow_their_constants_review_2026_11_10(monkeypatch):
    """REVIEW C3: the K6 / K7 row needs are built from GC at call time, never retyped (as the K3 'half' test)."""
    monkeypatch.setattr(GC, "K6_SELL_DECAY", 0.6)
    assert _row(_hf(), "k6_decay")["need"] == "under 60%"
    monkeypatch.setattr(GC, "K7_CONTRACTION", 0.8)
    monkeypatch.setattr(GC, "K7_EMA21_TOL_PCT", 0.25)
    r = _vcp_b()
    assert _row(r, "k7_ratio")["need"] == "each at most 80% of the one before"
    assert "0.25% under the 21 EMA" in _row(r, "k7_ema21")["need"]
