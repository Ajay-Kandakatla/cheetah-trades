"""🏔️ ATH tab on Chart Maps (2026-09-29) — spec §3.3-§3.4, tests 1-15.

Ajay 2026-09-29: "Can you give me a new tab - for all the stocks that are
reaching all time highs? call it ATH. Once some of them are going below their
ATH or 52 Week Highs.."

Pins `chart_maps/ath_tab.py` (completeness, the closed half, the per-request
classify, rank + counts, words, memo + filler) and the board wiring
(`ath_tiles`, the tab-scoped `slipping` sort, the two served sorts).
Positive AND negative cases. Stubs only — the conftest refuses Mongo; no
thread is ever started (`_spawn` is patched) and nothing reaches the network.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import ath_history as AH
from chart_maps import ath_tab as ATH
from chart_maps import board as B
from sepa import prices, symbols
from supply_demand import key_levels as KL

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]

NOW = datetime(2026, 9, 29, 11, 0, tzinfo=ET)          # Tuesday, rth
SESSION = date(2026, 9, 29)
LAST = "2026-09-28"


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
    """The closed session `n` sessions before the last closed bar."""
    return DAYS[-1 - n]


def _frame(n=300, *, end=LAST, close=90.0, sets=None, volume=1_000_000.0):
    idx = pd.DatetimeIndex(_market_days(end, n))
    df = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 1.0,
                       "close": close, "volume": volume}, index=idx)
    for day, vals in (sets or {}).items():
        for k, v in vals.items():
            df.loc[pd.Timestamp(day), k] = v
    return df


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _rth(px, *, ref, high=None, at=NOW, age_sec=30, close=None, pdc=None):
    return {"open": ref, "high": high if high is not None else max(ref, px),
            "low": min(ref, px), "close": close if close is not None else px,
            "last_trade_price": px, "last_trade_ts_ms": _ms(at) - age_sec * 1000,
            "prev_day_close": ref if pdc is None else pdc}


def _read(**kw) -> dict:
    base = {"symbol": "AAA", "hi_closed": 100.0, "hi_date": "2026-01-05",
            "hi_date_is_month": False, "first_bar": "2020-01-02", "first_is_month": False,
            "since": "2020-01-02", "listed": "2020-01-02", "status": "complete",
            "proven": True, "label": "ATH", "w52": {"price": 100.0, "set_on": "2026-01-05"},
            "w52_sessions_ago": 180, "hi_sessions_ago": 180, "sma50": 95.0, "adv50": 5e7,
            "ref_close": 97.0, "last_date": LAST, "stale_note": None,
            "lookback_start": _ago(ATH.SLIP_LOOKBACK_SESSIONS - 1), "doc_state": "ok",
            "refetch": None}
    base.update(kw)
    return base


def _cls(read, px, *, high=None, now=NOW):
    row = KL.row_from_snapshot(_rth(px, ref=read["ref_close"], high=high, at=now))
    return ATH.classify(read, row, now=now, session=KL.levels_session(now))


def _doc(sym, *, hi, hi_month, first_bar="2004-01-01", check_month="2026-08", check_high=None,
         cut_from=None, fetched_at=None, status="ok"):
    return {"_id": sym, "symbol": sym, "status": status, "first_bar": first_bar, "hi": hi,
            "hi_month": hi_month, "check_month": check_month, "check_high": check_high,
            "cut_from": cut_from, "n_months": 100, "curation": AH.curation_key(sym),
            "source": AH.SOURCE,
            "fetched_at": NOW.timestamp() - 3600 if fetched_at is None else fetched_at}


def _aug_high(df) -> float:
    idx = pd.DatetimeIndex(df.index)
    return float(df["high"][(idx.year == 2026) & (idx.month == 8)].max())


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    ATH._memo.clear()
    ATH._warming.clear()
    ATH._fill_errors.clear()
    monkeypatch.setattr(ATH, "_filling", False)
    spawned = []
    monkeypatch.setattr(ATH, "_spawn", lambda target, name: spawned.append((target, name)))
    monkeypatch.setenv(AH.STORE_ENV, "memory")
    AH._MEM.clear()
    yield spawned
    ATH._memo.clear()
    ATH._warming.clear()
    AH._MEM.clear()


# --------------------------------------------------------------------------
# 1 — completeness
# --------------------------------------------------------------------------
def test_01_completeness():
    # same listing month on a monthly first bar -> complete
    assert ATH.completeness("2020-09-01", True, "2020-09-30") == "complete"
    # the provider floor vs a 1980 listing -> short, labelled "High since 2003-09"
    assert ATH.completeness("2003-09-01", True, "1980-12-12") == "history_short"
    assert ATH.since_text("2003-09-01", True) == "2003-09"
    # XOM-shape: bars before a (late) profile listing with no hole -> never proven
    assert ATH.completeness("2003-09-01", True, "2026-07-02") == "bars_before_listing"
    assert ATH.completeness("2003-09-01", True, None) == "no_listing_date"
    # daily first bar within +/- BAR_SLACK_DAYS -> complete; one day more -> short
    from chart_maps.ipo import BAR_SLACK_DAYS
    assert BAR_SLACK_DAYS == 7
    assert ATH.completeness("2025-03-10", False, "2025-03-03") == "complete"
    assert ATH.completeness("2025-02-24", False, "2025-03-03") == "complete"
    assert ATH.completeness("2025-03-11", False, "2025-03-03") == "history_short"
    assert ATH.completeness("2025-02-23", False, "2025-03-03") == "bars_before_listing"


def test_01b_first_session_overrides_a_profile_date(monkeypatch):
    monkeypatch.setitem(symbols.FIRST_SESSION, "WWQ", ("2025-09-29", "test"))
    assert ATH.listed_for("WWQ", {"WWQ": "1993-02-09"}) == "2025-09-29"
    assert ATH.listed_for("PPP", {"PPP": "2020-09-30"}) == "2020-09-30"
    assert ATH.listed_for("PPP", {}) is None


# --------------------------------------------------------------------------
# 2 — closed_read
# --------------------------------------------------------------------------
def test_02_pre_frame_ath_comes_from_the_doc_as_a_month():
    df = _frame(sets={_ago(40): {"high": 100.0}})
    doc = _doc("AAA", hi=150.0, hi_month="2015-06", check_high=_aug_high(df))
    rd = ATH.closed_read("AAA", df, doc, "2003-10-01", SESSION)
    assert rd["doc_state"] == "ok" and rd["refetch"] is None
    assert rd["hi_closed"] == 150.0 and rd["hi_date"] == "2015-06" and rd["hi_date_is_month"]
    assert rd["hi_sessions_ago"] is None
    assert rd["first_bar"] == "2004-01-01" and rd["first_is_month"] is True
    assert rd["status"] == "history_short" and rd["label"] == "High since 2004-01"
    assert rd["w52"]["price"] == 100.0 and rd["w52"]["set_on"] == _ago(40)
    assert rd["w52_sessions_ago"] == 40
    assert rd["ref_close"] == 90.0 and rd["last_date"] == LAST and rd["stale_note"] is None


def test_02b_frame_ath_at_or_over_the_doc_gets_the_exact_day():
    df = _frame(sets={_ago(3): {"high": 120.0}})
    doc = _doc("AAA", hi=110.0, hi_month="2021-11", first_bar="2020-09-01",
               check_high=_aug_high(df))
    rd = ATH.closed_read("AAA", df, doc, "2020-09-30", SESSION)
    assert rd["hi_closed"] == 120.0 and rd["hi_date"] == _ago(3) and not rd["hi_date_is_month"]
    assert rd["hi_sessions_ago"] == 3
    assert rd["proven"] is True and rd["label"] == "ATH"
    # a tie to the cent also takes the exact day
    doc2 = _doc("AAA", hi=120.004, hi_month="2021-11", check_high=_aug_high(df))
    rd2 = ATH.closed_read("AAA", df, doc2, None, SESSION)
    assert rd2["hi_date"] == _ago(3) and rd2["hi_closed"] == 120.004
    assert rd2["status"] == "no_listing_date" and not rd2["proven"]


def test_02c_split_mismatch_serves_frame_only_and_refetches_only_when_old():
    df = _frame(sets={_ago(30): {"high": 95.0}})
    old = _doc("AAA", hi=500.0, hi_month="2010-01", check_high=2 * _aug_high(df),
               fetched_at=NOW.timestamp() - AH.REFETCH_MIN_AGE_SEC - 5)
    rd = ATH.closed_read("AAA", df, old, "1990-01-02", SESSION, now_ts=NOW.timestamp())
    assert rd["doc_state"] == "split" and rd["refetch"] == "split"
    assert rd["hi_closed"] == 95.0 and rd["status"] == "history_split" and not rd["proven"]
    assert rd["first_is_month"] is False and rd["first_bar"] == DAYS[-300]
    # NEGATIVE: a doc fetched inside REFETCH_MIN_AGE_SEC -> no refetch reason
    young = {**old, "fetched_at": NOW.timestamp() - 60}
    rd2 = ATH.closed_read("AAA", df, young, "1990-01-02", SESSION, now_ts=NOW.timestamp())
    assert rd2["doc_state"] == "split" and rd2["refetch"] is None and rd2["hi_closed"] == 95.0


def test_02d_a_check_month_before_the_frame_is_refetched_never_passed_empty():
    """critic 2026-09-29: the split check used to PASS on an empty overlap."""
    df = _frame(n=10)                                   # September bars only
    doc = _doc("AAA", hi=50.0, hi_month="2019-01", check_high=1.0)
    old = {**doc, "fetched_at": NOW.timestamp() - AH.REFETCH_MIN_AGE_SEC - 5}
    rd = ATH.closed_read("AAA", df, old, None, SESSION, now_ts=NOW.timestamp())
    assert rd["doc_state"] == "pending" and rd["refetch"] == "check_stale"
    assert rd["hi_closed"] == 91.0 and not rd["proven"]         # frame-only, the doc unused
    # NEGATIVE: a FRESH doc that still ends before the frame is never trusted but
    # never refetched either (no refetch loop on every rebuild)
    fresh = ATH.closed_read("AAA", df, doc, None, SESSION, now_ts=NOW.timestamp())
    assert fresh["doc_state"] == "pending" and fresh["refetch"] is None
    assert fresh["hi_closed"] == 91.0 and not fresh["first_is_month"]
    # NEGATIVE: the same doc against a frame that covers the check month is ok
    big = _frame()
    rd2 = ATH.closed_read("AAA", big, {**doc, "check_high": _aug_high(big)}, None, SESSION)
    assert rd2["doc_state"] == "ok" and rd2["refetch"] is None
    assert rd2["first_is_month"] and rd2["first_bar"] == "2004-01-01"      # the doc is read


def test_02e_curation_mismatch_is_frame_only_and_pending(monkeypatch):
    df = _frame()
    doc = _doc("AAA", hi=500.0, hi_month="2010-01", check_high=_aug_high(df))
    monkeypatch.setitem(symbols.FIRST_SESSION, "AAA", ("2024-01-02", "test"))
    rd = ATH.closed_read("AAA", df, doc, "1990-01-02", SESSION)
    assert rd["doc_state"] == "pending" and rd["refetch"] == "curation"
    assert rd["hi_closed"] == 91.0 and rd["status"] == "history_pending"
    # NEGATIVE: no doc at all -> missing, frame-only
    rd2 = ATH.closed_read("AAA", df, None, "1990-01-02", SESSION)
    assert rd2["refetch"] == "missing" and rd2["hi_closed"] == 91.0


def _young_doc(sym, df, first_bar):
    return _doc(sym, hi=float(df["high"].max()), hi_month="2026-08", first_bar=first_bar,
                check_high=_aug_high(df))


def test_02f_NEGATIVE_the_daily_frame_alone_never_proves_all_time():
    """critic 2026-09-29: a frame that starts on the listing date could simply
    be a cache that begins there — proof needs the monthly history."""
    df = _frame(n=100)
    rd = ATH.closed_read("NEWX", df, None, DAYS[-100], SESSION)
    assert rd["status"] == "history_pending" and not rd["proven"]
    assert rd["label"] == f"High since {DAYS[-100]}"
    assert rd["w52"] is None                              # < YEAR_BARS
    # a 2-year-old listing whose history is still pending reads "high since"
    two_y = _frame(n=400)
    rd2 = ATH.closed_read("TWOY", two_y, None, DAYS[-400], SESSION)
    assert rd2["status"] == "history_pending" and not rd2["proven"]
    assert rd2["label"].startswith("High since ") and rd2["refetch"] == "missing"
    # ... and so does one whose doc is 'empty' (the provider had no monthly bars)
    empty = {**_young_doc("NEWX", df, DAYS[-100][:8] + "01"), "status": "empty"}
    rd3 = ATH.closed_read("NEWX", df, empty, DAYS[-100], SESSION)
    assert rd3["doc_state"] == "empty" and not rd3["proven"]


def test_02f2_the_monthly_history_reaching_the_listing_proves_it():
    df = _frame(n=100)
    doc = _young_doc("NEWX", df, DAYS[-100][:8] + "01")      # the listing month
    rd = ATH.closed_read("NEWX", df, doc, DAYS[-100], SESSION)
    assert rd["doc_state"] == "ok" and rd["status"] == "complete" and rd["proven"]
    assert rd["label"] == "ATH"
    # NEGATIVE: the doc good but its first month after the listing month -> short
    late = _young_doc("NEWX", df, "2026-08-01")
    rd2 = ATH.closed_read("NEWX", _frame(n=400), late, DAYS[-400], SESSION)
    assert rd2["doc_state"] == "ok" and not rd2["proven"]
    assert rd2["status"] == "history_short" and rd2["label"] == f"High since {DAYS[-400]}"


def test_02f3_a_curated_mid_month_first_session_is_proven_by_the_next_month(monkeypatch):
    """`_cut_foreign_head` drops the listing month's own monthly bar (stamped
    the 1st) for a mid-month curated first session — SPCX 2026-06-12 shape."""
    monkeypatch.setitem(symbols.FIRST_SESSION, "MIDX", ("2026-06-12", "test"))
    df = prices._cut_foreign_head(_frame(n=200), "MIDX")
    doc = _doc("MIDX", hi=91.0, hi_month="2026-08", first_bar="2026-07-01",
               check_high=_aug_high(df))
    rd = ATH.closed_read("MIDX", df, doc, ATH.listed_for("MIDX", {}), SESSION)
    assert rd["first_bar"] == "2026-06-12" and rd["proven"] and rd["label"] == "ATH"
    assert ATH.monthly_reaches_listing("MIDX", "2026-07-01", "2026-06-12")
    # NEGATIVE: two months after -> not reached; not curated -> not reached
    assert not ATH.monthly_reaches_listing("MIDX", "2026-08-01", "2026-06-12")
    assert not ATH.monthly_reaches_listing("OTHR", "2026-07-01", "2026-06-12")
    assert not ATH.monthly_reaches_listing("MIDX", None, "2026-06-12")


def test_02g_cut_from_reaches_the_frame_but_never_a_spliced_rename(monkeypatch):
    df = _frame(sets={_ago(200): {"high": 200.0}, _ago(10): {"high": 99.0}})
    cut = _ago(150)
    doc = _doc("SPX2", hi=60.0, hi_month="2025-06", first_bar=cut, cut_from=cut,
               check_high=_aug_high(df))
    rd = ATH.closed_read("SPX2", df, doc, cut, SESSION)
    assert rd["hi_closed"] == 99.0 and rd["hi_date"] == _ago(10)
    # NEGATIVE: a spliced rename (former_names non-empty) keeps its head
    monkeypatch.setitem(symbols._FORMER, "SPX2", ["OLDSPX"])
    doc2 = {**doc, "curation": AH.curation_key("SPX2")}
    rd2 = ATH.closed_read("SPX2", df, doc2, cut, SESSION)
    assert rd2["doc_state"] == "ok" and rd2["hi_closed"] == 200.0


def test_02h_no_closed_bars_is_none_and_stale_bars_carry_a_note():
    today_only = _frame(n=1, end="2026-09-29")
    assert ATH.closed_read("AAA", today_only, None, None, SESSION) is None
    assert ATH.closed_read("AAA", None, None, None, SESSION) is None
    behind = _frame(end="2026-09-22")
    rd = ATH.closed_read("AAA", behind, None, None, SESSION)
    assert rd["stale_note"].startswith("ATH needs bars through 2026-09-28")


# --------------------------------------------------------------------------
# 3 — the A bound
# --------------------------------------------------------------------------
def test_03_a_bound_to_the_cent():
    g, a = _cls(_read(), 98.00)
    assert g == ATH.GROUP_AT and a["pct_from_high"] == -2.0 and a["through_prior_pct"] is None
    g2, _ = _cls(_read(), 97.99)
    assert g2 != ATH.GROUP_AT and g2 == ATH.GROUP_REST       # 0.01 past the bound excluded


# --------------------------------------------------------------------------
# 4 — through today
# --------------------------------------------------------------------------
def test_04_through_today_is_A_never_B():
    g, a = _cls(_read(), 101.0, high=106.0)
    assert g == ATH.GROUP_AT and a["through_prior_pct"] == 1.0 and a["high_today"]
    assert a["high"] == 106.0 and a["high_date"] == SESSION.isoformat()
    assert a["text"].startswith(f"{ATH.MARK} new all-time high today · +1.00% over 100.00")
    rows, counts = ATH.rank(_entry_of({"AAA": _read()}), {"AAA": _rth(101.0, ref=97.0,
                                                                        high=106.0)},
                            now=NOW, group=ATH.GROUP_SLIP)
    assert rows == [] and counts["at_ath"] == 1 and counts["through_today"] == 1


def test_04b_a_new_high_today_then_a_fall_is_B_set_today():
    g, a = _cls(_read(), 99.0, high=106.0)
    assert g == ATH.GROUP_SLIP
    assert a["slip"] == {"from": "ath", "price": 106.0, "date": SESSION.isoformat(),
                         "sessions_ago": 0, "pct": round((99 / 106 - 1) * 100, 2)}
    assert "set today" in a["text"] and a["text"].startswith(ATH.SLIP_MARK)


# --------------------------------------------------------------------------
# 5 — the B look-back
# --------------------------------------------------------------------------
def _w52_read(set_ago: int) -> dict:
    return _read(hi_closed=120.0, hi_date="2015-06", hi_date_is_month=True,
                 w52={"price": 100.0, "set_on": _ago(set_ago)}, w52_sessions_ago=set_ago)


def test_05_52w_high_ten_sessions_ago_five_pct_under_is_B():
    g, a = _cls(_w52_read(10), 95.0)
    assert g == ATH.GROUP_SLIP and a["slip"]["from"] == "52w"
    assert a["slip"]["sessions_ago"] == 10 and a["slip"]["date"] == _ago(10)
    assert "under the 52-week high 100.00" in a["text"] and "(10 sessions ago)" in a["text"]


def test_05b_NEGATIVE_22_sessions_ago_is_rest():
    g, _ = _cls(_w52_read(22), 95.0)
    assert g == ATH.GROUP_REST
    g20, _ = _cls(_w52_read(ATH.SLIP_LOOKBACK_SESSIONS - 1), 95.0)
    assert g20 == ATH.GROUP_SLIP                            # the window edge is inside


def test_05c_NEGATIVE_one_pct_under_a_52w_only_high_is_at_52w_only():
    g, a = _cls(_w52_read(10), 99.0)
    assert g == ATH.GROUP_52W_ONLY and a["slip"] is None


def test_05d_a_52w_high_that_IS_the_ath_slips_from_the_ath():
    g, a = _cls(_read(hi_closed=100.0, w52={"price": 100.0, "set_on": _ago(5)},
                      w52_sessions_ago=5, hi_date=_ago(5), hi_sessions_ago=5), 94.0)
    assert g == ATH.GROUP_SLIP and a["slip"]["from"] == "ath"
    assert "under the all-time high 100.00" in a["text"]


# --------------------------------------------------------------------------
# 6 — a young name (< 252 bars)
# --------------------------------------------------------------------------
def test_06_young_name_slips_from_its_ath():
    df = _frame(n=100, sets={_ago(5): {"high": 100.0}})
    doc = _young_doc("YNG", df, DAYS[-100][:8] + "01")
    rd = ATH.closed_read("YNG", df, doc, DAYS[-100], SESSION)
    assert rd["w52"] is None and rd["proven"] and rd["hi_sessions_ago"] == 5
    g, a = ATH.classify(rd, KL.row_from_snapshot(_rth(95.0, ref=90.0)), now=NOW,
                        session=SESSION)
    assert g == ATH.GROUP_SLIP and a["slip"]["from"] == "ath" and a["slip"]["sessions_ago"] == 5
    # NEGATIVE: the ATH 30 sessions back is outside the window -> rest
    rd_old = ATH.closed_read("YNG", _frame(n=100, sets={_ago(30): {"high": 100.0}}), doc,
                             DAYS[-100], SESSION)
    g2, _ = ATH.classify(rd_old, KL.row_from_snapshot(_rth(95.0, ref=90.0)), now=NOW,
                         session=SESSION)
    assert g2 == ATH.GROUP_REST


# --------------------------------------------------------------------------
# 7 — short history in A
# --------------------------------------------------------------------------
def test_07_short_history_is_high_since_and_never_proven():
    rd = _read(proven=False, status="history_short", since="2003-09", first_is_month=True,
               label="High since 2003-09", listed="1980-12-12")
    g, a = _cls(rd, 99.5)
    assert g == ATH.GROUP_AT and a["label"] == "High since 2003-09"
    assert a["text"].endswith("— not proven all-time")
    assert "high since 2003-09" in a["text"] and "all-time high" not in a["text"]
    rows, counts = ATH.rank(_entry_of({"AAA": rd}), {"AAA": _rth(99.5, ref=97.0)}, now=NOW,
                            group=ATH.GROUP_AT)
    assert counts["at_ath"] == 1 and counts["at_ath_proven"] == 0
    assert counts["history_short"] == 1
    stats = ATH.tile_stats(rows[0])
    assert stats[0]["k"] == "High since 2003-09"
    assert stats[-1] == {"k": "History", "v": "since 2003-09 (listed 1980-12-12)"}
    assert ATH.tile_lines(rows[0]) == [{"price": 100.0, "label": "HIGH SINCE 2003-09",
                                        "tone": "neutral"}]


# --------------------------------------------------------------------------
# 8 — foreign head (WOLF-shape)
# --------------------------------------------------------------------------
def test_08_foreign_head_spike_never_becomes_the_high(monkeypatch):
    monkeypatch.setitem(symbols.FIRST_SESSION, "WWQ", ("2025-09-29", "test"))
    daily = _frame(n=400, close=40.0,
                   sets={"2025-03-03": {"high": 999.0}, "2026-02-02": {"high": 60.0}})
    cut_daily = prices._cut_foreign_head(daily, "WWQ")        # the bulk_cached_frames cut
    months = [p for p in pd.period_range("2003-09", "2026-08", freq="M")]
    mdf = pd.DataFrame({"open": 10.0, "high": 20.0, "low": 5.0, "close": 10.0, "volume": 1e6},
                       index=pd.DatetimeIndex([p.to_timestamp() + pd.Timedelta(hours=5)
                                               for p in months]))
    mdf.loc[pd.Timestamp("2010-05-01 05:00"), "high"] = 5000.0
    mdf.loc[pd.Timestamp("2026-08-01 05:00"), "high"] = _aug_high(cut_daily)
    mdf.loc[pd.Timestamp("2026-02-01 05:00"), "high"] = 60.0
    doc = AH.summarize("WWQ", mdf, now=NOW)
    assert doc["first_bar"] == "2025-10-01" and doc["hi"] == 60.0
    rd = ATH.closed_read("WWQ", cut_daily, doc, ATH.listed_for("WWQ", {"WWQ": "1993-02-09"}),
                         SESSION)
    assert rd["hi_closed"] == 60.0 and rd["hi_closed"] not in (999.0, 5000.0)
    assert rd["proven"] and rd["first_bar"] == "2025-09-29"


# --------------------------------------------------------------------------
# 9 — rank: the invariant and the two orders
# --------------------------------------------------------------------------
def _entry_of(reads: dict, syms=None) -> dict:
    return {"syms": list(syms or reads), "reads": reads, "pending": [],
            "history": {"read": len(reads), "pending": 0}, "session": SESSION.isoformat(),
            "built_ts": 0, "built_at": None, "ukey": "full"}


def test_09_counts_invariant_and_orders():
    reads = {
        "THRU": _read(symbol="THRU"),                                    # through today
        "NEAR": _read(symbol="NEAR"),                                    # 1% under
        "NEAR2": _read(symbol="NEAR2"),                                  # 1% under (tie -> sym)
        "CLOSE": _read(symbol="CLOSE"),                                  # 0.5% under
        "SLIPA": _w52_read(3),                                           # 5% under, 3 ago
        "SLIPB": _w52_read(3),                                           # 3% under, 3 ago
        "SLIPC": _w52_read(8),                                           # 3% under, 8 ago
        "W52": _w52_read(10),                                            # at 52w only
        "REST": _read(symbol="REST"),                                    # far away
        "STALE": _read(stale_note="behind"),
        "NOPR": _read(),
        "BADV": _read(),                                                 # verify mismatch
    }
    snaps = {"THRU": _rth(102.0, ref=97.0), "NEAR": _rth(99.0, ref=97.0),
             "NEAR2": _rth(99.0, ref=97.0), "CLOSE": _rth(99.5, ref=97.0),
             "SLIPA": _rth(95.0, ref=97.0), "SLIPB": _rth(97.0, ref=97.0),
             "SLIPC": _rth(97.0, ref=97.0), "W52": _rth(99.0, ref=97.0),
             "REST": _rth(80.0, ref=97.0), "STALE": _rth(99.0, ref=97.0),
             "BADV": _rth(99.0, ref=97.0, pdc=91.0, close=92.0)}
    entry = _entry_of(reads, syms=list(reads) + ["NOBARS"])
    at, c = ATH.rank(entry, snaps, now=NOW, group=ATH.GROUP_AT)
    slip, c2 = ATH.rank(entry, snaps, now=NOW, group=ATH.GROUP_SLIP)
    assert c == c2
    assert c["scanned"] == 13
    assert c["scanned"] == (c["at_ath"] + c["slipping"] + c["at_52w_only"] + c["rest"]
                            + c["stale"] + c["no_print"] + c["no_bars"])
    assert (c["at_ath"], c["slipping"], c["at_52w_only"], c["rest"], c["stale"],
            c["no_print"], c["no_bars"]) == (4, 3, 1, 1, 2, 1, 1)
    assert [r["symbol"] for r in at] == ["THRU", "CLOSE", "NEAR", "NEAR2"]
    assert [r["symbol"] for r in slip] == ["SLIPB", "SLIPA", "SLIPC"]
    assert c["slip_from_52w"] == 3 and c["slip_from_ath"] == 0
    assert c["slip_above_sma50"] == 2                          # 97 > 95, 95 == 95 is not above
    assert c["through_today"] == 1 and c["at_ath_proven"] == 4


def test_09c_slipping_counts_proven_ath_apart_from_high_since():
    """critic 2026-09-29: an unproven 'high since' slip is never counted (or
    worded) as slipped 'from an all-time high'."""
    proven = _read(symbol="PRV", hi_closed=100.0, w52={"price": 100.0, "set_on": _ago(5)},
                   w52_sessions_ago=5, hi_date=_ago(5), hi_sessions_ago=5)
    since = _read(symbol="SNC", hi_closed=100.0, w52={"price": 100.0, "set_on": _ago(5)},
                  w52_sessions_ago=5, hi_date=_ago(5), hi_sessions_ago=5, proven=False,
                  status="history_short", since="2003-09", first_is_month=True,
                  label="High since 2003-09")
    since2 = {**since, "symbol": "SNC2"}
    w52 = _w52_read(3)
    reads = {"PRV": proven, "SNC": since, "SNC2": since2, "W52X": w52}
    snaps = {s: _rth(94.0, ref=97.0) for s in reads}
    rows, c = ATH.rank(_entry_of(reads), snaps, now=NOW, group=ATH.GROUP_SLIP)
    assert c["slipping"] == 4
    assert (c["slip_from_ath"], c["slip_from_high_since"], c["slip_from_52w"]) == (1, 2, 1)
    froms = {r["symbol"]: r["ath"]["slip"]["from"] for r in rows}
    assert froms == {"PRV": "ath", "SNC": "high", "SNC2": "high", "W52X": "52w"}
    h = ATH.header_text(c, group=ATH.GROUP_SLIP, ph="rth", history=None)
    assert "1 slipped from a proven all-time high" in h
    assert "2 from the high since their first bar (not proven all-time)" in h
    assert "1 from a 52-week high only" in h
    # NEGATIVE: the B opener never calls the group "all-time"
    assert "set an all-time" not in h and h.startswith(f"{ATH.SLIP_MARK} 4 names set a high")
    # NEGATIVE: every name unproven -> zero from a proven all-time high
    _r, c2 = ATH.rank(_entry_of({"SNC": since}), {"SNC": _rth(94.0, ref=97.0)}, now=NOW,
                      group=ATH.GROUP_SLIP)
    assert c2["slip_from_ath"] == 0 and c2["slip_from_high_since"] == 1


def test_09d_at_header_states_proven_and_high_since_apart():
    c = {k: 0 for k in ATH.COUNT_KEYS}
    c.update(scanned=9, at_ath=5, at_ath_proven=2, through_today=1)
    h = ATH.header_text(c, group=ATH.GROUP_AT, ph="rth", history=None)
    assert h.startswith(f"{ATH.MARK} 5 names trade at, or within 2% of, their high — ")
    assert "2 at a proven all-time high (full listed history)" in h
    assert "3 at the high since their first bar (not proven all-time)" in h
    # NEGATIVE: the total is never called "their all-time high"
    assert "5 names trade at, or within 2% of, their all-time high" not in h
    # the ↘️ header states the same split for the names it does not list
    hb = ATH.header_text(c, group=ATH.GROUP_SLIP, ph="rth", history=None)
    assert "5 at their high (🏔️ At ATH: 2 proven all-time, 3 high since their first bar)" in hb


def test_09e_note_never_claims_a_blanket_never_count():
    assert "never count" not in ATH.NOTE
    assert "a month-long gap" in ATH.NOTE and "curated cut" in ATH.NOTE
    assert "all-time" in ATH.EMPTY_NOTE_AT and "high since its first bar" in ATH.EMPTY_NOTE_AT
    assert "all-time" not in ATH.EMPTY_NOTE_SLIP


def test_09b_order_keys_directly():
    def a(sym, px, prior):
        return {"symbol": sym, "ath": {"px": px, "hi_prior": prior}}
    rows = [a("B", 99.0, 100.0), a("A", 99.0, 100.0), a("T", 101.0, 100.0), a("C", 98.5, 100.0)]
    assert [r["symbol"] for r in sorted(rows, key=ATH.at_key)] == ["T", "A", "B", "C"]

    def s(sym, d, pct):
        return {"symbol": sym, "ath": {"slip": {"date": d, "pct": pct}}}
    rows = [s("Z", "2026-09-20", -3.0), s("Y", "2026-09-25", -6.0), s("X", "2026-09-25", -2.5),
            s("W", "2026-09-25", -2.5)]
    assert [r["symbol"] for r in sorted(rows, key=ATH.slip_key)] == ["W", "X", "Y", "Z"]


# --------------------------------------------------------------------------
# 10 — the verify phases
# --------------------------------------------------------------------------
def test_10_verify_phases():
    entry = _entry_of({"MISM": _read(), "NOROW": _read(), "NOREF": _read(ref_close=None)})
    snaps = {"MISM": _rth(99.0, ref=97.0, pdc=90.0, close=90.5),
             "NOREF": _rth(99.0, ref=97.0)}
    rows, c = ATH.rank(entry, snaps, now=NOW, group=ATH.GROUP_AT)
    assert rows == [] and c["stale"] == 2 and c["no_print"] == 1
    # an empty snapshot row (every field None) is no print either
    rows, c = ATH.rank(_entry_of({"E": _read()}), {"E": {}}, now=NOW, group=ATH.GROUP_AT)
    assert c["no_print"] == 1


# --------------------------------------------------------------------------
# 11 — board()
# --------------------------------------------------------------------------
class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture
def ath_board(monkeypatch):
    from sepa import scanner
    state = {"frames": {}, "snaps": {}, "docs": {}, "listing": {}, "snap_calls": [],
             "finish_tiles": []}

    def _snaps(syms):
        state["snap_calls"].append(sorted(syms))
        return {s: state["snaps"][s] for s in syms if s in state["snaps"]}

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": LAST, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    real_finish = B._finish

    def _finish_spy(tiles, *a, **k):
        state["finish_tiles"].append([dict(t) for t in tiles])
        return real_finish(tiles, *a, **k)

    real_build = ATH.build

    def fake_build(universe, session, **k):
        return real_build(universe, session, universe_fn=lambda u: list(state["frames"]),
                          frames_fn=lambda syms: {s: state["frames"][s] for s in syms
                                                  if s in state["frames"]},
                          history_fn=lambda syms: dict(state["docs"]),
                          listing_fn=lambda syms: dict(state["listing"]))

    monkeypatch.setattr(ATH, "build", fake_build)
    monkeypatch.setattr(B, "datetime", _Fixed)
    monkeypatch.setattr(B, "_bulk_snaps", _snaps)
    monkeypatch.setattr(B, "_finish", _finish_spy)
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": []})
    monkeypatch.setattr(B, "_attach_bars", _bars)
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_enterable", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(B, "attach_burst", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(B, "attach_key_levels", lambda tiles, out=None, **k: None)

    def seed(frames, snaps, docs=None, listing=None):
        state.update(frames=frames, snaps=snaps, docs=docs or {}, listing=listing or {})
        ATH.cached_or_warm("full", now=NOW, sync=True)
    state["seed"] = seed
    return state


def _board_seed(ath_board):
    vol = 5_000_000.0                  # 90 x 5M = $450M/day, over every floor
    frames = {"ATHX": _frame(volume=vol, sets={_ago(4): {"high": 100.0}}),
              "SLPX": _frame(volume=vol, sets={_ago(4): {"high": 100.0}}),
              "FARX": _frame(volume=vol, sets={_ago(100): {"high": 100.0}})}
    snaps = {"ATHX": _rth(99.5, ref=90.0), "SLPX": _rth(94.0, ref=90.0),
             "FARX": _rth(70.0, ref=90.0)}
    listing = {s: DAYS[-300] for s in frames}
    docs = {s: _doc(s, hi=float(df["high"].max()), hi_month="2026-08",
                    first_bar=DAYS[-300][:8] + "01", check_high=_aug_high(df))
            for s, df in frames.items()}
    ath_board["seed"](frames, snaps, docs=docs, listing=listing)


def test_11_board_groups_sorts_and_notes(ath_board):
    _board_seed(ath_board)
    a = B.board(tab="ath", limit=24)
    assert a["tab"] == "ath" and a["sort"] == "default"
    assert [t["symbol"] for t in a["tiles"]] == ["ATHX"]
    assert a["sorts"] == [{"key": "default", "label": ATH.AT_ATH_LABEL},
                          {"key": "slipping", "label": ATH.SLIPPING_LABEL}]
    t = a["tiles"][0]
    assert t["ath"]["text"] == t["badges"][0]["text"] and t["badges"][0]["tone"] == "good"
    assert t["lines"] == [{"price": 100.0, "label": "ATH", "tone": "neutral"}]
    assert t["ath"]["group"] == "at_ath" and t["ath"]["proven"] is True
    ab = a["ath_board"]
    assert ab["state"] == "ready" and ab["group"] == "at_ath" and ab["measured"] is False
    assert ab["band_pct"] == ATH.BAND_PCT and ab["lookback_sessions"] == 21
    assert ab["counts"]["scanned"] == 3 and ab["counts"]["shown"] == 1
    assert a["note"] == ATH.NOTE
    assert len(ath_board["snap_calls"]) == 1                      # the ONE fan-out

    b = B.board(tab="ath", sort="slipping", limit=24)
    assert b["sort"] == "slipping" and [t["symbol"] for t in b["tiles"]] == ["SLPX"]
    assert b["tiles"][0]["badges"][0]["tone"] == "warn"
    assert b["ath_board"]["group"] == "slipping"
    assert b["ath_board"]["header"].startswith(f"{ATH.SLIP_MARK} 1 names set")


def test_11g_snapshot_fanout_equals_the_serial_read(monkeypatch):
    """critic 2026-09-29 #6: the universe snapshot was 3.8 s of a 4.6 s warm
    request (11 chunks one after another). The fan-out fetches the same
    chunks side by side; the merged map must be exactly the serial one."""
    monkeypatch.setattr(prices, "_SNAP_CHUNK", 3)
    calls = []

    def fake_bulk(syms):
        calls.append(list(syms))
        return {s: {"close": float(len(s)), "chunk": len(syms)} for s in syms if s != "MISS"}
    monkeypatch.setattr(prices, "bulk_snapshot", fake_bulk)
    syms = ["b", "A", "C", "D", "E", "F", "G", "MISS", "A", ""]
    fan = B._bulk_snaps_fanout(syms)
    calls_fan = sorted(calls)
    calls.clear()
    monkeypatch.setattr(prices, "_SNAP_CHUNK", 250)
    serial = B._bulk_snaps(syms)
    assert set(fan) == set(serial) == {"A", "B", "C", "D", "E", "F", "G"}
    assert {k: v["close"] for k, v in fan.items()} == {k: v["close"] for k, v in serial.items()}
    assert calls_fan == [["A", "B", "C"], ["D", "E", "F"], ["G", "MISS"]]   # every chunk once
    # NEGATIVE: one failing chunk loses only its own names (the serial call's failure mode)
    monkeypatch.setattr(prices, "_SNAP_CHUNK", 3)

    def flaky(syms):
        if "D" in syms:
            raise RuntimeError("boom")
        return fake_bulk(syms)
    monkeypatch.setattr(prices, "bulk_snapshot", flaky)
    part = B._bulk_snaps_fanout(syms)
    assert set(part) == {"A", "B", "C", "G"}
    # NEGATIVE: empty in, empty out; one chunk is the plain call
    assert B._bulk_snaps_fanout([]) == {} and B._bulk_snaps_fanout(None) == {}
    calls.clear()
    monkeypatch.setattr(prices, "bulk_snapshot", fake_bulk)
    assert set(B._bulk_snaps_fanout(["X", "Y"])) == {"X", "Y"} and calls == [["X", "Y"]]
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    body = src[src.index("def ath_tiles("):src.index("def _usd_short(")]
    assert "_bulk_snaps_fanout(entry[\"syms\"])" in body and "_bulk_snaps(entry" not in body


def test_11b_NEGATIVE_unknown_sort_is_A_and_slipping_is_tab_scoped(ath_board):
    _board_seed(ath_board)
    bogus = B.board(tab="ath", sort="bogus", limit=24)
    assert bogus["sort"] == "default" and [t["symbol"] for t in bogus["tiles"]] == ["ATHX"]
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    assert '(t == "ath" and sort == _ATH.SORT_SLIPPING)' in src
    assert 'elif t == "ath":' in src


def test_11c_NEGATIVE_slipping_on_key_levels_is_the_default(monkeypatch):
    seen = []
    monkeypatch.setattr(B, "key_level_tiles",
                        lambda limit, days, universe, tf, srt, tier, ctx=None:
                        seen.append(srt) or {"tiles": []})
    out = B.board(tab="key_levels", sort="slipping")
    assert seen == ["default"] and out["sort"] == "default"


def test_11d_empty_groups_say_the_group_sentence(ath_board):
    frames = {"FARX": _frame(volume=5e6, sets={_ago(100): {"high": 100.0}})}
    ath_board["seed"](frames, {"FARX": _rth(70.0, ref=90.0)}, listing={"FARX": DAYS[-300]})
    a = B.board(tab="ath", limit=24)
    assert a["tiles"] == [] and a["note"] == ATH.EMPTY_NOTE_AT
    b = B.board(tab="ath", sort="slipping", limit=24)
    assert b["tiles"] == [] and b["note"] == ATH.EMPTY_NOTE_SLIP


def test_11e_no_flat_attach_owned_keys_reach_finish(ath_board):
    _board_seed(ath_board)
    B.board(tab="ath", limit=24)
    handed = ath_board["finish_tiles"][-1]
    assert handed
    for t in handed:
        for k in B.ATTACH_OWNED_KEYS:
            assert k not in t, k


def test_11f_warming_board(monkeypatch, _clean):
    monkeypatch.setattr(ATH, "build", lambda *a, **k: _entry_of({}))
    out = B.ath_tiles(24, 130, "full", now=NOW, sort="slipping")
    assert out["tiles"] == [] and out["warming"] is True and out["note"] == ATH.WARMING_NOTE
    wb = out["ath_board"]
    assert wb["state"] == "warming" and wb["counts"] is None and wb["group"] == "slipping"
    assert wb["header"] == ATH.WARMING_NOTE and set(wb) == set(ATH.ready_block(
        {}, now=NOW, session=SESSION, ph="rth", group="at_ath", built_at=None, history={}))


# --------------------------------------------------------------------------
# 12 — memo + filler
# --------------------------------------------------------------------------
def _patch_build(monkeypatch, frames, docs=None):
    real = ATH.build

    def fake(universe, session, **k):
        return real(universe, session, universe_fn=lambda u: list(frames),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    history_fn=lambda syms: dict(docs or {}), listing_fn=lambda syms: {})
    monkeypatch.setattr(ATH, "build", fake)


def test_12_warming_then_ready_and_the_filler_spawns_once(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame(), "BBB": _frame()})
    got = ATH.cached_or_warm("full", now=NOW)
    assert got == {"state": "warming", "entry": None}
    assert [n for _t, n in _clean] == [f"ath-tab-{SESSION.isoformat()}-full"]
    _clean[0][0]()                                        # run the background build
    got = ATH.cached_or_warm("full", now=NOW)
    assert got["state"] == "ready" and set(got["entry"]["reads"]) == {"AAA", "BBB"}
    assert got["entry"]["pending"] == [("AAA", "missing"), ("BBB", "missing")]
    assert [n for _t, n in _clean][-1] == "ath-history-fill" and ATH.filling()
    # a second background build while the filler runs never spawns a second one
    ATH._memo.clear()
    ATH.cached_or_warm("full", now=NOW)
    _clean[-1][0]()
    assert [n for _t, n in _clean].count("ath-history-fill") == 1


def test_12b_the_filler_writes_then_invalidates(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame()})
    ATH.cached_or_warm("full", now=NOW)
    _clean[0][0]()
    fill_target = _clean[-1][0]
    monkeypatch.setattr(AH, "fill", lambda names, **k: (k["on_progress"](len(names)),
                                                        {"asked": 1, "ok": 0, "empty": 0,
                                                         "error": 1,
                                                         "error_symbols": ["AAA"]})[1])
    fill_target()
    assert not ATH.filling()
    assert all(e["built_ts"] == 0 for e in ATH._memo.values())
    # a name whose fetch failed this session waits for the next session
    assert ATH._maybe_fill([("AAA", "missing")], session_iso=SESSION.isoformat()) is False
    assert ATH._maybe_fill([("AAA", "missing")], session_iso="2026-09-30") is True


def test_12c_NEGATIVE_sync_never_spawns(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame()})
    got = ATH.cached_or_warm("full", now=NOW, sync=True)
    assert got["state"] == "ready" and got["entry"]["pending"] == [("AAA", "missing")]
    assert _clean == []


def test_12d_empty_frames_read_raises_and_is_not_memoised(monkeypatch, _clean):
    real = ATH.build
    with pytest.raises(RuntimeError, match="not memoising an empty read"):
        real("full", SESSION, universe_fn=lambda u: ["AAA"], frames_fn=lambda s: {},
             history_fn=lambda s: {}, listing_fn=lambda s: {})
    monkeypatch.setattr(ATH, "build", lambda *a, **k: real(
        "full", SESSION, universe_fn=lambda u: ["AAA"], frames_fn=lambda s: {},
        history_fn=lambda s: {}, listing_fn=lambda s: {}))
    ATH.cached_or_warm("full", now=NOW)
    _clean[0][0]()
    assert ATH._memo == {} and ATH._warming == set()
    assert all(n != "ath-history-fill" for _t, n in _clean)


def test_12e_a_late_older_session_build_is_dropped(monkeypatch, _clean):
    _patch_build(monkeypatch, {"AAA": _frame()})
    newer = ("2026-09-30", "full")
    ATH._memo[newer] = {"built_ts": 1e18, "sentinel": True}
    ATH._warm(("2026-09-29", "full"), "full", SESSION)
    _clean[0][0]()
    assert list(ATH._memo) == [newer] and ATH._memo[newer]["sentinel"]
    assert all(n != "ath-history-fill" for _t, n in _clean)


# --------------------------------------------------------------------------
# 13 — words
# --------------------------------------------------------------------------
def test_13_words_are_built_from_the_constants():
    assert "UNMEASURED" in ATH.NOTE and ATH.MEASURED is False
    counts = {k: 1 for k in ATH.COUNT_KEYS}
    for g in (ATH.GROUP_AT, ATH.GROUP_SLIP):
        h = ATH.header_text(counts, group=g, ph="rth", history={"read": 5, "pending": 2})
        assert "2%" in h and "2 names waiting for history — full history read for 5 of 1" in h
        assert "loading in the background" not in h
        assert "live print" in h
    served = [ATH.NOTE, ATH.WARMING_NOTE, ATH.EMPTY_NOTE_AT, ATH.EMPTY_NOTE_SLIP,
              ATH.AT_ATH_LABEL, ATH.SLIPPING_LABEL,
              ATH.header_text(counts, group="at_ath", ph=None, history=None)]
    for s in served:
        assert not re.search(r"bounc|fake", s, re.I), s
    assert f"within {ATH.BAND_PCT:g}%" in ATH.EMPTY_NOTE_AT
    assert f"last {ATH.SLIP_LOOKBACK_SESSIONS} sessions" in ATH.EMPTY_NOTE_SLIP
    assert "waiting for history" not in ATH.header_text(counts, group="at_ath", ph=None,
                                                        history={"read": 3, "pending": 0})
    filling = ATH.header_text(counts, group="at_ath", ph=None,
                              history={"read": 3, "pending": 4, "filling": True})
    assert "4 names waiting for history (loading in the background now)" in filling
    assert "never called all-time" in filling


def test_13b_band_is_not_typed(monkeypatch):
    monkeypatch.setattr(ATH, "AT_ATH_TOL", 0.95)
    h = ATH.header_text({}, group="at_ath", ph=None, history=None)
    assert "within 5% of" in h and "2%" not in h
    src = (BACKEND / "chart_maps" / "ath_tab.py").read_text(encoding="utf-8")
    assert "0.98" not in src and "from supply_demand.zone_edge import NEW_HIGH_TOL" in src
    from supply_demand.zone_edge import NEW_HIGH_TOL
    assert ATH.BAND_PCT == round((1 - NEW_HIGH_TOL) * 100, 2)


def test_13c_module_words_never_say_bounce_or_fake_and_it_writes_nothing():
    src = (BACKEND / "chart_maps" / "ath_tab.py").read_text(encoding="utf-8")
    assert not re.search("bounc|fake", src.replace("quick_bounce", ""), re.I)
    assert not re.search(r"insert_|update_one|replace_one|delete_|bulk_write|create_index|open\(",
                         src)
    assert "KL.anchor_read" in src and "KL.verify_last" in src
    assert "bulk_cached_frames" in src and "UNMEASURED" in src


# --------------------------------------------------------------------------
# 14 — source guard
# --------------------------------------------------------------------------
def test_14_no_trading_push_or_scanner_module_imports_the_tab():
    targets = list((BACKEND / "trading").rglob("*.py")) + list((BACKEND / "push").rglob("*.py"))
    targets.append(BACKEND / "sepa" / "scanner.py")
    pat = re.compile(r"\bath_tab\b|\bath_history\b")
    hits = [p.relative_to(BACKEND).as_posix() for p in targets
            if p.exists() and pat.search(p.read_text(encoding="utf-8"))]
    assert hits == []
    assert len(targets) > 3


# --------------------------------------------------------------------------
# 15 — TABS
# --------------------------------------------------------------------------
def test_15_ath_sits_right_after_dual_momentum():
    assert B.TABS.index("ath") == B.TABS.index("dual_momentum") + 1
    # 🛡️ resiliency was appended right after ath on 2026-09-30, 📉 fallen right
    # after resiliency on 2026-10-02, 🔻 drop10 right after fallen on 2026-10-05
    assert B.TABS[-4:] == ("ath", "resiliency", "fallen", "drop10")
    from supply_demand import enterable as EN
    assert "ath" not in EN.KIND_BY_TAB                           # 🎯 n/a (HIS CALL #8)


def test_11h_NEG_header_says_one_name_not_one_names_and_the_card_never_claims_a_load():
    txt = ATH.header_text({"scanned": 10}, group=ATH.GROUP_AT, ph=None,
                         history={"pending": 1, "read": 9, "filling": True})
    assert " 1 name waiting for history" in txt and "1 names" not in txt
    txt2 = ATH.header_text({"scanned": 10}, group=ATH.GROUP_AT, ph=None,
                          history={"pending": 2, "read": 8, "filling": False})
    assert " 2 names waiting for history" in txt2
    import inspect
    assert "full history loading" not in inspect.getsource(ATH)
