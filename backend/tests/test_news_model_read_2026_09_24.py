"""🧠 Model read on the 📰 News tab (2026-09-24).

Ajay: "You can use the abliterated model we have via hermes. For this tab".
Pins: facts come only from the served blocks; a read ships only two-sided,
with a lean from the three words, and with no number the model was not
handed; LOCAL model only, one call, no hosted fallback; the model never runs
on the request; one refresh at a time.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

import llm
from chart_maps import news_model_read as M
from chart_maps import news_tab as NT


# ── fixtures ────────────────────────────────────────────────────────────────
def _payload(**over):
    p = {
        "verdict": {"ok": True, "daily": {"word": "mixed", "state_label": "Caution", "score": 60.456},
                    "weekly": {"word": "bullish", "state_label": "Constructive", "score": 84},
                    "drivers": ["Breadth thinning", 7]},
        "macro": {"ok": True, "days": 14, "events": [
            {"label": "Jobless claims", "tier": 2, "when_label": "today"},
            {"label": "Core PCE", "tier": 1, "when_label": "in 6 days"},
            {"label": "Jobs report (NFP)", "tier": 1, "when_label": "in 8 days"},
            {"label": "GDP", "tier": 2, "when_label": "in 6 days"}]},
        "sectors": {"ok": True, "d1": {"live": True}, "rows": [
            {"sector": "Technology", "rel_1d": -0.4321, "rel_5d": 1.2, "rel_21d": 3.0,
             "heat": {"tone": "hot"}, "hot_lagging_1d": True, "cold_leading_1d": False},
            {"sector": "Energy", "rel_1d": 0.91, "rel_5d": -2.0, "rel_21d": -4.4,
             "heat": {"tone": "cold"}, "hot_lagging_1d": False, "cold_leading_1d": True},
            {"sector": "Utilities", "rel_1d": -0.2, "rel_5d": -0.1, "rel_21d": -1.0,
             "heat": {"tone": "mid"}}]},
        "headlines": {"ok": True, "items": [
            {"title": "S&P 500 slips as yields climb", "source": "Reuters"},
            {"title": "Oil jumps on supply worries", "source": "CNBC"},
            {"title": "Chip stocks mixed after earnings", "source": "MarketWatch"}]},
    }
    p.update(over)
    return p


GOOD = {
    "lean": "mixed",
    "bull": "Oil strength is lifting energy while the weekly gauge stays constructive for the broad tape.",
    "bear": "Rising yields weigh on the index and technology is lagging the equal-weight benchmark today.",
    "sectors_bullish": ["Energy"], "sectors_bearish": ["Technology"],
    "watch": ["Core PCE", "Jobless claims"],
}


class FakeColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.inserted = []

    def insert_one(self, d):
        self.inserted.append(d)
        self.docs.append(dict(d))

    def find(self, flt=None):
        flt = flt or {}
        rows = [dict(d) for d in self.docs if all(d.get(k) == v for k, v in flt.items())]
        return _Cur(rows)


class _Cur:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, key, direction):
        self.rows.sort(key=lambda d: d.get(key) or 0, reverse=direction < 0)
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def __iter__(self):
        return iter(self.rows)


@pytest.fixture(autouse=True)
def _free_lock():
    if M._LOCK.locked():
        M._LOCK.release()
    yield
    if M._LOCK.locked():
        M._LOCK.release()


# ── facts ───────────────────────────────────────────────────────────────────
def test_facts_built_from_served_blocks_only():
    f = M.facts(_payload())
    assert f["market"]["daily"] == {"word": "mixed", "label": "Caution", "score": 60.46}
    assert f["market"]["drivers"] == ["Breadth thinning"]          # non-strings dropped
    assert f["day_basis"] == "today"
    assert [s["sector"] for s in f["sectors"]] == ["Technology", "Energy", "Utilities"]
    assert f["sectors"][0]["vs_rsp_day_pp"] == -0.43                # 2 dp
    assert f["sectors"][0]["hot_but_lagging_day"] is True
    assert f["sectors"][2]["cold_but_leading_day"] is False         # missing → False
    assert [e["label"] for e in f["macro"]][:2] == ["Jobless claims", "Core PCE"]
    assert len(f["headlines"]) == 3


@pytest.mark.parametrize("block", ["verdict", "macro", "sectors", "headlines"])
def test_facts_none_when_any_block_failed(block):
    assert M.facts(_payload(**{block: {"ok": False, "reason": "still loading"}})) is None


@pytest.mark.parametrize("bad", [None, "x", 7, [], {}])
def test_facts_none_on_junk_payload(bad):
    assert M.facts(bad) is None


def test_facts_none_with_fewer_than_two_headlines():
    p = _payload(headlines={"ok": True, "items": [{"title": "only one"}, {"title": "  "}, "junk"]})
    assert M.facts(p) is None


def test_facts_none_without_sector_rows():
    assert M.facts(_payload(sectors={"ok": True, "rows": [{"sector": None}, "x"]})) is None


def test_facts_last_close_basis_and_headline_cap():
    items = [{"title": f"h{i}", "source": "s"} for i in range(20)]
    p = _payload(headlines={"ok": True, "items": items})
    p["sectors"]["d1"] = {"live": False}
    f = M.facts(p)
    assert f["day_basis"] == "last close"
    assert len(f["headlines"]) == M.MAX_HEADLINES_TO_MODEL


def test_facts_rounding_rejects_nan_inf_bool():
    p = _payload()
    p["sectors"]["rows"][0]["rel_1d"] = float("nan")
    p["sectors"]["rows"][1]["rel_1d"] = True
    p["sectors"]["rows"][2]["rel_1d"] = float("inf")
    f = M.facts(p)
    assert [s["vs_rsp_day_pp"] for s in f["sectors"]] == [None, None, None]


def test_facts_hash_stable_and_sensitive():
    a, b = M.facts(_payload()), M.facts(_payload())
    assert M.facts_hash(a) == M.facts_hash(b)
    p = _payload()
    p["headlines"]["items"][0]["title"] = "S&P 500 rallies"
    assert M.facts_hash(M.facts(p)) != M.facts_hash(a)


# ── clean ───────────────────────────────────────────────────────────────────
def test_clean_accepts_a_two_sided_read():
    read, why = M.clean(dict(GOOD), M.facts(_payload()))
    assert why is None
    assert read["lean"] == "mixed"
    assert read["sectors_bullish"] == ["Energy"] and read["sectors_bearish"] == ["Technology"]
    assert read["watch"] == ["Core PCE", "Jobless claims"]


def test_clean_lean_is_case_insensitive():
    read, _ = M.clean(dict(GOOD, lean=" Bullish "), M.facts(_payload()))
    assert read["lean"] == "bullish"


@pytest.mark.parametrize("lean", ["neutral", "", None, "risk_off", "constructive", 1])
def test_clean_refuses_any_other_lean(lean):
    read, why = M.clean(dict(GOOD, lean=lean), M.facts(_payload()))
    assert read is None and "lean" in why


@pytest.mark.parametrize("side", ["bull", "bear"])
@pytest.mark.parametrize("val", [None, "", "too short to count"])
def test_clean_refuses_a_one_sided_read(side, val):
    read, why = M.clean(dict(GOOD, **{side: val}), M.facts(_payload()))
    assert read is None and "one side" in why


@pytest.mark.parametrize("bad", [None, "json", [], 3])
def test_clean_refuses_non_objects(bad):
    read, why = M.clean(bad, M.facts(_payload()))
    assert read is None and why


def test_clean_refuses_a_number_it_was_not_handed():
    bear = "Yields climbing toward 5.2 percent could pull the index down another leg from here."
    read, why = M.clean(dict(GOOD, bear=bear), M.facts(_payload()))
    assert read is None and "5.2" in why


def test_clean_allows_numbers_that_are_in_the_facts():
    bull = "The S&P 500 headline aside, the weekly gauge at 84 keeps the broad trend constructive."
    read, why = M.clean(dict(GOOD, bull=bull), M.facts(_payload()))
    assert why is None and read["bull"] == bull


def test_clean_rounded_sector_number_is_allowed_raw_one_is_not():
    f = M.facts(_payload())
    ok, _ = M.clean(dict(GOOD, bear=GOOD["bear"] + " Technology trails by 0.43 today."), f)
    assert ok is not None
    bad, why = M.clean(dict(GOOD, bear=GOOD["bear"] + " Technology trails by 0.4321 today."), f)
    assert bad is None and "0.4321" in why


def test_stray_numbers_ignore_thousands_commas():
    f = {"x": "10,000 jobs"}
    assert M.stray_numbers("about 10,000 jobs", f) == []
    assert M.stray_numbers("about 12,000 jobs", f) == ["12000"]


def test_clean_keeps_only_exact_sector_and_macro_names():
    parsed = dict(GOOD, sectors_bullish=["Energy", "energy", "Crypto", 5, "Energy"],
                  sectors_bearish="Technology", watch=["CPI", "GDP", "Core PCE", "Jobless claims",
                                                       "Jobs report (NFP)"])
    read, _ = M.clean(parsed, M.facts(_payload()))
    assert read["sectors_bullish"] == ["Energy"]
    assert read["sectors_bearish"] == []                             # not a list → nothing
    assert read["watch"] == ["GDP", "Core PCE", "Jobless claims"]    # capped at 3, CPI not served


def test_clean_drops_a_sector_named_on_both_sides():
    parsed = dict(GOOD, sectors_bullish=["Energy", "Utilities"], sectors_bearish=["Energy", "Technology"])
    read, _ = M.clean(parsed, M.facts(_payload()))
    assert read["sectors_bullish"] == ["Utilities"]
    assert read["sectors_bearish"] == ["Technology"]


# ── generate: LOCAL ONLY, one call ──────────────────────────────────────────
@pytest.fixture
def store(monkeypatch):
    c = FakeColl()
    monkeypatch.setattr(M, "_coll", lambda: c)
    return c


def _fake_chat(calls, resp):
    def chat(prompt, **kw):
        calls.append(kw)
        if isinstance(resp, Exception):
            raise resp
        return resp
    return chat


def test_generate_calls_the_local_model_once_and_stores_the_read(monkeypatch, store):
    calls = []
    monkeypatch.setattr(llm, "chat", _fake_chat(calls, {
        "ok": True, "parsed": dict(GOOD), "model": "huihui_ai/Qwen3.8-abliterated:27b", "latency_sec": 140.2}))
    d = M.generate(M.facts(_payload()), now=1_000.0)
    assert [c["provider"] for c in calls] == ["local"]
    assert calls[0]["json_only"] is True
    assert d["ok"] is True and d["lean"] == "mixed"
    assert d["model"] == "huihui_ai/Qwen3.8-abliterated:27b" and d["provider"] == "local"
    assert d["measured"] is False
    assert store.inserted and store.inserted[0]["generated_at_epoch"] == 1_000.0


def test_generate_budget_is_the_measured_day_tag_budget(monkeypatch, store):
    from rotation import sector_news_tags as SNT
    calls = []
    monkeypatch.setattr(llm, "chat", _fake_chat(calls, {"ok": True, "parsed": dict(GOOD)}))
    M.generate(M.facts(_payload()))
    assert calls[0]["max_tokens"] == SNT.MAX_TOKENS and calls[0]["timeout"] == SNT.MODEL_TIMEOUT_SEC


def test_generate_local_down_is_stored_as_a_refusal_no_hosted_fallback(monkeypatch, store):
    calls = []
    monkeypatch.setattr(llm, "chat", _fake_chat(calls, {"ok": False, "error": "connection refused"}))
    d = M.generate(M.facts(_payload()))
    assert len(calls) == 1 and calls[0]["provider"] == "local"
    assert d["ok"] is False and "local model unavailable" in d["reason"]
    assert store.inserted[0]["ok"] is False


def test_generate_bad_output_is_stored_with_its_reason(monkeypatch, store):
    monkeypatch.setattr(llm, "chat", _fake_chat([], {"ok": True, "parsed": dict(GOOD, bear="")}))
    d = M.generate(M.facts(_payload()))
    assert d["ok"] is False and "one side" in d["reason"]
    assert "bull" not in d


def test_generate_never_raises(monkeypatch, store):
    monkeypatch.setattr(llm, "chat", _fake_chat([], RuntimeError("boom")))
    d = M.generate(M.facts(_payload()))
    assert d["ok"] is False and "boom" in d["reason"]


def test_generate_without_a_store_still_returns(monkeypatch):
    monkeypatch.setattr(M, "_coll", lambda: None)
    monkeypatch.setattr(llm, "chat", _fake_chat([], {"ok": True, "parsed": dict(GOOD)}))
    assert M.generate(M.facts(_payload()))["ok"] is True


# ── refresh policy ──────────────────────────────────────────────────────────
def test_should_refresh():
    now = 10_000.0
    fresh = now - 60
    stale = now - M.REFRESH_MIN_SEC - 1
    assert M.should_refresh(None, "h", now) is True
    assert M.should_refresh({"generated_at_epoch": fresh, "ok": False, "facts_hash": "x"}, "h", now) is False
    assert M.should_refresh({"generated_at_epoch": stale, "ok": True, "facts_hash": "h"}, "h", now) is False
    assert M.should_refresh({"generated_at_epoch": stale, "ok": False, "facts_hash": "h"}, "h", now) is True
    assert M.should_refresh({"generated_at_epoch": stale, "ok": True, "facts_hash": "old"}, "h", now) is True


# ── served: never runs the model on the request ─────────────────────────────
class _NoThread:
    started = []

    def __init__(self, target=None, args=(), **kw):
        self.target, self.args = target, args

    def start(self):
        _NoThread.started.append(self.args)


@pytest.fixture
def no_thread(monkeypatch):
    _NoThread.started = []
    monkeypatch.setattr(M.threading, "Thread", _NoThread)
    return _NoThread


def test_served_without_store_says_so(monkeypatch):
    monkeypatch.setattr(M, "_coll", lambda: None)
    out = M.served(_payload())
    assert out["ok"] is False and out["read"] is None and "store" in out["reason"]
    assert "UNMEASURED" in out["note"]


def test_served_returns_newest_ok_read_and_starts_one_refresh(monkeypatch, no_thread):
    now = 50_000.0
    c = FakeColl([
        {"ok": True, "lean": "bullish", "bull": "b" * 50, "bear": "c" * 50, "generated_at_epoch": now - 7200,
         "facts_hash": "old"},
        {"ok": True, "lean": "mixed", "bull": "b" * 50, "bear": "c" * 50, "generated_at_epoch": now - 3600,
         "facts_hash": "old"},
    ])
    monkeypatch.setattr(M, "_coll", lambda: c)
    monkeypatch.setattr(llm, "chat", lambda *a, **k: pytest.fail("the model ran on the request"))
    out = M.served(_payload(), now=now)
    assert out["ok"] is True and out["read"]["lean"] == "mixed" and out["age_sec"] == 3600
    assert len(no_thread.started) == 1 and out["refreshing"] is True
    assert out["last_error"] is None


def test_served_single_flight(monkeypatch, no_thread):
    c = FakeColl()
    monkeypatch.setattr(M, "_coll", lambda: c)
    M.served(_payload(), now=1.0)
    M.served(_payload(), now=2.0)
    assert len(no_thread.started) == 1


def test_served_no_refresh_inside_the_interval(monkeypatch, no_thread):
    now = 50_000.0
    c = FakeColl([{"ok": False, "reason": "model wrote numbers not in its facts (9)",
                   "generated_at_epoch": now - 60, "facts_hash": "x"}])
    monkeypatch.setattr(M, "_coll", lambda: c)
    out = M.served(_payload(), now=now)
    assert no_thread.started == [] and out["refreshing"] is False
    assert out["ok"] is False and "numbers" in out["reason"] and "numbers" in out["last_error"]


def test_served_waits_for_all_four_blocks(monkeypatch, no_thread):
    monkeypatch.setattr(M, "_coll", lambda: FakeColl())
    out = M.served(_payload(macro={"ok": False, "reason": "still loading"}))
    assert no_thread.started == []
    assert "all four blocks" in out["reason"]


def test_served_start_false_never_spawns(monkeypatch, no_thread):
    monkeypatch.setattr(M, "_coll", lambda: FakeColl())
    M.served(_payload(), start=False)
    assert no_thread.started == []


def test_background_run_releases_the_lock_even_when_generate_raises(monkeypatch):
    monkeypatch.setattr(M, "generate", lambda f, fh: (_ for _ in ()).throw(RuntimeError("x")))
    assert M._LOCK.acquire(blocking=False)
    with pytest.raises(RuntimeError):
        M._run({}, "h")
    assert not M._LOCK.locked()


def test_real_thread_writes_one_read(monkeypatch):
    c = FakeColl()
    monkeypatch.setattr(M, "_coll", lambda: c)
    done = threading.Event()

    def chat(prompt, **kw):
        done.set()
        return {"ok": True, "parsed": dict(GOOD), "model": "m"}
    monkeypatch.setattr(llm, "chat", chat)
    M.served(_payload(), now=5.0)
    assert done.wait(5)
    for _ in range(100):
        if not M._LOCK.locked():
            break
        threading.Event().wait(0.02)
    assert len(c.inserted) == 1 and c.inserted[0]["ok"] is True


# ── the tab carries the block and survives it breaking ──────────────────────
def _quick(monkeypatch):
    for leg in ("_gauge_leg", "_macro_leg", "_sectors_leg", "_news_leg"):
        monkeypatch.setattr(NT, leg, lambda: {"ok": True})


def test_build_carries_model_read(monkeypatch):
    _quick(monkeypatch)
    monkeypatch.setattr(M, "served", lambda body: {"ok": True, "read": {"lean": "mixed"}})
    out = asyncio.run(NT.build())
    assert out["model_read"]["read"]["lean"] == "mixed"
    assert out["verdict"]["ok"] is True


def test_build_survives_model_read_raising(monkeypatch):
    _quick(monkeypatch)

    def boom(body):
        raise RuntimeError("mongo exploded")
    monkeypatch.setattr(M, "served", boom)
    out = asyncio.run(NT.build())
    assert out["model_read"]["ok"] is False and "mongo exploded" in out["model_read"]["reason"]
    assert all(out[k]["ok"] for k in ("verdict", "macro", "sectors", "headlines"))


def test_build_model_read_past_budget_times_out_alone(monkeypatch):
    _quick(monkeypatch)
    monkeypatch.setattr(NT, "LEG_BUDGET_SEC", 0.05)
    monkeypatch.setattr(M, "served", lambda body: threading.Event().wait(0.5) or {"ok": True})
    out = asyncio.run(NT.build())
    assert out["model_read"]["ok"] is False and "timed out" in out["model_read"]["reason"]


# ── source guards ───────────────────────────────────────────────────────────
SRC = Path(M.__file__).read_text()


def test_source_local_only_no_hosted_provider():
    assert 'PROVIDER = "local"' in SRC
    for bad in ('provider="anthropic"', "provider='anthropic'", 'provider="auto"', '"anthropic"'):
        assert bad not in SRC


def test_source_no_hermes_agent_turn():
    code = SRC.split('"""', 2)[2]          # past the module docstring
    assert "ollama_chat" not in code and "hermes" not in code.lower()


@pytest.mark.parametrize("tok,want", [("84.0", "84"), ("0.430", "0.43"), ("09", "9"), ("500", "500"),
                                      ("0", "0"), ("0.0", "0"), ("100", "100")])
def test_norm_one_spelling_per_number(tok, want):
    assert M._norm(tok) == want


def test_integral_score_written_plainly_is_allowed():
    f = M.facts(_payload())
    assert f["market"]["weekly"]["score"] == 84.0
    assert M.stray_numbers("the weekly gauge reads 84", f) == []
