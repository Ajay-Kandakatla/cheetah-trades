"""🩳 EXTREME short-interest note on 🎾 cards + 👀 Watch tiles (2026-11-18).

Ajay, verbatim: "When there are extreme cases of short interest make a not for
them on reversal squeeze like percentage of short interest on the tickers card
and also on watch list"

The note is ONE more served key on the ONE SI read (`read.si_block` →
`extreme`), built from `client.SI_HIGH_PCT` BY NAME with `>=` on the SERVED 2-dp
% of float, only on an `ok` read with a float basis. Display only; UNMEASURED
(the 2026-11-17 SI × cradle study was too small to call either way).

Hermetic: no network, Mongo is the 10-03 fake. NEGATIVES: below the cut, stale,
no_record, suspect float, shares-out-only, the client's dtc disjunction NOT
mirrored, dtc 0/None/NaN, a raising note never costs the chip, no numeric
literal in the EXTREME slice, no forecast word in any served string.
Doc: docs/gajjala/si_extreme_note_2026_11_18.md.
"""
from __future__ import annotations

import copy
import io
import json
import re
import tokenize
from datetime import date
from pathlib import Path

import pytest

from short_interest import client as SIC
from short_interest import read as SR
from tests.test_short_interest_read_2026_10_03 import FORBIDDEN, FakeColl, FakeDB

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND / "tests" / "fixtures" / "short_interest_blocks_2026_10_03.json"
FIX = json.loads(FIXTURE.read_text(encoding="utf-8"))
FIX_TODAY = date.fromisoformat(FIX["today"])
CASES = {c["name"]: c for c in FIX["cases"]}
TODAY = date(2026, 11, 18)


def _akan(**over):
    """AKAN as the live read served it 2026-11-18 (GET /short-interest/map probe)."""
    d = {"_id": "AKAN", "symbol": "AKAN", "v": 2, "settlement_date": "2026-10-30",
         "short_interest": 193414, "days_to_cover": 1.0, "avg_daily_volume": 193414,
         "float_shares": 531210, "float_asof": "2026-10-22",
         "float_source": "yfinance floatShares (shares_cache)",
         "shares_outstanding": 2388212, "shares_asof": "2026-10-22",
         "shares_source": "yfinance sharesOutstanding (shares_cache)",
         "source": "FINRA short interest (Rule 4560) via Massive /stocks/v1/short-interest",
         "fetched_at": 1794700800.0}
    d.update(over)
    return d


def _ratio(si, fl=100_000, so=400_000, **over):
    return _akan(short_interest=si, float_shares=fl, shares_outstanding=so, **over)


def _eose(**over):
    d = copy.deepcopy(CASES["eose_v2_float"]["doc"])
    d.update(over)
    return d


# ═════════════════════════════════════════════ the AKAN pin (live probe)
def test_akan_pin_text_short_basis_and_title():
    b = SR.si_block(_akan(), TODAY)
    assert b["status"] == "ok" and b["headline_basis"] == "float"
    assert b["pct_of_float"] == 36.41 and b["pct_of_shares_out"] == 8.1
    assert b["chip"] == "🩳 SI 36.4% float · 1.0d · 10/30"
    e = b["extreme"]
    assert set(e) == {"text", "short", "title", "basis"}
    assert e["text"] == "🩳 EXTREME SI 36.4% float · 1.0d · 10/30"
    assert e["text"] == b["chip"].replace("🩳 SI", "🩳 EXTREME SI", 1)     # one engine
    assert e["short"] == "🩳 EXTREME SI 36.4% float"
    assert e["basis"] == "si_doc_float" == SR.EXTREME_BASIS
    t = e["title"]
    assert t.startswith(
        "🩳 EXTREME short interest — 36.4% of the float is sold short at the FINRA settlement "
        "2026-10-30 (published ~2026-11-10), at or above 20% of the float — the app's standard "
        "high-short-interest heuristic (SI_HIGH_PCT; not from any book, not one of GG's rules).")
    for want in ("at or above 20% of the float", "SI_HIGH_PCT", "not one of GG's rules", "531,210",
                 "too small to call either way", "not a forecast", "Not advice.",
                 "8.1% of shares outstanding (2.4M)", "1.0 days to cover"):
        assert want in t, want
    for never in ("band", "did not run"):
        assert never not in t.lower()


def test_exactly_at_the_cut_gets_the_note():
    b = SR.si_block(_ratio(20_000), TODAY)
    assert b["pct_of_float"] == 20.0 == SIC.SI_HIGH_PCT
    assert b["extreme"] is not None and b["extreme"]["short"] == "🩳 EXTREME SI 20.0% float"


def test_NEGATIVE_below_the_cut_is_none_and_the_chip_is_unchanged():
    b = SR.si_block(_ratio(19_990), TODAY)
    assert b["pct_of_float"] == 19.99
    assert b["extreme"] is None
    assert b["chip"] == "🩳 SI 20.0% float · 1.0d · 10/30"      # the chip prints 20.0 — the 2-dp value decides
    assert "EXTREME" not in b["chip"] and "EXTREME" not in b["title"]


def test_the_rounding_seam_follows_the_served_figure():
    b = SR.si_block(_ratio(19_996), TODAY)
    assert b["pct_of_float"] == 20.0                           # raw 19.996 → served 20.0
    assert b["extreme"] is not None


# ═════════════════════════════════════════════ NEGATIVES — where the note hides
def test_NEGATIVE_stale_reads_get_no_note():
    legacy = SR.si_block(CASES["eose_v1_legacy_stale"]["doc"], FIX_TODAY)
    assert legacy["status"] == "stale" and legacy["extreme"] is None
    late = SR.si_block(_akan(), date(2026, 11, 30))
    assert late["status"] == "stale" and late["pct_of_float"] == 36.41
    assert late["extreme"] is None and late["chip"].endswith("· stale")


def test_NEGATIVE_no_record_is_none_and_the_key_is_present():
    b = SR.si_block(CASES["no_record_miss"]["doc"], FIX_TODAY)
    assert b["status"] == "no_record" and "extreme" in b and b["extreme"] is None
    assert SR.extreme_block(None) is None and SR.extreme_block({}) is None


def test_NEGATIVE_a_suspect_float_gets_no_note_even_above_the_cut_on_shares_out():
    u = SR.si_block(CASES["uhal_v2_conflict"]["doc"], FIX_TODAY)
    assert u["float_suspect"] and u["extreme"] is None
    # BRK-B shape: float < si <= 0.5 · so, and % of shares out >= the cut
    b = SR.si_block(_ratio(250_000, fl=200_000, so=1_000_000), TODAY)
    assert b["float_suspect"] == SR.SHORT_EXCEEDS_FLOAT
    assert b["headline_basis"] == "shares_out" and b["pct_of_shares_out"] >= SIC.SI_HIGH_PCT
    assert b["extreme"] is None


def test_NEGATIVE_shares_out_only_basis_gets_no_note():
    b = SR.si_block(_ratio(150_000, fl=None, so=500_000), TODAY)
    assert b["headline_basis"] == "shares_out" and b["pct_of_shares_out"] == 30.0
    assert b["extreme"] is None


def test_NEGATIVE_the_clients_dtc_disjunction_is_not_mirrored():
    b = SR.si_block(_ratio(12_000, so=110_000, days_to_cover=6.0), TODAY)
    assert b["pct_of_float"] == 12.0 and b["days_to_cover"] == 6.0
    assert SIC._squeeze_signal(12.0, 6.0) == "high"           # the home rule calls it high …
    assert b["extreme"] is None                                # … this note does not (HIS CALL #1)


@pytest.mark.parametrize("dtc", [0, 0.0, None, float("nan")])
def test_NEGATIVE_a_zero_or_missing_dtc_drops_the_segment(dtc):
    b = SR.si_block(_akan(days_to_cover=dtc), TODAY)
    e = b["extreme"]
    assert e["text"] == "🩳 EXTREME SI 36.4% float · 10/30"
    assert "0.0d" not in e["text"] and "days to cover" not in e["title"]
    assert e["short"] == "🩳 EXTREME SI 36.4% float"
    json.dumps(b, allow_nan=False)


def test_NEGATIVE_extreme_block_reads_every_optional_with_get():
    b = SR.si_block(_akan(), TODAY)
    for k in ("pct_of_float",):
        bb = dict(b)
        bb.pop(k)
        assert SR.extreme_block(bb) is None
    assert SR.extreme_block({"status": "ok", "headline_basis": "float"}) is None


def test_missing_float_source_published_on_and_float_asof_read_na():
    b = SR.si_block(_akan(), TODAY)
    for k in ("float_source", "published_on", "float_asof", "settlement_date"):
        b.pop(k, None)
    e_title = SR.extreme_title(b, 36.41)
    assert "n/a" in e_title and "531,210" in e_title
    bb = SR.si_block(_akan(float_source=None, float_asof=None), TODAY)
    assert bb["extreme"] is not None


# ═════════════════════════════════════════════ the constant moves the cut
def test_the_constant_moves_the_cut(monkeypatch):
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 40.0)
    assert SR.si_block(_eose(), FIX_TODAY)["extreme"] is None          # 33.59 < 40
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 30.0)
    e = SR.si_block(_eose(), FIX_TODAY)["extreme"]
    assert e is not None and "at or above 30% of the float" in e["title"]
    assert "20%" not in e["title"]


# ═════════════════════════════════════════════ C7 — a note failure never costs the chip
def _boom(*a, **k):
    return 1 / 0


def test_NEGATIVE_a_raising_note_never_costs_the_chip(monkeypatch, caplog):
    before = SR.si_block(_akan(), TODAY)
    monkeypatch.setattr(SR, "extreme_title", _boom)
    b = SR.si_block(_akan(), TODAY)
    assert b is not None and b["extreme"] is None
    assert b["chip"] == before["chip"] and b["title"] == before["title"] and b["rows"] == before["rows"]
    assert any("extreme note" in r.getMessage() for r in caplog.records)
    db = FakeDB({SIC.SI_COLL: FakeColl([_akan()], name=SIC.SI_COLL)})
    m = SR.si_map(["AKAN"], db=db, today=TODAY)
    assert list(m) == ["AKAN"] and m["AKAN"]["chip"] == before["chip"] and m["AKAN"]["extreme"] is None


# ═════════════════════════════════════════════ the map
def test_si_map_carries_extreme_and_absent_names_stay_absent():
    db = FakeDB({SIC.SI_COLL: FakeColl([_akan(), _akan(_id="GP", symbol="GP", short_interest=34_675,
                                                      float_shares=854_034)], name=SIC.SI_COLL)})
    m = SR.si_map(["AKAN", "GP", "NOPE"], db=db, today=TODAY)
    assert list(m) == ["AKAN", "GP"]
    assert m["AKAN"]["extreme"]["text"] == "🩳 EXTREME SI 36.4% float · 1.0d · 10/30"
    assert m["GP"]["pct_of_float"] == 4.06 and m["GP"]["extreme"] is None
    assert "NOPE" not in m


def test_block_key_order_ends_with_extreme():
    assert SR._BLOCK_KEYS[-1] == "extreme" and SR._BLOCK_KEYS[-2] == "rows"
    assert list(SR.si_block(_akan(), TODAY))[-1] == "extreme"
    assert list(SR.si_block(CASES["no_record_miss"]["doc"], FIX_TODAY))[-1] == "extreme"


# ═════════════════════════════════════════════ wording
def _served_strings():
    out = []
    docs = [c["doc"] for c in CASES.values()] + [_akan(), _ratio(20_000), _akan(days_to_cover=None)]
    for d in docs:
        for today in (FIX_TODAY, TODAY):
            e = SR.si_block(d, today)["extreme"]
            if e:
                out += [e["text"], e["short"], e["title"], e["basis"]]
    return out


def test_NEGATIVE_no_served_extreme_string_or_pick_reads_as_a_forecast():
    texts = _served_strings()
    assert len(texts) >= 12
    picks = [p for p in SR.rules_section()["picks"] if "EXTREME" in p]
    assert len(picks) == 1
    for t in texts + picks:
        assert not FORBIDDEN.search(t), t
        assert "band" not in t.lower() and "did not run" not in t.lower(), t
        if t not in picks:                                     # the pick SAYS "never shows 0%"
            assert not re.search(r"(?<![\d.])0(\.0+)?%", t), t
    for d in [c["doc"] for c in CASES.values()] + [_akan()]:
        json.dumps(SR.si_block(d, TODAY), allow_nan=False)


def test_rules_pick_is_built_from_the_constant(monkeypatch):
    (pick,) = [p for p in SR.rules_section()["picks"] if "EXTREME" in p]
    assert ("%g%%" % SIC.SI_HIGH_PCT) in pick and "SI_HIGH_PCT" in pick
    assert "too small to call either way" in pick and "UNMEASURED" in pick
    assert "band" not in pick.lower() and "Reversal Squeeze" not in pick
    picks = SR.rules_section()["picks"]
    assert picks.index(pick) == 2 and picks[1].startswith("% of float = ")
    monkeypatch.setattr(SIC, "SI_HIGH_PCT", 25.0)
    (moved,) = [p for p in SR.rules_section()["picks"] if "EXTREME" in p]
    assert "at or above 25% of the float" in moved and "at or above 20%" not in moved


# ═════════════════════════════════════════════ the refactor is byte-neutral
@pytest.mark.parametrize("name", sorted(CASES))
def test_chip_text_default_equals_the_fixture_chip(name):
    b = CASES[name]["block"]
    assert SR.chip_text(b) == b["chip"]
    assert SR.chip_text(b, tag="") == b["chip"]


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_fixture_extreme_leaf_is_what_extreme_block_serves(name):
    b = CASES[name]["block"]
    assert SR.extreme_block(b) == b["extreme"]
    want = {"eose_v2_float", "dtc_missing"}
    assert (b["extreme"] is not None) == (name in want)


# ═════════════════════════════════════════════ SOURCE GUARD — the cut is the constant by name
_SRC = (BACKEND / "short_interest" / "read.py").read_text(encoding="utf-8")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def _extreme_slice(src: str) -> str:
    i = src.index("EXTREME_WORD = ")
    j = src.index("\ndef si_block", i)
    return src[i:j]


_NONZERO = re.compile(r"(?<![\w.])(?!0+(?:\.0+)?(?![\d.]))\d+(?:\.\d+)?")


def _literal_offenders(sl: str) -> list:
    """Every numeric code literal except the zero sign guard (`days_to_cover > 0`, the chip's own rule —
    a sign test, not a cut), plus every non-zero number inside a string literal other than an ISO date
    (the study's date). Format directives (%g, %s, %.1f) carry no digits that count."""
    bad = []
    for tok in tokenize.generate_tokens(io.StringIO(sl).readline):
        if tok.type == tokenize.NUMBER and tok.string != "0":
            bad.append(tok.string)
        elif tok.type == tokenize.STRING:
            body = _ISO.sub("", tok.string)
            bad += _NONZERO.findall(body)
    return bad


def test_SOURCE_GUARD_no_numeric_literal_in_the_extreme_slice():
    sl = _extreme_slice(_SRC)
    assert "def extreme_block" in sl and "def extreme_title" in sl
    assert "SIC.SI_HIGH_PCT" in sl and "pf < SIC.SI_HIGH_PCT" in sl
    assert _literal_offenders(sl) == []
    assert not re.search(r"\b20(\.0+)?\b", sl)


@pytest.mark.parametrize("mutant", [
    ("pf < SIC.SI_HIGH_PCT", "pf < 20"),
    ("pf < SIC.SI_HIGH_PCT", "pf < 20.0"),
    ("EXTREME_RULE_NOTE % SIC.SI_HIGH_PCT", "EXTREME_RULE_NOTE % 20"),
    ('"at or above %g%% of the float', '"at or above 20% of the float'),
    ("b[\"days_to_cover\"] > 0", "b[\"days_to_cover\"] > 0.5"),
])
def test_NEGATIVE_the_source_guard_catches_a_typed_number(mutant):
    old, new = mutant
    sl = _extreme_slice(_SRC)
    assert old in sl
    assert _literal_offenders(sl.replace(old, new, 1)) != []


def test_SOURCE_GUARD_the_note_is_not_read_by_any_gate_push_or_sort():
    # the note lives on the read only; nothing in the push / gate stack imports extreme_block
    for rel in ("alerts", "chart_maps/board.py", "autopilot"):
        p = BACKEND / rel
        files = [p] if p.is_file() else (list(p.rglob("*.py")) if p.exists() else [])
        for f in files:
            assert "extreme_block" not in f.read_text(encoding="utf-8", errors="ignore"), f
