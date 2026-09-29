"""🧬 Medical catalysts routine — one pass (spec §3.9).

Ajay 2026-09-29 00:40 ET (verbatim): "can you add a new routine to scan for
https://pounce.ajaykandakatla.dev/sepa/KOD?tab=catalyst amd trails or other
medi cal nws and sector them separatively like new fdaapprovals or break
throughs like mrnaresearch how to catch thsse sectorsand companiesand add
right setup and alerts"

SCHEDULE — no crontab line. It rides promo_live's `*/5 4-19 * * 1-5` line
(backend/crontab:459): `catalysts.promo_live.__main__` calls
`_run_medical_hook()` inside a `finally`, after promo's own work. supercronic
runs WITHOUT `-overlapping`, so a job still running at its next tick makes that
tick SKIP: the hook is bounded by HOOK_BUDGET_SEC plus at most one 15 s sync
call. Every network await goes through `_call` = `asyncio.wait_for(min(
CALL_CAP_SEC, remaining))`; a timed-out leg stops for this pass (the next pass
resumes from the cursor). No thread: a daemon thread dies with `__main__`, a
non-daemon one holds the process past the tick (the lanes lesson).

ONE `asyncio.run` per process (finnhub_client caches an AsyncClient per loop).

UNMEASURED — setup: pending study.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time as _time
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional

from . import alerts as A
from . import reaction as R
from . import sources as SRC
from . import store as S

log = logging.getLogger("catalysts.medical.routine")

HOOK_BUDGET_SEC = 150        # promo_live's own run is 2–59 s; supercronic skips a tick that overlaps
CALL_CAP_SEC = 20            # longest single wrapped network await
CALL_MIN_SEC = 3             # never START a network call with less than this left
SYNC_RESERVE_SEC = 20        # a sync call (bulk_snapshot / load_prices, 15 s timeouts) starts only with this much left
SLICE_MAX = 36               # Finnhub names per run at FINNHUB_PER_MIN=20 → ~108 s worst case
LEASE_SEC = 900
MIN_GAP_SEC = 240
LOOKBACK_H = 96
MERGE_SESSIONS = S.MERGE_SESSIONS
CADENCE_SEC = A.CADENCE_SEC  # rides `*/5 4-19 * * 1-5 … catalysts.promo_live` (crontab:459)
WINDOW_ET = (time(4, 0), time(20, 0))
LOAD_PRICES_PER_RUN = 10
FILL_DAYS = 45
EDGAR_SEEN_MAX = 3000
EDGAR_EARLY_CUTOFF_ET = time(8, 0)   # before 08:00 ET the previous market day's 8-Ks are searched too
MEDICAL_INDUSTRIES = ("Biotechnology", "Medical Devices", "Drug Manufacturers - Specialty & Generic",
                      "Diagnostics & Research", "Medical Instruments & Supplies", "Drug Manufacturers - General")
FDA_KEEP_TYPES = frozenset({"fda_approval", "fda_crl", "fda_revoked", "clinical_hold", "safety"})
SKIP = object()

COUNTERS = ("roster", "sliced", "finnhub_calls", "finnhub_cache_hits", "edgar_hits", "edgar_exhibits",
            "no_exhibit", "massive_items", "fda_items", "articles_new", "articles_dup", "undated_dropped",
            "irrelevant_dropped", "roundup_dropped", "commentary_dropped", "non_medical_dropped",
            "non_medical_event_dropped", "unattributed", "events_new", "events_merged", "unresolved_ticker",
            "high_impact", "pushed", "muted", "claimed_elsewhere", "recap", "blocked_price",
            "blocked_dollar_vol", "blocked_unknown_liquidity", "stale", "closed_day", "baseline",
            "budget_exhausted", "call_timeouts", "finnhub_stopped", "edgar_stopped", "massive_stopped",
            "fda_stopped", "errors")


# ---------------------------------------------------------------------------
# budget
# ---------------------------------------------------------------------------
async def _call(factory: Callable, *, leg: str, deadline: float, clock: Callable, counts: dict):
    """Bound ONE network await: never started with < CALL_MIN_SEC left; cut at
    min(CALL_CAP_SEC, remaining); a timeout stops that leg for the pass."""
    if counts.get(f"{leg}_stopped"):
        return SKIP
    remaining = deadline - clock()
    if remaining < CALL_MIN_SEC:
        counts["budget_exhausted"] = counts.get("budget_exhausted", 0) + 1
        return SKIP
    try:
        return await asyncio.wait_for(factory(), timeout=min(CALL_CAP_SEC, remaining))
    except asyncio.TimeoutError:
        counts["call_timeouts"] = counts.get("call_timeouts", 0) + 1
        counts[f"{leg}_stopped"] = 1
        return SKIP


def _wrap_get(real_get: Callable, *, leg: str, deadline: float, clock: Callable, counts: dict):
    async def get(url, params=None, headers=None):
        res = await _call(lambda: real_get(url, params=params, headers=headers), leg=leg,
                          deadline=deadline, clock=clock, counts=counts)
        return None if res is SKIP else res
    return get


# ---------------------------------------------------------------------------
# defaults (the only I/O the tests replace)
# ---------------------------------------------------------------------------
def _cls():
    from . import classify
    return classify


def _default_universe() -> list:
    from sepa.universe import load_universe
    return list(load_universe("full") or [])


def _default_companies(syms: list) -> dict:
    from companies.store import get_many_cached
    return get_many_cached(list(syms)) or {}


def _default_healthcare() -> set:
    try:
        from companies.store import _get_db
        db = _get_db()
        if db is None:
            return set()
        from companies import sector_overrides
        # Suites 2026-09-29: this direct `companies` read must heal the sector
        # itself (tests/test_sector_overrides_2026_09_19) — an override can move
        # a name INTO or OUT OF Healthcare.
        q = {"$or": [{"sector": "Healthcare"}, {"symbol": {"$in": sorted(sector_overrides.SECTOR_OVERRIDES)}}]}
        return healthcare_symbols(db.companies.find(q, {"symbol": 1, "sector": 1, "industry": 1}))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.routine: healthcare read failed: %s", SRC.redact_exc(exc))
        return set()


def healthcare_symbols(docs) -> set:
    """PURE: the Healthcare names among company docs, AFTER the sector override."""
    from companies import sector_overrides
    out = set()
    for d in docs or ():
        d = sector_overrides.apply(dict(d)) or d
        if d.get("symbol") and str(d.get("sector") or "").strip() == "Healthcare":
            out.add(str(d["symbol"]).upper())
    return out


def _default_scope(owner: Optional[str]) -> set:
    try:
        from daytrading import signal_lab as SL
        from portfolio.store import list_holdings
        if owner is None:
            from portfolio.alerts import _resolve_owner
            owner = _resolve_owner()
        return set(SL.merge_holdings(SL.get_watchlist(owner), list_holdings(owner)).get("symbols") or [])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.routine: scope read failed: %s", SRC.redact_exc(exc))
        return set()


def _default_name_for(sym: str) -> Optional[str]:
    try:
        from sepa.company_names import name_for
        return name_for(sym)
    except Exception:                                           # noqa: BLE001
        return None


def _default_biotech() -> list:
    from sepa.universe import THEME_UNIVERSE
    return list(THEME_UNIVERSE.get("biotech") or [])


def _default_snapshot(syms: list) -> dict:
    from sepa import prices
    return prices.bulk_live_prices(list(syms)) or {}


def _default_frames(syms: list) -> dict:
    from sepa import prices
    return prices.bulk_cached_frames(list(syms)) or {}


def _default_load_prices(sym: str):
    from sepa import prices
    return prices.load_prices(sym, "1y")


def _default_caps(syms: list, last: dict) -> dict:
    try:
        from catalysts.promo_circuit import market_caps_for
        return market_caps_for(list(syms), last, cap=0) or {}      # cache only — display, never a gate
    except Exception as exc:                                    # noqa: BLE001
        log.debug("medical.routine: caps failed: %s", exc)
        return {}


def _default_finnhub_cached(sym: str) -> bool:
    try:
        from finnhub_client import cache as _c
        return _c.get("news", sym) is not None
    except Exception:                                           # noqa: BLE001
        return False


def _fx(fetchers: Optional[dict]) -> dict:
    f = dict(fetchers or {})
    f.setdefault("finnhub", SRC._default_finnhub)
    f.setdefault("finnhub_cached", _default_finnhub_cached)
    f.setdefault("edgar_get", SRC._default_edgar_get)
    f.setdefault("http_get", SRC._default_http_get)
    f.setdefault("massive_key", None)
    f.setdefault("universe", _default_universe)
    f.setdefault("companies", _default_companies)
    f.setdefault("healthcare", _default_healthcare)
    f.setdefault("biotech", _default_biotech)
    f.setdefault("scope", _default_scope)
    f.setdefault("name_for", _default_name_for)
    f.setdefault("snapshot", _default_snapshot)
    f.setdefault("frames", _default_frames)
    f.setdefault("load_prices", _default_load_prices)
    f.setdefault("caps", _default_caps)
    f.setdefault("pace_sec", 60.0 / SRC.FINNHUB_PER_MIN)
    f.setdefault("sender", None)
    return f


# ---------------------------------------------------------------------------
# roster + issuers
# ---------------------------------------------------------------------------
def roster(owner=None, *, fetchers: Optional[dict] = None) -> list:
    """full universe ∩ companies(sector Healthcare, industry ∈ MEDICAL_INDUSTRIES)
    ∪ THEME_UNIVERSE['biotech']. Order: tier 0 = holdings ∪ Signals watchlist,
    tier 1 = biotech theme, tier 2 = the rest; alphabetical within a tier."""
    fx = _fx(fetchers)
    uni = [str(s).upper() for s in fx["universe"]()]
    comp = fx["companies"](uni)
    bio = [str(s).upper() for s in fx["biotech"]()]
    names = {s for s in uni if (comp.get(s) or {}).get("sector") == "Healthcare"
             and (comp.get(s) or {}).get("industry") in MEDICAL_INDUSTRIES}
    names |= set(bio)
    scope = {str(s).upper() for s in (fx["scope"](owner) or [])}

    def tier(s):
        return 0 if s in scope else (1 if s in bio else 2)
    return sorted(names, key=lambda s: (tier(s), s))


def medical_issuers(rost, *, fetchers: Optional[dict] = None) -> frozenset:
    """§3.4.6: roster ∪ companies with sector Healthcare ∪ the biotech theme."""
    fx = _fx(fetchers)
    return frozenset({str(s).upper() for s in rost} | {str(s).upper() for s in fx["healthcare"]()}
                     | {str(s).upper() for s in fx["biotech"]()})


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _et_now(now) -> datetime:
    return R.as_et(now) if now is not None else datetime.now(R.ET)


def _medical_title(title: str, cl: Optional[dict] = None) -> bool:
    """§3.4.6 MEDICAL_WORDS or a modality / area hit (the classifier owns both)."""
    C = _cls()
    fn = getattr(C, "medical_words_hit", None) or getattr(C, "is_medical_text", None)
    if callable(fn):
        try:
            if fn(title):
                return True
        except Exception:                                       # noqa: BLE001
            pass
    else:
        rx = getattr(C, "MEDICAL_WORDS", None)
        if rx is not None and hasattr(rx, "search") and rx.search(title or ""):
            return True
    cl = cl or {}
    return any(m != "unclassified" for m in cl.get("modality") or []) or \
        any(a != "unclassified" for a in cl.get("areas") or [])


class _Names:
    """Company names: sepa.company_names first, the SEC company_tickers title
    when that is None (§3.4.3 rule 1)."""

    def __init__(self, name_for: Callable, sec_titles: dict):
        self._nf, self._sec, self._memo = name_for, sec_titles or {}, {}

    def name(self, sym: str) -> Optional[str]:
        sym = (sym or "").upper()
        if sym not in self._memo:
            n = None
            try:
                n = self._nf(sym)
            except Exception:                                   # noqa: BLE001
                n = None
            self._memo[sym] = n or self._sec.get(sym) or None
        return self._memo[sym]

    def forms(self, sym: str) -> tuple:
        try:
            return tuple(_cls().name_forms(sym, self.name(sym)) or ())
        except Exception:                                       # noqa: BLE001
            return ()


def _ev_doc(ev: dict, art: dict, cl: dict, *, ticker, company, now_utc: datetime, baseline: bool) -> dict:
    T = _tax()
    pub_utc = datetime.fromtimestamp(float(art["published"]), tz=timezone.utc)
    pub_et = R.as_et(pub_utc)
    sd = R.session_date_for(pub_et)
    base = {"event_type": ev.get("event_type"), "subtype": ev.get("subtype"),
            "direction": ev.get("direction"), "phase": ev.get("phase"), "regulator": ev.get("regulator")}
    td = T.type_dir(base)
    trials = [ev["trial"]] if ev.get("trial") else []
    key = S.event_key(ticker, td, sd, company=company, title=art.get("title") or "")
    doc = dict(base, _id=key, event_key=key, ticker=ticker, company=company, type_dir=td,
               trials=trials, secondary_missed=ev.get("secondary_missed"),
               dilutive=ev.get("dilutive"), cue=ev.get("cue"),
               congress=ev.get("congress"), partial=ev.get("partial"),
               modality=list(cl.get("modality") or ["unclassified"]),
               areas=list(cl.get("areas") or ["unclassified"]),
               session_date=sd.isoformat(), released=R.released_bucket(pub_et),
               headline=art.get("title"), published_at=pub_utc, first_seen_at=now_utc,
               last_seen_at=now_utc,
               sources=[{"provider": art.get("provider"), "source": art.get("source"),
                         "title": art.get("title"), "url": art.get("url"),
                         "published_et": pub_et.isoformat(), "article_key": art.get("key")}],
               push={"state": "pending", "reason": None, "at": None},
               reaction={"at_detection": None, "liquidity": None, "at_close": None, "fwd": None},
               rules_version=cl.get("rules_version"), backfill=False, baseline=bool(baseline),
               from_commentary=bool(ev.get("from_commentary")))
    doc["impact"] = "high" if T.is_high_impact(doc) else "low"
    doc["label"] = T.event_label(doc)
    return doc


def _tax():
    from . import taxonomy
    return taxonomy


# ---------------------------------------------------------------------------
# the pass
# ---------------------------------------------------------------------------
def run_tick(*, now=None, push: bool = True, dry_run: bool = False, fetchers: Optional[dict] = None,
             colls: Optional[dict] = None, owner: Optional[str] = None,
             budget_sec: float = HOOK_BUDGET_SEC, clock: Callable = _time.monotonic) -> dict:
    """ONE event loop per cron process."""
    return asyncio.run(_tick(now=now, push=push, dry_run=dry_run, fetchers=fetchers, colls=colls,
                             owner=owner, budget_sec=budget_sec, clock=clock))


async def _tick(*, now, push, dry_run, fetchers, colls, owner, budget_sec, clock) -> dict:
    t_wall = _time.monotonic()
    counts = {k: 0 for k in COUNTERS}
    now_et = _et_now(now)
    now_utc = now_et.astimezone(timezone.utc)
    if not (WINDOW_ET[0] <= now_et.time() < WINDOW_ET[1]):
        return {"ran": False, "reason": "outside 04:00-20:00 ET"}
    fx = _fx(fetchers)
    c = S.colls(colls)
    st = c[S.STATE]
    if not S.claim_lease(st, now_utc, lease_sec=LEASE_SEC, min_gap_sec=MIN_GAP_SEC, pid=os.getpid()):
        return {"ran": False, "reason": "lease held"}
    out = {"ran": True, "counts": counts, "reason": None}
    try:
        deadline = clock() + float(budget_sec)
        await _body(now_et=now_et, now_utc=now_utc, fx=fx, c=c, counts=counts, deadline=deadline,
                    clock=clock, push=push, dry_run=dry_run, owner=owner, out=out)
    except Exception as exc:                                    # noqa: BLE001
        counts["errors"] += 1
        out["reason"] = SRC.redact_exc(exc)
        log.warning("medical.routine: pass failed: %s", out["reason"])
    finally:
        S.release_lease(st, now_utc)
    out["elapsed_sec"] = round(_time.monotonic() - t_wall, 2)
    if not dry_run:
        try:
            from supply_demand import alert_status as AS
            AS.record_pass(A.KIND, counts, now_et, reason=out.get("reason"),
                           coll=(colls or {}).get("alert_pass_latest"))
        except Exception as exc:                                # noqa: BLE001
            log.warning("medical.routine: record_pass failed: %s", SRC.redact_exc(exc))
    log.info("medical.routine: %s", json.dumps({"counts": counts, "elapsed_sec": out["elapsed_sec"]}))
    return out


async def _body(*, now_et, now_utc, fx, c, counts, deadline, clock, push, dry_run, owner, out):
    st, arts_c, ev_c = c[S.STATE], c[S.ARTICLES], c[S.EVENTS]
    C = _cls()
    today = now_et.date().isoformat()

    def remaining():
        return deadline - clock()

    def call(factory, leg):
        return _call(factory, leg=leg, deadline=deadline, clock=clock, counts=counts)

    edgar_get = _wrap_get(fx["edgar_get"], leg="edgar", deadline=deadline, clock=clock, counts=counts)
    http_massive = _wrap_get(fx["http_get"], leg="massive", deadline=deadline, clock=clock, counts=counts)
    http_fda = _wrap_get(fx["http_get"], leg="fda", deadline=deadline, clock=clock, counts=counts)

    # SEC titles, once per ET day (name fallback + FDA-page company match)
    # stored as [[TICKER, title], …] — a ticker is never used as a Mongo key
    sec_doc = S.get_state(st, "sec_tickers")
    stored = {str(t): str(n) for t, n in (sec_doc.get("titles") or [])}
    sec_titles = stored if (sec_doc.get("day") == today and stored) else None
    if sec_titles is None:
        sec_titles = await SRC.sec_company_titles(get=edgar_get)
        if sec_titles:
            S.set_state(st, "sec_tickers", {"day": today, "titles": sorted(sec_titles.items())})
        else:
            sec_titles = stored
    names = _Names(fx["name_for"], sec_titles)

    rost = roster(owner, fetchers=fx)
    counts["roster"] = len(rost)
    issuers = medical_issuers(rost, fetchers=fx)

    base_doc = S.get_state(st, "baseline")
    if not base_doc:
        base_doc = {"started_at": now_utc, "lap_complete_at": None, "names_done": []}
        S.set_state(st, "baseline", base_doc)
    lap_done = base_doc.get("lap_complete_at") is not None
    names_done = set(base_doc.get("names_done") or [])

    queue = []                                                  # (article, baseline_flag)

    # ── 1. discovery: EDGAR 8-K EX-99.1 ──────────────────────────────────
    seen_doc = S.get_state(st, "edgar_seen")
    edgar_first = not seen_doc
    seen = list(seen_doc.get("adsh") or [])
    day_from = now_et.date()
    if now_et.time() < EDGAR_EARLY_CUTOFF_ET:
        day_from = R.prev_market_day(day_from)
    hits = await SRC.edgar_8k_hits(day_from.isoformat(), now_et.date().isoformat(), get=edgar_get,
                                   counts=counts)
    for h in hits:
        if h["adsh"] in seen or counts.get("edgar_stopped") or remaining() < CALL_MIN_SEC:
            continue
        lead = await SRC.edgar_exhibit_lead(h.get("cik"), h["adsh"], get=edgar_get)
        if counts.get("edgar_stopped"):
            break
        if lead is None:
            continue                                            # fetch failed -> retried next pass
        if not lead:
            counts["no_exhibit"] += 1                           # no EX-99.1 (credit-agreement boilerplate hit)
            seen.append(h["adsh"])
            continue
        counts["edgar_exhibits"] += 1
        acc = await SRC.edgar_acceptance(h.get("cik"), h["adsh"], get=edgar_get)
        if counts.get("edgar_stopped"):
            break
        art = SRC.edgar_article(h, lead, acc)
        seen.append(h["adsh"])
        if art is None:
            counts["undated_dropped"] += 1
            continue
        queue.append((art, edgar_first or not lap_done))
    S.set_state(st, "edgar_seen", {"adsh": seen[-EDGAR_SEEN_MAX:], "at": now_utc})

    # ── 2. discovery: Massive market-wide (1 call) ───────────────────────
    hwm_doc = S.get_state(st, "massive_hwm")
    massive_first = not hwm_doc
    since = R.as_et(hwm_doc.get("published_utc")) if hwm_doc.get("published_utc") else None
    since = since or (now_et - timedelta(hours=LOOKBACK_H))
    mitems = await SRC.massive_marketwide(since, get=http_massive, key=fx["massive_key"], counts=counts)
    hwm = max([a["published"] for a in mitems] or [0.0])
    for a in mitems:
        issuer = SRC.resolve_issuer_massive(a["title"], a.get("tickers_tagged"), names.forms)
        a["ticker"] = issuer
        if not ((issuer and issuer in issuers) or _medical_title(
                a["title"], C.classify(a["title"], context="", ticker=None, forms=(), issuer_medical=None))):
            counts["non_medical_dropped"] += 1
            continue
        queue.append((a, massive_first or not lap_done))
    if hwm:
        S.set_state(st, "massive_hwm", {"published_utc": datetime.fromtimestamp(hwm, tz=timezone.utc)})
    elif massive_first and not counts.get("massive_stopped"):
        S.set_state(st, "massive_hwm", {"published_utc": since.astimezone(timezone.utc)})

    # ── 3. discovery: FDA press releases ─────────────────────────────────
    fda_doc = S.get_state(st, "fda_seen")
    fda_first = not fda_doc

    def fda_keeps(title: str) -> bool:
        try:
            cl = C.classify(title, context="", ticker=None, forms=(), issuer_medical=None)
        except Exception:                                       # noqa: BLE001
            return False
        return any(e.get("event_type") in FDA_KEEP_TYPES for e in cl.get("events") or [])

    def want_page(it) -> bool:
        key = SRC.article_key({"provider": "fda_rss", "guid": it.get("guid"), "url": it.get("url")})
        if arts_c is not None:
            try:
                if arts_c.find_one({"_id": key}) is not None:
                    return False
            except Exception:                                   # noqa: BLE001
                return False
        return fda_keeps(it.get("title") or "")

    fitems = await SRC.fda_press_releases(get=http_fda, want_page=want_page, counts=counts)
    for a in fitems:
        if not fda_keeps(a["title"]):
            counts["non_medical_dropped"] += 1
            continue
        a["ticker"] = SRC.match_company_title(a.get("company"), sec_titles)
        queue.append((a, fda_first or not lap_done))
    if fda_first and not counts.get("fda_stopped"):
        S.set_state(st, "fda_seen", {"first_run_at": now_utc})

    # ── 4. roster slice: Finnhub per ticker ──────────────────────────────
    cur = S.get_state(st, "cursor")
    i = int(cur.get("i") or 0) if cur.get("day") == today else 0
    if i >= len(rost):
        i = 0
    fetched = []
    slice_ = rost[i:i + SLICE_MAX]
    for n, sym in enumerate(slice_):
        if counts.get("finnhub_stopped"):
            break
        if remaining() < CALL_MIN_SEC:
            counts["budget_exhausted"] += 1
            break
        cached = bool(fx["finnhub_cached"](sym))
        company = names.name(sym)
        forms = names.forms(sym)
        rows = await call(lambda s=sym: fx["finnhub"](s, SRC.FINNHUB_DAYS_BACK), "finnhub")
        if rows is SKIP:
            break
        counts["finnhub_calls"] += 1
        if cached:
            counts["finnhub_cache_hits"] += 1
        fetched.append(sym)
        first_fetch = sym not in names_done
        arts = await SRC.finnhub_articles(sym, company=company, forms=forms, counts=counts,
                                          fetch=_rows_fetch(rows))
        for a in arts:
            queue.append((a, (not lap_done) or first_fetch))
        if not cached and fx["pace_sec"] and n < len(slice_) - 1:
            await asyncio.sleep(max(0.0, min(float(fx["pace_sec"]), remaining() - CALL_MIN_SEC)))
    counts["sliced"] = len(fetched)
    ni = i + len(fetched)
    if ni >= len(rost):
        ni = 0
    S.set_state(st, "cursor", {"i": ni, "day": today, "roster_hash": _roster_hash(rost)})
    names_done |= set(fetched)
    upd = {"names_done": sorted(names_done)}
    if not lap_done and rost and set(rost) <= names_done:
        upd["lap_complete_at"] = now_utc
    S.set_state(st, "baseline", upd)

    # ── 5. classify, dedupe, store ───────────────────────────────────────
    from news_search.core import fresh
    new_events = []
    # OLDEST first (critic 2026-09-29): the first article of a story creates
    # the event, so its session_date is the earliest publication's session —
    # newest-first keyed ABBV's 09-28 04:02 approval to 09-29.
    queue.sort(key=lambda q: float(q[0].get("published") or 0.0))
    for art, is_base in queue:
        if not fresh([art], window_hours=LOOKBACK_H, now=now_utc.timestamp()):
            continue
        tk = art.get("ticker")
        forms = names.forms(tk) if tk else ()
        try:
            cl = C.classify(art["title"], context=art.get("context") or "", ticker=tk, forms=forms,
                            issuer_medical=(tk in issuers) if tk else None)
        except Exception as exc:                                # noqa: BLE001
            counts["errors"] += 1
            log.warning("medical.routine: classify failed: %s", SRC.redact_exc(exc))
            continue
        status, aid = S.insert_article(arts_c, art, classification=cl, now=now_utc)
        if status != "new":
            counts["articles_dup"] += 1
            continue
        counts["articles_new"] += 1
        if cl.get("roundup"):
            counts["roundup_dropped"] += 1
            continue
        if cl.get("commentary") and not cl.get("events"):
            counts["commentary_dropped"] += 1
            continue
        counts["non_medical_event_dropped"] += sum(
            1 for d in (cl.get("dropped") or []) if str(d).startswith("non_medical_event"))
        # EDGAR (the filer) and FDA RSS (the page company) name the issuer
        # structurally; only headline feeds need the title to attribute it.
        if tk and cl.get("attributed") is False and art.get("provider") in ("finnhub", "massive"):
            counts["unattributed"] += 1
            continue
        keys = []
        company = names.name(tk) if tk else (art.get("company") or None)
        for ev in cl.get("events") or []:
            doc = _ev_doc(ev, art, cl, ticker=tk, company=company, now_utc=now_utc, baseline=is_base)
            sd = date.fromisoformat(doc["session_date"])
            target = S.find_merge_target(ev_c, doc, lo_date=R.add_market_days(sd, -MERGE_SESSIONS),
                                         hi_date=R.add_market_days(sd, MERGE_SESSIONS))
            if target is not None:
                keys.append(S.merge_into(ev_c, target, doc, impact_fn=_tax().is_high_impact,
                                         session_fn=_session_of, label_fn=_tax().event_label))
                counts["events_merged"] += 1
                continue
            if doc["from_commentary"]:
                continue
            status, key = S.insert_event(ev_c, doc)
            keys.append(key)
            if status == "new":
                counts["events_new"] += 1
                if not tk:
                    counts["unresolved_ticker"] += 1
                if doc["impact"] == "high":
                    counts["high_impact"] += 1
                new_events.append(doc)
            else:
                counts["events_merged"] += 1
        S.link_article(arts_c, aid, keys)

    # ── 6. reactions ─────────────────────────────────────────────────────
    _detect(new_events, fx=fx, ev_c=ev_c, now_et=now_et, remaining=remaining, counts=counts)
    _fill(ev_c, fx=fx, now_et=now_et)

    # ── 7. push ──────────────────────────────────────────────────────────
    pending = [e for e in S.events_since(ev_c, now_et.date() - timedelta(days=FILL_DAYS))
               if (e.get("push") or {}).get("state") == "pending"]
    if pending:
        prior = S.events_since(ev_c, R.add_market_days(now_et.date(), -(A.RECAP_SESSIONS + MERGE_SESSIONS + 5)))
        res = A.run_push(pending, now_et=now_et, prior=prior, claim_coll=c[S.ALERTS], events_coll=ev_c,
                         owner=owner, sender=fx["sender"], act=bool(push) and not dry_run, counts=counts)
        out["messages"] = res["messages"]
        out["decisions"] = res["decisions"]


def _session_of(published) -> date:
    """UTC publication -> the ET session it belongs to (reaction.session_date_for)."""
    return R.session_date_for(R.as_et(published))


def _roster_hash(rost) -> str:
    import hashlib
    return hashlib.md5(",".join(rost).encode()).hexdigest()[:12]


def _rows_fetch(rows):
    async def f(_sym, _days):
        return rows
    return f


def _detect(new_events: list, *, fx, ev_c, now_et, remaining, counts) -> None:
    """Detection reaction for this pass's new events: one snapshot, one frame read."""
    syms = sorted({e["ticker"] for e in new_events if e.get("ticker")})
    if not syms:
        return
    try:
        frames = fx["frames"](syms) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.routine: frames failed: %s", SRC.redact_exc(exc))
        frames = {}
    loaded = 0
    for s in syms:
        if s in frames or loaded >= LOAD_PRICES_PER_RUN:
            continue
        if remaining() < SYNC_RESERVE_SEC:
            break
        try:
            df = fx["load_prices"](s)
            if df is not None and len(df):
                frames[s] = df
        except Exception as exc:                                # noqa: BLE001
            log.warning("medical.routine: load_prices %s failed: %s", s, SRC.redact_exc(exc))
        loaded += 1
    snap = {}
    if remaining() >= SYNC_RESERVE_SEC:
        try:
            snap = fx["snapshot"](syms) or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("medical.routine: snapshot failed: %s", SRC.redact_exc(exc))
    bases = {}
    for e in new_events:
        t = e.get("ticker")
        if not t:
            continue
        sd = date.fromisoformat(e["session_date"])
        cf = R.closed_frame(frames.get(t), now_et)
        base = R.base_close(cf, snap.get(t), sd, now_et)
        liq = R.liquidity(cf, sd)
        bases[t] = base[0]
        det = R.at_detection(snap.get(t), base, now_et, avg_vol50=liq.get("avg_vol50"),
                             published_et=e.get("published_at"), session_date=sd)
        e["reaction"] = {"at_detection": det,
                         "liquidity": dict(liq, base_close=base[0], base_basis=base[1], market_cap=None),
                         "at_close": None, "fwd": None}
    caps = {}
    try:
        caps = fx["caps"](list(bases), {k: v for k, v in bases.items() if v}) or {}
    except Exception:                                           # noqa: BLE001
        caps = {}
    for e in new_events:
        t = e.get("ticker")
        if not t or not e.get("reaction"):
            continue
        e["reaction"]["liquidity"]["market_cap"] = caps.get(t)
        S.set_fields(ev_c, e["_id"], {"reaction": e["reaction"]})


def _fill(ev_c, *, fx, now_et) -> None:
    """at_close / fwd (and a still-unknown base) for events in the last
    FILL_DAYS days — Mongo frames only, never the network."""
    evs = [e for e in S.events_since(ev_c, now_et.date() - timedelta(days=FILL_DAYS)) if e.get("ticker")]
    todo = []
    for e in evs:
        reac = e.get("reaction") or {}
        fwd = reac.get("fwd") or {}
        liq = reac.get("liquidity") or {}
        if reac.get("at_close") is None or not fwd.get("matured_21d") or liq.get("base_close") is None:
            todo.append(e)
    if not todo:
        return
    try:
        frames = fx["frames"](sorted({e["ticker"] for e in todo})) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.routine: fill frames failed: %s", SRC.redact_exc(exc))
        return
    for e in todo:
        cf = R.closed_frame(frames.get(e["ticker"]), now_et)
        if cf is None:
            continue
        sd = date.fromisoformat(str(e["session_date"])[:10])
        reac = dict(e.get("reaction") or {})
        liq = dict(reac.get("liquidity") or {})
        if liq.get("base_close") is None:
            b = R.base_close(cf, None, sd, now_et)
            if b[0] is not None:
                liq.update(R.liquidity(cf, sd), base_close=b[0], base_basis=b[1])
        base = liq.get("base_close")
        if base is None:
            continue
        ac = R.at_close(cf, sd, base, liq.get("avg_vol50"))
        fwd = R.forward(cf, sd, base, (ac or {}).get("close"))
        reac.update(liquidity=liq, at_close=ac, fwd=fwd)
        S.set_fields(ev_c, e["_id"], {"reaction": reac})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def explain(symbol: str, *, now=None, colls: Optional[dict] = None) -> list:
    c = S.colls(colls)
    now_et = _et_now(now)
    evs = [e for e in S.events_since(c[S.EVENTS], now_et.date() - timedelta(days=FILL_DAYS),
                                     query={"ticker": symbol.upper()})]
    prior = S.events_since(c[S.EVENTS], R.add_market_days(now_et.date(), -(A.RECAP_SESSIONS + 10)))
    return [dict(A.explain(e, now_et=now_et, prior=prior), push=e.get("push"),
                 sources=len(e.get("sources") or []), reaction=e.get("reaction"))
            for e in evs]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m catalysts.medical.routine")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--budget", type=float, default=HOOK_BUDGET_SEC)
    ap.add_argument("--explain", default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    # httpx logs every request URL (Finnhub token= / Massive apiKey=) at INFO
    from observability.logsetup import install_redaction
    install_redaction()
    if a.explain:
        print(json.dumps(explain(a.explain), indent=2, default=str))
        return 0
    res = run_tick(push=not a.no_push, dry_run=a.dry_run, budget_sec=a.budget)
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
