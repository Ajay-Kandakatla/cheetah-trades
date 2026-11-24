"""🌱 Diverging sub on 🚩 Gajjala's 5-min tab — the forming read, the served block, the card, the wiring (SPEC
2026-11-18 §3.1–3.7, WP-A `diverging-backend`).

Ajay 2026-11-18 ~11:50 ET, verbatim: "For the divergence thing create a separate tab that are potentially diverging with
uptrend and volume breakout." · "Are you building that now?". His picks: (1) "Fresh cross, gap widening" · (2) "GG's
day floor + bar spike".

Hermetic: FakeColl stores only (conftest refuses MongoClient). Synthetic Bars5: a constant bar shape (h − l = 1, the
close flat) makes the 14-bar ATR exactly 1.0, so R1 = 9 EMA − 21 EMA; the 21 EMA sits under 1.0 on a 1/4096 grid so
`21 EMA + the 🧨 cut` is exact (the partition test needs R1 == DIVERGENCE_R1_LEVEL exactly). `prior_tail` bars are dated
the prior session (critique C3).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import divergence as DV
from chart_maps.gajjala import divergence_tab as DVT
from chart_maps.gajjala import diverging_tab as DGT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import _walk_strings, scan_doc

ET = ZoneInfo("America/New_York")
S = date(2026, 11, 13)                          # a Friday, a market day
PREV = date(2026, 11, 12)
B_WORD = re.compile("b" + "ounc", re.I)
DG = GC.DIVERGING_SUB
STEP = 1.0 / 4096


def at(hh, mm, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET)


NOW = at(13, 2)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ────────────────────────────────────────────────────────────────────────────────────────────────────
def stamps(day, end, n):
    hh, mm = (int(x) for x in end.split(":"))
    e = hh * 60 + mm
    out = []
    for k in range(n):
        m = e - 5 * (n - 1 - k)
        out.append(f"{day.isoformat()} {m // 60:02d}:{m % 60:02d}")
    return out


def series(n_today=40, *, end="12:50", day=S, session=None, prior_tail=20, prior_day=PREV, path=(0.10, 0.20, 0.30),
           base=-0.10, vol=1000.0, last_vol=2000.0, e21_step=STEP, close=10.0, vols=None):
    """`path` = the 9 − 21 gap (in ATRs, ATR == 1.0) of the LAST len(path) bars; every earlier bar sits at `base`
    (negative = 9 under 21). The 21 EMA = 0.25 + e21_step × j."""
    t = (stamps(prior_day, "20:00", prior_tail) if prior_tail else []) + stamps(day, end, n_today)
    n = len(t)
    gaps = [base] * (n - len(path)) + list(path)
    e21 = [0.25 + e21_step * j for j in range(n)]
    e9 = [s + g for s, g in zip(e21, gaps)]
    v = list(vols) if vols is not None else [vol] * (n - 1) + [last_vol]
    return DV.Bars5(t=t, o=[close] * n, h=[close + 0.5] * n, l=[close - 0.5] * n, c=[close] * n, v=v, ema9=e9,
                    ema21=e21, session=(session or day).isoformat())


def rd(b, sv=2e6):
    return DGT.read_bars(b, sv, session=S)


def tile_of(b):
    def bars(idx):
        return [{"t": b.t[j], "o": b.o[j], "h": b.h[j], "l": b.l[j], "c": b.c[j], "v": b.v[j]} for j in idx]

    def curves(idx):
        return [{"tone": "ema9", "label": "9 EMA", "values": [b.ema9[j] for j in idx]},
                {"tone": "ema21", "label": "21 EMA", "values": [b.ema21[j] for j in idx]}]
    pi = [j for j in range(len(b)) if b.t[j][:10] != b.session]
    ti = [j for j in range(len(b)) if b.t[j][:10] == b.session]
    return {"bars5_prior": bars(pi), "curves5_prior": curves(pi), "bars5": bars(ti), "curves5": curves(ti),
            "bars15": [], "vol_avg5": {"period": 50, "label": "50-bar avg volume", "values": [1000.0] * len(ti)}}


def read_doc(sym, b=None, *, tile=None):
    return {"_id": f"{S.isoformat()}|{sym}", "date": S.isoformat(), "symbol": sym, "setups": {}, "ctx": {},
            "tile": tile if tile is not None else tile_of(b if b is not None else series()),
            "updated_at": NOW, "at": NOW}


def store(reads=(), *, volumes=None):
    reads = list(reads)
    vols = volumes or {}
    return fake_store(**{ST.READS: FakeColl(reads),
                         ST.SCAN: FakeColl([scan_doc(r["symbol"], day=S, volume=vols.get(r["symbol"], 2e6))
                                            for r in reads])})


def board(st, sub=DG, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, owner=kw.pop("owner", True), **kw)


# ── the read: POSITIVE ──────────────────────────────────────────────────────────────────────────────────────────
def test_the_canonical_series_lists():
    r = rd(series())
    assert r is not None
    assert r["widen_bars"] == 2 and r["bar_vol_mult"] == 2.0 and r["window"] == "rth"
    assert r["gap_peak"] == r["gap_atr"] and r["gap_atr"] == pytest.approx(0.30)
    assert r["bar_t"] == "2026-11-13 12:50" and r["up_cross_t"] == "2026-11-13 12:40"
    assert r["cross_i"] == 57 and r["pre_bars"] == 0 and r["bar_vol_n"] == GC.DIVERGING_BAR_VOL_LOOKBACK
    assert [round(x, 6) for x in r["gap_path"]] == [0.1, 0.2, 0.3] and r["session_volume"] == 2e6


def test_after_hours_bar_lists_with_the_ah_window_words():
    r = rd(series(end="16:05"))
    assert r is not None and r["window"] == "ah"
    assert DGT.record_words(r)["window_text"] == DVT.WINDOW_WORDS["ah"]
    assert DGT.record_words(rd(series()))["window_text"] == DVT.WINDOW_WORDS["rth"]


def test_widen_run_counts_strict_increases_only():
    assert DGT.widen_run([None, 0.1, 0.2, 0.3], 3) == 2
    assert DGT.widen_run([0.05, 0.1, 0.2, 0.3], 3) == 3
    assert DGT.widen_run([None, 0.1, 0.2, 0.2], 3) == 0                 # NEGATIVE: a tie is not wider
    assert DGT.widen_run([0.1, None, 0.3], 2) == 0                      # NEGATIVE: an unknown predecessor
    assert DGT.widen_run([0.1, 0.2, None], 2) == 0
    assert DGT.widen_run([], 0) == 0 and DGT.widen_run([0.1], 5) == 0


# ── the read: NEGATIVES (each flips one thing off the canonical series) ─────────────────────────────────────────
def test_NEGATIVE_gap_exactly_at_the_cut_is_divergence_side_by_partition():
    L = GC.DIVERGENCE_R1_LEVEL
    b = series(path=(0.10, 0.20, L))
    A = DV.atr_series(b)
    R1 = DV.r1_series(b, A)
    i = len(b) - 1
    assert R1[i] == L                                                   # exact by construction
    assert rd(b) is None
    clock = DGT.clock_of(S)
    el = [j for j in range(len(b)) if DV.eligible(b, A, j, clock, GC.DIVERGENCE_WINDOWS[0])]
    assert DV.first_crossing(R1, el, L) == {"i": i, "after_over": False}   # 🧨 DOES find it — the partition


def test_NEGATIVE_gap_above_the_cut():
    assert rd(series(path=(0.10, 0.20, 0.70))) is None


def test_NEGATIVE_over_the_cut_earlier_since_this_cross():
    assert rd(series(path=(0.30, 0.60, 0.40, 0.20, 0.25, 0.30))) is None


def test_over_the_cut_is_per_cross_a_new_up_cross_starts_over():
    b = series(path=(0.30, 0.60, 0.40, -0.10, 0.20, 0.25, 0.30))
    r = rd(b)
    assert r is not None
    assert r["cross_i"] == len(b) - 3 and r["up_cross_t"] == b.t[len(b) - 3]
    assert r["gap_peak"] == pytest.approx(0.30) and r["widen_bars"] == 2


def test_a_bar_with_unknown_atr_inside_the_span_is_skipped(monkeypatch):
    b = series(path=(0.30, 0.60, 0.40, 0.20, 0.25, 0.30))
    j60 = len(b) - 5
    real = DV.atr_series

    def holed(bb):
        A = real(bb)
        A[j60] = None
        return A
    monkeypatch.setattr(DV, "atr_series", holed)
    r = rd(b)
    assert r is not None and r["gap_peak"] == pytest.approx(0.40)       # cannot be judged — skipped, not a gate


def test_NEGATIVE_widened_only_one_bar():
    assert rd(series(path=(0.25, 0.20, 0.30))) is None


def test_NEGATIVE_a_tie_is_not_widening():
    assert rd(series(path=(0.10, 0.20, 0.20))) is None


def test_NEGATIVE_21_ema_flat_or_falling():
    assert rd(series(e21_step=0.0)) is None
    assert rd(series(e21_step=-STEP)) is None


def test_NEGATIVE_close_under_the_21():
    assert rd(series(close=0.2)) is None


def test_NEGATIVE_9_under_21_on_the_latest_bar():
    assert rd(series(path=(0.10, 0.20, -0.05))) is None


def test_NEGATIVE_no_up_cross_on_the_session():
    b = series(base=0.05)
    assert DV.up_cross_before(b, len(b) - 1) is None
    assert rd(b) is None


def test_session_volume_floor_fails_closed():
    b = series()
    floor = GC.K11_MIN_SESSION_VOLUME
    assert rd(b, floor - 1) is None                                     # NEGATIVE
    assert rd(b, None) is None and rd(b, "1e6") is None and rd(b, float("nan")) is None   # NEGATIVE: fail-closed
    assert rd(b, True) is None
    assert rd(b, floor) is not None                                     # exactly the floor lists


def test_bar_volume_spike_boundary():
    assert rd(series(last_vol=1990.0)) is None                          # NEGATIVE: 1.99×
    assert rd(series(last_vol=2000.0)) is not None                      # 2.0× in


def test_NEGATIVE_zero_mean_and_too_few_prior_bars():
    assert rd(series(vol=0.0, last_vol=100.0)) is None
    assert rd(series(n_today=20, prior_tail=0)) is None                 # 19 prior bars


def test_NEGATIVE_min_bars_on_a_tail_less_tile_is_the_eligible_floor():
    n = GC.DIVERGENCE_MIN_BARS - 1
    b = series(n_today=n, prior_tail=0)
    i = len(b) - 1
    assert i >= GC.DIVERGING_BAR_VOL_LOOKBACK                           # the L guard is NOT the reason
    A = DV.atr_series(b)
    assert DV.eligible(b, A, i, DGT.clock_of(S), GC.DIVERGENCE_WINDOWS[0]) is False
    assert rd(b) is None
    assert rd(series(n_today=GC.DIVERGENCE_MIN_BARS, prior_tail=0)) is not None   # the twin lists


@pytest.mark.parametrize("end", ["09:30", "08:00", "16:00", "20:00"])
def test_NEGATIVE_outside_the_windows(end):
    assert rd(series(end=end)) is None


def test_NEGATIVE_a_stale_tile():
    b = series(day=PREV, prior_day=date(2026, 11, 11), session=S)
    assert rd(b) is None


def test_NEGATIVE_ragged_input_never_raises():
    b = series()
    b.ema9[-1] = None
    assert rd(b) is None
    b = series()
    b.v[-1] = float("nan")
    assert rd(b) is None
    assert DGT.read_bars(DV.Bars5([], [], [], [], [], [], [], [], S.isoformat()), 2e6, session=S) is None


def test_NEGATIVE_read_doc_raises_on_a_malformed_tile():
    doc = read_doc("AAA")
    doc["tile"]["curves5"][0]["values"] = [1.0]                         # a curve shorter than its bars
    with pytest.raises(ValueError):
        DGT.read_doc(doc, 2e6, session=S)
    assert DGT.read_doc(read_doc("AAA"), 2e6, session=S) is not None


# ── open bias (critique C1) ─────────────────────────────────────────────────────────────────────────────────────
def test_open_bias_pre_bars_is_served_as_a_fact():
    r = rd(series(end="09:35"))
    assert r is not None and r["pre_bars"] == 20
    bv = DGT.criteria(r)[3]["value"]
    assert bv.endswith("20 of the 20 bars in the mean closed before 09:35 ET (pre-market or the prior session)")
    r13 = rd(series(end="13:00"))
    assert r13["pre_bars"] == 0 and "closed before" not in DGT.criteria(r13)[3]["value"]
    assert DGT.record_words(r13)["pre_bars_text"] is None
    r10 = rd(series(end="10:00"))
    assert r10["pre_bars"] == 15 and DGT.record_words(r10)["pre_bars_text"] == "15 of 20 before 09:35 ET"


def test_honesty_names_the_open_bias_without_a_typed_clock():
    h = DGT.honesty()
    assert "20-bar volume mean" in h and "2.0×" in h and "09:35 ET" in h and "UNMEASURED" in h
    assert "hour" not in h.lower() and "half-hour" not in h.lower()
    assert set(re.findall(r"\d\d:\d\d", h)) == {GC.DIVERGENCE_WINDOWS[0][1]}
    is_from, is_to, n = GC.DIVERGENCE_IS_WINDOW
    assert is_from in h and is_to in h and f"{n} sessions" in h


# ── the words ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_rule_text_holds_only_constant_numbers():
    t = DGT.rule_text()
    assert f"{GC.DIVERGENCE_R1_LEVEL:.3f}" in t and "2.0×" in t and "1,000,000" in t
    assert "every bar since that cross" in t and "never pre-market" in t and "🧨 Divergence" in t
    for _k, lo, hi in GC.DIVERGENCE_WINDOWS:
        assert lo in t and hi in t
    floats = set(re.findall(r"\d+\.\d+", t))
    assert floats == {f"{GC.DIVERGENCE_R1_LEVEL:.3f}", f"{GC.DIVERGING_BAR_VOL_MULT:.1f}"}, floats
    ints = {int(x) for x in re.findall(r"(?<![\d.:,])\d+(?![\d.:,])", t)}
    assert ints <= {GC.EMA_FAST, GC.EMA_SLOW, GC.DIVERGENCE_ATR_PERIOD, GC.DIVERGING_WIDEN_BARS,
                    GC.DIVERGING_BAR_VOL_LOOKBACK, GC.DIVERGING_EMA21_RISE_BARS, 5}, ints


def test_the_numbers_move_with_the_constants(monkeypatch):
    b25 = series(last_vol=2500.0)
    assert rd(b25) is not None
    monkeypatch.setattr(GC, "DIVERGING_BAR_VOL_MULT", 3.0)
    assert rd(b25) is None
    assert "3.0×" in DGT.rule_text() and "3.0×" in DGT.honesty()


def test_widen_bars_constant_is_read_at_call_time(monkeypatch):
    b = series()
    assert rd(b) is not None
    monkeypatch.setattr(GC, "DIVERGING_WIDEN_BARS", 3)
    assert rd(b) is None


def test_the_cut_is_read_at_call_time_including_the_since_cross_clause(monkeypatch):
    b = series(path=(0.10, 0.20, 0.30))
    assert rd(b) is not None
    monkeypatch.setattr(GC, "DIVERGENCE_R1_LEVEL", 0.2)
    assert rd(b) is None                                                # 0.3 is 🧨's side now
    monkeypatch.undo()
    b2 = series(path=(0.10, 0.25, 0.15, 0.16, 0.17))
    assert rd(b2) is not None
    monkeypatch.setattr(GC, "DIVERGENCE_R1_LEVEL", 0.2)
    assert rd(b2) is None                                               # the since-cross clause reads the new level


def test_k11_floor_is_his_scanner_floor_by_identity():
    assert GC.K11_MIN_SESSION_VOLUME is GC.SCAN_MIN_VOLUME
    assert GC.K11_MIN_SESSION_VOLUME == 1_000_000
    assert (GC.DIVERGING_WIDEN_BARS, GC.DIVERGING_BAR_VOL_MULT, GC.DIVERGING_BAR_VOL_LOOKBACK,
            GC.DIVERGING_EMA21_RISE_BARS) == (2, 2.0, 20, 1)


def test_constants_carry_his_words():
    from pathlib import Path
    src = Path(GC.__file__).read_text(encoding="utf-8")
    for name, words in (("DIVERGING_WIDEN_BARS", "has widened for 2+ bars in a row"),
                        ("DIVERGING_BAR_VOL_MULT", "at least 2× its last 20 bars' average"),
                        ("DIVERGING_BAR_VOL_LOOKBACK", "its last 20 bars' average"),
                        ("DIVERGING_EMA21_RISE_BARS", "MINE")):
        line = next(ln for ln in src.splitlines() if ln.startswith(name + " ="))
        assert words in line, name
    assert GC.GG5_ONLY_SUBS == (GC.TABLE_SUB, GC.DIVERGENCE_SUB, GC.DIVERGING_SUB, GC.HIGH_SI_SUB)   # WIDENED 2026-11-23 — 🩳 High SI after 🌱


def test_no_local_window_dict():
    assert not hasattr(DGT, "WINDOW_TEXT") and not hasattr(DGT, "WINDOW_WORDS")


@pytest.mark.parametrize("tape", ["rth", "premarket", "closed"])
def test_window_words_are_the_divergence_helper(tape):
    sess = {"tape": tape, "label": "today"}
    blk = DGT.block(DGT._empty_ev(), session=S, now=NOW, is_today=True, in_window=True, reads_by={},
                    scan_row=lambda s: {}, sess=sess, halts_by={}, listed={}, pass_at=None, flags=frozenset(), v=None)
    assert blk["window_text"] == DVT.window_text(sess)
    if tape == "premarket":
        assert "09:35 ET" in blk["window_text"]
    assert blk["n"] == 0 and blk["empty_text"] == DGT.EMPTY_TODAY and blk["bars_text"] is None
    assert "latest stored" in DGT.EMPTY_TODAY


def test_NEGATIVE_block_is_none_only_on_a_faulted_evaluation():
    assert DGT.block(None, session=S, now=NOW, is_today=True, in_window=True, reads_by={}, scan_row=lambda s: {},
                     sess={}, halts_by={}, listed={}, pass_at=None, flags=frozenset(), v=None) is None
    blk = DGT.block(DGT._empty_ev(), session=S, now=NOW, is_today=False, in_window=False, reads_by={},
                    scan_row=lambda s: {}, sess={"tape": "closed", "label": "last session 2026-11-12"}, halts_by={},
                    listed={}, pass_at=None, flags=frozenset(), v=None)
    assert blk["empty_text"] == DGT.EMPTY_SESSION.format(label="last session 2026-11-12")


# ── evaluate ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_evaluate_is_gg5_only_and_raises_only_on_a_non_dict():
    reads = {"AAA": read_doc("AAA")}
    row = lambda s: {"volume": 2e6}                                     # noqa: E731
    assert len(DGT.evaluate(reads, scan_row=row, session=S)["rows"]) == 1
    for v in (V.GG1, V.GGA):
        assert DGT.evaluate(reads, scan_row=row, session=S, v=v) == DGT._empty_ev()   # NEGATIVE
    with pytest.raises(TypeError):
        DGT.evaluate(None, scan_row=row, session=S)


def test_one_pass_two_bars_serves_the_bars_line():
    a = series(end="12:15")
    x = series(end="12:10")
    st = store([read_doc("ABC", a), read_doc("XYZ", x)], volumes={"ABC": 3e6, "XYZ": 2e6})
    ev = DGT.evaluate({"ABC": read_doc("ABC", a), "XYZ": read_doc("XYZ", x)},
                      scan_row=lambda s: {"volume": 2e6}, session=S)
    assert ev["latest_bar_t"] == "2026-11-13 12:15" and ev["behind"] == ["XYZ"]
    out = board(st)
    blk = out["diverging"]
    assert blk["bars_text"] == ("Latest stored bar 12:15 ET · 1 of 2 name(s) last read on an earlier bar — each card "
                                "names its bar")
    by = {t["symbol"]: t for t in out["tiles"]}
    assert "12:10 ET" in by["XYZ"]["gajjala"]["state_label"] and "12:15 ET" in by["ABC"]["gajjala"]["state_label"]
    same = board(store([read_doc("ABC", a), read_doc("XYZ", a)]))
    assert same["diverging"]["bars_text"] is None                       # NEGATIVE: one common bar → no line


# ── the board ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_sub_serves_the_block_the_chip_and_the_card():
    out = board(store([read_doc("AAA")]))
    assert out["sub"] == DG and out["sub_resolved_from"] == "param"
    assert out["subs"][7] == {"key": "diverging", "emoji": "🌱", "label": "Diverging", "count": 1, "title": None}
    b = out["diverging"]
    assert b["n"] == 1 and b["n_read"] == 1 and b["title"] == DGT.TITLE and b["ask_text"] == DGT.ASK_TEXT
    assert b["pick_texts"] == list(DGT.PICK_TEXTS) and b["rule_text"] == DGT.rule_text()
    assert b["honesty"] == DGT.honesty() and b["cohort_text"] == DGT.COHORT_TEXT
    assert b["order_note"] == DGT.ORDER_NOTE and b["empty_text"] is None and b["faults_text"] is None
    assert b["bars_text"] is None and b["chartless"] == [] and "_tiles" not in b and out["empty_note"] is None
    assert len(out["tiles"]) == 1
    t = out["tiles"][0]
    g = t["gajjala"]
    assert t["symbol"] == "AAA" and t["lines"] == [] and g["plan_text"] is None
    assert not any(m.get("kind") == "buy" for m in t["markers"])
    assert g["state_label"].startswith("🌱 diverging") and g["setup"] == DG
    assert len(g["criteria"]) == 5 and all(c["ok"] is True for c in g["criteria"])
    assert [c["key"] for c in g["criteria"]] == ["gap", "widening", "uptrend", "bar_volume", "k11_volume"]
    assert g["criteria"][4]["label"] == "K11 today's volume 2,000,000 ≥ 1,000,000"
    assert "12:40 ET" in g["criteria"][2]["value"]                       # the cross time on every card (C6)
    assert "peak 0.30 since the cross" in g["criteria"][0]["value"]
    assert {s["k"] for s in t["stats"]} >= {"Gap", "Bar vol"}
    assert g["diverging"]["cut_text"] == "🧨 cut %.3f ATRs" % GC.DIVERGENCE_R1_LEVEL


def test_the_strip_count_on_another_sub_and_no_block_there():
    st = store([read_doc("AAA")])
    out = board(st, GC.DEFAULT_SUB)
    keys = [s["key"] for s in out["subs"]]
    assert len(keys) == len(GC.SUBS) and keys[7] == DG and keys.index(DG) == keys.index(GC.DIVERGENCE_SUB) + 1
    assert out["subs"][7]["count"] == 1 and "diverging" not in out


def test_NEGATIVE_no_diverging_key_on_any_other_sub():
    st = store([read_doc("AAA")])
    for k, _e, _l in GC.SUBS:
        if k != DG:
            assert "diverging" not in board(st, k), k


@pytest.mark.parametrize("variant", [V.GG1, V.GGA], ids=["gg1", "gga"])
def test_NEGATIVE_other_pages_fail_open_and_omit_the_chip(variant):
    st = store([read_doc("AAA")])
    out = board(st, variant=variant)
    assert out["sub"] == GC.DEFAULT_SUB and out["sub_resolved_from"] == "default" and "diverging" not in out
    keys = [s["key"] for s in out["subs"]]
    assert DG not in keys and GC.DIVERGENCE_SUB not in keys
    if variant is V.GGA:
        assert len(keys) == len(GC.SUBS) - len(GC.GG5_ONLY_SUBS)
    else:                                                               # the 1-minute page keeps 📋
        assert keys[0] == GC.TABLE_SUB and len(keys) == len(GC.SUBS) - 3   # WIDENED 2026-11-23 — 🩳 High SI after 🌱 (🧨 + 🌱 + 🩳 omitted)


def test_order_is_volume_desc_then_gap():
    st = store([read_doc("AAA"), read_doc("BBB")], volumes={"AAA": 2e6, "BBB": 5e6})
    out = board(st)
    assert [t["symbol"] for t in out["tiles"]] == ["BBB", "AAA"]
    st = store([read_doc("AAA", series(path=(0.10, 0.20, 0.35))), read_doc("BBB")])
    assert [t["symbol"] for t in board(st)["tiles"]] == ["AAA", "BBB"]   # same volume → the wider gap first


def test_NEGATIVE_no_b_word_anywhere_on_the_sub():
    out = board(store([read_doc("AAA", series(end="09:35"))]))
    assert out["diverging"]["n"] == 1
    assert not [s for s in _walk_strings(out) if B_WORD.search(s)]
    from pathlib import Path
    assert not B_WORD.search(Path(DGT.__file__).read_text(encoding="utf-8"))


def test_NEGATIVE_an_evaluation_fault_blanks_the_sub_only(monkeypatch):
    st = store([read_doc("AAA")])
    healthy = board(st)

    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(DGT, "evaluate", boom)
    out = board(st)
    assert out["diverging"] is None and out["tiles"] == [] and out["empty_note"] == DGT.FAULT_TEXT
    assert out["subs"][7]["count"] is None

    def rest(o):
        d = {k: v for k, v in o.items() if k not in ("diverging", "tiles", "empty_note", "subs")}
        d["subs"] = [s for i, s in enumerate(o["subs"]) if i != 7]
        return d
    assert rest(out) == rest(healthy)


def test_NEGATIVE_a_malformed_tile_is_a_fault_the_other_name_still_carded():
    bad = read_doc("BAD")
    bad["tile"]["curves5"][0]["values"] = [1.0]
    good_b = series(end="12:15")
    st = store([read_doc("AAA", good_b), bad])
    out = board(st)
    blk = out["diverging"]
    assert blk["faults"] == ["BAD"] and blk["faults_text"] == DGT.FAULTS_TEXT.format(n=1)
    assert [t["symbol"] for t in out["tiles"]] == ["AAA"]
    ev = DGT.evaluate({"AAA": read_doc("AAA", good_b), "BAD": bad}, scan_row=lambda s: {"volume": 2e6}, session=S)
    assert ev["faults"] == ["BAD"] and "BAD" not in ev["behind"] and ev["latest_bar_t"] == "2026-11-13 12:15"


def test_NEGATIVE_a_raising_card_goes_chartless_with_a_fault(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(DGT, "card", boom)
    out = board(store([read_doc("AAA")]))
    blk = out["diverging"]
    assert out["tiles"] == [] and blk["faults"] == ["AAA"] and len(blk["chartless"]) == 1
    line = blk["chartless"][0]
    assert line["symbol"] == "AAA" and line["at_text"] == "12:50 ET" and line["state_label"].startswith("🌱 diverging")
    assert line["text"] == DGT.CHARTLESS_TEXT.format(sym="AAA", hhmm="12:50")


def test_resolve_sub_fails_open_off_gg5_only():
    for v in (V.GG1, V.GGA):
        assert GT.resolve_sub(DG, "", store=None, session=S, reads_by={}, listed={}, pm_syms=set(), post_syms=set(),
                              v=v) == (GC.DEFAULT_SUB, "default")
    assert GT.resolve_sub(DG, "", store=None, session=S, reads_by={}, listed={}, pm_syms=set(), post_syms=set(),
                          v=V.GG5) == (DG, "param")


# ── rules_info ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_info_note_carries_the_diverging_row_from_constants(monkeypatch):
    from supply_demand import rules_info as RI
    line = RI._gg_diverging_clause()
    assert line.startswith(" 🌱 Diverging (forming read only): listed on the latest stored 5-min bar")
    for w in ("2.0×", "20 bars", "1,000,000", "under the 🧨 cut on every bar since that cross", "no push, no gate"):
        assert w in line, w
    assert "0.555" not in line and line in RI._gajjala_section()["note"]
    monkeypatch.setattr(GC, "DIVERGING_BAR_VOL_MULT", 3.0)
    assert "3.0×" in RI._gg_diverging_clause()


def test_NEGATIVE_rules_info_a_missing_constant_drops_only_the_clause(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.delattr(GC, "DIVERGING_BAR_VOL_MULT")
    assert RI._gg_diverging_clause() == ""
    note = RI._gajjala_section()["note"]
    assert "🌱" not in note and "🧨 Divergence (record only)" in note
