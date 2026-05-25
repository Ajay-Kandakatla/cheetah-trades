"""Opening Range Breakout (ORB) — Mark Fisher's intraday classic.

Two phases:

  1) CAPTURE — at 9:46 ET (1 minute after the 9:45 opening range close),
     fetch the 9:30-9:45 minute bars for the top 10 SEPA candidates from
     Massive's /v2/aggs/ticker/{T}/range/1/minute endpoint. Compute the
     range high / low. Create a pending setup with:
         trigger = range_high + 1 cent
         stop    = range_low  - 1 cent
         target  = range_high + 1.0 × range_size   (i.e. 1:1 R:R minimum)
     Expires at end of session (7h from creation).

  2) WATCH — every minute from 9:47 to 15:55 ET, poll the latest minute
     bar via Massive. For each pending ORB setup, if the bar's high
     >= trigger AND the bar's volume is meaningful (> the average per-
     minute volume from the opening range), mark it triggered and fire
     a push notification with a one-tap Fidelity deep link.

User experience:
  - 9:50 ET: phone buzzes with "🎯 NVDA ORB triggered @ 149.42, stop
    144.10, target 153.00" + tap to open ticker page.
  - User taps, sees the setup details, places limit-or-better at
    Fidelity, sets OCO stop+target, walks away.
  - By 16:00 ET they've either taken profit, been stopped, or hit
    the auto-exit-at-close discipline.

Risk gates (mechanical, not judgment):
  - Range must be ≥ 0.4% of price — too tight a range and the breakout
    is meaningless noise.
  - Range must be ≤ 3.5% of price — too wide and the stop is too far,
    no R:R math works.
  - At least 3 minute bars must have actual trades in the 9:30-9:45
    window — illiquid names without consistent prints aren't tradable.

Why we can't use websockets for this (yet):
  - Massive's WebSocket is on a more expensive tier than $79.
  - 1-minute polling is good enough for a ~1-2% target. We're not in
    HFT territory. Even a 30-second delay on a 5-minute range is
    irrelevant for the size of move we're looking for.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from . import store, universe

log = logging.getLogger("setups.orb")


# Range bounds — the % of price that the opening range must fall within.
_MIN_RANGE_PCT = 0.4    # below this = noise
_MAX_RANGE_PCT = 3.5    # above this = stop too wide
_MIN_BARS      = 3      # min minute bars with trades in 9:30-9:45
_TOP_N         = 10     # top SEPA candidates to track

_OPEN_HOUR_ET, _OPEN_MIN_ET = 9, 30
_RANGE_END_HOUR_ET, _RANGE_END_MIN_ET = 9, 45


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc) - timedelta(hours=5)


def _et_today_iso() -> str:
    return _now_et().strftime("%Y-%m-%d")


def _fetch_minute_bars(symbol: str, date_iso: str) -> list[dict]:
    """Fetch 1-minute bars for `symbol` on `date_iso` (US Eastern date).

    Massive endpoint: /v2/aggs/ticker/{T}/range/1/minute/{from}/{to}
    Returns list of {t (unix ms), o, h, l, c, v}.
    """
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        log.warning("orb: MASSIVE_API_KEY not set")
        return []
    url = (f"https://api.massive.com/v2/aggs/ticker/{symbol.upper()}"
           f"/range/1/minute/{date_iso}/{date_iso}")
    try:
        r = requests.get(url, params={
            "adjusted": "true", "sort": "asc", "limit": 1000, "apiKey": key,
        }, timeout=8)
        if r.status_code != 200:
            log.warning("orb: massive %s -> HTTP %s: %s",
                        symbol, r.status_code, r.text[:160])
            return []
        return (r.json() or {}).get("results") or []
    except Exception as exc:
        log.warning("orb: massive fetch failed for %s: %s", symbol, exc)
        return []


def _bars_in_window(bars: list[dict], start_h: int, start_m: int,
                    end_h: int, end_m: int, date_iso: str) -> list[dict]:
    """Filter bars to a [start, end) ET window on a given date.

    Bars carry a UTC unix-ms timestamp `t`. Translate to ET by accounting
    for the date_iso (DST is auto-handled by zoneinfo).
    """
    try:
        from zoneinfo import ZoneInfo
        tz_et = ZoneInfo("America/New_York")
    except Exception:
        tz_et = timezone(timedelta(hours=-5))
    y, m, d = map(int, date_iso.split("-"))
    start = datetime(y, m, d, start_h, start_m, tzinfo=tz_et)
    end   = datetime(y, m, d, end_h,   end_m,   tzinfo=tz_et)
    start_ms = int(start.timestamp() * 1000)
    end_ms   = int(end.timestamp()   * 1000)
    return [b for b in bars if start_ms <= int(b.get("t", 0)) < end_ms]


# ---------------------------------------------------------------------------
# Phase 1: capture the opening range
# ---------------------------------------------------------------------------
def capture_range() -> list[dict]:
    """Build the day's ORB setup list. Call once at ~9:46 ET via cron.

    Idempotent — calling twice in the same session overwrites today's
    pending rows (via store.upsert_setups). Useful if the 9:46 cron
    misfires; just run it manually anytime before 10:00 and we'll have
    a setup list.
    """
    if universe.is_bull_regime() is False:
        log.info("orb: bear regime — skipping capture")
        return []

    cands = universe.get_sepa_candidates(top_n=_TOP_N)
    if not cands:
        log.info("orb: no SEPA candidates available")
        return []

    today = _et_today_iso()
    setups: list[dict] = []

    for c in cands:
        sym = c.get("symbol")
        if not sym:
            continue
        bars = _fetch_minute_bars(sym, today)
        if not bars:
            continue
        window = _bars_in_window(
            bars,
            _OPEN_HOUR_ET, _OPEN_MIN_ET,
            _RANGE_END_HOUR_ET, _RANGE_END_MIN_ET,
            today,
        )
        if len(window) < _MIN_BARS:
            log.debug("orb: %s has only %d bars in opening window — skip", sym, len(window))
            continue
        range_high = max(b["h"] for b in window)
        range_low  = min(b["l"] for b in window)
        range_size = range_high - range_low
        last_close = window[-1]["c"]
        if last_close <= 0:
            continue
        range_pct = range_size / last_close * 100
        if range_pct < _MIN_RANGE_PCT or range_pct > _MAX_RANGE_PCT:
            log.debug("orb: %s range %.2f%% out of bounds — skip", sym, range_pct)
            continue

        trigger = round(range_high + 0.01, 4)
        stop    = round(range_low  - 0.01, 4)
        target  = round(range_high + range_size, 4)  # 1:1 R:R as first target

        # Average minute volume in the opening window — used by the
        # watcher to require "real" volume on the trigger bar.
        avg_open_vol = sum(b["v"] for b in window) / len(window)

        meta = {
            "range_high":  round(float(range_high), 4),
            "range_low":   round(float(range_low),  4),
            "range_pct":   round(float(range_pct),  2),
            "n_bars":      len(window),
            "avg_open_minute_vol": round(float(avg_open_vol), 2),
            "captured_at_et": _now_et().strftime("%H:%M"),
            "sepa_score":  c.get("score"),
            "sepa_rating": c.get("rating"),
            "rs_rank":     c.get("rs_rank"),
        }
        setup = store.make_setup(
            kind="orb",
            symbol=sym,
            trigger=trigger,
            stop=stop,
            target=target,
            expires_in_hours=7,    # auto-expires at close
            meta=meta,
        )
        setups.append(setup)

    inserted = store.upsert_setups("orb", setups)
    log.info("orb: captured ranges for %d/%d candidates; %d setups",
             len(setups), len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["meta"].get("range_pct") or 0)[:3]
            body = " · ".join(
                f"{s['symbol']} {s['meta']['range_low']:.2f}-{s['meta']['range_high']:.2f}"
                for s in top
            )
            send_alert(
                title=f"🎯 ORB ranges set for {len(setups)} names",
                body=body,
                kind="setup_orb_capture",
                url="/setups?kind=orb",
            )
        except Exception as exc:
            log.warning("orb capture: push notify failed: %s", exc)

    return setups


# ---------------------------------------------------------------------------
# Phase 2: watch for triggers
# ---------------------------------------------------------------------------
def _last_minute_bar(symbol: str, date_iso: str) -> Optional[dict]:
    """Return the most recent minute bar for `symbol` today, or None."""
    bars = _fetch_minute_bars(symbol, date_iso)
    return bars[-1] if bars else None


def check_triggers() -> int:
    """Iterate pending ORB setups; mark any whose latest bar broke above
    the trigger; fire push notifications.

    Returns the count of newly-triggered setups. Safe to call every
    minute — the mark_triggered update is idempotent."""
    pending = [
        s for s in store.get_setups(kind="orb", only_pending=True, limit=50)
        if s.get("date_et") == _et_today_iso()
    ]
    if not pending:
        return 0
    today = _et_today_iso()
    triggered = 0
    for s in pending:
        sym = s.get("symbol")
        if not sym:
            continue
        bar = _last_minute_bar(sym, today)
        if not bar:
            continue
        if bar.get("h", 0) < s["trigger"]:
            continue
        avg_open = s.get("meta", {}).get("avg_open_minute_vol") or 0
        # Volume confirmation: trigger bar must do at least 50% of the
        # opening-range avg minute volume. Filters out wick-only breaks
        # on no participation.
        if avg_open > 0 and bar.get("v", 0) < avg_open * 0.5:
            log.debug("orb: %s broke high but low volume (%s vs avg %.0f) — skip",
                      sym, bar.get("v"), avg_open)
            continue
        ok = store.mark_triggered(s["_id"], bar["c"])
        if not ok:
            continue
        triggered += 1
        try:
            from sepa.notify import send_alert
            send_alert(
                title=f"🎯 {sym} ORB triggered @ {bar['c']:.2f}",
                body=(f"buy ≥ {s['trigger']:.2f}  ·  stop {s['stop']:.2f}  "
                      f"·  target {s['target']:.2f}  ·  R:R {s['rr']}"),
                kind="setup_orb_triggered",
                ticker=sym,
                url=f"/sepa/{sym}?from=orb",
            )
        except Exception as exc:
            log.warning("orb trigger push failed for %s: %s", sym, exc)
    if triggered:
        log.info("orb: %d setups newly triggered", triggered)
    return triggered


if __name__ == "__main__":
    # CLI:
    #   python -m setups.orb capture     # run 9:46 ET
    #   python -m setups.orb watch       # run every minute 9:47-15:55 ET
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "capture"
    if cmd == "capture":
        capture_range()
    elif cmd == "watch":
        check_triggers()
    elif cmd == "expire":
        n = store.expire_stale()
        print(f"expired {n} stale setups")
    else:
        print(f"unknown command: {cmd}")
        sys.exit(2)
