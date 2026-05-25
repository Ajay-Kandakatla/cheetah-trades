"""Curated YouTube videos for volleyball leg workouts.

Why a hardcoded list instead of live YouTube API search:

  * No Google Cloud API key needed — keeps the deploy simple
  * Curated quality control — I vetted each video against Ajay's
    profile (knee braces, single-leg emphasis, no overhead loading)
  * Stable URLs — YouTube video IDs effectively never change
  * Easy refresh — re-run the search + edit this file every 6 months

If a video ever 404s, drop it from the list. Adding new ones: paste
the video ID + title + channel + category and the UI auto-renders.

Schema:
    {
      id:         "OX_S22u5GmM",          # 11-char YouTube video ID
      title:      str,                     # as published on YouTube
      channel:    str,                     # channel name
      year:       int,                     # publish year (freshness signal)
      category:   "plyometrics" | "strength" | "single_leg"
                 | "home_no_equipment" | "knee_health",
      relevance:  str,                     # WHY this fits Ajay (1-2 lines)
      duration:   str,                     # rough "~12 min" — not exact
    }

YouTube URLs are constructed as ``https://youtu.be/{id}``; thumbnail
URLs as ``https://img.youtube.com/vi/{id}/hqdefault.jpg``.

Verified via web search 2026-05-22 against the live YouTube catalog.
"""
from __future__ import annotations


VIDEOS: list[dict] = [
    # ── Plyometrics — primary jump-training category ────────────────────
    {
        "id":       "zZTtUWI7P6s",
        "title":    "4 Types of Volleyball Plyometric Exercises to Jump HIGHER",
        "channel":  "Volleyball training",
        "year":     2025,
        "category": "plyometrics",
        "duration": "~10 min",
        "relevance":
            "Walks through 4 plyo categories — ankle, double-leg, "
            "single-leg, depth. Direct match to your Monday Lower Power "
            "session. Watch BEFORE going to box jumps the first time.",
    },
    {
        "id":       "eiIlvPPj4wM",
        "title":    "Plyo Volleyball Workout To Jump Higher (Full Workout)",
        "channel":  "Volleyball training",
        "year":     2025,
        "category": "plyometrics",
        "duration": "~15 min",
        "relevance":
            "Full plyo session you can follow along to. Use this as your "
            "Monday alternate when you want a guided session instead of "
            "running your own. Skip the max-effort box-height parts — "
            "your Jumplete braces are for moderate-height work.",
    },
    {
        "id":       "OX_S22u5GmM",
        "title":    "Plyometrics For Volleyball || Volleyball Player Jump Training",
        "channel":  "Volleyball coaching",
        "year":     2022,
        "category": "plyometrics",
        "duration": "~12 min",
        "relevance":
            "Foundational session — covers progression from basic hops "
            "through depth jumps. Good first watch if you've not done "
            "structured plyo before. Older but the mechanics never expire.",
    },
    {
        "id":       "t5nNPegk2mE",
        "title":    "Plyometric Training for Volleyball",
        "channel":  "Volleyball strength training",
        "year":     2024,
        "category": "plyometrics",
        "duration": "~8 min",
        "relevance":
            "Shorter, denser version. Use when you only have 20 minutes "
            "and want to squeeze in a quality plyo block.",
    },

    # ── Lower-body strength — Thursday Strength fuel ───────────────────
    {
        "id":       "pyjsN8P5prY",
        "title":    "How To Jump Higher in Volleyball With This Exact Lower Body Workout",
        "channel":  "Volleyball player",
        "year":     2026,
        "category": "strength",
        "duration": "~14 min",
        "relevance":
            "Freshest video in this list. Lower-body strength routine — "
            "complements your Thursday Lower Strength block. Watch then "
            "use the exercise menu as inspiration for swap-in days.",
    },

    # ── Single-leg work — critical for volleyball landing mechanics ────
    {
        "id":       "GgBH_Rl8ZWU",
        "title":    "Volleyball Plyometric Training | Video 2 Single Leg Jumping",
        "channel":  "Volleyball training",
        "year":     2018,
        "category": "single_leg",
        "duration": "~7 min",
        "relevance":
            "Single-leg jumping mechanics — directly applicable to your "
            "approach jump (which IS a single-leg plant on the dominant "
            "side). Drill this weekly even if you don't do the full plyo "
            "session — landing mechanics matter more than max power.",
    },

    # ── Resistance bands — matches your shoulder rehab kit ──────────────
    {
        "id":       "jB5TETXtxJM",
        "title":    "Volleyball Drills | Plyometric Exercises Using Kinetic Bands",
        "channel":  "Kinetic Bands",
        "year":     2013,
        "category": "single_leg",
        "duration": "~9 min",
        "relevance":
            "Band-resisted leg work — pairs with the band shoulder kit "
            "you already use. Adds horizontal force production which "
            "isn't covered well in straight plyos. Lower impact = better "
            "on jumper's-knee days.",
    },

    # ── Plyometrics overview / educational ─────────────────────────────
    {
        "id":       "JM0BBD4z-t0",
        "title":    "Plyometrics for Volleyball!",
        "channel":  "Volleyball coaching",
        "year":     2020,
        "category": "plyometrics",
        "duration": "~6 min",
        "relevance":
            "Quick overview of plyo principles — Verkhoshansky's reactive "
            "strength concept explained in volleyball context. Theory "
            "lecture more than a workout — watch on a rest day.",
    },

    # ── Foot rehab — 2nd MTP plantar plate + intrinsic foot ─────────────
    # Added 2026-05-22 alongside the Rehab Protocols tab. These mirror
    # the inline `videos` field on REHAB_PROTOCOLS[0] in plan.py so users
    # can also find them through the Workouts catalog.
    {
        "id":       "meUFV2UQyf8",
        "title":    "Plantarflexion Taping for Plantar Plate Tears",
        "channel":  "Sports podiatry",
        "year":     2023,
        "category": "foot_rehab",
        "duration": "~5 min",
        "relevance":
            "Alternative to buddy-tape-to-3rd-toe — runs strap from top of "
            "the 2nd toe to its underside, holding the toe slightly down to "
            "directly offload the plantar plate. Show this to your PT.",
    },
    {
        "id":       "xM4E3pc0lQg",
        "title":    "6 Intrinsic Foot Muscle Strengthening Exercises",
        "channel":  "Foot rehab",
        "year":     2022,
        "category": "foot_rehab",
        "duration": "~10 min",
        "relevance":
            "Covers toe spreads + short-foot drill + towel scrunches — your "
            "entire Tuesday foot-intrinsic block. Watch once for form, then "
            "you can drill from memory.",
    },
    {
        "id":       "1RZXwuxXb4Y",
        "title":    "Plantar Fascia Intrinsic Towel Strengthening",
        "channel":  "Plantar fascia rehab",
        "year":     2021,
        "category": "foot_rehab",
        "duration": "~3 min",
        "relevance":
            "Specific towel scrunch demo. Form matters: drag the towel using "
            "only your toes, don't curl your whole foot. Common mistake.",
    },

    # ── Shoulder rehab — Crossover Symmetry / face pulls / landmine ────
    {
        "id":       "41YUdO7PEy8",
        "title":    "Ultimate Shoulder Warm-up and Rehab Guide w/ Crossover Symmetry",
        "channel":  "Crossover Symmetry",
        "year":     2023,
        "category": "shoulder_rehab",
        "duration": "~14 min",
        "relevance":
            "Canonical full Y-T-W protocol walkthrough from the company that "
            "named it. Watch once start-to-finish, then use it as your "
            "warmup template every upper-body session.",
    },
    {
        "id":       "lhRlNyavuKw",
        "title":    "Top 3 Crossover Symmetry Exercises",
        "channel":  "Crossover Symmetry",
        "year":     2022,
        "category": "shoulder_rehab",
        "duration": "~6 min",
        "relevance":
            "Minimum-effective-dose version of the full protocol. The 3 most "
            "important exercises for when you're short on time but still "
            "need the warmup.",
    },
    {
        "id":       "CU4Xc2qlLC0",
        "title":    "How To PROPERLY Do Face Pulls For Prehab & Shoulder Health",
        "channel":  "Form-focused PT",
        "year":     2024,
        "category": "shoulder_rehab",
        "duration": "~7 min",
        "relevance":
            "Form check for your weekly 3×15 face pulls. The key cue: pull "
            "to EARS, not nose. High anchor, external rotation at end of pull.",
    },
    {
        "id":       "n1NSt-h-tHA",
        "title":    "Landmine Press — Safest Open-Chain Shoulder Strengthening",
        "channel":  "Tim Keeley · Physio REHAB",
        "year":     2022,
        "category": "shoulder_rehab",
        "duration": "~8 min",
        "relevance":
            "Why landmine press is overhead-safe — the diagonal angle avoids "
            "the impingement zone. This is your substitute for barbell "
            "overhead pressing until 4 weeks pain-free.",
    },
]


# Categories with their UI metadata (emoji + short label + tone color).
# Matches the rest of the volleyball page styling palette.
CATEGORY_META: dict[str, dict] = {
    "plyometrics":       {"label": "Plyometrics",       "emoji": "🏐", "tone": "#3b82f6"},
    "strength":          {"label": "Lower strength",    "emoji": "🦵", "tone": "#22c55e"},
    "single_leg":        {"label": "Single-leg work",   "emoji": "🪶", "tone": "#f59e0b"},
    "home_no_equipment": {"label": "Home / no kit",     "emoji": "🏠", "tone": "#8b5cf6"},
    "knee_health":       {"label": "Knee health",       "emoji": "🦵", "tone": "#ec4899"},
    # Rehab categories — added 2026-05-22. Match the rehab protocol issues
    # in plan.py REHAB_PROTOCOLS so the Workouts tab and the Rehab tab
    # surface the same content from two angles.
    "foot_rehab":        {"label": "Foot rehab",        "emoji": "🦶", "tone": "#10b981"},
    "shoulder_rehab":    {"label": "Shoulder rehab",    "emoji": "🩹", "tone": "#06b6d4"},
}


def get_videos_by_category() -> dict[str, list[dict]]:
    """Group videos by category — used by the API endpoint + /volleyball
    Workouts tab. Returns categories in a stable insertion order matching
    CATEGORY_META so the tab strip renders predictably."""
    out: dict[str, list[dict]] = {k: [] for k in CATEGORY_META}
    for v in VIDEOS:
        cat = v.get("category", "plyometrics")
        out.setdefault(cat, []).append({
            **v,
            "url":           f"https://youtu.be/{v['id']}",
            "thumbnail_url": f"https://img.youtube.com/vi/{v['id']}/hqdefault.jpg",
        })
    # Drop empty categories so the UI doesn't render blank tabs.
    return {k: vs for k, vs in out.items() if vs}


__all__ = ["VIDEOS", "CATEGORY_META", "get_videos_by_category"]
