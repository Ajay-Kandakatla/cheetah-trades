"""Tomorrow Bias — overnight / after-hours → next-session lean.

For ONE ticker (the options-flow tab) or the whole MARKET (the Overnight page
panel) this combines three INDEPENDENT pillars into a single lean
(LEAN_UP / LEAN_DOWN / NEUTRAL) plus a confluence-gated confidence:

  1. The extended-hours (after-hours / premarket) price move of the name.
  2. Its options flow — SOIR contrarian OI + today's put/call VOLUME.
  3. The market backdrop — SPY/QQQ extended-hours gap (the ES/NQ proxy, since
     index futures aren't entitled) + VIX + the market-regime label.

Philosophy (Minervini house rule): this TILTS probability for *reacting at the
open* — it does NOT predict the overnight. NEUTRAL is the honest default; high
conviction requires all three pillars to agree on real, fresh data.

The scoring was pressure-tested by an adversarial review (2026-06-26). The
fixes that review forced are why several "obvious" confluences are deliberately
NOT counted — each one was a place the model would have shown confidence that
fades by the open:

  - Regime label is the exact enum ``market_in_correction`` (NOT "correction"),
    so the don't-fight-the-tape penalty actually fires.
  - The stock pillar is the BETA RESIDUAL (stock gap − beta·SPY gap) so a
    pure-beta move isn't rewarded twice (in the stock pillar AND the backdrop).
  - A FADED extended-hours gap (retraced >50 % off its session extreme) loses
    its weight — "gaps fill, thin prints fade by morning".
  - The earnings veto uses a confirmed earnings-calendar date (day-cached)
    AND an abnormally large implied move / IV — either forces EVENT MODE (a
    range, not a direction). A bullish lean into a `market_in_correction` tape
    (or a bearish lean into a confirmed uptrend) is also penalised as fighting
    the durable tape, even on a green overnight gap.
  - When the fast (volume) and slow (contrarian OI) options reads disagree, the
    options pillar contributes 0 rather than letting one manufacture a sign.
  - Staleness is measured from the LAST EH BAR timestamp, not compute time, and
    a premarket read past ~09:35 ET (or an after-hours read carried into the
    next session) is suppressed to NEUTRAL.

The pure scorers ``score_bias`` / ``score_market_bias`` take already-fetched
inputs and contain ALL the logic, so they unit-test on synthetic data with no
network (see tests/test_tomorrow_bias.py). The ``compute_bias`` /
``market_bias`` wrappers just gather inputs and delegate.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("options.tomorrow_bias")

# Regime labels — must match sepa/market_regime.py EXACTLY. A typo here silently
# dead-codes the tape guard (the adversarial review's #2 finding).
REGIME_UPTREND = "confirmed_uptrend"
REGIME_PRESSURE = "uptrend_under_pressure"
REGIME_CORRECTION = "market_in_correction"
VALID_REGIME_LABELS = frozenset({REGIME_UPTREND, REGIME_PRESSURE, REGIME_CORRECTION})

# Pillar weights (sum to 1.0). The stock's own EH move is the anchor.
W_STOCK, W_OPTIONS, W_BACKDROP = 0.45, 0.30, 0.25

# Lean threshold on the blended raw score.
LEAN_THRESH = 0.20

# A one-expiry ATM implied move this big reads as an event (earnings/binary) —
# corroborates the soft news-keyword earnings flag.
EVENT_EXPECTED_MOVE_PCT = 6.0
EVENT_ATM_IV_PCT = 80.0

# Gap measured below this magnitude is noise.
NOISE_GAP_PCT = 0.5
INDEX_NOISE_GAP_PCT = 0.15

# Standing honesty line — never let the copy read as a prediction.
CAVEAT = ("This TILTS probability for reacting at the open — it does not predict "
          "the overnight. React at the open; don't bet the overnight guess.")


# ---------------------------------------------------------------------------
# small math helpers
# ---------------------------------------------------------------------------
def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def _et_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc)


# ===========================================================================
# PURE SCORERS — all the logic, no network. Unit-tested on synthetic data.
# ===========================================================================
def score_bias(eh: Optional[dict], soir_row: Optional[dict],
               backdrop: Optional[dict], beta: float = 1.0) -> dict:
    """Per-ticker Tomorrow Bias from already-fetched inputs.

    ``eh`` — extended-hours move dict (see ``_latest_eh_move``), or None.
    ``soir_row`` — a SOIR snapshot (see options/soir.py), or None.
    ``backdrop`` — market backdrop dict (see ``_index_backdrop``), or None.
    ``beta`` — the name's beta vs SPY (default 1.0) for residualising the gap.
    """
    flags: list[str] = []
    backdrop = backdrop or {}
    spy_gap = float(backdrop.get("spy_gap_pct") or 0.0)
    qqq_gap = float(backdrop.get("qqq_gap_pct") or 0.0)
    regime_label = backdrop.get("regime_label")
    vix = backdrop.get("vix")
    vix_pct = backdrop.get("vix_percentile_252d")

    # ---- no EH data: honest "react at the open" -------------------------
    if not eh or eh.get("eh_gap_pct") is None:
        return _neutral_bias("No extended-hours move yet — react at the open.",
                             ["no_eh_data"], backdrop, soir_row, eh)
    if eh.get("stale"):
        return _neutral_bias("Extended-hours window has passed — react at the open.",
                             ["stale_eh"], backdrop, soir_row, eh)

    eh_gap = float(eh["eh_gap_pct"])
    em = soir_row.get("expected_move_pct") if soir_row else None
    atm_iv = soir_row.get("atm_iv") if soir_row else None
    last_close = eh.get("last_rth_close")

    # ---- EVENT GATE (earnings / binary). Trust IV, not just a keyword. ----
    event = False
    earnings_source = None
    if soir_row and soir_row.get("earnings_flag"):
        event = True
        earnings_source = soir_row.get("earnings_source") or "news_keyword"
    if em is not None and em >= EVENT_EXPECTED_MOVE_PCT:
        event, earnings_source = True, earnings_source or "iv_inferred"
    if atm_iv is not None and atm_iv >= EVENT_ATM_IV_PCT:
        event, earnings_source = True, earnings_source or "iv_inferred"
    if event:
        flags.append("event_risk")
        flags.append(f"earnings_source:{earnings_source}")
        band = _band(last_close, em)
        move_txt = f" (implied move ±{em:.1f}%)" if em else ""
        src_txt = {"calendar": "a scheduled earnings report",
                   "news_keyword": "earnings in the news",
                   "iv_inferred": "abnormal implied volatility"}.get(earnings_source, "an event")
        return {
            "lean": "NEUTRAL", "confidence": 20, "confidence_tier": "LOW",
            "raw_score": 0.0, "agree_count": 0,
            "reason": (f"Event night{move_txt} — flagged by {src_txt}. Binary event: "
                       "the straddle IS the forecast, trade the range not a direction."),
            "expected_move_band": band, "flags": flags,
            "pillars": _pillar_detail(None, None, None, eh, soir_row, backdrop),
            "as_of": eh.get("data_as_of"), "caveat": CAVEAT,
        }

    em_eff = max(float(em), 1.0) if em else 3.0

    # ---- PILLAR 1: stock EH move (beta residual) ------------------------
    residual = eh_gap - beta * spy_gap          # strip the market-beta push
    base = _clamp(residual / em_eff)
    if abs(eh_gap) < NOISE_GAP_PCT:
        base = 0.0
    bars = int(eh.get("eh_bars") or 0)
    holding = bool(eh.get("gap_holding"))
    thin = bars < 5
    if thin:
        vol_mult = 0.3
        flags.append("thin_print")
    elif bars < 15:
        vol_mult = 0.6
    else:
        vol_mult = 1.0 if holding else 0.6   # a faded "real" gap loses the x1.0
    if not holding and not thin:
        flags.append("gap_fading")
    p1 = _clamp(base * vol_mult)

    # ---- PILLAR 2: options flow -----------------------------------------
    options_partial = False
    if not soir_row:
        p2 = 0.0
        options_partial = True
        flags.append("no_options_data")
    else:
        sv = soir_row.get("soir_volume")
        fast = _fast_flow(sv)
        slow, slow_known = _slow_oi(soir_row.get("soir_percentile"))
        if not slow_known:
            options_partial = True
            flags.append("options_pillar_partial")
            p2 = 0.7 * fast               # fast-only; partial → won't unlock HIGH
        elif _sign(fast) and _sign(slow) and _sign(fast) != _sign(slow):
            p2 = 0.0                       # fast/slow disagree → contribute nothing
            flags.append("options_conflict")
        else:
            p2 = _clamp(0.7 * fast + 0.3 * slow)
        sig = soir_row.get("signal")
        if p2 and sig in ("BULLISH", "BEARISH"):
            sig_sign = 1 if sig == "BULLISH" else -1
            p2 = _clamp(p2 * (1.1 if sig_sign == _sign(p2) else 0.85))

    # ---- PILLAR 3: market backdrop --------------------------------------
    idx = _index_dir(spy_gap, qqq_gap)
    if regime_label == REGIME_UPTREND:
        regime_tilt = 0.3
    elif regime_label == REGIME_CORRECTION:
        regime_tilt = -0.3
    else:
        regime_tilt = 0.0
    p3 = _clamp(0.6 * idx + 0.4 * regime_tilt)

    # ---- blend + lean ---------------------------------------------------
    raw = W_STOCK * p1 + W_OPTIONS * p2 + W_BACKDROP * p3
    if raw >= LEAN_THRESH:
        lean = "LEAN_UP"
    elif raw <= -LEAN_THRESH:
        lean = "LEAN_DOWN"
    else:
        lean = "NEUTRAL"

    lean_sign = _sign(raw) if lean != "NEUTRAL" else 0
    pillars = [p1, p2, p3]
    agree_count = sum(1 for p in pillars if lean_sign and _sign(p) == lean_sign and abs(p) >= 0.25)

    # fighting-the-tape: stock and backdrop pillars directly oppose
    fighting = _sign(p1) and _sign(p3) and _sign(p1) != _sign(p3) and abs(p1) >= 0.25 and abs(p3) >= 0.25
    # …and the DURABLE tape: a bullish lean into a correction (or a bearish lean
    # into a confirmed uptrend) is fighting the regime even on a green overnight
    # gap — the regime is the durable signal; the gap is the fade-prone one.
    regime_fight = ((lean == "LEAN_UP" and regime_label == REGIME_CORRECTION)
                    or (lean == "LEAN_DOWN" and regime_label == REGIME_UPTREND))
    if (fighting or regime_fight) and "fighting_the_tape" not in flags:
        flags.append("fighting_the_tape")

    # ---- confidence (confluence-gated) ----------------------------------
    if lean == "NEUTRAL":
        conf = round(min(35, 50 * abs(raw) / 0.6))
    else:
        conf = round(50 * abs(raw) / 0.6 + 15 * agree_count - 10)
    caps = [90]
    if thin:
        caps.append(40)
    if (vix is not None and vix >= 30) or (vix_pct is not None and vix_pct >= 90):
        caps.append(55)
        flags.append("high_vix")
    if abs(eh_gap) < em_eff:
        caps.append(60)
        flags.append("inside_expected_move")
    if options_partial:
        caps.append(50)
    if fighting:
        caps.append(50)
    if regime_fight:
        caps.append(55)
    if not holding:
        caps.append(55)
    # HIGH (>=70) requires FULL 3-pillar confluence on real, calm, holding data
    # that isn't fighting the durable regime tape.
    high_ok = (agree_count >= 3 and not options_partial and not thin and holding
               and not fighting and not regime_fight and (vix is None or vix < 30))
    if not high_ok:
        caps.append(69)
    conf = int(max(0, min(min(caps), conf)))
    tier = "HIGH" if conf >= 70 else ("MEDIUM" if conf >= 40 else "LOW")

    reason = _reason(lean, eh, soir_row, backdrop, agree_count, flags, thin, holding)
    return {
        "lean": lean, "confidence": conf, "confidence_tier": tier,
        "raw_score": round(raw, 3), "agree_count": agree_count,
        "reason": reason,
        "expected_move_band": _band(last_close, em),
        "flags": flags,
        "pillars": _pillar_detail(p1, p2, p3, eh, soir_row, backdrop),
        "as_of": eh.get("data_as_of"), "caveat": CAVEAT,
    }


def _fast_flow(soir_volume) -> float:
    """Today's put/call VOLUME read NON-contrarian (fresh positioning)."""
    if soir_volume is None:
        return 0.0
    sv = float(soir_volume)
    if sv <= 0.5:
        return 1.0
    if sv <= 0.7:
        return 0.6
    if sv >= 1.5:
        return -1.0
    if sv >= 1.3:
        return -0.6
    # linear glide through the neutral band, centred at 1.0
    return _clamp((1.0 - sv) / 0.5 * 0.6)


def _slow_oi(soir_percentile):
    """Contrarian Schaeffer OI read. Returns (score, known?)."""
    if soir_percentile is None:
        return 0.0, False
    p = float(soir_percentile)
    if p >= 90:
        return 0.5, True
    if p >= 80:
        return 0.3, True
    if p <= 10:
        return -0.5, True
    if p <= 20:
        return -0.3, True
    return 0.0, True


def _index_dir(spy_gap: float, qqq_gap: float) -> float:
    """Combined SPY/QQQ extended-hours direction in [-1, +1]."""
    def bucket(g: float) -> float:
        if abs(g) < INDEX_NOISE_GAP_PCT:
            return 0.0
        return (1.0 if g > 0 else -1.0) * (1.0 if abs(g) > 0.5 else 0.5)
    return _clamp(0.6 * bucket(spy_gap) + 0.4 * bucket(qqq_gap))


def _band(center, em_pct):
    if center is None or em_pct is None:
        return None
    c = float(center)
    e = float(em_pct) / 100.0
    return {"center": round(c, 2), "low_pct": -abs(float(em_pct)),
            "high_pct": abs(float(em_pct)),
            "low": round(c * (1 - e), 2), "high": round(c * (1 + e), 2)}


def _neutral_bias(reason, flags, backdrop, soir_row, eh) -> dict:
    em = soir_row.get("expected_move_pct") if soir_row else None
    center = eh.get("last_rth_close") if eh else None
    return {
        "lean": "NEUTRAL", "confidence": 0, "confidence_tier": "LOW",
        "raw_score": 0.0, "agree_count": 0, "reason": reason,
        "expected_move_band": _band(center, em), "flags": flags,
        "pillars": _pillar_detail(None, None, None, eh, soir_row, backdrop),
        "as_of": (eh or {}).get("data_as_of"), "caveat": CAVEAT,
    }


def _pillar_detail(p1, p2, p3, eh, soir_row, backdrop) -> dict:
    eh = eh or {}
    soir_row = soir_row or {}
    backdrop = backdrop or {}
    return {
        "stock": {"score": None if p1 is None else round(p1, 3),
                  "gap_pct": eh.get("eh_gap_pct"), "session": eh.get("eh_session"),
                  "bars": eh.get("eh_bars"), "gap_holding": eh.get("gap_holding")},
        "options": {"score": None if p2 is None else round(p2, 3),
                    "soir_volume": soir_row.get("soir_volume"),
                    "soir_percentile": soir_row.get("soir_percentile"),
                    "schaeffer_signal": soir_row.get("signal")},
        "backdrop": {"score": None if p3 is None else round(p3, 3),
                     "regime_label": backdrop.get("regime_label"),
                     "spy_gap_pct": backdrop.get("spy_gap_pct"),
                     "qqq_gap_pct": backdrop.get("qqq_gap_pct"),
                     "vix": backdrop.get("vix")},
    }


def _reason(lean, eh, soir_row, backdrop, agree_count, flags, thin, holding) -> str:
    dirn = {"LEAN_UP": "up", "LEAN_DOWN": "down", "NEUTRAL": "flat"}[lean]
    gap = eh.get("eh_gap_pct")
    sess = eh.get("eh_session") or "EH"
    bits = []
    if gap is not None:
        bits.append(f"{sess} {gap:+.1f}%" + (" (thin print)" if thin else ("" if holding else " (fading)")))
    if soir_row and soir_row.get("soir_volume") is not None:
        sv = soir_row["soir_volume"]
        bits.append(f"{'calls' if sv < 1 else 'puts'} heavy today (P/C vol {sv:.2f})")
    bd = backdrop or {}
    if bd.get("spy_gap_pct") is not None:
        bits.append(f"SPY {bd['spy_gap_pct']:+.2f}% / QQQ {(bd.get('qqq_gap_pct') or 0):+.2f}%")
    if lean == "NEUTRAL":
        return "Lean flat — " + (", ".join(bits) if bits else "no confluence") + ". React at the open."
    return f"Lean {dirn} — " + ", ".join(bits) + f" — {agree_count}/3 pillars agree."


# ===========================================================================
# MARKET-LEVEL scorer
# ===========================================================================
def score_market_bias(spy_gap, qqq_gap, gap_state, vix, vix_pct, vix_dir,
                      regime_label, regime_score, breadth=None) -> dict:
    """Market Tomorrow Bias from already-fetched inputs.

    ``gap_state`` — 'HOLDING' | 'FADING'. ``vix_dir`` — -1 falling / +1 rising /
    None when only the SPY-gap inverse is available (then VIX is NOT counted as
    a confirmer — it can't confirm the spine it was derived from). ``breadth`` —
    net dispersion-weighted EH-mover breadth in [-1, +1], or None if not wired.
    """
    flags: list[str] = []
    spy_gap = float(spy_gap or 0.0)
    qqq_gap = float(qqq_gap or 0.0)

    # index-level confluence gate: indices must agree (outside noise) for a lean
    spy_out = abs(spy_gap) >= INDEX_NOISE_GAP_PCT
    qqq_out = abs(qqq_gap) >= INDEX_NOISE_GAP_PCT
    if spy_out and qqq_out and _sign(spy_gap) != _sign(qqq_gap):
        flags.append("indices_disagree")
        return {"lean": "NEUTRAL", "confidence_tier": "LOW", "agreement_count": 0,
                "spy_gap_pct": round(spy_gap, 3), "qqq_gap_pct": round(qqq_gap, 3),
                "gap_state": gap_state, "confirmers": {},
                "what_to_watch": "SPY and QQQ disagree overnight — no clean tape. React at the open.",
                "flags": flags, "caveat": CAVEAT}

    def bucket(g):
        if abs(g) < INDEX_NOISE_GAP_PCT:
            return 0.0
        return (2.0 if abs(g) > 0.5 else 1.0) * (1 if g > 0 else -1)
    G = 0.6 * bucket(spy_gap) + 0.4 * bucket(qqq_gap)
    if gap_state == "FADING":
        G *= 0.5
        flags.append("gap_fading")
    lean = "LEAN_UP" if G > 0 else ("LEAN_DOWN" if G < 0 else "NEUTRAL")
    lean_sign = _sign(G)

    confirmers: dict[str, str] = {}
    agree = 0

    # VIX — only an INDEPENDENT confirmer when we have a real 2-close delta.
    if vix_dir is None:
        confirmers["vix"] = "neutral"
        flags.append("vix_proxy_only")
    else:
        if lean == "LEAN_UP" and vix_dir < 0 and (vix is None or vix < 20):
            confirmers["vix"] = "agree"; agree += 1
        elif lean == "LEAN_DOWN" and (vix_dir > 0 or (vix is not None and vix > 25)):
            confirmers["vix"] = "agree"; agree += 1
        else:
            confirmers["vix"] = "disagree" if lean != "NEUTRAL" else "neutral"

    # Breadth — dispersion-weighted; None when not wired this run.
    if breadth is None:
        confirmers["breadth"] = "neutral"
        flags.append("breadth_unavailable")
    elif lean_sign and _sign(breadth) == lean_sign and abs(breadth) >= 0.2:
        confirmers["breadth"] = "agree"; agree += 1
    else:
        confirmers["breadth"] = "disagree" if lean != "NEUTRAL" else "neutral"

    # Regime
    if lean == "LEAN_UP" and regime_label == REGIME_UPTREND:
        confirmers["regime"] = "agree"; agree += 1
    elif lean == "LEAN_DOWN" and regime_label == REGIME_CORRECTION:
        confirmers["regime"] = "agree"; agree += 1
    else:
        confirmers["regime"] = "disagree" if lean != "NEUTRAL" else "neutral"

    # confidence ladder
    high_blocked = (gap_state == "FADING" or (vix is not None and vix > 25)
                    or regime_label == REGIME_CORRECTION)
    if lean == "NEUTRAL":
        tier = "LOW"
    elif agree >= 3 and not high_blocked:
        tier = "HIGH"
    elif agree == 2 and gap_state != "FADING":
        tier = "MEDIUM"
    else:
        tier = "LOW"

    watch = _market_watch(lean, gap_state, confirmers, vix)
    return {
        "lean": lean, "confidence_tier": tier, "agreement_count": agree,
        "spy_gap_pct": round(spy_gap, 3), "qqq_gap_pct": round(qqq_gap, 3),
        "gap_state": gap_state, "vix": vix, "regime_label": regime_label,
        "confirmers": confirmers, "what_to_watch": watch,
        "flags": flags, "caveat": CAVEAT,
    }


def _market_watch(lean, gap_state, confirmers, vix) -> str:
    if lean == "NEUTRAL":
        return "Flat overnight tape — let the open set direction."
    if gap_state == "FADING":
        return "Gap is fading off its extreme — watch whether it holds at the open or fills."
    dis = [k for k, v in confirmers.items() if v == "disagree"]
    if dis:
        return f"Lean {lean.split('_')[1].lower()}, but {dis[0]} disagrees — confirm at the open before sizing up."
    if vix is not None and vix > 25:
        return f"Lean {lean.split('_')[1].lower()} but VIX {vix:.0f} is elevated — gaps fill more often in stress."
    return f"Confluent lean {lean.split('_')[1].lower()} — confirm the open holds the gap, then react."


# ===========================================================================
# INPUT GATHERERS — network. Thin; all logic lives in the scorers above.
# ===========================================================================
def _latest_eh_move(symbol: str, df=None) -> Optional[dict]:
    """Latest extended-hours move vs the most recent regular-session close.

    Returns a dict with eh_gap_pct, eh_session, eh_bars, eh_volume, gap_holding,
    last_rth_close, data_as_of (last EH bar ISO), stale (bool), or None.
    """
    try:
        import pandas as pd  # noqa: F401
        from daytrading.data import load_intraday_range
        from datetime import date
    except Exception as exc:
        log.debug("eh_move import failed: %s", exc)
        return None
    today = datetime.now(timezone.utc).date()
    if df is None:
        df = load_intraday_range(symbol, today - timedelta(days=5), today,
                                 include_premarket=True, include_afterhours=True)
    if df is None or df.empty or "session" not in df.columns:
        return None
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return None
    last_rth_ts = rth.index[-1]
    last_rth_close = float(rth.loc[last_rth_ts, "close"])
    # EH bars are everything AFTER the most recent regular close.
    eh = df[(df.index > last_rth_ts) & (df["session"].isin(["premarket", "afterhours"]))]
    if eh.empty:
        return None
    eh_last = float(eh["close"].iloc[-1])
    eh_high = float(eh["high"].max())
    eh_low = float(eh["low"].min())
    eh_bars = int(len(eh))
    eh_vol = float(eh["volume"].sum()) if "volume" in eh.columns else 0.0
    gap = (eh_last / last_rth_close - 1) * 100 if last_rth_close else 0.0
    # gap_holding: has price held near its EH extreme in the gap direction?
    if gap >= 0:
        denom = max(eh_high - last_rth_close, 1e-9)
        holding = (eh_high - eh_last) / denom <= 0.5
    else:
        denom = max(last_rth_close - eh_low, 1e-9)
        holding = (eh_last - eh_low) / denom <= 0.5
    last_bar_ts = eh.index[-1]
    # the loader's index is tz-naive UTC — stamp it as UTC so as_of carries an
    # explicit +00:00 offset (a tz-naive isoformat is read as browser-local).
    das_utc = (last_bar_ts.tz_localize("UTC") if last_bar_ts.tzinfo is None
               else last_bar_ts.tz_convert("UTC"))
    session = str(eh["session"].iloc[-1])
    # prior full-RTH-day volume (thin-print context)
    prior_vol = float(rth["volume"].sum()) if "volume" in rth.columns else 0.0

    # staleness from the LAST EH BAR timestamp, not compute time.
    try:
        et = (last_bar_ts.tz_localize("UTC") if last_bar_ts.tzinfo is None
              else last_bar_ts).tz_convert("America/New_York")
        now_et = _et_now()
        stale = _eh_stale(session, et, now_et)
    except Exception:
        stale = False

    return {
        "eh_gap_pct": round(gap, 3), "eh_session": session, "eh_bars": eh_bars,
        "eh_volume": eh_vol, "prior_rth_volume": prior_vol,
        "eh_high": round(eh_high, 4), "eh_low": round(eh_low, 4),
        "eh_last": round(eh_last, 4), "last_rth_close": round(last_rth_close, 4),
        "gap_holding": bool(holding),
        "data_as_of": das_utc.isoformat(), "stale": bool(stale),
    }


def _eh_stale(session: str, bar_et, now_et) -> bool:
    """A premarket read is valid until ~09:35 ET that morning; an after-hours
    read is valid until the NEXT regular session opens (09:30 ET next trading
    day) — so a Friday after-hours read stays valid across the weekend."""
    if session == "premarket":
        if now_et.date() > bar_et.date():
            return True
        return now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 35)
    # afterhours
    if now_et.date() <= bar_et.date():
        return False
    if now_et.weekday() >= 5:          # weekend — next session hasn't opened yet
        return False
    return now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 30)


_BETA_CACHE: dict[str, float] = {}


def _beta(symbol: str, index: str = "SPY") -> float:
    """Daily-returns beta vs SPY over the last ~120 sessions. Falls back to 1.0."""
    key = symbol.upper()
    if key in _BETA_CACHE:
        return _BETA_CACHE[key]
    beta = 1.0
    try:
        from sepa.prices import load_prices
        s = load_prices(symbol, period="1y")
        m = load_prices(index, period="1y")
        if s is not None and m is not None and len(s) > 60 and len(m) > 60:
            sr = s["close"].pct_change().tail(120)
            mr = m["close"].pct_change().reindex(sr.index)
            df = (sr.to_frame("s").join(mr.rename("m"))).dropna()
            if len(df) > 30 and df["m"].var() > 0:
                b = float(df.cov().loc["s", "m"] / df["m"].var())
                if 0.1 <= b <= 4.0:        # sane range; ignore junk
                    beta = round(b, 2)
                    _BETA_CACHE[key] = beta   # cache ONLY a real value
                    return beta
    except Exception as exc:
        log.debug("beta(%s) failed: %s", symbol, exc)
    # transient failure / junk → return the 1.0 default but DON'T cache it,
    # so the next request re-attempts once prices recover.
    return beta


_BACKDROP_CACHE = {"value": None, "ts": 0.0}
_BACKDROP_TTL_SEC = 180.0


def _index_backdrop(force: bool = False) -> dict:
    """SPY/QQQ extended-hours gap (ES/NQ proxy) + VIX + regime. Cached ~3 min."""
    now = time.time()
    if not force and _BACKDROP_CACHE["value"] is not None and now - _BACKDROP_CACHE["ts"] < _BACKDROP_TTL_SEC:
        return _BACKDROP_CACHE["value"]
    spy = _latest_eh_move("SPY")
    qqq = _latest_eh_move("QQQ")
    spy_gap = (spy or {}).get("eh_gap_pct")
    qqq_gap = (qqq or {}).get("eh_gap_pct")
    # gap_state from whichever index is leading the move
    holds = [d.get("gap_holding") for d in (spy, qqq) if d]
    gap_state = "HOLDING" if holds and all(holds) else ("FADING" if holds else None)

    regime_label = regime_score = vix = vix_pct = None
    try:
        from sepa import market_regime as mr
        reg = mr.regime()
        regime_label = reg.get("label")
        regime_score = reg.get("score")
        stress = (reg.get("components") or {}).get("stress") or {}
        vix = stress.get("vix")
        vix_pct = stress.get("percentile_252d")
    except Exception as exc:
        log.debug("backdrop regime failed: %s", exc)

    vix_dir = _vix_direction()
    out = {
        "spy_gap_pct": spy_gap, "qqq_gap_pct": qqq_gap, "gap_state": gap_state,
        "regime_label": regime_label, "regime_score": regime_score,
        "vix": vix, "vix_percentile_252d": vix_pct, "vix_dir": vix_dir,
        "spy": spy, "qqq": qqq,
    }
    _BACKDROP_CACHE["value"] = out
    _BACKDROP_CACHE["ts"] = now
    return out


_EARNINGS_CACHE: dict[tuple, bool] = {}


def _earnings_tonight(symbol: str) -> bool:
    """Best-effort: is this name reporting today or the next trading day?

    A SOIR row never carries an earnings flag, so without this the event veto
    relies entirely on IV inference and a moderate-IV earnings name slips
    through as a directional lean the night before a binary event. We close
    that with the yfinance earnings calendar (catalysts.calendar._next_earnings),
    day-cached per symbol so the options tab pays the lookup at most once a day,
    and fully defensive — any failure returns False (degrade to IV-inferred)."""
    today = _et_now().date()
    key = (symbol.upper(), today.isoformat())
    if key in _EARNINGS_CACHE:
        return _EARNINGS_CACHE[key]
    flag = False
    try:
        from catalysts.calendar import _next_earnings
        rec = _next_earnings(symbol)
        d = (rec or {}).get("date")
        if d:
            ed = datetime.fromisoformat(d).date()
            flag = today <= ed <= today + timedelta(days=1)   # tonight / next open
    except Exception as exc:
        log.debug("earnings check %s failed: %s", symbol, exc)
    _EARNINGS_CACHE[key] = flag
    return flag


def _vix_direction() -> Optional[int]:
    """Sign of the 1-day VIX change from two real closes, or None if unavailable
    (never fabricate it from the SPY gap — that double-counts the spine)."""
    try:
        from sepa.prices import load_prices
        df = load_prices("^VIX", period="1mo")
        if df is not None and len(df) >= 2:
            a, b = float(df["close"].iloc[-2]), float(df["close"].iloc[-1])
            return _sign(b - a)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# public compute wrappers
# ---------------------------------------------------------------------------
def compute_bias(symbol: str, soir_row: Optional[dict] = None,
                 backdrop: Optional[dict] = None) -> dict:
    """Per-ticker Tomorrow Bias, gathering inputs then scoring."""
    sym = symbol.upper()
    if soir_row is None:
        try:
            from . import soir as soir_mod
            rows = soir_mod.load_latest(symbol=sym)
            soir_row = rows[0] if rows else None
        except Exception as exc:
            log.debug("soir load for %s failed: %s", sym, exc)
    # Best-effort earnings-tonight enrichment so the event veto fires on a
    # confirmed report even when IV isn't extreme (day-cached, defensive).
    if not (soir_row and soir_row.get("earnings_flag")) and _earnings_tonight(sym):
        soir_row = dict(soir_row or {})
        soir_row["earnings_flag"] = True
        soir_row["earnings_source"] = "calendar"
    eh = _latest_eh_move(sym)
    backdrop = backdrop if backdrop is not None else _index_backdrop()
    beta = _beta(sym)
    out = score_bias(eh, soir_row, backdrop, beta=beta)
    out["symbol"] = sym
    out["beta"] = beta
    out["computed_at"] = datetime.now(timezone.utc).isoformat()
    return out


def market_bias(force: bool = False, breadth: Optional[float] = None) -> dict:
    """Market-level Tomorrow Bias panel."""
    bd = _index_backdrop(force=force)
    out = score_market_bias(
        bd.get("spy_gap_pct"), bd.get("qqq_gap_pct"), bd.get("gap_state"),
        bd.get("vix"), bd.get("vix_percentile_252d"), bd.get("vix_dir"),
        bd.get("regime_label"), bd.get("regime_score"), breadth=breadth,
    )
    out["read_session"] = _read_session()
    out["computed_at"] = datetime.now(timezone.utc).isoformat()
    return out


def _read_session() -> str:
    now = _et_now()
    return "MORNING_PREMARKET" if now.hour < 12 else "EVENING_AFTERHOURS"
