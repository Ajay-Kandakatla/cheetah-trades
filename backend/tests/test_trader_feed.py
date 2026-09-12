"""📌 GnT tracker — Tito Adhikary (@GnT_Trades), 2026-09-12.

Ajay: "create a tab for me. I wanna track his stocks for investing" + "do this
daily twice".

EVERY TEST HERE EXISTS BECAUSE A NAIVE CASHTAG SCRAPER INVERTS HIM. His real
posts carry two incompatible kinds of mention:

    forward idea  "$SPCX reclaiming 150 into the close. Definitely on watch
                   next week, it held up nice all week"
    closed recap  "Great day on $QQQ puts, +$12K"
                  "Best trades were on $NVDA $RKLB $GS $NFLX $META"
                  "Traded $NFLX $NVDA $BBBY today"      (2022; BBBY is bankrupt)

and one post — "caught the upside on $FSLR and downside on $META $TSLA" —
carries BOTH directions split across its tickers, which is why this module is
forbidden from asserting a direction per ticker at all.

No network: every test drives the pure functions with real post text captured
from his timeline on 2026-09-12.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from traders import feed as G


# Real text, copied verbatim from his timeline on 2026-09-12.
FRESH_ID = "2098496057860673898"        # 2026-09-11 19:37Z
FRESH_TXT = ("$SPCX reclaiming 150 into the close. Definitely on watch next "
             "week, it held up nice all week https://t.co/hVhyEiLtUF")
PUTS_TXT = ("Great day on $QQQ puts, +$12K - gap up after 4 consecutive green "
            "days + the day before FOMC - fail of overnight support")
RECAP_TXT = ("New personal best week, +$75K! Lot of breakouts this week Best "
             "trades were on $NVDA $RKLB $GS $NFLX $META")
BOTH_WAYS = ("Strong day, +4k Good day with a few opportunities... caught the "
             "upside on $FSLR and downside on $META $TSLA")
TAPE_TXT = ("Have a good weekend everyone Harder week with $SPY $QQQ weak "
            "until the last day of the week, lack of momentum in general")


# ───────────────────────────────────────────────────────────── the timestamp
def test_the_post_time_comes_out_of_the_tweet_id_itself():
    """The recent source ships NO created_at, and a tracker with no timestamps
    cannot tell a live idea from a 2022 recap — the one distinction that
    matters on this board."""
    iso = G.snowflake_iso(FRESH_ID)
    assert iso is not None
    t = datetime.fromisoformat(iso)
    assert t.year == 2026 and t.month == 9 and t.day == 11


def test_NEGATIVE_a_junk_id_yields_no_time_rather_than_a_wrong_one():
    for bad in ("", "abc", None, "12", "999999999999999999999999"):
        assert G.snowflake_iso(bad) is None


# ───────────────────────────────────────────────────────────── the cashtags
def test_it_reads_the_tickers_out_of_a_real_post():
    assert G.cashtags(FRESH_TXT) == ["SPCX"]
    assert G.cashtags(RECAP_TXT) == ["NVDA", "RKLB", "GS", "NFLX", "META"]


def test_the_first_ticker_keeps_its_place_because_the_post_is_about_it():
    assert G.cashtags(RECAP_TXT)[0] == "NVDA"
    assert G.cashtags("$SMCI don't love the stock but can't ignore the chart") == ["SMCI"]


def test_NEGATIVE_a_dollar_amount_is_not_a_ticker():
    """'+$12K', '+$75K', '$45 from $2' are money. A scraper that reads them as
    tickers invents names he never mentioned."""
    for txt in ("New personal best week, +$75K!", "Great day, +$12K",
                "sold my last couple runners on the swing $45 from $2"):
        assert G.cashtags(txt) == [], txt


def test_NEGATIVE_the_same_ticker_twice_is_one_ticker():
    assert G.cashtags("Traded $NFLX $NVDA $BBBY today, $NFLX and $NVDA ideas") \
        == ["NFLX", "NVDA", "BBBY"]


# ─────────────────────────────────────────────── direction is NEVER asserted
def test_the_words_are_REPORTED_not_resolved_into_a_direction():
    f = G.flags(PUTS_TXT)
    assert "puts" in f, "a put trade must be visible as a put"
    assert "recap" in f


def test_THE_CENTRAL_NEGATIVE_one_post_can_carry_both_directions():
    """His own post: "caught the upside on $FSLR and downside on $META $TSLA".

    Post-level sentiment is PROVABLY WRONG here — one sentence, two directions,
    split across three tickers. Any module that emitted a single direction for
    this post would mark META and TSLA as longs. So it must surface both words
    and never collapse them, and it must expose no direction field at all."""
    f = G.flags(BOTH_WAYS)
    assert "long" in f and "short" in f, "both readings must survive"
    row = {"symbol": "META", "text": BOTH_WAYS}
    posts = [{"id": "1", "text": BOTH_WAYS, "created_at": G.snowflake_iso(FRESH_ID),
              "cashtags": G.cashtags(BOTH_WAYS), "flags": f, "url": "u"}]
    out = G.tickers(posts)
    for r in out:
        assert "direction" not in r, "this module must not claim a direction"
        assert "bias" not in r and "signal" not in r
    del row


# ───────────────────────────────────────────── the ticker rows and their age
def _post(pid, text, when):
    return {"id": pid, "text": text, "created_at": when.isoformat(),
            "cashtags": G.cashtags(text), "flags": G.flags(text),
            "url": f"https://x.com/{G.HANDLE}/status/{pid}"}


def test_every_ticker_row_carries_the_sentence_that_produced_it():
    """A ticker with no sentence beside it is how '$QQQ puts, +$12K' becomes a
    long idea."""
    now = datetime.now(timezone.utc)
    rows = G.tickers([_post("1", RECAP_TXT, now - timedelta(days=400))])
    assert rows
    for r in rows:
        assert r["last_post"]["text"] == RECAP_TXT
        assert r["last_post"]["url"].startswith("https://x.com/")


def test_a_recent_post_is_fresh_and_a_2022_recap_is_not():
    now = datetime.now(timezone.utc)
    rows = G.tickers([_post("1", FRESH_TXT, now - timedelta(days=1)),
                      _post("2", RECAP_TXT, now - timedelta(days=400))], now=now)
    by = {r["symbol"]: r for r in rows}
    assert by["SPCX"]["fresh"] is True
    assert by["NVDA"]["fresh"] is False
    assert by["NVDA"]["age_days"] == 400


def test_NEGATIVE_an_unknown_age_is_NOT_fresh():
    """Unknown must never read as current — that is how a 2022 mention of a
    bankrupt name lands at the top of a board labelled 'his stocks'."""
    rows = G.tickers([{"id": "x", "text": FRESH_TXT, "created_at": None,
                       "cashtags": ["SPCX"], "flags": [], "url": "u"}])
    assert rows[0]["age_days"] is None
    assert rows[0]["fresh"] is False


def test_the_feed_is_ordered_by_RECENCY_not_by_mention_count():
    """Stale-but-repeated is exactly the shape that must not lead. TSLA is
    mentioned six times across his history; SPCX once, yesterday."""
    now = datetime.now(timezone.utc)
    posts = [_post(str(i), "$TSLA still going", now - timedelta(days=300 + i))
             for i in range(6)]
    posts.append(_post("99", FRESH_TXT, now - timedelta(days=1)))
    rows = G.tickers(posts, now=now)
    assert rows[0]["symbol"] == "SPCX"
    assert rows[0]["mentions"] == 1
    tsla = next(r for r in rows if r["symbol"] == "TSLA")
    assert tsla["mentions"] == 6, "the count is still reported, just not the rank"


def test_NEGATIVE_index_tickers_are_the_TAPE_not_stocks_he_likes():
    """'Harder week with $SPY $QQQ weak' is him describing the market. Listing
    SPY as one of his stocks — while he is calling it WEAK — inverts him."""
    now = datetime.now(timezone.utc)
    rows = G.tickers([_post("1", TAPE_TXT, now)], now=now)
    assert [r["symbol"] for r in rows] == []
    assert "SPY" in G.MARKET_TICKERS and "QQQ" in G.MARKET_TICKERS


# ─────────────────────────────────────────────────────── fetching and fences
def test_the_recent_parser_pairs_a_post_with_its_own_id():
    import base64
    gid = base64.b64encode(b"Tweet:2098496057860673898").decode()
    html = (f'"client:{gid}:details":$R[9]={{__typename:"TBirdData",'
            f'display_text_range:[0,140],full_text:"$SPCX reclaiming 150"}}')
    out = G._parse_recent(html)
    assert len(out) == 1
    assert out[0]["id"] == "2098496057860673898"
    assert out[0]["text"] == "$SPCX reclaiming 150"
    assert out[0]["source"] == "recent"


def test_THE_LOUD_FAILURE_no_recent_posts_means_not_ok():
    """The syndication source is stale by construction — it spans 2022-2026 and
    does NOT carry yesterday's posts. If the RECENT source breaks, the board
    would keep rendering 101 old posts and look perfectly alive while it had
    stopped tracking him. That must surface."""
    def getter(url):
        return "<script id=\"__NEXT_DATA__\">{\"props\":{\"pageProps\":{\"timeline\":{\"entries\":[]}}}}</script>" \
            if "syndication" in url else "<html>nothing parseable</html>"
    out = G.fetch(getter=getter)
    assert out["ok"] is False
    assert any("latest posts" in e for e in out["errors"])


def test_NEGATIVE_a_dead_network_returns_a_payload_instead_of_raising():
    out = G.fetch(getter=lambda url: None)
    assert out["ok"] is False and out["posts"] == []
    assert out["errors"]


def test_the_cited_win_is_stored_WITH_its_source_and_its_caveat():
    """2,115.1% is HIS claim quoted from @USICOfficial — not a number this app
    measured, and not a transferable track record."""
    u = G.USIC_2025
    assert u["return_pct"] == 2115.1 and u["rank"] == 1
    assert "USICOfficial" in u["source"]
    assert "leverage" in u["note"] or "concentration" in u["note"]


def test_the_module_makes_no_forward_claim_and_gates_nothing():
    # whitespace-normalised: the docstring wraps, the assertion should not care
    doc = " ".join((G.__doc__ or "").lower().split())
    assert "nothing here is a signal, a gate or a lane" in doc
    assert "no scan consumes it, no alert fires from it, nothing buys from it" in doc
    # and the caveat travels with the DATA, not only in a docstring nobody opens
    d = G.board(coll=_EmptyColl()).get("disclaimer", "")
    assert "not advice" in d.lower() and "not a portfolio" in d.lower()
    assert "puts" in d.lower(), "the put problem must be stated on the board itself"


class _EmptyColl:
    """A Mongo stand-in so board() can be exercised with no database."""

    def find(self, *a, **k):
        return self

    def sort(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return []


def test_NEGATIVE_the_board_never_fetches_on_a_page_load():
    """A page load must not depend on X answering."""
    import inspect
    src = inspect.getsource(G.board)
    assert "fetch(" not in src, "board() must read STORED posts only"


# ── the registry (2026-09-12) ───────────────────────────────────────────────
# Ajay: "Also track their mentions for me.. Martin Luk +969.8% (stocks)".
def test_both_champions_are_registered_with_CITED_claims():
    from traders import registry as R
    assert set(R.keys()) == {"gnt", "martinluk"}
    for t in R.TRADERS:
        u = t["usic"]
        assert u["source"], f"{t['key']}: a championship claim needs its source"
        assert u["year"] == 2025 and u["rank"] == 1
        assert t["handle"] and t["display"]


def test_the_handles_are_the_ones_he_gave_me():
    from traders import registry as R
    assert R.get("gnt")["handle"] == "GnT_Trades"
    assert R.get("martinluk")["handle"] == "martinlukkt"


def test_NEGATIVE_the_969_8_decimal_was_NOT_invented():
    """He wrote "+969.8%". Martin's own bio and TraderLion both say 969%. The
    extra decimal is not resolvable from any public source, so the stored
    figure is the one his bio states rather than the one that looks precise."""
    from traders import registry as R
    assert R.get("martinluk")["usic"]["return_pct"] == 969.0


def test_the_two_feeds_cannot_merge_into_one_archive():
    """`stored(trader=...)` filters; a board that showed both would attribute
    one trader's idea to the other."""
    import inspect
    from traders import feed as F
    assert 'q = {} if trader is None else {"trader": trader}' in inspect.getsource(F.stored)
    assert '"trader": trader' in inspect.getsource(F.store)


def test_one_failing_account_does_not_stop_the_others():
    import inspect
    from traders import feed as F
    src = inspect.getsource(F.refresh_all)
    assert "except Exception" in src and "continue" not in src.split("except")[0]


def test_the_disclaimer_is_shared_so_no_surface_can_soften_it():
    from traders import registry as R
    d = R.DISCLAIMER.lower()
    assert "not advice" in d and "not a portfolio" in d and "puts" in d
    assert "not a transferable track record" in d
