"""Add the tickers these traders name to the scan universe — if they survive.

Ajay 2026-09-12: *"May be a cron job to check their events daily and add to our
list of stocks in case they are not in our existing list"*.

WHY THIS NEEDS A GATE AND NOT A LOOP
────────────────────────────────────
A cashtag is a string someone typed. Measured on the first real run, the eight
names these two accounts mention that are NOT already in `full` were:

    SPCX  HNGE  WOLF  KULR  LAES        ← real US-listed companies
    BNB   ETH   XRP                     ← CRYPTO

**Three of eight were crypto.** A naive "add what they mention" job would have
put BNB and XRP into the universe that every SEPA scan, every zone store, every
demand board and every paper lane runs on. So nothing is added on the strength
of being mentioned: a name is added because it RESOLVES — a real company record
and real price history — and it is rejected, with the reason stored, otherwise.

WHY MONGO AND NOT `sepa/universe.py`
────────────────────────────────────
The curated list is a Python literal baked into the image. A cron cannot edit
it, and if it could the edit would vanish on the next deploy. So adds live in
the `trader_universe_adds` collection, and `universe._fetch_component("traders")`
unions them in. That also makes every add auditable and reversible: each row
carries who said it, which post, and when — and flipping `status` to "rejected"
removes it from the next scan with no code change.

THE SECOND GATE STILL APPLIES. Being in `full` is necessary, not sufficient: a
name also needs a KNOWN market cap over $700M in `shares_cache` before
`zone_store` will give it bands, so a fresh add can sit in the universe and
still raise no alert until the weekly warm. This module warms the cap itself
for exactly that reason — otherwise a name reads as covered for up to a week
while being invisible.

NOTHING HERE IS A BUY. Adding a name means the app can SEE it. It does not mean
the app likes it, and no lane trades off this list.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("traders.curate")

COLL = "trader_universe_adds"

# A single run may not add more than this. A parsing regression that suddenly
# yields a hundred "tickers" must not be able to reshape the scan universe
# before anyone looks at it.
MAX_ADDS_PER_RUN = 12

# Price history a name must actually have before it is worth scanning. The
# app's own structure reads need far more than a handful of bars.
MIN_BARS = 60

# ...AND it must be CURRENT. Caught on the first real run against production
# prices (2026-09-12): SDIG — Stronghold Digital, acquired by Bitfarms — still
# returns 126 bars of history and would have sailed through a bars-only gate,
# then sat dead in the scan universe forever. Quantity is not liveness. Ten
# calendar days absorbs a long weekend plus a holiday without letting a name
# that stopped printing through.
MAX_STALE_DAYS = 10

# Never add these, whatever anyone posts. Index, volatility and crypto tickers
# are not stocks this app can scan, and the crypto ones are what the first real
# run actually turned up.
NEVER_ADD = frozenset({
    "SPY", "QQQ", "IWM", "DIA", "SPX", "NDX", "RUT", "DJI", "VIX", "VXX", "UVXY",
    "ES", "NQ", "RTY", "YM",
    "BTC", "ETH", "XRP", "BNB", "SOL", "ADA", "DOGE", "USDT", "USDC", "LTC",
    "BCH", "DOT", "AVAX", "MATIC", "SHIB", "TRX", "LINK", "XMR", "ETC",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    try:
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        return c.get_database(os.environ.get("MONGO_DB", "cheetah"))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.curate: no mongo: %s", exc)
        return None


def added_symbols(coll=None) -> list[str]:
    """What the `traders` universe component resolves to. Only `added` rows."""
    if coll is None:
        db = _db()
        if db is None:
            return []
        coll = db[COLL]
    try:
        return [str(d["_id"]).upper()
                for d in coll.find({"status": "added"}, {"_id": 1})]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.curate: read failed: %s", exc)
        return []


def _record(coll, sym: str, status: str, reason: str, src: dict) -> None:
    try:
        coll.update_one(
            {"_id": sym},
            {"$set": {"symbol": sym, "status": status, "reason": reason,
                      "checked_at": _now(), **src},
             "$setOnInsert": {"first_seen": _now()}},
            upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("traders.curate: write failed for %s: %s", sym, exc)


def _stale_days(df) -> Optional[int]:
    """Calendar days since the last bar, or None when the frame carries no
    readable date. None means UNKNOWN and is not treated as stale — the bars
    gate already ran, and inventing a death date is worse than missing one."""
    try:
        idx = getattr(df, "index", None)
        last = idx[-1] if idx is not None and len(idx) else None
        if last is None:
            return None
        ts = last.to_pydatetime() if hasattr(last, "to_pydatetime") else last
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - ts).total_seconds() // 86400))
    except Exception:                                          # noqa: BLE001
        return None


def validate(sym: str) -> tuple[bool, str]:
    """(ok, reason). The ONLY thing that decides whether a mention is added.

    Deliberately strict and deliberately boring: a real company record and real
    price history. "A champion mentioned it" is not a reason — that is the
    input, not the test."""
    sym = (sym or "").upper().strip()
    if not sym or not sym.isalpha() or len(sym) > 5:
        return False, "not a plausible US equity ticker"
    if sym in NEVER_ADD:
        return False, "index, volatility or crypto ticker — not a scannable stock"
    try:
        from sepa import symbols as SY
        if sym in (getattr(SY, "DELISTED", None) or set()):
            return False, "known delisted"
        renamed = (getattr(SY, "RENAMES", None) or {}).get(sym)
        if renamed:
            return False, f"renamed to {renamed} — add that instead"
    except Exception as exc:                                   # noqa: BLE001
        log.debug("traders.curate: symbol table unavailable: %s", exc)
    try:
        from sepa import prices
        df = prices.load_prices(sym)
    except Exception as exc:                                   # noqa: BLE001
        return False, f"price load raised: {type(exc).__name__}"
    if df is None or len(df) < MIN_BARS:
        return False, f"no usable price history (<{MIN_BARS} bars)"
    stale = _stale_days(df)
    if stale is not None and stale > MAX_STALE_DAYS:
        return False, f"stopped printing {stale}d ago — dead or acquired"
    return True, f"resolved, {len(df)} bars"


def _warm_cap(sym: str) -> Optional[float]:
    """Give the new name a shares row NOW.

    Without this it sits in `full` with no market cap, `zone_store` skips it
    (KNOWN cap over MIN_CAP_USD), and it looks covered while raising no alert
    until the weekly warm — up to a week of silent invisibility."""
    try:
        from supply_demand import shares_cache as SC
        return SC.warm([sym]).get(sym) if hasattr(SC, "warm") else None
    except Exception as exc:                                   # noqa: BLE001
        log.debug("traders.curate: cap warm failed for %s: %s", sym, exc)
        return None


def run(limit: int = MAX_ADDS_PER_RUN, coll=None, dry: bool = False) -> dict:
    """Check every tracked trader's tickers and add the ones that resolve."""
    from traders import feed as F, registry as R
    db = _db()
    if coll is None:
        if db is None:
            return {"error": "no mongo", "added": [], "rejected": []}
        coll = db[COLL]
    try:
        from sepa.universe import load_universe
        uni = {s.upper() for s in load_universe("full")}
    except Exception as exc:                                   # noqa: BLE001
        # Fail CLOSED: with no universe to compare against, every mention looks
        # missing and the job would add all of them.
        log.warning("traders.curate: universe unavailable, standing down: %s", exc)
        return {"error": "universe unavailable", "added": [], "rejected": []}

    seen_before = set(added_symbols(coll))
    candidates: dict[str, dict] = {}
    for t in R.TRADERS:
        for row in F.tickers(F.stored(limit=600, trader=t["key"])):
            sym = row["symbol"]
            if sym in uni or sym in seen_before or sym in candidates:
                continue
            post = row.get("last_post") or {}
            candidates[sym] = {"trader": t["key"], "handle": t["handle"],
                               "post_url": post.get("url"),
                               "post_text": (post.get("text") or "")[:280],
                               "post_at": post.get("created_at")}

    added, rejected = [], []
    for sym, src in sorted(candidates.items()):
        ok, reason = validate(sym)
        if not ok:
            rejected.append({"symbol": sym, "reason": reason, **src})
            if not dry:
                _record(coll, sym, "rejected", reason, src)
            continue
        if len(added) >= limit:
            # Never silently drop: what did not fit is reported and simply
            # gets picked up on the next run.
            rejected.append({"symbol": sym, "reason": "over the per-run cap", **src})
            continue
        cap = None if dry else _warm_cap(sym)
        if not dry:
            _record(coll, sym, "added", reason, {**src, "market_cap": cap})
        added.append({"symbol": sym, "reason": reason, "market_cap": cap, **src})

    log.info("traders.curate: %s added, %s rejected", len(added), len(rejected))
    return {"added": added, "rejected": rejected, "checked": len(candidates),
            "universe_before": len(uni), "dry": dry}


if __name__ == "__main__":                                     # pragma: no cover
    import sys
    dry = "--dry" in sys.argv
    out = run(dry=dry)
    if out.get("error"):
        print(f"traders.curate: {out['error']}")
        raise SystemExit(1)
    print(f"traders.curate: checked {out['checked']} unseen mentions "
          f"({'DRY RUN' if dry else 'live'})")
    for a in out["added"]:
        cap = f" cap ${a['market_cap']/1e6:,.0f}M" if a.get("market_cap") else ""
        print(f"  + {a['symbol']:<6} {a['reason']}{cap}   ({a['handle']})")
    for r in out["rejected"]:
        print(f"  - {r['symbol']:<6} {r['reason']}")
    raise SystemExit(0)
