# TradingView Charting Library — custom CANSLIM charting

**Goal (Ajay, for Ravi, 2026-06-04):** an editable, TradingView-grade chart *inside
Pounce* that can carry **custom indicators** (Extended CANSLIM and the SEPA
signals). The free TradingView **embed can't do this** — it's anonymous and blocks
custom Pine. The **licensed Charting Library** can: it's self-hosted, reads from
our own datafeed, and lets us define custom studies in JavaScript.

---

## ⛔ Step 1 — the license (only Ajay can do this)

The Charting Library is free but gated behind a license. **I can't accept a license
or grant on your behalf** (accepting terms / OAuth grants is yours to authorize),
and the files aren't downloadable without it.

1. Apply: <https://www.tradingview.com/advanced-charts/> → "Get the library".
2. Accept the license and link the **GitHub account** that should get access.
3. TradingView grants access to the private repo **`tradingview/charting_library`**
   (approval can take a few days).
4. From that repo, copy the contents of `charting_library/` into:
   ```
   frontend/public/charting_library/
   ```
   (git-ignored on purpose — it's TradingView's licensed code, not ours.)

That's the whole blocker. Everything below is already built and waiting for it.

## ✅ Step 2 — the datafeed (done)

`backend/tv_datafeed.py` + `/tv/udf/*` endpoints in `main.py` serve TradingView's
**UDF protocol** from our price cache (`sepa.prices`), so the chart uses the same
daily OHLCV the scanner does. Tested in `backend/tests/test_tv_datafeed.py`.

| Endpoint | Purpose |
|---|---|
| `GET /tv/udf/config` | capabilities (resolutions 1D/1W/1M, search, time) |
| `GET /tv/udf/time` | server time |
| `GET /tv/udf/symbols?symbol=` | resolve one symbol (pricescale 100, US session) |
| `GET /tv/udf/search?query=` | symbol search over the latest-scan universe |
| `GET /tv/udf/history?symbol=&resolution=&from=&to=&countback=` | OHLCV bars |

Daily is native; weekly/monthly are resampled. Intraday stays on the native
"● Live" chart (genuinely real-time).

## ✅ Step 3 — the front-end scaffold (done, dormant)

- `frontend/src/lib/tvDatafeed.ts` — datafeed adapter implementing the library's
  Datafeed API against `/tv/udf/*`.
- `frontend/src/components/TradingViewAdvancedChart.tsx` — loads
  `/charting_library/charting_library.js`, instantiates the widget with our
  datafeed, and shows a tidy placeholder until the files exist.

These compile now and light up automatically once Step 1's files are in place.

## ▶ Step 4 — remaining (after the license lands)

1. **Wire the toggle.** Add an "Advanced (TV)" option to the chart-tab source
   toggle in `pages/SepaCandidate.tsx`, rendering `<TradingViewAdvancedChart
   symbol={symbol} tvSymbol={tvSymbolFor(symbol, data?.profile?.exchange)} />`.
2. **Custom CANSLIM studies.** Implement via the widget's
   `custom_indicators_getter` (JavaScript studies, NOT Pine):
   - **MA ribbon** 10/20/50/100/200 — Minervini Trend Template (book p.79).
   - **Pocket pivots** — O'Neil low-risk re-entry (already computed in
     `portfolio/diagnosis.py::volume_factors`).
   - **Distribution / follow-through days** — Minervini pp.71-72, 76.
   - **RS line** vs S&P.
   Reuse the SEPA backend numbers (expose them on a small `/tv/studies/{symbol}`
   endpoint) rather than recomputing — and ground every threshold in the books
   per Rule #1 / Rule #4 (contracts + cites), exactly like the scanner.
3. **Live last candle.** Fill `subscribeBars` in `tvDatafeed.ts` from the existing
   SSE last-price stream so the current candle ticks live.

## Why not the embed (recap)

The `s.tradingview.com/widgetembed/` embed (the "TradingView" toggle today) is
anonymous: it can't load a logged-in account's custom Pine, and a paid account
doesn't change that. The licensed library is the supported path for custom,
self-hosted, editable charts — which is why we're here.

## Files

- `backend/tv_datafeed.py`, `backend/tests/test_tv_datafeed.py`
- `main.py` → `/tv/udf/*`
- `frontend/src/lib/tvDatafeed.ts`, `frontend/src/components/TradingViewAdvancedChart.tsx`
- `frontend/public/charting_library/` ← **you install this (Step 1)**; keep it git-ignored.
