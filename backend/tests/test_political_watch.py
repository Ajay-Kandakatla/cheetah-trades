"""🏛️ The POTUS / federal-stake headline watch — classification, resolution,
dedupe, and the push gate that keeps a fifth kind off his phone.

Ajay 2026-09-20: *"Anytime POTUS does new investments show me those"*.

THE MEASURED FACT THIS MODULE IS BUILT AROUND: of 377 titles pulled by these
queries on 2026-09-20, FOUR carried a cashtag or an exchange tag — 1.1%. A
tag-only extractor would have answered his ask with nothing, which is why
there is a reverse company-name index at all, and why a headline we cannot
resolve is stored as an UNNAMED candidate instead of being thrown away or, far
worse, guessed at.

Everything below runs against injected search results, an in-memory
collection, and an injected push. No network, no Mongo, no model.
"""
from __future__ import annotations

import pytest

from political import watch as W
from political import disclosures as D


# ── an in-memory stand-in for the candidate collection ───────────────────────

class FakeColl:
    """Just enough pymongo for this module: update_one with $set/$setOnInsert
    and upsert, find_one, find().sort().limit()."""

    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.updates = 0

    def update_one(self, flt, update, upsert=False):
        self.updates += 1
        key = flt["_id"]
        existed = key in self.docs
        doc = self.docs.setdefault(key, {"_id": key}) if (existed or upsert) else None
        if doc is None:
            return type("R", (), {"upserted_id": None})()
        if not existed:
            doc.update(update.get("$setOnInsert") or {})
        doc.update(update.get("$set") or {})
        return type("R", (), {"upserted_id": (None if existed else key)})()

    def find_one(self, flt, proj=None):
        return self.docs.get(flt["_id"])

    def find(self, flt=None, proj=None):
        rows = [dict(d) for k, d in self.docs.items() if not k.startswith("__")]
        class _C(list):
            def sort(self, *a, **k): return self
            def limit(self, *a, **k): return list(self)
        return _C(rows)


def _item(title, url="https://news.example/1", source="Reuters", published=1_700_000_000):
    return {"title": title, "url": url, "source": source, "published": published}


def _search(items_by_query=None, items=None):
    """An injected `search_sync`: returns `items` for the FIRST query and
    nothing for the rest, unless a per-query map is given."""
    seen = {"n": 0}

    def _fn(*, keyword, window_hours, relevance, audit):
        assert window_hours == W.WINDOW_HOURS
        assert relevance == "none"
        assert audit == "potus_watch"
        if items_by_query is not None:
            return {"items": list(items_by_query.get(keyword, []))}
        seen["n"] += 1
        return {"items": list(items or []) if seen["n"] == 1 else []}
    return _fn


INDEX = W._name_index({
    "RGTI": "Rigetti Computing",
    "USAR": "USA Rare Earth",
    "IONQ": "IonQ Inc",
    "AAPL": "Apple Inc",
    "V": "Visa Inc",
    "MP": "MP Materials Corp",
})


def _run(**kw):
    kw.setdefault("resolve", lambda sym: True)
    kw.setdefault("names", {"RGTI": "Rigetti Computing", "USAR": "USA Rare Earth",
                            "LMT": "Lockheed Martin Corp", "MP": "MP Materials Corp"})
    kw.setdefault("push", lambda *a, **k: {"sent": 1, "failed": 0, "total_targets": 1})
    return W.run(**kw)


# ── classify ─────────────────────────────────────────────────────────────────

def test_a_named_agency_with_a_percentage_is_a_pushable_equity_stake():
    c = W.classify("Commerce Department takes 10% equity stake in XYZ ($XYZ)")
    assert c == {"pattern": "equity_stake", "agency": "Commerce", "size": "10%"}
    assert W.is_pushable({**c, "ticker": "XYZ"}) is True


def test_weighing_a_stake_is_not_a_stake_it_is_only_a_candidate():
    """The exact row CRML is on the curated list to demonstrate."""
    c = W.classify("Government weighing stake in Critical Metals")
    assert c["pattern"] == "equity_stake"
    assert c["agency"] is None and c["size"] is None
    assert W.is_pushable({**c, "ticker": "CRML"}) is False


def test_a_federal_award_is_never_pushable_even_with_agency_and_size():
    c = W.classify("$ABC wins $400M Pentagon contract")
    assert c["pattern"] == "federal_award"
    assert c["agency"] == "Pentagon" and c["size"] == "$400M"
    assert W.is_pushable({**c, "ticker": "ABC"}) is False


def test_the_rigetti_chips_act_title_is_an_award_resolved_by_name_not_by_tag():
    """Measured 2026-09-20: this real title carries NO cashtag and NO exchange
    tag. Tag-only resolution would have dropped it entirely."""
    title = ("Rigetti Computing Finalizes $100 Million CHIPS Act Award with "
             "U.S. Department of Commerce")
    c = W.classify(title)
    assert c["pattern"] == "federal_award"
    assert c["agency"] == "Department of Commerce"
    assert c["size"] == "$100 Million"
    found = W.tickers_in(title, INDEX)
    assert found == {"by_tag": [], "by_name": ["RGTI"]}
    assert W.is_pushable({**c, "ticker": "RGTI"}) is False


def test_the_administration_taking_a_stake_is_an_equity_stake_not_a_family_row():
    """PATTERN_ORDER precedence. Filing this under potus_family would hide the
    exact event he asked to be told about."""
    title = "Trump administration takes 10% stake in Intel (NASDAQ: INTC)"
    c = W.classify(title)
    assert c["pattern"] == "equity_stake"
    assert c["agency"] is None
    assert W.is_pushable({**c, "ticker": "INTC"}) is False
    assert W.tickers_in(title, INDEX)["by_tag"] == ["INTC"]


def test_the_same_headline_with_the_agency_named_becomes_pushable():
    c = W.classify("Commerce Department takes 10% stake in Intel (NASDAQ: INTC)")
    assert c["pattern"] == "equity_stake"
    assert W.is_pushable({**c, "ticker": "INTC"}) is True


def test_pattern_order_is_the_precedence_and_covers_every_pattern():
    assert W.PATTERN_ORDER == ("equity_stake", "federal_award", "potus_family")
    assert set(W.PATTERN_ORDER) == set(W.PATTERNS)


def test_a_family_disclosure_with_no_stake_language_is_still_classified():
    c = W.classify("Trump family disclosed new holdings in three chipmakers")
    assert c["pattern"] == "potus_family"


@pytest.mark.parametrize("size", ["$100 Million", "$100M", "$2.5 billion", "9.9%", "10 %"])
def test_size_matches_case_insensitively_in_every_written_form(size):
    c = W.classify(f"Commerce Department takes an equity stake worth {size}")
    assert c["size"] is not None, size


def test_a_share_count_is_not_a_size():
    c = W.classify("Commerce Department takes equity stake of 100 shares")
    assert c["size"] is None


def test_an_ordinary_market_headline_classifies_as_nothing():
    assert W.classify("USD strengthens as dollar index rises") is None
    assert W.classify("") is None
    assert W.classify(None) is None


def test_is_pushable_rejects_garbage_and_a_classified_row_with_no_ticker():
    assert W.is_pushable(None) is False
    assert W.is_pushable("equity_stake") is False
    assert W.is_pushable({"pattern": "equity_stake", "agency": "DoD", "size": "15%"}) is False


# ── the reverse name index ───────────────────────────────────────────────────

def test_a_short_one_word_name_is_never_indexed():
    """'Apple' and 'Visa' are ordinary English before they are tickers. A
    PARSER rule, not a threshold on a signal."""
    assert W.MIN_ONE_WORD_NAME == 6
    keys = {k for k, _ in INDEX}
    assert "apple" not in keys and "visa" not in keys and "ionq" not in keys
    assert W.tickers_in("Visa rules apply to the apple harvest", INDEX)["by_name"] == []


def test_the_one_word_floor_is_exactly_six_characters_and_target_clears_it():
    """OPEN ITEM, flagged for Ajay (spec §7.14). The rule as written is
    "one-word names are kept only at >= 6 characters", and "Target" is exactly
    six — so a "Target raises guidance" headline WOULD resolve to TGT if it
    ever classified. It is a board row, never a push (the push gate needs an
    equity stake + agency + size), but it is the false positive the rule was
    meant to stop. Raising the floor to 7 is his call, not this module's.
    This test exists so the behaviour is pinned rather than discovered."""
    idx = W._name_index({"TGT": "Target Corporation"})
    assert idx == [("target", "TGT")]
    assert W.tickers_in("Target raises guidance", idx)["by_name"] == ["TGT"]


def test_the_index_is_longest_first_so_the_more_specific_name_wins():
    lengths = [len(k) for k, _ in INDEX]
    assert lengths == sorted(lengths, reverse=True)


def test_corporate_suffixes_are_stripped_on_both_sides():
    assert W._strip_name("MP Materials Corp") == "mp materials"
    assert W.tickers_in("Pentagon raises its MP Materials stake", INDEX)["by_name"] == ["MP"]


def test_a_tag_and_a_name_in_one_headline_produce_one_ticker_not_two():
    found = W.tickers_in("Rigetti Computing ($RGTI) wins a Commerce award", INDEX)
    assert found["by_tag"] == ["RGTI"]
    assert found["by_name"] == []


def test_an_empty_index_resolves_nothing_rather_than_guessing():
    assert W.tickers_in("Rigetti Computing wins an award", [])["by_name"] == []


def test_a_cold_name_cache_shrinks_the_index_instead_of_failing():
    assert W._name_index({}) == []


# ── run(): storage, dedupe, unnamed rows ─────────────────────────────────────

def test_a_pushable_headline_is_stored_and_pushed_once():
    coll = FakeColl()
    pushes = []
    counts = _run(search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in Lockheed Martin")]),
        coll=coll, push=lambda *a, **k: (pushes.append((a, k)) or
                                         {"sent": 1, "failed": 0, "total_targets": 1}))
    assert counts["candidates_new"] == 1 and counts["pushed"] == 1
    doc = coll.docs["LMT|https://news.example/1"]
    assert doc["ticker"] == "LMT" and doc["resolution"] == "name"
    assert doc["pushed"] is True and doc["heuristic"] is True
    assert doc["agency"] == "Commerce" and doc["size"] == "10%"
    assert doc["first_seen"]
    body = pushes[0][0][1]
    assert "heuristic" in body["body"]
    assert "LMT" in body["title"]
    assert pushes[0][1]["kind"] == W.KIND


def test_the_push_body_never_carries_the_curated_list_or_the_owner_address():
    coll = FakeColl()
    pushes = []
    _run(search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in Lockheed Martin")]),
        coll=coll, push=lambda *a, **k: (pushes.append(a) or
                                         {"sent": 1, "failed": 0, "total_targets": 1}))
    payload = pushes[0][1]
    text = " ".join(str(v) for v in payload.values())
    for on_list in ("MP Materials", "GLND", "USA Rare Earth"):
        assert on_list not in text
    assert payload["url"] == "/chart-maps?tab=potus"


def test_a_second_run_over_the_same_headline_neither_reinserts_nor_repushes():
    coll = FakeColl()
    pushes = []
    def _push(*a, **k):
        pushes.append(a)
        return {"sent": 1, "failed": 0, "total_targets": 1}
    item = _item("Commerce Department takes 10% equity stake in Lockheed Martin")
    first = _run(search=_search(items=[item]), coll=coll, push=_push)
    second = _run(search=_search(items=[item]), coll=coll, push=_push)
    assert first["candidates_new"] == 1 and second["candidates_new"] == 0
    assert len(pushes) == 1


def test_a_headline_naming_a_ticker_already_on_the_curated_list_is_dropped():
    coll = FakeColl()
    counts = _run(search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in Intel (NASDAQ: INTC)")]),
        coll=coll)
    assert "INTC" in D.by_ticker()
    assert counts["candidates_new"] == 0 and counts["pushed"] == 0
    assert coll.docs == {} or all(k.startswith("__") for k in coll.docs)


def test_a_name_resolved_ticker_already_on_the_list_is_dropped_too():
    coll = FakeColl()
    counts = _run(search=_search(items=[_item(
        "Pentagon raises its MP Materials equity stake to 20%")]), coll=coll)
    assert counts["candidates_new"] == 0 and counts["pushed"] == 0


def test_an_unresolvable_ticker_is_rejected_never_shown_as_a_company():
    """`companies.store.get` hands back a stub (refreshed_at None) for an
    unknown symbol — a stub is a REJECT, not a name."""
    coll = FakeColl()
    counts = _run(search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in ZZZZ ($ZZZZ)")]),
        coll=coll, resolve=lambda sym: False)
    assert counts["rejected_unresolved"] == 1
    assert counts["candidates_new"] == 0 and counts["pushed"] == 0


def test_a_classified_headline_we_cannot_name_is_stored_unnamed_and_never_pushed():
    """The USA Rare Earth title, with the company absent from the index."""
    coll = FakeColl()
    pushes = []
    title = ("Ranking Member Lofgren Raises Alarm Over Commerce Department "
             "Equity Stake in a 10% deal")
    counts = _run(search=_search(items=[_item(title)]), coll=coll,
                  names={}, push=lambda *a, **k: pushes.append(a))
    assert counts["unnamed"] == 1 and counts["pushed"] == 0 and not pushes
    doc = coll.docs["|https://news.example/1"]
    assert doc["ticker"] is None and doc["resolution"] == "unnamed"
    assert doc["pattern"] == "equity_stake" and doc["heuristic"] is True


def test_an_unclassified_headline_is_counted_but_stored_nowhere():
    coll = FakeColl()
    counts = _run(search=_search(items=[_item("USD strengthens as dollar index rises")]),
                  coll=coll)
    assert counts["headlines"] == 1
    assert counts["candidates_new"] == 0 and counts["unnamed"] == 0
    assert all(k.startswith("__") for k in coll.docs)


def test_a_failing_query_does_not_stop_the_pass():
    coll = FakeColl()
    def _boom(**kw):
        if kw["keyword"] == W.WATCH_QUERIES[0]:
            raise RuntimeError("provider down")
        return {"items": [_item("Commerce Department takes 10% equity stake in Lockheed Martin")]}
    counts = _run(search=_boom, coll=coll)
    assert counts["queries"] == len(W.WATCH_QUERIES)
    assert counts["candidates_new"] == 1


def test_a_dry_run_writes_nothing_and_pushes_nothing():
    coll = FakeColl()
    pushes = []
    counts = _run(dry_run=True, coll=coll,
                  search=_search(items=[_item(
                      "Commerce Department takes 10% equity stake in Lockheed Martin")]),
                  push=lambda *a, **k: pushes.append(a))
    assert coll.docs == {} and coll.updates == 0 and not pushes
    assert counts["candidates_new"] == 1


def test_a_transport_failure_leaves_the_row_unpushed_so_tomorrow_retries():
    coll = FakeColl()
    counts = _run(search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in Lockheed Martin")]),
        coll=coll, push=lambda *a, **k: {"sent": 0, "failed": 1, "total_targets": 1})
    assert counts["pushed"] == 0
    assert coll.docs["LMT|https://news.example/1"]["pushed"] is False


def test_nobody_targeted_is_terminal_so_his_muted_phone_is_not_retried_forever():
    """`prefs.potus_investment` is False until he flips it: total_targets 0.
    That is a fact the sender reports, not a failure — do not retry."""
    coll = FakeColl()
    counts = _run(search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in Lockheed Martin")]),
        coll=coll, push=lambda *a, **k: {"sent": 0, "failed": 0, "total_targets": 0})
    assert counts["pushed"] == 1
    assert coll.docs["LMT|https://news.example/1"]["pushed"] is True


def test_the_watch_never_writes_the_curated_json():
    before = D.JSON_PATH.read_bytes()
    _run(coll=FakeColl(), search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in Lockheed Martin")]))
    assert D.JSON_PATH.read_bytes() == before


def test_run_returns_every_counter():
    counts = _run(coll=FakeColl(), search=_search(items=[]))
    assert set(counts) == {"queries", "headlines", "candidates_new", "unnamed",
                           "pushed", "rejected_unresolved"}
    assert counts["queries"] == len(W.WATCH_QUERIES) == 7


def test_candidates_and_last_run_read_back_what_the_pass_wrote():
    coll = FakeColl()
    _run(coll=coll, search=_search(items=[_item(
        "Commerce Department takes 10% equity stake in Lockheed Martin")]))
    rows = W.candidates(coll=coll)
    assert [r["ticker"] for r in rows] == ["LMT"]
    assert W.last_run(coll=coll)


def test_no_mongo_means_no_crash():
    assert W.candidates(coll=None) == []
    assert W.last_run(coll=None) is None


# ── the kind registration — the phone stays quiet until he flips it ──────────

def test_the_kind_is_personal_and_never_a_market_kind():
    """Headline-driven, so a weekend does not make it stale: he asked for it
    on the days the government announces."""
    from market_hours import gate
    assert W.KIND in gate.PERSONAL_KINDS
    assert W.KIND not in gate.MARKET_ALERT_KINDS
    assert gate.should_drop_kind(W.KIND) is None


def test_the_kind_is_registered_and_ships_ON_since_2026_09_20():
    """Registered or it silently drops for every device (the 2026-06-24
    chokepoint). It shipped OFF for a few hours on 2026-09-20 and he flipped it
    the same day — "Yes for #1", and "Default on for any change of todays
    features Bondes or Potus or explosive growth or Earnings I wanna see all of
    them." It is in OWNER_KEEP_SET so a re-registration cannot mute it again.

    NOTE what did NOT change: the headline gate below (equity stake + named
    agency + stated size + resolved ticker) is untouched — this is which KINDS
    reach him, not what this one requires to fire."""
    from push import subs
    prefs = subs.default_prefs()
    assert W.KIND in prefs
    assert prefs[W.KIND] is True
    assert W.KIND not in subs.DISABLED_ALERT_KINDS
    assert W.KIND in subs.OWNER_KEEP_SET
    assert subs.owner_prefs()[W.KIND] is True


def test_a_subscription_is_targeted_only_once_the_pref_is_True(monkeypatch):
    from push import subs

    class FakeSubs:
        def __init__(self, rows): self.rows = rows
        def find(self, q):
            def ok(r):
                for k, v in q.items():
                    if k == "kind":
                        continue
                    cur = r
                    for part in k.split("."):
                        cur = (cur or {}).get(part) if isinstance(cur, dict) else None
                    if cur != v:
                        return False
                return True
            return [r for r in self.rows if ok(r)]

    rows = [{"user_email": "a@x", "prefs": {W.KIND: False}},
            {"user_email": "b@x", "prefs": {}},
            {"user_email": "c@x", "prefs": {W.KIND: True}}]
    db = type("DB", (), {"push_subscriptions": FakeSubs(rows)})()
    monkeypatch.setattr(subs, "_get_db", lambda: db)
    monkeypatch.setattr(subs, "_backfill", lambda _db: None)
    got = subs.list_subscriptions(filter_kind=W.KIND, honor_quiet_hours=False)
    assert [r["user_email"] for r in got] == ["c@x"]


def test_the_window_and_the_collection_are_what_the_board_advertises():
    assert W.WINDOW_HOURS == 24
    assert W.COLL == "political_candidates"
    assert "NOT a measured signal" in W.NOTE
    assert "named agency" in W.NOTE and "stated size" in W.NOTE


def test_the_owner_address_comes_from_growth_alerts_never_a_second_literal():
    from growth import alerts
    assert W._owner() == alerts.OWNER
    assert "@" not in W.__file__ or True
    src = open(W.__file__, encoding="utf-8").read()
    assert alerts.OWNER not in src
