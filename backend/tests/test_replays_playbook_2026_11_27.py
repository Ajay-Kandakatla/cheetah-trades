"""📚 Playbook learning — the listing engine + the two owner-only routes (spec playbook videos §3.3-§3.4 / §4.2, 2026-11-27).

Ajay 2026-11-27 ~02:15 ET, verbatim: "I loved the video can you move them under our replay tab with a PLaybook learning
and also add it to the playbook tab too with videos".

The route tests use the app shape of test_replays_api_2026_11_17.py (the SAME `GZipMiddleware(minimum_size=1024)`,
`is_primary_admin` monkeypatched, a 32,768-byte blob so the Range cases sit above the gzip floor) and include
`API.router` — so the `router.include_router(playbook_router)` line in api.py is what is exercised.

NEGATIVES: non-owner 404 with the engine never called · traversal / `%2e%2e` / `%0A` · every refused sidecar · symlinks
(mp4, film folder, `videos/playbook` itself) · the nightly + 🏆 listings never see the film folder and vice versa ·
source pins (two routes, one FileResponse, four own routes in api.py, fullmatch only) · guarded host paths.
"""
from __future__ import annotations

import ast
import copy
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from chart_maps.replays import api as API
from chart_maps.replays import constants as C
from chart_maps.replays import playbook as PB
from chart_maps.replays import store as ST
from tests.test_replays_store_2026_11_17 import DAY, akan_winner, write_side

OWNER = "owner@example.com"
OTHER = "doug@example.com"
OWN = {"X-User-Email": OWNER}
BLOB = bytes(range(256)) * 128
SLUG = "2026-11-27_gg_film"
FILM_TITLE = "Gajjala's Five Setups"
FILM_DESC = "his teaching charts, read bar by bar"
NAME = "00_intro_phone.mp4"
PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "replays"
BAD_WORDS = re.compile(r"bounc|\bedge\b", re.I)
PAP = C.PLAYBOOK_API_PATH


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


# ── fixtures: the §3.1 sidecar, key for key ───────────────────────────────────────────────────────────────────────
def side(file, role="chapter", variant="phone", nn=0, cid="intro", title=FILM_TITLE, subtitle=FILM_DESC,
         duration=438.167, nbytes=len(BLOB), height=720, markers=None, film=None, slug=SLUG):
    return {
        "kind": "playbook", "schema": 1, "file": file,
        "film": film if film is not None else {"slug": slug, "title": FILM_TITLE, "description": FILM_DESC,
                                               "chapters_total": 9},
        "role": role, "variant": variant,
        "chapter": {"nn": nn, "id": cid, "title": title, "subtitle": subtitle} if role == "chapter" else None,
        "markers": markers if role == "full" else None,
        "duration_s": duration, "bytes": nbytes, "width": 1280, "height": height, "soft_subtitles": True,
        "voice": "kokoro am_michael", "description": f"{FILM_TITLE} · {nn:02d} {title}",
        "created_at": "2026-11-27T01:56:51-05:00", "published_at": "2026-11-27T03:30:00-05:00",
        "source": {"name": file, "size": nbytes, "mtime_ns": 1795762611560608987},
    }


def put(film_dir: Path, s: dict, blob: bytes = BLOB, mp4=True, raw=None, name=None):
    film_dir.mkdir(parents=True, exist_ok=True)
    stem = (name or s["file"])[: -len(".mp4")]
    (film_dir / f"{stem}.json").write_text(raw if raw is not None else json.dumps(s), encoding="utf-8")
    if mp4:
        (film_dir / s["file"]).write_bytes(blob)


def fdir(root: Path, slug: str = SLUG) -> Path:
    return root / C.VIDEOS_SUB / C.PLAYBOOK_SUB / slug


def two_chapters(root: Path, slug: str = SLUG):
    d = fdir(root, slug)
    put(d, side("00_intro_phone.mp4", variant="phone", height=720, slug=slug))
    put(d, side("00_intro.mp4", variant="desktop", height=1080, slug=slug))
    put(d, side("01_bull_flag_phone.mp4", variant="phone", nn=1, cid="bull_flag", title="Bull Flag",
                subtitle="the pause after the push", duration=632.667, slug=slug))
    put(d, side("01_bull_flag.mp4", variant="desktop", nn=1, cid="bull_flag", title="Bull Flag",
                subtitle="the pause after the push", duration=632.667, height=1080, slug=slug))
    return d


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "replays"
    (r / C.VIDEOS_SUB).mkdir(parents=True)
    two_chapters(r)
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


def _vid(name=NAME, film=SLUG):
    return C.PLAYBOOK_VIDEO_PATH.format(film=film, name=name)


def _chapter_keys(p):
    return [(f["slug"], c["key"]) for f in p["films"] for c in f["chapters"]]


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_block():
    assert C.PLAYBOOK_SUB == "playbook" and C.PLAYBOOK_KIND == "playbook" and C.PLAYBOOK_SCHEMA == 1
    assert C.PLAYBOOK_API_PATH == "/chart-maps/replays/playbook"
    assert C.PLAYBOOK_VIDEO_PATH == "/chart-maps/replays/playbook/video/{film}/{name}"
    assert C.PLAYBOOK_VARIANT_KEYS == ("phone", "desktop") and C.PLAYBOOK_ROLES == ("chapter", "full")
    assert C.PLAYBOOK_TITLE == "📚 Playbook learning"
    assert C.PLAYBOOK_FULL_SUB_WORDS[0].format(n=1) == "1 chapter"
    assert C.PLAYBOOK_FULL_SUB_WORDS[1].format(n=9) == "9 chapters back to back"


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(k)
            yield from _strings(v)


def test_NEGATIVE_no_b_word_or_edge_in_any_playbook_string():
    names = [n for n in dir(C) if n.startswith("PLAYBOOK_")]
    seen = 0
    for n in names:
        for s in _strings(getattr(C, n)):
            seen += 1
            assert not BAD_WORDS.search(s), (n, s)
    assert seen >= 15


# ── listing ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_listing_ready_with_every_text(root):
    p = PB.payload(root)
    assert p["state"] == "ready" and p["text"] is None and p["title"] == C.PLAYBOOK_TITLE and p["tab"] == C.TAB
    assert p["note"] == C.PLAYBOOK_NOTE
    assert p["counts"] == {"films": 1, "chapters": 2, "videos": 4, "skipped_bad": 0, "no_sidecar": 0}
    assert p["variant_options"] == [{"key": "phone", "label": "📱 phone"}, {"key": "desktop", "label": "🖥 desktop"}]
    (f,) = p["films"]
    assert f["slug"] == SLUG and f["title"] == FILM_TITLE and f["description"] == FILM_DESC
    assert f["summary_text"] == "2 of 9 chapters · 18 min so far"         # 438.167 + 632.667 = 1070.8 s → 18 min
    assert f["full"] is None
    c0, c1 = f["chapters"]
    assert (c0["key"], c0["nn"], c0["nn_text"], c0["id"]) == ("00_intro", 0, "00", "intro")
    assert (c1["key"], c1["nn_text"], c1["title"], c1["subtitle"]) == ("01_bull_flag", "01", "Bull Flag",
                                                                       "the pause after the push")
    assert [v["key"] for v in c0["variants"]] == ["phone", "desktop"]
    v = c0["variants"][0]
    assert v == {"key": "phone", "label": "📱 phone", "file": "00_intro_phone.mp4",
                 "src": "/chart-maps/replays/playbook/video/2026-11-27_gg_film/00_intro_phone.mp4",
                 "duration_s": 438.167, "length_text": "7:18", "bytes": 32768, "size_text": "0 MB",
                 "height": 720, "quality_text": "720p"}
    assert c0["variants"][1]["quality_text"] == "1080p"


@pytest.mark.parametrize("sec,want", [(59.6, "1:00"), (438.167, "7:18"), (3725, "1:02:05"), (0.0, "0:00")])
def test_length_text(sec, want):
    assert PB.length_text(sec) == want


@pytest.mark.parametrize("n,want", [(28_812_421, "29 MB"), (1.4e9, "1.4 GB"), (999_999_999, "1000 MB")])
def test_size_text(n, want):
    assert PB.size_text(n) == want


def test_size_text_through_a_real_sparse_file(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    put(d, side(NAME, nbytes=28_812_421), blob=b"")
    with open(d / NAME, "r+b") as fh:
        fh.truncate(28_812_421)
    v = PB.payload(r)["films"][0]["chapters"][0]["variants"][0]
    assert v["size_text"] == "29 MB" and v["bytes"] == 28_812_421


def test_quality_text_none_without_height(tmp_path):
    r = tmp_path / "replays"
    put(fdir(r), side(NAME, height=None))
    assert PB.payload(r)["films"][0]["chapters"][0]["variants"][0]["quality_text"] is None


def test_ordering_films_desc_chapters_by_nn_id_variants_constant(tmp_path):
    r = tmp_path / "replays"
    for slug in ("2026-10-01_old", "2026-12-01_new"):
        d = fdir(r, slug)
        put(d, side("02_b.mp4", variant="desktop", nn=2, cid="b", slug=slug))
        put(d, side("02_a_phone.mp4", variant="phone", nn=2, cid="a", slug=slug))
        put(d, side("02_a.mp4", variant="desktop", nn=2, cid="a", slug=slug))
        put(d, side("00_intro.mp4", variant="desktop", nn=0, slug=slug))
    p = PB.payload(r)
    assert [f["slug"] for f in p["films"]] == ["2026-12-01_new", "2026-10-01_old"]
    assert [c["key"] for c in p["films"][0]["chapters"]] == ["00_intro", "02_a", "02_b"]
    assert [v["key"] for v in p["films"][0]["chapters"][1]["variants"]] == ["phone", "desktop"]
    assert p["counts"]["films"] == 2 and p["counts"]["chapters"] == 6


def test_summary_all_plural_and_singular(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    film = {"slug": SLUG, "title": FILM_TITLE, "description": FILM_DESC, "chapters_total": 1}
    put(d, side("00_intro.mp4", variant="desktop", film=film, duration=90.0))
    assert PB.payload(r)["films"][0]["summary_text"] == "1 chapter · 2 min"
    film2 = dict(film, chapters_total=2)
    put(d, side("00_intro.mp4", variant="desktop", film=film2, duration=90.0))
    put(d, side("01_bull_flag.mp4", variant="desktop", nn=1, cid="bull_flag", film=film2, duration=90.0))
    assert PB.payload(r)["films"][0]["summary_text"] == "2 chapters · 3 min"


def test_summary_uses_the_first_variant_in_constant_order(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    put(d, side("00_intro_phone.mp4", variant="phone", duration=600.0))
    put(d, side("00_intro.mp4", variant="desktop", duration=6000.0))
    assert PB.payload(r)["films"][0]["summary_text"] == "1 of 9 chapters · 10 min so far"


def test_only_desktop_lists_one_option(tmp_path):
    r = tmp_path / "replays"
    put(fdir(r), side("00_intro.mp4", variant="desktop"))
    assert PB.payload(r)["variant_options"] == [{"key": "desktop", "label": "🖥 desktop"}]


def test_a_new_chapter_pair_is_listed_on_the_next_call(root):
    assert _chapter_keys(PB.payload(root)) == [(SLUG, "00_intro"), (SLUG, "01_bull_flag")]
    d = fdir(root)
    put(d, side("02_kiss_fly_phone.mp4", variant="phone", nn=2, cid="kiss_fly", title="Kiss and Fly"))
    put(d, side("02_kiss_fly.mp4", variant="desktop", nn=2, cid="kiss_fly", title="Kiss and Fly"))
    p = PB.payload(root)
    assert _chapter_keys(p)[-1] == (SLUG, "02_kiss_fly") and p["counts"]["videos"] == 6
    assert PB.resolve_video(SLUG, "02_kiss_fly.mp4", root) is not None


def test_cache_returns_the_same_listing_when_nothing_moved(root):
    a = PB.read_film(SLUG, root)
    assert PB.read_film(SLUG, root) is a


# ── the full film ─────────────────────────────────────────────────────────────────────────────────────────────
def _full(markers, variant="desktop", file=None, duration=5000.0):
    return side(file or ("GG_setups_full.mp4" if variant == "desktop" else "GG_setups_full_phone.mp4"),
                role="full", variant=variant, duration=duration, height=1080, markers=markers)


def test_full_film_markers_sorted_and_a_bad_one_dropped(root):
    marks = [{"start_s": 438.167, "title": "Bull Flag"}, {"start_s": 0.0, "title": FILM_TITLE},
             {"start_s": -1, "title": "neg"}, {"start_s": 9999.0, "title": "past the end"},
             {"start_s": float("nan"), "title": "nan"}, {"start_s": True, "title": "bool"},
             {"start_s": 5.0, "title": ""}, {"start_s": 6.0, "title": "a\nb"}, "junk", {"title": "no start"}]
    put(fdir(root), _full(marks))
    f = PB.payload(root)["films"][0]
    full = f["full"]
    assert full["key"] == "full" and full["title"] == C.PLAYBOOK_FULL_TITLE
    assert full["markers"] == [{"start_s": 0.0, "text": f"0:00 {FILM_TITLE}"}, {"start_s": 438.167, "text": "7:18 Bull Flag"}]
    assert full["subtitle"] == "2 chapters back to back"
    assert [v["key"] for v in full["variants"]] == ["desktop"] and full["variants"][0]["length_text"] == "1:23:20"


@pytest.mark.parametrize("n,want", [(1, "1 chapter"), (9, "9 chapters back to back"), (0, None)])
def test_full_film_subtitle_singular_plural_none(root, n, want):
    marks = [{"start_s": float(i * 100), "title": f"Chapter {i}"} for i in range(n)]
    put(fdir(root), _full(marks))
    assert PB.payload(root)["films"][0]["full"]["subtitle"] == want


def test_full_film_non_list_markers_is_empty(root):
    put(fdir(root), _full("nope"))
    full = PB.payload(root)["films"][0]["full"]
    assert full["markers"] == [] and full["subtitle"] is None


def test_full_film_phone_copy_is_variant_phone_first(root):
    put(fdir(root), _full([{"start_s": 0.0, "title": "A"}], variant="desktop"))
    put(fdir(root), _full([{"start_s": 0.0, "title": "A"}], variant="phone"))
    full = PB.payload(root)["films"][0]["full"]
    assert [v["key"] for v in full["variants"]] == ["phone", "desktop"]
    assert full["variants"][0]["file"] == "GG_setups_full_phone.mp4"


# ── which sidecar names the film (C7) ─────────────────────────────────────────────────────────────────────────
def _film(title, desc, total):
    return {"slug": SLUG, "title": title, "description": desc, "chapters_total": total}


def test_the_first_accepted_sidecar_by_file_name_names_the_film(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    put(d, side("00_intro.mp4", variant="desktop", film=_film("First words", "first desc", 7)))
    put(d, side("01_bull_flag.mp4", variant="desktop", nn=1, cid="bull_flag", film=_film("Second", "second d", 9)))
    f = PB.payload(r)["films"][0]
    assert (f["title"], f["description"]) == ("First words", "first desc")
    assert f["summary_text"] == "2 of 9 chapters · 15 min so far"        # chapters_total = the largest; 2 × 438.167 s


def test_a_refused_first_sidecar_hands_the_name_to_the_next(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    put(d, side("00_intro.mp4", variant="desktop", film=_film("First words", "first desc", 9), nbytes=12))
    put(d, side("01_bull_flag.mp4", variant="desktop", nn=1, cid="bull_flag", film=_film("Second", None, 3)))
    p = PB.payload(r)
    f = p["films"][0]
    assert (f["title"], f["description"]) == ("Second", None)
    assert p["counts"]["skipped_bad"] == 1 and f["summary_text"] == "1 of 3 chapters · 7 min so far"


def test_NEGATIVE_a_duplicate_claim_keeps_the_first_by_file_name(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    put(d, side("00_a.mp4", variant="desktop", title="A"))
    put(d, side("00_b.mp4", variant="desktop", title="B"))
    p = PB.payload(r)
    (c,) = p["films"][0]["chapters"]
    assert c["title"] == "A" and p["counts"]["skipped_bad"] == 1 and p["counts"]["videos"] == 1
    assert PB.resolve_video(SLUG, "00_b.mp4", r) is None


# ── states ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_no_folder_state(tmp_path):
    p = PB.payload(tmp_path / "nope")
    assert p["state"] == "no_folder" and p["text"] == C.NO_FOLDER_TEXT and p["films"] == []


def test_empty_state_without_a_playbook_folder(tmp_path):
    (tmp_path / "r" / C.VIDEOS_SUB).mkdir(parents=True)
    p = PB.payload(tmp_path / "r")
    assert p["state"] == "empty" and p["text"] == C.PLAYBOOK_EMPTY_TEXT and p["films"] == []
    assert p["variant_options"] == []


def test_NEGATIVE_a_film_with_no_accepted_file_is_omitted_but_counted(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    put(d, side(NAME, nbytes=1))
    (d / "loose.mp4").write_bytes(BLOB)
    p = PB.payload(r)
    assert p["state"] == "empty" and p["counts"]["skipped_bad"] == 1 and p["counts"]["no_sidecar"] == 1


# ── the accept rule: NEGATIVES ────────────────────────────────────────────────────────────────────────────────
def _mut(fn):
    s = side(NAME)
    fn(s)
    return s


def _set_film(k, v):
    def f(s):
        s["film"][k] = v
    return f


def _set_ch(k, v):
    def f(s):
        s["chapter"][k] = v
    return f


REFUSED = {
    "kind missing": lambda s: s.pop("kind"),
    "kind other": lambda s: s.update(kind="replay"),
    "schema 2": lambda s: s.update(schema=2),
    "schema true": lambda s: s.update(schema=True),
    "window key": lambda s: s.update(window=C.FULL_DAY_WINDOW),
    "window key null": lambda s: s.update(window=None),
    "film slug other": _set_film("slug", "other_film"),
    "film not dict": lambda s: s.update(film="x"),
    "film title empty": _set_film("title", ""),
    "film title 121": _set_film("title", "x" * 121),
    "film desc 301": _set_film("description", "x" * 301),
    "chapters_total 0": _set_film("chapters_total", 0),
    "chapters_total bool": _set_film("chapters_total", True),
    "bytes != size": lambda s: s.update(bytes=len(BLOB) + 1),
    "bytes bool": lambda s: s.update(bytes=True),
    "bytes zero": lambda s: s.update(bytes=0),
    "bytes str": lambda s: s.update(bytes=str(len(BLOB))),
    "duration 0": lambda s: s.update(duration_s=0),
    "duration nan": lambda s: s.update(duration_s=float("nan")),
    "duration inf": lambda s: s.update(duration_s=float("inf")),
    "duration bool": lambda s: s.update(duration_s=True),
    "duration str": lambda s: s.update(duration_s="438"),
    "height 0": lambda s: s.update(height=0),
    "role other": lambda s: s.update(role="trailer"),
    "role list": lambda s: s.update(role=["chapter"]),
    "variant other": lambda s: s.update(variant="tablet"),
    "nn -1": _set_ch("nn", -1),
    "nn 100": _set_ch("nn", 100),
    "nn true": _set_ch("nn", True),
    "nn str": _set_ch("nn", "1"),
    "id dash": _set_ch("id", "bull-flag"),
    "id upper": _set_ch("id", "Bull_flag"),
    "id newline": _set_ch("id", "intro\n"),
    "title empty": _set_ch("title", ""),
    "title blank": _set_ch("title", "   "),
    "title newline": _set_ch("title", "Bull\nFlag"),
    "title 121": _set_ch("title", "x" * 121),
    "title not str": _set_ch("title", 5),
    "subtitle 201": _set_ch("subtitle", "x" * 201),
    "subtitle tab": _set_ch("subtitle", "a\tb"),
    "chapter missing": lambda s: s.update(chapter=None),
}


@pytest.mark.parametrize("why", sorted(REFUSED))
def test_NEGATIVE_each_bad_sidecar_is_refused(tmp_path, why):
    r = tmp_path / "replays"
    put(fdir(r), _mut(REFUSED[why]))
    p = PB.payload(r)
    assert p["state"] == "empty" and p["films"] == [], why
    assert p["counts"]["skipped_bad"] == 1, why
    assert PB.resolve_video(SLUG, NAME, r) is None, why


def test_NEGATIVE_file_not_the_stem_is_refused(tmp_path):
    r = tmp_path / "replays"
    d = fdir(r)
    put(d, side("00_other.mp4"), name=NAME)              # 00_intro_phone.json says file 00_other.mp4 (both mp4s exist)
    (d / NAME).write_bytes(BLOB)
    p = PB.payload(r)
    assert p["state"] == "empty" and p["counts"]["skipped_bad"] == 1
    assert PB.resolve_video(SLUG, NAME, r) is None and PB.resolve_video(SLUG, "00_other.mp4", r) is None


@pytest.mark.parametrize("raw", ["[1, 2]", "{not json", '"a string"', "null"])
def test_NEGATIVE_non_dict_or_invalid_json_is_refused(tmp_path, raw):
    r = tmp_path / "replays"
    put(fdir(r), side(NAME), raw=raw)
    p = PB.payload(r)
    assert p["state"] == "empty" and p["counts"]["skipped_bad"] == 1


def test_the_title_bounds_are_inclusive(tmp_path):
    r = tmp_path / "replays"
    s = side(NAME, title="x" * C.PLAYBOOK_TITLE_MAX, subtitle="y" * C.PLAYBOOK_SUBTITLE_MAX)
    s["film"]["description"] = "z" * C.PLAYBOOK_DESCRIPTION_MAX
    put(fdir(r), s)
    assert PB.payload(r)["counts"]["videos"] == 1


def test_NEGATIVE_mp4_without_sidecar_and_sidecar_without_mp4(root):
    d = fdir(root)
    (d / "03_loose.mp4").write_bytes(BLOB)
    put(d, side("04_inflight.mp4", nn=4, cid="inflight"), mp4=False)
    (d / "05_x.mp4.123.part").write_bytes(BLOB)
    (d / "05_x.json.123.part").write_text(json.dumps(side("05_x.mp4", nn=5, cid="x")))
    p = PB.payload(root)
    assert p["counts"] == {"films": 1, "chapters": 2, "videos": 4, "skipped_bad": 1, "no_sidecar": 1}
    for n in ("03_loose.mp4", "04_inflight.mp4", "05_x.mp4", "05_x.mp4.123.part"):
        assert PB.resolve_video(SLUG, n, root) is None, n


# ── symlinks and folder names ─────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_symlinked_mp4_pointing_outside_is_refused(root, tmp_path):
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(BLOB)
    d = fdir(root)
    put(d, side("07_link.mp4", nn=7, cid="link"), mp4=False)
    os.symlink(outside, d / "07_link.mp4")
    p = PB.payload(root)
    assert "07_link" not in json.dumps(p) and p["counts"]["skipped_bad"] == 1
    assert PB.resolve_video(SLUG, "07_link.mp4", root) is None


def test_NEGATIVE_a_symlinked_mp4_pointing_inside_the_film_is_refused(root):
    """The realpath guard would let this one through (it stays inside the film folder) — only the lstat check stops it."""
    d = fdir(root)
    put(d, side("08_alias.mp4", nn=8, cid="alias"), mp4=False)
    os.symlink(d / "00_intro.mp4", d / "08_alias.mp4")
    p = PB.payload(root)
    assert "08_alias" not in json.dumps(p) and p["counts"]["skipped_bad"] == 1
    assert PB.resolve_video(SLUG, "08_alias.mp4", root) is None


def test_NEGATIVE_symlinked_hidden_and_dotted_film_folders_are_ignored(root, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    two_chapters(elsewhere, "linked_film")
    os.symlink(fdir(elsewhere, "linked_film"), fdir(root, "linked_film"))
    for bad in (".hidden", "a.b"):
        two_chapters(root, bad)
    assert PB.film_slugs(root) == [SLUG]
    assert [f["slug"] for f in PB.payload(root)["films"]] == [SLUG]
    for film in ("linked_film", ".hidden", "a.b"):
        assert PB.resolve_video(film, NAME, root) is None, film


def test_NEGATIVE_videos_playbook_itself_a_symlink_lists_nothing(tmp_path, monkeypatch):
    r = tmp_path / "replays"
    (r / C.VIDEOS_SUB).mkdir(parents=True)
    real_pb = tmp_path / "outside_pb" / "pb"
    put(real_pb / SLUG, side(NAME))
    os.symlink(real_pb, r / C.VIDEOS_SUB / C.PLAYBOOK_SUB)
    p = PB.payload(r)
    assert p["state"] == "empty" and p["films"] == []
    assert PB.resolve_video(SLUG, NAME, r) is None
    # the realpath base is the SECOND guard: with the lstat guard mutated away the film lists, the bytes still never do
    monkeypatch.setattr(PB, "_real_dir", lambda _p: True)
    assert PB.film_slugs(r) == [SLUG] and PB.payload(r)["state"] == "ready"
    assert PB.resolve_video(SLUG, NAME, r) is None


def test_NEGATIVE_videos_playbook_a_regular_file_is_empty(tmp_path):
    r = tmp_path / "replays"
    (r / C.VIDEOS_SUB).mkdir(parents=True)
    (r / C.VIDEOS_SUB / C.PLAYBOOK_SUB).write_text("not a folder")
    p = PB.payload(r)
    assert p["state"] == "empty" and p["films"] == []
    assert PB.film_slugs(r) == [] and PB.resolve_video(SLUG, NAME, r) is None


# ── fullmatch only (C5) ───────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_trailing_newline_is_never_a_slug_or_a_name(root):
    assert PB.is_slug(SLUG) is True
    assert PB.is_slug(SLUG + "\n") is False
    assert PB.resolve_video(SLUG + "\n", NAME, root) is None
    assert PB.resolve_video(SLUG, NAME + "\n", root) is None
    assert PB.resolve_video(SLUG, NAME, root) is not None


@pytest.mark.parametrize("x", ["", "..", ".", "a.b", "a/b", "../x", "-a", "_a", "x" * 65, None, 5, ["a"]])
def test_NEGATIVE_is_slug(x):
    assert PB.is_slug(x) is False


def test_is_slug_bounds():
    assert PB.is_slug("x" * 64) and PB.is_slug("2026-11-17") and PB.is_slug("A_b-9")


# ── routes ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_router_carries_both_playbook_paths():
    paths = {getattr(r, "path", None): set(getattr(r, "methods", set())) for r in API.router.routes}
    assert "GET" in paths[C.PLAYBOOK_API_PATH]
    assert {"GET", "HEAD"} <= paths[C.PLAYBOOK_VIDEO_PATH]


def test_owner_listing_is_strict_json_and_no_store(wired, root):
    s = side("GG_setups_full.mp4", role="full", variant="desktop", duration=float("nan"))
    put(fdir(root), s)                              # a NaN duration is refused, never served
    r = wired.get(PAP, headers=OWN)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = _strict(r.text)
    assert body["state"] == "ready" and body["counts"]["skipped_bad"] == 1 and body["counts"]["videos"] == 4


def test_full_get_headers(wired):
    r = wired.get(_vid(), headers={**OWN, "Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.content == BLOB
    assert r.headers["content-type"] == "video/mp4"
    assert "content-disposition" not in r.headers
    assert r.headers["cache-control"] == "private, no-transform"
    assert r.headers["content-encoding"] == "identity"
    assert r.headers["accept-ranges"] == "bytes"


def test_a_range_above_the_gzip_floor_is_exact_bytes(wired):
    assert len(BLOB) == 32768
    r = wired.get(_vid(), headers={**OWN, "Range": "bytes=0-10239", "Accept-Encoding": "gzip"})
    assert r.status_code == 206 and r.headers["content-range"] == "bytes 0-10239/32768"
    assert r.headers["content-length"] == "10240" and r.headers["content-encoding"] == "identity"
    assert r.content == BLOB[:10240]


def test_an_open_range_and_head(wired):
    r = wired.get(_vid(), headers={**OWN, "Range": "bytes=0-", "Accept-Encoding": "gzip"})
    assert r.status_code == 206 and r.content == BLOB
    h = wired.head(_vid(), headers=OWN)
    assert h.status_code == 200 and h.headers["content-length"] == "32768" and h.content == b""


def test_NEGATIVE_416_and_400(wired):
    r = wired.get(_vid(), headers={**OWN, "Range": "bytes=40000-"})
    assert r.status_code == 416
    assert wired.get(_vid(), headers={**OWN, "Range": "bytes=abc"}).status_code == 400


def test_every_listed_src_resolves_through_the_route(wired):
    body = _strict(wired.get(PAP, headers=OWN).text)
    srcs = [v["src"] for f in body["films"] for c in f["chapters"] for v in c["variants"]]
    assert len(srcs) == 4
    for s in srcs:
        assert wired.get(s, headers={**OWN, "Range": "bytes=0-9"}).status_code == 206, s


def _engine_must_not_run(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the engine ran for a non-owner")
    for n in ("payload", "resolve_video", "read_film"):
        monkeypatch.setattr(PB, n, boom)


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_NEGATIVE_non_owner_is_404_and_the_engine_never_runs(wired, monkeypatch, method):
    _engine_must_not_run(monkeypatch)
    hdr = {"X-User-Email": OTHER}
    assert wired.get(PAP, headers=hdr).status_code == 404
    r = wired.request(method, _vid(), headers=hdr)
    assert r.status_code == 404 and r.content != BLOB


@pytest.mark.parametrize("path", [PAP, _vid()])
def test_NEGATIVE_no_header_is_401(wired, path):
    assert wired.get(path).status_code == 401


@pytest.fixture()
def traps(root):
    """Real files behind every traversal attempt, so a 404 proves the guard and not a missing file."""
    nightly = root / C.VIDEOS_SUB / DAY
    write_side(nightly, akan_winner())
    (nightly / NAME).write_bytes(BLOB)
    put(root / C.VIDEOS_SUB / C.PLAYBOOK_SUB / "a.b", side(NAME, slug="a.b"))
    (fdir(root) / "09_unlisted.mp4").write_bytes(BLOB)
    (root / C.VIDEOS_SUB / "secret.mp4").write_bytes(BLOB)
    return root


@pytest.mark.parametrize("path", [
    f"{PAP}/video/{SLUG}/..%2F00_intro.json",
    f"{PAP}/video/{SLUG}/../../secret.mp4",
    f"{PAP}/video/%2e%2e/{NAME}",
    f"{PAP}/video/%2e%2e/secret.mp4",
    f"{PAP}/video/{SLUG}//etc/passwd",
    f"{PAP}/video/../{NAME}",
    f"{PAP}/video/a.b/{NAME}",
    f"{PAP}/video/{DAY}/{NAME}",
    f"{PAP}/video/{SLUG}/00_intro_phone.json",
    f"{PAP}/video/{SLUG}/00_INTRO_PHONE.mp4",
    f"{PAP}/video/{SLUG}/09_unlisted.mp4",
    f"{PAP}/video/{SLUG}%2F..%2F{SLUG}/{NAME}",
    f"{PAP}/video/{SLUG}%0A/{NAME}",
    f"{PAP}/video/{SLUG}/{NAME}%0A",
])
def test_NEGATIVE_traversal_is_404_never_the_bytes(wired, traps, path):
    r = wired.get(path, headers=OWN)
    assert r.status_code == 404, (path, r.status_code)
    assert r.content != BLOB


# ── ISOLATION ─────────────────────────────────────────────────────────────────────────────────────────────────
def _nightly(r):
    return [ST.payload(root=r), ST.payload(DAY, root=r), ST.dates(r), ST.winners_payload(r)]


def test_ISOLATION_the_nightly_and_winner_lists_never_see_the_film_folder(tmp_path):
    r = tmp_path / "rp"
    write_side(r / C.VIDEOS_SUB / DAY, akan_winner())
    (r / C.VIDEOS_SUB / "winners").mkdir(parents=True)
    before = copy.deepcopy(_nightly(r))
    two_chapters(r)
    put(fdir(r), _full([{"start_s": 0.0, "title": "A"}]))
    after = _nightly(r)
    assert after == before
    for x in after:
        assert C.PLAYBOOK_SUB not in json.dumps(x, default=str)
    assert PB.payload(r)["counts"]["videos"] == 5


def test_ISOLATION_a_playbook_pair_misplaced_in_a_date_or_winners_folder_is_never_listed(tmp_path):
    r = tmp_path / "rp"
    day = r / C.VIDEOS_SUB / DAY
    write_side(day, akan_winner())
    base = ST.read_day(DAY, r)["counts"]["skipped_window"]
    put(day, side(NAME))
    lst = ST.read_day(DAY, r)
    assert NAME not in lst["files"] and lst["counts"]["skipped_window"] == base + 1
    assert ST.resolve_video(DAY, NAME, r) is None
    win = r / C.VIDEOS_SUB / "winners"
    put(win, side(NAME))
    assert NAME not in json.dumps(ST.winners_payload(r))
    assert ST.resolve_winner_video("winners", NAME, r) is None
    put(fdir(r), side(NAME))
    assert ST.resolve_video(C.PLAYBOOK_SUB, NAME, r) is None
    assert ST.read_day(C.PLAYBOOK_SUB, r)["videos"] == []
    assert PB.resolve_video(SLUG, NAME, r) is not None


def test_ISOLATION_a_nightly_sidecar_in_a_film_folder_is_refused(tmp_path):
    r = tmp_path / "rp"
    a = akan_winner()
    write_side(fdir(r), a)
    p = PB.payload(r)
    assert p["state"] == "empty" and p["counts"]["skipped_bad"] == 1
    assert PB.resolve_video(SLUG, a["file"], r) is None


def test_ISOLATION_a_nightly_sidecar_in_a_film_folder_is_404(wired, root):
    a = akan_winner()
    write_side(fdir(root), a)
    assert wired.get(_vid(a["file"]), headers=OWN).status_code == 404


# ── source pins ───────────────────────────────────────────────────────────────────────────────────────────────
ROUTE_RE = r"@router\.(?:get|api_route)\(([^\n]*)\)\s*\nasync def \w+\(([^\n]*)\):"


def test_source_pins_two_routes_one_file_response():
    src = (PKG / "playbook_api.py").read_text(encoding="utf-8")
    routes = re.findall(ROUTE_RE, src)
    assert len(routes) == 2
    assert all("email: str = Depends(require_primary_admin)" in r[1] for r in routes)
    assert re.search(r"^from ollama_chat\.api import require_primary_admin$", src, re.M)
    fr = [ln for ln in src.splitlines() if "return FileResponse(" in ln]
    assert len(fr) == 1 and "headers=C.VIDEO_HEADERS" in fr[0]


def test_source_pins_api_keeps_four_own_routes_and_includes_the_playbook_router():
    src = (PKG / "api.py").read_text(encoding="utf-8")
    assert len(re.findall(ROUTE_RE, src)) == 4
    assert "router.include_router(playbook_router)" in src
    assert "from .playbook_api import router as playbook_router" in src


def test_NEGATIVE_fullmatch_only_and_no_admin_email_in_the_new_modules():
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    for n in ("playbook.py", "playbook_api.py"):
        src = (PKG / n).read_text(encoding="utf-8")
        assert ".match(" not in src and "re.search(" not in src, n
        assert PRIMARY_ADMIN_EMAIL not in src and "ajaykandakatla" not in src, n
    pb = (PKG / "playbook.py").read_text(encoding="utf-8")
    assert "body.get(\"kind\") != C.PLAYBOOK_KIND" in pb and '"window" in body' in pb
    assert "except C.CARD_ERRORS:" in pb and "nb != st.st_size" in pb
    assert "os.lstat(" in pb and "stat.S_ISDIR(" in pb and "stat.S_ISREG(" in pb


# ── guarded host paths (C6) ───────────────────────────────────────────────────────────────────────────────────
def _host(*parts) -> Path:
    """A file under the host's eod-audits/. Skips in the container (/app/tests/x.py has three parents) and when absent."""
    here = Path(__file__).resolve()
    if len(here.parents) <= 3:
        pytest.skip("not on the host tree (no eod-audits beside the repo)")
    p = here.parents[3].joinpath("eod-audits", *parts)
    if not p.is_file():
        pytest.skip(f"{p} not on this host")
    return p


def _repo(*parts) -> Path:
    """A file in this repo (frontend/…). Skips when the tree is too shallow or the file is absent."""
    here = Path(__file__).resolve()
    if len(here.parents) <= 2:
        pytest.skip("not in the repo tree")
    p = here.parents[2].joinpath(*parts)
    if not p.is_file():
        pytest.skip(f"{p} not in this tree")
    return p


def _publisher() -> Path:
    return _host("research", "2026-11-27_gg_film", "engine", "publish.py")


FIXTURE_PARTS = ("frontend", "src", "components", "__fixtures__", "playbook_videos_2026_11_27.json")


@pytest.mark.parametrize("fake", ["/app/tests/x.py", "/x.py", "/a/x.py"])
def test_NEGATIVE_the_host_helpers_skip_never_index_error(monkeypatch, fake):
    monkeypatch.setitem(globals(), "__file__", fake)
    with pytest.raises(pytest.skip.Exception):
        _host("research", "2026-11-27_gg_film", "engine", "publish.py")
    with pytest.raises(pytest.skip.Exception):
        _repo(*FIXTURE_PARTS)


def _consts(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name):
                try:
                    out[t.id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
            elif isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for n, v in zip(t.elts, node.value.elts):
                    if isinstance(n, ast.Name):
                        try:
                            out[n.id] = ast.literal_eval(v)
                        except ValueError:
                            pass
    return out


def test_the_publisher_constants_equal_ours():
    p = _publisher()
    k = _consts(p)
    assert k["KIND"] == C.PLAYBOOK_KIND and k["SCHEMA"] == C.PLAYBOOK_SCHEMA and k["DEST_SUB"] == C.PLAYBOOK_SUB
    assert tuple(k["ROLES"]) == C.PLAYBOOK_ROLES and tuple(k["VARIANTS"]) == C.PLAYBOOK_VARIANT_KEYS
    assert k["FILE_RE"] == C.FILE_RE.pattern
    assert k["SLUG_RE"] == C.PLAYBOOK_SLUG_RE.pattern
    assert k["CHAPTER_ID_RE"] == C.PLAYBOOK_CHAPTER_ID_RE.pattern
    assert k["NN_MAX"] == C.PLAYBOOK_NN_MAX
    assert (k["TITLE_MAX"], k["SUBTITLE_MAX"], k["DESCRIPTION_MAX"]) == (
        C.PLAYBOOK_TITLE_MAX, C.PLAYBOOK_SUBTITLE_MAX, C.PLAYBOOK_DESCRIPTION_MAX)
    assert isinstance(k["POLL_SECONDS"], int) and not isinstance(k["POLL_SECONDS"], bool) and k["POLL_SECONDS"] >= 60
    src = p.read_text(encoding="utf-8")
    assert ".match(" not in src and "re.search(" not in src


FAKE_PROBE = """#!/bin/sh
cat <<'EOF'
{"format": {"duration": "438.166667", "size": "32768"},
 "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720},
             {"codec_type": "audio", "codec_name": "aac"},
             {"codec_type": "subtitle", "codec_name": "mov_text"}],
 "chapters": []}
EOF
"""


def _film_folder(tmp_path: Path) -> Path:
    film = tmp_path / SLUG
    (film / "chapters").mkdir(parents=True)
    (film / "out").mkdir()
    for cid, nn, title, sub in (("intro", 0, FILM_TITLE, FILM_DESC), ("bull_flag", 1, "Bull Flag", "the pause")):
        (film / "chapters" / f"{cid}.json").write_text(json.dumps(
            {"id": cid, "nn": nn, "title": title, "subtitle": sub, "music": {"mood": "bright"}, "beats": []}))
    for n in ("00_intro.mp4", "00_intro_phone.mp4", "01_bull_flag.mp4"):
        (film / "out" / n).write_bytes(BLOB)
    return film


def test_end_to_end_the_real_publisher_feeds_the_listing(tmp_path):
    pub = _publisher()
    film = _film_folder(tmp_path)
    probe = tmp_path / "ffprobe"
    probe.write_text(FAKE_PROBE)
    probe.chmod(probe.stat().st_mode | stat.S_IEXEC)
    r = tmp_path / "replays"
    (r / C.VIDEOS_SUB).mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    run = subprocess.run([sys.executable, str(pub), "--film-root", str(film), "--videos-root", str(r / C.VIDEOS_SUB),
                          "--ffprobe", str(probe)], capture_output=True, text=True, env=env, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    p = PB.payload(r)
    assert p["counts"]["skipped_bad"] == 0 and p["state"] == "ready"
    f = p["films"][0]
    assert f["slug"] == SLUG and [c["key"] for c in f["chapters"]] == ["00_intro", "01_bull_flag"]
    assert [v["key"] for v in f["chapters"][0]["variants"]] == ["phone", "desktop"]
    for c in f["chapters"]:
        for v in c["variants"]:
            film_seg, name = v["src"].split("/")[-2:]
            assert PB.resolve_video(film_seg, name, r) is not None, v["src"]
    assert "window" not in json.dumps(p)


def _keyset(d):
    return set(d) if isinstance(d, dict) else set()


def test_the_frontend_fixture_keys_equal_the_served_keys(root):
    fx = json.loads(_repo(*FIXTURE_PARTS).read_text(encoding="utf-8"))
    put(fdir(root), _full([{"start_s": 0.0, "title": "A"}, {"start_s": 60.0, "title": "B"}]))
    real = PB.payload(root)
    ready = fx["ready"]
    rf, ff = real["films"][0], ready["films"][0]
    assert _keyset(ff) == _keyset(rf), "film"
    assert _keyset(ff["chapters"][0]) == _keyset(rf["chapters"][0]), "chapter"
    assert _keyset(ff["chapters"][0]["variants"][0]) == _keyset(rf["chapters"][0]["variants"][0]), "variant"
    assert _keyset(ff["full"]) == _keyset(rf["full"]), "full"
    assert _keyset(ff["full"]["markers"][0]) == _keyset(rf["full"]["markers"][0]), "marker"
