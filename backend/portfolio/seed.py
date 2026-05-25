"""One-shot seeder for the user's initial portfolio holdings.

Run after deploy:

    docker compose exec api python -m portfolio.seed

Idempotent — re-running just updates shares/cost_basis with the latest
constants below. Share counts are computed at seed time from the
current yfinance price (``shares = current_value / last_price``), so
tomorrow's brief can show live P/L without needing manual share counts.

Edit HOLDINGS to reflect buys/sells, or use POST /portfolio for
incremental edits.
"""
from __future__ import annotations

import sys

from portfolio import quotes, store

USER_EMAIL = "ajaykandakatla@gmail.com"
ACCOUNT    = "Individual - TOD X90778361"

# (ticker, cost_basis_total_$, current_value_at_seed_$, tags)
HOLDINGS = [
    ("MU",   24999.61, 31544.50, ["semis", "memory"]),
    ("WDC",   9999.91, 10871.52, ["storage", "memory"]),
    ("RNG",   9999.96,  9624.69, ["comm", "cloud"]),
    ("AMD",   8122.00,  9103.80, ["semis", "cpu"]),
    ("GFS",   8453.27,  8658.03, ["semis", "foundry"]),
    ("SNDK",  6131.83,  6543.07, ["storage", "memory"]),
    ("DRAM",  4795.00,  5280.00, ["etf", "memory"]),
    ("MKSI",   562.88,   611.07, ["semis", "equipment"]),
]


def main() -> int:
    tickers = [t for t, _, _, _ in HOLDINGS]
    print(f"fetching live quotes for {len(tickers)} tickers…")
    q = quotes.fetch_quotes(tickers)

    failed: list[str] = []
    for t, cost, val, tags in HOLDINGS:
        last = (q.get(t) or {}).get("last")
        if not last:
            print(f"  {t}: SKIPPED — no live quote (yfinance returned nothing)")
            failed.append(t)
            continue
        # shares back-computed from screenshot value + current yfinance price.
        # Small price drift between screenshot capture and now is OK — we
        # keep shares fixed going forward; current_value recomputes live.
        shares = round(val / last, 4)
        r = store.upsert_holding(
            USER_EMAIL, t, shares, cost,
            account=ACCOUNT, tags=tags,
        )
        marker = "✓" if r.get("ok") else "✗"
        print(f"  {marker} {t}: {shares} sh @ ${last:.2f} · cost ${cost:,.2f} · {r}")

    if failed:
        print(f"\n{len(failed)} ticker(s) failed quote lookup: {failed}")
        print("These are not seeded. Possible causes:")
        print("  - yfinance is rate-limited (retry in 60s)")
        print("  - ticker delisted or symbol changed")
        return 1
    print("\nDone. Verify with: GET /portfolio  or  /morning/brief")
    return 0


if __name__ == "__main__":
    sys.exit(main())
