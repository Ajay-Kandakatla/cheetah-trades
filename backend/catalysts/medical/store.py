"""🧬 Medical catalysts — Mongo storage (spec §3.6).

Collections
  med_catalyst_articles  _id = article key ("fh:…", "sec:…", "mv:…", "fda:…")
  med_catalyst_events    _id = event_key "{TICKER or UNRESOLVED:slug}|{type_dir}|{session_date}"
  med_catalyst_state     _id = "lease" | "cursor" | "baseline" | "massive_hwm" | "sec_tickers" | "edgar_seen"
  med_catalyst_alerts    _id = "MC:{event_key}" / "MC:{TICKER}|topline|{session}" (demand_alerts.claim_key docs)

NEVER write into `catalysts_cache` — the catalyst paper lane
(trading/catalyst_entry.py) reads that cache and no lane may consume a
medical event.

Every collection handle is injectable (`colls=`) — the tests pass in-memory
stand-ins; `tests/conftest.py` refuses a real MongoClient.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Optional

log = logging.getLogger("catalysts.medical.store")

ARTICLES = "med_catalyst_articles"
EVENTS = "med_catalyst_events"
STATE = "med_catalyst_state"
ALERTS = "med_catalyst_alerts"
ALL = (ARTICLES, EVENTS, STATE, ALERTS)
MERGE_SESSIONS = 3        # the ±3-day "nearby" window of the 2026-09-01 8-K study (memory eightk_event_study_2026_09_01)
DEDUPE_WINDOW_SEC = 86400
# "pivotal" ranks just under a numbered Phase 3: on a tie the more specific
# label wins (the classifier collapses "pivotal Phase 3" into "3" the same way).
_PHASE_RANK = {"1": 1.0, "1/2": 1.5, "2": 2.0, "2/3": 2.5, "pivotal": 2.99, "3": 3.0, "4": 4.0}


def _coll(name: str):
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[name] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("medical.store: no mongo for %s: %s", name, exc)
        return None


def colls(injected: Optional[dict] = None) -> dict:
    """{name: collection-or-None} — the injected map wins per name."""
    injected = injected or {}
    return {n: (injected[n] if n in injected else _coll(n)) for n in ALL}


def ensure_indexes(c: Optional[dict] = None) -> None:
    c = c or colls()
    try:
        if c.get(ARTICLES) is not None:
            c[ARTICLES].create_index([("tkey", 1)])
            c[ARTICLES].create_index([("published", -1)])
        if c.get(EVENTS) is not None:
            c[EVENTS].create_index([("ticker", 1), ("session_date", -1)])
            for f in ("session_date", "event_type", "modality", "areas"):
                c[EVENTS].create_index([(f, 1)])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: index build failed: %s", exc)


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------
def title_key(title: str) -> str:
    from news_search.core import _title_key
    return _title_key(title)


def tkey(ticker: Optional[str], title: str) -> str:
    return f"{(ticker or '').upper()}|{title_key(title)}"


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:48] or "item"


def event_key(ticker: Optional[str], type_dir: str, session_date, company: Optional[str] = None,
              title: str = "") -> str:
    sd = session_date.isoformat() if isinstance(session_date, date) else str(session_date)
    who = (ticker or "").upper() or ("UNRESOLVED:" + slug(company or title))
    return f"{who}|{type_dir}|{sd}"


# ---------------------------------------------------------------------------
# articles
# ---------------------------------------------------------------------------
def insert_article(coll, art: dict, *, classification: Optional[dict] = None,
                   now: Optional[datetime] = None) -> tuple:
    """-> ("new" | "dup" | "also_via", _id). A repeat of the same key is a
    dup; the same story via another provider (same TICKER|title key within
    ±DEDUPE_WINDOW_SEC) is ONE article that gains an `also_via` entry."""
    key = art["key"]
    if coll is None:
        return "new", key
    try:
        if coll.find_one({"_id": key}) is not None:
            return "dup", key
        p = float(art.get("published") or 0)
        tk = tkey(art.get("ticker"), art.get("title") or "")
        twin = coll.find_one({"tkey": tk, "published": {"$gte": p - DEDUPE_WINDOW_SEC,
                                                        "$lte": p + DEDUPE_WINDOW_SEC}})
        if twin is not None:
            coll.update_one({"_id": twin["_id"]}, {"$addToSet": {
                "also_via": {"provider": art.get("provider"), "url": art.get("url"), "key": key}}})
            return "also_via", twin["_id"]
        doc = dict(art, _id=key, tkey=tk, event_keys=[], classification=classification or {},
                   ingested_at=now or datetime.now(timezone.utc), also_via=[])
        res = coll.update_one({"_id": key}, {"$setOnInsert": doc}, upsert=True)
        if getattr(res, "upserted_id", None) is None:
            return "dup", key
        return "new", key
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: article write failed: %s", _redact(exc))
        return "new", key


def link_article(coll, article_id: str, event_keys: list) -> None:
    if coll is None or not event_keys:
        return
    try:
        coll.update_one({"_id": article_id}, {"$addToSet": {"event_keys": {"$each": list(event_keys)}}})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: article link failed: %s", _redact(exc))


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------
def _union(a, b) -> list:
    out = [x for x in (a or []) if x != "unclassified"]
    for x in b or []:
        if x != "unclassified" and x not in out:
            out.append(x)
    return out or ["unclassified"]


def higher_phase(a, b):
    ra, rb = _PHASE_RANK.get(str(a), 0.0) if a else 0.0, _PHASE_RANK.get(str(b), 0.0) if b else 0.0
    return a if ra >= rb and a else (b or a)


def _utc(x):
    if isinstance(x, datetime) and x.tzinfo is None:
        return x.replace(tzinfo=timezone.utc)
    return x


def _sd(x) -> str:
    return x.isoformat() if isinstance(x, date) else str(x)


def find_merge_target(coll, ev: dict, *, lo_date: date, hi_date: date) -> Optional[dict]:
    """The existing event a new one merges into (spec §3.6 rules):
      * same ticker + type_dir with session_date in [lo, hi] (MERGE_SESSIONS);
      * (i)  a `topline_unknown` merges into a topline of ANY direction in that window;
      * (ii) a topline with a trial merges into the same ticker + type_dir + trial
             at ANY earlier date still stored (one primary readout per trial per direction);
      * (iii) fix round 2 (live run: CLDX / ALKS each showed TWO topline rows): a
             DIRECTED topline merges into a `topline_unknown` in the window that
             came first ("Reports Topline Results From Phase 3 …" at 03:05, "Positive
             Results … Met Primary" at 06:58) — never across two different trials.
             merge_into then lifts the stored direction.
    Unresolved events never merge (no issuer to key on).

    Fix round 3 (OOS grade 2026-09-29: "…; Meets Week 48 Endpoints In ISLEND-1 And
    ISLEND-2 Trials" merged into GILD's KEYNOTE-D46/EVOKE-03 negative): for a
    trial readout (TRIAL_TYPES) EVERY window rule skips a target whose SUBJECT
    keys (trial acronym / NCT id / drug code / drug name, `subjects_of`) are
    present on both sides and disjoint — two different trials never merge. No
    key on either side, or another kind -> the old rule. Fix round 4: the test is
    `different_story` (trial keys first, then same-class drug keys) and it covers
    FDA approvals too (SPLIT_TYPES)."""
    if coll is None or not ev.get("ticker"):
        return None
    t = ev["ticker"]
    base_q = {"ticker": t, "session_date": {"$gte": _sd(lo_date), "$lte": _sd(hi_date)}}
    def same_story(hit) -> bool:
        return not different_story(ev, hit)
    try:
        for hit in coll.find(dict(base_q, type_dir=ev["type_dir"])):
            if same_story(hit):
                return hit
        if ev.get("event_type") == "topline" and ev.get("type_dir") == "topline_unknown":
            for hit in coll.find(dict(base_q, event_type="topline")):
                if same_story(hit):
                    return hit
        if ev.get("event_type") == "topline" and ev.get("direction") in DIRECTED:
            for hit in coll.find(dict(base_q, type_dir="topline_unknown")):
                if same_story(hit):
                    return hit
        if ev.get("event_type") == "topline" and ev.get("trials"):
            for tr in ev["trials"]:
                hit = coll.find_one({"ticker": t, "type_dir": ev["type_dir"], "trials": tr,
                                     "session_date": {"$lte": _sd(hi_date)}})
                if hit is not None:
                    return hit
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: merge lookup failed: %s", _redact(exc))
    return None


DIRECTED = ("positive", "negative", "mixed")


def subjects_of(ev: dict) -> frozenset:
    """An event's SUBJECT keys: `subjects` (classify.extract_subjects) plus its
    `trials` / `trial_keys` — a doc stored before fix round 3 carries trials only."""
    return frozenset(str(x).upper() for x in list(ev.get("subjects") or []) + list(ev.get("trials") or [])
                     + list(ev.get("trial_keys") or []) if x)


def trial_keys_of(ev: dict) -> frozenset:
    """fix round 4: the trial-IDENTITY keys (trial name / NCT id) — `trial_keys`
    (classify.extract_trial_keys) plus `trials`."""
    return frozenset(str(x).upper() for x in list(ev.get("trial_keys") or []) + list(ev.get("trials") or []) if x)


def drug_keys_of(ev: dict) -> frozenset:
    """The drug / product keys: every subject key that is not a trial key."""
    return subjects_of(ev) - trial_keys_of(ev)


def _generic_id(k: str) -> bool:
    """An INN ("selpercatinib") or a drug code ("PN-881") — the NON-brand name
    of a drug. A brand and an INN / code can name the SAME drug (Retevmo =
    selpercatinib), so only two keys of the SAME class can prove two drugs differ."""
    from .classify import _DRUG_CODE, _INN
    return bool(_INN.fullmatch(k.lower()) or _DRUG_CODE.fullmatch(k))


def _disjoint(a: frozenset, b: frozenset) -> bool:
    return bool(a) and bool(b) and not (a & b)


# Disjoint subject keys SPLIT trial readouts and (fix round 4, OOS grade #4: an
# approval of another product — ABT's Volt PMA merged into the Piccolo 510(k)
# event, MRK's EXZOLT blocked as a recap of Keytruda) FDA approvals.
TRIAL_TYPES = frozenset({"topline", "conference_data", "trial_milestone", "readout_scheduled"})
SPLIT_TYPES = TRIAL_TYPES | frozenset({"fda_approval"})


def different_story(a: dict, b: dict) -> bool:
    """Two same-name events are about different trials / products (fix round 4,
    critic 2026-09-29 #1/#3):
      * both carry TRIAL keys -> different iff those are disjoint (ATTAIN-1 vs
        ATTAIN-2 differ though both name orforglipron);
      * else compare DRUG keys: different only when both carry them, they are
        disjoint AND both sides hold a key of the same class (brand vs brand, or
        INN / code vs INN / code) — "Retevmo" vs "selpercatinib" may be one drug;
      * a trial-only side against a drug-only side ("Islatravir And Lenacapavir
        Meets …" vs "ISLEND-1 And ISLEND-2 Results") -> the SAME story (old rule).
    Only SPLIT_TYPES split; every other kind keeps the ticker + kind rule."""
    if a.get("event_type") not in SPLIT_TYPES:
        return False
    ta, tb = trial_keys_of(a), trial_keys_of(b)
    if ta and tb:
        return not (ta & tb)
    da, db = drug_keys_of(a), drug_keys_of(b)
    if not _disjoint(da, db):
        return False
    ga, gb = {k for k in da if _generic_id(k)}, {k for k in db if _generic_id(k)}
    return bool((ga and gb) or ((da - ga) and (db - gb)))


def same_subject(a: dict, b: dict) -> bool:
    """The rehash link (alerts._repeat at any date, alerts.event_origin): not a
    different story AND a SHARED key — for a trial kind a shared TRIAL key only
    (fix round 4, critic #1: a drug name alone linked ATTAIN-2 to ATTAIN-1)."""
    if different_story(a, b):
        return False
    if a.get("event_type") in TRIAL_TYPES:
        return bool(trial_keys_of(a) & trial_keys_of(b))
    return bool(subjects_of(a) & subjects_of(b))


def merge_into(coll, target: dict, ev: dict, *, impact_fn=None, session_fn=None, label_fn=None) -> str:
    """Add `ev`'s source and fields to `target`; the key NEVER changes (the
    push claim stays stable). Returns the target key.

    Fix round 2026-09-29 (critic):
      * an event whose impact a merge lifts to HIGH ("KOD topline, no phase"
        + a later "Phase 3" source) while its push says `not_high_impact` is
        re-armed to `pending` — the gate's `stale` rule still guards lateness;
      * fix round 2: a `topline_unknown` target takes a DIRECTED source's
        direction (type_dir / secondary_missed follow; `_id` never changes);
        `label_fn(merged) -> str` re-labels after any phase / direction lift;
      * `session_fn(published_at) -> date`: when the merged earliest
        publication maps to an EARLIER session than the stored one, the event
        moves to that session (same `_id`) and its reaction is nulled so the
        routine's fill recomputes base / liquidity / close on the right day."""
    srcs = ev.get("sources") or []
    phase = higher_phase(target.get("phase"), ev.get("phase"))
    merged = dict(target)
    merged["phase"] = phase
    upd = {
        "modality": _union(target.get("modality"), ev.get("modality")),
        "areas": _union(target.get("areas"), ev.get("areas")),
        "trials": sorted(set((target.get("trials") or []) + (ev.get("trials") or []))),
        "subjects": sorted(set((target.get("subjects") or []) + (ev.get("subjects") or []))),
        "trial_keys": sorted(set((target.get("trial_keys") or []) + (ev.get("trial_keys") or []))),
        "phase": phase,
        "rules_version": ev.get("rules_version") or target.get("rules_version"),
    }
    if target.get("type_dir") == "topline_unknown" and ev.get("direction") in DIRECTED:
        upd["direction"] = ev["direction"]
        upd["type_dir"] = ev.get("type_dir") or f"topline_{ev['direction']}"
        upd["secondary_missed"] = ev.get("secondary_missed")
    merged.update(upd)
    if label_fn is not None:
        try:
            upd["label"] = label_fn(merged)
        except Exception as exc:                                # noqa: BLE001
            log.warning("medical.store: relabel failed: %s", _redact(exc))
    if impact_fn is not None:
        upd["impact"] = "high" if impact_fn(merged) else "low"
    # Mongo hands datetimes back NAIVE (UTC); a new doc carries aware ones —
    # comparing the two raises, so both are made aware first.
    pa = [_utc(x) for x in (target.get("published_at"), ev.get("published_at")) if x is not None]
    ls = [_utc(x) for x in (target.get("last_seen_at"), ev.get("last_seen_at")) if x is not None]
    if pa:
        upd["published_at"] = min(pa)
    if ls:
        upd["last_seen_at"] = max(ls)
    if session_fn is not None and pa:
        try:
            sd_new = _sd(session_fn(min(pa)))
            if target.get("session_date") and sd_new[:10] < _sd(target["session_date"])[:10]:
                upd["session_date"] = sd_new
                upd["reaction"] = {"at_detection": None, "liquidity": None, "at_close": None, "fwd": None}
        except Exception as exc:                                # noqa: BLE001
            log.warning("medical.store: session remap failed: %s", _redact(exc))
    push = target.get("push") or {}
    if upd.get("impact") == "high" and target.get("impact") != "high" and push.get("reason") == "not_high_impact":
        upd["push"] = {"state": "pending", "reason": None, "at": None}
    try:
        coll.update_one({"_id": target["_id"]}, {"$set": upd,
                                                 "$addToSet": {"sources": {"$each": srcs}}})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: merge write failed: %s", _redact(exc))
    return target["_id"]


def insert_event(coll, ev: dict) -> tuple:
    """-> ("new" | "exists", key). `$setOnInsert` — a same-key re-insert changes nothing."""
    key = ev["_id"]
    if coll is None:
        return "new", key
    try:
        res = coll.update_one({"_id": key}, {"$setOnInsert": ev}, upsert=True)
        if getattr(res, "upserted_id", None) is None:
            return "exists", key
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: event write failed: %s", _redact(exc))
    return "new", key


def set_push(coll, key: str, state: str, reason: Optional[str], at: datetime) -> None:
    if coll is None:
        return
    try:
        coll.update_one({"_id": key}, {"$set": {"push": {"state": state, "reason": reason, "at": at}}})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: push stamp failed: %s", _redact(exc))


def set_fields(coll, key: str, fields: dict) -> None:
    if coll is None or not fields:
        return
    try:
        coll.update_one({"_id": key}, {"$set": fields})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: field write failed: %s", _redact(exc))


def events_since(coll, since_date: date, *, query: Optional[dict] = None) -> list:
    if coll is None:
        return []
    q = dict(query or {})
    q["session_date"] = {"$gte": _sd(since_date)}
    try:
        return list(coll.find(q))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: events read failed: %s", _redact(exc))
        return []


def events_for_tickers(coll, tickers) -> list:
    """Every stored event of these names, any date — the push gate's rehash
    lookback (alerts.REHASH_SESSIONS = None follows merge rule (ii): "any
    earlier date still stored")."""
    tickers = sorted({str(t).upper() for t in (tickers or []) if t})
    if coll is None or not tickers:
        return []
    try:
        return list(coll.find({"ticker": {"$in": tickers}}))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: ticker events read failed: %s", _redact(exc))
        return []


def owned_subjects(coll, tickers) -> dict:
    """fix round 4 (OOS grade #1): {TICKER: {KEY}} — the subject keys stored on a
    name's events that NO other name's event carries (a partner's or rival's
    product named in the issuer's headline — "Trodelvy–KEYTRUDA" — is never the
    issuer's own). Generic / disease / stop words are never keys worth matching."""
    from .classify import generic_key
    rows = events_for_tickers(coll, tickers)
    per = {}
    for r in rows:
        t = str(r.get("ticker") or "").upper()
        if not t:
            continue
        for k in subjects_of(r):
            if not generic_key(k):
                per.setdefault(t, set()).add(k)
    keys = sorted({k for v in per.values() for k in v})
    if coll is None or not keys:
        return per
    try:
        shared = list(coll.find({"subjects": {"$in": keys}}))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: owned-subjects read failed: %s", _redact(exc))
        return {}
    for r in shared:
        t = str(r.get("ticker") or "").upper()
        for k in subjects_of(r):
            for owner, v in per.items():
                if owner != t and k in v:
                    v.discard(k)
    return {t: v for t, v in per.items() if v}


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def get_state(coll, sid: str) -> dict:
    if coll is None:
        return {}
    try:
        return coll.find_one({"_id": sid}) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: state read failed: %s", _redact(exc))
        return {}


def set_state(coll, sid: str, fields: dict) -> None:
    if coll is None:
        return
    try:
        coll.update_one({"_id": sid}, {"$set": fields}, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: state write failed: %s", _redact(exc))


def claim_lease(coll, now: datetime, *, lease_sec: float, min_gap_sec: float, pid: int) -> bool:
    """find_one_and_update on _id "lease": free (not running, or claimed
    before now − lease_sec) AND started before now − min_gap_sec. A held
    lease makes the upsert collide on _id -> DuplicateKeyError -> False."""
    if coll is None:
        return True
    from datetime import timedelta
    try:
        from pymongo.errors import DuplicateKeyError
    except Exception:                                           # pragma: no cover
        DuplicateKeyError = KeyError                            # noqa: N806
    q = {"_id": "lease",
         "$or": [{"status": {"$ne": "running"}},
                 {"claimed_at": {"$lte": now - timedelta(seconds=lease_sec)}}],
         "$and": [{"$or": [{"started_at": {"$exists": False}},
                           {"started_at": {"$lte": now - timedelta(seconds=min_gap_sec)}}]}]}
    try:
        coll.find_one_and_update(q, {"$set": {"status": "running", "claimed_at": now,
                                                    "started_at": now, "pid": pid}}, upsert=True)
    except DuplicateKeyError:
        return False
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.store: lease claim failed: %s", _redact(exc))
        return False
    return True


def release_lease(coll, now: datetime) -> None:
    set_state(coll, "lease", {"status": "done", "done_at": now})


def _redact(exc) -> str:
    from observability.logsetup import redact
    return redact(f"{type(exc).__name__}: {exc}")


__all__ = ["ARTICLES", "EVENTS", "STATE", "ALERTS", "MERGE_SESSIONS", "colls", "ensure_indexes",
           "tkey", "event_key", "insert_article", "link_article", "find_merge_target", "merge_into",
           "insert_event", "set_push", "set_fields", "events_since", "events_for_tickers", "owned_subjects", "subjects_of", "trial_keys_of", "drug_keys_of", "different_story",
           "same_subject", "TRIAL_TYPES", "SPLIT_TYPES", "get_state", "set_state",
           "claim_lease", "release_lease", "higher_phase"]
