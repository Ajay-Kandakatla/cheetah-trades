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

# ── 🏆 past-winner tag (2026-11-22) ─────────────────────────────────────────────────────────────────────────────────
# Ajay 2026-11-22, verbatim: "MEDS was a part winner that went up after hours.. Please actually add a past winner tag in
# our new ones looks for past winnings please if found again.." A day-folder card (and a 🏆 card) whose symbol has an
# accepted 🏆 reel that ENDED strictly before the card's own session carries a served `past_winner` list (newest first,
# at most PAST_WIN_MAX) + `past_winner_count`. No look-ahead: a multi-day run counts only from its LAST session. A tag,
# not a gate: no push, no rank, no filter. Descriptive, UNMEASURED.
PAST_WIN_MAX = 3                                             # "at most 3" — the ask's number (spec), not a rule
PAST_WIN_DAY_WORDS = "🏆 past winner"                        # the day-folder chip: "🏆 past winner 09-16 +275%"
PAST_WIN_BEFORE_WORDS = "🏆 won before"                      # on a 🏆 card: an EARLIER win of the same symbol
PAST_WIN_MORE_WORDS = "+{n} more"                            # n = past_winner_count − the entries served

# ── 🏆 setup + timing on the single-day winners (2026-11-22) ────────────────────────────────────────────────────────
# Ajay 2026-11-22, verbatim: "can you categorize past winners like some are kiss and fly based and some might be VCP
# based some might be horizontal faded.. Do we have those metrics? also reversal squeeze is mainly what I look for." →
# "yes please" (group / filter the 🏆 list by setup, 🎾 first). On the first-hour runners: "dont't remove but add a tag
# but sort by EOD and Intraday ones on the top". The LABELLER (eod-audits/research/2026-11-22_winner_setup_labels/
# label_winners.py + the time-of-day study) writes `setups` + `timing` into each single-day sidecar; the server only
# READS them (one engine — no setup or bucket is computed here). An unknown key / class / bucket → treated as absent and
# counted in `skipped_label`. A LABEL — descriptive, UNMEASURED; no gate, no push, no rank of setups.
WIN_SETUP_ORDER = ("reversal_squeeze", "intraday_vcp", "kiss_fly", "bull_flag", "horizontal_fade")   # the ask's order (🎾 first)
WIN_SETUP_NONE = "none"                                      # a labelled reel with no Gajjala primary (float-gated / none / no peak)
WIN_SETUP_WORDS = {**{k: SETUP_TEXT[k] for k in WIN_SETUP_ORDER},   # the 🚩 SUBS words (emoji + label), never retyped
                   WIN_SETUP_NONE: "no Gajjala setup"}
WIN_SETUP_FILTER_KEYS = WIN_SETUP_ORDER + (WIN_SETUP_NONE,)  # the filter row after 'All'
WIN_SETUP_ALL = "all"
WIN_SETUP_ALL_WORDS = "All"
# The labeller's classes (label_winners.CLASSES). A class WITH a primary setup vs one WITHOUT — a label that mixes them
# (e.g. a 🎾 primary on a "🎾 float-gated" reel) is malformed: absent + skipped_label. 🎾 float-gated is NEVER a 🎾 count.
WIN_CLASSES_WITH_SETUP = ("A+ before peak", "armed only", "after the peak")
WIN_CLASSES_NO_SETUP = ("🎾 float-gated", "none", "no peak")
# 2026-11-22 review fix (b): the label's peak is the 09:30–20:00 PEAK MINUTE, not the card's "+X% high" chip (that one is
# the 09:30–16:00 day bar and differs on 63 cards) — so every label word says "peak", never "high".
WIN_CLASS_WORDS = {"A+ before peak": "🎯 A+ before the peak", "armed only": "armed before the peak, no A+",
                   "after the peak": "read only after the peak", "🎾 float-gated": "🎾 float-gated — not a 🎾 label",
                   "none": None, "no peak": "no 09:30–20:00 peak"}   # "none" → the setup words already say it
WIN_STOPPED_WORDS = "⛔ stopped before the peak"
# 2026-11-22 review fix (a): a reel whose labeller `chips` (every setup armed / A+ that day) carry 🎾 beside another
# primary also passes the 🎾 filter (16 reels on 11-22). Only 🎾 — the ask's "reversal squeeze is mainly what I look for".
# A no-setup class (🎾 float-gated / none / no peak) must carry NO chip, so a float-gated reel never counts as 🎾.
WIN_CHIP_MATCH = ("reversal_squeeze",)
WIN_CHIP_WORDS = "also {words}"                              # a secondary chip: "also 🎾 Reversal Squeeze" — MINE
# timing buckets of the 09:30–20:00 peak minute, written by the labeller (eod-audits/research/2026-11-22_winner_time_of_day)
WIN_TIMING_ORDER = ("eod", "intraday", "first_hour")         # his "sort by EOD and Intraday ones on the top"; unknown LAST
WIN_TIMING_WORDS = {"eod": "🌙 end of day", "intraday": "☀️ intraday", "first_hour": "🌅 first hour"}
WIN_TIMING_TEXT = "{words} (peak {t})"                       # t = the labeller's peak minute HH:MM (ET)
# == label_winners.TIMING_BUCKETS (lower bound inclusive, upper exclusive; a test pins equality with the labeller's
# source). Review fix (c): a served bucket that disagrees with its own peak minute is a bad label (skipped_label).
WIN_TIMING_BUCKETS = (("first_hour", "09:30", "10:30"), ("intraday", "10:30", "15:00"), ("eod", "15:00", "20:00"))
HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$", re.ASCII)

# ── 🏆 one row per stock (2026-11-22) ───────────────────────────────────────────────────────────────────────────────
# Ajay 2026-11-22, verbatim: "Just AKAN can you please bring its past winner session to like from MAY multiday when ever
# a stock has multiday group it in the same role for past winners please." · "CLRO another example add all the videos
# may be click them together". The 🏆 block is ONE ROW PER SYMBOL holding every accepted reel of that symbol (single-day
# and multi-day). A win is counted by the past-winner index's one-per-run rule (a multi-day run absorbs the single-day
# reels on its days). Rows order: the newest single-day reel's timing (eod → intraday → first_hour → unknown), then the
# newest win desc, then the best close gain desc, then the symbol. Words only — no gate, no rank of setups.
WIN_ROW_WINS_WORDS = ("{n} win", "{n} wins")                 # singular, plural — MINE
WIN_ROW_NEWEST_WORDS = "newest {d}"                          # d = "Thu 2026-11-12" — MINE

# ── 🏆 chip → jump to that win's replay at its peak (2026-11-22) ───────────────────────────────────────────────────
# Ajay 2026-11-22, verbatim: "New feature when I click on this past winner tag take me to that video so change the date
# and focus me on that video at that. time". Navigation only: no gate, no push, no rank, no label change. UNMEASURED.
WINDOW_T0, WINDOW_T1 = FULL_DAY_WINDOW[:5], FULL_DAY_WINDOW[6:11]      # "04:00", "20:00" — never retyped
SEEK_SESSION_SEC = ((int(WINDOW_T1[:2]) * 60 + int(WINDOW_T1[3:])) - (int(WINDOW_T0[:2]) * 60 + int(WINDOW_T0[3:]))) * 60   # 57600
SEEK_HOLD_SEC = 3.0                # == eod-audits/replays/replay_gif.py HOLD_MS / 1000 — the END hold of every reel (a test pins the source)
SEEK_EPS = 1e-6                    # float-compare tolerance in SECONDS — arithmetic hygiene, no market meaning. The renderer adds the
                                   # frame offset to an epoch ≈ 1.8e9 (one float step there = 2.4e-7 s), so an offset within 1e-6 s
                                   # of a minute start IS that minute start. MINE.
SEEK_WORDS = "⏩ opens at the peak minute, {t} ET"                       # t = the labeller's peak minute HH:MM — MINE
SEEK_NONE_WORDS = "no peak time on this replay — it opens at the start"  # MINE
JUMP_MISSING_WORDS = "That replay is no longer listed."                  # MINE
assert HHMM_RE.fullmatch(WINDOW_T0) and HHMM_RE.fullmatch(WINDOW_T1)
