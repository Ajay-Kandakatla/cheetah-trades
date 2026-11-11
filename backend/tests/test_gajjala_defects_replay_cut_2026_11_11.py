"""Formulas audit D13 (2026-11-11, Ajay "Can you fix the defects please") — a `--now` replay read the 1-minute frame
UNCUT: the ☀️ premarket levels and the 🌙 K10 confirm summed minutes past the pass clock (audit demo
`L3/raw_cut_and_types.py`: a 16:10 replay listed RPLY on 600,000 after-hours shares; cut at 16:10 it is 22,594).

The fix (`run._upto`) cuts the frame at the pass clock in the three reads of `run.py` only (`pm_levels_for`, both
branches of the 🌙 `minutes(sym)` loader). A live pass is never cut (critic 2026-11-11: the pass clock is taken
before the frames load, so a minute that printed while the pass ran would have been dropped): `run_pass` hands `_upto`
`cut = now if now_given else None`, and `None` hands back the SAME frame. NEGATIVES: a frame with no later minute → the pass output byte-identical to the uncut code;
a minute starting AT `now` is excluded, one starting a second before is kept; None / empty pass through.
`in_window` is not touched (HIS CALL #9)."""
from __future__ import annotations

import ast
import inspect
import json
import textwrap
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from tests.test_gajjala_store import fake_store

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
DAY = date(2026, 11, 25)                                            # the audit demo's session (a full market day)
PREV = date(2026, 11, 24)
NOW = datetime(2026, 11, 25, 16, 10, tzinfo=ET)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def _naive_utc(dt):
    return dt.astimezone(UTC).replace(tzinfo=None)


def demo_minutes(day, rth_close_hhmm=(16, 0), ah_end_hhmm=(20, 0)):
    """The audit demo frame (`L3/k10_half_day.minutes`, same numbers): RTH 10.00–11.00 closing 10.90, the 16:00
    closing-cross minute, then after hours to 12.50 on 600,000 shares spread over the minutes 16:01 … end − 1."""
    rows, idx = [], []
    t = datetime.combine(day, datetime.min.time(), tzinfo=ET).replace(hour=9, minute=30)
    close = t.replace(hour=rth_close_hhmm[0], minute=rth_close_hhmm[1])
    end = t.replace(hour=ah_end_hhmm[0], minute=ah_end_hhmm[1])
    n_rth = int((close - t).total_seconds() // 60)
    n_ah = int((end - close).total_seconds() // 60) - 1
    for k in range(n_rth):
        px = 10.0 + 0.9 * k / (n_rth - 1)
        rows.append({"open": px, "high": min(11.0, px + 0.1), "low": max(10.0, px - 0.02), "close": px,
                     "volume": 5_000, "session": "rth"})
        idx.append(t + timedelta(minutes=k))
    rows.append({"open": 10.9, "high": 10.9, "low": 10.9, "close": 10.9, "volume": 40_000, "session": "rth"})
    idx.append(close)
    for k in range(n_ah):
        px = 11.5 + 1.0 * k / max(1, n_ah - 1)
        rows.append({"open": px, "high": px, "low": px - 0.02, "close": px, "volume": 600_000 / 239,
                     "session": "afterhours"})
        idx.append(close + timedelta(minutes=k + 1))
    return pd.DataFrame(rows, index=pd.DatetimeIndex([_naive_utc(x) for x in idx]))


def snap_row(price, prev, *, vol, when, close):
    ms = int(when.timestamp() * 1000)
    return {"last_trade_price": price, "last_trade_ts_ms": ms * 1_000_000, "prev_day_close": prev, "min_av": vol,
            "min_t_ms": ms, "volume": vol, "open": prev, "high": price, "low": prev, "close": close}


def _deps(frame, *, vol):
    """Fake deps over ONE name RPLY (price 12.40, regular close 10.90, prior close 9.00 — the demo's candidate).
    vol ≥ SCAN_MIN_VOLUME → a qualifier, read through `frames[sym].raw`; below it → the 🌙 `deps.load_day` branch."""
    rows = {"RPLY": snap_row(12.4, 9.0, vol=vol, when=datetime(2026, 11, 25, 16, 9, tzinfo=ET), close=10.9)}
    asked = []

    def load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
        asked.append((sym, day))
        return frame.copy() if day == DAY else None

    d = RUN.dry_deps()
    d.snapshot = lambda: (rows, {"http": 200, "wall_s": 0.1, "bytes": 1, "n": len(rows)})
    d.load_day = load_day
    d.halts = lambda: {"session_date": DAY.isoformat(), "by_ticker": {}}
    d.status_lookup = lambda sym, fetch=True: (None, "missing")
    d.massive_lookup = lambda sym: 5_000_000
    d.fetch_splits = lambda sym, since: []
    d.fetch_types = lambda: ({s: "CS" for s in rows}, True, 1)
    d.daily_loader = lambda sym, now=None: None
    d.clock = lambda: 0.0
    d.asked = asked                                                 # type: ignore[attr-defined]
    return d


def _pass(frame, *, vol, now=NOW):
    st = RUN.dry_store(fake_store())
    d = _deps(frame, vol=vol)
    out = RUN.run_pass(now, store=st, deps=d, dry=True)
    assert out["ran"] and out["tape_session"] == "afterhours", out
    return out, d


def _post(out):
    return {r["symbol"]: r for r in ((out.get("postmarket") or {}).get("rows") or [])}


# ── _upto, the unit ───────────────────────────────────────────────────────────────────────────────────────────────
def _grid(start_et, n, step=timedelta(minutes=1)):
    idx = [_naive_utc(start_et + k * step) for k in range(n)]
    return pd.DataFrame({"volume": list(range(1, n + 1))}, index=pd.DatetimeIndex(idx))


def test_upto_none_and_empty_pass_through():
    assert RUN._upto(None, NOW) is None
    empty = pd.DataFrame({"volume": []}, index=pd.DatetimeIndex([]))
    assert RUN._upto(empty, NOW) is empty


@pytest.mark.parametrize("now", [NOW, NOW.astimezone(UTC), _naive_utc(NOW)],
                         ids=["aware_et", "aware_utc", "naive_utc"])
def test_upto_cuts_at_the_pass_clock_whatever_the_zone_of_now(now):
    df = _grid(datetime(2026, 11, 25, 16, 5, tzinfo=ET), 10)        # 16:05 … 16:14
    cut = RUN._upto(df, now)
    assert len(cut) == 5 and cut.index[-1] == _naive_utc(datetime(2026, 11, 25, 16, 9, tzinfo=ET))


def test_NEGATIVE_a_minute_starting_AT_now_is_excluded_one_a_second_before_is_kept():
    at_now = _naive_utc(NOW)
    df = pd.DataFrame({"volume": [1.0, 2.0, 3.0]},
                      index=pd.DatetimeIndex([at_now - timedelta(seconds=1), at_now, at_now + timedelta(minutes=1)]))
    cut = RUN._upto(df, NOW)
    assert list(cut.index) == [at_now - timedelta(seconds=1)]
    assert list(cut["volume"]) == [1.0]


def test_NEGATIVE_nothing_at_or_after_now_returns_the_same_frame_not_a_copy():
    df = _grid(datetime(2026, 11, 25, 16, 0, tzinfo=ET), 10)        # 16:00 … 16:09, all before 16:10
    assert RUN._upto(df, NOW) is df


def test_NEGATIVE_a_live_pass_clock_of_None_keeps_every_minute_even_later_ones():
    df = demo_minutes(DAY)
    assert (df.index >= _naive_utc(NOW)).any()                     # the frame DOES hold minutes past 16:10
    assert RUN._upto(df, None) is df


def test_the_cut_clock_is_the_replay_clock_only():
    src = inspect.getsource(RUN.run_pass)
    assert src.count("cut = now if now_given else None") == 1
    assert src.count("_upto(") == 3 and "_upto(fr.raw, cut)" in src and "_upto(frames[sym].raw, cut)" in src
    assert ", now)" not in "".join(l for l in src.splitlines() if "_upto(" in l or "include_afterhours=True)" in l)


def test_upto_a_tz_aware_index_is_compared_aware():
    df = _grid(datetime(2026, 11, 25, 16, 5, tzinfo=ET), 10)
    df.index = df.index.tz_localize("UTC")
    cut = RUN._upto(df, NOW)
    assert len(cut) == 5


# ── the demo through run_pass ─────────────────────────────────────────────────────────────────────────────────────
def test_the_frame_holds_the_audit_demo_numbers():
    from chart_maps.gajjala import context as CX
    df = demo_minutes(DAY)
    uncut = CX._post_minutes(df, DAY)["ah_volume"]
    cut = CX._post_minutes(df[df.index < _naive_utc(NOW)], DAY)["ah_volume"]
    assert round(uncut) == 600_000 and round(cut) == 22_594
    assert cut < GC.K10_AH_MIN_VOLUME <= uncut


@pytest.mark.parametrize("vol", [3_000_000, 500_000], ids=["frames_branch", "load_day_branch"])
def test_a_1610_replay_never_lists_RPLY_on_minutes_past_the_clock(vol):
    out, d = _pass(demo_minutes(DAY), vol=vol)
    if vol >= GC.SCAN_MIN_VOLUME:
        assert "RPLY" in out["qualifiers"]                        # read through frames[sym].raw
    else:
        assert "RPLY" not in out["qualifiers"] and ("RPLY", DAY) in d.asked   # read through deps.load_day
    assert "RPLY" not in _post(out), _post(out)                    # 22,594 after-hours shares < 250,000
    assert out["postmarket"]["unchecked_n"] == 0                   # it WAS checked — and refused


@pytest.mark.parametrize("vol", [3_000_000, 500_000], ids=["frames_branch", "load_day_branch"])
def test_NEGATIVE_without_the_cut_the_same_replay_lists_RPLY(monkeypatch, vol):
    """The defect as the audit showed it: `_upto` made a pass-through → RPLY listed on 600,000 shares."""
    monkeypatch.setattr(RUN, "_upto", lambda raw, now: raw)
    out, _d = _pass(demo_minutes(DAY), vol=vol)
    assert round(_post(out)["RPLY"]["ah_volume"]) == 600_000


def _stable(out):
    return json.dumps({k: v for k, v in out.items() if k not in ("wall_s",)}, sort_keys=True, default=str)


@pytest.mark.parametrize("vol", [3_000_000, 500_000], ids=["frames_branch", "load_day_branch"])
def test_NEGATIVE_a_frame_with_no_later_minute_gives_a_byte_identical_pass(monkeypatch, vol):
    """A live pass: the frame ends before the clock (minutes 16:01 … 16:09 at 16:10) → the pass output equals the
    uncut code's, byte for byte."""
    frame = demo_minutes(DAY, ah_end_hhmm=(16, 10))
    assert frame.index[-1] < _naive_utc(NOW)
    fixed, _ = _pass(frame, vol=vol)
    monkeypatch.setattr(RUN, "_upto", lambda raw, now: raw)
    today, _ = _pass(frame, vol=vol)
    assert _stable(fixed) == _stable(today)
    assert "RPLY" not in _post(fixed)


def test_NEGATIVE_a_premarket_replay_reads_premarket_levels_only_up_to_the_clock():
    """☀️: a 08:00 replay over a frame that holds the whole pre-market — the levels stop at 07:59."""
    from chart_maps.gajjala import context as CX
    t0 = datetime(2026, 11, 25, 4, 0, tzinfo=ET)
    n = (9 * 60 + 30) - 4 * 60
    idx = [_naive_utc(t0 + timedelta(minutes=k)) for k in range(n)]
    df = pd.DataFrame({"open": 1.0, "high": [1.0 + k / 1000 for k in range(n)], "low": 1.0,
                       "close": [1.0 + k / 1000 for k in range(n)], "volume": 1_000.0, "session": "premarket"},
                      index=pd.DatetimeIndex(idx))
    now = datetime(2026, 11, 25, 8, 0, tzinfo=ET)
    cut = CX.pm_levels_for(RUN._upto(df, now), DAY)
    uncut = CX.pm_levels_for(df, DAY)
    assert cut is not None and uncut is not None
    assert cut["last"] == pytest.approx(1.0 + 239 / 1000) and uncut["last"] == pytest.approx(1.0 + (n - 1) / 1000)


# ── the three reads go through _upto (AST) ────────────────────────────────────────────────────────────────────────
def _calls_upto(node) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_upto"


def test_the_three_raw_reads_go_through_upto():
    tree = ast.parse(textwrap.dedent(inspect.getsource(RUN.run_pass)))
    pm = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
          and n.func.attr == "pm_levels_for"]
    assert len(pm) == 1 and _calls_upto(pm[0].args[0])
    mins = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "minutes"]
    assert len(mins) == 1
    rets = sorted((n for n in ast.walk(mins[0]) if isinstance(n, ast.Return)), key=lambda n: n.lineno)
    assert len(rets) == 2 and all(_calls_upto(r.value) for r in rets)
    inner = [r.value.args[0] for r in rets]
    assert isinstance(inner[0], ast.Attribute) and inner[0].attr == "raw"           # frames[sym].raw
    assert isinstance(inner[1], ast.Call) and isinstance(inner[1].func, ast.Attribute) \
        and inner[1].func.attr == "load_day"                                         # deps.load_day(...)


def test_NEGATIVE_no_bare_raw_read_left_in_run_pass():
    """Every `.raw` read inside run_pass sits inside an `_upto(...)` call."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(RUN.run_pass)))
    wrapped = {id(a) for n in ast.walk(tree) if _calls_upto(n) for a in n.args}
    raws = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "raw"]
    assert raws and all(id(n) in wrapped for n in raws)


def test_NEGATIVE_in_window_is_untouched():
    """HIS CALL #9: the pass schedule is not part of this fix."""
    assert "_upto" not in inspect.getsource(RUN.in_window)
