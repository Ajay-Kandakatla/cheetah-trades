"""⏸ The "no breakout" line on Gajjala's cards, 🧠 potentials and today's 📈 Track rows (2026-11-12).

Ajay 2026-11-12 ~14:45 ET, verbatim: "Most of our potentials are not having breakout, please write that on them that..
I need for an additonal break out from the triggers Usually after that run up to tirgger point they are mostly just
sitting there"

chart_maps/gajjala/breakout_state.py — display only, computed at serve time, attached by ONE post-walk call in
tab.build. NEGATIVES are mandatory: the stop printed before a breakout, far above the trigger, a fresh break, a stale
breakout, off the chart, eligibility, engine isolation, the 0/1 literal guard, the wording guard and the WRITES golden
unchanged. Spec: scratchpad nobreak/spec.md §3.1 / §3.2 / §4 (be-breakout-state).
"""
from __future__ import annotations

import ast
import copy
import json
import math
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from chart_maps.gajjala import breakout_state as BS
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX

GG_DIR = Path(__file__).resolve().parents[1] / "chart_maps" / "gajjala"
DAY = "2026-10-13"
T0 = datetime(2026, 10, 13, 10, 30)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def stamp(i, step=5, t0=T0):
    return (t0 + timedelta(minutes=step * i)).strftime("%Y-%m-%d %H:%M")


def bars(rows, *, step=5, t0=T0):
    """rows = [(h, l, c, v)] oldest first, one bar every `step` minutes from t0 (o = the low)."""
    return [{"t": stamp(i, step, t0), "o": l, "h": h, "l": l, "c": c, "v": v} for i, (h, l, c, v) in enumerate(rows)]


def k3(value):
    return {"key": D.K3_VOL_KEY, "label": "K3 volume dried up in the base", "ok": True, "value": value, "need": ""}


def read(setup="bull_flag", state="triggered", *, broke=True, trigger=1.00, stop=0.90, entry_t=None, as_of=None,
         peak="busiest bar 200,000", frame="5m", **kw):
    r = {"setup": setup, "state": state, "broke": broke, "trigger": trigger, "stop": stop, "frame": frame,
         "entry_bar_t": entry_t, "as_of_bar_t": as_of, "criteria": [k3(peak)] if peak is not None else [],
         "ready": False, "variant": None, "grade": None, "base": None}
    r.update(kw)
    return r


def doc_of(b5=None, b15=None, sym="AAA", b1=None):
    tile = {}
    if b5 is not None:
        tile["bars5"] = b5
    if b15 is not None:
        tile["bars15"] = b15
    if b1 is not None:
        tile["bars1"] = b1
    return {"symbol": sym, "tile": tile, "setups": {}}


def rb(bs, **kw):
    kw.setdefault("trigger", 1.00)
    kw.setdefault("entry_t", bs[0]["t"])
    return BS.read_breakout(bs, **kw)


def served(r, trigger=1.00, stop=0.90):
    return BS.words(r, trigger=trigger, stop=stop)


def all_strings():
    out = list(BS.HEAD.values()) + list(BS.PART.values()) + list(BS.VOL_WORD.values()) + [BS.hint()]
    assert all(isinstance(s, str) and s for s in out)
    return out


# ── 1. waiting ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_1_waiting_no_breakout_since_the_trigger_exact_words():
    bs = bars([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000), (1.09, 1.05, 1.07, 80_000)])
    r = rb(bs, stop=0.90, base_peak=631_500.0)
    assert r["state"] == "waiting" and r["level"] == 1.10 and r["minutes"] == 10 and r["at_t"] is None
    w = served(r)
    assert w["head"] == "⏸ no breakout since the trigger"
    assert w["detail"] == (" · last close 1.07 (+7.0% vs the trigger 1.00) · needs a close above 1.10 (the high since "
                           "the trigger) on volume louder than 631.5K (the base's busiest bar) · 10 min since the "
                           "trigger bar (10:30)")
    assert w["text"] == w["head"] + w["detail"]


# ── 2. NEGATIVE C3: far above the trigger is never "at the trigger" ──────────────────────────────────────────────
def test_2_NEGATIVE_C3_far_above_the_trigger_prints_the_distance():
    bs = bars([(1.50, 1.20, 1.50, 900_000), (1.48, 1.40, 1.45, 300_000), (1.49, 1.42, 1.46, 200_000)])
    r = rb(bs, trigger=1.08, stop=0.95, base_peak=631_500.0)
    assert r["state"] == "waiting"
    w = served(r, trigger=1.08, stop=0.95)
    assert w["text"] == ("⏸ no breakout since the trigger · last close 1.46 (+35.2% vs the trigger 1.08) · needs a "
                         "close above 1.50 (the high since the trigger) on volume louder than 631.5K (the base's "
                         "busiest bar) · 10 min since the trigger bar (10:30)")
    assert "+35.2% vs the trigger 1.08" in w["text"]
    assert not [s for s in all_strings() + [w["text"]] if "at the trigger" in s]


# ── 3. NEGATIVE C3: a fresh break (trigger bar = the latest bar) gets no line ───────────────────────────────────
@pytest.mark.parametrize("close", [0.80, 1.00, 1.05, 9.99])
def test_3_NEGATIVE_C3_fresh_break_on_the_latest_bar_no_line(close):
    bs = bars([(0.99, 0.95, 0.97, 50_000), (max(close, 1.01), 0.96, close, 400_000)])
    assert rb(bs, entry_t=bs[-1]["t"]) is None
    for state in ("aplus", "partial"):
        r = read(state=state, entry_t=bs[-1]["t"], as_of=bs[-1]["t"])
        assert BS.block(r, doc_of(bs)) is None, state


# ── 4. the latest bar is a breakout: 🔊 / 🔇 by the printed volume ───────────────────────────────────────────────
@pytest.mark.parametrize("v,state", [(250_000, "broke_vol"), (200_000, "broke_quiet"), (200_000.4, "broke_quiet"),
                                     (200_000.6, "broke_vol")])
def test_4_latest_bar_breakout_volume_compared_as_printed(v, state):
    bs = bars([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000), (1.13, 1.06, 1.12, v)])
    r = rb(bs, base_peak=200_000.0)
    assert r["state"] == state and r["at_t"] == bs[-1]["t"] and r["level"] == 1.10
    w = served(r)
    assert w["head"] == BS.HEAD[state].format(at="10:40")
    assert w["detail"].startswith(" · closed above 1.10, the high since the trigger · volume ")
    assert w["detail"].endswith(" vs 200.0K (the base's busiest bar) · last close 1.12 (+12.0% vs the trigger 1.00) · "
                                "10 min since the trigger bar (10:30)")


# ── 5. NEGATIVE C4: a stale 🔊 never stays on the card ──────────────────────────────────────────────────────────
def _engn(extra=()):
    rows = [(2.20, 2.15, 2.18, 300_000), (2.25, 2.18, 2.24, 100_000)] + [(2.20, 2.16, 2.17, 20_000)] * 32
    return bars(rows + list(extra), t0=datetime(2026, 10, 13, 9, 35))


def test_5_NEGATIVE_C4_stale_breakout_then_flat_reads_waiting_after():
    bs = _engn()
    r = rb(bs, trigger=2.17, stop=2.00, base_peak=49_200.0)
    assert r["state"] == "waiting" and r["at_t"] == "2026-10-13 09:40" and r["prior_state"] == "broke_vol"
    w = served(r, trigger=2.17, stop=2.00)
    assert w["head"] == "⏸ no new breakout since the 09:40 bar"
    assert w["text"] == ("⏸ no new breakout since the 09:40 bar · last close 2.17 (+0.0% vs the trigger 2.17) · needs a "
                         "close above 2.25 (the high since the trigger) on volume louder than 49.2K (the base's "
                         "busiest bar) · that breakout: volume louder than the base's busiest bar · 165 min since the "
                         "trigger bar (09:35)")
    assert not w["head"].startswith("🔊")


def test_5_C4_a_second_quiet_breakout_on_the_latest_bar_reads_by_that_bar():
    bs = _engn([(2.31, 2.20, 2.30, 40_000)])
    r = rb(bs, trigger=2.17, stop=2.00, base_peak=49_200.0)
    assert r["state"] == "broke_quiet" and r["at_t"] == bs[-1]["t"] and r["level"] == 2.25
    assert served(r, trigger=2.17)["head"].startswith("🔇 broke out on the 12:25 bar")


# ── 6. back under ────────────────────────────────────────────────────────────────────────────────────────────────
def test_6_back_under_names_the_first_bar_of_the_trailing_run():
    bs = bars([(1.10, 0.99, 1.05, 300_000), (1.06, 0.97, 0.99, 90_000), (1.03, 0.98, 1.01, 90_000),
               (1.02, 0.96, 0.99, 80_000), (1.00, 0.95, 0.98, 80_000)])
    r = rb(bs, stop=0.90)
    assert r["state"] == "back_under" and r["at_t"] == bs[3]["t"]
    assert served(r)["text"] == ("↩️ back under the trigger 1.00 since the 10:45 bar · last close 0.98 (-2.0% vs the "
                                 "trigger 1.00) · 20 min since the trigger bar (10:30)")


def test_6_NEGATIVE_a_close_equal_to_the_trigger_is_not_under():
    bs = bars([(1.10, 0.99, 1.05, 300_000), (1.06, 0.97, 1.00, 90_000)])
    assert rb(bs, stop=0.90)["state"] == "waiting"


# ── 7. NEGATIVE C2: nothing after the stop is a breakout ────────────────────────────────────────────────────────
def test_7_NEGATIVE_C2_critic_case_stop_then_close_above_is_stop_printed():
    bs = bars([(1.02, 0.99, 1.01, 300_000), (1.01, 0.93, 0.97, 400_000), (1.05, 0.97, 1.04, 900_000)])
    r = rb(bs, stop=0.95, base_peak=100_000.0)
    assert r["state"] == "stop_printed" and r["at_t"] == "2026-10-13 10:35" and r["prior_t"] is None
    w = served(r, stop=0.95)
    assert w["text"] == ("✖️ traded under the stop 0.95 on the 10:35 bar · last close 1.04 (+4.0% vs the trigger 1.00) · "
                         "10 min since the trigger bar (10:30)")
    assert "🔊" not in w["text"] and "broke out" not in w["text"]


def test_7_C2_the_trigger_bar_own_low_under_the_stop():
    bs = bars([(1.02, 0.94, 1.01, 300_000), (1.06, 1.00, 1.05, 400_000)])
    r = rb(bs, stop=0.95)
    assert r["state"] == "stop_printed" and r["at_t"] == bs[0]["t"]


def test_7_NEGATIVE_C2_low_equal_to_the_stop_is_not_under_and_no_stop_is_no_read():
    bs = bars([(1.02, 0.95, 1.01, 300_000), (1.01, 0.95, 0.99, 400_000), (1.06, 0.95, 1.05, 900_000)])
    assert rb(bs, stop=0.95, base_peak=100_000.0)["state"] == "broke_vol"
    low = bars([(1.02, 0.80, 1.01, 300_000), (1.06, 0.70, 1.05, 900_000)])
    assert rb(low, stop=None, base_peak=100_000.0)["state"] == "broke_vol"


def test_7_C2_a_breakout_before_the_stop_is_named():
    bs = bars([(1.02, 0.99, 1.01, 300_000), (1.06, 1.00, 1.05, 400_000), (1.05, 0.94, 0.96, 500_000)])
    r = rb(bs, stop=0.95, base_peak=100_000.0)
    assert r["state"] == "stop_printed" and r["prior_t"] == bs[1]["t"]
    assert served(r, stop=0.95)["text"] == ("✖️ traded under the stop 0.95 on the 10:40 bar · broke out on the 10:35 "
                                            "bar before that · last close 0.96 (-4.0% vs the trigger 1.00) · 10 min "
                                            "since the trigger bar (10:30)")


def test_7_C2_parity_with_detectors_stopped_after():
    rnd = random.Random(11)
    stop, seen = 0.95, set()
    for _ in range(400):
        n = rnd.randint(2, 9)
        lows = [rnd.choice((0.93, 0.95, 0.96, 0.99)) for _ in range(n)]
        bs = bars([(1.02, lo, 1.00, 100_000) for lo in lows])
        r = rb(bs, stop=stop)
        last = n - 1
        engine = lows[0] < stop or D.stopped_after(SimpleNamespace(l=lows), 0, None, stop, None, last)
        assert (r["state"] == "stop_printed") == engine, lows
        if r["state"] == "stop_printed":
            ks = [b["t"] for b in bs].index(r["at_t"])
            assert lows[ks] < stop and all(x >= stop for x in lows[:ks])
            seen.add(ks > 0)
    assert seen == {True, False}


# ── 8. base peak not on file ─────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("value", ["no bar yet", "busiest bar ~12", "", None, "busiest bar 1.5M"])
def test_8_peak_none_unjudged_and_need_nopeak(value):
    r0 = read(peak=value) if value is not None else read(peak=None)
    assert BS.base_peak_volume(r0) is None
    up = bars([(1.10, 0.99, 1.05, 300_000), (1.13, 1.06, 1.12, 900_000)])
    r = rb(up, base_peak=BS.base_peak_volume(r0))
    assert r["state"] == "broke_unjudged"
    w = served(r)
    assert w["head"] == "⤴️ broke out on the 10:35 bar — volume not judged"
    assert " · base volume not on file · " in w["detail"]
    flat = bars([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000)])
    assert " · needs a close above 1.10 (the high since the trigger); base volume not on file · " in served(rb(flat))["text"]


def test_8_NEGATIVE_nan_volume_on_the_breakout_bar_is_unjudged():
    bs = bars([(1.10, 0.99, 1.05, 300_000), (1.13, 1.06, 1.12, float("nan"))])
    assert rb(bs, base_peak=100_000.0)["state"] == "broke_unjudged"


# ── 9. C8: off the chart ─────────────────────────────────────────────────────────────────────────────────────────
def test_9_C8_trigger_bar_older_than_the_served_bars_is_off_chart():
    n = GC.GG1M_TILE_BARS_MAX
    full = bars([(1.02, 0.99, 1.01, 10_000)] * (n + 5), step=1, t0=datetime(2026, 10, 13, 9, 30))
    served_bars = full[-n:]
    r = read(frame="1m", entry_t=full[0]["t"], as_of=served_bars[-1]["t"])
    b = BS.block(r, doc_of(b1=served_bars), V.GG1)
    assert b["state"] == "off_chart" and b["head"] == "⏸ trigger bar 09:30 is off the chart — breakout not read"
    assert b["detail"] == "" and b["text"] == b["head"]


def test_9_NEGATIVE_absent_but_newer_entry_or_no_bars_no_line():
    bs = bars([(1.02, 0.99, 1.01, 10_000)] * 4)
    assert rb(bs, entry_t="2026-10-13 10:32") is None
    assert BS.read_breakout([], trigger=1.0, entry_t="2026-10-13 10:30") is None
    assert BS.block(read(entry_t="2026-10-13 10:30"), doc_of([])) is None


# ── 10. NEGATIVE NaN / inf ───────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("key,bad", [("h", float("nan")), ("c", float("inf")), ("c", None), ("h", "x")])
def test_10_NEGATIVE_non_finite_high_or_close_from_the_trigger_on_no_line(key, bad):
    bs = bars([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000), (1.09, 1.05, 1.07, 80_000)])
    bs[1][key] = bad
    assert rb(bs) is None
    pre = bars([(1.0, 0.9, 0.95, 1)] + [(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000)],
               t0=datetime(2026, 10, 13, 10, 25))
    pre[0][key] = bad                                                # before the trigger bar: not read
    assert rb(pre, entry_t=pre[1]["t"])["state"] == "waiting"


def test_10_every_served_block_is_strict_json():
    cases = [bars([(1.10, 0.99, 1.05, 300_000), (1.13, 1.06, 1.12, float("nan"))]),
             bars([(1.10, 0.99, 1.05, 300_000), (1.08, 0.80, 1.06, float("inf"))]),
             bars([(1.10, 0.99, 1.05, 300_000), (1.06, 0.97, 0.98, 90_000)]),
             bars([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000)])]
    for bs in cases:
        b = BS.block(read(entry_t=bs[0]["t"], as_of=bs[-1]["t"]), doc_of(bs))
        assert b and set(b) == {"state", "head", "detail", "text", "hint"}
        json.dumps(b, allow_nan=False)
        assert all(isinstance(x, str) for x in b.values())


# ── 11. NEGATIVE eligibility ─────────────────────────────────────────────────────────────────────────────────────
def _two():
    return bars([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000)])


@pytest.mark.parametrize("state", BS.SKIP_STATES)
def test_11_NEGATIVE_broke_reads_in_skip_states_no_line(state):
    bs = _two()
    assert BS.block(read(state=state, entry_t=bs[0]["t"]), doc_of(bs)) is None


@pytest.mark.parametrize("broke", [1, "yes", None, False])
def test_11_NEGATIVE_truthy_non_bool_broke_is_not_broke(broke):
    bs = _two()
    assert BS.block(read(state="triggered", broke=broke, entry_t=bs[0]["t"]), doc_of(bs)) is None


@pytest.mark.parametrize("setup", ["premarket", "postmarket", "", None, "luk_setup"])
def test_11_NEGATIVE_list_tiles_off_the_setups_get_no_key(setup):
    bs = _two()
    assert BS.block(read(setup=setup, entry_t=bs[0]["t"]), doc_of(bs)) is None
    tile = {"symbol": "AAA", "gajjala": {"setup": setup}}
    out = {"tiles": [tile]}
    BS.tag(out, {"AAA": dict(doc_of(bs), setups={setup or "x": read(setup=setup, entry_t=bs[0]["t"])})})
    assert "breakout" not in tile["gajjala"]


def test_11_partial_and_audited_held_carry_the_line():
    from chart_maps.gajjala import audited_rules as AR
    bs = _two()
    for state in ("partial", AR.HELD_STATE, "triggered"):
        b = BS.block(read(state=state, entry_t=bs[0]["t"], as_of=bs[-1]["t"]), doc_of(bs))
        assert b and b["state"] == "waiting", state


# ── 12. 🧠 forming ───────────────────────────────────────────────────────────────────────────────────────────────
def _pot_doc():
    rows = [(10.5, 10.0, 10.5, 200_000), (11.0, 10.875, 10.9375, 100_000), (10.96875, 10.8125, 10.875, 80_000),
            (10.9, 10.85, 10.88, 70_000)]
    return doc_of(bars(rows, t0=datetime(2026, 10, 13, 9, 55)))


@pytest.mark.parametrize("kind", ["armed", "building"])
def test_12_potential_no_break_yet_with_last_close_and_minutes(kind):
    from tests.test_gajjala_potential import bf_armed
    r = bf_armed() if kind == "armed" else dict(bf_armed(), ready=False)
    assert PT.potential_kind(r) == kind and r["as_of_bar_t"] == "2026-10-13 10:05"
    b = BS.block(r, _pot_doc(), pot={"first_bar_t": "2026-10-13 09:55"})
    assert b["state"] == "no_break_yet"
    assert b["text"] == ("⏸ no breakout yet · last close 10.88 (-0.8% vs the trigger 10.97) · 10 min since first seen "
                         "(09:55 bar)")                              # the 10:10 bar after as_of is never read


@pytest.mark.parametrize("first", ["2026-10-12 10:00", "2026-10-13 10:10", None, "garbled", 5])
def test_12_NEGATIVE_first_seen_other_date_later_or_missing_no_minutes(first):
    from tests.test_gajjala_potential import bf_armed
    b = BS.block(bf_armed(), _pot_doc(), pot={"first_bar_t": first})
    assert b["text"] == "⏸ no breakout yet · last close 10.88 (-0.8% vs the trigger 10.97)"
    assert BS.block(bf_armed(), _pot_doc(), pot=None)["text"] == b["text"]


def test_12_NEGATIVE_forming_without_a_base_or_partial_forming_no_card_line():
    from tests.test_gajjala_potential import bf_armed, bf_no_pullback
    nb = bf_no_pullback()
    assert PT.potential_kind(nb) is None
    assert BS.block(nb, _pot_doc()) is None
    pf = dict(bf_armed(), state="partial", broke=False)
    assert BS.block(pf, _pot_doc()) is None


# ── 13. 📈 Track rows ────────────────────────────────────────────────────────────────────────────────────────────
def _row(sym, setup):
    return {"symbol": sym, "setup": setup, "text": f"{sym} row"}


def _track_out(today, yday):
    return {"tiles": [], "track": {"today": {"rows": today}, "yesterday": {"rows": yday}}}


def test_13_rows_card_block_no_break_and_negatives():
    from tests.test_gajjala_potential import bf_armed
    bs = _two()
    broke = read(entry_t=bs[0]["t"], as_of=bs[-1]["t"])
    reads_by = {
        "BRK": dict(doc_of(bs, sym="BRK"), setups={"bull_flag": broke}),
        "POT": dict(_pot_doc(), symbol="POT", setups={"bull_flag": bf_armed()}),
        "INV": dict(doc_of(bs, sym="INV"), setups={"bull_flag": read(state="invalid", broke=False, trigger=1.2)}),
        "NON": dict(doc_of(bs, sym="NON"), setups={"bull_flag": read(state="none", broke=False, trigger=None)}),
        "PRF": dict(doc_of(bs, sym="PRF"), setups={"bull_flag": dict(bf_armed(), state="partial", broke=False)}),
        "STP": dict(doc_of(bs, sym="STP"), setups={"bull_flag": read(state="stopped", entry_t=bs[0]["t"])}),
    }
    today = [_row(s, "bull_flag") for s in ("BRK", "POT", "INV", "NON", "PRF", "STP", "GONE")]
    yday = [_row(s, "bull_flag") for s in ("BRK", "POT", "INV")]
    out = _track_out(today, yday)
    BS.tag(out, reads_by, pots=[{"symbol": "POT", "setup": "bull_flag", "first_bar_t": "2026-10-13 09:55"}])
    by = {r["symbol"]: r.get("breakout") for r in out["track"]["today"]["rows"]}
    assert by["BRK"] == BS.block(broke, reads_by["BRK"])
    assert by["POT"]["state"] == "no_break_yet" and "10 min since first seen (09:55 bar)" in by["POT"]["text"]
    assert by["INV"]["state"] == "no_break" and by["INV"]["text"] == "⏸ no breakout over 1.20"
    assert by["NON"]["state"] == "no_break" and by["NON"]["text"] == "⏸ no breakout"
    assert by["PRF"]["state"] == "no_break" and by["PRF"]["text"] == "⏸ no breakout over 10.97"
    assert by["STP"] is None and "breakout" not in out["track"]["today"]["rows"][5]          # NEGATIVE stopped
    assert by["GONE"] is None and "breakout" not in out["track"]["today"]["rows"][6]         # NEGATIVE no read
    assert not [r for r in out["track"]["yesterday"]["rows"] if "breakout" in r]              # NEGATIVE yesterday


# ── 14. the READ's frame, cut at as_of ───────────────────────────────────────────────────────────────────────────
def test_14_fade_15m_read_uses_bars15_on_a_5m_card_and_ignores_bars_after_as_of():
    b15 = bars([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000), (1.09, 1.05, 1.07, 80_000),
                (1.30, 1.10, 1.25, 900_000)], step=15)
    b5 = bars([(5.0, 4.0, 4.5, 1)] * 6, t0=datetime(2026, 10, 13, 9, 0))   # no 5m stamp equals the trigger bar
    r = read(setup="horizontal_fade", frame="15m", entry_t=b15[0]["t"], as_of=b15[2]["t"])
    b = BS.block(r, doc_of(b5, b15))
    assert b["state"] == "waiting" and "30 min since the trigger bar (10:30)" in b["text"]
    assert "last close 1.07" in b["text"]                            # the 11:15 breakout bar after as_of is not read
    assert BS.block(dict(r, frame="5m"), doc_of(b5, b15)) is None   # the 5m frame has no such bar → no line


# ── 15. K3 round trip ────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("x", [0, 999, 1_234_567, 1608758.385614])
def test_15_k3_busiest_round_trip(x):
    value = D._busiest(SimpleNamespace(v=[x]), [0])
    assert BS.base_peak_volume({"criteria": [k3(value)]}) == round(x)
    assert BS.base_peak_volume({"criteria": [k3(D._busiest(SimpleNamespace(v=[]), []))]}) is None


def test_15_k3_parse_over_the_detector_fixture_reads():
    cases = [D.bull_flag(FX.bf_aplus()), D.kiss_fly(FX.kf_frame()), D.intraday_vcp(FX.vcp_frame()),
             D.horizontal_fade(FX.hf_frame(), None), D.reversal_squeeze(FX.rs_frame())]
    frames = [FX.bf_aplus(), FX.kf_frame(), FX.vcp_frame(), FX.hf_frame(), FX.rs_frame()]
    n = 0
    for r, F in zip(cases, frames):
        rows = [c for c in r["criteria"] if c["key"] == D.K3_VOL_KEY]
        if not rows:
            assert BS.base_peak_volume(r) is None
            continue
        n += 1
        base = r.get("base") or {}
        span = [F.v[i] for i, t in enumerate(F.t) if base.get("from_t") and base["from_t"] <= t <= base["to_t"]]
        got = BS.base_peak_volume(r)
        if rows[0]["value"] == "no bar yet":
            assert got is None
        else:
            assert got in {round(x) for x in span} and got <= round(max(span))
    assert n >= 4


# ── 16–18. build integration (the real pass on the fixture store) ───────────────────────────────────────────────
def _pass_store():
    from tests.test_gajjala_run import RUN, T1, at, fake_store, make_deps, snap_row
    st = fake_store()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    RUN.run_pass(T1, store=st, deps=deps)
    return st, T1


def _aplus_store():
    from tests.test_gajjala_run import NOW, RUN, make_deps
    st, _t1 = _pass_store()
    RUN.run_pass(NOW, store=st, deps=make_deps()[0])
    return st, NOW


def _triggered_store():
    """The A+ read doc edited to a later pass: a pause bar, then a close above the high since the trigger bar on volume
    above the parsed K3 peak; state → triggered, as_of → the last appended bar."""
    from tests.test_gajjala_run import S
    st, now = _aplus_store()
    coll = st.coll(ST.READS)
    key = next(k for k, d in coll.docs.items() if d.get("symbol") == "GGA" and d.get("date") == S.isoformat())
    d = coll.docs[key]
    bf = d["setups"]["bull_flag"]
    peak = BS.base_peak_volume(bf)
    hi = max(b["h"] for b in d["tile"]["bars5"] if b["t"] >= bf["entry_bar_t"])
    d["tile"]["bars5"] += [{"t": "2026-10-13 10:45", "o": 11.2, "h": 11.22, "l": 11.1, "c": 11.15, "v": 90_000.0},
                           {"t": "2026-10-13 10:50", "o": 11.15, "h": hi + 0.3, "l": 11.1, "c": hi + 0.2,
                            "v": peak * 2}]
    bf.update(state="triggered", as_of_bar_t="2026-10-13 10:50", bars_since_entry=2)
    return st, now + timedelta(minutes=10)


def _tile(out, sym, setup=None):
    return next(t for t in out["tiles"] if t["symbol"] == sym and (setup is None or t["gajjala"]["setup"] == setup))


def test_16_build_potential_tile_and_today_row_carry_no_break_yet():
    st, now = _pass_store()
    out = GT.build(GC.POTENTIAL_SUB, now=now, store=st)
    t = _tile(out, "GGA")
    assert t["gajjala"]["breakout"]["state"] == "no_break_yet"
    rows = [r for r in out["track"]["today"]["rows"] if r["symbol"] == "GGA" and r["setup"] == "bull_flag"]
    assert rows and rows[0]["breakout"]["state"] == "no_break_yet"
    json.dumps(out, allow_nan=False)


def test_16_NEGATIVE_fresh_aplus_card_has_no_key_then_the_later_breakout_is_loud():
    st, now = _aplus_store()
    out = GT.build("bull_flag", now=now, store=st)
    t = _tile(out, "GGA", "bull_flag")
    assert t["gajjala"]["state"] == "aplus" and "breakout" not in t["gajjala"]
    st2, now2 = _triggered_store()
    t2 = _tile(GT.build("bull_flag", now=now2, store=st2), "GGA", "bull_flag")
    assert t2["gajjala"]["breakout"]["state"] == "broke_vol"
    assert t2["gajjala"]["breakout"]["head"].startswith("🔊 broke out on the 10:50 bar")


@pytest.mark.parametrize("variant", [None, V.GG1, V.GGA])
def test_16_tag_called_once_per_build_with_builds_reads_and_pots(variant, monkeypatch):
    st, now = _pass_store()
    calls = []
    real = BS.tag

    def spy(out, reads_by, v=None, *, pots=None):
        calls.append((reads_by, v, pots))
        return real(out, reads_by, v, pots=pots)
    monkeypatch.setattr(BS, "tag", spy)
    GT.build(GC.POTENTIAL_SUB, now=now, store=st, variant=variant)
    assert len(calls) == 1
    reads_by, v, pots = calls[0]
    assert set(reads_by) == {"GGA"} and v is V.of(variant if variant is not None else st)
    assert pots and {(d["symbol"], d["setup"]) for d in pots} >= {("GGA", "bull_flag")}


def test_17_NEGATIVE_a_raising_engine_serves_the_board_with_no_key(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("engine down")
    st, now = _pass_store()
    monkeypatch.setattr(BS, "read_forming", boom)
    out = GT.build(GC.POTENTIAL_SUB, now=now, store=st)
    assert out["tiles"] and not [t for t in out["tiles"] if "breakout" in t["gajjala"]]
    assert out["track"]["today"]["rows"] and not [r for r in out["track"]["today"]["rows"] if "breakout" in r]
    st2, now2 = _triggered_store()
    monkeypatch.setattr(BS, "read_breakout", boom)
    out2 = GT.build("bull_flag", now=now2, store=st2)
    assert out2["tiles"] and not [t for t in out2["tiles"] if "breakout" in t["gajjala"]]


def test_18_NEGATIVE_order_never_moves(monkeypatch):
    st, now = _pass_store()
    subs = [k for k, _e, _l in GC.SUBS if k != GC.LEDGER_SUB]

    def shape(o):
        tr = o.get("track") if isinstance(o.get("track"), dict) else {}
        rows = ((tr.get("today") or {}).get("rows") or []) + ((tr.get("yesterday") or {}).get("rows") or [])
        return ([(t.get("symbol"), (t.get("gajjala") or {}).get("setup")) for t in o.get("tiles") or []],
                [(r.get("symbol"), r.get("setup")) for r in rows])
    on = {k: shape(GT.build(k, now=now, store=st)) for k in subs}
    monkeypatch.setattr(BS, "tag", lambda *a, **k: None)
    off = {k: shape(GT.build(k, now=now, store=st)) for k in subs}
    assert on == off
    assert on[GC.POTENTIAL_SUB][1]


# ── 19–21. source guards ─────────────────────────────────────────────────────────────────────────────────────────
def test_19_NEGATIVE_engine_isolation():
    users = sorted(p.name for p in GG_DIR.glob("*.py")
                   if p.name != "breakout_state.py" and "breakout_state" in p.read_text(encoding="utf-8"))
    assert users == ["tab.py"]
    src = (GG_DIR / "tab.py").read_text(encoding="utf-8")
    assert len(re.findall(r"import breakout_state\b", src)) == 1
    for name in ("run.py", "run_1m.py", "alerts.py", "potential.py", "break_watch.py", "ledger.py", "detectors.py",
                 "stages.py"):
        assert "breakout_state" not in (GG_DIR / name).read_text(encoding="utf-8"), name
    for p in list(GG_DIR.glob("audited_*.py")) + list(GG_DIR.glob("live_*.py")):
        assert "breakout_state" not in p.read_text(encoding="utf-8"), p.name


def test_20_NEGATIVE_no_numeric_literal_but_0_and_1():
    tree = ast.parse((GG_DIR / "breakout_state.py").read_text(encoding="utf-8"))
    bad = [(n.lineno, n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant)
           and isinstance(n.value, (int, float, complex)) and not isinstance(n.value, bool) and n.value not in (0, 1)]
    assert bad == []


def test_21_NEGATIVE_wording_guard():
    bad = re.compile(r"\b(exit|sell|get out|b" + r"ounce)\b", re.I)
    assert not [s for s in all_strings() if bad.search(s)]
    assert "UNMEASURED" in BS.hint() and PT.CHEETAH_TAG.rstrip(")") in BS.hint()
    assert "“The volume will dry up during the entries of all my setups and it picks up if the setup works.”" in BS.hint()


def test_21_hint_without_the_quote_drops_only_the_gg_clause(monkeypatch):
    from chart_maps.gajjala import playbook as PB
    monkeypatch.setattr(PB, "_rules_doc", lambda: None)
    h = BS.hint()
    assert "GG:" not in h and h.endswith("(Cheetah default, not his.) UNMEASURED.")


# ── 22. NEGATIVE the WRITES golden is untouched ─────────────────────────────────────────────────────────────────
def test_22_NEGATIVE_gg5_writes_golden_unchanged(monkeypatch):
    monkeypatch.delenv("GG_WRITE_GOLDEN", raising=False)
    from tests import test_gajjala_variant_gg5_identity as ID
    ID.test_gg5_writes_are_byte_identical(monkeypatch)


def test_states_tuple_and_card_states():
    assert BS.CARD_STATES == BS.STATES[:-1] and BS.STATES[-1] == "no_break"
    assert set(BS.VOL_WORD) == {"broke_vol", "broke_quiet", "broke_unjudged"}
    assert not math.isnan(BS.base_peak_volume({"criteria": [k3("busiest bar 1,000")]}))
    assert copy.deepcopy(BS.HEAD) == BS.HEAD
