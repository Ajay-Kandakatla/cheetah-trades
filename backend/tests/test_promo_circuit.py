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
