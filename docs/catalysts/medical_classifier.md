# 🧬 Medical headline classifier (`catalysts/medical/classify.py`)

Ajay, 2026-09-29: *"…sector them separatively like new fdaapprovals or break throughs like mrnaresearch…"*

Deterministic word rules, **no model** (a local-model assist is HIS CALL #5, not built). Pure: stdlib `re`
only, no I/O. `RULES_VERSION = "med-rules-v3"` (`taxonomy.py`; v3 = fix round 2, 2026-09-29). UNMEASURED — setup: pending study.

Port of the reference harness `scratchpad/medcat_rev/rules_v2_final.py` (92/92 cases) and `attr.py`
(18/18), plus the v1 tables the harness never carried (fda_approval subtypes, ex-US approval, safety,
deal, financing, modality, area, trial names). The spec is `medical_catalysts_spec.md` §3.2–§3.4.

## Interface

```python
classify(title, *, context="", ticker=None, forms=(), issuer_medical=None) -> dict
name_forms(ticker, name) -> tuple          # regex strings naming the issuer
attribute(title, *, ticker, forms, cue_span=None) -> bool
direction(masked) -> (direction, first_outcome_span)
extract_phase(masked, anchor, *, drop_future=True) -> str | None
extract_trial(text) -> str | None
medical_words_hit(title) -> bool           # §3.4.6 gate words + any modality / area hit
```

`title` decides event types (precision); `title + context` decides modality and area (recall).
Output: `events` (each `event_type, subtype, direction, phase, regulator, trial, cue, cue_span,
from_commentary`, plus `dilutive` / `secondary_missed` / `congress` / `partial` where they apply),
`modality`, `areas` (priority-ordered, `["unclassified"]` when nothing matched — never guessed),
`roundup`, `commentary`, `merge_only`, `attributed`, `dropped`, `reasons`, `rules_version`.

## Order (fixed; each step sees the text the previous steps left)

1. **roundup** → no events (listicles, sector updates, law-firm spam).
2. **commentary** → no events (`Why …`, `Q&A:`, `A Look At …`, a `?`, transcripts, valuation /
   price-target / fair-value / under-/over-/fully-valued / bull-/bear-case pieces).
3. **merge_only** — a price story (`stock/shares … soars`, the company name + a price verb, `+N%`,
   `just got/won`): its events may MERGE into an existing event, never CREATE one.
4. Unrelated approvals masked (shareholders / board / Nasdaq / court / merger … approve).
5. **Background pre-pass** — after a head cue, `after / following / based on …` to the clause end is
   masked ("FDA Approves … After Phase 3 Success" is an approval only).
6. **Precedence ladder**: `fda_crl → fda_revoked → clinical_hold → regulatory_filing → pdufa → adcom →
   designation → conference_data → readout_scheduled → trial_milestone → fda_approval → exus_approval`.
   A cue with INTENT before (≤ 25 chars: *plans to, expects, may, could, eyes…*) or after (≤ 15 chars:
   *planned, expected…*) is suppressed and its clause masked. One event per type per title.
7. **topline** + direction + phase (skipped when a trial_milestone fired).
8. `discontinued` fallback (halt / terminate / discontinue with no outcome cue).
9. **safety / deal / financing** on what is left.
10. **Medical gate** — `deal`, `financing`, `safety`, `trial_milestone` need a resolved issuer AND
    (a medical issuer OR a medical word in the title); else `dropped: non_medical_event:<type>`.
11. **Attribution** — the issuer must be the subject (first clause or the cue's clause; never behind
    *race for / vs / than / including / reshape …*).
12. **Modality / area** over title + context; congress names add their area (ESMO → oncology…).

Masking replaces text with spaces, so every `cue_span` still indexes the original title.

## Direction (topline / conference / adcom)

- SECONDARY-MISS (`secondary endpoint … not met / missed`) → `mixed`, never negative, never high impact.
- NEG first, masked from its start to the clause end: *did not / failed to / not … meet · achieve ·
  reach · show · demonstrate · hit*, *missed … primary … endpoint*, *no statistically significant*,
  *futility*, *trial failed*, *setback*, *fell short of … primary*. **Bare `failure` is not a cue**
  (heart / kidney / liver failure are diseases).
- POS on what is left: *met / meets / hits (Phase N) primary endpoint*, *statistically significant*,
  *positive (up to two words) data / results / topline …*, *non-inferior*, *superior to*, *pass(ed) the
  trial*, *trial win*.
- Result: positive + (negative or secondary miss) → mixed; positive; negative; secondary miss alone →
  mixed; else `unknown` (never guessed).

## Phase

The phase token NEAREST the first outcome cue wins. Dropped: tokens after *plan / start / initiate /
advance / toward / next …* (future phases) and tokens followed by *enabling / ready* ("Phase 3 Enabling
… from Phase 2" → 2). `pivotal` right before a numbered phase collapses into it. `2b/3` → `2/3`.
A trial_milestone reads its own clause without the future filter ("initiation of the registrational
Phase 3 ZUPREME program" → 3).

## High impact (`taxonomy.is_high_impact`, the ONLY definition)

| Type | High when |
|---|---|
| fda_approval | subtype not tentative / generic, regulator FDA |
| fda_crl | crl, refuse-to-file, rejection (not a withdrawn application) |
| topline | phase 3 / 2/3 / pivotal AND positive or negative |
| designation | Breakthrough Therapy |
| clinical_hold | placed (incl. partial) |
| everything else | never |

`HIGH_IMPACT_TEXT` is joined from `HIGH_IMPACT_TABLE` (rules panel, board, push detail).

## Attribution

`name_forms`: suffix-stripped full name ("Eli Lilly and Company" → "Eli Lilly"), the distinctive word
(first ≥ 4-letter token that is not generic and not a modality word → **Lilly**, never "CRISPR"),
abbreviation aliases (BMS, J&J / Janssen, MSD, GSK, Roche / Genentech — case-sensitive), `$TICKER`,
`(TICKER)` / `(NASDAQ: TICKER)`, and the bare ticker (case-sensitive) when it has ≥ 4 letters.
The name comes from `sepa.company_names.name_for`, else the SEC `company_tickers.json` title.

## Fix round 2026-09-29 (critic grading on the live pass)

Precision fixes, each pinned by a fixture row (`g01`–`g24`):
- a parenthesised ticker `(CRL)` / `NYSE: CRL` is never a complete response letter (Charles River);
- a go-ahead / nod / clearance **for a study / trial** is `regulatory_filing/ind_cleared`, never an
  approval ("Prime Medicine Gets FDA Green Light for Gene Editing Study");
- valuation pieces (*undervalued, fully valued, fair value, bull case*) are commentary (LNTH, MRK,
  CGEM, INCY, IMVT, COGT);
- `Phase 2b/3` is Phase 2/3 (MRK BRUNELLO → high impact);
- *Positive One-Year Data* is positive (KYTX); *Meets Phase 3 Primary Endpoint* is positive (MIRM);
- *Phase 3 Enabling … from Phase 2* is Phase 2 (ACAD); *collaboration revenue* is not a deal (ZYME);
- 510(k) / De Novo only with a clearance / grant word (a 510(k) *submission* is never an approval);
- eponyms take an optional possessive ("Parkinson Disease" → neurology, #38).

**Replay of the 710 articles the live pass stored (2026-09-24..28), real classifier + branch merge:**
51 events, 10 high impact (9 with an issuer): KOD Ph3 positive, MIRM Ph3 positive, MRK Ph2/3 positive,
FDA approvals for ABBV, INCY, LLY, MIRM, MRK, QGEN (device clearance), MCT8 (unresolved, never pushed).
The stand-in's false highs (Charles River CRL, PRME IND, LNTH / MRK valuation pieces) are gone.
Known recall gap (not widened — HIS CALL): "Misses Primary **Goal**" / "Misses **Main** Endpoint" give
no topline (the NEG rule needs *primary … endpoint*). *Goal / target* fixed 2026-09-29 (fix round 2); *Main* Endpoint still open.

## How to add a rule

1. Add the row to `backend/tests/fixtures/medical/headlines.json` (real title, `source`, expected events).
2. Change the one regex in `classify.py` (hand-kept lists drift — never widen one without a row).
3. Add a named NEGATIVE to `tests/test_med_classify.py` if the change could over-fire.
4. Purge caches, run `tests/test_med_classify.py`; bump `RULES_VERSION` when a stored event could
   now classify differently.

HIS CALLs: device clearances (510(k) / "FDA Clears …") are high impact under the §3.8 table — QGEN's
panel clearance would ring; exclude `device_clearance` from high impact if that is noise. Two different
approvals of the same type on one name within ±3 sessions collapse into one event (LLY), and the
21-session recap then mutes the second one on the phone.

## Fix round 2 — 2026-09-29 (`med-rules-v3`)

Two independent checks found the v2 rules pushing wrong things: a critic probe of 63 new headlines
(about 40 of them traps) measured **high-impact push precision 0.44** (fda_approval 0.31), and the live
dry run over 09-21..09-28 had **5 of 16 would-push events wrong** (RVMD, MIRM recap, ANIP, VTGN, LLY
merge) plus 4 questionable. Every failing headline is now a fixture row (`f01`–`f60`, source C = critic,
L = live; `f55`–`f60` are positive controls that must still push) and `test_fix_round_2_push_set_*`
pins the exact push set. What changed:

- **An approval word is not an approval**: a negative / pending verb before it (*delays, declines,
  blocks, withholds, lacks, loses, panel, advisers, recommends, backs*), *delayed / pushed back* after it,
  a non-marketing clause (*to proceed / begin*, IDE, expanded access, manufacturing facility, a SAFETY
  label change), the adjective *FDA-Approved / FDA-Cleared*, or a background preposition right before
  the cue (*…Following FDA Approval of Revolution Medicines'…*). *FDA Panel / FDA Advisers* are adcom;
  *Approval to Proceed With Phase 3* is an IND-style go-ahead.
- **Subtypes**: *Abbreviated New Drug Application*, *bioequivalent*, *therapeutically equivalent* →
  generic (not high impact: ANIP, LNTH); *label update* / *in pediatric patients* → label expansion
  (still high impact under §3.8).
- **CRL as background** (*Following / Regarding / Addresses … CRL*, a resubmission named before it,
  `$CRL`, `CRL:` ticker prefix) is no CRL. A CRL whose release adds *plans to resubmit* still fires.
- **Holds**: removal / resolved / cleared / *FDA Lifts Hold* → lifted; a *response to a clinical hold
  letter* is its own low-impact subtype `response`.
- **Toplines**: a passed / survived futility look is masked; a positive in a subgroup / post-hoc clause
  does not rescue a primary miss (Sage → negative); positive + OLE / post-hoc / *published in* →
  direction unknown (VTGN); positive + end-of-phase / feedback / design → no topline; *early for
  efficacy* is a positive readout; *misses primary goal / target* is negative; an *FDA setback* is not
  a readout; analyst upgrades / ratings / *buy the dip* are commentary.
- **Attribution**: another company's possessive before the cue with the issuer first named after it →
  not the subject (LLY in *Amgen's MariTide … Outperforming Lilly's Zepbound*).
- **Board-only**: partnerships / licences / milestones need a medical word in their own title (the
  Montreal museum, Stephen Curry, Veeva CRM); M&A of a medical issuer stays; *acquired* before a
  condition is an adjective (RYTM); *buyout talks* and someone else's IPO are no events; *slumps*
  next to stock/shares is a price story; diabetic eye disease is ophthalmology, not cardio-metabolic.

Pipeline fixes in the same round: a snapshot print of 0.0 is no price (110 of 115 live events showed
−100%); a directed topline lifts an earlier `topline_unknown` on the same name instead of making a second
row (CLDX, ALKS); Finnhub article keys carry the ticker so a joint release reaches both issuers (MIRM +
INCY); the Healthcare read applies the sector override.

**Numbers (same set tuned against — not independent; re-grade on fresh headlines):** critic probe
0.44 → 0.90 push precision (19/21; the two left are ALKS partner CRL — HIS CALL — and Sage, which the
probe labelled not-high but is a Phase 3 primary miss). Replay of the live run's 1,478 stored
articles: 20 → 16 high-impact events; RVMD, LNTH, ANIP, VTGN gone; CLDX's two rows are one.

Still HIS CALL: device clearances (QGEN, SIBN) and label updates (MRK WINREVAIR) are high impact under
§3.8; partner CRLs ring on the partner (ALKS); distinct approvals on one name inside ±3 sessions still
merge (LLY), and the 21-session recap mutes a second one.

## 2026-09-29 — fix round 3 (OOS grade: strict 0.56 → see numbers)

Six defects from the out-of-sample grade, each a row in `tests/test_med_fix3_2026_09_29.py`:
the opinion FORM (a quoted rating, "Strong Buy/Sell", "Name: <rating> …") is commentary (PTGX);
the rival guard fires wherever the issuer sits — another company's possessive owning the thing
before the cue, another company's product as the cue's object, another company as the verb-led
cue's subject, and "competition with / a win for …" (LH Roche assay, MDT/Edwards); "meets … endpoints"
with up to four words between (never "met with FDA") is positive (GILD ISLEND); every event carries
`subjects` (`extract_subjects`: trial acronyms incl. "Libretto-432" and lists "ISLEND-1 And ISLEND-2",
NCT ids, drug codes, ®/™-marked names, INN stems, capitalised brands, "Results for <Brand>", the
issuer's possessive product — never a disease / biomarker / year / Roman numeral / company word);
merges of trial readouts never cross disjoint subjects (an undirected topline no longer merges into
another trial); every FDA approval carries a `materiality` class (device_clearance / label_update /
generic_formulation / biosimilar — a property, never a subtype change). RULES_VERSION left at v3
(the pinned version test was not in scope). Known limit: brand vs INN ("Retevmo" / "selpercatinib")
are different keys, so disjointness splits trial readouts only; approvals keep ticker + kind.

**Numbers (the OOS set is now TUNED against — no longer independent):** replay of the 80 names'
stored raw rows (scratchpad `medcat_r3/replay.py`, liquidity gate neutralised as the grader did):
18 → 18 pushes; strict 10/18 = 0.56 [0.34, 0.75] → 12/17 graded = 0.71 [0.47, 0.87] (+ LH 08-10
ungraded); letter 15/18 = 0.83 → 17/17 = 1.00 [0.82, 1.00]. Out: PTGX, LH 08-04 (Roche), PEN 07-27
rehash. In: GILD islatravir and LLY Jaypirca Phase 3 positives (both "missed_by_recap" in the grade),
LH 08-10 (Labcorp's own CDx, ungraded). With `PUSH_MATERIAL_ONLY = True`: 13 pushes, strict 11/12
graded, but PEN THUNDERBOLT (graded material) is dropped with MDT, LLY EBGLYSS and AMRX ×2.

## 2026-09-29 — fix round 4 (critic of round 3 + generic bugs from a FRESH OOS grade)

A second independent grade (80 new names, 2025-10-01..2026-01-31, verdict SHIP-SHADOW, strict
0.53 [0.36, 0.70]) stays OUT-OF-SAMPLE: nothing was tuned on its rows; every test row in
`tests/test_med_fix4_2026_09_29.py` is a synthetic headline of the same form or a critic probe.
Trial keys keep their number / suffix (`extract_trial_keys`: "REDEFINE 1" → REDEFINE-1, "PURPOSE 2" →
PURPOSE-2, "VENTURE-Oral" → VENTURE-ORAL, "MAESTRO-NASH OUTCOMES" → MAESTRO-NASH-OUTCOMES, never the
bare tail; a word carrying digits is never glued to a neighbour) and `extract_trial` uses the same
normaliser; events carry `trial_keys` beside `subjects`. `store.different_story` compares trial keys
first, then drug keys of the SAME class only (brand vs brand, INN / code vs INN / code — "Retevmo" and
"selpercatinib" may be one drug), and now splits FDA approvals too (another product's approval no
longer merges into / recaps the first); `store.same_subject` (the rehash and event-age link) needs a
shared TRIAL key for a trial kind. Attribution: the issuer as the headline's reporter ("…, <Issuer>
Says / Announces") or colon-prefix subject ("<Issuer>: FDA Approval of <Product>'s …") owns the
product; a disease possessive ("For Alzheimer's …") is never a rival. A pivotal / registrational token
in the outcome's own clause lifts a lower phase to pivotal (never "supports a registrational path",
never a future phase, never "Pivotal Phase 2b/3"). An undirected readout headline takes its direction
from the summary's FIRST sentence when that is directed and not post-hoc / regulatory talk
(`direction_from = "summary"`). "Publication in / of" is not a new readout. Materiality: an sNDA /
sBLA, a manufacturing-site approval or a packaging change is `label_update` (clause or the summary's
first sentence) — the switch stays OFF. Known limit: "<Issuer>: FDA Approves <Rival>'s Test" is now
attributed to the issuer (the colon rule cannot tell a product from a company without a lexicon).
