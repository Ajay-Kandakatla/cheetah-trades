"""Promo tag tape — where was the price when the account posted, and where
did it go? Ajay 2026-09-02: "did they actually PSA it before the blow up or
after… I am looking for the price points and time on a graph."

5-minute bars incl. pre/after-market from one session before the first tag
to now, every roster tag as a marker, and a pure read: how much the name had
already moved in the hour before the tag, how far it went after, and when.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("catalysts.promo_tape")

MAX_SESSIONS = 6          # a tag older than this shows the last 6 sessions
BEFORE_MIN = 60           # the "was it already running" window
_TTL = 60.0
_cache: dict = {}
_lock = threading.Lock()


def _as_utc(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


def tags_for_ticker(ticker: str) -> list[dict]:
    """Every roster tag on this ticker: one FIRST and one LAST marker per
    account (the sweep keeps first/last per account, not every post)."""
    from catalysts.promo_circuit import _coll, PROMO_ACCOUNTS
    coll = _coll("promo_circuit_tags")
    if coll is None:
        return []
    # PROMO_ACCOUNTS is keyed by handle (tolerate a list of dicts too).
    items = (PROMO_ACCOUNTS.items() if isinstance(PROMO_ACCOUNTS, dict)
             else ((a.get("handle"), a) for a in PROMO_ACCOUNTS))
    tiers = {str(h).lower(): (v.get("tier", "B") if isinstance(v, dict) else "B") for h, v in items if h}
    out = []
    try:
        for r in coll.find({"ticker": ticker.upper()}):
            h = r.get("account") or ""
            tier = tiers.get(h.lower(), r.get("tier") or "B")
            posts = sorted((pp for pp in (r.get("posts") or []) if _as_utc(pp.get("at"))),
                           key=lambda pp: _as_utc(pp["at"]))
            if posts:
                # Every ACTUAL post (kept since 2026-09-02): first = solid, rest = dashed
                for i, pp in enumerate(posts):
                    out.append({"handle": h, "tier": tier, "at": _as_utc(pp["at"]).isoformat(),
                                "which": "first" if i == 0 else "post", "msg_id": pp.get("id"),
                                "n_messages": r.get("n_messages"), "sample": pp.get("body")})
                continue
            first, last = _as_utc(r.get("first_tagged_at")), _as_utc(r.get("last_tagged_at"))
            if first:
                out.append({"handle": h, "tier": tier, "at": first.isoformat(), "which": "first",
                            "n_messages": r.get("n_messages"), "sample": r.get("sample")})
            if last and first and (last - first).total_seconds() > 60:
                out.append({"handle": h, "tier": tier, "at": last.isoformat(), "which": "last",
                            "n_messages": r.get("n_messages"), "sample": None})
    except Exception as exc:                                # pragma: no cover
        log.warning("promo_tape: tags for %s failed: %s", ticker, exc)
    out.sort(key=lambda t: t["at"])
    return out


def bars_for(ticker: str, first_tag: Optional[datetime], today: Optional[date] = None) -> list[dict]:
    """5-min bars incl. extended hours from the session before the first tag
    (capped at MAX_SESSIONS) to now: [{t: epoch ms, o, h, l, c, v, s}]."""
    from daytrading.data import load_intraday_range
    from supply_demand.timeframes import resample_ohlcv
    today = today or date.today()
    start = (first_tag.date() - timedelta(days=1)) if first_tag else (today - timedelta(days=2))
    floor = today - timedelta(days=int(MAX_SESSIONS * 1.6) + 2)
    start = max(start, floor)
    raw = load_intraday_range(ticker, start, today, include_premarket=True, include_afterhours=True)
    if raw is None or raw.empty:
        return []
    df = resample_ohlcv(raw, "5min")
    if df is None or df.empty:
        return []
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    out = []
    for ts, r in zip(idx, df.itertuples(index=False)):
        out.append({"t": int(ts.timestamp() * 1000), "o": round(float(r.open), 4),
                    "h": round(float(r.high), 4), "l": round(float(r.low), 4),
                    "c": round(float(r.close), 4),
                    "v": float(getattr(r, "volume", 0) or 0),
                    "s": getattr(r, "session", None) or "rth"})
    return out


def _price_at(bars: list[dict], t_ms: int) -> Optional[dict]:
    """The last bar closed at or before t (a tag between bars reads the
    bar before it), else the first bar after."""
    before = [b for b in bars if b["t"] <= t_ms]
    if before:
        return before[-1]
    after = [b for b in bars if b["t"] > t_ms]
    return after[0] if after else None


def analyze(bars: list[dict], tags: list[dict]) -> dict:
    """Pure. Was the tag before, during, or after the move?"""
    if not bars or not tags:
        return {"read": None, "verdict": None}
    # Per-marker stats so the tooltip can say, for EACH account, what had
    # already happened when it posted and what followed.
    for tg in tags:
        tms = int(_as_utc(tg["at"]).timestamp() * 1000)
        at_b = _price_at(bars, tms)
        if not at_b:
            continue
        ref_b = [b for b in bars if b["t"] <= tms - BEFORE_MIN * 60_000]
        base_b = ref_b[-1]["c"] if ref_b else bars[0]["o"]
        aft_b = [b for b in bars if b["t"] > tms]
        tg["price_at"] = at_b["c"]
        tg["before_pct"] = round((at_b["c"] / base_b - 1) * 100, 1) if base_b else None
        tg["peak_after_pct"] = (round((max(b["h"] for b in aft_b) / at_b["c"] - 1) * 100, 1)
                                if aft_b and at_b["c"] else None)
    t0 = int(_as_utc(tags[0]["at"]).timestamp() * 1000)
    at = _price_at(bars, t0)
    if not at:
        return {"read": None, "verdict": None}
    p_tag = at["c"]
    ref = [b for b in bars if b["t"] <= t0 - BEFORE_MIN * 60_000]
    p_before = ref[-1]["c"] if ref else bars[0]["o"]
    before_pct = round((p_tag / p_before - 1) * 100, 1) if p_before else None
    after = [b for b in bars if b["t"] > t0]
    if after:
        peak = max(after, key=lambda b: b["h"])
        trough = min(after, key=lambda b: b["l"])
        peak_pct = round((peak["h"] / p_tag - 1) * 100, 1)
        trough_pct = round((trough["l"] / p_tag - 1) * 100, 1)
        now_pct = round((after[-1]["c"] / p_tag - 1) * 100, 1)
        mins_to_peak = round((peak["t"] - t0) / 60_000)
    else:
        peak = trough = None
        peak_pct = trough_pct = now_pct = None
        mins_to_peak = None
    # Thresholds: 3% = "already moving", 5% = "a run". Before/after are both
    # measured from the price at the tag.
    already = before_pct is not None and before_pct >= 3
    if peak_pct is None:
        verdict, read = "NO_TAPE_AFTER", "Nothing has printed since the tag yet"
    elif already and before_pct >= 5 and peak_pct < 3:
        verdict = "AFTER_THE_MOVE"
        read = (f"Posted AFTER the move (@{tags[0]['handle']} first): already +{before_pct:.1f}% in the hour before the tag, "
                f"only +{peak_pct:.1f}% more to the peak, {now_pct:+.1f}% now")
    elif already:
        verdict = "MID_RUN"
        read = (f"Posted MID-RUN (@{tags[0]['handle']} first): +{before_pct:.1f}% in the hour before, then +{peak_pct:.1f}% "
                f"to the peak {mins_to_peak} min later, {now_pct:+.1f}% now")
    elif peak_pct >= 5:
        verdict = "BEFORE_THE_MOVE"
        read = (f"Posted BEFORE the move (@{tags[0]['handle']} first): {before_pct:+.1f}% in the hour before, then "
                f"+{peak_pct:.1f}% to the peak {mins_to_peak} min later, {now_pct:+.1f}% now")
    else:
        verdict = "NO_RUN"
        read = (f"No run yet: {before_pct:+.1f}% before the tag, +{peak_pct:.1f}% peak after, "
                f"{now_pct:+.1f}% now")
    return {
        "verdict": verdict, "read": read,
        "price_at_tag": p_tag, "tag_at": tags[0]["at"],
        "before_pct": before_pct, "peak_pct": peak_pct, "trough_pct": trough_pct,
        "now_pct": now_pct, "mins_to_peak": mins_to_peak,
        "peak_at": (datetime.fromtimestamp(peak["t"] / 1000, tz=timezone.utc).isoformat() if peak else None),
    }


LITE_STRIDE = 3     # 5-min bars → 15-min closes for the inline row sparkline


def lite_payload(p: dict, stride: int = LITE_STRIDE) -> dict:
    """The inline mini-tape needs closes, sessions, the tag markers and the
    read — not OHLCV × every 5 minutes × 180 rows. Every `stride`-th bar plus
    the last one; bar keys t/c/s only; tags without the post bodies."""
    bars = p.get("bars") or []
    keep = [b for i, b in enumerate(bars) if i % max(1, stride) == 0]
    if bars and (len(bars) - 1) % max(1, stride):
        keep.append(bars[-1])
    tag_keys = ("handle", "tier", "at", "which", "price_at", "before_pct", "peak_after_pct")
    return {
        "ticker": p.get("ticker"), "lite": True, "tf": p.get("tf"), "n_bars": len(bars),
        "bars": [{"t": b["t"], "c": b["c"], "s": b.get("s") or "rth"} for b in keep],
        "tags": [{k: t.get(k) for k in tag_keys} for t in (p.get("tags") or [])],
        "verdict": p.get("verdict"), "read": p.get("read"),
        "price_at_tag": p.get("price_at_tag"), "before_pct": p.get("before_pct"),
        "peak_pct": p.get("peak_pct"), "now_pct": p.get("now_pct"),
        "peak_at": p.get("peak_at"), "as_of": p.get("as_of"),
    }


def tape_for(ticker: str, force: bool = False) -> dict:
    key = ticker.upper()
    with _lock:
        hit = _cache.get(key)
        if hit and not force and time.time() - hit["at"] < _TTL:
            return hit["payload"]
    tags = tags_for_ticker(key)
    first = _as_utc(tags[0]["at"]) if tags else None
    try:
        bars = bars_for(key, first)
    except Exception as exc:
        log.warning("promo_tape: bars for %s failed: %s", key, exc)
        bars = []
    payload = {
        "ticker": key, "bars": bars, "tags": tags, "n_bars": len(bars),
        "tf": "5min · pre/post market", "as_of": datetime.now(timezone.utc).isoformat(),
        **analyze(bars, tags),
        "note": ("Marker = the account's first (and last) post on the name. Read compares the "
                 f"hour BEFORE the first tag with the peak after it — a post that lands "
                 "mid-run or after the peak is a victory lap, not a call."),
    }
    with _lock:
        _cache[key] = {"at": time.time(), "payload": payload}
    return payload
