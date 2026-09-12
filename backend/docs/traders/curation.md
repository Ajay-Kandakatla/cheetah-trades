# Curating the traders' mentions into the scan universe — 2026-09-12

> Ajay: *"Also track their mentions for me.. Martin Luk +969.8% (stocks), May be
> a cron job to check their events daily and add to our list of stocks in case
> they are not in our existing list"*

## Who is tracked

| key | handle | claim | cadence |
|---|---|---|---|
| `gnt` | @GnT_Trades | USIC 2025 #1, **+2,115.1%** ($20k+ Enhanced Growth) | posts most days |
| `martinluk` | @martinlukkt | USIC 2025 #1, **+969%** (Stocks) | **posts rarely — 57 days between posts when wired up** |

Both claims are **cited**, never recalled. Ajay quoted "+969.8%"; Martin's own
bio and TraderLion both say 969%, and the decimal is not resolvable from any
public source — so **the stored figure is 969.0 and the decimal was not
invented**.

That cadence column matters: a *daily* check on Martin will usually find
nothing. That is him, not a broken fetch.

## The gate — and why it is not a loop

The eight names these two accounts mention that were **not** already in `full`:

```
SPCX  HNGE  WOLF  KULR  LAES        ← real US-listed companies
BNB   ETH   XRP                     ← CRYPTO TOKENS
```

**Three of eight were crypto.** A job that added what it was told would have put
BNB and XRP into the universe every SEPA scan, every zone store, every demand
board and every paper lane runs on.

So being mentioned is the **input**, never the test. A name is added because it
**resolves**:

1. plausible US equity ticker (1–5 letters) — rejects `12K`, `1,300`
2. not an index / volatility / crypto ticker (`NEVER_ADD`)
3. not known-delisted; not renamed (points at the successor instead)
4. **≥ 60 bars** of price history
5. **last bar within 10 days** — see below

### The liveness gate, and how it was found

Gate 4 alone is not enough, and production data proved it on the first run:

| ticker | bars | verdict |
|---|---|---|
| `SDIG` | **126** | Stronghold — **acquired by Bitfarms**, stopped printing |
| `GREE` | 7 | effectively dead |
| `BITF` | 390 | **alive** — earlier failure was a false negative |
| `SMLR` | 337 | **alive** — same |

`SDIG` would have sailed through a bars-only check and then sat dead in the
universe forever — the same class as the NUVL / RNA dead tickers already on the
boards. **Quantity is not liveness.** `MAX_STALE_DAYS = 10` absorbs a long
weekend plus a holiday without letting a stopped name through.

The BITF / SMLR false negatives came from validating in a **container with no
`MASSIVE_API_KEY`**, which fell back to Yahoo. Re-checked against the running
api container before either was included. *Validate where the keys are.*

## Where adds live, and why not in `universe.py`

`sepa/universe.py`'s curated list is a **Python literal baked into the image**.
A cron cannot edit it, and the edit would vanish on the next deploy. So adds go
to Mongo (`trader_universe_adds`) and a new universe component unions them in:

```python
"full": ("russell3000", "sp1500", "curated", "themes", "traders")
```

Each row carries **who said it, which post, and when**, so every add is
auditable — and flipping `status` to `rejected` removes it from the next scan
with **no code change**.

Guards:

- **`MAX_ADDS_PER_RUN = 12`.** A parsing regression that suddenly yields a
  hundred "tickers" must not reshape the scan universe overnight. What does not
  fit is **reported**, not dropped, and is picked up next run.
- **Fails closed.** If the universe cannot be read, every mention looks missing
  — so the job stands down rather than adding all of them.
- **Fails empty.** `fetch_trader_adds()` returns `[]` on any error: this sits
  inside `full`, and a Mongo blip must cost a handful of curated names, never
  the 2,677-name universe every scan runs on. `_EXPECTED_COUNTS["traders"]` is
  `(0, 200)` because **zero is the legitimate starting state** and the default
  band starts at 1.
- **The cap is warmed on add.** Being in `full` is necessary, not sufficient: a
  name also needs a KNOWN market cap over `MIN_CAP_USD` in `shares_cache` before
  `zone_store` gives it bands. Without warming, a fresh add reads as covered
  while raising no alert for up to a week.

## Schedule

```
40  7,17  *  *  *   python -m traders.feed refresh      # both accounts
0   8     *  *  *   python -m traders.curate            # validated adds
```

## What an add means

**Adding a name means the app can SEE it.** It does not mean the app likes it,
and **no lane trades off this list**. `GET /traders/curated` shows both the adds
and the rejections — the rejections being the more useful half.
