"""chart_maps/gajjala/ledger.py — 🏁 Track record (BUILD_SPEC9 §3.2–§3.7 as amended by AMENDMENTS9 E1–E9, 2026-10-16).

Ajay 2026-10-16: "also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To see a percentage
and the ticker." / "We are not looking for winners just in time but when they got in to our alerts if they made it or
not. Like XLAB today was a winner I made good money on it". Knobs: "GG's trade math", "Both columns", Q0 "Keep GG's
math", E1 "From 09:45 ET only".

Every store is the in-memory FakeColl set (tests/conftest.py refuses a real MongoClient); every loader is injected —
never the network. The REAL tape is tests/fixtures/gajjala/xlab_2026_10_16_1m.json (a byte copy of the read-only probe,
never hand-edited); every other path is SYNTHETIC and named so. NEGATIVES are mandatory and marked.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D15, D16, D19 = date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 19)     # Thu, Fri, Mon
HALF = date(2026, 11, 27)                                                         # supply_demand.timeframes.HALF_DAYS
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "xlab_2026_10_16_1m.json"
B_WORD = re.compile("b" + "ounc", re.I)
SEPA_NAMES = re.compile(r"\bSEPA\b|minervini|bonde|\bTLSW\b|\bTTLAC\b", re.I)
HF_AT = "2026-10-16T12:51:00.771870+00:00"            # the XLAB ➖ ring as on file (BUILD_SPEC9 §1.2)
VCP_AT = "2026-10-16T13:01:00.983961+00:00"           # the XLAB 🌀 ring as on file


@pytest.fixture(autouse=True)
def _clean_memo(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    yield
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def et(d, hh, mm, ss=0, us=0) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, ss, us, tzinfo=ET).astimezone(UTC)


def bar(d, hh, mm, o, h, lo, c) -> tuple:
    return (et(d, hh, mm), float(o), float(h), float(lo), float(c))


def flat(d, start, end, px) -> list:
    """SYNTHETIC o=h=l=c=px minutes from `start` to `end` inclusive ((hh, mm) tuples, ET)."""
    out, t, stop = [], et(d, *start), et(d, *end)
    while t <= stop:
        out.append((t, float(px), float(px), float(px), float(px)))
        t += timedelta(minutes=1)
    return out


def path(*parts) -> list:
    return LG._merge(*parts)


def pot_doc(sym, setup, d, at, trig, stop, *, px=None, first_seen_et=None, at_et=None, mode="normal",
            state="pushed", push_extra=None):
    at_s = at if isinstance(at, str) or at is None else at.isoformat()
    at_et = at_et or (LG._parse_at(at_s).astimezone(ET).strftime("%H:%M") if LG._parse_at(at_s) else None)
    push = {"state": state, "at": at_s, "at_et": at_et, "kind_at_push": "building"}
    if at_s is None:
        push.pop("at")
    push.update(push_extra or {})
    return {"_id": ST.potential_key(d, sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "first_seen_et": first_seen_et or at_et, "first_seen_mode": mode, "first_px": px,
            "first_trigger": trig, "first_stop": stop, "push": push,
            "url": f"/chart-maps?tab=gajjala&sub={setup}&focus={sym}"}


def aplus_doc(sym, setup, d, at, trig, stop, *, state="shadow", price=None, prefix="SHADOW:"):
    key = f"GG:{d.isoformat()}|{sym}|{setup}"
    _id = (prefix + key) if state == "shadow" else key
    return {"_id": _id, "date": d.isoformat(), "symbol": sym, "setup": setup, "trigger": trig, "stop": stop,
            "price": price, "state": state, "at": at if isinstance(at, str) or at is None else at.isoformat(),
            "would_push": {"title": "x"}}


def store_with(pots=(), alerts=(), ledger=()):
    return fake_store(**{ST.POTENTIALS: FakeColl(list(pots)), ST.ALERTS: FakeColl(list(alerts)),
                         ST.LEDGER: FakeColl(list(ledger))})


def row_of(doc, kind="potential"):
    r = LG.alert_of(doc, kind)
    assert r is not None
    return r


def xlab_bars() -> list:
    """The REAL tape (read-only probe 2026-10-16 ~12:25 ET, 04:00–11:10 ET) through the loader's own DataFrame shape."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    df = pd.DataFrame(raw["bars"])
    df["ts_utc"] = pd.to_datetime(df["ts_utc"])
    return LG.bars_from_frame(df.set_index("ts_utc"))


def synthetic_xlab() -> list:
    """SYNTHETIC XLAB 10-16 path (the main session's, E1-shaped): highs ≥ both triggers at 08:51 / 08:55 / 09:18 / 09:30
    (all before 09:45), the 09:45 minute 1.80/1.855/1.79/1.84, the 09:50 minute high EXACTLY 1.95, 10:14 high 3.8399,
    15:59 close 2.71, and a 16:00 after-hours print (the closing cross minute) high 5.00."""
    d = D16
    return path([bar(d, 8, 50, 1.73, 1.80, 1.71, 1.79), bar(d, 8, 51, 1.79, 1.85, 1.78, 1.80),
                 bar(d, 8, 52, 1.80, 1.80, 1.76, 1.78), bar(d, 8, 53, 1.78, 1.79, 1.75, 1.77),
                 bar(d, 8, 54, 1.77, 1.79, 1.76, 1.78), bar(d, 8, 55, 1.78, 1.85, 1.77, 1.83)],
                flat(d, (8, 56), (9, 44), 1.80),
                [bar(d, 9, 18, 1.83, 1.855, 1.82, 1.84), bar(d, 9, 30, 1.85, 1.95, 1.84, 1.90),
                 bar(d, 9, 45, 1.80, 1.855, 1.79, 1.84)],
                flat(d, (9, 46), (9, 49), 1.84), [bar(d, 9, 50, 1.86, 1.95, 1.85, 1.90)],
                flat(d, (9, 51), (15, 58), 2.50), [bar(d, 10, 14, 3.11, 3.8399, 3.00, 3.63),
                                                   bar(d, 15, 59, 2.70, 2.72, 2.68, 2.71),
                                                   bar(d, 16, 0, 2.71, 5.00, 2.70, 2.80)])


HF = lambda: row_of(pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70, px=1.73))           # noqa: E731
VCP = lambda: row_of(pot_doc("XLAB", "intraday_vcp", D16, VCP_AT, 1.85, 1.75, px=1.7901))         # noqa: E731


def g_of(row, bars, h="same", **cut):
    b = LG.session_bounds(row["date"], row["at_utc"])
    b.update(cut)
    return LG.grade(row, bars, b, h)


def t_et(iso):
    return LG._parse_at(iso).astimezone(ET).strftime("%H:%M")


# ── the grader: SYNTHETIC XLAB (E1: fills from 09:45 ET only) ────────────────────────────────────────────────────
def test_synthetic_xlab_hf_fills_at_0945_at_the_trigger_and_wins():
    g = g_of(HF(), synthetic_xlab())
    assert (g["entry"], g["fill_px"], t_et(g["fill_t"])) == ("filled", 1.81, "09:45")
    assert (g["target_px"], g["outcome"], t_et(g["exit_t"]), g["reason"]) == (1.92, "win", "09:50", "target")
    assert (g["best_pct"], g["close_pct"]) == (112.15, 49.72)


def test_synthetic_xlab_vcp_wins_on_a_high_EQUAL_to_the_target_the_decimal_pin():
    g = g_of(VCP(), synthetic_xlab())
    assert (g["fill_px"], t_et(g["fill_t"]), g["target_px"]) == (1.85, "09:45", 1.95)
    assert (g["outcome"], t_et(g["exit_t"])) == ("win", "09:50")
    assert (g["best_pct"], g["close_pct"]) == (107.56, 46.49)
    assert not (1.95 >= 1.85 + (1.85 - 1.75)), "the binary-float trap the Decimal compare exists for"


def test_NEGATIVE_synthetic_highs_before_0945_never_fill():
    """08:51 (high 1.85 ≥ 1.81, also before alert + 30 s), 08:55, 09:18 and 09:30 all trade through the triggers —
    none is a fill under "From 09:45 ET only"."""
    for row in (HF(), VCP()):
        g = g_of(row, synthetic_xlab())
        assert LG._parse_at(g["fill_t"]) == et(D16, 9, 45)
    early = [b for b in synthetic_xlab() if b[0] < et(D16, 9, 45)]
    assert LG.grade(HF(), early, LG.session_bounds("2026-10-16", HF()["at_utc"]), "same")["entry"] == "no_entry"


def test_NEGATIVE_the_same_column_excludes_the_1600_minute():
    g = g_of(HF(), synthetic_xlab())
    assert LG._parse_at(g["through_t"]) == et(D16, 16, 0) and g["best_pct"] == 112.15   # the 16:00 high 5.00 is out
    assert LG._parse_at(g["end_t"]) == et(D16, 16, 0)


# ── the grader: the REAL tape ────────────────────────────────────────────────────────────────────────────────────
def test_real_tape_xlab_both_alerts_fill_0945_at_189_and_win():
    """E1 replay facts: ➖ 08:51 and 🌀 09:01 both fill 09:45 @1.89 (the open, above both triggers) and WIN."""
    bars = xlab_bars()
    assert len(bars) == 418
    hf, vcp = g_of(HF(), bars), g_of(VCP(), bars)
    for g in (hf, vcp):
        assert (g["entry"], g["fill_px"], t_et(g["fill_t"])) == ("filled", 1.89, "09:45")
        assert g["outcome"] == "win" and g["best_pct"] == 103.17
    assert (hf["target_px"], t_et(hf["exit_t"])) == (2.0, "09:49")
    assert (vcp["target_px"], t_et(vcp["exit_t"])) == (1.99, "09:48")        # 09:48 high 1.99 == 1.89 + 0.10


def test_NEGATIVE_real_tape_the_premarket_prints_are_no_position():
    """Before 09:45 the tape printed 1.85 (08:51/08:52) through both triggers and 1.69 (09:07) under the ➖ stop — no
    fill, so neither is a LOSS."""
    bars = xlab_bars()
    pre = [b for b in bars if b[0] < et(D16, 9, 45)]
    assert max(b[2] for b in pre) >= 1.85 and min(b[3] for b in pre) < 1.70
    assert g_of(HF(), pre)["entry"] == "no_entry"
    assert g_of(HF(), bars)["outcome"] == "win"


def test_real_tape_the_vcp_wins_on_the_0948_high_EQUAL_to_its_target():
    bars = xlab_bars()
    (b0948,) = [b for b in bars if b[0] == et(D16, 9, 48)]
    g = g_of(VCP(), bars)
    assert b0948[2] == g["target_px"] == 1.99 and t_et(g["exit_t"]) == "09:48"     # ≥, equality wins
    before = [b for b in bars if et(D16, 9, 45) < b[0] < et(D16, 9, 48)]
    assert max(b[2] for b in before) < 1.99


# ── the grader: the 10-15 15:11 alert (SYNTHETIC path, E1 replay facts) ──────────────────────────────────────────
def _xlab_1015_rows_and_bars():
    at = et(D15, 15, 11, 0, 500000)
    row = row_of(pot_doc("XLAB", "intraday_vcp", D15, at, 1.22, 1.16, px=1.19))
    day1 = path(flat(D15, (15, 10), (15, 20), 1.20), [bar(D15, 15, 21, 1.20, 1.23, 1.19, 1.22),
                                                       bar(D15, 15, 22, 1.22, 1.29, 1.21, 1.27)],
                flat(D15, (15, 23), (15, 59), 1.25), flat(D15, (16, 0), (19, 59), 1.30))
    day2 = path(flat(D16, (4, 0), (9, 29), 1.50), flat(D16, (9, 30), (15, 59), 2.50),
                [bar(D16, 10, 14, 3.11, 3.8399, 3.00, 3.63), bar(D16, 15, 59, 2.70, 2.72, 2.68, 2.71)])
    return row, day1, day2


def test_synthetic_1015_1511_alert_fills_1521_wins_1522_and_runs_215pct_next_session():
    row, day1, day2 = _xlab_1015_rows_and_bars()
    assert row["rang"] == "rth"
    same = g_of(row, day1)
    assert (same["fill_px"], t_et(same["fill_t"]), same["target_px"]) == (1.22, "15:21", 1.28)
    assert (same["outcome"], t_et(same["exit_t"])) == ("win", "15:22")
    nxt = g_of(row, path(day1, day2), "next")
    assert (nxt["outcome"], nxt["exit_t"], nxt["fill_t"]) == ("win", same["exit_t"], same["fill_t"])
    assert nxt["best_pct"] == 214.75 and LG._parse_at(nxt["end_t"]) == et(D16, 16, 0)


# ── the grader: rules (SYNTHETIC) ────────────────────────────────────────────────────────────────────────────────
A = date(2026, 10, 14)                                     # a Wednesday


def _row(trig=10.0, stop=9.0, at=None, d=A, sym="AAA", setup="bull_flag"):
    return row_of(pot_doc(sym, setup, d, at or et(d, 10, 30, 5), trig, stop))


def _rth(*bars_, pad=9.5):
    return path(flat(A, (10, 31), (15, 59), pad), list(bars_))


def test_loss_path_stop_after_the_fill():
    g = g_of(_row(), _rth(bar(A, 10, 40, 9.9, 10.1, 9.8, 10.0), bar(A, 10, 50, 9.5, 9.6, 8.9, 9.0)))
    assert (g["outcome"], g["reason"], t_et(g["exit_t"]), g["fill_px"]) == ("loss", "stop", "10:50", 10.0)


def test_NEGATIVE_a_bar_with_both_the_target_and_the_stop_is_a_loss():
    g = g_of(_row(), _rth(bar(A, 10, 40, 9.9, 10.1, 9.8, 10.0), bar(A, 10, 41, 10.0, 11.5, 8.5, 10.0)))
    assert (g["outcome"], t_et(g["exit_t"])) == ("loss", "10:41")


def test_NEGATIVE_a_stop_in_the_fill_minute_is_a_loss():
    g = g_of(_row(), _rth(bar(A, 10, 40, 9.9, 10.2, 8.9, 9.1)))
    assert (g["outcome"], g["reason"]) == ("loss", "stop_fill_minute")


def test_NEGATIVE_the_fill_minutes_high_never_counts_toward_the_win():
    g = g_of(_row(), path(flat(A, (10, 31), (15, 59), 9.5), [bar(A, 10, 40, 9.9, 11.5, 9.8, 10.5)]))
    assert (g["outcome"], g["reason"]) == ("open", "horizon_end") and g["best_pct"] == 15.0


def test_a_gap_fills_at_the_open_and_the_target_is_the_open_plus_r():
    g = g_of(_row(), _rth(bar(A, 10, 40, 10.5, 10.6, 10.4, 10.5), bar(A, 10, 41, 10.5, 11.5, 10.4, 11.4)))
    assert (g["fill_px"], g["target_px"], g["outcome"]) == (10.5, 11.5, "win")


def test_NEGATIVE_no_entry_when_the_trigger_prints_only_before_alert_plus_settle():
    row = _row(at=et(A, 10, 30, 10))                       # the 10:30 minute starts before 10:30:40
    g = g_of(row, path([bar(A, 10, 30, 9.9, 10.5, 9.8, 10.2)], flat(A, (10, 31), (15, 59), 9.5)))
    assert (g["entry"], g["reason"], g["best_pct"], g["close_pct"]) == ("no_entry", "no_entry", None, None)


def test_NEGATIVE_no_entry_when_the_trigger_never_prints():
    assert g_of(_row(), flat(A, (10, 31), (15, 59), 9.5))["entry"] == "no_entry"


@pytest.mark.parametrize("trig,stop,want", [(None, 9.0, "no_plan"), (10.0, None, "no_plan"), (9.0, 10.0, "no_plan"),
                                            (float("nan"), 9.0, "no_plan"), (10.0, 10.0, "no_risk")])
def test_NEGATIVE_no_plan_and_no_risk_are_never_filled(trig, stop, want):
    row = row_of(pot_doc("AAA", "bull_flag", A, et(A, 10, 30), trig, stop))
    assert row["plan"] == want and row["r"] is None
    g = g_of(row, _rth(bar(A, 10, 40, 9.9, 12.0, 9.8, 10.0)))
    assert (g["entry"], g["outcome"]) == (want, None)


def test_thin_r_is_flagged_and_still_graded():
    row = row_of(pot_doc("TTT", "bull_flag", A, et(A, 10, 30), 0.543, 0.5429))
    assert row["thin"] is True and row["plan"] == "ok" and row["r_pct"] < GC.LEDGER_MIN_R_PCT
    g = g_of(row, path(flat(A, (10, 31), (15, 59), 0.54), [bar(A, 10, 40, 0.542, 0.5432, 0.5431, 0.5432)]))
    assert g["entry"] == "filled"
    assert row_of(pot_doc("TTT", "bull_flag", A, et(A, 10, 30), 0.543, 0.52))["thin"] is False


def test_an_after_hours_alert_fills_in_the_next_session_never_on_its_own_evening():
    row = row_of(pot_doc("AAA", "bull_flag", D15, et(D15, 17, 30), 10.0, 9.0))
    assert row["rang"] == "ah"
    b = LG.session_bounds(D15, row["at_utc"])
    assert (b["same_date"], b["same_end"], b["next_date"]) == (D16, et(D16, 16, 0), D19)
    bars = path([bar(D15, 17, 45, 9.9, 10.5, 9.8, 10.2)], flat(D16, (4, 0), (9, 44), 10.4),
                [bar(D16, 9, 45, 10.3, 10.4, 10.2, 10.3)], flat(D16, (9, 46), (15, 59), 10.35))
    g = LG.grade(row, bars, b, "same")
    assert (g["fill_px"], LG._parse_at(g["fill_t"])) == (10.3, et(D16, 9, 45))      # 17:45 and pre-market: no fill
    assert g["end_date"] == "2026-10-16"


def test_NEGATIVE_a_premarket_alert_never_fills_before_0945_and_ends_at_1600():
    row = row_of(pot_doc("AAA", "bull_flag", A, et(A, 6, 0), 10.0, 9.0))
    assert row["rang"] == "pre"
    bars = path(flat(A, (6, 1), (9, 44), 10.5), flat(A, (9, 45), (15, 59), 9.5), flat(A, (16, 0), (19, 59), 10.5))
    g = g_of(row, bars)
    assert g["entry"] == "no_entry" and LG._parse_at(g["end_t"]) == et(A, 16, 0)


def test_rang_chips_from_the_alerts_own_stamp():
    assert [LG.rang_of(A, et(A, h, m)) for h, m in ((9, 29), (9, 30), (15, 59), (16, 0))] == ["pre", "rth", "rth", "ah"]
    assert LG.RANG_TEXT == {"pre": "rang pre", "rth": "rang RTH", "ah": "rang AH"}
    assert LG.rang_of(A, None) is None


def test_half_day_ends_1300_and_its_fill_window_too():
    b = LG.session_bounds(HALF, et(HALF, 10, 0))
    assert b["same_end"] == et(HALF, 13, 0) and LG.fill_window(HALF)[1].hour == 13
    after = LG.session_bounds(HALF, et(HALF, 13, 30))
    assert after["same_date"] == date(2026, 11, 30)
    row = row_of(pot_doc("AAA", "bull_flag", HALF, et(HALF, 10, 0), 10.0, 9.0))
    bars = path(flat(HALF, (10, 1), (12, 59), 9.5), [bar(HALF, 13, 30, 10.0, 10.5, 9.9, 10.1)])
    nxt = LG.grade(row, bars, b, "next")
    assert nxt["entry"] == "no_entry"                       # 13:30 on a half day is after the regular session


def test_same_no_entry_fills_in_the_next_column_on_day_2():
    row = row_of(pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0))
    bars = path(flat(D15, (11, 1), (19, 59), 9.5), flat(D16, (4, 0), (9, 59), 9.6),
                [bar(D16, 10, 0, 9.9, 10.2, 9.8, 10.1)], flat(D16, (10, 1), (15, 59), 10.3))
    assert g_of(row, bars)["entry"] == "no_entry"
    nxt = g_of(row, bars, "next")
    assert (nxt["entry"], nxt["outcome"], LG._parse_at(nxt["fill_t"])) == ("filled", "flat", et(D16, 10, 0))
    assert nxt["close_pct"] == 3.0 and nxt["end_date"] == "2026-10-16"


def test_next_flat_carries_a_signed_close():
    row = row_of(pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0))
    bars = path([bar(D15, 11, 1, 10.0, 10.1, 9.9, 10.0)], flat(D15, (11, 2), (19, 59), 9.8),
                flat(D16, (4, 0), (15, 59), 9.4))
    nxt = g_of(row, bars, "next")
    assert (nxt["outcome"], nxt["close_pct"]) == ("flat", -6.0)


@pytest.mark.parametrize("variant", ["win", "loss"])
def test_property_a_decided_same_column_equals_its_next_rewalk(variant):
    row = row_of(pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0))
    exit_bar = bar(D15, 12, 0, 10.5, 11.2, 10.4, 11.0) if variant == "win" else bar(D15, 12, 0, 9.5, 9.6, 8.8, 9.0)
    bars = path([bar(D15, 11, 1, 10.0, 10.1, 9.9, 10.0)], flat(D15, (11, 2), (19, 59), 10.2), [exit_bar],
                flat(D16, (4, 0), (15, 59), 14.0))
    s, n = g_of(row, bars), g_of(row, bars, "next")
    assert s["outcome"] == variant
    assert (n["fill_px"], n["fill_t"], n["outcome"], n["exit_t"]) == (s["fill_px"], s["fill_t"], s["outcome"],
                                                                    s["exit_t"])


def test_NEGATIVE_a_bad_horizon_raises():
    with pytest.raises(ValueError):
        g_of(_row(), [], "week")


def test_bars_from_frame_drops_nan_and_sorts():
    idx = pd.to_datetime(["2026-10-14T14:31:00", "2026-10-14T14:30:00", "2026-10-14T14:32:00"])
    df = pd.DataFrame({"open": [1.0, 2.0, float("nan")], "high": [1, 2, 3], "low": [1, 2, 3], "close": [1, 2, 3]},
                      index=idx)
    out = LG.bars_from_frame(df)
    assert [b[0] for b in out] == [datetime(2026, 10, 14, 14, 30, tzinfo=UTC), datetime(2026, 10, 14, 14, 31, tzinfo=UTC)]
    assert LG.bars_from_frame(None) == [] and LG.bars_from_frame(pd.DataFrame()) == []


# ── alert_of / rows_for (D1, E3) ─────────────────────────────────────────────────────────────────────────────────
def test_a_pushed_potential_is_a_live_row_from_its_first_sighting():
    r = HF()
    assert (r["kind"], r["line"], r["plan_source"], r["at_et"], r["trigger"], r["stop"], r["r"]) == \
        ("potential", "live", "first_sighting", "08:51", 1.81, 1.7, 0.11)
    assert r["id"] == "2026-10-16|XLAB|horizontal_fade|potential" == LG.ledger_id("2026-10-16", "xlab",
                                                                                  "horizontal_fade", "potential")
    assert r["url"] == "/chart-maps?tab=gajjala&sub=horizontal_fade&focus=XLAB" and r["price_at_alert"] == 1.73


def test_the_claims_own_trigger_wins_over_the_first_sighting():
    r = row_of(pot_doc("AAA", "bull_flag", A, et(A, 10, 30), 5.0, 4.0,
                       push_extra={"trigger": 10.0, "stop": 9.0, "px": 9.8}))
    assert (r["plan_source"], r["trigger"], r["stop"], r["price_at_alert"]) == ("push", 10.0, 9.0, 9.8)


def test_a_deferred_ring_reads_the_first_sighting_and_says_so():
    r = row_of(pot_doc("AAA", "bull_flag", A, et(A, 9, 46), 10.0, 9.0, first_seen_et="09:31"))
    assert r["plan_source"] == "first_sighting_deferred"


@pytest.mark.parametrize("state", ["no_target", "failed", "claimed"])
def test_NEGATIVE_a_push_that_never_reached_him_is_not_a_row(state):
    assert LG.alert_of(pot_doc("AAA", "bull_flag", A, et(A, 10, 30), 10.0, 9.0, state=state), "potential") is None


def test_NEGATIVE_a_joined_potential_is_never_a_row_even_with_a_hand_injected_push():
    assert LG.alert_of(pot_doc("AAA", "bull_flag", A, et(A, 10, 30), 10.0, 9.0, mode="joined"), "potential") is None
    doc = pot_doc("AAA", "bull_flag", A, et(A, 10, 30), 10.0, 9.0)
    doc.pop("push")
    assert LG.alert_of(doc, "potential") is None


def test_aplus_shadow_and_live_lines():
    sh = row_of(aplus_doc("PMI", "bull_flag", D16, et(D16, 10, 36), 2.0, 1.9, price=1.95), "aplus")
    assert (sh["line"], sh["plan_source"], sh["price_at_alert"], sh["at_et"]) == ("shadow", "aplus", 1.95, "10:36")
    live = row_of(aplus_doc("PMI", "bull_flag", D16, et(D16, 10, 36), 2.0, 1.9, state="pushed"), "aplus")
    assert live["line"] == "live"


@pytest.mark.parametrize("suffix,state", [("#suppressed_premarket", "suppressed_premarket"), ("#late", "late"),
                                          ("#not_aplus_variant", "not_aplus_variant"), ("", "claimed"),
                                          ("", "failed"), ("", "no_target"), ("#shadow", "shadow")])
def test_NEGATIVE_aplus_refusals_and_unsent_claims_are_not_rows(suffix, state):
    doc = aplus_doc("PMI", "bull_flag", D16, et(D16, 10, 36), 2.0, 1.9, state="pushed")
    doc.update(_id=doc["_id"] + suffix, state=state)
    assert LG.alert_of(doc, "aplus") is None


def test_E3_missing_or_unparseable_at_is_a_no_time_row_and_claimed_at_is_the_fallback():
    gone = row_of(pot_doc("AAA", "bull_flag", A, None, 10.0, 9.0, at_et="10:30"))
    assert gone["at_utc"] is None and gone["rang"] is None
    bad = row_of(pot_doc("BBB", "bull_flag", A, "x", 10.0, 9.0, at_et="10:31"))
    assert bad["at_utc"] is None
    assert LG.grade(bad, [], None, "same")["entry"] == "no_time"
    al = aplus_doc("CCC", "bull_flag", A, None, 10.0, 9.0)
    al["claimed_at"] = et(A, 10, 32).isoformat()
    assert row_of(al, "aplus")["at_utc"] == et(A, 10, 32)


def test_rows_for_orders_date_desc_then_alert_desc_symbol_setup_kind():
    pots = [pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70),
            pot_doc("XLAB", "intraday_vcp", D16, VCP_AT, 1.85, 1.75),
            pot_doc("AAA", "bull_flag", D15, et(D15, 15, 11), 1.22, 1.16),
            pot_doc("BBB", "bull_flag", D16, VCP_AT, 2.0, 1.9),
            pot_doc("NOT", "bull_flag", D16, VCP_AT, 2.0, 1.9, state="no_target")]
    alerts = [aplus_doc("BBB", "bull_flag", D16, VCP_AT, 2.0, 1.9)]
    rows = LG.rows_for([D15, D16], store_with(pots, alerts))
    assert [(r["date"], r["symbol"], r["setup"], r["kind"]) for r in rows] == [
        ("2026-10-16", "BBB", "bull_flag", "potential"), ("2026-10-16", "BBB", "bull_flag", "aplus"),
        ("2026-10-16", "XLAB", "intraday_vcp", "potential"), ("2026-10-16", "XLAB", "horizontal_fade", "potential"),
        ("2026-10-15", "AAA", "bull_flag", "potential")]


@pytest.mark.parametrize("which", [ST.POTENTIALS, ST.ALERTS])
def test_NEGATIVE_a_failed_read_raises_never_reads_as_no_alert(which):
    st = fake_store(**{which: FakeColl(fail=True)})
    with pytest.raises(LG.LedgerReadError):
        LG.rows_for([D16], st)
    with pytest.raises(LG.LedgerReadError):
        LG.rows_for([D16], ST.GajjalaStore(colls={n: None for n in ST.ALL}))


def test_count_today_counts_todays_graded_rows_only():
    pots = [pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70),
            pot_doc("XLAB", "intraday_vcp", D16, VCP_AT, 1.85, 1.75),
            pot_doc("J", "bull_flag", D16, VCP_AT, 2.0, 1.9, mode="joined")]
    assert LG.count_today(pots) == 0                        # E5: nothing graded yet → 0
    led = [{"_id": "2026-10-16|XLAB|horizontal_fade|potential", "same": {"entry": "filled"}},
           {"_id": "2026-10-16|J|bull_flag|potential", "same": {"entry": "filled"}}]
    assert LG.count_today(pots, led) == 1                   # NEGATIVE: the joined doc is never a row


# ── served_block (W1–W15) ─────────────────────────────────────────────────────────────────────────────────────────
NOW_1225 = et(D16, 12, 25)


def _graded(row, same=None, nxt=None):
    doc = {"_id": row["id"], "date": row["date"], "symbol": row["symbol"], "setup": row["setup"], "kind": row["kind"],
           "line": row["line"], "version": GC.LEDGER_GRADE_VERSION}
    if same:
        doc["same"] = same
    if nxt:
        doc["next"] = nxt
    return doc


def _g(outcome, *, best=10.0, close=1.0, exit_t=None, fill_t=None, entry="filled", reason=None, h="same"):
    return {"horizon": h, "entry": entry, "fill_px": 10.0, "fill_t": fill_t or et(D15, 11, 0).isoformat(),
            "outcome": outcome if entry == "filled" else None, "target_px": 11.0,
            "exit_t": exit_t or et(D15, 12, 0).isoformat(), "reason": reason or ("target" if outcome == "win" else "stop"),
            "best_pct": best, "close_pct": close, "end_t": None, "end_date": "2026-10-16" if h == "next" else "2026-10-15"}


def _all_strings(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _all_strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _all_strings(v)
    elif isinstance(o, str):
        yield o


def _assert_clean(block):
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    blob = json.dumps(block, ensure_ascii=False, allow_nan=False)
    for s in _all_strings(block):
        assert "None" not in s and "nan" not in s.lower().split(), s
        assert not B_WORD.search(s) and not SEPA_NAMES.search(s), s
        assert not [w for w in FORBIDDEN_WORDS if w in s.lower()], s
    assert "NaN" not in blob


def test_served_block_shape_and_the_fixed_words():
    st = store_with([pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70, px=1.73)])
    b = LG.served_block(st, D16, NOW_1225, span="today", is_today=True, today=None)
    assert b["title"] == "🏁 Track record — every Gajjala alert that rang, graded by GG's trade math · UNMEASURED"
    assert b["rule_label"] == "ⓘ how each alert is graded" and b["honesty"] == LG.HONESTY
    assert "09:45 ET" in b["rule_text"] and "+1R" in b["rule_text"] and f"{GC.BAR_SETTLE_SEC} s" in b["rule_text"]
    assert [h["key"] for h in b["heads"]] == ["symbol", "setup", "at", "kind", "plan", "same", "next"]
    assert [s["key"] for s in b["spans"]] == list(GC.LEDGER_SPANS) and b["spans"][2]["label"] == "Last 5 sessions"
    assert b["grade_at_et"] == GC.LEDGER_GRADE_AT_ET and b["span"] == "today"
    (day,) = b["days"]
    assert day["label"] == "Fri 2026-10-16 · today"
    (r,) = day["rows"]
    assert (r["key"], r["kind_text"], r["at_text"], r["rang_text"], r["setup_label"]) == (
        "2026-10-16-XLAB-horizontal_fade-potential", "🧠 live", "08:51 ET", "rang pre", "➖ Horizontal Fade")
    assert r["plan_text"] == "trigger 1.81 · stop 1.70" and r["note"] is None
    assert (r["same"]["state"], r["same"]["text"], r["same"]["sub_text"]) == ("pending", "not read yet",
                                                                              "graded tonight 20:15 ET")
    assert (r["next"]["text"], r["next"]["sub_text"]) == ("after Mon 10-19's close", "graded Mon 10-19 20:15 ET")
    assert b["today_text"] == "Today · not read on this open — graded tonight 20:15 ET"     # NEGATIVE today=None
    _assert_clean(b)


def test_provisional_today_rows_say_so_and_count():
    st = store_with([pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70),
                     pot_doc("XLAB", "intraday_vcp", D16, VCP_AT, 1.85, 1.75)])
    today = LG.today_read(NOW_1225, span="today", store=st, load_frames=lambda s, d: (xlab_bars(), False),
                          clock=lambda: 0.0)
    b = LG.served_block(st, D16, NOW_1225, span="today", is_today=True, today=today)
    rows = {r["setup"]: r for r in b["days"][0]["rows"]}
    hf = rows["horizontal_fade"]
    assert hf["same"] == {"state": "win", "text": "WIN · best +103.2% so far", "sub_text": "+1R at 09:49 · not final",
                          "provisional": True}
    assert hf["plan_text"] == "trigger 1.81 → fill 1.89 at 09:45 · stop 1.70 · +1R 2.00" and hf["fill_px"] == 1.89
    assert b["counts"]["live"]["same"]["win"] == 2 and b["counts"]["live"]["same"]["pct"] == 100
    assert b["counts_text"]["same"] == ("Same session: 2 wins · 0 losses · 100% won · 0 no entry · 0 open"
                                        " · today not final")
    assert b["today_text"] == "Today · through 12:24 ET · not final"        # 12:25 − settle, floored: what was read
    _assert_clean(b)


def test_NEGATIVE_an_aplus_shadow_win_never_moves_the_live_pct_and_shows_on_its_own_line():
    live = row_of(pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0))
    sh = row_of(aplus_doc("PMI", "bull_flag", D15, et(D15, 10, 36), 2.0, 1.9), "aplus")
    st = store_with([pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0)],
                    [aplus_doc("PMI", "bull_flag", D15, et(D15, 10, 36), 2.0, 1.9)],
                    [_graded(live, _g("loss")), _graded(sh, _g("win"))])
    b = LG.served_block(st, D16, NOW_1225, span="yesterday", is_today=True)
    assert (b["counts"]["live"]["same"]["win"], b["counts"]["live"]["same"]["loss"]) == (0, 1)
    assert b["counts"]["live"]["same"]["pct"] == 0 and b["counts"]["shadow"]["same"]["pct"] == 100
    assert b["counts_text"]["same"].startswith("Same session: 0 wins · 1 loss · 0% won")
    assert b["shadow_text"].startswith("A+ shadow (never sent, not in the %): same session 1 win · 0 losses · 100% won")
    assert [r["kind_text"] for r in b["days"][0]["rows"]] == ["🧠 live", "A+ shadow — never sent"]
    assert b["today_text"] is None                          # no today row in "yesterday"
    _assert_clean(b)


def test_NEGATIVE_no_shadow_row_means_no_shadow_line_and_no_graded_entry_reads_so():
    st = store_with([pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0)])
    b = LG.served_block(st, D16, NOW_1225, span="yesterday", is_today=True)
    assert b["shadow_text"] is None
    assert b["counts_text"]["same"] == ("Same session: 0 wins · 0 losses · no graded entry yet · 0 no entry · 0 open"
                                        " · 1 not graded yet")
    assert b["counts"]["live"]["same"]["pct"] is None


# ── 🎯 live A+ entries (DECISIONS10 D3 as modified by AMENDMENTS10 F3, 2026-10-16) ─────────────────────────────────
# Ajay 2026-10-16: "you alert me when that happens". A pushed `GG:` claim is a live row ("🎯 A+ entry") counted on its
# OWN line — never pooled into the 🧠 headline % (an A+ exists only once the trade survived its entry bar, F3). The
# existing NEGATIVES stay: a shadow win never moves the live % (test_NEGATIVE_an_aplus_shadow_win_never_moves_the_live_
# pct_and_shows_on_its_own_line) and failed / no_target / claimed / `#…` docs are never rows
# (test_NEGATIVE_aplus_refusals_and_unsent_claims_are_not_rows).
def _entry_store(with_entry=True):
    pot = pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0)
    ent = aplus_doc("PMI", "bull_flag", D15, et(D15, 10, 36), 2.0, 1.9, state="pushed", prefix="")
    led = [_graded(row_of(pot), _g("loss"))]
    if with_entry:
        led.append(_graded(row_of(ent, "aplus"), _g("win")))
    return store_with([pot], [ent] if with_entry else [], led)


def test_a_live_aplus_entry_sits_on_its_own_entry_line_never_in_the_headline_pct():
    b = LG.served_block(_entry_store(), D16, NOW_1225, span="yesterday", is_today=True)
    rows = {r["symbol"]: r for r in b["days"][0]["rows"]}
    e = rows["PMI"]
    assert (e["kind"], e["line"], e["kind_text"]) == ("aplus", "live", "🎯 A+ entry")
    assert e["kind_text"] == LG.KIND_TEXT[("aplus", "live")] == "🎯 A+ entry"
    assert e["href"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=PMI"
    assert b["counts"]["entry"]["same"]["win"] == 1 and b["counts"]["entry"]["same"]["pct"] == 100
    assert (b["counts"]["live"]["same"]["win"], b["counts"]["live"]["same"]["loss"]) == (0, 1)
    assert b["entries_text"].startswith("🎯 A+ entries sent (their own line, not pooled with the 🧠 %): same session "
                                        "1 win · 0 losses · 100% won")
    assert "; through next session " in b["entries_text"]
    assert b["shadow_text"] is None                          # a live entry is not the shadow line
    _assert_clean(b)


def test_NEGATIVE_an_aplus_entry_never_moves_the_headline_pct():
    """F3: the 🧠 % must not move when an A+ row is added — the same store without the entry serves the same
    counts.live and counts_text, byte for byte."""
    with_e = LG.served_block(_entry_store(True), D16, NOW_1225, span="yesterday", is_today=True)
    without = LG.served_block(_entry_store(False), D16, NOW_1225, span="yesterday", is_today=True)
    assert with_e["counts"]["live"] == without["counts"]["live"]
    assert with_e["counts_text"] == without["counts_text"]
    assert with_e["counts"]["live"]["same"]["pct"] == 0 == without["counts"]["live"]["same"]["pct"]
    assert without["entries_text"] is None and without["counts"]["entry"]["same"]["win"] == 0
    assert without["counts"]["entry"]["same"]["pct"] is None


def test_NEGATIVE_a_shadow_aplus_never_feeds_the_entry_line():
    sh = row_of(aplus_doc("PMI", "bull_flag", D15, et(D15, 10, 36), 2.0, 1.9), "aplus")
    st = store_with([], [aplus_doc("PMI", "bull_flag", D15, et(D15, 10, 36), 2.0, 1.9)], [_graded(sh, _g("win"))])
    b = LG.served_block(st, D16, NOW_1225, span="yesterday", is_today=True)
    assert b["entries_text"] is None and b["counts"]["entry"]["same"]["win"] == 0
    assert b["counts"]["shadow"]["same"]["win"] == 1 and b["shadow_text"]


@pytest.mark.parametrize("suffix,state", [("", "failed"), ("", "no_target"), ("", "claimed"),
                                          ("#suppressed_premarket", "suppressed_premarket")])
def test_NEGATIVE_an_unsent_live_claim_is_no_entry_row_and_no_entries_text(suffix, state):
    doc = aplus_doc("PMI", "bull_flag", D15, et(D15, 10, 36), 2.0, 1.9, state="pushed", prefix="")
    doc.update(_id=doc["_id"] + suffix, state=state)
    b = LG.served_block(store_with([], [doc], []), D16, NOW_1225, span="yesterday", is_today=True)
    assert b["entries_text"] is None and b["days"] == [] and b["counts"]["entry"]["same"]["win"] == 0


def test_NEGATIVE_a_provisional_entry_never_marks_the_headline_today_not_final():
    """F3: `counts_text` is the 🧠 pushes only — a provisional grade on a live A+ entry never stamps "today not final"
    on the headline."""
    st = store_with([], [aplus_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70, state="pushed", prefix="")])
    today = LG.today_read(NOW_1225, span="today", store=st, load_frames=lambda s, d: (xlab_bars(), False),
                          clock=lambda: 0.0)
    b = LG.served_block(st, D16, NOW_1225, span="today", is_today=True, today=today)
    (r,) = b["days"][0]["rows"]
    assert r["kind_text"] == "🎯 A+ entry" and r["same"]["provisional"] is True and r["same"]["state"] == "win"
    assert b["counts"]["entry"]["same"]["win"] == 1 and b["counts"]["live"]["same"]["win"] == 0
    assert "today not final" not in b["counts_text"]["same"] and b["entries_text"].startswith("🎯 A+ entries sent")


F3_HONESTY = ("A ledger of the alerts as sent, graded by GG's own trade math — not a backtest of a strategy, and small n "
              "early. A+ rows from the shadow period (never sent) stay out of the %; A+ entries sent live are counted on "
              "their own 🎯 line, not pooled with the 🧠 pushes — an A+ exists only once the trade survived its entry "
              "bar. The 2026-10-14 study of the five setups read NULL — no edge over a matched placebo "
              "(docs/gajjala/study_2026_10_13.md); this record does not change that.")


def test_honesty_has_no_never_sent_lie():
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    assert LG.HONESTY == F3_HONESTY
    assert "The A+ line was never sent" not in LG.HONESTY                       # NEGATIVE: false since the flip
    assert "A+ entries sent live are counted on their own 🎯 line, not pooled with the 🧠 pushes" in LG.HONESTY
    assert "A+ entries sent live count like the 🧠 pushes" not in LG.HONESTY    # NEGATIVE: F3 withdrew the pooling
    assert not B_WORD.search(LG.HONESTY) and "fake" not in LG.HONESTY.lower()
    assert not [w for w in FORBIDDEN_WORDS if w in LG.HONESTY.lower()]
    assert "15" not in LG.HONESTY and "09:45" not in LG.HONESTY                 # the 🏁 contracts read ledger.py code
    assert "study_2026_10_13.md" in LG.HONESTY and "NULL" in LG.HONESTY


def test_kind_text_is_one_literal_line_the_contracts_read():
    src = Path(LG.__file__).read_text(encoding="utf-8")
    assert '("aplus", "live"): "🎯 A+ entry"' in src
    assert LG.KIND_TEXT == {("potential", "live"): "🧠 live", ("aplus", "shadow"): "A+ shadow — never sent",
                            ("aplus", "live"): "🎯 A+ entry"}


def test_win_pct_rounds_half_up():
    pots, led = [], []
    for i in range(8):
        d = pot_doc(f"S{i}", "bull_flag", D15, et(D15, 11, i), 10.0, 9.0)
        pots.append(d)
        led.append(_graded(row_of(d), _g("win" if i == 0 else "loss")))
    b = LG.served_block(store_with(pots, (), led), D16, NOW_1225, span="yesterday", is_today=True)
    assert b["counts"]["live"]["same"]["pct"] == 13 and round(100 / 8) == 12      # 12.5 → 13 (Python rounds to 12)


def test_no_entry_no_plan_no_risk_thin_and_no_time_are_listed_never_counted():
    docs = [pot_doc("NE", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0),
            pot_doc("NP", "bull_flag", D15, et(D15, 11, 1), None, 9.0),
            pot_doc("NR", "bull_flag", D15, et(D15, 11, 2), 9.0, 9.0),
            pot_doc("TH", "bull_flag", D15, et(D15, 11, 3), 0.543, 0.5429),
            pot_doc("NT", "bull_flag", D15, "x", 10.0, 9.0, at_et="11:04"),
            pot_doc("WW", "bull_flag", D15, et(D15, 11, 5), 10.0, 9.0)]
    led = [_graded(row_of(docs[0]), _g(None, entry="no_entry")), _graded(row_of(docs[3]), _g("win")),
           _graded(row_of(docs[5]), _g("win"))]
    b = LG.served_block(store_with(docs, (), led), D16, NOW_1225, span="yesterday", is_today=True)
    c = b["counts"]["live"]["same"]
    assert (c["win"], c["loss"], c["no_entry"], c["no_plan"], c["no_risk"], c["thin"], c["no_time"], c["pct"]) == \
        (1, 0, 1, 1, 1, 1, 1, 100)
    rows = {r["symbol"]: r for r in b["days"][0]["rows"]}
    assert rows["NP"]["plan_text"] == "no trigger or stop on the alert" and rows["NP"]["same"]["text"] == "no plan"
    assert rows["NR"]["plan_text"] == "trigger = stop on the alert — no risk to size"
    assert rows["TH"]["thin_text"] == "thin R" and rows["WW"]["thin_text"] is None
    assert rows["NT"]["at_text"] == "no alert time" and rows["NT"]["same"]["state"] == "no_time"
    assert rows["NE"]["same"]["text"] == "no entry"
    assert " · 1 thin R (not in the %)" in b["counts_text"]["same"]
    _assert_clean(b)


def test_cell_words_for_loss_fill_minute_open_flat_and_split():
    rows = [row_of(pot_doc(s, "bull_flag", D15, et(D15, 11, i), 10.0, 9.0)) for i, s in enumerate("ABCD")]
    led = [_graded(rows[0], _g("loss", best=5.0, close=-12.0), _g("flat", h="next", best=7.5, close=-3.25)),
           _graded(rows[1], _g("loss", reason="stop_fill_minute")),
           _graded(rows[2], _g("open", best=4.0, close=2.0)),
           _graded(rows[3], None, {"horizon": "next", "entry": "filled", "reason": "split", "split_on": "2026-10-16"})]
    pots = [pot_doc(s, "bull_flag", D15, et(D15, 11, i), 10.0, 9.0) for i, s in enumerate("ABCD")]
    b = LG.served_block(store_with(pots, (), led), D16, NOW_1225, span="yesterday", is_today=True)
    r = {x["symbol"]: x for x in b["days"][0]["rows"]}
    assert (r["A"]["same"]["text"], r["A"]["same"]["sub_text"]) == ("LOSS · best +5.0%", "stop at 12:00 · close -12.0%")
    assert (r["A"]["next"]["text"], r["A"]["next"]["sub_text"]) == ("flat · best +7.5%",
                                                                    "close -3.2% at the Fri 10-16 close")
    assert r["B"]["same"]["sub_text"].startswith("stop in the fill minute 12:00")
    assert (r["C"]["same"]["text"], r["C"]["same"]["sub_text"]) == ("open · best +4.0%", "close +2.0%")
    assert (r["D"]["next"]["text"], r["D"]["next"]["sub_text"]) == ("split", "split on 2026-10-16 — not graded")
    assert (r["D"]["same"]["text"], r["D"]["same"]["sub_text"]) == ("not graded yet", "graded nightly at 20:15 ET")
    assert r["A"]["plan_text"] == "trigger 10.00 → fill 10.00 at 11:00 · stop 9.00 · +1R 11.00"
    assert " · 1 split" in b["counts_text"]["next"]
    _assert_clean(b)


def test_next_pending_texts_for_todays_and_a_weekdays_close():
    pot = pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0)
    b = LG.served_block(store_with([pot]), D16, NOW_1225, span="yesterday", is_today=True)
    nxt = b["days"][0]["rows"][0]["next"]
    assert (nxt["text"], nxt["sub_text"]) == ("after today's close", "graded tonight 20:15 ET")
    late = et(D16, 21, 0)
    b2 = LG.served_block(store_with([pot]), D16, late, span="yesterday", is_today=True)
    assert b2["days"][0]["rows"][0]["next"]["text"] == "not graded yet"


def test_rows_max_and_the_more_line(monkeypatch):
    monkeypatch.setattr(GC, "LEDGER_ROWS_MAX", 2)
    pots = [pot_doc(f"S{i}", "bull_flag", D15, et(D15, 11, i), 10.0, 9.0) for i in range(3)]
    b = LG.served_block(store_with(pots), D16, NOW_1225, span="yesterday", is_today=True)
    assert sum(len(d["rows"]) for d in b["days"]) == 2
    assert b["more_text"] == "+1 more rows — the counts above cover all 3" and b["days"][0]["more_n"] == 1
    assert b["counts"]["live"]["same"]["pending"] == 3


def test_every_span_reads_its_sessions_and_an_unknown_span_is_the_default():
    st = store_with([pot_doc("OLD", "bull_flag", date(2026, 10, 13), et(date(2026, 10, 13), 11, 0), 10.0, 9.0),
                     pot_doc("AAA", "bull_flag", D15, et(D15, 11, 0), 10.0, 9.0),
                     pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70)])
    syms = lambda b: [r["symbol"] for d in b["days"] for r in d["rows"]]          # noqa: E731
    assert syms(LG.served_block(st, D16, NOW_1225, span="today", is_today=True)) == ["XLAB"]
    assert syms(LG.served_block(st, D16, NOW_1225, span="yesterday", is_today=True)) == ["AAA"]
    five = LG.served_block(st, D16, NOW_1225, span="5d", is_today=True)
    assert syms(five) == ["XLAB", "AAA", "OLD"]
    assert LG.served_block(st, D16, NOW_1225, span="bogus", is_today=True)["span"] == GC.LEDGER_SPAN_DEFAULT == "5d"
    assert syms(LG.served_block(st, D16, NOW_1225, span="all", is_today=True)) == ["XLAB", "AAA", "OLD"]


def test_E7_all_span_reads_the_alert_dates_never_the_ledger_dates_alone():
    old = date(2026, 9, 1)
    pot = pot_doc("AAA", "bull_flag", old, et(old, 11, 0), 10.0, 9.0)
    st = store_with([pot])                                  # nothing graded: ledger_dates() is []
    assert st.ledger_dates() == []
    b = LG.served_block(st, D16, NOW_1225, span="all", is_today=True)
    assert [r["symbol"] for d in b["days"] for r in d["rows"]] == ["AAA"]
    assert b["days"][0]["rows"][0]["same"]["text"] == "not graded yet"


@pytest.mark.parametrize("span,want", [("today", "No Gajjala alert has rung yet this session."),
                                       ("yesterday", "No Gajjala alert rang on 2026-10-15."),
                                       ("5d", "No Gajjala alert rang in the last 5 sessions."),
                                       ("all", "No Gajjala alert on file yet.")])
def test_empty_texts(span, want):
    b = LG.served_block(store_with(), D16, NOW_1225, span=span, is_today=True)
    assert b["empty_text"] == want and b["days"] == [] and b["today_text"] is None
    _assert_clean(b)


def test_NEGATIVE_served_block_raises_on_a_ledger_read_fault():
    st = fake_store(**{ST.LEDGER: FakeColl(fail=True)})
    with pytest.raises(LG.LedgerReadError):
        LG.served_block(st, D16, NOW_1225, span="today", is_today=True)


def test_deferred_plan_note():
    st = store_with([pot_doc("AAA", "bull_flag", D15, et(D15, 9, 46), 10.0, 9.0, first_seen_et="09:31")])
    r = LG.served_block(st, D16, NOW_1225, span="yesterday", is_today=True)["days"][0]["rows"][0]
    assert r["note"] == "trigger as first seen 09:31 ET (the ring was 09:46 ET)"


# ── grade_step (§3.5) ─────────────────────────────────────────────────────────────────────────────────────────────
class Loader:
    """An injected symbol-day loader: {(SYM, day): bars}; `fail` = provider failures; every call is logged."""

    def __init__(self, by_day=None, fail=()):
        self.by_day, self.fail, self.calls = dict(by_day or {}), set(fail), []

    def __call__(self, sym, day):
        self.calls.append((sym, day))
        if (sym, day) in self.fail:
            return None, True
        return list(self.by_day.get((sym, day), [])), False


def no_split(sym, a, n):
    return False


def _xlab_store():
    return store_with([pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70, px=1.73),
                       pot_doc("XLAB", "intraday_vcp", D16, VCP_AT, 1.85, 1.75, px=1.7901)])


def _xlab_loader():
    return Loader({("XLAB", D16): xlab_bars(), ("XLAB", D19): flat(D19, (9, 30), (15, 59), 2.0)})


NIGHT_16, NIGHT_19 = et(D16, 20, 15), et(D19, 20, 15)


def test_grade_step_at_2015_writes_same_never_next_then_next_on_monday():
    st, ld = _xlab_store(), _xlab_loader()
    out = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=no_split)
    assert (out["same"], out["next"], out["written"], out["loads"], out["read_fault"]) == (2, 0, 2, 1, False)
    assert out["not_due"] == 2 and ld.calls == [("XLAB", D16)]
    doc = st.coll(ST.LEDGER).docs["2026-10-16|XLAB|horizontal_fade|potential"]
    assert "next" not in doc                                # NEGATIVE: not due before Monday's close
    assert (doc["same"]["outcome"], doc["same"]["fill_px"], doc["alert"]["plan_source"]) == ("win", 1.89,
                                                                                             "first_sighting")
    assert set(doc) <= ST.LEDGER_KEYS | {"_id"} and doc["version"] == GC.LEDGER_GRADE_VERSION
    mon = LG.grade_step(st, NIGHT_19, load_day=ld, split_lookup=no_split)
    assert (mon["next"], mon["same"], mon["next_copied"]) == (2, 0, 2)
    doc = st.coll(ST.LEDGER).docs["2026-10-16|XLAB|horizontal_fade|potential"]
    assert doc["next"]["outcome"] == doc["same"]["outcome"] == "win"
    assert doc["next"]["exit_t"] == doc["same"]["exit_t"] and doc["next"]["end_date"] == "2026-10-19"


def test_NEGATIVE_a_second_run_the_same_night_loads_and_writes_nothing():
    st, ld = _xlab_store(), _xlab_loader()
    LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=no_split)
    w = st.coll(ST.LEDGER).writes
    ld2 = _xlab_loader()
    out = LG.grade_step(st, NIGHT_16 + timedelta(minutes=5), load_day=ld2, split_lookup=no_split)
    assert (out["loads"], out["written"], ld2.calls) == (0, 0, [])
    assert st.coll(ST.LEDGER).writes == w


def test_NEGATIVE_a_1300_manual_run_writes_nothing_for_today():
    st, ld = _xlab_store(), _xlab_loader()
    out = LG.grade_step(st, et(D16, 13, 0), load_day=ld, split_lookup=no_split)
    assert (out["written"], out["loads"], out["not_due"]) == (0, 0, 4) and st.coll(ST.LEDGER).docs == {}


def test_max_loads_defers_then_the_next_run_grades_the_rest():
    pots = [pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70),
            pot_doc("ZZZ", "bull_flag", D16, VCP_AT, 10.0, 9.0)]
    ld = Loader({("XLAB", D16): xlab_bars(), ("ZZZ", D16): flat(D16, (9, 30), (15, 59), 9.5)})
    st = store_with(pots)
    out = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=no_split, max_loads=1)
    assert (out["same"], out["deferred_cap"], out["written"]) == (1, 1, 1)
    out2 = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=no_split, max_loads=1)
    assert (out2["same"], out2["deferred_cap"]) == (1, 0) and len(st.coll(ST.LEDGER).docs) == 2


def test_NEGATIVE_a_provider_failure_leaves_the_column_absent_never_no_entry():
    st = _xlab_store()
    out = LG.grade_step(st, NIGHT_16, load_day=Loader(fail={("XLAB", D16)}), split_lookup=no_split)
    assert (out["load_failed"], out["same"], out["written"]) == (2, 0, 0) and st.coll(ST.LEDGER).docs == {}


def test_NEGATIVE_an_empty_alert_day_is_absent_no_bars_and_retried():
    st = _xlab_store()
    out = LG.grade_step(st, NIGHT_16, load_day=Loader(), split_lookup=no_split)
    assert (out["no_bars"], out["written"]) == (2, 0)
    out2 = LG.grade_step(st, NIGHT_16, load_day=_xlab_loader(), split_lookup=no_split)
    assert out2["same"] == 2


def test_an_empty_next_day_without_a_failure_is_graded_with_a_note():
    st, ld = _xlab_store(), Loader({("XLAB", D16): xlab_bars()})
    LG.grade_step(st, NIGHT_19, load_day=ld, split_lookup=no_split)
    doc = st.coll(ST.LEDGER).docs["2026-10-16|XLAB|intraday_vcp|potential"]
    assert doc["next"]["next_no_prints"] is True and doc["next"]["outcome"] == "win"


def _undecided_store_and_loader():
    """SYNTHETIC: a 10-16 alert whose trigger never trades (same = no_entry) — its next column is WALKED (§3.5.6)."""
    st = store_with([pot_doc("NNN", "bull_flag", D16, et(D16, 10, 0), 50.0, 40.0)])
    return st, Loader({("NNN", D16): flat(D16, (9, 30), (15, 59), 10.0), ("NNN", D19): flat(D19, (9, 30), (15, 59), 9.0)})


def test_split_true_marks_a_walked_next_column_split_and_none_leaves_it_absent():
    st, ld = _undecided_store_and_loader()
    out = LG.grade_step(st, NIGHT_19, load_day=ld, split_lookup=lambda s, a, n: "2026-10-19")
    assert (out["split"], out["next_copied"]) == (1, 0)
    doc = st.coll(ST.LEDGER).docs["2026-10-16|NNN|bull_flag|potential"]
    assert doc["same"]["entry"] == "no_entry"
    assert (doc["next"]["reason"], doc["next"]["split_on"], doc["next"]["outcome"]) == ("split", "2026-10-19", None)
    st2, ld2 = _undecided_store_and_loader()
    out2 = LG.grade_step(st2, NIGHT_19, load_day=ld2, split_lookup=lambda s, a, n: None)
    assert out2["split_check_failed"] == 1
    assert all("next" not in d for d in st2.coll(ST.LEDGER).docs.values())


_TRADE = ("entry", "fill_px", "fill_t", "outcome", "target_px", "exit_t", "reason", "best_pct", "close_pct")


def test_NEGATIVE_a_split_on_the_next_session_never_overwrites_a_trade_the_same_session_ended():
    """Critic fix round 1: XLAB 10-16 won on 10-16; a split dated 10-19 must not erase the win from the next-session %
    (§3.5.4 a decided same column is copied; §3.5.6 the split guard is for a WALKED next only)."""
    st, ld = _xlab_store(), _xlab_loader()
    out = LG.grade_step(st, NIGHT_19, load_day=ld, split_lookup=lambda s, a, n: "2026-10-19")
    assert (out["split"], out["next_copied"], out["next"]) == (0, 2, 2)
    assert ld.calls == [("XLAB", D16)]                      # no walk across the split: 10-19 never loaded
    for doc in st.coll(ST.LEDGER).docs.values():
        assert doc["next"]["outcome"] == doc["same"]["outcome"] == "win"
        assert all(doc["next"][k] == doc["same"][k] for k in _TRADE)
        assert (doc["next"]["reason"], doc["next"]["split_on"], doc["next"]["best_through"]) == (
            "target", "2026-10-19", "same")
        assert doc["next"]["end_date"] == "2026-10-19" and doc["next"]["horizon"] == "next"
    b = LG.served_block(st, D19, et(D19, 20, 30), span="all", is_today=True)
    assert b["counts"]["live"]["next"]["win"] == 2 and b["counts"]["live"]["next"]["split"] == 0
    assert b["counts_text"]["next"].startswith("Through next session: 2 wins · 0 losses · 100% won")
    assert " split" not in b["counts_text"]["next"]
    cell = b["days"][0]["rows"][0]["next"]
    assert cell["state"] == "win"
    assert cell["sub_text"].endswith(" · split on 2026-10-19 — best and close through the same session")
    _assert_clean(b)


def test_NEGATIVE_an_unread_split_check_never_drops_a_decided_trade():
    st, ld = _xlab_store(), _xlab_loader()
    out = LG.grade_step(st, NIGHT_19, load_day=ld, split_lookup=lambda s, a, n: None)
    assert (out["split_check_failed"], out["next_copied"], out["next"]) == (2, 2, 2)
    assert ld.calls == [("XLAB", D16)]
    for doc in st.coll(ST.LEDGER).docs.values():
        assert all(doc["next"][k] == doc["same"][k] for k in _TRADE)
        assert doc["next"]["split_unchecked"] is True and "split_on" not in doc["next"]


def test_a_decided_same_without_a_split_keeps_its_trade_and_walks_only_for_the_best():
    row, day1, day2 = _xlab_1015_rows_and_bars()
    st = store_with([pot_doc("XLAB", "intraday_vcp", D15, row["at_utc"], 1.22, 1.16)])
    LG.grade_step(st, NIGHT_16, load_day=Loader({("XLAB", D15): day1, ("XLAB", D16): day2}), split_lookup=no_split)
    doc = st.coll(ST.LEDGER).docs["2026-10-15|XLAB|intraday_vcp|potential"]
    assert all(doc["next"][k] == doc["same"][k] for k in _TRADE if k not in ("best_pct", "close_pct"))
    assert doc["next"]["best_pct"] == 214.75 > doc["same"]["best_pct"] and "best_through" not in doc["next"]


def test_the_default_split_lookup_reads_the_scanners_record_first(monkeypatch):
    st = fake_store()
    st.set_split_check(D19, "AAA", "held", held=True)
    st.set_split_check(D19, "BBB", "ok")
    look = LG._default_split_lookup(st)
    from chart_maps import drop10_tab as DT
    monkeypatch.setattr(DT, "fetch_splits_strict", lambda s, since: [{"execution_date": "2026-10-19"}])
    assert (look("AAA", D16, D19), look("BBB", D16, D19), look("CCC", D16, D19)) == (True, False, "2026-10-19")
    monkeypatch.setattr(DT, "fetch_splits_strict", lambda s, since: [{"execution_date": "2026-10-16"}])
    assert look("CCC", D16, D19) is False                    # on the alert day itself: not between the two sessions

    def boom(s, since):
        raise RuntimeError("no key")
    monkeypatch.setattr(DT, "fetch_splits_strict", boom)
    assert look("CCC", D16, D19) is None


def test_a_version_bump_regrades(monkeypatch):
    st, ld = _xlab_store(), _xlab_loader()
    LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=no_split)
    monkeypatch.setattr(GC, "LEDGER_GRADE_VERSION", GC.LEDGER_GRADE_VERSION + 1)
    out = LG.grade_step(st, NIGHT_16, load_day=_xlab_loader(), split_lookup=no_split)
    assert (out["same"], out["written"]) == (2, 2)
    assert st.coll(ST.LEDGER).docs["2026-10-16|XLAB|intraday_vcp|potential"]["version"] == GC.LEDGER_GRADE_VERSION


def test_NEGATIVE_dry_writes_nothing():
    st = _xlab_store()
    out = LG.grade_step(st, NIGHT_16, load_day=_xlab_loader(), split_lookup=no_split, dry=True)
    assert (out["same"], out["written"], out["dry"]) == (2, 0, True) and st.coll(ST.LEDGER).writes == 0


def test_NEGATIVE_a_read_fault_writes_nothing():
    st = fake_store(**{ST.POTENTIALS: FakeColl(fail=True)})
    out = LG.grade_step(st, NIGHT_16, load_day=_xlab_loader(), split_lookup=no_split)
    assert out["read_fault"] is True and out["written"] == 0


def test_E3_bad_docs_never_crash_the_grade_each_row_in_its_own_try(monkeypatch):
    pots = [pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70),
            pot_doc("NOAT", "bull_flag", D16, None, 10.0, 9.0, at_et="10:00"),
            pot_doc("BADAT", "bull_flag", D16, "x", 10.0, 9.0, at_et="10:01"),
            pot_doc("BOOM", "bull_flag", D16, VCP_AT, 10.0, 9.0),
            {"_id": "junk", "date": "not-a-date", "symbol": "J", "setup": "bull_flag", "push": {"state": "pushed"}}]
    st = store_with(pots)
    real = LG.grade

    def grade(alert, *a, **k):
        if alert.get("symbol") == "BOOM":
            raise RuntimeError("bad doc")
        return real(alert, *a, **k)
    monkeypatch.setattr(LG, "grade", grade)
    out = LG.grade_step(st, NIGHT_16, load_day=Loader({("XLAB", D16): xlab_bars(),
                                                       ("BOOM", D16): flat(D16, (9, 30), (15, 59), 9.5)}),
                        split_lookup=no_split)
    assert out["faulted"] == 1 and out["rows"] == 4
    docs = st.coll(ST.LEDGER).docs
    assert docs["2026-10-16|XLAB|horizontal_fade|potential"]["same"]["outcome"] == "win"
    assert docs["2026-10-16|NOAT|bull_flag|potential"]["same"]["entry"] == "no_time"
    assert docs["2026-10-16|BADAT|bull_flag|potential"]["same"]["entry"] == "no_time"
    assert "2026-10-16|BOOM|bull_flag|potential" not in docs


def test_grade_step_1015_after_hours_lookback_and_the_215pct_next_session():
    row, day1, day2 = _xlab_1015_rows_and_bars()
    st = store_with([pot_doc("XLAB", "intraday_vcp", D15, row["at_utc"], 1.22, 1.16)])
    ld = Loader({("XLAB", D15): day1, ("XLAB", D16): day2})
    out = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=no_split)
    assert (out["same"], out["next"]) == (1, 1)
    doc = st.coll(ST.LEDGER).docs["2026-10-15|XLAB|intraday_vcp|potential"]
    assert doc["same"]["outcome"] == doc["next"]["outcome"] == "win" and doc["next"]["best_pct"] == 214.75
    assert sorted(set(ld.calls)) == [("XLAB", D15), ("XLAB", D16)] and len(ld.calls) == 2      # the memo


def test_grade_step_lookback_covers_the_tabs_life():
    out = LG.grade_step(fake_store(), NIGHT_16, load_day=Loader(), split_lookup=no_split)
    assert len(out["sessions"]) == GC.LEDGER_GRADE_LOOKBACK_SESSIONS and out["sessions"][-1] == "2026-10-16"
    assert "2026-10-13" in out["sessions"]


# ── today_read (§3.6, E6, E8) ─────────────────────────────────────────────────────────────────────────────────────
class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_today_read_grades_todays_rows_and_NEVER_WRITES():
    st = _xlab_store()
    calls = []
    out = LG.today_read(NOW_1225, span="today", store=st,
                        load_frames=lambda s, d: (calls.append((s, d)) or xlab_bars(), False), clock=Clock())
    assert calls == [("XLAB", D16)] and out["session"] == "2026-10-16" and out["not_read"] == []
    g = out["grades"]["2026-10-16|XLAB|intraday_vcp|potential"]
    assert (g["outcome"], g["fill_px"], t_et(g["exit_t"])) == ("win", 1.89, "09:48")
    assert out["through_et"] == "12:24" and out["stats"]["loaded"] == 1
    assert all(st.coll(n).writes == 0 for n in ST.ALL)


def test_NEGATIVE_today_read_still_returns_when_upsert_ledger_would_raise(monkeypatch):
    st = _xlab_store()

    def boom(*a, **k):
        raise AssertionError("today_read wrote the ledger")
    monkeypatch.setattr(st, "upsert_ledger", boom)
    out = LG.today_read(NOW_1225, span="today", store=st, load_frames=lambda s, d: (xlab_bars(), False),
                        clock=Clock())
    assert len(out["grades"]) == 2


def test_today_read_memo_then_reload_after_the_memo_window():
    st, clk, calls = _xlab_store(), Clock(), []
    load = lambda s, d: (calls.append(s) or xlab_bars(), False)                                      # noqa: E731
    LG.today_read(NOW_1225, store=st, load_frames=load, clock=clk)
    clk.t += GC.LEDGER_TODAY_MEMO_SEC - 1
    out = LG.today_read(NOW_1225 + timedelta(seconds=GC.LEDGER_TODAY_MEMO_SEC - 1), store=st, load_frames=load,
                        clock=clk)
    assert calls == ["XLAB"] and out["stats"]["memo"] == 1
    clk.t += 1
    LG.today_read(NOW_1225 + timedelta(seconds=GC.LEDGER_TODAY_MEMO_SEC), store=st, load_frames=load, clock=clk)
    assert calls == ["XLAB", "XLAB"]


def test_E6_a_memoised_frame_ends_the_label_and_the_walk_at_its_fetch_time():
    """SYNTHETIC: a frame fetched at 10:00:00 and served from the memo 290 s later — "through" is 09:59 (fetch −
    settle, floored), never 10:04, and the 10:02 target print the frame never held is not read."""
    st = store_with([pot_doc("AAA", "bull_flag", D16, et(D16, 9, 50), 10.0, 9.0)])
    bars = path([bar(D16, 9, 51, 9.9, 10.1, 9.8, 10.0)], flat(D16, (9, 52), (10, 3), 10.2),
                [bar(D16, 10, 2, 10.5, 11.5, 10.4, 11.0)])
    clk, t0 = Clock(), et(D16, 10, 0)
    LG.today_read(t0, store=st, load_frames=lambda s, d: (bars, False), clock=clk)
    clk.t += 290
    out = LG.today_read(t0 + timedelta(seconds=290), store=st, load_frames=lambda s, d: pytest.fail("reloaded"),
                        clock=clk)
    g = out["grades"]["2026-10-16|AAA|bull_flag|potential"]
    assert out["through_et"] == "09:59" and g["outcome"] == "open"
    assert LG._parse_at(g["through_t"]) == et(D16, 9, 59)


def test_NEGATIVE_an_unclosed_minute_is_not_graded():
    st = store_with([pot_doc("AAA", "bull_flag", D16, et(D16, 9, 50), 10.0, 9.0)])
    bars = path(flat(D16, (9, 51), (9, 58), 9.5), [bar(D16, 9, 59, 9.9, 10.5, 9.8, 10.2)])
    out = LG.today_read(et(D16, 10, 0, 20), store=st, load_frames=lambda s, d: (bars, False), clock=Clock())
    assert out["grades"]["2026-10-16|AAA|bull_flag|potential"]["entry"] == "no_entry"
    assert out["through_et"] == "09:59"
    out2 = LG.today_read(et(D16, 10, 0, 31), store=fake_store(**{ST.POTENTIALS: st.coll(ST.POTENTIALS)}),
                         load_frames=lambda s, d: (bars, False), clock=Clock(10 ** 6))
    assert out2["grades"]["2026-10-16|AAA|bull_flag|potential"]["entry"] == "filled"


def test_today_read_caps_the_names_and_lists_the_rest(monkeypatch):
    monkeypatch.setattr(GC, "LEDGER_TODAY_MAX", 2)
    pots = [pot_doc(f"S{i}", "bull_flag", D16, et(D16, 10, i), 10.0, 9.0) for i in range(4)]
    calls = []
    out = LG.today_read(NOW_1225, store=store_with(pots),
                        load_frames=lambda s, d: (calls.append(s) or flat(D16, (10, 5), (12, 0), 9.5), False),
                        clock=Clock())
    assert calls == ["S3", "S2"] and out["not_read"] == ["S1", "S0"] and out["stats"]["capped"] == 2


def test_NEGATIVE_today_read_failed_and_empty_loads_are_not_read():
    pots = [pot_doc("F", "bull_flag", D16, et(D16, 10, 0), 10.0, 9.0),
            pot_doc("E", "bull_flag", D16, et(D16, 10, 1), 10.0, 9.0)]

    def load(s, d):
        if s == "F":
            raise RuntimeError("massive down")
        return [], False
    out = LG.today_read(NOW_1225, store=store_with(pots), load_frames=load, clock=Clock())
    assert out["grades"] == {} and sorted(out["not_read"]) == ["E", "F"]
    assert (out["stats"]["failed"], out["stats"]["no_bars"], out["through_et"]) == (1, 1, None)


def test_NEGATIVE_today_read_skips_rows_with_a_stored_same_and_answers_none_when_none_left():
    hf = HF()
    st = store_with([pot_doc("XLAB", "horizontal_fade", D16, HF_AT, 1.81, 1.70)], (), [_graded(hf, _g("win"))])
    assert LG.today_read(NOW_1225, store=st, load_frames=lambda s, d: pytest.fail("read"), clock=Clock()) is None


def test_NEGATIVE_today_read_none_for_yesterday_and_a_closed_day():
    st = _xlab_store()
    no = lambda s, d: pytest.fail("loaded")                  # noqa: E731
    assert LG.today_read(NOW_1225, span="yesterday", store=st, load_frames=no) is None
    sat = datetime(2026, 10, 17, 16, 0, tzinfo=UTC)
    assert LG.today_read(sat, span="today", store=st, load_frames=no) is None


def test_NEGATIVE_an_after_hours_alert_today_is_not_read_its_same_session_is_tomorrow():
    st = store_with([pot_doc("AAA", "bull_flag", D16, et(D16, 17, 0), 10.0, 9.0)])
    assert LG.today_read(et(D16, 18, 0), store=st, load_frames=lambda s, d: pytest.fail("read"), clock=Clock()) is None


# ── today_read / served_block: an alert at or after the close is read on its same session (E1; critic round 1) ──
def _ah_store():
    """SYNTHETIC: a 10-15 17:00 ET potential (trigger 10 / stop 9) — its same session is 10-16 (E1)."""
    return store_with([pot_doc("AAA", "bull_flag", D15, et(D15, 17, 0), 10.0, 9.0)])


def _ah_bars():
    """SYNTHETIC 10-16: fills at 10:00 (high 10.20), +1R (11.00) at 10:10; no low reaches the 9.00 stop."""
    top = 10.0 + GC.LEDGER_R_MULT * 1.0
    return path(flat(D16, (9, 30), (9, 59), 9.5), [bar(D16, 10, 0, 9.9, 10.2, 9.8, 10.1)],
                flat(D16, (10, 1), (10, 9), 10.1), [bar(D16, 10, 10, 10.5, top + 0.2, 10.4, 11.0)],
                flat(D16, (10, 11), (11, 28), 10.8))


NOW_1130 = et(D16, 11, 30)


def test_E1_yesterdays_after_close_alert_is_read_today_and_served_provisional():
    st, calls = _ah_store(), []
    today = LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: (calls.append((s, d)) or _ah_bars(), False),
                          clock=Clock(), split_lookup=no_split)
    assert calls == [("AAA", D16)]
    g = today["grades"]["2026-10-15|AAA|bull_flag|potential"]
    assert (g["outcome"], t_et(g["fill_t"]), t_et(g["exit_t"])) == ("win", "10:00", "10:10")
    assert today["through_et"] == "11:29"
    b = LG.served_block(st, D16, NOW_1130, span="5d", is_today=True, today=today)
    (row,) = [r for d in b["days"] for r in d["rows"]]
    assert (row["same"]["state"], row["same"]["provisional"]) == ("win", True)
    assert row["same"]["text"].startswith("WIN · best ") and row["same"]["text"].endswith(" so far")
    assert row["same"]["sub_text"] == "+1R at Fri 10:10 · not final"
    assert b["today_text"] == "Today · through 11:29 ET · not final"
    assert b["counts_text"]["same"].endswith(" · today not final") and b["counts"]["live"]["same"]["win"] == 1
    _assert_clean(b)


def test_E1_yesterdays_after_close_alert_unread_is_pending_and_the_today_line_says_not_read():
    b = LG.served_block(_ah_store(), D16, NOW_1130, span="5d", is_today=True, today=None)
    (row,) = [r for d in b["days"] for r in d["rows"]]
    assert (row["same"]["state"], row["same"]["text"], row["same"]["sub_text"]) == (
        "pending", "after today's close", "graded tonight 20:15 ET")
    assert row["same"]["provisional"] is False
    assert b["today_text"] == "Today · not read on this open — graded tonight 20:15 ET"


def test_NEGATIVE_the_yesterday_span_shows_no_today_line_for_an_after_close_alert():
    b = LG.served_block(_ah_store(), D16, NOW_1130, span="yesterday", is_today=True, today=None)
    (row,) = [r for d in b["days"] for r in d["rows"]]
    assert row["same"]["state"] == "pending" and b["today_text"] is None
    assert LG.today_read(NOW_1130, span="yesterday", store=_ah_store(),
                         load_frames=lambda s, d: pytest.fail("read")) is None


def test_NEGATIVE_yesterdays_rth_alert_is_never_read_today_its_same_session_was_yesterday():
    st = store_with([pot_doc("RTH", "intraday_vcp", D15, et(D15, 15, 11), 10.0, 9.0)])
    assert LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: pytest.fail("read"), clock=Clock()) is None
    fake_today = {"session": "2026-10-16", "through_et": "11:29", "not_read": [],
                  "grades": {"2026-10-15|RTH|intraday_vcp|potential": _g("win")}}
    b = LG.served_block(st, D16, NOW_1130, span="5d", is_today=True, today=fake_today)
    (row,) = [r for d in b["days"] for r in d["rows"]]
    assert (row["same"]["state"], row["same"]["text"], row["same"]["provisional"]) == (
        "pending", "not graded yet", False)                 # a stray grade for a past session is never provisional
    assert b["today_text"] is None and "today not final" not in b["counts_text"]["same"]


def test_NEGATIVE_the_today_span_never_reads_yesterdays_rows():
    assert LG.today_read(NOW_1130, span="today", store=_ah_store(), load_frames=lambda s, d: pytest.fail("read"),
                         clock=Clock()) is None


def test_NEGATIVE_yesterdays_after_close_alert_with_a_stored_same_is_not_read_again():
    row = row_of(pot_doc("AAA", "bull_flag", D15, et(D15, 17, 0), 10.0, 9.0))
    st = store_with([pot_doc("AAA", "bull_flag", D15, et(D15, 17, 0), 10.0, 9.0)], (), [_graded(row, _g("win"))])
    assert LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: pytest.fail("read"), clock=Clock()) is None


# ── an after-close alert across a split (critic fix round 2) ─────────────────────────────────────────────────────
def _ah_split_store():
    """SYNTHETIC: a 10-15 17:30 ET 🧠 push (trigger 1.22 / stop 1.16, the probe's numbers) — same session 10-16 (E1)."""
    return store_with([pot_doc("RSX", "intraday_vcp", D15, et(D15, 17, 30), 1.22, 1.16, px=1.19)])


def _post_split_bars():
    """SYNTHETIC 10-16 after a 1:10 reverse split: every print ≈ 12.30, far above the pre-split trigger; the 09:45
    open fills (a gap over 1.22) and 09:46 trades through fill + R (12.36) — a WIN if read unguarded."""
    return path(flat(D16, (9, 30), (15, 59), 12.30), [bar(D16, 9, 45, 12.30, 12.50, 12.20, 12.36),
                                                      bar(D16, 9, 46, 12.30, 12.40, 12.25, 12.36)])


class SplitLog:
    """An injected split lookup: answers `by_window[(alert_date, end_date)]` (default False); every call is logged."""

    def __init__(self, by_window=None, default=False):
        self.by_window, self.default, self.calls = dict(by_window or {}), default, []

    def __call__(self, sym, a, n):
        self.calls.append((sym, a, n))
        return self.by_window.get((a, n), self.default)


AH_SPLIT_ID = "2026-10-15|RSX|intraday_vcp|potential"


def test_NEGATIVE_grade_step_an_after_close_alert_with_a_split_on_its_same_session_is_never_a_win():
    sp = SplitLog({(D15, D16): "2026-10-16"})
    ld = Loader({("RSX", D16): _post_split_bars()})
    st = _ah_split_store()
    out = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=sp)
    assert ("RSX", D15, D16) in sp.calls                     # the same column asked over (alert day, same session]
    assert (out["split"], out["same"], out["written"]) == (1, 1, 1) and ld.calls == []   # never graded on those bars
    same = st.coll(ST.LEDGER).docs[AH_SPLIT_ID]["same"]
    assert (same["reason"], same["split_on"], same["outcome"], same["entry"], same["fill_px"]) == (
        "split", "2026-10-16", None, None, None)
    b = LG.served_block(st, D16, NIGHT_16 + timedelta(minutes=5), span="5d", is_today=True)
    (row,) = [r for d in b["days"] for r in d["rows"]]
    assert (row["same"]["state"], row["same"]["text"], row["same"]["sub_text"]) == (
        "split", "split", "split on 2026-10-16 — not graded")
    assert "fill" not in row["plan_text"] and row["fill_px"] is None
    assert b["counts"]["live"]["same"]["win"] == 0 and b["counts"]["live"]["same"]["pct"] is None
    assert "WIN" not in json.dumps(row) and "100% won" not in b["counts_text"]["same"]
    _assert_clean(b)


def test_without_the_split_the_same_after_close_path_would_win_the_guard_is_load_bearing():
    st = _ah_split_store()
    LG.grade_step(st, NIGHT_16, load_day=Loader({("RSX", D16): _post_split_bars()}), split_lookup=SplitLog())
    g = st.coll(ST.LEDGER).docs[AH_SPLIT_ID]["same"]
    assert (g["outcome"], g["fill_px"], g["target_px"]) == ("win", 12.3, 12.36)        # the critic's probe row


def test_NEGATIVE_grade_step_an_unread_same_session_split_check_leaves_the_column_absent_and_retries():
    st = _ah_split_store()
    ld = Loader({("RSX", D16): _post_split_bars()})
    out = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=SplitLog(default=None))
    assert (out["split_check_failed"], out["same"], out["written"], ld.calls) == (1, 0, 0, [])
    assert st.coll(ST.LEDGER).docs == {}
    out2 = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=SplitLog({(D15, D16): True}))
    assert out2["split"] == 1
    assert st.coll(ST.LEDGER).docs[AH_SPLIT_ID]["same"]["split_on"] == "2026-10-16"     # one-session window


def test_NEGATIVE_a_split_on_the_same_session_also_marks_the_next_column_split():
    sp = SplitLog({(D15, D16): "2026-10-16", (D15, D19): "2026-10-16"})
    st = _ah_split_store()
    ld = Loader({("RSX", D16): _post_split_bars(), ("RSX", D19): flat(D19, (9, 30), (15, 59), 12.4)})
    out = LG.grade_step(st, NIGHT_19, load_day=ld, split_lookup=sp)
    doc = st.coll(ST.LEDGER).docs[AH_SPLIT_ID]
    assert (doc["same"]["reason"], doc["next"]["reason"], doc["next"]["outcome"]) == ("split", "split", None)
    assert out["split"] == 2 and ld.calls == []


def test_NEGATIVE_a_regular_session_alert_never_asks_the_split_lookup_for_its_same_column():
    sp = SplitLog(default="2026-10-16")
    st, ld = _xlab_store(), _xlab_loader()
    out = LG.grade_step(st, NIGHT_16, load_day=ld, split_lookup=sp)
    assert sp.calls == [] and out["split"] == 0 and out["same"] == 2


def test_NEGATIVE_today_read_holds_out_an_after_close_row_across_a_split_and_lists_it_not_read():
    st = _ah_split_store()
    sp = SplitLog({(D15, D16): "2026-10-16"})
    out = LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: pytest.fail("read across a split"),
                        clock=Clock(), split_lookup=sp)
    assert sp.calls == [("RSX", D15, D16)]
    assert (out["grades"], out["not_read"], out["through_et"], out["stats"]["split_held"]) == ({}, ["RSX"], None, 1)
    b = LG.served_block(st, D16, NOW_1130, span="5d", is_today=True, today=out)
    (row,) = [r for d in b["days"] for r in d["rows"]]
    assert row["same"]["state"] == "pending" and row["same"]["provisional"] is False
    assert b["counts"]["live"]["same"]["win"] == 0 and "WIN" not in json.dumps(row)
    assert b["today_text"] == "Today · not read on this open — graded tonight 20:15 ET"
    out2 = LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: pytest.fail("read"), clock=Clock(),
                         split_lookup=lambda *a: pytest.fail("asked again"))
    assert out2["not_read"] == ["RSX"]                      # an answered check is memoised for the session


def test_NEGATIVE_today_read_an_unread_split_check_is_not_read_and_asked_again_next_open():
    st, sp = _ah_split_store(), SplitLog(default=None)
    out = LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: pytest.fail("read"), clock=Clock(),
                        split_lookup=sp)
    assert out["not_read"] == ["RSX"] and out["grades"] == {}

    def boom(*a):
        raise RuntimeError("no key")
    out2 = LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: pytest.fail("read"), clock=Clock(),
                         split_lookup=boom)
    assert out2["not_read"] == ["RSX"] and LG._TODAY_SPLIT == {}
    out3 = LG.today_read(NOW_1130, store=st, load_frames=lambda s, d: (_post_split_bars(), False), clock=Clock(),
                         split_lookup=SplitLog())
    assert out3["not_read"] == [] and AH_SPLIT_ID in out3["grades"]


def test_NEGATIVE_today_read_never_asks_the_split_lookup_for_todays_own_rows():
    sp = SplitLog(default=True)
    out = LG.today_read(NOW_1225, store=_xlab_store(), load_frames=lambda s, d: (xlab_bars(), False), clock=Clock(),
                        split_lookup=sp)
    assert sp.calls == [] and len(out["grades"]) == 2


def test_NEGATIVE_the_default_lookup_never_uses_the_scanners_one_session_record_for_a_two_session_window(monkeypatch):
    st = fake_store()
    st.set_split_check(D16, "CCC", "ok")
    st.set_split_check(D15, "CCC", "ok")
    from chart_maps import drop10_tab as DT
    asked = []
    monkeypatch.setattr(DT, "fetch_splits_strict",
                        lambda s, since: asked.append(since) or [{"execution_date": "2026-10-16"}])
    look = LG._default_split_lookup(st)
    assert look("CCC", D15, D19) == "2026-10-16" and asked == ["2026-10-16"]       # (10-15, 10-19] spans two
    assert look("CCC", D15, D16) is False and asked == ["2026-10-16"]              # one session: the record
    monkeypatch.setattr(DT, "fetch_splits_strict", lambda s, since: (_ for _ in ()).throw(RuntimeError("x")))
    assert look("CCC", D15, D19) is None


# ── E6 through at the close; the W9b note never prints a missing time (critic fix round 2) ─────────────────────
def test_NEGATIVE_an_after_close_today_read_says_through_the_close_never_the_clock():
    st = store_with([pot_doc("AAA", "bull_flag", D16, et(D16, 10, 0), 10.0, 9.0)])
    out = LG.today_read(et(D16, 18, 0), store=st, load_frames=lambda s, d: (flat(D16, (10, 1), (19, 0), 9.5), False),
                        clock=Clock())
    g = out["grades"]["2026-10-16|AAA|bull_flag|potential"]
    assert out["through_et"] == "16:00" and LG._parse_at(g["through_t"]) == et(D16, 16, 0)


def test_NEGATIVE_a_push_without_a_ring_time_or_a_first_seen_time_serves_no_note():
    no_at = pot_doc("NOAT", "bull_flag", D15, None, 10.0, 9.0, first_seen_et="09:50")
    no_first = pot_doc("NOFS", "bull_flag", D15, et(D15, 9, 46), 10.0, 9.0)
    no_first.pop("first_seen_et")
    assert LG.alert_of(no_at, "potential")["plan_source"] == "first_sighting"
    assert LG.alert_of(no_first, "potential")["plan_source"] == "first_sighting"
    b = LG.served_block(store_with([no_at, no_first]), D16, NOW_1225, span="yesterday", is_today=True)
    rows = [r for d in b["days"] for r in d["rows"]]
    assert len(rows) == 2 and all(r["note"] is None for r in rows)
    assert "None" not in json.dumps(b)
    _assert_clean(b)


def test_NEGATIVE_a_note_never_serves_for_a_deferred_row_missing_a_time(monkeypatch):
    row = LG.alert_of(pot_doc("DEF", "bull_flag", D15, et(D15, 9, 46), 10.0, 9.0, first_seen_et="09:31"), "potential")
    assert row["plan_source"] == "first_sighting_deferred"
    real = LG.alert_of
    monkeypatch.setattr(LG, "alert_of", lambda d, k: dict(real(d, k), first_seen_et=None))
    st = store_with([pot_doc("DEF", "bull_flag", D15, et(D15, 9, 46), 10.0, 9.0, first_seen_et="09:31")])
    (r,) = [r for d in LG.served_block(st, D16, NOW_1225, span="yesterday", is_today=True)["days"] for r in d["rows"]]
    assert r["note"] is None


# ── source guards on the module ──────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_module_names_no_b_word_and_no_forecast_word():
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    src = Path(LG.__file__).read_text(encoding="utf-8")
    assert not B_WORD.search(src)
    import ast

    from tests.test_gajjala_source_guard import _string_literals
    tree = ast.parse(src)
    every = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [s for s in every for w in FORBIDDEN_WORDS if w in s.lower()]          # docstrings included
    assert not [s for s in _string_literals(tree) if SEPA_NAMES.search(s)]           # served literals (not docstrings)
