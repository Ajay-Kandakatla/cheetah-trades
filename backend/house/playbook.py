"""Daily playbook generator — what to do today, given current state.

Inputs:
  - config:    address, list_price, listed_on, comps
  - latest snapshot:  views/saves/tours/showings/offers
  - history:   prior 30 days of snapshots
  - comps:     recent comparable solds

Outputs a deterministic checklist + strategic advice block. Pure-Python,
no external services — runs anywhere.

The advice is keyed off Days On Market (DOM) thresholds that real-estate
brokers use:
  - Days 1-7   "Launch window"      — max showings, no concessions
  - Days 8-21  "Reset week"         — analyse, refresh photos, more open houses
  - Days 22-45 "Price reduction"    — market is telling you the price is wrong
  - Days 46+   "Strategic pivot"    — reduce or relist; consider rent
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional


def _days_on_market(listed_on: Optional[str]) -> int:
    if not listed_on:
        return 0
    try:
        listed = datetime.fromisoformat(listed_on).date()
    except Exception:
        return 0
    return (date.today() - listed).days


def _phase(dom: int) -> str:
    if dom <= 7:   return "launch"
    if dom <= 21:  return "reset"
    if dom <= 45:  return "reduce"
    return "pivot"


def _phase_label(p: str) -> str:
    return {
        "launch":  "Launch window (Days 1-7)",
        "reset":   "Reset week (Days 8-21)",
        "reduce":  "Price reduction zone (Days 22-45)",
        "pivot":   "Strategic pivot (Day 46+)",
    }.get(p, p)


def _interest_total(snap: dict) -> int:
    """Combined views/saves count across all platforms — single number to
    track day-over-day change."""
    if not snap:
        return 0
    keys = ["redfin_views", "redfin_saves", "redfin_tours",
            "zillow_views", "zillow_saves",
            "realtor_saves"]
    return sum(int(snap.get(k) or 0) for k in keys)


def _interest_velocity(history: list[dict]) -> dict:
    """Compare last 3-day rolling average vs previous 3-day to spot
    cooling/heating interest."""
    if len(history) < 6:
        return {"trend": "insufficient_data", "current_avg": 0, "prior_avg": 0}
    recent = history[-3:]
    prior = history[-6:-3]
    cur = sum(_interest_total(s) for s in recent) / 3
    prev = sum(_interest_total(s) for s in prior) / 3
    if prev == 0:
        return {"trend": "no_baseline", "current_avg": round(cur), "prior_avg": 0}
    delta_pct = (cur - prev) / prev * 100
    if delta_pct >= 15:
        trend = "heating"
    elif delta_pct <= -20:
        trend = "cooling"
    else:
        trend = "stable"
    return {
        "trend": trend,
        "current_avg": round(cur),
        "prior_avg":   round(prev),
        "delta_pct":   round(delta_pct, 1),
    }


def _comp_signal(list_price: Optional[float], comps: list[dict]) -> dict:
    """Compare list price/sqft against recent comp median.

    Returns:
      {
        "list_ppsf":   235,
        "comp_median_ppsf": 220,
        "premium_pct":  6.8,   # listing is 6.8% above median sold ppsf
        "verdict":     "above_market" | "in_line" | "below_market",
      }
    """
    if not list_price or not comps:
        return {"verdict": "insufficient_comps"}
    valid = [c for c in comps if c.get("ppsf")]
    if not valid:
        return {"verdict": "insufficient_comps"}
    ppsf_vals = sorted(int(c["ppsf"]) for c in valid)
    median = ppsf_vals[len(ppsf_vals) // 2]
    # Need our own sqft — comps store ppsf so we need the config.
    return {
        "comp_median_ppsf": median,
        "comp_count":       len(valid),
        "comp_min_ppsf":    ppsf_vals[0],
        "comp_max_ppsf":    ppsf_vals[-1],
    }


def build_playbook(*, config: dict, latest: Optional[dict],
                   history: list[dict], comps: list[dict],
                   events: list[dict]) -> dict:
    """Assemble the full playbook dict consumed by the frontend."""
    dom = _days_on_market(config.get("listed_on") if config else None)
    phase = _phase(dom)
    velocity = _interest_velocity(history)
    interest_today = _interest_total(latest or {})
    comp_signal = _comp_signal(
        (config or {}).get("list_price"),
        comps,
    )

    # Per-platform breakdown (latest day only, for the dashboard tiles).
    # `prev_*` fields are yesterday's values — used by the manual-entry
    # form as placeholder hints so the user can spot "no change" days.
    snap = latest or {}
    prev = history[-2] if len(history) >= 2 else {}
    platforms = {
        "redfin": {
            "views":      snap.get("redfin_views"),
            "saves":      snap.get("redfin_saves"),
            "tours":      snap.get("redfin_tours"),
            "prev_views": prev.get("redfin_views"),
            "prev_saves": prev.get("redfin_saves"),
            "prev_tours": prev.get("redfin_tours"),
            "url":        (config or {}).get("redfin_url"),
        },
        "zillow": {
            "views":      snap.get("zillow_views"),
            "saves":      snap.get("zillow_saves"),
            "prev_views": prev.get("zillow_views"),
            "prev_saves": prev.get("zillow_saves"),
            "url":        (config or {}).get("zillow_url"),
        },
        "realtor": {
            "saves":      snap.get("realtor_saves"),
            "prev_saves": prev.get("realtor_saves"),
            "url":        (config or {}).get("realtor_url"),
        },
    }
    # Total "interested" — saves are higher-intent than views, count them
    # together but weight saves 5× when ranking interest level.
    total_saves = sum(int(snap.get(k) or 0)
                      for k in ["redfin_saves", "zillow_saves", "realtor_saves"])
    total_views = sum(int(snap.get(k) or 0)
                      for k in ["redfin_views", "zillow_views"])
    total_tours = int(snap.get("redfin_tours") or 0)
    interested_score = total_saves * 5 + total_tours * 10 + (total_views // 10)

    # Daily checklist — phase-driven, deterministic.
    checklist = _build_checklist(
        phase=phase, dom=dom,
        velocity=velocity, latest=latest, comps=comps, events=events,
        config=config,
    )

    # Strategic notes — long-form advice for this phase.
    strategy = _strategy_for_phase(
        phase=phase, dom=dom, velocity=velocity,
        interest_today=interest_today, comp_signal=comp_signal,
        latest=latest, config=config,
    )

    return {
        "address":     (config or {}).get("address"),
        "list_price":  (config or {}).get("list_price"),
        "listed_on":   (config or {}).get("listed_on"),
        "dom":         dom,
        "phase":       phase,
        "phase_label": _phase_label(phase),
        "platforms":   platforms,
        "totals": {
            "views":            total_views,
            "saves":            total_saves,
            "tours":            total_tours,
            "interested_score": interested_score,
        },
        "velocity":    velocity,
        "comp_signal": comp_signal,
        "checklist":   checklist,
        "strategy":    strategy,
        "snapshot_count": len(history),
    }


# ---------------------------------------------------------------------------
# Daily checklist
# ---------------------------------------------------------------------------
def _build_checklist(*, phase: str, dom: int, velocity: dict,
                     latest: Optional[dict], comps: list[dict],
                     events: list[dict], config: dict) -> list[dict]:
    """Today's action items. Ordered by priority.

    Each item is {id, label, why, priority: 'high' | 'med' | 'low', done: bool}.
    `done` is always False — marking them done is a frontend localStorage
    feature so it survives reload but doesn't pollute Mongo.
    """
    items: list[dict] = []

    # Universal — every day
    items.append({
        "id": "check_views",
        "label": "Update today's view & save counts",
        "why":  "Daily delta is the single best leading indicator. Check Redfin/Zillow/Realtor and enter today's numbers in the snapshot form below.",
        "priority": "high",
    })

    # Phase-specific
    if phase == "launch":
        items += [
            {
                "id": "max_open_house",
                "label": "Schedule a Saturday + Sunday open house THIS weekend",
                "why":  "Days 1-7 attract the most curious buyers. Stack open houses to maximize foot traffic before the listing ages out of 'new' on every platform.",
                "priority": "high",
            },
            {
                "id": "share_socials",
                "label": "Share listing on Nextdoor + your neighborhood Facebook group",
                "why":  "Word-of-mouth is highest-intent traffic in McKinney's tight neighborhoods.",
                "priority": "med",
            },
            {
                "id": "agent_pings",
                "label": "Ask your agent to email the listing to top-25 buyer's agents in McKinney/Allen/Frisco",
                "why":  "Agent-to-agent direct outreach beats MLS broadcast in the launch window.",
                "priority": "med",
            },
        ]

    elif phase == "reset":
        items += [
            {
                "id": "review_photos",
                "label": "Audit listing photos — replace any below-grade shots",
                "why":  "By day 14, view rate decay typically starts. Fresh photos on Redfin/Zillow trigger the platform 'updated' badge and bump back into top-of-feed.",
                "priority": "high",
            },
            {
                "id": "agent_feedback",
                "label": "Ask agent for buyer feedback from this week's showings",
                "why":  "Common objections (kitchen dated, tight backyard, road noise) point to either a price adjustment or a staging fix.",
                "priority": "high",
            },
            {
                "id": "twilight_photos",
                "label": "Add twilight / drone exterior photos if missing",
                "why":  "Listing differentiation — only ~20% of McKinney listings have twilight shots. They double-click rate per multiple Redfin studies.",
                "priority": "med",
            },
        ]

    elif phase == "reduce":
        items += [
            {
                "id": "consider_drop",
                "label": "Consider a 2-3% price reduction (psychological round number)",
                "why":  "Beyond day 22 with cooling interest, the market is telling you the price is wrong. A clean break to a round number ($549K → $539K) refreshes platform algorithms AND signals to lurkers that you're motivated.",
                "priority": "high",
            },
            {
                "id": "comps_check",
                "label": "Re-pull comps within 0.5mi sold in last 30 days",
                "why":  "Static comps from listing day are stale by day 30. Today's market may have moved.",
                "priority": "high",
            },
            {
                "id": "video_walkthrough",
                "label": "Add a video walkthrough if not already on the listing",
                "why":  "Listings with video get 2-3× engagement on Zillow vs photo-only. Particularly impactful in the reduce phase.",
                "priority": "med",
            },
        ]

    else:   # pivot
        items += [
            {
                "id": "strategic_options",
                "label": "Decide: aggressive price drop, relist later, or rent it out",
                "why":  "Day 46+ DOM stigmatizes a listing — buyers wonder 'what's wrong'. Three honest paths: 5%+ drop, withdraw + relist in 60 days fresh, or convert to rental.",
                "priority": "high",
            },
            {
                "id": "rent_modeling",
                "label": "Get rental comps for the same address (Zillow Rent Zestimate, Rentometer)",
                "why":  "DFW rents are still climbing. Holding 12-18 months and selling next spring may net more than absorbing today's reduction.",
                "priority": "high",
            },
            {
                "id": "relist_calc",
                "label": "Calc: what would the listing look like if withdrawn for 60 days then relisted fresh?",
                "why":  "MLS days-on-market resets after 30-60 days off-market. Worth modeling vs the price-drop path.",
                "priority": "med",
            },
        ]

    # Reactive — based on signal
    if velocity.get("trend") == "cooling":
        items.insert(1, {
            "id": "react_cooling",
            "label": f"⚠️ Interest cooling ({velocity.get('delta_pct')}% vs prior 3 days) — schedule extra showings or refresh listing",
            "why":  "Cooling early in the cycle is recoverable; cooling in the reduce/pivot phase is the price-drop trigger.",
            "priority": "high",
        })
    elif velocity.get("trend") == "heating":
        items.insert(1, {
            "id": "react_heating",
            "label": f"🔥 Interest heating (+{velocity.get('delta_pct')}%) — hold firm on price + push for offers",
            "why":  "When interest accelerates, even soft offers tend to come in. Don't pre-emptively reduce.",
            "priority": "med",
        })

    if latest and latest.get("offers_received") and latest["offers_received"] > 0:
        items.insert(0, {
            "id": "review_offer",
            "label": f"📩 Review offer(s) — {latest['offers_received']} on the table",
            "why":  "Counter quickly. Multi-day delays signal weakness and offers walk.",
            "priority": "high",
        })

    if latest and latest.get("redfin_tours") and int(latest["redfin_tours"]) >= 3:
        items.append({
            "id": "tours_strong",
            "label": f"✓ {latest['redfin_tours']} tours scheduled — confirm with agent that walk-throughs convert",
            "why":  "High tour count without offers suggests staging or pricing friction at the door.",
            "priority": "med",
        })

    return items


# ---------------------------------------------------------------------------
# Strategic narrative
# ---------------------------------------------------------------------------
def _strategy_for_phase(*, phase: str, dom: int, velocity: dict,
                        interest_today: int, comp_signal: dict,
                        latest: Optional[dict], config: dict) -> list[str]:
    """Long-form advice paragraphs for the current phase. Returns a list
    of strings — frontend renders them as paragraphs."""
    paras: list[str] = []

    if phase == "launch":
        paras.append(
            f"You're {dom} day(s) into the launch window. The first 7 days are when "
            "every Redfin/Zillow user with a saved search in your zip gets the "
            "'NEW' badge in their feed. Maximum visibility you'll ever have. "
            "Don't negotiate concessions yet — sit on the asking price for at "
            "least the first weekend's open house."
        )
        paras.append(
            "Top priority this week: stack open houses, get all your photos "
            "right (the listing-feed image especially), and have your agent "
            "personally email top buyer's agents in McKinney/Allen/Frisco."
        )

    elif phase == "reset":
        paras.append(
            f"Day {dom} — the 'NEW' badge is gone on most platforms. Buyers "
            "who haven't pinged yet are signaling 'it's overpriced for what "
            "it is, OR I'd already be in there.' This week is for honest "
            "diagnosis."
        )
        paras.append(
            "Three things to look at: (1) Photos — replace any sub-par shots "
            "and add twilight/drone if missing. Most platforms re-promote "
            "edited listings. (2) Buyer feedback — debrief your agent on "
            "what showings have said. Common objections cluster — that's "
            "your fix list. (3) Open-house frequency — running one every "
            "weekend in the reset phase is the standard playbook."
        )

    elif phase == "reduce":
        paras.append(
            f"Day {dom} with cooling/flat interest is the market's quiet vote "
            "that you're priced too high. The data is consistent across "
            "DFW: listings that haven't gotten an offer by day 21-25 either "
            "drop price or sit until they do."
        )
        paras.append(
            "A 2-3% reduction to a round number ($549K → $539K) does two "
            "things: bumps you back into top-of-feed on the platforms (they "
            "promote price changes), and signals lurkers that you're "
            "negotiable. Bigger drops don't always pay off — buyers smell "
            "desperation."
        )
        if comp_signal.get("comp_median_ppsf"):
            paras.append(
                f"Comp set median is ${comp_signal['comp_median_ppsf']}/sqft "
                f"across {comp_signal.get('comp_count', 0)} recent solds. "
                "Compare your current $/sqft to that median; if you're more "
                "than 5% above, you're swimming upstream."
            )

    else:   # pivot
        paras.append(
            f"Day {dom} is well past where most listings convert. The MLS "
            "'days on market' counter is now actively hurting you — buyers "
            "see a high DOM number and assume there's something wrong with "
            "the house."
        )
        paras.append(
            "Three honest paths: (1) Aggressive 5%+ price drop to break the "
            "stalemate. (2) Withdraw and relist fresh in 30-60 days — DOM "
            "resets and the listing comes back as new on most platforms. "
            "(3) Convert to rental for 12-18 months and re-list spring 2027 "
            "— DFW rents are still strong and you avoid taking a loss in a "
            "soft market."
        )

    return paras
