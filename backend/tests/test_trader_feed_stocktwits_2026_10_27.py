"""📌 algo888 on StockTwits joins the traders board (2026-10-27).

Ajay, 2026-10-27 ~08:45 ET: "Can you track this guy please? and his tickers"
(https://stocktwits.com/algo888), then "Add them to Gajjals, they are pretty
good".

The fixture is HIS REAL stream page of 2026-10-27 (98 KB, read through the
house client at ~08:59 ET): 30 messages, all by algo888, 12:14:26Z–13:56:49Z;
19 carry `symbols` (GPUS ×15, MXCT ×4); his own label sits in
`entities.sentiment.basic` (Bullish ×27, none ×3); bodies are HTML-escaped; 7
are reshares whose INNER message is never his post.

UNMEASURED: nothing here reads his names as good or bad. No network anywhere in
this file — every fetch is stubbed at a seam.
"""
from __future__ import annotations

import copy
import html
import inspect
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import stocktwits_client as stc
from traders import curate as C
from traders import feed as G
from traders import registry as R

FIX = Path(__file__).parent / "fixtures"
PAGE = json.loads((FIX / "stocktwits_user_algo888_2026_10_27.json").read_text())
MSGS = PAGE["messages"]
BY_ID = {m["id"]: m for m in MSGS}
GNT_PAGE = (FIX / "x_profile_GnT_Trades_2026_10_22.html").read_text()
SYND_ONE = ('<script id="__NEXT_DATA__">{"props":{"pageProps":{"timeline":{"entries":'
            '[{"content":{"tweet":{"id_str":"1500000000000000000","full_text":"old $NVDA recap",'
            '"favorite_count":9,"created_at":"x"}}}]}}}}</script>')

# The GnT posts `refresh(trader="gnt")` stored on 2026-10-27 BEFORE this
# change, captured from that day's `fetch()` over the 10-22 page + SYND_ONE
# (minus `first_seen`, which is the wall clock). Frozen: the x path must not
# move by one byte.
FROZEN_GNT_DOCS = json.loads(r"""[{"_id": "1500000000000000000", "cashtags": ["NVDA"], "created_at": "2022-03-05T06:47:23.309000+00:00", "created_at_raw": "x", "favorites": 9, "flags": [], "id": "1500000000000000000", "source": "top", "text": "old $NVDA recap", "trader": "gnt", "url": "https://x.com/GnT_Trades/status/1500000000000000000"}, {"_id": "2016662579427397790", "author": "GnT_Trades", "cashtags": [], "created_at": "2026-01-29T00:00:01.371000+00:00", "created_at_ms": 1769644801000, "favorites": 1873, "flags": [], "id": "2016662579427397790", "pinned": true, "shape": "relay", "source": "recent", "text": "It's finally official From opening my first brokerage account less than 6 years ago to winning the US Investing Championship with a new all-time contest record... I'm honored and grateful to share that I won the $20k+ Enhanced Growth Division with a 2,115% return in 2025. https://t.co/2zXUgzNFnj", "trader": "gnt", "url": "https://x.com/GnT_Trades/status/2016662579427397790"}, {"_id": "2112904111276658898", "author": "GnT_Trades", "cashtags": ["NBIS"], "created_at": "2026-10-21T13:49:30.645000+00:00", "created_at_ms": 1792590570000, "favorites": 13, "flags": [], "id": "2112904111276658898", "pinned": false, "shape": "relay", "source": "recent", "text": "15 mins into the open and neoclouds already taking a lot of heat with a lot of names down over 3% since the opening print Not the best action on names like $NBIS - was at 183 in the overnight hours down almost 18 from there now https://t.co/2n81BuCFtI", "trader": "gnt", "url": "https://x.com/GnT_Trades/status/2112904111276658898"}, {"_id": "2112906454336262499", "author": "GnT_Trades", "cashtags": ["TWST", "TXG"], "created_at": "2026-10-21T13:58:49.274000+00:00", "created_at_ms": 1792591129000, "favorites": 12, "flags": [], "id": "2112906454336262499", "pinned": false, "shape": "relay", "source": "recent", "text": "A few genomics names $TWST $TXG finding buyers off the 50d SMA this morning https://t.co/1sNoj49BOZ", "trader": "gnt", "url": "https://x.com/GnT_Trades/status/2112906454336262499"}, {"_id": "2112980230667485574", "author": "GnT_Trades", "cashtags": ["CRWD"], "created_at": "2026-10-21T18:51:58.922000+00:00", "created_at_ms": 1792608718000, "favorites": 20, "flags": [], "id": "2112980230667485574", "pinned": false, "shape": "relay", "source": "recent", "text": "Based on how cyber has been acting today and in general on dips this year, $CRWD probably not a bad buy here around the 50d SMA https://t.co/DhuLGG19EW", "trader": "gnt", "url": "https://x.com/GnT_Trades/status/2112980230667485574"}, {"_id": "2112980501086822804", "author": "GnT_Trades", "cashtags": ["TSLA"], "created_at": "2026-10-21T18:53:03.395000+00:00", "created_at_ms": 1792608783000, "favorites": 11, "flags": [], "id": "2112980501086822804", "pinned": false, "shape": "relay", "source": "recent", "text": "$TSLA right at the 200d SMA into earnings https://t.co/NlGpAOEMsV", "trader": "gnt", "url": "https://x.com/GnT_Trades/status/2112980501086822804"}]""")

# The x refresh line, exactly as it read before 2026-10-27.
X_LINE = "f = fetch(recent_url=recent_url(handle), top_url=top_url(handle), handle=handle)"


def _posts():
    return G.parse_stocktwits(copy.deepcopy(MSGS), "algo888")


def _ok_stream(*a, **k):
    return {"ok": True, "reason": None, "reason_code": "ok",
            "messages": copy.deepcopy(MSGS), "pages": 1}


class _Coll:
    """A one-collection Mongo stand-in: find_one / replace_one / update_one /
    find-sort-limit (the 10-22 test's)."""

    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q.get("_id"))

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)

    def update_one(self, q, u, upsert=False):
        cur = dict(self.docs.get(q["_id"]) or {})
        if not cur:
            cur.update(u.get("$setOnInsert") or {})
        cur.update(u.get("$set") or {})
        self.docs[q["_id"]] = cur

    def find(self, q=None):
        self._q = q or {}
        return self

    def sort(self, *a, **k):
        return self

    def limit(self, n):
        rows = [d for d in self.docs.values()
                if all(d.get(k) == v for k, v in self._q.items())]
        return sorted(rows, key=lambda d: d.get("created_at") or "", reverse=True)[:n]


@pytest.fixture(autouse=True)
def _no_overlay(monkeypatch):
    """board() attaches this app's own read per ticker (universe, growth,
    zones) — Mongo-backed and not under test here."""
    monkeypatch.setattr(G, "overlay", lambda rows: rows)
    yield


# ───────────────────────────────────────────────── parse_stocktwits
def test_the_real_page_is_30_posts_19_with_names():
    posts = _posts()
    assert len(posts) == 30
    assert sum(1 for p in posts if p["cashtags"]) == 19
    rows = {r["symbol"]: r["mentions"] for r in G.tickers(posts)}
    assert rows == {"GPUS": 15, "MXCT": 4}


def test_ids_are_st_prefixed():
    posts = _posts()
    assert all(p["id"].startswith("st") for p in posts)
    assert {p["id"] for p in posts} == {f"st{m['id']}" for m in MSGS}
    # never a bare number that could collide with a tweet id in the same archive
    assert not any(p["id"].isdigit() for p in posts)


def test_html_entities_are_unescaped():
    by = {p["id"]: p for p in _posts()}
    assert by["st667436141"]["text"] == "@CantAffordMe nah, you're just slow.."
    assert "&" in by["st667429197"]["text"] and "&amp;" not in by["st667429197"]["text"]
    assert not any("&#39;" in p["text"] or "&amp;" in p["text"] for p in by.values())


def test_created_at_is_utc_from_stocktwits_own_stamp():
    by = {p["id"]: p for p in _posts()}
    assert by["st667426628"]["created_at"] == "2026-10-27T12:28:48+00:00"
    for m in MSGS:
        iso = by[f"st{m['id']}"]["created_at"]
        assert iso.endswith("+00:00") and not iso.endswith("Z")
        assert datetime.fromisoformat(iso).timestamp() == stc.parse_created_at(m["created_at"])


def test_the_url_is_his_message_page():
    by = {p["id"]: p for p in _posts()}
    assert by["st667426628"]["url"] == "https://stocktwits.com/algo888/message/667426628"
    assert all(p["url"] == f"https://stocktwits.com/algo888/message/{p['id'][2:]}"
               for p in by.values())


def test_sentiment_is_his_own_word_or_none():
    s = [p["sentiment"] for p in _posts()]
    assert s.count("Bullish") == 27 and s.count(None) == 3
    assert set(s) == {"Bullish", None}, "his label as found — never inferred"


def test_symbols_meta_kept():
    by = {p["id"]: p for p in _posts()}
    assert by["st667426628"]["symbols_meta"] == [
        {"symbol": "GPUS", "exchange": "NYSEMkt", "instrument_class": "Stock",
         "trade_status": None}]
    assert by["st667436630"]["symbols_meta"] == [
        {"symbol": "MXCT", "exchange": "NASDAQ", "instrument_class": "Stock",
         "trade_status": "WHOLE"}]
    for p in by.values():
        assert p["source"] == "stocktwits" and p["shape"] == "stocktwits_v2"
        assert p["author"] == "algo888"


def test_NEGATIVE_a_message_by_another_username_is_not_his():
    other = copy.deepcopy(BY_ID[667426628])
    other["id"] = 1
    other["user"] = {**other["user"], "username": "WC25"}
    posts = G.parse_stocktwits([other] + copy.deepcopy(MSGS), "algo888")
    assert "st1" not in {p["id"] for p in posts}
    assert len(posts) == 30
    # the handle check is case-insensitive, never a substring match
    assert G.parse_stocktwits([copy.deepcopy(BY_ID[667426628])], "ALGO888")
    assert G.parse_stocktwits([copy.deepcopy(BY_ID[667426628])], "algo88") == []


def test_NEGATIVE_an_empty_body_is_skipped():
    msgs = []
    for i, body in enumerate(("", "   \n ", "&nbsp;", None)):
        m = copy.deepcopy(BY_ID[667426628])
        m["id"], m["body"] = 10 + i, body
        msgs.append(m)
    assert G.parse_stocktwits(msgs, "algo888") == []


def test_NEGATIVE_a_reshared_inner_message_is_never_a_post():
    posts = _posts()
    texts = " ".join(p["text"] for p in posts)
    assert "Closing @ high of day" not in texts
    inner = {m["reshare_message"]["message"]["id"] for m in MSGS if m.get("reshare_message")}
    assert len(inner) == 7
    # an inner message that is ALSO on the page as his own outer message
    # (he reshared himself, e.g. 667428037) is a post because of the OUTER one;
    # every inner-only id must be absent
    inner_only = inner - set(BY_ID)
    assert inner_only and 667389844 in inner_only
    assert not ({f"st{i}" for i in inner_only} & {p["id"] for p in posts})
    assert len(posts) == len(MSGS)
    # the OUTER message of a reshare is his own sentence and stays
    assert next(p for p in posts if p["id"] == "st667436630")["text"] == "$MXCT nice"


# ───────────────────────────────────────────────── fetch_stocktwits
def test_fetch_stocktwits_ok_on_the_real_page():
    seen = []

    def getter(handle, **kw):
        seen.append((handle, kw))
        return _ok_stream()

    out = G.fetch_stocktwits("algo888", getter, pages=2, timeout=5.0)
    assert out["ok"] is True and out["errors"] == []
    assert out["sources"] == {"recent": 30, "top": 0}
    assert out["recent_shape"] == "stocktwits_v2"
    ats = [p["created_at"] for p in out["posts"]]
    assert ats == sorted(ats, reverse=True), "newest first"
    assert seen == [("algo888", {"max_pages": 2, "timeout": 5.0})]
    # pages / timeout None → the client's own defaults (nothing passed)
    G.fetch_stocktwits("algo888", getter)
    assert seen[-1] == ("algo888", {})
    # the default getter is the house client's user stream
    assert "stocktwits_client.fetch_user_stream" in inspect.getsource(G.fetch_stocktwits)


def test_NEGATIVE_a_dark_stream_is_not_ok_and_says_the_client_sentence():
    dark = G.fetch_stocktwits("algo888", lambda h, **k: {
        "ok": False, "reason": stc.SENTENCE_CHALLENGE, "reason_code": "challenge",
        "messages": [], "pages": 0})
    assert dark["ok"] is False and dark["posts"] == []
    assert dark["errors"] == [stc.SENTENCE_CHALLENGE]
    assert dark["recent_shape"] is None and dark["sources"] == {"recent": 0, "top": 0}
    empty = G.fetch_stocktwits("algo888", lambda h, **k: {"ok": True, "messages": []})
    assert empty["ok"] is False and empty["errors"] == [G.ST_EMPTY_ERROR]
    # a stream full of OTHER people's messages is not his either
    other = copy.deepcopy(MSGS)
    for m in other:
        m["user"]["username"] = "someoneelse"
    notmine = G.fetch_stocktwits("algo888", lambda h, **k: {"ok": True, "messages": other})
    assert notmine["ok"] is False and notmine["errors"] == [G.ST_EMPTY_ERROR]


def test_NEGATIVE_fetch_stocktwits_never_raises():
    def boom(*a, **k):
        raise RuntimeError("https://api.stocktwits.com curl: (28) secret")

    out = G.fetch_stocktwits("algo888", boom)
    assert out["ok"] is False and out["posts"] == []
    assert out["errors"] == ["RuntimeError"], "the type name only — never the exception text"
    assert G.fetch_stocktwits("algo888", lambda h, **k: None)["ok"] is False
    assert G.fetch_stocktwits("algo888", lambda h, **k: {"ok": True, "messages": [None, 7]})["ok"] is False


# ───────────────────────────────────────────────── refresh
def test_refresh_dispatches_on_source(monkeypatch):
    calls = []
    monkeypatch.setattr(stc, "fetch_user_stream",
                        lambda h, **k: calls.append((h, k)) or _ok_stream())
    monkeypatch.setattr(G, "fetch", lambda *a, **k: pytest.fail("x fetch on a StockTwits account"))
    posts, st = _Coll(), _Coll()
    r = G.refresh(coll=posts, trader="algo888", status_coll=st)
    assert calls == [("algo888", {"max_pages": G.TRADER_ST_PAGES})]
    assert r["ok"] is True and r["stored"] == 30 and r["source"] == "stocktwits"
    assert r["recent_shape"] == "stocktwits_v2"
    assert all(d["trader"] == "algo888" and d["_id"].startswith("st") for d in posts.docs.values())
    assert st.docs["algo888"]["source"] == "stocktwits" and st.docs["algo888"]["ok"] is True
    # the pass's in-pass read: its own pages and timeout
    G.refresh(coll=posts, trader="algo888", status_coll=st, pages=1, timeout=5.0)
    assert calls[-1] == ("algo888", {"max_pages": 1, "timeout": 5.0})
    # an x account never touches StockTwits (the real x fetch, stubbed at _get)
    monkeypatch.undo()
    monkeypatch.setattr(stc, "fetch_user_stream",
                        lambda *a, **k: pytest.fail("StockTwits read on an x account"))
    monkeypatch.setattr(G, "_get", lambda url: SYND_ONE if "syndication" in url else GNT_PAGE)
    g = G.refresh(coll=_Coll(), trader="gnt", status_coll=st)
    assert g["source"] == "x" and g["recent_shape"] == "relay"
    assert st.docs["gnt"]["source"] == "x"


def test_NEGATIVE_the_x_refresh_path_is_byte_identical(monkeypatch):
    monkeypatch.setattr(G, "_get", lambda url: SYND_ONE if "syndication" in url else GNT_PAGE)
    monkeypatch.setattr(stc, "fetch_user_stream",
                        lambda *a, **k: pytest.fail("StockTwits read on the x path"))
    posts, st = _Coll(), _Coll()
    G.refresh(coll=posts, trader="gnt", status_coll=st, pages=9, timeout=0.1)
    docs = sorted(({k: v for k, v in d.items() if k != "first_seen"}
                   for d in posts.docs.values()), key=lambda d: d["_id"])
    assert json.dumps(docs, sort_keys=True, ensure_ascii=False) == \
        json.dumps(FROZEN_GNT_DOCS, sort_keys=True, ensure_ascii=False)
    assert X_LINE in inspect.getsource(G.refresh)
    # and the x reader itself never learned a StockTwits word
    assert "stocktwits" not in inspect.getsource(G.fetch).lower()


# ───────────────────────────────────────────────── board
def test_board_for_algo888_serves_source_profile_and_no_claim(monkeypatch):
    monkeypatch.setattr(stc, "fetch_user_stream", _ok_stream)
    posts, st = _Coll(), _Coll()
    G.refresh(coll=posts, trader="algo888", status_coll=st)
    b = G.board(coll=posts, trader="algo888", status_coll=st)
    assert b["key"] == "algo888" and b["handle"] == "algo888"
    assert b["source"] == "stocktwits" and b["source_text"] == "on StockTwits"
    assert b["profile_url"] == "https://stocktwits.com/algo888"
    assert b["profile"] == R.get("algo888")["profile"]
    assert b["profile"]["user_id"] == 2124563 and b["profile"]["followers"] == 3846
    assert b["usic"] is None and b["claim_text"] is None
    assert b["gajjala_text"] == G.GAJJALA_TEXT
    assert b["n_posts"] == 30 and [r["symbol"] for r in b["tickers"]] == ["MXCT", "GPUS"]
    assert "StockTwits stream answered with 30 posts" in b["refresh"]["note"]


def test_NEGATIVE_a_claimless_trader_never_shows_gnts_2115():
    b = G.board(coll=_Coll(), trader="algo888", status_coll=_Coll())
    blob = json.dumps(b, default=str)
    assert "2115" not in blob and "USIC" not in blob
    assert b["usic"] is None
    assert "or USIC_2025" not in inspect.getsource(G.board)
    # the x champions keep their own claim and no Gajjala sentence
    g = G.board(coll=_Coll(), trader="gnt", status_coll=_Coll())
    assert g["usic"]["return_pct"] == 2115.1 and g["gajjala_text"] is None
    assert g["source"] == "x" and g["source_text"] == "on X"
    assert g["profile_url"] == "https://x.com/GnT_Trades"


def test_claim_text_for_gnt_and_martin():
    assert G.claim_text(R.get("gnt")["usic"]) == "USIC 2025 #1 · 2115.1% ($20,000+ Enhanced Growth)"
    m = G.claim_text(R.get("martinluk")["usic"])
    assert m == "USIC 2025 #1 · 969% (Stocks)"
    assert "969.0" not in m
    assert G.board(coll=_Coll(), trader="martinluk", status_coll=_Coll())["claim_text"] == m
    for nothing in (None, {}, {"year": 2025}):
        assert G.claim_text(nothing) is None


def _st_run(ok, at, errors=None):
    return {"trader": "algo888", "handle": "algo888", "stored": 30 if ok else 0, "ok": ok,
            "sources": {"recent": 30 if ok else 0, "top": 0},
            "errors": [] if ok else (errors or [stc.SENTENCE_CHALLENGE]),
            "recent_shape": "stocktwits_v2" if ok else None, "fetched_at": at,
            "source": "stocktwits"}


def test_refresh_note_names_the_stocktwits_stream():
    st = _Coll()
    G.store_status(_st_run(True, "2026-10-27T13:00:00+00:00"), status_coll=st)
    ok = G.board(coll=_Coll(), trader="algo888", status_coll=st)["refresh"]["note"]
    assert ok == ("Latest posts checked 2026-10-27 09:00 ET: the StockTwits stream answered "
                  "with 30 posts. Checked twice a day, and by Gajjala's scan while it runs.")
    G.store_status(_st_run(False, "2026-10-27T21:40:00+00:00"), status_coll=st)
    dark = G.board(coll=_Coll(), trader="algo888", status_coll=st)["refresh"]["note"]
    assert dark == ("⚠️ NOT tracking algo888's latest posts: at the 2026-10-27 17:40 ET check "
                    "the StockTwits stream returned no posts — StockTwits is challenging this "
                    "client (http 403) (it last answered 2026-10-27 09:00 ET). The names below "
                    "are the stored archive.")
    assert "x.com" not in ok + dark


def test_NEGATIVE_the_x_note_words_are_unchanged():
    ok = {"at": "2026-10-22T21:40:00+00:00", "ok": True, "sources": {"recent": 5, "top": 101}}
    dark = {"at": "2026-10-22T12:31:00+00:00", "ok": False, "sources": {"recent": 0, "top": 101},
            "last_ok_at": "2026-09-24T21:40:02+00:00"}
    dead = {**dark, "sources": {"recent": 0, "top": 0}, "last_ok_at": None}
    assert G.refresh_note(ok, "Tito Adhikary") == (
        "Latest posts checked 2026-10-22 17:40 ET: the x.com page answered with 5 posts "
        "and the history source with 101. Checked twice a day.")
    assert G.refresh_note(dark, "Tito Adhikary") == (
        "⚠️ NOT tracking Tito Adhikary's latest posts: at the 2026-10-22 08:31 ET check the "
        "x.com page returned no posts (it last answered 2026-09-24 17:40 ET). The history "
        "source answered with 101 posts, so the names below are Tito Adhikary's history, "
        "not what was posted today.")
    assert G.refresh_note(dead, "his") == (
        "⚠️ NOT tracking his latest posts: at the 2026-10-22 08:31 ET check the x.com page "
        "returned no posts (it last answered never). The history source returned nothing "
        "either, so the names below are the stored archive.")
    for s in (ok, dark, dead, None):
        assert G.refresh_note(s, "Tito Adhikary", "x") == G.refresh_note(s, "Tito Adhikary")
        assert "StockTwits" not in G.refresh_note(s, "Tito Adhikary")
    assert G.refresh_block(None, "his")["note"].startswith("No refresh recorded yet")


# ───────────────────────────────────────────────── the registry row
def test_exactly_one_gajjala_flag_and_it_is_algo888():
    flagged = [t["key"] for t in R.TRADERS if t.get("gajjala") is True]
    assert flagged == ["algo888"]
    assert R.keys()[-1] == "algo888", "appended LAST"
    assert R.DEFAULT_KEY == "gnt"
    for k in ("gnt", "martinluk"):
        t = R.get(k)
        assert t["source"] == "x" and t["gajjala"] is False and t["curate"] is True
        assert t["profile_url"] == G.recent_url(t["handle"])
    a = R.get("algo888")
    assert a["source"] == "stocktwits" and a["usic"] is None and a["curate"] is False


def test_every_quote_in_his_style_is_his_own_words():
    a = R.get("algo888")
    fixture_bio = next(m["reshare_message"]["message"]["user"]["bio"]
                       for m in MSGS if m.get("reshare_message"))
    assert a["profile"]["bio"] == fixture_bio, "the bio byte-exact"
    quotes = re.findall(r"“([^”]*)”(?: \((\d\d:\d\d), message (\d+)\))?", a["style"])
    assert len(quotes) == 5
    et = ZoneInfo("America/New_York")
    for frag, hhmm, mid in quotes:
        assert frag
        if mid:
            m = BY_ID[int(mid)]
            assert frag in html.unescape(m["body"]), (mid, frag)
            when = datetime.fromtimestamp(stc.parse_created_at(m["created_at"]), timezone.utc)
            assert when.astimezone(et).strftime("%H:%M") == hhmm, (mid, hhmm)
        else:
            assert frag in fixture_bio, frag


def test_the_disclaimer_carries_the_dated_exception():
    d = R.DISCLAIMER
    assert d.endswith(
        "Nothing here gates a scan, an alert or a lane — except that, by Ajay's "
        "2026-10-27 call, an account flagged for Gajjala's tab has its fresh names "
        "ADDED to that scan's candidate list, tagged 📌; GG's own rules still decide "
        "every read and every A+.")
    assert d.startswith("Their posts, NOT advice and NOT a portfolio.")
    assert "Nothing here gates a scan, an alert or a lane." not in d, \
        "the old last sentence never stands alone without its exception"


# ───────────────────────────────────────────────── the client
class _Resp:
    def __init__(self, body):
        self.status_code, self.headers, self._body = 200, {}, body

    def json(self):
        return self._body


def test_fetch_user_stream_walks_pages_like_fetch_stream(monkeypatch):
    monkeypatch.setattr(stc, "_working_profile", None)
    monkeypatch.setattr(stc, "HAVE_CURL_CFFI", True)
    first = copy.deepcopy(MSGS[:15])
    second = copy.deepcopy(MSGS[15:])
    urls = []

    def stub_get(url, profile, timeout):
        urls.append(url)
        if "?max=" in url:
            return _Resp({"messages": copy.deepcopy(second), "cursor": {"more": False}})
        return _Resp({"messages": copy.deepcopy(first),
                      "cursor": {"more": True, "max": first[-1]["id"]}})

    monkeypatch.setattr(stc, "_http_get", stub_get)
    out = stc.fetch_user_stream(" algo888 ", max_pages=2)
    assert stc.USER_URL == "https://api.stocktwits.com/api/2/streams/user/{username}.json"
    assert urls == ["https://api.stocktwits.com/api/2/streams/user/algo888.json",
                    f"https://api.stocktwits.com/api/2/streams/user/algo888.json?max={first[-1]['id']}"]
    assert out["ok"] is True and out["pages"] == 2 and len(out["messages"]) == 30
    assert all(m["_epoch"] for m in out["messages"])
    urls.clear()
    sym = stc.fetch_stream("gpus", max_pages=2)
    assert urls[0] == "https://api.stocktwits.com/api/2/streams/symbol/GPUS.json"
    assert set(sym) == set(out) and sym["pages"] == 2
    assert "fetch_user_stream" in stc.__all__
    # one page cap by default, like fetch_stream
    urls.clear()
    stc.fetch_user_stream("algo888")
    assert len(urls) == 1


def test_NEGATIVE_a_dark_stocktwits_account_exits_2(monkeypatch):
    monkeypatch.setattr(G, "_get", lambda url: SYND_ONE if "syndication" in url else GNT_PAGE)
    monkeypatch.setattr(stc, "fetch_user_stream", lambda h, **k: {
        "ok": False, "reason": stc.SENTENCE_RATE_LIMITED, "reason_code": "rate_limited",
        "messages": [], "pages": 0})
    st = _Coll()
    all_ = G.refresh_all(coll=_Coll(), status_coll=st)
    a = all_["traders"]["algo888"]
    assert a["ok"] is False and a["stored"] == 0
    assert a["errors"] == [stc.SENTENCE_RATE_LIMITED]
    assert G.exit_code(all_) == 2
    assert G.verdict_word(a) == "NOTHING STORED"
    assert st.docs["algo888"]["source"] == "stocktwits"


# ───────────────────────────────────────────────── A1: the curator (2026-10-27)
class _CurColl:
    def __init__(self):
        self.writes = []

    def find(self, q=None, proj=None):
        return []

    def update_one(self, flt, update, upsert=False):
        self.writes.append((flt["_id"], update["$set"]["status"]))


WOLF_POST = {"id": "2098496057860673898", "text": "$WOLF breakout on watch",
             "created_at": "2026-09-11T19:37:00+00:00",
             "url": "https://x.com/GnT_Trades/status/2098496057860673898",
             "cashtags": ["WOLF"], "flags": ["long", "watch"]}


def _curate_env(monkeypatch):
    import sepa.universe as U
    monkeypatch.setattr(C, "_db", lambda: None)
    monkeypatch.setattr(U, "load_universe", lambda *a, **k: ["AAPL"], raising=False)
    checked = []
    monkeypatch.setattr(C, "validate", lambda s: checked.append(s) or (True, "resolved, 400 bars"))
    monkeypatch.setattr(C, "_warm_cap", lambda s: None)
    by = {"gnt": [WOLF_POST], "martinluk": [], "algo888": _posts()}
    monkeypatch.setattr(G, "stored", lambda limit=400, coll=None, trader=None: list(by.get(trader, [])))
    return checked


def test_NEGATIVE_a_curate_false_trader_never_reaches_full(monkeypatch):
    checked = _curate_env(monkeypatch)
    coll = _CurColl()
    out = C.run(coll=coll)
    syms = {a["symbol"] for a in out["added"]} | {r["symbol"] for r in out["rejected"]}
    assert "GPUS" not in syms and "MXCT" not in syms
    assert "GPUS" not in checked and "MXCT" not in checked, "never even validated"
    assert not any(w[0] in ("GPUS", "MXCT") for w in coll.writes)
    assert out["skipped_traders"] == ["algo888"]
    assert 'if t.get("curate") is False:' in inspect.getsource(C.run)


def test_a_curate_true_trader_is_curated_as_before(monkeypatch):
    _curate_env(monkeypatch)
    now = C.run(coll=_CurColl())
    assert [a["symbol"] for a in now["added"]] == ["WOLF"]
    assert now["added"][0]["trader"] == "gnt"
    # the same run with the PRE-2026-10-27 registry rows (no source / gajjala /
    # curate / profile_url keys) adds exactly the same, byte for byte
    old_rows = [{k: v for k, v in t.items()
                 if k not in ("source", "gajjala", "curate", "profile_url")}
                for t in R.TRADERS if t["key"] in ("gnt", "martinluk")]
    monkeypatch.setattr(R, "TRADERS", old_rows)
    before = C.run(coll=_CurColl())
    assert before["skipped_traders"] == []
    strip = lambda o: {k: v for k, v in o.items() if k != "skipped_traders"}
    assert json.dumps(strip(now), sort_keys=True) == json.dumps(strip(before), sort_keys=True)
