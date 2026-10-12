# Accumulation push scope — his real holdings + watchlist (2026-10-11)

**Bug.** The Sunday 07:00 `accumulation_change` push (13F share flow on his
names) printed sweep `{scanned: 1, compared: 1}`. `_alert_symbols()` read only
the manual holdings store (`portfolio_holdings`, one row: WULX) and the SEPA
file watchlist (empty). The live book is the Plaid -> Fidelity link, and his
watchlist is the Mongo list behind `/watchlist` — neither was read.

**Fix.** `supply_demand/accumulation_changes._alert_symbols()` unions four
sources, each in its own try, with one INFO line of counts per source:

| source | store | reader |
|---|---|---|
| plaid | `portfolio_holdings_cache` | `portfolio.plaid_store.held_tickers(owner)` |
| manual | `portfolio_holdings` | `portfolio.store.list_holdings(owner)` |
| watchlist | `watchlist` (household-wide, no owner key) | `watchlist.store.list_entries()` |
| sepa_watchlist | SEPA watchlist file | `sepa.scanner.load_watchlist()` |

Owner = `HOUSE_OWNER_EMAILS[0]`. No owner: holdings sources skipped, watchlist
kept, WARNING logged. A source that raises (or Plaid's store unreachable)
logs WARNING and reads `=down`; the others still count.

`plaid_store.held_tickers` joins `holdings[].security_id` to
`securities[].ticker_symbol` (a Plaid holding carries no ticker), skips cash
equivalents (SPAXX, FDRXX), reads the cache whatever its age, and returns
`None` only when the store is unreachable.

**Non-tickers.** Anything not ticker-shaped (`^[A-Z]{1,5}([.-][A-Z]{1,2})?$`)
is skipped: `$`-prefixed CSV positions and Fidelity's dotted pseudo-symbols.
Live Plaid cache 2026-10-11 carried `RESTRICTED.STOCK.UNITS`,
`SP.TTL.INTL.IDX.CL.C` and `BTC.LP.IDX.2055.H` **without** a `$`, so a
`$`-only filter would have missed them. `BRK.B` / `MOG-A` are kept.

**Live scope (read-only probe, 2026-10-11).** Plaid 12 rows -> 11 tickers
(2 cash) · manual 1 · watchlist 17 -> 27 names (24 after the non-ticker
filter), up from 1.

**Backlog check (point 6).** Would the first wider sweep push a burst of moves
already recorded? Read-only simulation over the 27 names, against the
dedup collection and stored snapshots: **0 would push.** Every scoped name's
prior-quarter snapshot is dollars-only (banked before 2026-10-06), so overlap
= 0 and nothing is comparable; the 3 existing `accumulation_changes` rows are
legacy dollar rows for names outside the scope. The per-(symbol,
new_quarter) dedup is unchanged and `_notify` sends one consolidated message,
so no dedup seeding was added. First real comparisons arrive at the Q3 13F
roll, against the share-based Q2 snapshots.

Tests: `backend/tests/test_accumulation_alert_scope_2026_10_11.py`.
