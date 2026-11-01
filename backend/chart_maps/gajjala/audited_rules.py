"""🧪 Gajjala · Audited — the registry of audit rules + the pure gate math + the served words (BUILD SPEC 2026-11-01 §3.1).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited / So we can keep track of improvements on this tab"

A VERSIONED REGISTRY: each audit-derived rule is one frozen `Rule` with its eod-audits source, the date it joined, its
status (ON on this tab / OFF / lane_only), its verdict and what it changes. The launch set is the four pre-registered
gates of 2026-10-30 (eod-audits/research/2026-10-30_gajjala_gates_prereg.md — frozen before any run): G1 · G2 · G4 ON,
G3 lane_only (a paper-lane ENTRY gate, never a read; nothing in trading/ changes). Every rule is UNMEASURED: the
pre-registered replay read every gate TOO SMALL (report.md "Per gate"; LEDGER.md rows dated 2026-10-30). The rules
FILTER 🚩 Gajjala's A+ read on this tab only — never a new setup, never a push, never the 🚩 tab.

THE GATE MATH is ported VERBATIM from the study script (study branch `study/gajjala-gates-2026-10-30`, worktree
wt-gggates, backend/scripts/gajjala_gates_study_2026_10_30.py `g1_pass`, `g2_pass`, `last_red_run`, `risk_pct`,
`g4_pass` :198-258 and `_base_idx` :411-414). The bytes READ for this port: sha256
20bb1970b5c5c9a59921a01afcfd570787ddc65c5c25bc5f8c16ff4ba08b2798 (wt-gggates HEAD 0678034f; byte copy
tests/fixtures/gajjala/gates_study_2026_10_30.py.txt). report.md:5 cites the RUN-2 bytes e308ab74…dfff08 — report.md:47:
"The file was then edited only to print a one-week CI as 'no interval' and to re-render these files from `results.json`
(`--render-only`, no data read)." The run-2 bytes are not in git; the port cites the bytes it read (20bb1970…) beside them.

Fail-closed: a rule that reads None FAILS (the A+ is held) and its served why is NONE_WHY[id] — no served string ever
prints "None". `judge` serves JSON-native values only (float / str / int / bool / None — never a Decimal: tab._plain has
no Decimal branch). Every number below carries its source line; GG's own number (G2) is read BY NAME from constants.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping, Optional

from . import constants as GC
from . import detectors as D
from . import ledger as LG

# ── the frozen sources (read, never retyped) ────────────────────────────────────────────────────────────────────────
PREREG_PATH = "eod-audits/research/2026-10-30_gajjala_gates_prereg.md"     # under /Users/ajay/clinet-test/ (outside the repo); byte copy tests/fixtures/gajjala/gates_prereg_2026_10_30.md
PREREG_SHA256 = "4ebc30d20e7f3eb19aa6df5fbe2b620d9c19e0e22144ae6620e66ca7bf8d14b6"   # report.md:5 — the frozen prereg
REPORT_PATH = "eod-audits/research/gajjala_gates_2026_10_30/report.md"       # copy tests/fixtures/gajjala/gates_report_2026_10_30.md
LEDGER_PATH = "eod-audits/research/LEDGER.md"                                # rows dated 2026-10-30: TOO SMALL (= UNMEASURED)
STUDY_PATH = "wt-gggates/backend/scripts/gajjala_gates_study_2026_10_30.py"  # the ported gate math; byte copy tests/fixtures/gajjala/gates_study_2026_10_30.py.txt
STUDY_SHA256 = "20bb1970b5c5c9a59921a01afcfd570787ddc65c5c25bc5f8c16ff4ba08b2798"   # the file AS PORTED (wt-gggates HEAD 0678034f); report.md:5 cites run-2 bytes e308ab74…dfff08 — report.md:47 "edited only to print a one-week CI … --render-only"
AUDIT_VERSION = 1                                                            # TRANSPORT — bump when judge() changes (stored on every audit block)

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
})
FROZEN_REASONS = MappingProxyType({                 # values.G4.frozen_reason — the card says WHY the stop it read
    "frozen": "🎾 stop frozen at the first armed read",
    "no_match": "no armed read with this trigger — the alert's stop",
    "not_squeeze": "not a 🎾 read — the alert's stop",
})
AUDIT_SERVED_KEYS = ("aplus", "original_aplus", "rules", "passed", "failed", "values", "text", "version", "frame")
STATUS_TEXT = MappingProxyType({
    STATUS_ON: "ON on this tab",
    STATUS_OFF: "OFF — listed, not applied",
    STATUS_LANE_ONLY: "lane only — registered, not applied on this tab",
})

_FIRST_HAND = "tests/fixtures/gajjala/first_hand_2026_10_13.md"   # backend-relative
_VR = "chart_maps/gajjala/verified_rules.json"                     # backend-relative


@dataclass(frozen=True)
class Rule:
    """One registry entry. `rule` is a template formatted with `params` at serve time (the FE composes nothing)."""
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
REGISTRY = (G1, G2, G3, G4)


def validate() -> None:
    """Raise ValueError on a junk G2_RUN or a registry entry outside STATUSES / with a verdict other than UNMEASURED
    (run at import; g2_run re-checks G2_RUN at call time)."""
    if G2_RUN not in G2_RUNS:
        raise ValueError(f"audited_rules: G2_RUN must be one of {G2_RUNS}, not {G2_RUN!r}")
    for r in REGISTRY:
        if r.status not in STATUSES:
            raise ValueError(f"audited_rules: {r.id} status {r.status!r} not in {STATUSES}")
        if r.status == STATUS_ON and not r.applies:
            raise ValueError(f"audited_rules: {r.id} is ON but does not apply")


validate()


def on_rules() -> tuple:
    """The rules this tab APPLIES to an A+ read (status ON and applies), registry order."""
    return tuple(r for r in REGISTRY if r.status == STATUS_ON and r.applies)


def by_id(i) -> Optional[Rule]:
    return next((r for r in REGISTRY if r.id == i), None)


def _g(x) -> str:
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
    return ", ".join(f"{k} = {_g(v)}" for k, v in p.items())


def registry_rows() -> list:
    """The served registry: one dict of WORDS per rule (the FE prints them, composes nothing)."""
    out = []
    for r in REGISTRY:
        gg = " · ".join(f"GG: \"{q}\"" for _f, _w, q in r.gg)
        src = f"pre-registered {r.source[0][0]} (sha256 {PREREG_SHA256[:12]}…)"
        out.append({"id": r.id, "name": r.name, "rule": r.rule.format(**r.params), "params_text": _params_text(r),
                    "source_text": src + (" · " + gg if gg else ""), "since": r.date_added, "status": r.status,
                    "status_text": STATUS_TEXT[r.status], "verdict": r.verdict,
                    "verdict_text": f"{r.verdict} — {r.verdict_source}", "changes_text": r.changes,
                    "applies": r.applies, "note": r.note})
    return out


def rules_clause() -> str:
    """The ℹ️ panel's sentence for the audited tab — every number formatted from the constants above (no literal)."""
    on = "; ".join(f"{r.id} {r.name} ({r.rule.format(**r.params)})" for r in on_rules())
    lane = [r for r in REGISTRY if r.status == STATUS_LANE_ONLY]
    lane_txt = " ".join(f"{r.id} {r.name} ({_params_text(r)}) is a paper-lane entry gate — registered, not applied on "
                        f"this tab." for r in lane)
    return (f"🧪 Gajjala · Audited — an overlay on 🚩 Gajjala's A+ reads, recorded in shadow, never sent: {on}. "
            f"{lane_txt} A removed A+ is listed as held, never hidden; the 🚩 tab is never filtered. Every rule is "
            f"{VERDICT_UNMEASURED} (the pre-registered replay read TOO SMALL against the lab's "
            f"{_g(MEASURE_FLOOR_WEEKS)}-week floor).")


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


def judge(read: dict, F, frozen=None) -> Optional[dict]:
    """The audit block of ONE A+ read on its own frame `F` (the bars.Frame the read was made on). None unless the read
    is in state "aplus" (the contract: the audit filters A+ reads only). Every ON rule that reads None FAILS with
    NONE_WHY[id]; every value is JSON-native."""
    if not isinstance(read, dict) or read.get("state") != "aplus":
        return None
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

    ids = [r.id for r in on_rules()]
    passed = [i for i in ids if results[i][0] is True]
    failed = [{"id": i, "why": results[i][1]} for i in ids if results[i][0] is not True]
    ok = not failed
    if ok:
        text = f"audited A+ — {' · '.join(ids)} pass · {VERDICT_UNMEASURED}"
    else:
        text = ("🚩 A+ on the original, held here by: " + "; ".join(f"{f['id']} — {f['why']}" for f in failed)
                + f" · {VERDICT_UNMEASURED}")
    return {"aplus": ok, "original_aplus": True, "rules": ids, "passed": passed, "failed": failed, "frame": frame,
            "values": {i: values[i] for i in ids}, "text": text, "version": AUDIT_VERSION}
