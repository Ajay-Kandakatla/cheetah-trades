"""💎 growth/quality_alerts.py — the capital-quality upgrade push.

The rule under test is narrow on purpose: a DEFINITIONAL component of
`growth/capital_quality.py` crosses FAIL -> PASS on a NEW fiscal quarter.
Almost every test here is a NEGATIVE, because almost everything that looks
like an upgrade is not one:

  * `unknown -> pass` is the APP learning, not the company improving. The next
    `board_metrics` warm will make ~15 of 21 names "improve" at once for
    exactly that reason.
  * A sector-RELATIVE component can move because a PEER filed.
  * The same quarter re-read is a provider wobble, not a filing — the 🔔
    price-alert lesson, 2,022 stale re-fires.
  * A first observation is a baseline, not news.
  * A downgrade is a different alert he did not ask for.
"""
from __future__ import annotations

import pytest

from growth import capital_quality as CQ
from growth import quality_alerts as QA
from push import subs


# ── a Mongo stand-in that behaves like the four calls this module makes ──────
class FakeColl:
    """`find({_id: {$in: [...]}})`, `update_one($setOnInsert, upsert)`,
    `replace_one(upsert)`, `delete_one` — nothing else is used."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.fail_find = False

    def find(self, q, proj=None):
        if self.fail_find:
            raise RuntimeError("mongo down")
        ids = (q.get("_id") or {}).get("$in") or []
        return [dict(self.docs[i]) for i in ids if i in self.docs]

    def update_one(self, q, u, upsert=False):
        key = q["_id"]
        existed = key in self.docs
        if not existed:
            self.docs[key] = dict(u.get("$setOnInsert") or {})
        return type("R", (), {"upserted_id": None if existed else key,
                              "matched_count": 1 if existed else 0})()

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)

    def delete_one(self, q):
        self.docs.pop(q["_id"], None)


def _capture(monkeypatch, result=None, raises=False):
    """Capture pushes. `portfolio.alerts` is stubbed for the same reason
    test_new_alert_kinds stubs it: it cannot import under this venv's 3.9."""
    import sys
    import types
    sent = []
    fake = types.SimpleNamespace(_resolve_owner=lambda: "o@x")
    pkg = types.ModuleType("portfolio")
    pkg.__path__ = []
    pkg.alerts = fake
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.alerts", fake)
    from push import sender

    def _send(email, msg, kind=None):
        sent.append((kind, msg))
        if raises:
            raise RuntimeError("transport")
        return dict(result or {"sent": 1, "total_targets": 1})

    monkeypatch.setattr(sender, "send_to_user", _send)
    return sent


def _read(verdicts, period="FY2026 Q3", passed=None, answered=None, details=None):
    """A `capital_quality.for_row`-shaped read with the given verdicts."""
    details = details or {}
    comps = {k: {"verdict": v, "reason": None if v != CQ.UNKNOWN else "missing_roce",
                 "detail": details.get(k)}
             for k, v in verdicts.items()}
    for k in CQ.COMPONENT_KEYS:
        comps.setdefault(k, {"verdict": CQ.UNKNOWN, "reason": "missing_roce",
                             "detail": None})
    p = sum(1 for c in comps.values() if c["verdict"] == CQ.PASS) if passed is None else passed
    f = sum(1 for c in comps.values() if c["verdict"] == CQ.FAIL)
    return {"grade": "some", "passed": p, "failed": f,
            "answered": (p + f) if answered is None else answered,
            "unknown": 0, "rank_key": p, "components": comps,
            "period": period, "period_end": None, "measured": CQ.MEASURED}


def _row(sym="NVDA", verdicts=None, period="FY2026 Q3", warnings=None, **kw):
    return {"symbol": sym, "warnings": list(warnings or []),
            "capital_quality": _read(verdicts or {}, period=period, **kw)}


def _state(sym="NVDA", components=None, period="FY2026 Q2"):
    """A `read_state()`-shaped map: keyed by SYMBOL, for scan()."""
    return {sym: {"components": dict(components or {}), "period": period}}


def _docs(sym="NVDA", components=None, period="FY2026 Q2"):
    """A FakeColl-shaped map: keyed by `_id`, for run()."""
    return {QA._state_id(sym): {"_id": QA._state_id(sym), "symbol": sym,
                                "components": dict(components or {}),
                                "period": period}}


# ══════════════════════════════════════════════════════════ registration
def test_the_kind_is_registered_or_it_silently_targets_zero_devices():
    """A kind missing from default_prefs sends to ZERO devices AND renders no
    toggle — he could never switch it on. The 2026-06-24 chokepoint."""
    assert QA.KIND in subs.default_prefs()


def test_the_kind_ships_OFF_and_is_the_only_one_that_does():
    """He has not seen this kind fire. His 2026-09-20 'default on for any
    change of todays features' named the features that existed THAT DAY."""
    assert subs.default_prefs()[QA.KIND] is False
    off = {k for k, v in subs.default_prefs().items()
           if v is False and not k.startswith("quiet_hours")}
    # 🔑 key_level_alert (2026-09-25) is OFF in default_prefs too — ON only for
    # the owner, through OWNER_KEEP_SET (his answer).
    assert off == {QA.KIND, "key_level_alert"}, "another kind quietly shipped muted: %s" % sorted(off)


def test_NEGATIVE_the_kind_is_not_in_the_owner_keep_set():
    assert QA.KIND not in subs.OWNER_KEEP_SET
    # …and therefore comes back muted for a re-registering owner device.
    assert subs.owner_prefs()[QA.KIND] is False
    assert subs.prefs_for(subs._owner_email())[QA.KIND] is False


def test_NEGATIVE_the_keep_set_itself_did_not_move():
    """This package flips no notification pref. The keep-set is exactly these
    ten (🔑 key_level_alert joined 2026-09-25 on his own answer)."""
    assert subs.OWNER_KEEP_SET == frozenset({
        "hot_pullback_alert", "pattern_alert", "demand_alert", "position_alert",
        "potus_investment", "growth_demand_alert", "earnings_reaction",
        "board_arrival", "price_alert", "key_level_alert"})


def test_NEGATIVE_the_kind_is_not_hard_stopped():
    """Registered-but-disabled would be a toggle that can never fire."""
    assert QA.KIND not in subs.DISABLED_ALERT_KINDS


def test_it_is_a_market_kind_so_closed_days_stay_quiet():
    from market_hours import gate
    assert QA.KIND in gate.MARKET_ALERT_KINDS
    assert QA.KIND not in gate.PERSONAL_KINDS
    assert gate.should_drop_kind(QA.KIND, __import__("datetime").datetime(
        2026, 9, 7, 12, 0, tzinfo=gate._ET)) == "holiday 2026-09-07"


def test_the_digest_body_is_registered_as_a_ticker_list():
    from push import recent
    assert QA.KIND in recent.DIGEST_KINDS


def test_the_alerts_page_carries_the_pass_and_reads_the_slot_from_here():
    from supply_demand import alert_status as AS
    assert QA.KIND in AS.DAILY_PASS_KINDS and QA.KIND in AS.PASS_KINDS
    assert AS.schedule_map()[QA.KIND] == "%s ET, trading days" % QA.SLOT_ET


def test_the_schedule_MOVES_when_the_slot_moves(monkeypatch):
    """Source guard: the page must never type a minute of its own."""
    from supply_demand import alert_status as AS
    monkeypatch.setattr(QA, "SLOT_ET", "06:02")
    assert AS.schedule_map()[QA.KIND] == "06:02 ET, trading days"


def test_the_rules_panel_says_it_is_off_that_nothing_gates_it_and_not_measured():
    from supply_demand import rules_info as RI
    line = [l for l in RI.sections()["alerts"]["alerts"] if QA.KIND in l]
    assert len(line) == 1
    t = line[0]
    assert "OFF by default" in t
    assert "NOTHING GATES THIS KIND" in t
    assert CQ.MEASURED_NOTE in t
    assert QA.SLOT_ET in t
    for phrase in QA.UPGRADE_PHRASE.values():
        assert phrase in t


# ══════════════════════════════════════════════════ the component contract
def test_every_definitional_component_has_a_phrase():
    """A new definitional leg over in capital_quality must be given WORDS here
    before it can reach his phone as a raw key."""
    assert set(QA.UPGRADE_PHRASE) == set(QA._definitional_keys())


def test_NEGATIVE_only_definitional_components_can_fire():
    """A RELATIVE leg moves when a PEER files. 'Your company improved' must
    never be said because somebody else got worse."""
    relative = {k for k, kind, _l in CQ.COMPONENTS if kind == CQ.RELATIVE}
    assert relative == {"roce_above_sector", "capex_below_sector"}
    assert not (relative & set(QA._definitional_keys()))
    assert not (relative & set(QA.UPGRADE_PHRASE))


def test_the_definitional_keys_are_READ_from_capital_quality(monkeypatch):
    """Not a second hand-typed list: add a leg there, it appears here."""
    monkeypatch.setattr(CQ, "COMPONENTS", CQ.COMPONENTS + (
        ("fake_leg", CQ.DEFINITIONAL, "x"), ("fake_rel", CQ.RELATIVE, "y")))
    keys = QA._definitional_keys()
    assert "fake_leg" in keys and "fake_rel" not in keys


# ═════════════════════════════════════════════════════════════ upgrades()
def test_a_fail_to_pass_crossing_is_an_upgrade():
    assert QA.upgrades({"net_cash": CQ.FAIL}, {"net_cash": CQ.PASS}) == ["net_cash"]


@pytest.mark.parametrize("prev,now", [
    (CQ.UNKNOWN, CQ.PASS),   # the app LEARNING — the mass-fire trap
    (CQ.PASS, CQ.UNKNOWN),   # the app forgetting
    (CQ.FAIL, CQ.UNKNOWN),
    (CQ.UNKNOWN, CQ.UNKNOWN),
    (CQ.PASS, CQ.PASS),      # still good is not news
    (CQ.FAIL, CQ.FAIL),
    (CQ.PASS, CQ.FAIL),      # a DOWNGRADE — a different alert, his call
])
def test_NEGATIVE_no_other_transition_is_an_upgrade(prev, now):
    assert QA.upgrades({"net_cash": prev}, {"net_cash": now}) == []


def test_NEGATIVE_a_first_observation_never_fires():
    """'We only just started watching' must never read as 'it improved' — the
    rule sepa/board_arrival.tracking_since applies to a first cohort."""
    assert QA.upgrades(None, {"net_cash": CQ.PASS}) == []
    assert QA.upgrades({}, {"net_cash": CQ.PASS}) == []
    # a key absent from an EXISTING state doc is also a first observation
    assert QA.upgrades({"positive_fcf": CQ.PASS}, {"net_cash": CQ.PASS}) == []


def test_NEGATIVE_a_relative_component_crossing_is_not_an_upgrade():
    assert QA.upgrades({"roce_above_sector": CQ.FAIL},
                       {"roce_above_sector": CQ.PASS}) == []


def test_upgrades_are_returned_in_components_order():
    prev = {k: CQ.FAIL for k in QA._definitional_keys()}
    now = {k: CQ.PASS for k in QA._definitional_keys()}
    assert QA.upgrades(prev, now) == list(QA._definitional_keys())


# ═════════════════════════════════════════════════════════════ observed()
def test_observed_keeps_UNKNOWN_as_UNKNOWN():
    """If UNKNOWN were dropped or folded into FAIL, the next pass would read
    unknown -> pass as an upgrade. This is the hinge of the whole rule."""
    r = _read({"net_cash": CQ.UNKNOWN, "positive_fcf": CQ.PASS})
    assert QA.observed(r)["net_cash"] == CQ.UNKNOWN


def test_NEGATIVE_observed_ignores_the_relative_components():
    r = _read({"roce_above_sector": CQ.PASS, "capex_below_sector": CQ.FAIL})
    assert not (set(QA.observed(r)) & {"roce_above_sector", "capex_below_sector"})


def test_observed_survives_a_junk_read():
    assert QA.observed({}) == {} and QA.observed(None) == {}


# ═════════════════════════════════════════════════════════════════ scan()
def test_a_new_quarter_with_a_crossing_is_an_item():
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")]
    items, (counts, _rec) = QA.scan(rows, _state("NVDA", {"net_cash": CQ.FAIL}))
    assert [i["symbol"] for i in items] == ["NVDA"]
    assert items[0]["flips"] == ["net_cash"]
    assert items[0]["period"] == "FY2026 Q3" and items[0]["prev_period"] == "FY2026 Q2"
    assert counts["upgraded"] == 1


def test_NEGATIVE_the_same_quarter_never_fires_however_the_figures_moved():
    """A figure that moved without a filing behind it is a provider wobble."""
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q2")]
    items, (counts, rec) = QA.scan(rows, _state("NVDA", {"net_cash": CQ.FAIL},
                                                period="FY2026 Q2"))
    assert items == [] and counts["same_period"] == 1
    assert rec[0]["components"]["net_cash"] == CQ.PASS      # still remembered


def test_NEGATIVE_no_capital_period_never_fires():
    """Rule #7: with no as-of quarter the pass cannot tell a filing from a
    wobble. Measured 2026-09-22 this is EVERY row until board_metrics warms."""
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period=None)]
    items, (counts, rec) = QA.scan(rows, _state("NVDA", {"net_cash": CQ.FAIL}))
    assert items == [] and counts["no_capital_period"] == 1
    assert rec[0]["period"] is None


def test_NEGATIVE_a_stored_record_with_NO_PERIOD_is_a_baseline_never_a_prior():
    """THE MIRROR of `test_NEGATIVE_no_capital_period_never_fires`, and the one
    that was missing.

    That test covers NOW having no period. This covers PREV having none — which
    is the day-one state for every row on this board: measured 2026-09-22, 21 of
    21 rows answered `no_capital_period` and 0 of 485 `board_metrics` documents
    carried `capital_returns`, so the FIRST pass writes a period-less record for
    every name.

    When the metrics warm then lands, `capital_period` appears and the same warm
    re-reads cash / debt / shares. If a period-less record counted as a prior,
    a FAIL -> PASS inside ONE fiscal quarter would ring "now holds more cash
    than debt ... (was an earlier quarter)" with no filing behind it — the exact
    claim `same_period` exists to refuse, and it cannot catch this one because
    "" never equals "FY2026 Q2".
    """
    prev = {"NVDA": {"components": {"net_cash": CQ.FAIL}, "period": None}}
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q2")]
    items, (counts, rec) = QA.scan(rows, prev)
    assert items == []
    assert counts["baseline"] == 1 and counts["upgraded"] == 0
    # the verdicts are still remembered, and now WITH the quarter they came from
    assert rec[0]["components"]["net_cash"] == CQ.PASS
    assert rec[0]["period"] == "FY2026 Q2"


def test_a_period_less_baseline_still_rings_on_the_NEXT_real_quarter():
    """The refusal above must be a ONE-pass baseline, not a permanent mute: the
    record it writes carries the period, so the next genuine filing compares."""
    prev = {"NVDA": {"components": {"net_cash": CQ.FAIL}, "period": None}}
    _items, (_c, rec) = QA.scan([_row("NVDA", {"net_cash": CQ.FAIL},
                                      period="FY2026 Q2")], prev)
    state = {r["symbol"]: {"components": r["components"], "period": r["period"]}
             for r in rec}
    items, (counts, _rec) = QA.scan([_row("NVDA", {"net_cash": CQ.PASS},
                                          period="FY2026 Q3")], state)
    assert [i["symbol"] for i in items] == ["NVDA"] and counts["upgraded"] == 1


def test_NEGATIVE_it_does_not_fall_back_to_the_income_statement_period():
    """The board row carries its own `period` from the 100/100 screen. Using it
    as the as-of of a BALANCE-SHEET fact would report a date that is not the
    date the figure came from."""
    row = _row("NVDA", {"net_cash": CQ.PASS}, period=None)
    row["period"] = "FY2026 Q3"                      # the growth screen's quarter
    items, (counts, _rec) = QA.scan([row], _state("NVDA", {"net_cash": CQ.FAIL}))
    assert items == [] and counts["no_capital_period"] == 1


def test_NEGATIVE_a_first_observation_is_recorded_not_pushed():
    rows = [_row("NVDA", {"net_cash": CQ.PASS})]
    items, (counts, rec) = QA.scan(rows, {})
    assert items == [] and counts["baseline"] == 1
    assert rec[0]["components"]["net_cash"] == CQ.PASS


def test_NEGATIVE_a_row_with_no_quality_read_is_counted_not_crashed():
    items, (counts, rec) = QA.scan([{"symbol": "X"}, None, {"capital_quality": {}}], {})
    assert items == [] and counts["ungraded"] == 3 and rec == []


def test_no_crossing_is_counted_and_still_recorded():
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")]
    items, (counts, rec) = QA.scan(rows, _state("NVDA", {"net_cash": CQ.PASS}))
    assert items == [] and counts["no_upgrade"] == 1 and rec[0]["period"] == "FY2026 Q3"


def test_items_are_ordered_by_crossings_then_alphabetically_not_by_a_rank():
    rows = [_row("ZZZ", {"net_cash": CQ.PASS}, period="Q3"),
            _row("AAA", {"net_cash": CQ.PASS}, period="Q3"),
            _row("MMM", {"net_cash": CQ.PASS, "positive_fcf": CQ.PASS}, period="Q3")]
    state = {}
    for s in ("ZZZ", "AAA", "MMM"):
        state.update(_state(s, {"net_cash": CQ.FAIL, "positive_fcf": CQ.FAIL}, period="Q2"))
    items, _c = QA.scan(rows, state)
    assert [i["symbol"] for i in items] == ["MMM", "AAA", "ZZZ"]


# ════════════════════════════════════════════════════════════ read_state()
def test_NEGATIVE_a_failed_state_read_means_silence_not_a_false_upgrade():
    """The opposite failure side from growth.alerts._seen: there a lost read
    costs a duplicate, here it would cost a FALSE claim that a company
    improved. So it costs silence — everything reads as a baseline."""
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    coll.fail_find = True
    assert QA.read_state(coll, ["NVDA"]) == {}
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")]
    items, (counts, _r) = QA.scan(rows, QA.read_state(coll, ["NVDA"]))
    assert items == [] and counts["baseline"] == 1


def test_read_state_with_no_collection_is_empty():
    assert QA.read_state(None, ["NVDA"]) == {} and QA.read_state(FakeColl(), []) == {}


# ═══════════════════════════════════════════════════════════════ message()
def test_the_body_carries_the_period_the_prior_period_and_the_measured_note():
    item = {"symbol": "NVDA", "flips": ["net_cash"], "period": "FY2027 Q2",
            "prev_period": "FY2027 Q1", "row": {"warnings": []},
            "read": _read({"net_cash": CQ.PASS}, details={"net_cash": "cash > debt"})}
    m = QA.message(item)
    assert m["kind"] == QA.KIND and m["ticker"] == "NVDA" and m["tickers"] == ["NVDA"]
    assert "FY2027 Q2" in m["body"] and "FY2027 Q1" in m["body"]
    assert "cash > debt" in m["body"]
    assert CQ.MEASURED_NOTE in m["body"]
    assert QA.NOT_A_RECOMMENDATION in m["body"]
    assert m["data"]["measured"] is False
    assert "NVDA" in m["url"]


def test_the_measured_note_is_READ_from_capital_quality(monkeypatch):
    """Not retyped — change it there, the phone changes with it."""
    monkeypatch.setattr(CQ, "MEASURED_NOTE", "MOVED NOTE")
    item = {"symbol": "X", "flips": ["net_cash"], "period": "Q2", "prev_period": "Q1",
            "row": {}, "read": _read({"net_cash": CQ.PASS})}
    assert "MOVED NOTE" in QA.message(item)["body"]


def test_a_refused_name_says_so_in_the_body_rather_than_silently():
    item = {"symbol": "FF", "flips": ["net_cash"], "period": "Q2", "prev_period": "Q1",
            "row": {"warnings": ["⛔ under $2 — the engine will refuse it"]},
            "read": _read({"net_cash": CQ.PASS})}
    assert "⛔ under $2" in QA.message(item)["body"]


def test_multiple_crossings_ride_one_push():
    item = {"symbol": "X", "flips": ["net_cash", "positive_fcf"], "period": "Q2",
            "prev_period": "Q1", "row": {},
            "read": _read({"net_cash": CQ.PASS, "positive_fcf": CQ.PASS})}
    m = QA.message(item)
    assert "+1 more" in m["title"]
    assert QA.UPGRADE_PHRASE["positive_fcf"] in m["body"]


def test_NEGATIVE_no_surface_word_he_reads_says_bounce():
    """Every surface he reads says 'reversal', never 'bounce' — standing."""
    item = {"symbol": "X", "flips": ["net_cash"], "period": "Q2", "prev_period": "Q1",
            "row": {}, "read": _read({"net_cash": CQ.PASS})}
    m = QA.message(item)
    blob = (m["title"] + m["body"] + " ".join(QA.UPGRADE_PHRASE.values())
            + QA.NOT_A_RECOMMENDATION).lower()
    assert "bounce" not in blob


def test_the_digest_lists_every_name_and_keeps_the_note():
    items = [{"symbol": "A", "flips": ["net_cash"]},
             {"symbol": "B", "flips": ["positive_fcf"]}]
    d = QA.digest_message(items)
    assert d["tickers"] == ["A", "B"] and "A (" in d["body"] and "B (" in d["body"]
    assert CQ.MEASURED_NOTE in d["body"] and d["ticker"] is None


# ══════════════════════════════════════════════════════════════════ run()
def _wet(monkeypatch, rows, coll, **kw):
    """One wet pass with the /alerts recorder stubbed.

    `run()` does `from supply_demand import alert_status` — an ATTRIBUTE lookup
    on an already-imported package, which `sys.modules` patching never reaches.
    The function itself is patched instead."""
    from supply_demand import alert_status as AS
    monkeypatch.setattr(AS, "record_result", lambda *a, **k: True)
    return QA.run(board_rows=rows, coll=coll, **kw)


def test_a_wet_pass_sends_claims_and_records_the_new_state(monkeypatch):
    sent = _capture(monkeypatch)
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    out = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert out["individual"] == 1 and out["upgraded"] == 1 and len(sent) == 1
    assert sent[0][0] == QA.KIND
    assert coll.docs[QA._claim_id("NVDA", "FY2026 Q3")]["flips"] == ["net_cash"]
    assert coll.docs[QA._state_id("NVDA")]["period"] == "FY2026 Q3"
    assert coll.docs[QA._state_id("NVDA")]["components"]["net_cash"] == CQ.PASS


def test_NEGATIVE_the_second_pass_on_the_same_quarter_sends_nothing(monkeypatch):
    """The latch. The 🔔 price-alert kind re-fired 2,022 times, every one of
    them sent=0, because a state with no latch re-asserts itself every pass."""
    sent = _capture(monkeypatch)
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")]
    _wet(monkeypatch, rows, coll)
    out2 = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert len(sent) == 1, "it rang twice for one quarter"
    # The stored state now carries FY2026 Q3, so the second pass never even
    # reaches the crossing test — it stops at the period guard. Two independent
    # latches (the period, then the per-quarter claim) and the outer one wins.
    assert out2["individual"] == 0 and out2["same_period"] == 1


def test_NEGATIVE_the_claim_survives_even_if_the_state_doc_is_lost(monkeypatch):
    """Belt and braces: wipe the state, the per-quarter claim still refuses."""
    sent = _capture(monkeypatch)
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    rows = [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")]
    _wet(monkeypatch, rows, coll)
    coll.docs[QA._state_id("NVDA")] = {"_id": QA._state_id("NVDA"), "symbol": "NVDA",
                                       "components": {"net_cash": CQ.FAIL},
                                       "period": "FY2026 Q2"}
    out = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert len(sent) == 1 and out["claimed_elsewhere"] == 1 and out["individual"] == 0


def test_NEGATIVE_a_transport_failure_releases_the_claim_and_keeps_the_old_state(monkeypatch):
    """Recording the new verdicts before a confirmed delivery is how a real
    upgrade gets swallowed forever."""
    _capture(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    out = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert out["individual"] == 0 and out["retry_pending"] == 1
    assert QA._claim_id("NVDA", "FY2026 Q3") not in coll.docs
    assert coll.docs[QA._state_id("NVDA")]["components"]["net_cash"] == CQ.FAIL
    # …and the next pass finds the identical crossing again.
    sent = _capture(monkeypatch)
    out2 = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert out2["individual"] == 1 and len(sent) == 1


def test_NEGATIVE_a_send_that_RAISES_also_retries(monkeypatch):
    _capture(monkeypatch, raises=True)
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    out = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert out["retry_pending"] == 1 and out["individual"] == 0
    assert coll.docs[QA._state_id("NVDA")]["components"]["net_cash"] == CQ.FAIL


def test_NEGATIVE_a_closed_day_drop_is_not_terminal(monkeypatch):
    """This claim is per QUARTER, so keeping it over a push that never left the
    building would mute the name for three months."""
    assert QA._terminal({"skipped": "weekend", "sent": 0, "total_targets": 0}) is False
    _capture(monkeypatch, result={"skipped": "weekend", "sent": 0, "total_targets": 0})
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    out = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert out["retry_pending"] == 1
    assert QA._claim_id("NVDA", "FY2026 Q3") not in coll.docs


def test_nobody_targeted_is_terminal_because_the_kind_ships_off(monkeypatch):
    """With the pref off the sender reports 0 targets. That is a FACT, not a
    failure: the claim stands and the quarter is not re-attempted daily."""
    _capture(monkeypatch, result={"sent": 0, "total_targets": 0})
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    out = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="FY2026 Q3")], coll)
    assert out["individual"] == 1 and out["retry_pending"] == 0
    assert QA._claim_id("NVDA", "FY2026 Q3") in coll.docs


def test_the_spill_past_MAX_INDIVIDUAL_shares_one_digest(monkeypatch):
    sent = _capture(monkeypatch)
    n = QA.MAX_INDIVIDUAL + 2
    syms = ["S%02d" % i for i in range(n)]
    rows = [_row(s, {"net_cash": CQ.PASS}, period="Q3") for s in syms]
    docs = {}
    for s in syms:
        docs.update(_docs(s, {"net_cash": CQ.FAIL}, period="Q2"))
    out = _wet(monkeypatch, rows, FakeColl(docs))
    assert out["individual"] == QA.MAX_INDIVIDUAL and out["digest"] == 2
    assert len(sent) == QA.MAX_INDIVIDUAL + 1
    assert sent[-1][1]["ticker"] is None and len(sent[-1][1]["tickers"]) == 2


def test_NEGATIVE_a_dry_run_writes_nothing_but_still_READS_the_state(monkeypatch):
    sent = _capture(monkeypatch)
    coll = FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}))
    before = dict(coll.docs)
    out = QA.run(dry_run=True, board_rows=[_row("NVDA", {"net_cash": CQ.PASS},
                                                period="FY2026 Q3")], coll=coll)
    assert sent == [] and coll.docs == before
    assert out["dry_run"] is True and out["individual"] == 1   # what a wet pass WOULD send
    assert out["upgraded"] == 1                                # the READ happened


def test_NEGATIVE_the_summary_borrows_no_zone_gate_counter(monkeypatch):
    """Alerts.tsx sums these six names over EVERY recorded pass — a counter
    borrowing one would silently pollute the S/D gate aggregate on /alerts."""
    _capture(monkeypatch)
    out = _wet(monkeypatch, [_row("NVDA", {"net_cash": CQ.PASS}, period="Q3")],
               FakeColl(_docs("NVDA", {"net_cash": CQ.FAIL}, period="Q2")))
    for forbidden in ("skipped_room", "skipped_proximity", "skipped_direction",
                      "skipped_knife", "skipped_mood", "skipped_floor"):
        assert forbidden not in out, forbidden


def test_the_summary_says_it_is_not_measured(monkeypatch):
    _capture(monkeypatch)
    out = _wet(monkeypatch, [], FakeColl())
    assert out["measured"] is False and out["kind"] == QA.KIND and out["ran"] is True


def test_the_pass_is_recorded_for_the_alerts_page(monkeypatch):
    from supply_demand import alert_status as AS
    seen = []
    _capture(monkeypatch)
    monkeypatch.setattr(AS, "record_result",
                        lambda kind, summary, now=None: seen.append((kind, summary)))
    QA.run(board_rows=[], coll=FakeColl())
    assert seen and seen[0][0] == QA.KIND
    assert seen[0][1]["ran"] is True


# ════════════════════════════════════════════════════════════════ rows()
def test_capital_quality_is_attached_AFTER_board_metrics(monkeypatch):
    """Reversed, every component answers UNKNOWN and this pass goes silent
    forever while looking perfectly healthy."""
    order = []
    from sepa import board_metrics as BM
    monkeypatch.setattr(BM, "attach", lambda rows, *a, **k: order.append("metrics"))
    monkeypatch.setattr(CQ, "attach", lambda rows, *a, **k: order.append("quality"))
    QA.rows({"rows": [{"symbol": "NVDA"}]})
    assert order == ["metrics", "quality"]


def test_a_failing_attach_does_not_take_the_pass_down(monkeypatch):
    from sepa import board_metrics as BM

    def boom(*a, **k):
        raise RuntimeError("cold cache")

    monkeypatch.setattr(BM, "attach", boom)
    monkeypatch.setattr(CQ, "attach", boom)
    assert QA.rows({"rows": [{"symbol": "NVDA"}]}) == [{"symbol": "NVDA"}]


# ═══════════════════════════════════════════════════════════════════ CLI
def test_the_cron_entry_point_exists_and_is_dry_runnable(monkeypatch):
    called = {}
    monkeypatch.setattr(QA, "run", lambda dry_run=False: called.setdefault("dry", dry_run) or {})
    from growth import __main__ as M
    assert M.main(["quality", "--dry-run"]) == 0
    assert called["dry"] is True
