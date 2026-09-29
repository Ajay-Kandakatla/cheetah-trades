# 🧬 Medical headline classifier (`catalysts/medical/classify.py`)

Ajay, 2026-09-29: *"…sector them separatively like new fdaapprovals or break throughs like mrnaresearch…"*

Deterministic word rules, **no model** (a local-model assist is HIS CALL #5, not built). Pure: stdlib `re`
only, no I/O. `RULES_VERSION = "med-rules-v2"` (`taxonomy.py`). UNMEASURED — setup: pending study.

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
no topline (the NEG rule needs *primary … endpoint*).

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
