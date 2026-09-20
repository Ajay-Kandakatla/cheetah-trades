"""Sector day-tags — Ajay 2026-09-19.

    "Also for the hot sectors if you see any postive news I would like you to
     see a bullish and bearish case result for a stocks and add it to the
     sector as a tag for that day."

The tests that matter most here are the ones that stop this from quietly
turning into a recommendation engine:

  * a tag never ships with only one side of the argument written
  * the name is picked by whether it HAS news, never by how far it moved
  * nothing here reaches into supply_demand/ or trading/
  * the model is told, in the prompt this file reads back, that it may not
    introduce a number
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from rotation import sector_news_tags as SNT


NOW = 1_789_800_000.0          # pinned; nothing below reads the wall clock
HOUR = 3600.0


def _item(title, published, source="Reuters", summary="s"):
    return {"title": title, "published": published, "source": source,
            "summary": summary, "url": "https://example.test/x"}


# ---------------------------------------------------------------------------
# _fresh
# ---------------------------------------------------------------------------
class TestFresh:
    def test_keeps_a_headline_inside_the_window_newest_first(self):
        got = SNT._fresh([_item("old", NOW - 20 * HOUR),
                          _item("new", NOW - 1 * HOUR)], now=NOW)
        assert [i["title"] for i in got] == ["new", "old"]

    def test_drops_a_headline_older_than_the_window(self):
        stale = NOW - (SNT.NEWS_WINDOW_HOURS + 2) * HOUR
        assert SNT._fresh([_item("stale", stale)], now=NOW) == []

    def test_an_UNDATED_headline_is_dropped_not_assumed_fresh(self):
        # Google's RSS is the feed that omits the stamp. Letting these through
        # turns a 36-hour window into "whatever the cache happens to hold".
        assert SNT._fresh([{"title": "no stamp"}], now=NOW) == []
        assert SNT._fresh([_item("none", None)], now=NOW) == []

    def test_a_millisecond_stamp_is_understood_not_treated_as_the_far_future(self):
        got = SNT._fresh([_item("ms", (NOW - 2 * HOUR) * 1000)], now=NOW)
        assert len(got) == 1
        assert abs(got[0]["published"] - (NOW - 2 * HOUR)) < 1

    def test_a_far_future_stamp_is_dropped(self):
        assert SNT._fresh([_item("future", NOW + 10 * HOUR)], now=NOW) == []

    def test_empty_and_none_are_safe(self):
        assert SNT._fresh([], now=NOW) == []
        assert SNT._fresh(None, now=NOW) == []


# ---------------------------------------------------------------------------
# _facts
# ---------------------------------------------------------------------------
class TestFacts:
    def test_carries_the_numbers_the_board_already_has(self):
        f = SNT._facts(
            {"group": "Technology", "rel_5d": 1.2, "pct_positive_1d": 60.0},
            {"symbol": "NVDA", "name": "Nvidia", "rel_21d": 8.4,
             "sales_yoy": 55.0, "at_demand": True},
        )
        assert f["sector"] == "Technology"
        assert f["sector_vs_benchmark_5d_pct"] == 1.2
        assert f["symbol"] == "NVDA"
        assert f["vs_benchmark_21d_pct"] == 8.4
        assert f["sales_growth_yoy_pct"] == 55.0
        assert f["at_demand"] is True

    def test_absent_values_are_OMITTED_so_the_model_never_sees_a_hole(self):
        f = SNT._facts({"group": "Energy"}, {"symbol": "XOM", "rel_5d": None})
        assert "vs_benchmark_5d_pct" not in f
        assert "sales_growth_yoy_pct" not in f
        assert f["sector"] == "Energy"

    def test_nan_is_dropped_like_a_missing_value(self):
        f = SNT._facts({"group": "Energy", "rel_5d": float("nan")},
                       {"symbol": "XOM"})
        assert "sector_vs_benchmark_5d_pct" not in f


# ---------------------------------------------------------------------------
# _pick_name — the momentum trap
# ---------------------------------------------------------------------------
class TestPickName:
    def test_picks_the_name_with_the_most_headlines(self):
        names = [{"symbol": "AAA"}, {"symbol": "BBB"}]
        news = {"AAA": [_item("a", NOW), _item("b", NOW)],
                "BBB": [_item("c", NOW), _item("d", NOW), _item("e", NOW)]}
        row, items = SNT._pick_name(names, news)
        assert row["symbol"] == "BBB"
        assert len(items) == 3

    def test_ties_break_on_the_BOARDS_OWN_rank_not_on_return(self):
        names = [{"symbol": "AAA", "rel_1d": 0.1},
                 {"symbol": "BBB", "rel_1d": 99.0}]
        news = {"AAA": [_item("a", NOW), _item("b", NOW)],
                "BBB": [_item("c", NOW), _item("d", NOW)]}
        row, _ = SNT._pick_name(names, news)
        assert row["symbol"] == "AAA"

    def test_THE_BIGGEST_MOVER_DOES_NOT_WIN_ON_ITS_MOVE(self):
        # The whole point: a news tag chosen by return is a momentum read
        # wearing a news label, and he can already sort the board by return.
        names = [{"symbol": "MOVER", "rel_1d": 40.0}, {"symbol": "QUIET", "rel_1d": 0.2}]
        news = {"MOVER": [_item("one lonely headline", NOW)],
                "QUIET": [_item("a", NOW), _item("b", NOW), _item("c", NOW)]}
        row, _ = SNT._pick_name(names, news)
        assert row["symbol"] == "QUIET"

    def test_one_loose_headline_is_not_a_story(self):
        names = [{"symbol": "AAA"}]
        assert SNT._pick_name(names, {"AAA": [_item("a", NOW)]}) is None

    def test_no_news_at_all_returns_None(self):
        assert SNT._pick_name([{"symbol": "AAA"}], {}) is None
        assert SNT._pick_name([], {}) is None

    def test_only_the_leading_names_are_read(self):
        names = [{"symbol": f"S{i}"} for i in range(20)]
        deep = f"S{SNT.NAMES_PER_SECTOR + 3}"
        news = {deep: [_item("a", NOW), _item("b", NOW), _item("c", NOW)]}
        assert SNT._pick_name(names, news) is None


# ---------------------------------------------------------------------------
# _usable — half a tag is worse than none
# ---------------------------------------------------------------------------
class TestUsable:
    GOOD = "x" * 60

    def test_both_sides_written_is_usable(self):
        assert SNT._usable({"bull": self.GOOD, "bear": self.GOOD}) is True

    def test_A_BULL_CASE_WITH_NO_BEAR_CASE_IS_REFUSED(self):
        # This is the failure that would turn the tag into a recommendation.
        assert SNT._usable({"bull": self.GOOD, "bear": ""}) is False
        assert SNT._usable({"bull": self.GOOD}) is False

    def test_a_bear_case_with_no_bull_case_is_refused_too(self):
        assert SNT._usable({"bear": self.GOOD}) is False

    def test_a_one_word_side_is_refused(self):
        assert SNT._usable({"bull": self.GOOD, "bear": "Risky."}) is False

    def test_junk_is_refused(self):
        assert SNT._usable(None) is False
        assert SNT._usable("bull: yes") is False
        assert SNT._usable({}) is False


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def _board():
    return {"sectors": [
        {"group": "Technology", "rel_1d": 0.5, "rel_5d": 2.0,
         "names": [{"symbol": "NVDA", "name": "Nvidia", "rel_1d": 1.0},
                   {"symbol": "AMD", "name": "AMD", "rel_1d": 0.4}]},
        {"group": "Energy", "rel_1d": -0.3,
         "names": [{"symbol": "XOM", "name": "Exxon", "rel_1d": -0.2}]},
    ]}


@pytest.fixture
def stub(monkeypatch):
    """News + model stubbed. Nothing in this file touches the network."""
    async def _news(symbols):
        return {s: [_item(f"{s} beats", NOW), _item(f"{s} expands", NOW)]
                for s in symbols}
    monkeypatch.setattr(SNT, "_news_for", _news)
    monkeypatch.setattr(SNT, "_ask_model", lambda facts, items: {
        "positive": True, "bull": "b" * 60, "bear": "r" * 60,
        "why_positive": "beat", "provider": "local"})


class TestBuild:
    def test_tags_each_sector_that_has_news(self, stub):
        out = SNT.build(_board(), date="2026-09-19")
        assert set(out["tags"]) == {"Technology", "Energy"}
        assert out["counts"]["tagged"] == 2

    def test_the_tag_carries_both_sides_the_date_and_its_provenance(self, stub):
        tag = SNT.build(_board(), date="2026-09-19")["tags"]["Technology"]
        assert tag["date"] == "2026-09-19"
        assert tag["bull"] and tag["bear"]
        assert tag["symbol"] == "NVDA"
        assert tag["sector"] == "Technology"
        assert tag["trigger"]["title"]
        assert tag["facts"]["sector"] == "Technology"

    def test_the_tag_KEEPS_EVERY_HEADLINE_THE_MODEL_SAW(self, stub):
        # The audit trail. The news cache rolls within hours, so without this
        # a number in the prose that came from a real story is, a day later,
        # indistinguishable from one the model invented.
        tag = SNT.build(_board(), date="2026-09-19")["tags"]["Technology"]
        assert len(tag["headlines"]) == 2
        assert {h["title"] for h in tag["headlines"]} == {"NVDA beats", "NVDA expands"}
        assert all(h["source"] and h["published"] for h in tag["headlines"])
        # The trigger must be one of them, never a seventh mystery headline.
        assert tag["trigger"]["title"] in {h["title"] for h in tag["headlines"]}

    def test_the_stored_headlines_are_capped_at_what_the_model_was_shown(self, monkeypatch):
        async def _many(symbols):
            return {s: [_item(f"{s} story {i}", NOW - i * 60) for i in range(12)]
                    for s in symbols}
        monkeypatch.setattr(SNT, "_news_for", _many)
        monkeypatch.setattr(SNT, "_ask_model", lambda f, i: {
            "positive": True, "bull": "b" * 60, "bear": "r" * 60, "provider": "local"})
        tag = SNT.build(_board(), date="2026-09-19")["tags"]["Technology"]
        assert len(tag["headlines"]) == SNT.MAX_HEADLINES_TO_MODEL
        # headline_count still reports the TRUE total, not the capped list.
        assert tag["headline_count"] == 12

    def test_the_tag_says_it_is_NOT_MEASURED_and_names_who_read_it(self, stub):
        # Without these the surface has no way to stop itself presenting an
        # LLM's read of three headlines as a measurement.
        tag = SNT.build(_board(), date="2026-09-19")["tags"]["Technology"]
        assert tag["measured"] is False
        assert tag["read_by"] == "local"

    def test_NO_TAG_when_the_model_writes_only_a_bull_case(self, monkeypatch, stub):
        monkeypatch.setattr(SNT, "_ask_model", lambda f, i: {
            "positive": True, "bull": "b" * 60, "bear": ""})
        out = SNT.build(_board(), date="2026-09-19")
        assert out["tags"] == {}
        assert out["counts"]["no_model"] == 2

    def test_NO_TAG_when_the_model_is_unavailable(self, monkeypatch, stub):
        monkeypatch.setattr(SNT, "_ask_model", lambda f, i: None)
        assert SNT.build(_board(), date="2026-09-19")["tags"] == {}

    def test_NO_TAG_when_there_is_no_news(self, monkeypatch):
        async def _none(symbols):
            return {}
        monkeypatch.setattr(SNT, "_news_for", _none)
        monkeypatch.setattr(SNT, "_ask_model",
                            lambda f, i: pytest.fail("must not ask the model"))
        out = SNT.build(_board(), date="2026-09-19")
        assert out["tags"] == {}
        assert out["counts"]["no_news"] == 2

    def test_a_negative_read_still_produces_a_two_sided_tag(self, monkeypatch, stub):
        # He asked for the tag on POSITIVE news, and the surface filters on
        # `positive`. The builder still records the read rather than throwing
        # the work away, so a day with no positive news is visibly a day with
        # no positive news rather than indistinguishable from an outage.
        monkeypatch.setattr(SNT, "_ask_model", lambda f, i: {
            "positive": False, "bull": "b" * 60, "bear": "r" * 60,
            "provider": "local"})
        tag = SNT.build(_board(), date="2026-09-19")["tags"]["Technology"]
        assert tag["positive"] is False
        assert tag["bull"] and tag["bear"]

    def test_an_empty_board_does_not_crash(self, stub):
        out = SNT.build({}, date="2026-09-19")
        assert out["tags"] == {}
        assert out["counts"]["sectors"] == 0

    def test_a_sector_with_no_names_is_skipped(self, stub):
        out = SNT.build({"sectors": [{"group": "Empty", "names": []}]},
                        date="2026-09-19")
        assert out["tags"] == {}

    def test_only_SECTORS_PER_RUN_sectors_are_tagged(self, stub):
        board = {"sectors": [
            {"group": f"S{i}", "names": [{"symbol": f"T{i}", "name": f"n{i}"}]}
            for i in range(SNT.SECTORS_PER_RUN + 4)]}
        out = SNT.build(board, date="2026-09-19")
        assert len(out["tags"]) == SNT.SECTORS_PER_RUN


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------
class TestAttach:
    def test_hangs_the_tag_on_its_sector_and_NEVER_REORDERS(self, ):
        body = {"sectors": [{"group": "A"}, {"group": "B"}, {"group": "C"}]}
        SNT.attach(body, {"B": {"sector": "B", "date": "2026-09-19",
                                "bull": "x", "bear": "y"}})
        assert [s["group"] for s in body["sectors"]] == ["A", "B", "C"]
        assert body["sectors"][1]["day_tag"]["sector"] == "B"

    def test_an_untagged_sector_gets_an_explicit_None_not_a_missing_key(self):
        body = {"sectors": [{"group": "A"}]}
        SNT.attach(body, {})
        assert "day_tag" in body["sectors"][0]
        assert body["sectors"][0]["day_tag"] is None

    def test_reports_which_day_the_tags_are_from(self):
        body = {"sectors": [{"group": "A"}]}
        SNT.attach(body, {"A": {"sector": "A", "date": "2026-09-18"}})
        assert body["day_tags_as_of"] == "2026-09-18"

    def test_no_tags_reports_no_date_rather_than_todays(self):
        body = {"sectors": [{"group": "A"}]}
        SNT.attach(body, {})
        assert body["day_tags_as_of"] is None

    def test_junk_payload_is_returned_untouched(self):
        assert SNT.attach(None, {}) is None
        assert SNT.attach([], {}) == []


# ---------------------------------------------------------------------------
# latest_within — the weekend
# ---------------------------------------------------------------------------
class TestLatestWithin:
    def test_falls_back_to_the_most_recent_day_that_has_tags(self, monkeypatch):
        seen = []

        def _load(day=None):
            seen.append(day)
            return {"Technology": {"date": day}} if len(seen) == 3 else {}

        monkeypatch.setattr(SNT, "load", _load)
        got = SNT.latest_within(days=5)
        assert got["Technology"]["date"] == seen[2]
        assert len(seen) == 3          # stopped as soon as it found one

    def test_returns_empty_when_nothing_is_within_reach(self, monkeypatch):
        monkeypatch.setattr(SNT, "load", lambda day=None: {})
        assert SNT.latest_within(days=3) == {}

    def test_a_zero_day_window_still_checks_today(self, monkeypatch):
        calls = []
        monkeypatch.setattr(SNT, "load",
                            lambda day=None: calls.append(day) or {})
        SNT.latest_within(days=0)
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Source guards
# ---------------------------------------------------------------------------
SRC = Path(SNT.__file__).read_text(encoding="utf-8")


class TestSourceGuards:
    def test_the_model_is_forbidden_from_inventing_a_number(self):
        assert "may not state any number" in SNT._SYSTEM

    def test_the_model_is_forbidden_from_recommending(self):
        low = SNT._SYSTEM.lower()
        assert "no recommendation" in low
        assert "no price target of" in low

    def test_it_may_REPORT_an_analysts_target_but_never_adopt_one(self):
        # Quoting "Deutsche Bank raised its target to $13" is reporting the
        # headline; naming a target of its own is advice. The prompt has to
        # separate those or it either lies about the news or gives advice.
        low = SNT._SYSTEM.lower()
        assert "may report" in low
        assert "never adopt it as your own" in low

    def test_the_prompt_says_reversal_never_bounce(self):
        # Standing rule on every surface he reads.
        assert re.search(r'"reversal".{0,12}never.{0,3}"bounce"',
                         SNT._SYSTEM, re.I | re.S), SNT._SYSTEM

    def test_no_surface_word_in_this_module_says_bounce(self):
        # The internals of supply_demand keep `bouncing` on purpose; nothing
        # in THIS module is an internal, it is all read by him.
        assert not re.search(r"\bbounce\b", SRC, re.I) or \
            re.search(r'never "bounce"', SRC)

    def test_this_module_never_reaches_into_the_S_AND_D_OR_TRADING_STACK(self):
        # Rule #10: a news tag may not touch a rule, a gate or a lane. It is
        # allowed to READ a shipped zone field off a board row (`at_demand`),
        # which arrives as data; it may not import the engine that made it.
        body = re.sub(r"#.*", "", SRC)
        body = re.sub(r'""".*?"""', "", body, flags=re.S)
        for banned in ("supply_demand", "trading", "alert_gates", "entries"):
            assert banned not in body, f"{banned} reached from a news tag"

    def test_it_pushes_nothing(self):
        body = re.sub(r"#.*", "", SRC)
        body = re.sub(r'""".*?"""', "", body, flags=re.S)
        for banned in ("push", "notify", "twilio", "pushover"):
            assert banned not in body.lower(), f"{banned} in a news tag"

    def test_the_scope_knobs_are_not_presented_as_measured(self):
        assert "NOT SIGNAL THRESHOLDS" in SRC
        assert SNT.SECTORS_PER_RUN > 0 and SNT.NAMES_PER_SECTOR > 0
        assert SNT.MIN_HEADLINES >= 2

    def test_the_day_stamp_is_the_ET_SESSION_DATE_not_UTC(self):
        # He reads this board in the evening in CT, when UTC has already
        # rolled over. A UTC stamp files the 06:20 run under one date and
        # looks it up under the next; `latest_within` would paper over it,
        # but the tag PRINTS its date on the tile.
        from datetime import datetime
        from zoneinfo import ZoneInfo
        assert SNT.ET == ZoneInfo("America/New_York")
        assert SNT.today_et() == datetime.now(SNT.ET).strftime("%Y-%m-%d")
        assert "timezone.utc" not in SRC

    def test_the_window_survives_a_weekend_gap(self):
        # A Monday 06:00 run must still see Friday's close-of-day story.
        assert SNT.NEWS_WINDOW_HOURS >= 36
