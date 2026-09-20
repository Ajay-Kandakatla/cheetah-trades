"""⚖️ Per-ticker bull / bear read — Ajay 2026-09-20.

    "I would like it to be in individual tickers but also in to the potus page
     in chart maps"

The tests that matter here are the ones that stop this from becoming a second
opinion engine with its own prompt, and the ones that stop a number the app
cannot stand behind from reaching the model:

  * the system prompt IS the sector tags' object, by identity — not a copy
  * a read never ships with one side written (the `_usable` rule)
  * a model that is unavailable is said so, never papered over
  * EITHER YoY pair not four quarters apart BLANKS the growth legs
  * an UNVERIFIABLE pair is accepted, exactly as every board accepts it
  * `facts` never carries a None for the model to hallucinate around
  * GET never calls the model
"""
from __future__ import annotations

import asyncio

import pytest

from news_search import two_sided as TS
from rotation import sector_news_tags as SNT

# Imported HERE, at collection, on purpose — not inside `_stub_sources`.
# `asyncio.run()` (which this file's own router tests and several other test
# modules use) leaves the thread's current event loop set to None, and on
# Python 3.9 the next `get_event_loop()` in that thread is a hard
# RuntimeError. `sepa.scanner` pulls in `sepa.insider`, which builds an
# `asyncio.Lock()` at module scope, so importing it from inside a test body
# blows up whenever a poisoning module ran first. Collection happens before
# any test runs, so these four are in `sys.modules` by then and the stub
# helper only rebinds attributes on already-imported modules.
from sepa import company_names, earnings_watch, research, scanner  # noqa: E402


DAY = "2026-09-20"
BULL = "The order book is the argument here and the headline says it grew again this quarter."
BEAR = "Margins are the counter-argument and the same filing says they went the other way."


def _item(title="Something happened", url="https://example.test/a", source="Reuters",
          published=1_789_800_000.0):
    return {"title": title, "url": url, "source": source, "published": published,
            "summary": "s"}


def _search_returning(items):
    calls = []

    def fake(**kw):
        calls.append(kw)
        return {"items": list(items), "selector": {"kind": "ticker", "value": kw.get("ticker")},
                "counts": {"raw": len(items)}}
    fake.calls = calls
    return fake


def _ask_returning(parsed):
    calls = []

    def fake(facts, items):
        calls.append((facts, items))
        return parsed
    fake.calls = calls
    return fake


GOOD = {"positive": True, "bull": BULL, "bear": BEAR,
        "why_positive": "the contract award headline", "provider": "local"}


def _current_loop():
    """The thread's current loop, or None when a caller cleared it."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        return None


@pytest.fixture(autouse=True)
def _loop_intact():
    """Hand the thread back with the event loop it arrived with.

    The router tests below call `asyncio.run()`, which clears the thread's
    current loop on the way out. Same rule as `chart_maps.ipo._run`: whoever
    disturbs the loop restores it, so the next test module in the run is not
    the one that pays for it.
    """
    prev = _current_loop()
    try:
        yield
    finally:
        if _current_loop() is not prev:
            asyncio.set_event_loop(prev)


@pytest.fixture(autouse=True)
def _no_mongo_no_clock(monkeypatch):
    """No store, no wall clock. Every test states its own day."""
    monkeypatch.setattr(TS, "_coll", lambda: None)
    monkeypatch.setattr(TS, "today_et", lambda: DAY)


@pytest.fixture
def _stub_facts(monkeypatch):
    """`read` under test, not the fact gatherers — those have their own class."""
    monkeypatch.setattr(TS, "facts_for", lambda sym: {"symbol": sym, "last_close": 10.0})


# ---------------------------------------------------------------------------
# The shared prompt — identity, not a copy
# ---------------------------------------------------------------------------
class TestSharedPrompt:
    def test_the_system_prompt_object_is_the_sector_tags_one(self):
        assert TS._SYSTEM is SNT._SYSTEM

    def test_the_usable_rule_and_the_headline_floor_are_the_shared_ones(self):
        assert TS._usable is SNT._usable
        assert TS.MIN_HEADLINES is SNT.MIN_HEADLINES
        assert TS.MAX_HEADLINES_TO_MODEL is SNT.MAX_HEADLINES_TO_MODEL

    def test_the_window_is_the_one_news_window(self):
        from news_search import core
        assert TS.WINDOW_HOURS is core.DEFAULT_WINDOW_HOURS


# ---------------------------------------------------------------------------
# read — the happy path and every way it refuses
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("_stub_facts")
class TestRead:
    def test_a_good_read_carries_both_sides_read_by_and_measured_false(self):
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        out = TS.read("nvda", search=s, ask=_ask_returning(GOOD))
        assert out["ok"] is True
        assert out["symbol"] == "NVDA"
        assert out["date"] == DAY
        assert out["bull"] == BULL and out["bear"] == BEAR
        assert out["read_by"] == "local"
        assert out["measured"] is False
        assert out["cached"] is False
        assert out["headline_count"] == 2
        assert "_id" not in out

    def test_the_search_is_the_ticker_selector_on_the_one_window_and_is_audited(self):
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        TS.read("NVDA", search=s, ask=_ask_returning(GOOD))
        assert s.calls == [{"ticker": "NVDA", "window_hours": TS.WINDOW_HOURS,
                            "audit": "two_sided"}]

    def test_headlines_are_capped_at_the_shared_maximum(self):
        items = [_item(url=f"https://example.test/{i}") for i in range(20)]
        out = TS.read("NVDA", search=_search_returning(items), ask=_ask_returning(GOOD))
        assert len(out["headlines"]) == SNT.MAX_HEADLINES_TO_MODEL
        assert out["headline_count"] == 20
        assert set(out["headlines"][0]) == {"title", "url", "source", "published"}

    # ---- NEGATIVE ---------------------------------------------------------
    def test_too_few_headlines_is_not_a_read_and_the_model_is_never_asked(self):
        ask = _ask_returning(GOOD)
        out = TS.read("NVDA", search=_search_returning([_item()]), ask=ask)
        assert out["ok"] is False
        assert "fewer than" in out["reason"]
        assert str(SNT.MIN_HEADLINES) in out["reason"]
        assert len(out["headlines"]) == 1      # stored WITH what was found
        assert ask.calls == []

    def test_no_headlines_at_all_is_not_a_read(self):
        out = TS.read("NVDA", search=_search_returning([]), ask=_ask_returning(GOOD))
        assert out["ok"] is False
        assert out["headlines"] == []

    def test_a_model_that_is_off_says_model_unavailable(self):
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        out = TS.read("NVDA", search=s, ask=_ask_returning(None))
        assert out["ok"] is False
        assert out["reason"] == "model unavailable"
        assert len(out["headlines"]) == 2

    def test_a_model_that_raises_is_the_same_as_a_model_that_is_off(self):
        def boom(facts, items):
            raise RuntimeError("ollama down")
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        out = TS.read("NVDA", search=s, ask=boom)
        assert out["ok"] is False and out["reason"] == "model unavailable"

    @pytest.mark.parametrize("parsed", [
        {"bull": BULL, "bear": "", "provider": "local"},
        {"bull": "", "bear": BEAR, "provider": "local"},
        {"bull": BULL, "bear": "too short", "provider": "local"},
        {"bull": BULL, "provider": "local"},
    ])
    def test_half_a_read_is_never_shipped(self, parsed):
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        out = TS.read("NVDA", search=s, ask=_ask_returning(parsed))
        assert out["ok"] is False
        assert out["reason"] == "the model did not write both sides"
        assert "bull" not in out and "bear" not in out

    def test_a_news_leg_that_raises_ends_in_a_reason_not_an_exception(self):
        def boom(**kw):
            raise RuntimeError("provider down")
        out = TS.read("NVDA", search=boom, ask=_ask_returning(GOOD))
        assert out["ok"] is False
        assert out["headlines"] == []

    def test_an_empty_symbol_is_refused_without_a_search(self):
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        out = TS.read("", search=s, ask=_ask_returning(GOOD))
        assert out["ok"] is False and s.calls == []


# ---------------------------------------------------------------------------
# The once-a-day cache
# ---------------------------------------------------------------------------
class _FakeColl:
    def __init__(self, doc=None):
        self.docs = {doc["_id"]: doc} if doc else {}
        self.writes = []

    def find_one(self, q):
        return self.docs.get(q.get("_id"))

    def replace_one(self, q, doc, upsert=False):
        self.writes.append(doc)
        self.docs[doc["_id"]] = doc


@pytest.mark.usefixtures("_stub_facts")
class TestCache:
    def test_todays_stored_read_is_served_without_a_model_call(self, monkeypatch):
        stored = {"_id": f"NVDA|{DAY}", "ok": True, "symbol": "NVDA", "date": DAY,
                  "bull": BULL, "bear": BEAR, "read_by": "local", "measured": False}
        coll = _FakeColl(stored)
        monkeypatch.setattr(TS, "_coll", lambda: coll)
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        ask = _ask_returning(GOOD)
        out = TS.read("NVDA", search=s, ask=ask)
        assert out["cached"] is True
        assert out["bull"] == BULL
        assert ask.calls == [] and s.calls == []
        assert "_id" not in out

    def test_force_re_reads_and_overwrites_the_stored_doc(self, monkeypatch):
        stored = {"_id": f"NVDA|{DAY}", "ok": True, "symbol": "NVDA", "date": DAY,
                  "bull": "old bull", "bear": "old bear", "read_by": "local"}
        coll = _FakeColl(stored)
        monkeypatch.setattr(TS, "_coll", lambda: coll)
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        ask = _ask_returning(GOOD)
        out = TS.read("NVDA", force=True, search=s, ask=ask)
        assert out["cached"] is False
        assert out["bull"] == BULL
        assert len(ask.calls) == 1
        assert coll.docs[f"NVDA|{DAY}"]["bull"] == BULL

    def test_a_failed_read_is_stored_too_so_the_audit_can_see_it(self, monkeypatch):
        coll = _FakeColl()
        monkeypatch.setattr(TS, "_coll", lambda: coll)
        TS.read("NVDA", search=_search_returning([_item()]), ask=_ask_returning(GOOD))
        assert len(coll.writes) == 1
        assert coll.writes[0]["ok"] is False
        assert coll.writes[0]["_id"] == f"NVDA|{DAY}"

    def test_cached_returns_none_when_nothing_was_read_today(self, monkeypatch):
        monkeypatch.setattr(TS, "_coll", lambda: _FakeColl())
        assert TS.cached("NVDA") is None

    def test_a_mongo_that_is_down_never_breaks_the_read(self, monkeypatch):
        monkeypatch.setattr(TS, "_coll", lambda: None)
        s = _search_returning([_item(), _item(url="https://example.test/b")])
        out = TS.read("NVDA", search=s, ask=_ask_returning(GOOD))
        assert out["ok"] is True


# ---------------------------------------------------------------------------
# facts_for — every number from the app, and the adjacency guard
# ---------------------------------------------------------------------------
SALES = {"tier": "explosive", "growth_yoy_pct": 42.1, "prior_yoy_pct": 30.0,
         "accelerating": True, "score": 90}
EQ = {"components": {"npm_latest_pct": 21.5}}

ADJACENT = [8106, 8105, 8104, 8103, 8102, 8101]
# IOVA's shape — Q0 is 8105 and the slot four back is 8100, five quarters away.
MISMATCHED = [8105, 8104, 8102, 8101, 8100, 8098]
# The HEADLINE pair (0,4) is clean here and the PRIOR pair (1,5) is not:
# 8105 - 8100 is five quarters. `sales_prior_yoy_pct` and `accelerating` are
# computed off THAT pair, and 📈 Bonde / 🔥 Hottest / the 🚀 growth board all
# blank this document. Guarding only (0,4) handed it to the model.
PRIOR_MISMATCHED = [8106, 8105, 8104, 8103, 8102, 8100]
# No fiscal-period keys at all (352 of 2,078 live scan rows): unverifiable,
# accepted by every board, so accepted here.
UNVERIFIABLE = None


def _stub_sources(monkeypatch, *, periods, snap_extra=None, row=None, nxt=None,
                  snapshot=None):
    """Inject research / scanner / earnings_watch — no Mongo, no yfinance.

    The four modules are the file-level imports: no import runs inside a test
    body, so no test ordering can poison this helper.
    """
    snap = {"sales": SALES, "q_eps_growth_pct": 55.5, "earnings_quality": EQ,
            "q_period_series": periods}
    snap.update(snap_extra or {})
    monkeypatch.setattr(research, "decision_snapshot",
                        snapshot or (lambda syms: {"NVDA": snap}))
    monkeypatch.setattr(scanner, "load_latest",
                        lambda: {"all_results": [row] if row else []})
    monkeypatch.setattr(earnings_watch, "next_event", lambda s: nxt)
    monkeypatch.setattr(company_names, "name_for", lambda s: None)


class TestFacts:
    def test_an_adjacent_pair_carries_every_leg(self, monkeypatch):
        _stub_sources(monkeypatch, periods=ADJACENT,
                      row={"symbol": "NVDA", "name": "NVIDIA", "last_close": 178.2},
                      nxt={"date": "2026-11-19"})
        f = TS.facts_for("nvda")
        assert f["symbol"] == "NVDA"
        assert f["company"] == "NVIDIA"
        assert f["last_close"] == 178.2
        assert f["sales_growth_yoy_pct"] == 42.1
        assert f["sales_prior_yoy_pct"] == 30.0
        assert f["sales_tier"] == "explosive"
        assert f["sales_accelerating"] is True
        assert f["eps_growth_yoy_pct"] == 55.5
        assert f["net_margin_pct"] == 21.5
        assert f["next_earnings"] == "2026-11-19"
        assert f["yoy_pair_comparable"] is True

    # ---- NEGATIVE: the guard ---------------------------------------------
    def test_a_mismatched_yoy_pair_blanks_the_sales_and_eps_legs(self, monkeypatch):
        _stub_sources(monkeypatch, periods=MISMATCHED,
                      row={"symbol": "NVDA", "name": "NVIDIA", "last_close": 178.2})
        f = TS.facts_for("NVDA")
        for k in ("sales_growth_yoy_pct", "sales_prior_yoy_pct", "sales_tier",
                  "sales_accelerating", "eps_growth_yoy_pct"):
            assert k not in f, f"{k} survived a non-adjacent YoY pair"
        # The level is NOT a YoY pair, so it stays, and the block SAYS the
        # pair is not comparable rather than going quiet.
        assert f["net_margin_pct"] == 21.5
        assert f["yoy_pair_comparable"] is False

    def test_a_mismatched_PRIOR_pair_blanks_the_legs_too(self, monkeypatch):
        """The (1,5) pair is guarded, not just (0,4).

        FAILS on the pre-refix code, which checked `_adjacent(periods, 0, 4)`
        only and handed `sales_prior_yoy_pct` / `sales_accelerating` to the
        model on documents 📈 Bonde, 🔥 Hottest and the 🚀 growth board blank.
        """
        from sepa import qoq
        assert qoq._adjacent(PRIOR_MISMATCHED, 0, 4, gap=4) is True   # (0,4) is clean
        assert qoq.period_ok(PRIOR_MISMATCHED) is False               # (1,5) is not

        _stub_sources(monkeypatch, periods=PRIOR_MISMATCHED,
                      row={"symbol": "NVDA", "name": "NVIDIA", "last_close": 178.2})
        f = TS.facts_for("NVDA")
        for k in ("sales_growth_yoy_pct", "sales_prior_yoy_pct", "sales_tier",
                  "sales_accelerating", "eps_growth_yoy_pct"):
            assert k not in f, f"{k} survived a non-adjacent PRIOR pair"
        assert f["net_margin_pct"] == 21.5
        assert f["yoy_pair_comparable"] is False

    def test_an_unverifiable_pair_is_accepted_exactly_as_the_boards_accept_it(
            self, monkeypatch):
        """None keys on file is UNVERIFIABLE, not a mismatch.

        682 of 3,754 research documents carry no `q_period_series`. Blanking
        those would put the ticker page at odds with every board, which is the
        disagreement this guard exists to remove.
        """
        from sepa import qoq
        assert qoq.period_ok(UNVERIFIABLE) is None
        _stub_sources(monkeypatch, periods=UNVERIFIABLE, row={"symbol": "NVDA"})
        f = TS.facts_for("NVDA")
        assert f["sales_growth_yoy_pct"] == 42.1
        assert f["sales_prior_yoy_pct"] == 30.0
        assert f["sales_accelerating"] is True
        assert f["yoy_pair_comparable"] is True

    def test_a_none_slot_inside_a_pair_is_unverifiable_not_a_mismatch(self, monkeypatch):
        holed = [8106, None, 8104, 8103, 8102, 8101]
        from sepa import qoq
        assert qoq.period_ok(holed) is None
        _stub_sources(monkeypatch, periods=holed, row={"symbol": "NVDA"})
        assert TS.facts_for("NVDA")["yoy_pair_comparable"] is True

    def test_the_guard_is_the_apps_one_adjacency_engine(self, monkeypatch):
        """No parallel implementation: patching `sepa.qoq._adjacent` moves it.

        `Q.period_ok` → `Q.yoy_pairs_ok` → the module-global `_adjacent`, so a
        monkeypatch on the one engine still bites through the ticker page.
        """
        from sepa import qoq
        monkeypatch.setattr(qoq, "_adjacent", lambda *a, **k: False)
        _stub_sources(monkeypatch, periods=ADJACENT, row={"symbol": "NVDA"})
        assert TS.facts_for("NVDA")["yoy_pair_comparable"] is False

    def test_the_guard_reads_the_shared_tri_state_not_a_local_rule(self, monkeypatch):
        """`sepa.qoq.period_ok` is the function the module calls."""
        from sepa import qoq
        seen = []

        def fake(periods, *a, **k):
            seen.append(list(periods or []))
            return False
        monkeypatch.setattr(qoq, "period_ok", fake)
        _stub_sources(monkeypatch, periods=ADJACENT, row={"symbol": "NVDA"})
        f = TS.facts_for("NVDA")
        assert seen == [ADJACENT]
        assert f["yoy_pair_comparable"] is False
        assert "sales_prior_yoy_pct" not in f

    def test_a_qoq_that_cannot_be_imported_accepts_rather_than_blanks(self, monkeypatch):
        """A broken import is unverifiable, not a mismatch — never a silent blank."""
        from sepa import qoq

        def boom(*a, **k):
            raise RuntimeError("qoq unavailable")
        monkeypatch.setattr(qoq, "period_ok", boom)
        _stub_sources(monkeypatch, periods=ADJACENT, row={"symbol": "NVDA"})
        f = TS.facts_for("NVDA")
        assert f["yoy_pair_comparable"] is True
        assert f["sales_growth_yoy_pct"] == 42.1

    def test_facts_never_carry_a_none_or_an_empty_string(self, monkeypatch):
        _stub_sources(monkeypatch, periods=ADJACENT,
                      snap_extra={"sales": {"tier": "unknown", "growth_yoy_pct": None,
                                            "prior_yoy_pct": None, "accelerating": None},
                                  "q_eps_growth_pct": None,
                                  "earnings_quality": {"components": {}}},
                      row=None, nxt=None)
        f = TS.facts_for("NVDA")
        assert all(v is not None and v != "" for v in f.values())
        assert "sales_tier" not in f          # "unknown" is not a fact
        assert "last_close" not in f
        assert "next_earnings" not in f

    def test_a_research_cache_that_is_down_still_yields_the_symbol(self, monkeypatch):

        def boom(_):
            raise RuntimeError("mongo down")
        _stub_sources(monkeypatch, periods=ADJACENT, snapshot=boom)
        f = TS.facts_for("NVDA")
        assert f["symbol"] == "NVDA"

    def test_an_empty_symbol_has_no_facts(self):
        assert TS.facts_for("") == {}


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------
class TestApi:
    def test_get_serves_the_stored_doc_and_never_calls_the_model(self, monkeypatch):
        from news_search import api
        stored = {"_id": f"NVDA|{DAY}", "ok": True, "symbol": "NVDA", "date": DAY,
                  "bull": BULL, "bear": BEAR, "read_by": "local"}
        monkeypatch.setattr(TS, "_coll", lambda: _FakeColl(stored))

        def never(*a, **k):
            raise AssertionError("GET must not call the model")
        monkeypatch.setattr(TS, "_ask_model", never)
        resp = asyncio.run(api.get_two_sided("nvda"))
        import json
        body = json.loads(resp.body)
        assert body["ok"] is True and body["cached"] is True

    def test_get_without_a_read_today_says_so(self, monkeypatch):
        from news_search import api
        import json
        monkeypatch.setattr(TS, "_coll", lambda: _FakeColl())
        body = json.loads(asyncio.run(api.get_two_sided("NVDA")).body)
        assert body["ok"] is False
        assert body["reason"] == "not read today"

    def test_post_runs_the_read_and_scrubs_nan(self, monkeypatch):
        from news_search import api
        import json
        monkeypatch.setattr(TS, "read", lambda sym, force=False: {
            "ok": True, "symbol": sym.upper(), "facts": {"last_close": float("nan")},
            "headlines": []})
        body = json.loads(asyncio.run(api.post_two_sided("nvda", force=False)).body)
        assert body["facts"]["last_close"] is None

    def test_post_that_blows_up_returns_a_reason_not_a_500(self, monkeypatch):
        from news_search import api
        import json

        def boom(sym, force=False):
            raise RuntimeError("everything")
        monkeypatch.setattr(TS, "read", boom)
        body = json.loads(asyncio.run(api.post_two_sided("NVDA", force=False)).body)
        assert body["ok"] is False and "read failed" in body["reason"]


# ---------------------------------------------------------------------------
# Test-order independence — the `TestFacts` block used to fail only when a
# module that calls `asyncio.run()` had run first in the same process.
# ---------------------------------------------------------------------------
class TestOrderIndependence:
    def test_the_sepa_modules_are_imported_at_COLLECTION_not_inside_a_test(self):
        """`_stub_sources` must never trigger an import while a test runs."""
        import sys
        for mod in ("sepa.company_names", "sepa.earnings_watch", "sepa.research",
                    "sepa.scanner", "sepa.insider"):
            assert mod in sys.modules, f"{mod} is imported lazily — order-fragile"
        assert _stub_sources.__globals__["scanner"] is sys.modules["sepa.scanner"]

    # ---- NEGATIVE: the exact poison, reproduced -------------------------
    def test_the_stubs_survive_a_thread_whose_event_loop_was_taken_away(
            self, monkeypatch):
        """This is what `asyncio.run()` leaves behind on Python 3.9."""
        prev = _current_loop()
        asyncio.set_event_loop(None)
        try:
            _stub_sources(monkeypatch, periods=ADJACENT,
                          row={"symbol": "NVDA", "name": "NVIDIA"})
            f = TS.facts_for("NVDA")
        finally:
            asyncio.set_event_loop(prev)
        assert f["symbol"] == "NVDA"
        assert f["sales_growth_yoy_pct"] == 42.1
        assert f["yoy_pair_comparable"] is True

    # ---- NEGATIVE: this file is not the next module's poisoner ----------
    def test_a_router_call_hands_the_thread_back_with_a_usable_loop(self, monkeypatch):
        """`asyncio.run` clears the loop; `_loop_intact` puts it back. Run the
        fixture's own restore over a known-good loop so the assertion holds
        whatever the module that ran before this one left behind."""
        from news_search import api
        monkeypatch.setattr(TS, "_coll", lambda: _FakeColl())
        outer, mine = _current_loop(), asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(mine)
            asyncio.run(api.get_two_sided("NVDA"))
            assert _current_loop() is None          # the poison, unhealed
            asyncio.set_event_loop(mine)            # what `_loop_intact` does
            assert _current_loop() is mine
        finally:
            mine.close()
            asyncio.set_event_loop(outer)

    def test_facts_never_raise_when_a_sepa_module_is_unimportable(self, monkeypatch):
        """Production guards every lazy import; a broken one degrades, never 500s."""
        def boom(*a, **k):
            raise RuntimeError("no current event loop")
        monkeypatch.setattr(research, "decision_snapshot", boom)
        monkeypatch.setattr(scanner, "load_latest", boom)
        monkeypatch.setattr(earnings_watch, "next_event", boom)
        monkeypatch.setattr(company_names, "name_for", boom)
        assert TS.facts_for("NVDA") == {"symbol": "NVDA", "yoy_pair_comparable": True}
