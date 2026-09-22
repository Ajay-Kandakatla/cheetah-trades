"""Curate the promo-circuit board's names into the scan universe — if they survive.

Ajay 2026-09-21: *"We have this page that pull data from social media and chatter
the keeps pulling new stocks.. Can you please check if we can use them and make
sure to do some research and add them to our list as they come through please?"*

WHAT THIS IS, AND WHAT IT IS NOT
────────────────────────────────
The promo-circuit sweep (`catalysts/promo_circuit.py`) records which pump/alert
accounts tagged which ticker. **A tag is the PROMOTION, never foresight** — the
measured record on this cohort is a fade, and every surface that shows a
promo-tagged name says so. This module does not act on the tag. It answers one
much smaller question: *is the name even VISIBLE to the app?*

**Adding a name means the app can SEE it.** It does not mean the app likes it,
and no lane trades off this list. A promo-origin name passes through every
EXISTING downstream gate — the $700M known-cap floor in `zone_store`, the
`safety_floor` price/cap floors at `trading/entries._evaluate`, the SEPA
qualifier's liquidity gate — exactly like a Russell micro-cap. Nothing here is
a buy, nothing here is a push, and nothing here relaxes a gate.

WHY A GATE AND NOT A LOOP
─────────────────────────
Measured 2026-09-21: 1,561 distinct tickers have been tagged; 1,012 of them are
outside `full`. Inside the 14-day board window and after the shotgun prune, 374
outsiders were tagged. Of those **170 trade under $2**, **121 have median 50-day
dollar volume under $5M**, and **24 of the 54 that clear both floors are ETFs,
ETVs or foreign ADRs** (BIL, GDX, EWY, MCHI, SIL, REMX, ETHA, NOK, NVO, PBR,
SHEL, SFTBY, BAESY…). Adding what the board shows would put index funds and
OTC-quoted ADRs into the universe every scan, zone store, demand board and paper
lane runs on. So a tag is the INPUT, never the test.

THE GATE ORDER IS ITSELF A DESIGN DECISION
──────────────────────────────────────────
Cheapest and most permanent refusal first:

  1. already in the universe        — no fetch of ANY kind
  2. `traders.curate.NEVER_ADD`      — index / volatility / crypto cashtags; the
                                       same set step 4 refuses, asked here only
                                       because asking costs nothing
  3. Massive reference type/exchange — ONE http GET; ADRC/ETF/ETV/OTC refused
                                       here, BEFORE any bar is loaded
  4. `traders.curate.validate`       — the existing resolve gate (2y bars)
  5. `safety_floor.MIN_SHARE_PRICE`  — $2 last close
  6. `hot_pullback.MIN_DOLLAR_VOL_USD` — $5M median 50-day dollar volume

An ETF therefore never triggers a bar load, and an `$SPX` cashtag triggers
nothing at all. That ordering is not cosmetic: 24 of the 54 floor-passers are
refusable on one reference call, and `curate.validate` WRITES `price_cache` on
a miss.

The reference lookup **fails CLOSED**. An unknown security type is refused, not
admitted — a Massive outage costs a day of adds, never a bad add. That refusal
is about the RUN, not the name: class `unknown` is re-checked on the NEXT run,
tag or no tag, so an outage morning cannot refuse a name for the rest of its
14-day window.

REUSE, NOT A PARALLEL ENGINE
────────────────────────────
`traders.curate` is the one curation engine: `validate`, `_record`,
`added_symbols` and `MAX_ADDS_PER_RUN` are imported, never retyped. The window,
the age-out, the shotgun prune and the tier order are `promo_circuit`'s own
constants. The floors are the app's existing floors, by name.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import requests

from catalysts import promo_circuit as pc
from sepa import symbols as SY
from sepa import universe as U
from supply_demand import hot_pullback as HP
from traders import curate
# `trading.safety_floor` is a pure constants module (no broker, no orders, no
# Alpaca) and is the ONE place the $2 floor lives. It is the single deliberate
# exception to this module's "never import trading" guard — see
# `test_promo_curate.py::test_AST_GUARD_the_lane_never_imports_a_push_or_a_trade`.
from trading import safety_floor

log = logging.getLogger("catalysts.promo_curate")

COLL = "promo_universe_adds"
# One doc per LIVE run. Two of the numbers a run produces have NO row of their
# own: a name already `in_universe` is counted and never written (writing it
# would invent an add), and a name over the per-run cap is queued, not rejected
# — it gets its row on the run that actually admits it. Derived from the rows,
# both read 0 forever, which is a counter that LIES. They are served from this
# summary instead, and `last_run_at` says when it was last true.
RUNS_COLL = "promo_curate_runs"

# Every one of these is an EXISTING constant imported by name. Changing any of
# them is a rule change and is his call, not this module's.
MAX_ADDS_PER_RUN = curate.MAX_ADDS_PER_RUN               # 12
CANDIDATE_WINDOW_DAYS = pc.TAG_WINDOW_DAYS               # 14 — while the board shows it
AGE_OUT_DAYS = pc.RETAG_RESET_DAYS                       # 14 — the sweep's "campaign over"
MIN_SHARE_PRICE = safety_floor.MIN_SHARE_PRICE           # $2.00 on the last close
MIN_MEDIAN_DOLLAR_VOL = HP.MIN_DOLLAR_VOL_USD            # $5M median 50-day dollar volume
LISTING_EXCHANGES = U.MAJOR_EXCHANGES                    # XNYS/XNAS/ARCX/BATS/XASE

# Massive reference `type`. Probed 2026-09-21: BCS/BAK/BABA/TSM -> ADRC (XNYS),
# ADDYY/BAESY -> ADRC on "OTC Link", ADBT/AEMD/FBGL/TOPS -> CS. Foreign-domiciled
# Nasdaq/NYSE ordinaries (MNDY, DRTS, PHVS, STLA) are typed CS and are NOT
# refused by this — the ADR pin is `type`, never a 5-letter "Y" suffix and never
# `locale` (which reads `us` for ADRs too).
ADD_TYPES = frozenset({"CS"})

# A reason that cannot change overnight. A row rejected for one of these is
# never re-checked, however many times the account tags it again. `price`,
# `liquidity`, `stale`, `short` and `unreadable` are re-validated as soon as a
# NEW tag lands after the last check. `unknown` is the exception on the other
# side: it says the PROVIDER did not answer, so it is re-checked every run.
PERMANENT_REJECTS = frozenset({"adr", "not_common", "otc", "never_add", "renamed"})

# The universe a candidate is measured against — `full` MINUS this lane, so a
# name this lane already added never reads back as "in_universe" (which would
# make it un-age-outable) and `universe_before` is the honest non-promo count.
BASE_COMPONENTS = tuple(c for c in U._UNIVERSE_ALIASES["full"] if c != "promo")

# Filled by the MAIN SESSION from backend/scripts/promo_tag_study.py's
# --emit-measured JSON. None until that study has run: the chip and the audit
# endpoint then read "measurement pending", which is the truth.
MEASURED: Optional[dict] = {
    "as_of": "2026-09-22",
    "primary": "pooled-5-open",
    "n_5": 1231,
    "n_date_clusters_5": 31,
    "delta_5": -0.0477741596282352,
    "ci_date_5": [-0.07194734256908117, -0.034083210376948773],
    "ci_symbol_5": [-0.06496903727591287, -0.03431338961847651],
    "placebo_median_5": -0.0252365930599369,
    "oos_5": {"n": 415, "clusters": 8, "sign": "\u2212", "ci": None},
    "oos_clean": False,
    "rerun_after": "2026-10-12",
    "verdict": "inverted — do-not-chase radar; not a source of entries",
    "script": "backend/scripts/promo_tag_study.py",
    "doc": "docs/catalysts/promo_tag_study_2026_09_21.md",
    "artifact": "backend/scripts/promo_tag_measured.json",
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(v) -> Optional[datetime]:
    """Anything Mongo or `curate._record` may have stored -> aware datetime."""
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:                                      # noqa: BLE001
            return pc._parse_ts(v)
    return None


def _db():
    return curate._db()


def _default_loader() -> Callable:
    from sepa import prices
    return prices.load_prices


def _tier_of(account: Optional[str], fallback: Optional[str]) -> Optional[str]:
    """The LIVE roster's tier, not the one frozen in the doc — `tags_for` does
    the same, because a retier must not need a Mongo rewrite."""
    live = (pc.PROMO_ACCOUNTS.get(account or "") or {}).get("tier")
    return live or fallback


def _earliest_tag(doc: dict) -> Optional[datetime]:
    """`first_tagged_at` is the CURRENT campaign's first tag — the sweep resets
    it after RETAG_RESET_DAYS of dormancy. 127 docs carry a post older than it,
    so the earliest post wins."""
    stamps = [_dt(doc.get("first_tagged_at"))]
    for p in (doc.get("posts") or []):
        stamps.append(_dt(p.get("at")))
    live = [s for s in stamps if s is not None]
    return min(live) if live else None


# ---------------------------------------------------------------------------
# the tag set — ONE pruned, resolved set feeds candidates() AND age_out()
# ---------------------------------------------------------------------------
def _live_tags(tags_coll=None, now: Optional[datetime] = None) -> Optional[list[dict]]:
    """Roster tags inside the board window, shotgun-pruned and fate-resolved.

    The one set both `candidates()` and `age_out()` read, so a name can never be
    a candidate under one prune and alive under another. `symbols.resolve` runs
    here (DOOO -> DOO) because `curate.validate` REFUSES a renamed ticker and
    points at its successor — resolving first is how the successor gets checked
    instead of the tag being thrown away.

    Returns **None** — never `[]` — when the collection is missing or the read
    raises. An empty list is a real answer ("nothing is tagged right now") and
    `age_out()` reads it as *every campaign is over*, which would write
    `aged_out` over every added row on a single Mongo blip. Unreadable is not
    empty, so the caller stands down exactly as it does for an unreadable
    universe.
    """
    now = now or _now()
    cutoff = now - timedelta(days=CANDIDATE_WINDOW_DAYS)
    if tags_coll is None:
        tags_coll = pc._tags_coll()
    if tags_coll is None:
        log.warning("promo_curate: no promo_circuit_tags collection")
        return None
    try:
        docs = list(tags_coll.find({}))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("promo_curate: tag read failed: %s", exc)
        return None

    fresh = []
    for d in docs:
        last = _dt(d.get("last_tagged_at"))
        if last is not None and last >= cutoff and d.get("account"):
            fresh.append(d)

    out = []
    for d in pc.prune_shotgun_tags(fresh):
        raw = str(d.get("ticker") or "").upper().strip()
        if not raw or SY.is_delisted(raw):
            continue
        sym = SY.resolve(raw)
        if SY.is_delisted(sym):
            continue
        out.append({**d, "ticker": sym, "raw_ticker": raw})
    return out


def candidates(live: list[dict]) -> dict[str, dict]:
    """The pruned tag set grouped by RESOLVED ticker."""
    out: dict[str, dict] = {}
    for d in live:
        sym = d["ticker"]
        acct = d.get("account")
        tier = _tier_of(acct, d.get("tier"))
        first, last = _earliest_tag(d), _dt(d.get("last_tagged_at"))
        row = out.get(sym)
        if row is None:
            row = out[sym] = {"symbol": sym, "accounts": [], "best_tier": tier,
                              "first_tagged_at": first, "last_tagged_at": last,
                              "n_messages": 0}
        if acct and acct not in row["accounts"]:
            row["accounts"].append(acct)
        if tier and pc.TIER_ORDER.get(tier, 9) < pc.TIER_ORDER.get(row["best_tier"] or "", 9):
            row["best_tier"] = tier
        if first and (row["first_tagged_at"] is None or first < row["first_tagged_at"]):
            row["first_tagged_at"] = first
        if last and (row["last_tagged_at"] is None or last > row["last_tagged_at"]):
            row["last_tagged_at"] = last
        row["n_messages"] += int(d.get("n_messages") or 0)
    return out


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------
def reference_kind(sym: str, fetch: Optional[Callable] = None) -> Optional[dict]:
    """ONE Massive reference call — the only place a security TYPE is read per
    ticker. `None` on any failure, and `None` is REFUSED upstream: unknown
    security type is not an invitation to guess."""
    if fetch is not None:
        try:
            return fetch(sym)
        except Exception as exc:                               # noqa: BLE001
            log.debug("promo_curate: reference stub raised for %s: %s", sym, exc)
            return None
    try:
        from massive_keys import stocks_key
        key = stocks_key()
    except Exception:                                          # noqa: BLE001
        key = None
    if not key:
        return None
    try:
        r = requests.get(
            f"https://api.massive.com/v3/reference/tickers/{sym.upper()}",
            params={"apiKey": key}, timeout=8)
        if r.status_code != 200:
            return None
        res = (r.json() or {}).get("results") or {}
        if not res:
            return None
        return {"type": res.get("type"),
                "primary_exchange": res.get("primary_exchange"),
                "market": res.get("market"), "active": res.get("active"),
                "name": res.get("name"), "market_cap": res.get("market_cap")}
    except Exception as exc:                                   # noqa: BLE001
        log.debug("promo_curate: reference fetch failed for %s: %s", sym, exc)
        return None


def population(sym: str, uni: set, ref: Optional[dict]) -> str:
    """Which bucket this ticker belongs to. Pure."""
    if sym in uni:
        return "in_universe"
    if not ref:
        return "unknown"
    kind = str(ref.get("type") or "").upper()
    if kind.startswith("ADR"):
        return "adr"
    if kind not in ADD_TYPES:
        return "not_common"
    if str(ref.get("primary_exchange") or "").upper() not in LISTING_EXCHANGES:
        return "otc"
    if ref.get("active") is False:
        return "inactive"
    return "candidate"


# curate.validate's sentence -> a stable class the skip rule can key on.
def _reason_class(reason: str) -> str:
    r = (reason or "").lower()
    if "renamed to" in r:
        return "renamed"
    if "crypto" in r or "index" in r or "not a plausible" in r:
        return "never_add"
    if "delisted" in r:
        return "dead"
    if "stopped printing" in r:
        return "stale"
    if "price history" in r:
        return "short"
    if "price load raised" in r:
        return "unreadable"
    return "refused"


def _close_and_dvol(df) -> tuple[Optional[float], Optional[float]]:
    """(last close, median 50-day dollar volume). The same expression
    `hot_pullback` enforces its floor on: median of close x volume over 50."""
    try:
        close = float(df["close"].iloc[-1])
        dvol = float((df["close"] * df["volume"]).iloc[-50:].median())
    except Exception as exc:                                   # noqa: BLE001
        log.debug("promo_curate: frame unreadable: %s", exc)
        return None, None
    if close != close or dvol != dvol:                         # NaN
        return None, None
    return close, dvol


def validate_promo(sym: str, uni: set, *, ref_fetch: Optional[Callable] = None,
                   loader: Optional[Callable] = None,
                   now: Optional[datetime] = None) -> tuple[bool, str, str, dict]:
    """(ok, reason_class, reason, facts) — the gate, in refusal-cost order.

    `loader` exists ONLY so the container dry-probe can hand in a read-only
    `price_cache` reader; the default is the app's own `prices.load_prices`.
    """
    facts: dict = {}
    sym = (sym or "").upper().strip()

    if sym in uni:
        return False, "in_universe", "already in the scan universe", facts

    # `curate.NEVER_ADD` refused one step later anyway (step 4), and that check
    # is the first thing `curate.validate` does — before ANY price load — so
    # asking it here costs nothing and saves one HTTP reference call per index /
    # crypto cashtag per morning. It also lands the row in the PERMANENT class
    # `never_add` instead of `unknown`, so `_skip_rejected` never looks again.
    # Same rule, same constant, same sentence — only the ORDER changed.
    if sym in curate.NEVER_ADD:
        _, reason = curate.validate(sym)
        return False, "never_add", reason, facts

    ref = reference_kind(sym, ref_fetch)
    if ref is None:
        return (False, "unknown",
                "reference unavailable — refused this run, re-checked next", facts)
    facts.update({"ref_type": ref.get("type"),
                  "exchange": ref.get("primary_exchange"),
                  "name": ref.get("name"), "market_cap": ref.get("market_cap")})

    pop = population(sym, uni, ref)
    if pop == "adr":
        return (False, "adr",
                f"{ref.get('type')} on {ref.get('primary_exchange')} — a foreign "
                f"ADR, not a promo candidate", facts)
    if pop == "not_common":
        return (False, "not_common",
                f"{ref.get('type') or 'unknown type'} — not a common stock", facts)
    if pop == "otc":
        return (False, "otc",
                f"{ref.get('primary_exchange')} — not on a listing exchange", facts)
    if pop == "inactive":
        return False, "inactive", "no longer an active listing", facts

    ok, reason = curate.validate(sym)
    if not ok:
        return False, _reason_class(reason), reason, facts

    df = (loader or _default_loader())(sym)
    close, dvol = _close_and_dvol(df)
    if close is None:
        return False, "short", "no readable last close", facts

    facts["last_close"] = round(close, 4)
    if close < MIN_SHARE_PRICE:
        return (False, "price",
                f"last close ${close:,.2f} is under the ${MIN_SHARE_PRICE:,.2f} "
                f"floor (safety_floor.MIN_SHARE_PRICE)", facts)

    facts["median_dvol_50"] = round(dvol, 2) if dvol is not None else None
    if dvol is None or dvol < MIN_MEDIAN_DOLLAR_VOL:
        return (False, "liquidity",
                f"median 50-day dollar volume ${(dvol or 0.0)/1e6:,.1f}M is under "
                f"the ${MIN_MEDIAN_DOLLAR_VOL/1e6:,.1f}M floor "
                f"(hot_pullback.MIN_DOLLAR_VOL_USD)", facts)

    return True, "ok", reason, facts


# ---------------------------------------------------------------------------
# the store
# ---------------------------------------------------------------------------
def _record(coll, sym: str, status: str, reason: str, src: dict) -> None:
    """`curate._record` — same shape, same `checked_at` / `first_seen`."""
    curate._record(coll, sym, status, reason, src)


def added_symbols(coll=None) -> list[str]:
    """What the `promo` universe component resolves to. Only `added` rows."""
    if coll is None:
        db = _db()
        if db is None:
            return []
        coll = db[COLL]
    return curate.added_symbols(coll)


def _record_run(runs_coll, summary: dict, now: Optional[datetime] = None) -> None:
    """Persist ONE summary doc per live run.

    `in_universe` and `capped` names are deliberately never written to `COLL`
    (the first is not an add, the second is not a refusal), so any count of them
    rebuilt from the rows is 0 whatever the run actually did. The run doc is the
    one place those two numbers exist.
    """
    if runs_coll is None:
        return
    try:
        runs_coll.insert_one({"at": now or _now(), **summary})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("promo_curate: run summary write failed: %s", exc)


def last_run(runs_coll=None) -> dict:
    """The most recent run summary, or `{}` when no run has been recorded.

    `{}` is the honest answer for "never ran": the audit endpoint serves null
    rather than a zero that would read like a drained queue.
    """
    if runs_coll is None:
        db = _db()
        if db is None:
            return {}
        runs_coll = db[RUNS_COLL]
    try:
        docs = list(runs_coll.find({}).sort("at", -1).limit(1))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("promo_curate: run summary read failed: %s", exc)
        return {}
    if not docs:
        return {}
    return {k: v for k, v in dict(docs[0]).items() if k != "_id"}


def _rows(coll) -> dict[str, dict]:
    try:
        return {str(d["_id"]).upper(): d for d in coll.find({})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("promo_curate: row read failed: %s", exc)
        return {}


def _skip_rejected(row: Optional[dict], cand: dict) -> bool:
    """True when a previously-rejected name must not be re-checked.

    A reference type does not change overnight, so a permanent-class reject is
    never looked at again. Everything else is re-validated only when a NEW tag
    landed after the last check — otherwise the same 300 refusals would burn a
    reference call and a 2y bar fetch every single morning.
    """
    if not row or row.get("status") != "rejected":
        return False
    if row.get("reason_class") in PERMANENT_REJECTS:
        return True
    if row.get("reason_class") == "unknown":
        # `unknown` is not a verdict about the NAME, it is a verdict about the
        # RUN: the Massive reference call did not answer. On an outage morning
        # every candidate is stamped `unknown`; waiting for a NEW tag before
        # re-checking would refuse a name for the rest of its 14-day window
        # purely because the provider was down. §3.2 / §6: re-checked NEXT RUN,
        # tag or no tag.
        return False
    checked, last = _dt(row.get("checked_at")), cand.get("last_tagged_at")
    if checked is None or last is None:
        return False
    return last <= checked


def warm_cap(sym: str) -> Optional[float]:
    """Give the new name a shares row NOW — `zone_store` needs a KNOWN cap over
    $700M before it draws bands, so an unwarmed add reads as covered while
    raising nothing for up to a week."""
    try:
        from sepa import cap_warm, volume_movers as vm
        coll = vm._shares_coll()
        cap_warm.warm([sym], coll=coll)
        if coll is None:
            return None
        row = coll.find_one({"_id": sym}) or {}
        cap = row.get("market_cap")
        return float(cap) if cap is not None else None
    except Exception as exc:                                   # noqa: BLE001
        log.debug("promo_curate: cap warm failed for %s: %s", sym, exc)
        return None


def age_out(coll, live: list[dict], now: Optional[datetime] = None,
            dry: bool = False) -> list[dict]:
    """Drop adds whose campaign is over, or that stopped resolving.

    Reads the SAME pruned set `candidates()` reads: a name whose only remaining
    mention is one shotgun drive-by is not "still tagged".
    """
    now = now or _now()
    cutoff = now - timedelta(days=AGE_OUT_DAYS)
    still: dict[str, datetime] = {}
    for d in live:
        last = _dt(d.get("last_tagged_at"))
        if last is None or last < cutoff:
            continue
        sym = d["ticker"]
        if sym not in still or last > still[sym]:
            still[sym] = last

    dropped = []
    for sym in sorted(added_symbols(coll)):
        if sym not in still:
            reason = f"no roster tag for {AGE_OUT_DAYS}d — campaign over"
        else:
            ok, why = curate.validate(sym)
            if ok:
                continue
            reason = why
        dropped.append({"symbol": sym, "reason": reason})
        if not dry:
            _record(coll, sym, "aged_out", reason, {"origin": "promo_circuit"})
    return dropped


def origin_tags(coll=None) -> dict:
    """{SYM: {accounts, tier, first_tagged_at, added_at, reason}} for the chip."""
    if coll is None:
        db = _db()
        if db is None:
            return {}
        coll = db[COLL]
    out: dict = {}
    try:
        rows = list(coll.find({"status": "added"}))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("promo_curate: origin read failed: %s", exc)
        return {}
    for r in rows:
        sym = str(r.get("_id") or r.get("symbol") or "").upper()
        if not sym:
            continue
        first = r.get("first_tagged_at")
        out[sym] = {"accounts": r.get("accounts") or [],
                    "tier": r.get("best_tier"),
                    "first_tagged_at": first.isoformat() if isinstance(first, datetime) else first,
                    "added_at": r.get("checked_at"),
                    "reason": r.get("reason")}
    return out


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------
def run(limit: int = MAX_ADDS_PER_RUN, coll=None, tags_coll=None,
        dry: bool = False, now: Optional[datetime] = None,
        recheck: bool = False, ref_fetch: Optional[Callable] = None,
        loader: Optional[Callable] = None, runs_coll=None) -> dict:
    """One pass: age out finished campaigns, then validate the fresh tags."""
    now = now or _now()
    db = None
    if coll is None:
        db = _db()
        if db is None:
            return {"error": "no mongo", "added": [], "rejected": [], "aged_out": []}
        coll = db[COLL]
    if runs_coll is None and db is not None:
        runs_coll = db[RUNS_COLL]

    try:
        uni = {s.upper() for s in U.load_universe(",".join(BASE_COMPONENTS))}
    except Exception as exc:                                   # noqa: BLE001
        # Fail CLOSED: with no universe to compare against every tag looks
        # missing and the job would add them all at once.
        log.warning("promo_curate: universe unavailable, standing down: %s", exc)
        return {"error": "universe unavailable", "added": [], "rejected": [],
                "aged_out": []}

    live = _live_tags(tags_coll, now)
    if live is None:
        # Fail CLOSED, same as the universe above: an unreadable tag collection
        # is not "no campaigns are live". Feeding an empty set to `age_out`
        # would age out EVERY added row on one Mongo blip and empty the promo
        # component out of `full` with a real write.
        log.warning("promo_curate: tags unavailable, standing down")
        return {"error": "tags unavailable", "added": [], "rejected": [],
                "aged_out": []}

    aged = age_out(coll, live, now, dry)

    cands = candidates(live)
    rows = _rows(coll)
    already = set(added_symbols(coll))

    populations = {k: 0 for k in ("in_universe", "adr", "not_common", "otc",
                                  "inactive", "unknown", "candidate")}
    queue = []
    skipped_rejected = 0
    for sym, cand in cands.items():
        if sym in uni:
            # Counted, never fetched and never written: the board shows plenty
            # of names the app already scans.
            populations["in_universe"] += 1
            continue
        if sym in already:
            continue
        if not recheck and _skip_rejected(rows.get(sym), cand):
            skipped_rejected += 1
            continue
        queue.append(cand)
    # Freshest S-tier campaigns first; the cap is a cap, not a filter.
    queue.sort(key=lambda c: (pc.TIER_ORDER.get(c["best_tier"] or "", 9),
                              -(c["last_tagged_at"] or now).timestamp()))

    added, rejected = [], []
    queue_remaining = 0
    for cand in queue:
        sym = cand["symbol"]
        # Validate FIRST, cap the ADDS — `traders.curate.run`'s own order. A
        # name that was going to be refused anyway must not eat a slot, or the
        # 170 sub-$2 tags would starve the handful that resolve, and the
        # populations split would only describe the first dozen names looked at.
        ok, cls, reason, facts = validate_promo(
            sym, uni, ref_fetch=ref_fetch, loader=loader, now=now)
        populations[cls if cls in populations else "candidate"] += 1
        src = {"origin": "promo_circuit", "reason_class": cls,
               "accounts": cand["accounts"], "best_tier": cand["best_tier"],
               "first_tagged_at": cand["first_tagged_at"],
               "last_tagged_at": cand["last_tagged_at"],
               "n_messages": cand["n_messages"], **facts}
        if not ok:
            rejected.append({"symbol": sym, "reason": reason, "reason_class": cls,
                             **facts})
            if not dry:
                _record(coll, sym, "rejected", reason, src)
            continue
        if len(added) >= limit:
            # Never silently drop: the overflow is reported AND counted, and is
            # simply picked up on the next run.
            queue_remaining += 1
            rejected.append({"symbol": sym, "reason": "over the per-run cap",
                             "reason_class": "capped"})
            continue
        cap = None if dry else warm_cap(sym)
        # A failed warm returns None — it must never ERASE the Massive reference
        # cap already on `facts`. Downstream ($700M zone_store gate) reads a
        # missing cap as "unknown", so overwriting a known cap with None would
        # blind a name the reference had already sized.
        cap = cap if cap is not None else facts.get("market_cap")
        if not dry:
            _record(coll, sym, "added", reason, {**src, "market_cap": cap})
        added.append({"symbol": sym, "reason": reason, **src, "market_cap": cap})

    # A name over the per-run cap is QUEUED, not refused — it rides in the
    # `rejected` list so the dry run prints it, but counting it as a rejection
    # in the stored summary would report it twice (once under `rejected`, once
    # under `queue_remaining`) and make the lane look stricter than it is.
    refused = [r for r in rejected if r.get("reason_class") != "capped"]
    log.info("promo_curate: %s added, %s refused, %s aged out, %s queued",
             len(added), len(refused), len(aged), queue_remaining)
    if not dry:
        _record_run(runs_coll, {
            "added": len(added), "rejected": len(refused),
            "capped": queue_remaining,
            "aged_out": len(aged), "skipped_rejected": skipped_rejected,
            "checked": len(queue), "queue_remaining": queue_remaining,
            "universe_before": len(uni), "populations": dict(populations),
            "added_symbols": [a["symbol"] for a in added],
        }, now)
    return {"added": added, "rejected": rejected, "aged_out": aged,
            "skipped_rejected": skipped_rejected, "checked": len(queue),
            "queue_remaining": queue_remaining, "universe_before": len(uni),
            "populations": populations, "dry": dry}


if __name__ == "__main__":                                     # pragma: no cover
    import sys
    out = run(dry="--dry" in sys.argv, recheck="--recheck" in sys.argv)
    if out.get("error"):
        print(f"promo_curate: {out['error']}")
        raise SystemExit(1)
    print(f"promo_curate: checked {out['checked']} tagged name(s) "
          f"({'DRY RUN' if out['dry'] else 'live'}); universe before "
          f"{out['universe_before']}")
    print(f"  populations: {out['populations']}")
    for a in out["added"]:
        cap = f" cap ${a['market_cap']/1e6:,.0f}M" if a.get("market_cap") else ""
        print(f"  + {a['symbol']:<6} {a['reason']}{cap}  "
              f"(tier {a['best_tier']}, {', '.join(a['accounts'])})")
    for r in out["rejected"]:
        print(f"  - {r['symbol']:<6} [{r.get('reason_class')}] {r['reason']}")
    for d in out["aged_out"]:
        print(f"  x {d['symbol']:<6} {d['reason']}")
    print(f"  skipped (already rejected): {out['skipped_rejected']}; "
          f"queued for the next run: {out['queue_remaining']}")
    raise SystemExit(0)
