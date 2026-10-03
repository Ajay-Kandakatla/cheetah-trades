"""📉 Down 40%+ tab on Chart Maps (2026-10-02) — spec §3.1-§3.7, WP-BE tests 1-25.

Ajay 2026-10-02: "Can you build me a tab in chart maps about stocks that
dropped more than 40% lowers from like app loving company as an example whcih
si 60% low. But I also need you to capture informations about sales like
Bondes and other indicators based on Bondes formula please." then "Scan the
universe and bring me these stocks" and "also add things like possible
catalyst that made is drop like that."

Pins `chart_maps/fallen_tab.py` (the closed read, the held-out classes, the
Bonde block, the orders, the memo, the words) and the board wiring
(`fallen_tiles`, the tab-scoped sorts, the depth view, the api coercion).
Positive AND negative cases. Hermetic: the conftest refuses Mongo, every reader
is injected, no thread is started (`_spawn` is patched), no network.
"""
from __future__ import annotations

import ast
import asyncio
import io
import re
import tokenize
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import board as BOARD
from chart_maps import dual_momentum_tab as DMT
from chart_maps import fallen_catalysts as FC
from chart_maps import fallen_tab as FAL
from sepa import bonde as BD
from sepa import bonde_picks as BP
from sepa import buyable_verdict as BV
from sepa import prices, symbols
from sepa import qoq as Q
from supply_demand import key_levels as KL

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]

NOW = datetime(2026, 10, 2, 21, 0, tzinfo=ET)          # Friday, after the 20:00 roll
SESSION = date(2026, 10, 5)                             # -> the next market day
LAST = "2026-10-02"
NOW_RTH = datetime(2026, 10, 2, 11, 0, tzinfo=ET)       # same Friday, mid-session


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _market_days(end: str, n: int) -> list:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


DAYS = [d.date().isoformat() for d in _market_days(LAST, 400)]


def _ago(n: int) -> str:
    return DAYS[-1 - n]


def _frame(n=300, *, end=LAST, close=100.0, volume=1_000_000.0, sets=None):
    idx = pd.DatetimeIndex(_market_days(end, n))
    df = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 1.0,
                       "close": close, "volume": volume}, index=idx)
    for day, vals in (sets or {}).items():
        for k, v in vals.items():
            df.loc[pd.Timestamp(day), k] = v
    return df


def _fall(df, after: str, close: float, *, open_=None):
    """Every bar AFTER `after` prints `close` (the first one opens at `open_`)."""
    mask = df.index > pd.Timestamp(after)
    df.loc[mask, ["open", "close"]] = close
    df.loc[mask, "high"] = close + 1.0
    df.loc[mask, "low"] = close - 1.0
    if open_ is not None:
        first = df.index[mask][0]
        df.loc[first, "open"] = open_
    return df


def _attach_stub(rows, db=None):
    for r in rows:
        BP._count(r)
    return rows


_EMPTY_READERS = {k: (lambda syms, names, db: {}) for k in FC.PRIORITY}
_EMPTY_READERS["frames"] = lambda syms: {}


def _cats(reads, **kw):
    return FC.attach_all(reads, readers=_EMPTY_READERS, **kw)


def _build(frames, *, scan=None, attach=None, caps=None, profiles=None, cats=None,
           session=SESSION):
    return FAL.build("full", session, universe_fn=lambda u: list(frames),
                     frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                     scan_fn=lambda: {"all_results": list(scan or []),
                                      "generated_at": "2026-10-02T18:19:48-04:00"},
                     scan_key_fn=lambda: (1, 2), attach_fn=attach or _attach_stub,
                     caps_fn=lambda syms, closes: dict(caps or {}),
                     profiles_fn=lambda syms: dict(profiles or {}),
                     catalysts_fn=cats or _cats)


def _scan_row(sym, *, periods=(8105, 8104, 8103, 8102, 8101, 8100), rev=None, sector="Technology",
              growth=52.8, is_etf=False):
    rev = rev or [380_000_000, 364_000_000, 330_000_000, 300_000_000, 248_700_000, 240_000_000]
    return {"symbol": sym, "name": f"{sym} Corp", "sector": sector, "last_close": 271.73,
            "is_etf": is_etf, "liquidity": {"avg_dollar_vol": 2.5e9},
            "fundamentals": {"rev_q_series": list(rev),
                             "eps_q_series": [1.20, 1.10, 0.95, 0.80, 0.50, 0.45],
                             "q_period_series": list(periods),
                             "sales": {"score": 80, "growth_yoy_pct": growth,
                                       "prior_yoy_pct": 24.2, "tier": "strong",
                                       "accelerating": True, "consecutive_growth_q": 4}}}


def _app_frame():
    df = _frame(close=700.0, sets={_ago(200): {"high": 738.01}, _ago(50): {"low": 212.4}})
    _fall(df, _ago(150), 271.73)
    df.loc[pd.Timestamp(_ago(50)), "low"] = 212.4
    return df


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    FAL._memo.clear()
    FAL._warming.clear()
    FAL._failures.clear()
    spawned = []
    monkeypatch.setattr(FAL, "_spawn", lambda target, name: spawned.append((target, name)))
    return spawned


# --------------------------------------------------------------------------
# 1-2 — the 52-week HIGH, never the close max
# --------------------------------------------------------------------------
def test_01_app_shape_reads_63_18_under_the_intraday_high():
    e = _build({"APP": _app_frame()})
    r = e["rows"]["APP"]
    assert r["pct_below"] == 63.18 and r["high"] == 738.01 and r["high_date"] == _ago(200)
    assert r["close"] == 271.73 and r["close_date"] == LAST
    assert r["low"] == 212.4 and r["low_date"] == _ago(50) and r["pct_above_low"] == 27.93
    assert e["counts"]["fallen"] == 1 and e["as_of"] == LAST


def test_02_NEG_the_high_column_is_used_not_the_close_max():
    df = _frame(sets={_ago(100): {"close": 150.0, "high": 151.0},
                      _ago(120): {"high": 200.0}})
    st, rd = FAL.classify("HIX", df, None, set(), SESSION)
    assert st == "fallen" and rd["high"] == 200.0 and rd["high_date"] == _ago(120)
    assert rd["pct_below"] == 50.0
    # the trend-template close max (150) would have read 33.33% — under the line
    assert round((1 - 100.0 / float(df["close"].max())) * 100, 2) < FAL.THRESHOLD_PCT


# --------------------------------------------------------------------------
# 3-8 — closed bars, boundary, held-out classes
# --------------------------------------------------------------------------
def test_03_NEG_an_in_progress_bar_never_lists_a_name_and_counts_after_the_roll():
    df = _frame(sets={_ago(30): {"high": 120.0}})
    df.loc[pd.Timestamp(LAST), ["open", "close", "low"]] = [60.0, 60.0, 59.0]
    rth_session = KL.levels_session(NOW_RTH)
    assert rth_session == date(2026, 10, 2)
    st, rd = FAL.classify("LIVE", df, None, set(), rth_session)
    assert st == "under_threshold" and rd["close_date"] == _ago(1) and rd["close"] == 100.0
    st2, rd2 = FAL.classify("LIVE", df, None, set(), KL.levels_session(NOW))
    assert st2 == "fallen" and rd2["close_date"] == LAST and rd2["pct_below"] == 50.0


def test_04_boundary_39_99_is_out_and_40_00_is_in():
    a = _frame(close=60.01, sets={_ago(10): {"high": 100.0}})
    b = _frame(close=60.0, sets={_ago(10): {"high": 100.0}})
    sa, ra = FAL.classify("AAA", a, None, set(), SESSION)
    sb, rb = FAL.classify("BBB", b, None, set(), SESSION)
    assert ra["pct_below"] == 39.99 and sa == "under_threshold"
    assert rb["pct_below"] == 40.0 and sb == "fallen"


def test_05_NEG_251_closed_bars_is_short_history():
    df = _frame(n=FAL.YEAR_BARS - 1, close=10.0, sets={_ago(10): {"high": 100.0}})
    st, rd = FAL.classify("YNG", df, None, set(), SESSION)
    assert st == "short_history" and rd["high"] is None and rd["pct_below"] is None
    assert FAL.classify("YNG", _frame(n=FAL.YEAR_BARS, close=10.0,
                                      sets={_ago(10): {"high": 100.0}}),
                        None, set(), SESSION)[0] == "fallen"


def test_06_NEG_a_last_bar_before_the_prior_market_day_is_stale():
    df = _frame(end=_ago(2), close=10.0, sets={_ago(30): {"high": 100.0}})
    assert KL.prev_market_day(SESSION).isoformat() == LAST
    st, _rd = FAL.classify("OLD", df, None, set(), SESSION)
    assert st == "stale"


def test_07_NEG_etfs_by_the_static_list_and_by_the_scan_flag(monkeypatch):
    df = _frame(close=10.0, sets={_ago(10): {"high": 100.0}})
    etfs = FAL._static_etfs()
    assert "SPY" in etfs
    assert FAL.classify("SPY", df, None, etfs, SESSION)[0] == "etf"
    assert FAL.classify("ZZET", df, {"is_etf": True}, etfs, SESSION)[0] == "etf"
    assert FAL.classify("ZZST", df, {"is_etf": False}, etfs, SESSION)[0] == "fallen"
    monkeypatch.setattr(FAL, "INCLUDE_ETFS", True)
    assert FAL.classify("SPY", df, None, etfs, SESSION)[0] == "fallen"


def test_08_NEG_a_delisted_fate_is_never_listed(monkeypatch):
    df = _frame(close=10.0, sets={_ago(10): {"high": 100.0}})
    monkeypatch.setattr(symbols, "is_delisted", lambda s: s == "DEAD")
    assert FAL.classify("DEAD", df, None, set(), SESSION)[0] == "delisted"
    assert FAL.classify("LIVE", df, None, set(), SESSION)[0] == "fallen"


# --------------------------------------------------------------------------
# 9-10 — the data-error guards
# --------------------------------------------------------------------------
def test_09_split_splice_shapes_are_held_out_and_named_the_rna_shape_is_not():
    ctva = _fall(_frame(close=77.65, sets={_ago(40): {"high": 80.0}}), _ago(11), 12.57)
    wshp = _frame(close=10.0)
    wshp.loc[wshp.index > pd.Timestamp(_ago(21)), ["open", "close"]] = 60.0
    wshp.loc[wshp.index > pd.Timestamp(_ago(21)), "high"] = 61.0
    _fall(wshp, _ago(15), 20.0)
    rna = _fall(_frame(close=100.0), _ago(9), 21.0)
    e = _build({"CTVA": ctva, "WSHP": wshp, "RNA": rna})
    assert set(e["rows"]) == {"RNA"}
    assert e["counts"]["data_suspect"] == 2
    sb = FAL.suspects_block(e["suspects"])
    assert sb["n"] == 2
    assert f"CTVA — 77.65 → 12.57 on {_ago(10)} (0.16× in one session)" in sb["lines"]
    assert any(ln.startswith("WSHP — 10.00 → 60.00") and "6.00×" in ln
               for ln in sb["lines"])
    assert 1 / 0.21 < FAL.GLITCH_RATIO                     # the guard's reach, documented
    assert e["rows"]["RNA"]["pct_below"] == round((1 - 21.0 / 101.0) * 100, 2)


def test_09b_NEG_the_named_list_is_capped_the_count_is_whole(monkeypatch):
    monkeypatch.setattr(FAL, "SUSPECT_LINES_MAX", 1)
    many = [{"symbol": f"S{i}", "date": LAST, "prev_close": 10.0, "close": 1.0, "ratio": 0.1}
            for i in range(3)]
    sb = FAL.suspects_block(many)
    assert sb["n"] == 3 and len(sb["lines"]) == 1 and sb["head"].startswith("3 names")


def test_10_NEG_the_curated_foreign_head_cut_reaches_the_read(monkeypatch):
    first = _ago(120)
    df = _frame(close=100.0)
    df.loc[df.index < pd.Timestamp(first), ["open", "close"]] = 450.0
    df.loc[df.index < pd.Timestamp(first), "high"] = 500.0
    # uncut: the old security's 500 high makes it look 80% down
    assert FAL.classify("OLDX", df, None, set(), SESSION)[0] == "fallen"
    monkeypatch.setitem(symbols.FIRST_SESSION, "OLDX", (first, "test: a reused ticker"))
    e = _build({"OLDX": df}, )
    e2 = FAL.build("full", SESSION, universe_fn=lambda u: ["OLDX"],
                   frames_fn=lambda syms: {s: prices._cut_foreign_head(df, s) for s in syms},
                   scan_fn=lambda: {}, scan_key_fn=lambda: None, attach_fn=_attach_stub,
                   caps_fn=lambda s, c: {}, profiles_fn=lambda s: {}, catalysts_fn=_cats)
    assert "OLDX" in e["rows"]                         # the test seam (no cut) lists it
    assert e2["rows"] == {} and e2["counts"]["fallen"] == 0
    assert e2["counts"]["short_history"] + e2["counts"]["under_threshold"] == 1
    src = (BACKEND / "chart_maps" / "fallen_tab.py").read_text(encoding="utf-8")
    assert "frames_fn = prices.bulk_cached_frames" in src


# --------------------------------------------------------------------------
# 11 — the counts invariant
# --------------------------------------------------------------------------
def _mixed_frames():
    base = {"sets": {_ago(10): {"high": 100.0}}}
    return {
        "FALA": _frame(close=50.0, **base),
        "FALB": _frame(close=30.0, **base),
        "THIN": _frame(close=20.0, volume=1_000.0, **base),
        "UNDR": _frame(close=90.0, **base),
        "SPY": _frame(close=10.0, **base),
        "STAL": _frame(end=_ago(3), close=10.0, **base),
        "YNG": _frame(n=100, close=10.0),
        "CTVA": _fall(_frame(close=77.65, sets={_ago(40): {"high": 80.0}}), _ago(11), 12.57),
    }


def test_11_counts_invariant_over_a_mixed_universe(monkeypatch):
    monkeypatch.setattr(symbols, "is_delisted", lambda s: s == "DEAD")
    frames = _mixed_frames()
    frames["DEAD"] = _frame(close=10.0, sets={_ago(10): {"high": 100.0}})
    e = FAL.build("full", SESSION, universe_fn=lambda u: list(frames) + ["NOBARS", "fala"],
                  frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                  scan_fn=lambda: {}, scan_key_fn=lambda: None, attach_fn=_attach_stub,
                  caps_fn=lambda s, c: {}, profiles_fn=lambda s: {}, catalysts_fn=_cats)
    c = e["counts"]
    assert c["scanned"] == len(frames) + 1                        # "fala" deduped
    assert c["scanned"] == sum(c[k] for k in FAL.STATUSES)
    assert (c["no_bars"], c["delisted"], c["etf"], c["stale"], c["short_history"],
            c["under_threshold"], c["data_suspect"], c["fallen"]) == (1, 1, 1, 1, 1, 1, 1, 3)
    rows, rc = FAL.rank(e, sort="default", depth=60)
    assert rc["at_depth"] == len(rows) == 2 and rc["at_depth"] <= rc["fallen"]
    assert {r["symbol"] for r in rows} == {"FALB", "THIN"}


# --------------------------------------------------------------------------
# 12-15 — Bonde, never retyped
# --------------------------------------------------------------------------
def _leg_attach(rows, db=None):
    for r in rows:
        r["pick"]["legs"]["surprise"] = {"ok": True, "value": 12.0, "why": None}
        BP._count(r)
    return rows


def test_12_bonde_identity_with_the_bonde_tab_row():
    row = _scan_row("APP")
    snapshot = repr(row)
    e = _build({"APP": _app_frame()}, scan=[row], attach=_leg_attach)
    got = e["rows"]["APP"]
    ref = BD._row(row, BV._bonde_pillar(row), None)
    _leg_attach([ref])
    assert got["pick"]["legs"] == ref["pick"]["legs"]
    assert (got["pick"]["n_pass"], got["pick"]["n_fail"], got["pick"]["n_unknown"]) == \
        (ref["pick"]["n_pass"], ref["pick"]["n_fail"], ref["pick"]["n_unknown"])
    assert got["growth_yoy_pct"] == ref["growth_yoy_pct"] == 52.8
    assert got["in_scan"] is True and got["scan_note"] is None and got["sector"] == "Technology"
    assert repr(row) == snapshot                                   # the shared row is untouched
    b = FAL.bonde_read(got)
    assert b["n_read"] == b["n_pass"] + got["pick"]["n_fail"]
    assert b["n_not_read"] == len(FAL.GATED_KEYS) - b["n_read"]
    assert b["line"] == (f"\U0001F4CB Bonde: {b['n_pass']} of the {b['n_read']} legs read pass "
                         f"· {b['n_not_read']} not read")
    assert len(FAL.GATED_KEYS) == len(BP.COMPUTED_KEYS) - len(BP.FACT_KEYS)


def test_13_NEG_no_scan_row_reads_only_the_cache_legs():
    e = _build({"NOSC": _frame(close=10.0, sets={_ago(10): {"high": 100.0}})},
               attach=_leg_attach, profiles={"NOSC": {"name": "Nosc Inc", "sector": "Energy"}})
    r = e["rows"]["NOSC"]
    assert r["in_scan"] is False and r["scan_note"] and e["counts"]["in_scan"] == 0
    assert set(r["pick"]["legs"]) == {"surprise"}
    assert not (set(r["pick"]["legs"]) & set(BP.SCAN_KEYS))
    assert r["sector"] == "Energy" and r["sector_source"] == "profile" and r["name"] == "Nosc Inc"
    line = FAL.bonde_line(r)
    assert line == (f"\U0001F4CB Bonde: 1 of the 1 legs read pass · the {len(BP.SCAN_KEYS)} "
                    "scan legs not read — no SEPA scan row")
    assert FAL.sales_line(r) == "Sales — not read"


def test_14_NEG_a_pair_not_a_year_apart_is_blanked_like_the_bonde_board():
    row = _scan_row("IOVA", periods=(8105, 8104, 8102, 8101, 8100, 8098))
    assert BD._pair_mismatch(row)
    part = FAL.scan_part(row)
    assert part["pair_blanked"] is True
    assert part["tier"] is None and part["growth_yoy_pct"] is None
    assert part["prior_yoy_pct"] is None and part["accelerating"] is None
    assert FAL.sales_line(part) == ("Sales — the fiscal pair is not a year apart (the Bonde "
                                    "tab blanks it too)")
    ok = FAL.scan_part(_scan_row("OKAY"))
    assert ok["pair_blanked"] is False and ok["growth_yoy_pct"] == 52.8


def test_15_sales_line_suffixes_and_qoq_only_on_a_positive_base():
    base = {"growth_yoy_pct": 52.8, "prior_yoy_pct": -4.0, "qoq_pct": 4.41,
            "qoq_base": Q.BASE_OK, "period": "FY2026 Q2", "base_state": "ok"}
    assert FAL.sales_line(base) == ("Sales +52.8% y/y · +4.4% q/q · prior −4.0% y/y "
                                    "· FY2026 Q2")
    assert "q/q" not in FAL.sales_line({**base, "qoq_base": Q.BASE_NOT_ADJACENT})
    assert "q/q" not in FAL.sales_line({**base, "qoq_base": Q.BASE_TOO_SMALL})
    small = FAL.sales_line({**base, "base_state": "too_small"})
    assert small.endswith(f"year-ago revenue under {FAL._usd(BD.MIN_MATERIAL_BASE_REV)} "
                          "— the % is arithmetic") and "$1M" in small
    flip = FAL.sales_line({**base, "base_state": "non_positive"})
    assert flip.endswith("year-ago revenue ≤ 0 — the % is a sign flip")
    row = FAL.scan_part(_scan_row("QQQQ"))
    assert row["qoq_base"] == Q.compute(
        rev_series=_scan_row("QQQQ")["fundamentals"]["rev_q_series"],
        eps_series=_scan_row("QQQQ")["fundamentals"]["eps_q_series"],
        periods=_scan_row("QQQQ")["fundamentals"]["q_period_series"])["growth_base"]


# --------------------------------------------------------------------------
# 16-17 — orders and the depth view
# --------------------------------------------------------------------------
def _r(sym, n_pass, pct, cap=None, base="ok", g=None, added=None):
    return {"symbol": sym, "pick": {"n_pass": n_pass}, "pct_below": pct, "market_cap": cap,
            "base_state": base, "growth_yoy_pct": g, "rev_added": added}


def _entry_of(rows):
    return {"rows": {r["symbol"]: r for r in rows}, "counts": {"fallen": len(rows)},
            "session": SESSION.isoformat(), "as_of": LAST}


def test_16_orders_default_depth_sales_and_cap():
    rows = [_r("AAA", 2, 45.0, cap=5e9, g=10.0, added=1e6),
            _r("BBB", 4, 41.0, cap=None, g=80.0, added=5e6),
            _r("CCC", 4, 70.0, cap=2e8, base="too_small", g=900.0, added=1e5),
            _r("DDD", 0, 55.0, cap=9e10, base=None, g=None),
            _r("EEE", 4, 70.0, cap=1e9, g=20.0, added=2e6)]
    e = _entry_of(rows)
    order = lambda s, d=40: [r["symbol"] for r in FAL.rank(e, sort=s, depth=d)[0]]  # noqa: E731
    assert order("default") == ["CCC", "EEE", "BBB", "AAA", "DDD"]
    assert order(FAL.SORT_DEPTH) == ["CCC", "EEE", "DDD", "AAA", "BBB"]
    assert order(FAL.SORT_SALES) == [r["symbol"] for r in sorted(rows, key=BD._sales_key)]
    assert order(FAL.SORT_SALES)[-1] == "DDD"                      # no sales read -> last
    assert order(DMT.SORT_MARKET_CAP) == ["DDD", "AAA", "EEE", "CCC", "BBB"]
    assert order(DMT.SORT_MARKET_CAP_ASC) == ["CCC", "EEE", "AAA", "DDD", "BBB"]
    assert order("default", 60) == ["CCC", "EEE"]
    assert FAL.rank(e, sort="default", depth=60)[1]["at_depth"] == 2


def test_17_parse_depth_and_the_depth_block():
    assert FAL.parse_depth("50") == 50 and FAL.parse_depth(" 70 ") == 70
    for bad in ("45", "30", "abc", "", None, "40.5", "-50", "1e2"):
        assert FAL.parse_depth(bad) == FAL.DEPTH_STEPS[0], bad
    assert FAL.DEPTH_STEPS[0] == FAL.THRESHOLD_PCT
    blk = FAL.depths_block(60)
    assert [b["key"] for b in blk] == [str(d) for d in FAL.DEPTH_STEPS]
    assert sum(b["on"] for b in blk) == 1 and [b for b in blk if b["on"]][0]["key"] == "60"
    assert [b["default"] for b in blk] == [True, False, False, False]


# --------------------------------------------------------------------------
# 18 — the drop days
# --------------------------------------------------------------------------
def test_18_top_drops_after_the_high_only_and_their_arithmetic():
    df = _frame(close=100.0, sets={_ago(100): {"high": 200.0}})
    # a drop BEFORE the high's day never counts; the high day itself never counts
    df.loc[pd.Timestamp(_ago(101)), "close"] = 90.0
    df.loc[pd.Timestamp(_ago(100)), "close"] = 80.0
    closes = {_ago(60): 90.0, _ago(40): 70.0, _ago(20): 63.0, _ago(10): 60.0}
    cur = 100.0
    for i in range(99, -1, -1):
        day = _ago(i)
        if day in closes:
            cur = closes[day]
        df.loc[pd.Timestamp(day), ["close", "open"]] = cur
        if day == _ago(40):
            df.loc[pd.Timestamp(day), "open"] = 85.0          # gap -5.56%, intraday -17.65%
            df.loc[pd.Timestamp(day), "volume"] = 3_000_000.0
    closed = KL.closed_frame(df, SESSION)
    read = FAL.closed_read("DRP", df, SESSION)
    drops = FAL.top_drops(closed, read)
    # the two -10% days tie: the later date first
    assert [d["date"] for d in drops] == [_ago(40), _ago(20), _ago(60)]
    assert all(d["date"] > read["high_date"] for d in drops)
    assert all(d["c2c_pct"] < 0 for d in drops)
    d0 = drops[0]
    assert d0["c2c_pct"] == round((70 / 90 - 1) * 100, 2)
    assert d0["gap_pct"] == round((85 / 90 - 1) * 100, 2)
    assert d0["intraday_pct"] == round((70 / 85 - 1) * 100, 2) and d0["larger_leg"] == "intraday"
    assert d0["vol_x50"] == 3.0
    assert d0["share_of_fall_pct"] == round(20 / (200 - 60) * 100, 2)
    assert d0["window"] == {"lo": _ago(41), "hi": _ago(39)}
    assert FAL.tile_marker({"drops": drops}) == {"date": _ago(40), "label": "−22.2%"}


def test_18b_NEG_vol_none_under_50_prior_bars_window_clamped_ties_later_first():
    hi_day, early_day = _ago(FAL.YEAR_BARS - 1), _ago(FAL.YEAR_BARS - 4)
    df = _frame(n=FAL.YEAR_BARS + 5, close=100.0, sets={hi_day: {"high": 300.0}})
    df.loc[df.index >= pd.Timestamp(early_day), "close"] = 80.0     # 9th bar: < 50 prior bars
    df.loc[pd.Timestamp(_ago(1)), "close"] = 40.0
    df.loc[pd.Timestamp(_ago(0)), "close"] = 20.0                    # -50% twice: a tie
    df.loc[:, "open"] = df["close"]
    read = FAL.closed_read("CLM", df, SESSION)
    assert read["high_date"] == hi_day
    drops = FAL.top_drops(KL.closed_frame(df, SESSION), read)
    assert [d["date"] for d in drops] == [_ago(0), _ago(1), early_day]   # the later date first
    assert drops[0]["window"] == {"lo": _ago(1), "hi": _ago(0)}       # clamped at the last bar
    assert drops[2]["vol_x50"] is None and drops[0]["vol_x50"] == 1.0
    assert FAL.top_drops(KL.closed_frame(_frame(), SESSION),
                         FAL.closed_read("FLAT", _frame(), SESSION)) == []


# --------------------------------------------------------------------------
# 19 — memo
# --------------------------------------------------------------------------
def _patch_build(monkeypatch, frames):
    real = FAL.build

    def fake(universe, session, **k):
        return real(universe, session, universe_fn=lambda u: list(frames),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    scan_fn=lambda: {}, scan_key_fn=lambda: None, attach_fn=_attach_stub,
                    caps_fn=lambda s, c: {}, profiles_fn=lambda s: {}, catalysts_fn=_cats)
    monkeypatch.setattr(FAL, "build", fake)


def test_19_warming_then_ready_spawns_once(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame(close=10.0, sets={_ago(5): {"high": 100.0}})})
    monkeypatch.setattr(FAL, "_scan_key", lambda: "k1")
    got = FAL.cached_or_warm("full", now=NOW)
    assert got["state"] == "warming" and got["entry"] is None
    FAL.cached_or_warm("full", now=NOW)
    assert len(_clean) == 1                                   # single flight
    _clean[0][0]()
    got = FAL.cached_or_warm("full", now=NOW)
    assert got["state"] == "ready" and got["stale_scan"] is False and "AAA" in got["entry"]["rows"]


def test_19b_a_new_scan_serves_the_held_entry_and_warms_once(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame(close=10.0, sets={_ago(5): {"high": 100.0}})})
    key = ["k1"]
    monkeypatch.setattr(FAL, "_scan_key", lambda: key[0])
    FAL.cached_or_warm("full", now=NOW, sync=True)
    assert _clean == []
    key[0] = "k2"
    got = FAL.cached_or_warm("full", now=NOW)
    assert got["state"] == "ready" and got["stale_scan"] is True
    FAL.cached_or_warm("full", now=NOW)
    assert len(_clean) == 1
    _clean[0][0]()
    assert list(FAL._memo) == [(SESSION.isoformat(), "full", "k2")]   # the older scan evicted
    assert FAL.cached_or_warm("full", now=NOW)["stale_scan"] is False


def test_19c_NEG_sync_never_spawns(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame()})
    assert FAL.cached_or_warm("full", now=NOW, sync=True)["state"] == "ready"
    assert _clean == []


def test_19d_NEG_an_empty_frames_read_raises_is_not_memoised_and_backs_off(monkeypatch, _clean):
    with pytest.raises(RuntimeError, match="not memoising an empty read"):
        FAL.build("full", SESSION, universe_fn=lambda u: ["AAA"], frames_fn=lambda s: {},
                  scan_fn=lambda: {}, scan_key_fn=lambda: None)
    monkeypatch.setattr(FAL, "build", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("frames down")))
    monkeypatch.setattr(FAL, "_scan_key", lambda: "k1")
    assert FAL.cached_or_warm("full", now=NOW)["state"] == "warming"
    _clean[0][0]()
    assert FAL._memo == {} and FAL._warming == set()
    got = FAL.cached_or_warm("full", now=NOW)
    assert got["state"] == "error" and got["reason"] == "frames down"
    assert len(_clean) == 1                                    # backing off: no second spawn
    key = (SESSION.isoformat(), "full", "k1")
    FAL._failures[key] = (FAL._failures[key][0] - FAL.FAIL_RETRY_SEC - 1, "frames down")
    FAL.cached_or_warm("full", now=NOW)
    assert len(_clean) == 2                                    # retried after FAIL_RETRY_SEC


def test_19e_NEG_a_late_older_session_build_is_dropped(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame()})
    newer = ("2026-10-06", "full", "k")
    FAL._memo[newer] = {"built_ts": 1e18, "sentinel": True}
    FAL._warm(("2026-10-05", "full", "k"), "full", SESSION)
    _clean[0][0]()
    assert list(FAL._memo) == [newer] and FAL._memo[newer]["sentinel"]


# --------------------------------------------------------------------------
# 20-22 — words, source guards, display-only
# --------------------------------------------------------------------------
_BANNED = re.compile(r"bounc|fake|caused|because|minervini", re.I)


def _served_words(e=None) -> list:
    counts = {k: 3 for k in FAL.COUNT_KEYS}
    out = [FAL.NOTE, FAL.WARMING_NOTE, FAL.EMPTY_NOTE_FMT.format(depth=50), FAL.error_note("x"),
           FAL.TAB_LABEL, FAL.DEFAULT_SORT_LABEL, FAL.DEPTH_SORT_LABEL, FAL.SALES_SORT_LABEL,
           FAL.header_text(counts, depth=60, as_of=LAST),
           FAL.count_line(counts, min_tier_label="Tradeable", need_date=LAST),
           FAL.suspects_block([{"symbol": "X", "date": LAST, "prev_close": 9.0, "close": 1.0,
                                "ratio": 0.11}])["head"]]
    out += [FAL.order_line(s["key"]) for s in FAL.served_sorts()]
    return out


def test_20_words_follow_the_constants(monkeypatch):
    counts = {k: 3 for k in FAL.COUNT_KEYS}
    h = FAL.header_text({**counts, "fallen": 618, "scanned": 2744}, depth=40, as_of=LAST)
    assert h == (f"{FAL.MARK} 618 of 2,744 names closed 40% or more under their 52-week high on "
                 f"{LAST} — the highest intraday high of the last 252 closed sessions.")
    assert "the depth you picked" not in h
    assert "3 of them are 60% or more" in FAL.header_text(counts, depth=60, as_of=LAST)
    monkeypatch.setattr(FAL, "THRESHOLD_PCT", 30.0)
    monkeypatch.setattr(FAL, "YEAR_BARS", 200)
    h2 = FAL.header_text(counts, depth=40, as_of=LAST)
    assert "30% or more" in h2 and "last 200 closed sessions" in h2 and "40%" not in h2
    cl = FAL.count_line(counts, min_tier_label="Tradeable", need_date=LAST)
    assert "in the last 200 sessions" in cl and "fewer than 200 sessions" in cl
    assert f"{prices._SCALE_GLITCH_RATIO:g}×" in cl
    assert "with no turnover" in cl
    assert "with no turnover" not in FAL.count_line({**counts, "no_turnover": 0},
                                                    min_tier_label="T", need_date=LAST)
    assert "UNMEASURED" in FAL.NOTE and FAL.MEASURED is False
    assert f"{40.0:g}%" in FAL.NOTE and FAL.TAB_LABEL == "\U0001F4C9 Down 40%+"


def test_20b_NEG_no_banned_word_in_any_served_string_or_the_module():
    for s in _served_words():
        assert not _BANNED.search(s), s
        assert "SEPA" not in s or "SEPA scan row" in s, s
    for name in ("fallen_tab.py", "fallen_catalysts.py"):
        src = (BACKEND / "chart_maps" / name).read_text(encoding="utf-8")
        assert not _BANNED.search(src.replace("quick_bounce", "")), name
        assert not re.search(r"insert_|update_one|update_many|replace_one|delete_|bulk_write|"
                             r"create_index|\.drop\(|open\(", src), name


def _code_only(path: Path) -> str:
    """The module's code: docstrings and comments blanked."""
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant) and isinstance(
                    body[0].value.value, str):
                for i in range(body[0].lineno - 1, body[0].end_lineno):
                    lines[i] = ""
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            r, c = tok.start
            lines[r - 1] = lines[r - 1][:c]
    return "\n".join(lines)


_RETYPED = [r"(?<![\w.])0\.05(?![\d])", r"(?<![\w.])100\.0(?![\d])", r"(?<![\d_])25_000_000(?![\d_])",
            r"(?<![\d_])10_000_000(?![\d_])", r"(?<![\d_])100_000_000(?![\d_])",
            r"(?<![\d_])10_000_000_000(?![\d_])", r"(?<![\w.])39(?![\w.])", r"(?<![\w.])157(?![\w.])",
            r"[\"']Technology[\"']", r"[\"']Healthcare[\"']", r"[\"']Consumer Cyclical[\"']",
            r"(?<![\w.])5\.0(?![\d])"]


def test_21_source_guards_reuse_never_retype():
    code = _code_only(BACKEND / "chart_maps" / "fallen_tab.py")
    for need in ("from sepa import bonde_picks as BP", "BP.attach", "BP.legend", "BP.coverage",
                 "B._row", "BV._bonde_pillar", "B._pair_mismatch", "B._sales_key",
                 "KL.period_levels", "prices._is_scale_glitch", "prices._SCALE_GLITCH_RATIO",
                 "KL.YEAR_BARS", "scanner.load_latest_shared", "DMT.market_cap_key"):
        assert need in code, need
    for name in ("fallen_tab.py", "fallen_catalysts.py"):
        c = _code_only(BACKEND / "chart_maps" / name)
        for pat in _RETYPED:
            assert not re.search(pat, c), (name, pat)
        assert not re.search(r"load_latest\(", c), name
        assert "json.load" not in c and "bulk_snapshot" not in c, name
    # the guard itself bites: a retyped glitch ratio would be caught
    assert re.search(_RETYPED[-1], "GLITCH_RATIO = 5.0")
    assert re.search(_RETYPED[0], "x = 0.05")


def test_22_NEG_no_trading_push_scanner_or_alert_module_imports_the_tab():
    targets = list((BACKEND / "trading").rglob("*.py")) + list((BACKEND / "push").rglob("*.py"))
    targets.append(BACKEND / "sepa" / "scanner.py")
    targets += list((BACKEND / "supply_demand").glob("*alerts*.py"))
    targets += list((BACKEND / "catalysts").rglob("*alerts*.py"))
    pat = re.compile(r"\bfallen_tab\b|\bfallen_catalysts\b")
    hits = [p.relative_to(BACKEND).as_posix() for p in targets
            if p.exists() and pat.search(p.read_text(encoding="utf-8"))]
    assert hits == [] and len(targets) > 5


# --------------------------------------------------------------------------
# 23 — board wiring
# --------------------------------------------------------------------------
class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture
def fal_board(monkeypatch):
    from supply_demand import zone_store
    state = {"frames": {}, "scan": [], "snap_calls": [], "finish_tiles": [], "en_kinds": [],
             "caps": {}}

    def _snaps(syms):
        state["snap_calls"].append(list(syms))
        return {}

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": LAST, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    real_finish = BOARD._finish

    def _finish_spy(tiles, *a, **k):
        state["finish_tiles"].append([dict(t) for t in tiles])
        return real_finish(tiles, *a, **k)

    def _enterable(tiles, kind="demand", **k):
        state["en_kinds"].append(kind)
        for t in tiles:
            if "enterable" not in t:
                t["enterable"] = {"verdict": "WATCH", "kind": kind}
        return len(tiles)

    real_build = FAL.build

    def fake_build(universe, session, **k):
        fr = state["frames"]
        return real_build(universe, session, universe_fn=lambda u: list(fr),
                          frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                          scan_fn=lambda: {"all_results": state["scan"]},
                          scan_key_fn=lambda: None, attach_fn=_leg_attach,
                          caps_fn=lambda s, c: dict(state["caps"]), profiles_fn=lambda s: {},
                          catalysts_fn=_cats)

    monkeypatch.setattr(FAL, "build", fake_build)
    monkeypatch.setattr(FAL, "_scan_key", lambda: "k")
    monkeypatch.setattr(BOARD, "datetime", _Fixed)
    monkeypatch.setattr(BOARD, "_bulk_snaps", _snaps)
    monkeypatch.setattr(BOARD, "_finish", _finish_spy)
    monkeypatch.setattr(BOARD, "_attach_bars", _bars)
    monkeypatch.setattr(BOARD, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(BOARD, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(BOARD, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(BOARD, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(BOARD, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(BOARD, "attach_enterable", _enterable)
    monkeypatch.setattr(BOARD, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(BOARD, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(BOARD, "attach_burst", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(BOARD, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(BOARD, "attach_key_levels", lambda tiles, out=None, **k: None)
    monkeypatch.setattr(zone_store, "load_latest", lambda syms: (None, {}))

    def seed(frames, scan=None, caps=None):
        state.update(frames=frames, scan=list(scan or []), caps=dict(caps or {}))
        FAL.cached_or_warm("full", now=NOW, sync=True)
    state["seed"] = seed
    return state


_READY_KEYS = {"state", "session", "as_of", "built_at", "stale_scan", "measured", "threshold_pct",
               "year_bars", "glitch_ratio", "depth_pct", "depth_param", "depths", "sort",
               "header", "order_line", "count_line", "note", "counts", "suspects",
               "pick_legend", "pick_coverage", "catalysts"}


def _board_seed(fal_board):
    frames = _mixed_frames()
    frames["APP"] = _app_frame()
    fal_board["seed"](frames, scan=[_scan_row("APP")], caps={"APP": 92.1e9})


def test_23_board_ready_envelope_tiles_and_one_snapshot(fal_board):
    _board_seed(fal_board)
    out = BOARD.board(tab="fallen", limit=24)
    assert out["tab"] == "fallen" and out["sort"] == "default"
    assert [s["key"] for s in out["sorts"]] == ["default", "fallen_depth", "fallen_sales",
                                               "market_cap", "market_cap_asc"]
    assert out["sorts"] == FAL.served_sorts()
    fb = out["fallen_board"]
    assert set(fb) == _READY_KEYS and fb["state"] == "ready" and fb["measured"] is False
    assert fb["threshold_pct"] == FAL.THRESHOLD_PCT and fb["year_bars"] == KL.YEAR_BARS
    assert fb["pick_legend"] == BP.legend() and fb["catalysts"]["note"] == FC.POSSIBLE_NOTE
    assert fb["as_of"] == LAST and fb["session"] == SESSION.isoformat()
    c = fb["counts"]
    assert c["scanned"] == sum(c[k] for k in FAL.STATUSES)
    assert c["at_depth"] <= c["fallen"] and c["shown"] <= c["at_depth"] - c["dropped_thin"]
    syms = [t["symbol"] for t in out["tiles"]]
    assert syms[0] == "APP" and "THIN" not in syms and "CTVA" not in syms and "SPY" not in syms
    assert c["dropped_thin"] == 1 and c["shown"] == len(syms) == 3
    assert "CTVA" in " ".join(fb["suspects"]["lines"])
    t = out["tiles"][0]
    f = t["fallen"]
    assert f["pct_below"] == 63.18 and f["high"] == 738.01 and f["high_date"] == _ago(200)
    assert f["market_cap"] == 92.1e9 and f["in_scan"] is True and f["sector"] == "Technology"
    assert f["hit"]["text"].startswith(f"{FC.HIT_MARK} What hit it: −61.2% on {_ago(149)}")
    assert "possible: nothing on file" in f["hit"]["text"] and f["hit"]["class"] == "nothing"
    assert set(f["zone"]) >= {"reason", "demand", "room", "floor", "gate", "print", "text"}
    assert t["badges"][0] == {"text": f"{FAL.MARK} 63.18% below the 52-week high",
                              "tone": "warn"}
    assert t["badges"][1]["text"].endswith(" cap")
    assert t["markers"] == [{"date": _ago(149), "label": "−61.2%"}]
    assert t["pick"]["legs"]["surprise"]["ok"] is True and "n_pass" in t["pick"]
    assert t["why"].startswith(f"{FAL.MARK} 63.18% under its 52-week high · ")
    assert [s["k"] for s in t["stats"][:4]] == ["52w high", "52w low", "Sector", "Sales"]
    for tile in out["tiles"]:
        assert tile["enterable"]["kind"] == "demand" and "fallen" in tile and "pick" in tile
    assert out["enterable_kind"] == "n/a"
    assert fal_board["en_kinds"][0] == "demand"
    assert len(fal_board["snap_calls"]) == 1
    assert set(fal_board["snap_calls"][0]) <= {"APP", "FALA", "FALB"}
    assert len(fal_board["snap_calls"][0]) <= 24 + BOARD.BAR_BUFFER
    for handed in fal_board["finish_tiles"][-1]:
        for k in BOARD.ATTACH_OWNED_KEYS:
            assert k not in handed, k


def test_23b_NEG_generic_sorts_fall_back_and_fallen_keys_are_tab_scoped(fal_board, monkeypatch):
    _board_seed(fal_board)
    assert BOARD.board(tab="fallen", sort="volume")["sort"] == "default"
    assert BOARD.board(tab="fallen", sort="nearest_demand")["sort"] == "default"
    dep = BOARD.board(tab="fallen", sort="fallen_depth")
    assert dep["sort"] == "fallen_depth" and dep["fallen_board"]["sort"] == "fallen_depth"
    assert [t["symbol"] for t in dep["tiles"]][0] == "FALB"
    cap = BOARD.board(tab="fallen", sort="market_cap")
    assert [t["symbol"] for t in cap["tiles"]][0] == "APP"
    seen = []
    monkeypatch.setattr(BOARD, "ath_tiles", lambda limit, days, universe, tf, srt, tier,
                        ctx=None: seen.append(srt) or {"tiles": []})
    assert BOARD.board(tab="ath", sort="fallen_depth")["sort"] == "default" and seen == ["default"]


def test_23c_NEG_depth_view_and_unknown_depths(fal_board):
    _board_seed(fal_board)
    d45 = BOARD.board(tab="fallen", depth="45")["fallen_board"]
    assert d45["depth_pct"] == 40 and [d["on"] for d in d45["depths"]] == [True, False, False, False]
    d60 = BOARD.board(tab="fallen", depth="60")
    assert d60["fallen_board"]["depth_pct"] == 60
    assert all(t["fallen"]["pct_below"] >= 60 for t in d60["tiles"])
    assert "the depth you picked" in d60["fallen_board"]["header"]
    d70 = BOARD.board(tab="fallen", depth="70")
    assert {t["symbol"] for t in d70["tiles"]} == {"FALB"}


def test_23d_warming_and_error_envelopes(monkeypatch, _clean):
    monkeypatch.setattr(FAL, "_scan_key", lambda: "k")
    out = BOARD.fallen_tiles(24, 130, "full", now=NOW, sort="fallen_sales", depth="50")
    assert out["tiles"] == [] and out["warming"] is True and out["note"] == FAL.WARMING_NOTE
    wb = out["fallen_board"]
    assert set(wb) == _READY_KEYS and wb["state"] == "warming" and wb["header"] == FAL.WARMING_NOTE
    for k in ("counts", "suspects", "pick_legend", "pick_coverage", "catalysts", "built_at"):
        assert wb[k] is None, k
    assert wb["depth_pct"] == 50 and wb["sort"] == "fallen_sales" and wb["note"] == FAL.NOTE
    key = (SESSION.isoformat(), "full", "k")
    FAL._warming.clear()
    FAL._failures[key] = (1e18, "boom")
    err = BOARD.fallen_tiles(24, 130, "full", now=NOW)
    assert "warming" not in err and err["note"] == FAL.error_note("boom")
    assert err["fallen_board"]["state"] == "error" and set(err["fallen_board"]) == _READY_KEYS


def test_23e_NEG_the_memo_rows_are_never_mutated_by_a_request(fal_board):
    _board_seed(fal_board)
    (key, entry), = FAL._memo.items()
    before = repr(entry["rows"])
    BOARD.board(tab="fallen", limit=24)
    BOARD.board(tab="fallen", sort="market_cap", limit=24)
    assert repr(entry["rows"]) == before


def test_23f_api_coercion_with_query_objects(monkeypatch):
    from chart_maps import api
    seen = {}

    def fake_board(**kw):
        seen.update(kw)
        return {"tiles": []}
    monkeypatch.setattr(api.board_mod, "board", fake_board)
    asyncio.run(api.chart_maps(tab="fallen"))                    # every other arg a Query object
    assert seen["tab"] == "fallen" and seen["depth"] is None
    asyncio.run(api.chart_maps(tab="fallen", depth="60"))
    assert seen["depth"] == "60"
    asyncio.run(api.chart_maps(tab="fallen", depth="   "))
    assert seen["depth"] is None


def test_23g_source_pins_on_the_board():
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    assert '(t == "fallen" and sort in _FAL.TAB_SORTS)' in src and 'elif t == "fallen":' in src
    body = src[src.index("def fallen_tiles("):src.index("def _usd_short(")]
    assert "load_latest(" not in body.replace("zone_store.load_latest(", "")
    assert "load_latest_shared" not in body and "_bulk_snaps_fanout" not in body
    assert body.count("_bulk_snaps(") == 1 and "copy.deepcopy(r)" in body


# --------------------------------------------------------------------------
# 24-25 — rules panel, TABS
# --------------------------------------------------------------------------
def test_24_rules_panel_section_is_last_and_built_from_the_constants(monkeypatch):
    from supply_demand import rules_info as RI
    assert RI.SECTION_KEYS[-1] == "fallen"
    secs = RI.sections()
    assert tuple(secs) == RI.SECTION_KEYS
    sec = secs["fallen"]
    assert sec["picks"] and sec["stops"] and len(sec["picks"]) <= 8 and len(sec["stops"]) <= 6
    text = " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])
    assert f"{FAL.THRESHOLD_PCT:g}% or more" in text and f"last {FAL.YEAR_BARS} closed" in text
    assert f"{FAL.GLITCH_RATIO:g}× or more" in text and f"the {FC.TOP_DROPS} biggest" in text
    assert FAL.order_line("default") in sec["picks"] and sec["emoji"] == FAL.MARK
    assert not _BANNED.search(text)
    monkeypatch.setattr(FAL, "THRESHOLD_PCT", 30.0)
    assert "30% or more" in " ".join(RI._fallen_section()["picks"])


def test_25_fallen_is_the_last_tab_and_not_a_demand_tab():
    assert "fallen" in BOARD.TABS and BOARD.TABS[-1] == "fallen"
    from supply_demand import enterable as EN
    assert "fallen" not in EN.KIND_BY_TAB                          # 🎯 n/a (HIS CALL #18)


# --------------------------------------------------------------------------
# critic round 2026-10-03 — regressions
# --------------------------------------------------------------------------
def test_26_NEG_a_shallow_etf_or_delisted_name_counts_under_threshold(monkeypatch):
    deep = _frame(close=10.0, sets={_ago(10): {"high": 100.0}})
    shallow = _frame(close=90.0, sets={_ago(10): {"high": 100.0}})
    etfs = FAL._static_etfs()
    assert FAL.classify("SPY", deep, None, etfs, SESSION)[0] == "etf"
    assert FAL.classify("SPY", shallow, None, etfs, SESSION)[0] == "under_threshold"
    assert FAL.classify("ZZET", shallow, {"is_etf": True}, etfs, SESSION)[0] == "under_threshold"
    monkeypatch.setattr(symbols, "is_delisted", lambda s: s in ("DEAD", "GONE"))
    assert FAL.classify("DEAD", deep, None, set(), SESSION)[0] == "delisted"
    assert FAL.classify("GONE", shallow, None, set(), SESSION)[0] == "under_threshold"
    frames = {"SPY": deep.copy(), "QQQ": shallow.copy(), "DEAD": deep.copy(),
              "GONE": shallow.copy(), "FALA": deep.copy()}
    e = _build(frames)
    c = e["counts"]
    assert (c["etf"], c["delisted"], c["under_threshold"], c["fallen"]) == (1, 1, 2, 1)
    assert c["scanned"] == sum(c[k] for k in FAL.STATUSES) == 5
    assert set(e["rows"]) == {"FALA"}


class _FakeShares:
    def __init__(self, docs):
        self.docs = {d["_id"]: d for d in docs}
        self.finds = 0

    def find(self, q):
        self.finds += 1
        return [self.docs[s] for s in q["_id"]["$in"] if s in self.docs]


def test_27_NEG_a_pre_reverse_split_share_count_serves_cap_na(monkeypatch):
    # BYND 2026-10-02: 515,818,978 shares x 8.23 = $4.2B vs the doc's own $215.4M
    coll = _FakeShares([
        {"_id": "BYND", "shares_outstanding": 515_818_978, "market_cap": 215_406_000},
        {"_id": "APP", "shares_outstanding": 305_700_000, "market_cap": 90_000_000_000},
        {"_id": "NOMC", "shares_outstanding": 1_000_000},
        {"_id": "ONLYMC", "market_cap": 5e8}])
    from sepa import volume_movers as vm
    monkeypatch.setattr(vm, "shares_for",
                        lambda s: (_ for _ in ()).throw(AssertionError("provider call")))
    caps = FAL.shares_caps(["BYND", "APP", "NOMC", "ONLYMC", "MISS"],
                           {"BYND": 8.23, "APP": 271.73, "NOMC": 5.0, "ONLYMC": 3.0,
                            "MISS": 1.0}, coll=coll)
    assert coll.finds == 1                                  # ONE shares-cache read
    assert caps["BYND"] is None                              # disagree >= the ratio -> n/a
    assert caps["APP"] == pytest.approx(305_700_000 * 271.73)
    assert caps["NOMC"] == pytest.approx(5_000_000.0)        # no doc cap -> the cap stands
    assert caps["ONLYMC"] == pytest.approx(5e8)              # the doc's own cap, no shares
    assert caps["MISS"] is None                              # never fetched (cap=0)
    r = FAL.CAP_DISAGREE_RATIO
    assert r == FAL.GLITCH_RATIO == prices._SCALE_GLITCH_RATIO
    assert FAL.checked_cap(r * 100.0, 100.0) is None         # boundary: AT the ratio -> n/a
    assert FAL.checked_cap(100.0, r * 100.0) is None         # either direction
    assert FAL.checked_cap(r * 99.0, 100.0) == pytest.approx(r * 99.0)
    assert FAL.checked_cap(0, 100.0) is None and FAL.checked_cap(None, 1.0) is None
    assert FAL.checked_cap(50.0, 0) == 50.0 and FAL.checked_cap(50.0, float("nan")) == 50.0
    src = (BACKEND / "chart_maps" / "fallen_tab.py").read_text(encoding="utf-8")
    assert "caps_fn = shares_caps" in src and "cap=0)" in src


def test_28_NEG_drops_head_never_prints_a_share_above_100():
    three = [{"date": LAST}] * 3
    t = FAL.drops_head({"drops": three, "top3_share_pct": 116.8})
    assert "116.8" not in t and "%" not in t
    assert t == ("3 biggest down days since the high — their drops add up to more than "
                 "the high-to-close fall (it rallied in between)")
    one = FAL.drops_head({"drops": three[:1], "top3_share_pct": 101.0})
    assert one.endswith("its drop is more than the high-to-close fall (it rallied in between)")
    assert FAL.drops_head({"drops": three, "top3_share_pct": 100.0}).endswith(
        "— 100.0% of the fall")
    assert FAL.drops_head({"drops": three, "top3_share_pct": 57.51}).endswith("57.5% of the fall")
    assert FAL.drops_head({"drops": three, "top3_share_pct": None}) == (
        "3 biggest down days since the high")


def test_27b_NEG_a_withheld_cap_is_described_as_left_off_never_as_cap_na():
    # critic round 2 2026-10-03: the board adds the cap badge only `if cap`, so
    # a withheld cap is NO badge — the doc and comment must not promise "cap n/a"
    board = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    assert "if cap else []" in board
    fal = (BACKEND / "chart_maps" / "fallen_tab.py").read_text(encoding="utf-8")
    doc = (BACKEND.parent / "docs" / "chart_maps" / "fallen_40_tab_2026_10_02.md").read_text(
        encoding="utf-8")
    assert "cap n/a" not in fal and "cap n/a" not in doc
    assert "cap badge off" in fal and doc.count("the cap badge is left off") == 2
