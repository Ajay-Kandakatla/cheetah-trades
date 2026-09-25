"""Test-session isolation.

WHY THIS FILE EXISTS (2026-08-17)
--------------------------------
It didn't, and the suite was talking to the LIVE database.

Every Mongo-backed module here resolves its connection from `MONGO_URL` at call
time, defaulting to a reachable host. Inside the api container that default IS
production. Nothing in the suite overrode it, so any test that reached a real
write path wrote real rows — and the day this was found, a fresh
`demand_reentry.scan()` recording hook did exactly that: fixture symbols AAA,
BBB and GOOD, plus two runs for universe "Test", landed in the live
`demand_board_runs` / `demand_episodes` collections on the first full run of
`pytest`.

That is the same defect that had just been fixed one module over, where 5,371
simulated `zone_backtest` rows were being served from the pattern ledger as if
they were live observations. Simulated data in a live ledger is not a cosmetic
problem: it is published on a page as a track record.

The guard REPLACES `pymongo.MongoClient` rather than pointing `MONGO_URL` at a
dead address. Both block the writes; only this one is free. Redirecting the URL
was measured first and cost the suite 44s -> 109s, because pymongo keeps
retrying a refused socket for the whole `serverSelectionTimeoutMS` window on
every single call. Raising at construction is instant, and every `_coll()` /
`_db()` helper in this codebase already catches a construction failure and
returns None — the documented "no mongo" path each module handles. So the guard
needs no per-module cooperation.

`MONGO_URL` is redirected as well, for the belt-and-braces case of a module
that builds a client through some other import path.

A test that genuinely wants to exercise a Mongo path monkeypatches the module's
own accessor with an in-memory stand-in (see `tests/test_demand_history.py`),
which is faster and more precise than a live database anyway.

The guard is installed when this file is IMPORTED, not in a fixture (changed
2026-09-24): test modules run their own module-level code at collection, before
any fixture exists, and test_cloud_infra_theme.py resolves
`load_universe("full")` at module level — which reaches the Mongo-backed
trader/promo curation lanes. The fixture below only undoes the guard at exit.

HERMETIC UNIVERSE LISTS + NO LIVE NETWORK (2026-09-24)
-----------------------------------------------------
Five tests went red on a clean origin/main on the afternoon of 2026-09-24 with
no code change. `sepa.universe` caches each index list for 30 days in
`~/.cheetah/universe/<name>.txt`, every file on the Mac had been written
2026-08-25 15:30:02, so at 15:30 on 2026-09-24 they expired together and the
suite started resolving the index lists LIVE:

  russell3000   local iShares xls -> needs lxml, absent from the host venv
                -> iShares CSV (Cloudflare page, no 'Ticker' header)
                -> curated + sp500 + sp400 = 1,020 names: the WRONG universe
  sp400, sp600  Wikipedia via pandas.read_html -> needs lxml -> stale cache
  sp500         Wikipedia fails, the datahub CSV mirror SUCCEEDS over the
                live network, and rewrote the host's cache file mid-run

Measured on a full run: 147 Wikipedia and 49 iShares requests, all from
`sepa.universe`, and none from anywhere else. The suite would have gone red
on ANY machine 30 days after its cache was written. Inside the api container
(where `make contracts` runs) that directory is the production volume.

Three guards, all installed at import for the same collection-time reason:

1. The universe cache directory is a per-session temp copy of the committed
   snapshot in tests/fixtures/universe/ (provenance in MANIFEST.json there),
   stamped fresh at session start so the 30-day TTL cannot lapse under a run.
   A test that writes or expires a list only touches the copy, which is
   re-seeded after that test.
2. Live network is refused. A socket connect or DNS lookup for any host that
   is not loopback, and any curl_cffi request (yfinance and StockTwits go
   through libcurl, which never touches Python's socket module), raises
   LiveNetworkBlocked — an OSError, so every caller's own offline path runs
   exactly as it would with the cable pulled. Those paths swallow the error
   and fall back quietly (that is how "1,020 names" hid the cause today), so
   a test that FAILS carries a "live network refused" section naming the
   hosts it reached for, and the run ends with a short list of every test
   that tried. On 2026-09-24 that list was 9 tests in 4 files calling Yahoo
   through yfinance (curl_cffi, invisible to a socket log) for junk symbols.
   On 2026-09-25 each had its own read stubbed and the list is EMPTY, so any
   name in it is a new offender (docs/sepa/universe_test_snapshot.md). An
   attempt is credited to the test running AT THE TIME, so a background
   thread's fetch can land on the next test; module caches (macro calendar,
   gauge) mean only the first test to fill one ever shows up.
3. `sepa.universe`'s module-global provenance (_LAST_SOURCE, LAST_COUNTS) is
   cleared around every test. The russell2000 derivation reads its parents'
   provenance, and a 'curated' left behind by one test's resolve failed three
   tests in another file.
"""
from __future__ import annotations

import atexit
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ---------------------------------------------------------------------------
# 1. Mongo: refused at construction
# ---------------------------------------------------------------------------
_MONGO_ENV_KEYS = ("MONGO_URL", "MONGO_DB")
_PRIOR_MONGO_ENV = {k: os.environ.get(k) for k in _MONGO_ENV_KEYS}
os.environ["MONGO_URL"] = "mongodb://mongo.disabled-in-tests.invalid:27017"
os.environ["MONGO_DB"] = "cheetah_test_should_never_exist"

try:
    import pymongo
except Exception:                             # pragma: no cover
    pymongo = None

_REAL_MONGO_CLIENT = getattr(pymongo, "MongoClient", None) if pymongo else None


def _refuse_mongo(*a, **k):
    raise RuntimeError(
        "MongoClient is disabled during tests (tests/conftest.py). "
        "Patch the module's own _coll()/_db() with an in-memory "
        "stand-in instead — see tests/test_demand_history.py.")


if _REAL_MONGO_CLIENT is not None:
    pymongo.MongoClient = _refuse_mongo


# ---------------------------------------------------------------------------
# 2. Live network: refused, recorded, and fatal to the test that tried
# ---------------------------------------------------------------------------
class LiveNetworkBlocked(OSError):
    """A test reached for the live network. An OSError on purpose: every
    caller's own offline handling runs exactly as it would with the cable
    pulled."""


NET_ATTEMPTS: list[str] = []
NET_OFFENDERS: dict[str, list[str]] = {}          # nodeid -> refused targets
_LOCAL_HOSTS = frozenset({"localhost", "testserver", "0.0.0.0", "::", "::1"})


def _is_local(host) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host).strip("[]").lower()
    return not host or host in _LOCAL_HOSTS or host.startswith("127.")


def _refuse_network(what: str):
    NET_ATTEMPTS.append(what)
    raise LiveNetworkBlocked(
        "live network is disabled during tests (tests/conftest.py): " + what)


_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_INET = (socket.AF_INET, socket.AF_INET6)


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _is_local(host):
        _refuse_network("dns %s" % host)
    return _REAL_GETADDRINFO(host, *args, **kwargs)


def _guarded_connect(self, address):
    if self.family in _INET and not _is_local(address[0]):
        _refuse_network("connect %s:%s" % (address[0], address[1]))
    return _REAL_CONNECT(self, address)


def _guarded_connect_ex(self, address):
    if self.family in _INET and not _is_local(address[0]):
        _refuse_network("connect %s:%s" % (address[0], address[1]))
    return _REAL_CONNECT_EX(self, address)


socket.getaddrinfo = _guarded_getaddrinfo
socket.socket.connect = _guarded_connect
socket.socket.connect_ex = _guarded_connect_ex

try:
    from curl_cffi import curl as _curl
    from curl_cffi.const import CurlOpt as _CurlOpt
except Exception:                             # pragma: no cover
    _curl = None

_REAL_CURL_SETOPT = _curl.Curl.setopt if _curl is not None else None


def _guarded_curl_setopt(self, option, value):
    if option == _CurlOpt.URL:
        url = value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
        host = urlsplit(url).hostname
        if not _is_local(host):
            _refuse_network("curl %s" % host)
    return _REAL_CURL_SETOPT(self, option, value)


if _curl is not None:
    _curl.Curl.setopt = _guarded_curl_setopt


# ---------------------------------------------------------------------------
# 3. The universe lists: a committed snapshot, never the host's cache
# ---------------------------------------------------------------------------
UNIVERSE_SNAPSHOT_DIR = Path(__file__).resolve().parent / "fixtures" / "universe"
HERMETIC_UNIVERSE_DIR = Path(tempfile.mkdtemp(prefix="cheetah-test-universe-"))
atexit.register(shutil.rmtree, HERMETIC_UNIVERSE_DIR, ignore_errors=True)

if not any(UNIVERSE_SNAPSHOT_DIR.glob("*.txt")):
    raise RuntimeError(
        "tests/fixtures/universe/ is missing or empty — without it every "
        "universe test resolves its index lists live (see tests/conftest.py)")


def _universe_dir_state() -> dict:
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
            for p in HERMETIC_UNIVERSE_DIR.iterdir()}


def _seed_universe_cache() -> dict:
    """Copy the snapshot in and stamp every file NOW. The TTL is measured from
    the stamp, so a snapshot committed months ago still reads as fresh."""
    for p in HERMETIC_UNIVERSE_DIR.iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for src in sorted(UNIVERSE_SNAPSHOT_DIR.glob("*.txt")):
        dst = HERMETIC_UNIVERSE_DIR / src.name
        shutil.copyfile(src, dst)
        os.utime(dst, None)
    return _universe_dir_state()


from sepa import universe as _universe      # noqa: E402

_universe.UNIV_CACHE_DIR = HERMETIC_UNIVERSE_DIR
_PRISTINE_UNIVERSE = _seed_universe_cache()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="session")
def _never_touch_a_real_database():
    """Undo the import-time guards when the session ends."""
    yield

    if _REAL_MONGO_CLIENT is not None:
        pymongo.MongoClient = _REAL_MONGO_CLIENT
    for k, v in _PRIOR_MONGO_ENV.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    socket.getaddrinfo = _REAL_GETADDRINFO
    socket.socket.connect = _REAL_CONNECT
    socket.socket.connect_ex = _REAL_CONNECT_EX
    if _curl is not None:
        _curl.Curl.setopt = _REAL_CURL_SETOPT


@pytest.fixture(autouse=True)
def _hermetic_test(request):
    global _PRISTINE_UNIVERSE
    _universe._LAST_SOURCE.clear()
    _universe.LAST_COUNTS.clear()
    request.node._net_start = len(NET_ATTEMPTS)
    yield
    _universe._LAST_SOURCE.clear()
    _universe.LAST_COUNTS.clear()
    if _universe_dir_state() != _PRISTINE_UNIVERSE:
        _PRISTINE_UNIVERSE = _seed_universe_cache()
    attempts = sorted(set(NET_ATTEMPTS[request.node._net_start:]))
    if attempts:
        NET_OFFENDERS[request.node.nodeid] = attempts


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A failing test says what it reached for: the refusal itself is usually
    swallowed by a fallback, so the assertion alone rarely names the cause."""
    outcome = yield
    report = outcome.get_result()
    start = getattr(item, "_net_start", None)
    if report.failed and start is not None:
        attempts = sorted(set(NET_ATTEMPTS[start:]))
        if attempts:
            report.sections.append((
                "live network refused (tests/conftest.py)", "\n".join(attempts)))


def pytest_terminal_summary(terminalreporter):
    if not NET_OFFENDERS:
        return
    by_file: dict[str, set[str]] = {}
    for nodeid, attempts in NET_OFFENDERS.items():
        hosts = by_file.setdefault(nodeid.split("::")[0], set())
        hosts.update(a.split(" ", 1)[1].rsplit(":", 1)[0] for a in attempts)
    terminalreporter.write_sep(
        "-", "live network refused in %d test(s) — stub the fetch "
             "(tests/conftest.py)" % len(NET_OFFENDERS))
    for f in sorted(by_file):
        terminalreporter.write_line("  %s -> %s" % (f, ", ".join(sorted(by_file[f]))))


@pytest.fixture
def blocked_network_attempts():
    """For a test that drives code into the network guard on purpose. Call the
    yielded function for the attempts made so far in this test; they are
    consumed at teardown, so the test is not listed as an offender for doing
    exactly what it set out to do."""
    start = len(NET_ATTEMPTS)
    yield lambda: list(NET_ATTEMPTS[start:])
    del NET_ATTEMPTS[start:]
