"""📅 Long Term — 🎯 Enterable (zones): the served per-row `zone` block + `zone_rules` (2026-11-14, ltenter spec §3.1-3.4,
§3.6, §3.9, §4 WP-BE).

Ajay 2026-11-14, verbatim: "Make a enterable check box in longterm stocks with zone and filters please".

One engine (`sepa.pankaj_picks.setup_status`), two sheets (Pankaj's seed zones + Gabbar's split-adjusted bands), the
proximity = `alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT` imported by name. A display filter only — no push, no gate, no
ordering. UNMEASURED. NEGATIVES throughout: fell-through / too-far / no price / no zone are never enterable; the
Gabbar closes never leak into the 🧭 / 🔔 paths; the public ℹ️ panel never names Pankaj; no NaN served; no "buy zone".
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from catalysts import gabbar_levels as GL
from long_term_list import api as API
from long_term_list import constants as C
from long_term_list import payload as P
from long_term_list import seed as SD
from long_term_list import sources as SRC
from long_term_list import store as ST
from long_term_list import weekly as WK
from long_term_list import words as W
from long_term_list import zones as Z
from sepa import pankaj_picks as PK
from supply_demand import alert_gates as AG
from tests.test_long_term_list_store import FakeColl

BACKEND = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "long_term_list"
BANNED = re.compile(r"\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b", re.I)
REBOUND = re.compile("bou" + "nce", re.I)
DATE = "2026-11-13"
NOW_FRI = dt.datetime(2026, 11, 20, 18, 0)
ZONES = {"TSM": {"close": 405.49, "date": "2026-11-20"}, "META": {"close": 623.61, "date": "2026-11-20"},
         "NVDA": {"close": 166.19, "date": "2026-11-20"}, "INTU": {"close": 340.17, "date": "2026-11-20"}}
ET = ZoneInfo("America/New_York")
OWNER = "owner@example.com"

NEW_NAMES = ("ENTERABLE_ABOVE_PCT", "GABBAR_SNAPSHOT_DATE", "ZONE_SOURCES", "GABBAR_DEEP_LEVEL_KEY", "GABBAR_DEEP_FROM",
             "ZONE_REASON_CODES", "ZONE_FILTER_LS_KEY")


def _band(lo, hi, key="C1", source="pankaj"):
    label = f"{'Pankaj' if source == 'pankaj' else 'Gabbar'} {key}"
    return {"source": source, "key": key, "level": key, "label": label, "lo": lo, "hi": hi}


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _seed_only(**kw):
    return P.build_payload(SD.load(), _load("baseline_mini.json"), [], [], kw.get("zones", ZONES),
                           now=dt.datetime(2026, 11, 12, 22, 0), owner=True, **{k: v for k, v in kw.items()
                                                                                  if k != "zones"})


def _rows(p):
    return [r for c in p["categories"] for r in c["rows"]] + p["changed"]


def _row(p, sym):
    return next(r for r in _rows(p) if r["symbol"] == sym)


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_imported_by_name():
    assert C.ENTERABLE_ABOVE_PCT is AG.ALERT_MAX_ABOVE_DEMAND_PCT
    assert C.GABBAR_SNAPSHOT_DATE == GL.BAND_ATTRIBUTION["snapshot_date"]
    assert C.CONSTANT_SOURCES["ENTERABLE_ABOVE_PCT"] == "HIS"
    assert C.CONSTANT_SOURCES["ZONE_FILTER_LS_KEY"] == "MINE"
    assert C.CONSTANT_SOURCES["GABBAR_DEEP_LEVEL_KEY"] == "MINE" and C.CONSTANT_SOURCES["GABBAR_DEEP_FROM"] == "MINE"
    assert C.ZONE_FILTER_LS_KEY == "lt_zone_filter_v1"                  # the FE pins the same literal
    assert C.ZONE_REASON_CODES == ("below", "above", "no_zone", "no_price", "filtered")


def test_every_new_upper_name_is_in_constant_sources():
    for name in NEW_NAMES:
        assert hasattr(C, name), name
        assert name in C.CONSTANT_SOURCES, name


def test_NEGATIVE_no_new_pct_literal_typed_in_constants():
    pre_existing = {"CQ_MIN_ROE_PCT", "CQ_MIN_FCF_MARGIN_PCT", "FALLEN_MIN_PCT_ABOVE_LOW", "FALLEN_MIN_SALES_YOY_PCT",
                    "QUIET_MIN_SALES_CAGR_PCT", "QUIET_MIN_PCT_BELOW_HIGH", "ACCEL_MIN_PRIOR_YOY_PCT",
                    "ACCEL_MIN_PCT_BELOW_HIGH", "ACCEL_MIN_PCT_ABOVE_LOW", "FORWARD_CI_PCT"}
    src = (BACKEND / "long_term_list" / "constants.py").read_text(encoding="utf-8")
    typed = {m.group(1) for m in re.finditer(r"^(\w*_PCT\w*)\s*=\s*[-\d.]", src, re.M)}
    assert typed == pre_existing, typed ^ pre_existing
    assert re.search(r"^ENTERABLE_ABOVE_PCT\s*=\s*AG\.ALERT_MAX_ABOVE_DEMAND_PCT\b", src, re.M)


# ── the engine: the §3.6 case table ──────────────────────────────────────────────────────────────────────────────
CASES = [
    ("VRT inside C1", [(195, 205)], 200.00, "inside", 0.0, True, 0),
    ("pad edge 0.4% above hi", [(100, 110)], 110.44, "inside", 0.0, True, 0),
    ("0.6% above hi", [(100, 110)], 110.66, "near", 0.6, True, 0),
    ("1.0% above hi", [(100, 110)], 111.10, "near", 1.0, True, 0),
    ("META 1.9% above C1", [(620, 630)], 641.97, "above", 1.9, False, 0),
    ("NFLX 3.6% above cons.2", [(55, 60)], 62.16, "above", 3.6, False, 0),
    ("pad edge 0.4% under lo", [(100, 110)], 99.60, "inside", 0.0, True, 0),
    ("0.6% under lo fell through", [(100, 110)], 99.40, "below", -0.6, False, 0),
    ("GOOGL 4.6% under C1", [(310, 315)], 295.74, "below", -4.6, False, 0),
    ("BKNG Gabbar aggressive ÷25", [(148, 156)], 150.00, "inside", 0.0, True, 0),
    ("two bands, inside the second", [(100, 110), (120, 130)], 125.00, "inside", 0.0, True, 1),
    ("two bands, 0.8% above band 1", [(100, 110), (150, 160)], 110.88, "near", 0.8, True, 0),
    ("nearest wins: 2.0% over band 1, 1.0% under band 2", [(100, 110), (113.33, 120)], 112.20, "below", -1.0, False, 1),
]


@pytest.mark.parametrize("name,pairs,price,state,pct,ent,idx", CASES, ids=[c[0] for c in CASES])
def test_case_table(name, pairs, price, state, pct, ent, idx):
    bands = [_band(lo, hi, key=f"Z{i}") for i, (lo, hi) in enumerate(pairs)]
    r = Z.read(bands, price, DATE)
    assert (r["state"], r["pct"], r["enterable"]) == (state, pct, ent), name
    assert r["band"]["key"] == f"Z{idx}"
    assert r["basis"] == "close" and r["price"] == price


def test_NEGATIVE_fell_through_and_too_far_are_not_enterable():
    assert Z.read([_band(100, 110)], 99.40, DATE)["enterable"] is False
    assert Z.read([_band(620, 630)], 641.97, DATE)["enterable"] is False


@pytest.mark.parametrize("price", [None, float("nan"), 0, -1, float("inf"), "200"])
def test_NEGATIVE_no_price(price):
    r = Z.read([_band(195, 205)], price, DATE)
    assert r["state"] == "no_price" and r["enterable"] is None and r["band"] is None and r["pct"] is None
    assert r["text"] == W.ZONE_WORDS["no_price"] and r["price"] is None


def test_NEGATIVE_no_bands_is_no_zone_checked_before_no_price():
    r = Z.read([], 200.0, DATE)
    assert r["state"] == "no_zone" and r["enterable"] is None and r["text"] == W.ZONE_WORDS["no_zone"]
    assert Z.read([], None, DATE)["state"] == "no_zone"                  # NOT no_price — the order


def test_band_state_is_the_one_engine():
    rng = random.Random(20261114)
    b = _band(100, 110)
    for _ in range(20):
        px = round(rng.uniform(80, 130), 2)
        st = PK.setup_status({"kind": "pullback", "zone": {"lo": 100, "hi": 110}}, px)
        want = {"in_zone": "in", "above_zone": "above", "below_zone": "below"}[st["state"]]
        assert Z.band_state(b, px) == (want, st["dist_pct"])


def test_proximity_is_never_typed(monkeypatch):
    monkeypatch.setattr(C, "ENTERABLE_ABOVE_PCT", 3.0)
    r = Z.read([_band(620, 630)], 641.97, DATE)
    assert r["state"] == "near" and r["enterable"] is True


def test_pad_follows_the_engines_constant_not_a_copy(monkeypatch):
    # Coupling documented: band_state reads PK.ZONE_PAD_PCT (the /pankaj engine); C.PANKAJ_ZONE_PAD_PCT is the same
    # number, served as pad_pct so the FE agrees. Moving the copy alone does nothing.
    assert C.PANKAJ_ZONE_PAD_PCT == PK.ZONE_PAD_PCT
    monkeypatch.setattr(C, "PANKAJ_ZONE_PAD_PCT", 0.0)
    assert Z.read([_band(100, 110)], 110.44, DATE)["state"] == "inside"
    monkeypatch.setattr(PK, "ZONE_PAD_PCT", 0.0)
    assert Z.read([_band(100, 110)], 110.44, DATE)["state"] == "near"


def test_date_is_served_iso_and_printed_mmdd():
    r = Z.read([_band(195, 205)], 200.0, DATE)
    assert r["date"] == "2026-11-13" and r["text"].endswith("· close 11-13")
    assert Z.read([_band(195, 205)], 200.0, None)["text"].endswith(f"· close {W.DASH}")


# ── row_block ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def seed():
    return SD.load()


def test_NEGATIVE_row_block_with_none_close_never_raises(seed):
    order = SD.zone_order(seed)
    b = Z.row_block("MANH", None, order, None)
    assert b["bands"] == [] and b["gabbar_text"] is None
    assert b["close"]["state"] == "no_zone" and b["close"]["enterable"] is None
    assert set(b) == {"bands", "gabbar_text", "close"}
    amd = Z.row_block("AMD", None, order, None)
    assert amd["bands"] and {x["source"] for x in amd["bands"]} == {"gabbar"}
    assert amd["close"]["state"] == "no_price"
    ent = SD.pankaj_entries(seed)["TSM"]
    assert Z.row_block("TSM", ent, order, {})["close"]["state"] == "no_price"
    assert Z.row_block("TSM", ent, order, "garbage")["close"]["state"] == "no_price"


# ── bands ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_bkng_gabbar_bands_split_adjusted_level_by_index():
    got = [(b["lo"], b["hi"], b["key"], b["level"]) for b in Z.gabbar_bands("BKNG")]
    assert got == [(148.0, 156.0, "aggressive", "aggressive"), (128.0, 136.0, "conservative 1", "conservative 1"),
                   (108.0, 116.0, "conservative 2", C.GABBAR_DEEP_LEVEL_KEY)]
    assert all(b["label"] == f"Gabbar {b['key']}" and b["source"] == "gabbar" for b in Z.gabbar_bands("BKNG"))
    assert "÷25 split-adjusted (04-06)" in Z.gabbar_text("BKNG")


def test_level_follows_gabbar_deep_from(monkeypatch):
    monkeypatch.setattr(C, "GABBAR_DEEP_FROM", 3)
    assert [b["level"] for b in Z.gabbar_bands("BKNG")] == ["aggressive", "conservative 1", "conservative 2"]


def test_NEGATIVE_no_label_tuple_typed_in_zones_source():
    src = (BACKEND / "long_term_list" / "zones.py").read_text(encoding="utf-8")
    assert "conservative 1" not in src and "aggressive" not in src


def test_NEGATIVE_bkng_never_serves_the_pre_split_level(seed):
    p = _seed_only(zone_closes_all={"BKNG": {"close": 150.0, "date": DATE}})
    row = _row(p, "BKNG")
    assert not [s for s in _strings(row) if "3700" in s]
    assert "3700" not in json.dumps(row["zone"])
    assert row["zone"]["close"]["state"] == "inside"


def test_lly_tsm_nvda_fslr_amd_manh_anet(seed):
    pk, order = SD.pankaj_entries(seed), SD.zone_order(seed)
    lly = Z.gabbar_bands("LLY")
    assert len(lly) == 4 and [b["level"] for b in lly].count(C.GABBAR_DEEP_LEVEL_KEY) == 2
    for s in ("TSM", "NVDA"):
        assert Z.gabbar_text(s) == W.gabbar_tracked_text(s) and Z.gabbar_bands(s) == []
    fslr = Z.bands_for("FSLR", pk.get("FSLR"), order)
    assert fslr and {b["source"] for b in fslr} == {"gabbar"}                  # 🧭 name with no pair
    assert {b["source"] for b in Z.bands_for("AMD", pk.get("AMD"), order)} == {"gabbar"}
    manh = Z.row_block("MANH", pk.get("MANH"), order, None)
    assert manh["bands"] == [] and manh["close"]["state"] == "no_zone"
    anet = Z.bands_for("ANET", pk.get("ANET"), order)
    n_pk = len(Z.pankaj_bands(pk["ANET"], order))
    assert n_pk >= 2 and [b["source"] for b in anet] == ["pankaj"] * n_pk + ["gabbar"] * 3
    assert [b["key"] for b in anet[:n_pk]] == [zk for zk in order if pk["ANET"]["zones"][zk][0] is not None]


def test_intu_reads_the_gabbar_band_not_pankaj_agg(seed):
    pk, order = SD.pankaj_entries(seed), SD.zone_order(seed)
    r = Z.row_block("INTU", pk["INTU"], order, {"close": 340.17, "date": DATE})["close"]
    assert r["state"] == "inside" and r["band"]["label"] == "Gabbar conservative 1"
    assert r["text"] == "inside Gabbar conservative 1 335–350 · close 11-13"


def test_gabbar_level_keys_derived(seed):
    assert Z.gabbar_level_keys(seed) == ("aggressive", "conservative 1", C.GABBAR_DEEP_LEVEL_KEY)


def test_zone_symbols_derived_from_the_seed(seed):
    pk = SD.pankaj_entries(seed)

    def has_pair(s):
        return any(lo is not None and hi is not None for lo, hi in (pk.get(s) or {}).get("zones", {}).values())
    want = [s for s in SD.unique_names(seed) if has_pair(s) or GL.get_bands(s)]
    assert Z.zone_symbols(seed) == want
    assert "MANH" not in want and "AMD" in want and "TSM" in want


# ── payload ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_top_keys_and_row_key_order():
    assert P.TOP_KEYS.index("zone_rules") == P.TOP_KEYS.index("zones") + 1
    p = _seed_only()
    assert tuple(p.keys()) == P.TOP_KEYS
    rows = _rows(p)
    assert len(rows) == 109
    for r in rows:
        keys = list(r)
        assert keys.index("zone") == keys.index("pankaj") + 1 and keys[-1] == "caveat_tag"
        assert set(r["zone"]) == {"bands", "gabbar_text", "close"}


def test_zone_rules_block(seed):
    zr = _seed_only()["zone_rules"]
    assert list(zr) == ["pad_pct", "above_pct", "snapshot_date", "ls_key", "text", "sources", "levels", "reasons",
                        "words"]
    assert zr["pad_pct"] == C.PANKAJ_ZONE_PAD_PCT and zr["above_pct"] == C.ENTERABLE_ABOVE_PCT
    assert zr["snapshot_date"] == C.GABBAR_SNAPSHOT_DATE and zr["ls_key"] == C.ZONE_FILTER_LS_KEY
    order = SD.zone_order(seed)
    assert [(lv["source"], lv["key"]) for lv in zr["levels"]] == (
        [("pankaj", zk) for zk in order] + [("gabbar", k) for k in Z.gabbar_level_keys(seed)])
    assert [r["code"] for r in zr["reasons"]] == list(C.ZONE_REASON_CODES)
    assert [s["key"] for s in zr["sources"]] == ["both", "pankaj", "gabbar"]
    assert zr["words"]["dash"] == W.DASH and zr["words"] == W.ZONE_WORDS


def test_NEGATIVE_gabbar_closes_never_leak_into_the_pankaj_paths():
    extra = dict(ZONES, AMD={"close": 191.52, "date": DATE}, BKNG={"close": 150.0, "date": DATE})
    a = _seed_only()
    b = _seed_only(zone_closes_all=extra)
    assert json.dumps(a["zones"], sort_keys=True) == json.dumps(b["zones"], sort_keys=True)
    for ra, rb in zip(_rows(a), _rows(b)):
        assert ra["symbol"] == rb["symbol"] and ra["pankaj"] == rb["pankaj"]
    assert "AMD" not in [z["symbol"] for z in b["zones"]["at_zone"]]
    assert _row(a, "AMD")["zone"]["close"]["state"] == "no_price"
    amd = _row(b, "AMD")["zone"]["close"]
    assert amd["state"] == "near" and amd["text"] == "just above Gabbar aggressive 180–190 · +0.8% · close 11-13"


def test_NEGATIVE_nan_close_never_served():
    p = _seed_only(zone_closes_all={"AMD": {"close": float("nan"), "date": DATE},
                                    "TSM": {"close": float("inf"), "date": DATE}})
    json.dumps(p, allow_nan=False)
    assert _row(p, "AMD")["zone"]["close"]["state"] == "no_price"
    assert _row(p, "TSM")["zone"]["close"]["state"] == "no_price"


def test_rules_lines_owner_only_line():
    pub = W.rules_lines()
    assert "zone_enterable" not in [r["key"] for r in pub]                  # NEGATIVE: the public ℹ️ panel
    assert "Pankaj" not in json.dumps(pub, ensure_ascii=False)
    own = W.rules_lines(include_pankaj=True)
    keys = [r["key"] for r in own]
    assert keys.count("zone_enterable") == 1 and keys.index("zone_enterable") == keys.index("zone_alert") + 1
    line = own[keys.index("zone_enterable")]
    assert line["source"] == "MINE" and line["his_call"] is True and line["text"] == W.ZONE_RULES_TEXT
    assert [r["key"] for r in _seed_only()["rules"]] == keys


def test_NEGATIVE_public_rules_panel_has_no_zone_enterable():
    from supply_demand import rules_info as RI
    sec = RI.sections()["long_term"]
    blob = json.dumps(sec, ensure_ascii=False)
    assert "Enterable (zones)" not in blob and "Pankaj" not in blob


def test_owner_only_still_three_keys():
    p = P.build_payload(SD.load(), {}, [], [], ZONES, now=NOW_FRI, owner=False,
                        zone_closes_all={"AMD": {"close": 191.52, "date": DATE}})
    assert set(p) == {"state", "reason", "title"}


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_zone_cell_text_literals():
    assert W.zone_cell_text("inside", _band(195, 205), 0.0, "close", DATE) == "inside Pankaj C1 195–205 · close 11-13"
    assert (W.zone_cell_text("near", _band(180, 190, "aggressive", "gabbar"), 0.8, "close", DATE)
            == "just above Gabbar aggressive 180–190 · +0.8% · close 11-13")
    assert (W.zone_cell_text("above", _band(620, 630), 1.9, "close", DATE)
            == "above the zone Pankaj C1 620–630 · +1.9% · close 11-13")
    assert (W.zone_cell_text("below", _band(310, 315), -4.6, "close", DATE)
            == "below the zone Pankaj C1 310–315 · -4.6% · close 11-13")
    assert W.zone_cell_text("no_price", None, None, "close", DATE) == "no price read"
    assert W.zone_cell_text("no_zone", None, None, "close", DATE) == "no zone on either sheet"
    assert W.zone_cell_text("filtered", None, None, "close", DATE) == "no zone under this filter"
    assert W.zone_cell_text("inside", _band(195, 205), 0.0, "close", None).endswith(W.DASH)
    for name, pairs, price, *_ in CASES:
        r = Z.read([_band(lo, hi) for lo, hi in pairs], price, DATE)
        assert r["text"] == W.zone_cell_text(r["state"], r["band"], r["pct"], "close", DATE)


def _new_served():
    p = _seed_only(zone_closes_all=dict(ZONES, AMD={"close": 191.52, "date": DATE}, BKNG={"close": 150.0, "date": DATE}))
    out = list(_strings(p["zone_rules"]))
    for r in _rows(p):
        out += list(_strings(r["zone"]))
    out += [ln["text"] for ln in W.rules_lines(include_pankaj=True) if ln["key"] == "zone_enterable"]
    return out


def test_NEGATIVE_no_banned_word_no_rebound_no_buy_zone():
    served = _new_served()
    assert served
    assert not [s for s in served if BANNED.search(s)]
    assert not [s for s in served if REBOUND.search(s)]
    assert not [s for s in served if re.search(r"buy\s*zone", s, re.I)]
    full = json.dumps(_seed_only(), ensure_ascii=False)
    assert not re.search(r"buy[\s-]*zone", full, re.I)
    src = (BACKEND / "long_term_list" / "zones.py").read_text(encoding="utf-8")
    assert not BANNED.search(src) and not REBOUND.search(src) and not re.search(r"buy\s*zone", src, re.I)


# ── api ──────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def wired(monkeypatch):
    import ollama_chat.api as OA
    db = {C.RUNS_COLL: FakeColl(C.RUNS_COLL), C.FORWARD_COLL: FakeColl(C.FORWARD_COLL),
          C.CLAIMS_COLL: FakeColl(C.CLAIMS_COLL)}
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(ST, "_db", lambda: db)
    calls = []

    def _closes(symbols, now=None):
        calls.append(list(symbols))
        return {"TSM": {"close": 405.49, "date": DATE}, "AMD": {"close": 191.52, "date": DATE}}
    monkeypatch.setattr(SRC, "pankaj_closes", _closes)

    def _never(*a, **k):
        raise AssertionError("the GET built a week")
    monkeypatch.setattr(WK, "run", _never)
    monkeypatch.setattr(SRC, "load_all", _never)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.closes_calls = calls
    return c


def test_api_one_closes_read_over_the_union(wired):
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    body = r.json()
    assert r.status_code == 200 and len(wired.closes_calls) == 1
    syms = wired.closes_calls[0]
    seed = SD.load()
    assert "AMD" in syms and "TSM" in syms
    assert sorted(syms) == sorted(set(SD.pankaj_entries(seed)) | set(Z.zone_symbols(seed)))
    assert "MANH" not in syms                                            # a no-zone name is not read
    assert _row(body, "AMD")["zone"]["close"]["state"] == "near"
    assert "AMD" not in [z["symbol"] for z in body["zones"]["at_zone"]]  # NEG: Gabbar closes stay out of 🧭
    assert [z["symbol"] for z in body["zones"]["at_zone"]] == ["TSM"]


def test_api_raising_closes_still_answers(wired, monkeypatch):
    def _boom(symbols, now=None):
        raise RuntimeError("cache down")
    monkeypatch.setattr(SRC, "pankaj_closes", _boom)
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    body = r.json()
    assert r.status_code == 200 and body["state"] == "seed_only"
    assert {x["zone"]["close"]["state"] for x in _rows(body)} <= {"no_price", "no_zone"}


def test_NEGATIVE_api_non_owner_gets_owner_only(wired):
    r = wired.get(C.API_PATH, headers={"X-User-Email": "doug@example.com"})
    assert r.status_code == 200 and set(r.json()) == {"state", "reason", "title"}
    assert "zone_rules" not in r.text and wired.closes_calls == []


def test_api_closes_failure_path_never_math_nan(wired, monkeypatch):
    monkeypatch.setattr(SRC, "pankaj_closes", lambda symbols, now=None: {"AMD": {"close": math.nan, "date": DATE}})
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    assert "NaN" not in r.text and _row(r.json(), "AMD")["zone"]["close"]["state"] == "no_price"
