# 🩳 % of float: dilution, splits, filings — frontend half (2026-11-24)

Ajay 2026-11-24, in order:

> "Yeah please"
> "Make sure we are looking for Dilution.."
> "Also split related events and filing so we flag them in the right way"

Spec: `sidilute` §3.7 (work package `fe`). The engine, the verdict and every word are on the backend
(`backend/short_interest/basis_math.py`, `read.py`, `share_basis.py`; see `docs/short_interest/float_dilution_split_2026_11_24.md`).

## What the frontend does

- **Prints, never builds.** The flags (`⚠️ float stale`, `⚠️ shares up N×`, `✂️ split M/D`, `✂️ split due M/D`, `📄 S-4 M/D`,
  `❔ shares fell N×`, `❔ share count unchecked`, `❔ last check failed`, `❔ dilution unchecked`) arrive INSIDE the served
  `chip`, `title`, `rows`, `extreme.short` / `extreme.title` and the 🩳 card's `state_label`. The house 🩳 chip, the 🎾 card
  label, the 👀 Watch tags row and the 👀 EXTREME note print them as served. No new chip component, no colour.
- **Types** (`frontend/src/lib/shortInterest.ts`): `SiBasis`, `SiFlag`, `ShortInterestRead.basis?`. A block with no `basis`
  key (an older API, or a name never checked) is read exactly as before.
- **Guards** (same file): `siBasisPending(read)` — `basis.pending === true` strictly (a string, `1`, `null` are not pending) →
  the served `retry_after_sec` in ms clamped into `[SI_FOLLOWUP_MIN_MS = 5000, SI_FOLLOWUP_MAX_MS = 120000]`; a NaN / negative /
  string / absent delay reads the minimum. `siFlags(read)` — well-formed flags only (four strings, non-empty `key` and `short`), `[]` otherwise.
- **Follow-up re-ask** (`frontend/src/hooks/useShortInterest.ts`) `[C5]`: the map route marks a name whose background check is
  queued or running with `basis.pending` + `retry_after_sec`. One module-level map and ONE timer re-ask those names: the k-th
  re-ask after `clamp(served × 2^(k-1), 5 s, 120 s)` — at a served 20 s that is 20 + 40 + 80 + 120 + 120 + 120 s = 500 s — at most
  `SI_FOLLOWUP_MAX = 6` in a row. A non-pending answer clears the name; due names go out together in chunks of `SI_CHUNK` (200).
  No mounted listener when the timer fires → nothing is asked and the map clears. `_resetShortInterestCache` clears both.
  A failed follow-up keeps the last read on screen and ends that name's series (no retry loop; the normal TTL / retry rules apply).
- **🩳 High SI panel** (`frontend/src/components/GgHighSi.tsx`): the served `basis_text` (the names that were High / EXTREME on
  the float on file but whose float is stale or across a split — not tiered, so not listed) prints right after the counts line,
  testid `gg-hs-basis`. `GgHighSiBlock.basis_text?` in `frontend/src/lib/gajjala.ts`. A number / empty / NaN / null prints nothing.

## Judgement calls in this package

- `SI_FOLLOWUP_MIN_MS` / `SI_FOLLOWUP_MAX_MS` live in `lib/shortInterest.ts` (the guard clamps with them) and are re-exported by the
  hook — one definition, no import cycle.
- A failed follow-up deletes the name from the follow-up map (the spec says only "keeps the last read"); a later pending answer
  starts a new series at the served delay.
- A name that hit the cap stays capped (no further re-asks) until a non-pending answer clears it — the `useBorrow` precedent.

## Tests

- `frontend/src/lib/shortInterest.basis.test.ts` — the guards; junk `pending` / `retry_after_sec` / `flags`; `parseSiMap` passes `basis` through.
- `frontend/src/hooks/useShortInterest.basis.test.ts` — the re-ask, the doubling and the cap, the reset, the failed follow-up,
  no listener, chunking on one timer, the older API (no timer).
- `frontend/src/components/GgHighSi.basis.test.tsx` — `basis_text` placement and the junk values.
- `frontend/src/components/GgSiExtremeNote.basis.test.tsx` — the SMTK chip verbatim through the chip, the 🎾 label and the
  👀 Watch tags row; JZ's `extreme.short` with `✂️ split due 12/24` verbatim on the Watch tile with its title.

Display only. UNMEASURED: nothing here is a signal.
