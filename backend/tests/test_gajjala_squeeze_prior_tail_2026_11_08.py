"""🎾 the prior session's tail on the squeeze card (2026-11-08, spec gg-squeeze §3.2, WP be-prior-tail).

Ajay 2026-11-08: "I need something like this but that big of circle for reversal squeen mainly on the cart itself also
increase the width of the reversal sqeeze chart to show more bars" — GG's TPST chart runs from the prior day's 15:00.

Pins: the three RS_TILE_* caps are BUILT from two typed-and-pinned times (never a retyped 15 / 20 / 60 / 192 / 252);
`bars.tile_prior_payload` serves the prior session's bars whose bucket START is ≥ RS_TILE_PRIOR_FROM_ET (never one of
today's); the GG5 pass stores `bars5_prior / curves5_prior / vol_avg5_prior` on every read doc while every other tile key
stays byte-identical; GG1 (run_1m.py) stores nothing new; no detector / alert / ledger module reads a `_prior` key.
The wall time of one call is MEASURED and printed (`-s`) — no threshold is asserted (a threshold would be a new number).
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import time as _clock
from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from tests import test_gajjala_constants as TC
from tests import test_gajjala_run as TR
from tests.test_gajjala_store import fake_store

PKG = pathlib.Path(GC.__file__).parent
SRC = pathlib.Path(GC.__file__).read_text()
LINES = SRC.splitlines()
MINE_TAGS = ("TRANSPORT — MINE", "derived — MINE", "Cheetah default (MINE")     # = test_gajjala_constants.MINE_TAGS
ASK = ("I need something like this but that big of circle for reversal squeen mainly on the cart itself also increase "
       "the width of the reversal sqeeze chart to show more bars")
RS_NAMES = ("RS_TILE_PRIOR_FROM_ET", "RS_TILE_PRIOR_TO_ET", "RS_TILE_PRIOR_BARS_MAX", "RS_TILE_TODAY_BARS_MAX",
            "RS_TILE_BARS_MAX")
PRIOR_KEYS = {"bars5_prior", "curves5_prior", "vol_avg5_prior"}
GG5_KEYS = {"bars5", "curves5", "vol_avg5", "bars15", "curves15", "vol_avg15"}
EMPTY = {"bars": [], "curves": [], "vol_avg": None}


@pytest.fixture(autouse=True)
def _as_test_gajjala_run(monkeypatch):
    """test_gajjala_run's own autouse guards: no holiday override, never the real detached 1-minute spawn."""
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def _assigns(src: str) -> dict:
    """{NAME: (value_node, lineno)} for every top-level `NAME = …` of `src`."""
    out = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = (node.value, node.lineno)
    return out


def _comment(lines: list, lineno: int) -> str:
    line = lines[lineno - 1]
    return line.split("#", 1)[1].strip() if "#" in line else ""


def _names(node) -> set:
    return {x.id for x in ast.walk(node) if isinstance(x, ast.Name)}


def _check_derived(src: str) -> None:
    """The three caps are built from names only — the `.hour` of both pinned times, never a retyped 15 / 20."""
    a, lines = _assigns(src), src.splitlines()
    node, ln = a["RS_TILE_PRIOR_BARS_MAX"]
    assert _names(node) == {"RS_TILE_PRIOR_TO_ET", "RS_TILE_PRIOR_FROM_ET", "LEDGER_TAPE_TF_MIN"}, _names(node)
    code = lines[ln - 1].split("#", 1)[0]
    assert not re.search(r"\b(15|20)\b", code), code
    attrs = {x.attr for x in ast.walk(node) if isinstance(x, ast.Attribute)}
    assert attrs == {"hour"}, attrs
    assert _names(a["RS_TILE_TODAY_BARS_MAX"][0]) == {"LEDGER_TAPE_BARS_MAX", "LEDGER_TAPE_SESSIONS"}
    assert _names(a["RS_TILE_BARS_MAX"][0]) == {"RS_TILE_PRIOR_BARS_MAX", "RS_TILE_TODAY_BARS_MAX"}


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_window_times_are_pinned_to_the_house_clock():
    from daytrading.data import ET_AFTERHOURS_CLOSE
    assert GC.RS_TILE_PRIOR_FROM_ET == time(15, 0)
    assert GC.RS_TILE_PRIOR_TO_ET == ET_AFTERHOURS_CLOSE == time(20, 0)
    assert GC.RS_TILE_PRIOR_FROM_ET.minute == 0 and GC.RS_TILE_PRIOR_TO_ET.minute == 0     # `.hour` alone is exact


def test_the_caps_are_derived_and_never_retyped():
    from daytrading.data import ET_AFTERHOURS_CLOSE
    d = date(2026, 11, 8)
    want = ((datetime.combine(d, ET_AFTERHOURS_CLOSE) - datetime.combine(d, GC.RS_TILE_PRIOR_FROM_ET))
            // timedelta(minutes=GC.LEDGER_TAPE_TF_MIN))
    assert GC.RS_TILE_PRIOR_BARS_MAX == want == 60
    assert GC.RS_TILE_TODAY_BARS_MAX == GC.GG1M_TILE_BARS_MAX == 192
    assert GC.RS_TILE_BARS_MAX == GC.RS_TILE_PRIOR_BARS_MAX + GC.RS_TILE_TODAY_BARS_MAX == 252
    _check_derived(SRC)


def test_NEGATIVE_the_derived_guard_bites_on_a_retyped_number():
    a = _assigns(SRC)
    for name, fake in (("RS_TILE_PRIOR_BARS_MAX", "RS_TILE_PRIOR_BARS_MAX = 60   # derived — MINE"),
                       ("RS_TILE_PRIOR_BARS_MAX",
                        "RS_TILE_PRIOR_BARS_MAX = ((20 - RS_TILE_PRIOR_FROM_ET.hour) * 60) // LEDGER_TAPE_TF_MIN   # derived — MINE"),
                       ("RS_TILE_TODAY_BARS_MAX", "RS_TILE_TODAY_BARS_MAX = 192   # derived — MINE"),
                       ("RS_TILE_BARS_MAX", "RS_TILE_BARS_MAX = 252   # derived — MINE")):
        lines = list(LINES)
        lines[a[name][1] - 1] = fake
        try:
            _check_derived("\n".join(lines))
        except AssertionError:
            continue
        raise AssertionError(f"the derived guard did not bite on {fake!r}")


def test_the_five_lines_carry_a_mine_tag_and_the_block_quotes_his_ask():
    a = _assigns(SRC)
    for n in RS_NAMES:
        c = _comment(LINES, a[n][1])
        assert c.startswith(MINE_TAGS), (n, c)
        assert not c.startswith("GG"), (n, c)
    assert "not GG" in _comment(LINES, a["RS_TILE_PRIOR_FROM_ET"][1])
    first = a["RS_TILE_PRIOR_FROM_ET"][1]
    block = []
    for ln in range(first - 1, 0, -1):                                   # the comment block right above the first line
        line = LINES[ln - 1]
        if not line.startswith("#"):
            break
        block.insert(0, line[1:].strip())
    assert ASK in " ".join(block), block
    assert TC.MINE_TAGS == MINE_TAGS                                       # one tag set (the house guard's own)


def test_NEGATIVE_the_house_constants_guards_stay_green():
    """test_gajjala_constants: the file imports only `datetime` (constants.py never imports daytrading.data) and every
    number — the five new lines included — carries a provenance tag."""
    TC.test_NEGATIVE_the_constants_import_only_the_stdlib_datetime_besides_the_ema_pair()
    TC.test_every_number_carries_a_provenance_comment()
    froms = {node.module or "" for node in ast.walk(ast.parse(SRC)) if isinstance(node, ast.ImportFrom)}
    assert not any(m.startswith("daytrading") for m in froms), froms


# ── bars.tile_prior_payload ───────────────────────────────────────────────────────────────────────────────────────
def _run_frames():
    return B.build_frames("GGA", TR.S, TR.NOW, TR.PRIOR_1M, TR.TODAY_1M)


def _flat(n: int):
    return [(10.0, 10.25, 9.75, 10.0, 1000.0 + k) for k in range(n)]


def _full_prior_day():
    """A synthetic full prior session 04:00 → 20:00 (192 five-minute buckets): regular-session tag until 16:00, after-hours
    after it — enough bars that the 21 EMA and the 50-bar volume average are warm by 15:00."""
    day = TR.minutes_from_5m(_flat(144), TR.PREV, "04:00", session="rth")
    ah = TR.minutes_from_5m(_flat(48), TR.PREV, "16:00", session="afterhours")
    return pd.concat([day, ah]).sort_index()


def test_the_run_scenario_serves_the_prior_buckets_from_15_00_only():
    fr = _run_frames()
    f = fr.frame("5m")
    p = B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    want = [f"2026-10-12 15:{m:02d}" for m in range(5, 45, 5)]                 # buckets 15:00 … 15:35 → labels 15:05 … 15:40
    assert [b["t"] for b in p["bars"]] == want
    assert all(b["t"][:10] == TR.PREV.isoformat() for b in p["bars"])
    assert "2026-10-12 15:00" not in {b["t"] for b in p["bars"]}                # the 14:55 bucket (label 15:00) is before the window
    today = {f.t[i] for i in f.today}
    assert not today & {b["t"] for b in p["bars"]}
    assert p["bars"][-1]["t"] < f.t[f.today.start]
    # the house rule (tile_payload's): an all-None curve / average is OMITTED. The fixture's prior day is 20 bars, so the
    # 21 EMA is still warm-up (masked) on all 8 and the 50-bar volume average has no value yet → only the 9 EMA is served
    assert [c["tone"] for c in p["curves"]] == ["ema9"]
    assert len(p["curves"][0]["values"]) == len(p["bars"]) == 8
    assert p["curves"][0]["values"] == [f.ema9[i] for i in range(f.today.start - 8, f.today.start)]
    assert all(f.ema21[i] is None for i in range(f.today.start))
    assert p["vol_avg"] is None
    assert set(p) == {"bars", "curves", "vol_avg"}


def test_a_full_prior_session_serves_exactly_the_cap_with_both_curves_the_average_and_the_ah_flags():
    fr = B.build_frames("GGA", TR.S, TR.NOW, _full_prior_day(), TR.TODAY_1M)
    f = fr.frame("5m")
    p = B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    assert len(p["bars"]) == GC.RS_TILE_PRIOR_BARS_MAX == 60
    assert p["bars"][0]["t"] == "2026-10-12 15:05" and p["bars"][-1]["t"] == "2026-10-12 20:00"
    assert [c["tone"] for c in p["curves"]] == ["ema9", "ema21"]
    assert all(len(c["values"]) == 60 and None not in c["values"] for c in p["curves"])
    first = f.today.start - 60
    assert p["curves"][1]["values"] == f.ema21[first:f.today.start]                # aligned by index
    assert p["vol_avg"]["period"] == 50 and len(p["vol_avg"]["values"]) == 60
    assert None not in p["vol_avg"]["values"]
    flags = [b.get("s") for b in p["bars"]]
    assert flags == [None] * 12 + ["ah"] * 48                                      # 15:00…15:55 regular, 16:00…19:55 after hours
    assert len(p["bars"]) + len(B.tile_payload(fr, "5m")["bars"]) <= GC.RS_TILE_BARS_MAX


def test_the_15_minute_frame_works_too():
    p = B.tile_prior_payload(_run_frames(), "15m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    assert [b["t"] for b in p["bars"]] == ["2026-10-12 15:15", "2026-10-12 15:30", "2026-10-12 15:45"]


def test_NEGATIVE_a_prior_session_that_ends_before_the_window_serves_nothing():
    assert B.tile_prior_payload(_run_frames(), "5m", from_et=time(16, 0)) == EMPTY        # the fixture has no AH bars
    early = TR.minutes_from_5m(_flat(12), TR.PREV, "09:30")                              # 09:30 … 10:30, nothing at 15:00
    fr = B.build_frames("GGA", TR.S, TR.NOW, early, TR.TODAY_1M)
    assert B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET) == EMPTY


def test_NEGATIVE_no_prior_day_serves_nothing():
    fr = B.build_frames("GGA", TR.S, TR.NOW, None, TR.TODAY_1M)
    assert fr.frame("5m").today.start == 0
    assert B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET) == EMPTY


def test_NEGATIVE_an_early_window_never_reaches_into_today():
    fr = _run_frames()
    f = fr.frame("5m")
    p = B.tile_prior_payload(fr, "5m", from_et=time(0, 0))
    assert [b["t"] for b in p["bars"]] == f.t[:f.today.start]                         # the whole prior session, no more
    assert all(b["t"][:10] == TR.PREV.isoformat() for b in p["bars"])


def test_the_measured_wall_time_of_one_call():
    """MEASURED, printed with -s — no threshold asserted (a threshold would be a new number)."""
    fr = _run_frames()
    B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)                    # warm the imports
    n = 20
    t0 = _clock.perf_counter()
    for _ in range(n):
        B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    one = (_clock.perf_counter() - t0) / n * 1000
    full = B.build_frames("GGA", TR.S, TR.NOW, _full_prior_day(), TR.TODAY_1M)
    t0 = _clock.perf_counter()
    for _ in range(n):
        B.tile_prior_payload(full, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    one_full = (_clock.perf_counter() - t0) / n * 1000
    print(f"\ntile_prior_payload: {one:.2f} ms (test_gajjala_run frames, mean of {n})")
    print(f"tile_prior_payload: {one_full:.2f} ms (full 04:00→20:00 prior session, mean of {n})")
    assert one > 0 and one_full > 0


# ── run.py: the GG5 pass stores the tail on every read doc ────────────────────────────────────────────────────────
def _pass_tile():
    st = fake_store()
    deps, *_ = TR.make_deps()
    out = RUN.run_pass(TR.NOW, store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok", out
    return st.get_read(TR.S, "GGA")["tile"]


def test_the_pass_stores_the_prior_keys_and_every_other_key_is_byte_identical(monkeypatch):
    tile = _pass_tile()
    assert set(tile) == GG5_KEYS | PRIOR_KEYS
    assert "bars15_prior" not in tile and "curves15_prior" not in tile
    assert [b["t"] for b in tile["bars5_prior"]] == [f"2026-10-12 15:{m:02d}" for m in range(5, 45, 5)]
    assert tile["bars5_prior"][-1]["t"] < tile["bars5"][0]["t"]
    assert [c["tone"] for c in tile["curves5_prior"]] == ["ema9"] and tile["vol_avg5_prior"] is None
    monkeypatch.setattr(B, "tile_prior_payload", lambda *a, **k: dict(EMPTY))
    without = _pass_tile()
    assert {k: without[k] for k in PRIOR_KEYS} == {"bars5_prior": [], "curves5_prior": [], "vol_avg5_prior": None}
    for k in GG5_KEYS:
        assert json.dumps(tile[k], sort_keys=True) == json.dumps(without[k], sort_keys=True), k


def test_NEGATIVE_the_1_minute_pass_stores_no_prior_tail():
    """run_1m.py is untouched — test_gajjala_run_1m_2026_10_27's pin on its tile keys stays the guard."""
    src = (PKG / "run_1m.py").read_text()
    assert "tile_prior_payload" not in src and "_prior\"" not in src and "RS_TILE_PRIOR" not in src


PRIOR_RX = re.compile(r"\b(?:bars|curves|vol_avg)\d*_prior\b|\btile_prior_payload\b|\bRS_TILE_PRIOR_")
PRIOR_ALLOWED = {"bars.py", "run.py", "tab.py", "squeeze_marks.py", "constants.py"}


def _readers(texts: dict) -> set:
    return {name for name, text in texts.items() if PRIOR_RX.search(text)}


def test_NEGATIVE_no_rule_module_reads_a_prior_key():
    texts = {p.name: p.read_text() for p in PKG.glob("*.py")}
    found = _readers(texts)
    assert {"bars.py", "run.py", "constants.py"} <= found
    assert found <= PRIOR_ALLOWED, found - PRIOR_ALLOWED
    texts["alerts.py"] = texts.get("alerts.py", "") + '\nx = doc["tile"]["bars5_prior"]\n'     # the guard bites
    assert "alerts.py" in _readers(texts) - PRIOR_ALLOWED
