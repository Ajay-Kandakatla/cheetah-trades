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
    r"|under-?valued|over-?valued|fully valued|fair value|bull case|bear case"
    # fix round 2 (critic probe 2026-09-29): "Jefferies Upgrades Viking … Phase 3
    # Trial Met Primary Endpoint", "Buy The Dip After Positive Phase 3 … (Rating
    # Upgrade)" pushed as Phase 3 toplines -> analyst-rating words are commentary.
    r"|upgrades?|upgraded|downgrades?|downgraded|reiterates?|buy the dip|analyst rating|rating (?:upgrade|downgrade|change)"
    r"|(?:buy|sell|hold|outperform|underperform|overweight|underweight|neutral|market perform|sector perform) rating)\b", I)
# fix round 3 (OOS grade 2026-09-29, PTGX "Protagonist Therapeutics: 'Strong Buy'
# ICOTYDE FDA Approval And PN-881 Advancement" pushed as an FDA approval): the
# opinion-piece FORM — a QUOTED rating anywhere ('Buy', "Hold", 'Strong Sell'),
# the two-word ratings unquoted, or a "Name: <rating> …" prefix — is commentary.
_RATING = r"(?:strong\s+)?(?:buy|sell|hold|outperform|underperform|overweight|underweight|neutral|accumulate)"
COMMENT_FORM = re.compile(
    r"['\"‘’“”]\s*" + _RATING + r"\s*[,.!]?\s*['\"‘’“”]"
    r"|\bstrong\s+(?:buy|sell)\b"
    r"|^[^:;!?]{2,80}:\s+(?:(?:upgrad|downgrad|reiterat|rat|initiat)\w*\s+(?:(?:to|at|as|with)\s+(?:an?\s+)?)?)?"
    + _RATING + r"(?=\s+(?:on|after|as|despite|before|ahead|amid|into|for|here|now|thesis|rating)\b|\s*[,;—–-]|\s*$)", I)
PV = (r"pops?|popping|soar(?:s|ed|ing)?|jump(?:s|ed|ing)?|surg(?:es|ed|ing)|sinks?|sank|falls?|falling|fell"
      r"|slid(?:es|ing)?|slides?|plung(?:es|ed|ing)|rocket(?:s|ed|ing)?|skyrocket(?:s|ed|ing)?|climb(?:s|ed|ing)?"
      r"|rall(?:y|ies|ied|ying)|tumbl(?:es|ed|ing)|slip(?:s|ped|ping)?|spik(?:es|ed|ing)|crater(?:s|ed|ing)?"
      r"|plummet(?:s|ed|ing)?|tank(?:s|ed|ing)?|catapult(?:s|ed|ing)?|edg(?:es|ed) (?:higher|lower|up|down)"
      r"|trad(?:es|ing) (?:higher|lower)|rises?|rising|rose|dives?|dived|leaps?|leapt|zooms?|explodes?"
      r"|ripping|rips")
# fix round 2 (live run: "CLDX Stock Slumps 11% – … Calls Phase 3 Trial Safety
# Concerns 'Misplaced'" CREATED a safety event): slump / drop are price verbs
# next to stock/shares or a % move only — "Pfizer Drops Program" stays news.
PV_PRICE = PV + r"|slump(?:s|ed|ing)?|drops?|dropped|dropping"
M1 = re.compile(r"\b(?:stock|shares?)\b" + GAP + r"{0,15}\b(?:" + PV_PRICE + r")\b", I)
M3 = re.compile(r"\b(?:" + PV_PRICE + r")\b\s+(?:by\s+|nearly\s+|more than\s+|over\s+)?[+-]?\d+(?:\.\d+)?\s?(?:%|x\b)"
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
_CRL_TICKER = re.compile(r"\$\s*$|\(\s*(?:(?:NYSE|NASDAQ|Nasdaq|NYSE American|OTC)\s*:\s*)?$|\b(?:NYSE|NASDAQ|Nasdaq)\s*:\s*$")
# fix round 2 (critic probe): a CRL named as BACKGROUND is not a new CRL —
# "Resubmits BLA … Following CRL", "Type A Meeting With FDA Regarding CRL",
# "Addresses CRL Issues". Applies to both "CRL" and "complete response letter".
_CRL_BACKREF = re.compile(r"\b(?:regarding|following|after|address\w*|respon\w* to|resolv\w*|over|about|post)\b"
                          + GAP + r"{0,15}$", I)
_RESUBMIT = re.compile(r"\bresubmi\w*", I)
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
        # fix round 2 (critic probe): "Removal of Clinical Hold", "Clinical Hold
        # on Novavax Phase 1 Trial Resolved", "FDA Lifts Hold" pushed as PLACED.
        (r"(?:lift(?:s|ed|ing)?|remov(?:es|ed|al|ing)|release[sd]?|resol(?:ves?|ved|ution|ving)|clear(?:s|ed))\b"
         + GAP + r"{0,30}(?:partial\s+)?clinical hold|clinical hold" + GAP
         + r"{0,40}\b(?:lifted|removed|released|resolved|cleared)"
         r"|\b(?:lift(?:s|ed|ing)?|remov(?:es|ed|al))\s+(?:the\s+)?(?:partial\s+)?hold\b"
         r"|\bhold\s+(?:is\s+|was\s+|has been\s+)?lifted\b", "lifted"),
        # "Submits Complete Response to FDA Clinical Hold Letter": a reply, not a new hold
        (r"\b(?:submi\w*|respon\w*|repl(?:y|ies|ied))\b" + GAP + r"{0,40}(?:partial\s+)?clinical hold", "response"),
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
         + r"{0,30}\b(?:stud(?:y|ies)|trials?|clinical testing)\b", "ind_cleared"),
        # fix round 2 (critic probe): "Receives FDA Approval to Proceed With Phase 3
        # Trial", "IDE Approval to Begin Pivotal Study" are trial go-aheads.
        (r"\bapprov\w*\s+to\s+(?:proceed|begin|start|initiate|commence|resume)\b" + GAP
         + r"{0,40}\b(?:stud(?:y|ies)|trials?|phase|clinical testing)\b", "ind_cleared")]),
    ("pdufa", True, [
        (_cs(r"\bPDUFA\b") + r"|target action date|goal date|approval decision (?:expected|anticipated|date)"
         r"|\bFDA (?:action|decision) (?:date|on)\b",
         "date")]),
    # fix round 2 (critic probe): "FDA Panel Recommends Approval", "FDA Advisers
    # Back Approval of …" pushed as FDA approvals -> they are the committee.
    ("adcom", True, [(r"advisory committee|" + _cs(r"\b(?:AdCom|ODAC|VRBPAC)\b")
                      + r"|\bFDA(?:['\u2019]s)?\s+(?:expert\s+|outside\s+)?(?:panel|advis[eo]rs|advisory panel)\b",
                      "meeting")]),
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
        (r"first (?:patient|participant|subject)s? (?:dosed|enrolled|randomi[sz]ed|treated)"
         r"|\bdos(?:es|ed) (?:the )?first (?:patient|participant|subject)s?\b", "first_patient"),
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
# fix round 2 (critic probe 2026-09-29, fda_approval precision 0.31): an
# approval WORD is not an approval. Before it: a negative / pending-review verb
# ("FDA Delays / Declines / Withholds Approval", "Lacks", "Loses", "Panel
# Recommends", "Advisers Back"); after it: "… Delayed / Pushed Back"; in its
# clause: a non-marketing object ("Approval to Proceed With Phase 3", "IDE
# Approval to Begin", "Expanded Access", "Manufacturing Facility"); the
# adjective "FDA-Approved" / "FDA-Cleared"; a background preposition right
# before the cue ("… Following FDA Approval of Revolution Medicines' …").
_APPR_NEG_B = re.compile(r"\b(?:declin\w*|delay\w*|block\w*|withh[oe]ld\w*|lacks?|lacking|los(?:es|t|ing)|question\w*"
                         r"|doubts?|narrow\w*|recommend\w*|backs?|backing|without|no|not|panel|advis[eo]rs?|staff"
                         r"|reviewers?)\b" + GAP + r"{0,25}$", I)
_APPR_NEG_A = re.compile(r"^" + GAP + r"{0,30}\b(?:delayed|postponed|pushed back|put on hold|in doubt)\b", I)
_APPR_NOT_MARKETING = re.compile(r"\bto (?:proceed|begin|start|initiate|commence)\b|expanded access|study plan"
                                 r"|\bprotocol\b|" + _cs(r"\bIDE\b") + r"|investigational device exemption"
                                 r"|manufactur\w*|\bfacility\b"
                                 # a SAFETY label change is not an approval ("Approves Label Update … Boxed Warning")
                                 r"|(?:label(?:ing)? (?:update|change)|update to (?:the )?(?:product )?label)" + GAP
                                 + r"{0,60}\b(?:boxed warning|warnings?|monitoring|REMS|safety)\b", I)
_APPR_ADJ = re.compile(r"FDA\s*-\s*(?:approved|cleared|authori[sz]ed)", I)
_APPR_BACKREF = re.compile(r"\b(?:after|following|post|since|despite|amid|in the wake of|on the back of)\W+"
                           r"(?:(?:the|its|an?|U\.?S\.?)\s+)?$", I)
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
BACKGROUND = re.compile(r"\b(?:despite|after|following|based on|on the back of|supported by|building on|backed by"
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
       r"\bmiss(?:es|ed)?\b" + GAP + r"{0,20}\bprimary\b" + GAP + r"{0,20}(?:endpoints?|goal|target)",
       r"\bprimary (?:efficacy )?endpoints?\s+(?:was |were )?not\s+(?:met|achieved|reached)",
       r"\b(?:not|no|lack of|without)\s+(?:a\s+)?statistically significant", r"\bfutility\b",
       r"\b(?:trial|study)\s+(?:fail(?:s|ed)?|failure)\b", r"\bfail(?:s|ed)?\b" + GAP + r"{0,20}\b(?:trial|study)\b",
       r"(?<!FDA )(?<!regulatory )(?<!Regulatory )\bsetback\b", r"\bthrew in the towel\b", r"\bnegative (?:top[- ]?line|results|data|outcome)\b",
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
       r"\btrial win\b|\bwins?\b" + GAP + r"{0,20}\btrial\b",
       # fix round 3 (OOS grade: GILD "…; Meets Week 48 Endpoints In ISLEND-1 And
       # ISLEND-2 Trials", "Meets Dual Primary Endpoints" came out undirected): up to
       # four words between the verb and "endpoints" — never "Met With FDA On
       # Endpoints" (a meeting). A negated verb ("did not meet …") is masked by NEG
       # before POS runs.
       r"\b(?:met|meets?|achiev(?:ed|es)|hits?)\s+(?:(?!(?:not|no|with|to|on|regarding|about|discuss\w*|fda|agency"
       r"|regulators?)\b)[\w/-]+\s+){0,4}?end ?points?\b",
       # fix round 2 (critic probe, recall): "Halts Phase 3 … Trial Early for Efficacy"
       r"\bearly (?:for|due to|on|after) (?:overwhelming |positive |strong |clear )?efficacy\b"]
_EFFICACY_STOP = re.compile(POS[-1], I)
STOP = [r"\bdiscontinu\w*\b" + GAP + r"{0,30}\b(?:trial|study|program|development)\b",
        r"\bterminat\w*\b" + GAP + r"{0,20}\b(?:trial|study|program)\b",
        r"\bhalt(?:s|ed)?\b" + GAP + r"{0,30}\b(?:trial|study|program)\b"]
# fix round 2 (critic probe): "Phase 3 Trial Passes Prespecified Interim
# Futility Analysis" read NEGATIVE — a passed / survived futility look is masked.
_PASSED_FUTILITY = re.compile(
    r"\b(?:pass(?:es|ed|ing)?|clear(?:s|ed)?|surviv\w+|continu\w*|proceed\w*)\b" + GAP + r"{0,35}\bfutility\b"
    r"(?:\s+(?:analysis|review|look|concerns?|boundary))?|\b(?:no|without)\s+(?:a\s+)?futility\b"
    r"|\bfutility\b" + GAP + r"{0,40}\b(?:will continue|to continue|continu(?:es|ed|ation)|proceed\w*)\b", I)
# A POSITIVE "topline" that is not a new controlled readout: a regulatory
# interaction (dropped) or secondary / uncontrolled data (direction unknown).
_NOT_READOUT_REG = re.compile(r"\b(?:end[- ]of[- ]phase|type [abc] meeting|feedback|alignment|design)\b", I)
_NOT_READOUT_DATA = re.compile(r"\b(?:post[- ]hoc|subgroups?|sub-?analys[ie]s|exploratory|open[- ]label extension"
                               r"|long[- ]term extension|extension (?:portion|study|period|phase)|published in"
                               # fix round 4 (OOS grade #7): "Announces Publication in The Lancet of
                               # Positive Phase 3 Data" is a journal paper of an old readout
                               r"|publication (?:in|of))\b", I)
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
# fix round 2 (live run: RYTM "…Weight Management In … Acquired Hypothalamic
# Obesity" became M&A): "acquired" before a condition is an adjective.
_ACQ_ADJ = (r"(?!(?:\s+[\w-]+){0,2}\s+(?:obesity|deficien\w*|hemophilia|diseases?|disorders?|syndromes?|resistan\w*"
            r"|infections?|pneumonia|an(?:a)?emia|thrombo\w*|immunodeficiency|TTP)\b)")
DEAL = (("mna", r"\bacquires?\b|\bacquired\b" + _ACQ_ADJ + r"|acquisition of|to acquire|buyout|\bmerger\b|merge with|tender offer|takeover"),
        ("licensing", r"licens(?:e|ing) (?:agreement|deal)|in-licens\w*|exclusive license"),
        ("partnership", r"collaboration(?! revenue)|partnership|partners with|strategic alliance"),
        ("milestone", r"milestone payment|\bupfront\b"))
# a deal cue followed by talk / rumour is chatter, not a deal (VKTX "Buyout Talks")
_DEAL_TALK = re.compile(r"^\W*(?:talks?|rumou?rs?|speculation|chatter|interest|hopes?|bets?)\b", I)
# "…Became a Partner Before Its IPO": the IPO is someone else's
_IPO_OTHER = re.compile(r"\b(?:before|ahead of|pre)\W+(?:(?:its|their|an?|the)\s+)?$", I)
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
    r"\b(?:FDA|EMA|CHMP|clinical|trials?|phase\s*\d|patients?|(?:bio)?therap\w+|drugs?|vaccines?|biotech\w*"
    r"|(?:bio)?pharma\w*"
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
    "cardio_metabolic": r"obesity|overweight|\bdiabet(?!ic\s+(?:macular|retinopathy|retinal|eye))\w+|insulin|heart failure|hypertension|cholesterol|Lp\(a\)"
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
                         r"|such as|including|against|reshape"
                         # fix round 3 (OOS: MDT credited with "Edwards wins FDA clearance
                         # for LAA clip, setting up competition with AtriCure and Medtronic")
                         r"|competition (?:with|for|from)|compet(?:es|ing|e) (?:with|against)|win for|blow to"
                         r"|weighs? on|pressure on)\b[^;!?]{0,30}$", I)


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


_POSSESSIVE = re.compile(r"(?-i:\b([A-Z][\w&.-]*))['\u2019]s\b")
_POSSESSIVE_NOT_RIVAL = frozenset({"FDA", "EMA", "CHMP", "MHRA", "NICE", "PMDA", "NMPA", "U.S", "US", "America",
                                   "Europe", "EU", "Japan", "China", "World", "Today", "Week", "Year", "Trump",
                                   "Street", "Wall", "Investor", "Investors", "Company", "Patients"})


def _rival_possessive(head: str, forms) -> bool:
    fr = []
    for f in forms or ():
        try:
            fr.append(re.compile(r"(?<![\w$])(?:" + str(f) + r")", I))
        except re.error:
            continue
    for pm in _POSSESSIVE.finditer(head or ""):
        if pm.group(1) in _POSSESSIVE_NOT_RIVAL:
            continue
        if not any(r.match(head, pm.start()) for r in fr):
            return True
    return False


def _form_rx(forms) -> list:
    fr = []
    for f in forms or ():
        try:
            fr.append(re.compile(r"(?<![\w$])(?:" + str(f) + r")", I))
        except re.error:
            continue
    return fr


_OBJ_POSSESSIVE = re.compile(r"^\s*(?:(?:of|for|to|on)\s+)?(?:the\s+)?(?:its\s+partner\s+)?"
                             r"(?-i:((?:[A-Z][\w&.-]*\s+){0,2}[A-Z][\w&.-]*))['’]s\b", I)
# a headline's own SUBJECT: 1-5 capitalised words (a parenthesised ticker allowed)
# right before a verb-led cue, or before a reporting verb that precedes the cue
_SUBJ_PHRASE = re.compile(r"^\W*(?-i:((?:[A-Z][\w&.’'-]*\s+(?:(?:and|&|of)\s+)?){0,4}[A-Z][\w&.’'-]*))"
                          r"\s*(?:\([^)]*\)\s*)?(?:(?:announces?|reports?|says?|unveils?|posts?|shares?|releases?)\s+)?$")
_VERB_CUE = re.compile(r"^(?:receives?|received|wins?|won|gets?|got|gains?|secures?|lands?|obtains?|announces?"
                       r"|earns?|snags?|reports?|nabs?|scores?)\b", I)
_NOT_SUBJECT = re.compile(r"^(?:FDA|EMA|CHMP|MHRA|NICE|U\.?S\.?|US|EU|Breaking|Update[ds]?|Exclusive|Report(?:ed)?"
                          r"|Correction|Watch|Why|How|What|New|The|A|An)\b", I)


def _rival_owner_before(title: str, cue0: int, hits: list, fr: list) -> bool:
    """The LAST non-regulator possessive before the cue belongs to another company
    and the issuer is not re-named between it and the cue."""
    last = None
    for pm in _POSSESSIVE.finditer(title[:cue0]):
        if pm.group(1) in _POSSESSIVE_NOT_RIVAL:
            continue
        last = pm
    if last is None:
        return False
    if any(r.match(title, last.start()) for r in fr):
        return False
    # the possessive may be the tail of a multi-word issuer name ("Eli Lilly's")
    if any(h < last.start() and not re.search(r"[;!?]|\b(?:and|&|of)\b", title[h:last.start()], I)
           and len(title[h:last.start()].split()) <= 2 for h in hits):
        return False
    return not any(last.end() <= h < cue0 for h in hits)


def _not_a_company(phrase: str) -> bool:
    """A disease / modality / medical phrase ("Alzheimer's", "Parkinson's") —
    never another company (fix round 4, critic #4)."""
    return bool(MEDICAL_WORDS.search(phrase) or _areas(phrase, phrase) != ["unclassified"])


_REPORT_VERB = r"(?:says?|said|announces?|announced|reports?|reported|confirms?|confirmed)"


def _issuer_reports(title: str, hits: list, fr: list) -> bool:
    """fix round 4 (critic #4): the issuer is the headline's REPORTER — "…,
    <Issuer> Says / Announces" or "… - <Issuer>" at the end — so the phrase that
    leads the headline is the issuer's own product ("Opdivo Gets FDA Nod …,
    Bristol Myers Squibb Says")."""
    for h in hits:
        if not re.search(r"(?:[,;:\u2013\u2014]|\s-)\s*$", title[:h]):
            continue
        for r in fr:
            m = r.match(title, h)
            if m and re.match(r"\s*(?:\([^)]*\)\s*)?(?:" + _REPORT_VERB + r"\b|[.!]?\s*$)", title[m.end():], I):
                return True
    return False


def _issuer_colon_subject(title: str, hits: list, fr: list) -> bool:
    """"<Issuer>: FDA Approval of Keytruda's Subcutaneous Form" — the colon-prefix
    names the headline's subject; what follows is the issuer's own news (fix
    round 4, critic #4). Opinion forms ("Name: 'Strong Buy' …") are dropped
    earlier by COMMENT_FORM."""
    for h in hits:
        if title[:h].strip(" \"'\u201c\u2018"):
            continue
        for r in fr:
            m = r.match(title, h)
            if m and re.match(r"\s*(?:\([^)]*\)\s*)?:\s", title[m.end():]):
                return True
    return False


def _rival_object_after(title: str, cue1: int, fr: list, hits: Optional[list] = None) -> bool:
    """"… Approved By FDA / FDA Approval of Roche's Assay": the cue's OBJECT is
    another company's product. Never a disease possessive ("Approval For
    Alzheimer's Agitation"), never when the issuer is the colon-prefix subject."""
    m = _OBJ_POSSESSIVE.match(title[cue1:])
    if not m:
        return False
    a = cue1 + m.start(1)
    words = m.group(1).split()
    if words[-1] in _POSSESSIVE_NOT_RIVAL or _not_a_company(m.group(1)):
        return False
    if hits and _issuer_colon_subject(title, hits, fr):
        return False
    return not any(r.match(title, a) or r.search(m.group(1)) for r in fr)


def _rival_subject(title: str, cue_span: tuple, fr: list) -> bool:
    """"Edwards wins FDA clearance …, … Medtronic": the headline's subject company
    (the capitalised phrase leading the cue's clause) is not the issuer."""
    a = cstart(title, cue_span[0])
    pre = title[a:cue_span[0]]
    cue_txt = title[cue_span[0]:cue_span[1]]
    m = _SUBJ_PHRASE.match(pre)
    if not m or not pre.strip():
        return False
    ends_with_verb = bool(re.search(r"\b(?:announces?|reports?|says?|unveils?|posts?|shares?|releases?)\s*$", pre, I))
    if not (_VERB_CUE.match(cue_txt) or ends_with_verb):
        return False
    subj = m.group(1)
    if _NOT_SUBJECT.match(subj) or MEDICAL_WORDS.search(subj) or _modality(subj) != ["unclassified"] \
            or _areas(subj, subj) != ["unclassified"]:
        return False
    return not any(r.search(subj) for r in fr)


def attribute(title: str, *, ticker: str, forms: tuple, cue_span: Optional[tuple] = None) -> bool:
    """§3.4.3 rule 3 — is `ticker` the SUBJECT of this title?"""
    title = title or ""
    forms = forms or name_forms(ticker, None)
    hits = _mentions(title, forms)
    if not hits:
        return False
    first = hits[0]
    if THIRD_PARTY.search(title[max(0, first - 40):first]):
        return False
    # fix round 2 (critic probe): with ticker LLY, "Amgen's MariTide Met Primary
    # Endpoint in Phase 3 Trial, Outperforming Lilly's Zepbound" pushed a LLY
    # Phase 3 positive; with BEAM, "Intellia's Clinical Hold Weighs on … Beam".
    # Another company's possessive BEFORE the cue, the issuer first named AFTER
    # it -> the issuer is not the subject.
    if cue_span and first > cue_span[0] and _rival_possessive(title[:cue_span[0]], forms):
        return False
    # fix round 3 (OOS grade 2026-09-29): the rival guard fired only when the
    # issuer was named AFTER the cue. "Labcorp Announces Availability of Roche's
    # Ventana … Assay, … Approved By FDA" credited LH with Roche's approval; "Edwards
    # wins FDA clearance …, setting up competition with AtriCure and Medtronic"
    # credited MDT. Wherever the issuer sits: another company's possessive owning
    # the thing before the cue, another company's product as the cue's object, or
    # another company as the headline's subject -> not the issuer's event.
    if cue_span:
        fr = _form_rx(forms)
        if _rival_owner_before(title, cue_span[0], hits, fr) or _rival_object_after(title, cue_span[1], fr, hits):
            return False
        # fix round 4 (critic #4): "Opdivo Gets FDA Nod …, Bristol Myers Squibb
        # Says" — the issuer REPORTING its own product is not a rival subject.
        if first >= cue_span[1] and _rival_subject(title, cue_span, fr) and not _issuer_reports(title, hits, fr):
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
    # fix round 4 (OOS grade #5): "Phase 1/2 … registrational expansion cohort met
    # the primary endpoint" — a pivotal / registrational token in the OUTCOME's
    # own clause lifts a lower phase to pivotal (never a "supports a registrational
    # path" talk token, never a future one — those were dropped above).
    from .store import _PHASE_RANK
    if _PHASE_RANK.get(best[2], 0.0) < _PHASE_RANK["pivotal"]:
        ca, cb = cstart(masked, aa), cend(masked, ab)
        for a0, b0, v in merged:                          # "pivotal Phase 2b/3" stays 2/3
            if v == "pivotal" and ca <= a0 and b0 <= cb and not _PIVOTAL_TALK.search(masked[max(0, a0 - 30):a0]):
                return "pivotal"
    return best[2]


_PIVOTAL_TALK = re.compile(r"\b(?:support\w*|enabl\w*|potential(?:ly)?|path(?:way)?s?\s+to(?:ward)?|inform\w*"
                           r"|pav\w*|toward\w*|for\s+a)\b" + GAP + r"{0,12}$", I)


def direction(masked: str) -> tuple:
    """§3.4.2-D -> (direction, first outcome-cue span)."""
    d, first, _sec = _direction(masked)
    return d, first


def _direction(masked: str) -> tuple:
    """(direction, first outcome-cue span, secondary_missed)."""
    m, neg, sec, first = masked, False, False, None
    for x in list(_PASSED_FUTILITY.finditer(m)):
        m = mask(m, x.start(), x.end())
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
        for x in re.finditer(p, m, I):
            # "Misses Primary Goal but Shows Statistically Significant Benefit
            # in Subgroup" (Sage, critic probe) is a MISS, not mixed.
            if _NOT_READOUT_DATA.search(m[cstart(m, x.start()):cend(m, x.end())]):
                continue
            pos = True
            first = first or (x.start(), x.end())
            break
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
    """'DAYBREAK', 'AZURE-1', 'REDEFINE-2', 'NCT06556368' — else None. Fix round 4
    (critic 2026-09-29): the SAME normaliser as the trial keys (`extract_trial_keys`)
    — "REDEFINE 1 Trial" and "REDEFINE 2 Trial" were both 'REDEFINE', so merge rule
    (ii) ("same trial at any earlier date") fused two different trials."""
    for k in extract_trial_keys(text):
        if k.startswith("NCT") or len(k.split("-")[0]) >= 4:
            return k
    return None


# ---------------------------------------------------------------------------
# fix round 3 — SUBJECT keys: what an event is ABOUT (trial acronym, NCT id,
# drug code, drug / product name). The push gate's repeat block, the topline
# claim and the store's merge rules compare them: two events whose keys are
# both present and DISJOINT are different trials / drugs and never merge or
# block each other (OOS 2026-09-29: GILD's islatravir Phase 3 and LLY's Jaypirca
# Phase 3 positives were swallowed by an earlier, unrelated topline); two that
# SHARE a key are the same story (PEN THUNDERBOLT re-reported 31 sessions later).
# Unknown is never guessed: no key -> [] and the old ticker + kind rule applies.
# ---------------------------------------------------------------------------
# Fix round 4 (critic 2026-09-29): a trial NAME keeps its number / suffix —
# "REDEFINE 1" -> REDEFINE-1, "PURPOSE 2" -> PURPOSE-2, "VENTURE-Oral" ->
# VENTURE-ORAL, "MAESTRO-NASH OUTCOMES" -> MAESTRO-NASH-OUTCOMES (never the bare
# generic tail OUTCOMES). A name is at most two capitalised words plus a trailing
# 1-2 digit number, adjacent to "trial / study / program"; a word carrying digits
# (a drug code, "KEYNOTE-689") is never glued to its neighbour.
_TW = r"(?:[A-Z][A-Z0-9]{2,}(?:-[A-Za-z0-9]+)*|[A-Z][a-z]+-\d+[A-Za-z]?)"
_TNUM = r"\d{1,2}[A-Za-z]?"
_TNAME = r"(?-i:" + _TW + r"(?:\s+" + _TW + r")?(?:\s+" + _TNUM + r"\b)?)"
_TRIAL_LIST = re.compile(r"(" + _TNAME + r"(?:\s*(?:/|,|&|\band\b)\s*" + _TNAME + r")*)"
                         r"(?=\s+(?:pivotal\s+|registrational\s+|confirmatory\s+)?(?:phase\s+\S+\s+)?(?:[\w-]+\s+)?"
                         r"(?:trials?|stud(?:y|ies)|programs?)\b)", I)
_TNUM_RX = re.compile(_TNUM)
_NCT = re.compile(r"(?-i:\bNCT\d{8}\b)")
_DRUG_CODE = re.compile(r"(?<![\w$.-])((?=[a-zA-Z]{0,4}[A-Z])[a-zA-Z]{1,5}-?\d{3,7}[A-Za-z]?)(?![\w-])")
_YEARISH = re.compile(r"^(?:FY|CY|Q|H|FQ)?-?(?:19|20)\d\d[A-Za-z]?$", I)
_MARKED = re.compile(r"(?<![\w-])([A-Za-z][\w-]{2,})\s*(?:\u00ae|\u2122|\((?:TM|R)\))")
_INN = re.compile(r"\b([a-z]{3,}(?:mab|tinib|ciclib|rafenib|lisib|parib|degib|rasib|glutide|trutide|patide|lintide"
                  r"|glipron|avir|evir|ivir|uvir|cept|leucel|temcel|siran|rsen|vedotin|deruxtecan|govitecan"
                  r"|mafodotin|ozogamicin|tesirine|delpar|gliflozin|xaban|sertib|metinib))\b", I)
_INN_NOT = frozenset({"concept", "concepts", "intercept", "except", "accept", "precept", "percept"})
_ROMAN = re.compile(r"(?:I{1,3}|IV|VI{0,3}|IX|X)")            # "Phase III" is not a trial name
_MUTATION = re.compile(r"[A-Z]\d{1,4}[A-Z]")                 # G12C, V600E, T790M — a biomarker
_CAPS = re.compile(r"(?-i:\b([A-Z][A-Z0-9]{3,}(?:-[A-Za-z0-9]+)*)\b)")
# 4+ letter capitals that name a disease, biomarker, body, market or newsroom
# word — never a product. Anything the area / modality / medical-word tables
# already match is dropped too.
_CAPS_NOT = frozenset({
    "TNBC", "NSCLC", "SCLC", "KRAS", "EGFR", "HER2", "BRCA", "BRAF", "PTEN", "NTRK", "FGFR", "ROS1", "IDH1", "IDH2",
    "CDK4", "PDL1", "MASH", "NASH", "COPD", "ADHD", "PTSD", "HFPEF", "HFREF", "ATTR", "IGAN", "DLBCL", "HIV-1",
    "COVID", "COVID-19", "GLP-1", "USPTO", "NYSE", "NASDAQ", "AMEX", "OTCQB", "OTCQX", "PDUFA", "SNDA", "SBLA",
    "ANDA", "CHMP", "MHRA", "PMDA", "NMPA", "UPDATE", "UPDATED", "BREAKING", "CORRECTION", "EXCLUSIVE", "ALERT",
    "NEWS", "REPORT", "WATCH", "PRESS", "RELEASE", "PHASE", "TRIAL", "STUDY", "DATA", "RESULTS", "TOPLINE",
    "POSITIVE", "NEGATIVE", "APPROVAL", "APPROVED", "CLEARANCE", "PIVOTAL", "GLOBAL", "CLINICAL", "WEEK", "WEEKS",
    "WITH", "FROM", "INTO", "THAT", "THIS", "FOR", "AND", "THE", "INC", "CORP", "LTD", "PLC", "ETF", "SPAC",
    "CEO", "CFO", "USA", "CRISPR", "MRNA", "RMAT", "PRIME"})
# Title-case product slot: "Results for Jaypirca", "Trial of Retevmo", "Approval
# for Its Trodelvy", "Evaluating Islatravir". The slot word is dropped when it is
# a generic word (below) or matches the medical / area / modality tables.
_SLOT = re.compile(r"(?:\b(?:results?|data|trials?|stud(?:y|ies)|approval|nod|clearance|designation|readout)\s+"
                   r"(?:of|for|with|on)\s+(?:its\s+|their\s+|the\s+)?|\bevaluating\s+|\bfor\s+its\s+)"
                   r"(?-i:([A-Z][a-z]{3,}[a-z0-9]*))\b(?!['\u2019]s\b)", I)
_SLOT_NOT = frozenset({
    "additional", "adults", "adult", "patients", "patient", "people", "children", "treatment", "use", "expanded",
    "broader", "full", "extended", "updated", "first", "second", "third", "late", "early", "oral", "once", "two",
    "three", "four", "its", "their", "the", "this", "that", "label", "advanced", "metastatic", "relapsed",
    "refractory", "chronic", "acute", "severe", "moderate", "weight", "combination", "monotherapy", "positive",
    "negative", "topline", "strong", "key", "primary", "pivotal", "global", "strengths", "supplemental",
    "companion", "device", "system", "test", "assay", "company", "breast", "lung", "skin", "heart", "liver",
    "kidney", "blood", "seasonal", "influenza", "stroke", "clot", "previously", "certain", "select", "new",
    "novel", "investigational", "late-stage", "mid-stage", "long-term", "higher", "lower", "high", "low",
    "potential", "multiple", "several", "both", "each", "prostate", "melanoma", "vaccine", "drug", "phase",
    "results", "data", "study", "studies", "trial", "trials", "program", "pivotal", "registrational",
    "biosimilar", "generic", "injection", "tablets", "capsules"})


def generic_key(k: str) -> bool:
    """fix round 4: a stored subject key too generic to identify a product in a
    headline on its own — a stop / disease / body / newsroom word. (Modality
    suffixes are NOT generic here: "zolimab" is a drug name.)"""
    u = (k or "").upper()
    base = u.split("-")[0]
    return (u in _CAPS_NOT or u in _TRIAL_STOP or base in _CAPS_NOT or base in _TRIAL_STOP
            or u.lower() in _SLOT_NOT or bool(MEDICAL_WORDS.fullmatch(u)) or _areas(u, "") != ["unclassified"])


def _generic_word(w: str) -> bool:
    return (w.lower() in _SLOT_NOT or bool(MEDICAL_WORDS.fullmatch(w)) or _modality(w) != ["unclassified"]
            or _areas(w, "") != ["unclassified"])


def _mostly_caps(t: str) -> bool:
    letters = re.findall(r"[A-Za-z]{2,}", t or "")
    return bool(letters) and sum(1 for w in letters if w.isupper()) > len(letters) / 2


def _trial_key_spans(t: str, *, ticker: Optional[str] = None, forms: tuple = ()) -> list:
    """[(start, end, KEY)] of every trial NAME adjacent to "trial / study /
    program", in text order (fix round 4). A list ("ISLEND-1 And ISLEND-2",
    "KEYNOTE-D46/EVOKE-03") gives one key per item; inside an item only the name
    next to the trial word counts; stop / disease / issuer words split it."""
    fr = _form_rx(forms)
    caps = _mostly_caps(t)

    def issuer_word(w: str, at: int) -> bool:
        if ticker and w.upper() == ticker.upper():
            return True
        return any(r.match(t, at) for r in fr)

    out = []
    for m in _TRIAL_LIST.finditer(t):
        items = [[]]
        for tm in re.finditer(r"[A-Za-z0-9-]+|[/,&]", m.group(1)):
            w, at = tm.group(0), m.start(1) + tm.start()
            if w in ("/", ",", "&") or w.lower() == "and":
                items.append([])
                continue
            items[-1].append((w, at))
        for it in items:
            segs, cur = [], []
            for w, at in it:
                if _TNUM_RX.fullmatch(w):
                    if cur:
                        cur.append((w, at))
                    continue
                u = w.upper()
                base = u.split("-")[0]
                if (u in _TRIAL_STOP or u in _CAPS_NOT or base in _TRIAL_STOP or base in _CAPS_NOT
                        or _ROMAN.fullmatch(w) or w.isdigit() or issuer_word(w, at)):
                    if cur:
                        segs.append(cur)
                    cur = []
                    continue
                if any(ch.isdigit() for ch in w):
                    if cur:
                        segs.append(cur)
                    segs.append([(w, at)])
                    cur = []
                    continue
                if caps and cur:
                    segs.append(cur)
                    cur = []
                cur.append((w, at))
            if cur:
                segs.append(cur)
            if segs:
                last = segs[-1]
                out.append((last[0][1], last[-1][1] + len(last[-1][0]), "-".join(x[0] for x in last).upper()))
    out.extend((m.start(), m.end(), m.group(0)) for m in _NCT.finditer(t))
    return sorted(out)


def extract_trial_keys(text: str, *, ticker: Optional[str] = None, forms: tuple = ()) -> list:
    """PURE: the trial-IDENTITY keys (trial names + NCT ids), in text order,
    de-duplicated. A subset of `extract_subjects`; the rest are drug / product
    keys (store.drug_keys_of)."""
    seen, out = set(), []
    for _a, _b, k in _trial_key_spans(text or "", ticker=ticker, forms=forms):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def extract_subjects(text: str, *, ticker: Optional[str] = None, forms: tuple = ()) -> list:
    """PURE: the sorted, upper-cased subject keys of a headline (see above)."""
    t = text or ""
    out = set()
    fr = _form_rx(forms)

    def issuer_word(w: str, at: int) -> bool:
        if ticker and w.upper() == ticker.upper():
            return True
        return any(r.match(t, at) for r in fr)

    spans = _trial_key_spans(t, ticker=ticker, forms=forms)
    out.update(k for _a, _b, k in spans)
    out.update(m.group(0) for m in _NCT.finditer(t))
    for m in _DRUG_CODE.finditer(t):
        v = m.group(1)
        if not _YEARISH.match(v) and not v.upper().startswith("NCT") and v.upper() not in _CAPS_NOT:
            out.add(v.upper())
    for m in _MARKED.finditer(t):
        if not issuer_word(m.group(1), m.start(1)):
            out.add(m.group(1).upper())
    for m in _INN.finditer(t):
        if m.group(1).lower() not in _INN_NOT:
            out.add(m.group(1).upper())
    if not _mostly_caps(t):
        for m in _CAPS.finditer(t):
            w = m.group(1)
            base = w.split("-")[0]
            if any(a <= m.start(1) < b for a, b, _k in spans):
                continue                                    # a word of a trial NAME is not a product
            if w in _CAPS_NOT or w in _TRIAL_STOP or issuer_word(w, m.start(1)) or _CONGRESS_CS.fullmatch(w) \
                    or _MUTATION.fullmatch(w) or _YEARISH.match(w) or _generic_word(w) \
                    or base in _CAPS_NOT or base in _TRIAL_STOP or _generic_word(base):
                continue
            out.add(w.upper())
    for m in _SLOT.finditer(t):
        w = m.group(1)
        if not _generic_word(w) and not issuer_word(w, m.start(1)):
            out.add(w.upper())
    for pm in _POSSESSIVE.finditer(t):                      # "<issuer>'s <Product>"
        if not issuer_word(pm.group(1), pm.start(1)):
            continue
        nm = re.match(r"\s+(?-i:([A-Z][\w-]{3,}))", t[pm.end():])
        if nm and not _generic_word(nm.group(1)):
            out.add(nm.group(1).upper())
    return sorted(out)


def subjects_disjoint(a, b) -> bool:
    """Both carry subject keys and share none -> different trials / drugs."""
    sa, sb = {str(x).upper() for x in (a or []) if x}, {str(x).upper() for x in (b or []) if x}
    return bool(sa) and bool(sb) and not (sa & sb)


def subjects_overlap(a, b) -> bool:
    sa, sb = {str(x).upper() for x in (a or []) if x}, {str(x).upper() for x in (b or []) if x}
    return bool(sa & sb)


# ---------------------------------------------------------------------------
# fix round 3 — MATERIALITY class of an FDA approval (HIS CALL: taxonomy
# PUSH_MATERIAL_ONLY decides whether these push; default = today's behaviour).
# A property of the event like modality — never a change of its subtype.
# ---------------------------------------------------------------------------
MATERIALITY_CLASSES = ("device_clearance", "label_update", "generic_formulation", "biosimilar")
_MAT_BIOSIMILAR = re.compile(r"\bbiosimilar\w*|\binterchangeab\w*", I)
_MAT_GENERIC_FORM = re.compile(
    r"\badditional strengths?\b|\bnew strengths?\b|\b(?:vial|syringe|bag|bottle|pen)\s+presentations?\b"
    r"|\bpresentations?\s+of\b|\bnew formulation\b|\breformulat\w*|\bready[- ]to[- ](?:use|dilute|administer)\b"
    r"|\bpre-?mixed\b|\binjection\s+solution\b|\binjection,?\s+USP\b|\b505\(b\)\(2\)", I)
_MAT_LABEL_UPDATE = re.compile(
    r"\bmaintenance dos(?:e|es|ing)\b|\bdos(?:e|es|ing)\s+(?:every|interval|regimen|schedule|frequency|option)\b"
    r"|\bevery\s+(?:\w+|\d+)\s+(?:weeks|months)\b|\b(?:extended|less frequent|new)\s+dosing\b"
    r"|\blabel(?:ing)?\s+(?:update|change)\b|\bupdate[ds]?\s+to\s+(?:the\s+)?(?:\w+\s+)?(?:product\s+)?label\b"
    r"|\bupdated\s+(?:\w+\s+)?label\b|\bself-administ\w*|\bat-home\s+administ\w*", I)


# fix round 4 (OOS grade #3): a SUPPLEMENTAL application (sNDA / sBLA), a
# manufacturing-site approval or a packaging change is a label update — it was
# typed `novel` / `label_expansion` with materiality None, so the switch could
# never reach it. Read on the cue's clause and the summary's first sentence.
_MAT_SUPPLEMENT = re.compile(
    _cs(r"\bs(?:NDA|BLA)s?\b") + r"|\bsupplemental\s+(?:new\s+drug|biologics?\s+license)\s+applications?\b"
    r"|\bmanufacturing\s+(?:site|facilit(?:y|ies)|plant)\b"
    r"|\b(?:at|for)\s+(?:its\s+|the\s+|a\s+)?(?:[\w,.'-]+\s+){0,3}(?:site|facility|plant)\b"
    r"|\bpackag(?:e|ed|ing)\b|\bcarrying\s+case\b", I)


def first_sentence(text: str) -> str:
    """The first sentence of an article summary (≤ 400 chars)."""
    t = (text or "").strip()
    if not t:
        return ""
    return re.split(r"(?<=[.!?])\s+(?=[A-Z\"'\u201c])", t, maxsplit=1)[0][:400]


def materiality_class(subtype: Optional[str], clause: str, text_all: str = "") -> Optional[str]:
    """device_clearance / label_update / generic_formulation / biosimilar, else None."""
    if subtype == "device_clearance":
        return "device_clearance"
    if _MAT_BIOSIMILAR.search(clause or "") or _MAT_BIOSIMILAR.search(text_all or ""):
        return "biosimilar"
    if _MAT_LABEL_UPDATE.search(clause or ""):
        return "label_update"
    if _MAT_SUPPLEMENT.search(clause or "") or _MAT_SUPPLEMENT.search(first_sentence(text_all)):
        return "label_update"
    if _MAT_GENERIC_FORM.search(clause or ""):
        return "generic_formulation"
    return None


def _regulator_exus(t: str) -> Optional[str]:
    for name, rx in EXUS_REGULATORS:
        if re.search(rx, t):
            return name
    return None


def _approval_subtype(clause: str) -> str:
    if re.search(r"tentative", clause, I):
        return "tentative"
    # fix round 2 (live run): ANIP "Final FDA Approval Of Its Abbreviated New
    # Drug Application" and LNTH "…Determined to be Bioequivalent and
    # Therapeutically Equivalent" were typed NOVEL (and pushed).
    if re.search(_cs(r"\bANDA\b") + r"|\bgeneric\b|biosimilar|abbreviated new drug application"
                 r"|bioequivalen\w*|therapeutic(?:ally)? equivalen\w*", clause, I):
        return "generic"
    if re.search(r"accelerated", clause, I):
        return "accelerated"
    if re.search(r"emergency use authori[sz]ation|" + _cs(r"\bEUA\b"), clause, I):
        return "eua"
    if re.search(r"\bclear(?:s|ed|ance)\b|510\(k\)|\bDe Novo\b|\bPMA\b", clause, I):
        return "device_clearance"
    # fix round 2 (live run: MRK "FDA Approves Update To US Product Label For
    # WINREVAIR" typed novel): a label update is a label change.
    if re.search(_cs(r"\bs(?:NDA|BLA)\b") + r"|supplemental (?:new drug|biologics? license) application"
                 r"|label expansion|expanded (?:indication|label|approval)"
                 r"|additional indication|\b(?:for|in) (?:adolescents|children|pediatric|paediatric|younger patients)\b"
                 r"|label update|update to (?:the )?(?:U\.?S\.? )?(?:product )?label|updated (?:product )?label",
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
         "cue": None, "cue_span": None, "from_commentary": False, "subjects": [], "trial_keys": [],
         "materiality": None}
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
    if COMMENT.search(t0) or COMMENT_FORM.search(t0):
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
                if typ == "fda_crl" and sub == "crl" and x.group(0) == "CRL" and (
                        _CRL_TICKER.search(t0[:x.start()])
                        or (not t0[:x.start()].strip() and t0[x.end():].lstrip().startswith(":"))):
                    continue                                    # "(CRL)", "$CRL", "NYSE: CRL", "CRL: Charles River …"
                if typ == "fda_crl" and sub == "crl" and (_CRL_BACKREF.search(t0[max(0, x.start() - 40):x.start()])
                                                         or _RESUBMIT.search(t0[:x.start()])):
                    continue
                if typ == "readout_scheduled" and re.search(
                        r"financial results|earnings|fiscal|quarter(?:ly)?\s+(?:\d{4}\s+)?(?:financial|results"
                        r"|earnings|report)", cl, I):
                    continue
                if typ == "regulatory_filing" and sub == "ind_cleared" and re.search(
                        r"\b(?:pilot|guidance|policy|framework|program)\b", cl, I):
                    continue
                if typ == "fda_approval":
                    if (_APPR_ADJ.fullmatch(x.group(0).strip())
                            or _APPR_NOT_MARKETING.search(t0[cstart(t0, x.start()):cend(t0, x.end())])
                            or _APPR_BACKREF.search(t0[max(0, x.start() - 30):x.start()])):
                        intent = True
                    w = _APPROVAL_WORD.search(x.group(0))
                    if w:
                        wa, wb = x.start() + w.start(), x.start() + w.end()
                        if (PENDING_B.search(t[max(0, wa - 20):wa]) or PENDING_A.search(t[wb:wb + 25])
                                or _APPR_NEG_B.search(t[max(0, wa - 30):wa]) or _APPR_NEG_A.search(t[wb:wb + 40])):
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
                    if re.search(r"vot(?:es|ed)\b" + GAP + r"{0,20}(?:in favor|favorabl|to (?:support|recommend))"
                                 r"|\b(?:recommend\w*|backs?|backed|endors\w*|supports?)\s+(?:the\s+)?approval", t0, I):
                        ev["direction"] = "positive"
                    elif re.search(r"vot(?:es|ed)\b" + GAP + r"{0,25}against|negative vote", t0, I):
                        ev["direction"] = "negative"
                if typ == "trial_milestone":
                    ev["phase"] = extract_phase(t[x.start():cend(t, x.end())], (0, 1), drop_future=False)
                if typ == "fda_approval":
                    clause0 = t0[cstart(t0, x.start()):cend(t0, x.end())]
                    ev["subtype"] = _approval_subtype(clause0)
                    ev["materiality"] = materiality_class(ev["subtype"], clause0, context or "")
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
            d, anchor, sec = _direction(t)
            reg_talk = d == "positive" and _NOT_READOUT_REG.search(t0)
            if d == "positive" and _NOT_READOUT_DATA.search(t0):
                d = "unknown"                               # OLE / post-hoc / published: no new readout
            if not INTENT_B.search(pre) and not reg_talk:
                sneg = any(re.search(sp, t, I) for sp in STOP) and not _EFFICACY_STOP.search(t)
                if sneg and d == "unknown":
                    d = "negative"
                elif sneg and d == "positive":
                    d = "mixed"
                d_from = "title"
                # fix round 4 (OOS grade #6): an undirected readout headline
                # ("Demonstrated Meaningful …", "Boosts Survival") takes its
                # direction from the summary's FIRST sentence when that one is
                # directed and is not post-hoc / OLE / publication talk.
                if d == "unknown" and context:
                    s1 = first_sentence(context)
                    if s1 and not _NOT_READOUT_DATA.search(s1) and not _NOT_READOUT_REG.search(s1):
                        d1, _a1, sec1 = _direction(s1)
                        if d1 in ("positive", "negative", "mixed"):
                            d, sec, d_from = d1, sec1, "summary"
                events.append(_ev("topline", None, direction=d, phase=extract_phase(t, anchor or cue),
                                  secondary_missed=bool(sec), cue=t0[cue[0]:cue[1]], cue_span=cue,
                                  direction_from=d_from))
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
        x = next((y for y in re.finditer(rx, t, I) if not _DEAL_TALK.search(t[y.end():y.end() + 20])), None)
        if x:
            events.append(_ev("deal", sub, cue=t0[x.start():x.end()], cue_span=(x.start(), x.end())))
            t = mask(t, x.start(), x.end())
            break
    for sub, rx in FINANCING:
        x = re.search(rx, t0 if sub == "secondary_holders" else t, I)
        if x and sub == "ipo" and _IPO_OTHER.search(t0[max(0, x.start() - 20):x.start()]):
            x = None
        if x:
            events.append(_ev("financing", sub, dilutive=(sub != "secondary_holders"),
                              cue=t0[x.start():x.end()], cue_span=(x.start(), x.end())))
            break

    # trial name on the events that carry one
    trial = extract_trial(t0)
    subjects = extract_subjects(t0, ticker=ticker, forms=forms)
    tkeys = extract_trial_keys(t0, ticker=ticker, forms=forms)
    for e in events:
        if e["event_type"] in ("topline", "conference_data", "trial_milestone", "readout_scheduled"):
            e["trial"] = trial
        e["subjects"] = list(subjects)
        e["trial_keys"] = list(tkeys)

    # 10 medical gate (§3.4.6)
    medical = bool(issuer_medical) or medical_words_hit(t0)
    kept = []
    for e in events:
        if e["event_type"] in GATED_TYPES and not (ticker and medical):
            out["dropped"].append(f"non_medical_event:{e['event_type']}")
            continue
        # fix round 2 (live run board): "Merck Canada Partners with the Montreal
        # Museum of Fine Arts", "Glaukos Partners with … Stephen Curry", "Veeva
        # Expands Amgen Partnership With Global Vault CRM" were medical DEALS on
        # the issuer flag alone -> a partnership / licence / milestone needs a
        # medical word in its own title. M&A OF a medical issuer stays (a
        # takeover is material whatever the headline says about it).
        if e["event_type"] == "deal" and e.get("subtype") != "mna" and not medical_words_hit(t0):
            out["dropped"].append("non_medical_event:deal")
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
