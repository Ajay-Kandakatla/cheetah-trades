"""Pattern-scan contracts — source guards for the universe widening.

See `docs/sepa/patterns_scan_universe.md` for the spec these enforce, and
`docs/supply_demand/pattern_demand_gate.md` for the gate they refuse to let
drift. Run before AND after any change to `patterns/scan.py`:

    docker compose exec api python -m pytest /app/tests/test_patterns_contracts.py -v

Tests are intentionally cheap — no Mongo, no price cache, no detectors.
Constants are asserted by re-importing the module and behaviour is asserted by
reading the source; the behavioural counterpart lives in
`test_patterns_universe.py`.

WHY THIS FILE EXISTS
--------------------
Ajay, 2026-09-10: *"The chart patterns are only looking at qualified sepa list
I want them to run against all"*. The narrowing was not a setting, it was three
lines of code: an early `return` on the SEPA scan's rows, a `[:200]` slice, and
a verdict universe built from the qualifier set. Each is cheap to reintroduce
by accident during a refactor and silent when it happens — the board just gets
smaller. So each is pinned to a line of source here, where a regression fails
loudly instead of quietly shrinking what he sees.

The second half of the file guards the opposite direction. Widening the scan
widens the BOARD; it must never widen the PHONE. The $1B zone floor and the
demand-band gate are asserted unchanged, so "we ran against all" can never be
delivered by loosening a gate.
"""
from __future__ import annotations

import inspect
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# patterns/scan imports pandas + detector at module load (py3.9 host lacks
# pandas) — stub before import, like the other pattern tests.
try:
    import pandas  # noqa: F401
except ImportError:                                   # pragma: no cover
    sys.modules["pandas"] = types.ModuleType("pandas")
try:
    from patterns import detector  # noqa: F401
except Exception:                                     # pragma: no cover
    stub = types.ModuleType("patterns.detector")
    stub.VALIDATION_HORIZON = 21
    stub.DETECTORS = {}
    sys.modules["patterns.detector"] = stub

from patterns import pattern_alerts as PA
from patterns import scan
from supply_demand import zone_store as ZS


# ── the universe can never narrow back to the qualifier list ─────────────────

def test_the_universe_is_not_built_solely_from_the_sepa_scan():
    """DEFECT 1, pinned to the line that caused it. `_universe_with_context`
    used to `return list(ctx.keys()), ctx` the moment the SEPA scan had rows,
    so the universe loader below it was dead code and 286 full-universe names
    were never scanned. That early return must not come back."""
    src = inspect.getsource(scan._universe_with_context)
    assert "return list(ctx.keys()), ctx" not in src, (
        "the SEPA scan's rows must not short-circuit the universe loader — "
        "that is the exact narrowing Ajay reported on 2026-09-10")
    assert "load_universe(" in src, "the universe loader must be reached"


def test_the_universe_loader_is_asked_for_the_full_universe():
    """`full` is the alias the SEPA scan, zone_store and the demand boards all
    run (2,650 names on 2026-09-10), so the pattern board can never be narrower
    than the pages that link into it. `russell1000` is allowed to survive ONLY
    as the last-resort no-context fallback below the union — asking for it
    first would be a fallback that loses names, which is not a fallback."""
    assert scan.UNIVERSE_MODE == "full"
    src = inspect.getsource(scan._universe_with_context)
    assert "load_universe(UNIVERSE_MODE)" in src
    assert src.index("load_universe(UNIVERSE_MODE)") < src.index('load_universe("russell1000")')


def test_the_universe_is_a_union_not_a_replacement():
    """Both sides must survive: the loader supplies reach, the SEPA scan
    supplies the context the board's chips and the scan's own sort read."""
    src = inspect.getsource(scan._universe_with_context)
    assert "ctx" in src, "SEPA context must still be built"
    # The symbol list has to be assembled from both sources, so the function
    # cannot end on either one alone.
    assert src.count("return") >= 2


def test_verdict_universe_keeps_the_symbol_list_it_is_handed():
    """DEFECT 3, pinned to its line. `_verdict_universe` used to open with
    `_, ctx = _universe_with_context()` — throwing away the symbol list and
    covering only qualifiers ∪ holdings ∪ buyable ∪ at_pivot ∪ leader (313
    names) while the SEPA page listed 2,365 rows, so the 📐 chip was blank on
    everything else."""
    src = inspect.getsource(scan._verdict_universe)
    assert "_, ctx = _universe_with_context()" not in src, (
        "the verdict universe must keep the symbols, not just the context")
    assert '"universe"' in src or "'universe'" in src, (
        "plain universe members need their own source tag")


def test_every_existing_verdict_source_tag_is_still_emitted():
    """The Portfolio / Leaderboard cross-link chips render off these exact
    strings (SOURCE_META in PatternsPage.tsx). Adding `universe` must not cost
    any of them."""
    src = inspect.getsource(scan._verdict_universe)
    for tag in ("qualifier", "buyable", "holding", "at_pivot", "leader"):
        assert '"%s"' % tag in src, "verdict source tag %r went missing" % tag


# ── the results cap ──────────────────────────────────────────────────────────

def test_max_results_exceeds_a_realistic_n_found():
    """DEFECT 2. The old literal was 200 against a measured n_found of 239, so
    the cap BOUND on an ordinary day and the sort (confirmed → is_candidate →
    rs_rank) made the 39 discards skew non-qualifier — the very names he asked
    for, and the list `pattern_alerts` reads.

    The headroom is real, not aspirational: a result row measures ~600 B, so
    2,000 rows is ~1.2 MB against Mongo's 16 MB document limit."""
    assert scan.MAX_RESULTS >= 2000, (
        "MAX_RESULTS must sit far above a realistic n_found (239 measured "
        "2026-09-10), or the board silently drops non-qualifiers again")


def test_the_results_slice_goes_through_max_results():
    """No literal slice. A hard-coded number here is invisible on the board and
    was the whole defect."""
    src = inspect.getsource(scan._run_scan)
    assert "MAX_RESULTS" in src
    assert "[:200]" not in src


def test_the_cap_counts_what_it_drops():
    """House rule: every counter that drops names is counted and reportable, so
    a blind run never reads as a quiet market."""
    src = inspect.getsource(scan._run_scan)
    assert "n_dropped" in src, (
        "the payload must record how many hits the cap discarded")
    assert '"n_found": len(all_found)' in src, (
        "n_found stays the HONEST pre-cap total, not the persisted length")
    assert '"n_results"' in src and '"max_results"' in src, (
        "the payload states what it kept and the cap it kept it under, so a "
        "truncated board can be recognised from the payload alone")
    assert "log.warning" in src, (
        "a bound cap must be loud in the log too — it reads exactly like a "
        "quiet market otherwise")


def test_symbols_scanned_is_the_universe_size():
    """The number that answers 'did it really run against all?'."""
    src = inspect.getsource(scan._run_scan)
    assert '"symbols_scanned": len(symbols)' in src


# ── nothing here is allowed to move the phone ────────────────────────────────

def test_mongo_doc_ids_and_alert_kind_unchanged():
    """Renaming a doc id or an alert kind orphans the dedupe state and either
    re-pushes everything or goes silent. Neither is acceptable on his phone."""
    src = inspect.getsource(scan)
    assert '"_id": "latest"' in src
    assert '"_id": "qualifier_verdicts"' in src
    assert PA.SCAN_DOC_ID == "latest"          # NOT the newest by generated_at
    assert PA.KIND == "pattern_alert"
    assert PA.STATE_COLL == "pattern_alerts"


def test_the_zone_cap_floor_matches_the_one_he_set():
    """Ajay 2026-09-03: *"billion or at least bigger than a billion"*. 1,242 of
    the 2,650 names now swept have no zone doc BY HIS CHOICE. Widening the scan
    widens the board; it must not reach down to sub-$1B names on the phone."""
    # Ajay 2026-09-10: "make cap 700 m". The POINT of this test is that the
    # patterns widening never moved his floor on its own — it is his number,
    # changed only when he says so, and every S/D path must carry the same one
    # (tests/test_cap_floor.py pins them equal).
    from supply_demand import demand_alerts as DA
    assert ZS.MIN_CAP_USD == 700_000_000.0
    assert DA.MIN_CAP_USD == ZS.MIN_CAP_USD


def test_the_demand_gate_is_untouched():
    """docs/supply_demand/pattern_demand_gate.md. A pattern reaches the phone
    only standing at a level — inside an eligible demand band, or reversing off
    one and still ≤5% above its top. Widening the scan must never be paid for
    by loosening this."""
    assert PA.MAX_ZONE_BUILDS == 40
    assert PA.NEAR_MAX_PCT == 5.0              # == quick_bounce.NEAR_MAX_PCT
    assert PA.FRESH_BARS == 2
    src = inspect.getsource(PA)
    assert "in_demand_read" in src and "bounce_read" in src


def test_the_demand_gate_still_fails_closed_with_two_counters():
    """A name with no zone coverage sends nothing and is counted SEPARATELY
    from a name that is covered and simply not at a level — so a blind morning
    can never be mistaken for a quiet one. More names in the scan means more
    ways to be blind, which makes this guard matter more, not less."""
    src = inspect.getsource(PA)
    assert "skipped_no_zone" in src
    assert "skipped_no_demand" in src
