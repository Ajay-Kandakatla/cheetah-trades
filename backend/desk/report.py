"""Daily pre-market Desk report — the app's data through a trader's lens.

Ajay 2026-08-28: "Add a cron or daily routine use our data to do the
analysis" as an experienced buy-side momentum trader (his pasted persona:
pattern-driven, unsentimental, hunts asymmetry, sizes for survival, says
"nothing qualifies today" when nothing qualifies).

Division of labor (the design rule of this module):
  * desk/scoring.py computes every NUMBER — verdicts, cuts, component
    scores, R multiples, share counts. Deterministic, tested.
  * The LLM (llm.chat, anthropic) writes only PROSE around those numbers
    — thesis cards, the bear case, the mind-changer — and is instructed
    to use nothing outside the payload. If the LLM is down the report
    still ships with deterministic one-liners; analysis never blocks on
    a language model.

Data sources, all in-house: sepa.scanner.load_latest (swing module),
sepa.market_regime (regime), catalysts.premarket + gabbar levels (at-the-
level module), chart_maps.board.undervalue_tiles (position module),
options.gex_history (dealer book, post-close — labeled as such),
sepa.earnings_watch (binary-event cuts), rotation.tracker (group RS),
patterns.history.accuracy (base rates), portfolio holdings + knife_watch
(what he already owns). No web, no memory: anything the app cannot verify
is reported as unavailable, never estimated.

Persistence: one doc per ET day in Mongo ``desk_reports``. Yesterday's
book is graded every morning (triggered / stopped / target / dead) — the
carry-forward loop is what turns this from a toy into a journal.

Delivery: ``todo_reminder`` push when the report is ready (it IS a
scheduled reminder; the 2026-06-24 keep-set gains no new kinds) linking
to /desk. Cron: 8:40am ET weekdays, after the 19:10 earnings-calendar
refresh and inside the pre-market quote window.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from desk import scoring

log = logging.getLogger("desk.report")

ET = ZoneInfo("America/New_York")

SWING_TIME_STOP = "10 sessions without trigger → drop"
LEVEL_TIME_STOP = "today only — level trades don't age"
POSITION_TIME_STOP = "8 weeks or thesis break, whichever first"

PERSONA = """You are an experienced buy-side momentum trader running a \
daily pre-market scan. You have traded through 2000, 2008, 2020 and 2022. \
You are pattern-driven and unsentimental: you hunt asymmetry, you size for \
survival, and you kill ideas fast. You do not pump, you do not chase \
headlines, and you say "nothing qualifies today" when nothing qualifies.

Rules for THIS task:
- You are writing the prose sections of a report whose numbers were \
already computed by the scanner. Use ONLY figures present in the JSON \
payload. If a claim needs a number that is not in the payload, write \
[unverified] instead of a number. Never invent prices, floats, short \
interest, dates or catalysts.
- Price is primary evidence; when story and chart disagree, the chart is \
the update. Name the theme every candidate belongs to. Ask who is on the \
other side. Think in base rates (the payload carries the app's own \
pattern expectancy ledger). No hype language, no "this could 10x".
- The reader over-indexes on AI/semis. If the book is all one theme, say \
so bluntly in tilt_check; if it is balanced, say that in one line.
- Be willing to say the setup quality is poor. Flattery costs money."""

_PROSE_SCHEMA_HINT = """Return STRICT JSON, nothing else:
{
 "regime_lines": ["<=3 short lines explaining the regime verdict from the payload numbers"],
 "cards": {"TICKER": "<=120 words: what is happening, why now, who is selling, the single number/event that proves or kills it, and the exact invalidation price/fact"},
 "bear_case": "5 short lines shorting the TOP-scored name, as the smartest person fading it",
 "tilt_check": "1-2 lines: is this book over-concentrated for this reader?",
 "mind_changer": "the one breadth/macro event in the payload's horizon that would flip the regime verdict"
}
Write a card for every ticker in payload.book. Keys of cards must be exactly those tickers."""


# ── payload assembly ───────────────────────────────────────────────────────
def _today_et() -> str:
    return datetime.now(tz=ET).date().isoformat()


def _swing_candidates(rows: list, earn_map: dict) -> tuple:
    """Module B: SEPA rows worth scoring — buyable, or candidate with the
    setup ready and price in the zone. Returns (scored, cut_list)."""
    scored, cuts = [], []
    for r in rows:
        if not (r.get("is_buyable")
                or (r.get("is_candidate") and r.get("setup_ready")
                    and r.get("is_in_buy_zone"))):
            continue
        sym = r.get("symbol")
        days_to = (earn_map.get(sym) or {}).get("days_to")
        reasons = scoring.disqualify(r, earnings_in_days=days_to)
        if reasons:
            cuts.append({"symbol": sym, "module": "B", "reasons": reasons})
            continue
        s = scoring.score_row(r)
        if s["plan"] is None:
            cuts.append({"symbol": sym, "module": "B",
                         "reasons": ["no honest entry/stop geometry"]})
            continue
        scored.append({
            "symbol": sym, "module": "B", "score": s["total"],
            "parts": s["parts"], "plan": s["plan"],
            "last_close": r.get("last_close"), "rs_rank": r.get("rs_rank"),
            "industry": r.get("industry"),
            "theme": (r.get("pioneer_themes") or [None])[0],
            "stage": (r.get("stage") or {}).get("stage"),
            "sales_tier": ((r.get("fundamentals") or {}).get("sales")
                           or {}).get("tier"),
            "vcp_contractions": (r.get("vcp") or {}).get("n_contractions"),
            "up_down_vol_ratio": (r.get("volume") or {}).get("up_down_vol_ratio"),
            "adv_dollars": (r.get("liquidity") or {}).get("avg_dollar_vol"),
            "buyable": bool(r.get("is_buyable")),
            "time_stop": SWING_TIME_STOP,
        })
    scored.sort(key=lambda c: -c["score"])
    return scored, cuts


def _at_the_level() -> dict:
    """Module A: today's tape — pre-market gappers (only inside the
    pre-market window; empty outside it, honestly labeled) plus curated
    Gabbar levels the live price is touching or approaching."""
    out = {"gappers": [], "gabbar_hits": [], "window": None}
    try:
        from catalysts import premarket
        win = premarket.is_premarket_window()
        out["window"] = win
        if win.get("open"):
            scan = premarket.scan_premarket(max_results=10)
            out["gappers"] = scan.get("candidates") or scan.get("results") or []
    except Exception as exc:
        log.warning("desk: premarket scan failed: %s", exc)
    try:
        from catalysts import gabbar_levels as GL
        from catalysts.gabbar_watch import band_proximity
        from sepa import prices
        covered = GL.list_covered_symbols()
        live = prices.bulk_live_prices(covered) or {}
        for sym in covered:
            q = live.get(sym) or {}
            last = q.get("price") or q.get("last_trade_price")
            payload = GL.get_bands(sym)
            if not last or not payload:
                continue
            for hit in band_proximity(float(last), payload.get("bands") or []):
                out["gabbar_hits"].append({**hit, "symbol": sym,
                                           "price": float(last)})
    except Exception as exc:
        log.warning("desk: gabbar proximity failed: %s", exc)
    return out


def _position_ideas(limit: int = 6) -> list:
    """Module C: Under Value board top names — explosive sales priced
    below their growth, the structural-reprice module."""
    try:
        from chart_maps import board
        data = board.undervalue_tiles(limit=limit)
        out = []
        for t in (data.get("tiles") or [])[:limit]:
            stats = {s.get("k"): s.get("v") for s in t.get("stats") or []}
            out.append({"symbol": t.get("symbol"), "module": "C",
                        "theme": t.get("theme"),
                        "ps": stats.get("P/S"), "rev_yoy": stats.get("Rev YoY"),
                        "psg": stats.get("PSG"), "mkt_cap": stats.get("Mkt cap"),
                        "why": t.get("why"),
                        "time_stop": POSITION_TIME_STOP})
        return out
    except Exception as exc:
        log.warning("desk: undervalue module failed: %s", exc)
        return []


def _account(owner: str) -> dict:
    """Live account value from holdings — the sizing denominator. The
    knife-watch verdicts ride along so the report opens with whether
    anything he OWNS is broken before pitching anything new."""
    out = {"value": None, "holdings": [], "knives": [],
           "cash": None, "positions_value": None}
    try:
        from portfolio import store
        from portfolio.quotes import fetch_quotes
        holdings = store.list_holdings(owner)
        quotes = fetch_quotes([h["ticker"] for h in holdings]) or {}
        total = 0.0
        for h in holdings:
            q = quotes.get(h["ticker"]) or {}
            last = q.get("last")
            val = (float(last) * float(h.get("shares") or 0)
                   if isinstance(last, (int, float)) else None)
            if val:
                total += val
            out["holdings"].append({"ticker": h["ticker"],
                                    "shares": h.get("shares"),
                                    "last": last, "value": val,
                                    "day_change_pct": q.get("day_change_pct")})
        out["positions_value"] = round(total, 2) if total else None
        # Cash rides on top (2026-08-31). His book went to ~86% cash after the
        # Friday selloff and the old holdings-only value sized every idea off
        # a seventh of the real account. None = cash not tracked, and then the
        # value falls back to positions alone — labelled by cash staying None
        # so the report can say which denominator it used.
        cash = store.get_cash(owner)
        out["cash"] = cash
        total_eq = total + (cash or 0.0)
        out["value"] = round(total_eq, 2) if total_eq else None
    except Exception as exc:
        log.warning("desk: account read failed: %s", exc)
    try:
        from portfolio import knife_watch
        rows = knife_watch.check_holdings(owner, push=False).get("rows") or []
        out["knives"] = [{"ticker": r["ticker"], "verdict": r["verdict"],
                          "signals": r.get("price_signals") or []}
                         for r in rows if r.get("verdict") != "CLEAN"]
    except Exception as exc:
        log.warning("desk: knife read failed: %s", exc)
    return out


def _context_blocks(book_symbols: list) -> dict:
    """Rotation, dealer gamma for the book, pattern base rates, macro —
    every block degrades to None rather than blocking the report."""
    ctx = {"rotation": None, "gex": None, "pattern_base_rates": None,
           "macro": None}
    try:
        from rotation import tracker
        from datetime import timedelta
        start = (datetime.now(tz=ET).date() - timedelta(days=92)).isoformat()
        rot = tracker.build(start=start)
        ctx["rotation"] = {
            "benchmark": (rot.get("benchmark") or {}).get("symbol"),
            "leading": rot.get("leaders") or [],
            "lagging": rot.get("laggards") or [],
            "havens": [h.get("group") or h.get("name")
                       for h in (rot.get("havens") or [])[:3]],
            "stance": rot.get("stance"),
        }
    except Exception as exc:
        log.warning("desk: rotation read failed: %s", exc)
    try:
        from options import gex_history
        snap = gex_history.snapshot_for(book_symbols) if book_symbols else {}
        ctx["gex"] = {s: {"regime": v.get("regime"),
                          "put_wall": v.get("put_wall"),
                          "call_wall": v.get("call_wall"),
                          "date_et": v.get("date_et")}
                      for s, v in (snap or {}).items()}
        if ctx["gex"]:
            ctx["gex_note"] = "post-close dealer book — yesterday's positioning"
    except Exception as exc:
        log.warning("desk: gex read failed: %s", exc)
    try:
        from patterns import history as ph
        acc = ph.accuracy()
        pats = {}
        for name, by_status in (acc.get("patterns") or {}).items():
            blob = by_status.get("resolved") or next(iter(by_status.values()), {})
            if isinstance(blob, dict) and blob.get("n"):
                pats[name] = {"n": blob.get("n"),
                              "expectancy_pct": blob.get("expectancy_pct")}
        ctx["pattern_base_rates"] = pats or None
    except Exception as exc:
        log.warning("desk: pattern accuracy read failed: %s", exc)
    try:
        from sepa import macro_risk
        m = macro_risk.cached_market()
        if m:
            ctx["macro"] = {"score": m.get("score"), "level": m.get("level"),
                            "summary": m.get("summary"),
                            "stale": m.get("stale")}
    except Exception as exc:
        log.warning("desk: macro read failed: %s", exc)
    return ctx


# ── carried forward: grade yesterday's book ────────────────────────────────
def grade_prior_book(prior: Optional[dict]) -> list:
    """For each name in the prior report's book: did it trigger, did the
    stop or target print, is the thesis intact? Uses daily bars after the
    report date — deterministic, no opinions."""
    if not prior or not prior.get("book"):
        return []
    from sepa import prices
    graded = []
    since = prior.get("date")
    for idea in prior["book"]:
        sym, plan = idea.get("symbol"), idea.get("plan") or {}
        g = {"symbol": sym, "module": idea.get("module"),
             "score": idea.get("score"), "from": since, "status": "no_data"}
        entry, stop, t1 = plan.get("entry"), plan.get("stop"), plan.get("target1")
        try:
            df = prices.load_prices(sym)
            if df is None or not len(df) or not isinstance(entry, (int, float)):
                graded.append(g)
                continue
            after = df[df.index > since]
            if not len(after):
                g["status"] = "no_new_bars"
                graded.append(g)
                continue
            trig_days = after[after["high"] >= entry]
            if not len(trig_days):
                g["status"] = "not_triggered"
            else:
                post = after[after.index >= trig_days.index[0]]
                if isinstance(stop, (int, float)) and (post["low"] <= stop).any():
                    g["status"] = "stopped"
                elif isinstance(t1, (int, float)) and (post["high"] >= t1).any():
                    g["status"] = "target1_hit"
                else:
                    g["status"] = "open"
                g["last_close"] = float(after["close"].iloc[-1])
        except Exception as exc:
            log.warning("desk: grading %s failed: %s", sym, exc)
        graded.append(g)
    return graded


# ── LLM prose ──────────────────────────────────────────────────────────────
def _prose(payload: dict) -> dict:
    """Persona prose from the computed payload. Deterministic fallbacks on
    any failure — the report never blocks on the LLM."""
    fallback = {
        "regime_lines": [f"Regime {payload['regime']['verdict']} — "
                         + "; ".join(payload["regime"]["drivers"][:3])],
        "cards": {i["symbol"]: _det_card(i) for i in payload["book"]},
        "bear_case": "LLM unavailable — bear case not written. The numbers above stand on their own.",
        "tilt_check": "LLM unavailable.",
        "mind_changer": ("Distribution-day count crossing 6/25 or a VIX "
                         "close over 30 flips the verdict a notch down."),
        "provider": "deterministic",
    }
    try:
        import json

        import llm
        if not llm.is_enabled():
            return fallback
        resp = llm.chat(
            "PAYLOAD:\n" + json.dumps(payload, default=str)
            + "\n\n" + _PROSE_SCHEMA_HINT,
            system=PERSONA, provider="anthropic", json_only=True,
            max_tokens=2500, temperature=0.4, timeout=180)
        parsed = resp.get("parsed") if resp.get("ok") else None
        if not isinstance(parsed, dict) or "cards" not in parsed:
            return fallback
        parsed["provider"] = resp.get("provider")
        for k, v in fallback.items():
            parsed.setdefault(k, v)
        # Models sometimes return the 5-line bear case as a JSON list even
        # when asked for a string; the FE renders strings.
        for k in ("bear_case", "tilt_check", "mind_changer"):
            if isinstance(parsed.get(k), list):
                parsed[k] = "\n".join(str(x) for x in parsed[k])
        if isinstance(parsed.get("regime_lines"), str):
            parsed["regime_lines"] = [parsed["regime_lines"]]
        cards = parsed.get("cards")
        if isinstance(cards, dict):
            parsed["cards"] = {k: ("\n".join(str(x) for x in v)
                                   if isinstance(v, list) else str(v))
                               for k, v in cards.items()}
        return parsed
    except Exception as exc:
        log.warning("desk: LLM prose failed: %s", exc)
        return fallback


def _det_card(idea: dict) -> str:
    plan = idea.get("plan") or {}
    return (f"{idea.get('module')}-module setup, score {idea.get('score')}"
            f" (parts {idea.get('parts')}). Entry {plan.get('entry')},"
            f" stop {plan.get('stop')}, T1 {plan.get('target1')}"
            f" ({plan.get('rr')}R). Invalidation: a close below the stop"
            f" or loss of the setup that put it on this list.")


# ── the run ────────────────────────────────────────────────────────────────
def build(owner: Optional[str] = None) -> dict:
    """Assemble the full report doc (no side effects — run() persists)."""
    from portfolio.alerts import _resolve_owner
    from sepa import earnings_watch
    from sepa import market_regime as mr
    from sepa import scanner

    owner = owner or _resolve_owner()
    scan = scanner.load_latest()
    rows = (scan or {}).get("all_results") or []
    regime_raw = mr.regime(scan_rows=rows)
    verdict = scoring.regime_verdict(regime_raw)
    throttle = verdict["throttle"]

    earn_map = (earnings_watch.bulk_map() or {}).get("map") or {}
    swing, cuts = _swing_candidates(rows, earn_map)
    level = _at_the_level()
    positions = _position_ideas()
    account = _account(owner)

    book = [c for c in swing if c["score"] >= scoring.REPORT_MIN]
    book = book[:throttle["max_ideas"]]
    watch = [c for c in swing if c not in book][:5]
    for idea in book:
        plan = idea["plan"]
        idea["size"] = scoring.position_size(
            account.get("value"), plan["entry"], plan["stop"],
            size_factor=throttle["size_factor"])
        days_to = (earn_map.get(idea["symbol"]) or {}).get("days_to")
        if days_to is not None:
            idea["earnings_in_days"] = days_to

    ctx = _context_blocks([i["symbol"] for i in book])

    today = _today_et()
    # before_date so a same-day re-run still grades YESTERDAY's book, not
    # the doc this very run upserted an hour ago.
    prior = latest_report(before_date=today)
    carried = grade_prior_book(prior)

    payload = {
        "date": today,
        "params": {"risk_pct_per_trade": scoring.RISK_PCT_PER_TRADE,
                   "max_positions": scoring.MAX_POSITIONS,
                   "instruments": "common stock only",
                   "exclusions": f"price < ${scoring.MIN_PRICE:g}, "
                                 f"ADV < {scoring._fmt_dollars(scoring.MIN_DOLLAR_VOL)}, "
                                 f"earnings inside {scoring.EARNINGS_WINDOW_DAYS}d, "
                                 "weak/declining sales"},
        "regime": {**verdict,
                   "score": regime_raw.get("score"),
                   "narrative": (regime_raw.get("narrative") or {}).get("headline")
                   if isinstance(regime_raw.get("narrative"), dict) else None},
        "book": book, "watch": watch, "cuts": cuts,
        "at_the_level": level, "position_ideas": positions,
        "account": account, "context": ctx, "carried_forward": carried,
        "scan_generated_at": (scan or {}).get("generated_at"),
        "unavailable": ["economic calendar (CPI/FOMC dates) — not wired",
                        "float / short interest — no provider",
                        "insider transactions — no provider"],
        "nothing_qualifies": not book,
    }
    payload["prose"] = _prose(payload)
    payload["disclaimer"] = ("Generated from the app's own scans. Not "
                             "investment advice — verify independently "
                             "before risking capital.")
    return payload


# ── persistence + delivery ─────────────────────────────────────────────────
def _coll():
    try:
        from portfolio.store import _get_db
        return _get_db().desk_reports
    except Exception:                                          # pragma: no cover
        return None


def latest_report(before_date: Optional[str] = None) -> Optional[dict]:
    coll = _coll()
    if coll is None:
        return None
    try:
        q = {"date": {"$lt": before_date}} if before_date else {}
        doc = coll.find_one(q, sort=[("date", -1)])
        if doc:
            doc.pop("_id", None)
        return doc
    except Exception as exc:
        log.warning("desk: latest_report read failed: %s", exc)
        return None


def run(*, push: bool = True) -> dict:
    """Cron entrypoint: build, store (one doc per ET day, re-runs
    overwrite), push a todo_reminder that the desk is ready."""
    report = build()
    coll = _coll()
    if coll is not None:
        try:
            coll.update_one({"date": report["date"]}, {"$set": report},
                            upsert=True)
        except Exception as exc:
            log.warning("desk: store failed: %s", exc)
    if push:
        try:
            from portfolio.alerts import _resolve_owner
            from push import sender as _push
            n = len(report["book"])
            verdict = report["regime"]["verdict"]
            body = (f"{verdict} — nothing qualifies today"
                    if report["nothing_qualifies"]
                    else f"{verdict} — {n} idea{'s' if n != 1 else ''}, "
                         f"top: {report['book'][0]['symbol']} "
                         f"{report['book'][0]['score']:g}")
            _push.send_to_user(_resolve_owner(), {
                "title": "🧠 Morning desk report",
                "body": body,
                "data": {"url": "/desk"},
            }, kind="todo_reminder")
        except Exception as exc:
            log.warning("desk: push failed: %s", exc)
    log.info("desk: %s verdict=%s book=%d cuts=%d carried=%d",
             report["date"], report["regime"]["verdict"],
             len(report["book"]), len(report["cuts"]),
             len(report["carried_forward"]))
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run()
