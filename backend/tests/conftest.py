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
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _never_touch_a_real_database():
    import os
    from chart_maps.gajjala_watch import constants as WC
    prior = {k: os.environ.get(k) for k in ("MONGO_URL", "MONGO_DB", "LUK_ENABLED", "GAJJALA_BAR_CLOSE_MODE",
                                            WC.ENV_ENABLED)}
    os.environ["MONGO_URL"] = "mongodb://mongo.disabled-in-tests.invalid:27017"
    os.environ["MONGO_DB"] = "cheetah_test_should_never_exist"
    # 🥇 2026-11-01 — Luk's kill switch ASSIGNED off for the whole session (never
    # setdefault: an exported LUK_ENABLED=1 would spawn a REAL detached Luk pass
    # from every gajjala RUN.main([]) test). Tests that exercise the spawn
    # monkeypatch.setenv("LUK_ENABLED", "1") themselves. Restored on teardown.
    os.environ["LUK_ENABLED"] = "0"
    # ⏱ 2026-11-09 — the bar-close child's mode ASSIGNED off for the session the same way (the env can only LOWER
    # chart_maps/gajjala/bar_close.mode(), never raise it): an unguarded RUN.main([]) test would otherwise spawn a REAL
    # detached bar-close child. Tests that exercise the mode monkeypatch.setenv / delenv it themselves. Restored on teardown.
    os.environ["GAJJALA_BAR_CLOSE_MODE"] = "off"
    # 👀 2026-11-15 — the watch's minute loop ASSIGNED off for the session the same way (the Luk pattern): an unguarded
    # RUN.main([]) test would otherwise spawn a REAL detached `chart_maps.gajjala_watch.loop --loop`. Tests that
    # exercise the spawn monkeypatch.setenv it themselves. Restored on teardown.
    os.environ[WC.ENV_ENABLED] = "0"

    try:
        import pymongo
    except Exception:                             # pragma: no cover
        pymongo = None

    real = getattr(pymongo, "MongoClient", None) if pymongo else None
    if real is not None:
        def _refuse(*a, **k):
            raise RuntimeError(
                "MongoClient is disabled during tests (tests/conftest.py). "
                "Patch the module's own _coll()/_db() with an in-memory "
                "stand-in instead — see tests/test_demand_history.py.")
        pymongo.MongoClient = _refuse

    # 🔒 2026-11-22 — the Reg SHO engine's ONE outside-call seam ASSIGNED to a refuser for the whole session (never
    # setdefault): a payload / kick_refresh with no `http=` must never reach nasdaqtrader / nyse / cboe. Tests that
    # want an outside answer pass their own `http=` fake. Restored on teardown.
    import short_interest.reg_sho as RS
    prior_rs_http = RS._http

    def _refuse_http(*a, **k):
        raise RuntimeError("reg_sho outside calls are disabled during tests (tests/conftest.py)")
    RS._http = _refuse_http

    # 💸 2026-11-22 — the IBKR borrow engine's ONE outside-call seam ASSIGNED to a refuser for the whole session the
    # same way: a payload / kick_refresh with no `ftp=` must never open an FTP session to Interactive Brokers. Tests
    # that want an outside answer pass their own `ftp=` fake. Restored on teardown.
    import short_interest.borrow as BR
    prior_br_ftp = BR._ftp

    def _refuse_ftp(*a, **k):
        raise RuntimeError("IBKR borrow FTP sessions are disabled during tests (tests/conftest.py)")
    BR._ftp = _refuse_ftp

    # 🔌 2026-11-23 — the Massive minute fetch's ONE outside-call seam (`daytrading.data._http_get`, spec ggconn §3.3 /
    # critique C4) ASSIGNED to a refuser for the whole session the same way. A test that needs the fetch does
    # `monkeypatch.setattr(D, "_http_get", your_fake)` (function scope wins; the refuser is back afterwards). Restored
    # on teardown.
    import daytrading.data as DD
    prior_dd_http = DD._http_get

    class MinuteFetchRefused(BaseException):
        """BaseException ON PURPOSE: the fetch wraps its GET in `except Exception` (daytrading/data.py) — an Exception
        here would be logged as a provider failure, return None and count on the breaker."""

    def _refuse_minute(*a, **k):
        raise MinuteFetchRefused("daytrading.data minute fetches are disabled during tests (tests/conftest.py) — "
                                 "monkeypatch.setattr(D, '_http_get', your_fake)")
    _refuse_minute.__wrapped__ = prior_dd_http          # a test of the seam itself reads the real function here
    DD._http_get = _refuse_minute

    # 🩳 2026-11-24 — the share-basis worker's ONE SEC outside-call seam (`short_interest.share_basis._http`, spec
    # sidilute §4 main-session) ASSIGNED to a refuser for the whole session, the reg_sho pattern above: a
    # refresh_symbol / kick with no `http=` must never reach data.sec.gov. Tests that want an SEC answer pass their own
    # `http=` fake or monkeypatch `SB._http`. Restored on teardown.
    import short_interest.share_basis as SBAS
    prior_sb_http = SBAS._http

    def _refuse_sec(*a, **k):
        raise RuntimeError("share_basis SEC calls are disabled during tests (tests/conftest.py)")
    SBAS._http = _refuse_sec

    yield

    SBAS._http = prior_sb_http
    DD._http_get = prior_dd_http
    BR._ftp = prior_br_ftp
    RS._http = prior_rs_http
    if real is not None:
        pymongo.MongoClient = real
    for k, v in prior.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
