"""🏆 Past winners on 🎬 Replays — store + routes (spec pastwinners §3.5 / §4 WP-APP, 2026-11-18).

Ajay 2026-11-18 ~21:45 ET, verbatim: "can you work on todays videos and also..  Winners in general from the past".

`videos/winners/` (single-day winner reels, one session 04:00-20:00 ET) and `videos/multiday/` (the multi-day runner
reels, window "04:00-20:00 ET x N sessions (...)") are listed by two new owner-only routes. The kind comes from the
FOLDER; every served word is composed from constants + sidecar numbers. Hand-picked winners: descriptive, UNMEASURED.

GOLDEN: the day listing (`payload`, `dates`, the HTTP body) is byte-identical before vs after the two folders appear.
NEGATIVES throughout: non-owner 404 (store never read), no header 401, bad subs / names / symlinks / unlisted files,
bad windows, bad numbers, legacy `gain_pct` never the headline, sidecar free text never served, no b-word / "edge".
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from chart_maps.gajjala import constants as GC
from chart_maps.replays import api as API
from chart_maps.replays import constants as C
from chart_maps.replays import store as ST
from tests.test_replays_store_2026_11_17 import (DAY, akan_winner, cenn_carried, pavs_loser, rs_side, write_ledger,
                                                 write_side)

OWNER = "owner@example.com"
OTHER = "doug@example.com"
OWN = {"X-User-Email": OWNER}
BLOB = bytes(range(256)) * 128                       # 32,768 bytes — above the GZip floor (the 11-17 api test)
PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "replays"
ASK = "can you work on todays videos and also..  Winners in general from the past"
LABEL = "hand-picked winners (survivorship) - traits are descriptive, UNMEASURED, not an edge"
BAD_WORDS = re.compile(r"bounc|\bedge\b", re.I)


@pytest.fixture(autouse=True)
def _pages_as_of_11_17(monkeypatch):
    """The day-listing golden reuses the 11-17 fixtures (1-min reels) with the 11-18 exclusion OFF, like the 11-17 tests."""
    monkeypatch.setattr(C, "EXCLUDED_PAGES", ())


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


# ── fixtures in the WP-VID sidecar shapes (spec §3.4) ─────────────────────────────────────────────────────────────
def single(sym="GP", day="2026-11-12", cg=120.0, hp=180.0, spike=False, pick="plus100", today_rank=None,
           today_n=None, window=C.FULL_DAY_WINDOW, **kw):
    s = {"file": f"{day}_{sym}_45x.mp4", "symbol": sym, "kind": "single_day", "category": "single-day winners",
         "pick": pick, "today_rank": today_rank, "today_n": today_n, "day": day, "days": [day],
         "base_day": "2026-11-11", "base_close": 1.0, "open": 1.2, "high": 1 + hp / 100, "close": 1 + cg / 100,
         "volume": 5_000_000, "window": window, "speed": 45.0, "fps": 10, "frames": 12830, "minutes": 21.4,
         "source": "built from 1-min bars", "close_gain_pct": cg, "high_pct": hp, "spike_print": spike,
         "spike_x": 2.0, "day_before": {"prior_vol": 1.0}, "run_day1": {"day1_gap_pct": 3.0},
         "app_rang": None, "also_multiday": None, "label": LABEL, "ask": ASK, "render_sec": 19.0}
    s.update(kw)
    return s


def multi(sym="BTCT", days=("2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21", "2026-08-24"), cg=300.0,
          gain_pct=491.5, spike=False, forced=None, **kw):
    days = list(days)
    s = {"file": f"{days[1]}_{sym}_45x.mp4", "symbol": sym, "category": "multi-day runners", "days": days,
         "window": f"{C.FULL_DAY_WINDOW} x {len(days)} sessions ({days[0]} -> {days[-1]})", "speed": 45.0, "fps": 10,
         "frames": 64030, "minutes": 106.7, "source": "built from 1-min bars", "gain_pct": gain_pct,
         "base_day": days[0], "peak_day": days[-1], "day_before": {}, "run_day1": {}, "label": LABEL,
         "ask": "the multi-day ask", "forced": forced, "render_sec": 211.9,
         # the WP-VID backfill keys (spec §3.4)
         "kind": "multi_day", "day": days[1], "close_gain_pct": cg, "high_pct": gain_pct, "spike_print": spike,
         "spike_x": 2.0}
    s.update(kw)
    return s


def put(root: Path, sub: str, side: dict, mp4=True, raw=None, blob=BLOB):
    d = root / C.VIDEOS_SUB / sub
    d.mkdir(parents=True, exist_ok=True)
    stem = side["file"][: -len(".mp4")]
    (d / f"{stem}.json").write_text(raw if raw is not None else json.dumps(side, indent=1), encoding="utf-8")
    if mp4:
        (d / side["file"]).write_bytes(blob)
    return d


def day_root(r: Path) -> Path:
    """The 11-17 day folder the golden compares (cards + a 16:00 reel + jobs.json + the ledger)."""
    d = r / C.VIDEOS_SUB / DAY
    for s in (akan_winner(), cenn_carried(), pavs_loser(), rs_side("GP", "10:05", 40.0)):
        write_side(d, s)
    s = akan_winner()
    s.update(file="OLD_1600_24x.mp4", window="04:00-16:00 ET")
    write_side(d, s)
    (r / C.VIDEOS_SUB / "jobs.json").write_text("[]")
    write_ledger(r)
    return r


def add_winner_folders(r: Path):
    put(r, "winners", single("GP", "2026-11-12", cg=120.0, hp=180.0))
    put(r, "winners", single("PAVS", "2026-06-09", cg=8.4, hp=2738.0, spike=True))
    put(r, "winners", single("ZZZ", "2026-11-18", cg=60.0, hp=80.0, pick="today_top", today_rank=2, today_n=5))
    put(r, "winners", single("AAA", "2026-11-12", cg=300.0, hp=320.0))
    put(r, "multiday", multi("BTCT"))
    put(r, "multiday", multi("NXXT", days=("2026-11-10", "2026-11-11", "2026-11-12"), cg=785.0, gain_pct=3140.0,
                             spike=True, forced="Ajay's example; NOT a +100% multi-day run in the bars"))
    put(r, "multiday", multi("GP", days=("2026-11-11", "2026-11-12", "2026-11-13"), cg=90.0, gain_pct=150.0,
                             file="2026-11-12_GP_45x.mp4"))
    for sub in ("winners", "multiday"):
        (r / C.VIDEOS_SUB / sub / "jobs.json").write_text(json.dumps([{"id": "x", "window": C.FULL_DAY_WINDOW}]))
    (r / C.VIDEOS_SUB / "multiday" / "runners.json").write_text(json.dumps({"runs": [], "window": [1, 2]}))
    (r / C.VIDEOS_SUB / "winners" / "winners.json").write_text(json.dumps({"rows": [], "window": C.FULL_DAY_WINDOW}))
    phone = r / C.VIDEOS_SUB / "multiday" / "phone"
    phone.mkdir()
    (phone / "2026-08-19_BTCT_45x.mp4").write_bytes(BLOB)
    (phone / "2026-08-19_BTCT_45x.json").write_text(json.dumps(multi("BTCT")))
    (r / C.VIDEOS_SUB / "winners" / "run_log.tsv").write_text("x\tok\t1\t1\n")


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "replays"
    day_root(r)
    add_winner_folders(r)
    return r


def _app(monkeypatch, root):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setenv(C.ROOT_ENV, str(root))
    app = FastAPI()
    app.add_middleware(GZipMiddleware, minimum_size=1024)       # the SAME middleware + floor main.py ships
    app.include_router(API.router)
    return app


@pytest.fixture()
def wired(monkeypatch, root):
    return TestClient(_app(monkeypatch, root))


def _wv(sub, name):
    return C.WINNERS_VIDEO_PATH.format(sub=sub, name=name)


def _cards(p):
    return [v for g in p["groups"] for v in g["videos"]]


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_built_from_the_house_constants():
    assert C.WINNERS_API_PATH == C.API_PATH + "/winners" == "/chart-maps/replays/winners"
    assert C.WINNERS_VIDEO_PATH == "/chart-maps/replays/winners/video/{sub}/{name}"
    assert C.WINNER_SUB_KEYS == ("winners", "multiday")
    assert [k for _s, k, _t in C.WINNER_SUBS] == ["single_day", "multi_day"]
    assert C.MULTI_WINDOW_PREFIX == C.FULL_DAY_WINDOW + " x "
    assert C.WINNERS_TITLE == "🏆 Past winners"
    assert "UNMEASURED" in C.WINNERS_NOTE
    assert f"+{GC.SA_BIG_RUNNER_PCT:g}%" in C.WINNERS_NOTE
    assert f"{GC.SCAN_MIN_VOLUME:,}" in C.WINNERS_NOTE
    assert f"${GC.SCAN_MIN_PRICE:g}" in C.WINNERS_NOTE and f"${GC.SCAN_MAX_PRICE:g}" in C.WINNERS_NOTE
    assert C.FULL_DAY_WINDOW in C.WINNERS_WINDOW_NOTE
    assert set(C.NON_SIDECAR_JSON) == {"jobs.json", "runners.json", "winners.json"}


def test_NEGATIVE_no_b_word_or_edge_in_any_winners_string():
    names = [n for n in dir(C) if n.startswith("WINNERS_") or n.endswith("_WORDS")]
    assert names
    for n in names:
        for s in _strings(getattr(C, n)):
            assert not BAD_WORDS.search(s), (n, s)


def test_NEGATIVE_the_note_numbers_are_never_retyped_in_constants():
    src = (PKG / "constants.py").read_text(encoding="utf-8")
    block = src[src.index("WINNERS_NOTE"):src.index("WINNERS_WINDOW_NOTE")]
    for lit in ("1,000,000", "1_000_000", "100%", "0.10", "$100"):
        assert lit not in block, lit
    assert "GC.SA_BIG_RUNNER_PCT" in block and "GC.SCAN_MIN_VOLUME" in block


# ── GOLDEN: the day listing never moves ───────────────────────────────────────────────────────────────────────
def test_GOLDEN_the_day_listing_is_byte_identical_with_the_winner_folders(tmp_path, monkeypatch):
    r = tmp_path / "replays"
    day_root(r)
    before = json.dumps(ST.payload(DAY, r), sort_keys=True)
    before_dates = ST.dates(r)
    c = TestClient(_app(monkeypatch, r))
    http_before = c.get(C.API_PATH, params={"date": DAY}, headers=OWN).content
    add_winner_folders(r)
    os.utime(r / C.VIDEOS_SUB / DAY)                              # force a re-scan of the day folder too
    ST._DAY_CACHE.clear()
    assert json.dumps(ST.payload(DAY, r), sort_keys=True) == before
    assert ST.dates(r) == before_dates == [DAY]
    assert c.get(C.API_PATH, params={"date": DAY}, headers=OWN).content == http_before
    assert json.dumps(ST.payload(None, r), sort_keys=True) == before


# ── listing ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_both_kinds_listed_groups_date_desc_close_gain_desc(root):
    p = ST.winners_payload(root)
    assert p["state"] == "ready" and p["text"] is None
    assert p["title"] == C.WINNERS_TITLE and p["tab"] == C.TAB and p["note"] == C.WINNERS_NOTE
    assert p["window"] == C.FULL_DAY_WINDOW and p["window_note"] == C.WINNERS_WINDOW_NOTE
    assert [g["date"] for g in p["groups"]] == ["2026-11-18", "2026-11-12", "2026-11-11", "2026-08-19", "2026-06-09"]
    assert [g["label"] for g in p["groups"]] == ["Wed 2026-11-18", "Thu 2026-11-12", "Wed 2026-11-11",
                                                 "Wed 2026-08-19", "Tue 2026-06-09"]
    g12 = p["groups"][1]
    assert [(v["symbol"], v["sub"]) for v in g12["videos"]] == [("AAA", "winners"), ("GP", "winners"),
                                                                ("GP", "multiday")]
    assert p["counts"] == {"videos": 7, "single_day": 4, "multi_day": 3, "skipped_window": 0, "skipped_bad": 0,
                           "no_sidecar": 0}
    assert p["summary_text"] == "7 videos · 4 single-day · 3 multi-day"
    _strict(json.dumps(p, allow_nan=True))


def test_card_fields_single_and_multi(root):
    by = {(v["sub"], v["symbol"]): v for v in _cards(ST.winners_payload(root))}
    gp = by[("winners", "GP")]
    assert gp == {"file": "2026-11-12_GP_45x.mp4", "sub": "winners",
                  "src": "/chart-maps/replays/winners/video/winners/2026-11-12_GP_45x.mp4", "symbol": "GP",
                  "kind": "single_day", "kind_text": "single-day", "date": "2026-11-12", "label_date": "Thu 2026-11-12",
                  "days": ["2026-11-12"], "days_text": "2026-11-12", "close_gain_pct": 120.0,
                  "gain_text": "+120% on the close", "high_pct": 180.0, "high_text": "+180% high",
                  "spike_print": False, "spike_text": None, "pick_text": None, "speed": 45.0, "speed_text": "45x",
                  "minutes": 21.4, "length_text": "21 min"}
    bt = by[("multiday", "BTCT")]
    assert bt["kind"] == "multi_day" and bt["kind_text"] == "multi-day"
    assert bt["days_text"] == "2026-08-18 → 2026-08-24 · 5 sessions"
    assert bt["gain_text"] == "+300% best close vs the day before" and bt["high_text"] == "+492% run high"
    assert bt["pick_text"] is None and bt["date"] == "2026-08-19"
    top = by[("winners", "ZZZ")]
    assert top["pick_text"] == f"top 5 mover of its day (high under +{GC.SA_BIG_RUNNER_PCT:g}%)"


def test_the_same_file_name_in_both_subs_is_two_cards_two_srcs(root):
    gp = [v for v in _cards(ST.winners_payload(root)) if v["file"] == "2026-11-12_GP_45x.mp4"]
    assert len(gp) == 2 and len({v["src"] for v in gp}) == 2 and {v["sub"] for v in gp} == {"winners", "multiday"}


def test_spike_card_and_NEGATIVE_legacy_gain_pct_never_the_headline(root):
    by = {(v["sub"], v["symbol"]): v for v in _cards(ST.winners_payload(root))}
    pavs = by[("winners", "PAVS")]
    assert pavs["spike_print"] is True and pavs["spike_text"] == "⚠ high more than 2× the close — a spike print?"
    assert pavs["gain_text"] == "+8% on the close"
    nx = by[("multiday", "NXXT")]
    assert nx["gain_text"] == "+785% best close vs the day before"
    assert "3140" not in nx["gain_text"]
    assert nx["pick_text"] == f"your example — not a +{GC.SA_BIG_RUNNER_PCT:g}% run"
    assert "Ajay's example" not in json.dumps(ST.winners_payload(root))
    s = single("SPK", spike=True, spike_x=2.0, cg=20.0, hp=500.0)
    card = ST.winner_card(s, "winners")
    assert card["spike_text"] and card["gain_text"] == "+20% on the close"


def test_NEGATIVE_a_negative_gain_uses_the_true_minus():
    card = ST.winner_card(single("DN", cg=-12.4, hp=105.0), "winners")
    assert card["gain_text"] == "−12% on the close" and "-" not in card["gain_text"]
    assert ST._signed_pct(5.4) == "+5%" and ST._signed_pct(-0.4) == "−0%"


def test_NEGATIVE_spike_text_only_when_spike_print_is_true(root):
    for v in _cards(ST.winners_payload(root)):
        assert (v["spike_text"] is not None) == (v["spike_print"] is True), v["symbol"]


def test_NEGATIVE_jobs_runners_winners_json_and_phone_copies_are_ignored(root):
    for sub in C.WINNER_SUB_KEYS:
        lst = ST.read_winner_sub(sub, root)
        assert not any(f.endswith(".json") for f in lst["files"])
    p = ST.winners_payload(root)
    assert p["counts"]["skipped_bad"] == 0 and p["counts"]["skipped_window"] == 0
    txt = json.dumps(p)
    assert "jobs.json" not in txt and "runners.json" not in txt and "winners.json" not in txt and "phone" not in txt
    assert sum(1 for v in _cards(p) if v["symbol"] == "BTCT") == 1


def test_NEGATIVE_sidecar_free_text_is_never_served(root):
    txt = json.dumps(ST.winners_payload(root))
    for t in (LABEL, ASK, "the multi-day ask", "single-day winners", "built from 1-min bars"):
        assert t not in txt, t
    assert '"gain_pct"' not in txt


def test_NEGATIVE_a_sidecar_category_why_or_label_never_reaches_the_card():
    s = single("FREE", category="CATEGORY-TEXT", why=["WHY-TEXT"], label="LABEL-TEXT", ask="ASK-TEXT")
    m = multi("FREEM", category="MCAT-TEXT", forced="FORCED-TEXT", label="MLABEL-TEXT")
    txt = json.dumps([ST.winner_card(s, "winners"), ST.winner_card(m, "multiday")])
    for t in ("CATEGORY-TEXT", "WHY-TEXT", "LABEL-TEXT", "ASK-TEXT", "MCAT-TEXT", "FORCED-TEXT", "MLABEL-TEXT"):
        assert t not in txt, t


def test_NEGATIVE_every_served_string_is_free_of_the_b_word_and_edge(root):
    p = ST.winners_payload(root)
    for s in _strings(p):
        assert not BAD_WORDS.search(s), s


def test_empty_and_no_folder_shapes(tmp_path):
    p = ST.winners_payload(tmp_path / "missing")
    assert p["state"] == "no_folder" and p["text"] == C.NO_FOLDER_TEXT and p["groups"] == []
    r = tmp_path / "r"
    (r / C.VIDEOS_SUB).mkdir(parents=True)
    e = ST.winners_payload(r)
    assert e["state"] == "empty" and e["text"] == C.WINNERS_EMPTY_TEXT and e["groups"] == []
    assert e["summary_text"] == "0 videos · 0 single-day · 0 multi-day"
    write_side(r / C.VIDEOS_SUB / DAY, pavs_loser())               # a day reel never counts as a past winner
    assert ST.winners_payload(r)["state"] == "empty"


# ── accept rule NEGATIVES ─────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("window", ["04:00-16:00 ET", "04:00-20:00 ETX", None, 7, ["04:00-20:00 ET"],
                                    "04:00-20:00 ET x 3 sessions (2026-11-10 -> 2026-11-12)"])
def test_NEGATIVE_a_bad_window_in_winners_is_skipped_window(tmp_path, window):
    s = single("BADW")
    if window is None:
        del s["window"]
    else:
        s["window"] = window
    put(tmp_path, "winners", s)
    lst = ST.read_winner_sub("winners", tmp_path)
    assert lst["videos"] == [] and lst["counts"]["skipped_window"] == 1 and lst["counts"]["no_sidecar"] == 0


@pytest.mark.parametrize("window", [C.FULL_DAY_WINDOW, "04:00-16:00 ET x 3 sessions", None, "04:00-20:00 ETx 3"])
def test_NEGATIVE_multiday_needs_the_x_form(tmp_path, window):
    s = multi("ONE")
    s["window"] = window
    put(tmp_path, "multiday", s)
    lst = ST.read_winner_sub("multiday", tmp_path)
    assert lst["videos"] == [] and lst["counts"]["skipped_window"] == 1


@pytest.mark.parametrize("field,value", [("close_gain_pct", float("nan")), ("close_gain_pct", "12"),
                                         ("close_gain_pct", None), ("close_gain_pct", True), ("symbol", ""),
                                         ("symbol", 5), ("day", "2026-11-1"), ("days", []), ("days", ["x"]),
                                         ("days", "2026-11-12"), ("speed", None), ("minutes", "21"),
                                         ("speed", float("inf")), ("spike_print", "yes"), ("spike_print", None),
                                         ("pick", "other"), ("pick", None)])
def test_NEGATIVE_one_malformed_card_drops_only_itself(tmp_path, field, value):
    put(tmp_path, "winners", single("OK1"))
    s = single("MAL", day="2026-11-13")
    s[field] = value
    put(tmp_path, "winners", s, raw=json.dumps(s, allow_nan=True))
    lst = ST.read_winner_sub("winners", tmp_path)
    assert [v["symbol"] for v in lst["videos"]] == ["OK1"]
    assert lst["counts"]["skipped_bad"] == 1
    p = ST.winners_payload(tmp_path)
    assert p["state"] == "ready" and p["counts"]["skipped_bad"] == 1
    _strict(json.dumps(p, allow_nan=True))


@pytest.mark.parametrize("missing", ["close_gain_pct", "spike_print", "day", "days", "symbol"])
def test_NEGATIVE_a_missing_key_is_skipped_bad(tmp_path, missing):
    s = single("MISS")
    del s[missing]
    put(tmp_path, "winners", s)
    assert ST.read_winner_sub("winners", tmp_path)["counts"]["skipped_bad"] == 1


def test_NEGATIVE_spike_true_needs_a_positive_spike_x(tmp_path):
    for i, sx in enumerate((None, 0, -2.0, float("nan"), "2")):
        s = single(f"SX{i}", spike=True, spike_x=sx)
        put(tmp_path, "winners", s, raw=json.dumps(s, allow_nan=True))
    lst = ST.read_winner_sub("winners", tmp_path)
    assert lst["videos"] == [] and lst["counts"]["skipped_bad"] == 5


def test_NEGATIVE_today_top_needs_a_positive_int_today_n(tmp_path):
    for i, n in enumerate((None, 0, "5", True, 5.0)):
        put(tmp_path, "winners", single(f"TN{i}", pick="today_top", today_n=n))
    assert ST.read_winner_sub("winners", tmp_path)["counts"]["skipped_bad"] == 5


def test_NEGATIVE_high_pct_nan_is_served_null(tmp_path):
    s = single("HNAN", hp=float("nan"))
    put(tmp_path, "winners", s, raw=json.dumps(s, allow_nan=True))
    p = ST.winners_payload(tmp_path)
    v = _cards(p)[0]
    assert v["high_pct"] is None and v["high_text"] is None
    _strict(json.dumps(p, allow_nan=True))


def test_NEGATIVE_a_sidecar_kind_never_decides_the_kind(tmp_path):
    s = single("KND")
    s["kind"] = "multi_day"
    put(tmp_path, "winners", s)
    assert _cards(ST.winners_payload(tmp_path))[0]["kind"] == "single_day"


def test_NEGATIVE_an_mp4_without_sidecar_and_a_part_render(tmp_path):
    d = tmp_path / C.VIDEOS_SUB / "winners"
    d.mkdir(parents=True)
    (d / "2026-11-12_LOOSE_45x.mp4").write_bytes(BLOB)
    s = single("PART")
    put(tmp_path, "winners", s, mp4=False)
    (d / "2026-11-12_PART_45x.part.mp4").write_bytes(BLOB)
    lst = ST.read_winner_sub("winners", tmp_path)
    assert lst["videos"] == [] and lst["counts"]["no_sidecar"] == 2 and lst["counts"]["skipped_bad"] == 1
    assert ST.resolve_winner_video("winners", "2026-11-12_LOOSE_45x.mp4", tmp_path) is None
    os.rename(d / "2026-11-12_PART_45x.part.mp4", d / "2026-11-12_PART_45x.mp4")
    assert "2026-11-12_PART_45x.mp4" in ST.read_winner_sub("winners", tmp_path)["files"]


def test_cache_reparses_only_when_the_folder_key_moves(root, monkeypatch):
    real = ST._read_sidecar
    n = {"c": 0}

    def counting(p):
        n["c"] += 1
        return real(p)
    monkeypatch.setattr(ST, "_read_sidecar", counting)
    ST._WIN_CACHE.clear()
    ST.read_winner_sub("winners", root)
    first = n["c"]
    assert first == 4                                               # winners.json / jobs.json are never read
    ST.read_winner_sub("winners", root)
    assert n["c"] == first
    p = root / C.VIDEOS_SUB / "winners" / "2026-11-12_GP_45x.json"
    s = json.loads(p.read_text())
    s["close_gain_pct"] = 150.0
    p.write_text(json.dumps(s))
    st = os.stat(p)
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))
    lst = ST.read_winner_sub("winners", root)
    assert n["c"] > first
    assert {v["symbol"]: v["close_gain_pct"] for v in lst["videos"]}["GP"] == 150.0


# ── resolve_winner_video ──────────────────────────────────────────────────────────────────────────────────────
def test_resolve_a_listed_file_in_each_sub(root):
    a = ST.resolve_winner_video("winners", "2026-11-12_GP_45x.mp4", root)
    b = ST.resolve_winner_video("multiday", "2026-11-12_GP_45x.mp4", root)
    assert a is not None and b is not None and a != b and a.parent.name == "winners" and b.parent.name == "multiday"


@pytest.mark.parametrize("sub,name", [
    (DAY, "AKAN_reversal_squeeze_1mpage_24x.mp4"), ("..", "2026-11-12_GP_45x.mp4"), ("phone", "2026-08-19_BTCT_45x.mp4"),
    ("_bars", "x.mp4"), ("Winners", "2026-11-12_GP_45x.mp4"), ("winners/..", "2026-11-12_GP_45x.mp4"),
    ("multiday/phone", "2026-08-19_BTCT_45x.mp4"), ("winners", "x/y.mp4"), ("winners", ".."),
    ("winners", "../2026-11-12_GP_45x.mp4"), ("winners", ".hidden.mp4"), ("winners", "2026-11-12_GP_45x.json"),
    ("winners", "2026-11-12_GP_45x.MP4"), ("winners", "x.mp4.json"), ("winners", "winners.json"),
    ("winners", "2026-11-12_BTCT_45x.mp4"), ("multiday", "2026-11-12_AAA_45x.mp4"), (None, "x.mp4"),
])
def test_NEGATIVE_resolve_refuses(root, sub, name):
    assert ST.resolve_winner_video(sub, name, root) is None


def test_NEGATIVE_a_symlink_out_of_the_folder_is_refused(root, tmp_path):
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"secret")
    s = single("LINK")
    d = put(root, "winners", s, mp4=False)
    os.symlink(outside, d / s["file"])
    assert s["file"] in ST.read_winner_sub("winners", root)["files"]         # the name is listed …
    assert ST.resolve_winner_video("winners", s["file"], root) is None       # … the bytes are never served


# ── routes ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_four_routes_and_the_gate_in_source():
    paths = {getattr(r, "path", None): set(getattr(r, "methods", set())) for r in API.router.routes}
    assert C.WINNERS_API_PATH in paths and "GET" in paths[C.WINNERS_API_PATH]
    assert {"GET", "HEAD"} <= paths[C.WINNERS_VIDEO_PATH]
    src = (PKG / "api.py").read_text(encoding="utf-8")
    routes = re.findall(r"@router\.(?:get|api_route)\(([^\n]*)\)\s*\nasync def \w+\(([^\n]*)\):", src)
    assert len(routes) == 4
    assert all("email: str = Depends(require_primary_admin)" in r[1] for r in routes)
    fr = [l for l in src.splitlines() if "return FileResponse(" in l]
    assert len(fr) == 2 and all("headers=C.VIDEO_HEADERS" in l for l in fr)


def test_store_source_pins():
    src = (PKG / "store.py").read_text(encoding="utf-8")
    body = src[src.index("def winner_card"):src.index("def _empty_win_counts")]
    assert '"gain_pct"' not in body and "'gain_pct'" not in body
    for w in ('"label"', '"ask"', '"why"', '"category"'):
        assert w not in body, w
    ww = src[src.index("def winner_window_ok"):src.index("def _signed_pct")]
    assert "C.FULL_DAY_WINDOW" in ww and "C.MULTI_WINDOW_PREFIX" in ww and "04:00" not in ww
    assert "os.path.realpath" in src[src.index("def resolve_winner_video"):]


def test_owner_listing(wired):
    r = wired.get(C.WINNERS_API_PATH, headers=OWN)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = _strict(r.text)
    assert body["state"] == "ready" and body["counts"]["videos"] == 7


@pytest.mark.parametrize("method,path", [("GET", C.WINNERS_API_PATH),
                                         ("GET", _wv("winners", "2026-11-12_GP_45x.mp4")),
                                         ("HEAD", _wv("winners", "2026-11-12_GP_45x.mp4")),
                                         ("GET", _wv("multiday", "2026-08-19_BTCT_45x.mp4")),
                                         ("GET", _wv("..", "x.mp4"))])
def test_NEGATIVE_anyone_else_gets_the_stealth_404_and_nothing_is_read(wired, monkeypatch, method, path):
    def _never(*a, **k):
        raise AssertionError("the store was read for a non-owner")
    for fn in ("winners_payload", "resolve_winner_video", "read_winner_sub", "payload", "read_day"):
        monkeypatch.setattr(ST, fn, _never)
    r = wired.request(method, path, headers={"X-User-Email": OTHER})
    assert r.status_code == 404
    if method == "GET":
        assert r.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("path", [C.WINNERS_API_PATH, _wv("winners", "2026-11-12_GP_45x.mp4"),
                                  _wv("multiday", "2026-08-19_BTCT_45x.mp4")])
def test_NEGATIVE_no_header_is_401(wired, path):
    assert wired.get(path).status_code == 401


@pytest.mark.parametrize("path", [
    _wv(DAY, "AKAN_reversal_squeeze_1mpage_24x.mp4"), _wv("phone", "2026-08-19_BTCT_45x.mp4"),
    _wv("_bars", "x.mp4"), _wv("Winners", "2026-11-12_GP_45x.mp4"), _wv("2026-11-17", "x.mp4"),
    f"{C.WINNERS_API_PATH}/video/winners/..%2Fmultiday%2F2026-08-19_BTCT_45x.mp4",
    f"{C.WINNERS_API_PATH}/video/winners%2F..%2Fmultiday/2026-08-19_BTCT_45x.mp4",
    f"{C.WINNERS_API_PATH}/video/multiday/phone%2F2026-08-19_BTCT_45x.mp4",
    _wv("winners", ".hidden.mp4"), _wv("winners", "2026-11-12_GP_45x.json"), _wv("winners", "2026-11-12_GP_45x.MP4"),
    _wv("winners", "x.mp4.json"), _wv("winners", "winners.json"), _wv("multiday", "runners.json"),
    _wv("winners", "2026-08-19_BTCT_45x.mp4"),
])
def test_NEGATIVE_bad_subs_names_and_unlisted_files_are_404(wired, path):
    r = wired.get(path, headers=OWN)
    assert r.status_code == 404
    assert r.content != BLOB


def test_C1_range_206_identity_private_under_the_same_gzip(wired):
    for sub, name in (("winners", "2026-11-12_GP_45x.mp4"), ("multiday", "2026-08-19_BTCT_45x.mp4")):
        r = wired.get(_wv(sub, name), headers={**OWN, "Range": "bytes=0-10239", "Accept-Encoding": "gzip"})
        assert r.status_code == 206
        assert r.headers["content-range"] == "bytes 0-10239/32768" and r.headers["content-length"] == "10240"
        assert r.headers["content-encoding"] == "identity"
        assert "private" in r.headers["cache-control"]
        assert r.content == BLOB[:10240]


def test_head_answers_headers_only(wired):
    r = wired.head(_wv("winners", "2026-11-12_GP_45x.mp4"), headers=OWN)
    assert r.status_code == 200 and r.headers["content-length"] == "32768" and r.content == b""
    assert r.headers["accept-ranges"] == "bytes" and r.headers["content-encoding"] == "identity"


def test_full_get_headers(wired):
    r = wired.get(_wv("multiday", "2026-11-12_GP_45x.mp4"), headers={**OWN, "Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.content == BLOB
    assert r.headers["content-type"] == "video/mp4" and r.headers["cache-control"] == "private, no-transform"
    assert "content-disposition" not in r.headers


def test_NEGATIVE_the_admin_email_is_never_typed_in_the_package():
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    for p in PKG.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert PRIMARY_ADMIN_EMAIL not in src and "ajaykandakatla" not in src, p
