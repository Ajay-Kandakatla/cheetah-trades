"""Weekly grocery roll-up — projects 7 days of menus into a shopping list.

Strategy:
  - Look at last 7 days of cooked menus (proxy for a typical week).
  - For each cooked recipe, sum its ingredients.
  - Group by category: vegetables / meat / dairy / pantry / spices.
  - Subtract pantry-stocked items (rice, dal, ghee, spices) so the list
    surfaces only what needs buying THIS week.

Returns a structured list grouped by category, plus prep notes.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta

from . import recipes as rec_mod, store

log = logging.getLogger("food.grocery")


def _today_iso() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def _projected_recipes(user_email: str, days: int = 7) -> list[dict]:
    """Return the list of recipe dicts to roll up.

    Strategy: take last 7 days of actually-cooked recipes (the most accurate
    forecast) and add today's planner suggestions on top so the list reflects
    the WEEK YOU'RE COOKING, not just the last week.
    """
    out: list[dict] = []
    rows = store.history(user_email, days=days)
    today = date.fromisoformat(_today_iso())
    cutoff = (today - timedelta(days=days)).isoformat()
    for r in rows:
        if r.get("date_et", "") < cutoff:
            continue
        for rid in r.get("recipe_ids") or []:
            recipe = rec_mod.by_id(rid)
            if recipe:
                out.append(recipe)

    # Augment with today's option-A so the list always has SOMETHING even
    # for new users with empty history.
    if not out:
        from . import planner
        suggestion = planner.suggest_today(user_email)
        opt = (suggestion.get("options") or [{}])[0]
        for slot in ["adult_breakfast", "kid_breakfast"]:
            for r in opt.get(slot) or []:
                out.append(r)
        d = opt.get("dinner") or {}
        for key in ["main", "side", "charu"]:
            for r in d.get(key) or []:
                out.append(r)
    return out


def weekly_grocery(user_email: str) -> dict:
    """Build this week's grocery list.

    Output:
      {
        "week_start":   "2026-05-08",
        "n_recipes":    12,
        "categories": {
          "vegetables": [{"item":..., "qty":..., "unit":..., "from": [...]}],
          "meat":       [...],
          "dairy":      [...],
          "pantry":     [...],
          "spices":     [...],
        },
        "in_pantry":     [list of items skipped because already on hand],
        "weekly_recurring": [shopping reminders the user does each week],
        "bulk_reminders": [{"item": "rice", "next_buy_in_days": ...}],
      }
    """
    pantry = store.get_pantry(user_email)
    recipes_to_roll = _projected_recipes(user_email)

    # Aggregate ingredients
    raw: dict[tuple, dict] = {}   # (category, item, unit) -> aggregate row
    for r in recipes_to_roll:
        for ing in (r.get("ingredients") or []):
            key = (ing["category"], ing["item"].lower(), ing.get("unit", ""))
            row = raw.setdefault(key, {
                "item":      ing["item"],
                "category":  ing["category"],
                "unit":      ing.get("unit", ""),
                "qty":       0,
                "from":      [],
            })
            try:
                row["qty"] += float(ing.get("qty") or 0)
            except (TypeError, ValueError):
                # Some quantities are non-numeric (e.g. "1 small bunch") —
                # we still count occurrences for visibility.
                row["qty"] += 1
            row["from"].append(r["name"])

    # Filter out pantry-stocked items where the user already has bulk supply.
    in_pantry: list[str] = []
    final: dict[str, list[dict]] = defaultdict(list)
    for (cat, item_lower, unit), row in raw.items():
        if _is_in_pantry(item_lower, pantry):
            in_pantry.append(row["item"])
            continue
        # Round quantities to a sane precision for display
        row["qty"] = round(float(row["qty"]), 1) if isinstance(row["qty"], (int, float)) else row["qty"]
        # Dedupe the "from" list while preserving order
        seen = set()
        row["from"] = [n for n in row["from"] if not (n in seen or seen.add(n))]
        final[cat].append(row)

    # Sort each category alphabetically
    for cat in final:
        final[cat].sort(key=lambda r: r["item"].lower())

    bulk_reminders = _bulk_reminders(pantry)

    return {
        "week_start":         _today_iso(),
        "n_recipes":          len(recipes_to_roll),
        "categories":         dict(final),
        "in_pantry":          sorted(set(in_pantry)),
        "weekly_recurring":   [
            "Idli/dosa batter (fresh weekly)",
            "Curd/yogurt (gallon)",
            "Cilantro + curry leaves",
            "Lemons + green chilies",
            "Bananas (kid)",
        ],
        "bulk_reminders":     bulk_reminders,
    }


def _is_in_pantry(item_lower: str, pantry: dict) -> bool:
    """Return True when this ingredient is covered by what the user buys
    in bulk (rice, dal, spices, ghee, etc.)."""
    if pantry.get("rice_kg", 0) > 0 and "rice" in item_lower:
        # Skip "basmati rice" line items — buyer already has bulk rice
        return True
    if "toor dal" in item_lower and pantry.get("toor_dal_kg", 0) > 0:
        return True
    if "moong dal" in item_lower and pantry.get("moong_dal_kg", 0) > 0:
        return True
    if pantry.get("spices_stocked"):
        if any(s in item_lower for s in [
            "garam masala", "chili powder", "turmeric", "cumin",
            "mustard seeds", "fenugreek seeds", "pepper", "saffron",
            "sesame seeds",
        ]):
            return True
    if pantry.get("tamarind") and "tamarind" in item_lower:
        return True
    if pantry.get("jaggery") and "jaggery" in item_lower:
        return True
    if pantry.get("ghee") and "ghee" in item_lower:
        return True
    return False


def _bulk_reminders(pantry: dict) -> list[dict]:
    """Project when bulk staples need rebuying. Rice every ~60 days etc."""
    reminders: list[dict] = []
    if pantry.get("rice_kg", 0) <= 5:
        reminders.append({"item": "Rice (bulk)", "msg": "Running low — order next 20kg bag"})
    return reminders
