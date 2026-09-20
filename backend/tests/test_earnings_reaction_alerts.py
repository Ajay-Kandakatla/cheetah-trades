"""📣 earnings_reaction — the push the Earnings Flow tab never sent.

Ajay 2026-09-20: *"Also don't forget to alert me on earnings surprises I think
stock witz also has it. I wanna make sure we are catching those in alerts as
well."* And, the same day: *"Default on for any change of todays features
Bondes or Potus or explosive growth or Earnings I wanna see all of them."*

    .venv/bin/python -m pytest tests/test_earnings_reaction_alerts.py -q

The negatives are the point of this file. Every one of them is a way the
2026-09-20 critique showed this pass could push the WRONG bar or read a
provider outage as a quiet tape:

  * an AMC reporter's PRE-report bar (the ATEX/BULL shape the tab exists to
    keep separate) — refused by the reaction-date match;
  * a BMO reporter's next-day drift bar — same rule, other direction;
  * the PRIOR quarter's surprise, which the calendar doc still carries until
    the 17:45 refresh rolls it;
  * a yfinance fallback that looks exactly like "the number is not out yet";
  * a price cache whose last bar is not the session this slot expects.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import earnings as E                     # noqa: E402
from chart_maps import earnings_alerts as EA             # noqa: E402
from growth import alerts as GA                          # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]

# The Friday the last closed bar was when this shipped.
FRI = "2026-09-18"
THU = "2026-09-17"
MON = "2026-09-21"
EVENING = datetime(2026, 9, 18, 17, 35, tzinfo=ET)
MORNING = datetime(2026, 9, 21, 8, 25, tzinfo=ET)


# ── fixtures: a frame, a scored bar, a REACTED row ──────────────────────────
def _frame(end: str = FRI, n: int = 200, last_volume: float = 3_000_000.0) -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=n)
    close = [100.0] * n
    df = pd.DataFrame({"open": [99.0] * n, "high": [101.0] * n, "low": [98.0] * n,
                       "close": close, "volume": [1_000_000.0] * n}, index=idx)
    df.iloc[-1, df.columns.get_loc("volume")] = last_volume
    return df


def _row(symbol="AAA", report_date=THU, when="AMC", date=FRI, dollar_vol=412_000_000.0,
         surprise_pct=6.16, change_pct=8.4, vol_ratio=3.1, close_loc=0.88):
    """The shape `chart_maps.earnings.scan()` puts in `reacted`: the calendar
    fields plus `bar_metrics` merged in."""
    return {"symbol": symbol, "phase": E.REACTED, "report_date": report_date, "when": when,
            "surprise_pct": surprise_pct, "drift_since_pct": 0.0, "still_above_pre": True,
            "date": date, "open": 98.0, "high": 112.0, "low": 96.0, "close": 110.0,
            "volume": 3_000_000.0, "prev_close": 101.5, "vol_ratio": vol_ratio,
            "close_loc": close_loc, "dollar_vol": dollar_vol, "change_pct": change_pct,
            "range_pct": 16.6, "gap_pct": -3.4}


def _lr(date=THU, when="AMC", eps_actual=1.05, eps_estimate=0.99, surprise_pct=6.16):
    return {"date": date, "when": when, "eps_actual": eps_actual,
            "eps_estimate": eps_estimate, "surprise_pct": surprise_pct}


def _res(reacted=None, upcoming=None, **counts):
    out = {"reacted": list(reacted or []), "upcoming": list(upcoming or []),
           "as_of": FRI, "checked": 1, "skipped": 0, "calendar_names": 3,
           "reacted_seen": len(reacted or []), "reacted_not_institutional": 0,
           "dropped_not_last_bar": 0}
    out.update(counts)
    return out


class FakeColl:
    """The dedupe collection: `_id` upserts, and every write is recorded."""

    def __init__(self, seeded=()):
        self.docs = {k: {"_id": k} for k in seeded}
        self.writes, self.deletes = [], []

    def find(self, q, _proj=None):
        ids = (q.get("_id") or {}).get("$in") or []
        return [self.docs[i] for i in ids if i in self.docs]

    def update_one(self, flt, update, upsert=False):
        key = flt["_id"]
        self.writes.append(key)
        existed = key in self.docs
        if not existed:
            self.docs[key] = dict(update.get("$setOnInsert") or {}, _id=key)
        return type("R", (), {"upserted_id": None if existed else key,
                              "matched_count": 1 if existed else 0})()

    def delete_one(self, flt):
        self.deletes.append(flt["_id"])
        self.docs.pop(flt["_id"], None)


class Sender:
    def __init__(self, result=None, raise_on=None):
        self.calls, self.result, self.raise_on = [], result or {"sent": 1}, raise_on

    def send_to_user(self, owner, payload, kind=None):
        self.calls.append({"owner": owner, "payload": payload, "kind": kind})
        if self.raise_on and self.raise_on(payload):
            raise RuntimeError("transport down")
        return self.result


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """No test in this file may reach Mongo, yfinance or the price cache."""
    monkeypatch.setattr(EA, "_db", lambda: None)
    monkeypatch.setattr(EA, "_frame_for", lambda sym: _frame())
    monkeypatch.setattr(EA.EW, "_fetch_next", lambda sym: pytest.fail("un-injected fetch"))
    monkeypatch.setattr(EA, "_bands_for", lambda sym: [])


def _run(monkeypatch, *, rows=None, upcoming=None, doc_reports=None, fetch=None,
         coll=None, sender=None, now=EVENING, dry_run=False, force=True, bands=None, **kw):
    sender = sender or Sender()
    import push
    monkeypatch.setattr(push, "sender", sender)
    frames = {r["symbol"]: _frame(end=r["date"]) for r in (rows or [])}
    if bands is None:
        bands = {r["symbol"]: [] for r in (rows or [])}
    return EA.run(dry_run=dry_run, force=force, now=now, coll=coll if coll is not None else FakeColl(),
                  scan_result=_res(rows, upcoming), doc_reports=doc_reports or {},
                  fetch=fetch or (lambda s: {"when": "AMC", "last_report": _lr()}),
                  frames=frames, bands=bands, **kw), sender


# ── the slots and the ON-by-default registration ────────────────────────────
def test_the_two_slots_are_the_ones_the_calendar_traps_allow():
    """17:35 is before the 17:45 refresh that rolls an AMC reporter to
    UPCOMING; 08:25 is before any bar for today exists. Move either and the
    pass reads a rolled doc or a partial bar."""
    assert EA.SLOTS_ET == ("08:25", "17:35")
    assert EA.KIND == "earnings_reaction" and EA.STATE_COLL == "earnings_reaction_state"


def test_the_kind_is_registered_and_ships_ON():
    """Ajay 2026-09-20: "Default on for any change of todays features Bondes or
    Potus or explosive growth or Earnings I wanna see all of them.\""""
    from push import subs
    prefs = subs.default_prefs()
    assert EA.KIND in prefs and prefs[EA.KIND] is True
    assert EA.KIND in subs.OWNER_KEEP_SET
    assert subs.owner_prefs()[EA.KIND] is True
    assert EA.KIND not in subs.DISABLED_ALERT_KINDS


def test_it_is_a_MARKET_kind_so_a_closed_day_stays_silent():
    """It scores a CLOSED reaction bar; on a holiday that bar is stale."""
    from market_hours import gate
    assert EA.KIND in gate.MARKET_ALERT_KINDS
    assert EA.KIND not in gate.PERSONAL_KINDS
    labor_day = datetime(2026, 9, 7, 17, 35, tzinfo=ET)
    assert gate.should_drop_kind(EA.KIND, labor_day) == "holiday 2026-09-07"


def test_a_subscription_is_targeted_only_where_the_pref_is_True(monkeypatch):
    from push import subs

    class FakeSubs:
        def __init__(self, rows): self.rows = rows

        def find(self, q):
            def ok(r):
                for k, v in q.items():
                    if k == "kind":
                        continue
                    cur = r
                    for part in k.split("."):
                        cur = (cur or {}).get(part) if isinstance(cur, dict) else None
                    if cur != v:
                        return False
                return True
            return [r for r in self.rows if ok(r)]

    rows = [{"user_email": "a@x", "prefs": {EA.KIND: False}},
            {"user_email": "b@x", "prefs": {}},
            {"user_email": "c@x", "prefs": {EA.KIND: True}}]
    db = type("DB", (), {"push_subscriptions": FakeSubs(rows)})()
    monkeypatch.setattr(subs, "_get_db", lambda: db)
    monkeypatch.setattr(subs, "_backfill", lambda _db: None)
    got = subs.list_subscriptions(filter_kind=EA.KIND, honor_quiet_hours=False)
    assert [r["user_email"] for r in got] == ["c@x"]


# ── surprise_for: the reaction-date match (critique F1 + F7) ────────────────
def test_a_this_report_beat_scored_on_its_own_reaction_bar_is_ok():
    s, status = EA.surprise_for(_row(), _lr(), _row(), frame=_frame())
    assert (s, status) == (6.16, "ok")


def test_a_confirmed_date_one_day_off_the_estimate_still_pushes():
    """NEGATIVE of the first draft's rule: `last_report.date == report_date`
    never comes true when yfinance moves a confirmed date by a day, and the
    kind would have been permanently silent (critique F7)."""
    row = _row(report_date="2026-09-16", when="AMC", date=FRI)
    s, status = EA.surprise_for(row, _lr(date=THU, when="AMC"), row, frame=_frame())
    assert (s, status) == (6.16, "ok")


def test_the_PRIOR_quarters_report_is_pending_never_a_push():
    """The calendar doc carries the prior quarter until the 17:45 refresh. The
    tab prints it; this pass must not."""
    row = _row()
    s, status = EA.surprise_for(row, _lr(date="2026-06-18"), row, frame=_frame())
    assert (s, status) == (None, "pending")


def test_an_AMC_reporter_scored_on_the_REPORT_day_bar_is_refused():
    """The exact false push the critique traced: `when` None on the doc made
    an AMC name anchor like BMO, so the bar that traded BEFORE the numbers
    would have pushed as "reacted UP" — and burned the dedupe key the real
    reaction needed."""
    row = _row(report_date=THU, when=None, date=THU)       # scored on the report day
    s, status = EA.surprise_for(row, _lr(date=THU, when="AMC"), row, frame=_frame())
    assert (s, status) == (None, "pending")


def test_a_BMO_reporter_scored_on_the_NEXT_day_bar_is_refused():
    """The drift bar is not the reaction bar."""
    row = _row(report_date=THU, when="BMO", date=FRI)
    s, status = EA.surprise_for(row, _lr(date=THU, when="BMO"), row, frame=_frame())
    assert (s, status) == (None, "pending")


def test_no_timing_on_the_FRESH_read_is_never_guessed():
    row = _row()
    assert EA.surprise_for(row, _lr(when=None), row, frame=_frame()) == (None, "timing_unknown")


def test_a_null_or_NaN_surprise_is_no_surprise_not_a_beat():
    row = _row()
    assert EA.surprise_for(row, _lr(surprise_pct=None), row, frame=_frame())[1] == "no_surprise"
    assert EA.surprise_for(row, _lr(surprise_pct=float("nan")), row,
                           frame=_frame())[1] == "no_surprise"


def test_a_miss_and_an_in_line_print_are_both_not_a_beat():
    row = _row()
    assert EA.surprise_for(row, _lr(surprise_pct=-3.0), row, frame=_frame())[1] == "not_a_beat"
    assert EA.surprise_for(row, _lr(surprise_pct=0.0), row, frame=_frame())[1] == "not_a_beat"


def test_a_missing_report_or_a_missing_frame_is_pending():
    row = _row()
    assert EA.surprise_for(row, None, row, frame=_frame()) == (None, "pending")
    assert EA.surprise_for(row, _lr(), row, frame=None) == (None, "pending")


def test_the_unit_is_PERCENT_and_nothing_here_rescales():
    """REGRESSION: the tree's other surprise reader served a FRACTION until
    2026-09-20. 6.16 means +6.16%; a fraction-shaped 0.0616 is a +0.06% beat
    and prints as one — it is NOT silently multiplied."""
    row = _row()
    assert EA.surprise_for(row, _lr(surprise_pct=6.16), row, frame=_frame())[0] == 6.16
    ctx = {"room": None, "room_ok": True, "hit": None, "band": None, "enterable": None}
    assert "beat by +6.2%" in EA.message(row, _lr(), ctx, 6.16)["title"]
    assert "beat by +0.1%" in EA.message(row, _lr(surprise_pct=0.0616), ctx, 0.0616)["title"]


# ── this_quarter_report: doc, fetched, fetch_failed (critique F3) ───────────
def test_a_doc_that_already_describes_this_report_costs_no_fetch():
    lr, status = EA.this_quarter_report(_row(), _lr(),
                                        fetch=lambda s: pytest.fail("fetched anyway"))
    assert status == "doc" and lr["surprise_pct"] == 6.16


def test_a_stale_doc_triggers_ONE_read_only_fetch():
    seen = []

    def fetch(sym):
        seen.append(sym)
        return {"when": "AMC", "last_report": _lr()}

    lr, status = EA.this_quarter_report(_row(), _lr(date="2026-06-18"), fetch=fetch)
    assert status == "fetched" and lr["date"] == THU and seen == ["AAA"]


def test_a_dead_fetch_is_fetch_failed_not_pending(monkeypatch):
    """NEGATIVE (critique F3): 1,636 of 2,071 docs came back on the
    `Ticker.calendar` fallback on 2026-09-18. "The provider went dark" and
    "the number is not published yet" must not render as the same count."""
    monkeypatch.setattr(EA, "FETCH_RETRY_SLEEP_SEC", 0)
    calls = []

    def dead(sym):
        calls.append(sym)
        return None

    lr, status = EA.this_quarter_report(_row(), None, fetch=dead)
    assert (lr, status) == (None, "fetch_failed")
    assert len(calls) == EA.FETCH_RETRIES + 1, "one retry, then give up"


def test_the_calendar_FALLBACK_shape_counts_as_a_failed_fetch(monkeypatch):
    monkeypatch.setattr(EA, "FETCH_RETRY_SLEEP_SEC", 0)
    fallback = {"next_date": MON, "when": None, "eps_estimate": None, "last_report": None}
    assert EA.this_quarter_report(_row(), None, fetch=lambda s: fallback)[1] == "fetch_failed"


def test_a_real_answer_with_no_past_report_is_NOT_a_failed_fetch(monkeypatch):
    """`when` present means yfinance answered; there is simply no past report
    yet. That is `pending`, and the morning slot retries it."""
    monkeypatch.setattr(EA, "FETCH_RETRY_SLEEP_SEC", 0)
    res = {"next_date": MON, "when": "AMC", "eps_estimate": 1.0, "last_report": None}
    assert EA.this_quarter_report(_row(), None, fetch=lambda s: res) == (None, "fetched")


def test_the_fetch_path_never_writes_the_calendar():
    """A write would roll `next_date` and delete the name from the tab's
    REACTED half the same hour (the roll trap)."""
    writes = []

    class Spy:
        def replace_one(self, *a, **k): writes.append("replace")
        def update_one(self, *a, **k): writes.append("update")
        def bulk_write(self, *a, **k): writes.append("bulk")

    EA.this_quarter_report(_row(), None, fetch=lambda s: {"when": "AMC", "last_report": _lr()})
    assert writes == []
    import inspect
    src = inspect.getsource(EA.this_quarter_report)
    for bad in ("replace_one", "update_one", "bulk_write", "refresh("):
        assert bad not in src, bad
    _ = Spy()


# ── the body ────────────────────────────────────────────────────────────────
def _msg(**kw):
    ctx = kw.pop("ctx", {"room": None, "room_ok": True, "hit": None, "band": None,
                         "enterable": None})
    return EA.message(_row(**kw), _lr(), ctx, 6.16)


def test_the_body_carries_every_number_the_bar_was_judged_on():
    m = _msg()
    assert m["title"] == ("📣 AAA beat by +6.2%% — reacted UP +8.4%% on 3.1× volume (%s)" % FRI)
    b = m["body"]
    assert "EPS 1.05 vs 0.99 est" in b
    assert "reported %s AMC" % THU in b
    assert "reaction +8.4% on 3.1× median volume, $412M traded" in b
    assert "closed in the top 40% of the range (loc 0.88)" in b
    assert "gap -3.4%" in b
    assert m["ticker"] == "AAA" and m["kind"] == EA.KIND
    assert m["url"] == "/chart-maps?tab=earnings&symbol=AAA"
    assert "enterable" in m


def test_the_title_carries_the_REACTION_DATE_in_both_slots():
    """NEGATIVE (critique F9): the 08:25 push lands after an overnight move,
    so a title that said "reacted UP" with no date would read as today."""
    assert "(%s)" % FRI in _msg()["title"]
    assert "(%s)" % THU in _msg(date=THU, report_date="2026-09-16")["title"]


def test_the_body_says_what_it_is_and_what_it_is_not():
    b = _msg()["body"]
    assert "NOT measured" in b and "not a recommendation" in b
    assert "event notice" in b
    for word in ("buy now", "should buy", "add here"):
        assert word not in b.lower()


def test_no_surface_he_reads_says_bounce():
    m = _msg()
    assert "bounce" not in m["title"].lower() and "bounce" not in m["body"].lower()


def test_the_closing_line_is_BUILT_from_the_gate_constants(monkeypatch):
    """SOURCE GUARD: move the constant, move the words. A retyped 1.5× would
    keep telling him the old rule after the gate changed."""
    before = _msg()["body"]
    assert "(1.5× median vol · close in top 40% · ≥ $50M)" in before
    monkeypatch.setattr(E, "MIN_VOL_RATIO", 2.4)
    monkeypatch.setattr(E, "MIN_CLOSE_LOC", 0.75)
    after = _msg()["body"]
    assert "(2.4× median vol · close in top 25% · ≥ $50M)" in after


def test_the_body_names_the_demand_read_without_letting_it_gate():
    band = {"lo": 100.0, "hi": 112.0, "kind": "demand", "touches": 3}
    ctx = {"room": None, "room_ok": True, "band": band, "hit": {"state": "in"},
           "enterable": None}
    assert "in demand $100–112" in EA.message(_row(), _lr(), ctx, 6.16)["body"]
    ctx2 = dict(ctx, hit={"state": "above", "dist_pct": 0.7})
    assert "0.7% above demand $100–112" in EA.message(_row(), _lr(), ctx2, 6.16)["body"]
    empty = {"room": None, "room_ok": None, "band": None, "hit": None, "enterable": None}
    assert "zone read unavailable" in EA.message(_row(), _lr(), empty, 6.16)["body"]


def test_the_digest_lists_every_name_and_carries_the_ticker_list():
    items = [{"row": _row("AAA", change_pct=8.4), "surprise_pct": 6.16},
             {"row": _row("BBB", change_pct=4.2), "surprise_pct": 12.0}]
    d = EA.digest_message(items)
    assert d["title"] == "📣 2 earnings beats with institutional buying"
    assert d["body"] == "AAA +6.2% beat / +8.4% · BBB +12.0% beat / +4.2%"
    assert d["tickers"] == ["AAA", "BBB"] and d["ticker"] is None
    assert d["url"] == "/chart-maps?tab=earnings" and d["kind"] == EA.KIND


# ── the pass ────────────────────────────────────────────────────────────────
def test_a_this_quarter_beat_pushes_once_and_claims_its_key(monkeypatch):
    coll = FakeColl()
    out, sender = _run(monkeypatch, rows=[_row()], coll=coll,
                       doc_reports={"AAA": _lr()})
    assert out["ran"] is True and out["candidates"] == 1 and out["individual"] == 1
    assert out["slot"] == "evening" and out["date"] == FRI
    assert coll.writes == ["AAA|%s" % THU] and coll.deletes == []
    assert sender.calls[0]["kind"] == EA.KIND and sender.calls[0]["owner"] == GA.OWNER
    assert "beat by +6.2%" in sender.calls[0]["payload"]["title"]


def test_a_second_pass_the_same_evening_sends_nothing(monkeypatch):
    coll = FakeColl(seeded=["AAA|%s" % THU])
    out, sender = _run(monkeypatch, rows=[_row()], coll=coll, doc_reports={"AAA": _lr()})
    assert out["candidates"] == 1 and out["fresh"] == 0 and sender.calls == []


def test_next_quarters_report_is_a_NEW_key_and_pushes(monkeypatch):
    coll = FakeColl(seeded=["AAA|%s" % THU])
    row = _row(report_date="2026-12-17", date="2026-12-18")
    out, sender = _run(monkeypatch, rows=[row], coll=coll,
                       now=datetime(2026, 12, 18, 17, 35, tzinfo=ET),
                       doc_reports={"AAA": _lr(date="2026-12-17")})
    assert out["fresh"] == 1 and len(sender.calls) == 1
    assert coll.writes == ["AAA|2026-12-17"]


def test_the_spill_over_MAX_INDIVIDUAL_rides_ONE_digest(monkeypatch):
    rows = [_row("S%d" % i, dollar_vol=(10 - i) * 1e8) for i in range(GA.MAX_INDIVIDUAL + 3)]
    docs = {r["symbol"]: _lr() for r in rows}
    out, sender = _run(monkeypatch, rows=rows, doc_reports=docs)
    assert out["individual"] == GA.MAX_INDIVIDUAL and out["digest"] == 3
    singles = [c["payload"]["ticker"] for c in sender.calls[:GA.MAX_INDIVIDUAL]]
    assert singles == ["S0", "S1", "S2", "S3"], "scan()'s dollar-volume order is kept"
    assert len(sender.calls) == GA.MAX_INDIVIDUAL + 1
    assert sender.calls[-1]["payload"]["tickers"] == ["S4", "S5", "S6"]


def test_UPCOMING_rows_are_never_iterated(monkeypatch):
    """The ATEX/BULL case: a pre-report run-up is a binary event still ahead,
    and this kind is about a print that already landed."""
    up = [{"symbol": "BULL", "phase": E.UPCOMING, "report_date": FRI, "when": "AMC"}]
    out, sender = _run(monkeypatch, rows=[_row()], upcoming=up, doc_reports={"AAA": _lr()})
    assert out["upcoming_ignored"] == 1
    assert [c["payload"]["ticker"] for c in sender.calls] == ["AAA"]


def test_every_skip_is_counted_and_none_of_them_claims_a_key(monkeypatch):
    """A claim on a skip would mute the name for the quarter — the morning slot
    could never retry a surprise that published late."""
    rows = [_row("PEND"), _row("NULLS"), _row("MISS"), _row("TIME")]
    fetched = {"PEND": _lr(date="2026-06-18"), "NULLS": _lr(surprise_pct=None),
               "MISS": _lr(surprise_pct=-3.0), "TIME": _lr(when=None)}
    coll = FakeColl()
    out, sender = _run(monkeypatch, rows=rows, coll=coll, doc_reports={},
                       fetch=lambda s: {"when": "AMC", "last_report": fetched[s]})
    assert out["skipped_surprise_pending"] == 1
    assert out["skipped_no_surprise"] == 1
    assert out["skipped_not_a_beat"] == 1
    assert out["skipped_timing_unknown"] == 1
    assert out["candidates"] == 0 and sender.calls == [] and coll.writes == []


def test_a_dead_provider_says_so_instead_of_reading_as_a_quiet_tape(monkeypatch):
    monkeypatch.setattr(EA, "FETCH_RETRY_SLEEP_SEC", 0)
    coll = FakeColl()
    rows = [_row("A1"), _row("A2")]
    out, sender = _run(monkeypatch, rows=rows, coll=coll, doc_reports={},
                       fetch=lambda s: None)
    assert out["fetch_failed"] == 2 and out["candidates"] == 0
    assert coll.writes == [] and sender.calls == []
    assert out["reason"] == "yfinance fallback on 2 of 2 REACTED names — surprises unread"


def test_one_failed_fetch_out_of_four_is_NOT_a_pass_wide_reason(monkeypatch):
    monkeypatch.setattr(EA, "FETCH_RETRY_SLEEP_SEC", 0)
    rows = [_row("A%d" % i) for i in range(4)]
    docs = {r["symbol"]: _lr() for r in rows if r["symbol"] != "A0"}
    out, _ = _run(monkeypatch, rows=rows, doc_reports=docs,
                  fetch=lambda s: None if s == "A0" else {"when": "AMC", "last_report": _lr()})
    assert out["fetch_failed"] == 1 and "reason" not in out


def test_a_transport_raise_RELEASES_the_key_so_the_next_pass_retries(monkeypatch):
    coll = FakeColl()
    sender = Sender(raise_on=lambda p: True)
    out, _ = _run(monkeypatch, rows=[_row()], coll=coll, doc_reports={"AAA": _lr()},
                  sender=sender)
    assert out["individual"] == 0
    assert coll.writes == ["AAA|%s" % THU] and coll.deletes == ["AAA|%s" % THU]
    assert "AAA|%s" % THU not in coll.docs


def test_a_NON_TERMINAL_result_releases_too(monkeypatch):
    """A closed day / a muted device / a failed transport: `sent 0` with a
    target that failed is "retry", not "delivered"."""
    coll = FakeColl()
    sender = Sender(result={"sent": 0, "failed": 1, "total_targets": 1})
    out, _ = _run(monkeypatch, rows=[_row()], coll=coll, doc_reports={"AAA": _lr()},
                  sender=sender)
    assert out["individual"] == 0 and coll.deletes == ["AAA|%s" % THU]


def test_nobody_targeted_is_TERMINAL_and_keeps_the_claim(monkeypatch):
    coll = FakeColl()
    sender = Sender(result={"sent": 0, "failed": 0, "total_targets": 0})
    out, _ = _run(monkeypatch, rows=[_row()], coll=coll, doc_reports={"AAA": _lr()},
                  sender=sender)
    assert out["individual"] == 1 and coll.deletes == []


def test_a_digest_raise_releases_EVERY_digest_key(monkeypatch):
    rows = [_row("S%d" % i, dollar_vol=(10 - i) * 1e8) for i in range(GA.MAX_INDIVIDUAL + 2)]
    docs = {r["symbol"]: _lr() for r in rows}
    coll = FakeColl()
    sender = Sender(raise_on=lambda p: p.get("ticker") is None)
    out, _ = _run(monkeypatch, rows=rows, coll=coll, doc_reports=docs, sender=sender)
    assert out["digest"] == 0
    assert sorted(coll.deletes) == ["S4|%s" % THU, "S5|%s" % THU]


def test_a_dry_run_reads_the_state_and_writes_nothing(monkeypatch):
    coll = FakeColl(seeded=["AAA|%s" % THU])
    recorded = []
    monkeypatch.setattr(EA.AS, "record_result", lambda *a, **k: recorded.append(a))
    rows = [_row(), _row("BBB")]
    out, sender = _run(monkeypatch, rows=rows, coll=coll, dry_run=True,
                       doc_reports={"AAA": _lr(), "BBB": _lr()})
    assert out["dry_run"] is True and out["candidates"] == 2 and out["fresh"] == 1
    assert out["individual"] == 1, "what a wet pass WOULD send"
    assert sender.calls == [] and coll.writes == [] and coll.deletes == []
    assert recorded == [], "a dry run records no pass"


def test_a_wet_pass_records_itself_for_the_alerts_page(monkeypatch):
    recorded = []
    monkeypatch.setattr(EA.AS, "record_result",
                        lambda kind, res, now=None, coll=None: recorded.append((kind, res)))
    out, _ = _run(monkeypatch, rows=[_row()], doc_reports={"AAA": _lr()})
    assert recorded and recorded[0][0] == EA.KIND
    assert recorded[0][1]["candidates"] == 1 and out["ran"] is True


# ── the guards (in-session, price-cache freshness) ──────────────────────────
def test_the_pass_refuses_to_run_IN_SESSION(monkeypatch):
    """Between 10:00 and 16:30 the cache's last row is today's PARTIAL bar
    (vcp-watch patches it hourly): every reaction would be half a session."""
    scanned = []
    monkeypatch.setattr(EA, "_scan", lambda *a, **k: scanned.append(1) or ([], {}))
    out = EA.run(now=datetime(2026, 9, 18, 11, 0, tzinfo=ET))
    assert out["ran"] is False and "partial bar" in out["reason"] and scanned == []


def test_a_stale_or_pre_patched_price_cache_skips_the_pass(monkeypatch):
    """NEGATIVE (critique F5): a pre-market Scan click patches TODAY's date
    into the cache, so at 08:25 every BMO reporter would silently drop. The
    pass says which bar it found instead of reporting a quiet tape."""
    scanned = []
    monkeypatch.setattr(EA, "_scan", lambda *a, **k: scanned.append(1) or ([], {}))
    recorded = []
    monkeypatch.setattr(EA.AS, "record_result",
                        lambda kind, res, now=None, coll=None: recorded.append(res))
    out = EA.run(now=MORNING, last_bar=MON)
    assert out["ran"] is False and scanned == []
    assert out["reason"] == "price cache last bar %s, expected %s — pass skipped" % (MON, FRI)
    assert recorded and recorded[0]["reason"] == out["reason"]


def test_the_expected_bar_is_today_in_the_evening_and_the_last_session_at_dawn():
    assert EA.expected_last_bar(EVENING) == FRI
    assert EA.expected_last_bar(MORNING) == FRI, "Monday 08:25 expects Friday's close"
    assert EA._slot(MORNING) == "morning" and EA._slot(EVENING) == "evening"


def test_the_freshness_guard_passes_on_the_bar_it_expects(monkeypatch):
    out, sender = _run(monkeypatch, rows=[_row()], doc_reports={"AAA": _lr()},
                       force=False, last_bar=FRI)
    assert out["ran"] is True and len(sender.calls) == 1


# ── context: recorded, never binding ────────────────────────────────────────
def test_a_zone_read_that_FAILS_never_drops_the_push(monkeypatch):
    def boom(sym):
        raise RuntimeError("zone_store down")

    monkeypatch.setattr(EA, "_bands_for", boom)
    sender = Sender()
    import push
    monkeypatch.setattr(push, "sender", sender)
    out = EA.run(force=True, now=EVENING, coll=FakeColl(), scan_result=_res([_row()]),
                 doc_reports={"AAA": _lr()}, frames={"AAA": _frame()})
    assert out["context_unavailable"] == 1 and out["individual"] == 1
    assert "zone read unavailable" in sender.calls[0]["payload"]["body"]


def test_the_room_gate_is_COUNTED_and_never_enforced(monkeypatch):
    """memory feedback_alert_gate_room_proximity binds the S/D zone pushes.
    This is an event notice, not a demand entry — widening that gate to this
    kind is HIS call (§7.4b), so the pass only says how often it would have
    refused."""
    lid = {"lo": 110.5, "hi": 115.0, "kind": "supply", "touches": 5, "strength": 80}
    out, sender = _run(monkeypatch, rows=[_row()], doc_reports={"AAA": _lr()},
                       bands={"AAA": [lid]})
    assert out["would_skip_room"] == 1
    assert out["individual"] == 1, "counted, never enforced"


def test_no_counter_this_pass_reports_is_one_the_alerts_page_sums(monkeypatch):
    """NEGATIVE (critique C11): `Alerts.tsx::skipsToday` sums six `skipped_*`
    keys across EVERY pass in the payload. A counter named `skipped_room` here
    would silently inflate the S/D gate's own tally on the page."""
    reserved = {"skipped_room", "skipped_proximity", "skipped_direction",
                "skipped_knife", "skipped_mood", "skipped_floor"}
    wet, _ = _run(monkeypatch, rows=[_row()], doc_reports={"AAA": _lr()})
    dry, _ = _run(monkeypatch, rows=[_row()], doc_reports={"AAA": _lr()}, dry_run=True)
    for summary in (wet, dry):
        assert reserved.isdisjoint(summary), sorted(reserved & set(summary))
    assert "would_skip_room" in wet, "the room read is reported under its own name"


# ── module boundaries ───────────────────────────────────────────────────────
def test_the_owner_address_is_imported_never_a_second_literal():
    src = Path(EA.__file__).read_text(encoding="utf-8")
    assert GA.OWNER not in src and "@" not in src
    assert EA.OWNER == GA.OWNER and EA.MAX_INDIVIDUAL == GA.MAX_INDIVIDUAL


def test_the_module_reads_the_ONE_engine_and_no_second_surprise_source():
    src = Path(EA.__file__).read_text(encoding="utf-8")
    assert "catalyst" not in src and "last_surprise_pct" not in src
    assert "E.scan(" in src, "the tab's scan is the engine, not a second scanner"
    assert "earnings_picks" in src, "the shared reaction reader anchors the bar"


def test_the_gate_thresholds_are_never_retyped_in_this_module():
    """SOURCE GUARD: a literal here would drift from chart_maps.earnings."""
    src = Path(EA.__file__).read_text(encoding="utf-8")
    body = src.split('"""', 2)[-1]          # skip the module docstring
    for literal in ("1.5", "0.60", "50_000_000", "0.6 "):
        assert literal not in body, literal


# ── the "doc" branch is live in cron, not only under injection (2026-09-20) ──
def test_the_cron_path_reads_the_calendar_docs_so_the_doc_branch_is_not_dead(monkeypatch):
    """POSITIVE, refix 2026-09-20. `run()` never passed `doc_reports`, so
    `this_quarter_report` always fell through to a network read — the "doc"
    branch existed only in tests. Un-injected, `_scan` now fills it ONCE from
    the same collection `scan()` read, and `doc_hits` says how many names cost
    no fetch. Cost, never correctness: the pushed numbers are identical."""
    import sepa.earnings_watch as EW

    class Cal:
        def find(self, q):
            return [{"_id": "AAA", "next_date": THU, "when": "AMC", "last_report": _lr()}]

    monkeypatch.setattr(EW, "_coll", lambda: Cal())
    monkeypatch.setattr(EA, "_frame_for", lambda sym: _frame(end=FRI))
    out = EA.run(force=True, now=EVENING, coll=FakeColl(), dry_run=True,
                 scan_result=_res([_row()]), frames={"AAA": _frame(end=FRI)},
                 bands={"AAA": []},
                 fetch=lambda s: pytest.fail("the doc already described this report"))
    assert out["doc_hits"] == 1 and out["candidates"] == 1
    assert out["fetch_failed"] == 0


def test_a_doc_for_ANOTHER_quarter_still_pays_the_fetch(monkeypatch):
    """NEGATIVE. The cheap read must not become a second source of truth: a
    calendar row whose `last_report.date` is some older quarter is ignored and
    the fresh read decides, exactly as before. `doc_hits` stays 0."""
    import sepa.earnings_watch as EW

    class Cal:
        def find(self, q):
            return [{"_id": "AAA", "last_report": _lr(date="2026-06-18")}]

    monkeypatch.setattr(EW, "_coll", lambda: Cal())
    calls = []

    def fetch(sym):
        calls.append(sym)
        return {"when": "AMC", "last_report": _lr()}

    out = EA.run(force=True, now=EVENING, coll=FakeColl(), dry_run=True,
                 scan_result=_res([_row()]), frames={"AAA": _frame(end=FRI)},
                 bands={"AAA": []}, fetch=fetch)
    assert calls == ["AAA"] and out["doc_hits"] == 0 and out["candidates"] == 1


def test_a_calendar_read_that_blows_up_falls_straight_back_to_fetching(monkeypatch):
    """NEGATIVE. Mongo down must cost the pass nothing but the network reads it
    was already making — never an exception out of `run()`."""
    import sepa.earnings_watch as EW

    def boom():
        raise RuntimeError("mongo down")

    monkeypatch.setattr(EW, "_coll", boom)
    out = EA.run(force=True, now=EVENING, coll=FakeColl(), dry_run=True,
                 scan_result=_res([_row()]), frames={"AAA": _frame(end=FRI)},
                 bands={"AAA": []},
                 fetch=lambda s: {"when": "AMC", "last_report": _lr()})
    assert out["ran"] is True and out["doc_hits"] == 0 and out["candidates"] == 1


def test_an_injected_empty_doc_map_is_NOT_treated_as_missing(monkeypatch):
    """NEGATIVE. `{}` is a caller saying 'no docs, fetch everything' — the lazy
    read must fire only on None, or every fetch-path test in this file would
    quietly start reading Mongo."""
    import sepa.earnings_watch as EW
    monkeypatch.setattr(EW, "_coll", lambda: pytest.fail("un-injected calendar read"))
    out = EA.run(force=True, now=EVENING, coll=FakeColl(), dry_run=True,
                 scan_result=_res([_row()]), doc_reports={},
                 frames={"AAA": _frame(end=FRI)}, bands={"AAA": []},
                 fetch=lambda s: {"when": "AMC", "last_report": _lr()})
    assert out["doc_hits"] == 0 and out["candidates"] == 1


def test_no_reacted_rows_means_no_calendar_read_at_all(monkeypatch):
    """NEGATIVE. A quiet tape must cost zero Mongo reads."""
    import sepa.earnings_watch as EW
    monkeypatch.setattr(EW, "_coll", lambda: pytest.fail("read the calendar for nothing"))
    out = EA.run(force=True, now=EVENING, coll=FakeColl(), dry_run=True,
                 scan_result=_res([]), frames={}, bands={})
    assert out["candidates"] == 0 and out["doc_hits"] == 0
