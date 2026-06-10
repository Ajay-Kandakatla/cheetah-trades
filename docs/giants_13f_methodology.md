# Giants 13F flow engine — methodology

Built 2026-06-10 (Ajay: "leaderboard section of where the giants are buying…
a trend with a timeline… for MU it would help to know where the money moved").

## What it is

Full quarterly portfolios of the curated Tier S/A funds (backend
`giants/registry.py`, mirrors `frontend/src/lib/fundTiers.ts`), pulled from
**SEC EDGAR 13F-HR information tables** (free, no key), diffed
quarter-over-quarter, aggregated per ticker, persisted with history.

This is the per-FUND inversion of `supply_demand/whales.py` (yfinance,
per-symbol, top ~15 holders, latest quarter only). Only full portfolios can
answer "the fund sold $14.5B of MU — where did that money GO?"

## Pipeline

1. `giants/edgar.py` — per fund CIK: `data.sec.gov/submissions` → 13F-HR
   accessions (latest filing per period wins, amendments replace) → filing
   directory `index.json` → information-table XML → parse. Filings are
   immutable → parsed holdings cached forever in Mongo `giants_13f_filings`.
2. `giants/cusips.py` — CUSIP→ticker via SEC **Fails-to-Deliver** files
   (primary, ~12.5k CUSIPs per half-month file, 3 files merged) +
   normalized-issuer-name fallback against `company_tickers.json`.
   Live-measured coverage on Capital World Q1-2026: **98.4% by value**;
   misses stay visible by issuer name, never silently dropped.
3. `giants/flows.py` — per-fund consecutive-quarter diffs → per-ticker
   per-quarter aggregate → `giants_flows` Mongo doc: ranked inflow/outflow
   rows for the latest quarter, a per-ticker net-flow timeline across all
   cached quarters, per-quarter top movers, per-fund summaries.
   `symbol_rotation(sym)`: for every fund that moved the symbol, the SAME
   filing's biggest adds/trims — the rotation answer.
4. Refresh: cron 17:35 ET weekdays (`python -m giants.refresh`) + self-heal
   kick on `GET /giants/flows` when the doc is >26h old. Outside filing
   season (mid-Feb/May/Aug/Nov) a run is ~38 submissions checks.

## Conventions (locked by backend/tests/test_giants.py)

- **Move value = Δshares × period-end price of the later quarter**
  (price = value/shares from the filing itself); full exits use the prior
  quarter's price; new positions use the full reported value. Price drift
  with zero share change is NOT a flow. (This intentionally differs from the
  whales modal's `fundDollarsAdded`, which prices at TODAY via yfinance —
  both are stated where shown.)
- 13F values verified live to be **full dollars at period-end** (Capital
  World Q1-2026 MU: 42,054,392 sh, $14.21B ⇒ $337.8 ≈ MU's 2026-03-31 close;
  yfinance shows the same share count priced at today).
- **Options rows (putCall) excluded** from flows; excluded count kept on the
  filing doc. Shorts never appear in 13Fs.
- A fund **counts** as buyer/seller of a name only when its move is ≥ $2M;
  dollar sums include everything. Rotation lists floor at $1M.
- Same-ticker share classes (ADR + ordinary, dual class) are **netted per
  ticker** before display so "AZN +3.6B" and "AZN −3.4B" don't both show.
- **Index giants excluded by design** (Vanguard/BlackRock/State Street/
  Geode): mandate-driven flow, and entity restructurings (the 2026 Vanguard
  LLC shuffle) read as fake "+100% new positions". `style: quant` funds
  (Citadel, Millennium, D.E. Shaw…) are included per the curated tier list
  but tagged, so the UI can caveat their churn.

## Honest limits

- Quarterly, up to **45-day lag** — positioning/rotation, not real-time flow.
- Longs only; no shorts, no swaps, no non-US-listed holdings.
- ~1.6% of portfolio value stays unmapped to tickers (foreign lines, bonds);
  shown by issuer name in `unmapped_big_moves`.
- First-ever build downloads ~6 quarters × 38 funds (15–40 min, background).

## Surfaces

- Leaderboard → **GiantsFlowBoard** (stock-ranked net flows, quarterly trend
  sparkline per row, per-quarter top-mover strip, click → rotation modal).
- **GiantsRotationModal** — also linked from WhalesFlowModal
  ("🧭 Where did the money move? →").
- API: `GET /giants/flows`, `GET /giants/rotation/{symbol}`,
  `GET /giants/refresh/status`, `POST /giants/refresh` (admin).
