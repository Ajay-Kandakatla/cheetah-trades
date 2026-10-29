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
RS_FLOAT_SORT = "within_state"           # MINE (DECISIONS13 D3) — state rank first, then float ascending, unknown last; "global" = float above the state rank (HIS CALL Q1)
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
                    "POTENTIAL_DEFER_REFUSED")

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
SUBS = (("bull_flag", "🚩", "Bull Flag"), ("kiss_fly", "💋", "EMA Kiss & Fly"),
        ("horizontal_fade", "➖", "Horizontal Fade"), ("intraday_vcp", "🌀", "Intraday VCP"),
        ("reversal_squeeze", "🎾", "Reversal Squeeze"), ("premarket", "☀️", "Premarket"),
        ("postmarket", "🌙", "Post-market"), ("playbook", "📓", "Playbook"),
        ("potential", "🧠", "Potential"), ("track_record", "🏁", "Track record"))
DEFAULT_SUB = "bull_flag"
TAB_LABEL = "Gajjala's"                  # DECISIONS — emoji/slot HIS CALL 18

# 🚫 broker tag (2026-10-17, DECISIONS12 D1 / D5) — a TAG on his own list, never a filter: nothing here gates a scan or a push
BROKER_NAME = "Fidelity"                 # Ajay 2026-10-17 ("In Fidelity")
BROKER_FLAG_SEED = ()                    # Ajay 2026-10-17 — EMPTY: he withdrew WORX ("sorry I might be wrong about worx"); a name enters only when Fidelity itself refused it (his own add)
BROKER_SYMBOL_MAX_LEN = 10               # TRANSPORT — MINE (DECISIONS12 D5: the ticker shape ^[A-Z][A-Z0-9.\-]{0,9}$ = one letter + up to 9)

# 📌 trader names (2026-10-27, Ajay "Add them to Gajjals, they are pretty good")
TRADER_TAG = "📌"                        # Cheetah default (MINE, not GG — the 📌 traders board's emoji)
TRADER_NAMES_FRESH_SESSIONS = 2          # Cheetah default (MINE, not GG — HIS CALL #5): posted since 00:00 ET of the previous market session
TRADER_NAMES_MAX = 10                    # Cheetah default (MINE, not GG — HIS CALL #5): names added per pass, newest mention first
TRADER_REFRESH_SEC = PASS_CADENCE_SEC * 3   # derived — MINE (HIS CALL #5): the pass re-reads a flagged StockTwits account every 900 s
TRADER_FETCH_PAGES = 1                   # TRANSPORT — MINE: one 30-message page per in-pass read
TRADER_FETCH_TIMEOUT_SEC = 5.0           # TRANSPORT — MINE: worst case 3 profiles x 5 s, out of the pass's own bar budget

# 🚩 Gajjala's 1-minute page (Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of
# Gajjalas but on 1 min candles please." / "do everything and also add the track record for it from today..") —
# BUILD_SPEC27 §3.2. The variant (chart_maps/gajjala/variant.py GG1) runs GG's SAME rules on 1-minute bars; every number
# below is MINE (a Cheetah transport / page default) or derived — NO GG number is copied or changed here, and none of
# his K-numbers moves. UNMEASURED: nothing has measured a 1-minute read.
GAJJALA_1M_ENABLED = True                # MINE — kill switch; env GAJJALA_1M_ENABLED=0 also stops it (read by run.main + run_1m)
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
