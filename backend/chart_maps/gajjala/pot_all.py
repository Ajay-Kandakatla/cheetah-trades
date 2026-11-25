"""🧠 from every tab — one list under the 🧠 Potential cards of every name a Gajjala sub shows FORMING (2026-11-24).

Ajay 2026-11-24 ~22:00 ET, verbatim, in order: "Also I see some stocks stay intraday and some stay in Reversal Squeeze.."
· "I need all the potentials moving to the potentials tab real time.." · "I noticed its not happening today" · "I need a
common place to see all the potnetials from all tabs" · "I mean all Gajjala's tabs". Earlier that day: "On the potential
tab the Intraday VCP like BENF and LVWR are supposed to show up but they are not.. They are only in Intraday why?" — the
offer shipped here: keep the broken-out names with "✅ broke HH:MM" (SPEC potall REV 2 §2–§3.1, WP be-potall).

WHAT. `block()` = ONE served block `all_potentials` on the 🧠 sub (GG5 only, tab.build): one row per (symbol, setup) of
  1. every card the five setup subs (🚩 💋 ➖ 🌀 🎾) show in a LIST_STATES state (forming) that the served 🧠 cards do
     not already show (`covered`) — tier "potential" when potential.potential_kind calls it one (a card fault / the
     `lim` cut / a tracker fault left it off the cards; normally empty), else tier "forming";
  2. every 🌱 Diverging row (build's ONE diverging_tab.evaluate answer), tier "forming";
  3. KEEP_BROKE: every (symbol, setup) whose 🧭 stages (stages.steps — the ONE "when did it reach A+" engine: the 🧠
     tracker's `aplus` step, or a live A+ alert that RANG) show a 🎯 A+ this session, kept with "✅ broke HH:MM". A
     current `triggered` / `stopped` read with no such step is NEVER broke (BAK 2026-11-24: stopped, no A+ ever).
Each row in its sub's own served words (tab.state_label / variant_label / grade_label, potential.state_word,
diverging_tab.state_label), linked to its card ONLY when that card exists. "listed · no 🧠 alert" marks a row the 🧠 push
never rings for (its read is not a potential).

PURE. No store, no fetch, no clock, no write, no push: build hands every read in (reads_by, carded, trackers, entries,
dvg, hsi — its own reads, none new). Every number in a served sentence is a count. Nothing here moves a rule, a gate, a
threshold, the 🧠 cards, the chip count, the tracker or any push. Display order only — UNMEASURED.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import diverging_tab as DGT
from chart_maps.gajjala import high_si as HS                 # SQUEEZE_SETUP only (the 🩳 tag on a 🎾 row)
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import stages as SG
from chart_maps.gajjala import tab as GT                     # tab imports this module lazily inside build

log = logging.getLogger("chart_maps.gajjala.pot_all")

# ── module words / switches: the ONLY place they are typed (the FE types none) ───────────────────────────────────
LIST_STATES = (GC.POTENTIAL_STATE,)          # HIS CALL #1 — adding "partial" lists the rule-failed cards (K1: not a potential)
KEEP_BROKE = True                            # HIS CALL #2 — my 2026-11-24 offer, shipped ON
TIERS = ("potential", "forming", "broke")    # group order (HIS CALL #5)
BROKE_TEXT = "✅ broke {at}"
BROKE_TEXT_NOCLOCK = "✅ broke today"
NO_ALERT_TEXT = "listed · no 🧠 alert"
TRACK_FAULT_TEXT = "the 🧠 tracker could not be read — ✅ broke may be missing"
AS_OF_TEXT = "as of the {as_of} pass · {label}"
TITLE = "🧠 from every tab — {f} other forming · {b} ✅ broke today · {p} 🧠 potential on the cards above"
ORDER_TEXT = ("other forming names first (trigger armed, then highest volume) · then ✅ broke, newest first · your 🚫 "
              "names last in each group")
FAULT_SEP = " · "


def _meta(key: str) -> tuple:
    return GT.SUB_META[key]


def rule_text() -> str:
    """The ⓘ rule sentence, built at CALL time from the served sub emojis / labels (never typed twice)."""
    setups = " ".join(_meta(s)[0] for s in GC.SETUPS)
    dvg_e, dvg_l = _meta(GC.DIVERGING_SUB)
    stages_e = SG.TITLE.split(" ", 1)[0]
    pot_e = _meta(GC.POTENTIAL_SUB)[0]
    broke = BROKE_TEXT.split(" {", 1)[0]
    return (f"One row per name and setup a Gajjala sub shows forming right now that the {pot_e} cards above do not — "
            f"the {setups} cards in the forming state and {dvg_e} {dvg_l} — in that sub's own words, linked to its card "
            f"when the card exists. A setup whose {stages_e} stages show a {SG.STAGE_WORDS['aplus']} this session stays "
            f"with {broke} and that A+ clock (the pass that first saw it, or the A+ alert that rang). “{NO_ALERT_TEXT}” "
            f"= the {pot_e} push never rings for that state. Partial cards (a rule failed), {_meta(GC.DIVERGENCE_SUB)[0]} "
            f"records, {_meta(GC.HIGH_SI_SUB)[0]} names with no forming read and {_meta('premarket')[0]} / "
            f"{_meta('postmarket')[0]} movers are not rows; {_meta(GC.HIGH_SI_SUB)[0]} tags a "
            f"{_meta(HS.SQUEEZE_SETUP)[0]} row it also shows. Display only — no rule, gate, count or push changes. "
            f"{GT.UNMEASURED}.")


def covered(tiles: list) -> set:
    """{(SYM, setup)} the served 🧠 cards show: each tile's gajjala.potential.setup + every 🧩 also setup."""
    out = set()
    for t in tiles if isinstance(tiles, list) else ():
        if not isinstance(t, dict):
            continue
        sym = str(t.get("symbol") or "").upper()
        pot = (t.get("gajjala") or {}).get("potential") if isinstance(t.get("gajjala"), dict) else None
        if not sym or not isinstance(pot, dict):
            continue
        if isinstance(pot.get("setup"), str):
            out.add((sym, pot["setup"]))
        for a in pot.get("also") or []:
            if isinstance(a, dict) and isinstance(a.get("setup"), str):
                out.add((sym, a["setup"]))
    return out


def _read_of(doc, setup: str) -> Optional[dict]:
    """The stored read of `setup` on the read doc — None when there is none (no state)."""
    setups = doc.get("setups") if isinstance(doc, dict) and isinstance(doc.get("setups"), dict) else {}
    r = setups.get(setup)
    return r if isinstance(r, dict) and isinstance(r.get("state"), str) and r.get("state") else None


def _key(kind, sym: str, setup: str, doc, scan_by: dict) -> tuple:
    values = PT.tell_values(sym, setup, ctx=(doc or {}).get("ctx") if isinstance(doc, dict) else None,
                            scan_row=(scan_by.get(sym) or {}).get("last"), ah_prev=None, prev_scan=None, also=[])
    return PT.order_key(kind, values, setup, sym)


def _broke_at(trackers: dict, entries: Optional[dict], session_iso: str, sym: str, setup: str):
    """(broke, at) off stages.steps ONLY: the FIRST 🎯 A+ step's clock (None = broke, no clock). (False, None) when no
    step is an A+ — a triggered / stopped read alone is never evidence of one."""
    raw = SG.steps(trackers.get((sym, setup)), entry_at=(entries or {}).get((session_iso, sym, setup)))
    first = next((s for s in raw if s.get("stage") == "aplus"), None)
    if first is None:
        return False, None
    return True, SG.clock_of(first.get("at_et"))


def block(*, reads_by: dict, carded: dict, covered: set, trackers: dict, entries: Optional[dict], session_iso: str,
          dvg: Optional[dict], hsi: Optional[dict], scan_by: dict, rang: Callable[[str, str], Optional[bool]],
          flags, sess: dict, in_window: bool, pass_info: dict, pass_at, pot_ok: bool, v=None) -> dict:
    """The served `all_potentials` block (SPEC potall §3.1). Each candidate row in its own try → `faults_n`."""
    reads_by = reads_by if isinstance(reads_by, dict) else {}
    carded = carded if isinstance(carded, dict) else {}
    cov = covered if isinstance(covered, (set, frozenset)) else set()
    trackers = trackers if isinstance(trackers, dict) else {}
    scan_by = scan_by if isinstance(scan_by, dict) else {}
    pass_info = pass_info if isinstance(pass_info, dict) else {}
    hsi_syms = {str(r.get("symbol") or "").upper() for r in (hsi or {}).get("rows") or [] if isinstance(r, dict)}
    faults = 0
    p_n = 0
    rows: dict = {}                                     # (SYM, setup) → {"key": order key, "row": served row}

    def words(sym, setup, tier, read, doc, *, kind, tracker=None):
        e, label = _meta(setup)
        also = []
        if setup == HS.SQUEEZE_SETUP and sym in hsi_syms:
            he, hl = _meta(GC.HIGH_SI_SUB)
            also.append({"key": GC.HIGH_SI_SUB, "emoji": he, "label": hl})
        if setup == GC.DIVERGING_SUB:
            state, state_word = DGT.STATE, DGT.state_label(read)
            state_label = state_word
        elif read is not None:
            state = read.get("state")
            state_word = GT.variant_label(read) or GT.grade_label(read) or PT.state_word(state, kind)
            state_label = GT.state_label(read, rang(sym, setup) if callable(rang) else None)
        else:
            path = [x for x in (tracker or {}).get("state_path") or [] if isinstance(x, dict)]
            last = path[-1] if path else {}
            state = last.get("state") if isinstance(last.get("state"), str) else None
            state_word, state_label = PT.state_word(state, last.get("kind")), None
        carded_here = sym in (carded.get(setup) or ())
        tag = " " + " ".join(a["emoji"] for a in also) if also else ""
        return {"symbol": sym, "setup": setup, "tier": tier, "state": state, "kind": kind, "emoji": e, "label": label,
                "also": also, "state_word": state_word, "state_label": state_label, "broke_at": None,
                "broke_text": None, "alert_text": None,
                "read_at_text": GT._read_at_text(doc, pass_at) if isinstance(doc, dict) else None,
                "href": PT.deep_link(sym, setup, v) if (carded_here or setup == GC.DIVERGING_SUB) else None,
                "text": f"{sym} · {e} {label}{tag} · {state_word}"}

    # 1. the five setup subs' carded forming reads the 🧠 cards do not show
    for setup in GC.SETUPS:
        for sym0 in carded.get(setup) or []:
            try:
                sym = str(sym0).upper()
                doc = reads_by.get(sym)
                read = _read_of(doc, setup)
                if read is None or read.get("state") not in LIST_STATES:
                    continue
                kind = PT.potential_kind(read)
                if kind:
                    p_n += 1
                if (sym, setup) in cov:
                    continue
                tier = TIERS[0] if kind else TIERS[1]
                row = words(sym, setup, tier, read, doc, kind=kind)
                row["alert_text"] = None if kind else NO_ALERT_TEXT
                rows[(sym, setup)] = {"key": _key(kind, sym, setup, doc, scan_by), "row": row}
            except Exception as exc:                                # noqa: BLE001 — one row never takes the block down
                log.warning("gajjala pot_all: %s/%s failed: %s", sym0, setup, type(exc).__name__)
                faults += 1

    # 2. 🌱 Diverging rows (build's ONE evaluation)
    for item in (dvg or {}).get("rows") or []:
        try:
            sym = str(item.get("symbol") or "").upper()
            if not sym:
                raise ValueError("no symbol")
            doc = item.get("read_doc")
            row = words(sym, GC.DIVERGING_SUB, TIERS[1], item.get("read") or {}, doc, kind=None)
            row["alert_text"] = NO_ALERT_TEXT
            rows[(sym, GC.DIVERGING_SUB)] = {"key": _key(None, sym, GC.DIVERGING_SUB, doc, scan_by), "row": row}
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala pot_all: 🌱 row failed: %s", type(exc).__name__)
            faults += 1

    # 3. ✅ broke — stages.steps ONLY (the 🧭 tag's own 🎯 A+ clock)
    if KEEP_BROKE:
        cands = [k for k in trackers if isinstance(k, tuple) and len(k) == 2]
        for k in (entries or {}):
            if isinstance(k, tuple) and len(k) == 3 and k[0] == session_iso:
                cands.append((str(k[1] or "").upper(), k[2]))
        seen = set()
        for sym0, setup in cands:
            sym = str(sym0 or "").upper()
            if (sym, setup) in seen or setup not in GC.SETUPS or (sym, setup) in cov:
                continue
            seen.add((sym, setup))
            try:
                broke, at = _broke_at(trackers, entries, session_iso, sym, setup)
                if not broke:
                    continue
                text = BROKE_TEXT.format(at=at) if at else BROKE_TEXT_NOCLOCK
                hit = rows.get((sym, setup))
                if hit is None:
                    doc = reads_by.get(sym)
                    read = _read_of(doc, setup)
                    kind = PT.potential_kind(read) if read is not None else None
                    row = words(sym, setup, TIERS[2], read, doc, kind=kind, tracker=trackers.get((sym, setup)))
                    hit = rows[(sym, setup)] = {"key": None, "row": row}
                hit["row"]["broke_at"], hit["row"]["broke_text"] = at, text
            except Exception as exc:                                # noqa: BLE001
                log.warning("gajjala pot_all: ✅ %s/%s failed: %s", sym, setup, type(exc).__name__)
                faults += 1

    # 4. order: potential / forming by potential.order_key; ✅ broke newest first (no clock last), then the name
    by_tier = {t: [] for t in TIERS}
    for item in rows.values():
        by_tier[item["row"]["tier"]].append(item)
    ordered = []
    for t in TIERS[:2]:
        ordered += [i["row"] for i in sorted(by_tier[t], key=lambda i: i["key"])]
    brk = sorted(by_tier[TIERS[2]], key=lambda i: (i["row"]["symbol"], i["row"]["setup"]))
    brk.sort(key=lambda i: (i["row"]["broke_at"] is not None, i["row"]["broke_at"] or ""), reverse=True)   # stable
    ordered += [i["row"] for i in brk]
    n = len(ordered)
    cut = GT._capped(ordered)
    kept, more_n = cut["rows"], cut.get("more_n") or 0
    final = []
    for t in TIERS:                                                 # contiguous by construction
        final += GT.broker_bottom([r for r in kept if r["tier"] == t], flags)

    counts = {"potential": p_n, "forming": sum(1 for r in ordered if r["tier"] == TIERS[1]),
              "broke": sum(1 for r in ordered if r["broke_text"])}
    live = bool(in_window and not pass_info.get("stale") and not pass_info.get("warming")
                and pass_info.get("status") == "ok")
    as_of = pass_info.get("as_of_et")
    as_of_text = (AS_OF_TEXT.format(as_of=as_of, label=(sess or {}).get("label"))
                  if final and isinstance(as_of, str) else None)
    from chart_maps.gajjala import all_table as TBL                 # its FAULT / MORE words, never retyped
    fault_bits = ([TRACK_FAULT_TEXT] if pot_ok is False else []) + ([TBL.FAULT_TEXT.format(n=faults)] if faults else [])
    return {"title": TITLE.format(f=counts["forming"], b=counts["broke"], p=counts["potential"]),
            "order_text": ORDER_TEXT, "rule_text": rule_text(), "live": live, "as_of_text": as_of_text,
            "rows": final, "n": n, "more_n": more_n,
            "more_text": TBL.MORE_TEXT.format(n=more_n, cap=GC.TILE_LIMIT_MAX) if more_n else None,
            "counts": counts, "faults_n": faults, "fault_text": FAULT_SEP.join(fault_bits) if fault_bits else None}


__all__ = ["LIST_STATES", "KEEP_BROKE", "TIERS", "BROKE_TEXT", "BROKE_TEXT_NOCLOCK", "NO_ALERT_TEXT", "TRACK_FAULT_TEXT",
           "AS_OF_TEXT", "TITLE", "ORDER_TEXT", "rule_text", "covered", "block"]
