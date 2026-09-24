"""📰 News tab on Chart Maps — the four blocks, the one word map, the budget.

Ajay 2026-09-24: "build me a news tab in chartmaps to give me a bullish market
or bearsish market and also pull Macro calendar that has T1 and T2 tier events
... which sectors are bullish or which hotsectors are bearish. In a table."

What can silently go wrong, one group each, negatives first-class:
  * the market word is invented instead of mapped from the gauge's own state,
  * the macro block reads the calendar at a second cache key (the C1 defect),
  * "today" is printed off a day column that is really the last close (C5),
  * a slow leg hangs the whole tab instead of costing its own block (C6),
  * the sector study's numbers drift from the doc that measured them.
Nothing here talks to Mongo, FRED or Google.
"""
from __future__ import annotations

import ast
import asyncio
import datetime as dt
import json
import os
import re
import time

import pytest

import macro_calendar
from chart_maps import api as CM_API
from chart_maps import news_tab as NT
from rotation import api as RA
from rotation import heat
from rotation import hottest as H
from rotation import sector_news_tags as SNT
from rotation import tracker as T
from sepa import market_gauge
from supply_demand import enterable as EN

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(BACKEND, "chart_maps", "news_tab.py")
SRC = open(SRC_PATH, encoding="utf-8").read()
TREE = ast.parse(SRC)
HEAT_DOC = os.path.join(os.path.dirname(BACKEND), "docs", "supply_demand", "sector_heat.md")
MIRROR = os.path.join(BACKEND, "tests", "fixtures", "enterable_mirror_2026_09_15.json")


# ── fixtures ────────────────────────────────────────────────────────────────
def _gauge(daily=(60, "caution", "Caution"), weekly=(84, "constructive", "Constructive")):
    wk = None
    if weekly is not None:
        wk = {"score": weekly[0], "state": weekly[1], "state_label": weekly[2], "extra": 1}
    return {
        "score": daily[0], "state": daily[1], "state_label": daily[2],
        "as_of_label": "live 09:41", "generated_at_iso": "2026-09-24T13:41:00Z",
        "drivers": ["Trend: SPY above its 50-day", "VIX 17 — calm"],
        "weekly": wk,
        "next_day_outlook": {
            "bias": daily[1], "label": "Mixed tape — reduced-exposure band",
            "note": "Daily gauge 60 (caution) · weekly 84 (constructive).",
            "watch": ["Daily and weekly gauges disagree — the weekly trend is intact while "
                      "the daily reads caution.", "CPI in 3 days"],
        },
        "exposure_band": {"low": 25, "high": 50},
        "disclaimer": "Educational market-health read, not a forecast.",
    }


def _sector(group, rel_1d, rel_5d, rel_21d, names=("LEAD",), day_tag=None):
    return {"group": group, "n_full": 40, "rel_1d": rel_1d, "rel_5d": rel_5d,
            "rel_21d": rel_21d, "pct_positive_1d": 55.0,
            "names": [{"symbol": n} for n in names], "day_tag": day_tag}


def _index():
    """Pooled scale of six groups: A (5.0) hot, B (1.0) neutral, C (-3.0) cold.
    Sorted: [-3, 0, 1, 2, 3, 5] → A 100th pctl, B 50th, C 16.7th."""
    payload = {
        "as_of": "2026-09-23", "benchmark": {"symbol": "RSP"},
        "sectors": [{"group": "A", "rel_5d": 5.0, "n": 40},
                    {"group": "B", "rel_5d": 1.0, "n": 40},
                    {"group": "C", "rel_5d": -3.0, "n": 40}],
        "industries": [{"group": "X", "rel_5d": 0.0, "n": 20},
                       {"group": "Y", "rel_5d": 2.0, "n": 20},
                       {"group": "Z", "rel_5d": 3.0, "n": 20}],
    }
    return heat.build_index(payload), payload


TAG = {"date": "2026-09-23", "bull": "Orders beat.", "bear": "Guidance cut.", "read_by": "model-x"}


def _body(rows=None, d1=None):
    body = {"as_of": "2026-09-23", "benchmark": "RSP",
            "sectors": rows if rows is not None else [
                _sector("A", -0.4, 5.0, 6.0, day_tag=TAG),
                _sector("B", 0.2, 1.0, 0.0),
                _sector("C", 0.9, -3.0, -2.0),
            ]}
    if d1 is not None:
        body[H.D1_KEY] = d1
    return body


# ── market_word ─────────────────────────────────────────────────────────────
def test_market_word_maps_the_three_gauge_states():
    assert NT.market_word("constructive") == "bullish"
    assert NT.market_word("caution") == "mixed"
    assert NT.market_word("risk_off") == "bearish"


@pytest.mark.parametrize("bad", [None, "", "Caution", "bullish", 123, [], {"a": 1}, "risk-off"])
def test_market_word_anything_else_is_unknown_never_raises(bad):
    assert NT.market_word(bad) == "unknown"


def test_market_word_keys_are_exactly_the_gauge_states():
    assert set(NT.MARKET_WORD) == set(market_gauge.EXPOSURE) == {"constructive", "caution", "risk_off"}


def test_market_word_map_is_one_literal_line():
    assert ('MARKET_WORD = {"constructive": "bullish", "caution": "mixed", "risk_off": "bearish"}'
            in SRC)


# ── leg_word ────────────────────────────────────────────────────────────────
def test_leg_word_signs():
    assert NT.leg_word(0.3) == "bullish"
    assert NT.leg_word(-0.01) == "bearish"
    assert NT.leg_word(0) == "flat"
    assert NT.leg_word(0.0) == "flat"


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "abc", True, [], {}])
def test_leg_word_unreadable_is_unknown(bad):
    assert NT.leg_word(bad) == "unknown"


# ── verdict_block ───────────────────────────────────────────────────────────
def test_verdict_block_daily_and_weekly_words_and_disagreement():
    v = NT.verdict_block(_gauge())
    assert v["ok"] is True
    assert v["daily"] == {"score": 60, "state": "caution", "state_label": "Caution", "word": "mixed"}
    assert v["weekly"] == {"score": 84, "state": "constructive", "state_label": "Constructive",
                           "word": "bullish"}
    assert v["agree"] is False
    # served sentences travel verbatim
    assert v["outlook"]["watch"] == _gauge()["next_day_outlook"]["watch"]
    assert v["outlook"]["label"] == "Mixed tape — reduced-exposure band"
    assert v["drivers"] == _gauge()["drivers"]
    assert v["disclaimer"] == _gauge()["disclaimer"]
    assert v["as_of_label"] == "live 09:41"
    # sizing flavour is not carried (spec §7.8)
    assert "exposure_band" not in v


def test_verdict_block_agree_true_when_states_match():
    v = NT.verdict_block(_gauge(daily=(80, "constructive", "Constructive")))
    assert v["agree"] is True
    assert v["daily"]["word"] == v["weekly"]["word"] == "bullish"


def test_verdict_block_weekly_none_means_agree_none():
    v = NT.verdict_block(_gauge(weekly=None))
    assert v["ok"] is True
    assert v["weekly"] is None
    assert v["agree"] is None


@pytest.mark.parametrize("bad", [None, {}, "gauge", []])
def test_verdict_block_unavailable(bad):
    v = NT.verdict_block(bad)
    assert v == {"ok": False, "reason": "market gauge unavailable"}


def test_verdict_block_unknown_state_word_is_unknown_not_invented():
    v = NT.verdict_block(_gauge(daily=(50, "Caution", "Caution")))
    assert v["daily"]["word"] == "unknown"


# ── macro_block (C1) ────────────────────────────────────────────────────────
def _cal():
    ev = [
        {"date": "2026-09-24", "kind": "claims", "tier": 2, "label": "Jobless claims"},
        {"date": "2026-09-24", "kind": "fomc", "tier": 1, "label": "FOMC decision"},
        {"date": "2026-09-24", "kind": "housing", "tier": 3, "label": "Housing starts"},
        {"date": "2026-10-01", "kind": "claims", "tier": 2, "label": "Jobless claims"},
        {"date": "2026-10-02", "kind": "jobs", "tier": 1, "label": "Jobs report"},
        {"date": "2026-10-08", "kind": "claims", "tier": 2, "label": "Jobless claims"},
        {"date": "2026-10-14", "kind": "cpi", "tier": 1, "label": "CPI"},          # day 20
        {"date": "2026-10-15", "kind": "claims", "tier": 2, "label": "Jobless claims"},  # day 21
    ]
    return {"days": 14, "macro": ev, "tier_labels": dict(macro_calendar.TIER_LABELS),
            "next_tier1": ev[1], "disclaimer": "A heads-up — not a forecast or advice."}


@pytest.fixture
def cal_recorder(monkeypatch):
    calls = []

    def rec(*args, **kwargs):
        calls.append((args, kwargs))
        return _cal()

    monkeypatch.setattr(macro_calendar, "get_macro_calendar", rec)
    monkeypatch.setattr(macro_calendar, "_today_et", lambda: dt.date(2026, 9, 24))
    return calls


def test_macro_block_t1_t2_only_sorted_and_labelled(cal_recorder):
    m = NT.macro_block()
    assert m["ok"] is True
    assert m["days"] == macro_calendar.DEFAULT_DAYS
    got = [(e["date"], e["kind"], e["tier"]) for e in m["events"]]
    assert got == [("2026-09-24", "fomc", 1), ("2026-09-24", "claims", 2),
                   ("2026-10-01", "claims", 2), ("2026-10-02", "jobs", 1),
                   ("2026-10-08", "claims", 2)]
    assert {e["tier"] for e in m["events"]} <= {1, 2}
    for e in m["events"]:
        assert e["tier_label"] == macro_calendar.TIER_LABELS[e["tier"]]
    keys = [(e["days_until"], e["tier"]) for e in m["events"]]
    assert keys == sorted(keys)
    assert m["events"][0]["when_label"] == "today"
    assert m["next_tier1"]["kind"] == "fomc"
    assert m["tier_labels"] == {"1": "Market movers", "2": "Trend shapers", "3": "Context"}
    assert m["disclaimer"].startswith("A heads-up")


def test_macro_block_never_passes_a_window_to_the_calendar(cal_recorder):
    NT.macro_block()
    assert cal_recorder, "the calendar was never read"
    for args, kwargs in cal_recorder:
        assert args == () and kwargs == {}, f"C1 defect: calendar called with {args} {kwargs}"


def test_macro_block_event_beyond_default_days_absent(cal_recorder):
    kinds_dates = {(e["kind"], e["date"]) for e in NT.macro_block()["events"]}
    assert ("cpi", "2026-10-14") not in kinds_dates
    assert ("claims", "2026-10-15") not in kinds_dates
    assert ("housing", "2026-09-24") not in kinds_dates          # tier 3


def test_macro_block_raising_calendar_soft_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("fred down")
    monkeypatch.setattr(macro_calendar, "get_macro_calendar", boom)
    m = NT.macro_block()
    assert m["ok"] is False
    assert m["events"] == []
    assert m["reason"]


# ── d1_block (C5) ───────────────────────────────────────────────────────────
def test_d1_block_carries_five_keys_never_moves():
    body = {H.D1_KEY: {"live": True, "basis": "live", "as_of": "09:41", "reason": None,
                       "market_closed": None, "moves": {"AAA": 1.2}, "symbols": 900}}
    d = NT.d1_block(body)
    assert d == {"live": True, "basis": "live", "as_of": "09:41", "reason": None,
                 "market_closed": None}
    assert "moves" not in d


def test_d1_block_missing_is_last_close_with_reason():
    d = NT.d1_block({"sectors": []})
    assert d["live"] is False
    assert d["basis"] is None
    assert d["reason"] == "no day block served"


@pytest.mark.parametrize("live", ["yes", 1, "true", None])
def test_d1_block_live_is_strict_bool(live):
    d = NT.d1_block({H.D1_KEY: {"live": live, "basis": "close"}})
    assert d["live"] is False


def test_d1_block_non_dict_body():
    assert NT.d1_block(None)["live"] is False
    assert NT.d1_block({H.D1_KEY: "live"})["reason"] == "no day block served"


# ── sector_rows ─────────────────────────────────────────────────────────────
def test_sector_rows_tones_and_leg_named_flags():
    idx, _ = _index()
    rows = NT.sector_rows(_body(), idx)
    by = {r["sector"]: r for r in rows}
    assert by["A"]["heat"]["tone"] == "hot"
    assert by["B"]["heat"]["tone"] == "neutral"
    assert by["C"]["heat"]["tone"] == "cold"
    assert by["A"]["heat"]["heat_window"] == heat.HEAT_WINDOW
    # hot AND down on the day leg
    assert by["A"]["hot_lagging_1d"] is True and by["A"]["cold_leading_1d"] is False
    # cold AND up on the day leg
    assert by["C"]["cold_leading_1d"] is True and by["C"]["hot_lagging_1d"] is False
    assert by["B"]["hot_lagging_1d"] is False and by["B"]["cold_leading_1d"] is False
    assert by["A"]["read"] == {"1d": "bearish", "5d": "bullish", "21d": "bullish"}
    assert by["B"]["read"]["21d"] == "flat"
    assert by["A"]["leader"] == "LEAD"
    assert by["A"]["n"] == 40 and by["A"]["benchmark"] == "RSP"
    # served numbers untouched
    assert by["A"]["rel_1d"] == -0.4 and by["A"]["rel_5d"] == 5.0 and by["A"]["rel_21d"] == 6.0


def test_sector_rows_keep_served_order_even_when_day_leg_disagrees():
    idx, _ = _index()
    rows = NT.sector_rows(_body(), idx)
    # C has the largest rel_1d; the served order (by rel_5d) is still A, B, C
    assert [r["sector"] for r in rows] == ["A", "B", "C"]


def test_sector_rows_day_tag_passed_through_untouched():
    idx, _ = _index()
    rows = NT.sector_rows(_body(), idx)
    assert rows[0]["day_tag"] is TAG
    assert rows[1]["day_tag"] is None


def test_sector_rows_rel_1d_none_is_unknown_and_no_flag():
    idx, _ = _index()
    rows = NT.sector_rows(_body(rows=[_sector("A", None, 5.0, 1.0), _sector("C", None, -3.0, 1.0)]), idx)
    for r in rows:
        assert r["read"]["1d"] == "unknown"
        assert r["hot_lagging_1d"] is False and r["cold_leading_1d"] is False


def test_sector_rows_rel_1d_nan_is_unknown_and_no_flag():
    idx, _ = _index()
    rows = NT.sector_rows(_body(rows=[_sector("A", float("nan"), 5.0, 1.0)]), idx)
    assert rows[0]["read"]["1d"] == "unknown"
    assert rows[0]["hot_lagging_1d"] is False


def test_sector_rows_rel_1d_zero_is_flat_and_no_flag():
    idx, _ = _index()
    rows = NT.sector_rows(_body(rows=[_sector("A", 0.0, 5.0, 1.0), _sector("C", 0.0, -3.0, 1.0)]), idx)
    for r in rows:
        assert r["read"]["1d"] == "flat"
        assert r["hot_lagging_1d"] is False and r["cold_leading_1d"] is False


def test_sector_rows_sector_absent_from_index_is_unknown_tone():
    idx, _ = _index()
    rows = NT.sector_rows(_body(rows=[_sector("Nowhere", -1.0, 9.0, 1.0)]), idx)
    assert rows[0]["heat"]["tone"] == "unknown"
    assert rows[0]["hot_lagging_1d"] is False


def test_sector_rows_empty_index_is_unknown_tone():
    rows = NT.sector_rows(_body(), {})
    assert {r["heat"]["tone"] for r in rows} == {"unknown"}
    assert not any(r["hot_lagging_1d"] or r["cold_leading_1d"] for r in rows)


def test_sector_rows_old_key_does_not_exist():
    idx, _ = _index()
    for r in NT.sector_rows(_body(), idx):
        assert "hot_lagging_today" not in r
        assert "cold_leading_today" not in r


def test_sector_rows_no_names_leader_none_and_junk_rows_skipped():
    idx, _ = _index()
    rows = NT.sector_rows(_body(rows=[_sector("A", 1.0, 5.0, 1.0, names=()), "junk", None]), idx)
    assert len(rows) == 1
    assert rows[0]["leader"] is None
    assert NT.sector_rows({}, idx) == []


# ── _sectors_leg (C8) ───────────────────────────────────────────────────────
@pytest.fixture
def sectors_env(monkeypatch):
    idx_payload = _index()[1]
    state = {"payload_calls": 0, "build_live": [], "build_index_arg": None}
    table = {"by_symbol": {"LEAD": {}}, "benchmark": {"symbol": "RSP"}}

    monkeypatch.setattr(RA, "_members_table",
                        lambda: (table, {"source": "persisted", "built_at_iso": "2026-09-23T21:00:00Z",
                                         "stale": False, "age_sec": 10}))

    def payload():
        state["payload_calls"] += 1
        return idx_payload
    monkeypatch.setattr(RA, "_members_payload", payload)

    def build_live(p, **kw):
        state["build_live"].append((p, kw))
        return _body(d1={"live": False, "basis": "close", "as_of": None,
                         "reason": "the market is closed (weekend)", "market_closed": "weekend",
                         "moves": {"LEAD": 1.0}})
    monkeypatch.setattr(H, "build_live", build_live)

    def latest_within(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(SNT, "latest_within", latest_within)

    real = heat.build_index

    def build_index(p):
        state["build_index_arg"] = p
        return real(p)
    monkeypatch.setattr(heat, "build_index", build_index)
    state["table"] = table
    state["base"] = idx_payload
    return state


def test_sectors_leg_reads_payload_once_and_wraps_the_tag_attach(sectors_env):
    b = NT._sectors_leg()
    assert b["ok"] is True
    assert sectors_env["payload_calls"] == 1
    assert sectors_env["build_index_arg"] is sectors_env["base"]
    # the tag read raised → every row carries day_tag None (the route's own fallback)
    # (rows came with day_tag set in the fixture body for A; setdefault keeps it)
    assert [r["day_tag"] for r in b["rows"]][1:] == [None, None]
    p, kw = sectors_env["build_live"][0]
    assert p[T.MEMBERS_KEY] is sectors_env["table"]
    assert kw == {"sort": H.DEFAULT_SORT, "direction": H.DEFAULT_DIR,
                  "names_per_group": 1, "basis": H.D1_CLOSE}
    assert b["d1"]["live"] is False and b["d1"]["market_closed"] == "weekend"
    assert "moves" not in b["d1"]
    assert b["ranked_by"] == H.DEFAULT_SORT
    assert b["heat_window"] == heat.HEAT_WINDOW
    assert b["study"] is NT.SECTOR_STUDY
    assert b["source"] == "persisted" and b["stale"] is False
    assert [r["sector"] for r in b["rows"]] == ["A", "B", "C"]
    assert b["rows"][0]["heat"]["tone"] == "hot"


def test_sectors_leg_attach_failure_sets_day_tag_none_on_rows_without_one(sectors_env, monkeypatch):
    def build_live(p, **kw):
        body = _body()
        for s in body["sectors"]:
            s.pop("day_tag", None)
        return body
    monkeypatch.setattr(H, "build_live", build_live)
    b = NT._sectors_leg()
    assert all("day_tag" in r and r["day_tag"] is None for r in b["rows"])
    assert b["tags_date"] is None


def test_sectors_leg_tags_date_from_attached_tags(sectors_env, monkeypatch):
    monkeypatch.setattr(SNT, "latest_within", lambda *a, **k: {"A": TAG})
    b = NT._sectors_leg()
    assert b["rows"][0]["day_tag"] == TAG
    assert b["rows"][1]["day_tag"] is None
    assert b["tags_date"] == "2026-09-23"


def test_sectors_leg_no_member_table_never_builds(sectors_env, monkeypatch):
    monkeypatch.setattr(RA, "_members_table", lambda: (None, {"reason": "x"}))
    b = NT._sectors_leg()
    assert b == {"ok": False, "reason": "x", "rows": []}
    assert sectors_env["build_live"] == []
    assert sectors_env["payload_calls"] == 0


def test_sectors_leg_no_member_table_no_reason(sectors_env, monkeypatch):
    monkeypatch.setattr(RA, "_members_table", lambda: (None, {}))
    assert NT._sectors_leg()["reason"] == "member table unavailable"


# ── SECTOR_STUDY source guard ───────────────────────────────────────────────
def test_sector_study_numbers_are_the_docs_numbers():
    doc = open(HEAT_DOC, encoding="utf-8").read().replace("−", "-")
    for tok in ("-0.57", "-1.87", "0.71", "-2.55", "-4.48", "-0.65", "50,191", "2,243", "192 dates"):
        assert tok in doc, tok
    s = NT.SECTOR_STUDY
    assert (s["hot_win_rate_pp"], s["hot_win_rate_ci"]) == (-0.57, [-1.87, 0.71])
    assert (s["hot_minus_cold_5d_pp"], s["hot_minus_cold_5d_ci"]) == (-2.55, [-4.48, -0.65])
    assert (s["arrivals"], s["dates"], s["names"]) == (50191, 192, 2243)
    note = s["note"].replace("−", "-")
    for tok in ("-0.57pp", "-1.87", "+0.71", "-2.55pp", "-4.48", "-0.65", "50,191"):
        assert tok in note, tok


def test_sector_study_shipped_on_is_the_heat_key_and_unmeasured():
    s = NT.SECTOR_STUDY
    assert s["shipped_on"] == heat.HEAT_KEY
    assert s["measured_on"] == "rel_21d"
    assert "UNMEASURED" in s["note"]
    assert "95% CI" in s["note"]
    assert s["script"] in s["note"]
    assert os.path.exists(os.path.join(os.path.dirname(BACKEND), s["script"]))
    assert os.path.exists(os.path.join(os.path.dirname(BACKEND), s["doc"]))


def test_sector_study_note_says_reversal_language_never_bounce():
    assert re.search(r"\bbounce\b", NT.SECTOR_STUDY["note"], re.I) is None
    assert re.search(r"\bbounce\b", NT.NOTE, re.I) is None


# ── headlines_block ─────────────────────────────────────────────────────────
def test_headlines_block_trims_core_result():
    res = {"items": [{"title": "Stocks rise", "url": "https://x", "source": "Wire",
                      "summary": "long text", "published": 1790000000.0, "provider": "google"},
                     "junk"],
           "selector": {"kind": "keyword"}, "query": "q", "window_hours": 36,
           "fetched_at": 1790000100.0, "counts": {"raw": 2}}
    h = NT.headlines_block(res)
    assert h["ok"] is True
    assert h["items"] == [{"title": "Stocks rise", "url": "https://x", "source": "Wire",
                           "published": 1790000000.0, "provider": "google"}]
    assert h["window_hours"] == 36 and h["query"] == "q" and h["counts"] == {"raw": 2}
    assert "selector" not in h


def test_headlines_block_empty_is_ok_with_no_items():
    h = NT.headlines_block({"items": []})
    assert h["ok"] is True and h["items"] == []


@pytest.mark.parametrize("bad", [None, "x", []])
def test_headlines_block_none_is_not_ok(bad):
    h = NT.headlines_block(bad)
    assert h["ok"] is False and h["items"] == []


def test_news_leg_uses_the_one_routine_with_the_market_query(monkeypatch):
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return {"items": [], "window_hours": 36}
    monkeypatch.setattr(NT.core, "search_sync", fake)
    assert NT._news_leg()["ok"] is True
    assert seen == {"keyword": NT.MARKET_QUERY, "audit": NT.AUDIT_TAG}


# ── build (C6) ──────────────────────────────────────────────────────────────
LEGS = ("_gauge_leg", "_macro_leg", "_sectors_leg", "_news_leg")
BLOCKS = ("verdict", "macro", "sectors", "headlines")


@pytest.fixture
def quick_legs(monkeypatch):
    for leg, block in zip(LEGS, BLOCKS):
        monkeypatch.setattr(NT, leg, (lambda b: (lambda: {"ok": True, "which": b}))(block))


def _run(coro):
    async def timed():
        t0 = time.monotonic()
        out = await coro
        return out, time.monotonic() - t0
    return asyncio.run(timed())


def test_build_all_legs_present(quick_legs):
    out, _ = _run(NT.build())
    for b in BLOCKS:
        assert out[b] == {"ok": True, "which": b}
    assert out["budget_sec"] == NT.LEG_BUDGET_SEC
    assert out["measured"] is False
    assert out["note"] == NT.NOTE


@pytest.mark.parametrize("i", range(4))
def test_build_one_leg_raising_costs_only_its_block(quick_legs, monkeypatch, i):
    def boom():
        raise RuntimeError("leg exploded")
    monkeypatch.setattr(NT, LEGS[i], boom)
    out, _ = _run(NT.build())
    assert out[BLOCKS[i]] == {"ok": False, "reason": "leg exploded"}
    for j, b in enumerate(BLOCKS):
        if j != i:
            assert out[b]["ok"] is True


def test_build_empty_exception_message_still_has_a_reason(quick_legs, monkeypatch):
    def boom():
        raise KeyError
    monkeypatch.setattr(NT, "_gauge_leg", boom)
    out, _ = _run(NT.build())
    assert out["verdict"]["ok"] is False and out["verdict"]["reason"]


@pytest.mark.parametrize("i", range(4))
def test_build_each_leg_past_budget_times_out_alone(quick_legs, monkeypatch, i):
    monkeypatch.setattr(NT, "LEG_BUDGET_SEC", 0.05)

    def slow():
        time.sleep(0.6)
        return {"ok": True, "which": "late"}
    monkeypatch.setattr(NT, LEGS[i], slow)
    out, took = _run(NT.build())
    assert took < 0.5, took
    assert out[BLOCKS[i]] == {"ok": False, "reason": NT.TIMED_OUT.format(0.05)}
    assert "refresh" in out[BLOCKS[i]]["reason"]
    for j, b in enumerate(BLOCKS):
        if j != i:
            assert out[b] == {"ok": True, "which": b}


def test_endpoint_direct_call_scrubs_nan_and_serves_budget(monkeypatch):
    g = _gauge()
    g["score"] = float("nan")
    monkeypatch.setattr(NT, "_gauge_leg", lambda: NT.verdict_block(g))
    monkeypatch.setattr(NT, "_macro_leg", lambda: {"ok": True, "days": 14, "events": []})
    monkeypatch.setattr(NT, "_sectors_leg", lambda: {"ok": True, "rows": [
        {"sector": "A", "rel_1d": float("nan"), "rel_5d": float("inf")}]})
    monkeypatch.setattr(NT, "_news_leg", lambda: {"ok": True, "items": []})
    resp = asyncio.run(CM_API.chart_maps_news())
    assert resp.status_code == 200
    raw = resp.body.decode()
    assert "NaN" not in raw and "Infinity" not in raw
    body = json.loads(raw)
    assert body["budget_sec"] == NT.LEG_BUDGET_SEC
    assert body["verdict"]["daily"]["score"] is None
    assert body["verdict"]["daily"]["word"] == "mixed"
    assert body["sectors"]["rows"][0]["rel_1d"] is None


def test_endpoint_takes_no_parameters():
    import inspect
    assert list(inspect.signature(CM_API.chart_maps_news).parameters) == []


# ── AST / source guards ─────────────────────────────────────────────────────
BANNED = {"alert_gates", "trading", "push", "zone_edge_entry"}


def _imported_modules() -> set:
    out = set()
    for n in ast.walk(TREE):
        if isinstance(n, ast.Import):
            for a in n.names:
                out |= set(a.name.split("."))
        elif isinstance(n, ast.ImportFrom):
            out |= set((n.module or "").split("."))
            out |= {a.name for a in n.names}
    return out


def test_module_imports_nothing_that_gates_trades_or_pushes():
    assert _imported_modules() & BANNED == set()


def test_module_never_says_bounce():
    assert re.search(r"\bbounce\b", SRC, re.I) is None


def test_module_never_passes_a_days_kwarg():
    # C1 regression: `within_days=` is the imminent_events window (the default
    # key's doc, no recompute) and is allowed; a bare `days=` is not.
    assert re.search(r"\bdays\s*=", SRC) is None
    for n in ast.walk(TREE):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name == "get_macro_calendar":
                assert n.args == [] and n.keywords == []


def test_module_carries_one_budget_constant():
    assert "LEG_BUDGET_SEC" in SRC and "MACRO_BUDGET_SEC" not in SRC


# ── enterable mirror ────────────────────────────────────────────────────────
def test_news_tab_is_na_in_both_halves_of_the_mirror():
    assert EN.KIND_BY_TAB["news"] == EN.KIND_NA
    with open(MIRROR) as fh:
        fix = json.load(fh)
    assert fix["kind_by_tab"]["news"] == "n/a"
    assert fix["kind_by_tab"] == EN.KIND_BY_TAB
