"""Price alerts: one fire per crossing (latch), honest wording, one bulk call.

2026-09-21. Ajay: "why I am getting such older alerts these are supposed to be
realtime" — May/June presets whose price simply STAYED past their line were
re-firing every ALERT_COOLDOWN_SEC, forever, with undated raw-float text.

Covered here: the `armed` latch and its legacy migration, the rule that a
CACHED-close fallback print may fire but may never re-arm, the rebuilt wording,
the single `bulk_live_prices` call per run, and the served `state_line`.
Everything is synthetic — no Mongo, no Massive.
"""
import copy
import inspect

import pytest

from sepa import price_alerts


# ---------------------------------------------------------------------------
# In-process fake Mongo
# ---------------------------------------------------------------------------
class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **k):
        return self

    def limit(self, n):
        return _Cursor(self._docs[:n])

    def __iter__(self):
        return iter(self._docs)


class _Coll:
    def __init__(self, docs=None):
        self.docs = [dict(d) for d in (docs or [])]
        self.insert_key_sets = []

    def find(self, q=None):
        docs = list(self.docs)
        if q:
            gt = (q.get("fired_at") or {}).get("$gt")
            if gt is not None:
                docs = [d for d in docs if (d.get("fired_at") or 0) > gt]
        return _Cursor(docs)

    def insert_one(self, doc):
        # Pin the key set the CALLER wrote, before Mongo's own _id is added.
        self.insert_key_sets.append(set(doc.keys()))
        doc.setdefault("_id", f"oid{len(self.docs) + 1}")
        self.docs.append(doc)

        class _R:
            inserted_id = doc["_id"]
        return _R()

    def update_one(self, filt, upd):
        for d in self.docs:
            if d["_id"] == filt["_id"]:
                d.update(upd.get("$set") or {})
                return


class _DB:
    def __init__(self, alerts=None, fires=None):
        self.price_alerts = _Coll(alerts)
        self.price_alert_fires = _Coll(fires)


class _Env:
    def __init__(self):
        self.db = _DB()
        self.now = 1_790_000_000
        self.sends = []
        self.bulk = {}
        self.bulk_calls = []
        self.bulk_raises = False
        self.ltp = {}
        self.ltp_calls = []

    def seed(self, *docs):
        self.db.price_alerts.docs.extend(dict(d) for d in docs)

    def doc(self, _id="a1"):
        return next(d for d in self.db.price_alerts.docs if d["_id"] == _id)

    @property
    def fires(self):
        return self.db.price_alert_fires.docs


@pytest.fixture
def env(monkeypatch):
    e = _Env()
    monkeypatch.setattr(price_alerts, "_db", lambda: e.db)
    # the module does `import time`, so patch the attribute it looks through
    monkeypatch.setattr(price_alerts.time, "time", lambda: e.now)

    def _bulk(syms):
        e.bulk_calls.append(list(syms))
        if e.bulk_raises:
            raise RuntimeError("massive snapshot down")
        return {s: e.bulk[s] for s in syms if s in e.bulk}

    def _ltp(sym):
        e.ltp_calls.append(sym)
        return e.ltp.get(sym)

    def _send(**kw):
        e.sends.append(kw)
        return 1

    monkeypatch.setattr(price_alerts.prices, "bulk_live_prices", _bulk)
    monkeypatch.setattr(price_alerts.prices, "last_trade_price", _ltp)
    monkeypatch.setattr(price_alerts.notify, "send_alert", _send)
    return e


def _alert(**kw):
    d = {
        "_id": "a1", "symbol": "MKSI", "kind": "below", "level": 300.0,
        "created_price": 350.0, "created_at": 1780436864, "last_fired_at": 0,
        "channels": ["push", "browser"], "note": None,
        "user_email": "trader@x.com",
    }
    d.update(kw)
    return d


def _armed(**kw):
    d = _alert(armed=True, triggered_at=None, triggered_price=None,
               triggered_ref=None, rearmed_at=None)
    d.update(kw)
    return d


def _row(px, prev=None):
    return {"last_trade_price": px, "price": px, "prev_day_close": prev}


# ---------------------------------------------------------------------------
# 1-5 the latch itself
# ---------------------------------------------------------------------------
def test_01_armed_and_hit_fires_once_and_latches(env):
    env.seed(_armed())
    env.bulk["MKSI"] = _row(250.0, 260.0)
    out = price_alerts.check_alerts()

    assert out["fired"] == 1 and out["checked"] == 1
    assert len(env.fires) == 1
    assert len(env.sends) == 1 and env.sends[0]["user_email"] == "trader@x.com"
    d = env.doc()
    assert d["armed"] is False
    assert d["triggered_at"] == env.now
    assert d["triggered_price"] == 250.0
    assert d["triggered_ref"] == 300.0
    assert d["last_fired_at"] == env.now


def test_02_NEG_latched_and_still_hit_never_fires_again(env):
    """THE bug: price stays past the line → old code re-fired every 6h forever."""
    env.seed(_armed(armed=False, triggered_at=env.now, triggered_price=250.0,
                    triggered_ref=300.0, last_fired_at=env.now))
    env.bulk["MKSI"] = _row(250.0, 260.0)
    for _ in range(10):
        env.now += price_alerts.ALERT_COOLDOWN_SEC + 1
        out = price_alerts.check_alerts()
        assert out["fired"] == 0 and out["held"] == 1

    assert env.sends == []
    assert env.fires == []
    d = env.doc()
    assert d["armed"] is False
    assert d.get("rearmed_at") is None


def test_03_rearm_is_silent_on_a_live_row(env):
    env.seed(_armed(armed=False, triggered_at=env.now - 100,
                    triggered_price=250.0, last_fired_at=env.now - 100))
    env.bulk["MKSI"] = _row(310.0, 260.0)
    out = price_alerts.check_alerts()

    assert out["rearmed"] == 1 and out["fired"] == 0
    assert env.sends == [] and env.fires == []
    d = env.doc()
    assert d["armed"] is True and d["rearmed_at"] == env.now


def test_04_a_real_recrossing_fires_again(env):
    env.seed(_armed())
    env.bulk["MKSI"] = _row(250.0, 260.0)
    price_alerts.check_alerts()                      # fire

    env.now += price_alerts.ALERT_COOLDOWN_SEC + 1
    env.bulk["MKSI"] = _row(320.0, 260.0)
    price_alerts.check_alerts()                      # back over → rearm

    env.now += 60
    env.bulk["MKSI"] = _row(248.0, 260.0)
    price_alerts.check_alerts()                      # re-cross → fire

    assert len(env.fires) == 2
    assert len(env.sends) == 2


def test_05_cooldown_is_unchanged_and_blocks_a_fast_recross(env):
    env.seed(_armed())
    env.bulk["MKSI"] = _row(250.0, 260.0)
    price_alerts.check_alerts()

    env.now += 60
    env.bulk["MKSI"] = _row(320.0, 260.0)
    price_alerts.check_alerts()                      # rearm

    env.now += 60
    env.bulk["MKSI"] = _row(249.0, 260.0)
    out = price_alerts.check_alerts()                # inside the window
    assert out["fired"] == 0
    assert env.doc()["armed"] is True                # untouched, still armed

    env.now += price_alerts.ALERT_COOLDOWN_SEC + 1
    out = price_alerts.check_alerts()
    assert out["fired"] == 1
    assert len(env.fires) == 2


# ---------------------------------------------------------------------------
# 6-9 legacy migration
# ---------------------------------------------------------------------------
def test_06_legacy_hit_with_a_prior_fire_latches_silently_without_a_price(env):
    lf = 1_790_017_201                                # 2026-09-21 15:00:01 ET
    env.now = lf + 600
    env.seed(_alert(last_fired_at=lf))                # no `armed` key
    env.bulk["MKSI"] = _row(256.1493, 260.0)
    out = price_alerts.check_alerts()

    assert out["latched_legacy"] == 1 and out["fired"] == 0
    assert env.sends == [] and env.fires == []
    d = env.doc()
    assert d["armed"] is False
    assert d["triggered_at"] == lf                    # the fire, not this run
    assert d["triggered_price"] is None               # different moment (C4)
    assert d["triggered_ref"] == 300.0
    assert d["migrated_at"] == env.now


def test_07_legacy_hit_never_fired_fires_once(env):
    env.seed(_alert(last_fired_at=0))
    env.bulk["MKSI"] = _row(250.0, 260.0)
    out = price_alerts.check_alerts()

    assert out["fired"] == 1 and out["latched_legacy"] == 0
    assert len(env.sends) == 1 and len(env.fires) == 1
    d = env.doc()
    assert d["armed"] is False and d["triggered_price"] == 250.0


def test_08_legacy_not_hit_arms_on_a_live_row(env):
    env.seed(_alert(last_fired_at=1_790_017_201))
    env.bulk["MKSI"] = _row(320.0, 260.0)
    out = price_alerts.check_alerts()

    assert out["armed_legacy"] == 1 and out["fired"] == 0
    d = env.doc()
    assert d["armed"] is True and d["rearmed_at"] is None
    assert d["migrated_at"] == env.now


def test_09_migration_is_idempotent(env):
    env.seed(
        _alert(_id="hit_fired", last_fired_at=1_790_017_201),
        _alert(_id="not_hit", symbol="ARM", last_fired_at=1_790_017_201),
        _alert(_id="hit_fresh", symbol="ON", last_fired_at=0),
    )
    env.bulk = {"MKSI": _row(250.0, 260.0), "ARM": _row(320.0, 260.0),
                "ON": _row(250.0, 260.0)}
    price_alerts.check_alerts()
    after_first = copy.deepcopy(env.db.price_alerts.docs)

    out = price_alerts.check_alerts()
    assert out["latched_legacy"] == 0 and out["armed_legacy"] == 0
    assert env.db.price_alerts.docs == after_first


# ---------------------------------------------------------------------------
# 10-12 wording
# ---------------------------------------------------------------------------
def test_10_wording_drop_pct_carries_set_price_set_date_and_today(env):
    a = _armed(symbol="ARM", kind="drop_pct", level=7.0, created_price=394.17,
               created_at=1780323625, note="−7% preset")
    msg = price_alerts._format(a, 321.3, _row(321.3, 275.61))
    head, note = msg.split("\n")
    assert head == ("ARM -18.5% vs $394.17 when you set it (Jun 1) "
                    "· today +16.6% · now $321.30")
    assert note == "Note: −7% preset"


def test_11_NEG_no_previous_close_means_no_today_segment(env):
    a = _armed(symbol="ARM", kind="drop_pct", level=7.0, created_price=394.17,
               created_at=1780323625)
    for row in (_row(321.3, None), _row(321.3, 0), None):
        head = price_alerts._format(a, 321.3, row).split("\n")[0]
        assert "today" not in head
        assert "+0.0%" not in head
        assert head.endswith("· now $321.30")


def test_12_wording_below_and_above(env):
    a = _armed(symbol="MKSI", kind="below", level=306.18, created_price=331.39,
               created_at=1780436864)
    assert price_alerts._format(a, 256.1493) == (
        "MKSI ↓ $256.15 crossed your ≤ $306.18 line (set Jun 2 at $331.39)")

    b = dict(a, kind="above", level=306.18)
    assert price_alerts._format(b, 400.0) == (
        "MKSI ↑ $400.00 crossed your ≥ $306.18 line (set Jun 2 at $331.39)")

    c = dict(a, created_price=None)
    assert price_alerts._format(c, 256.1493) == (
        "MKSI ↓ $256.15 crossed your ≤ $306.18 line (set Jun 2)")


# ---------------------------------------------------------------------------
# 13-16 one bulk call, fallback, no print
# ---------------------------------------------------------------------------
def test_13_one_bulk_call_and_fallback_only_for_the_missing_symbol(env):
    env.seed(_armed(_id="a1", symbol="ARM"), _armed(_id="a2", symbol="MKSI"),
             _armed(_id="a3", symbol="ON"))
    env.bulk = {"ARM": _row(320.0, 300.0), "MKSI": _row(320.0, 300.0)}
    env.ltp["ON"] = 320.0
    out = price_alerts.check_alerts()

    assert env.bulk_calls == [["ARM", "MKSI", "ON"]]
    assert env.ltp_calls == ["ON"]
    assert out["fallback_prints"] == 1


def test_14_NEG_a_row_without_a_print_is_skipped_not_backfilled(env):
    env.seed(_alert())                                 # legacy doc
    env.bulk["MKSI"] = {"last_trade_price": 0, "price": None,
                        "prev_day_close": 260.0}
    out = price_alerts.check_alerts()

    assert out["skipped_no_print"] == 1 and out["checked"] == 0
    assert env.ltp_calls == []                         # never a prev-close stand-in
    assert "armed" not in env.doc()                    # legacy stays legacy


def test_15_NEG_no_fallback_print_means_no_fire(env):
    env.seed(_armed())
    env.ltp["MKSI"] = None
    out = price_alerts.check_alerts()

    assert out["skipped_no_print"] == 1 and out["fired"] == 0
    assert env.sends == []


def test_16_bulk_failure_falls_back_for_every_symbol(env):
    env.seed(_armed(_id="a1", symbol="ARM"), _armed(_id="a2", symbol="MKSI"))
    env.bulk_raises = True
    env.ltp = {"ARM": 320.0, "MKSI": 320.0}
    out = price_alerts.check_alerts()

    assert out["fallback_prints"] == 2
    assert sorted(env.ltp_calls) == ["ARM", "MKSI"]


# ---------------------------------------------------------------------------
# 17-19 served state, purity, source pins
# ---------------------------------------------------------------------------
def test_17_state_line_is_served_and_the_fires_row_keeps_its_key_set(env):
    env.seed(
        _armed(_id="latched", armed=False, triggered_at=1_790_017_201,
               triggered_price=256.1493),
        _armed(_id="legacy_latch", armed=False, triggered_at=1_790_017_201,
               triggered_price=None),
        _armed(_id="rise", kind="rise_pct", level=5.0, armed=False,
               triggered_at=1_790_017_201, triggered_price=256.1493),
        _armed(_id="still_armed"),
        _alert(_id="never_seen"),
    )
    rows = {r["_id"]: r for r in price_alerts.list_active()}
    assert rows["latched"]["state_line"] == (
        "triggered Sep 21 at $256.15 — re-arms when price crosses back above the line")
    assert rows["legacy_latch"]["state_line"] == (
        "triggered Sep 21 — re-arms when price crosses back above the line")
    assert "at $" not in rows["legacy_latch"]["state_line"]
    assert "back below the line" in rows["rise"]["state_line"]
    assert rows["still_armed"]["state_line"] is None
    assert rows["never_seen"]["armed"] is None
    assert rows["never_seen"]["state_line"] is None

    # The fires collection has TWO writers; pin only the row check_alerts writes.
    env.db.price_alert_fires.docs.append({
        "_id": "vcp1", "alert_id": None, "symbol": "NVDA", "kind": "setup_vcp",
        "level": 180.0, "price": 180.0, "fired_at": env.now - 10,
        "channels": [], "message": "vcp", "meta": {"src": "vcp_watch"},
    })
    env.db.price_alerts.docs = [_armed(_id="fire_me")]
    env.bulk["MKSI"] = _row(250.0, 260.0)
    price_alerts.check_alerts()

    assert env.db.price_alert_fires.insert_key_sets == [{
        "alert_id", "symbol", "kind", "level", "price", "fired_at",
        "channels", "message"}]
    vcp = next(d for d in price_alerts.recent_fires() if d["symbol"] == "NVDA")
    assert vcp["meta"] == {"src": "vcp_watch"}


def test_18_transition_is_pure_and_live_only_gates_rearm_and_arm_legacy(env):
    a = _armed(armed=False)
    before = copy.deepcopy(a)
    price_alerts._transition(a, 250.0, env.now, True)
    assert a == before

    for live in (True, False):
        assert price_alerts._transition(_armed(), 250.0, env.now, live)[0] == "fire"
        assert price_alerts._transition(_armed(), 400.0, env.now, live)[0] == "noop"
        assert price_alerts._transition(_armed(armed=False), 250.0, env.now,
                                        live)[0] == "hold"
    assert price_alerts._transition(_armed(armed=False), 400.0, env.now,
                                    True)[0] == "rearm"
    assert price_alerts._transition(_armed(armed=False), 400.0, env.now,
                                    False)[0] == "hold"


def test_19_delivery_source_pins_still_hold():
    src = "\n".join(l.split("#", 1)[0]
                    for l in inspect.getsource(price_alerts.check_alerts).splitlines())
    assert "user_email=" in src
    assert "_target_email" in src


# ---------------------------------------------------------------------------
# 20-24 born armed, the stale-fallback rule, malformed docs
# ---------------------------------------------------------------------------
def test_20_a_freshly_created_alert_is_born_armed_and_never_migrates(env):
    env.ltp["BB"] = 9.23
    doc = price_alerts.create("BB", "drop_pct", 5, user_email="trader@x.com")
    assert doc["armed"] is True
    for k in ("triggered_at", "triggered_price", "triggered_ref", "rearmed_at"):
        assert doc[k] is None
    assert "migrated_at" not in doc

    env.bulk["BB"] = _row(9.20, 9.30)                  # above the 8.7685 line
    out = price_alerts.check_alerts()
    assert (out["fired"], out["latched_legacy"], out["armed_legacy"],
            out["rearmed"], out["held"]) == (0, 0, 0, 0, 0)
    assert env.doc(doc["_id"])["armed"] is True

    env.bulk["BB"] = _row(8.70, 9.30)
    out = price_alerts.check_alerts()
    assert out["fired"] == 1
    assert out["latched_legacy"] == 0 and out["armed_legacy"] == 0


def test_21_NEG_a_cached_close_fallback_never_rearms_a_latched_doc(env):
    env.seed(_armed(armed=False, triggered_at=env.now - 100,
                    triggered_price=250.0, last_fired_at=env.now - 100))
    env.bulk_raises = True
    env.ltp["MKSI"] = 310.0                            # stale close, over the line
    out = price_alerts.check_alerts()

    assert out["held"] == 1 and out["rearmed"] == 0
    d = env.doc()
    assert d["armed"] is False and d.get("rearmed_at") is None

    env.bulk_raises = False
    env.bulk["MKSI"] = _row(310.0, 300.0)
    out = price_alerts.check_alerts()
    assert out["rearmed"] == 1
    assert env.doc()["armed"] is True and env.doc()["rearmed_at"] == env.now


def test_22_NEG_a_cached_close_fallback_never_arms_a_legacy_doc(env):
    env.seed(_alert(last_fired_at=1_790_017_201))
    env.bulk_raises = True
    env.ltp["MKSI"] = 310.0
    out = price_alerts.check_alerts()

    assert out["armed_legacy"] == 0
    d = env.doc()
    assert "armed" not in d and "migrated_at" not in d

    env.bulk_raises = False
    env.bulk["MKSI"] = _row(310.0, 300.0)
    out = price_alerts.check_alerts()
    assert out["armed_legacy"] == 1
    assert env.doc()["armed"] is True


def test_23_NEG_malformed_docs_never_raise_and_never_500_the_list(env):
    assert price_alerts._state_line({"armed": False}) is None
    assert price_alerts._state_line({"armed": False, "kind": "weird"}) is None
    assert price_alerts._state_line({
        "armed": False, "kind": "below",
        "triggered_price": "abc", "triggered_at": "x"}) == (
        "triggered — re-arms when price crosses back above the line")
    assert "$" not in price_alerts._state_line({
        "armed": False, "kind": "below", "triggered_price": True})

    assert price_alerts._threshold({"kind": "weird", "level": 1}, 5) is None
    assert price_alerts._hit({"kind": "weird", "level": 1}, 5) is False
    assert price_alerts._threshold({"kind": "drop_pct", "level": 5}, None) is None

    env.db.price_alerts.docs = [
        {"_id": "m1", "armed": False},
        {"_id": "m2", "armed": False, "kind": "weird"},
        {"_id": "m3", "armed": False, "kind": "below",
         "triggered_price": "abc", "triggered_at": "x"},
        {"_id": "m4", "armed": False, "kind": "below", "triggered_price": True},
        _armed(_id="good", armed=False, triggered_at=1_790_017_201,
               triggered_price=256.1493),
    ]
    rows = price_alerts.list_active()
    assert len(rows) == 5
    assert rows[-1]["state_line"].startswith("triggered Sep 21 at $256.15")


def test_24_a_fallback_print_may_still_fire(env):
    """Unchanged behaviour: today's code fires on whatever last_trade_price
    returns. It just can no longer RE-ARM (test 21). His call, §7.9."""
    env.seed(_armed())
    env.bulk_raises = True
    env.ltp["MKSI"] = 250.0
    out = price_alerts.check_alerts()

    assert out["fired"] == 1 and out["fallback_prints"] == 1
    assert len(env.sends) == 1
    d = env.doc()
    assert d["armed"] is False and d["triggered_price"] == 250.0
