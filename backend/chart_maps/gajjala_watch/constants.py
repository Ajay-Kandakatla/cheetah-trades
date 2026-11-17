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
FRAMES = (("1m", "1min"), ("3m", "3min"), ("5m", "5min"))   # his words "1 min 3 min and 5 min charts" — order = draw order
FRAME_WORDS = {"1m": "1-min", "3m": "3-min", "5m": "5-min"}
AXIS_FRAME = "1m"                                      # the frame whose bars set the tile's axis end (C1.7)
MAX_SYMBOLS = 12                                       # MINE — HIS CALL #1 (= daytrading.signal_lab.MAX_SYMBOLS; ≥ 9 = his 3x3)
PUSH_FRAMES = ("1m",)                                  # his words "I need alerts on these from 1 min" — 3m / 5m = HIS CALL #2
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
ARGV_LOOP = (sys.executable, "-m", "chart_maps.gajjala_watch.loop", "--loop")    # = ops/docker_watchdog CRON_DETACHED_CHILD_ARGS entry
ARGV_BUILD = (sys.executable, "-m", "chart_maps.gajjala_watch.loop", "--build")  # the API's add-time child; builds every pending name
PROC_NAME_LOOP, PROC_NAME_BUILD = "gajjala-watch-loop", "gajjala-watch-build"


def live_audience() -> frozenset:
    """👀 LIVE (2026-11-16, Ajay: "Can you make the watch list charts live please"): the ONE audience of the watch's
    `gajjala.update` batches — the primary owner's lower-cased email, the SAME identity `api._is_owner` gates the board
    with (ollama_chat.api.PRIMARY_ADMIN_EMAIL). Imported LAZILY so this module's top keeps importing only `sys` + `GC`
    (the cron child's import graph is unchanged). Broadcasting to the household instead = HIS CALL #2."""
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    return frozenset({PRIMARY_ADMIN_EMAIL.strip().lower()})
