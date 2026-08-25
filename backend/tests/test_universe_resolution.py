"""Universe resolution + size guards.

Ajay 2026-08-16: "May be add a count checks for returned values for all the
tickers API like Russel 3000 and S&P 500 as well."

Two bugs prompted this, both of the same shape — a universe silently becoming
a DIFFERENT universe while every label kept saying the right thing:

  1. `load_universe("sp1500_plus")` returned the curated 158 names, byte for
     byte identical to what a garbage key returned. /supply-demand ran a
     158-name scan while its own dropdown said "S&P 1500".
  2. `demand_reentry.UNIVERSES["sp1500_plus"]` was labelled "+ themes" but its
     lambda was `fetch_sp1500()`, so 34 of the 82 theme names were never
     scanned on the page that advertised them.

Neither raised. Neither logged an error. That is why the tests below assert on
SIZE and MEMBERSHIP rather than on "did it return a list".

These are deliberately network-free: real fetchers are monkeypatched, so the
suite pins the ROUTING and the GUARD logic, which is where both bugs lived.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import universe as U  # noqa: E402


@pytest.fixture
def fake_lists(monkeypatch):
    """Replace every component fetcher with a labelled synthetic list, so a
    resolution can be traced back to exactly which components it unioned."""
    def make(prefix, n):
        return [f"{prefix}{i}" for i in range(n)]

    lists = {
        "curated": make("CUR", 158),
        "sp500": make("F", 500),
        "sp400": make("M", 400),
        "sp600": make("S", 600),
        "sp1500": make("F", 500) + make("M", 400) + make("S", 600),
        "nasdaq100": make("N", 102),
        "themes": make("T", 82),
        "russell1000": make("R", 1001),
        "russell3000": make("R", 2559),
        "microcap": make("U", 1278),
        "etf": make("E", 373),
        "broad": make("B", 3707),
    }
    monkeypatch.setattr(U, "_COMPONENT_FETCHERS",
                        {k: (lambda v=v: list(v)) for k, v in lists.items()}
                        | {"micro": lambda: list(lists["microcap"]),
                           "etfs": lambda: list(lists["etf"])})
    monkeypatch.setattr(U, "_KNOWN_COMPONENTS", frozenset(U._COMPONENT_FETCHERS))
    monkeypatch.setattr(U, "UNIVERSE", lists["curated"])
    for key in ("SEPA_UNIVERSE_FILE", "SEPA_UNIVERSE", "SEPA_UNIVERSE_MODE"):
        monkeypatch.delenv(key, raising=False)
    return lists


# --------------------------------------------------------------------------
# The bug: single keys falling through to curated
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key,expected_min", [
    ("sp500", 500), ("sp400", 400), ("sp600", 600), ("sp1500", 1500),
    ("nasdaq100", 102), ("themes", 82),
    ("russell1000", 1001), ("russell3000", 2559),
])
def test_a_known_component_resolves_to_itself_not_to_curated(
        fake_lists, key, expected_min):
    got = U.load_universe(key)
    assert len(got) >= expected_min, f"{key} collapsed to {len(got)} names"
    # The exact failure that shipped: identical to the curated fallback.
    assert len(got) != len(fake_lists["curated"]) + 3


def test_sp1500_plus_is_sp1500_plus_curated_plus_themes(fake_lists):
    got = set(U.load_universe("sp1500_plus"))
    assert set(fake_lists["sp1500"]) <= got
    assert set(fake_lists["themes"]) <= got, "the +themes alias dropped the themes"
    assert set(fake_lists["curated"]) <= got


def test_the_alias_expands_to_the_components_it_names(fake_lists):
    assert U._UNIVERSE_ALIASES["sp1500_plus"] == ("sp1500", "curated", "themes")
    for part in U._UNIVERSE_ALIASES["sp1500_plus"]:
        assert part in U._KNOWN_COMPONENTS, f"alias names unknown component {part}"


def test_benchmarks_are_always_appended(fake_lists):
    for key in ("sp500", "sp1500_plus", "themes", "curated"):
        got = U.load_universe(key)
        assert {"SPY", "QQQ", "IWM"} <= set(got), f"{key} lost the RS anchors"


# --- negatives ---

def test_an_unknown_key_falls_back_but_says_so_loudly(fake_lists, caplog):
    """Silence was the bug. The fallback is fine; the silence was not."""
    with caplog.at_level(logging.ERROR, logger=U.log.name):
        got = U.load_universe("totally_bogus_key_xyz")
    assert len(got) == len(fake_lists["curated"]) + 3
    assert any("unknown mode" in r.getMessage() for r in caplog.records), \
        "unknown universe key logged nothing at ERROR"


def test_curated_itself_does_not_log_an_error(fake_lists, caplog):
    """Negative of the above — the legitimate default must stay quiet."""
    with caplog.at_level(logging.ERROR, logger=U.log.name):
        U.load_universe("curated")
    assert not caplog.records


def test_multi_select_still_works(fake_lists):
    got = set(U.load_universe("sp500,themes"))
    assert set(fake_lists["sp500"]) <= got and set(fake_lists["themes"]) <= got
    assert not set(fake_lists["sp600"]) & got


# --------------------------------------------------------------------------
# Size guards
# --------------------------------------------------------------------------
def test_every_component_has_a_size_band():
    """A fetcher with no band gets (1, 1e9) — i.e. no guard at all. The two
    aliases (micro/etfs) share their target's band by design."""
    unbanded = {k for k in U._COMPONENT_FETCHERS
                if k not in U._EXPECTED_COUNTS
                and k not in ("curated", "micro", "etfs")}
    assert not unbanded, f"no size band for: {sorted(unbanded)}"


def test_bands_are_sane():
    for name, (lo, hi) in U._EXPECTED_COUNTS.items():
        assert 0 <= lo <= hi, f"{name} band {lo}-{hi} is inverted"
        assert hi < 10 ** 6, f"{name} upper bound is not a real guard"


def test_russell3000_band_floors_above_the_clean_fallback():
    """The fallback (curated ∪ sp500 ∪ sp400) is ~1,030 names — a fine universe
    but NOT the Russell 3000. The band must call that out, not accept it."""
    lo, _ = U._EXPECTED_COUNTS["russell3000"]
    assert lo > 1100


def test_record_count_flags_out_of_range_and_returns_input(caplog):
    with caplog.at_level(logging.ERROR, logger=U.log.name):
        out = U._record_count("sp500", ["A", "B"])
    assert out == ["A", "B"], "the guard must not mutate the list"
    assert U.LAST_COUNTS["sp500"]["ok"] is False
    assert U.LAST_COUNTS["sp500"]["count"] == 2
    assert caplog.records, "an out-of-band list logged nothing at ERROR"


def test_record_count_is_quiet_when_in_range(caplog):
    with caplog.at_level(logging.ERROR, logger=U.log.name):
        U._record_count("sp500", [f"X{i}" for i in range(503)])
    assert U.LAST_COUNTS["sp500"]["ok"] is True
    assert not caplog.records


def test_record_count_treats_empty_as_a_failure():
    """An empty list is the loudest possible symptom and must never pass."""
    U._record_count("sp1500", [])
    assert U.LAST_COUNTS["sp1500"]["ok"] is False


def test_microcap_has_no_lower_bound_because_absent_is_legitimate():
    U._record_count("microcap", [])
    assert U.LAST_COUNTS["microcap"]["ok"] is True


def test_count_guarded_wraps_every_return_path():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return ["A"] if calls["n"] == 1 else [f"X{i}" for i in range(503)]

    guarded = U._count_guarded("sp500", flaky)
    guarded()
    assert U.LAST_COUNTS["sp500"]["ok"] is False   # first (bad) return recorded
    guarded()
    assert U.LAST_COUNTS["sp500"]["ok"] is True    # second (good) return recorded


def test_count_guarded_preserves_the_wrapped_signature():
    def fetch(limit=None):
        return [f"X{i}" for i in range(limit or 503)]
    guarded = U._count_guarded("sp500", fetch)
    assert len(guarded(limit=460)) == 460
    assert guarded.__name__ == "fetch"


def test_the_public_fetchers_are_actually_guarded():
    """Regression: the guards are installed by reassignment at the bottom of
    universe.py. A refactor that moves a fetcher below that block silently
    unguards it."""
    for name in ("fetch_sp500", "fetch_sp1500", "fetch_russell3000",
                 "fetch_russell1000", "fetch_broad", "fetch_themes",
                 "fetch_etf_universe", "fetch_microcap", "fetch_nasdaq100",
                 "fetch_sp400", "fetch_sp600"):
        fn = getattr(U, name)
        assert getattr(fn, "__wrapped__", None) is not None, f"{name} is not guarded"


def test_universe_counts_reports_every_list_and_names_the_failures(monkeypatch):
    monkeypatch.setattr(U, "fetch_sp500", lambda: ["A"])          # out of band
    monkeypatch.setattr(U, "fetch_sp400", lambda: [f"M{i}" for i in range(400)])
    for n in ("sp600", "nasdaq100", "sp1500", "russell1000", "russell3000",
              "microcap", "etf", "themes", "broad"):
        monkeypatch.setattr(U, f"fetch_{ {'etf':'etf_universe','microcap':'microcap'}.get(n, n) }",
                            lambda n=n: [f"{n}{i}" for i in range(U._EXPECTED_COUNTS[n][0] + 1)])
    got = U.universe_counts()
    assert "sp500" in got["_failing"]
    assert "sp400" not in got["_failing"]
    assert got["sp500"]["expected"] == [450, 530]


def test_universe_counts_survives_a_throwing_fetcher(monkeypatch):
    def boom():
        raise RuntimeError("iShares 403")
    monkeypatch.setattr(U, "fetch_russell3000", boom)
    got = U.universe_counts(names=["russell3000"])
    assert got["russell3000"]["ok"] is False
    assert "iShares 403" in got["russell3000"]["error"]


# ── QQQ / SPY / Nasdaq (Ajay 2026-08-20) ─────────────────────────────────────
def test_the_three_universes_Ajay_asked_for_are_all_offered():
    """"I want QQQ stocks and SPY stocks and Nasdaq stocks." QQQ and SPY are
    ETFs, so what he means is the index each tracks."""
    from supply_demand import demand_reentry as dr
    for key in ("qqq", "sp500", "nasdaq"):
        assert key in dr.UNIVERSES, f"{key} missing from the dropdown"


def test_the_labels_name_the_TICKER_he_thinks_in():
    """A dropdown that only ever said "S&P 500" never made it obvious that was
    the same list as SPY — which is why he asked for SPY as if it were new."""
    from supply_demand import demand_reentry as dr
    assert "SPY" in dr.UNIVERSES["sp500"][0]
    assert "QQQ" in dr.UNIVERSES["qqq"][0]
    assert "Nasdaq" in dr.UNIVERSES["nasdaq"][0]


def test_qqq_resolves_to_the_nasdaq_100_not_something_broader():
    from supply_demand import demand_reentry as dr
    import inspect
    src = inspect.getsource(dr)
    assert '"qqq":    ("QQQ · Nasdaq-100", lambda: universe_mod.fetch_nasdaq100())' in src


def test_nasdaq_is_PRIMARY_listing_not_merely_tradeable_there():
    """A stock is a Nasdaq stock because Nasdaq is where it is LISTED. Anything
    looser returns most of the market and the word stops meaning anything."""
    import inspect
    src = inspect.getsource(U.fetch_nasdaq_listed)
    assert "MIC_NASDAQ" in src
    assert U.MIC_NASDAQ == "XNAS"


def test_the_nasdaq_filter_cannot_silently_match_everything_or_nothing():
    """The guard band is the whole defence: a broken exchange filter either
    matches nothing (0) or leaks the full 5,300 major-exchange list."""
    lo, hi = U._EXPECTED_COUNTS["nasdaq_listed"]
    assert lo > 0
    assert hi < 5000, "the band must exclude the full major-exchange list"


def test_fetch_massive_universe_defaults_are_byte_for_byte_unchanged():
    """It grew two parameters so the Nasdaq fetch could share its paging. Every
    existing caller passes neither, and must be unaffected."""
    import inspect
    sig = inspect.signature(U.fetch_massive_universe.__wrapped__
                            if hasattr(U.fetch_massive_universe, "__wrapped__")
                            else U.fetch_massive_universe)
    params = sig.parameters
    assert params["keep_exchanges"].default == U.MAJOR_EXCHANGES
    assert params["cache_name"].default == "massive_universe"
    assert U.MAJOR_EXCHANGES == frozenset({"XNYS", "XNAS", "ARCX", "BATS", "XASE"})


def test_the_two_nasdaq_universes_are_not_the_same_list():
    """QQQ is 100-odd names; the listing is thousands. If someone points one at
    the other the dropdown grows a duplicate that looks like a choice."""
    from supply_demand import demand_reentry as dr
    assert dr.UNIVERSES["qqq"][0] != dr.UNIVERSES["nasdaq"][0]
    n100_lo, n100_hi = U._EXPECTED_COUNTS["nasdaq100"]
    nl_lo, _ = U._EXPECTED_COUNTS["nasdaq_listed"]
    assert nl_lo > n100_hi


def test_themes_are_KEPT_because_no_index_carries_those_names():
    """IONQ, OKLO, SMR and QBTS are NYSE-listed and in no S&P tier, so `nasdaq`
    does not carry them either — measured 2026-08-20. Deleting the theme
    entries would silently drop them from every board."""
    from supply_demand import demand_reentry as dr
    assert "themes" in dr.UNIVERSES
    assert "sp1500_plus" in dr.UNIVERSES


def test_themes_sort_LAST_so_the_index_choices_lead():
    from supply_demand import demand_reentry as dr
    keys = list(dr.UNIVERSES)
    assert keys[-1] == "themes"
    assert keys.index("sp500") < keys.index("sp1500")
    assert keys.index("qqq") < keys.index("sp1500")


def test_full_is_russell1000_union_sp1500_plus_curated_plus_themes(fake_lists):
    """'full' exists so the scanner's net matches the demand board's (Ajay
    2026-08-25). Every layer must survive the union — losing sp1500 here would
    silently shrink the SEPA page back to the 1,001-name scan."""
    got = set(U.load_universe("full"))
    for part in ("russell1000", "sp1500", "curated", "themes"):
        assert set(fake_lists[part]) <= got, f"'full' dropped {part}"


def test_full_alias_only_names_known_components(fake_lists):
    assert U._UNIVERSE_ALIASES["full"] == ("russell1000", "sp1500", "curated", "themes")
    for part in U._UNIVERSE_ALIASES["full"]:
        assert part in U._KNOWN_COMPONENTS, f"alias names unknown component {part}"


# ---------------------------------------------------------------------------
# Symbol fates at the universe chokepoint (2026-08-25)
#
# Most components are 30-day-cached fetches, so a rename or delisting sits in
# the cached lists long after the fact — SMAR was dead in the universe for 19
# months. _resolve_fates() runs inside _with_benchmarks(), which every
# load_universe path funnels through, so the caches never need to be right.
# ---------------------------------------------------------------------------
def test_resolve_fates_maps_renames_to_the_live_symbol():
    assert U._resolve_fates(["DOOO"]) == ["DOO"]
    assert U._resolve_fates(["IAC"]) == ["PPLI"]


def test_resolve_fates_dedups_old_and_new_when_both_present():
    """IAC and PPLI were BOTH in the universe (the fetched list carried the
    new name, the cache still carried the old) — one company, one slot."""
    assert U._resolve_fates(["IAC", "PPLI"]) == ["PPLI"]
    assert U._resolve_fates(["PPLI", "IAC"]) == ["PPLI"]


def test_resolve_fates_drops_verified_delistings():
    out = U._resolve_fates(["SMAR", "CFLT", "EA", "AVB", "CWEN-A", "NVDA"])
    assert out == ["NVDA"]


def test_resolve_fates_leaves_ordinary_symbols_untouched_in_order():
    """NEGATIVE: fate resolution must not reorder or rewrite live names."""
    syms = ["NVDA", "BF-A", "SMP", "FISV", "P", "Q"]
    assert U._resolve_fates(syms) == syms


def test_with_benchmarks_applies_fates_before_appending_anchors():
    out = U._with_benchmarks(["IAC", "EA", "NVDA"])
    assert out == ["PPLI", "NVDA", "SPY", "QQQ", "IWM"]


def test_env_var_universe_cannot_resurrect_a_dead_ticker(monkeypatch):
    """Every load_universe path goes through the chokepoint — including the
    SEPA_UNIVERSE literal override."""
    monkeypatch.setenv("SEPA_UNIVERSE", "SMAR,NVDA,DOOO")
    monkeypatch.delenv("SEPA_UNIVERSE_FILE", raising=False)
    out = U.load_universe()
    assert "SMAR" not in out
    assert "DOOO" not in out
    assert "DOO" in out
    assert "NVDA" in out
