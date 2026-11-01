"""chart_maps/luk/screens.py — 🥇 his three screens (spec §3.6): strict boundaries as his frames read, cap unknown KEPT,
deferred daily facts KEPT and counted, the third need_text (C12), sorted by the served key only, the shortlist cap."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from chart_maps.luk import constants as LC
from chart_maps.luk import daily as DA
from chart_maps.luk import screens as SC

ET = ZoneInfo("America/New_York")
ISO = "2026-11-02"


def ns(d, hh, mm):
    return int(datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).timestamp() * 1e9)


def snap(price=20.0, open_=19.0, change=5.0, prev=18.0, print_at=None, print_px=None):
    return {"open": open_, "high": 21.0, "low": 18.5, "close": price, "volume": 1e6, "change_pct": change,
            "prev_day_close": prev, "last_trade_price": print_px if print_px is not None else price,
            "last_trade_ts_ms": print_at if print_at is not None else ns(date(2026, 11, 2), 11, 0)}


def facts(**over):
    f = {k: None for k in DA.FACT_KEYS}
    f.update({"close": 18.0, "ema9": 17.5, "ema21": 17.0, "ema50": 15.0, "ema150": 12.0, "adr20_pct": 6.2,
              "avg_vol_10d": 2e6, "px_vol": 9e7, "px_vol_1w": 5e8, "vol_1w_pct": 5.0, "perf_1m_pct": 30.0,
              "tier": "lead", "n_bars": 200, "as_of": "2026-10-30"})
    f.update(over)
    return f


def row(sym="AAA", snap_kw=None, cap=2e9, **fkw):
    return SC.row_of(sym, snap(**(snap_kw or {})), facts(**fkw), cap, ISO)


def oks(key, r):
    return {c["key"]: c["ok"] for c in SC.criteria(key, r)}


# ── boundary pairs (his frames read ">") ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("cap,ok", [(100_000_000, False), (100_000_001, True)])
def test_cap_boundary(cap, ok):
    assert LC.LUK_SCREEN_MIN_CAP_USD == 100_000_000
    r = row(cap=cap)
    for key in SC.SCREENS:
        assert oks(key, r)["cap"] is ok
    assert bool(SC.leader([r])) is ok


@pytest.mark.parametrize("v,ok", [(500_000, False), (500_001, True)])
def test_avg_vol_boundary(v, ok):
    r = row(avg_vol_10d=v)
    assert oks("premarket", r)["avg_vol_10d"] is ok and oks("leader", r)["avg_vol_10d"] is ok


@pytest.mark.parametrize("v,ok", [(3.5, False), (3.51, True)])
def test_vol_1w_boundary(v, ok):
    r = row(vol_1w_pct=v)
    assert oks("premarket", r)["vol_1w_pct"] is ok and oks("potent", r)["vol_1w_pct"] is ok


@pytest.mark.parametrize("v,ok", [(50e6, False), (50e6 + 1, True)])
def test_px_vol_boundary(v, ok):
    r = row(px_vol=v)
    assert oks("premarket", r)["px_vol"] is ok and oks("potent", r)["px_vol"] is ok


@pytest.mark.parametrize("v,ok", [(300e6, False), (300e6 + 1, True)])
def test_px_vol_1w_boundary(v, ok):
    assert oks("leader", row(px_vol_1w=v))["px_vol_1w"] is ok


@pytest.mark.parametrize("pct,ok", [(0.5, False), (0.51, True), (-0.5, False), (-0.51, True)])
def test_chg_from_open_band(pct, ok):
    price = round(20.0 * (1 + pct / 100), 6)
    r = row(snap_kw={"price": price, "open_": 20.0})
    assert r["chg_from_open_pct"] == pytest.approx(pct)
    assert oks("potent", r)["chg_from_open"] is ok


def test_price_equal_ema21_passes_equal_ema50_fails():
    r = row(snap_kw={"price": 17.0}, ema21=17.0, ema50=15.0)
    assert oks("potent", r)["price_vs_ema21"] is True
    r = row(snap_kw={"price": 15.0}, ema21=14.0, ema50=15.0)
    assert oks("potent", r)["price_vs_ema50"] is False


# ── the unknowns ───────────────────────────────────────────────────────────────────────────────────────────────
def test_cap_unknown_is_kept_with_the_served_text():
    r = row(cap=None)
    assert r["cap_text"] == "cap unknown — not filtered"
    for key in SC.SCREENS:
        c = next(c for c in SC.criteria(key, r) if c["key"] == "cap")
        assert c["ok"] is None and c["need_text"] == "cap unknown — not filtered"
    assert [x["symbol"] for x in SC.leader([r])] == ["AAA"], "NEGATIVE: no row is dropped by an unknown cap"


def test_C12_no_regular_session_open_yet():
    r = row(snap_kw={"open_": 0})
    c = next(c for c in SC.criteria("potent", r) if c["key"] == "chg_from_open")
    assert c["ok"] is False and c["need_text"] == "no regular-session open yet"
    assert c["need_text"] != SC.NO_DAILY_TEXT
    assert SC.potent([r]) == []
    assert row(snap_kw={"open_": None})["chg_from_open_pct"] is None


def test_none_fact_fails_with_no_daily_bars_cached():
    r = SC.row_of("AAA", snap(), None, 2e9, ISO)
    c = next(c for c in SC.criteria("leader", r) if c["key"] == "avg_vol_10d")
    assert c["ok"] is False and c["need_text"] == "no daily bars cached"
    assert SC.leader([r]) == []


def test_C2_deferred_daily_facts_rows_are_kept_and_counted():
    r = SC.row_of("AAA", snap(), DA.pending(), 2e9, ISO)
    assert r["daily_pending"] is True and r["pending_text"] == DA.PENDING_TEXT
    for key in SC.SCREENS:
        daily = [c for c in SC.criteria(key, r) if c["key"] not in ("cap", "chg_from_open")]
        assert daily and all(c["ok"] is None and c["need_text"] == DA.PENDING_TEXT for c in daily), key
    assert [x["symbol"] for x in SC.leader([r])] == ["AAA"], "KEPT"
    facts_slot = DA.pending()
    assert not facts_slot, "counted in not_screened (falsy facts)"


def test_premarket_print_dated_yesterday_is_no_pm_change():
    today = SC.row_of("AAA", snap(print_at=ns(date(2026, 11, 2), 8, 0), print_px=19.8, prev=18.0), facts(), 2e9, ISO)
    assert today["pm_chg_pct"] == pytest.approx((19.8 / 18.0 - 1) * 100)
    stale = SC.row_of("AAA", snap(print_at=ns(date(2026, 10, 30), 8, 0), print_px=19.8), facts(), 2e9, ISO)
    assert stale["pm_chg_pct"] is None
    rth = SC.row_of("AAA", snap(print_at=ns(date(2026, 11, 2), 10, 0)), facts(), 2e9, ISO)
    assert rth["pm_chg_pct"] is None
    assert SC.premarket([stale, rth]) == [] and SC.no_premarket_n([stale, rth, today]) == 2


# ── sorting and the cut ───────────────────────────────────────────────────────────────────────────────────────
def test_each_screen_sorts_by_its_served_key_only():
    a = row("AAA", snap_kw={"change": 3.0}, perf_1m_pct=10.0, cap=9e11)
    b = row("BBB", snap_kw={"change": 9.0}, perf_1m_pct=50.0, cap=2e8)
    c = row("CCC", snap_kw={"change": 6.0}, perf_1m_pct=30.0, cap=5e9)
    assert [r["symbol"] for r in SC.leader([a, b, c])] == ["BBB", "CCC", "AAA"]
    assert [r["symbol"] for r in SC.potent([a, b, c])] == ["BBB", "CCC", "AAA"]
    out = SC.leader([a, b, c])
    assert [r["rank"] for r in out] == [1, 2, 3] and all("criteria" in r for r in out)


def test_premarket_sorts_by_pm_change():
    rows = [SC.row_of(s, snap(print_at=ns(date(2026, 11, 2), 8, 0), print_px=px, prev=10.0), facts(), 2e9, ISO)
            for s, px in (("AAA", 11.0), ("BBB", 13.0), ("CCC", 12.0))]
    assert [r["symbol"] for r in SC.premarket(rows)] == ["BBB", "CCC", "AAA"]


def test_top_n_cut():
    rows = [row(f"S{i:03d}", snap_kw={"change": float(i)}) for i in range(LC.LUK_SCREEN_TOP_N + 5)]
    out = SC.potent(rows)
    assert len(out) == LC.LUK_SCREEN_TOP_N and out[0]["symbol"] == f"S{LC.LUK_SCREEN_TOP_N + 4:03d}"


def test_shortlist_union_order_and_cap():
    lists = {"premarket": [{"symbol": "AAA", "chg_pct": 5.0}], "leader": [{"symbol": "BBB", "chg_pct": -9.0}],
             "potent": [{"symbol": "AAA", "chg_pct": 5.0}, {"symbol": "CCC", "chg_pct": 5.0}]}
    names, capped = SC.shortlist(lists, {"ZZZ"})
    assert names == ["BBB", "AAA", "CCC", "ZZZ"] and capped == 0
    many = {"potent": [{"symbol": f"S{i:03d}", "chg_pct": float(i)} for i in range(LC.LUK_SHORTLIST_MAX + 7)]}
    names, capped = SC.shortlist(many, set())
    assert len(names) == LC.LUK_SHORTLIST_MAX and capped == 7 and names[0] == f"S{LC.LUK_SHORTLIST_MAX + 6:03d}"


def test_titles_built_from_the_constants():
    t = SC.titles()
    assert "cap > $100M" in t["premarket"] and "> 3.5%" in t["premarket"] and "500K" in t["premarket"]
    assert "$300M" in t["leader"] and "±0.5%" in t["potent"] and "≥ 21 EMA" in t["potent"]
    for s in t.values():
        assert "boun" not in s.lower() and "edge" not in s.lower()


def test_row_carries_facts_tier_and_chips():
    r = row(cap=1.2e9)
    assert r["cap_text"] == "$1.2B" and r["tier_text"].startswith("Lead")
    assert r["small_cap_text"] and "ADR 6.2%" in r["adr_text"] and r["adr_pref_ok"] is True
    assert all(k in r for k in DA.FACT_KEYS)
