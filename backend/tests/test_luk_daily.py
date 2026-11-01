"""chart_maps/luk/daily.py — 🥇 Luk's daily facts and THE TRUST RULE (spec §3.5, C2 / C9).

REFIX 2026-11-01: a daily bar dated d is a CLOSED day only when Luk's OWN fetch made it at or after d 16:00 ET +
LC.LUK_DAILY_TRUST_AFTER_SEC (stored in luk_daily, source "fetch"). NO house cache doc is trusted —
`prices.patch_latest_closes` re-stamps `cached_at` without rewriting the rows under it. The house reads
(`cached_frame_meta`, `_mongo_get`, `load_prices`) are monkeypatched to record / refuse."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import store as GS
from chart_maps.luk import constants as LC
from chart_maps.luk import daily as DA
from chart_maps.luk import store as LS
from orderflow.signals import ema
from sepa import prices as P
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
D = date(2026, 10, 30)                     # a Friday
SESSION = date(2026, 11, 2)                # the Monday after: prev_market_day == D
NOW = datetime(2026, 11, 2, 9, 52, tzinfo=ET)


def at(d, hh, mm, ss=0) -> float:
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET).timestamp()


def frame(n=200, last=D, base=10.0, step=0.1, extra_today=False):
    idx = list(pd.bdate_range(end=pd.Timestamp(last), periods=n))
    if extra_today:
        idx.append(pd.Timestamp(SESSION))
    close = [base + step * i for i in range(len(idx))]
    return pd.DataFrame({"open": close, "high": [c + 0.5 for c in close], "low": [c - 0.5 for c in close],
                         "close": close, "volume": [1e6 + i for i in range(len(idx))]}, index=pd.DatetimeIndex(idx))


def meta(cached_at, **kw):
    return {"frame": frame(**kw), "cached_at": cached_at}


@pytest.fixture
def cache(monkeypatch):
    docs: dict = {}
    reads = []

    def _meta(sym):
        reads.append(sym)
        return docs.get(sym)

    monkeypatch.setattr(P, "cached_frame_meta", _meta)

    def _refuse(*a, **k):
        raise AssertionError("Luk never reads a closed day through _mongo_get / load_prices(force=False)")

    monkeypatch.setattr(P, "_mongo_get", _refuse)
    monkeypatch.setattr(P, "load_prices", _refuse)
    docs["_reads"] = reads
    return docs


def fake_luk():
    colls = {n: FakeColl() for n in LS.LOGICAL}
    colls[LS.SCREENS_KEY] = FakeColl()
    return LS.LukStore(colls=colls)


# ── the trust rule ─────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sec,ok", [(LC.LUK_DAILY_TRUST_AFTER_SEC - 1, False), (LC.LUK_DAILY_TRUST_AFTER_SEC, True),
                                    (-3600, False), (86400, True)])
def test_trusted_through_boundary(sec, ok):
    assert DA.trusted_through(at(D, 16, 0) + sec, D) is ok


def test_trusted_through_close_plus_29_false_plus_30_true():
    assert LC.LUK_DAILY_TRUST_AFTER_SEC == 30
    assert DA.trusted_through(at(D, 16, 0, 29), D) is False
    assert DA.trusted_through(at(D, 16, 0, 30), D) is True


def test_trusted_through_is_dst_aware_and_rejects_junk():
    winter = date(2026, 12, 15)
    assert DA.close_epoch(winter) == datetime(2026, 12, 15, 21, 0, tzinfo=ZoneInfo("UTC")).timestamp()
    assert DA.close_epoch(D) == datetime(2026, 10, 30, 20, 0, tzinfo=ZoneInfo("UTC")).timestamp()
    for junk in (None, "x", True, float("nan")):
        assert DA.trusted_through(junk, D) is False


# ── cached_frame: REFIX — no house doc is a close proof ────────────────────────────────────────────────────────
def test_REFIX_cached_frame_is_none_even_for_a_doc_stamped_after_the_close(cache):
    cache["AAA"] = meta(at(D, 16, 30), extra_today=True)
    assert DA.cached_frame("AAA", SESSION, now=NOW) is None
    assert cache["_reads"] == [], "NEGATIVE: the house doc is never even read"


def test_NEGATIVE_REFIX_the_patch_latest_closes_restamp_is_never_served(cache):
    """The trap: load_prices wrote a HALF-SESSION D bar at 15:00 ET on D; on D+1 a scan's patch_latest_closes
    pushed D+1's bar and re-stamped cached_at → the stamp is AFTER D's close but the D row is still partial."""
    half = frame(n=200)
    half.iloc[-1, half.columns.get_loc("close")] = 1.0         # the half-session close
    cache["AAA"] = {"frame": half, "cached_at": at(SESSION, 9, 40)}
    assert DA.trusted_through(at(SESSION, 9, 40), D) is True, "the stamp alone WOULD pass the old rule"
    assert DA.cached_frame("AAA", SESSION, now=NOW) is None
    st = fake_luk()
    out = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=0, budget_sec=60, cached=DA.cached_frame, fetch=None)
    assert out["computed"] == 0 and out["untrusted"] == 1 and DA.is_pending(out["facts"]["AAA"])
    assert st.coll(GS.DAILY).docs == {}
    loads = {"daily": 0, "minute": 0}
    got = DA.closed_through("AAA", D, now=NOW, fetch=lambda s: frame(n=200), loads=loads)
    assert loads["daily"] == 1 and got["close"] == frame(n=200)["close"].iloc[-1] and got["close"] != 1.0
    assert cache["_reads"] == []


def test_closed_before_drops_today_and_after():
    df = frame(n=5, extra_today=True)
    out = DA.closed_before(df, SESSION)
    assert len(out) == 5 and out.index[-1].date() == D
    aware = df.copy()
    aware.index = aware.index.tz_localize(ET)
    assert len(DA.closed_before(aware, SESSION)) == 5
    assert DA.closed_before(None, SESSION) is None


# ── facts ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_facts_keys_and_formulas():
    df = frame(n=200)
    f = DA.facts_from_frame(df)
    assert tuple(f) == DA.FACT_KEYS
    c = df["close"]
    assert f["ema9"] == pytest.approx(ema(c, 9).iloc[-1]) and f["ema150"] == pytest.approx(ema(c, 150).iloc[-1])
    assert f["avg_vol_10d"] == pytest.approx(df["volume"].iloc[-LC.LUK_AVG_VOL_SESSIONS:].mean())
    assert f["px_vol"] == pytest.approx(c.iloc[-1] * df["volume"].iloc[-1])
    assert f["px_vol_1w"] == pytest.approx((c * df["volume"]).iloc[-LC.LUK_PX_VOL_1W_SESSIONS:].sum())
    rng = ((df["high"] - df["low"]) / c * 100).iloc[-LC.LUK_VOL_1W_SESSIONS:]
    assert f["vol_1w_pct"] == pytest.approx(rng.mean())
    assert f["perf_1m_pct"] == pytest.approx((c.iloc[-1] / c.iloc[-1 - LC.LUK_PERF_1M_SESSIONS] - 1) * 100)
    assert f["tier"] == "lead" and f["n_bars"] == 200 and f["as_of"] == D.isoformat()
    assert f["prev_high"] == df["high"].iloc[-1] and f["prev2_low"] == df["low"].iloc[-2]


def test_ema_spans_match_the_constants():
    assert DA.EMA_SPANS[0] == LC.LUK_PULLBACK_DAILY_EMA
    assert tuple(DA.EMA_SPANS[1:3]) == tuple(LC.LUK_POTENT_EMAS)


def test_NEGATIVE_ema150_none_under_150_bars():
    assert DA.facts_from_frame(frame(n=149))["ema150"] is None
    assert DA.facts_from_frame(frame(n=150))["ema150"] is not None
    short = DA.facts_from_frame(frame(n=8))
    assert short["ema9"] is None and short["avg_vol_10d"] is None and short["perf_1m_pct"] is None
    assert short["tier"] is None
    assert DA.facts_from_frame(None) is None


@pytest.mark.parametrize("h2,l2,h1,l1,inside", [
    (12, 8, 11, 9, True), (12, 8, 12, 9, False), (12, 8, 11, 8, False), (12, 8, 13, 9, False)])
def test_inside_day_is_strict(h2, l2, h1, l1, inside):
    df = frame(n=30)
    df.iloc[-2, df.columns.get_loc("high")], df.iloc[-2, df.columns.get_loc("low")] = h2, l2
    df.iloc[-1, df.columns.get_loc("high")], df.iloc[-1, df.columns.get_loc("low")] = h1, l1
    assert DA.facts_from_frame(df)["inside_day"] is inside


# ── warm ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _never_cached(sym, session, *, now):
    raise AssertionError("REFIX: warm never consults the house cache")


def _fetch_200(log=None):
    def fetch(sym, session):
        if log is not None:
            log.append(sym)
        return frame(n=200, extra_today=True)
    return fetch


def _seed(st, sym, **over):
    body = {"facts": DA.facts_from_frame(frame(n=200)), "daily_cached_at": at(SESSION, 9, 31),
            "source": DA.SOURCE_FETCH}
    body.update(over)
    st.upsert_daily(SESSION, sym, body, now=NOW)


def test_warm_own_post_close_fetch_computes_writes_one_doc_and_is_reused():
    st = fake_luk()
    fetched = []
    out = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=8, budget_sec=60, cached=_never_cached,
                  fetch=_fetch_200(fetched))
    assert fetched == ["AAA"] and (out["computed"], out["fetched"], out["untrusted"]) == (1, 1, 1)
    assert out["facts"]["AAA"]["as_of"] == D.isoformat(), "today's row is cut"
    docs = st.coll(GS.DAILY).docs
    assert list(docs) == [f"{SESSION.isoformat()}|AAA"]
    doc = docs[f"{SESSION.isoformat()}|AAA"]
    assert doc["source"] == DA.SOURCE_FETCH and doc["daily_cached_at"] == NOW.timestamp()
    again = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=8, budget_sec=60, cached=_never_cached,
                    fetch=lambda s, d: pytest.fail("≈1 fetch per name per session: the own doc is reused"))
    assert again["doc_hits"] == 1 and again["untrusted"] == 0
    assert again["facts"]["AAA"]["close"] == out["facts"]["AAA"]["close"]


@pytest.mark.parametrize("over", [{"source": "cache"}, {"source": None}, {"daily_cached_at": at(D, 15, 0)},
                                  {"daily_cached_at": at(D, 16, 0, 29)}, {"daily_cached_at": None},
                                  {"facts": dict(DA.facts_from_frame(frame(n=200)), as_of="2026-10-29")}])
def test_NEGATIVE_a_luk_daily_doc_not_from_the_own_post_close_fetch_is_refetched(over):
    st = fake_luk()
    _seed(st, "AAA", **over)
    fetched = []
    out = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=8, budget_sec=60, cached=_never_cached,
                  fetch=_fetch_200(fetched))
    assert out["doc_hits"] == 0 and fetched == ["AAA"] and out["computed"] == 1
    assert st.coll(GS.DAILY).docs[f"{SESSION.isoformat()}|AAA"]["source"] == DA.SOURCE_FETCH


def test_own_doc_boundary_close_plus_30s_is_a_hit():
    st = fake_luk()
    _seed(st, "AAA", daily_cached_at=at(D, 16, 0, 30))
    out = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=8, budget_sec=60, fetch=None)
    assert out["doc_hits"] == 1 and out["deferred"] == 0


def test_warm_cap_spent_defers_with_the_served_sentence_and_counts_untrusted():
    st = fake_luk()
    fetched = []
    out = DA.warm(st, SESSION, ["AAA", "BBB", "CCC"], now=NOW, cap_new=1, budget_sec=60, cached=_never_cached,
                  fetch=_fetch_200(fetched))
    assert fetched == ["AAA"]
    assert (out["untrusted"], out["fetched"], out["computed"], out["deferred"]) == (3, 1, 1, 2)
    for sym in ("BBB", "CCC"):
        f = out["facts"][sym]
        assert DA.is_pending(f) and not f, "deferred = Pending, FALSY (counted not screened)"
        assert f["pending_text"] == "daily facts pending — Luk's own post-close fetch not made yet"
        assert "cache" not in f["pending_text"], "NEGATIVE (REFIX 2026-11-01): the sentence never blames the cache"
    assert set(st.coll(GS.DAILY).docs) == {f"{SESSION.isoformat()}|AAA"}, "NEGATIVE: no doc for a deferred name"


def test_NEGATIVE_a_fetch_without_the_last_market_day_writes_no_doc():
    st = fake_luk()
    out = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=8, budget_sec=60, cached=_never_cached,
                  fetch=lambda s, d: frame(n=200, last=date(2026, 10, 29)))
    assert out["no_frame"] == 1 and out["computed"] == 0 and "AAA" not in out["facts"]
    assert st.coll(GS.DAILY).docs == {}


def test_NEGATIVE_dry_run_without_fetch_defers_never_fetches():
    st = fake_luk()
    out = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=8, budget_sec=60, cached=_never_cached, fetch=None)
    assert out["deferred"] == 1 and out["fetched"] == 0 and DA.is_pending(out["facts"]["AAA"])


def test_NEGATIVE_before_the_last_close_settles_warm_makes_no_fetch():
    st = fake_luk()
    early = datetime(2026, 10, 30, 16, 0, 29, tzinfo=ET)       # session D+1's prev day = D, not settled yet
    out = DA.warm(st, date(2026, 10, 31), ["AAA"], now=early, cap_new=8, budget_sec=60, cached=_never_cached,
                  fetch=lambda s, d: pytest.fail("a fetch before the settle is never a close"))
    assert out["deferred"] == 1 and out["fetched"] == 0 and st.coll(GS.DAILY).docs == {}


def test_warm_budget_bounds_the_loop():
    st = fake_luk()
    ticks = iter([0.0, 0.0, 100.0, 100.0, 100.0, 100.0])
    out = DA.warm(st, SESSION, ["AAA", "BBB", "CCC"], now=NOW, cap_new=8, budget_sec=60,
                  clock=lambda: next(ticks), cached=_never_cached, fetch=_fetch_200())
    assert out["computed"] == 1 and out["deferred"] == 2
    assert DA.is_pending(out["facts"]["BBB"]) and DA.is_pending(out["facts"]["CCC"])


def test_NEGATIVE_REFIX_a_trusted_looking_house_doc_never_spares_the_fetch(cache):
    cache["AAA"] = meta(at(D, 16, 30))
    st = fake_luk()
    out = DA.warm(st, SESSION, ["AAA"], now=NOW, cap_new=0, budget_sec=60, fetch=None)
    assert out["untrusted"] == 1 and out["computed"] == 0 and DA.is_pending(out["facts"]["AAA"])
    assert cache["_reads"] == []


# ── closed_through (the 🏁 grade path) ─────────────────────────────────────────────────────────────────────────
AFTER = datetime(2026, 10, 30, 16, 5, tzinfo=ET)


def test_REFIX_closed_through_ignores_a_trusted_looking_cache_and_makes_one_counted_fetch(cache):
    cache["AAA"] = meta(at(D, 16, 30), extra_today=True)
    loads = {"daily": 0, "minute": 0}
    calls = []
    got = DA.closed_through("AAA", D, now=AFTER, fetch=lambda s: (calls.append(s), frame(n=200))[1], loads=loads)
    c = frame(n=200)["close"]
    assert calls == ["AAA"] and loads == {"daily": 1, "minute": 0}
    assert got["close"] == c.iloc[-1] and got["ema9_close"] == pytest.approx(ema(c, 9).iloc[-1])
    assert got["n_bars"] == 200 and got["daily_cached_at"] == AFTER.timestamp()
    assert cache["_reads"] == [], "NEGATIVE: the house doc is never read"


def test_NEGATIVE_fetch_brings_nothing_is_none(cache):
    loads = {"daily": 0, "minute": 0}
    assert DA.closed_through("AAA", D, now=AFTER, fetch=lambda s: None, loads=loads) is None
    assert loads["daily"] == 1


def test_NEGATIVE_a_fetch_lacking_d_is_none(cache):
    loads = {"daily": 0, "minute": 0}
    got = DA.closed_through("AAA", D, now=AFTER, fetch=lambda s: frame(n=200, last=date(2026, 10, 29)), loads=loads)
    assert got is None and loads["daily"] == 1


def test_NEGATIVE_cap_spent_refuses_without_fetching(cache):
    loads = {"daily": LC.LUK_GRADE_MAX_LOADS - 10, "minute": 10}
    got = DA.closed_through("AAA", D, now=AFTER, fetch=lambda s: pytest.fail("refused past the cap"), loads=loads)
    assert got is None and loads == {"daily": LC.LUK_GRADE_MAX_LOADS - 10, "minute": 10}
    loads = {"daily": 0, "minute": LC.LUK_GRADE_MAX_LOADS - 1}
    assert DA.closed_through("AAA", D, now=AFTER, fetch=lambda s: frame(n=200), loads=loads) is not None
    assert loads["daily"] == 1


def test_NEGATIVE_before_the_close_settles_nothing_is_fetched(cache):
    loads = {"daily": 0, "minute": 0}
    early = datetime(2026, 10, 30, 16, 0, 29, tzinfo=ET)
    assert DA.closed_through("AAA", D, now=early, fetch=lambda s: pytest.fail("no fetch"), loads=loads) is None
    assert loads["daily"] == 0
    on_time = datetime(2026, 10, 30, 16, 0, 30, tzinfo=ET)
    assert DA.closed_through("AAA", D, now=on_time, fetch=lambda s: frame(n=200), loads=loads) is not None


def test_closed_through_cuts_to_d(cache):
    loads = {"daily": 0, "minute": 0}
    later = frame(n=200, last=date(2026, 11, 4))
    got = DA.closed_through("AAA", D, now=AFTER + timedelta(days=5), fetch=lambda s: later, loads=loads)
    assert got["close"] == later.loc[:pd.Timestamp(D), "close"].iloc[-1]


def test_REFIX_daily_never_reads_the_house_cache_in_source():
    import inspect
    src = inspect.getsource(DA)
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("#", '"', "`")))
    for banned in ("cached_frame_meta(", "_mongo_get(", "SOURCE_CACHE"):
        assert banned not in code


# ── index state ────────────────────────────────────────────────────────────────────────────────────────────────
def test_index_state_reads_both_indices_and_cuts_today():
    seen = []

    def loader(sym):
        seen.append(sym)
        return frame(n=60, extra_today=True) if sym == "QQQ" else None

    out = DA.index_state(SESSION, loader=loader)
    assert seen == list(LC.LUK_INDEX_SYMBOLS) and out["IWM"] is None
    c = frame(n=60)["close"]
    q = out["QQQ"]
    assert q["close"] == c.iloc[-1] and q["ema9"] == pytest.approx(ema(c, 9).iloc[-1])
    assert q["dist_9_pct"] == pytest.approx((q["close"] / q["ema9"] - 1) * 100)


def test_NEGATIVE_index_loader_raising_is_none_not_a_crash():
    out = DA.index_state(SESSION, loader=lambda s: (_ for _ in ()).throw(RuntimeError("down")))
    assert all(v is None for v in out.values())


# ── index state: Luk's own fetch, ONCE per session (REFIX 2026-11-01, luk_state LC.LUK_STATE_INDEX) ──────────────
def _spy_loader(seen, *, raise_=False, iwm=True):
    def loader(sym):
        seen.append(sym)
        if raise_:
            raise AssertionError("the second pass of a session never loads an index frame")
        return frame(n=60) if (iwm or sym != "IWM") else None
    return loader


def test_index_state_first_pass_of_a_session_loads_each_index_and_keeps_the_words():
    st, seen = fake_luk(), []
    out = DA.index_state(SESSION, loader=_spy_loader(seen), store=st, now=NOW)
    assert seen == list(LC.LUK_INDEX_SYMBOLS)
    assert all(out[s] is not None for s in LC.LUK_INDEX_SYMBOLS)
    doc = st.get_state(LC.LUK_STATE_INDEX)
    assert doc["session"] == SESSION.isoformat() and doc["states"] == out and doc["at"] is not None


def test_NEGATIVE_the_second_pass_of_the_same_session_makes_no_load_and_serves_the_same_words():
    st = fake_luk()
    first = DA.index_state(SESSION, loader=_spy_loader([]), store=st, now=NOW)
    seen: list = []
    second = DA.index_state(SESSION, loader=_spy_loader(seen, raise_=True), store=st, now=NOW + timedelta(hours=2))
    assert seen == [], "the raising loader is never reached"
    assert second == first


def test_a_different_session_refetches_and_replaces_the_words():
    st = fake_luk()
    DA.index_state(SESSION, loader=_spy_loader([]), store=st, now=NOW)
    nxt, seen = date(2026, 11, 3), []
    DA.index_state(nxt, loader=_spy_loader(seen), store=st, now=NOW + timedelta(days=1))
    assert seen == list(LC.LUK_INDEX_SYMBOLS)
    assert st.get_state(LC.LUK_STATE_INDEX)["session"] == nxt.isoformat()


@pytest.mark.parametrize("doc", [{"session": "2026-10-30", "states": {"QQQ": {}, "IWM": {}}},
                                 {"session": "2026-11-02", "states": "junk"},
                                 {"session": "2026-11-02", "states": {"QQQ": {}}},
                                 {"session": "2026-11-02"}])
def test_NEGATIVE_a_stale_or_junk_kept_doc_is_never_served(doc):
    st = fake_luk()
    st.set_state(LC.LUK_STATE_INDEX, doc)
    seen: list = []
    out = DA.index_state(SESSION, loader=_spy_loader(seen), store=st, now=NOW)
    assert seen == list(LC.LUK_INDEX_SYMBOLS) and all(out[s] is not None for s in LC.LUK_INDEX_SYMBOLS)


def test_NEGATIVE_a_failed_index_load_is_not_kept_for_the_session():
    st = fake_luk()
    out = DA.index_state(SESSION, loader=_spy_loader([], iwm=False), store=st, now=NOW)
    assert out["IWM"] is None and st.get_state(LC.LUK_STATE_INDEX) == {}
    seen: list = []
    DA.index_state(SESSION, loader=_spy_loader(seen), store=st, now=NOW)
    assert seen == list(LC.LUK_INDEX_SYMBOLS), "the next pass retries"


def test_NEGATIVE_a_store_read_fault_falls_back_to_the_load():
    class Boom:
        def get_state(self, sid):
            raise RuntimeError("mongo down")

        def set_state(self, sid, fields):
            raise RuntimeError("mongo down")
    seen: list = []
    out = DA.index_state(SESSION, loader=_spy_loader(seen), store=Boom(), now=NOW)
    assert seen == list(LC.LUK_INDEX_SYMBOLS) and out["QQQ"] is not None


def test_the_default_index_loader_is_luks_own_force_fetch(monkeypatch):
    calls = []

    def load_prices(sym, period="2y", force=False):
        calls.append((sym, period, force))
        return frame(n=60, extra_today=True)

    def refuse(*a, **k):
        raise AssertionError("the index words never read the house cache")
    monkeypatch.setattr(P, "load_prices", load_prices)
    for name in ("closed_daily_frame", "cached_frame_meta", "_mongo_get"):
        monkeypatch.setattr(P, name, refuse)
    out = DA.index_state(SESSION, store=fake_luk(), now=NOW)
    assert calls == [(s, "1y", True) for s in LC.LUK_INDEX_SYMBOLS]
    assert out["QQQ"]["close"] == frame(n=60)["close"].iloc[-1], "today's bar is cut"


def test_REFIX_daily_names_the_house_index_readers_only_in_its_never_sentence():
    import inspect
    src = inspect.getsource(DA)
    start = src.index("Luk never reads a closed day")
    end = src.index("`prices.cached_frame_meta`.", start) + len("`prices.cached_frame_meta`.")
    assert end < len(DA.__doc__) + 4, "the sentence sits in the module docstring"
    sentence, rest = src[start:end], src[:start] + src[end:]
    for banned in ("closed_daily_frame", "cached_frame_meta"):
        assert banned in sentence
        assert banned not in rest, banned


def test_a_dry_store_records_the_index_write_and_lands_nothing():
    real = fake_luk()
    dry = LS.dry_store(real)
    DA.index_state(SESSION, loader=_spy_loader([]), store=dry, now=NOW)
    assert real.get_state(LC.LUK_STATE_INDEX) == {}
    assert any(w[0] == "luk_state" for w in dry.writes)
