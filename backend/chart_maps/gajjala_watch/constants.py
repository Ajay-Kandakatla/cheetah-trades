"""👀 Gajjala's Watch — constants (2026-11-15). Ajay, verbatim: "I need dashboard to add tickers to Gajjalas watch
dashboard. I wanna be able to remove and add remove tickers from the dashboard. When I add a ticker I need 1 min 3 min
and 5 min charts... Not the SEPA and I need clear distinction or may be a brighter and thicker 21 EMA and 9 EMA, from
the videos I notice that when ever 9 EMA crosses over 21 EMA on uptrend is where the bullish momentum started I need
alerts on these from 1 min to I can be ready... I think the cross over is slow but once it picks up its very rapid.."
Every number is the NAME of an existing constant or MINE with its HIS CALL number. UNMEASURED."""
from __future__ import annotations
import sys
from chart_maps.gajjala import constants as GC

TAB = "gajjala_watch"
TAB_LABEL = "👀 Gajjala's Watch"                      # MINE — HIS CALL #9
API_PATH = "/chart-maps/gajjala-watch"
API_SYMBOL_PATH = API_PATH + "/symbols/{symbol}"
API_LIST_PATH = API_PATH + "/symbols"                     # ➕/➖ card button: the owner's names only (2026-11-15)
API_LIVE_PATH = API_PATH + "/live"                       # 👀 LIVE (2026-11-16): the owner registers the board's live interest (== FE GGW_LIVE_PATH)
# 2026-11-23 (Ajay, verbatim: "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board"): was
# 1 / 3 / 5 since 11-15 ("1 min 3 min and 5 min charts") — order = served order (1m on top, the 5m + 15m pair)
FRAMES = (("1m", "1min"), ("5m", "5min"), ("15m", "15min"))
FRAME_WORDS = {"1m": "1-min", "5m": "5-min", "15m": "15-min"}
AXIS_FRAME = "1m"                                      # the frame whose bars set the tile's axis end (C1.7)
MAX_SYMBOLS = GC.GG_WATCH_N                            # HIS CALL 2026-11-18 "18 (Recommended)": GG "watches 18 stocks simultaneously" (was 12 = MINE, = signal_lab)
PUSH_FRAMES = ("1m",)                                  # his words "I need alerts on these from 1 min" — 5m / 15m = HIS CALL #2
# 📈 VWAP + 📐 daily zones (2026-11-23, spec vwapzones rev 2 — Ajay, verbatim: "can you add vwap and supply demand zone in
# the daily time frame on the watch list please" · "Add vwap and supply demand too"). DISPLAY ONLY — nothing gates, sorts,
# rings or caps on any of this. UNMEASURED.
VWAP_ON = True                      # his word (asked twice)
VWAP_SESSIONS = ("rth",)            # HIS CALL #1 (BLOCKING) — one of vwap.SESSION_SETS; ("rth",) = vwap_session's own default argument
VWAP_TONE, VWAP_LABEL = "vwap", "VWAP"
VWAP_DP = 6                         # = bars._masked_ema's rounding
ZONES_ON = True                     # his word
ZONES_PER_SIDE = None               # None = price_zones.MAX_ZONES_PER_SIDE read BY NAME at call time; an int = HIS CALL #3
ZONES_MAX_NEW = GC.DAILY_MAX_NEW_PER_PASS   # daily reads per 5-minute slot, retries included (the 🎾 chip's cap)
ZONES_PERIOD = "2y"                 # = zone_store.warm's loader period (zone_store.py:312) = index_zones.py:803 — a source-read test pins both [C5]
ZONE_KINDS = ("demand", "supply")   # == price_zones band kinds
ZONE_BAND_KIND = {"demand": "board_demand", "supply": "board_supply"}   # the SERVED CmBand kind = the house look of the board's bands [C9]
LEVELS_STATES = ("ok", "none", "retry", "pending")
LEVELS_MODULE = "chart_maps.gajjala_watch.levels"   # imported LAZILY by payload.py and loop.py (loop.py does not import payload)
PUSH_MODES = GC.FADE_CROSS_PUSH_MODES                  # ("off", "live")
PUSH_MODE = "live"                                     # his words "I need alerts on these"
PUSH_KIND = GC.FADE_CROSS_PUSH_KIND                    # HIS CALL #7 — the 🧠 kind (gajjala_potential); no new OWNER_KEEP_SET kind
LATCHES = ("session", "cross")
LATCH = "session"                                      # MINE — HIS CALL #3: once per ticker / frame / session
UPTREND_FILTERS = (None, "k5_cross_frame", "k5_5m")
UPTREND_FILTER = None                                  # HIS CALL #4 — he said "on uptrend"; None = no filter, K5 shown + recorded
HELD_REASONS = ("off", "missed_fetch", "suppressed_closed", "suppressed_premarket", "suppressed_first15",
                "suppressed_window", "under_floor", "not_uptrend", "no_store", "no_target", "failed",
                "suppressed_auto")                      # 🤖 2026-11-17 — appended LAST (= AUTO_HELD_REASON, auto.hold_crosses)
ENABLED = True
ENV_ENABLED = "GAJJALA_WATCH_ENABLED"                  # "0" lowers it (tests/conftest assigns "0")
CLAIM_PREFIX = "GGW"                                   # never "GG:" — the 🏁 reads GG: claims
COLL_LIST, COLL_TILES, COLL_ALERTS, COLL_STATE = ("gajjala_watch_list", "gajjala_watch_tiles",
                                                  "gajjala_watch_alerts", "gajjala_watch_state")
LIST_DOC_ID, STATE_LATEST_ID, LOOP_STATE_ID = "owner", "latest", "loop"   # the lease doc id is store.LEASE_ID
# 🤖 auto section (2026-11-17 — Ajay: "add more stocks in to watch list … portentials from Gajjals's 1 min and regular and
# also Audited potentials with good volume to Watchlist on an interval.. Remove as they are not progressing"). auto.py is
# the ONE engine; every number below is the NAME of an existing constant or MINE with its HIS CALL number. UNMEASURED.
AUTO_DOC_ID = "auto"                               # the SECOND doc of COLL_LIST (never the owner doc)
AUTO_MAX_SYMBOLS = GC.GG_WATCH_N                   # MINE to reuse (HIS CALL #1): GG "watches 18 stocks simultaneously"
AUTO_SOURCES = ("gajjala", "gajjala_1m", "gga")    # == (V.GG5.key, V.GG1.key, V.GGA.key) — a test pins equality
AUTO_SOURCE_WORDS = {"gajjala": "🚩 5-min", "gajjala_1m": "🚩 1-min", "gga": "🧪"}
AUTO_READ_SOURCES = ("gajjala", "gajjala_1m")      # the two STORED read sets; "gga" borrows GG5's (variant.GGA.borrows)
AUTO_MIN_VOLUME = GC.K11_MIN_SESSION_VOLUME        # GG's floor, the SAME number cross_alerts holds the push under (HIS CALL #2)
AUTO_VOLUME_SOURCES = ("scan", "tracker")          # [C2] the scan row, else GG5's tracker last.session_volume (K11's number)
AUTO_REMOVE_STATES = ("back_under", "stop_printed")            # [C1] breakout_state.STATES — "not progressing" (HIS CALL #3)
AUTO_KEEP_STATES = ("waiting", "broke_vol", "broke_quiet", "broke_unjudged")  # [C1] ⏸ = holding above the trigger → kept
AUTO_DROP_GRACE_SEC = GC.PASS_CADENCE_SEC          # [C3] SUPERSEDED 2026-11-17 12:55 (accumulate): NOTHING reads it for removal
                                                   # now — a lapsed name stays; kept for the old docs / tests only
AUTO_REMOVED_SHOWN = AUTO_MAX_SYMBOLS              # [C3] the newest removals served (every event stays in the doc)
AUTO_PUSH_MODES = GC.FADE_CROSS_PUSH_MODES         # ("off", "live")
AUTO_PUSH_MODE = "off"                             # HIS CALL #4 — auto names never ring the 1-min cross push; "live" = his word
AUTO_HELD_REASON = "suppressed_auto"               # == HELD_REASONS[-1] (a test pins it)
AUTO_TAG = "🤖"
# 🎯 A+ seats (2026-11-17 ~17:20 ET, spec ggwaplus2 WP-1 — Ajay, verbatim: "Push new Apluses immediately in to watch list
# and an alert for me please Missed AKAN and GP"). A name in tab.MARKED_STATES on any of the three boards (the 🎯 tag's
# ONE classifier) takes a seat at the next loop minute. No new number. UNMEASURED.
AUTO_APLUS_WHY = "aplus"        # the entry's `why` (absent = a 🧠 potential entry; old docs carry none)
AUTO_APLUS_EVICTS = True        # HIS CALL #1 — an A+ name takes a seat ahead of potentials (lapsed first, then oldest-added); False = free seats only
AUTO_APLUS_STAYS = True         # HIS CALL #2 — ↩️/✖️ never remove an A+ name (the 🎯 chip says "A+, then stopped"); only his ×
# 🚫 his broker list on the Watch (2026-11-19, spec watchfid — Ajay, verbatim: "Add a button to say not in fidelity, AZI and
# CHSN are not in fidelity don't add them to watch list"). auto.broker_gate reads THE list (gajjala.store.broker_flags). UNMEASURED.
AUTO_SKIP_NOT_ELIGIBLE = True             # his word 2026-11-19 — a name on his 🚫 list never takes a NEW 🤖 / 🎯 seat
AUTO_NOT_ELIGIBLE_REMOVES = True          # HIS CALL #2 (spec watchfid) — a seated 🧠 potential that joins his list leaves next minute
AUTO_NOT_ELIGIBLE_REMOVES_APLUS = False   # HIS CALL #3 — False keeps his 11-17 call: an A+ seat leaves only on his ×
ARGV_LOOP = (sys.executable, "-m", "chart_maps.gajjala_watch.loop", "--loop")    # = ops/docker_watchdog CRON_DETACHED_CHILD_ARGS entry
ARGV_BUILD = (sys.executable, "-m", "chart_maps.gajjala_watch.loop", "--build")  # the API's add-time child; builds every pending name
# 2026-11-19: the in-window add-time child — only names with no tile doc, or added after their tile doc's last write
ARGV_BUILD_NEW = ARGV_BUILD + ("--new-only",)
PROC_NAME_LOOP, PROC_NAME_BUILD = "gajjala-watch-loop", "gajjala-watch-build"


def live_audience() -> frozenset:
    """👀 LIVE (2026-11-16, Ajay: "Can you make the watch list charts live please"): the ONE audience of the watch's
    `gajjala.update` batches — the primary owner's lower-cased email, the SAME identity `api._is_owner` gates the board
    with (ollama_chat.api.PRIMARY_ADMIN_EMAIL). Imported LAZILY so this module's top keeps importing only `sys` + `GC`
    (the cron child's import graph is unchanged). Broadcasting to the household instead = HIS CALL #2."""
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    return frozenset({PRIMARY_ADMIN_EMAIL.strip().lower()})

# ── 🗂 sections · 📅 ran last session · 📅 previous-day runners strip (2026-11-22, spec watch_org rev 4) ── Ajay 2026-11-22:
# "Manual ones I add them need to be on top then auto intraday.. every month I want previous say winners sorted and  remove
# hot sectors mess from Gajjalas top view I need a new thing there.. use that space between the parent tab of Gajjala and
# watch tab to be for previous day runners but remove them if they don’t run the current day". LAYOUT + served labels + a
# display strip: no gate, push, cap, eviction or add rule reads any of this. Descriptive, UNMEASURED. "every month" is read
# as "every morning" (the strip refreshes every session) — nothing monthly is built.
SECTIONS_ON = True                                   # MINE — HIS CALL #9: False = the 11-21 payload byte for byte
SECTION_KEYS = ("yours", "aplus", "auto")            # his 11-22 order (👤 first, then the 🤖 names) [D3: autoadd_spec APPENDS "ran"]
SECTION_ORDER = SECTION_KEYS
RAN_MIN_PCT = 40.0                                   # HIS answer 11-22 "+40% vs prior close" (11-21 "around 40 to 100%")
RAN_PCT_ROUND = 4                                    # = the scanner's change_pct rounding — EVERY compare (+40 and +25) at this [D5]
PCT_SHOW_PLACES = 1                                  # a % printed beside its bar is FLOORED to this, never rounded across it [D5]
BAR_PRE, BAR_AH = "pre", "ah"                        # bars5 `s` values; absent = regular (bars.py / support.py)
BAR_MIN = 5                                          # bars5 are 5-minute, RIGHT-labelled (bars.py:4-5); a test pins = the frame
RUNNERS_STRIP_ON = True                              # MINE — HIS CALL #9
RUNNERS_LEAVE_PCT = GC.SCAN_MIN_CHANGE_PCT           # GG S8 19:51 "at least minimum 25% change" — "runs today" (HIS CALL #3)
RUNNERS_STALE_SEC = 2 * GC.PASS_CADENCE_SEC          # MINE — HIS CALL #3 [D6]: a today read older than two passes judges nothing
RUNNERS_FOLD_AT = 8                                  # MINE — HIS CALL #5 (desktop; the rest behind "+n more")
RUNNERS_FOLD_AT_PHONE = 3                            # MINE — HIS CALL #5 [D7]: the phone's folded line = count + top 3 (SYM + gain)
RUNNERS_PAST_WORDS = "🏆"                             # the strip's short prefix handed to replays.past_wins_before
RUNNERS_SCAN_FIELDS = {"symbol": 1, "date": 1, "held": 1, "last.prev_close": 1, "last.day_c": 1, "last.tape_session": 1}
RUNNERS_READ_FIELDS = {"symbol": 1, "date": 1, "at": 1, "tile.bars5": 1, "ctx.float": 1}   # `at` = the pass stamp [D6]
API_RUNNERS_PATH = API_PATH + "/runners"             # == FE GG_RUNNERS_PATH (contract)
SCAN_SESSION_AFTER = "afterhours"                    # `last.tape_session` once the day bar is frozen (scanner.py:189-190)
ORG_NOTE = "descriptive — UNMEASURED; a label, never a gate, push, cap or add rule"
# words — every one MINE (HIS CALL #7); `{open}` / `{end}` / `{cut}` / `{stale_min}` are BUILT at format time
# (runners.clock_words: daytrading.data ET_RTH_OPEN / ET_AFTERHOURS_CLOSE, potential._mute_end_hhmm, RUNNERS_STALE_SEC)
SECTION_WORDS = {"yours": "👤 Your names", "aplus": "🎯 A+", "auto": "🤖 Added today"}
SECTION_TEXT = "{title} · {n}"
SECTION_HINTS = {
    "yours": "Names you added, newest first. Names added before 11-19 carry no time.",
    "aplus": ("🤖 added these because a Gajjala board read them A+ this session (or promoted a 🧠 potential when it went "
              "A+). They stay all session, a stop included. Your own A+ names stay in 👤 with their 🎯 chip."),
    "auto": ("🤖 adds this session, newest first — each tile says when it was added. 📅 on a tile = it ran last session "
             "({date}); a label, not why it was added."),
}
WHEN_TEXT = {"premarket": "{verb} premarket {at}", "intraday": "{verb} {at}", "after_hours": "{verb} after hours {at}"}
WHEN_VERBS = ("added", "re-added")
WHEN_TITLE = "{verb} {date} {at} ET by 🤖 — {where}"
WHEN_WHERE = {"premarket": "before the open", "intraday": "during the regular session", "after_hours": "after the close"}
WHEN_READD_TITLE = " · removed earlier this session at {rm_at} ET, then added again"
WHEN_HIS_TEXT = "👤 added {at}"                      # today
WHEN_HIS_DAY_TEXT = "👤 added {md}"                  # an earlier day, MM-DD
WHEN_HIS_UNDATED = "👤 yours"
RAN_TEXT = "📅 ran {day} {pct} ({timing} peak)"      # pct f"{x:+.0f}%" — safe: counts ⇒ run_pct ≥ 40 ⇒ prints ≥ +40
RAN_TEXT_NO_TIMING = "📅 ran {day} {pct}"            # a replays fault (no 🎬 bucket) — the chip prints without the parenthesis
RAN_TITLE = ("{date} on Gajjala's scanner: {open}–{end} high {high} = {pct} vs the prior close {pc}, in the 5-minute bar "
             "from {at} ET; premarket high {pm}. 📅 = +{bar:g}% or more printed {open}–{end} ET with the day's peak not "
             "premarket (your 11-21 rule).")                         # {pct} / {pm} via runners.pct_show (floored)
RAN_PM_PEAK_TITLE = ("{date}: the day's peak was premarket ({pm}), above the {open}–{end} high ({pct}) — not counted "
                     "(your 11-21 rule: “pumped pre market and got dumped pre market” is not a winner).")
RAN_UNDER_TITLE = "{date}: {open}–{end} high {pct} vs the prior close — under +{bar:g}%."   # 39.96 prints +39.9%
RAN_NONE = "none premarket"
RUNNERS_TITLE = "📅 Previous day runners — {day} {md}"
RUNNERS_COUNT_ALL = "{n}"
RUNNERS_COUNT_CUT = "{k} running today of {n}"       # k = today_state "running" ONLY [D4]
RUNNERS_COUNT_NOT_READ = " · {u} not read yet"       # appended when u > 0 [D4]
RUNNERS_STALE_TEXT = " · today's read is from {at} ET — nothing removed"     # appended when stale [D6]
RUNNERS_HINT = ("Ran {day}: a {open}–{end} high of +{bar:g}% or more vs the prior close on Gajjala's scanner, the day's "
                "peak not premarket (your 11-21 rule). Biggest gain first; 🚫 names last, never dropped. From {cut} ET a "
                "name leaves while today's high since {open} ET is under +{leave:g}% vs its {day} close (GG's scanner "
                "floor) and comes back when it gets there — never on a read older than {stale_min} minutes. "
                "Descriptive — UNMEASURED.")
RUNNERS_REMOVED_TEXT = "{n} not running today (under +{leave:g}% since {open} ET)"
RUNNERS_TODAY_TEXT = "today {pct} since {open}"     # pct via pct_show (floored) — the chip's title line only, after the cut
RUNNERS_NOT_READ_TEXT = "today not read yet — kept"
RUNNERS_EMPTY_TEXT = "No name on Gajjala's scanner {day} reached +{bar:g}% {open}–{end} with its peak after the open."
RUNNERS_ERROR_TEXT = "Last session's runners could not be read — Gajjala's scanner store did not answer."
RUNNERS_MORE_TEXT = "+{n} more"
RUNNERS_LESS_TEXT = "show less"
RUNNERS_STATES = ("ok", "empty", "error", "off", "owner_only")
TODAY_STATES = ("running", "not_running", "not_read")
