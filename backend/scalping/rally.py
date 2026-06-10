"""Confirmed-bullish rally screen (Ajay 2026-06-10: "I want it to identify
confirmed bullish stocks that can rally a few $") — the on-demand 🚀 scan on
the Scalping page.

Three measured ingredients, no folklore:
  1. CONFIRMED BULLISH — the name either confirmed a bullish daily pattern
     within the in-the-moment window (today/yesterday, close above its line)
     or clears the FULL Minervini buy gate right now (is_buyable). A bearish
     last-bar candle read disqualifies — this is a bullish-only screen.
  2. ROOM TO RALLY IN DOLLARS — typical daily range = price × ADR%. A $9
     stock with 5% ADR moves ~$0.45/day; it cannot "rally a few $" no matter
     how pretty the chart. Default gate: ≥ $2/day typical range.
  3. LIVE TAPE CHECK — the top names get the 5-min tape read (pivot/pattern
     line/VWAP/OR) so a REJECTION/BREAKDOWN right now is visible before entry.

HONESTY: the $ range is ADR arithmetic — what the name TYPICALLY traverses in
a day, not a prediction that it will, nor direction. Confirmation is a daily-
close fact; same-day confirmations are provisional until today's close.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("scalping.rally")

MIN_DOLLAR_MOVE = 2.0      # CONFIGURED — "a few $" needs a real per-share range
VERDICT_CAP = 60           # bounded fresh-verdict compute (~10ms/symbol)
TAPE_TOP_N = 8             # live tape reads only for the leaders (intraday loads)


def candidates(profile: str = "aggressive",
               min_dollar_move: float = MIN_DOLLAR_MOVE,
               with_tape: bool = True) -> dict:
    # Pool: today's day-tradeable universe + every current buyable from the scan
    # (a buyable mega-cap with a $6 daily range belongs here even if it isn't a
    # top-ADR "mover").
    pool: dict = {}
    try:
        from daytrading.universe import day_trade_universe
        for n in (day_trade_universe(profile=profile, limit=120) or {}).get("names") or []:
            if n.get("symbol"):
                pool[n["symbol"]] = n
    except Exception as exc:
        log.warning("rally pool universe failed: %s", exc)
    try:
        from sepa import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            sym = r.get("symbol")
            if (not sym or r.get("is_etf") or sym in pool
                    or not r.get("is_buyable")
                    or not r.get("adr_pct") or not r.get("last_close")):
                continue
            pool[sym] = {"symbol": sym, "adr_pct": float(r["adr_pct"]),
                         "last_close": float(r["last_close"]),
                         "rs_rank": r.get("rs_rank")}
    except Exception as exc:
        log.warning("rally pool buyables failed: %s", exc)

    # Dollar-range gate BEFORE the verdict cap so big-range names survive it.
    rows = []
    for n in pool.values():
        adr, px = n.get("adr_pct"), n.get("last_close")
        if not adr or not px:
            continue
        rng = float(px) * float(adr) / 100.0
        if rng >= min_dollar_move:
            rows.append({**n, "dollar_range": round(rng, 2)})
    rows.sort(key=lambda n: -n["dollar_range"])
    rows = rows[:VERDICT_CAP]

    from patterns import scan as pscan
    vmap = {v["symbol"]: v for v in
            (pscan.verdicts_for([n["symbol"] for n in rows]) or {}).get("verdicts") or []}

    out = []
    for n in rows:
        v = vmap.get(n["symbol"]) or {}
        matches = v.get("matches") or []
        conf = next((m for m in matches if m.get("status") == "confirmed"), None)
        buyable = bool((v.get("sepa") or {}).get("is_buyable"))
        if not conf and not buyable:
            continue                       # not CONFIRMED bullish — out
        formations = (v.get("candles") or {}).get("formations") or []
        if any(f.get("read") == "bearish_warning" for f in formations):
            continue                       # bearish last-bar read disqualifies
        why = []
        if conf:
            why.append(f"{conf['pattern'].replace('_', ' ')} confirmed "
                       f"{'today' if conf.get('bars_since_confirm') == 0 else 'yesterday'}")
        if buyable:
            why.append("clears the full Minervini buy gate")
        out.append({
            "symbol": n["symbol"], "price": n["last_close"],
            "adr_pct": n.get("adr_pct"), "dollar_range": n["dollar_range"],
            "rs_rank": n.get("rs_rank"),
            "confirmed_pattern": conf["pattern"] if conf else None,
            "confirmed_today": bool(conf and conf.get("bars_since_confirm") == 0),
            "neckline": conf.get("neckline") if conf else None,
            "target": conf.get("target") if conf else None,
            "stop": conf.get("stop") if conf else None,
            "is_buyable": buyable, "why": why,
            "bullish_candle": next((f["name"] for f in formations
                                    if f.get("read") == "bullish_reversal_setup"), None),
        })

    # Confluence first (confirmed pattern AND buyable), then biggest $ range.
    out.sort(key=lambda c: (0 if (c["confirmed_pattern"] and c["is_buyable"])
                            else 1 if c["confirmed_pattern"] else 2,
                            -c["dollar_range"]))

    if with_tape:
        from . import sepa_watch
        for c in out[:TAPE_TOP_N]:
            try:
                r = sepa_watch.tape_read(c["symbol"])
                if r.get("ok") and r.get("read"):
                    c["tape_state"] = r["read"]["state"]
                    c["tape_verdict"] = r["read"]["verdict"]
            except Exception as exc:
                log.debug("rally tape read %s failed: %s", c["symbol"], exc)

    return {
        "generated_at": int(time.time()), "profile": profile,
        "min_dollar_move": min_dollar_move,
        "n_pool": len(rows), "n_candidates": len(out), "candidates": out,
        "criteria": (f"confirmed bullish (pattern ✓ ≤1d or full buy gate) · no bearish "
                     f"last-bar candle · typical daily range ≥ ${min_dollar_move:.0f} "
                     f"(price × ADR)"),
        "disclaimer": (
            "The $ range is what the name TYPICALLY traverses in a day (price × "
            "ADR) — capacity, not a prediction, and not direction. Same-day "
            "confirmations are provisional until the close. Educational, not advice."),
    }
