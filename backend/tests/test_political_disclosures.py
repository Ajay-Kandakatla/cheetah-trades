"""The curated political list — validation, the JSON↔TS contract, the board.

Ajay 2026-09-20 asked for the 🏛️ watch. The watch needs to know which tickers
are ALREADY on the list, and a cron container cannot read TypeScript, so the
list moved to ``backend/political/disclosures.json`` and the TS is generated.

The assertions that matter here are the NEGATIVE ones. ``validate`` exists to
stop the one failure this list can actually have: a row that CLAIMS a
government equity stake without naming the agency or stating the size. The
2026-09-19 note says it in words — "The administration is weighing a stake is
not a stake" — and GLND is on the list precisely so the chip can say "we
looked, and there is no deal". A validator that let that through would make
every chip on the page mean nothing.
"""
from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from political import disclosures as D
from political import api as API

TODAY = date(2026, 9, 20)


def _row(**over):
    base = {"ticker": "TEST", "company": "Test Co", "sector": "Test",
            "categories": ["inferred"], "disclosureBand": None, "govtStake": None,
            "notes": None, "asOf": None, "addedOn": None}
    base.update(over)
    return base


# ── the file itself ──────────────────────────────────────────────────────────

def test_the_committed_json_is_valid():
    assert D.validate(D.entries()) == []


def test_the_list_is_forty_four_rows_with_the_eight_september_additions():
    rows = D.entries()
    assert len(rows) == 44
    added = [r["ticker"] for r in rows if r["addedOn"] == "2026-09-19"]
    assert sorted(added) == sorted(["MP", "USAR", "LAC", "TMQ", "ALOY",
                                    "CRML", "GLND", "UUUU"])


def test_MP_carries_the_agency_and_the_size():
    assert D.by_ticker()["MP"]["govtStake"] == "DoD 15%"


@pytest.mark.parametrize("ticker", ["GLND", "CRML", "UUUU"])
def test_the_greenland_cohort_is_inferred_and_claims_no_stake(ticker):
    """The single most important row-level fact on the list: a stock that
    RALLIED on an Arctic headline is not a stock the government invested in."""
    row = D.by_ticker()[ticker]
    assert row["categories"] == ["inferred"]
    assert row["govtStake"] is None


def test_every_row_carries_every_key():
    for row in D.entries():
        assert set(row) == set(D.ROW_KEYS), row.get("ticker")


# ── validate: the negatives are the point ────────────────────────────────────

def test_a_stake_on_a_row_that_is_not_a_government_investment_is_rejected():
    errs = D.validate([_row(categories=["govt_contractor"], govtStake="DoD 15%")])
    assert any("not govt_investment" in e for e in errs)


def test_a_stake_with_no_named_agency_is_rejected():
    errs = D.validate([_row(categories=["govt_investment"], govtStake="15%")])
    assert any("names no agency" in e for e in errs)


def test_a_stake_with_no_stated_percentage_is_rejected():
    errs = D.validate([_row(categories=["govt_investment"],
                            govtStake="Commerce is weighing a stake")])
    assert any("states no percentage" in e for e in errs)


def test_a_duplicate_ticker_is_rejected():
    errs = D.validate([_row(ticker="MP"), _row(ticker="mp")])
    assert any("duplicate ticker" in e for e in errs)


def test_an_unknown_category_is_rejected():
    errs = D.validate([_row(categories=["potus_friend"])])
    assert any("unknown category" in e for e in errs)


def test_an_empty_category_list_is_rejected():
    assert any("non-empty" in e for e in D.validate([_row(categories=[])]))


@pytest.mark.parametrize("bad", ["2026-13-01", "19/09/2026", "tomorrow", 20260919])
def test_a_bad_date_is_rejected(bad):
    assert any("YYYY-MM-DD" in e for e in D.validate([_row(addedOn=bad)]))
    assert any("YYYY-MM-DD" in e for e in D.validate([_row(asOf=bad)]))


def test_a_missing_ticker_or_company_is_rejected():
    assert any("missing ticker" in e for e in D.validate([_row(ticker="")]))
    assert any("missing company" in e for e in D.validate([_row(company=None)]))


def test_a_clean_row_produces_no_errors():
    assert D.validate([_row(categories=["govt_investment"],
                            govtStake="Treasury 9.9%")]) == []


# ── is_new — the same rule as the TS ─────────────────────────────────────────

def test_is_new_inside_and_outside_the_window():
    assert D.is_new({"addedOn": "2026-09-19"}, date(2026, 9, 19)) is True
    assert D.is_new({"addedOn": "2026-09-19"}, date(2026, 10, 2)) is True   # day 13
    assert D.is_new({"addedOn": "2026-09-19"}, date(2026, 10, 3)) is True   # day 14
    assert D.is_new({"addedOn": "2026-09-19"}, date(2026, 10, 4)) is False  # day 15


def test_a_seed_row_a_typo_and_a_future_date_are_never_new():
    assert D.is_new({"addedOn": None}, TODAY) is False
    assert D.is_new({}, TODAY) is False
    assert D.is_new({"addedOn": "tomorrow"}, TODAY) is False
    assert D.is_new({"addedOn": "2027-01-01"}, TODAY) is False


# ── the generator contract ───────────────────────────────────────────────────

def test_the_generated_files_are_up_to_date_with_the_json():
    from scripts import gen_political_ts as G
    assert G.main(["--check"]) == 0


def test_the_generated_ts_says_it_is_generated_and_names_the_source():
    from scripts import gen_political_ts as G
    text = G.OUT_TS.read_text(encoding="utf-8")
    assert "GENERATED by backend/scripts/gen_political_ts.py" in text
    assert "DO NOT EDIT" in text
    assert "backend/political/disclosures.json" in text


def test_the_generated_json_is_byte_equal_to_the_source():
    from scripts import gen_political_ts as G
    assert G.OUT_JSON.read_text(encoding="utf-8") == G.SRC_JSON.read_text(encoding="utf-8")


def test_check_fails_when_a_row_changes(monkeypatch, tmp_path):
    """The mutation proof: change one row in the SOURCE and --check must go
    red. A generator whose --check cannot fail is decoration."""
    from scripts import gen_political_ts as G
    rows = json.loads(G.SRC_JSON.read_text(encoding="utf-8"))
    rows[0]["company"] = "Nvidia Corporation (edited)"
    fake = tmp_path / "disclosures.json"
    fake.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(G, "SRC_JSON", fake)
    assert G.main(["--check"]) == 1


def test_check_fails_when_the_generated_ts_is_hand_edited(monkeypatch, tmp_path):
    from scripts import gen_political_ts as G
    stale = tmp_path / "politicalDisclosures.ts"
    stale.write_text("// somebody edited this by hand\n", encoding="utf-8")
    monkeypatch.setattr(G, "OUT_TS", stale)
    assert G.main(["--check"]) == 1


def test_the_generated_ts_carries_every_row_and_the_new_export():
    from scripts import gen_political_ts as G
    text = G.OUT_TS.read_text(encoding="utf-8")
    for ticker in ("NVDA", "INTC", "GLND", "MP", "ALOY"):
        assert f"ticker: '{ticker}'" in text, ticker
    assert text.count("  { ticker: ") == 44
    for export in ("POLITICAL_DISCLOSURES", "POLITICAL_DISCLOSURE_TOTAL_COUNT",
                   "POLITICAL_DISCLOSURE_SOURCE_NOTE", "getPoliticalDisclosure",
                   "isNewDisclosure", "getPoliticalChipFlags", "recentDisclosures",
                   "NEW_DISCLOSURE_DAYS"):
        assert f"export const {export}" in text or f"export function {export}" in text, export


def test_an_invalid_json_stops_the_generator_rather_than_writing_a_bad_ts(monkeypatch, tmp_path):
    from scripts import gen_political_ts as G
    rows = json.loads(G.SRC_JSON.read_text(encoding="utf-8"))
    rows[0]["categories"] = ["not_a_category"]
    fake = tmp_path / "disclosures.json"
    fake.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(G, "SRC_JSON", fake)
    with pytest.raises(SystemExit):
        G.main([])


# ── the board payload ────────────────────────────────────────────────────────

def test_board_groups_every_row_and_counts_a_two_category_row_twice(monkeypatch):
    monkeypatch.setattr(API.W, "candidates", lambda **kw: [])
    monkeypatch.setattr(API.W, "last_run", lambda **kw: None)
    b = API._board(200, TODAY)
    assert len(b["entries"]) == 44
    assert set(b["groups"]) == set(D.CATEGORIES)
    assert sum(len(v) for v in b["groups"].values()) == 47   # 44 rows + INTC/PLTR/HOOD ×2
    assert "INTC" in b["groups"]["potus_family"] and "INTC" in b["groups"]["govt_investment"]


def test_board_flags_the_eight_new_rows_and_says_it_is_heuristic(monkeypatch):
    monkeypatch.setattr(API.W, "candidates", lambda **kw: [])
    monkeypatch.setattr(API.W, "last_run", lambda **kw: None)
    b = API._board(200, TODAY)
    assert sum(1 for e in b["entries"] if e["is_new"]) == 8
    assert b["watch"]["heuristic"] is True
    assert b["watch"]["window_hours"] == 24
    assert "NOT a measured signal" in b["watch"]["note"]
    assert len(b["watch"]["queries"]) == 7


def test_board_serves_candidates_verbatim_including_an_unnamed_one(monkeypatch):
    rows = [{"ticker": None, "resolution": "unnamed", "pattern": "equity_stake",
             "agency": "Commerce", "size": None, "pushed": False, "heuristic": True,
             "headline": {"title": "t", "url": "u", "source": "s", "published": 1}}]
    monkeypatch.setattr(API.W, "candidates", lambda **kw: rows)
    monkeypatch.setattr(API.W, "last_run", lambda **kw: "2026-09-20T06:35:00+00:00")
    b = API._board(200, TODAY)
    assert b["candidates"] == rows
    assert b["watch"]["last_run"] == "2026-09-20T06:35:00+00:00"


def test_entries_are_copies_so_a_caller_cannot_corrupt_the_cache():
    first = D.entries()
    first[0]["ticker"] = "MUTATED"
    assert D.entries()[0]["ticker"] != "MUTATED"


def test_scrub_kills_a_nan_before_it_reaches_the_browser():
    assert API._scrub({"a": float("nan"), "b": [float("inf"), 1.5]}) == {"a": None, "b": [None, 1.5]}
