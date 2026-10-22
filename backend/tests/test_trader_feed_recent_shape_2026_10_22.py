"""📌 The latest-posts source went dark for four weeks (2026-09-25 → 10-22).

Observed: `python -m traders.feed refresh` exiting 1 twice a day with
"gnt: stored 101 posts, ok=False, sources={'recent': 0, 'top': 101}" while the
board's newest stored post stayed 2026-09-24 and GnT posted on NBIS, $TWST $TXG,
$CRWD and $TSLA on 10-21.

Root cause, measured from inside the api container on 2026-10-22 (httpx, the
module's own transport, HTTP 200, 274 KB — so NOT a TLS/IP block): X moved the
timeline out of the flat key stream (`client:VHdlZXQ6…:details … full_text`)
into a server-rendered Relay record
(`kind:"GraphQLRequestStream.Completed" … result:{kind:"Result.Ok",value:"…"}`)
whose `value` is an escaped JSON `profile_user_originals_timeline`.

The fixtures are the REAL pages of 2026-10-22 trimmed to that record (plus one
non-timeline record that must be skipped). No network anywhere in this file.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from traders import feed as G

FIX = Path(__file__).parent / "fixtures"
GNT_PAGE = (FIX / "x_profile_GnT_Trades_2026_10_22.html").read_text()
MARTIN_PAGE = (FIX / "x_profile_martinlukkt_2026_10_22.html").read_text()
SYND_EMPTY = ('<script id="__NEXT_DATA__">{"props":{"pageProps":{"timeline":'
              '{"entries":[]}}}}</script>')
SYND_ONE = ('<script id="__NEXT_DATA__">{"props":{"pageProps":{"timeline":{"entries":'
            '[{"content":{"tweet":{"id_str":"1500000000000000000","full_text":"old $NVDA recap",'
            '"favorite_count":9,"created_at":"x"}}}]}}}}</script>')

# What he actually posted on 2026-10-21, read off the fixture by eye.
GNT_1021 = {
    "2112904111276658898": "NBIS",     # "Not the best action on names like $NBIS"
    "2112906454336262499": "TWST",     # "$TWST $TXG finding buyers off the 50d SMA"
    "2112980230667485574": "CRWD",     # "$CRWD probably not a bad buy here"
    "2112980501086822804": "TSLA",     # "$TSLA right at the 200d SMA into earnings"
}
GNT_PINNED = "2016662579427397790"     # 2026-01-29, the championship post


# ───────────────────────────────────────────────── the new shape is read
def test_the_real_2026_10_22_page_yields_his_four_posts_of_10_21_and_the_pin():
    out = G._parse_recent(GNT_PAGE, "GnT_Trades")
    ids = {p["id"] for p in out}
    assert set(GNT_1021) <= ids, "the four 10-21 posts must come out of the new shape"
    assert GNT_PINNED in ids
    assert len(out) == 5
    for p in out:
        assert p["source"] == "recent" and p["shape"] == "relay"
        assert p["author"] == "GnT_Trades"


def test_each_post_carries_its_own_sentence_and_X_s_own_timestamp():
    by = {p["id"]: p for p in G._parse_recent(GNT_PAGE, "GnT_Trades")}
    for tid, sym in GNT_1021.items():
        assert sym in G.cashtags(by[tid]["text"]), (tid, by[tid]["text"])
        # X now ships created_at_ms; it agrees with the snowflake clock the
        # module has always used, to the second.
        ms = by[tid]["created_at_ms"]
        assert isinstance(ms, int)
        snow = datetime.fromisoformat(G.snowflake_iso(tid))
        assert abs(snow.timestamp() - ms / 1000) < 1.0
    assert by[GNT_PINNED]["pinned"] is True
    assert all(by[t]["pinned"] is False for t in GNT_1021)


def test_martin_s_page_reads_too_and_carries_the_posts_the_dark_source_missed():
    """He posted 2026-10-01 and 10-08 — both after the 09-25 break, both
    missed. They must be in the parse now."""
    out = G._parse_recent(MARTIN_PAGE, "martinlukkt")
    days = sorted(G.snowflake_iso(p["id"])[:10] for p in out)
    assert "2026-10-01" in days and "2026-10-08" in days
    assert all(p["author"] == "martinlukkt" for p in out)


def test_a_non_timeline_Result_Ok_record_contributes_nothing():
    """The GnT fixture carries a finance-card record (`finance_asset_data`)
    beside the timeline — a Result.Ok with no posts in it. It must be skipped,
    not misread."""
    assert "finance_asset_data" in GNT_PAGE
    out = G._parse_recent(GNT_PAGE, "GnT_Trades")
    assert len(out) == 5


def test_fetch_end_to_end_on_the_real_page_is_ok_and_the_10_21_ideas_are_fresh():
    def getter(url):
        return SYND_ONE if "syndication" in url else GNT_PAGE
    out = G.fetch(getter=getter, handle="GnT_Trades")
    assert out["ok"] is True
    assert out["sources"] == {"recent": 5, "top": 1}
    assert out["recent_shape"] == "relay"
    assert out["errors"] == []
    now = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)
    rows = {r["symbol"]: r for r in G.tickers(out["posts"], now=now)}
    for sym in ("NBIS", "TWST", "TXG", "CRWD", "TSLA"):
        assert rows[sym]["fresh"] is True, sym
        assert rows[sym]["age_days"] <= 1
    # the pinned championship post is history, not an idea
    pinned = next(p for p in out["posts"] if p["id"] == GNT_PINNED)
    assert G.age_days(pinned["created_at"], now) > G.FRESH_DAYS


def test_the_old_key_stream_shape_still_reads_as_a_fallback():
    """X may roll back. The 2026-09 reader is kept behind the new one."""
    import base64
    gid = base64.b64encode(b"Tweet:2098496057860673898").decode()
    html = (f'"client:{gid}:details":$R[9]={{__typename:"TBirdData",'
            f'display_text_range:[0,140],full_text:"$SPCX reclaiming 150"}}')
    out = G._parse_recent(html, "GnT_Trades")
    assert [p["id"] for p in out] == ["2098496057860673898"]
    assert out[0]["shape"] == "keystream"


# ───────────────────────────────────────────────── NEGATIVES: stays loud
def test_NEGATIVE_the_relay_wrapper_with_no_entries_is_zero_posts_and_NOT_ok():
    html = ('<script>($R=>$R[1].next($R[2]={kind:"GraphQLRequestStream.Completed",'
            'result:$R[3]={kind:"Result.Ok",value:"{\\"data\\":{\\"user_result_by_screen_name\\":'
            '{\\"result\\":{\\"profile_user_originals_timeline\\":{\\"timeline\\":{\\"instructions\\":'
            '[{\\"__typename\\":\\"TimelineClearCache\\"}]}}}}}}"}}))</script>')
    assert G._parse_recent(html, "GnT_Trades") == []
    out = G.fetch(getter=lambda u: SYND_ONE if "syndication" in u else html,
                  handle="GnT_Trades")
    assert out["ok"] is False
    assert out["recent_shape"] is None
    assert G.RECENT_DARK_ERROR in out["errors"]
    assert "NOT tracking" in G.RECENT_DARK_ERROR


def test_NEGATIVE_an_undecodable_value_is_skipped_not_raised():
    html = ('<script>kind:"Result.Ok",value:"{\\"data\\": not json at all"}'
            'kind:"Result.Ok",value:"\\q broken escape"</script>')
    assert G._parse_recent(html, "GnT_Trades") == []
    assert G._decode_js_string('\\q') is None
    assert G._decode_js_string("It\\'s fine") == "It's fine"


def test_NEGATIVE_somebody_else_s_post_on_his_page_is_not_his():
    """A retweet or a quoted post surfaced as an entry carries another author.
    With the handle known it is dropped; with the handle unknown nothing is
    guessed and the post is kept."""
    swapped = GNT_PAGE.replace('\\"screen_name\\":\\"GnT_Trades\\"',
                               '\\"screen_name\\":\\"SomeoneElse\\"')
    assert swapped != GNT_PAGE
    assert G._parse_recent(swapped, "GnT_Trades") == []
    assert len(G._parse_recent(swapped, None)) == 5
    assert len(G._parse_recent(swapped, "someoneelse")) == 5, "case-insensitive"


def test_NEGATIVE_the_quoted_USICOfficial_post_inside_his_pin_is_NOT_a_post_of_his():
    """The pinned post quotes @USICOfficial's congratulation. That nested tweet
    has its own rest_id and full_text; it must not come out as his."""
    assert "Congratulation to Tito Adhikary" in GNT_PAGE
    texts = [p["text"] for p in G._parse_recent(GNT_PAGE, "GnT_Trades")]
    assert not any("Congratulation to Tito" in t for t in texts)


def test_NEGATIVE_a_blank_or_dead_page_is_zero_posts_from_both_readers():
    for html in ("", None, "<html>nothing</html>", "VHdlZXQ6 full_text client:"):
        assert G._parse_recent(html or "", "GnT_Trades") == []


# ───────────────────────────────────────────────── the verdict, stored + served
class _Coll:
    """A one-collection Mongo stand-in: find_one / replace_one / find-sort-limit."""

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


def _run(ok: bool, at: str, top: int = 101) -> dict:
    return {"trader": "gnt", "handle": "GnT_Trades", "stored": top + (5 if ok else 0),
            "ok": ok, "sources": {"recent": 5 if ok else 0, "top": top},
            "errors": [] if ok else [G.RECENT_DARK_ERROR],
            "recent_shape": "relay" if ok else None, "fetched_at": at}


def test_a_dark_run_keeps_the_date_the_source_last_answered():
    st = _Coll()
    G.store_status(_run(True, "2026-09-24T21:40:02+00:00"), status_coll=st)
    G.store_status(_run(False, "2026-10-22T12:31:00+00:00"), status_coll=st)
    doc = G.read_status("gnt", st)
    assert doc["ok"] is False
    assert doc["at"] == "2026-10-22T12:31:00+00:00"
    assert doc["last_ok_at"] == "2026-09-24T21:40:02+00:00"
    assert doc["sources"] == {"recent": 0, "top": 101}


def test_the_board_serves_the_dark_verdict_as_one_sentence_with_both_dates():
    st = _Coll()
    G.store_status(_run(True, "2026-09-24T21:40:02+00:00"), status_coll=st)
    G.store_status(_run(False, "2026-10-22T12:31:00+00:00"), status_coll=st)
    b = G.board(coll=_Coll(), trader="gnt", status_coll=st)
    r = b["refresh"]
    assert r["ok"] is False
    note = r["note"]
    assert note.startswith("⚠️ NOT tracking Tito Adhikary's latest posts")
    assert "2026-10-22 08:31 ET" in note, "the dark check, in his clock"
    assert "last answered 2026-09-24 17:40 ET" in note
    assert "101 posts" in note and "history" in note


def test_an_ok_run_clears_the_warning_and_says_what_answered():
    st = _Coll()
    G.store_status(_run(False, "2026-10-22T12:31:00+00:00"), status_coll=st)
    G.store_status(_run(True, "2026-10-22T21:40:00+00:00"), status_coll=st)
    b = G.board(coll=_Coll(), trader="gnt", status_coll=st)
    r = b["refresh"]
    assert r["ok"] is True and r["last_ok_at"] == "2026-10-22T21:40:00+00:00"
    assert "⚠️" not in r["note"]
    assert "2026-10-22 17:40 ET" in r["note"]
    assert "5 posts" in r["note"] and "101" in r["note"]


def test_NEGATIVE_no_status_doc_yet_is_said_so_never_a_typed_checked_claim():
    b = G.board(coll=_Coll(), trader="gnt", status_coll=_Coll())
    r = b["refresh"]
    assert r["ok"] is None and r["at"] is None
    assert "No refresh recorded yet" in r["note"]
    assert set(r) == {"at", "ok", "last_ok_at", "stored", "sources", "errors",
                      "recent_shape", "note"}


def test_NEGATIVE_both_sources_dead_is_said_as_the_archive_not_as_history():
    st = _Coll()
    G.store_status(_run(False, "2026-10-22T12:31:00+00:00", top=0), status_coll=st)
    note = G.board(coll=_Coll(), trader="gnt", status_coll=st)["refresh"]["note"]
    assert "returned nothing either" in note
    assert "last answered never" in note


def test_refresh_writes_the_verdict_beside_the_posts(monkeypatch):
    posts, st = _Coll(), _Coll()
    monkeypatch.setattr(G, "_get", lambda url: SYND_ONE if "syndication" in url else GNT_PAGE)
    r = G.refresh(coll=posts, trader="gnt", status_coll=st)
    assert r["ok"] is True and r["stored"] == 6 and r["recent_shape"] == "relay"
    assert st.docs["gnt"]["ok"] is True and st.docs["gnt"]["sources"]["recent"] == 5
    # and a dark run right after keeps that date
    monkeypatch.setattr(G, "_get", lambda url: SYND_ONE if "syndication" in url else "<html/>")
    r2 = G.refresh(coll=posts, trader="gnt", status_coll=st)
    assert r2["ok"] is False and r2["stored"] == 1
    assert st.docs["gnt"]["last_ok_at"] == r["fetched_at"]


def test_NEGATIVE_the_board_still_never_fetches():
    src = inspect.getsource(G.board)
    assert "fetch(" not in src
    assert "read_status(" in src, "the verdict is READ from the store, not refreshed"


# ───────────────────────────────────────────────── the cron's exit code
def _all(**per):
    return {"ok": all(r.get("ok") for r in per.values()), "traders": per}


def test_exit_0_when_every_latest_posts_source_answered():
    assert G.exit_code(_all(gnt={"ok": True, "stored": 106}, martinluk={"ok": True, "stored": 101})) == 0


def test_exit_1_is_PARTIAL_history_stored_but_a_latest_source_dark():
    """The 2026-09-25 → 10-22 case: 101 posts stored every run, recent dark."""
    a = _all(gnt={"ok": False, "stored": 101}, martinluk={"ok": False, "stored": 101})
    assert G.exit_code(a) == 1
    assert G.verdict_word(a["traders"]["gnt"]) == "PARTIAL"


def test_exit_2_when_an_account_stored_nothing_at_all():
    a = _all(gnt={"ok": True, "stored": 106}, martinluk={"ok": False, "stored": 0})
    assert G.exit_code(a) == 2
    assert G.verdict_word(a["traders"]["martinluk"]) == "NOTHING STORED"


def test_NEGATIVE_a_dark_source_never_exits_0():
    assert G.exit_code(_all(gnt={"ok": False, "stored": 101})) != 0


def test_the_crontab_line_is_unchanged_and_its_comment_knows_the_codes():
    """The host crontab is mounted, not shipped: the COMMAND must not change."""
    cron = (Path(__file__).parent.parent / "crontab").read_text()
    assert "40     7,17  *    *    *    /usr/local/bin/python -m traders.feed refresh" in cron
    assert "rc=1" in cron and "rc=2" in cron and "refresh.note" in cron
