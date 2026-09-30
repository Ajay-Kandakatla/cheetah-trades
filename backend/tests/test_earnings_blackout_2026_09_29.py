"""Pre-earnings blackout reaches the scan (2026-09-29, MU).

BUG: `entry_exit.build_entry_exit` has always implemented the pre-earnings
blackout (`PREEARNINGS_BLOCK_DAYS`), but BOTH scanner call sites — the full scan
(`_analyze_symbol`) and the fast scan (`_hot_recompute`) — never passed
`earnings_date`, so the blackout never fired for any name. MU reports
2026-09-30 AMC and its card read "actionable" on 2026-09-29.

FIX: the scan reads the `earnings_calendar` cache ONCE (`earnings_watch.bulk_map`,
the same source as the FE 📅 chip), and `_next_earnings_date` hands each call
site a valid future ISO date or None. The blackout length and verdict logic in
entry_exit.py are untouched.

Pinned here (Rule #4 — behavioural + regression + source guard):
  * SOURCE GUARD — every `build_entry_exit(` call in scanner.py passes
    `earnings_date=`, and every analyze call in both scan loops passes
    `earnings_map=`.
  * earnings in 1 day → blackout fires, verdict WAIT (not ENTER).
  * earnings in 10 days → verdict unchanged (ENTER), blackout False.
  * past date / garbage / None / missing name → no date, verdict unchanged.
  * the fast-scan and full-scan paths both carry the date to build_entry_exit.

ROUND 2 (critic, same day):
  * the on-demand callers — GET /sepa/candidate fallback, POST /sepa/rescan,
    POST /sepa/analyze (the card's Rescan button, which PERSISTS its row into
    the latest scan) and position_lens — also pass `earnings_map`; the guard
    now pins the keyword VALUE (the `earnings_map` name bound from
    `_earnings_map`, or the helper call itself), not mere presence.
  * end-to-end: the real `scan_universe` / `scan_universe_fast` loops, incl.
    the retry and fast-scan fallback submits, deliver the date to a spied
    build_entry_exit; the real `sepa_analyze_one` body keeps WAIT and persists it.
  * days-to-earnings counts on the America/New_York calendar
    (`entry_exit.et_date`), so a 23:35 ET scan does not block a report 4 days
    out a day early (UTC had already rolled to tomorrow).

All synthetic. No network, no Mongo.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import sys
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from sepa import entry_exit as ee  # noqa: E402
from sepa import scanner as sc  # noqa: E402

SCANNER_SRC = Path(sc.__file__).read_text()
BACKEND = Path(__file__).resolve().parents[1]
MAIN_SRC = (BACKEND / "main.py").read_text()
LENS_SRC = (BACKEND / "sepa" / "position_lens.py").read_text()
ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 29, 20, 0, tzinfo=timezone.utc)   # 16:00 ET, MU day
TODAY = NOW.date()

# In-zone, Stage-2, setup-ready, volume-confirmed → ENTER with no earnings.
PLAN = {"entries": {"aggressive": 100.0}, "buy_zone": {"lo": 100.0, "hi": 102.5},
        "stop": {"recommended": 93.0, "recommended_label": "base low"},
        "targets": {"r1": 110.0, "r2": 120.0, "r3": 135.0}}


def _in(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _card(earnings_date):
    return ee.build_entry_exit(
        last_close=101.0, trade_plan=PLAN, df=None,
        stage={"stage": 2}, vol={"high_vol_breakout": True},
        setup_ready=True, earnings_date=earnings_date, now=NOW)


def _card_via_scanner(emap, sym="MU"):
    return _card(sc._next_earnings_date(sym, emap, now=NOW))


# ---------------------------------------------------------------------------
# SOURCE GUARD — both call sites pass earnings_date
# ---------------------------------------------------------------------------
def _calls(tree, name):
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if fname == name:
            out.append(node)
    return out


def _is_map_value(v) -> bool:
    """The only accepted `earnings_map=` values: the local name `earnings_map`
    or a direct call of the one-read helper `_earnings_map()`."""
    if isinstance(v, ast.Name):
        return v.id == "earnings_map"
    if isinstance(v, ast.Call):
        f = v.func
        return (f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)) == "_earnings_map"
    return False


def _kw(call, name):
    return next((k.value for k in call.keywords if k.arg == name), None)


def _func_name(node):
    return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", None)


def test_source_guard_every_build_entry_exit_call_passes_earnings_date():
    tree = ast.parse(SCANNER_SRC)
    calls = _calls(tree, "build_entry_exit")
    assert len(calls) == 2, "expected the full-scan + fast-scan call sites"
    for c in calls:
        v = _kw(c, "earnings_date")
        assert v is not None, (
            f"scanner.py:{c.lineno} build_entry_exit omits earnings_date — "
            "the pre-earnings blackout silently never fires (MU 2026-09-29)")
        # VALUE, not presence: _next_earnings_date(symbol, earnings_map)
        assert isinstance(v, ast.Call) and _func_name(v.func) == "_next_earnings_date", (
            f"scanner.py:{c.lineno} earnings_date is not _next_earnings_date(...)")
        assert len(v.args) >= 2 and _is_map_value(v.args[1]), (
            f"scanner.py:{c.lineno} _next_earnings_date is not fed earnings_map")


def test_source_guard_every_analyze_call_in_scanner_passes_earnings_map():
    tree = ast.parse(SCANNER_SRC)
    seen = 0
    for c in _calls(tree, "_analyze_symbol") + _calls(tree, "_hot_recompute"):
        seen += 1
        assert _is_map_value(_kw(c, "earnings_map")), (
            f"scanner.py:{c.lineno} analyze call drops earnings_map (or passes a non-map value)")
    for c in _calls(tree, "submit"):
        if c.args and getattr(c.args[0], "id", None) in ("_analyze_symbol", "_hot_recompute"):
            seen += 1
            assert _is_map_value(_kw(c, "earnings_map")), (
                f"scanner.py:{c.lineno} ex.submit(analyze) drops earnings_map")
    assert seen >= 4   # full loop, full retry, fast fallback, fast hot path


def _analyze_sites(src):
    """[(enclosing function, call node)] for every `_analyze_symbol` call —
    direct, or handed to asyncio.to_thread as the first argument."""
    tree = ast.parse(src)
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for c in ast.walk(fn):
            if not isinstance(c, ast.Call):
                continue
            direct = _func_name(c.func) == "_analyze_symbol"
            threaded = (_func_name(c.func) == "to_thread" and c.args
                        and _func_name(c.args[0]) == "_analyze_symbol")
            if direct or threaded:
                out.append((fn, c))
    return out


# The on-demand callers the 2026-09-29 round-2 fix list names. The Rescan
# button is sepa_analyze_one (POST /sepa/analyze — it persists its row into the
# latest scan, so without the map it WIPED the blackout the scan had set).
MAIN_FIXED = {"sepa_candidate_detail", "sepa_rescan", "sepa_analyze_one", "_analyze_for_verdict"}
# GET /sepa/verdicts batch helper (Portfolio / Auto-Pilot position cards) was
# reported out of scope in round 2 and fixed in the main session the same day.
MAIN_NOT_IN_SCOPE: set = set()


def _binds_from_helper(fn) -> bool:
    """`earnings_map = ...` in this function is built from `_earnings_map`
    (directly or via asyncio.to_thread(sc._earnings_map))."""
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "earnings_map" for t in n.targets):
            return any(_func_name(x) == "_earnings_map" for x in ast.walk(n.value)
                       if isinstance(x, (ast.Name, ast.Attribute)))
    return False


def _assert_site_ok(fn, c, where):
    v = _kw(c, "earnings_map")
    assert _is_map_value(v), (
        f"{where}:{c.lineno} {fn.name} calls _analyze_symbol without "
        "earnings_map=earnings_map / _earnings_map() — blackout lost")
    if isinstance(v, ast.Name):
        assert _binds_from_helper(fn), (
            f"{where}:{c.lineno} {fn.name}: earnings_map not bound from _earnings_map")


def test_source_guard_main_on_demand_callers_pass_the_map():
    sites = _analyze_sites(MAIN_SRC)
    names = {fn.name for fn, _ in sites}
    # Every call site is accounted for: a NEW caller must be added to one set.
    assert names <= MAIN_FIXED | MAIN_NOT_IN_SCOPE, names - (MAIN_FIXED | MAIN_NOT_IN_SCOPE)
    assert MAIN_FIXED <= names, MAIN_FIXED - names
    for fn, c in sites:
        if fn.name in MAIN_FIXED:
            _assert_site_ok(fn, c, "main.py")


def test_source_guard_position_lens_passes_the_map():
    sites = _analyze_sites(LENS_SRC)
    assert len(sites) == 1
    fn, c = sites[0]
    _assert_site_ok(fn, c, "position_lens.py")


@pytest.mark.parametrize("bad", ["None", "{}", "emap", "other()", "sc._earnings_map"])
def test_is_map_value_rejects_non_map_values(bad):
    # NEGATIVE: the guard must not accept a placeholder value.
    assert not _is_map_value(ast.parse(bad, mode="eval").body)


@pytest.mark.parametrize("good", ["earnings_map", "_earnings_map()", "sc._earnings_map()",
                                  "scanner._earnings_map()"])
def test_is_map_value_accepts_the_map(good):
    assert _is_map_value(ast.parse(good, mode="eval").body)


def test_source_guard_both_scans_build_the_map():
    tree = ast.parse(SCANNER_SRC)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("scan_universe", "scan_universe_fast"):
        assert _calls(fns[name], "_earnings_map"), f"{name} never reads the calendar"


def test_blackout_constant_untouched():
    assert ee.PREEARNINGS_BLOCK_DAYS == 3


# ---------------------------------------------------------------------------
# _next_earnings_date — validation (negatives mandatory)
# ---------------------------------------------------------------------------
def test_next_date_future_and_today_pass_through():
    assert sc._next_earnings_date("MU", {"MU": _in(1)}, now=NOW) == _in(1)
    assert sc._next_earnings_date("MU", {"MU": _in(0)}, now=NOW) == _in(0)
    assert sc._next_earnings_date("mu", {"MU": _in(1)}, now=NOW) == _in(1)


@pytest.mark.parametrize("emap", [
    None, {}, {"AAPL": "2026-09-30"},                   # missing name
    {"MU": None}, {"MU": ""}, {"MU": "   "},             # empty
    {"MU": "soon"}, {"MU": "2026-13-45"}, {"MU": 20260930},  # garbage
    {"MU": ["2026-09-30"]},
    {"MU": "2026-09-28"}, {"MU": "2025-12-17"},           # past
])
def test_next_date_negatives_return_none(emap):
    assert sc._next_earnings_date("MU", emap, now=NOW) is None


def test_next_date_empty_symbol_is_none():
    assert sc._next_earnings_date("", {"": _in(1)}, now=NOW) is None


# ---------------------------------------------------------------------------
# Behaviour — the existing entry_exit rule, now fed a date
# ---------------------------------------------------------------------------
def test_baseline_no_earnings_is_enter():
    c = _card(None)
    assert c["decision"] == "ENTER"
    assert c["earnings"] is None


def test_earnings_in_1_day_blackout_fires():
    c = _card_via_scanner({"MU": _in(1)})
    assert c["decision"] == "WAIT"
    assert c["decision_color"] == "amber"
    assert c["earnings"] == {"date": _in(1), "in_days": 1, "blackout": True}
    assert "Earnings in 1d" in c["decision_reason"]


@pytest.mark.parametrize("days", [0, 1, 2, 3])
def test_blackout_window_edges_inside(days):
    c = _card_via_scanner({"MU": _in(days)})
    assert c["decision"] == "WAIT" and c["earnings"]["blackout"] is True


@pytest.mark.parametrize("days", [4, 10, 30])
def test_earnings_outside_window_verdict_unchanged(days):
    c = _card_via_scanner({"MU": _in(days)})
    assert c["decision"] == "ENTER"                     # same as no earnings
    assert c["earnings"]["blackout"] is False
    assert c["earnings"]["in_days"] == days


@pytest.mark.parametrize("val", ["2026-09-28", "garbage", None, "", 12345])
def test_past_or_garbage_leaves_card_exactly_as_before(val):
    c = _card_via_scanner({"MU": val})
    base = _card(None)
    assert c["decision"] == base["decision"] == "ENTER"
    assert c["earnings"] is None
    assert c["timeline"] == base["timeline"]


def test_missing_calendar_leaves_card_exactly_as_before():
    assert _card_via_scanner(None) == _card(None)
    assert _card_via_scanner({}) == _card(None)


# ---------------------------------------------------------------------------
# _earnings_map — one cached read, fails soft
# ---------------------------------------------------------------------------
def test_earnings_map_reads_bulk_map(monkeypatch):
    from sepa import earnings_watch
    monkeypatch.setattr(earnings_watch, "bulk_map", lambda: {"ok": True, "map": {
        "MU": {"date": "2026-09-30", "days_to": 1, "when": "AMC"},
        "nvda": {"date": "2026-10-20", "days_to": 21, "when": None},
        "BAD": {"date": None}, "WORSE": "x"}})
    assert sc._earnings_map() == {"MU": "2026-09-30", "NVDA": "2026-10-20"}


def test_earnings_map_no_mongo_is_empty(monkeypatch):
    from sepa import earnings_watch
    monkeypatch.setattr(earnings_watch, "bulk_map", lambda: {"ok": False, "map": {}})
    assert sc._earnings_map() == {}


def test_earnings_map_exception_is_empty(monkeypatch):
    from sepa import earnings_watch

    def boom():
        raise RuntimeError("calendar down")
    monkeypatch.setattr(earnings_watch, "bulk_map", boom)
    assert sc._earnings_map() == {}


def test_earnings_map_real_path_without_mongo_is_empty():
    # conftest refuses MongoClient → earnings_watch._coll() is None → {}.
    assert sc._earnings_map() == {}


# ---------------------------------------------------------------------------
# Both scan paths carry the date to build_entry_exit
# ---------------------------------------------------------------------------
def _df(n_bars: int = 300):
    idx = pd.bdate_range(end=pd.Timestamp(date.today()), periods=n_bars)
    px = pd.Series(100.0 + np.arange(n_bars) * 0.1, index=idx)
    return pd.DataFrame({"open": px, "high": px * 1.01, "low": px * 0.99,
                         "close": px, "volume": pd.Series(1_000_000, index=idx)})


@pytest.fixture
def spy(monkeypatch):
    seen = []
    real = ee.build_entry_exit

    def _spy(**kw):
        seen.append(kw)
        return real(**kw)
    monkeypatch.setattr(ee, "build_entry_exit", _spy)
    return seen


def _et_in(days: int) -> str:
    """ISO date `days` after today on the ET calendar build_entry_exit counts on."""
    return (ee.et_date(datetime.now(timezone.utc)) + timedelta(days=days)).isoformat()


def _tomorrow_utc() -> str:   # name kept; now the ET calendar (round 2)
    return _et_in(1)


def test_fast_scan_path_passes_earnings_date(spy):
    d = _tomorrow_utc()
    row = sc._hot_recompute("MUX", _df(), {}, {"liquidity": {"liquid": True}},
                            earnings_map={"MUX": d})
    assert row is not None
    assert spy and spy[-1]["earnings_date"] == d
    assert row["entry_exit"]["earnings"]["blackout"] is True
    assert row["entry_exit"]["decision"] != "ENTER"


def test_fast_scan_path_without_map_unchanged(spy):
    row = sc._hot_recompute("MUX", _df(), {}, {"liquidity": {"liquid": True}})
    assert row is not None
    assert spy and spy[-1]["earnings_date"] is None
    assert row["entry_exit"]["earnings"] is None


def test_fast_scan_path_past_date_ignored(spy):
    past = _et_in(-2)
    row = sc._hot_recompute("MUX", _df(), {}, {"liquidity": {"liquid": True}},
                            earnings_map={"MUX": past})
    assert spy and spy[-1]["earnings_date"] is None
    assert row["entry_exit"]["earnings"] is None


def test_full_scan_path_passes_earnings_date(spy, monkeypatch):
    d = _tomorrow_utc()
    monkeypatch.setattr(sc.prices, "load_prices", lambda *a, **k: _df())
    row = sc._analyze_symbol("MUX", {}, require_liquidity=False,
                             earnings_map={"MUX": d})
    assert row is not None
    assert spy and spy[-1]["earnings_date"] == d
    assert row["entry_exit"]["earnings"]["blackout"] is True


# ---------------------------------------------------------------------------
# END-TO-END — the real scan loops (incl. retry + fast fallback submits)
# ---------------------------------------------------------------------------
class _Stop(Exception):
    """Raised from group_leadership.annotate — the first call after the scan
    loops in BOTH scans — so the test sees the loop results without running
    market context / enrichment / persistence."""
    def __init__(self, results):
        super().__init__("stop")
        self.results = results


@pytest.fixture
def scan_env(monkeypatch, spy):
    """Hermetic scan: prices/RS/names/SPY stubbed; MUY's FIRST price load
    raises so its row only arrives through the retry submit."""
    loads: dict = {}

    def _load(symbol, *a, **k):
        loads[symbol] = loads.get(symbol, 0) + 1
        if symbol in ("MUY", "MUZ") and loads[symbol] == 1:
            raise RuntimeError("transient 429")
        return _df()

    monkeypatch.setattr(sc.prices, "load_prices", _load)
    monkeypatch.setattr(sc.prices, "patch_latest_closes", lambda *a, **k: {})
    monkeypatch.setattr(sc.rs_rank, "rs_ranks", lambda *a, **k: {})
    monkeypatch.setattr(sc.company_names, "bulk_warm", lambda *a, **k: None)
    monkeypatch.setattr(sc, "_refresh_spy_baseline", lambda: None)
    monkeypatch.setattr(sc.time, "sleep", lambda *_: None)

    def _stop(results):
        raise _Stop(list(results))
    monkeypatch.setattr(sc.group_leadership, "annotate", _stop)
    return types.SimpleNamespace(spy=spy, loads=loads)


def _rows(exc_info):
    return {r["symbol"]: r for r in exc_info.value.results}


def test_e2e_full_scan_and_retry_deliver_the_date(scan_env, monkeypatch):
    emap = {"MUX": _et_in(1), "MUY": _et_in(2)}
    monkeypatch.setattr(sc, "_earnings_map", lambda: dict(emap))
    with pytest.raises(_Stop) as ei:
        sc.scan_universe(["MUX", "MUY"], persist=False)
    rows = _rows(ei)
    assert scan_env.loads["MUY"] == 2                       # came via the retry submit
    assert set(rows) == {"MUX", "MUY"}
    assert sorted(k["earnings_date"] for k in scan_env.spy) == sorted(emap.values())
    for sym, d in emap.items():
        e = rows[sym]["entry_exit"]
        assert e["earnings"]["date"] == d and e["earnings"]["blackout"] is True
        assert e["decision"] == "WAIT"


def test_e2e_fast_scan_hot_fallback_and_retry_deliver_the_date(scan_env, monkeypatch):
    # MUX: cached research → _hot_recompute. MUY: no research → fallback
    # _analyze_symbol, first load raises → retry → fallback again.
    # MUZ: cached research, first load raises → retry → _hot_recompute.
    emap = {"MUX": _et_in(1), "MUY": _et_in(2), "MUZ": _et_in(3)}
    monkeypatch.setattr(sc, "_earnings_map", lambda: dict(emap))
    blob = {"liquidity": {"liquid": True}}
    monkeypatch.setattr(sc.research_mod, "get_all_research",
                        lambda: {"MUX": blob, "MUZ": blob})
    with pytest.raises(_Stop) as ei:
        sc.scan_universe_fast(["MUX", "MUY", "MUZ"], persist=False)
    rows = _rows(ei)
    assert scan_env.loads["MUY"] == 2 and scan_env.loads["MUZ"] == 2
    assert set(rows) == {"MUX", "MUY", "MUZ"}
    assert rows["MUX"].get("from_cache") and rows["MUZ"].get("from_cache")
    assert not rows["MUY"].get("from_cache")                  # fallback path
    assert sorted(k["earnings_date"] for k in scan_env.spy) == sorted(emap.values())
    for sym, d in emap.items():
        e = rows[sym]["entry_exit"]
        assert e["earnings"]["date"] == d and e["earnings"]["blackout"] is True
        assert e["decision"] != "ENTER"


@pytest.mark.parametrize("which", ["full", "fast"])
def test_e2e_scans_without_calendar_are_unchanged(scan_env, monkeypatch, which):
    # NEGATIVE: empty calendar → no date reaches build_entry_exit, no blackout.
    monkeypatch.setattr(sc, "_earnings_map", lambda: {})
    monkeypatch.setattr(sc.research_mod, "get_all_research",
                        lambda: {"MUX": {"liquidity": {"liquid": True}}})
    with pytest.raises(_Stop) as ei:
        if which == "full":
            sc.scan_universe(["MUX", "MUY"], persist=False)
        else:
            sc.scan_universe_fast(["MUX", "MUY"], persist=False)
    rows = _rows(ei)
    assert set(rows) == {"MUX", "MUY"}
    assert scan_env.spy and all(k["earnings_date"] is None for k in scan_env.spy)
    assert all(r["entry_exit"]["earnings"] is None for r in rows.values())


# ---------------------------------------------------------------------------
# END-TO-END — the Rescan button (POST /sepa/analyze) and POST /sepa/rescan
# ---------------------------------------------------------------------------
def _endpoint(name, ns):
    """Compile ONE endpoint body straight out of main.py (the local venv cannot
    import main.py whole) into a namespace of stand-ins for its module globals.
    The body — incl. its `from sepa import ...` and the persist step — is the
    real source."""
    tree = ast.parse(MAIN_SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    fn.decorator_list = []
    mod = ast.Module(body=[fn], type_ignores=[])
    exec(compile(mod, "main.py", "exec"), ns)
    return ns[name]


@pytest.fixture
def endpoint_env(monkeypatch, tmp_path):
    from starlette.responses import JSONResponse
    from sepa import prices, rs_rank, research
    latest_path = tmp_path / "latest.json"
    latest_path.write_text(json.dumps({
        "all_results": [{"symbol": "MUX", "entry_exit": {"decision": "WAIT"}}],
        "candidates": []}))

    def _load_latest():
        return json.loads(latest_path.read_text())

    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: _df())
    monkeypatch.setattr(rs_rank, "rs_ranks", lambda *a, **k: {})
    monkeypatch.setattr(research, "compute_research", lambda *a, **k: None)
    ns = {
        "asyncio": asyncio, "json": json, "log": logging.getLogger("t"),
        "JSONResponse": JSONResponse, "Query": lambda d=None, **k: d,
        "sepa_scanner": types.SimpleNamespace(load_latest=_load_latest,
                                              LATEST_PATH=str(latest_path)),
    }
    return types.SimpleNamespace(ns=ns, load_latest=_load_latest)


def _call(fn, *a, **k):
    resp = asyncio.run(fn(*a, **k))
    return json.loads(resp.body)


def test_e2e_rescan_button_keeps_wait_and_persists_it(endpoint_env, monkeypatch, spy):
    d = _et_in(1)
    monkeypatch.setattr(sc, "_earnings_map", lambda: {"MUX": d})
    fn = _endpoint("sepa_analyze_one", endpoint_env.ns)
    res = _call(fn, "mux", with_catalyst=False)
    assert spy and spy[-1]["earnings_date"] == d
    e = res["entry_exit"]
    assert e["decision"] == "WAIT" and "Earnings in 1d" in e["decision_reason"]
    assert e["earnings"] == {"date": d, "in_days": 1, "blackout": True}
    # The row written back into the latest scan keeps the blackout.
    row = next(r for r in endpoint_env.load_latest()["all_results"] if r["symbol"] == "MUX")
    assert row["entry_exit"]["decision"] == "WAIT"
    assert row["entry_exit"]["earnings"]["blackout"] is True


def test_e2e_rescan_button_without_calendar_no_blackout(endpoint_env, monkeypatch, spy):
    # NEGATIVE: calendar empty → the card is the pre-fix card (no WAIT-for-earnings).
    monkeypatch.setattr(sc, "_earnings_map", lambda: {})
    fn = _endpoint("sepa_analyze_one", endpoint_env.ns)
    res = _call(fn, "MUX", with_catalyst=False)
    assert spy and spy[-1]["earnings_date"] is None
    assert res["entry_exit"]["earnings"] is None
    assert res["entry_exit"]["decision"] != "WAIT"


def test_e2e_post_rescan_keeps_wait(endpoint_env, monkeypatch, spy):
    d = _et_in(1)
    monkeypatch.setattr(sc, "_earnings_map", lambda: {"MUX": d})
    fn = _endpoint("sepa_rescan", endpoint_env.ns)
    res = _call(fn, "MUX")
    assert spy and spy[-1]["earnings_date"] == d
    assert res["entry_exit"]["decision"] == "WAIT"


# ---------------------------------------------------------------------------
# ET calendar — days-to-earnings across the UTC midnight boundary
# ---------------------------------------------------------------------------
def _card_at(now, earnings_date):
    return ee.build_entry_exit(
        last_close=101.0, trade_plan=PLAN, df=None,
        stage={"stage": 2}, vol={"high_vol_breakout": True},
        setup_ready=True, earnings_date=earnings_date, now=now)


LATE_EDT = datetime(2026, 9, 29, 23, 35, tzinfo=ET)      # = 2026-09-30 03:35 UTC


def test_et_date_helper():
    assert LATE_EDT.astimezone(timezone.utc).date() == date(2026, 9, 30)
    assert ee.et_date(LATE_EDT) == date(2026, 9, 29)
    assert ee.et_date(LATE_EDT.astimezone(timezone.utc)) == date(2026, 9, 29)
    assert ee.et_date(datetime(2026, 9, 30, 3, 35)) == date(2026, 9, 29)   # naive = UTC
    assert ee.et_date(datetime(2026, 12, 2, 0, 30, tzinfo=timezone.utc)) == date(2026, 12, 1)  # EST


def test_2335_et_report_4_days_out_is_not_blocked_a_day_early():
    # UTC says 3 days (blackout); the ET calendar says 4 → no blackout.
    for now in (LATE_EDT, LATE_EDT.astimezone(timezone.utc)):
        c = _card_at(now, "2026-10-03")
        assert c["earnings"] == {"date": "2026-10-03", "in_days": 4, "blackout": False}
        assert c["decision"] == "ENTER"


def test_2335_et_report_3_days_out_is_blocked():
    c = _card_at(LATE_EDT, "2026-10-02")
    assert c["earnings"]["in_days"] == 3 and c["earnings"]["blackout"] is True
    assert c["decision"] == "WAIT"


def test_2335_et_report_today_is_not_dropped_as_past():
    # UTC would call 09-29 "yesterday" (in_days -1, no blackout) and the scanner
    # would drop it; ET says it is today.
    now_utc = LATE_EDT.astimezone(timezone.utc)
    assert sc._next_earnings_date("MU", {"MU": "2026-09-29"}, now=now_utc) == "2026-09-29"
    c = _card_at(now_utc, "2026-09-29")
    assert c["earnings"]["in_days"] == 0 and c["decision"] == "WAIT"
    # NEGATIVE: yesterday on the ET calendar is still dropped.
    assert sc._next_earnings_date("MU", {"MU": "2026-09-28"}, now=now_utc) is None


def test_before_2000_et_utc_and_et_agree():
    now = datetime(2026, 9, 29, 19, 59, tzinfo=ET)          # 23:59 UTC, same date
    c = _card_at(now, "2026-10-03")
    assert c["earnings"]["in_days"] == 4 and c["decision"] == "ENTER"
    c = _card_at(now, "2026-10-02")
    assert c["earnings"]["in_days"] == 3 and c["decision"] == "WAIT"


def test_est_winter_boundary():
    now = datetime(2026, 12, 1, 19, 30, tzinfo=ET)           # EST: 00:30 UTC 12-02
    assert _card_at(now, "2026-12-05")["earnings"] == {
        "date": "2026-12-05", "in_days": 4, "blackout": False}
    assert _card_at(now, "2026-12-04")["decision"] == "WAIT"


def test_just_after_et_midnight_counts_the_new_day():
    now = datetime(2026, 9, 30, 0, 5, tzinfo=ET)
    c = _card_at(now, "2026-10-03")
    assert c["earnings"]["in_days"] == 3 and c["decision"] == "WAIT"
