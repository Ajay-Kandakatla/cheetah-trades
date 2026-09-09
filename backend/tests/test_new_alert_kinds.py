"""The 2026-09-09 keep-set: 🔥 hot pullback + 📐 chart patterns.

Ajay: "Can you give me hot pull back alerts and chart pattern Alerts and also
Sameday deman alerts please... Kill all other.. I just wanna these alerts..
Default turn these on from tomorrow." Asked whether the stop alerts on stocks he
OWNS counted as "other", he kept those and dropped the todo reminders.

THESE THREE ARE THE THREE THIS APP HAS MEASURED AT OR BELOW A COIN FLIP. He was
shown the numbers and asked for them anyway, as a watchlist. So the tests below
pin that every push CARRIES its own record — the screen may never imply more
than the measurement supports.
"""
from __future__ import annotations

import pytest

from patterns import pattern_alerts as PA
from push import subs
from supply_demand import hot_pullback_alerts as HPA


class FakeColl:
    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def update_one(self, q, u, upsert=False):
        self.docs[q["_id"]] = u["$set"]


def _capture(monkeypatch, result=None):
    """Capture pushes, and stub `portfolio.alerts` in sys.modules.

    The real module cannot be imported under this venv's python3.9 — a pydantic
    model in it uses `str | None`. test_promo_live solves it the same way; the
    alternative is importlib gymnastics for a function we only need to return a
    string."""
    import sys, types
    sent = []
    fake = types.SimpleNamespace(_resolve_owner=lambda: "o@x")
    pkg = types.ModuleType("portfolio"); pkg.__path__ = []; pkg.alerts = fake
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.alerts", fake)
    from push import sender
    monkeypatch.setattr(sender, "send_to_user",
                        lambda email, msg, kind=None: (sent.append((kind, msg)),
                                                       dict(result or {"sent": 1, "total_targets": 1}))[1])
    return sent


# ── the keep-set itself ────────────────────────────────────────────────────
def test_the_keep_set_is_exactly_what_he_asked_for():
    assert subs.OWNER_KEEP_SET == frozenset({
        "hot_pullback_alert", "pattern_alert", "demand_alert", "position_alert"})


def test_the_killed_kinds_are_really_gone_from_the_keep_set():
    for dead in ("zone_bounce_alert", "supply_break_alert", "todo_reminder",
                 "promo_alert", "pivot_alert"):
        assert dead not in subs.OWNER_KEEP_SET, dead


def test_both_new_kinds_are_registered_or_they_silently_drop():
    """A kind missing from default_prefs sends to ZERO devices, silently — the
    trap that cost this app a week of "alerts are broken"."""
    d = subs.default_prefs()
    assert d["hot_pullback_alert"] is True and d["pattern_alert"] is True
    assert set(subs.OWNER_KEEP_SET) <= set(d), "every kept kind must exist in default_prefs"


def test_owner_prefs_turns_on_the_four_and_nothing_else():
    p = subs.owner_prefs()
    on = {k for k, v in p.items() if v is True}
    assert on == set(subs.OWNER_KEEP_SET)


def test_both_new_kinds_are_market_kinds_so_closed_days_stay_quiet():
    from market_hours import gate
    assert "hot_pullback_alert" in gate.MARKET_ALERT_KINDS
    assert "pattern_alert" in gate.MARKET_ALERT_KINDS


# ── 🔥 hot pullback ────────────────────────────────────────────────────────
def _hp_row(sym="DYN"):
    return {"symbol": sym, "close": 20.31, "flush_pct": -30.0, "reversal": 19.5,
            "vol_x": 11.0, "band": {"lo": 16.56, "hi": 17.02},
            "plan": {"stop": 16.48}}


def test_hot_pullback_push_carries_the_interval_that_includes_zero(monkeypatch):
    """The board measures 51.8% win with a 95% interval of -0.19R to +0.41R.
    The phone must say so — he asked for a watchlist ping, not an edge."""
    sent = _capture(monkeypatch)
    out = HPA.check_once(owner="o@x", rows=[_hp_row()], day="2026-09-08",
                         coll=FakeColl())
    assert out["pushed"] == 1
    _kind, msg = sent[0]
    assert msg["kind"] == "hot_pullback_alert" and msg["ticker"] == "DYN"
    assert "51.8% win" in msg["body"]
    assert "INCLUDES ZERO" in msg["body"]
    assert "Watchlist, not an edge" in msg["body"]


def test_hot_pullback_study_line_is_built_from_the_study_dict_never_retyped():
    from supply_demand import hot_pullback as HP
    line = HPA.study_line()
    assert str(HP.STUDY["sim_win_pct"]) in line
    assert str(HP.STUDY["sim_n"]) in line


def test_hot_pullback_pushes_once_per_name_per_signal_day(monkeypatch):
    sent = _capture(monkeypatch)
    coll = FakeColl()
    kw = dict(owner="o@x", rows=[_hp_row()], day="2026-09-08", coll=coll)
    assert HPA.check_once(**kw)["pushed"] == 1
    out = HPA.check_once(**kw)
    assert out["pushed"] == 0 and out["skipped_seen"] == 1 and len(sent) == 1


def test_hot_pullback_caps_singles_and_digests_the_rest(monkeypatch):
    sent = _capture(monkeypatch)
    rows = [_hp_row("S%d" % i) for i in range(9)]
    out = HPA.check_once(owner="o@x", rows=rows, day="2026-09-08", coll=FakeColl())
    assert out["singles"] == HPA.MAX_SINGLES and out["digest"] is True
    assert len(sent) == HPA.MAX_SINGLES + 1
    assert "more hot pullbacks" in sent[-1][1]["title"]


def test_hot_pullback_with_nothing_recorded_pushes_nothing(monkeypatch):
    sent = _capture(monkeypatch)
    out = HPA.check_once(owner="o@x", rows=[], day=None, coll=FakeColl())
    assert out["pushed"] == 0 and sent == []


# ── 📐 chart patterns ──────────────────────────────────────────────────────
def _pat(sym="AAA", pattern="double_bottom", status="confirmed", bars=0):
    return {"symbol": sym, "pattern": pattern, "status": status,
            "bars_since_confirm": bars, "confirmed_date": "2026-09-09",
            "last_close": 12.5, "neckline": 12.0, "stop": 11.4, "target": 14.1}


def test_pattern_push_carries_its_record_AND_the_placebo(monkeypatch):
    """His ledger: double_bottom 43% up over 248 against a 50% placebo. Neither
    number may be dropped — a per-name rate without its placebo is the thing he
    made a standing rule about."""
    sent = _capture(monkeypatch)
    out = PA.check_once(owner="o@x", rows=[_pat()], coll=FakeColl())
    assert out["pushed"] == 1
    _kind, msg = sent[0]
    assert msg["kind"] == "pattern_alert" and msg["ticker"] == "AAA"
    assert "43% up over 248" in msg["body"]
    assert "placebo 50%" in msg["body"]
    assert "does NOT beat chance" in msg["body"]


def test_no_pattern_in_the_table_beats_the_placebo_so_none_may_claim_to():
    from supply_demand import bullish_context as BC
    placebo = BC.PATTERN_PLACEBO[1]
    for name, (_n, up, _m) in BC.PATTERN_RECORD.items():
        assert up <= placebo, name
        assert "does NOT beat chance" in PA.record_line(name), name


def test_only_a_fresh_confirmed_named_pattern_fires():
    assert PA.is_fresh(_pat()) is True
    assert PA.is_fresh(_pat(status="forming")) is False
    assert PA.is_fresh(_pat(bars=PA.FRESH_BARS + 1)) is False
    assert PA.is_fresh(_pat(pattern="flat_top")) is False, "fired on 120/120 names"
    for bad in (None, {}, {"pattern": "double_bottom"},
                _pat(bars="soon"), _pat(bars=-1)):
        assert PA.is_fresh(bad) is False, bad


def test_pattern_pushes_once_per_symbol_pattern_and_confirmation_day(monkeypatch):
    sent = _capture(monkeypatch)
    coll = FakeColl()
    assert PA.check_once(owner="o@x", rows=[_pat()], coll=coll)["pushed"] == 1
    out = PA.check_once(owner="o@x", rows=[_pat()], coll=coll)
    assert out["pushed"] == 0 and out["skipped_seen"] == 1 and len(sent) == 1
    # a DIFFERENT pattern on the same name is its own alert
    assert PA.check_once(owner="o@x", rows=[_pat(pattern="cup_with_handle")],
                         coll=coll)["pushed"] == 1


def test_pattern_counts_what_it_skipped_so_a_quiet_phone_is_explainable(monkeypatch):
    _capture(monkeypatch)
    rows = [_pat(status="forming"), _pat(sym="B", pattern="flat_top"), _pat(sym="C")]
    out = PA.check_once(owner="o@x", rows=rows, coll=FakeColl())
    assert out["skipped_stale"] == 2 and out["fresh"] == 1 and out["pushed"] == 1
