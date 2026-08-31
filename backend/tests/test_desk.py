"""Desk daily report (desk/scoring.py + desk/report.py pure parts).

Ajay 2026-08-28: "Add a cron or daily routine use our data to do the
analysis" through his pasted momentum-trader persona. The persona writes
prose; these tests lock the NUMBERS — a wrong verdict throttles his size,
a wrong R multiple sizes a real position, and a false disqualifier hides
a setup. Negative cases are the point (his Rule #6).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desk import report as R  # noqa: E402
from desk import scoring as S  # noqa: E402


def _row(**over):
    """A clean, fully-tradable scan row; tests break one thing at a time."""
    base = {
        "symbol": "TENB", "last_close": 37.67, "rs_rank": 89,
        "ext_from_pivot_pct": -5.9, "is_in_buy_zone": True,
        "day_change_pct": 1.2, "is_buyable": True, "is_candidate": True,
        "setup_ready": True,
        "climax_distribution": {"is_distribution": False, "in_climax": False,
                                "severity": 3},
        "sell_signals": {"signals": {"close_below_50ma_on_high_vol": False}},
        "stage": {"stage": 2}, "industry": "Software", "pioneer_themes": [],
        "trend": {"pass_all": True},
        "vcp": {"has_base": True, "n_contractions": 3,
                "monotonic_shrinkage": True},
        "volume": {"accumulation": True, "up_down_vol_ratio": 2.2},
        "liquidity": {"liquid": True, "avg_dollar_vol": 115e6},
        "fundamentals": {"q_eps_growth_pct": 125.0,
                         "sales": {"tier": "strong", "accelerating": True},
                         "earnings_quality": {"tier": "accelerating"}},
        "trade_plan": {"entry_recommended": 38.0,
                       "stop": {"recommended": 36.0, "risk_pct": 5.3}},
    }
    base.update(over)
    return base


# ── regime verdict: maps, downgrades, never upgrades ────────────────────────
def test_regime_labels_map_to_the_three_verdicts():
    assert S.regime_verdict({"label": "confirmed_uptrend"})["verdict"] == "RISK_ON"
    assert S.regime_verdict({"label": "pressure"})["verdict"] == "MIXED"
    assert S.regime_verdict({"label": "correction"})["verdict"] == "RISK_OFF"
    assert S.regime_verdict(None)["verdict"] == "MIXED", \
        "unknown regime must not default to full size"


def test_distribution_and_vix_downgrade_one_notch_each_never_upgrade():
    comp = {"distribution": {"count": 7}, "stress": {"vix": 12.0}}
    v = S.regime_verdict({"label": "confirmed_uptrend", "components": comp})
    assert v["verdict"] == "MIXED"
    comp2 = {"distribution": {"count": 7}, "stress": {"vix": 34.0}}
    v2 = S.regime_verdict({"label": "confirmed_uptrend", "components": comp2})
    assert v2["verdict"] == "RISK_OFF", "both flags stack to two notches"
    calm = {"distribution": {"count": 0}, "stress": {"vix": 11.0}}
    v3 = S.regime_verdict({"label": "correction", "components": calm})
    assert v3["verdict"] == "RISK_OFF", "a calm VIX never upgrades a correction"


def test_regime_components_list_form_is_read():
    comp = [{"key": "distribution", "count": 8}, {"key": "stress", "vix": 15}]
    v = S.regime_verdict({"label": "confirmed_uptrend", "components": comp})
    assert v["verdict"] == "MIXED"


def test_throttle_caps_are_the_personas():
    assert S.THROTTLE["RISK_ON"]["max_ideas"] == 5
    assert S.THROTTLE["MIXED"] == {**S.THROTTLE["MIXED"], "max_ideas": 3,
                                   "size_factor": 0.5}
    assert S.THROTTLE["RISK_OFF"]["max_ideas"] == 1


# ── disqualifiers: each cut fires alone; absence of data is not a signal ────
def test_each_disqualifier_fires_with_its_reason():
    assert any("price" in r for r in S.disqualify(_row(last_close=1.50)))
    assert any("dollar volume" in r for r in S.disqualify(
        _row(liquidity={"avg_dollar_vol": 2e6})))
    assert any("earnings" in r for r in S.disqualify(_row(), earnings_in_days=3))
    assert any("extended" in r for r in S.disqualify(
        _row(ext_from_pivot_pct=14.0)))
    assert any("knife" in r for r in S.disqualify(
        _row(fundamentals={"sales": {"tier": "declining"}})))
    assert any("climax" in r for r in S.disqualify(
        _row(climax_distribution={"is_distribution": True, "in_climax": False})))
    assert any("climax" in r for r in S.disqualify(
        _row(climax_distribution={"is_distribution": False, "in_climax": True})))
    assert any("sell signals" in r for r in S.disqualify(
        _row(sell_signals={"signals": {"a": True, "b": True, "c": False}})))


def test_clean_row_passes_and_soft_absences_do_not_cut():
    assert S.disqualify(_row()) == []
    assert S.disqualify(_row(), earnings_in_days=20) == [], \
        "earnings outside the window is not a cut"
    assert S.disqualify(_row(fundamentals={})) == [], \
        "un-enriched rows (no sales tier) must not be cut for missing data"
    assert S.disqualify(_row(sell_signals={"signals": {"a": True}})) == [], \
        "a single sell signal is a note, not a cut"
    assert S.disqualify(_row()) == [], \
        "a BENIGN climax dict (all flags False) must never cut — the block " \
        "is present on every scanned row"
    cut = S.disqualify(_row(liquidity={}))
    assert any("dollar volume" in r for r in cut), \
        "UNKNOWN liquidity IS a cut — trading blind on size kills accounts"


# ── R multiple and sizing: honest math or nothing ───────────────────────────
def test_rr_multiple_refuses_nonsense_geometry():
    assert S.rr_multiple(100, 95, 115) == pytest.approx(3.0)
    assert S.rr_multiple(100, 105, 115) is None      # stop above entry
    assert S.rr_multiple(100, 95, 90) is None        # target below entry
    assert S.rr_multiple(None, 95, 115) is None
    assert S.rr_multiple("x", 95, 115) is None


def test_position_size_is_off_the_stop_never_off_conviction():
    s = S.position_size(60_000, 38.0, 36.0, size_factor=1.0, risk_pct=0.75)
    assert s["shares"] == int(60_000 * 0.0075 / 2.0)
    assert s["risk_dollars"] <= 60_000 * 0.0075
    half = S.position_size(60_000, 38.0, 36.0, size_factor=0.5, risk_pct=0.75)
    assert half["shares"] == s["shares"] // 2
    assert S.position_size(None, 38.0, 36.0) is None
    assert S.position_size(60_000, 38.0, 38.0) is None, \
        "zero stop distance is an infinite position — refuse"
    assert S.position_size(60_000, 38.0, 40.0) is None


# ── component scoring ───────────────────────────────────────────────────────
def test_score_row_ships_subscores_and_respects_weights():
    s = S.score_row(_row())
    assert set(s["parts"]) == {"catalyst", "technical", "asymmetry",
                               "liquidity", "crowding"}
    assert s["parts"]["catalyst"] <= 25 and s["parts"]["technical"] <= 25
    assert s["parts"]["asymmetry"] <= 20
    assert s["parts"]["liquidity"] <= 15 and s["parts"]["crowding"] <= 15
    assert s["total"] == pytest.approx(sum(s["parts"].values()), abs=0.1)
    assert s["plan"]["rr"] == pytest.approx((38 * 1.20 - 38) / 2.0, abs=0.01)


def test_no_trade_plan_means_no_asymmetry_and_no_plan():
    s = S.score_row(_row(trade_plan={}))
    assert s["parts"]["asymmetry"] == 0.0 and s["plan"] is None


def test_extension_and_megacap_pay_crowding_penalties():
    hot = S.score_row(_row(ext_from_pivot_pct=7.0, day_change_pct=9.0,
                           liquidity={"avg_dollar_vol": 2e9}))
    calm = S.score_row(_row())
    assert hot["parts"]["crowding"] < calm["parts"]["crowding"]


# ── module B assembly (pure given rows + earnings map) ──────────────────────
def test_swing_candidates_score_cut_and_sort():
    rows = [_row(symbol="GOOD"),
            _row(symbol="EARN"),
            _row(symbol="THIN", liquidity={"avg_dollar_vol": 1e6}),
            _row(symbol="NOTSETUP", is_buyable=False, is_candidate=False),
            _row(symbol="NOPLAN", trade_plan={})]
    scored, cuts = R._swing_candidates(rows, {"EARN": {"days_to": 2}})
    assert [c["symbol"] for c in scored] == ["GOOD"]
    cut_syms = {c["symbol"] for c in cuts}
    assert cut_syms == {"EARN", "THIN", "NOPLAN"}, \
        "NOTSETUP is skipped silently — it was never a candidate"
    assert scored[0]["time_stop"] == R.SWING_TIME_STOP


# ── carried forward: the journal loop, deterministic ────────────────────────
def _bars(rows):
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({"open": [r[1] for r in rows],
                         "high": [r[2] for r in rows],
                         "low": [r[3] for r in rows],
                         "close": [r[4] for r in rows]}, index=idx)


def test_grade_prior_book_walks_trigger_stop_target(monkeypatch):
    from sepa import prices as prices_mod
    frames = {
        "TRIG": _bars([("2026-08-27", 37, 39, 36.5, 38.5),
                       ("2026-08-28", 38, 40, 37.5, 39.0)]),
        "STOPD": _bars([("2026-08-27", 38, 39, 35.0, 35.5)]),
        "TGT": _bars([("2026-08-27", 38, 46.0, 37.6, 45.9)]),
        "SLEEP": _bars([("2026-08-27", 30, 31.0, 29.5, 30.5)]),
    }
    monkeypatch.setattr(prices_mod, "load_prices",
                        lambda sym, **kw: frames.get(sym))
    plan = {"entry": 38.0, "stop": 36.0, "target1": 45.6}
    prior = {"date": "2026-08-26", "book": [
        {"symbol": "TRIG", "module": "B", "plan": plan},
        {"symbol": "STOPD", "module": "B", "plan": plan},
        {"symbol": "TGT", "module": "B", "plan": plan},
        {"symbol": "SLEEP", "module": "B", "plan": plan},
        {"symbol": "GONE", "module": "B", "plan": plan}]}
    by = {g["symbol"]: g["status"] for g in R.grade_prior_book(prior)}
    assert by == {"TRIG": "open", "STOPD": "stopped", "TGT": "target1_hit",
                  "SLEEP": "not_triggered", "GONE": "no_data"}


def test_grade_prior_book_empty_inputs():
    assert R.grade_prior_book(None) == []
    assert R.grade_prior_book({"date": "2026-08-27", "book": []}) == []


# ── LLM prose: report never blocks on the model ─────────────────────────────
def test_prose_falls_back_deterministic_when_llm_disabled(monkeypatch):
    import types
    fake = types.SimpleNamespace(is_enabled=lambda: False, chat=None)
    monkeypatch.setitem(sys.modules, "llm", fake)
    payload = {"regime": {"verdict": "MIXED", "drivers": ["a", "b"]},
               "book": [{"symbol": "TENB", "module": "B", "score": 80,
                         "parts": {}, "plan": {"entry": 38, "stop": 36,
                                               "target1": 45.6, "rr": 3.8}}]}
    p = R._prose(payload)
    assert p["provider"] == "deterministic"
    assert "TENB" in p["cards"] and "38" in p["cards"]["TENB"]
    assert p["regime_lines"][0].startswith("Regime MIXED")


# ── delivery discipline ─────────────────────────────────────────────────────
def test_push_kind_is_todo_reminder_no_new_kinds():
    """Standing rule (2026-06-24): the keep-set gains no new kinds — a
    scheduled morning report is exactly what todo_reminder means."""
    import inspect
    src = inspect.getsource(R)
    assert 'kind="todo_reminder"' in src
    assert "desk_alert" not in src and 'kind="desk' not in src


def test_report_min_bar_is_seventy():
    assert S.REPORT_MIN == 70.0, \
        "the persona reports only names scoring >= 70"


# ── cash in the sizing denominator (2026-08-31) ────────────────────────────
def _stub_portfolio(monkeypatch, holdings, cash, quotes):
    """Stub the portfolio package in sys.modules. The real package __init__
    imports its FastAPI router, whose `str | None` annotations cannot even be
    IMPORTED on the py3.9 test venv (Rule #6 quirk) — prod runs 3.11. The stub
    also stands in for knife_watch, which _account degrades behind try/except."""
    import sys
    import types

    pkg = types.ModuleType("portfolio")
    store = types.ModuleType("portfolio.store")
    store.list_holdings = lambda o: holdings
    store.get_cash = lambda o: cash
    qmod = types.ModuleType("portfolio.quotes")
    qmod.fetch_quotes = lambda ts: quotes
    pkg.store, pkg.quotes = store, qmod
    for name, mod in (("portfolio", pkg), ("portfolio.store", store),
                      ("portfolio.quotes", qmod)):
        monkeypatch.setitem(sys.modules, name, mod)


def test_account_value_is_cash_plus_positions(monkeypatch):
    """Ajay went ~86% cash after the Friday selloff ($107k account, ~$15k in
    two names). The holdings-only value would size every idea off a seventh
    of the real account — 0.75% risk of $15k is a $112 stop budget on a $107k
    book."""
    from desk import report as R

    _stub_portfolio(monkeypatch,
                    holdings=[{"ticker": "VRSK", "shares": 51.444},
                              {"ticker": "ACN", "shares": 26.242}],
                    cash=92072.63,
                    quotes={"VRSK": {"last": 194.0}, "ACN": {"last": 190.0}})
    out = R._account("ajaykandakatla@gmail.com")
    positions = 51.444 * 194.0 + 26.242 * 190.0
    assert out["cash"] == 92072.63
    assert out["positions_value"] == round(positions, 2)
    assert out["value"] == round(positions + 92072.63, 2)


def test_untracked_cash_falls_back_to_positions_and_says_so(monkeypatch):
    """None = not tracked, which must not read as $0 of cash. The value falls
    back to positions alone and `cash` stays None so the report can name the
    denominator it used."""
    from desk import report as R

    _stub_portfolio(monkeypatch,
                    holdings=[{"ticker": "ACN", "shares": 10.0}],
                    cash=None,
                    quotes={"ACN": {"last": 190.0}})
    out = R._account("ajaykandakatla@gmail.com")
    assert out["cash"] is None
    assert out["value"] == 1900.0
