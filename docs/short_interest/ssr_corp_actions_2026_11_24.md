# ⛔ SSR tag — the session's dividends and splits (`short_interest/ssr_corp.py`)

**2026-11-23.** Ajay, verbatim: *"No shorting at the bid (SEC short-sale restriction) / Can we check or this for other stocks too?"*

Spec rev 2 §3.4a, work package W5 (critique C1(b) and C6). Display only: nothing here gates, sorts, pushes or trades.

## Why

Our computed Rule 201 read compares a session low with the snapshot's prior close, and that prior close is **not adjusted** on an ex-dividend or split day.

- **PXED** (NYSE common) went ex-dividend $2.36 on 2026-11-23. The snapshot read it as prior close 19.66 vs day low 17.39, a false computed tag. NYSE's 11/23 list does not have it. It was the one false tag in 28 on the NYSE side (§1.3).
- A reverse split on T can make the computed read say a false OFF (C6).

The SEC FAQ leaves the prior close to the listing market (Q1.3, Q3.1) and has no question on corporate actions. So we compute **no adjusted close of our own**. A name with a dividend ex-date or a split executed on trigger day T gets no computed answer for T. This module only says which names those are.

## The two reads (per day D, by date, no ticker)

```
GET https://api.massive.com/v3/reference/dividends?ex_dividend_date=D&limit=1000
GET https://api.massive.com/v3/reference/splits?execution_date=D&limit=1000
```

- Client: `sepa.prices._http()`. Key: `massive_keys.stocks_key()`. Timeout 15 s, the house value for this endpoint (`drop10_tab.py:350`).
- Strict, like `chart_maps.drop10_tab.fetch_splits_strict`. A non-200 on **either** read, no key, a transport error, or a body without a list `results` is an **error, never an empty day**.
- Paging: a `next_url` is followed with our key re-attached through `params` (any key already in the URL is stripped first), up to `CA_MAX_PAGES` = 5 pages. If there are still more pages after that, the day reads `error "truncated"`, because a partial day is never read as complete. A `next_url` pointing anywhere other than `https://api.massive.com/` is an error and is never asked (the key never goes to another host).
- The key is never logged and never stored. An exception is recorded by its class name only (`"dividends ConnectionError"`), through `prices._scrub_key`.
- Symbols: `sepa.symbols.for_yahoo(ticker.upper())`, which is the snapshot's own dash spelling (`BRK.B` becomes `BRK-B`). A row with a blank ticker is skipped.

### Measured sizes (the real bodies, captured 2026-11-23 ~22:58 ET; fixtures `backend/tests/fixtures/ssr_corp/`)

| Read | Rows | Names |
|---|---|---|
| dividends, ex-date 11/23 | 198 | 195 (7 currencies) |
| splits, executed 11/23 | 15 | 15 (TOPP 5→1, ITP 40→1, PARA 100→1, …) |
| `actions(11/23)` | — | 209 (NWSZF has both, and split wins) |

Each read is one page, so 2 GETs per read of a day. Stored ≈ 10 KB a day.

## Who calls it

- **The writer** is the ⛔ list worker (`ssr_lists.refresh_due`), as its last job, in its own fenced try: `refresh_due(coll, SL.file_dates(now_et), now_et)`. An outside call never rides the Gajjala pass, and the served read never calls out.
- **The reader** is `ssr.payload` (W1): `load(coll, in_play(now_et))`, `actions(loaded, T)`, `any_due(...)` (which kicks the worker), and `source_view(...)` (one `sources` row).

## Frozen interface (alias `CA`)

| Call | Contract |
|---|---|
| `fetch_day(d, *, http=None)` | never raises; `found` with `dividends [[SYM, cash, currency]]` and `splits [[SYM, from, to]]`, or `error` with a text |
| `refresh_due(coll, days, now_et, *, http=None)` | never raises; ≤ 1 `fetch_day` per due day; state doc written BEFORE the outside call; returns `{ran, results, calls}` |
| `load(coll, days)` | Mongo reads only, never raises; each day's actions decoded once per `rev` (in-process) |
| `any_due(loaded, days, now_et)` | the due rule below |
| `actions(loaded, T)` | `{SYM: "split" \| "dividend"}`, split wins; **None = day T not read** (never `{}` for an unread day); `{}` only for a day read with no rows |
| `source_view(loaded, days, now_et)` | `{key: "corp_actions", exchange: None, ok, status, as_of, n, error, text}` |

Docs (collection handed in, never purged): `corp|<date>` holds `{kind, date, dividends, splits, n_div, n_split, read_at, after_open, rev}`, and `corpstate|<date>` holds `{kind, date, attempt_at, result, error, errors}`.

## Due rule (day D)

1. No good doc → due.
2. A good doc read **before** D's regular-session open (09:30 ET, `daytrading.data.ET_RTH_OPEN`; `after_open` false) → due **once more** at/after the open, to catch late listings.
3. A good doc read at/after the open → **never due again**.
4. Throttle: the last attempt must be older than `CA_RETRY_MIN` = 30 min, or `CA_ERROR_RETRY_MIN` = 5 min while the day's errors in a row < `CA_ERROR_STRIKES` = 2.

So a day costs at most 2 good reads × 2 GETs, and 0 calls once every day handed in has been read after its open.

## Served texts (`source_view`)

The worst day decides the status (failed, then pending, then ok), and the text names the days in that status (M/D):

- `dividends and splits of 11/23 read · 209 names`
- `dividends and splits of 11/20 not read yet` (no read yet, or a single error that is still being retried)
- `dividends and splits of 11/23 could not be read` (errors in a row ≥ `CA_ERROR_STRIKES`, or Mongo unreadable)

No URL, no key and no b-word appears in any served text or error.

## What a dividend voids vs what a split voids (applied in `ssr.py`, §3.6)

| Corporate action on T | Computed ON | Computed OFF | Official row |
|---|---|---|---|
| dividend (ex-date T) | **voided** → `unknown / corp_action` | stands (an adjusted close would only lower the 10% line) | stands |
| split (executed T) | **voided** | **voided**, never a false off | stands (TOPP and ITP split on 11/23 and ARE on NYSE's list) |
| day T not read (`actions` None) | stands, with `corp_checked: false` | stands | stands |

## Limits

- **No adjusted close is ever computed.** A dividend or split name reads unknown until the exchange list speaks.
- A corporate action that Massive lists **late** is caught only by the after-open re-read. One that is listed after that, or never, slips through until both exchange lists are complete, and then the computed tag comes off anyway (C1(a)).
- Refresh is lazy (an open page kicks the worker). With no page open, no day is read and `actions` stays None.
- UNMEASURED beyond the one day above: how often Massive lists an action after 09:30 ET.

## Tests

`backend/tests/test_ssr_corp_2026_11_24.py`: the real bodies, strictness (500 on either read, no key, timeout, malformed body), paging and truncation, the request shape (by date, no `ticker`, limit, timeout), the due rule and throttle, state-before-call, `actions` None vs `{}`, the three served texts, the key never in a log record or a stored doc, never raising on a broken collection, and source guards (no `ssr` / `ssr_lists` import, heavy imports lazy, no adjusted close).
