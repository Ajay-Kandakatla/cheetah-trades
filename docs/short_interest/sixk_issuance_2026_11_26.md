# 🩳 6-K issuance check — SEC full-text search (2026-11-26)

Ajay 2026-11-26 ~21:10 ET, verbatim: "Fix the POM chip and the 6-K dilution check. Also find alternative srouces for
this share count, I think the short interest theory is actually working may be its a bias for me on the ones its
working out but lets track them in our list of SI. and maintain a track record of our stocks"

Spec `sishares` rev 2, §3.1 + §3.3, work package be-io. Code: `backend/short_interest/sec_fts.py` (NEW),
`backend/short_interest/share_basis.py`. Tests: `backend/tests/test_si_sec_fts_2026_11_26.py`. Display + tracking
only; no gate, sort, size or push changes. UNMEASURED.

## Why a full-text search

- A foreign issuer reports a share issuance in a **6-K**. A 6-K carries no item numbers, so the filing listing alone
  cannot tell an issuance 6-K from a press release or a Nasdaq letter. Before this change `fetch_filings` dropped
  every 6-K, so POM's 6-K of 11-04 (33,185,841 shares issued) never reached the check.
- **The SEC document host refuses the house User-Agent.** One GET on 2026-11-26 to the EDGAR Archives with
  `SB_HTTP_HEADERS` (`Mozilla/5.0 (compatible; share-count-reader)`, no contact) → HTTP 403 "Your Request Originates
  from an Undeclared Automated Tool" (saved in the session scratchpad as `probe_archives_generic.htm`). So the 6-K
  TEXT is never read. Reading it needs a declared User-Agent with a contact — HIS CALL #3, not built.
- **The SEC full-text search (efts.sec.gov) answers the same User-Agent** (three GETs 2026-11-26, all 200). It is under
  the SAME SEC fair-access policy that the 403 enforces; today it does not enforce it. It is an undocumented
  endpoint: its shape or access can change. It returns which DOCUMENTS of a filer match a query, never their text.

## Request / answer

`GET https://efts.sec.gov/LATEST/search-index?q=…&forms=6-K&ciks=<cik10>&dateRange=custom&startdt=<since>&enddt=<today ET>`

Every GET goes through `share_basis._sec_get` — the one pacer `_sec_wait` (SB_SEC_MIN_INTERVAL_SEC apart, shared with
data.sec.gov), `SB_HTTP_HEADERS`, and the `_http` seam the test session refuses. `sec_fts.py` holds no http client and
names one host.

Answer fields read: `hits.total.value`, `hits.hits[]._id` = `<accession>:<file>`, `_source.{adsh, file_date, form,
file_type, file_description}`. A junk hit is dropped; an answer without `hits.total` / `hits.hits` is `failed`.
A hit counts only when its accession is a 6-K / 6-K/A of the filer's own listing in the window (`reports` from the
same submissions GET); one row per accession, filed newest first; the other documents hit are kept as
`ex: [{type, desc}]` (description cut to `FTS_DESC_MAX` = 120 chars, display only — MINE).

Stored under `sec.fts` (shape FROZEN in spec §3.1): `status` ok / none_6k / failed / blocked / off, `since`, `top_6k`,
`top_6k_filed`, `read_at`, `error`, `error_at`, `strikes`, `cap` (rows returned, only when the total is larger),
`issuance`, `number`. Each issuance 6-K is also appended to `sec.filings` with `"fts": "issuance"` (filed DESC, inside
`SB_FILINGS_KEPT`; `filings_cap` set when the list is cut).

## The two queries

1. **Issuance phrases** (`FTS_ISSUANCE_PHRASES`, OR — MINE, HIS CALL #4): "agreed to issue", "issued an aggregate",
   "private placement", "registered direct", "securities purchase agreement", "debt conversion", "at-the-market",
   "exercise of warrants", "subscription agreement". Asked only when a 6-K was filed in the window.
2. **The exact share count added** — `format(n, ",")`, `n = to_shares − from_shares` of the verdict's share-count
   growth (`sec_fts.default_growth_fn`, a lazy `basis_math.verdict` read; `share_basis.py` keeps exactly its two
   basis_math import lines). Asked only when the phrase answer is ok this pass, a 6-K is in the window and `n > 0`.
   Stored as `number: {n, from, to, read_at, hits: [{accn, filed, form, doc}]}`; `hits: []` = asked, nothing prints it.

### How the phrase list was checked

| Saved answer (2026-11-26, POM CIK 0001877971) | Window | Hits |
|---|---|---|
| the 9 phrases, forms 6-K | 09-01 → 11-26 | 2 documents = the 11-04 6-K (primary + EX-10.1 "DEBT CONVERSION AGREEMENT…") |
| `"33,185,841"` | 10-30 → 11-26 | the same 2 documents |
| `"ordinary shares"` (a broad control) | 10-01 → 11-26 | 6 documents in 5 accessions |

Local re-check of the 9 phrases on the 14 saved filing texts (case-insensitive, whitespace collapsed, word edges —
`sec_fts.text_matches`, test-only): of the nine POM 6-Ks ONLY 11-04 matches ("agreed to issue", "debt conversion");
of the five NCPL 8-Ks ONLY 10-20 (the Item 3.02 note, already a 📄 by its item). Near misses that do NOT match:
10-19 "Share Consolidation" / ADS exchange · 10-09 "issued the delisting determination", "1-for-18 reverse stock split"
· 11-02 Nasdaq letter · 11-06 "issued a press release" · 10-02 "were issued and outstanding" · 09-24 / 09-29 / 09-30.
The 09-29 interim report is stored cut to its first 6,000 chars after the phrases were checked on its full text.
A split-mention query was rejected: it would hit 10-02, 10-19 and the 10-09 Nasdaq letter.

**Recall is 1 of 1 issuer.** The ship gate below measures it on every stored foreign issuer with an offering on file.

## Caching and the no-hit rule [C8]

The phrase answer is asked again when ANY of: the newest 6-K of the window moved · the window `since` moved · the held
status is failed / blocked / off · the held answer has an `error` (the last try failed) · `holds()` is false.
The number is asked again when (n, from, to, since, newest 6-K) moved or `holds()` is false.

`holds(top_filed, read_at, hit)`: a held answer that HIT the newest 6-K stands from the first read; a no-hit answer
stands only when it was read (Eastern date) AFTER `basis_math.day_after(top_filed)`. A no-hit read made on the filing
day or the day after is asked again on the next pass. Junk dates → never held. The index lag is unknown: a lag longer
than that is a miss until the window moves or a newer 6-K lands.

## The stop and the switch

- A 403 / 429 from efts stops ONLY the full-text reads for `SB_SEC_BLOCK_MIN` (15 min), never data.sec.gov. The stop is
  persisted as `{"_id": "state|fts", "blocked_until", "reason"}` in `si_share_basis` (the `state|sec` shape) so a
  second process honours it; `refresh_symbol(store=False)` writes no stop; `_clean` keeps the id out of symbol lists.
- Status rule as on every share-basis sub-doc: a failed try over a held good read keeps the data, `read_at` and status
  and sets `error` / `error_at` / `strikes`; nothing good held → `failed`; the stop on with nothing held → `blocked`.
- 2026-11-26 refix [C1]: under the stop a held good answer is returned as it is ONLY while it still covers the window.
  A held `none_6k` with 6-Ks now listed, a held `top_6k` that is no longer the newest 6-K, or a moved `since` comes
  back with `error "blocked"` + `error_at` (strikes unchanged), so `filings_known` is false and the next pass after
  the stop asks again.
- 2026-11-26 (refix, retry clock): `is_due` reads `ref` / `sec` / `splits` only, NOT `sec.fts`. A failed / blocked /
  errored full-text read is therefore re-asked on the name's next pass at `SB_REFRESH_MIN` (60 min) or on a `seen`
  change, not at `SB_ERROR_RETRY_MIN` (5 min). That is deliberate: while the efts stop holds, a 5-minute clock would
  re-run the data.sec.gov submissions read of every blocked name for nothing. Pinned by
  `test_NEGATIVE_a_failed_or_blocked_fts_alone_does_not_make_the_name_due` and
  `test_a_failed_fts_is_due_again_at_the_refresh_clock`.
- `sec_fts.FTS_WHEN = "on"` (HIS CALL #3). `"off"` — or any value but the exact word "on" — makes NO efts call and
  stores `status "off"`; POM then stays "float stale".

## What it cannot do

- No 6-K text: it proves a number or a phrase is PRINTED in a filing of that issuer, not what it means. A filing that
  only agrees to issue (closing later) matches.
- No number without a share-count growth on file; the number query runs only for 6-K filers (HIS CALL #16).
- Index lag unknown; 100 rows a page (a larger total sets `cap`).

## Massive share counts (WP-3, the I/O half)

`fetch_ref` already GETs the Massive ticker reference; it now also keeps `results.share_class_shares_outstanding` →
`ref.share_class_shares` and `results.weighted_shares_outstanding` → `ref.weighted_shares` (a finite number > 0; bool,
NaN, ≤ 0, strings → None). Zero new requests per read. The provider gives NO as-of date for either: they are dated by
the read only. A held ref WITHOUT both keys is not fresh [C16], so every name re-reads its ref once after deploy (one
Massive call per name, spread by the due rule and `SB_QUEUE_MAX`). Provider field wording, as the ticker-overview
reference describes them (quoted from the provider's reference as known, not re-fetched on 11-26): share class — "the
recorded number of outstanding shares for this particular share class"; weighted — "the shares outstanding calculated
assuming all shares of other share classes are converted to this share class". POM 11-26: share class null, weighted
35,966,137 = 35,761,933 Class A + 204,204 Class B.

## Ship gate — the recall probe [C7]

Read-only (no Mongo write, no file). For each stored basis doc whose `sec.filings` holds an F- registration or a 424B
row: ONE submissions GET + ONE phrase query over the doc's own window, both through `_sec_get`. A name with no 6-K in
its window is listed and not asked; a 403 / 429 stops the probe. `--max N` is required (a probe size, never a rule).

```bash
docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/.wt-sishares/backend:/app:ro -w /app cheetah-api:latest python -u /app/scripts/si_fts_recall_probe.py --max 40
```

Output, per name then the summary (no pass mark is set; the table goes to him):

```
POM    | offerings 424B4 2026-11-01 | 6-Ks since 2026-10-30: 2026-11-06, 2026-11-04, 2026-11-02 | phrases hit: 6-K 2026-11-04
ZED    | offerings F-1/A 2026-11-03 | 6-Ks since 2026-10-30: none — not asked
asked 1 / with a hit 1 / with none 0 · no 6-K in window 1 · failed 0
names with none: —
```

(The lines above are the test fixture's, not live data. The live table is filled by the §5.2b run before deploy.)

After deploy, one worker pass for POM: `python -m short_interest.share_basis refresh --symbols POM` (one Massive ref
GET, two efts GETs); its summary line ends `| fts ok, 1 issuance 6-K, number 1 hit`.
