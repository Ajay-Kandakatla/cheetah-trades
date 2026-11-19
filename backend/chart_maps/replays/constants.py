"""🎬 Replays — constants (replays spec §3.1, WP-BE, 2026-11-17).

Ajay 2026-11-17 ~22:30 ET, verbatim: "Can you store the videos in to the app please".
His standing 11-16 rule: "Remove all the videos that are not till 8pm I only wanna see ones from 4 AM to 8 pm please"
→ only sidecars whose `window == FULL_DAY_WINDOW` are ever listed.

Every string the frontend prints lives here or in `store.py`; the frontend types none. Setup words come from the 🚩
`SUBS` triples and page words from 👀 Watch's `FRAME_WORDS` — never retyped. No rule, gate, threshold, push or trade.
A replay is for his eyes, not a signal. UNMEASURED.
"""
from __future__ import annotations

import re

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import constants as WC

TAB = "replays"
TAB_LABEL = "🎬 Replays"                                   # MINE — HIS CALL #2
TITLE = TAB_LABEL
API_PATH = "/chart-maps/replays"
API_VIDEO_PATH = API_PATH + "/video/{day}/{name}"
ROOT_ENV = "REPLAYS_DIR"
ROOT_DEFAULT = "/data/replays"                             # the container side of the compose binds (WP-OPS pins equality)
VIDEOS_SUB, RS_SUB, LEDGER_FILE = "videos", "rs_potentials", "ledger.csv"
FULL_DAY_WINDOW = "04:00-20:00 ET"                         # his 11-16 rule; == replay_video.py:1263 after_hours literal
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$", re.ASCII)     # used with fullmatch (no trailing-newline slip, ASCII digits)
FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.mp4$")   # no '/', no leading '.', .mp4 only
RS_WORD = "🎾 Reversal Squeeze potential"                   # == replay_video.py:67 (pipeline-owned; test pins the literal)
MOVER_WHY_PREFIX = "biggest mover of"                      # == replay_video.py:1199 words — the ONLY marker the pipeline writes
APLUS_SUFFIX = "|aplus"                                    # ring_id tail of an A+ ring
GROUPS = (("aplus_winners", "🏁 A+ winners"), ("aplus_losers", "A+ losers"),
          ("rs_potentials", "🎾 Reversal Squeeze potentials"), ("biggest_mover", "biggest mover"),
          ("other", "other"))                               # the ask's words, in the ask's order
# Ajay 2026-11-18, verbatim: "Also on the videos categorize winners and losers as categories and then remove 1 mins from
# them". (1) A carried after-close A+ ring (rang after the close, graded on the next session) now files under 🏁 A+
# winners / A+ losers by its grade, like any A+ ring (it used to sit under "other" — HIS CALL #3 of 11-17, answered);
# "other" keeps only an ungraded ring. (2) The 🚩 1-minute page retired 2026-11-18 ("stop 1 min tab"): its reels and its
# 🎾 tracker rows are never listed (they stay on disk).
EXCLUDED_PAGES = ("gajjala_1m",)
GROUP_KEYS = tuple(k for k, _ in GROUPS)
PAGE_WORDS = {"gajjala": WC.FRAME_WORDS["5m"], "gajjala_1m": WC.FRAME_WORDS["1m"]}
SETUP_TEXT = {k: f"{e} {l}" for k, e, l in GC.SUBS if k in GC.SETUPS}
WINDOW_NOTE = f"Only replays that run {FULL_DAY_WINDOW} are listed."
EMPTY_DAY_TEXT = f"No {FULL_DAY_WINDOW} replays for this session."
NO_FOLDER_TEXT = "The replay folder is not mounted on this server."
RS_TITLE = "🎾 Reversal Squeeze potentials — tracker"
RS_NOTE = "descriptive — UNMEASURED, not an edge; no placebo, so no average or median return is printed"   # == rs_potentials/<date>.md line 11
RS_EMPTY_TEXT = "No 🎾 tracker rows for this session."
RS_EMPTY_CELL = "—"
RS_COLUMNS = (("symbol", "Symbol"), ("page", "Page"), ("first_seen_et", "First stored"), ("first_kind", "Kind"),
              ("first_trigger", "Trigger"), ("first_stop", "Stop"), ("push_et", "🧠 push"), ("push_grade", "🧠 grade"),
              ("went_aplus_et", "A+ this page"), ("aplus_setup", "A+ setup"), ("other_page_aplus_et", "A+ other page"),
              ("triggered_et", "Triggered"), ("stop_before_trigger", "Stop first"),
              ("high_before_stop_pct", "High before stop %"), ("high_after_pct", "High after %"),
              ("close_2000_pct", "20:00 %"), ("video", "Video"))   # the .md table's set — HIS CALL #6
VIDEO_HEADERS = {"Content-Encoding": "identity",           # GZipMiddleware trap (spec §1.3) — pinned by contracts
                 "Cache-Control": "private, no-transform", # Cloudflare edge never caches `private` (spec §1.3) — pinned by contracts
                 "Accept-Ranges": "bytes"}
LISTING_HEADERS = {"Cache-Control": "no-store"}
CARD_ERRORS = (TypeError, ValueError, IndexError, KeyError, AttributeError)   # one bad sidecar → skipped_bad, never a 500

# ── 🏆 Past winners (spec pastwinners §3.5, WP-APP, 2026-11-18) ───────────────────────────────────────────────────────
# Ajay 2026-11-18 ~21:45 ET, verbatim: "can you work on todays videos and also..  Winners in general from the past".
# Two more folders under videos/ (already inside the :ro bind): `winners/` (market-wide single-day winner reels, one
# session 04:00-20:00 ET at 45x) and `multiday/` (the 15 multi-day runner reels). The KIND comes from the FOLDER, never
# from sidecar text; every served word is composed here from these constants + sidecar NUMBERS (no sidecar free text).
# Hand-picked winners (survivorship): descriptive, UNMEASURED, not a signal.
WINNERS_API_PATH = API_PATH + "/winners"
WINNERS_VIDEO_PATH = WINNERS_API_PATH + "/video/{sub}/{name}"
WINNER_SUBS = (("winners", "single_day", "single-day"), ("multiday", "multi_day", "multi-day"))   # folder, kind, chip
WINNER_SUB_KEYS = tuple(s for s, _k, _t in WINNER_SUBS)
MULTI_WINDOW_PREFIX = FULL_DAY_WINDOW + " x "              # replay_multiday.py:413 "04:00-20:00 ET x N sessions (...)"
NON_SIDECAR_JSON = ("jobs.json", "runners.json", "winners.json")
WINNERS_TITLE = "🏆 Past winners"                            # MINE — == FE RP_WINNERS_TITLE (contract-pinned)
WINNERS_NOTE = (f"Market-wide stocks whose high reached +{GC.SA_BIG_RUNNER_PCT:g}% or more over the prior close in one "
                f"session (volume {GC.SCAN_MIN_VOLUME:,}+, prior close ${GC.SCAN_MIN_PRICE:g}–${GC.SCAN_MAX_PRICE:g}), "
                "rung by us or not, plus the multi-day runners. Hand-picked winners (survivorship): descriptive, "
                "UNMEASURED, not a signal. Gains are quoted on the close.")
WINNERS_WINDOW_NOTE = f"Only replays that run {FULL_DAY_WINDOW} (every session) are listed."
WINNERS_EMPTY_TEXT = "No past-winner replays yet."
GAIN_WORDS = {"single_day": "on the close", "multi_day": "best close vs the day before"}
HIGH_WORDS = {"single_day": "high", "multi_day": "run high"}
SPIKE_WORDS = "⚠ high more than {x:g}× the close — a spike print?"         # x = the sidecar's spike_x
TODAY_TOP_WORDS = "top {n} mover of its day (high under +{pct:g}%)"         # pct = GC.SA_BIG_RUNNER_PCT
FORCED_WORDS = "your example — not a +{pct:g}% run"
WINNER_PICKS = ("plus100", "today_top")                     # the finder's two `pick` values (spec §3.1 select)
