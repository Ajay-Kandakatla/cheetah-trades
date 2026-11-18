"""Every number the Gajjala tab uses — other modules IMPORT these, never retype one.

Provenance tag on every line:
  GG <src> <ts>   = his own words (FIRST_HAND_ibd_webinar.md; S8 = IBD webinar CI7mNvEQyms, S9 = TraderLion podcast
                    10pHBNVi4Jc; X = his post on X, by id)
  Ajay K# / H#    = Ajay's answer 2026-10-13 (DECISIONS.md, binding — the ROUND A/B/C answers override the first round)
  Ajay 2026-10-18 = Ajay's answer 2026-10-18 after the K-rules audit (DECISIONS13.md, binding; his words verbatim on the line)
  Cheetah default = Ajay's number, NOT Gajjala's — the ℹ️ panel labels it so (DECISIONS round A)
  TRANSPORT       = pacing only — no list, read or push depends on it
H1–H5 were placeholders (None) until Ajay answered on 2026-10-13; every one is filled. The only None values left are
the OFF switches in OFF_BY_DEFAULT (an unanswered display option whose default is "off", never a missing number).
"""
import datetime as _dt                                    # 🏁 the ledger's fill window (LEDGER_FILL_FROM_ET / _TO_ET)

from orderflow.signals import EMA_FAST, EMA_SLOW          # 9 / 21 — GG S8 25:36, S9 24:42 (one definition)

# scanner — GG S8 19:12–19:51, S9 22:10 (verbatim), Ajay's round-A floor
SCAN_MIN_PRICE = 0.10                    # GG X 1753094531757838340 (2024-02-01) "brought the scanner to show me 0.1$ and above" — his latest; 0.50 in S8 19:12 (Ajay round A)
SCAN_MAX_PRICE = 100.0                   # GG S8 19:12 "anything from 50 cents to $100"
SCAN_MIN_VOLUME = 1_000_000              # GG S8 19:12 + S8 1:32:02 "minimum 1 million"
SCAN_MIN_CHANGE_PCT = 25.0               # GG S8 19:51 "at least minimum 25% change" vs the previous day
SCAN_INCLUDE_OTC = False                 # Ajay round A "OTC off" (also the Massive default)
SCAN_INSTRUMENT_TYPES = frozenset({"CS", "ADRC"})   # Ajay round A: common stock + ADRs; ETFs, warrants, units, rights OUT
SCAN_UNKNOWN_TYPE_POLICY = "list"        # Ajay round A: a symbol with no reference type yet (new listing) is listed
SCAN_UNKNOWN_TYPE_POLICIES = ("list", "drop")
SCAN_UNKNOWN_TYPE = "unknown"            # the `type` a row carries when the reference map has no entry
SCAN_UNKNOWN_TYPE_LABEL = "type unknown"  # Ajay round A wording
STAY_LISTED_SESSIONS = 2                 # Cheetah default (Ajay, not GG — he says "a couple of days", S9 1:17:32)
NO_TRADE_AFTER_OPEN_MIN = 15             # GG S8 14:41 "I don't take trades for the first 15 minutes" · Ajay 2026-10-18 "also 15 mins filter" — confirmed

# instrument-type reference map (Massive /v3/reference/tickers, all types, paginated, once per trading day)
TYPES_PAGE_LIMIT = 1000                  # TRANSPORT — Massive's largest page
TYPES_MAX_PAGES = 15                     # TRANSPORT — "≤ 15 calls/day" (STRATEGY_SPEC D-TYPES); a cut map is flagged incomplete

# K1 demand bar
K1_BODY_GAIN_PCT = 3.0                   # Ajay K1: close >= open * 1.03
K1_RANGE_MULT = 1.5                      # Ajay K1: range >= 1.5x the prior bars' average range
K1_RANGE_LOOKBACK = 20                   # Ajay K1: prior 20 bars
# K2 volume shape on the leg
K2_MAX_VOL_STEP = 5.0                    # Ajay K2: no bar > 5x the previous demand bar
K2_CHECK_FIRST_BAR = False               # Ajay round C (R1-5): the step check stays WITHIN the leg
# K3 pullback
K3_DEPTH_FRAC = 0.50                     # Ajay K3: lows >= last demand high - 0.50 x its range
K3_VOL_FRAC = 0.50                       # Ajay K3: pullback volume <= 0.50 x the demand bars' mean
K3_DEPTH_SETUPS = ("bull_flag", "kiss_fly")   # Ajay round C: the depth floor binds the Bull Flag and Kiss & Fly ONLY
# K4 pullback / base lengths
K4_BF_PULL_MIN = 1                       # Ajay K4: Bull Flag min 1 bar
K4_BF_PULL_MAX = 5                       # Ajay 2026-10-18 "make the change for Long flags" — Substack NXTP 4 / ZYNE 5 pullback bars shown as valid trades; was 3 (Ajay K4 2026-10-13)
K4_BF_LONG_FLAG_MAX = None               # Ajay 2026-10-18: the "long flag" band is EMPTY (1–5 = A+, > 5 invalid); was 5 (Ajay K4a). The detector keeps the None path.
K4_KF_PULL_MAX = 9                       # Ajay K5a: Kiss & Fly pullback <= 9 bars (round A raised K4's 8)
K4_HF_BASE_MIN = 6                       # Ajay K4: Horizontal Fade base 6-24 bars
K4_HF_BASE_MAX = 24                      # Ajay K4
K4_VCP_MIN_CYCLES = 2                    # Ajay K4 / K7: >= 2 contractions
# K5 kiss & fly
K5_KISS_TOL_PCT = 0.5                    # Ajay K5: kiss = low <= EMA9 x 1.005 (or crosses it) and close > EMA9
K5_SLOPE_BARS = 3                        # Ajay K5: both EMAs above their value 3 bars earlier
KF_HONOR_ALL_PULLBACK_CLOSES = True      # Ajay K5a: EVERY pullback bar must CLOSE >= EMA9 ("honors the 9 EMA")
KF_ALLOW_NO_TOUCH = True                 # Ajay K5a: no kiss but K3 + uptrend pass -> LISTED "near-kiss", never A+, never pushed
KF_NO_TOUCH_VARIANT = "near_kiss"        # Ajay K5a wording ("near-kiss") — the Read `variant`
# K6 horizontal fade
K6_MERGE_PCT = 0.5                       # Ajay K6: |EMA9 - EMA21| <= 0.5% of close
K6_TIGHT_PCT = 8.0                       # Ajay K6: base high - base low <= 8% of close
K6_SELL_DECAY = 0.70                     # Ajay K6: second-half volume < 0.70 x first-half
HF_TRIGGER = "base_high"                 # Ajay round C: trigger = the BASE's high (GG "takes the new highs"); stop = prior bar's low
HF_TRIGGERS = ("prior_bar", "base_high")
# K7 intraday VCP
K7_CONTRACTION = 0.75                    # Ajay K7: each cycle's range <= 0.75 x the previous
K7_EMA21_TOL_PCT = 0.5                   # Ajay K7: each cycle low >= EMA21 x 0.995
VCP_B_READS = True                       # Ajay round C: exactly one of {K7 contraction, K7 21-EMA hold} false -> "B — imperfect", listed, never pushed
VCP_B_GRADE = "B"                        # Ajay round C wording ("B — imperfect")
VCP_LIST_FROM_K4 = True                    # Ajay 2026-10-20 "show me stocks only that have 2 contractions … I don't see a point of seeing the ones with one contraction": the 🌀 sub cards only reads with ≥ K4_VCP_MIN_CYCLES contractions — fewer are COUNTED, never carded, never a 🧠 potential; False = card every read (the pre-2026-10-20 board)


def vcp_list_min_cycles() -> "int | None":
    """The fewest contractions a 🌀 read needs to be carded (and to be a 🧠 potential): K4_VCP_MIN_CYCLES while
    VCP_LIST_FROM_K4 is on, else None (no listing rule). Reads both at call time — a patched K4 is followed; no
    second number (BUILD_SPEC18 D1)."""
    return K4_VCP_MIN_CYCLES if VCP_LIST_FROM_K4 else None


# K8 reversal squeeze
K8_MAX_FLOAT = 10_000_000                # Ajay K8: float <= 10,000,000 · Ajay 2026-10-18 "Keep the float reduce" — confirmed after the audit
K8_DROP_PCT = 8.0                        # Ajay K8: tennis ball = a drop >= 8% from a bar's high
K8_RECOVER_PCT = 2.0                     # Ajay K8: recovered to within 2% of the pre-drop level
K8_RECOVER_BARS = 3                      # Ajay K8: within 3 bars
K8_HISTORY_SESSIONS = 30                 # Ajay K8: squeeze-history chip over the last 30 sessions
K8_HISTORY_RANGE_PCT = 50.0              # Ajay K8: (high - low)/low >= 50% OR a halt that day
FLOAT_SUSPECT_POLICY = "ineligible"      # spec default (R1-9b not answered): a float on file > shares out -> unknown -> ineligible
FLOAT_SUSPECT_POLICIES = ("ineligible", "shares_out")
RS_FLOAT_SORT = "within_state"           # MINE (DECISIONS13 D3) — state rank first, then float ascending, unknown last; "global" = float above the state rank (HIS CALL Q1). 2026-11-09: the ONE float-sort mode knob for EVERY setup in FLOAT_SORT_SETUPS (name kept — tests and contracts pin it); ➖ keeps its EMA gap first, float right after the gap
HF_EMA_SORT = "pre_break"               # MINE (Ajay 2026-11-07 "I need a ranking in horizontal fade when the stock 9 EMA and 21 EMA are converging or close to converge on all tabs") — ➖ reads that have NOT broken out (forming AND partial) rank together by |9 − 21 EMA| as % of close (the k6_merge number, a snapshot) ascending, unknown last; A+/held/triggered/stopped keep today's key on top. "within_state" = the 🎾 twin (gap after each state rank; partial always below forming); "global" = the gap above every state (HIS CALL #6 of docs/gajjala/fade_ema_rank_2026_11_08.md)
HF_EMA_SORTS = ("pre_break", "within_state", "global")   # MINE — the three ➖ orders HF_EMA_SORT may name (HIS CALL #6)
# K9 premarket / K10 post-market
K9_PM_MIN_VOLUME = 1_000_000             # Ajay K9: accumulated premarket volume >= 1,000,000
K9_AH_CARRY_PCT = 10.0                   # Ajay K9: prior-day after-hours move >= 10% vs the regular close
K10_CLOSE_TOP_FRAC = 0.30                # Ajay K10: regular close in the top 30% of the day's range
K10_AH_MIN_VOLUME = 250_000              # Ajay K10: after-hours volume >= 250,000
K10_AH_MIN_GAIN_PCT = 5.0                # Ajay K10: after-hours gain >= 5% vs the regular close
# K11 today's volume on the A+ claim (2026-10-21, BUILD_SPEC22 B1) — judged at the ring by detectors.k11_gate on the
# scanner's session volume of the pass that reads the entry bar; ONE number (his scanner floor), never a second
K11_MIN_SESSION_VOLUME = SCAN_MIN_VOLUME  # GG VR 0.4 "1M is a floor … it must SUSTAIN (one 1M bar then a fade = not interested)" — Ajay 2026-10-21 "keep what ever Gajjala says" on "Whether an A+ should also require today's volume to clear GG's 1M floor (NIXX rang on 288K shares)"

# leg minimums he stated
BF_LEG_MIN_BARS = 2                      # GG S9 1:59:24 "at least two big green bars"
KF_LEG_MIN_BARS = 1                      # GG S8 31:33 "only two green bars or one green bar"

# ── formerly NEW HIS-CALL placeholders H1–H5 — answered by Ajay 2026-10-13 (DECISIONS round C) ─────────────────────
HF_LEG_MIN_BARS = 2                      # Ajay H3 — Fade "left side strong" (GG S8 32:49)
VCP_LEG_MIN_BARS = 1                     # Ajay H3 — VCP "left side good demand" (GG S8 33:50)
VCP_PIVOT_WINDOW = 2                     # Ajay H5 — closed bars each side confirming a cycle pivot
K8_FAIL_NEAR_PCT = 2.0                   # Ajay H1 — attempt high within 2% of today's high so far (premarket included)
K8_FAIL_DROP_PCT = 8.0                   # Ajay H1 — a later low 8% under the attempt bar's high = failed
K8_FAIL_EVENT_RULE = "distinct"          # Ajay H2 — the failed attempt's sell-off ends before the tennis ball's reference bar
RS_BASE_MIN_BARS = 1                     # Ajay H4 — squeeze quiet-base minimum bars (no maximum)
PLACEHOLDERS = {"H1": ("K8_FAIL_NEAR_PCT", "K8_FAIL_DROP_PCT"), "H2": ("K8_FAIL_EVENT_RULE",),
                "H3": ("HF_LEG_MIN_BARS", "VCP_LEG_MIN_BARS"), "H4": ("RS_BASE_MIN_BARS",),
                "H5": ("VCP_PIVOT_WINDOW",)}
PLACEHOLDER_BY_SETUP = {"horizontal_fade": ("H3",), "intraday_vcp": ("H3", "H5"),
                        "reversal_squeeze": ("H1", "H2", "H4")}
K8_FAIL_EVENT_RULES = ("distinct", "same_ok")

# situational awareness — GG S8 43:39–44:37 (DECISIONS hard-coded)
SA_BIG_RUNNER_PCT = 100.0                # GG S8 43:39 "a couple of 100%+ runners" on a good day
SA_RUNNER_PCT = 80.0                     # GG S8 43:39 "a bunch of 90+ / 80+ runners"
SA_QUIET_BEST_PCT = 40.0                 # GG S8 44:37 bad day: "maximum runners would be 30%–40%" -> quiet below 40
# psychological levels — GG S9 1:09:11, 1:21:19, 1:39:13 (his sell / climax levels)
PSY_LEVELS = (1.0, 5.0, 10.0)            # GG S9 1:09:11, 1:21:19, 1:39:13
PSY_NEAR_PCT = 5.0                       # Cheetah default (Ajay, not GG): chip when a level is within 5% above price

# red closes — display chip only (Ajay round C, R2-5)
RED_CLOSES_WAIT = 3                      # GG X 1733882105204011109 "more than 3 red closes is red flag to me"
RED_CLOSES_MODE = "chip"                 # Ajay round C: chip only — never a criterion
RED_CLOSES_MODES = ("chip", "criterion", "off")
RED_CLOSE_DEF = "close_below_open"       # Ajay round C: red = close < open

# OFF switches — an unanswered display option whose default is OFF (spec R2-3 / R2-4). None = off; NOT placeholders.
HALT_CALM_BARS = None                    # spec default (R2-3 not answered): halts are a chip only, no push suppression
AH_EXHAUSTION_MAX_PCT = None             # spec default (R2-4 not answered): show the regular-session gain only
OFF_BY_DEFAULT = ("HALT_CALM_BARS", "AH_EXHAUSTION_MAX_PCT")

# labels the ℹ️ panel must say are Ajay's, not Gajjala's (DECISIONS round A)
CHEETAH_DEFAULTS = ("STAY_LISTED_SESSIONS", "PSY_NEAR_PCT", "POTENTIAL_NEEDS_BASE", "POTENTIAL_FRESH_TAPE",
                    "POTENTIAL_DEFER_REFUSED", "PROMO_NAMES_MAX")

# push — DECISIONS round A shipped SHADOW (2026-10-13 … 16); Ajay flipped it LIVE 2026-10-16 — his call, not a measurement
# (the 2026-10-14 study read NULL, docs/gajjala/study_2026_10_13.md). Every A+ entry is its own push, once per (symbol, setup, ET day)
PUSH_KIND = "gajjala_setup"
GAJJALA_PUSH_MODE = "live"               # Ajay 2026-10-16 ("you alert me when that happens" — the entry of his stocks from all 5 tabs when they satisfy all his criteria; DECISIONS10 D1); "shadow" 2026-10-13…16 (round A)
PUSH_MODES = ("shadow", "live")

# 🧠 potential · 📈 track · 🔔 gajjala_potential (Ajay 2026-10-15, DECISIONS4 K1–K3) — NO new number. A potential is the
# detectors' own forming read (the setup's K-criteria above decide forming vs partial); THREE conditions sit on top and
# are MINE — Cheetah defaults, not GG: in CHEETAH_DEFAULTS and served so on the ℹ️ panel, the strip and Notifications.
POTENTIAL_SUB = "potential"                  # Ajay 2026-10-15 msg 1 "create a potential category" (DECISIONS4: one new sub)
POTENTIAL_STATE = "forming"                  # Ajay K1 2026-10-15 "Structure forming, any gate still open"
POTENTIAL_KINDS = ("armed", "building")      # Ajay K1: ready True = "trigger armed"; not ready = "building"
POTENTIAL_PUSH_KIND = "gajjala_potential"    # Ajay 2026-10-15 msg 3 — NEW kind, LIVE, owner-only (DECISIONS4)
POTENTIAL_NEEDS_BASE = True                  # Cheetah default (MINE, not GG — HIS CALL P0): ≥1 sideways bar; DECISIONS4 "first two clauses present"
POTENTIAL_DEFER_REFUSED = True               # Cheetah default (MINE, not GG — HIS CALL P1): a first sighting held by the mute / no fresh print rings at the next eligible pass while still a potential
POTENTIAL_FRESH_TAPE = True                  # Cheetah default (MINE, not GG — HIS CALL P2): ring only when the 5-minute bar that just closed printed (alerts.MAX_ENTRY_AGE_SEC)
POTENTIAL_PUSH_ARMED_ONLY = True             # Ajay 2026-11-11 "Also apply your proposal too." — proposal #1 (entries_followthrough.md:236): a 🧠 rings only when armed; a doc first seen building rings once when it arms
POTENTIAL_ONE_RING_PER_NAME = True           # Ajay 2026-11-11 "Also apply your proposal too." — proposal #2 (entries_followthrough.md:237)
GAJJALA_BREAK_PUSH_MODES = ("off", "shadow", "live")   # Ajay 2026-11-11 "please tell me to enter based on this" — the three states of the ⚡ break push
GAJJALA_BREAK_PUSH_MODE = "shadow"           # HIS CALL #1 — Ajay 2026-11-11 "please tell me to enter based on this"; SHADOW until his word ("live" = rings his phone)
GAJJALA_BREAK_PUSH_KIND = POTENTIAL_PUSH_KIND   # HIS CALL #2 — rides the 🧠 kind (no 8th OWNER_KEEP_SET kind); "gajjala_break" only on his word
# 🔀 2026-11-15 — Ajay, verbatim: "I like how you put the 9 EMA and 21 ema cross over for OMH can you add an alert in
# horizonal fade when that happens?" · "For any stocks that crossing over and add the same feedback in to that horizontal
# fade charts". The cross is the ONE engine chart_maps.gajjala.ema_cross over the frame's own EMA_FAST / EMA_SLOW (no new number);
# the card marks every cross of the session (tab.ema_cross_block), the push rings the first 9-over-21 cross on a closed bar
# once per name per session (alerts.run_fade_cross). Information only — no gate, threshold, detector rule or A+ moves.
FADE_CROSS_SETUPS = ("horizontal_fade",)     # Ajay 2026-11-15 "can you add an alert in horizonal fade" — the ➖ sub only; other subs = HIS CALL
FADE_CROSS_PUSH_MODES = ("off", "live")      # Ajay 2026-11-15 — the two states of the 🔀 cross push ("off" = one word, nothing rings)
FADE_CROSS_PUSH_MODE = "live"                # Ajay 2026-11-15 "can you add an alert in horizonal fade when that happens?" — rings his phone
FADE_CROSS_PUSH_KIND = POTENTIAL_PUSH_KIND   # Ajay 2026-11-15 — rides the 🧠 kind (the GAJJALA_BREAK_PUSH_KIND precedent: no new OWNER_KEEP_SET kind)
FOCUS_N = 5                                  # Ajay 2026-11-11 "Also apply your proposal too." — proposal #9 "Focus 5"; GG U14 "4–5 active (1–2 in poor markets)"
ENTRY_MARK_NEW_MIN = 30                      # Ajay 2026-11-12 "an Indicator or new tickers with in last 30 mins like blinkers or something would be nice" — how long a ✨ blinker stays on a Gajjala card / sub chip (display only)
PASS_MINUTE_OFFSET = 1                       # TRANSPORT — = the crontab minute field "1-56/5" of chart_maps.gajjala.run (test pins it)

# WP6 study — Ajay round C (exits reported side by side; placebo = same-session scanner names with no setup)
STUDY_SESSIONS = 250                     # Ajay round C: the last 250 sessions
STUDY_TIME_EXIT_MIN = 60                 # Ajay round C: stop-or-60-min exit
STUDY_BE_AFTER_R = 1.0                   # Ajay round C: breakeven after +1R, then the first 5-min close under the 9 EMA
STUDY_EXIT_RULES = ("session", "time60", "trail9")   # stop-or-16:00 · stop-or-60-min · breakeven-then-9-EMA

# TRANSPORT (spec H6 — veto only)
PASS_CADENCE_SEC = 300                   # TRANSPORT — DECISIONS "every 5 min"
PASS_OPEN_ET = "04:00"                   # TRANSPORT — DECISIONS 04:00–20:00 ET
PASS_CLOSE_ET = "20:05"                  # TRANSPORT — admits the 20:01 pass that closes the 19:55-20:00 bar
PASS_BUDGET_SEC = 240                    # TRANSPORT
LEASE_SEC = 280                          # TRANSPORT
LEASE_MIN_GAP_SEC = PASS_BUDGET_SEC      # derived: no second pass inside the first one's budget
BAR_SETTLE_SEC = 30                      # TRANSPORT — a bucket counts as closed 30 s after its right label
STALE_AFTER_SEC = max(300, 3 * PASS_CADENCE_SEC)   # TRANSPORT — = frontend pages/Alerts.tsx staleAfterSec (FE test pins equality)
FLOAT_MAX_NEW_PER_PASS = 8               # TRANSPORT — Yahoo fetches per pass; Massive shares-out fills the gap at once
DAILY_MAX_NEW_PER_PASS = 8               # TRANSPORT — 🎾 history chip in-pass; the rest at nightly
AH_CONFIRM_MAX_PER_PASS = 150            # TRANSPORT — rotation queue; the unchecked count is served
TILE_LIMIT_DEFAULT = 24                  # TRANSPORT — = chart_maps.board.LIMIT_DEFAULT (test pins equality)
TILE_LIMIT_MAX = 80                      # TRANSPORT — = chart_maps.board.LIMIT_MAX (test pins equality)
# 🔄 scan on open (Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.") — DECISIONS5 K4, C1, C2.
# Pacing only: nothing lists, reads or pushes on these numbers. Measured 2026-10-15 (the live pass docs, read-only):
# pass wall time p50 5.6 s, p90 11.7 s, p99 18.2 s, max 34.7 s (16:06 ET, 66 names); cron start offset after the tick
# minute (424 pass docs) p50 0.8 s, 7 starts >= 10 s, max 58.5 s. The cron's gap clock is its TICK clock (AMENDMENTS5
# A6), so a wait never eats the next tick's gap: a tick 58.5 s late leaves the on-time next tick 241.5 s >= 240 s.
ON_DEMAND_REUSE_SEC = 60                 # Ajay 2026-10-15 K4 — an open reuses a pass that finished under 60 s ago
ON_DEMAND_BUDGET_SEC = 45                # TRANSPORT — MINE (HIS CALL Q4): the on-open pass's bar budget (from its start, like PASS_BUDGET_SEC); above the measured max wall 34.7 s (p99 18.2 s), well under the cron's 240 s
CRON_WAIT_ON_DEMAND_SEC = ON_DEMAND_BUDGET_SEC   # derived — MINE (DECISIONS5 C1): a cron tick waits at most the on-open budget for an on-open pass, then takes the lease over
ON_DEMAND_POLL_SEC = 5                   # TRANSPORT — MINE (HIS CALL Q4): a waiter (the cron on the lease, the board on the GET) re-checks every 5 s
ON_DEMAND_WAIT_MAX_SEC = 2 * ON_DEMAND_BUDGET_SEC   # derived — MINE (HIS CALL Q4): the board stops waiting after 90 s (an on-open pass plus its tail, or a typical cron pass); the 5-minute re-read takes over
# ⏱ bar close + settle (Ajay 2026-11-09: "make it more live with websockets or something else where there is a low latency
# monitoring on the prices action changes"; GG LIVE spec §3.4, WP-C). Pacing only: nothing lists, reads, gates or pushes on
# these numbers, and the pass stays on the crontab's `:x1` minute. `probe` = a detached child per cron tick reads the bar that
# just closed TWICE (close + BAR_SETTLE_SEC and close + PASS_MINUTE_OFFSET minutes — the cron pass's own read moment) for
# ≤ GG1M_MAX_NAMES names and writes gajjala_bar_final; `on` = the pass itself at close + BAR_SETTLE_SEC. An env value can
# only LOWER the mode (chart_maps/gajjala/bar_close.mode), never raise it.
GAJJALA_BAR_CLOSE_MODE = "probe"         # TRANSPORT — HIS CALL #5 of docs/gajjala/bar_close_pass_2026_11_09.md: "off" | "probe" | "on" (on = the pass at close + 30 s, only on his word after the "Bar finality" line)
GAJJALA_BAR_FINAL_PROBE_SESSIONS = 5     # TRANSPORT — MINE (GG LIVE spec C5): the probe stops itself ("probe complete") once gajjala_bar_final holds 5 session dates
GAJJALA_BAR_FINAL_PROBE_WORKERS = 2      # TRANSPORT — MINE (GG LIVE critic review 2026-11-09): the probe's fetch concurrency; its second read lands beside the cron pass's own ~150-frame fetch (separate process, own 429 breaker) — 2 never crowds the REAL pass
BAR_CLOSE_LATE_MAX_SEC = PASS_MINUTE_OFFSET * 60 - BAR_SETTLE_SEC   # derived — MINE: a child that wakes later than this after its target reads no earlier than the `:x1` cron pass would → refuses (late) → 30
# Mongo retention (spec §3.1.6)
LEDGER_TTL_DAYS = 30                     # TRANSPORT — gajjala_scan / _ah_carry / _post / _passes / _daily
READS_TTL_DAYS = 14                      # TRANSPORT — gajjala_reads (tile bars are the bulk)

# 🏁 Track record (Ajay 2026-10-16: "also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To
# see a percentage and the ticker." / "We are not looking for winners just in time but when they got in to our alerts if
# they made it or not. Like XLAB today was a winner I made good money on it") — DECISIONS9 D1–D10 + AMENDMENTS9. Operational
# accounting of the alerts as sent, graded by GG's trade math (his knob answer) — never a study, never a measured edge.
# Not LEDGER_TTL_DAYS above (that is the 30-day TTL of gajjala_scan & co.): gajjala_ledger is KEPT, no TTL.
LEDGER_SUB = "track_record"              # Ajay 2026-10-16 "keep a new tab" — DECISIONS9 D7 (appended LAST to SUBS)
LEDGER_R_MULT = 1.0                      # Ajay 2026-10-16 ("GG's trade math": +1R before the stop)
LEDGER_HORIZONS = ("same", "next")       # Ajay 2026-10-16 ("Both columns")
LEDGER_FILL_FROM_ET = (_dt.datetime(2000, 1, 3, 9, 30) + _dt.timedelta(minutes=NO_TRADE_AFTER_OPEN_MIN)).time()   # Ajay 2026-10-16 ("From 09:45 ET only") = 09:30 (daytrading.data.ET_RTH_OPEN, test pins equality) + NO_TRADE_AFTER_OPEN_MIN — AMENDMENTS9 E1
LEDGER_FILL_TO_ET = _dt.time(16, 0)      # Cheetah default (regular session) — = daytrading.data.ET_RTH_CLOSE (test pins equality); AMENDMENTS9 E1
LEDGER_MIN_R_PCT = 0.5                   # Cheetah default (MINE, not GG — AMENDMENTS9 E4; HIS CALL Q16): R < 0.5% of the trigger = "thin R", graded, out of the %
LEDGER_SPANS = ("today", "yesterday", "5d", "10d", "all")   # Cheetah default (MINE, not GG — DECISIONS9 D7 day picker; HIS CALL Q9; "10d" DECISIONS11 D3, HIS CALL Q3 of docs/gajjala/entry_timeline_2026_10_16.md)
LEDGER_SPAN_DEFAULT = "5d"               # Cheetah default (MINE, not GG — AMENDMENTS9 E2 "5 sessions"; HIS CALL Q9)
LEDGER_SPAN_SESSIONS = 5                 # Cheetah default (MINE, not GG — DECISIONS9 D7 "last 5 sessions"; HIS CALL Q9)
LEDGER_SPAN_SESSIONS_LONG = 10           # Cheetah default (MINE, not GG — DECISIONS11 D3 "the whole past week + fits": the "10d" span; HIS CALL Q3)
LEDGER_TAPE_TF_MIN = 5                   # TRANSPORT — MINE (DECISIONS11 D2): the Promo Circuit tape's 5-minute closes (catalysts/promo_tape.bars_for "5min", test pins equality)
LEDGER_TAPE_SESSIONS = 3                 # TRANSPORT — MINE (DECISIONS11 D2, BUILD_SPEC11 C3): the alert's day + its same session + the next (an after-close alert's same session is the next market day)
LEDGER_TAPE_BARS_MAX = LEDGER_TAPE_SESSIONS * (16 * 60 // LEDGER_TAPE_TF_MIN)   # derived — MINE: 16 h = daytrading.data ET_PREMARKET_OPEN → ET_AFTERHOURS_CLOSE (test pins equality) → 576
LEDGER_TAPE_MEMO_SEC = PASS_CADENCE_SEC  # derived — MINE (DECISIONS11 D2 "memo 5 min per id")
LEDGER_LOSS_FAST_MIN = 5                 # TRANSPORT — MINE (DECISIONS11 D12/D13 class C4): "stopped ≤ 5 min after the fill"
LEDGER_LOSS_LATE_RTH_MIN = 30            # TRANSPORT — MINE (DECISIONS11 D12, class C2): "the last 30 min of RTH"
LEDGER_LOSS_STALE_FILL_MIN = 60          # TRANSPORT — MINE (DECISIONS11 D12, class C3): "filled ≥ 60 min after the ring"
LEDGER_LOSS_NO_PROGRESS_R = 0.3          # TRANSPORT — MINE (DECISIONS11 D12, class C5): best < +0.3R before the stop
LEDGER_LOSS_GAVE_BACK_R = 0.8            # TRANSPORT — MINE (DECISIONS11 D12, class C6): best ≥ +0.8R, then stopped
LEDGER_LOSS_CLASS_FLAG_N = 3             # Ajay 2026-09-03 (Rule #9: "≥3 of the same class" → propose a rule, never change one) — the losers study's flag count
LEDGER_TODAY_MEMO_SEC = PASS_CADENCE_SEC # derived — MINE (DECISIONS9 D5c "memo 5 min"; HIS CALL Q2)
LEDGER_TODAY_MAX = 60                    # TRANSPORT — MINE (AMENDMENTS9 E8, DECISIONS9 D5c "≤ ~60 names"; HIS CALL Q2): rows read per open
LEDGER_TODAY_MAX_NAMES = LEDGER_TODAY_MAX   # derived — MINE: the BUILD_SPEC9 §3.1 name of the same cap (one number, AMENDMENTS9 E8)
LEDGER_TODAY_BUDGET_SEC = 15             # TRANSPORT — MINE (HIS CALL Q2): the open's 1-minute fetch budget, from its start
LEDGER_GRADE_AT_ET = "20:15"             # TRANSPORT — = the crontab line of chart_maps.gajjala.nightly (contracts pin it)
LEDGER_GRADE_LOOKBACK_SESSIONS = 10      # TRANSPORT — MINE (DECISIONS9 D6; HIS CALL Q6): the nightly re-reads 10 market days
LEDGER_BACKFILL_MAX_SYMBOL_DAYS = 120    # TRANSPORT — MINE (AMENDMENTS9 E9; HIS CALL Q6): symbol-day loads per nightly run; the rest "not graded yet", the next night
LEDGER_GRADE_MAX_LOADS = LEDGER_BACKFILL_MAX_SYMBOL_DAYS   # derived — MINE: the BUILD_SPEC9 §3.1 name of the same cap (one number, AMENDMENTS9 E9)
LEDGER_ROWS_MAX = 400                    # TRANSPORT — MINE (2026-10-16 night, DECISIONS11 D3: the 10d span at ~30 rows a session; the counts still cover every row)
LEDGER_GRADE_VERSION = 1                 # TRANSPORT — bump to re-grade the lookback window (the grader changed)

# sub-tabs (DECISIONS order) — key, emoji, label. 🧠 Potential (Ajay 2026-10-15 msg 1) then 🏁 Track record (Ajay
# 2026-10-16) appended after it (HIS CALL Q7); nothing else moves (HIS CALL P8)
SETUPS = ("bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze")
# 🎾→all (Ajay 2026-11-09 "Are the reversal squeeze tickers sorted by high probability can you update other tabs in the same
# way I like how they are realtime updating the prices of now" · "When I say all tabs with in Gajjalas only"): every
# setup sub takes the 🎾 float key (Ajay 2026-10-18 "for the float lower the better is what I wanna follow so sort it by
# lowest on top") — state rank, then float ascending (unknown last), then today's key; placement = RS_FLOAT_SORT. DISPLAY
# ORDER ONLY: no gate, rule, push or data change; no probability is claimed (there is none).
FLOAT_SORT_SETUPS = tuple(SETUPS)        # derived — MINE: every setup sub the board shows (SETUPS, never retyped); his 2026-11-09 words above
# 2026-11-09 ~10:25 ET — Ajay, verbatim: "Ok sort any stocks by volume on all Gajjala's charts". Today's scanner volume (the
# card's own Volume number — _chips ← scan_row volume; GG S8 1:21:56 "I sort by volume", S8 1:32:02 "the more the better")
# sorts DESCENDING inside every state on every card sub, unknown last, and sits BEFORE the float key (his 2026-10-18 float
# call is the next key); placement = RS_FLOAT_SORT. The 🧠 sub's potential.order_key takes the same swap. DISPLAY ORDER ONLY.
VOLUME_SORT_SETUPS = FLOAT_SORT_SETUPS   # derived — the same subs as the float key (never retyped); his 2026-11-09 ~10:25 ET words above
# 💋 2026-11-11 ~12:50 ET — Ajay, verbatim: "Sort by relative volume, and closer to the EMA." · "This filter is needed for
# EMA Kiss atleast". Inside each state on the 💋 sub: relative volume DESCENDING (this pass's session volume ÷ the
# 50-session average, chart_maps.drop10_tab.rvol_read — the house sort engine), then the low's distance to the 9 EMA
# ASCENDING (the K5 row's own printed number), both unknown last, BEFORE the 📊 volume / float slot. DISPLAY ORDER ONLY: no
# gate, rule, push or count change; UNMEASURED (the 11-11 entries study's loudest-three read was null-to-negative).
RVOL_SORT_SETUPS = ("kiss_fly",)         # MINE (HIS CALL Q8 of docs/gajjala/kiss_rvol_sort_2026_11_11.md) — his "EMA Kiss atleast": the 💋 sub only
KF_EMA_SORT = "rvol_first"               # MINE (HIS CALL Q6) — his word order: relative volume first, then closest to the 9 EMA; "ema_first" swaps the two
KF_EMA_SORTS = ("rvol_first", "ema_first")   # MINE — the two 💋 orders KF_EMA_SORT may name (HIS CALL Q6)
# 📋 2026-11-13 — Ajay, verbatim: "Hey can you build be a table like track record on Gajjals landing page.. Call all
# strategies." The table sub sits FIRST (the phone strip scrolls sideways — an 11th chip at the end is off-screen), GG5
# only (tab.resolve_sub fails open off it on the 1-minute / 🧪 pages); DEFAULT_SUB unchanged (HIS CALL #1 of
# docs/gajjala/all_strategies_table_2026_11_13.md). ONE tuple literal of string-literal triples, no name inside it and no
# comment on its closing line — frontend/scripts/contracts.mjs parses it with a regex (GG_SUBS == SUBS, in order).
# 🧨 2026-11-18: ("divergence", "🧨", "Divergence") right after 🎾 (HIS CALL #4 of docs/gajjala/divergence_sub_2026_11_18.md), GG5 only.
SUBS = (("all_strategies", "📋", "All strategies"), ("bull_flag", "🚩", "Bull Flag"), ("kiss_fly", "💋", "EMA Kiss & Fly"),
        ("horizontal_fade", "➖", "Horizontal Fade"), ("intraday_vcp", "🌀", "Intraday VCP"),
        ("reversal_squeeze", "🎾", "Reversal Squeeze"), ("divergence", "🧨", "Divergence"),
        ("premarket", "☀️", "Premarket"), ("postmarket", "🌙", "Post-market"), ("playbook", "📓", "Playbook"),
        ("potential", "🧠", "Potential"), ("track_record", "🏁", "Track record"))
TABLE_SUB = SUBS[0][0]                   # "all_strategies" — read off the literal, never a second spelling (2026-11-13)
# Ajay 2026-11-13, verbatim: "others close to strategies next liek EMA near kiss first, horizontal fade 9 EM Anad 25 EMA
# merge second and VCP next reversal potental next" — the forming tier's setup order on the 📋 table; bull_flag LAST is
# MINE (he did not name it — HIS CALL #3). A permutation of SETUPS (the test pins it). DISPLAY ORDER ONLY.
TABLE_SETUP_ORDER = ("kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze", "bull_flag")
GG_WATCH_N = 18                          # Ajay 2026-11-13 "He watches 18 stocks simultaneously" — a divider on the 📋 table, never a cap (HIS CALL #8)
DEFAULT_SUB = "bull_flag"
TAB_LABEL = "Gajjala's"                  # DECISIONS — emoji/slot HIS CALL 18

# 🚫 broker tag (2026-10-17, DECISIONS12 D1 / D5) — a TAG on his own list, never a filter: nothing here gates a scan or a push
BROKER_NAME = "Fidelity"                 # Ajay 2026-10-17 ("In Fidelity")
BROKER_FLAG_SEED = ()                    # Ajay 2026-10-17 — EMPTY: he withdrew WORX ("sorry I might be wrong about worx"); a name enters only when Fidelity itself refused it (his own add)
BROKER_SYMBOL_MAX_LEN = 10               # TRANSPORT — MINE (DECISIONS12 D5: the ticker shape ^[A-Z][A-Z0-9.\-]{0,9}$ = one letter + up to 9)

# 🧨 Divergence (Ajay 2026-11-18 "yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish"):
# a DISPLAY + RECORD of the 11-16 study's REGISTERED pick on the 5-min tab. No push, no gate, no rule. UNMEASURED live;
# in-sample the rule did not make money (REPORT.md). Every number below is the study's (OOS_SPEC.md by sha; pins_only.json)
# — study dir eod-audits/research/2026-11-16_explosive_divergence/; the test pins each against
# tests/fixtures/gajjala/divergence_study_2026_11_16.json. The engine is divergence.py (one module, three callers).
DIVERGENCE_SUB = "divergence"
GG5_ONLY_SUBS = (TABLE_SUB, DIVERGENCE_SUB)   # derived — the subs only the 5-min page shows (tab.resolve_sub fails open off them on 🧪 / 1-min)
DIVERGENCE_OOS_SPEC_SHA256 = "9da1ab8e1b79aac2c1a69ab21088c988baf7aade38987b33a1a759a1bbe8ed90"   # S/OOS_SPEC.md
DIVERGENCE_DESIGN_SHA256 = "c5a1f2eb7091bb586febf8767f5e553805f27036d3431aeddc8d3c8495224d3f"     # S/design.md
DIVERGENCE_R1_LEVEL = 0.5552257708108612          # spec default — OOS_SPEC "level q60 … the IS number, never re-estimated"
DIVERGENCE_LEVEL_PCT = 60                         # spec default — OOS_SPEC q60 (pins_only LEVEL_PCTS[0])
DIVERGENCE_ATR_PERIOD = 14                        # spec default — pins_only ATR_PERIOD = supply_demand.patterns.atr's default (test pins equality)
DIVERGENCE_V2_RUN = 3                             # spec default — pins_only V2_RUN
DIVERGENCE_V2_HOUR_BARS = 12                      # spec default — pins_only V2_HOUR_BARS
DIVERGENCE_V2_MIN_HOUR_BARS = 6                   # spec default — pins_only V2_MIN_HOUR_BARS
DIVERGENCE_MIN_BARS = 30                          # spec default — pins_only MINBARS (tx.MINBARS)
DIVERGENCE_WINDOWS = (("rth", "09:35", "15:55"), ("ah", "16:05", "19:55"))   # pins_only WINDOWS — close stamps; pre-market NEVER
DIVERGENCE_COST_BPS = 0.001                       # spec default — pins_only costs.COST_BPS — tx.net_pct per side
DIVERGENCE_SLIP_USD = 0.01                        # spec default — pins_only costs.SLIP_USD — per share per side
DIVERGENCE_OOS_SESSIONS = ("2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-30")   # OOS_SPEC
DIVERGENCE_ASK_DAY = "2026-11-16"                 # OOS_SPEC — its own block, never a criterion
DIVERGENCE_OOS_SEAL_ET = "2026-11-30 20:00"       # OOS_SPEC.md:7 "Not read now … after 2026-11-30 20:00 ET" — totals over OOS rows withheld before it
DIVERGENCE_STATE_ID = "divergence_redetect"       # the ONE gajjala_state doc of the nightly re-detect markers (day_read.STATE_ID pattern)
DIVERGENCE_IS_WINDOW = ("2026-10-13", "2026-11-13", 24)   # REPORT.md in-sample window; pins_only inputs.sessions
DIVERGENCE_GRADE_VERSION = 1                      # TRANSPORT — bump to re-grade
DIVERGENCE_GRADE_MAX_LOADS = LEDGER_BACKFILL_MAX_SYMBOL_DAYS   # derived — the nightly's symbol-day cap, as the 🏁's
DIVERGENCE_ROWS_MAX = LEDGER_ROWS_MAX             # derived — the 🏁 fold's row cap, as the 🏁's
DIVERGENCE_IS = {                                 # results.json cohorts.P5M.cells["R1|60|G+V2|X3"] (+ pick.minus_B) / cohorts.P5M.windows.AH.cells[…]
    "rth": {"trades": 56, "mean_net": -3.0929, "lo": -6.7296, "hi": 1.0578, "win_pct": 26.8, "median_net": -6.4072,
            "exit_downcross": 38, "exit_close": 18, "lt1_trades": 28, "word": "NOT SHOWN",
            "vs_listed_mean": 3.2757, "vs_listed_lo": -1.7965, "vs_listed_hi": 8.8953, "vs_listed_p": 0.2207, "vs_listed_word": "NOT SHOWN"},
    "ah":  {"trades": 32, "mean_net": -8.9283, "lo": -15.6032, "hi": -3.1323, "win_pct": 21.9, "median_net": -8.7334,
            "exit_downcross": 17, "exit_close": 15, "lt1_trades": 16, "word": "LOST MONEY"},
}

# 📌 trader names (2026-10-27, Ajay "Add them to Gajjals, they are pretty good")
TRADER_TAG = "📌"                        # Cheetah default (MINE, not GG — the 📌 traders board's emoji)
TRADER_NAMES_FRESH_SESSIONS = 2          # Cheetah default (MINE, not GG — HIS CALL #5): posted since 00:00 ET of the previous market session
TRADER_NAMES_MAX = 10                    # Cheetah default (MINE, not GG — HIS CALL #5): names added per pass, newest mention first
TRADER_REFRESH_SEC = PASS_CADENCE_SEC * 3   # derived — MINE (HIS CALL #5): the pass re-reads a flagged StockTwits account every 900 s
TRADER_FETCH_PAGES = 1                   # TRANSPORT — MINE: one 30-message page per in-pass read
TRADER_FETCH_TIMEOUT_SEC = 5.0           # TRANSPORT — MINE: worst case 3 profiles x 5 s, out of the pass's own bar budget

# 🎪 Promo-circuit names (2026-10-29, Ajay "should we pull stocks from PROMO circuit by default every day … I do wanna
# run them against Gajjalas strategies") — chart_maps/gajjala/promo_names.py; the add waives GG's change and volume
# floors for the ADD only (the 📌 pattern); every K-rule and the 1M push floor are GG's, unchanged
PROMO_TAG = "🎪"                         # Cheetah default (MINE, not GG — the 🎪 Promo circuit page's emoji)
PROMO_NAMES_MAX = 25                     # Cheetah default (MINE, not GG — HIS CALL #1): 🎪 adds listed per session, today's % change first

# 🚩 Gajjala's 1-minute page (Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of
# Gajjalas but on 1 min candles please." / "do everything and also add the track record for it from today..") —
# BUILD_SPEC27 §3.2. The variant (chart_maps/gajjala/variant.py GG1) runs GG's SAME rules on 1-minute bars; every number
# below is MINE (a Cheetah transport / page default) or derived — NO GG number is copied or changed here, and none of
# his K-numbers moves. UNMEASURED: nothing has measured a 1-minute read.
GAJJALA_1M_ENABLED = False               # Ajay 2026-11-18 ~00:10 ET ("This is good info stop 1 min tab it was a good experiment") — the 1-minute PAGE retired: no spawn, no pass, no fetch, no push, no write; its 🏁 record stays readable; True 2026-10-27 … 2026-11-17. Flip back = this one word (env GAJJALA_1M_ENABLED=0 also stops it; read through variant.enabled). The 👀 Watch keeps its 1-minute charts ("But keep the one min chart in the watch list I still want them") — its bars never ran through this pass; the ⤢ card frame reads the Watch's stored 1m tile.
GAJJALA_1M_RETIRED_ON = "2026-11-18"    # Ajay 2026-11-18 (the words above) — served in the retired sentences only; no gate reads it
GAJJALA_1M_PUSH_MODE = "live"            # Ajay 2026-10-29 ("Only give me Gajjalas chart notifications from both tabs, / I am missing out the ones in noise." — HIS CALL #1 of the 1-minute page answered); "shadow" 2026-10-27…28 (recorded, never sent)
GG1M_TAB_LABEL = "Gajjala's 1-min"       # MINE — HIS CALL #10
GG1M_CADENCE_SEC = 60                    # TRANSPORT — one iteration per closed 1-minute bar
GG1M_MAX_NAMES = 60                      # TRANSPORT — MINE (HIS CALL #3): names per iteration, top change first
GG1M_MINUTE_BUDGET_SEC = 35              # TRANSPORT — MINE: one iteration's bar budget, from its start
GG1M_SLOT_MARGIN_SEC = 20                # TRANSPORT — MINE: start + budget + margin must be ≤ the next cron tick
GG1M_LEASE_SEC = 55                      # TRANSPORT — MINE: a crashed 1-minute holder frees itself
GG1M_LEASE_MIN_GAP_SEC = 0               # TRANSPORT — MINE: the iterations of one loop are ~20–60 s apart; the lease alone serialises
GG1M_STALE_AFTER_SEC = max(300, 3 * GG1M_CADENCE_SEC)   # derived — the STALE_AFTER_SEC formula → 300 (= Alerts.tsx staleAfterSec(60))
GG1M_TAPE_TF_MIN = 1                     # TRANSPORT — MINE (HIS CALL #8): the 🏁 entry tape on 1-minute bars
GG1M_TAPE_BARS_MAX = LEDGER_TAPE_SESSIONS * (16 * 60 // GG1M_TAPE_TF_MIN)   # derived → 2,880
GG1M_TILE_BARS_MAX = LEDGER_TAPE_BARS_MAX // LEDGER_TAPE_SESSIONS          # derived — MINE (HIS CALL #7): last 192 1-minute bars per card
GG1M_RECORD_FROM = "2026-10-27"          # Ajay 2026-10-27 "add the track record for it from today" — no session before it is read

# 🧪 Gajjala · Audited (Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day.. Gajjals-Audited. So we can keep track of improvements on this tab") — chart_maps/gajjala/audited_rules.py holds every rule number with its prereg cite; nothing here is a GG number
GAJJALA_AUDITED_PUSH_MODE = "shadow"     # Ajay 2026-11-01 (the ask above) — SHADOW: recorded, never sent; going live = HIS CALL (and a code change: audited_pass passes mode="shadow" explicitly)
GGA_TAB_LABEL = "🧪 Gajjala · Audited"   # MINE — the main session's label (design #7); his words "Gajjals-Audited"
GGA_RECORD_FROM = "2026-11-01"           # Ajay 2026-11-01 "So we can keep track of improvements on this tab" — the record starts at his ask; no session before it is read

# 📐 Gajjala's chart on the stock page (Ajay 2026-11-06: "If I click on Gajjalas tab stocks show me "Gajjalas chart" in
# supply and demand of his view by default mainly.. Like if he looks at 24 hours or 2 week or anything else that is what I
# would like to see"). The served tile href opens the house ticker page's Supply / Demand tab on the frame the card is
# DRAWN on. Values are supply_demand/timeframes.py NAMES, resolved by chart_maps.gajjala.tab.chart_href with getattr at
# call time (this file imports nothing from supply_demand — test_gajjala_constants pins its imports); a retired key cannot
# ship (the test pins each name is a TIMEFRAMES key whose bar_label matches the frame's minutes). His view = verified_rules
# topics[3].verified[0] T1 "5-minute primary, 15-minute secondary; 1/2/3/10-minute tried and rejected". The chart under
# it draws the HOUSE averages (chart_maps.board.MA_SPECS: 9 EMA / 20 SMA / 200 SMA), not his 21 EMA — HIS CALL, not built.
CHART_FRAME_KEY_CONST = {"1m": "M1_TODAY", "5m": "M5_TODAY", "15m": "M15"}   # Ajay 2026-11-06 — the 5-minute card opens today's 5-minute frame (M5_TODAY), not the 24-hour one he also named = MINE (HIS CALL #1); 15m → the two-week 15-minute frame; 1m → today to the minute (the 1-minute page)
CHART_TF_PARAM = "tf"                    # TRANSPORT — the Support tab's own query name (frontend pages/ChartMaps.tsx + pages/SepaCandidate.tsx read `?tf=`; the FE contract pins equality)

# 🎾 GG's chart on the squeeze card (Ajay 2026-11-08: "I need something like this but that big of circle for reversal squeen mainly on the
# cart itself also increase the width of the reversal sqeeze chart to show more bars" — his own TPST chart runs from the prior day's 15:00).
# Drawing window only — nothing lists, reads, gates or pushes on these; every K number stays above.
RS_TILE_PRIOR_FROM_ET = _dt.time(15, 0)   # Cheetah default (MINE, not GG — HIS CALL #3 of docs/gajjala/squeeze_chart_2026_11_08.md): the first bar of his TPST chart; the GG5 🎾 card's bars start at the prior session's 15:00 bucket
RS_TILE_PRIOR_TO_ET = _dt.time(20, 0)     # Cheetah default (MINE) — = daytrading.data.ET_AFTERHOURS_CLOSE (test pins equality — the LEDGER_FILL_TO_ET pattern; constants.py may import only datetime, test_gajjala_constants)
RS_TILE_PRIOR_BARS_MAX = ((RS_TILE_PRIOR_TO_ET.hour - RS_TILE_PRIOR_FROM_ET.hour) * 60) // LEDGER_TAPE_TF_MIN   # derived — MINE: 15:00 → 20:00 in 5-minute bars → 60 (the only literal is 60 min/h, as on LEDGER_TAPE_BARS_MAX; never retype 15 or 20 here)
RS_TILE_TODAY_BARS_MAX = LEDGER_TAPE_BARS_MAX // LEDGER_TAPE_SESSIONS  # derived — MINE: one 16-hour session in 5-minute bars → 192 (= GG1M_TILE_BARS_MAX's expression, the 5-minute page's cap)
RS_TILE_BARS_MAX = RS_TILE_PRIOR_BARS_MAX + RS_TILE_TODAY_BARS_MAX     # derived — MINE: the most bars a 🎾 card ever serves → 252

# 📶 base count (2026-11-15) — Ajay, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app
# please" · "I need that tracked in to Gajjala's". GG verified rule E6 (single_source, his example(s), his_call): S8 40:54–41:18,
# S8 1:00:37; counter-rule S9 55:18–57:49 (quoted, NOT computed — its trigger "100% in 20 minutes" has no constant). INFORMATION
# ONLY — nothing gates, sorts, filters, pushes or trades on it; UNMEASURED (Ajay 2026-11-15 "Just show it"). Every count
# number is an EXISTING constant by name. Ajay's answers 2026-11-15 set FROM / UNTIL / MIN / RESTART; the other switch
# defaults are MINE, not GG's (HIS CALL #1 / #2, docs/gajjala/run_bases_2026_11_15.md).
RUN_BASE_FRAME = "5m"                      # GG verified T1, S8 1:40:07 "I tried 1 minute 3 minute 5 minute 15 minutes … I concluded on the five minute" — the 1-min page counts on its 5m frame too (HIS CALL #2)
RUN_BASE_HOURS = ("session", "rth")        # MINE — "session" = the detectors' today (premarket on / through 20:00); "rth" = daytrading.data ET_RTH_OPEN / ET_RTH_CLOSE
RUN_BASE_FROM = "rth"                      # Ajay 2026-11-15 "Can you check what he says I think he is identifying 3 times and then 3rd assumes as climax run" — GG gives no start clock; he counts the run he trades and names "entering on bias from the premarket run" a mistake → the count starts at the 09:30 open
RUN_BASE_UNTIL = "rth"                     # Ajay 2026-11-15 (the same answer) — the count runs to the regular 16:00 close
RUN_BASE_LEG_MIN_BARS = BF_LEG_MIN_BARS    # MINE to reuse (HIS CALL #1b) — GG S9 1:59:24 "at least two big green bars"
RUN_BASE_MIN_BARS = K4_HF_BASE_MIN         # Ajay 2026-11-15 "What does he say I think 2nd option" — the shortest base = his horizontal-base minimum (a 1-bar flag no longer counts)
RUN_BASE_MAX_BARS = K4_HF_BASE_MAX         # MINE to reuse (HIS CALL #1d) — the longest base his setups read (Fade, 24 bars)
RUN_BASE_DEPTH_FLOOR = False               # Cheetah default (MINE, not GG — HIS CALL #1g): True = K3_DEPTH_FRAC on every base (K3_DEPTH_SETUPS binds no base setup today)
RUN_BASE_RESTART = True                    # Ajay 2026-11-15 "Yes, restart" — a pause longer than RUN_BASE_MAX_BARS ends the run; the next run counts from 1
RUN_BASE_CLIMAX_N = 3                      # GG S8 40:54–41:18 "third base, this is a climax run … I was peeling off early" (E6)
RUN_BASE_OUT_N = 4                         # GG S8 1:00:37 "fourth base, I came out of everything" (E6)

# 🔀 blinker (2026-11-15) — Ajay, verbatim: "On All of the charts and also the tabs I need a new blinker to show me EMA
# uptrends 9 crossing over 21 EMA please.." · WHERE "All Gajjala tabs" · FRAME "Each chart's own frame" · DURATION "Yes
# and I need some sort of urgency or fast blink for the one are closer together than approaching with sort also aligned
# with it" · "Or atleast closing in on other tabs for me". INFORMATION ONLY — no gate, push, alert, A+ rule, lane, sort
# default or track record reads it; the opt-in sort is BLINK_SORT_KEY. The read is ema_cross.blink_read over the frame's
# own EMA_FAST / EMA_SLOW curves (no new EMA). Every number is MINE (HIS CALL #n, docs/chart_maps/ema_blink_2026_11_15.md)
# or an existing constant reused by name. A crossed-up Gajjala card blinks for as long as the 9 stays over the 21 on its
# drawn frame — Ajay 2026-11-15 "Yes" to "until 9 drops under 21" (no age cap: blink_read's up_max_bars default, no
# constant). The tab-dot feed re-reads only while THE pass window is open on a market day (run.in_window: PASS_OPEN_ET /
# PASS_CLOSE_ET + market_hours.gate.closed_reason — no second window typed here). UNMEASURED
# (eod-audits/research/2026-11-15_video_9x21_upcross: a cross times a runner, never picks one; 1-minute ≈ 12 crosses a chart).
BLINK_NARROW_BARS = K5_SLOPE_BARS            # MINE to reuse (HIS CALL #1) — "closing in" = the 9/21 gap is smaller than it was this many closed bars ago (his K5 EMA-slope lookback)
BLINK_MAX_BARS = K4_HF_BASE_MAX              # MINE to reuse (HIS CALL #2) — a cross projected further out than this many bars is not "closing in" (the longest base his setups read)
BLINK_NEAR_BARS = BLINK_NARROW_BARS          # derived — MINE (HIS CALL #3): "near" = the cross is projected within this many bars
BLINK_IMMINENT_BARS = 1                      # Cheetah default (MINE, not GG — HIS CALL #3): "imminent" = projected on the next closed bar — the frame's own unit, no other number; a gap of exactly 0 counts as imminent
BLINK_DAILY_UP_MAX_BARS = 0                  # Cheetah default (MINE, not GG — HIS CALL #4): the daily Chart Maps boards blink crossed-up only when the cross bar IS the latest CLOSED bar ("crossed this session"); None = the Gajjala rule above
BLINK_SORT_KEY = "ema_blink"                 # TRANSPORT — the opt-in `sort` value (GG setup subs + 🧠; board.SORTS / POST_CUT_SORTS on the other boards); the FE contract pins the spelling
BLINK_TAB_REFRESH_SEC = GG1M_CADENCE_SEC     # derived — MINE (HIS CALL #6): the tab-dot count (GET /chart-maps/ema-blink) re-reads once per closed 1-minute bar while run.in_window(now) holds; 0 otherwise
