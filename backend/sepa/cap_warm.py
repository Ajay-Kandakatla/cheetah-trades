"""Market-cap coverage warm — make "unknown cap" mean unknown.

The bug (measured 2026-09-11)
-----------------------------
``supply_demand.zone_store.big_cap_universe`` keeps a name only when the weekly
shares cache carries a ``market_cap`` at or above the floor. It fails closed on
purpose — an unpriced name is not a small name, but it is not a known-big one
either. The problem was never that rule. The problem was that nothing ever
filled the cache over the scan universe, so "unknown" was mostly an artifact:

    universe (full)          2,651
    no shares_cache row        671
    row present, cap None       39
    TOTAL BLIND                710   (26.8%)
    kept by big_cap_universe 1,728

331 of the blind names traded over $50M/day. MU ($37.0B/day), TSM, LLY, SHOP,
APH, AZO, CVNA, TGT, TEAM, TTWO, SAP, ALNY, UAL, DVN and CAH had no zone_store
doc at all — and therefore no bands, no demand_alert, no zone_bounce_alert, no
supply_break_alert, and no zone_edge_entry paper lane.

Two independent causes, both real:

1. ``volume_movers.shares_for`` is LAZY. It fetches only when a card render or
   the Russell watch happens to ask for a symbol. There was no warm job over
   the scan universe, so 671 names were simply never asked about.

2. A PARTIAL row is honored for the full 7-day TTL. MU's row was
   ``{float_shares: 1125620978, shares_outstanding: None, market_cap: None}``:
   yfinance returned a float but no marketCap, ``any(v is not None)`` is True,
   so the row looked fresh and MU stayed invisible to every zone board for a
   week at a time — even though the data to derive a cap was sitting in the row.

What this module does NOT do
----------------------------
It does not touch the $700M floor, and it does not touch the fail-closed
comparison in ``big_cap_universe``. Both stay exactly as ``tests/test_cap_floor.py``
pins them across six modules. A name with a genuinely unknown cap is still
excluded. All this does is fill the cache so that "unknown" is a fact about the
name and not a fact about our fetch schedule. The eligible set widens because
the data arrived, not because a gate was loosened.

Derivation, and why a float-derived cap is safe
-----------------------------------------------
When a row has shares but no reported cap, the cap is derived from our OWN
price cache (``sepa.prices.load_prices`` — Mongo, closed bars, no provider call
per symbol):

    shares_outstanding x last_close  ->  cap_source "derived_shares"
    float_shares       x last_close  ->  cap_source "derived_float"

``derived_float`` is NOT the market cap — float excludes insider and restricted
stock, so it UNDERSTATES. That is precisely why it is safe against a gate that
only ever asks ">= floor": since float_shares <= shares_outstanding, a
float-derived cap is a LOWER BOUND on the true cap, so clearing the floor on it
means the true cap clears it too. It can under-admit a name, never over-admit
one. The bound works in ONE direction only, and that asymmetry is enforced: a
float-derived cap is written only when it CLEARS the floor. Below the floor the
understatement could flip a real answer, and since 2026-09-11 a known sub-floor
cap is a HARD block on the entry path (``trading/safety_floor.cap_block``) while
an unknown cap is merely a warning — so writing a too-low number there could
refuse a buy on a name whose true cap is fine. Such a row is left blind: it is
excluded from the zone boards either way, and the entry path keeps warning
instead of blocking on a number we cannot stand behind.

The gate stays fail-closed in the same direction it always failed.

Every filled cap is tagged with ``cap_source`` so a derived number is never
mistaken for a reported one.

Coverage, not freshness
-----------------------
This job fills MISSING caps. A row that already carries a cap is left alone even
when it is past the 7-day TTL (``refresh_stale=True`` overrides, off by default)
— ``shares_for`` already re-fetches those lazily, and a weekly re-fetch of 2,000
names to refresh numbers that gate a ">= $700M" question would be provider load
spent on nothing. Steady state is therefore cheap: after the first fill, a run
only fetches names that are new to the universe.

Cron: Saturdays 08:10 ET (backend/crontab), after symbol_liveness, on a day
when no scan is running. Cache-only concern, no market-day gate.

Docs: docs/supply_demand/cap_coverage.md
"""
from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional

log = logging.getLogger(__name__)

# yfinance is a polite-neighbour problem: ~700 calls on the first run, then
# near zero. Small pool + a pause between batches, never a stampede.
DEFAULT_WORKERS = 4
BATCH_SIZE = 50
BATCH_PAUSE_SEC = 1.0
DEFAULT_BUDGET_SEC = 1800.0        # 30 min; the Saturday slot is otherwise idle

REPORTED = "reported"
DERIVED_SHARES = "derived_shares"
DERIVED_FLOAT = "derived_float"

_SHARES_KEYS = ("shares_outstanding", "float_shares", "market_cap")


def _pos_finite(x) -> Optional[float]:
    """float(x) when it is a real, finite, positive number — else None.

    NaN is the trap this exists for: it survives float(), and `nan >= floor`
    is False, so a NaN cap would fail closed downstream but still LOOK like a
    known cap on the row. Never write one."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0:
        return None
    return v


def _floor(floor: Optional[float] = None) -> float:
    """The S/D cap floor, read from the module that enforces it so this can
    never drift away from it. tests/test_cap_floor.py pins all seven copies
    equal; this reads one rather than retyping an eighth."""
    if floor is not None:
        return float(floor)
    try:
        from supply_demand.zone_store import MIN_CAP_USD
        return float(MIN_CAP_USD)
    except Exception:                                          # noqa: BLE001
        return 700_000_000.0


def last_close(symbol: str, loader: Optional[Callable] = None) -> Optional[float]:
    """Last bar's close from our own Mongo price cache. None when the frame is
    missing or its close is not a usable number.

    Never prices.with_today_bar: a cap is a scale read, and that call costs a
    provider snapshot per symbol, which is the thing zone_store is careful never
    to do. The cache's last bar IS today's once the session has printed, which
    is correct here and unlike zone_store's own drop_today — a band drawn from
    today's low would be tautologically "touched", but a cap is just shares x a
    price and today's price is the best one. On the Saturday cron the last bar
    is Friday's anyway."""
    if loader is None:
        from sepa import prices

        def loader(sym):
            return prices.load_prices(sym)

    try:
        df = loader(symbol)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("cap_warm: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or getattr(df, "empty", True):
        return None
    try:
        return _pos_finite(df["close"].iloc[-1])
    except Exception:                                          # noqa: BLE001
        return None


def derive_cap(row: Optional[dict], close: Optional[float]) -> tuple[Optional[float], Optional[str]]:
    """(cap, cap_source) for one shares-cache row. (None, None) when the row
    carries nothing to work with.

    A reported cap always wins and is returned untouched — this never
    overwrites a provider's own number with an estimate. Otherwise shares
    outstanding is preferred over float, because float UNDERSTATES the cap
    (see the module docstring on why understating is the safe direction)."""
    if not row:
        return None, None
    reported = _pos_finite(row.get("market_cap"))
    if reported is not None:
        return reported, REPORTED
    px = _pos_finite(close)
    if px is None:
        return None, None
    so = _pos_finite(row.get("shares_outstanding"))
    if so is not None:
        return so * px, DERIVED_SHARES
    fl = _pos_finite(row.get("float_shares"))
    if fl is not None:
        return fl * px, DERIVED_FLOAT
    return None, None


def cap_fields(symbol: str, row: Optional[dict], loader: Optional[Callable] = None,
               close: Optional[float] = None, floor: Optional[float] = None) -> dict:
    """The ``$set`` fields that give one row a usable cap — {} when nothing can
    be derived. Shared by this job and by volume_movers.shares_for, so a lazy
    fetch and the weekly warm fill a row the same way and neither clobbers the
    other's work."""
    if not row:
        return {}
    if _pos_finite(row.get("market_cap")) is not None:
        return {"cap_source": REPORTED}
    if close is None:
        close = last_close(symbol, loader)
    cap, source = derive_cap(row, close)
    if cap is None or source == REPORTED:
        return {}
    if source == DERIVED_FLOAT and cap < _floor(floor):
        # The lower-bound argument licenses ADMITTING on a float-derived cap,
        # never REJECTING on one. Below the floor it is the one place the
        # understatement can flip a real answer, and since 2026-09-11 a KNOWN
        # sub-floor cap is a HARD block on the entry path
        # (trading/safety_floor.cap_block) while an unknown one is only a
        # warning. Writing this number could refuse a buy on a name whose true
        # cap clears the floor. Leave the row blind instead: same exclusion
        # from the zone boards, and the entry path keeps warning rather than
        # blocking on a number we cannot stand behind.
        return {}
    return {"market_cap": int(round(cap)), "cap_source": source,
            "cap_derived_close": round(float(close), 4)}


def needs_cap(row: Optional[dict]) -> bool:
    """A row is blind when it is absent or its cap is not a usable number."""
    return _pos_finite((row or {}).get("market_cap")) is None


# --------------------------------------------------------------------------
# The job
# --------------------------------------------------------------------------
def warm(universe: Optional[Iterable[str]] = None, *, coll=None,
         loader: Optional[Callable] = None, fetcher: Optional[Callable] = None,
         max_workers: int = DEFAULT_WORKERS, batch_size: int = BATCH_SIZE,
         pause_sec: float = BATCH_PAUSE_SEC, budget_sec: float = DEFAULT_BUDGET_SEC,
         refresh_stale: bool = False, limit: Optional[int] = None) -> dict:
    """Give every scan-universe name a market cap. Every input is injectable
    for tests; the cron passes none.

    Order of work per symbol, cheapest first:
      1. Row already has a cap -> leave it (unless refresh_stale).
      2. Row exists without one -> DERIVE from the row + our price cache.
         Costs no provider call, which is the whole of the 39 null-cap names.
      3. No row at all -> fetch shares once, then derive if the fetch still
         brought no cap back.

    Never raises: a symbol that fails is counted and skipped."""
    t0 = time.time()
    if universe is None:
        from sepa.universe import load_universe
        universe = load_universe("full")
    syms = sorted({str(s).upper().strip() for s in universe if s})
    if limit:
        syms = syms[:int(limit)]

    if coll is None:
        from sepa import volume_movers as vm
        coll = vm._shares_coll()
    if fetcher is None:
        from sepa.volume_movers import _fetch_shares_yf as fetcher

    res = {"universe": len(syms), "already": 0, "derived": 0, "fetched": 0,
           "no_data": 0, "failed": 0, "timed_out": False, "seconds": 0.0}
    if coll is None:
        log.warning("cap_warm: no shares cache collection — nothing to do")
        res["seconds"] = round(time.time() - t0, 1)
        return res

    try:
        rows = {d["_id"]: d for d in coll.find({"_id": {"$in": syms}})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("cap_warm: cache read failed: %s", exc)
        rows = {}

    todo = []
    for s in syms:
        row = rows.get(s)
        if row is not None and not needs_cap(row) and not refresh_stale:
            res["already"] += 1
            continue
        todo.append(s)

    def one(sym):
        """-> (sym, set_fields, kind). Never raises."""
        row = rows.get(sym)
        try:
            if row is not None and (row.get("shares_outstanding") or row.get("float_shares")):
                fields = cap_fields(sym, row, loader)
                return sym, fields, ("derived" if fields else "no_data")
            fetched = fetcher(sym)
            now = int(time.time())
            payload = dict(fetched or {k: None for k in _SHARES_KEYS})
            payload["as_of"] = now
            extra = cap_fields(sym, fetched, loader) if fetched else {}
            payload.update(extra)
            if _pos_finite(payload.get("market_cap")) is not None:
                payload.setdefault("cap_source", REPORTED)
                return sym, payload, "fetched"
            return sym, payload, "no_data"
        except Exception as exc:                               # noqa: BLE001
            log.debug("cap_warm: %s failed: %s", sym, exc)
            return sym, {}, "failed"

    for start in range(0, len(todo), max(1, int(batch_size))):
        if time.time() - t0 > budget_sec:
            res["timed_out"] = True
            break
        batch = todo[start:start + max(1, int(batch_size))]
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
            futs = {pool.submit(one, s): s for s in batch}
            for fut in as_completed(futs):
                try:
                    sym, fields, kind = fut.result()
                except Exception as exc:                       # pragma: no cover
                    log.warning("cap_warm: worker failed: %s", exc)
                    res["failed"] += 1
                    continue
                res[kind if kind in res else "failed"] += 1
                if not fields:
                    continue
                try:
                    coll.update_one({"_id": sym}, {"$set": fields}, upsert=True)
                except Exception as exc:                       # noqa: BLE001
                    log.debug("cap_warm: write failed for %s: %s", sym, exc)
        if pause_sec and start + batch_size < len(todo):
            time.sleep(float(pause_sec))

    res["seconds"] = round(time.time() - t0, 1)
    return res


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser(description="Fill market caps for the scan universe")
    ap.add_argument("--limit", type=int, default=None, help="first N symbols only")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET_SEC)
    ap.add_argument("--refresh-stale", action="store_true",
                    help="also re-derive rows that already carry a cap")
    a = ap.parse_args()
    out = warm(limit=a.limit, max_workers=a.workers, budget_sec=a.budget,
               refresh_stale=a.refresh_stale)
    log.info("CAP-WARM: universe=%s already=%s derived=%s fetched=%s no_data=%s "
             "failed=%s timed_out=%s seconds=%s", out["universe"], out["already"],
             out["derived"], out["fetched"], out["no_data"], out["failed"],
             out["timed_out"], out["seconds"])
