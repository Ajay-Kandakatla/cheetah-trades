"""📅 Long Term tab — the ONLY number source (2026-11-12).

Every threshold the tab reads lives here, tagged by whose number it is:
  HIS  = Ajay's own number, quoted somewhere in the app already;
  APP  = an existing app constant, IMPORTED (never retyped);
  MINE = proposed by the main session on 2026-11-12 (or this spec) = HIS CALL.

His words (2026-11-12 ~21:00 ET): "Save this entire list for me. In a New tab -
Long Term - Remember this analays criteria I am asking you to for this tab and
keep updating it from all the other tabs info.. Weekly and if something gets
dropped let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4
changes."

Spec: scratchpad longterm/spec.md revision 2, §3.2. Nothing here rings a phone:
DIGEST_PUSH_MODE is "off" (critique C9) and the tab is PRIMARY OWNER ONLY
(critique C10) until his word.
"""
from __future__ import annotations

from pathlib import Path

from sepa import sales as S, stage_transitions as STX, scanner as SC, longterm as LT, pankaj_picks as PK
from chart_maps import fallen_tab as FAL, undervalue_peers as UVP, board as B
from rotation import hottest as H, backtest as RB

MARK = "\U0001F4C5"                                   # 📅
TAB_KEY = "long_term"
TITLE = MARK + " Long Term"
API_PATH = "/chart-maps/long-term"
SAVED_ON = "2026-11-12"
SEED_FILE = Path(__file__).parent / "data" / "seed_2026_11_12.json"
# sha256 of the committed seed — the file is never rewritten (his list, byte-identical).
SEED_SHA256 = "74ecc4e36bb89f63715c2c65264e0d01a9e07d8a189218012b81cd593bbc1c00"
BASELINE_FILE = Path(__file__).parent / "data" / "baseline_2026_11_12.json"
MEASURED = False
SCREENED_KEYS = ("s2_growth", "capital_quality", "undervalue", "bonde",
                 "fallen_growers", "hot", "quiet_strong", "accel_after_fall")
PANKAJ_KEY = "pankaj"
CATEGORY_KEYS = SCREENED_KEYS + (PANKAJ_KEY,)
OWNER_ONLY = True                                     # MINE default (C10) — HIS CALL §7 #11

# ── list shape — the seed's "rules" (a test pins these equal to the file) ──
PER_CATEGORY = 10
MAX_PER_SECTOR = 3
HOT_MAX_PER_SECTOR = 2

# ── 🚀 Stage 2 growth leaders ──
S2_STAGE = 2
S2_SALES_TIERS = ("strong", "explosive")
S2_STEADY_TIER = "steady"
S2_EPS_CHECKS = ("c_strong_q_eps", "a_strong_y_eps")  # APP check keys on the scan row

# ── 💎 Capital quality ──
CQ_MIN_ROE_PCT = 20.0
CQ_MIN_FCF_MARGIN_PCT = 0.0                           # strict >
CQ_MAX_NET_DEBT_EBITDA = 1.0

# ── 🏷️ Undervalue vs peers (the vs-peers file's own numbers) ──
UV_PS_MAX_FRACTION = UVP.PEER_PS_MAX_FRACTION
UV_MIN_Q_YOY_PCT = UVP.MIN_SALES_YOY_Q_PCT
UV_MIN_TTM_GROWTH_PCT = UVP.MIN_SALES_TTM_GROWTH_PCT
UV_MIN_TTM_REVENUE_USD = UVP.MIN_TTM_REVENUE_USD
FLOOR_TIER = B.DEFAULT_MIN_TIER                       # APP "ok"

# ── 📈 Bonde ──
BONDE_TIERS = ("strong", "explosive")

# ── 📉 Fallen growers turning up ──
FALLEN_MIN_PCT_BELOW = FAL.THRESHOLD_PCT              # HIS 40
FALLEN_MIN_PCT_ABOVE_LOW = 10.0
FALLEN_MIN_SALES_YOY_PCT = 20.0
FALLEN_SORT = FAL.DEFAULT_SORT
FALLEN_PAGE = B.LIMIT_MAX

# ── 🔥 Hot sectors ──
HOT_SALES_TIERS = ("strong", "explosive")
HOT_MIN_Q_EPS_YOY = 0.0                               # strict >
HOT_MIN_RET_21D = 0.0                                 # strict >
HOT_PAGE = H.NAMES_PER_GROUP
HOT_SORT = H.DEFAULT_SORT

# ── 🌱 Strong but not moving yet ──
QUIET_STAGE = 1
QUIET_MIN_SCORE = 70.0
QUIET_MIN_NET_PROFIT = 0.0                            # strict >
QUIET_MIN_OCF = 0.0                                   # strict >
QUIET_MIN_SALES_CAGR_PCT = 15.0
QUIET_MAX_LIAB_TO_EQUITY = 1.0
QUIET_MIN_DOLLAR_VOL = 5_000_000.0
QUIET_MIN_PCT_BELOW_HIGH = 10.0
QUIET_SALES_TIERS = S.BONDE_PASS_TIERS                # APP tuple; as a gate = MINE (seed, post-critique) [C2]
SHARE_CLASS_KEYS = ("net_profit", "ocf", "opm", "sales_cagr", "profit_cagr")
SCORE_IS_MEASURED = LT.SCORE_IS_MEASURED

# ── 🔄 Small & mid caps accelerating after a fall ──
ACCEL_UNIVERSE = "full"
ACCEL_MIN_CAP_USD = 300_000_000.0
ACCEL_MAX_CAP_USD = 10_000_000_000.0
ACCEL_SALES_TIERS = ("strong", "explosive")
ACCEL_MIN_PRIOR_YOY_PCT = 0.0                         # strict >
ACCEL_MIN_PCT_BELOW_HIGH = 30.0
ACCEL_MIN_PCT_ABOVE_LOW = 10.0
ACCEL_STAGES = (1, 2)
ACCEL_MIN_DOLLAR_VOL = 3_000_000.0

# ── 🧭 Pankaj's long-term list ──
PANKAJ_ZONE_PAD_PCT = PK.ZONE_PAD_PCT                 # APP 0.5 (the /pankaj page's in-zone pad) — §7 #23

# ── notices ──
STAGE_DROP_PAIRS = tuple(p for p in STX.TRANSITIONS if p[0] == 2)          # ((2,3),(2,4))
STAGE_DROP_TO = tuple(sorted({p[1] for p in STAGE_DROP_PAIRS}))           # (3, 4)
STARTED_MOVING_PAIR = (1, 2)
SALES_TIER_LADDER = ("declining", "weak") + tuple(S.BONDE_PASS_TIERS)     # low → high
RING_KINDS = ("stage_drop", "sales_drop", "started_moving")                # MINE (C4) — §7 #10

# ── weekly ──
RUN_AFTER_ET = SC.SEPA_RERATE_ET
ENV_SWITCH = "LONG_TERM_LIST_WEEKLY"                  # "0" = off; never assigned in prod
RUNS_COLL = "long_term_list_runs"
FORWARD_COLL = "long_term_list_forward"
CLAIMS_COLL = "long_term_list_claims"
CHILD_ARGV_MODULE = "long_term_list.weekly"
CHILD_NAME = "long_term_list_weekly"

# ── forward record [C7] ──
FORWARD_BASE_KIND = "open"                            # MINE: the first session after SAVED_ON — §7 #8
BENCHMARK = RB.BENCHMARK
BENCHMARK_ALT = RB.BENCHMARK_ALT
FORWARD_MIN_SESSIONS = RB.REBALANCE                   # 21 — a DISPLAY gate, not a test
FORWARD_CI_PCT = 95.0
FORWARD_BOOT_DRAWS = 2000
FORWARD_PLACEBO_DRAWS = 1000
FORWARD_RNG_SEED = 20261112

# ── push (HELD — WP-PUSH not run) ──
DIGEST_KIND = "long_term_digest"
DIGEST_PUSH_MODE = "off"                              # [C9]; "live" only after §7 #1 + WP-PUSH
DIGEST_URL = "/chart-maps?tab=long_term"
DIGEST_BODY_LINES = 6

# name -> "HIS" | "APP" | "MINE" for every number / cut-off set the tab reads.
# Served in the payload's `rules`; his_call = (source == "MINE").
CONSTANT_SOURCES = {
    "PER_CATEGORY": "MINE", "MAX_PER_SECTOR": "MINE", "HOT_MAX_PER_SECTOR": "MINE",
    "S2_STAGE": "APP", "S2_SALES_TIERS": "MINE", "S2_STEADY_TIER": "MINE", "S2_EPS_CHECKS": "MINE",
    "CQ_MIN_ROE_PCT": "MINE", "CQ_MIN_FCF_MARGIN_PCT": "MINE", "CQ_MAX_NET_DEBT_EBITDA": "MINE",
    "UV_PS_MAX_FRACTION": "HIS", "UV_MIN_Q_YOY_PCT": "HIS", "UV_MIN_TTM_GROWTH_PCT": "HIS",
    "UV_MIN_TTM_REVENUE_USD": "HIS", "FLOOR_TIER": "APP",
    "BONDE_TIERS": "MINE",
    "FALLEN_MIN_PCT_BELOW": "HIS", "FALLEN_MIN_PCT_ABOVE_LOW": "MINE", "FALLEN_MIN_SALES_YOY_PCT": "MINE",
    "FALLEN_PAGE": "APP",
    "HOT_SALES_TIERS": "MINE", "HOT_MIN_Q_EPS_YOY": "MINE", "HOT_MIN_RET_21D": "MINE", "HOT_PAGE": "APP",
    "QUIET_STAGE": "APP", "QUIET_MIN_SCORE": "MINE", "QUIET_MIN_NET_PROFIT": "MINE", "QUIET_MIN_OCF": "MINE",
    "QUIET_MIN_SALES_CAGR_PCT": "MINE", "QUIET_MAX_LIAB_TO_EQUITY": "MINE", "QUIET_MIN_DOLLAR_VOL": "MINE",
    "QUIET_MIN_PCT_BELOW_HIGH": "MINE", "QUIET_SALES_TIERS": "MINE",
    "ACCEL_MIN_CAP_USD": "MINE", "ACCEL_MAX_CAP_USD": "MINE", "ACCEL_SALES_TIERS": "MINE",
    "ACCEL_MIN_PRIOR_YOY_PCT": "MINE", "ACCEL_MIN_PCT_BELOW_HIGH": "MINE", "ACCEL_MIN_PCT_ABOVE_LOW": "MINE",
    "ACCEL_STAGES": "MINE", "ACCEL_MIN_DOLLAR_VOL": "MINE",
    "PANKAJ_ZONE_PAD_PCT": "APP",
    "STAGE_DROP_PAIRS": "MINE", "STARTED_MOVING_PAIR": "MINE", "RING_KINDS": "MINE",
    "FORWARD_BASE_KIND": "MINE", "FORWARD_MIN_SESSIONS": "APP", "FORWARD_CI_PCT": "MINE",
    "FORWARD_BOOT_DRAWS": "MINE", "FORWARD_PLACEBO_DRAWS": "MINE", "FORWARD_RNG_SEED": "MINE",
    "DIGEST_PUSH_MODE": "MINE", "DIGEST_BODY_LINES": "MINE",
}
