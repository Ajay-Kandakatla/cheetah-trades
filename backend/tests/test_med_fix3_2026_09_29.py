"""🧬 medical catalysts — fix round 3 (2026-09-29): SHADOW mode + the six OOS
defects + the materiality switch.

WHY: an independent out-of-sample grade on REAL Finnhub news 2026-06-01..08-15
(80 random healthcare names) gave STRICT push precision 0.56 [0.34, 0.75],
verdict SHIP-SHADOW. Every failing headline of that grade is a row below:

  (1) PTGX "Protagonist Therapeutics: 'Strong Buy' ICOTYDE FDA Approval …" — a
      SeekingAlpha opinion piece passed the commentary filter;
  (2) PEN "Penumbra (PEN) Wins FDA Clearance For THUNDERBOLT …" 31 sessions after
      the real clearance — the repeat block was 21 sessions and the stale gate
      measured the ARTICLE, not the EVENT;
  (3) LH "Labcorp Announces Availability of Roche's Ventana … Approved By FDA" —
      the rival guard fired only when the issuer was named after the cue;
  (4) MDT "Edwards wins FDA clearance …, setting up competition with AtriCure and
      Medtronic" credited to MDT;
  (5) the repeat block keyed ticker + kind -> GILD's islatravir and LLY's
      Jaypirca Phase 3 positives were swallowed by unrelated earlier toplines;
  (6) "Meets Week 48 Endpoints" / "Meets Dual Primary Endpoints" undirected, and
      an undirected topline merged into ANY topline (another trial).
Materiality (510(k), dosing / label updates, generic-type formulations,
biosimilars) is HIS CALL: one switch, default = today's behaviour.

NEGATIVES everywhere. Purge the bytecode caches before running.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import alerts as A        # noqa: E402
from catalysts.medical import classify as C      # noqa: E402
from catalysts.medical import routine as RT      # noqa: E402
from catalysts.medical import store as S         # noqa: E402
from catalysts.medical import taxonomy as T      # noqa: E402
from tests.test_med_alerts import Sender, kod    # noqa: E402
from tests.test_med_store import FakeColl        # noqa: E402

ET = ZoneInfo("America/New_York")
MON_0730 = datetime(2026, 9, 28, 7, 30, tzinfo=ET)

NAMES = {"PTGX": "Protagonist Therapeutics, Inc.", "LLY": "Eli Lilly and Company", "ALKS": "Alkermes plc",
         "PEN": "Penumbra, Inc.", "LH": "Labcorp Holdings Inc.", "MDT": "Medtronic plc",
         "GILD": "Gilead Sciences, Inc.", "AMRX": "Amneal Pharmaceuticals, Inc.", "OGN": "Organon & Co.",
         "UTHR": "United Therapeutics Corporation", "MRNA": "Moderna, Inc.", "EW": "Edwards Lifesciences Corporation",
         "BSX": "Boston Scientific Corporation", "FULC": "Fulcrum Therapeutics, Inc.", "BHVN": "Biohaven Ltd",
         "BTAI": "BioXcel Therapeutics, Inc.", "XYZ": "XYZ Bio Inc.", "ADCT": "ADC Therapeutics SA"}


def cls(title: str, ticker: str, context: str = "") -> dict:
    return C.classify(title, context=context, ticker=ticker, forms=C.name_forms(ticker, NAMES.get(ticker)),
                      issuer_medical=True)


def one(r: dict, typ: str) -> dict:
    evs = [e for e in r["events"] if e["event_type"] == typ]
    assert len(evs) == 1, (typ, r["events"])
    return evs[0]


def would_push(r: dict) -> bool:
    return (not r["commentary"] and r["attributed"] is not False and not r["merge_only"]
            and any(T.is_high_impact(e) for e in r["events"]))


def et(*a):
    return datetime(*a, tzinfo=ET)


# ════════════════════════════════════════════════════════════════════════════
# (A) SHADOW MODE
# ════════════════════════════════════════════════════════════════════════════
def _push(evs, *, sender, claims=None, evc=None, now=MON_0730, prior=None, act=True, counts=None, shadow=None):
    claims = claims if claims is not None else FakeColl()
    evc = evc if evc is not None else FakeColl(evs)
    counts = counts if counts is not None else {}
    out = A.run_push(evs, now_et=now, prior=prior or [], claim_coll=claims, events_coll=evc, owner="o@x.com",
                     sender=sender, act=act, counts=counts, shadow=shadow)
    return out, claims, evc, counts


def test_the_switch_ships_in_SHADOW():
    assert A.SHADOW is True, "verdict SHIP-SHADOW: nothing is sent until Ajay flips it"
    assert "SHADOW MODE" in A.gate_text()


def test_shadow_never_calls_the_sender_and_records_would_push():
    s = Sender()
    out, claims, evc, counts = _push([kod()], sender=s)                  # shadow = the module default
    assert s.calls == [], "NEGATIVE: shadow NEVER sends"
    ev = evc.docs["KOD|topline_positive|2026-09-28"]
    assert ev["push"]["state"] == "shadow" and ev["push"]["reason"] == "would_push"
    wp = ev["would_push"]
    assert wp["value"] is True and wp["mode"] == "shadow" and wp["title"].startswith("🧬 KOD · Phase 3 topline positive")
    assert counts["shadow"] == 1 and counts["shadow_mode"] == 1 and counts["pushed"] == 0
    assert claims.docs and all(k.startswith(A.SHADOW_CLAIM_PREFIX) for k in claims.docs), \
        "NEGATIVE: shadow never burns a LIVE claim key"
    assert out["shadow"] is True and out["messages"][0]["shadow"] is True


def test_shadow_still_applies_the_gate_and_records_the_reason():
    s = Sender()
    cheap = kod(reaction={"at_detection": {"move_pct": 5.0, "price": 1.0},
                          "liquidity": {"base_close": 0.56, "adv50_usd": 9e6}})
    _o, claims, evc, counts = _push([cheap], sender=s)
    ev = evc.docs[cheap["_id"]]
    assert s.calls == [] and claims.docs == {}
    assert ev["push"]["state"] == "blocked:price"
    assert ev["would_push"] == {"value": False, "reason": "blocked_price", "at": ev["would_push"]["at"],
                                "mode": "shadow"}
    assert counts["shadow"] == 0 and counts["blocked_price"] == 1
    # stale and low-impact are shadow-blocked too
    _o, _c, evc2, c2 = _push([kod()], sender=s, now=et(2026, 9, 28, 13, 0))
    assert evc2.docs["KOD|topline_positive|2026-09-28"]["would_push"]["reason"] == "stale" and c2["shadow"] == 0
    low = kod(direction="unknown", type_dir="topline_unknown", _id="KOD|topline_unknown|2026-09-28")
    _o, _c, evc3, c3 = _push([low], sender=s)
    assert evc3.docs[low["_id"]]["would_push"]["value"] is False and c3["not_high_impact"] == 1


def test_shadow_is_once_per_event_too():
    s = Sender()
    _o, claims, _e, _c = _push([kod()], sender=s)
    _o, _cl, _e2, c2 = _push([kod()], sender=s, claims=claims)
    assert c2["claimed_elsewhere"] == 1 and c2["shadow"] == 0 and s.calls == []


def test_a_shadow_ring_counts_as_rung_for_the_repeat_block():
    first = kod(push={"state": "shadow"})
    again = kod(_id="KOD|topline_positive|2026-10-05", session_date="2026-10-05",
                published_at=datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc))
    assert A.gate(again, now_et=et(2026, 10, 5, 6, 30), baseline=False, prior=[first]) == "recap"


def test_flipping_the_switch_sends_exactly_once_per_event(monkeypatch):
    monkeypatch.setattr(A, "SHADOW", False)
    s = Sender()
    _o, claims, evc, counts = _push([kod()], sender=s)
    assert len(s.calls) == 1 and counts["pushed"] == 1 and counts["shadow"] == 0 and counts["shadow_mode"] == 0
    assert evc.docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "pushed"
    assert not [k for k in claims.docs if k.startswith(A.SHADOW_CLAIM_PREFIX)]
    _push([kod()], sender=s, claims=claims)
    assert len(s.calls) == 1, "NEGATIVE: the second pass never re-sends"


def test_live_mode_still_applies_the_gate(monkeypatch):
    monkeypatch.setattr(A, "SHADOW", False)
    s = Sender()
    cheap = kod(reaction={"at_detection": {"move_pct": 5.0}, "liquidity": {"base_close": 0.56, "adv50_usd": 9e6}})
    _push([cheap], sender=s)
    _push([kod()], sender=s, now=et(2026, 9, 28, 13, 0))
    assert s.calls == []


def test_the_shadow_claims_never_block_a_live_send_after_the_flip(monkeypatch):
    s = Sender()
    _o, claims, _e, _c = _push([kod()], sender=s)                        # shadow
    monkeypatch.setattr(A, "SHADOW", False)
    _push([kod()], sender=s, claims=claims)                              # a fresh pending doc, live
    assert len(s.calls) == 1


def test_dry_run_in_shadow_writes_nothing():
    s = Sender()
    _o, claims, evc, _c = _push([kod()], sender=s, act=False)
    assert s.calls == [] and claims.docs == {}
    assert evc.docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "pending"
    assert "would_push" not in evc.docs["KOD|topline_positive|2026-09-28"]


def test_the_routine_in_shadow_rings_nothing_stamps_shadow_and_counts_it_on_the_alerts_page():
    from tests.test_med_routine import fetchers, seeded, tick, NOW
    now = NOW.replace(hour=9, minute=0)
    c = seeded(now=now)
    fx, _calls = fetchers(now=now)
    out = tick(c, fx, now=now)
    assert out["ran"] is True, out
    assert fx["sender"].calls == [], "NEGATIVE: the shadow routine never sends"
    ev = c[S.EVENTS].docs["KOD|topline_positive|2026-09-28"]
    assert ev["push"]["state"] == "shadow" and ev["would_push"]["value"] is True
    pc = c["alert_pass_latest"].docs["med_catalyst"]["counts"]
    assert pc["shadow"] >= 1 and pc["shadow_mode"] == 1 and pc["pushed"] == 0
    # the event already recorded in shadow never rings late once the switch flips
    import catalysts.medical.alerts as AA
    old = AA.SHADOW
    AA.SHADOW = False
    try:
        fx2, _ = fetchers(now=now, sender=Sender())
        tick(c, fx2, now=now + timedelta(minutes=5))
        assert fx2["sender"].calls == []
    finally:
        AA.SHADOW = old


def test_the_board_row_carries_would_push():
    from catalysts.medical import board as B
    r = B.row(kod(would_push={"value": True, "reason": "gate_passed", "mode": "shadow", "at": MON_0730}))
    assert r["would_push"] == {"value": True, "reason": "gate_passed", "mode": "shadow"}
    assert B.row(kod())["would_push"] is None


def test_the_rules_line_says_shadow_and_reads_its_constants(monkeypatch):
    from supply_demand import rules_info as RI
    line = [l for l in RI.sections()["alerts"]["alerts"] if "med_catalyst" in l][0]
    assert "SHADOW MODE" in line and "per trial" in line and "at any earlier date" in line
    monkeypatch.setattr(A, "SHADOW", False)
    monkeypatch.setattr(A, "REHASH_SESSIONS", 40)
    line = [l for l in RI.sections()["alerts"]["alerts"] if "med_catalyst" in l][0]
    assert "SHADOW MODE" not in line and "LIVE" in line and "within 40 sessions" in line


# ════════════════════════════════════════════════════════════════════════════
# (1) commentary FORM
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tk,title", [
    ("PTGX", "Protagonist Therapeutics: 'Strong Buy' ICOTYDE FDA Approval And PN-881 Advancement"),
    ("LLY", "Eli Lilly: 'Strong Buy' On Retatrutide Obesity Drug And EBGLYSS Maintenance Label Expansion"),
    ("ALKS", "Alkermes: 'Buy' On Avadel Acquisition And Positive NT2 Data With Alixorexton"),
    ("FULC", "Fulcrum: 'Hold' On Pociredir Discontinuation And Strategic Alternatives Shift"),
    ("BHVN", "Biohaven: Upgrading To Buy On Protein Degraders Pivotal Study Initiations"),
    ("LLY", "Eli Lilly: Buy After Phase 3 Retatrutide Met Primary Endpoint"),
    ("LLY", "Strong Sell On Lilly After FDA Approval"),
])
def test_opinion_form_is_commentary_and_never_pushes(tk, title):
    r = cls(title, tk)
    assert r["commentary"] is True and r["events"] == [] and not would_push(r)


@pytest.mark.parametrize("tk,title,typ", [
    ("BTAI", "BioXcel: Hold Lifted On Phase 3 Trial", "clinical_hold"),                 # "Hold" is not a rating here
    ("LLY", "Reported Earlier: Eli Lilly's Mounjaro Receives FDA Approval To Treat Children", "fda_approval"),
    ("PTGX", "Protagonist Therapeutics Receives FDA Approval For ICOTYDE", "fda_approval"),
])
def test_NEGATIVE_a_name_prefix_or_hold_without_a_rating_stays_news(tk, title, typ):
    r = cls(title, tk)
    assert r["commentary"] is False and typ in [e["event_type"] for e in r["events"]]


# ════════════════════════════════════════════════════════════════════════════
# (3)(4) rival attribution
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tk,title", [
    ("LH", "Labcorp Announces Availability of Roche's Ventana Pten RxDx Assay, First Immunohistochemistry "
           "Companion Diagnostic Test Approved By FDA To Determine Pten Protein Loss In Prostate Adenocarcinoma Patients"),
    ("LH", "Labcorp Announces FDA Approval of Roche's Companion Diagnostic"),
    ("LH", "FDA Approves Roche's Test; Labcorp To Offer It Nationwide"),
    ("MDT", "Edwards wins FDA clearance for LAA clip, setting up competition with AtriCure and Medtronic"),
    ("BSX", "Penumbra’s FDA nod for clot removal tech a win for Boston Scientific"),
    ("LLY", "Amgen's MariTide Met Primary Endpoint in Phase 3 Trial, Outperforming Lilly's Zepbound"),
])
def test_another_companys_event_is_not_the_issuers(tk, title):
    r = cls(title, tk)
    assert r["attributed"] is False and not would_push(r)


@pytest.mark.parametrize("tk,title", [
    ("LH", "Labcorp Announces FDA Approval of Companion Diagnostic Supporting Patients with Advanced Melanoma"),
    ("EW", "Edwards wins FDA clearance for LAA clip, setting up competition with AtriCure and Medtronic"),
    ("LLY", "FDA approves Lilly's EBGLYSS® (lebrikizumab-lbkz) for one maintenance dose every eight weeks"),
    ("LLY", "FDA Grants Approval For Eli Lilly's Selpercatinib For Patients With A RET Gene Fusion"),
    ("LLY", "After Novo's Setback, Lilly Receives FDA Approval for Orforglipron Tablets"),
    ("LLY", "Weight-Loss Drug Wins FDA Nod for Lilly"),
    ("PEN", "Penumbra's THUNDERBOLT Gets FDA Clearance To Treat Acute Ischemic Stroke"),
    ("GILD", "Merck And Gilead Discontinue Phase 3 KEYNOTE-D46/EVOKE-03 Trial After Trodelvy–KEYTRUDA "
             "Combination Fails To Achieve Statistically Significant Progression-Free Survival Benefit"),
])
def test_NEGATIVE_the_issuers_own_event_stays_attributed(tk, title):
    assert cls(title, tk)["attributed"] is True


# ════════════════════════════════════════════════════════════════════════════
# (6) direction of "meets … endpoints"
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("title", [
    "Gilead And Merck Report Phase 3 Results For Once-Weekly Oral HIV Regimen Islatravir/Lenacapavir; "
    "Meets Week 48 Endpoints In ISLEND-1 And ISLEND-2 Trials",
    "XYZ Bio Meets Dual Primary Endpoints In Phase 3 ALPHA Trial",
    "XYZ Bio Phase 3 ALPHA Trial Met All Primary And Secondary Endpoints",
])
def test_meets_endpoints_variants_are_positive_phase_3(title):
    e = one(cls(title, "GILD" if "Gilead" in title else "XYZ"), "topline")
    assert e["direction"] == "positive" and e["phase"] == "3" and T.is_high_impact(e)


@pytest.mark.parametrize("title,d", [
    ("XYZ Bio Did Not Meet Week 48 Endpoints In Phase 3 ALPHA Trial", "negative"),
    ("XYZ Bio Phase 3 ALPHA Trial Failed To Meet Dual Primary Endpoints", "negative"),
    ("XYZ Bio Phase 3 ALPHA Trial Met Primary Endpoint But Missed Key Secondary Endpoints", "mixed"),
])
def test_NEGATIVE_a_negated_meets_endpoints_is_never_positive(title, d):
    assert one(cls(title, "XYZ"), "topline")["direction"] == d


def test_NEGATIVE_meeting_an_enrollment_goal_or_the_FDA_is_no_positive_readout():
    assert "topline" not in [e["event_type"] for e in cls("XYZ Bio Meets Enrollment Goal In Phase 3 Trial", "XYZ")["events"]]
    for t in ("XYZ Bio Met With FDA On Phase 3 ALPHA Trial Endpoints",
              "XYZ Bio Meets With Regulators To Discuss Phase 3 Endpoints"):
        assert not [e for e in cls(t, "XYZ")["events"] if e["event_type"] == "topline" and e["direction"] == "positive"], t


# ════════════════════════════════════════════════════════════════════════════
# subject keys
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tk,title,want", [
    ("GILD", "Gilead And Merck Report Phase 3 Results For Once-Weekly Oral HIV Regimen Islatravir/Lenacapavir; "
             "Meets Week 48 Endpoints In ISLEND-1 And ISLEND-2 Trials",
     {"ISLEND-1", "ISLEND-2", "ISLATRAVIR", "LENACAPAVIR"}),
    ("GILD", "Merck And Gilead Discontinue Phase 3 KEYNOTE-D46/EVOKE-03 Trial After Combination Fails",
     {"KEYNOTE-D46", "EVOKE-03"}),
    ("GILD", "Gilead’s Livdelzi® (Seladelpar) Delivers Statistically Significant Composite ALP "
             "Normalization in Phase 3 IDEAL Trial", {"LIVDELZI", "SELADELPAR", "IDEAL"}),
    ("LLY", "Eli Lilly announces Phase 3 Libretto-432 trial of Retevmo met primary endpoint", {"LIBRETTO-432", "RETEVMO"}),
    ("LLY", "Eli Lilly (LLY) Announces Positive Phase 3 Results for Jaypirca Combination in Relapsed CLL/SLL", {"JAYPIRCA"}),
    ("PEN", "Penumbra (PEN) Wins FDA Clearance For THUNDERBOLT After Strong Stroke Study", {"THUNDERBOLT"}),
    ("PEN", "Penumbra's THUNDERBOLT Gets FDA Clearance To Treat Acute Ischemic Stroke", {"THUNDERBOLT"}),
    ("PTGX", "Protagonist Receives FDA Approval For ICOTYDE; PN-881 Advances", {"ICOTYDE", "PN-881"}),
    ("XYZ", "XYZ Bio Starts Phase 2 Study NCT06556368", {"NCT06556368"}),
])
def test_subject_keys(tk, title, want):
    got = set(C.extract_subjects(title, ticker=tk, forms=C.name_forms(tk, NAMES.get(tk))))
    assert want <= got, (want - got, got)


@pytest.mark.parametrize("title,never", [
    ("Gilead, Merck Report Positive Phase III HIV Study Data, End NSCLC Study", {"III", "HIV", "NSCLC", "PHASE"}),
    ("Lilly's olomorasib receives Breakthrough Therapy designation in KRAS G12C-mutant pancreatic cancer",
     {"G12C", "KRAS"}),
    ("Pfizer Receives FDA Approval for Drugzumab in FY2026 Q3 2026", {"FY2026", "2026", "Q3"}),
    ("Labcorp Announces FDA Approval of Roche's Companion Diagnostic", {"ROCHE", "COMPANION"}),
    ("PENUMBRA RECEIVES FDA CLEARANCE FOR NEW DEVICE", {"PENUMBRA", "RECEIVES", "DEVICE"}),
    ("Moderna Receives U.S. FDA Approval for Influenza Vaccine", {"INFLUENZA", "VACCINE", "MODERNA"}),
])
def test_NEGATIVE_disease_biomarker_year_company_and_shouting_words_are_never_keys(title, never):
    tk = "LLY" if "Lilly" in title else "PEN" if "PENUMBRA" in title else "MRNA" if "Moderna" in title else "XYZ"
    got = set(C.extract_subjects(title, ticker=tk, forms=C.name_forms(tk, NAMES.get(tk))))
    assert not (got & never), got & never


def test_every_event_carries_its_subjects_and_the_routine_stores_them():
    r = cls("Eli Lilly announces Phase 3 Libretto-432 trial of Retevmo met primary endpoint", "LLY")
    e = one(r, "topline")
    assert {"LIBRETTO-432", "RETEVMO"} <= set(e["subjects"])
    art = {"key": "fh:1", "title": "t", "published": datetime(2026, 6, 1, 12, tzinfo=timezone.utc).timestamp(),
           "provider": "finnhub"}
    doc = RT._ev_doc(e, art, r, ticker="LLY", company="Eli Lilly", now_utc=datetime(2026, 6, 1, 12, 5, tzinfo=timezone.utc),
                     baseline=False)
    assert {"LIBRETTO-432", "RETEVMO"} <= set(doc["subjects"]) and doc["materiality"] is None


# ════════════════════════════════════════════════════════════════════════════
# (5)(6) merge + repeat keys include the trial / drug
# ════════════════════════════════════════════════════════════════════════════
def _tl(tk="GILD", td="topline_positive", sd="2026-06-08", subjects=(), trials=(), state="pending", **kw):
    d = {"_id": S.event_key(tk, td, sd), "ticker": tk, "type_dir": td, "event_type": td.split("_")[0]
         if td.startswith("topline") else td, "direction": td.split("_")[1] if td.startswith("topline") else None,
         "phase": "3", "session_date": sd, "subjects": list(subjects), "trials": list(trials),
         "modality": ["unclassified"], "areas": ["unclassified"], "sources": [], "impact": "high",
         "subtype": "novel" if td == "fda_approval" else None, "regulator": "FDA" if td == "fda_approval" else None,
         "published_at": datetime.fromisoformat(sd).replace(hour=12, tzinfo=timezone.utc),
         "last_seen_at": datetime.fromisoformat(sd).replace(hour=12, tzinfo=timezone.utc),
         "push": {"state": state, "reason": None, "at": None}, "baseline": False,
         "reaction": {"at_detection": {"move_pct": 4.0}, "liquidity": {"base_close": 100.0, "adv50_usd": 1e9}}}
    d.update(kw)
    return d


WIN = dict(lo_date=date(2026, 6, 3), hi_date=date(2026, 6, 11))


def test_an_undirected_topline_of_another_trial_never_merges():
    evoke = _tl(td="topline_negative", subjects=["EVOKE-03", "KEYNOTE-D46"])
    islend = _tl(td="topline_unknown", subjects=["ISLEND-1", "ISLEND-2"])
    assert S.find_merge_target(FakeColl([evoke]), islend, **WIN) is None
    # a directed one never merges into another trial's unknown either
    unk = _tl(td="topline_unknown", subjects=["EVOKE-03"])
    pos = _tl(td="topline_positive", subjects=["ISLEND-1"])
    assert S.find_merge_target(FakeColl([unk]), pos, **WIN) is None
    # nor the same type_dir of another trial
    other = _tl(td="topline_positive", subjects=["IDEAL"], sd="2026-06-05")
    assert S.find_merge_target(FakeColl([other]), pos, **WIN) is None


def test_NEGATIVE_the_same_trial_or_an_unkeyed_report_still_merges():
    first = _tl(td="topline_positive", subjects=["ISLEND-1", "ISLEND-2", "ISLATRAVIR"])
    later = _tl(td="topline_positive", sd="2026-06-09", subjects=["ISLATRAVIR", "LENACAPAVIR"])
    assert S.find_merge_target(FakeColl([first]), later, **WIN)["_id"] == first["_id"]
    bare = _tl(td="topline_positive", sd="2026-06-09")
    assert S.find_merge_target(FakeColl([first]), bare, **WIN)["_id"] == first["_id"]
    unk = _tl(td="topline_unknown", sd="2026-06-09")
    assert S.find_merge_target(FakeColl([first]), unk, **WIN)["_id"] == first["_id"]


def test_NEGATIVE_an_approval_named_by_brand_and_by_INN_still_merges():
    """"FDA Grants Approval For Eli Lilly's Selpercatinib …" + "… Wins Full FDA
    Approval For Retevmo …" is ONE approval — disjoint names split only trials."""
    inn = _tl("LLY", "fda_approval", "2026-07-14", subjects=["SELPERCATINIB"])
    brand = _tl("LLY", "fda_approval", "2026-07-15", subjects=["RETEVMO"])
    assert S.find_merge_target(FakeColl([inn]), brand, lo_date=date(2026, 7, 9), hi_date=date(2026, 7, 20))["_id"] == inn["_id"]


def test_merge_unions_subjects():
    c = FakeColl([_tl(subjects=["ISLEND-1"])])
    tgt = c.find_one({})
    S.merge_into(c, tgt, _tl(sd="2026-06-09", subjects=["ISLATRAVIR"]))
    assert set(c.find_one({})["subjects"]) == {"ISLEND-1", "ISLATRAVIR"}


def test_GILD_islatravir_and_LLY_jaypirca_positives_are_not_a_repeat_of_another_trial():
    livdelzi = _tl(td="topline_positive", sd="2026-06-02", subjects=["IDEAL", "LIVDELZI", "SELADELPAR"], state="pushed")
    islend = _tl(td="topline_positive", sd="2026-06-08", subjects=["ISLEND-1", "ISLATRAVIR"])
    now = et(2026, 6, 8, 8, 5)
    assert A.gate(islend, now_et=now, baseline=False, prior=[livdelzi]) is None
    retevmo = _tl("LLY", "topline_positive", "2026-06-01", subjects=["LIBRETTO-432", "RETEVMO"], state="pushed")
    jaypirca = _tl("LLY", "topline_positive", "2026-06-29", subjects=["JAYPIRCA"])
    assert A.gate(jaypirca, now_et=et(2026, 6, 29, 8, 5), baseline=False, prior=[retevmo]) is None


def test_NEGATIVE_the_repeat_block_still_holds_for_the_same_trial_an_unkeyed_one_and_approvals():
    livdelzi = _tl(td="topline_positive", sd="2026-06-02", subjects=["IDEAL", "LIVDELZI"], state="pushed")
    rehash = _tl(td="topline_positive", sd="2026-06-15", subjects=["IDEAL"])
    now = et(2026, 6, 15, 8, 5)
    assert A.gate(rehash, now_et=now, baseline=False, prior=[livdelzi]) == "recap"
    assert A.gate(_tl(td="topline_positive", sd="2026-06-15"), now_et=now, baseline=False, prior=[livdelzi]) == "recap"
    # two approvals with different names within 21 sessions: still the old ticker + kind block
    a1 = _tl("LLY", "fda_approval", "2026-07-14", subjects=["SELPERCATINIB"], state="pushed")
    a2 = _tl("LLY", "fda_approval", "2026-07-20", subjects=["RETEVMO"])
    assert A.gate(a2, now_et=et(2026, 7, 20, 8, 5), baseline=False, prior=[a1]) == "recap"


# ════════════════════════════════════════════════════════════════════════════
# (2) rehash beyond 21 sessions + stale by EVENT first sighting
# ════════════════════════════════════════════════════════════════════════════
def test_PEN_thunderbolt_rehash_31_sessions_later_never_rings():
    first = _tl("PEN", "fda_approval", "2026-06-11", subjects=["THUNDERBOLT"], state="pushed",
                subtype="device_clearance")
    again = _tl("PEN", "fda_approval", "2026-07-27", subjects=["THUNDERBOLT"], subtype="device_clearance",
                published_at=datetime(2026, 7, 25, 14, 0, tzinfo=timezone.utc))      # a SATURDAY article
    now = et(2026, 7, 27, 4, 5)                                                     # Monday pre-market
    assert A.R.rth_minutes_between(again["published_at"], now) == 0, "the ARTICLE is 0 trading minutes old"
    assert A.gate(again, now_et=now, baseline=False, prior=[first]) == "recap"
    # the first one never rang (blocked): the rehash is as old as its story -> stale
    blocked = dict(first, push={"state": "blocked:price"})
    assert A.gate(again, now_et=now, baseline=False, prior=[blocked]) == "stale"
    assert A.event_origin(again, [blocked]) == first["published_at"]


def test_NEGATIVE_a_different_device_on_the_same_name_later_still_rings():
    first = _tl("PEN", "fda_approval", "2026-06-11", subjects=["THUNDERBOLT"], state="pushed")
    other = _tl("PEN", "fda_approval", "2026-07-27", subjects=["LIGHTNING"],
                published_at=datetime(2026, 7, 27, 11, 0, tzinfo=timezone.utc))
    assert A.gate(other, now_et=et(2026, 7, 27, 7, 5), baseline=False, prior=[first]) is None
    assert A.event_origin(other, [first]) == other["published_at"]


def test_the_rehash_window_is_a_named_switch(monkeypatch):
    first = _tl("PEN", "fda_approval", "2026-06-11", subjects=["THUNDERBOLT"], state="pushed")
    again = _tl("PEN", "fda_approval", "2026-07-27", subjects=["THUNDERBOLT"],
                published_at=datetime(2026, 7, 27, 11, 0, tzinfo=timezone.utc))
    assert A.REHASH_SESSIONS is None
    monkeypatch.setattr(A, "REHASH_SESSIONS", 25)
    assert A._repeat(again, [first]) is False                       # 31 sessions back > 25
    monkeypatch.setattr(A, "REHASH_SESSIONS", 40)
    assert A._repeat(again, [first]) is True


def test_ADCT_lift_a_session_late_stays_stale():
    ev = _tl("ADCT", "topline_positive", "2026-06-03", subjects=["LOTIS-5"],
             published_at=datetime(2026, 6, 3, 11, 0, tzinfo=timezone.utc))   # 07:00 ET the first report
    assert A.gate(ev, now_et=et(2026, 6, 4, 10, 30), baseline=False, prior=[]) == "stale"


# ════════════════════════════════════════════════════════════════════════════
# topline claim: one per name per session PER TRIAL
# ════════════════════════════════════════════════════════════════════════════
def test_two_trials_same_session_both_ring_the_same_trial_once(monkeypatch):
    monkeypatch.setattr(A, "SHADOW", False)
    now = et(2026, 6, 8, 12, 45)
    evoke = _tl(td="topline_negative", subjects=["EVOKE-03"], published_at=datetime(2026, 6, 8, 16, 40, tzinfo=timezone.utc))
    islend = _tl(td="topline_positive", subjects=["ISLEND-1"], published_at=datetime(2026, 6, 8, 16, 40, tzinfo=timezone.utc))
    s, claims = Sender(), FakeColl()
    _push([evoke], sender=s, claims=claims, now=now)
    _push([islend], sender=s, claims=claims, now=now)
    assert len(s.calls) == 2
    # NEGATIVE: the same trial's opposite read the same session is claimed elsewhere
    same = _tl(td="topline_negative", subjects=["ISLEND-1"], published_at=islend["published_at"],
               _id="GILD|topline_negative|2026-06-08|b")
    _o, _c, _e, c3 = _push([same], sender=s, claims=claims, now=now)
    assert len(s.calls) == 2 and c3["claimed_elsewhere"] == 1


def test_NEGATIVE_an_unkeyed_topline_yields_to_a_keyed_one_and_vice_versa(monkeypatch):
    monkeypatch.setattr(A, "SHADOW", False)
    now = et(2026, 6, 8, 12, 45)
    pub = datetime(2026, 6, 8, 16, 40, tzinfo=timezone.utc)
    s, claims = Sender(), FakeColl()
    _push([_tl(td="topline_positive", subjects=["ISLEND-1"], published_at=pub)], sender=s, claims=claims, now=now)
    _o, _c, _e, c2 = _push([_tl(td="topline_negative", published_at=pub)], sender=s, claims=claims, now=now)
    assert len(s.calls) == 1 and c2["claimed_elsewhere"] == 1
    s2, claims2 = Sender(), FakeColl()
    _push([_tl(td="topline_negative", published_at=pub)], sender=s2, claims=claims2, now=now)
    _o, _c, _e, c4 = _push([_tl(td="topline_positive", subjects=["ISLEND-1"], published_at=pub)], sender=s2,
                           claims=claims2, now=now)
    assert len(s2.calls) == 1 and c4["claimed_elsewhere"] == 1


# ════════════════════════════════════════════════════════════════════════════
# (C) MATERIALITY — HIS CALL, default = today's behaviour
# ════════════════════════════════════════════════════════════════════════════
MAT_ROWS = [
    ("MDT", "Medtronic Receives FDA Clearance for Nellcor(TM) Pulse Oximetry System With Nell-EQ(TM) Intelligent "
            "Processor, a New Technology Designed To Improve Reliability", "", "device_clearance"),
    ("LLY", "FDA approves Lilly's EBGLYSS® (lebrikizumab-lbkz) for one maintenance dose every eight weeks in "
            "patients with moderate-to-severe atopic dermatitis", "", "label_update"),
    ("AMRX", "Amneal Pharmaceuticals Romidepsin Injection Solution Receives FDA Approval", "", "generic_formulation"),
    ("AMRX", "Amneal Pharma Secures FDA Approval For Additional Strengths And Vial Presentations Of Iohexol "
             "Injection; Co. Plans To Launch These Products In Q3 Of 2026", "", "generic_formulation"),
    ("OGN", "Organon Receives FDA Approval for Interchangeable Designation of Its Denosumab Product", "",
     "biosimilar"),
    ("OGN", "Organon Receives FDA Approval For New Indication", "the biosimilar referencing Prolia", "biosimilar"),
]


@pytest.mark.parametrize("tk,title,ctx,klass", MAT_ROWS)
def test_materiality_class_and_the_default_keeps_todays_behaviour(tk, title, ctx, klass):
    e = one(cls(title, tk, ctx), "fda_approval")
    assert e["materiality"] == klass
    assert T.PUSH_MATERIAL_ONLY is False, "HIS CALL — ships at today's behaviour"
    assert T.is_high_impact(e), "default: every non-tentative, non-generic FDA approval is still high impact"


@pytest.mark.parametrize("tk,title,ctx,klass", MAT_ROWS)
def test_the_switch_on_drops_each_class_from_high_impact(monkeypatch, tk, title, ctx, klass):
    monkeypatch.setattr(T, "PUSH_MATERIAL_ONLY", True)
    e = one(cls(title, tk, ctx), "fda_approval")
    assert not T.is_high_impact(e)
    assert "device clearance" in T.high_impact_text() and "device clearance" in A.gate_text()


@pytest.mark.parametrize("tk,title", [
    ("LLY", "FDA Grants Approval For Eli Lilly's Selpercatinib For Patients With A RET Gene Fusion"),
    ("MRNA", "Moderna Receives U.S. FDA Approval for Influenza Vaccine mFLUSIVA"),
    ("GILD", "Gilead Sciences Receives FDA Approval For Its Trodelvy To Treat Triple-Negative Breast Cancer"),
    ("LLY", "After Novo's Setback, Lilly Receives FDA Approval for Orforglipron Tablets"),
    ("UTHR", "United Therapeutics Corporation Announces FDA Approval of the LungFX™ Device for Ex Vivo Lung Perfusion"),
])
def test_NEGATIVE_a_material_approval_stays_high_with_the_switch_on(monkeypatch, tk, title):
    monkeypatch.setattr(T, "PUSH_MATERIAL_ONLY", True)
    e = one(cls(title, tk), "fda_approval")
    assert e["materiality"] is None and T.is_high_impact(e)


def test_NEGATIVE_materiality_never_changes_the_subtype_or_the_off_text():
    e = one(cls("Amneal Pharmaceuticals Romidepsin Injection Solution Receives FDA Approval", "AMRX"), "fda_approval")
    assert e["subtype"] == "novel"
    assert T.high_impact_text() == T.HIGH_IMPACT_TEXT
    # a spelled-out supplemental BLA is a label expansion (a label, not a push, change)
    e = one(cls("Organon's Supplemental Biologics License Application Gets FDA Approval For TOFIDENCE To Treat "
                "Cytokine Release Syndrome", "OGN"), "fda_approval")
    assert e["subtype"] == "label_expansion" and T.is_high_impact(e)


# ════════════════════════════════════════════════════════════════════════════
# the OOS push set, headline by headline (graded_pushes.json)
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tk,title", [
    ("PEN", "Penumbra's THUNDERBOLT Gets FDA Clearance To Treat Acute Ischemic Stroke"),
    ("GILD", "Merck And Gilead Discontinue Phase 3 KEYNOTE-D46/EVOKE-03 Trial After Trodelvy–KEYTRUDA "
             "Combination Fails To Achieve Statistically Significant Progression-Free Survival Benefit In "
             "First-Line Metastatic NSCLC"),
    ("GILD", "Gilead Sciences Receives FDA Approval For Its Trodelvy Antibody-Dug Conjugate To Treat Adult "
             "Patients With Unresectable Locally Advanced Or Metastatic Triple-Negative Breast Cancer"),
    ("UTHR", "United Therapeutics Corporation Announces FDA Approval of the LungFX™ Device for Centralized "
             "Ex Vivo Lung Perfusion"),
    ("MRNA", "Moderna Receives U.S. FDA Approval for Influenza Vaccine mFLUSIVA"),
    ("LLY", "Eli Lilly announces Phase 3 Libretto-432 trial of Retevmo met primary endpoint"),
    ("LLY", "FDA Grants Approval For Eli Lilly's Selpercatinib For Patients With Locally Advanced Or Metastatic "
            "Solid Tumors With A RET Gene Fusion"),
    ("LLY", "Eli Lilly Reports Topline Results From TRIUMPH-2 And TRIUMPH-3 Phase 3 Trials Evaluating "
            "Retatrutide; Treatment Met Primary Endpoint, With Substantial Weight Loss In Adults With Obesity"),
    ("LLY", "Lilly's olomorasib receives U.S. FDA's Breakthrough Therapy designation for the treatment of "
            "previously treated KRAS G12C-mutant advanced pancreatic cancer"),
    ("GILD", "Gilead And Merck Report Phase 3 Results For Once-Weekly Oral HIV Regimen Islatravir/Lenacapavir; "
             "Meets Week 48 Endpoints In ISLEND-1 And ISLEND-2 Trials"),
    ("LLY", "Eli Lilly (LLY) Announces Positive Phase 3 Results for Jaypirca Combination in Relapsed CLL/SLL"),
])
def test_the_graded_TRUE_pushes_still_qualify(tk, title):
    assert would_push(cls(title, tk))


@pytest.mark.parametrize("tk,title", [
    ("PTGX", "Protagonist Therapeutics: 'Strong Buy' ICOTYDE FDA Approval And PN-881 Advancement"),
    ("LH", "Labcorp Announces Availability of Roche's Ventana Pten RxDx Assay, First Immunohistochemistry Companion "
           "Diagnostic Test Approved By FDA To Determine Pten Protein Loss In Prostate Adenocarcinoma Patients"),
    ("MDT", "Edwards wins FDA clearance for LAA clip, setting up competition with AtriCure and Medtronic"),
])
def test_the_graded_FALSE_pushes_no_longer_qualify(tk, title):
    assert not would_push(cls(title, tk))
