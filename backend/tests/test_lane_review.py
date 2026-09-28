"""The daily loss review + Confirm/Dismiss cards (trading/lane_review.py).

Ajay 2026-09-27: "analayze losses everyday with a routine or something and
restategize and confirm with me" — no auto-pause.

Pins (hermetic: MiniDB, faked journal/broker reads):
  * the numbers: Wilson interval in percent, a SEEDED bootstrap (same input,
    same interval), n < 2 -> no interval;
  * a closed day writes nothing; the review NEVER writes trading_config and
    never applies a proposal — only his Confirm does, and only config keys; a
    code-level Confirm is a TODO that changes nothing; both are ledgered;
    a decided card cannot be decided twice;
  * a pause is proposed only at n >= 20 with the whole expectancy CI below
    zero; a loss class needs 3; a dismissed card returns only on more evidence;
    demand_residents is not proposed when it is already strict;
  * the loser line reads the entry snapshot (cm_lane_entries) and never says
    the other word; 0DTE R = pnl / (fill x 100 x qty x premium stop);
  * broker fills resolve BEFORE the journal reconcile, are paged past 500,
    and an unreadable broker says "approximate" instead of failing;
  * a SEPA-sell (distribution) close is counted; an unpriced close is counted
    in n_unpriced and kept out of expectancy;
  * the four API routes.
"""
import asyncio
import json
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE  # noqa: E402
import trading.journal as JN  # noqa: E402
import trading.lane_review as LR  # noqa: E402
import trading.program_caps as PC  # noqa: E402
from tests.test_program_caps import ET, MiniDB, et  # noqa: E402

NOW = et(17, 5)                                   # Monday 2026-09-28, after the close
DAY = "2026-09-28"


class FillsBroker:
    def __init__(self, pages=None, raises=None):
        self.pages = list(pages or [[]])
        self.raises = raises
        self.calls = []

    def mode(self):
        return "paper"

    def closed_orders_since(self, iso):
        self.calls.append(iso)
        if self.raises:
            raise self.raises
        return self.pages.pop(0) if self.pages else []


def jdoc(sym, sid, pnl, *, i=0, day=DAY, leg="stop", kind=None, priced=True, approx=False,
         ref=None, reason=None):
    """A closed journal doc: 100 sh @ 10.00, stop 9.50 -> 1R = $50."""
    return {"trade_id": "%s-%d" % (sym, i), "symbol": sym, "status": "closed",
            "entry": {"strategy": sid, "ts": "%sT14:%02d:00Z" % (day, i % 60), "qty": 100,
                      "price": 10.0, "stop_price": 9.5, "entry_reason": reason or {},
                      "program": {"sid": sid, "snapshot_ref": ref} if ref else None},
            "exit": {"ts": "%sT18:%02d:00Z" % (day, i % 60), "leg": leg, "kind": kind,
                     "price": (10.0 + pnl / 100.0) if priced else None, "approx": approx},
            "realized": {"gain_dollars": pnl if priced else None, "exit_reason": leg}}


@pytest.fixture
def rv(monkeypatch):
    db = MiniDB(cfg={"cm_program": True, "cm_program_started": None})
    monkeypatch.setattr(EE, "_db", lambda: db)
    monkeypatch.setattr(JN, "_db", lambda: db)
    monkeypatch.setattr(EE, "_broker_mode", lambda: "paper")
    import usage
    monkeypatch.setattr(usage, "feature_counts", lambda top=50: [])
    state = {"docs": [], "calls": [], "config_writes": []}
    monkeypatch.setattr(JN, "load", lambda *a, **k: list(state["docs"]))
    monkeypatch.setattr(JN, "reconcile", lambda: state["calls"].append("reconcile") or {})
    real_resolve = JN.resolve_exit_fills

    def resolve(orders, dry=False, now=None):
        state["calls"].append("resolve")
        return real_resolve(orders, dry=dry, now=now)

    monkeypatch.setattr(JN, "resolve_exit_fills", resolve)
    real_update = EE.update_config
    monkeypatch.setattr(EE, "update_config",
                        lambda **f: state["config_writes"].append(f) or real_update(**f))
    return db, state


def _ledger(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


def _autopsy(db, tid, cls, feedback="shakeout under the band; reversal failed"):
    db.trade_autopsies.rows.append({"_id": tid, "classification": cls, "feedback": feedback})


# ═════════════════════════════════════════════════════════════════════════════
# Statistics
# ═════════════════════════════════════════════════════════════════════════════
def test_wilson_interval_in_percent_and_its_edges():
    assert LR.wilson(0, 0) == [None, None]
    assert LR.wilson(1, 1) == [None, None]
    assert LR.wilson(3, 10) == [10.8, 60.3]
    assert LR.wilson(0, 5)[0] == 0.0 and LR.wilson(5, 5)[1] == 100.0
    for bad in (("x", 3), (4, 3), (-1, 3), (None, None)):
        assert LR.wilson(*bad) == [None, None]


def test_the_bootstrap_is_seeded_and_deterministic():
    xs = [-1.0, 0.5, 2.0, -0.8, 1.1, -1.0, 0.3]
    a, b = LR.boot_mean_ci(xs), LR.boot_mean_ci(xs)
    assert a == b and a[0] < sum(xs) / len(xs) < a[1]
    assert LR.boot_mean_ci(xs, seed=1) != a or LR.boot_mean_ci(xs, B=500) != a
    assert LR.boot_mean_ci([1.0]) == [None, None] and LR.boot_mean_ci([]) == [None, None]
    assert LR.boot_mean_ci([None, "x", float("nan")]) == [None, None]
    assert (LR.BOOT_B, LR.BOOT_SEED, LR.KILL_MIN_N, LR.CLASS_PROPOSE_MIN) == \
        (2000, 20260927, 20, 3)


# ═════════════════════════════════════════════════════════════════════════════
# The scoreboard
# ═════════════════════════════════════════════════════════════════════════════
def test_distribution_exits_count_and_unpriced_closes_stay_out_of_expectancy(rv):
    docs = [jdoc("A", "amd", 100.0, i=1, leg="take_profit"),
            jdoc("B", "amd", -50.0, i=2, leg=None, kind="distribution_exit", approx=True),
            jdoc("C", "amd", 0.0, i=3, leg=None, kind="watchdog_exit", priced=False)]
    b = LR.scoreboard(ts=LR.trades(docs=docs))["amd"]
    assert b["n_closed"] == 3 and b["n_unpriced"] == 1 and b["n_approx"] == 1
    assert b["exits_by_kind"] == {"take_profit": 1, "distribution_exit": 1, "watchdog_exit": 1}
    assert (b["wins"], b["losses"], b["win_pct"]) == (1, 1, 50.0)
    assert b["exp_r"] == 0.5                                   # (2R + -1R) / 2 — C is out
    assert b["total_usd"] == 50.0 and b["small_n"] is True and b["measured"] is False
    assert b["open_risk_label"] == "risk at entry"


def test_zero_dte_r_is_pnl_over_the_premium_stop_risk(rv):
    db, _ = rv
    from trading import zero_dte_lane as ZD
    db.zero_dte_positions.rows.append({"pos_id": "z1", "symbol": "SPY261", "status": "closed",
                                       "fill_price": 2.0, "fill_qty": 1, "realized_pnl": -50.0,
                                       "exit_price": 1.0,
                                       "close_reason": "premium -50% (bid 1.00 vs fill 2.00)",
                                       "order_ts": "2026-09-28T14:00:00Z",
                                       "closed_ts": "2026-09-28T15:00:00Z"})
    db.zero_dte_positions.rows.append({"pos_id": "z2", "status": "dry_run"})
    t = [x for x in LR.trades(docs=[]) if x["sid"] == "signals"]
    assert len(t) == 1
    risk = 2.0 * 100 * 1 * ZD.PREMIUM_STOP_PCT / 100.0
    assert t[0]["risk_usd"] == round(risk, 2) and t[0]["r"] == round(-50.0 / risk, 2)
    assert t[0]["exit_kind"] == "premium_stop"


def test_since_day_filters_on_the_entry_day(rv):
    docs = [jdoc("A", "amd", 10.0, day="2026-09-25"), jdoc("B", "amd", 10.0)]
    assert [t["symbol"] for t in LR.trades("2026-09-28", docs=docs)] == ["B"]


# ═════════════════════════════════════════════════════════════════════════════
# The daily build
# ═════════════════════════════════════════════════════════════════════════════
def test_a_closed_day_writes_nothing(rv):
    db, state = rv
    assert LR.build(now=datetime(2026, 9, 26, 17, 5, tzinfo=ET), brk=FillsBroker()) == \
        {"skipped": "weekend"}
    assert LR.build(day="2026-09-07", now=NOW, brk=FillsBroker())["skipped"].startswith("holiday")
    assert db.lane_reviews.rows == [] and state["calls"] == []


def test_fills_resolve_before_the_reconcile_and_the_review_never_writes_config(rv):
    db, state = rv
    state["docs"] = [jdoc("L%d" % i, "amd", -50.0 - i, i=i) for i in range(3)]
    for i in range(3):
        _autopsy(db, "L%d-%d" % (i, i), "market_down")
    doc = LR.build(now=NOW, brk=FillsBroker())
    assert state["calls"] == ["resolve", "reconcile"]
    assert state["config_writes"] == []
    assert db.lane_reviews.rows[0]["_id"] == DAY and doc["fills"] == {"ok": True, "resolved": 0}
    props = db.lane_proposals.rows
    assert len(props) == 1 and props[0]["status"] == "proposed"
    assert props[0]["kind"] == "class:market_down" and props[0]["level"] == "code"
    assert props[0]["todo"] == "index filter" and props[0]["change"] is None
    assert EE.get_config().get("cm_lanes") in (None, {})
    assert "UNMEASURED" in doc["summary_lines"][-1]


def test_an_unreadable_broker_says_approximate(rv):
    db, state = rv
    doc = LR.build(now=NOW, brk=FillsBroker(raises=RuntimeError("HTTP 500")))
    assert doc["fills"]["ok"] is False
    assert any("approximate" in line for line in doc["summary_lines"])
    assert state["calls"] == ["reconcile"]                   # the review still runs


def test_closed_orders_are_paged_past_500(rv):
    page1 = [{"id": "o%d" % i, "submitted_at": "2026-09-2%dT10:00:%02dZ" % (1 + i // 60, i % 60)}
             for i in range(LR.BROKER_PAGE)]
    page2 = [dict(page1[-1]), {"id": "x1", "submitted_at": "2026-09-28T10:00:00Z"}]
    brk = FillsBroker(pages=[page1, page2])
    out = LR._paged_closed_orders(brk, "2026-09-14T00:00:00Z")
    assert brk.calls == ["2026-09-14T00:00:00Z", page1[-1]["submitted_at"]]
    assert len(out) == LR.BROKER_PAGE + 1                     # the overlap row once
    short = FillsBroker(pages=[[{"id": "a", "submitted_at": "x"}]])
    assert len(LR._paged_closed_orders(short, "s")) == 1 and len(short.calls) == 1


def test_a_dry_build_writes_nothing(rv):
    db, state = rv
    state["docs"] = [jdoc("L%d" % i, "amd", -50.0, i=i) for i in range(3)]
    doc = LR.build(now=NOW, brk=FillsBroker(), record=False)
    assert "reconcile" not in state["calls"] and state["config_writes"] == []
    assert db.lane_reviews.rows == [] and db.lane_proposals.rows == []
    assert db.journal_exit_fills.rows == [] and doc["day"] == DAY


@pytest.mark.parametrize("n,paused", [(19, False), (20, True)])
def test_a_pause_waits_for_twenty_closed_trades(rv, n, paused):
    db, state = rv
    state["docs"] = [jdoc("L%d" % i, "amd", -40.0 - (i % 5) * 5, i=i) for i in range(n)]
    doc = LR.build(now=NOW, brk=FillsBroker())
    pauses = [p for p in doc["proposals"] if p["kind"] == "pause"]
    assert bool(pauses) is paused
    if paused:
        p = pauses[0]
        assert p["change"] == {"key": "cm_lanes", "value": {"amd": False}}
        assert p["evidence"]["exp_r_ci"][1] < 0 and p["level"] == "config"
    assert state["config_writes"] == []


def test_a_pause_needs_the_whole_interval_below_zero(rv):
    board = {"amd": dict(LR.empty_board(), n_closed=30, exp_r=-0.1, exp_r_ci=[-0.5, 0.2])}
    assert LR.propose(board, {}, {}) == []


@pytest.mark.parametrize("n,proposed", [(2, False), (3, True)])
def test_a_loss_class_needs_three(rv, n, proposed):
    db, state = rv
    state["docs"] = [jdoc("L%d" % i, "deep_demand", -50.0, i=i) for i in range(n)]
    for i in range(n):
        _autopsy(db, "L%d-%d" % (i, i), "shakeout")
    doc = LR.build(now=NOW, brk=FillsBroker())
    assert bool([p for p in doc["proposals"] if p["kind"] == "class:shakeout"]) is proposed
    row = next(s for s in doc["strategies"] if s["sid"] == "deep_demand")
    assert row["loss_classes"] == {"shakeout": n}
    assert row["named_classes"] == (["shakeout"] if proposed else [])


def test_a_dismissed_card_returns_only_on_more_evidence(rv):
    db, state = rv
    state["docs"] = [jdoc("L%d" % i, "amd", -50.0, i=i) for i in range(3)]
    for i in range(3):
        _autopsy(db, "L%d-%d" % (i, i), "market_down")
    pid = LR.build(now=NOW, brk=FillsBroker())["proposals"][0]["id"]
    LR.dismiss(pid, "owner@x")
    assert LR.build(now=NOW, brk=FillsBroker())["proposals"] == []
    state["docs"].append(jdoc("L3", "amd", -50.0, i=3))
    _autopsy(db, "L3-3", "market_down")
    again = LR.build(now=NOW, brk=FillsBroker())["proposals"]
    assert [p["id"] for p in again] == [pid] and again[0]["evidence"]["count"] == 4


def test_demand_residents_is_proposed_only_when_it_is_on():
    cc = {"zones": {"chased": 3}}
    assert LR.propose({}, cc, {}) == []                               # already strict
    p = LR.propose({}, cc, {"zone_edge_rules": {"demand_residents": True}})
    assert p[0]["change"] == {"key": "zone_edge_rules", "value": {"demand_residents": False}}
    assert LR.propose({}, {"amd": {"chased": 3}}, {})[0]["todo"] == "entry-distance cap"
    bf = LR.propose({}, {"zones": {"band_failed": 3}}, {})[0]          # default is already 2
    assert bf["change"] is None and bf["todo"] == "band selection"
    bf = LR.propose({}, {"zones": {"band_failed": 3}}, {"zone_edge_rules": {"min_touches": 1}})[0]
    assert bf["change"] == {"key": "zone_edge_rules", "value": {"min_touches": 2}}
    assert LR.propose({}, {"zones": {"unclassified": 9}}, {}) == []
    assert LR.propose({}, {"minervini": {"shakeout": 9}}, {}) == []   # not a Chart Maps lane


def test_the_loser_line_reads_the_entry_snapshot_and_says_reversal(rv):
    db, state = rv
    ref = "cheetah-QBX-20260928-entry"
    db.cm_lane_entries.rows.append({"_id": ref, "adapter_version": "cm-lanes-v1",
                                    "live": {"verdict": "READY",
                                             "band": {"lo": 9.37, "hi": 9.59},
                                             "room": {"room_pct": 6.2, "target": 11.0}}})
    state["docs"] = [jdoc("QBX", "quick_bounce", -50.0, i=1, ref=ref)]
    _autopsy(db, "QBX-1", "shakeout", feedback="bounced once then broke the band; stop tight")
    doc = LR.build(now=NOW, brk=FillsBroker())
    row = next(s for s in doc["strategies"] if s["sid"] == "quick_bounce")
    line = row["losers_today"][0]
    assert line.startswith("QBX −1R −$50")
    assert "band 9.37–9.59" in line and "room +6.2% → 11" in line
    assert "Quick Reversal, cm-lanes-v1" in line and "reversed once" in line
    assert "bounc" not in line.lower() and "bounc" not in row["label"].lower()
    t = dict(LR.trades(docs=state["docs"])[0], approx=True)
    assert LR.loss_line(t, None, None).endswith("(≈ price)")
    assert LR._no_bounce("Bounce bounced bounces bouncing") == "Reversal reversed reversals reversing"
    assert "autopsy pending" in LR.loss_line(t, None, None)


# ═════════════════════════════════════════════════════════════════════════════
# Confirm / Dismiss
# ═════════════════════════════════════════════════════════════════════════════
def _seed(db, pid, **p):
    db.lane_proposals.rows.append(dict({"_id": pid, "id": pid, "sid": "amd", "status": "proposed",
                                        "evidence": {"count": 3}}, **p))


def test_a_config_confirm_applies_exactly_and_ledgers_before_and_after(rv):
    db, state = rv
    db.trading_config.rows[0]["cm_lanes"] = {"ict": True}
    _seed(db, "p1", kind="pause", level="config",
          change={"key": "cm_lanes", "value": {"amd": False}})
    out = LR.confirm("p1", "owner@x")
    assert out["status"] == "confirmed" and out["applied"] == {"cm_lanes": {"ict": True, "amd": False}}
    assert EE.get_config()["cm_lanes"] == {"ict": True, "amd": False}
    row = _ledger(db, "lane_proposal_confirmed")[0]["detail"]
    assert row["before"] == {"ict": True} and row["after"] == {"ict": True, "amd": False}
    assert row["by"] == "owner@x"
    with pytest.raises(ValueError, match="already confirmed"):
        LR.confirm("p1", "owner@x")
    with pytest.raises(ValueError, match="already confirmed"):
        LR.dismiss("p1", "owner@x")


def test_a_zone_rules_confirm_merges_and_validates(rv):
    db, _ = rv
    db.trading_config.rows[0]["zone_edge_rules"] = {"breakout_any_band": True}
    _seed(db, "p2", kind="class:band_failed", level="config",
          change={"key": "zone_edge_rules", "value": {"min_touches": 2}})
    LR.confirm("p2", "o")
    assert EE.get_config()["zone_edge_rules"] == {"breakout_any_band": True, "min_touches": 2}
    _seed(db, "p3", level="config", change={"key": "zone_edge_rules", "value": {"typo": 1}})
    with pytest.raises(ValueError, match="unknown key"):
        LR.confirm("p3", "o")
    _seed(db, "p4", level="config", change={"key": "equity_cap", "value": 1e9})
    with pytest.raises(ValueError, match="not applyable"):
        LR.confirm("p4", "o")


def test_a_code_level_confirm_changes_nothing(rv):
    db, state = rv
    _seed(db, "c1", kind="class:market_down", level="code", change=None, todo="index filter")
    before = dict(EE.get_config())
    out = LR.confirm("c1", "o")
    assert out["status"] == "todo" and out["applied"] is None
    assert state["config_writes"] == [] and EE.get_config() == before
    assert _ledger(db, "lane_proposal_confirmed")[0]["detail"]["todo"] == "index filter"


def test_dismiss_ledgers_and_unknown_ids_raise(rv):
    db, state = rv
    _seed(db, "d1", level="code", change=None, todo="x")
    assert LR.dismiss("d1", "o") == {"id": "d1", "status": "dismissed"}
    assert _ledger(db, "lane_proposal_dismissed")[0]["detail"]["evidence"] == {"count": 3}
    assert state["config_writes"] == []
    with pytest.raises(KeyError):
        LR.confirm("nope", "o")
    with pytest.raises(KeyError):
        LR.dismiss("nope", "o")


# ═════════════════════════════════════════════════════════════════════════════
# Reads + the API
# ═════════════════════════════════════════════════════════════════════════════
def test_latest_full_and_summary(rv):
    db, state = rv
    assert LR.latest()["day"] is None
    state["docs"] = [jdoc("L%d" % i, "amd", -50.0, i=i) for i in range(3)]
    for i in range(3):
        _autopsy(db, "L%d-%d" % (i, i), "market_down")
    LR.build(now=NOW, brk=FillsBroker())
    full = LR.latest("full")
    assert full["day"] == DAY and full["link"] == LR.LINK and len(full["proposals_open"]) == 1
    s = LR.latest("summary")
    assert set(s) == {"day", "built_at", "headline", "strategies", "losers", "proposals_open",
                      "summary_lines", "link"}
    assert len(s["losers"]) == 3 and s["proposals_open"][0]["level"] == "code"
    amd = next(x for x in s["strategies"] if x["sid"] == "amd")
    assert amd["n_closed"] == 3 and amd["today"]["losers"] == 3


def test_the_review_routes(rv):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    db, _ = rv
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_review_latest(email="nobody@example.com"))
    assert exc.value.status_code == 403
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_review_day(day="2026-01-01", email=admin))
    assert exc.value.status_code == 404
    LR.build(now=NOW, brk=FillsBroker())
    body = json.loads(asyncio.run(TA.trading_review_day(day=DAY, email=admin)).body)
    assert body["day"] == DAY
    body = json.loads(asyncio.run(TA.trading_review_latest(format="SUMMARY", email=admin)).body)
    assert "losers" in body and "strategies" in body
    _seed(db, "k1", level="code", change=None, todo="x")
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_review_confirm("missing", email=admin))
    assert exc.value.status_code == 404
    body = json.loads(asyncio.run(TA.trading_review_confirm("k1", email=admin)).body)
    assert body["status"] == "todo"
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_review_dismiss("k1", email=admin))
    assert exc.value.status_code == 409
    _seed(db, "k2", level="config", change={"key": "equity_cap", "value": 1})
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_review_confirm("k2", email=admin))
    assert exc.value.status_code == 400
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_review_confirm("k2", email="nobody@example.com"))
    assert exc.value.status_code == 403


def test_the_config_route_validates_the_program_keys(rv):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    db, _ = rv
    db.trading_config.rows[0]["cm_program"] = False
    body = json.loads(asyncio.run(TA.trading_config({"cm_lanes": {"ict": True}},
                                                    email=admin)).body)
    assert body == {"cm_lanes": {"ict": True}}
    for bad in ({"cm_program": "yes"}, {"cm_lanes": {"ict": 1}},
                {"cm_lane_caps": {"amd": {"per_day": 5}}}, {"zone_edge_rules": {"typo": 1}}):
        with pytest.raises(fastapi.HTTPException) as exc:
            asyncio.run(TA.trading_config(bad, email=admin))
        assert exc.value.status_code == 400, bad


def test_the_strategies_route_is_admin_gated(rv, monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    from trading import chart_maps_lanes as CML
    import auth
    monkeypatch.setattr(CML, "strategies_payload", lambda now=None: {"program": {}, "strategies": []})
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_strategies(email="nobody@example.com"))
    assert exc.value.status_code == 403
    body = json.loads(asyncio.run(TA.trading_strategies(email=auth.HOUSE_OWNER_EMAIL)).body)
    assert body == {"program": {}, "strategies": []}
    assert PC.PROGRAM_RISK_PCT == 0.25
