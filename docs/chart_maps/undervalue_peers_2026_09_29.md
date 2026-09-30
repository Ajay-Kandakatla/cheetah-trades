# 🏷️ Under Value → vs peers (2026-09-29)

## The ask, verbatim

> "create me another tab where valuations are wrong based on analytics, this is purely driven by wrong valuation of the stocks in the whole universe we have.. What I am looking for is great sales growth, annual review but Market cap and stock price is very low at least 50% low compared to peers."

then

> "Use the same tab actually"

So this is a toggle on the existing 💎 Under Value Chart Maps tab (`/chart-maps?tab=undervalue`), not a new tab.

## Two views, one tab

| | 💎 P/S ÷ growth (default) | 🏷️ vs peers (`?uv=peers`) |
|---|---|---|
| Population | Bonde strong/explosive names, top 120 by growth | every name in the latest scan (`all_results`) |
| Question | is the price tag lagging the growth? | is the company valued at half its peers per dollar of sales, while growing? |
| Revenue | `sepa.rev_ttm` (yfinance `totalRevenue`) | sum of the last 4 adjacent reported quarters (`research.decision_snapshot`) |
| Market cap | Massive shares × price-cache close | `promo_circuit.market_caps_for(..., cap=0)`: stored share count × the scan's close |
| Builder | `board.undervalue_tiles` (**untouched**) | `board.undervalue_peer_tiles` + `chart_maps/undervalue_peers.py` |

The 💎 view is byte-identical. Proof by construction: `undervalue_tiles`, `psg_ratio` and `_uv_band_state` are not edited, and `tests/fixtures/undervalue_psg_golden_2026_09_29.json` was captured on the untouched tree (8d62a4c) **before** the first edit: two payloads plus the SHA-256 of all three functions' source. `test_the_psg_view_is_byte_identical_to_the_pre_toggle_board` asserts both. The default payload gains exactly one key, `undervalue_view` (the served toggle).

## Rules (every constant lives in `chart_maps/undervalue_peers.py`)

One bucket per scan name, in this order:

1. no sector → `no_sector` (not read)
2. no fresh research doc → `no_fundamentals` (not read)
3. `_source == "yfinance"` → `currency_unverified` (not read; see traps)
4. the last `QUARTERS_FOR_TTM` quarters are not all present, or are not adjacent (`qoq._adjacent`) → `no_ttm_revenue` (not read)
5. TTM revenue ≤ 0 → `nonpositive_revenue` (read; never a peer, never passes)
6. no cap → `no_cap` (not read)
7. cap tagged `DERIVED_FLOAT` (a lower bound) → `cap_lower_bound` (not read)
8. otherwise `usable`: P/S = cap ÷ TTM revenue

Then, for each usable name:

9. Peers are the usable names in the same (industry, sector) that ALSO clear `MIN_TTM_REVENUE_USD = $100M` (round 2), with the name itself excluded, when there are at least `MIN_PEERS = 5`. Otherwise the sector's floor-passing names, under the same floor. Otherwise `no_peer_group`.
10. P/S ÷ the peer median (`capital_quality._median`) > `PEER_PS_MAX_FRACTION = 0.50` → `not_cheap`. Exactly 0.50 passes.
11. TTM revenue < `MIN_TTM_REVENUE_USD = $100M` → `under_revenue_floor`.
12. Latest-quarter YoY (`sales.growth_yoy_pct`, headline pair checked by `qoq.yoy_pairs_ok`, year-ago quarter > 0): not read → `q_growth_not_read`; < `MIN_SALES_YOY_Q_PCT = 20` → `q_growth_short`.
13. Trailing year (last 4 quarters vs the 4 before; all 8 adjacent; prior year > 0): not read → `ttm_growth_not_read`; < `MIN_SALES_TTM_GROWTH_PCT = 20` → `ttm_growth_short`.
14. `passed` (and `sector_fallback` when step 9 used the sector).

The order is deepest discount first, with ties broken by symbol. The Sort dropdown, liquidity floor and phase lens work as they do on every tab. The phase lens uses `_uv_band_state`, unchanged.

Card extras (display only; none of them gates):
- **EV/Sales vs the same peers**: from `board_metrics.attach`. The median needs ≥ `MIN_PEERS` peers with a meaningful balance sheet; `n/a` in `NON_OPERATING_SECTORS`.
- **CPA red flags**: the `capital_quality.for_row` definitional FAILs (`net_cash`, `positive_fcf`, `no_dilution`, `positive_roce`). These are sign tests, so no threshold is chosen here. With no `board_metrics` row the card says `CPA: not read`.
- **Next ER**: from `earnings_calendar` (`rotation.hottest._earnings_map`).

UNMEASURED: `MEASURED = False`. No study in this app says a name valued at half its peers does better afterwards. The share price itself is never compared across companies.

## Data sources and as-of

- Revenue is as of the last reported quarter, shown on each card as `TTM rev … · FY2026 Q2`. A research doc older than `research.CACHE_TTL_SEC` is not read.
- Market cap is the stored share count × the scan's close. Each card reads `shares fetched {date}` (the shares_cache `as_of`, i.e. when the count was FETCHED, not the share-count period) `× close {date}` (the ET date of the scan's own `generated_at`). `cap_basis` is `stored` when only the provider's stored `market_cap` existed.
- The memo is keyed by (scan generation = scan file mtime, ET date) — the mtime is a memo key only, never a date on a card and lives for `MEMO_TTL_SEC` = 30 min. That TTL is cache freshness, not a rule.

## Live read (2026-09-29, ~00:30 ET 09-30, read-only probe in the api container, Mongo writes blocked)

Re-run the probe to update these numbers; the served header line on the tab is the same funnel.

| Read | Count |
|---|---|
| scan names | 1,829 |
| not read: no sector / no fundamentals / currency unverified / no 4 clean quarters / no cap / cap lower bound | 20 / 4 / 178 / 251 / 0 / 20 (473) |
| TTM revenue ≤ 0 | 25 |
| usable P/S | 1,331 |
| not cheap | 1,040 |
| under $100M | 0 |
| Q growth not read / short | 3 / 236 |
| trailing year not read / short | 20 / 14 |
| **passed** | **18** (6 via sector; EV compared 9 of 18; CPA not read 7) |

Top of the list: SMCI (0.7x vs Computer Hardware 31.7x, 98% below), AVT, ARW, HRMY, CRBG, BG, HPE, HHH, TPG, TARS, LPLA, WDC, VCEL, OMC, ALNY, ARQT, HALO, SHLS. No TSM / BABA / SONY-class ADR appears.

Timing: the view's own read took 0.43 s cold and under 1 ms warm. Through the full `board()` path it took 2.3 s cold and 0.7 s warm.

Default view vs `origin/main`, same process and same moment, `limit=80`: 80 tiles. There were no top-level key differences and no tile key differences once `undervalue_view` was removed. The source hashes of the three old functions are equal.

## Traps

- **ADR currency.** yfinance-sourced foreign filers report revenue in local currency against a USD cap: TSM (TWD), BABA/JD/NIO (CNY), SONY (JPY) show P/S of 0.01–0.5. These names are excluded as `currency_unverified`. The existing 💎 view has the same exposure through `rev_ttm` and is not touched here (HIS CALL 7).
- **Peer labels mix story stocks.** SMCI's "Computer Hardware" group includes quantum names at 72–488x sales. The card shows the group, n and the median.
- **Sector fallback compares business models.** Distributors, agri and agencies read "cheap" against a sector median. The ⚖️ chip says so.
- **Massive omits the FY-Q4 quarter.** The trailing-year leg is unreadable for about half the universe. Those names are counted, never estimated.
- **Lower-bound caps** (`derived_float`) would make a name look cheaper, so they are excluded.
- **Share-count age** runs up to about 106 days, and dual-class tickers enter the median twice.
- **`board_metrics` is board-scoped**, so EV and CPA are often "not read". A "not read" is never a pass and never a chip.
- **Card ladder.** No badge on this view starts with a PRICE/ENTRY prefix. Only the reused phase badges (`◉ `, `→ `) jump a rung.
- **Direct in-container calls** hand `board()` Query objects. `parse_view` treats anything that is not "peers" as 💎, and `api.py` coerces.

## HIS CALL (built as below until he says otherwise)

1. The 50% bar, `PEER_PS_MAX_FRACTION = 0.50`, inclusive.
2. The peer floor, `MIN_PEERS = 5`, also applied to the sector fallback. The app's other floors are 8 (Hottest) and 20 (sector percentiles).
3. Whether to fall back to the sector at all: 6 of 18 live passes came through it.
4. 20% for the latest quarter AND 20% for the trailing year. The trailing-year leg is unreadable for about half the universe (20 cheap names today).
5. The $100M revenue floor.
6. Keep Financial Services / Real Estate in, with a ⚖️ chip? 5 of 18 live passes are there.
7. Excluding yfinance-sourced fundamentals, and whether to fix the 💎 view's matching ADR exposure.
8. A maximum age for the share count. None is applied today; the date is on each card.
9. Peer medians ignore the liquidity dropdown.
10. Widening the 17:45 `board_metrics` warm to this view's passes. This would change the cron's scope.

## Verification

- `backend/tests/test_undervalue_peers.py` (positives + negatives), `backend/tests/test_chart_maps.py::test_the_psg_view_is_byte_identical_to_the_pre_toggle_board` (golden + source hashes).
- Mutation proofs, each red and then green again: `>` → `>=` on the 50% compare; self-exclusion dropped; one character in `undervalue_tiles`'s note.
- Frontend: `src/lib/undervalueView.test.ts`, `src/components/UndervalueViewNote.test.tsx`, `src/pages/ChartMapsUndervaluePeers.test.tsx`, and the contract "🏷️ Under Value vs peers (2026-09-29)" in `scripts/contracts.mjs`.

## Round 2 (2026-09-29, review fixes)

1. **Close date.** The card's `× close {date}` came from the scan FILE's mtime, which a later rewrite moves (it read 2026-09-30, a session not yet traded). It now comes from the ET date of the scan's own `generated_at`; with no `generated_at` it says `undated`, never the mtime. The mtime stays the memo key. The scan payload carries no last-bar date field, so `generated_at` is the nearest date the scan itself states.
2. **A failed read is not "no name passes".** `build_failure(counts)` flags a build that compared nothing: `no_scan` (no scan rows), `no_sector` (no row carried a sector), `no_fundamentals` (the research read returned nothing — `decision_snapshot` returns `{}` when Mongo is down), `no_usable` (no readable P/S, e.g. the shares-cache read returned nothing). A raised exception carries its type name. Such an entry is never memoised; the served `undervalue_view.error` carries the key and the header says the read failed and why. The empty board prints the same line, never `EMPTY_NOTE`.
3. **Empty board wording.** `EMPTY_NOTE` only when `counts.passed == 0`. When names passed but the board is empty, `hidden_note` names the cause: the phase filter, the liquidity floor, no price history, or chart bars that did not load.
4. **Shares date wording.** `shares fetched {date}` (it is the fetch date of `shares_cache`, not the share-count period).
5. **Peers clear the revenue floor (default change).** Peer medians use only usable names (positive revenue, positive full cap) that also clear `MIN_TTM_REVENUE_USD`; self excluded; the ≥ `MIN_PEERS` rule and the sector fallback apply to that filtered pool. A sub-$100M name is still measured as a candidate (it lands in `under_revenue_floor`). The served note says so.

Live read after round 2 (2026-09-29 ~23:45 ET, read-only probe of the branch module in the api container, Mongo writes blocked; re-run = the served header):

| Read | Count |
|---|---|
| scanned / usable | 1,829 / 1,331 |
| not read: no fundamentals · currency unverified · no four clean quarters · cap lower bound · no sector | 4 · 178 · 251 · 20 · 20 |
| not cheap | 1,064 |
| q growth short / not read · trailing-year short / not read | 221 / 2 · 14 / 18 |
| **passed** | **12** (6 via the sector, EV/Sales compared for 4) |

Passes, deepest discount first (P/S ÷ peer median): SMCI 0.047 · AVT 0.068 · ARW 0.073 · BG 0.206 · CRBG 0.213 · HRMY 0.257 · HPE 0.271 · HHH 0.313 · TPG 0.391 · LPLA 0.452 · OMC 0.454 · SHLS 0.499. First card: `$26.9B · shares fetched 2026-09-22 × close 2026-09-29` (file mtime 2026-09-30 00:01 ET, `generated_at` 2026-09-29 23:27 ET). Outage simulation (`decision_snapshot` → `{}`): error `no_fundamentals`, nothing memoised, header "🏷️ The vs-peers read failed — no fundamentals came back for any of the 1829 scan names …".

Tests: the round-2 block at the end of `backend/tests/test_undervalue_peers.py`. Mutation proofs (each red, then green): peer pool without the floor; close dated from the mtime; `build_failure` bypassed in `read()`; the old `shares {date}` wording; `EMPTY_NOTE` whenever the board is empty.
