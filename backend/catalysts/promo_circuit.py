"""Promo-circuit watch — track the accounts that seed tiny-float movers.

Born 2026-09-01 from the chatter-provenance hunt: for 11 movers on the
predictions board we traced WHO called each move in advance, with exact
StockTwits timestamps and EDGAR acceptance times. The answer, for most of
them, was "the promoters themselves": named alert accounts tag a low-float
ticker days before it goes vertical, then victory-lap when their own crowd
moves it. The tag IS the promotion — so a fresh tag from these accounts is
(a) an early-warning watchlist entry ("this is being seeded NOW"), and
(b) a NEGATIVE conviction signal (exit-liquidity risk), never a buy signal.

Measured basis for the roster (all timestamps in the study notes):
  - @ShangVXO touted "$PETZ" (8/19) and "$FLYE" (8/20) via "_ProfessorGamma";
    both went vertical the SAME Monday 8/31 on near-silent public tapes.
  - @topstockalerts ran the NWGL alert loop from 8/19 into a 98.4M-share
    resale shelf; a bagholder described the mechanism in real time on 8/20.
  - @beppels watchlisted RDAC 8/21 + 8/25, then re-flagged it premarket the
    day it ran +44%.
  - @StockSenseiTrendTraders sold Zoom access off SWVL's run all weekend.

Two EDGAR tells ride along for every watched ticker:
  - owner-stake filings (SC 13D/G) — the ONE genuinely predictive public
    signal in the study (GPRO: Markiplier's 13G landed 6 sessions early);
  - fresh shelf/offering plumbing (S-1/S-3/F-1/F-3/424B/FWP) — the
    short-side tell (NWGL resale, SSM 19.9% direct, LIDR ATM).

Data: StockTwits public user streams (no auth; same API family the chatter
module already uses), Massive daily aggs for price-since-tag, EDGAR
submissions JSON via evidence.py helpers. Sweep runs from cron; the board
endpoint reads Mongo and never fetches StockTwits inline.

NOT book logic — no Minervini scope here (uncited market-structure
convention, catalysts family).
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import requests

log = logging.getLogger("catalysts.promo_circuit")

# StockTwits sits behind Cloudflare bot protection that 403s the `requests`
# client fingerprint (measured 2026-09-01: requests=403 "Just a moment",
# httpx with a browser UA=200). Use httpx + browser UA for StockTwits ONLY;
# Massive/SEC keep requests (they don't block it).
_ST_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/128.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

_CACHE_TTL_SEC = 10 * 60          # board cache
TAG_WINDOW_DAYS = 14              # board shows tags from the last 14 days
PENALTY_WINDOW_DAYS = 7           # predictions penalty only for fresh tags
SEEDING_MAX_DAYS = 7              # tag older than this without a run = QUIET
RAN_MIN_GAIN_PCT = 30.0           # max gain since tag that counts as "it ran"
DUMPED_DROP_PCT = -40.0           # give-back from post-tag peak = DUMPED
RETAG_RESET_DAYS = 14             # dormant this long -> new campaign, reset first_tagged_at
SHOTGUN_DISTINCT_TAGS = 25        # account tagging more tickers than this in the
                                  # window is a watchlist machine: its one-off
                                  # mentions are noise, repeats are campaigns
EDGAR_ROW_CAP = 80
MAX_POSTS_KEPT = 40           # posts kept per account x ticker for the tag tape                # EDGAR lookups only for the rows that matter

# ---------------------------------------------------------------------------
# The roster. USER-EDITABLE — same pattern as frontend/src/lib/fundTiers.ts:
# when Ajay says "add account X to the promo circuit", add one entry here
# with tier + a dated evidence line, and deploy api+cron. Tiers:
#   S  documented pump-circuit tell — their tags preceded verticals on
#      SILENT public tapes (private-group signature). Strongest negative.
#   A  alert-room promoters — sell access / run victory-lap loops; their
#      crowd IS the move. Strong negative.
#   B  momentum-watchlist reposters — context only; tags shown on the board
#      but never penalize the predictions score.
# ---------------------------------------------------------------------------
PROMO_ACCOUNTS: dict[str, dict] = {
    "ShangVXO": {
        "tier": "S",
        "note": "'_ProfessorGamma' tout template; resurrected account",
        "evidence": ("PETZ 8/19 + FLYE 8/20 touts -> both vertical Tue 9/1 on "
                     "silent tapes. Dormant Feb 2014, reborn 2026-08-06 as an "
                     "SPCX/'_ProfessorGamma' vehicle; staged VMAR with "
                     "@topstockalerts (his 8/18 tout, TSA's 8/26 victory lap)"),
        "audit": ("Aug-2026: 870 tags in 27d, 28% not even priceable "
                  "securities (filler camouflage); real touts 16.5% hit +20% "
                  "in 5 sessions but 25.7% in 10 — median peak session 4, "
                  "HALF the hits after session 5, median tout −6.1% by "
                  "session 10"),
        # His pumps land ~10 SESSIONS after the tag (PETZ session 9, FLYE
        # session 8) — the default 7-day penalty window would expire before
        # the move. Measured 2026-09-02.
        "penalty_days": 14,
    },
    "topstockalerts": {
        "tier": "A",
        "note": "alert loop, reposts own wins 5-6x",
        "evidence": ("NWGL 'ALERTED @ $0.25' loop from 8/19 into the resale "
                     "shelf; BTCT 'alerted @ $0.54' admitted to be a July-29 "
                     "call, rebranded same-day with a live claim ladder "
                     "27%->296%; staged VMAR with @ShangVXO; posted literal "
                     "'strong pump ahead' (LESL 8/17, GNS 8/19)"),
        "audit": ("Aug-2026: 1,134 tags in 27d, tagged mid-run (+6% median "
                  "tag-day move); 25% hit +20% from the close but 19% from "
                  "the next open (the gap eats the edge) — median red at "
                  "every entry; even his self-selected alert-brags are "
                  "−6.4% ten sessions after the public post"),
    },
    "beppels": {
        "tier": "A",
        "note": "low-float SPAC watchlists + day-of premarket flags",
        "evidence": "RDAC watchlists 8/21 + 8/25, re-flag 5:22am ET 9/1 before +44%",
        "audit": ("Aug-2026: 47 tags, 24% ever hit +20%, median peak +7.6%, "
                  "median day-5 close −3.2% — genuinely premarket-early, "
                  "still loses at the median"),
    },
    "StockSenseiTrendTraders": {
        "tier": "A",
        "note": "sells Zoom-room access off runs",
        "evidence": "SWVL 'covered on the Zoom before it moved' 8/28 while selling access",
        "audit": ("Aug-2026: 47 tags, median day-5 −19.6% — after-close "
                  "victory-laps of already-run names; a WETO follower's "
                  "next-open entry was the exact top print"),
    },
    "ItTakesItAll": {
        "tier": "A",
        "note": "running %-scoreboard promotion",
        "evidence": "NWGL scoreboards 8/21 '70%+' / 8/26 '205%+' during the resale run-up",
        "audit": ("Aug-2026: 31 tags, 19% follower hit rate (worst of the "
                  "A-tier), median day-5 −6.1%; overnight gaps eat the "
                  "'adding' posts"),
    },
    # RENAMED from @PennyStocksMom (same display name, user id 1302364) —
    # the old handle 404s on the API. Found in the 2026-09-01 audit.
    "PSM_EmpowerTrading": {
        "tier": "B",
        "note": "watchlist reposter (ex-@PennyStocksMom)",
        "evidence": "RDAC 8/21 watchlists; PETZ evening-of 8/31 (after the AH gap)",
        "audit": ("Aug-2026: 160-ticker shotgun, 24% ever hit +20%, median "
                  "pick day-5 −9.5% — survives by victory-lapping the "
                  "survivors"),
    },
    "TeamBullish": {"tier": "B", "note": "momentum tagger",
                    "evidence": "SWVL 'solid data point for Monday' Fri 8/28"},
    "Xen_TorpedoCapital": {"tier": "B", "note": "model-bullish posts on promo names",
                           "evidence": "NWGL 8/21 during the alert loop"},
    "stockusfrance": {"tier": "B", "note": "premarket price-target tags",
                      "evidence": "'$SWVL 4 today' 5:03am ET Mon 8/31",
                      "audit": ("Aug-2026: 0/5 tags ever hit +20%, median "
                                "day-5 −29% — bag-holder noise, kept for "
                                "context only")},
    "Swagger_Ape": {"tier": "B", "note": "promo tagger",
                    "evidence": "SWVL promo tag premarket Mon 8/31"},
    "XkaliburTrading": {"tier": "B", "note": "evening watchlists",
                        "evidence": "PETZ evening 8/31 after the AH gap"},
    "AlertsAndNews": {"tier": "B", "note": "evening watchlists",
                      "evidence": "PETZ evening 8/31 after the AH gap"},
    "BonddBon": {"tier": "B", "note": "squeeze-priming posts",
                 "evidence": "OLOX 'news imminent... best low float squeeze' 8/27, mid-dump",
                 "audit": ("Aug-2026: 11 tags, posted mid-spike; follower "
                           "next-open entry medians −13% by day 5")},
    # ── Early callers — added 2026-09-02 from the winner-provenance study
    # (22 names that ran ≥ +2% on 9/2; who tagged them BEFORE the move) and a
    # backtest of every Aug-2026 tag (entry = first close on/after the tag,
    # hit = +30% touch within 15 sessions, dump = close ≤ 60% of the peak).
    # Radar only (tier B): no conviction penalty, never a phone alert. A
    # higher +30% touch rate meant MORE volatile picks, not an edge for a
    # follower — every one of them medians red by day 5.
    "theblueflames": {"tier": "B", "note": "early caller — evening watchlists",
                      "evidence": ("10 of the 9/2 winners tagged before the move: BIAF 3h "
                                   "early 9/1, SWVL/GYGY/NCPL the evening before"),
                      "audit": ("Sep-2026 backtest: 87 priced Aug tags, 29% touched +30% in 15 "
                                "sessions, 64% of hits dumped ≥40% off the peak, day-5 median "
                                "−5.5% — best follower math of the callers, still negative")},
    "stock_catcher": {"tier": "B", "note": "early caller — reacts to the tape",
                      "evidence": ("8 winners, minutes early (VIOT 2m, LHAI 5m, NCPL 2m) — "
                                   "sees the print, not the plan"),
                      "audit": ("Sep-2026 backtest: 10 priced Aug tags (n too small), 50% "
                                "touched +30%, 60% of hits dumped; no day-5 read")},
    "blakecapital26": {"tier": "B", "note": "early caller — late-night lists",
                       "evidence": "6 winners ~1h early (BIAF, SGLD, VIVK at 11pm 9/1)",
                       "audit": ("Sep-2026 backtest: 43 priced Aug tags, 49% touched +30%, "
                                 "81% of hits dumped ≥40%, day-5 median −13.7%")},
    "jmjtrading": {"tier": "B", "note": "early caller",
                   "evidence": "4 winners 5–23h early (BIAF, NCPL, PMI, FLYE)",
                   "audit": ("Sep-2026 backtest: 86 priced Aug tags, 37% touched +30%, "
                             "75% of hits dumped ≥40%, day-5 median −14.3%")},
    "birdseyetrader": {"tier": "B", "note": "early caller",
                       "evidence": "4 winners (BIAF 10h, VIVK 4.5h, SGLD 25m early)",
                       "audit": ("Sep-2026 backtest: 107 priced Aug tags, 40% touched +30%, "
                                 "70% of hits dumped ≥40%, day-5 median −15.6%")},
    "davidscott": {"tier": "B", "note": "early caller — big following",
                   "evidence": "3 winners (BIAF 5h, NCPL 22h, FLYE 16h early)",
                   "audit": ("Sep-2026 backtest: 37 priced Aug tags, 46% touched +30%, "
                             "59% of hits dumped ≥40%; day-5 median n/a")},
    "sadyk189": {"tier": "B", "note": "early caller — multi-ticker posts",
                 "evidence": "3 winners in one 9/2 01:06 ET post (SWVL, NWGL, FLYE)",
                 "audit": ("Sep-2026 backtest: 64 priced Aug tags, 44% touched +30%, "
                           "79% of hits dumped ≥40%, day-5 median −12.9%")},
    "robbysinvestmentllc": {"tier": "B", "note": "early caller — highest hit rate, worst hold",
                            "evidence": "3 winners (BIAF 9h, VIVK 6h, FLYE 5h early)",
                            "audit": ("Sep-2026 backtest: 70 priced Aug tags, 54% touched +30% "
                                      "(highest of anyone), 82% of hits dumped ≥40%, day-5 "
                                      "median −18.8% (worst of anyone)")},
}

# Tags on these are never interesting for a tiny-float promo board.
EXCLUDE_TICKERS = {
    "SPY", "QQQ", "IWM", "DIA", "VIX", "UVXY", "SQQQ", "TQQQ",
    "BTC", "ETH", "BTC.X", "ETH.X", "DOGE.X",
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "GOOG", "META", "AMD",
}

TIER_ORDER = {"S": 0, "A": 1, "B": 2}


# --- Mongo ----------------------------------------------------------------

def _coll(name: str):
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db][name]
    except Exception as exc:
        log.warning("promo circuit mongo unavailable: %s", exc)
        return None


def _tags_coll():
    return _coll("promo_circuit_tags")


# --- StockTwits user streams ----------------------------------------------

def _fetch_user_stream(handle: str, limit: int = 30, max_pages: int = 4,
                       oldest: Optional[datetime] = None) -> Optional[list[dict]]:
    """Public StockTwits user stream, paginated via the max= cursor until
    `oldest` is covered (None = first page only). A prolific account can
    post >30 messages across the 11.5h overnight cron gap — one page would
    silently drop the early-evening seeds (review finding 2026-09-01).

    Returns None when the FIRST page fails (vs [] = genuinely empty);
    later pages fail soft and return what we have.
    """
    url = f"https://api.stocktwits.com/api/2/streams/user/{handle}.json"
    out: list[dict] = []
    cursor: Optional[int] = None
    for _ in range(max_pages):
        params: dict = {"limit": limit}
        if cursor is not None:
            params["max"] = cursor
        try:
            r = httpx.get(url, params=params, headers=_ST_HEADERS,
                          timeout=8, follow_redirects=True)
        except Exception as exc:
            log.debug("stocktwits user fetch failed for %s: %s", handle, exc)
            return out if out else None
        if r.status_code != 200:
            if r.status_code == 429:
                log.warning("stocktwits rate limited on user %s", handle)
            elif r.status_code == 403:
                log.warning("stocktwits 403 (bot-wall) on user %s — "
                            "client fingerprint blocked again?", handle)
            return out if out else None
        msgs = (r.json() or {}).get("messages") or []
        if not msgs:
            break
        out.extend(msgs)
        if oldest is None:
            break
        tail_ts = _parse_ts(msgs[-1].get("created_at") or "")
        if tail_ts and tail_ts < oldest:
            break
        cursor = min((m.get("id") or (1 << 62)) for m in msgs) - 1
    return out


def _parse_ts(created: str) -> Optional[datetime]:
    """StockTwits created_at: '2026-09-01T12:34:56Z' (UTC)."""
    try:
        return datetime.strptime(created.split("Z")[0], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc)
    except Exception:
        return None


def extract_tags(handle: str, messages: list[dict],
                 after_msg_id: int = 0) -> dict[str, dict]:
    """Pure: one account's messages -> {ticker: tag-record}.

    Only messages with id > after_msg_id count (re-sweeps must not re-count).
    A message tagging 5 symbols yields 5 records — promo posts are lists.
    """
    out: dict[str, dict] = {}
    for m in messages or []:
        mid = m.get("id") or 0
        if mid <= after_msg_id:
            continue
        ts = _parse_ts(m.get("created_at") or "")
        if ts is None:
            continue
        body = (m.get("body") or "").strip()
        for s in (m.get("symbols") or []):
            tkr = (s.get("symbol") or "").upper().strip()
            if not tkr or tkr in EXCLUDE_TICKERS or "." in tkr:
                continue  # skip crypto-style symbols (BTC.X) and excluded
            rec = out.setdefault(tkr, {
                "first_tagged_at": ts, "last_tagged_at": ts,
                "n_messages": 0, "sample": body[:180], "max_msg_id": mid,
                "msg_ids": [], "posts": [],
            })
            rec["n_messages"] += 1
            rec["msg_ids"].append(mid)
            # Every post, not just first/last: the tag tape marks the ACTUAL
            # announcement times (Ajay 2026-09-02: TLYS was already +15% when
            # the 3:35p post landed; the 9:23p-the-night-before mention was
            # a different call).
            rec["posts"].append({"id": mid, "at": ts, "body": body[:160]})
            if ts < rec["first_tagged_at"]:
                rec["first_tagged_at"] = ts
            if ts > rec["last_tagged_at"]:
                rec["last_tagged_at"] = ts
                rec["sample"] = body[:180]
            if mid > rec["max_msg_id"]:
                rec["max_msg_id"] = mid
    return out


def sweep() -> dict:
    """Fetch every roster account's stream and upsert tag records in Mongo.

    Rate-limit friendly: ~14-20 requests per run (pagination only digs past
    page one after a long cron gap). Runs from cron; board reads never
    trigger this inline.
    """
    coll = _tags_coll()
    meta_coll = _coll("promo_circuit_meta")
    now = datetime.now(timezone.utc)

    # Paginate back past the previous sweep (overnight gap 11.5h, weekend
    # holes up to 12h) with an hour of margin; 48h floor for the first run.
    oldest = now - timedelta(hours=48)
    if meta_coll is not None:
        try:
            doc = meta_coll.find_one({"_id": "sweep"}) or {}
            prev_sweep = _as_utc(doc.get("last_sweep_at"))
            if prev_sweep:
                oldest = max(oldest, prev_sweep - timedelta(hours=1))
        except Exception as exc:
            log.warning("sweep meta read failed: %s", exc)

    ok, failed, n_new = [], [], 0
    for handle, meta in PROMO_ACCOUNTS.items():
        msgs = _fetch_user_stream(handle, oldest=oldest)
        if msgs is None:
            failed.append(handle)
            continue
        ok.append(handle)
        if coll is None:
            continue

        try:
            seen = {d["ticker"]: d for d in coll.find({"account": handle})}
        except Exception as exc:
            # MongoClient is lazy — a down Mongo surfaces HERE, not in
            # _coll(). Skip this account's writes, keep sweeping the rest.
            log.warning("tag read failed for %s: %s", handle, exc)
            failed.append(f"{handle}:mongo")
            continue

        for tkr, rec in extract_tags(handle, msgs).items():
            prev = seen.get(tkr)
            # Per-TICKER high-water mark. An account-wide mark let one
            # ticker's successful upsert bury a sibling ticker's failed
            # one forever (review finding 2026-09-01).
            prev_max = (prev or {}).get("max_msg_id") or 0
            fresh_ids = [i for i in rec["msg_ids"] if i > prev_max]
            if prev and not fresh_ids:
                continue
            first = rec["first_tagged_at"]
            n_msgs = len(fresh_ids)
            if prev:
                prev_last = _as_utc(prev.get("last_tagged_at"))
                # Dormant account re-tagging = a NEW campaign: reset the
                # clock. Within a live campaign, keep the original first
                # tag (price base) and accumulate counts.
                if prev_last and (first - prev_last) < timedelta(days=RETAG_RESET_DAYS):
                    prev_first = _as_utc(prev.get("first_tagged_at"))
                    if prev_first:
                        first = min(first, prev_first)
                    n_msgs += prev.get("n_messages") or 0
            fresh_posts = [pp for pp in rec.get("posts") or [] if pp["id"] > prev_max]
            try:
                coll.update_one(
                    {"_id": f"{handle}:{tkr}"},
                    {"$set": {
                        "account": handle, "ticker": tkr,
                        "tier": meta["tier"],  # snapshot; reads use the live roster
                        "first_tagged_at": first,
                        "last_tagged_at": max(rec["last_tagged_at"],
                                              _as_utc(prev.get("last_tagged_at")) or rec["last_tagged_at"]) if prev else rec["last_tagged_at"],
                        "n_messages": n_msgs,
                        "sample": rec["sample"],
                        "max_msg_id": max(rec["max_msg_id"], prev_max),
                        "swept_at": now,
                    },
                     # keep the last MAX_POSTS_KEPT posts per account x ticker
                     "$push": {"posts": {"$each": fresh_posts, "$slice": -MAX_POSTS_KEPT}}},
                    upsert=True,
                )
                n_new += 1
            except Exception as exc:
                log.warning("tag upsert failed %s:%s: %s", handle, tkr, exc)

    if meta_coll is not None:
        try:
            meta_coll.update_one(
                {"_id": "sweep"},
                {"$set": {"last_sweep_at": now, "accounts_ok": ok,
                          "accounts_failed": failed, "n_tag_upserts": n_new}},
                upsert=True)
        except Exception as exc:
            log.warning("sweep meta write failed: %s", exc)

    out = {"accounts_ok": len(ok), "accounts_failed": failed,
           "n_tag_upserts": n_new, "at": now.isoformat()}
    log.info("promo sweep: %s", out)
    return out


# --- Price since tag (Massive daily aggs) ---------------------------------

def _bars_since(ticker: str, since: datetime) -> Optional[list[dict]]:
    try:
        from massive_keys import stocks_key
        key = stocks_key()
    except Exception:
        key = None
    if not key:
        return None
    # Start a week BEFORE the tag so the base can be the prior session's
    # close (weekend/premarket tags must not use the run day's own close);
    # limit sized for months-long merged campaigns (60 bars silently
    # truncated to stale data — review finding 2026-09-01).
    frm = (since - timedelta(days=7)).date().isoformat()
    to = datetime.now(timezone.utc).date().isoformat()
    url = (f"https://api.massive.com/v2/aggs/ticker/{ticker.upper()}"
           f"/range/1/day/{frm}/{to}")
    try:
        r = requests.get(url, params={"adjusted": "true", "sort": "asc",
                                      "limit": 5000, "apiKey": key}, timeout=8)
        if r.status_code != 200:
            return None
        return (r.json() or {}).get("results") or None
    except Exception as exc:
        log.debug("aggs fetch failed for %s: %s", ticker, exc)
        return None


def _bar_date(b: dict):
    """Massive agg bar 't' is epoch ms (tolerate seconds)."""
    t = b.get("t")
    if not isinstance(t, (int, float)):
        return None
    if t > 1e11:
        t = t / 1000
    return datetime.fromtimestamp(t, tz=timezone.utc).date()


def price_action_since(bars: Optional[list[dict]], tag_date=None) -> dict:
    """Pure: daily bars (including ~a week BEFORE the tag) ->
    {pct_since_tag, max_gain_pct, drop_from_peak_pct, last_close}.

    Base = the last close BEFORE the first session on/after the tag. A
    weekend/premarket tag whose first bar is the run day itself must not
    measure the run against that day's own close — that made RAN/DUMPED
    unreachable for exactly the weekend-groomed movers (review finding
    2026-09-01). Falls back to the first forward bar's open, then close
    (fresh IPOs / callers passing tag_date=None with forward-only bars).
    Peak/last are computed from forward bars only.
    """
    none_shape = {"pct_since_tag": None, "max_gain_pct": None,
                  "drop_from_peak_pct": None, "last_close": None, "base_close": None}
    if not bars:
        return none_shape
    if tag_date is None:
        prior, fwd = [], list(bars)
    else:
        prior = [b for b in bars if (d := _bar_date(b)) and d < tag_date]
        fwd = [b for b in bars if (d := _bar_date(b)) and d >= tag_date]
    if not fwd:
        return none_shape
    base = prior[-1].get("c") if prior else None
    if not base:
        base = fwd[0].get("o") or fwd[0].get("c")
    last = fwd[-1].get("c")
    peak = max((b.get("h") or 0) for b in fwd)
    if not base or not last:
        return {**none_shape, "last_close": last}
    return {
        "pct_since_tag": round((last / base - 1) * 100, 1),
        "max_gain_pct": round((peak / base - 1) * 100, 1) if peak else None,
        "drop_from_peak_pct": round((last / peak - 1) * 100, 1) if peak else None,
        "last_close": last,
        "base_close": base,     # the since-tag base, so a LIVE print can be measured against it
    }


def classify_status(days_since_last_tag: Optional[float],
                    pct_since_tag: Optional[float],
                    max_gain_pct: Optional[float],
                    drop_from_peak_pct: Optional[float]) -> str:
    """Pure decision table.

    RAN     it already popped >= RAN_MIN_GAIN_PCT since the first tag (late).
    DUMPED  it ran AND gave back >= |DUMPED_DROP_PCT| from the post-tag peak
            (the circuit already exited).
    SEEDING freshly tagged (<= SEEDING_MAX_DAYS since the LATEST tag) and no
            run yet — the row that matters: promotion is loaded, move hasn't
            happened. Keyed to the latest tag, not the campaign's first: the
            circuit keeps names warm >7d before the push, and a campaign
            kept warm must not expire to QUIET the morning it fires (review
            finding 2026-09-01; beppels' RDAC re-flag was day 11).
    QUIET   no fresh tag and never ran.
    UNKNOWN no price data.
    """
    if pct_since_tag is None or max_gain_pct is None:
        return "UNKNOWN"
    if max_gain_pct >= RAN_MIN_GAIN_PCT:
        if drop_from_peak_pct is not None and drop_from_peak_pct <= DUMPED_DROP_PCT:
            return "DUMPED"
        return "RAN"
    if days_since_last_tag is not None and days_since_last_tag <= SEEDING_MAX_DAYS:
        return "SEEDING"
    return "QUIET"


# --- EDGAR tells ----------------------------------------------------------

_OWNER_FORMS = ("SC 13D", "SC 13G", "13D", "13G")
_SHELF_PREFIXES = ("S-1", "S-3", "F-1", "F-3", "424B", "FWP")


def edgar_flags_from_filings(filings: list[dict],
                             now: Optional[datetime] = None) -> dict:
    """Pure: recent-filings list (evidence._fetch_sec_filings shape) ->
    {owner_stake, shelf}. Owner window 14d; shelf window 30d. S-8 (employee
    plans) never counts as shelf."""
    now = now or datetime.now(timezone.utc)
    owner_cut = (now - timedelta(days=14)).date()
    shelf_cut = (now - timedelta(days=30)).date()
    owner, shelf = None, None
    for f in filings or []:
        form = (f.get("form") or "").upper()
        try:
            fdate = datetime.strptime(f.get("filing_date") or "", "%Y-%m-%d").date()
        except Exception:
            continue
        base = {"form": form, "filing_date": f.get("filing_date"), "url": f.get("url")}
        if owner is None and fdate >= owner_cut and any(
                form == p or form.startswith(p + "/") for p in _OWNER_FORMS):
            owner = base
        if shelf is None and fdate >= shelf_cut and not form.startswith("S-8") \
                and any(form.startswith(p) for p in _SHELF_PREFIXES):
            shelf = base
    return {"owner_stake": owner, "shelf": shelf}


def _edgar_flags(ticker: str) -> dict:
    return _edgar_bundle(ticker)["edgar"]


# ── Five tells per row (Ajay 2026-09-02: "add a new column to call out
# russell addition ... another for sales and another for catalyst and
# another for any 8k or SEC filings") ─────────────────────────────────────
_EIGHTK_WINDOW_DAYS = 14
_SEC_WINDOW_DAYS = 30
NEWS_CACHE_TTL_SEC = 30 * 60
SALES_CACHE_TTL_SEC = 7 * 24 * 3600
SALES_FETCH_CAP = 40             # new provider lookups per build
SALES_FETCH_BUDGET_SEC = 25.0


def sec_flags_from_filings(filings: list[dict], now: Optional[datetime] = None) -> dict:
    """Pure sibling of edgar_flags_from_filings over the SAME submissions list:
    {eightk, sec}. eightk = the newest 8-K inside _EIGHTK_WINDOW_DAYS with its
    item codes; sec = a roll-up of everything else filed inside
    _SEC_WINDOW_DAYS (count, distinct forms newest-first, the latest one,
    Form 4 count, offering plumbing). Both None-shaped when nothing is there."""
    now = now or datetime.now(timezone.utc)
    k_cut = (now - timedelta(days=_EIGHTK_WINDOW_DAYS)).date()
    s_cut = (now - timedelta(days=_SEC_WINDOW_DAYS)).date()
    eightk, n_8k = None, 0
    others: list[dict] = []
    for f in filings or []:
        form = (f.get("form") or "").upper()
        try:
            fdate = datetime.strptime(f.get("filing_date") or "", "%Y-%m-%d").date()
        except Exception:
            continue
        base = {"form": form, "filing_date": f.get("filing_date"), "url": f.get("url")}
        if form.startswith("8-K"):
            if fdate >= k_cut:
                n_8k += 1
                if eightk is None:
                    codes = [c.strip() for c in (f.get("items") or "").split(",") if c.strip()]
                    eightk = {**base, "items": codes}
            continue
        if fdate >= s_cut:
            others.append(base)
    if eightk is not None:
        eightk["n_14d"] = n_8k
    others.sort(key=lambda b: b["filing_date"], reverse=True)
    sec = None
    if others:
        forms: list[str] = []
        for b in others:
            if b["form"] not in forms:
                forms.append(b["form"])
        sec = {
            "n_30d": len(others), "forms": forms[:5], "latest": others[0],
            "n_form4": sum(1 for b in others if b["form"] in ("4", "4/A")),
            "has_offering": any(not b["form"].startswith("S-8")
                                and b["form"].startswith(_SHELF_PREFIXES) for b in others),
        }
    return {"eightk": eightk, "sec": sec}


def _edgar_bundle(ticker: str) -> dict:
    """ONE EDGAR submissions fetch feeds three fields — edgar (the two dated
    tells), eightk, sec. Never three fetches for one row."""
    try:
        from .evidence import _fetch_sec_filings
        filings = _fetch_sec_filings(ticker, days=_SEC_WINDOW_DAYS)
        return {"edgar": edgar_flags_from_filings(filings), **sec_flags_from_filings(filings)}
    except Exception as exc:
        log.debug("edgar bundle failed for %s: %s", ticker, exc)
        return {"edgar": {"owner_stake": None, "shelf": None}, "eightk": None, "sec": None}


def catalyst_from_news(news: Optional[list], now: Optional[datetime] = None) -> Optional[dict]:
    """Pure: 48h news list (evidence._fetch_massive_news shape, each item
    already carrying `tone`) -> {n_48h, n_bullish, n_bearish, top, verdict}.
    REAL = a headline the keyword tagger reads as bullish or bearish (a
    contract, an approval, an offering...); THIN = only untagged chatter;
    NONE = nothing in 48h. None in = fetch failed -> None out (unknown, not
    'no catalyst')."""
    if news is None:
        return None
    items = sorted((n for n in news if n.get("title")),
                   key=lambda n: n.get("published_utc") or "", reverse=True)
    n_b = sum(1 for n in items if n.get("tone") == "bullish")
    n_r = sum(1 for n in items if n.get("tone") == "bearish")
    top = next((n for n in items if n.get("tone") in ("bullish", "bearish")), items[0] if items else None)
    verdict = "REAL" if (n_b or n_r) else ("THIN" if items else "NONE")
    return {
        "n_48h": len(items), "n_bullish": n_b, "n_bearish": n_r, "verdict": verdict,
        "top": ({"title": top.get("title"), "url": top.get("url"), "publisher": top.get("publisher"),
                 "published_utc": top.get("published_utc"), "tone": top.get("tone") or "neutral"}
                if top else None),
    }


def _catalyst(ticker: str) -> Optional[dict]:
    """48h news read, cached per ticker for NEWS_CACHE_TTL_SEC so the 10-min
    board never re-asks Massive about the same name."""
    coll = _coll("promo_news_cache")
    now = time.time()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": ticker})
            if doc and now - float(doc.get("at") or 0) < NEWS_CACHE_TTL_SEC:
                return doc.get("catalyst")
        except Exception:
            pass
    try:
        from .evidence import _fetch_massive_news, _tag_news_tone
        news = _fetch_massive_news(ticker, hours=48)
        for n in news:
            n["tone"] = _tag_news_tone(n.get("title") or "", n.get("description") or "")
        out = catalyst_from_news(news)
    except Exception as exc:
        log.debug("catalyst news failed for %s: %s", ticker, exc)
        return None
    if coll is not None and out is not None:
        try:
            coll.update_one({"_id": ticker}, {"$set": {"at": now, "catalyst": out}}, upsert=True)
        except Exception:
            pass
    return out


def _sales_project(block: Optional[dict], source: str) -> Optional[dict]:
    if not block:
        return None
    return {"tier": block.get("tier"), "growth_yoy_pct": block.get("growth_yoy_pct"),
            "prior_yoy_pct": block.get("prior_yoy_pct"), "accelerating": block.get("accelerating"),
            "score": block.get("score"), "reason": block.get("reason"), "source": source}


def sales_for(tickers: list[str], fetch=None, snapshot=None, coll=None,
              cap: int = SALES_FETCH_CAP, budget_sec: float = SALES_FETCH_BUDGET_SEC) -> dict:
    """Bonde sales read (sepa/sales.py::compute — YoY, never QoQ) for every
    ticker: the SEPA research cache first (one Mongo query), then this
    board's own 7-day cache, then at most `cap` provider lookups inside
    `budget_sec` for names the SEPA universe never researched (most promo
    micro-caps). A miss stays None — 'unknown', never a pass."""
    out: dict = {}
    if snapshot is None:
        def snapshot(syms):
            from sepa.research import sales_snapshot
            return sales_snapshot(syms)
    try:
        snap = snapshot(list(tickers)) or {}
    except Exception as exc:
        log.warning("promo board: sales snapshot failed: %s", exc)
        snap = {}
    for t in tickers:
        blk = (snap.get(t) or {}).get("sales")
        if blk:
            out[t] = _sales_project(blk, "sepa_research")
    missing = [t for t in tickers if t not in out]
    coll = coll if coll is not None else _coll("promo_sales_cache")
    now = time.time()
    if coll is not None and missing:
        try:
            for d in coll.find({"_id": {"$in": missing}}):
                if now - float(d.get("at") or 0) < SALES_CACHE_TTL_SEC:
                    out[d["_id"]] = d.get("sales")            # may be None = looked, nothing
        except Exception as exc:
            log.warning("promo board: sales cache read failed: %s", exc)
    missing = [t for t in tickers if t not in out][:cap]
    if not missing:
        return out
    if fetch is None:
        def fetch(sym):
            from sepa.canslim import fundamentals_for
            return (fundamentals_for(sym) or {}).get("sales")
    t0 = time.time()

    def _one(sym):
        if time.time() - t0 > budget_sec:
            return sym, "skip", None
        try:
            return sym, "ok", fetch(sym)
        except Exception as exc:
            log.debug("sales fetch failed for %s: %s", sym, exc)
            return sym, "err", None
    with ThreadPoolExecutor(max_workers=4) as ex:
        for sym, state, blk in ex.map(_one, missing):
            if state == "skip":
                continue
            val = _sales_project(blk, "provider") if state == "ok" else None
            out[sym] = val
            if coll is not None and state == "ok":
                try:
                    coll.update_one({"_id": sym}, {"$set": {"at": now, "sales": val}}, upsert=True)
                except Exception:
                    pass
    return out


def russell_for(coll=None) -> dict:
    """Per-symbol join onto the Russell watch's CACHED board (raw read — never
    russell_watch.build(): a cold build takes minutes). {symbol: {board,
    market_cap, add_event, first_seen, as_of}}; {} when no board yet."""
    try:
        if coll is None:
            from . import russell_watch as rw
            coll = rw._cache_coll()
        if coll is None:
            return {}
        pay = (coll.find_one({"_id": "board"}) or {}).get("payload") or {}
    except Exception as exc:
        log.warning("promo board: russell join failed: %s", exc)
        return {}
    out = {}
    for r in (pay.get("adds_r2000") or []) + (pay.get("promotions_r1000") or []):
        out[r["symbol"]] = {"board": r.get("board"), "market_cap": r.get("market_cap"),
                            "add_event": r.get("add_event"), "first_seen": r.get("first_seen"),
                            "as_of": pay.get("as_of")}
    return out


def _enrich(row: dict) -> dict:
    """The capped network pass for one actionable row: one EDGAR fetch (edgar
    + eightk + sec) and one cached news read (catalyst)."""
    b = _edgar_bundle(row["ticker"])
    return {**b, "catalyst": _catalyst(row["ticker"])}


# --- Board ----------------------------------------------------------------

def _as_utc(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def prune_shotgun_tags(tags: list[dict],
                       max_distinct: int = SHOTGUN_DISTINCT_TAGS) -> list[dict]:
    """Pure: drop one-off mentions from shotgun accounts.

    Measured 2026-09-01: ShangVXO ~100 distinct cashtags, XkaliburTrading
    180/month, PSM 163/month — watchlist machines whose single drive-by
    mentions (LZB, HZO, DZZ...) buried the board in 274 fake SEEDING rows.
    An account tagging more than `max_distinct` tickers in the window keeps
    only tickers it mentioned in >= 2 messages (repetition = campaign);
    focused accounts keep everything.
    """
    per_account: dict[str, int] = {}
    for t in tags:
        per_account[t["account"]] = per_account.get(t["account"], 0) + 1
    return [t for t in tags
            if per_account[t["account"]] <= max_distinct
            or (t.get("n_messages") or 0) >= 2]


def build(force: bool = False) -> dict:
    """The watchlist board: every ticker tagged by the roster in the last
    TAG_WINDOW_DAYS, with who/when, price-since-tag, status, EDGAR tells."""
    cache = _coll("promo_circuit_cache")
    now = datetime.now(timezone.utc)
    if not force and cache is not None:
        try:
            doc = cache.find_one({"_id": "latest"})
            ts = _as_utc((doc or {}).get("cached_at"))
            if doc and ts and (now - ts).total_seconds() < _CACHE_TTL_SEC:
                payload = dict(doc["payload"])
                payload["cached"] = True
                payload["cache_age_sec"] = round((now - ts).total_seconds())
                return payload
        except Exception as exc:
            log.warning("promo cache get failed: %s", exc)

    t0 = time.time()
    coll = _tags_coll()
    cutoff = now - timedelta(days=TAG_WINDOW_DAYS)
    tags: list[dict] = []
    if coll is not None:
        try:
            tags = list(coll.find({"last_tagged_at": {"$gte": cutoff}}))
        except Exception as exc:
            log.warning("promo tags read failed: %s", exc)

    tags = prune_shotgun_tags(
        [t for t in tags if t.get("account") in PROMO_ACCOUNTS])

    # Group by ticker
    by_ticker: dict[str, list[dict]] = {}
    for t in tags:
        by_ticker.setdefault(t["ticker"], []).append(t)

    tickers = sorted(by_ticker.keys())

    def _tier(rec: dict) -> str:
        # The LIVE roster is the tier authority — a stored tier is just a
        # snapshot, and roster edits must apply to existing tags
        # immediately (review finding 2026-09-01).
        acct = PROMO_ACCOUNTS.get(rec.get("account")) or {}
        return acct.get("tier") or rec.get("tier") or "B"

    # Two FREE bulk reads, hoisted out of the per-row pool (sales: one Mongo
    # query + capped provider fill; russell: the cached board, raw).
    sales_by = sales_for(tickers)
    russ_by = russell_for()

    def _row(tkr: str) -> dict:
        recs = sorted(by_ticker[tkr], key=lambda r: TIER_ORDER.get(_tier(r), 9))
        first = min((_as_utc(r.get("first_tagged_at")) or now) for r in recs)
        latest = max((_as_utc(r.get("last_tagged_at")) or first) for r in recs)
        days_since_first = (now - first).total_seconds() / 86400
        days_since_last = (now - latest).total_seconds() / 86400
        pa = price_action_since(_bars_since(tkr, first), tag_date=first.date())
        status = classify_status(days_since_last, pa["pct_since_tag"],
                                 pa["max_gain_pct"], pa["drop_from_peak_pct"])
        return {
            "ticker": tkr,
            "accounts": [{
                "handle": r["account"], "tier": _tier(r),
                "last_tagged_at": (_as_utc(r.get("last_tagged_at")) or now).isoformat(),
                "n_messages": r.get("n_messages"),
                "sample": r.get("sample"),
            } for r in recs],
            "best_tier": _tier(recs[0]),
            "first_tagged_at": first.isoformat(),
            "last_tagged_at": max((_as_utc(r.get("last_tagged_at")) or now) for r in recs).isoformat(),
            "days_since_first_tag": round(days_since_first, 1),
            "days_since_last_tag": round(days_since_last, 1),
            **pa,
            "status": status,
            "edgar": {"owner_stake": None, "shelf": None},
            # the five tells (Ajay 2026-09-02) — slow-changing, so they live
            # on the 10-min board, and the live table just carries them over
            "russell": russ_by.get(tkr),
            "sales": sales_by.get(tkr),
            "catalyst": None, "eightk": None, "sec": None,
        }

    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(_row, tickers))

    status_rank = {"SEEDING": 0, "RAN": 1, "DUMPED": 2, "QUIET": 3, "UNKNOWN": 4}
    rows.sort(key=lambda r: (status_rank.get(r["status"], 9),
                             TIER_ORDER.get(r["best_tier"], 9),
                             r["days_since_last_tag"]))

    # EDGAR tells only for the rows anyone will act on — a 377-row first
    # build spent 104s mostly on EDGAR for QUIET noise (measured 2026-09-01).
    edgar_rows = [r for r in rows[:EDGAR_ROW_CAP]
                  if r["status"] in ("SEEDING", "RAN", "DUMPED")]
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r, got in zip(edgar_rows, ex.map(_enrich, edgar_rows)):
            r["edgar"] = got["edgar"]
            r["eightk"], r["sec"], r["catalyst"] = got["eightk"], got["sec"], got["catalyst"]

    meta_coll = _coll("promo_circuit_meta")
    sweep_meta = None
    if meta_coll is not None:
        try:
            doc = meta_coll.find_one({"_id": "sweep"}) or {}
            ts = _as_utc(doc.get("last_sweep_at"))
            sweep_meta = {
                "last_sweep_at": ts.isoformat() if ts else None,
                "accounts_failed": doc.get("accounts_failed") or [],
            }
        except Exception:
            pass

    payload = {
        "as_of": now.isoformat(),
        "rows": rows,
        "n_tickers": len(rows),
        "roster": [{"handle": h, **m} for h, m in PROMO_ACCOUNTS.items()],
        "sweep": sweep_meta,
        "method_note": (
            "Roster = accounts caught seeding the 8/31-9/1 movers in the "
            "2026-09-01 provenance study (StockTwits timestamps + EDGAR "
            "acceptance times). A tag from them is the PROMOTION, not "
            "foresight: SEEDING = tagged, hasn't run — expect the pop, and "
            "expect to be exit liquidity if you chase it. EDGAR tells: "
            "13D/G owner stakes were the study's one genuinely predictive "
            "public signal (GPRO); fresh S-1/S-3/F-1/F-3/424B/FWP is "
            "dilution plumbing (NWGL resale, SSM direct, LIDR ATM). "
            "Roster is user-editable in backend/catalysts/promo_circuit.py."
        ),
        "elapsed_sec": round(time.time() - t0, 1),
        "cached": False,
        "cache_age_sec": 0,
    }
    if cache is not None:
        try:
            cache.update_one({"_id": "latest"},
                             {"$set": {"cached_at": now, "payload": payload}},
                             upsert=True)
        except Exception as exc:
            log.warning("promo cache put failed: %s", exc)
    return payload


# --- Predictions integration ----------------------------------------------

def tags_for(tickers: list[str], days: int = PENALTY_WINDOW_DAYS) -> dict[str, dict]:
    """S/A-tier tags in the last `days` for these tickers, for the
    predictions penalty. B-tier watchlist reposters never penalize."""
    coll = _tags_coll()
    if coll is None or not tickers:
        return {}
    now = datetime.now(timezone.utc)
    # Query with the widest window any roster account carries; the
    # per-account window is enforced below. An account can override the
    # default via "penalty_days" — ShangVXO's pumps land ~10 sessions after
    # his tags, so a 7-day window expired right before the move (measured
    # 2026-09-02: PETZ ran session 9, FLYE session 8).
    max_days = max([days] + [int(m.get("penalty_days") or 0)
                             for m in PROMO_ACCOUNTS.values()])
    cutoff = now - timedelta(days=max_days)
    out: dict[str, dict] = {}
    try:
        # Tier is resolved against the LIVE roster, not the tier stamped on
        # the doc at sweep time — a roster demotion/promotion must apply to
        # existing tags immediately (review finding 2026-09-01).
        cur = coll.find({"ticker": {"$in": [t.upper() for t in tickers]},
                         "last_tagged_at": {"$gte": cutoff}})
        for doc in cur:
            acct = PROMO_ACCOUNTS.get(doc.get("account"))
            if not acct or acct.get("tier") not in ("S", "A"):
                continue
            ts = _as_utc(doc.get("last_tagged_at"))
            window = int(acct.get("penalty_days") or days)
            if not ts or (now - ts) > timedelta(days=window):
                continue
            t = doc["ticker"]
            rec = out.setdefault(t, {"handles": [], "tiers": [], "days_ago": 0.0})
            rec["handles"].append(doc["account"])
            rec["tiers"].append(acct.get("tier"))
            rec["days_ago"] = max(rec["days_ago"],
                                  round((now - ts).total_seconds() / 86400, 1))
    except Exception as exc:
        log.warning("promo tags_for failed: %s", exc)
        return {}
    return out


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    print(json.dumps(sweep(), indent=2))
    # Pre-warm the board cache so the page never pays the ~70s first build
    # (bars + EDGAR for ~150 tickers) interactively.
    b = build(force=True)
    print(json.dumps({"board_rows": b.get("n_tickers"),
                      "board_build_sec": b.get("elapsed_sec")}, indent=2))


def backfill_posts(days: int = 14) -> dict:
    """One-off: fetch every roster stream back `days` and add each post to
    its tag record's `posts` (never touching high-water marks or counts).
    Needed once after 2026-09-02, when the sweep started keeping posts."""
    coll = _tags_coll()
    if coll is None:
        return {"ok": False, "reason": "mongo unavailable"}
    oldest = datetime.now(timezone.utc) - timedelta(days=days)
    added, failed = 0, []
    for handle in PROMO_ACCOUNTS:
        msgs = _fetch_user_stream(handle, oldest=oldest, max_pages=40)
        if msgs is None:
            failed.append(handle)
            continue
        for tkr, rec in extract_tags(handle, msgs).items():
            try:
                res = coll.update_one({"_id": f"{handle}:{tkr}"},
                                      {"$addToSet": {"posts": {"$each": rec["posts"]}}})
                added += int(res.matched_count or 0)
            except Exception as exc:                        # pragma: no cover
                log.warning("backfill %s:%s failed: %s", handle, tkr, exc)
    return {"ok": True, "records_touched": added, "accounts_failed": failed, "days": days}
