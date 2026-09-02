# Promo-circuit watch

**Shipped 2026-09-01.** Tracks the StockTwits alert/pump accounts we caught
seeding the 8/31–9/1 tiny-float movers, and turns their fresh tags into
(a) a SEEDING watchlist on the Catalysts page and (b) a −15 conviction
penalty on the predictions board. Includes the two EDGAR tells from the same
study. **Not book logic** — catalysts family, uncited market-structure
convention (no Minervini scope; see feedback_sepa_book_scope).

## Where it came from (measured basis)

The 2026-09-01 chatter-provenance study traced WHO called 11 board movers in
advance, with exact StockTwits message timestamps (global sequential IDs) and
EDGAR acceptance times:

- **The "predictions" were mostly the promotion itself.** @ShangVXO touted
  PETZ (8/19) and FLYE (8/20) via "_ProfessorGamma"; both went vertical the
  same Monday 8/31 on near-silent public tapes (FLYE: zero public posts
  8/29–9/1 premarket, 10,957× volume). @topstockalerts ran the NWGL alert
  loop from 8/19 into a 98.4M-share resale shelf. @beppels watchlisted RDAC
  8/21+8/25, re-flagged it premarket the day it ran +44%.
- **Chatter velocity LAGGED price in 5 of 10 cases** — crowds arrive after
  the candle. The only advance signals were **named accounts**, not volume
  curves.
- **The one genuinely predictive public signal was EDGAR**: Markiplier's
  GPRO 13G hit EDGAR six sessions before the +46% day; resale/shelf filings
  (NWGL, SSM 19.9% direct, LIDR ATM) marked the exit-liquidity setups.

Hence the two rules encoded here: **a roster tag is the promotion, never
foresight** (negative signal, early warning), and **13D/G + shelf filings
ride along** for every watched ticker.

## Architecture

`backend/catalysts/promo_circuit.py`

1. **Roster** — `PROMO_ACCOUNTS`, user-editable like
   `frontend/src/lib/fundTiers.ts`. Tiers: **S** documented pump-circuit
   tell (silent-tape verticals), **A** alert-room promoters (sell access,
   victory-lap loops), **B** watchlist reposters (context only — never
   penalize).
   **Maintenance recipe:** when Ajay says "add account X to the promo
   circuit", add one entry with tier + a *dated* evidence line, deploy
   `api cron`. No other change needed.
2. **Sweep** (cron, `python -m catalysts.promo_circuit`) — fetches each
   account's public user stream (`streams/user/{handle}.json`, ~14–20
   requests per run; paginated back past the previous sweep so overnight/
   weekend cron gaps can't drop a prolific account's early-evening seeds),
   extracts ticker tags, upserts per `(account, ticker)` into Mongo
   `promo_circuit_tags` with a **per-ticker** message-ID high-water mark
   (re-sweeps never re-count; an account-wide mark could bury a sibling
   ticker whose upsert failed). A dormant account re-tagging after ≥14 days
   resets `first_tagged_at` — a new campaign. Weekdays every 30 min
   7:00–19:30 ET; weekends every 2 h (the 8/31 movers were groomed on
   Saturday/Sunday). ETFs/megacaps/crypto symbols are excluded at
   extraction. StockTwits sits behind Cloudflare bot protection that 403s
   `requests` — the fetch uses **httpx + a browser UA** (measured
   2026-09-01), which is also the root cause of the chatter fetcher's
   0-message bug.
3. **Board** (`GET /catalysts/promo-circuit`, 10-min Mongo cache) — tags
   from the last 14 days grouped by ticker, joined with Massive daily bars
   since the first tag and EDGAR flags. Reads Mongo only; StockTwits is
   never fetched inline. `POST /catalysts/promo-circuit/sweep` = manual run.
4. **Predictions penalty** — `tags_for(tickers)` returns S/A-tier tags from
   the last 7 days (per-account override via `penalty_days`: ShangVXO's is
   **14d**, because his pumps land ~10 *sessions* after the tag — PETZ ran
   session 9, FLYE session 8, and 53% of his measured hits peaked after
   session 5); `predictions._extract_signals` adds `promo_circuit_tagged`
   (−15, **not** a hard veto, and only when `market_cap` is unknown or <
   **$2B** — the exit-liquidity thesis doesn't apply to a liquid name
   tagged in passing) plus a bear-thesis line. B-tier never penalizes.
   Tier is resolved against the **live roster** at read time, never the
   tier stamped at sweep time, so roster edits apply to existing tags
   immediately.

## Decision tables

Status per ticker (pure `classify_status`; price base = the last close
**before** the first session on/after the first tag — a weekend/premarket
tag must not measure the run against the run day's own close, or RAN/DUMPED
become unreachable for exactly the weekend-groomed movers):

| Status  | Condition |
|---------|-----------|
| RAN     | max gain since first tag ≥ **+30%** |
| DUMPED  | RAN and now ≤ **−40%** from the post-tag peak |
| SEEDING | **latest** tag ≤ **7 days** old, hasn't run — *the row that matters* (keyed to the latest tag so a campaign kept warm >7d still shows SEEDING the morning it's re-flagged) |
| QUIET   | no fresh tag, never ran |
| UNKNOWN | no daily bars |

EDGAR tells (pure `edgar_flags_from_filings`, off
`evidence._fetch_sec_filings(days=30)`):

| Tell | Forms | Window | Meaning |
|------|-------|--------|---------|
| owner_stake | SC 13D/G (+ /A) | 14 d | the study's one predictive public signal (GPRO) |
| shelf | S-1, S-3, F-1, F-3, 424B*, FWP (never S-8) | 30 d | dilution plumbing — exit-liquidity tell |

## Frontend

`PromoCircuit.tsx` — 🎪 tab on `/catalysts`. SEEDING table first, then
RAN/DUMPED ("how the last campaigns ended"), roster with evidence lines,
sweep freshness, method note rendered. Account chips carry the sample post
in the tooltip. Prediction cards need no changes — the penalty arrives
through the generic signal stack.

## Limits (stated on the board too)

- StockTwits-only. The study could not read Reddit directly (blocked +
  archive stale) and X at all; a group can groom elsewhere and stay
  invisible here until the tag hits StockTwits.
- Accounts get renamed/banned; roster handles are exact strings. A failed
  fetch shows in `sweep.accounts_failed` on the board.
- Selection: the roster is the accounts we CAUGHT once (2026-09-01). It will
  grow; absence of a tag is weak evidence of absence.
- Massive daily aggs may lack brand-new listings → status UNKNOWN, never a
  guess.

## Tests

`backend/tests/test_promo_circuit.py` — roster shape, tag extraction
(high-water mark, multi-symbol posts, excluded symbols, bad timestamps),
price-action math, full status decision table incl. the RAN boundary, EDGAR
windows (amendments count, S-8 excluded), predictions penalty wiring incl.
negatives (no signal / empty handles → no penalty; not a hard veto),
offline behavior, crontab + API source guards.
`frontend/src/components/PromoCircuit.test.tsx` — SEEDING render, table
split, EDGAR chips, no-flag dash, empty board + roster, HTTP failure.

## 2026-09-02 pm — the board reads live

Ajay: *"Is this page real time? I do not see realtime update… show me when it
was tagged with a date."*

- **Sweep every 10 min** on weekdays (was 30): a fresh tag reaches the board
  within 10 minutes.
- **Tag stamps:** every row shows *First tag* and *Last tag* as an ET
  date/time ("Sep 1 · 3:20p ET") next to the day count; rows carry
  `first_tagged_at` / `last_tagged_at`.
- **Live cells:** the one live fetch that feeds the ⚡ table (30 s while the
  tape is open) also feeds a *Today* column (live % vs prior close, PRE/AH
  badge) and a **live *Since tag*** (`pct_since_tag_live` = last print vs the
  board's own pre-tag base, `base_close`) on every SEEDING / RAN / DUMPED row —
  marked with a green dot; the daily-close read stays in the tooltip and is the
  fallback when nothing has printed.
- Status (SEEDING → RAN → DUMPED) is still classified on **daily closes** by
  the sweep, so a name that "blew up" intraday shows the move live but flips
  status at the next sweep.
