"""🔑 key_level_alert (2026-09-25) — `supply_demand/key_level_alerts.py` and
its hook on the zone_edge minute.

Ajay 2026-09-25: "I wanna know when key levels are broken for a stock."

Pins the spec v2 §3.7 push: the close tier only (16:05–16:30, half days
13:05–13:30), PUSH_PERIODS members only, the per-LIFE week/month latch, the
ARMED 52-week latch, claim-before-send with release on a transport failure,
"nobody targeted" terminal (muted), singles for holdings then ONE digest,
the exact push strings, dry runs that write nothing, the zone_edge hook at
all three exits, and the OFF-by-default pref. Every coll, sender, frame,
snapshot and scope is injected: no network, no Mongo (conftest refuses it).
"""
from __future__ import annotations

import collections
import inspect
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from supply_demand import alert_status as AS
from supply_demand import key_level_alerts as KLA
from supply_demand import key_levels as KL
from supply_demand import zone_edge as ZE

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


# --------------------------------------------------------------------------
# fakes
# --------------------------------------------------------------------------
class FakeColl:
    """claim coll (update_one $setOnInsert / delete_one / find $in), state
    doc coll (find_one / replace_one) and pass coll (replace_one) in one."""

    def __init__(self):
        self.docs = {}
        self.calls = collections.Counter()

    def find_one(self, q):
        self.calls["find_one"] += 1
        d = self.docs.get(q["_id"])
        return dict(d) if d else None

    def update_one(self, q, u, upsert=False):
        self.calls["update_one"] += 1
        existed = q["_id"] in self.docs
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        if not existed:
            d.update(u.get("$setOnInsert", {}))
        return SimpleNamespace(matched_count=1 if existed else 0,
                               upserted_id=None if existed else q["_id"])

    def delete_one(self, q):
        self.calls["delete_one"] += 1
        self.docs.pop(q["_id"], None)

    def replace_one(self, q, doc, upsert=False):
        self.calls["replace_one"] += 1
        self.docs[q["_id"]] = dict(doc)

    def find(self, q, projection=None):
        self.calls["find"] += 1
        for k in q["_id"]["$in"]:
            if k in self.docs:
                yield dict(self.docs[k])

    @property
    def writes(self):
        return sum(self.calls[k] for k in ("update_one", "delete_one", "replace_one"))


class Sender:
    def __init__(self, result=None, raises=False):
        self.sent, self.result, self.raises = [], result, raises

    def __call__(self, owner, msg, kind):
        self.sent.append({"owner": owner, "kind": kind, **msg})
        if self.raises:
            raise RuntimeError("apns down")
        return self.result or {"sent": 1, "failed": 0, "total_targets": 1}


def _colls():
    return {"first_coll": FakeColl(), "claim_coll": FakeColl(), "pass_coll": FakeColl()}


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _market_days(start: str, end: str) -> list:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(start)
    while d <= pd.Timestamp(end):
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d += pd.Timedelta(days=1)
    return out


def _frame(end: str, rows=None, *, start="2026-07-01", base=(120.0, 90.0, 102.0)) -> pd.DataFrame:
    """Daily bars `start`..`end`; every day (high, low, close) = base unless
    `rows` overrides it. open = close."""
    idx = pd.DatetimeIndex(_market_days(start, end))
    h, l, c = base
    df = pd.DataFrame({"open": c, "high": h, "low": l, "close": c, "volume": 1e6}, index=idx)
    for day, (hh, ll, cc) in (rows or {}).items():
        ts = pd.Timestamp(day)
        if ts in df.index:
            df.loc[ts, ["high", "low", "close", "open"]] = [hh, ll, cc, cc]
    return df


def _at(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ET)


def _snap(frame, now, *, close, low=None, high=None, px=None, age_sec=30):
    """A bulk_snapshot row whose prev_day_close IS the cached last close (the
    §3.1(b) verification passes)."""
    ts = int((now - timedelta(seconds=age_sec)).timestamp() * 1000)
    return {"open": close, "high": high if high is not None else close,
            "low": low if low is not None else close, "close": close,
            "last_trade_price": px if px is not None else close, "last_trade_ts_ms": ts,
            "prev_day_close": float(frame["close"].iloc[-1])}


def _run(sym, frame, snap_row, now, colls, *, held=True, sender=None, push=True,
         dry_run=False, scope=None):
    scope = scope or {"symbols": [sym], "held": [sym] if held else []}
    return KLA.run_pass(snapshot={sym: snap_row}, now=now, push=push, owner="o@x",
                        scope=scope, frames={sym: frame}, sender=sender or Sender(),
                        dry_run=dry_run, **colls)


# The WEEK scenario: prior week 09-14..09-18 lows 101 except 09-16 at 100.00
# (PWL 100, as_of Fri 09-18); August high 120 / low 90 (PMH / PML far away);
# fewer than 252 bars, so no 52-week members.
WEEK = {"2026-09-14": (103.0, 101.0, 102.0), "2026-09-15": (103.0, 101.0, 102.0),
        "2026-09-16": (103.0, 100.0, 102.0), "2026-09-17": (103.0, 101.0, 102.0),
        "2026-09-18": (103.0, 101.0, 102.0)}


def _week(end, extra=None):
    return _frame(end, {**WEEK, **(extra or {})})


# --------------------------------------------------------------------------
# close window
# --------------------------------------------------------------------------
def test_rth_broken_member_never_pushes_and_stamps_first_through():
    colls = _colls()
    fr = _week("2026-09-18")
    now = _at(2026, 9, 21, 10, 42)
    snd = Sender()
    out = _run("WULX", fr, _snap(fr, now, close=99.7, low=99.6, px=99.7), now, colls, sender=snd)
    c = out["counts"]
    assert c["broken"] == 1 and c["closed_beyond"] == 0 and c["pushed"] == 0
    assert snd.sent == [] and colls["claim_coll"].calls["update_one"] == 0
    first = colls["first_coll"].docs["2026-09-21"]["first"]
    assert first == {"WULX|week_low_10000|down|through": "10:42"}
    assert out["reason"] == "close verdicts push 16:05–16:30 ET"
    assert colls["pass_coll"].docs["key_level_alert"]["reason"] == out["reason"]
    # a second pass with nothing new writes NO state doc
    w = colls["first_coll"].calls["replace_one"]
    _run("WULX", fr, _snap(fr, _at(2026, 9, 21, 10, 43), close=99.7, low=99.6),
         _at(2026, 9, 21, 10, 43), colls)
    assert colls["first_coll"].calls["replace_one"] == w
    assert colls["first_coll"].docs["2026-09-21"]["first"]["WULX|week_low_10000|down|through"] == "10:42"


@pytest.mark.parametrize("hh,mm,fires", [(16, 4, False), (16, 5, True), (16, 29, True),
                                         (16, 30, False), (19, 0, False)])
def test_close_window_is_16_05_to_16_30(hh, mm, fires):
    colls = _colls()
    fr = _week("2026-09-18")
    now = _at(2026, 9, 21, hh, mm)
    snd = Sender()
    out = _run("WULX", fr, _snap(fr, now, close=99.8, low=99.5), now, colls, sender=snd)
    assert (out["counts"]["pushed"] == 1) is fires, out["counts"]
    assert bool(snd.sent) is fires
    if not fires:
        assert colls["claim_coll"].calls["update_one"] == 0, "nothing claimed outside the window"


def test_half_day_window_is_13_05_to_13_30():
    fr = _frame("2026-11-25", {"2026-11-16": (103.0, 100.0, 102.0), "2026-11-17": (103.0, 101.0, 102.0),
                               "2026-11-18": (103.0, 101.0, 102.0), "2026-11-19": (103.0, 101.0, 102.0),
                               "2026-11-20": (103.0, 101.0, 102.0)})
    for (hh, mm), fires in (((13, 5), True), ((13, 29), True), ((13, 30), False),
                            ((12, 59), False), ((16, 10), False)):
        colls = _colls()
        now = _at(2026, 11, 27, hh, mm)
        out = _run("WULX", fr, _snap(fr, now, close=99.8, low=99.5), now, colls)
        assert (out["counts"]["pushed"] == 1) is fires, (hh, mm, out["counts"])
    colls = _colls()
    out = _run("WULX", fr, _snap(fr, _at(2026, 11, 27, 10, 0), close=101.0), _at(2026, 11, 27, 10, 0), colls)
    assert out["reason"] == "close verdicts push 13:05–13:30 ET"


def test_NEGATIVE_day_levels_never_push():
    """A close through the PRIOR-DAY low only: no day member is even read."""
    colls = _colls()
    fr = _week("2026-09-21", {"2026-09-21": (102.0, 101.5, 102.0)})
    now = _at(2026, 9, 22, 16, 10)
    out = _run("WULX", fr, _snap(fr, now, close=101.0, low=100.9), now, colls)
    assert out["counts"]["pushed"] == 0 and out["counts"]["closed_beyond"] == 0
    assert out["keys"] == [] and out["messages"] == []
    assert not any(":day:" in k for k in colls["claim_coll"].docs)


# --------------------------------------------------------------------------
# week / month latch: once per LIFE and direction
# --------------------------------------------------------------------------
def test_week_latch_is_once_per_level_life_and_direction():
    colls = _colls()
    snd = Sender()
    # Mon: close under PWL 100.00 -> push
    fr = _week("2026-09-18")
    now = _at(2026, 9, 21, 16, 10)
    out = _run("WULX", fr, _snap(fr, now, close=99.8, low=99.5), now, colls, sender=snd)
    assert out["counts"]["pushed"] == 1
    assert snd.sent[-1]["title"] == "🔑 WULX closed under prior-week low $100.00"
    assert "KL:WULX:week:low:down:2026-09-18" in colls["claim_coll"].docs
    # Tue: close back over -> push "closed back over"
    fr = _week("2026-09-21", {"2026-09-21": (102.0, 99.5, 99.8)})
    now = _at(2026, 9, 22, 16, 10)
    out = _run("WULX", fr, _snap(fr, now, close=100.3, low=99.6), now, colls, sender=snd)
    assert out["counts"]["pushed"] == 1
    assert snd.sent[-1]["title"] == "🔑 WULX closed back over prior-week low $100.00"
    # Wed: close under AGAIN -> NO push (same life, same direction)
    fr = _week("2026-09-22", {"2026-09-21": (102.0, 99.5, 99.8), "2026-09-22": (100.5, 99.6, 100.3)})
    now = _at(2026, 9, 23, 16, 10)
    out = _run("WULX", fr, _snap(fr, now, close=99.7, low=99.6), now, colls, sender=snd)
    assert out["counts"]["closed_beyond"] == 1 and out["counts"]["pushed"] == 0
    assert out["counts"]["claimed_elsewhere"] == 1 and len(snd.sent) == 2
    # next week's PWL (a new as_of) is a new life -> pushes again
    rows = {"2026-09-21": (102.0, 99.5, 99.8), "2026-09-22": (100.5, 99.6, 100.3),
            "2026-09-23": (100.3, 99.5, 99.7), "2026-09-24": (100.0, 99.2, 99.5),
            "2026-09-25": (100.0, 99.0, 99.5)}
    fr = _week("2026-09-25", rows)
    now = _at(2026, 9, 28, 16, 10)
    out = _run("WULX", fr, _snap(fr, now, close=98.7, low=98.6), now, colls, sender=snd)
    assert out["counts"]["pushed"] == 1 and len(snd.sent) == 3
    assert "KL:WULX:week:low:down:2026-09-25" in colls["claim_coll"].docs
    assert snd.sent[-1]["title"] == "🔑 WULX closed under prior-week low $99.00"


# --------------------------------------------------------------------------
# year latch: ARMED, re-arms only on a close back inside the CLAIMED level
# --------------------------------------------------------------------------
def _year(end, rows):
    return _frame(end, {"2026-03-04": (150.0, 140.0, 145.0), **rows},
                  start="2025-06-02", base=(120.0, 90.0, 100.0))


def test_year_latch_is_armed_and_rearms_only_past_the_claimed_level_by_the_buffer():
    colls = _colls()
    snd = Sender()
    d1 = {"2026-09-21": (149.0, 140.0, 148.0)}
    fr = _year("2026-09-21", d1)
    assert len(KL.closed_frame(fr, date(2026, 9, 22))) >= KL.YEAR_BARS
    now = _at(2026, 9, 22, 16, 10)
    out = _run("MP", fr, _snap(fr, now, close=151.0, high=151.5, low=147.0), now, colls, sender=snd)
    assert out["counts"]["pushed"] == 1, out
    assert snd.sent[-1]["title"] == "🔑 MP closed over 52-week high $150.00"
    assert "level: 52-week high, set Wed 03-04" in snd.sent[-1]["body"]
    claim = colls["claim_coll"].docs["KL:MP:year:high:up"]
    assert claim["level"] == 150.0 and claim["session"] == "2026-09-22"
    # day 2: a NEW 52wH (151.50) and a close over it again -> NO push
    d2 = {**d1, "2026-09-22": (151.5, 147.0, 151.0)}
    fr = _year("2026-09-22", d2)
    now = _at(2026, 9, 23, 16, 10)
    out = _run("MP", fr, _snap(fr, now, close=153.0, high=153.5, low=150.8), now, colls, sender=snd)
    assert out["counts"]["closed_beyond"] == 1 and out["counts"]["pushed"] == 0
    assert out["counts"]["claimed_elsewhere"] == 1 and out["counts"]["rearmed"] == 0
    # day 3: a close at claimed x (1 - 0.14%) -> NOT re-armed
    d3 = {**d2, "2026-09-23": (153.5, 150.5, 153.0)}
    fr = _year("2026-09-23", d3)
    now = _at(2026, 9, 24, 16, 10)
    out = _run("MP", fr, _snap(fr, now, close=round(150.0 * (1 - 0.0014), 2), low=149.5), now,
               colls, sender=snd)
    assert out["counts"]["rearmed"] == 0 and "KL:MP:year:high:up" in colls["claim_coll"].docs
    # ... a close at claimed x (1 - 0.16%) -> re-armed silently
    out = _run("MP", fr, _snap(fr, now, close=round(150.0 * (1 - 0.0016), 2), low=149.5), now,
               colls, sender=snd)
    assert out["counts"]["rearmed"] == 1 and out["counts"]["pushed"] == 0
    assert "KL:MP:year:high:up" not in colls["claim_coll"].docs and len(snd.sent) == 1
    # day 4: the next close over -> push
    d4 = {**d3, "2026-09-24": (153.0, 149.5, 149.76)}
    fr = _year("2026-09-24", d4)
    now = _at(2026, 9, 25, 16, 10)
    out = _run("MP", fr, _snap(fr, now, close=154.0, high=154.2, low=150.0), now, colls, sender=snd)
    assert out["counts"]["pushed"] == 1 and len(snd.sent) == 2
    assert colls["claim_coll"].docs["KL:MP:year:high:up"]["level"] == 153.5


def test_year_rearm_helper_both_directions_and_negatives():
    up = {"level": 100.0, "direction": "up"}
    assert KLA.year_rearm(up, 99.84) is True and KLA.year_rearm(up, 99.86) is False
    dn = {"level": 100.0, "direction": "down"}
    assert KLA.year_rearm(dn, 100.16) is True and KLA.year_rearm(dn, 100.14) is False
    assert KLA.year_rearm(None, 90.0) is False
    assert KLA.year_rearm({"level": None, "direction": "up"}, 90.0) is False
    assert KLA.year_rearm({"level": 100.0, "direction": "sideways"}, 90.0) is False
    assert KLA.year_rearm(up, None) is False


def test_claim_keys():
    wk = {"period": "week", "kind": "low", "direction": "down", "as_of": "2026-09-18"}
    assert KLA.claim_key_for(wk, "wulx") == "KL:WULX:week:low:down:2026-09-18"
    yr = {"period": "year", "kind": "high", "direction": "up", "as_of": "2026-09-21"}
    assert KLA.claim_key_for(yr, "MP") == "KL:MP:year:high:up", "no as_of: the latch outlives the level"
    assert set(KLA.year_keys("MP")) == {"KL:MP:year:high:up", "KL:MP:year:high:down",
                                        "KL:MP:year:low:up", "KL:MP:year:low:down"}


# --------------------------------------------------------------------------
# delivery
# --------------------------------------------------------------------------
def _mon():
    fr = _week("2026-09-18")
    now = _at(2026, 9, 21, 16, 10)
    return fr, now, _snap(fr, now, close=99.8, low=99.5)


def test_transport_failure_releases_and_the_next_pass_sends():
    colls = _colls()
    fr, now, row = _mon()
    out = _run("WULX", fr, row, now, colls, sender=Sender({"sent": 0, "failed": 1, "total_targets": 1}))
    assert out["counts"]["pushed"] == 0 and colls["claim_coll"].docs == {}
    snd = Sender()
    out = _run("WULX", fr, row, now + timedelta(minutes=1), colls, sender=snd)
    assert out["counts"]["pushed"] == 1 and len(snd.sent) == 1


def test_a_raising_sender_releases():
    colls = _colls()
    fr, now, row = _mon()
    out = _run("WULX", fr, row, now, colls, sender=Sender(raises=True))
    assert out["counts"]["pushed"] == 0 and colls["claim_coll"].docs == {}


def test_nobody_targeted_is_terminal_claims_kept_and_counted_muted():
    colls = _colls()
    fr, now, row = _mon()
    out = _run("WULX", fr, row, now, colls, sender=Sender({"sent": 0, "failed": 0, "total_targets": 0}))
    assert out["counts"]["muted"] == 1 and out["counts"]["pushed"] == 0
    assert "KL:WULX:week:low:down:2026-09-18" in colls["claim_coll"].docs
    # turning the kind on later never replays it
    snd = Sender()
    out = _run("WULX", fr, row, now + timedelta(minutes=1), colls, sender=snd)
    assert snd.sent == [] and out["counts"]["claimed_elsewhere"] == 1


def test_a_second_pass_in_the_same_window_sends_nothing():
    colls = _colls()
    fr, now, row = _mon()
    snd = Sender()
    _run("WULX", fr, row, now, colls, sender=snd)
    out = _run("WULX", fr, row, now + timedelta(minutes=5), colls, sender=snd)
    assert len(snd.sent) == 1 and out["counts"]["claimed_elsewhere"] == 1 and out["counts"]["pushed"] == 0


def test_push_off_claims_nothing_and_sends_nothing():
    colls = _colls()
    fr, now, row = _mon()
    snd = Sender()
    out = _run("WULX", fr, row, now, colls, sender=snd, push=False)
    assert snd.sent == [] and colls["claim_coll"].writes == 0
    assert out["messages"], "the would-be message is still reported"


# --------------------------------------------------------------------------
# routing: singles for holdings only, then ONE digest
# --------------------------------------------------------------------------
def test_singles_only_for_held_names_capped_then_one_digest_with_more():
    colls = _colls()
    fr, now, _row = _mon()
    held = [f"H{i}" for i in range(5)]
    watch = [f"W{i}" for i in range(8)]
    syms = held + watch
    snd = Sender()
    out = KLA.run_pass(snapshot={s: _snap(fr, now, close=99.8, low=99.5) for s in syms}, now=now,
                       push=True, owner="o@x", scope={"symbols": syms, "held": held},
                       frames={s: fr for s in syms}, sender=snd, **colls)
    assert len(snd.sent) == ZE.MAX_SINGLES_PER_PASS + 1 and out["counts"]["pushed"] == len(snd.sent)
    singles, digest = snd.sent[:-1], snd.sent[-1]
    assert all(m["ticker"] in held for m in singles)
    assert all(m["kind"] == KLA.KIND == "key_level_alert" for m in snd.sent)
    lines = digest["body"].split("\n")
    rest = len(syms) - ZE.MAX_SINGLES_PER_PASS
    assert digest["title"].startswith("🔑 Key levels closed through — ")
    assert digest["title"].endswith(f" +{rest - 1} more")
    assert len(lines) == ZE.DIGEST_MAX + 2
    assert lines[ZE.DIGEST_MAX] == f"+{rest - ZE.DIGEST_MAX} more"
    assert lines[-1] == "Unmeasured — a close through a level, not a signal."
    assert digest["ticker"] is None and len(digest["tickers"]) == rest
    lead = digest["tickers"][0]
    assert digest["url"] == f"/chart-maps?tab=support&symbol={lead}" == digest["data"]["url"]
    # held overflow rides the digest (never dropped)
    assert set(held) - {m["ticker"] for m in singles} <= set(digest["tickers"])


def test_NEGATIVE_watchlist_only_names_never_get_a_single():
    colls = _colls()
    fr, now, row = _mon()
    snd = Sender()
    out = _run("MP", fr, row, now, colls, sender=snd, held=False)
    assert len(snd.sent) == 1 and snd.sent[0]["title"].startswith("🔑 Key levels closed through — MP")
    assert snd.sent[0]["ticker"] is None and out["counts"]["pushed"] == 1


# --------------------------------------------------------------------------
# exact push text
# --------------------------------------------------------------------------
def _m(period, kind, direction, price, as_of="2026-09-18", set_on=None, mid=None):
    label = KL.LABELS[(period, kind)]
    return {"id": mid or f"{period}_{kind}_{int(round(price * 100))}", "period": period, "kind": kind,
            "direction": direction, "price": price, "label": label, "name": KL.NAMES[label],
            "as_of": as_of, "set_on": set_on, "beyond_pct": None}


def test_single_exact_strings():
    pwl = _m("week", "low", "down", 14.80)
    msg = KLA.single_text("WULX", [pwl], close=14.52,
                          first_seen={"WULX|week_low_1480|down|through": "10:42"})
    assert msg["title"] == "🔑 WULX closed under prior-week low $14.80"
    assert msg["body"] == ("Close $14.52 (−1.9% vs the level) · first through 10:42 · your position · "
                           "level frozen at the Fri 09-18 close · Unmeasured: what happened, not a buy "
                           "or sell signal.")
    assert msg["url"] == "/chart-maps?tab=support&symbol=WULX" == msg["data"]["url"]
    assert msg["ticker"] == "WULX" and msg["kind"] == "key_level_alert"
    # no stamp -> no "first through"
    assert "first through" not in KLA.single_text("WULX", [pwl], close=14.52)["body"]
    yr = _m("year", "high", "up", 150.0, as_of="2026-09-21", set_on="2026-03-04")
    body = KLA.single_text("MP", [yr], close=151.0)["body"]
    assert "level: 52-week high, set Wed 03-04" in body and "frozen" not in body
    two = KLA.single_text("WULX", [_m("month", "low", "down", 14.10), pwl], close=13.9)
    assert two["title"] == "🔑 WULX closed under prior-week low $14.80 and prior-month low $14.10"
    back = KLA.single_text("WULX", [_m("week", "low", "up", 14.80)], close=14.9)
    assert back["title"] == "🔑 WULX closed back over prior-week low $14.80"


def test_digest_exact_strings():
    items = [("MP", [_m("month", "high", "up", 60.10)], 60.58),
             ("AAA", [_m("week", "low", "down", 10.0)], 9.9),
             ("BBB", [_m("week", "high", "down", 20.0)], 19.8)]
    msg = KLA.digest_text(items)
    assert msg["title"] == "🔑 Key levels closed through — MP over prior-month high +2 more"
    lines = msg["body"].split("\n")
    assert lines[0] == "MP closed over prior-month high $60.10 (+0.8%)"
    assert lines[1] == "AAA closed under prior-week low $10.00 (−1.0%)"
    assert lines[2] == "BBB closed back under prior-week high $20.00 (−1.0%)"
    assert lines[-1] == "Unmeasured — a close through a level, not a signal."
    assert KLA.digest_text(items[:1])["title"] == "🔑 Key levels closed through — MP over prior-month high"


def test_NEGATIVE_close_messages_never_say_bounce_premkt_or_afterhrs():
    fr, now, row = _mon()
    colls = _colls()
    snd = Sender()
    row["last_trade_ts_ms"] = int((now - timedelta(seconds=20)).timestamp() * 1e9)   # an AH print, ns
    _run("WULX", fr, row, now, colls, sender=snd)
    _run("MP", fr, row, now, colls, sender=snd, held=False)
    assert len(snd.sent) == 2
    for m in snd.sent:
        blob = (m["title"] + " " + m["body"]).lower()
        assert "unmeasured" in blob
        for banned in ("bounc", "pre-mkt", "after-hrs"):
            assert banned not in blob, (banned, m)


# --------------------------------------------------------------------------
# scope and prices
# --------------------------------------------------------------------------
def test_scope_is_holdings_union_signals_and_ONE_extra_snapshot_call(monkeypatch):
    import sys
    import types
    from daytrading import signal_lab as SL
    from sepa import prices
    monkeypatch.setattr(SL, "get_watchlist", lambda owner: ["MP", "NVDA"] if owner == "o@x" else [])
    # portfolio.store stand-in: the real package's __init__ loads its FastAPI
    # router (py3.10 annotations) — the pass only needs list_holdings
    pkg = types.ModuleType("portfolio")
    ps = types.ModuleType("portfolio.store")
    ps.list_holdings = lambda owner: [{"ticker": "WULX"}, {"ticker": "MP"}] if owner == "o@x" else []
    pkg.store = ps
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.store", ps)
    fr, now, row = _mon()
    calls = []

    def fake_bulk(syms):
        calls.append(list(syms))
        return {s: dict(row) for s in syms}
    monkeypatch.setattr(prices, "bulk_snapshot", fake_bulk)
    snd = Sender()
    out = KLA.run_pass(snapshot={"MP": row}, now=now, push=True, owner="o@x",
                       frames={"MP": fr, "NVDA": fr, "WULX": fr}, sender=snd, **_colls())
    assert out["counts"]["scope"] == 3
    assert calls == [["NVDA", "WULX"]], "names missing from zone_edge's snapshot: ONE call"
    singles = [m for m in snd.sent if m.get("ticker")]
    assert {m["ticker"] for m in singles} == {"WULX", "MP"}, "held = the portfolio"
    # nothing missing -> NO extra call
    calls.clear()
    KLA.run_pass(snapshot={s: row for s in ("MP", "NVDA", "WULX")}, now=now, push=True, owner="o@x",
                 frames={"MP": fr, "NVDA": fr, "WULX": fr}, sender=Sender(), **_colls())
    assert calls == []


def test_guards_count_and_never_push_on_a_stale_or_missing_frame():
    colls = _colls()
    fr, now, row = _mon()
    stale = _week("2026-09-15")
    bad = dict(row, prev_day_close=103.0, close=99.8)          # cache close 102 vs official 103
    scope = {"symbols": ["OK", "NOFRAME", "STALE", "BAD", "NOSNAP"], "held": []}
    snd = Sender()
    out = KLA.run_pass(snapshot={"OK": row, "NOFRAME": row, "STALE": row, "BAD": bad}, now=now,
                       push=True, owner="o@x", scope=scope,
                       frames={"OK": fr, "STALE": stale, "BAD": fr, "NOSNAP": fr},
                       sender=snd, **colls)
    c = out["counts"]
    assert c["scope"] == 5 and c["no_frame"] == 1 and c["stale_frame"] == 2 and c["unverified"] == 1
    assert [m["tickers"] for m in snd.sent] == [["OK"]], "only the verified name pushes"


def test_empty_scope_records_a_reason_and_reads_nothing(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "bulk_snapshot", lambda s: pytest.fail("no names, no call"))
    colls = _colls()
    out = KLA.run_pass(snapshot=None, now=_at(2026, 9, 21, 16, 10), push=True, owner="o@x",
                       scope={"symbols": [], "held": []}, frames={}, sender=Sender(), **colls)
    assert out["counts"]["scope"] == 0 and "no names in scope" in out["reason"]
    assert colls["pass_coll"].docs["key_level_alert"]["counts"]["scope"] == 0


# --------------------------------------------------------------------------
# dry run + first-seen doc
# --------------------------------------------------------------------------
def test_dry_run_writes_nothing_anywhere():
    colls = _colls()
    fr, now, row = _mon()
    snd = Sender()
    out = _run("WULX", fr, row, now, colls, sender=snd, dry_run=True)
    assert snd.sent == []
    assert all(c.writes == 0 for c in colls.values()), {k: dict(c.calls) for k, c in colls.items()}
    assert out["keys"] == ["KL:WULX:week:low:down:2026-09-18"] and len(out["messages"]) == 1
    out = _run("WULX", fr, _snap(fr, _at(2026, 9, 21, 10, 42), close=99.7, px=99.7),
               _at(2026, 9, 21, 10, 42), colls, dry_run=True)
    assert out["counts"]["broken"] == 1 and all(c.writes == 0 for c in colls.values())


def test_first_seen_doc_is_replaced_whole_so_a_dotted_symbol_is_one_key():
    colls = _colls()
    fr = _week("2026-09-18")
    now = _at(2026, 9, 21, 11, 5)
    _run("BRK.B", fr, _snap(fr, now, close=99.7, px=99.7), now, colls)
    fc = colls["first_coll"]
    assert fc.calls["replace_one"] == 1 and fc.calls["update_one"] == 0
    doc = fc.docs["2026-09-21"]
    assert doc["first"] == {"BRK.B|week_low_10000|down|through": "11:05"}
    assert KL.read_first_seen("2026-09-21", coll=fc) == doc["first"], "the engine reads what we wrote"


def test_reversal_is_stamped_once_and_the_single_carries_the_first_through_time():
    colls = _colls()
    fr = _week("2026-09-18")
    t1, t2 = _at(2026, 9, 21, 10, 42), _at(2026, 9, 21, 11, 30)
    _run("WULX", fr, _snap(fr, t1, close=99.7, low=99.6, px=99.7), t1, colls)
    _run("WULX", fr, _snap(fr, t2, close=100.4, low=99.6, px=100.4), t2, colls)
    first = colls["first_coll"].docs["2026-09-21"]["first"]
    assert first == {"WULX|week_low_10000|down|through": "10:42",
                     "WULX|week_low_10000|down|reversal": "11:30"}
    t3 = _at(2026, 9, 21, 16, 10)
    snd = Sender()
    _run("WULX", fr, _snap(fr, t3, close=99.8, low=99.5), t3, colls, sender=snd)
    assert "first through 10:42" in snd.sent[0]["body"]


def test_outside_the_state_window_records_the_window_and_stamps_nothing():
    colls = _colls()
    fr = _week("2026-09-21", {"2026-09-21": (102.0, 99.5, 99.8)})
    now = _at(2026, 9, 21, 20, 0)                              # the roll: next session, phase None
    out = _run("WULX", fr, _snap(fr, now, close=99.8), now, colls)
    assert out["phase"] is None and out["session"] == "2026-09-22"
    assert colls["first_coll"].writes == 0 and out["counts"]["pushed"] == 0


# --------------------------------------------------------------------------
# zone_edge hook
# --------------------------------------------------------------------------
class ZColl(FakeColl):
    def insert_many(self, docs):
        self.calls["insert_many"] += 1

    def delete_many(self, q):
        self.calls["delete_many"] += 1
        return SimpleNamespace(deleted_count=0)


def _zcolls():
    return {"coll_break": ZColl(), "coll_demand": ZColl(), "latest_coll": ZColl(), "track_coll": ZColl()}


ZNOW = datetime(2026, 9, 3, 10, 0, tzinfo=ET)


class Spy:
    def __init__(self, raises=False):
        self.calls, self.raises = [], raises

    def __call__(self, **kw):
        self.calls.append(kw)
        if self.raises:
            raise RuntimeError("key pass blew up")
        return {"ran": True, "counts": {"pushed": 7}}


def test_store_empty_exit_calls_the_hook_with_no_snapshot():
    spy = Spy()
    out = ZE.check_once(store={}, now=ZNOW, key_pass=spy, **_zcolls())
    assert len(spy.calls) == 1 and spy.calls[0]["snapshot"] is None
    assert spy.calls[0]["now"] == ZNOW and spy.calls[0]["push"] is True and spy.calls[0]["dry_run"] is False
    assert out["key_levels"] == {"ran": True, "counts": {"pushed": 7}} and out["pushed"] == 0


def test_snapshot_failure_exit_calls_the_hook_with_an_EMPTY_snapshot(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "bulk_snapshot", lambda syms: (_ for _ in ()).throw(RuntimeError("massive 500")))
    spy = Spy()
    out = ZE.check_once(store={"AAA": {"bands": []}}, now=ZNOW, key_pass=spy, **_zcolls())
    assert out["ran"] is False and "snapshot failed" in out["reason"]
    assert len(spy.calls) == 1 and spy.calls[0]["snapshot"] == {}
    assert "key_levels" in out


def _normal(key_pass, colls):
    snap = {"AAA": {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
                    "last_trade_price": 100.0,
                    "last_trade_ts_ms": int((ZNOW - timedelta(seconds=30)).timestamp() * 1000),
                    "prev_day_close": 100.0, "change_pct": 0.0}}
    store = {"AAA": {"symbol": "AAA", "bands": [], "prev_close": 100.0}}
    return ZE.check_once(store=store, snapshot=snap, caps={"AAA": 5e9}, names={}, owner="o@x",
                         now=ZNOW, key_pass=key_pass, **colls)


def test_normal_exit_calls_the_hook_after_the_latest_write():
    spy, colls = Spy(), _zcolls()
    out = _normal(spy, colls)
    assert len(spy.calls) == 1 and "AAA" in spy.calls[0]["snapshot"]
    assert out["key_levels"]["counts"] == {"pushed": 7}
    assert "latest" in colls["latest_coll"].docs


def test_NEGATIVE_a_raising_hook_changes_nothing_in_the_zone_edge_pass():
    ca, cb = _zcolls(), _zcolls()
    ok = _normal(False, ca)
    bad = _normal(Spy(raises=True), cb)
    assert set(ok) == set(bad) and ok["pushed"] == bad["pushed"]
    assert bad["key_levels"]["ran"] is False and "blew up" in bad["key_levels"]["error"]
    la, lb = ca["latest_coll"].docs["latest"], cb["latest_coll"].docs["latest"]
    assert set(la) == set(lb) and la["counts"] == lb["counts"]
    for k in ("breaking", "near_demand", "candidates", "priced", "stale_print"):
        assert ok[k] == bad[k], k
    assert AS.counts_from_result(ok) == AS.counts_from_result(bad)
    assert "key_levels" not in AS.counts_from_result(bad)


def test_NEGATIVE_an_injected_store_never_runs_the_real_pass(monkeypatch):
    spy = Spy()
    monkeypatch.setattr(KLA, "run_pass", spy)
    ZE.check_once(store={}, now=ZNOW, **_zcolls())
    _normal(None, _zcolls())
    assert spy.calls == [], "store injected + key_pass None: no network in tests"
    out = ZE.check_once(store={}, now=ZNOW, key_pass=False, **_zcolls())
    assert spy.calls == [] and out["key_levels"]["ran"] is False


def test_the_cron_path_runs_the_real_pass(monkeypatch):
    from supply_demand import zone_store
    spy = Spy()
    monkeypatch.setattr(KLA, "run_pass", spy)
    monkeypatch.setattr(zone_store, "load", lambda *a, **k: {})
    ZE.check_once(now=ZNOW, **_zcolls())
    assert len(spy.calls) == 1 and spy.calls[0]["snapshot"] is None


def test_outside_the_pass_window_the_hook_never_runs():
    spy = Spy()
    out = ZE.check_once(store={}, now=datetime(2026, 9, 3, 3, 0, tzinfo=ET), key_pass=spy, **_zcolls())
    assert out["ran"] is False and spy.calls == []
    out = ZE.check_once(store={}, now=datetime(2026, 9, 7, 10, 0, tzinfo=ET), key_pass=spy, **_zcolls())
    assert out["ran"] is False and spy.calls == [], "Labor Day: in_session refuses"


def test_dry_zone_edge_pass_is_a_dry_key_pass():
    spy = Spy()
    ZE.check_once(store={}, now=ZNOW, key_pass=spy, track=False, **_zcolls())
    assert spy.calls[0]["dry_run"] is True


def test_zone_edge_imports_key_level_alerts_only_lazily():
    src = (BACKEND / "supply_demand/zone_edge.py").read_text()
    head = src.split("def _now_et")[0]
    assert "key_level" not in head, "no module-level import"
    assert "import key_levels" not in src and "key_levels as" not in src, "the engine only via the alerts module"
    assert "from supply_demand import key_level_alerts" in inspect.getsource(ZE._run_key_pass)
    assert "_run_key_pass(" in inspect.getsource(ZE.check_once)
    assert inspect.getsource(ZE.check_once).count("_run_key_pass(") == 3, "all three exits"


# --------------------------------------------------------------------------
# prefs / gate / status / rules
# --------------------------------------------------------------------------
def test_pref_is_ON_for_the_owner_and_OFF_for_everyone_else():
    """Ajay 2026-09-25: "On: week + month + 52-week" / "Holdings + Signals
    list" / "No, close only". ON for his devices via OWNER_KEEP_SET; OFF in
    default_prefs, so nobody else starts receiving it."""
    from push import subs
    assert "key_level_alert" in subs.OWNER_KEEP_SET
    assert subs.owner_prefs()["key_level_alert"] is True
    assert subs.prefs_for(subs._owner_email())["key_level_alert"] is True
    assert subs.default_prefs()["key_level_alert"] is False
    assert subs.prefs_for("someone-else@example.com")["key_level_alert"] is False
    assert "key_level_alert" not in subs.DISABLED_ALERT_KINDS


def test_closed_day_gate_drops_the_kind_on_labor_day(monkeypatch):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    assert "key_level_alert" in gate.MARKET_ALERT_KINDS and "key_level_alert" not in gate.PERSONAL_KINDS
    assert gate.should_drop_kind("key_level_alert", datetime(2026, 9, 7, 16, 10, tzinfo=ET)) == "holiday 2026-09-07"
    assert gate.should_drop_kind("key_level_alert", datetime(2026, 9, 8, 16, 10, tzinfo=ET)) is None


def test_alert_status_registers_the_pass_with_zone_edges_cadence():
    assert "key_level_alert" in AS.PASS_KINDS
    assert AS.CADENCE_SEC["key_level_alert"] == AS.CADENCE_SEC[AS.ZONE_EDGE_KIND]
    assert "key_levels" in AS._NOT_COUNTS
    p = AS.status_payload(pass_coll=FakeColl(), latest_coll=FakeColl(), now=ZNOW)
    assert p["passes"]["key_level_alert"]["as_of"] is None, "a missing pass doc = no pass yet"


def test_rules_panel_section_is_built_from_the_constants():
    from supply_demand import rules_info as RI
    sec = RI.sections()["key_levels"]
    assert "key_levels" in RI.SECTION_KEYS and sec["emoji"] == KL.MARK
    blob = " ".join([sec["title"]] + sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])
    assert KL.rule_text() in sec["picks"]
    assert sec["stops"] == ["No stop, no target, no size: a drawing and a state."]
    assert "UNMEASURED" in blob and "bounc" not in blob.lower()
    assert "(ON by default)" in blob and "ships OFF by default" not in blob
    assert "OFF unless" not in blob, "owner_prefs() is the default, never his stored toggle"
    assert "%g%%" % KL.PIERCE_PCT in blob and "16:05–16:30" in blob and "13:05–13:30" in blob
    assert ("at most %d" % ZE.MAX_SINGLES_PER_PASS) in blob and ("up to %d names" % ZE.DIGEST_MAX) in blob


def test_rules_panel_moves_when_a_constant_moves(monkeypatch):
    from push import subs
    from supply_demand import rules_info as RI
    monkeypatch.setattr(KLA, "CLOSE_PUSH_WINDOW_MIN", 40)
    monkeypatch.setattr(ZE, "DIGEST_MAX", 9)
    monkeypatch.setattr(subs, "OWNER_KEEP_SET", subs.OWNER_KEEP_SET | {"key_level_alert"})
    blob = " ".join(RI.sections()["key_levels"]["alerts"])
    assert "16:05–16:45" in blob and "up to 9 names" in blob
    assert "(ON by default)" in blob and "OFF by default" not in blob, "the ON/OFF word is read at request time"


def test_NEGATIVE_rules_panel_types_no_number_of_its_own():
    from supply_demand import rules_info as RI
    src = inspect.getsource(RI._key_levels_section)
    literals = re.findall(r'"([^"\\]*)"', src)
    assert any("Key levels" in s for s in literals), "the block was not located"
    stripped = [re.sub(r"%[0-9]*[sdg]", "", s) for s in literals]
    offenders = [s for s in stripped if any(ch.isdigit() for ch in s)]
    assert offenders == [], offenders


def test_key_level_alerts_is_display_only_nothing_trades_on_it():
    hits = set()
    pat = re.compile(r"^\s*(from\s+\S+\s+import\s+[^\n]*\bkey_level_alerts\b"
                     r"|from\s+\S*key_level_alerts\s+import|import\s+\S*key_level_alerts)", re.M)
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv/", "tests/")) or "/site-packages/" in rel:
            continue
        try:
            if pat.search(p.read_text(encoding="utf-8")):
                hits.add(rel)
        except (OSError, UnicodeDecodeError):
            continue
    assert hits == {"supply_demand/zone_edge.py", "supply_demand/rules_info.py"}, sorted(hits)
    assert not any(h.startswith("trading/") for h in hits)


def test_docs_exist_and_say_off_and_unmeasured():
    doc = (ROOT / "docs/notifications/key_level_alert.md").read_text()
    for needle in ("key_level_alert", "OFF", "UNMEASURED", "OWNER_KEEP_SET", "probe",
                   "I wanna know when key levels are broken", "key_level_alert_state"):
        assert needle in doc, needle
    page = (ROOT / "docs/supply_demand/alerts_page.md").read_text()
    assert "key_level_alert" in page and "claimed_elsewhere" in page
