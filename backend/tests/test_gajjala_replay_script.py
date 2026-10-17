"""⏪ scripts/gajjala_replay.py — the offline replay of today's detectors on a session with no record (2026-10-16 night,
DECISIONS11 D4 / D6, BUILD_SPEC11 §3.12 / §3.13 / §4 WP-D, AMENDMENTS11 F11).

Hermetic: the REAL 2-name slice of the study cache (tests/fixtures/gajjala/replay_cache_2026_10_12, see its README)
copied to tmp_path; `now` = Fri 2026-10-16 22:00 ET; a recorder store (records_on / types_map / upsert_replay); a
`fetch_minutes` recorder that RAISES unless the test allows it; every run injects `split_lookup` (AMENDMENTS11 F11) —
NO_SPLIT answers False, the ledger's own "no split" (`ledger._default_split_lookup`: True / iso = a split, False =
none, None = the check was not read). The network is never reached (the container runs --network none).
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tape as TP
from scripts import gajjala_replay as R
from scripts import gajjala_study as S

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
NOW = datetime(2026, 10, 16, 22, 0, tzinfo=ET)                  # Friday night, after the 20:00 ET close
FIXTURE = Path(__file__).parent / "fixtures" / "gajjala" / "replay_cache_2026_10_12"
SESSIONS = ("2026-10-09", "2026-10-12")
SCRIPT = Path(R.__file__)
# the real hits (the fixture README's table — the study's own detectors on these bars)
HITS = {("2026-10-09", "WFF", "intraday_vcp"): ("2026-10-09 15:00", "2026-10-09 15:00", 14.4, 10.68),
        ("2026-10-09", "WFF", "reversal_squeeze"): ("2026-10-09 16:50", "2026-10-09 16:50", 13.145, 12.1562),
        ("2026-10-12", "TCRT", "bull_flag"): ("2026-10-12 16:20", "2026-10-12 16:20", 1.04, 1.03),
        ("2026-10-12", "WFF", "reversal_squeeze"): ("2026-10-12 20:00", "2026-10-12 20:00", 15.17, 14.61)}


def NO_SPLIT(*_a, **_k):                                          # F11: injected "no split" (the ledger's False)
    return False


class RecStore:
    """Recorders for the three store calls the script makes."""

    def __init__(self, records=0, types=None):
        self.records = records
        self.types = types
        self.calls: list = []
        self.upserts: list = []

    def records_on(self, d):
        self.calls.append(("records_on", d))
        if isinstance(self.records, Exception):
            raise self.records
        return self.records(d) if callable(self.records) else self.records

    def types_map(self):
        self.calls.append(("types_map",))
        return {"types": self.types} if self.types is not None else {}

    def upsert_replay(self, doc):
        self.calls.append(("upsert_replay", doc.get("_id")))
        self.upserts.append(doc)
        return True


class FetchRec:
    """`fetch_minutes` recorder: records every call, RAISES unless allowed; `ret` = one answer for every call, or a
    callable (sym, day) -> answer."""

    def __init__(self, allow=False, ret=None):
        self.allow, self.ret, self.calls = allow, ret, []

    def __call__(self, sym, day):
        self.calls.append((sym, day))
        if not self.allow:
            raise AssertionError(f"fetch_minutes called for {sym} {day}")
        return self.ret(sym, day) if callable(self.ret) else self.ret


class MemColl:
    """A minimal in-memory collection (find / replace_one / distinct) for a real GajjalaStore."""

    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}

    def find(self, q, *_a, **_k):
        def ok(doc):
            for k, v in q.items():
                if isinstance(v, dict) and "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
                elif doc.get(k) != v:
                    return False
            return True
        return [dict(d) for d in self.docs.values() if ok(d)]

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)

    def distinct(self, key):
        return sorted({d.get(key) for d in self.docs.values()})


def mem_store(**over) -> ST.GajjalaStore:
    colls = {n: MemColl() for n in ST.ALL}
    colls.update(over)
    return ST.GajjalaStore(colls=colls)


@pytest.fixture()
def cache(tmp_path) -> Path:
    dst = tmp_path / "cache"
    shutil.copytree(FIXTURE, dst)
    return dst


def run(cache, tmp_path, *extra, sessions=SESSIONS, now=NOW, store=None, fetch=None, split=NO_SPLIT, out="out",
        offline=True, types="none"):
    store = store if store is not None else RecStore()
    fetch = fetch if fetch is not None else FetchRec()
    argv = ["--sessions", *sessions, "--cache", str(cache), "--out", str(tmp_path / out), "--types", types, *extra]
    if offline:
        argv.append("--offline")
    kw = {"now": now, "store": store, "fetch_minutes": fetch}
    if split is not None:
        kw["split_lookup"] = split
    rc = R.main(argv, **kw)
    return rc, store, fetch


def summary(tmp_path, out="out") -> dict:
    return json.loads((tmp_path / out / "replay.json").read_text())


def events(tmp_path, out="out") -> dict:
    with open(tmp_path / out / "events.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {(r["date"], r["symbol"], r["setup"]): r for r in rows}


def tree(p: Path) -> dict:
    return {str(f.relative_to(p)): f.read_bytes() for f in sorted(p.rglob("*")) if f.is_file()}


def minute_bars(cache, sym, *days) -> list:
    c = S.Cache(cache, offline=True)
    return LG._merge(*(LG.bars_from_frame(c.minutes(sym, date.fromisoformat(x))) for x in days))


def row_of(d_iso, sym, trig, stop, pass_t):
    at = datetime.strptime(pass_t, "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(UTC)
    return {"symbol": sym, "date": d_iso, "at_utc": at, "trigger": trig, "stop": stop,
            "plan": LG.plan_of(trig, stop)[0]}, LG.session_bounds(date.fromisoformat(d_iso), at)


# ── 1. smoke --offline --types none ───────────────────────────────────────────────────────────────────────────────
def test_smoke_offline_grades_from_the_cache_never_fetches_never_writes(cache, tmp_path):
    before = tree(cache)
    rc, st, fm = run(cache, tmp_path)
    assert rc == 0
    assert (tmp_path / "out" / "events.csv").is_file() and (tmp_path / "out" / "replay.json").is_file()
    ev = events(tmp_path)
    kept = {k: v for k, v in ev.items() if v["kept"] == "True"}
    assert set(kept) == set(HITS)                                 # exactly the real hits, nothing synthesized
    for k, (bar_t, pass_t, trig, stop) in HITS.items():
        r = kept[k]
        assert (r["entry_bar_t"], r["pass_t"], float(r["trigger"]), float(r["stop"])) == (bar_t, pass_t, trig, stop)
    # A = TCRT (10-12 A+, its 10-13 minutes ARE cached): rang after the close → same graded on the cached 10-13 bars
    a = kept[("2026-10-12", "TCRT", "bull_flag")]
    assert a["same_entry"] == "filled" and a["same_fill_t"].startswith("2026-10-13")
    assert a["next_entry"] == ""                                  # its next session (10-14) is not in the study cache
    # B = WFF on 10-12 (its 10-13 minutes are NOT cached): nothing graded
    b = kept[("2026-10-12", "WFF", "reversal_squeeze")]
    assert b["same_entry"] == "" and b["next_entry"] == ""
    # the next column graded from the cache: WFF 10-09 intraday_vcp (same 10-09, next 10-12, both cached)
    v = kept[("2026-10-09", "WFF", "intraday_vcp")]
    assert v["same_entry"] == "filled" and v["next_entry"] == "filled"
    w = kept[("2026-10-09", "WFF", "reversal_squeeze")]
    assert w["same_fill_t"].startswith("2026-10-12") and w["next_entry"] == ""
    s = summary(tmp_path)["sessions"]
    assert {k: (v["state"], v["kept"], v["same_graded"], v["next_graded"], v["next_not_cached"])
            for k, v in s.items()} == {"2026-10-09": ("replayed", 2, 2, 1, 1), "2026-10-12": ("replayed", 2, 1, 0, 2)}
    assert fm.calls == []                                         # NEGATIVE: --offline never fetches
    assert st.upserts == [] and not [c for c in st.calls if c[0] == "upsert_replay"]   # no --write → no write
    assert summary(tmp_path)["written"] == 0
    assert tree(cache) == before                                  # NEGATIVE: the cache is never written


# ── 2. --write: the frozen §3.12 doc, read back by the ledger ─────────────────────────────────────────────────────
def test_write_docs_have_the_frozen_shape_and_the_ledger_reads_them_as_replayed(cache, tmp_path):
    rc, st, _fm = run(cache, tmp_path, "--write", "--sha", "abc1234")
    assert rc == 0
    assert len(st.upserts) == len(HITS) == summary(tmp_path)["written"]
    for doc in st.upserts:
        assert set(doc) - {"_id"} == ST.REPLAY_KEYS
        assert doc["_id"] == LG.replay_id(doc["date"], doc["symbol"], doc["setup"])
        assert (doc["kind"], doc["state"], doc["float_gate"], doc["universe"]) == \
            ("aplus", "replayed", False, "study same-day q")
        assert doc["caveats"] == list(LG.REPLAY_CAVEATS)
        assert doc["detectors_sha"] == "abc1234" and re.fullmatch(r"[0-9a-f]{64}", doc["detectors_sha256"])
        assert datetime.fromisoformat(doc["replayed_at"]) == NOW
        json.dumps(doc)                                           # plain JSON / BSON types only (no numpy)
        a = doc["alert"]
        assert set(a) == {"date", "symbol", "setup", "entry_bar_t", "frame", "trigger", "stop", "risk_pct", "pass_t",
                          "q_t", "at"}
        at = datetime.fromisoformat(a["at"])
        assert at.utcoffset().total_seconds() == 0
        assert at == datetime.strptime(a["pass_t"], "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        # bars5: 5-minute RIGHT labels, ascending, from the alert day's 04:05 ET through the next column's end
        ts = [x["t"] for x in doc["bars5"]]
        assert ts and ts == sorted(ts) and all(t % (GC.LEDGER_TAPE_TF_MIN * 60_000) == 0 for t in ts)
        d = date.fromisoformat(doc["date"])
        first = datetime(d.year, d.month, d.day, 4, 5, tzinfo=ET).timestamp() * 1000
        b = LG.session_bounds(d, at)
        assert ts[0] >= first and ts[-1] <= b["next_end"].timestamp() * 1000
        assert set(doc["bars5"][0]) == {"t", "o", "h", "l", "c", "v", "s"}
        # the ledger reads what the script writes
        row = LG.alert_of(doc, "aplus")
        assert row["line"] == "replayed" and row["id"] == doc["_id"] and row["at_utc"] == at
        assert (row["trigger"], row["stop"]) == (a["trigger"], a["stop"])
    # one engine: the stored same column IS ledger.grade on the cache's own minutes
    vcp = next(x for x in st.upserts if x["_id"] == "REPLAY:2026-10-09|WFF|intraday_vcp")
    row, b = row_of("2026-10-09", "WFF", 14.4, 10.68, "2026-10-09 15:00")
    assert vcp["same"] == LG.grade(row, minute_bars(cache, "WFF", "2026-10-09"), b, "same")
    assert vcp["next"] == LG.grade(row, minute_bars(cache, "WFF", "2026-10-09", "2026-10-12"), b, "next")
    assert vcp["bars5"][:3] == TP.bars5(S.Cache(cache, offline=True).minutes("WFF", date(2026, 10, 9)))[:3]


def test_write_through_a_real_store_is_idempotent_and_replay_rows_reads_it(cache, tmp_path):
    real = mem_store()
    rc, _st, _fm = run(cache, tmp_path, "--write", "--sha", "abc1234", store=real)
    assert rc == 0 and summary(tmp_path)["written"] == len(HITS)
    rc2, _st, _fm = run(cache, tmp_path, "--write", "--sha", "abc1234", store=real, out="out2")
    assert rc2 == 0
    docs = real.replay_rows(list(SESSIONS))
    assert sorted(d["_id"] for d in docs) == sorted(LG.replay_id(*k) for k in HITS)     # re-run replaced, no dup
    assert real.replay_dates() == list(SESSIONS)
    assert all(LG.alert_of(d, "aplus")["line"] == "replayed" for d in docs)
    assert real.coll(ST.LEDGER).docs == {} and real.coll(ST.ALERTS).docs == {}           # NEGATIVE: only gajjala_replay


# ── 3. online: ONE fetch per missing (symbol, day), never a cached day, never written ─────────────────────────────
def test_online_fetches_b_10_13_exactly_once_and_never_a_cached_day(cache, tmp_path):
    before = tree(cache)
    fm = FetchRec(allow=True, ret=None)
    rc, _st, _ = run(cache, tmp_path, sessions=("2026-10-09",), fetch=fm, offline=False)
    assert rc == 0
    assert fm.calls == [("WFF", date(2026, 10, 13))]              # 10-09 rs: next = 10-13; once though needed once
    fm2 = FetchRec(allow=True, ret=None)
    rc, _st, _ = run(cache, tmp_path, fetch=fm2, offline=False, out="out2")
    assert rc == 0
    got = Counter(fm2.calls)
    assert set(got) == {("WFF", date(2026, 10, 13)), ("TCRT", date(2026, 10, 14)), ("WFF", date(2026, 10, 14))}
    assert set(got.values()) == {1}                               # WFF 10-13 is needed by two events: ONE fetch
    cached = {(p.stem, date.fromisoformat(p.parent.name)) for p in (cache / "minutes").rglob("*.json")}
    assert not set(got) & cached                                  # NEGATIVE: never a day the cache holds
    assert tree(cache) == before                                  # NEGATIVE: a fetched day is never written
    cs = summary(tmp_path, "out2")["cache_stats"]
    assert cs["minutes_fetch_failed"] == 3                        # NEGATIVE: a None answer (the HTTP loader's
    assert cs.get("minutes_fetch_unwritten", 0) == 0              # failed / cut / no key) is a failure, not a fetch


def test_online_a_fetched_real_day_is_graded_like_the_cache_and_never_written(cache, tmp_path):
    """Real bars only: WFF 10-12 is removed from the tmp copy and served by the fetch recorder from the fixture's own
    file; the 10-09 intraday_vcp next column must equal the offline run on the full fixture, and nothing is written."""
    rc, _st, _ = run(cache, tmp_path, sessions=("2026-10-09",), out="full")
    assert rc == 0
    full = events(tmp_path, "full")[("2026-10-09", "WFF", "intraday_vcp")]
    assert full["next_entry"] == "filled"
    p = cache / "minutes" / "2026-10-12" / "WFF.json"
    wff_1012 = S.json_to_frame(json.loads(p.read_text()))
    p.unlink()
    before = tree(cache)
    fm = FetchRec(allow=True, ret=lambda sym, day: wff_1012 if (sym, day) == ("WFF", date(2026, 10, 12)) else None)
    rc, _st, _ = run(cache, tmp_path, sessions=("2026-10-09",), fetch=fm, offline=False, out="online")
    assert rc == 0
    assert Counter(fm.calls)[("WFF", date(2026, 10, 12))] == 1    # ONE fetch for the missing day
    got = events(tmp_path, "online")[("2026-10-09", "WFF", "intraday_vcp")]
    cols = [k for k in full if k.startswith("next_")]
    assert cols and {k: got[k] for k in cols} == {k: full[k] for k in cols}   # the fetched frame IS graded
    assert tree(cache) == before and not p.exists()               # NEGATIVE: the fetched day is never written
    cs = summary(tmp_path, "online")["cache_stats"]
    assert cs["minutes_fetch_unwritten"] == 1                     # the 10-12 frame
    assert cs["minutes_fetch_failed"] == len(fm.calls) - 1        # every None answer (10-13) is a failure


def test_online_a_raising_fetch_is_not_graded_and_never_sinks_the_run(cache, tmp_path):
    fm = FetchRec(allow=False)                                    # raises on every call
    rc, _st, _ = run(cache, tmp_path, fetch=fm, offline=False)
    assert rc == 0 and len(fm.calls) == 3
    s = summary(tmp_path)
    assert s["cache_stats"]["minutes_fetch_failed"] == 3
    assert sum(v["kept"] for v in s["sessions"].values()) == len(HITS)
    assert events(tmp_path)[("2026-10-12", "TCRT", "bull_flag")]["next_entry"] == ""


# ── 4. NEGATIVE: RTH ──────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("hhmm", [(10, 0), (9, 30), (15, 59)])
def test_rth_refused_before_anything_is_read(tmp_path, capsys, hhmm):
    nope = tmp_path / "nope"
    st, fm = RecStore(), FetchRec()
    rc = R.main(["--sessions", "2026-10-12", "--cache", str(nope), "--out", str(tmp_path / "out"), "--write",
                 "--sha", "abc1234"], now=datetime(2026, 10, 19, *hhmm, tzinfo=ET), store=st, fetch_minutes=fm,
                split_lookup=NO_SPLIT)
    assert rc == 2
    assert "inside the regular session" in capsys.readouterr().err
    assert not nope.exists() and not (tmp_path / "out").exists()  # the cache path is never opened, nothing written
    assert st.calls == [] and fm.calls == []                      # no store call, no fetch


def test_after_the_close_is_not_refused(cache, tmp_path):
    rc, _st, _ = run(cache, tmp_path, now=datetime(2026, 10, 19, 16, 0, tzinfo=ET))
    assert rc == 0


# ── 5. NEGATIVE: a session with records ───────────────────────────────────────────────────────────────────────────
def test_a_session_with_records_is_refused_and_nothing_is_written(cache, tmp_path):
    st = RecStore(records=3)
    rc, st, _ = run(cache, tmp_path, "--write", "--sha", "abc1234", store=st)
    assert rc == 3
    s = summary(tmp_path)["sessions"]
    for d in SESSIONS:
        assert s[d]["state"] == "refused" and s[d]["why"].endswith("never replayed") and s[d]["why"].startswith("3 ")
    assert st.upserts == [] and summary(tmp_path)["written"] == 0
    assert all(r["kept"] == "False" for r in events(tmp_path).values())


@pytest.mark.parametrize("records", [None, RuntimeError("mongo down")], ids=["none", "raises"])
def test_unreadable_records_are_refused(cache, tmp_path, records):
    st = RecStore(records=records)
    rc, st, _ = run(cache, tmp_path, "--write", "--sha", "abc1234", store=st)
    assert rc == 3
    assert {v["why"] for v in summary(tmp_path)["sessions"].values()} == {"records unreadable"}
    assert st.upserts == []


def test_only_the_session_with_records_is_refused(cache, tmp_path):
    st = RecStore(records=lambda d: 1 if d == date(2026, 10, 12) else 0)
    rc, st, _ = run(cache, tmp_path, "--write", "--sha", "abc1234", store=st)
    assert rc == 0
    s = summary(tmp_path)["sessions"]
    assert (s["2026-10-09"]["state"], s["2026-10-12"]["state"]) == ("replayed", "refused")
    assert {d["date"] for d in st.upserts} == {"2026-10-09"}


# ── 6. NEGATIVE: --write without --sha, future / unfinished sessions ──────────────────────────────────────────────
@pytest.mark.parametrize("sha", [None, "xyz", "abc12", "g" * 7, "a" * 41])
def test_write_needs_a_hex_sha(cache, tmp_path, sha):
    extra = ("--write",) + (("--sha", sha) if sha else ())
    rc, st, _ = run(cache, tmp_path, *extra)
    assert rc == 2 and st.calls == [] and not (tmp_path / "out").exists()


@pytest.mark.parametrize("session,now", [
    ("2026-10-19", NOW),                                           # a future session
    ("2026-10-16", datetime(2026, 10, 16, 17, 0, tzinfo=ET)),      # today before its after-hours close
    ("2026-10-10", NOW),                                           # a Saturday
], ids=["future", "today-before-close", "weekend"])
def test_a_session_not_completed_is_refused(cache, tmp_path, session, now):
    rc, st, _ = run(cache, tmp_path, sessions=(session,), now=now)
    assert rc == 3
    assert summary(tmp_path)["sessions"][session] == {"state": "refused", "why": "not a completed session"}
    assert st.calls == []                                         # never asks the store about a session not over


def test_a_session_whose_grouped_file_is_not_cached_is_refused(cache, tmp_path):
    rc, _st, _ = run(cache, tmp_path, sessions=("2026-10-13",))
    assert rc == 3
    assert summary(tmp_path)["sessions"]["2026-10-13"]["why"] == "grouped not cached"


def test_a_directory_without_the_study_marker_is_refused_and_never_written(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    st = RecStore()
    rc = R.main(["--sessions", "2026-10-12", "--cache", str(empty), "--out", str(tmp_path / "out")], now=NOW,
                store=st, fetch_minutes=FetchRec(), split_lookup=NO_SPLIT)
    assert rc == 2 and list(empty.iterdir()) == [] and st.calls == []


def test_a_stale_layout_is_refused(cache, tmp_path):
    (cache / S.CACHE_MARKER).write_text(json.dumps({"layout": 1}))
    rc, st, _ = run(cache, tmp_path)
    assert rc == 2 and st.calls == []


# ── 7. NEGATIVE: the A+ filter ────────────────────────────────────────────────────────────────────────────────────
def test_only_clean_aplus_breaks_in_the_window_are_kept(cache, tmp_path, monkeypatch):
    base = {"symbol": "TCRT", "session": "2026-10-12", "setup": "bull_flag", "frame": "5m",
            "entry_bar_t": "2026-10-12 10:30", "entry_class": "aplus", "trigger": 1.04, "stop": 1.03,
            "risk_pct": 0.96, "q_t": "2026-10-12 09:52", "pass_t": "2026-10-12 10:30", "variant": None, "grade": None}
    evs = [dict(base, entry_class="stopped_in_bar"), dict(base, setup="intraday_vcp", variant="long_flag"),
           dict(base, setup="reversal_squeeze", grade="B"),
           dict(base, setup="first_pullback", entry_bar_t="2026-10-12 09:35", pass_t="2026-10-12 09:35")]

    def stub(sym, d, *a, **k):
        assert (k.get("with_pool"), k.get("method"), k.get("scope")) == (False, "v2", "live")
        return {"symbol": sym, "q_t": "2026-10-12 09:52", "events": [dict(e, symbol=sym) for e in evs]}

    monkeypatch.setattr(S, "study_symbol_day", stub)
    rc, st, _ = run(cache, tmp_path, "--write", "--sha", "abc1234", "--symbols", "TCRT", sessions=("2026-10-12",))
    assert rc == 0
    s = summary(tmp_path)["sessions"]["2026-10-12"]
    assert s["kept"] == 0 and s["events"] == 4
    assert s["dropped"] == {"not_aplus": 1, "variant": 1, "grade": 1, "window": 1}
    assert st.upserts == []
    assert {r["why_dropped"] for r in events(tmp_path).values()} == {"not_aplus", "variant", "grade", "window"}


def test_the_study_runs_with_no_pool_on_method_v2(cache, tmp_path, monkeypatch):
    seen = []
    real = S.study_symbol_day

    def spy(*a, **k):
        seen.append(k)
        return real(*a, **k)

    monkeypatch.setattr(S, "study_symbol_day", spy)
    run(cache, tmp_path, sessions=("2026-10-12",))
    assert seen and all((k["with_pool"], k["method"], k["scope"]) == (False, "v2", "live") for k in seen)


# ── 8. replay.json = counts only ──────────────────────────────────────────────────────────────────────────────────
BANNED_KEY = re.compile(r"pct|rate|win|expect", re.I)


def _keys(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + (k,)
            yield from _keys(v, path + (k,))
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v, path)


def _strings(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, path + (k,))
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v, path)
    elif isinstance(obj, str):
        yield path, obj


@pytest.mark.parametrize("extra", [(), ("--write", "--sha", "abc1234")], ids=["dry", "write"])
def test_replay_json_has_counts_only_no_rate_no_percent(cache, tmp_path, extra):
    run(cache, tmp_path, *extra)
    s = summary(tmp_path)
    for p in _keys(s):
        # the ONE allowed hit: §3.13 step 6 names the dropped counter "window" (the push window, not a win)
        if p[-1] == "window":
            assert len(p) == 4 and p[0] == "sessions" and p[2] == "dropped"
            continue
        assert not BANNED_KEY.search(p[-1]), p
    for p, text in _strings(s):
        if p[:1] == ("caveats",):
            continue
        assert "%" not in text, (p, text)
    assert s["caveats"] == list(LG.REPLAY_CAVEATS)


# ── F11: the split guard — injected, never the network ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("split", [None, lambda *a, **k: None], ids=["offline-no-lookup", "lookup-unread"])
def test_offline_without_a_lookup_every_guarded_column_is_null(cache, tmp_path, split, monkeypatch):
    # NEGATIVE (critic round 2): under --offline the script never builds the ledger's default lookup — that lookup
    # reads Massive. A recorder factory answering False would GRADE the guarded columns, so a built default either
    # records a call here or turns a null into a grade; both fail.
    built: list = []

    def factory(*a, **k):
        built.append((a, k))
        return NO_SPLIT

    monkeypatch.setattr(LG, "_default_split_lookup", factory)
    rc, st, fm = run(cache, tmp_path, "--write", "--sha", "abc1234", split=split)
    assert rc == 0 and fm.calls == []
    assert built == []                                             # the default (network) lookup is never built
    docs = {d["_id"]: d for d in st.upserts}
    assert all(d["next"] is None for d in docs.values())           # next is always guarded over (d, next_date]
    assert docs["REPLAY:2026-10-09|WFF|reversal_squeeze"]["same"] is None     # after-close same: guarded → null
    assert docs["REPLAY:2026-10-12|TCRT|bull_flag"]["same"] is None
    assert docs["REPLAY:2026-10-09|WFF|intraday_vcp"]["same"]["entry"] == "filled"   # RTH same is not guarded
    s = summary(tmp_path)["sessions"]
    assert (s["2026-10-09"]["split_unread"], s["2026-10-12"]["split_unread"]) == (2, 1)
    assert sum(v["next_graded"] for v in s.values()) == 0


def test_a_split_on_file_is_a_split_cell_never_a_grade(cache, tmp_path):
    asked = []

    def split(sym, d, end_d):
        asked.append((sym, d, end_d))
        return "2026-10-12" if end_d == date(2026, 10, 12) else False

    rc, st, _ = run(cache, tmp_path, "--write", "--sha", "abc1234", split=split)
    assert rc == 0
    docs = {d["_id"]: d for d in st.upserts}
    vcp = docs["REPLAY:2026-10-09|WFF|intraday_vcp"]
    assert vcp["same"]["entry"] == "filled"
    assert (vcp["next"]["reason"], vcp["next"]["split_on"], vcp["next"]["outcome"]) == ("split", "2026-10-12", None)
    rs = docs["REPLAY:2026-10-09|WFF|reversal_squeeze"]
    assert (rs["same"]["reason"], rs["same"]["fill_px"]) == ("split", None)       # after close: guarded over 10-12
    assert ("WFF", date(2026, 10, 9), date(2026, 10, 12)) in asked
    assert all(x[1] < x[2] for x in asked)                         # the window is (alert day, end]


# ── --types store / --symbols ─────────────────────────────────────────────────────────────────────────────────────
def test_types_store_reads_the_live_map_and_applies_the_scanner_rule(cache, tmp_path):
    st = RecStore(types={"TCRT": "CS", "WFF": "WARRANT"})
    rc, st, _ = run(cache, tmp_path, store=st, types="store")
    assert ("types_map",) in st.calls
    s = summary(tmp_path)
    assert s["types"] == "store"
    assert rc == 0 and s["sessions"]["2026-10-12"]["superset"] == 1 and s["sessions"]["2026-10-09"]["superset"] == 0
    assert {k[1] for k, r in events(tmp_path).items() if r["kept"] == "True"} == {"TCRT"}   # NEGATIVE: WFF out


def test_symbols_limits_the_names(cache, tmp_path):
    run(cache, tmp_path, "--symbols", "TCRT")
    assert {k[1] for k in events(tmp_path)} == {"TCRT"}


# ── source hygiene ────────────────────────────────────────────────────────────────────────────────────────────────
def test_script_source_offline_cache_one_write_no_banned_words():
    src = SCRIPT.read_text()
    assert "S.Cache(a.cache, offline=True)" in src
    assert src.count("bool(store.upsert_replay(") == 1 and "if a.write:" in src
    for bad in ("load_intraday", "_mongo_put_day", "upsert_ledger", "insert_one", "update_one", "frame_to_json"):
        assert bad not in src, bad
    low = src.lower()
    for bad in ("b" + "ounce", "fa" + "ke", "forecast", "verdict =", "win_rate", "expectancy ="):
        assert bad not in low, bad


# ── 9. the frozen names the script codes against (WP-C step 1) ───────────────────────────────────────────────────
def test_frozen_names_exist():
    for name in ("records_on", "upsert_replay", "replay_rows"):
        assert hasattr(ST.GajjalaStore, name), name
    assert hasattr(LG, "REPLAY_CAVEATS") and hasattr(LG, "replay_id") and hasattr(TP, "bars5")
    assert hasattr(ST, "REPLAY") and hasattr(ST, "REPLAY_KEYS")
