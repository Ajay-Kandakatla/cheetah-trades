# Analyst Pulse — estimate revisions, price targets, broker actions

**Code:** `backend/sepa/analyst_pulse.py` · endpoints `GET /sepa/analyst-map?symbols=A,B,C` (cap 100) + `GET /sepa/analyst/{symbol}` · cron weekdays 17:25 ET (`python -m sepa.analyst_pulse refresh`)
**Contracts:** `backend/tests/test_analyst_pulse.py` (behavioral, incl. the live-verified WDC fixture) + the `test_analyst_pulse_constants_locked_and_out_of_score` block in `backend/tests/test_sepa_contracts.py`
**Book:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013) — `backend/sepa/minervini.pdf`. Every quote below re-verified against the PDF on 2026-06-12.
**Status:** built 2026-06-12. **Display + tracking only — NOT in the composite scanner score** (locked: scanner.py must never import analyst_pulse).

---

## Book rules and their page cites

| Rule | Page | Verbatim anchor | Code |
|---|---|---|---|
| ±5% estimate revisions matter | **p.124** | "when estimates are revised upward by 5 percent or more, stocks tend to show better-than-average performance. Conversely, with downward revisions of 5 percent or more, stocks exhibit lower than average performance." | `REVISION_BIG_PCT = 5.0` → `big_up` / `red_flag` |
| FY / next-FY trending higher vs 30 days ago | **p.125** | "I like to see the current fiscal year or the next year's estimates trending higher from 30 days earlier; if both are trending higher, that is even better." | `TREND_WINDOW_DAYS = 30` → `trending_higher: 'both'│'fy'│'next_fy'│None` |
| Large downward revisions = red flag | **p.125** | "large downward estimate revisions are definitely a red flag." | `red_flag` dominates every bullish verdict |
| Raising estimates is the hunt | **p.125** | "Look for companies for which analysts are raising estimates." | up/down revision counts (`rev_counts`) shipped as context |
| Bigger surprise = better; drift lasts months; penny-beats don't count | **p.121-123** | "the bigger the earnings surprise, the better" / only a "meaningful margin" counts | last-report `surprise_pct` JOINED from `sepa.earnings_watch`'s cache (no refetch) on the detail endpoint |
| Tune out analysts on topping/Stage-4 names | **p.86** | "trust what you see, not what you hear. Tune out the analyst" | stage gating below |
| Upgrades on broken stocks are short candidates | **p.89** ("Brokerage House Opinions") | "stocks that are upgraded on the basis of valuation after a large price decline turn out to be good short candidates" | `p89_trap` |
| Expensive-looking ≠ avoid; analysts underestimate winners | **p.41** / **p.44** | "what looks expensive or too high may turn out to be the next superperformance stock" / "the really great companies are almost always going to appear expensive" / section "High Growth Baffles the Analysts" | the FRAMING for price targets — see below |

## The 5%-window ambiguity (stated honestly)

The p.124 study quote gives a **threshold (5%) but no lookback window**. We do
not invent one: the module computes **both** a 30-day and a 90-day revision
percent per period and keys the `big_up` / `red_flag` badges off the **30-day
window** — the only window the book itself names (p.125's "trending higher
from 30 days earlier"). The 90-day number ships as separate context
(`big_up_90d`, `fy_rev_90d`, `next_fy_rev_90d`) and is never folded into the
30d badge. `red_flag` is likewise 30d-keyed; the 90d fields are displayed so
a slow bleed is still visible.

## Signed-EPS convention

EPS estimates can be negative, and a naive `(cur/base − 1)` flips the sign of
the revision: a loss estimate narrowing from **−1.00 to −0.50 is an UPWARD
revision**, but naive math calls it −50%. We compute the percent on the
**delta over the absolute base**:

```
rev_pct = (current − base) / abs(base) × 100      (None when base is 0/missing)
```

so −1.00 → −0.50 reads **+50%**, and −0.50 → −1.00 reads −100%. This is an
implementation convention (the book does no negative-EPS arithmetic), locked
in both test files.

## Price targets are DATA, not Minervini methodology

`implied_upside_pct` (= mean analyst target vs live price) appears nowhere in
the book as a buy/sell input. Ch.4 (p.41, p.44 "High Growth Baffles the
Analysts") argues the opposite of target-following: analysts systematically
underestimate superperformance stocks, and the great ones "are almost always
going to appear expensive." We surface the implied upside **as data with that
Ch.4 caveat attached**; the UI must not render it as a book signal, and it
carries zero weight anywhere.

## Stage gating (p.86 / p.89)

The bullish read of revisions, targets, and upgrades applies **only to names
in a confirmed uptrend** — i.e. the latest scan's `qualifier` (Trend Template
p.79 + liquid). The context plumbing:

- scan `qualifier == true` → `in_uptrend = True` → `context: 'uptrend'`
- in the scan but not a qualifier → `False` → `context: 'broken'` — any
  upgrade or target raise in the last 90d sets **`p89_trap`** (verdict
  `p89_trap`, rendered amber/red, never bullish). Even **without** broker
  actions, a broken name **never gets a bullish verdict**: bullish estimate
  data (`big_up` / `trending_higher`) still ships as raw fields, but the
  verdict falls to `neutral` (p.86: "trust what you see, not what you hear.
  Tune out the analyst").
- not in the scan → `None` → `context: 'unknown'`, trap **never** fires
  (Rule #1: no invented verdicts without trend context); the bullish
  revision read itself still applies (only `'broken'` gates it).

Verdict precedence: `red_flag` > `p89_trap` > `revisions_up_big` >
`trending_higher` > `neutral`. A red flag beats the trap; both beat every
bullish read; bullish verdicts additionally require `context != 'broken'`.

## Engine parameters (NOT book numbers)

| Param | Value | Why |
|---|---|---|
| `ACTIONS_WINDOW_DAYS` | 90 | broker-action lookback — the book gives no window; 90d keeps the feed recent |
| cache staleness | 18 h | analyst data moves daily at most; one cron cycle + stale-kick covers it |
| fetch pacing | 0.4 s/symbol | polite to Yahoo (yfinance is unofficial) |
| map cap | 100 symbols/request | payload sanity on the bulk endpoint |

## Universe, storage, cadence

- **Universe:** latest scan **qualifiers + buyables** + portfolio holdings +
  watchlist tickers (dedup) — the decision universe, not all ~6k names.
- **Store:** Mongo `analyst_pulse`, one doc per symbol (`_id` = ticker),
  upserted whole. Source: yfinance `analyst_price_targets`, `eps_trend`,
  `eps_revisions`, `upgrades_downgrades` — every property individually
  guarded (thin-coverage names throw per property; missing pieces → None).
- **Cron:** weekdays **17:25 ET**, after the 17:20 pattern resolver and
  before the 17:35 giants refresh. `--force` refetches everything.
- **Serve:** `get_map` joins `read()` against cached docs at request time
  with ONE `bulk_live_prices` call + the cached scan's qualifier context;
  `get_detail` adds the full doc, the `earnings_calendar` last-report
  surprise join (p.121), and a stale-kick (>18h → background refresh,
  stale data returned immediately).

## NOT in the composite score

Analyst Pulse is **display + tracking only**. It adds no points, gates no
candidate, and never touches `is_candidate` / `is_buyable` / `score`. The
contract test asserts `sepa/scanner.py` does not import `analyst_pulse`.
Wiring it into the score would be a methodology change (Rule #4): new
behavioral tests, this doc updated with page cites, and Ajay's sign-off.

## Honesty notes

- yfinance analyst data is unofficial Yahoo Finance scraping — coverage is
  thin on small caps and fields go missing without notice; `error` per doc
  records which properties failed.
- Estimate revisions are an **earnings-quality confirmation layer** (Ch.7),
  not a timing tool — the chart and the Trend Template still decide.
- Not advice.
