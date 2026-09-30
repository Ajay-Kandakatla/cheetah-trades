"""🛡️ Resiliency tab — three follow-ups (2026-09-30).

1. The 🌅 pre-market volume leg is OFF (`PM_VOLUME_VERIFIED = False`): no
   served sentence — header, note, rules, box notes, box labels, card text — and
   neither the ✨ entry nor the tab blurb may promise the 1.5× pre-market volume
   bar while it is off; the 🌅 box carries a one-line reason instead.
2. GDP (his "todays Inflation and GDP") fell on Core PCE (T1) days in the
   window, so T2 counted GDP 0 and the header silently dropped it. The header
   now names a T2 kind whose every print landed on a T1 day.
3. During RTH a card with no fresh print is priced off the snapshot's forming
   day bar — it reads "day bar (intraday)", and "day close" only after the close.

Positive AND negative cases. Hermetic (the conftest refuses Mongo; FRED, the
calendar, the frames and the snapshot are injected, as in test_resiliency_tab).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from chart_maps import resiliency_tab as R
from tests.test_resiliency_tab import (CAL, DAYS, ET, EV, FRAMES, LAST, NOW, PRE,  # noqa: F401
                                       SESSION, SNAPS, SPY_REF, T1_DAYS, T2_DAYS, _entry,
                                       _events, _pre, _rth)

REPO = Path(__file__).resolve().parents[2]
CLOSE = datetime(2026, 9, 30, 16, 30, tzinfo=ET)          # KL.phase == "close"
PROMISES = ("usual pre-market volume by the same minute",
            "pre-market volume by the same minute",
            "pre-market volume against its own usual volume")


def _bar():
    return f"{R.PM_RVOL_MIN:g}×"


def _counts():
    return {"scanned": 5, "rated_t1": 3, "t1_pass": 2, "eod_pass": 1, "eod_session": 0,
            "pre_pass": 0, "pre_read": 2, "pre_no_baseline": 0, "dropped_thin": 0,
            "no_turnover": 0, "shown": 4}


def _served_texts(entry) -> list:
    """Every sentence the tab serves that could describe the 🌅 read."""
    out = [R.NOTE, R.note_text(), *R.rules_block()["lines"], *R.box_notes().values(),
           R.events_line(entry)]
    for ph in ("pre", "rth", "close", None):
        out.append(R.header_text(_counts(), entry=entry, ph=ph, pm_state="ready"))
    fb = R.filters_block([{"pre": None}], ("pre",), pool=1)
    for it in fb["items"]:
        out += [it["label"], it["note"], str(it.get("off_reason") or "")]
    out.append(str(fb.get("line") or ""))
    st = R.study_block()
    out += [str((st.get(k) or {}).get("text") or "") for k in R.FILTER_KEYS]
    base = {"sessions": 12, "slot_mean": [10.0] * 33}
    kw = dict(ref_close=100.0, ref_date=LAST, now=PRE, session=SESSION, phase="pre",
              baseline=base, baseline_state="ready")
    out.append(R.pre_read(_pre(100.65, ref=100.0, av=5000), **kw)["text"])
    rows, *_ = R.rank(entry, {"QUIET": _pre(50.3, ref=50.0, av=9000)}, None, now=PRE,
                      sort="default")
    for r in rows:
        out += [s["v"] for s in R.tile_stats(r)] + [R.why_text(r)]
    return out


# --------------------------------------------------------------------------
# 1 — the 🌅 volume leg is off: nothing promises it
# --------------------------------------------------------------------------
def test_NEG_no_served_sentence_promises_the_pre_volume_bar_while_off():
    assert R.PM_VOLUME_VERIFIED is False
    texts = _served_texts(_entry())
    for t in texts:
        assert _bar() not in t, t
        for p in PROMISES:
            assert p not in t, t
    # ... and every surface he reads says plainly that it is off
    assert R.PRE_OFF_REASON in R.box_notes()["pre"]
    assert R.PRE_OFF_REASON in R.rules_block()["lines"][-1]
    assert R.PRE_OFF_REASON in R.note_text()
    rth = R.header_text(_counts(), entry=_entry(), ph="rth", pm_state=None)
    assert R.PRE_OFF_REASON in rth and "runs 04:00–09:30 ET only" not in rth
    pre = R.filters_block([{"pre": None}], (), pool=1)["items"][-1]
    assert pre["key"] == "pre" and pre["off"] is True and pre["off_reason"] == R.PRE_OFF_REASON
    # one short line beside the box — no clutter
    assert len(R.PRE_OFF_REASON) <= 70 and "\n" not in R.PRE_OFF_REASON


def test_the_pre_volume_bar_is_named_only_once_the_leg_is_verified(monkeypatch):
    monkeypatch.setattr(R, "PM_VOLUME_VERIFIED", True)
    assert _bar() in R.rules_block()["lines"][-1]
    assert _bar() in R.box_notes()["pre"] and "same minute" in R.box_notes()["pre"]
    assert _bar() in R.note_text()
    items = R.filters_block([{"pre": True}], (), pool=1)["items"]
    assert all("off" not in it and "off_reason" not in it for it in items)
    rth = R.header_text(_counts(), entry=_entry(), ph="rth", pm_state=None)
    assert "runs 04:00–09:30 ET only" in rth and R.PRE_OFF_REASON not in rth
    # NEGATIVE: the off wording never rides along once it is on
    assert R.PRE_OFF_REASON not in R.box_notes()["pre"] + R.note_text()
    assert R.PRE_OFF_REASON not in " ".join(R.rules_block()["lines"])


def test_NEG_only_the_pre_box_is_greyed():
    items = R.filters_block([{"t1": True, "t2": False, "eod": True, "pre": None}], (), pool=1)["items"]
    assert [it["key"] for it in items if it.get("off")] == ["pre"]


def _nf_entry() -> str:
    nf = (REPO / "frontend/src/lib/newFeatures.ts").read_text(encoding="utf-8")
    at = nf.index("id: 'chart-maps-resiliency-2026-09-30'")
    return nf[at:nf.index("' },", at)]


def _blurb() -> str:
    src = (REPO / "frontend/src/lib/chartMaps.ts").read_text(encoding="utf-8")
    m = re.search(r"\n  resiliency: \{\n    label: '[^']*',\n    blurb: '((?:[^'\\]|\\.)*)',", src)
    assert m, "TAB_META.resiliency blurb missing"
    return m.group(1)


@pytest.mark.parametrize("surface", ["newFeatures", "blurb"])
def test_NEG_fe_copy_does_not_promise_the_pre_volume_bar_while_off(surface):
    """Tied to the live flag: flip PM_VOLUME_VERIFIED to True and this pin
    stops asserting — the copy may then promise the bar again."""
    txt = _nf_entry() if surface == "newFeatures" else _blurb()
    if R.PM_VOLUME_VERIFIED:
        pytest.skip("the pre-market volume leg is verified — the promise is allowed")
    assert _bar() not in txt
    for p in PROMISES:
        assert p not in txt
    assert "volume check is OFF" in txt


# --------------------------------------------------------------------------
# 2 — a T2 kind whose every print sat on a T1 day is named, not dropped
# --------------------------------------------------------------------------
PCE_DAY, GDP_ALONE = DAYS[-20], DAYS[-25]


def _gdp_events(gdp_days, pce_days=(PCE_DAY,)):
    ev = _events()
    ev["events"] = list(ev["events"])
    ev["events"] += [{"date": d, "kind": "pce", "tier": 1, "label": "Core PCE", "source": "x",
                      "release_id": 54} for d in pce_days]
    ev["events"] += [{"date": d, "kind": "gdp", "tier": 2, "label": "GDP", "source": "x",
                      "release_id": 53} for d in gdp_days]
    return ev


def _header(e):
    return R.header_text(_counts(), entry=e, ph="rth", pm_state=None)


GONE = "GDP 0 — every GDP print in the window landed on a T1 Core PCE day and is counted there"


def test_gdp_on_a_pce_day_is_named_in_the_header():
    e = _entry(events=_gdp_events([PCE_DAY]))
    ev = e["events_summary"]
    assert ev["t2_by_kind"]["gdp"] == 0 and ev["t1_by_kind"]["pce"] == 1
    assert ev["t2_on_t1_by_kind"]["gdp"] == {"n": 1, "t1_labels": ["Core PCE"]}
    h = _header(e)
    assert GONE in h
    # the base fixture's claims print on a CPI day is absorbed too, but claims
    # still count 3 in T2 — so it is never explained away
    assert ev["t2_on_t1_by_kind"]["claims"] == {"n": 1, "t1_labels": ["CPI"]}
    assert "every Jobless claims print" not in h and "Jobless claims 0" not in h
    # the T2 list still prints the kinds that did count
    assert "Jobless claims 3; " + GONE in h


def test_NEG_a_standalone_gdp_day_counts_in_t2_and_is_not_explained_away():
    e = _entry(events=_gdp_events([GDP_ALONE]))
    ev = e["events_summary"]
    assert ev["t2_by_kind"]["gdp"] == 1 and "gdp" not in ev["t2_on_t1_by_kind"]
    h = _header(e)
    assert "GDP 1" in h and "every GDP print" not in h


def test_NEG_gdp_split_between_a_pce_day_and_its_own_day_says_gdp_1_not_every():
    e = _entry(events=_gdp_events([PCE_DAY, GDP_ALONE]))
    ev = e["events_summary"]
    assert ev["t2_by_kind"]["gdp"] == 1 and ev["t2_on_t1_by_kind"]["gdp"]["n"] == 1
    h = _header(e)
    assert "GDP 1" in h and "every GDP print" not in h and "GDP 0" not in h


def test_NEG_no_gdp_in_the_window_adds_no_sentence():
    h = _header(_entry())
    assert "GDP" not in h.split("T2-only days:")[1].split("SPY fell")[0]
    assert "gdp" not in _entry()["events_summary"]["t2_on_t1_by_kind"]
    assert "landed on a T1" not in h


def test_NEG_t2_on_t1_is_empty_when_t2_keeps_the_t1_days(monkeypatch):
    monkeypatch.setattr(R, "T2_EXCLUDES_T1_DAYS", False)
    rows = _gdp_events([PCE_DAY])["events"]
    assert R.t2_on_t1(rows, DAYS, start=SESSION.replace(year=2025), end=SESSION) == {}


def test_NEG_the_t2_only_kinds_text_is_unchanged_without_absorption():
    assert R._kinds_txt({"claims": 3, "gdp": 0}) == "Jobless claims 3"
    assert R._kinds_txt({"gdp": 0}, {}) == "none"
    assert R._kinds_txt({"gdp": 0}, {"gdp": {"n": 2, "t1_labels": ["Core PCE"]}}) == "none; " + GONE
    # a kind that still counted in T2 is never explained away
    assert R._kinds_txt({"gdp": 1}, {"gdp": {"n": 1, "t1_labels": ["Core PCE"]}}) == "GDP 1"


# --------------------------------------------------------------------------
# 3 — the day bar is intraday during RTH; "day close" only after the close
# --------------------------------------------------------------------------
def _stale_row(px, *, ref, at):
    return _rth(px, ref=ref, at=at, age_sec=3600, close=px)       # no fresh print


def test_rth_no_fresh_print_reads_day_bar_intraday():
    t = R.today_read(_stale_row(100.3, ref=100.0, at=NOW), ref_close=100.0, ref_date=LAST,
                     now=NOW, session=SESSION, phase="rth", event=EV)
    assert t["state"] == "read" and t["basis"] == R.DAY_BAR_BASIS and t["move_pct"] == 0.3
    txt = R._today_stat(t)
    assert txt.endswith(R.DAY_BAR_WORD) and "day close" not in txt


def test_NEG_after_the_close_it_is_the_day_close():
    t = R.today_read(_stale_row(100.3, ref=100.0, at=CLOSE), ref_close=100.0, ref_date=LAST,
                     now=CLOSE, session=SESSION, phase="close", event=EV)
    assert t["state"] == "read" and t["basis"] == "day_close"
    txt = R._today_stat(t)
    assert txt.endswith(R.DAY_CLOSE_WORD) and "intraday" not in txt


def test_NEG_a_fresh_rth_print_stays_live():
    t = R.today_read(_rth(100.42, ref=100.0), ref_close=100.0, ref_date=LAST, now=NOW,
                     session=SESSION, phase="rth", event=EV)
    assert t["basis"] == "live" and "intraday" not in R._today_stat(t)


def test_spy_today_line_labels_both_clocks():
    base = {"event_day": True, "session": "2026-09-30", "t1": ["Core PCE"], "t2": [], "tier": 1,
            "spy_move_pct": 0.2, "spy_tape": None, "spy_as_of_et": None, "read": 1, "holding": 1}
    assert f"({R.DAY_BAR_WORD})" in R.today_line({**base, "spy_basis": R.DAY_BAR_BASIS})
    closed = R.today_line({**base, "spy_basis": "day_close"})
    assert "(day close)" in closed and "intraday" not in closed
    live = R.today_line({**base, "spy_tape": "rth", "spy_as_of_et": "10:59", "spy_basis": "live"})
    assert "(live 10:59 ET)" in live


def test_rank_serves_spy_basis_on_both_clocks():
    e = _entry()
    rth_snaps = {**SNAPS, "SPY": _stale_row(440.43, ref=SPY_REF, at=NOW),
                 "QUIET": _stale_row(50.1, ref=50.0, at=NOW)}
    rows, _c, _f, today, _su = R.rank(e, rth_snaps, None, now=NOW, sort="default")
    assert today["spy_basis"] == R.DAY_BAR_BASIS and R.DAY_BAR_WORD in R.today_line(today)
    q = next(r for r in rows if r["symbol"] == "QUIET")
    assert R.DAY_BAR_WORD in next(s["v"] for s in R.tile_stats(q, event_day=True) if s["k"] == "Today")
    close_snaps = {**SNAPS, "SPY": _stale_row(440.43, ref=SPY_REF, at=CLOSE),
                   "QUIET": _stale_row(50.1, ref=50.0, at=CLOSE)}
    rows2, _c, _f, today2, _su = R.rank(e, close_snaps, None, now=CLOSE, sort="default")
    assert today2["spy_basis"] == "day_close" and "intraday" not in R.today_line(today2)
    q2 = next(r for r in rows2 if r["symbol"] == "QUIET")
    v2 = next(s["v"] for s in R.tile_stats(q2, event_day=True) if s["k"] == "Today")
    assert v2.endswith(R.DAY_CLOSE_WORD)
