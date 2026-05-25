"""Daily meal planner — picks 2 options per slot avoiding recent repeats.

Slots:
  - adult_breakfast — for Ajay + wife
  - kid_breakfast   — for the 3.5y old (probiotic-leaning, mild)
  - dinner          — main + side curry + charu (always); becomes next-day lunch

Ranking heuristics per slot (higher score wins):
  +100  base
  -200  cooked in last 7 days (cooldown — soft block)
  -50   cooked in last 14 days (mild penalty)
  +30   iron_rich AND we haven't had iron-rich in last 3 days (wife focus)
  +20   probiotic AND kid breakfast slot (daughter focus)
  +25   protein the family hasn't had in 5+ days (variety)
  +15   recipe matches the user's cuisine bias (telangana > andhra > others)
  -100  is_weekend AND today is Mon-Thu (saves paya/biryani for weekends)
  -150  shrimp/fish if cooldown not met (per-protein freq guards)
  +rng  small jitter so two runs aren't identical
"""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, timezone
from typing import Optional

from . import recipes as rec_mod, store

log = logging.getLogger("food.planner")


def _today_iso() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def _is_weekend() -> bool:
    """Saturday / Sunday in ET = weekend window where paya, biryani belong."""
    try:
        from zoneinfo import ZoneInfo
        d = datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        d = datetime.now(timezone.utc).date()
    return d.weekday() >= 5


# ---------------------------------------------------------------------------
# Scoring per recipe
# ---------------------------------------------------------------------------
def _score_recipe(*, recipe: dict, user_email: str, slot: str,
                  recent_iron_rich_count: int, recent_proteins: dict,
                  prefs: dict, last_seen: Optional[int]) -> tuple[float, list[str]]:
    """Return (score, reason_strings)."""
    score = 100.0
    reasons: list[str] = []

    # Cooldowns
    if last_seen is not None and last_seen <= 7:
        score -= 200
        reasons.append(f"in 7-day cooldown ({last_seen}d ago)")
    elif last_seen is not None and last_seen <= 14:
        score -= 50
        reasons.append(f"recent ({last_seen}d ago)")

    # Iron focus — wife's deficiency. Bias toward iron-rich during weeks
    # we haven't hit the iron_focus_days threshold yet.
    if recipe.get("iron_rich") and recent_iron_rich_count < prefs.get("iron_focus_days", 3):
        score += 30
        reasons.append("iron-rich (wife)")

    # Probiotic priority for kid breakfast
    if slot == "kid_breakfast" and recipe.get("probiotic") and prefs.get("kid_probiotic_priority"):
        score += 25
        reasons.append("probiotic (kid)")

    # Citrus boost for charus on iron-light days (citrus + iron together
    # boosts iron absorption — vitamin C effect)
    if recipe.get("type") == "rasam" and recipe.get("citrus") and recent_iron_rich_count < 2:
        score += 10
        reasons.append("citrus boost (iron absorption)")

    # Protein variety (mains only)
    p = recipe.get("protein")
    if recipe.get("type") == "main_curry" and p:
        last_p_days = recent_proteins.get(p)
        if last_p_days is None or last_p_days >= 5:
            score += 25
            reasons.append("protein variety")
        elif last_p_days <= 1:
            score -= 30
            reasons.append("same protein yesterday")

    # Cuisine bias — Telangana > Andhra > others (per Ajay's brief)
    cuisine = recipe.get("cuisine", "")
    if cuisine == "telangana":
        score += 15 * float(prefs.get("telangana_bias", 0.7))
        reasons.append("telangana")
    elif cuisine == "andhra":
        score += 15 * float(prefs.get("andhra_bias", 0.2))
        reasons.append("andhra")

    # Weekend gating — paya, biryani saved for Saturday/Sunday
    if recipe.get("weekend") and not _is_weekend():
        score -= 100
        reasons.append("weekend dish on weekday")

    # Quick-cook bias on weekdays — slow braises and labor-intensive
    # dishes like methi paratha only belong on weekends. Bonus for quick
    # dishes Mon-Thu.
    if not _is_weekend():
        if recipe.get("quick"):
            score += 18
            reasons.append("quick (weeknight)")
        elif recipe.get("prep_min") and recipe["prep_min"] >= 60:
            score -= 25
            reasons.append("slow (>60min on a weeknight)")

    # Per-protein frequency guards
    if p == "fish":
        # "fish" protein covers both fish AND shrimp here. Differentiate
        # via tag.
        is_shrimp = "seafood" in (recipe.get("tags") or [])
        if is_shrimp:
            min_gap = prefs.get("shrimp_freq_days", 14)
            if last_seen is not None and last_seen < min_gap:
                score -= 150
                reasons.append(f"shrimp cooldown ({min_gap}d)")
        else:
            min_gap = prefs.get("fish_freq_days", 7)
            if last_seen is not None and last_seen < min_gap:
                score -= 80
                reasons.append(f"fish cooldown ({min_gap}d)")

    # Small jitter so two runs aren't identical
    score += random.uniform(-3, 3)

    return score, reasons


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _gather_recent(user_email: str, days: int = 14) -> tuple[int, dict]:
    """Return (recent_iron_rich_count_in_last_7d, {protein: days_since_last})."""
    iron_count = 0
    proteins: dict[str, int] = {}
    today = date.fromisoformat(_today_iso())

    rows = store.history(user_email, days=days)
    for r in rows:
        ds = (today - date.fromisoformat(r["date_et"])).days
        for rid in r.get("recipe_ids") or []:
            recipe = rec_mod.by_id(rid)
            if not recipe: continue
            if recipe.get("iron_rich") and ds <= 7:
                iron_count += 1
            p = recipe.get("protein")
            if p and (p not in proteins or proteins[p] > ds):
                proteins[p] = ds
    return iron_count, proteins


def _pick_top_n(*, candidates: list[dict], user_email: str, slot: str,
                n: int, prefs: dict) -> list[dict]:
    """Score every candidate and return the top-N.

    Returns enriched dicts with `_score` and `_reasons` fields so the UI can
    explain *why* this dish was suggested today. Also attaches a
    `validated_video` block when one is cached in food_video_cache, so the
    frontend can show a real, live-checked YouTube link instead of a
    fragile guessed URL.
    """
    from food import video_resolver as _vr

    iron_count, recent_proteins = _gather_recent(user_email)
    scored: list[tuple[float, dict, list[str]]] = []
    for r in candidates:
        last_seen = store.days_since_last(user_email, r["id"])
        score, reasons = _score_recipe(
            recipe=r, user_email=user_email, slot=slot,
            recent_iron_rich_count=iron_count,
            recent_proteins=recent_proteins,
            prefs=prefs, last_seen=last_seen,
        )
        scored.append((score, r, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict] = []
    for s, r, reasons in scored[:n]:
        item = dict(r)
        item["_score"] = round(s, 1)
        item["_reasons"] = reasons
        cached = _vr.get_cached(r["id"])
        if cached:
            # Slim down — frontend only needs the visible bits.
            item["validated_video"] = {
                "video_id":    cached.get("video_id"),
                "video_url":   cached.get("video_url"),
                "title":       cached.get("title"),
                "author_name": cached.get("author_name"),
                "author_url":  cached.get("author_url"),
                "thumbnail":   cached.get("thumbnail"),
                "validated_at":cached.get("validated_at"),
            }
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Top-level: today's two menus
# ---------------------------------------------------------------------------
def suggest_today(user_email: str, quick_only: bool = False) -> dict:
    """Generate two menu options for today's slots.

    Args:
      quick_only: when True, hard-filter to only quick-cook recipes
                  (≤30min prep, no heavy effort). Use this on tired
                  weeknights when methi paratha is too much.

    Output:
      {
        "date_et":   "2026-05-08",
        "is_weekend": bool,
        "options": [
          {
            "label": "Option 1",
            "adult_breakfast": [recipe...],
            "kid_breakfast":   [recipe...],
            "dinner": {
              "main":    [recipe...],
              "side":    [recipe...],
              "charu":   [recipe...],   # always populated — every meal has a charu
            },
            "iron_total_mg":   sum across the day's iron items,
          },
          { "label": "Option 2", ... }
        ],
        "kid_breakfast_options":    [recipe, recipe, recipe],   # 3 fresh options
        "history_summary": {
          "recent_iron_count":   N,
          "recent_proteins":     {...},
        },
      }
    """
    prefs = store.get_preferences(user_email)

    iron_count, recent_proteins = _gather_recent(user_email)

    # Build two distinct candidate pools — pull 4 of each so option 1 and
    # option 2 don't repeat the same dish.
    # Adult breakfast pool: pulls from breakfast_adult AND breakfast_either
    # (idli/dosa/uttapam/rava idli/plain dosa work for adults too — family
    # eats the same thing). Kid pool: breakfast_kid + breakfast_either.
    adult_candidates = (
        rec_mod.filter_recipes(t="breakfast_adult",  quick_only=quick_only)
        + rec_mod.filter_recipes(t="breakfast_either", quick_only=quick_only)
    )
    kid_candidates = (
        rec_mod.filter_recipes(t="breakfast_kid",    quick_only=quick_only)
        + rec_mod.filter_recipes(t="breakfast_either", quick_only=quick_only)
    )
    breakfast_pool = _pick_top_n(
        candidates=adult_candidates,
        user_email=user_email, slot="adult_breakfast",
        n=4, prefs=prefs,
    )
    kid_pool = _pick_top_n(
        candidates=kid_candidates,
        user_email=user_email, slot="kid_breakfast",
        n=3, prefs=prefs,
    )
    main_pool = _pick_top_n(
        candidates=rec_mod.filter_recipes(t="main_curry", quick_only=quick_only),
        user_email=user_email, slot="dinner",
        n=4, prefs=prefs,
    )
    side_pool = _pick_top_n(
        candidates=rec_mod.filter_recipes(t="side_curry", quick_only=quick_only),
        user_email=user_email, slot="dinner",
        n=4, prefs=prefs,
    )
    charu_pool = _pick_top_n(
        candidates=rec_mod.filter_recipes(t="rasam", quick_only=quick_only),
        user_email=user_email, slot="dinner",
        n=4, prefs=prefs,
    )
    # Daily protein add-on — air-fried pre-marinated meat / paneer / eggs.
    # Always one per dinner so there's protein on the table even when the
    # main is vegetarian (chana, rajma, paneer-only days etc.).
    protein_side_pool = _pick_top_n(
        candidates=rec_mod.filter_recipes(t="protein_side", quick_only=False),
        user_email=user_email, slot="dinner",
        n=4, prefs=prefs,
    )

    # Pick two MAIN dishes with DIFFERENT proteins so option A and option B
    # don't both serve mutton, or both shrimp, etc. Walk the sorted pool
    # picking the first 2 with distinct primary proteins.
    seen_proteins: set[str] = set()
    distinct_mains: list[dict] = []
    for r in main_pool:
        p = r.get("protein")
        if p in seen_proteins:
            continue
        seen_proteins.add(p)
        distinct_mains.append(r)
        if len(distinct_mains) >= 2:
            break
    # Fallback: if filter left us with <2 distinct mains, top-up with
    # whatever's left in score order even if same protein.
    while len(distinct_mains) < 2 and len(distinct_mains) < len(main_pool):
        for r in main_pool:
            if r not in distinct_mains:
                distinct_mains.append(r)
                break

    # Compose two options. Take alternating entries so option 1 and option 2
    # have meaningfully different profiles (e.g. one is mutton, the other
    # is paneer; one breakfast is acai bowl, the other is pesarattu).
    def _opt(idx: int, label: str) -> dict:
        bk = [breakfast_pool[idx]] if idx < len(breakfast_pool) else []
        # If the user wants a second adult-breakfast for the day, slot in
        # one (e.g., wife eats acai/oats while husband eats egg whites).
        if idx + 2 < len(breakfast_pool):
            bk.append(breakfast_pool[idx + 2])
        elif idx + 1 < len(breakfast_pool):
            bk.append(breakfast_pool[idx + 1])

        main = [distinct_mains[idx]] if idx < len(distinct_mains) else []
        side = [side_pool[idx]] if idx < len(side_pool) else []
        # Always pair a charu with dinner
        charu = [charu_pool[idx]] if idx < len(charu_pool) else []
        # Daily protein add-on — skip if main is already a meaty protein,
        # otherwise always include to satisfy the "protein every day" rule.
        protein_side: list[dict] = []
        main_is_meat = bool(main and (main[0].get("protein") in ("chicken", "goat", "fish")))
        if not main_is_meat and idx < len(protein_side_pool):
            protein_side = [protein_side_pool[idx]]

        # Iron total — sum iron_mg across everything served that day for
        # this option (incl kid breakfast since the family eats together)
        all_today = list(bk) + list(main) + list(side) + list(charu) + list(protein_side)
        iron_total = round(sum((r.get("iron_mg") or 0) for r in all_today), 1)

        return {
            "label":           label,
            "adult_breakfast": bk,
            "kid_breakfast":   [kid_pool[idx]] if idx < len(kid_pool) else [],
            "dinner": {
                "main":          main,
                "side":          side,
                "charu":         charu,
                "protein_side":  protein_side,
            },
            "iron_total_mg":   iron_total,
        }

    # Weekend extras — eat-out / buffet picks. Family goes out on
    # weekends, so offer a 3rd "skip cooking" option alongside the two
    # home-cook menus.
    eat_out: list[dict] = []
    if _is_weekend():
        try:
            from food import eat_out as _eo
            eat_out = _eo.picks_for_today(n=5)
        except Exception:
            eat_out = []

    return {
        "date_et":     _today_iso(),
        "is_weekend":  _is_weekend(),
        "options":     [_opt(0, "Option A"), _opt(1, "Option B")],
        "kid_breakfast_options": kid_pool,
        "eat_out":     eat_out,
        "history_summary": {
            "recent_iron_count":  iron_count,
            "recent_proteins":    recent_proteins,
            "iron_focus_target":  prefs.get("iron_focus_days", 3),
        },
    }
