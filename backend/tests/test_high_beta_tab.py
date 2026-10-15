"""🎢 High Beta tab (chart_maps/high_beta_tab.py) — behaviour, negatives,
memo, board wiring, the watch list and source guards.

Ajay 2026-10-14, verbatim: "Can you create a new tab for High Beta stocks" ·
"give me all 3 categories" · "in the High Beta tab.I wanna able to sort my most
volatile stocks".

Every number the tests assert is derived from the module's constants or from
the frames built here; the boundary tests sit exactly on the cuts.
"""
from __future__ import annotations

import ast
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps import board as BOARD
from chart_maps import drop10_tab as D10
from chart_maps import high_beta_tab as HB
from chart_maps import membership as MEM
from sepa import beta as BETA

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]

FRI = date(2026, 10, 2)
THU = "2026-10-01"
NOW_RTH = datetime(2026, 10, 2, 11, 0, tzinfo=ET)
NOW_AFTER = datetime(2026, 10, 2, 17, 0, tzinfo=ET)
NOW_NIGHT = datetime(2026, 10, 5, 2, 0, tzinfo=ET)          # Monday 02:00 -> Friday closed
N_BARS = 300


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


_IDX = pd.DatetimeIndex(_market_days(FRI.isoformat(), N_BARS))
_SPY_LR = np.random.RandomState(7).normal(0.0004, 0.01, N_BARS)


def _frame(beta: float, *, n: int = N_BARS, move=None, base: float = 100.0, end_thu=False,
           volume: float = 1_000_000.0):
    """Log returns = beta × SPY's on the same calendar (so β is exact); the
    last (Friday) bar moves `move` % against Thursday's close when given."""
    lr = beta * _SPY_LR[-n:]
    close = base * np.exp(np.cumsum(lr))
    df = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                       "close": close, "volume": volume}, index=_IDX[-n:])
    if move is not None:
        prev = float(df["close"].iloc[-2])
        c = prev * (1 + move / 100.0)
        for k, v in (("open", prev), ("high", max(prev, c) * 1.001),
                     ("low", min(prev, c) * 0.999), ("close", c)):
            df.iloc[-1, df.columns.get_loc(k)] = v
    return df.iloc[:-1] if end_thu else df


def _prev(df_full) -> float:
    return round(float(df_full["close"].iloc[-2]), 4)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _snap(last, prev, *, at=datetime(2026, 10, 2, 10, 59, tzinfo=ET)):
    return {"open": prev, "high": max(prev, last) * 1.001, "low": min(prev, last) * 0.999,
            "close": last, "volume": 2e6, "prev_day_close": prev, "min_t_ms": _ms(at),
            "last_trade_ts_ms": _ms(at) * 1_000_000, "date": pd.Timestamp("2026-10-05")}


def _bench():
    return {"SPY": _frame(1.0, move=-1.0), "RSP": _frame(1.0, move=-0.8),
            "QQQ": _frame(1.2, move=-1.5)}


def _frames():
    """AAA β2.5 −7%, BBB β2.0 −5.0%, CCC β1.6 −4.9%, DDD β1.5 +2%, EEE β1.49 −9%
    (not listed), LOW β0.8, SHORT 200 bars (no β), XLV an ETF with β 3.4."""
    f = {"AAA": _frame(2.5, move=-7.0), "BBB": _frame(2.0, move=-5.0),
         "CCC": _frame(1.6, move=-4.9), "DDD": _frame(1.5, move=2.0),
         "EEE": _frame(1.49, move=-9.0), "LOW": _frame(0.8, move=-1.0),
         "SHORT": _frame(3.0, n=200, move=-8.0), "XLV": _frame(3.4, move=-6.0)}
    f.update(_bench())
    return f


UNIVERSE = ["AAA", "BBB", "CCC", "DDD", "EEE", "LOW", "SHORT", "XLV"]


def _build(frames, now, *, universe=None, qqq=("AAA",), snaps=None, snap_calls=None,
           etfs=("XLV", "SPY", "RSP", "QQQ"), dead=()):
    def snap_fn(syms):
        if snap_calls is not None:
            snap_calls.append(list(syms))
        return {s: v for s, v in (snaps or {}).items() if s in syms}

    def qqq_fn():
        if isinstance(qqq, Exception):
            raise qqq
        return list(qqq)

    return HB.build("full", now, universe_fn=lambda u: list(universe or UNIVERSE),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    qqq_fn=qqq_fn, etf_fn=lambda: set(etfs), is_delisted=lambda s: s in dead,
                    snap_fn=snap_fn)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for m in (HB._memo, HB._base_memo, HB._failures):
        m.clear()
    HB._warming.clear()
    spawned = []
    monkeypatch.setattr(HB, "_spawn", lambda target, name: spawned.append((target, name)))
    return spawned


# --------------------------------------------------------------------------
# 1 — wording guard (AST over every string constant, docstrings included)
# --------------------------------------------------------------------------
def _strings(path: Path, skip_assign: str = "") -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and skip_assign
                and any(isinstance(t, ast.Name) and t.id == skip_assign for t in node.targets)):
            skip |= {id(n) for n in ast.walk(node.value)}
    return " ".join(n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and id(n) not in skip).lower()


def test_01_NEG_guard_no_bounce_fake_or_forecast_words():
    words = _strings(BACKEND / "chart_maps" / "high_beta_tab.py", skip_assign="FORBIDDEN_WORDS")
    assert "unmeasured" in words
    for w in HB.FORBIDDEN_WORDS:
        assert w not in words, w
    m = _strings(BACKEND / "chart_maps" / "high_beta_measured.py")
    for w in HB.FORBIDDEN_WORDS:
        assert w not in m, w
    # the list itself carries the two words the spec names
    assert "bounce" in HB.FORBIDDEN_WORDS and "fake" in HB.FORBIDDEN_WORDS


def test_01b_NEG_the_guard_catches_a_planted_word(tmp_path):
    p = tmp_path / "x.py"
    p.write_text('"""a docstring that says rebound"""\nFORBIDDEN_WORDS = ("bounce",)\n')
    words = _strings(p, skip_assign="FORBIDDEN_WORDS")
    assert "rebound" in words and "bounce" not in words


def test_01c_served_words_say_unmeasured_and_quote_the_order(monkeypatch):
    assert "UNMEASURED" in HB.NOTE_PENDING and "largest β × today's drop first" in HB.NOTE_PENDING
    assert f"{HB.BETA_LOOKBACK} daily log returns" in HB.NOTE_PENDING
    # the placeholder literal (before the study ran) serves the UNMEASURED note verbatim …
    from chart_maps import high_beta_measured as HBM
    monkeypatch.setattr(HBM, "MEASURED", {"state": "unmeasured"})
    assert HB.study_block()["status"] == "unmeasured" and HB.note_text() == HB.NOTE_PENDING


def test_01d_the_measured_literal_serves_the_study_line_not_the_placeholder():
    # 2026-10-14: the study ran (prereg 80c5f516) and the literal was pasted; the served line
    # carries its verdict + CI, never a forecast word, and the placeholder note is gone
    from chart_maps import high_beta_measured as HBM
    m = HBM.load()
    assert m.get("status") == "measured" and m["prereg_commit"] == "80c5f516"
    sb = HB.study_block()
    assert sb["status"] == "measured" and HB.note_text() == sb["text"] != HB.NOTE_PENDING
    assert "MEASURED" in sb["text"] and "80c5f516" in sb["text"]
    assert f"{m['primary']['contrast_pp']:+.2f} pp" in sb["text"]
    assert "an order, not a forecast" in sb["text"]
    assert not any(w in sb["text"].lower() for w in HB.FORBIDDEN_WORDS)


# --------------------------------------------------------------------------
# 2 — one β engine
# --------------------------------------------------------------------------
def test_02_beta_from_frame_equals_beta_for_on_identical_frames(monkeypatch):
    import sepa.prices
    spy, stock = _frame(1.0), _frame(2.3)
    monkeypatch.setattr(sepa.prices, "load_prices", lambda sym, *a, **k: spy if sym == "SPY" else stock)
    BETA._cache.clear()
    BETA._spy_lr_cache.update(date=None, lr=None)
    want = BETA.beta_for("ZZZ")
    got = BETA.beta_from_frame(stock, BETA._log_returns(spy))
    assert got == want == 2.3
    assert BETA.log_returns(spy).equals(BETA._log_returns(spy))


def test_02b_NEG_251_aligned_returns_is_none_252_is_a_beta():
    spy_lr = BETA.log_returns(_frame(1.0))
    assert BETA.beta_from_frame(_frame(2.0, n=BETA.BETA_LOOKBACK), spy_lr) is None      # 251 returns
    assert BETA.beta_from_frame(_frame(2.0, n=BETA.BETA_LOOKBACK + 1), spy_lr) == 2.0
    assert BETA.beta_from_frame(None, spy_lr) is None
    assert BETA.beta_from_frame(_frame(2.0), None) is None


# --------------------------------------------------------------------------
# 3 / 4 — rating and the three categories
# --------------------------------------------------------------------------
def test_03_NEG_beta_none_is_excluded_and_counted():
    e = _build(_frames(), NOW_NIGHT)
    assert "SHORT" not in e["rows"] and e["counts"]["short_history"] == 1
    assert e["counts"]["scanned"] == len(UNIVERSE)
    total = sum(e["counts"][k] for k in HB.BASE_STATUSES)
    assert total == e["counts"]["scanned"]


def test_04_categories_boundaries_ties_and_the_empty_universe():
    cats, blk = HB.categories({"A": 1.50, "B": 1.49, "C": 2.00, "D": 1.99})
    assert "b15" in cats["A"] and "b15" not in cats.get("B", [])
    assert "b20" in cats["C"] and "b20" not in cats["D"]
    # top 20% of 4 rated = ceil(0.8) = 1 -> the single highest (C)
    assert blk["top20"]["k"] == 1 and blk["top20"]["cut_beta"] == 2.00 and cats["C"][-1] == "top20"
    # ties at the cut are included
    cats, blk = HB.categories({"A": 3.0, "B": 3.0, "C": 1.0, "D": 0.5, "E": 0.4,
                               "F": 0.3, "G": 0.2, "H": 0.1, "I": 0.1, "J": 0.1})
    assert blk["top20"]["k"] == 2 and "top20" in cats["A"] and "top20" in cats["B"]
    cats, blk = HB.categories({"A": 3.0, "B": 2.9, "C": 2.9, "D": 0.1, "E": 0.1,
                               "F": 0.1, "G": 0.1, "H": 0.1, "I": 0.1, "J": 0.1, "K": 0.1})
    assert blk["top20"]["k"] == math.ceil(11 * HB.TOP_PCT / 100) == 3
    cats, blk = HB.categories({"A": 3.0, "B": 2.9, "C": 2.8, "D": 2.8, "E": 0.1,
                               "F": 0.1, "G": 0.1, "H": 0.1, "I": 0.1, "J": 0.1, "K": 0.1})
    assert blk["top20"]["cut_beta"] == 2.8 and blk["top20"]["n"] == 4      # tie at the 3rd
    cats, blk = HB.categories({})
    assert cats == {} and blk["top20"]["cut_beta"] is None and blk["top20"]["k"] == 0


def test_04b_NEG_an_etf_is_never_rated_nor_in_the_top20_denominator():
    e = _build(_frames(), NOW_NIGHT)
    assert "XLV" not in e["rows"] and e["counts"]["etf"] == 1
    rated = e["counts"]["rated"]
    assert e["categories"]["top20"]["of"] == rated == 6        # AAA BBB CCC DDD EEE LOW
    assert "EEE" not in e["rows"]                              # β 1.49, not in the top 20%
    assert e["rows"]["AAA"]["cats"] == ["b15", "b20", "top20"]
    assert e["rows"]["DDD"]["cats"] == ["b15"]


# --------------------------------------------------------------------------
# 5 — the Nasdaq-100
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [RuntimeError("wiki down"), ()])
def test_05_NEG_a_failed_or_empty_ndx_read_never_crashes_and_no_name_gets_a_badge(bad):
    e = _build(_frames(), NOW_NIGHT, qqq=bad)
    assert e["qqq"]["available"] is False and e["qqq"]["error"]
    assert all(r["qqq"] is False and r["hb_filter"]["qqq"] is None for r in e["rows"].values())
    rows, _c, f = HB.rank(e, sort="default", active=("qqq",), include_green=True)
    assert rows == []                                             # ticked: passes no name
    item = next(i for i in f["items"] if i["key"] == "qqq")
    assert item["off"] is True and item["off_reason"] == HB.QQQ_OFF_REASON
    assert "could not be read" in HB.qqq_line(e["qqq"], e["summary"], e["rows"])
    r = e["rows"]["AAA"]
    assert "QQQ" not in HB.category_pill(r)


def test_05b_an_ndx_name_absent_from_full_is_added_and_counted():
    fr = _frames()
    fr["NDXONLY"] = _frame(2.2, move=-6.0)
    e = _build(fr, NOW_NIGHT, qqq=("AAA", "NDXONLY"))
    assert e["counts"]["scanned"] == len(UNIVERSE) + 1 and e["counts"]["ndx_added"] == 1
    assert e["rows"]["NDXONLY"]["qqq"] is True and e["rows"]["AAA"]["qqq"] is True
    assert e["rows"]["BBB"]["qqq"] is False and e["rows"]["AAA"]["hb_filter"]["qqq"] is True
    assert HB.category_pill(e["rows"]["AAA"]).endswith(" · QQQ")


# --------------------------------------------------------------------------
# 6 / 7 / 8 — today's move: prior close, modes, no print
# --------------------------------------------------------------------------
def _row(prev=4.025):
    return {"symbol": "NNBR", "beta": 2.0, "prev_close": prev, "prev_date": THU, "bar": None}


def test_06_official_prior_close_within_tolerance_is_used():
    raw = _snap(4.0, 4.04)
    td, _ms_ = HB.today_read(_row(), raw, mode=HB.MODE_LIVE, session=FRI)
    assert td["state"] == "read" and td["prev_close"] == 4.04
    assert td["move_pct"] == round((4.0 / 4.04 - 1) * 100, 2) == -0.99
    assert td["basis"] == "live"


def test_06b_NEG_a_prior_close_beyond_tolerance_or_a_glitch_is_held_out():
    tol = D10.PREV_CLOSE_TOL_PCT
    raw = _snap(9.0, 10.0 * (1 + (tol + 0.5) / 100))
    td, _ = HB.today_read(_row(10.0), raw, mode=HB.MODE_LIVE, session=FRI)
    assert td["state"] == "suspect" and td["move_pct"] is None and "disagrees" in td["reason"]
    glitch = _snap(100.0, 10.0)
    td, _ = HB.today_read(_row(10.0), glitch, mode=HB.MODE_LIVE, session=FRI)
    assert td["state"] == "suspect" and td["move_pct"] is None
    fr = _frames()
    full = fr["AAA"]
    fr = {k: v.iloc[:-1] for k, v in fr.items()}
    snaps = {"AAA": _snap(10.0, _prev(full) * 1.5)}
    e = _build(fr, NOW_RTH, snaps=snaps)
    assert e["rows"]["AAA"]["today"]["state"] == "suspect" and e["counts"]["suspect"] == 1
    blk = HB.suspects_block(e["suspects"])
    assert blk["n"] == 1 and blk["lines"][0].startswith("AAA — print 10.00 vs prior close")


def test_07_three_modes():
    fr = _frames()
    e = _build(fr, NOW_NIGHT)
    td = e["rows"]["AAA"]["today"]
    assert e["mode"] == HB.MODE_CLOSED and td["basis"] == HB.LAST_BASIS and td["move_pct"] == -7.0
    thu = {k: v.iloc[:-1] for k, v in fr.items()}
    HB._base_memo.clear()
    snaps = {"AAA": _snap(_prev(fr["AAA"]) * 0.9, _prev(fr["AAA"]))}
    e = _build(thu, NOW_RTH, snaps=snaps)
    assert e["mode"] == HB.MODE_LIVE and e["rows"]["AAA"]["today"]["basis"] == "live"
    assert e["rows"]["AAA"]["today"]["move_pct"] == -10.0
    HB._base_memo.clear()
    snaps = {"AAA": _snap(_prev(fr["AAA"]) * 0.9, _prev(fr["AAA"]),
                          at=datetime(2026, 10, 2, 15, 59, tzinfo=ET))}
    e = _build(thu, NOW_AFTER, snaps=snaps)
    assert e["mode"] == HB.MODE_AFTER and e["rows"]["AAA"]["today"]["basis"] == "day_close"


def test_07b_NEG_an_overnight_snapshot_carrying_the_last_bar_is_never_read():
    raw = _snap(9.0, 10.0, at=datetime(2026, 10, 1, 15, 59, tzinfo=ET))      # Thursday's bar
    td, _ = HB.today_read(_row(10.0), raw, mode=HB.MODE_LIVE, session=FRI)
    assert td["state"] == "no_print" and td["move_pct"] is None


def test_08_NEG_no_print_is_never_plus_zero_and_no_answer_is_no_snapshot():
    fr = {k: v.iloc[:-1] for k, v in _frames().items()}
    calls = []
    e = _build(fr, NOW_RTH, snaps={"SPY": _snap(100, 100)}, snap_calls=calls)
    assert len(calls) == 2                                       # asked twice
    r = e["rows"]["AAA"]
    assert r["today"]["state"] == "no_snapshot" and e["counts"]["no_snapshot"] == len(e["rows"])
    stats = {s["k"]: s["v"] for s in HB.tile_stats(r)}
    assert "+0.00%" not in stats["Today"] and stats["Today"].startswith("no snapshot answer")
    assert stats["β × drop"] == "—" and r["swing"] is None
    raw = _snap(0, 0)
    td, _ = HB.today_read(_row(10.0), raw, mode=HB.MODE_LIVE, session=FRI)
    assert td["state"] == "no_print"
    assert "+0.00%" not in HB.today_text(td)
    assert [b for b in HB.tile_badges({**r, "today": td}) if b["text"].startswith("\U0001F4C5")] == []


def test_08b_NEG_an_empty_snapshot_or_frames_read_raises_and_is_not_memoised():
    fr = {k: v.iloc[:-1] for k, v in _frames().items()}
    with pytest.raises(RuntimeError):
        _build(fr, NOW_RTH, snaps={})
    HB._base_memo.clear()
    with pytest.raises(RuntimeError):
        HB.build("full", NOW_NIGHT, universe_fn=lambda u: ["AAA"], frames_fn=lambda s: {},
                 qqq_fn=list, etf_fn=set, is_delisted=lambda s: False)
    assert HB._base_memo == {}


# --------------------------------------------------------------------------
# 9 — the three orders
# --------------------------------------------------------------------------
def _r(sym, beta, move, *, state="read", sigma=None):
    td = {"state": state, "move_pct": move if state == "read" else None}
    return {"symbol": sym, "beta": beta, "sigma_pct": sigma, "cats": ["b15"], "qqq": False,
            "today": td, "swing": HB.swing(beta, move if state == "read" else None),
            "hb_filter": HB.tile_filter({"cats": ["b15"], "qqq": False, "today": td},
                                        qqq_available=True)}


def _entry(*rows):
    return {"rows": {r["symbol"]: r for r in rows}, "counts": {}, "qqq": {"available": True}}


def test_09_orders_swing_drop_vol_green_after_red_unread_last():
    e = _entry(_r("A", 3.0, -4.0, sigma=2.0), _r("B", 1.5, -7.0, sigma=5.0),
               _r("C", 2.0, -6.0, sigma=None), _r("D", 2.0, 1.0, sigma=9.0),
               _r("E", 2.0, None, state="no_print", sigma=1.0), _r("F", 2.0, 0.0, sigma=3.0),
               _r("G", 2.0, -6.0, sigma=4.0))
    # swing: A 12.0, C 12.0, G 12.0 (tie -> move then symbol), B 10.5
    order = [r["symbol"] for r in HB.rank(e, sort="default", include_green=True)[0]]
    assert order == ["C", "G", "A", "B", "F", "D", "E"]
    order = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_DROP, include_green=True)[0]]
    assert order == ["B", "C", "G", "A", "F", "D", "E"]
    order = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_VOL, include_green=True)[0]]
    assert order == ["D", "B", "G", "F", "A", "E", "C"]                 # σ None last
    assert HB.resolve_sort("default") == HB.SORT_SWING == HB.resolve_sort("volume")


def test_09b_NEG_tab_keys_are_tab_scoped(hb_board):
    assert BOARD.board(tab="drop10", sort=HB.SORT_DROP)["sort"] == "default"
    out = BOARD.board(tab="high_beta", sort="volume", limit=24)
    assert out["sort"] == HB.SORT_SWING and out["high_beta_board"]["sort"] == HB.SORT_SWING
    out = BOARD.board(tab="high_beta", sort=HB.SORT_VOL, limit=24)
    assert out["sort"] == HB.SORT_VOL
    assert not set(HB.TAB_SORTS) & set(BOARD.SORTS)
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    assert '(t == "high_beta" and sort in _HB.TAB_SORTS)' in src


def test_09c_swing_is_beta_times_the_drop_and_zero_when_green():
    assert HB.swing(2.5, -7.0) == 17.5 and HB.swing(2.5, 3.0) == 0.0
    assert HB.swing(None, -3.0) is None and HB.swing(2.0, None) is None


# --------------------------------------------------------------------------
# 10 — the five boxes and the view
# --------------------------------------------------------------------------
def test_10_d5_boundary_a_name_down_4_9_is_not_d5():
    e = _build(_frames(), NOW_NIGHT)
    assert e["rows"]["BBB"]["hb_filter"]["d5"] is True                  # exactly −5.00%
    assert e["rows"]["CCC"]["hb_filter"]["d5"] is False                 # −4.90%
    assert e["rows"]["AAA"]["hb_filter"]["d5"] is True
    assert e["counts"]["down5"] == 2


def test_10b_filters_any_default_all_mode_junk_dropped_unread_hidden():
    assert HB.parse_filters("b20, junk,D5,+qqq") == ("b20", "qqq", "d5")
    assert HB.parse_filters(None) == () and HB.parse_mode("ALL ") == "all" and HB.parse_mode("x") == "any"
    e = _entry(_r("A", 2.5, -7.0), _r("B", 1.6, -6.0), _r("C", 2.5, -1.0),
               _r("U", 2.5, None, state="no_print"))
    e["rows"]["A"]["hb_filter"]["b20"] = True
    e["rows"]["C"]["hb_filter"]["b20"] = True
    e["rows"]["U"]["hb_filter"]["b20"] = True
    rows, _c, f = HB.rank(e, sort="default", active=("b20", "d5"), include_green=True)
    assert [r["symbol"] for r in rows] == ["A", "B", "C", "U"]           # ANY
    rows, _c, f = HB.rank(e, sort="default", active=("b20", "d5"), mode="all", include_green=True)
    assert [r["symbol"] for r in rows] == ["A"]                          # ALL
    d5 = next(i for i in f["items"] if i["key"] == "d5")
    assert d5["no_read"] == 1 and d5["pass"] == 2 and d5["hidden"] == 2
    rows, _c, _f = HB.rank(e, sort="default", active=("d5",), include_green=True)
    assert "U" not in [r["symbol"] for r in rows]                        # unread never passes
    assert f["mode_param"] == HB.FILTER_MODE_PARAM and f["keys"] == list(HB.FILTER_KEYS)


def test_10c_hb_all_default_false_is_red_only():
    e = _entry(_r("A", 2.5, -7.0), _r("D", 2.0, 1.0), _r("U", 2.5, None, state="no_print"))
    rows, c, _f = HB.rank(e, sort="default")
    assert [r["symbol"] for r in rows] == ["A"] and c["hidden_by_view"] == 2
    rows, c, _f = HB.rank(e, sort="default", include_green=True)
    assert [r["symbol"] for r in rows] == ["A", "D", "U"] and c["hidden_by_view"] == 0
    import inspect
    assert inspect.signature(BOARD.board).parameters["hb_all"].default is False


# --------------------------------------------------------------------------
# 11 — NBIS + IREN in the universe (positive pin)
# --------------------------------------------------------------------------
def test_11_nbis_and_iren_are_in_the_static_layers_of_full():
    from sepa import symbols
    from sepa import universe as U
    assert "NBIS" in U.UNIVERSE and "NBIS" in U.THEME_UNIVERSE["ai_power"]
    assert "IREN" in U.THEME_UNIVERSE["ai_power"]
    assert not symbols.is_delisted("NBIS") and not symbols.is_delisted("IREN")
    syms, _n = HB.resolve_symbols("full", frozenset(), universe_fn=lambda u: ["nbis", "IREN", "NBIS"])
    assert syms == ["NBIS", "IREN"]


# --------------------------------------------------------------------------
# 12 — the memo
# --------------------------------------------------------------------------
def _patch_build(monkeypatch, frames, **kw):
    real = HB.build

    def qqq_fn():
        q = kw.get("qqq", ("AAA",))
        if isinstance(q, Exception):
            raise q
        return list(q)

    def fake(universe, now, **k):
        return real(universe, now, universe_fn=lambda u: list(kw.get("universe") or UNIVERSE),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    qqq_fn=qqq_fn, etf_fn=lambda: {"XLV", "SPY", "RSP", "QQQ"},
                    is_delisted=lambda s: False, snap_fn=kw.get("snap_fn"))
    monkeypatch.setattr(HB, "build", fake)


def test_12_warming_then_ready_spawns_once(monkeypatch, _clean):
    _patch_build(monkeypatch, _frames())
    assert HB.cached_or_warm("full", now=NOW_NIGHT)["state"] == "warming"
    HB.cached_or_warm("full", now=NOW_NIGHT)
    assert len(_clean) == 1
    _clean[0][0]()
    got = HB.cached_or_warm("full", now=NOW_NIGHT)
    assert got["state"] == "ready" and "AAA" in got["entry"]["rows"]


def test_12b_NEG_a_failure_is_an_error_block_backed_off_then_retried(monkeypatch, _clean):
    import time as _t
    monkeypatch.setattr(HB, "build", lambda u, now, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    HB.cached_or_warm("full", now=NOW_NIGHT)
    _clean[0][0]()
    got = HB.cached_or_warm("full", now=NOW_NIGHT)
    assert got["state"] == "error" and got["reason"] == "boom" and len(_clean) == 1
    key = (HB.MODE_CLOSED, FRI.isoformat(), "full")
    HB._failures[key] = (_t.time() - HB.FAIL_RETRY_SEC - 1, "boom")
    HB.cached_or_warm("full", now=NOW_NIGHT)
    assert len(_clean) == 2                                      # retried after the back-off


def test_12c_NEG_a_late_older_session_build_is_dropped():
    HB._memo[(HB.MODE_CLOSED, "2026-10-05", "full")] = {"built_ts": 1.0}
    assert HB._store((HB.MODE_CLOSED, "2026-10-02", "full"), {"built_ts": 2.0}) is False
    assert list(HB._memo) == [(HB.MODE_CLOSED, "2026-10-05", "full")]


def test_12d_the_memo_rows_are_never_mutated_by_a_request(hb_board):
    key = (HB.MODE_CLOSED, FRI.isoformat(), "full")
    before = repr(HB._memo[key]["rows"])
    BOARD.board(tab="high_beta", limit=24, hb="b20,d5", hb_all=True)
    assert repr(HB._memo[key]["rows"]) == before


# --------------------------------------------------------------------------
# 13 — board wiring
# --------------------------------------------------------------------------
class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW_NIGHT.astimezone(tz) if tz else NOW_NIGHT.replace(tzinfo=None)


class _FakeColl:
    def __init__(self):
        self.docs, self.writes = {}, 0

    def replace_one(self, flt, doc, upsert=False):
        self.writes += 1
        self.docs[flt["_id"]] = dict(doc)


class _FakeDB:
    def __init__(self):
        self.coll = _FakeColl()

    def __getitem__(self, name):
        return self.coll


def _stub_board(monkeypatch, state):
    from supply_demand import zone_store

    def _snaps(syms):
        state["snap_calls"].append(list(syms))
        return {}

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": FRI.isoformat(), "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    def _enterable(tiles, kind="demand", **k):
        for t in tiles:
            t.setdefault("enterable", {"verdict": "WATCH", "kind": kind})
        return len(tiles)

    monkeypatch.setattr(BOARD, "datetime", _Fixed)
    monkeypatch.setattr(BOARD, "_bulk_snaps", _snaps)
    monkeypatch.setattr(BOARD, "_attach_bars", _bars)
    monkeypatch.setattr(BOARD, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(BOARD, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(BOARD, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(BOARD, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(BOARD, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(BOARD, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(BOARD, "attach_enterable", _enterable)
    monkeypatch.setattr(BOARD, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(BOARD, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(BOARD, "attach_burst", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(BOARD, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(BOARD, "attach_key_levels", lambda tiles, out=None, **k: None)
    monkeypatch.setattr(zone_store, "load_latest", lambda syms: (None, {}))


@pytest.fixture
def hb_board(monkeypatch):
    state = {"snap_calls": [], "db": _FakeDB()}
    fr = _frames()
    fr["THIN"] = _frame(2.4, move=-6.0, volume=100.0)
    _patch_build(monkeypatch, fr, universe=UNIVERSE + ["THIN"])
    _stub_board(monkeypatch, state)
    monkeypatch.setattr(MEM, "_db", lambda db=None: state["db"])
    HB.cached_or_warm("full", now=NOW_NIGHT, sync=True)
    return state


_BOARD_KEYS = {"state", "mode", "session", "as_of", "built_at", "base_built_at", "stale",
               "measured", "refresh_sec", "sort", "header", "market_line", "qqq_line",
               "order_line", "view_line", "count_line", "categories_line", "categories", "qqq",
               "filters", "view", "table", "note", "study", "counts", "suspects"}
_TILE_HB_KEYS = {"beta", "cats", "qqq", "sigma_pct", "swing", "today", "adv50", "zone"}
_ROW_KEYS = {"symbol", "beta", "cats", "qqq", "move_pct", "state", "swing", "sigma_pct",
             "prev_close", "basis", "thin", "red", "text"}


def test_13_board_ready_envelope_rows_and_tiles(hb_board):
    assert BOARD.TABS[-1] == "high_beta" and BOARD.TABS[-2] == "drop10"
    out = BOARD.board(tab="high_beta", limit=24)
    assert out["tab"] == "high_beta" and out["sort"] == HB.SORT_SWING
    assert out["sorts"] == HB.served_sorts() and len(out["sorts"]) == 3
    b = out["high_beta_board"]
    # `measured` follows the literal (False before the study ran, True since 2026-10-14) and the
    # note is whatever study_block serves for that state
    assert set(b) == _BOARD_KEYS and b["state"] == "ready"
    assert b["measured"] is (HB.study_block()["status"] == "measured")
    assert b["note"] == HB.note_text() and b["refresh_sec"] is None
    syms = [t["symbol"] for t in out["tiles"]]
    assert syms == ["AAA", "BBB", "CCC"]                 # red only, swing order, THIN under the floor
    t = out["tiles"][0]
    assert set(t["high_beta"]) == _TILE_HB_KEYS and set(t["hb_filter"]) == set(HB.FILTER_KEYS)
    assert t["badges"][0]["text"] == "\U0001F3A2 β 2.50 · ≥1.5 · ≥2.0 · top 20% · QQQ"
    assert t["badges"][1]["text"].startswith("\U0001F4C5 last session Fri 10-02 · -7.00%")
    assert t["why"].startswith("\U0001F3A2 β 2.50 · today −7.00% · β × drop 17.50 · ")
    assert {s["k"] for s in t["stats"]} >= {"β", "Today", "β × drop", HB.STAT_SIGMA}
    rows = out["rows"]
    assert all(set(r) == _ROW_KEYS for r in rows)
    # A1 / K2 "every red name": the floor cuts the charts, never the table —
    # THIN (β 2.4, −6%, $100/day) is a row (swing order, flagged thin), no tile.
    assert [r["symbol"] for r in rows] == ["AAA", "THIN", "BBB", "CCC"]
    assert [r["symbol"] for r in rows if r["thin"]] == ["THIN"] and "THIN" not in syms
    assert all(r["qqq"] is (r["symbol"] == "AAA") for r in rows)       # list read: True/False
    assert set(syms) <= {r["symbol"] for r in rows}                      # rows ⊇ tiles
    c = b["counts"]
    assert c["dropped_thin"] == 1 and c["shown"] == 3 and c["rows"] == 4
    assert "listed in the table as thin, no chart" in b["count_line"]
    assert b["header"].startswith("\U0001F3A2 4 red of 5 High-Beta names · charts for the top 3")
    assert "Red names only" in b["view_line"] and b["view"]["on"] is False
    assert len(hb_board["snap_calls"]) == 1 and set(hb_board["snap_calls"][0]) == set(syms)
    # A1 table: served heads (the card's stat keys) + one engine for the cell text.
    tb = b["table"]
    assert [c["key"] for c in tb["columns"]] == [k for k, _l in HB.TABLE_COLUMNS]
    assert {c["label"] for c in tb["columns"]} >= {"β", "Today", "β × drop", HB.STAT_SIGMA}
    assert tb["cat_labels"] == HB.CAT_SHORT and tb["qqq_label"] == HB.QQQ_ETF
    by = {s["k"]: s["v"] for s in t["stats"]}
    assert rows[0]["text"] == {"beta": by["β"], "today": by["Today"], "swing": by["β × drop"],
                               "sigma": by[HB.STAT_SIGMA]}
    assert all(r["red"] is True for r in rows)


def test_13a_NEG_green_and_unread_rows_are_not_red_and_never_print_a_bare_number():
    green, unread, nos = _r("UP", 2.0, 3.0, sigma=4.0), _r("NOP", 2.0, None, state="no_print"), \
        _r("NS", 2.0, -6.0)
    for r in (green, nos):
        r["today"]["prev_close"] = 50.0
    g, u, n = (HB.compact_row(x, qqq_available=True) for x in (green, unread, nos))
    assert g["red"] is False and u["red"] is False and n["red"] is True
    assert g["text"]["swing"] == "— (up or flat today)" and u["text"]["swing"] == "—"
    assert u["text"]["today"] != "+0.00%" and "0.00" not in u["text"]["today"]
    assert n["text"]["sigma"] == "—"                                      # no σ -> dash
    assert n["text"]["today"] == "−6.00% vs 50.00" and g["text"]["sigma"] == "4.00%"


def test_13b_rows_cover_every_listed_name_beyond_the_chart_limit(hb_board):
    out = BOARD.board(tab="high_beta", limit=1, hb_all=True, min_tier="any")
    assert len(out["tiles"]) == 1 and len(out["rows"]) == 5           # AAA BBB CCC DDD THIN
    assert out["tiles"][0]["symbol"] == out["rows"][0]["symbol"]
    assert out["rows"][-1]["symbol"] == "DDD"                          # green after the red
    assert not any(r["thin"] for r in out["rows"])                      # no floor = none thin
    assert out["high_beta_board"]["view"]["on"] is True


def test_13g_NEG_qqq_list_unread_serves_null_never_false(monkeypatch, _clean):
    """§3.3 `qqq` true|false|null: the Nasdaq-100 read failing must read
    'unknown' (None) on the card and the row, never 'not a member' (False)."""
    state = {"snap_calls": [], "db": _FakeDB()}
    _patch_build(monkeypatch, _frames(), qqq=RuntimeError("wikipedia down"))
    _stub_board(monkeypatch, state)
    monkeypatch.setattr(MEM, "_db", lambda db=None: state["db"])
    HB.cached_or_warm("full", now=NOW_NIGHT, sync=True)
    out = BOARD.board(tab="high_beta", limit=24, hb_all=True)
    assert out["tiles"] and out["rows"]
    assert all(t["high_beta"]["qqq"] is None for t in out["tiles"])
    assert all(t["hb_filter"]["qqq"] is None for t in out["tiles"])
    assert all(r["qqq"] is None for r in out["rows"])
    assert out["high_beta_board"]["qqq"]["available"] is False
    assert not any("QQQ" in t["badges"][0]["text"] for t in out["tiles"])


def test_13h_NEG_compact_row_and_tile_block_qqq_flag():
    r = {"symbol": "X", "beta": 2.1, "cats": ["b15"], "qqq": False, "today": {}}
    assert HB.compact_row(r, qqq_available=True)["qqq"] is False
    assert HB.compact_row(r, qqq_available=False)["qqq"] is None
    assert HB.compact_row({**r, "qqq": True}, qqq_available=False)["qqq"] is None
    assert HB.tile_block(r, qqq_available=True)["qqq"] is False
    assert HB.tile_block({**r, "qqq": True}, qqq_available=False)["qqq"] is None
    assert HB.compact_row(r, qqq_available=True)["thin"] is False
    assert HB.compact_row(r, qqq_available=True, thin=True)["thin"] is True
    assert HB.qqq_available({}) is False and HB.qqq_available({"qqq": {"available": True}})


def test_13c_ticked_boxes_and_all_mode_reach_the_tab(hb_board):
    out = BOARD.board(tab="high_beta", limit=24, hb="b20,d5", hb_mode="all")
    assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB"]
    f = out["high_beta_board"]["filters"]
    assert f["active"] == ["b20", "d5"] and f["mode"] == "all" and f["line"]
    assert [b["text"] for b in out["tiles"][0]["badges"] if b.get("hb_filter")] == [
        HB.FILTER_LABELS["b20"], HB.FILTER_LABELS["d5"]]


def test_13d_membership_hook_still_writes_for_the_default_request(hb_board):
    BOARD.board(tab="high_beta", limit=BOARD.LIMIT_MAX)
    doc = hb_board["db"].coll.docs.get("high_beta")
    assert doc and doc["symbols"] == ["AAA", "BBB", "CCC"]
    assert doc["ttl_name"] == "chart_maps.high_beta_tab.CLOSED_TTL_SEC"
    BOARD.board(tab="high_beta", limit=BOARD.LIMIT_MAX, hb="b20")
    BOARD.board(tab="high_beta", limit=BOARD.LIMIT_MAX, hb_all=True)
    assert hb_board["db"].coll.writes == 1                              # filtered views write nothing
    req = {n: p.default for n, p in __import__("inspect").signature(BOARD.board).parameters.items()}
    req.update(limit=BOARD.LIMIT_MAX, tab="zones")
    assert MEM.is_default_request(**req) is True                        # every tab still writes (T1)
    assert MEM.MEMO_BLOCK_KEY["high_beta"] == "high_beta_board"
    live = MEM.ttl_for_tab("high_beta", {"high_beta_board": {"mode": HB.MODE_LIVE}})
    assert live == (HB.LIVE_TTL_SEC, "chart_maps.high_beta_tab.LIVE_TTL_SEC")
    assert MEM.ttl_for_tab("high_beta", {}) == (None, None)


def test_13e_warming_and_error_envelopes(monkeypatch, _clean):
    monkeypatch.setattr(BOARD, "datetime", _Fixed)
    out = BOARD.high_beta_tiles()
    assert out["warming"] is True and out["tiles"] == [] and out["rows"] == []
    assert out["high_beta_board"]["state"] == "warming"
    assert out["high_beta_board"]["header"] == HB.WARMING_NOTE
    assert set(out["high_beta_board"]) == _BOARD_KEYS
    assert out["high_beta_board"]["table"] is None                       # no table while warming
    HB._failures[(HB.MODE_CLOSED, FRI.isoformat(), "full")] = (9e12, "boom")
    out = BOARD.high_beta_tiles()
    assert out["high_beta_board"]["state"] == "error" and "boom" in out["high_beta_board"]["header"]


def test_13f_api_threads_the_three_params_and_serves_the_watch_route():
    src = (BACKEND / "chart_maps" / "api.py").read_text(encoding="utf-8")
    for need in ('hb=(hb if isinstance(hb, str)', 'hb_mode=(hb_mode if isinstance(hb_mode, str)',
                 "hb_all=hb_all is True", '@router.get("/chart-maps/high-beta/watch")',
                 "board_mod.high_beta_watch"):
        assert need in src, need
    assert "bounce" not in src[src.index("hb: str = Query"):src.index("min_tier: str = Query")]


# --------------------------------------------------------------------------
# 14 — the watch list
# --------------------------------------------------------------------------
def test_14_NEG_watch_warming_is_empty_and_two_gets_start_one_warm(monkeypatch, _clean):
    monkeypatch.setattr(BOARD, "datetime", _Fixed)
    _patch_build(monkeypatch, _frames())
    a = BOARD.high_beta_watch()
    b = BOARD.high_beta_watch()
    assert a["warming"] is True and a["symbols"] == [] and b["warming"] is True
    assert len(_clean) == 1                                       # one warm, never two


def test_14b_watch_ready_biggest_drop_first_price_floor_no_cap(monkeypatch, _clean):
    from trading.safety_floor import MIN_SHARE_PRICE
    fr = _frames()
    fr["PENNY"] = _frame(2.6, move=-20.0, base=1.0)
    _patch_build(monkeypatch, fr, universe=UNIVERSE + ["PENNY"])
    monkeypatch.setattr(BOARD, "datetime", _Fixed)
    HB.cached_or_warm("full", now=NOW_NIGHT, sync=True)
    w = BOARD.high_beta_watch()
    assert w["state"] == "ready" and w["warming"] is False and w["price_floor"] == MIN_SHARE_PRICE
    syms = [s["symbol"] for s in w["symbols"]]
    assert syms == ["AAA", "BBB", "CCC", "DDD"] and "PENNY" not in syms
    assert w["n_under_floor"] == 1 and w["n_listed"] == 5
    assert set(w["symbols"][0]) == {"symbol", "beta", "cats", "move_pct", "state"}


# --------------------------------------------------------------------------
# 15 — source guards
# --------------------------------------------------------------------------
def test_15_NEG_trading_and_push_never_import_the_tab():
    for sub in ("trading", "push"):
        for p in (BACKEND / sub).rglob("*.py"):
            assert "high_beta_tab" not in p.read_text(errors="ignore"), p


def test_15b_NEG_the_tab_never_imports_board_at_module_level_and_writes_nothing():
    src = (BACKEND / "chart_maps" / "high_beta_tab.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [getattr(node, "module", "") or ""] + [a.name for a in node.names]
            assert not any("board" in n for n in names), names
    import re
    assert not re.search(r"insert_|update_one|update_many|replace_one|delete_|bulk_write|"
                         r"create_index|\.drop\(|open\(", src)
    for need in ("D10.base_read", "D10.day_from_snapshot", "D10.day_from_bar",
                 "D10.suspect_reason", "RES.official_prev_close", "RES.sigma_pct",
                 "BETA.beta_from_frame", "zone_store.drop_today", "DMT.passes",
                 "prices.bulk_cached_frames", "_bulk_snaps_fanout"):
        assert need in src, need
    assert "betas_for" not in src and "load_prices" not in src


def test_15c_his_numbers_are_named_and_tagged():
    src = (BACKEND / "chart_maps" / "high_beta_tab.py").read_text(encoding="utf-8")
    for name in ("B15_MIN = 1.5", "B20_MIN = 2.0", "TOP_PCT = 20.0", "DOWN_CHIP_PCT = 5.0"):
        line = next(l for l in src.splitlines() if l.startswith(name))
        assert "# Ajay 2026-10-14" in line, line
    assert HB.SIGMA_BARS == 50 and HB.BETA_LOOKBACK == BETA.BETA_LOOKBACK
    assert HB.FILTER_LABELS["d5"] == "\U0001F4C9 Down 5%+ today"
    assert HB.TAB_LABEL == "\U0001F3A2 High Beta"
