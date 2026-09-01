# IPO Age — data-trust rules (2026-08-31)

## Book basis (unchanged)

TLSW Ch. 11, p. 260: "Eighty percent of the stock market winners that drove
the tech boom during the 1990s were IPOs within the prior eight years."
The block reports:

- `is_young` — listed ≤ 8 years ago (the book's youth window)
- `is_recent_ipo` — listed ≤ 2 years ago (still in primary-base territory,
  same chapter's "The Primary Base" section)

These thresholds are locked; `tests/test_ipo_age.py::test_book_thresholds_unchanged`
trips if they drift.

## The bug this doc exists for

`sepa/ipo_age.py` used to read the **first bar of the cached price frame** as
the listing date. Two facts make that wrong for almost every mature company:

1. Every price fetch has a hard lookback cap — `prices.PERIOD_DAYS` stops at
   730 days for the scan's default `"2y"`, and even `"max"` stops at 3650
   days.
2. The price cache (Mongo/parquet) is keyed by **symbol only**, so whatever
   window the *last* caller fetched is what everyone gets. In practice that
   is the scan's 2y frame, regardless of the `period` ipo_age asks for.

Live failure: `GET /sepa/candidate/SAIC` reported
`first_trade_date=2024-09-03, is_recent_ipo=true` — that date is just the 2y
cache boundary. SAIC listed **2013-09-16** (Finnhub profile2, verified
2026-08-31).

## The rules now

1. **Cap guard.** If the first bar's age lands within ±10 calendar days of
   any known fetch cap (`PERIOD_DAYS`: 365 / 730 / 1095 / 1825 / 3650), the
   frame start is indistinguishable from truncation and is never read as a
   listing date.
2. **Profile provider as the real source.** In the suspect case we ask
   Finnhub `profile2` for its `ipo` field (the app's existing profile
   provider). Successes cache in Mongo (`ipo_dates`, keyed `_id=symbol`)
   forever — listing dates are immutable. A clean "no date" answer caches
   for a week; transport errors / 429s cache nothing and simply retry on the
   next call, so a rate-limited Sunday research batch degrades to `unknown`
   and back-fills over subsequent runs.
3. **No bars-only recent-IPO claims.** Even a frame that starts *inside* the
   cap window (≤2y span, clear of every boundary) must attempt a profile
   confirm before claiming `is_recent_ipo` — the profile wins when it knows
   a date. This also covers frames that merely start late for non-listing
   reasons (provider coverage gaps, unstitched renames).
4. **Unknown is a first-class state.** When history is suspect and the
   profile can't say, the block is returned with every field `null` and
   `source: null` — never a guess. The payload gains a `source` field:
   `"history"` | `"profile"` | `null`.

## Downstream

- `is_recent_ipo` / `is_young` feed **no** scanner gate or score — the block
  is display-only (candidate detail payload + research blob). Verified
  2026-08-31: `scanner.py` imports the module but never calls it.
- FE: `SepaCandidate.tsx` renders the callout through
  `src/lib/ipoAgeLabel()`, which returns `null` for the unknown state so the
  row disappears instead of printing `IPO null · nully old`. Null flags never
  print badges.

## Tests

- `backend/tests/test_ipo_age.py` — SAIC-shaped truncation refusal, every
  cap window suspect, genuine young IPO inside the window, profile override
  of late-starting bars, no-profile-call fast path for old names, empty
  frame, future profile date, guard boundaries, threshold source-guard.
- `frontend/src/lib/ipoAge.test.ts` — label for young/old/unknown/missing,
  null-flag negatives.
