# 🩳 EXTREME short-interest note on 🎾 cards + 👀 Watch tiles (2026-11-18)

## The ask, verbatim

Ajay 2026-11-18 ~01:45 ET: "When there are extreme cases of short interest make a not for them on reversal squeeze like percentage of short interest on the tickers card and also on watch list"

## What it is and where it shows

> Superseded later on 2026-11-18 (see the tier section below): the chip now reads `🩳 SI EXTREME 44.0% float …` (CLRO), `chip_text` has no `tag=` argument, and AKAN is no longer EXTREME (float unconfirmed → High). The examples in this section and in "Served payload" are the first 11-18 shape.

- **🎾 Reversal Squeeze card** (🚩 Gajjala's 5-min, 🧪 Audited, and the 1-min page through the same card line until that page is retired): the existing 🩳 label **becomes** the note when the read is extreme. It stays ONE line (Rule #5: the SI prints once). Example: `🩳 EXTREME SI 36.4% float · 1.0d · 10/30`. It is bold, and hovering shows the full sentence.
- **👀 Watch tile** (his rows and the 🤖 auto rows): a short chip in the tile head, `🩳 EXTREME SI 36.4% float`. The full sentence shows on hover. In a fitted grid it stays on one line.
- Everything else is unchanged: the chip on non-🎾 cards, the 📋 all-strategies 🩳 column, ordering, pushes, gates, lanes and K8.

## The rule (built by name, never retyped)

- Served by the ONE SI read: `backend/short_interest/read.py` → `si_block(doc)["extreme"]`, built by `extreme_block` / `extreme_title`.
- Cut: `pct_of_float >= client.SI_HIGH_PCT` (env `SI_HIGH_PCT_FLOAT`, default 20). The check runs on the **served 2-dp** `pct_of_float`, so the printed figure and the verdict always agree: a raw 19.996 % prints 20.0 % and gets the note, while 19.99 % does not.
- It shows only when `status == "ok"` and `headline_basis == "float"`. A stale read, a no_record miss, a suspect float, or a read with only shares outstanding all get `extreme: null`, never a 0 %.
- **The constant's home use is a different rule.** `client._squeeze_signal` applies `SI_HIGH_PCT` to **% of shares OUTSTANDING**, and it also calls a name "high" at `SI_ELEV_PCT` with `SI_HIGH_DTC` days to cover. **This note mirrors neither.** It uses % of float with `>=` only, so a 12 % / 6-day name is "high" there and un-noted here (pinned by a NEGATIVE test). `SI_HIGH_PCT` is the app's standard high-short-interest heuristic: it is not from any book and is not one of GG's rules. GG has no short-interest rule in any source.
- A failure inside the note never costs the chip. `si_block` catches it, logs it and serves `extreme: null`, and `si_map` still carries the name.

## Float basis

The % counts **the float stored with the short-interest record at the last warm**, not today's `shares_cache` row that the card's Float chip reads. The two can differ. AKAN on 2026-11-18: the 🩳 read serves **36.4 %** of the SI-doc float (531,210 shares as of 2026-10-22), while the 11-17 study's 27.2 % used today's float. The hover says which float it counts. Changing the basis = the 11-08 HIS CALL #3, a change to every 🩳 chip.

## Served payload

`GET /short-interest/map?symbols=…` → `items[SYM].extreme`:

```
{"text":  "🩳 EXTREME SI 36.4% float · 1.0d · 10/30",   // chip_text(b, tag="EXTREME ") — the chip's own builder
 "short": "🩳 EXTREME SI 36.4% float",                  // the 👀 tile form
 "title": "🩳 EXTREME short interest — 36.4% of the float is sold short at the FINRA settlement 2026-10-30 (published ~2026-11-10), at or above 20% of the float — the app's standard high-short-interest heuristic (SI_HIGH_PCT; not from any book, not one of GG's rules). … Not advice.",
 "basis": "si_doc_float"}
```

or `null`. `_BLOCK_KEYS` ends with `"extreme"`. The front end prints these strings verbatim and does no arithmetic on SI fields (contracts.mjs).

ℹ️ Rules: one pick was added to the 🩳 section. It is built from `EXTREME_RULE_NOTE % SIC.SI_HIGH_PCT` and `EXTREME_STUDY_NOTE`.

## Measurement

**UNMEASURED.** The 2026-11-17 SI × cradle study (`eod-audits/research/2026-11-17_si_cradle_squeeze/report.md`) was **too small to call either way**: no direction may be quoted from it. The note is display only. It is never a push, gate, sort, size or lane input.

## Tests

- Backend: `backend/tests/test_si_extreme_note_2026_11_18.py`.
  - Positive cases: the AKAN pin from the live probe (text / short / basis / title), the exact-cut `>=` at 20.0, and the 19.996 rounding seam.
  - NEGATIVES: 19.99 → none and the chip unchanged; stale (legacy, and AKAN on 11-30) → none; no_record → `extreme` present and null; a suspect float (UHAL, and the BRK-B shape) → none; shares-out-only ≥ 20 → none; the client's dtc disjunction (12 % / 6 d) is not mirrored; dtc 0 / None / NaN → the days segment is dropped and never "0.0d"; missing leaves → "n/a"; a raising `extreme_title` → chip served, `extreme` null, and `si_map` keeps the name.
  - The constant moves the cut (40 → none, 30 → "30% of the float"), and the ℹ️ pick moves with it.
  - FORBIDDEN-word scan over every served extreme string and the pick, and no "band" / "did not run".
  - `chip_text(b)` equals the fixture chip for every case, so the refactor is byte-neutral.
  - A SOURCE GUARD finds no numeric literal in the EXTREME slice (only the zero sign guard), and its own mutants (`pf < 20`, a typed "20%") are caught.
- Frontend (other work packages): the `siExtreme` lib, `GgSiExtremeNote`, `GgShortInterestLabel` (one line), `GajjalaBoard.si_extreme.test.tsx`, and `GajjalaWatchBoard.si_extreme.test.tsx`, each with NEGATIVES. The Watch GET-count pins in `GajjalaWatchBoard.test.tsx` (`:217, :236, :240, :244, :247, :265`) moved to pathname filters, because the note adds ONE `/short-interest/map` GET per mount.

## Fixture regenerated

`backend/tests/fixtures/short_interest_blocks_2026_10_03.json` was regenerated with `si_block` (`json.dumps(indent=1, ensure_ascii=False) + "\n"`). The diff is exactly:

- 7 × `    ]` → `    ],` (each block's `rows` close);
- 5 × `    "extreme": null` (bynd_v2_float, fcg_v2_no_denoms, uhal_v2_conflict, eose_v1_legacy_stale, no_record_miss);
- 2 × six-line `"extreme": {…}` dicts:
  - eose_v2_float: `🩳 EXTREME SI 33.6% float · 4.1d · 9/15`;
  - dtc_missing: `🩳 EXTREME SI 33.6% float · 9/15`.

No `chip` / `title` / `rows` leaf moved.

## HIS CALLs (defaults built; none decided as a rule)

1. **The cut:** `SI_HIGH_PCT` on % of float with `>=` (default). The alternatives:
   - (a) % of shares outstanding, as in the constant's home;
   - (b) also admit `SI_ELEV_PCT` + `SI_HIGH_DTC` days to cover;
   - (c) a measured cut, which needs a re-run of the study.
2. **Float basis:** the SI-doc float (default). The alternative is today's `shares_cache` float (11-08 HIS CALL #3).
3. **Stale read** → no note (default). The alternative is the note with the "stale" word.
4. **Shares-out-only basis** → no note (default).
5. **Watch:** the short form in the tile head (default). The alternatives are the note on the ⤢ stretch only, or the full text.
6. **The 1-min page** shows it through the shared card line (default). The alternative is a variant gate.
7. **ONE line on the 🎾 card** (default). The alternative is a second line under the label.
8. **✨ wording** names the heuristic without typing 20 % (default).
9. **GgCardView ⤢** shows no Watch-style chip (default).
10. ~~The 📋 all-table column and non-🎾 muted chips get no EXTREME mark (out of scope).~~ **Superseded 2026-11-18 (later) for the WORD only:** every chip, the 📋 column included, now carries the tier word (see below). No colour, no bold outside the 🎾 card.
11. **ℹ️ pick:** keep or strike.
12. **"Not advice." + the study line in every hover:** keep or strike.

UNMEASURED. Not advice.

Pins that moved: `GajjalaWatchBoard.test.tsx` :217 (full / rows GET split) and :236 / :240 / :244 / :247 / :265 (the rows GET counted through the GGW_PATH + `?symbols=` filter), because the Watch board now also batches the 🩳 read for the head note.

## 2026-11-18 (later) — tier words + float confirmation (AKAN defect)

### His words

Ajay 2026-11-18 ~15:50 ET: "Is the short interest you got for AKAN accurate?" → "I see it as less now" → to the proposal "only call 🩳 EXTREME when it's ≥ 20% of float AND ≥ 10% of all shares":

> "Yes please and may be add better terminilogy like Moderate with a percentage relative to float."

### The defect (live read, 2026-11-18)

| name | shares short | float on file | shares out | % of float | % of shares out | before | now |
|---|---|---|---|---|---|---|---|
| AKAN | 193,393 | 531,210 (as of 2026-10-22) | 2,388,212 | 36.41 | 8.1 | `🩳 EXTREME SI 36.4% float · 1.0d · 10/30` (**wrong**) | `🩳 SI High 36.4% float · float unconfirmed · 1.0d · 10/30`, no note |
| CLRO | 391,224 | 888,130 (as of 2026-11-10) | 2,675,412 | 44.05 | 14.62 | EXTREME (right) | `🩳 SI EXTREME 44.0% float · 1.0d · 10/30`, note kept |
| SLSN | 359,433 | — | — | — | — | `🩳 SI 359.4K sh · 19.5d · 10/30` | unchanged |

AKAN's Yahoo float is stale after a dilution (StockAnalysis: float 2.39M, shares +634% QoQ); the true short is ~8.1% of all shares (Finviz 8.09%). CLRO's float matches StockAnalysis (888,125).

### The rule (built by name, `backend/short_interest/read.py` → `si_tier`)

- **Ladder** on the served 2-dp **% of float**, half-open: Low < `SI_MODERATE_PCT` (5, new in client.py) ≤ Moderate < `SI_ELEV_PCT` (10) ≤ High < `SI_HIGH_PCT` (20) ≤ EXTREME. A common market convention (StockAlarm 5/10/20, Schwab + MarketBeat 10/20, LuxAlgo ~20) — not from any book, not one of GG's rules.
- **EXTREME also needs the float confirmed:** % of shares outstanding ≥ `SI_EXTREME_MIN_PCT_SHARES_OUT` (10, new in client.py, NOT env-tunable — his number).
- **Unconfirmed** (shares out known, below 10%) → the word stops at **High**, and the chip adds `float unconfirmed`. **Unchecked** (no shares out on file) → High with no flag (0 live names). The cap is explicit (`t = TIER_HIGH`), so it is **monotone**: at a fixed float and shares out, more short interest never reads a lower word (T5 sweep; N13 shows the v1 "re-tier on shares out" rule fails it).
- **The float check runs on stale reads too**: no tier word on a stale read, but `float unconfirmed` stays on the chip, so AKAN's 36.4% never comes back unflagged after ~11-27.
- **No tier word** on: a stale read; a shares-outstanding-only read (suspect float or no float); no denominator; a 0% of float; an out-of-order ladder at run time (`_ladder_ok()` — an env mistake never prints a wrong word, and serves no EXTREME note).
- **The EXTREME note fires only when `tier == "extreme"`**, and its text IS the chip: `🩳 SI EXTREME 44.0% float · 1.0d · 10/30`; short form `🩳 SI EXTREME 44.0% float` (the word order flipped from `🩳 EXTREME SI …`). The note's hover adds "That is at or above the 10% of shares outstanding that confirms the float (SI_EXTREME_MIN_PCT_SHARES_OUT)."
- **Every % print** goes through `_pct_tier`: one decimal as before, two decimals only where one-decimal rounding would carry the figure up across a cut (5 / 10 / 20 / the 10% confirmation). ULCC's hover says `9.98%`, never `10.0%`; a 19.99% float reads `High 19.99% float`, never `High 20.0%`. The decision stays on the served 2-dp value.
- **Where the words print:** the chip (every Chart Maps tab, ticker page, 🎾 card label, 👀 tags row, 📋 `si_text`), a short `Tier: …` sentence in the hover (only the word's own range — the hover never names EXTREME for a Low / Moderate / High read), a `Float check: …` sentence when there is a float to check, and two ticker-panel rows: **Tier** (sentence + the full ladder) and **Float check**. The full ladder also prints in ℹ️ Rules → 🩳 (pick 2, rewritten).
- Served keys: `tier` (`low` / `moderate` / `high` / `extreme` / null) and `float_check` (`confirmed` / `unconfirmed` / `unchecked` / null), right after `float_suspect` in `_BLOCK_KEYS`. The 📋 all-table gets the words through `si_text` only — `SI_KEYS` is still 4 keys, so the gg5 golden does not move.
- Nothing sorts, gates or pushes on it; `_float_suspect` is byte-identical (context.py's Float-suspect chip and the cradle study import it). Display only. **UNMEASURED.**

### Served forms

| doc shape | tier | float_check | chip | extreme |
|---|---|---|---|---|
| AKAN @11-18 | high | unconfirmed | `🩳 SI High 36.4% float · float unconfirmed · 1.0d · 10/30` | null |
| AKAN @11-30 (stale) | null | unconfirmed | `🩳 SI 36.4% float · float unconfirmed · 1.0d · 10/30 · stale` | null |
| CLRO @11-18 | extreme | confirmed | `🩳 SI EXTREME 44.0% float · 1.0d · 10/30` | text = chip |
| CLRO @11-30 (stale) | null | confirmed | `🩳 SI 44.0% float · 1.0d · 10/30 · stale` | null |
| ULCC shape 32.98 / 9.98 | high | unconfirmed | `🩳 SI High 33.0% float · float unconfirmed · …`; hover "only 9.98% of all shares" | null |
| float 36% + no shares out | high | unchecked | `🩳 SI High 36.0% float · …` (no flag) | null |
| 0% of float | null | null | `🩳 SI 0.0% float · …` | null |
| 19.99% of float | high | null | `🩳 SI High 19.99% float · 1.0d · 10/30` | null |
| SLSN (no float) | null | null | `🩳 SI 359.4K sh · 19.5d · 10/30` | null |

### Population (live SI cache, 2026-11-18, main code)

- 23,862 docs, 22,552 `ok`; headline basis float 3,459 / shares_out 186 / none 18,907.
- Float-basis reads ≥ 20% of float: **354** — **299 confirmed**, **55 unconfirmed**, 0 unchecked. Unconfirmed examples (% of float / % of shares out): SECZ 95.4/4.76, FAMI 77.8/2.9, UCAR 70.3/0.93, AKAN 36.4/8.1. Closely-held names that look **genuine** also stop at High: ULCC 32.98/9.98, CRK 41.78/9.03, BKV 30.04/8.55, FLOC 38.13/8.67, COKE 31.98/4.5 (HIS CALL #3).
- **Residual nothing checks:** float-basis reads below 20% whose float tier is above their shares-out tier — 54 High-on-float / Low-on-shares-out (ACT, AIRS, ARDT, AXG, ARM), 247 High / Moderate, 240 Moderate / Low. Most are genuine (ARM 11.06 / 1.48); only a second float source could tell them apart (HIS CALL #5).

### Three floats on one 👀 tile (AKAN)

The 🩳 chip counts the float stored with the SI record (**531,210**, as of 2026-10-22, named in its hover). The tile's own **Float chip** prints **~0.71M** from today's `shares_cache` row. StockAnalysis says **2.39M**. **The Float chip is not checked by this build** — wiring it to `float_check` is HIS CALL #12.

### Fixture regenerated

`backend/tests/fixtures/short_interest_blocks_2026_10_03.json`, every block rebuilt with `si_block` (`json.dumps(indent=1, ensure_ascii=False) + "\n"`), plus three new cases copied from `eose_v2_float` (settlement 2026-09-15, dtc 1.0): `akan_shape_unconfirmed` (193,393 / 531,210 / 2,388,212), `clro_shape_extreme` (391,224 / 888,130 / 2,675,412), `float_unchecked` (36,000 / 100,000 / no shares out). Leaf diff on the seven existing cases:

- every block gains `tier` and `float_check` (after `float_suspect`);
- chips: `eose_v2_float` → `🩳 SI EXTREME 33.6% float · 4.1d · 9/15`, `dtc_missing` → `🩳 SI EXTREME 33.6% float · 9/15`, `bynd_v2_float` → `🩳 SI Low 1.0% float · 4.7d · 9/15`; fcg / uhal / legacy-stale / no_record chips unchanged;
- titles + rows: eose / dtc_missing gain `Tier: EXTREME (20% or more of the float).` + `Float check: confirmed — 33.2% …` and the Tier / Float check rows; bynd gains `Tier: Low (under 5% of the float).` + the Tier row; fcg / uhal gain the no-usable-float Tier sentence + row; legacy-stale gains `Tier: not given on a stale read.` + row; no_record unchanged;
- `extreme` (eose / dtc_missing): `text` → the new chip order, `short` → `🩳 SI EXTREME 33.6% float`, `title` gains the confirmation sentence.

No other leaf moved.

### Tests

- NEW `backend/tests/test_si_tier_2026_11_18.py`: T1 AKAN (exact chip, basis float, served % unchanged, Tier / Float check sentences and rows), T2 CLRO, T3 the six cut values + the confirmation seam, T4 `si_map`, **T5 monotonicity sweep** over six (float, shares out) pairs incl. the critic's 19,990 → High / 20,000 → High, T6 seam prints (ULCC 9.98%, `_pct_tier` table), T7 short hover. NEGATIVES N1 no float, N2 stale (AKAN keeps `float unconfirmed`), N3 shares-out basis, N4 unchecked, N5 the note never fires unconfirmed (4 × 3 sweep), N6 NaN, N7 no_record keys, N8 a raising `si_tier` never costs the chip, N9 `_float_suspect` untouched, N10 FORBIDDEN + "band" scan, N11 the 0% guard, N12 an out-of-order ladder / a raised confirmation, N13 the sweep catches the v1 rule. C1–C4 constants by name. SOURCE GUARD over the tier slice + its mutants (`< 5`, `>= 10`, `"under 5%"`).
- Re-pinned with `# 2026-11-18 sitier:` comments: `test_si_extreme_note_2026_11_18.py` (AKAN → the NEGATIVE, CLRO → the positive pin, cut tests on `so=200_000`, stale AKAN keeps the flag, map / dtc / raising-note on the CLRO shape, `tag=` dropped, + `clro_shape_extreme`, 3 new guard mutants, tier names absent from alerts / autopilot / board.py); `test_short_interest_read_2026_10_03.py` (fixture chips, 10 case names, the EXTREME / High forms); `test_gajjala_all_table_si_2026_11_16.py` (`🩳 SI EXTREME 30.0% float · 2.3d · 9/30` + a NEGATIVE that `SI_KEYS` is still the 4-tuple).
- Mutation-checked (bytecode purged): the High cap removed, `_ladder_ok` dropped, `_pct_tier` → `_pct1`, `p <= 0` → `p < 0`, the `tier == extreme` note guard removed — each turns tests red.

### HIS CALLs (defaults built; none decided as a rule)

1. **Cut-offs** Low < 5 ≤ Moderate < 10 ≤ High < 20 ≤ EXTREME on % of float (alternative: StockAlarm's five steps, Elevated 10–20, High 20–30, Extreme > 30).
2. **The 10–20% word:** "High" (default) or "Elevated".
3. **Confirmation at ≥ 10% of shares outstanding** (his yes) holds genuine closely-held floats at High (55 of 354). Alternatives: a second float source, or a lower confirmation.
4. **What an unconfirmed float reads:** % of float, High, `float unconfirmed` (default, monotone) vs leading with % of shares outstanding (AKAN `8.1% shs out`, like Finviz) — then more short interest reads a lower word at the 20% cut.
5. **Floats below 20% are never checked** (541 names with a float tier above their shares-out tier).
6. **Shares out unknown + float ≥ 20%:** High, no flag (default) vs EXTREME on the float alone.
7. **Shares-out-only reads:** no word (default) vs the ladder on % of shares outstanding (ETFs would read EXTREME).
8. **Stale read:** no word, flag kept (default) vs the word + "stale".
9. **Decide on the served 2-dp %, print 2-dp at a seam** (default) vs deciding on the printed figure.
10. **No colour by tier** (10-03 neutral tone) vs tinting via `data-si-tier`.
11. **Chip token** `float unconfirmed` (default) vs "unconfirmed float" / none.
12. **The 👀 tile's Float chip** stays unchecked vs reading the served `float_check`.

UNMEASURED. Not advice.
