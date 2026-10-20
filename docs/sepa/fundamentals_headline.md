# Company Net-Worth / Shareholders'-Equity Headline — Spec (2026-06-01)

**Why this doc exists.** The "current net worth + shareholders' equity" figures
have silently vanished from the UI **three times**, always via the same trap: a
schema-versioned analysis cache serving blobs that predate the `headline` field
after a rebase dropped (or failed to bump) something. This doc pins the data
path, the cache discipline, and the contract so it stops happening.

- **Contract:** `backend/tests/test_sepa_contracts.py` →
  `test_fundamental_headline_keys_locked`,
  `test_analysis_schema_version_bumped_for_headline`,
  `test_card_enrichment_surfaces_headline` (run in `make contracts`).

---

## 1. What the figures are

| UI label | Field | Meaning | Source (`yfinance .info`) |
|---|---|---|---|
| **Current net worth** | `market_cap` | what the market pays for the whole company | `marketCap` |
| **Shareholders' equity** | `shareholder_equity` | book value = assets − liabilities | the FILED balance sheet (`sepa.massive_fundamentals`, 2026-10-20); `bookValue × sharesOutstanding` only as a plausible fallback |
| TTM revenue | `revenue_ttm` | trailing-12-month revenue | `totalRevenue` |
| Enterprise value | `enterprise_value` | mkt cap + debt − cash | `enterpriseValue` |
| (also) book value / share | `book_value_per_share` | per-share equity | `bookValue` |

## 2. The data path (and where it breaks)

```
yfinance .info
   │
   ▼
sepa.stock_analysis.fundamental_panel(symbol)   ← builds the "headline" dict
   │
   ▼
sepa.stock_analysis.analysis_for(symbol)        ← Mongo cache "stock_analysis_cache"
   │                                              · schema-versioned (SCHEMA_VERSION)
   │                                              · 60-min TTL
   ├──────────────► GET /sepa/analysis/{symbol}
   │                   └► FE CompanyHeadline.tsx  (detail-page strip)
   │                        reads j.fundamental.headline; if missing → hides
   │
   └──────────────► sepa.card_enrichment.enrich(symbol)   ← Mongo cache, 24h TTL
                       └► GET /sepa/card-enrichment/{symbol}
                            └► FE CardEnrichmentChips.tsx  (💵 net worth · 🏛️ equity)
```

**The failure mode (all 3 regressions):** when the `headline` shape changes, the
caches keep serving the OLD shape until invalidated. The FE bails the moment
`headline` is absent (`if (!headline) return null`), so the whole strip / both
chips disappear — looking like a feature deletion when it's really a stale cache.

## 3. The cache discipline — **the rule that prevents this**

> **Whenever you add or change a field under `fundamental.headline` (or any
> `fundamental_panel` output), BUMP `SCHEMA_VERSION` in `stock_analysis.py`.**

`analysis_for` auto-refreshes any cached blob whose `schema_version` ≠ the
current `SCHEMA_VERSION`. Bumping it forces every stale blob to recompute with
the new shape on first request — no waiting out the 60-min (analysis) or 24h
(enrichment) TTL. The headline addition originally shipped **without** the bump,
which is exactly why it stayed broken. `SCHEMA_VERSION` is `5` as of 2026-10-20 (was `4` when this doc was written).

`card_enrichment` has no schema_version of its own, so it carries a guard:
`enrich()`'s cache-hit branch treats a doc with `headline is None` as a miss and
recomputes — so enrichment-cached cards from before the headline also self-heal.

## 4. The two FE consumers

- **Detail page** — `CompanyHeadline.tsx`, mounted in `SepaCandidate.tsx`. Shows
  the 4-figure strip. Reads `GET /sepa/analysis/{symbol}.fundamental.headline`.
- **Scan-list cards** — `CardEnrichmentChips.tsx` (JIT via IntersectionObserver).
  Shows `💵 $X net worth · 🏛️ $Y equity` next to the valuation chip. Reads
  `GET /sepa/card-enrichment/{symbol}.headline`.

Both render nothing when the data is genuinely absent (e.g. an obscure ADR
yfinance has no fundamentals for) — that's intended graceful degradation, NOT
the bug. The bug is when a name that HAS data shows nothing because of cache
staleness.

## 5. Contract guarantees (locked)

- `fundamental_panel` source must contain `"headline"` + the five keys.
- `SCHEMA_VERSION >= 4` (the bump that restored it).
- `card_enrichment._extract_headline` exists and reads market_cap +
  shareholder_equity; `enrich()` payload + cache carry `headline`.

If you intentionally remove the headline, update these tests AND this doc —
don't just delete the field.

## 2026-10-20 — shareholders' equity = the FILED balance sheet first

Ajay, the SXTC card: "Share holders queirty is werong". The header showed **$25.69B** on a $1.2M company. The product
above (Yahoo `bookValue` per share × `sharesOutstanding`) multiplied a stale, pre-reverse-split **$2,480.58** per share
by today's 10,357,498 shares. The 20-F filed 2026-07-01 says **$29,707,422** as of 2026-03-31 (SEC XBRL
`StockholdersEquity`; `sepa.massive_fundamentals.fetch_reports("SXTC", timeframe="annual")` returns the same row).
Yahoo's cash ($28.3M) and debt ($1.1M) matched the filing, so the negative enterprise value was real; only the equity
product was broken. A scan of the 1,348 cached headlines found five such products (equity > 20× market cap and > $0.5B):

| Name | Yahoo product on the card | Filed equity (SEC XBRL = the helper) |
|---|---|---|
| SXTC | $25.69B | $29.7M, 20-F, period ended 2026-03-31, filed 2026-07-01 |
| BRK-B | $735T (the A-share book value per share × the B-share count) | $717.4B parent / $719.7B total, FY2025 — under Massive's dotted `BRK.B` |
| CDT | $4.59B | $103.1M, 10-Q, 2026-06-30 (CDT Equity Inc., CIK 0001896212) |
| NIVF | $2.39B | $26.6M, 2025-12-31 |
| TWG | $1.13B | $27.8M, 20-F, 2025-12-31 |

**The engine now** (`stock_analysis.py`): `filed_equity(symbol)` asks the ONE financials helper for the quarterly and the
annual series (one period each, income spine + balance sheet only, `HELPER_TIMEOUT_SEC` 6 s per call — foreign filers
such as SXTC have no quarterly rows in v1, Berkshire only annual) with `symbols.for_massive` spelling, and keeps the row
with the newest period end that carries `equity_attributable_to_parent` (line "parent", else `equity`, line "total" —
the note says which); on a tie (a derived Q4 row and the FY row end on the same day) the row that names its filing date
wins. It returns one of three shapes: `filing`, `none` (the provider answered: no filings here) or `unavailable`
(the provider did not answer — rate_limited, server_error, …; the second series is not asked). A fund (`is_etf`) never
asks (`skipped`). `pick_equity(filed, derived, market_cap, financial_currency=…)` (PURE) chooses: the filed figure when
there is one — never guarded (SXTC's real equity is 26× its market cap); else Yahoo's product when it is plausible;
else nothing. The guard is MINE and single: `EQUITY_IMPLAUSIBLE_CAP_MULT = 20` — a DERIVED equity above 20× market cap,
or with no positive market cap to judge it against, is refused with words (the five garbage products ran 36× to
670,000×; the critic's probe of a $932M product on a $1.15M cap, 810×, is refused too). The served note names the
case — "No filed balance sheet was found under this ticker", "The filings provider did not answer (rate_limited)",
"Filings are not read for a fund" — so an outage is never reported as a fact about the company. When Yahoo's
`financialCurrency` is not USD (BABA CNY, SONY JPY) the note adds "The company reports in JPY; the figure is as the
filings provider serves it, not converted here" — probed 2026-10-20: the helper serves BABA and SONY in USD (their
20-F convenience translations) and has nothing for TSM, so no local-currency figure surfaced; conversion or a hard
refusal for non-USD filers is HIS CALL. A crash never 500s the panel: it falls back.

**Served keys** on `fundamental.headline` (and through `card_enrichment._extract_headline`): `shareholder_equity`,
`equity_source` ("filing" | "derived" | null), `equity_status` ("filing" | "none" | "unavailable" | "skipped" | null —
what the helper said), `equity_as_of` (the filed period end), `equity_filed`, `equity_period` ("FY 2026" / "Q2 2026"),
`equity_note` (the served sentence every ⓘ prints — the FE types no formula of its own except the fallback when no note
is served). `book_value_per_share` and `shares_outstanding` are still served untouched.

**Surfaces**: `CompanyHeadline.tsx` (the figure, "as of YYYY-MM-DD" under it when filed, "estimated" when derived, the
note on the ⓘ), `StockAnalysisPanel.tsx` (the note on the ⓘ), `CardEnrichmentChips.tsx` (the note on the 🏛️ hover).
**Caches**: `SCHEMA_VERSION` 4 → 5 so every cached v4 product recomputes on its next read; an analysis built while the
provider was down is kept `UNAVAILABLE_TTL_SEC` = 5 min (a per-row `ttl_sec`), not the hour. The 24h
`card_enrichment_cache` recomputes any row cached before the filed-equity keys (`_headline_current`, the
`sell_count_30d` pattern — no manual deletion needed) and never writes an outage build (`_cacheable`). Cost: up to four
Massive v1 calls per uncached analysis build (six when a ticker spans several CIKs), each with a 6 s timeout and the
helper's retries — the route runs the build in a worker thread (`asyncio.to_thread`), never on the event loop.
**Nearby, not touched (HIS CALL):** the valuation score's P/B still comes from Yahoo's `priceToBook`, built on the same
stale `bookValue`, next to an ⓘ that defines P/B as market cap ÷ filed equity.

**Tests**: `backend/tests/test_fundamental_headline_equity_2026_10_20.py` (the SXTC case, the pre-fix product
reproduced as a NEGATIVE, parent-vs-total, newest period across series, negative equity served, dotted spelling,
NEGATIVE provider trouble → plausible fallback, NEGATIVE empty + implausible → refused with words, NEGATIVE crash never
breaks the panel, NEGATIVE no inputs, `pick_equity` boundaries, schema ≥ 5, the chip pass-through);
plus the critic's round: the tie, the outage words and the short-circuit, the micro-cap product under $1B refused, no
market cap refused, the currency hint and its NEGATIVE, the fund skip, `cache_ttl_for`, `_headline_current`,
`_cacheable`); `frontend/src/components/CompanyHeadline.equity.test.tsx`; contracts block "🏛️ shareholders' equity = the FILED balance
sheet first (2026-10-20)". ✨ `sepa-headline-equity-filed-2026-10-20`. UNMEASURED and not advice.
