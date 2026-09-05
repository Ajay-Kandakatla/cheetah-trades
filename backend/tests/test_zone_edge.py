"""supply_demand/zone_edge — within 1% of breaking the last supply band toward
new highs, and within 1% above a demand level; every minute, tracked, pushed
once per band per day (Ajay 2026-09-03 ~5pm ET).

Behavioural tests on synthetic bands (NEGATIVES throughout) + source guards
for the wiring (pref default, crontab line, API route).
"""
import collections
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import zone_edge as ZE      # noqa: E402
from supply_demand import demand_alerts as DA  # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 3, 10, 0, tzinfo=ET)
DAY = "2026-09-03"

RES = {"kind": "supply", "lo": 100.0, "hi": 102.0, "touches": 3, "strength": 40.0}
OVER = {"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 1, "strength": 20.0}
DEM = {"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2, "strength": 30.0}
LOWDEM = {"kind": "demand", "lo": 80.0, "hi": 82.0, "touches": 4, "strength": 55.0}


class FakeColl:
    """State (find/update_one), latest (find_one/replace_one) and track
    (insert_many/delete_many/find) in one fake — each pass gets four of them.
    `calls` counts every Mongo-shaped call so a test can prove the pass never
    goes to Mongo per symbol. Deliberately NO create_index: the module's
    guarded ensure_track_index must survive a coll without it."""

    def __init__(self):
        self.docs = {}
        self.rows = []
        self.calls = collections.Counter()

    def find_one(self, q):
        self.calls["find_one"] += 1
        return self.docs.get(q["_id"])

    def update_one(self, q, u, upsert=False):
        self.calls["update_one"] += 1
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        d.update(u.get("$set", {}))

    def replace_one(self, q, doc, upsert=False):
        self.calls["replace_one"] += 1
        self.docs[q["_id"]] = dict(doc)

    def insert_many(self, docs):
        self.calls["insert_many"] += 1
        self.rows.extend(dict(d) for d in docs)

    def delete_many(self, q):
        self.calls["delete_many"] += 1
        cutoff = q["date"]["$lt"]
        before = len(self.rows)
        self.rows = [r for r in self.rows if not (r["date"] < cutoff)]
        return SimpleNamespace(deleted_count=before - len(self.rows))

    def find(self, q, projection=None):
        self.calls["find"] += 1
        if "_id" in q:                                    # state: {"_id": {"$in": [...]}}
            for k in q["_id"]["$in"]:
                if k in self.docs:
                    yield dict(self.docs[k])
            return
        for r in self.rows:
            if "date" in q and r.get("date") != q["date"]:
                continue
            if "symbol" in q and r.get("symbol") not in q["symbol"]["$in"]:
                continue
            ts = str(r.get("ts") or "")
            if "ts" in q and not (q["ts"]["$gte"] <= ts <= q["ts"].get("$lte", ts)):
                continue
            yield dict(r)


class IndexedFakeColl(FakeColl):
    def __init__(self):
        super().__init__()
        self.indexes = []

    def create_index(self, keys, **kw):
        self.calls["create_index"] += 1
        self.indexes.append((list(keys), dict(kw)))


class FakeNames:
    """The company_names_cache coll: {symbol, name} docs, one $in read."""

    def __init__(self, names):
        self.names, self.calls = dict(names), 0

    def find(self, q, projection=None):
        self.calls += 1
        for s in q["symbol"]["$in"]:
            if s in self.names:
                yield {"symbol": s, "name": self.names[s]}


def _colls():
    return {"coll_break": FakeColl(), "coll_demand": FakeColl(),
            "latest_coll": FakeColl(), "track_coll": FakeColl()}


def _doc(sym, bands, prev_close, high_252=None, day=DAY):
    return {"_id": f"{sym}:{day}", "symbol": sym, "date": day, "geom": "board",
            "bands": bands, "atr14": 1.0, "prev_close": prev_close, "high_252": high_252}


def _snap(last, prev=None, change_pct=0.0, *, now=NOW, age_sec=30):
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    return {"open": last, "high": last, "low": last, "close": last, "volume": 1e6,
            "change_pct": change_pct, "last_trade_price": last, "last_trade_ts_ms": ts_ns,
            "prev_day_close": prev}


def _capture(monkeypatch, result=None):
    from push import sender
    sent = []

    def fake(owner, payload, kind=None):
        sent.append({"owner": owner, "kind_arg": kind, **payload})
        return result or {"sent": 1, "failed": 0, "total_targets": 1}
    monkeypatch.setattr(sender, "send_to_user", fake)
    return sent


_NO_NAMES = object()          # default: inject {} (no name lookups); pass None to exercise _names_for


def _run(store, snapshot, caps, *, colls=None, now=NOW, push=True, names=_NO_NAMES, track=True):
    colls = colls or _colls()
    out = ZE.check_once(push=push, force=True, track=track, store=store, snapshot=snapshot,
                        caps=caps, names={} if names is _NO_NAMES else names, owner="o@x",
                        now=now, **colls)
    return out, colls


# ── side A: the pure read ────────────────────────────────────────────────────
def test_near_resistance_qualifies_at_0_9_pct_under_not_1_1():
    r = ZE.read_breaking(102 / 1.009, [RES], 99.0, None)
    assert r and r["tier"] == "near" and r["dist_pct"] == 0.9 and r["band"]["hi"] == 102.0
    assert ZE.read_breaking(102 / 1.011, [RES], 99.0, None) is None, "1.1% under is not <1%"
    r0 = ZE.read_breaking(102.0, [RES], 99.0, None)
    assert r0 and r0["tier"] == "near" and r0["dist_pct"] == 0.0, "sitting on the ceiling"
    assert ZE.read_breaking(101.5, [RES, DEM], 99.0, None)["tier"] == "near", "demand bands ignored"


def test_resistance_is_the_smallest_top_at_or_above_the_print():
    bands = [RES, OVER, {"kind": "supply", "lo": 103.0, "hi": 104.5, "touches": 2, "strength": 25.0}]
    r = ZE.read_breaking(103.6, bands, 99.0, None)
    assert r["tier"] == "near" and r["band"]["hi"] == 104.5 and r["dist_pct"] == 0.87
    assert r["overhead_bands"] == 1 and r["new_highs"] is False, "OVER still sits above"
    # a print 1.5% under the next ceiling: not near, and RES was NOT broken today
    # (yesterday already closed above it) -> nothing
    assert ZE.read_breaking(102.95, bands, 102.5, None) is None


def test_a_supply_band_above_means_no_new_highs_unless_the_52w_rule():
    r = ZE.read_breaking(101.5, [RES, OVER], 99.0, None)
    assert r["tier"] == "near" and r["new_highs"] is False and r["overhead_bands"] == 1
    clear = ZE.read_breaking(101.5, [RES], 99.0, None)
    assert clear["new_highs"] is True and clear["overhead_bands"] == 0
    assert ZE.read_breaking(101.5, [RES], 99.0, 130.0)["new_highs"] is True, "nothing overhead wins"


def test_52w_rule_band_top_at_or_above_98_pct_of_the_252_bar_high():
    r = ZE.read_breaking(101.5, [RES, OVER], 99.0, 103.0)      # 102 >= 0.98*103 = 100.94
    assert r["new_highs"] is True and r["overhead_bands"] == 1
    assert r["high_252"] == 103.0 and r["pct_to_52w"] == 1.48
    assert ZE.read_breaking(101.5, [RES, OVER], 99.0, 104.08)["new_highs"] is True, "102/0.98 = 104.08"
    assert ZE.read_breaking(101.5, [RES, OVER], 99.0, 104.09)["new_highs"] is False
    assert ZE.read_breaking(101.5, [RES, OVER], 99.0, 105.0)["new_highs"] is False
    unk = ZE.read_breaking(101.5, [RES, OVER], 99.0, None)
    assert unk["new_highs"] is False and unk["high_252"] is None and unk["pct_to_52w"] is None
    assert ZE.read_breaking(101.5, [RES, OVER], 99.0, float("nan"))["high_252"] is None
    assert ZE.read_breaking(101.5, [RES, OVER], 99.0, -5.0)["high_252"] is None


def test_broke_tier_needs_prev_close_at_or_under_the_top_and_at_most_3_pct_through():
    r = ZE.read_breaking(103.0, [RES], 101.0, None)
    assert r["tier"] == "broke" and r["dist_pct"] == -0.97 and r["band"] == RES
    assert ZE.read_breaking(103.0, [RES], 102.0, None)["tier"] == "broke", "closed ON the ceiling"
    assert ZE.read_breaking(103.0, [RES], 102.01, None) is None, "yesterday already above = not today"
    assert ZE.read_breaking(103.0, [RES], None, None) is None, "unknown prev close: cannot say"
    assert ZE.read_breaking(102.0 * 1.03, [RES], 101.0, None)["tier"] == "broke"       # 3.0% through
    assert ZE.read_breaking(102.0 * 1.035, [RES], 101.0, None) is None, "3.5% through drops"
    assert ZE.read_breaking(102.0 * 1.03 + 0.01, [RES], 101.0, None) is None


def test_broke_is_the_highest_broken_band_and_near_wins_over_broke():
    s2 = {"kind": "supply", "lo": 98.0, "hi": 99.5, "touches": 2, "strength": 20.0}
    r = ZE.read_breaking(102.3, [s2, RES], 97.0, None)
    assert r["tier"] == "broke" and r["band"]["hi"] == 102.0
    nxt = {"kind": "supply", "lo": 103.5, "hi": 104.5, "touches": 2, "strength": 25.0}
    r2 = ZE.read_breaking(103.6, [RES, nxt], 101.0, None)
    assert r2["tier"] == "near" and r2["band"]["hi"] == 104.5, "1% under the next ceiling reads as near"
    assert r2["overhead_bands"] == 0 and r2["new_highs"] is True


def test_breaking_garbage_never_crashes():
    assert ZE.read_breaking(None, [RES], 99.0, None) is None
    assert ZE.read_breaking(0, [RES], 99.0, None) is None
    assert ZE.read_breaking("x", [RES], 99.0, None) is None
    assert ZE.read_breaking(101.5, [], 99.0, None) is None
    assert ZE.read_breaking(101.5, None, 99.0, None) is None
    assert ZE.read_breaking(101.5, [{"kind": "supply", "lo": None, "hi": 102.0}], 99.0, None) is None
    assert ZE.read_breaking(101.5, [{"kind": "supply", "lo": 105.0, "hi": 102.0}], 99.0, None) is None
    assert ZE.read_breaking(101.5, [DEM], 99.0, None) is None


# ── side B: the pure read ────────────────────────────────────────────────────
def test_near_demand_in_and_near_tiers():
    r = ZE.read_near_demand(91.0, [DEM, RES], -1.0, 95.0)
    assert r["tier"] == "in" and r["dist_pct"] == 0.0 and r["role"] == "demand" and r["band"] == DEM
    r = ZE.read_near_demand(92.5, [DEM, RES], -1.0, 95.0)
    assert r["tier"] == "near" and r["dist_pct"] == 0.54 and r["band"] == DEM
    assert ZE.read_near_demand(92.92, [DEM], -1.0, 95.0)["dist_pct"] == 0.99
    assert ZE.read_near_demand(93.0, [DEM], -1.0, 95.0) is None, "1.08% above: not <1%"
    assert ZE.read_near_demand(89.0, [DEM], -1.0, 95.0) is None, "under the floor, nothing beneath"
    r = ZE.read_near_demand(89.0, [DEM, LOWDEM], -1.0, 95.0)
    assert r is None, "under DEM's floor, 8.5% above LOWDEM: neither"
    assert ZE.read_near_demand(82.5, [DEM, LOWDEM], -1.0, 95.0)["band"] == LOWDEM


def test_broken_supply_counts_as_support_only_once_yesterday_closed_above_it():
    # yesterday closed 103.5 > 102: RES is broken supply = support; 0.49% above it today
    r = ZE.read_near_demand(102.5, [DEM, RES], -1.0, 103.5)
    assert r["tier"] == "near" and r["role"] == "broken supply" and r["band"] == RES
    assert r["dist_pct"] == 0.49 and r["arrival"] is True, "103.5 was outside the 1% ring"
    r2 = ZE.read_near_demand(102.5, [DEM, RES], -1.0, 102.5)
    assert r2["role"] == "broken supply" and r2["arrival"] is False, "sat on the shelf yesterday: resident"
    # yesterday closed UNDER the top (99 / 101 / exactly 102): the shelf is being broken
    # TODAY — Side A's fact — and is NOT support here (zone_bounce_alerts.is_eligible)
    for prev in (99.0, 101.0, 102.0):
        assert ZE.read_near_demand(102.5, [DEM, RES], 3.5, prev) is None, prev
    assert ZE.read_near_demand(102.5, [DEM, RES], 3.5, None) is None, "unknown prev: never support"
    assert ZE.read_near_demand(101.0, [DEM, RES], -1.0, 103.5) is None, \
        "inside a SUPPLY band is not 'in demand'; RES is not below the print"
    assert ZE.read_near_demand(94.0, [{"kind": "demand", "lo": 95.0, "hi": 97.0, "touches": 2}], -1.0, 99.0) is None, \
        "a demand band entirely ABOVE the print is not support"
    # a demand band still lists with an unknown prev close (resident) — only supply needs it
    u = ZE.read_near_demand(91.0, [DEM, RES], -1.0, None)
    assert u["tier"] == "in" and u["role"] == "demand" and u["arrival"] is False


def test_arrival_is_demand_alerts_rule_exactly_resident_never_arrival():
    assert ZE.read_near_demand(91.0, [DEM], -1.0, 95.0)["arrival"] is True     # 3.2% above yesterday
    assert ZE.read_near_demand(91.0, [DEM], -1.0, 91.5)["arrival"] is False    # slept inside
    assert ZE.read_near_demand(91.0, [DEM], -1.0, 92.5)["arrival"] is False    # 0.54% above = in the ring
    assert ZE.read_near_demand(91.0, [DEM], -1.0, 92.93)["arrival"] is True    # 1.0% above = outside
    assert ZE.read_near_demand(91.0, [DEM], -1.0, 89.0)["arrival"] is True     # reclaim from under
    r = ZE.read_near_demand(91.0, [DEM], -1.0, None)
    assert r["tier"] == "in" and r["arrival"] is False and r["hit"] is None, "unknown prev = resident"
    hit = ZE.read_near_demand(92.5, [DEM], -1.0, 95.0)["hit"]
    assert hit == DA.read(92.5, DEM, -1.0, 95.0) == {"tier": "at", "state": "above", "dist_pct": 0.54}


def test_near_demand_garbage_never_crashes():
    assert ZE.read_near_demand(None, [DEM], 0, 95.0) is None
    assert ZE.read_near_demand(0, [DEM], 0, 95.0) is None
    assert ZE.read_near_demand(91.0, [], 0, 95.0) is None
    assert ZE.read_near_demand(91.0, None, 0, 95.0) is None
    assert ZE.read_near_demand(91.0, [{"kind": "demand", "lo": None, "hi": 92.0}], 0, 95.0) is None
    assert ZE.read_near_demand(91.0, [{"kind": "demand", "lo": 93.0, "hi": 92.0}], 0, 95.0) is None


# ── keys + messages ──────────────────────────────────────────────────────────
def test_state_keys():
    assert ZE.break_state_key("AAA", RES, DAY, "near") == "AAA:100.00-102.00:2026-09-03:near"
    assert ZE.break_state_key("AAA", RES, DAY, "broke") == "AAA:100.00-102.00:2026-09-03:broke"
    assert DA.state_key("AAA", DEM, DAY, "at") == "AAA:90.00-92.00:2026-09-03:at"


def test_break_single_message_near_and_broke_exact():
    item = {"symbol": "AAA", "band": RES, "last": 101.5, "dist_pct": 0.49, "tier": "near",
            "high_252": 103.0, "pct_to_52w": 1.48, "cap": 5e9, "name": "Alpha"}
    m = ZE.break_single_message(item)
    assert m["title"] == "🚀 AAA 0.49% under resistance $100–102 → new highs"
    assert m["body"] == "$101.5 · tested 3x · 52w high $103 (+1.5%) · $5.0B · Alpha"
    assert m["url"] == "/sepa/AAA?tab=supply" and m["data"]["url"] == m["url"]
    assert m["kind"] == "supply_break_alert" == ZE.KIND_BREAK
    m2 = ZE.break_single_message(dict(item, tier="broke", last=103.0, dist_pct=-0.97,
                                      high_252=None, pct_to_52w=None, name=None))
    assert m2["title"] == "🚀 AAA broke resistance $100–102 (+1.0%) → new highs"
    assert m2["body"] == "$103 · tested 3x · $5.0B", "52w and name dropped when unknown"


def test_break_digest_is_broke_first_then_nearest_capped_at_six():
    items = [{"symbol": f"N{i}", "band": RES, "last": 101.0 + i * 0.1, "dist_pct": 0.9 - i * 0.1,
              "tier": "near", "cap": 2e9} for i in range(7)]
    items.append({"symbol": "B1", "band": RES, "last": 103.0, "dist_pct": -0.97, "tier": "broke", "cap": 3e9})
    m = ZE.break_digest_message(items)
    assert m["title"] == "🚀 Breaking resistance — B1 broke +1.0% +7 more"
    lines = m["body"].split("\n")
    assert len(lines) == ZE.DIGEST_MAX + 1 and lines[-1] == "+2 more"
    assert lines[0] == "B1 $103 · broke $100–102 (+1.0%) · tested 3x · $3.0B"
    assert lines[1] == "N6 $101.6 · 0.3% under $100–102 · tested 3x · $2.0B"
    assert m["kind"] == "supply_break_alert" and m["url"] == "/chart-maps?tab=deep_demand"
    one = ZE.break_digest_message(items[:1])
    assert one["title"] == "🚀 Breaking resistance — N0 0.9%"
    assert ZE.break_digest_message([]) is None


# ── the print ────────────────────────────────────────────────────────────────
def test_stale_print_is_skipped_and_counted_at_the_three_minute_line(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES, DEM], 99.0)}
    out, _ = _run(store, {"AAA": _snap(101.5, 99.0, age_sec=ZE.STALE_PRINT_SEC + 1)}, {"AAA": 5e9})
    assert out["stale_print"] == 1 and out["priced"] == 0
    assert out["breaking"] == [] and out["near_demand"] == [] and sent == []
    out, _ = _run(store, {"AAA": _snap(101.5, 99.0, age_sec=ZE.STALE_PRINT_SEC - 1)}, {"AAA": 5e9})
    assert out["priced"] == 1 and len(out["breaking"]) == 1
    assert ZE.STALE_PRINT_SEC == 180


# ── check_once end to end ────────────────────────────────────────────────────
def test_near_resistance_toward_new_highs_pushes_once_with_exact_payload(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES, DEM], 99.0, 103.0)}
    out, colls = _run(store, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9}, names={"AAA": "Alpha"})
    assert out["ran"] and out["singles_break"] == 1 and out["digest_break"] == 0 and out["pushed"] == 1
    assert len(sent) == 1
    m = sent[0]
    assert m["title"] == "🚀 AAA 0.49% under resistance $100–102 → new highs"
    assert m["body"] == "$101.5 · tested 3x · 52w high $103 (+1.5%) · room: clear runway · $5.0B · Alpha"
    assert m["kind"] == "supply_break_alert" and m["kind_arg"] == "supply_break_alert"
    assert m["owner"] == "o@x" and m["url"] == "/sepa/AAA?tab=supply"
    assert list(colls["coll_break"].docs) == ["AAA:100.00-102.00:2026-09-03:near"]
    assert colls["coll_demand"].docs == {}
    row = out["breaking"][0]
    assert row["symbol"] == "AAA" and row["name"] == "Alpha" and row["tier"] == "near"
    assert row["side"] == "supply" and row["role"] == "resistance" and row["new_highs"] is True
    assert row["overhead_bands"] == 0 and row["high_252"] == 103.0 and row["pct_to_52w"] == 1.48
    assert row["first_seen"] == "10:00" and row["arrival"] is None and row["cap"] == 5e9


def test_broke_today_pushes_with_the_broke_title(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES], 101.0)}
    out, colls = _run(store, {"AAA": _snap(103.0, 101.0)}, {"AAA": 5e9})
    assert out["pushed"] == 1 and sent[0]["title"] == "🚀 AAA broke resistance $100–102 (+1.0%) → new highs"
    assert list(colls["coll_break"].docs) == ["AAA:100.00-102.00:2026-09-03:broke"]
    assert out["breaking"][0]["tier"] == "broke" and out["breaking"][0]["dist_pct"] == -0.97


def test_overhead_supply_is_on_the_board_but_never_pushed(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES, OVER], 99.0, 120.0)}
    out, colls = _run(store, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9})
    assert len(out["breaking"]) == 1 and out["breaking"][0]["new_highs"] is False
    assert out["breaking"][0]["overhead_bands"] == 1
    assert sent == [] and colls["coll_break"].docs == {}


def test_touches_under_two_are_listed_never_pushed(monkeypatch):
    sent = _capture(monkeypatch)
    one = dict(RES, touches=1)
    onedem = dict(DEM, touches=1)
    store = {"AAA": _doc("AAA", [one], 99.0), "BBB": _doc("BBB", [onedem], 95.0)}
    out, colls = _run(store, {"AAA": _snap(101.5, 99.0), "BBB": _snap(91.0, 95.0, -2.0)},
                      {"AAA": 5e9, "BBB": 5e9})
    assert [r["symbol"] for r in out["breaking"]] == ["AAA"] and out["breaking"][0]["band"]["touches"] == 1
    assert [r["symbol"] for r in out["near_demand"]] == ["BBB"] and out["near_demand"][0]["arrival"] is True
    assert sent == [] and colls["coll_break"].docs == {} and colls["coll_demand"].docs == {}
    assert ZE.MIN_TOUCHES_PUSH == 2


def test_unknown_cap_is_skipped_from_the_board_small_cap_listed_not_pushed(monkeypatch):
    sent = _capture(monkeypatch)
    store = {s: _doc(s, [RES], 99.0) for s in ("UNK", "SML", "BIG")}
    snap = {s: _snap(101.5, 99.0) for s in store}
    out, _ = _run(store, snap, {"UNK": None, "SML": 9e8, "BIG": 5e9})
    assert [r["symbol"] for r in out["breaking"]] == ["BIG", "SML"]
    assert out["unknown_cap"] == 1 and out["skipped_cap"] == 1
    assert [s["title"].split()[1] for s in sent] == ["BIG"]
    out2, _ = _run(store, snap, {})
    assert out2["breaking"] == [] and out2["unknown_cap"] == 3


def test_near_demand_arrival_pushes_via_demand_alert_kind_and_demand_alerts_state(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    out, colls = _run(store, {"AAA": _snap(91.0, 95.0, -4.2)}, {"AAA": 5e9}, names={"AAA": "Alpha"})
    assert out["singles_demand"] == 1 and out["pushed"] == 1 and len(sent) == 1
    m = sent[0]
    assert m["title"] == "🧲 AAA in demand $90–92"
    assert m["body"] == "$91 · tested 2x · room +9.9% -> $100 · $5.0B · Alpha"   # RES 100-102 (hi >= prev 95) is the first unbroken lid
    assert m["kind"] == "demand_alert" == DA.KIND and m["kind_arg"] == "demand_alert"
    key = DA.state_key("AAA", DEM, DAY, "at")
    assert list(colls["coll_demand"].docs) == [key] == ["AAA:90.00-92.00:2026-09-03:at"]
    assert colls["coll_demand"].docs[key]["tier"] == "at" and colls["coll_break"].docs == {}
    row = out["near_demand"][0]
    assert row["tier"] == "in" and row["side"] == "demand" and row["role"] == "demand"
    assert row["arrival"] is True and row["dist_pct"] == 0.0 and row["new_highs"] is None
    assert ZE.STATE_COLL_BREAK == "supply_break_state" and DA.STATE_COLL == "demand_alert_state"


def test_demand_alerts_five_minute_pass_never_double_fires_a_band_zone_edge_already_sent(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [DEM], 95.0)}
    out, colls = _run(store, {"AAA": _snap(91.0, 95.0, -4.2)}, {"AAA": 5e9})
    assert out["pushed"] == 1
    board = {"rows": [{"symbol": "AAA", "name": "AAA Inc", "entry_zone": dict(DEM)}], "approaching_rows": []}
    live = {"AAA": {"price": 91.0, "change_pct": -4.2, "prev_day_close": 95.0}}
    da = DA.check_once(push=True, force=True, board=board, live=live, caps={"AAA": 5e9},
                       coll=colls["coll_demand"], owner="o@x", now=NOW, store=store)
    assert da["at"] == 0 and da["pushed"] == 0 and len(sent) == 1, "same key, same coll: one fact"
    # and the other way round: a key demand_alerts wrote silences zone_edge
    pre = _colls()
    pre["coll_demand"].update_one({"_id": DA.state_key("AAA", DEM, DAY, "at")},
                                  {"$set": {"symbol": "AAA"}}, upsert=True)
    out2, _ = _run(store, {"AAA": _snap(91.0, 95.0, -4.2)}, {"AAA": 5e9}, colls=pre)
    assert out2["pushed"] == 0 and len(sent) == 1 and len(out2["near_demand"]) == 1


def test_resident_is_on_the_board_tagged_and_never_pushed(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"RES": _doc("RES", [DEM], 91.5), "ARR": _doc("ARR", [DEM], 95.0),
             "UNK": _doc("UNK", [DEM], None)}
    snap = {"RES": _snap(91.0, 91.5, -0.5), "ARR": _snap(91.0, 95.0, -4.2), "UNK": _snap(91.0, None, -1.0)}
    out, colls = _run(store, snap, {s: 5e9 for s in store})
    rows = {r["symbol"]: r for r in out["near_demand"]}
    assert set(rows) == {"RES", "ARR", "UNK"}
    assert rows["ARR"]["arrival"] is True and rows["RES"]["arrival"] is False and rows["UNK"]["arrival"] is False
    assert [r["symbol"] for r in out["near_demand"]][0] == "ARR", "arrivals first"
    assert out["unknown_prev"] == 1
    assert [s["title"] for s in sent] == ["🧲 ARR in demand $90–92"]
    assert list(colls["coll_demand"].docs) == ["ARR:90.00-92.00:2026-09-03:at"]


def test_singles_capped_at_three_per_side_rest_one_digest_digest_names_recorded(monkeypatch):
    sent = _capture(monkeypatch)
    store, snap, caps = {}, {}, {}
    for i, px in enumerate([103.0, 102.5]):                         # broke: -0.97%, -0.49%
        s = f"B{i}"
        store[s], snap[s], caps[s] = _doc(s, [RES], 101.0), _snap(px, 101.0), 5e9
    for i, px in enumerate([101.9, 101.5, 101.2]):                  # near: 0.1%, 0.49%, 0.79%
        s = f"N{i}"
        store[s], snap[s], caps[s] = _doc(s, [RES], 99.0), _snap(px, 99.0), 5e9
    for i, px in enumerate([91.0, 92.2, 92.4, 92.6, 92.8]):         # demand: in, 0.22, 0.43, 0.65, 0.86
        s = f"D{i}"
        store[s], snap[s], caps[s] = _doc(s, [DEM], 95.0), _snap(px, 95.0, -3.0), 5e9
    out, colls = _run(store, snap, caps)
    assert out["singles_break"] == 3 and out["digest_break"] == 2
    assert out["singles_demand"] == 3 and out["digest_demand"] == 2 and out["pushed"] == 8
    titles = [s["title"] for s in sent]
    assert titles[:3] == ["🚀 B0 broke resistance $100–102 (+1.0%) → new highs",
                          "🚀 B1 broke resistance $100–102 (+0.5%) → new highs",
                          "🚀 N0 0.1% under resistance $100–102 → new highs"]
    assert titles[3] == "🚀 Breaking resistance — N1 0.49% +1 more"
    assert [l.split()[0] for l in sent[3]["body"].split("\n")] == ["N1", "N2"]
    assert titles[4:7] == ["🧲 D0 in demand $90–92", "🧲 D1 0.22% above demand $90–92",
                           "🧲 D2 0.43% above demand $90–92"]
    assert titles[7] == "🧲 Demand zone — D3 +1 more"
    assert [l.split()[0] for l in sent[7]["body"].split("\n")] == ["D3", "D4"]
    assert all(s["kind"] == "supply_break_alert" for s in sent[:4])
    assert all(s["kind"] == "demand_alert" for s in sent[4:])
    assert len(colls["coll_break"].docs) == 5, "digest names recorded too"
    assert len(colls["coll_demand"].docs) == 5
    assert ZE.MAX_SINGLES_PER_PASS == 3 and ZE.DIGEST_MAX == 6
    # board ordering: broke first, then near; arrivals first
    assert [r["symbol"] for r in out["breaking"]] == ["B0", "B1", "N0", "N1", "N2"]
    # B0/B1 broke RES TODAY (prev 101 inside it): Side A's fact only — the shelf
    # they are 0.49% / 0.97% above is not support until a close above it.
    assert [r["symbol"] for r in out["near_demand"]] == ["D0", "D1", "D2", "D3", "D4"]
    assert [r["arrival"] for r in out["near_demand"]] == [True] * 5


def test_second_identical_pass_pushes_nothing_but_still_lists_and_tracks(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES, DEM], 99.0), "BBB": _doc("BBB", [DEM], 95.0)}
    snap = {"AAA": _snap(101.5, 99.0), "BBB": _snap(91.0, 95.0, -4.2)}
    caps = {"AAA": 5e9, "BBB": 5e9}
    out1, colls = _run(store, snap, caps)
    assert out1["pushed"] == 2 and len(sent) == 2
    later = NOW + timedelta(minutes=1)
    snap2 = {"AAA": _snap(101.6, 99.0, now=later), "BBB": _snap(91.2, 95.0, -4.0, now=later)}
    out2, _ = _run(store, snap2, caps, colls=colls, now=later)
    assert out2["pushed"] == 0 and len(sent) == 2
    assert len(out2["breaking"]) == 1 and len(out2["near_demand"]) == 1
    assert out2["breaking"][0]["first_seen"] == "10:00" and out2["near_demand"][0]["first_seen"] == "10:00"
    assert len(colls["track_coll"].rows) == 4
    # a NEW tier on the same band is a new fact: near at 10:00, broke at 10:02 —
    # ONE push. The shelf it just went through (prev 99 < floor 100) is not
    # support today, so no 🧲 rides along for the same band in the same minute.
    later2 = NOW + timedelta(minutes=2)
    out3, _ = _run(store, {"AAA": _snap(103.0, 99.0, now=later2)}, caps, colls=colls, now=later2)
    assert out3["pushed"] == 1
    assert sent[-1]["title"] == "🚀 AAA broke resistance $100–102 (+1.0%) → new highs"
    assert [r["symbol"] for r in out3["near_demand"]] == []
    assert set(colls["coll_break"].docs) == {"AAA:100.00-102.00:2026-09-03:near", "AAA:100.00-102.00:2026-09-03:broke"}
    assert set(colls["coll_demand"].docs) == {"BBB:90.00-92.00:2026-09-03:at"}
    out3b, _ = _run(store, {"AAA": _snap(103.1, 99.0, now=later2)}, caps, colls=colls, now=later2)
    assert out3b["pushed"] == 0 and len(sent) == 3
    # tomorrow is a new day
    tmrw = NOW + timedelta(days=1)
    out4, _ = _run({"AAA": _doc("AAA", [RES, DEM], 99.0, day="2026-09-04")},
                   {"AAA": _snap(101.5, 99.0, now=tmrw)}, caps, colls=colls, now=tmrw)
    assert out4["pushed"] == 1 and out4["breaking"][0]["first_seen"] == "10:00"


def test_transport_failure_retries_but_muted_pref_is_terminal(monkeypatch):
    store = {"AAA": _doc("AAA", [RES], 99.0)}
    snap = {"AAA": _snap(101.5, 99.0)}
    colls = _colls()
    _capture(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    out, _ = _run(store, snap, {"AAA": 5e9}, colls=colls)
    assert out["pushed"] == 0 and colls["coll_break"].docs == {}, "failed transport retries next minute"
    _capture(monkeypatch, result={"sent": 0, "failed": 0, "total_targets": 0})
    out, _ = _run(store, snap, {"AAA": 5e9}, colls=colls)
    assert out["pushed"] == 1 and len(colls["coll_break"].docs) == 1, "nobody targeted = done today"


def test_dry_run_reads_everything_pushes_nothing_and_track_false_writes_nothing(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES, DEM], 99.0)}
    out, colls = _run(store, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9}, push=False)
    assert out["singles_break"] == 1 and out["pushed"] == 0 and sent == []
    assert colls["coll_break"].docs == {} and "latest" in colls["latest_coll"].docs
    assert len(colls["track_coll"].rows) == 1
    out2, colls2 = _run(store, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9}, push=False, track=False)
    assert out2["singles_break"] == 1 and colls2["latest_coll"].docs == {} and colls2["track_coll"].rows == []
    assert out2["breaking"][0]["first_seen"] is None


def test_empty_store_missing_snapshot_rows_are_quiet(monkeypatch):
    sent = _capture(monkeypatch)
    out, _ = _run({}, {}, {})
    assert out["ran"] and out["candidates"] == 0 and out["pushed"] == 0 and out["breaking"] == []
    out, _ = _run({"AAA": _doc("AAA", [RES], 99.0)}, {}, {"AAA": 5e9})
    assert out["priced"] == 0 and out["breaking"] == [] and sent == []


def test_a_shelf_broken_today_is_one_push_a_shelf_broken_yesterday_is_support(monkeypatch):
    """Regression (review 2026-09-03): with 'supply hi < px' alone the same band
    fired 🚀 broke AND 🧲 'above demand' in the same minute for one breakout."""
    sent = _capture(monkeypatch)
    for prev in (99.0, 101.0, 102.0):                            # under the floor / inside / on the top
        sent.clear()
        out, _ = _run({"AAA": _doc("AAA", [RES, DEM], prev)}, {"AAA": _snap(102.5, prev, 3.5)}, {"AAA": 5e9})
        assert out["breaking"][0]["tier"] == "broke", prev
        assert out["near_demand"] == [], "the shelf it is breaking today is not support"
        assert [s["kind"] for s in sent] == ["supply_break_alert"], prev
    # yesterday CLOSED 1.5% above the shelf; today pulled back to 0.49% above it:
    # not breaking anything (Side A None), an ARRIVAL at broken-supply support
    sent.clear()
    out2, colls = _run({"AAA": _doc("AAA", [RES, DEM], 103.5)}, {"AAA": _snap(102.5, 103.5, -1.0)}, {"AAA": 5e9})
    assert out2["breaking"] == []
    nd = out2["near_demand"][0]
    assert nd["tier"] == "near" and nd["role"] == "broken supply" and nd["arrival"] is True
    assert [s["title"] for s in sent] == ["🧲 AAA 0.49% above demand $100–102"]
    assert list(colls["coll_demand"].docs) == ["AAA:100.00-102.00:2026-09-03:at"]
    # closed ON the shelf's ring yesterday (102.5, 0.49% above): resident, listed, silent
    sent.clear()
    out3, _ = _run({"AAA": _doc("AAA", [RES, DEM], 102.5)}, {"AAA": _snap(102.5, 102.5, 0.0)}, {"AAA": 5e9})
    assert out3["near_demand"][0]["arrival"] is False and sent == []


# ── tracking ─────────────────────────────────────────────────────────────────
def test_track_rows_written_per_listed_row_with_the_exact_shape(monkeypatch):
    _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES, DEM], 99.0), "BBB": _doc("BBB", [DEM], 95.0)}
    out, colls = _run(store, {"AAA": _snap(101.5, 99.0), "BBB": _snap(91.0, 95.0, -4.2)},
                      {"AAA": 5e9, "BBB": 5e9})
    rows = colls["track_coll"].rows
    assert out["tracked"] == 2 and len(rows) == 2
    a = [r for r in rows if r["symbol"] == "AAA"][0]
    assert a == {"symbol": "AAA", "date": DAY, "ts": NOW.isoformat(), "side": "supply", "tier": "near",
                 "px": 101.5, "dist_pct": 0.49, "band": {"lo": 100.0, "hi": 102.0}}
    b = [r for r in rows if r["symbol"] == "BBB"][0]
    assert b["side"] == "demand" and b["tier"] == "in" and b["dist_pct"] == 0.0


def test_purge_deletes_rows_older_than_two_days_every_pass(monkeypatch):
    _capture(monkeypatch)
    colls = _colls()
    for d in ("2026-08-30", "2026-08-31", "2026-09-01", "2026-09-02"):
        colls["track_coll"].rows.append({"symbol": "OLD", "date": d, "ts": f"{d}T10:00:00-04:00",
                                         "side": "supply", "tier": "near", "px": 1.0, "dist_pct": 0.5,
                                         "band": {"lo": 1.0, "hi": 2.0}})
    out, _ = _run({"AAA": _doc("AAA", [RES], 99.0)}, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9}, colls=colls)
    assert out["purged"] == 2
    assert sorted({r["date"] for r in colls["track_coll"].rows}) == ["2026-09-01", "2026-09-02", DAY]
    assert ZE.TRACK_KEEP_DAYS == 2
    assert ZE.purge_track(None, NOW.date()) == 0


def test_first_seen_is_the_first_minute_listed_today_per_symbol_side_band(monkeypatch):
    _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [RES], 99.0)}
    colls = _colls()
    # yesterday's clocks never leak: the map doc is per day
    colls["latest_coll"].docs["first_seen"] = {"_id": "first_seen", "date": "2026-09-02",
                                               "rows": [["AAA:supply:100.00-102.00", "09:31"]]}
    t1, t2, t3 = NOW, NOW + timedelta(minutes=1), NOW + timedelta(minutes=2)
    _run(store, {"AAA": _snap(101.3, 99.0, now=t1)}, {"AAA": 5e9}, colls=colls, now=t1)
    _run(store, {"AAA": _snap(101.5, 99.0, now=t2)}, {"AAA": 5e9}, colls=colls, now=t2)
    out, _ = _run(store, {"AAA": _snap(101.7, 99.0, now=t3)}, {"AAA": 5e9}, colls=colls, now=t3)
    assert out["breaking"][0]["first_seen"] == "10:00"
    assert ZE.read_first_seen(colls["latest_coll"], DAY) == {"AAA:supply:100.00-102.00": "10:00"}
    assert ZE.read_first_seen(colls["latest_coll"], "2026-09-02") == {}, "another day = empty map"
    assert ZE.read_first_seen(None, DAY) == {}
    assert colls["latest_coll"].docs["first_seen"]["date"] == DAY
    assert ZE.read_track(colls["track_coll"], DAY, ["AAA"], as_of=t3) == \
        {"supply:AAA": [["10:00", 0.69], ["10:01", 0.49], ["10:02", 0.29]]}
    # a different band on the same side is its own clock
    other = {"kind": "supply", "lo": 104.0, "hi": 105.0, "touches": 2, "strength": 20.0}
    t4 = NOW + timedelta(minutes=5)
    out4, _ = _run({"AAA": _doc("AAA", [RES, other], 99.0)}, {"AAA": _snap(104.5, 99.0, now=t4)},
                   {"AAA": 5e9}, colls=colls, now=t4)
    assert out4["breaking"][0]["band"]["hi"] == 105.0 and out4["breaking"][0]["first_seen"] == "10:05"
    # off the board for a while (no row listed), then back on the FIRST band:
    # the clock is the first listing today, not the return (== earliest track row)
    t6, t7 = NOW + timedelta(minutes=6), NOW + timedelta(minutes=7)
    off, _ = _run(store, {"AAA": _snap(120.0, 99.0, now=t6)}, {"AAA": 5e9}, colls=colls, now=t6)
    assert off["breaking"] == [] and off["tracked"] == 0
    back, _ = _run(store, {"AAA": _snap(101.4, 99.0, now=t7)}, {"AAA": 5e9}, colls=colls, now=t7)
    assert back["breaking"][0]["first_seen"] == "10:00"
    # a dry run (track=False) shows the clocks it finds and starts none
    dry, _ = _run({"AAA": _doc("AAA", [RES, other], 99.0)}, {"AAA": _snap(104.6, 99.0, now=t7)},
                  {"AAA": 5e9}, colls=colls, now=t7, track=False)
    assert dry["breaking"][0]["first_seen"] == "10:05"
    fresh, fresh_colls = _run({"BBB": _doc("BBB", [RES], 99.0)}, {"BBB": _snap(101.4, 99.0, now=t7)},
                              {"BBB": 5e9}, now=t7, track=False)
    assert fresh["breaking"][0]["first_seen"] is None and fresh_colls["latest_coll"].docs == {}


def test_track_series_is_the_last_thirty_minutes_up_to_as_of_chronological():
    coll = FakeColl()
    for i in range(35):
        ts = (datetime(2026, 9, 3, 9, 31, tzinfo=ET) + timedelta(minutes=i)).isoformat()
        coll.rows.append({"symbol": "AAA", "date": DAY, "ts": ts, "side": "demand", "tier": "near",
                          "px": 91.0, "dist_pct": float(i), "band": {"lo": 90.0, "hi": 92.0}})
    last = datetime(2026, 9, 3, 10, 5, tzinfo=ET)
    series = ZE.read_track(coll, DAY, ["AAA", "ZZZ"], as_of=last)
    pts = series["demand:AAA"]
    assert len(pts) == ZE.TRACK_POINTS == 30
    assert pts[0] == ["09:36", 5.0] and pts[-1] == ["10:05", 34.0]
    assert "demand:ZZZ" not in series
    # the window is by time, not by count: rows older than 30 min before as_of are never read
    coll.calls.clear()
    mid = ZE.read_track(coll, DAY, ["AAA"], as_of=datetime(2026, 9, 3, 9, 45, tzinfo=ET))
    assert mid["demand:AAA"][0] == ["09:31", 0.0] and mid["demand:AAA"][-1] == ["09:45", 14.0]
    assert len(mid["demand:AAA"]) == 15 and coll.calls["find"] == 1
    assert ZE.read_track(coll, DAY, ["AAA"]) == series, "no as_of: the whole day, trimmed"
    assert ZE.read_track(None, DAY, ["AAA"]) == {}
    assert ZE.read_track(coll, DAY, []) == {}
    assert ZE.read_track(coll, "2026-09-02", ["AAA"], as_of=last) == {}


# ── API payload ──────────────────────────────────────────────────────────────
def test_api_payload_shape_ordering_and_json_safety(monkeypatch):
    _capture(monkeypatch)
    store = {"B0": _doc("B0", [RES], 101.0, np.float64(120.0)),
             "N0": _doc("N0", [RES, OVER], 99.0), "N1": _doc("N1", [RES], 99.0),
             "D0": _doc("D0", [DEM], 91.5), "D1": _doc("D1", [DEM], 95.0)}
    store["N1"]["bands"] = [dict(RES, touches=np.int64(3), strength=np.float64(40.0))]
    snap = {"B0": _snap(np.float64(103.0), np.float64(101.0)),
            "N0": _snap(101.9, 99.0), "N1": _snap(101.5, 99.0),
            "D0": _snap(91.0, 91.5, -0.5), "D1": _snap(92.5, 95.0, float("nan"))}
    caps = {"B0": np.float64(5e9), "N0": 5e9, "N1": 5e9, "D0": 5e9, "D1": 5e9}
    out, colls = _run(store, snap, caps)
    payload = ZE.api_payload(latest_coll=colls["latest_coll"], track_coll=colls["track_coll"], now=NOW)
    assert set(payload) >= {"as_of", "date", "in_session", "pass_sec", "params", "counts",
                            "breaking", "near_demand", "track", "disclaimer"}
    assert payload["as_of"] == NOW.isoformat() and payload["date"] == DAY and payload["in_session"] is True
    assert payload["params"] == {"edge_pct": 1.0, "broke_max_pct": 3.0, "min_cap_usd": 1e9,
                                 "min_touches_push": 2}
    assert payload["counts"] == {"breaking": 3, "near_demand": 2, "candidates": 5, "priced": 5,
                                 "stale_print": 0}
    # broke first; then near with new_highs first (N1 clear, N0 has OVER above), then dist
    assert [r["symbol"] for r in payload["breaking"]] == ["B0", "N1", "N0"]
    # B0 broke RES today (prev 101 inside it): Side A only — the shelf is not support yet
    assert [r["symbol"] for r in payload["near_demand"]] == ["D1", "D0"], \
        "arrival before residents, then distance"
    assert [r["arrival"] for r in payload["near_demand"]] == [True, False]
    row = payload["breaking"][0]
    assert set(row) == {"symbol", "name", "last", "dist_pct", "tier", "side", "role", "band", "cap",
                        "new_highs", "high_252", "pct_to_52w", "overhead_bands", "arrival",
                        "first_seen", "url"}
    assert set(row["band"]) == {"kind", "lo", "hi", "touches", "strength"}
    assert payload["track"] == {"supply:B0": [["10:00", -0.97]], "supply:N1": [["10:00", 0.49]],
                                "supply:N0": [["10:00", 0.1]], "demand:D1": [["10:00", 0.54]],
                                "demand:D0": [["10:00", 0.0]]}
    text = json.dumps(payload, allow_nan=False)                     # raises on NaN / numpy
    assert "NaN" not in text

    def _plain(o):
        if isinstance(o, dict):
            return all(isinstance(k, str) and _plain(v) for k, v in o.items())
        if isinstance(o, list):
            return all(_plain(v) for v in o)
        return o is None or type(o) in (bool, int, float, str)
    assert _plain(payload)
    assert type(payload["breaking"][1]["band"]["touches"]) is int
    assert type(payload["breaking"][0]["high_252"]) is float and type(payload["breaking"][0]["cap"]) is float
    stored = colls["latest_coll"].docs["latest"]
    assert stored["_id"] == "latest" and "track" not in stored and stored["breaking"] == payload["breaking"]


def test_api_payload_without_a_pass_and_in_session_is_evaluated_at_request_time(monkeypatch):
    empty = ZE.api_payload(latest_coll=FakeColl(), track_coll=FakeColl(), now=NOW)
    assert empty["as_of"] is None and empty["in_session"] is False and empty["reason"] == "no pass yet"
    assert empty["breaking"] == [] and empty["near_demand"] == [] and empty["track"] == {}
    json.dumps(empty, allow_nan=False)
    _capture(monkeypatch)
    last_pass = datetime(2026, 9, 3, 15, 59, tzinfo=ET)
    out, colls = _run({"AAA": _doc("AAA", [RES], 99.0)}, {"AAA": _snap(101.5, 99.0, now=last_pass)},
                      {"AAA": 5e9}, now=last_pass)
    evening = ZE.api_payload(latest_coll=colls["latest_coll"], track_coll=colls["track_coll"],
                             now=datetime(2026, 9, 3, 18, 0, tzinfo=ET))
    assert evening["in_session"] is False and evening["as_of"] == last_pass.isoformat()
    assert evening["track"] == {"supply:AAA": [["15:59", 0.49]]}


# ── the session gate ─────────────────────────────────────────────────────────
def test_session_gate_is_nine_thirty_one_to_four_weekdays():
    assert ZE.in_session(datetime(2026, 9, 3, 9, 30, tzinfo=ET)) is False
    assert ZE.in_session(datetime(2026, 9, 3, 9, 31, tzinfo=ET)) is True
    assert ZE.in_session(datetime(2026, 9, 3, 16, 0, tzinfo=ET)) is True
    assert ZE.in_session(datetime(2026, 9, 3, 16, 1, tzinfo=ET)) is False
    assert ZE.in_session(datetime(2026, 9, 5, 11, 0, tzinfo=ET)) is False     # Saturday
    assert ZE.in_session(datetime(2026, 9, 6, 11, 0, tzinfo=ET)) is False     # Sunday


def test_check_once_refuses_outside_rth_unless_forced():
    colls = _colls()
    out = ZE.check_once(store={}, now=datetime(2026, 9, 3, 7, 0, tzinfo=ET), **colls)
    assert out["ran"] is False and "RTH" in out["reason"]
    out = ZE.check_once(store={}, now=datetime(2026, 9, 3, 7, 0, tzinfo=ET), force=True, **colls)
    assert out["ran"] is True and out["candidates"] == 0


# ── source guards: the wiring ────────────────────────────────────────────────
def test_constants_locked():
    assert ZE.EDGE_PCT == 1.0 and ZE.BROKE_MAX_PCT == 3.0 and ZE.MIN_CAP_USD == 1e9
    assert ZE.MIN_TOUCHES_PUSH == 2 and ZE.MAX_SINGLES_PER_PASS == 3 and ZE.DIGEST_MAX == 6
    assert ZE.STALE_PRINT_SEC == 180 and ZE.TRACK_KEEP_DAYS == 2 and ZE.TRACK_POINTS == 30
    assert ZE.KIND_BREAK == "supply_break_alert" and ZE.STATE_COLL_BREAK == "supply_break_state"
    assert ZE.LATEST_COLL == "zone_edge_latest" and ZE.TRACK_COLL == "zone_edge_track"
    assert ZE.SESSION_OPEN.hour == 9 and ZE.SESSION_OPEN.minute == 31
    assert ZE.SESSION_CLOSE.hour == 16 and ZE.SESSION_CLOSE.minute == 0


def test_crontab_runs_zone_edge_every_minute_after_the_bounce_line():
    cron = (ROOT / "backend/crontab").read_text().splitlines()
    edge = [l for l in cron if "supply_demand.zone_edge" in l and not l.startswith("#")]
    assert len(edge) == 1 and edge[0].split()[:5] == ["*", "9-16", "*", "*", "1-5"]
    assert edge[0].split()[5:] == ["/usr/local/bin/python", "-m", "supply_demand.zone_edge"]
    bounce = [i for i, l in enumerate(cron) if "supply_demand.zone_bounce_alerts" in l and not l.startswith("#")]
    assert cron.index(edge[0]) > bounce[0], "placed after the zone_bounce entry"


def test_default_prefs_has_supply_break_alert_and_no_new_demand_kind():
    subs = (ROOT / "backend/push/subs.py").read_text()
    assert '"supply_break_alert": True' in subs
    assert subs.index('"zone_bounce_alert": True') < subs.index('"supply_break_alert": True')
    from push import subs as S
    assert S.default_prefs()["supply_break_alert"] is True
    assert S.default_prefs()["demand_alert"] is True
    src = (ROOT / "backend/supply_demand/zone_edge.py").read_text()
    assert 'kind=DA.KIND' in src and '"demand_alert"' not in src.replace("``demand_alert``", ""), \
        "the near-demand side reuses demand_alerts.KIND, never a new string"


def test_api_route_exists_and_offloads_to_a_thread():
    src = (ROOT / "backend/supply_demand/api.py").read_text()
    assert '@router.get("/supply-demand/zone-edge")' in src
    assert "asyncio.to_thread(zone_edge_mod.api_payload)" in src
    assert "not advice" in src[src.index('"/supply-demand/zone-edge"'):][:2000]


def test_no_per_symbol_network_call_in_the_pass():
    import inspect
    src = inspect.getsource(ZE.check_once)
    for forbidden in ("_fetch_massive_minute", "load_prices", "for_symbol", "requests.get",
                      "httpx", "with_today_bar", "shares_for", "name_for", "find_one(", "_already("):
        assert forbidden not in src, f"check_once reaches for {forbidden}"
    assert "bulk_snapshot(syms)" in src and "market_caps_for(list(prints), prints)" in src
    assert "_names_for(" in src and "_existing_keys(" in src and "read_first_seen(" in src


def test_pass_never_goes_to_mongo_per_symbol_one_bulk_read_each(monkeypatch):
    """Review 2026-09-03: name_for per row and find_one per push candidate were
    a Mongo round trip per listed name every minute. Now: one names $in read,
    one $in read per state coll, one first_seen doc read — however many rows."""
    sent = _capture(monkeypatch)
    from sepa import company_names
    fake_names = FakeNames({f"N{i}": f"Name {i}" for i in range(40)})
    monkeypatch.setattr(company_names, "_get_mongo", lambda: fake_names)
    store, snap, caps = {}, {}, {}
    for i in range(40):                                              # 40 push-eligible near rows
        s = f"N{i}"
        store[s], snap[s], caps[s] = _doc(s, [RES], 99.0), _snap(101.0 + i * 0.02, 99.0), 5e9
    for i in range(40):                                              # 40 demand arrivals
        s = f"D{i}"
        store[s], snap[s], caps[s] = _doc(s, [DEM], 95.0), _snap(91.0 + i * 0.02, 95.0, -3.0), 5e9
    colls = {"coll_break": FakeColl(), "coll_demand": FakeColl(),
             "latest_coll": FakeColl(), "track_coll": IndexedFakeColl()}
    out, _ = _run(store, snap, caps, colls=colls, names=None)
    assert len(out["breaking"]) == 40 and len(out["near_demand"]) == 40
    assert out["pushed"] == 8 and len(sent) == 8                     # 3+1 per side
    assert fake_names.calls == 1, "one names read for 80 listed rows"
    assert all(r["name"] == f"Name {r['symbol'][1:]}" for r in out["breaking"])
    assert all(r["name"] is None for r in out["near_demand"]), "D* names are not in the cache"
    assert out["breaking"][0]["symbol"] == "N39", "closest to the ceiling first"
    assert sent[0]["body"].endswith("· Name 39"), "pushes carry the bulk-read name"
    assert sent[3]["kind"] == "supply_break_alert" and sent[3]["body"].endswith("+31 more"), \
        "37 digest items: 6 spelled out, the rest counted"
    for c in ("coll_break", "coll_demand"):
        assert colls[c].calls["find_one"] == 0 and colls[c].calls["find"] == 1, c
        assert colls[c].calls["update_one"] == 40, "digest names recorded too"
    assert colls["latest_coll"].calls["find_one"] == 1 and colls["latest_coll"].calls["replace_one"] == 2
    assert colls["track_coll"].calls == {"create_index": 1, "insert_many": 1, "delete_many": 1}
    assert colls["track_coll"].indexes == [([("date", 1), ("symbol", 1), ("ts", 1)], {"name": "date_symbol_ts"})]
    # second minute: the 80 keys are already recorded — still ONE read per coll, nothing pushed
    later = NOW + timedelta(minutes=1)
    snap2 = {s: _snap(v["last_trade_price"], v["prev_day_close"], v["change_pct"], now=later)
             for s, v in snap.items()}
    out2, _ = _run(store, snap2, caps, colls=colls, names=None, now=later)
    assert out2["pushed"] == 0 and len(sent) == 8
    for c in ("coll_break", "coll_demand"):
        assert colls[c].calls["find_one"] == 0 and colls[c].calls["find"] == 2, c
    assert colls["track_coll"].calls["create_index"] == 2, "idempotent, once per pass"
    assert fake_names.calls == 2


def test_names_read_failure_and_missing_index_support_are_quiet(monkeypatch):
    _capture(monkeypatch)
    from sepa import company_names
    monkeypatch.setattr(company_names, "_get_mongo", lambda: None)
    out, colls = _run({"AAA": _doc("AAA", [RES], 99.0)}, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9},
                      names=None)
    assert out["pushed"] == 1 and out["breaking"][0]["name"] is None
    assert "create_index" not in colls["track_coll"].calls, "the plain fake has none — and the pass ran"
    assert ZE._names_for([]) == {} and ZE._existing_keys(None, ["k"]) == set()
    assert ZE._existing_keys(FakeColl(), []) == set() and ZE.ensure_track_index(None) is False

    class Broken:
        def find(self, q, projection=None):
            raise RuntimeError("down")
    assert ZE._existing_keys(Broken(), ["k"]) == set(), "read failure = push again, never never"


# ── fixes 2026-09-05 (review of the S/D zone logic; Ajay: "yes please fix the bugs") ──
def test_near_tier_ignores_a_supply_band_yesterday_closed_above(monkeypatch):
    """Blocker: prev 104 > RES.hi 102 = broken supply = SUPPORT (Side B's rule),
    yet a pullback INTO that shelf read as 'near resistance → new highs' and
    pushed 🚀 five minutes after the same band pushed 🧲 — two contradictory
    phone pushes on one band on a down day."""
    assert ZE.read_breaking(101.5, [RES], 104.0, 104.5) is None
    assert ZE.read_breaking(102.0, [RES], 104.0, 104.5) is None, "on the top: still not resistance"
    near = ZE.read_breaking(101.5, [RES], 99.0, None)
    assert near and near["tier"] == "near" and near["dist_pct"] == 0.49, "prev under the band: as before"
    on_top = ZE.read_breaking(101.5, [RES], 102.0, None)
    assert on_top and on_top["tier"] == "near", "prev ON the top (hi >= prev): resistance, same edge as broke"
    assert ZE.read_breaking(101.5, [RES], None, None)["tier"] == "near", "unknown prev: geometry only"
    # a broken band is skipped; the next UNBROKEN band is the resistance
    nxt = {"kind": "supply", "lo": 104.2, "hi": 104.5, "touches": 2, "strength": 20.0}
    r = ZE.read_breaking(103.7, [RES, nxt], 104.0, None)
    assert r["tier"] == "near" and r["band"]["hi"] == 104.5 and r["dist_pct"] == 0.77
    # end to end: prev 104. 10:00 print 102.5 -> 🧲 arrival at broken-supply support;
    # 10:05 print 101.5 (inside the shelf) -> Side A silent, no 🚀, the row never flips side
    sent = _capture(monkeypatch)
    store = {"XYZ": _doc("XYZ", [RES], 104.0, 104.5)}
    colls = _colls()
    out1, _ = _run(store, {"XYZ": _snap(102.5, 104.0, -1.4)}, {"XYZ": 5e9}, colls=colls)
    assert [r["side"] for r in out1["near_demand"]] == ["demand"] and out1["breaking"] == []
    later = NOW + timedelta(minutes=5)
    out2, _ = _run(store, {"XYZ": _snap(101.5, 104.0, -2.4, now=later)}, {"XYZ": 5e9}, colls=colls, now=later)
    assert out2["breaking"] == [] and out2["near_demand"] == []
    assert [s["kind"] for s in sent] == ["demand_alert"], "one band, one day, one fact"


def test_api_payload_from_another_day_is_never_live(monkeypatch):
    """A cold zone_store (warm failed) left Thursday's doc as 'latest' all Friday,
    served with in_session True and Thursday's rows under a live header."""
    _capture(monkeypatch)
    thu = datetime(2026, 9, 3, 15, 59, tzinfo=ET)
    out, colls = _run({"AAA": _doc("AAA", [RES], 99.0)}, {"AAA": _snap(101.5, 99.0, now=thu)},
                      {"AAA": 5e9}, now=thu)
    fri = datetime(2026, 9, 4, 10, 0, tzinfo=ET)
    p = ZE.api_payload(latest_coll=colls["latest_coll"], track_coll=colls["track_coll"], now=fri)
    assert p["in_session"] is False and p["date"] == "2026-09-03"
    assert p["reason"] == "last pass 2026-09-03; no pass yet today"
    assert len(p["breaking"]) == 1, "the evening/weekend board still shows the last pass"
    json.dumps(p, allow_nan=False)
    same = ZE.api_payload(latest_coll=colls["latest_coll"], track_coll=colls["track_coll"],
                          now=thu + timedelta(minutes=1))
    assert same["in_session"] is True and "reason" not in same, "same day: live as before"
    # a cold store on Friday writes an EMPTY payload with the reason -> the board self-heals
    out2, _ = _run({}, {}, {}, colls=colls, now=fri)
    assert out2["reason"] == "zone store empty for today"
    p2 = ZE.api_payload(latest_coll=colls["latest_coll"], track_coll=colls["track_coll"], now=fri)
    assert p2["as_of"] is None and p2["date"] == "2026-09-04" and p2["breaking"] == [] and p2["track"] == {}
    assert p2["reason"] == "zone store empty for today"
    json.dumps(p2, allow_nan=False)
    dry = _colls()
    _run({}, {}, {}, colls=dry, now=fri, track=False)
    assert dry["latest_coll"].docs == {}, "a dry run on a cold store writes nothing"


def test_session_gate_skips_market_holidays_in_all_three_modules():
    """Weekday-only gates ran on holidays: the store warmed with the holiday's date
    and the board said 'refreshes every minute' over an empty list."""
    from supply_demand import zone_bounce_alerts as ZB
    from market_hours.reminder import is_market_day
    labor_day = datetime(2026, 9, 7, 10, 0, tzinfo=ET)
    assert is_market_day(labor_day) is False, "the house calendar (market_hours/reminder.py) is the one source"
    assert ZE.in_session(labor_day) is False and ZB.in_session(labor_day) is False
    assert DA.in_session(labor_day) is False
    tue = datetime(2026, 9, 8, 10, 0, tzinfo=ET)
    assert ZE.in_session(tue) is True and ZB.in_session(tue) is True and DA.in_session(tue) is True
    colls = _colls()
    assert ZE.check_once(store={}, now=labor_day, **colls)["ran"] is False


def test_state_and_first_seen_keys_use_fixed_two_decimals():
    """':g' (6 significant digits) collapsed two bands on a $10,000+ name into
    one key — the second band was silently deduped for the day."""
    from supply_demand import zone_bounce_alerts as ZB
    a = {"kind": "supply", "lo": 12345.67, "hi": 12400.0, "touches": 2}
    b = {"kind": "supply", "lo": 12345.72, "hi": 12400.0, "touches": 2}
    assert ZE.break_state_key("X", a, DAY, "near") != ZE.break_state_key("X", b, DAY, "near")
    assert ZE.break_state_key("X", a, DAY, "near") == "X:12345.67-12400.00:2026-09-03:near"
    assert ZE.first_seen_key("X", "supply", a) != ZE.first_seen_key("X", "supply", b)
    assert ZE.first_seen_key("AAA", "supply", RES) == "AAA:supply:100.00-102.00"
    assert DA.state_key("X", a, DAY, "at") != DA.state_key("X", b, DAY, "at")
    assert ZB.state_key("X", a, DAY) != ZB.state_key("X", b, DAY)
    assert ZB.state_key("NTAP", {"lo": 161.78, "hi": 167.54}, DAY) == "NTAP:161.78-167.54:2026-09-03"
    assert ZE._band_txt(RES) == "$100–102", "display text keeps the short form"


def test_phone_gate_near_demand_needs_five_percent_room_to_supply(monkeypatch):
    """Ajay 2026-09-05: "When alert I need the same logic. Need only alerts on
    stocks that have atleast 5% to Supply and also <1% bounce from demand zone".
    The board lists; only the phone tightens."""
    from supply_demand import alert_gates as AG
    sent = _capture(monkeypatch)
    tight = {"kind": "supply", "lo": 93.0, "hi": 94.0, "touches": 2, "strength": 20.0}   # 2.2% over a $91 print
    # prev 93.5: still an arrival (1.6% above DEM's top) AND the lid is unbroken (94 >= 93.5)
    out, colls = _run({"AAA": _doc("AAA", [DEM, tight], 93.5)}, {"AAA": _snap(91.0, 93.5, -2.7)}, {"AAA": 5e9})
    assert [r["symbol"] for r in out["near_demand"]] == ["AAA"] and out["near_demand"][0]["arrival"] is True
    assert sent == [] and out["pushed"] == 0 and out["skipped_room"] == 1 and colls["coll_demand"].docs == {}
    roomy = {"kind": "supply", "lo": 96.0, "hi": 97.0, "touches": 2, "strength": 20.0}   # 5.49% over
    out2, _ = _run({"AAA": _doc("AAA", [DEM, roomy], 95.0)}, {"AAA": _snap(91.0, 95.0, -4.2)}, {"AAA": 5e9})
    assert out2["pushed"] == 1 and out2["skipped_room"] == 0
    assert sent[-1]["body"] == "$91 · tested 2x · room +5.5% -> $96 · $5.0B"
    out3, _ = _run({"AAA": _doc("AAA", [DEM], 95.0)}, {"AAA": _snap(91.0, 95.0, -4.2)}, {"AAA": 5e9})
    assert out3["pushed"] == 1 and sent[-1]["body"] == "$91 · tested 2x · room: clear runway · $5.0B"
    assert ZE.EDGE_PCT == AG.ALERT_MAX_ABOVE_DEMAND_PCT == 1.0, "the in/near tier IS the <1% rule — reused, not duplicated"


def test_phone_gate_breaking_needs_five_percent_to_the_next_band(monkeypatch):
    """'At least 5% to supply' applies to every phone kind: a 🚀 push wants 5% from
    the print to the NEXT band above the one being broken."""
    sent = _capture(monkeypatch)
    close_next = {"kind": "supply", "lo": 104.0, "hi": 106.0, "touches": 1, "strength": 20.0}   # 2.5% over $101.5
    # RES top 102 >= 98% of the 52w high 103 -> new_highs by the 52w rule even with a band overhead
    out, colls = _run({"AAA": _doc("AAA", [RES, close_next], 99.0, 103.0)}, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9})
    row = out["breaking"][0]
    assert row["new_highs"] is True and row["overhead_bands"] == 1
    assert sent == [] and out["pushed"] == 0 and out["skipped_room"] == 1 and colls["coll_break"].docs == {}
    out2, _ = _run({"AAA": _doc("AAA", [RES, OVER], 99.0, 103.0)}, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9})
    assert out2["pushed"] == 1 and out2["skipped_room"] == 0
    assert sent[-1]["body"] == "$101.5 · tested 3x · 52w high $103 (+1.5%) · room +8.4% -> $110 · $5.0B"
    out3, _ = _run({"AAA": _doc("AAA", [RES], 99.0, 103.0)}, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9})
    assert out3["pushed"] == 1 and "· room: clear runway ·" in sent[-1]["body"]


# ── integrator fixes 2026-09-05 (review of the 22-bug sweep) ─────────────────
def test_overhead_counts_an_overlapping_supply_band_whose_top_is_above_the_broken_one(monkeypatch):
    """Review 2026-09-05: overhead was 'supply bands with lo > band.hi', so a lid
    OVERLAPPING the band being broken (99-104 over 96-99.5, print 100) was
    invisible — new_highs True, overhead 0, a 🚀 push with the print INSIDE a
    supply band, and zone_edge_entry skipped its room check on the same fact.
    Overhead is every OTHER supply band whose top is above this band's top."""
    a = {"kind": "supply", "lo": 96.0, "hi": 99.5, "touches": 3, "strength": 30.0}
    b = {"kind": "supply", "lo": 99.0, "hi": 104.0, "touches": 2, "strength": 25.0}
    r = ZE.read_breaking(100.0, [a, b], 99.0)
    assert r["tier"] == "broke" and r["band"]["hi"] == 99.5
    assert r["overhead_bands"] == 1 and r["new_highs"] is False, "99-104 still sits overhead"
    # the near tier reads the same way: RES 100-102 approached with 101-105 overlapping it
    ovl = {"kind": "supply", "lo": 101.0, "hi": 105.0, "touches": 2, "strength": 25.0}
    n = ZE.read_breaking(101.5, [RES, ovl], 99.0)
    assert n["tier"] == "near" and n["band"]["hi"] == 102.0
    assert n["overhead_bands"] == 1 and n["new_highs"] is False
    # non-overlapping geometry is byte-for-byte unchanged
    assert ZE.read_breaking(101.5, [RES, OVER], 99.0)["overhead_bands"] == 1
    assert ZE.read_breaking(101.5, [RES], 99.0)["overhead_bands"] == 0
    # end to end: the row lists (broke, not new highs) and the phone stays quiet
    sent = _capture(monkeypatch)
    out, _ = _run({"OVL": _doc("OVL", [a, b], 99.0)}, {"OVL": _snap(100.0, 99.0, 1.0)}, {"OVL": 5e9})
    assert [(r["tier"], r["new_highs"], r["overhead_bands"]) for r in out["breaking"]] == [("broke", False, 1)]
    assert sent == [] and out["pushed"] == 0


def test_a_transient_empty_store_read_does_not_overwrite_todays_live_payload(monkeypatch):
    """Review 2026-09-05: zone_store.load swallows a Mongo read error and returns
    {}, and the cold-store self-heal wrote an EMPTY 'latest' on every {} — one
    failed find at 10:30 blanked the day's board ('no pass yet today') and
    zone_edge_entry read as_of None for a minute. A latest doc that is a real
    pass from TODAY is kept; a stale-day or missing doc is still replaced."""
    _capture(monkeypatch)
    colls = _colls()
    out1, _ = _run({"AAA": _doc("AAA", [RES], 99.0)}, {"AAA": _snap(101.5, 99.0)}, {"AAA": 5e9}, colls=colls)
    assert len(out1["breaking"]) == 1
    live = dict(colls["latest_coll"].docs["latest"])
    later = NOW + timedelta(minutes=1)
    out2, _ = _run({}, {}, {}, colls=colls, now=later)
    assert out2["reason"] == "zone store empty for today" and out2["latest_written"] is False
    kept = colls["latest_coll"].docs["latest"]
    assert kept["as_of"] == live["as_of"] and len(kept["breaking"]) == 1, \
        "one failed store read must not blank the day's board"
    p = ZE.api_payload(latest_coll=colls["latest_coll"], track_coll=colls["track_coll"], now=later)
    assert p["in_session"] is True and len(p["breaking"]) == 1 and "reason" not in p
    # a doc from ANOTHER day is still replaced — the self-heal the 2026-09-05 fix was written for
    stale = _colls()
    stale["latest_coll"].docs["latest"] = dict(live, date="2026-09-02")
    out3, _ = _run({}, {}, {}, colls=stale)
    assert out3["latest_written"] is True
    assert stale["latest_coll"].docs["latest"]["reason"] == "zone store empty for today"
    # and so is a missing doc (first pass of the day on a cold store)
    cold = _colls()
    out4, _ = _run({}, {}, {}, colls=cold)
    assert out4["latest_written"] is True and cold["latest_coll"].docs["latest"]["date"] == DAY
