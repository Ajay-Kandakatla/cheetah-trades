"""🧬 Medical catalysts — storage (catalysts/medical/store.py, spec §3.6).

In-memory Mongo stand-in (`FakeColl`, reused by the other test_med_* files):
tests/conftest.py refuses a real MongoClient. Pins article idempotence, the
cross-source `also_via` dedupe, the event-merge rules (window, topline_unknown,
same trial, commentary never creates) and the lease.
"""
from __future__ import annotations

import copy
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import store as S   # noqa: E402


# ---------------------------------------------------------------------------
# in-memory collection (the subset of pymongo the medical package uses)
# ---------------------------------------------------------------------------
def _get(doc, path):
    cur = doc
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None, False
        cur = cur[p]
    return cur, True


def _match_val(v, cond, present) -> bool:
    if isinstance(cond, dict) and cond and all(str(k).startswith("$") for k in cond):
        for op, arg in cond.items():
            if op == "$exists":
                if bool(present) != bool(arg):
                    return False
            elif op == "$ne":
                if (v == arg) or (isinstance(v, list) and arg in v):
                    return False
            elif op == "$in":
                vals = v if isinstance(v, list) else [v]
                if not any(x in arg for x in vals):
                    return False
            elif op in ("$gte", "$lte", "$gt", "$lt"):
                if v is None or not present:
                    return False
                try:
                    ok = {"$gte": v >= arg, "$lte": v <= arg, "$gt": v > arg, "$lt": v < arg}[op]
                except TypeError:
                    return False
                if not ok:
                    return False
            else:
                raise NotImplementedError(op)
        return True
    if isinstance(v, list) and not isinstance(cond, list):
        return cond in v
    return present and v == cond


def match(doc, q) -> bool:
    for k, cond in (q or {}).items():
        if k == "$or":
            if not any(match(doc, sub) for sub in cond):
                return False
            continue
        if k == "$and":
            if not all(match(doc, sub) for sub in cond):
                return False
            continue
        v, present = _get(doc, k)
        if not _match_val(v, cond, present):
            return False
    return True


class DuplicateKeyError(Exception):
    pass


class FakeColl:
    def __init__(self, docs=None):
        self.docs = {}
        for d in docs or []:
            self.docs[d["_id"]] = copy.deepcopy(d)
        self.writes = 0
        self.indexes = []

    # reads
    def find_one(self, q=None, projection=None):
        for d in self.docs.values():
            if match(d, q or {}):
                return copy.deepcopy(d)
        return None

    def find(self, q=None, projection=None):
        return [copy.deepcopy(d) for d in self.docs.values() if match(d, q or {})]

    # writes
    def _apply(self, doc, upd, inserting):
        for op, fields in upd.items():
            if op == "$set" or (op == "$setOnInsert" and inserting):
                for k, v in fields.items():
                    doc[k] = copy.deepcopy(v)
            elif op == "$setOnInsert":
                continue
            elif op == "$addToSet":
                for k, v in fields.items():
                    arr = doc.setdefault(k, [])
                    items = v["$each"] if isinstance(v, dict) and "$each" in v else [v]
                    for it in items:
                        if it not in arr:
                            arr.append(copy.deepcopy(it))
            elif op == "$min":
                for k, v in fields.items():
                    doc[k] = v if doc.get(k) is None else min(doc[k], v)
            elif op == "$max":
                for k, v in fields.items():
                    doc[k] = v if doc.get(k) is None else max(doc[k], v)
            else:
                raise NotImplementedError(op)

    def update_one(self, q, upd, upsert=False):
        self.writes += 1
        for _id, d in self.docs.items():
            if match(d, q):
                self._apply(d, upd, False)
                return SimpleNamespace(upserted_id=None, matched_count=1)
        if not upsert:
            return SimpleNamespace(upserted_id=None, matched_count=0)
        new = {k: v for k, v in q.items() if not k.startswith("$") and not isinstance(v, dict)}
        self._apply(new, upd, True)
        if new.get("_id") in self.docs:
            raise DuplicateKeyError(new["_id"])
        self.docs[new["_id"]] = new
        return SimpleNamespace(upserted_id=new["_id"], matched_count=0)

    def find_one_and_update(self, q, upd, upsert=False):
        for d in self.docs.values():
            if match(d, q):
                before = copy.deepcopy(d)
                self._apply(d, upd, False)
                return before
        if upsert:
            from pymongo.errors import DuplicateKeyError as PDK
            if q.get("_id") in self.docs:
                raise PDK("dup")
            new = {"_id": q["_id"]}
            self._apply(new, upd, True)
            self.docs[new["_id"]] = new
        return None

    def replace_one(self, q, doc, upsert=False):
        self.writes += 1
        self.docs[q["_id"]] = copy.deepcopy(doc)

    def delete_one(self, q):
        self.docs.pop(q.get("_id"), None)

    def create_index(self, spec, **kw):
        self.indexes.append(spec)


def fake_colls() -> dict:
    return {S.ARTICLES: FakeColl(), S.EVENTS: FakeColl(), S.STATE: FakeColl(), S.ALERTS: FakeColl(),
            "alert_pass_latest": FakeColl()}


# ---------------------------------------------------------------------------
# articles
# ---------------------------------------------------------------------------
def _art(key="fh:1", title="Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints",
         published=1_790_000_000.0, provider="finnhub", ticker="KOD", url="https://x/1"):
    return {"key": key, "title": title, "published": published, "provider": provider,
            "ticker": ticker, "url": url, "source": "Benzinga"}


def test_article_idempotence_same_key_is_a_dup_and_writes_nothing_else():
    c = FakeColl()
    assert S.insert_article(c, _art())[0] == "new"
    n = len(c.docs)
    assert S.insert_article(c, _art())[0] == "dup"
    assert len(c.docs) == n == 1


def test_same_story_via_two_providers_is_ONE_article_with_also_via():
    """The same Benzinga headline via Finnhub and Massive (Massive resolved the
    issuer to KOD) — one article, the second provider recorded in also_via."""
    c = FakeColl()
    assert S.insert_article(c, _art())[0] == "new"
    st, aid = S.insert_article(c, _art(key="mv:abc", provider="massive", published=1_790_000_300.0,
                                       url="https://benzinga/kod"))
    assert st == "also_via" and aid == "fh:1"
    assert len(c.docs) == 1
    assert c.docs["fh:1"]["also_via"] == [{"provider": "massive", "url": "https://benzinga/kod", "key": "mv:abc"}]


def test_NEGATIVE_same_title_two_days_apart_or_other_issuer_is_a_new_article():
    c = FakeColl()
    S.insert_article(c, _art())
    assert S.insert_article(c, _art(key="fh:2", published=1_790_000_000.0 + 2 * 86400))[0] == "new"
    assert S.insert_article(c, _art(key="fh:3", ticker="MRNA"))[0] == "new"


def test_tkey_and_event_key_shapes():
    assert S.tkey("kod", "Kodiak Sciences Soars!") == "KOD|kodiaksciencessoars"
    assert S.event_key("KOD", "topline_positive", date(2026, 9, 28)) == "KOD|topline_positive|2026-09-28"
    assert S.event_key(None, "fda_approval", "2026-09-29", company="Egetis") == \
        "UNRESOLVED:egetis|fda_approval|2026-09-29"


# ---------------------------------------------------------------------------
# event merge rules
# ---------------------------------------------------------------------------
def _ev(ticker="KOD", td="topline_positive", sd="2026-09-28", trials=("DAYBREAK",), **kw):
    et = td.split("_")[0] if td.startswith("topline") else td
    d = {"_id": S.event_key(ticker, td, sd), "ticker": ticker, "type_dir": td, "event_type": et,
         "session_date": sd, "trials": list(trials), "phase": "3", "modality": ["unclassified"],
         "areas": ["ophthalmology"], "sources": [{"provider": "finnhub", "title": "t", "article_key": "a"}],
         "published_at": datetime(2026, 9, 28, 6, 34, tzinfo=timezone.utc),
         "last_seen_at": datetime(2026, 9, 28, 7, 0, tzinfo=timezone.utc),
         "push": {"state": "pending"}}
    d.update(kw)
    return d


def _win(sd):
    d = date.fromisoformat(sd)
    return dict(lo_date=d - timedelta(days=5), hi_date=d + timedelta(days=5))


def test_same_ticker_and_type_dir_inside_the_window_merges_and_unions():
    c = FakeColl([_ev()])
    new = _ev(sd="2026-09-30", trials=(), modality=["antibody_bispecific"], phase="pivotal",
              sources=[{"provider": "sec", "title": "u", "article_key": "b"}],
              published_at=datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc))
    t = S.find_merge_target(c, new, **_win("2026-09-30"))
    assert t is not None and t["_id"] == "KOD|topline_positive|2026-09-28"
    key = S.merge_into(c, t, new)
    d = c.docs[key]
    assert key == "KOD|topline_positive|2026-09-28", "the key never changes"
    assert len(d["sources"]) == 2 and d["modality"] == ["antibody_bispecific"]
    assert d["published_at"] == datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)   # $min
    assert d["phase"] == "3"


def test_a_naive_stored_datetime_merges_with_an_aware_new_one():
    """Mongo returns naive UTC datetimes; the new event's are aware — no TypeError."""
    stored = _ev(published_at=datetime(2026, 9, 28, 6, 34), last_seen_at=datetime(2026, 9, 28, 7, 0))
    c = FakeColl([stored])
    new = _ev(published_at=datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc),
              last_seen_at=datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc))
    S.merge_into(c, c.find_one({"_id": stored["_id"]}), new)
    d = c.docs[stored["_id"]]
    assert d["published_at"] == datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)
    assert d["last_seen_at"] == datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


def test_topline_unknown_merges_into_a_directed_topline_but_NOT_the_reverse_type():
    c = FakeColl([_ev()])
    unk = _ev(td="topline_unknown", trials=())
    assert S.find_merge_target(c, unk, **_win("2026-09-28"))["_id"] == "KOD|topline_positive|2026-09-28"
    neg = _ev(td="topline_negative", trials=())
    assert S.find_merge_target(c, neg, **_win("2026-09-28")) is None


def test_same_trial_same_direction_merges_at_ANY_earlier_date():
    c = FakeColl([_ev()])
    later = _ev(sd="2026-11-10")
    assert S.find_merge_target(c, later, lo_date=date(2026, 11, 5), hi_date=date(2026, 11, 13)) is not None
    other_trial = _ev(sd="2026-11-10", trials=("GLOW2",))
    assert S.find_merge_target(c, other_trial, lo_date=date(2026, 11, 5), hi_date=date(2026, 11, 13)) is None


def test_NEGATIVE_unresolved_events_and_other_tickers_never_merge():
    c = FakeColl([_ev()])
    assert S.find_merge_target(c, _ev(ticker=None), **_win("2026-09-28")) is None
    assert S.find_merge_target(c, _ev(ticker="MRNA"), **_win("2026-09-28")) is None


def test_insert_event_is_idempotent():
    c = FakeColl()
    assert S.insert_event(c, _ev())[0] == "new"
    assert S.insert_event(c, _ev(phase="2"))[0] == "exists"
    assert c.docs["KOD|topline_positive|2026-09-28"]["phase"] == "3"


def test_higher_phase():
    assert S.higher_phase("2", "3") == "3" and S.higher_phase("3", None) == "3"
    assert S.higher_phase(None, "1/2") == "1/2"
    # a numbered Phase 3 beats "pivotal" either way round (KOD: SEC "Pivotal", Benzinga "Phase 3")
    assert S.higher_phase("pivotal", "3") == "3" and S.higher_phase("3", "pivotal") == "3"
    assert S.higher_phase("2/3", "pivotal") == "pivotal"


# ---------------------------------------------------------------------------
# lease
# ---------------------------------------------------------------------------
NOW = datetime(2026, 9, 29, 13, 0, tzinfo=timezone.utc)


def test_lease_claim_then_held_then_released_then_min_gap_then_expired():
    c = FakeColl()
    assert S.claim_lease(c, NOW, lease_sec=900, min_gap_sec=240, pid=1) is True
    assert S.claim_lease(c, NOW + timedelta(seconds=30), lease_sec=900, min_gap_sec=240, pid=2) is False
    S.release_lease(c, NOW + timedelta(seconds=60))
    # released, but MIN_GAP not yet elapsed since the last start
    assert S.claim_lease(c, NOW + timedelta(seconds=120), lease_sec=900, min_gap_sec=240, pid=3) is False
    assert S.claim_lease(c, NOW + timedelta(seconds=300), lease_sec=900, min_gap_sec=240, pid=4) is True
    # a crashed holder: still "running" but claimed > LEASE_SEC ago -> reclaimed
    assert S.claim_lease(c, NOW + timedelta(seconds=300 + 901), lease_sec=900, min_gap_sec=240, pid=5) is True
    assert c.docs["lease"]["pid"] == 5


def test_no_mongo_is_the_documented_none_path():
    assert S.insert_article(None, _art())[0] == "new"
    assert S.find_merge_target(None, _ev(), **_win("2026-09-28")) is None
    assert S.get_state(None, "cursor") == {}
    S.set_state(None, "cursor", {"i": 1})
    assert S.claim_lease(None, NOW, lease_sec=1, min_gap_sec=1, pid=1) is True


def test_NEGATIVE_the_package_never_writes_the_catalyst_lane_cache():
    """The catalyst paper lane (trading/catalyst_entry.py) reads `catalysts_cache`;
    no medical module may name it as a collection."""
    root = Path(__file__).resolve().parents[1] / "catalysts" / "medical"
    for f in root.glob("*.py"):
        src = f.read_text()
        assert '"catalysts_cache"' not in src and "'catalysts_cache'" not in src, f.name


# ---------------------------------------------------------------------------
# fix round 2026-09-29 (critic #3, #4)
# ---------------------------------------------------------------------------
def _hi(e):
    return e.get("phase") == "3"


def test_a_merge_that_lifts_impact_to_high_re_arms_a_not_high_impact_push():
    """Massive's price story (no phase) first, the Phase 3 press release later."""
    first = _ev(phase=None, impact="low", push={"state": "not_eligible", "reason": "not_high_impact", "at": None})
    c = FakeColl([first])
    later = _ev(phase="3", sources=[{"provider": "finnhub", "title": "Phase 3 met", "article_key": "z"}])
    S.merge_into(c, c.find_one({"_id": first["_id"]}), later, impact_fn=_hi)
    d = c.docs[first["_id"]]
    assert d["impact"] == "high" and d["push"]["state"] == "pending" and d["push"]["reason"] is None


@pytest.mark.parametrize("push", [
    {"state": "not_eligible", "reason": "unresolved_ticker"},
    {"state": "baseline", "reason": "baseline"},
    {"state": "pushed", "reason": None},
    {"state": "blocked:stale", "reason": "stale"}])
def test_NEGATIVE_an_upgrade_never_re_arms_any_other_push_state(push):
    first = _ev(phase=None, impact="low", push=dict(push, at=None))
    c = FakeColl([first])
    S.merge_into(c, c.find_one({"_id": first["_id"]}), _ev(phase="3"), impact_fn=_hi)
    assert c.docs[first["_id"]]["push"]["state"] == push["state"]


def test_NEGATIVE_a_merge_that_stays_low_never_re_arms():
    first = _ev(phase=None, impact="low", push={"state": "not_eligible", "reason": "not_high_impact", "at": None})
    c = FakeColl([first])
    S.merge_into(c, c.find_one({"_id": first["_id"]}), _ev(phase="2"), impact_fn=_hi)
    assert c.docs[first["_id"]]["push"]["state"] == "not_eligible"


def _session(p):
    from catalysts.medical import reaction as R
    return R.session_date_for(R.as_et(p))


def test_an_earlier_source_moves_the_event_to_its_session_and_nulls_the_reaction():
    """ABBV: keyed 09-29 from a later story; the 09-28 04:02 ET article arrives -> session 09-28."""
    stored = _ev(ticker="ABBV", td="fda_approval", sd="2026-09-29", trials=(),
                 published_at=datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc),
                 reaction={"at_detection": {"move_pct": 1.0}, "liquidity": {"base_close": 200.0},
                           "at_close": {"day_pct": 0.5}, "fwd": None})
    c = FakeColl([stored])
    early = _ev(ticker="ABBV", td="fda_approval", sd="2026-09-28", trials=(),
                published_at=datetime(2026, 9, 28, 8, 2, tzinfo=timezone.utc))     # 04:02 ET
    key = S.merge_into(c, c.find_one({"_id": stored["_id"]}), early, session_fn=_session)
    d = c.docs[key]
    assert key == "ABBV|fda_approval|2026-09-29", "the key never changes"
    assert d["session_date"] == "2026-09-28"
    assert d["reaction"] == {"at_detection": None, "liquidity": None, "at_close": None, "fwd": None}


def test_NEGATIVE_a_later_source_never_moves_the_session_or_touches_the_reaction():
    reac = {"at_detection": {"move_pct": 1.0}, "liquidity": {"base_close": 200.0}, "at_close": None, "fwd": None}
    stored = _ev(reaction=reac)
    c = FakeColl([stored])
    late = _ev(sd="2026-09-30", published_at=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc))
    S.merge_into(c, c.find_one({"_id": stored["_id"]}), late, session_fn=_session)
    d = c.docs[stored["_id"]]
    assert d["session_date"] == "2026-09-28" and d["reaction"] == reac
