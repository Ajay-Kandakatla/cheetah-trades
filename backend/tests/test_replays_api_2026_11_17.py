"""🎬 Replays — the routes (replays spec §3.1 / §4 WP-BE, 2026-11-17).

Ajay 2026-11-17, verbatim: "Can you store the videos in to the app please".

PRIMARY OWNER ONLY on both routes (`require_primary_admin`, stealth 404; no header → 401, the house shape). The test
app carries the SAME `GZipMiddleware(minimum_size=1024)` main.py ships, and the fixture mp4 is 32,768 bytes so the
Range cases sit ABOVE the gzip floor — a 100-byte partial is never gzipped and would prove nothing (critique C1).

NEGATIVES: anyone else → 404 on both routes and the store is never called; a malformed date → 404; traversal through
the HTTP layer → 404; an existing-but-unlisted mp4 → 404; 416 / 400; and THE TRAP ITSELF — an unprotected
`FileResponse` under the same middleware answers a 10,240-byte Range with `content-encoding: gzip`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient

from chart_maps.replays import api as API
from chart_maps.replays import constants as C


@pytest.fixture(autouse=True)
def _pages_as_of_11_17(monkeypatch):
    """2026-11-18: the 🚩 1-minute page retired (C.EXCLUDED_PAGES); these 11-17 route tests keep their 1-min fixtures
    with the exclusion OFF (the exclusion itself is pinned in test_replays_store_2026_11_17.py)."""
    monkeypatch.setattr(C, "EXCLUDED_PAGES", ())
from chart_maps.replays import store as ST
from tests.test_replays_store_2026_11_17 import (DAY, akan_winner, cenn_carried, pavs_loser, rs_side, write_ledger,
                                                 write_side)

OWNER = "owner@example.com"
OTHER = "doug@example.com"
OWN = {"X-User-Email": OWNER}
BLOB = bytes(range(256)) * 128
NAME = "AKAN_reversal_squeeze_1mpage_24x.mp4"
PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "replays"


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "replays"
    d = r / C.VIDEOS_SUB / DAY
    for s in (akan_winner(), cenn_carried(), pavs_loser(), rs_side("GP", "10:05", 40.0)):
        write_side(d, s)
    (d / NAME).write_bytes(BLOB)
    s = akan_winner()
    s.update(file="OLD_1600_24x.mp4", window="04:00-16:00 ET")
    write_side(d, s)
    (d / "OLD_1600_24x.mp4").write_bytes(BLOB)
    (r / C.VIDEOS_SUB / "jobs.json").write_text("[]")
    write_ledger(r)
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


def _vid(name=NAME, day=DAY):
    return C.API_VIDEO_PATH.format(day=day, name=name)


def test_the_fixture_sits_above_the_gzip_floor():
    assert len(BLOB) == 32768 and len(BLOB) > 10240 >= 1024


def test_paths_are_the_constants():
    assert C.API_PATH == "/chart-maps/replays"
    assert C.API_VIDEO_PATH == "/chart-maps/replays/video/{day}/{name}"
    paths = {getattr(r, "path", None): getattr(r, "methods", set()) for r in API.router.routes}
    assert C.API_PATH in paths and "GET" in paths[C.API_PATH]
    assert {"GET", "HEAD"} <= set(paths[C.API_VIDEO_PATH])


def test_main_mounts_the_router():
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert "from chart_maps.replays.api import router as replays_router" in src
    assert "app.include_router(replays_router)" in src


# ── listing ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_owner_listing(wired):
    r = wired.get(C.API_PATH, headers=OWN)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = _strict(r.text)
    assert body["state"] == "ready" and body["date"] == DAY and body["dates"] == [DAY]
    assert [g["key"] for g in body["groups"]] == ["aplus_winners", "aplus_losers", "rs_potentials"]   # RE-PINNED 2026-11-18: the carried CENN W left "other"
    assert len(body["rs"]["rows"]) == 19
    assert "OLD_1600_24x.mp4" not in r.text and "jobs.json" not in r.text


def test_valid_but_unknown_date_is_empty_and_kept(wired):
    body = _strict(wired.get(C.API_PATH, params={"date": "2026-11-08"}, headers=OWN).text)
    assert body["state"] == "empty" and body["date"] == "2026-11-08" and body["dates"] == [DAY]
    assert body["text"] == C.EMPTY_DAY_TEXT


@pytest.mark.parametrize("bad", ["17-11-2026", "2026-11-17x", "..", "2026-11-17\n", "x"])
def test_NEGATIVE_a_malformed_date_is_404(wired, bad):
    r = wired.get(C.API_PATH, params={"date": bad}, headers=OWN)
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}


def test_no_folder_is_a_sentence_not_a_500(monkeypatch, tmp_path):
    c = TestClient(_app(monkeypatch, tmp_path / "missing"))
    body = _strict(c.get(C.API_PATH, headers=OWN).text)
    assert body["state"] == "no_folder" and body["text"] == C.NO_FOLDER_TEXT


# ── owner-only ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("method,path", [("GET", C.API_PATH), ("GET", C.API_PATH + "?date=2026-11-17"),
                                         ("GET", C.API_PATH + "?date=bad"), ("GET", _vid()), ("HEAD", _vid()),
                                         ("GET", _vid("../x.mp4")), ("GET", _vid(day="..")),
                                         ("GET", _vid("OLD_1600_24x.mp4"))])
def test_NEGATIVE_anyone_else_gets_the_stealth_404_and_nothing_is_read(wired, monkeypatch, method, path):
    def _never(*a, **k):
        raise AssertionError("the store was read for a non-owner")
    monkeypatch.setattr(ST, "payload", _never)
    monkeypatch.setattr(ST, "resolve_video", _never)
    monkeypatch.setattr(ST, "read_day", _never)
    r = wired.request(method, path, headers={"X-User-Email": OTHER})
    assert r.status_code == 404
    if method == "GET":
        assert r.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("path", [C.API_PATH, _vid()])
def test_NEGATIVE_no_header_is_401(wired, path):
    assert wired.get(path).status_code == 401


def test_NEGATIVE_the_admin_email_is_never_typed_in_the_package():
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    assert PRIMARY_ADMIN_EMAIL
    for p in PKG.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert PRIMARY_ADMIN_EMAIL not in src, p
        assert "ajaykandakatla" not in src, p
    api_src = (PKG / "api.py").read_text(encoding="utf-8")
    assert api_src.count("Depends(require_primary_admin)") == 2
    assert "headers=C.VIDEO_HEADERS" in api_src


# ── video bytes ───────────────────────────────────────────────────────────────────────────────────────────────
def test_C1_a_range_above_the_gzip_floor_is_exact_bytes_not_gzip(wired):
    r = wired.get(_vid(), headers={**OWN, "Range": "bytes=0-10239", "Accept-Encoding": "gzip"})
    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 0-10239/32768"
    assert r.headers["content-length"] == "10240"
    assert r.headers["content-encoding"] == "identity"
    assert r.content == BLOB[:10240]


def test_a_small_range_is_the_slice(wired):
    r = wired.get(_vid(), headers={**OWN, "Range": "bytes=100-199", "Accept-Encoding": "gzip"})
    assert r.status_code == 206 and r.headers["content-length"] == "100" and r.content == BLOB[100:200]


def test_an_open_range_is_the_whole_file(wired):
    r = wired.get(_vid(), headers={**OWN, "Range": "bytes=0-", "Accept-Encoding": "gzip"})
    assert r.status_code == 206 and r.content == BLOB
    assert r.headers["content-range"] == "bytes 0-32767/32768"


def test_NEGATIVE_an_unsatisfiable_range_is_416(wired):
    r = wired.get(_vid(), headers={**OWN, "Range": "bytes=40000-"})
    assert r.status_code == 416 and r.headers["content-range"] == "*/32768"


def test_NEGATIVE_a_malformed_range_is_400(wired):
    assert wired.get(_vid(), headers={**OWN, "Range": "bytes=abc"}).status_code == 400


def test_head_answers_headers_only(wired):
    r = wired.head(_vid(), headers=OWN)
    assert r.status_code == 200 and r.headers["content-length"] == "32768" and r.content == b""
    assert r.headers["accept-ranges"] == "bytes"


def test_full_get_headers(wired):
    r = wired.get(_vid(), headers={**OWN, "Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.content == BLOB
    assert r.headers["content-type"] == "video/mp4"
    assert "content-disposition" not in r.headers
    assert r.headers["cache-control"] == "private, no-transform"
    assert r.headers["content-encoding"] == "identity"
    assert r.headers["accept-ranges"] == "bytes"


def test_NEGATIVE_the_trap_itself_an_unprotected_file_response_is_gzipped(tmp_path):
    """If this stops failing, Starlette changed and `identity` is no longer the lever — read it, do not delete it."""
    f = tmp_path / "a.mp4"
    f.write_bytes(BLOB)
    app = FastAPI()
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/bare")
    async def _bare():                                              # noqa: ANN202
        return FileResponse(str(f), media_type="video/mp4")
    c = TestClient(app)
    r = c.get("/bare", headers={"Range": "bytes=0-10239", "Accept-Encoding": "gzip"})
    assert r.status_code == 206
    assert r.headers.get("content-encoding") == "gzip"
    assert r.headers["content-length"] != "10240"
    assert int(r.headers["content-length"]) < 10240                # the wire carries a gzip member, not the slice
    assert r.content == BLOB[:10240]                                # (httpx un-gzips it; a browser's media stack does not)
    # below the floor the same route passes through UNCOMPRESSED — why the C1 case must exceed minimum_size
    s = c.get("/bare", headers={"Range": "bytes=100-199", "Accept-Encoding": "gzip"})
    assert s.status_code == 206 and "content-encoding" not in s.headers and s.content == BLOB[100:200]


@pytest.mark.parametrize("path", [
    f"{C.API_PATH}/video/{DAY}/..%2Fjobs.json",
    f"{C.API_PATH}/video/{DAY}/../../jobs.json",
    f"{C.API_PATH}/video/..%2F..%2Fetc/passwd",
    f"{C.API_PATH}/video/{DAY}//etc/passwd",
    f"{C.API_PATH}/video/2026-11-99/x.mp4",
    f"{C.API_PATH}/video/{DAY}/AKAN_reversal_squeeze_1mpage_24x.json",
    f"{C.API_PATH}/video/{DAY}/OLD_1600_24x.mp4",
    f"{C.API_PATH}/video/{DAY}/akan_reversal_squeeze_1mpage_24x.mp4",
    f"{C.API_PATH}/video/{DAY}/..",
    f"{C.API_PATH}/video/{DAY}%2F..%2F..%2Freplays/{NAME}",
])
def test_NEGATIVE_traversal_and_unlisted_files_are_404(wired, path):
    r = wired.get(path, headers=OWN)
    assert r.status_code == 404
    assert r.content != BLOB and b"[]" != r.content


def test_a_listed_file_is_200_and_the_unlisted_twin_is_404(wired, root):
    assert (root / C.VIDEOS_SUB / DAY / "OLD_1600_24x.mp4").is_file()
    assert wired.get(_vid(), headers=OWN).status_code == 200
    assert wired.get(_vid("OLD_1600_24x.mp4"), headers=OWN).status_code == 404
