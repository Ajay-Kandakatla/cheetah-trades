"""Glue between event sources (breakouts, etc.) and push delivery.

When a new breakout alert is recorded, this module is called to fan it out
to every subscribed device whose prefs allow that kind.
"""
from __future__ import annotations

import logging
from typing import Optional

from push import sender

log = logging.getLogger("push.hooks")


def notify_breakout(*, kind: str, ticker: str, reason: str,
                    score: Optional[float] = None,
                    last_close: Optional[float] = None,
                    day_change_pct: Optional[float] = None,
                    on_watchlist: bool = False) -> dict:
    """Fan out a breakout alert to subscribed devices.

    ``kind`` is the matching pref key — "volume_breakout" or "rising_momentum"
    or "watchlist_breakout".
    """
    title_emoji = "🚀" if kind == "volume_breakout" else "📈"
    title = f"{title_emoji} {ticker}"
    if last_close is not None:
        title += f" · ${last_close:.2f}"
    if day_change_pct is not None:
        title += f" {'+' if day_change_pct >= 0 else ''}{day_change_pct:.1f}%"

    # Click routing depends on kind:
    #   - rising_momentum → /track  (user wants to see the learning context)
    #   - volume_breakout → /sepa/{ticker} (immediate price-action context)
    # Both notifications include the ticker in the title so it's still scannable.
    if kind == "rising_momentum":
        url = f"/track#rising-{ticker}"
    else:
        url = f"/sepa/{ticker}"

    payload = {
        "title": title,
        "body": reason,
        "tag": f"{kind}-{ticker}",   # de-dupe on device
        "url": url,
        "ticker": ticker,
        "kind": kind,
    }

    # If the ticker is on the watchlist, ALSO fan out under the
    # watchlist_breakout pref — different users can subscribe to one but not
    # the other (e.g. "I only want notifications for things I'm tracking").
    result = sender.send_to_all(payload, kind=kind)
    if on_watchlist:
        sender.send_to_all(payload, kind="watchlist_breakout")
    return result


def notify_juggernauts(*, juggernauts: list[dict],
                       new_today: list[str],
                       today_et: str) -> dict:
    """Consolidated push for watchlist "Juggernaut" emergences.

    A Juggernaut = watchlist ticker showing institutional accumulation
    (up/down vol ratio ≥ 1.5) + rising momentum simultaneously. Fired by
    the ``sepa.juggernaut`` cron when new names join today's set.

    One push per emergence — the body lists every current juggernaut, with
    🆕 marking the names that just joined. Tag is keyed by ET date so a
    second emergence later in the same day replaces the previous banner
    on-device rather than stacking.
    """
    if not juggernauts:
        return {"sent": 0, "reason": "empty"}

    new_set = set(new_today)
    lines: list[str] = []
    for j in juggernauts:
        marker = "🆕 " if j["ticker"] in new_set else "   "
        bits: list[str] = []
        close = j.get("last_close")
        chg = j.get("day_change_pct")
        ud = j.get("ud_ratio")
        mom = j.get("momentum") or "?"
        if close is not None:
            bits.append(f"${close:.2f}")
        if chg is not None:
            bits.append(f"{'+' if chg >= 0 else ''}{chg:.1f}%")
        if ud is not None:
            bits.append(f"u/d {ud}×")
        bits.append(mom)
        lines.append(f"{marker}{j['ticker']} · {' · '.join(bits)}")

    # Push bodies have practical length limits across iOS/macOS/Chrome
    # (~256-300 chars). Cap at 8 lines and tease the rest.
    visible = lines[:8]
    body = "\n".join(visible)
    if len(juggernauts) > len(visible):
        body += f"\n+{len(juggernauts) - len(visible)} more on /watchlist"

    payload = {
        "title": "Juggernaut stocks today from SEPA watch List",
        "body": body,
        "tag":  f"juggernaut-{today_et}",   # one slot per ET day; replaces on device
        "url":  "/watchlist",
        "kind": "juggernaut_watchlist",
        "ticker": None,
    }
    # Goes through sender.send_to_all → also routed to Mac SSE via the
    # mac_outbox fan-out in notify._send_push (one notification stream).
    return sender.send_to_all(payload, kind="juggernaut_watchlist")


def notify_macbook_deals(new_deals: list[dict]) -> dict:
    """Fire ONE consolidated push for newly-seen MacBook deals.

    Called by lifeboard.macbook.scan_and_persist after a non-silent scan
    when at least one deal's URL wasn't in Mongo before this run. We
    intentionally batch into a single notification — four scans/day × N
    deals would otherwise spam.

    Click-routes to the morning page's macbook section.
    """
    if not new_deals:
        return {"sent": 0, "reason": "no new deals"}

    # Best deal headlines the body — biggest discount wins, ties broken by
    # lowest absolute price.
    new_deals = sorted(
        new_deals,
        key=lambda d: (-(d.get("discount_pct") or 0), d.get("price") or 9999999),
    )
    top = new_deals[0]
    src = top.get("source") or "?"
    cfg = top.get("config") or top.get("title", "")[:40]
    price = top.get("price")
    disc = top.get("discount_pct")
    extra = f" — {disc:.0f}% off" if disc else ""
    body = f"{cfg} · ${price:,.0f} ({src}){extra}"
    if len(new_deals) > 1:
        body += f"\n+{len(new_deals) - 1} more new deal{'s' if len(new_deals) > 2 else ''}"

    n = len(new_deals)
    payload = {
        "title": f"💻 {n} new MacBook deal{'s' if n > 1 else ''}",
        "body": body,
        "tag": "macbook-deals",  # de-dupe on device — newest replaces previous
        "url": "/morning#macbook-deals",
        "kind": "macbook_deal",
    }
    return sender.send_to_all(payload, kind="macbook_deal")
