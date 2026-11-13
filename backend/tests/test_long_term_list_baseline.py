"""📅 Long Term — the AT-SAVE baseline fixture + its builder (WP-DATA, 2026-11-12).

Ajay 2026-11-12 ~21:00 ET: "Save this entire list for me. In a New tab - Long
Term - ... if something gets dropped let me know when to like is Sales drop or
Stage 2 to Stage 3 or stage 4 changes."

`long_term_list/data/baseline_2026_11_12.json` is generated ONCE by
`scripts/long_term_list_baseline_2026_11_12.py` from the 11-12 scratch dumps
(stage, close at save, sales, every leg, the 🧭 zone read, the initial flags).
Pins: strict JSON; all 109 saved names; spot facts (AMD Stage 2 strong, ANET 3,
NVDA 1, XPEL 1 with no scan row, SATL 1, BRK-B 2); 🧭 TSM in Agg, META in C1,
NVDA in C2; every screened seed name passes its own list's legs; the stored legs
are what `criteria.legs` says over the stored values; `last_stage2_on` is the
save date for exactly the Stage 2 names. The script is pure (no Mongo, no
network). When the scratch dumps exist, `--check` reproduces the seed: 7 lists
EXACT, 🏷️ differs only by the sector cap.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from long_term_list import constants as C
from long_term_list import criteria as CR
from long_term_list import notices as N
from long_term_list import seed as SEED

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "long_term_list_baseline_2026_11_12.py"
SCRATCH = Path("/private/tmp/claude-501/-Users-ajay-clinet-test/"
               "2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad")


def _refuse(x):
    raise ValueError(f"non-strict JSON constant {x}")


@pytest.fixture(scope="module")
def base():
    return json.loads(C.BASELINE_FILE.read_text(encoding="utf-8"), parse_constant=_refuse)


@pytest.fixture(scope="module")
def seed():
    return SEED.load()


def _script():
    spec = importlib.util.spec_from_file_location("lt_baseline_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_baseline_is_strict_json_and_loads_through_seed(base):
    got = SEED.load_baseline()
    assert "reason" not in got and got == base
    assert base["saved_on"] == C.SAVED_ON == "2026-11-12"
    assert set(base) == {"saved_on", "built_from", "names", "categories", "pankaj", "flags"}
    assert base["built_from"]["seed"]["sha256"] == C.SEED_SHA256


def test_all_109_saved_names(base, seed):
    names = SEED.unique_names(seed)
    assert len(names) == 109 and set(base["names"]) == set(names) == set(base["flags"])
    for s, n in base["names"].items():
        assert set(n) == {"stage", "stage_label", "stage_bar_date", "close_at_save",
                          "sales_tier", "sales_yoy_pct", "sales_q_end", "sales_read_on",
                          "sector", "name"}, s
        assert n["close_at_save"] is not None and n["stage"] in (1, 2, 3, 4), s


def test_spot_facts(base):
    n = base["names"]
    assert (n["AMD"]["stage"], n["AMD"]["sales_tier"]) == (2, "strong")
    assert n["ANET"]["stage"] == 3 and n["NVDA"]["stage"] == 1 and n["SATL"]["stage"] == 1
    assert n["BRK-B"]["stage"] == 2
    assert n["XPEL"]["stage"] == 1 and n["XPEL"]["name"] is None            # no scan row
    assert base["categories"]["quiet_strong"]["XPEL"]["values"]["net_debt_ebitda"] is None
    assert n["XPEL"]["sector"] == "Consumer Cyclical"                       # from the long-term row
    assert n["TSM"]["close_at_save"] == 405.49 and n["META"]["close_at_save"] == 623.61
    assert all(v["stage_bar_date"] == "2026-11-12" for v in n.values())


def test_pankaj_zone_reads_at_the_save_close(base):
    pk = base["pankaj"]
    assert len(pk) == 40
    assert pk["TSM"]["zone_read"]["in"] == ["Agg"]
    assert pk["META"]["zone_read"]["in"] == ["C1"]
    assert pk["NVDA"]["zone_read"]["in"] == ["C2"]
    intu = pk["INTU"]["zone_read"]
    assert intu["in"] == [] and intu["nearest"]["zone"] == "Agg" and intu["nearest"]["side"] == "over"
    assert round(intu["nearest"]["pct"], 1) == 23.7
    assert base["flags"]["TSM"]["zone_in"] == ["Agg"]
    for s, row in base["categories"]["pankaj"].items():
        assert "action" not in row["values"], s                             # §7 #22


def test_every_screened_seed_name_passes_its_own_list(base, seed):
    for cat in C.SCREENED_KEYS:
        names = [SEED.name_symbol(e) for e in SEED.category(seed, cat)["names"]]
        assert set(base["categories"][cat]) == set(names), cat
        for s in names:
            assert CR.qualifies(cat, base["categories"][cat][s]["values"]) is True, (cat, s)


def test_stored_legs_equal_criteria_over_the_stored_values(base):
    for cat, rows in base["categories"].items():
        for s, row in rows.items():
            want = [lg.to_dict() for lg in CR.legs(cat, row["values"])]
            got = row["legs"]
            assert [(d["key"], d["kind"], d["verdict"]) for d in got] == \
                   [(d["key"], d["kind"], d["verdict"]) for d in want], (cat, s)


def test_flags_last_stage2_on_exactly_for_the_stage_2_names(base):
    st2 = {s for s, n in base["names"].items() if n["stage"] == 2}
    assert st2
    for s, f in base["flags"].items():
        assert f == N.initial_flags(N.at_save(s, base)), s
        if s in st2:
            assert f["last_stage2_on"] == C.SAVED_ON, s
        else:
            assert f["last_stage2_on"] is None, s          # NEG: never set for Stage 1/3/4
        assert f["stage_drop_on"] is None and f["stage_drop_active"] is False


def test_NEG_the_baseline_script_is_pure():
    src = SCRIPT.read_text(encoding="utf-8")
    for bad in ("bulk_cached_frames", "load_prices", "load_latest", "_get_mongo", "MongoClient",
                "requests", "urlopen", "load_all("):
        assert bad not in src, bad
    assert "allow_nan=False" in src


def test_script_number_parser():
    m = _script()
    assert m._num("+48% · peers +19%") == 48.0 and m._num("−12%") == -12.0
    assert m._num("$27.6B · FY2026 Q4") == 27.6e9 and m._num("$822M · FY2026 Q2") == 822e6
    assert m._num("4.4x") == 4.4 and m._num(None) is None and m._num("—") is None


def test_check_table_marks_every_list_and_pankaj_is_not_a_screen():
    m = _script()
    rows = [{"cat": "s2_growth", "seed": ["A"], "pick_top": ["A"], "uncapped": ["A"],
             "n_qualify": 1, "verdict": "EXACT"},
            {"cat": "undervalue", "seed": ["A", "B"], "pick_top": ["A", "C"],
             "uncapped": ["A", "B"], "n_qualify": 3, "verdict": "differs only by the sector cap"}]
    t = m.check_table(rows)
    assert "| s2_growth | 1 | EXACT | A |" in t and "↳ seed" in t and "↳ uncapped" in t
    assert "| pankaj | — | n/a" in t


_DUMPS = {"seed": "longterm/saved_list_2026_11_12.json", "scan": "sepa1112/full.json",
          "sweep": "sc1112/sweep.json", "snap": "sc1112/snap.json", "lt": "sc1112/lt_rows.json",
          "hot": "hot1112/h.json", "fallen": "val1112/fallen2.json", "uvp": "val1112/uvp.json",
          "acc": "sc1112/acc_rows.json", "caps": "sc1112/acc_caps.json",
          "dec": "longterm/dec1112.json"}


@pytest.mark.skipif(not all((SCRATCH / p).exists() for p in _DUMPS.values()),
                    reason="the 2026-11-12 scratch dumps are not on this machine")
def test_reproduction_from_the_11_12_dumps(base):
    m = _script()
    seed = SEED.load(SCRATCH / _DUMPS["seed"])
    dumps = {k: m._load(SCRATCH / p) for k, p in _DUMPS.items() if k != "seed"}
    srcs = m.sources_from_dumps(dumps)
    rows = {r["cat"]: r for r in m.reproduction(seed, srcs)}
    exact = [c for c, r in rows.items() if r["verdict"] == "EXACT"]
    assert sorted(exact) == sorted(set(C.SCREENED_KEYS) - {"undervalue"})
    uv = rows["undervalue"]
    assert uv["verdict"] == "differs only by the sector cap" and uv["uncapped"] == uv["seed"]
    assert uv["pick_top"] == ["AVT", "ARW", "SMCI", "WKC", "BTSG", "CSTM", "CRBG", "CTRI",
                              "STC", "KALU"]
    assert rows["fallen_growers"]["n_qualify"] == 56 and rows["accel_after_fall"]["n_qualify"] == 46
    rebuilt = m.build_baseline(seed, srcs, base["built_from"])
    assert json.loads(json.dumps(rebuilt, allow_nan=False)) == base       # the committed file


# ---------------------------------------------------------------------------
# [C11] the sales text carries the quarter end + the read date in seed_only too
# (refix 2026-11-12: the first baseline had neither, so every 🌱 row read
# "Sales +56.5% y/y · tier strong" with no dates until the first Friday run)
# ---------------------------------------------------------------------------
def test_c11_baseline_names_carry_quarter_end_and_read_date(base):
    n = base["names"]
    assert (n["AMD"]["sales_q_end"], n["AMD"]["sales_read_on"]) == ("2026-09-26", "2026-11-08")
    with_q = [s for s, v in n.items() if v["sales_q_end"]]
    assert len(with_q) == 107 and all(v["sales_read_on"] == "2026-11-08" for v in n.values())
    for s in ("BRK-B", "TSM"):                     # NEG: no q_end_series in the cache -> None, never invented
        assert n[s]["sales_q_end"] is None, s
    assert base["built_from"]["dec"]["file"] == "dec1112.json"


def test_c11_seed_only_rows_print_quarter_end_and_read_date(base):
    import datetime as dt
    from long_term_list import payload as P
    p = P.build_payload(SEED.load(), base, [], [], {}, now=dt.datetime(2026, 11, 12, 22, 0), owner=True)
    assert p["state"] == "seed_only"
    rows = {r["symbol"]: r for c in p["categories"] for r in c["rows"]}
    rows.update({r["symbol"]: r for r in p.get("changed") or []})
    assert len(rows) == 109
    assert rows["AMD"]["sales"]["text"] == \
        "Sales +44.7% y/y · tier strong · quarter ended 2026-09-26 · read 2026-11-08"
    quiet = next(c for c in p["categories"] if c["key"] == "quiet_strong")
    for r in quiet["rows"]:
        assert " · quarter ended 20" in r["sales"]["text"] and r["sales"]["text"].endswith(
            " · read 2026-11-08"), r["symbol"]
    tsm = rows["TSM"]["sales"]["text"]             # NEG: missing quarter end dropped, read date kept
    assert "quarter ended" not in tsm and tsm.endswith("read 2026-11-08")


def test_c11_research_dates_only_from_the_same_read():
    m = _script()
    snap = {"AAA": {"sales": {"tier": "strong", "growth_yoy_pct": 40.0}},
            "BBB": {"sales": {"tier": "strong", "growth_yoy_pct": 30.0}},
            "CCC": {"sales": None}}
    dec = {"rows": {"AAA": {"sales": {"tier": "strong", "growth_yoy_pct": 40.0},
                            "q_end_series": ["2026-09-30"], "cached_at": 1794186004},
                    "BBB": {"sales": {"tier": "strong", "growth_yoy_pct": 31.0},     # a newer read
                            "q_end_series": ["2026-09-30"], "cached_at": 1794186004},
                    "CCC": {"sales": None, "q_end_series": ["2026-09-30"], "cached_at": 1},
                    "DDD": {"sales": {"tier": "steady"}, "q_end_series": ["2026-06-30"], "cached_at": 1},
                    "EEE": "garbage"}}
    got = m.research_dates(snap, dec)
    assert got == {"AAA": {"q_end_series": ["2026-09-30"], "cached_at": 1794186004}}
    assert m.research_dates(snap, None) == {} and m.research_dates(snap, {"rows": None}) == {}
    assert m.research_dates(snap, ["x"]) == {}


def test_c11_NEG_no_dec_dump_leaves_the_dates_none():
    m = _script()
    d = {"scan": {"all_results": [], "candidates": []}, "sweep": [], "lt": {}, "hot": {"sectors": []},
         "fallen": {"tiles": []}, "uvp": {"tiles": []}, "acc": [], "caps": {},
         "snap": {"AAA": {"sales": {"tier": "strong", "growth_yoy_pct": 40.0}}}}
    srcs = m.sources_from_dumps(d)
    assert srcs["research"]["rows"]["AAA"] == {"sales": {"tier": "strong", "growth_yoy_pct": 40.0}}
    from long_term_list import facts as F
    sf = F.sales_facts(srcs["research"]["rows"]["AAA"])
    assert sf["sales_q_end"] is None and sf["sales_read_on"] is None
    d["dec"] = {"rows": {"AAA": {"sales": {"tier": "strong", "growth_yoy_pct": 40.0},
                                 "q_end_series": ["2026-09-30", "2026-06-30"], "cached_at": 1794186004}}}
    sf = F.sales_facts(m.sources_from_dumps(d)["research"]["rows"]["AAA"])
    assert (sf["sales_q_end"], sf["sales_read_on"]) == ("2026-09-30", "2026-11-08")
