# Bonde pick-line data caches — 2026-09-20

The Bonde board's pick line renders facts about each name (float, market cap,
short interest, earnings surprise, analyst coverage, listing date). **The board
path makes ZERO network calls.** Every one of those facts is a bulk read against
a cache that some other cron already fills, plus one new cache built here.

This page is about the READERS and the caches. The legs, the quotes and their
cites live in `docs/sepa/bonde_pick_list_2026_09_20.md`.

---

## Two short measurements, two caches — do not cross them

`backend/short_interest/client.py` owns two different things, and reading one
as the other produces a confident, plausible, wrong number.

| | short VOLUME | short INTEREST |
|---|---|---|
| what it measures | the fraction of ONE session's tape that printed short | total shares sold short and still open at a FINRA settlement |
| cadence | daily | bi-monthly (mid-month + end-of-month settlements) |
| provider path | Massive `/stocks/v1/short-volume` | Massive `/stocks/v1/short-interest` |
| caches | `short_volume_cache` (time-series), `short_volume_latest` (snapshot) | **`short_interest_latest`** (`SI_COLL`, new 2026-09-20) |
| engine | `short_volume_for()` / `latest_short_pct()` | `short_interest_for()` |
| bulk reader | (none) | `short_interest_map(symbols, db=None)` |

The days-to-cover number on the pick line is a SHORT INTEREST number.
`short_interest_map` reads `SI_COLL` and nothing else, and
`tests/test_short_interest.py::test_NEGATIVE_the_map_never_reads_the_short_VOLUME_cache`
seeds `short_volume_latest` for the symbol and asserts the map is still empty —
so a future edit cannot quietly add the volume cache as a fallback.

### `short_interest_map(symbols, db=None)`

ONE `find({"_id": {"$in": syms}})` on `SI_COLL`. Each value is the stored doc
plus two computed keys:

- `age_days` — calendar days between `settlement_date` and today, or `None`
- `stale` — `age_days > SI_STALE_DAYS`, or `None` when `age_days` is `None`

A symbol with no doc is ABSENT from the map. Absent means "never warmed", not
"no short interest". A doc with `settlement_date: None` is a remembered miss —
the warm asked and the provider had no record.

### `SI_STALE_DAYS = 45` — an APP label, never one of his numbers

Rule #7 is "check the reported PERIOD against the source's cadence, not the
cache age". FINRA settles mid-month and end-of-month and publishes about nine
business days later, so a settlement older than 45 days means two missed
settlements plus the publication lag — the CACHE is behind, not the market.

The label is rendered beside the value. **It never flips a pass or a fail.**
Accepting 45 or setting a different bound is his call (spec §7.15).

**2026-09-20 — one clock on the pick line.** `_age_days` aged the settlement
against the UTC calendar date while every other "today" on the pick line (the
surprise leg's stale label, the IPO leg) reads the LOCAL `date.today()` through
`sepa.bonde_picks._today()`. After 19:00 CT the UTC day is already tomorrow, so
for those five hours a night the short-interest `age_days` was one day high and
the two stale labels on the same row disagreed — a settlement exactly 45 days
old flipped to `stale` in the evening and back in the morning. `_age_days` now
reads `date.today()`. Pinned by `test_the_stale_label_reads_the_same_clock_as_
the_rest_of_the_pick_line` (equality against `bonde_picks._today()`, true at
any hour) and by the source pin `test_NEGATIVE_age_days_never_reaches_for_the_
UTC_clock`, since the wall-clock failure is invisible for 19 hours a day. The
fetch/TTL paths keep `_now_utc()`; only the rendered age label changed.

### Warming it

```bash
docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u -m short_interest.client warm-si > /tmp/warm-si.log 2>&1'
docker exec -i -w /app cheetah-market-app-api-1 python -m short_interest.client show-si
```

| flag | effect |
|---|---|
| (none) | `sepa.bonde.symbols()` — the names the board SHOWS, ≤260 |
| `--all-passers` | every `_bonde_pillar` passer off the latest scan, ~1,051 names |
| `--symbols A,B,C` | an explicit list |
| `--force` | ignore `SI_WARM_TTL_SEC` and refetch |
| `--sleep 0.25` | pause between names (default 0.25 s) |

Cost: `short_interest_for()` is **two Massive calls per name** (the settlement
rows plus the share count). ~199 shown names at 0.25 s ≈ 5 minutes;
`--all-passers` ≈ 35 minutes, so run it detached and off-RTH.

`SI_WARM_TTL_SEC = 24 * 3600` — the series moves twice a month, so a day keeps
the warm cheap and still picks up a new settlement the day after it publishes.
A `None` answer is WRITTEN as `{settlement_date: None}` so the miss is
remembered: without that, every ADR and thin name re-pays two Massive calls on
every run, forever. The warm never raises — one bad name must not take the
other 198 down inside a cron.

### The proposed crontab line — NOT added

The crontab is host-tree-mounted and **a deploy does not ship a crontab
change**. Until this runs, the short-interest leg reads unknown on every row,
and the served `pick_legend.warm_note` says so. Cadence and scope are his call
(spec §7.6 / §7.11). The proposed line, after the 17:45 metrics warm:

```
55 17 * * 1-5 /usr/local/bin/python -m market_hours.gate short_interest.client warm-si
```

---

## The additive fields on existing caches

Three modules gained a field rather than a new engine. One fact, one provider.

| module | new keys | filled by | until then |
|---|---|---|---|
| `sepa/board_metrics.py` `balance_metrics()` | `float_shares` (`.info.floatShares`), `shares_outstanding` (`.info.sharesOutstanding`) | `python -m sepa.board_metrics warm --all`, or the 36 h TTL rolling on the 17:45 weekday cron | key absent → reader reads `None` → unknown |
| `sepa/board_metrics.py` `attach()` | flattens `market_cap`, `float_shares`, `shares_outstanding` onto the row | immediate | — |
| `sepa/analyst_pulse.py` `fetch_one()` | `n_analysts`, `n_analysts_source` | `python -m sepa.analyst_pulse refresh --force`, or the 17:25 weekday cron as docs age past 18 h | key absent → `None` → unknown |

419 `board_metrics` docs and 1,365 `analyst_pulse` docs were written before
2026-09-20 and carry neither key. Every reader treats the absence as UNKNOWN,
never as zero, and the negatives pin exactly that
(`test_NEGATIVE_a_PRE_2026_09_20_doc_shape_flattens_to_None_not_a_KeyError`,
`test_NEGATIVE_a_PRE_2026_09_20_doc_reads_None_not_zero`).

`floatShares` is thinner than `marketCap` — ADRs and thin names omit it.
Falling back to shares outstanding would mint a false "tiny float ✓", so the
absence stays an absence.

### "No analyst coverage" is an inference, not a reading

PROBED live on yfinance 1.2.0: AAPL's `earnings_estimate.numberOfAnalysts`
reads `[27, 21, 39, 40]`; SLNH reads `[1, 1, 1, 1]`; BTCS, which has no
coverage, returns an **empty frame** — no column, no exception.

**Yahoo never prints 0.** The absence of an estimate row is the only evidence
of no coverage, and it is not proof of it. So `fetch_one` stores the reading
and its provenance separately:

| what came back | `n_analysts` | `n_analysts_source` |
|---|---|---|
| empty frame | `0` | `"empty_frame"` |
| a `0q` row with a `numberOfAnalysts` column | the count | `"0q_row"` |
| rows but no `0q` row, or no such column | `None` | `None` |
| `None`, or the property raised | `None` | `None` |

A frame with rows but no `0q` row is UNKNOWN, never zero. Whether an empty
frame should be read as his "no analyst coverage" at all is his call
(spec §7.13); the label exists so the reading can be withdrawn without
touching the stored data.

### `coverage_map`, not `get_map`

`analyst_pulse.get_map()` calls `_bulk_live()` — a batched LIVE price call — to
build its verdict. The Bonde board renders off the last closed scan and must
make no network call, so the board path uses
`coverage_map(symbols) -> {SYM: {n_analysts, n_analysts_source, fetched_at}}`,
ONE projected `$in` read. A test monkeypatches `_bulk_live` to raise and asserts
`coverage_map` still answers.

---

## The other two bulk readers

### `sepa/ipo_age.py` `listing_dates_map(symbols) -> {SYM: "YYYY-MM-DD"}`

ONE `find` on `ipo_dates` with `{"ipo": {"$ne": None}}`. Symbols resolve through
`symbols.resolve` exactly as `_profile_ipo_date` does, and the answer comes back
under both the caller's spelling and the resolved one. Docs with `ipo: None` (a
cached miss) are omitted — absent means unknown, never "not young".

Why a new reader instead of the existing functions: `listing_date()` can fall
through to **Finnhub** on a miss and `age()` **loads price history**. Neither
may run per-symbol on a page render. A test monkeypatches both `requests.get`
and `load_prices` to raise and asserts the map still answers.

**These dates are uncorroborated.** 21.4% of profile dates on this universe
belong to a recycled ticker (`chart_maps/ipo.py:20-27`) — a RECENT date for an
OLD company, i.e. a false "young ✓". `chart_maps/ipo.corroborate()` only reaches
back ~130 days, so it cannot check a ten-year claim. The leg is labelled
`uncorroborated` rather than corroborated; whether it belongs on the chip line
at all is his call (spec §7.14).

### `sepa/earnings_watch.py` `last_report_map(symbols)`

ONE projected `find` on `earnings_calendar` for `last_report`. Returns
`date`, `when`, `eps_actual`, `eps_estimate`, `surprise_pct` **raw**. Docs whose
`last_report` is `None` are omitted; a report that carries no surprise keeps the
key as `None`, so the caller can tell "no report" from "a report with no
surprise figure".

**THE UNIT TRAP:** `last_report.surprise_pct` is a PERCENT. AAL 2026-07-23 reads
`227.58` for a $0.15 print against a $0.05 estimate. `sepa/catalyst.py` carried a
FRACTION on a different path until 2026-09-20 — do not "fix" the calendar's unit
to match it. A pinned test asserts 227.58 comes back as 227.58.

`last_report` is the most recent PAST row that carried a Reported EPS, so it can
be a quarter or two old: 63 of the 885 docs that have a surprise carry a report
older than 110 days. That is a freshness LABEL, computed in ONE place in
`bonde_picks.attach` and never here.
