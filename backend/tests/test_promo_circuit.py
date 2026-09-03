"""Promo-circuit watch — behavioral tests (catalysts/promo_circuit.py).

Guards the 2026-09-01 provenance-study feature: roster shape, pure tag
extraction, the SEEDING/RAN/DUMPED decision table, EDGAR-tell windows,
the predictions penalty wiring (incl. NEGATIVES: no tag -> no penalty;
B-tier never penalizes via tags_for's tier filter), and the crontab line.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from catalysts import promo_circuit as pc
from catalysts import predictions


NOW = datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)


# --- roster ---------------------------------------------------------------

def test_roster_shape():
    assert pc.PROMO_ACCOUNTS, "roster must not be empty"
    for handle, meta in pc.PROMO_ACCOUNTS.items():
        assert handle.strip() and " " not in handle, handle
        assert meta["tier"] in ("S", "A", "B"), handle
        assert meta.get("evidence"), f"{handle} needs a dated evidence line"


def test_roster_has_the_study_accounts():
    # The four load-bearing catches from the provenance study.
    for h in ("ShangVXO", "topstockalerts", "beppels", "StockSenseiTrendTraders"):
        assert h in pc.PROMO_ACCOUNTS, h
    assert pc.PROMO_ACCOUNTS["ShangVXO"]["tier"] == "S"


# --- extract_tags (pure) --------------------------------------------------

def _msg(mid, created, body, *symbols):
    return {"id": mid, "created_at": created, "body": body,
            "symbols": [{"symbol": s} for s in symbols]}


def test_extract_tags_basic_and_multisymbol():
    msgs = [
        _msg(100, "2026-08-30T12:00:00Z", "watch these $ABCD $EFGH", "ABCD", "EFGH"),
        _msg(101, "2026-08-31T09:00:00Z", "ABCD again", "ABCD"),
    ]
    tags = pc.extract_tags("someacct", msgs)
    assert set(tags) == {"ABCD", "EFGH"}
    assert tags["ABCD"]["n_messages"] == 2
    assert tags["ABCD"]["first_tagged_at"].day == 30
    assert tags["ABCD"]["last_tagged_at"].day == 31
    assert tags["ABCD"]["sample"] == "ABCD again"   # latest message wins
    assert tags["ABCD"]["max_msg_id"] == 101


def test_extract_tags_respects_high_water_mark():
    msgs = [_msg(100, "2026-08-30T12:00:00Z", "old", "ABCD"),
            _msg(101, "2026-08-31T09:00:00Z", "new", "ABCD")]
    tags = pc.extract_tags("someacct", msgs, after_msg_id=100)
    assert tags["ABCD"]["n_messages"] == 1          # only the new message


def test_extract_tags_skips_excluded_and_crypto():
    msgs = [_msg(1, "2026-08-30T12:00:00Z", "macro", "SPY", "BTC.X", "TINY")]
    tags = pc.extract_tags("someacct", msgs)
    assert set(tags) == {"TINY"}


def test_extract_tags_bad_timestamp_dropped():
    msgs = [_msg(1, "not-a-date", "junk", "ABCD")]
    assert pc.extract_tags("someacct", msgs) == {}


def test_extract_tags_exposes_per_message_ids():
    # sweep() needs per-ticker message ids for its per-ticker high-water
    # mark (an account-wide mark buried failed sibling upserts forever).
    msgs = [_msg(100, "2026-08-30T12:00:00Z", "a", "ABCD"),
            _msg(101, "2026-08-31T09:00:00Z", "b", "ABCD", "EFGH")]
    tags = pc.extract_tags("someacct", msgs)
    assert tags["ABCD"]["msg_ids"] == [100, 101]
    assert tags["EFGH"]["msg_ids"] == [101]


# --- price_action_since (pure) -------------------------------------------

def _t(day):
    return int(datetime(2026, 8, day, 5, 0, tzinfo=timezone.utc).timestamp() * 1000)


def test_price_action_since_math():
    bars = [{"c": 1.00, "h": 1.05}, {"c": 1.40, "h": 1.60}, {"c": 1.10, "h": 1.15}]
    pa = pc.price_action_since(bars)
    assert pa["pct_since_tag"] == 10.0          # 1.10 / 1.00
    assert pa["max_gain_pct"] == 60.0           # peak 1.60
    assert round(pa["drop_from_peak_pct"]) == -31   # 1.10 / 1.60
    assert pa["last_close"] == 1.10


def test_price_action_since_empty_is_all_none():
    pa = pc.price_action_since(None)
    assert pa["pct_since_tag"] is None and pa["max_gain_pct"] is None


def test_weekend_tag_uses_prior_close_as_base():
    # REGRESSION (review 2026-09-01): Saturday tag, Monday +44% run. Base
    # must be Friday's close, not Monday's own post-run close — otherwise
    # the run is invisible and a vertical shows as SEEDING forever.
    bars = [
        {"t": _t(28), "o": 0.98, "h": 1.02, "c": 1.00},   # Fri 8/28
        {"t": _t(31), "o": 1.10, "h": 1.50, "c": 1.44},   # Mon 8/31 run day
    ]
    tag_sat = datetime(2026, 8, 29, 13, 0, tzinfo=timezone.utc).date()
    pa = pc.price_action_since(bars, tag_date=tag_sat)
    assert pa["max_gain_pct"] == 50.0            # vs Friday close 1.00
    assert pc.classify_status(0.5, pa["pct_since_tag"], pa["max_gain_pct"],
                              pa["drop_from_peak_pct"]) == "RAN"
    # ...and the subsequent collapse is DUMPED, not SEEDING
    sep1 = int(datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc).timestamp() * 1000)
    bars_dumped = bars + [{"t": sep1, "o": 1.00, "h": 1.00, "c": 0.80}]
    pa2 = pc.price_action_since(bars_dumped, tag_date=tag_sat)
    assert pc.classify_status(1.5, pa2["pct_since_tag"], pa2["max_gain_pct"],
                              pa2["drop_from_peak_pct"]) == "DUMPED"


def test_fresh_listing_falls_back_to_first_open():
    bars = [{"t": _t(31), "o": 1.10, "h": 1.50, "c": 1.44}]   # no prior bar
    pa = pc.price_action_since(bars, tag_date=datetime(2026, 8, 29, tzinfo=timezone.utc).date())
    assert pa["max_gain_pct"] == round((1.50 / 1.10 - 1) * 100, 1)


def test_tag_after_all_bars_is_unknown_shape():
    bars = [{"t": _t(28), "o": 1, "h": 1, "c": 1}]
    pa = pc.price_action_since(bars, tag_date=datetime(2026, 9, 15, tzinfo=timezone.utc).date())
    assert pa["pct_since_tag"] is None


# --- classify_status decision table --------------------------------------

def test_status_seeding_fresh_tag_no_run():
    assert pc.classify_status(2.0, 4.0, 12.0, -5.0) == "SEEDING"


def test_status_ran():
    assert pc.classify_status(3.0, 35.0, 45.0, -8.0) == "RAN"


def test_status_dumped_after_run():
    # Ran +60% at the peak, now 55% below it — the circuit exited.
    assert pc.classify_status(5.0, -20.0, 60.0, -55.0) == "DUMPED"


def test_status_quiet_old_tag_never_ran():
    assert pc.classify_status(12.0, 3.0, 8.0, -2.0) == "QUIET"


def test_status_unknown_without_prices():
    assert pc.classify_status(2.0, None, None, None) == "UNKNOWN"


def test_status_boundary_run_threshold():
    assert pc.classify_status(2.0, 10.0, pc.RAN_MIN_GAIN_PCT, -1.0) == "RAN"
    assert pc.classify_status(2.0, 10.0, pc.RAN_MIN_GAIN_PCT - 0.1, -1.0) == "SEEDING"


def test_status_seeding_keyed_to_latest_tag_not_campaign_start():
    # REGRESSION (review 2026-09-01): a campaign kept warm for 11 days and
    # re-flagged premarket (beppels' RDAC) is SEEDING because the LATEST
    # tag is fresh — first-tag age must not expire it to QUIET.
    days_since_last_tag = 0.2      # re-flagged this morning
    assert pc.classify_status(days_since_last_tag, 3.0, 9.0, -2.0) == "SEEDING"


# --- EDGAR tells ----------------------------------------------------------

def test_edgar_owner_stake_within_14d_only():
    fresh = [{"form": "SC 13G", "filing_date": "2026-08-25", "url": "u"}]
    stale = [{"form": "SC 13G", "filing_date": "2026-08-10", "url": "u"}]
    assert pc.edgar_flags_from_filings(fresh, now=NOW)["owner_stake"] is not None
    assert pc.edgar_flags_from_filings(stale, now=NOW)["owner_stake"] is None


def test_edgar_owner_stake_amendment_counts():
    f = [{"form": "SC 13D/A", "filing_date": "2026-08-28", "url": "u"}]
    assert pc.edgar_flags_from_filings(f, now=NOW)["owner_stake"] is not None


def test_edgar_shelf_forms_and_s8_excluded():
    shelf = [{"form": "424B5", "filing_date": "2026-08-20", "url": "u"}]
    s8 = [{"form": "S-8", "filing_date": "2026-08-20", "url": "u"}]
    assert pc.edgar_flags_from_filings(shelf, now=NOW)["shelf"] is not None
    assert pc.edgar_flags_from_filings(s8, now=NOW)["shelf"] is None


def test_edgar_shelf_window_30d():
    old = [{"form": "S-3", "filing_date": "2026-07-25", "url": "u"}]
    assert pc.edgar_flags_from_filings(old, now=NOW)["shelf"] is None


def test_edgar_empty_filings():
    flags = pc.edgar_flags_from_filings([], now=NOW)
    assert flags == {"owner_stake": None, "shelf": None}


# --- predictions penalty wiring ------------------------------------------

BASE_CANDIDATE = {"ticker": "TINY", "quadrant": "DEAD", "pump": {},
                  "evidence": {}, "volume_surge_ratio": 0, "change_pct": 0,
                  "chatter_score": 0, "evidence_score": 0}


def test_promo_penalty_fires_with_signal():
    sigs = predictions._extract_signals(
        dict(BASE_CANDIDATE),
        promo_signal={"handles": ["beppels", "topstockalerts", "ShangVXO"],
                      "tiers": ["A", "A", "S"], "days_ago": 2.0})
    pen = [p for p in sigs["penalties"] if p["type"] == "promo_circuit_tagged"]
    assert len(pen) == 1
    assert pen[0]["weight"] == predictions.PENALTY_WEIGHTS["promo_circuit_tagged"]
    assert not pen[0].get("hard_veto")           # negative, but NOT a veto
    assert "@beppels" in pen[0]["detail"] and "+1" in pen[0]["detail"]


def test_promo_penalty_absent_without_signal():
    sigs = predictions._extract_signals(dict(BASE_CANDIDATE), promo_signal=None)
    assert not any(p["type"] == "promo_circuit_tagged" for p in sigs["penalties"])
    # empty-handles record must not fire either
    sigs2 = predictions._extract_signals(dict(BASE_CANDIDATE),
                                         promo_signal={"handles": []})
    assert not any(p["type"] == "promo_circuit_tagged" for p in sigs2["penalties"])


def test_promo_penalty_reaches_bear_thesis():
    sigs = predictions._extract_signals(
        dict(BASE_CANDIDATE),
        promo_signal={"handles": ["ShangVXO"], "tiers": ["S"], "days_ago": 1.0})
    thesis = predictions._synthesize_thesis(dict(BASE_CANDIDATE),
                                            sigs["signals"], sigs["penalties"])
    assert "promo-circuit" in (thesis["bear_thesis"] or "")


def test_promo_penalty_weight_in_table():
    assert predictions.PENALTY_WEIGHTS["promo_circuit_tagged"] < 0


def test_promo_penalty_gated_by_market_cap():
    # REGRESSION (review 2026-09-01): an alert account tagging a liquid
    # name in passing must not dock a real candidate — tiny floats only.
    sig = {"handles": ["beppels"], "tiers": ["A"], "days_ago": 1.0}
    big = predictions._extract_signals(
        {**BASE_CANDIDATE, "market_cap": 10e9}, promo_signal=sig)
    assert not any(p["type"] == "promo_circuit_tagged" for p in big["penalties"])
    small = predictions._extract_signals(
        {**BASE_CANDIDATE, "market_cap": 500e6}, promo_signal=sig)
    assert any(p["type"] == "promo_circuit_tagged" for p in small["penalties"])
    # unknown cap = likely tiny -> penalty applies
    nocap = predictions._extract_signals(dict(BASE_CANDIDATE), promo_signal=sig)
    assert any(p["type"] == "promo_circuit_tagged" for p in nocap["penalties"])


# --- offline behavior -----------------------------------------------------

def test_tags_for_no_mongo_returns_empty(monkeypatch):
    monkeypatch.setattr(pc, "_tags_coll", lambda: None)
    assert pc.tags_for(["TINY"]) == {}


def test_tags_for_empty_tickers_no_query():
    assert pc.tags_for([]) == {}


def test_prune_shotgun_tags():
    # REGRESSION (measured 2026-09-01): 274 fake SEEDING rows from
    # drive-by cashtags. Shotgun accounts keep only repeated tickers;
    # focused accounts keep everything.
    shotgun = [{"account": "spray", "ticker": f"T{i}", "n_messages": 1}
               for i in range(30)]
    shotgun.append({"account": "spray", "ticker": "REAL", "n_messages": 3})
    focused = [{"account": "sniper", "ticker": "AAAA", "n_messages": 1}]
    out = pc.prune_shotgun_tags(shotgun + focused)
    kept = {(t["account"], t["ticker"]) for t in out}
    assert ("spray", "REAL") in kept
    assert ("sniper", "AAAA") in kept
    assert not any(a == "spray" and t.startswith("T") for a, t in kept)


def test_prune_shotgun_keeps_all_below_threshold():
    tags = [{"account": "few", "ticker": f"T{i}", "n_messages": 1} for i in range(10)]
    assert len(pc.prune_shotgun_tags(tags)) == 10


class _FakeColl:
    def __init__(self, docs):
        self.docs = docs

    def find(self, *_a, **_k):
        return list(self.docs)


def test_tags_for_uses_live_roster_tier_not_stored(monkeypatch):
    # REGRESSION (review 2026-09-01): roster edits apply immediately.
    now = datetime.now(timezone.utc)
    docs = [
        # Stored as B (stale snapshot) but ShangVXO is S in the roster -> counts.
        {"account": "ShangVXO", "ticker": "AAAA", "tier": "B", "last_tagged_at": now},
        # Stored as A but stockusfrance is B in the roster -> must NOT count.
        {"account": "stockusfrance", "ticker": "BBBB", "tier": "A", "last_tagged_at": now},
        # Account no longer on the roster -> must NOT count.
        {"account": "gone_account", "ticker": "CCCC", "tier": "S", "last_tagged_at": now},
    ]
    monkeypatch.setattr(pc, "_tags_coll", lambda: _FakeColl(docs))
    out = pc.tags_for(["AAAA", "BBBB", "CCCC"])
    assert set(out) == {"AAAA"}
    assert out["AAAA"]["tiers"] == ["S"]


def test_tags_for_per_account_penalty_window(monkeypatch):
    # ShangVXO's pumps land ~10 sessions after the tag (PETZ session 9,
    # FLYE session 8 — measured 2026-09-02), so his window is 14d while
    # the default stays 7d.
    now = datetime.now(timezone.utc)
    ten_days = now - timedelta(days=10)
    docs = [
        {"account": "ShangVXO", "ticker": "AAAA", "last_tagged_at": ten_days},
        {"account": "beppels", "ticker": "BBBB", "last_tagged_at": ten_days},
    ]
    monkeypatch.setattr(pc, "_tags_coll", lambda: _FakeColl(docs))
    out = pc.tags_for(["AAAA", "BBBB"])
    assert "AAAA" in out
    assert "BBBB" not in out
    assert pc.PROMO_ACCOUNTS["ShangVXO"]["penalty_days"] >= 10


class _ErrColl:
    def find(self, *_a, **_k):
        raise RuntimeError("server selection timeout")


def test_sweep_survives_mongo_read_failure(monkeypatch):
    # REGRESSION (review 2026-09-01): MongoClient is lazy, so a down Mongo
    # raises at find() — the sweep must skip that account's writes and keep
    # going, not crash the cron run.
    monkeypatch.setattr(pc, "_fetch_user_stream",
                        lambda h, **k: [_msg(1, "2026-08-30T12:00:00Z", "x", "TINY")])
    monkeypatch.setattr(pc, "_tags_coll", lambda: _ErrColl())
    monkeypatch.setattr(pc, "_coll", lambda name: None)   # meta coll offline too
    out = pc.sweep()
    assert out["accounts_ok"] == len(pc.PROMO_ACCOUNTS)
    assert all(f.endswith(":mongo") for f in out["accounts_failed"])
    assert len(out["accounts_failed"]) == len(pc.PROMO_ACCOUNTS)


# --- source guards --------------------------------------------------------

def test_crontab_has_promo_sweep_lines():
    crontab = (Path(__file__).resolve().parents[1] / "crontab").read_text()
    lines = [l for l in crontab.splitlines()
             if "catalysts.promo_circuit" in l and not l.strip().startswith("#")]
    assert len(lines) >= 2, "need weekday + weekend sweep lines"
    assert any(re.search(r"\b1-5\b", l) for l in lines), "weekday sweep missing"
    assert any(re.search(r"\b0,6\b", l) for l in lines), "weekend sweep missing"


def test_api_exposes_promo_routes():
    src = (Path(__file__).resolve().parents[1] / "catalysts" / "api.py").read_text()
    assert '"/catalysts/promo-circuit"' in src
    assert '"/catalysts/promo-circuit/sweep"' in src


def test_price_action_carries_the_base_close_for_live_reads():
    from datetime import date, datetime, timezone
    ms = lambda y, m, d: int(datetime(y, m, d, 20, 0, tzinfo=timezone.utc).timestamp() * 1000)
    bars = [{"t": ms(2026, 8, 28), "o": 9.8, "h": 10.6, "l": 9.7, "c": 10.5},
            {"t": ms(2026, 9, 1), "o": 10.6, "h": 12.0, "l": 10.4, "c": 11.5}]
    pa = pc.price_action_since(bars, tag_date=date(2026, 9, 1))
    assert pa["base_close"] == 10.5 and pa["pct_since_tag"] == 9.5
    assert pc.price_action_since([], tag_date=date(2026, 9, 1))["base_close"] is None


def test_sweep_cron_is_ten_minutes_on_weekdays():
    from pathlib import Path
    crontab = (Path(__file__).resolve().parents[1] / "crontab").read_text()
    line = [l for l in crontab.splitlines() if "catalysts.promo_circuit" in l and "1-5" in l][0]
    assert line.startswith("*/10")


def test_extract_tags_keeps_every_post_with_time_and_text():
    msgs = [{"id": 11, "created_at": "2026-09-01T13:23:00Z", "body": "$TLYS watch", "symbols": [{"symbol": "TLYS"}]},
            {"id": 12, "created_at": "2026-09-02T19:35:00Z", "body": "$TLYS what looked ordinary this morning looks much better now.", "symbols": [{"symbol": "TLYS"}]}]
    rec = pc.extract_tags("topstockalerts", msgs)["TLYS"]
    assert [p["id"] for p in rec["posts"]] == [11, 12]
    assert rec["posts"][1]["body"].startswith("$TLYS what looked ordinary") and rec["posts"][1]["at"].hour == 19


def test_sweep_pushes_only_fresh_posts_capped(monkeypatch):
    calls = []

    class _Coll:
        def find(self, q): return [{"ticker": "TLYS", "max_msg_id": 11, "first_tagged_at": "2026-09-01T13:23:00+00:00",
                                    "last_tagged_at": "2026-09-01T13:23:00+00:00", "n_messages": 1}]
        def update_one(self, q, u, upsert=False): calls.append((q, u))
        def find_one(self, q): return {}
    monkeypatch.setattr(pc, "_tags_coll", lambda: _Coll())
    monkeypatch.setattr(pc, "_coll", lambda name: _Coll())
    monkeypatch.setattr(pc, "PROMO_ACCOUNTS", {"topstockalerts": {"tier": "A"}})
    monkeypatch.setattr(pc, "_fetch_user_stream", lambda handle, **kw: [
        {"id": 11, "created_at": "2026-09-01T13:23:00Z", "body": "old", "symbols": [{"symbol": "TLYS"}]},
        {"id": 12, "created_at": "2026-09-02T19:35:00Z", "body": "new", "symbols": [{"symbol": "TLYS"}]}])
    pc.sweep()
    tag_updates = [u for q, u in calls if q.get("_id") == "topstockalerts:TLYS"]
    assert tag_updates and "$push" in tag_updates[0]
    pushed = tag_updates[0]["$push"]["posts"]
    assert [p["id"] for p in pushed["$each"]] == [12] and pushed["$slice"] == -pc.MAX_POSTS_KEPT


# ── Early callers added 2026-09-02 (winner-provenance study + Aug backtest) ──
EARLY_CALLERS = ["theblueflames", "stock_catcher", "blakecapital26", "jmjtrading",
                 "birdseyetrader", "davidscott", "sadyk189", "robbysinvestmentllc"]


def test_early_callers_are_radar_only_never_penalty_never_alert():
    from catalysts import promo_live as pl
    for h in EARLY_CALLERS:
        m = pc.PROMO_ACCOUNTS[h]
        assert m["tier"] == "B" and "penalty_days" not in m, h
        assert "backtest" in m["audit"] and "%" in m["audit"] and m["evidence"], h
        assert h not in pl.PROMO_ALERT_HANDLES, h


# ── five tells per row (Ajay 2026-09-02) ─────────────────────────────────────
from datetime import datetime as _dt, timezone as _tz  # noqa: E402

_NOW = _dt(2026, 9, 2, 20, 0, tzinfo=_tz.utc)


def test_sec_flags_eightk_window_items_and_rollup():
    fs = [
        {"form": "8-K", "filing_date": "2026-09-01", "url": "u1", "items": "1.01,9.01"},
        {"form": "8-K", "filing_date": "2026-08-25", "url": "u0", "items": "2.02"},
        {"form": "8-K", "filing_date": "2026-08-01", "url": "old", "items": "8.01"},   # outside 14d
        {"form": "4", "filing_date": "2026-08-30", "url": "f4a"},
        {"form": "4", "filing_date": "2026-08-29", "url": "f4b"},
        {"form": "424B5", "filing_date": "2026-08-20", "url": "off"},
        {"form": "S-8", "filing_date": "2026-08-21", "url": "s8"},
        {"form": "10-Q", "filing_date": "2026-07-01", "url": "oldq"},                   # outside 30d
    ]
    out = pc.sec_flags_from_filings(fs, now=_NOW)
    assert out["eightk"] == {"form": "8-K", "filing_date": "2026-09-01", "url": "u1",
                             "items": ["1.01", "9.01"], "n_14d": 2}
    sec = out["sec"]
    assert sec["n_30d"] == 4 and sec["forms"] == ["4", "S-8", "424B5"]
    assert sec["latest"]["filing_date"] == "2026-08-30" and sec["n_form4"] == 2
    assert sec["has_offering"] is True                       # 424B5 counts, S-8 never does
    assert pc.sec_flags_from_filings([], now=_NOW) == {"eightk": None, "sec": None}
    # NEGATIVE: only an old 8-K -> no eightk, and it never leaks into sec
    assert pc.sec_flags_from_filings([fs[2]], now=_NOW) == {"eightk": None, "sec": None}


def test_catalyst_from_news_verdicts():
    assert pc.catalyst_from_news(None) is None                 # fetch failed = unknown
    assert pc.catalyst_from_news([])["verdict"] == "NONE"
    thin = pc.catalyst_from_news([{"title": "Stock moves", "tone": "neutral", "published_utc": "2026-09-02T10:00:00Z"}])
    assert thin["verdict"] == "THIN" and thin["top"]["title"] == "Stock moves"
    real = pc.catalyst_from_news([
        {"title": "Chatter", "tone": "neutral", "published_utc": "2026-09-02T12:00:00Z"},
        {"title": "Wins $40M contract", "tone": "bullish", "published_utc": "2026-09-02T09:00:00Z", "url": "u", "publisher": "GlobeNewswire"},
    ])
    assert real["verdict"] == "REAL" and real["n_48h"] == 2 and real["n_bullish"] == 1
    assert real["top"]["title"] == "Wins $40M contract" and real["top"]["publisher"] == "GlobeNewswire"


class _Coll:
    def __init__(self):
        self.docs = {}
    def find(self, q):
        ids = q["_id"]["$in"]
        return [d for k, d in self.docs.items() if k in ids]
    def find_one(self, q):
        return self.docs.get(q["_id"])
    def update_one(self, q, u, upsert=False):
        self.docs.setdefault(q["_id"], {"_id": q["_id"]}).update(u["$set"])


def test_sales_for_snapshot_then_cache_then_capped_fetch():
    fetched = []
    coll = _Coll()
    coll.docs["CACHED"] = {"_id": "CACHED", "at": 1e12, "sales": {"tier": "weak", "growth_yoy_pct": 2.0, "source": "provider"}}
    def snapshot(syms):
        return {"SEPA": {"sales": {"tier": "strong", "growth_yoy_pct": 38.0, "score": 80}}}
    def fetch(sym):
        fetched.append(sym)
        return {"tier": "unknown", "reason": "insufficient revenue history (need >= 5 quarters)"} if sym == "NEWB" else None
    out = pc.sales_for(["SEPA", "CACHED", "NEWB", "NONE", "OVERCAP"], fetch=fetch, snapshot=snapshot, coll=coll, cap=2)
    assert out["SEPA"]["tier"] == "strong" and out["SEPA"]["source"] == "sepa_research"
    assert out["CACHED"]["tier"] == "weak"
    assert fetched == ["NEWB", "NONE"]                         # cap=2 -> OVERCAP waits for the next build
    assert out["NEWB"]["tier"] == "unknown" and "insufficient" in out["NEWB"]["reason"]
    assert out["NONE"] is None and "OVERCAP" not in out
    assert coll.docs["NEWB"]["sales"]["source"] == "provider"  # cached for 7 days
    assert coll.docs["NONE"]["sales"] is None                  # a looked-and-empty is cached too


def test_russell_for_reads_the_cached_board_raw():
    coll = _Coll()
    coll.docs["board"] = {"_id": "board", "payload": {
        "as_of": "2026-09-03T00:30:00Z",
        "adds_r2000": [{"symbol": "SYM", "board": "add_r2000", "market_cap": 5.2e9,
                        "add_event": {"key": "recon_dec_2026", "in_index": "2026-12-14"}, "first_seen": "2026-09-03T00:30:00Z"}],
        "promotions_r1000": [{"symbol": "BIG", "board": "promote_r1000", "market_cap": 6e9, "add_event": None}]}}
    out = pc.russell_for(coll=coll)
    assert out["SYM"]["add_event"]["in_index"] == "2026-12-14" and out["SYM"]["as_of"] == "2026-09-03T00:30:00Z"
    assert out["BIG"]["board"] == "promote_r1000"
    assert pc.russell_for(coll=_Coll()) == {}


def test_build_row_carries_the_five_tells_and_one_edgar_fetch_feeds_three(monkeypatch):
    import inspect
    src = inspect.getsource(pc)
    body = src[src.index("def _row(tkr: str)"):src.index("status_rank = ")]
    for k in ('"russell"', '"sales"', '"catalyst"', '"eightk"', '"sec"'):
        assert k in body, k
    enrich = src[src.index("def _enrich(row"):src.index("def _enrich(row") + 400]
    assert "_edgar_bundle(row" in enrich and "_catalyst(row" in enrich
    calls = []
    monkeypatch.setattr(pc, "_fetch_sec_filings", None, raising=False)
    import catalysts.evidence as ev
    monkeypatch.setattr(ev, "_fetch_sec_filings", lambda t, days=7: calls.append((t, days)) or [
        {"form": "8-K", "filing_date": "2026-09-01", "url": "u", "items": "8.01"},
        {"form": "SC 13G", "filing_date": "2026-09-01", "url": "g"}])
    b = pc._edgar_bundle("TINY")
    assert calls == [("TINY", 30)]                              # ONE fetch
    assert b["edgar"]["owner_stake"]["form"] == "SC 13G" and b["eightk"]["items"] == ["8.01"]
    assert b["sec"]["forms"] == ["SC 13G"]


# ── stale-while-revalidate, single flight (2026-09-03: the 16-min board hang) ─
def _cache_doc(age_sec, payload=None):
    from datetime import datetime as _d, timedelta as _td, timezone as _z
    return {"_id": "latest", "cached_at": _d.now(_z.utc) - _td(seconds=age_sec),
            "payload": payload or {"rows": [], "as_of": "x"}}


class _CacheColl:
    def __init__(self, doc): self.doc = doc
    def find_one(self, q): return self.doc
    def update_one(self, *a, **k): pass


def test_build_serves_fresh_cache_and_never_blocks_on_a_stale_one(monkeypatch):
    started = []
    monkeypatch.setattr(pc, "_coll", lambda name: _CacheColl(_cache_doc(30)))
    monkeypatch.setattr(pc, "_build_now", lambda: started.append("sync") or {"rows": []})
    class T:
        def __init__(self, target=None, **kw): self.target = target
        def start(self): started.append("thread")
    monkeypatch.setattr(pc.threading, "Thread", T)
    pc._REFRESHING["on"] = False
    out = pc.build()
    assert out["cached"] is True and "stale" not in out and started == []
    # expired: stale copy back at once, ONE background rebuild kicked
    monkeypatch.setattr(pc, "_coll", lambda name: _CacheColl(_cache_doc(pc._CACHE_TTL_SEC + 5)))
    out = pc.build()
    assert out["stale"] is True and out["refreshing"] is True and started == ["thread"]
    assert pc._REFRESHING["on"] is True                      # the fake thread never ran → still flagged
    out2 = pc.build()                                        # a second caller does not start another
    assert started == ["thread"] and "already running" in out2["stale_note"]
    # force from the UI with a cache present → same non-blocking path
    out3 = pc.build(force=True)
    assert out3["refreshing"] is True and started == ["thread"]
    pc._REFRESHING["on"] = False
    # nothing cached at all → the only case that builds inline
    monkeypatch.setattr(pc, "_coll", lambda name: _CacheColl(None))
    assert pc.build() == {"rows": []} and started == ["thread", "sync"]


def test_cron_entry_builds_inline_not_via_the_daemon_thread():
    import inspect
    src = inspect.getsource(pc)
    main = src[src.index('if __name__ == "__main__"'):]
    assert "_build_now()" in main and "build(force=True)" not in main


def test_sales_fill_is_massive_only_and_capped():
    import inspect
    src = inspect.getsource(pc.sales_for)
    assert "_fetch_massive_financials" in src and "fundamentals_for" not in src
    assert pc.SALES_FETCH_CAP <= 12 and pc.SALES_FETCH_BUDGET_SEC <= 15
