"""⚖️ Per-ticker bull / bear read — the sector day-tag, pointed at one name.

Ajay 2026-09-20, verbatim: *"I would like it to be in individual tickers but
also in to the potus page in chart maps"* — "it" being the two-sided read that
already ships on the 🔥 Hottest board's sector tiles.

ONE PROMPT, ONE MODEL LEG, ONE DEFINITION OF "USABLE"
-----------------------------------------------------
Everything that decides what the model is told and what counts as an answer is
IMPORTED from `rotation.sector_news_tags`, never restated here:

    _SYSTEM                 the prompt — the hard rules, the JSON shape,
                            "say reversal, never bounce"
    _ask_model              local-first then hosted, `read_by` recorded
    _usable                 both sides written, >= 40 chars each, or no read
    MIN_HEADLINES           one loose headline is not a story
    MAX_HEADLINES_TO_MODEL  how many headlines the model is shown
    today_et                the ET session date, not UTC

A second prompt for the ticker page is the thing this module exists to avoid.
Two prompts drift, and the day they drift the same company reads bullish on
its sector tile and bearish on its own page off the same six headlines, with
nothing on either surface to say why.

THE APP OWNS EVERY NUMBER
-------------------------
`facts_for` builds the FACTS block from what the app already computed — the
research cache's sales/EPS/margin read, the scan row's last close, the
earnings watch's next date. The model is forbidden (rule 1 of `_SYSTEM`) from
stating a number that is not in that block, and the frontend renders the
numbers from `facts`, never parsed back out of the prose. Same division of
labour as `desk.report` and the sector tags.

THE ADJACENCY GUARD RIDES HERE TOO
----------------------------------
`sepa.qoq.period_ok` is the app's one answer to "are these YoY pairs actually
four quarters apart?" — Massive omits a quarter it does not have rather than
leaving a placeholder, so list POSITION is not quarter adjacency. It checks
BOTH pairs the block prints, `Q.HEADLINE_PAIR` (0,4) and `Q.PRIOR_PAIR` (1,5),
and a name that fails either one gets its sales and EPS legs BLANKED rather
than handed to the model: a wrong growth number in the FACTS block is worse
than no growth number, because rule 1 makes the model repeat it.

The same tri-state the 📈 Bonde and 🔥 Hottest rows serve decides it here:
`False` (checked, not four apart) blanks, `None` (no fiscal-period keys on
file) is accepted exactly as those boards accept it. The ticker page and the
boards therefore blank the same documents off the same filed quarter.

NOT A SIGNAL, NOT A GATE
------------------------
This reads nothing, enters nothing, pushes nothing and sizes nothing. Every
result carries `measured: False` and `read_by`, so no surface can present it
as measurement.

FAILURE IS QUIET AND TOTAL
--------------------------
News down, too few headlines, LLM off, half an answer — every one of them ends
in `ok: False` with a reason and whatever headlines were found. Nothing raises
past the caller.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from . import core
from rotation.sector_news_tags import (          # noqa: F401  (re-exported on purpose)
    _SYSTEM, _ask_model, _usable, MAX_HEADLINES_TO_MODEL, MIN_HEADLINES, today_et,
)

log = logging.getLogger("cheetah.news_search.two_sided")

COLL = "news_two_sided"

# The ONE news window. Not a second knob: `core.DEFAULT_WINDOW_HOURS` is what
# the sector tags read on, and a ticker page that read a different span would
# disagree with its own sector tile about what "today's news" is.
WINDOW_HOURS = core.DEFAULT_WINDOW_HOURS

AUDIT = "two_sided"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
def _coll():
    try:
        from sepa.prices import _get_mongo
        pc = _get_mongo()
        return None if pc is None else pc.database[COLL]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("two-sided: mongo unavailable: %s", exc)
        return None


def _save(doc: dict) -> None:
    """Every result is stored, including the failures.

    The audit reason is the same one the sector tags learned the hard way: the
    news cache rolls within hours, so a day later a claim in the prose cannot
    be traced back to the headline that produced it unless the headlines were
    kept beside it.
    """
    coll = _coll()
    if coll is None:
        return
    try:
        coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("two-sided: save %s failed: %s", doc.get("_id"), exc)


def cached(symbol: str, *, date: Optional[str] = None) -> Optional[dict]:
    """Today's stored read for `symbol`, or None. Never calls the model."""
    coll = _coll()
    if coll is None:
        return None
    sym = (symbol or "").upper()
    day = date or today_et()
    try:
        doc = coll.find_one({"_id": f"{sym}|{day}"})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("two-sided: read %s failed: %s", sym, exc)
        return None
    if not doc:
        return None
    doc.pop("_id", None)
    doc["cached"] = True
    return doc


# ---------------------------------------------------------------------------
# Facts — every number from the app, none from the model
# ---------------------------------------------------------------------------
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else None


def _scan_row(sym: str) -> dict:
    try:
        from sepa import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            if str(r.get("symbol") or "").upper() == sym:
                return r
    except Exception as exc:                                   # noqa: BLE001
        log.debug("two-sided: scan row for %s unavailable: %s", sym, exc)
    return {}


def _period_ok(periods):
    """The app's tri-state on the YoY pairs: True / False / None.

    `sepa.qoq.period_ok` is the ONE implementation — imported, never restated.
    It covers BOTH year-over-year pairs the FACTS block prints, `Q.HEADLINE_PAIR`
    (0,4) for `sales_growth_yoy_pct` / `eps_growth_yoy_pct` and `Q.PRIOR_PAIR`
    (1,5) for `sales_prior_yoy_pct` and the `accelerating` flag that is derived
    from it. Guarding only (0,4) — what this module did until 2026-09-20 — handed
    the model a prior-year leg on exactly the documents 📈 Bonde, 🔥 Hottest and
    the 🚀 growth board blank, which is the "explosive here, refused there"
    split the data spine exists to close.

    `None` means UNVERIFIABLE (no fiscal-period keys on file), never "fine" —
    the caller decides, and it accepts, because refusing every legacy document
    would blank the block rather than improve it.
    """
    try:
        from sepa.qoq import period_ok
        return period_ok(periods)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("two-sided: adjacency check unavailable: %s", exc)
        return None


def facts_for(symbol: str) -> dict:
    """The deterministic block handed to the model. Numbers ONLY from the app.

    Keys whose value is missing are DROPPED (the `_facts` rule in the sector
    tags): the model is never handed a `None` to hallucinate around, and the
    frontend never renders an em-dash where a fact should be.
    """
    sym = (symbol or "").upper()
    if not sym:
        return {}

    snap: dict = {}
    try:
        from sepa import research
        snap = (research.decision_snapshot([sym]) or {}).get(sym) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.debug("two-sided: research snapshot for %s unavailable: %s", sym, exc)

    sales = snap.get("sales") or {}
    eq = snap.get("earnings_quality") or {}
    components = (eq.get("components") or {}) if isinstance(eq, dict) else {}

    # THE GUARD. A mismatched YoY pair — EITHER pair — blanks every leg that is
    # computed off it: the growth number, the prior-year number, the tier that
    # is derived from the growth number, the acceleration flag that is derived
    # from the prior, and the EPS YoY that is the same comparison on the bottom
    # line. Only a CHECKED mismatch blanks (`period_ok is False`); an
    # unverifiable pair (`None`) is accepted, the same accept-by-default
    # `rotation.hottest._fundamentals_row` and 📈 Bonde apply to the same
    # documents, so the ticker page cannot disagree with either board.
    period_state = _period_ok(snap.get("q_period_series"))
    pair_ok = period_state is not False

    row = _scan_row(sym)

    next_earnings = None
    try:
        from sepa import earnings_watch
        nxt = earnings_watch.next_event(sym) or {}
        next_earnings = nxt.get("date")
    except Exception as exc:                                   # noqa: BLE001
        log.debug("two-sided: earnings watch for %s unavailable: %s", sym, exc)

    company = row.get("name") or row.get("company")
    if not company:
        try:
            from sepa import company_names
            company = company_names.name_for(sym)
        except Exception:                                      # noqa: BLE001
            company = None

    raw = {
        "symbol": sym,
        "company": company,
        "last_close": _num(row.get("last_close") or row.get("close")),
        "sales_growth_yoy_pct": _num(sales.get("growth_yoy_pct")) if pair_ok else None,
        "sales_prior_yoy_pct": _num(sales.get("prior_yoy_pct")) if pair_ok else None,
        "sales_tier": (sales.get("tier") if pair_ok else None),
        "sales_accelerating": (sales.get("accelerating") if pair_ok else None),
        "eps_growth_yoy_pct": _num(snap.get("q_eps_growth_pct")) if pair_ok else None,
        "net_margin_pct": _num(components.get("npm_latest_pct")),
        "next_earnings": next_earnings,
        # Said in the block itself so the model can write "the growth figures
        # are not comparable this quarter" instead of inventing one.
        "yoy_pair_comparable": pair_ok,
    }
    if (raw.get("sales_tier") or "").lower() == "unknown":
        raw["sales_tier"] = None
    return {k: v for k, v in raw.items() if v is not None and v != ""}


# ---------------------------------------------------------------------------
# The read
# ---------------------------------------------------------------------------
def _headlines(items: list) -> list:
    return [{"title": h.get("title"), "url": h.get("url"),
             "source": h.get("source"), "published": h.get("published")}
            for h in (items or [])[:MAX_HEADLINES_TO_MODEL]]


def read(symbol: str, *, force: bool = False, now: Optional[float] = None,
         search=None, ask=None) -> dict:
    """One ticker's bull case AND bear case off today's headlines.

    Once per ET session date per symbol: the stored doc is served back with
    `cached: True` and NO model call, because the model leg is the expensive
    one and the headlines it read are already beside the answer. `force=True`
    re-reads.
    """
    sym = (symbol or "").upper()
    day = today_et()
    if not sym:
        return {"ok": False, "symbol": sym, "date": day,
                "reason": "no symbol", "headlines": [], "measured": False}

    if not force:
        hit = cached(sym, date=day)
        if hit is not None:
            return hit

    search = search or core.search_sync
    ask = ask or _ask_model

    try:
        res = search(ticker=sym, window_hours=WINDOW_HOURS, audit=AUDIT) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("two-sided: news for %s failed: %s", sym, exc)
        res = {}
    items = res.get("items") or []

    base = {"_id": f"{sym}|{day}", "symbol": sym, "date": day,
            "window_hours": WINDOW_HOURS, "measured": False,
            "built_at": time.time() if now is None else now}

    if len(items) < MIN_HEADLINES:
        out = {**base, "ok": False,
               "reason": f"fewer than {MIN_HEADLINES} headlines in the last "
                         f"{WINDOW_HOURS}h",
               "headlines": _headlines(items),
               "headline_count": len(items)}
        _save(out)
        return _served(out)

    facts = facts_for(sym)
    try:
        parsed = ask(facts, items)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("two-sided: model leg for %s failed: %s", sym, exc)
        parsed = None

    if parsed is None:
        out = {**base, "ok": False, "reason": "model unavailable",
               "headlines": _headlines(items), "headline_count": len(items),
               "facts": facts}
        _save(out)
        return _served(out)

    if not _usable(parsed):
        # Half a read is worse than none: a bull case with an empty bear case
        # reads as a recommendation, which is the one thing this is not.
        out = {**base, "ok": False,
               "reason": "the model did not write both sides",
               "headlines": _headlines(items), "headline_count": len(items),
               "facts": facts}
        _save(out)
        return _served(out)

    out = {
        **base,
        "ok": True,
        "positive": bool(parsed.get("positive")),
        "why_positive": (parsed.get("why_positive") or "").strip() or None,
        "bull": parsed["bull"].strip(),
        "bear": parsed["bear"].strip(),
        "facts": facts,
        "headlines": _headlines(items),
        "headline_count": len(items),
        "read_by": parsed.get("provider") or "llm",
    }
    _save(out)
    return _served(out)


def _served(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["cached"] = False
    return out
