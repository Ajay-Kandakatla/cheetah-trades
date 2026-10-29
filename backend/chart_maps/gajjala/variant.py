"""🚩 Gajjala's pipeline, parametrized — GG5 (today's tab, 5-minute bars) and GG1 (the 1-minute page). BUILD_SPEC27 §3.1.

Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
please." / "do everything and also add the track record for it from today.."

ONE pipeline, ONE engine per concept: the scanner list, the detectors (his five setups, K1–K11), the A+ claim, the 🧠
potentials, the 📈 track and the 🏁 record run unchanged; a frozen `Variant` names what differs — the frames (primary
first, the Fade's slow frame second), the collections a variant WRITES (GG1: `gajjala_1m_*`; it READS GG5's scanner
list, halts, daily, ah-carry, post and the ONE broker list), the claim prefix, the push kinds / senders / mode switch,
the api base, the tape and stale numbers. Every number is read off constants.py BY NAME at CALL time (tests monkeypatch
them); nothing here is a new rule.

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
VARIANTS = (GG5, GG1)

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
def words(v=None) -> Mapping:
    """{} for GG5 (its words stay where they are); WORDS_1M for any other variant."""
    return MappingProxyType({}) if is_gg5(v) else WORDS_1M


def word(key, v=None, **fmt) -> Optional[str]:
    """One served word of the variant, its numbers filled at call time ({p}, {s}, {from}, {tail} + `fmt`); None when
    the variant has no such word (GG5 always). In shadow mode a key WORDS_1M_SHADOW carries serves that sentence."""
    tpl = words(v).get(key)
    if tpl is None:
        return None
    vv = of(v)
    if push_mode(vv) == "shadow" and key in WORDS_1M_SHADOW:   # 2026-10-29: the words follow the mode at call time
        tpl = WORDS_1M_SHADOW[key]
    from .potential import TAIL
    args = {"p": frame_minutes(vv.primary, vv), "s": frame_minutes(vv.slow, vv), "from": GC.GG1M_RECORD_FROM,
            "tail": TAIL}
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
            "api_base": vv.api_base, "record_from": GC.GG1M_RECORD_FROM}
