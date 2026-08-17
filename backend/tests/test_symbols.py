"""Symbol identity — renames and per-provider spelling.

Ajay 2026-08-16: *"look at this issue with SATS stocks"*. The detail page said
"SATS looks delisted or acquired" while SATS traded at $91.89.

Two defects made a live company look dead, and both are guarded here:
  1. EchoStar renamed SATS -> ECHO (2026-06-24); Block renamed SQ -> XYZ
     (2025-01-21) and had been silently stale for **576 days**.
  2. Massive returns NOTHING for dash-form class shares (BRK-B, BF-B, MOG-A),
     which pushed them all onto the yfinance fallback without anyone noticing.

The splice guards matter most. A rename splice that joins the wrong series
fabricates price history for a chart real money is sized against, so the join
refuses on any discontinuity rather than guessing.

All synthetic. No network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")

from sepa import symbols as S  # noqa: E402


# ---------------------------------------------------------------------------
# resolve / former_names
# ---------------------------------------------------------------------------
def test_the_sats_case_resolves_to_the_live_symbol():
    assert S.resolve("SATS") == "ECHO"


def test_the_sq_case_that_was_wrong_for_576_days():
    assert S.resolve("SQ") == "XYZ"


def test_resolve_is_idempotent():
    """resolve(resolve(x)) must equal resolve(x) — the fetch path calls it on
    values that may already be resolved."""
    for s in ("SATS", "ECHO", "SQ", "XYZ", "NVDA"):
        assert S.resolve(S.resolve(s)) == S.resolve(s)


def test_an_ordinary_symbol_is_untouched():
    assert S.resolve("NVDA") == "NVDA"
    assert S.former_names("NVDA") == []


def test_case_and_whitespace_do_not_defeat_the_map():
    assert S.resolve(" sats ") == "ECHO"


def test_former_names_points_back_from_the_live_symbol():
    """The fetch path starts from the LIVE symbol and needs to find the old one
    to splice; a one-way map would leave ECHO with 37 bars of history."""
    assert S.former_names("ECHO") == ["SATS"]
    assert S.former_names("XYZ") == ["SQ"]


def test_rename_of_carries_the_evidence():
    r = S.rename_of("SATS")
    assert r["to"] == "ECHO"
    assert r["effective"] == "2026-06-24"
    assert r["evidence"], "every rename must record how it was verified"


# --- negatives ---
def test_rename_of_an_ordinary_symbol_is_none():
    assert S.rename_of("NVDA") is None
    assert S.rename_of("") is None


def test_empty_input_does_not_explode():
    assert S.resolve("") == ""
    assert S.resolve(None) is None
    assert S.former_names("") == []


def test_no_rename_target_is_itself_a_rename_key():
    """A chain (A->B, B->C) would silently resolve only one hop. Entries must be
    written direct, so no target may also be a key."""
    for old, (new, _e, _w) in S.RENAMES.items():
        assert new not in S.RENAMES, f"{old}->{new} chains; write it direct"


# ---------------------------------------------------------------------------
# Provider spelling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("canon,massive", [
    ("BRK-B", "BRK.B"), ("BF-B", "BF.B"), ("MOG-A", "MOG.A"), ("CWEN-A", "CWEN.A"),
])
def test_class_shares_are_dotted_for_massive(canon, massive):
    """Measured 2026-08-16: Massive returns None for every dash form and real
    bars for every dot form."""
    assert S.for_massive(canon) == massive


def test_class_shares_are_dashed_for_yahoo():
    assert S.for_yahoo("BRK.B") == "BRK-B"


def test_provider_spelling_is_idempotent():
    assert S.for_massive("BRK.B") == "BRK.B"
    assert S.for_yahoo("BRK-B") == "BRK-B"


def test_round_trip_returns_the_canonical_spelling():
    assert S.for_yahoo(S.for_massive("BRK-B")) == "BRK-B"


# --- negatives ---
def test_a_plain_symbol_is_never_rewritten():
    for s in ("NVDA", "AAPL", "F", "GOOGL"):
        assert S.for_massive(s) == s
        assert S.for_yahoo(s) == s


def test_a_multi_letter_suffix_is_not_a_share_class():
    """Only a SINGLE trailing letter is a class suffix. Rewriting anything else
    would invent a symbol."""
    assert S.for_massive("ABC-XY") == "ABC-XY"
    assert S.for_massive("BRK-") == "BRK-"
    assert S.for_massive("-B") == "-B"


def test_a_trailing_digit_is_not_a_share_class():
    assert S.for_massive("ABC-1") == "ABC-1"


def test_empty_spelling_input():
    assert S.for_massive("") == ""
    assert S.for_yahoo(None) is None


# ---------------------------------------------------------------------------
# The splice — where a wrong join fabricates history
# ---------------------------------------------------------------------------
from sepa import prices as P  # noqa: E402


def frame(dates, closes, opens=None):
    opens = opens or closes
    return pd.DataFrame(
        {"open": opens, "high": closes, "low": closes, "close": closes,
         "volume": [1_000] * len(closes)},
        index=pd.to_datetime(dates))


def test_the_real_sats_boundary_splices():
    """SATS ends 2026-06-23 at 103.915; ECHO opens 2026-06-24 at 101.16.
    Consecutive sessions, -2.6% overnight. Massive only carries ~37 bars under
    ECHO, so without this join a 200-day average is impossible."""
    old = frame(["2026-06-22", "2026-06-23"], [106.40, 103.915])
    new = frame(["2026-06-24", "2026-06-25"], [99.86, 97.19], opens=[101.16, 100.275])
    out = P.splice_history(old, new, "SATS->ECHO")
    assert len(out) == 4
    assert str(out.index[0].date()) == "2026-06-22"
    assert float(out["close"].iloc[-1]) == pytest.approx(97.19)


def test_the_sq_boundary_splices_across_a_market_holiday():
    """SQ ends Fri 2025-01-17; XYZ opens Tue 2025-01-21 — MLK Day in between.
    A same-session-only rule would refuse this real, clean rename."""
    old = frame(["2025-01-16", "2025-01-17"], [86.38, 86.96])
    new = frame(["2025-01-21", "2025-01-22"], [89.50, 87.48], opens=[88.06, 90.20])
    assert len(P.splice_history(old, new, "SQ->XYZ")) == 4


def test_overlapping_old_bars_are_dropped_not_duplicated():
    old = frame(["2026-06-23", "2026-06-24"], [103.9, 999.0])
    new = frame(["2026-06-24", "2026-06-25"], [99.86, 97.19], opens=[101.16, 100.0])
    out = P.splice_history(old, new, "x")
    assert len(out) == 3
    assert float(out.loc["2026-06-24", "close"]) == pytest.approx(99.86), \
        "the new series must win on any shared date"


def test_the_result_is_sorted():
    old = frame(["2026-06-23"], [103.9])
    new = frame(["2026-06-24"], [99.9], opens=[101.0])
    out = P.splice_history(old, new, "x")
    assert list(out.index) == sorted(out.index)


# --- negatives: the joins that must be REFUSED ---
def test_a_price_jump_at_the_boundary_refuses_the_splice():
    """A 10x jump on the rename date is a reverse split or a wrong RENAMES
    entry. Splicing would draw a cliff on a chart Ajay sizes against; a short
    history is the safe failure."""
    old = frame(["2026-06-23"], [10.0])
    new = frame(["2026-06-24"], [100.0], opens=[100.0])
    out = P.splice_history(old, new, "x")
    assert len(out) == 1, "must return the new series alone"


def test_a_long_hole_at_the_boundary_refuses_the_splice():
    """Months of silence between the two series is not a relabelling."""
    old = frame(["2026-01-05"], [100.0])
    new = frame(["2026-06-24"], [101.0], opens=[101.0])
    assert len(P.splice_history(old, new, "x")) == 1


def test_a_modest_overnight_move_still_splices():
    """The guard must not be so tight it refuses ordinary gaps. -2.6% (the real
    SATS case) and even -20% must pass."""
    old = frame(["2026-06-23"], [100.0])
    new = frame(["2026-06-24"], [80.0], opens=[80.0])
    assert len(P.splice_history(old, new, "x")) == 2


def test_missing_sides_are_handled():
    good = frame(["2026-06-24"], [101.0])
    assert P.splice_history(None, good, "x") is good
    assert P.splice_history(good, None, "x") is good
    assert P.splice_history(None, None, "x") is None
    empty = good.iloc[0:0]
    assert len(P.splice_history(empty, good, "x")) == 1


def test_new_series_starting_before_the_old_one_keeps_only_the_new():
    """Nothing in the old frame precedes the new series, so there is nothing to
    prepend — and certainly nothing to interleave."""
    old = frame(["2026-07-01"], [100.0])
    new = frame(["2026-06-24"], [101.0], opens=[101.0])
    assert len(P.splice_history(old, new, "x")) == 1


# ---------------------------------------------------------------------------
# yf_ticker — the OTHER thirty call sites
# ---------------------------------------------------------------------------
# Ajay 2026-08-16, from the deploy log minutes after the rename fix shipped:
#
#     ERROR HTTP Error 404: No fundamentals data found for symbol: SQ
#
# The price path resolved renames. Thirty-one other call sites still handed
# Yahoo the retired ticker, so Block kept its chart and lost its profile,
# fundamentals, catalysts, earnings date and analyst ratings — every one of
# which reads as "this company has no data", the same wrong story the delisted
# banner was telling.
def test_yf_ticker_resolves_the_rename():
    yf = pytest.importorskip("yfinance")
    assert S.yf_ticker("SQ").ticker == "XYZ"
    assert S.yf_ticker("SATS").ticker == "ECHO"


def test_yf_ticker_leaves_an_ordinary_symbol_alone():
    pytest.importorskip("yfinance")
    assert S.yf_ticker("NVDA").ticker == "NVDA"


def test_yf_ticker_uses_yahoos_class_share_spelling():
    pytest.importorskip("yfinance")
    assert S.yf_ticker("BRK.B").ticker == "BRK-B"
    assert S.yf_ticker("BRK-B").ticker == "BRK-B"


def test_yf_ticker_passes_index_symbols_through_untouched():
    """^VIX and friends must survive a blanket application of this helper."""
    pytest.importorskip("yfinance")
    assert S.yf_ticker("^VIX").ticker == "^VIX"
    assert S.yf_ticker("^GSPC").ticker == "^GSPC"


# --- the source guard ---
def _backend_root():
    """Walk up for the backend package. tests/ sits at a different depth inside
    the api container than in the repo, and hardcoding parents[1] broke a
    pre-commit hook once already."""
    here = Path(__file__).resolve()
    for cand in [here.parent] + list(here.parents):
        if (cand / "sepa" / "symbols.py").exists():
            return cand
    return None


def test_no_module_calls_yf_Ticker_directly():
    """Every call site must go through yf_ticker so a rename can never again
    take out a company's fundamentals while its chart keeps working.

    sepa/prices.py is the one exception, and it is deliberate: the rename
    splice has to fetch the OLD symbol on purpose.
    """
    root = _backend_root()
    if root is None:
        pytest.skip("backend root not found (running outside the repo layout)")

    allowed = {root / "sepa" / "prices.py", root / "sepa" / "symbols.py"}
    offenders = []
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if ".venv" in parts or "tests" in parts or path in allowed:
            continue
        try:
            src = path.read_text()
        except Exception:
            continue
        if "yf.Ticker(" in src:
            offenders.append(str(path.relative_to(root)))

    assert not offenders, (
        "these call yf.Ticker directly and will 404 on a renamed ticker — "
        "use sepa.symbols.yf_ticker instead: " + ", ".join(sorted(offenders)))


def test_prices_keeps_its_direct_call_on_purpose():
    """The guard above must not be 'fixed' by routing prices.py through the
    resolver — the splice fetches the OLD symbol by design, and resolving it
    would silently drop every pre-rename bar."""
    root = _backend_root()
    if root is None:
        pytest.skip("backend root not found")
    assert "yf.Ticker(" in (root / "sepa" / "prices.py").read_text()
