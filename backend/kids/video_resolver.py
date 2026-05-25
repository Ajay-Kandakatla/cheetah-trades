"""Validated YouTube video resolver for kids activities.

Same pipeline as food/video_resolver.py:
  1. LLM crafts an optimal YouTube search query for the activity
  2. Scrape YouTube search results HTML for video IDs
  3. Validate each via oEmbed (free, no API key)
  4. LLM picks the best candidate biased toward authoritative sources
     (Tinkergarten official, Big Little Feelings, Janet Lansbury,
     Hands On As We Grow, Busy Toddler, How We Montessori)
  5. Cache the winner in Mongo `kids_video_cache`

CLI:
  python -m kids.video_resolver run         # resolve all
  python -m kids.video_resolver run NAME    # one activity by id
  python -m kids.video_resolver revalidate  # drop dead videos for re-resolve
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import requests

from llm import chat as llm_chat, is_enabled as llm_enabled
from kids import activities as act_mod

log = logging.getLogger("kids.video_resolver")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")

TRUSTED_KIDS_CHANNELS = [
    "Tinkergarten",
    "Big Little Feelings",
    "Janet Lansbury",
    "Hands On As We Grow",
    "Busy Toddler",
    "How We Montessori",
    "The Pinay Homeschooler",
    "Days With Grey",
    "TT Kids",
    "Toddlers Can Read",
]


def _coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        coll = client[os.getenv("MONGO_DB", "cheetah")].kids_video_cache
        coll.create_index([("activity_id", ASCENDING)], unique=True)
        return coll
    except Exception as exc:
        log.warning("kids video_cache mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def get_cached(activity_id: str) -> Optional[dict]:
    c = _coll()
    if c is None: return None
    doc = c.find_one({"activity_id": activity_id})
    if doc: doc.pop("_id", None)
    return doc


def put_cached(activity_id: str, payload: dict) -> None:
    c = _coll()
    if c is None: return
    c.update_one(
        {"activity_id": activity_id},
        {"$set": {**payload, "activity_id": activity_id, "validated_at": _now()}},
        upsert=True,
    )


def all_cached() -> list[dict]:
    c = _coll()
    if c is None: return []
    rows = list(c.find({}))
    for r in rows: r.pop("_id", None)
    return rows


def is_video_live(video_id: str) -> bool:
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}",
                    "format": "json"},
            timeout=6,
            headers={"User-Agent": UA},
        )
        return r.status_code == 200
    except Exception:
        return False


def oembed_metadata(video_id: str) -> Optional[dict]:
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}",
                    "format": "json"},
            timeout=6,
            headers={"User-Agent": UA},
        )
        if r.status_code != 200:
            return None
        d = r.json()
        return {
            "title":         d.get("title"),
            "author_name":   d.get("author_name"),
            "author_url":    d.get("author_url"),
            "thumbnail_url": d.get("thumbnail_url"),
        }
    except Exception:
        return None


def search_youtube(query: str, *, max_results: int = 10) -> list[str]:
    try:
        r = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": query, "hl": "en"},
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        html = r.text
    except Exception:
        return []

    ids: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r'"videoId":"([a-zA-Z0-9_-]{11})"', html):
        vid = m.group(1)
        if vid in seen: continue
        seen.add(vid)
        ids.append(vid)
        if len(ids) >= max_results:
            break
    return ids


def craft_search_query(activity: dict) -> str:
    """Use Gemma to craft a better-than-default search query.
    Biased TOWARD household-items demos and AWAY from buy-this-toy content.
    Falls back to the static `search_query` field on the activity."""
    if not llm_enabled():
        # Even the fallback gets the household-items keyword baked in.
        base = activity.get("search_query") or activity["name"]
        return f"{base} household items DIY at home"
    sys_prompt = (
        "You write YouTube search queries for parent-led toddler activities "
        "that use HOUSEHOLD ITEMS only — lentils, paper cups, rice, cardboard, "
        "ice cube trays, sponges. Avoid videos that pitch toys, kits, or "
        "subscription boxes. "
        f"Prefer trusted channels: {', '.join(TRUSTED_KIDS_CHANNELS)}. "
        "Keep the query under 14 words. Include phrases like 'at home', "
        "'household items', 'no toys needed', or 'DIY' when natural. "
        "Return ONLY the query — no quotes, no explanation."
    )
    user_prompt = (
        f"Activity: {activity['name']}\n"
        f"Framework: {activity.get('framework')}\n"
        f"Materials (household): {', '.join(activity.get('materials') or [])[:200]}\n"
        f"Skill: {activity.get('skill')}\n"
        f"Duration: {activity.get('duration_min')}min for ages "
        f"{activity.get('age_min')}-{activity.get('age_max')}\n\n"
        "Write the YouTube search query."
    )
    res = llm_chat(user_prompt, system=sys_prompt, max_tokens=80,
                   temperature=0.3, timeout=30)
    if res.get("ok") and res.get("text"):
        q = res["text"].strip().strip('"').splitlines()[0].strip()
        if 5 < len(q) < 200:
            return q
    return activity.get("search_query") or activity["name"]


def pick_best_candidate(activity: dict, candidates: list[dict]) -> Optional[dict]:
    if not candidates: return None
    if len(candidates) == 1:
        c = dict(candidates[0]); c["llm_reason"] = "only candidate"; return c
    if not llm_enabled():
        c = dict(candidates[0])
        c["llm_reason"] = "LLM disabled — picked top YouTube ranking"
        return c

    sys_prompt = (
        "You judge which YouTube video best demonstrates a parent-led toddler "
        "activity USING HOUSEHOLD ITEMS (lentils, paper cups, rice, cardboard, "
        "ice cube trays, sponges). The activity should be doable with stuff "
        "already in the kitchen / recycling — NO toys to buy, NO kits, NO "
        "subscription boxes. "
        f"Prefer authentic walkthroughs from trusted channels: {', '.join(TRUSTED_KIDS_CHANNELS)}. "
        "PENALIZE HEAVILY: shorts under 1 min, compilations, ads, "
        "AI-generated content, videos selling/promoting toys or kits, "
        "kid-passive-watching content (like Cocomelon clones), and anything "
        "not closely matching this specific activity. "
        'Reply with JSON only: {"choice_index": <int>, "reason": "<short>"}'
    )
    cand_lines = []
    for i, c in enumerate(candidates):
        cand_lines.append(
            f"  [{i}] title=\"{c.get('title','')}\" channel=\"{c.get('author_name','')}\""
        )
    user_prompt = (
        f"Activity: {activity['name']} ({activity.get('framework')}, "
        f"ages {activity.get('age_min')}-{activity.get('age_max')}).\n"
        f"What it teaches: {activity.get('skill')}\n\n"
        "Candidates:\n" + "\n".join(cand_lines)
    )
    res = llm_chat(user_prompt, system=sys_prompt, max_tokens=200,
                   temperature=0.2, json_only=True, timeout=45)
    parsed = (res.get("parsed") or {}) if res.get("ok") else {}
    idx = parsed.get("choice_index")
    reason = parsed.get("reason") or "LLM judged"
    if isinstance(idx, int) and 0 <= idx < len(candidates):
        c = dict(candidates[idx]); c["llm_reason"] = reason; return c
    c = dict(candidates[0])
    c["llm_reason"] = "LLM unparseable — picked top YouTube ranking"
    return c


def resolve_video(activity: dict, *, max_candidates: int = 8) -> Optional[dict]:
    aid = activity["id"]
    log.info("[%s] resolving…", aid)
    query = craft_search_query(activity)
    log.info("[%s] query=\"%s\"", aid, query)
    video_ids = search_youtube(query, max_results=max_candidates * 2)
    if not video_ids:
        log.warning("[%s] no candidates", aid)
        return None
    live: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for vid, meta in zip(video_ids, ex.map(oembed_metadata, video_ids[:max_candidates*2])):
            if meta is None: continue
            live.append({"video_id": vid, **meta})
            if len(live) >= max_candidates: break
    log.info("[%s] %d/%d live", aid, len(live), len(video_ids))
    if not live: return None
    pick = pick_best_candidate(activity, live)
    if pick is None: return None
    payload = {
        "activity_id":   aid,
        "video_id":      pick["video_id"],
        "video_url":     f"https://www.youtube.com/watch?v={pick['video_id']}",
        "title":         pick.get("title"),
        "author_name":   pick.get("author_name"),
        "author_url":    pick.get("author_url"),
        "thumbnail":     pick.get("thumbnail_url"),
        "search_query":  query,
        "candidates_seen": len(video_ids),
        "candidates_live": len(live),
        "llm_reason":    pick.get("llm_reason"),
    }
    put_cached(aid, payload)
    log.info("[%s] ✓ %s · %s", aid, pick.get("author_name"), (pick.get("title") or "")[:80])
    return payload


def resolve_all(force: bool = False, sleep_between: float = 0.5) -> dict:
    out = {"resolved": 0, "skipped": 0, "failed": 0}
    for activity in act_mod.ACTIVITIES:
        aid = activity["id"]
        if not force and get_cached(aid):
            out["skipped"] += 1
            continue
        try:
            res = resolve_video(activity)
            if res: out["resolved"] += 1
            else:   out["failed"] += 1
        except Exception:
            out["failed"] += 1
            log.exception("[%s] failed", aid)
        time.sleep(sleep_between)
    return out


def revalidate_cache() -> dict:
    coll = _coll()
    if coll is None: return {"ok": False, "reason": "mongo unavailable"}
    rows = list(coll.find({}))
    dead = 0
    for r in rows:
        vid = r.get("video_id")
        if not vid: continue
        if not is_video_live(vid):
            coll.delete_one({"activity_id": r["activity_id"]})
            dead += 1
    return {"ok": True, "checked": len(rows), "dropped_dead": dead}


def refresh_stale(max_age_days: int = 21) -> dict:
    """Re-resolve cache entries older than `max_age_days`. Drops them
    from cache so the next resolve_all pass finds CURRENT best videos
    via fresh YouTube search + Gemma judging — even when the existing
    pinned video is still alive."""
    coll = _coll()
    if coll is None: return {"ok": False, "reason": "mongo unavailable"}
    cutoff = _now() - max_age_days * 86400
    rows = list(coll.find({}))
    stale = kept = 0
    for r in rows:
        if (r.get("validated_at") or 0) < cutoff:
            coll.delete_one({"activity_id": r["activity_id"]})
            stale += 1
            log.info("refresh_stale: dropped %s", r["activity_id"])
        else:
            kept += 1
    return {"ok": True, "checked": len(rows),
            "dropped_stale": stale, "kept_fresh": kept,
            "max_age_days": max_age_days}


def factory_run(max_age_days: int = 21) -> dict:
    """Continuous-factory daily cron entry:
      1. drop dead videos (any age)
      2. drop entries > max_age_days old (force refresh of pinned picks)
      3. resolve any missing — newly-added activities + replacements
    """
    log.info("factory_run starting (max_age_days=%d)", max_age_days)
    rev = revalidate_cache()
    stale = refresh_stale(max_age_days=max_age_days)
    res = resolve_all(force=False)
    summary = {"revalidate": rev, "refresh_stale": stale, "resolve": res}
    log.info("factory_run done: %s", summary)
    return summary


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        if len(sys.argv) > 2:
            aid = sys.argv[2]
            a = act_mod.by_id(aid)
            if not a: print(f"unknown: {aid}"); sys.exit(1)
            print(json.dumps(resolve_video(a), indent=2, default=str))
        else:
            print(json.dumps(resolve_all(force="--force" in sys.argv), indent=2))
    elif cmd == "revalidate":
        print(json.dumps(revalidate_cache(), indent=2))
    elif cmd == "factory":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 21
        print(json.dumps(factory_run(max_age_days=days), indent=2, default=str))
    elif cmd == "refresh-stale":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 21
        print(json.dumps(refresh_stale(max_age_days=days), indent=2))
    elif cmd == "list":
        for r in all_cached():
            print(f"  {r['activity_id']:30s} {r.get('author_name','')[:30]:30s} {r.get('title','')[:60]}")
    else:
        print(f"unknown: {cmd}"); sys.exit(1)


if __name__ == "__main__":
    main()
