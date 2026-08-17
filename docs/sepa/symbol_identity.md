# Symbol identity — renames, class shares, and the SATS bug

**The app told Ajay a stock was dead while it traded at $91.89.**

2026-08-16, EchoStar's detail page:

> ⚠️ **SATS looks delisted or acquired.** No recent price data — this stock
> looks delisted or acquired, so live charts won't load.

SATS closed at **$91.89** that week. The sentence was wrong, and it had been
wrong about a second stock for **576 days**.

Code: `backend/sepa/symbols.py`, `backend/sepa/prices.py` (`_fetch`,
`splice_history`), `backend/observability/symbol_liveness.py`.
Tests: `backend/tests/test_symbols.py` (36),
`backend/tests/test_symbol_liveness.py` (18),
`frontend/src/components/DelistedBanner.test.tsx` (8).

---

## What actually happened

Two independent defects, both of which turn a live company into a dead one.

### 1. Ticker renames

EchoStar renamed **SATS → ECHO** effective 2026-06-24. Our price series for
SATS ends 2026-06-23 and never resumes. `is_stale()` sees six-plus missed
sessions and returns True — **correctly, on the data it was given**. The UI then
converted "we have no bars" into "this company was acquired", which is a
different and unverified claim.

Measured 2026-08-16 across the full 1,631-name universe, six symbols had stopped
printing. Three of them were **not** dead:

| symbol | our data stops | truth |
|---|---|---|
| `SATS` | 2026-06-23 | **alive as ECHO**, $91.89 — rename |
| `SQ` | 2025-01-17 | **alive as XYZ**, $82.88 — Block renamed, **576 days stale** |
| `CWEN-A` | — | **alive**, spelling bug (below) |
| `SMAR` | 2025-01-21 | genuinely delisted (taken private) |
| `DOOO` | 2025-12-05 | genuinely gone from US listings |
| `CFLT` | 2026-03-16 | genuinely acquired |

`SQ` is the one that matters. Block renamed in **January 2025** and nothing
noticed for nineteen months.

### 2. Provider spelling for class shares

Our canonical spelling is the S&P/Wikipedia one — a dash before the share class.
Massive uses a dot. Measured the same day:

```
BRK-B  → None       BRK.B  → 250 bars
BF-B   → None       BF.B   → 250 bars
MOG-A  → None       MOG.A  → 250 bars
CWEN-A → None       CWEN.A → 177 bars
```

Massive returns **nothing** for every dash form. Three of those four worked
anyway — because `_fetch` silently falls through to yfinance, so `BRK-B`,
`BF-B` and `MOG-A` were being served by a **different provider with a different
adjustment convention inside the same scan**, and nobody knew. `CWEN-A` fails on
both spellings at both providers, so it vanished entirely.

---

## The fix

### Renames are curated, never inferred

```python
RENAMES = {
    "SATS": ("ECHO", "2026-06-24", "SATS last bar 2026-06-23 close 103.915; "
                                   "ECHO first bar 2026-06-24 open 101.16..."),
    "SQ":   ("XYZ",  "2025-01-21", "SQ last bar 2025-01-17 close 86.96; "
                                   "XYZ first bar 2025-01-21 open 88.06..."),
}
```

It is tempting to detect renames automatically — data stops here, some other
symbol starts there at a similar price, join them. **Do not.** A wrong guess
splices another company's price history into a chart Ajay sizes real positions
against, and it does so silently. A missing entry costs one stale name that the
monitor flags within a week; a wrong entry costs a fabricated chart. Those are
not symmetric.

Every entry carries the boundary bars that were checked.

### The splice, and when it refuses

Massive only carries ~37 bars under `ECHO`. A 200-day moving average needs 200,
so continuity is the whole point, not a nicety. `splice_history()` prepends the
old series and returns **499 continuous bars** for SATS.

It refuses in two cases, returning the short new series instead:

| guard | value | why |
|---|---|---|
| `SPLICE_MAX_JUMP_RATIO` | 1.35 | A rename is a relabelling — the price does not move because of it. A larger jump means a reverse split, a spin-off, or a wrong `RENAMES` entry. |
| `SPLICE_MAX_GAP_DAYS` | 10 | Months of silence between the two series is not a clean relabelling. |

Both real cases pass comfortably: SATS moved **−2.6%** overnight across the
boundary, and SQ→XYZ spans a market holiday (MLK Day) but only one session.

A short history fails SEPA's gates gracefully. A fabricated one does not fail at
all — it just draws a cliff and gets traded.

### Spelling is a pure function per provider

`for_massive("BRK-B") == "BRK.B"`, `for_yahoo("BRK.B") == "BRK-B"`. Only a
**single trailing letter** after the separator counts as a share class, so
`ABC-XY`, `ABC-1` and `BRK-` are left alone rather than rewritten into symbols
that do not exist.

This composes with the existing `_CLASS_SHARE_REMAP` in `universe.py`, which
maps the raw iShares form to ours: `BRKB` → `BRK-B` → `BRK.B`.

### Every yfinance call site, not just the price one

Minutes after the rename fix deployed, the api log said:

```
ERROR HTTP Error 404: No fundamentals data found for symbol: SQ
```

The price path resolved renames. **Thirty-one other call sites across 28 files**
still handed Yahoo the retired ticker, so Block kept its chart and lost its
profile, fundamentals, catalysts, earnings date and analyst ratings — each of
which renders as "this company has no data", the same wrong story the banner
was telling.

`symbols.yf_ticker(sym)` now wraps `yf.Ticker(for_yahoo(resolve(sym)))`, and
every call site goes through it. Index symbols (`^VIX`, `^GSPC`) and unrenamed
tickers pass through untouched, so it is safe to apply blanket.

**`sepa/prices.py` is the one deliberate exception** — its splice has to fetch
the OLD symbol on purpose, and resolving there would silently drop every
pre-rename bar. `test_no_module_calls_yf_Ticker_directly` enforces the rule and
`test_prices_keeps_its_direct_call_on_purpose` stops someone "fixing" the
exception.

Verified: `symbols.yf_ticker("SQ").info` returns **Block, Inc. · Technology ·
10,205 employees**, where the raw symbol 404'd.

### The banner says what we observed

| | |
|---|---|
| before | "SATS looks delisted or acquired." |
| after (unknown) | "No recent price data for SATS. Our price provider has returned no bars since 2026-06-23. That usually means the symbol was delisted, acquired or renamed — but it can also be a data gap, so check before acting on it." |
| after (known rename) | "↪️ SATS now trades as ECHO (since 2026-06-24). Charts follow the new symbol." |

Two different claims were being collapsed into one: *our data stops here* (true,
and all we know) and *this company was bought* (a guess, and it was wrong).

---

## The monitor — why `SQ` sat wrong for 576 days

`backend/observability/symbol_liveness.py`, weekly, Saturdays 07:40.

Every existing check would have called SQ green every single day:

| check | asks | verdict on SQ |
|---|---|---|
| `check_price_cache` | how old is the cache FILE? | ✅ refreshed on schedule |
| `period_freshness` | has quarterly CONTENT rolled? | n/a |
| **`symbol_liveness`** | **when did the newest BAR print?** | ❌ 576 days ago |

The cache was refreshing perfectly. It was storing the same dead bars each time.

Design choices, all deliberate:

* **Reports, never guesses.** It says "these stopped"; a person checks the
  ticker and either adds a `RENAMES` entry with evidence or drops the name.
* **Never pushes.** WARN only, visible on `/health`. The phone keep-set is three
  kinds and this is not one of them.
* **Never fetches.** Cache reads only, so the sweep can never itself hammer the
  provider.
* **A universe-wide outage names no symbols.** If more than 10% *and* at least
  25 symbols look dead, that is the provider or the warm cron, not 1,600
  corporate actions — printing the list would bury the one real rename. The
  absolute floor exists because a fraction alone misfires on small lists: 1 dead
  name out of 3 is 33%, and it is still just a dead ticker.
* **A `RENAMES` entry that goes stale is a *regression*.** Those symbols are
  spliced and must read fresh; if one reappears, the splice broke, which is more
  urgent than an unknown dead ticker and is reported separately.

### After the fix

```
total 1631   fresh 1627   stopped 4   regressed 0
  SMAR    2025-01-21   408 sessions
  DOOO    2025-12-05   180 sessions
  CFLT    2026-03-16   109 sessions
  CWEN-A  2026-04-30    76 sessions
```

SATS and SQ are gone from the list. The remaining four are genuinely dead —
`CWEN-A` was verified across all three sources (Massive stops 2026-04-30, Yahoo
404s, Finnhub returns 0).

---

## Honest limits

* **The rename map is only as current as the last person who looked.** The
  monitor shortens the window from "forever" to "a week", but it cannot close
  it. A rename between Saturday sweeps is still wrong until Saturday.
* **The splice guards can refuse a real rename.** A company that renames *and*
  reverse-splits on the same date trips `SPLICE_MAX_JUMP_RATIO` and gets a short
  history. That is the intended failure, not an oversight — handling it properly
  needs a split factor, which is a different piece of data we do not have here.
* **Four dead names remain in the universe.** `is_stale` already keeps them out
  of the scan, so they cost nothing but a monitor line. Removing them from the
  index rosters is a separate decision.
* **`swrCache` has no age check.** A `stale_data: true` payload cached in
  localStorage survives until the next successful refetch, so the banner can
  outlive the fix by one page load.

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| SATS resolves to the live symbol | `test_the_sats_case_resolves_to_the_live_symbol` |
| SQ resolves (the 576-day case) | `test_the_sq_case_that_was_wrong_for_576_days` |
| Renames are written direct, never chained | `test_no_rename_target_is_itself_a_rename_key` |
| Every entry carries its evidence | `test_rename_of_carries_the_evidence` |
| Class shares are dotted for Massive | `test_class_shares_are_dotted_for_massive` |
| Only a single trailing letter is a class | `test_a_multi_letter_suffix_is_not_a_share_class` |
| The real SATS boundary splices | `test_the_real_sats_boundary_splices` |
| A holiday does not block a clean rename | `test_the_sq_boundary_splices_across_a_market_holiday` |
| A price cliff refuses the splice | `test_a_price_jump_at_the_boundary_refuses_the_splice` |
| The new series wins on shared dates | `test_overlapping_old_bars_are_dropped_not_duplicated` |
| An outage names no symbols | `test_a_universe_wide_outage_names_no_symbols` |
| …but a small list is not an outage | `test_just_under_the_breadth_alarm_still_lists_symbols` |
| A broken splice reads as a regression | `test_a_symbol_already_in_RENAMES_is_flagged_as_a_regression` |
| Counts stay truthful when the listing is capped | `test_the_symbol_list_is_capped_so_the_report_stays_readable` |
| The banner never asserts a corporate action | `DelistedBanner.test.tsx` → "reports missing DATA" |
| No module calls `yf.Ticker` directly again | `test_no_module_calls_yf_Ticker_directly` |
| …except prices.py, on purpose | `test_prices_keeps_its_direct_call_on_purpose` |
| Index symbols survive the blanket helper | `test_yf_ticker_passes_index_symbols_through_untouched` |
