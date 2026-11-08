"""🎾 GG's chart marks + the wide squeeze card (SPEC gg-squeeze §3.3 / WP be-ellipses, 2026-11-08).

Ajay 2026-11-08, verbatim: "I need something like this but that big of circle for reversal squeen mainly on the cart
itself also increase the width of the reversal sqeeze chart to show more bars" / "This is from Gajjals".

chart_maps/gajjala/squeeze_marks.py turns the STORED 🎾 read's `structure` stamps (+ the A+ marker's bar + the prior
session's after-hours spike from the K9 carry row) into served `ellipses`; tab._tile_frame(wide=True) lays the stored
prior-session tail ahead of today's bars, capped at GC.RS_TILE_BARS_MAX. Reads are typed by hand (the §3.1 `structure`
and §3.2 `_prior` shapes); the real-detector round trip is the main session's test. Display only. UNMEASURED.
"""
from __future__ import annotations

import ast
import copy
import re

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import squeeze_marks as SM
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import NOW, PREV, S, R, latest, read_doc, scan_doc, store_with

RS, BF, KF, HF, VCP = "reversal_squeeze", "bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp"
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
GGA_OWN = (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY, ST.EXITS)
ITEM_KEYS = {"kind", "from_t", "to_t", "lo", "hi", "label", "note", "tone"}
SESS = {"tape": "rth", "label": "today"}
CAP = 252                                   # the merged tree's GC.RS_TILE_BARS_MAX (be-prior-tail pins the value)


@pytest.fixture(autouse=True)
def _cap(monkeypatch):
    """The pre-merge tree has no RS_TILE_BARS_MAX yet (be-prior-tail adds it) — set it for this module."""
    monkeypatch.setattr(GC, "RS_TILE_BARS_MAX", getattr(GC, "RS_TILE_BARS_MAX", CAP), raising=False)


# ── fixtures ──────────────────────────────────────────────────────────────────────────────────────────────────────
def stamp(day, minutes):
    hh, mm = divmod(minutes, 60)
    return f"{day.isoformat()} {hh:02d}:{mm:02d}"


def run_bars(n, *, day=S, start=4 * 60 + 5, step=5, base=4.0, s=None, h=None):
    out = []
    for i in range(n):
        b = {"t": stamp(day, start + step * i), "o": base, "h": base + 0.1 if h is None else h, "l": base - 0.1,
             "c": base + 0.05, "v": 1000 + i}
        if s:
            b["s"] = s
        out.append(b)
    return out


def today192():
    return run_bars(192)                                                 # 04:05 → 20:00


def prior60():
    """The prior session 15:05 → 20:00 (60 bars): 16:05 onward flagged after hours."""
    out = run_bars(60, day=PREV, start=15 * 60 + 5, base=3.0)
    for b in out:
        if b["t"][11:] > "16:00":
            b["s"] = "ah"
    return out


def box(a, b, lo, hi, bars=2):
    return {"from_t": a, "to_t": b, "lo": lo, "hi": hi, "bars": bars}


T = lambda hm: f"{S.isoformat()} {hm}"                                    # noqa: E731
STRUCT = {"tennis": box(T("04:50"), T("04:55"), 5.6875, 6.25),
          "run": box(T("04:55"), T("04:55"), 5.8125, 6.25, 1),
          "base": box(T("05:00"), T("05:05"), 6.09375, 6.21875),
          "attempts": [box(T("04:20"), T("04:25"), 5.375, 5.96875)]}
ENTRY = T("05:10")


def rs_read(state="triggered", **kw):
    r = R(RS, state, entry_bar_t=ENTRY if state in ("aplus", "triggered", "stopped") else None,
          broke=state in ("aplus", "triggered", "stopped"), base={"from_t": T("05:00"), "to_t": T("05:05"), "bars": 2},
          structure=copy.deepcopy(STRUCT))
    r.update(kw)
    return r


def curves(n, tones=("ema9", "ema21"), v=1.0):
    return [{"tone": t, "label": t, "values": [v] * n} for t in tones]


def vol(n, v=100.0):
    return {"period": 50, "label": "50-bar avg volume", "values": [v] * n}


def wide_doc(sym, setups, *, prior=True, today=None, **kw):
    """A GG5 read doc carrying today's 192 bars and (by default) the prior session's 15:05 → 20:00 tail."""
    d = read_doc(sym, setups, **kw)
    tb = today if today is not None else today192()
    d["tile"].update(bars5=tb, curves5=curves(len(tb)), vol_avg5=vol(len(tb)))
    if prior:
        pb = prior60()
        d["tile"].update(bars5_prior=pb, curves5_prior=curves(len(pb), v=0.5), vol_avg5_prior=vol(len(pb), 50.0))
    return d


CARRY_ROW = {"ah_move_pct": 23.4, "ah_last": 0.247, "reg_close": 0.20}


def carry_doc(names=None, day=PREV):
    return {"_id": day.isoformat(), "date": day.isoformat(), "names": names if names is not None else {"SQZ": CARRY_ROW}}


def ah_bars(spike_at=("16:20", "16:25", "16:30")):
    """48 prior-day after-hours bars 16:05 → 20:00 around 0.20; the `spike_at` bars print highs of 0.25."""
    out = run_bars(48, day=PREV, start=16 * 60 + 5, base=0.20, s="ah", h=0.205)
    for b in out:
        if b["t"][11:] in spike_at:
            b["h"], b["l"] = 0.25, 0.21
    return out


def kinds(items):
    return [e["kind"] for e in items]


# ── words / one predicate / the guard ─────────────────────────────────────────────────────────────────────────────
def test_words_are_short_quote_gg_and_carry_no_advice():
    assert set(SM.WORDS) == set(SM.KINDS) == set(SM.TONE)
    for k, (label, note) in SM.WORDS.items():
        assert len(label) <= 12, k
        assert "GG" in note, k
        for s in (label, note):
            assert "buy" not in s.lower() and "sell" not in s.lower(), k
            assert not EDGE.search(s) and not B_WORD.search(s), k
    assert SM.TONE["entry"] == "entry" and {SM.TONE[k] for k in SM.KINDS if k != "entry"} == {"structure"}


def test_one_k9_predicate_is_imported_never_copied():
    assert SM._at_least is SC._at_least
    src = (GT.__file__.rsplit("/", 1)[0] + "/squeeze_marks.py")
    text = open(src, encoding="utf-8").read()
    assert "def _at_least" not in text
    nums = {n.value for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}
    assert nums <= {0, 1}, nums                                             # K9_AH_CARRY_PCT never retyped


def test_the_new_module_is_under_the_source_guard():
    from tests.test_gajjala_source_guard import FILES
    assert "squeeze_marks.py" in {f.name for f in FILES}
    src = (FILES[0].parent / "squeeze_marks.py").read_text(encoding="utf-8")
    assert not B_WORD.search(src) and "SEPA" not in src and "Minervini" not in src


# ── squeeze_marks.ellipses ───────────────────────────────────────────────────────────────────────────────────────
def test_a_triggered_read_serves_every_piece_plus_the_entry():
    bars = today192()
    out = SM.ellipses(rs_read(), bars, entry_t=ENTRY, carry_row=None, prev_iso=PREV.isoformat())
    assert kinds(out) == ["attempt", "tennis", "run", "base", "entry"]
    stamps = {b["t"] for b in bars}
    for e in out:
        assert set(e) == ITEM_KEYS
        assert e["from_t"] in stamps and e["to_t"] in stamps
        assert isinstance(e["lo"], float) and isinstance(e["hi"], float) and e["lo"] <= e["hi"]
        assert e["tone"] == ("entry" if e["kind"] == "entry" else "structure")
        assert (e["label"], e["note"]) == SM.WORDS[e["kind"]]
    by = {e["kind"]: e for e in out}
    assert (by["tennis"]["from_t"], by["tennis"]["to_t"], by["tennis"]["lo"], by["tennis"]["hi"]) == \
        (T("04:50"), T("04:55"), 5.6875, 6.25)
    assert by["base"]["lo"] == 6.09375 and by["run"]["from_t"] == by["run"]["to_t"] == T("04:55")
    ent = by["entry"]
    bar = next(b for b in bars if b["t"] == ENTRY)
    assert ent["from_t"] == ent["to_t"] == ENTRY and (ent["lo"], ent["hi"]) == (bar["l"], bar["h"])


def test_two_attempts_serve_two_items_in_order():
    r = rs_read()
    r["structure"]["attempts"].append(box(T("04:35"), T("04:40"), 5.5, 6.0))
    out = SM.ellipses(r, today192(), entry_t=None, carry_row=None, prev_iso=None)
    assert [(e["kind"], e["from_t"]) for e in out if e["kind"] == "attempt"] == \
        [("attempt", T("04:20")), ("attempt", T("04:35"))]


def test_NEGATIVE_no_attempts_no_base_no_attempt_or_base_item():
    r = rs_read()
    r["structure"].update(attempts=[], base=None)
    out = SM.ellipses(r, today192(), entry_t=ENTRY, carry_row=None, prev_iso=None)
    assert kinds(out) == ["tennis", "run", "entry"]


def test_NEGATIVE_a_stamp_off_the_served_window_drops_that_item():
    """The 192-bar cap case: bars that start after the tennis ball → the tennis/attempt items vanish, the rest draw."""
    bars = [b for b in today192() if b["t"] >= T("04:55")]
    out = SM.ellipses(rs_read(), bars, entry_t=ENTRY, carry_row=None, prev_iso=None)
    assert kinds(out) == ["run", "base", "entry"]


@pytest.mark.parametrize("state", ("forming", "partial"))
def test_NEGATIVE_no_marker_means_no_entry_item(state):
    """A forming read / a partial broke read (entry_bar_t set, no A+ marker) → the caller passes entry_t None."""
    r = rs_read(state, entry_bar_t=ENTRY if state == "partial" else None)
    out = SM.ellipses(r, today192(), entry_t=None, carry_row=None, prev_iso=None)
    assert "entry" not in kinds(out) and kinds(out) == ["attempt", "tennis", "run", "base"]


def test_NEGATIVE_no_structure_serves_only_entry_or_ah():
    r = rs_read()
    r.pop("structure")
    assert SM.ellipses(r, today192(), entry_t=None, carry_row=None, prev_iso=None) == []
    assert kinds(SM.ellipses(r, today192(), entry_t=ENTRY, carry_row=None, prev_iso=None)) == ["entry"]


@pytest.mark.parametrize("junk", (None, {}, [], "x", 3, {"structure": "x"}, {"structure": {"tennis": "x",
                                                                                              "attempts": "y"}},
                                  {"structure": {"tennis": box(T("04:50"), T("04:55"), "a", None)}},
                                  {"structure": {"tennis": box(T("04:50"), T("04:55"), 6.0, 5.0)}}))
def test_NEGATIVE_junk_never_raises(junk):
    assert SM.ellipses(junk, today192(), entry_t=None, carry_row=None, prev_iso=None) == []
    assert SM.ellipses(rs_read(), "bars", entry_t=ENTRY, carry_row="x", prev_iso=3) == []
    assert SM.ellipses(rs_read(), [None, 3, {"t": 5}], entry_t=ENTRY, carry_row=CARRY_ROW, prev_iso="x") == []


# ── the after-hours spike (K9 carry) ──────────────────────────────────────────────────────────────────────────────
def test_ah_spans_only_the_bars_over_the_k9_line():
    bars = ah_bars() + today192()
    out = SM.ellipses(rs_read(), bars, entry_t=None, carry_row=CARRY_ROW, prev_iso=PREV.isoformat())
    assert kinds(out)[0] == "ah"
    ah = out[0]
    assert (ah["from_t"], ah["to_t"]) == (f"{PREV} 16:20", f"{PREV} 16:30")         # the spike, not 16:05 → 20:00
    assert (ah["lo"], ah["hi"]) == (0.21, 0.25)
    assert ah["note"] == SM.WORDS["ah"][1] + " · after hours +23.4% vs the regular close"
    assert ah["label"] == "AH spike" and ah["tone"] == "structure"


def test_ah_follows_the_constant_never_a_retyped_number(monkeypatch):
    bars = ah_bars() + today192()
    monkeypatch.setattr(GC, "K9_AH_CARRY_PCT", 1.0)                         # 0.202 line → every AH bar clears it
    ah = SM.ellipses(rs_read(), bars, entry_t=None, carry_row=CARRY_ROW, prev_iso=PREV.isoformat())[0]
    assert (ah["from_t"], ah["to_t"]) == (f"{PREV} 16:05", f"{PREV} 20:00")
    monkeypatch.setattr(GC, "K9_AH_CARRY_PCT", 24.0)                        # 0.248 → still the three spike bars
    ah = SM.ellipses(rs_read(), bars, entry_t=None, carry_row=CARRY_ROW, prev_iso=PREV.isoformat())[0]
    assert (ah["from_t"], ah["to_t"]) == (f"{PREV} 16:20", f"{PREV} 16:30")


@pytest.mark.parametrize("row", ({"ah_move_pct": 23.4, "reg_close": 0.30},          # nothing clears the line
                                 {"ah_move_pct": 23.4, "reg_close": None},
                                 {"ah_move_pct": 23.4, "reg_close": 0},
                                 {"ah_move_pct": 23.4}))
def test_ah_falls_back_to_the_whole_stretch(row):
    ah = SM.ellipses(rs_read(), ah_bars() + today192(), entry_t=None, carry_row=row, prev_iso=PREV.isoformat())[0]
    assert ah["kind"] == "ah"
    assert (ah["from_t"], ah["to_t"]) == (f"{PREV} 16:05", f"{PREV} 20:00")
    assert ah["lo"] == pytest.approx(0.1) and ah["hi"] == 0.25


def test_ah_note_without_a_move_has_no_tail():
    ah = SM.ellipses({}, ah_bars(), entry_t=None, carry_row={"reg_close": 0.2}, prev_iso=PREV.isoformat())[0]
    assert ah["note"] == SM.WORDS["ah"][1]


def test_NEGATIVE_no_ah_item_without_a_carry_row_or_prior_ah_bars():
    full = ah_bars() + today192()
    assert "ah" not in kinds(SM.ellipses(rs_read(), full, entry_t=None, carry_row=None, prev_iso=PREV.isoformat()))
    assert "ah" not in kinds(SM.ellipses(rs_read(), today192(), entry_t=None, carry_row=CARRY_ROW,
                                         prev_iso=PREV.isoformat()))                 # today-only bars
    no_s = [{k: v for k, v in b.items() if k != "s"} for b in ah_bars()]
    assert "ah" not in kinds(SM.ellipses(rs_read(), no_s, entry_t=None, carry_row=CARRY_ROW,
                                         prev_iso=PREV.isoformat()))                 # `s` missing
    assert "ah" not in kinds(SM.ellipses(rs_read(), full, entry_t=None, carry_row=CARRY_ROW, prev_iso=None))
    assert "ah" not in kinds(SM.ellipses(rs_read(), full, entry_t=None, carry_row=CARRY_ROW,
                                         prev_iso="2026-10-09"))                     # another day's after hours


# ── tab._tile_frame(wide=…) ──────────────────────────────────────────────────────────────────────────────────────
def test_wide_frame_lays_the_prior_tail_ahead_of_today():
    d = wide_doc("SQZ", {RS: rs_read()})
    fr = GT._tile_frame(d, "5m", wide=True)
    assert fr["tf"] == "5m" and len(fr["bars"]) == 252
    assert fr["bars"] == d["tile"]["bars5_prior"] + d["tile"]["bars5"]
    assert [c["tone"] for c in fr["curves"]] == ["ema9", "ema21"]
    for c in fr["curves"]:
        assert c["values"] == [0.5] * 60 + [1.0] * 192
    assert fr["vol_avg"] == {"period": 50, "label": "50-bar avg volume", "values": [50.0] * 60 + [100.0] * 192}


def test_wide_frame_caps_at_rs_tile_bars_max_keeping_the_last_bars():
    d = wide_doc("SQZ", {RS: rs_read()}, today=run_bars(180))
    d["tile"].update(bars5_prior=run_bars(120, day=PREV, start=10 * 60), curves5_prior=curves(120, v=0.5),
                     vol_avg5_prior=vol(120, 50.0))                                     # 300 bars
    fr = GT._tile_frame(d, "5m", wide=True)
    assert len(fr["bars"]) == GC.RS_TILE_BARS_MAX == 252
    allb = d["tile"]["bars5_prior"] + d["tile"]["bars5"]
    assert fr["bars"] == allb[-252:] and fr["bars"][0] == d["tile"]["bars5_prior"][48]
    for c in fr["curves"]:
        assert c["values"] == [0.5] * 72 + [1.0] * 180
    assert fr["vol_avg"]["values"] == [50.0] * 72 + [100.0] * 180


def test_wide_frame_pads_a_one_sided_tone_and_a_missing_average():
    d = wide_doc("SQZ", {RS: rs_read()})
    d["tile"]["curves5_prior"] = curves(60, tones=("ema21",), v=0.5)
    d["tile"]["curves5"] = curves(192, tones=("ema9",))
    d["tile"].pop("vol_avg5_prior")
    fr = GT._tile_frame(d, "5m", wide=True)
    by = {c["tone"]: c["values"] for c in fr["curves"]}
    assert by["ema21"] == [0.5] * 60 + [None] * 192
    assert by["ema9"] == [None] * 60 + [1.0] * 192
    assert all(len(v) == len(fr["bars"]) for v in by.values())
    assert fr["vol_avg"]["values"] == [None] * 60 + [100.0] * 192


def test_NEGATIVE_wide_false_and_no_prior_are_byte_identical_to_today():
    d = wide_doc("SQZ", {RS: rs_read()})
    old = {"tf": "5m", "bars": d["tile"]["bars5"], "curves": d["tile"]["curves5"], "vol_avg": d["tile"]["vol_avg5"]}
    assert GT._tile_frame(d, "5m") == GT._tile_frame(d, "5m", wide=False) == old
    plain = wide_doc("SQZ", {RS: rs_read()}, prior=False)
    assert GT._tile_frame(plain, "5m", wide=True) == GT._tile_frame(plain, "5m")
    empty = wide_doc("SQZ", {RS: rs_read()})
    empty["tile"]["bars5_prior"] = []
    assert GT._tile_frame(empty, "5m", wide=True) == GT._tile_frame(empty, "5m")
    assert GT._tile_frame(d, "15m", wide=True) == GT._tile_frame(d, "15m")          # no bars15_prior
    assert GT._last_close(d, "5m") == d["tile"]["bars5"][-1]["c"]


# ── tab.setup_tile ───────────────────────────────────────────────────────────────────────────────────────────────
def _tile(doc, setup=RS, tf="5m", v=None, **kw):
    return GT.setup_tile(doc, setup, tf, scan_row={"price": 4.05, "change_pct": 40.0, "volume": 2e6}, sess=SESS,
                         listed=None, v=v, **kw)


def test_a_squeeze_card_serves_ellipses_and_the_wide_bars():
    d = wide_doc("SQZ", {RS: rs_read()})
    t = _tile(d, carry=carry_doc(), prev_iso=PREV.isoformat())
    assert len(t["bars"]) == 252 and t["bars"][0]["t"] == f"{PREV} 15:05"
    assert t["markers"] == [{"date": ENTRY, "kind": "buy", "label": "A+"}]
    assert kinds(t["ellipses"]) == ["ah", "attempt", "tennis", "run", "base", "entry"]
    assert (t["ellipses"][0]["from_t"], t["ellipses"][0]["to_t"]) == (f"{PREV} 16:05", f"{PREV} 20:00")   # all clear
    bare = copy.deepcopy(d)
    for k in ("bars5_prior", "curves5_prior", "vol_avg5_prior"):
        bare["tile"].pop(k)
    bare["setups"][RS].pop("structure")
    b = _tile(bare)
    diff = {k for k in set(t) | set(b) if t.get(k) != b.get(k)}
    assert diff <= {"bars", "curves", "vol_avg", "ellipses"} and "ellipses" in diff
    assert len(b["bars"]) == 192 and kinds(b["ellipses"]) == ["entry"]


def test_the_ah_item_reaches_the_card_through_the_carry_row():
    d = wide_doc("SQZ", {RS: rs_read()})
    d["tile"]["bars5_prior"] = ah_bars()
    d["tile"]["curves5_prior"], d["tile"]["vol_avg5_prior"] = curves(48), vol(48)
    t = _tile(d, carry=carry_doc(), prev_iso=PREV.isoformat())
    assert kinds(t["ellipses"])[0] == "ah" and t["ellipses"][0]["from_t"] == f"{PREV} 16:20"
    other = _tile(d, carry=carry_doc({"ELSE": CARRY_ROW}), prev_iso=PREV.isoformat())
    assert "ah" not in kinds(other["ellipses"])                                           # NEGATIVE: not in the carry
    for junk in (None, {}, {"names": None}, {"names": "x"}, "x"):
        assert "ah" not in kinds(_tile(d, carry=junk, prev_iso=PREV.isoformat())["ellipses"]), junk


@pytest.mark.parametrize("setup", (BF, KF, HF, VCP))
def test_NEGATIVE_other_setups_carry_no_ellipses_and_today_bars_only(setup):
    r = rs_read(setup=setup)
    d = wide_doc("SQZ", {setup: r})
    t = _tile(d, setup=setup, carry=carry_doc(), prev_iso=PREV.isoformat())
    assert "ellipses" not in t
    assert t["bars"] == d["tile"]["bars5"] and len(t["bars"]) == 192
    assert t == _tile(d, setup=setup)                                                    # the kwargs change nothing


def test_NEGATIVE_the_15m_toggle_serves_no_ellipses_even_when_stamps_join():
    """[C3] the AEHL shape: a 5-minute tennis ball on 09:15 → 09:30 exists among the 15-minute bars too."""
    r = rs_read(entry_bar_t=T("09:45"))
    r["structure"] = {"tennis": box(T("09:15"), T("09:30"), 4.0, 4.5), "run": box(T("09:30"), T("09:30"), 4.1, 4.5, 1),
                      "base": None, "attempts": []}
    d = wide_doc("SQZ", {RS: r}, today=run_bars(60, start=9 * 60 + 5))
    d["tile"]["bars15"] = run_bars(8, start=9 * 60 + 15, step=15, base=4.2)                # 09:15, 09:30, 09:45 …
    assert {T("09:15"), T("09:30"), T("09:45")} <= {b["t"] for b in d["tile"]["bars15"]}
    t15 = _tile(d, tf="15m", carry=carry_doc(), prev_iso=PREV.isoformat())
    assert t15["tf"] == "15m" and t15["ellipses"] == []
    assert t15["bars"] == d["tile"]["bars15"]                                             # no bars15_prior
    assert t15["markers"] == [{"date": T("09:45"), "kind": "buy", "label": "A+"}]         # the marker keeps _on_bars
    t5 = _tile(d, tf="5m", carry=carry_doc(), prev_iso=PREV.isoformat())
    assert kinds(t5["ellipses"]) == ["ah", "tennis", "run", "entry"]


def test_a_read_without_a_frame_draws_on_the_primary():
    r = rs_read()
    r.pop("frame")
    t = _tile(wide_doc("SQZ", {RS: r}))
    assert t["tf"] == "5m" and kinds(t["ellipses"]) == ["attempt", "tennis", "run", "base", "entry"]
    assert _tile(wide_doc("SQZ", {RS: r}), tf="15m")["ellipses"] == []


def test_NEGATIVE_a_list_tile_never_carries_ellipses():
    d = wide_doc("SQZ", {RS: rs_read()})
    for v in (None, V.GG1, V.GGA):
        t = GT._list_tile("SQZ", "premarket", d, "5m", scan_row={"price": 4.05}, sess=SESS, listed=None,
                          extra={"state_label": "listed"}, v=v)
        assert "ellipses" not in t, v
    t = GT._list_tile("SQZ", "premarket", d, "5m", scan_row={"price": 4.05}, sess=SESS, listed=None,
                      extra={"state_label": "listed"})
    assert t["bars"] == d["tile"]["bars5"]                                                 # never the wide frame


# ── tab.build ────────────────────────────────────────────────────────────────────────────────────────────────────
def _gg5(docs, carry=(carry_doc(),)):
    return store_with(reads=docs, scans=[scan_doc(d["symbol"]) for d in docs], passes=[latest()], carry=list(carry))


def _tiles(out):
    return {t["symbol"]: t for t in out["tiles"]}


def test_build_serves_ellipses_on_the_squeeze_sub_and_threads_the_carry():
    d = wide_doc("SQZ", {RS: rs_read()})
    d["tile"]["bars5_prior"] = ah_bars()
    d["tile"]["curves5_prior"], d["tile"]["vol_avg5_prior"] = curves(48), vol(48)
    out = GT.build(RS, now=NOW, store=_gg5([d]))
    t = _tiles(out)["SQZ"]
    assert kinds(t["ellipses"]) == ["ah", "attempt", "tennis", "run", "base", "entry"]
    assert len(t["bars"]) == 48 + 192
    assert "_float_shares" not in t["gajjala"]                                             # order key still popped


def test_NEGATIVE_build_other_sub_tiles_carry_no_ellipses():
    docs = [wide_doc("SQZ", {RS: rs_read()}), wide_doc("FLG", {BF: rs_read(setup=BF)})]
    out = GT.build(BF, now=NOW, store=_gg5(docs))
    t = _tiles(out)["FLG"]
    assert "ellipses" not in t and len(t["bars"]) == 192


def test_build_reads_the_carry_no_more_than_before(monkeypatch):
    """[C8] no NEW carry read: the two pre-existing reads (premarket_rows :1232 and `ah_prev`) — both of `prev`."""
    st = _gg5([wide_doc("SQZ", {RS: rs_read()})])
    calls = []
    real = st.ah_carry

    def spy(session):
        calls.append(session)
        return real(session)
    monkeypatch.setattr(st, "ah_carry", spy)
    GT.build(RS, now=NOW, store=st)
    n_rs = len(calls)
    calls.clear()
    GT.build(BF, now=NOW, store=st)
    assert n_rs == len(calls) == 2 and set(calls) == {PREV}


def test_NEGATIVE_a_raising_carry_read_still_builds_without_an_ah_item(monkeypatch):
    d = wide_doc("SQZ", {RS: rs_read()})
    d["tile"]["bars5_prior"] = ah_bars()
    d["tile"]["curves5_prior"], d["tile"]["vol_avg5_prior"] = curves(48), vol(48)
    st = _gg5([d])

    def boom(_session):
        raise RuntimeError("carry down")
    monkeypatch.setattr(st, "ah_carry", boom)
    t = _tiles(GT.build(RS, now=NOW, store=st))["SQZ"]
    assert kinds(t["ellipses"]) == ["attempt", "tennis", "run", "base", "entry"]


def test_NEGATIVE_the_outer_potential_failure_leaves_ah_prev_bound(monkeypatch):
    """A tracker doc whose `setup` is unhashable raises inside build's outer try BEFORE `ah_prev` is read → the
    pre-bound None serves; the 🎾 board still builds its cards with their ellipses (no NameError)."""
    st = _gg5([wide_doc("SQZ", {RS: rs_read()})])
    monkeypatch.setattr(st, "potentials", lambda session: [{"symbol": "SQZ", "setup": ["unhashable"]}])
    out = GT.build(RS, now=NOW, store=st)
    t = _tiles(out)["SQZ"]
    assert kinds(t["ellipses"]) == ["attempt", "tennis", "run", "base", "entry"]


def test_the_potential_sub_card_of_a_squeeze_read_carries_ellipses():
    r = rs_read("forming", ready=True, criteria=[{"key": "k3_vol", "label": "k3_vol", "ok": True, "value": "",
                                                  "need": ""}])
    d = wide_doc("SQZ", {RS: r})
    d["tile"]["bars5_prior"] = ah_bars()
    d["tile"]["curves5_prior"], d["tile"]["vol_avg5_prior"] = curves(48), vol(48)
    out = GT.build(GC.POTENTIAL_SUB, now=NOW, store=_gg5([d]))
    t = _tiles(out)["SQZ"]
    assert t["gajjala"]["setup"] == RS and "potential" in t["gajjala"]
    assert kinds(t["ellipses"]) == ["ah", "attempt", "tennis", "run", "base"]              # forming: no entry mark


# ── the three variants ───────────────────────────────────────────────────────────────────────────────────────────
def _gg1(doc1, gg5_doc):
    own = {n: FakeColl() for n in ST.OWN}
    own[ST.READS] = FakeColl([doc1])
    own[ST.PASSES] = FakeColl([latest()])
    return ST.GajjalaStore(colls=own, variant=V.GG1, shared=_gg5([gg5_doc]))


def gg1_doc():
    """A 1-minute page doc: 1-minute stamps, no `_prior` keys (run_1m.py stores none)."""
    T1 = lambda hm: f"{S.isoformat()} {hm}"                                             # noqa: E731
    r = rs_read(frame="1m", entry_bar_t=T1("09:50"))
    r["structure"] = {"tennis": box(T1("09:41"), T1("09:43"), 4.0, 4.4, 3), "run": box(T1("09:44"), T1("09:46"), 4.1,
                                                                                        4.5, 3),
                      "base": box(T1("09:47"), T1("09:49"), 4.3, 4.45, 3), "attempts": []}
    d = read_doc("SQZ", {RS: r})
    b1 = run_bars(30, start=9 * 60 + 31, step=1)
    d["tile"] = {"bars1": b1, "curves1": curves(30), "vol_avg1": vol(30),
                 "bars5": run_bars(6, start=9 * 60 + 35), "curves5": curves(6), "vol_avg5": vol(6)}
    return d


@pytest.mark.parametrize("vname", ("gg5", "gg1", "gga"))
def test_parity_ellipses_on_all_three_variants(vname):
    g5 = wide_doc("SQZ", {RS: rs_read()})
    if vname == "gg5":
        out, want = GT.build(RS, now=NOW, store=_gg5([g5])), 252
        exp = ["ah", "attempt", "tennis", "run", "base", "entry"]
    elif vname == "gg1":
        out, want = GT.build(RS, now=NOW, store=_gg1(gg1_doc(), g5), variant=V.GG1), 30
        exp = ["tennis", "run", "base", "entry"]
    else:
        st = ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=_gg5([g5]))
        out, want = GT.build(RS, now=NOW, store=st, variant=V.GGA), 252
        exp = ["ah", "attempt", "tennis", "run", "base", "entry"]                       # AH_CARRY is SHARED
    t = _tiles(out)["SQZ"]
    assert kinds(t["ellipses"]) == exp, vname
    assert len(t["bars"]) == want, vname


# ── the 🧠 potential golden (REFIX 2026-11-08): the ONLY delta this package makes is `ellipses` on 🎾 tiles ────────
def _split(doc):
    """(🎾 tiles, every other tile) across every board of a golden doc — the doc itself, not a copy."""
    rs, other = [], []
    for board in doc["boards"].values():
        for t in board.get("tiles") or []:
            (rs if (t.get("gajjala") or {}).get("setup") == RS else other).append(t)
    return rs, other


def _strip_rs_ellipses(doc):
    """A deep copy with `ellipses` dropped from every 🎾 tile of every board."""
    out = copy.deepcopy(doc)
    for t in _split(out)[0]:
        t.pop("ellipses", None)
    return out


def _golden_pair():
    import json
    from tests import test_gajjala_potential_tab as PT
    new = json.loads(PT.golden_payload())
    old = json.loads(PT.GOLDEN.read_text(encoding="utf-8"))
    return PT, old, new


def test_potential_golden_moves_only_by_rs_ellipses():
    """The 4th golden this package moves (frontend/src/components/__fixtures__/gajjala_potential_golden_2026_10_15.json):
    stripped of 🎾 `ellipses`, the served payload equals the committed file — before AND after the main session's regen
    (`GG_WRITE_GOLDEN=1 … test_gajjala_potential_tab.py -k golden`). Any other path moving fails here."""
    PT, old, new = _golden_pair()
    rs_new, other_new = _split(new)
    assert _strip_rs_ellipses(new) == _strip_rs_ellipses(old), f"the potential golden moved beyond 🎾 `ellipses` — investigate before: {PT.RECIPE}"
    assert rs_new, "the fixture day has a 🎾 tile (DDD) — the delta this guard pins"
    assert all("ellipses" in t for t in rs_new)
    assert all("ellipses" not in t for t in other_new)                                 # NEGATIVE: 🚩/💋/… untouched


def test_potential_golden_rs_forming_tile_serves_empty_ellipses():
    """The DDD 🎾 forming tile: no `structure` in the stored read, no A+ marker, no carry row → `ellipses == []`."""
    _, _, new = _golden_pair()
    tiles = _split(new)[0]
    assert any(t["symbol"] == "DDD" and t["gajjala"]["state"] == "forming" and t["ellipses"] == [] for t in tiles)


def test_potential_golden_guard_catches_a_foreign_delta():
    """NEGATIVE: the strip is narrow — a moved non-`ellipses` key on a 🎾 tile, or `ellipses` on a 🚩 tile, still differs."""
    _, old, new = _golden_pair()
    s_old = _strip_rs_ellipses(old)
    bad = copy.deepcopy(new)
    rs_tile = _split(bad)[0][0]
    rs_tile["bars"] = rs_tile["bars"][1:]
    assert _strip_rs_ellipses(bad) != s_old
    bad2 = copy.deepcopy(new)
    _split(bad2)[1][0]["ellipses"] = []
    assert _strip_rs_ellipses(bad2) != s_old
    assert not all("ellipses" not in t for t in _split(bad2)[1])
