"""Volleyball + sports-health education cards.

Same shape as backend/flashcards/flashcards.py — push delivers one
card per day; the /volleyball Education tab shows the full bank
organized by topic.

Topics tuned to Ajay's stated profile:
  - shoulder      — long-term shoulder durability for hitters
  - foot          — 2nd MTP plantar plate (right index toe), taping,
                    intrinsic foot, insole + metatarsal pad placement
  - jumps         — vertical jump training (Verkhoshansky / NSCA)
  - knees         — patellar tendon, Spanish squats, eccentric work
  - recovery      — sleep, cold, compression, foam rolling
  - supplements   — Mg Glycinate, Moringa, D3/K2 — why these specifically
  - technique     — block timing, approach mechanics, defense
  - longevity     — career length, periodization, what >35yo VB players do

OWNER-ONLY — content keyed to Ajay's personal injury history.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta


SHOULDER_CARDS = [
    {"topic": "shoulder", "title": "🩹 Shoulder · The rotator cuff isn't 'small'",
     "body":  "Subscap, supraspinatus, infraspinatus, teres minor — these four muscles "
              "stabilize the glenohumeral joint during EVERY hit. They're small in cross-section "
              "but high in slow-twitch fibers; train them with LIGHT band work for HIGH reps "
              "(15-30/set), not heavy DB raises.",
     "source": "Andrews & Reinold · Sports Medicine of the Shoulder"},
    {"topic": "shoulder", "title": "🩹 Shoulder · Crossover Symmetry science",
     "body":  "Y-T-W band sequence activates serratus anterior + lower trap, the two muscles "
              "MOST inhibited in chronic shoulder pain. Daily 5-min protocol = +12° flexion ROM "
              "in 8 weeks (Cools et al, 2014). Skip it = pinching cycle continues.",
     "source": "Cools et al · J Athletic Training 2014"},
    {"topic": "shoulder", "title": "🩹 Shoulder · Why face pulls > shrugs",
     "body":  "Face pulls externally rotate while retracting — exactly the motion that's "
              "weak in spikers (whose shoulders live in internal rotation). Shrugs only "
              "elevate. Spikers need 3 face-pull sets for every 1 pressing set, minimum.",
     "source": "Eric Cressey · Pitching the Right Way"},
    {"topic": "shoulder", "title": "🩹 Shoulder · Sleep position matters",
     "body":  "Right-side sleeping COMPRESSES the right shoulder all night. If you have "
              "right-shoulder pain, sleep on the LEFT or back with a small pillow under the "
              "right elbow to keep it neutral. Two weeks of left-side sleeping = noticeable "
              "morning ROM improvement.",
     "source": "Park et al · Journal of Orthopaedic Research 2018"},
    {"topic": "shoulder", "title": "🩹 Shoulder · The pec minor culprit",
     "body":  "Tight pec minor pulls the scapula into anterior tilt = impingement. "
              "Doorway stretch 30 sec × 2 sides + lacrosse ball pec minor release "
              "after every upper session. 80% of 'rotator cuff' pain is actually pec minor.",
     "source": "Clinical Anatomy of the Shoulder"},
]

FOOT_CARDS = [
    {"topic": "foot", "title": "🦶 Foot · 2nd MTP plantar plate, defined",
     "body":  "The plantar plate is the dense fibrocartilage band under the "
              "metatarsophalangeal joints (where your toes meet your foot). "
              "The 2nd MTP plate tears most often in volleyball jumpers because "
              "takeoff drives all your bodyweight through that single joint when "
              "the heel comes off. Once torn, the toe can start to drift toward "
              "the big toe (early sign). Recovery: 8-16 weeks with rigid taping + "
              "stiff insoles + offloading the metatarsal head.",
     "source": "Cleveland Clinic · Plantar plate tear"},
    {"topic": "foot", "title": "🦶 Foot · Tape 2nd to 3rd toe, NEVER to big toe",
     "body":  "Buddy-taping the 2nd toe to the BIG toe pulls the 2nd metatarsal "
              "head further into the floor — the opposite of what you want. "
              "Tape 2nd TO 3RD toe instead. The 3rd toe is shorter and stabilizes "
              "without leveraging additional plate stress. Use rigid athletic "
              "tape at two points (above + below the joint, not across it).",
     "source": "Sports podiatry · plantar plate management"},
    {"topic": "foot", "title": "🦶 Foot · Metatarsal pad placement",
     "body":  "Metatarsal pad goes PROXIMAL to (behind) the painful spot, not "
              "ON it. The pad spreads the metatarsal heads + lifts the 2nd "
              "metatarsal off the ground at toe-off. Wrong placement (under "
              "the painful spot) makes it worse. Trim a felt pad to a "
              "teardrop, place point forward, behind the metatarsal head.",
     "source": "Foot & Ankle International"},
    {"topic": "foot", "title": "🦶 Foot · Viktry / stiff-soled insole rationale",
     "body":  "Plantar plate heals only if the joint stops bending at toe-off. "
              "A stiff-soled or carbon-plate insole (like Viktry's forefoot "
              "design) REDUCES MTP flexion during gait + landings — letting the "
              "plate consolidate. Flexible runners are the opposite — they "
              "encourage exactly the motion that re-tears the plate.",
     "source": "Sports podiatry consensus"},
    {"topic": "foot", "title": "🦶 Foot · Intrinsic muscle strengthening",
     "body":  "The intrinsic foot muscles (small ones inside the foot, not the "
              "calf) stabilize the metatarsal arch DURING takeoff. They atrophy "
              "in modern shoes. Three drills, 2× weekly: toe spreads (separate "
              "all 5 toes), short-foot drill (dome the arch WITHOUT curling "
              "toes), towel scrunches (drag a towel toward you with toes). "
              "8 weeks of this = measurably stronger forefoot.",
     "source": "McKeon et al · Br J Sports Med 2015"},
    {"topic": "foot", "title": "🦶 Foot · Why barefoot walking is bad now",
     "body":  "Barefoot walking lets the MTP joints flex through full range with "
              "every step. That's GREAT for healthy feet but REOPENS the plate "
              "tear while healing. Until pain is zero for 4 weeks: shoes on, "
              "even indoors. Yes really. Buy house slippers with a stiff sole.",
     "source": "American Orthopaedic Foot & Ankle Society"},
]

JUMP_CARDS = [
    {"topic": "jumps", "title": "🏐 Jumps · Verkhoshansky shock method",
     "body":  "The drop-jump (depth-jump) builds reactive strength = how quickly the "
              "Achilles + patellar tendon RECOIL after landing. KEY: brief ground contact "
              "(< 200ms). If you land flat and hold, you're doing a depth squat, not a "
              "depth jump. Box height: 12-18 inches max for most VB players.",
     "source": "Verkhoshansky · Special Strength Training Manual"},
    {"topic": "jumps", "title": "🏐 Jumps · Why your vertical plateaus",
     "body":  "Beginners gain inches from gym strength. Advanced jumpers gain from "
              "REACTIVE work (plyos) + approach mechanics. If your 1RM squat keeps going "
              "up but vertical doesn't, your problem is the LANDING phase — you're "
              "absorbing instead of recoiling. Shift to plyo emphasis 8 weeks.",
     "source": "NSCA · Essentials of Strength Training"},
    {"topic": "jumps", "title": "🏐 Jumps · Volume kills jumps",
     "body":  "More than 80 high-intensity contacts per week = jumpers knee territory. "
              "Track jumps: sets in practice (≈20/hr) + games (≈30) + plyo training (≈40). "
              "Sustainable cap: 300-400 contacts per week for adults. Above that, "
              "patellar tendon micro-tears outpace repair.",
     "source": "Visnes & Bahr · Sports Medicine"},
    {"topic": "jumps", "title": "🏐 Jumps · Approach mechanics > strength",
     "body":  "A 3-step approach converts horizontal momentum into vertical lift. Slow "
              "the FIRST step, accelerate steps 2-3, plant HARD. Most amateur jumpers "
              "lose 6 inches by sprinting all 3 steps equally. Drill the rhythm "
              "(slow-fast-fast) on a flat floor weekly.",
     "source": "USA Volleyball coaching manual"},
]

KNEE_CARDS = [
    {"topic": "knees", "title": "🦵 Knees · Spanish squat magic",
     "body":  "Band looped behind knees, squat with VERTICAL shins. Forces the patellar "
              "tendon to load in the position it gets injured in — but ECCENTRICALLY. "
              "Heron et al 2017: Spanish squats reduced patellar tendinopathy pain "
              "by 40% over 12 weeks vs standard PT. Cheaper than reverse Nordic.",
     "source": "Heron et al 2017 · BJSM"},
    {"topic": "knees", "title": "🦵 Knees · Jumper's knee mechanism",
     "body":  "Patellar tendinopathy = micro-tears at the inferior pole of the patella. "
              "It's not 'wear and tear' — it's a load-management failure. Tendons need "
              "ECCENTRIC overload to remodel. Heavy slow resistance (3-sec down on every "
              "rep) is the proven protocol. NOT rest.",
     "source": "Kongsgaard et al · Am J Sports Medicine"},
    {"topic": "knees", "title": "🦵 Knees · Jumplete braces use-when",
     "body":  "Patellar straps reduce peak load on the tendon by 20-30% during jumps. "
              "Wear them DURING games + heavy plyo sessions. Don't wear them on rest "
              "days or strength days — the tendon needs full loading to adapt. Crutch "
              "during competition, off during training.",
     "source": "de Vries et al · Sports Health 2016"},
    {"topic": "knees", "title": "🦵 Knees · Insole forefoot support",
     "body":  "Viktry-style forefoot-cushion insoles redistribute landing impact across "
              "the metatarsal heads. Reduces the localized stress on the second/third "
              "metatarsal that gives volleyball players stress reactions. Replace every "
              "6-9 months — the cushion compresses out.",
     "source": "Sports podiatry consensus"},
]

RECOVERY_CARDS = [
    {"topic": "recovery", "title": "💤 Recovery · Sleep is the #1 input",
     "body":  "<7 hours sleep = 30% drop in time-to-exhaustion on next-day testing "
              "(Mah et al, Stanford). Growth hormone pulse + glymphatic clearance "
              "happen DEEP in slow-wave sleep, which compresses when total sleep drops. "
              "If you only optimize one thing, sleep duration is it. 8 hours non-negotiable.",
     "source": "Mah et al 2011 · Sleep"},
    {"topic": "recovery", "title": "💤 Recovery · Cold shower science",
     "body":  "3-5 min cold post-game reduces DOMS (delayed-onset muscle soreness) "
              "by ~20% at 24h. Mechanism: vasoconstriction flushes inflammatory "
              "cytokines. NOT for strength gains (cold dampens hypertrophy signal) — "
              "USE cold after competition + matches, AVOID after gym strength days.",
     "source": "Cochrane Review 2012"},
    {"topic": "recovery", "title": "💤 Recovery · Compression sleeves",
     "body":  "Graded compression knee sleeves post-game reduce edema and speed "
              "lymphatic clearance. Wear 30-60 min after matches. NOT during sleep "
              "(can compress nerves overnight). Cheap intervention with proven "
              "subjective DOMS benefit.",
     "source": "Hill et al · J Strength Cond Res"},
    {"topic": "recovery", "title": "💤 Recovery · Foam rolling reality",
     "body":  "Foam rolling does NOT 'break up fascia' (you can't with body weight). "
              "What it DOES do: temporarily increase ROM via neural inhibition + "
              "subjectively reduce soreness. 5-10 min post-session is plenty. "
              "Skip if you have time pressure — sleep matters more.",
     "source": "Beardsley & Skarabot · J Bodywork Movement"},
    {"topic": "recovery", "title": "💤 Recovery · Walking is underrated",
     "body":  "30-min easy walk on rest days = arterial flow without stress on tendons. "
              "Increases recovery-marker normalization 30% faster than total rest "
              "(Stewart et al). Outdoor walks add sunlight = vitamin D + circadian "
              "regulation. Do this every Sunday.",
     "source": "Stewart et al · Med Sci Sports Exerc"},
]

SUPPLEMENT_CARDS = [
    {"topic": "supplements", "title": "💊 Magnesium · Glycinate is the right form",
     "body":  "Citrate = laxative effect. Oxide = poorly absorbed (~4% bioavailable). "
              "Glycinate = bound to glycine; crosses blood-brain barrier; doesn't "
              "upset gut. Dose: 200-400 mg 30-60 min before bed for muscle relaxation + "
              "GABA-pathway sleep depth. The form Ajay takes is the right one.",
     "source": "Schwalfenberg & Genuis · Scientifica 2017"},
    {"topic": "supplements", "title": "💊 Magnesium · Why athletes deplete it",
     "body":  "Sweat losses + muscle contraction demands = athletes need ~20% more "
              "than the RDA. Symptoms of low Mg: cramps, restless sleep, twitching, "
              "post-workout DOMS that drags 2+ days. Bloodwork doesn't catch it well "
              "(99% of body Mg is intracellular). Supplement first; test later.",
     "source": "Volpe · Adv Nutr 2015"},
    {"topic": "supplements", "title": "💊 D3/K2 · The synergy",
     "body":  "D3 alone increases calcium absorption — but without K2, the calcium "
              "can deposit in arteries (calcification) instead of bones. K2 (specifically "
              "MK-7 form) activates osteocalcin to direct calcium to bone. ALWAYS take "
              "D3 with K2. Dose: 2000-5000 IU D3 + 100-180 mcg K2 daily, with fat.",
     "source": "Maresz · Integrative Medicine"},
    {"topic": "supplements", "title": "💊 D3 · Most US athletes are low",
     "body":  "82% of indoor-sport athletes test below 30 ng/mL (insufficient) at end "
              "of winter. D3 affects fast-twitch fiber recruitment + immune function + "
              "bone density. Get a baseline (target: 40-60 ng/mL), supplement, re-test "
              "in 3 months. Skip if you're already at 50+ year-round.",
     "source": "Cannell et al · Med Sci Sports Exerc"},
    {"topic": "supplements", "title": "💊 Moringa · Real but modest",
     "body":  "Moringa oleifera leaves contain ~25% protein, iron, calcium, B-vitamins "
              "+ moderate antioxidant load. Effect is real but modest — not a "
              "'superfood'. Best use case: low-cost micronutrient insurance in the "
              "morning. Don't expect performance boosts; do expect baseline B-vitamin "
              "coverage if your diet is uneven.",
     "source": "Stohs & Hartman 2015 · Phytotherapy Research"},
]

TECHNIQUE_CARDS = [
    {"topic": "technique", "title": "🏐 Block · Penetrate the net",
     "body":  "Blocking that REACHES OVER the net is 2× as effective as blocking "
              "AT the net. Get your wrists past the tape. Requires shoulder ROM + "
              "core rigidity to stay rigid mid-flight. If your shoulders won't allow "
              "it, block lower and bigger — protect them.",
     "source": "USAV coaching standards"},
    {"topic": "technique", "title": "🏐 Defense · Low ready position",
     "body":  "Knees over toes, weight on forefoot, hips below knees. Holds your "
              "center of gravity low so you can move EITHER direction in equal time. "
              "Standing tall in defense = you're committed to one direction before "
              "the ball is even hit. Drill this against a wall — partner spikes, "
              "you read.",
     "source": "Mike Hebert · Thinking Volleyball"},
    {"topic": "technique", "title": "🏐 Approach · Slow-fast-fast",
     "body":  "3-step approach rhythm. Step 1 is patient — read the set. Steps 2-3 "
              "are explosive — convert horizontal speed to vertical. Most amateurs "
              "sprint all three steps and arrive at the ball before it's set. "
              "Slow Step 1 = best jump.",
     "source": "USAV setter manual"},
    {"topic": "technique", "title": "🏐 Serve · Toss < shoulder height",
     "body":  "For a float serve: toss the ball NO HIGHER than your reach. High tosses "
              "introduce arc variance. Toss low, contact at full extension, no spin. "
              "Float serves with a low toss have 40% more 'wobble' in flight = more "
              "passing errors against you.",
     "source": "USAV coaching"},
]

LONGEVITY_CARDS = [
    {"topic": "longevity", "title": "🌳 Longevity · The 30-year-old VB player",
     "body":  "By 30, most players have accumulated micro-damage in shoulders, "
              "patellar tendons, fingers, lower back. The ones who play to 50+ all "
              "share: (1) consistent prehab routine, (2) periodized volume (off-season "
              "is REAL rest), (3) zero ego-lifting, (4) sleep priority. Skip any one of "
              "the four and the body wins.",
     "source": "Master's volleyball longitudinal data"},
    {"topic": "longevity", "title": "🌳 Longevity · Periodize the year",
     "body":  "4-week microcycles: 3 weeks build, 1 week deload (50% volume). "
              "Quarterly macrocycle: 12 weeks build, 4 weeks active recovery. Annual: "
              "8-week off-season completely off court. The body needs the recovery "
              "weeks to adapt — without them you're just accumulating fatigue.",
     "source": "Bompa · Periodization Training"},
    {"topic": "longevity", "title": "🌳 Longevity · Mobility before strength",
     "body":  "Lose hip mobility → compensate with lower back → herniated disc by 40. "
              "Lose thoracic mobility → compensate with shoulder → rotator cuff tear. "
              "20 min of mobility 3× weekly preserves both. Foam roll + dynamic "
              "stretching + yoga. Most volleyball careers end from MOBILITY loss, not "
              "strength loss.",
     "source": "Sports medicine clinical practice"},
    {"topic": "longevity", "title": "🌳 Longevity · Hydration math",
     "body":  "Lose 2% body weight in fluid → 10% drop in jump height. Most players "
              "play dehydrated and don't realize it. Weigh yourself pre- and post-game; "
              "every pound lost = 16 oz water needed. Add electrolytes (sodium, "
              "potassium) for sessions over 90 minutes.",
     "source": "ACSM hydration position stand"},
]


TOPIC_POOLS = {
    "shoulder":    SHOULDER_CARDS,
    "foot":        FOOT_CARDS,    # renamed from 'fingers' 2026-05-22 — actual issue is 2nd MTP plantar plate
    "jumps":       JUMP_CARDS,
    "knees":       KNEE_CARDS,
    "recovery":    RECOVERY_CARDS,
    "supplements": SUPPLEMENT_CARDS,
    "technique":   TECHNIQUE_CARDS,
    "longevity":   LONGEVITY_CARDS,
}

ALL_CARDS: list[dict] = [c for pool in TOPIC_POOLS.values() for c in pool]


# Day-of-year rotation across the FLAT card list — every card surfaces
# once before any repeat. With ~30 cards, that's a ~30-day cycle.
def _day_of_year_et() -> int:
    et = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-5)))
    return et.timetuple().tm_yday


def pick_today() -> dict:
    """One card per day for the daily-education push."""
    return ALL_CARDS[_day_of_year_et() % len(ALL_CARDS)]


__all__ = ["TOPIC_POOLS", "ALL_CARDS", "pick_today"]
