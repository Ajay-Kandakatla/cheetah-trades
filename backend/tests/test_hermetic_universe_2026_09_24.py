"""The suite resolves its index lists from a committed snapshot, never live.

On the afternoon of 2026-09-24 five tests went red on a clean origin/main with
no code change: every file in the host's ~/.cheetah/universe had been written
2026-08-25 15:30:02, the 30-day TTL lapsed at 15:30, and the suite began
resolving the index lists over the network. With no lxml in the host venv the
Russell 3000 fell to the curated + sp500 + sp400 fallback (1,020 names, the
wrong universe) while the datahub CSV quietly rewrote the host's sp500 cache.
tests/conftest.py now pins all of it; these tests pin the pins.

Every negative here drives the REAL `sepa.universe` fetch ladder. Only the
iShares xls parser is stubbed, because its lxml dependency is exactly the
thing that differs between the host venv and the api container.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from pathlib import Path

import pytest

import tests.conftest as C
from sepa import universe as U

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "universe"
MANIFEST = json.loads((SNAPSHOT / "MANIFEST.json").read_text())
BACKEND = Path(__file__).resolve().parents[1]

# Evaluated at COLLECTION, before any fixture runs — the moment
# test_cloud_infra_theme.py resolves load_universe("full").
_DIR_AT_COLLECTION = U.UNIV_CACHE_DIR
try:
    import pymongo
    pymongo.MongoClient("mongodb://mongo:27017")
    _MONGO_AT_COLLECTION = "constructed a real client"
except RuntimeError as _exc:
    _MONGO_AT_COLLECTION = str(_exc)


def _snapshot(name: str) -> list[str]:
    return [ln.strip().upper() for ln in (SNAPSHOT / f"{name}.txt").read_text().splitlines()
            if ln.strip()]


def _expire(name: str) -> None:
    """Age one list in the session copy past its TTL — the 2026-09-24 state.
    The autouse fixture re-seeds the copy after the test."""
    old = time.time() - U.UNIV_CACHE_TTL_SEC - 60
    os.utime(U._cache_path(name), (old, old))


def _lxml_missing(path, *, source_label):
    raise ModuleNotFoundError("No module named 'lxml'")


@pytest.fixture(autouse=True)
def _refuse_to_run_against_a_real_cache():
    """Several tests below age or rewrite cache files. Without the redirect
    they would do it to ~/.cheetah/universe — which is exactly what a mutation
    run with the redirect removed did on 2026-09-24. Fail first instead."""
    if U.UNIV_CACHE_DIR != C.HERMETIC_UNIVERSE_DIR:
        pytest.fail("sepa.universe.UNIV_CACHE_DIR is %s, not the session copy — "
                    "refusing to touch a real cache" % U.UNIV_CACHE_DIR, pytrace=False)


# ---------------------------------------------------------------------------
# where the lists come from
# ---------------------------------------------------------------------------
def test_the_cache_under_test_is_the_session_copy_never_the_hosts():
    home = Path.home() / ".cheetah" / "universe"
    assert U.UNIV_CACHE_DIR == C.HERMETIC_UNIVERSE_DIR
    assert U.UNIV_CACHE_DIR != home
    assert U._cache_path("russell3000").parent == C.HERMETIC_UNIVERSE_DIR


def test_the_redirect_is_already_in_place_at_collection():
    """A fixture would be too late: module-level code in a test file runs at
    collection. This module's own module-level read proves the order."""
    assert _DIR_AT_COLLECTION == C.HERMETIC_UNIVERSE_DIR


def test_NEGATIVE_mongo_is_refused_at_collection_too():
    """The Mongo guard used to be installed by a session fixture, so the
    module-level load_universe("full") in test_cloud_infra_theme.py built a
    real client to mongodb://mongo:27017 during collection."""
    assert "disabled during tests" in _MONGO_AT_COLLECTION


@pytest.mark.parametrize("name,fetch", [
    ("sp500", lambda: U.fetch_sp500()),
    ("sp400", lambda: U.fetch_sp400()),
    ("sp600", lambda: U.fetch_sp600()),
    ("nasdaq100", lambda: U.fetch_nasdaq100()),
    ("russell1000", lambda: U.fetch_russell1000()),
    ("russell3000", lambda: U.fetch_russell3000()),
    ("microcap", lambda: U.fetch_microcap()),
])
def test_every_snapshot_list_is_served_from_the_cache_exactly(name, fetch):
    assert fetch() == _snapshot(name)
    if name != "microcap":                    # fetch_microcap records no provenance
        assert U.last_source(name)["source"] == "cache"


def test_full_is_built_from_the_snapshot_and_nothing_else():
    """The real `full` alias over the snapshot: every index layer present."""
    full = set(U.load_universe("full"))
    for name in ("russell3000", "sp500", "sp400", "sp600"):
        # through the same rename/delisting map load_universe applies
        missing = set(U._resolve_fates(_snapshot(name))) - full
        assert not missing, "%s names missing from full: %s" % (name, sorted(missing)[:10])
    assert U.last_source("russell3000")["source"] == "cache"
    assert U.LAST_COUNTS["russell3000"]["ok"] is True
    assert U.LAST_COUNTS["sp1500"]["ok"] is True


def test_an_old_committed_snapshot_is_still_served_fresh(tmp_path, monkeypatch):
    """The TTL is measured from the copy's stamp, not the committed file's
    mtime — so no run can ever start on an expired snapshot."""
    src, dst = tmp_path / "committed", tmp_path / "session"
    src.mkdir()
    dst.mkdir()
    committed = src / "russell3000.txt"
    committed.write_text("AAA\nBBB\n")
    two_years = time.time() - 2 * 365 * 86400
    os.utime(committed, (two_years, two_years))
    monkeypatch.setattr(C, "UNIVERSE_SNAPSHOT_DIR", src)
    monkeypatch.setattr(C, "HERMETIC_UNIVERSE_DIR", dst)
    monkeypatch.setattr(U, "UNIV_CACHE_DIR", dst)
    C._seed_universe_cache()
    assert U._read_cached("russell3000") == ["AAA", "BBB"]


def test_NEGATIVE_the_ttl_is_real_so_the_stamp_is_what_keeps_runs_hermetic():
    _expire("russell3000")
    assert U._read_cached("russell3000") is None


# ---------------------------------------------------------------------------
# the snapshot is what it says it is
# ---------------------------------------------------------------------------
def test_the_snapshot_matches_its_manifest():
    on_disk = {p.stem for p in SNAPSHOT.glob("*.txt")}
    assert on_disk == set(MANIFEST["lists"]), "a list was added or removed without the manifest"
    for name, rec in MANIFEST["lists"].items():
        body = (SNAPSHOT / f"{name}.txt").read_bytes()
        assert hashlib.sha256(body).hexdigest() == rec["sha256"], (
            "%s.txt was edited by hand — regenerate it (see %s)" % (name, MANIFEST["regenerate"]))
        assert len(_snapshot(name)) == rec["count"]


def test_NEGATIVE_every_snapshot_list_sits_inside_its_own_size_band():
    """A truncated snapshot would shrink the universe under test silently —
    the same failure the production size bands exist to catch."""
    for name in MANIFEST["lists"]:
        lo, hi = U._EXPECTED_COUNTS.get(name, (1, 10**9))
        n = len(_snapshot(name))
        assert lo <= n <= hi, "%s snapshot has %d names, outside %d-%d" % (name, n, lo, hi)


def test_the_russell_snapshot_is_the_committed_ishares_export():
    """The Russell lists are the parse of the xls files in sepa/data. When a
    fresh export is dropped in, the snapshot is stale and must be regenerated
    in the same change — otherwise the tests keep asserting against the
    PREVIOUS quarter's membership."""
    on_disk = {str(p.relative_to(BACKEND)) for p in (BACKEND / "sepa" / "data").glob("iShares-*.xls")}
    pinned = {rec["file"] for rec in MANIFEST["ishares_exports"].values()}
    assert on_disk == pinned, (
        "iShares exports on disk %s != snapshotted %s — regenerate "
        "tests/fixtures/universe/ (see %s)" % (sorted(on_disk), sorted(pinned),
                                               MANIFEST["regenerate"]))
    for name, rec in MANIFEST["ishares_exports"].items():
        actual = hashlib.sha256((BACKEND / rec["file"]).read_bytes()).hexdigest()
        assert actual == rec["sha256"], (
            "%s changed since the test snapshot was taken — regenerate "
            "tests/fixtures/universe/ (see %s)" % (rec["file"], MANIFEST["regenerate"]))


# ---------------------------------------------------------------------------
# no live network
# ---------------------------------------------------------------------------
def test_NEGATIVE_live_network_is_refused_and_recorded(blocked_network_attempts):
    import requests
    from curl_cffi import requests as curl_requests

    with pytest.raises(C.LiveNetworkBlocked):
        socket.getaddrinfo("en.wikipedia.org", 443)
    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(C.LiveNetworkBlocked):
            raw.connect(("93.184.216.34", 443))       # a literal IP skips DNS
    finally:
        raw.close()
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://www.ishares.com/us/products/239714/", timeout=1)
    with pytest.raises(OSError):              # libcurl never touches Python sockets
        curl_requests.get("https://api.stocktwits.com/api/2/streams/symbol/NVDA.json")

    seen = blocked_network_attempts()
    assert "dns en.wikipedia.org" in seen
    assert "connect 93.184.216.34:443" in seen
    assert "dns www.ishares.com" in seen
    assert "curl api.stocktwits.com" in seen
    assert issubclass(C.LiveNetworkBlocked, OSError)


def test_loopback_still_works():
    """The guard must not break in-process servers or local sockets."""
    assert socket.getaddrinfo("localhost", 80)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        cli = socket.create_connection(srv.getsockname(), timeout=2)
        cli.close()
    finally:
        srv.close()


# ---------------------------------------------------------------------------
# the 2026-09-24 condition, replayed hermetically against the REAL ladder
# ---------------------------------------------------------------------------
def test_NEGATIVE_an_expired_cache_with_no_lxml_falls_back_LOUDLY(
        monkeypatch, blocked_network_attempts):
    """Exactly what happened: cache expired, the local xls could not be parsed
    (no lxml), iShares is reached for — refused here, a Cloudflare page in real
    life — and the ladder lands on curated + sp500 + sp400. That fallback must
    say it is the wrong universe, in provenance AND in the size guard."""
    _expire("russell3000")
    monkeypatch.setattr(U, "_load_ishares_local_xls", _lxml_missing)

    out = U.fetch_russell3000()

    expected = list(dict.fromkeys(list(U.UNIVERSE) + _snapshot("sp500") + _snapshot("sp400")))
    assert out == expected
    assert U.last_source("russell3000")["source"] == "curated"
    assert U.LAST_COUNTS["russell3000"]["ok"] is False
    assert "dns www.ishares.com" in blocked_network_attempts()


def test_an_expired_cache_with_a_parseable_export_rebuilds_locally(
        monkeypatch, blocked_network_attempts):
    """The api container's path (it has lxml): the committed export is parsed,
    the count passes, and nothing reaches for the network."""
    _expire("russell3000")
    monkeypatch.setattr(U, "_load_ishares_local_xls",
                        lambda path, *, source_label: _snapshot("russell3000"))

    assert U.fetch_russell3000() == _snapshot("russell3000")
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_LOCAL
    assert U.LAST_COUNTS["russell3000"]["ok"] is True
    assert U._cache_age_days("russell3000") < 1          # rewritten in the COPY
    assert blocked_network_attempts() == []


def test_NEGATIVE_a_curated_provenance_left_behind_does_not_poison_a_healthy_derivation(
        monkeypatch, tmp_path):
    """Today's cross-file failure, pinned on the production side: provenance
    from an EARLIER resolve must never decide THIS derivation. The real parents
    re-record on every call, so the guard reads the current resolve."""
    monkeypatch.setattr(U, "_LOCAL_IWM_PATH", tmp_path / "absent.xls")
    U._cache_path("russell2000").unlink(missing_ok=True)   # the derivation, even once an IWM export is snapshotted
    U._LAST_SOURCE["russell1000"] = {"source": "curated", "n": 903, "age_days": 0.0}
    U._LAST_SOURCE["russell3000"] = {"source": "curated", "n": 1020, "age_days": 0.0}

    out = U.fetch_russell2000()

    big = set(_snapshot("russell1000"))
    assert out == [s for s in dict.fromkeys(_snapshot("russell3000")) if s not in big]
    assert U.last_source("russell2000")["source"] == U.SRC_DERIVED_R2000


def test_NEGATIVE_a_parent_that_really_falls_back_still_kills_the_derivation(
        monkeypatch, tmp_path, blocked_network_attempts):
    """...and the guard still fires when a parent genuinely degrades in THIS
    resolve: russell1000 expired, unparseable, network refused -> curated ->
    no russell2000 at all rather than a subtraction off the wrong universe."""
    monkeypatch.setattr(U, "_LOCAL_IWM_PATH", tmp_path / "absent.xls")
    U._cache_path("russell2000").unlink(missing_ok=True)   # the derivation, even once an IWM export is snapshotted
    _expire("russell1000")
    monkeypatch.setattr(U, "_load_ishares_local_xls", _lxml_missing)

    assert U.fetch_russell2000() == []
    assert U.last_source("russell1000")["source"] == "curated"
    assert U.last_source("russell2000")["source"] == "empty"
    assert "dns www.ishares.com" in blocked_network_attempts()


def test_provenance_does_not_survive_into_the_next_test_part_1():
    U._record("russell3000", "curated", ["AAPL"])
    assert U.last_source("russell3000")["source"] == "curated"


def test_provenance_does_not_survive_into_the_next_test_part_2():
    """Runs after part 1 (file order). The autouse fixture cleared it."""
    assert U.last_source("russell3000") is None
    assert "russell3000" not in U.LAST_COUNTS
