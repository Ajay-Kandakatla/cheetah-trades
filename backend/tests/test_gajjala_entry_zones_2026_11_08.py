"""🧪 / 1-min entry zone (SPEC gg-zones §3.1 / WP be-zones-rank, 2026-11-08).

Ajay 2026-11-07, verbatim: "On the Gajjalas Audited and Gajjalas 1 min tab can you add entry signal on the chart please
like a small zone. Based on what he said, Like when its imminent with volume drying and selling pressure is low. and Also
when the pullback is ideal and close EMAs I guess based on what he says."

chart_maps/gajjala/entry_zone.py: ONE served band `gg_entry` (lo = stop, hi = trigger) on a FORMING GG1 / GGA setup tile
when IMMINENT (ready + no red-closes flag) and/or IDEAL PULLBACK (K3 volume dry + the setup's own EMA criterion). [C1]
`label` = the short word, `note` = the sentence. GG5 serves none (byte-identical). Pure reads: no Mongo but the fake
stores, no clock but the pinned one. UNMEASURED.
"""
from __future__ import annotations

import re

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import entry_zone as EZ
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import NOW, R, latest, read_doc, scan_doc, store_with

BF, KF, HF, VCP, RS = "bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze"
BASE = {"from_t": "2026-10-13 10:00", "to_t": "2026-10-13 10:10", "bars": 3}
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
GGA_OWN = (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY, ST.EXITS)


def C(key, ok, value=""):
    return {"key": key, "label": key, "ok": ok, "value": value, "need": ""}


def ready_bf(**kw):
    """A forming READY Bull Flag: every criterion met, a 3-bar pullback, red closes under the wait."""
    r = R(BF, "forming", ready=True, base=dict(BASE), red_closes=1,
          criteria=[C("k2", True), C("k3_vol", True), C("k4", True)])
    r.update(kw)
    return r


def building(setup, crit, **kw):
    """A forming read that is NOT ready (a length minimum still pending) with the given criteria rows."""
    r = R(setup, "forming", ready=False, base=dict(BASE), red_closes=1, criteria=crit)
    r.update(kw)
    return r


# ── the words ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_zone_words_live_in_both_variant_tables_only():
    for k in (EZ.ZONE_LABEL_KEY, EZ.ZONE_NOTE_KEY):
        assert V.WORDS_1M[k] == V.WORDS_GGA[k], k
        assert V.word(k, V.GG5) is None and V.word(k, None) is None, k                  # NEGATIVE: GG5 has none
    assert V.word(EZ.ZONE_LABEL_KEY, V.GG1) == V.word(EZ.ZONE_LABEL_KEY, V.GGA) == "entry zone"
    assert V.WORDS_1M[EZ.ZONE_NOTE_KEY] == "{why} · UNMEASURED"


def test_why_imminent_names_the_red_closes_wait_under_chip_and_drops_it_under_off(monkeypatch):
    """[C4] "chip" (shipped) → the clause names RED_CLOSES_WAIT; "off" → no red-closes clause (the engine checks none)."""
    assert GC.RED_CLOSES_MODE == "chip"
    assert EZ.why_imminent() == ("imminent — trigger armed, volume dry, no more than "
                                 f"{GC.RED_CLOSES_WAIT} red closes in a row")
    monkeypatch.setattr(GC, "RED_CLOSES_MODE", "off")
    assert EZ.why_imminent() == "imminent — trigger armed, volume dry"
    assert "red closes" not in EZ.why_imminent()


def test_why_pullback_reads_k6_merge_pct_at_call_time(monkeypatch):
    assert EZ.why_pullback("k6_merge").endswith(f"within {GC.K6_MERGE_PCT:g}%")
    monkeypatch.setattr(GC, "K6_MERGE_PCT", 0.25)
    assert EZ.why_pullback("k6_merge").endswith("within 0.25%")
    assert "9 EMA" in EZ.why_pullback("k5a_honor") and "21 EMA" in EZ.why_pullback("k7_ema21")
    with pytest.raises(KeyError):                                                       # NEGATIVE: no other rule
        EZ.why_pullback("k3_vol")


# ── the band ──────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("v", (V.GG1, V.GGA), ids=("gg1", "gga"))
def test_a_ready_forming_bull_flag_serves_one_band_with_the_variant_words(v):
    r = ready_bf()
    out = EZ.bands(r, v)
    assert len(out) == 1
    b = out[0]
    assert set(b) == {"kind", "lo", "hi", "label", "note"}
    assert b["kind"] == EZ.ZONE_KIND == "gg_entry"
    assert b["lo"] == r["stop"] and b["hi"] == r["trigger"] and b["lo"] < b["hi"]
    assert b["label"] == V.word("zone_label", v) == "entry zone"                        # [C1] the SHORT word
    assert b["note"] == V.word("zone_note", v, why=EZ.why_imminent())
    assert "UNMEASURED" in b["note"]
    assert "—" not in b["label"] and len(b["label"]) < len(b["note"])                   # [C1]
    for s in (b["label"], b["note"]):
        assert "buy" not in s.lower() and not EDGE.search(s) and not B_WORD.search(s) and "5-minute" not in s


@pytest.mark.parametrize("v", (None, V.GG5), ids=("none", "gg5"))
def test_NEGATIVE_gg5_serves_no_band(v):
    assert EZ.bands(ready_bf(), v) == []
    assert EZ.reasons(ready_bf()) == [EZ.IMMINENT_KEY]                                   # the read itself qualifies


@pytest.mark.parametrize("state", ("partial", "aplus", "triggered", "stopped", "invalid", "none", "aplus_held"))
def test_NEGATIVE_no_band_off_a_forming_read(state):
    r = ready_bf(state=state)
    assert EZ.reasons(r) == [] and EZ.bands(r, V.GG1) == [] and EZ.bands(r, V.GGA) == []


@pytest.mark.parametrize("base", (None, {}, {"bars": 0}, {"bars": None}, {"bars": True}, "3 bars"))
def test_NEGATIVE_no_band_without_a_base_bar(base):
    """K3 volume is vacuously True over an EMPTY pullback (detectors.k3_vol_ok) — the base-span guard is load-bearing."""
    for r in (ready_bf(base=base),
              building(KF, [C("k3_vol", True), C("k5a_honor", True)], base=base)):
        assert EZ.reasons(r) == [] and EZ.bands(r, V.GG1) == [], base


def test_red_closes_boundary_wait_is_a_band_wait_plus_one_is_none():
    """[C8] red_closes == RED_CLOSES_WAIT → the chip engine shows no flag → band; == WAIT + 1 → no imminent."""
    w = GC.RED_CLOSES_WAIT
    assert CX.red_closes_chip(w) is None and CX.red_closes_chip(w + 1) is not None
    assert EZ.reasons(ready_bf(red_closes=w)) == [EZ.IMMINENT_KEY]
    assert len(EZ.bands(ready_bf(red_closes=w), V.GG1)) == 1
    assert EZ.reasons(ready_bf(red_closes=w + 1)) == []
    assert EZ.bands(ready_bf(red_closes=w + 1), V.GG1) == []                             # a Bull Flag: imminent only
    hf = ready_bf(setup=HF, red_closes=w + 1, criteria=[C("k3_vol", True), C("k6_merge", True)])
    assert EZ.reasons(hf) == ["k6_merge"]                                                # the pullback leg survives


def test_red_closes_mode_off_allows_imminent_and_drops_the_clause(monkeypatch):
    """[C4] under "off" the chip engine returns None for every count → imminent allowed; the note has no clause."""
    monkeypatch.setattr(GC, "RED_CLOSES_MODE", "off")
    r = ready_bf(red_closes=GC.RED_CLOSES_WAIT + 5)
    assert EZ.reasons(r) == [EZ.IMMINENT_KEY]
    assert EZ.bands(r, V.GG1)[0]["note"] == "imminent — trigger armed, volume dry · UNMEASURED"


@pytest.mark.parametrize("trig_stop", ((4.0, 4.0), (3.9, 4.0), (None, 4.0), (4.0, None), (0.0, 0.0)))
def test_NEGATIVE_no_band_without_a_plan(trig_stop):
    t, s = trig_stop
    assert EZ.bands(ready_bf(trigger=t, stop=s), V.GG1) == [], trig_stop


def test_kiss_fly_building_with_dry_volume_and_the_9_ema_honoured():
    r = building(KF, [C("k2", True), C("k3_vol", True), C("k5a_honor", True), C("k5_kiss", False)])
    assert EZ.reasons(r) == ["k5a_honor"]
    assert EZ.bands(r, V.GG1)[0]["note"] == EZ.why_pullback("k5a_honor") + " · UNMEASURED"
    dry_off = building(KF, [C("k3_vol", False), C("k5a_honor", True)])
    assert EZ.reasons(dry_off) == [] and EZ.bands(dry_off, V.GG1) == []                 # NEGATIVE: volume not dry
    no_ema = building(KF, [C("k3_vol", True), C("k5a_honor", False)])
    assert EZ.reasons(no_ema) == []                                                      # NEGATIVE: the EMA failed
    unjudged = building(KF, [C("k3_vol", True), C("k5a_honor", None)])
    assert EZ.reasons(unjudged) == []                                                    # NEGATIVE: None is not True


def test_NEGATIVE_no_honour_row_is_no_ema_leg_never_a_key_error(monkeypatch):
    """[C5] KF_HONOR_ALL_PULLBACK_CLOSES False → the 💋 read carries no `k5a_honor` row → no EMA leg, no crash."""
    monkeypatch.setattr(GC, "KF_HONOR_ALL_PULLBACK_CLOSES", False)
    r = building(KF, [C("k2", True), C("k3_vol", True), C("k5_kiss", False)])
    assert EZ.reasons(r) == [] and EZ.bands(r, V.GGA) == []
    assert EZ.reasons(dict(r, ready=True, criteria=[C("k3_vol", True)])) == [EZ.IMMINENT_KEY]
    assert EZ.reasons(dict(r, criteria=None)) == [] and EZ.reasons(dict(r, criteria=["junk", 3])) == []


def test_vcp_holds_the_21_ema_and_fade_merged():
    vcp = building(VCP, [C("k4_cycles", True), C("k3_vol", True), C("k7_ema21", True)])
    assert EZ.reasons(vcp) == ["k7_ema21"]
    hf = building(HF, [C("k4", True), C("k3_vol", True), C("k6_merge", True)])
    assert EZ.reasons(hf) == ["k6_merge"]
    assert EZ.reasons(dict(hf, criteria=[C("k3_vol", True), C("k6_merge", False)])) == []   # NEGATIVE


def test_NEGATIVE_bull_flag_and_squeeze_have_no_pullback_leg():
    """🚩 and 🎾 have no EMA criterion → a building read never zones (imminent only)."""
    for setup in (BF, RS):
        r = building(setup, [C("k3_vol", True), C("k6_merge", True), C("k5a_honor", True), C("k7_ema21", True)])
        assert EZ.reasons(r) == [] and EZ.bands(r, V.GG1) == [], setup
    assert EZ.reasons(building(RS, [C("k3_vol", True)], ready=True)) == [EZ.IMMINENT_KEY]


def test_a_ready_fade_with_merged_emas_carries_both_reasons_imminent_first():
    r = ready_bf(setup=HF, criteria=[C("k4", True), C("k3_vol", True), C("k6_merge", True)])
    assert EZ.reasons(r) == [EZ.IMMINENT_KEY, "k6_merge"]
    assert EZ.bands(r, V.GGA)[0]["note"] == (EZ.why_imminent() + " · " + EZ.why_pullback("k6_merge")
                                             + " · UNMEASURED")


def test_the_real_detector_fade_read_round_trips():
    """detectors.fade_on on the merged base before the break (FX.hf_frame, entry None) → forming, ready, K3 + K6 ✓ →
    both reasons; the broken flag (A+) → none; the EMAs apart (partial) → none."""
    r = D.fade_on(FX.hf_frame(entry=None))
    assert r["state"] == "forming" and r["ready"] is True and r["base"]["bars"] >= 1
    assert EZ.reasons(r) == [EZ.IMMINENT_KEY, "k6_merge"]
    b = EZ.bands(r, V.GG1)[0]
    assert (b["lo"], b["hi"]) == (r["stop"], r["trigger"])
    assert EZ.reasons(D.fade_on(FX.hf_frame())) == []                                    # A+ — the entry has printed
    assert EZ.reasons(D.fade_on(FX.hf_frame(merged=False, entry=None))) == []            # partial — K6 missed


def test_reasons_never_raises_on_junk():
    for junk in (None, {}, [], "x", {"state": "forming"}, {"state": "forming", "base": BASE, "trigger": "a"}):
        assert EZ.reasons(junk) == [], junk


# ── the served board ──────────────────────────────────────────────────────────────────────────────────────────────
def _shared(reads):
    return store_with(reads=[read_doc(s, {r["setup"]: r}) for s, r in reads.items()],
                      scans=[scan_doc(s) for s in reads], passes=[latest()])


def _gg1(reads):
    own = {n: FakeColl() for n in ST.OWN}
    own[ST.READS] = FakeColl([read_doc(s, {r["setup"]: r}) for s, r in reads.items()])
    own[ST.PASSES] = FakeColl([latest()])
    return ST.GajjalaStore(colls=own, variant=V.GG1, shared=_shared(reads))


def _gga(reads):
    return ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=_shared(reads))


READS = {"ZON": ready_bf(), "OFF": ready_bf(red_closes=GC.RED_CLOSES_WAIT + 1)}


@pytest.mark.parametrize("v", (V.GG1, V.GGA), ids=("gg1", "gga"))
def test_build_serves_the_band_on_the_setup_sub_and_the_potential_sub(v):
    st = _gg1(READS) if v is V.GG1 else _gga(READS)
    for sub in (BF, GC.POTENTIAL_SUB):
        out = GT.build(sub, now=NOW, store=st, variant=v)
        by = {t["symbol"]: t for t in out["tiles"]}
        assert set(by) >= {"ZON", "OFF"}, sub
        z = by["ZON"]
        assert z["bands"] == [{"kind": "gg_entry", "lo": z["gajjala"]["stop"], "hi": z["gajjala"]["trigger"],
                               "label": "entry zone", "note": V.word("zone_note", v, why=EZ.why_imminent())}], sub
        assert by["OFF"]["bands"] == [], sub                                             # NEGATIVE: WAIT + 1
        assert by["OFF"]["gajjala"]["chips"]                                             # the card is still served


def test_NEGATIVE_gg5_build_serves_no_band_on_any_tile():
    st = _shared(READS)
    for sub in (BF, GC.POTENTIAL_SUB):
        out = GT.build(sub, now=NOW, store=st)
        assert out["tiles"] and all(t["bands"] == [] for t in out["tiles"]), sub
        assert "variant" not in out


def test_NEGATIVE_a_list_tile_never_zones():
    """☀️ / 🌙 rows (tab._list_tile) serve `bands: []` whatever the read doc holds, on every variant."""
    doc = read_doc("ZON", {BF: ready_bf()})
    sess = {"tape": "premarket", "label": "today"}
    for v in (None, V.GG1, V.GGA):
        t = GT._list_tile("ZON", "premarket", doc, "5m", scan_row={"price": 4.05}, sess=sess, listed=None,
                          extra={"state_label": "listed"}, v=v)
        assert t["bands"] == [], v


def test_the_zone_reads_the_stored_read_not_the_served_block():
    """`base` is on the stored read only (never served on `gajjala`), and the band is built from it."""
    out = GT.build(BF, now=NOW, store=_gg1(READS), variant=V.GG1)
    t = next(t for t in out["tiles"] if t["symbol"] == "ZON")
    assert "base" not in t["gajjala"] and t["bands"]


def test_the_new_module_is_under_the_source_guard():
    from tests.test_gajjala_source_guard import FILES
    assert "entry_zone.py" in {f.name for f in FILES}
    src = (FILES[0].parent / "entry_zone.py").read_text(encoding="utf-8")
    assert not B_WORD.search(src) and "fake" not in src.lower()


def test_NEGATIVE_the_zone_note_without_why_raises_never_serves_a_brace():
    """REFIX 2026-11-08: `zone_note` = "{why} · UNMEASURED" on BOTH tables. A caller that forgets `why` fails loudly
    (KeyError) rather than serving a half sentence; with `why` the text carries no brace. GG5 has no such word."""
    for v in (V.GG1, V.GGA):
        with pytest.raises(KeyError):
            V.word("zone_note", v)
        txt = V.word("zone_note", v, why="why")
        assert txt == "why · UNMEASURED" and "{" not in txt, v
        assert V.word("zone_label", v) == "entry zone", v
    assert V.word("zone_note", V.GG5, why="why") is None
