# SEPA v2 — Design Plan

**Status:** DRAFT — awaiting user sign-off before implementation.
**Companion docs:** `docs/SEPA_CONTRACTS.md` (v1 locked behavior).
**Trigger:** v1's VCP monotonic-shrinkage gate (≤75% of prior, ALL contractions)
rejects 100% of names on a 1357-name Russell 1000 analyzed pool, producing
only 1 candidate when the user historically sees ~150. Spec §12 forbids
relaxing v1 — SEPA v2 is the documented escape hatch.

---

## 1. Why v2 exists

Per `docs/SEPA_CONTRACTS.md` §12:

> Never change `SCORE_WEIGHTS`, the 8 trend template gates, the VCP rules,
> the stage classifier... without explicit user sign-off *before* any code
> is written. ... any agent or contributor who's tempted to "upgrade" SEPA
> — even with a backtest showing the new weights are "better" — must
> instead build a **SEPA v2 page** (separate route, separate score table,
> separate UI) where the new formula runs in parallel without affecting the
> v1 list.

v2 is **not** a replacement for v1. It's a parallel sandbox. v1 keeps
shipping its candidate list to the live `/sepa` page (locked formula, real
trading dependency). v2 is the comparison view where formula experiments
prove themselves over weeks of live observation before any promotion.

**No v2 → v1 promotion happens automatically.** Promotion is a separate
RFC, written after live observation makes it obvious which v2 candidates
turned into actual successful trades and which v1 candidates were false
negatives that v2 caught.

---

## 2. Scope — what's different in v2

Initial v2 differs from v1 in **exactly one place** so we can isolate the
experiment:

| Module / rule              | v1 (locked)                              | v2 (experiment)                                                                |
|----------------------------|------------------------------------------|--------------------------------------------------------------------------------|
| `vcp.detect()` monotonic   | `all(d[k] ≤ d[k-1] * 0.75)`              | Directional trend: `final < first` AND ≤1 mid-base contraction violates the ≤0.75 rule |
| Trend template (8 gates)   | unchanged                                | unchanged                                                                       |
| Stage classifier           | unchanged                                | unchanged                                                                       |
| `SCORE_WEIGHTS`            | unchanged                                | unchanged                                                                       |
| Rating thresholds          | unchanged                                | unchanged                                                                       |
| RS rank, ADR, base count   | unchanged                                | unchanged                                                                       |
| Volume / liquidity         | unchanged                                | unchanged                                                                       |

**Why only the monotonic gate?** Smallest possible change that addresses the
1-candidate symptom. If v2 starts surfacing 150 candidates of which most are
trash, we know the relaxation went too far — easy to dial back to ≤2 violations,
≤3 violations, etc. without touching anything else. If we change multiple things
at once, we can't tell which one is responsible for the outcome.

**Numerical specifics for v2 (NEEDS PDF PAGE CITATION — see §6 open questions).**

Proposed implementation:

```python
# backend/sepa_v2/vcp.py — copy of v1 vcp.py with this one change:
violations = sum(1 for k in range(1, len(depths)) if depths[k] > depths[k-1] * 0.75)
overall_shrinking = depths[-1] < depths[0]
monotonic_v2 = overall_shrinking and violations <= 1
```

Interpretation: the BASE as a whole must contract from start to end, AND
at most one mid-base contraction is allowed to be wider than 75% of its
predecessor. Catches Minervini's textbook "about half the previous" while
tolerating real-world swing-detection noise.

Conservative alternative if v2 over-produces: `violations <= 0` with the
`overall_shrinking` requirement still in place — same as v1 effectively.

---

## 3. Architecture

### Backend

```
backend/sepa_v2/
  __init__.py
  scanner.py          ← thin wrapper around backend/sepa/scanner.py
                        that swaps the vcp import for sepa_v2.vcp
  vcp.py              ← the ONE file with the relaxed gate
  store.py            ← writes/reads sepa_v2_scans Mongo collection
                        (separate from sepa_scans — DO NOT cross-write)
```

The scanner is a *thin wrapper* — it imports everything from `backend/sepa/`
except `vcp`, which it overrides. This makes the diff between v1 and v2
trivially auditable: `git diff backend/sepa/vcp.py backend/sepa_v2/vcp.py`
should show only the monotonic block.

### Routes (new, all gated on the same `portfolio`-style feature flag for safety)

```
GET  /sepa-v2/scan                    ← latest cached v2 scan
POST /sepa-v2/scan                    ← trigger fresh v2 scan
GET  /sepa-v2/candidate/{symbol}      ← v2 detail
GET  /sepa-v2/compare                 ← diff endpoint: which symbols are
                                         v1-only, v2-only, or both
```

### Mongo collections

| Collection           | Purpose                                                    | Indexes                            |
|----------------------|------------------------------------------------------------|------------------------------------|
| `sepa_v2_scans`      | One doc per scan run, mirrors `sepa_scans` shape           | `generated_at desc`                |
| `sepa_v2_candidates` | One doc per (scan_id, symbol) row, mirrors `sepa_candidates` | `(scan_id, symbol)`, `score desc` |

### Cron

```cron
# Run v2 scan 5 min AFTER v1 scan so v2 doesn't compete for Massive rate
# budget during the critical v1 window.
40 23 * * 1-5  /usr/local/bin/python /app/sepa_v2/cli_scan.py
```

v1 cron stays exactly where it is. v2 is purely additive.

---

## 4. UI plan

### `/sepa` (v1, no behavior change)

The current live page. Add a **single discrete chip** at the top right next
to "Fast Scan / Full Scan":

```
[ Reload ] [ Fast Scan ] [ Full Scan ]
                                       ┌──────────┐
                                       │ v1  │ v2 │   ← tab strip
                                       └──────────┘
```

Default tab = v1. The v2 tab is the entry point to the experiment view.

### `/sepa-v2` (new page)

Same layout as `/sepa`. Same filter chips, same setup-category strip, same
heatmap if eventually added. Differences:

- Page header eyebrow: `SEPA v2 — EXPERIMENTAL — NOT FOR LIVE TRADING DECISIONS`
- Banner at top: "These results come from the experimental formula. v1 is at /sepa."
- Each candidate row has an additional "Also in v1?" badge — green ✓ if
  the same symbol is a v1 candidate (high-confidence: both formulas agree),
  yellow ⚠ if v2-only (low-confidence: needs human review before trading).

### `/sepa-compare` (new comparison page)

A small admin page showing the day's v1 vs v2 diff:

```
v1 ∩ v2     (15 names)   ← both lists agree
v1 only     (3 names)    ← v2 missed these — investigate
v2 only     (132 names)  ← v2 surfaced these — review for trade quality
```

This is the **decision feedback loop**. Over weeks the user observes which
"v2-only" names actually turned into successful trades. That dataset drives
the eventual v2 → v1 promotion RFC.

---

## 5. Testing

### Locked v1 contracts — unchanged

`backend/tests/test_sepa_contracts.py` runs unmodified. v2 cannot make it
fail because v2 never touches `backend/sepa/`.

### New v2 contracts

`backend/tests/test_sepa_v2_contracts.py` — same shape as the v1 test, plus
two specific assertions:

```python
def test_v2_vcp_is_relaxed_per_design():
    """v2 monotonic check accepts 1 violation, v1 accepts 0."""
    # synthesize depths = [20, 18, 22, 5]  — 1 mid-base violation (18→22)
    # v1 should reject, v2 should accept.

def test_v2_share_of_universe_in_realistic_range():
    """v2 should surface 5%-15% of analyzed names as candidates.
    < 5% means too strict (defeats purpose), > 15% means too loose."""
```

Wired into `make contracts` once v2 ships, alongside v1 + Kell.

---

## 6. Open questions — need user input before coding

1. **PDF citation for the v2 monotonic rule.**
   - The proposed `≤1 violation` is a guess at "about half the previous,
     ±tolerance." Need confirmation from Minervini's *Trade Like a Stock
     Market Wizard* — what page? what exact wording?
   - If the book is stricter than the proposed v2 rule, we should use the
     book's wording even if v2 surfaces fewer names. The win of v2 isn't
     "more candidates"; it's "candidates that match the book."

2. **Feature gate**: should `/sepa-v2` be owner-only via the same
   `portfolio`-style feature flag, or visible to all signed-in users?
   - Recommendation: owner-only initially. Less risk of someone else
     trading off v2 numbers while it's experimental.

3. **Backfill**: do you want v2 to scan a historical window (e.g. each
   day for the last 30 days) on first deploy so you can immediately see
   "what would v2 have surfaced last week"?
   - Recommendation: skip the backfill on first deploy. Start clean,
     observe live for 2-4 weeks, decide.

4. **v2 chips/tabs in the existing /sepa setup-category strip?**
   - Probably no — v2 is its own page. Mixing v2 chips into the v1 strip
     muddies the contract that v1 ships locked v1 output.

5. **Cron timing**: 23:40 ET (5 min after v1's nightly scan)?

---

## 7. Definition of "v2 is ready for promotion review"

Before any RFC to promote v2 → v1 can be written, the following must hold
for at least **30 consecutive trading days**:

- Daily v1∩v2 overlap > 60% of v1 candidates (v2 doesn't ignore v1 winners)
- Daily v2-only count between 5 and 50 names (not surfacing trash)
- User has manually reviewed at least 10 v2-only names and judged them
  "would-have-traded-this" yes/no, with ≥70% yes rate
- Zero v1 candidates dropped from v2 without a documented reason

The promotion RFC is a separate doc (`docs/SEPA_V2_PROMOTION_RFC.md`),
written by Ajay after the observation period.

---

## 8. Out of scope

- Changing v1 in any way. v1 stays at 1-5 candidates until v2 promotes.
- Adding v2 to existing alerts / breakout banners / push notifications.
  Those all consume v1 only.
- Cross-feeding v2 candidates into the portfolio / position lens. Those
  stay v1-only.
- A "v3" parallel — one experiment at a time.

---

## 9. Build estimate

| Phase                                          | Time   | Output                                      |
|------------------------------------------------|--------|---------------------------------------------|
| `backend/sepa_v2/` scaffold + relaxed vcp.py   | ~30 min| Backend scans + caches v2 results           |
| FastAPI routes for /sepa-v2                    | ~20 min| GET/POST scan + candidate detail            |
| v2 contracts test                              | ~20 min| `test_sepa_v2_contracts.py`                 |
| Frontend `/sepa-v2` page (clone of /sepa)      | ~45 min| New route, tab strip on /sepa               |
| `/sepa-compare` diff endpoint + page           | ~30 min| Three-column compare view                   |
| Cron entry + container restart                 | ~5 min | Nightly v2 scan running                     |
| **Total**                                      | **~2.5 hrs** |                                           |

---

## 10. Sign-off needed

Before any code lands, confirm:

- [ ] Monotonic rule proposed in §2 matches the book (PDF page citation)
- [ ] Feature gate: owner-only? (§6.2)
- [ ] Backfill: skip on first deploy? (§6.3)
- [ ] Promotion criteria in §7 acceptable?
- [ ] Build plan in §9 acceptable?

Once signed, this doc moves from DRAFT to v1.0 with the relevant commit
SHA recorded, and implementation can begin.
