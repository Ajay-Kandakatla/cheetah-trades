"""Quarter-over-quarter institutional flow — the comparison and its alerts.

Ajay 2026-08-16: "give me updated and notification as Accumulations change as
money moving I need a comparison."

The load-bearing test is `test_a_mixed_payload_is_never_summed_across_quarters`.
The existing modal added one fund's Q1 delta to another's Q2 delta and printed
a confident "Net inflow: +$1.1B" that describes no period at all. Every number
here is scoped to a single quarter or explicitly marked not comparable.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import accumulation_changes as ac  # noqa: E402


def _h(holder, date, value):
    return {"holder": holder, "date_reported": f"{date} 00:00:00", "value": value}


# ---------------------------------------------------------------------------
# grouping
# ---------------------------------------------------------------------------
def test_holders_group_by_their_own_filing_quarter():
    hs = [_h("A", "2026-03-31", 100), _h("B", "2026-03-31", 50),
          _h("C", "2026-06-30", 200)]
    out = ac.by_quarter(hs)
    assert set(out) == {"2026-03-31", "2026-06-30"}
    assert out["2026-03-31"]["n"] == 2 and out["2026-03-31"]["total_value"] == 150
    assert out["2026-06-30"]["n"] == 1


def test_grouping_ignores_undated_and_malformed_rows():
    hs = [_h("A", "2026-03-31", 100),
          {"holder": "X", "value": 999},
          {"holder": "Y", "date_reported": "garbage", "value": 999}]
    out = ac.by_quarter(hs)
    assert list(out) == ["2026-03-31"]
    assert out["2026-03-31"]["total_value"] == 100


def test_grouping_treats_a_missing_value_as_zero_not_a_crash():
    out = ac.by_quarter([{"holder": "A", "date_reported": "2026-06-30", "value": None}])
    assert out["2026-06-30"]["total_value"] == 0.0


# ---------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------
def test_a_mixed_payload_is_never_summed_across_quarters():
    """THE BUG THIS EXISTS TO PREVENT. APGE-shaped input: 6 funds on Mar 31,
    4 on Jun 30, and NO fund in both — which is what real payloads look like.
    Differencing the quarter totals would print +$200 of 'flow'; the honest
    answer is that there is nothing to compare."""
    hs = ([_h(f"old{i}", "2026-03-31", 100) for i in range(6)]
          + [_h(f"new{i}", "2026-06-30", 200) for i in range(4)])
    c = ac.compare_quarters(hs)
    assert c["comparable"] is False
    assert "sampling artifact" in c["reason"]
    assert c["overlap_funds"] == 0


def test_comparison_names_new_buyers_and_exits():
    c = ac.compare_maps({"Stayer": 100, "Leaver": 50},
                        {"Stayer": 120, "Joiner": 80})
    assert c["new_buyers"] == ["Joiner"] and c["exits"] == ["Leaver"]
    # entrant/exit dollars are reported, never folded into the flow figure
    assert c["new_buyer_usd"] == 80 and c["exit_usd"] == 50
    assert c["net_change_usd"] == 20        # Stayer only: 120 - 100


def test_direction_reads_from_the_sign():
    up = ac.compare_maps({"A": 100, "B": 10, "C": 10}, {"A": 300, "B": 10, "C": 10})
    down = ac.compare_maps({"A": 300, "B": 10, "C": 10}, {"A": 100, "B": 10, "C": 10})
    assert up["direction"] == "accumulating" and up["net_change_pct"] == 166.67
    assert down["direction"] == "distributing" and down["net_change_pct"] == -62.5


def test_one_quarter_only_is_NOT_comparable():
    """A name whose funds have not rolled must say so, not report +0%."""
    c = ac.compare_quarters([_h("A", "2026-03-31", 100), _h("B", "2026-03-31", 50)])
    assert c["comparable"] is False
    assert "not rolled" in c["reason"]


def test_no_dated_holdings_is_not_comparable():
    c = ac.compare_quarters([])
    assert c["comparable"] is False and "no dated holdings" in c["reason"]


def test_a_zero_prior_book_does_not_divide_by_zero():
    c = ac.compare_maps({"A": 0, "B": 0, "C": 0}, {"A": 500, "B": 0, "C": 0})
    assert c["net_change_pct"] is None
    assert c["net_change_usd"] == 500


def test_a_thin_overlap_is_refused():
    """The provider returns a top-N list, so 1-2 shared funds is sampling
    noise, not a flow."""
    c = ac.compare_maps({"A": 100, "B": 50}, {"A": 900, "Z": 10})
    assert c["overlap_funds"] == 1
    from_snapshot = ac.compare_maps({"A": 1, "B": 1, "C": 1}, {"A": 2, "B": 2, "C": 2})
    assert from_snapshot["overlap_funds"] == 3      # at the floor, allowed


# ---------------------------------------------------------------------------
# significance
# ---------------------------------------------------------------------------
def test_big_dollar_move_is_significant():
    assert ac.is_significant({"comparable": True, "net_change_usd": 60_000_000,
                              "net_change_pct": 2.0}) is True


def test_big_percentage_move_on_a_small_book_is_significant():
    assert ac.is_significant({"comparable": True, "net_change_usd": 5_000_000,
                              "net_change_pct": 40.0}) is True


def test_rounding_noise_is_not_significant():
    assert ac.is_significant({"comparable": True, "net_change_usd": 1_000_000,
                              "net_change_pct": 1.5}) is False


def test_a_non_comparable_ticker_is_never_significant():
    assert ac.is_significant({"comparable": False}) is False
    assert ac.is_significant({}) is False


def test_a_large_OUTFLOW_is_significant_too():
    """Money leaving is as much a change as money arriving."""
    assert ac.is_significant({"comparable": True, "net_change_usd": -90_000_000,
                              "net_change_pct": -30.0}) is True


# ---------------------------------------------------------------------------
# the alert line
# ---------------------------------------------------------------------------
def test_alert_line_is_phone_sized_and_carries_the_quarters():
    line = ac.alert_line({
        "symbol": "NVDA", "direction": "accumulating",
        "net_change_usd": 2_100_000_000, "net_change_pct": 34.0,
        "new_buyers": ["A", "B"], "exits": ["C"],
        "prev_quarter": "2026-03-31", "new_quarter": "2026-06-30",
    })
    assert "NVDA" in line and "+$2.1B" in line and "+34%" in line
    assert "2 new" in line and "1 out" in line
    assert "2026-03-31→2026-06-30" in line
    assert len(line) < 120


def test_alert_line_marks_an_outflow_red_and_signed():
    line = ac.alert_line({
        "symbol": "XYZ", "direction": "distributing",
        "net_change_usd": -450_000_000, "net_change_pct": -22.0,
        "new_buyers": [], "exits": [], "prev_quarter": "Q1", "new_quarter": "Q2",
    })
    assert "🔴" in line and "-$450M" in line
    assert "new" not in line and "out" not in line


def test_money_formatting_across_magnitudes():
    assert ac._fmt_usd(2_100_000_000) == "+$2.1B"
    assert ac._fmt_usd(-450_000_000) == "-$450M"
    assert ac._fmt_usd(12_345) == "+$12,345"
    assert ac._fmt_usd(None) == "+$0"


# ---------------------------------------------------------------------------
# the sweep: idempotency + scope
# ---------------------------------------------------------------------------
class _Coll:
    def __init__(self):
        self.docs = []

    def find_one(self, q, *a, **kw):
        return next((d for d in self.docs
                     if all(d.get(k) == v for k, v in q.items())), None)

    def insert_one(self, doc):
        self.docs.append(doc)


class _DB:
    def __init__(self):
        self.accumulation_changes = _Coll()


def test_a_quarter_is_recorded_and_alerted_only_ONCE(monkeypatch):
    """A weekly cron would otherwise re-announce the same quarter every Sunday
    for three months."""
    db = _DB()
    monkeypatch.setattr(ac, "_db", lambda: db)
    monkeypatch.setattr(ac, "for_symbol", lambda s, **kw: {
        "symbol": s, "comparable": True, "significant": True,
        "new_quarter": "2026-06-30", "net_change_usd": 500_000_000,
        "net_change_pct": 40.0, "direction": "accumulating",
        "new_buyers": [], "exits": [],
    })

    first = ac.sweep(["NVDA"])
    assert first["new_this_run"] == 1
    second = ac.sweep(["NVDA"])
    assert second["new_this_run"] == 0
    assert second["significant"] == 1        # still significant, just not NEW


def test_insignificant_moves_are_never_recorded(monkeypatch):
    db = _DB()
    monkeypatch.setattr(ac, "_db", lambda: db)
    monkeypatch.setattr(ac, "for_symbol", lambda s, **kw: {
        "symbol": s, "comparable": True, "significant": False,
    })
    res = ac.sweep(["KO"])
    assert res["new_this_run"] == 0 and db.accumulation_changes.docs == []


def test_sweep_does_not_notify_unless_asked(monkeypatch):
    db = _DB()
    sent = []
    monkeypatch.setattr(ac, "_db", lambda: db)
    monkeypatch.setattr(ac, "_notify", lambda ch: sent.append(ch) or len(ch))
    monkeypatch.setattr(ac, "for_symbol", lambda s, **kw: {
        "symbol": s, "comparable": True, "significant": True,
        "new_quarter": "2026-06-30", "net_change_usd": 500_000_000,
    })
    ac.sweep(["NVDA"])
    assert sent == []
    ac.sweep(["AMD"], notify=True)
    assert len(sent) == 1


def test_alert_scope_is_holdings_and_watchlist_only():
    """A universe-wide accumulation alert is ~2,600 pushes a quarter, which is
    how a useful channel becomes a muted one."""
    assert ac.ALERT_SCOPE == ("portfolio", "watchlist")


def test_the_new_push_kind_is_registered_and_not_disabled():
    from push import subs
    assert subs.default_prefs().get("accumulation_change") is True
    assert "accumulation_change" not in subs.DISABLED_ALERT_KINDS


def test_notification_is_batched_into_one_message(monkeypatch):
    """One push for N names, not N pushes."""
    payloads = []

    class _Sender:
        @staticmethod
        def send_to_user(email, payload, kind=None):
            payloads.append(payload)
            return {"sent": 1}

    monkeypatch.setitem(sys.modules, "push.sender", _Sender())
    import push
    monkeypatch.setattr(push, "sender", _Sender(), raising=False)

    changes = [{"symbol": f"T{i}", "direction": "accumulating",
                "net_change_usd": 100_000_000 * (i + 1), "net_change_pct": 20.0,
                "new_buyers": [], "exits": [],
                "prev_quarter": "2026-03-31", "new_quarter": "2026-06-30"}
               for i in range(8)]
    ac._notify(changes)
    assert len(payloads) == 1
    assert payloads[0]["kind"] == "accumulation_change"
    assert "8 names" in payloads[0]["title"]
    assert "+3 more" in payloads[0]["body"]        # top 5 shown, rest counted
    assert len(payloads[0]["body"]) <= 300


# ---------------------------------------------------------------------------
# snapshot hygiene — the baseline a future comparison will trust
# ---------------------------------------------------------------------------
class _SnapColl:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)

    def delete_many(self, *a, **kw):
        pass

    def find_one(self, q, sort=None):
        return self.docs[-1] if self.docs else None


def test_an_empty_payload_is_never_banked_as_a_baseline(monkeypatch):
    """REGRESSION: an empty snapshot still matches the "different quarter"
    lookup later, so it would be picked as the baseline and compared against
    nothing — inventing a 100% outflow on a name we simply had no data for."""
    coll = _SnapColl()
    monkeypatch.setattr(ac, "_snapshots", lambda: coll)

    assert ac.take_snapshot("MUU", {"holders": [], "period": {}}) is None
    assert ac.take_snapshot("X", {"holders": [], "period": {"dominant": "2026-06-30"}}) is None
    assert ac.take_snapshot("Y", {"holders": [{"holder": "A", "value": 1}],
                                  "period": {}}) is None
    assert coll.docs == []


def test_a_real_payload_is_banked_with_its_quarter(monkeypatch):
    coll = _SnapColl()
    monkeypatch.setattr(ac, "_snapshots", lambda: coll)
    doc = ac.take_snapshot("NVDA", {
        "holders": [{"holder": "Vanguard", "value": 100.0},
                    {"holder": "BlackRock", "value": 50.0}],
        "period": {"dominant": "2026-06-30"}})
    assert doc is not None
    assert coll.docs[0]["dominant_quarter"] == "2026-06-30"
    assert coll.docs[0]["holders"] == {"Vanguard": 100.0, "BlackRock": 50.0}


def test_comparison_says_baseline_recorded_when_there_is_no_prior(monkeypatch):
    """First ever sweep must be explicit that comparisons start NEXT quarter,
    not silently report a flat 0%."""
    class _Empty(_SnapColl):
        def find_one(self, q, sort=None):
            return None

    monkeypatch.setattr(ac, "_snapshots", lambda: _Empty())
    c = ac.compare_to_snapshot("NVDA", {"holders": [{"holder": "A", "value": 1}],
                                        "period": {"dominant": "2026-06-30"}})
    assert c["comparable"] is False
    assert "comparisons begin" in c["reason"]
