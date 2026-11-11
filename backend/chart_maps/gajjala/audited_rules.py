"""🧪 Gajjala · Audited — the registry of audit rules + the pure gate math + the served words (BUILD SPEC 2026-11-01 §3.1).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited / So we can keep track of improvements on this tab"

A VERSIONED REGISTRY: each audit-derived rule is one frozen `Rule` with its eod-audits source, the date it joined, its
status (ON on this tab / OFF / lane_only), its verdict and what it changes. The launch set is the four pre-registered
gates of 2026-10-30 (eod-audits/research/2026-10-30_gajjala_gates_prereg.md — frozen before any run): G1 · G2 · G4 ON,
G3 lane_only (a paper-lane ENTRY gate, never a read; nothing in trading/ changes). Every rule is UNMEASURED: the
pre-registered replay read every gate TOO SMALL (report.md "Per gate"; LEDGER.md rows dated 2026-10-30). The rules
FILTER 🚩 Gajjala's A+ read on this tab only — never a new setup, never a push, never the 🚩 tab.

THE EIGHT 2026-11-01 MODIFICATIONS (SPEC gg-audited-mods §3.1). Ajay 2026-11-01: "Yes make the changes in audited
please" and "But keep a track record too to see the winners and loster". Frozen before any code in
eod-audits/research/2026-11-01_gajjala_audited_modifications_prereg.md (byte copy
tests/fixtures/gajjala/audited_modifications_prereg_2026_11_01.md, sha256 PREREG2_SHA256). Six FILTERS on the A+ read
(T1 daily entry cap · T2 first-hour block · A1 time cut · H1 regular hours only · T4 regime gate · A2 volume-spike skip)
and two EXIT GRADES on the 🧪 🏁 beside GG's math (T3 fixed target on the Intraday VCP · T5 21 EMA trail). Every one
is ON on this tab only and UNMEASURED (forward-recorded; the 10-30 cohort is TOO SMALL). 🧪 judges only the A+ bars 🚩
would ring on the same pass (alerts.refusal is None — audited_pass's job); T1 needs the day's claims and the pass's
ring order, so `judge` stays pure and per read (the stateless rules, judge_rules()) and T1 is appended LAST by
`with_t1` over `t1_slots(ring_order(...))`. T4 reads the pass's own scanner strip (`ctx["best_change_pct"]`); without
it T4 fails closed, and H1 fails closed without the session.

THE GATE MATH is ported VERBATIM from the study script (study branch `study/gajjala-gates-2026-10-30`, worktree
wt-gggates, backend/scripts/gajjala_gates_study_2026_10_30.py `g1_pass`, `g2_pass`, `last_red_run`, `risk_pct`,
`g4_pass` :198-258 and `_base_idx` :411-414). The bytes READ for this port: sha256
20bb1970b5c5c9a59921a01afcfd570787ddc65c5c25bc5f8c16ff4ba08b2798 (wt-gggates HEAD 0678034f; byte copy
tests/fixtures/gajjala/gates_study_2026_10_30.py.txt). report.md:5 cites the RUN-2 bytes e308ab74…dfff08 — report.md:47:
"The file was then edited only to print a one-week CI as 'no interval' and to re-render these files from `results.json`
(`--render-only`, no data read)." The run-2 bytes are not in git; the port cites the bytes it read (20bb1970…) beside them.

THE K3S ADMIT (2026-11-09, SPEC gg-k3s §3.2). Ajay 2026-11-09: "yes change the audit as per you like that is yours I
need you to make it successful and earn money that is the goal". Frozen before any code in
eod-audits/research/2026-11-09_gajjala_audited_k3s_prereg.md (byte copy
tests/fixtures/gajjala/audited_k3s_prereg_2026_11_09.md, sha256 PREREG3_SHA256). A third KIND, KIND_ADMIT: K3S ADMITS
a 🚩 "broke — not A+" 🎾 Reversal Squeeze read whose ONLY miss is K3 (`missed == [D.K3_VOL_KEY]`) ON ITS BREAK BAR
(the detector's own `bars_since_entry == 0`) as a 🧪 A+ with 🚩's own plan — the re-read is the ONE detector
(`detectors.reversal_squeeze(..., k3_binding=False)`) with K11 re-applied by the overlay (a partial read never carries
the K11 row). The admitted read then passes through every ON 🧪 filter exactly as a 🚩 A+ would (`judge(..., admit=)`).
K3_VOL_FRAC is untouched; the 🚩 tab is untouched; pushes stay SHADOW. UNMEASURED.

Fail-closed: a rule that reads None FAILS (the A+ is held) and its served why is NONE_WHY[id] — no served string ever
prints "None". `judge` serves JSON-native values only (float / str / int / bool / None — never a Decimal: tab._plain has
no Decimal branch). Every number below carries its source line; GG's own numbers (G2, T4, T5) are read BY NAME from
constants.py.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping, Optional

from daytrading.data import ET_RTH_CLOSE, ET_RTH_OPEN

from . import alerts as AL
from . import constants as GC
from . import detectors as D
from . import ledger as LG
from . import variant as V

# ── the frozen sources (read, never retyped) ────────────────────────────────────────────────────────────────────────
PREREG_PATH = "eod-audits/research/2026-10-30_gajjala_gates_prereg.md"     # under /Users/ajay/clinet-test/ (outside the repo); byte copy tests/fixtures/gajjala/gates_prereg_2026_10_30.md
PREREG_SHA256 = "4ebc30d20e7f3eb19aa6df5fbe2b620d9c19e0e22144ae6620e66ca7bf8d14b6"   # report.md:5 — the frozen prereg
PREREG2_PATH = "eod-audits/research/2026-11-01_gajjala_audited_modifications_prereg.md"   # byte copy tests/fixtures/gajjala/audited_modifications_prereg_2026_11_01.md
PREREG2_SHA256 = "0f6e1e9172696a3b757d89b039dc40820aac6f629182a93a706993e0068a337c"   # shasum -a 256 of the frozen file (written before any code)
PREREG3_PATH = "eod-audits/research/2026-11-09_gajjala_audited_k3s_prereg.md"   # byte copy tests/fixtures/gajjala/audited_k3s_prereg_2026_11_09.md
PREREG3_SHA256 = "be966681e31703f9bba2761d6dd28c0d135108ef93076be000ec8ec516b6ef54"   # shasum -a 256 of the frozen file (written before any code)
PREREG_SHA_BY_PATH = MappingProxyType({PREREG_PATH: PREREG_SHA256, PREREG2_PATH: PREREG2_SHA256,
                                       PREREG3_PATH: PREREG3_SHA256})
REPORT_PATH = "eod-audits/research/gajjala_gates_2026_10_30/report.md"       # copy tests/fixtures/gajjala/gates_report_2026_10_30.md
LEDGER_PATH = "eod-audits/research/LEDGER.md"                                # rows dated 2026-10-30: TOO SMALL (= UNMEASURED); 2026-11-01: UNMEASURED
STUDY_PATH = "wt-gggates/backend/scripts/gajjala_gates_study_2026_10_30.py"  # the ported gate math; byte copy tests/fixtures/gajjala/gates_study_2026_10_30.py.txt
STUDY_SHA256 = "20bb1970b5c5c9a59921a01afcfd570787ddc65c5c25bc5f8c16ff4ba08b2798"   # the file AS PORTED (wt-gggates HEAD 0678034f); report.md:5 cites run-2 bytes e308ab74…dfff08 — report.md:47 "edited only to print a one-week CI … --render-only"
AUDIT_VERSION = 3                                                            # TRANSPORT — bump when judge() changes (stored on every audit block); 2 = the 2026-11-01 modifications; 3 = the 2026-11-09 K3S admit

# ── the rule numbers (each from its prereg row; the in-sample picks of report.md "Per gate" / LEDGER.md) ──────────
G1_K = 2.0                 # prereg row G1 "k ∈ {1.0, 1.5, 2.0}"; the in-sample pick k=2 (LEDGER.md row "gates G1"; report.md §Per gate)
G2_MAX_RED = GC.RED_CLOSES_WAIT   # prereg row G2 "No variants (GG's own number)" = GG X6 by NAME (constants.py RED_CLOSES_WAIT), never a second literal
G2_RUN = "last"            # prereg row G2 "the base's last run"; "longest" = the detectors' chip number the 10-30 replay read (report.md §Judgement calls: disagree on 4 of 26) — HIS CALL
G2_RUNS = ("last", "longest")
G3_MAX_AGE_MIN = 30        # prereg row G3 "m ∈ {10, 20, 30}"; pick m=30 — a LANE entry gate: registered lane_only, NOT applied
G3_MISSED_R = 0.5          # prereg row G3 "MISSED_R ∈ {0.5, 1.0}"; pick 0.5 — lane_only
G4_MAX_RISK_PCT = 10.0     # prereg row G4 "c ∈ {8 %, 10 %, 12 %}"; pick c=10 ("the app's own ABS_MAX_STOP_PCT 10 on every other lane")
FROZEN_STOP_SETUPS = ("reversal_squeeze",)   # prereg row G4 "🎾 stop frozen at the first armed read"; report.md §Judgement calls "the rest read the alert's stop"
MEASURE_FLOOR_WEEKS = 30   # LEDGER.md:11 "TOO SMALL means fewer than 30 OOS entry weeks"; 2026-10-29_strategy_lab.md:29

# ── the 2026-11-01 modifications (each from its prereg2 row; never a second literal of a GG number) ──────────────
KIND_FILTER, KIND_EXIT = "filter", "exit"   # a FILTER removes an A+ on this tab; an EXIT changes the 🏁 grade only
KIND_ADMIT = "admit"                        # 2026-11-09: an ADMIT makes a 🚩 "broke — not A+" read a 🧪 A+ (K3S)
KINDS = (KIND_FILTER, KIND_EXIT, KIND_ADMIT)
T1_DAILY_CAP = 2                            # prereg2 row T1 — GG "one trade a day, two max" (the ceiling); 1 = HIS CALL #16
T1_ORDER = "ring"                           # prereg2 row T1 — 🚩's ring order = alerts._candidates (bar, SETUPS index, symbol) [C3]
T2_FIRST_HOUR_END_ET = dt.time(10, 30)      # prereg2 row T2 "not A+ when the break bar STARTS before 10:30 ET"
A1_LAST_ENTRY_ET = dt.time(11, 59)          # prereg2 row A1 "not A+ when the break bar STARTS after 11:59 ET" — a START ≤ 11:59 passes
H1_OPEN_ET, H1_CLOSE_ET = ET_RTH_OPEN, ET_RTH_CLOSE   # prereg2 row H1 — daytrading.data BY NAME (half days via alerts._closes / is_after_hours_bar)
T4_QUIET_TOP_PCT = GC.SA_QUIET_BEST_PCT     # prereg2 row T4 — GG S8 44:37 bad day by NAME; ≤ fails
A2_SPIKE_MULT = 10.0                        # prereg2 row A2 "≥ 10 × the prior bar's volume" (SYNTHESIS §A3 #2 "skip a 10x prior-candle volume spike")
T3_SETUPS = ("intraday_vcp",)               # prereg2 row T3 "on 🌀 Intraday VCP rows only"
T3_R_MULTS = (2.0, 3.0)                     # prereg2 row T3 "+2R (primary, the lower bound) and +3R" — primary = T3_R_MULTS[0] (HIS CALL #17)
T5_EMA = GC.EMA_SLOW                        # prereg2 row T5 "the 21 EMA" — orderflow.signals EMA_SLOW by NAME
T5_FRAME = V.GG5.primary                    # prereg2 row T5 "the GG5 5-minute frame" — by name

# ── the 2026-11-09 K3S admit (prereg3 "The rule, exactly"; no number of its own — K3_VOL_FRAC by name) ────────────
K3S_SETUPS = ("reversal_squeeze",)          # prereg3 "Setup: `reversal_squeeze` only."
K3S_MISSED = (D.K3_VOL_KEY,)                # prereg3 "`missed` is exactly `["k3_vol"]`" — the detector's key by name


def exit_col_key(rule_id: str, r_mult=None) -> str:
    """The exits-collection column of an EXIT rule: "T3_2R" / "T3_3R" (one per r_mult) / "T5" — built, never typed."""
    return f"{rule_id}_{r_mult:g}R" if r_mult is not None else str(rule_id)


def build_exit_cols() -> tuple:
    """Every exit column, from T3_R_MULTS (read at call time) + T5 [C8]."""
    return tuple(exit_col_key("T3", k) for k in T3_R_MULTS) + (exit_col_key("T5"),)


EXIT_COLS = build_exit_cols()               # == ("T3_2R", "T3_3R", "T5") by test — built, never typed [C8]

# ── words / states ──────────────────────────────────────────────────────────────────────────────────────────────────
STATUS_ON, STATUS_OFF, STATUS_LANE_ONLY = "on", "off", "lane_only"
STATUSES = (STATUS_ON, STATUS_OFF, STATUS_LANE_ONLY)
VERDICT_UNMEASURED = "UNMEASURED"
HELD_STATE = "aplus_held"  # the audited tab's SERVED state for a GG5 A+ an ON rule removed — never stored on a GG5 doc, never a detectors state
HELD_ROW_STATE = "held"    # the GGA alerts row "GGA:{date}|SYM|setup#held" (alerts._record; `#` = never a 🏁 row)
NEVER_SENDS = "the audited variant never sends — recorded only"
NONE_WHY = MappingProxyType({                       # one served sentence per rule when a rule reads None (fail-closed stays)
    "G1": "not judgeable — the break bar is not on the frame",
    "G2": "not judgeable — no run to read",
    "G4": "not judgeable — no trigger or stop to read",
    "T1": "not judgeable — today's audited entries could not be read",
    "T2": "not judgeable — the break bar has no clock",
    "A1": "not judgeable — the break bar has no clock",
    "H1": "not judgeable — the break bar has no clock",
    "T4": "not judgeable — the pass holds no top runner",
    "A2": "not judgeable — no prior bar to compare",
})
FROZEN_REASONS = MappingProxyType({                 # values.G4.frozen_reason — the card says WHY the stop it read
    "frozen": "🎾 stop frozen at the first armed read",
    "no_match": "no armed read with this trigger — the alert's stop",
    "not_squeeze": "not a 🎾 read — the alert's stop",
})
T1_KEPT = "kept — claimed earlier today"            # values.T1.slot of an A+ whose (symbol, setup) was claimed on an earlier pass
T1_TIE_TEXT = " — tied on one bar, 🚩's ring order broke it"
AUDIT_SERVED_KEYS = ("aplus", "original_aplus", "rules", "passed", "failed", "values", "text", "version", "frame",
                     "admit")                # 2026-11-09: `admit` = the ADMIT rule's id on a K3S block, None on every other
K3S_PARTIAL_ROW_STATE = "partial_break"      # the GGA alerts row "GGA:{date}|SYM|reversal_squeeze#partial_break" (first-wins; never a 🏁 row, never a claim)
ADMIT_TEXT_OK = "🧪 A+ by {admit} — 🚩 reads it '{reason}' · {ids} pass · {unmeasured}"
ADMIT_TEXT_HELD = "🧪 A+ by {admit} (🚩 reads it '{reason}'), held here by: {fails} · {unmeasured}"
STATUS_TEXT = MappingProxyType({
    STATUS_ON: "ON on this tab",
    STATUS_OFF: "OFF — listed, not applied",
    STATUS_LANE_ONLY: "lane only — registered, not applied on this tab",
})

_FIRST_HAND = "tests/fixtures/gajjala/first_hand_2026_10_13.md"   # backend-relative
_VR = "chart_maps/gajjala/verified_rules.json"                     # backend-relative


@dataclass(frozen=True)
class Rule:
    """One registry entry. `rule` is a template formatted with `params` at serve time (the FE composes nothing).
    `kind` / `prereg` (2026-11-01) are TRAILING with defaults — G1–G4 are built positionally and stay byte-equal."""
    id: str
    name: str
    date_added: str
    status: str
    applies: bool
    rule: str
    params: Mapping
    source: tuple            # ((path, quote), …) — source[0] is the frozen prereg row
    gg: tuple                # ((file, where, quote), …) — GG's own words on file in this repo
    verdict: str
    verdict_source: str
    changes: str
    note: str
    kind: str = KIND_FILTER  # KIND_FILTER (removes an A+ on this tab) | KIND_EXIT (a 🏁 grade beside GG's math) | KIND_ADMIT
    prereg: str = PREREG_PATH   # the frozen prereg this entry was registered in (PREREG_SHA_BY_PATH)


G1 = Rule(
    "G1", "break-bar proof", "2026-11-01", STATUS_ON, True,
    "A+ only when the break bar CLOSES above the trigger AND its volume ≥ {k:g} × the mean volume of the base bars",
    MappingProxyType({"k": G1_K}),
    ((PREREG_PATH, "A+ only when the 5-min break bar CLOSES above the trigger AND its volume ≥ k × the mean volume of "
                   "the base bars. k ∈ {1.0, 1.5, 2.0}"),
     (REPORT_PATH, "k=2 (2 · 0.401)")),
    ((_FIRST_HAND, "222", "to prove it."),
     (_VR, "topics[0].verified[7]", "I just trade the price and volume action")),
    VERDICT_UNMEASURED, "LEDGER.md row 'gates G1' 2026-10-30: TOO SMALL — OOS 4 trades, 1 entry week",
    "a FILTER on the A+ read — never a new setup, never a push, never a lane gate",
    "a break with no base bars reads 'no proof' (report.md:54). Judged on the read's OWN frame: 5-minute for Bull Flag · "
    "Kiss & Fly · Intraday VCP · 🎾, 15-minute for the Horizontal Fade — the prereg row says '5-min break bar'; HIS "
    "CALL #14")
G2 = Rule(
    "G2", "red closes", "2026-11-01", STATUS_ON, True,
    "not A+ when the base's {run} run has more than {max_red} consecutive red closes",
    MappingProxyType({"max_red": G2_MAX_RED, "run": G2_RUN}),
    ((PREREG_PATH, "not A+ when the base's last run has > 3 consecutive red 5-min closes. No variants (GG's own "
                   "number)"),
     (REPORT_PATH, "max_red=3 (18 · -0.060)")),
    ((_VR, "topics[10].verified[5]", "more than 3 red closes is red flag to me => wait more"),),
    VERDICT_UNMEASURED, "LEDGER.md row 'gates G2' 2026-10-30: TOO SMALL — OOS 4 trades, 1 entry week",
    "a FILTER on the A+ read — never a new setup, never a push, never a lane gate",
    "the 10-30 replay read the detectors' longest run; this tab reads the prereg's last run (G2_RUN) — HIS CALL. Judged "
    "on the read's OWN frame (the Horizontal Fade's is 15-minute; the prereg says 'red 5-min closes') — HIS CALL #14")
G3 = Rule(
    "G3", "ring age at the tick", "2026-11-01", STATUS_LANE_ONLY, False,
    "no lane entry when the ring is older than {m} minutes at the tick, or the tick is past trigger + {missed_r:g} × R",
    MappingProxyType({"m": G3_MAX_AGE_MIN, "missed_r": G3_MISSED_R}),
    ((PREREG_PATH, "no lane entry when the ring is older than m minutes at the tick, m ∈ {10, 20, 30}; MISSED_R ∈ "
                   "{0.5, 1.0}"),
     (REPORT_PATH, "m=30, missed_r=0.5 (11 · -0.267)")),
    (),
    VERDICT_UNMEASURED, "LEDGER.md row 'gates G3' 2026-10-30: TOO SMALL — OOS 3 trades, 1 entry week",
    "nothing on this tab — a paper-lane entry gate, registered only",
    "a PAPER-LANE entry gate, not a read — not applied on this tab; nothing in trading/ changes; the lane trades 🚩 "
    "Gajjala's A+ only")
G4 = Rule(
    "G4", "stop-distance cap", "2026-11-01", STATUS_ON, True,
    "not A+ when (trigger − stop)/trigger > {c_pct:g}%; on 🎾 the stop is frozen at the first armed read with the "
    "alert's trigger",
    MappingProxyType({"c_pct": G4_MAX_RISK_PCT, "frozen_setups": FROZEN_STOP_SETUPS}),
    ((PREREG_PATH, "not A+ when (trigger − stop)/trigger > c, c ∈ {8 %, 10 %, 12 %}; 🎾 stop frozen at the first armed "
                   "read"),
     (REPORT_PATH, "c=10 (20 · 0.103)")),
    ((_VR, "topics[11].verified[2]", "a breakout back into its range = out"),),
    VERDICT_UNMEASURED, "LEDGER.md row 'gates G4' 2026-10-30: TOO SMALL — OOS 5 trades, 1 entry week",
    "a FILTER on the A+ read — the trade's own stop and R stay the alert's; never the 🚩 tab",
    "on 🎾 the cap reads the stop of the first armed read with the alert's trigger, else the alert's stop "
    "(report.md §Judgement calls)")

# ── the eight 2026-11-01 modifications (prereg2 rows; source[0][1] is a substring of the frozen file) ───────────────
_V2 = "LEDGER.md row '🧪 {}' 2026-11-01: UNMEASURED — forward-recorded on 🧪; the 10-30 cohort (26 filled A+) is TOO SMALL"
_FILTER_CHANGES = "a FILTER on the A+ read — never a new setup, never a push, never the 🚩 tab"
_EXIT_CHANGES = "an EXIT GRADE on the 🏁 beside GG's math — the A+ read, the claim and the push are untouched"

T1 = Rule(
    "T1", "daily entry cap", "2026-11-01", STATUS_ON, True,
    "at most {cap} audited A+ a day — slots in claim order, then 🚩's ring order within a pass (entry bar, setup "
    "order, symbol); an A+ already claimed today keeps its slot",
    MappingProxyType({"cap": T1_DAILY_CAP, "order": T1_ORDER}),
    ((PREREG2_PATH, "daily entry cap: at most 2 audited A+ a day. Slots go in claim order — an A+ claimed on an earlier "
                    "pass keeps its slot — and within one pass in 🚩's ring order (entry bar, then setup order, then "
                    "symbol — the order the pushes leave the pass, alerts._candidates); only a bar 🚩 would ring takes "
                    "a slot; two A+ on the same bar are a TIE broken by that order — flagged and counted, the tie rule "
                    "itself is HIS CALL"),),
    (),
    VERDICT_UNMEASURED, _V2.format("T1"),
    "a FILTER on the A+ read, judged LAST over the day's audited entries — never the 🚩 tab",
    "cap = his ceiling 'two max' (podcast 10pHBNVi4Jc 1:28:10); 1 is the floor — HIS CALL #16. The order is 🚩's own "
    "ring order (alerts._candidates — the order the pushes leave the pass); two A+ on ONE bar tie and the tie breaks by "
    "setup order then symbol — flagged `tie` and counted; the tie rule is HIS CALL #16. Only a bar 🚩 would ring takes "
    "a slot. GG said 2–4 a day in a good market (CI7mNvEQyms 49:48)",
    KIND_FILTER, PREREG2_PATH)
T2 = Rule(
    "T2", "first-hour block", "2026-11-01", STATUS_ON, True,
    "not A+ when the break bar starts before {cut:%H:%M} ET",
    MappingProxyType({"cut": T2_FIRST_HOUR_END_ET}),
    ((PREREG2_PATH, "not A+ when the break bar STARTS before 10:30 ET; a bar whose start is 10:30:00 passes; the bars "
                    "before 09:45 never reach 🧪 (🚩 never rings them), so this record is the 09:45–10:29 bars"),),
    ((_VR, "topics[3].verified[9]", "Most profitable hours in 2023: 11 AM and 5 PM ET; the first hour was the worst"),),
    VERDICT_UNMEASURED, _V2.format("T2"), _FILTER_CHANGES,
    f"the bar is judged by its START (alerts.window_reason convention); a start of exactly "
    f"{T2_FIRST_HOUR_END_ET:%H:%M} passes. 🚩 never rings a bar before 09:45 (its own window), so this record is the "
    f"09:45–10:29 bars. GG's 2023 TraderSync chart, self-reported",
    KIND_FILTER, PREREG2_PATH)
A1 = Rule(
    "A1", "time cut", "2026-11-01", STATUS_ON, True,
    "not A+ when the break bar starts after {cut:%H:%M} ET",
    MappingProxyType({"cut": A1_LAST_ENTRY_ET, "k8": GC.K8_MAX_FLOAT}),
    ((PREREG2_PATH, "not A+ when the break bar STARTS after 11:59 ET; a bar starting 11:55 is the last 5-minute bar to "
                    "pass, a 12:00 bar fails; the float < 100M half is a NO-OP (K8_MAX_FLOAT 10,000,000)"),),
    (),
    VERDICT_UNMEASURED, _V2.format("A1"), _FILTER_CHANGES,
    f"a bar starting 11:55 is the last 5-minute bar to pass; 12:00 fails. The float < 100M half of the source is a "
    f"NO-OP here: 🚩's K8 caps the universe at {GC.K8_MAX_FLOAT:,} shares (GC.K8_MAX_FLOAT) and a suspect float is "
    f"ineligible — verified, not built",
    KIND_FILTER, PREREG2_PATH)
H1 = Rule(
    "H1", "regular hours only", "2026-11-01", STATUS_ON, True,
    "not A+ when the break bar starts outside {open:%H:%M}–{close:%H:%M} ET (the regular close on a half day)",
    MappingProxyType({"open": H1_OPEN_ET, "close": H1_CLOSE_ET}),
    ((PREREG2_PATH, "not A+ when the break bar STARTS outside the regular session 09:30–16:00 ET (13:00 on a half "
                    "day): 15:55 passes, 16:00 fails; premarket bars never reach 🧪, so this record is the after-hours "
                    "bars"),),
    ((_VR, "topics[1].verified[5]", "Very little premarket trading; outside regular hours: limit orders only, less "
                                    "size."),),
    VERDICT_UNMEASURED, _V2.format("H1"), _FILTER_CHANGES,
    "re-look 10-29: 4 of 5 unfilled A+ rang after hours. Premarket bars never reach 🧪 (🚩's window), so this record "
    "is the after-hours bars. The 🚩 tab's own window is untouched — keep or cut there is HIS CALL #22",
    KIND_FILTER, PREREG2_PATH)
T4 = Rule(
    "T4", "regime gate", "2026-11-01", STATUS_ON, True,
    "not A+ when the day's top scanner runner is ≤ +{pct:g}% at the ring",
    MappingProxyType({"pct": T4_QUIET_TOP_PCT}),
    ((PREREG2_PATH, "not A+ when the day's top scanner runner at the ring is ≤ +40% (GC.SA_QUIET_BEST_PCT by name); "
                    "40.0 fails, 40.01 passes; no number on the pass → fail-closed; PROVENANCE: unverified overflow "
                    "(REPORT §6 T4); served: fired = holds where T4 failed, fired alone = holds where ONLY T4 "
                    "failed"),),
    (),
    VERDICT_UNMEASURED, _V2.format("T4"), _FILTER_CHANGES,
    "unverified overflow (REPORT §6 T4: GG webinar CI7mNvEQyms ~43:15–45:30). Ross audit Q5: a ≥50% mover existed by "
    "10:00 on 501 of 504 days, so this gate may almost never fire. Count how often it fires before anything else — "
    "the 🏁 serves `fired` (T4 failed) and `fired alone` (only T4 failed) over the bars 🚩 rang. The number is "
    "GC.SA_QUIET_BEST_PCT by name; the strip's `quiet` flag uses a strict < — the equality case is HIS CALL #18",
    KIND_FILTER, PREREG2_PATH)
A2 = Rule(
    "A2", "volume-spike skip", "2026-11-01", STATUS_ON, True,
    "not A+ when the break bar's volume is ≥ {mult:g}× the prior bar's volume",
    MappingProxyType({"mult": A2_SPIKE_MULT}),
    ((PREREG2_PATH, "not A+ when the break bar's volume ≥ 10 × the prior bar's volume on the read's own frame; exactly "
                    "10× fails, 9.9× passes; no prior bar or a zero prior volume → fail-closed"),),
    ((_VR, "topics[5].verified[3]", "Volume step: \"twice, thrice\" the previous candle is fine, ~10× = climax / "
                                    "invalid"),),
    VERDICT_UNMEASURED, _V2.format("A2"), _FILTER_CHANGES,
    f"judged on the read's OWN frame (HIS CALL #14 carries over); exactly {A2_SPIKE_MULT:g}× fails; no prior bar or a "
    f"zero prior volume → fail-closed. Source F4VS: '2-3x is fine'",
    KIND_FILTER, PREREG2_PATH)
T3 = Rule(
    "T3", "fixed target on the Intraday VCP", "2026-11-01", STATUS_ON, True,
    "on 🌀 Intraday VCP rows: win when +{r1:g}R (and, as a second column, +{r2:g}R) prints before the stop — the 🏁's "
    "fill and stop rules",
    MappingProxyType({"r1": T3_R_MULTS[0], "r2": T3_R_MULTS[1], "setups": T3_SETUPS}),
    ((PREREG2_PATH, "exit grade on 🌀 Intraday VCP rows only: +2R (primary, the lower bound) and +3R fixed targets with "
                    "the 🏁's fill and stop-touch rules; the fill minute's high never counts"),),
    (),
    VERDICT_UNMEASURED, _V2.format("T3"), _EXIT_CHANGES,
    f"primary = the lower bound {T3_R_MULTS[0]:g}R, stated first — HIS CALL #17. adminapius Strategy R with a fixed "
    f"2R: 178 trades, −0.142R (REPORT §5) — a different lane",
    KIND_EXIT, PREREG2_PATH)
T5 = Rule(
    "T5", "21 EMA trail", "2026-11-01", STATUS_ON, True,
    "after the fill, exit at the first {frame_min:g}-minute close under the {ema:g} EMA; the stop still first",
    MappingProxyType({"ema": T5_EMA, "frame_min": AL.FRAME_MINUTES[T5_FRAME], "frame": T5_FRAME}),
    ((PREREG2_PATH, "exit grade on every setup: after the fill, exit at the first 5-minute CLOSE strictly under the 21 "
                    "EMA of the GG5 5-minute frame (warm-up None = no exit); a stop touch first = −1R; R = (exit − "
                    "fill)/(trigger − stop); open when neither by the regular close"),),
    ((_VR, "topics[11].verified[9]", "Dollar Wisdom's \"exit everything on a close below the 21 EMA, 3 setups\" — "
                                     "never implemented."),),
    VERDICT_UNMEASURED, _V2.format("T5"), _EXIT_CHANGES,
    "claim_only, unverified overflow (Dollar Wisdom uG8CzABsIPM); contradicts GG's 9 EMA trail (VR 11.4) — a true "
    "modification, not GG. The 5-minute frame for every setup incl. the Horizontal Fade (HIS CALL #20)",
    KIND_EXIT, PREREG2_PATH)
# ── the 2026-11-09 K3S admit (prereg3; source quotes are single lines of the frozen file) ─────────────────────────
K3S = Rule(
    "K3S", "K3 volume-dry not binding on the 🎾 base", "2026-11-09", STATUS_ON, True,
    "a 🎾 Reversal Squeeze break that 🚩 refuses ONLY on K3 (volume dried up in the base: no base bar above {frac:g}× "
    "the average bar of the run back up) is a 🧪 A+ at that break bar with 🚩's own trigger, stop and R; K11 session "
    "volume re-applied; every other 🧪 rule then applies",
    MappingProxyType({"frac": GC.K3_VOL_FRAC, "setups": K3S_SETUPS, "missed": K3S_MISSED}),
    ((PREREG3_PATH, "Fires when: the 🚩 read's state is \"partial\", its break bar is identified (`entry_bar_t` set), "
                    "and `missed` is exactly"),
     (PREREG3_PATH, "Output: a 🧪 A+ ring at that break bar with 🚩's OWN plan unchanged — trigger, stop, R, risk % — no "
                    "new number anywhere.")),
    ((_FIRST_HAND, "110", "gradual decrease in volume"),),
    VERDICT_UNMEASURED,
    "LEDGER.md row '🧪 K3S' 2026-11-09: UNMEASURED — forward-recorded on 🧪; the 11-04/11-05 cohort (9 reads, 0 🚩 🎾 A+) "
    "is a motivating observation, not a result",
    "an ADMIT on the A+ read — a 🧪 A+ 🚩 never rings, with 🚩's own plan; never a new setup, never a push, never the 🚩 "
    "tab; K3_VOL_FRAC untouched",
    f"nine 🎾 reads on 2026-11-04/05 broke partial on K3 alone with zero 🚩 🎾 A+ — a cohort, not a result. GG's words on "
    f"the squeeze base are qualitative (S8 36:12); the {GC.K3_VOL_FRAC:g}× number is Ajay's K3. Judged on the break bar "
    f"only; K11 re-applied with the pass's own session volume, fail-closed. Decision rule: at n ≥ 30 rings a positive "
    f"read → a paper-lane variant ONLY on HIS CALL; null → OFF and the row stays. 🚩's own 🎾 A+ arm may be too small to "
    f"compare — the placebos are the lab's read. HIS CALLs #37–#49",
    KIND_ADMIT, PREREG3_PATH)
REGISTRY = (G1, G2, G3, G4, T1, T2, A1, H1, T4, A2, T3, T5, K3S)   # display order = the ask's order


def validate() -> None:
    """Raise ValueError on a junk G2_RUN or a registry entry outside STATUSES / KINDS, an ON rule that does not apply,
    or a prereg path that is not pinned (run at import; g2_run re-checks G2_RUN at call time)."""
    if G2_RUN not in G2_RUNS:
        raise ValueError(f"audited_rules: G2_RUN must be one of {G2_RUNS}, not {G2_RUN!r}")
    for r in REGISTRY:
        if r.status not in STATUSES:
            raise ValueError(f"audited_rules: {r.id} status {r.status!r} not in {STATUSES}")
        if r.status == STATUS_ON and not r.applies:
            raise ValueError(f"audited_rules: {r.id} is ON but does not apply")
        if r.kind not in KINDS:
            raise ValueError(f"audited_rules: {r.id} kind {r.kind!r} not in {KINDS}")
        if r.prereg not in PREREG_SHA_BY_PATH:
            raise ValueError(f"audited_rules: {r.id} prereg {r.prereg!r} is not pinned")


validate()


def on_rules() -> tuple:
    """Every rule this tab APPLIES (status ON and applies) — filters AND exit grades, registry order."""
    return tuple(r for r in REGISTRY if r.status == STATUS_ON and r.applies)


def filter_rules() -> tuple:
    """on_rules() that FILTER the A+ read (T1 included), registry order."""
    return tuple(r for r in on_rules() if r.kind == KIND_FILTER)


def judge_rules() -> tuple:
    """filter_rules() minus T1 — the stateless per-read rules `judge` applies, in order (G1 G2 G4 T2 A1 H1 T4 A2)."""
    return tuple(r for r in filter_rules() if r.id != T1.id)


def exit_rules() -> tuple:
    """on_rules() that change the 🏁 grade only (T3 T5)."""
    return tuple(r for r in on_rules() if r.kind == KIND_EXIT)


def admit_rules() -> tuple:
    """on_rules() that ADMIT a 🚩 "broke — not A+" read as a 🧪 A+ (K3S) — never in filter_rules / judge_rules."""
    return tuple(r for r in on_rules() if r.kind == KIND_ADMIT)


def k3s_on() -> bool:
    """K3S is ON on this tab (status ON and applies)."""
    return K3S in admit_rules()


def _int0(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x == 0


def k3s_partial(read) -> bool:
    """PURE. A 🎾 read 🚩 stored "partial" ON ITS BREAK PASS (the detector's own `bars_since_entry == 0`, detectors
    _resolve_break) with a non-empty `missed` — any missed set (the `#partial_break` marker's predicate: placebo (a)
    included). Never a read with an unjudged row, a variant or a grade."""
    if not isinstance(read, dict) or read.get("setup") not in K3S_SETUPS:
        return False
    missed = read.get("missed")
    return (read.get("state") == "partial" and read.get("broke") is True and bool(read.get("entry_bar_t"))
            and _int0(read.get("bars_since_entry")) and isinstance(missed, (list, tuple)) and len(missed) > 0
            and not read.get("unjudged") and not read.get("variant") and not read.get("grade"))


def k3s_candidate(read) -> bool:
    """PURE. k3s_partial AND `missed` is EXACTLY K3S_MISSED (K3 the only miss) — a name is a candidate once, on its
    break bar; the same read one bar later is not."""
    return k3s_partial(read) and list(read["missed"]) == list(K3S_MISSED)


def by_id(i) -> Optional[Rule]:
    return next((r for r in REGISTRY if r.id == i), None)


def _g(x) -> str:
    if isinstance(x, dt.time):
        return x.strftime("%H:%M")
    return f"{x:g}" if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def _params_text(r: Rule) -> str:
    p = r.params
    if r.id == "G1":
        return f"k = {_g(p['k'])}"
    if r.id == "G2":
        return f"more than {_g(p['max_red'])} red closes · the base's {p['run']} run"
    if r.id == "G3":
        return f"m = {_g(p['m'])} min · MISSED_R = {_g(p['missed_r'])}"
    if r.id == "G4":
        return f"c = {_g(p['c_pct'])}% · {FROZEN_REASONS['frozen']}"
    if r.id == "T1":
        return f"cap = {_g(p['cap'])} a day · 🚩's ring order"
    if r.id == "T2":
        return f"break bar starts at or after {_g(p['cut'])} ET"
    if r.id == "A1":
        return f"break bar starts at or before {_g(p['cut'])} ET"
    if r.id == "H1":
        return f"break bar starts inside {_g(p['open'])}–{_g(p['close'])} ET"
    if r.id == "T4":
        return f"top runner above +{_g(p['pct'])}% (his bad-day number)"
    if r.id == "A2":
        return f"break-bar volume under {_g(p['mult'])}× the prior bar"
    if r.id == "T3":
        return f"+{_g(p['r1'])}R and +{_g(p['r2'])}R · 🌀 Intraday VCP only"
    if r.id == "T5":
        return f"{_g(p['frame_min'])}-minute close under the {_g(p['ema'])} EMA"
    if r.id == "K3S":
        return (f"🎾 only · fires when K3 volume dried up in the base (no bar above {_g(p['frac'])}× the average bar "
                f"of the run back up) is the ONLY miss on the break bar · K11 re-applied · 🚩's plan unchanged")
    return ", ".join(f"{k} = {_g(v)}" for k, v in p.items())


def registry_rows() -> list:
    """The served registry: one dict of WORDS per rule (the FE prints them, composes nothing)."""
    out = []
    for r in REGISTRY:
        gg = " · ".join(f"GG: \"{q}\"" for _f, _w, q in r.gg)
        src = f"pre-registered {r.source[0][0]} (sha256 {PREREG_SHA_BY_PATH[r.prereg][:12]}…)"
        out.append({"id": r.id, "name": r.name, "rule": r.rule.format(**r.params), "params_text": _params_text(r),
                    "source_text": src + (" · " + gg if gg else ""), "since": r.date_added, "status": r.status,
                    "status_text": STATUS_TEXT[r.status], "verdict": r.verdict,
                    "verdict_text": f"{r.verdict} — {r.verdict_source}", "changes_text": r.changes,
                    "applies": r.applies, "note": r.note, "kind": r.kind})
    return out


def rules_clause() -> str:
    """The ℹ️ panel's sentence for the audited tab — every number formatted from the constants above (no literal)."""
    filters = "; ".join(f"{r.id} {r.name} ({r.rule.format(**r.params)})" for r in filter_rules())
    exits = "; ".join(f"{r.id} {r.name} ({r.rule.format(**r.params)})" for r in exit_rules())
    admits = "; ".join(f"{r.id} {r.name} ({r.rule.format(**r.params)})" for r in admit_rules())
    admit_txt = (f"Admits on the A+ read — a 🧪 A+ 🚩 never rings, with 🚩's own plan: {admits}. " if admits else "")
    lane = [r for r in REGISTRY if r.status == STATUS_LANE_ONLY]
    lane_txt = " ".join(f"{r.id} {r.name} ({_params_text(r)}) is a paper-lane entry gate — registered, not applied on "
                        f"this tab." for r in lane)
    return (f"🧪 Gajjala · Audited — an overlay on 🚩 Gajjala's A+ reads, recorded in shadow, never sent: {filters}. "
            f"Exit grades on its 🏁 beside GG's math: {exits}. "
            f"{admit_txt}"
            f"{lane_txt} A removed A+ is listed as held, never hidden; the 🚩 tab is never filtered. Every rule is "
            f"{VERDICT_UNMEASURED} (the pre-registered replay read TOO SMALL against the lab's "
            f"{_g(MEASURE_FLOOR_WEEKS)}-week floor; the newest entries are recorded forward on this tab).")


# ── the pure gate math (ported VERBATIM from the study, sha256 20bb1970…2798 — see the module docstring) ───────────
def base_idx(F, base) -> list:
    """study `_base_idx`: the frame indices of the read's base span ([] when either end is not on the frame)."""
    if not isinstance(base, dict) or base.get("from_t") not in F.t or base.get("to_t") not in F.t:
        return []
    return list(range(F.t.index(base["from_t"]), F.t.index(base["to_t"]) + 1))


def g1_pass(F, j: int, trigger, idx, k=None) -> Optional[bool]:
    """Break bar j CLOSES above the trigger AND its volume ≥ k × the mean volume of the base bars. None = no base."""
    k = G1_K if k is None else k
    idx = list(idx or [])
    if not idx or not (0 <= j < len(F.c)):
        return None
    mv = D._mean(F.v[i] for i in idx)
    return D._and(D.gt(LG._D(F.c[j]), LG._D(trigger)), D.ge(F.v[j], D._mul(mv, k)))


def last_red_run(F, idx) -> int:
    """The length of the most recent run of consecutive red closes among `idx` (detectors._is_red)."""
    last = cur = 0
    for k in idx or []:
        if D._is_red(F, k):
            cur += 1
            last = cur
        else:
            cur = 0
    return last


def g2_run(F, idx, read) -> Optional[int]:
    """The run G2 reads: G2_RUN "last" → last_red_run over the base (None when the base is not on the frame — no run
    to read, fail-closed); "longest" → the detectors' own `red_closes` (an int, never a bool), else None. A junk
    G2_RUN raises ValueError."""
    if G2_RUN not in G2_RUNS:
        raise ValueError(f"audited_rules: G2_RUN must be one of {G2_RUNS}, not {G2_RUN!r}")
    if G2_RUN == "last":
        return last_red_run(F, idx) if idx else None
    rc = (read or {}).get("red_closes")
    return rc if isinstance(rc, int) and not isinstance(rc, bool) else None


def g2_pass(run) -> Optional[bool]:
    """Pass unless the base ran MORE than GC.RED_CLOSES_WAIT red closes in a row (3 pass, 4 fail). None = no run."""
    if isinstance(run, bool) or not isinstance(run, int):
        return None
    return D.le(run, G2_MAX_RED)


def risk_pct(trigger, stop) -> Optional[Decimal]:
    plan, r = LG.plan_of(trigger, stop)
    if plan != LG.PLANS[0]:
        return None
    return LG._D(r) / LG._D(trigger) * 100


def g4_pass(trigger, cap_stop, c=None) -> Optional[bool]:
    """Pass unless (trigger − stop)/trigger > c %. `cap_stop` = the alert's stop (🎾: frozen at the first armed read)."""
    c = G4_MAX_RISK_PCT if c is None else c
    p = risk_pct(trigger, cap_stop)
    return None if p is None else bool(p <= LG._D(c))


def cap_stop_for(read: dict, frozen) -> tuple:
    """(stop, frozen_used, frozen_reason key) — on a FROZEN_STOP_SETUPS read, the stop of the first frozen entry whose
    trigger equals the read's (LG._D both sides) → "frozen"; no such entry → the read's stop, "no_match"; any other
    setup never reads the frozen list → the read's stop, "not_squeeze"."""
    read = read or {}
    stop = read.get("stop")
    if read.get("setup") not in FROZEN_STOP_SETUPS:
        return stop, False, "not_squeeze"
    trig = LG._num(read.get("trigger"))
    if trig is not None:
        for e in frozen or []:
            if not isinstance(e, dict):
                continue
            et, es = LG._num(e.get("trigger")), LG._num(e.get("stop"))
            if et is None or es is None:
                continue
            if LG._D(et) == LG._D(trig):
                return es, True, "frozen"
    return stop, False, "no_match"


# ── the judge (the AUDIT BLOCK — served per tile, stored per setup) ────────────────────────────────────────────────
def _px(x) -> str:
    from .tab import _px as tab_px                       # the ONE price formatter (lazy: tab imports the world)
    return tab_px(x)


def _vol(x) -> str:
    from .tab import _compact
    return _compact(x) or "—"


def _dstr(x) -> Optional[str]:
    """A price as the detectors store it, printed lossless: the decimal the float prints as (LG._D) — a str."""
    v = LG._num(x)
    return None if v is None else str(LG._D(v))


def _fnum(x) -> Optional[float]:
    v = LG._num(x)
    return None if v is None else float(v)


# ── the 2026-11-01 per-read rules (pure; tri-state — None = not judgeable → the A+ is held, fail-closed) ────────────
def bar_start_et(entry_bar_t, frame) -> Optional[dt.datetime]:
    """The START of the bar stamped `entry_bar_t` (its CLOSE, bars.py) on `frame` — alerts.window_reason's convention:
    alerts.bar_close_et(t) − the frame's minutes (alerts.FRAME_MINUTES; an unknown frame reads the GG5 primary's).
    None when the stamp is unparsable."""
    close = AL.bar_close_et(entry_bar_t)
    if close is None:
        return None
    return close - dt.timedelta(minutes=AL.FRAME_MINUTES.get(frame, AL.FRAME_MINUTES[V.GG5.primary]))


def t2_pass(start_et) -> Optional[bool]:
    """T2: pass when the break bar STARTS at or after T2_FIRST_HOUR_END_ET (10:30:00 passes, 10:25 fails)."""
    if not isinstance(start_et, dt.datetime):
        return None
    return start_et.time() >= T2_FIRST_HOUR_END_ET


def a1_pass(start_et) -> Optional[bool]:
    """A1: pass when the break bar STARTS at or before A1_LAST_ENTRY_ET (11:55 passes, 12:00 fails)."""
    if not isinstance(start_et, dt.datetime):
        return None
    return start_et.time() <= A1_LAST_ENTRY_ET


def _rth_close(session) -> Optional[dt.time]:
    """The session's regular close (13:00 on a half day) — alerts._closes, the house calendar. None when unreadable."""
    if session is None:
        return None
    try:
        return AL._closes(session)[0]
    except (TypeError, ValueError):
        return None


def h1_pass(entry_bar_t, session, frame) -> Optional[bool]:
    """H1: pass when the break bar STARTS inside the regular session — at or after H1_OPEN_ET and not an after-hours
    bar (alerts.is_after_hours_bar: START ≥ the session's regular close). None with no clock or no session."""
    start = bar_start_et(entry_bar_t, frame)
    if start is None or _rth_close(session) is None:
        return None
    return start.time() >= H1_OPEN_ET and not AL.is_after_hours_bar(entry_bar_t, session, frame)


def t4_pass(best_change_pct) -> Optional[bool]:
    """T4: pass when the day's top scanner runner is ABOVE T4_QUIET_TOP_PCT (40.0 fails, 40.01 passes). None = no
    number on the pass."""
    best = LG._num(best_change_pct)
    if best is None:
        return None
    return not D.le(best, T4_QUIET_TOP_PCT)


def a2_pass(F, j) -> Optional[bool]:
    """A2: pass unless frame bar j's volume ≥ A2_SPIKE_MULT × bar j−1's (exactly 10× fails, 9.9× passes). None = no
    prior bar, a zero / missing prior volume, or no volume on bar j."""
    vs = list(getattr(F, "v", None) or []) if F is not None else []
    if not isinstance(j, int) or isinstance(j, bool) or j < 1 or j >= len(vs):
        return None
    prior, cur = LG._num(vs[j - 1]), LG._num(vs[j])
    if prior is None or prior == 0 or cur is None:
        return None
    hit = D.ge(cur, D._mul(prior, A2_SPIKE_MULT))
    return None if hit is None else not hit


def _hhmm(t) -> Optional[str]:
    return t.strftime("%H:%M") if isinstance(t, (dt.datetime, dt.time)) else None


def _finish(results: dict, values: dict, frame, *, admit=None) -> dict:
    """The ONE text composer (judge and with_t1): `results` = {id: (ok, why)} in rule order. `admit` (2026-11-09) = the
    ADMIT rule's id when the read is a 🚩 "broke — not A+" read that rule admitted (ADMIT_TEXT_OK / ADMIT_TEXT_HELD,
    `original_aplus` False); None → today's words. Every block carries `admit`."""
    ids = list(results)
    passed = [i for i in ids if results[i][0] is True]
    failed = [{"id": i, "why": results[i][1]} for i in ids if results[i][0] is not True]
    ok = not failed
    fails = "; ".join(f"{f['id']} — {f['why']}" for f in failed)
    admitted = isinstance(admit, str) and bool(admit)
    if admitted:
        tpl = ADMIT_TEXT_OK if ok else ADMIT_TEXT_HELD
        text = tpl.format(admit=admit, reason=D.NOT_APLUS_REASON, ids=" · ".join(ids), fails=fails,
                          unmeasured=VERDICT_UNMEASURED)
    elif ok:
        text = f"audited A+ — {' · '.join(ids)} pass · {VERDICT_UNMEASURED}"
    else:
        text = "🚩 A+ on the original, held here by: " + fails + f" · {VERDICT_UNMEASURED}"
    return {"aplus": ok, "original_aplus": not admitted, "rules": ids, "passed": passed, "failed": failed,
            "frame": frame, "values": {i: values[i] for i in ids}, "text": text, "version": AUDIT_VERSION,
            "admit": admit if admitted else None}


def judge(read: dict, F, frozen=None, ctx=None, *, admit=None) -> Optional[dict]:
    """The audit block of ONE A+ read on its own frame `F` (the bars.Frame the read was made on). None unless the read
    is in state "aplus" (the contract: the audit filters A+ reads only). The rules are judge_rules() (every ON filter
    but T1 — appended later by with_t1). `ctx` = {"session": date | iso | None, "best_change_pct": float | None,
    "best_symbol": str | None} — the pass's own session and scanner strip; absent → H1 and T4 read None (fail-closed).
    Every ON rule that reads None FAILS with NONE_WHY[id]; every value is JSON-native.
    `admit` (2026-11-09) = None, or the id of an ON admit rule (K3S) whose re-read made this A+ — anything else raises
    ValueError; it rides into the block (`admit`, the ADMIT words, `original_aplus` False)."""
    if admit is not None and (not isinstance(admit, str) or admit not in tuple(r.id for r in admit_rules())):
        raise ValueError("audited_rules: admit must name an ON admit rule")
    if not isinstance(read, dict) or read.get("state") != "aplus":
        return None
    ctx = ctx if isinstance(ctx, dict) else {}
    t = read.get("entry_bar_t")
    tl = list(getattr(F, "t", None) or [])
    j = tl.index(t) if (F is not None and t is not None and t in tl) else None
    frame = getattr(F, "frame", None) if F is not None else None
    trigger, stop = read.get("trigger"), read.get("stop")
    idx = base_idx(F, read.get("base")) if j is not None else []
    k = G1_K
    results, values = {}, {}

    # G1 — break-bar proof
    mv = D._mean(F.v[i] for i in idx) if idx else None
    vals1 = {"close": _dstr(F.c[j]) if j is not None else None, "trigger": _dstr(trigger),
             "vol": _fnum(F.v[j]) if j is not None else None, "base_mean_vol": _fnum(mv), "k": float(k),
             "base_n": len(idx), "frame": frame}
    if j is None or LG._num(trigger) is None:
        g1, why1 = None, NONE_WHY["G1"]
    else:
        g1 = g1_pass(F, j, trigger, idx, k)
        if g1 is None:
            why1 = "no base bars to prove against"
        else:
            bits = []
            if D.gt(LG._D(F.c[j]), LG._D(trigger)) is False:
                bits.append(f"the break bar closed {_px(F.c[j])} vs trigger {_px(trigger)}")
            if D.ge(F.v[j], D._mul(mv, k)) is False:
                bits.append(f"break-bar volume {_vol(F.v[j])} < {k:g}× the base mean {_vol(mv)}")
            why1 = " and ".join(bits)
    results["G1"], values["G1"] = (g1, why1), vals1

    # G2 — red closes
    run = g2_run(F, idx, read) if j is not None else None
    rc = read.get("red_closes")
    vals2 = {"run": run, "longest": rc if isinstance(rc, int) and not isinstance(rc, bool) else None,
             "max": int(G2_MAX_RED), "mode": G2_RUN, "frame": frame}
    g2 = g2_pass(run)
    if g2 is None:
        why2 = NONE_WHY["G2"]
    else:
        where = "at the end of the base" if G2_RUN == "last" else "in the base (the longest run)"
        why2 = f"{run} red closes in a row {where} (> {G2_MAX_RED})"
    results["G2"], values["G2"] = (g2, why2), vals2

    # G4 — stop-distance cap (🎾: the stop frozen at the first armed read)
    cap_stop, frozen_used, reason = cap_stop_for(read, frozen)
    risk = risk_pct(trigger, cap_stop) if j is not None else None
    g4 = g4_pass(trigger, cap_stop) if (j is not None and risk is not None) else None
    vals4 = {"risk_pct": float(risk) if risk is not None else None, "stop_used": _dstr(cap_stop),
             "frozen": bool(frozen_used), "frozen_reason": FROZEN_REASONS[reason], "cap_pct": float(G4_MAX_RISK_PCT)}
    if g4 is None:
        why4 = NONE_WHY["G4"]
    else:
        why4 = f"stop {_px(cap_stop)} is {float(risk):.1f}% under the trigger (> {G4_MAX_RISK_PCT:g}%)"
        if frozen_used:
            why4 += " · " + FROZEN_REASONS["frozen"]
    results["G4"], values["G4"] = (g4, why4), vals4

    # T2 / A1 / H1 — the break bar's clock (its START on the read's own frame)
    rframe = frame or read.get("frame")
    start = bar_start_et(t, rframe)
    start_s = _hhmm(start)
    t2 = t2_pass(start)
    results["T2"] = (t2, NONE_WHY["T2"] if t2 is None else
                     f"the break bar started {start_s} ET, before {_hhmm(T2_FIRST_HOUR_END_ET)}")
    values["T2"] = {"start_et": start_s, "cut_et": _hhmm(T2_FIRST_HOUR_END_ET), "frame": rframe}
    a1 = a1_pass(start)
    results["A1"] = (a1, NONE_WHY["A1"] if a1 is None else
                     f"the break bar started {start_s} ET, after {_hhmm(A1_LAST_ENTRY_ET)}")
    values["A1"] = {"start_et": start_s, "cut_et": _hhmm(A1_LAST_ENTRY_ET), "frame": rframe}
    session = ctx.get("session")
    close_t = _rth_close(session)
    h1 = h1_pass(t, session, rframe)
    open_s, close_s = _hhmm(H1_OPEN_ET), _hhmm(close_t if close_t is not None else H1_CLOSE_ET)
    results["H1"] = (h1, NONE_WHY["H1"] if h1 is None else
                     f"the break bar started {start_s} ET, outside {open_s}–{close_s} ET")
    values["H1"] = {"start_et": start_s, "open_et": open_s, "close_et": close_s, "frame": rframe}

    # T4 — the day's top scanner runner (the pass's own strip)
    best, best_sym = LG._num(ctx.get("best_change_pct")), ctx.get("best_symbol")
    best_sym = str(best_sym) if isinstance(best_sym, str) and best_sym else None
    t4 = t4_pass(best)
    if t4 is None:
        why_t4 = NONE_WHY["T4"]
    else:
        why_t4 = (f"the day's top runner is {best:+.1f}%" + (f" ({best_sym})" if best_sym else "")
                  + f" — at or under {T4_QUIET_TOP_PCT:g}%")
    results["T4"] = (t4, why_t4)
    values["T4"] = {"best_change_pct": best, "best_symbol": best_sym, "max_pct": float(T4_QUIET_TOP_PCT),
                    "fired": t4 is not True}

    # A2 — volume-spike skip (the break bar vs the bar before it, on the read's own frame)
    a2 = a2_pass(F, j) if j is not None else None
    vol = _fnum(F.v[j]) if j is not None else None
    prior = _fnum(F.v[j - 1]) if (j is not None and j >= 1) else None
    results["A2"] = (a2, NONE_WHY["A2"] if a2 is None else
                     f"break-bar volume {_vol(vol)} is ≥ {A2_SPIKE_MULT:g}× the prior bar {_vol(prior)}")
    values["A2"] = {"vol": vol, "prior_vol": prior, "mult": float(A2_SPIKE_MULT),
                    "ratio": (vol / prior) if (vol is not None and prior) else None, "frame": frame}

    ids = [r.id for r in judge_rules()]
    return _finish({i: results[i] for i in ids}, values, frame, admit=admit)


# ── T1: the daily entry cap (cross-read state — judged LAST by audited_pass over the pass's claimable survivors) ────
def ring_order(items) -> list:
    """`items` = [(sym, setup, read, audit)] → the same items in 🚩's ring order: the ORDER alerts._candidates gives
    the pass (entry bar, SETUPS index, symbol, setup) — ONE engine, the order the pushes leave the pass [C3]. The
    reads are handed to alerts._candidates itself (as A+), never re-sorted by a second key."""
    items = list(items or [])
    reads, by_key = {}, {}
    for it in items:
        sym, setup, read = it[0], it[1], it[2]
        reads.setdefault(sym, {})[setup] = dict(read or {}, state="aplus")
        by_key.setdefault((str(sym).upper(), setup), []).append(it)
    out = []
    for c in AL._candidates(reads):
        bucket = by_key.get((c[2], c[3])) or []
        if bucket:
            out.append(bucket.pop(0))
    return out


def _bar_of(it) -> str:
    return str(((it[2] if len(it) > 2 else None) or {}).get("entry_bar_t") or "")


def t1_slots(order, claimed, cap=None, claims_fault=False) -> dict:
    """{(SYM, setup): (ok, why, values)} over `order` (ring_order's output). A (SYM, setup) in `claimed` (today's 🧪
    claims, read before the pass) keeps its slot without taking a new one; the rest take a slot while
    len(claimed) + taken < cap, in order; the others are held "cap reached". `claims_fault` (the claims could not be
    read) → every item None + NONE_WHY["T1"] (fail-closed). values.tie is True when a held item shares its entry bar
    with an item that took a slot on this pass (and on that item, when it took the last slot) — the tie 🚩's ring
    order broke [C3]."""
    cap = T1_DAILY_CAP if cap is None else cap
    order = list(order or [])
    claimed_u = {(str(s).upper(), st) for s, st in (claimed or set())}
    used_before = len(claimed_u)
    out, taken, held = {}, [], []
    for pos, it in enumerate(order, start=1):
        key = (str(it[0]).upper(), it[1])
        if claims_fault:
            out[key] = [None, NONE_WHY["T1"], {"slot": None, "order": pos}]
        elif key in claimed_u:
            out[key] = [True, "", {"slot": T1_KEPT, "order": pos}]
        elif used_before + len(taken) < cap:
            taken.append(it)
            out[key] = [True, "", {"slot": used_before + len(taken), "order": pos}]
        else:
            held.append(it)
            out[key] = [False, "", {"slot": None, "order": pos}]
    holders = [{"symbol": s, "setup": st, "entry_bar_t": None} for s, st in sorted(claimed_u)] + [
        {"symbol": str(it[0]).upper(), "setup": it[1], "entry_bar_t": _bar_of(it) or None} for it in taken]
    taken_bars = {_bar_of(it) for it in taken}
    held_bars = {_bar_of(it) for it in held}
    last = taken[-1] if (taken and used_before + len(taken) >= cap) else None
    names = ", ".join(f"{h['symbol']} {h['entry_bar_t'][11:16]}" if h["entry_bar_t"] else f"{h['symbol']} earlier today"
                      for h in holders)
    res = {}
    for it in order:
        key = (str(it[0]).upper(), it[1])
        ok, why, vals = out[key]
        bar = _bar_of(it)
        if ok is False:
            tie = bool(bar) and bar in taken_bars
            why = f"daily cap of {cap} reached — the slots went to {names}" + (T1_TIE_TEXT if tie else "")
        elif ok is True and last is not None and it is last:
            tie = bool(bar) and bar in held_bars
        else:
            tie = False
        vals = dict(vals, cap=int(cap), used_before=None if claims_fault else used_before, tie=tie,
                    holders=[] if claims_fault else [dict(h) for h in holders])
        res[key] = (ok, why, vals)
    return res


def with_t1(audit: Optional[dict], ok, why, values) -> Optional[dict]:
    """The audit block with T1 appended LAST: rules / passed | failed / values gain "T1", `aplus` and `text` are
    recomputed by the ONE composer (_finish). A None (or junk) audit stays None. A T1 already on the block is
    replaced, never doubled. Fail-closed: ok None fails with NONE_WHY["T1"]."""
    if not isinstance(audit, dict):
        return None
    tid = T1.id
    why_by = {f.get("id"): f.get("why") for f in (audit.get("failed") or []) if isinstance(f, dict)}
    passed = set(audit.get("passed") or [])
    results = {}
    for i in [x for x in (audit.get("rules") or []) if x != tid]:
        results[i] = (True, "") if i in passed else (False, why_by.get(i) or NONE_WHY.get(i, ""))
    results[tid] = (ok, (NONE_WHY[tid] if ok is None else (why or "")))
    vals = {i: v for i, v in (audit.get("values") or {}).items() if i != tid}
    vals[tid] = dict(values or {})
    out = _finish(results, vals, audit.get("frame"), admit=audit.get("admit"))
    out["original_aplus"] = audit.get("original_aplus", True)
    return out
