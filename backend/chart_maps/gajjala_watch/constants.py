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
                "suppressed_window", "under_floor", "not_uptrend", "no_store", "no_target", "failed")
ENABLED = True
ENV_ENABLED = "GAJJALA_WATCH_ENABLED"                  # "0" lowers it (tests/conftest assigns "0")
CLAIM_PREFIX = "GGW"                                   # never "GG:" — the 🏁 reads GG: claims
COLL_LIST, COLL_TILES, COLL_ALERTS, COLL_STATE = ("gajjala_watch_list", "gajjala_watch_tiles",
                                                  "gajjala_watch_alerts", "gajjala_watch_state")
LIST_DOC_ID, STATE_LATEST_ID, LOOP_STATE_ID = "owner", "latest", "loop"   # the lease doc id is store.LEASE_ID
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
