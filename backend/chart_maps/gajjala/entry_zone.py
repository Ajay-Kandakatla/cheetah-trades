"""🧪 / 1-min entry zone (Ajay 2026-11-07, verbatim: "On the Gajjalas Audited and Gajjalas 1 min tab can you add entry
signal on the chart please like a small zone. Based on what he said, Like when its imminent with volume drying and
selling pressure is low. and Also when the pullback is ideal and close EMAs I guess based on what he says.").

WHAT. ONE served band on a FORMING setup tile of the 1-minute page (GG1) and the audited tab (GGA): kind `gg_entry`,
lo = the read's stop, hi = its trigger — the house band primitive across the chart. Its `label` is the SHORT variant word
("entry zone" — the chart's <title> and crosshair readout print it, a phone card has no room for a sentence); its `note`
is the sentence (the card line under the chart). GG5 (🚩 Gajjala's) serves none — the words live in WORDS_1M / WORDS_GGA
only, so `variant.word` answers None for GG5 and the tile keeps `bands: []` byte for byte.

WHEN (the ONLY ingredients — the detectors' own reads, no new rule, no new number):
- IMMINENT — the trigger is armed (`ready` True: every criterion met, K3 volume dry among them) AND the ONE red-closes
  chip engine (context.red_closes_chip) shows no flag (≤ RED_CLOSES_WAIT red closes in a row). GG S11 "The volume will
  dry up during the entries of all my setups"; GG X 1733882105204011109 "more than 3 red closes is red flag to me".
- IDEAL PULLBACK — K3 volume dry (`k3_vol` True) AND the setup's OWN EMA criterion True: 💋 `k5a_honor` (honours the 9
  EMA, GG KF1), 🌀 `k7_ema21` (holds the 21 EMA, GG VCP1), ➖ `k6_merge` (9 and 21 EMA merged, GG S8 32:49). 🚩 and 🎾
  have no EMA criterion → the imminent zone only.
A read with no base bar never zones: K3's volume check is vacuously True over an EMPTY pullback (detectors.k3_vol_ok),
the POTENTIAL_NEEDS_BASE precedent. The plan is the ONE plan rule (ledger.plan_of): no zone unless trigger > stop.

READ, NEVER SERVED. `reasons` / `bands` take the STORED read (it carries `base`; the served `gajjala` block does not).
Display only: nothing here gates, filters, pushes or trades. UNMEASURED — the 2026-10-14 study of the setups read NULL.
"""
from __future__ import annotations

from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX                   # red_closes_chip — the ONE red-closes engine
from chart_maps.gajjala import variant as V
from chart_maps.gajjala.ledger import PLANS, plan_of          # the ONE plan rule

ZONE_KIND = "gg_entry"           # == frontend PatternChart BAND_FILL / BAND_NAME key == CmBand union member (contract)
ZONE_LABEL_KEY = "zone_label"    # [C1] the SHORT word — WORDS_1M / WORDS_GGA; GG5 has none
ZONE_NOTE_KEY = "zone_note"      # [C1] the sentence — served as band["note"], printed as the card line
EMA_CRIT = {"kiss_fly": "k5a_honor", "intraday_vcp": "k7_ema21", "horizontal_fade": "k6_merge"}
IMMINENT_KEY = "imminent"
PRE_BREAK_STATES = ("forming",)  # zones on forming reads only (HIS CALL #5) — never partial / A+ / triggered / stopped
WHY_SEP = " · "


def why_imminent() -> str:
    """GG S11 "The volume will dry up during the entries of all my setups"; GG X 1733882105204011109. [C4] The
    red-closes clause is said ONLY while RED_CLOSES_MODE is not "off" — under "off" the chip engine returns None for
    every count, so the clause would be a typed claim nothing checked."""
    head = "imminent — trigger armed, volume dry"
    if GC.RED_CLOSES_MODE == "off":
        return head
    return f"{head}, no more than {GC.RED_CLOSES_WAIT} red closes in a row"


def why_pullback(crit_key: str) -> str:
    """GG KF1 (honours the 9 EMA) / VCP1 (holds the 21 EMA) / S8 32:49 (the 9 and 21 EMA merge)."""
    return {"k5a_honor": "ideal pullback — low volume, honours the 9 EMA",
            "k7_ema21": "ideal pullback — low volume, holds the 21 EMA",
            "k6_merge": f"ideal pullback — low volume, 9 and 21 EMA within {GC.K6_MERGE_PCT:g}%"}[crit_key]


def _has_base(read: dict) -> bool:
    """The pullback / base is a span of at least one bar (detectors._span; None for an empty one)."""
    base = read.get("base")
    n = base.get("bars") if isinstance(base, dict) else None
    return isinstance(n, int) and not isinstance(n, bool) and n > 0


def reasons(read: dict) -> list:
    """[] unless the read is forming, has a base bar and a plan (trigger > stop); then IMMINENT_KEY when `ready` is True
    and the red-closes chip engine shows no flag, plus the setup's EMA criterion key when `k3_vol` and that criterion
    are both True. [C5] A missing criterion row is simply no EMA leg — never a KeyError."""
    r = read if isinstance(read, dict) else {}
    if r.get("state") not in PRE_BREAK_STATES or not _has_base(r):
        return []
    if plan_of(r.get("trigger"), r.get("stop"))[0] != PLANS[0]:
        return []
    crit = {c.get("key"): c.get("ok") for c in (r.get("criteria") or []) if isinstance(c, dict)}
    out = []
    if r.get("ready") is True and CX.red_closes_chip(r.get("red_closes")) is None:
        out.append(IMMINENT_KEY)
    ema = EMA_CRIT.get(r.get("setup"))
    if ema is not None and crit.get("k3_vol") is True and crit.get(ema) is True:
        out.append(ema)
    return out


def bands(read: dict, v=None) -> list:
    """[] for GG5, for a variant without the zone words, or when `reasons` is empty; else ONE band
    {kind, lo = stop, hi = trigger, label = the short word, note = the sentence (imminent first, then the EMA reason)}."""
    if V.is_gg5(v):
        return []
    label: Optional[str] = V.word(ZONE_LABEL_KEY, v)
    if label is None:
        return []
    keys = reasons(read)
    if not keys:
        return []
    whys = [why_imminent() if k == IMMINENT_KEY else why_pullback(k) for k in keys]
    return [{"kind": ZONE_KIND, "lo": float(read["stop"]), "hi": float(read["trigger"]), "label": label,
             "note": V.word(ZONE_NOTE_KEY, v, why=WHY_SEP.join(whys))}]


__all__ = ["ZONE_KIND", "ZONE_LABEL_KEY", "ZONE_NOTE_KEY", "EMA_CRIT", "IMMINENT_KEY", "PRE_BREAK_STATES",
           "why_imminent", "why_pullback", "reasons", "bands"]
