"""📅 Long Term (2026-11-12) — the served payload: owner-only gate, section order, one row per
symbol, no Possible Action, NaN-free, seed_only / error states, golden key set."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from growth.api import _scrub
from long_term_list import constants as C
from long_term_list import payload as P
from long_term_list import seed as SD
from long_term_list import words as W

FIX = Path(__file__).parent / "fixtures" / "long_term_list"
GOLDEN = Path(__file__).parent / "fixtures" / "long_term_list_payload_golden.json"
NOW_FRI = dt.datetime(2026, 11, 20, 18, 0)
ZONES = {"TSM": {"close": 405.49, "date": "2026-11-20"}, "META": {"close": 623.61, "date": "2026-11-20"},
         "NVDA": {"close": 166.19, "date": "2026-11-20"}, "INTU": {"close": 340.17, "date": "2026-11-20"}}


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _ready(**kw):
    return P.build_payload(SD.load(), _load("baseline_mini.json"), _load("runs_w46_w47.json"),
                           _load("forward_w47.json"), kw.get("zones", ZONES), now=kw.get("now", NOW_FRI),
                           owner=True)


def _seed_only():
    return P.build_payload(SD.load(), _load("baseline_mini.json"), [], [], ZONES,
                           now=dt.datetime(2026, 11, 12, 22, 0), owner=True)


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def key_paths(o, prefix=""):
    out = set()
    if isinstance(o, dict):
        for k, v in o.items():
            p = f"{prefix}.{k}" if prefix else k
            out.add(p)
            out |= key_paths(v, p)
    elif isinstance(o, list):
        for v in o:
            out |= key_paths(v, prefix + "[]")
    return out


def test_owner_false_is_exactly_three_keys():
    p = P.build_payload(SD.load(), _load("baseline_mini.json"), _load("runs_w46_w47.json"),
                        _load("forward_w47.json"), ZONES, now=NOW_FRI, owner=False)
    assert p == {"state": "owner_only", "reason": W.OWNER_ONLY_TEXT, "title": C.TITLE}


def test_negative_owner_only_leaks_nothing():
    p = P.build_payload(SD.load(), _load("baseline_mini.json"), _load("runs_w46_w47.json"),
                        _load("forward_w47.json"), ZONES, now=NOW_FRI, owner=False)
    text = json.dumps(p, ensure_ascii=False)
    assert "Pankaj" not in text
    for sym in SD.unique_names(SD.load()):
        assert f'"{sym}"' not in text and f" {sym} " not in text
    for w in SD.his_words(SD.load()):
        assert w[:30] not in text


def test_ready_section_order_and_keys():
    p = _ready()
    assert p["state"] == "ready" and p["reason"] is None
    assert tuple(p.keys()) == P.TOP_KEYS
    assert [c["key"] for c in p["categories"]] == list(C.CATEGORY_KEYS)
    assert p["measured"] is False and p["not_a_signal"] == W.NOT_A_SIGNAL
    assert p["as_of"]["week"] == "2026-W47" and p["as_of"]["session"] == "2026-11-20"
    assert p["as_of"]["next_run_text"].endswith("next: Friday 2026-11-27.")      # Thanksgiving week: Fri is open


def test_one_row_per_symbol_with_all_chips():
    p = _ready()
    rows = [r for c in p["categories"] for r in c["rows"]] + p["changed"]
    syms = [r["symbol"] for r in rows]
    assert len(syms) == len(set(syms)) == 109
    anet = next(r for r in rows if r["symbol"] == "ANET")
    assert [c["key"] for c in anet["chips"]] == ["capital_quality", "bonde", "pankaj"]
    assert anet["pankaj"]["tier_text"].startswith("Pankaj: Tier ")


def test_changed_and_started_moving_sections():
    p = _ready()
    assert [r["symbol"] for r in p["changed"]] == ["AMD", "MA"]
    amd = p["changed"][0]
    assert amd["status"]["key"] == "changed"
    assert amd["events"][0]["kind"] == "stage_drop"
    assert [s["symbol"] for s in p["started_moving"]] == ["HLNE"]
    assert p["started_moving"][0]["date"] == "2026-11-20"
    quiet = next(c for c in p["categories"] if c["key"] == "quiet_strong")
    assert quiet["moved_text"] == "MPWR 8.2% under its 52-week high (needs ≥ 10%)"
    assert "HLNE" in [r["symbol"] for r in quiet["rows"]]
    mpwr = next(r for r in quiet["rows"] if r["symbol"] == "MPWR")
    assert mpwr["status"]["key"] == "holding"


def test_xpel_absent_is_not_read_not_dropped():
    p = _ready()
    xpel = next(r for c in p["categories"] for r in c["rows"] if r["symbol"] == "XPEL")
    assert xpel["status"]["key"] in ("holding", "not_read")
    assert any("not read, not dropped" in e["text"] for e in xpel["events"])


def test_sales_text_carries_quarter_and_read_dates():
    p = _ready()
    hlne = next(r for c in p["categories"] for r in c["rows"] if r["symbol"] == "HLNE")
    assert hlne["sales"]["text"] == "Sales +30.0% y/y · tier strong · quarter ended 2026-09-30 · read 2026-11-08"


def test_negative_no_possible_action_strings():
    text = json.dumps(_ready(), ensure_ascii=False) + json.dumps(_seed_only(), ensure_ascii=False)
    for a in ("Wait and Watch", "Buy CL1", "Buy CL2", "Buy Zone AAG1", "Going for CL1", "Going for CL2",
              "Going for CL3", '"action"'):
        assert a not in text


def test_negative_nan_inf_scrubbed():
    runs = _load("runs_w46_w47.json")
    runs[-1]["names"]["AMD"]["sales_yoy_pct"] = float("nan")
    runs[-1]["digest"]["n_new_in_top"] = 1
    fwd = _load("forward_w47.json")
    fwd[1].update({"list_pct": float("inf"), "rsp_pct": float("nan"), "n_sessions": 21})
    p = P.build_payload(SD.load(), _load("baseline_mini.json"), runs, fwd, ZONES, now=NOW_FRI, owner=True)
    assert p["forward"]["too_early"] is False and p["forward"]["points"][0]["list_pct"] is None
    assert p["forward"]["points"][0]["rsp_pct"] is None
    json.dumps(_scrub(p), allow_nan=False)
    json.dumps(p, allow_nan=False)


def test_null_field_renders_dash():
    p = _ready()
    nrix = next(r for c in p["categories"] for r in c["rows"] if r["symbol"] == "NRIX")
    f = next(f for f in nrix["fields"] if f["key"] == "sales_yoy")
    assert f["text"] == "—" and f["verdict"] == "unknown"


def test_seed_only_109_rows_and_pankaj_zone_read():
    p = _seed_only()
    assert p["state"] == "seed_only" and p["digest"] is None
    rows = [r for c in p["categories"] for r in c["rows"]] + p["changed"]
    assert len(rows) == 109 and p["changed"] == []
    assert all(r["status"]["text"] == "Saved 2026-11-12 — first weekly read 2026-11-13 after 4:30 PM ET"
               for r in rows)
    z = p["zones"]
    assert [a["symbol"] for a in z["at_zone"]] == ["TSM", "META", "NVDA"]
    assert z["at_zone"][0]["zone_text"] == "In Pankaj's Agg zone (400–410) at the 11-20 close"
    intu = next(r for r in rows if r["symbol"] == "INTU")
    assert intu["pankaj"]["zone_text"] == "23.7% over Pankaj's Agg zone top (275)"
    brk = next(a for a in rows if a["symbol"] == "BRK-B")
    assert brk["pankaj"]["zone_text"] == "No cached close"
    assert p["forward"]["too_early"] is True and p["forward"]["points"] == []
    assert all(c["top"] == [] for c in p["categories"])
    amd = next(r for r in rows if r["symbol"] == "AMD")
    assert amd["stage"]["text"] == "Stage 2 · Advancing (saved at Stage 2)"
    assert [f["key"] for f in amd["fields"]][:2] == ["qualifier", "stage"]


def test_negative_error_when_the_seed_sha_mismatches(monkeypatch):
    monkeypatch.setattr(C, "SEED_SHA256", "0" * 64)
    p = P.build_payload(None, {}, [], [], {}, now=NOW_FRI, owner=True)
    assert p["state"] == "error" and "changed" in p["reason"]
    assert "categories" not in p


def test_negative_owner_check_first_even_on_a_broken_seed(monkeypatch):
    monkeypatch.setattr(C, "SEED_SHA256", "0" * 64)
    assert P.build_payload(None, {}, [], [], {}, now=NOW_FRI, owner=False)["state"] == "owner_only"


def test_negative_strip_rows_carry_no_fields():
    p = _ready()
    s2 = next(c for c in p["categories"] if c["key"] == "s2_growth")
    assert [t["symbol"] for t in s2["top"]] == ["AMC", "NEWX"]
    for c in p["categories"]:
        for t in c["top"]:
            assert set(t) == {"symbol", "name", "sector", "rank_text", "new"}
    assert [t["new"] for t in s2["top"]] == [False, True]
    pk = next(c for c in p["categories"] if c["key"] == "pankaj")
    assert pk["top"] == [] and pk["top_text"] is None


def test_digest_history_forward_rules():
    p = _ready()
    assert p["digest"]["title"].startswith("📅 Long Term — week of 2026-11-20: 1 dropped")
    assert p["digest"]["pushed_text"] == "Phone push is off — this digest shows here only."
    assert [h["week"] for h in p["history"]] == ["2026-W47", "2026-W46"]
    assert p["history"][1]["n_events"].get("zone") == 1
    assert p["forward"]["too_early"] is True and p["forward"]["counts_line"].startswith("1 without a 2026-11-13")
    assert [s["key"] for s in p["forward"]["series"]] == ["list_pct", "rsp_pct", "spy_pct"]
    keys = [r["key"] for r in p["rules"]]
    assert keys[:8] == list(C.SCREENED_KEYS) and "pankaj" in keys
    assert {s["key"]: s["ok"] for s in p["as_of"]["sources"]} == {"scan": True, "fallen": False}


def test_caveats_keep_the_one_allowed_sentence():
    p = _ready()
    assert W.NOT_A_SIGNAL in p["caveats"]
    assert len(p["caveats"]) == len(SD.load()["caveats"])


def test_build_never_raises_on_garbage():
    p = P.build_payload(SD.load(), {"names": "garbage"}, [{"names": 5}], [None], {"TSM": "x"},
                        now=NOW_FRI, owner=True)
    assert p["state"] in ("ready", "error")


def test_golden_key_set():
    paths = sorted(key_paths(_ready()) | key_paths(_seed_only()))
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert golden["owner_only"] == sorted(P.owner_only_payload())
    assert golden["paths"] == paths


def test_next_run_date_rules():
    assert P.next_run_date(dt.datetime(2026, 11, 13, 16, 29)) == dt.date(2026, 11, 13)
    assert P.next_run_date(dt.datetime(2026, 11, 13, 16, 30)) == dt.date(2026, 11, 20)
    assert P.next_run_date(dt.datetime(2027, 3, 24, 12, 0)) == dt.date(2027, 3, 25)     # before Good Friday
    assert P.next_run_date(dt.datetime(2026, 11, 14, 12, 0)) == dt.date(2026, 11, 20)   # Saturday
    assert P.next_run_date(dt.datetime(2026, 11, 13, 10, 0), ran_this_week=True) == dt.date(2026, 11, 20)
