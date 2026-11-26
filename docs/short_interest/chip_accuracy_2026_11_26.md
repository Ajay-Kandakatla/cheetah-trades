# 🩳 chip accuracy — 📄 events, S-11, same-day filings, days to cover, the "shares up" baseline (2026-11-26)

Spec: scratchpad `sitrack/spec.md` rev 2, work package `be-si-chip` (A1 A2 A3 A4 A6). A5 (🔒 run start) and A7 (🧨 weak lid) are other packages.
Display only. Nothing here gates, sorts, sizes, pushes or enters a lane. UNMEASURED.

## The ask, verbatim

Ajay 2026-11-26: "can we make sure in the future these # are accurate ?" (the 🩳 / 🔒 / ⚠️ / 📄 / 🧨 chips on Gajjala cards, after WHLR and AKAN showed wrong numbers)

## What changed, in plain words

| # | Before | Now | Where |
|---|---|---|---|
| A1 | 📄 counted every stored row. WHLR files ONE prospectus document under three registration files after each 8-K → `📄 424B3 11/24 +18` | counts filing EVENTS. A 424B document filed under two or more registration files on a day the issuer also filed a report (8-K, 6-K, 10-Q, 10-K, 20-F, 40-F) is that report re-filed: no event, its rows are copies. Any other multi-file document = one event. The text says how many copies were left out | `share_basis.fetch_filings` (row shape), `basis_math.filing_events`, `basis_math.verdict` |
| A2 | S-11 was not read (WHLR's 11/10 S-11 missing) | `S-11`, `S-11/A`, `S-11MEF` are registrations | `basis_math.FILING_REGISTRATION_FORMS` |
| A3 | a filing dated ON the float's date was dropped (`>`) — AKAN's 11/20 F-1/A | counted (`>=`) and labelled "same day — which came first is not known" | `basis_math.filing_events` |
| A4 | the chip printed the provider's `1.0d` — FINRA's floor, not a measurement | shares short ÷ average daily volume (both on the record); FINRA's floor said in words | `read.dtc_computed`, `chip_text`, `title_text`, `rows_for`, `rules_section` |
| A6 | no usable float: "shares up" read from the record's own count (WHLR 978,675, older than the SEC 10-Q cover 1,788,532 already dated) → `⚠️ shares up 2.3×` | the baseline is the LARGER of the record's count and the newest same-unit SEC cover dated on or before it (rebased to its split side). WHLR → 1.2×, under `FLOAT_STALE_WHEN` → no ⚠️; the three counts move to the hover | `basis_math.verdict`, no-usable-float branch only |

## A1 — the row shape and the event rules

`fetch_filings` rows: `{"form", "filed", "items", "doc", "file", "accn", "with"}` — `doc` = `primaryDocument`, `file` = `fileNumber`, `accn` = `accessionNumber`, `with` = the form of the first report (listing order) the issuer filed the SAME day, read over the whole `recent` listing before the kind filter (an 8-K Item 8.01 that is not kept still marks its day). A missing or ragged array leaves the three fields None and the row counts as before. `SB_REPORT_FORMS = ("8-K", "6-K")` (MINE; a test pins `SB_REPORT_FORMS[0] == BM.FILING_8K_FORM`); the periodic reports come from `SEC_PERIODIC_PREFIXES`. When the kind-filtered list is longer than `SB_FILINGS_KEPT` (40), `fetch_filings` returns `cap`, `_sec_step` stores `sec.filings_cap`, and the text says "only the newest 40 filings are read". `SB_VERSION` unchanged.

`filing_events(filings, anchor, cap=None)` (PURE, never raises), over rows filed ON or after the anchor:
1. E1 — the 424B rows of one day with the same non-empty `doc` are one document; its files = the distinct `file`s.
2. E2 — a document with two or more files AND a same-day report adds no event; all its rows are copies.
3. Any other document = one event (`copies` = rows − 1).
4. A 424B row with no `doc` (stored before today) = one event, counted in `unchecked` → "N prospectus filings not yet checked for copies".
5. Every other row (registration, 8-K) = one event; an 8-K 5.03 / 3.03 is a charter event (the title line).
6. `same_day` = filed on the anchor. Order: filed newest first, then the stored order.

Expected on the real SEC payloads (`backend/tests/fixtures/sec_submissions_{whlr,akan}_2026_11_26.json`, the `filings.recent` arrays only):

| Name | Anchor | Events | Chip | Counts |
|---|---|---|---|---|
| WHLR | 2026-11-07 (record share count; the record float is suspect) | 8-K 3.02 11/20 · 424B3 11/18 (the real prospectus, one file) · 8-K 3.02 11/18 · S-11 11/10 · 8-K 3.02 11/9 | `📄 8-K 3.02 11/20 +4` (was `📄 424B3 11/24 +18`) | 20 dilution-kind rows, 15 copies; charter 8-K Item 3.03/5.03 11/24; the 11/24 reverse-split document is never an event |
| AKAN | 2026-11-20 (float date) | F-1/A 11/20 | `📄 F-1/A 11/20 · same day` | text: "F-1/A 11/20 filed the same day the float was read; which came first is not known" |

The stored `si_share_basis` rows have no `doc` yet: until a name's basis doc refreshes (`SB_REFRESH_MIN` after its next read), its chip counts as before and its text says "not yet checked" (WHLR today: `📄 424B3 11/24 +18 … 16 prospectus filings not yet checked for copies`).

## A2 — forms

EDGAR's form-type list (`sec.gov/info/edgar/forms/edgform.pdf`, read 2026-11-26) lists `S-11`, `S-11/A` and `S-11MEF`. There is no F-11 form, so nothing is added for it. Exact families stay ([C13]): `S-1` never catches `S-11` by prefix; `S-111`, `F-11`, `S-8` → no kind. Reg A (1-A, 253G2) and F-10 are still not read (HIS CALL §7 #16).

## A4 — days to cover

FINRA's equity short interest glossary (re-read 2026-11-26): days to cover = short interest ÷ average daily share volume, rounded to hundredths; "1.00 will be displayed for any values equal or less than 1".

- `read.DTC_FINRA_FLOOR = 1.0`; `DTC_FLOOR_NOTE` (" FINRA's file shows 1.00 for any value at or under 1.") is built from it; `DTC_CHIP_FLOOR` = `≤1d`.
- `read.dtc_computed(b)` = `si_shares ÷ avg_daily_volume` when both are positive finite numbers, else None. PURE, FROZEN (WP5's `si_track` imports it by name).
- Chip: the computed figure (`<0.1d` under 0.05); else the provider's figure — `≤1d` when it equals the floor; 0 / None → no segment.
- Title and the "Days to cover" row: "0.05 days to cover — 439,892 shares short ÷ 8,981,291 average daily volume (the provider's window)." + the floor sentence when the provider's figure IS the floor and nothing computed sits above it, + `DTC_SPLIT_NOTE` when `basis.change` is a dict (a split executed between the two settlements). `b["days_to_cover"]` keeps the provider's value; no block key added.
- The 🩳 rules pick "Days to cover = …" gains one sentence built from the constants.
- 2026-11-26 refix: `extreme_title` (the EXTREME hover on the same card) printed the provider's "1.0 days to cover" beside a `<0.1d` chip (the WHLR defect). It now reads `read._dtc_sentence(b, dtc_computed(b))` — the one sentence the card title uses, with `_dtc_notes` — and keeps its own rule that no ADV and a provider 0 / None / NaN prints no segment. Pin moved: `test_si_extreme_note_2026_11_18.py` (CLRO `1.0 days to cover` → `2.02 days to cover — 391,224 shares short ÷ 193,414 …`); the shared fixture's three EXTREME titles (`eose_v2_float`, `dtc_missing`, `clro_shape_extreme`) regenerated from `si_block`, nothing else in it moved.

Read-only probe of `short_interest_latest`, 2026-11-26 (settlement 2026-11-13):

| Name | shares short | ADV | provider | computed | chip |
|---|---|---|---|---|---|
| WHLR | 439,892 | 8,981,291 | 1.0 | 0.049 | `<0.1d` |
| AKAN | 160,256 | 8,959,848 | 1.0 | 0.018 | `<0.1d` |
| NCPL | 464,533 | 2,884,336 | 1.0 | 0.161 | `0.2d` |

## A6 — the "shares up" baseline (no usable float only)

In the branch where the float cannot head the chip, after `base = (record count, its date)`: the newest same-unit SEC cover dated on or before the anchor is rebased to the record's split side (`_rb`); when that is LARGER than the record's count it becomes the baseline (`source "sec"`), and the record's own count is kept as `growth.record_under`. `paired`, `growth`, `count_flag` and `fell` then run unchanged; the count the % of shares outstanding uses (step 3) is not touched. A split ON either date, a cover dated after the anchor, an ADR / other-unit cover (`sec_units`) → baseline unchanged. The float branch is NOT changed (HIS CALL §7 #4) — pinned byte-identical to `cc63e6ff` on the SMTK, MEDS, JELD and SMX fixtures.

WHLR: baseline 1,788,532 (SEC 10-Q cover 11/3) → 2,220,906 (Yahoo 11/25) = 1.2× → under `FLOAT_STALE_WHEN` → no `⚠️ shares up`. Hover: "Share counts: the record carried 978,675 (11/7), under the SEC 10-Q cover count 1,788,532 (11/3) already dated — growth is read from the SEC count: 2,220,906 (Yahoo, 11/25) = 1.2×."

[C8] `fell` reads the same baseline and is NOT suppressed: a newer count at or under the SEC cover × `SR.SUSPECT_MAX_SHARES_OUT_FRACTION` fires `❔ shares fell`, with the SEC count and its date as the "from" side. WHLR: no `fell` (2,220,906 is over half of 1,788,532). The probe of every stored basis doc for names whose `fell` appears or disappears is the main session's (§5.4); a name that GAINS a flag goes to him before deploy.

## Mutation list (each run on a scratch copy; the new test file goes red on every one)

| Mutation | Red tests |
|---|---|
| `>=` back to `>` (filed vs anchor) | 5 |
| drop E2 (report re-filed) | 4 |
| drop the `files >= 2` test in E2 | 3 |
| baseline `max` → the record's count | 5 |
| drop the raised baseline from `fell` [C8] | 1 |
| drop S-11 / S-11MEF from the form tuple | 7 |
| chip prints the provider's figure | 3 |
| drop the FINRA floor sentence | 2 |
| EXTREME hover back to the provider's figure (refix) | 16 (with the two moved pin files) |
| `with` never set (no same-day report) | 5 |

## Tests

- NEW `backend/tests/test_si_chip_accuracy_2026_11_26.py` (92, 13 of them the 2026-11-26 EXTREME-hover refix): row shape, cap, the WHLR / AKAN chips, every ✗ of spec WP1, the float-branch golden hashes, [C8] both ways.
- Pins moved, each with a dated note: `test_si_basis_math_2026_11_24.py` (S-11 out of the "no kind" list; event counts in the 📄 text; XLAB same-day), `test_si_share_basis_2026_11_24.py` (row shape), `test_si_basis_read_2026_11_24.py` / `test_si_basis_integration_2026_11_24.py` / `test_si_float_newer*_2026_11_24.py` / `test_si_tier_2026_11_18.py` / `test_si_extreme_note_2026_11_18.py` / `test_short_interest_read_2026_10_03.py` (`1.0d` → `≤1d` or the computed figure; SRTM's same-day 8-K).
- The shared fixture `backend/tests/fixtures/short_interest_blocks_2026_10_03.json` (also read by `frontend/src/components/ShortInterest.payload.test.tsx`) must be regenerated from `si_block` — only its days-to-cover strings move (22 lines). Not in this package's files.

## HIS CALL (none decided here)

- §7 #1 what counts as one filing (E2 is structural: a real supplement filed under two or more registrations on a report day would be left out; none seen in the two payloads).
- §7 #4 the same baseline rule where a float IS on file.
- §7 #16 Reg A / F-10 forms.
