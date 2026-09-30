# Massive vX financials snapshot (2026-09-30)

Ajay 2026-09-30, asked whether to save Massive's old financials feed before it shuts down: "yes please".

## Why

- `/vX/reference/financials` answers `Deprecation: true`, `Sunset: 2026-10-09`, and is already in 410 brownouts. Its successor is the v1 fundamentals (`Link: rel="successor-version"`).
- vX is the only Massive feed that carries each filing's ORIGINAL `filing_date`. The v1 successor stamps restated dates and has no delisted names. A point-in-time backtest of the 🏷️ vs-peers view needs the originals.
- **The app still reads vX live** in `sepa/canslim.py`, `sepa/longterm.py`, `sepa/capital_returns.py` and `sepa/board_metrics.py`. The snapshot does not keep those working after the sunset; they need a v1 migration.

## What

- Script: `backend/scripts/vx_financials_snapshot.py`. Tests: `backend/tests/test_vx_financials_snapshot.py`.
- One unfiltered cursor crawl (`sort=filing_date&order=asc&limit=100`), with no partitions. Rows with a null `filing_date` come first and are kept.
- Each page is written atomically to `pages/NNNNNN.json.gz`, then `state.json` advances. A restart resumes exactly and never re-fetches or skips a page.
- 410, 429, 5xx, timeouts and unreadable bodies are retried on the same cursor (backoff 3 s to 900 s) until sunset + 1 day. The 410s are random per-request brownouts, about 15–30% of calls, not long windows. 400, 401, 403 and 404 stop the crawl.
- The crawl is only done when its last page reaches the feed's newest `filing_date`, probed at the start. A page with no `next_url` before that is a cut-off: the same cursor is asked again.
- **Top-up** (critic review 2026-09-30) catches what one pass cannot see:
  - null-date Q4 rows the feed adds after a 10-K, which sort behind the cursor;
  - filings newer than the last page;
  - rows that tie on the server's cursor key `(filing_date, cik, fiscal_year, fiscal_period)`, which it re-reads by `cik=`.
  It keeps only rows the snapshot lacks, counted per row so true duplicates survive.
- `--follow` crawls, then tops up every 12 h until 6 h before the sunset.
- Keys are hashed to 12 bytes, so about 1M rows index in roughly 150 MB.
- The key comes from `MASSIVE_API_KEY_STOCKS` and never reaches disk; stored URLs are key-stripped.

## Where it runs

Host data directory: `/Users/ajay/clinet-test/data/massive_vx_financials_2026-09-30/`. The crawler copy lives in `_crawler/`.

```bash
docker run -d --name vx-snapshot --restart on-failure:50 -e MASSIVE_API_KEY_STOCKS -e PYTHONUNBUFFERED=1 -v /Users/ajay/clinet-test/data/massive_vx_financials_2026-09-30:/out --entrypoint python cheetah-api:latest /out/_crawler/vx_financials_snapshot.py --out /out --follow
```

## Check it

```bash
docker exec -e MASSIVE_API_KEY_STOCKS vx-snapshot python /out/_crawler/vx_financials_snapshot.py --out /out --verify
```

- `--verify` writes `manifest.json`: page gaps, rows vs state, unique and duplicate rows, null-filing-date rows, CIKs, and counts by filing year and by timeframe.
- `--crosscheck AAPL,MSFT,cik:0000001750` re-reads the named tickers or CIKs and names any row the snapshot lacks. It counts copies, not a set.
- `ok` needs all of: the crawl is done, it reached the newest filing, and there are no page gaps.
