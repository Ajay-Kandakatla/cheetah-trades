"""The reusable news routine — Ajay 2026-09-20, "A reusable backend routine".

What these tests exist to stop:

  * an UNDATED headline being read as a fresh one. That is not hypothetical:
    `news._parse_rss_date` stamped every unparseable Google date with the
    current time until 2026-09-19, which made every recency window in the app
    inert. The drop is pinned here from both ends.
  * a typed query silently truncating at the first `&`, `?` or `#`. The legacy
    `_google_news` builds a raw f-string; `google_search` must quote.
  * the sector day-tags changing behaviour when they were only refactored —
    `_fresh` and `_news_for` delegate, and the delegation is proved against a
    re-implementation of the pre-delegation body.
  * a bare three-letter ticker matching prose about the dollar (USD).

Nothing here touches the network: every provider leg is a fake.
"""
from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, unquote, urlparse

import pytest

import news
from news_search import core
from rotation import sector_news_tags as SNT


NOW = 1_789_800_000.0          # pinned; nothing below reads the wall clock
HOUR = 3600.0
W = core.DEFAULT_WINDOW_HOURS


def _item(title, published, url="https://example.test/x", source="Reuters"):
    return {"title": title, "published": published, "url": url,
            "source": source, "summary": "s", "provider": "google"}


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_news_cache():
    news._cache.clear()
    yield
    news._cache.clear()


# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------
class TestNormalise:
    def test_maps_the_massive_shape(self):
        got = core.normalise({
            "title": " Massive headline ",
            "url": "https://m.test/a",
            "publisher": "Benzinga",
            "description": "  body  ",
            "published_utc": "2026-09-19T20:13:00Z",
        })
        assert got["title"] == "Massive headline"
        assert got["source"] == "Benzinga"
        assert got["summary"] == "body"
        assert got["published"] == 1789848780

    def test_maps_the_catalyst_shape_link_and_rfc2822_pub(self):
        got = core.normalise({"title": "t", "link": "https://c.test/b",
                              "pub": "Fri, 18 Sep 2026 20:13:00 GMT"},
                             provider="google")
        assert got["url"] == "https://c.test/b"
        assert got["provider"] == "google"
        assert got["published"] == news._parse_rss_date("Fri, 18 Sep 2026 20:13:00 GMT")
        assert got["published"] is not None

    def test_an_unreadable_pub_stays_undated_not_now(self):
        got = core.normalise({"title": "t", "link": "u", "pub": "sometime last week"})
        assert got["published"] is None

    def test_an_iso_without_a_zone_is_read_as_utc(self):
        assert core.normalise({"title": "t", "published_utc": "2026-09-19T20:13:00"}) \
            ["published"] == 1789848780

    def test_a_nan_published_is_treated_as_undated(self):
        assert core.normalise({"title": "t", "published": float("nan")})["published"] is None

    def test_an_empty_item_does_not_raise(self):
        got = core.normalise({})
        assert got["title"] == "" and got["published"] is None and got["url"] == ""


# ---------------------------------------------------------------------------
# fresh
# ---------------------------------------------------------------------------
class TestFresh:
    def test_an_undated_headline_is_dropped_never_assumed_fresh(self):
        assert core.fresh([{"title": "no stamp"}], now=NOW) == []
        assert core.fresh([_item("none", None)], now=NOW) == []
        assert core.fresh([_item("nan", float("nan"))], now=NOW) == []

    def test_the_window_boundary_one_second_either_side(self):
        inside = NOW - (W * HOUR) + 1
        outside = NOW - (W * HOUR) - 1
        assert [i["title"] for i in core.fresh([_item("in", inside)], now=NOW)] == ["in"]
        assert core.fresh([_item("out", outside)], now=NOW) == []

    def test_a_future_stamp_beyond_the_skew_allowance_is_dropped(self):
        assert [i["title"] for i in core.fresh([_item("skew", NOW + 3599)], now=NOW)] == ["skew"]
        assert core.fresh([_item("future", NOW + 3601)], now=NOW) == []

    def test_a_millisecond_stamp_is_understood(self):
        got = core.fresh([_item("ms", (NOW - 2 * HOUR) * 1000)], now=NOW)
        assert len(got) == 1
        assert abs(got[0]["published"] - (NOW - 2 * HOUR)) < 1

    def test_newest_first(self):
        got = core.fresh([_item("old", NOW - 20 * HOUR), _item("new", NOW - 1 * HOUR)],
                         now=NOW)
        assert [i["title"] for i in got] == ["new", "old"]

    def test_empty_and_none_do_not_raise(self):
        assert core.fresh([], now=NOW) == []
        assert core.fresh(None, now=NOW) == []


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------
class TestDedupe:
    def test_same_title_key_across_two_wires(self):
        got = core.dedupe([
            _item("Nvidia beats on earnings", NOW, url="https://a.test/1"),
            _item("NVIDIA  beats, on earnings!", NOW, url="https://b.test/2"),
        ])
        assert len(got) == 1

    def test_same_url_under_a_rewritten_headline(self):
        got = core.dedupe([
            _item("One headline", NOW, url="https://a.test/1"),
            _item("A completely different headline", NOW, url="https://a.test/1"),
        ])
        assert len(got) == 1

    def test_two_genuinely_different_stories_both_survive(self):
        got = core.dedupe([
            _item("Nvidia beats", NOW, url="https://a.test/1"),
            _item("AMD guides lower", NOW, url="https://b.test/2"),
        ])
        assert len(got) == 2

    def test_an_untitled_item_is_dropped(self):
        assert core.dedupe([{"title": "", "url": "https://a.test/1"}]) == []

    def test_two_items_with_no_url_are_kept_when_titles_differ(self):
        got = core.dedupe([{"title": "a", "url": ""}, {"title": "b", "url": ""}])
        assert len(got) == 2


# ---------------------------------------------------------------------------
# relevance_filter
# ---------------------------------------------------------------------------
class TestRelevance:
    def test_a_three_letter_ticker_does_not_match_currency_prose(self):
        items = [_item("USD strengthens as dollar rally extends", NOW)]
        assert core.relevance_filter(items, ticker="USD", company=None) == []

    def test_but_a_cashtag_is_kept(self):
        items = [_item("$USD holders brace for the print", NOW)]
        assert len(core.relevance_filter(items, ticker="USD", company=None)) == 1

    def test_the_company_first_word_is_enough(self):
        items = [_item("NVIDIA lifts data-centre guidance", NOW)]
        got = core.relevance_filter(items, ticker="NVDA", company="NVIDIA Corporation")
        assert len(got) == 1

    def test_a_four_letter_bare_ticker_is_accepted(self):
        items = [_item("Analysts raise NVDA to buy", NOW)]
        assert len(core.relevance_filter(items, ticker="NVDA", company=None)) == 1

    def test_an_unrelated_headline_is_dropped_even_with_a_name(self):
        items = [_item("Fed holds rates steady", NOW)]
        assert core.relevance_filter(items, ticker="NVDA", company="NVIDIA Corporation") == []

    def test_no_ticker_filters_nothing(self):
        items = [_item("Fed holds rates steady", NOW)]
        assert len(core.relevance_filter(items, ticker="", company=None)) == 1


# ---------------------------------------------------------------------------
# build_query
# ---------------------------------------------------------------------------
class TestBuildQuery:
    def test_a_sector_is_quoted_and_anchored_to_equities(self):
        assert core.build_query(sector="Semiconductors") == '"Semiconductors" sector stocks'

    def test_a_keyword_is_passed_through_stripped(self):
        assert core.build_query(keyword="  CHIPS Act  ") == "CHIPS Act"

    @pytest.mark.parametrize("kw", ["", "   ", "\t\n"])
    def test_an_empty_or_whitespace_query_raises(self, kw):
        with pytest.raises(ValueError):
            core.build_query(keyword=kw)
        with pytest.raises(ValueError):
            core.build_query(sector=kw)


# ---------------------------------------------------------------------------
# news.google_search — the escaping that `_google_news` never did
# ---------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, text="<rss></rss>", status_code=200):
        self.text = text
        self.status_code = status_code


class _FakeClient:
    """Records every URL `news` asks for; returns one canned RSS body."""

    calls: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **k):
        _FakeClient.calls.append(url)
        return _FakeResp(_RSS_ONE)


_RSS_ONE = (
    "<rss><channel><item>"
    "<title>Nvidia lifts guidance</title>"
    "<link>https://g.test/1</link>"
    "<pubDate>Fri, 18 Sep 2026 20:13:00 GMT</pubDate>"
    "<description>body</description>"
    "</item></channel></rss>"
)


@pytest.fixture
def fake_http(monkeypatch):
    _FakeClient.calls = []
    monkeypatch.setattr(news.httpx, "AsyncClient", _FakeClient)
    return _FakeClient


class TestGoogleSearch:
    QUERY = 'AT&T stake? #1 C++ 100% "x"'

    def test_a_hostile_query_survives_the_url_intact(self, fake_http):
        _run(news.google_search(self.QUERY))
        url = fake_http.calls[-1]
        raw_q = url.split("q=", 1)[1].split("&hl=", 1)[0]
        for bad in (" ", "&", "?", "#", "+"):
            assert bad not in raw_q, f"raw {bad!r} leaked into the query segment"
        assert unquote(raw_q) == self.QUERY
        assert parse_qs(urlparse(url).query)["q"] == [self.QUERY]

    def test_it_parses_the_feed_into_the_news_item_shape(self, fake_http):
        got = _run(news.google_search("CHIPS Act"))
        assert len(got) == 1
        assert got[0]["title"] == "Nvidia lifts guidance"
        assert got[0]["url"] == "https://g.test/1"
        assert got[0]["provider"] == "google"
        assert got[0]["published"] is not None

    def test_it_caches_by_query(self, fake_http):
        _run(news.google_search("CHIPS Act"))
        _run(news.google_search("CHIPS Act"))
        assert len(fake_http.calls) == 1
        _run(news.google_search("export controls"))
        assert len(fake_http.calls) == 2

    @pytest.mark.parametrize("q", ["", "   ", None])
    def test_an_empty_query_raises_and_never_calls_out(self, fake_http, q):
        with pytest.raises(ValueError):
            _run(news.google_search(q))
        assert fake_http.calls == []

    def test_a_non_200_returns_empty_and_does_not_raise(self, monkeypatch):
        class _Bad(_FakeClient):
            async def get(self, url, **k):
                return _FakeResp("", 503)
        monkeypatch.setattr(news.httpx, "AsyncClient", _Bad)
        assert _run(news.google_search("anything")) == []

    def test_a_raising_transport_returns_empty(self, monkeypatch):
        class _Boom(_FakeClient):
            async def get(self, url, **k):
                raise RuntimeError("socket")
        monkeypatch.setattr(news.httpx, "AsyncClient", _Boom)
        assert _run(news.google_search("anything")) == []

    def test_the_legacy_ticker_url_is_unchanged(self, fake_http):
        """`fetch_news`'s Google leg is pinned — `google_search` is additive."""
        client = _FakeClient()
        _run(news._google_news(client, "NVDA"))
        assert fake_http.calls[-1] == (
            "https://news.google.com/rss/search"
            "?q=NVDA+stock+OR+earnings+OR+analyst&hl=en-US&gl=US&ceid=US:en"
        )


# ---------------------------------------------------------------------------
# search — the selector contract
# ---------------------------------------------------------------------------
class TestSelector:
    def test_zero_selectors_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            _run(core.search())

    def test_two_selectors_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            _run(core.search(ticker="NVDA", keyword="CHIPS Act"))

    def test_three_selectors_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            _run(core.search(ticker="NVDA", sector="Semis", keyword="CHIPS Act"))

    def test_a_whitespace_only_selector_counts_as_absent(self):
        with pytest.raises(ValueError, match="exactly one"):
            _run(core.search(ticker="   "))


@pytest.fixture
def no_name(monkeypatch):
    from sepa import company_names
    monkeypatch.setattr(company_names, "name_for", lambda s: None)
    return company_names


class TestSearchTicker:
    def _patch(self, monkeypatch, items):
        async def _fetch(sym):
            return list(items)
        monkeypatch.setattr(news, "fetch_news", _fetch)

    def test_it_drops_undated_stale_irrelevant_and_duplicates_and_counts_each(
            self, monkeypatch):
        from sepa import company_names
        monkeypatch.setattr(company_names, "name_for", lambda s: "NVIDIA Corporation")
        self._patch(monkeypatch, [
            _item("NVIDIA beats", NOW - HOUR, url="https://a.test/1"),
            _item("NVIDIA beats!", NOW - HOUR, url="https://b.test/2"),   # dupe title
            _item("NVIDIA slipped last month", NOW - 400 * HOUR, url="https://c.test/3"),
            _item("NVIDIA undated", None, url="https://d.test/4"),
            _item("Fed holds rates steady", NOW - HOUR, url="https://e.test/5"),
        ])
        got = _run(core.search(ticker="nvda", now=NOW))
        assert [i["title"] for i in got["items"]] == ["NVIDIA beats"]
        assert got["counts"] == {"raw": 5, "undated_dropped": 1, "stale_dropped": 1,
                                 "irrelevant_dropped": 1, "deduped": 1}
        assert got["selector"] == {"kind": "ticker", "value": "NVDA"}
        assert got["window_hours"] == core.DEFAULT_WINDOW_HOURS

    def test_relevance_none_keeps_everything_dated_and_fresh(self, monkeypatch, no_name):
        self._patch(monkeypatch, [
            _item("Fed holds rates steady", NOW - HOUR, url="https://e.test/5"),
            _item("Dollar rallies", NOW - HOUR, url="https://f.test/6"),
        ])
        got = _run(core.search(ticker="USD", now=NOW, relevance="none"))
        assert len(got["items"]) == 2
        assert got["counts"]["irrelevant_dropped"] == 0

    def test_relevance_company_is_the_default_and_bites(self, monkeypatch, no_name):
        self._patch(monkeypatch, [_item("Dollar rallies", NOW - HOUR)])
        got = _run(core.search(ticker="USD", now=NOW))
        assert got["items"] == []
        assert got["counts"]["irrelevant_dropped"] == 1

    def test_a_provider_failure_returns_empty_and_never_raises(self, monkeypatch, no_name):
        async def _boom(sym):
            raise RuntimeError("provider down")
        monkeypatch.setattr(news, "fetch_news", _boom)
        got = _run(core.search(ticker="NVDA", now=NOW))
        assert got["items"] == [] and got["counts"]["raw"] == 0

    def test_a_failing_name_lookup_does_not_raise(self, monkeypatch):
        from sepa import company_names

        def _boom(sym):
            raise RuntimeError("mongo down")
        monkeypatch.setattr(company_names, "name_for", _boom)
        self._patch(monkeypatch, [_item("Analysts raise NVDA to buy", NOW - HOUR)])
        got = _run(core.search(ticker="NVDA", now=NOW))
        assert len(got["items"]) == 1

    def test_the_limit_is_applied_last(self, monkeypatch, no_name):
        items = [_item(f"NVDA story {i}", NOW - HOUR, url=f"https://a.test/{i}")
                 for i in range(20)]
        self._patch(monkeypatch, items)
        got = _run(core.search(ticker="NVDA", now=NOW, limit=3))
        assert len(got["items"]) == 3


class TestSearchSectorKeyword:
    def _patch(self, monkeypatch, items, seen):
        async def _gs(query, **k):
            seen.append(query)
            return list(items)
        monkeypatch.setattr(news, "google_search", _gs)

    def test_a_sector_builds_the_quoted_query_and_never_relevance_filters(
            self, monkeypatch):
        seen: list = []
        self._patch(monkeypatch, [_item("Chip stocks rip", NOW - HOUR)], seen)
        got = _run(core.search(sector="Semiconductors", now=NOW))
        assert seen == ['"Semiconductors" sector stocks']
        assert got["query"] == '"Semiconductors" sector stocks'
        assert got["selector"] == {"kind": "sector", "value": "Semiconductors"}
        assert len(got["items"]) == 1
        assert got["counts"]["irrelevant_dropped"] == 0

    def test_a_keyword_is_passed_through(self, monkeypatch):
        seen: list = []
        self._patch(monkeypatch, [_item("Act signed", NOW - HOUR)], seen)
        got = _run(core.search(keyword="CHIPS Act", now=NOW))
        assert seen == ["CHIPS Act"]
        assert got["selector"]["kind"] == "keyword"

    def test_a_keyword_provider_failure_returns_empty(self, monkeypatch):
        async def _boom(query, **k):
            raise RuntimeError("down")
        monkeypatch.setattr(news, "google_search", _boom)
        got = _run(core.search(keyword="CHIPS Act", now=NOW))
        assert got["items"] == [] and got["counts"]["raw"] == 0

    def test_a_stale_sector_headline_is_dropped(self, monkeypatch):
        seen: list = []
        self._patch(monkeypatch, [_item("Old chip story", NOW - 400 * HOUR)], seen)
        got = _run(core.search(sector="Semiconductors", now=NOW))
        assert got["items"] == [] and got["counts"]["stale_dropped"] == 1


# ---------------------------------------------------------------------------
# search_sync
# ---------------------------------------------------------------------------
class TestSearchSync:
    def test_it_works_from_plain_sync_code(self, monkeypatch, no_name):
        async def _fetch(sym):
            return [_item("Analysts raise NVDA to buy", NOW - HOUR)]
        monkeypatch.setattr(news, "fetch_news", _fetch)
        got = core.search_sync(ticker="NVDA", now=NOW)
        assert len(got["items"]) == 1

    def test_it_works_from_inside_a_running_loop(self, monkeypatch, no_name):
        async def _fetch(sym):
            return [_item("Analysts raise NVDA to buy", NOW - HOUR)]
        monkeypatch.setattr(news, "fetch_news", _fetch)

        async def _outer():
            import concurrent.futures as _f
            with _f.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(core.search_sync, ticker="NVDA", now=NOW).result()

        assert len(_run(_outer())["items"]) == 1


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
class _FakeColl:
    def __init__(self):
        self.calls: list = []

    def update_one(self, flt, update, upsert=False):
        self.calls.append((flt, update, upsert))


class TestAudit:
    def _patch_fetch(self, monkeypatch):
        async def _fetch(sym):
            return [_item("Analysts raise NVDA to buy", NOW - HOUR)]
        monkeypatch.setattr(news, "fetch_news", _fetch)

    def test_it_upserts_under_the_composite_id(self, monkeypatch, no_name):
        from datetime import datetime
        self._patch_fetch(monkeypatch)
        coll = _FakeColl()
        monkeypatch.setattr(core, "_coll", lambda: coll)
        _run(core.search(ticker="NVDA", now=NOW, audit="sector_day_tags"))
        day = datetime.now(core.ET).strftime("%Y-%m-%d")
        flt, update, upsert = coll.calls[0]
        assert flt == {"_id": f"sector_day_tags|ticker|NVDA|{day}"}
        assert upsert is True
        assert update["$set"]["caller"] == "sector_day_tags"
        assert update["$set"]["counts"]["raw"] == 1

    def test_no_audit_argument_never_touches_mongo(self, monkeypatch, no_name):
        self._patch_fetch(monkeypatch)
        coll = _FakeColl()
        monkeypatch.setattr(core, "_coll", lambda: coll)
        _run(core.search(ticker="NVDA", now=NOW))
        assert coll.calls == []

    def test_a_write_failure_never_reaches_the_caller(self, monkeypatch, no_name):
        self._patch_fetch(monkeypatch)

        class _Boom:
            def update_one(self, *a, **k):
                raise RuntimeError("mongo gone")
        monkeypatch.setattr(core, "_coll", lambda: _Boom())
        got = _run(core.search(ticker="NVDA", now=NOW, audit="x"))
        assert len(got["items"]) == 1

    def test_no_mongo_is_not_an_error(self, monkeypatch, no_name):
        self._patch_fetch(monkeypatch)
        monkeypatch.setattr(core, "_coll", lambda: None)
        assert len(_run(core.search(ticker="NVDA", now=NOW, audit="x"))["items"]) == 1


# ---------------------------------------------------------------------------
# The sector day-tags delegation is behaviour-preserving
# ---------------------------------------------------------------------------
def _legacy_fresh(items, now):
    """`sector_news_tags._fresh`'s body as it stood before the delegation."""
    floor = now - SNT.NEWS_WINDOW_HOURS * 3600
    out = []
    for it in items or []:
        ts = it.get("published")
        if not isinstance(ts, (int, float)) or ts != ts:
            continue
        if ts > 1e12:
            ts = ts / 1000.0
        if ts < floor or ts > now + 3600:
            continue
        out.append({**it, "published": ts})
    out.sort(key=lambda x: x["published"], reverse=True)
    return out


class TestSectorTagsDelegation:
    def test_the_window_is_the_one_constant_not_a_copy(self):
        assert SNT.NEWS_WINDOW_HOURS is core.DEFAULT_WINDOW_HOURS

    @pytest.mark.parametrize("fixture", [
        [],
        None,
        [{"title": "no stamp"}],
        [_item("none", None)],
        [_item("nan", float("nan"))],
        [_item("ms", (NOW - 2 * HOUR) * 1000)],
        [_item("future", NOW + 10 * HOUR)],
        [_item("skew", NOW + 3599)],
        [_item("edge_in", NOW - (W * HOUR) + 1)],
        [_item("edge_out", NOW - (W * HOUR) - 1)],
        [_item("old", NOW - 20 * HOUR), _item("new", NOW - 1 * HOUR)],
    ])
    def test_fresh_is_byte_identical_to_the_pre_delegation_body(self, fixture):
        assert SNT._fresh(fixture, now=NOW) == _legacy_fresh(fixture, NOW)

    def test_news_for_asks_with_relevance_off(self, monkeypatch):
        """The tags have never filtered on the company name — §7 item 8."""
        seen: list = []

        async def _search(**kw):
            seen.append(kw)
            return {"items": [_item("anything", NOW - HOUR)]}
        monkeypatch.setattr(core, "search", _search)
        got = _run(SNT._news_for(["NVDA", "AMD"]))
        assert sorted(got) == ["AMD", "NVDA"]
        assert all(k["relevance"] == "none" for k in seen)
        assert all(k["window_hours"] == SNT.NEWS_WINDOW_HOURS for k in seen)
        assert all(k["audit"] == SNT.COLLECTION for k in seen)

    def test_one_failing_symbol_does_not_take_the_sweep_down(self, monkeypatch):
        async def _search(**kw):
            if kw.get("ticker") == "AMD":
                raise RuntimeError("provider down")
            return {"items": [_item("ok", NOW - HOUR)]}
        monkeypatch.setattr(core, "search", _search)
        got = _run(SNT._news_for(["NVDA", "AMD"]))
        assert got["AMD"] == []
        assert len(got["NVDA"]) == 1
