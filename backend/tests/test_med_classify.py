"""🧬 catalysts.medical.classify + taxonomy — table-driven over the labelled
fixture (tests/fixtures/medical/headlines.json, spec §3.4.5) plus named
NEGATIVES, each with its own test id (spec WP-CLS).

Mutation pins (purge caches first — macOS bytecode cache defeats them):
  drop `hit` from the NEG verbs         -> test_negation_did_not_hit fails
  restore a bare `failure` NEG cue      -> test_heart_and_kidney_failure_met_is_positive fails
  revert A1 to a 40-char FDA window     -> test_compromise_with_fda_and_path_to_approval_are_no_event fails
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from catalysts.medical import classify as C   # noqa: E402
from catalysts.medical import taxonomy as T   # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "medical", "headlines.json")
DATA = json.load(open(FIX, encoding="utf-8"))
ROWS = DATA["rows"]
ATTR = DATA["attribution"]


def run(row: dict) -> dict:
    tk = row.get("ticker")
    forms = C.name_forms(tk, row.get("company")) if tk else ()
    im = row.get("issuer_medical", bool(tk))
    return C.classify(row["title"], context=row.get("context") or "", ticker=tk, forms=forms, issuer_medical=im)


def cls(title: str, ticker=None, company=None, issuer_medical=None) -> dict:
    forms = C.name_forms(ticker, company) if ticker else ()
    return C.classify(title, ticker=ticker, forms=forms,
                      issuer_medical=bool(ticker) if issuer_medical is None else issuer_medical)


def types(r: dict) -> list:
    return sorted(e["event_type"] for e in r["events"])


def one(r: dict, typ: str) -> dict:
    evs = [e for e in r["events"] if e["event_type"] == typ]
    assert len(evs) == 1, (typ, r["events"])
    return evs[0]


# ---------------------------------------------------------------------------
# table-driven: every labelled row
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_labelled_headline(row):
    r = run(row)
    exp = row["expected"]
    want = Counter(e["event_type"] for e in exp["events"])
    got = Counter(e["event_type"] for e in r["events"])
    assert got == want, (row["title"], r["events"])
    used = set()
    for xe in exp["events"]:
        ge = next(g for i, g in enumerate(r["events"]) if g["event_type"] == xe["event_type"] and i not in used)
        used.add(r["events"].index(ge))
        for k, v in xe.items():
            if k == "high":
                assert T.is_high_impact(ge) is v, (row["id"], ge)
            else:
                assert ge.get(k) == v, (row["id"], k, ge)
    for k in ("modality", "areas", "attributed", "merge_only"):
        if k in exp:
            assert r[k] == exp[k], (row["id"], k, r[k])
    for d in exp.get("dropped") or []:
        assert d in r["dropped"], (row["id"], r["dropped"])
    assert r["rules_version"] == T.RULES_VERSION


@pytest.mark.parametrize("row", ATTR, ids=[a["id"] for a in ATTR])
def test_attribution_row(row):
    forms = C.name_forms(row["ticker"], row["company"])
    assert C.attribute(row["title"], ticker=row["ticker"], forms=forms, cue_span=None) is row["attributed"]


def test_fixture_is_big_enough_and_every_row_is_labelled():
    real = [r for r in ROWS if not r["synthetic"]]
    assert len(real) >= 40 and len(ATTR) == 18
    assert all("expected" in r and "events" in r["expected"] for r in ROWS)
    assert len({r["id"] for r in ROWS}) == len(ROWS)


# ---------------------------------------------------------------------------
# named NEGATIVES — direction
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title,phase", [
    ("XYZ Phase 3 Trial Did Not Meet Primary Endpoint", "3"),
    ("ABC Fails to Meet Primary Endpoint in Phase 2b", "2"),
    ("EFG Phase 2 Study Showed No Statistically Significant Difference", "2"),
    ("HIJ Discontinues Phase 3 Program After Futility Analysis", "3"),
])
def test_negation_gives_negative_topline(title, phase):
    e = one(cls(title), "topline")
    assert e["direction"] == "negative" and e["phase"] == phase


def test_negation_did_not_hit():
    e = one(cls("ABC Phase 3 Study Did Not Hit Its Primary Endpoint"), "topline")
    assert e["direction"] == "negative"
    assert one(cls("XYZ Phase 3 Trial Fails to Hit Primary Endpoint"), "topline")["direction"] == "negative"


def test_negation_failed_to_show_statistically_significant_is_negative_not_mixed():
    e = one(cls("DEF Phase 3 Trial Failed to Show Statistically Significant Improvement in Overall Survival"), "topline")
    assert e["direction"] == "negative"


def test_heart_and_kidney_failure_met_is_positive():
    assert one(cls("GHI Phase 3 Trial in Heart Failure Met Primary Endpoint"), "topline")["direction"] == "positive"
    assert one(cls("JKL Phase 3 Study in Kidney Failure Patients Achieved Statistical Significance"),
               "topline")["direction"] == "positive"


def test_missed_secondary_is_mixed_never_negative_and_never_high():
    e = one(cls("MNO Phase 3 Trial Misses Key Secondary Endpoint"), "topline")
    assert e["direction"] == "mixed" and e["secondary_missed"] is True
    assert T.is_high_impact(e) is False


def test_mixed_from_positive_plus_secondary_miss_and_from_met_but_missed():
    assert one(cls("DEF Announces Positive Topline Results; Key Secondary Endpoint Not Met"),
               "topline")["direction"] == "mixed"
    assert one(cls("QRS Did Not Meet Primary Endpoint but Showed Statistically Significant Improvement in Key "
                   "Secondary Endpoint"), "topline")["direction"] == "mixed"


def test_bare_failure_is_not_a_topline():
    assert cls("Failure of Novartis' Pelacarsen Could Reshape the Lp(a) Race for CRISPR and Ionis")["events"] == []


# ---------------------------------------------------------------------------
# named NEGATIVES — approval precision
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title", [
    "Shareholders Approve Merger With JKL", "MNO Receives Nasdaq Approval to Transfer Listing",
    "Court Approves Settlement With DEF Holders", "Board Approves Share Buyback at GHI"])
def test_unrelated_approval_never_fires_fda_approval(title):
    assert "fda_approval" not in types(cls(title))


@pytest.mark.parametrize("title", [
    "Satellos Announces FDA Clearance of IND Application for Forazapadin in Facioscapulohumeral Muscular Dystrophy",
    "FDA approves IND for Nutshell’s NRF2 degrader NTS-231",
    "AstraZeneca seeks U.S. FDA approval for lung cancer treatment",
    "AstraZeneca files for US FDA approval of HUTCHMED lung cancer drug combination",
    "FDA Accepts BLA for Zenkuda Based on Positive Phase 3 DAYBREAK Results; Approval Decision Expected in 2027",
    "Prime Medicine Gets FDA Green Light for Gene Editing Study",
])
def test_filings_and_ind_clearances_are_never_approval_or_topline(title):
    t = types(cls(title))
    assert "regulatory_filing" in t and "fda_approval" not in t and "topline" not in t


def test_compromise_with_fda_and_path_to_approval_are_no_event():
    assert cls("Moderna strikes compromise with FDA to advance flu vaccine for 2026 approval")["events"] == []
    assert cls("Solving the Cholinergic Problem: Cobenfy's Path From Shelf to FDA Approval")["events"] == []


def test_refuses_to_review_for_potential_approval_is_a_crl_not_an_approval():
    r = cls("FDA Refuses to Review Moderna's Influenza Vaccine for Potential Approval")
    assert types(r) == ["fda_crl"] and one(r, "fda_crl")["subtype"] == "refuse_to_file"


def test_nod_after_refusal_to_file_is_approval_not_crl():
    assert types(cls("Moderna's mRNA flu shot mFlusiva snags FDA nod after refusal-to-file imbroglio")) == ["fda_approval"]


def test_fda_pulls_clearance_is_revoked_and_never_high():
    r = cls("FDA pulls clearance of Pfizer-BioNTech COVID-19 vaccine for children under 5")
    assert types(r) == ["fda_revoked"] and T.is_high_impact(one(r, "fda_revoked")) is False
    assert types(cls("FDA Rescinds EUA but Approves Updated 2025-2026 COVID Vaccines")) == ["fda_approval", "fda_revoked"]


def test_tentative_approval_is_not_high():
    e = one(cls("Lupin Receives Tentative U.S. FDA Approval For Apixaban Oral Suspension"), "fda_approval")
    assert e["subtype"] == "tentative" and T.is_high_impact(e) is False


def test_exus_approval_is_not_fda():
    r = cls("Natera's Signatera Wins Japan PMDA Approval as Bladder Cancer CDx")
    assert types(r) == ["exus_approval"] and one(r, "exus_approval")["regulator"] == "PMDA"
    assert T.is_high_impact(one(r, "exus_approval")) is False


def test_parenthesised_crl_ticker_is_not_a_complete_response_letter():
    assert cls("Charles River Laboratories (CRL) Stock Still Seems Reasonable Despite Rapid Cell Banking Launch",
               "CRL", "Charles River Laboratories International, Inc.")["events"] == []
    assert types(cls("GHI Receives CRL From FDA for Its Lead Drug")) == ["fda_crl"]


def test_510k_submission_is_a_filing_and_clearance_is_device_clearance():
    assert "fda_approval" not in types(cls("ABC Submits 510(k) to FDA for Its Glucose Monitor"))
    e = one(cls("ABC Receives FDA 510(k) Clearance for Its Glucose Monitor"), "fda_approval")
    assert e["subtype"] == "device_clearance"


# ---------------------------------------------------------------------------
# named NEGATIVES — phase, milestone, scheduled
# ---------------------------------------------------------------------------
def test_plans_to_start_phase_3_keeps_phase_2():
    e = one(cls("TUV Reports Positive Phase 2 Data and Plans to Start Phase 3"), "topline")
    assert e["phase"] == "2" and T.is_high_impact(e) is False


def test_initiates_phase_3_following_phase_2_is_a_milestone_only():
    r = cls("TUV Initiates Pivotal Phase 3 Trial Following Positive Phase 2 Results", "TUV", "TUV Therapeutics")
    assert types(r) == ["trial_milestone"] and one(r, "trial_milestone")["subtype"] == "initiated"


def test_phase_2b_3_is_phase_2_3_and_high():
    e = one(cls("Merck’s Remigromig Met Primary Endpoint in the Pivotal Phase 2b/3 BRUNELLO Study", "MRK",
                "Merck & Co., Inc."), "topline")
    assert e["phase"] == "2/3" and T.is_high_impact(e) is True


def test_halt_after_recruitment_struggles_is_discontinued_no_topline():
    r = cls("EXCLUSIVE: Pfizer, BioNTech halt US COVID vaccine study after recruitment struggles", "PFE", "Pfizer Inc.")
    assert types(r) == ["trial_milestone"] and one(r, "trial_milestone")["subtype"] == "discontinued"
    assert T.is_high_impact(one(r, "trial_milestone")) is False


@pytest.mark.parametrize("title", [
    "Kodiak Sciences To Host Webcast To Report Phase 3 DAYBREAK Topline Results For Wet AMD Candidates On September 28",
    "Kodiak Sciences to Present Topline Results on September 28, 2026 from DAYBREAK Pivotal Phase 3 Study",
    "ABC Expects Phase 3 Topline Data in the Fourth Quarter"])
def test_readout_scheduled_is_never_a_topline(title):
    assert types(cls(title)) == ["readout_scheduled"]


def test_bla_planned_is_no_filing_and_no_approval():
    r = cls("Zenkuda and tabirafusp-ted Meet Primary Endpoints in Pivotal DAYBREAK Trial in wAMD; biologics "
            "license application (BLA) planned for the fourth quarter of 2026")
    assert types(r) == ["topline"]


@pytest.mark.parametrize("title", [
    "Inside the Eye-Drug Breakthrough That Sent Kodiak Sciences Up 172%",
    "Cancer Drug Breakthroughs Accelerate as Biotech Funding Recovers"])
def test_bare_breakthrough_is_never_a_designation(title):
    assert "designation" not in types(cls(title))


@pytest.mark.parametrize("title", [
    "BLAIZE HOLDINGS DEADLINE: ROSEN, THE FIRST FILING FIRM, Encourages Blaize Holdings, Inc. Investors",
    "BlackRock Investor News: If You Have Suffered Losses in BlackRock",
    "Blaize Files for Listing Transfer"])
def test_bla_nda_are_case_sensitive_and_word_bounded(title):
    assert "regulatory_filing" not in types(cls(title)) and "fda_crl" not in types(cls(title))


# ---------------------------------------------------------------------------
# named NEGATIVES — no-event pre-filters
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title", [
    "Teva to Host Conference Call to Discuss Third Quarter 2026 Financial Results on November 3, 2026 at 8 a.m. ET",
    "IN8bio to Present at Sidoti Small-Cap Virtual Conference",
    "XYZ to Present at the H.C. Wainwright 28th Annual Global Investment Conference"])
def test_earnings_calls_and_investor_conferences_are_no_event(title):
    assert cls(title)["events"] == []


@pytest.mark.parametrize("title,flag", [
    ("12 Health Care Stocks Moving In Monday's Pre-Market Session", "roundup"),
    ("Shareholders who lost money in shares of acquired Doximity, Inc. (NYSE: DOCS) should contact Wolf Haldenstein",
     "roundup"),
    ("Roundup: FDA Approves Lilly’s Olumiant, AbbVie’s Juvmo, Mirum & Incyte’s Atebrioz", "roundup"),
    ("Why Moderna (MRNA) Is Up 29.1% After Melanoma Vaccine Success And Middle East Expansion Talks", "commentary"),
    ("CRSP, NTLA, BEAM, PRME, EDIT Shares Slip — Did Claude Just Spook Gene-Editing Stocks?", "commentary"),
    ("Q&A: Cutlip on the SELUTION SLR DEB's FDA Approval for Coronary In-Stent Restenosis", "commentary"),
    ("A Look At Kodiak Sciences (KOD) Valuation After Positive Phase 3 GLOW2 Results For Zenkuda", "commentary"),
    ("Kodiak Sciences Inc. (KOD) Discusses DAYBREAK Topline Data and Primary Endpoint Results Transcript", "commentary"),
    ("Lantheus Holdings (LNTH) Stock May Be 14% Undervalued On FDA Approval", "commentary"),
    ("Cullinan Therapeutics (CGEM) Could Be 50% Below Fair Value On Phase 3 Zipalertinib Data", "commentary"),
    ("Immunovant (IMVT): One Trial Failure Doesn’t Break the Bull Case", "commentary"),
])
def test_roundups_law_firms_and_commentary_are_no_event(title, flag):
    r = cls(title)
    assert r["events"] == [] and r[flag] is True


# ---------------------------------------------------------------------------
# merge-only (price stories)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title,ticker,company", [
    ("Kodiak Sciences soars as Zenkuda, tabirafusp-ted hit primary endpoints in phase III wet AMD trial", "KOD",
     "Kodiak Sciences Inc."),                                                       # M2 name + verb
    ("Moderna Surges 9% as Phase 3 Melanoma Data Wins Presidential Symposium Slot", "MRNA", "Moderna, Inc."),  # M2 / M3
    ("Kodiak Sciences Stock Pops 70% After Eye-Disease Drugs Pass Key Trial", "KOD", "Kodiak Sciences Inc."),  # M1 / M3
    ("Moderna Just Got a Major FDA Approval. The Stock Is Slipping.", "MRNA", "Moderna, Inc."),  # M3 just got
    ("Eli Lilly Just Won FDA Approval for a Once Weekly Insulin and the Stock Is Knocking on $1,200", "LLY",
     "Eli Lilly and Company"),
])
def test_price_stories_are_merge_only(title, ticker, company):
    r = cls(title, ticker, company)
    assert r["merge_only"] is True and r["events"] and all(e["from_commentary"] for e in r["events"])


def test_gains_fda_approval_is_the_news_not_a_price_story():
    r = cls("XYZ Gains FDA Approval for Its Drug")
    assert r["merge_only"] is False and types(r) == ["fda_approval"]


# ---------------------------------------------------------------------------
# attribution
# ---------------------------------------------------------------------------
def test_third_party_subject_is_not_attributed():
    t = "Failure of Novartis' Pelacarsen Could Reshape the Lp(a) Race for CRISPR and Ionis"
    assert cls(t, "CRSP", "CRISPR Therapeutics AG")["attributed"] is False


def test_bntx_clause_rule_and_mrna_subject():
    t = "Moderna Surges 9% as Phase 3 Melanoma Data Wins Presidential Symposium Slot; Merck and BioNTech Edge Higher"
    assert cls(t, "BNTX", "BioNTech SE")["attributed"] is False
    assert cls(t, "MRNA", "Moderna, Inc.")["attributed"] is True


def test_lly_is_found_by_the_distinctive_word_lilly():
    assert "Lilly" in C.name_forms("LLY", "Eli Lilly and Company")
    assert cls("Lilly gets FDA approval for severe alopecia areata", "LLY", "Eli Lilly and Company")["attributed"]


def test_issuer_choice_hcm_via_sec_title_and_elevar_never_rlay_and_san_never_on_a_spac():
    t = "HUTCHMED Announces Submission of US NDA for ORPATHYS plus TAGRISSO in MET-Driven EGFR-Mutated Lung Cancer"
    assert C.normalise_name("HUTCHMED (China) Ltd") == "HUTCHMED"
    assert cls(t, "HCM", "HUTCHMED (China) Ltd")["attributed"] is True
    assert cls(t, "AZN", "ASTRAZENECA PLC")["attributed"] is False
    assert cls("Elevar Therapeutics Announces FDA Approval of Lyrfigtu", "RLAY",
               "Relay Therapeutics, Inc.")["attributed"] is False
    assert cls("Live Oak Acquisition Corp. VI Completes $230,000,000 Initial Public Offering", "SAN",
               "Banco Santander, S.A.")["attributed"] is False


def test_name_normalisation():
    assert C.normalise_name("Eli Lilly and Company") == "Eli Lilly"
    assert C.normalise_name("ELI LILLY & Co") == "ELI LILLY"
    assert C.normalise_name("Merck & Co., Inc.") == "Merck"
    # CRISPR alone is a modality word -> never the distinctive word
    assert "CRISPR" not in C.name_forms("CRSP", "CRISPR Therapeutics AG")


def test_no_ticker_means_attributed_none():
    assert C.classify("FDA Approves First Treatment for MCT8 Deficiency")["attributed"] is None


# ---------------------------------------------------------------------------
# medical gate (§3.4.6)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title,ticker,company,typ", [
    ("FTAI Acquires 27 Boeing 737-700 Aircraft from WestJet", "FTAI", "FTAI Aviation Ltd.", "deal"),
    ("Acme Motors Announces Voluntary Recall of 12,000 Sedans", "ACMM", "Acme Motors Inc.", "safety"),
    ("Burke Bank Prices $50 Million Public Offering of Subordinated Notes", "BRKB", "Burke Bank Corp.", "financing"),
])
def test_medical_gate_drops_non_medical_deals_recalls_and_notes(title, ticker, company, typ):
    r = cls(title, ticker, company, issuer_medical=False)
    assert r["events"] == [] and f"non_medical_event:{typ}" in r["dropped"]


def test_medical_gate_drops_unresolved_financing_and_keeps_a_medical_issuers_offering():
    t = "ADARx Pharmaceuticals Announces Pricing of Upsized $446.3 Million Initial Public Offering"
    assert cls(t)["events"] == []
    e = one(cls("ABC Therapeutics Announces $150 Million Public Offering", "ABCT", "ABC Therapeutics, Inc.",
                issuer_medical=True), "financing")
    assert e["dilutive"] is True


def test_secondary_by_holders_is_not_dilutive():
    e = one(cls("InnovAge Announces Pricing of Secondary Offering of Common Stock by Selling Stockholders", "INNV",
                "InnovAge Holding Corp.", issuer_medical=True), "financing")
    assert e["subtype"] == "secondary_holders" and e["dilutive"] is False
    assert T.event_label(e) == "Secondary by holders (not dilutive)"


def test_satellos_partnership_tail_is_masked_by_the_filing_clause():
    r = cls("Satellos Announces FDA Clearance of IND Application for Forazapadin in FSHD and a Partnership with "
            "FSHD Canada Foundation", "MSLE", "Satellos Bioscience Inc.")
    assert types(r) == ["regulatory_filing"]


def test_medical_words_hit():
    assert C.medical_words_hit("Phase 3 data in wet AMD")
    assert C.medical_words_hit("A new mRNA shot")
    assert not C.medical_words_hit("FTAI Acquires 27 Boeing 737-700 Aircraft from WestJet")


# ---------------------------------------------------------------------------
# one event per type, two types in one title, unknown -> unclassified
# ---------------------------------------------------------------------------
def test_one_event_per_type_per_title():
    assert types(cls("PDUFA Target Action Date Extended to March 2027")) == ["pdufa"]


def test_two_events_in_one_title():
    r = cls("Mirum Pharmaceuticals Announces FDA Approval of Atebrioz and Positive Phase 3 Data for Hepatitis Delta")
    assert types(r) == ["fda_approval", "topline"]
    assert one(r, "topline")["phase"] == "3" and one(r, "topline")["direction"] == "positive"


def test_unknown_is_unclassified_never_guessed():
    r = cls("MediciNova Announces Topline Results from  MN-001-NATG-202 Clinical Trial of MN-001 (Tipelukast)")
    assert r["modality"] == ["unclassified"] and r["areas"] == ["unclassified"]
    assert one(r, "topline")["direction"] == "unknown"


def test_meran_is_mrna_and_adc_prunes_antibody():
    assert cls("Moderna To Present Three Abstracts On Intismeran Autogene At ESMO 2026")["modality"] == ["mrna"]
    assert C.classify("Enhertu (trastuzumab deruxtecan) antibody-drug conjugate data")["modality"] == ["adc"]


def test_antibody_prunes_an_inhibitor_only_small_molecule():
    assert C.classify("Checkpoint inhibitor pembrolizumab data")["modality"] == ["antibody_bispecific"]
    assert C.classify("Oral KRAS inhibitor sotorasib tablet data")["modality"] == ["small_molecule"]


def test_context_adds_modality_and_area_but_never_events():
    r = C.classify("Kodiak Sciences Announces Update", context="Phase 3 met primary endpoints in wet AMD; tarcocimab")
    assert r["events"] == []
    assert r["modality"] == ["antibody_bispecific"] and r["areas"] == ["ophthalmology"]


def test_cue_span_points_at_the_title_text():
    t = "FDA Places Clinical Hold on PQR's Phase 1 Trial"
    e = one(C.classify(t), "clinical_hold")
    a, b = e["cue_span"]
    assert t[a:b] == e["cue"] == "Clinical Hold"


def test_extract_trial_and_phase_helpers():
    assert C.extract_trial("Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints") == "DAYBREAK"
    assert C.extract_trial("Primary Endpoint Met in Phase 3 AZURE-1 Study") == "AZURE-1"
    assert C.extract_trial("results of NCT06556368 were posted") == "NCT06556368"
    assert C.extract_trial("FDA Approves First Treatment for MCT8 Deficiency") is None
    assert C.extract_phase("phase III wet AMD trial met", (0, 1)) == "3"
    assert C.extract_phase("no phase here", (0, 1)) is None
    assert C.direction("met its primary endpoint")[0] == "positive"


# ---------------------------------------------------------------------------
# taxonomy
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ev,high", [
    ({"event_type": "topline", "phase": "3", "direction": "positive"}, True),
    ({"event_type": "topline", "phase": "pivotal", "direction": "negative"}, True),
    ({"event_type": "topline", "phase": "2/3", "direction": "positive"}, True),
    ({"event_type": "topline", "phase": "2", "direction": "positive"}, False),
    ({"event_type": "topline", "phase": "3", "direction": "mixed"}, False),
    ({"event_type": "topline", "phase": "3", "direction": "unknown"}, False),
    ({"event_type": "topline", "phase": None, "direction": "positive"}, False),
    ({"event_type": "fda_approval", "subtype": "novel", "regulator": "FDA"}, True),
    ({"event_type": "fda_approval", "subtype": "tentative", "regulator": "FDA"}, False),
    ({"event_type": "fda_approval", "subtype": "generic", "regulator": "FDA"}, False),
    ({"event_type": "fda_approval", "subtype": "novel", "regulator": None}, False),
    ({"event_type": "fda_crl", "subtype": "crl"}, True),
    ({"event_type": "fda_crl", "subtype": "refuse_to_file"}, True),
    ({"event_type": "fda_crl", "subtype": "withdrawn"}, False),
    ({"event_type": "fda_revoked", "subtype": "revoked", "regulator": "FDA"}, False),
    ({"event_type": "designation", "subtype": "breakthrough_therapy"}, True),
    ({"event_type": "designation", "subtype": "fast_track"}, False),
    ({"event_type": "designation", "subtype": "breakthrough_device"}, False),
    ({"event_type": "clinical_hold", "subtype": "placed"}, True),
    ({"event_type": "clinical_hold", "subtype": "lifted"}, False),
    ({"event_type": "conference_data", "subtype": "upcoming", "direction": "positive", "phase": "3"}, False),
    ({"event_type": "readout_scheduled"}, False), ({"event_type": "adcom", "direction": "positive"}, False),
    ({"event_type": "exus_approval", "regulator": "EMA"}, False), ({"event_type": "financing"}, False),
    ({"event_type": "deal"}, False), ({"event_type": "safety"}, False), ({"event_type": "pdufa"}, False),
    ({"event_type": "trial_milestone", "subtype": "discontinued"}, False),
    ({"event_type": "regulatory_filing", "subtype": "ind_cleared"}, False),
])
def test_is_high_impact_table(ev, high):
    assert T.is_high_impact(ev) is high


def test_high_impact_text_is_built_from_the_table():
    for _k, txt in T.HIGH_IMPACT_TABLE:
        assert txt in T.HIGH_IMPACT_TEXT
    assert set(T.HIGH_IMPACT_TYPES) == {"fda_approval", "fda_crl", "topline", "designation", "clinical_hold"}


def test_type_dir_and_labels():
    kod = {"event_type": "topline", "direction": "positive", "phase": "3"}
    assert T.type_dir(kod) == "topline_positive" and T.event_label(kod) == "Phase 3 topline positive"
    assert T.type_dir({"event_type": "topline"}) == "topline_unknown"
    assert T.event_label({"event_type": "topline", "direction": "unknown"}) == "Topline results (direction not stated)"
    assert T.type_dir({"event_type": "adcom", "direction": "positive"}) == "adcom_positive"
    assert T.type_dir({"event_type": "fda_approval"}) == "fda_approval"
    assert T.event_label({"event_type": "fda_crl", "subtype": "refuse_to_file"}) == "FDA refuse-to-file"
    assert T.event_label({"event_type": "clinical_hold", "subtype": "placed", "partial": True}) == \
        "Partial clinical hold placed"
    assert T.event_label({"event_type": "conference_data", "subtype": "upcoming", "congress": "ESMO"}) == \
        "ESMO data (upcoming)"
    assert T.event_label({"event_type": "fda_revoked"}) == "FDA approval pulled / authorization revoked"
    assert T.event_label({"event_type": "trial_milestone", "subtype": "discontinued"}) == \
        "Trial halted or discontinued"
    assert T.event_label({"event_type": "financing", "subtype": "public", "dilutive": True}) == "Offering (dilution)"


def test_every_event_type_has_a_known_family_and_labels_are_unmeasured():
    fams = {k for k, _l, _e in T.EVENT_FAMILIES}
    assert all(v["family"] in fams for v in T.EVENT_TYPES.values())
    assert T.MEASURED is False and T.SETUP_STATUS == "pending study" and "UNMEASURED" in T.UNMEASURED_NOTE
    assert set(T.MODALITY_PRIORITY) | {"unclassified"} == set(T.MODALITIES)
    assert set(T.AREA_PRIORITY) | {"unclassified"} == set(T.AREAS)
    assert T.AREA_PRIORITY[-1] == "rare_disease"


def test_no_entry_stop_or_target_and_no_bounce_in_the_taxonomy_text():
    import re
    blob = " ".join([T.UNMEASURED_NOTE, T.HIGH_IMPACT_TEXT] + [v["label"] for v in T.EVENT_TYPES.values()])
    assert not re.search(r"bounce|\b(?:entry|stop|target)\b", blob, re.I)
