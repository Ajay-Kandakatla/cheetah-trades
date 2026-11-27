# 🩳 POM chip, the 6-K dilution check, share-count sources — the verdict side (2026-11-26)

Spec `sishares` rev 2, §3.2 / §3.4 / §4.1 (package `be-verdict`). Display only — no gate, sort, size or lane entry
changes. UNMEASURED.

## The ask, verbatim

Ajay 2026-11-26 ~21:10 ET:
"Fix the POM chip and the 6-K dilution check. Also find alternative srouces for this share count, I think the short
interest theory is actually working may be its a bias for me on the ones its working out but lets track them in our
list of SI. and maintain a track record of our stocks"

This doc covers the first two sentences on the read side (`backend/short_interest/basis_math.py`,
`backend/short_interest/read.py`) and the share-count sources. The full-text reader is `docs/short_interest/sixk_issuance_2026_11_26.md`;
the follow-up / track record is `docs/gajjala/si_follow_2026_11_26.md`.

## What was wrong with POM

The record's float (1,119,065) and the count stored beside it (2,576,092) were both read 11-09. Yahoo's current row
(11-25) holds float 1,545,214 and 35,761,933 shares. The 11-24 rule saw 13.9× more shares "since the float was read"
and refused the newer float as stale: chip `🩳 SI 0.2% shs out · 0.2d · 11/13 · ⚠️ float updated · ⚠️ float stale`.

That was false for POM. The 33,185,841 new shares were issued 11-04 (6-K filed 11-04, a debt conversion), BEFORE the
11-09 float read. 2,576,092 + 33,185,841 = 35,761,933 exactly. The count stored with the float was out of date, not the
float.

Now: `🩳 SI Moderate 5.0% float · 0.2d · 11/13 · ⚠️ float updated · ⚠️ shares up 14×` (77,883 / 1,545,214 = 5.04%;
0.22% of 35,761,933 shares outstanding). No 📄 — the 11-04 6-K is before the 11-09 anchor; it is listed as a
"Share issuance" row with its SEC link.

## The same shape elsewhere (spec §1.2)

| Name (fixture) | newer float co-dated with the larger count | 📄 dilution event since the older float | a filing dated BEFORE the older float prints the exact added count | % on the newer float | Built default |
|---|---|---|---|---|---|
| POM (live docs) | yes (same Yahoo row 11-25) | none | YES (6-K 11-04, 33,185,841) | 5.04 Moderate | **freed** |
| LABT | yes (SEC cover 11-13, Yahoo 11-18) | none | no (domestic, no 6-K) | 4.78 Low | refused (unchanged) |
| SRTM | yes | 424B3, S-1/A, S-1, 8-K 3.02 | no | 7.25 Moderate | refused (unchanged) |
| KITT | yes once rebased across the 9/25 1-for-6 | S-1 11/12 | no | 12.64 High | refused (unchanged) |
| GMEX | no growth | none | — | 3.52 Low | unchanged by any mode |

## The modes — `basis_math.FLOAT_FRESH_WHEN` (HIS CALL #1)

Built default: `issuance_before_float`. An unknown value behaves as `off`.

Every mode first needs: the larger count dated ON or BEFORE the newer float, on the same side of every split (none
ON either date), and the newer float's own Yahoo row carrying at least that count (rebased to the float track's
date). Then:

| Mode | Freed when | Can prove | Cannot prove |
|---|---|---|---|
| `off` | never | — | — (the 11-24 rule) |
| `issuance_before_float` | an SEC 6-K the full-text search found prints the EXACT shares added (count now − count then, to the share), filed STRICTLY before the older float's date, same split side | the shares were already out when the older float was read; the newer float was read with the grown count | that Yahoo's float figure took the new shares in; a filing that only AGREES to issue (closing later) passes the date test |
| `co_dated_no_filing` (built, NOT default) | no 📄 dilution event since the older float AND every filing read answered (`filings_known`) | nothing positive — it rests on an absence | it frees LABT-class names (HIS CALL #2, the 11-24 question); only as good as the phrase list (recall 1 of 1 issuer) |

Rejected, not built: co-dating alone (frees FFAI at EXTREME 39.2%, JDZG, SRTM, KITT — true by construction when the
evidence is the Yahoo row itself), a size cut on how far the float moved (a new threshold), judging by
"Regulation S / insider" words (needs the 6-K text, which www.sec.gov refuses to the house UA).

A float refused for a split is never "fresh" (no "the % of float uses the newer float" wording on a split refusal).

## Fail closed — state → result (default mode)

Every state below serves EXACTLY what `off` serves (today's refusal); one test per state in
`backend/tests/test_si_share_count_verdict_2026_11_26.py::test_C1_NEGATIVE_POM_fails_closed`.

| State | Result |
|---|---|
| `sec.fts` absent (every doc until its first pass after deploy) | refused, float stale |
| fts status failed / blocked / off / none_6k | refused |
| sec status failed / blocked / no_cik, or no `sec` | refused (failed / blocked also show ❔) |
| `number` None, or `number.hits` [] | refused |
| `n` off by one; `from` / `to` not this growth's; `n` a float or a bool | refused |
| the hit filed ON the anchor, or after it | refused |
| a split between the hit and the float track's date | refused |
| the hit's form not 6-K / 6-K/A | refused |
| mode `off` or unknown | refused |
| fts status ok with `error` set (a held answer; a filed document does not change) | **freed** |

Second mode, each stays refused: an FFAI-shaped doc (4 events) with sec failed / blocked / missing · `filings_cap`
set · `sec.error` set · fts absent / failed / blocked / off / `error` / `cap` · SRTM · KITT · a 6-K issuance event on
or after the anchor.

## The 6-K as a 📄 event

- `_filings` re-emits `fts: "issuance"` only on a 6-K / 6-K/A (dropped on any other form); such a row is kind
  `foreign_issuance`, now in `DILUTION_KINDS`. `filing_kind` is unchanged: a bare 6-K names no kind.
  `_filings(_filings(raw)) == _filings(raw)`.
- `filing_events`: the marked 6-K is one event under the same anchor rule as every filing — EXCEPT on a day that
  yields a counted event of another dilution kind (424B5 + its pricing 6-K = ONE event, the 424B5; the text adds
  " — 1 same-day 6-K not counted (the report of an offering already counted that day)"; new key `n_reports`). On an E2
  day (the 424B rows are the report re-filed) the 6-K IS the event. A charter 8-K the same day does not swallow it.
- The 6-K is NOT counted in the 🏁 pattern `dilution_before` (si_track, another package).
- The check sentence gains a 4th clause ONLY when `sec.fts` is a dict: "6-K issuance search (SEC full-text): read
  M/D HH:MM ET" · "no 6-K filed in the window" · "not read — last try failed …" · "not read — paused" · "switched off".
  A doc without `fts` keeps a byte-identical sentence.
- **2026-11-26 refix (verifier miss 1):** a held `none_6k` answer that a later pass could not re-ask (6-Ks now listed,
  the SEC stop on → `error` "blocked"; or the try failed → `error` set) no longer says "no 6-K filed in the window": it
  reads "not read — paused" (`error` "blocked") or "not read — last try failed M/D HH:MM ET" (any other `error`). Pinned
  in `backend/tests/test_si_shares_refix_2026_11_26.py`.

## Share counts — `basis_math.share_counts` (spec §3.4)

Served as `basis.share_counts` (always a list for a checked name) and ONE "Share counts" row (not in the hover
title). Rows in this order, only those with a value: record · Yahoo current row · newest same-unit SEC cover · Massive
this class · Massive all classes · the number a 6-K states for THIS growth. No comparison, no "disagree" word, no cut,
no flag; the tier keeps the one chosen float. An ADR cover keeps "not compared — an ADR's SEC cover counts ordinary
shares".

POM row: `short-interest record 2,576,092 (read 11/9) · Yahoo 35,761,933 (read 11/25) · Massive, all classes
35,966,137 (read 11/25 — the provider gives no as-of) · 6-K 11/4 states +33,185,841 · SEC cover: none on file.`
(Judgement call: the text follows the §3.4 row order, so the record comes before Yahoo — the spec's example line
listed Yahoo first.)

Massive's two fields (quoted from the provider's ticker-overview field descriptions as known to the build; not
re-fetched 11-26):
- `share_class_shares_outstanding` — "The recorded number of outstanding shares for this particular share class."
  → "Massive ticker details, this share class".
- `weighted_shares_outstanding` — "The shares outstanding calculated assuming all shares of other share classes are
  converted to this share class." → "Massive ticker details, all classes converted". POM: 35,761,933 Class A +
  204,204 Class B = 35,966,137.

### Sources — each fetched ONCE 11-26 (generic UA; Massive through the house key, read-only container probe)

| Source | POM | NCPL | AKAN | SMTK | CLRO | Date it carries | Verdict |
|---|---|---|---|---|---|---|---|
| SI record pairing (Yahoo at `float_asof`) | 2,576,092 (11-09) | 8,018,428 (11-18) | 2,388,212 (11-20) | 4,859,369 (11-18) | 2,675,412 (11-17) | read date | have |
| Yahoo live row (`shares_cache`) | 35,761,933 / float 1,545,214 (11-25) | 8,018,428 / 4,387,760 (11-25) | 2,388,212 / 709,911 (11-20) | 4,859,369 / 546,875 (11-18) | no basis doc yet | read date | have |
| SEC cover, dei (`fetch_covers`) | NoSuchKey (dual class) | 7,847,899 (10-Q 2026-03-19) | 1,983,546 (20-F 2025-12-31) | 4,859,369 (10-Q 11-11) | not read | as-of on the cover | have |
| SEC companyfacts, other tags | us-gaap only, no common count | — | — | — | — | — | REJECT |
| Massive `share_class_shares_outstanding` | null | 7,847,899 | 2,388,212 | null | 2,675,412 | NONE | list, "read date" only |
| Massive `weighted_shares_outstanding` | 35,966,137 | 8,018,428 | 2,639,467 | 971,873 | 3,675,411 | NONE | list, "read date" only |
| Filing-stated number via SEC full-text search | 6-K 11-04 states 33,185,841 | — | — | — | — | filing date | ADD |
| Nasdaq api `/quote/SYM/summary`, `/info` | no shares field | — | — | — | — | — | REJECT (no count; not independent) |
| StockAnalysis statistics | 2.32M / 1.55M | 7.85M / 4.39M | — | — | — | none; 3 significant digits | REJECT |
| Finviz | 6.34M / "-" | 6.85M / 2.09M | — | — | — | none; 3 significant digits | REJECT |
| OTC Markets / transfer agent | all five Nasdaq-listed | | | | | — | not applicable |

No free, dated SECOND FLOAT source was found (NCPL 4.39M Yahoo vs 2.09M Finviz stays open, HIS CALL #8).

## Served shape

- Verdict keys added: `issuances` (list), `share_counts` (list), `float_fresh` (None | `{mode, accn, filed}`).
- `read.BASIS_KEYS` += `share_counts`, `issuances` (always lists). `_BLOCK_KEYS` untouched; a name with no basis doc
  is byte-identical (`tests/fixtures/short_interest_blocks_2026_10_03.json` unchanged).
- Title: one sentence per issuance ("Issuance on file: 6-K 11/4, 33,185,841 shares."). The archive URL
  (`basis_math.SEC_ARCHIVE_URL`, www.sec.gov) is a LINK for the browser — never fetched; `filing_url` returns None
  unless the CIK is digits, the accession NNNNNNNNNN-NN-NNNNNN and the document a plain file name.
- Rules sentence: one clause from `FLOAT_FRESH_MODE_WORDS[FLOAT_FRESH_WHEN]`, one for the 6-K.

## HIS CALL

1. Which newer floats are trusted — `FLOAT_FRESH_WHEN` (`off` / `issuance_before_float` built default /
   `co_dated_no_filing`).
2. LABT-class — stays refused under the default; freed under `co_dated_no_filing`.
5. A 6-K issuance is a 📄 on the chip, never a second event on an offering day; not in the 🏁 pattern.
6. Massive's two counts carry no as-of — shown, marked "read date", never compared. Or hide them.
7. Which source wins when they differ — unchanged; no tolerance, no "disagree" flag (the queued second run).
8. A second float source — none free and dated was found.
16. The exact-number check runs only for 6-K filers.
20. `⚠️ shares up N×` stays on a float judged fresh (POM). Drop the word = his call.

## Re-run — the mode table (ship gate §5.2a)

In a throwaway container with the worktree's backend mounted read-only, outside 09:30–16:00 ET, one container:

```bash
docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 --env-file <600-mode key file> -v /Users/ajay/clinet-test/.wt-sishares/backend:/app:ro -v <outdir>:/out -w /out cheetah-api:latest python -u /app/scripts/si_share_basis_probe.py --modes --with-fts
```

`--modes` reads every stored basis doc (no outside call) under each mode and prints per name that differs from
`off`: refusal, % of float, tier, 🩳 High SI list membership (`high_si.classify` on the session's stored read), flags
gained / lost; writes `si_share_basis_modes.json`. `--with-fts` first re-reads (`share_basis.refresh_symbol(...,
store=False)`, writes nothing) only the names `off` refuses as diluted under a newer float. Expected under the
default: POM only. A name that enters or leaves the 🩳 list goes to him first.

**2026-11-26 refix (verifier miss 4):** "enters / leaves the 🩳 list" counts only a real membership flip (listed True ↔
False, `_list_flip`); a name off the list both ways whose reason word changed (POM) is still printed as a mover but is
not an enter / leave. The last line prints the attempted-write count WITH the method names (`attempted writes: N
{"method": n}`), as the per-name path does.

Tests: `backend/tests/test_si_share_count_verdict_2026_11_26.py` (155 cases incl. the probe table on a fake db); 25
mutations of the new conditions each turn a test red (scratch copy).
