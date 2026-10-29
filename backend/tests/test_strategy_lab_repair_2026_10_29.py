"""Strategy lab 2026-10-29 REPAIR (audit defects 1-4) — synthetic bars only, Mongo-free.

1  a changed prereg is refused (rc 2) BEFORE any bar or OOS read; nothing written, ledger unchanged.
2  --ledger must equal LEDGER_PATH and its directory must exist; nothing is ever mkdir-ed.
3  a >= 5x jump inside a hold is KEPT and flagged; A prints with and without the flagged rows.
4  each unmeasurable candidate carries its own status.json fact.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from scripts import strategy_lab_2026_10_29 as L
from sepa import prices
from tests.test_strategy_lab_2026_10_29 import (FUND_KW, NIGHT, _boom, _iid_panel, _known_panel,
                                                _rc, _universe_frames, no_key,  # noqa: F401
                                                restore_guards)  # noqa: F401


def _mongo(monkeypatch):
    from chart_maps.gajjala import scanner
    monkeypatch.setattr(scanner, "fetch_type_map", _boom)
    monkeypatch.setattr(scanner, "ensure_type_map", _boom)
    fr, days = _universe_frames(n_names=40, T=260, seed=21)
    pairs = [[s, "CS"] for s in fr if s != "SPY"]

    class _State:
        def find_one(self, q):
            return {"_id": "types", "as_of": days[-1], "complete": True, "pairs": pairs}

    class _Db(dict):
        def __getitem__(self, k):
            return _State()

    class _Coll:
        name = "price_cache"
        database = _Db()

        def distinct(self, key):
            return list(fr)
    monkeypatch.setattr(prices, "_get_mongo", lambda: _Coll())
    kw = dict(frames_fn=lambda ss: {s: fr[s] for s in ss if s in fr}, fund_kw=FUND_KW,
              calib_reps=2, now=NIGHT)
    oos = L.split_sessions(L.signal_sessions(260), days, None)["oos_from"]
    return kw, oos


def _outcome_argv(oos, pre, led, out):
    return ["--candidate", "c5_reversal", "--oos-from", oos, "--prereg", str(pre),
            "--prereg-commit", "abcdef1234567", "--ledger", str(led), "--out", str(out),
            "--draws", "200", "--placebo-sets", "30"]


# ---------------------------------------------------------------------------
# 1 changed prereg -> refused before any read
# ---------------------------------------------------------------------------
def test_R1_NEG_changed_prereg_is_refused_before_any_read(tmp_path, monkeypatch, no_key):
    led = tmp_path / "ledger.json"
    old = [{"trial_id": "T01", "prereg_sha256": "old", "as_of": "x", "sr_per_entry_day": 0.1}]
    led.write_text(json.dumps(old))
    monkeypatch.setattr(L, "LEDGER_PATH", str(led))
    pre = tmp_path / "prereg.md"
    pre.write_text("# edited prereg\n")
    out = tmp_path / "out"
    rc = _rc(_outcome_argv("2026-03-20", pre, led, out))
    assert rc == 2
    assert not out.exists()
    assert json.loads(led.read_text()) == old


def test_R1b_same_sha_runs_and_replaces_and_another_trial_is_no_clash(tmp_path, monkeypatch,
                                                                       no_key, restore_guards):
    kw, oos = _mongo(monkeypatch)
    pre = tmp_path / "prereg.md"
    pre.write_text("# prereg\n")
    sha = L.prereg_sha256(pre)
    led = tmp_path / "ledger.json"
    led.write_text(json.dumps([{"trial_id": "T00", "prereg_sha256": "other", "as_of": "y",
                                "sr_per_entry_day": 0.05}]))
    monkeypatch.setattr(L, "LEDGER_PATH", str(led))
    out = tmp_path / "o"
    assert L.main(_outcome_argv(oos, pre, led, out), block=False, **kw) == 0
    assert L.main(_outcome_argv(oos, pre, led, out), block=False, **kw) == 0
    rows = json.loads(led.read_text())
    assert [r["trial_id"] for r in rows] == ["T00", "T01"] and rows[1]["prereg_sha256"] == sha
    st = json.loads((out / "stats.json").read_text())
    assert st["oos"]["C"]["N"] == 2


def test_R1c_ledger_conflict_is_the_one_check_append_uses(tmp_path):
    rows = [{"trial_id": "T01", "prereg_sha256": "a"}]
    assert L.ledger_conflict(rows, "T01", "a") is None
    assert L.ledger_conflict(rows, "T02", "b") is None
    assert L.ledger_conflict([], "T01", "b") is None
    msg = L.ledger_conflict(rows, "T01", "b")
    assert msg and "different prereg sha256" in msg
    led = tmp_path / "l.json"
    led.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="different prereg sha256"):
        L.ledger_append(led, {"trial_id": "T01", "prereg_sha256": "b", "as_of": "z"})
    assert json.loads(led.read_text()) == rows


# ---------------------------------------------------------------------------
# 2 ledger path + no mkdir
# ---------------------------------------------------------------------------
def test_R2_NEG_only_the_mounted_research_ledger_is_accepted(tmp_path, monkeypatch):
    assert L.LEDGER_PATH == "/research/strategy_lab_ledger.json"
    assert f"--ledger {L.LEDGER_PATH}" in L.RUN_OUTCOME
    monkeypatch.setattr(L, "REFUSED_LEDGER_ROOTS", ())
    for bad in ("/strat/out/ledger.json", "/tmp/strategy_lab_ledger.json",
                "/research/other.json", "research/strategy_lab_ledger.json",
                str(tmp_path / "strategy_lab_ledger.json")):
        assert L.ledger_refusal(bad), bad
        assert L._ledger_refused(bad), bad
    good = tmp_path / "strategy_lab_ledger.json"
    monkeypatch.setattr(L, "LEDGER_PATH", str(good))
    assert L.ledger_refusal(str(good)) is None
    monkeypatch.setattr(L, "REFUSED_LEDGER_ROOTS", (str(tmp_path.resolve()),))
    assert "not durable" in L.ledger_refusal(str(good))


def test_R2b_NEG_missing_mount_is_refused_and_never_created(tmp_path, monkeypatch, no_key):
    led = tmp_path / "research_not_mounted" / "strategy_lab_ledger.json"
    monkeypatch.setattr(L, "LEDGER_PATH", str(led))
    assert "does not exist" in L.ledger_refusal(str(led))
    pre = tmp_path / "prereg.md"
    pre.write_text("# prereg\n")
    out = tmp_path / "o"
    assert _rc(_outcome_argv("2026-03-20", pre, led, out)) == 2
    assert not led.parent.exists() and not out.exists()
    with pytest.raises(FileNotFoundError):
        L.ledger_append(led, {"trial_id": "T01", "prereg_sha256": "a", "as_of": "z"})
    assert not led.parent.exists()


# ---------------------------------------------------------------------------
# 3 scale-glitch hold rows kept + flagged
# ---------------------------------------------------------------------------
def test_R3_a_crash_inside_the_hold_is_kept_and_flagged():
    p, t0 = _known_panel()
    for c in ("open", "close"):
        p[c][18, t0 + 3:] = 15.0
    p["open"][18, t0 + 1] = 100.0
    p["high"] = np.fmax(p["open"], p["close"]) * 1.01
    p["low"] = np.fmin(p["open"], p["close"]) * 0.99
    liq = L.liquidity_panel(p)
    o = L.trade_outcome(p, 18, t0, int(liq["rank"][18, t0]))
    assert "skip_reason" not in o and o["glitch_hold"] is True
    c = L.cost_side(int(liq["rank"][18, t0]))
    assert o["net_ret"] == pytest.approx(15.0 * (1 - c) / (100.0 * (1 + c)) - 1, abs=1e-12)
    co, tr = L.c5_rows(p, liq, {"oos": [t0]})
    pa = tr[tr["sym"] == "PA"]
    assert len(pa) == 1 and bool(pa["glitch_hold"].iloc[0])
    assert "PA" in set(co["sym"])
    assert co.attrs["flags"]["oos"]["scale_glitch_hold"] == 1
    assert "scale_glitch_hold" not in co.attrs["skips"]["oos"]


def test_R3b_NEG_gate_A_keeps_the_flagged_rows_and_the_without_line_drops_them():
    p = _iid_panel(33, N=200, T=217)
    liq = L.liquidity_panel(p)
    sess = list(range(60, 140))
    t_mid = 100
    s_hit = L.c5_select(p, liq, t_mid)[0]
    p.pop("_aux", None)
    for c in ("open", "close", "high", "low"):
        p[c][s_hit, t_mid + 3:] = p[c][s_hit, t_mid + 3:] / 10.0
    liq = L.liquidity_panel(p)
    assert s_hit in L.c5_select(p, liq, t_mid)
    co, tr = L.c5_rows(p, liq, {"oos": sess})
    flagged = tr["glitch_hold"].astype(bool)
    assert flagged.sum() >= 1
    assert co["glitch_hold"].sum() >= flagged.sum()
    g = L.gate_block(tr, co, draws=500, placebo_sets=30, seed=5, trial_srs_others=[])
    rep = g["reported"]
    assert rep["n_scale_glitch_hold"] == int(flagged.sum())
    want_all = round(float(tr["net_ret"].mean()) * 100, L.SHOW_DP)
    want_wo = round(float(tr.loc[~flagged, "net_ret"].mean()) * 100, L.SHOW_DP)
    assert g["A"]["mean_pct"] == pytest.approx(want_all, abs=1e-9)
    assert rep["A_without_scale_glitch_hold"]["mean_pct"] == pytest.approx(want_wo, abs=1e-9)
    assert rep["A_without_scale_glitch_hold"]["n"] == len(tr) - int(flagged.sum())
    assert g["A"]["n"] == len(tr)
    assert want_all < want_wo


# ---------------------------------------------------------------------------
# 4 per-candidate fact
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cand,fact", [("c1_ath_atr10", L.ROLLING_CACHE_FACT),
                                       ("c2_xsmom_12_1", L.ROLLING_CACHE_FACT),
                                       ("c3_ear_drift", L.EARNINGS_DATES_FACT),
                                       ("c4_spy_sma10m", L.ROLLING_CACHE_FACT)])
def test_R4_each_unmeasurable_candidate_states_its_own_fact(tmp_path, cand, fact, no_key):
    assert _rc(["--candidate", cand, "--out", str(tmp_path / cand)]) == 3
    st = json.loads((tmp_path / cand / "status.json").read_text())
    assert st["fact"] == fact == L.CANDIDATES[cand]["fact"]


def test_R4b_NEG_c3_fact_is_not_the_rolling_window():
    f = L.CANDIDATES["c3_ear_drift"]["fact"]
    assert "rolling 2-year" not in f and "BMO/AMC" in f and "last_report" in f
    assert not hasattr(L, "UNMEASURABLE_FACT")
    assert all(L.CANDIDATES[k].get("fact") for k in L.UNMEASURED_NAMES)
