"""🧬 med_catalyst push (catalysts/medical/alerts.py, spec §3.8) + the kind's registries.

Ajay 2026-09-29: "…and add right setup and alerts". NEGATIVES first: sub-$2,
thin, unknown liquidity, closed day, stale, recap, low-impact types, baseline —
none of them ever reaches the sender. Once per event; one topline push per
name per session; a transport failure releases the claim; a muted send keeps it.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import alerts as A          # noqa: E402
from catalysts.medical import store as S           # noqa: E402
from tests.test_med_store import FakeColl          # noqa: E402

ET = ZoneInfo("America/New_York")
MON_0730 = datetime(2026, 9, 28, 7, 30, tzinfo=ET)
LABOR_DAY = datetime(2026, 9, 7, 7, 30, tzinfo=ET)


def et(*a):
    return datetime(*a, tzinfo=ET)


def kod(**kw) -> dict:
    """The KOD 2026-09-28 event as the routine stores it (§1.6 numbers)."""
    ev = {"_id": "KOD|topline_positive|2026-09-28", "ticker": "KOD", "company": "Kodiak Sciences Inc.",
          "event_type": "topline", "subtype": None, "direction": "positive", "phase": "3",
          "regulator": None, "type_dir": "topline_positive", "trials": ["DAYBREAK"],
          "modality": ["antibody_bispecific"], "areas": ["ophthalmology"], "session_date": "2026-09-28",
          "published_at": datetime(2026, 9, 28, 6, 34, tzinfo=timezone.utc),       # 02:34 ET
          "first_seen_at": datetime(2026, 9, 28, 11, 25, tzinfo=timezone.utc),     # 07:25 ET
          "sources": [{"provider": "finnhub"}, {"provider": "sec"}, {"provider": "finnhub"}],
          "baseline": False, "push": {"state": "pending"},
          "reaction": {"at_detection": {"price": 55.64, "move_pct": 72.0, "session": "premarket",
                                        "as_of": et(2026, 9, 28, 7, 24).isoformat()},
                       "liquidity": {"base_close": 32.35, "adv50_usd": 22.7e6, "avg_vol50": 672_000.0}}}
    ev.update(kw)
    return ev


@pytest.fixture(autouse=True)
def _live_mode(monkeypatch):
    """Fix round 3 ships SHADOW = True (tests/test_med_fix3_2026_09_29.py pins
    it); the send-path tests below exercise LIVE mode."""
    monkeypatch.setattr(A, "SHADOW", False)


def liq(ev, **kw):
    ev["reaction"]["liquidity"].update(kw)
    return ev


# ── gate: the negatives ─────────────────────────────────────────────────────
def test_KOD_passes_the_gate_pre_market():
    assert A.gate(kod(), now_et=MON_0730, baseline=False, prior=[]) is None


def test_HUMA_under_two_dollars_is_blocked_price():
    ev = liq(kod(_id="HUMA|fda_approval|2026-09-28", ticker="HUMA", event_type="fda_approval",
                 type_dir="fda_approval", subtype="novel", regulator="FDA"), base_close=0.56, adv50_usd=2.3e6)
    assert A.gate(ev, now_et=MON_0730, baseline=False, prior=[]) == "blocked_price"


def test_MNOV_thin_is_blocked_dollar_vol_and_its_undirected_topline_is_not_high_impact():
    thin = liq(kod(ticker="MNOV"), base_close=2.58, adv50_usd=0.1e6)
    assert A.gate(thin, now_et=MON_0730, baseline=False, prior=[]) == "blocked_dollar_vol"
    undirected = liq(kod(ticker="MNOV", direction="unknown", phase=None, type_dir="topline_unknown"),
                     base_close=2.58, adv50_usd=0.1e6)
    assert A.gate(undirected, now_et=MON_0730, baseline=False, prior=[]) == "not_high_impact"


def test_unknown_liquidity_fails_CLOSED():
    for kw in ({"base_close": None}, {"adv50_usd": None}):
        assert A.gate(liq(kod(), **kw), now_et=MON_0730, baseline=False, prior=[]) == "blocked_unknown_liquidity"


def test_the_floors_are_read_from_trading_safety_floor(monkeypatch):
    from trading import safety_floor as SF
    monkeypatch.setattr(SF, "THIN_DOLLAR_VOL", 25e6)
    assert A.gate(kod(), now_et=MON_0730, baseline=False, prior=[]) == "blocked_dollar_vol"
    monkeypatch.setattr(SF, "THIN_DOLLAR_VOL", 5e6)
    monkeypatch.setattr(SF, "MIN_SHARE_PRICE", 40.0)
    assert A.gate(kod(), now_et=MON_0730, baseline=False, prior=[]) == "blocked_price"


def test_closed_day(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    ev = kod(published_at=datetime(2026, 9, 7, 10, 34, tzinfo=timezone.utc), session_date="2026-09-08")
    assert A.gate(ev, now_et=LABOR_DAY, baseline=False, prior=[]) == "closed_day"


@pytest.mark.parametrize("now,expected", [
    (et(2026, 9, 28, 9, 20), None),       # 06:00 PR, pre-market: 0 RTH minutes
    (et(2026, 9, 28, 9, 36), None),       # 6 minutes of regular trading
    (et(2026, 9, 28, 13, 0), "stale"),    # 210 minutes — the session has traded it
])
def test_stale_is_regular_session_minutes_since_publication(now, expected):
    ev = kod(published_at=datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc))   # 06:00 ET
    assert A.gate(ev, now_et=now, baseline=False, prior=[]) == expected


def test_an_11_00_release_seen_11_05_may_push_and_weekend_news_rings_monday_pre_market():
    ev = kod(published_at=datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc))   # 11:00 ET
    assert A.gate(ev, now_et=et(2026, 9, 28, 11, 5), baseline=False, prior=[]) is None
    sat = kod(published_at=datetime(2026, 9, 26, 14, 0, tzinfo=timezone.utc))  # Saturday
    assert A.gate(sat, now_et=et(2026, 9, 28, 4, 5), baseline=False, prior=[]) is None


def test_recap_a_second_same_kind_event_within_21_sessions_stays_on_the_board_only():
    first = kod(push={"state": "pushed"})
    again = kod(_id="KOD|topline_positive|2026-10-05", session_date="2026-10-05",
                published_at=datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc))
    assert A.gate(again, now_et=et(2026, 10, 5, 6, 30), baseline=False, prior=[first]) == "recap"
    # NEGATIVE: a first event that never rang (blocked) is not a recap source
    blocked = kod(push={"state": "blocked:price"})
    assert A.gate(again, now_et=et(2026, 10, 5, 6, 30), baseline=False, prior=[blocked]) != "recap"
    # fix round 3: …but the SAME trial (DAYBREAK) inherits the story's age -> stale;
    # with no shared subject key it may still ring
    assert A.gate(again, now_et=et(2026, 10, 5, 6, 30), baseline=False, prior=[blocked]) == "stale"
    assert A.gate(dict(again, trials=[]), now_et=et(2026, 10, 5, 6, 30), baseline=False,
                  prior=[dict(blocked, trials=[])]) is None
    # NEGATIVE: another direction is another kind
    neg = kod(push={"state": "pushed"}, type_dir="topline_negative", direction="negative")
    assert A.gate(again, now_et=et(2026, 10, 5, 6, 30), baseline=False, prior=[neg]) is None


def test_baseline_never_pushes():
    assert A.gate(kod(), now_et=MON_0730, baseline=True, prior=[]) == "baseline"


def test_unresolved_ticker_never_pushes():
    assert A.gate(kod(ticker=None), now_et=MON_0730, baseline=False, prior=[]) == "unresolved_ticker"


@pytest.mark.parametrize("kw", [
    {"event_type": "conference_data", "type_dir": "conference_data", "subtype": "upcoming"},
    {"event_type": "designation", "type_dir": "designation", "subtype": "fast_track"},
    {"phase": "2"},                                                            # Phase 2 positive
    {"direction": "unknown", "type_dir": "topline_unknown"},
    {"direction": "mixed", "type_dir": "topline_mixed"},
    {"event_type": "readout_scheduled", "type_dir": "readout_scheduled", "subtype": "scheduled"},
    {"event_type": "financing", "type_dir": "financing", "subtype": "offering"},
    {"event_type": "fda_approval", "type_dir": "fda_approval", "subtype": "tentative", "regulator": "FDA"},
    {"event_type": "fda_crl", "type_dir": "fda_crl", "subtype": "withdrawn", "regulator": "FDA"},
    {"event_type": "clinical_hold", "type_dir": "clinical_hold", "subtype": "lifted"},
    {"event_type": "fda_revoked", "type_dir": "fda_revoked", "subtype": "revoked", "regulator": "FDA"},
])
def test_low_impact_types_never_push(kw):
    assert A.gate(kod(**kw), now_et=MON_0730, baseline=False, prior=[]) == "not_high_impact"


# ── wording (exact) ─────────────────────────────────────────────────────────
def test_the_KOD_title_is_exact():
    m = A.single_text(kod())
    assert m["title"] == "🧬 KOD · Phase 3 topline positive · ophthalmology · +72% · UNMEASURED, not a buy signal"
    assert m["url"] == "/sepa/KOD?tab=catalyst" and m["data"]["url"] == "/sepa/KOD?tab=catalyst"
    assert m["kind"] == "med_catalyst" and m["tag"] == "med-kod-topline_positive"
    assert m["data"]["event_key"] == "KOD|topline_positive|2026-09-28" and m["data"]["source"] == "med_catalyst"
    assert m["body"] == ("Kodiak Sciences Inc. · DAYBREAK · vs $32.35 prior close, premarket print $55.64 "
                         "at 07:24 ET · first seen 07:25 ET via finnhub (3 sources)")


def test_a_negative_title_ends_not_a_sell_signal_and_never_says_buy():
    for kw in ({"direction": "negative", "type_dir": "topline_negative"},
               {"event_type": "fda_crl", "type_dir": "fda_crl", "subtype": "crl", "regulator": "FDA"},
               {"event_type": "clinical_hold", "type_dir": "clinical_hold", "subtype": "placed"}):
        t = A.single_text(kod(**kw))["title"]
        assert t.endswith("UNMEASURED, not a sell signal") and "buy" not in t, t


def test_no_print_yet_and_unclassified_area():
    ev = kod(areas=["unclassified"])
    ev["reaction"]["at_detection"] = {}
    t = A.single_text(ev)
    assert " · area unclassified · no print yet · " in t["title"]
    assert "no print yet" in t["body"]


def test_NEGATIVE_no_entry_stop_or_target_words_in_any_push_text():
    import re
    blob = " ".join(str(v) for v in A.single_text(kod()).values()) + " " + \
        " ".join(str(v) for v in A.digest_text([kod()] * 8).values())
    assert not re.search(r"\b(entry|stop|target|bounce)\b", blob, re.I), blob


# ── claim + send ────────────────────────────────────────────────────────────
class Sender:
    def __init__(self, res=None, raise_exc=None):
        self.calls, self.res, self.raise_exc = [], res or {"sent": 1, "failed": 0, "total_targets": 1}, raise_exc

    def __call__(self, owner, msg, kind):
        self.calls.append((owner, msg, kind))
        if self.raise_exc:
            raise self.raise_exc
        return self.res


def _push(evs, *, sender, claims=None, evc=None, now=MON_0730, prior=None, act=True, counts=None):
    claims = claims if claims is not None else FakeColl()
    evc = evc if evc is not None else FakeColl(evs)
    out = A.run_push(evs, now_et=now, prior=prior or [], claim_coll=claims, events_coll=evc,
                     owner="o@x.com", sender=sender, act=act, counts=counts if counts is not None else {})
    return out, claims, evc


def test_kod_pushes_once_and_a_second_pass_is_claimed_elsewhere():
    s = Sender()
    counts = {}
    out, claims, evc = _push([kod()], sender=s, counts=counts)
    assert len(s.calls) == 1 and s.calls[0][2] == "med_catalyst" and counts["pushed"] == 1
    # fix round 3: the topline claim is per trial (DAYBREAK) + the per-session marker
    assert set(claims.docs) == {"MC:KOD|topline|2026-09-28|DAYBREAK", "MC:KOD|topline|2026-09-28|+",
                                "MC:KOD|topline_positive|2026-09-28"}
    assert evc.docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "pushed"
    s2, c2 = Sender(), {}
    _push([kod()], sender=s2, claims=claims, counts=c2)
    assert s2.calls == [] and c2["claimed_elsewhere"] == 1


def test_one_topline_push_per_name_per_session_negative_after_positive_is_claimed_elsewhere():
    s = Sender()
    _o, claims, _e = _push([kod()], sender=s)
    neg = kod(_id="KOD|topline_negative|2026-09-28", direction="negative", type_dir="topline_negative")
    s2, c2 = Sender(), {}
    _push([neg], sender=s2, claims=claims, counts=c2)
    assert s2.calls == [] and c2["claimed_elsewhere"] == 1
    assert "MC:KOD|topline_negative|2026-09-28" not in claims.docs


def test_closed_day_writes_no_claim_sends_nothing_stays_pending_then_rings_next_trading_day(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    ev = kod(_id="KOD|topline_positive|2026-09-08", session_date="2026-09-08",
             published_at=datetime(2026, 9, 7, 10, 34, tzinfo=timezone.utc))
    s, counts = Sender(), {}
    _o, claims, evc = _push([ev], sender=s, now=LABOR_DAY, counts=counts)
    assert s.calls == [] and claims.docs == {} and counts["closed_day"] == 1
    assert evc.docs[ev["_id"]]["push"]["state"] == "pending"
    s2 = Sender()
    _push([evc.docs[ev["_id"]]], sender=s2, claims=claims, evc=evc, now=et(2026, 9, 8, 6, 0))
    assert len(s2.calls) == 1 and evc.docs[ev["_id"]]["push"]["state"] == "pushed"


def test_transport_failure_releases_the_claims_and_stays_pending():
    s = Sender(raise_exc=RuntimeError("boom token=SECRET"))
    _o, claims, evc = _push([kod()], sender=s)
    assert claims.docs == {}
    assert evc.docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "pending"


def test_nobody_targeted_is_muted_and_the_claim_is_KEPT():
    s = Sender(res={"sent": 0, "failed": 0, "total_targets": 0})
    counts = {}
    _o, claims, evc = _push([kod()], sender=s, counts=counts)
    assert counts["muted"] == 1 and "MC:KOD|topline_positive|2026-09-28" in claims.docs
    assert evc.docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "muted"


def test_more_than_three_ring_three_singles_then_one_digest():
    evs = []
    for i, sym in enumerate(("AAAA", "BBBB", "CCCC", "DDDD", "EEEE")):
        evs.append(kod(_id=f"{sym}|topline_positive|2026-09-28", ticker=sym,
                       reaction={"at_detection": {"move_pct": 10.0 + i, "price": 10.0},
                                 "liquidity": {"base_close": 9.0, "adv50_usd": 9e6}}))
    s = Sender()
    out, _c, evc = _push(evs, sender=s)
    assert len(s.calls) == 4
    digest = s.calls[-1][1]
    assert digest["title"] == "🧬 2 more medical catalysts"
    assert digest["url"] == "/chart-maps?tab=catalysts&sub=medical" and digest["tickers"] == ["BBBB", "AAAA"]
    assert [c[1]["ticker"] for c in s.calls[:3]] == ["EEEE", "DDDD", "CCCC"]
    assert all(d["push"]["state"] == "pushed" for d in evc.docs.values())


def test_digest_caps_at_six_lines_plus_the_board_line():
    evs = [kod(ticker=f"T{i:03d}") for i in range(9)]
    d = A.digest_text(evs)
    lines = d["body"].split("\n")
    assert len(lines) == 7 and lines[-1] == "+3 more on Chart Maps ▸ Catalysts ▸ 🧬 Medical"


def test_baseline_pass_pushes_nothing_and_stamps_baseline():
    s, counts = Sender(), {}
    _o, claims, evc = _push([kod(baseline=True)], sender=s, counts=counts)
    assert s.calls == [] and claims.docs == {} and counts["baseline"] == 1
    assert evc.docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "baseline"


def test_dry_run_writes_nothing_and_sends_nothing_but_explains():
    s = Sender()
    out, claims, evc = _push([kod()], sender=s, act=False)
    assert s.calls == [] and claims.docs == {}
    assert evc.docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "pending"
    assert out["messages"][0]["title"].startswith("🧬 KOD · Phase 3 topline positive")
    ex = A.explain(kod(), now_et=et(2026, 9, 28, 13, 0), prior=[])
    assert ex["reason"] == "stale" and ex["title"].startswith("🧬 KOD ·")


def test_gate_text_and_constants():
    assert A.RTH_EXPOSURE_MAX_MIN == 10 and A.RECAP_SESSIONS == 21 and A.MAX_SINGLES == 3
    t = A.gate_text()
    assert "$2" in t and "$5M" in t and "10 minutes" in t and "21 sessions" in t


# ── registries ──────────────────────────────────────────────────────────────
def test_the_kind_is_registered_everywhere_the_house_pattern_needs():
    from push import subs, recent
    from market_hours import gate
    assert subs.default_prefs()["med_catalyst"] is False, "everyone else starts off"
    assert "med_catalyst" in subs.OWNER_KEEP_SET
    assert subs.owner_prefs()["med_catalyst"] is True, "ON for his phone (HIS CALL #1)"
    assert "med_catalyst" in gate.MARKET_ALERT_KINDS and "med_catalyst" not in gate.PERSONAL_KINDS
    assert "med_catalyst" in recent.DIGEST_KINDS


def test_closed_day_drop_at_the_sender_too(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    from market_hours import gate
    assert gate.should_drop_kind("med_catalyst", datetime(2026, 9, 7, 10, 0, tzinfo=ET)) == "holiday 2026-09-07"


def test_hooks_wrapper_sends_to_the_owner_under_its_own_kind(monkeypatch):
    from push import hooks, sender
    seen = []
    monkeypatch.setattr(sender, "send_to_user", lambda who, payload, kind=None: seen.append((who, kind)) or
                        {"sent": 1, "failed": 0, "total_targets": 1})
    assert hooks.notify_med_catalyst(owner="o@x.com", payload={"title": "t"})["sent"] == 1
    assert seen == [("o@x.com", "med_catalyst")]
