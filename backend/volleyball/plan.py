"""7-day volleyball training plan tuned to Ajay's constraints.

Personalization rules built in (read this if you ever extend the plan):

  * Right shoulder — long-term overuse from hitting. NO bilateral
    barbell overhead pressing. Substitute landmine press, floor press,
    and band Y-T-W. Daily band warmup (Crossover Symmetry / Jaeger
    Bands protocol) BEFORE any upper-body work.

  * Right 2nd MTP (index toe) plantar plate — jumper's forefoot
    pathology. Plantar plate is the fibrocartilaginous structure
    under the 2nd metatarsophalangeal joint that prevents toe
    hyperextension on toe-off. Volleyball jumpers tear it from
    repeated forefoot loading at takeoff.
    Protocol:
      - Buddy-tape 2ND TOE to 3RD TOE (NOT to big toe — that
        increases stress on the 2nd plantar plate)
      - Stiff-soled shoes + Viktry forefoot insole always on
      - Metatarsal pad PROXIMAL to the 2nd metatarsal head (just
        behind the painful spot) — redistributes load
      - Limit barefoot training, especially on hard floors
      - Modify jump landings: full-foot / midfoot landings, NOT
        forefoot stick-landings
      - Intrinsic foot strengthening (toe spreads, towel scrunches,
        short-foot drill) 2× weekly

  * Knees — Jumplete patellar braces during plyos. Spanish squats and
    single-leg eccentric work for patellar-tendon resilience. Jump
    LOWER than ego suggests; vertical-jump training is volume work.

  * Supplements — D3/K2 + Moringa in the AM (fat-soluble + iron-light
    energy); Magnesium Glycinate 30-60 min pre-sleep for muscle
    recovery + sleep quality.

  * Gear — Viktry insoles in every shoe for forefoot support during
    jump landings (especially important for the 2nd MTP plantar
    plate — these were chosen exactly for this).

The plan rotates by weekday (Mon → 0 ... Sun → 6 in Python convention).

OWNER-ONLY MODULE — this content is keyed to Ajay's personal injury
profile. The /vb/* endpoints gate on require_house_owner so it never
surfaces to friends even if a feature flag accidentally toggled on.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional


SESSION_TYPES = [
    "lower_power",       # Mon
    "upper_pull_rehab",  # Tue
    "skills_active_rec", # Wed
    "lower_strength",    # Thu
    "upper_push_stab",   # Fri
    "match_day",         # Sat
    "recovery_mobility", # Sun
]


# Day-of-week (0=Mon ... 6=Sun) → session blueprint.
# Each block has: name, focus, blocks[].
# block.exercises[] is what the UI renders as a checklist.
PLAN: dict[int, dict] = {
    0: {
        "name":  "Mon · Lower Power",
        "focus": "Vertical jump + posterior chain. Plyos at moderate volume. "
                  "2nd MTP-friendly: full-foot landings, taped + insoled.",
        "duration_min": 50,
        "tags": ["plyos", "knees", "glutes", "forefoot-safe"],
        "blocks": [
            {
                "label": "Warmup (12 min)",
                "exercises": [
                    "Tape 2nd toe to 3rd toe BEFORE shoes (not to big toe)",
                    "Viktry insoles in shoes · check metatarsal pad placement",
                    "Dynamic mobility — leg swings, hip circles, ankle rocks (3 min)",
                    "Intrinsic foot warmup — toe spreads 2×10, short-foot drill 2×10 sec",
                    "Band Y-T-W 2×10 each — Crossover Symmetry protocol",
                    "Band external rotations 2×15 each side",
                    "Low pogo hops 2×15 — moderate height, FULL-FOOT landings (no forefoot stick)",
                ],
            },
            {
                "label": "Power (20 min)",
                "exercises": [
                    "Single-leg RDL 3×8 each — light dumbbell, slow tempo",
                    "Spanish squat 3×10 — band around knees, vertical shins",
                    "Box jumps 5×3 — LOW box (~12-18\"); MIDFOOT landing, not forefoot",
                    "Bent-knee calf raises 3×12 each — soleus bias reduces plantar fascia pull",
                ],
            },
            {
                "label": "Core + Finish (10 min)",
                "exercises": [
                    "Dead bug 3×8 each side",
                    "Pallof press 3×10 each — anti-rotation",
                    "Towel scrunches 2×30 reps — intrinsic foot strength",
                    "5-minute walk — flush legs, keep shoes ON",
                ],
            },
        ],
    },
    1: {
        "name":  "Tue · Upper Pull + Shoulder Rehab",
        "focus": "Build pulling volume. Active rehab for right shoulder via bands. "
                  "Light intrinsic-foot block at the end.",
        "duration_min": 45,
        "tags": ["shoulder-rehab", "pull", "foot-intrinsics"],
        "blocks": [
            {
                "label": "Shoulder warmup (10 min) — DO NOT SKIP",
                "exercises": [
                    "Band Y-T-W 3×10 each (no rest between letters)",
                    "Band external rotations 3×15 each — elbow tucked at side",
                    "Face pulls 3×15 — high anchor, pull to ears not nose",
                    "Scapular pull-ups (no bend) 3×8",
                ],
            },
            {
                "label": "Main pull (25 min)",
                "exercises": [
                    "Pull-ups 3×AMRAP — keep shoes ON (don't go barefoot for hanging foot stress)",
                    "Single-arm dumbbell row 3×10 each — neutral grip, no shoulder shrug",
                    "Cable rope rows 3×12 — pull to upper chest",
                    "Reverse flies 3×12 — light weight, slow eccentric",
                ],
            },
            {
                "label": "Foot intrinsics + cooldown (10 min) — dedicated 2nd MTP rehab",
                "exercises": [
                    "Toe spreads 3×15 — separate all 5 toes, hold 1 sec at end",
                    "Towel scrunches 3×20 reps — pull a towel toward you using only toes",
                    "Short-foot drill 3×30 sec — dome the arch without curling toes",
                    "Marble pickups 2×10 — proprioception + intrinsic strength",
                    "Doorway pec stretch 2×30 sec each side",
                ],
            },
        ],
    },
    2: {
        "name":  "Wed · Skills + Active Recovery",
        "focus": "Volleyball skill drills. NO heavy lifting today — legs need to be fresh for Thursday. "
                  "Toe tape + insoles for any jump approaches.",
        "duration_min": 60,
        "tags": ["skills", "recovery", "court"],
        "blocks": [
            {
                "label": "Court warmup (10 min)",
                "exercises": [
                    "Tape 2nd toe to 3rd toe · Viktry insoles in court shoes",
                    "Jog perimeter 5 min",
                    "Dynamic stretches (hips, hammies, shoulders)",
                    "Band shoulder routine — half of Tuesday's (5 min)",
                ],
            },
            {
                "label": "Approach + jump (20 min)",
                "exercises": [
                    "3-step approach to wall — focus on plant + arm swing, 20 reps at 70%",
                    "4-step approach + block jump — 15 reps at 70% effort, FULL-FOOT landing",
                    "Block timing drill against wall — 30 reps",
                ],
            },
            {
                "label": "Setting + serving (15 min)",
                "exercises": [
                    "Wall sets — 50 reps, focus on hand shape",
                    "Float serve practice — 20 reps from baseline",
                    "Jump serve — 10 reps at moderate effort (watch the right-foot plant)",
                ],
            },
            {
                "label": "Active recovery (15 min)",
                "exercises": [
                    "Walk 30 min outdoors WITH SHOES — sunlight on skin (boosts circadian)",
                    "OR — pool swim, easy pace, 20 min (water unloads the forefoot)",
                ],
            },
        ],
    },
    3: {
        "name":  "Thu · Lower Strength",
        "focus": "Heavy compound posterior-chain work. No plyometrics today.",
        "duration_min": 55,
        "tags": ["strength", "knees", "hams"],
        "blocks": [
            {
                "label": "Warmup (10 min)",
                "exercises": [
                    "Bike or row 5 min easy",
                    "Goblet squat 2×10 — light, full ROM",
                    "Glute bridge 2×12 — squeeze at top",
                    "Band Y-T-W 2×10 — quick shoulder routine",
                ],
            },
            {
                "label": "Main strength (30 min)",
                "exercises": [
                    "Goblet squat 4×6 — moderate-heavy, full depth",
                    "Hex bar deadlift 4×5 — neutral spine, no shoulder shrug",
                    "Bulgarian split squat 3×8 each — DBs at sides, Jumplete on if needed",
                    "Romanian deadlift 3×8 — focus on hammies, light vs Thursday max",
                ],
            },
            {
                "label": "Knee health + finish (15 min)",
                "exercises": [
                    "Spanish squat 3×12 — patellar tendon eccentric",
                    "Tibialis raises against wall 3×15 — calf balance",
                    "Couch stretch 90 sec each side",
                ],
            },
        ],
    },
    4: {
        "name":  "Fri · Upper Push + Stability (shoulder-safe)",
        "focus": "Push patterns that avoid the right-shoulder pinch zone.",
        "duration_min": 45,
        "tags": ["shoulder-safe", "push", "core"],
        "blocks": [
            {
                "label": "Shoulder warmup (10 min)",
                "exercises": [
                    "Band Y-T-W 3×10 — full routine, no skipping",
                    "Band pull-aparts 3×15",
                    "Wall slides 2×10 — slow, control through full ROM",
                ],
            },
            {
                "label": "Push (20 min) — shoulder-safe variations",
                "exercises": [
                    "Floor press 3×8 — DBs, no shoulder impingement risk",
                    "Landmine press 3×10 each — neutral angle, no overhead",
                    "Pushup variants 3×AMRAP — buddy-tape finger; if pain, switch to incline",
                    "Tricep pushdowns 3×12 — cable rope",
                ],
            },
            {
                "label": "Core + finish (10 min)",
                "exercises": [
                    "Cable Pallof press 3×10 each — anti-rotation",
                    "Hollow body hold 3×30 sec",
                    "Banded shoulder ER 2×15 each — finisher rehab dose",
                ],
            },
        ],
    },
    5: {
        "name":  "Sat · Match / Game Day",
        "focus": "Compete. Pre-game routine + post-game recovery is the workout.",
        "duration_min": 120,
        "tags": ["match", "competition"],
        "blocks": [
            {
                "label": "60-min pre-game",
                "exercises": [
                    "Tape 2nd toe to 3rd toe (RIGHT foot) BEFORE shoes",
                    "Viktry insoles + metatarsal pad placement check",
                    "Knee braces (Jumplete) on if jumping heavy this match",
                    "Band Y-T-W full routine (5 min)",
                    "Band external rotations (3 min)",
                    "Jump rope 3 min — short ground contacts, full-foot",
                    "Approach jumps 5×3 — dial in timing, midfoot landings",
                    "Setting + spike warmup with partner (10 min)",
                ],
            },
            {
                "label": "Match",
                "exercises": [
                    "Hydrate every set break — water + electrolytes",
                    "Apply Viktry insole — check shoes",
                    "Knee braces (Jumplete) if jumping is heavy",
                    "Between sets: shake out wrists, no sitting",
                ],
            },
            {
                "label": "Post-game recovery",
                "exercises": [
                    "Cold shower 3-5 min — reduces inflammation",
                    "Compression sleeves on knees 30 min",
                    "Foam roll quads + IT band + calves (10 min)",
                    "Magnesium Glycinate before bed — sleep is the recovery",
                ],
            },
        ],
    },
    6: {
        "name":  "Sun · Recovery + Mobility",
        "focus": "Active recovery. Mobility, fascia, parasympathetic shift.",
        "duration_min": 45,
        "tags": ["recovery", "mobility", "rest"],
        "blocks": [
            {
                "label": "Mobility flow (20 min)",
                "exercises": [
                    "World's greatest stretch 3×each side",
                    "Cat-cow + thoracic rotations 2×10",
                    "Hip 90/90 stretches 2×30 sec each",
                    "Pancake stretch 2×60 sec — hammies + adductors",
                ],
            },
            {
                "label": "Soft tissue (15 min)",
                "exercises": [
                    "Foam roll quads + IT band + glutes (5 min)",
                    "Lacrosse ball: pec minor + upper traps (3 min each side)",
                    "Lacrosse ball: feet 2 min each — neural reset",
                ],
            },
            {
                "label": "Long walk (30 min)",
                "exercises": [
                    "Walk outdoors — sunlight on skin",
                    "No headphones — let the mind drift",
                ],
            },
        ],
    },
}


SUPPLEMENT_SCHEDULE = [
    {
        "name":   "D3 / K2",
        "time":   "07:00 ET",
        "with":   "fat-containing breakfast",
        "why":    "fat-soluble; K2 directs calcium away from arteries to bones; D3 levels are seasonal (low in winter US latitudes)",
    },
    {
        "name":   "Moringa",
        "time":   "07:00 ET",
        "with":   "morning beverage",
        "why":    "iron-light energy + chlorophyll + ~25% protein by weight; small ergogenic boost without caffeine spike",
    },
    {
        "name":   "Magnesium Glycinate",
        "time":   "21:30 ET (30-60 min before bed)",
        "with":   "water, away from caffeine/tea",
        "why":    "glycinate form crosses blood-brain barrier; muscle relaxation + GABA-pathway sleep depth + recovery from training",
    },
]


REHAB_PROTOCOLS = [
    {
        "issue":   "Right 2nd MTP (index toe) plantar plate",
        "always":  [
            "Buddy-tape 2ND TOE to 3RD TOE before shoes — NOT to the big toe (big-toe taping increases stress on the 2nd plantar plate)",
            "Alternative: PLANTARFLEXION strap — runs from top of toe over to underside, holds toe slightly down. Some PTs prefer this for direct plate offload (see video #1). Coordinate with your PT.",
            "Viktry forefoot insole + metatarsal pad placed PROXIMAL to the 2nd metatarsal head (just behind the painful spot, not on it)",
            "Stiff-soled shoes only — avoid flexible runners, no barefoot walking on hard floors",
            "Jump landings: full-foot or midfoot. NO forefoot stick-landings — those load the plantar plate directly",
            "After session: ice 10 min if swelling; 5 min of toe spreads",
        ],
        "weekly":  [
            "Toe spreads, towel scrunches, short-foot drill, marble pickups — Tuesday is the dedicated foot-intrinsic block",
            "Bent-knee calf raises (soleus bias) 3×15 instead of straight-leg — reduces plantar fascia pull",
            "Pool walking 20 min once a week — unloads forefoot while keeping movement",
        ],
        "see_doc": "If pain at rest 2+ weeks OR if you see the toe starting to drift away from the others, see a sports podiatrist. Plantar plate tears can need imaging (MRI) and rarely surgery. Long term protection is the carbon-plate insole + taping protocol.",
        # Hand-curated YouTube video instructions for this issue. Format
        # mirrors backend/volleyball/videos.py so the frontend can use
        # the same rendering. URLs verified via web search 2026-05-22.
        "videos":  [
            {
                "id":      "meUFV2UQyf8",
                "title":   "Plantarflexion Taping for Plantar Plate Tears",
                "channel": "Sports podiatry",
                "note":    "Alternative to buddy-taping — strap runs from top of the toe over to the underside, holding the toe in a slight plantarflexion to offload the plate directly. Some clinicians prefer this over buddy-to-3rd-toe.",
            },
            {
                "id":      "xM4E3pc0lQg",
                "title":   "6 Intrinsic Foot Muscle Strengthening Exercises",
                "channel": "Foot rehab / PT",
                "note":    "Covers toe spreads, short-foot drill, and towel scrunches — all of your Tuesday foot-intrinsic block in one video. Pay attention to the short-foot demo: dome the arch WITHOUT curling toes.",
            },
            {
                "id":      "1RZXwuxXb4Y",
                "title":   "Plantar Fascia Intrinsic Towel Strengthening",
                "channel": "Plantar fascia rehab",
                "note":    "Specific towel scrunch demo. Form matters — drag the towel using only your toes, don't curl your whole foot.",
            },
        ],
    },
    {
        "issue":   "Right shoulder (overuse)",
        "always":  [
            "Band Y-T-W routine BEFORE every upper-body session (Mon, Tue, Fri, Sat warmup)",
            "External rotation bands — minimum 30 reps/day total, split across sessions",
            "NO bilateral barbell overhead pressing until pain-free 4 weeks",
            "Floor press + landmine press as overhead substitutes",
        ],
        "weekly":  [
            "Face pulls 3×15 — minimum 3 days/week",
            "Doorway pec stretch — 30 sec each side, daily",
            "Crossover Symmetry / Jaeger Bands full protocol — twice weekly",
        ],
        "see_doc": "If sharp pain on internal rotation OR night pain wakes you up, get an MRI ruling out labrum / SLAP.",
        "videos":  [
            {
                "id":      "41YUdO7PEy8",
                "title":   "Ultimate Shoulder Warm-up and Rehab Guide with Crossover Symmetry",
                "channel": "Crossover Symmetry",
                "note":    "Canonical full Y-T-W protocol walkthrough from the company that named it. Watch once start-to-finish, then use it as your warmup template (M/Tu/F/Sat).",
            },
            {
                "id":      "lhRlNyavuKw",
                "title":   "Top 3 Crossover Symmetry Exercises",
                "channel": "Crossover Symmetry",
                "note":    "When you only have 5 minutes — the highest-yield 3 movements. Use this as your minimum-effective-dose warmup on busy days.",
            },
            {
                "id":      "CU4Xc2qlLC0",
                "title":   "How To PROPERLY Do Face Pulls For Prehab & Shoulder Health",
                "channel": "Form-focused PT",
                "note":    "Form check for your 3×15 face pulls — pull to EARS, not nose. High anchor point. External rotation at the end of the pull is the key cue most people miss.",
            },
            {
                "id":      "n1NSt-h-tHA",
                "title":   "Landmine Press - The Safest Open Chain Shoulder Strengthening",
                "channel": "Tim Keeley · Physio REHAB",
                "note":    "Why landmine press is overhead-safe — the diagonal angle avoids the impingement zone. This is your substitute for barbell overhead pressing.",
            },
        ],
    },
]


def _now_et() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-5)))


def get_today_plan(weekday: Optional[int] = None) -> dict:
    """Today's session blueprint. Default to current ET weekday."""
    if weekday is None:
        weekday = _now_et().weekday()
    plan = PLAN.get(weekday, PLAN[0])
    return {
        "weekday":     weekday,
        "session":     plan,
        "supplements": SUPPLEMENT_SCHEDULE,
        "rehab":       REHAB_PROTOCOLS,
        "date_et":     _now_et().strftime("%Y-%m-%d"),
    }


def get_weekly_plan() -> dict:
    return {
        "days":        [{"weekday": k, **v} for k, v in PLAN.items()],
        "supplements": SUPPLEMENT_SCHEDULE,
        "rehab":       REHAB_PROTOCOLS,
    }


__all__ = ["PLAN", "SUPPLEMENT_SCHEDULE", "REHAB_PROTOCOLS",
           "get_today_plan", "get_weekly_plan"]
