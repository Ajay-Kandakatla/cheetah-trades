"""🧬 Medical headline classifier — deterministic word rules (spec §3.3–§3.4).

PURE: stdlib `re` only, no I/O. A port of the reference harness
`scratchpad/medcat_rev/rules_v2_final.py` (92/92 cases) + `attr.py` (18/18),
plus the v1 tables the harness does not carry (fda_approval subtypes, exus,
safety, deal, financing, modality, area, trial names).

Evaluation order per title (fixed; each step sees what the previous left):
  1 roundup -> no events        2 commentary -> no events
  3 merge_only flag (price story: events may MERGE, never CREATE)
  4 unrelated-approval spans masked      5 background pre-pass
  6 precedence ladder (crl -> revoked -> hold -> filing -> pdufa -> adcom ->
    designation -> conference -> scheduled -> milestone -> approval -> exus)
  7 topline + direction + phase (skipped when a trial_milestone fired)
  8 discontinued fallback   9 safety / deal / financing   10 medical gate
 11 attribution            12 modality / area over title + context

Unknown is never guessed: no modality / area hit -> ["unclassified"].
Masking replaces text with spaces so every offset (cue_span) stays valid.

UNMEASURED — setup: pending study.
"""
from __future__ import annotations

import re
from typing import Optional

from .taxonomy import AREA_PRIORITY, CONGRESS_AREA, MODALITY_PRIORITY, RULES_VERSION

I = re.I
GAP = r"[^;!?]"
CLAUSE_END = re.compile(r";|!|\?|\s[—–|]\s|\s-\s|:\s|\b(?:but|while|whereas|however)\b", I)


def _cs(s: str) -> str:
    """A case-sensitive inline group."""
    return "(?-i:" + s + ")"


def cend(t: str, p: int) -> int:
    m = CLAUSE_END.search(t, p)
    return m.start() if m else len(t)


def cstart(t: str, p: int) -> int:
    last = 0
    for m in CLAUSE_END.finditer(t):
        if m.end() <= p:
            last = m.end()
        else:
            break
    return last


def mask(t: str, a: int, b: int) -> str:
    return t[:a] + " " * (b - a) + t[b:]


# ---------------------------------------------------------------------------
# 3.4.1 pre-filters
# ---------------------------------------------------------------------------
ROUNDUP = re.compile(
    r"^\d+\s+(?:health ?care|biotech|pharma|medical|s&p ?500|nasdaq)?\s*stocks?\b"
    r"|stocks? (?:that )?(?:explain|moving|making waves)|(?:top|biggest) (?:gainers|losers|movers)"
    r"|(?:and|&) (?:other|more) (?:big )?stocks|stocks? (?:moving|to watch|to buy)|sector update"
    r"|^round-?up\b|^recap\b|^week in review|\bweekly (?:roundup|recap)"
    r"|shareholders? who lost|investors? who lost|class action|securities fraud|deadline alert|investor alert"
    r"|\b(?:rosen|pomerantz|bragar|glancy|faruqi|bronstein|wolf haldenstein|kessler topaz|levi & korsinsky)\b", I)
# fix round (critic grading 2026-09-29): valuation pieces "May Be 14% Undervalued
# On FDA Approval", "Could Be 50% Below Fair Value On Phase 3 … Data",
# "Doesn't Break the Bull Case" created events -> under/overvalued, fair value,
# bull/bear case join the valuation words (each pinned by a fixture row).
COMMENT = re.compile(
    r"^(?:why |what |how |is |should |can |will |here'?s |q&a:|opinion:|analysis:|inside the |this )"
    r"|^a look at |\?\s*$|\b(?:transcript|slideshow)\s*$"
    r"|\b(?:comments? on|statement on|reacts? to|responds? to)\b"
    r"|\b(?:valuation|options flow|price target|initiates coverage|stock forecast|anniversary"
    r"|under-?valued|over-?valued|fully valued|fair value|bull case|bear case)\b", I)
PV = (r"pops?|popping|soar(?:s|ed|ing)?|jump(?:s|ed|ing)?|surg(?:es|ed|ing)|sinks?|sank|falls?|falling|fell"
      r"|slid(?:es|ing)?|slides?|plung(?:es|ed|ing)|rocket(?:s|ed|ing)?|skyrocket(?:s|ed|ing)?|climb(?:s|ed|ing)?"
      r"|rall(?:y|ies|ied|ying)|tumbl(?:es|ed|ing)|slip(?:s|ped|ping)?|spik(?:es|ed|ing)|crater(?:s|ed|ing)?"
      r"|plummet(?:s|ed|ing)?|tank(?:s|ed|ing)?|catapult(?:s|ed|ing)?|edg(?:es|ed) (?:higher|lower|up|down)"
      r"|trad(?:es|ing) (?:higher|lower)|rises?|rising|rose|dives?|dived|leaps?|leapt|zooms?|explodes?"
      r"|ripping|rips")
M1 = re.compile(r"\b(?:stock|shares?)\b" + GAP + r"{0,15}\b(?:" + PV + r")\b", I)
M3 = re.compile(r"\b(?:" + PV + r")\b\s+(?:by\s+|nearly\s+|more than\s+|over\s+)?[+-]?\d+(?:\.\d+)?\s?(?:%|x\b)"
                r"|\b(?:up|down)\s+(?:nearly\s+|more than\s+)?\d+(?:\.\d+)?\s?%|\bjust (?:got|won|received|hit)\b", I)
UNREL = re.compile(r"\b(?:shareholders?|stockholders?|board|nasdaq|nyse|court|hsr|antitrust|listing|merger)\b"
                   + GAP + r"{0,25}\bapprov\w*", I)
INTENT_B = re.compile(r"\b(?:eyes|plans? to|planned|planning|aims? to|expects?|expected to|anticipates?|may|could"
                      r"|might|hopes? to|considering|weighs|would|intends? to|to seek|preparing to)\b"
                      + GAP + r"{0,25}$", I)
INTENT_A = re.compile(r"^" + GAP + r"{0,15}\b(?:planned|expected|anticipated|targeted)\b", I)

# ---------------------------------------------------------------------------
# 3.4.2 precedence ladder
# ---------------------------------------------------------------------------
REG = r"\b(?:NDA|BLA|sNDA|sBLA|MAA)\b"
# fix round: "Charles River Laboratories (CRL) Stock …" — the CS CRL cue never
# fires on a parenthesised ticker / exchange notation.
_CRL_TICKER = re.compile(r"\(\s*(?:(?:NYSE|NASDAQ|Nasdaq|NYSE American|OTC)\s*:\s*)?$|\b(?:NYSE|NASDAQ|Nasdaq)\s*:\s*$")
_IND = _cs(r"\bIND\b") + r"|investigational new drug"
_IND_POLICY = r"\b(?:pilot|guidance|policy|framework)\b"
LADDER = [
    ("fda_crl", True, [
        (r"complete response letter", "crl"), (_cs(r"\bCRL\b"), "crl"),
        (r"refus(?:e|es|ed|al) to (?:file|review)|refusal[- ]to[- ]file", "refuse_to_file"),
        (r"not approvable", "rejection"),
        (r"\bFDA\b" + GAP + r"{0,30}\b(?:rejects?|rejected|declines? to approve|denie[sd])\b", "rejection"),
        (r"\bwithdr[ae]w\w*\b" + GAP + r"{0,30}" + _cs(REG), "withdrawn")]),
    ("fda_revoked", True, [
        (r"\b(?:pulls?|pulled|revok\w+|rescind\w*|suspend\w*)\s+(?:\w+\s+){0,2}?(?:approval|clearance"
         r"|authori[sz]ation|" + _cs(r"EUA") + r")", "revoked")]),
    ("clinical_hold", True, [
        (r"(?:lift(?:s|ed)?|remov(?:es|ed)|release[sd]?|resolv(?:es|ed))\b" + GAP + r"{0,30}(?:partial\s+)?"
         r"clinical hold|clinical hold" + GAP + r"{0,20}\b(?:lifted|removed|released)", "lifted"),
        (r"(?:partial\s+)?clinical hold", "placed")]),
    ("regulatory_filing", True, [
        (r"(?:submi(?:ssion|ts?|tted)|files?|filed|filing)\b" + GAP + r"{0,40}(?:" + _cs(REG)
         + r"|(?:new drug|biologics license|marketing authori[sz]ation) application)", "submitted"),
        (_cs(REG) + GAP + r"{0,30}\b(?:accepted|acceptance|under review)\b", "accepted"),
        (r"\baccept\w*\b" + GAP + r"{0,30}" + _cs(REG), "accepted"),
        (r"\b(?:files?|filed|filing|submit\w*|appl(?:y|ies|ied|ying))\s+(?:for\s+)?(?:U\.?S\.?\s+)?(?:FDA\s+)?"
         r"approval", "submitted"),
        (r"\bseek(?:s|ing)?\b" + GAP + r"{0,25}\bFDA\b" + GAP + r"{0,10}approval", "submitted"),
        (r"(?:" + _IND + r")" + GAP + r"{0,40}\b(?:clear\w*|approv\w*|accept\w*|allow\w*|effective)\b(?!" + GAP
         + r"{0,30}" + _IND_POLICY + r")|\b(?:clear\w*|approv\w*|allow\w*)\b" + GAP + r"{0,40}(?:" + _IND
         + r")(?!" + GAP + r"{0,30}" + _IND_POLICY + r")", "ind_cleared"),
        # fix round (critic grading: "Prime Medicine Gets FDA Green Light for Gene
        # Editing Study" was an approval): a go-ahead FOR A STUDY is a trial
        # clearance, not a marketing approval.
        (r"\b(?:green light|go-ahead|nod|clear(?:s|ed|ance)?|allow\w*)\b" + GAP + r"{0,12}\b(?:for|to)\b" + GAP
         + r"{0,30}\b(?:stud(?:y|ies)|trials?|clinical testing)\b", "ind_cleared")]),
    ("pdufa", True, [
        (_cs(r"\bPDUFA\b") + r"|target action date|goal date|approval decision (?:expected|anticipated|date)",
         "date")]),
    ("adcom", True, [(r"advisory committee|" + _cs(r"\b(?:AdCom|ODAC|VRBPAC)\b"), "meeting")]),
    ("designation", False, [
        (r"breakthrough therapy", "breakthrough_therapy"), (r"breakthrough device", "breakthrough_device"),
        (r"fast[- ]track", "fast_track"), (r"orphan (?:drug )?(?:designation|status)", "orphan"),
        (_cs(r"\bRMAT\b") + r"|regenerative medicine advanced therapy", "rmat"),
        (r"priority review", "priority_review"), (r"rare pediatric disease designation", "rare_pediatric"),
        (_cs(r"\bPRIME\b") + r"(?=" + GAP + r"{0,20}\b(?:designation|scheme|eligibility)\b)", "prime")]),
    ("conference_data", "clause", None),
    ("readout_scheduled", True, [
        (r"\bto (?:present|report|announce|host|share|release)\b" + GAP + r"{0,80}\b(?:top[- ]?line|results|data"
         r"|readout)", "scheduled"),
        (r"(?:results|data|readout|topline)\s+(?:are |is )?(?:due|expected|scheduled|anticipated)", "scheduled"),
        (r"\b(?:top[- ]?line|results|data|readout)\b" + GAP + r"{0,80}\b(?:are|is|were)\s+(?:due|expected"
         r"|scheduled|anticipated|slated|set)\b", "scheduled"),
        (r"webcast to (?:report|present)|investor (?:call|event) to (?:share|discuss)", "scheduled"),
        (r"\b(?:expects?|anticipates?|guides? to|on track to (?:report|announce))\b" + GAP + r"{0,40}\b(?:top[- ]?"
         r"line|results|data|readout)", "scheduled")]),
    ("trial_milestone", True, [
        (r"first (?:patient|participant|subject)s? (?:dosed|enrolled|randomi[sz]ed|treated)", "first_patient"),
        (r"(?:completes?|completed|completion of) (?:patient )?(?:enrollment|enrolment|dosing|recruitment)",
         "enrollment_complete"),
        (r"\b(?:initiat(?:es|ed|ion|ing)|start(?:s|ed|ing)?|launch(?:es|ed|ing)?|begins?|began|commenc\w+)\b"
         + GAP + r"{0,40}\b(?:phase|trial|study|program)\b", "initiated")]),
    ("fda_approval", False, [
        (r"\bFDA\b\W+(?:[\w'\u2019.-]+\s+){0,2}?(?:approv(?:es|ed|al)|grants? (?:accelerated |full |traditional )?"
         r"approval|clear(?:s|ed|ance)|authori[sz](?:es|ed|ation)|issues emergency use authori[sz]ation)\b", "A1"),
        (r"\bapprov(?:al|ed) (?:by|from) (?:the )?(?:U\.?S\.? )?FDA\b", "A3"),
        (r"\b(?:snags?|wins?|won|gets?|got|receives?|lands?|earns?)\s+(?:an?\s+)?(?:U\.?S\.?\s+)?FDA\s+(?:nod"
         r"|green light|go-ahead)|\bFDA\s+(?:nod|green light|go-ahead)s?\s+(?:for|to)\b", "A4"),
        (r"\b(?:receives?|received|wins?|won|gets?|got|gains?|secures?|lands?|obtains?|announces?|earns?)\b"
         + GAP + r"{0,30}(?:U\.?S\.?\s+)?FDA\b" + GAP + r"{0,20}\b(?:approval|clearance|authori[sz]ation)\b", "A2"),
        # CS 510(k) / De Novo / PMA approval — only with a clearance / grant word
        # ("submits 510(k)" is a filing, never an approval)
        (r"\b(?:receives?|received|granted|grants?|obtains?|secures?|wins?|won|gets?|got)\b" + GAP + r"{0,30}"
         + _cs(r"(?:510\(k\)|\bDe Novo\b)") + r"|" + _cs(r"(?:510\(k\)|\bDe Novo\b)") + GAP
         + r"{0,20}\b(?:clearance|cleared|authori[sz]ation|granted)\b|" + _cs(r"\bPMA\b") + r"\s+approval", "DEV")]),
]
_APPROVAL_WORD = re.compile(r"approv\w*|clear\w*|authori\w*|nod|green light|go-ahead|510\(k\)|De Novo", I)

CONGRESS_NAMED = (r"\b(?:UEG Week|DDW|WCLC|ERS|ATS|ASGCT|ESGCT|CROI|ISTH|EAN|ECTRIMS|AES|ESMO|ASCO|AACR|SABCS|SITC|AAN"
                  r"|AAIC|CTAD|AAO|Euretina|ARVO|ADA|EASD|ObesityWeek|ACC|AHA|ESC|IDWeek|ESCMID|ACR|EULAR|AAD|EADV"
                  r"|ASH|EHA|EASL|AASLD)\b")
GENERIC_MEET = r"\b(?:congress|conference|symposium|annual meeting|scientific sessions)\b"
SCI = r"\b(?:present\w*|data|abstracts?|late[- ]breaking|posters?|oral presentation|results|slot)\b"
SCI_DATA = r"\b(?:data|abstracts?|late[- ]breaking|posters?|oral presentation|results|slot)\b"
INVESTOR = re.compile(
    r"\b(?:conference call|financial results|quarter(?:ly)?|fiscal|earnings|small-cap|virtual conference|investor"
    r"|investment|fireside|healthcare conference|Jefferies|Wainwright|Cantor|Piper|Stifel|Leerink|Guggenheim"
    r"|Evercore|Morgan Stanley|Goldman|J\.?P\.? ?Morgan|Cowen|Oppenheimer|Truist|BofA|Citi|Barclays|UBS|Needham"
    r"|Canaccord|Chardan|Baird|RBC|Mizuho|Wells Fargo|LifeSci|Ladenburg|Roth)\b", I)
PRES_SYMP = r"\b(?:presidential symposium|plenary (?:session|slot)|late[- ]breaking (?:abstract|session|oral))\b"
_CONGRESS_CS = re.compile(r"(?-i:" + CONGRESS_NAMED + r")")
PENDING_B = re.compile(r"\b(?:path|road|journey|race|push|bid|quest|hopes?|chance|odds|potential|possible|pending"
                       r"|seek\w*|towards?|path to|pursu\w*|support\w*|enabl\w*|ahead of|await\w*|expected"
                       r"|anticipated|could|may|if)\b" + GAP + r"{0,20}$|\bto\s+(?:U\.?S\.?\s+)?(?:FDA\s+)?$", I)
PENDING_A = re.compile(r"^\W*(?:\w+\W+){0,1}?(?:decision|date|expected|anticipated|pathway|path|process"
                       r"|application|submission|filing|request|timeline|package)\b", I)
BACKGROUND = re.compile(r"\b(?:after|following|based on|on the back of|supported by|building on|backed by"
                        r"|on the strength of)\b", I)
HEAD = [r"\bFDA\b" + GAP + r"{0,40}\b(?:approv(?:es|ed|al)|grants?|clear(?:s|ed|ance)|nod)",
        r"(?:receives?|wins?|won|gets?|got|snags?|lands?|secures?)\b" + GAP + r"{0,30}FDA",
        r"complete response|refus", r"designation",
        r"acquire|acquisition|merger|licens|collaboration|partnership|milestone payment|offering|placement",
        r"initiat\w*|first (?:patient|participant)|enrollment"]

# ── 3.4.2-D direction ──────────────────────────────────────────────────────
SECMISS = [re.compile(r"\b(?:key |important |main )?secondary (?:efficacy )?endpoints?\b" + GAP
                      + r"{0,20}\b(?:not (?:met|achieved|reached)|missed|failed)\b", I),
           re.compile(r"\b(?:miss(?:es|ed)?|fail(?:s|ed)? to (?:meet|hit|achieve)|did not (?:meet|hit|achieve)"
                      r"|not (?:meet|hit|achieve))\b" + GAP + r"{0,30}\bsecondary\b" + GAP + r"{0,20}endpoints?", I)]
NEG = [r"\b(?:did not|didn['’]t|does not|doesn['’]t|failed to|fails to|fail to|failing to|not|unable to)\s+"
       r"(?:meet|achieve|reach|show|demonstrate|hit)\b",
       r"\bmiss(?:es|ed)?\b" + GAP + r"{0,20}\bprimary\b" + GAP + r"{0,20}endpoints?",
       r"\bprimary (?:efficacy )?endpoints?\s+(?:was |were )?not\s+(?:met|achieved|reached)",
       r"\b(?:not|no|lack of|without)\s+(?:a\s+)?statistically significant", r"\bfutility\b",
       r"\b(?:trial|study)\s+(?:fail(?:s|ed)?|failure)\b", r"\bfail(?:s|ed)?\b" + GAP + r"{0,20}\b(?:trial|study)\b",
       r"\bsetback\b", r"\bthrew in the towel\b", r"\bnegative (?:top[- ]?line|results|data|outcome)\b",
       r"\bfell short of\b" + GAP + r"{0,20}\b(?:primary|endpoint)"]
# fix round (critic grading: KYTX "Reports Positive One-Year Data Demonstrating
# Durable Clinical Responses" came out undirected): up to two words may sit
# between "positive" and the data noun ("Positive One-Year Data", "Positive
# Long-Term Results").
# fix round (regrade: "Brelovitug Meets Phase 3 Primary Endpoint" came out
# undirected): an optional phase token may sit before "primary".
_PH_OPT = r"(?:phase\s*(?:\d|i{1,3}|iv)\w*(?:/\d\w*)?\s+)?"
POS = [r"\bmet (?:its |the |both |all |key )?" + _PH_OPT + r"(?:co-)?primary(?: and key secondary)? (?:efficacy )?endpoints?",
       r"\bmeets? (?:its |the |both |all )?" + _PH_OPT + r"(?:co-)?primary (?:efficacy )?endpoints?",
       r"\bprimary (?:efficacy )?endpoints? (?:was |were )?(?:met|achieved)",
       r"\bhits? (?:the |its |both |all )?(?:co-)?primary (?:efficacy )?endpoints?",
       r"\bachiev(?:ed|es) (?:statistical significance|(?:the|its) primary (?:efficacy )?endpoint)",
       r"\bstatistically significant", r"\bclear(?:s|ed)? (?:the |its |both |all |key )*(?:co-)?(?:primary )?endpoints?",
       r"\bpositive (?:[\w-]+ ){0,2}?(?:top[- ]?line|phase|pivotal|results|data|outcome|readout|study)",
       r"\bnon-?inferior(?:ity)?", r"\bsuperior(?:ity)? (?:to|over|vs)",
       r"\bpass(?:es|ed)? (?:a |the )?(?:key |pivotal )?(?:trial|study)",
       r"\btrial win\b|\bwins?\b" + GAP + r"{0,20}\btrial\b"]
STOP = [r"\bdiscontinu\w*\b" + GAP + r"{0,30}\b(?:trial|study|program|development)\b",
        r"\bterminat\w*\b" + GAP + r"{0,20}\b(?:trial|study|program)\b",
        r"\bhalt(?:s|ed)?\b" + GAP + r"{0,30}\b(?:trial|study|program)\b"]
PH = r"phase\s*(?:\d|i{1,3}|iv)\w*(?:/\d\w*)?"
TOPCUE = [r"top[- ]?line", r"primary (?:efficacy )?endpoints?",
          r"\b" + PH + r"\b" + GAP + r"{0,60}\b(?:results?|data|readout)\b",
          r"\b(?:results?|data|readout)\b" + GAP + r"{0,60}\b" + PH]
# fix round (critic grading: MRK "Pivotal Phase 2b/3" came out Phase 2): the
# seamless 2b/3 and 2a/3 designs are Phase 2/3.
PHASE_TOK = re.compile(r"\bphase\s*(2b/3|2a/3|1/2|2/3|1b/2|1b|1a|2a|2b|3a|3b|iii|ii|iv|i|1|2|3|4)\b"
                       r"|\b(pivotal|registrational)\b", I)
PH_NORM = {"iii": "3", "ii": "2", "i": "1", "iv": "4", "2b": "2", "2a": "2", "3b": "3", "3a": "3", "1b": "1",
           "1a": "1", "1b/2": "1/2", "2b/3": "2/3", "2a/3": "2/3"}
_ENABLING = re.compile(r"[\s-]*(?:enabling|ready)\b", I)
FUTURE_PH = re.compile(r"\b(?:plan\w*|start\w*|initiat\w*|advanc\w*|launch\w*|begin\w*|begun|mov\w* (?:in)?to"
                       r"|progress\w* (?:in)?to|enter\w*|toward\w*|next|upcoming|future)\b" + GAP + r"{0,25}$", I)

# ── exus / safety / deal / financing (v1 tables) ───────────────────────────
EXUS_REGULATORS = (("EMA", r"\bEMA\b"), ("European Commission", r"European Commission"), ("CHMP", r"\bCHMP\b"),
                   ("MHRA", r"\bMHRA\b"), ("Health Canada", r"Health Canada"), ("PMDA", r"\bPMDA\b"),
                   ("NMPA", r"\bNMPA\b"), ("TGA", r"\bTGA\b"), ("Swissmedic", r"Swissmedic"),
                   ("ANVISA", r"\bANVISA\b"), ("Japan", r"\bJapan(?:ese)?\b"), ("China", r"\bChina\b"),
                   ("EU", r"\bEU\b|\bEurope(?:an)?\b"))
EXUS_CUE = r"\bapprov(?:al|es|ed)\b|positive opinion|marketing authori[sz]ation"
SAFETY = r"(?:patient|participant) deaths?|boxed warning|safety (?:signal|concern|event|issue)s?" \
         r"|paus(?:es|ed) (?:dosing|enrollment|the (?:trial|study))|(?:voluntary )?recall|serious adverse"
DEAL = (("mna", r"\bacquire[sd]?\b|acquisition of|to acquire|buyout|\bmerger\b|merge with|tender offer|takeover"),
        ("licensing", r"licens(?:e|ing) (?:agreement|deal)|in-licens\w*|exclusive license"),
        ("partnership", r"collaboration(?! revenue)|partnership|partners with|strategic alliance"),
        ("milestone", r"milestone payment|\bupfront\b"))
FINANCING = (("secondary_holders", r"secondary offering\b.{0,60}selling (?:stock|share)holders"),
             ("ipo", r"initial public offering|" + _cs(r"\bIPO\b")),
             ("registered_direct", r"registered direct"),
             ("private_placement", r"private placement|" + _cs(r"\bPIPE\b")),
             ("atm", r"at-the-market|" + _cs(r"\bATM\b") + r" program"),
             ("convertible", r"convertible (?:senior )?notes"),
             ("public", r"public offering|underwritten offering|equity offering|pricing of|prices? \$|upsized"
                        r"|shelf registration"))

# ---------------------------------------------------------------------------
# 3.4.6 medical gate
# ---------------------------------------------------------------------------
MEDICAL_WORDS = re.compile(
    r"\b(?:FDA|EMA|CHMP|clinical|trials?|phase\s*\d|patients?|therap\w+|drugs?|vaccines?|biotech\w*|pharma\w*"
    r"|medic\w+|disease|oncolog\w*|cancer|tumou?r|antibod\w+|genes?|diagnos\w+|surgical|biolog\w+|molecule"
    r"|pipeline|orphan|(?-i:IND|NDA|BLA))\b", I)
GATED_TYPES = frozenset({"deal", "financing", "safety", "trial_milestone"})

# ---------------------------------------------------------------------------
# 3.4.4 modality / area
# ---------------------------------------------------------------------------
MODALITY_RX = {
    "mrna": _cs(r"\bmRNA\b") + r"|messenger RNA|\b\w+meran\b|" + _cs(r"\bmRNA-\d+") + r"|individuali[sz]ed neoantigen therapy",
    "gene_editing": _cs(r"\bCRISPR\b") + r"|gene[- ]edit\w*|base edit\w*|prime edit\w*|" + _cs(r"\bCas(?:9|12)\w*")
                    + r"|in vivo edit\w*",
    "gene_therapy": r"gene therap(?:y|ies)|" + _cs(r"\bAAV\d*\b") + r"|adeno-associated|lentivir\w*|\b\w+vec\b|gene transfer",
    "cell_therapy": _cs(r"\b(?:CAR[- ]?T|CAR[- ]?NK|TCR[- ]?T|TIL|iPSC)\b") + r"|cell therap(?:y|ies)|stem cell"
                    r"|allogeneic|autologous|\b\w+leucel\b|\b\w+temcel\b",
    "rnai_antisense": _cs(r"\b(?:siRNA|RNAi|ASO)\b") + r"|antisense|\b\w+siran\b|\b\w+rsen\b",
    "adc": _cs(r"\bADCs?\b") + r"|antibody[- ]drug conjugates?|\b\w+(?:vedotin|deruxtecan|govitecan|mafodotin"
                              r"|ozogamicin|tesirine)\b",
    "antibody_bispecific": r"bispecific|monoclonal antibod\w+|T[- ]cell engager|" + _cs(r"\bBiTE\b")
                           + r"|\b\w+mab\b|\b\w+tug\b|\b\w+bart\b|\b\w+mig\b|\b\w{4,}fusp\b|fusion protein|\bantibod(?:y|ies)\b",
    "radiopharma": r"radioligand|radiopharmaceutical|radioconjugate|(?:\bLu|lutetium)[- ]?177|177Lu"
                   r"|(?:\bAc|actinium)[- ]?225|225Ac",
    "glp1_obesity": _cs(r"\b(?:GLP-?1|GIP)\b") + r"|amylin|obesity|overweight|weight (?:loss|management|reduction)"
                    r"|\b\w+(?:glutide|lintide)\b|tirzepatide|orforglipron|retatrutide|incretin",
    "vaccine": r"\bvaccines?\b|vaccination|immuni[sz]ation|\b(?:flu|covid(?:-19)?|rsv) shots?\b|\b\w+vax\b",
    "small_molecule": r"small[- ]molecule|\boral\b.{0,20}(?:inhibitor|tablet|pill|capsule)|\btablets?\b|\bpills?\b"
                      r"|\bcapsules?\b|\b\w+(?:tinib|ciclib|rafenib|lisib|parib|degib)\b|\binhibitors?\b|\bdegraders?\b|"
                      + _cs(r"\bPROTAC\b"),
    "medtech_device": _cs(r"510\(k\)|\bDe Novo\b|\bPMA\b") + r"|\bdevices?\b|\bimplant(?:able|s)?\b|catheter"
                      r"|\bstents?\b|\bpumps?\b|pacemaker|neurostimulat\w*|surgical (?:system|robot)|wearable",
    "diagnostics": r"\bdiagnostics?\b|\bassays?\b|companion diagnostic|" + _cs(r"\b(?:CDx|MRD)\b")
                   + r"|liquid biopsy|\b(?:blood|screening|genetic) tests?\b|imaging agent",
}
_SM_INHIBITOR_ONLY = re.compile(r"\binhibitors?\b", I)
# Fix vs the v1 table: `Parkinson\W?s` missed "Parkinson Disease" (#38) -> the
# possessive is optional for every eponym.
AREA_RX = {
    "oncology": r"\bcancers?\b|oncolog\w*|\btumou?rs?\b|carcinoma|lymphoma|leuk(?:a)?emia|myeloma|melanoma|sarcoma"
                r"|glioblastoma|metasta\w+|cholangiocarcinoma|myelodysplastic|neoplasm|"
                + _cs(r"\b(?:NSCLC|SCLC|HER2|EGFR|KRAS)\b"),
    "neurology": r"Parkinson(?:\W?s)?\b|Alzheimer(?:\W?s)?\b|amyotrophic|epilep\w+|seizures?|migraine"
                 r"|multiple sclerosis|Huntington(?:\W?s)?\b|schizophrenia|depress(?:ion|ive)|bipolar|neuropath\w+"
                 r"|spinal muscular atrophy|Duchenne|muscular dystrophy|ataxia|narcolepsy|neurolog\w+|dementia|\bRett\b|"
                 + _cs(r"\b(?:ALS|SMA|FSHD)\b"),
    "ophthalmology": _cs(r"\b(?:AMD|wAMD|DME)\b") + r"|macular (?:degeneration|edema)|geographic atrophy|retina\w*"
                     r"|retinopathy|glaucoma|dry eye|uveitis|Stargardt|ophthalm\w+|eye[- ](?:disease|drug|drops?|condition)s?"
                     r"|visual acuity|vision (?:gains?|loss)|retinal vein occlusion|myopia",
    "infectious_disease": _cs(r"\b(?:COVID|SARS-CoV-2|RSV|HIV|HBV|HDV|CMV)") + r"|influenza|\bflu\b|hepatitis|Ebola"
                          r"|dengue|malaria|tuberculosis|antibiotic|antifungal|antiviral|infection\w*|sepsis|norovirus"
                          r"|mpox|pneumococcal|meningococcal",
    "immunology": r"atopic dermatitis|eczema|psoria\w+|lupus|rheumatoid arthritis|ulcerative colitis|Crohn(?:\W?s)?\b"
                  r"|alopecia areata|myasthenia gravis|Sj[oö]gren(?:\W?s)?\b|autoimmun\w+|immunolog\w+|hidradenitis"
                  r"|vitiligo|asthma|eosinophilic|nephrotic syndrome|IgA nephropathy|transplant\w*|urticaria|"
                  + _cs(r"\b(?:SLE|IBD|COPD)\b"),
    "cardio_metabolic": r"obesity|overweight|diabet\w+|insulin|heart failure|hypertension|cholesterol|Lp\(a\)"
                        r"|lipoprotein|cardiomyopathy|atrial fibrillation|cardiovascular|coronary"
                        r"|chronic kidney disease|hypertriglyceridemia|thrombo\w+|\bstroke\b|"
                        + _cs(r"\b(?:LDL|MASH|NASH|CKD)\b"),
    "rare_disease": r"rare (?:disease|disorder|condition)|ultra-?rare|orphan|fibrodysplasia|Sanfilippo|Duchenne"
                    r"|hemophilia|sickle cell|thalassemia|Fabry|Pompe|Gaucher|lysosomal|cystic fibrosis"
                    r"|Huntington(?:\W?s)?\b|Alexander disease|polycythemia vera|amyloidosis|"
                    + _cs(r"\b(?:FOP|MCT8|FSHD|SMA|PKU)\b"),
}
_MOD_C = {k: re.compile(v, I) for k, v in MODALITY_RX.items()}
_AREA_C = {k: re.compile(v, I) for k, v in AREA_RX.items()}

# ---------------------------------------------------------------------------
# 3.4.3 attribution
# ---------------------------------------------------------------------------
NAME_SUFFIX = re.compile(r"(?:,?\s+(?:inc\.?|incorporated|corp\.?|corporation|company|co\.?|ltd\.?|limited|plc|ag"
                         r"|s\.?a\.?|n\.?v\.?|ab|asa|a/?s|a s|se|holdings?|group|llc|l\.?p\.?)|\s*&|\s+and)\s*$", I)
GENERIC_NAME_WORDS = frozenset({
    "the", "first", "united", "american", "general", "global", "advanced", "applied", "international", "national",
    "bio", "pharma", "medical", "health", "summit", "vera", "therapeutics", "pharmaceuticals", "pharmaceutical",
    "sciences", "biosciences", "bioscience", "biotherapeutics", "biopharma", "biopharmaceuticals", "oncology",
    "genetics", "genomics", "labs", "laboratories", "technologies", "holdings", "eli", "new", "life", "gene",
    "cell", "crispr", "mrna", "vaccines", "immune", "neuro"})
MOD_AREA_WORDS = re.compile(r"^(?:crispr|mrna|gene|cell|vaccines?|antibod\w*|oncolog\w*|neuro\w*|immun\w*"
                            r"|cardio\w*|rna|dna)$", I)
ISSUER_ALIASES = {"BMY": ("BMS",), "JNJ": ("J&J", "Janssen"), "MRK": ("MSD",), "GSK": ("GSK",),
                  "RHHBY": ("Roche", "Genentech")}
THIRD_PARTY = re.compile(r"\b(?:race for|vs\.?|versus|than|threat to|peers? like|competitors? like|rivals? like"
                         r"|such as|including|against|reshape)\b[^;!?]{0,30}$", I)


def normalise_name(name: Optional[str]) -> str:
    """'Eli Lilly and Company' -> 'Eli Lilly'; 'HUTCHMED (China) Ltd' -> 'HUTCHMED'."""
    n = re.sub(r"\([^)]*\)", " ", name or "")
    n = re.sub(r"\s+", " ", n).strip()
    prev = None
    while prev != n:
        prev = n
        n = NAME_SUFFIX.sub("", n).strip(" ,")
    return n


def name_forms(ticker: str, name: Optional[str]) -> tuple:
    """Regex strings (case-insensitive unless an inline CS group) that name the
    issuer: normalised full name · the distinctive word · abbreviation aliases ·
    $TICKER · (TICKER) / (NASDAQ: TICKER) · bare CS ticker when len >= 4."""
    ticker = (ticker or "").upper().strip()
    out = []
    n = normalise_name(name) if name else ""
    if n:
        out.append(re.escape(n).replace(r"\-", r"[\s-]").replace(r"\ ", r"[\s-]"))
    for tok in re.split(r"[\s-]+", n):
        w = re.sub(r"[^\w&]", "", tok)
        if len(w) >= 4 and w.lower() not in GENERIC_NAME_WORDS and not MOD_AREA_WORDS.match(w):
            if re.escape(w) not in out:
                out.append(re.escape(w))
            break
    for a in ISSUER_ALIASES.get(ticker, ()):
        out.append(_cs(re.escape(a)))
    if ticker:
        t = re.escape(ticker)
        out.append(r"\$" + t)
        out.append(r"\(\s*(?:(?:NASDAQ|NYSE|NYSE American|OTC)\s*:\s*)?" + t + r"\s*\)")
        if len(ticker) >= 4:
            out.append(_cs(t))
    return tuple(out)


def _mentions(title: str, forms) -> list:
    hits = []
    for p in forms or ():
        try:
            rx = re.compile(r"(?<![\w$])(?:" + str(p) + r")(?![\w])", I)
        except re.error:
            rx = re.compile(r"(?<![\w$])" + re.escape(str(p)) + r"(?![\w])", I)
        hits.extend(m.start() for m in rx.finditer(title or ""))
    return sorted(hits)


def attribute(title: str, *, ticker: str, forms: tuple, cue_span: Optional[tuple] = None) -> bool:
    """§3.4.3 rule 3 — is `ticker` the SUBJECT of this title?"""
    title = title or ""
    hits = _mentions(title, forms or name_forms(ticker, None))
    if not hits:
        return False
    first = hits[0]
    if THIRD_PARTY.search(title[max(0, first - 40):first]):
        return False
    c0 = cend(title, 0)
    if cue_span:
        ca, cb = cstart(title, cue_span[0]), cend(title, cue_span[1])
    else:
        ca, cb = 0, c0
    return any(h < c0 or ca <= h < cb for h in hits)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def merge_only_flag(t: str, forms=()) -> bool:
    """§3.4.1 M1 / M2 / M3 — a price story: its events may merge, never create."""
    if M1.search(t) or M3.search(t):
        return True
    for f in forms or ():
        try:
            if re.search(r"(?<![\w$])(?:" + str(f) + r")(?:['’]s)?(?:\s+(?:Inc\.?|Corp\.?|\([A-Z.:\s]+\)|stock|shares))?"
                         r"\s+(?:" + PV + r")\b", t, I):
                return True
        except re.error:
            continue
    return False


def extract_phase(masked: str, anchor: Optional[tuple], *, drop_future: bool = True) -> Optional[str]:
    """§3.4.2-P: the phase token NEAREST the outcome cue; future phases dropped.
    A trial_milestone reads its own clause with drop_future=False — the phase
    being initiated IS the milestone's phase ("initiation of the registrational
    Phase 3 ZUPREME program" -> 3)."""
    toks = []
    for m in PHASE_TOK.finditer(masked):
        if drop_future and FUTURE_PH.search(masked[max(0, m.start() - 40):m.start()]):
            continue
        # "Phase 3 Enabling Topline Results from Phase 2 RADIANT" (ACAD, regrade): enabling / ready = the NEXT phase
        if drop_future and _ENABLING.match(masked[m.end():m.end() + 12]):
            continue
        v = (m.group(1) or m.group(2)).lower()
        v = PH_NORM.get(v, v)
        if v == "registrational":
            v = "pivotal"
        toks.append((m.start(), m.end(), v))
    merged = []
    for i, (a, b, v) in enumerate(toks):
        if v == "pivotal" and i + 1 < len(toks) and toks[i + 1][0] - b <= 12:
            continue
        merged.append((a, b, v))
    if not merged or anchor is None:
        return None
    aa, ab = anchor
    best = min(merged, key=lambda x: (0 if (x[0] < ab and x[1] > aa) else min(abs(x[0] - ab), abs(aa - x[1])), x[0]))
    return best[2]


def direction(masked: str) -> tuple:
    """§3.4.2-D -> (direction, first outcome-cue span)."""
    d, first, _sec = _direction(masked)
    return d, first


def _direction(masked: str) -> tuple:
    """(direction, first outcome-cue span, secondary_missed)."""
    m, neg, sec, first = masked, False, False, None
    for p in SECMISS:
        for x in list(p.finditer(m)):
            sec = True
            m = mask(m, x.start(), x.end())
    for p in NEG:
        for x in list(re.finditer(p, m, I)):
            neg = True
            first = first or (x.start(), x.end())
            m = mask(m, x.start(), cend(m, x.end()))
    pos = False
    for p in POS:
        x = re.search(p, m, I)
        if x:
            pos = True
            first = first or (x.start(), x.end())
    mixed_lit = re.search(r"mixed (?:results|data)", masked, I) or re.search(
        r"\bmet\b" + GAP + r"{0,60}\bbut\b" + GAP + r"{0,40}\b(?:missed|did not|failed)", masked, I)
    if mixed_lit or (pos and (neg or sec)):
        d = "mixed"
    elif pos:
        d = "positive"
    elif neg:
        d = "negative"
    elif sec:
        d = "mixed"
    else:
        d = "unknown"
    return d, first, sec


_TRIAL_RX = re.compile(r"(?-i:\b([A-Z][A-Z0-9-]{3,14})\b)(?=\s+(?i:(?:pivotal\s+)?(?:phase\s+\S+\s+)?(?:[\w-]+\s+)?"
                       r"(?:trial|study|program)))|(?-i:\b(NCT\d{8})\b)")
_TRIAL_STOP = frozenset({"FDA", "NDA", "BLA", "IND", "PDUFA", "ESMO", "ASCO", "COVID", "HIV", "AMD", "FSHD", "CEO",
                         "USA", "PHASE", "WAMD", "COVID-19", "MRNA", "SNDA", "SBLA", "EMA", "CHMP", "CRISPR",
                         "CLINICAL", "GLOBAL", "PIVOTAL"})


def extract_trial(text: str) -> Optional[str]:
    """'DAYBREAK', 'AZURE-1', 'NCT06556368' — else None."""
    for m in _TRIAL_RX.finditer(text or ""):
        v = m.group(1) or m.group(2)
        if v and v.upper() not in _TRIAL_STOP and not v.isdigit():
            return v
    return None


def _regulator_exus(t: str) -> Optional[str]:
    for name, rx in EXUS_REGULATORS:
        if re.search(rx, t):
            return name
    return None


def _approval_subtype(clause: str) -> str:
    if re.search(r"tentative", clause, I):
        return "tentative"
    if re.search(_cs(r"\bANDA\b") + r"|\bgeneric\b|biosimilar", clause, I):
        return "generic"
    if re.search(r"accelerated", clause, I):
        return "accelerated"
    if re.search(r"emergency use authori[sz]ation|" + _cs(r"\bEUA\b"), clause, I):
        return "eua"
    if re.search(r"\bclear(?:s|ed|ance)\b|510\(k\)|\bDe Novo\b|\bPMA\b", clause, I):
        return "device_clearance"
    if re.search(_cs(r"\bs(?:NDA|BLA)\b") + r"|label expansion|expanded (?:indication|label|approval)"
                 r"|additional indication|\bfor (?:adolescents|children|pediatric|paediatric|younger patients)\b",
                 clause, I):
        return "label_expansion"
    if re.search(r"\bupdated\b.{0,30}vaccines?", clause, I):
        return "updated_vaccine"
    return "novel"


def _modality(text: str) -> list:
    hit = {k for k, rx in _MOD_C.items() if rx.search(text)}
    if "adc" in hit:
        hit.discard("antibody_bispecific")
    if "antibody_bispecific" in hit and "small_molecule" in hit:
        sm = _MOD_C["small_molecule"]
        spans = [m.group(0) for m in sm.finditer(text)]
        if spans and all(_SM_INHIBITOR_ONLY.fullmatch(s) for s in spans):
            hit.discard("small_molecule")
    out = [k for k in MODALITY_PRIORITY if k in hit]
    return out or ["unclassified"]


def _areas(text: str, title: str) -> list:
    hit = {k for k, rx in _AREA_C.items() if rx.search(text)}
    for m in _CONGRESS_CS.finditer(title or ""):
        a = CONGRESS_AREA.get(m.group(0))
        if a:
            hit.add(a)
    out = [k for k in AREA_PRIORITY if k in hit]
    return out or ["unclassified"]


def medical_words_hit(title: str) -> bool:
    """§3.4.6 MEDICAL_WORDS or any modality / area hit on the title."""
    t = title or ""
    if MEDICAL_WORDS.search(t):
        return True
    return _modality(t) != ["unclassified"] or _areas(t, t) != ["unclassified"]


def _ev(typ: str, sub, **kw) -> dict:
    e = {"event_type": typ, "subtype": sub, "direction": None, "phase": None, "regulator": None, "trial": None,
         "cue": None, "cue_span": None, "from_commentary": False}
    e.update(kw)
    return e


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------
def classify(title: str, *, context: str = "", ticker: Optional[str] = None, forms: tuple = (),
             issuer_medical: Optional[bool] = None) -> dict:
    """PURE. `title` decides event types (precision); `title + context` decides
    modality and area (recall). See the module docstring for the order."""
    t0 = (title or "").strip()
    ticker = (ticker or "").upper() or None
    if ticker and not forms:
        forms = name_forms(ticker, None)
    text_all = t0 + " " + (context or "")
    out = {"events": [], "modality": _modality(text_all), "areas": _areas(text_all, t0),
           "roundup": False, "commentary": False, "merge_only": False,
           "attributed": None, "dropped": [], "reasons": [], "rules_version": RULES_VERSION}
    if ticker:
        out["attributed"] = attribute(t0, ticker=ticker, forms=forms, cue_span=None)
    if ROUNDUP.search(t0):
        out["roundup"] = True
        out["reasons"].append("roundup")
        return out
    if COMMENT.search(t0):
        out["commentary"] = True
        out["reasons"].append("commentary")
        return out
    out["merge_only"] = merge_only_flag(t0, forms)

    t = t0
    for x in list(UNREL.finditer(t)):
        t = mask(t, x.start(), x.end())
    for x in list(BACKGROUND.finditer(t)):
        a = cstart(t, x.start())
        if any(re.search(h, t[a:x.start()], I) for h in HEAD):
            t = mask(t, x.start(), cend(t, x.end()))

    events, emitted = [], set()
    for typ, ext, cues in LADDER:
        if typ == "conference_data":
            t = _conference(t, t0, events, emitted)
            continue
        for pat, sub in cues:
            for x in list(re.finditer(pat, t, I)):
                pre = t[max(0, x.start() - 25):x.start()]
                post = t[x.end():x.end() + 25]
                intent = bool(INTENT_B.search(pre)) or bool(INTENT_A.search(post))
                cl = t[cstart(t, x.start()):cend(t, x.end())]
                if typ == "fda_crl" and sub == "crl" and x.group(0) == "CRL" and _CRL_TICKER.search(t0[:x.start()]):
                    continue
                if typ == "readout_scheduled" and re.search(
                        r"financial results|earnings|fiscal|quarter(?:ly)?\s+(?:\d{4}\s+)?(?:financial|results"
                        r"|earnings|report)", cl, I):
                    continue
                if typ == "regulatory_filing" and sub == "ind_cleared" and re.search(
                        r"\b(?:pilot|guidance|policy|framework|program)\b", cl, I):
                    continue
                if typ == "fda_approval":
                    w = _APPROVAL_WORD.search(x.group(0))
                    if w:
                        wa, wb = x.start() + w.start(), x.start() + w.end()
                        if PENDING_B.search(t[max(0, wa - 20):wa]) or PENDING_A.search(t[wb:wb + 25]):
                            intent = True
                if intent:
                    t = mask(t, x.start(), cend(t, x.end()))
                    continue
                if typ in emitted:                              # one event per type per title
                    continue
                ev = _ev(typ, sub, cue=t0[x.start():x.end()], cue_span=(x.start(), x.end()))
                if typ in ("fda_crl", "fda_revoked", "clinical_hold", "pdufa", "adcom", "fda_approval"):
                    ev["regulator"] = "FDA"
                if typ == "fda_crl" and sub == "withdrawn" and re.search(_cs(r"\bMAA\b"), x.group(0)):
                    ev["regulator"] = "EMA"
                if typ == "designation":
                    ev["regulator"] = "EMA" if sub == "prime" else "FDA"
                if typ == "clinical_hold" and sub == "placed":
                    ev["partial"] = bool(re.search(r"partial", x.group(0), I))
                if typ == "pdufa":
                    ev["subtype"] = ("extended" if re.search(r"extend\w*|delay\w*", cl, I) else
                                     "set" if re.search(r"\b(?:set|sets|assigned|assigns)\b", cl, I) else "upcoming")
                if typ == "adcom":
                    if re.search(r"vot(?:es|ed)\b" + GAP + r"{0,20}(?:in favor|favorabl|to (?:support|recommend))", t0, I):
                        ev["direction"] = "positive"
                    elif re.search(r"vot(?:es|ed)\b" + GAP + r"{0,25}against|negative vote", t0, I):
                        ev["direction"] = "negative"
                if typ == "trial_milestone":
                    ev["phase"] = extract_phase(t[x.start():cend(t, x.end())], (0, 1), drop_future=False)
                if typ == "fda_approval":
                    ev["subtype"] = _approval_subtype(t0[cstart(t0, x.start()):cend(t0, x.end())])
                events.append(ev)
                emitted.add(typ)
                t = mask(t, x.start(), cend(t, x.end()) if ext else x.end())

    # 12 exus_approval: an approval / positive-opinion cue with a non-US regulator and no FDA
    if "fda_approval" not in emitted and not re.search(_cs(r"\bFDA\b"), t0):
        reg = _regulator_exus(t)
        if reg:
            for x in re.finditer(EXUS_CUE, t, I):
                pre = t[max(0, x.start() - 25):x.start()]
                if INTENT_B.search(pre) or PENDING_B.search(t[max(0, x.start() - 20):x.start()]):
                    continue
                events.append(_ev("exus_approval", "approval", regulator=reg, cue=t0[x.start():x.end()],
                                  cue_span=(x.start(), x.end())))
                emitted.add("exus_approval")
                t = mask(t, x.start(), x.end())
                break

    if emitted:
        for x in list(BACKGROUND.finditer(t)):
            t = mask(t, x.start(), cend(t, x.end()))

    # 13 topline / 8 discontinued fallback
    if "trial_milestone" not in emitted:
        cue = None
        for p in TOPCUE + NEG + POS + [x.pattern for x in SECMISS]:
            x = re.search(p, t, I)
            if x and (cue is None or x.start() < cue[0]):
                cue = (x.start(), x.end())
        if cue:
            pre = t[max(0, cue[0] - 25):cue[0]]
            if not INTENT_B.search(pre):
                d, anchor, sec = _direction(t)
                sneg = any(re.search(sp, t, I) for sp in STOP)
                if sneg and d == "unknown":
                    d = "negative"
                elif sneg and d == "positive":
                    d = "mixed"
                events.append(_ev("topline", None, direction=d, phase=extract_phase(t, anchor or cue),
                                  secondary_missed=bool(sec), cue=t0[cue[0]:cue[1]], cue_span=cue))
                emitted.add("topline")
        elif any(re.search(sp, t, I) for sp in STOP):
            sp = next(re.search(p, t, I) for p in STOP if re.search(p, t, I))
            events.append(_ev("trial_milestone", "discontinued", cue=t0[sp.start():sp.end()],
                              cue_span=(sp.start(), sp.end())))
            emitted.add("trial_milestone")

    # 14–16 safety / deal / financing on what is left
    x = re.search(SAFETY, t, I)
    if x:
        events.append(_ev("safety", "safety", cue=t0[x.start():x.end()], cue_span=(x.start(), x.end())))
        t = mask(t, x.start(), x.end())
    for sub, rx in DEAL:
        x = re.search(rx, t, I)
        if x:
            events.append(_ev("deal", sub, cue=t0[x.start():x.end()], cue_span=(x.start(), x.end())))
            t = mask(t, x.start(), x.end())
            break
    for sub, rx in FINANCING:
        x = re.search(rx, t0 if sub == "secondary_holders" else t, I)
        if x:
            events.append(_ev("financing", sub, dilutive=(sub != "secondary_holders"),
                              cue=t0[x.start():x.end()], cue_span=(x.start(), x.end())))
            break

    # trial name on the events that carry one
    trial = extract_trial(t0)
    for e in events:
        if e["event_type"] in ("topline", "conference_data", "trial_milestone", "readout_scheduled"):
            e["trial"] = trial

    # 10 medical gate (§3.4.6)
    medical = bool(issuer_medical) or medical_words_hit(t0)
    kept = []
    for e in events:
        if e["event_type"] in GATED_TYPES and not (ticker and medical):
            out["dropped"].append(f"non_medical_event:{e['event_type']}")
            continue
        kept.append(e)
    events = kept

    # 11 attribution — the issuer must be the subject in the first clause or the cue's clause
    if ticker:
        span = events[0]["cue_span"] if events else None
        out["attributed"] = attribute(t0, ticker=ticker, forms=forms, cue_span=span)
    for e in events:
        e["from_commentary"] = bool(out["merge_only"])
    out["events"] = events
    out["reasons"].extend(f"{e['event_type']}:{e.get('subtype') or e.get('direction')}" for e in events)
    return out


def _conference(t: str, t0: str, events: list, emitted: set) -> str:
    """Ladder #8 — a NAMED congress (or symposium / plenary / late-breaking slot)
    with a science word, or a GENERIC meeting with a DATA word and no investor
    word, in the same clause. The whole clause is masked."""
    for x in list(re.finditer(CONGRESS_NAMED + "|" + PRES_SYMP + "|" + GENERIC_MEET, t, I)):
        a, b = cstart(t, x.start()), cend(t, x.end())
        clause = t[a:b]
        named = re.search(CONGRESS_NAMED + "|" + PRES_SYMP, x.group(0), I)
        if named and re.fullmatch(CONGRESS_NAMED, x.group(0), I) and not _CONGRESS_CS.fullmatch(x.group(0)):
            continue                                            # "Ash", "ada", "aes" in prose: congress names are CS
        if not re.search(SCI if named else SCI_DATA, clause, I):
            continue
        if not named and INVESTOR.search(clause):
            continue
        # "Announces Presentation of … at Euretina 2026" (#54) is the pre-meeting notice
        sub = "upcoming" if re.search(r"to be presented|will present|to present|accepted for|\bslot\b|highlights?\b"
                                      + GAP + r"{0,40}to be|\bannounces? (?:[\w-]+ ){0,3}?presentations? of\b",
                                      clause, I) else "presented"
        d, anchor, _sec = _direction(clause)
        ph = extract_phase(clause, anchor or (x.start() - a, x.end() - a))
        cm = _CONGRESS_CS.search(t0[a:b])
        events.append(_ev("conference_data", sub, direction=d if d != "unknown" else None, phase=ph,
                          congress=cm.group(0) if cm else None, cue=t0[x.start():x.end()],
                          cue_span=(x.start(), x.end())))
        emitted.add("conference_data")
        return mask(t, a, b)
    return t
