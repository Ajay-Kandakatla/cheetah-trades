# 🧮 The second dated float — Massive free float (2026-11-26)

Spec floatguard §3.2 + §3.3, work package `be-io`. Ajay 2026-11-26 ~21:20 ET: "Also the Float share count issue and SI
discrepancy happened too many times need to do something about it".

This file covers the I/O half only: where the second float comes from, how it is stored, who reads it and what it
costs. The comparison (`short_interest/source_check.py`), the nightly audit (`short_interest/source_audit.py`, package
be-audit, built) and the chip words are other packages' docs (`float_accuracy_guard_2026_11_26.md`, `source_audit_2026_11_26.md`).

## The endpoint

- `GET https://api.massive.com/stocks/vX/float` (`share_basis.MASSIVE_FLOAT_PATH`, the host by name from
  `ssr_corp.BASE_URL`, the key from `ssr_corp._key`, the getter `ssr_corp._getter` — the same host, key and session as
  the ticker reference).
- Params: `ticker.any_of` = a comma list, `limit` = `SB_MFLOAT_CHUNK` (100, the endpoint's default page size),
  `apiKey` (in params only, never in the URL text). Timeout `SB_HTTP_TIMEOUT_SEC`.
- Fields read per row: `ticker`, `free_float` (shares), `free_float_percent`, `effective_date`. Docs:
  massive.com/docs/rest/stocks/fundamentals/float — "Updated as needed"; on every stocks plan.
- `/stocks/vX/` is Massive's experimental prefix: the shape can change. Every miss is `failed`, never `none`.
- Tickers are spelled `symbols.for_massive(symbols.resolve(s))` (`BRK-B` -> `BRK.B`) and mapped back.
- Two rows for one ticker in one answer: the newest `effective_date` is kept.

## Stored shape (FROZEN) — `si_share_basis` doc, top-level `mfloat`

```
"mfloat": {"status": "ok" | "none" | "failed",
           "shares": int | None,        # free_float as published
           "pct": float | None,         # free_float_percent, 0 < pct <= 100, else None
           "as_of": "YYYY-MM-DD" | None,# effective_date
           "read_at": ts, "error": None | "<type or http_NNN>", "error_at": ts | None, "strikes": int}
```

Status rule = the house one (`share_basis._ok_sub` / `_failed_sub`):

| Answer | Stored |
|---|---|
| a usable row (`free_float` a count > 0, `effective_date` a date) | `ok` |
| an HTTP 200 with no `next_url` that lists no usable row for the name | `none` (one source only) |
| no key | `failed`, `no_key`, no GET |
| HTTP 429 / 500 / any non-200 | `failed`, `http_NNN` |
| a non-JSON 200, or no `results` list | `failed`, `malformed` |
| a 200 that names a `next_url` (a later page exists) | the names it did not answer: `failed`, `partial` |
| a raising GET | `failed`, the exception TYPE only (its text can carry the key) |
| any failure over a held `ok` / `none` read | the held data and `read_at` stand; `error` / `error_at` / `strikes` set |

A doc with NO `mfloat` key behaves exactly as before everywhere: `refresh_symbol` never adds the key by itself.

## The switch

`SB_MFLOAT_WHEN = "on"` in `SB_MFLOAT_MODES = ("off", "on")` — HIS CALL #7. Any other word = off. Off -> no
second-float call anywhere; a held `mfloat` is still carried by `refresh_symbol` and stays in the hover with its date.

## Who reads it

| Reader | When | Calls |
|---|---|---|
| the worker step `mfloat_step(sym, db)` | every name the worker pops; `kick` queues only names that `is_due`, so in practice right after a due refresh | ONE GET for the name, unless the held read is `ok` / `none`, error-free and inside `SB_REF_REFRESH_DAYS` (`fresh`) |
| the nightly `source_audit.audit_night` (spec §3.6, package be-audit, BUILT) | every 20:15 ET nightly, via `high_si.source_audit_night` in its own fence | calls `fetch_mfloats` over every `checked_symbols` name in chunks of `SB_MFLOAT_CHUNK` (100), at most `max_refresh()` GETs, then `store_mfloats` (the `--dry` run lays them over the docs in memory and writes nothing) |
| `refresh_symbol` | every refresh | NONE. It only carries a held `mfloat` (step 2b) and widens `since2` to its date (step 7) |

**Two writers of `mfloat` (corrected 2026-11-27): the share_basis worker step `mfloat_step` (a name that `is_due` and
was kicked) and the nightly `source_audit.audit_night` (`backend/short_interest/source_audit.py`, `SB.store_mfloats`
over every checked name; skipped when `SB_MFLOAT_WHEN` is off).** Inside `share_basis.py` the step is the only caller.
A name nobody kicks still gets its second float from the nightly.

`mfloat_step` returns, first match: `off` · `test` (pytest with no `http` injected — before any read) · `no_doc` (no
doc, or a seed-only doc with no `checked_at`) · `fresh` · `stored` · `failed`. The worker widens the splits window only
on `stored`. The worker's `refresh_symbol(sym, db)` call is unchanged (tests monkeypatch it positionally).

Writes: `store_mfloats` and `widen_splits` use `update_one({"_id": sym, "checked_at": {"$exists": True}}, {"$set":
{...}})` — never an upsert, never the `state|sec` / `state|fts` docs, never a seed-only doc. `checked_symbols` lists
only `_id`s that hold `checked_at` and survive `_clean`.

Why not inside `refresh_symbol`: five Massive call-count pins on it (tests/test_si_share_basis_2026_11_24.py :309,
:381, :385; tests/test_si_sec_fts_2026_11_26.py :666, :675) and three test fakes that meet an unknown path. A worker
step costs none of them. A nightly `$set` lost to a refresh that read the doc a moment earlier is put back by the same
worker's `mfloat_step`.

## The splits window and why it is widened

A basis doc's `splits` holds only rows with `execution_date >= splits.since`. Massive does not re-date a float on a
split (SMX float 08-13 with a split 11-09; WHLR 10-08 with 10-30; DKI 10-20 with a 1-for-50 on 10-22). So a second float
dated before `splits.since` cannot be split-rebased until the window reaches its date: 124 of 693 names on 11-26.

- `needs_window(doc)`: a held `ok` `mfloat` with a dated `as_of`, and no dated `splits.since` or `as_of < splits.since`.
- `refresh_symbol` step 7: `since2 = min(since2, mfloat.as_of)` for a held `ok` one. ONLY `since2` — the SEC window
  `since` and the 📄 flags never move; `doc["sec"]` is the same with and without a held `mfloat`.
- `widen_splits(sym, db, ...)`: ONE splits read from the second float's date through `_splits_sub` (step 7's own body,
  moved verbatim) -> `widened` | `not_needed` (no call) | `no_doc` | `failed` | `test`. `store=False` writes nothing and
  returns the sub (the audit's dry run lays it over the doc in memory). A failed read keeps the held rows and `since`
  and sets `error` (the status rule; `is_due` then re-reads the name on its usual error retry).
- `is_due` is NOT changed (no stampede after deploy).

## Cost

- Today: one GET per due, kicked name whose held read is not `fresh` (the worker step), plus one splits read when its
  second float is older than the window.
- The nightly (be-audit, built): one GET per 100 checked names — about 8 GETs for the 792 docs of 11-26 — capped at
  `max_refresh()` (`GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS`, 120) float GETs, plus its own budget of `max_refresh()` outside
  reads a night for refreshes and splits widening (see `source_audit_2026_11_26.md`).

## Sources read 11-26 (spec §1.4)

| Source | Carries | Automated read | Verdict |
|---|---|---|---|
| SEC cover dei / 20-F / 40-F (data.sec.gov) | shares outstanding, as-of | already read (`fetch_covers`) | have |
| 6-K stated number (efts.sec.gov) | shares added + running total, filed date | already read (047acbb4) | have |
| Massive ticker details | two share counts, NO as-of | already read (`fetch_ref`) | have; never compared |
| Massive `/stocks/vX/float` | free float + effective date | house key, same host | ADDED here |
| Nasdaq api `/quote/SYM/summary`, `/info` | no share count (MarketCap only) | robots.txt and terms page timed out twice — unread | NOT USED |
| StockAnalysis statistics | shares + float, no date, 3 digits | robots.txt allows the page; Terms of Use (2026-11-10) bar bots / scripts / scrapers, with an exception for crawlers that follow robots.txt | NOT USED (his call #8) |
| Finviz quote | shares + float, no date, 3 digits | robots.txt does not list /quote.ashx; terms page could not be fetched (3 URLs, 404) — UNREAD | NOT USED until read (his call #8) |

So Finviz's NCPL 2.09M cannot be machine-checked. The one dated second float (Massive 4,246,497, 08-14) sides with
Yahoo's 4,387,760 (11-18).

## CLI

```bash
cd backend && .venv/bin/python -m short_interest.share_basis mfloat --symbols NCPL,DKI
```

Prints the parsed answer, writes nothing, needs no database. `refresh` / `show` print ` | mfloat <status>` when the doc
holds one.

## Tests

`backend/tests/test_si_mfloat_2026_11_26.py` over the real 11-26 answer (`backend/tests/fixtures/massive_float_2026_11_26.json`,
a keyed extract of the planner's capture, no key). The six named pins and the share-basis / sec_fts / integration /
probe suites stay green with no existing test file edited.

## Correction (2026-11-27)

This page first said the nightly was "planned, not built" and the worker step was the only writer. Wrong once be-audit
landed: `backend/short_interest/source_audit.py` (`audit_night`, called from `chart_maps.gajjala.nightly` through
`high_si.source_audit_night`) calls `SB.store_mfloats` every night. Rows above rewritten as built; the pin
`test_doc_names_two_writers_and_the_nightly_as_built` now holds the true wording.
