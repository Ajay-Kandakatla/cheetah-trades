"""📌 The trader feed — reading a public X account into tickers + evidence.

Ajay 2026-09-12: *"Can you create a new tab on chartmaps tracking this person..
https://x.com/GnT_Trades ... He had humongous growth of stocks"* and
*"do this daily twice. and create a tab for me. I wanna track his stocks for
investing"*.

WHO HE IS, verified off his own profile on 2026-09-12 and not from memory:
bio reads "Investor/Trader | Sharing reflections and ideas | USIC 2025 #1,
2115%"; the pinned post (2026-01-29) says he won the $20k+ Enhanced Growth
Division with a 2,115% return in 2025, quoting @USICOfficial: "Congratulation
to Tito Adhikary, a Harvard cancer researcher, for setting a new world record
in the enhanced growth division, + 2115.1%!". 33.9K followers, 6,568 posts.

═══════════════════════════════════════════════════════════════════════════
THE THING TO UNDERSTAND BEFORE READING THIS BOARD
═══════════════════════════════════════════════════════════════════════════
**He does not post a portfolio.** Reading his actual posts, two completely
different kinds of ticker mention show up, and conflating them would invert
him:

  1. FORWARD IDEAS — "$SPCX reclaiming 150 into the close. Definitely on watch
     next week", "$BBY has a nice look", "$SMCI don't love the stock but can't
     ignore the chart going into next week". These are what Ajay asked for.

  2. RESULT RECAPS of CLOSED trades, many of them SHORT — "Great day on $QQQ
     **puts**, +$12K", "$NFLX turned out to be a *great* trade **with puts**",
     "Best trades **were** on $NVDA $RKLB $GS $NFLX $META". Past tense. Several
     are from 2022 and one names $BBBY, which is bankrupt.

A naive cashtag scraper produces a "his stocks" list containing bankrupt names,
index tickers and BEARISH put trades read as longs. So this module NEVER emits
a bare ticker: every row carries the post that produced it, its age, and the
words that decide how to read it.

**AND IT NEVER ASSERTS A DIRECTION PER TICKER.** One of his own posts is
"caught the upside on $FSLR and downside on $META $TSLA" — one post, two
directions, split across tickers. Post-level sentiment is provably wrong there,
so this module reports the WORDS IT FOUND (`flags`) and lets his sentence
speak. Guessing long/short from keywords would be an invention.

═══════════════════════════════════════════════════════════════════════════
WHERE THE DATA COMES FROM — two sources, because neither is enough
═══════════════════════════════════════════════════════════════════════════
  RECENT  https://x.com/<handle>          — his latest ~6 posts, CHRONOLOGICAL.
          This is the one that carries live ideas. The timeline rides in an
          undocumented React-stream blob (`client:VHdlZXQ6<b64id>:details ...
          full_text:"..."`), so it is FRAGILE BY NATURE and X can change it
          any day. It fails LOUDLY — `ok: False` on the payload and said on
          the board — rather than quietly going stale, because a tracker that
          silently stops updating is worse than one that is visibly broken.

  TOP     https://syndication.twitter.com/srv/timeline-profile/screen-name/...
          — a stable public JSON blob, ~101 posts, but ENGAGEMENT-RANKED and
          badly stale: spans 2022-05 to 2026-01 and does NOT contain his post
          from yesterday. Useful as history and as a fallback, useless as a
          daily feed. Measured, not assumed: favourite counts descend
          monotonically through it.

Neither needs an API key or a login. Both are read-only fetches of a public
profile.

STORAGE is cumulative and idempotent: `_id` is the tweet's own id, so running
twice a day (or ten times) upserts the same posts instead of inventing
duplicates, and the history deepens past what either endpoint returns today.

NOTHING HERE IS A SIGNAL, A GATE OR A LANE. It reads one public account. No
scan consumes it, no alert fires from it, nothing buys from it. A championship
return is also not a transferable track record: the USIC enhanced-growth
divisions permit concentration and leverage that the rules in this app's own
trading engine forbid, and his posts describe options day-trades, not the
position sizing anything here is built on.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("traders.gnt")

# Kept as the module default so every existing caller and test keeps working;
# `registry.py` is what actually says WHO is tracked.
DEFAULT_HANDLE = "GnT_Trades"
HANDLE = DEFAULT_HANDLE
DISPLAY = "Tito Adhikary"
PROFILE_URL = f"https://x.com/{HANDLE}"


def recent_url(handle: str) -> str:
    return f"https://x.com/{handle}"


def top_url(handle: str) -> str:
    return ("https://syndication.twitter.com/srv/timeline-profile/screen-name/"
            f"{handle}")

# His claim, quoted from the @USICOfficial post he pinned. Stored as a CITED
# fact with its source, not as a number this app measured.
USIC_2025 = {
    "year": 2025,
    "division": "$20,000+ Enhanced Growth",
    "return_pct": 2115.1,
    "rank": 1,
    "source": "@USICOfficial, quoted in his pinned post 2026-01-29",
    "note": ("A contest return, self-selected and unaudited by this app. The "
             "enhanced-growth divisions permit concentration and leverage that "
             "this app's own risk rules forbid."),
}

RECENT_URL = recent_url(HANDLE)
TOP_URL = top_url(HANDLE)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")
TIMEOUT_SEC = 25
COLL = "gnt_posts"
KEEP_POSTS = 2000

# Twitter's snowflake epoch. The tweet id encodes its own creation time, which
# is how a post gets an exact timestamp out of a stream that carries no
# `created_at` field at all.
SNOWFLAKE_EPOCH_MS = 1288834974657

# A post older than this is history, not an idea. His live posts are hours old;
# most of the syndication cashtags are from 2022.
FRESH_DAYS = 14

# $AAPL yes. Cashtags are upper-case 1-6 letters with an optional dot/dash.
CASHTAG_RE = re.compile(r"\$([A-Z][A-Z.\-]{0,5})\b")

# Index and volatility tickers are not "stocks he likes" — they are how he
# describes the TAPE ("Harder week with $SPY $QQQ weak"). Kept on the post,
# excluded from the ticker roster.
MARKET_TICKERS = frozenset({"SPY", "QQQ", "SPX", "NDX", "IWM", "DIA", "VIX",
                            "VXX", "UVXY", "ES", "NQ", "RUT", "DJI"})

# The words that change how a mention reads. Reported as FOUND, never resolved
# into a direction — "caught the upside on $FSLR and downside on $META $TSLA"
# is one post carrying both.
FLAG_WORDS = {
    "puts": ("put", "puts"),
    "calls": ("call", "calls"),
    "short": ("short", "downside", "breakdown", "shorted"),
    "long": ("breakout", "broke out", "upside", "reclaim", "long"),
    "watch": ("on watch", "watching", "nice look", "like the look",
              "can't ignore", "eyeing"),
    "recap": ("great day", "solid day", "strong day", "best trades",
              "personal best", "traded", "+$", "caught"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _db():
    try:
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        return c.get_database(os.environ.get("MONGO_DB", "cheetah"))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.gnt: no mongo: %s", exc)
        return None


def snowflake_iso(tweet_id: str) -> Optional[str]:
    """The post's creation time, decoded from its own id.

    Neither source ships a usable `created_at` on the recent stream, and a
    tracker with no timestamps cannot tell a live idea from a 2022 recap —
    which is the single most important distinction on this board."""
    try:
        ms = (int(tweet_id) >> 22) + SNOWFLAKE_EPOCH_MS
    except (TypeError, ValueError):
        return None
    # STRICTLY greater: any id under 2**22 shifts to zero and lands exactly on
    # the epoch, so "12" would decode to a real-looking 2010-11-04 timestamp.
    # A wrong date is worse than none here — it decides `fresh`.
    if ms <= SNOWFLAKE_EPOCH_MS or ms > 4102444800000:         # sanity: 2010..2100
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def cashtags(text: str) -> list[str]:
    """Tickers in the post, de-duplicated, ORDER PRESERVED — the first ticker
    in a sentence is usually the one it is about."""
    out: list[str] = []
    for t in CASHTAG_RE.findall(text or ""):
        t = t.upper().rstrip(".-")
        if t and t not in out:
            out.append(t)
    return out


def flags(text: str) -> list[str]:
    """Which reading-words the post contains. FOUND, not interpreted."""
    low = (text or "").lower()
    return [k for k, words in FLAG_WORDS.items() if any(w in low for w in words)]


def _clean(s: str) -> str:
    return " ".join((s or "").split())


def _parse_recent(html: str) -> list[dict]:
    """His latest posts out of the x.com React stream.

    The id rides in the object KEY immediately before the text
    (`client:VHdlZXQ6<base64 "Tweet:<id>">:details ... full_text:"..."`), which
    is the only thing tying a body to a timestamp here. Undocumented and
    fragile on purpose — see the module docstring; the caller reports failure
    rather than hiding it."""
    pat = re.compile(
        r'client:(VHdlZXQ6[A-Za-z0-9+/=]+):details.{0,2000}?full_text:"((?:[^"\\]|\\.)*)"',
        re.S)
    out, seen = [], set()
    for m in pat.finditer(html or ""):
        try:
            gid = base64.b64decode(m.group(1)).decode("utf-8", "ignore")
            tid = gid.split(":", 1)[1] if ":" in gid else ""
            if not tid.isdigit() or tid in seen:
                continue
            text = _clean(json.loads('"' + m.group(2) + '"'))
        except Exception:                                      # noqa: BLE001,S112
            continue
        seen.add(tid)
        out.append({"id": tid, "text": text, "source": "recent"})
    return out


def _parse_top(html: str) -> list[dict]:
    """The syndication blob. Stable, but engagement-ranked and stale."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        entries = data["props"]["pageProps"]["timeline"]["entries"]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.gnt: syndication shape changed: %s", exc)
        return []
    out = []
    for e in entries:
        t = (e.get("content") or {}).get("tweet") or {}
        tid = str(t.get("id_str") or t.get("id") or "")
        if not tid.isdigit():
            continue
        out.append({"id": tid,
                    "text": _clean(t.get("full_text") or t.get("text") or ""),
                    "favorites": t.get("favorite_count"),
                    "created_at_raw": t.get("created_at"),
                    "source": "top"})
    return out


def _get(url: str) -> Optional[str]:
    try:
        import httpx
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT_SEC,
                      follow_redirects=True)
        return r.text if r.status_code == 200 else None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.gnt: fetch failed %s: %s", url, exc)
        return None


def fetch(recent_url: str = RECENT_URL, top_url: str = TOP_URL,
          getter=None) -> dict:
    """Both sources, merged. Never raises.

    Returns {"posts", "ok", "sources", "errors"}. `ok` is False the moment the
    RECENT source yields nothing — the stale source alone would keep the board
    looking alive while it stopped tracking him, and that is the failure this
    board must never hide."""
    g = getter or _get
    errors, sources = [], {}
    by_id: dict[str, dict] = {}

    raw_recent = g(recent_url)
    fresh = _parse_recent(raw_recent or "")
    sources["recent"] = len(fresh)
    if not fresh:
        errors.append("the recent-post source returned nothing — X may have "
                      "changed its page shape; this board is NOT tracking his "
                      "latest posts right now")

    raw_top = g(top_url)
    top = _parse_top(raw_top or "")
    sources["top"] = len(top)
    if not top:
        errors.append("the syndication source returned nothing")

    # Recent wins on a collision: same id, but the recent parse is the one
    # whose freshness we rely on.
    for p in top + fresh:
        prev = by_id.get(p["id"]) or {}
        by_id[p["id"]] = {**prev, **p}

    posts = []
    for p in by_id.values():
        iso = snowflake_iso(p["id"])
        text = p.get("text") or ""
        posts.append({**p, "created_at": iso, "url": f"{PROFILE_URL}/status/{p['id']}",
                      "cashtags": cashtags(text), "flags": flags(text)})
    posts.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return {"posts": posts, "ok": bool(fresh), "sources": sources,
            "errors": errors, "fetched_at": _now().isoformat()}


# ═══════════════════════════════════════════════════════════════════════════
# STORAGE — cumulative, so the history outgrows what either endpoint returns
# ═══════════════════════════════════════════════════════════════════════════
def store(payload: dict, coll=None, trader: str = "gnt") -> int:
    """Upsert every post. `_id` is the tweet's own id, so running twice a day
    deepens the archive instead of duplicating it. Returns posts written."""
    posts = (payload or {}).get("posts") or []
    if coll is None:
        db = _db()
        if db is None:
            return 0
        coll = db[COLL]
    n = 0
    for p in posts:
        try:
            coll.update_one({"_id": p["id"]},
                            {"$set": {**p, "_id": p["id"], "trader": trader},
                             "$setOnInsert": {"first_seen": _now().isoformat()}},
                            upsert=True)
            n += 1
        except Exception as exc:                               # noqa: BLE001
            log.warning("traders.gnt: store failed for %s: %s", p.get("id"), exc)
    return n


def stored(limit: int = 400, coll=None, trader: Optional[str] = None) -> list[dict]:
    """Everything we have ever seen them post, newest first.

    `trader=None` returns EVERY tracked account's posts — used by the curator,
    which does not care who said a name. A board always passes its own key: two
    feeds in one table would attribute one trader's idea to the other."""
    if coll is None:
        db = _db()
        if db is None:
            return []
        coll = db[COLL]
    q = {} if trader is None else {"trader": trader}
    try:
        return list(coll.find(q).sort("created_at", -1).limit(int(limit)))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.gnt: read failed: %s", exc)
        return []


def age_days(iso: Optional[str], now: Optional[datetime] = None) -> Optional[int]:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max(0, int(((now or _now()) - t).total_seconds() // 86400))


def tickers(posts: list[dict], now: Optional[datetime] = None) -> list[dict]:
    """His posts collapsed to one row PER TICKER, each carrying its evidence.

    Index and volatility symbols are dropped from the roster — "Harder week
    with $SPY $QQQ weak" is him describing the tape, not naming a stock he
    likes — but they stay visible on the post itself.

    Every row keeps the FULL post text of its most recent mention. That is the
    whole design: a ticker with no sentence beside it is how "$QQQ puts, +$12K"
    becomes a long idea, and how a 2022 mention of a bankrupt name reads as
    current.
    """
    rows: dict[str, dict] = {}
    for p in posts:
        for sym in p.get("cashtags") or []:
            if sym in MARKET_TICKERS:
                continue
            r = rows.setdefault(sym, {"symbol": sym, "mentions": 0, "posts": [],
                                      "flags": set()})
            r["mentions"] += 1
            r["flags"].update(p.get("flags") or [])
            r["posts"].append({"id": p.get("id"), "text": p.get("text"),
                               "created_at": p.get("created_at"),
                               "url": p.get("url"), "flags": p.get("flags") or []})
    out = []
    for sym, r in rows.items():
        r["posts"].sort(key=lambda x: x.get("created_at") or "", reverse=True)
        newest = r["posts"][0]
        age = age_days(newest.get("created_at"), now)
        out.append({
            "symbol": sym,
            "mentions": r["mentions"],
            "flags": sorted(r["flags"]),
            "last_post": newest,
            "posts": r["posts"][:5],
            "age_days": age,
            # Fresh is about whether this is an IDEA or history. Unknown age is
            # not fresh — it is unknown, and must not read as current.
            "fresh": (age is not None and age <= FRESH_DAYS),
        })
    # Newest mention first. This is a feed, not a leaderboard: how MANY times he
    # said a name is not how recently he said it, and stale-but-repeated is
    # exactly the 2022 $BBBY shape that must not float to the top.
    out.sort(key=lambda r: ((r["last_post"].get("created_at") or ""),), reverse=True)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# THE OVERLAY — his names against OUR read, which is the point of a tab here
# ═══════════════════════════════════════════════════════════════════════════
def _universe() -> set:
    """The `full` universe — what the hourly scan, the zone store and every
    board actually run on. A name he likes that is NOT in here is invisible to
    this entire app however good his call was, which is the AXTI case all over
    again and worth saying on the row."""
    try:
        from sepa.universe import load_universe
        return {str(s).upper() for s in (load_universe("full") or [])}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.gnt: universe unavailable: %s", exc)
        return set()


def _growth_tags() -> dict:
    try:
        from growth import tracker as GT
        return {r["symbol"]: r for r in ((GT.board() or {}).get("rows") or [])
                if r.get("symbol")}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.gnt: growth board unavailable: %s", exc)
        return {}


def overlay(rows: list[dict]) -> list[dict]:
    """Attach this app's own read to each of his tickers.

    Reuses `growth.tracker._zone_read` rather than re-deriving a demand state:
    two definitions of "at demand" on two boards is how they start disagreeing.
    Every attachment is fenced — his post must still render when our side of
    the read is unavailable.
    """
    uni = _universe()
    growth = _growth_tags()
    try:
        from growth.tracker import _zone_read
    except Exception:                                          # noqa: BLE001
        _zone_read = None                                      # type: ignore

    out = []
    for r in rows:
        sym = r["symbol"]
        covered = (not uni) or (sym in uni)
        row = {**r,
               # `None` when we could not load a universe at all — unknown, not
               # a claim that the name is uncovered.
               "covered": (None if not uni else sym in uni),
               "growth": None, "zone": None}
        g = growth.get(sym)
        if g:
            row["growth"] = {"sales": g.get("sales_growth_pct"),
                             "eps": g.get("q_eps_growth_pct"),
                             "refused": any(str(w).startswith("⛔")
                                            for w in (g.get("warnings") or []))}
        if _zone_read is not None and covered:
            try:
                z = _zone_read(sym)
                row["zone"] = {"missing": z.get("missing"),
                               "in_band": z.get("in_band"),
                               "intact": z.get("intact")}
            except Exception as exc:                           # noqa: BLE001
                log.debug("traders.gnt: zone read failed for %s: %s", sym, exc)
        out.append(row)
    return out


def board(limit: int = 400, coll=None, trader: str = "gnt") -> dict:
    """Everything the tab renders. Reads STORED posts; it never fetches.

    Same rule as every other board here: a page load must not depend on a third
    party answering. The twice-daily cron owns the fetching."""
    from traders import registry as R
    who = R.get(trader) or R.get(R.DEFAULT_KEY) or {}
    posts = stored(limit=limit, coll=coll, trader=who.get("key", trader))
    rows = overlay(tickers(posts))
    fresh = [r for r in rows if r["fresh"]]
    newest = next((p.get("created_at") for p in posts if p.get("created_at")), None)
    handle = who.get("handle") or HANDLE
    return {
        "key": who.get("key"), "handle": handle, "display": who.get("display") or DISPLAY,
        "profile_url": recent_url(handle),
        "usic": who.get("usic") or USIC_2025, "style": who.get("style"),
        "n_posts": len(posts), "n_tickers": len(rows), "n_fresh": len(fresh),
        "fresh_days": FRESH_DAYS,
        "newest_post_at": newest,
        "newest_age_days": age_days(newest),
        "tickers": rows,
        "market_tickers": sorted(MARKET_TICKERS),
        "disclaimer": R.DISCLAIMER,
    }


def refresh(coll=None, trader: str = "gnt") -> dict:
    """Fetch → store, for ONE trader. What the cron calls, twice a day."""
    from traders import registry as R
    who = R.get(trader) or {}
    handle = who.get("handle") or HANDLE
    f = fetch(recent_url=recent_url(handle), top_url=top_url(handle))
    n = store(f, coll=coll, trader=who.get("key", trader))
    log.info("traders.feed[%s]: stored %s posts (ok=%s sources=%s)",
             handle, n, f["ok"], f["sources"])
    return {"trader": who.get("key", trader), "handle": handle, "stored": n,
            "ok": f["ok"], "sources": f["sources"], "errors": f["errors"],
            "fetched_at": f["fetched_at"]}


def refresh_all(coll=None) -> dict:
    """Every tracked account. One failing account must not stop the others."""
    from traders import registry as R
    out, ok = {}, True
    for t in R.TRADERS:
        try:
            r = refresh(coll=coll, trader=t["key"])
        except Exception as exc:                               # noqa: BLE001
            log.warning("traders.feed: %s failed: %s", t["key"], exc)
            r = {"trader": t["key"], "ok": False, "stored": 0,
                 "errors": [f"{type(exc).__name__}: {exc}"[:160]]}
        out[t["key"]] = r
        ok = ok and bool(r.get("ok"))
    return {"ok": ok, "traders": out}


if __name__ == "__main__":                                     # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "refresh"
    if cmd == "refresh":
        all_ = refresh_all()
        for key, r in all_["traders"].items():
            print(f"{key}: stored {r.get('stored')} posts, ok={r.get('ok')}, "
                  f"sources={r.get('sources')}")
            for e in r.get("errors") or []:
                print(f"  ⚠️  {e}")
        raise SystemExit(0 if all_["ok"] else 1)
    if cmd == "show":
        b = board(trader=(sys.argv[2] if len(sys.argv) > 2 else "gnt"))
        print(f"{b['display']} (@{b['handle']}) — {b['n_posts']} posts, "
              f"{b['n_tickers']} tickers, {b['n_fresh']} fresh")
        for r in b["tickers"][:20]:
            print(f"  {r['symbol']:<6} {str(r['age_days']):>4}d covered={r['covered']} "
                  f"{r['flags']}")
        raise SystemExit(0)
    print(__doc__)
    raise SystemExit(2)
