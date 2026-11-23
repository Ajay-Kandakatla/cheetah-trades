"""🏆 chip → jump to that win's replay at its peak (pwjump spec §3.1 / §3.2 / §4 `be`, 2026-11-22).

Ajay 2026-11-22, verbatim: "New feature when I click on this past winner tag take me to that video so change the date
and focus me on that video at that. time" then "past winner 11-18 +57%".

The 🏆 card gains `seek_s` (the MIDDLE of the first frame inside the labelled peak minute, from the renderer's own
schedule) + `seek_text`; the 🏆 payload gains `jump_missing_text`. Navigation only: no gate, no push, no rank. UNMEASURED.
NEGATIVES: no label / multi-day / unknown schedule / absurd numbers → None (never a raise, never a guess, never a hang);
the 36x / 10 fps float floor-division trap; the day payload and the past_winner entry keys are unchanged; owner-only.
"""
from __future__ import annotations

import ast
import bisect
import inspect
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chart_maps.replays import constants as C
from chart_maps.replays import store as ST
from tests.test_replays_past_winner_tag_2026_11_22 import day_card, meds_winners
from tests.test_replays_store_2026_11_17 import write_side
from tests.test_replays_winners_2026_11_18 import OTHER, OWN, _app, _cards, _strict, multi, put, single

PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "replays"
BAD_WORDS = re.compile(r"bounc|\bedge\b", re.I)
WIN_DAY = "2026-11-18"
CARD_DAY = "2026-11-20"
SCHEDULES = ((45.0, 10), (36, 10), (7, 3), (90, 7), (22.5, 10))


@pytest.fixture(autouse=True)
def _fresh_caches():
    for c in (ST._DAY_CACHE, ST._WIN_CACHE, ST._PW_CACHE):
        c.clear()
    yield
    for c in (ST._DAY_CACHE, ST._WIN_CACHE, ST._PW_CACHE):
        c.clear()


def tim(t, bucket=None):
    return {"bucket": bucket if bucket is not None else ST.bucket_of(t), "peak_t": t, "source": "label_winners 2026-11-22"}


def side(t="15:54", speed=45.0, fps=10, frames=12830, day=WIN_DAY, sym="VWAV", **kw):
    """A real single-day sidecar shape (the WP-VID keys) with a labeller `timing`."""
    s = single(sym, day, cg=57.07, hp=68.98, pick="today_top", today_rank=5, today_n=5, speed=speed, fps=fps,
               frames=frames)
    if t is not None:
        s["timing"] = tim(t)
    s.update(kw)
    return s


def _returns(fn, *a):
    """Run fn in a thread; a hung loop fails instead of hanging the suite."""
    out = {}

    def run():
        out["v"] = fn(*a)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(10)
    assert not th.is_alive(), "the call never returned"
    return out["v"]


def _host(*parts) -> Path:
    """A file under the host's eod-audits/ (the renderer + reels, READ-ONLY). Skips in the container (/app/tests/x.py
    has three parents) and when the file is not there."""
    here = Path(__file__).resolve()
    if len(here.parents) <= 3:
        pytest.skip("not on the host tree (no eod-audits beside the repo)")
    p = here.parents[3].joinpath("eod-audits", *parts)
    if not p.is_file():
        pytest.skip(f"{p} not on this host")
    return p


# ── 1. the mapping on REAL sidecar values (hermetic literals, spec §1.3) ──────────────────────────────────────────────
@pytest.mark.parametrize("t,want", [("15:54", 952.05), ("17:13", 1057.35), ("19:59", 1278.65), ("09:49", 465.35)])
def test_mapping_on_real_sidecar_values(t, want):
    assert ST.seek_seconds(side(t), "single_day") == want


def test_NEGATIVE_the_served_second_is_the_middle_of_the_frame_never_its_boundary():
    v = ST.seek_seconds(side("15:54"), "single_day")
    assert v == 952.05 and v != 952.0 and v != 952.1


# ── 2. host files (skip when absent) ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,want", [("2026-11-18_VWAV_45x.json", 952.05), ("2026-06-25_NEXR_45x.json", 1057.35)])
def test_host_sidecars(name, want):
    p = _host("replays", "videos", "winners", name)
    s = json.loads(p.read_text(encoding="utf-8"))
    assert ST.seek_seconds(s, "single_day") == want
    card = ST.winner_card(s, "winners")
    assert card["seek_s"] == want and card["seek_text"] == C.SEEK_WORDS.format(t=s["timing"]["peak_t"])


# ── 3. renderer source pins (skip when absent) ────────────────────────────────────────────────────────────────────
def test_renderer_hold_ms_equals_the_seek_hold():
    tree = ast.parse(_host("replays", "replay_gif.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "HOLD_MS" for t in n.targets))
    assert ast.literal_eval(node.value) == C.SEEK_HOLD_SEC * 1000


def test_renderer_schedule_source_pins():
    src = _host("replays", "replay_multiday.py").read_text(encoding="utf-8")
    for s in ("DAY_T0, DAY_T1 = dtime(4, 0), dtime(20, 0)", "step = self.speed / self.fps", "t0 + (j + 1) * step",
              "if not out or out[-1][1] < t1", "hi = bisect.bisect_left(self.m_t, t)"):
        assert s in src, s
    body = src[src.index("def render"):]
    assert body.index("for i, t in p.times()") < body.index("for _ in range(hold)")
    w = _host("replays", "replay_winners.py").read_text(encoding="utf-8")
    assert "RM.Plan(" in w and "RM.render(" in w


# ── 4. the schedule [C6] ──────────────────────────────────────────────────────────────────────────────────────────
def test_session_frames_known_schedules():
    assert ST.session_frames(45.0, 10) == 12800
    assert ST.session_frames(36, 10) == 16000
    assert ST.session_frames(7, 3) == 24686
    assert 5 * ST.session_frames(45.0, 10) + 30 == 64030          # the multi-day identity on the real GP reel


def _renderer_times(speed, fps):
    """replay_multiday.Plan.times for ONE session, EXACTLY its arithmetic, on a real epoch."""
    step = speed / fps
    t0 = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc).timestamp()
    t1 = t0 + 57600
    n = int((t1 - t0) // step)
    out = [t0 + (j + 1) * step for j in range(n)]
    if not out or out[-1] < t1:
        out.append(t1)
    return t0, out


@pytest.mark.parametrize("speed,fps", SCHEDULES)
def test_brute_force_mirror_of_the_renderer(speed, fps):
    t0, times = _renderer_times(speed, fps)
    assert len(times) == ST.session_frames(speed, fps)
    off = [m for m in range(960)
           if ST._seek_frame(60 * m, speed / fps) != bisect.bisect_right(times, t0 + 60 * m)]
    assert off == []


def test_NEGATIVE_mutation_guard_float_floor_division_sits_one_frame_early():
    assert int(19800 // 3.6) == 5499                              # the plain formula: one frame early
    assert ST._seek_frame(19800, 3.6) == 5500                     # the renderer first shows 09:30 on frame 5500
    s = side("09:30", speed=36, fps=10, frames=16030)
    assert ST.seek_seconds(s, "single_day") == 550.05


def test_NEGATIVE_no_while_in_the_seek_helpers():
    for fn in (ST._seek_step, ST.session_frames, ST._seek_frame, ST.seek_seconds):
        assert not re.search(r"\bwhile\b", inspect.getsource(fn)), fn.__name__


# ── 5. constants ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants():
    assert (C.WINDOW_T0, C.WINDOW_T1) == ("04:00", "20:00")
    assert C.SEEK_SESSION_SEC == 57600
    assert 0 < C.SEEK_EPS < 1e-3
    assert C.SEEK_WORDS.format(t="15:54") == "⏩ opens at the peak minute, 15:54 ET"
    assert C.SEEK_NONE_WORDS == "no peak time on this replay — it opens at the start"
    assert C.JUMP_MISSING_WORDS == "That replay is no longer listed."


def test_NEGATIVE_the_window_and_schedule_are_never_retyped():
    src = (PKG / "constants.py").read_text(encoding="utf-8")
    block = src[src.index("WINDOW_T0, WINDOW_T1 ="):src.index("JUMP_MISSING_WORDS =")]
    code = [ln.split("#")[0] for ln in block.splitlines()]
    assert not any(w in ln for ln in code for w in ("04:00", "20:00", "57600")), code
    banned = {57600, 45, 45.0, 10, 3000, 12800, 12830, 30, "04:00", "20:00"}
    for fn in (ST._seek_step, ST.session_frames, ST._seek_frame, ST.seek_seconds):
        tree = ast.parse(inspect.getsource(fn))
        doc = ast.get_docstring(tree.body[0])
        consts = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value != doc
                  and not isinstance(n.value, bool)}
        assert not consts & banned, (fn.__name__, consts & banned)


# ── 6. no label ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_timing_key_serves_none_and_the_card_is_still_listed(tmp_path):
    put(tmp_path, "winners", side(t=None))
    p = ST.winners_payload(tmp_path)
    (v,) = _cards(p)
    assert v["seek_s"] is None and v["seek_text"] == C.SEEK_NONE_WORDS
    assert p["counts"]["skipped_bad"] == 0 and p["counts"]["videos"] == 1


# ── 7. bad inputs [C7] ────────────────────────────────────────────────────────────────────────────────────────────
_BAD = [
    ("peak 25:99", {"timing": {"bucket": "eod", "peak_t": "25:99"}}),
    ("peak int", {"timing": {"bucket": "eod", "peak_t": 1554}}),
    ("peak None", {"timing": {"bucket": "eod", "peak_t": None}}),
    ("bucket null", {"timing": {"bucket": None, "peak_t": "15:54"}}),
    ("bucket disagrees", {"timing": {"bucket": "first_hour", "peak_t": "15:54"}}),
    ("timing not a dict", {"timing": "15:54"}),
    ("speed 0", {"speed": 0}),
    ("speed -45", {"speed": -45.0}),
    ("speed 5e-324", {"speed": 5e-324}),
    ("speed 1e-300", {"speed": 1e-300}),
    ("speed nan", {"speed": float("nan")}),
    ("speed str", {"speed": "45"}),
    ("fps 0", {"fps": 0}),
    ("fps True", {"fps": True}),
    ("fps str", {"fps": "10"}),
    ("fps float", {"fps": 10.0}),
    ("fps 10**400", {"fps": 10 ** 400}),
    ("frames intro", {"frames": 12860}),
    ("frames no hold", {"frames": 12800}),
    ("frames str", {"frames": "12830"}),
    ("frames 10**400", {"frames": 10 ** 400}),
    ("frames True", {"frames": True}),
    ("frames 0", {"frames": 0}),
    ("days two", {"days": ["2026-11-17", "2026-11-18"]}),
    ("days str", {"days": "2026-11-18"}),
    ("window 16:00", {"window": "04:00-16:00 ET"}),
]


@pytest.mark.parametrize("why,patch", _BAD, ids=[b[0] for b in _BAD])
def test_NEGATIVE_bad_inputs_give_none_never_a_raise_never_a_hang(why, patch):
    s = side("15:54")
    s.update(patch)
    assert _returns(ST.seek_seconds, s, "single_day") is None


@pytest.mark.parametrize("missing", ["fps", "frames", "days", "speed", "window", "timing"])
def test_NEGATIVE_a_missing_key_gives_none(missing):
    s = side("15:54")
    s.pop(missing)
    assert _returns(ST.seek_seconds, s, "single_day") is None


@pytest.mark.parametrize("speed,fps", [(5e-324, 10), (1e-300, 10), (45.0, 10 ** 400), (0, 10), (45.0, 0),
                                       (float("inf"), 10), (45.0, True), (None, 10)])
def test_NEGATIVE_session_frames_on_absurd_inputs_never_raises(speed, fps):
    v = _returns(ST.session_frames, speed, fps)
    assert v is None or (speed == 1e-300 and isinstance(v, int))


def test_NEGATIVE_seek_frame_on_a_tiny_step_returns():
    assert isinstance(_returns(ST._seek_frame, 19800, 1e-301), (int, type(None)))


def test_NEGATIVE_the_helper_swallows_a_non_dict_side():
    assert _returns(ST.seek_seconds, None, "single_day") is None
    assert _returns(ST.seek_seconds, ["x"], "single_day") is None


def test_NEGATIVE_absurd_sidecars_through_both_payloads_are_listed_with_no_second(tmp_path):
    put(tmp_path, "winners", side("15:54", sym="TINY", speed=5e-324))
    put(tmp_path, "winners", side("15:54", sym="HUGE", fps=10 ** 400))
    put(tmp_path, "winners", side("15:54", sym="BIGF", frames=10 ** 400))
    put(tmp_path, "winners", side("15:54", sym="SMALL", speed=1e-300))
    p = _returns(ST.winners_payload, tmp_path)
    by = {v["symbol"]: v for v in _cards(p)}
    assert set(by) == {"TINY", "HUGE", "BIGF", "SMALL"} and p["counts"]["skipped_bad"] == 0
    assert all(v["seek_s"] is None and v["seek_text"] == C.SEEK_NONE_WORDS for v in by.values())
    for sym in by:
        write_side(tmp_path / C.VIDEOS_SUB / CARD_DAY, day_card(sym))
    d = _returns(ST.payload, CARD_DAY, tmp_path)
    tagged = {v["symbol"]: v for v in _cards(d)}
    assert set(tagged) == set(by) and all(v["past_winner"][0]["day"] == WIN_DAY for v in tagged.values())


# ── 8. multi-day ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_multi_day_reel_with_a_stray_valid_timing_serves_none(tmp_path):
    m = multi("BTCT", timing=tim("15:54"))
    assert ST.seek_seconds(m, "multi_day") is None
    assert ST.seek_seconds(side("15:54"), "single_day") == 952.05
    assert ST.seek_seconds(side("15:54"), "multi_day") is None        # the SAME valid one-session shape: the kind decides
    put(tmp_path, "multiday", m)
    (v,) = _cards(ST.winners_payload(tmp_path))
    assert v["kind"] == "multi_day" and v["seek_s"] is None and v["seek_text"] == C.SEEK_NONE_WORDS


# ── 9. each card its own second ───────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_wrong_symbol_each_card_carries_its_own_second(tmp_path):
    put(tmp_path, "winners", side("15:54", sym="VWAV"))
    put(tmp_path, "winners", side("15:23", sym="AKAN"))
    by = {v["symbol"]: v for v in _cards(ST.winners_payload(tmp_path))}
    assert by["VWAV"]["seek_s"] == 952.05 and by["AKAN"]["seek_s"] == 910.65
    assert by["VWAV"]["seek_s"] != by["AKAN"]["seek_s"]
    assert by["VWAV"]["seek_text"] == "⏩ opens at the peak minute, 15:54 ET"
    assert by["AKAN"]["seek_text"] == "⏩ opens at the peak minute, 15:23 ET"


# ── 10. jump_missing_text in all three states ─────────────────────────────────────────────────────────────────────
def test_jump_missing_text_in_ready_empty_and_no_folder(tmp_path):
    assert ST.winners_payload(tmp_path / "nope")["state"] == "no_folder"
    assert ST.winners_payload(tmp_path / "nope")["jump_missing_text"] == C.JUMP_MISSING_WORDS
    (tmp_path / C.VIDEOS_SUB).mkdir()
    e = ST.winners_payload(tmp_path)
    assert e["state"] == "empty" and e["jump_missing_text"] == C.JUMP_MISSING_WORDS
    put(tmp_path, "winners", side("15:54"))
    r = ST.winners_payload(tmp_path)
    assert r["state"] == "ready" and r["jump_missing_text"] == C.JUMP_MISSING_WORDS


# ── 11. the day payload is unchanged ──────────────────────────────────────────────────────────────────────────────
def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def test_NEGATIVE_the_day_payload_gains_no_key_and_the_entry_keys_are_unchanged(tmp_path):
    put(tmp_path, "winners", side("15:54"))
    write_side(tmp_path / C.VIDEOS_SUB / CARD_DAY, day_card("VWAV"))
    d = ST.payload(CARD_DAY, tmp_path)
    keys = set(_keys(d))
    assert not keys & {"seek_s", "seek_text", "jump_missing_text"}
    (v,) = _cards(d)
    assert set(v["past_winner"][0]) == {"day", "kind", "close_gain_pct", "file", "sub", "text"}
    assert v["past_winner"][0]["file"] == "2026-11-18_VWAV_45x.mp4" and v["past_winner"][0]["sub"] == "winners"


# ── 12. a multi-day win → the run is the entry ────────────────────────────────────────────────────────────────────
def test_a_multi_day_win_is_served_as_the_run(tmp_path):
    meds_winners(tmp_path)
    write_side(tmp_path / C.VIDEOS_SUB / CARD_DAY, day_card("MEDS"))
    (v,) = _cards(ST.payload(CARD_DAY, tmp_path))
    assert [(e["sub"], e["file"]) for e in v["past_winner"]] == [("multiday", "2026-09-15_MEDS_45x.mp4")]


# ── 13. only wins that ENDED before the card's day ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("card_day", [WIN_DAY, "2026-11-17"])
def test_NEGATIVE_a_win_on_the_cards_own_day_or_later_is_no_entry(tmp_path, card_day):
    put(tmp_path, "winners", side("15:54"))
    write_side(tmp_path / C.VIDEOS_SUB / card_day, day_card("VWAV", card_day))
    (v,) = _cards(ST.payload(card_day, tmp_path))
    assert "past_winner" not in v


# ── 14. the owner route ───────────────────────────────────────────────────────────────────────────────────────────
def test_owner_route_serves_the_second_and_NEGATIVE_anyone_else_404(monkeypatch, tmp_path):
    put(tmp_path, "winners", side("15:54"))
    c = TestClient(_app(monkeypatch, tmp_path))
    r = c.get(C.WINNERS_API_PATH, headers=OWN)
    assert r.status_code == 200
    body = _strict(r.text)
    (v,) = _cards(body)
    assert v["seek_s"] == 952.05 and body["jump_missing_text"] == C.JUMP_MISSING_WORDS
    o = c.get(C.WINNERS_API_PATH, headers={"X-User-Email": OTHER})
    assert o.status_code == 404 and o.json() == {"detail": "Not Found"}


# ── 15. words + source ────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_new_strings_carry_no_b_word_or_edge(tmp_path):
    for n in ("SEEK_WORDS", "SEEK_NONE_WORDS", "JUMP_MISSING_WORDS"):
        assert not BAD_WORDS.search(getattr(C, n)), n
    put(tmp_path, "winners", side("15:54"))
    put(tmp_path, "winners", side(t=None, sym="NOLB"))
    p = ST.winners_payload(tmp_path)
    served = [v["seek_text"] for v in _cards(p)] + [p["jump_missing_text"]]
    assert C.SEEK_NONE_WORDS in served and "⏩ opens at the peak minute, 15:54 ET" in served
    assert not any(BAD_WORDS.search(s) for s in served)


def test_source_pins_one_seek_helper_and_four_routes():
    src = (PKG / "store.py").read_text(encoding="utf-8")
    assert src.count("def seek_seconds(") == 1
    api = (PKG / "api.py").read_text(encoding="utf-8")
    routes = re.findall(r"@router\.(?:get|api_route)\(([^\n]*)\)\s*\nasync def \w+\(([^\n]*)\):", api)
    assert len(routes) == 4
    assert "seek" not in api
