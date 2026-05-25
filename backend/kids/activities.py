"""Curated activity DB — research-backed, household-items only.

Each activity has:
  - name, framework (Montessori / RIE / Reggio / etc.)
  - age_min, age_max — typical age band
  - duration_min — realistic attention span at age 3-4
  - materials — only stuff in the kitchen / recycling
  - skill — what it develops (fine_motor / counting / sorting / etc.)
  - mess_level — 1 (clean) to 5 (full sensory chaos)
  - setup_min — adult prep time
  - reset_min — cleanup time
  - notes — short adult-facing instruction
  - source — author / framework citation
  - search_query — Google query to find a video walkthrough
"""
from __future__ import annotations

# Frameworks → influence shorthand the planner uses to bias rotation:
# parents tend to revisit the same framework for a week, then switch.
FRAMEWORKS = {
    "Montessori":    "Maria Montessori — sensorial, practical life",
    "RIE":           "Magda Gerber / Janet Lansbury — respectful, child-led",
    "Reggio":        "Reggio Emilia — loose parts, atelier",
    "Play-based":    "Bev Bos / Lisa Murphy — open-ended play",
    "Big Little Feelings": "Kristin Gallant / Deena Margolin — emotion regulation",
    "Whole-Brain":   "Dan Siegel / Tina Payne Bryson — integration",
    "Tinkergarten":  "Tinkergarten — nature, outdoor sensory",
}


ACTIVITIES: list[dict] = [
    # ─── Lentil / rice / dry-goods sensory bins (Montessori classic) ──────
    {
        "id": "lentil_scoop_pour",
        "name": "Lentil Scoop & Pour Station",
        "framework": "Montessori",
        "age_min": 2.5, "age_max": 5,
        "duration_min": 20,
        "materials": ["1 cup dry lentils (toor / moong / chana)",
                      "2 small bowls", "1 spoon or scoop", "tray"],
        "skill": "fine_motor · cause_and_effect · concentration",
        "mess_level": 3,
        "setup_min": 2, "reset_min": 5,
        "notes": ("Set the tray on the floor. Pour lentils into one bowl, "
                  "give her the spoon. Show ONCE: scoop and transfer to the "
                  "other bowl. Then step back and let her work. Resist "
                  "narrating — Montessori principle of uninterrupted focus."),
        "source": "Maria Montessori, The Absorbent Mind (Ch. 11)",
        "search_query": "Montessori lentil pouring transfer activity toddler",
    },
    {
        "id": "rice_color_sort",
        "name": "Color Sort with Rice + Bowls",
        "framework": "Montessori",
        "age_min": 3, "age_max": 5,
        "duration_min": 25,
        "materials": ["2 cups uncooked rice (mix in 4 colors using food coloring)",
                      "4 small bowls or paper cups", "small spoons"],
        "skill": "color_recognition · sorting · fine_motor",
        "mess_level": 4,
        "setup_min": 15, "reset_min": 8,
        "notes": ("Pre-color the rice once (vinegar + 2-3 drops food color, "
                  "spread to dry — keeps for months in jars). Mix all colors "
                  "in a tray. Ask her to scoop each color into the matching "
                  "bowl. Builds early sorting and color naming."),
        "source": "Montessori — practical life + sensorial",
        "search_query": "Montessori colored rice sorting toddler activity",
    },
    {
        "id": "lentil_bury_treasure",
        "name": "Buried Treasure in Lentils",
        "framework": "Montessori",
        "age_min": 2, "age_max": 5,
        "duration_min": 20,
        "materials": ["large bowl of dry lentils or rice",
                      "5-8 small toys / spoons / coins (anything she can find)",
                      "tongs or spoon for fishing them out"],
        "skill": "fine_motor · object_permanence · problem_solving",
        "mess_level": 3,
        "setup_min": 3, "reset_min": 5,
        "notes": ("Bury 5-8 small objects in the lentil bowl. Challenge: "
                  "find them with a spoon (no hands). Builds the same "
                  "fine-motor skill her future writing hand needs. Switch "
                  "to chopsticks/tongs as she gets older."),
        "source": "Montessori sensorial bin tradition",
        "search_query": "Montessori sensory bin buried objects toddler",
    },

    # ─── Paper cup activities ─────────────────────────────────────────────
    {
        "id": "cup_tower_count",
        "name": "Paper Cup Tower + Count-and-Knock",
        "framework": "Play-based",
        "age_min": 2, "age_max": 5,
        "duration_min": 15,
        "materials": ["10-15 paper cups", "soft ball or rolled-up sock"],
        "skill": "counting · gross_motor · cause_and_effect",
        "mess_level": 1,
        "setup_min": 1, "reset_min": 1,
        "notes": ("Stack cups into a pyramid. Count each one as she places "
                  "it: 'one, two, three…'. Then she knocks it down with the "
                  "ball. Repeat. Hits counting + grossmotor + the dopamine "
                  "rush of demolition (Bev Bos: 'the joy of knocking down')."),
        "source": "Bev Bos — Don't Move the Muffin Tins",
        "search_query": "paper cup tower toddler counting activity",
    },
    {
        "id": "cup_phone_listening",
        "name": "Paper Cup Phone (Telephone Game)",
        "framework": "RIE",
        "age_min": 3, "age_max": 6,
        "duration_min": 15,
        "materials": ["2 paper cups", "string (3-4 ft)",
                      "scissors (adult)", "tape"],
        "skill": "language · cause_and_effect · social_play",
        "mess_level": 1,
        "setup_min": 5, "reset_min": 1,
        "notes": ("Poke a hole in each cup bottom, thread string, knot inside. "
                  "Pull tight, talk into one — she hears you in the other. "
                  "Magic moment. RIE-style: ask her what she hears, let her "
                  "explain rather than narrating it for her."),
        "source": "Magda Gerber, RIE — respectful conversation",
        "search_query": "string telephone paper cup kids science",
    },
    {
        "id": "cup_color_match",
        "name": "Paper Cup + Pom-Pom Color Match",
        "framework": "Montessori",
        "age_min": 2.5, "age_max": 4.5,
        "duration_min": 15,
        "materials": ["6-8 paper cups (mark each with a color dot)",
                      "matching colored pom-poms or bottle caps",
                      "tongs or her fingers"],
        "skill": "color_match · fine_motor · concentration",
        "mess_level": 1,
        "setup_min": 3, "reset_min": 2,
        "notes": ("Color a dot on each cup rim with marker. Give her the "
                  "pom-poms in a bowl. Drop each one into the matching cup. "
                  "If you don't have pom-poms, use buttons or even Lego "
                  "pieces — same principle."),
        "source": "Montessori sensorial — visual matching",
        "search_query": "Montessori color matching pom pom toddler",
    },
    {
        "id": "cup_stacking_letters",
        "name": "Cup Stack + Letter Hunt",
        "framework": "Play-based",
        "age_min": 3, "age_max": 5,
        "duration_min": 20,
        "materials": ["10 paper cups (write a letter on each)",
                      "blank paper", "marker"],
        "skill": "letter_recognition · gross_motor",
        "mess_level": 1,
        "setup_min": 5, "reset_min": 1,
        "notes": ("Write letters of her name (or simple words like CAT, DOG) "
                  "on cups. Scatter them. Call out a letter — she finds it "
                  "and stacks it. Builds early literacy via movement."),
        "source": "Lisa Murphy — Ooey Gooey Lady, play + literacy",
        "search_query": "alphabet cup stacking toddler letter recognition",
    },

    # ─── Practical life (Montessori) — kitchen ─────────────────────────────
    {
        "id": "wash_dishes",
        "name": "Real Dishwashing (Practical Life)",
        "framework": "Montessori",
        "age_min": 2.5, "age_max": 6,
        "duration_min": 25,
        "materials": ["small basin or sink", "1-2 plastic plates / cups",
                      "tiny squeeze of dish soap", "sponge", "towel",
                      "step stool"],
        "skill": "practical_life · sequencing · responsibility",
        "mess_level": 4,
        "setup_min": 3, "reset_min": 5,
        "notes": ("Real water, real soap, real dishes. Show her the steps "
                  "ONCE: wet, soap, scrub, rinse, place on towel. She'll "
                  "do it for 25+ min straight — practical-life work has "
                  "the longest attention span at this age. Apron + towel "
                  "on the floor saves the kitchen."),
        "source": "Maria Montessori — practical life is the gateway",
        "search_query": "Montessori toddler dishwashing practical life",
    },
    {
        "id": "fruit_chopping",
        "name": "Banana Chopping with Butter Knife",
        "framework": "Montessori",
        "age_min": 2.5, "age_max": 5,
        "duration_min": 15,
        "materials": ["1 banana (peeled)", "small plastic / butter knife",
                      "cutting board", "small bowl"],
        "skill": "practical_life · fine_motor · independence",
        "mess_level": 1,
        "setup_min": 1, "reset_min": 2,
        "notes": ("Banana is soft enough for a butter knife. Show her how "
                  "to hold the knife, cut down (not toward fingers), drop "
                  "slices into the bowl. She'll proudly serve YOU her "
                  "snack — Montessori 'help me do it myself.'"),
        "source": "Montessori — practical life",
        "search_query": "Montessori toddler banana cutting child knife",
    },
    {
        "id": "snack_pouring",
        "name": "Self-Serve Snack Station",
        "framework": "Montessori",
        "age_min": 2.5, "age_max": 5,
        "duration_min": 10,
        "materials": ["small jug of water (1-cup capacity)",
                      "small cup", "tray", "snack in a small bowl"],
        "skill": "practical_life · independence · spill_recovery",
        "mess_level": 2,
        "setup_min": 1, "reset_min": 2,
        "notes": ("Set up a low shelf or table corner with the jug + cup + "
                  "snack. She pours her own water, eats her own snack. "
                  "Spills are part of the lesson — keep a sponge nearby "
                  "and she'll learn to clean up. RIE + Montessori both "
                  "agree: independence builds confidence."),
        "source": "Janet Lansbury — Elevating Child Care",
        "search_query": "Montessori toddler snack station self serve",
    },

    # ─── Cardboard / recycling (Reggio loose parts) ────────────────────────
    {
        "id": "cardboard_box_house",
        "name": "Cardboard Box House",
        "framework": "Reggio",
        "age_min": 2, "age_max": 6,
        "duration_min": 60,
        "materials": ["large cardboard box (Amazon delivery)",
                      "markers / crayons", "tape", "(optional) blanket"],
        "skill": "imagination · spatial · long_play",
        "mess_level": 2,
        "setup_min": 5, "reset_min": 3,
        "notes": ("Cut a door + window. Hand her crayons — she decorates. "
                  "Drape a blanket inside for cozy. Lasts an hour easy at "
                  "her age. Reggio principle: the child uses 'a hundred "
                  "languages' to express. The box is a canvas, not a toy."),
        "source": "Reggio Emilia / Loris Malaguzzi",
        "search_query": "cardboard box fort toddler Reggio Emilia",
    },
    {
        "id": "loose_parts_tray",
        "name": "Loose Parts Sorting Tray",
        "framework": "Reggio",
        "age_min": 2.5, "age_max": 6,
        "duration_min": 30,
        "materials": ["muffin tin or ice cube tray",
                      "mixed small objects: buttons, bottle caps, dry beans, "
                      "pasta, coins, beads, small Legos (anything bigger "
                      "than her thumbnail — choking-safe)"],
        "skill": "sorting · classifying · open_ended_play",
        "mess_level": 2,
        "setup_min": 3, "reset_min": 3,
        "notes": ("Dump everything in a bowl, hand her the muffin tin. NO "
                  "instructions — let her sort by whatever criterion makes "
                  "sense to her (color, size, shape, mood). Reggio core "
                  "tenet: trust the child's own logic."),
        "source": "Reggio Emilia + Bev Bos — open-ended materials",
        "search_query": "Reggio loose parts sorting toddler activity",
    },
    {
        "id": "tape_track",
        "name": "Floor Tape Race Track",
        "framework": "Play-based",
        "age_min": 2, "age_max": 5,
        "duration_min": 30,
        "materials": ["1 roll masking tape or painter's tape",
                      "any toy cars / push toys"],
        "skill": "spatial · imagination · gross_motor",
        "mess_level": 1,
        "setup_min": 5, "reset_min": 3,
        "notes": ("Tape a road on the floor — straights, curves, intersection. "
                  "She drives cars on it for 30 min. Add a 'gas station' "
                  "(circle) and 'home' (square) for narrative. Painter's "
                  "tape removes cleanly from hardwood + carpet."),
        "source": "Lisa Murphy — Ooey Gooey",
        "search_query": "masking tape road floor toddler car play",
    },

    # ─── Water / sensory ───────────────────────────────────────────────────
    {
        "id": "water_transfer",
        "name": "Water Transfer with Sponges",
        "framework": "Montessori",
        "age_min": 2, "age_max": 4.5,
        "duration_min": 25,
        "materials": ["2 small bowls", "1 sponge",
                      "old towel underneath", "water"],
        "skill": "fine_motor · cause_and_effect · concentration",
        "mess_level": 4,
        "setup_min": 2, "reset_min": 5,
        "notes": ("Fill one bowl with water. Show: dip sponge, squeeze into "
                  "empty bowl, repeat until empty bowl is full. Hits the "
                  "Montessori 'work cycle' — kids find this oddly meditative. "
                  "Outdoors or on tile flooring."),
        "source": "Montessori practical life — water work",
        "search_query": "Montessori toddler sponge water transfer",
    },
    {
        "id": "frozen_treasures",
        "name": "Frozen Treasure Rescue (Ice Tray)",
        "framework": "Tinkergarten",
        "age_min": 2.5, "age_max": 5,
        "duration_min": 25,
        "materials": ["ice cube tray", "small toys (one per cube)",
                      "warm water in a small cup",
                      "salt (optional, melts faster)",
                      "tray or towel"],
        "skill": "problem_solving · cause_and_effect · patience",
        "mess_level": 3,
        "setup_min": "freeze overnight", "reset_min": 3,
        "notes": ("Freeze a small toy in each ice cube the night before. "
                  "Next day: she rescues them by pouring warm water / "
                  "sprinkling salt / tapping. Big STEM moment — phases of "
                  "matter, problem-solving."),
        "source": "Tinkergarten — sensory + nature",
        "search_query": "frozen toys ice rescue toddler sensory",
    },

    # ─── Whole-brain / emotion (Daniel Siegel + Big Little Feelings) ──────
    {
        "id": "feelings_chart",
        "name": "Build a Feelings Chart Together",
        "framework": "Big Little Feelings",
        "age_min": 3, "age_max": 6,
        "duration_min": 20,
        "materials": ["paper", "markers / crayons",
                      "(optional) printed face emojis"],
        "skill": "emotional_literacy · vocabulary",
        "mess_level": 1,
        "setup_min": 2, "reset_min": 1,
        "notes": ("Draw 4-6 faces: happy, sad, mad, scared, excited, frustrated. "
                  "She names each one. Hang it in her room. When a meltdown "
                  "starts, point to the chart: 'which face is your body "
                  "right now?'. Names the feeling = brain regulates faster "
                  "(Siegel's 'name it to tame it')."),
        "source": "Daniel Siegel + Tina Payne Bryson — Whole-Brain Child; "
                  "Big Little Feelings @biglittlefeelings",
        "search_query": "feelings chart toddler name it to tame it",
    },
    {
        "id": "calm_jar",
        "name": "DIY Calm-Down Jar",
        "framework": "Whole-Brain",
        "age_min": 3, "age_max": 7,
        "duration_min": 15,
        "materials": ["empty water bottle", "warm water",
                      "1-2 tbsp clear glue or hair gel",
                      "glitter / sequins / small foam shapes",
                      "hot glue (adult-only) to seal cap"],
        "skill": "emotional_regulation · sensory_calming",
        "mess_level": 3,
        "setup_min": 10, "reset_min": 3,
        "notes": ("Fill bottle 2/3 with warm water + glue + glitter. Shake = "
                  "swirling chaos. She watches it settle — counted-breath "
                  "regulation tool. Used by Montessori, RIE, Whole-Brain "
                  "Child practitioners alike. Hot-glue the cap."),
        "source": "Daniel Siegel — Whole-Brain Child",
        "search_query": "DIY calm down jar glitter toddler regulation",
    },

    # ─── Music + body movement ─────────────────────────────────────────────
    {
        "id": "rice_shaker",
        "name": "Homemade Rice Shaker (Music Time)",
        "framework": "Play-based",
        "age_min": 2, "age_max": 5,
        "duration_min": 15,
        "materials": ["empty plastic bottle (water bottle, sealed)",
                      "1/4 cup uncooked rice or lentils",
                      "tape over the cap"],
        "skill": "rhythm · cause_and_effect · gross_motor",
        "mess_level": 1,
        "setup_min": 2, "reset_min": 1,
        "notes": ("Pour rice in, seal cap with tape. Put on Carnatic music "
                  "or any nursery rhyme — she shakes along. Make TWO "
                  "shakers: one for her, one for you, dance together. "
                  "Music + movement = bilateral brain integration."),
        "source": "Bev Bos / Lisa Murphy — joyful play",
        "search_query": "homemade rice shaker toddler music instrument",
    },
    {
        "id": "freeze_dance",
        "name": "Freeze Dance",
        "framework": "Whole-Brain",
        "age_min": 2.5, "age_max": 8,
        "duration_min": 15,
        "materials": ["any music source"],
        "skill": "self_regulation · listening · gross_motor",
        "mess_level": 1,
        "setup_min": 0, "reset_min": 0,
        "notes": ("Play music — she dances. Stop the music — she freezes. "
                  "Builds inhibitory control (the same brain function she'll "
                  "need to NOT touch the hot stove). Best 5-min cool-down "
                  "before screen time or bedtime."),
        "source": "Whole-Brain Child — executive function games",
        "search_query": "freeze dance toddler inhibitory control",
    },
]


# Influencer / framework reference list — surfaced on the page so the
# user can dig deeper into the parenting research.
INFLUENCERS: list[dict] = [
    {
        "name": "Maria Montessori",
        "framework": "Montessori",
        "blurb": "Italian physician who in 1907 invented child-led, mixed-age "
                 "classrooms. Practical-life + sensorial activities are the "
                 "core of toddler/preschool Montessori. Her books still "
                 "the bedrock of every modern home Montessori setup.",
        "links": [
            {"label": "The Absorbent Mind (book)", "url": "https://www.goodreads.com/book/show/76327.The_Absorbent_Mind"},
            {"label": "How We Montessori (blog)", "url": "https://www.howwemontessori.com/"},
        ],
    },
    {
        "name": "Janet Lansbury",
        "framework": "RIE",
        "blurb": "Magda Gerber's foremost student. RIE = Resources for "
                 "Infant Educarers. Treats kids as full humans capable of "
                 "their own work + emotions. Famous for 'sportscasting' "
                 "(narrating without judgment). Don't sweat the fuss — "
                 "they're processing.",
        "links": [
            {"label": "Janet Lansbury — Elevating Child Care", "url": "https://www.janetlansbury.com/"},
            {"label": "Unruffled Podcast", "url": "https://www.janetlansbury.com/podcast-audio/"},
        ],
    },
    {
        "name": "Big Little Feelings",
        "framework": "Big Little Feelings",
        "blurb": "Kristin Gallant (parenting coach) + Deena Margolin "
                 "(child therapist). Specifically for the 1-5 emotional "
                 "wave — tantrums, big feelings, boundaries. Highly "
                 "practical, IG-friendly, evidence-based.",
        "links": [
            {"label": "@biglittlefeelings (Instagram)", "url": "https://www.instagram.com/biglittlefeelings/"},
            {"label": "Winning the Toddler Stage course", "url": "https://www.biglittlefeelings.com/"},
        ],
    },
    {
        "name": "Dr. Daniel Siegel + Tina Payne Bryson",
        "framework": "Whole-Brain",
        "blurb": "Whole-Brain Child + No-Drama Discipline. UCLA neuroscience "
                 "made parent-friendly. 'Name it to tame it', upstairs vs "
                 "downstairs brain, connection-before-correction. The "
                 "research foundation under everything Big Little Feelings "
                 "builds on.",
        "links": [
            {"label": "The Whole-Brain Child (book)", "url": "https://www.drdansiegel.com/books/the-whole-brain-child/"},
            {"label": "No-Drama Discipline (book)", "url": "https://www.drdansiegel.com/books/no-drama-discipline/"},
        ],
    },
    {
        "name": "Lisa Murphy (Ooey Gooey Lady)",
        "framework": "Play-based",
        "blurb": "ECE researcher and seven-essentials-of-play advocate. "
                 "Big on messy / hands-on play, anti-screen, anti-overschedule. "
                 "Talks about how kids need to MAKE things, not consume them.",
        "links": [
            {"label": "Ooey Gooey Inc", "url": "https://www.ooeygooey.com/"},
            {"label": "The Ooey Gooey Handbook (book)", "url": "https://www.amazon.com/Ooey-Gooey-Handbook-Lisa-Murphy/dp/0974930105"},
        ],
    },
    {
        "name": "Bev Bos",
        "framework": "Play-based",
        "blurb": "Iconic preschool teacher (Roseville Community Preschool, "
                 "CA). 'If it hasn't been in the hand and the body, it can't "
                 "be in the brain.' Open-ended materials over toys, mess "
                 "over neat, joy over compliance.",
        "links": [
            {"label": "Don't Move the Muffin Tins (book)", "url": "https://www.amazon.com/Dont-Move-Muffin-Tins-Hands/dp/0942702220"},
        ],
    },
    {
        "name": "Reggio Emilia approach",
        "framework": "Reggio",
        "blurb": "Italian post-WWII pedagogy from the city of Reggio Emilia. "
                 "Loris Malaguzzi's 'hundred languages of children' — kids "
                 "express understanding via art, building, dramatic play, "
                 "movement, not just words. Loose parts are central.",
        "links": [
            {"label": "An Everyday Story — Reggio at home", "url": "https://www.aneverydaystory.com/beginners-guide-to-reggio-emilia/"},
        ],
    },
    {
        "name": "Tinkergarten",
        "framework": "Tinkergarten",
        "blurb": "Outdoor / nature-based early childhood program. Founder "
                 "Meghan Fitzgerald. Everything is sensory and outdoor — "
                 "puddle science, leaf sorting, mud kitchen. Backed by "
                 "child-development research from the Center on the "
                 "Developing Child at Harvard.",
        "links": [
            {"label": "Tinkergarten — Free Activities", "url": "https://tinkergarten.com/diy-activities"},
        ],
    },
]


def by_id(aid: str) -> dict | None:
    for a in ACTIVITIES:
        if a.get("id") == aid:
            return a
    return None


def filter_activities(*, framework: str | None = None,
                      mess_max: int | None = None,
                      duration_max: int | None = None,
                      skill: str | None = None,
                      age: float | None = None,
                      exclude_ids: list[str] | None = None) -> list[dict]:
    out = list(ACTIVITIES)
    if framework:
        out = [a for a in out if a.get("framework") == framework]
    if mess_max is not None:
        out = [a for a in out if (a.get("mess_level") or 0) <= mess_max]
    if duration_max is not None:
        out = [a for a in out if (a.get("duration_min") or 999) <= duration_max]
    if skill:
        out = [a for a in out if skill in (a.get("skill") or "")]
    if age is not None:
        out = [a for a in out
               if (a.get("age_min", 0) <= age <= a.get("age_max", 99))]
    if exclude_ids:
        ex = set(exclude_ids)
        out = [a for a in out if a.get("id") not in ex]
    return out
