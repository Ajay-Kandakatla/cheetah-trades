"""The breakout board ranked by income + growth, quarter over quarter (2026-09-12).

Ajay, reversing the stage gate he had asked for three hours earlier:
*"May show any stage but prioritize income and growth only quarter over
quarter"*.

Two changes, and the second is the load-bearing one:
  • the stage gate is OFF — every stage shows, the Stage column tells him which;
  • the ORDER is the income+growth blend, computed over every candidate BEFORE
    the top-N cut.

MEASURED before shipping (see docs/sepa/breakout_qoq_rank.md for the scripts):
  · sequential and quarterly-YoY are genuinely different orders — Spearman
    0.58 revenue, 0.37 EPS
  · 11 of the top 20 on the RAW percentage were bought by a prior-quarter EPS
    under $0.10 a share, NINE of them tiny-POSITIVE rather than negative
  · median sequential revenue runs +5.3% for a fiscal Q1→Q2 transition against
    −4.0% for Q4→Q1 — nine points of pure calendar
  · the raw sequential leaderboard did WORSE next quarter than the rest of the
    board (median +0.4%, 50% positive, vs a placebo of +24.0%, 70% positive)
"""
from __future__ import annotations

import inspect

from sepa import breakout as B


def r(sym, **kw):
    base = {"symbol": sym, "breakout_count": 3, "rs_rank": 50,
            "days_since_breakout": 3, "ai_sector_rank": None,
            "qoq_score": None, "rank_income": None, "stage": 2}
    base.update(kw)
    return base


# ── ordering ───────────────────────────────────────────────────────────────
def test_the_higher_blend_ranks_first():
    rows = [r("LOW", qoq_score=20.0, rank_income=5.0),
            r("HIGH", qoq_score=95.0, rank_income=60.0)]
    rows.sort(key=B._qoq_key)
    assert [x["symbol"] for x in rows] == ["HIGH", "LOW"]


def test_a_name_that_EARNED_money_outranks_one_that_did_not_even_on_a_lower_blend():
    """You cannot prioritise income by ignoring whether there is any. MEASURED:
    only 90 of the 250 rows had a profitable prior quarter, so an EPS
    percentage simply does not exist for most of a breakout board. Names with
    one rank as a block above names without, and both blocks are then ordered
    by the same blend — rather than inventing a number for the rest."""
    rows = [r("NOEPS", qoq_score=99.0, rank_income=None),
            r("EARNS", qoq_score=55.0, rank_income=30.0)]
    rows.sort(key=B._qoq_key)
    assert [x["symbol"] for x in rows] == ["EARNS", "NOEPS"]


def test_NEGATIVE_an_UNSCORED_name_sorts_LAST_and_never_as_a_zero():
    """A zero would rank a name we know nothing about above every measured
    decliner — an unknown reading as the favourable state."""
    rows = [r("UNKNOWN", qoq_score=None),
            r("BAD", qoq_score=1.0, rank_income=-80.0)]
    rows.sort(key=B._qoq_key)
    assert [x["symbol"] for x in rows] == ["BAD", "UNKNOWN"]


def test_NEGATIVE_unscored_sinks_even_among_rows_that_ALL_lack_an_income_leg():
    """The income block masks the unknown guard in the simple case, so this
    pins the guard on its own: two rows with no EPS number, one scored on
    growth alone and one scored on nothing at all."""
    rows = [r("NOSCORE", qoq_score=None, rank_income=None),
            r("GROWTH_ONLY", qoq_score=10.0, rank_income=None)]
    rows.sort(key=B._qoq_key)
    assert [x["symbol"] for x in rows] == ["GROWTH_ONLY", "NOSCORE"]


def test_the_AI_SECTOR_rule_survives_INSIDE_the_ranking_not_instead_of_it():
    """His 2026-06-25 standing rule. It breaks ties between equal blends; it
    does not override the blend, or MRVL-class names would ride a fake number
    to the top on sector alone."""
    rows = [r("PLAIN", qoq_score=80.0, rank_income=1.0, ai_sector_rank=None),
            r("AI", qoq_score=80.0, rank_income=1.0, ai_sector_rank=0),
            r("BETTER", qoq_score=90.0, rank_income=1.0, ai_sector_rank=None)]
    rows.sort(key=B._qoq_key)
    assert [x["symbol"] for x in rows] == ["BETTER", "AI", "PLAIN"]


def test_recency_is_kept_as_a_TIEBREAK_not_discarded():
    rows = [r("OLD", qoq_score=70.0, rank_income=1.0, days_since_breakout=30),
            r("FRESH", qoq_score=70.0, rank_income=1.0, days_since_breakout=0)]
    rows.sort(key=B._qoq_key)
    assert [x["symbol"] for x in rows] == ["FRESH", "OLD"]


def test_NEGATIVE_an_undated_breakout_still_sorts_after_a_dated_one_on_a_tie():
    rows = [r("NODATE", qoq_score=70.0, rank_income=1.0, days_since_breakout=None),
            r("DATED", qoq_score=70.0, rank_income=1.0, days_since_breakout=40)]
    rows.sort(key=B._qoq_key)
    assert [x["symbol"] for x in rows] == ["DATED", "NODATE"]


# ── where it runs ──────────────────────────────────────────────────────────
def test_THE_FUNDAMENTALS_ARE_READ_BEFORE_THE_CUT():
    """The whole change. The overlay used to run AFTER `rows[:top]`, so ranking
    on it would have been a growth-ranked view OF A RECENCY-RANKED SAMPLE —
    250 rows reordered out of 2,840 candidates that had already been filtered
    on other grounds. Exactly the cap trap the recency sort hit this morning."""
    src = inspect.getsource(B.board)
    assert src.index("_attach_fundamentals(rows)") < src.index("rows.sort(key=")
    assert src.index("rows.sort(key=") < src.index("rows = rows[:top]")


def test_the_percentiles_are_computed_over_EVERY_candidate_not_the_survivors():
    """A score means "where it sits among everything that broke out". Scoring
    after the cut would make it "where it sits among the 250 that happened to
    survive", which is a different and much weaker statement."""
    src = inspect.getsource(B._attach_fundamentals)
    assert "score_board" in src
    board_src = inspect.getsource(B.board)
    assert board_src.index("_attach_fundamentals(rows)") < board_src.index("rows = rows[:top]")


def test_BETA_deliberately_stays_AFTER_the_cut():
    """The fundamentals read is one projected Mongo query and is cheap to widen
    from 250 names to 2,840. Beta loads PRICES per name and is not."""
    src = inspect.getsource(B.board)
    assert src.index("rows = rows[:top]") < src.index("from sepa import beta as _beta")


def test_the_ranked_numbers_are_held_APART_from_the_displayed_ones():
    """The page shows the plain sequential move; the rank uses the seasonally
    referenced one. A board that shows one number and sorts by another without
    saying so is a board he cannot reason about — so they live in different
    keys and the row carries `rank_basis`."""
    src = inspect.getsource(B._attach_fundamentals)
    for key in ('x["growth_qoq"]', 'x["rank_growth"]', 'x["rank_basis"]'):
        assert key in src
    assert 'income_key="rank_income"' in src


# ── the payload ────────────────────────────────────────────────────────────
def test_the_board_reports_how_much_of_the_ranking_it_could_ANSWER():
    """A board ordered by income where most names have no income must say so."""
    src = inspect.getsource(B.board)
    for key in ('"qoq_scored"', '"qoq_income"', '"qoq_growth"',
                '"qoq_seasonal_basis"', '"qoq_seasonal_echo"', '"sort"'):
        assert key in src


def test_the_sort_is_selectable_and_defaults_to_his_ask():
    sig = inspect.signature(B.board)
    assert sig.parameters["sort"].default == B.SORT_QOQ
    assert set(B.SORTS) == {"qoq", "recent"}


def test_NEGATIVE_an_unknown_sort_name_falls_back_instead_of_raising():
    """A bad query string must not 500 a board he opens every morning."""
    src = inspect.getsource(B.board)
    assert "sort if sort in SORTS else SORT_QOQ" in src


def test_every_stage_may_show():
    sig = inspect.signature(B.board)
    assert sig.parameters["stages"].default is False


# ── the plumbing that had to exist first ───────────────────────────────────
def test_the_quarterly_series_ARE_PERSISTED_on_every_source_path():
    """They were fetched and thrown away — `_from_hybrid` consumed them into
    sales/earnings-quality and returned nothing, so MEASURED 2026-09-12 exactly
    0 of 250 board rows carried one and the sequential read was unanswerable."""
    from sepa import canslim
    src = inspect.getsource(canslim)
    for path in ("_from_hybrid", "_from_massive", "_from_yfinance", "_empty"):
        body = inspect.getsource(getattr(canslim, path))
        for key in ('"rev_q_series"', '"eps_q_series"', '"ni_q_series"'):
            assert key in body, f"{path} must carry {key}"


def test_NEGATIVE_the_yfinance_path_no_longer_returns_a_PERMANENT_blank():
    """20% of the cache — 746 of 3,738 documents — has `_source: yfinance`, and
    those returned None for every series. The Sunday refresh could never fill
    them; only an out-of-band backfill reached them at all."""
    from sepa import canslim
    body = inspect.getsource(canslim._from_yfinance)
    assert '"rev_q_series": None' not in body
    assert "_q_series_yf(t," in body


def test_the_series_ride_the_SAME_projected_query_not_a_second_read():
    from sepa import research
    for f in ("fundamentals.rev_q_series", "fundamentals.eps_q_series",
              "fundamentals.ni_q_series"):
        assert f in research.DECISION_FIELDS


def test_NEGATIVE_the_backfill_never_bumps_cached_at():
    """Bumping it would extend the life of stale fundamentals — the opposite of
    the point. It writes the three series and nothing else."""
    from sepa import qoq
    src = inspect.getsource(qoq.backfill)
    assert '"$set": sets' in src
    # `sets` is built from the three series keys and nothing else, so no write
    # path can reach cached_at.
    assert 'sets = {f"fundamentals.{k}": m.get(k)' in src
    for k in ('"q_period_series"', '"rev_q_series"', '"eps_q_series"', '"ni_q_series"'):
        assert k in src
    assert '"cached_at"' not in src


def test_the_backfill_is_WIRED_TO_CRON_not_just_available():
    """It shipped unwired once: coverage sat at 210 of 3,738 documents (5.6%),
    so the board ranked whatever slice the cache happened to hold and called it
    the market. Two lines — a daily fill and a weekly WIDEN, because the daily
    one only touches names with no series at all and a document stored under
    the old 8-quarter fetch would otherwise keep 8 forever."""
    from pathlib import Path
    cron = Path(__file__).resolve().parents[1] / "crontab"
    text = cron.read_text()
    assert "sepa.qoq backfill --limit" in text
    assert "sepa.qoq backfill --all" in text
