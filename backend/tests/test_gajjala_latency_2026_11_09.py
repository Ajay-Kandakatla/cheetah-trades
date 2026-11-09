"""⏱ Speed — the 🚩 A+ latency ledger (GG LIVE P4, BUILD SPEC rev 2 §3.6 / WP-E, 2026-11-09).

Ajay 2026-11-09: "I would like the autopilot to be continously monitored or live tracked … where there is a low latency
monitoring on the prices action changes please?" — chart_maps/gajjala/latency.py measures every step from the 5-minute
entry bar's close to the ring and the lane's order / fill.

Locks: §1.4's arithmetic (HUHU close 14:45:00 ET, ring 14:46:10.16 → 70.2 s, order 14:47:02 → 122 s) and the five-step
"before" row (Read 61.0 · Rang 70.6 · Lane saw 122.0 · Ordered 124.0 · Filled 127.0 p50); the C4 trap (naive ET, never
UTC: +14,400 s) — NEG; a 15m row is not shifted — NEG; SHADOW / #state / other-variant rows excluded — NEG; unfilled /
skipped → "—" but counted in Read / Rang; no order_source → "tick"; numpy linear percentile on 5 values (NEG nearest-rank);
the GG_LIVE_FROM split; the seeded bootstrap (deterministic; n < 5 → no interval); stream vs 1-minute — the five tick
outcomes, the entry delta sign, odd-lot-only (NEG a trigger_lot row), no stream rows → no block (NEG); bar finality
counts + split (NEG no rows → no line); the endpoint (admin 200, NEG non-admin 403, empty span → the served words); the
script prints the endpoint's numbers.

Hermetic: a fake attribute-style Mongo behind exit_engine._db (the lane's own IO seam); no network, no broker.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE
import trading.gajjala_entry as GE
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import latency as LT

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DAY = "2026-10-19"                                     # a Monday, EDT (UTC-4)
NOW = datetime(2026, 10, 19, 20, 0, tzinfo=ET)


# ── fakes ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _match(doc, q):
    for k, v in (q or {}).items():
        x = doc.get(k)
        if isinstance(v, dict):
            if "$in" in v and x not in v["$in"]:
                return False
            if "$gte" in v and not (x is not None and x >= v["$gte"]):
                return False
            if "$lt" in v and not (x is not None and x < v["$lt"]):
                return False
        elif x != v:
            return False
    return True


class Coll:
    def __init__(self, rows=()):
        self.rows = [dict(r) for r in rows]
        self.queries = []

    def find(self, q=None, *a, **k):
        self.queries.append(q)
        return [dict(r) for r in self.rows if _match(r, q)]


class DB:
    def __init__(self, alerts=(), lane=(), stream=(), final=()):
        self.gajjala_alerts = Coll(alerts)
        self.gajjala_lane = Coll(lane)
        self.gajjala_lane_stream = Coll(stream)
        self.gajjala_bar_final = Coll(final)


@pytest.fixture
def mongo(monkeypatch):
    def put(**kw):
        db = DB(**kw)
        monkeypatch.setattr(EE, "_db", lambda: db)
        return db
    return put


def _iso(dt):
    return dt.astimezone(UTC).isoformat()


def _close(day, hhmm):
    return datetime.fromisoformat(f"{day} {hhmm}").replace(tzinfo=ET)


def alert(sym, day=DAY, bar="14:45", read=61.0, ring=70.6, setup="vr", frame="5m", state="pushed", _id=None):
    c = _close(day, bar)
    return {"_id": _id or f"GG:{day}|{sym}|{setup}", "date": day, "symbol": sym, "setup": setup, "frame": frame,
            "entry_bar_t": f"{day} {bar}", "state": state, "trigger": 2.0, "stop": 1.8,
            "at": _iso(c + timedelta(seconds=read)) if read is not None else None,
            "claimed_at": _iso(c + timedelta(seconds=ring)) if ring is not None else None}


def lane(a, seen=None, order=None, fill=None, state="closed", **kw):
    c = GE._parse_et(a["entry_bar_t"])
    d = {"_id": a["_id"], "date": a["date"], "symbol": a["symbol"], "state": state, "trigger": 2.0, "stop": 1.8,
         "first_seen": _iso(c + timedelta(seconds=seen)) if seen is not None else None,
         "ordered_at": _iso(c + timedelta(seconds=order)) if order is not None else None,
         "fill_t": _iso(c + timedelta(seconds=fill)) if fill is not None else None, "last": None}
    d.update(kw)
    return d


def srow(a, event, print_s, recv_s=None, px=2.0, odd=False, lag_ms=120):
    c = GE._parse_et(a["entry_bar_t"])
    return {"_id": f"{a['_id']}|{event}", "doc_id": a["_id"], "symbol": a["symbol"], "event": event,
            "print_px": px, "print_size": 50 if odd else 300, "conditions": [37] if odd else [], "odd_lot": odd,
            "print_t": _iso(c + timedelta(seconds=print_s)),
            "recv_t": _iso(c + timedelta(seconds=recv_s if recv_s is not None else print_s + 0.1)), "lag_ms": lag_ms,
            "mode": "shadow"}


def summary_of(p, side):
    return next(s for s in p["summary"] if s["side"] == side)


# ── §1.4 arithmetic + the acceptance row ─────────────────────────────────────────────────────────────────────────
def test_huhu_arithmetic_reproduces_the_probe(mongo):
    a = alert("HUHU", bar="14:45", read=61.0, ring=70.16)
    a["claimed_at"] = "2026-10-19T18:46:10.160000+00:00"        # 14:46:10.16 ET (EDT)
    d = lane(a, seen=121.0, order=None, fill=None, state="closed",
             ordered_at="2026-10-19T18:47:02+00:00", fill_t="2026-10-19T18:47:05+00:00")
    mongo(alerts=[a], lane=[d])
    p = LT.payload("all", now=NOW, live_from=None)
    r = p["rows"][0]
    assert r["close_et"] == "14:45:00"
    assert r["ring"] == 70.2 and r["order"] == 122.0 and r["fill"] == 125.0 and r["broker"] == 3.0
    assert r["source"] == "tick"
    assert [c["text"] for c in r["cells"]] == ["61.0", "70.2", "121.0", "122.0", "125.0"]


def _baseline_alerts():
    vals = (("AAA", "10:00", 60.6, 65.4, 121.0, 122.0, 123.0),
            ("BBB", "11:00", 61.0, 70.6, 122.0, 124.0, 127.0),
            ("CCC", "12:00", 176.1, 203.5, 2480.0, 3603.0, 3605.0))
    al, ln = [], []
    for sym, bar, rd, rg, se, od, fl in vals:
        a = alert(sym, bar=bar, read=rd, ring=rg)
        al.append(a)
        ln.append(lane(a, seen=se, order=od, fill=fl))
    return al, ln


def test_acceptance_before_row_is_the_baseline_five_steps(mongo):
    al, ln = _baseline_alerts()
    later = alert("ZZZ", day="2026-11-10", bar="10:00", read=31.0, ring=40.0)
    mongo(alerts=al + [later], lane=ln)
    p = LT.payload("all", now=datetime(2026, 11, 10, 20, 0, tzinfo=ET), live_from="2026-11-10")
    assert [c["label"] for c in p["columns"]] == ["Read", "Rang", "Lane saw", "Ordered", "Filled"]
    b = summary_of(p, "before")
    assert b["label"] == "before 2026-11-10" and b["n"] == 3
    assert [b["steps"][k]["p50"] for k in ("read", "ring", "seen", "order", "fill")] == [61.0, 70.6, 122.0, 124.0, 127.0]
    assert b["steps"]["seen"]["max"] == 2480.0 and b["steps"]["ring"]["min"] == 65.4
    assert b["cells"][1]["text"] == "70.6 · 176.9 (3)" and b["cells"][1]["line"] == "Rang: 70.6 · 176.9 (3)"
    s = summary_of(p, "since")
    assert s["label"] == "since 2026-11-10" and s["n"] == 1 and s["steps"]["ring"]["p50"] == 40.0
    assert s["cells"][2]["text"] == LT.DASH                     # no lane doc since → "—", n 0
    assert p["footnote"] == "From the alert and lane records: p50 · p90 (n). A timing, not a result."
    assert p["title"] == "⏱ Speed — seconds after the 5-minute bar closed"


# ── C4: the clock trap (NEGATIVE) ────────────────────────────────────────────────────────────────────────────────
def test_neg_entry_bar_t_is_naive_et_never_utc(mongo):
    a = alert("NAIV", bar="18:10", read=60.0, ring=70.0)
    assert a["entry_bar_t"] == "2026-10-19 18:10"
    mongo(alerts=[a])
    r = LT.payload("all", now=NOW, live_from=None)["rows"][0]
    assert r["ring"] == 70.0
    wrong = (GE._parse(a["claimed_at"]) - GE._parse(a["entry_bar_t"])).total_seconds()   # the naive-as-UTC read
    assert wrong == 70.0 + 14_400 and wrong >= 14_400
    assert LT.close_of(a["entry_bar_t"]) == _close(DAY, "18:10")


def test_neg_a_15m_frame_row_is_not_shifted(mongo):
    a5 = alert("FIVE", bar="13:00", ring=70.0, frame="5m")
    a15 = alert("FIFT", bar="13:00", ring=70.0, frame="15m")
    mongo(alerts=[a5, a15])
    rows = {r["symbol"]: r for r in LT.payload("all", now=NOW, live_from=None)["rows"]}
    assert rows["FIFT"]["ring"] == rows["FIVE"]["ring"] == 70.0      # never + 15 × 60
    assert rows["FIFT"]["close_et"] == "13:00:00"


def test_neg_shadow_state_and_other_variant_rows_are_excluded(mongo):
    live = alert("LIVE")
    shadow = dict(alert("SHAD"), _id=f"SHADOW:GG:{DAY}|SHAD|vr", state="pushed")
    refusal = dict(alert("REFU"), _id=f"GG:{DAY}|REFU|vr#stale", state="pushed")
    gg1 = dict(alert("ONEM"), _id=f"GG1:{DAY}|ONEM|vr")
    gga = dict(alert("AUDT"), _id=f"GGA:{DAY}|AUDT|vr")
    claimed = alert("CLMD", state="claimed")
    failed = alert("FAIL", state="failed")
    mongo(alerts=[live, shadow, refusal, gg1, gga, claimed, failed])
    p = LT.payload("all", now=NOW, live_from=None)
    assert [r["symbol"] for r in p["rows"]] == ["LIVE"] and p["n_alerts"] == 1
    assert LT.is_live_row(live) and not any(LT.is_live_row(x) for x in (shadow, refusal, gg1, gga, claimed, failed))


def test_unfilled_and_skipped_show_dash_but_count_in_read_and_rang(mongo):
    a1, a2, a3 = alert("UNF", bar="10:00"), alert("SKP", bar="10:05"), alert("FIL", bar="10:10")
    l1 = lane(a1, seen=121, order=122, fill=None, state="unfilled", skip_kind=None)   # an order the broker cancelled
    l2 = lane(a2, seen=121, state="skipped", skip_kind="missed")
    l3 = lane(a3, seen=121, order=122, fill=125)
    mongo(alerts=[a1, a2, a3], lane=[l1, l2, l3])
    p = LT.payload("all", now=NOW, live_from=None)
    rows = {r["symbol"]: r for r in p["rows"]}
    for s in ("UNF", "SKP"):
        assert rows[s]["order"] is None and rows[s]["fill"] is None and rows[s]["broker"] is None
        assert [c["text"] for c in rows[s]["cells"]][3:] == [LT.DASH, LT.DASH]
        assert rows[s]["source"] is None
    st = summary_of(p, "all")["steps"]
    assert st["read"]["n"] == 3 and st["ring"]["n"] == 3 and st["seen"]["n"] == 3
    assert st["order"]["n"] == 1 and st["fill"]["n"] == 1


def test_no_order_source_reads_tick_and_a_stream_source_is_kept(mongo):
    a1, a2 = alert("TICK", bar="10:00"), alert("STRM", bar="10:05")
    mongo(alerts=[a1, a2], lane=[lane(a1, seen=121, order=122, fill=125),
                                 lane(a2, seen=61, order=62, fill=64, order_source="stream", enter_ms=410)])
    rows = {r["symbol"]: r for r in LT.payload("all", now=NOW, live_from=None)["rows"]}
    assert rows["TICK"]["source"] == "tick" and rows["STRM"]["source"] == "stream"
    assert rows["STRM"]["enter_ms"] == 410


def test_rows_order_close_descending_then_symbol(mongo):
    mongo(alerts=[alert("BBB", bar="10:00"), alert("AAA", bar="11:00"), alert("CCC", bar="11:00"),
                  alert("DDD", day="2026-10-20", bar="09:50")])
    rows = LT.payload("all", now=NOW, live_from=None)["rows"]
    assert [r["symbol"] for r in rows] == ["DDD", "AAA", "CCC", "BBB"]


# ── statistics ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_percentile_is_numpy_linear_on_five_values():
    xs = [10.0, 1.0, 4.0, 2.0, 3.0]
    assert LT.pct(xs, 50) == 3.0
    assert LT.pct(xs, 90) == pytest.approx(7.6)                 # 4 + 0.6 × (10 − 4)
    assert LT.pct(xs, 90) == float(np.percentile(xs, 90))
    assert LT.pct(xs, 90) != 10.0                               # NEG: nearest-rank would read 10
    assert LT.step_stats(xs) == {"n": 5, "p50": 3.0, "p90": 7.6, "min": 1.0, "max": 10.0}
    assert LT.pct([], 50) is None and LT.step_stats([None])["n"] == 0


def test_split_at_live_from_and_no_split_without_it(mongo, monkeypatch):
    monkeypatch.setattr(LT, "GG_LIVE_FROM", None)               # the no-split path, explicitly
    al, ln = _baseline_alerts()
    later = alert("ZZZ", day="2026-10-20", bar="10:00")
    mongo(alerts=al + [later], lane=ln)
    p = LT.payload("all", now=NOW, live_from="2026-10-20")
    assert [s["side"] for s in p["summary"]] == ["before", "since"]
    assert [s["n"] for s in p["summary"]] == [3, 1]
    q = LT.payload("all", now=NOW, live_from=None)
    assert [s["side"] for s in q["summary"]] == ["all"] and q["summary"][0]["label"] == "All" and q["ci"] == []
    r = LT.payload("all", now=NOW)                              # the constant (patched None) → no split
    assert r["live_from"] is None and [s["side"] for s in r["summary"]] == ["all"]


def test_the_shipped_constant_splits_before_and_since_at_its_date(mongo, monkeypatch):
    assert LT.GG_LIVE_FROM == "2026-11-10"                      # MINE: the first full session after the 11-09 deploy
    pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    eve = alert("EVE", day="2026-11-09", bar="15:00", read=61.0, ring=70.6)
    day1 = alert("DAY", day="2026-11-10", bar="10:00", read=31.0, ring=40.0)
    mongo(alerts=[eve, day1])
    monkeypatch.setattr(GE, "_now_et", lambda: datetime(2026, 11, 10, 20, 0, tzinfo=ET))
    body = json.loads(asyncio.run(TA.trading_gajjala_latency(span="all", email=auth.HOUSE_OWNER_EMAIL)).body)
    assert body["live_from"] == "2026-11-10"
    assert [(s["side"], s["label"], s["n"]) for s in body["summary"]] == [
        ("before", "before 2026-11-10", 1), ("since", "since 2026-11-10", 1)]
    assert summary_of(body, "before")["steps"]["ring"]["p50"] == 70.6       # 2026-11-09 → before
    assert summary_of(body, "since")["steps"]["ring"]["p50"] == 40.0        # 2026-11-10 → since
    assert [c["key"] for c in body["ci"]] == ["read", "ring", "seen", "order", "fill"]
    assert all(c["lo"] is None for c in body["ci"])             # n 1 a side → no interval


@pytest.mark.parametrize("bad", ["junk", "2026-13-40", "", 20261110, ["2026-11-10"]])
def test_neg_an_invalid_constant_is_no_split_never_a_raise(mongo, monkeypatch, bad):
    monkeypatch.setattr(LT, "GG_LIVE_FROM", bad)
    mongo(alerts=[alert("EVE", day="2026-11-09"), alert("DAY", day="2026-11-10")])
    p = LT.payload("all", now=NOW)
    assert p["live_from"] is None and [s["side"] for s in p["summary"]] == ["all"] and p["ci"] == []
    assert p["summary"][0]["n"] == 2


def test_bootstrap_is_deterministic_and_needs_five_a_side():
    a = [60.0, 61.0, 62.0, 63.0, 64.0, 70.0]
    b = [30.0, 31.0, 32.0, 33.0, 40.0]
    c1, c2 = LT.boot_ci(a, b), LT.boot_ci(a, b)
    assert c1 == c2 and c1["diff"] == -30.5 and c1["lo"] <= c1["diff"] <= c1["hi"]
    assert LT.boot_ci(a, b[:4]) is None and LT.boot_ci(a[:4], b) is None      # NEG: n < 5 on a side


def test_ci_words_with_and_without_an_interval(mongo):
    before = [alert(f"B{i}", bar=f"10:{i * 5:02d}", read=60.0 + i, ring=70.0 + i) for i in range(5)]
    since = [alert(f"S{i}", day="2026-10-20", bar=f"10:{i * 5:02d}", read=30.0 + i, ring=40.0 + i) for i in range(5)]
    mongo(alerts=before + since)
    p = LT.payload("all", now=NOW, live_from="2026-10-20")
    ci = {c["key"]: c for c in p["ci"]}
    assert ci["ring"]["diff"] == -30.0 and ci["ring"]["lo"] is not None
    assert ci["ring"]["text"].startswith("Rang: p50 -30.0 s since 2026-10-20 (95% interval ")
    assert ci["ring"]["text"].endswith("n 5 before · 5 since)")
    assert ci["order"]["lo"] is None and ci["order"]["text"] == \
        "Ordered: fewer than 5 on a side — no interval (n 0 before · 0 since)"
    assert p == LT.payload("all", now=NOW, live_from="2026-10-20")   # seeded: the same served block twice


# ── stream vs 1-minute check ─────────────────────────────────────────────────────────────────────────────────────
def _check_fixture():
    a = {k: alert(k, bar=bar) for k, bar in (("TRG", "10:00"), ("STP", "10:05"), ("EXP", "10:10"), ("MIS", "10:15"),
                                              ("OTH", "10:20"), ("WAI", "10:25"), ("NOS", "10:30"))}
    ln = [lane(a["TRG"], seen=121, order=122, fill=125, fill_px=2.05),
          lane(a["STP"], seen=121, state="unfilled", skip_kind="never_triggered", last=1.79),
          lane(a["EXP"], seen=121, state="unfilled", skip_kind="never_triggered"),
          lane(a["MIS"], seen=121, state="skipped", skip_kind="missed", last=2.30),
          lane(a["OTH"], seen=121, state="skipped", skip_kind="cap_open", last=2.01),
          lane(a["WAI"], seen=121, state="waiting"),
          lane(a["NOS"], seen=121, order=122, fill=125, fill_px=2.0)]
    st = [srow(a["TRG"], "trigger", 90, px=2.0), srow(a["TRG"], "trigger_lot", 90, px=2.0),
          srow(a["TRG"], "seen", 60),
          srow(a["STP"], "stop", 200, px=1.79),
          srow(a["EXP"], "seen", 60),                         # none
          srow(a["MIS"], "trigger", 95, px=2.0, odd=True),      # odd-lot only (no trigger_lot row)
          srow(a["OTH"], "stop", 300, px=1.8), srow(a["OTH"], "trigger", 100, px=2.0, odd=True),
          srow(a["OTH"], "trigger_lot", 110, px=2.0),
          srow(a["WAI"], "trigger", 90)]
    return a, ln, st


def test_stream_vs_minute_five_tick_outcomes_and_pair_order(mongo):
    a, ln, st = _check_fixture()
    mongo(alerts=list(a.values()), lane=ln, stream=st)
    chk = LT.payload("all", now=NOW, live_from=None)["check"]
    got = [(x["stream"], x["tick"], x["agree"], x["n"]) for x in chk["pairs"]]
    assert got == [("trigger", "ordered", True, 1), ("stop", "never_triggered", True, 1), ("none", "expired", True, 1),
                   ("trigger", "missed", False, 1), ("trigger", "other_skip", False, 1)]
    assert chk["same"] == 3 and chk["different"] == 2 and chk["n"] == 5     # WAI (still waiting) and NOS (no rows) out
    assert chk["title"] == "Stream vs 1-minute check — same outcome 3 · different 2"
    assert chk["pairs"][0]["text"] == "stream: trigger print first · 1-minute: ordered (1)"
    assert {LT.tick_terminal(d) for d in ln} == {"ordered", "never_triggered", "expired", "missed", "other_skip", None}


def test_stream_first_is_the_earliest_print_not_the_row_order():
    a = alert("X")
    ev = {"stop": srow(a, "stop", 100), "trigger": srow(a, "trigger", 50)}
    assert LT.stream_first(ev) == "trigger"
    ev = {"stop": srow(a, "stop", 40), "trigger": srow(a, "trigger", 50)}
    assert LT.stream_first(ev) == "stop"
    assert LT.stream_first({"seen": srow(a, "seen", 1)}) == "none"


def test_entry_delta_r_sign_fill_above_the_print_is_positive(mongo):
    up, dn, strm = alert("UPP", bar="10:00"), alert("DWN", bar="10:05"), alert("STR", bar="10:10")
    mongo(alerts=[up, dn, strm],
          lane=[lane(up, order=122, fill=125, fill_px=2.06), lane(dn, order=122, fill=125, fill_px=1.98),
                lane(strm, order=62, fill=64, fill_px=2.50, order_source="stream")],     # NEG: not a tick order
          stream=[srow(up, "trigger", 90, px=2.0), srow(dn, "trigger", 90, px=2.0), srow(strm, "trigger", 60, px=2.0)])
    ed = LT.payload("all", now=NOW, live_from=None)["check"]["entry_delta_r"]
    assert ed["n"] == 2
    assert ed["p90"] > 0                                      # (2.06 − 2.00) / 0.20 = +0.30; (1.98 − 2.00) / 0.20 = −0.10
    assert ed["p50"] == pytest.approx(0.10) and ed["p90"] == pytest.approx(0.26)
    assert ed["text"] == "1-minute fill vs the stream's trigger print: p50 +0.10 R · p90 +0.26 R (2)"


def test_odd_lot_only_count_and_neg_a_trigger_lot_row(mongo):
    a, ln, st = _check_fixture()
    mongo(alerts=list(a.values()), lane=ln, stream=st)
    ol = LT.payload("all", now=NOW, live_from=None)["check"]["odd_lot_only"]
    assert ol["k"] == 1 and ol["n"] == 4                      # MIS only; OTH has a trigger_lot row (NEG); TRG not odd
    assert ol["text"] == "Trigger seen only on an odd-lot print: 1 of 4"


def test_neg_no_stream_rows_no_check_block(mongo):
    al, ln = _baseline_alerts()
    mongo(alerts=al, lane=ln)
    assert LT.payload("all", now=NOW, live_from=None)["check"] is None


# ── bar finality ─────────────────────────────────────────────────────────────────────────────────────────────────
def _final(sym, part, changed, fields, v30, v60):
    return {"_id": f"{DAY}|10:00|{sym}", "date": DAY, "symbol": sym, "bar_t": "10:00", "session_part": part,
            "at30": {"o": 1, "h": 1, "l": 1, "c": 1, "v": v30}, "at60": {"o": 1, "h": 1, "l": 1, "c": 1, "v": v60},
            "changed": changed, "fields_changed": fields, "v_delta": v60 - v30}


def test_finality_counts_and_split(mongo):
    fin = [_final("A", "regular", True, ["v"], 900, 1000), _final("B", "regular", False, [], 500, 500),
           _final("C", "regular", True, ["c"], 400, 400), _final("D", "extended", True, ["v", "h"], 80, 100)]
    mongo(alerts=[alert("A")], final=fin)
    f = LT.payload("all", now=NOW, live_from=None)["finality"]
    assert (f["n"], f["changed"], f["v_changed"]) == (4, 3, 2)
    assert f["text"] == ("Bar finality: 3 of 4 closed 5-minute bars changed between 30 s and 60 s after close "
                         "(volume on 2).")
    assert [p["part"] for p in f["parts"]] == ["regular", "extended"]
    reg, ext = f["parts"]
    assert (reg["n"], reg["changed"], reg["v_changed"]) == (3, 2, 1) and (ext["n"], ext["v_changed"]) == (1, 1)
    assert ext["v_delta_p90_pct"] == 20.0 and ext["text"].startswith("Extended hours — Bar finality: 1 of 1 ")


def test_neg_no_bar_final_rows_no_finality_line(mongo):
    mongo(alerts=[alert("A")])
    assert LT.payload("all", now=NOW, live_from=None)["finality"] is None


# ── span ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_span_today_reads_only_today_and_bad_span_is_the_default(mongo):
    db = mongo(alerts=[alert("TDY"), alert("OLD", day="2026-10-16")])
    p = LT.payload("today", now=NOW, live_from=None)
    assert p["span"] == "today" and p["days"] == [DAY] and [r["symbol"] for r in p["rows"]] == ["TDY"]
    assert db.gajjala_alerts.queries[-1]["date"] == {"$in": [DAY]}
    q = LT.payload("bogus", now=NOW, live_from=None)
    assert q["span"] == GC.LEDGER_SPAN_DEFAULT and len(q["days"]) == GC.LEDGER_SPAN_SESSIONS
    assert [s["key"] for s in q["spans"]] == list(GC.LEDGER_SPANS)


def test_empty_span_serves_the_empty_words(mongo):
    mongo()
    p = LT.payload("5d", now=NOW, live_from="2026-10-20")
    assert p["empty_text"] == "No 🚩 A+ rang in this span." and p["rows"] == [] and p["summary"] == []
    assert p["check"] is None and p["finality"] is None and p["n_alerts"] == 0


def test_a_read_fault_is_no_rows_never_a_raise(monkeypatch):
    def boom():
        raise RuntimeError("mongo down")
    monkeypatch.setattr(EE, "_db", boom)
    assert LT.payload("all", now=NOW, live_from=None)["empty_text"] == LT.EMPTY_TEXT


# ── one source per name ──────────────────────────────────────────────────────────────────────────────────────────
def test_names_are_the_houses():
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import variant as V
    from chart_maps.gajjala import bar_close as BC
    from trading import gajjala_stream as GS
    assert LT.ALERTS_COLL == ST.ALERTS and LT.LIVE_PREFIX == V.GG5.claim_prefix + ":"
    assert LT.STREAM_COLL == GS.STREAM_COLL == "gajjala_lane_stream" and LT.BAR_FINAL_COLL == BC.COLL == "gajjala_bar_final"
    src = open(LT.__file__, encoding="utf-8").read()
    assert "def _parse" not in src and "datetime.fromisoformat" not in src   # ONE stamp parser: gajjala_entry's
    words = " ".join([LT.TITLE, LT.FOOTNOTE, LT.PLACEBO_TEXT, LT.EMPTY_TEXT, LT.CHECK_TITLE, LT.FINALITY_TEXT,
                      LT.CI_TEXT, LT.NO_CI_TEXT, LT.ENTRY_DELTA_TEXT, LT.ODD_LOT_TEXT]
                     + list(LT.STREAM_WORDS.values()) + list(LT.TICK_WORDS.values()))
    assert not re.search("b" + "ounc", words, re.I) and not re.search(r"\bedge\b", words, re.I)


# ── endpoint + script ────────────────────────────────────────────────────────────────────────────────────────────
def test_endpoint_admin_200_and_neg_non_admin_403(mongo, monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    monkeypatch.setattr(LT, "GG_LIVE_FROM", None)               # the no-split body, explicitly
    from trading import api as TA
    import auth
    al, ln = _baseline_alerts()
    mongo(alerts=al, lane=ln)
    monkeypatch.setattr(GE, "_now_et", lambda: NOW)
    resp = asyncio.run(TA.trading_gajjala_latency(span="all", email=auth.HOUSE_OWNER_EMAIL))
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["n_alerts"] == 3 and summary_of(body, "all")["steps"]["ring"]["p50"] == 70.6
    for who in ("nobody@example.com", None):
        with pytest.raises(fastapi.HTTPException) as exc:
            asyncio.run(TA.trading_gajjala_latency(span="all", email=who))
        assert exc.value.status_code == 403


def test_endpoint_empty_span_serves_the_words(mongo, monkeypatch):
    pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    mongo()
    monkeypatch.setattr(GE, "_now_et", lambda: NOW)
    body = json.loads(asyncio.run(TA.trading_gajjala_latency(span="", email=auth.HOUSE_OWNER_EMAIL)).body)
    assert body["span"] == GC.LEDGER_SPAN_DEFAULT and body["empty_text"] == LT.EMPTY_TEXT


def test_script_prints_the_endpoints_numbers(mongo, monkeypatch):
    pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    from scripts import gajjala_latency_report as REP
    a, ln, st = _check_fixture()
    al, ln2 = _baseline_alerts()
    mongo(alerts=list(a.values()) + al, lane=ln + ln2, stream=st,
          final=[_final("A", "regular", True, ["v"], 900, 1000)])
    monkeypatch.setattr(GE, "_now_et", lambda: NOW)
    body = json.loads(asyncio.run(TA.trading_gajjala_latency(span="all", email=auth.HOUSE_OWNER_EMAIL)).body)
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert REP.main(["--span", "all", "--json"]) == 0
    assert json.loads(buf.getvalue()) == body
    buf = io.StringIO()
    with redirect_stdout(buf):
        REP.main(["--span", "all"])
    text = buf.getvalue()
    assert text.startswith(LT.TITLE) and LT.FOOTNOTE in text and body["check"]["title"] in text
    assert "p50      70.6" in text                              # the ring p50 of the same rows
