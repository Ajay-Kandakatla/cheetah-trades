"""Sector day-tags — one name's bull case AND bear case, off the day's news.

Ajay 2026-09-19, verbatim:

    "Also for the hot sectors if you see any postive news I would like you to
     see a bullish and bearish case result for a stocks and add it to the
     sector as a tag for that day."

So: walk the 🔥 Hottest board's sectors, look at the news on their leading
names, and where a name actually HAS news today, attach one tag to that
sector for that date carrying both sides of the argument.

WHY BOTH SIDES, ALWAYS
----------------------
He asked for both, and that is what keeps this honest. A one-sided "positive
news" tag on a board he already reads as a discovery surface would function
as a buy suggestion while claiming to be a summary. A tag that always states
the case against is a briefing. If the bear case is ever missing, the tag is
suppressed rather than shown half-built — see `_usable`.

WHO DECIDES "POSITIVE"
----------------------
The LLM does, reading the headlines, and the payload says so in those words.
There is NO sentiment score here, because we do not have a measured one: no
lexicon was invented, no numeric threshold was fitted, and nothing counts
"positive words". A fitted score would look like evidence and be worth
nothing. The tag carries `read_by` so the surface can never present this as
measurement.

THE DIVISION OF LABOUR IS THE SAME ONE THE DESK REPORT USES
-----------------------------------------------------------
`desk.report` established it and this follows it exactly: the app owns every
NUMBER, the model owns only PROSE. The facts block below is built from the
hottest payload — returns against the benchmark, the zone state, sales and
EPS growth, the next earnings date — and handed to the model. The model is
told, in the system prompt, that it may not introduce a number that is not in
that block. Whatever it writes, the numbers a reader sees on the tile are
rendered by the frontend from `facts`, never parsed back out of the prose.

NOT A SIGNAL, NOT A GATE
------------------------
This tag pushes nothing, gates nothing, sizes nothing and enters no lane. It
does not reorder the board: `attach()` writes onto sector rows that were
already ranked and returns them in the order it received them. The 🔥 Hottest
board is explicitly a DISCOVERY surface with no measured edge, and a tag on
top of it inherits exactly that status and no more.

FAILURE IS QUIET AND TOTAL
--------------------------
Every step degrades to "no tag": news down, LLM off, model returns junk, one
side of the argument missing. A sector with no tag renders as it always did.
Nothing on this board is allowed to break because a headline feed timed out.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("cheetah.rotation.sector_news_tags")

# ── SCOPE KNOBS, NOT SIGNAL THRESHOLDS ─────────────────────────────────────
# These bound COST — how much of the board gets looked at in one pass. None of
# them is fitted to an outcome, none gates anything, and moving one changes
# how much gets summarised, never what any number means. They are deliberately
# separate from anything in supply_demand/ or trading/, which is where real
# thresholds live and where nothing here may reach.
SECTORS_PER_RUN = 6        # sectors tagged per pass, hottest first
NAMES_PER_SECTOR = 5       # leading names whose news is read, per sector
NEWS_WINDOW_HOURS = 36     # a headline older than this is not "today's news";
                           # 36 not 24 so a Monday run still sees Friday's
                           # close-of-day story and a weekend run sees Friday
MIN_HEADLINES = 2          # one loose headline is not a story worth a tag
MAX_HEADLINES_TO_MODEL = 6

# Two paragraphs of prose plus the JSON scaffolding — and, on a REASONING
# model, the reasoning that comes first. MEASURED against the model actually
# installed here (huihui_ai/Qwen3.8-abliterated:27b via Ollama), on real board
# prompts of ~1,900 characters:
#
#     700   -> truncated mid-string; ok=True, 847 chars, json.loads failed
#     1200  -> 5 of 6 sectors returned EMPTY content (thinking ate the budget)
#     2500  -> 6 of 6 parse and are usable; ~145s per sector, ~1,000 chars out
#
# The 1200 failure is the instructive one: `ok=True` with `textlen=0`. Qwen3
# spends its budget reasoning before it writes anything, Ollama returns the
# reasoning outside `content`, and a budget that runs out mid-thought yields a
# successful HTTP call carrying nothing. It does not look like a failure
# anywhere except in the output.
#
# `/no_think` was tried and does NOT work through Ollama's OpenAI-compatible
# endpoint on this model — measured, same empty result. Budget is the lever.
#
# Six sectors at ~145s is about fifteen minutes once a day on a local model
# that costs nothing, finishing long before the open. No reason to run tight.
MAX_TOKENS = 2500
MODEL_TIMEOUT_SEC = 300

COLLECTION = "sector_day_tags"

# The day stamp is the ET SESSION DATE, not UTC. He reads this board in the
# evening in CT, when UTC has already rolled over: a UTC stamp would file the
# 06:20 run under one date and then look it up under the next one. `latest_within`
# would still find it by walking back a day, but only by papering over a wrong
# stamp — and the tag prints its date on the tile, so a wrong one is visible.
ET = ZoneInfo("America/New_York")


def today_et() -> str:
    return datetime.now(ET).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Facts — everything the model is allowed to know, all of it from the payload
# ---------------------------------------------------------------------------
def _num(v):
    return v if isinstance(v, (int, float)) and v == v else None


def _facts(sector_row: dict, name_row: dict) -> dict:
    """The deterministic block. Every number the tag will ever show.

    Only keys whose value is actually present survive, so the model is never
    handed a `None` to hallucinate around and the frontend never renders an
    em-dash where a fact should be.
    """
    raw = {
        "sector": sector_row.get("group"),
        "sector_vs_benchmark_1d_pct": _num(sector_row.get("rel_1d")),
        "sector_vs_benchmark_5d_pct": _num(sector_row.get("rel_5d")),
        "sector_vs_benchmark_21d_pct": _num(sector_row.get("rel_21d")),
        "sector_members_up_today_pct": _num(sector_row.get("pct_positive_1d")),
        "symbol": name_row.get("symbol"),
        "company": name_row.get("name"),
        "industry": name_row.get("industry"),
        "last_close": _num(name_row.get("last_close")),
        "vs_benchmark_1d_pct": _num(name_row.get("rel_1d")),
        "vs_benchmark_5d_pct": _num(name_row.get("rel_5d")),
        "vs_benchmark_21d_pct": _num(name_row.get("rel_21d")),
        "vs_its_own_sector_21d_pct": _num(name_row.get("vs_group_21")),
        "sales_growth_yoy_pct": _num(name_row.get("sales_yoy")),
        "eps_growth_yoy_pct": _num(name_row.get("q_eps_yoy")),
        "net_margin_pct": _num(name_row.get("net_margin")),
        "sales_accelerating": name_row.get("sales_accelerating"),
        "margin_expanding": name_row.get("margin_expanding"),
        "next_earnings": name_row.get("next_earnings"),
        # The zone state matters to BOTH cases and is the one thing on this
        # row that says where price actually is rather than how fast it got
        # there. `at_demand` is the shipped read; it is passed through
        # verbatim and never recomputed here.
        "at_demand": name_row.get("at_demand"),
        "zone_role": name_row.get("zone_role"),
        "zone_off_floor_pct": _num(name_row.get("zone_off_floor_pct")),
    }
    return {k: v for k, v in raw.items() if v is not None and v != ""}


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------
def _fresh(items: list, now: Optional[float] = None) -> list:
    """Headlines inside NEWS_WINDOW_HOURS, newest first.

    An item with no timestamp is DROPPED rather than assumed fresh. The feeds
    mix three providers and Google's RSS is the one that most often omits it;
    letting those through would quietly turn a 36-hour window into "whatever
    the cache holds".
    """
    now = time.time() if now is None else now
    floor = now - NEWS_WINDOW_HOURS * 3600
    out = []
    for it in items or []:
        ts = it.get("published")
        if not isinstance(ts, (int, float)) or ts != ts:
            continue
        # Feeds have shipped milliseconds before; a 13-digit stamp is not a
        # headline from the year 45000.
        if ts > 1e12:
            ts = ts / 1000.0
        if ts < floor or ts > now + 3600:
            continue
        out.append({**it, "published": ts})
    out.sort(key=lambda x: x["published"], reverse=True)
    return out


async def _news_for(symbols: list) -> dict:
    """{SYMBOL: [fresh headline, ...]} — failures come back as empty lists."""
    try:
        from news import fetch_news
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sector tags: news module unavailable: %s", exc)
        return {}

    async def one(sym):
        try:
            return sym, _fresh(await fetch_news(sym))
        except Exception as exc:                               # noqa: BLE001
            log.debug("sector tags: news %s failed: %s", sym, exc)
            return sym, []

    pairs = await asyncio.gather(*(one(s) for s in symbols))
    return dict(pairs)


# ---------------------------------------------------------------------------
# The model leg — prose only
# ---------------------------------------------------------------------------
_SYSTEM = """You write two-sided briefing notes for one experienced trader.

HARD RULES, in order of importance:
1. You may not state any number that is not present in the FACTS block you
   are given. Not a price target, not a percentage, not a market share, not a
   date. If you want to say a thing is growing fast, say it in words.
2. You write BOTH a bull case and a bear case, always, even when the news
   reads one-sided. The bear case on good news is the part that has value.
3. Ground both cases in the supplied HEADLINES and FACTS. Do not import
   anything you happen to know about the company from elsewhere.
4. No recommendation, no rating, no "buy"/"sell"/"hold", no price target, no
   position sizing. You are describing an argument, not giving advice.
5. Say "reversal", never "bounce".
6. Two to three sentences per case. Plain language. No preamble.

Return STRICT JSON, no markdown fence:
{"positive": true|false, "bull": "...", "bear": "...", "why_positive": "..."}

"positive" is your read of whether the day's HEADLINES are net favourable for
this company. "why_positive" is one short clause naming the headline that
decided it. If the headlines are routine noise with nothing favourable in
them, set positive to false and still write both cases."""


def _ask_model(facts: dict, headlines: list) -> Optional[dict]:
    """One model call. None on any failure — the caller then writes no tag."""
    try:
        import llm
        if not llm.is_enabled():
            return None
        payload = {
            "FACTS": facts,
            "HEADLINES": [
                {"title": h.get("title"), "source": h.get("source"),
                 "summary": (h.get("summary") or "")[:280]}
                for h in headlines[:MAX_HEADLINES_TO_MODEL]
            ],
        }
        # LOCAL FIRST, then the hosted model. Not `provider="auto"`, which
        # resolves to Anthropic whenever a key is configured and would send
        # every one of these off-box even with LM Studio running.
        #
        # The fallback is not decoration: measured on the cron container the
        # day this shipped, the local server was refusing connections
        # (host.docker.internal:1234) while Anthropic answered. A daily
        # unattended job that only ever tried local would have shipped as a
        # feature that silently never fires. `read_by` records which one
        # actually wrote it, on every tag.
        prompt = json.dumps(payload, default=str)
        resp = llm.chat(prompt, system=_SYSTEM, provider="local",
                        json_only=True, max_tokens=MAX_TOKENS, temperature=0.3,
                        timeout=MODEL_TIMEOUT_SEC)
        if not resp.get("ok") or not isinstance(resp.get("parsed"), dict):
            log.info("sector tags: local model unusable (%s) — trying hosted",
                     str(resp.get("error"))[:120])
            resp = llm.chat(prompt, system=_SYSTEM, provider="anthropic",
                            json_only=True, max_tokens=MAX_TOKENS,
                            temperature=0.3, timeout=MODEL_TIMEOUT_SEC)
        if not resp.get("ok"):
            return None
        parsed = resp.get("parsed")
        if not isinstance(parsed, dict):
            return None
        parsed["provider"] = resp.get("provider")
        return parsed
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sector tags: model leg failed: %s", exc)
        return None


def _usable(parsed: Optional[dict]) -> bool:
    """A tag ships only with BOTH sides written.

    Half a tag is worse than none: a bull case with an empty bear case reads
    as a recommendation, which is the one thing this is not.
    """
    if not isinstance(parsed, dict):
        return False
    bull = (parsed.get("bull") or "").strip()
    bear = (parsed.get("bear") or "").strip()
    return len(bull) >= 40 and len(bear) >= 40


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def _pick_name(names: list, news: dict) -> Optional[tuple]:
    """The leading name that actually has a story today.

    Ordered by HEADLINE COUNT, then by the board's own ranking. Deliberately
    NOT by return: picking the biggest mover would make the tag a momentum
    read wearing a news label, and he can already sort the board by return.
    """
    best = None
    for rank, row in enumerate(names[:NAMES_PER_SECTOR]):
        sym = (row.get("symbol") or "").upper()
        items = news.get(sym) or []
        if len(items) < MIN_HEADLINES:
            continue
        key = (-len(items), rank)
        if best is None or key < best[0]:
            best = (key, row, items)
    return (best[1], best[2]) if best else None


def build(hottest_payload: dict, *, date: Optional[str] = None,
          sectors_per_run: int = SECTORS_PER_RUN) -> dict:
    """Build today's tags from a `rotation.hottest` payload.

    Returns ``{"date", "tags": {sector: tag}, "counts": {...}}``. Never
    raises: a sector that fails for any reason is simply absent from `tags`.
    """
    day = date or today_et()
    sectors = (hottest_payload or {}).get("sectors") or []
    considered = [s for s in sectors if (s.get("names") or [])][:sectors_per_run]

    wanted = []
    for s in considered:
        for row in (s.get("names") or [])[:NAMES_PER_SECTOR]:
            sym = (row.get("symbol") or "").upper()
            if sym:
                wanted.append(sym)
    wanted = sorted(set(wanted))
    if not wanted:
        return {"date": day, "tags": {},
                "counts": {"sectors": 0, "no_news": 0, "no_model": 0}}

    try:
        news = asyncio.run(_news_for(wanted))
    except RuntimeError:
        # Already inside a loop (the API path). Hand it to a worker thread so
        # this is callable from both the cron and a request.
        import concurrent.futures as _f
        with _f.ThreadPoolExecutor(max_workers=1) as ex:
            news = ex.submit(lambda: asyncio.run(_news_for(wanted))).result()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sector tags: news sweep failed: %s", exc)
        news = {}

    tags, no_news, no_model = {}, 0, 0
    for s in considered:
        sector = s.get("group")
        if not sector:
            continue
        picked = _pick_name(s.get("names") or [], news)
        if not picked:
            no_news += 1
            continue
        name_row, items = picked
        facts = _facts(s, name_row)
        parsed = _ask_model(facts, items)
        if not _usable(parsed):
            no_model += 1
            continue
        top = items[0]
        tags[sector] = {
            "date": day,
            "sector": sector,
            "symbol": name_row.get("symbol"),
            "company": name_row.get("name"),
            "positive": bool(parsed.get("positive")),
            "why_positive": (parsed.get("why_positive") or "").strip() or None,
            "bull": parsed["bull"].strip(),
            "bear": parsed["bear"].strip(),
            "headline_count": len(items),
            "trigger": {"title": top.get("title"), "url": top.get("url"),
                        "source": top.get("source"),
                        "published": top.get("published")},
            "facts": facts,
            # So no surface can ever present this as a measurement.
            "read_by": parsed.get("provider") or "llm",
            "measured": False,
            "built_at": time.time(),
        }

    return {"date": day, "tags": tags,
            "counts": {"sectors": len(considered), "tagged": len(tags),
                       "no_news": no_news, "no_model": no_model}}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
def _coll():
    try:
        from sepa.prices import _get_mongo
        pc = _get_mongo()
        return None if pc is None else pc.database[COLLECTION]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sector tags: mongo unavailable: %s", exc)
        return None


def save(built: dict) -> int:
    """Upsert one doc per (date, sector). Returns how many were written."""
    coll = _coll()
    if coll is None:
        return 0
    n = 0
    for sector, tag in (built.get("tags") or {}).items():
        try:
            coll.replace_one({"_id": f"{built['date']}|{sector}"},
                             {"_id": f"{built['date']}|{sector}", **tag},
                             upsert=True)
            n += 1
        except Exception as exc:                               # noqa: BLE001
            log.warning("sector tags: save %s failed: %s", sector, exc)
    return n


def load(date: Optional[str] = None) -> dict:
    """{sector: tag} for one date. Empty dict when Mongo is down.

    A date with no tags returns ``{}`` and the board renders exactly as it did
    before any of this existed.
    """
    coll = _coll()
    if coll is None:
        return {}
    day = date or today_et()
    try:
        out = {}
        for doc in coll.find({"date": day}):
            doc.pop("_id", None)
            if doc.get("sector"):
                out[doc["sector"]] = doc
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sector tags: load failed: %s", exc)
        return {}


def latest_within(days: int = 3) -> dict:
    """{sector: tag} from the most recent date that HAS tags, within `days`.

    The weekend problem: he asked for a weekend run, and a Sunday pass builds
    off Friday's board with Friday's news. Rather than print nothing on a
    Sunday, the board falls back to the newest day that produced tags and the
    tag carries its own `date` so the surface can say which day it is from.
    """
    today = datetime.now(ET).date()
    for back in range(max(0, int(days)) + 1):
        day = (today - timedelta(days=back)).strftime("%Y-%m-%d")
        got = load(day)
        if got:
            return got
    return {}


def attach(payload: dict, tags: Optional[dict] = None) -> dict:
    """Hang each sector's tag on its row, in place, and return the payload.

    ORDER IS NEVER TOUCHED. The board's ranking is the board's business; this
    adds a key and nothing else. A sector with no tag gets `day_tag: None` so
    the frontend reads one shape everywhere instead of testing for presence.
    """
    if not isinstance(payload, dict):
        return payload
    got = load() if tags is None else tags
    for s in payload.get("sectors") or []:
        if isinstance(s, dict):
            s["day_tag"] = got.get(s.get("group"))
    payload["day_tags_as_of"] = (
        next(iter(got.values()), {}).get("date") if got else None)
    return payload


def hottest_payload() -> Optional[dict]:
    """The same board the 🔥 Hottest endpoint serves, by the same route.

    Deliberately NOT a second way of building it. `rotation.api` reads the
    persisted rotation doc and never rebuilds, so the tag is always written
    against the board he is actually looking at; a private build here could
    tag a sector on numbers the board never showed.

    `build`, not `build_live`: the live leg re-quotes every name, and a tag
    written at 06:00 against prints that move all day would be describing a
    board that no longer exists by the time he reads it. Close basis, and the
    tag carries its date.
    """
    try:
        from . import api as A
        from . import hottest as H
        from . import tracker as T
        table, _meta = A._members_table()
        if table is None:
            return None
        payload = dict(A._members_payload() or {})
        payload[T.MEMBERS_KEY] = table
        return H.build(payload)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sector tags: hottest payload unavailable: %s", exc)
        return None


def run(sectors_per_run: int = SECTORS_PER_RUN) -> dict:
    """Cron entry point: build from the shipped hottest board, then store."""
    board = hottest_payload()
    if not board:
        return {"ok": False, "reason": "hottest board unavailable"}
    try:
        built = build(board, sectors_per_run=sectors_per_run)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sector tags: build failed: %s", exc)
        return {"ok": False, "reason": str(exc)[:200]}
    saved = save(built)
    log.info("sector tags %s: %s", built["date"], built["counts"])
    return {"ok": True, "date": built["date"], "saved": saved,
            **built["counts"]}


if __name__ == "__main__":       # `python -m rotation.sector_news_tags`
    print(run())
