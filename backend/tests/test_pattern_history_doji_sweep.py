"""🕯️ Doji Sweep — the pattern ledger kind (patterns/history.py, BUILD_SPEC6 §3.7, WP-B; AMENDMENTS6 B7 / B8).

Ajay 2026-10-16: "create me a new tab for Doji candle after a sweep. For any stocks after a down trend. May be from
all chart maps especially on the 60% 70% down stocks" — and K1 "do some research and back test please on accuracy".

The tab's fired candles are recorded by the 17:20 `python -m patterns.history` run as kind `doji_sweep` with the
up-direction read, graded forward by the existing candle grader, and served in their OWN `/patterns/accuracy` block
(never the 📐 Chart Patterns candle table — HIS CALL Q3). B7: the headline is the tab's default view (the house 5%
body at the default liquidity floor); the 10%-body and below-floor fires are sub-blocks. B8: the record runs LAST in
the cron, after `resolve_pending`, so a failing universe read never stops the grading of the existing kinds.
In-test FakeColl; `_coll` monkeypatched; no Mongo, no network. UNMEASURED.
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from chart_maps import doji_sweep_tab as DJ
from patterns import history as PH

HEAD, WIDE, THIN = DJ.LEDGER_BUCKETS


# ── fakes ────────────────────────────────────────────────────────────────────
class _R:
    def __init__(self, upserted_id=None):
        self.upserted_id = upserted_id


def _match(d: dict, q: dict) -> bool:
    for k, v in (q or {}).items():
        if isinstance(v, dict) and "$ne" in v:
            if d.get(k) == v["$ne"]:
                return False
        elif d.get(k) != v:
            return False
    return True


class _Cursor(list):
    def limit(self, n):
        return _Cursor(self[:n])


class FakeColl:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}
        self.writes = 0

    def update_one(self, q, u, upsert=False):
        self.writes += 1
        _id = q["_id"]
        r = _R()
        if "$setOnInsert" in u and _id not in self.docs:
            self.docs[_id] = {"_id": _id, **u["$setOnInsert"]}
            r.upserted_id = _id
        if "$set" in u and _id in self.docs:
            self.docs[_id].update(u["$set"])
        return r

    def find(self, q=None, proj=None):
        return _Cursor(dict(d) for d in self.docs.values() if _match(d, q or {}))


def _fire(sym="AAA", day="2026-10-15", *, close=10.0, doji5=True, adv50=50_000_000.0, **kw):
    f = {k: None for k in DJ.LEDGER_KEYS}
    f.update(symbol=sym, date=day, close=close, doji5=doji5, body_pct=0.02 if doji5 else 0.07,
             variant="dragonfly", test_pct=-1.5, undercut=True, reclaimed=True, ref_low=9.9,
             ref_date="2026-10-05", reads=["w52"], pct_below_52w=71.2, pct_below_ath=None,
             below_mas=True, vol_ratio=1.2, adv50=adv50)
    f.update(kw)
    f["bucket"] = kw.get("bucket", DJ.ledger_bucket(f))
    return f


def _df(closes, start="2026-09-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c,
                         "volume": np.full(len(c), 1e6)}, index=idx)


# ── constants ────────────────────────────────────────────────────────────────
def test_the_kind_and_read_constants():
    assert PH.DOJI_SWEEP_KIND == "doji_sweep" == DJ.TAB_KEY
    assert PH.GRADABLE_KINDS == ("pattern", "candle", PH.DOJI_SWEEP_KIND)
    assert PH._doji_buckets() == DJ.LEDGER_BUCKETS == ("doji_sweep", "doji_sweep_10pct", "doji_sweep_thin")


def test_NEG_the_read_word_must_be_the_graders_up_word():
    """_grade_candle grades every read other than "bullish_reversal_setup" as BEARISH — a nicer word would
    silently invert every grade."""
    assert PH.DOJI_SWEEP_READ == "bullish_reversal_setup"
    assert '"bullish_reversal_setup"' in inspect.getsource(PH._grade_candle)


# ── 1. record ────────────────────────────────────────────────────────────────
def test_record_writes_one_doc_per_candle_and_dedupes():
    c = FakeColl()
    assert PH.record_doji_sweeps([_fire()], coll=c) == 1
    d = c.docs["AAA:doji_sweep:2026-10-15"]
    assert d["et_date"] == d["formed_date"] == "2026-10-15"
    assert d["kind"] == d["formation"] == PH.DOJI_SWEEP_KIND and d["read"] == PH.DOJI_SWEEP_READ
    assert d["obs_close"] == 10.0 and d["resolved"] is False and d["bucket"] == HEAD
    assert d["reads"] == ["w52"] and d["variant"] == "dragonfly" and d["reclaimed"] is True
    assert PH.record_doji_sweeps([_fire()], coll=c) == 0                  # re-recording is a no-op
    assert PH.record_doji_sweeps([_fire(close=99.0)], coll=c) == 0
    assert c.docs["AAA:doji_sweep:2026-10-15"]["obs_close"] == 10.0       # $setOnInsert never overwrites
    assert len(c.docs) == 1


def test_record_uses_the_monkeypatched_coll_when_none_is_passed(monkeypatch):
    c = FakeColl()
    monkeypatch.setattr(PH, "_coll", lambda: c)
    assert PH.record_doji_sweeps([_fire("BBB")]) == 1 and "BBB:doji_sweep:2026-10-15" in c.docs


@pytest.mark.parametrize("bad", [{"symbol": None}, {"symbol": ""}, {"date": None}, {"date": "2026-10"},
                                 {"date": ""}])
def test_NEG_a_fire_missing_symbol_or_date_is_skipped_never_raises(bad):
    c = FakeColl()
    f = _fire()
    f.update(bad)
    assert PH.record_doji_sweeps([f, "junk", None, 7], coll=c) == 0 and c.docs == {}


def test_NEG_no_coll_or_no_fires_is_zero(monkeypatch):
    monkeypatch.setattr(PH, "_coll", lambda: None)
    assert PH.record_doji_sweeps([_fire()]) == 0
    assert PH.record_doji_sweeps([], coll=FakeColl()) == 0


def test_NEG_a_failing_write_is_logged_not_raised():
    class Boom(FakeColl):
        def update_one(self, *a, **k):
            raise RuntimeError("mongo down")
    assert PH.record_doji_sweeps([_fire(), _fire("BBB")], coll=Boom()) == 0


def test_B7_buckets_split_by_body_and_floor():
    c = FakeColl()
    fires = [_fire("H1"), _fire("W1", doji5=False), _fire("T1", adv50=3_000_000.0),
             _fire("T2", doji5=False, adv50=None)]
    assert PH.record_doji_sweeps(fires, coll=c) == 4
    got = {d["symbol"]: d["bucket"] for d in c.docs.values()}
    assert got == {"H1": HEAD, "W1": WIDE, "T1": THIN, "T2": THIN}


def test_NEG_an_unknown_bucket_is_recomputed_by_the_tabs_rule():
    c = FakeColl()
    PH.record_doji_sweeps([_fire("X1", bucket="made_up", adv50=1.0)], coll=c)
    assert c.docs["X1:doji_sweep:2026-10-15"]["bucket"] == THIN


# ── 2. grade ─────────────────────────────────────────────────────────────────
def _doc(day, close, **kw):
    d = {"et_date": day, "read": PH.DOJI_SWEEP_READ, "obs_close": close, "kind": PH.DOJI_SWEEP_KIND}
    d.update(kw)
    return d


def test_grade_candle_hits_on_an_up_move_and_misses_on_a_down_move():
    up = _df([10.0] * 10 + [10.5, 11.0, 11.5, 12.0, 12.5, 13.0])
    day = up.index[9].strftime("%Y-%m-%d")
    assert PH._grade_candle(up, _doji_obs(day, 10.0))["outcome"] == "hit"
    dn = _df([10.0] * 10 + [9.5, 9.0, 8.5, 8.0, 7.5, 7.0])
    res = PH._grade_candle(dn, _doji_obs(day, 10.0))
    assert res["outcome"] == "miss" and res["fwd_5_pct"] < 0


def _doji_obs(day, close):
    return _doc(day, close)


def test_NEG_a_bearish_word_would_invert_the_grade():
    up = _df([10.0] * 10 + [10.5, 11.0, 11.5, 12.0, 12.5, 13.0])
    day = up.index[9].strftime("%Y-%m-%d")
    assert PH._grade_candle(up, {**_doji_obs(day, 10.0), "read": "reversal_up_candidate"})["outcome"] == "miss"


def test_resolve_pending_grades_a_doji_sweep_doc(monkeypatch):
    from sepa import prices
    df = _df([10.0] * 30 + [10.5, 11.0, 11.5, 12.0, 12.5, 13.0])
    day = df.index[29].strftime("%Y-%m-%d")
    c = FakeColl()
    PH.record_doji_sweeps([_fire("AAA", day)], coll=c)
    monkeypatch.setattr(PH, "_coll", lambda: c)
    monkeypatch.setattr(prices, "load_prices", lambda sym: df)
    r = PH.resolve_pending()
    assert r["ok"] and r["resolved"] == 1 and r["skipped_ungradable"] == 0
    d = c.docs[f"AAA:doji_sweep:{day}"]
    assert d["resolved"] is True and d["outcome"] == "hit" and d["fwd_5_pct"] == 25.0


# ── 3. accuracy ──────────────────────────────────────────────────────────────
def _candle(_id, day, outcome, fwd, resolved=True):
    return {"_id": _id, "symbol": "CCC", "et_date": day, "kind": "candle", "formation": "hammer",
            "read": "bullish_reversal_setup", "resolved": resolved, "outcome": outcome, "fwd_5_pct": fwd}


def _dj(_id, day, bucket, *, resolved=True, outcome="hit", fwd=2.0, doji5=True):
    return {"_id": _id, "symbol": _id.split(":")[0], "et_date": day, "kind": PH.DOJI_SWEEP_KIND,
            "formation": PH.DOJI_SWEEP_KIND, "read": PH.DOJI_SWEEP_READ, "resolved": resolved,
            "outcome": outcome if resolved else None, "fwd_5_pct": fwd if resolved else None,
            "bucket": bucket, "doji5": doji5}


CANDLES = [_candle("c1", "2026-09-01", "hit", 1.0), _candle("c2", "2026-09-02", "miss", -2.0),
           _candle("c3", "2026-09-03", None, None, resolved=False)]
DOJIS = [_dj("A:doji_sweep:2026-08-01", "2026-08-01", HEAD, outcome="hit", fwd=3.0),
         _dj("B:doji_sweep:2026-08-02", "2026-08-02", HEAD, outcome="miss", fwd=-1.0),
         _dj("C:doji_sweep:2026-08-03", "2026-08-03", HEAD, outcome="hit", fwd=5.0),
         _dj("D:doji_sweep:2026-10-15", "2026-10-15", HEAD, resolved=False),
         _dj("E:doji_sweep:2026-07-01", "2026-07-01", WIDE, outcome="miss", fwd=-4.0, doji5=False),
         _dj("F:doji_sweep:2026-07-02", "2026-07-02", THIN, outcome="hit", fwd=9.0),
         _dj("G:doji_sweep:2026-10-14", "2026-10-14", THIN, resolved=False),
         _dj("H:doji_sweep:2026-06-01", "2026-06-01", "made_up", outcome="hit", fwd=1.0)]


def test_accuracy_serves_the_doji_block_and_never_touches_the_candle_numbers(monkeypatch):
    monkeypatch.setattr(PH, "_coll", lambda: FakeColl(CANDLES))
    base = PH.accuracy()
    monkeypatch.setattr(PH, "_coll", lambda: FakeColl(CANDLES + DOJIS))
    acc = PH.accuracy()
    assert acc["candles"] == base["candles"] and PH.DOJI_SWEEP_KIND not in acc["candles"]   # NEGATIVE
    assert acc["pending"] == base["pending"] == 1                                         # doji pending excluded
    assert acc["since"] == base["since"] == "2026-09-01"                                  # doji dates excluded
    dj = acc["doji_sweep"]
    assert dj["n"] == 3 and dj["pending"] == 1 and dj["since"] == "2026-08-01"
    assert dj["direction_hit_pct"] == 66.7 and dj["median_fwd_5d_pct"] == 3.0
    assert dj["horizon_bars"] == PH.CANDLE_HORIZON
    assert f"close {PH.CANDLE_HORIZON} sessions after" in dj["read_text"] and "reversal up" in dj["read_text"]
    assert "no placebo" in dj["note"].lower()


def test_B7_the_headline_never_pools_the_10pct_or_thin_fires(monkeypatch):
    monkeypatch.setattr(PH, "_coll", lambda: FakeColl(DOJIS))
    dj = PH.accuracy()["doji_sweep"]
    assert dj["n"] == 3                                              # HEAD only
    assert dj[WIDE] == {"n": 1, "pending": 0, "direction_hit_pct": 0.0, "median_fwd_5d_pct": -4.0,
                        "since": "2026-07-01"}
    assert dj[THIN] == {"n": 1, "pending": 1, "direction_hit_pct": 100.0, "median_fwd_5d_pct": 9.0,
                        "since": "2026-07-02"}
    assert dj["unbucketed"] == 1                                     # never joins a block
    assert dj["since"] == "2026-08-01"                               # the THIN / WIDE / unbucketed dates excluded


def test_NEG_no_doji_docs_serves_an_empty_block(monkeypatch):
    monkeypatch.setattr(PH, "_coll", lambda: FakeColl(CANDLES))
    dj = PH.accuracy()["doji_sweep"]
    assert dj["n"] == 0 and dj["pending"] == 0 and dj["direction_hit_pct"] is None and dj["since"] is None
    assert dj[WIDE]["n"] == 0 and dj[THIN]["n"] == 0


def test_NEG_compute_monthly_never_counts_a_doji_doc(monkeypatch):
    monkeypatch.setattr(PH, "_coll", lambda: FakeColl(CANDLES))
    base = PH.compute_monthly()
    monkeypatch.setattr(PH, "_coll", lambda: FakeColl(CANDLES + DOJIS))
    got = PH.compute_monthly()
    assert got == base
    assert [m["month"] for m in got] == ["2026-09"]
    assert sum(m["n_observations"] for m in got) == 2


# ── 4. the cron main (B8: the doji record runs LAST) ─────────────────────────
def _main_spies(monkeypatch, fires_fn):
    calls = []
    monkeypatch.setattr(PH, "resolve_pending", lambda: calls.append("resolve") or {"ok": True})
    monkeypatch.setattr(PH, "snapshot_monthly", lambda: calls.append("snapshot") or {"ok": True})
    monkeypatch.setattr(DJ, "ledger_fires", lambda **k: calls.append("fires") or fires_fn())
    c = FakeColl()
    monkeypatch.setattr(PH, "_coll", lambda: c)
    real = PH.record_doji_sweeps

    def rec(fires, **k):
        calls.append("record")
        return real(fires, **k)
    monkeypatch.setattr(PH, "record_doji_sweeps", rec)
    return calls, c


def test_main_records_two_fires_after_the_existing_kinds(monkeypatch):
    calls, c = _main_spies(monkeypatch, lambda: [_fire("AAA"), _fire("BBB")])
    assert PH.main() == 0
    assert calls == ["resolve", "snapshot", "fires", "record"]
    assert len(c.docs) == 2


def test_NEG_a_raising_doji_read_leaves_the_grading_and_the_exit_code(monkeypatch):
    def boom():
        raise RuntimeError("bulk read failed")
    calls, c = _main_spies(monkeypatch, boom)
    assert PH.main() == 0
    assert calls[:2] == ["resolve", "snapshot"] and "record" not in calls and c.docs == {}


def test_NEG_the_exit_code_is_resolve_pendings(monkeypatch):
    calls, _ = _main_spies(monkeypatch, lambda: [])
    monkeypatch.setattr(PH, "resolve_pending", lambda: calls.append("resolve") or {"ok": False})
    assert PH.main() == 1 and calls[0] == "resolve"


def test_the_module_entry_point_calls_main():
    src = inspect.getsource(PH)
    tail = src[src.index('if __name__ == "__main__":'):]
    assert "sys.exit(main())" in tail
    main_src = inspect.getsource(PH.main)
    assert main_src.index("resolve_pending()") < main_src.index("ledger_fires()")      # B8 order
