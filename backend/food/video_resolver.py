"""Validated YouTube video resolver — finds + validates a real, currently-live
video for each recipe using Gemma (local LLM via LM Studio) + YouTube
scraping + oEmbed validation.

Pipeline per recipe:
  1. LLM crafts an optimal YouTube search query
     (e.g. "Hyderabadi Bagara Baingan recipe Sanjay Thumma vahchef")
  2. Scrape YouTube search results HTML → extract video IDs from
     ytInitialData JSON
  3. Validate each via oEmbed (free, no API key) — keeps only live ones
  4. LLM picks the best candidate by title + channel; biases toward
     trusted channels (Vismai Food, VahChef, Amma Chethi Vanta,
     Hebbar's Kitchen, Indian Healthy Recipes)
  5. Cache the winner in Mongo `food_video_cache`

CLI:
  python -m food.video_resolver run        # resolve all recipes
  python -m food.video_resolver run NAME   # one recipe by id
  python -m food.video_resolver revalidate # re-check cached videos
                                            #   (drop dead ones for re-resolve)
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
from food import recipes as recipes_mod

log = logging.getLogger("food.video_resolver")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")

TRUSTED_CHANNELS = [
    "Vismai Food",
    "VahChef",
    "Vahrehvah",
    "Amma Chethi Vanta",
    "Hebbar's Kitchen",
    "Indian Healthy Recipes",
    "Swasthi's Recipes",
    "Yummy Indian Kitchen",
    "Madhura's Recipe",
    "Show Me The Curry",
    "Ranveer Brar",
]


# ---------------------------------------------------------------------------
# Mongo cache
# ---------------------------------------------------------------------------
def _coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        coll = client[os.getenv("MONGO_DB", "cheetah")].food_video_cache
        coll.create_index([("recipe_id", ASCENDING)], unique=True)
        return coll
    except Exception as exc:
        log.warning("video_cache mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def get_cached(recipe_id: str) -> Optional[dict]:
    c = _coll()
    if c is None: return None
    doc = c.find_one({"recipe_id": recipe_id})
    if doc:
        doc.pop("_id", None)
    return doc


def put_cached(recipe_id: str, payload: dict) -> None:
    c = _coll()
    if c is None: return
    c.update_one(
        {"recipe_id": recipe_id},
        {"$set": {**payload, "recipe_id": recipe_id, "validated_at": _now()}},
        upsert=True,
    )


def all_cached() -> list[dict]:
    c = _coll()
    if c is None: return []
    rows = list(c.find({}))
    for r in rows: r.pop("_id", None)
    return rows


# ---------------------------------------------------------------------------
# YouTube oEmbed validation (free, no API key, returns 200 only when live)
# ---------------------------------------------------------------------------
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
    """Return title + author when video is live, else None."""
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


# ---------------------------------------------------------------------------
# YouTube search scrape — extract video IDs from search results HTML
# ---------------------------------------------------------------------------
def search_youtube(query: str, *, max_results: int = 10) -> list[str]:
    """Scrape the YouTube search results page for video IDs.

    YouTube embeds search results in a `ytInitialData` JSON blob inside a
    `<script>` tag. We find that blob and pull video IDs from it. Returns
    up to `max_results` ordered by YouTube's relevance ranking.
    """
    try:
        url = "https://www.youtube.com/results"
        r = requests.get(
            url,
            params={"search_query": query, "hl": "en"},
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
            timeout=15,
        )
        if r.status_code != 200:
            log.warning("YouTube search %s returned %d", query[:60], r.status_code)
            return []
        html = r.text
    except Exception as exc:
        log.warning("YouTube search failed for %s: %s", query[:60], exc)
        return []

    # The page has many "videoId":"<11chars>" occurrences. Some are dupes
    # (search results, recommendations, related). Take the first N unique.
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


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------
def craft_search_query(recipe: dict) -> str:
    """Ask Gemma to write the best YouTube search query for this recipe."""
    if not llm_enabled():
        return f"{recipe['name']} recipe {recipe.get('cuisine', '')}"

    sys_prompt = (
        "You write YouTube search queries for Indian cooking recipes. "
        "Pick a query that returns a high-quality, authentic walkthrough. "
        "Bias toward trusted channels: Vismai Food, VahChef, Amma Chethi Vanta, "
        "Hebbar's Kitchen, Indian Healthy Recipes. Keep the query under 12 words. "
        "Return ONLY the query, no quotes, no explanation."
    )
    user_prompt = (
        f"Recipe: {recipe['name']}\n"
        f"Cuisine: {recipe.get('cuisine', 'indian')}\n"
        f"Tags: {', '.join(recipe.get('tags', []))}\n"
        f"Protein: {recipe.get('protein', '')}\n\n"
        "Write the YouTube search query."
    )
    res = llm_chat(user_prompt, system=sys_prompt, max_tokens=80, temperature=0.3, timeout=30)
    if res.get("ok") and res.get("text"):
        q = res["text"].strip().strip('"').splitlines()[0].strip()
        # Sanity-fence: if Gemma returned nothing useful, fall back.
        if 5 < len(q) < 200:
            return q
    return f"{recipe['name']} recipe {recipe.get('cuisine', '')}"


def pick_best_candidate(recipe: dict, candidates: list[dict]) -> Optional[dict]:
    """Ask Gemma to pick the best candidate. Each candidate has
    {video_id, title, author_name}.

    Returns the winning candidate dict augmented with `llm_reason`.
    Falls back to the first candidate if LLM is unavailable or its
    response is unparseable.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        c = dict(candidates[0])
        c["llm_reason"] = "only candidate"
        return c
    if not llm_enabled():
        c = dict(candidates[0])
        c["llm_reason"] = "LLM disabled — picked top YouTube ranking"
        return c

    sys_prompt = (
        "You judge which YouTube cooking video best teaches a specific Indian "
        "recipe. Prefer authentic walkthroughs from trusted channels: "
        f"{', '.join(TRUSTED_CHANNELS)}. Penalize compilation videos, ads, "
        "shorts under 1 min, and unrelated dishes (e.g. 'mutton biryani' for "
        "'mutton paya' is wrong). Reply with JSON only: "
        '{"choice_index": <int>, "reason": "<one short sentence>"}'
    )
    cand_lines = []
    for i, c in enumerate(candidates):
        cand_lines.append(
            f"  [{i}] title=\"{c.get('title','')}\" channel=\"{c.get('author_name','')}\""
        )
    user_prompt = (
        f"Recipe: {recipe['name']} (cuisine: {recipe.get('cuisine')}).\n\n"
        "Candidates:\n" + "\n".join(cand_lines)
    )
    res = llm_chat(user_prompt, system=sys_prompt, max_tokens=200,
                   temperature=0.2, json_only=True, timeout=45)
    parsed = (res.get("parsed") or {}) if res.get("ok") else {}
    idx = parsed.get("choice_index")
    reason = parsed.get("reason") or "LLM judged"
    if isinstance(idx, int) and 0 <= idx < len(candidates):
        c = dict(candidates[idx])
        c["llm_reason"] = reason
        return c
    # Fallback — first candidate
    c = dict(candidates[0])
    c["llm_reason"] = "LLM response unparseable — picked top YouTube ranking"
    return c


# ---------------------------------------------------------------------------
# Per-recipe resolver
# ---------------------------------------------------------------------------
def resolve_video(recipe: dict, *, max_candidates: int = 8) -> Optional[dict]:
    """Run the full pipeline for one recipe. Returns the cached payload or
    None if no live videos were found.

    Cached payload shape:
      {
        "recipe_id":   ...,
        "video_id":    "abc...",
        "video_url":   "https://www.youtube.com/watch?v=...",
        "title":       ...,
        "author_name": ...,
        "thumbnail":   "...",
        "search_query":  "...",   # what we asked YouTube
        "candidates_seen": N,
        "candidates_live": M,
        "llm_reason":  "...",
        "validated_at": <epoch>,
      }
    """
    rid = recipe["id"]
    log.info("[%s] starting resolve…", rid)

    # 1. Craft query
    query = craft_search_query(recipe)
    log.info("[%s] query=\"%s\"", rid, query)

    # 2. Scrape search results
    video_ids = search_youtube(query, max_results=max_candidates * 2)
    if not video_ids:
        log.warning("[%s] no candidates from YouTube search", rid)
        return None

    # 3. Validate each via oEmbed (parallel)
    live_candidates: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for vid, meta in zip(video_ids, ex.map(oembed_metadata, video_ids[:max_candidates*2])):
            if meta is None:
                continue
            live_candidates.append({"video_id": vid, **meta})
            if len(live_candidates) >= max_candidates:
                break

    log.info("[%s] %d/%d candidates live", rid, len(live_candidates), len(video_ids))
    if not live_candidates:
        return None

    # 4. LLM pick
    pick = pick_best_candidate(recipe, live_candidates)
    if pick is None:
        return None

    # 5. Build payload + cache
    payload = {
        "recipe_id":       rid,
        "video_id":        pick["video_id"],
        "video_url":       f"https://www.youtube.com/watch?v={pick['video_id']}",
        "title":           pick.get("title"),
        "author_name":     pick.get("author_name"),
        "author_url":      pick.get("author_url"),
        "thumbnail":       pick.get("thumbnail_url"),
        "search_query":    query,
        "candidates_seen": len(video_ids),
        "candidates_live": len(live_candidates),
        "llm_reason":      pick.get("llm_reason"),
    }
    put_cached(rid, payload)
    log.info("[%s] ✓ %s · %s", rid, pick.get("author_name"), (pick.get("title") or "")[:80])
    return payload


# ---------------------------------------------------------------------------
# Bulk runner
# ---------------------------------------------------------------------------
def resolve_all(force: bool = False, sleep_between: float = 0.5) -> dict:
    """Resolve videos for every recipe. Skips ones already cached unless
    force=True. Sleeps a bit between recipes to be polite to YouTube."""
    out = {"resolved": 0, "skipped": 0, "failed": 0, "details": []}
    for recipe in recipes_mod.RECIPES:
        rid = recipe["id"]
        if not force and get_cached(rid):
            out["skipped"] += 1
            continue
        try:
            res = resolve_video(recipe)
            if res:
                out["resolved"] += 1
                out["details"].append({"id": rid, "ok": True,
                                        "video_id": res["video_id"],
                                        "channel": res["author_name"]})
            else:
                out["failed"] += 1
                out["details"].append({"id": rid, "ok": False, "reason": "no live candidates"})
        except Exception as exc:
            out["failed"] += 1
            out["details"].append({"id": rid, "ok": False, "reason": str(exc)})
            log.exception("[%s] resolve failed", rid)
        time.sleep(sleep_between)
    return out


def revalidate_cache() -> dict:
    """For each cached entry, re-check the video is still live via oEmbed.
    Drop dead ones so the next resolve_all pass picks fresh candidates."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "mongo unavailable"}
    rows = list(coll.find({}))
    dead = 0
    for r in rows:
        vid = r.get("video_id")
        if not vid:
            continue
        if not is_video_live(vid):
            coll.delete_one({"recipe_id": r["recipe_id"]})
            dead += 1
            log.info("revalidate: dropped dead %s (%s)", r["recipe_id"], vid)
    return {"ok": True, "checked": len(rows), "dropped_dead": dead}


def refresh_stale(max_age_days: int = 21) -> dict:
    """Re-resolve cache entries older than `max_age_days`. Drops them
    from cache so the next resolve_all pass finds CURRENT best videos
    via fresh YouTube search + Gemma judging — even when the existing
    pinned video is still alive.

    Combined with daily revalidate + resolve_all(), this gives a true
    continuous factory:
      - Daily: drop dead → re-resolve replacements + new recipes
      - Every 21d (per-entry): drop stale → find newer/better content

    Returns counts of {checked, dropped_stale, kept_fresh}.
    """
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "mongo unavailable"}
    cutoff = _now() - max_age_days * 86400
    rows = list(coll.find({}))
    stale = kept = 0
    for r in rows:
        validated_at = r.get("validated_at") or 0
        if validated_at < cutoff:
            coll.delete_one({"recipe_id": r["recipe_id"]})
            stale += 1
            log.info("refresh_stale: dropped %s (age %dd > %dd)",
                     r["recipe_id"],
                     (_now() - validated_at) // 86400 if validated_at else 999,
                     max_age_days)
        else:
            kept += 1
    return {"ok": True, "checked": len(rows),
            "dropped_stale": stale, "kept_fresh": kept,
            "max_age_days": max_age_days}


def factory_run(max_age_days: int = 21) -> dict:
    """Single-call continuous-factory pipeline. Designed for daily cron:

      1. revalidate_cache()  — drop dead videos (any age)
      2. refresh_stale(N)    — drop entries > N days old (find newer picks)
      3. resolve_all()       — fill in everything missing (new recipes too)

    Idempotent — running it more than once a day is fine but wasteful.
    """
    log.info("factory_run starting (max_age_days=%d)", max_age_days)
    rev = revalidate_cache()
    stale = refresh_stale(max_age_days=max_age_days)
    res = resolve_all(force=False)
    summary = {
        "revalidate":  rev,
        "refresh_stale": stale,
        "resolve":     res,
    }
    log.info("factory_run done: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        if len(sys.argv) > 2:
            rid = sys.argv[2]
            r = recipes_mod.by_id(rid)
            if not r:
                print(f"unknown recipe: {rid}")
                sys.exit(1)
            res = resolve_video(r)
            print(json.dumps(res, indent=2, default=str))
        else:
            force = "--force" in sys.argv
            res = resolve_all(force=force)
            print(json.dumps({"resolved": res["resolved"], "skipped": res["skipped"],
                              "failed": res["failed"]}, indent=2))
    elif cmd == "revalidate":
        print(json.dumps(revalidate_cache(), indent=2))
    elif cmd == "factory":
        # Continuous-factory cron entry: drop dead + drop stale + fill missing
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 21
        print(json.dumps(factory_run(max_age_days=days), indent=2, default=str))
    elif cmd == "refresh-stale":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 21
        print(json.dumps(refresh_stale(max_age_days=days), indent=2))
    elif cmd == "list":
        for r in all_cached():
            print(f"  {r['recipe_id']:40s} {r.get('author_name', '')[:30]:30s} {r.get('title','')[:60]}")
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
