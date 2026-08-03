"""OpEx panel — options-expiration mechanics for one ticker.

For the nearest expiration we compute:
  - the expiration date + type (weekly / monthly 3rd-Friday / quad-witching) + DTE
  - the MAX-PAIN strike (gamma-agnostic, OI-only) — the classic into-expiry magnet
  - a DEALER-GAMMA read: net GEX → "pinning" (vol-suppressing) vs "amplifying"
    (vol-expanding), plus the call/put gamma walls that bracket the range.

HONESTY — this is a TENDENCY into expiration, not a guarantee, and a swing
trader should treat a pin as a reason a breakout may STALL into expiry, not a
tradeable signal on its own (confirm with the SEPA setup). Two specific honesty
points the design review forced:

  1. The net-GEX SIGN RULE — every call's OI is signed +gamma to the dealer,
     every put's OI is signed -gamma — is the blind SqueezeMetrics/SpotGamma
     heuristic applied to ALL open interest. It is most defensible on index/ETF
     (SPY/QQQ) and can literally INVERT on single-name momentum leaders (where
     customers are net long calls). So we down-weight it on single names and
     always label it an approximation of an unobservable dealer book.
  2. Max-pain and the gamma pin are statistical drifts under normal conditions;
     an earnings print / guidance / M&A / macro shock overwhelms dealer hedging
     entirely.

Pure functions (classify_expiration / max_pain / net_gex_and_walls) carry all
the logic and unit-test with no network; compute_opex fetches the chain and
delegates. Reuses the same Massive snapshot shape as options/soir.py.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Optional

from massive_keys import options_key

log = logging.getLogger("options.opex")

# Index/ETF tickers where the blind GEX sign rule is most defensible. On single
# names it can invert, so we flag lower reliability there.
INDEX_LIKE = frozenset({"SPY", "QQQ", "IWM", "DIA", "SPX", "NDX", "RUT", "VIX"})

CONTRACT_MULTIPLIER = 100


# ---------------------------------------------------------------------------
# PURE LOGIC — no network
# ---------------------------------------------------------------------------
def classify_expiration(date_str: str, today: date) -> dict:
    """Classify an expiry from its date alone (no external calendar).

    The 3rd Friday of any month always falls on the 15th–21st. Quad-witching =
    a 3rd-Friday in Mar/Jun/Sep/Dec (index futures+options+stock options+single-
    stock futures all expire → strongest pin tendency)."""
    d = date.fromisoformat(date_str)
    is_friday = d.weekday() == 4
    is_third_friday = is_friday and 15 <= d.day <= 21
    if is_third_friday and d.month in (3, 6, 9, 12):
        etype = "quad_witching"
    elif is_third_friday:
        etype = "monthly"
    else:
        etype = "weekly"
    return {"expiration_date": date_str, "expiration_type": etype,
            "days_to_expiry": (d - today).days}


def max_pain(call_oi: dict, put_oi: dict, spot: Optional[float] = None) -> Optional[dict]:
    """Max-pain strike: the listed strike S minimizing the total intrinsic value
    owed to option holders if price pinned to S at expiry. Gamma-agnostic, OI is
    the only weight. Returns None on an empty or all-zero-OI grid."""
    strikes = sorted(set(call_oi) | set(put_oi))
    if not strikes:
        return None
    total_oi = sum(call_oi.values()) + sum(put_oi.values())
    if total_oi <= 0:
        return None

    best_s = None
    best_total = None
    second_total = None
    for s in strikes:
        total = 0.0
        for k in strikes:
            if k < s:
                total += (call_oi.get(k, 0) or 0) * (s - k)
            elif k > s:
                total += (put_oi.get(k, 0) or 0) * (k - s)
        total *= CONTRACT_MULTIPLIER
        if best_total is None or total < best_total:
            second_total = best_total
            best_total, best_s = total, s
        elif second_total is None or total < second_total:
            second_total = total

    # soft/ambiguous pin: runner-up within 1% of the minimum
    tie = (second_total is not None and best_total is not None
           and best_total > 0 and abs(second_total - best_total) <= 0.01 * best_total)
    out = {
        "max_pain_strike": best_s,
        "max_pain_total_dollars": round(best_total, 2) if best_total is not None else None,
        "strike_count": len(strikes),
        "total_oi": int(total_oi),
        "max_pain_tie": bool(tie),
    }
    if spot:
        out["pct_from_spot"] = round((best_s / spot - 1) * 100, 2)
    return out


def net_gex_and_walls(rows: list[dict], spot: Optional[float]) -> Optional[dict]:
    """Dealer gamma exposure for one expiry from per-strike rows.

    rows: [{strike, type ('call'|'put'), gamma (float|None), oi (int)}].

    SIGN RULE (pinned — do not silently flip): calls add +gamma·OI, puts add
    −gamma·OI (dealer long call-gamma / short put-gamma, the SqueezeMetrics
    heuristic). Net > 0 → dealers net long gamma → sell rips / buy dips →
    vol-suppressing = PINNING. Net < 0 → AMPLIFYING. Scale 100·0.01·spot² gives
    $ of hedging flow per 1% move. Returns None when spot or all gammas missing.
    """
    if not spot or spot <= 0:
        return None
    scale = CONTRACT_MULTIPLIER * 0.01 * spot * spot
    per_strike: dict[float, float] = {}
    covered_oi = 0
    total_oi = 0
    for r in rows:
        oi = r.get("oi") or 0
        total_oi += oi
        g = r.get("gamma")
        if g is None:
            continue
        covered_oi += oi
        sign = 1.0 if r.get("type") == "call" else -1.0   # PIN: call=+, put=−
        per_strike[r["strike"]] = per_strike.get(r["strike"], 0.0) + sign * float(g) * oi
    if not per_strike:
        return None

    net = sum(per_strike.values()) * scale

    # Walls bracket the expected range (NOT price targets): the call wall is the
    # largest positive-gamma strike at/above spot (upper cap); the put wall the
    # largest |negative|-gamma strike at/below spot (support).
    call_wall = max((k for k, v in per_strike.items() if k >= spot and v > 0),
                    key=lambda k: per_strike[k], default=None)
    put_wall = min((k for k, v in per_strike.items() if k <= spot and v < 0),
                   key=lambda k: per_strike[k], default=None)
    # dominant magnet = largest absolute per-strike gamma concentration
    magnet = max(per_strike, key=lambda k: abs(per_strike[k]), default=None)

    # Gamma FLIP (zero-gamma level, added 2026-07-17): walk strikes ascending
    # accumulating per-strike net gamma; the flip is where the running sum
    # changes sign, linearly interpolated between the bracketing strikes.
    # Below the flip dealers are net short gamma (moves get amplified); above
    # it net long (moves get dampened). No crossing -> None (profile is
    # one-sided; the regime field already says which side).
    flip = None
    strikes_sorted = sorted(per_strike)
    cum = 0.0
    prev_cum = 0.0
    for i, k in enumerate(strikes_sorted):
        prev_cum = cum
        cum += per_strike[k]
        if i > 0 and prev_cum != 0 and (prev_cum < 0) != (cum < 0):
            k_prev = strikes_sorted[i - 1]
            frac = abs(prev_cum) / (abs(prev_cum) + abs(per_strike[k]))
            flip = round(k_prev + frac * (k - k_prev), 2)
            break

    # Top gamma nodes (the "key nodes" for the board/setup lens): largest
    # |dealer gamma| strikes, dollar-scaled like net_gex_dollars.
    top_nodes = [
        {"strike": k, "gex_dollars": round(per_strike[k] * scale, 0)}
        for k in sorted(per_strike, key=lambda s: abs(per_strike[s]),
                        reverse=True)[:6]
    ]

    return {
        "net_gex_dollars": round(net, 0),
        "regime": "pinning" if net > 0 else "amplifying",
        "call_wall": call_wall,
        "put_wall": put_wall,
        "magnet_strike": magnet,
        "flip_strike": flip,
        "top_nodes": top_nodes,
        "oi_coverage_pct": round(100 * covered_oi / total_oi, 1) if total_oi else 0.0,
    }


def _bs_vanna(spot: float, strike: float, iv: float, dte_days: int) -> Optional[float]:
    """Black-Scholes vanna (dDelta/dVol, per 1.00 of vol, r≈0). Same for calls
    and puts under BS. Massive's snapshot has no vanna field, so this is ALWAYS
    derived from implied_volatility — VEX is one more modelling step removed
    from the tape than GEX and should be read with matching humility.
    Returns None on degenerate inputs."""
    try:
        t = max(dte_days, 1) / 365.0
        if spot <= 0 or strike <= 0 or iv <= 0:
            return None
        sig = iv if iv < 5 else iv / 100.0   # accept fraction or percent
        rt = sig * math.sqrt(t)
        d1 = (math.log(spot / strike) + 0.5 * sig * sig * t) / rt
        d2 = d1 - rt
        nprime = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
        return -nprime * d2 / sig
    except Exception:
        return None


def net_vex(rows: list[dict], spot: Optional[float]) -> Optional[dict]:
    """Dealer VANNA exposure ("VEX") for one expiry.

    rows: [{strike, type ('call'|'put'), vanna (float|None), oi (int)}].

    NAMING HONESTY: retail tools disagree on what "VEX" means (some say vega
    exposure). Here VEX = net dealer VANNA — how much dealer DELTA moves when
    IV moves — the GEXBot/SpotGamma-style usage, because that's the one with a
    tradeable mechanic: with net vanna POSITIVE, FALLING IV forces dealers to
    BUY stock (the "vanna tailwind" behind calm grind-up rallies); NEGATIVE
    means falling IV forces dealer SELLING. Sign rule mirrors net_gex_and_walls
    (call=+, put=−, the same blind dealer-book heuristic — same caveats).
    Scale: $ of dealer delta per 1 vol-point change. None when spot/all vanna
    missing."""
    if not spot or spot <= 0:
        return None
    scale = CONTRACT_MULTIPLIER * 0.01 * spot
    total = 0.0
    covered_oi = 0
    total_oi = 0
    for r in rows:
        oi = r.get("oi") or 0
        total_oi += oi
        v = r.get("vanna")
        if v is None:
            continue
        covered_oi += oi
        sign = 1.0 if r.get("type") == "call" else -1.0   # mirror the GEX rule
        total += sign * float(v) * oi
    if not covered_oi:
        return None
    dollars = round(total * scale, 0)
    return {
        "net_vex_dollars": dollars,
        "read": ("falling IV = dealer buying (vanna tailwind)" if dollars > 0
                 else "falling IV = dealer selling (vanna headwind)" if dollars < 0
                 else "vanna flat"),
        "oi_coverage_pct": round(100 * covered_oi / total_oi, 1) if total_oi else 0.0,
    }


def best_case(spot: Optional[float], gamma: Optional[dict],
              vex: Optional[dict]) -> Optional[dict]:
    """The plain-English 'best case' read for the Setup tab (Ajay 2026-07-17:
    "show me what is the best case possibility in the setup"). Pure — derives
    everything from the gamma/vex blocks; never invents levels. None when
    there's no gamma read at all."""
    if not spot or not gamma:
        return None
    flip = gamma.get("flip_strike")
    cw = gamma.get("call_wall")
    pw = gamma.get("put_wall")
    net = gamma.get("net_gex_dollars") or 0

    def _pct(level):
        return round((level / spot - 1) * 100, 1) if level else None

    above_flip = flip is None or spot >= flip
    if net > 0 and above_flip:
        bias = "bullish"
        headline = "Dealers are pinning — they buy dips here."
        path = (f"Best case: grind up toward the call wall ${cw:g} "
                f"({_pct(cw):+g}%)." if cw else
                "Best case: steady grind higher — no call wall overhead in "
                "this expiry.")
        risk = (f"Loses the flip at ${flip:g} ({_pct(flip):+g}%) and dealer "
                f"hedging starts AMPLIFYING moves instead." if flip else
                (f"Put wall ${pw:g} ({_pct(pw):+g}%) is the downside "
                 f"shelf." if pw else "No mapped downside shelf this expiry."))
    elif net <= 0 and not above_flip:
        bias = "bearish"
        headline = "Dealers are amplifying — they sell weakness here."
        path = (f"Best case: reclaim the flip at ${flip:g} ({_pct(flip):+g}%) "
                f"— above it dealer hedging flips supportive"
                + (f", opening the call wall ${cw:g} ({_pct(cw):+g}%)." if cw
                   else "."))
        risk = (f"Below the put wall ${pw:g} ({_pct(pw):+g}%) hedging "
                f"pressure accelerates the slide." if pw else
                "No put wall below — air pocket if selling picks up.")
    else:
        bias = "mixed"
        headline = "Gamma is split — regime and flip disagree."
        path = (f"Best case: hold above the flip ${flip:g} ({_pct(flip):+g}%) "
                f"until the profile turns one-sided." if flip else
                "Best case: wait for a one-sided gamma profile.")
        risk = "Reads are weakest in this state — lean on the SEPA setup."

    vanna_note = (vex or {}).get("read")
    return {"bias": bias, "headline": headline, "path": path, "risk": risk,
            "vanna_note": vanna_note}


def _bs_gamma(spot: float, strike: float, iv: float, dte_days: int) -> Optional[float]:
    """Black-Scholes gamma fallback when the snapshot omits greeks.gamma. r≈0 is
    fine for the short swing horizon. Returns None on degenerate inputs."""
    try:
        t = max(dte_days, 1) / 365.0
        if spot <= 0 or strike <= 0 or iv <= 0:
            return None
        sig = iv if iv < 5 else iv / 100.0   # accept fraction or percent
        d1 = (math.log(spot / strike) + 0.5 * sig * sig * t) / (sig * math.sqrt(t))
        nprime = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
        return nprime / (spot * sig * math.sqrt(t))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FETCH + COMPUTE
# ---------------------------------------------------------------------------
def _fetch_contracts(symbol: str) -> tuple[list[dict], Optional[float]]:
    """Raw per-contract chain from Massive (Polygon /v3/snapshot/options), the
    same source options/soir.py uses. Returns (contracts, spot)."""
    key = options_key()
    if not key:
        return [], None
    try:
        import requests
    except ImportError:
        return [], None
    sess = requests.Session()
    base = f"https://api.massive.com/v3/snapshot/options/{symbol.upper()}"
    params = {"limit": 250, "apiKey": key}
    contracts: list[dict] = []
    spot: Optional[float] = None
    next_url: Optional[str] = base
    pages = 0
    try:
        while next_url and pages < 6:
            r = sess.get(next_url, params=params if pages == 0 else {"apiKey": key}, timeout=10)
            if r.status_code != 200:
                log.debug("%s: opex chain HTTP %s", symbol, r.status_code)
                break
            body = r.json() or {}
            for c in (body.get("results") or []):
                contracts.append(c)
                if spot is None:
                    px = (c.get("underlying_asset") or {}).get("price")
                    if px:
                        try:
                            spot = float(px)
                        except (TypeError, ValueError):
                            pass
            next_url = body.get("next_url")
            pages += 1
    except Exception as exc:
        log.warning("%s: opex chain fetch failed: %s", symbol, exc)
    return contracts, spot


def compute_opex(symbol: str) -> Optional[dict]:
    """Full OpEx read for the NEAREST expiration. Returns None if no chain."""
    sym = symbol.upper()
    contracts, spot = _fetch_contracts(sym)
    if not contracts:
        return None
    today = datetime.now(timezone.utc).date()

    # group by expiry, take the nearest (snapshot only carries live contracts)
    by_expiry: dict[str, list[dict]] = {}
    for c in contracts:
        exp = (c.get("details") or {}).get("expiration_date")
        if exp:
            by_expiry.setdefault(exp, []).append(c)
    if not by_expiry:
        return None
    next_expiry = sorted(by_expiry.keys())[0]
    chain = by_expiry[next_expiry]
    cls = classify_expiration(next_expiry, today)

    call_oi: dict[float, int] = {}
    put_oi: dict[float, int] = {}
    gex_rows: list[dict] = []
    for c in chain:
        d = c.get("details") or {}
        k = d.get("strike_price")
        typ = d.get("contract_type")
        if k is None or typ not in ("call", "put"):
            continue
        oi = c.get("open_interest") or 0
        if typ == "call":
            call_oi[k] = call_oi.get(k, 0) + int(oi)
        else:
            put_oi[k] = put_oi.get(k, 0) + int(oi)
        g = (c.get("greeks") or {}).get("gamma")
        if g is None:                       # BS fallback from IV
            g = _bs_gamma(spot or 0, float(k), c.get("implied_volatility") or 0,
                          cls["days_to_expiry"])
        # Vanna is never in the snapshot — always BS-derived from IV.
        vn = _bs_vanna(spot or 0, float(k), c.get("implied_volatility") or 0,
                       cls["days_to_expiry"])
        gex_rows.append({"strike": k, "type": typ, "gamma": g, "vanna": vn,
                         "oi": int(oi)})

    mp = max_pain(call_oi, put_oi, spot)
    gex = net_gex_and_walls(gex_rows, spot)
    vex = net_vex(gex_rows, spot)

    return {
        "symbol": sym,
        "spot": round(spot, 2) if spot else None,
        **cls,
        "max_pain": mp,
        "gamma": gex,
        "vex": vex,
        "best_case": best_case(spot, gex, vex),
        "gex_reliability": "index" if sym in INDEX_LIKE else "single_name",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "note": ("A tendency into expiration, not a guarantee — confirm with the "
                 "SEPA setup. Gamma sign is a heuristic (SqueezeMetrics), most "
                 "reliable on index/ETF and can invert on single-name leaders."),
    }
