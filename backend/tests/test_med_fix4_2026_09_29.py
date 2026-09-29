"""🧬 medical catalysts — fix round 4 (2026-09-29): the round-3 critic's four
code defects + the /alerts shadow count, and the GENERIC bugs the fresh
out-of-sample grade (2025-10..2026-01, 80 new names) exposed.

The fresh grade's rows stay OUT-OF-SAMPLE: every row below is a synthetic
headline of the same FORM (invented tickers / products), or a critic probe —
never a graded headline.

  critic #1  a drug-name key linked ATTAIN-2 to ATTAIN-1 (recap / stale forever);
  critic #2  "REDEFINE 1" / "REDEFINE 2" both keyed REDEFINE, "OUTCOMES" a key;
  critic #3  one readout phrased by drug and by trial rang twice;
  critic #4  "<Product> Gets FDA Nod …, <Issuer> Says" / "<Issuer>: FDA Approval
             of <Product>'s …" / "Approval For Alzheimer's …" lost attribution;
  critic #5  /alerts `shadow` read 0 five minutes after a would-push;
  OOS #1     a product-only headline never reached the classifier;
  OOS #2     a garbled "NDA … Receives FDA's Approval" (an ACCEPTANCE) pushed;
  OOS #3     sNDA / manufacturing-site / packaging approvals had no materiality;
  OOS #4     an approval of ANOTHER product merged into / was blocked by the first;
  OOS #5     "registrational cohort met primary" inside a Phase 1/2 stayed 1/2;
  OOS #6     an undirected readout headline ignored its summary's "positive topline";
  OOS #7     "Publication in The Lancet of Positive Phase 3 Data" read as a new readout.
NEGATIVES everywhere. Purge the bytecode caches before running.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import alerts as A        # noqa: E402
from catalysts.medical import classify as C      # noqa: E402
from catalysts.medical import routine as RT      # noqa: E402
from catalysts.medical import sources as SRC     # noqa: E402
from catalysts.medical import store as S         # noqa: E402
from catalysts.medical import taxonomy as T      # noqa: E402
from tests.test_med_alerts import Sender, kod    # noqa: E402
from tests.test_med_store import FakeColl        # noqa: E402

ET = ZoneInfo("America/New_York")

NAMES = {"LLY": "Eli Lilly and Company", "GILD": "Gilead Sciences, Inc.", "MRK": "Merck & Co., Inc.",
         "BMY": "Bristol-Myers Squibb Company", "AXSM": "Axsome Therapeutics, Inc.", "LH": "Labcorp Holdings Inc.",
         "XYZ": "XYZ Bio Inc.", "QRS": "QRS Therapeutics, Inc.", "NVO": "Novo Nordisk A/S",
         "ABC": "ABC Medical Corporation"}


def cls(title: str, ticker: str, context: str = "") -> dict:
    return C.classify(title, context=context, ticker=ticker, forms=C.name_forms(ticker, NAMES.get(ticker)),
                      issuer_medical=True)


def one(r: dict, typ: str) -> dict:
    evs = [e for e in r["events"] if e["event_type"] == typ]
    assert len(evs) == 1, (typ, r["events"])
    return evs[0]


def et(*a):
    return datetime(*a, tzinfo=ET)


def ev_(tk="LLY", td="topline_positive", sd="2026-08-17", *, subjects=(), trial_keys=(), trials=(),
        state="pending", **kw):
    typ = "topline" if td.startswith("topline") else td
    d = {"_id": S.event_key(tk, td, sd) + kw.pop("suffix", ""), "ticker": tk, "type_dir": td, "event_type": typ,
         "direction": td.split("_")[1] if typ == "topline" else None, "phase": "3", "session_date": sd,
         "subjects": sorted(set(subjects) | set(trial_keys)), "trial_keys": list(trial_keys),
         "trials": list(trials), "modality": ["unclassified"], "areas": ["unclassified"], "sources": [],
         "impact": "high", "subtype": "novel" if typ == "fda_approval" else None,
         "regulator": "FDA" if typ == "fda_approval" else None,
         "published_at": datetime.fromisoformat(sd).replace(hour=10, minute=30, tzinfo=timezone.utc),
         "first_seen_at": datetime.fromisoformat(sd).replace(hour=10, minute=31, tzinfo=timezone.utc),
         "push": {"state": state, "reason": None, "at": None}, "baseline": False,
         "reaction": {"at_detection": {"move_pct": 4.0}, "liquidity": {"base_close": 100.0, "adv50_usd": 1e9}}}
    d.update(kw)
    return d


MON_0630 = et(2026, 8, 17, 6, 35)


# ════════════════════════════════════════════════════════════════════════════
# critic #2 — trial keys keep their number / suffix
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("title,want", [
    ("Novo Nordisk: CagriSema Meets Primary Endpoint In REDEFINE 1 Trial", ["REDEFINE-1"]),
    ("Novo Nordisk: CagriSema Meets Primary Endpoint In REDEFINE 2 Trial", ["REDEFINE-2"]),
    ("Lenacapavir PURPOSE 2 Trial Meets Primary Endpoint", ["PURPOSE-2"]),
    ("Viking Therapeutics Announces Positive Topline Results From VENTURE-Oral Phase 2 Study", ["VENTURE-ORAL"]),
    ("Madrigal Announces Positive Topline Data From MAESTRO-NASH OUTCOMES Phase 3 Trial",
     ["MAESTRO-NASH-OUTCOMES"]),
    ("Gilead Meets Week 48 Endpoints In ISLEND-1 And ISLEND-2 Trials", ["ISLEND-1", "ISLEND-2"]),
    ("Merck And Gilead Discontinue Phase 3 KEYNOTE-D46/EVOKE-03 Trial", ["KEYNOTE-D46", "EVOKE-03"]),
    ("XYZ Bio Starts Phase 2 Study NCT06556368", ["NCT06556368"]),
])
def test_trial_keys_keep_the_trial_number(title, want):
    assert C.extract_trial_keys(title) == want
    assert set(want) <= set(C.extract_subjects(title))


@pytest.mark.parametrize("title,never", [
    ("Madrigal Announces Positive Topline Data From MAESTRO-NASH OUTCOMES Phase 3 Trial", {"OUTCOMES", "MAESTRO-NASH"}),
    ("XYZ Bio Reports XYZ-101 ALPHA Trial Results", {"XYZ-101-ALPHA"}),
    ("XYZ Bio Reports Positive HIV PURPOSE 2 Trial Data", {"HIV", "HIV-PURPOSE-2"}),
    ("XYZ BIO ANNOUNCES ALPHA 2 PHASE 3 TRIAL RESULTS", {"BIO", "ANNOUNCES", "BIO-ANNOUNCES"}),
    ("XYZ Bio Phase 3 Trial Meets Primary Endpoint", {"PHASE", "PHASE-3"}),
])
def test_NEGATIVE_no_generic_tail_no_glued_code_no_stop_word_no_shouting_word(title, never):
    got = set(C.extract_trial_keys(title, ticker="XYZ", forms=C.name_forms("XYZ", NAMES["XYZ"])))
    assert not (got & never), got & never


def test_a_drug_code_before_a_trial_name_stays_a_drug_key():
    t = "XYZ Bio Reports XYZ-101 ALPHA Trial Results"
    assert C.extract_trial_keys(t) == ["ALPHA"]
    assert "XYZ-101" in C.extract_subjects(t) and "XYZ-101" not in C.extract_trial_keys(t)


def test_extract_trial_uses_the_same_normaliser():
    assert C.extract_trial("CagriSema Meets Primary Endpoint In REDEFINE 2 Trial") == "REDEFINE-2"
    assert C.extract_trial("Kodiak DAYBREAK Phase 3 Study Meets Primary Endpoint") == "DAYBREAK"
    assert C.extract_trial("XYZ Bio Phase 3 Trial Meets Primary Endpoint") is None, "NEGATIVE: no name, no trial"


def test_REDEFINE_2_never_merges_into_REDEFINE_1_at_any_date():
    r1 = ev_("NVO", sd="2026-04-17", trial_keys=["REDEFINE-1"], trials=["REDEFINE-1"])
    r2 = ev_("NVO", trial_keys=["REDEFINE-2"], trials=["REDEFINE-2"])
    assert S.find_merge_target(FakeColl([r1]), r2, lo_date=date(2026, 8, 12), hi_date=date(2026, 8, 20)) is None
    # NEGATIVE: the SAME trial at any earlier date still merges (rule ii)
    r1b = ev_("NVO", trial_keys=["REDEFINE-1"], trials=["REDEFINE-1"])
    assert S.find_merge_target(FakeColl([r1]), r1b, lo_date=date(2026, 8, 12),
                               hi_date=date(2026, 8, 20))["_id"] == r1["_id"]


# ════════════════════════════════════════════════════════════════════════════
# critic #1 — a drug name alone never links two different trials
# ════════════════════════════════════════════════════════════════════════════
ATTAIN1 = dict(sd="2026-04-17", subjects=["ORFORGLIPRON"], trial_keys=["ATTAIN-1"])
ATTAIN2 = dict(subjects=["ORFORGLIPRON"], trial_keys=["ATTAIN-2"])


def test_ATTAIN_2_is_not_a_recap_of_ATTAIN_1_and_does_not_inherit_its_age():
    old = ev_(state="pushed", **ATTAIN1)
    new = ev_(**ATTAIN2)
    assert A.gate(new, now_et=MON_0630, baseline=False, prior=[old]) is None
    never_rang = dict(old, push={"state": "not_eligible"})
    assert A.event_origin(new, [never_rang]) == new["published_at"]
    assert A.gate(new, now_et=MON_0630, baseline=False, prior=[never_rang]) is None, "NEGATIVE: not stale"


def test_NEGATIVE_the_same_trial_re_reported_months_later_is_still_a_recap():
    old = ev_(state="pushed", **ATTAIN1)
    again = ev_(subjects=["ORFORGLIPRON"], trial_keys=["ATTAIN-1"])
    assert A.gate(again, now_et=MON_0630, baseline=False, prior=[old]) == "recap"
    assert A.event_origin(again, [dict(old, push={"state": "not_eligible"})]) == old["published_at"]


def test_a_drug_only_topline_months_later_is_not_linked_by_the_drug_name():
    old = ev_("GILD", sd="2026-04-17", state="pushed", subjects=["LENACAPAVIR"], trial_keys=["PURPOSE-2"])
    new = ev_("GILD", subjects=["ISLATRAVIR", "LENACAPAVIR"])
    assert A.gate(new, now_et=MON_0630, baseline=False, prior=[old]) is None
    # NEGATIVE: inside RECAP_SESSIONS the drug-only vs trial-only pair keeps the old per-name rule
    recent = dict(old, session_date="2026-08-10", _id="GILD|topline_positive|2026-08-10")
    assert A.gate(new, now_et=MON_0630, baseline=False, prior=[recent]) == "recap"


def test_NEGATIVE_approvals_are_still_linked_by_the_drug_at_any_date():
    old = ev_("XYZ", "fda_approval", "2026-06-01", state="pushed", subjects=["THUNDERCLAP"])
    rehash = ev_("XYZ", "fda_approval", subjects=["THUNDERCLAP"])
    assert A.gate(rehash, now_et=MON_0630, baseline=False, prior=[old]) == "recap"


# ════════════════════════════════════════════════════════════════════════════
# critic #3 — one readout phrased two ways rings once
# ════════════════════════════════════════════════════════════════════════════
def _live(evs, claims=None):
    s = Sender()
    claims = claims if claims is not None else FakeColl()
    out = A.run_push(evs, now_et=MON_0630, prior=[], claim_coll=claims, events_coll=FakeColl(evs), owner="o",
                     sender=s, counts={}, shadow=False)
    return s, out, claims


def test_one_readout_by_drug_and_by_trial_rings_once():
    by_drug = ev_("GILD", subjects=["ISLATRAVIR", "LENACAPAVIR"])
    by_trial = ev_("GILD", trial_keys=["ISLEND-1", "ISLEND-2"], suffix="|b",
                   published_at=datetime(2026, 8, 17, 10, 40, tzinfo=timezone.utc))
    s, out, _c = _live([by_drug, by_trial])
    assert len(s.calls) == 1 and [d["reason"] for d in out["decisions"]].count("claimed_elsewhere") == 1


@pytest.mark.parametrize("a,b,n", [
    (dict(**ATTAIN1), dict(**ATTAIN2), 2),                                          # two trials
    (dict(subjects=["RETEVMO"], trial_keys=["LIBRETTO-432"]), dict(subjects=["JAYPIRCA"]), 2),   # brand vs brand
    (dict(subjects=["RETEVMO"]), dict(subjects=["SELPERCATINIB"]), 1),              # brand vs INN: may be one drug
    (dict(subjects=["ORFORGLIPRON"], trial_keys=["ATTAIN-2"]), dict(subjects=["ORFORGLIPRON"]), 1),
])
def test_the_topline_claim_mirrors_different_story(a, b, n):
    a = dict(a, sd="2026-08-17")
    e1 = ev_(**a)
    e2 = ev_(suffix="|b", published_at=datetime(2026, 8, 17, 10, 40, tzinfo=timezone.utc), **b)
    s, _o, _c = _live([e1, e2])
    assert len(s.calls) == n


def test_NEGATIVE_the_existing_per_trial_claim_keys_are_unchanged():
    _s, _o, claims = _live([kod()])
    assert {"MC:KOD|topline|2026-09-28|DAYBREAK", "MC:KOD|topline|2026-09-28|+"} <= set(claims.docs)


# ════════════════════════════════════════════════════════════════════════════
# OOS #4 — an approval of ANOTHER product is another story
# ════════════════════════════════════════════════════════════════════════════
def test_an_approval_of_another_product_never_merges_and_is_not_a_recap():
    first = ev_("ABC", "fda_approval", "2026-08-12", state="pushed", subjects=["PICCOLINO"])
    other = ev_("ABC", "fda_approval", subjects=["ZAPWAVE"])
    assert S.find_merge_target(FakeColl([first]), other, lo_date=date(2026, 8, 12), hi_date=date(2026, 8, 20)) is None
    assert A.gate(other, now_et=MON_0630, baseline=False, prior=[first]) is None


def test_NEGATIVE_brand_and_INN_approvals_still_merge_and_an_unkeyed_one_still_recaps():
    inn = ev_("LLY", "fda_approval", "2026-08-13", state="pushed", subjects=["SELPERCATINIB"])
    brand = ev_("LLY", "fda_approval", subjects=["RETEVMO"])
    assert S.find_merge_target(FakeColl([inn]), brand, lo_date=date(2026, 8, 12),
                               hi_date=date(2026, 8, 20))["_id"] == inn["_id"]
    assert A.gate(brand, now_et=MON_0630, baseline=False, prior=[inn]) == "recap"
    bare = ev_("LLY", "fda_approval")
    assert A.gate(bare, now_et=MON_0630, baseline=False, prior=[inn]) == "recap"


def test_NEGATIVE_designations_keep_the_ticker_plus_kind_rule():
    a = ev_("XYZ", "designation", "2026-08-12", state="pushed", subjects=["ALPHAMAB"], subtype="breakthrough_therapy")
    b = ev_("XYZ", "designation", subjects=["BETAMAB"], subtype="breakthrough_therapy")
    assert S.different_story(b, a) is False
    assert A.gate(b, now_et=MON_0630, baseline=False, prior=[a]) == "recap"


# ════════════════════════════════════════════════════════════════════════════
# critic #4 — attribution: the issuer's own product
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tk,title", [
    ("BMY", "Opdivo Gets FDA Nod For Liver Cancer, Bristol Myers Squibb Says"),
    ("AXSM", "Auvelity Receives FDA Approval For Alzheimer's Agitation, Axsome Announces"),
    ("MRK", "Merck: FDA Approval of Keytruda's Subcutaneous Form"),
    ("MRK", "Keytruda Wins FDA Approval For Early Lung Cancer, Merck Says"),
    ("XYZ", "Zolimab Receives FDA Approval For Parkinson's Disease Psychosis, XYZ Bio Says"),
])
def test_the_issuers_own_product_is_attributed(tk, title):
    assert cls(title, tk)["attributed"] is True


@pytest.mark.parametrize("tk,title", [
    ("LH", "Labcorp Announces FDA Approval of Roche's Companion Diagnostic"),
    ("LH", "Roche's Test Wins FDA Approval, Labcorp Says"),
    ("LH", "Labcorp Announces Availability of Roche's Assay, Test Approved By FDA For Prostate Cancer"),
    ("XYZ", "Rivalco Receives FDA Approval For Zolimab, Setting Up Competition With XYZ Bio"),
])
def test_NEGATIVE_a_rival_is_still_not_the_issuer(tk, title):
    assert cls(title, tk)["attributed"] is False


# ════════════════════════════════════════════════════════════════════════════
# critic #5 — /alerts keeps the shadow count for the session
# ════════════════════════════════════════════════════════════════════════════
def test_shadow_session_count_survives_the_next_pass():
    from tests.test_med_routine import fetchers, seeded, tick, NOW, Sender as RSender
    assert A.SHADOW is True
    now = NOW.replace(hour=9, minute=0)
    c = seeded(now=now)
    fx, _ = fetchers(now=now)
    out = tick(c, fx, now=now)
    assert fx["sender"].calls == [], "NEGATIVE: shadow never sends"
    assert out["counts"]["shadow"] >= 1 and out["counts"]["shadow_session"] >= 1
    fx2, _ = fetchers(now=now, sender=RSender())
    out2 = tick(c, fx2, now=now + timedelta(minutes=5))
    assert out2["counts"]["shadow"] == 0, "nothing new would push on the second pass"
    assert out2["counts"]["shadow_session"] == out["counts"]["shadow_session"]
    assert c["alert_pass_latest"].docs["med_catalyst"]["counts"]["shadow_session"] >= 1


def test_NEGATIVE_shadow_session_counts_only_this_session_and_only_shadow():
    evc = FakeColl([ev_(state="shadow", sd="2026-08-14"), ev_(state="shadow"), ev_(state="pushed", suffix="|p"),
                    ev_(state="pending", suffix="|q")])
    assert RT.shadow_session_count(evc, MON_0630) == 1
    assert RT.shadow_session_count(None, MON_0630) == 0


# ════════════════════════════════════════════════════════════════════════════
# OOS #1 — a product-only headline reaches the classifier
# ════════════════════════════════════════════════════════════════════════════
def test_subject_hit_needs_a_capitalised_proper_noun():
    assert SRC.subject_hit("FDA Approves Zolimab For Wet AMD", {"ZOLIMAB"}) == ["ZOLIMAB"]
    assert SRC.subject_hit("FDA approves first oral antibiotic ZOLIMAB", ["ZOLIMAB"]) == ["ZOLIMAB"]
    assert SRC.subject_hit("A venture into purpose-built devices", {"VENTURE", "PURPOSE"}) == [], \
        "NEGATIVE: an ordinary lower-case word is never a product"
    assert SRC.subject_hit("FDA Approves Zolimabx", {"ZOLIMAB"}) == [], "NEGATIVE: whole word only"
    assert SRC.subject_hit("anything", None) == []


def test_owned_subjects_drop_keys_another_name_carries():
    c = FakeColl([ev_("XYZ", subjects=["ZOLIMAB", "KEYTRUDA"]), ev_("MRK", subjects=["KEYTRUDA"]),
                  ev_("XYZ", "fda_approval", "2026-08-10", subjects=["PHASE", "NSCLC", "ONCOLOGY"])])
    own = S.owned_subjects(c, ["XYZ"])
    assert own == {"XYZ": {"ZOLIMAB"}}, "NEGATIVE: a partner's / rival's product and generic words are dropped"
    assert S.owned_subjects(None, ["XYZ"]) == {}


def test_finnhub_articles_keep_a_product_only_headline_with_via_subject():
    rows = [{"headline": "FDA Approves Zolimab, First Oral Treatment For Gonorrhea", "datetime": 1_780_000_000,
             "id": 1, "url": "u1", "source": "s", "summary": "", "related": "XYZ"},
            {"headline": "FDA Approves Rivalmab For Gonorrhea", "datetime": 1_780_000_100, "id": 2, "url": "u2",
             "source": "s", "summary": "", "related": "XYZ"}]

    async def fetch(_s, _d):
        return rows
    counts = {}
    arts = asyncio.run(SRC.finnhub_articles("XYZ", company=NAMES["XYZ"], forms=C.name_forms("XYZ", NAMES["XYZ"]),
                                            fetch=fetch, counts=counts, subject_keys={"ZOLIMAB"}))
    assert [a["title"] for a in arts] == [rows[0]["headline"]] and arts[0]["via_subject"] == ["ZOLIMAB"]
    assert counts["irrelevant_dropped"] == 1 and counts["subject_relevant"] == 1


def test_the_routine_attributes_via_the_product_but_keeps_the_rival_guard():
    t = "FDA Approves Zolimab, First Oral Treatment For Gonorrhea"
    cl = cls(t, "XYZ")
    assert cl["attributed"] is False
    forms = C.name_forms("XYZ", NAMES["XYZ"])
    assert RT._attributed_via_subject(C, {"title": t, "via_subject": ["ZOLIMAB"]}, cl, "XYZ", forms) is True
    rival = "FDA Approves Rivalco's Zolimab For Gonorrhea"
    assert RT._attributed_via_subject(C, {"title": rival, "via_subject": ["ZOLIMAB"]}, cls(rival, "XYZ"),
                                      "XYZ", forms) is False, "NEGATIVE: another company's possessive"
    assert RT._attributed_via_subject(C, {"title": t}, cl, "XYZ", forms) is False, "NEGATIVE: no via_subject"


# ════════════════════════════════════════════════════════════════════════════
# OOS #2 — an approval contradicted by the same drug's filing acceptance
# ════════════════════════════════════════════════════════════════════════════
def _acc(sd="2026-08-17", subjects=("ZIDOTINIB",), tk="XYZ", **kw):
    d = ev_(tk, "regulatory_filing", sd, subjects=subjects, **kw)
    d.update(subtype="accepted", impact="low", regulator=None, _id=S.event_key(tk, "regulatory_filing", sd))
    return d


def test_classifier_forms_of_the_pair():
    appr = cls("XYZ Bio New Drug Application For Zidotinib Reeives FDA's Approval To Treat Lung Cancer", "XYZ")
    acc = cls("XYZ Bio Announces FDA Acceptance Of NDA For Zidotinib", "XYZ")
    assert one(appr, "fda_approval")["subjects"] == one(acc, "regulatory_filing")["subjects"] == ["ZIDOTINIB"]
    assert one(acc, "regulatory_filing")["subtype"] == "accepted"


@pytest.mark.parametrize("approval_first", [True, False])
def test_a_same_drug_acceptance_nearby_contradicts_the_approval(approval_first):
    appr = ev_("XYZ", "fda_approval", "2026-08-17", subjects=["ZIDOTINIB"])
    acc = _acc("2026-08-18")
    c = FakeColl([appr, acc])
    n = RT._contradict(c, (appr if approval_first else acc)["_id"], at=datetime(2026, 8, 18, tzinfo=timezone.utc))
    got = c.docs[appr["_id"]]
    assert n == 1 and got["contradicted"]["by"] == acc["_id"] and got["impact"] == "low"
    assert T.is_high_impact(got) is False and T.is_high_impact(appr) is True
    assert A.gate(got, now_et=et(2026, 8, 18, 6, 0), baseline=False, prior=[]) == "not_high_impact"
    assert RT._contradict(c, appr["_id"], at=None) == 0, "stamped once"


@pytest.mark.parametrize("acc", [
    _acc(subjects=("OTHERTINIB",)),                  # another drug
    _acc(sd="2026-06-01"),                           # outside store.MERGE_SESSIONS
    _acc(tk="QRS"),                                  # another name
    _acc(subjects=()),                               # an unkeyed acceptance proves nothing
])
def test_NEGATIVE_no_contradiction_without_the_same_drug_nearby(acc):
    appr = ev_("XYZ", "fda_approval", "2026-08-17", subjects=["ZIDOTINIB"])
    c = FakeColl([appr, acc])
    assert RT._contradict(c, appr["_id"], at=None) == 0 and "contradicted" not in c.docs[appr["_id"]]
    assert RT._contradict(c, "missing", at=None) == 0 and RT._contradict(None, appr["_id"], at=None) == 0


# ════════════════════════════════════════════════════════════════════════════
# OOS #3 — supplemental / site / packaging approvals carry a materiality
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("title,context", [
    ("XYZ Bio Receives FDA Approval Of sNDA For Zolimab In Adolescents", ""),
    ("FDA Approves XYZ Bio's Supplemental Biologics License Application For Zolimab", ""),
    ("XYZ Bio Received FDA Approval For Zolimab At Its Springfield, Ohio Site", ""),
    ("FDA Approves XYZ Bio's Zolimab Nasal Spray Packaged In A New Carrying Case", ""),
    ("XYZ Bio Announces FDA Approval Of Zolimab In Adult Patients With Relapsed AML",
     "The FDA approved the company's supplemental New Drug Application for Zolimab. Shares rose."),
])
def test_supplements_sites_and_packaging_are_label_updates(title, context):
    e = one(cls(title, "XYZ", context), "fda_approval")
    assert e["materiality"] == "label_update"
    assert T.is_high_impact(e) is True, "the switch ships OFF: today's behaviour"


def test_NEGATIVE_a_novel_approval_has_no_materiality_class_and_the_subtype_never_changes():
    e = one(cls("XYZ Bio Receives FDA Approval Of Zolimab For Wet AMD", "XYZ",
                "The approval is the first for the company. A supplemental filing is planned next year."), "fda_approval")
    assert e["materiality"] is None and e["subtype"] == "novel"
    e2 = one(cls("XYZ Bio Receives FDA Approval Of sNDA For Zolimab", "XYZ"), "fda_approval")
    assert e2["subtype"] == "label_expansion" and e2["materiality"] == "label_update"


def test_the_switch_on_drops_a_label_update(monkeypatch):
    e = one(cls("XYZ Bio Receives FDA Approval Of sNDA For Zolimab", "XYZ"), "fda_approval")
    monkeypatch.setattr(T, "PUSH_MATERIAL_ONLY", True)
    assert T.is_high_impact(e) is False


# ════════════════════════════════════════════════════════════════════════════
# OOS #5 — a registrational / pivotal cohort lifts the phase
# ════════════════════════════════════════════════════════════════════════════
def test_a_registrational_cohort_inside_a_phase_1_2_is_pivotal():
    e = one(cls("XYZ Bio's Phase 1/2 ALPHA Trial Registrational Expansion Cohort Met Primary Endpoint", "XYZ"),
            "topline")
    assert e["phase"] == "pivotal" and e["direction"] == "positive" and T.is_high_impact(e)


@pytest.mark.parametrize("title,phase", [
    ("XYZ Bio Positive Phase 2 Results Support Registrational Path For Zolimab", "2"),
    ("XYZ Bio Phase 2 Data Met Primary Endpoint; Company Plans To Advance To Registrational Trial", "2"),
    ("Merck's Remigromig Met Primary Endpoint in the Pivotal Phase 2b/3 BRUNELLO Study", "2/3"),
    ("XYZ Bio Phase 1/2 ALPHA Trial Met Primary Endpoint", "1/2"),
])
def test_NEGATIVE_talk_future_and_numbered_pivotal_phases_are_not_lifted(title, phase):
    tk = "MRK" if "Merck" in title else "XYZ"
    assert one(cls(title, tk), "topline")["phase"] == phase


# ════════════════════════════════════════════════════════════════════════════
# OOS #6 — an undirected readout takes the summary's first sentence
# ════════════════════════════════════════════════════════════════════════════
UNDIRECTED = "XYZ Bio Announces Phase 3 ALPHA Results For Zolimab Demonstrating Meaningful Survival Improvement"


def test_an_undirected_readout_takes_the_summarys_direction():
    r = cls(UNDIRECTED, "XYZ", "XYZ Bio announced positive topline results from the Phase 3 ALPHA trial. More follows.")
    e = one(r, "topline")
    assert e["direction"] == "positive" and e["direction_from"] == "summary" and T.is_high_impact(e)
    neg = one(cls(UNDIRECTED, "XYZ", "The Phase 3 ALPHA trial did not meet its primary endpoint."), "topline")
    assert neg["direction"] == "negative"


@pytest.mark.parametrize("context", [
    "",
    "Shares rose in early trade. The company said the trial met its primary endpoint.",   # 2nd sentence only
    "A post-hoc analysis showed the trial met its primary endpoint in a subgroup.",
    "The company discussed the trial design and alignment with the FDA.",
])
def test_NEGATIVE_no_direction_from_a_later_sentence_or_post_hoc_talk(context):
    e = one(cls(UNDIRECTED, "XYZ", context), "topline")
    assert e["direction"] == "unknown" and not T.is_high_impact(e)


def test_NEGATIVE_a_directed_headline_is_never_overridden_by_the_summary():
    e = one(cls("XYZ Bio Phase 3 ALPHA Trial Met Primary Endpoint", "XYZ",
                "The trial did not meet its key secondary endpoint in all patients."), "topline")
    assert e["direction"] == "positive" and e["direction_from"] == "title"


# ════════════════════════════════════════════════════════════════════════════
# OOS #7 — a journal publication is not a new readout
# ════════════════════════════════════════════════════════════════════════════
def test_a_publication_of_old_data_is_not_a_new_positive_readout():
    r = cls("XYZ Bio Announces Publication in The Lancet of Positive Zolimab Phase 3 Data", "XYZ")
    assert not [e for e in r["events"] if e["event_type"] == "topline" and T.is_high_impact(e)]


def test_NEGATIVE_a_real_readout_mentioning_a_future_publication_still_pushes():
    e = one(cls("XYZ Bio Phase 3 ALPHA Trial Met Primary Endpoint; Data To Be Submitted For Publication", "XYZ"),
            "topline")
    assert e["direction"] == "positive" and T.is_high_impact(e)


# ════════════════════════════════════════════════════════════════════════════
# wording
# ════════════════════════════════════════════════════════════════════════════
def test_gate_text_and_high_impact_text_say_the_new_rules():
    g = A.gate_text()
    assert "approval of a different product, is not a repeat" in g and "SHADOW MODE" in g
    assert "not contradicted by an FDA acceptance" in T.HIGH_IMPACT_TEXT
