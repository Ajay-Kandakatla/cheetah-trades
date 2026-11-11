"""🚩 Gajjala's pipeline, parametrized — GG5 (today's tab, 5-minute bars) and GG1 (the 1-minute page). BUILD_SPEC27 §3.1.

Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
please." / "do everything and also add the track record for it from today.."

ONE pipeline, ONE engine per concept: the scanner list, the detectors (his five setups, K1–K11), the A+ claim, the 🧠
potentials, the 📈 track and the 🏁 record run unchanged; a frozen `Variant` names what differs — the frames (primary
first, the Fade's slow frame second), the collections a variant WRITES (GG1: `gajjala_1m_*`; it READS GG5's scanner
list, halts, daily, ah-carry, post and the ONE broker list), the claim prefix, the push kinds / senders / mode switch,
the api base, the tape and stale numbers. Every number is read off constants.py BY NAME at CALL time (tests monkeypatch
them); nothing here is a new rule.

🧪 2026-11-01 — GGA, the audited tab (Ajay: "I would like you to create a new tab for Gajjals when you modifiy with audit
of End of day.. Gajjals-Audited"): a THIRD variant that rides GG5's own pass as an overlay (no frames of its own to
fetch), borrowing GG5's reads and owning its alerts / state / ledger / overlay. Its words are WORDS_GGA (shadow, always
UNMEASURED); its record starts GC.GGA_RECORD_FROM (`record_from_const`).

GG5 = today's tab, every stored and served byte unchanged (tests/test_gajjala_variant_gg5_identity.py + the three
goldens prove it): `words(GG5)` is {} — GG5's words stay where they are. GG1's served words are WORDS_1M, frozen here,
their numbers formatted at call time from the variant and constants (the FE prints them; it types none).

A Cheetah variant — GG trades these setups on 5-minute bars. UNMEASURED: nothing has measured a 1-minute read. Every GG1
alert was recorded in SHADOW, never sent, 2026-10-27 … 2026-10-28; since 2026-10-29 they ring his phone (GAJJALA_1M_PUSH_MODE
"live" — HIS CALL #1 answered, Ajay: "Only give me Gajjalas chart notifications from both tabs, / I am missing out the
ones in noise."). The words follow the MODE at call time: in "shadow" (a flip back is one word) `word()` serves
WORDS_1M_SHADOW's sentence for each key it carries, so a served sentence never says "rings your phone" while nothing
rings.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from . import constants as GC


@dataclass(frozen=True)
class Variant:
    """One reading of GG's pipeline. Every `*_const` names a constants.py attribute (read at call time)."""
    key: str
    tab: str
    label: str
    primary: str                       # the frame the four setups read (and the push / tape clock)
    slow: str                          # the Fade's first frame (the 15→5 analog)
    rules: tuple                       # ((tf, pandas_rule), …) — ordered: the frames build, store and serve in this order
    cadence_const: str
    store_prefix: str                  # the OWN collections' prefix ("gajjala" = the twelve names as they are)
    claim_prefix: str                  # the A+ claim id prefix ("GG" → "GG:{date}|{SYM}|{setup}")
    push_kind_setup: str
    push_kind_potential: str
    push_mode_const: str
    send_setup: str                    # push.hooks function names
    send_potential: str
    api_base: str
    tape_tf_const: str
    tape_bars_const: str
    stale_const: str
    lane: bool                         # the 🚩 Auto-Pilot lane consumes this variant's claims (GG5 only — HIS CALL #9)
    ledger_push_states: tuple          # the 🧠 push states the 🏁 record counts
    # 🧪 2026-11-01 (the audited tab): trailing, defaulted — GG5 / GG1 positional construction is unchanged
    borrows: tuple = ()                # logical OWN names this variant READS from GG5's store instead of its own
    record_from_const: str = "GG1M_RECORD_FROM"   # the constants.py name of the first session its 🏁 record reads

    @property
    def tfs(self) -> tuple:
        return tuple(tf for tf, _r in self.rules)

    @property
    def rules_map(self) -> dict:
        return {tf: r for tf, r in self.rules}


GG5 = Variant("gajjala", "gajjala", "Gajjala's", "5m", "15m", (("5m", "5min"), ("15m", "15min")), "PASS_CADENCE_SEC",
              "gajjala", "GG", "gajjala_setup", "gajjala_potential", "GAJJALA_PUSH_MODE", "notify_gajjala_setup",
              "notify_gajjala_potential", "/chart-maps/gajjala", "LEDGER_TAPE_TF_MIN", "LEDGER_TAPE_BARS_MAX",
              "STALE_AFTER_SEC", True, ("pushed",))
GG1 = Variant("gajjala_1m", "gajjala_1m", GC.GG1M_TAB_LABEL, "1m", "5m", (("1m", "1min"), ("5m", "5min")),
              "GG1M_CADENCE_SEC", "gajjala_1m", "GG1", "gajjala_1m_setup", "gajjala_1m_potential",
              "GAJJALA_1M_PUSH_MODE", "notify_gajjala_1m_setup", "notify_gajjala_1m_potential",
              "/chart-maps/gajjala-1m", "GG1M_TAPE_TF_MIN", "GG1M_TAPE_BARS_MAX", "GG1M_STALE_AFTER_SEC", False,
              ("pushed", "shadow"))
# 🧪 Gajjala · Audited (Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of
# End of day.. Gajjals-Audited. So we can keep track of improvements on this tab"). NOT a second pipeline: an OVERLAY on
# GG5's own pass — it BORROWS GG5's reads / potentials / passes / replay and OWNS its alerts / state / ledger / overlay
# (`gajjala_audited_*`). No sender exists (send_setup = send_potential = "" — alerts._default_send refuses), no 🧠 row on
# its 🏁 (ledger_push_states = ()), never a lane. SHADOW only (GAJJALA_AUDITED_PUSH_MODE). UNMEASURED.
GGA = Variant("gga", "gajjala_audited", GC.GGA_TAB_LABEL, "5m", "15m", (("5m", "5min"), ("15m", "15min")),
              "PASS_CADENCE_SEC", "gajjala_audited", "GGA", "gajjala_audited_setup", "gajjala_audited_potential",
              "GAJJALA_AUDITED_PUSH_MODE", "", "", "/chart-maps/gajjala-audited", "LEDGER_TAPE_TF_MIN",
              "LEDGER_TAPE_BARS_MAX", "STALE_AFTER_SEC", False, (),
              borrows=("gajjala_reads", "gajjala_potentials", "gajjala_passes", "gajjala_replay"),
              record_from_const="GGA_RECORD_FROM")
VARIANTS = (GG5, GG1, GGA)

# GG1's served words — FROZEN (BUILD_SPEC27 §3.1; LIVE words 2026-10-29). {p}/{s} = frame_minutes(primary/slow),
# {from} = GC.GG1M_RECORD_FROM, {tail} = potential.TAIL (read at call time — potential imports this module); the rest are
# word()'s keyword args. Ajay 2026-10-29: "Only give me Gajjalas chart notifications from both tabs," — the shadow period
# (2026-10-27 … 2026-10-28) stays named, so no row of it ever reads as sent.
LIVE_SINCE_1M = "2026-10-29"             # the day his words above flipped GAJJALA_1M_PUSH_MODE to "live"
_HIS_WORDS_1M = "Only give me Gajjalas chart notifications from both tabs"
# 🔁 2026-11-02 (Ajay: one count per stock per day) — typed HERE because variant.py cannot import ledger at module level;
# MUST equal ledger.DUP_RULE_TEXT byte for byte (tests/test_gajjala_ledger_dedupe_2026_11_02.py pins it). No brace, no
# digit: the words are .format()ed.
DUP_RULE_TEXT = ("One count per stock per day — your rule: \"make sure you are not accounting for duplicates of the same "
                 "stock as winner unless it did the same pattern again and met all the criteria on the same day\". A "
                 "name that rang again the same day is listed and chipped, never counted twice, unless the later ring "
                 "set up again: its own fill minute, its own trigger and stop, and a trade of its own, not one held "
                 "while the first was still running. A duplicate stays out of every count, % and chart.")
WORDS_1M: Mapping = MappingProxyType({
    "title": "🚩 Gajjala's — the same rules on {p}-minute candles · Cheetah variant · UNMEASURED",
    "honesty": ("GG trades these setups on {s}-minute bars; this page runs the same bar-count rules on {p}-minute bars "
                "by your call ({from}). Its alerts ring your phone since " + LIVE_SINCE_1M + " by your call (\""
                + _HIS_WORDS_1M + "\"); from {from} to 2026-10-28 they were recorded in shadow, never sent. Nothing "
                "measured."),
    "push": ("📲 Every A+ on this page rings your phone since " + LIVE_SINCE_1M + " by your call (\"" + _HIS_WORDS_1M
             + "\") — once per name, setup and day; the A+ of {from} to 2026-10-28 were recorded in shadow, never "
             "sent. UNMEASURED."),
    # 2026-11-11 (Ajay "Also apply your proposal too." — proposals #1 / #2, POTENTIAL_PUSH_ARMED_ONLY /
    # POTENTIAL_ONE_RING_PER_NAME): the ring rule = potential.ring_rule() with both switches on, frozen here
    "push_potential": ("🧠 Potentials on this page ring your phone since " + LIVE_SINCE_1M + " by your call — the "
                       "first time it is armed (every rule met, only the break missing) — one push per name and "
                       "session, {open}–{close} ET on the {cad}-minute pass, never {rth_open}–{mute_end} (his first "
                       "{n} minutes). From {from} to 2026-10-28 they were recorded in shadow, never sent. {tail}."),
    "held_stale_tape": "no print in the last {p}-minute bar",
    "ledger_title": "🏁 Track record — every {p}-minute Gajjala alert since {from}, graded by GG's trade math · UNMEASURED",
    "ledger_honesty": ("A ledger of this page's alerts: from {from} to 2026-10-28 they were recorded in shadow (never "
                       "sent); since " + LIVE_SINCE_1M + " they ring your phone by your call. Each row's kind says "
                       "which. The 🧠 potentials — shadow and sent — make the headline %; A+ rows keep their own lines, "
                       "as on 🚩 Gajjala's. Graded by GG's own trade math on 1-minute bars — not a backtest, small n "
                       "early. The 2026-10-14 study of the 5-minute setups read NULL (docs/gajjala/study_2026_10_13.md); "
                       "nothing has measured this page. " + DUP_RULE_TEXT),                      # 🔁 2026-11-02
    # a 🧠 row's kind word is read off ITS OWN push state (ledger._variant_words): shadow / pushed; the neutral word only
    # when a row carries neither — the A+ rows read KIND_TEXT by their line (the claim's own state), the neutral A+ word
    # only when that has no entry
    "ledger_kind_potential": "🧠 potential (1-minute)",
    "ledger_kind_potential_shadow": "🧠 shadow — never sent",
    "ledger_kind_potential_pushed": "🧠 live",
    "ledger_kind_aplus": "A+ (1-minute)",
    # the headline counts lead, read off the states of the span's 🧠 rows: none / shadow only / sent only / both
    "ledger_counts_lead": "🧠 potentials",
    "ledger_counts_lead_shadow": "🧠 shadow — recorded, never sent",
    "ledger_counts_lead_pushed": "🧠 live — sent to your phone",
    "ledger_counts_lead_mixed": "🧠 shadow (recorded, never sent) + live (sent)",
    "ledger_empty": "No 1-minute alert recorded on this span yet (the record starts {from}).",    # 🧪 2026-11-08 (entry_zone.py; Ajay "add entry signal on the chart please like a small zone") — [C1] the band's SHORT
    # label (chart <title> + crosshair readout) and the card line's sentence ({why} = entry_zone's reasons, joined)
    "zone_label": "entry zone",
    "zone_note": "{why} · UNMEASURED",
})
# The 2026-10-27 shadow sentences — served INSTEAD of WORDS_1M's for these keys while GAJJALA_1M_PUSH_MODE reads
# "shadow" (fail closed: any value but "live"), so a flip back never leaves "rings your phone" on the page.
WORDS_1M_SHADOW: Mapping = MappingProxyType({
    "honesty": ("GG trades these setups on {s}-minute bars; this page runs the same bar-count rules on {p}-minute bars "
                "by your call ({from}). Every alert here is recorded in shadow, never sent, until you say so. Nothing "
                "measured."),
    "push": "A+ on this page is in SHADOW — every A+ is recorded, never sent, until you say so. UNMEASURED.",
    # MOVED 2026-11-11 (T-PINS #5): the built rule — armed only, one per name per session — in WORDS_1M["push_potential"]'s
    # own words (potential.ring_rule() with both switches on); "one per name" without "push", as the 10-27 shadow wrote it
    "push_potential": ("🧠 Potentials on this page are recorded in shadow — the first time it is armed (every rule met, "
                       "only the break missing) — one per name and session, {open}–{close} ET on the {cad}-minute pass, "
                       "never {rth_open}–{mute_end} (his first {n} minutes). Never sent until you say so. {tail}."),
    # 2026-10-29 (verifier LOW): the 🏁 honesty line follows the mode too — a flip back never leaves "ring your phone"
    "ledger_honesty": ("A ledger of this page's alerts as RECORDED — none reached your phone. The 🧠 potentials "
                       "recorded in shadow make the headline %; A+ rows keep their own lines, as on 🚩 Gajjala's. "
                       "Graded by GG's own trade math on 1-minute bars — not a backtest, small n early. The 2026-10-14 "
                       "study of the 5-minute setups read NULL (docs/gajjala/study_2026_10_13.md); nothing has "
                       "measured this page. " + DUP_RULE_TEXT),                                  # 🔁 2026-11-02
})


# 🧪 The audited tab's served words — FROZEN (BUILD SPEC 2026-11-01 §3.2). Every key of WORDS_1M (so the 🏁 / 🧠 /
# held callers read the same keys) plus the audited keys. {p} = frame_minutes(primary), {from} = GC.GGA_RECORD_FROM,
# {tail} = potential.TAIL; the rest are word()'s keyword args (the callers format every number from the constants).
# Every sentence says UNMEASURED or shadow where it applies; "reversal", never the b-word.
WORDS_GGA: Mapping = MappingProxyType({
    "title": "🧪 Gajjala · Audited — 🚩 Gajjala's A+ reads, filtered by the audit overlay · UNMEASURED",
    "honesty": ("The same scanner, the same bars, the same detectors as 🚩 Gajjala's — every number here is read off "
                "that tab's {p}-minute pass; this tab only decides which of its A+ reads survive the audit rules "
                "below. A removed A+ is listed here as held, never hidden. Every alert here is recorded in shadow, "
                "never sent, until you say so. Every rule is UNMEASURED: the 2026-10-30 replay read TOO SMALL. "
                "Nothing here trades or enters a lane."),
    "push": "A+ on this tab is in SHADOW — every audited A+ is recorded, never sent, until you say so. UNMEASURED.",
    "push_potential": ("🧠 Potentials shown here are 🚩 Gajjala's own, for context — this tab records no potential "
                       "and sends nothing. {tail}."),
    "held_stale_tape": "no print in the last {p}-minute bar",
    # 🧪 2026-11-05 (SPEC gg-track-parity §3.2; Ajay: "its hard to tell which ones won in Gajjlas Audit page") — the 🏁
    # lists 🚩's own A+ rows on the sessions this tab records, each with the audit's call in a 🧪 Audit column.
    "ledger_title": ("🏁 Track record — every 🚩 A+ since {from}, each with the audit's call, graded by GG's trade math "
                     "· UNMEASURED"),
    "ledger_honesty": ("The rows are 🚩 Gajjala's own A+ on the sessions this tab records — sent to your phone by that "
                       "tab and graded by GG's own trade math, the same ✅ / ❌ as 🚩's 🏁. The 🧪 Audit column says "
                       "what this tab's rules did with each one: passed every rule, or held by the rules named — the "
                       "reason per rule is in the held list below; what the original then did stays in its cells. No "
                       "🧠 row here: the audit is a filter on the A+ read only. Today's rows are graded tonight, never "
                       "read live here. Nothing has measured these rules. " + DUP_RULE_TEXT),
                                                                                                # 🔁 2026-11-02
    "ledger_kind_potential": "🧠 — not recorded on this tab",
    "ledger_kind_potential_shadow": "🧠 — not recorded on this tab",
    "ledger_kind_potential_pushed": "🧠 — not recorded on this tab",
    "ledger_kind_aplus": "A+ audited (shadow — never sent)",
    "ledger_counts_lead": "🧠 — none on this tab (A+ only)",
    "ledger_counts_lead_shadow": "🧠 — none on this tab (A+ only)",
    "ledger_counts_lead_pushed": "🧠 — none on this tab (A+ only)",
    "ledger_counts_lead_mixed": "🧠 — none on this tab (A+ only)",
    "ledger_empty": "No 🚩 A+ on this span (the record starts {from}).",
    # 🧪 2026-11-05 — the 🏁 row's 🧪 Audit cell (ids only — the why sentences stay in the compare's held list, HIS
    # CALL #31) and the exit-grade sub-line of a passed row (numbers are kwargs: k = AUD.T3_R_MULTS, ema = AUD.T5_EMA)
    "ledger_audit_head": "🧪 Audit",
    "row_audit_passed": "🧪 passed every rule",
    "row_audit_passed_none_on": "no rule was on when it was judged",
    "row_audit_held": "🧪 held by {ids}",
    "row_audit_not_judged": "🧪 not judged",
    "row_audit_not_judged_sub": "no audit record on this bar",
    "row_audit_not_read": "🧪 audit not read this time — the next re-read tries again",
    "row_exit_t3": "T3 +{k:g}R",
    "row_exit_t5": "T5 {ema} EMA trail",
    "row_exit_pending": "not graded yet",
    "row_exit_no_plan": "no plan",
    "row_exit_no_risk": "no risk",
    "row_exit_split": "split",
    "strip_title": "🧪 What is different here",
    "lane_only": ("G3 (ring age ≤ {m} min at the tick, MISSED_R {mr}) is a paper-lane ENTRY gate, not a read — "
                  "registered here, not applied on this tab; the lane itself still trades 🚩 Gajjala's A+ only. "
                  "UNMEASURED."),
    "unmeasured": ("Every rule here is UNMEASURED — the 2026-10-30 replay read TOO SMALL (out-of-sample 4–5 trades in "
                   "1 entry week, against the lab's {floor}-week floor). This tab records forward so the next read "
                   "has n."),
    "floor_reached": ("The record holds {n} entry weeks (the lab's floor is {floor}) — still UNMEASURED until the "
                      "lab's out-of-sample + placebo read; nothing flips by count."),
    "process": ("An audit-derived modification becomes a registry entry with its eod-audits source, OFF until your "
                "call, then ON on this tab only — the 🚩 tab is never the target."),
    "held_title": "🚩 A+ on the original, held here by the audit · {n} · UNMEASURED",
    "held_empty": "No A+ held by the audit right now.",
    "compare_title": "🧪 Audited vs 🚩 original — the same sessions, the same trade math · UNMEASURED",
    "compare_honesty": ("Gross, as the 🏁 ledger grades (+{r:g}R target, the stop a touch); mean R over decided rows "
                        "only, W = +{r:g}R, L = −1R. A held A+ shows what it did on the original — the rule's effect, "
                        "day by day. UNMEASURED until the record holds {floor} entry weeks; {n} so far. "
                        + DUP_RULE_TEXT),                                                       # 🔁 2026-11-02
    "compare_recon": ("{original_only} A+ on the original with no audited or held row (the overlay did not run on "
                      "that pass) · {audited_only} audited with no original row (the original's send failed — the "
                      "same read, kept here) · UNMEASURED"),
    "by_rule_note": "a held A+ counts under every rule it failed — these rows can sum past the held total",
    "pass_line": ("🧪 audit overlay ran on the {hhmm} ET pass · {n_read} reads · {n_orig} A+ on the original · "
                  "{n_aud} pass · {n_held} held"),
    "pass_stale": ("⚠ the audit overlay did not run on the latest 🚩 pass ({hhmm} ET) — the cards carry the original "
                   "reads; the audit waits for the next pass"),
    "unaudited_line": "{n} A+ on the original carry no audit on this pass — shown as the original reads them",
    # 🧪 2026-11-01 — the 🏁 per-rule table (SPEC gg-audited-mods §3.4; Ajay "But keep a track record too to see the
    # winners and loster"). Sentences only — every number is a caller kwarg (audited_tab._per_rule counts them).
    "per_rule_title": ("🧪 Rule by rule — what each change would have done on the same A+ · counts, not verdicts · "
                       "UNMEASURED"),
    "per_rule_with": "with the rule",
    "per_rule_held": "held by the rule — what the original did",
    "per_rule_cap_held": "held — cap reached — what the original did",
    "per_rule_gg_math": "GG's math on the same rows",
    "per_rule_delta_filter": "removed {w} and {l} · {u} never filled",
    "per_rule_delta_exit": "{rule}: {ww} W / {wl} L · GG's math: {gw} W / {gl} L on the same {n}",
    "per_rule_not_graded": "not graded yet — exit grades land the night after the session",
    "per_rule_not_judged": "{n} recorded before this rule joined — not judged",
    "per_rule_no_rows": "no A+ judged on this rule yet",
    "per_rule_t4_fired": "fired on {fired} rung bars · alone on {alone}",
    "per_rule_t1_tie": "{n} held on a tied bar — 🚩's ring order broke the tie",    # 🧪 2026-11-08 (entry_zone.py; Ajay "add entry signal on the chart please like a small zone") — [C1] the band's SHORT
    # label (chart <title> + crosshair readout) and the card line's sentence ({why} = entry_zone's reasons, joined)
    "zone_label": "entry zone",
    "zone_note": "{why} · UNMEASURED",
    # 🧪 2026-11-09 K3S (SPEC gg-k3s §3.4; Ajay "yes change the audit as per you like that is yours") — the ADMIT words:
    # a 🎾 break 🚩 reads "broke — not A+" on K3 alone is a 🧪 A+ here. Sentences only — {reason} =
    # detectors.NOT_APLUS_REASON, {rule} = the admit rule's id, {vol} = the K11 refusals, {gate} = audited_tab.K11_RULE (the rule's name off
    # detectors.K11_KEY; no digit typed here, placeholder names included), every count a caller kwarg; {mr} = audited_tab._mean_text.
    "k3s_pass_line": ("{n} 🧪 A+ by {rule} today — 🚩 read them '{reason}' · {rang} rang in shadow · {held} held · "
                      "{vol} refused by {gate} · {cand} candidates · {pa} 🎾 breaks partial on another rule"),
    "admitted_title": "🧪 only — A+ this tab admitted that 🚩 read '{reason}' · UNMEASURED",
    "admitted_line": ("{n} 🧪 only by {rule}: {rang} rang in shadow · {held} held by another rule · {w} W / {l} L of "
                      "{filled} filled · {u} no entry · {pending} not graded yet · {mr}"),
    "admitted_empty": "No 🧪-only A+ yet — {rule} has admitted nothing on these sessions.",
    "admitted_held_by": "held by: {parts}",
    "admitted_same_day": ("🚩 rang its own 🎾 A+ later the same day — not judged here (one claim per name per "
                          "day)"),
    "per_rule_admit_with": "🧪 only — admitted by the rule",
    "per_rule_admit_other": "🚩's own 🎾 A+ on the same sessions",
    "per_rule_delta_admit": ("{n} 🧪 only: {w} W / {l} L of {filled} filled · {u} never filled · {mr} · 🚩 🎾 A+: "
                             "{gw} W / {gl} L on {gn}"),
})


# ── lookups ──────────────────────────────────────────────────────────────────────────────────────────────────────
def by_key(k) -> Optional[Variant]:
    return next((v for v in VARIANTS if v.key == k), None)


def by_tab(t) -> Optional[Variant]:
    return next((v for v in VARIANTS if v.tab == t), None)


def for_api_base(path) -> Optional[Variant]:
    """The variant whose api base IS `path` or prefixes it at a "/" ("/chart-maps/gajjala-1m/scan" → GG1); the longest
    base wins (GG5's base prefixes GG1's string, never at a "/"). Anything else → None."""
    if not isinstance(path, str):
        return None
    p = path.split("?", 1)[0].rstrip("/")
    for v in sorted(VARIANTS, key=lambda x: len(x.api_base), reverse=True):
        if p == v.api_base or p.startswith(v.api_base + "/"):
            return v
    return None


def of(obj=None) -> Variant:
    """A Variant → it; an object whose `.variant` is a Variant (a store) → that; anything else → GG5 (fail to GG5)."""
    if isinstance(obj, Variant):
        return obj
    v = getattr(obj, "variant", None) if obj is not None else None
    return v if isinstance(v, Variant) else GG5


def is_gg5(v=None) -> bool:
    return of(v) is GG5


def is_audited(v=None) -> bool:
    """🧪 2026-11-01 — the audited tab's variant (GGA). A string is never it (`of` fails to GG5)."""
    return of(v) is GGA


# ── numbers, read AT CALL TIME ───────────────────────────────────────────────────────────────────────────────────
def _const(name: str) -> int:
    return int(getattr(GC, name))


def cadence_sec(v=None) -> int:
    return _const(of(v).cadence_const)


def stale_after_sec(v=None) -> int:
    return _const(of(v).stale_const)


def tape_tf_min(v=None) -> int:
    return _const(of(v).tape_tf_const)


def tape_bars_max(v=None) -> int:
    return _const(of(v).tape_bars_const)


def push_mode(v=None) -> str:
    """"live" only when the variant's constant says exactly that; anything else (None, "LIVE", junk) → "shadow"."""
    return "live" if getattr(GC, of(v).push_mode_const, None) == "live" else "shadow"


def frame_minutes(tf, v=None) -> int:
    """`int(tf[:-1])` for a frame of the variant ("1m" → 1, "15m" → 15); any other value → the primary's minutes."""
    vv = of(v)
    return int((tf if tf in vv.tfs else vv.primary)[:-1])


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
_WORDS = {GG1.key: WORDS_1M, GGA.key: WORDS_GGA}


def words(v=None) -> Mapping:
    """{} for GG5 (its words stay where they are); WORDS_1M for the 1-minute page (the SAME object); WORDS_GGA for the
    🧪 audited tab (2026-11-01)."""
    return _WORDS.get(of(v).key, MappingProxyType({}))


def word(key, v=None, **fmt) -> Optional[str]:
    """One served word of the variant, its numbers filled at call time ({p}, {s}, {from}, {tail} + `fmt`); None when
    the variant has no such word (GG5 always). In shadow mode a key WORDS_1M_SHADOW carries serves that sentence."""
    tpl = words(v).get(key)
    if tpl is None:
        return None
    vv = of(v)
    if vv is GG1 and push_mode(vv) == "shadow" and key in WORDS_1M_SHADOW:   # 2026-10-29: the words follow the mode
        tpl = WORDS_1M_SHADOW[key]                                         # (GG1 only — GGA's words are shadow already)
    from .potential import TAIL
    args = {"p": frame_minutes(vv.primary, vv), "s": frame_minutes(vv.slow, vv),
            "from": getattr(GC, vv.record_from_const), "tail": TAIL}
    args.update(fmt)
    return tpl.format(**args)


def served_block(v=None) -> Optional[dict]:
    """None for GG5 (its payload gains no key); else the page's served identity — the FE prints title / honesty and
    builds its frame toggle from `tfs`."""
    vv = of(v)
    if vv is GG5:
        return None
    return {"key": vv.key, "tab": vv.tab, "label": vv.label, "title": word("title", vv),
            "honesty": word("honesty", vv), "tfs": list(vv.tfs), "primary": vv.primary, "slow": vv.slow,
            "api_base": vv.api_base, "record_from": getattr(GC, vv.record_from_const)}
