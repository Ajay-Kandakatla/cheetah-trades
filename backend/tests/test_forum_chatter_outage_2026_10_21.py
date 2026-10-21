"""forum_chatter StockTwits stale keep + outage words (2026-10-21).

api.stocktwits.com went dark for everyone on 2026-10-21 and the ticker page
showed 0 / 0 / 0 plus a raw libcurl error. Pins:
  * an outage with no earlier good read → zeros + the served sentence
    + " · no earlier read";
  * an outage with a cached good read → THAT block, flagged stale with
    stale_since / stale_reason / last_attempt_at; summary from it;
  * a good fetch after an outage clears stale;
  * a cached block that is itself unavailable is never served as good;
  * the StockTwits keep never touches the Reddit / HN blocks;
  * stale_since <= fetched_at, and survives a second outage tick;
  * the Reddit keep's stale_reason is the served Reddit sentence.

Mongo and every lane are monkeypatched — no network, no database.
"""
import asyncio
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import forum_chatter as fc
from sepa import reddit_scrape

NOW = 1_800_000_000
EARLIER = NOW - 6 * 3600
OUTAGE = "StockTwits is not answering (timed out after 10s)"


class FakeColl:
    def __init__(self, doc=None):
        self.doc = copy.deepcopy(doc)
        self.writes = []

    def find_one(self, q):
        return copy.deepcopy(self.doc)

    def update_one(self, q, upd, upsert=False):
        self.writes.append(copy.deepcopy(upd))
        new = dict(self.doc or {"_id": q["_id"]})
        new.update(copy.deepcopy(upd["$set"]))
        self.doc = new


def st_good(bull=4, bear=1, neu=2):
    return {"available": True, "reason_code": "ok",
            "messages": [{"id": 1, "body": "hi"}, {"id": 2, "body": "yo"}],
            "bullish": bull, "bearish": bear, "neutral": neu,
            "total": bull + bear + neu}


def st_down(reason=OUTAGE, code="timeout"):
    return {"available": False, "reason": reason, "reason_code": code,
            "messages": [], "bullish": 0, "bearish": 0, "neutral": 0}


def reddit_ok(n=2):
    return {"available": True, "partial": False, "threads": [],
            "mentions_7d": n, "mentions_prior_7d": 1,
            "reason": None, "reason_code": None}


def reddit_down():
    sentence = reddit_scrape.failure_sentence("blocked", 403, False)
    return {"available": False, "partial": False, "threads": [],
            "mentions_7d": 0, "mentions_prior_7d": 0,
            "reason": sentence, "reason_code": "blocked"}


HN = {"available": True, "stories": [], "n": 3}


def cached_doc(st, fetched_at=EARLIER, **extra):
    payload = {"symbol": "POM", "fetched_at": fetched_at,
               "thoughtful": reddit_ok(9), "momentum": reddit_ok(9),
               "stocktwits": st, "hn": {"available": True, "stories": [], "n": 99},
               "summary": {}}
    doc = {"_id": "POM", "fetched_at": fetched_at, "payload": payload}
    doc.update(extra)
    return doc


@pytest.fixture
def wire(monkeypatch):
    def _wire(coll, st, thoughtful=None, momentum=None, now=NOW):
        monkeypatch.setattr(fc, "_get_cache", lambda: coll)
        monkeypatch.setattr(fc, "_append_history", lambda p: None)
        monkeypatch.setattr(fc, "_now", lambda: now)

        async def _t(sym):
            return copy.deepcopy(thoughtful or reddit_ok())

        async def _m(sym):
            return copy.deepcopy(momentum or reddit_ok())

        async def _s(sym):
            return copy.deepcopy(st)

        async def _h(sym, name=None):
            return copy.deepcopy(HN)

        monkeypatch.setattr(fc, "_reddit_thoughtful", _t)
        monkeypatch.setattr(fc, "_reddit_momentum", _m)
        monkeypatch.setattr(fc, "_stocktwits", _s)
        monkeypatch.setattr(fc, "_hacker_news", _h)
    return _wire


def run(**kw):
    return asyncio.run(fc.chatter_for("POM", refresh=True, **kw))


def test_outage_without_cache_serves_zeros_and_sentence(wire):
    coll = FakeColl(None)
    wire(coll, st_down())
    out = run()
    st = out["stocktwits"]
    assert st["available"] is False
    assert st["bullish"] == st["bearish"] == st["neutral"] == 0
    assert st["reason"] == OUTAGE + " · no earlier read"
    assert st["reason_code"] == "timeout"
    assert "stale" not in st
    assert "stocktwits_last_good_at" not in coll.writes[-1]["$set"]


def test_outage_without_mongo_serves_zeros_and_sentence(wire):
    wire(None, st_down())
    st = run()["stocktwits"]
    assert st["available"] is False
    assert st["reason"].endswith(" · no earlier read")


def test_outage_with_cache_serves_last_good_block_flagged_stale(wire):
    coll = FakeColl(cached_doc(st_good(5, 2, 1)))
    wire(coll, st_down())
    out = run()
    st = out["stocktwits"]
    assert st["available"] is True
    assert (st["bullish"], st["bearish"], st["neutral"]) == (5, 2, 1)
    assert [m["id"] for m in st["messages"]] == [1, 2]
    assert st["stale"] is True
    assert st["stale_since"] == EARLIER
    assert st["stale_reason"] == OUTAGE
    assert st["last_attempt_at"] == NOW
    assert st["stale_since"] <= out["fetched_at"]
    # summary computed from the served (stale) counts
    assert out["summary"]["stocktwits_bullish"] == 5
    assert out["summary"]["stocktwits_bearish"] == 2
    # the rest of the payload is the fresh one
    assert out["fetched_at"] == NOW
    assert out["hn"]["n"] == 3
    assert out["thoughtful"]["mentions_7d"] == 2
    # the write keeps the stale block and records the last good time
    written = coll.writes[-1]["$set"]
    assert written["payload"]["stocktwits"]["stale"] is True
    assert written["stocktwits_last_good_at"] == EARLIER


def test_second_outage_tick_keeps_the_original_good_time(wire):
    coll = FakeColl(cached_doc(st_good()))
    wire(coll, st_down())
    run()
    later = NOW + 20 * 60
    wire(coll, st_down("StockTwits is down (http 502)", "http_5xx"), now=later)
    out = run()
    st = out["stocktwits"]
    assert st["stale"] is True
    assert st["stale_since"] == EARLIER  # not the first outage tick
    assert st["stale_reason"] == "StockTwits is down (http 502)"
    assert st["reason_code"] == "http_5xx"
    assert st["last_attempt_at"] == later
    assert st["stale_since"] <= out["fetched_at"]


def test_good_fetch_after_outage_clears_stale(wire):
    coll = FakeColl(cached_doc(st_good()))
    wire(coll, st_down())
    run()
    wire(coll, st_good(7, 0, 0), now=NOW + 3600)
    st = run()["stocktwits"]
    assert st["available"] is True
    for k in ("stale", "stale_since", "stale_reason", "last_attempt_at"):
        assert k not in st
    assert st["bullish"] == 7
    assert coll.writes[-1]["$set"]["stocktwits_last_good_at"] == NOW + 3600


def test_cached_unavailable_block_never_served_as_good(wire):
    coll = FakeColl(cached_doc(st_down("StockTwits is not reachable",
                                       "unreachable")))
    wire(coll, st_down())
    st = run()["stocktwits"]
    assert st["available"] is False
    assert "stale" not in st
    assert st["reason"] == OUTAGE + " · no earlier read"


def test_cache_row_without_stocktwits_block_is_no_earlier_read(wire):
    doc = cached_doc(st_good())
    del doc["payload"]["stocktwits"]
    coll = FakeColl(doc)
    wire(coll, st_down())
    st = run()["stocktwits"]
    assert st["available"] is False
    assert st["reason"].endswith(" · no earlier read")


def test_stocktwits_keep_never_touches_reddit_or_hn(wire):
    coll = FakeColl(cached_doc(st_good()))
    wire(coll, st_down(), thoughtful=reddit_ok(4), momentum=reddit_ok(6))
    out = run()
    assert out["thoughtful"]["mentions_7d"] == 4   # fresh, not cached 9
    assert out["momentum"]["mentions_7d"] == 6
    assert out["hn"]["n"] == 3                     # fresh, not cached 99
    assert "stale" not in out                      # payload-level flag is Reddit's
    assert out["stocktwits"]["stale"] is True


def test_stale_since_never_after_fetched_at(wire):
    # A clock-skewed cache row (fetched_at in the future) is clamped.
    coll = FakeColl(cached_doc(st_good(), fetched_at=NOW + 999))
    wire(coll, st_down())
    out = run()
    assert out["stocktwits"]["stale_since"] <= out["fetched_at"]


def test_reddit_keep_stale_reason_is_the_served_sentence(wire):
    coll = FakeColl(cached_doc(st_good()))
    wire(coll, st_good(), thoughtful=reddit_down(), momentum=reddit_down())
    out = run()
    assert out["stale"] is True
    assert out["stale_reason"] == reddit_down()["reason"]
    assert "rate-limit?" not in out["stale_reason"]
    assert out["stale_reason"] != "reddit unavailable; showing last good fetch"


def test_both_outages_reddit_keep_serves_stale_stocktwits(wire):
    coll = FakeColl(cached_doc(st_good(3, 3, 0)))
    wire(coll, st_down(), thoughtful=reddit_down(), momentum=reddit_down())
    out = run()
    assert out["stale"] is True
    st = out["stocktwits"]
    assert st["stale"] is True and st["bullish"] == 3
    assert st["stale_reason"] == OUTAGE


def test_fast_path_cache_hit_untouched(wire):
    # Within the 15-min TTL and refresh=False the cached payload returns as is.
    coll = FakeColl(cached_doc(st_good(), fetched_at=NOW - 60))
    wire(coll, st_down())
    out = asyncio.run(fc.chatter_for("POM"))
    assert out["cached"] is True
    assert "stale" not in out["stocktwits"]
    assert coll.writes == []


LEGACY = "all subs returned errors (rate-limit?)"


def legacy_reddit():
    return {"available": False, "partial": False, "threads": [],
            "mentions_7d": 0, "mentions_prior_7d": 0, "reason": LEGACY}


def test_reddit_keep_replaces_legacy_rate_limit_lanes(wire):
    # Critic 23 HIGH: a cached row whose failed lanes carry the old typed
    # "(rate-limit?)" guess must serve the fresh A3 sentence instead.
    import json
    doc = cached_doc(st_good())
    doc["payload"]["thoughtful"] = legacy_reddit()
    doc["payload"]["momentum"] = legacy_reddit()
    coll = FakeColl(doc)
    wire(coll, st_down(), thoughtful=reddit_down(), momentum=reddit_down())
    out = run()
    assert "(rate-limit?)" not in json.dumps(out)
    sentence = reddit_down()["reason"]
    assert out["thoughtful"]["reason"] == sentence
    assert out["momentum"]["reason"] == sentence
    assert out["thoughtful"]["reason_code"] == "blocked"


def test_reddit_keep_keeps_a_good_old_lane(wire):
    # NEGATIVE: a cached lane that was available is not replaced by the failure.
    coll = FakeColl(cached_doc(st_good()))
    wire(coll, st_good(), thoughtful=reddit_down(), momentum=reddit_down())
    out = run()
    assert out["thoughtful"]["available"] is True
    assert out["thoughtful"]["mentions_7d"] == 9
    assert out["momentum"]["mentions_7d"] == 9


def test_reddit_keep_summary_reads_the_served_stocktwits(wire):
    # Critic 23 MED: summary must match the served StockTwits block.
    doc = cached_doc(st_down("StockTwits is not reachable", "unreachable"))
    doc["payload"]["summary"] = {"stocktwits_bullish": 0,
                                 "stocktwits_bearish": 0}
    coll = FakeColl(doc)
    wire(coll, st_good(bull=7, bear=2), thoughtful=reddit_down(),
         momentum=reddit_down())
    out = run()
    assert out["stocktwits"]["bullish"] == 7
    assert out["summary"]["stocktwits_bullish"] == out["stocktwits"]["bullish"]
    assert out["summary"]["stocktwits_bearish"] == out["stocktwits"]["bearish"]
    assert out["summary"]["mentions_7d"] == 18     # the kept good lanes 9 + 9


def test_reddit_keep_saves_a_good_stocktwits_read_without_moving_fetched_at(wire):
    # Critic 23 LOW: a good StockTwits read during a Reddit outage is saved
    # (payload.stocktwits + stocktwits_last_good_at); fetched_at is untouched.
    coll = FakeColl(cached_doc(st_down("StockTwits is not reachable",
                                       "unreachable")))
    wire(coll, st_good(bull=7, bear=2), thoughtful=reddit_down(),
         momentum=reddit_down())
    run()
    assert len(coll.writes) == 1
    written = coll.writes[0]["$set"]
    assert set(written) == {"payload.stocktwits", "stocktwits_last_good_at"}
    assert written["payload.stocktwits"]["bullish"] == 7
    assert written["stocktwits_last_good_at"] == NOW
    assert "fetched_at" not in written


def test_reddit_keep_no_write_when_stocktwits_has_no_good_read(wire):
    # NEGATIVE: both down and no earlier StockTwits read → nothing written.
    coll = FakeColl(cached_doc(st_down("StockTwits is not reachable",
                                       "unreachable")))
    wire(coll, st_down(), thoughtful=reddit_down(), momentum=reddit_down())
    out = run()
    assert coll.writes == []
    assert out["stocktwits"]["reason"].endswith(" · no earlier read")
