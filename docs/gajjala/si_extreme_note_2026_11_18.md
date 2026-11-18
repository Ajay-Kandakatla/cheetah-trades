# 🩳 EXTREME short-interest note on 🎾 cards + 👀 Watch tiles (2026-11-18)

## The ask, verbatim

Ajay 2026-11-18 ~01:45 ET: "When there are extreme cases of short interest make a not for them on reversal squeeze like percentage of short interest on the tickers card and also on watch list"

## What it is and where it shows

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
10. The 📋 all-table column and non-🎾 muted chips get no EXTREME mark (out of scope).
11. **ℹ️ pick:** keep or strike.
12. **"Not advice." + the study line in every hover:** keep or strike.

UNMEASURED. Not advice.

Pins that moved: `GajjalaWatchBoard.test.tsx` :217 (full / rows GET split) and :236 / :240 / :244 / :247 / :265 (the rows GET counted through the GGW_PATH + `?symbols=` filter), because the Watch board now also batches the 🩳 read for the head note.
