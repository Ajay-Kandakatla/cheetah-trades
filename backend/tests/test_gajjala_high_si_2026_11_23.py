"""🩳 High SI sub on 🚩 Gajjala's 5-min tab — membership (the two-float rule), the served words, the card, the wiring
(SPEC highsi §3.1–3.4, WP be-sub, 2026-11-23).

Ajay 2026-11-23 (voice-typed), verbatim: "Can you create a tab similarly like Divergent with high charging tested, SHO
tag, and low floats similar to what we've done in Divergent tab under Gazilla?" [voice typing: "high charging tested" =
high short interest, "Gazilla" = Gajjala] · "New tab like divergence*".

Hermetic: FakeColl stores only (conftest refuses MongoClient). Short-interest blocks are built by the house
`short_interest.read.si_block` over synthetic cache docs (never typed by hand), so the tier / float_check leaves are the
house read's own. The four 2026-11-23 disagreement shapes (GMEX, LABT, KITT, SMX) use the probe's share counts.
"""
from __future__ import annotations

import ast
import inspect
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as DT
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC
from short_interest import client as SIC
from short_interest import read as SR
from supply_demand import rules_info as RI
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import scan_doc

ET = ZoneInfo("America/New_York")
S = date(2026, 11, 13)                          # a Friday, a market day
PREV = date(2026, 11, 12)
SETTLE = "2026-10-31"                           # fresh on S (published 11-10, next due 11-27)
B_WORD = re.compile("b" + "ounc", re.I)
HSUB = GC.HIGH_SI_SUB
CAP = GC.K8_MAX_FLOAT


def at(hh, mm, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET)


NOW = at(13, 2)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ────────────────────────────────────────────────────────────────────────────────────────────────────
def blk(sym, si, fl, so=None, *, settle=SETTLE, today=S, v=2):
    doc = {"symbol": sym, "short_interest": si, "settlement_date": settle, "v": v, "float_shares": fl,
           "shares_outstanding": so, "float_source": "yahoo", "float_asof": "2026-10-30", "fetched_at": 1.7e9}
    return SR.si_block(doc, today)


def fr(shares, *, src="float", suspect=False, text=None):
    d = {"shares": shares, "src": src, "suspect": suspect}
    if text is not None:
        d["text"] = text
    return d


# the probe's 2026-11-23 shapes (share counts from spec §1.6)
GMEX = (blk("GMEX", round(0.6287 * 20235), 20235), fr(361428))
LABT = (blk("LABT", round(0.1804 * 847661), 847661), fr(3201536))
KITT = (blk("KITT", round(0.0369 * 5527831), 5527831), fr(1612787))
SMX = (blk("SMX", round(0.0603 * 791704), 791704), fr(282748))
HIGH = (blk("HIGH", 300000, 2000000), fr(2100000))                              # 15 % / 14.29 % — both High
EXTR = (blk("EXTR", 600000, 2000000, 3000000), fr(2000000))                      # 30 % of float, 20 % of shares out
AKAN = (blk("AKAN", 1000000, 2750000, 12345679), fr(2750000))                    # 36.4 % of float, 8.1 % of shares


def test_the_shapes_are_the_house_reads():
    assert GMEX[0]["tier"] == SR.TIER_HIGH and GMEX[0]["float_check"] == SR.FLOAT_UNCHECKED
    assert LABT[0]["tier"] == SR.TIER_HIGH and KITT[0]["tier"] == SR.TIER_LOW and SMX[0]["tier"] == SR.TIER_MODERATE
    assert HIGH[0]["tier"] == SR.TIER_HIGH and EXTR[0]["tier"] == SR.TIER_EXTREME
    assert AKAN[0]["tier"] == SR.TIER_HIGH and AKAN[0]["float_check"] == SR.FLOAT_UNCONFIRMED
    assert all(b[0]["status"] == "ok" for b in (GMEX, LABT, KITT, SMX, HIGH, EXTR, AKAN))


# ── classify: POSITIVE ──────────────────────────────────────────────────────────────────────────────────────────
def test_classify_lists_high_on_both_floats_under_the_cap():
    c = HS.classify(*HIGH)
    assert c["listed"] is True and c["reason"] is None and c["tier"] == SR.TIER_HIGH and c["hi_card"] is True
    assert c["float_shares"] == 2100000 and c["si_float_shares"] == 2000000 and c["pct_card"] == 14.29


def test_classify_lists_extreme_confirmed_and_the_akan_shape_unconfirmed():
    assert HS.classify(*EXTR)["listed"] is True and HS.classify(*EXTR)["tier"] == SR.TIER_EXTREME
    c = HS.classify(*AKAN)
    assert c["listed"] is True and c["float_check"] == SR.FLOAT_UNCONFIRMED


def test_classify_card_float_exactly_the_cap_lists_and_one_over_does_not():
    b = blk("CAPX", 3_000_000, 9_000_000)
    assert HS.classify(b, fr(CAP))["listed"] is True
    assert HS.classify(b, fr(CAP + 1))["reason"] == "float_over"                # NEGATIVE


def test_classify_record_float_exactly_the_cap_lists_and_one_over_is_si_float_over():
    assert HS.classify(blk("RECX", 2_000_000, CAP), fr(9_000_000))["listed"] is True
    c = HS.classify(blk("RECY", 2_000_000, CAP + 1), fr(9_000_000))             # NEGATIVE
    assert c["listed"] is False and c["reason"] == "si_float_over"


def test_card_pct_exactly_the_high_cut_lists_and_one_hundredth_under_does_not():
    b = blk("CUT", 100_000, 500_000)                                            # 20 % on the record — EXTREME → High (unchecked)
    at_cut = fr(int(100_000 / (SIC.SI_ELEV_PCT / 100.0)))
    assert HS.card_pct(b, at_cut) == SIC.SI_ELEV_PCT and HS.classify(b, at_cut)["listed"] is True
    under = fr(int(round(100_000 / ((SIC.SI_ELEV_PCT - 0.01) / 100.0))))
    assert HS.card_pct(b, under) == pytest.approx(SIC.SI_ELEV_PCT - 0.01)
    c = HS.classify(b, under)                                                   # NEGATIVE
    assert c["listed"] is False and c["reason"] == "floats_disagree"


# ── classify: NEGATIVES, one flip each ──────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_block_no_record_and_no_si_shares():
    assert HS.classify(None, fr(1_000_000))["reason"] == "no_si"
    assert HS.classify("junk", fr(1_000_000))["reason"] == "no_si"
    nr = SR.si_block({"symbol": "NRX", "fetched_at": 1.7e9}, S)
    assert nr["status"] == "no_record" and HS.classify(nr, fr(1_000_000))["reason"] == "no_si"
    b = dict(HIGH[0], si_shares=None)
    assert HS.classify(b, HIGH[1])["reason"] == "no_si"


def test_NEGATIVE_stale_read_the_akan_on_11_30_shape():
    b = blk("AKAN", 1000000, 2750000, 12345679, settle="2026-09-15")
    assert b["status"] == "stale"
    assert HS.classify(b, AKAN[1])["reason"] == "stale" and not HS.classify(b, AKAN[1])["listed"]


def test_NEGATIVE_tier_none_on_an_ok_shares_out_only_read():
    b = blk("SHO", 300000, None, 2_000_000)
    assert b["status"] == "ok" and b["tier"] is None and b["headline_basis"] == "shares_out"
    assert HS.classify(b, fr(1_500_000))["reason"] == "no_tier"


def test_NEGATIVE_low_and_moderate():
    assert HS.classify(blk("LOW", 10_000, 1_000_000), fr(5_000_000))["reason"] == "not_high"
    assert HS.classify(blk("MOD", 70_000, 1_000_000), fr(5_000_000))["reason"] == "not_high"


@pytest.mark.parametrize("bad", [None, fr(None), fr(0), fr(-5), fr(2_000_000, suspect=True), "junk", fr("x")])
def test_NEGATIVE_card_float_unknown(bad):
    assert GC.FLOAT_SUSPECT_POLICY == "ineligible"
    c = HS.classify(HIGH[0], bad)
    assert c["listed"] is False and c["reason"] == "float_unknown"


def test_NEGATIVE_junk_leaves_never_raise():
    for b in ({}, {"status": "ok"}, {"status": "ok", "si_shares": "x", "tier": "high"},
              {"status": "ok", "si_shares": 5, "tier": object()}, {"status": None, "si_shares": 1e400}, []):
        for f in (None, {}, {"shares": float("nan")}, {"shares": float("inf")}, 7):
            c = HS.classify(b, f)
            assert c["listed"] is False and c["reason"] in HS.REASONS


# ── the two-float rule [C1] ─────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_gmex_shape_high_on_the_record_under_the_cut_on_the_card():
    c = HS.classify(*GMEX)
    assert c["tier"] == SR.TIER_HIGH and c["pct_card"] == 3.52
    assert c["listed"] is False and c["reason"] == "floats_disagree"


def test_NEGATIVE_labt_shape():
    c = HS.classify(*LABT)
    assert c["pct_card"] == 4.78 and c["listed"] is False and c["reason"] == "floats_disagree"


def test_NEGATIVE_kitt_shape_low_on_the_record_high_on_the_card():
    c = HS.classify(*KITT)
    assert c["tier"] == SR.TIER_LOW and c["pct_card"] >= SIC.SI_ELEV_PCT
    assert c["listed"] is False and c["reason"] == "floats_disagree"
    assert HS.classify(*SMX)["reason"] == "floats_disagree"


def test_NEGATIVE_kitt_shape_with_the_card_float_over_the_cap_is_not_high():
    b = blk("KITX", 2_000_000, 60_000_000)                                       # 3.33 % on the record — Low
    f = fr(CAP + 1)                                                              # 20 %+ on the card, over the cap
    assert HS.card_pct(b, f) >= SIC.SI_ELEV_PCT
    assert HS.classify(b, f)["reason"] == "not_high"


def test_moving_the_high_cut_moves_both_sides_of_the_rule(monkeypatch):
    assert HS.classify(*LABT)["reason"] == "floats_disagree"
    monkeypatch.setattr(SIC, "SI_MODERATE_PCT", 3.0)                             # the ladder stays in order
    monkeypatch.setattr(SIC, "SI_ELEV_PCT", 4.0)                                 # the card side clears now (4.78 %)
    b = blk("LABT", round(0.1804 * 847661), 847661)
    assert HS.classify(b, LABT[1])["listed"] is True
    monkeypatch.setattr(SIC, "SI_ELEV_PCT", 19.0)                                # the record side drops to Moderate
    b = blk("LABT", round(0.1804 * 847661), 847661)
    assert b["tier"] == SR.TIER_MODERATE and HS.classify(b, LABT[1])["reason"] == "not_high"


def test_moving_the_high_cut_moves_membership(monkeypatch):
    assert HS.classify(*HIGH)["listed"] is True
    monkeypatch.setattr(SIC, "SI_ELEV_PCT", 16.0)
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 25.0)
    assert HS.classify(blk("HIGH", 300000, 2000000), HIGH[1])["reason"] == "not_high"


def test_card_pct_none_on_a_missing_or_zero_side_and_never_raises():
    assert HS.card_pct(None, fr(1)) is None and HS.card_pct(HIGH[0], None) is None
    assert HS.card_pct(HIGH[0], fr(0)) is None and HS.card_pct(dict(HIGH[0], si_shares=0), fr(1000)) is None
    assert HS.card_pct({"si_shares": "x"}, fr(1000)) is None and HS.card_pct("junk", "junk") is None


def test_tiers_read_the_house_constants():
    assert HS.TIERS == (SR.TIER_HIGH, SR.TIER_EXTREME)
    assert GC.HIGH_SI_MAX_FLOAT == GC.K8_MAX_FLOAT


def test_moving_the_cap_moves_membership_and_every_served_sentence(monkeypatch):
    monkeypatch.setattr(GC, "HIGH_SI_MAX_FLOAT", 1_234_567)
    assert HS.classify(*HIGH)["reason"] == "float_over"
    ev = {"rows": [], "counts": dict({r: 0 for r in HS.REASONS}, float_over=1), "no_tier_low": ["ZZ"], "n_read": 1,
          "faults": [], "over": [{"symbol": "HIGH", "which": "card", "float_text": "Float 2.1M"}]}
    for text in (HS.title(), HS.rule_text(), HS.counts_text(ev), HS.no_tier_text(ev), HS.empty_today(),
                 HS.empty_session("x")):
        assert "1,234,567" in text and "10,000,000" not in text, text


# ── parity: the card float is the K8 gate's float ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("read", [fr(5_000_000), fr(CAP), fr(CAP + 1), fr(4_000_000, src="shares_out_yf"),
                                  fr(4_000_000, src="shares_out_massive"), fr(4_000_000, suspect=True), fr(None),
                                  None])
def test_float_shares_agrees_with_the_k8_gate(read):
    r = {"setup": "reversal_squeeze", "state": "forming", "meta": {}, "as_of_bar_t": None}
    gated = DT._float_gate(r, read)
    k8_ok = gated is r
    fs = HS.float_shares(read)
    assert k8_ok == (fs is not None and fs <= GC.K8_MAX_FLOAT)


# ── si_blocks ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_si_blocks_chunks_and_never_drops(monkeypatch):
    calls = []

    def fake_map(syms, db=None, today=None):
        calls.append(list(syms))
        assert len(syms) <= SR.MAP_MAX_SYMBOLS
        return {s: {"symbol": s} for s in syms}
    monkeypatch.setattr(SR.SIC, "_get_db", lambda: object())
    monkeypatch.setattr(SR, "si_map", fake_map)
    syms = ["S%03d" % i for i in range(450)]
    out = HS.si_blocks(syms + ["s001", ""], today=S)
    assert len(calls) == 3 and len(out) == 450 and set(out) == set(syms)


def test_NEGATIVE_one_si_map_call_drops_names_beyond_the_cap():
    assert SR.MAP_MAX_SYMBOLS < 450                                              # a single call would drop 250


def test_NEGATIVE_si_blocks_db_none_is_the_fault(monkeypatch):
    monkeypatch.setattr(SR.SIC, "_get_db", lambda: None)
    assert HS.si_blocks(["AAA"], today=S) is None


# ── evaluate ────────────────────────────────────────────────────────────────────────────────────────────────────
def rdoc(sym, float_read=None, *, ctx=None, tile=None):
    c = dict(ctx or {})
    if float_read is not None:
        c["float"] = float_read
    return {"_id": f"{S.isoformat()}|{sym}", "date": S.isoformat(), "symbol": sym, "setups": {}, "ctx": c,
            "tile": tile if tile is not None else tile_of(), "updated_at": NOW, "at": NOW}


def ev_of(reads, blocks, *, volumes=None, listed=None, v=None):
    vols = volumes or {}
    return HS.evaluate(reads, scan_row=lambda s: {"volume": vols.get(s)}, session=S, now=NOW, v=v,
                       si_read=lambda syms: blocks, listed=listed)


def test_evaluate_lists_orders_and_counts():
    reads = {"HIGH": rdoc("HIGH", HIGH[1]), "EXTR": rdoc("EXTR", EXTR[1]), "AKAN": rdoc("AKAN", AKAN[1]),
             "GMEX": rdoc("GMEX", GMEX[1]), "KITT": rdoc("KITT", KITT[1]), "LOW": rdoc("LOW", fr(5_000_000)),
             "BIG": rdoc("BIG", fr(CAP + 1)), "NOSI": rdoc("NOSI", fr(1_000_000)),
             "SHO": rdoc("SHO", fr(1_500_000)), "SHOB": rdoc("SHOB", fr(CAP + 1))}
    blocks = {"HIGH": HIGH[0], "EXTR": EXTR[0], "AKAN": AKAN[0], "GMEX": GMEX[0], "KITT": KITT[0],
              "LOW": blk("LOW", 10_000, 1_000_000), "BIG": blk("BIG", 3_000_000, 9_000_000),
              "SHO": blk("SHO", 300000, None, 2_000_000), "SHOB": blk("SHOB", 300000, None, 2_000_000)}
    ev = ev_of(reads, blocks, volumes={"HIGH": 3e6, "EXTR": 3e6, "AKAN": None})
    assert [r["symbol"] for r in ev["rows"]] == ["EXTR", "HIGH", "AKAN"]          # volume ↓, float ↑, unknown last
    assert ev["counts"]["floats_disagree"] == 2 and ev["counts"]["float_over"] == 1
    assert ev["counts"]["not_high"] == 1 and ev["counts"]["no_si"] == 1 and ev["counts"]["no_tier"] == 2
    assert sum(ev["counts"].values()) == ev["n_read"] - len(ev["rows"]) - len(ev["faults"])
    assert [d["symbol"] for d in ev["disagree"]] == ["GMEX", "KITT"]
    g = ev["disagree"][0]
    assert (g["tier_word"], g["pct_record"], g["si_float_shares"], g["pct_card"], g["float_shares"]) == (
        "High", 62.87, 20235, 3.52, 361428)
    assert ev["over"] == [{"symbol": "BIG", "which": "card", "float_text": "Float 10.0M"}]
    assert ev["no_tier_low"] == ["SHO"]                                          # NEGATIVE: SHOB's card float is over the cap
    assert ev["unconfirmed"] == 1 and ev["settlement"]["settlement_date"] == SETTLE
    r = ev["rows"][2]["read"]
    assert r["tier_word"] == "High" and r["session_volume"] is None and r["si_chip"] == AKAN[0]["chip"]


def test_evaluate_order_equals_the_order_key_slot():
    reads = {"A": rdoc("A", fr(3_000_000)), "B": rdoc("B", fr(2_000_000)), "C": rdoc("C", fr(2_000_000)),
             "D": rdoc("D", fr(1_000_000))}
    blocks = {s: blk(s, 900_000, 3_000_000) for s in reads}
    vols = {"A": 5e6, "B": 2e6, "C": 2e6, "D": None}
    ev = ev_of(reads, blocks, volumes=vols)
    got = [r["symbol"] for r in ev["rows"]]
    assert got == ["A", "B", "C", "D"]

    def card_(sym):
        return {"symbol": sym, "gajjala": {"setup": "bull_flag", "state": "forming", "ready": False,
                                           "_volume": vols[sym], "_float_shares": HS.float_shares(reads[sym]["ctx"]["float"])}}
    for a, b in (("A", "B"), ("B", "D")):
        ka, kb = GT.order_key(card_(a)), GT.order_key(card_(b))
        assert ka[1:3] == GT.vol_float_slot(vols[a], card_(a)["gajjala"]["_float_shares"])
        assert (ka < kb) == (got.index(a) < got.index(b))


def test_vol_float_slot_is_byte_equal_to_the_old_order_key_slot():
    for vol, fl in ((None, None), (0, 0), (2e6, 3e6), ("x", 5), (float("nan"), 1), (-1, -2), (1, None)):
        v = GT._f(vol)
        old = (-v if v is not None else float("inf"), float(fl) if fl else float("inf"))
        assert GT.vol_float_slot(vol, fl) == old


SK_LINE = "    sk = ((vkey,) if has_vol else ()) + ((fkey,) if has_fl else ())"


def test_order_key_sk_line_stays_byte_identical():
    import inspect
    src = inspect.getsource(GT.order_key)
    lines = src.splitlines()
    hits = [i for i, ln in enumerate(lines) if ln.startswith(SK_LINE)]
    assert len(hits) == 1, "contracts.mjs pins the sk line byte-identical"
    assert lines[hits[0] + 1].strip().startswith("sk = _kf_slot(g) + sk")
    assert "sk =((vkey,)" not in src                                              # NEGATIVE: the 11-23 dropped space
    assert not any(ln.startswith(SK_LINE.replace("sk = ", "sk =")) for ln in lines)


def test_evaluate_carried_and_adds_on_listed_rows_only():
    reads = {"HIGH": rdoc("HIGH", HIGH[1], ctx={"trader_text": "📌 algo888"}),
             "EXTR": rdoc("EXTR", EXTR[1], ctx={"promo_text": "🎪 Promo"}),
             "GMEX": rdoc("GMEX", GMEX[1], ctx={"trader_text": "📌 x"})}
    blocks = {"HIGH": HIGH[0], "EXTR": EXTR[0], "GMEX": GMEX[0]}
    listed = {"HIGH": {"last_qualified": S.isoformat()}, "EXTR": {"last_qualified": PREV.isoformat()},
              "GMEX": {"last_qualified": PREV.isoformat()}}
    ev = ev_of(reads, blocks, listed=listed)
    by = {r["symbol"]: r["read"] for r in ev["rows"]}
    assert by["HIGH"]["carried"] is False and by["EXTR"]["carried"] is True and ev["carried"] == 1
    assert ev["adds"] == [{"symbol": "EXTR", "add_text": "🎪 Promo"}, {"symbol": "HIGH", "add_text": "📌 algo888"}] or \
        sorted(a["symbol"] for a in ev["adds"]) == ["EXTR", "HIGH"]
    assert "GMEX" not in [a["symbol"] for a in ev["adds"]]                       # NEGATIVE: not a listed row
    t = HS.adds_text(ev)
    assert "Of the 2 listed here: 1 qualified on his scanner today · 1 carried" in t
    assert "📌 algo888" in t and "🎪 Promo" in t


def test_NEGATIVE_listed_none_serves_carried_none_and_adds_text_still():
    ev = ev_of({"HIGH": rdoc("HIGH", HIGH[1])}, {"HIGH": HIGH[0]}, listed=None)
    assert ev["rows"][0]["read"]["carried"] is None and ev["carried"] == 0
    assert HS.adds_text(ev).startswith("Of the 1 listed here: 1 qualified")
    ev2 = ev_of({"HIGH": rdoc("HIGH", HIGH[1])}, {"HIGH": HIGH[0]}, listed={})
    assert ev2["rows"][0]["read"]["carried"] is None


def test_NEGATIVE_a_raising_name_is_a_fault_and_the_rest_stand():
    reads = {"HIGH": rdoc("HIGH", HIGH[1]), "BAD": rdoc("BAD", HIGH[1])}

    def row(s):
        if s == "BAD":
            raise RuntimeError("boom")
        return {"volume": 2e6}
    ev = HS.evaluate(reads, scan_row=row, session=S, now=NOW, si_read=lambda syms: {"HIGH": HIGH[0], "BAD": HIGH[0]})
    assert ev["faults"] == ["BAD"] and [r["symbol"] for r in ev["rows"]] == ["HIGH"]
    assert "1 unreadable this time" in HS.counts_text(ev)


def test_NEGATIVE_unread_si_raises_and_non_gg5_is_empty():
    with pytest.raises(RuntimeError):
        ev_of({"HIGH": rdoc("HIGH", HIGH[1])}, None)
    with pytest.raises(TypeError):
        HS.evaluate([], scan_row=dict, session=S, now=NOW)
    for v in (V.GG1, V.GGA):
        ev = ev_of({"HIGH": rdoc("HIGH", HIGH[1])}, {"HIGH": HIGH[0]}, v=v)
        assert ev["rows"] == [] and ev["n_read"] == 0


# ── words ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _all_words(ev=None):
    ev = ev or {"rows": [], "counts": {r: 0 for r in HS.REASONS}, "n_read": 0}
    return [HS.title(), HS.rule_text(), HS.push_text(), HS.honesty(), HS.cohort_text(), HS.counts_text(ev),
            HS.ORDER_NOTE, HS.FAULT_TEXT, HS.empty_today(), HS.empty_session("Fri 11/13"), HS.RULE_LABEL]


def test_ask_text_is_his_words_verbatim_with_no_clock_time():
    assert "“Can you create a tab similarly like Divergent with high charging tested, SHO tag, and low floats similar " \
           "to what we've done in Divergent tab under Gazilla?" in HS.ASK_TEXT
    assert "And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA." in HS.ASK_TEXT
    assert "“New tab like divergence*”" in HS.ASK_TEXT and "[voice typing:" in HS.ASK_TEXT
    assert not re.search(r"\d{1,2}:\d{2}", HS.ASK_TEXT) and "ET" not in HS.ASK_TEXT.replace("ETF", "")


def test_honesty_carries_the_divergence_figures_from_the_constant(monkeypatch):
    t = HS.honesty()
    assert t.startswith("UNMEASURED") and t.endswith("Not advice.")
    ah, rth = GC.DIVERGENCE_IS["ah"], GC.DIVERGENCE_IS["rth"]
    assert ah["word"] in t and rth["word"] in t and "LOST MONEY" in t and "NOT SHOWN" in t
    assert "−8.93% net per trade [−15.60, −3.13]" in t and "%d trades" % ah["trades"] in t
    assert GC.DIVERGENCE_OOS_SEAL_ET in t and "%d business days" % SR.FINRA_PUBLICATION_BDAYS in t
    new = {"ah": dict(ah, trades=77, word="ZZ WORD"), "rth": dict(rth)}
    monkeypatch.setattr(GC, "DIVERGENCE_IS", new)
    t2 = HS.honesty()
    assert "77 trades" in t2 and "ZZ WORD" in t2 and "LOST MONEY" not in t2


def test_cohort_text_names_carried_names_and_adds():
    t = HS.cohort_text()
    assert "kept %d more sessions" % GC.STAY_LISTED_SESSIONS in t and "📌" in t and "🎪" in t
    assert f"{GC.SCAN_MIN_VOLUME:,}" in t and "Nothing new fetched" in t


def test_counts_text_prints_only_non_zero_segments_that_sum():
    ev = {"rows": [{}, {}], "counts": dict({r: 0 for r in HS.REASONS}, floats_disagree=4, not_high=34, no_tier=27),
          "no_tier_low": ["X"] * 13, "n_read": 68, "faults": ["F1"], "unconfirmed": 1}
    t = HS.counts_text(ev)
    assert t.startswith("68 listed names read · 2 listed here (1 of them High · float unconfirmed) · not listed: ")
    assert "4 where the two float reads disagree on High" in t and "34 Low or Moderate" in t
    assert "27 with no tier word (no usable float on the short-interest record; 13 of them with a card float" in t
    assert "stale" not in t and "card float over" not in t                     # NEGATIVE: zero segments dropped
    tail = t.split("not listed: ", 1)[1]
    nums = [int(seg.split(" ", 1)[0]) for seg in tail.split(" · ")]
    assert sum(nums) == 68 - 2


def test_NEGATIVE_counts_text_all_zero_reads_none():
    t = HS.counts_text({"rows": [], "counts": {r: 0 for r in HS.REASONS}, "n_read": 0})
    assert t == "0 listed names read · 0 listed here · not listed: none"


def test_NEGATIVE_no_b_word_no_buy_no_squeeze_promise_anywhere():
    ev = {"rows": [{"symbol": "A"}], "counts": {r: 1 for r in HS.REASONS}, "n_read": 9, "faults": [],
          "disagree": [{"symbol": "G", "tier_word": "High", "pct_record": 62.87, "si_float_shares": 20235,
                        "pct_card": 3.52, "float_shares": 361428}],
          "over": [{"symbol": "B", "which": "record", "float_text": "11.0M"}], "no_tier_low": ["Z"],
          "settlement": {"settlement_date": SETTLE, "published_on": "2026-11-10", "next_due_on": "2026-11-27"}}
    texts = _all_words(ev) + [HS.disagree_text(ev), HS.excluded_text(ev), HS.no_tier_text(ev), HS.asof_text(ev),
                              HS.ASK_TEXT.split("”")[-1]]
    for mode in ("off", "live"):
        GC_mode = GC.HIGH_SI_CROSS_PUSH_MODE
        try:
            GC.HIGH_SI_CROSS_PUSH_MODE = mode
            texts += [HS.push_text(), HS.title()]
        finally:
            GC.HIGH_SI_CROSS_PUSH_MODE = GC_mode
    for t in texts:
        assert not B_WORD.search(t), t
        assert not re.search(r"\bbuy\b", t, re.I), t
        assert "squeeze" not in t.lower(), t
        assert not re.search(r"\d+% (gain|upside|return)", t), t


def test_no_typed_digit_in_the_served_sentences(monkeypatch):
    """Every number in a served sentence is a constant read at call time: move them all, the old values leave."""
    monkeypatch.setattr(GC, "HIGH_SI_MAX_FLOAT", 7_777_777)
    monkeypatch.setattr(GC, "K11_MIN_SESSION_VOLUME", 3_333_333)
    monkeypatch.setattr(GC, "EMA_FAST", 8)
    monkeypatch.setattr(GC, "EMA_SLOW", 34)
    monkeypatch.setattr(GC, "SCAN_MIN_VOLUME", 4_444_444)
    monkeypatch.setattr(GC, "STAY_LISTED_SESSIONS", 6)
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 17)
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", "live")
    blob = " ".join([HS.title(), HS.rule_text(), HS.push_text(), HS.cohort_text(),
                     HS.volume_row(None)["label"], HS.volume_row(5)["label"]])
    for old in ("10,000,000", "1,000,000", " 9 ", " 21 ", "first 15 "):
        assert old not in blob, old
    for new in ("7,777,777", "3,333,333", "4,444,444", "8 EMA", "34 EMA", "kept 6 more", "first 17 minutes"):
        assert new in blob, new


# ── the mode [C13] ──────────────────────────────────────────────────────────────────────────────────────────────
def test_the_mode_is_one_of_its_modes():
    assert GC.HIGH_SI_CROSS_PUSH_MODE in GC.HIGH_SI_CROSS_PUSH_MODES
    assert GC.HIGH_SI_CROSS_PUSH_MODES == GC.FADE_CROSS_PUSH_MODES
    assert GC.HIGH_SI_CROSS_LATCHES == WC.LATCHES and GC.HIGH_SI_CROSS_LATCH in GC.HIGH_SI_CROSS_LATCHES
    assert GC.HIGH_SI_CROSS_FRAMES == ("5m", "15m") and set(GC.HIGH_SI_CROSS_FRAMES) <= set(WC.FRAME_WORDS)
    assert GC.HIGH_SI_CROSS_CLAIM_PREFIX not in ("GG", "GGX", "GGW", "GG1")
    assert GC.HIGH_SI_CROSS_CLAIM_PREFIX != WC.CLAIM_PREFIX


def test_mode_off_reads_the_off_words(monkeypatch):
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", GC.HIGH_SI_CROSS_PUSH_MODES[0])
    assert HS.push_mode() == GC.HIGH_SI_CROSS_PUSH_MODES[0]
    # RE-PINNED 2026-11-24 — the 🔕 sentence carries his call (GC.CLEAN_ALERTS_CALL / _SHORT, no ISO date)
    assert HS.push_text() == HS.PUSH_OFF_TEXT.format(fast=GC.EMA_FAST, slow=GC.EMA_SLOW, call=GC.CLEAN_ALERTS_CALL,
                                                     short=GC.CLEAN_ALERTS_SHORT)
    assert "ring" not in HS.title()
    assert HS.cross_row({"tf": "5m", "bars": [], "curves": []}, "5m")["need"] == ""


def test_mode_live_reads_the_ring_words_with_the_candle_start_mute(monkeypatch):
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", GC.HIGH_SI_CROSS_PUSH_MODES[1])
    t = HS.push_text()
    assert t.startswith("🔔 Rings your phone") and "STARTED in GG's first %d minutes" % GC.NO_TRADE_AFTER_OPEN_MIN in t
    assert "04:00–20:00 ET (17:00 on a half day)" in t and "once per name, chart and cross" in t
    assert "UNMEASURED" in t and t.endswith("Not advice.") and "never sent late" in t
    assert "ring your phone" in HS.title()
    assert HS.cross_row({"tf": "5m", "bars": [], "curves": []}, "5m")["need"]
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_LATCH", "session")
    assert "once per name, chart and session" in HS.push_text()


@pytest.mark.parametrize("junk", ["LIVE", "on", "", None, 1, "shadow"])
def test_NEGATIVE_a_junk_mode_reads_as_off(monkeypatch, junk):
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", junk)
    assert HS.push_mode() == GC.HIGH_SI_CROSS_PUSH_MODES[0]
    assert HS.push_text().startswith("🔕") and "ring" not in HS.title()


# ── volume_row [C3] ─────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("v", [None, float("nan"), "junk", True, -1, float("inf")])
def test_NEGATIVE_unknown_volume_is_never_a_cross(v):
    r = HS.volume_row(v)
    assert r["ok"] is None and r["ok"] is not False and "judged at the ring" in r["label"]
    assert DT.K11_UNKNOWN not in r["label"] and r["key"] == DT.K11_KEY


def test_volume_row_equals_the_detector_on_every_known_volume():
    floor = GC.K11_MIN_SESSION_VOLUME
    assert HS.volume_row(floor - 1)["ok"] is False and HS.volume_row(floor)["ok"] is True
    for v in (0, 999_999, 1_000_000, 2.5e6, 10**9):
        assert HS.volume_row(v) == DT.k11_criterion(v)


# ── sho_text [C8] ───────────────────────────────────────────────────────────────────────────────────────────────
ROWS3 = [{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}]


def sho(items, complete, unread=()):
    srcs = [{"ok": True, "text": "Nasdaq list 11/12 · 300 names"}] + [{"ok": False, "text": t} for t in unread]
    return lambda now: {"items": {s: {"short": "🔒"} for s in items}, "complete": complete, "sources": srcs}


def test_sho_text_complete_counts_the_tagged_names():
    t = HS.sho_text(ROWS3, now=NOW, sho_read=sho(["AAA", "BBB", "ZZZ"], True))
    assert t == "🔒 2 of the 3 listed are on a Reg SHO threshold list — a tag, not a condition."
    t = HS.sho_text(ROWS3, now=NOW, sho_read=sho([], True))
    assert t == "🔒 None of the 3 listed is on a Reg SHO threshold list — a tag, not a condition."


def test_NEGATIVE_incomplete_reg_sho_never_says_none():
    t = HS.sho_text(ROWS3, now=NOW, sho_read=sho([], False, unread=("NYSE list not read yet",)))
    assert "None of" not in t and "NYSE list not read yet" in t and "does not mean a name is on no list" in t
    t = HS.sho_text(ROWS3, now=NOW, sho_read=sho(["AAA"], False, unread=("Cboe list failed",)))
    assert "at least" in t and "Cboe list failed" in t and t.startswith("🔒 1 of the 3")


def test_NEGATIVE_a_raising_sho_read_is_none_and_no_rows_is_none():
    def boom(now):
        raise RuntimeError("x")
    assert HS.sho_text(ROWS3, now=NOW, sho_read=boom) is None
    assert HS.sho_text([], now=NOW, sho_read=sho(["AAA"], True)) is None


# ── floats_text / the other name lists ──────────────────────────────────────────────────────────────────────────
def test_floats_text_labels_both_floats():
    assert HS.floats_text(fr(361428, text="Float 361.4K"), GMEX[0]) == \
        "Float 361.4K on this card · 20.2K on the short-interest record"
    assert HS.floats_text(fr(None), GMEX[0]) is None                            # NEGATIVE
    assert HS.floats_text(GMEX[1], dict(GMEX[0], float_shares=None)) is None    # NEGATIVE
    assert HS.floats_text(GMEX[1], None) is None


def test_disagree_excluded_and_no_tier_texts_name_both_numbers():
    ev = {"disagree": [{"symbol": "GMEX", "tier_word": "High", "pct_record": 62.87, "si_float_shares": 20235,
                        "pct_card": 3.52, "float_shares": 361428}],
          "over": [{"symbol": "BIG", "which": "card", "float_text": "Float 12.0M"},
                   {"symbol": "REC", "which": "record", "float_text": "11.0M"}], "no_tier_low": ["ABTS", "AMCI"]}
    assert HS.disagree_text(ev) == ("The two float reads disagree — not listed: GMEX — High on the short-interest "
                                    "record's float (62.9% of 20.2K), 3.5% of this card's float (361.4K)")
    assert HS.excluded_text(ev) == "High / EXTREME but over the float cap: BIG (card Float 12.0M) · REC (record float 11.0M)"
    assert "ABTS · AMCI — the tier is never worked out on the card's float here." in HS.no_tier_text(ev)
    for f in (HS.disagree_text, HS.excluded_text, HS.no_tier_text, HS.asof_text, HS.adds_text):
        assert f({}) is None                                                     # NEGATIVE: none → None


# ── the board (tab.build wiring) ────────────────────────────────────────────────────────────────────────────────
def stamps(day, start, n, step):
    hh, mm = (int(x) for x in start.split(":"))
    s = hh * 60 + mm
    return [f"{day.isoformat()} {(s + step * k) // 60:02d}:{(s + step * k) % 60:02d}" for k in range(n)]


def frame_bars(n, step, *, cross_at, down_at=None, start="09:35"):
    t = stamps(S, start, n, step)
    e21 = [5.0] * n
    e9 = [4.9 if (k < cross_at or (down_at is not None and k >= down_at)) else 5.1 for k in range(n)]
    bars = [{"t": t[k], "o": 5.0, "h": 5.2, "l": 4.8, "c": 5.1, "v": 10000.0} for k in range(n)]
    curves = [{"tone": "ema9", "label": "9 EMA", "values": e9}, {"tone": "ema21", "label": "21 EMA", "values": e21}]
    return bars, curves


def tile_of(down15=False):
    b5, c5 = frame_bars(30, 5, cross_at=20)
    b15, c15 = frame_bars(10, 15, cross_at=4, down_at=8 if down15 else None, start="09:45")
    return {"bars5": b5, "curves5": c5, "bars15": b15, "curves15": c15,
            "vol_avg5": {"period": 50, "label": "50-bar avg volume", "values": [1000.0] * len(b5)}}


def store(reads, *, volumes=None, prev_only=(), alerts=()):
    vols = volumes or {}
    scans = [scan_doc(r["symbol"], day=S, volume=vols.get(r["symbol"], 2e6)) for r in reads
             if r["symbol"] not in prev_only]
    scans += [scan_doc(s, day=PREV) for s in prev_only]
    return fake_store(**{ST.READS: FakeColl(list(reads)), ST.SCAN: FakeColl(scans), ST.ALERTS: FakeColl(list(alerts))})


@pytest.fixture
def si(monkeypatch):
    holder = {"blocks": {}}

    def fake(symbols, *, today):
        assert today == S
        return holder["blocks"]
    monkeypatch.setattr(HS, "si_blocks", fake)
    monkeypatch.setattr(HS, "_sho_payload", lambda now: {"items": {"HIGH": {"short": "🔒"}}, "complete": True,
                                                          "sources": []})
    return holder


def board(st, sub=HSUB, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, owner=kw.pop("owner", True), **kw)


def three_reads():
    return [rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1]), rdoc("GMEX", GMEX[1])]


def test_board_serves_the_sub_after_the_diverging_chip(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0], "GMEX": GMEX[0]}
    out = board(store(three_reads(), volumes={"HIGH": 3e6, "EXTR": 2e6}))
    assert out["sub"] == HSUB
    keys = [s["key"] for s in out["subs"]]
    assert keys[8] == HSUB and keys.index(HSUB) == keys.index(GC.DIVERGING_SUB) + 1
    assert out["subs"][8] == {"key": "high_si", "emoji": "🩳", "label": "High SI", "count": 2, "title": None}
    b = out["high_si"]
    assert b["n"] == 2 and b["n_read"] == 3 and b["push_text"] == HS.push_text()
    assert "GMEX" in b["disagree_text"] and "1 where the two float reads disagree" in b["counts_text"]
    assert b["sho_text"].startswith("🔒 1 of the 2 listed") and b["faults_text"] is None
    for k in ("title", "ask_text", "rule_label", "rule_text", "honesty", "cohort_text", "counts_text", "adds_text",
              "asof_text", "order_note", "empty_text", "chartless", "excluded_text", "no_tier_text", "shown_text"):
        assert k in b, k
    assert "_tiles" not in b
    syms = [t["symbol"] for t in out["tiles"]]
    assert syms == ["HIGH", "EXTR"]                                              # volume ↓
    g = out["tiles"][0]["gajjala"]
    assert g["setup"] == HSUB and g["state"] == HS.STATE and g["plan_text"] is None and g["missed"] == []
    assert [c["key"] for c in g["criteria"]] == ["si_tier", "float", "cross_5m", "cross_15m", DT.K11_KEY]
    assert g["criteria"][2]["ok"] is True and "crossed above" in g["criteria"][2]["value"]
    assert "on this card · 2.0M on the short-interest record" in g["criteria"][1]["value"]
    assert g["high_si"]["tier"] == SR.TIER_HIGH and g["high_si"]["carried"] is False
    t = out["tiles"][0]
    assert t["tf"] == "5m" and any(m["kind"] == GT.EMA_CROSS_MARK["up"] for m in t["markers"])
    assert not any("buy" in str(m.get("kind")) or "entry" in str(m.get("kind")) for m in t["markers"])


def test_board_tf_15m_draws_the_15_minute_frame_and_a_down_cross_reads_false(si):
    si["blocks"] = {"HIGH": HIGH[0]}
    out = board(store([rdoc("HIGH", HIGH[1], tile=tile_of(down15=True))]), tf="15m")
    t = out["tiles"][0]
    assert t["tf"] == "15m" and len(t["bars"]) == 10
    rows = {c["key"]: c for c in t["gajjala"]["criteria"]}
    assert rows["cross_15m"]["ok"] is False and "crossed under" in rows["cross_15m"]["value"]
    assert rows["cross_5m"]["ok"] is True


def test_board_cut_at_lim_serves_shown_text_and_broker_bottom_keeps_his_names(si, monkeypatch):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0], "AKAN": AKAN[0]}
    reads = [rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1]), rdoc("AKAN", AKAN[1])]
    vols = {"HIGH": 9e6, "EXTR": 5e6, "AKAN": 2e6}
    out = board(store(reads, volumes=vols), limit=2)
    assert out["high_si"]["shown_text"] == "Showing the first 2 of 3 listed names — every name is counted above."
    assert len(out["tiles"]) == 2
    monkeypatch.setattr(ST, "broker_flags", lambda st: (("HIGH",), False))
    out = board(store(reads, volumes=vols))
    assert [t["symbol"] for t in out["tiles"]] == ["EXTR", "AKAN", "HIGH"]       # 🚫 last, never dropped


def test_NEGATIVE_high_si_key_only_on_the_high_si_sub(si):
    si["blocks"] = {"HIGH": HIGH[0]}
    st = store([rdoc("HIGH", HIGH[1])])
    for k, _e, _l in GC.SUBS:
        if k != HSUB:
            out = board(st, k)
            assert "high_si" not in out, k
            assert next(s for s in out["subs"] if s["key"] == HSUB)["count"] == 1, k


@pytest.mark.parametrize("variant", [V.GG1, V.GGA], ids=["gg1", "gga"])
def test_NEGATIVE_other_pages_fail_open_and_omit_the_chip(si, variant):
    si["blocks"] = {"HIGH": HIGH[0]}
    out = board(store([rdoc("HIGH", HIGH[1])]), variant=variant)
    assert out["sub"] == GC.DEFAULT_SUB and out["sub_resolved_from"] == "default" and "high_si" not in out
    assert HSUB not in [s["key"] for s in out["subs"]]
    kw = dict(store=store([]), session=S, reads_by={}, listed={}, pm_syms=set(), post_syms=set(), potentials=[])
    assert GT.resolve_sub(HSUB, "", v=variant, **kw) == (GC.DEFAULT_SUB, "default")
    assert GT.resolve_sub(HSUB, "", **kw) == (HSUB, "param")


def test_NEGATIVE_unread_si_serves_the_fault_and_every_other_sub_stands(monkeypatch):
    monkeypatch.setattr(HS, "si_blocks", lambda symbols, *, today: None)
    st = store([rdoc("HIGH", HIGH[1])])
    out = board(st)
    assert out["high_si"] is None and out["tiles"] == [] and out["empty_note"] == HS.FAULT_TEXT
    assert next(s for s in out["subs"] if s["key"] == HSUB)["count"] is None
    other = board(st, GC.DEFAULT_SUB)
    assert other["sub"] == GC.DEFAULT_SUB and next(s for s in other["subs"] if s["key"] == HSUB)["count"] is None


def test_NEGATIVE_a_raising_card_is_a_chartless_line_never_the_sub_down(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    bad = rdoc("EXTR", EXTR[1], tile={"bars5": "junk"})
    out = board(store([rdoc("HIGH", HIGH[1]), bad]))
    b = out["high_si"]
    assert [t["symbol"] for t in out["tiles"]] == ["HIGH"] and b["faults"] == ["EXTR"]
    assert b["chartless"][0]["symbol"] == "EXTR" and b["chartless"][0]["text"] == "🩳 EXTR listed · chart not stored"
    assert b["faults_text"].startswith("1 name(s)")


def test_chartless_no_bars_line_names_the_ticker_in_the_served_text(si):
    """2026-11-23 refix (LOW): a listed name with no stored bars is a chartless line whose served `text` is the ONE string
    naming the ticker (CHARTLESS_TEXT); the served `state_label` carries the tier only — the FE prints `text`.
    NEGATIVE: the state_label never names the ticker (so printing it alone would hide which name it is), and a no-bars
    name is never a fault and never a tile."""
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    empty = {"bars5": [], "curves5": [], "bars15": [], "curves15": []}
    out = board(store([rdoc("HIGH", HIGH[1], tile=empty), rdoc("EXTR", EXTR[1])]))
    b = out["high_si"]
    assert [t["symbol"] for t in out["tiles"]] == ["EXTR"] and b["faults"] == []
    assert [c["symbol"] for c in b["chartless"]] == ["HIGH"]
    line = b["chartless"][0]
    assert line["text"] == HS.CHARTLESS_TEXT.format(sym="HIGH") and "HIGH" in line["text"]
    assert line["state_label"].startswith("🩳 ") and "HIGH" not in line["state_label"]


def test_carried_name_has_no_volume_sorts_last_and_its_k11_row_is_none(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    out = board(store([rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1])], prev_only=("HIGH",)))
    assert [t["symbol"] for t in out["tiles"]] == ["EXTR", "HIGH"]
    g = out["tiles"][1]["gajjala"]
    k11 = next(c for c in g["criteria"] if c["key"] == DT.K11_KEY)
    assert k11["ok"] is None and g["high_si"]["carried"] is True
    assert "1 carried from an earlier session" in out["high_si"]["adds_text"]


def test_empty_list_serves_the_empty_words(si):
    si["blocks"] = {"GMEX": GMEX[0]}
    out = board(store([rdoc("GMEX", GMEX[1])]))
    b = out["high_si"]
    assert b["n"] == 0 and out["tiles"] == [] and b["empty_text"] == HS.empty_today() and b["sho_text"] is None


# ── rang_today ──────────────────────────────────────────────────────────────────────────────────────────────────
def claim(sym, frame, bar_t, state="cross_pushed", kind=GC.HIGH_SI_CROSS_PUSH_KIND, prefix="GGS"):
    return {"_id": f"{prefix}:{S.isoformat()}|{sym}|{frame}|{bar_t}", "date": S.isoformat(), "symbol": sym,
            "frame": frame, "bar_t": bar_t, "kind": kind, "state": state}


def test_rang_today_serves_the_rang_row(si):
    si["blocks"] = {"HIGH": HIGH[0]}
    alerts = [claim("HIGH", "15m", "2026-11-13 11:00"), claim("HIGH", "5m", "2026-11-13 10:40")]
    st = store([rdoc("HIGH", HIGH[1])], alerts=alerts)
    assert HS.rang_today(st, S) == {"HIGH": [("5m", "2026-11-13 10:40"), ("15m", "2026-11-13 11:00")]}
    g = board(st)["tiles"][0]["gajjala"]
    row = g["criteria"][-1]
    assert row == {"key": "rang", "label": "🔔 rang today", "value": "5-min 10:40 ET · 15-min 11:00 ET", "need": "",
                   "ok": True}
    assert len(g["criteria"]) == 6


def test_NEGATIVE_rang_today_ignores_other_states_kinds_and_prefixes():
    alerts = [claim("A", "5m", "2026-11-13 10:40", state="cross_claimed"),
              claim("B", "5m", "2026-11-13 10:40", state="cross_no_target"),
              claim("C", "5m", "2026-11-13 10:40", kind=GC.POTENTIAL_PUSH_KIND),
              claim("D", "5m", "2026-11-13 10:40", prefix="GGX")]
    assert HS.rang_today(store([], alerts=alerts), S) == {}
    st = fake_store(**{ST.ALERTS: FakeColl([claim("A", "5m", "t")], fail=True)})
    assert HS.rang_today(st, S) == {} and HS.rang_today(None, S) == {}


# ── rules_info ──────────────────────────────────────────────────────────────────────────────────────────────────
def _note():
    return RI._gajjala_section()["note"]


def test_rules_info_clause_is_in_the_section_note_and_moves_with_the_constants(monkeypatch):
    n = _note()
    assert "🩳 High SI:" in n and "BOTH float reads" in n and "display only" in n and HS.push_text() in n
    assert n.index("🌱 Diverging") < n.index("🩳 High SI")
    monkeypatch.setattr(GC, "HIGH_SI_MAX_FLOAT", 6_543_210)
    assert "6,543,210" in _note()
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", "live")
    assert "cross push rings for" in _note() and HS.push_text().startswith("🔔") and HS.push_text() in _note()


def test_NEGATIVE_rules_info_clause_is_empty_on_a_raise(monkeypatch):
    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(HS, "push_text", boom)
    assert RI._gg_high_si_clause() == "" and "🩳 High SI:" not in _note()


# ── short_interest/read.py amendments [C10] ─────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_two_served_display_only_strings_are_byte_identical():
    assert SR.EXTREME_STUDY_NOTE == ("Display only — the 2026-11-17 SI × cradle study under eod-audits/research was "
                                     "too small to call either way.")
    assert SR.rules_section()["title"] == "Short interest — FINRA's count of open short positions (display only)"
    src = Path(SR.__file__).read_text(encoding="utf-8")
    assert src.count("AMENDED 2026-11-23 — one exception: the 🩳 High SI sub") == 4


# ── source guards ───────────────────────────────────────────────────────────────────────────────────────────────
SRC = Path(HS.__file__).read_text(encoding="utf-8")


def test_SOURCE_GUARD_high_si_has_no_parallel_engine_fetch_or_trade():
    for bad in (".ewm(", "signals.ema(", "_masked_ema(", "send_to_all", "frames_for(", "import requests",
                "websocket", "from trading", "import trading"):
        assert bad not in SRC, bad
    assert not re.search(r"ema9\W*[<>]=?\W*ema21|ema21\W*[<>]=?\W*ema9", SRC)


def test_SOURCE_GUARD_no_numeric_literal_for_a_tier_cap_or_floor():
    tree = ast.parse(SRC)
    lits = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)}
    assert lits <= {0, 1, 2, 100.0}, lits                                       # index / rounding / the % scale only
    for v in (SIC.SI_ELEV_PCT, SIC.SI_HIGH_PCT, SIC.SI_MODERATE_PCT, GC.K8_MAX_FLOAT, GC.K11_MIN_SESSION_VOLUME):
        assert v not in lits or v in (0, 1, 2, 100.0)
    assert "SR.tier_of" in inspect.getsource(HS.classify)
    assert "floats_disagree" in inspect.getsource(HS.classify) and "si_float_over" in inspect.getsource(HS.classify)


def test_finite_helpers_are_sane():
    assert HS._f(float("nan")) is None and HS._f(True) is None and HS._f("2") == 2.0 and math.isfinite(HS._f(1))
