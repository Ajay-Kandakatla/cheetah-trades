# Order Flow ("Tape") — methodology

**Status: industry-standard techniques, NOT book-cited.** Requested by Ajay
2026-07-06 ("order flow, bookmap, prints, trade flash, big delta and EMAs,
demand and supply and GEX") after seeing the strategies in a WhatsApp group
claiming ~70% accuracy. No source PDF was provided, so per Rule #1 every
definition below is the standard industry one, every threshold is a
**configured house value** (like `supply_demand/price_zones.py`), and the
claimed accuracy is **measured, not assumed** — see the forward ledger.

Module: `backend/orderflow/` · UI: ticker page → **Tape** tab ·
Endpoints: `GET /orderflow/{symbol}`, `POST /orderflow/{symbol}/scan`,
`GET /orderflow/ledger/accuracy`

## Data reality (what our keys can and cannot see)

| Input | Source | Notes |
|---|---|---|
| Raw trade prints | Massive `/v3/trades/{sym}` (Stocks Advanced) | full session 04:00–20:00 ET, paginated 50k/page, cap 24 pages → `truncated` flag |
| 1-min bars | Massive aggs via `daytrading/data.py` | volume profile + intraday EMAs |
| Daily bars | `sepa/prices.py` | trend gate fallback + ledger grading |
| Zones | `supply_demand/price_zones.py` (reused) | swing-cluster supply/demand bands |
| GEX / max pain | `options/opex.py` (reused) | context only, never in the verdict |
| **Level-2 order book** | **NOT AVAILABLE** | Massive sells no stock depth feed → no bookmap. Substitute: volume profile (traded volume can't be spoofed; resting orders can). |
| **NBBO quote stream** | too heavy (5-10× trade count) | → tick-rule classification instead of the quote rule |

## Trade classification — the tick rule

Uptick ⇒ buyer-aggressive (+1), downtick ⇒ seller-aggressive (−1), zero-tick
carries the last direction; leading unchanged prints are unknown (0), excluded
from delta but counted in totals. Literature puts tick-rule agreement with the
full quote rule at **~75–80%** — this error bar is inherited by delta, big
prints, and bursts, and is stated on the page.

## Derived reads (configured house values)

| Read | Rule |
|---|---|
| **Cumulative delta** | Σ(size × side); per-minute series; `late_delta` = last 30 min |
| **Big prints** | notional ≥ max($100k, day's 99.9th-pct notional); top 20 by $ |
| **Trade-flash bursts** | 10s windows with ≥ $250k, ≥ 15 prints, ≥ 75% one-sided; top 10 |
| **Volume profile** | 40 buckets over the session range; POC = heaviest; 70% value area expanding from POC |
| **Intraday EMAs** | EMA9 vs EMA21 on 5-min RTH closes |
| **Daily trend gate** | SEPA scan qualifier or Stage 2; fallback close > SMA50 ∧ close > EMA21 ∧ EMA21 rising 5 bars; **no data ⇒ fail (safe default)** |

## Trade eligibility + date stamps (2026-09-27)

Ajay 2026-09-27, on the ORCL Tape tab: *"Can you add date stamps please to
the tape?"* then *"this is for oracle hoping this info is accurate"*.

**It was not accurate.** No orderflow file read Massive's trade `conditions`
or `correction` fields, so every row counted as a trade with a side. On ORCL
2026-09-25 the single closing cross (1,671,248 @ $137.10, $229.1M, cond 8)
appeared **five times** as a "buy": the cross plus four NYSE *Official Close*
re-sends (cond 15) at 16:04:14, 16:10, 18:30 and 19:00. Each re-send has its
own `id` and `sequence_number`, so only the condition identifies it. The
opening cross (275,822 @ $138.12) appeared twice, and the 16:04:10
"BUY FLASH $483.5M" was the close.

**The rule** (`orderflow/tape.py:print_kind`, first match wins; ids are
Massive's, `GET /v3/reference/conditions?asset_class=stocks`):

| kind | condition / correction | volume & venues | sides, delta, bursts, big-print $ | big-print list |
|---|---|---|---|---|
| `busted` | correction ∈ {1, 7, 8, 10, 11} | out | out | out |
| `summary` | {15 Official Close, 16 Official Open, 38 Corrected Consolidated Close} (`updates_volume = false`) | out | out | out |
| `non_flow` | {2, 5, 7, 10, 13, 20, 21, 22, 29, 32, 33, 52, 53} (`updates_high_low` or `updates_open_close` = false) | in | out | out |
| `auction_open` / `auction_close` / `auction_reopen` | {17, 25} / {8, 19} / {18, 28} | in | out | **listed, side = none** |
| `regular` | everything else, incl. 14 ISO, 41, 9 alone, **12 Form T, 37 odd lot** | in | in | in |

- 12 (Form T) and 37 (odd lot) are flagged by Massive for session and size
  reasons, not a stale price. They are kept as regular flow. That is the
  status quo; dropping them is **his call**.
- Auctions are identified by **condition, not clock**. ORCL's NYSE crosses
  printed at 09:30:14 and 16:04:14, which the old `09:30:00 / 16:00:00` window
  filter missed. That filter (`trade_flash.AUCTION_CROSS_ET`) is kept as a
  backstop.
- Sides (tick rule and quote rule) are computed over the regular prints only,
  so an excluded print never sets the reference tick.
- `last_price` is the last **regular** print.
- The big-print threshold is computed on the regular prints. Auction rows are
  listed when they clear it. They are never added to Big buy $ or Big sell $,
  so the `big_buyers` and `delta` verdict checks read regular flow only.
- Sources: Massive "Understanding Trade Eligibility" (a "no" on any one
  condition takes precedence), the Massive glossary for correction codes, and
  the Massive trades docs for `sip_timestamp` vs `participant_timestamp`.
- Pinned in `backend/tests/test_tape_conditions_2026_09_27.py` against a
  checked-in copy of the reference
  (`tests/fixtures/massive_sale_conditions_2026_09_27.json`). A real-print
  fixture (`tests/fixtures/orcl_tape_2026_09_25.json`) shows the five close
  rows collapsing to one side-less `auction_close` row.

**Date stamps.** Every big print, burst and dark block now carries `date_et`
next to its time. The page serves the last session's snapshot on later days,
so without a date Friday's prints showed on Sunday as a bare `16:04:14`.

- The stamp is the **SIP time**: the time the tape shows the print, and what
  the fetch window, NBBO merge and resample all use.
- Massive's `participant_timestamp` (execution time) rides along as
  `exec_date_et` / `exec_time_et`. The page shows it only when the
  **execution date differs** from the tape date, e.g. a Form T print
  executed in the prior evening and reported at 04:00. No time threshold is
  applied; whether to show smaller gaps is his call.

**What the page now says.** `tape.excluded` counts every held-out print, and
`tape.excluded.note` is the one-line sentence the page renders under the
big-print tiles. The sentence is served from the backend, not written in the
frontend.

**ORCL 2026-09-25, before → after.** Tape audit 2026-09-27: full session,
real NBBO. Re-run with
`backend/scripts/tape_eligibility_before_after_2026_09_27.py ORCL --date
2026-09-25` in a throwaway container (read-only Massive GETs, no engine, no
Mongo writes; `--raw` + `--offline` replay a saved dump with the tick rule).
"Before" is the same frame with the `kind` column dropped, which
`analyze_tape` reads as every print a trade. The other three verdict checks
are held at the live snapshot's reads (trend FAIL, EMA FAIL, zone PASS).

| | before | after |
|---|---|---|
| session delta | +9,710,852 (+31.7%) | −937,106 (−4.8%) |
| Big buy $ / sell $ | $1,563.8M / $118.3M | $110.7M / $119.7M |
| `big_buyers` / `delta` checks | PASS / PASS | FAIL / FAIL |
| checks passed | 3/5 | 1/5 (verdict AVOID either way, trend gate) |
| tape total shares vs official daily volume | +29.4% (30,626,585 vs 23,671,011) | −0.02% (23,665,321; busted + summary out) |

**Fix round 2026-09-27.**

- **Old snapshots read stale.** A stored snapshot whose `tape` has no
  `excluded` key was computed before this rule (every print a buy or a sell).
  `engine._is_stale` now returns true for it whatever its date or age, so the
  page shows the rescan hint instead of serving ORCL's five BUY rows for one
  cross as fresh.
- **Retail % of volume.** Retail prints and their sign come from the regular
  prints; the percent now divides by the session's real volume (busted +
  summary out, the venue split's base), not the regular prints alone. ORCL
  09-25: 2,393,580 retail shares were 12.3% of regular prints, 10.1% of real
  volume. `retail.identify(..., total_volume=)`; every other caller (Back in
  Demand, the retail scripts) keeps its old divisor.
- **Ledger tag.** Each ledger observation now carries `method`:
  `eligibility_2026_09_27` for a verdict computed under this rule,
  `all_prints` for an old snapshot (`history.tape_method`). `checks_passed`
  means different things on each side of that line (ORCL 09-25: 3/5 → 1/5).
  `GET /orderflow/ledger/accuracy` does not split by it yet; whether to is
  **his call**.

**Trade Flash push (`trade_flash`).** `fetch_recent_trades` applies the same
rule (`regular_only`) before sides and bursts. What changed:

- It no longer fires on auction crosses that print off the bell, or on
  summary, average-price, contingent, derivatively-priced or busted prints.
- A window that was under 75% one-sided only because a non-flow print sat on
  the other side can now qualify.
- No threshold moved.

## The verdict table (fixed — no other rule may decide)

```
AVOID  if trend_daily fails
AVOID  if zone == caution AND delta fails
BUY    if trend_daily ∧ ema_intraday ∧ delta ∧ (big_buyers ∨ zone favorable)
       ∧ zone != caution
WAIT   otherwise
BUY on < 500 prints ⇒ WAIT (thin-tape gate)
Before 09:45 ET the PRIOR session is scanned (premarket tape is noise).
```

- `delta` passes when session delta > 0 **and** last-30-min delta ≥ 0.
- `big_buyers` passes when big-print buy $ ≥ 1.25× sell $ (≥ 1 big buy print).
- `zone` favorable/neutral/caution comes from the price-zones `entry_read`.
- **GEX is context only** — pin/amplify + max pain shown, never counted
  (single-name gamma sign can invert; see `opex_methodology.md`).

## Forward accuracy ledger (`orderflow/history.py`)

Every computed snapshot records one observation per (symbol, ET date,
verdict) — all three verdicts, so BUY has a control group. Cron
(17:10 ET weekdays) grades against daily closes: `fwd_1d` at T+1, `fwd_5d`
backfilled at T+5; hit = close in the verdict's direction (BUY up, AVOID
down; WAIT tracked, not scored). Entry = last tape price at scan time.
Gross close-to-close, no costs, never pruned. `GET /orderflow/ledger/accuracy`
reports per-verdict hit rates with n — **read the n before the %**.

## Honesty caveats (also shown in the UI)

1. Tick rule ≈ 75–80% of the quote rule — delta is an estimate.
2. No Level-2 ⇒ no bookmap; the volume profile shows where volume *traded*,
   not where orders *rest*.
3. Order flow is intraday-noisy; the daily SEPA gate exists precisely so this
   page can never fight the main system.
4. The WhatsApp 70% is unverified until OUR ledger shows it. Decision-support,
   not advice.
