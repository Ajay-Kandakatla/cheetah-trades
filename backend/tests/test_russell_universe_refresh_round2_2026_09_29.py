"""Russell universe refresh — fix round 2 (2026-09-29).

Critic findings on the live-holdings refresh, each pinned here with its
negatives:

  1. a parent re-baseline (russell1000 / russell3000) re-baselines the DERIVED
     russell2000 in the same run — the 10-04 backlog is not published as
     Russell 2000 changes; an ordinary week still diffs it
  2. versioned iShares cache keys + a holdings-date sidecar: a cache hit keeps
     `as_of`; russell_watch reads it
  3. a failed live fetch is memoised for ISHARES_LIVE_FAILURE_MEMO_SEC (fake
     clock); the resolved list is memoised per cache generation
  4. the health audit WARNs on ANY served snapshot, with its date
  5. a live parse under ISHARES_LIVE_MIN_SNAPSHOT_FRACTION of the snapshot's
     count is rejected (microcap had no lower bound)
"""
from __future__ import annotations

import logging
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sepa import universe as U  # noqa: E402
from sepa import universe_changes as UC  # noqa: E402

_HEADER = ("Ticker,Name,Sector,Asset Class,Market Value,Weight (%),"
           "Notional Value,Quantity,Price,Location,Exchange,Currency,"
           "FX Rate,Market Currency,Accrual Date")
_HTML = "<!DOCTYPE html><html><head><title>iShares</title></head><body></body></html>"


def _row(tkr):
    return (f'"{tkr}","CO","Information Technology","Equity","1,000.00",'
            f'"0.01","1,000.00","100.00","10.00","United States","NASDAQ",'
            f'"USD","1.00","USD","-"')


def live_csv(tickers, as_of="Sep 28, 2026"):
    head = ["iShares Fund", f'Fund Holdings as of,"{as_of}"',
            'Inception Date,"May 22, 2000"', 'Shares Outstanding,"1.00"',
            'Stock,"-"', 'Bond,"-"', 'Cash,"-"', 'Other,"-"', "", _HEADER]
    return "\n".join(head + [_row(t) for t in tickers]) + "\n"


def _names(n, prefix="Q"):
    return [f"{prefix}{i:04d}" for i in range(n)]


def _dated(days_ago):
    return (date.today() - timedelta(days=days_ago)).strftime("%b %d, %Y")


@pytest.fixture
def env(monkeypatch, tmp_path):
    """tmp cache + tmp snapshots, stubbed network, a fake clock."""
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(U, "UNIV_CACHE_DIR", cache)
    snaps = {}
    for attr, n, pre in (("_LOCAL_IWB_PATH", 1000, "B"),
                         ("_LOCAL_IWV_PATH", 1900, "S"),
                         ("_LOCAL_IWC_PATH", 1000, "M")):
        p = tmp_path / f"{attr}.csv"
        p.write_text(live_csv(_names(n, pre), as_of=_dated(1)))
        monkeypatch.setattr(U, attr, p)
        snaps[attr] = p
    state = {"text": live_csv(_names(2000, "L"), as_of="Sep 28, 2026"),
             "urls": [], "raise": None, "cache": cache, "snaps": snaps,
             "t": 1_000_000.0}

    def fake_fetch(url, *, timeout=20):
        state["urls"].append(url)
        if state["raise"]:
            raise state["raise"]
        return state["text"]
    monkeypatch.setattr(U, "_fetch_text", fake_fetch)
    monkeypatch.setattr(U, "_clock", lambda: state["t"])
    monkeypatch.setattr(U, "fetch_sp500", lambda: ["CUR1", "CUR2"])
    monkeypatch.setattr(U, "fetch_sp400", lambda: ["CUR3"])
    monkeypatch.setattr(U, "UNIVERSE", ["CUR0"])
    for n in ("russell1000", "russell3000", "microcap"):
        U._LAST_SOURCE.pop(n, None)
    U.forget_ishares_memos()
    yield state
    U.forget_ishares_memos()


# ===========================================================================
# 1. a parent re-baseline re-baselines the derived russell2000
# ===========================================================================
class _Coll:
    def __init__(self, latest_by_index=None):
        self._latest = dict(latest_by_index or {})
        self.inserted = []

    def find_one(self, query=None, *a, **kw):
        return self._latest.get((query or {}).get("index"))

    def insert_one(self, doc):
        self.inserted.append(doc)

    def delete_many(self, *a, **kw):
        pass


class _DB:
    def __init__(self, latest_by_index=None):
        self.universe_snapshots = _Coll(latest_by_index)
        self.universe_changes = _Coll()


def _snap(syms, source):
    return {"symbols": list(syms), "source": source, "taken_at": "t0"}


@pytest.fixture
def week(monkeypatch):
    """A three-index run: parents and the derivation, sources dialled."""
    r1000 = _names(1000, "B")
    r3000 = r1000 + _names(1560, "S")
    state = {"r1000": r1000, "r3000": r3000,
             "src": {"russell1000": U.SRC_ISHARES_NETWORK,
                     "russell3000": U.SRC_ISHARES_NETWORK,
                     "russell2000": U.SRC_DERIVED_R2000}}

    def r2000():
        big = set(state["r1000"])
        return [s for s in state["r3000"] if s not in big]
    monkeypatch.setattr(UC, "_expire_cache", lambda name: None)
    monkeypatch.setattr(UC, "_fetchers", lambda: {
        "russell1000": lambda: list(state["r1000"]),
        "russell3000": lambda: list(state["r3000"]),
        "russell2000": r2000})
    monkeypatch.setattr(U, "last_source",
                        lambda n: {"source": state["src"].get(n), "n": 0})
    monkeypatch.setattr(U, "russell2000_coverage",
                        lambda: {"complete": False, "attributable": False,
                                 "derived_from": {}})
    return state


def _prior_week(parent_source):
    """Last week's stored snapshots: the parents from `parent_source`, the
    derivation 1,560 names."""
    r1000 = _names(1000, "B")
    r2000 = _names(1560, "S")
    return _DB({"russell1000": _snap(r1000, parent_source),
                "russell3000": _snap(r1000 + r2000, parent_source),
                "russell2000": _snap(r2000, U.SRC_DERIVED_R2000)})


def test_parents_rebaselining_rebaselines_the_derived_r2000_in_the_same_run(week, monkeypatch):
    """THE 10-04 CASE. The first live Sunday re-baselines both parents
    (ishares-local -> ishares-network). The derivation's source string never
    changes, so without the fix it publishes the June/Sep backlog as Russell
    2000 events."""
    db = _prior_week(U.SRC_ISHARES_LOCAL)
    monkeypatch.setattr(UC, "_db", lambda: db)
    # the backlog: 40 new small caps, 25 gone
    week["r3000"] = (week["r1000"] + _names(1535, "S")[:1535]
                     + _names(40, "NEW"))
    res = UC.run(["russell1000", "russell3000", "russell2000"])
    by = {r["index"]: r for r in res["indices"]}
    assert by["russell1000"]["rebaselined"] is True
    assert by["russell3000"]["rebaselined"] is True
    r2 = by["russell2000"]
    assert r2["ok"] is True and r2["rebaselined"] is True
    assert r2["added"] == [] and r2["removed"] == []
    assert r2["raw_diff_not_published"] == {"added": 40, "removed": 25}
    assert "russell1000" in r2["reason"] and "russell3000" in r2["reason"]
    assert db.universe_changes.inserted == [], "no backlog in the change log"
    assert res["changed"] == [] and res["total_added"] == 0
    # the derived list IS the new baseline
    assert [d["index"] for d in db.universe_snapshots.inserted] == [
        "russell1000", "russell3000", "russell2000"]


def test_one_parent_rebaselining_is_enough(week):
    db = _prior_week(U.SRC_ISHARES_NETWORK)
    week["r3000"] = week["r1000"] + _names(1560, "S") + ["NEW1"]
    r = UC.refresh_one("russell2000", db=db, parents_rebaselined={"russell3000"})
    assert r["rebaselined"] is True and r["added"] == []
    assert "russell3000" in r["reason"] and "russell1000" not in r["reason"]
    assert db.universe_changes.inserted == []


def test_NEGATIVE_a_normal_week_still_diffs_the_derived_list(week, monkeypatch):
    """Parents live last week AND this week: nothing re-baselines, and a real
    Russell 2000 add is published."""
    db = _prior_week(U.SRC_ISHARES_NETWORK)
    monkeypatch.setattr(UC, "_db", lambda: db)
    week["r3000"] = week["r1000"] + _names(1560, "S") + ["NEW1", "NEW2"]
    res = UC.run(["russell1000", "russell3000", "russell2000"])
    by = {r["index"]: r for r in res["indices"]}
    assert by["russell1000"]["rebaselined"] is False
    assert by["russell3000"]["rebaselined"] is False
    assert by["russell2000"]["rebaselined"] is False
    assert by["russell2000"]["added"] == ["NEW1", "NEW2"]
    rows = {c["index"]: c for c in db.universe_changes.inserted}
    assert rows["russell2000"]["added"] == ["NEW1", "NEW2"]
    assert rows["russell3000"]["added"] == ["NEW1", "NEW2"]


def test_NEGATIVE_an_unrelated_rebaseline_does_not_touch_the_derivation(week):
    db = _prior_week(U.SRC_ISHARES_NETWORK)
    week["r3000"] = week["r1000"] + _names(1560, "S") + ["NEW1"]
    r = UC.refresh_one("russell2000", db=db, parents_rebaselined={"sp500"})
    assert r["rebaselined"] is False and r["added"] == ["NEW1"]
    assert len(db.universe_changes.inserted) == 1


def test_NEGATIVE_a_real_list_is_not_rebaselined_by_its_siblings(week):
    """Only the DERIVED source follows its parents: russell3000 itself (a
    real list) is judged on its own source."""
    db = _prior_week(U.SRC_ISHARES_NETWORK)
    week["r3000"] = week["r1000"] + _names(1560, "S") + ["NEW1"]
    r = UC.refresh_one("russell3000", db=db, parents_rebaselined={"russell1000"})
    assert r["rebaselined"] is False and r["added"] == ["NEW1"]


def test_NEGATIVE_a_first_derived_snapshot_is_not_called_a_rebaseline(week):
    db = _DB({})
    r = UC.refresh_one("russell2000", db=db,
                       parents_rebaselined={"russell1000", "russell3000"})
    assert r["first_snapshot"] is True and r["rebaselined"] is False


# ===========================================================================
# 2. versioned cache keys + holdings-date sidecar
# ===========================================================================
@pytest.mark.parametrize("name,key", [("russell1000", "russell1000_v2"),
                                      ("russell3000", "russell3000_v2"),
                                      ("microcap", "microcap_v2")])
def test_the_ishares_cache_keys_are_versioned(env, name, key):
    assert U._cache_path(name).name == f"{key}.txt"
    assert U._cache_as_of_path(name).name == f"{key}.as_of"


def test_NEGATIVE_other_lists_keep_their_cache_names(env):
    for name in ("sp500", "russell2000", "themes", "nasdaq_listed"):
        assert U._cache_path(name).name == f"{name}.txt"


def test_NEGATIVE_a_legacy_unversioned_cache_is_never_read(env):
    """The May-xls cache in the shared volume stops matching on deploy."""
    (env["cache"] / "russell3000.txt").write_text("\n".join(_names(2559, "OLD")))
    out = U.fetch_russell3000()
    assert out[0] == "L0000"
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_NETWORK
    assert len(env["urls"]) == 1


def test_a_cache_hit_carries_the_holdings_date(env):
    U.fetch_russell3000()                                   # live -> cache + sidecar
    assert U._cache_as_of_path("russell3000").read_text() == "2026-09-28"
    # a NEW process: memos and provenance gone, only the files remain
    U.forget_ishares_memos()
    U._LAST_SOURCE.pop("russell3000", None)
    out = U.fetch_russell3000()
    rec = U.last_source("russell3000")
    assert out[0] == "L0000" and rec["source"] == "cache"
    assert rec["as_of"] == "2026-09-28"
    assert len(env["urls"]) == 1, "served from the cache"


@pytest.mark.parametrize("content", [None, "not a date", ""])
def test_NEGATIVE_a_missing_or_garbage_sidecar_is_None_not_a_crash(env, content):
    (U._cache_path("russell3000")).write_text("\n".join(_names(2000, "C")))
    if content is not None:
        U._cache_as_of_path("russell3000").write_text(content)
    assert U.fetch_russell3000()[0] == "C0000"
    assert U.last_source("russell3000").get("as_of") is None


def test_NEGATIVE_a_live_list_with_no_date_removes_an_old_sidecar(env):
    """A stale date must never outlive the list it described."""
    U._cache_as_of_path("russell3000").write_text("2026-05-28")
    env["text"] = live_csv(_names(2000, "L"), as_of="not a date")
    U.fetch_russell3000()
    assert not U._cache_as_of_path("russell3000").exists()
    assert U.last_source("russell3000").get("as_of") is None


def test_russell_watch_labels_files_date_from_the_cache_hit(env):
    from catalysts import russell_watch as RW
    for name, n, pre in (("russell1000", 1000, "B"), ("russell3000", 2000, "C")):
        U._cache_path(name).write_text("\n".join(_names(n, pre)))
        U._cache_as_of_path(name).write_text("2026-09-28")
    # the committed snapshot says May: it must NOT label a live-cached list
    env["snaps"]["_LOCAL_IWB_PATH"].write_text(
        live_csv(_names(1000, "B"), as_of="May 28, 2026"))
    r1000, r3000, d = RW._baseline()
    assert len(r1000) == 1000 and len(r3000) == 2000
    assert d == "2026-09-28"
    assert env["urls"] == []


def test_russell_watch_labels_a_served_snapshot_with_its_own_date(env):
    from catalysts import russell_watch as RW
    env["raise"] = ConnectionError("down")
    env["snaps"]["_LOCAL_IWB_PATH"].write_text(
        live_csv(_names(1000, "B"), as_of="Sep 21, 2026"))
    _r1000, _r3000, d = RW._baseline()
    assert U.last_source("russell1000")["source"] == U.SRC_ISHARES_SNAPSHOT
    assert d == "2026-09-21"


def test_NEGATIVE_russell_watch_never_borrows_the_snapshot_date_for_curated(env):
    from catalysts import russell_watch as RW
    env["raise"] = ConnectionError("down")
    for attr in ("_LOCAL_IWB_PATH", "_LOCAL_IWV_PATH"):
        env["snaps"][attr].unlink()
    _r1000, _r3000, d = RW._baseline()
    assert U.last_source("russell1000")["source"] == "curated"
    assert d is None


def test_expire_cache_drops_the_list_the_sidecar_and_the_memos(env):
    U.fetch_russell3000()
    env["raise"] = ConnectionError("down")
    U._ISHARES_FAILED[("russell3000", str(U.UNIV_CACHE_DIR))] = (env["t"], "x")
    UC._expire_cache("russell3000")
    assert not U._cache_path("russell3000").exists()
    assert not U._cache_as_of_path("russell3000").exists()
    assert not any(k[0] == "russell3000" for k in U._ISHARES_FAILED)
    assert "russell3000" not in U._ISHARES_RESOLVED


# ===========================================================================
# 3. failure memo + resolved-list memo (fake clock)
# ===========================================================================
def test_an_outage_downloads_once_per_memo_window(env):
    env["raise"] = ConnectionError("iShares down")
    for _ in range(5):
        out = U.fetch_russell3000()
        assert out[0] == "S0000"
        assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_SNAPSHOT
    assert len(env["urls"]) == 1, "one live attempt, then the memo"
    env["t"] += U.ISHARES_LIVE_FAILURE_MEMO_SEC - 1
    U.fetch_russell3000()
    assert len(env["urls"]) == 1, "memo still holds one second before expiry"
    env["t"] += 1
    U.fetch_russell3000()
    assert len(env["urls"]) == 2, "retried once the memo expired"


def test_recovery_after_the_memo_serves_live_and_clears_it(env):
    env["raise"] = ConnectionError("down")
    U.fetch_russell3000()
    env["raise"] = None
    env["t"] += U.ISHARES_LIVE_FAILURE_MEMO_SEC
    assert U.fetch_russell3000()[0] == "L0000"
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_NETWORK
    assert not any(k[0] == "russell3000" for k in U._ISHARES_FAILED)


def test_a_rejected_parse_is_memoised_too(env):
    env["text"] = live_csv(_names(12, "T"))
    U.fetch_russell3000()
    U.fetch_russell3000()
    assert len(env["urls"]) == 1


def test_the_outage_is_one_WARNING_then_INFO(env, caplog):
    env["raise"] = ConnectionError("down")
    with caplog.at_level(logging.INFO, logger="sepa.universe"):
        U.fetch_russell3000()
        U.fetch_russell3000()
    lines = [r for r in caplog.records if "serving the committed snapshot" in r.getMessage()]
    assert [r.levelno for r in lines] == [logging.WARNING, logging.INFO]


def test_NEGATIVE_the_memo_is_per_fund(env):
    env["raise"] = ConnectionError("down")
    U.fetch_russell3000()
    env["raise"] = None
    env["text"] = live_csv(_names(1000, "L"))
    assert U.fetch_russell1000()[0] == "L0000", "IWB is still asked"
    assert U.last_source("russell1000")["source"] == U.SRC_ISHARES_NETWORK


def test_NEGATIVE_the_memo_does_not_leak_across_cache_dirs(env, tmp_path, monkeypatch):
    env["raise"] = ConnectionError("down")
    U.fetch_russell3000()
    other = tmp_path / "other_cache"
    other.mkdir()
    monkeypatch.setattr(U, "UNIV_CACHE_DIR", other)
    env["raise"] = None
    assert U.fetch_russell3000()[0] == "L0000"


def test_a_forced_refresh_asks_iShares_inside_the_memo_hour(env):
    env["raise"] = ConnectionError("down")
    U.fetch_russell3000()
    env["raise"] = None
    UC._expire_cache("russell3000")
    assert U.fetch_russell3000()[0] == "L0000"
    assert len(env["urls"]) == 2


def test_the_resolved_list_is_memoised_per_cache_generation(env, monkeypatch):
    U.fetch_russell3000()
    reads = {"n": 0}
    real = U._read_cached

    def spy(name):
        reads["n"] += 1
        return real(name)
    monkeypatch.setattr(U, "_read_cached", spy)
    for _ in range(3):
        assert U.fetch_russell3000()[0] == "L0000"
    assert reads["n"] == 0, "same generation: no disk read"
    # another process rewrites the cache -> a new generation -> re-read
    p = U._cache_path("russell3000")
    p.write_text("\n".join(_names(2001, "N")))
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert U.fetch_russell3000()[0] == "N0000"
    assert reads["n"] == 1


def test_NEGATIVE_the_memo_never_outlives_an_expired_cache(env, monkeypatch):
    U.fetch_russell3000()
    p = U._cache_path("russell3000")
    old = p.stat().st_mtime - U.UNIV_CACHE_TTL_SEC - 10
    os.utime(p, (old, old))
    env["text"] = live_csv(_names(2000, "Z"))
    assert U.fetch_russell3000()[0] == "Z0000"
    assert len(env["urls"]) == 2


def test_the_snapshot_is_parsed_once_during_an_outage(env, monkeypatch):
    env["raise"] = ConnectionError("down")
    calls = {"n": 0}
    real = U._load_ishares_file

    def spy(path, *, source_label):
        calls["n"] += 1
        return real(path, source_label=source_label)
    monkeypatch.setattr(U, "_load_ishares_file", spy)
    for _ in range(4):
        U.fetch_russell3000()
    assert calls["n"] == 1


# ===========================================================================
# 4. health audit: ANY served snapshot warns, with its date
# ===========================================================================
def _counts(monkeypatch, *, age, served):
    src = U.SRC_ISHARES_SNAPSHOT if served else U.SRC_ISHARES_NETWORK
    monkeypatch.setattr(U, "fetch_russell3000", lambda: _names(2000))
    monkeypatch.setattr(U, "last_source",
                        lambda n: {"source": src, "n": 2000, "age_days": age,
                                   "as_of": _dated(age)})
    return U.universe_counts(names=["russell3000"])


def test_a_FRESH_served_snapshot_is_named_in_snapshot_served(env, monkeypatch):
    env["snaps"]["_LOCAL_IWV_PATH"].write_text(live_csv(["A"], as_of=_dated(3)))
    got = _counts(monkeypatch, age=3, served=True)
    assert got["_snapshot_served"] == ["russell3000"]
    assert got["_stale"] == [], "fresh: served, not stale"


def test_NEGATIVE_a_live_list_is_not_named(env, monkeypatch):
    got = _counts(monkeypatch, age=3, served=False)
    assert got["_snapshot_served"] == [] and got["_stale"] == []


def test_health_audit_WARNS_on_a_fresh_served_snapshot_with_its_date(monkeypatch):
    from observability import health_audit as H
    monkeypatch.setattr(U, "universe_counts", lambda: {
        "russell3000": {"count": 2587, "expected": [1800, 3200], "ok": True,
                        "snapshot": {"as_of": "2026-09-28", "age_days": 1.0}},
        "_failing": [], "_stale": [], "_snapshot_served": ["russell3000"]})
    r = H.check_universe_counts()
    assert r["ok"] is False and r["severity"] == H.WARN
    assert "2026-09-28" in r["detail"] and "russell3000" in r["detail"]
    assert "live holdings fetch failed" in r["detail"]
    assert "STALE" not in r["detail"]


def test_health_audit_says_STALE_only_for_the_stale_one(monkeypatch):
    from observability import health_audit as H
    monkeypatch.setattr(U, "universe_counts", lambda: {
        "russell1000": {"count": 1022, "expected": [900, 1150], "ok": True,
                        "snapshot": {"as_of": "2026-09-28", "age_days": 1.0}},
        "russell3000": {"count": 2587, "expected": [1800, 3200], "ok": True,
                        "snapshot": {"as_of": "2026-05-28", "age_days": 124.0}},
        "_failing": [], "_stale": ["russell3000"],
        "_snapshot_served": ["russell1000", "russell3000"]})
    r = H.check_universe_counts()
    assert r["ok"] is False
    assert "russell1000 (holdings as of 2026-09-28" in r["detail"]
    assert "russell3000 (STALE, holdings as of 2026-05-28" in r["detail"]


def test_health_audit_failing_band_also_names_the_served_snapshot(monkeypatch):
    from observability import health_audit as H
    monkeypatch.setattr(U, "universe_counts", lambda: {
        "sp500": {"count": 12, "expected": [450, 530], "ok": False},
        "russell3000": {"count": 2587, "expected": [1800, 3200], "ok": True,
                        "snapshot": {"as_of": "2026-09-28", "age_days": 1.0}},
        "_failing": ["sp500"], "_stale": [], "_snapshot_served": ["russell3000"]})
    r = H.check_universe_counts()
    assert "sp500=12" in r["detail"] and "2026-09-28" in r["detail"]


def test_NEGATIVE_health_audit_ok_when_nothing_served(monkeypatch):
    from observability import health_audit as H
    monkeypatch.setattr(U, "universe_counts", lambda: {
        "russell3000": {"count": 2587, "expected": [1800, 3200], "ok": True},
        "_failing": [], "_stale": [], "_snapshot_served": []})
    assert H.check_universe_counts()["ok"] is True


# ===========================================================================
# 5. a truncated live parse is rejected against the snapshot's own size
# ===========================================================================
def test_the_floor_constant():
    assert U.ISHARES_LIVE_MIN_SNAPSHOT_FRACTION == 0.60
    assert U.ISHARES_LIVE_FAILURE_MEMO_SEC == 3600


def test_a_truncated_IWC_parse_is_rejected_for_the_snapshot(env, caplog):
    """microcap's band floor is 0, so before this a 50-name IWC download was
    served (and cached for 30 days) as the micro-cap layer."""
    env["text"] = live_csv(_names(50, "T"))
    with caplog.at_level(logging.WARNING, logger="sepa.universe"):
        out = U.fetch_microcap()
    assert len(out) == 1000 and out[0] == "M0000"
    assert U.last_source("microcap")["source"] == U.SRC_ISHARES_SNAPSHOT
    assert any("truncated download" in r.getMessage() for r in caplog.records)
    assert not U._cache_path("microcap").exists()


@pytest.mark.parametrize("delta,accepted", [(0, True), (-1, False)])
def test_the_floor_boundary_is_60pct_of_the_snapshot(env, delta, accepted):
    floor = math.ceil(U.ISHARES_LIVE_MIN_SNAPSHOT_FRACTION * 1000)
    assert U._ishares_live_floor("microcap", env["snaps"]["_LOCAL_IWC_PATH"]) == floor
    env["text"] = live_csv(_names(floor + delta, "L"))
    U.fetch_microcap()
    want = U.SRC_ISHARES_NETWORK if accepted else U.SRC_ISHARES_SNAPSHOT
    assert U.last_source("microcap")["source"] == want


def test_NEGATIVE_no_snapshot_means_no_floor(env):
    env["snaps"]["_LOCAL_IWC_PATH"].unlink()
    env["text"] = live_csv(["MICRO1", "MICRO2"])
    assert U.fetch_microcap() == ["MICRO1", "MICRO2"]
    assert U.last_source("microcap")["source"] == U.SRC_ISHARES_NETWORK


def test_NEGATIVE_the_floor_never_loosens_a_static_band(env):
    """russell3000: snapshot 1,900 -> floor 1,140, but the static band floor
    is 1,800 — a 1,500-name list is still rejected."""
    env["text"] = live_csv(_names(1500, "L"))
    U.fetch_russell3000()
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_SNAPSHOT
