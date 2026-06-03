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


def notify_leaderboard_breakout(*, broke_out: list[dict], today_et: str) -> dict:
    """Consolidated push titled 'Leaderboard' — a name ON the rank leaderboard
    broke out today. Body lists which one(s). Tag keyed by ET date so a later
    breakout the same day replaces the banner rather than stacking on-device.
    Fired by the sepa.leaderboard_breakout_watch cron (Ajay 2026-06-03)."""
    if not broke_out:
        return {"sent": 0, "reason": "empty"}
    lines: list[str] = []
    for b in broke_out:
        bits: list[str] = []
        if b.get("last_close") is not None:
            bits.append(f"${b['last_close']:.2f}")
        if b.get("day_change_pct") is not None:
            bits.append(f"{'+' if b['day_change_pct'] >= 0 else ''}{b['day_change_pct']:.1f}%")
        if b.get("rs_rank") is not None:
            bits.append(f"RS {b['rs_rank']}")
        if b.get("rank") is not None:
            bits.append(f"#{b['rank']}")
        lines.append(f"🚀 {b['symbol']} · {' · '.join(bits)}")
    visible = lines[:8]
    body = "\n".join(visible)
    if len(broke_out) > len(visible):
        body += f"\n+{len(broke_out) - len(visible)} more"

    payload = {
        "title": "Leaderboard",
        "body": body,
        "tag":  f"leaderboard-breakout-{today_et}",
        "url":  "/leaderboard",
        "kind": "leaderboard_breakout",
        "ticker": broke_out[0]["symbol"] if len(broke_out) == 1 else None,
    }
    return sender.send_to_all(payload, kind="leaderboard_breakout")


# Sole admin — never expected to change. Hardcoded rather than env-var
# because we don't want accidental privilege escalation via misconfig.
ADMIN_EMAIL = "ajaykandakatla@gmail.com"


def notify_new_user(email: str) -> dict:
    """One-time admin push when a brand-new user signs in.

    Fires only once per user (gated by `users.store.record_signin`
    flipping `notified_admin` to True on its first call). Recipient: the
    admin's subscribed devices. Goes through the `user_signin` pref so
    the admin can mute later if onboarding bursts get noisy.
    """
    payload = {
        "title":  "👋 New user signed in",
        "body":   f"{email} just opened Pounce for the first time.",
        "tag":    f"new-user-{email}",     # de-dupe in case it ever re-fires
        "url":    "/admin/usage",
        "kind":   "user_signin",
        "email":  email,
    }
    r = sender.send_to_user(ADMIN_EMAIL, payload, kind="user_signin")
    log.info("notify_new_user: %s → admin sent=%d failed=%d",
             email, r.get("sent", 0), r.get("failed", 0))
    return r


# notify_macbook_deals(...) removed 2026-05-15 along with the rest of
# the lifeboard module. The caller (lifeboard.macbook.scan_and_persist)
# was deleted, so this hook had no callers left.
