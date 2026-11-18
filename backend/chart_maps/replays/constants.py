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
