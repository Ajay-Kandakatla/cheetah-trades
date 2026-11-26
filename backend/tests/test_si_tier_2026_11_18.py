"""🩳 SI tier words + EXTREME float confirmation (2026-11-18, later).

Ajay, verbatim: "Yes please and may be add better terminilogy like Moderate with a
percentage relative to float."  ("Yes please" answered: only call 🩳 EXTREME when
it's ≥ 20% of float AND ≥ 10% of all shares — AKAN's stale float read 36.4%.)

The ONE SI read (`read.si_block`) serves two more keys, `tier` and `float_check`,
from SIC.SI_MODERATE_PCT / SI_ELEV_PCT / SI_HIGH_PCT / SI_EXTREME_MIN_PCT_SHARES_OUT
BY NAME on the served 2-dp % of FLOAT. An unconfirmed or unchecked float stops at
High (monotone in short interest). Display only; UNMEASURED.

Hermetic: no network, Mongo is the 10-03 fake. Positives T1–T7, NEGATIVES N1–N13,
constants by name C1–C4, and a SOURCE GUARD over the tier slice.
Spec: scratchpad sitier/spec.md §3; doc: docs/gajjala/si_extreme_note_2026_11_18.md.
"""
from __future__ import annotations

import copy
import json
import logging
import math
import re
from datetime import date
from pathlib import Path

import pytest

from short_interest import client as SIC
from short_interest import read as SR
from tests.test_short_interest_read_2026_10_03 import FORBIDDEN, FakeColl, FakeDB
from tests.test_si_extreme_note_2026_11_18 import _extreme_slice, _literal_offenders

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND / "tests" / "fixtures" / "short_interest_blocks_2026_10_03.json"
FIX = json.loads(FIXTURE.read_text(encoding="utf-8"))
FIX_TODAY = date.fromisoformat(FIX["today"])
CASES = {c["name"]: c for c in FIX["cases"]}
TODAY = date(2026, 11, 18)
LATE = date(2026, 11, 30)                                      # after the 11-13 settlement's due day → stale
WORD = re.compile(r"\b(Low|Moderate|High|EXTREME)\b")


def _doc(sym, si, fl, so, **over):
    d = {"_id": sym, "symbol": sym, "v": 2, "settlement_date": "2026-10-30",
         "short_interest": si, "days_to_cover": 1.0, "avg_daily_volume": si,
         "float_shares": fl, "float_asof": "2026-10-22",
         "float_source": "yfinance floatShares (shares_cache)",
         "shares_outstanding": so, "shares_asof": "2026-10-22",
         "shares_source": "yfinance sharesOutstanding (shares_cache)",
         "source": "FINRA short interest (Rule 4560) via Massive /stocks/v1/short-interest",
         "fetched_at": 1794700800.0}
    d.update(over)
    return d


def _akan(**over):
    """AKAN as the live read served it 2026-11-18 (si 193,393 / float 531,210 / shares out 2,388,212)."""
    return _doc("AKAN", 193_393, 531_210, 2_388_212, **over)


def _clro(**over):
    return _doc("CLRO", 391_224, 888_130, 2_675_412, float_asof="2026-11-10", **over)


def _slsn(**over):
    return _doc("SLSN", 359_433, None, None, days_to_cover=19.48, **over)


def _ratio(si, fl=100_000, so=200_000, **over):
    return _doc("TST", si, fl, so, **over)


def _blk(doc, today=TODAY):
    return SR.si_block(doc, today)


def _row(b, k):
    hits = [r["v"] for r in b["rows"] if r["k"] == k]
    return hits[0] if hits else None


def _all_strings(b):
    out = [b.get("chip") or "", b.get("title") or ""]
    out += [r["k"] + " " + r["v"] for r in b.get("rows") or []]
    e = b.get("extreme")
    if e:
        out += [e["text"], e["short"], e["title"], e["basis"]]
    return out


# ═════════════════════════════════════════════ T1 — AKAN live shape
def test_T1_akan_reads_high_float_unconfirmed():
    b = _blk(_akan())
    assert b["status"] == "ok" and b["headline_basis"] == "float"
    assert b["pct_of_float"] == 36.41 and b["pct_of_shares_out"] == 8.1         # served truth unchanged
    assert b["tier"] == "high" and b["float_check"] == "unconfirmed"
    assert b["chip"] == "🩳 SI High 36.4% float · float unconfirmed · 1.0d · 10/30"
    head = b["chip"].split(" · 1.0d")[0]
    assert head.endswith("float · float unconfirmed")                           # C7: the head names the float basis
    assert b["extreme"] is None
    t = b["title"]
    assert "Tier: High — 36.4% of the float, held below EXTREME until the float is confirmed." in t
    assert "Float check: float unconfirmed — the float on file (531,210 shares," in t
    assert "only 8.1% of all shares are short" in t
    assert "Ladder" not in t
    tier_row = _row(b, "Tier")
    assert tier_row is not None and "Ladder: Low under 5%" in tier_row
    assert _row(b, "Float check") is not None and _row(b, "Float check").startswith("float unconfirmed — ")
    keys = [r["k"] for r in b["rows"]]
    assert keys.index("Tier") == keys.index("% of shares outstanding") + 1
    assert keys.index("Float check") == keys.index("Tier") + 1


# ═════════════════════════════════════════════ T2 — CLRO confirmed
def test_T2_clro_reads_extreme_confirmed():
    b = _blk(_clro())
    assert b["tier"] == "extreme" and b["float_check"] == "confirmed"
    assert b["chip"] == "🩳 SI EXTREME 44.0% float · 1.0d · 10/30"
    assert b["extreme"]["text"] == b["chip"]
    assert b["extreme"]["short"] == "🩳 SI EXTREME 44.0% float"
    assert "Tier: EXTREME (20% or more of the float)." in b["title"]
    assert "Float check: confirmed — 14.6% of shares outstanding is short" in b["title"]
    assert "SI_EXTREME_MIN_PCT_SHARES_OUT" in b["extreme"]["title"]


def test_T2_block_key_order():
    keys = list(SR._BLOCK_KEYS)
    i = keys.index("float_suspect")
    assert keys[i + 1:i + 3] == ["tier", "float_check"]
    assert keys[-2:] == ["rows", "extreme"]
    assert list(_blk(_clro())) == keys


# ═════════════════════════════════════════════ T3 — boundaries on the served 2-dp value
@pytest.mark.parametrize("si,tier,printed", [
    (4_990, "low", "4.99%"),
    (5_000, "moderate", "5.0%"),
    (9_990, "moderate", "9.99%"),
    (10_000, "high", "10.0%"),
    (19_990, "high", "19.99%"),
    (20_000, "extreme", "20.0%"),
])
def test_T3_boundaries(si, tier, printed):
    b = _blk(_ratio(si))                                       # fl 100k, so 200k
    assert b["tier"] == tier
    assert b["chip"].startswith("🩳 SI %s %s float · " % (SR.TIER_WORDS[tier], printed))
    if tier == "extreme":
        assert b["pct_of_shares_out"] == 10.0 and b["float_check"] == "confirmed" and b["extreme"] is not None
    else:
        assert b["float_check"] is None and b["extreme"] is None


def test_T3_the_confirmation_seam():
    un = _blk(_ratio(10_000, fl=50_000, so=100_100))
    assert un["pct_of_float"] == 20.0 and un["pct_of_shares_out"] == 9.99
    assert un["tier"] == "high" and un["float_check"] == "unconfirmed" and un["extreme"] is None
    assert un["chip"].startswith("🩳 SI High 20.0% float · float unconfirmed · ")
    assert "only 9.99% of all shares" in un["title"]
    ok = _blk(_ratio(10_000, fl=50_000, so=100_000))
    assert ok["pct_of_shares_out"] == 10.0
    assert ok["tier"] == "extreme" and ok["float_check"] == "confirmed" and ok["extreme"] is not None


# ═════════════════════════════════════════════ T4 — si_map end to end
def test_T4_si_map_end_to_end():
    # 2026-11-26 sitrack A4: SLSN read with no ADV, so its chip still prints the provider's 19.48 (the builder's ADV
    # equals the short count, which the chip would divide into 1.0d)
    db = FakeDB({SIC.SI_COLL: FakeColl([_akan(), _clro(), _slsn(avg_daily_volume=None)], name=SIC.SI_COLL)})
    m = SR.si_map(["AKAN", "CLRO", "SLSN", "NOPE"], db=db, today=TODAY)
    assert list(m) == ["AKAN", "CLRO", "SLSN"]
    assert (m["AKAN"]["tier"], m["AKAN"]["float_check"], m["AKAN"]["extreme"]) == ("high", "unconfirmed", None)
    assert (m["CLRO"]["tier"], m["CLRO"]["float_check"]) == ("extreme", "confirmed")
    assert m["CLRO"]["extreme"]["text"] == m["CLRO"]["chip"]
    assert m["SLSN"]["chip"] == "🩳 SI 359.4K sh · 19.5d · 10/30"
    assert (m["SLSN"]["tier"], m["SLSN"]["float_check"], m["SLSN"]["extreme"]) == (None, None, None)
    for b in m.values():
        json.dumps(b, allow_nan=False)


# ═════════════════════════════════════════════ T5 — MONOTONICITY (critique C1)
def _sweep(fl, so):
    step = max(1, fl // 2000)
    sis = set(range(1, fl + 1, step))
    for c in SR._cuts():
        for base in (fl, so):
            if base:
                k = int(math.ceil(c * base / 100.0))
                sis.update(x for x in (k - 1, k, k + 1) if 1 <= x <= fl)
    sis.update(x for x in (19_990, 20_000) if x <= fl)
    return sorted(sis)


def _monotone_faults(fl, so):
    """Every violation of the ladder's promises along a sweep of short interest at a fixed float + shares out."""
    faults, last = [], -1
    for si in _sweep(fl, so):
        b = _blk(_ratio(si, fl=fl, so=so))
        if b["status"] != "ok" or b["headline_basis"] != "float":
            continue
        t, fc, pf = b["tier"], b["float_check"], b["pct_of_float"]
        if pf > 0 and t is None:
            faults.append(("no word", si))
            continue
        if t is None:
            continue
        r = SR.TIER_ORDER.index(t)
        if r < last:
            faults.append(("decrease", si, t))
        last = max(last, r)
        if (t == "extreme") != (fc == "confirmed"):
            faults.append(("extreme<>confirmed", si, t, fc))
        if (b["extreme"] is not None) != (t == "extreme"):
            faults.append(("note<>tier", si, t))
    return faults


PAIRS = [(100_000, 222_000), (531_210, 2_388_212), (888_130, 2_675_412), (100_000, 200_000),
         (100_000, 100_000), (100_000, None)]


@pytest.mark.parametrize("fl,so", PAIRS)
def test_T5_monotone_in_short_interest(fl, so):
    assert _monotone_faults(fl, so) == []


def test_T5_the_critics_exact_pair():
    a = _blk(_ratio(19_990, fl=100_000, so=222_000))
    b = _blk(_ratio(20_000, fl=100_000, so=222_000))
    assert (a["tier"], a["float_check"]) == ("high", None)
    assert (b["tier"], b["float_check"]) == ("high", "unconfirmed")
    assert a["chip"].startswith("🩳 SI High 19.99% float · ")
    assert b["chip"].startswith("🩳 SI High 20.0% float · float unconfirmed · ")


# ═════════════════════════════════════════════ T6 — seam prints (critique C2)
def test_T6_ulcc_shape_prints_9_98_never_10_0():
    b = _blk(_ratio(32_980, fl=100_000, so=330_460))
    assert b["pct_of_float"] == 32.98 and b["pct_of_shares_out"] == 9.98
    assert b["tier"] == "high" and b["float_check"] == "unconfirmed"
    assert "only 9.98% of all shares" in _row(b, "Float check")
    assert "9.98% of shares outstanding — " in b["title"]
    assert _row(b, "% of shares outstanding").startswith("9.98% — ")
    for s in _all_strings(b):
        assert "10.0%" not in s, s


@pytest.mark.parametrize("p,want", [
    (4.99, "4.99%"), (9.95, "9.9%"), (9.98, "9.98%"), (19.99, "19.99%"), (20.0, "20.0%"),
    (36.41, "36.4%"), (0.04, "<0.1%"), (0.0, "0.0%"),
])
def test_T6_pct_tier_table(p, want):
    assert SR._pct_tier(p) == want


# ═════════════════════════════════════════════ T7 — the hover stays short (critique C8)
@pytest.mark.parametrize("si,tier", [(2_000, "low"), (7_000, "moderate"), (15_000, "high")])
def test_T7_hover_has_only_its_own_range(si, tier):
    b = _blk(_ratio(si))
    assert b["tier"] == tier and b["float_check"] is None
    assert "EXTREME" not in b["title"] and "Ladder" not in b["title"]
    assert "Tier: %s (" % SR.TIER_WORDS[tier] in b["title"]
    assert "Float check" not in b["title"] and _row(b, "Float check") is None
    assert "Ladder: " in _row(b, "Tier")


# ═════════════════════════════════════════════ NEGATIVES
def test_N1_slsn_no_float_gets_no_word():
    b = _blk(_slsn())
    assert b["tier"] is None and b["float_check"] is None
    assert not WORD.search(b["chip"])
    assert ("Tier: not given — the tier words count the % of float, and no usable float is on file."
            in b["title"])


@pytest.mark.parametrize("mk,fc", [(_akan, "unconfirmed"), (_clro, "confirmed")])
def test_N2_stale_reads_get_no_word(mk, fc):
    b = _blk(mk(), LATE)
    assert b["status"] == "stale" and b["tier"] is None and b["extreme"] is None
    assert not WORD.search(b["chip"]) and b["chip"].endswith("· stale")
    assert "Tier: not given on a stale read." in b["title"]
    assert b["float_check"] == fc
    assert ("float unconfirmed" in b["chip"]) == (fc == "unconfirmed")


def test_N2_stale_akan_exact_chip():
    assert _blk(_akan(), LATE)["chip"] == "🩳 SI 36.4% float · float unconfirmed · 1.0d · 10/30 · stale"
    assert _blk(_clro(), LATE)["chip"] == "🩳 SI 44.0% float · 1.0d · 10/30 · stale"


def test_N3_shares_out_basis_gets_no_word():
    u = SR.si_block(CASES["uhal_v2_conflict"]["doc"], FIX_TODAY)
    brk = _blk(_ratio(250_000, fl=200_000, so=1_000_000))
    so_only = _blk(_ratio(150_000, fl=None, so=500_000))
    for b in (u, brk, so_only):
        assert b["headline_basis"] == "shares_out"
        assert b["tier"] is None and b["float_check"] is None and b["extreme"] is None
        assert not WORD.search(b["chip"]) and "float unconfirmed" not in b["chip"]
    assert so_only["chip"] == "🩳 SI 30.0% shs out · 1.0d · 10/30"
    assert u["chip"] == CASES["uhal_v2_conflict"]["block"]["chip"]


def test_N4_unchecked_reads_high_with_no_flag():
    b = _blk(_ratio(36_000, fl=100_000, so=None))
    assert b["tier"] == "high" and b["float_check"] == "unchecked" and b["extreme"] is None
    assert "High" in b["chip"] and "float unconfirmed" not in b["chip"]
    assert b["chip"] == "🩳 SI High 36.0% float · 1.0d · 10/30"
    assert "Float check: not possible — shares outstanding is not on file" in b["title"]


@pytest.mark.parametrize("pf", [20, 25, 50, 95.4])
@pytest.mark.parametrize("ps", [0.5, 5, 9.99])
def test_N5_the_note_never_fires_unconfirmed(pf, ps):
    si = int(round(pf * 1_000))
    so = int(round(si * 100.0 / ps))
    b = _blk(_ratio(si, fl=100_000, so=so))
    assert b["pct_of_float"] >= SIC.SI_HIGH_PCT and b["pct_of_shares_out"] < SIC.SI_EXTREME_MIN_PCT_SHARES_OUT
    assert b["tier"] == "high" and b["float_check"] == "unconfirmed"
    assert b["extreme"] is None and "EXTREME" not in b["chip"]


@pytest.mark.parametrize("field", ["float_shares", "shares_outstanding", "days_to_cover"])
def test_N6_nan_never_reaches_the_payload(field):
    for mk in (_akan, _clro):
        b = _blk(mk(**{field: float("nan")}))
        s = json.dumps(b, allow_nan=False, ensure_ascii=False)
        assert not re.search(r"\bnan\b", s, re.I)


def test_N7_no_record_carries_both_keys_as_none():
    b = SR.si_block(CASES["no_record_miss"]["doc"], FIX_TODAY)
    assert b["status"] == "no_record"
    assert "tier" in b and "float_check" in b and b["tier"] is None and b["float_check"] is None
    assert SR.si_tier(None) == (None, None) and SR.si_tier({}) == (None, None)


def test_N8_a_raising_tier_never_costs_the_chip(monkeypatch, caplog):
    def boom(_b):
        raise ZeroDivisionError("x")
    monkeypatch.setattr(SR, "si_tier", boom)
    with caplog.at_level(logging.WARNING, logger="short_interest.read"):
        b = _blk(_clro())
    assert b["chip"] == "🩳 SI 44.0% float · 1.0d · 10/30"
    assert b["tier"] is None and b["float_check"] is None and b["extreme"] is None
    assert any("tier" in r.getMessage() and "failed" in r.getMessage() for r in caplog.records)


def test_N9_the_old_float_guard_is_untouched():
    assert SR._float_suspect(193_393, 531_210, 2_388_212) is None
    assert SR.SUSPECT_MAX_SHARES_OUT_FRACTION == 0.5
    assert SR._float_suspect(10, 200, 100) == SR.FLOAT_EXCEEDS_SHARES == "float_exceeds_shares_out"
    assert SR._float_suspect(250, 200, 1_000) == SR.SHORT_EXCEEDS_FLOAT == "short_exceeds_float"


def test_N10_no_forecast_word_in_any_new_string():
    docs = ([c["doc"] for c in CASES.values()]
            + [_akan(), _clro(), _slsn(), _ratio(36_000, so=None), _ratio(0), _ratio(2_000), _ratio(7_000)])
    texts = []
    for d in docs:
        for today in (FIX_TODAY, TODAY, LATE):
            b = SR.si_block(d, today)
            texts += _all_strings(b)
            texts += [r["v"] for r in b["rows"] if r["k"] in ("Tier", "Float check")]
    texts += [SR.TIER_STALE_TEXT, SR.TIER_NO_FLOAT_TEXT, SR.TIER_ZERO_TEXT, SR._ladder(),
              SR.FLOAT_UNCHECKED_TEXT % SIC.SI_EXTREME_MIN_PCT_SHARES_OUT]
    texts += [p for p in SR.rules_section()["picks"] if "EXTREME" in p]
    assert any(t.startswith("Tier ") for t in texts) and any(t.startswith("Float check ") for t in texts)
    for t in texts:
        assert not FORBIDDEN.search(t), t
        assert "band" not in t.lower(), t


def test_N11_the_zero_guard():
    # 2026-11-26 sitrack A4: 0 shares short → nothing to divide, the provider's 1.0 is FINRA's floor ('≤1d');
    # 1 share short ÷ an ADV of 1 → 1.0d
    for doc, dtc in ((_ratio(0), "≤1d"), (_ratio(1, fl=100_000_000, so=400_000_000), "1.0d")):
        b = _blk(doc)
        assert b["pct_of_float"] == 0.0 and b["headline_basis"] == "float"
        assert b["tier"] is None and b["float_check"] is None
        assert b["chip"] == "🩳 SI 0.0% float · " + dtc + " · 10/30"
        assert "Tier: not given — too few shares short to read as a share of the float." in b["title"]
    assert SR.tier_of(0) is None and SR.tier_of(0.0) is None and SR.tier_of(-1) is None
    assert SR.tier_of(None) is None and SR.tier_of(float("nan")) is None
    assert SR.tier_of(0.04) == "low"


def test_N12_an_out_of_order_ladder_serves_no_word(monkeypatch):
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 8.0)              # below SI_ELEV_PCT — an env mistake
    assert SR._ladder_ok() is False
    for d in [c["doc"] for c in CASES.values()] + [_akan(), _clro()]:
        b = SR.si_block(d, FIX_TODAY if d in [c["doc"] for c in CASES.values()] else TODAY)
        assert b["tier"] is None and b["extreme"] is None
        assert not WORD.search(b["chip"] or ""), b["chip"]
        assert "Tier:" not in b["title"] or "not given" in b["title"]


def test_N12_his_confirmation_number_holds_the_cap(monkeypatch):
    monkeypatch.setattr(SIC, "SI_EXTREME_MIN_PCT_SHARES_OUT", 50.0)
    b = _blk(_clro())
    assert b["tier"] == "high" and b["float_check"] == "unconfirmed" and b["extreme"] is None
    assert b["chip"].startswith("🩳 SI High 44.0% float · float unconfirmed · ")


def test_N13_the_sweep_bites_on_the_v1_rule(monkeypatch):
    orig = SR.si_tier

    def v1(b):                                                 # v1: an unconfirmed float re-tiers on % of shares out
        t, fc = orig(b)
        if t is not None and fc == SR.FLOAT_UNCONFIRMED:
            t = SR.tier_of(b["pct_of_shares_out"])
        return t, fc
    monkeypatch.setattr(SR, "si_tier", v1)
    faults = _monotone_faults(100_000, 222_000)
    assert any(f[0] == "decrease" for f in faults)


# ═════════════════════════════════════════════ constants by name
def test_C1_his_numbers():
    assert SIC.SI_EXTREME_MIN_PCT_SHARES_OUT == 10.0           # his yes, 2026-11-18
    assert SIC.SI_MODERATE_PCT == 5.0


def test_C2_shipped_ordering():
    assert 0 < SIC.SI_MODERATE_PCT < SIC.SI_ELEV_PCT < SIC.SI_HIGH_PCT
    assert SR._ladder_ok() is True


def test_C3_each_constant_moves_the_tiers_and_the_words(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(SIC, "SI_HIGH_PCT", 30.0)
        b = _blk(_ratio(25_000))                               # 25% of float, 12.5% of shares out
        assert b["tier"] == "high" and b["float_check"] is None
        assert "High 10% to under 30%" in _row(b, "Tier") and "EXTREME 30% or more" in _row(b, "Tier")
        assert "Tier: High (10% to under 30% of the float)." in b["title"]
    with monkeypatch.context() as m:
        m.setattr(SIC, "SI_ELEV_PCT", 12.0)
        b = _blk(_ratio(11_000))
        assert b["tier"] == "moderate" and "Tier: Moderate (5% to under 12% of the float)." in b["title"]
    with monkeypatch.context() as m:
        m.setattr(SIC, "SI_MODERATE_PCT", 3.0)
        b = _blk(_ratio(4_000))
        assert b["tier"] == "moderate" and "Tier: Moderate (3% to under 10% of the float)." in b["title"]
        assert "Low under 3%" in _row(b, "Tier")
    with monkeypatch.context() as m:
        m.setattr(SIC, "SI_EXTREME_MIN_PCT_SHARES_OUT", 15.0)
        b = _blk(_clro())                                      # 14.62% of shares out < 15
        assert b["float_check"] == "unconfirmed" and "under the 15% of shares outstanding" in b["title"]
        assert "at least 15% of shares outstanding" in _row(b, "Tier")
    assert _blk(_clro())["tier"] == "extreme"                 # back to the shipped constants


def test_C4_the_cuts_are_the_constants(monkeypatch):
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 44.05)
    assert _blk(_clro())["tier"] == "extreme"
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 44.06)
    assert _blk(_clro())["tier"] == "high"
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 20.0)
    monkeypatch.setattr(SIC, "SI_EXTREME_MIN_PCT_SHARES_OUT", 14.62)
    assert _blk(_clro())["float_check"] == "confirmed"
    monkeypatch.setattr(SIC, "SI_EXTREME_MIN_PCT_SHARES_OUT", 14.63)
    assert _blk(_clro())["float_check"] == "unconfirmed"


# ═════════════════════════════════════════════ SOURCE GUARD — the tier slice
_SRC = (BACKEND / "short_interest" / "read.py").read_text(encoding="utf-8")


def _tier_slice(src: str) -> str:
    i = src.index("TIER_LOW, TIER_MODERATE, TIER_HIGH, TIER_EXTREME = ")
    j = src.index("\ndef extreme_block", i)
    return src[i:j]


def test_SOURCE_GUARD_no_numeric_literal_in_the_tier_slice():
    sl = _tier_slice(_SRC)
    assert sl in _extreme_slice(_SRC)                          # the 11-18 guard covers it too
    for name in ("SIC.SI_MODERATE_PCT", "SIC.SI_ELEV_PCT", "SIC.SI_HIGH_PCT", "SIC.SI_EXTREME_MIN_PCT_SHARES_OUT"):
        assert name in sl, name
    assert "t = TIER_HIGH" in sl
    assert "round(" not in sl
    assert _literal_offenders(sl) == []


def test_SOURCE_GUARD_one_print_helper_and_no_tag_kwarg():
    assert _SRC.count("_pct1(") == 2                           # its def + the call inside _pct_tier
    assert "tag=" not in _SRC and "EXTREME_TAG" not in _SRC
    assert "SI_MODERATE_PCT = 5.0" in (BACKEND / "short_interest" / "client.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("mutant", [
    ("< SIC.SI_MODERATE_PCT", "< 5"),
    (">= SIC.SI_EXTREME_MIN_PCT_SHARES_OUT", ">= 10"),
    ('"under %g%%"', '"under 5%"'),
])
def test_NEGATIVE_the_tier_source_guard_catches_a_typed_number(mutant):
    old, new = mutant
    sl = _tier_slice(_SRC)
    assert old in sl
    assert _literal_offenders(sl.replace(old, new, 1)) != []


def test_fixture_new_cases_are_served_exactly():
    for name, want in (("akan_shape_unconfirmed", ("high", "unconfirmed", False)),
                       ("clro_shape_extreme", ("extreme", "confirmed", True)),
                       ("float_unchecked", ("high", "unchecked", False))):
        b = copy.deepcopy(CASES[name]["block"])
        assert SR.si_block(CASES[name]["doc"], FIX_TODAY) == b
        assert (b["tier"], b["float_check"], b["extreme"] is not None) == want
