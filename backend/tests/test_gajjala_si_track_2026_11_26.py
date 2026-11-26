"""🏁 🩳 SI track record (2026-11-26, SPEC sitrack rev 2 §3.7, WP be-track) — the ledger's rules, negatives first.

Ajay 2026-11-26: "I want us to track these patters for future from SI like a track recprd with in SI stocks itself".
Hermetic: a fake gajjala store, injected SI / SSR / Reg SHO / split / 1-minute seams. Not advice.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import si_track as SIT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import runners as RN
from chart_maps.replays import constants as RC
from daytrading.data import ET_PREMARKET_OPEN, ET_RTH_OPEN
from short_interest import basis_math as BM
from short_interest import read as SR
from short_interest import ssr as SSR
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_store import fake_store as _base_fake_store

ET = ZoneInfo("America/New_York")
S, P, PP, N = date(2026, 11, 19), date(2026, 11, 18), date(2026, 11, 17), date(2026, 11, 20)
HALF, AFTER_HALF = date(2026, 11, 27), date(2026, 11, 30)
GOLDEN = Path(__file__).parent / "fixtures" / "gajjala_si_track_block_golden_2026_11_26.json"


class StateColl(FakeColl):
    """FakeColl + Mongo's `$addToSet` (the index write) + a find that FAILS on chosen ids: `fail_ids[_id] = k` makes
    the next k finds of that id raise (what store.get_state swallows into {})."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fail_ids = {}
        self.ops = []

    def _trip(self, q):
        sid = (q or {}).get("_id")
        if isinstance(sid, str) and self.fail_ids.get(sid, 0) > 0:
            self.fail_ids[sid] -= 1
            raise RuntimeError("mongo down")

    def find(self, q=None, projection=None):
        self._trip(q)
        return super().find(q, projection)

    def find_one(self, q=None, projection=None):
        self._trip(q)
        return super().find_one(q, projection)

    def update_one(self, q, upd, upsert=False):
        self.ops.append((q.get("_id"), tuple(upd)))
        return super().update_one(q, upd, upsert)

    def _apply(self, doc, upd, inserting):
        rest = {}
        for op, fields in upd.items():
            if op != "$addToSet":
                rest[op] = fields
                continue
            for k, v in fields.items():
                cur = doc.get(k, [])
                if not isinstance(cur, list):
                    raise TypeError("$addToSet on a non-array")
                doc[k] = cur if v in cur else cur + [v]
        super()._apply(doc, rest, inserting)


def fake_store(**over):
    return _base_fake_store(**dict({ST.STATE: StateColl()}, **over))


# ── builders ──────────────────────────────────────────────────────────────────────────────────────────────────────
def et(d, hhmm):
    return datetime.combine(d, time.fromisoformat(hhmm), tzinfo=ET)


def utc(d, hhmm):
    return et(d, hhmm).astimezone(timezone.utc)


NIGHT = utc(S, "20:15")


def bar(d, start, o, h=None, l=None, c=None, v=1000.0, s=None):
    t = datetime.combine(d, time.fromisoformat(start)) + timedelta(minutes=5)
    h = o if h is None else h
    l = min(o, h) if l is None else l
    c = o if c is None else c
    out = {"t": t.strftime("%Y-%m-%d %H:%M"), "o": o, "h": h, "l": l, "c": c, "v": v}
    if s:
        out["s"] = s
    return out


def starts(lo, hi):
    t = datetime.combine(S, time.fromisoformat(lo))
    end = datetime.combine(S, time.fromisoformat(hi))
    out = []
    while t < end:
        out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=5)
    return out


def flat(d, lo, hi, px, s=None, v=1000.0):
    return [bar(d, t, px, px, px, px, v, s) for t in starts(lo, hi)]


def tail(d, close, reg_end="16:00"):
    """The prior session's 15:00–20:00 tail; bars past `reg_end` tagged after hours."""
    return flat(d, "15:00", reg_end, close) + flat(d, reg_end, "20:00", close * 1.01, s="ah")


def day(d, px=1.0, pm=None, ah=None, reg_end="16:00"):
    return (flat(d, "04:00", "09:30", pm if pm is not None else px, s="pre")
            + flat(d, "09:30", reg_end, px) + flat(d, reg_end, "20:00", ah if ah is not None else px, s="ah"))


def put_high(bars, start, h):
    for b in bars:
        if RN._bar_start(b) == start:
            b["h"] = h
            b["c"] = min(b["c"], h)
    return bars


def rdoc(sym, d, bars5, prior=None, curves=None, at=None, fl=2_000_000):
    return {"_id": f"{d.isoformat()}|{sym}", "date": d.isoformat(), "symbol": sym,
            "tile": {"bars5": bars5, "curves5": curves or [], "bars5_prior": prior or []},
            "ctx": {"float": {"shares": fl, "src": "float", "text": "Float", "as_of": P.isoformat()}},
            "at": at or utc(d, "20:01")}


def scan(sym, d, *, first="08:10", pc=None, held=False):
    doc = {"_id": f"{d.isoformat()}|{sym}", "date": d.isoformat(), "symbol": sym,
           "first_qualified_at": utc(d, first), "last": {"prev_close": pc} if pc else {}}
    if held:
        doc["held"] = True
    return doc


def blk(sym, *, si=800_000, fl=2_000_000, settlement="2026-10-30", prev=("2026-10-15", 500_000), today=S, **extra):
    doc = {"symbol": sym, "v": 2, "short_interest": si, "settlement_date": settlement, "float_shares": fl,
           "float_asof": "2026-11-18", "float_source": "yahoo", "shares_outstanding": int(fl * 1.25),
           "shares_asof": "2026-11-01", "shares_source": "sec", "avg_daily_volume": 100_000, "days_to_cover": 1.0}
    if prev:
        doc.update(prev_settlement_date=prev[0], prev_short_interest=prev[1])
    b = SR.si_block(doc, today=today)
    b.update(extra)
    return b


def put(st, name, *docs):
    for doc in docs:
        st.coll(name).docs[doc["_id"]] = dict(doc)


def ssr_engine(states_open=None, states_night=None, items=None, status="ok", seen=None):
    def read(symbols, at):
        if seen is not None:
            seen.append(at)
        night = at.astimezone(ET).time() >= SIT._clock(SIT.NIGHT_AT)
        st = states_night if night else states_open
        return {"status": status, "states": {s: (st or {}).get(s, "unknown") for s in symbols},
                "items": dict(items or {}) if night else {}}
    return read


def world(*, blocks=None, extra_reads=(), tail_close=1.0):
    """AAA listed on P only (a winner), BBB on P and S (not a winner), CCC first listed S at 08:10 (a winner),
    ZZZ read but never listed. Prior close 1.0 from every tail."""
    st = fake_store()
    put(st, ST.SCAN, scan("AAA", P, first="09:40"), scan("BBB", P, first="09:45"),
        scan("BBB", S, first="10:00", pc=1.0), scan("CCC", S, first="08:10", pc=1.0))
    prior = tail(P, tail_close)
    put(st, ST.READS,
        rdoc("AAA", S, put_high(day(S), "10:00", 1.5), prior),
        rdoc("BBB", S, put_high(day(S), "11:00", 1.2), prior),
        rdoc("CCC", S, put_high(day(S), "09:35", 1.8), prior),
        rdoc("ZZZ", S, put_high(day(S), "10:00", 3.0), prior), *extra_reads)
    blocks = blocks if blocks is not None else {s: blk(s) for s in ("AAA", "BBB", "CCC", "ZZZ")}
    return st, (lambda syms: {s: blocks[s] for s in syms if s in blocks})


SEAMS = dict(ssr_read=ssr_engine(), sho_read=lambda now: {"items": {}, "complete": True},
             split_lookup=lambda sym, lo, hi: False, load_1m=lambda sym, d: None)


def rec(st, si_read, session=S, now=NIGHT, **kw):
    seams = dict(SEAMS, si_read=si_read)
    seams.update(kw)
    return SIT.record_session(st, session, now, **seams)


def row_of(res, sym):
    return next(r for r in res["doc"]["rows"] if r["symbol"] == sym)


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_the_house_ones_by_name():
    from scripts import gajjala_study as GS
    assert SIT.WIN_PCT == WC.RAN_MIN_PCT
    assert SIT.FIRST_HOUR_END == RC.WIN_TIMING_BUCKETS[0][2]
    assert SIT.SSR_OPEN_AT == ET_PREMARKET_OPEN and SIT.NIGHT_AT == GC.LEDGER_GRADE_AT_ET
    assert SIT.LOOKBACK_SESSIONS == GC.LEDGER_GRADE_LOOKBACK_SESSIONS
    assert SIT.MAX_LOADS == GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS and SIT.ROWS_MAX == GC.LEDGER_ROWS_MAX
    assert SIT.SPAN_SESSIONS == GC.LEDGER_SPAN_SESSIONS_LONG
    assert SIT.MIN_NAMES == GS.MIN_CLUSTERS                      # NEGATIVE pin: the typed copy never drifts
    assert SIT.FAULT_TEXT == HS.SIT_FAULT_TEXT
    assert not hasattr(SIT, "PRIOR")


def test_NEGATIVE_seven_patterns_gap_up_is_a_shape_only():
    keys = [k for k, _l, _w in SIT.PATTERNS]
    assert len(SIT.PATTERNS) == 7
    assert keys == ["ssr_open", "tier_extreme", "regsho_on", "regsho_past", "dilution_before", "split_before",
                    "prev_winner"]
    assert "gap_up" not in keys and "gap_up" in [k for k, _l in SIT.SHAPES]
    assert "dilution" not in keys and "split" not in keys


def test_engine_pin_in_play_at_both_clocks_on_a_regular_a_half_and_the_day_after():
    from catalysts.medical.reaction import prev_market_day
    for d in (S, HALF, AFTER_HALF):
        o, n = SIT.ssr_clocks(d)
        assert SSR.in_play(o) == [prev_market_day(d)], d
        assert SSR.in_play(n) == [d], d


# ── cohort [C1] ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_cohort_lists_the_listed_names_and_NEGATIVE_an_unlisted_read_gets_no_row():
    st, si = world()
    res = rec(st, si)
    assert [r["symbol"] for r in res["doc"]["rows"]] == ["AAA", "BBB", "CCC"]
    assert "ZZZ" not in {r["symbol"] for r in res["doc"]["rows"]}
    assert set(res["doc"]["rows"][0]) == set(SIT.ROW_KEYS)
    assert st.get_state(SIT.INDEX_ID)["dates"] == [S.isoformat()]


def test_NEGATIVE_listed_read_raising_records_nothing(monkeypatch):
    from chart_maps.gajjala import scanner as SC
    st, si = world()
    monkeypatch.setattr(SC, "listed_symbols", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        rec(st, si)
    assert st.get_state(SIT.STATE_FMT.format(date=S.isoformat())) == {} and st.get_state(SIT.INDEX_ID) == {}
    out = SIT.record_night(NIGHT, store=st, **dict(SEAMS, si_read=si))
    assert any(f.startswith("record:%s" % S.isoformat()) or f.startswith("listed_empty") for f in out["faults"])
    assert SIT.index_dates(st) == []


def test_NEGATIVE_short_interest_unread_records_nothing():
    st, _si = world()
    with pytest.raises(RuntimeError):
        rec(st, lambda syms: None)
    assert SIT.index_dates(st) == []


def test_NEGATIVE_excluded_names_get_no_row_and_are_counted():
    blocks = {"AAA": blk("AAA"), "BBB": blk("BBB", tier=None), "CCC": dict(blk("CCC"), status="stale")}
    st, si = world(blocks=blocks, extra_reads=())
    put(st, ST.SCAN, scan("DDD", P), scan("EEE", P))
    put(st, ST.READS, rdoc("DDD", S, day(S), tail(P, 1.0), fl=10_000_000),
        rdoc("EEE", S, day(S), tail(P, 1.0), fl=20_000_000))
    blocks.update(DDD=blk("DDD"), EEE=blk("EEE"))
    res = rec(st, lambda syms: {s: blocks[s] for s in syms if s in blocks})
    assert [r["symbol"] for r in res["doc"]["rows"]] == ["AAA"]
    ex = res["doc"]["excluded"]
    assert ex["no_tier"] == 1 and ex["stale"] == 1 and ex["floats_disagree"] == 1 and ex["float_over"] == 1
    assert set(ex) == set(HS.REASONS)


# ── listing [C1] ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_listing_flags_are_ex_ante_and_not_the_house_carried_word():
    st, si = world()
    res = rec(st, si)
    a, b, c = (row_of(res, s) for s in ("AAA", "BBB", "CCC"))
    assert (a["listed_before"], a["qualified_today"], a["listed_at"]) == (True, False, None)
    assert (b["listed_before"], b["qualified_today"], b["listed_at"]) == (True, True, "10:00")
    assert (c["listed_before"], c["qualified_today"], c["listed_at"]) == (False, True, "08:10")
    assert len(SIT.counted(res["doc"]["rows"])) == 2               # BBB qualified again — never dropped


def test_NEGATIVE_a_held_scan_doc_lists_nothing():
    st, si = world()
    st.coll(ST.SCAN).docs = {}
    put(st, ST.SCAN, scan("AAA", P, held=True))
    res = rec(st, si)
    assert res["rows"] == 0


# ── prior close [C1] ──────────────────────────────────────────────────────────────────────────────────────────────
def test_prior_close_order_tail_then_prior_read_then_scan():
    prior = tail(P, 2.0)
    assert SIT.prior_close_of(rdoc("A", S, day(S), prior), None, None, S) == (2.0, "tail")


def test_NEGATIVE_the_day_after_a_half_day_takes_the_prior_read_bar_starting_12_55():
    half_tail = flat(HALF, "15:00", "16:00", 9.0) + flat(HALF, "16:00", "20:00", 9.0, s="ah")
    prev_doc = rdoc("A", HALF, flat(HALF, "09:30", "12:55", 3.0) + [bar(HALF, "12:55", 3.3)]
                    + flat(HALF, "13:00", "16:00", 9.0), at=utc(HALF, "17:01"))
    v = SIT.prior_close_of(rdoc("A", AFTER_HALF, day(AFTER_HALF), half_tail), prev_doc, None, AFTER_HALF)
    assert v == (3.3, "prior_read")


def test_NEGATIVE_no_prior_read_falls_to_the_scan_doc_and_none_is_no_prev_close():
    assert SIT.prior_close_of(rdoc("A", S, day(S)), None, scan("A", S, pc=1.7), S) == (1.7, "scan")
    assert SIT.prior_close_of(rdoc("A", S, day(S)), None, None, S) == (None, None)
    st, si = world()
    st.coll(ST.READS).docs[f"{S.isoformat()}|AAA"]["tile"]["bars5_prior"] = []
    r = row_of(rec(st, si), "AAA")
    assert r["outcome_state"] == "no_prev_close" and r["winner"] is None and r["high_pct"] is None
    assert len(SIT.counted([r])) == 0


def test_NEGATIVE_a_name_with_no_scan_doc_that_day_is_graded():
    st, si = world()
    r = row_of(rec(st, si), "AAA")                                # AAA has no scan doc on S (the 138-of-248 case)
    assert r["prev_close_src"] == "tail" and r["scan_prev_close"] is None
    assert r["outcome_state"] == "ok" and r["winner"] is True and r["winner_scan"] is None


def test_NEGATIVE_the_scan_figure_is_never_chosen_while_a_tail_exists_glsi_shape():
    st, si = world(tail_close=13.81)
    hi = 13.76 * 1.4                                              # +40% on the scan figure, under +40% on the tail
    st.coll(ST.READS).docs[f"{S.isoformat()}|BBB"]["tile"]["bars5"] = put_high(day(S, 13.9), "11:00", hi)
    st.coll(ST.SCAN).docs[f"{S.isoformat()}|BBB"]["last"]["prev_close"] = 13.76
    r = row_of(rec(st, si), "BBB")
    assert r["prev_close"] == 13.81 and r["prev_close_src"] == "tail" and r["scan_prev_close"] == 13.76
    assert r["winner"] is False and r["winner_scan"] is True


# ── split [C1] ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_split_in_the_window_leaves_no_outcome_numbers():
    st, si = world()
    r = row_of(rec(st, si, split_lookup=lambda sym, lo, hi: "2026-11-19" if sym == "AAA" else False), "AAA")
    assert r["outcome_state"] == "split" and r["winner"] is None and r["high_pct"] is None and r["open_930"] is None


def test_NEGATIVE_an_unreadable_split_check_is_split_unread_and_retried():
    st, si = world()
    rec(st, si, split_lookup=lambda sym, lo, hi: None)
    r = next(x for x in SIT.session_doc(st, S)["rows"] if x["symbol"] == "AAA")
    assert r["outcome_state"] == "split_unread" and r["winner"] is None
    ctx = SIT.Ctx(st, NIGHT + timedelta(days=1), **dict(SEAMS))
    SIT.retry_session(ctx, S)
    r = next(x for x in SIT.session_doc(st, S)["rows"] if x["symbol"] == "AAA")
    assert r["outcome_state"] == "ok" and r["winner"] is True


def test_NEGATIVE_one_split_lookup_per_symbol_and_window_per_run():
    calls = []
    ctx = SIT.Ctx(fake_store(), NIGHT, split_lookup=lambda s, lo, hi: calls.append((s, lo, hi)) or False)
    for _ in range(3):
        assert ctx.split("AAA", P, S) is False
    ctx.split("AAA", S, N)
    assert calls == [("AAA", P, S), ("AAA", S, N)] and ctx.budget.split_calls == 2


# ── point in time ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_settlement_published_on_the_session_day_is_not_used():
    d = date(2026, 11, 24)
    b = blk("AAA", settlement="2026-11-13", prev=("2026-10-30", 300_000), today=d)
    assert b["published_on"] == d.isoformat()
    p = SIT.pit_block(b, d)
    assert p["pit"] == "prev" and p["settlement_date"] == "2026-10-30" and p["si_shares"] == 300_000
    assert SIT.pit_block(b, date(2026, 11, 25))["pit"] == "latest"


def test_NEGATIVE_no_prior_settlement_means_no_row_and_no_si_counted():
    d = date(2026, 11, 24)
    assert SIT.pit_block(blk("AAA", settlement="2026-11-13", prev=None, today=d), d) is None
    st, si = world(blocks={"AAA": blk("AAA", settlement="2026-10-30", prev=None, today=S, published_on=S.isoformat()),
                           "BBB": blk("BBB"), "CCC": blk("CCC")})
    res = rec(st, si)
    assert "AAA" not in {r["symbol"] for r in res["doc"]["rows"]} and res["doc"]["excluded"]["no_si"] == 1


def test_NEGATIVE_a_prior_settlement_itself_not_yet_published_is_no_row():
    d = date(2026, 11, 24)
    b = dict(blk("AAA", settlement="2026-11-13", today=d), prev_settlement_date="2026-11-14")
    assert SIT.pit_block(b, d) is None


# ── winner ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _facts(bars, pc=1.0, d=S, curves=None):
    f = SIT.session_facts(bars, curves or [], pc, d, reg_close=SIT._reg_close(d))
    f.pop("ran")
    return f


def test_ncpl_shape_fade_then_after_hours_ramp_is_not_a_winner():
    bars = (flat(S, "04:00", "09:30", 2.05, s="pre") + [bar(S, "09:30", 2.10, 2.12, 2.05, 2.08)]
            + flat(S, "09:35", "16:00", 2.0) + flat(S, "16:00", "19:55", 2.2, s="ah")
            + [bar(S, "19:55", 2.4, 2.70, 2.4, 2.6, s="ah")])
    f = _facts(bars, pc=2.0)
    assert f["winner"] is False and f["high_where"] == "ah" and f["high_at"] == "19:55"
    assert f["morning_fade"] is True and f["fade_ramp"] is True and f["open_930"] == 2.10
    assert f["high_pct"] == pytest.approx(35.0)


def test_NEGATIVE_a_premarket_only_spike_is_not_a_winner():
    f = _facts(put_high(put_high(day(S), "08:00", 1.6), "10:00", 1.3))
    assert f["winner"] is False and f["pm_peak"] is True and f["day_high_where"] == "pre"
    assert f["high_pct"] == pytest.approx(30.0)


def test_NEGATIVE_plus_40_in_hours_with_a_higher_premarket_high_is_a_winner_but_not_strict():
    f = _facts(put_high(put_high(day(S), "08:00", 1.6), "10:00", 1.45))
    assert f["winner"] is True and f["pm_peak"] is True and f["winner_strict"] is False


def test_NEGATIVE_exactly_40_counts_and_39_99_does_not():
    assert _facts(put_high(day(S), "10:00", 1.4))["winner"] is True
    assert _facts(put_high(day(S), "10:00", 1.3999))["winner"] is False


def test_NEGATIVE_half_day_bar_starting_13_05_tagged_regular_is_after_hours():
    bars = flat(HALF, "09:30", "16:00", 1.0)
    put_high(bars, "13:05", 1.5)
    f = _facts(bars, d=HALF)
    assert f["high_at"] == "13:05" and f["high_where"] == "ah"


def test_equality_pin_grade_is_ran_of_on_the_stand_in_scan_doc():
    doc = rdoc("A", S, put_high(day(S), "10:00", 1.5))
    assert SIT.grade(doc, 1.0, S) == RN.ran_of({"last": {"prev_close": 1.0}}, doc, S)


def _minutes(d, high_at="10:07", high=1.5):
    rows = []
    t = et(d, "04:00")
    while t < et(d, "20:00"):
        hhmm = t.strftime("%H:%M")
        sess = "premarket" if hhmm < "09:30" else ("rth" if hhmm < "16:00" else "afterhours")
        px = high if hhmm == high_at else 1.0
        rows.append((t.astimezone(timezone.utc).replace(tzinfo=None), 1.0, max(px, 1.0), 1.0, 1.0, 100.0, sess))
        t += timedelta(minutes=1)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "session"]).set_index("ts")
    return df


def test_equality_pin_the_1_minute_stand_in_gives_the_stored_bars_high_where_and_high_at():
    doc = SIT.standin_read("A", S, _minutes(P), _minutes(S), NIGHT)
    stored = put_high(day(S), "10:05", 1.5)
    a = _facts(doc["tile"]["bars5"])
    b = _facts(stored)
    assert (a["high_at"], a["high_where"]) == (b["high_at"], b["high_where"]) == ("10:05", "first_hour")


# ── bars [C9] ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_half_day_doc_stamped_17_01_is_complete_no_load():
    calls = []
    ctx = SIT.Ctx(fake_store(), NIGHT, load_1m=lambda s, d: calls.append((s, d)))
    doc = rdoc("A", HALF, day(HALF), at=utc(HALF, "17:01"))
    assert SIT.complete(doc, HALF) and SIT.day_read(ctx, "A", HALF, doc) == (doc, "reads") and calls == []


def test_NEGATIVE_a_half_day_doc_at_16_40_and_a_regular_doc_at_19_40_take_the_1_minute_path():
    for d, stamp in ((HALF, "16:40"), (S, "19:40")):
        calls = []
        ctx = SIT.Ctx(fake_store(), utc(AFTER_HALF, "20:30"), load_1m=lambda s, dd: calls.append((s, dd)) or _minutes(dd))
        doc = rdoc("A", d, day(d), at=utc(d, stamp))
        assert not SIT.complete(doc, d)
        got, src = SIT.day_read(ctx, "A", d, doc)
        assert src == "minutes" and calls[0] == ("A", d) and got is not doc


# ── ⛔ [C2] ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ssr_three_states_field_by_field():
    o = {"status": "ok", "states": {"A": "on", "B": "off", "C": "unknown"}}
    n = {"status": "ok", "states": {"A": "off", "B": "on", "C": "unknown"},
         "items": {"B": {"triggered_on": "2026-11-19", "triggered_at_et": "10:18"}}}
    assert SIT.ssr_facts(o, n, "A") == {"ssr_open": True, "ssr_trig_day": False, "ssr_trig_on": None,
                                        "ssr_trig_at": None}
    assert SIT.ssr_facts(o, n, "B") == {"ssr_open": False, "ssr_trig_day": True, "ssr_trig_on": "2026-11-19",
                                        "ssr_trig_at": "10:18"}
    assert SIT.ssr_facts(o, n, "C") == dict.fromkeys(SIT.SSR_KEYS)


def test_NEGATIVE_a_session_with_no_ssr_record_is_none_never_false():
    st, si = world()
    rows = rec(st, si, ssr_read=ssr_engine())["doc"]["rows"]      # every name "unknown" (the 11-13 shape)
    assert all(r["ssr_open"] is None and r["ssr_trig_day"] is None for r in rows)


def test_NEGATIVE_a_status_other_than_ok_is_none_and_a_raise_is_a_fault_row_still_written():
    assert SIT.ssr_facts({"status": "failed", "states": {"A": "on"}}, None, "A")["ssr_open"] is None
    st, si = world()

    def boom(symbols, at):
        raise RuntimeError("ssr down")
    res = rec(st, si, ssr_read=boom)
    assert res["rows"] == 3 and "ssr_open" in res["faults"] and "ssr_night" in res["faults"]
    assert all(r["ssr_open"] is None for r in res["doc"]["rows"])


def test_NEGATIVE_both_clocks_are_built_from_the_session_date_not_the_wall_clock():
    seen_a, seen_b = [], []
    st, si = world()
    rec(st, si, ssr_read=ssr_engine(seen=seen_a))
    st2, si2 = world()
    rec(st2, si2, now=NIGHT + timedelta(days=6), source="late", ssr_read=ssr_engine(seen=seen_b))
    assert seen_a == seen_b == [utc(S, "04:00"), utc(S, GC.LEDGER_GRADE_AT_ET)]


def test_NEGATIVE_a_none_ssr_field_is_reread_and_filled_once_never_overwritten():
    st, si = world()
    rec(st, si, ssr_read=ssr_engine(states_open={"AAA": "on"}))
    ctx = SIT.Ctx(st, NIGHT + timedelta(days=1),
                  **dict(SEAMS, ssr_read=ssr_engine(states_open={"AAA": "off", "BBB": "off"},
                                                     states_night={"BBB": "on"},
                                                     items={"BBB": {"triggered_on": S.isoformat(),
                                                                    "triggered_at_et": "11:02"}})))
    SIT.retry_session(ctx, S)
    rows = {r["symbol"]: r for r in SIT.session_doc(st, S)["rows"]}
    assert rows["AAA"]["ssr_open"] is True                       # a stored True is never overwritten
    assert rows["BBB"]["ssr_open"] is False and rows["BBB"]["ssr_trig_day"] is True
    assert rows["BBB"]["ssr_trig_at"] == "11:02" and rows["CCC"]["ssr_open"] is None


# ── 📄 ✂️ [C3] ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _basis(filings=(), splits=(), sec="ok", sp="ok", flags=()):
    return {"basis": {"filings": list(filings), "splits": list(splits), "sources": {"sec": sec, "splits": sp},
                      "flags": list(flags)}}


def test_filings_dated_the_session_day_vs_the_day_before():
    flag = {"key": BM.FLAG_FILING, "short": "📄 424B5 11/19"}
    f = SIT.filing_facts(_basis([{"form": "424B5", "filed": S.isoformat()}], flags=[flag]), S)
    assert f["dilution"] is True and f["dilution_before"] is False and f["flag_shorts"] == ["📄 424B5 11/19"]
    f = SIT.filing_facts(_basis([{"form": "424B5", "filed": P.isoformat()}], flags=[flag]), S)
    assert f["dilution"] is True and f["dilution_before"] is True


def test_splits_executed_on_the_day_vs_upcoming():
    ex = {"execution_date": S.isoformat(), "when": "executed"}
    up = {"execution_date": N.isoformat(), "when": "upcoming"}
    assert SIT.filing_facts(_basis(splits=[ex]), S)["split_before"] is True
    assert SIT.filing_facts(_basis(splits=[up]), S)["split_before"] is False


def test_NEGATIVE_sec_failed_and_no_basis_are_none():
    assert SIT.filing_facts(_basis([{"filed": P.isoformat()}], sec="failed"), S)["dilution_before"] is None
    assert SIT.filing_facts(_basis(sp="failed"), S)["split_before"] is None
    assert SIT.filing_facts({}, S) == dict.fromkeys(SIT.FILING_KEYS)


def test_NEGATIVE_late_and_backfill_sessions_carry_no_sho_filing_split_fields():
    blocks = {s: dict(blk(s), **_basis([{"form": "424B5", "filed": P.isoformat()}])) for s in ("AAA", "BBB", "CCC")}
    sho = lambda now: {"items": {"AAA": {"state": "on", "as_of": P.isoformat(), "run": {"state": "passed"}}},
                       "complete": True}
    for src in ("late", "backfill"):
        st, si = world(blocks=blocks)
        rows = rec(st, si, source=src, sho_read=sho)["doc"]["rows"]
        for r in rows:
            for k in SIT.SHO_KEYS + SIT.FILING_KEYS:
                assert r[k] is None, (src, k)
            assert r["late"] is True
    st, si = world(blocks=blocks)
    r = row_of(rec(st, si, sho_read=sho), "AAA")
    assert r["regsho_on"] is True and r["regsho_past"] is True and r["dilution_before"] is True and r["late"] is False


def test_NEGATIVE_sho_off_list_is_false_only_when_every_list_was_read():
    assert SIT.sho_facts({"items": {}, "complete": True}, "A")["regsho_on"] is False
    assert SIT.sho_facts({"items": {}, "complete": False}, "A")["regsho_on"] is None
    assert SIT.sho_facts(None, "A") == dict.fromkeys(SIT.SHO_KEYS)


# ── cross [C9] ────────────────────────────────────────────────────────────────────────────────────────────────────
def _curves(bars, up_at_start):
    i = next(j for j, b in enumerate(bars) if RN._bar_start(b) == up_at_start)
    fast = [1.0] * i + [2.0] * (len(bars) - i)
    return [{"tone": "ema9", "values": fast}, {"tone": "ema21", "values": [1.5] * len(bars)}]


def test_NEGATIVE_a_premarket_only_cross_never_sets_the_first_hour():
    bars = day(S)
    f = _facts(bars, curves=_curves(bars, "08:40"))
    assert f["cross_pre"] is True and f["cross_up_at"] is None and f["cross_by_first_hour"] is False


def test_cross_on_the_bar_starting_09_50_is_first_hour_and_10_30_is_not():
    bars = day(S)
    assert _facts(bars, curves=_curves(bars, "09:50"))["cross_by_first_hour"] is True
    f = _facts(bars, curves=_curves(bars, "10:30"))
    assert f["cross_up_at"] == "10:30" and f["cross_by_first_hour"] is False and f["cross_pre"] is False


def test_NEGATIVE_no_curves_reads_none_not_false():
    f = _facts(day(S))
    assert f["cross_pre"] is None and f["cross_by_first_hour"] is None


# ── VWAP [C9] ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_vwap_reclaim_under_and_never_under():
    df = _minutes(S)
    df.loc[df.index[-30:-10], "close"] = 0.5                     # dips under late, then back above
    df.loc[df.index[-10:], "close"] = 2.0
    f = SIT.minute_facts(df, S, reg_close=SIT._reg_close(S))
    assert f["vwap_state"] == "reclaimed" and f["vwap_reclaim_at"] == "19:50"
    df.loc[df.index[-1], "close"] = 0.1
    assert SIT.minute_facts(df, S, reg_close=SIT._reg_close(S))["vwap_state"] == "under"
    up = _minutes(S)
    up["low"] = 0.5                                               # every close above its typical price → never at / under
    assert SIT.minute_facts(up, S, reg_close=SIT._reg_close(S))["vwap_state"] == "never_under"


def test_NEGATIVE_no_frame_is_not_read():
    assert SIT.minute_facts(None, S, reg_close=SIT._reg_close(S)) == {"vwap_reclaim_at": None,
                                                                     "vwap_state": "not_read"}


# ── prev_winner [C7] ──────────────────────────────────────────────────────────────────────────────────────────────
def test_prev_winner_from_the_prior_stored_doc():
    st, si = world()
    st.set_state(SIT.STATE_FMT.format(date=P.isoformat()), {"rows": [{"symbol": "AAA", "winner": True}]})
    assert row_of(rec(st, si), "AAA")["prev_winner"] is True


def test_NEGATIVE_no_prior_row_grades_the_prior_reads_on_the_same_basis_and_nothing_is_none():
    st, si = world()
    put(st, ST.READS, rdoc("BBB", P, day(P, 1.0), tail(PP, 1.0)))       # did NOT run on P → False, not None
    put(st, ST.READS, rdoc("CCC", P, put_high(day(P), "10:00", 1.6), tail(PP, 1.0)))
    res = rec(st, si)
    assert row_of(res, "BBB")["prev_winner"] is False and row_of(res, "CCC")["prev_winner"] is True
    assert row_of(res, "AAA")["prev_winner"] is None


# ── next ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_next_is_pending_until_the_next_session_ends_then_filled_and_a_split_is_split():
    st, si = world()
    rec(st, si)
    out = SIT.fill_next(st, S, utc(N, "19:00"), **dict(split_lookup=SEAMS["split_lookup"], load_1m=SEAMS["load_1m"]))
    assert out["filled"] == 0 and all(r["next"]["state"] == "pending" for r in SIT.session_doc(st, S)["rows"])
    nb = put_high(day(N, 2.0), "11:00", 3.0)
    nb = [dict(b, l=1.5) if RN._bar_start(b) == "12:00" else b for b in nb]
    put(st, ST.READS, rdoc("AAA", N, nb))
    SIT.fill_next(st, S, utc(N, "20:15"), split_lookup=lambda s, lo, hi: "2026-11-20" if s == "BBB" else False,
                  load_1m=lambda s, d: None)
    rows = {r["symbol"]: r for r in SIT.session_doc(st, S)["rows"]}
    a = rows["AAA"]["next"]
    assert a["state"] == "ok" and a["open"] == 2.0 and a["high_pct"] == pytest.approx(50.0)
    assert a["low_pct"] == pytest.approx(-25.0)
    assert rows["BBB"]["next"]["state"] == "split" and rows["BBB"]["next"]["open"] is None
    assert rows["CCC"]["next"]["state"] == "no_bars"


# ── shuffle + stats [C1 C4 C7] ────────────────────────────────────────────────────────────────────────────────────
def test_shuffle_two_days_two_rows_and_the_seed_repeats():
    flags, wins, days = [True, False, True, False], [True, False, True, False], ["d1", "d1", "d2", "d2"]
    a = SIT.shuffle_share(flags, wins, days, draws=4000, seed=7)
    assert a == SIT.shuffle_share(flags, wins, days, draws=4000, seed=7)
    assert abs(a - 0.5) < 0.04                                    # exact: half the shuffles keep |diff| = 1


def test_NEGATIVE_single_label_days_never_shuffle_and_labels_never_cross_days():
    flags, wins, days = [True, True, False, False], [True, True, False, False], ["d1", "d1", "d2", "d2"]
    assert SIT.shuffle_share(flags, wins, days, draws=500, seed=1) == 1.0
    assert SIT.shuffle_share([True, True], [True, False], ["d", "d"], draws=10, seed=1) is None


def _row(sym, d, *, win, before=True, **kw):
    r = SIT.blank_row(d, sym)
    r.update(listed_before=before, winner=win, outcome_state="ok", **kw)
    return r


def test_hand_computed_two_by_two():
    rows = ([_row("A%d" % i, "2026-11-1%d" % i, win=i < 2, ssr_open=True) for i in range(4)]
            + [_row("B%d" % i, "2026-11-1%d" % i, win=i < 1, ssr_open=False) for i in range(6)]
            + [_row("C0", "2026-11-10", win=True, ssr_open=None)])
    p = SIT.stats(rows)["patterns"][0]
    assert (p["key"], p["n_with"], p["w_with"], p["n_without"], p["w_without"], p["unknown"]) == ("ssr_open", 4, 2, 6,
                                                                                                    1, 1)
    assert p["rate_with"] == 0.5 and p["rate_without"] == pytest.approx(1 / 6)
    assert p["diff_pp"] == pytest.approx(100 * (0.5 - 1 / 6))
    assert p["verdict"] == "no_interval" and p["word"] == "too few names or days" and p["shuffle_share"] is None


def test_NEGATIVE_a_first_listed_winner_moves_no_rate_and_lands_in_new_today():
    rows = [_row("A", "2026-11-10", win=False, ssr_open=True), _row("B", "2026-11-10", win=True, ssr_open=False)]
    a = SIT.stats(rows)
    b = SIT.stats(rows + [_row("C", "2026-11-10", win=True, before=False, ssr_open=True, listed_at="08:10"),
                          _row("D", "2026-11-10", win=True, before=False, listed_at="10:15")])
    assert a["base"] == b["base"] and a["patterns"] == b["patterns"] and a["shapes"] == b["shapes"]
    assert b["new_today"] == {"n": 2, "winners": 2, "before_open": {"n": 1, "winners": 1},
                              "after_open": {"n": 1, "winners": 1}}


def _wide(n_names=25, n_days=25):
    rows = []
    for i in range(n_names * 2):
        d = (date(2026, 1, 1) + timedelta(days=i % n_days)).isoformat()
        rows.append(_row("S%02d" % i, d, win=i % 3 == 0, ssr_open=(i % 2 == 0)))
    return rows


def test_NEGATIVE_under_min_names_or_days_on_a_side_is_no_interval():
    for rows in (_wide(n_names=25, n_days=10), _wide(n_names=8, n_days=25)):
        p = SIT.stats(rows)["patterns"][0]
        assert p["verdict"] == "no_interval" and p["word"] == SIT.WORDS["too_few"] and p["shuffle_share"] is None


def test_NEGATIVE_clear_on_names_only_is_not_shown_the_house_verdict(monkeypatch):
    from scripts import gajjala_study as GS

    def fake(ev, ek, pv, pk, **k):
        return [0.05, 0.10] if str(ek[0]).startswith("S") else [-0.01, 0.02]
    monkeypatch.setattr(GS, "cluster_delta_ci", fake)
    p = SIT.stats(_wide())["patterns"][0]
    assert p["ci_names_pp"] == pytest.approx([5.0, 10.0]) and p["ci_days_pp"] == pytest.approx([-1.0, 2.0])
    assert p["verdict"] == GS.verdict(p["ci_days_pp"], p["ci_names_pp"]) == "no_signal"
    assert p["word"] == "NOT SHOWN" and isinstance(p["shuffle_share"], float)
    monkeypatch.setattr(GS, "cluster_delta_ci", lambda *a, **k: [0.05, 0.10])
    p = SIT.stats(_wide())["patterns"][0]
    assert p["verdict"] == "measured_edge" and p["word"] == SIT.WORDS["clear"] % 7


def test_NEGATIVE_gap_up_counts_as_a_shape_with_no_interval():
    rows = [_row("A", "2026-11-10", win=True, gap_up=True), _row("B", "2026-11-10", win=False, gap_up=False)]
    s = SIT.stats(rows)
    g = next(x for x in s["shapes"] if x["key"] == "gap_up")
    assert g == {"key": "gap_up", "winners": {"k": 1, "n": 1}, "rest": {"k": 0, "n": 1}}
    assert "gap_up" not in {p["key"] for p in s["patterns"]}


def test_NEGATIVE_the_import_failing_leaves_no_interval_but_the_counts(monkeypatch):
    monkeypatch.setattr(SIT, "_study", lambda: None)
    s = SIT.stats(_wide())
    assert s["interval_ok"] is False and s["base"]["ci_names"] is None and s["base"]["n"] == 50
    assert all(p["verdict"] == "no_interval" for p in s["patterns"])


# ── served block ──────────────────────────────────────────────────────────────────────────────────────────────────
def _three_sessions():
    """A fixed three-session fixture: P (AAA winner), S (the world), N (BBB listed before)."""
    st, si = world()
    put(st, ST.SCAN, scan("AAA", PP), scan("CCC", P, first="07:55"))
    put(st, ST.READS, rdoc("AAA", P, put_high(day(P), "10:00", 1.5), tail(PP, 1.0)),
        rdoc("CCC", P, day(P), tail(PP, 1.0)))
    put(st, ST.SCAN, scan("BBB", N, first="09:31", pc=1.0))
    put(st, ST.READS, rdoc("BBB", N, put_high(day(N), "15:10", 1.45), tail(S, 1.0)),
        rdoc("AAA", N, day(N), tail(S, 1.0)))
    put(st, ST.DAILY, {"_id": f"{S.isoformat()}|AAA", "date": S.isoformat(), "symbol": "AAA", "avg_vol_50": 40_000.0})
    with pytest.MonkeyPatch.context() as mp:                     # WP1's frozen name, pinned to a fixed stand-in
        mp.setattr(SR, "dtc_computed", lambda b: round(b["si_shares"] / b["avg_daily_volume"], 2), raising=False)
        for d, now in ((P, utc(P, "20:15")), (S, NIGHT), (N, utc(N, "20:15"))):
            SIT.record_night(now, store=st, **dict(SEAMS, si_read=si, ssr_read=ssr_engine(
                states_open={"AAA": "on", "BBB": "off"}, states_night={"AAA": "off", "BBB": "on"},
                items={"BBB": {"triggered_on": d.isoformat(), "triggered_at_et": "10:18"}})))
    return st


def _block():
    st = _three_sessions()
    return SIT.served_block(st, N, utc(N, "20:30"))


def test_served_block_golden():
    b = _block()
    got = json.loads(json.dumps(b, default=str))
    if os.environ.get("SI_TRACK_GOLDEN_WRITE") == "1":
        GOLDEN.write_text(json.dumps(got, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    assert got == json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert set(b) == set(SIT.BLOCK_KEYS)
    assert [d["date"] for d in b["days"]] == [N.isoformat(), S.isoformat(), P.isoformat()]
    assert [p["key"] for p in b["patterns"]][:2] == ["ssr_open", "tier_extreme"]


def test_NEGATIVE_golden_carries_no_prior_text_no_signal_no_edge_no_bare_shown():
    text = GOLDEN.read_text(encoding="utf-8")
    assert '"prior_text"' not in text
    for bad in (r"\bsignals?\b", r"\bedges?\b", r"(?<!NOT )\bSHOWN\b", r"bounc"):
        assert re.search(bad, text, re.I if bad != r"(?<!NOT )\bSHOWN\b" else 0) is None, bad


def test_NEGATIVE_summary_counts_the_counted_cohort_only():
    b = _block()
    rows = SIT.all_rows(_three_sessions())
    c = SIT.counted(rows)
    assert b["summary_text"] == "🏁 SI track record · %d of %d ran +40%%" % (sum(r["winner"] for r in c), len(c))
    assert len(c) < len([r for r in rows if isinstance(r.get("winner"), bool)])
    for d in b["days"]:
        flags = [r["counted"] for r in d["rows"]]
        assert flags == sorted(flags, reverse=True)               # a not-counted row never sits above a counted one
        groups = [SIT.DAY_GROUPS.index(r["group"]) for r in d["rows"]]
        assert groups == sorted(groups)                           # counted → first listed that day → other


# ── 2026-11-26 refix: the day table's labels and the flags printed once ─────────────────────────────────────────
def _drow(sym, listed_before, winner, state="ok", high=None, flags=None, listed_at=None):
    return {"symbol": sym, "date": S.isoformat(), "listed_before": listed_before, "listed_at": listed_at,
            "winner": winner, "outcome_state": state, "high_pct": high, "flag_shorts": flags}


def test_day_rows_split_into_counted_then_first_listed_then_other_in_that_order():
    rows = [_drow("OTH", True, None, state="no_bars"), _drow("NEW", False, True, high=60.0, listed_at="08:10"),
            _drow("WIN", True, True, high=45.0), _drow("SPL", True, None, state="split"),
            _drow("LOS", True, False, high=10.0), _drow("UNK", None, False, high=5.0)]
    out = SIT._day_rows(rows)
    assert [(r["symbol"], r["group"], r["counted"]) for r in out] == [
        ("WIN", "counted", True), ("LOS", "counted", True), ("NEW", "new", False),
        ("UNK", "other", False), ("OTH", "other", False), ("SPL", "other", False)]
    assert SIT.DAY_GROUPS == ("counted", "new", "other")


def test_NEGATIVE_a_row_listed_before_but_not_graded_is_never_in_the_first_listed_group():
    for st_ in ("no_bars", "split", "split_unread", "no_prev_close"):
        (r,) = SIT._day_rows([_drow("PND", True, None, state=st_)])
        assert r["group"] == "other" and r["counted"] is False, st_
        assert r["cells"]["listed"] == "before"                   # the label it sits under no longer contradicts this
    (r,) = SIT._day_rows([_drow("FRS", False, None, state="no_bars", listed_at="09:31")])
    assert r["group"] == "new" and r["cells"]["listed"] == "09:31"   # first listed that day, ungraded → still "new"
    (r,) = SIT._day_rows([_drow("UNK", None, True, high=50.0)])
    assert r["group"] == "other" and r["counted"] is False       # no listing date on file → never "first listed"


def test_NEGATIVE_served_day_carries_both_labels_and_they_differ():
    b = _block()
    assert b["days"] and all(d["new_label"] == SIT.NEW_LABEL and d["other_label"] == SIT.OTHER_LABEL for d in b["days"])
    assert SIT.NEW_LABEL != SIT.OTHER_LABEL and "first listed" not in SIT.OTHER_LABEL
    for d in b["days"]:
        for r in d["rows"]:
            assert r["group"] in SIT.DAY_GROUPS and r["counted"] is (r["group"] == "counted")


def test_NEGATIVE_every_flag_prints_once_on_a_row_in_the_flags_column_only():
    flags = ["📄 F-1/A 11/20 · same day", "✂️ 1:10 11/19"]
    (r,) = SIT._day_rows([_drow("FLG", True, True, high=50.0, flags=flags)])
    assert r["cells"]["flags"] == " · ".join(flags)
    assert r["chips"] == []
    served = json.dumps({k: v for k, v in r.items()}, ensure_ascii=False)
    for f in flags:
        assert served.count(f) == 1, f
    (r,) = SIT._day_rows([_drow("NOF", True, True, high=50.0, flags=None)])
    assert r["chips"] == [] and r["cells"]["flags"] == SIT.DASH  # flags unread → the dash, still no chip


def test_NEGATIVE_no_stored_doc_is_the_empty_block_not_a_fault():
    b = SIT.served_block(fake_store(), S, NIGHT)
    assert set(b) == set(SIT.BLOCK_KEYS) and b["fault_text"] is None
    assert b["summary_text"] == SIT.EMPTY_SUMMARY and b["empty_text"] and b["n"] == 0


def test_NEGATIVE_every_number_in_rule_text_is_a_constant_value():
    allowed = {str(GC.STAY_LISTED_SESSIONS), "%g" % SIT.WIN_PCT, str(SR.FINRA_PUBLICATION_BDAYS), str(SIT.MIN_NAMES),
               str(SIT.LOOKBACK_SESSIONS), "5", "0"}              # 5 = the 5-minute bar; 0 = "clear 0" (the interval's zero)
    for t in (ET_RTH_OPEN, SIT.SSR_OPEN_AT, time.fromisoformat(GC.LEDGER_GRADE_AT_ET), time(20, 0)):
        allowed |= {t.strftime("%H"), t.strftime("%M")}
    nums = re.findall(r"\d+", SIT.rule_text())
    assert nums and set(nums) <= allowed, set(nums) - allowed
    assert not re.search(r"20\d\d-\d\d-\d\d", SIT.rule_text())


def _hs_block(st):
    return HS.block({"rows": [], "counts": {r: 0 for r in HS.REASONS}}, session=S, now=NIGHT, is_today=True,
                    in_window=True, tf="5m", lim=10, scan_row=lambda s: None, sess={}, halts_by={}, listed={},
                    pass_at=None, flags=None, v=None, st=st, sho_read=lambda now: {"items": {}, "complete": True},
                    ssr_read=lambda s, n: {"status": "ok"}, ssr_si_read=lambda syms: {})


def test_NEGATIVE_a_raising_read_inside_the_high_si_block_is_the_fault_and_the_cards_stand(monkeypatch):
    good = _hs_block(fake_store())
    assert good[HS.SI_TRACK_KEY]["summary_text"] == SIT.EMPTY_SUMMARY
    monkeypatch.setattr(SIT, "served_block", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    bad = _hs_block(fake_store())
    assert bad[HS.SI_TRACK_KEY] == {"fault_text": HS.SIT_FAULT_TEXT}
    assert {k: v for k, v in bad.items() if k != HS.SI_TRACK_KEY} == {k: v for k, v in good.items()
                                                                      if k != HS.SI_TRACK_KEY}


def test_NEGATIVE_a_broken_si_track_module_is_the_fault_too(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.si_track", None)
    import chart_maps.gajjala as pkg
    monkeypatch.delattr(pkg, "si_track", raising=False)
    assert _hs_block(fake_store())[HS.SI_TRACK_KEY] == {"fault_text": HS.SIT_FAULT_TEXT}


def test_NEGATIVE_dtc_reads_the_frozen_engine_name_and_none_without_it(monkeypatch):
    st, si = world()
    st2, si2 = world()                                            # blocks built before the name is patched

    def boom(b):
        raise ValueError("no adv")
    monkeypatch.setattr(SR, "dtc_computed", boom, raising=False)
    assert all(r["dtc"] is None and r["dtc_provider"] == 1.0 for r in rec(st, si)["doc"]["rows"])
    monkeypatch.setattr(SR, "dtc_computed", lambda b: b["si_shares"] / b["avg_daily_volume"], raising=False)
    r = row_of(rec(st2, si2), "AAA")
    assert r["dtc"] == pytest.approx(8.0) and r["dtc_provider"] == 1.0   # pit "latest": 800k short ÷ 100k a day


def test_NEGATIVE_source_guard_no_luk_no_b_word_no_write_but_state_and_kick_false():
    src = Path(SIT.__file__).read_text(encoding="utf-8")
    assert re.search(r"luk", src, re.I) is None
    assert re.search(r"bounc", src, re.I) is None
    assert "kick=False" in src and "kick=True" not in src and "kick_refresh" not in src
    for bad in ("upsert_read", "upsert_ledger", "record_pass", "send_", "insert_one", "replace_one"):
        assert bad not in src, bad
    # PIN MOVED 2026-11-26 refix (predicted by the refix: "add dates with $addToSet") — ONE update_one, the index's
    # $addToSet on gajjala_state; no other raw write.
    # PIN MOVED again 2026-11-26 verify LOW — TWO update_one, both on gajjala_state: the index's $addToSet and the
    # session doc's $set in _write_session (a raised write must raise, never be swallowed and indexed).
    assert src.count("update_one") == 2
    assert re.search(r"c = st\.coll\(ST\.STATE\)[\s\S]{0,120}c\.update_one\(\{\"_id\": INDEX_ID\}, \{\"\$addToSet\"", src)
    assert re.search(r"def _write_session[\s\S]{0,500}c = st\.coll\(ST\.STATE\)[\s\S]{0,200}c\.update_one\(\{\"_id\": sid\}, \{\"\$set\": dict\(doc\)\}, upsert=True\)", src)
    assert "ALL" not in re.findall(r"ST\.(\w+)", src)
