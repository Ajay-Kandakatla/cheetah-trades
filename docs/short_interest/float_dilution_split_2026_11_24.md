# 🩳 % of float — dilution, splits, filings (2026-11-24)

Engine doc for the share-basis check. Spec: `sidilute` rev 2. Branch `feat/si-float-dilution-split-2026-11-24`.
Modules: `backend/short_interest/share_basis.py` (I/O), `backend/short_interest/basis_math.py` (pure verdict + words),
`backend/short_interest/read.py` (`si_block(doc, today, basis=...)`), `backend/short_interest/api.py` (the kick).
Front-end side: `docs/short_interest/float_dilution_split_frontend_2026_11_24.md`. 🩳 High SI side: `docs/gajjala/high_si_sub_2026_11_23.md`.

## The ask, verbatim

Ajay 2026-11-24, in order, after Claude offered: "add a check so that when Yahoo's float is far below the SEC-filed share
count, or older than a split, the 🩳 % stops using it, falls back to % of shares outstanding with that figure's date, and says why."

> "Yeah please"
> "Make sure we are looking for Dilution.."
> "Also split related events and filing so we flag them in the right way"

## The rule in plain words

- The % of float is shown only when the float can be shown as fact. It is **not shown** when:
  - **a split sits between the float and the short-interest count** (the float was first seen on one side of the split, FINRA counted on the other), or either one landed **on the split day** (which side it is on is not known); or
  - **the company issued enough shares since the float was read** — under the built cut, more shares were added than the float held (`FLOAT_STALE_WHEN = "added_exceeds_float"`, HIS CALL #1).
- Then the chip falls back to **% of shares outstanding**, on the newest dated count (an SEC cover-page count, rebased across any split, or Yahoo's current count when it is on the same side of every split), names that count's date and source, and **drops the tier** (no tier on a shares-outstanding read — the house rule). The name leaves 🩳 High SI and is named under it when it was High / EXTREME on the old float.
- No usable dated count on the right side of a split → no % at all; the chip prints the share count.
- A name never asked for by a page is served **byte-identical to before** (no `basis` key).
- A source that fails on a re-check never un-refuses a float: the held answer stands, and the chip says `❔ last check failed`.

The float's side of a split comes from a **track** of the float value (the date the value was first seen, carried across a split when the new value equals the old one split-adjusted within `CARRY_REL_TOL`), never from the day Yahoo was last read — 73 of 100 floats were still the pre-split value after the split (spec §1.8).

## Sources and dates

| Source | What | Date used | Notes |
|---|---|---|---|
| FINRA short interest (via Massive) | the short count, the prior count | the settlement date | Massive serves FINRA's counts as published, not split-adjusted (35 of 43 records across a split) |
| Yahoo `shares_cache` | float + share count | the day the value was first seen (track) / the read day | a Yahoo read date does not say which side of a split a number is on (SMX) |
| SEC `data.sec.gov` companyconcept `dei:EntityCommonStockSharesOutstanding` | cover-page share count | the cover's own `end` date | generic User-Agent, no email; 0.5 s between SEC calls; a 403/429 stops SEC for 15 min |
| SEC `data.sec.gov` submissions `filings.recent` | dilution and charter filings | the filing date | only the kinds of `basis_math.filing_kind` are kept |
| Massive `/v3/reference/splits` | splits, future-dated rows included | execution date | through `drop10_tab.fetch_splits_strict` |
| Massive `/v3/reference/tickers/{sym}` | CIK + security type | — | its share count is undated and is **never** a denominator (HIS CALL #8) |

ADRs (`type` not in `SEC_COVER_SAME_UNIT_TYPES = ("CS", "OS")`): the SEC cover counts ordinary shares, FINRA and Yahoo count ADSs (JZ 517,110,000 vs 2,377,874) — the cover is **not compared** (HIS CALL #19).

## The three modes, 11-24 (74 names: 🩳 tab 11 cards + its lists + 👀 Watch 34)

One constant, `basis_math.FLOAT_STALE_WHEN`. KITT and SMX are split refusals and refuse the same in every mode.

| Mode | Fires when | Names that lose the % of float | Leave the 🩳 list |
|---|---|---|---|
| `any_increase` | any newer dated count is larger than the count paired with the float | **37** (JELD at ×1.0001) | BNAI, CUE, SMTK, ZNB, MEDS |
| `tier_moves` | the ladder word would change on the newer count | **11** (adds MEDS, GPUS, INV, NVTS, SURG, BENF, MGY to the four below) | SMTK, MEDS |
| `added_exceeds_float` ← **built, provisional** | more shares were added than the float held | **4: SMTK, LABT + KITT, SMX** | SMTK |

Shares added ÷ float on file, ranked: LABT 7.76 · SMTK 6.99 · BENF 0.94 · ZNB 0.72 · GPUS 0.67 · STIM 0.55 · MEDS 0.37 … JELD 0.0001.

What moves under the built mode (spec §7 #2):

| Name | Before | After | Why |
|---|---|---|---|
| SMTK | EXTREME 79.0% float | 8.9% shs out (SEC 10-Q cover 11/11, 4,859,369) | 4.7× more shares than the count paired with the float (8.6× SEC cover to cover since Aug) · 1-for-5 reverse split 11/23 · S-4 11/13 |
| LABT | High 18.0% float | 1.7% shs out | 8,950,088 (SEC 11/13) vs 2,369,688 |
| KITT | Low 3.7% float | 7.7% shs out | float read before the 9/25 1-for-6 split, and 2.1× more shares since |
| SMX | Moderate 6.0% float | share count only | float read on the 11/9 1-for-2.8 split day |
| WETO | 22.4% shs out | 1.6% shs out · `⚠️ shares up 14×` | Yahoo 1,077,801 → 14,897,999; both 20-F covers are older than the anchor |
| NXAT | 1.6% float | unchanged · `❔ shares fell 21×` | 68,476,338 → 3,236,567 with no split row |
| CLRO | EXTREME 44.0% float | unchanged · `📄 S-1/A 11/24 +1` | no newer dated count (Massive's undated 3,675,411 is not used) |
| JZ | EXTREME 27.2% float | unchanged · `✂️ split due 12/24` | ADR — cover not compared |

The SMTK chip on the frozen fixture (`backend/tests/fixtures/si_share_basis_2026_11_24.json`):
`🩳 SI 8.9% shs out · 1.0d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13`.

## The flags (appended last to the chip, the 👀 EXTREME note's `short` and the 🩳 card chip; full text in the hover)

| Key | Chip | Means |
|---|---|---|
| `float_stale` | `⚠️ float stale` | more shares than when the float was read (ratio, both counts, sources, dates) |
| `count_stale` | `⚠️ shares up N×` | shares-headed name: a newer count is larger; the % uses it |
| `split` | `✂️ split M/D` (` +N`) / `✂️ split due M/D` | a split after the float or the count; the hover says which side each sits on |
| `filing` | `📄 FORM M/D` (` +N`) | a dilution filing after the float was first seen: S-1 / S-3 / S-4, F-1 / F-3 / F-4 (+ /A, MEF, ASR), 424B*, 8-K Item 3.02 |
| `count_fell` | `❔ shares fell N×` | the share count fell to half or less with no split on file — a missed split is possible; never a refusal |
| `unchecked` | `❔ share count unchecked` / `❔ last check failed` / `❔ dilution unchecked` | a source never answered / the newest re-check failed and the earlier answer is used / a carried float with no SEC count from before it |

Charter 8-Ks (Item 5.03 / 3.03 — where a reverse split is filed, among other charter changes) go to the hover only.

## The change vs the prior settlement across a split

Massive serves FINRA's two counts as published. When a split executed between the two settlements, the % compared two share units
(OMEX served −95.9%). The change is now **rebased** to today's shares: OMEX +2.5% (4,766,804 → 190,672 of today's shares), KNDI +6.5%.
A split ON either settlement day → no % and the words say which side is not known. The rebased change can still be huge (AZTR +2,623%). HIS CALL #16.

## What is NOT covered

- Names no page asked for (the worker runs only when `/short-interest/map` is asked): the ⛔ new-SSR rows off his list (~740 names), 📈 Bonde's DTC leg, the 🔔 cross push for a name whose card was never drawn.
- The card's Float chip and GG's K8 float gate still read Yahoo's float (HIS CALL #11).
- A split the splits read does not list (NXAT) — only `❔ shares fell` catches it, and only past the cut.
- Yahoo applying a split to its share count BEFORE the execution date (SMX) can make the ⚠️ ratio read the split factor; the % it falls back to is right.
- Foreign filers (20-F / 6-K): no quarterly cover, no 8-K items — dilution shows only through Yahoo's own later count.
- Split proxies (PRE 14A / DEF 14A) are not read (the form code does not say what the vote is; the text sits on www.sec.gov, which refuses the generic UA).
- The SEPA realtime chip's "% vs prior settlement" reads the raw record and is untouched.
- Nothing here is a signal; no study is proposed.

## HIS CALL

1. **When dilution refuses the % of float** — `FLOAT_STALE_WHEN`: built `added_exceeds_float` (provisional; the same as a typed ratio of 1.0); alternatives `any_increase`, `tier_moves`, or a ratio he names. Decide before any push.
2. The 11-24 moves above.
3. Tier on the fallback: built none ("not tiered — float stale"); alternative: tier the % of shares.
4. The ⚠️ ratio: built 4.7× vs the count paired with the float; his 8.6× "since Aug" is in the hover.
5. 📄 in the chip (19 of 73 names) or the hover only; the form list (424B3 resale prospectuses, `RW` does not clear, `S-11` and `S-8` not flagged, charter 8-K hover only, proxies not read).
6. A split ON the settlement day or the float's first-seen day: built no % (5 of 8 live records sat post-split, 3 pre); alternative: assume post-split.
7. Yahoo's later count as evidence and as the denominator (WETO): built in; alternative: SEC only.
8. Massive's undated share count is not used (CLRO's 3,675,411 would refuse its 44.0% float).
9. The SEC User-Agent stays generic; a declared contact is his choice.
10. Scope: checked = names a page asks for.
11. The card's Float chip and K8 float gate untouched.
12. EXTREME's "≥ 10% of shares" confirmation still uses the record's paired count on names that are not refused.
13. Loading the 11-24 seed (3,629 names) after deploy — a one-time write.
14. Engineering numbers (Claude's): re-check every 60 min, SEC pace 0.5 s, 15-min SEC stop on 403/429, FE follow-up 20 s doubling to 120 s, at most 6.
15. Still open from before: 11-08 #3 (the label reads the live float) · 11-18 #4 ("float unconfirmed" names).
16. The change across a split: built split-adjusted with the words; alternative: no % across a split.
17. `CARRY_REL_TOL = 1e-4`: the six real matches sit at or under 1.8e-5, the nearest non-match at 3.0e-3.
18. A count that falls with no split: built `❔` at half or less (`SUSPECT_MAX_SHARES_OUT_FRACTION`, by name) — 1 of 239 (NXAT); alternative: also refuse the % of float.
19. ADRs: the SEC cover is never compared; alternative: convert by the ADS ratio (no ratio source on file).
20. `❔ last check failed` on the chip or hover only.

## How to run the probe (read-only)

`backend/scripts/si_share_basis_probe.py` calls `block_writes()` FIRST (every pymongo write becomes a recorded no-op), then for each name builds
the block with `basis=None` (old) and with `share_basis.refresh_symbol(.., store=False)` (new). It prints one line per name
(`SYM | old chip | new chip | refused | flags | sources`), a summary by `FLOAT_STALE_WHEN` mode (all three, same inputs), the names whose tier
changes, the names whose change % was rebased, and writes `si_share_basis_probe.json` + `si_live_blocks.json` (the shared-fixture shape).
It **exits 1** unless SMTK's new block holds the structure: `pct_of_float` None, `tier` None, `basis.float_refused` in (`diluted`, `split`),
flag keys include `float_stale` and `split`, `shares_source` starts `SEC`, `pct_of_shares_out` equals `round(si_shares / shares_outstanding * 100, 2)`,
and — while its settlement is before 2026-11-23 — `shares_outstanding == 4859369`. No chip string and no settlement date is asserted.

Run it only in a throwaway container with the worktree mounted, never in the live api:

```bash
docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 --env-file <600-mode key file> -v /Users/ajay/clinet-test/.wt-sidilute/backend:/app:ro -v <outdir>:/out -w /out cheetah-api:latest python -u /app/scripts/si_share_basis_probe.py --symbols SMTK,LABT,KITT,SMX,WETO,JELD,CLRO,AKAN,NXAT,JZ
```

With no `--symbols` it reads the 🩳 sub's stored names and the 👀 Watch rows from Mongo. Then the real payload through the real component:

```bash
cd frontend && SI_LIVE_PAYLOAD=<outdir>/si_live_blocks.json npx vitest run src/components/ShortInterest.payload.test.tsx
```

## The seed (after his deploy)

The 11-24 float seed (3,629 records with a float, captured before the 11-24 18:40 ET warm) keeps the 11-02 float pairing that tonight's warm erases:

```bash
docker exec -i -w /app cheetah-market-app-cron-1 python -m short_interest.share_basis seed --stdin < /private/tmp/claude-501/-Users-ajay-clinet-test/2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/sidilute/float_seed_2026_11_24.json
```

`seed` writes only `float_track` and only when the live record's float equals the seed's and no earlier `since` is held.

## Tests

- `backend/tests/test_si_share_basis_2026_11_24.py` — the I/O worker.
- `backend/tests/test_si_basis_math_2026_11_24.py`, `backend/tests/test_si_basis_read_2026_11_24.py` — the verdict, the words, the block, the route.
- `backend/tests/test_si_basis_integration_2026_11_24.py` — the real modules over the captured fixture with fake HTTP and an in-memory Mongo: the §7 #2 moves, every SEC call failing on the first pass, a good pass then every call failing, no CIK, an ETF, an ADR, and no host other than `data.sec.gov` / `api.massive.com`.
- `backend/tests/test_gajjala_high_si_basis_2026_11_24.py` — the 🩳 sub.
