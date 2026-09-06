"""Catalyst-lane entry behavior — fake broker + fake Mongo, no network, no
scan ever triggered (docs/supply_demand/catalyst_entry.md).

Locks trading/catalyst_entry.py:

  Source    catalysts.api._cache_get() ONLY (the cached scan); None -> the
            tick skips with "no cached catalyst scan" and never scans.
  Funnel    quadrant REAL|OVERLOOKED, review grade A|B, no pump warning, no
            offering on file, price >= 2, dollar volume >= $2M; every
            missing field fails CLOSED.
  Gate      the phone's alert rules (supply_demand/alert_gates): room to the
            first unbroken band overhead >= 5% (CLEAR ok, IN_BAND/NEAR fail)
            AND (a bounce read OR a demand band within 1% under the print);
            coverage 'pending' -> skipped, retried next tick.
  Stop      demand band lo x (1 - STOP_BUFFER_PCT%) handed to entries as the
            ABSOLUTE level; broken-supply bounce -> that band's lo.
  Cap       1 catalyst buy per ET day; one attempt per (symbol, ET day),
            state written BEFORE entries.enter.
  Buys      ONLY via entries.enter (source grep here + contracts).

Host-runnable (py3.9, no pandas/numpy):
    cd backend && .venv/bin/python -m pytest tests/test_catalyst_entry.py -q
"""
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pathlib
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.catalyst_entry as CE
import trading.entries as EN
import trading.exit_engine as EE
import trading.zone_edge_entry as ZE
from supply_demand.alert_gates import ALERT_MAX_ABOVE_DEMAND_PCT, ALERT_MIN_ROOM_PCT
from trading.risk_rules import ABS_MAX_STOP_PCT

ET = ZoneInfo("America/New_York")
DAY = EE._et_day()
NOW = datetime.combine(date.fromisoformat(DAY), dtime(10, 30), tzinfo=ET)
_REAL_ZONE_ROWS = CE.zone_rows          # captured before any fixture patches it


def _as_of(seconds_before_now: int) -> str:
    return (NOW - timedelta(seconds=seconds_before_now)).astimezone(timezone.utc).isoformat()


# ── Fakes (pattern: tests/test_zone_edge_entry.py) ───────────────────────────

class FakeCursor(list):
    def sort(self, key=None, direction=1, *a, **k):
        if isinstance(key, str):
            return FakeCursor(sorted(self, key=lambda d: d.get(key) or 0,
                                     reverse=(direction == -1)))
        return self

    def limit(self, n):
        return FakeCursor(self[:int(n)])


class FakeColl:
    def __init__(self, docs=None):
        self.rows = [dict(d) for d in (docs or [])]

    @staticmethod
    def _match(doc, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict):
                dv = doc.get(k)
                if "$in" in v and dv not in v["$in"]:
                    return False
                if "$ne" in v and dv == v["$ne"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, q=None, *a, **k):
        for d in self.rows:
            if self._match(d, q):
                return dict(d)
        return None

    def find(self, q=None, *a, **k):
        return FakeCursor(dict(d) for d in self.rows if self._match(d, q))

    def insert_one(self, doc):
        self.rows.append(dict(doc))

    def update_one(self, q, update, upsert=False):
        for d in self.rows:
            if self._match(d, q):
                d.update(update.get("$set") or {})
                return
        if upsert:
            base = {k: v for k, v in (q or {}).items() if not isinstance(v, dict)}
            base.update(update.get("$set") or {})
            self.rows.append(base)

    def delete_many(self, q):
        self.rows = [d for d in self.rows if not self._match(d, q)]


class FakeDB:
    def __init__(self, armed=True, flag=True):
        self.trading_config = FakeColl([{
            "_id": "config", "armed": armed, "catalyst_entry": flag,
            "zone_edge_entry": False, "auto_entry": False,
            "consecutive_losses": 0, "processed_order_ids": [],
            "equity_cap": 100_000.0, "progressive_exposure": False}])
        self.trade_ledger = FakeColl()
        self.catalyst_entry_state = FakeColl()
        self.zone_edge_entry_state = FakeColl()
        self.auto_entry_state = FakeColl()


class FakeBroker:
    """Reads only — any submit_*/replace/cancel attempt raises AttributeError."""

    def __init__(self, positions=(), market_open=True, configured=True, mode="paper"):
        self._positions = list(positions)
        self._market_open = bool(market_open)
        self._configured = bool(configured)
        self._mode = mode

    def configured(self):
        return self._configured

    def clock(self):
        return {"is_open": self._market_open}

    def mode(self):
        return self._mode

    def account(self):
        return {"equity": "100000", "cash": "100000", "buying_power": "100000"}

    def positions(self):
        return [dict(p) for p in self._positions]

    def open_orders(self, symbol=None):
        return []

    def latest_trade(self, symbol):
        return None

    def make_client_order_id(self, symbol, intent):
        return "cheetah-%s-%s-%s" % (symbol, DAY.replace("-", ""), intent)


# ── Builders ────────────────────────────────────────────────────────────────

def cand(ticker="EOSE", quadrant="REAL", grade="A", pump=False, offering=False,
         price=5.0, dollar_volume=5_000_000, summary="Grid storage contract award",
         composite=80.0, review="default", evidence="default", **extra):
    c = {"ticker": ticker, "price": price, "dollar_volume": dollar_volume,
         "change_pct": 12.0, "market_cap": 3e8, "enterprise_value": 9e8,   # clears the $700M EV floor (2026-09-06)
         "quadrant": quadrant, "composite_score": composite}
    if review == "default":
        c["review"] = {"catalyst_summary": summary, "evidence_grade": grade,
                       "is_pump_warning": pump}
    elif review is not None:
        c["review"] = review
    if evidence == "default":
        c["evidence"] = {"sec_filings": {"has_offering": offering}}
    elif evidence is not None:
        c["evidence"] = evidence
    c.update(extra)
    return c


def scan(cands, as_of="2026-09-05T14:20:00+00:00", age=60):
    return {"as_of": as_of, "candidates": list(cands), "n_total": len(cands),
            "cached": True, "cache_age_sec": age}


def br_row(sym, print_px, room=None, bounce=None, coverage="store"):
    if coverage != "store":
        return {"symbol": sym, "coverage": coverage,
                **({"error": "no / insufficient price data"} if coverage == "unavailable" else {})}
    return {"symbol": sym, "print": print_px, "fresh": True, "coverage": coverage,
            "bounce": bounce, "room": room, "print_age_sec": 30}


def br_payload(rows, store_date=DAY):
    return {"as_of": NOW.isoformat(), "in_session": True, "store_date": store_date,
            "rows": {r["symbol"]: r for r in rows},
            "requested": len(rows),
            "covered": sum(1 for r in rows if r["coverage"] in ("store", "ondemand")),
            "pending": sum(1 for r in rows if r["coverage"] == "pending"),
            "unavailable": sum(1 for r in rows if r["coverage"] == "unavailable")}


def band(kind, lo, hi, touches=3):
    return {"kind": kind, "lo": lo, "hi": hi, "touches": touches, "strength": 50.0}   # proven (2026-09-06 rule)


def zdoc(sym, bands, prev_close=4.9):
    return {"_id": "%s:%s" % (sym, DAY), "symbol": sym, "date": DAY,
            "bands": list(bands), "prev_close": prev_close, "atr14": 0.2,
            "high_252": 8.0}


def bounce_of(b, touch_low, bounce_pct=4.0, role="demand"):
    return {"band": {"kind": b["kind"], "lo": b["lo"], "hi": b["hi"],
                     "touches": b["touches"]},
            "role": role, "touch_low": touch_low, "touch_date": DAY,
            "sessions_ago": 1, "bounce_pct": bounce_pct, "floor_pct": 3.0,
            "strong": False, "atr_x": 1.0}


# The default happy case: EOSE printing 5.00, demand band 4.80-4.97 under it
# (0.6% above the top -> inside the 1% proximity line), first supply 5.60
# (+12%) -> room passes, stop = 4.80 x 0.995 = 4.776.
DEMAND = band("demand", 4.80, 4.97)
SUPPLY_FAR = band("supply", 5.60, 5.80)


def happy(sym="EOSE", print_px=5.0, bands=(DEMAND, SUPPLY_FAR), bounce=None,
          room_state="ROOM", room_pct=12.0):
    rows = [br_row(sym, print_px, room={"state": room_state, "room_pct": room_pct,
                                         "band": None, "atr_days": None,
                                         "at_highs": False}, bounce=bounce)]
    return br_payload(rows), {sym: zdoc(sym, bands)}


@pytest.fixture
def env(monkeypatch):
    """Wire catalyst_entry's seams; returns (broker, db, enter_calls, pushes,
    calls) where calls counts scan / bounce-room / zone-doc reads."""

    def build(payload="none", bounce=None, docs=None, positions=(), armed=True,
              flag=True, market_open=True, configured=True, now=NOW,
              enter_result=None, enter_raises=None, mode="paper",
              sales=None):
        fake = FakeBroker(positions, market_open, configured, mode)
        db = FakeDB(armed=armed, flag=flag)
        enter_calls, pushes = [], []
        calls = {"scan": 0, "rows": [], "docs": []}
        scan_payload = None if payload == "none" else payload

        def fake_enter(symbol, limit_price=None, stop_pct=None,
                       allow_earnings=False, top_up=False, stop_price=None,
                       strategy="manual", reason=None):
            enter_calls.append({"symbol": symbol, "limit_price": limit_price,
                                "stop_pct": stop_pct, "stop_price": stop_price,
                                "allow_earnings": allow_earnings, "top_up": top_up,
                                "strategy": strategy, "reason": reason})
            if enter_raises:
                raise enter_raises
            res = enter_result or {"order_id": "o-%d" % len(enter_calls), "shares": 40,
                                   "stop": {"stop_pct": stop_pct, "stop_price": stop_price,
                                            "basis": "requested"}}
            EE.ledger("entry", symbol=symbol,
                      detail={"order_id": res["order_id"],
                              "client_order_id": "coid-%s" % symbol, "price": 5.0,
                              "strategy": strategy, "entry_reason": reason})
            return res

        def fake_scan():
            calls["scan"] += 1
            return scan_payload

        def fake_rows(cands, zdocs, day, as_of, now_et):
            # The injected bounce-room rows stand in for zone_rows' pure read
            # (zone_rows itself is unit-tested on a real doc below); `bounce`
            # None = every name without a zone doc.
            syms = [c["symbol"] for c in cands]
            calls["rows"].append(syms)
            if bounce is None:
                return {s: {"symbol": s, "coverage": "pending"} for s in syms}
            return bounce["rows"]

        def fake_docs(tickers, store_date):
            calls["docs"].append((list(tickers), store_date))
            return {t: (docs or {}).get(t) for t in tickers if (docs or {}).get(t)}

        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(EN, "_db", lambda: db)
        monkeypatch.setattr(CE, "_db", lambda: db)
        monkeypatch.setattr(ZE, "_db", lambda: db)      # EE.status() walks every lane's block
        monkeypatch.setattr(ZE, "broker", fake)
        monkeypatch.setattr(CE, "broker", fake)
        monkeypatch.setattr(EE, "broker", fake)
        monkeypatch.setattr(EN, "broker", fake)
        monkeypatch.setattr(CE, "_now_et", lambda: now)
        monkeypatch.setattr(CE, "_cached_scan", fake_scan)
        monkeypatch.setattr(CE, "_store_day", lambda now_et: date.fromisoformat(DAY))
        monkeypatch.setattr(CE, "zone_rows", fake_rows)
        monkeypatch.setattr(CE, "_zone_docs", fake_docs)
        monkeypatch.setattr(CE, "_notify",
                            lambda sym, mode_word, body: pushes.append((sym, mode_word, body)))
        monkeypatch.setattr(CE.entries, "enter", fake_enter)
        # Size + sales gates (Ajay 2026-09-06) pass by default so the older
        # tests keep exercising the zone gate; the gate tests override these.
        _sales = sales if sales is not None else {"tier": "steady", "score": 60, "growth_yoy_pct": 12.0}
        monkeypatch.setattr(CE, "sales_for", lambda syms: {s: (dict(_sales) if _sales else None) for s in syms})
        return fake, db, enter_calls, pushes, calls

    return build


def _kind_rows(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


def _state_rows(db):
    return db.catalyst_entry_state.rows


def _assert_never(db, enter_calls):
    assert enter_calls == []
    assert _kind_rows(db, "catalyst_entry") == []
    assert _state_rows(db) == []


# ── Owner settings locked ────────────────────────────────────────────────────

def test_owner_settings_locked():
    assert CE.MAX_CATALYST_ENTRIES_PER_DAY == 1          # "time to time"
    assert CE.CATALYST_MIN_PRICE == 2.0                  # conservative default, NOT from Ajay
    assert CE.CATALYST_MIN_DOLLAR_VOL == 2_000_000       # conservative default, NOT from Ajay
    assert CE.QUADRANTS_OK == ("REAL", "OVERLOOKED")
    assert CE.GRADES_OK == ("A", "B")
    assert CE.STATE_COLL == "catalyst_entry_state"
    assert CE.SUMMARY_MAX_CHARS == 160
    assert CE.LAST_ENTRY_ET is ZE.LAST_ENTRY_ET          # reused, never redefined
    assert CE.STOP_BUFFER_PCT is ZE.STOP_BUFFER_PCT


# ── Gates ────────────────────────────────────────────────────────────────────

def test_flag_off_noops_with_single_daily_disabled_ledger(env):
    _, db, enter_calls, _, calls = env(payload=scan([cand()]), flag=False)
    out = CE.run()
    assert out["ran"] is False and out["reason"] == "gated"
    assert out["gate"]["catalyst_entry"] is False
    _assert_never(db, enter_calls)
    assert calls["scan"] == 0                              # gated before any read
    assert len(_kind_rows(db, "catalyst_entry_disabled")) == 1
    CE.run()
    assert len(_kind_rows(db, "catalyst_entry_disabled")) == 1


def test_disarmed_and_closed_and_unconfigured_place_no_orders(env):
    for kw in ({"armed": False}, {"market_open": False}, {"configured": False}):
        _, db, enter_calls, _, _ = env(payload=scan([cand()]), **kw)
        out = CE.run()
        assert out["reason"] == "gated"
        _assert_never(db, enter_calls)


def test_after_last_entry_time_places_nothing(env):
    late = datetime.combine(date.fromisoformat(DAY), dtime(15, 45), tzinfo=ET)
    _, db, enter_calls, _, calls = env(payload=scan([cand()]), now=late)
    out = CE.run()
    assert out["reason"] == "after_last_entry_time"
    assert calls["scan"] == 0
    _assert_never(db, enter_calls)


def test_no_cached_scan_skips_and_never_triggers_a_scan(env):
    _, db, enter_calls, _, calls = env(payload=None)
    out = CE.run()
    assert out["ran"] is True and out["reason"] == "no cached catalyst scan"
    assert calls["scan"] == 1 and calls["rows"] == [] and calls["docs"] == []
    _assert_never(db, enter_calls)


# ── Quality funnel (pure) ────────────────────────────────────────────────────

@pytest.mark.parametrize("c, why", [
    (cand(quadrant="PUMP_RISK"), "quadrant PUMP_RISK"),
    (cand(quadrant="DEAD"), "quadrant DEAD"),
    (cand(quadrant=None), "quadrant None"),
    (cand(grade="C"), "grade C"),
    (cand(grade=None), "grade None"),
    (cand(pump=True), "pump warning"),
    (cand(offering=True), "offering on file"),
    (cand(price=1.99), "price 1.99 < 2"),
    (cand(price=None), "no price"),
    (cand(dollar_volume=1_999_999), "dollar volume"),
    (cand(dollar_volume=None), "dollar volume unknown"),
    (cand(review=None), "no review"),
    (cand(evidence=None), "offering unknown"),
    (cand(ticker=""), "no symbol"),
])
def test_funnel_rejects(c, why):
    reason = CE.qualify(c)
    assert reason is not None and why.split()[0].lower() in reason.lower(), (why, reason)


def test_funnel_accepts_real_a_and_overlooked_b_sorted_by_composite():
    a, b = cand("AAA", "REAL", "A", composite=70), cand("BBB", "OVERLOOKED", "B", composite=90)
    assert CE.qualify(a) is None and CE.qualify(b) is None
    cands, rejected = CE.read_candidates(scan([a, b, cand("CCC", quadrant="PUMP_RISK")]))
    assert [c["symbol"] for c in cands] == ["BBB", "AAA"]     # composite desc
    assert rejected == [{"symbol": "CCC", "reason": "quadrant PUMP_RISK"}]
    assert cands[0]["catalyst_summary"] == "Grid storage contract award"


def test_funnel_truncates_summary_and_survives_malformed_payload():
    long = "x" * 500
    cands, _ = CE.read_candidates(scan([cand(summary=long)]))
    assert len(cands[0]["catalyst_summary"]) == CE.SUMMARY_MAX_CHARS
    assert CE.read_candidates(None) == ([], [])
    assert CE.read_candidates({"candidates": "nope"}) == ([], [])
    cands, rejected = CE.read_candidates({"candidates": [None, 3, {"ticker": "ZZZ"}]})
    assert cands == [] and rejected[0]["symbol"] == "ZZZ"


# ── Zone gate (the phone's alert rules) ──────────────────────────────────────

def test_no_zone_doc_skips_without_attempt_then_enters_next_tick(env, monkeypatch):
    """A name with no zone doc yet is a SKIP (re-read next tick), never an
    attempt and never a build: the docs come from Mongo only (the Catalysts
    board's bounce-room call builds them) — review 2026-09-05."""
    payload = scan([cand()])
    _, db, enter_calls, _, calls = env(payload=payload, bounce=None)   # every row doc-less
    out = CE.run()
    assert out["skipped"] == [{"symbol": "EOSE", "reason": CE.NO_DOC_REASON}]
    assert "Catalysts board" in CE.NO_DOC_REASON and "next tick" in CE.NO_DOC_REASON
    assert out["skipped_pending"] == 1
    _assert_never(db, enter_calls)
    assert calls["rows"] == [["EOSE"]]
    assert calls["docs"] == [(["EOSE"], date.fromisoformat(DAY))]
    br, docs = happy()
    monkeypatch.setattr(CE, "zone_rows", lambda cands, zdocs, day, as_of, now_et: br["rows"])
    monkeypatch.setattr(CE, "_zone_docs", lambda tickers, day: docs)
    out2 = CE.run()
    assert out2["entered"] == ["EOSE"] and len(enter_calls) == 1


def test_snap_from_scan_and_zone_rows_are_pure_and_read_the_scans_print():
    """The tick reads NO tape: the print is the cached scan's own price, the
    session low its day_low, the prior close its prev_close — shaped like a
    bulk_snapshot row so bounce_room.read_symbol (pure) produces the same
    bounce / room read the board would. as_of stamps the print's age."""
    as_of = _as_of(60)
    c = cand(price=5.0, day_low=4.83, day_high=5.05, prev_close=4.90)
    snap = CE.snap_from_scan(c, as_of)
    assert snap["last_trade_price"] == 5.0 and snap["close"] == 5.0
    assert snap["low"] == 4.83 and snap["high"] == 5.05 and snap["prev_day_close"] == 4.90
    assert snap["date"] == DAY
    assert abs(snap["last_trade_ts_ms"] - datetime.fromisoformat(as_of).timestamp() * 1000) < 1
    # a candidate without a day low still prints (no touch read, no bounce)
    bare = CE.snap_from_scan(cand(price=5.0), as_of)
    assert bare["last_trade_price"] == 5.0 and bare["low"] is None
    assert CE.snap_from_scan(cand(price=None), as_of) is None
    # zone_rows: doc + scan bar -> a bounce read off the touched demand band;
    # no doc -> pending (doc-less); print age from as_of.
    doc = zdoc("EOSE", (DEMAND, SUPPLY_FAR), prev_close=4.90)
    doc["atr14"] = 0.1
    doc["recent"] = []
    rows = CE.zone_rows([CE._candidate(c), CE._candidate(cand("NODOC"))],
                        {"EOSE": doc}, date.fromisoformat(DAY), as_of, NOW)
    r = rows["EOSE"]
    assert r["coverage"] == "store" and r["print"] == 5.0
    assert r["print_age_sec"] == pytest.approx(60, abs=1)
    assert r["bounce"] and r["bounce"]["band"]["lo"] == 4.80 and r["bounce"]["role"] == "demand"
    assert r["room"]["state"] == "ROOM" and r["room"]["room_pct"] == 12.0
    assert rows["NODOC"] == {"symbol": "NODOC", "coverage": "pending"}
    # a stale scan still yields a row (the gate decides), with its true age
    old = CE.zone_rows([CE._candidate(c)], {"EOSE": doc}, date.fromisoformat(DAY),
                       _as_of(720), NOW)
    assert old["EOSE"]["print_age_sec"] == pytest.approx(720, abs=1)
    # unparseable as_of -> age None (fails closed at the gate)
    assert CE.zone_rows([CE._candidate(c)], {"EOSE": doc}, date.fromisoformat(DAY),
                        "garbage", NOW)["EOSE"]["print_age_sec"] is None


def test_run_never_reaches_the_tape_or_the_ondemand_queue(env, monkeypatch):
    """REGRESSION (review 2026-09-05): the lane used to call
    bounce_room.api_payload from the tick — a synchronous provider snapshot
    plus on-demand zone builds for every funnel survivor. Now the tick reads
    Mongo docs only and prices off the cached scan. With the REAL zone_rows
    wired and every network / builder seam rigged to blow up, a buy still
    goes through."""
    from supply_demand import bounce_room as BR

    def boom(*a, **k):
        raise AssertionError("the catalyst tick must never reach the tape or the queue")

    monkeypatch.setattr(BR, "api_payload", boom)
    monkeypatch.setattr(BR, "queue_ondemand", boom)
    monkeypatch.setattr(BR, "default_builder", boom, raising=False)
    monkeypatch.setattr(BR, "_coll", boom)
    c = cand(price=5.0, day_low=4.83, day_high=5.05, prev_close=4.90)
    doc = zdoc("EOSE", (DEMAND, SUPPLY_FAR), prev_close=4.90)
    doc["atr14"] = 0.1
    doc["recent"] = []
    _, db, enter_calls, _, calls = env(payload=scan([c], as_of=_as_of(60)), docs={"EOSE": doc})
    monkeypatch.setattr(CE, "zone_rows", _REAL_ZONE_ROWS)                # the real one
    out = CE.run()
    assert out["entered"] == ["EOSE"] and len(enter_calls) == 1
    assert calls["docs"] == [(["EOSE"], date.fromisoformat(DAY))]
    r = enter_calls[0]["reason"]
    assert r["print"] == 5.0 and r["print_basis"] == "catalyst scan price"
    assert r["print_age_sec"] == pytest.approx(60, abs=1)
    assert r["bounce"]["band"]["lo"] == 4.80


def test_stale_scan_print_is_skipped_on_the_phones_stale_line(env):
    """Phone gate = entry gate: zone_bounce_alerts drops a print older than
    STALE_PRINT_SEC; the lane refuses to buy on one too (reused constant, not
    a new number). Unknown age fails closed."""
    from supply_demand.zone_bounce_alerts import STALE_PRINT_SEC
    br, docs = happy()
    br["rows"]["EOSE"]["print_age_sec"] = STALE_PRINT_SEC + 100
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"].startswith("alert gate: print stale")
    assert "%d" % STALE_PRINT_SEC in out["skipped"][0]["reason"]
    assert out["skipped_alert_gate"] == 1
    _assert_never(db, enter_calls)
    br, docs = happy()
    br["rows"]["EOSE"]["print_age_sec"] = None
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"].startswith("alert gate: print age unknown")
    _assert_never(db, enter_calls)
    # exactly at the line still passes (the phone's own boundary)
    br, docs = happy()
    br["rows"]["EOSE"]["print_age_sec"] = STALE_PRINT_SEC
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]


def test_unavailable_coverage_skips(env):
    br = br_payload([br_row("EOSE", None, coverage="unavailable")])
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br)
    out = CE.run()
    assert out["skipped"][0]["reason"].startswith("zone coverage unavailable")
    _assert_never(db, enter_calls)


def test_room_in_band_and_under_floor_skip_clear_and_wide_pass(env):
    # IN_BAND: a supply band containing the print.
    br, docs = happy(bands=(DEMAND, band("supply", 4.95, 5.10)))
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"].startswith("alert gate: inside supply band 4.95-5.1")
    assert out["skipped_alert_gate"] == 1
    _assert_never(db, enter_calls)
    # ROOM under the floor: first supply 5.15 = +3.0%.
    br, docs = happy(bands=(DEMAND, band("supply", 5.15, 5.30)))
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"] == "alert gate: room 3.00%% < %g%% (supply 5.15-5.3)" % ALERT_MIN_ROOM_PCT
    _assert_never(db, enter_calls)
    # A demand band ABOVE the print is broken support = resistance too.
    br, docs = happy(bands=(DEMAND, band("demand", 5.10, 5.20)))
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert "room 2.00% <" in out["skipped"][0]["reason"] and "(demand 5.1-5.2)" in out["skipped"][0]["reason"]
    # CLEAR: nothing overhead.
    br, docs = happy(bands=(DEMAND,), room_state="CLEAR", room_pct=None)
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["entered"] == ["EOSE"]
    assert enter_calls[0]["reason"]["room"]["state"] == "CLEAR"
    # Wide room (+12%) passes.
    br, docs = happy()
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]
    assert enter_calls[0]["reason"]["room"]["room_pct"] == 12.0


def test_broken_supply_under_prev_close_is_not_overhead(env):
    """A supply band yesterday CLOSED above is support (the house rule): with
    prev_close 5.45 the 5.20-5.40 band no longer lids the print."""
    bands = (DEMAND, band("supply", 5.20, 5.40), SUPPLY_FAR)
    br, docs = happy(bands=bands)
    docs["EOSE"]["prev_close"] = 5.45
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]
    docs["EOSE"]["prev_close"] = 5.0                    # not broken -> 4% room -> skip
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"].startswith("alert gate: room 4.00% <")


def test_requires_bounce_or_demand_proximity(env):
    """Room fine, but the print sits 3% above the demand band's top with no
    bounce read -> not at a level -> skipped, no attempt."""
    br, docs = happy(print_px=5.12)          # 4.97 x 1.03
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"] == ("alert gate: not at a demand level (no bounce, no "
                                          "demand band within %g%% under the print)"
                                          % ALERT_MAX_ABOVE_DEMAND_PCT)
    _assert_never(db, enter_calls)
    # Just inside the line (0.99% above the top) passes.
    br, docs = happy(print_px=round(4.97 * 1.0099, 4))
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]
    assert enter_calls[0]["reason"]["proximity"]["band"]["lo"] == 4.80
    # Under the band floor (fell through) fails too.
    br, docs = happy(print_px=4.70)
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == []


def test_proximity_anchor_stop_under_band_floor_absolute_level(env):
    br, docs = happy()
    _, db, enter_calls, pushes, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["entered"] == ["EOSE"] and out["entries_today"] == 1
    call = enter_calls[0]
    assert call["symbol"] == "EOSE" and call["limit_price"] is None
    assert call["allow_earnings"] is False and call["top_up"] is False
    assert call["stop_price"] == pytest.approx(4.80 * (1 - ZE.STOP_BUFFER_PCT / 100.0), abs=1e-4)
    assert call["stop_pct"] == pytest.approx((5.0 - call["stop_price"]) / 5.0 * 100, abs=0.01)
    assert call["strategy"] == "catalyst"
    r = call["reason"]
    assert r["quadrant"] == "REAL" and r["grade"] == "A"
    assert r["catalyst_summary"] == "Grid storage contract award"
    assert r["price"] == 5.0 and r["dollar_volume"] == 5_000_000
    assert r["room"]["room_pct"] == 12.0 and r["bounce"] is None
    assert r["proximity"]["band"] == {"kind": "demand", "lo": 4.80, "hi": 4.97, "touches": 3}
    assert r["side"] == "demand"
    json.dumps(r, allow_nan=False)
    # Bookkeeping: state entered, ledger row, push.
    st = _state_rows(db)
    assert len(st) == 1 and st[0]["entered"] is True and st[0]["result"] == "entered"
    assert st[0]["key"] == "EOSE:%s" % DAY and st[0]["order_id"] == "o-1"
    led = _kind_rows(db, "catalyst_entry")
    assert len(led) == 1 and led[0]["dry_run"] is False
    assert led[0]["detail"]["strategy"] == "catalyst"
    assert "TLSW" not in (led[0].get("cite") or "") and "p." not in (led[0].get("cite") or "")
    assert pushes and pushes[0][0] == "EOSE" and pushes[0][1] == "paper"
    assert "EOSE" in pushes[0][2] and "4.78" in pushes[0][2]


def test_bounce_off_demand_uses_bounce_band_with_buffer(env):
    b = bounce_of(DEMAND, touch_low=4.82, bounce_pct=3.7)
    br, docs = happy(print_px=5.0, bounce=b)
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]
    assert enter_calls[0]["stop_price"] == pytest.approx(4.80 * 0.995, abs=1e-4)
    assert enter_calls[0]["reason"]["bounce"]["bounce_pct"] == 3.7
    assert enter_calls[0]["reason"]["side"] == "demand"


def test_bounce_off_broken_supply_stops_at_that_band_lo(env):
    """Pure bounce off a broken supply shelf: no demand band anchors the read,
    so the stop is the shelf's lo (no buffer) — the owner spec."""
    shelf = band("supply", 4.60, 4.75)
    b = bounce_of(shelf, touch_low=4.70, bounce_pct=1.7, role="broken_supply")
    # print 4.78 = 0.6% above the shelf top: inside the 1% proximity line
    # (review 2026-09-05 — a bounce anchor must still be AT the level).
    br, docs = happy(print_px=4.78, bands=(shelf, SUPPLY_FAR), bounce=b)
    docs["EOSE"]["prev_close"] = 4.90
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]
    assert enter_calls[0]["stop_price"] == pytest.approx(4.60, abs=1e-6)
    assert enter_calls[0]["reason"]["side"] == "broken_supply"
    assert enter_calls[0]["reason"]["proximity"]["anchor"] == "bounce"    # review 2026-09-05


def test_bounce_anchor_must_still_be_within_the_proximity_line(env):
    """REGRESSION (review 2026-09-05): a bounce read anchored the buy with NO
    proximity check, while zone_bounce_alerts gates every bounce push on
    alert_gates.demand_proximity_gate. A 3%+ lift is REQUIRED for a bounce
    read, so the print routinely sits >1% over the band top — exactly the
    "I am late" case. Phone gate = entry gate: the bounce band must still hold
    the print within ALERT_MAX_ABOVE_DEMAND_PCT of its top."""
    b95 = band("demand", 95.0, 97.0)
    far = band("supply", 110.0, 112.0)
    b = bounce_of(b95, touch_low=95.5, bounce_pct=5.8)
    br, docs = happy(print_px=101.0, bands=(b95, far), bounce=b)
    _, db, enter_calls, _, _ = env(payload=scan([cand(price=101.0)]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"] == (
        "alert gate: print 4.1%% above bounce band top 97 (max %g%%)" % ALERT_MAX_ABOVE_DEMAND_PCT)
    assert out["skipped_alert_gate"] == 1
    _assert_never(db, enter_calls)
    # 0.5% above the top: at the level -> passes, anchored to the bounce band
    br, docs = happy(print_px=97.5, bands=(b95, far), bounce=bounce_of(b95, 95.5, 2.1))
    _, db, enter_calls, _, _ = env(payload=scan([cand(price=97.5)]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]
    assert enter_calls[0]["stop_price"] == pytest.approx(95.0 * 0.995, abs=1e-4)
    assert enter_calls[0]["reason"]["proximity"] == {
        "ok": True, "band": {"kind": "demand", "lo": 95.0, "hi": 97.0, "touches": 3},
        "above_top_pct": pytest.approx(0.52, abs=0.01), "anchor": "bounce"}
    # a broken-supply shelf bounce obeys the same line
    shelf = band("supply", 90.0, 92.0)
    br, docs = happy(print_px=95.0, bands=(shelf, far),
                     bounce=bounce_of(shelf, 91.0, 4.4, role="broken_supply"))
    docs["EOSE"]["prev_close"] = 93.0
    _, db, enter_calls, _, _ = env(payload=scan([cand(price=95.0)]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"].startswith("alert gate: print 3.3% above bounce band top 92")
    _assert_never(db, enter_calls)


def test_stop_wider_than_engine_max_skips_without_attempt(env):
    """A bounce read off a WIDE band (floor 12% under the print, top within
    the 1% proximity line) -> the requested stop is past ABS_MAX_STOP_PCT ->
    skipped (never clamped, never attempted)."""
    deep = band("demand", 4.40, 4.96)
    b = bounce_of(deep, touch_low=4.42, bounce_pct=13.0)
    br, docs = happy(print_px=5.0, bands=(deep, SUPPLY_FAR), bounce=b)
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    out = CE.run()
    assert out["skipped"][0]["reason"].startswith("stop wider than engine max")
    assert "%g" % ABS_MAX_STOP_PCT in out["skipped"][0]["reason"]
    _assert_never(db, enter_calls)


# ── Cap, attempts, held ──────────────────────────────────────────────────────

def test_one_catalyst_entry_per_day(env):
    rows = [br_row(s, 5.0, room={"state": "ROOM", "room_pct": 12.0}) for s in ("AAA", "BBB")]
    docs = {s: zdoc(s, (DEMAND, SUPPLY_FAR)) for s in ("AAA", "BBB")}
    _, db, enter_calls, _, _ = env(payload=scan([cand("AAA", composite=90), cand("BBB", composite=80)]),
                                   bounce=br_payload(rows), docs=docs)
    out = CE.run()
    assert out["entered"] == ["AAA"]
    assert {"symbol": "BBB", "reason": "daily cap %d reached" % CE.MAX_CATALYST_ENTRIES_PER_DAY} in out["skipped"]
    assert len(enter_calls) == 1
    out2 = CE.run()
    assert out2["entered"] == [] and len(enter_calls) == 1
    assert out2["reason"] == "daily cap reached"


def test_already_held_and_attempted_today_are_skipped(env):
    br, docs = happy()
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs,
                                   positions=[{"symbol": "EOSE", "qty": "10",
                                               "avg_entry_price": "4.5"}])
    out = CE.run()
    assert out["skipped"] == [{"symbol": "EOSE", "reason": "already held"}]
    _assert_never(db, enter_calls)


def test_state_written_before_enter_and_unexpected_error_recorded_once(env):
    br, docs = happy()
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs,
                                   enter_raises=RuntimeError("boom"))
    out = CE.run()
    assert len(enter_calls) == 1 and out["entered"] == []
    st = _state_rows(db)
    assert len(st) == 1 and st[0]["attempted"] is True and st[0]["entered"] is False
    assert st[0]["result"] == "error" and "boom" in st[0]["reason"]
    err = _kind_rows(db, "catalyst_entry_error")
    assert len(err) == 1 and err[0]["dry_run"] is False
    assert "verify at the broker" in err[0]["detail"]["hint"]
    assert out["errors"] == ["EOSE: boom"]
    out2 = CE.run()                                   # never retried the same day
    assert len(enter_calls) == 1
    assert out2["skipped"] == [{"symbol": "EOSE", "reason": "attempted today"}]


def test_enter_veto_recorded_blocked_and_not_retried(env):
    br, docs = happy()
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs,
                                   enter_raises=ValueError("earnings in 3d (2026-09-08)"))
    out = CE.run()
    assert out["blocked"] == ["EOSE"] and out["entered"] == []
    st = _state_rows(db)[0]
    assert st["result"] == "blocked" and "earnings" in st["reason"]
    blk = _kind_rows(db, "catalyst_entry_blocked")
    assert len(blk) == 1 and blk[0]["dry_run"] is True
    CE.run()
    assert len(enter_calls) == 1


def test_market_closed_veto_is_not_an_attempt(env):
    br, docs = happy()
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs,
                                   enter_raises=ValueError("market closed — market entries blocked"))
    out = CE.run()
    assert out["skipped"] == [{"symbol": "EOSE", "reason": "market closed"}]
    assert _state_rows(db) == []


def test_state_unreadable_fails_closed(env, monkeypatch):
    br, docs = happy()
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    monkeypatch.setattr(CE, "_entered_today", lambda day: None)
    out = CE.run()
    assert out["ok"] is False and out["reason"] == "state_unavailable"
    assert enter_calls == []


def test_state_write_failure_means_no_order(env, monkeypatch):
    br, docs = happy()
    _, db, enter_calls, _, _ = env(payload=scan([cand()]), bounce=br, docs=docs)
    monkeypatch.setattr(CE, "_set_state", lambda key, **f: False)
    out = CE.run()
    assert enter_calls == [] and out["ok"] is False
    assert out["skipped"] == [{"symbol": "EOSE", "reason": "state write failed (not attempted)"}]


# ── Status block + wiring ────────────────────────────────────────────────────

def test_status_block_shape(env):
    _, db, _, _, _ = env(payload=scan([cand("AAA"), cand("BBB", quadrant="PUMP_RISK")]))
    blk = CE.status_block(EE.get_config())
    assert blk["enabled"] is True and blk["entries_today"] == 0
    assert blk["max_per_day"] == 1 and blk["last_entry_et"] == "15:45"
    assert blk["as_of"] == "2026-09-05T14:20:00+00:00"
    assert blk["scan"] == {"cached": True, "cache_age_sec": 60, "n_total": 2}
    assert [c["symbol"] for c in blk["candidates"]] == ["AAA"]
    assert blk["skipped"] == [{"symbol": "BBB", "reason": "quadrant PUMP_RISK"}]
    assert blk["attempts"] == []
    assert blk["paper_only"] is True                      # FakeBroker mode "paper"
    rules = blk["rules"]
    assert all(set(r) >= {"rule", "value", "source"} for r in rules)
    srcs = " ".join(r["source"] for r in rules)
    assert "owner" in srcs and "NOT from Ajay" in srcs and "risk_rules" in srcs
    assert not any(re.search(r"\bpp?\.\s?\d", r["rule"] + r["source"]) for r in rules)
    json.dumps(blk, allow_nan=False)
    _, db, _, _, _ = env(payload=None, flag=False)
    blk = CE.status_block(EE.get_config())
    assert blk["enabled"] is False and blk["as_of"] is None and blk["candidates"] == []
    assert blk["scan"] is None


def test_paper_only_is_derived_from_the_broker_mode_not_hardcoded(env):
    """review 2026-09-05: the honesty label must come from the account."""
    _, db, _, _, _ = env(payload=None, mode="live")
    assert CE.status_block(EE.get_config())["paper_only"] is False
    _, db, _, _, _ = env(payload=None, mode="sim")
    assert CE.status_block(EE.get_config())["paper_only"] is True
    src = open(CE.__file__, encoding="utf-8").read()
    assert '"paper_only": True' not in src


def test_engine_status_carries_block_and_degrades(env, monkeypatch):
    _, db, _, _, _ = env(payload=None)
    out = EE.status()
    assert out["catalyst_entry"]["enabled"] is True
    assert out["catalyst_entry"]["max_per_day"] == 1

    def boom(cfg=None):
        raise RuntimeError("status boom")

    monkeypatch.setattr(CE, "status_block", boom)
    out = EE.status()
    assert out["catalyst_entry"] == {"enabled": True, "error": "status boom"}


def test_config_default_off_and_api_accepts_flag(env):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    _, db, _, _, _ = env(payload=None, flag=False)
    db.trading_config.rows[0].pop("catalyst_entry", None)
    assert EE.get_config()["catalyst_entry"] is False        # default OFF in every mode
    resp = asyncio.run(TA.trading_config({"catalyst_entry": True}, email=admin))
    assert json.loads(resp.body) == {"catalyst_entry": True}
    assert EE.get_config()["catalyst_entry"] is True
    assert _kind_rows(db, "config_update")[-1]["detail"]["catalyst_entry"] is True
    resp = asyncio.run(TA.trading_config({"catalyst_entry": None}, email=admin))
    assert json.loads(resp.body) == {"catalyst_entry": False}
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({"catalyst_entry": "yes"}, email=admin))
    assert exc.value.status_code == 400
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({"catalyst_entry": True}, email="nobody@example.com"))
    assert exc.value.status_code == 403


def test_tick_step_j_fenced_after_h(monkeypatch):
    path = os.path.join(os.path.dirname(__file__), "..", "trading", "exit_engine.py")
    with open(path, encoding="utf-8") as fh:
        eng = fh.read()
    hook = ('    try:\n'
            '        from trading import catalyst_entry\n'
            '        summary["catalyst_entry"] = catalyst_entry.run(broker=broker,\n'
            '                                                       cfg=get_config())\n'
            '    except Exception as exc:')
    assert hook in eng, "tick step (j) catalyst_entry.run missing or not fenced like (h)"
    assert eng.index('summary["zone_edge_entry"] = zone_edge_entry.run(') \
        < eng.index('summary["catalyst_entry"] = catalyst_entry.run(') \
        < eng.index('summary["journal"] = journal.reconcile()')
    assert '"catalyst_entry": bool(doc.get("catalyst_entry", False))' in eng
    assert 'out["catalyst_entry"] = catalyst_entry.status_block(cfg)' in eng


def test_never_calls_the_broker_directly_and_cites_no_book():
    path = os.path.join(os.path.dirname(__file__), "..", "trading", "catalyst_entry.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    for forbidden in ("submit_", "replace_order", "cancel_order", "close_position",
                      "_full_scan(", "scan_catalysts("):
        assert forbidden not in src, forbidden
    assert "entries.enter(" in src
    assert "_cache_get()" in src                    # cached scan only
    assert "TLSW" not in src and "TTLAC" not in src and "Minervini" not in src.replace(
        "NOT Minervini", "").replace("not Minervini", "")
    assert re.search(r"\bpp?\.\s?\d", src) is None
    assert "OWNER" in src
    assert "alert_gates.room_gate(" in src and "alert_gates.demand_proximity_gate(" in src
    assert "ALPACA_PAPER" not in src
    # review 2026-09-05: the tick reads Mongo docs + the cached scan ONLY —
    # never the tape, never the on-demand zone builder.
    for forbidden in ("api_payload", "queue_ondemand", "bulk_snapshot", "load_prices(",
                      "build_doc(", "sepa.prices", "from sepa", "background="):
        assert forbidden not in src, forbidden
    assert "bounce_room.load_docs(" in src and "bounce_room.read_symbol(" in src



# ── warm (cron) — the lane's two inputs get populated outside the tick ──────
def test_warm_reuses_a_fresh_cached_scan_and_builds_only_missing_docs():
    calls = {"scan": 0, "put": 0, "batch": []}
    payload = {"candidates": [{"ticker": "eose"}, {"ticker": "CLYM"}, {"ticker": "CLYM"}, {"x": 1}]}

    def scan_fn(**kw):
        calls["scan"] += 1
        return payload

    def cache_put(p):
        calls["put"] += 1

    def load_docs(tickers, day):
        assert tickers == ["CLYM", "EOSE"]
        return {"CLYM": {"bands": []}}, ["EOSE"]

    def compute_batch(syms, day):
        calls["batch"].append(list(syms))
        return {"built": 1}

    with_now = datetime(2026, 9, 8, 10, 12, tzinfo=CE.ET)
    orig = CE._store_day
    CE._store_day = lambda now_et: date(2026, 9, 8)
    try:
        out = CE.warm(with_now, cached=lambda: payload, scan_fn=scan_fn, cache_put=cache_put,
                      load_docs=load_docs, compute_batch=compute_batch)
    finally:
        CE._store_day = orig
    assert out["scan"] == "cached" and calls["scan"] == 0 and calls["put"] == 0
    assert out["candidates"] == 2 and out["docs_have"] == 1
    assert out["docs_missing"] == 1 and out["docs_built"] == 1
    assert calls["batch"] == [["EOSE"]]
    assert out["error"] is None


def test_warm_runs_the_boards_scan_with_the_review_when_the_cache_is_cold_and_never_raises():
    seen = {}

    def scan_fn(**kw):
        seen.update(kw)
        return {"candidates": [{"ticker": "EOSE"}]}

    puts = []
    orig = CE._store_day
    CE._store_day = lambda now_et: date(2026, 9, 8)
    try:
        out = CE.warm(datetime(2026, 9, 8, 10, 42, tzinfo=CE.ET), cached=lambda: None,
                      scan_fn=scan_fn, cache_put=puts.append,
                      load_docs=lambda t, d: ({}, ["EOSE"]),
                      compute_batch=lambda s, d: {"built": 1})
        assert out["scan"] == "ran" and seen == {"with_gemma": True} and len(puts) == 1
        assert out["docs_built"] == 1 and out["error"] is None

        def boom(**kw):
            raise RuntimeError("massive down")
        out2 = CE.warm(datetime(2026, 9, 8, 10, 42, tzinfo=CE.ET), cached=lambda: None,
                       scan_fn=boom, cache_put=puts.append,
                       load_docs=lambda t, d: ({}, []), compute_batch=lambda s, d: {})
        assert out2["error"] == "massive down" and out2["candidates"] == 0
    finally:
        CE._store_day = orig


def test_warm_cron_line_is_in_the_crontab_and_pinned():
    crontab = (pathlib.Path(__file__).resolve().parents[1] / "crontab").read_text()
    assert CE.WARM_CRON == "12,42 9-15 * * 1-5"
    line = [ln for ln in crontab.splitlines() if "trading.catalyst_entry --warm" in ln]
    assert len(line) == 1, "exactly one catalyst warm cron line"
    assert line[0].split("/usr/local/bin/python")[0].split() == CE.WARM_CRON.split()


# ── size + sales gates (Ajay 2026-09-06: ">700 mil enterprise value and also, Sales are intact") ──
def test_size_and_sales_gates_pure():
    assert CE.CATALYST_MIN_EV_USD == 700_000_000.0
    from sepa.sales import BONDE_PASS_TIERS
    assert CE.SALES_PASS_TIERS == BONDE_PASS_TIERS
    assert CE.size_gate({"enterprise_value": 7.0e8, "market_cap": 1e9}) is None
    assert CE.size_gate({"enterprise_value": 6.99e8, "market_cap": 9e9}).startswith("enterprise value $699M < $700M")
    assert CE.size_gate({"enterprise_value": None, "market_cap": 8.0e8}) is None, "EV unknown: market cap stands in"
    assert CE.size_gate({"market_cap": 3.0e8}).startswith("market cap $300M < $700M (EV unknown)")
    assert CE.size_gate({"market_cap": None}) == "enterprise value and market cap unknown"
    assert CE.sales_gate({"tier": "strong", "score": 80, "growth_yoy_pct": 40.0}) is None
    assert CE.sales_gate({"tier": "explosive", "score": 90}) is None
    assert CE.sales_gate({"tier": "declining", "score": 20, "growth_yoy_pct": -12.0}) == "sales declining (-12% YoY) — not intact"
    assert CE.sales_gate({"tier": "weak", "score": 30}) == "sales weak — not intact"
    assert CE.sales_gate(None) == "sales unknown (no research snapshot)"
    assert CE.sales_gate({"tier": "steady"}) == "sales unknown (no research snapshot)", "no score = never computed"
    # the scan row carries EV (scanner._enrich_with_yfinance) and the funnel keeps it
    c = CE._candidate(dict(cand(), enterprise_value="850000000"))
    assert c["enterprise_value"] == 8.5e8
    # the tick reads sales CACHE-ONLY: promo_circuit.sales_for with cap=0
    import inspect
    assert "_promo_sales(syms, cap=0)" in inspect.getsource(CE.sales_for)
    assert "_promo_sales(tickers)" in inspect.getsource(CE.warm), "the warm is where the fetch happens"


def test_small_ev_or_broken_sales_skip_before_the_zone_read(env):
    bounce, docs = happy()
    small = scan([dict(cand(), enterprise_value=4.5e8)])
    fake, db, enter_calls, _, calls = env(payload=small, bounce=bounce, docs=docs)
    out = CE.run()
    assert enter_calls == [] and out["skipped_size"] == 1 and calls["docs"] == []
    assert out["skipped"][0] == {"symbol": "EOSE", "reason": "enterprise value $450M < $700M"}
    big = scan([dict(cand(), enterprise_value=2.1e9)])
    fake, db, enter_calls, _, calls = env(payload=big, bounce=bounce, docs=docs,
                                          sales={"tier": "declining", "score": 15, "growth_yoy_pct": -30.0})
    out = CE.run()
    assert enter_calls == [] and out["skipped_sales"] == 1 and calls["docs"] == []
    assert out["skipped"][0]["reason"] == "sales declining (-30% YoY) — not intact"
    fake, db, enter_calls, _, calls = env(payload=big, bounce=bounce, docs=docs, sales={})
    out = CE.run()
    assert out["skipped_sales"] == 1 and "sales unknown" in out["skipped"][0]["reason"]
    # EV unknown + market cap over the line + sales intact: the zone read runs as before
    capped = scan([dict(cand(), enterprise_value=None, market_cap=9.0e8)])
    fake, db, enter_calls, _, calls = env(payload=capped, bounce=bounce, docs=docs,
                                          sales={"tier": "strong", "score": 85, "growth_yoy_pct": 44.0})
    out = CE.run()
    assert out["entered"] == ["EOSE"] and out["skipped_size"] == 0 and out["skipped_sales"] == 0
    rules = " ".join(r["rule"] for r in CE.rules_list())
    assert "Enterprise value at least $700M" in rules and "Sales intact" in rules
