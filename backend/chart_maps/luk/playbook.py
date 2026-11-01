"""📓 Luk's Playbook + the ℹ️ panel lines — the served text of 🥇 Luk's (BUILD SPEC luk-tab §3.10 / §3.12, 2026-11-01).

WHAT. His method in HIS words: every rule item is read from verified_rules.json (the cited registry — each quote is
byte-matched to its fixture line by tests/test_luk_verified_rules.py) and served with its cite ("{video} {h:mm:ss}",
the guest post, or a URL). Item kinds: "his" (his rule, his caption words in curly quotes; `verbatim` False for the one
paraphrase), "consideration" (what he is considering — listed, not applied), "mine" (a Cheetah formula, HIS CALL),
"his_call" (SYNTHESIS §D, none applied), "external" (a third party's numbers, not re-run here).

NUMBERS. The Playbook's rule texts quote his numbers as he said them; every number this module FORMATS (the worked
sizing example, the formulas, every ℹ️ line) is read from chart_maps.luk.constants at call time, never typed.

WORDING. "Reversal", never the other word; nothing here claims an advantage. UNMEASURED: no study in this app says
these setups win. Nothing here gates, ranks, sizes or pushes.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.luk import constants as LC

log = logging.getLogger("chart_maps.luk.playbook")

_RULES_FILE = Path(__file__).resolve().parent / "verified_rules.json"
KINDS = ("his", "mine", "external", "his_call", "consideration")
KIND_HIS, KIND_MINE, KIND_EXTERNAL, KIND_HIS_CALL, KIND_CONSIDERATION = KINDS
TITLE = "📓 Luk's Playbook — his own words, cited line by line · UNMEASURED"
SUBSTACK_CITE = "his guest post, 2025-02-01"
FAN_CITE = "his screener frames (iMBI3ZcQ6sU ~1:17:44, transcribed on martinluk.com)"
HIS_CALL_CITE = "SYNTHESIS §D #{n} — not applied, his call"
MINE_CITE = "MINE — a Cheetah formula ({h})"
EXTERNAL_TAIL = " — EXTERNAL, not re-run here"
_YT = re.compile(r"[?&]v=([A-Za-z0-9_-]+)")
_SEC_PER_MIN = 60                          # a unit, not a rule
_THOUSAND, _MILLION, _BILLION = 1_000, 1_000_000, 1_000_000_000   # units, not rules

# (key, title, registry ids) — the §3.10 order. "sizing" and "formulas" gain items built from the constants.
SECTIONS = (
    ("who", "Who he is", ("R1", "R2")),
    ("scans", "The three scans", ("U2", "U4", "U5", "U6", "U1", "U8")),
    ("tiers", "Watchlist tiers", ("U3",)),
    ("where", "Where he buys", ("E1", "E8", "E5")),
    ("trigger", "The trigger", ("E2", "E3", "E6", "E7", "E4")),
    ("stop", "The stop", ("S1", "S2", "S3", "S4")),
    ("exits", "Exits — stated, computed only for grading", ("X1", "X2", "X3", "X4", "X5", "X6")),
    ("sizing", "Sizing — listed, never applied", ("Z1", "Z2", "Z3", "Z4")),
    ("market", "Market — a state word, never a gate", ("M1", "M2", "M3", "M3-paraphrase")),
    ("considerations", "His considerations, not applied", ("U7",)),
    ("formulas", "Formulas computed here", ()),
    ("his_calls", "The 15 HIS CALLs (SYNTHESIS §D)", tuple("H%d" % i for i in range(1, 16))),
    ("external", "External backtests — EXTERNAL, not re-run here", ("EX1", "EX2")),
    ("stats", "His own stats", ("ST1", "ST2", "ST3")),
)
_KIND_OF_ID = {"U7": KIND_CONSIDERATION, "R1": KIND_EXTERNAL, "EX1": KIND_EXTERNAL, "EX2": KIND_EXTERNAL}


# ── the registry ─────────────────────────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _rules_doc() -> Optional[dict]:
    try:
        return json.loads(_RULES_FILE.read_text(encoding="utf-8"))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk playbook: verified_rules.json unreadable: %s", exc)
        return None


def rules_by_id(doc: Optional[dict] = None) -> dict:
    doc = doc if doc is not None else _rules_doc()
    out = {}
    for t in (doc or {}).get("topics") or []:
        for r in t.get("verified") or []:
            if isinstance(r, dict) and r.get("id"):
                out[r["id"]] = r
    return out


def _source_titles(doc: Optional[dict]) -> dict:
    return {s.get("key"): s for s in (doc or {}).get("sources") or [] if isinstance(s, dict)}


def _cite_of(src: dict, srcs: dict) -> Optional[str]:
    key, ts, url = src.get("key"), src.get("ts"), src.get("url") or ""
    if key == "L7":
        return SUBSTACK_CITE
    if key == "L8":
        return FAN_CITE
    m = _YT.search(url)
    if m:
        return "%s %s" % (m.group(1), ts) if ts else m.group(1)
    return url or (srcs.get(key) or {}).get("url")


def _cite_text(rule: dict, srcs: dict) -> str:
    cites = []
    for s in rule.get("sources") or []:
        c = _cite_of(s, srcs)
        if c and c not in cites:
            cites.append(c)
    return " · ".join(cites)


def _first_url(rule: dict) -> Optional[str]:
    for s in rule.get("sources") or []:
        if s.get("url"):
            return s["url"]
    return None


def _rule_item(rule: dict, srcs: dict) -> dict:
    rid = rule.get("id")
    if rule.get("status") == "his_call":
        n = int(rid[1:]) if isinstance(rid, str) and rid[1:].isdigit() else 0
        return {"id": rid, "text": rule.get("rule", ""), "cite_text": HIS_CALL_CITE.format(n=n), "url": None,
                "kind": KIND_HIS_CALL, "verbatim": False}
    kind = _KIND_OF_ID.get(rid, KIND_HIS)
    quotes = [q for q in rule.get("quotes") or [] if isinstance(q, str) and q]
    text = rule.get("rule", "")
    if quotes:
        text = text + " — " + " · ".join("“%s”" % q for q in quotes)
    if rule.get("note"):
        text = text + " (" + rule["note"] + ")"
    if kind == KIND_EXTERNAL:
        text = text + EXTERNAL_TAIL
    return {"id": rid, "text": text, "cite_text": _cite_text(rule, srcs) or (_first_url(rule) or ""),
            "url": _first_url(rule), "kind": kind, "verbatim": bool(quotes) and rule.get("kind") != "paraphrase"}


# ── items built from the constants ───────────────────────────────────────────────────────────────────────────────
def _g(x) -> str:
    return "%g" % x


def _usd(v) -> str:
    v = float(v)
    for unit, suffix in ((_BILLION, "B"), (_MILLION, "M"), (_THOUSAND, "K")):
        if abs(v) >= unit:
            return "$%g%s" % (v / unit, suffix)
    return "$%g" % v


def _count(v) -> str:
    v = float(v)
    for unit, suffix in ((_MILLION, "M"), (_THOUSAND, "K")):
        if abs(v) >= unit:
            return "%g%s" % (v / unit, suffix)
    return "%g" % v


def _hhmm(t) -> str:
    return t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)


def sizing_example_item(z2: Optional[dict] = None) -> dict:
    """His worked example (the LAST source of rule Z2 — VKNEJA5r8zw 3:03:50), every number from LC.LUK_SIZING_EXAMPLE."""
    acct, risk_pct, risk_usd, stop_pct, pos_usd, pos_pct = LC.LUK_SIZING_EXAMPLE
    text = ("Worked example, his: a {acct} account risking {r}% = {ru} of risk; {ru} ÷ a {s}% stop = a {pu} position "
            "({pp}% of the account) — listed, never applied").format(
        acct="${:,}".format(acct), r=_g(risk_pct), ru="$%g" % risk_usd, s=_g(stop_pct), pu="${:,}".format(pos_usd),
        pp=_g(pos_pct))
    srcs = (z2 or {}).get("sources") or [{}]
    src = srcs[-1]
    return {"id": "Z2-example", "text": text, "cite_text": _cite_of(src, {}) or "", "url": src.get("url"),
            "kind": KIND_HIS, "verbatim": False}


def formula_items() -> list:
    """The MINE formulas (spec §7 #7, #10, #11, #12) — every number from LC."""
    rows = (
        ("F1", "1-week volatility = the mean of (high − low) ÷ close over %d sessions" % LC.LUK_VOL_1W_SESSIONS,
         "HIS CALL #10"),
        ("F2", "1-week price × volume = the sum over %d sessions" % LC.LUK_PX_VOL_1W_SESSIONS, "HIS CALL #10"),
        ("F3", "1-month %% = the change over %d sessions" % LC.LUK_PERF_1M_SESSIONS, "HIS CALL #10"),
        ("F4", "ADR = %d sessions, the house ADR (his \"ADR\" names no period)" % LC.LUK_ADR_SESSIONS, "HIS CALL #10"),
        ("F5", "%d-day average volume = %d sessions (his \"%dD\")"
         % (LC.LUK_AVG_VOL_SESSIONS, LC.LUK_AVG_VOL_SESSIONS, LC.LUK_AVG_VOL_SESSIONS), "HIS CALL #10"),
        ("F6", "Hourly bars = regular-session minutes only, clock-anchored (his TradingView anchors the open)",
         "HIS CALL #7"),
        ("F7", "Low of day = the regular-session low (premarket excluded)", "HIS CALL #7"),
        ("F8", "\"US\" on his frames = common stock + ADRs; ETFs, warrants and units out", "HIS CALL #11"),
        ("F9", "A market cap not in the house cache → the row is kept with \"cap unknown — not filtered\"",
         "HIS CALL #12"),
        ("F10", "A daily bar is a closed day only when cached at least %d s after the %s ET close"
         % (LC.LUK_DAILY_TRUST_AFTER_SEC, _hhmm(LC.LUK_FILL_TO_ET)), "HIS CALL #27"),
    )
    return [{"id": i, "text": t, "cite_text": MINE_CITE.format(h=h), "url": None, "kind": KIND_MINE,
             "verbatim": False} for i, t, h in rows]


# ── the served blocks ────────────────────────────────────────────────────────────────────────────────────────────
def playbook(doc: Optional[dict] = None) -> dict:
    """{"title", "sections": [{"key", "title", "items": [{id, text, cite_text, url, kind, verbatim}]}]} — an id the
    registry lacks is skipped (logged), never invented."""
    doc = doc if doc is not None else _rules_doc()
    by_id = rules_by_id(doc)
    srcs = _source_titles(doc)
    sections = []
    for key, title, ids in SECTIONS:
        items = []
        for rid in ids:
            r = by_id.get(rid)
            if r is None:
                log.warning("luk playbook: rule %s missing from verified_rules.json", rid)
                continue
            items.append(_rule_item(r, srcs))
        if key == "sizing":
            items.append(sizing_example_item(by_id.get("Z2")))
        if key == "formulas":
            items.extend(formula_items())
        sections.append({"key": key, "title": title, "items": items})
    return {"title": TITLE, "sections": sections}


def all_items(pb: Optional[dict] = None) -> list:
    pb = pb if pb is not None else playbook()
    return [it for s in pb.get("sections") or [] for it in s.get("items") or []]


def rules_lines() -> list:
    """The ℹ️ Rules panel lines for 🥇 Luk's — every number formatted from chart_maps.luk.constants (and GC's cadence /
    settle) at call time; supply_demand.rules_info wraps them as {"title": "🥇 Luk's", "lines": rules_lines()}."""
    cap, v1w = _usd(LC.LUK_SCREEN_MIN_CAP_USD), _g(LC.LUK_SCREEN_MIN_VOL_1W_PCT)
    avg = "%d-day average volume > %s" % (LC.LUK_AVG_VOL_SESSIONS, _count(LC.LUK_SCREEN_MIN_AVG_VOL_10D))
    pxv = _usd(LC.LUK_SCREEN_MIN_PX_VOL_USD)
    e21, e50 = LC.LUK_POTENT_EMAS
    h9, h21 = LC.LUK_HOURLY_EMAS
    i9, i21 = LC.LUK_INDEX_EMAS
    one, five = LC.LUK_ORH_CANDLE_MIN, LC.LUK_ORH_SWITCH_MIN
    win = LC.LUK_TRIGGER_WINDOW_END_MIN
    cad = GC.PASS_CADENCE_SEC // _SEC_PER_MIN
    r1, r2 = LC.LUK_PARTIAL_R
    p1, p2 = LC.LUK_POSITION_PCT
    syms = " and ".join(LC.LUK_INDEX_SYMBOLS)
    return [
        ("Martin Luk's own published rules (US Investing Championship stock-division winner; he sells nothing), every rule "
         "cited line by line on the 📓 Playbook. Every alert is recorded in shadow, never sent. UNMEASURED — nothing "
         "here trades, sizes or enters a lane. Not advice."),
        ("☀️ Pre-market screen: market cap > %s, %s, price × volume > %s, 1-week volatility > %s%%, sorted by "
         "pre-market %% change. 🏆 Leader: market cap > %s, %s, 1-week price × volume > %s, sorted by 1-month %%. "
         "⚡ Potent: price above the %d EMA and at or above the %d EMA, market cap > %s, 1-week volatility > %s%%, "
         "price × volume > %s, change from open outside ±%s%%, sorted by %% change. Top %d per screen; a cap the house "
         "cache lacks is kept, not filtered."
         % (cap, avg, pxv, v1w, cap, avg, _usd(LC.LUK_LEADER_MIN_PX_VOL_1W_USD), e50, e21, cap, v1w, pxv,
            _g(LC.LUK_POTENT_CHG_FROM_OPEN_BAND_PCT), LC.LUK_SCREEN_TOP_N)),
        ("One pass every %d minutes, %s–%s ET, as a detached child of the 🚩 pass: up to %d screened names get "
         "%d-minute, %d-minute and hourly bars."
         % (cad, LC.LUK_PASS_OPEN_ET, LC.LUK_PASS_CLOSE_ET, LC.LUK_SHORTLIST_MAX, one, five)),
        ("↩️ Pullback reversal: today's regular-session low at or under the prior close's daily %d EMA, a flush that "
         "touches the hourly %d EMA (reaching under the hourly %d EMA is a fact, not a gate), then the first break of the previous "
         "bar's high after the low — %d-minute bars for the first %d minutes, %d-minute bars to %d minutes."
         % (LC.LUK_PULLBACK_DAILY_EMA, h9, h21, one, LC.LUK_ONE_MIN_UNTIL_MIN, five, LC.LUK_FIVE_MIN_UNTIL_MIN)),
        ("🔔 Opening range: the take-out of the first %d-minute candle's high, on %d-minute bars until the first "
         "%d-minute candle forms, then %d-minute bars, inside the first %d minutes."
         % (LC.LUK_ORH_CANDLE_MIN, one, LC.LUK_ORH_SWITCH_MIN, five, win)),
        "📦 Inside day: yesterday's range inside the day before's (strict), then yesterday's high taken out at any "
        "regular-session time.",
        ("Stop: the low of day; when the trigger is more than %s%% above it, the %d-minute entry candle's low. A+ needs "
         "the stop within %s%% of the trigger and within %s × the %d-day ADR — wider is listed, not A+."
         % (_g(LC.LUK_LOD_SWITCH_PCT), five, _g(LC.LUK_STOP_MAX_PCT), _g(LC.LUK_STOP_ADR_FRAC), LC.LUK_ADR_SESSIONS)),
        ("Listed, never A+: more than %s%% above the low of day (his no-chase rule), or a pullback / opening-range "
         "break after the first %d minutes. A listed card keeps its trigger, stop and R."
         % (_g(LC.LUK_NO_CHASE_PCT), win)),
        ("A+ = every rule met and the break bar closed: on %d-minute bars the latest closed bar; on %d-minute bars any "
         "bar closed since the previous pass with no stop touch since — a %d-minute trigger is read up to %d minutes "
         "after its bar closed." % (five, one, one, cad)),
        ("🧭 %s: the %d EMA under the %d EMA = his not-favourable-for-longs read — a word, never a gate."
         % (syms, i9, i21)),
        ("🏁 Track record from %s: fill = the first %d-minute bar at least %d s after the alert at or above the "
         "trigger; exit = the stop or the first daily close below the %d EMA; +%dR / +%dR shown as flags. His sizing "
         "(%s%% risk, %d–%d%% positions) is listed, never applied."
         % (LC.LUK_RECORD_FROM, one, GC.BAR_SETTLE_SEC, LC.LUK_TRAIL_EMAS[0], r1, r2,
            _g(LC.LUK_RISK_PER_TRADE_PCT), p1, p2)),
    ]
