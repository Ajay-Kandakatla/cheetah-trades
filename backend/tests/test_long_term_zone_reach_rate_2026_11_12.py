"""📅 Long Term 🔔 — the reach-rate script counts what the push rule would ring (pkzone spec §1.6, critique C3).

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones …". The script is a measurement, read
only: ONE cache find, no provider call, no Mongo write, no push. NEGATIVES: a prior close inside never counts; a None
edge is skipped; the pad is the constant (monkeypatched → the count moves); the AST never names a fetch / write / send.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd

from long_term_list import constants as C
from long_term_list import criteria as CR
from scripts import long_term_zone_reach_rate as RR

SCRIPT = Path(RR.__file__)
ZONES = {"Agg": (400.0, 410.0), "C1": (360.0, 375.0), "C3": (None, None)}


def frame(rows, start="2026-11-02"):
    idx = pd.bdate_range(start, periods=len(rows))
    return pd.DataFrame([{"open": c, "high": h, "low": lo, "close": c, "volume": 1} for c, h, lo in rows], index=idx)


def test_prior_outside_and_the_range_touching_counts_range_only():
    df = frame([(430.0, 431, 429), (420.0, 425, 409.0)])
    rng, cls, seen = RR.count_frame(df, ZONES, C.PANKAJ_ZONE_PAD_PCT, 60)
    assert sum(rng.values()) == 1 and sum(cls.values()) == 0 and len(seen) == 1


def test_close_inside_counts_both():
    df = frame([(430.0, 431, 429), (405.0, 425, 404.0)])
    rng, cls, _ = RR.count_frame(df, ZONES, C.PANKAJ_ZONE_PAD_PCT, 60)
    assert sum(rng.values()) == 1 and sum(cls.values()) == 1


def test_NEGATIVE_prior_close_inside_never_counts():
    df = frame([(405.0, 406, 404), (406.0, 407, 403.0)])
    rng, cls, _ = RR.count_frame(df, ZONES, C.PANKAJ_ZONE_PAD_PCT, 60)
    assert sum(rng.values()) == 0 and sum(cls.values()) == 0


def test_NEGATIVE_a_none_edge_is_skipped():
    assert [z for z, _, _ in RR.bands(ZONES, 0.5)] == ["Agg", "C1"]
    assert RR.bands({"Agg": (410.0, 400.0)}, 0.5) == []                  # lo > hi skipped too


def test_the_pad_is_the_constant(monkeypatch):
    df = frame([(430.0, 431, 429), (411.5, 412, 411.5)])                  # 0.37% over the 410 top
    entries = {"TSM": {"zones": ZONES}}
    base = RR.compute(entries, {"TSM": df}, sessions=60, boot=200, seed=7)
    assert base["rows"]["close"]["mean"] == 1.0 and base["pad_pct"] == C.PANKAJ_ZONE_PAD_PCT
    monkeypatch.setattr(C, "PANKAJ_ZONE_PAD_PCT", 0.1)
    moved = RR.compute(entries, {"TSM": df}, sessions=60, boot=200, seed=7)
    assert moved["rows"]["close"]["mean"] == 0.0                          # NEG: the number is never typed


def test_band_membership_equals_the_one_zone_engine():
    for px in (397.9, 398.0, 400.0, 405.0, 410.0, 412.05, 412.1, 359.0, 377.0):
        in_band = [z for z, a, b in RR.bands(ZONES, C.PANKAJ_ZONE_PAD_PCT) if a <= px <= b]
        assert in_band == CR.zone_read(ZONES, px, "d", ("Agg", "C1", "C3"))["in"], px


def test_output_carries_every_field(tmp_path, monkeypatch):
    rows = [(430.0, 431, 429), (405.0, 425, 404), (430.0, 431, 429), (420.0, 425, 409), (430.0, 431, 429)]
    out = RR.compute({"TSM": {"zones": ZONES}, "XYZ": {"zones": {}}}, {"TSM": frame(rows)}, sessions=60, boot=500,
                     seed=7)
    for k in ("mean", "ci_lo", "ci_hi", "per_week", "per_week_lo", "per_week_hi", "max_day", "zero_days"):
        assert k in out["rows"]["close"] and k in out["rows"]["day_range"]
    assert out["sessions"] == {"n": 4, "first": "2026-11-03", "last": "2026-11-06"}
    assert out["n_names"] == 2 and out["n_names_with_frames"] == 1 and out["n_zones"] == 2
    assert out["rows"]["day_range"]["mean"] == 0.5 and out["rows"]["day_range"]["zero_days"] == 2
    assert out["rows"]["day_range"]["per_week"] == RR.DAYS_PER_WEEK * 0.5
    assert out["top_names"] == [["TSM", 2]] and "hindsight" in out["caveat"] and "no placebo" in out["caveat"]
    assert "| close inside (lower bound) |" in RR.table(out)
    from long_term_list import seed as SD
    from sepa import prices
    calls = []
    monkeypatch.setattr(SD, "pankaj_entries", lambda seed: {"TSM": {"zones": ZONES}})
    monkeypatch.setattr(prices, "bulk_cached_frames", lambda syms: calls.append(list(syms)) or {"TSM": frame(rows)})
    assert RR.main(["--boot", "100", "--out", str(tmp_path)]) == 0
    assert calls == [["TSM"]]                                             # ONE cache find
    assert json.loads((tmp_path / "reach_rate.json").read_text())["rows"]["close"]["mean"] == 0.25


def test_NEGATIVE_the_script_never_fetches_writes_or_sends():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    for bad in ("bulk_snapshot", "load_prices", "send_to_user", "send_to_all", "insert_one", "update_one"):
        assert bad not in names, bad
    assert "bulk_cached_frames" in names
