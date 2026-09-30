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
- 410, 429, 5xx, timeouts and unreadable bodies are retried on the same cursor (backoff 15 s to 900 s) until sunset + 1 day. 400, 401, 403 and 404 stop the crawl.
- The key comes from `MASSIVE_API_KEY_STOCKS` and never reaches disk; stored URLs are key-stripped.

## Where it runs

Host data directory: `/Users/ajay/clinet-test/data/massive_vx_financials_2026-09-30/`. The crawler copy lives in `_crawler/`.

```bash
docker run -d --name vx-snapshot --restart on-failure:50 -e MASSIVE_API_KEY_STOCKS -e PYTHONUNBUFFERED=1 -v /Users/ajay/clinet-test/data/massive_vx_financials_2026-09-30:/out --entrypoint python cheetah-api:latest /out/_crawler/vx_financials_snapshot.py --out /out
```

## Check it

```bash
docker exec -e MASSIVE_API_KEY_STOCKS vx-snapshot python /out/_crawler/vx_financials_snapshot.py --out /out --verify
```

- `--verify` writes `manifest.json`: page gaps, rows vs state, unique and duplicate rows, null-filing-date rows, CIKs, and counts by filing year and by timeframe.
- `--crosscheck AAPL,MSFT,...` re-reads named tickers from the feed and names any row the snapshot lacks.
