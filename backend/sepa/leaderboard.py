"""SEPA rank leaderboard — day-level "honourable mentions" for the portfolio page.

Built from scan history (sepa.history): across every scan in the lookback window
it re-ranks each run by score, then per symbol computes where it has been —
best / worst / current rank, how CONSISTENTLY it sat near the top (persistence),
and how VOLATILE its rank was (range). The point (user 2026-06-02): surface the
names that have been scoring high *before* they break out — "if BB was in
honourable mentions I'd have caught the breakout ahead of time" — plus flag the
volatile movers (BB went #1 → #100 → #1).

Complements `top_picks` (what's buyable RIGHT NOW) with "who's been strong, and
who's primed." Reads the same history other tabs use; cached briefly.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from . import history, scanner

LOOKBACK_DAYS = 14          # ≈ 10 business days
TOP_TIER = 20               # "scored high" = ranked within the top this many
VOLATILE_RANGE = 30         # best→worst rank spread that counts as "volatile"
MAX_DAYS = 30               # cap trading days processed per call (cost guard)

_cache: dict = {}
_CACHE_TTL_SEC = 180


def _rank_runs(db, cutoff: int) -> list[dict]:
    """ONE scan per trading day (the latest that day), each as {symbol: rank} by
    score desc. Day-LEVEL on purpose: persistence then means "% of DAYS in the
    top", which is what "how often is it on top this week" actually asks. Ranking
    by raw scans instead over-weighted the last few dense-intraday days (recent
    days have ~10 scans each, so the most-recent-N-scans window only spanned ~3
    days) and dropped week-strong names — BB read 28% over recent scans but 88%
    over recent DAYS (top-20 on 7 of 8 days). 2026-06-02."""
    runs = list(db.scan_runs.find({"generated_at": {"$gte": cutoff}},
                                   {"generated_at": 1, "date_et": 1})
                .sort("generated_at", 1))                  # oldest first
    by_date: dict = {}
    for r in runs:
        if r.get("date_et"):
            by_date[r["date_et"]] = r                      # last per date = latest that day
    daily = [by_date[d] for d in sorted(by_date)][-MAX_DAYS:]
    out = []
    for run in reversed(daily):                            # newest first (aggregate uses ranks[0] = current)
        snaps = list(db.candidate_snapshots.find(
            {"scan_run_id": run["_id"]}, {"symbol": 1, "score": 1}))
        snaps = [s for s in snaps if s.get("score") is not None]
        if not snaps:
            continue
        snaps.sort(key=lambda s: -s["score"])
        out.append({
            "generated_at": run["generated_at"],
            "rank": {s["symbol"]: i + 1 for i, s in enumerate(snaps)},
            "score": {s["symbol"]: s["score"] for s in snaps},
        })
    return out  # newest first


def _drop_reason(stage, dist_days, accum) -> str:
    """Human 'why the rank slipped', from the current scan's weakening signals,
    most-severe first: a Stage downgrade > a distribution cluster (book p.76) >
    volume turning, else a relative ease vs stronger peers. Pure → unit-testable.
    Only meaningful for names whose rank fell well below their best."""
    if stage is not None and stage != 2:
        return f"Stage {stage} — advance stalling"
    if dist_days is not None and dist_days >= 4:
        return f"{dist_days} distribution days — institutions selling"
    if accum == "distributing":
        return "volume distributing — supply > demand"
    if accum == "neutral":
        return "demand cooled — volume neutral"
    return "score eased vs stronger peers"


def _coiling(ready: bool, buyable: bool, vcp: dict, vol: dict) -> bool:
    """Pre-breakout 'coiling' = setup ready, NOT yet broken out, in a tight VCP
    base with volume drying up (book pp.198-205) — the spring before the move."""
    if not (ready and not buyable and vcp.get("has_base")):
        return False
    drying = bool(vcp.get("volume_drying")) or (
        vol.get("vol_dryup") is not None and vol.get("vol_dryup") < 0.85)
    fc = vcp.get("final_contraction_pct")
    tight = fc is not None and fc <= 6.0
    return bool(drying and tight)


def _near_r1(close, targets: list):
    """(near_r1, r1_price, dist_pct): is price approaching its first R-target?
    'near' = within ~4% below R1 (or just past it). dist +ve = R1 still above."""
    r1 = next((t.get("price") for t in (targets or []) if t.get("label") == "R1"), None)
    if not (r1 and close):
        return False, r1, None
    dist = round((r1 / close - 1) * 100, 1)
    return (-1.0 <= dist <= 4.0), r1, dist


def aggregate(runs: list[dict], live: dict, n: int) -> list[dict]:
    """Pure: collapse ranked runs (newest first) + a live-status map into the
    sorted leaderboard rows. Separated from Mongo so it's unit-testable."""
    agg: dict[str, dict] = {}
    for run in runs:                                      # newest first
        for sym, rk in run["rank"].items():
            a = agg.setdefault(sym, {"ranks": [], "scores": []})
            a["ranks"].append(rk)
            a["scores"].append(run["score"][sym])

    rows = []
    for sym, a in agg.items():
        ranks = a["ranks"]
        appearances = len(ranks)
        best, worst = min(ranks), max(ranks)
        avg = round(sum(ranks) / appearances, 1)
        persistence = round(100.0 * sum(1 for r in ranks if r <= TOP_TIER) / appearances)
        cur = live.get(sym) or {}
        buyable = bool(cur.get("is_buyable"))
        ready = bool(cur.get("setup_ready"))
        flag = ("breaking_out" if buyable else "primed" if ready
                else "volatile" if (worst - best) >= VOLATILE_RANGE else "steady")
        vol = cur.get("volume") or {}
        stage = cur.get("stage")
        stage = stage.get("stage") if isinstance(stage, dict) else stage
        last_vol = vol.get("last_vol")
        avg50 = vol.get("avg_vol_50")
        close = cur.get("last_close")
        dist_days = vol.get("distribution_days_25")
        accum = vol.get("accumulation_strength")
        dropped = ranks[0] > best + 5            # rank fell well below its best
        vcp = cur.get("vcp") or {}
        targets = ((cur.get("entry_exit") or {}).get("exit") or {}).get("targets") or []
        coiling = _coiling(ready, buyable, vcp, vol)
        near_r1, r1_price, dist_r1 = _near_r1(close, targets)
        rows.append({
            "symbol":        sym,
            "name":          cur.get("name"),
            "current_rank":  ranks[0],            # newest run
            "current_score": a["scores"][0],
            "rs_rank":       cur.get("rs_rank"),
            "best_rank":     best,
            "worst_rank":    worst,
            "avg_rank":      avg,
            "rank_range":    worst - best,        # volatility
            "appearances":   appearances,
            "persistence_pct": persistence,       # % of scans in the top TOP_TIER
            "status":        "buyable" if buyable else "ready" if ready else "watch",
            "flag":          flag,
            # Enrichment (Ajay 2026-06-03 "add total volume + why these went down"):
            "volume":        last_vol,                                          # today's share volume
            "dollar_vol":    int(last_vol * close) if (last_vol and close) else None,
            "vol_x":         round(last_vol / avg50, 2) if (last_vol and avg50) else None,  # relative vol
            "stage":         stage,
            "distribution_days": dist_days,
            "accumulation":  accum,
            # Minervini Ch.8 earnings quality (Code 33 / margins / red flags,
            # book p.140-159) — passed through from the live candidate so the
            # leaderboard can show the chip. None for names whose scan wasn't
            # catalyst-enriched (same coverage as CANSLIM). The RANKING already
            # reflects it via current_score (scanner folds eq into the score).
            "earnings_quality": (cur.get("fundamentals") or {}).get("earnings_quality"),
            "drop_reason":   _drop_reason(stage, dist_days, accum) if dropped else None,
            # Coiling (pre-breakout spring) + near first R-target (Ajay 2026-06-03)
            "coiling":       coiling,
            "near_r1":       near_r1,
            "r1_price":      r1_price,
            "dist_to_r1_pct": dist_r1,
        })

    # Honourable mentions: most consistently high first; ties → best rank.
    rows.sort(key=lambda r: (-r["persistence_pct"], r["avg_rank"], r["best_rank"]))
    return rows[:n]


def _stage_of(r: dict):
    st = r.get("stage")
    return st.get("stage") if isinstance(st, dict) else st


def _why_not_buyable(r: dict) -> str:
    """Plain-English reason a QUALIFIED name (passes the trend template +
    liquidity, book p.79) is not yet a clean same-day buy — so the watchlist
    says what to wait FOR, not just 'no'."""
    stg = _stage_of(r)
    if stg != 2:
        return f"Stage {stg} — wait for a Stage-2 advance" if stg else "Not Stage 2 yet"
    if not r.get("setup_ready"):
        return "Stage 2 · strong RS — waiting on a pivot/setup trigger"
    return "Qualified — not a same-day entry"


def _buyable_note(r: dict) -> str:
    """Note for a name that clears the full buy gate. If the SAME row ALSO carries
    an active distribution/exit sell-signal (climax run, stop breach, below the
    50/200-day), it is NOT a clean fresh entry: Minervini does not initiate into a
    climax/parabolic (Ch.13 climax tops; p.203 — buy AT the pivot, never chasing an
    extended run). Reconciles 'Buyable now' with the position card's REDUCE so the
    same stock can't read 'clean entry' AND 'trim' at once (Ajay 2026-06-08)."""
    ss = r.get("sell_signals") or {}
    if ss.get("action") in ("REDUCE", "SELL"):
        sigs = ss.get("signals") or {}
        if sigs.get("climax_run_25pct_in_3w"):
            g = ss.get("climax_15d_gain_pct")
            gtxt = f"+{round(g)}%/15d" if isinstance(g, (int, float)) else "climax"
            return f"⚠ clears the gate BUT climax run {gtxt} — don't chase (Ch.13)"
        if sigs.get("stop_loss_breached"):
            return "⚠ clears the gate BUT stop breached — manage, don't add"
        if sigs.get("close_below_200ma"):
            return "⚠ clears the gate BUT closed below the 200-day — caution"
        if sigs.get("close_below_50ma_on_high_vol"):
            return "⚠ clears the gate BUT below the 50-day on volume — caution"
        return "⚠ clears the gate BUT flagged for reduction — don't chase (Ch.13)"
    # EXTENDED (no sell-signal needed): the raw is_buyable gate can fire on a LATE
    # pocket pivot while price is already well past the pivot (KNX: is_buyable but
    # +22.9% past). Minervini buys AT the pivot, not chasing (p.203) — so flag it
    # missed/extended rather than "clean entry" (Ajay 2026-06-08, KNX case).
    ee = r.get("entry_exit") or {}
    if (ee.get("entry") or {}).get("status") == "missed_extended":
        pivot = (r.get("entry_setup") or {}).get("pivot")
        cur = r.get("last_close")
        if pivot and cur and pivot > 0:
            return f"⚠ extended — missed, don't chase (+{round((cur / pivot - 1) * 100)}% past pivot)"
        return "⚠ extended past the pivot — missed, don't chase"
    return "Clean entry — clears the full buy gate"


def resilient_picks(latest: dict, macro_market: Optional[dict], k: int = 5) -> dict:
    """Names that still pass the SEPA gate while the macro backdrop is risky
    (Ajay 2026-06-04: 'if these are risky due to macro, pull the top 5 that
    qualify all the other criteria'). Two honest tiers, never blurred:
      • 'buyable'  — clears the FULL buy gate right now (scanner `is_buyable`:
        Stage 2 + setup + trend + liquidity + volume-confirmed breakout). Clean
        entries — EXCEPT a name that also carries an active sell-signal (climax
        run / stop breach / below the 50-200d) is kept but flagged "don't chase"
        via `_buyable_note`, so it can't read clean-entry AND reduce at once.
      • 'qualified'— when nothing is a clean buy (risk-off), the closest names
        that pass the qualifier gate (trend template + liquidity, book p.79),
        each tagged with what's holding it out of a buy.
    Macro is an OVERLAY here, not a gate — `is_buyable` never factored macro in —
    so this answers 'what still qualifies technically, regardless of the
    backdrop', with each pick's own macro read attached for context."""
    rows = latest.get("all_results") or latest.get("candidates") or []

    _mrisk = None
    if macro_market:
        try:
            from . import macro_risk as _mrisk
        except Exception:
            _mrisk = None

    def pack(r: dict, why: str) -> dict:
        item = {
            "symbol":  r.get("symbol"),
            "name":    r.get("name"),
            "score":   r.get("score"),
            "rs_rank": r.get("rs_rank"),
            "stage":   _stage_of(r),
            "why":     why,
        }
        if _mrisk is not None:
            try:
                item["macro_risk"] = _mrisk.score_stock(r.get("symbol", ""), macro_market)
            except Exception:
                pass
        return item

    buyable = sorted((r for r in rows if r.get("is_buyable")),
                     key=lambda r: r.get("score") or 0, reverse=True)
    if buyable:
        return {"tier": "buyable", "count": len(buyable),
                "picks": [pack(r, _buyable_note(r)) for r in buyable[:k]]}

    cand = sorted((r for r in rows if r.get("is_candidate")),
                  key=lambda r: r.get("score") or 0, reverse=True)
    return {"tier": "qualified", "count": len(cand),
            "picks": [pack(r, _why_not_buyable(r)) for r in cand[:k]]}


def leaderboard(n: int = 12, lookback_days: int = LOOKBACK_DAYS) -> dict:
    key = (n, lookback_days)
    hit = _cache.get(key)
    if hit and time.time() - hit["ts"] < _CACHE_TTL_SEC:
        return hit["data"]

    db = history._get_db()
    empty = {"leaders": [], "scans_in_window": 0, "lookback_days": lookback_days}
    if db is None:
        return empty

    cutoff = int(time.time()) - lookback_days * 86400
    runs = _rank_runs(db, cutoff)
    if not runs:
        return empty

    latest = scanner.load_latest() or {}
    live = {r.get("symbol"): r
            for r in (latest.get("all_results") or latest.get("candidates") or [])}

    leaders = aggregate(runs, live, n)

    # Macro-risk overlay (Ajay 2026-06-04): per-name macro/geopolitical risk from
    # the cached market read — pure + cheap, never blocks. Surfaces on the
    # Leaderboard + Portfolio lists alongside the SEPA score.
    macro_market = None
    try:
        from . import macro_risk as _mrisk
        macro_market = _mrisk.get_market()
        if macro_market:
            for row in leaders:
                row["macro_risk"] = _mrisk.score_stock(row.get("symbol", ""), macro_market)
    except Exception as exc:
        logging.getLogger("sepa.leaderboard").warning("macro_risk overlay failed: %s", exc)

    data = {
        "leaders":         leaders,
        "buyable_despite_macro": resilient_picks(latest, macro_market),
        "scans_in_window": len(runs),
        "lookback_days":   lookback_days,
        "top_tier":        TOP_TIER,
        "macro_market":    macro_market,
    }
    _cache[key] = {"data": data, "ts": time.time()}
    return data
