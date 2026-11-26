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

What moves under the built mode (spec §7 #2) — **results before the newer-float rule** (the "2026-11-24 later" section; the current results on the same fixture are in the second table):

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

**Current results, with the newer-float rule** (same frozen fixture, `added_exceeds_float`, run 2026-11-24 on this branch):

| Name | Chip now | Refused | What changed vs the table above |
|---|---|---|---|
| SMTK | `8.9% shs out · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13` | diluted | nothing (no newer Yahoo float) |
| LABT | `1.7% shs out · ⚠️ float updated · ⚠️ float stale` | diluted | gains `⚠️ float updated` (3,201,536 Yahoo 11/18 replaced 847,661 11/9); still refused from the replaced float's date |
| KITT | `7.7% shs out · ⚠️ float updated · ⚠️ float stale · ✂️ split 9/25 · 📄 S-1 11/12` | diluted only | the newer float (11/23) is on the count's side of the 9/25 split, so the split refusal goes; the dilution since 9/3 still refuses it |
| SMX | `47.7K sh · ⚠️ float updated · ✂️ split 11/9 · 📄 424B3 11/23 +2` | split | the newer float (11/24) is after the 11/9 split, short interest before it; no count on the settlement's side, so no % at all |
| WETO | `Low 1.6% float · ⚠️ float updated · ⚠️ shares up 14×` | — | Yahoo's newer float (14,735,015 on 14,897,999) heads; HIS CALL 2 below |
| NXAT | `Low 1.6% float · ❔ shares fell 21×` | — | unchanged |
| CLRO | `EXTREME 44.0% float · 📄 S-1/A 11/24 +1` | — | unchanged |
| JZ | `EXTREME 27.2% float · ✂️ split due 12/24` | — | unchanged |

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

## 2026-11-24 later — a newer dated float is the one divided by ("Is GMEX float accurate?")

Ajay, verbatim: "Is GMEX float accurate?"

**Not as served.** GMEX's short-interest record divides FINRA's 12,722 shares short (10-30) by Yahoo's float of 20,235 read 11-02 and served `🩳 SI High 62.9% float · float unconfirmed`. Its own share-basis doc already held Yahoo's 11-19 read: float **361,428** on the same 752,439 shares outstanding — **3.5% of float, on Yahoo's newer read, not confirmed by a filing** (both numbers are Yahoo reads; the float moved 17.9× with shares outstanding unchanged, and no SEC filing confirms either). 1.69% of shares out.

**The rule (`basis_math.newer_float`, called by the read-time verdict only):** when the basis doc's Yahoo float (the `shares_cache` row it read) is dated LATER than the record's `float_asof` and differs from it, that newer float is used for exactly two things:

1. **The division** — the % of float (and the "would read N%" on a SPLIT-refused float; a dilution refusal's is on the replaced float — refix 3 below) divides by it; its suspect check (`read._float_suspect`) pairs it with Yahoo's shares outstanding from the same row (the record's count when that row has none).
2. **The split-side check** — whether that float and the short-interest count sit on the same side of a split (`split` / `split_same_day`), judged on the newer read's date.

**Everything on the dilution side keeps the REPLACED float's own date and count** — the dilution-filing window (📄) starts at the record float's first-seen date, the share-growth check (⚠️ float stale / ⚠️ shares up) measures from the record's paired count and date, the refusal judges the replaced float, and the stored float track (`share_basis.refresh_symbol`) follows the SI record exactly as before. A newer float never moves any of these forward. Which path a name takes (float-headed vs shares-headed growth) is still decided on the replaced float, exactly as before.

The served block carries the newer float, its date and the source `yfinance floatShares (shares_cache, current row)`, and the flag `⚠️ float updated — 361,428 (Yahoo 11/19) replaced 20,235 (11/2)` (first on the chip; row "Float updated"; the EXTREME note's float line names it). The served `basis` gains `float_update` {shares, as_of, source, paired_shares, replaced_shares, replaced_asof, suspect, pct} **only when a newer float was used** — with none, the block is byte-identical to before.

- The older read never wins: a Yahoo read dated on or before the record's float date, an equal count, or a missing / undated / NaN / zero / negative Yahoo float leaves the record's float as before.
- **[C1] Nothing is replaced unless the splits read is held** (`splits.status == "ok"`; held rows after a failed retry count). With no splits on file the record's float stands. HIS CALL below.

**Why the fix (same day, verifier):** the first build moved the float's start date to the Yahoo read date, so any Yahoo float drift — SRTM moved +421 shares (552,120 → 552,541) — restarted the dilution window and the growth baseline at the Yahoo date. On main → that build, SRTM went from `0.9% shs out · ⚠️ float stale · 📄 424B3 11/6 +2` (shares 569,639 → 4,539,240, 7.97×) to `Moderate 7.2% float` with no ⚠️ and no 📄; AAOI, ALTG, ALXO, DCGO, SOAR and NUAI lost their 📄, LABT and OMH lost ⚠️ float stale, WETO lost ⚠️ shares up 14×.

**Live, 11-24 16:17 ET (read-only, api container; this branch's `short_interest` loaded from a /tmp copy, main from /app, over EVERY stored basis doc — 66 names with an SI record; 🩳 list membership on the session's 107 stored reads):**

- **Flags lost vs main: none.** 27 names carry a newer Yahoo float; each gains only `⚠️ float updated`. The other 39 are byte-identical to main.
- Replay of the 12,446 captured `si_block` inputs: 12,419 byte-identical to main, 27 differ, all with a newer float; 0 differ without one.
- Tier changes: GMEX High → Low (62.87% → 3.52%), GYGY High → Low (31.09% → 3.37%, keeps `📄 424B3 11/19 +12`), INV EXTREME → High (21.27% → 16.44%), BAK Moderate → Low (5.33% → 4.87%), WETO shares-headed → Low 1.64% (keeps `⚠️ shares up 14×`). Leaving High / EXTREME: GMEX, GYGY. Entering: none.
- Still refused, flags kept: SRTM (`⚠️ float stale · ✂️ split 11/23 · 📄 424B3 11/6 +2`), LABT and OMH (`⚠️ float stale`).
- **🩳 High SI list (and so the 9/21 cross push list): no name enters or leaves.** GMEX `floats_disagree` → `not_high`; WETO `no_tier` → `not_high`.

The probe (`scripts/si_share_basis_probe.py`) prints a "newer Yahoo float" section per name — floats and dates, % of float, tier, refusal, 🩳 High SI list membership, flags gained and **flags LOST** before (Yahoo's float removed) and now — and a `newer-float flags LOST (must be empty)` line.

### HIS CALL (newer float)

1. **No splits on file → the record's float stands** ([C1]). The alternative ("never the older one", even with no splits read) would let a post-split Yahoo float divide a pre-split count unchecked.
2. **WETO:** the replaced float (186,729) was suspect, so WETO stays on the shares-headed growth path: Yahoo's newer float (14,735,015, read with 14,897,999 shares on 11-20) now heads at Low 1.6% while `⚠️ shares up 14×` stays beside it — the 14× growth is not a refusal of the newer float. Refusing it instead would be a new rule.
3. **A float newer than the short-interest count** (GMEX, GYGY, INV: SI counted 10-30, float read later) divides an older count by a later float; when the float grew from dilution in between, the % can read low. LABT-style cases stay refused because growth is still measured from the replaced float's date.
4. **Any difference flags** (LVWR moved 79 shares and gains `⚠️ float updated`). A size cut would be a new threshold — his number, if wanted.

Tests: `backend/tests/test_si_float_newer_2026_11_24.py` (GMEX fixture; every negative; the split rules on a newer read; the suspect pairing; SRTM / AAOI / ALTG / DCGO / SOAR / ALXO / LABT on their live 11-24 numbers with "same dilution side as the record float" pinned; the byte-identical no-update block), `backend/tests/test_si_float_newer_probe_2026_11_24.py` (the probe section over the captured fixture, flags lost = none, a planted lost flag is reported, the stored track follows the record). Pins in `test_si_basis_math` / `_read` / `_integration` for KITT (now refused `diluted` only — the newer float clears the split side), WETO, JELD and the `basis` key set.

### 2026-11-24, later still — the verifier's second round (findings 1–6)

1. **A newer Yahoo float that fails its own suspect check never replaces a good record float** (`basis_math.verdict`: a suspect newer float with a non-suspect record float is dropped, and the record float, its split check and its count stand). Before: record float 1,000,000 / 2,000,000 shares, Yahoo 2,100,000 on 2,050,000 → `15.0% shs out · ⚠️ float updated`, no tier, "no float on file"; now `EXTREME 30.0% float`, as on main. With a 1-for-10 split between: before, no refusal and 5.0% off the pre-split count; now refused `split` at 50.0% shs out, as on main. When the record float is suspect too, the newer float is still served with its suspect reason.
2. **A good newer float with the record's share count across a split from the settlement:** the % of shares outstanding (and so the EXTREME float check) uses step 3's count choice (newest SEC cover or Yahoo count on the settlement's side), else the newer float's own Yahoo row count; none → no % of shares outstanding (float check "unchecked", held at High). Before: 66.7% of float read `High · float unconfirmed` off the pre-split 5.0%; now `EXTREME 66.7% float` on 200,000 post-split shares (50.0%).
3. **The "not shown — float stale" line names the replaced float** (LABT: "the float on file (847,661, yfinance floatShares (shares_cache), as of 2026-11-09) would read 18.04%", was 3,201,536 as of 11-18 at 4.78%). A split refusal under a newer float still names the newer float — that is the one across the split. The served `float_pct_on_file` is unchanged (still the newer float's %).
4. **🩳 High SI `floats_text`** under a newer float: "Float 361.4K on this card · 361.4K from Yahoo's newer read (11/19), replacing 20.2K on the short-interest record".
5. The split wording under a newer float ("first seen", its own date — never "carried across it") is pinned.
6. The fixture table above is marked "before the newer-float rule"; the current results are beside it.

**Live re-probe, 11-24 (read-only, api container; this branch's `short_interest` from `/tmp/sinewer_fix3`, main from `/app`; 72 stored basis docs with an SI record, 107 stored reads):** flags lost vs main **none**; 42 names without a newer float byte-identical to main; 30 carry a newer float. Tier changes vs main: GMEX High → Low (62.87% → 3.52%), GYGY High → Low (31.09% → 3.37%), INV EXTREME → High (21.27% → 16.44%), BAK Moderate → Low (5.33% → 4.87%), WETO shares-headed → Low 1.64%. Leaving High/EXTREME: GMEX, GYGY; entering: none. 🩳 High SI list: no entries or exits (GMEX `floats_disagree` → `not_high`, WETO `no_tier` → `not_high`). Against the previous round, only the LABT / OMH / SRTM refusal lines changed (finding 3); no live name hits findings 1 or 2 today.

Tests: `backend/tests/test_si_float_newer_fixes_2026_11_24.py` (cases a and b, newer ok, the row-count fallback and every negative, LABT's line, `floats_text`, the carried/first-seen wording); the GMEX suspect pin in `test_si_float_newer_2026_11_24.py` now expects the record float to stand.

### 2026-11-24, later still — refix 3 (the verifier's third round)

1. **A dilution refusal's on-file % is on the REPLACED float, exactly as on main** (`basis_math.verdict`: `float_pct_on_file` divides by the record float when the refusal is `diluted` and a newer float was used; a split refusal keeps the newer float's %, the one across the split). This supersedes round 2's "the served `float_pct_on_file` is unchanged". LABT: 18.04% (High) on 847,661, not 4.78% (Low) on Yahoo's 3,201,536 — so the "% of float: not shown" line and the 🩳 High SI panel's basis_text agree, and LABT stays named there as on main. The refusal line now reads this one number (no second computation in `read._refusal_line`).
2. **No "would read N%" across a split:** on a dilution refusal under a newer float, when an executed split sits between the replaced float's date and the settlement, the line names the float and its date but gives no %. KITT shape (captured inputs, not live): "the float on file (5,527,831, …, as of 2026-09-03)" with no 3.69% — that % divides a short count from after the 9/25 1-for-6 by a float from before it. The served `float_pct_on_file` (3.69%, Low, as on main) is left as it is.
3. One test pins the both-floats-suspect shape (Yahoo read after a split: not refused, the newer float is not divided by, so no split check runs on it).

**Live re-probe, 11-24 16:49 ET (read-only, api container; this branch's `short_interest` from `/tmp/refix3_wt`, main from `/app`; 72 stored basis docs, 107 stored reads):** flags lost vs main **none**; 42 names without a newer float byte-identical to main; tiers as in round 2 (GMEX, GYGY leave High; INV EXTREME → High; BAK Moderate → Low; WETO → Low 1.64%; none enter). 🩳 High SI basis_text: **LABT, SMTK on main and on this branch**. The refusal rows of LABT, OMH and SRTM are now byte-identical to main; the 27 rows that differ are the non-refused names whose % of float uses the newer float.

Tests: `backend/tests/test_si_float_newer_refix3_2026_11_24.py`; the KITT `float_pct_on_file` pins in `test_si_float_newer_2026_11_24.py` and `test_si_basis_math_2026_11_24.py` move from 12.64 to 3.69 (main's value).

## 2026-11-26 — 📄 events not copies, S-11, same-day filings, the "shares up" baseline ("can we make sure in the future these # are accurate ?")

Full write-up: `docs/short_interest/chip_accuracy_2026_11_26.md` (spec sitrack rev 2, package be-si-chip). What moves in THIS doc's rules:

- **📄 counts events.** Stored filing rows now carry `doc` / `file` / `accn` / `with`; `basis_math.filing_events` folds one prospectus document filed under several registration files into one event, and drops it when the issuer filed a report that day (the report re-filed). WHLR `📄 424B3 11/24 +18` → `📄 8-K 3.02 11/20 +4`. Rows stored before 2026-11-26 count as before and say "not yet checked for copies".
- **S-11 / S-11MEF** join `FILING_REGISTRATION_FORMS` (the "no kind" list above loses S-11). No F-11 form exists.
- **The dilution window is `>=` the anchor** (was `>`): a filing ON the float's (or share count's) date is counted and labelled "same day — which came first is not known". The charter title line reads the same events.
- **No usable float → the "shares up" baseline is the larger of the record's count and the SEC cover dated on or before it** (same split side). The float branch, step 3's count and `FLOAT_STALE_WHEN` are unchanged. `basis.growth.record_under` names the record's own count. `fell` reads the raised baseline [C8].
