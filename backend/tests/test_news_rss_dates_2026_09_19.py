"""backend/news.py — the RSS date parse. The first tests this module has ever had.

MEASURED BUG, 2026-09-19. `_parse_rss_date` replaced this:

    try:
        ts = int(datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %z").timestamp())
    except Exception:
        ts = int(time.time())

`%z` does not accept a NAMED zone. Google News RSS emits exactly that —
"Fri, 18 Sep 2026 20:13:00 GMT" — so the parse raised on EVERY Google item and
stamped it with the current time. Verified against the live feed the day this
was found: fetch_news("NVDA") returned 12 Google items, all 12 reporting an age
of 0.00 hours, one of them genuinely dated "Wed, 26 Aug 2026" — twenty-four
days old, served as brand new.

Every downstream recency filter was therefore filtering on a constant.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import news


def _epoch(y, mo, d, h=0, mi=0, s=0):
    return int(datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc).timestamp())


class TestNamedZones:
    def test_GMT_parses_it_is_the_whole_bug(self):
        # Google News' actual format. This is the case that used to raise.
        got = news._parse_rss_date("Fri, 18 Sep 2026 20:13:00 GMT")
        assert got == _epoch(2026, 9, 18, 20, 13, 0)

    def test_an_OLD_google_date_is_read_as_old_not_as_now(self):
        # The real sample from the live feed: 24 days stale, served as fresh.
        got = news._parse_rss_date("Wed, 26 Aug 2026 07:00:00 GMT")
        assert got == _epoch(2026, 8, 26, 7, 0, 0)
        assert time.time() - got > 20 * 86400

    def test_UT_and_Z_and_the_us_zones_parse(self):
        for raw, exp in (
            ("Fri, 18 Sep 2026 20:13:00 UT",  _epoch(2026, 9, 18, 20, 13)),
            ("Fri, 18 Sep 2026 20:13:00 Z",   _epoch(2026, 9, 18, 20, 13)),
            ("Fri, 18 Sep 2026 16:13:00 EDT", _epoch(2026, 9, 18, 20, 13)),
        ):
            assert news._parse_rss_date(raw) == exp, raw


class TestNumericOffsets:
    def test_the_yahoo_format_still_parses(self):
        # This one always worked; it must keep working.
        assert news._parse_rss_date("Fri, 18 Sep 2026 20:13:00 +0000") == \
            _epoch(2026, 9, 18, 20, 13)

    def test_a_real_offset_is_applied_not_ignored(self):
        assert news._parse_rss_date("Fri, 18 Sep 2026 15:13:00 -0500") == \
            _epoch(2026, 9, 18, 20, 13)

    def test_a_naive_date_is_read_as_UTC_per_RFC_2822(self):
        assert news._parse_rss_date("Fri, 18 Sep 2026 20:13:00") == \
            _epoch(2026, 9, 18, 20, 13)


class TestUnknownIsNoneNeverNow:
    """The half of the fix that matters more than the parsing.

    A date we cannot read must come back as "we do not know", because the old
    fallback did not merely lose the date — it asserted a specific, wrong,
    maximally-favourable one. `None` is rejected by a window; `now` is the one
    value guaranteed to survive every window there is.
    """

    def test_empty_is_None(self):
        assert news._parse_rss_date("") is None
        assert news._parse_rss_date(None) is None
        assert news._parse_rss_date("   ") is None

    def test_garbage_is_None(self):
        for raw in ("yesterday", "not a date", "2026-09-18", "???", "Fri,"):
            assert news._parse_rss_date(raw) is None, raw

    def test_NOTHING_unparseable_ever_comes_back_as_roughly_now(self):
        now = time.time()
        for raw in ("", "yesterday", "garbage", None, "2026/09/18"):
            got = news._parse_rss_date(raw)
            assert got is None, f"{raw!r} -> {got!r}"
            # Belt and braces: if a future edit reinstates a fallback, this
            # is the assertion that catches it.
            assert not (isinstance(got, (int, float)) and abs(now - got) < 600)


class TestItemsCarryWhatWasParsed:
    def test_an_rss_item_with_a_named_zone_keeps_its_real_timestamp(self):
        xml = (
            "<item><title>Old story</title>"
            "<link>https://example.test/a</link>"
            "<pubDate>Wed, 26 Aug 2026 07:00:00 GMT</pubDate>"
            "</item>"
        )
        out = news._parse_rss(xml, "test") if hasattr(news, "_parse_rss") else None
        if out is None:
            import pytest
            pytest.skip("no standalone rss parser to exercise")
        assert out and out[0]["published"] == _epoch(2026, 8, 26, 7, 0)
