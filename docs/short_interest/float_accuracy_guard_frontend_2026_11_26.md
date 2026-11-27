# Float accuracy guard — frontend (2026-11-26, spec floatguard §3.9, WP fe)

Ajay 2026-11-26 ~21:20 ET: "Also the Float share count issue and SI discrepancy happened too many times need to do something about it".

## 2026-11-26 — what the frontend draws

Display only. Every word and number is served by the backend; the frontend computes nothing on a short-interest field.

- **🧮 GgSiAuditSection** (`frontend/src/components/GgSiAudit.tsx`) — the nightly float and share-count source audit
  (`high_si.block` → `si_audit`, built by `short_interest/source_audit.served_block`).
  - Where: inside the 🩳 High SI panel, right after the 🏁 SI track record, on the same mount line
    (`GgHighSi.tsx`). So on the 🚩 board it sits inside the 🩳 sub's closed ⓘ fold. Nothing new on the landing.
    `GgHighSiState` does not draw it.
  - Absent or not an object → nothing. A served `fault_text` → one error line, no fold. No served `summary_text` → nothing.
  - Otherwise ONE closed fold (`data-testid="gg-sa"`). Its summary is the served summary. The body mounts only while open:
    title, as-of, empty line, the table, shown line, then a nested closed fold for the rule text + the honesty paragraph.
  - The table: the served `heads`. The first column is the row's symbol, linked only through `ggHref` (a junk href is plain
    text). Every other column is the served cell for that head key. A row served `contested` carries `data-contested`. A row
    served `held` carries `data-held`. A row with no served symbol is dropped. A NaN / number / empty cell prints nothing.
  - The file types no tier word, no "sources disagree", no digit, and formats no number. House classes only — no CSS edit.
- **🩳 SEPA card chip** (`RealtimeChips.tsx` + `hooks/useRealtimeSignals.ts`) — the hover gains one served sentence naming
  the share count the % divides by: `Share count: {shares_source}`, plus `, as of {shares_asof}` when served. Today the
  backend serves `Massive ticker details — the provider gives no as-of date`. No number changes. With no `shares_source`
  (an older API) the hover is today's, byte for byte.
- **Chips, card label, EXTREME note, panel** — no code change. The hover is the served `title`, the panel prints the served
  rows (the new `Float sources` row arrives as a served row), the chip prints the served text (with `⚠️ sources disagree`
  when served).

## The arithmetic guard, widened

`contracts.mjs` pins the pattern
`(pct_of_float|pct_of_shares_out|pct_of_shares|days_to_cover|si_shares|short_interest)[^;\n]*(toFixed|[*\/+-]\s*\d)` on three
files. `frontend/src/lib/shortInterest.arith_guard.test.ts` runs the same pattern over every non-test source file under
`src/` (630 files on 11-26).

- Comments are stripped first. On 11-26 the raw pattern finds exactly one line in all of `src/`: a COMMENT in
  `lib/newFeatures.ts` that quotes a backend path followed by "(S-11)". A comment computes nothing, so stripped it finds zero.
- Planted lines trip it (`pct_of_float * 100`, `pct_of_shares.toFixed(1)`, …). A float-turnover line
  (`volume / float_shares`) and a served print (`${si.pct_of_shares}% of shares outstanding`) do not.

## Tests

- `frontend/src/components/GgSiAudit.test.tsx` — the section standalone and inside the panel, its negatives, its source guards.
- `frontend/src/components/RealtimeChips.siSource.test.tsx` — the served sentence; an older API keeps today's hover.
- `frontend/src/lib/shortInterest.arith_guard.test.ts` — the widened guard; the admin address is in no touched file.

Re-run: `cd frontend && rtk proxy npx vitest run src/components/GgSiAudit.test.tsx src/components/RealtimeChips.siSource.test.tsx src/lib/shortInterest.arith_guard.test.ts`
and `rtk proxy npx tsc --noEmit -p tsconfig.json`.

Not advice. UNMEASURED — what two data providers say; neither was checked against a filing.
