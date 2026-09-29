"""🧬 Medical catalysts — labels, families, high-impact table (spec §3.2, §3.8).

PURE: no I/O. The ONE definition of "high impact" (`is_high_impact`) — the
board chip and the push gate both read it, and `HIGH_IMPACT_TEXT` (rules panel,
board, push detail) is built from the same table, never retyped.

UNMEASURED — setup: pending study. Nothing here is a buy or sell signal.
"""
from __future__ import annotations

RULES_VERSION = "med-rules-v3"   # v3 = fix round 2 (2026-09-29): approval / CRL / hold / topline precision
MEASURED = False
STATUS = "unmeasured"
SETUP_STATUS = "pending study"
UNMEASURED_NOTE = ("UNMEASURED — nothing here has been measured. Events are classified by fixed "
                   "word rules; moves are what the stock did, not a prediction. "
                   "Setup: pending study. Not a buy or sell signal.")

# (key, label, emoji) in DISPLAY order
EVENT_FAMILIES = (
    ("fda", "FDA decisions", "🏛️"),
    ("trial", "Trial readouts", "🧪"),
    ("conference", "Conference data", "🎤"),
    ("regulatory", "Designations, filings & dates", "🏷️"),
    ("hold", "Holds & safety", "⚠️"),
    ("deal", "Deals", "🤝"),
    ("financing", "Financing — dilution", "💵"),
    ("scheduled", "Scheduled & milestones", "📅"),
)
_FAMILY_EMOJI = {k: e for k, _l, e in EVENT_FAMILIES}


def _et(label: str, family: str) -> dict:
    return {"label": label, "family": family, "emoji": _FAMILY_EMOJI[family]}


EVENT_TYPES = {
    "fda_approval": _et("FDA approval", "fda"),
    "fda_crl": _et("FDA rejection / CRL", "fda"),
    "fda_revoked": _et("FDA approval pulled / revoked", "fda"),
    "adcom": _et("Advisory committee", "fda"),
    "topline": _et("Trial topline", "trial"),
    "conference_data": _et("Conference data", "conference"),
    "designation": _et("Designation", "regulatory"),
    "regulatory_filing": _et("Regulatory filing", "regulatory"),
    "pdufa": _et("PDUFA date", "regulatory"),
    "exus_approval": _et("Ex-US approval", "regulatory"),
    "clinical_hold": _et("Clinical hold", "hold"),
    "safety": _et("Safety", "hold"),
    "deal": _et("Deal", "deal"),
    "financing": _et("Financing (dilution)", "financing"),
    "readout_scheduled": _et("Readout scheduled", "scheduled"),
    "trial_milestone": _et("Trial milestone", "scheduled"),
}

MODALITIES = {"mrna": "mRNA", "gene_editing": "Gene editing", "gene_therapy": "Gene therapy",
              "cell_therapy": "Cell therapy", "rnai_antisense": "RNAi / antisense", "adc": "ADC",
              "antibody_bispecific": "Antibodies & bispecifics", "radiopharma": "Radiopharma",
              "glp1_obesity": "GLP-1 / obesity", "vaccine": "Vaccine", "small_molecule": "Small molecule",
              "medtech_device": "Medtech device", "diagnostics": "Diagnostics", "unclassified": "unclassified"}
MODALITY_PRIORITY = ("mrna", "gene_editing", "gene_therapy", "cell_therapy", "rnai_antisense", "adc",
                     "radiopharma", "antibody_bispecific", "glp1_obesity", "vaccine", "small_molecule",
                     "medtech_device", "diagnostics")
AREAS = {"oncology": "oncology", "neurology": "neurology", "rare_disease": "rare disease",
         "immunology": "immunology", "cardio_metabolic": "cardio-metabolic",
         "ophthalmology": "ophthalmology", "infectious_disease": "infectious disease",
         "unclassified": "unclassified"}
# rare_disease LAST: an orphan cancer drug is oncology first
AREA_PRIORITY = ("oncology", "ophthalmology", "neurology", "infectious_disease", "cardio_metabolic",
                 "immunology", "rare_disease")
PHASE3_CLASS = frozenset({"3", "2/3", "pivotal"})

# A fact about the meeting, not a guess (spec §3.4.4). ASH/EHA/EASL/AASLD: no area.
CONGRESS_AREA = {
    "ESMO": "oncology", "ASCO": "oncology", "AACR": "oncology", "SABCS": "oncology", "SITC": "oncology",
    "AAN": "neurology", "AAIC": "neurology", "CTAD": "neurology",
    "AAO": "ophthalmology", "Euretina": "ophthalmology", "ARVO": "ophthalmology",
    "ADA": "cardio_metabolic", "EASD": "cardio_metabolic", "ObesityWeek": "cardio_metabolic",
    "ACC": "cardio_metabolic", "AHA": "cardio_metabolic", "ESC": "cardio_metabolic",
    "IDWeek": "infectious_disease", "ESCMID": "infectious_disease",
    "ACR": "immunology", "EULAR": "immunology", "AAD": "immunology", "EADV": "immunology",
}

# ── §3.8 high-impact table: (event_type, human text). The predicate per row
#    lives in is_high_impact; HIGH_IMPACT_TEXT joins these texts. ─────────────
FDA_APPROVAL_LOW_SUBTYPES = frozenset({"tentative", "generic"})
FDA_CRL_HIGH_SUBTYPES = frozenset({"crl", "refuse_to_file", "rejection"})
TOPLINE_HIGH_DIRECTIONS = frozenset({"positive", "negative"})
DESIGNATION_HIGH_SUBTYPES = frozenset({"breakthrough_therapy"})
HOLD_HIGH_SUBTYPES = frozenset({"placed"})

HIGH_IMPACT_TABLE = (
    ("fda_approval", "FDA approval (not tentative or generic)"),
    ("fda_crl", "FDA complete response letter, refuse-to-file or rejection (not a withdrawn application)"),
    ("topline", "Phase 3 / Phase 2/3 / pivotal topline positive or negative (never mixed or undirected)"),
    ("designation", "Breakthrough Therapy designation"),
    ("clinical_hold", "clinical hold placed (incl. partial)"),
)
HIGH_IMPACT_TYPES = frozenset(k for k, _t in HIGH_IMPACT_TABLE)
HIGH_IMPACT_TEXT = "High impact = " + "; ".join(t for _k, t in HIGH_IMPACT_TABLE)


def _phase(ev: dict) -> str:
    p = ev.get("phase")
    return "" if p is None else str(p)


def is_high_impact(ev: dict) -> bool:
    """§3.8 — the ONLY definition (board chip + push gate)."""
    t, s = ev.get("event_type"), ev.get("subtype")
    if t == "fda_approval":
        return s not in FDA_APPROVAL_LOW_SUBTYPES and ev.get("regulator") == "FDA"
    if t == "fda_crl":
        return s in FDA_CRL_HIGH_SUBTYPES
    if t == "topline":
        return _phase(ev) in PHASE3_CLASS and ev.get("direction") in TOPLINE_HIGH_DIRECTIONS
    if t == "designation":
        return s in DESIGNATION_HIGH_SUBTYPES
    if t == "clinical_hold":
        return s in HOLD_HIGH_SUBTYPES
    return False


def type_dir(ev: dict) -> str:
    """'topline_positive' … 'topline_unknown', 'adcom_positive' …; else the bare type."""
    t = ev.get("event_type") or "unknown"
    if t in ("topline", "adcom"):
        return f"{t}_{ev.get('direction') or 'unknown'}"
    return t


_APPROVAL_LABELS = {"novel": "FDA approval", "accelerated": "FDA accelerated approval",
                    "tentative": "FDA tentative approval", "generic": "FDA generic / biosimilar approval",
                    "eua": "FDA emergency use authorization", "device_clearance": "FDA device clearance",
                    "label_expansion": "FDA label expansion", "updated_vaccine": "FDA approval (updated vaccine)"}
_CRL_LABELS = {"crl": "FDA complete response letter", "refuse_to_file": "FDA refuse-to-file",
               "rejection": "FDA rejection", "withdrawn": "Application withdrawn"}
_DESIG_LABELS = {"breakthrough_therapy": "Breakthrough Therapy designation",
                 "breakthrough_device": "Breakthrough Device designation",
                 "fast_track": "Fast Track designation", "orphan": "Orphan Drug designation",
                 "rmat": "RMAT designation", "priority_review": "Priority Review",
                 "rare_pediatric": "Rare Pediatric Disease designation", "prime": "EMA PRIME designation"}
_FILING_LABELS = {"submitted": "Application submitted", "accepted": "Application accepted for review",
                  "ind_cleared": "IND cleared"}
_PDUFA_LABELS = {"set": "PDUFA date set", "extended": "PDUFA date extended", "upcoming": "PDUFA date upcoming"}
_MILESTONE_LABELS = {"first_patient": "First patient dosed", "enrollment_complete": "Enrollment complete",
                     "initiated": "Trial initiated", "discontinued": "Trial halted or discontinued"}
_DEAL_LABELS = {"mna": "M&A", "licensing": "Licensing deal", "partnership": "Partnership",
                "milestone": "Milestone payment"}


def event_label(ev: dict) -> str:
    t, s = ev.get("event_type"), ev.get("subtype")
    if t == "topline":
        d = ev.get("direction")
        if d in (None, "unknown"):
            return "Topline results (direction not stated)"
        p = _phase(ev)
        head = "Pivotal topline" if p == "pivotal" else (f"Phase {p} topline" if p else "Topline")
        return f"{head} {d}"
    if t == "fda_approval":
        return _APPROVAL_LABELS.get(s, "FDA approval")
    if t == "fda_crl":
        return _CRL_LABELS.get(s, "FDA complete response letter")
    if t == "fda_revoked":
        return "FDA approval pulled / authorization revoked"
    if t == "exus_approval":
        reg = ev.get("regulator")
        return f"{reg} approval" if reg else "Ex-US approval"
    if t == "designation":
        return _DESIG_LABELS.get(s, "Designation")
    if t == "regulatory_filing":
        return _FILING_LABELS.get(s, "Regulatory filing")
    if t == "pdufa":
        return _PDUFA_LABELS.get(s, "PDUFA date")
    if t == "adcom":
        d = ev.get("direction")
        return f"Advisory committee vote {d}" if d in ("positive", "negative") else "Advisory committee meeting"
    if t == "conference_data":
        who = ev.get("congress") or "Conference"
        when = "upcoming" if s == "upcoming" else "presented"
        return f"{who} data ({when})"
    if t == "readout_scheduled":
        return "Readout scheduled"
    if t == "trial_milestone":
        return _MILESTONE_LABELS.get(s, "Trial milestone")
    if t == "clinical_hold":
        if s == "lifted":
            return "Clinical hold lifted"
        if s == "response":
            return "Response to clinical hold submitted"
        return "Partial clinical hold placed" if ev.get("partial") else "Clinical hold placed"
    if t == "safety":
        return "Safety event"
    if t == "deal":
        return _DEAL_LABELS.get(s, "Deal")
    if t == "financing":
        if s == "secondary_holders" or ev.get("dilutive") is False:
            return "Secondary by holders (not dilutive)"
        return "Offering (dilution)"
    return (EVENT_TYPES.get(t) or {}).get("label") or str(t)
