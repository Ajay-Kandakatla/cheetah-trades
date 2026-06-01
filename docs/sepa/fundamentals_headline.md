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
| **Shareholders' equity** | `shareholder_equity` | book value = assets − liabilities | `bookValue × sharesOutstanding` |
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
which is exactly why it stayed broken. `SCHEMA_VERSION` is `4` as of this doc.

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
