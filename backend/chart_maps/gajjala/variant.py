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
WORDS_1M: Mapping = MappingProxyType({
    "title": "🚩 Gajjala's — the same rules on {p}-minute candles · Cheetah variant · UNMEASURED",
    "honesty": ("GG trades these setups on {s}-minute bars; this page runs the same bar-count rules on {p}-minute bars "
                "by your call ({from}). Its alerts ring your phone since " + LIVE_SINCE_1M + " by your call (\""
                + _HIS_WORDS_1M + "\"); from {from} to 2026-10-28 they were recorded in shadow, never sent. Nothing "
                "measured."),
    "push": ("📲 Every A+ on this page rings your phone since " + LIVE_SINCE_1M + " by your call (\"" + _HIS_WORDS_1M
             + "\") — once per name, setup and day; the A+ of {from} to 2026-10-28 were recorded in shadow, never "
             "sent. UNMEASURED."),
    "push_potential": ("🧠 Potentials on this page ring your phone since " + LIVE_SINCE_1M + " by your call — one push "
                       "per name, setup and session the first time it is a potential, {open}–{close} ET on the "
                       "{cad}-minute pass, never {rth_open}–{mute_end} (his first {n} minutes). From {from} to "
                       "2026-10-28 they were recorded in shadow, never sent. {tail}."),
    "held_stale_tape": "no print in the last {p}-minute bar",
    "ledger_title": "🏁 Track record — every {p}-minute Gajjala alert since {from}, graded by GG's trade math · UNMEASURED",
    "ledger_honesty": ("A ledger of this page's alerts: from {from} to 2026-10-28 they were recorded in shadow (never "
                       "sent); since " + LIVE_SINCE_1M + " they ring your phone by your call. Each row's kind says "
                       "which. The 🧠 potentials — shadow and sent — make the headline %; A+ rows keep their own lines, "
                       "as on 🚩 Gajjala's. Graded by GG's own trade math on 1-minute bars — not a backtest, small n "
                       "early. The 2026-10-14 study of the 5-minute setups read NULL (docs/gajjala/study_2026_10_13.md); "
                       "nothing has measured this page."),
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
    "ledger_empty": "No 1-minute alert recorded on this span yet (the record starts {from}).",
})
# The 2026-10-27 shadow sentences — served INSTEAD of WORDS_1M's for these keys while GAJJALA_1M_PUSH_MODE reads
# "shadow" (fail closed: any value but "live"), so a flip back never leaves "rings your phone" on the page.
WORDS_1M_SHADOW: Mapping = MappingProxyType({
    "honesty": ("GG trades these setups on {s}-minute bars; this page runs the same bar-count rules on {p}-minute bars "
                "by your call ({from}). Every alert here is recorded in shadow, never sent, until you say so. Nothing "
                "measured."),
    "push": "A+ on this page is in SHADOW — every A+ is recorded, never sent, until you say so. UNMEASURED.",
    "push_potential": ("🧠 Potentials on this page are recorded in shadow — one per name, setup and session the first "
                       "time it is a potential, {open}–{close} ET on the {cad}-minute pass, never {rth_open}–{mute_end} "
                       "(his first {n} minutes). Never sent until you say so. {tail}."),
    # 2026-10-29 (verifier LOW): the 🏁 honesty line follows the mode too — a flip back never leaves "ring your phone"
    "ledger_honesty": ("A ledger of this page's alerts as RECORDED — none reached your phone. The 🧠 potentials "
                       "recorded in shadow make the headline %; A+ rows keep their own lines, as on 🚩 Gajjala's. "
                       "Graded by GG's own trade math on 1-minute bars — not a backtest, small n early. The 2026-10-14 "
                       "study of the 5-minute setups read NULL (docs/gajjala/study_2026_10_13.md); nothing has "
                       "measured this page."),
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
    "ledger_title": ("🏁 Track record — every audited A+ since {from}, recorded in shadow, graded by GG's trade math "
                     "· UNMEASURED"),
    "ledger_honesty": ("A ledger of this tab's audited A+ as RECORDED — none reached your phone. No 🧠 row here: the "
                       "audit is a filter on the A+ read only. Graded by GG's own trade math — the same math as 🚩 "
                       "Gajjala's 🏁 — not a backtest, small n. Nothing has measured these rules."),
    "ledger_kind_potential": "🧠 — not recorded on this tab",
    "ledger_kind_potential_shadow": "🧠 — not recorded on this tab",
    "ledger_kind_potential_pushed": "🧠 — not recorded on this tab",
    "ledger_kind_aplus": "A+ audited (shadow — never sent)",
    "ledger_counts_lead": "🧠 — none on this tab (A+ only)",
    "ledger_counts_lead_shadow": "🧠 — none on this tab (A+ only)",
    "ledger_counts_lead_pushed": "🧠 — none on this tab (A+ only)",
    "ledger_counts_lead_mixed": "🧠 — none on this tab (A+ only)",
    "ledger_empty": "No audited A+ recorded on this span yet (the record starts {from}).",
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
                        "day by day. UNMEASURED until the record holds {floor} entry weeks; {n} so far."),
    "compare_recon": ("{original_only} A+ on the original with no audited or held row (the overlay did not run on "
                      "that pass) · {audited_only} audited with no original row (the original's send failed — the "
                      "same read, kept here) · UNMEASURED"),
    "by_rule_note": "a held A+ counts under every rule it failed — these rows can sum past the held total",
    "pass_line": ("🧪 audit overlay ran on the {hhmm} ET pass · {n_read} reads · {n_orig} A+ on the original · "
                  "{n_aud} pass · {n_held} held"),
    "pass_stale": ("⚠ the audit overlay did not run on the latest 🚩 pass ({hhmm} ET) — the cards carry the original "
                   "reads; the audit waits for the next pass"),
    "unaudited_line": "{n} A+ on the original carry no audit on this pass — shown as the original reads them",
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
