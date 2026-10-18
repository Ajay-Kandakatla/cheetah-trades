"""🎚️ tape_control (2026-10-16) — "buyers in control on the tape" for pinned names.

Ajay 2026-10-16: "Can you add a watcher tape for IREN please." then "I wwant you to alert me
when the Buyers are winning in tape for IREN today."

Hermetic: stub Mongo, stub HTTP, synthetic tapes through the REAL tape.analyze_tape and the
REAL signals.delta_check (check 3 by call). No network, no real Mongo.
"""
import copy
import inspect
import io
import re
import sys
import tokenize
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import signals as SG            # noqa: E402
from orderflow import tape as TP               # noqa: E402
from orderflow import tape_burst_kinds as TBK  # noqa: E402
from orderflow import tape_control as TC       # noqa: E402
from orderflow import trade_flash as TF        # noqa: E402

ET = ZoneInfo("America/New_York")
DAY = "2026-10-16"                                  # a Friday, NYSE open
NOW = datetime(2026, 10, 16, 10, 12, tzinfo=ET)
SRC = Path(TC.__file__).read_text()
# Assembled so the words never sit in this file as written words.
BANNED = re.compile("|".join(["b" + "oun", "f" + "ake", r"\bbuy\b", r"\benter", "sha" + "dow"]), re.I)


# ── stubs ────────────────────────────────────────────────────────────────────
class Res:
    def __init__(self, upserted_id=None, modified_count=0):
        self.upserted_id, self.modified_count = upserted_id, modified_count


def _match(doc, q):
    for k, v in (q or {}).items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class StubColl:
    def __init__(self, db, docs=()):
        self.db, self.docs = db, {d["_id"]: copy.deepcopy(d) for d in docs}
        self.finds = 0
        self.lose_race = False
        self.raise_dup = False

    def find_one(self, q, proj=None):
        self.finds += 1
        self.db.reads += 1
        d = self.docs.get(q.get("_id"))
        return copy.deepcopy(d) if d else None

    def find(self, q=None, proj=None):
        self.db.reads += 1
        return [copy.deepcopy(d) for d in self.docs.values() if _match(d, q)]

    def update_one(self, q, u, upsert=False):
        self.db.writes += 1
        if self.raise_dup:
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("E11000 duplicate key")
        _id = q["_id"]
        if "$setOnInsert" in u:
            if _id in self.docs:
                return Res(None, 0)
            self.docs[_id] = {"_id": _id, **copy.deepcopy(u["$setOnInsert"])}
            return Res(_id, 0)
        doc = self.docs.get(_id)
        if doc is None or self.lose_race or not _match(doc, {k: v for k, v in q.items() if k != "_id"}):
            return Res(None, 0)
        for k, v in u["$set"].items():
            doc[k] = copy.deepcopy(v)
        return Res(None, 1)

    def replace_one(self, q, doc, upsert=False):
        self.db.writes += 1
        self.docs[q["_id"]] = copy.deepcopy(doc)


class StubDB:
    def __init__(self):
        self.reads = self.writes = 0
        self.colls = {}

    def __getitem__(self, name):
        if name not in self.colls:
            self.colls[name] = StubColl(self)
        return self.colls[name]


class BrokenColl:
    def find(self, *a, **k):
        raise RuntimeError("mongo down")

    find_one = update_one = find


def tape(direction=+1, n=11, step_min=7, start=(9, 0), late_down=False):
    """A synthetic regular-print tape on DAY: n prints step_min apart from `start` ET, prices
    moving one cent per print in `direction`; `late_down` turns the last 5 prints down."""
    t0 = datetime(2026, 10, 16, start[0], start[1], tzinfo=ET)
    idx = pd.DatetimeIndex([pd.Timestamp(t0) + pd.Timedelta(minutes=step_min * i) for i in range(n)]
                           ).tz_convert("UTC")
    px, p = [], 10.0
    for i in range(n):
        if i:
            d = direction
            if late_down and i >= n - 5:
                d = -1
            p = round(p + 0.01 * d, 2)
        px.append(p)
    df = pd.DataFrame({"price": px, "size": [100] * n, "kind": ["regular"] * n}, index=idx)
    df.index.name = "ts_utc"
    df.attrs["truncated"] = False
    return df


def read(in_control=True, at="2026-10-16T10:12:00-04:00", hhmm="10:12", hms="10:12:00",
         delta=1000, late=500, pct=90.9, price=10.10, last="10:10:00"):
    return {"at": at, "hhmm": hhmm, "hms": hms, "in_control": in_control, "delta": delta,
            "late_delta": late, "pct": pct, "late_window_min": TP.LATE_WINDOW_MIN,
            "n_trades": 11, "price": price, "last_print_et": last, "method": "tick"}


W2_UP_FIRST = ("IREN · session delta +90.9% of volume (+1,000 shares), last 30 min +500 shares · "
               "$10.10 · 10:12 ET · first read today · tick rule (the Tape tab's quote-rule read can differ)")


def at(h, m, d=16):
    return datetime(2026, 10, d, h, m, tzinfo=ET)


def run(db, now=NOW, frame=None, **kw):
    calls = kw.pop("calls", None)

    def fetch(sym, day):
        if calls is not None:
            calls.append((sym, day))
        return frame if frame is not None else tape(+1)
    kw.setdefault("status_fn", lambda *a, **k: None)
    return TC.run_pass(now=now, db=db, fetch_fn=kw.pop("fetch_fn", fetch), **kw)


@pytest.fixture
def owner_push(monkeypatch):
    """TF._db → one StubDB (state + events), sender.send_to_user → a spy."""
    db = StubDB()
    sent = []
    result = {"sent": 1, "failed": 0, "total_targets": 1}
    from push import sender

    def spy(email, payload, kind=None):
        sent.append((email, payload, kind))
        if isinstance(result.get("raise"), Exception):
            raise result["raise"]
        return dict(result)
    monkeypatch.setattr(TF, "_db", lambda: db)
    monkeypatch.setattr(sender, "send_to_user", spy)
    monkeypatch.setattr(TC, "WATCH", {"IREN": DAY})
    return db, sent, result


# ── decide: every edge (BUILD_SPEC7 §3.3) ────────────────────────────────────
NO_DOC = object()


@pytest.mark.parametrize("edge,prev_in,rd,ring,new_in,since_moves,faults", [
    ("E1", NO_DOC, None, False, None, False, 1),
    ("E2", NO_DOC, True, True, True, True, 0),
    ("E3", NO_DOC, False, False, False, True, 0),
    ("E4", None, None, False, None, False, 3),
    ("E5", None, True, True, True, True, 2),
    ("E6", None, False, False, False, True, 2),
    ("E7", False, True, True, True, True, 2),
    ("E8", False, False, False, False, False, 2),
    ("E9", False, None, False, False, False, 3),
    ("E10", True, True, False, True, False, 2),
    ("E11", True, False, False, False, True, 2),
    ("E12", True, None, False, True, False, 3),
])
def test_decide_every_edge(edge, prev_in, rd, ring, new_in, since_moves, faults):
    prev = None if prev_in is NO_DOC else {
        "in_control": prev_in, "since": "OLD", "since_hhmm": "09:40", "faults": 2,
        "rings": [{"at": "OLD", "hhmm": "09:40", "pushed": True}] if prev_in else []}
    r = None if rd is None else read(in_control=rd)
    s, rang = TC.decide(prev, r)
    assert rang is ring, edge
    assert s["in_control"] is new_in, edge
    if since_moves:
        assert s["since"] == r["at"] and s["since_hhmm"] == "10:12", edge
    else:
        assert s["since"] == (None if prev is None else "OLD"), edge
    assert s["faults"] == faults, edge


def test_decide_first_true_poll_of_the_day_rings():
    s, ring = TC.decide(None, read(True))
    assert ring is True and s["rings"] == [{"at": read()["at"], "hhmm": "10:12",
                                           "first_read": True, "retry": False}]
    assert s["first_read"] is True


def test_NEGATIVE_no_ring_while_sellers_lead():
    d = {"delta": -1000, "late_delta": 500, "late_window_min": 30}
    assert SG.delta_check(d)["pass"] is False
    s, ring = TC.decide(None, read(in_control=SG.delta_check(d)["pass"], delta=-1000))
    assert ring is False and s["in_control"] is False


def test_NEGATIVE_session_up_but_last_30_down_is_not_in_control(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": DAY})
    d = {"delta": 1000, "late_delta": -1, "late_window_min": 30}
    assert SG.delta_check(d)["pass"] is False
    s, ring = TC.decide(None, read(in_control=False, delta=1000, late=-1))
    assert ring is False
    state, text = TC.pin_text(TC.pins_for(DAY)[0], {**s, "date": DAY}, NOW)
    assert state == "not_in_control" and text.startswith("sellers took the last 30 min since 10:12 ET")


def test_the_edges_are_check_3s():
    flat = {"delta": 0, "late_delta": 0, "late_window_min": 30}
    edge = {"delta": 1, "late_delta": 0, "late_window_min": 30}
    assert SG.delta_check(flat)["pass"] is False           # the session's `>`
    assert SG.delta_check(edge)["pass"] is True            # the last 30 min's `>=`
    for d, want in ((flat, False), (edge, True)):
        r, f = TC.read_tape("IREN", date(2026, 10, 16), at=NOW, fetch_fn=lambda s, dd: tape(+1),
                            analyze_fn=lambda t, d=d: {"delta": {**d, "delta_pct_of_volume": 0.0,
                                                                 "n_trades": 5},
                                                       "last_price": 10.0,
                                                       "classification": {"method": "tick"}})
        assert f is None and r["in_control"] is want


def test_NEGATIVE_no_second_ring_while_it_holds():
    s, rings = None, 0
    for _ in range(3):
        s, ring = TC.decide(s, read(True))
        rings += ring
    assert rings == 1 and len(s["rings"]) == 1


def test_rearm_then_ring_again():
    s, r1 = TC.decide(None, read(True, at="A1", hhmm="10:12"))
    s, r2 = TC.decide(s, read(False, at="A2", hhmm="10:17", delta=-5))
    assert s["since"] == "A2"
    s, r3 = TC.decide(s, read(True, at="A3", hhmm="10:22"))
    assert (r1, r2, r3) == (True, False, True)
    assert s["since"] == "A3" and len(s["rings"]) == 2
    assert s["rings"][1]["first_read"] is False and s["first_read"] is False


def test_NEGATIVE_a_fault_never_rings_and_never_rearms():
    s, a = TC.decide(None, read(True))
    s, b = TC.decide(s, None)
    assert s["in_control"] is True
    s, c = TC.decide(s, read(True))
    assert (a, b, c) == (True, False, False) and len(s["rings"]) == 1
    s, _ = TC.decide(None, read(False))
    s, d = TC.decide(s, None)
    assert d is False and s["in_control"] is False and s["faults"] == 1


def test_NEGATIVE_first_poll_fault_then_true_rings_once():
    s, a = TC.decide(None, None)
    assert s["in_control"] is None and s["faults"] == 1
    s, b = TC.decide(s, read(True))
    s, c = TC.decide(s, read(True))
    assert (a, b, c) == (False, True, False) and s["first_read"] is True


def test_decide_is_pure():
    prev = {"in_control": False, "since": "X", "rings": [{"at": "X", "hhmm": "09:40", "pushed": True}],
            "faults": 1}
    r = read(True)
    p0, r0 = copy.deepcopy(prev), copy.deepcopy(r)
    TC.decide(prev, r)
    TC.decide(prev, None)
    TC.apply_outcome({**prev, "push_attempts": 0}, False, "not_sent")
    assert prev == p0 and r == r0


# ── the read ─────────────────────────────────────────────────────────────────
def test_read_calls_fetch_trades_with_the_ET_session_day_and_analyze_without_quotes():
    seen, analyzed = [], []
    late_utc = datetime(2026, 10, 17, 0, 30, tzinfo=timezone.utc)      # 20:30 ET on 10-16
    sig = inspect.signature(TC.read_tape)
    assert sig.parameters["analyze_fn"].default is None

    def spy_analyze(*a, **k):
        analyzed.append((a, k))
        return TP.analyze_tape(*a, **k)
    r, f = TC.read_tape("IREN", late_utc.astimezone(ET).date(), at=late_utc,
                        fetch_fn=lambda s, d: seen.append((s, d)) or tape(+1), analyze_fn=spy_analyze)
    assert seen == [("IREN", date(2026, 10, 16))]
    assert len(analyzed) == 1 and len(analyzed[0][0]) == 1 and analyzed[0][1] == {}
    assert f is None and r["method"] == "tick" and r["hhmm"] == "20:30"
    assert "analyze_fn or TP.analyze_tape" in inspect.getsource(TC.read_tape)


def test_the_pass_reads_the_ET_session_day_not_the_UTC_date(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": DAY})
    seen = []
    late_utc = datetime(2026, 10, 17, 0, 30, tzinfo=timezone.utc)      # 20:30 ET on 10-16
    r = TC.run_pass(now=late_utc, dry_run=True, db=StubDB(), record_fn=lambda e, **k: {"would_push": 1},
                    fetch_fn=lambda s, d: seen.append((s, d)) or tape(+1))
    assert seen == [("IREN", date(2026, 10, 16))] and r["active"] == 1


def test_read_numbers_come_from_the_real_tape_engine():
    r, f = TC.read_tape("IREN", date(2026, 10, 16), at=NOW, fetch_fn=lambda s, d: tape(+1))
    assert f is None
    assert (r["delta"], r["late_delta"], r["pct"], r["price"], r["last_print_et"], r["n_trades"]) == (
        1000, 500, 90.9, 10.10, "10:10:00", 11)
    assert r["in_control"] is True and r["late_window_min"] == TP.LATE_WINDOW_MIN


def test_read_is_check_3_by_call(monkeypatch):
    r1, _ = TC.read_tape("IREN", date(2026, 10, 16), at=NOW, fetch_fn=lambda s, d: tape(+1))
    monkeypatch.setattr(SG, "delta_check", lambda d: {"pass": not (d["delta"] > 0 and d["late_delta"] >= 0)})
    r2, _ = TC.read_tape("IREN", date(2026, 10, 16), at=NOW, fetch_fn=lambda s, d: tape(+1))
    assert r1["in_control"] is True and r2["in_control"] is False


def test_NEGATIVE_read_faults():
    d = date(2026, 10, 16)
    assert TC.read_tape("IREN", d, at=NOW, fetch_fn=lambda s, dd: None) == (None, "no_prints")

    def boom(s, dd):
        raise RuntimeError("http")
    assert TC.read_tape("IREN", d, at=NOW, fetch_fn=boom) == (None, "error")
    cut = tape(+1)
    cut.attrs["truncated"] = True
    assert TC.read_tape("IREN", d, at=NOW, fetch_fn=lambda s, dd: cut) == (None, "truncated")
    nf = tape(+1)
    nf["kind"] = "non_flow"
    assert TC.read_tape("IREN", d, at=NOW, fetch_fn=lambda s, dd: nf) == (None, "no_regular")

    def limited(s, dd):
        raise TC.RateLimited(s)
    assert TC.read_tape("IREN", d, at=NOW, fetch_fn=limited) == (None, "rate_limited")
    assert TC.read_tape("IREN", d, at=NOW, fetch_fn=lambda s, dd: tape(+1),
                        analyze_fn=lambda t: 1 / 0) == (None, "error")


def test_late_window_is_tape_LATE_WINDOW_MIN(monkeypatch):
    monkeypatch.setattr(TP, "LATE_WINDOW_MIN", 45)
    r, _ = TC.read_tape("IREN", date(2026, 10, 16), at=NOW, fetch_fn=lambda s, d: tape(+1))
    assert r["late_window_min"] == 45
    assert "last 45 min" in TC.headline({**r, "symbol": "IREN"})


# ── A4: the opt-in 429 cap in tape.fetch_trades ──────────────────────────────
class _R:
    def __init__(self, code, body=None):
        self.status_code, self._b, self.text = code, body or {}, ""

    def json(self):
        return self._b


def _ok_body():
    ns = int(datetime(2026, 10, 16, 10, 0, tzinfo=ET).timestamp() * 1e9)
    return {"results": [{"sip_timestamp": ns + i * 1_000_000_000, "price": 10.0 + i / 100,
                         "size": 100, "conditions": None} for i in range(5)]}


@pytest.fixture
def http(monkeypatch):
    import massive_keys
    import requests
    calls, sleeps, plan = [], [], {"n429": 50}   # critic 2026-10-16: a finite default so a lost cap fails fast instead of hanging
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: "k")
    monkeypatch.setattr(TP.time, "sleep", lambda s: sleeps.append(s))
    from orderflow import massive_pages as MP
    # 2026-10-18 (DECISIONS14 D6): ONE window here so the exact call / sleep counts of the serial
    # contract hold; the parallel semantics live in test_tape_parallel_fetch_2026_10_18.py
    monkeypatch.setattr(MP, "WINDOW_EDGES_ET", ("04:00", "20:00"))

    def get(url, params=None, timeout=None):
        calls.append(url)
        if len(calls) <= plan["n429"]:
            return _R(429)
        return _R(200, _ok_body())
    monkeypatch.setattr(requests, "get", get)
    return calls, sleeps, plan


def test_NEGATIVE_a_429_storm_gives_up_after_exactly_max_429_retries(http):
    calls, sleeps, _ = http
    assert TP.fetch_trades("IREN", date(2026, 10, 16), max_429=TC.MAX_429) is None
    assert len(calls) == TC.MAX_429 + 1 and len(sleeps) == TC.MAX_429
    assert TP.last_fetch_fault() == "rate_limited"


def test_the_capped_read_names_the_429_fault(http):
    r, f = TC.read_tape("IREN", date(2026, 10, 16), at=NOW)
    assert (r, f) == (None, "rate_limited") and TC.FAULT_WORDS[f]


def test_the_default_path_still_retries_429_uncapped(http):
    calls, sleeps, plan = http
    plan["n429"] = 12
    df = TP.fetch_trades("IREN", date(2026, 10, 16))
    assert df is not None and len(df) == 5 and len(sleeps) == 12
    assert TP.last_fetch_fault() is None
    assert inspect.signature(TP.fetch_trades).parameters["max_429"].default is None


def test_NEGATIVE_a_429_under_the_cap_still_reads(http):
    calls, sleeps, plan = http
    plan["n429"] = TC.MAX_429
    df = TP.fetch_trades("IREN", date(2026, 10, 16), max_429=TC.MAX_429)
    assert df is not None and TP.last_fetch_fault() is None


# ── pins ─────────────────────────────────────────────────────────────────────
def test_NEGATIVE_an_expired_pin_is_never_fetched(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": "2026-10-15"})
    db, calls, recorded = StubDB(), [], []
    r = run(db, calls=calls, status_fn=lambda *a, **k: recorded.append((a, k)))
    assert calls == [] and db.reads == 0 and db.writes == 0
    assert (r["expired"], r["active"], r["pins"]) == (1, 0, 1)
    assert r["reason"] == TC.REASON_NO_PIN and r["ran"] is True
    assert recorded and recorded[0][1]["reason"] == TC.REASON_NO_PIN


def test_a_standing_pin_is_active():
    assert TC.pins_for("2099-01-01", {"NBIS": None}) == [{"symbol": "NBIS", "until": None, "active": True}]


def test_pins_for_sorts_and_compares_iso():
    p = TC.pins_for("2026-10-16", {"ZZ": "2026-10-16", "AA": "2026-10-15", "MM": "2026-10-17"})
    assert [x["symbol"] for x in p] == ["AA", "MM", "ZZ"]
    assert [x["active"] for x in p] == [False, True, True]


def test_NEGATIVE_selected():
    assert TC.selected("tape_burst_highbeta") is False
    assert TC.selected(["tape_burst_chartmaps"]) is False
    for k in (None, "all", "", "tape_control", "tape_burst_highbeta,tape_control",
              ["tape_control"], " tape_control "):
        assert TC.selected(k) is True, k


def test_watch_symbols_are_tickers_and_dates_are_iso():
    assert TC.WATCH
    for k, v in TC.WATCH.items():
        assert re.fullmatch(r"[A-Z]{1,5}", k)
        assert v is None or date.fromisoformat(v)


# ── the pass ─────────────────────────────────────────────────────────────────
def test_a_ring_is_one_owner_push_through_record_and_push(owner_push):
    db, sent, _ = owner_push
    r = run(db, poll_ts=1)
    assert r["ran"] is True and (r["read"], r["in_control"], r["rang"], r["pushed"]) == (1, 1, 1, 1)
    assert len(sent) == 1
    email, payload, kind = sent[0]
    assert email == TF._owner_email() and kind == "tape_control" == payload["kind"]
    assert payload["title"] == "\U0001F39A️ IREN — buyers in control on the tape"
    assert payload["body"] == W2_UP_FIRST
    assert payload["url"] == "/sepa/IREN?tab=tape&from=alerts"
    assert payload["items"] == [{"symbol": "IREN", "text": W2_UP_FIRST}]
    evs = db[TC.EVENTS_COLL].docs
    assert list(evs) == [TF.event_id("IREN", DAY, "10:12:00")]
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["rev"] == 1 and st["rings"][0]["pushed"] is True and st["rang"] is True
    assert st["rings"][0]["event_id"] == TF.event_id("IREN", DAY, "10:12:00")


def test_NEGATIVE_a_held_read_sends_nothing_on_the_next_poll(owner_push):
    db, sent, _ = owner_push
    run(db, poll_ts=1)
    r = run(db, now=at(10, 17), poll_ts=2)
    assert len(sent) == 1 and r["rang"] == 0 and r["in_control"] == 1
    assert db[TC.STATE_COLL].docs["IREN:" + DAY]["rev"] == 2


def test_NEGATIVE_dry_run_writes_nothing_sends_nothing_records_no_pass(owner_push):
    db, sent, _ = owner_push
    recorded = []
    r = run(db, dry_run=True, status_fn=lambda *a, **k: recorded.append(a))
    assert db.writes == 0 and sent == [] and recorded == []
    assert r["dry_run"] is True and r["would_push"] == 1
    assert r["reads"][0]["would_ring"] is True and r["reads"][0]["symbol"] == "IREN"
    assert r["reads"][0]["text"].startswith("buyers led at the first read today 10:12 ET")


def test_NEGATIVE_a_lost_race_never_rings(owner_push):
    db, sent, _ = owner_push
    db[TC.STATE_COLL].docs["IREN:" + DAY] = {"_id": "IREN:" + DAY, "rev": 4, "in_control": False,
                                             "date": DAY, "kind": TC.KIND, "symbol": "IREN"}
    db[TC.STATE_COLL].lose_race = True
    r = run(db)
    assert r["lost_race"] == 1 and r["rang"] == 0 and sent == []
    assert db[TC.EVENTS_COLL].docs == {}


def test_NEGATIVE_a_duplicate_key_on_the_first_claim_is_a_lost_race(owner_push):
    db, sent, _ = owner_push
    db[TC.STATE_COLL].raise_dup = True
    r = run(db)
    assert r["lost_race"] == 1 and r["rang"] == 0 and sent == []


def test_NEGATIVE_mongo_down_never_rings(owner_push, monkeypatch):
    _, sent, _ = owner_push
    monkeypatch.setattr(TF, "_db", lambda: None)
    calls = []
    r = TC.run_pass(now=NOW, fetch_fn=lambda s, d: calls.append(s) or tape(+1),
                    status_fn=lambda *a, **k: None)
    assert calls == [] and sent == [] and r["reason"] == TC.REASON_NO_MONGO
    assert r["ran"] is False and r["faults"] == 1


def test_NEGATIVE_a_broken_state_read_never_fetches_never_rings(owner_push):
    _, sent, _ = owner_push

    class DB:
        def __getitem__(self, name):
            return BrokenColl()
    calls = []
    r = run(DB(), calls=calls)
    assert calls == [] and sent == [] and r["ran"] is False and r["reason"] == TC.FAULT_WORDS["no_mongo"]


def test_NEGATIVE_the_budget_guard_is_a_fault_not_a_false(owner_push):
    db, sent, _ = owner_push
    run(db, poll_ts=1)
    assert len(sent) == 1
    calls = []
    r = run(db, now=at(10, 17), calls=calls, started=0.0, clock=lambda: float(TC.START_BY_SEC))
    assert calls == [] and r["skipped_budget"] == 1 and r["faults"] == 1 and r["ran"] is False
    assert r["reason"] == TC.FAULT_WORDS["budget"]
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["in_control"] is True and st["last_fault"]["why"] == "budget"
    r = run(db, now=at(10, 22), poll_ts=3)
    assert r["rang"] == 0 and len(sent) == 1


def test_NEGATIVE_outside_the_window_the_pass_never_reads(owner_push, monkeypatch):
    db, sent, _ = owner_push
    monkeypatch.setattr(TC, "WATCH", {"IREN": None})          # standing, so Saturday is not "expired"
    for now in (at(9, 31), at(16, 0), at(11, 0, d=17)):
        calls = []
        r = run(db, now=now, calls=calls)
        assert calls == [] and r["ran"] is False and r["reason"] == TC.REASON_OUTSIDE, now
    assert db.reads == 0 and db.writes == 0 and sent == []
    calls = []
    run(db, now=at(9, 32), calls=calls)
    assert len(calls) == 1


def test_A5_all_fault_polls_do_not_count_as_ran(owner_push):
    db, sent, _ = owner_push
    r = run(db, fetch_fn=lambda s, d: None)
    assert (r["active"], r["read"], r["ran"]) == (1, 0, False)
    assert r["reason"] == TC.FAULT_WORDS["no_prints"] and sent == []
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["in_control"] is None and st["faults"] == 1


def test_a_ring_that_reached_no_device_says_so(owner_push):
    db, sent, result = owner_push
    result.update(sent=0, total_targets=0)
    run(db, poll_ts=1)
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["rings"][0]["pushed"] is False and st["rang"] is False and st["push_attempts"] == 1
    assert st["not_pushed_reason"] == "not_sent"
    _, text = TC.pin_text(TC.pins_for(DAY)[0], st, NOW)
    assert "(reached no device)" in text


def test_A3_a_ring_to_no_device_is_retried_once_then_exhausted(owner_push):
    db, sent, result = owner_push
    result.update(sent=0, total_targets=0)
    r1 = run(db, poll_ts=1)
    r2 = run(db, now=at(10, 17), poll_ts=2)
    assert (r1["rang"], r2["rang"]) == (1, 1) and len(sent) == 2
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["push_attempts"] == TC.MAX_PUSH_ATTEMPTS and st["exhausted"] is True
    assert sent[1][1]["body"].endswith("10:17 ET · " + TC.RULE_TAIL)     # a retry is not "first read"
    r3 = run(db, now=at(10, 22), poll_ts=3)
    assert r3["rang"] == 0 and len(sent) == 2
    _, text = TC.pin_text(TC.pins_for(DAY)[0], db[TC.STATE_COLL].docs["IREN:" + DAY], at(10, 22))
    assert "rang twice to no device — check Notifications" in text
    assert len(db[TC.EVENTS_COLL].docs) == 2


def test_A3_a_false_poll_resets_the_attempts(owner_push):
    db, sent, result = owner_push
    result.update(sent=0, total_targets=0)
    run(db, poll_ts=1)
    run(db, now=at(10, 17), poll_ts=2, frame=tape(-1))
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["push_attempts"] == 0 and st["exhausted"] is False and st["in_control"] is False
    result.update(sent=1, total_targets=1)
    r = run(db, now=at(10, 22), poll_ts=3)
    assert r["rang"] == 1 and r["pushed"] == 1 and len(sent) == 2


def test_A3_a_delivered_ring_is_never_retried(owner_push):
    db, sent, _ = owner_push
    run(db, poll_ts=1)
    run(db, now=at(10, 17), poll_ts=2)
    run(db, now=at(10, 22), poll_ts=3)
    assert len(sent) == 1


def test_A3_a_send_that_raises_is_error_no_crash(owner_push):
    db, sent, _ = owner_push

    def boom(*a, **k):
        raise RuntimeError("push down")
    r = run(db, poll_ts=1, record_fn=boom)
    assert r["rang"] == 1 and r["pushed"] == 0
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["not_pushed_reason"] == "error" and st["rings"][0]["pushed"] is False


def test_A3_a_pending_ring_whose_patch_was_lost_is_never_resent():
    s, ring = TC.decide(None, read(True))
    s["rings"][-1]["pushed"] = None                     # claimed, outcome never written
    s2, again = TC.decide(s, read(True, hhmm="10:17"))
    assert ring is True and again is False


def test_NEGATIVE_a_sellers_tape_never_rings(owner_push):
    db, sent, _ = owner_push
    r = run(db, frame=tape(-1))
    assert r["rang"] == 0 and r["in_control"] == 0 and r["read"] == 1 and sent == []
    st = db[TC.STATE_COLL].docs["IREN:" + DAY]
    assert st["in_control"] is False


def test_events_live_in_their_own_collection(owner_push):
    assert len({TC.EVENTS_COLL, TBK.EVENTS_COLL, TF.EVENTS_COLL}) == 3
    db, _, _ = owner_push
    seen = []
    run(db, record_fn=lambda events, **kw: seen.append(kw) or {"ok": True, "new": 1, "pushed": True,
                                                              "fresh_ids": [e["_id"] for e in events]})
    assert seen[0]["precheck_colls"] == () and seen[0]["coll_name"] == TC.EVENTS_COLL
    assert seen[0]["kind"] == TC.KIND and seen[0]["title_fmt"] == TC.TITLE_FMT


# ── words ────────────────────────────────────────────────────────────────────
def _doc(**kw):
    s, _ = TC.decide(None, read(True))
    s.update(date=DAY, symbol="IREN", kind=TC.KIND, last_fault=None)
    s.update(kw)
    return s


def test_status_words_for_every_state(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": DAY})
    pin = TC.pins_for(DAY)[0]
    num = ("session delta +90.9% of volume (+1,000 shares), last 30 min +500 shares · $10.10 · "
           "last print 10:10:00 ET")
    assert TC.pin_text(pin, None, NOW) == (
        "waiting", "watched 09:32–16:00 ET on trading days · no read yet today")
    nr = {"date": DAY, "in_control": None, "last_read": None,
          "last_fault": {"at": "x", "hhmm": "10:07", "why": "no_prints"}}
    assert TC.pin_text(pin, nr, NOW) == (
        "no_read", "no read yet today · 10:07 ET poll not read: no prints from the provider")
    d = _doc()
    d["rings"][0]["pushed"] = True
    assert TC.pin_text(pin, d, NOW) == (
        "in_control", "buyers led at the first read today 10:12 ET · " + num
        + " · read 10:12 ET · rang 10:12 ET · tick rule")
    d2 = _doc(first_read=False, last_fault={"at": "2026-10-16T10:17:00-04:00", "hhmm": "10:17",
                                            "why": "truncated"})
    d2["rings"][0]["pushed"] = False
    d2["rings"][0]["not_pushed_reason"] = "not_sent"
    # CHANGED 2026-10-18 (DECISIONS14 D8): FAULT_WORDS["truncated"] no longer says the newest prints were missing
    assert TC.pin_text(pin, d2, NOW) == (
        "in_control", "buyers in control since 10:12 ET · " + num
        + " · read 10:12 ET · rang 10:12 (reached no device) ET · 10:17 ET poll not read: "
          "the densest minutes were capped — every window of the session was read · tick rule")
    for delta, late, who in ((-1000, 500, "sellers in control for the session"),
                             (0, 0, "session delta flat"),
                             (1000, -1, "sellers took the last 30 min")):
        s, _ = TC.decide(None, read(False, delta=delta, late=late, pct=-90.9 if delta < 0 else 0.0))
        s.update(date=DAY)
        st, text = TC.pin_text(pin, s, NOW)
        assert st == "not_in_control"
        assert text.startswith(who + " since 10:12 ET · session delta ")
        assert text.endswith(" · read 10:12 ET · rings when buyers take control · tick rule")
    assert TC.pin_text({"symbol": "IREN", "until": "2026-10-15", "active": False}, None, NOW) == (
        "expired", "pin ended at the close of 2026-10-15 · not read")
    blk = TC.status_block(NOW, coll=BrokenColl())
    assert blk["note"] == TC.UNMEASURED_NOTE + " " + TC.RULE_NOTE
    assert [p["state"] for p in blk["pins"]] == ["waiting"]
    assert TC.status_block(NOW, coll=None)["pins"][0]["state"] == "waiting"


def test_status_block_serves_pins_from_one_read(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": DAY, "OLD": "2026-10-01"})
    db = StubDB()
    d = _doc()
    d["_id"] = "IREN:" + DAY
    d["rings"][0]["pushed"] = True
    db[TC.STATE_COLL].docs[d["_id"]] = d
    db[TC.STATE_COLL].docs["NBIS:" + DAY] = {**d, "_id": "NBIS:" + DAY, "symbol": "NBIS"}
    blk = TC.status_block(NOW, coll=db[TC.STATE_COLL])
    assert db.reads == 1
    assert [p["symbol"] for p in blk["pins"]] == ["IREN", "OLD"]       # an unpinned doc is not listed
    p = blk["pins"][0]
    assert p["state"] == "in_control" and p["rang"] == ["10:12"] and p["url"] == TC.tape_url("IREN")
    assert p["text"] == TC.pin_text(TC.pins_for(DAY)[0], d, NOW)[1]
    assert blk["pins"][1]["state"] == "expired" and blk["pins"][1]["rang"] == []


def test_NEGATIVE_a_state_doc_of_another_day_is_waiting(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": None})
    st, _ = TC.pin_text(TC.pins_for(DAY)[0], _doc(date="2026-10-15"), NOW)
    assert st == "waiting"


def test_served_strings_carry_tick_rule_and_no_banned_word(owner_push):
    db, sent, _ = owner_push
    pin = TC.pins_for(DAY)[0]
    texts = [TC.TITLE_FMT.format(lead="IREN"), W2_UP_FIRST, TC.headline({**read(), "symbol": "IREN"}),
             TC.UNMEASURED_NOTE, TC.RULE_NOTE, TC.REASON_NO_PIN, TC.REASON_NO_MONGO,
             TC.REASON_OUTSIDE, *TC.FAULT_WORDS.values(), *TC.NOT_PUSHED_WORDS.values()]
    sentences = [W2_UP_FIRST, TC.headline({**read(), "symbol": "IREN"})]
    for doc in (_doc(), _doc(first_read=False, exhausted=True, push_attempts=2)):
        sentences.append(TC.pin_text(pin, doc, NOW)[1])
    for delta, late in ((-5, 1), (0, 0), (5, -1)):
        s, _ = TC.decide(None, read(False, delta=delta, late=late))
        sentences.append(TC.pin_text(pin, {**s, "date": DAY}, NOW)[1])
    r = run(db, dry_run=True)
    sentences += [x["text"] for x in r["reads"]]
    texts += sentences + [TC.pin_text(pin, None, NOW)[1],
                          TC.pin_text({**pin, "active": False}, None, NOW)[1]]
    for s in sentences:
        assert TC.RULE_WORD in s, s
    for t in texts:
        assert not BANNED.search(t), t
    assert W2_UP_FIRST.endswith(" · tick rule (the Tape tab's quote-rule read can differ)")
    assert TC.headline({**read(), "symbol": "IREN"}).endswith(" · 10:12 ET · " + TC.RULE_TAIL)


def _code_only(src: str) -> str:
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            out.append(tok.string)
    return " ".join(out)


def test_the_constants_are_tagged():
    lines = {ln.split("=")[0].strip(): ln for ln in SRC.splitlines()
             if re.match(r"^[A-Z_0-9]+ = ", ln)}
    assert "# Ajay 2026-10-16" in lines["WATCH"]
    for name in ("KIND", "EVENTS_COLL", "STATE_COLL", "MARK", "TITLE_FMT", "URL_FMT", "START_BY_SEC",
                 "FAULT_WORDS", "MAX_429", "MAX_PUSH_ATTEMPTS", "RULE_TAIL", "NOT_PUSHED_WORDS"):
        assert "# MINE" in lines[name], name
    assert "Cheetah default" in lines["RULE_WORD"]
    assert TC.START_BY_SEC == TBK.KINDS_BUDGET_SEC
    assert "START_BY_SEC = KINDS_BUDGET_SEC" in SRC


def test_NEGATIVE_the_cheap_path_only():
    code = _code_only(SRC)
    for bad in ("engine.compute", "fetch_quotes", "last_session_trades", "date.today(",
                "fetch_recent_trades", "quotes="):
        assert bad.replace("(", " (") not in code and bad not in code, bad


def test_NEGATIVE_the_source_never_says_the_banned_words():
    assert not re.search("b" + "oun|f" + "ake", SRC, re.I)
    assert not re.search("b" + "oun|f" + "ake", Path(__file__).read_text(), re.I)
