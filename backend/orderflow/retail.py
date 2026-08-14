"""Retail order flow, identified from the tape (BJZZ + the Barber correction).

Ajay 2026-08-14, asking whether another API could show retail orders resting in
the book. Short answer no — the book is anonymous, retail marketable orders are
internalised by wholesalers and never reach the lit book at all, and stops
exist in no feed until they fire. Buying depth-of-book (Databento MBO, ~$1.4k/mo)
would buy a clear view of market-maker and institutional limit orders, i.e. the
opposite of what he wants.

But EXECUTED retail flow is identifiable, from the tape we already pull.

THE METHOD
----------
Boehmer, Jones, Zhang & Zhang (2021): retail orders internalised by wholesalers
(Citadel Securities, Virtu) receive **sub-penny price improvement**. Reg NMS
Rule 612 bans sub-penny QUOTES but permits sub-penny FILLS, so a sub-penny
print reported off-exchange is a wholesaler filling retail. Institutional flow
is not executed that way.

    retail  =  exchange is a FINRA TRF  AND  price has a sub-penny remainder
               (excluding the 0.0 and 0.5 increments, which are not price
               improvement)

THE CORRECTION — AND WHY IT IS NOT OPTIONAL
-------------------------------------------
BJZZ signed the trade from the DIRECTION of the sub-penny: just under a round
penny meant a retail buy, just over meant a sell. Barber, Huang, Jorion, Odean
& Schwarz (2024, *Journal of Finance*) validated that against 85,000 KNOWN
retail trades in real brokerage accounts and found it identifies ~35% of retail
trades, **mis-signs 28% of the ones it finds**, and yields uninformative
imbalances for 30% of stocks. Their fix: sign against the **quote midpoint**
instead, which drops signing error to ~5%.

We measured the difference on SWKS, 2026-08-14:

    naive sub-penny sign : buy 34,004  sell 39,998  ->  imbalance  -8.1%
    midpoint sign (fix)  : buy 51,296  sell 37,351  ->  imbalance +15.7%

**They disagree on direction.** So this module signs on the midpoint only, and
refuses to report an imbalance at all when NBBO is unavailable — an unsigned
count is honest, a wrongly-signed one is worse than nothing.

WHAT IT IS NOT
--------------
Not a view of resting orders, not proof of who is on the other side, and not a
complete census — it catches roughly a third of retail activity by construction.
Configured house thresholds around a published method. Not advice.

Spec: docs/orderflow/retail_flow.md
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from . import darkpool

log = logging.getLogger("orderflow.retail")

# A sub-penny remainder this close to .0 or .5 is not price improvement — those
# are ordinary penny and half-penny prints.
SUBPENNY_EPS = 0.001

# Below this many identified trades an imbalance is noise, not a read.
MIN_TRADES_FOR_READ = 50

# |imbalance| beyond this reads as one-sided rather than balanced.
IMBALANCE_LEAN_PCT = 10.0

DISCLAIMER = (
    "Retail flow identified by sub-penny price improvement on off-exchange "
    "prints (Boehmer et al. 2021), signed against the quote midpoint (Barber "
    "et al. 2024, which found the original sub-penny signing mis-signs 28% of "
    "trades). Catches roughly a third of retail activity by construction — a "
    "sample, not a census. Not a view of resting orders. Not advice."
)


def is_subpenny(price: float, eps: float = SUBPENNY_EPS) -> bool:
    """True when `price` carries a sub-penny remainder that is real price
    improvement. PURE.

    Excludes the .0 and .5 cent increments: a print at exactly $10.00 or
    $10.005 is not a wholesaler improving on the penny."""
    if not price or price <= 0:
        return False
    z = (float(price) * 100.0) % 1.0
    if z < eps or z > 1.0 - eps:          # on the penny
        return False
    if abs(z - 0.5) < eps:                 # half-cent
        return False
    return True


def identify(trades: Optional[pd.DataFrame],
             quotes: Optional[pd.DataFrame] = None) -> dict:
    """Split a tape into retail vs everything else.

    `quotes` (NBBO) is what makes the SIGN trustworthy. Without it the counts
    are still reported but `signed` is False and no imbalance is returned.
    """
    out = {"available": False, "signed": False,
           "retail_trades": 0, "retail_shares": 0, "retail_pct_of_volume": None,
           "buy_shares": None, "sell_shares": None, "imbalance_pct": None,
           "lean": None, "read": None, "disclaimer": DISCLAIMER}
    if trades is None or trades.empty or "exchange" not in trades.columns:
        return out

    off = trades[trades["exchange"].map(darkpool.is_off_exchange)]
    if off.empty:
        return {**out, "available": True}
    retail = off[off["price"].map(is_subpenny)]
    total_vol = int(trades["size"].sum())
    r_shares = int(retail["size"].sum()) if not retail.empty else 0

    out.update({
        "available": True,
        "retail_trades": int(len(retail)),
        "retail_shares": r_shares,
        "retail_pct_of_volume": (round(100.0 * r_shares / total_vol, 1)
                                 if total_vol else None),
    })
    if retail.empty or quotes is None or quotes.empty:
        out["read"] = ("Retail prints identified but unsigned — no NBBO for this "
                       "session, and sub-penny signing mis-signs 28% of trades.")
        return out

    m = pd.merge_asof(
        retail.reset_index().sort_values("ts_utc")[["ts_utc", "price", "size"]],
        quotes.reset_index().sort_values("ts_utc")[["ts_utc", "bid", "ask"]],
        on="ts_utc", direction="backward",
    )
    m = m.dropna(subset=["bid", "ask"])
    if m.empty:
        out["read"] = "Retail prints identified but no quote matched them."
        return out

    mid = (m["bid"] + m["ask"]) / 2.0
    buy = int(m.loc[m["price"] > mid, "size"].sum())
    sell = int(m.loc[m["price"] < mid, "size"].sum())
    denom = buy + sell
    imb = round(100.0 * (buy - sell) / denom, 1) if denom else None

    lean = None
    if imb is not None and len(m) >= MIN_TRADES_FOR_READ:
        lean = ("buying" if imb >= IMBALANCE_LEAN_PCT else
                "selling" if imb <= -IMBALANCE_LEAN_PCT else "balanced")

    out.update({"signed": True, "buy_shares": buy, "sell_shares": sell,
                "imbalance_pct": imb, "lean": lean,
                "read": _read(out["retail_pct_of_volume"], imb, lean, len(m))})
    return out


def _read(pct_vol, imb, lean, n) -> str:
    if n < MIN_TRADES_FOR_READ:
        return (f"Only {n} retail prints identified — too few to read a "
                f"direction from.")
    where = f"{pct_vol}% of volume" if pct_vol is not None else "some volume"
    if lean == "buying":
        return f"Retail is BUYING ({imb:+.1f}% imbalance on {where} identified as retail)."
    if lean == "selling":
        return f"Retail is SELLING ({imb:+.1f}% imbalance on {where} identified as retail)."
    return f"Retail is balanced ({imb:+.1f}% imbalance on {where} identified as retail)."


def divergence(retail: dict, blocks: list) -> Optional[dict]:
    """Retail lean vs where the BLOCK money went — the configuration worth
    looking at.

    Ajay wanted to sort demand zones by retail activity. Raw retail COUNT is
    close to useless for that: a heavily traded name has more retail prints
    whatever else is true, so it mostly re-sorts by volume. What carries
    information is the DISAGREEMENT — retail buying into a level while large
    off-exchange blocks print on the other side, or vice versa.

    `blocks` is `darkpool.dark_blocks(...)`. Block side is not known from the
    tape, so this compares retail direction against block CONCENTRATION only
    and says so — it is a flag to go look, not a verdict.
    """
    if not retail or not retail.get("signed") or retail.get("lean") in (None, "balanced"):
        return None
    n_blocks = len(blocks or [])
    if n_blocks == 0:
        return None
    dollars = sum(b.get("dollars") or 0 for b in blocks)
    return {
        "retail_lean": retail["lean"],
        "block_count": n_blocks,
        "block_dollars": int(dollars),
        "note": (f"Retail is {retail['lean']} while {n_blocks} large off-exchange "
                 f"block(s) worth ${dollars/1e6:.1f}M printed in the same session. "
                 f"Block side is not knowable from the tape — this flags a "
                 f"configuration to look at, not a conclusion."),
    }
