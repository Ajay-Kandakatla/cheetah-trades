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


class _AllAtDemand(dict):
    """Every symbol has zone coverage and is standing INSIDE a demand band.
    The `anchors` seam exists so the gate's own tests can drive it without
    Mongo, prices or a zone build."""

    def __contains__(self, _k):
        return True

    def get(self, _k, _default=None):
        return {"state": "in_zone", "price": 12.5, "role": "demand",
                "band": {"kind": "demand", "lo": 12.2, "hi": 12.9, "touches": 3},
                "off_floor_pct": 2.46}


_ANCH = _AllAtDemand()

_REVERSAL = {"state": "reversal", "price": 12.5, "role": "demand",
             "band": {"kind": "demand", "lo": 11.4, "hi": 12.0, "touches": 3},
             "off_low_pct": 6.2, "above_top_pct": 4.17, "sessions_ago": 1}


def test_pattern_push_carries_its_record_AND_the_placebo(monkeypatch):
    """His ledger: double_bottom 43% up over 248 against a 50% placebo. Neither
    number may be dropped — a per-name rate without its placebo is the thing he
    made a standing rule about."""
    sent = _capture(monkeypatch)
    out = PA.check_once(owner="o@x", rows=[_pat()], coll=FakeColl(), anchors=_ANCH)
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
    assert PA.check_once(owner="o@x", rows=[_pat()], coll=coll, anchors=_ANCH)["pushed"] == 1
    out = PA.check_once(owner="o@x", rows=[_pat()], coll=coll, anchors=_ANCH)
    assert out["pushed"] == 0 and out["skipped_seen"] == 1 and len(sent) == 1
    # a DIFFERENT pattern on the same name is its own alert
    assert PA.check_once(owner="o@x", rows=[_pat(pattern="cup_with_handle")],
                         coll=coll, anchors=_ANCH)["pushed"] == 1


def test_pattern_counts_what_it_skipped_so_a_quiet_phone_is_explainable(monkeypatch):
    _capture(monkeypatch)
    rows = [_pat(status="forming"), _pat(sym="B", pattern="flat_top"), _pat(sym="C")]
    out = PA.check_once(owner="o@x", rows=rows, coll=FakeColl(), anchors=_ANCH)
    assert out["skipped_stale"] == 2 and out["fresh"] == 1 and out["pushed"] == 1


# ── the push builders must never raise on a real recorded row ──────────────
# Caught by a dry run before the 08:15 cron ever fired: `reversal` on a recorded
# hot-pullback row is a DICT ({"off_low_pct", "range_pos"}), not a number, and
# float(dict) raises. A push builder that throws takes the whole pass with it.
def test_hot_pullback_message_handles_the_real_recorded_row_shape():
    row = {"symbol": "DYN", "date": "2026-09-08", "close": 20.31, "prev_close": 24.28,
           "flush_pct": -36.3, "vol_x": 6.9, "under_ma21_pct": -20.59,
           "reversal": {"off_low_pct": 19.46, "range_pos": 0.846},
           "band": {"kind": "demand", "lo": 16.56, "hi": 17.02, "touches": 4},
           "plan": {"stop": 16.48, "entry_note": "next open"}}
    body = HPA.message(row)["body"]
    assert "+19.5% off the low" in body
    assert "85% up the day's range" in body
    assert "flushed 36%" in body and "band $16.56-17.02" in body


@pytest.mark.parametrize("junk", [
    {}, {"symbol": "X"},
    {"symbol": "X", "close": "n/a", "flush_pct": {}, "vol_x": None,
     "reversal": "weird", "band": {"lo": None, "hi": "x"}, "plan": {"stop": float("nan")}},
    {"symbol": "X", "reversal": {"off_low_pct": None, "range_pos": "x"},
     "band": {}, "plan": {}},
])
def test_neither_push_builder_raises_on_junk(junk):
    """A builder that throws takes the whole pass down. Every numeric read is
    guarded, NaN included."""
    assert HPA.message(junk)["kind"] == "hot_pullback_alert"
    assert PA.message({**junk, "pattern": "double_bottom"})["kind"] == "pattern_alert"


def test_pattern_message_handles_the_real_scan_row_shape():
    row = _pat()
    body = PA.message(row)["body"]
    assert "$12.5" in body and "neckline $12" in body and "target $14.1" in body


def test_pattern_alerts_read_the_scan_doc_by_id_not_by_timestamp():
    """`patterns_scan` holds TWO docs: "latest" (the scan, 200 rows) and
    "qualifier_verdicts" (always empty, and NEWER). Sorting by generated_at
    picks the empty one, and the pass would find nothing forever while looking
    like a quiet market. Caught by a dry run before the cron shipped."""
    import inspect
    assert PA.SCAN_DOC_ID == "latest"
    src = inspect.getsource(PA.check_once)
    assert 'find_one({"_id": SCAN_DOC_ID})' in src
    assert 'sort=[("generated_at"' not in src


# ── the demand gate (Ajay 2026-09-09: "on the Patterns you know the deal, we
#    need make sure they need to be in demand zone or bouncing off demand
#    zone"). It is a TIGHTENING and it FAILS CLOSED. ─────────────────────────
def test_a_confirmation_away_from_demand_never_reaches_the_phone(monkeypatch):
    """Coverage exists, the name simply is not at a level -> silence, counted
    as skipped_no_demand so the quiet is explainable."""
    sent = _capture(monkeypatch)
    out = PA.check_once(owner="o@x", rows=[_pat()], coll=FakeColl(),
                        anchors={"AAA": None})
    assert out["pushed"] == 0 and sent == []
    assert out["skipped_no_demand"] == 1 and out["skipped_no_zone"] == 0


def test_no_zone_coverage_fails_closed_and_is_counted_apart(monkeypatch):
    """A blind morning must never look like a quiet one: a name with no zone
    doc at all sends nothing and lands in its OWN counter."""
    sent = _capture(monkeypatch)
    out = PA.check_once(owner="o@x", rows=[_pat()], coll=FakeColl(),
                        anchors={}, build_zones=False)
    assert out["pushed"] == 0 and sent == []
    assert out["skipped_no_zone"] == 1 and out["skipped_no_demand"] == 0


def test_the_push_says_which_side_of_the_demand_gate_it_came_from(monkeypatch):
    sent = _capture(monkeypatch)
    PA.check_once(owner="o@x", rows=[_pat()], coll=FakeColl(), anchors=_ANCH)
    assert "\U0001F9F2 in demand $12.2-12.9" in sent[0][1]["body"]
    sent2 = _capture(monkeypatch)
    PA.check_once(owner="o@x", rows=[_pat()], coll=FakeColl(),
                  anchors={"AAA": _REVERSAL})
    body = sent2[0][1]["body"]
    assert "\U0001FA83 reversal off demand $11.4-12" in body and "+6.2%" in body


def test_the_word_bounce_is_gone_from_the_pattern_push(monkeypatch):
    """Ajay 2026-09-09: "I have trauma with that word now cuz I caught falliing
    knives with it". The wording is part of the contract, not decoration."""
    sent = _capture(monkeypatch)
    PA.check_once(owner="o@x", rows=[_pat(), _pat(sym="B")], coll=FakeColl(),
                  anchors={"AAA": _ANCH.get("AAA"), "B": _REVERSAL})
    for _kind, msg in sent:
        assert "bounc" not in (msg["title"] + msg["body"]).lower(), msg


def test_a_duplicated_scan_row_is_one_push_not_two(monkeypatch):
    """The live scan really did carry HGBL double_bottom twice on 2026-09-09.
    Mongo dedupe only spans passes; without an in-pass guard that is two
    identical pushes in one go."""
    sent = _capture(monkeypatch)
    out = PA.check_once(owner="o@x", rows=[_pat(), _pat()], coll=FakeColl(),
                        anchors=_ANCH)
    assert out["skipped_dup"] == 1 and out["pushed"] == 1 and len(sent) == 1


def test_digest_lines_say_which_side_of_the_gate_each_name_is_on():
    rows = [dict(_pat(sym="A"), demand_anchor=_ANCH.get("A")),
            dict(_pat(sym="B"), demand_anchor=_REVERSAL)]
    body = PA.digest_message(rows, "2026-09-09")["body"]
    assert "A (double bottom \u00b7 in demand)" in body
    assert "B (double bottom \u00b7 reversal)" in body


# ── the anchor read itself, against the real bounce_room ───────────────────
def _zone_doc():
    """Bands the way zone_store writes them: a demand band, a NESTED tighter
    one inside it, a broken supply shelf (top under yesterday's close) and an
    unbroken supply lid overhead."""
    return {"date": "2026-09-09", "prev_close": 12.6, "atr14": 0.25, "recent": [],
            "bands": [{"kind": "demand", "lo": 11.8, "hi": 12.6, "touches": 3},
                      {"kind": "demand", "lo": 12.1, "hi": 12.4, "touches": 2},
                      {"kind": "supply", "lo": 10.4, "hi": 11.0, "touches": 3},
                      {"kind": "supply", "lo": 14.0, "hi": 14.6, "touches": 4}]}


def test_in_demand_read_takes_the_innermost_band_and_ignores_an_unbroken_lid():
    from supply_demand import bounce_room as BR
    doc = _zone_doc()
    inz = BR.in_demand_read(12.3, doc)
    assert inz["band"]["lo"] == 12.1 and inz["band"]["hi"] == 12.4, "innermost wins"
    assert inz["role"] == "demand"
    assert BR.in_demand_read(14.2, doc) is None, "an unbroken supply lid is not demand"
    # A BROKEN supply shelf is support and counts — but only off a gap day.
    # Against this doc's 12.6 close a 10.7 print is -15%, and alert_gates.
    # gap_day then makes every shelf trapped supply (the DYN 2026-09-08 rule),
    # so the same price reads differently under a close it did not gap from.
    near = dict(doc, prev_close=11.2)
    assert BR.in_demand_read(10.7, near)["role"] == "broken_supply"
    assert BR.in_demand_read(10.7, doc) is None, "gap day: a shelf is not support"
    assert BR.in_demand_read(13.2, doc) is None, "between bands is not in a zone"
    for junk in (None, 0, -1, "x", float("nan")):
        assert BR.in_demand_read(junk, doc) is None, junk
    assert BR.in_demand_read(12.3, None) is None
    assert BR.in_demand_read(12.3, {}) is None


def test_demand_anchor_rejects_a_name_that_already_ran_past_the_band():
    """SIG on 2026-09-09 touched $78.69-81.56 and printed $102.48 — a true
    reversal by the filter's rule (no ceiling, by design) and exactly the
    "late by the time it reaches me" push this gate must not send."""
    doc = _zone_doc()
    near = PA.demand_anchor("X", doc, None, fallback_px=12.9)
    far = PA.demand_anchor("X", doc, None, fallback_px=12.6 * 1.30)
    assert (near or {}).get("state") in ("in_zone", "reversal", None)
    assert far is None, "30% above the band top is not standing at it"


def test_demand_anchor_fails_closed_on_a_missing_doc_tombstone_or_price():
    doc = _zone_doc()
    assert PA.demand_anchor("X", None, None, fallback_px=12.3) is None
    assert PA.demand_anchor("X", {}, None, fallback_px=12.3) is None
    assert PA.demand_anchor("X", {"error": "no data"}, None, fallback_px=12.3) is None
    for junk in (None, 0, -5, "n/a", float("nan"), {}):
        assert PA.demand_anchor("X", doc, None, fallback_px=junk) is None, junk


def test_anchor_txt_never_raises_and_says_nothing_when_there_is_no_anchor():
    assert PA.anchor_txt(None) == "" and PA.anchor_txt("weird") == ""
    assert PA.anchor_txt({"state": "reversal", "band": {}}) .startswith("\U0001FA83")
    assert "broken-supply shelf" in PA.anchor_txt(
        {"state": "in_zone", "role": "broken_supply",
         "band": {"lo": 10.4, "hi": 11.0}})
