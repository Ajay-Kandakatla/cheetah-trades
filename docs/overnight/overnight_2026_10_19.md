# 🌙 Overnight session read (Blue Ocean) + one morning push (2026-10-19)

## The ask

Ajay, 2026-10-19 (real money, he acts on pushes), four messages, his spelling kept:

> "Can you do an over night scan for all the stocks they are all growing over night"

> (StockTwits watchlist screenshot) "Here are from stocktwits"

> "These are over night check qqq for example"

> "Massive is what we use probably we don't have the subscription"

**Status: branch `feat/overnight-session-2026-10-19`, not on main. UNMEASURED.** This board says what moved in the
overnight session, never what to buy. No study in this app measures an overnight-session read (no doc, no memory note);
the prior on a new signal is null and no edge is claimed. A large overnight move in a fund that fell the prior session
is a reversal read on the tape, not an entry. Not advice.

Home: Chart Maps ▸ Overnight (`frontend/src/lib/chartMaps.ts` tab `overnight`) gets two subs — **🌙 Overnight session**
(new, default) and **Gappers** (unchanged). Spec: BUILD_SPEC16 + AMENDMENTS16 (A1–A5) in the session scratchpad.

Measured on the branch: _filled by the main session after the branch dry-run_

## Measured tonight (read-only probes)

Probes ran in `cheetah-market-app-cron-1` on Mon 2026-10-19 at 01:03 and ~01:18 ET. The scripts live in the session
scratchpad `gg_overnight/` (`lag_probe.py`, `base_probe.py`, `overnight_probe.py`, `alpaca_overnight_probe.py`,
`overnight_scan.py`, `st_check.py`); none is in the repo and none measures an edge — they establish what the feeds carry.

| Fact | Value | Script |
|---|---|---|
| Cron container env carries Alpaca keys | `ALPACA_KEY_ID` True, `ALPACA_SECRET_KEY` True | lag_probe.py |
| `GET data.alpaca.markets/v2/stocks/snapshots?feed=overnight` | HTTP 200, `X-Ratelimit-Limit 200` | lag_probe.py |
| `latestTrade` age vs now | TSLA 936 s, NVDA 1044 s, SPY 910 s, QQQ 993 s, SOXL 900 s; cond `['@']`, exch `B` | lag_probe.py |
| `latestQuote` age | 0 s on all five (real time) | lag_probe.py |
| `dailyBar.t` | `2026-10-19T00:00:00Z` = the TRADE date (keys o h l c v vw n t) | lag_probe.py, 2nd probe |
| `prevDailyBar` | `t 2026-10-16`, TSLA `c 376.81` = the Fri OVERNIGHT bar, not Fri regular (354.72) | lag_probe.py |
| Alpaca timestamps | 9-digit nanoseconds + `Z` (`2026-10-19T05:02:24.704579971Z`) | 2nd probe |
| Class share on overnight feed | `BRK.B` (dot) answers, dailyBar v 3,024 | 2nd probe |
| Massive snapshot `day.c` | == Massive daily agg close 10-16 (TSLA 354.72, QQQ 709.8, NVDA 214.13) | base_probe.py |
| Massive snapshot `day` keys | `c dv h l o v vw` — **no `t`**; item `updated` = Fri 10-16 20:00:00 ET | base_probe.py |
| `todaysChangePerc` | uses lastTrade incl. after-hours: TSLA −2.754 vs `day.c/prevDay.c` −2.13; QQQ −2.765 vs −2.50; NVDA −1.602 vs −1.427 | lag_probe.py |
| Python | test venv **3.9.6** (`backend/.venv`), prod image 3.11.16 | `--version` |

One pass of `overnight_scan.py` (the brief's probe, this session): 6,267 names after base close ≥ $2 and base $ volume
≥ $1M; 32 Alpaca calls of 200 symbols; 7.2 s; 6,142 priced this session; 750 with overnight $ volume ≥ $25k; the top
gainers were dominated by 2×/3× funds (KORU, AXTX, AAOX, NBIL, SOXL…). Massive carries zero overnight prints
(`overnight_probe.py`) — so "now" cannot come from Massive. `feed=boats` snapshots answer 403 on our plan;
`/v2/stocks/{sym}/trades?feed=boats` works with `end` ≥ 15 min old.

Alpaca's own doc (https://docs.alpaca.markets/us/docs/245-trading): overnight 20:00–04:00 ET, Sunday evening → Friday
morning, the evening before the trade date; follows the NYSE holiday calendar — no session the evening before a full
closure (none the Wednesday before Thanksgiving; it resumes Thursday 20:00); half days run the full eight hours;
indicative trades are delayed 15 minutes and adjusted to fit within the bid-ask spread; quotes are real time. The doc
says the indicative feed is a paid subscription — our plan answered 200 anyway (OPEN O1).

## The engine

Modules (inside the existing `backend/overnight/` package; the old pre-market tracker `movers.py` and
`/overnight/movers` are untouched and never imported by the new modules):

- `backend/overnight/session.py` — the pure session clock. `ET = ZoneInfo("America/New_York")` (pinned equal to
  `supply_demand.zone_edge.ET`), `SESSION_OPEN_ET = dtime(20, 0)`, `SESSION_CLOSE_ET = dtime(4, 0)`; `session_for(now)`
  → `{open, trade_date, base_date, opens_at, closes_at, next_open, reason}`. At or after 20:00 the candidate trade date
  is tomorrow; before 04:00 it is today; 04:00–19:59 is between sessions. Open only when the ONE calendar
  (`market_hours.gate.closed_reason`, passed an aware ET noon of the trade date) says the trade date is a market day;
  `base_date = catalysts.medical.reaction.prev_market_day(trade_date)`.
- `backend/overnight/scan.py` — the engine; the cron container runs it, the api never does.
- `backend/overnight/board.py` — the served payload, Mongo only.
- `backend/overnight/push.py` — the one morning push (ships OFF).
- `backend/overnight/api.py` — gains the route `GET /overnight/session`.

### Base — pinned once per session

The base is the last regular close from the ONE whole-market Massive engine
`sepa.prices.market_snapshot_with_meta(include_otc=False)`, **pinned once per session at its first pass** (collection
`overnight_base`, `_id` = trade date) and never re-pulled: the snapshot resets ~03:30 ET (OPEN O2) and is 5.7 MB a
call. `pin_base` refuses when the snapshot is not HTTP 200, when SPY's `close` or `prev_day_close` is missing or ≤ 0
("Massive snapshot carries no close for SPY — not pinned"), or when no pin exists by `BASE_PIN_LATEST_ET` = 03:30
("base not pinned before the 03:30 ET snapshot reset"). The base date comes from the calendar, never the snapshot row
(the row's `date` falls back to today — the snapshot carries no `day.t`). Prior-session % = `close / prev_day_close`,
never `todaysChangePerc` (it carries after-hours prints — measured above). Alpaca's `dailyBar` / `prevDailyBar` are
overnight-session bars and are never the base.

### Now — the price rule (AMENDMENTS16 A1: live quote mid first)

Alpaca `feed=overnight` snapshots, batches of `ALPACA_BATCH` = 200. Overnight trades are indicative, delayed (~15 min,
measured 900–1,044 s) and already adjusted into the spread; quotes are real time. Per row:

1. **Quote mid** when the quote is good: latestQuote time ≥ the session open AND its age ≤ `QUOTE_FRESH_SEC` = 300
   (MINE) AND 0 < bid < ask AND (ask − bid) / mid ≤ `QUOTE_SPREAD_MAX` = 0.015 (MINE) → `price` = mid, `src` = `"q"`,
   `price_age_sec` = the quote's age, `spread_pct` served.
2. Else the **delayed indicative trade** if it printed this session → `price` = trade, `src` = `"t"`, `price_age_sec` =
   the trade's age.
3. Else the row is dropped (`no_price`); a symbol the feed did not answer is `not_on_feed`.

So on the board the `q` chip marks a quote-mid price (the common case) and `t` marks a delayed indicative print; the
board prints the pass's median trade age (`trade_age_median_sec`). Every trade-based price is called indicative and
delayed, never "live".

Row math: `pct = 100 × (price / base close − 1)`; `prior_pct = 100 × (close / prev_day_close − 1)` when
`prev_day_close > 0`, else None; `prior_dollar_vol = close × volume`. `on_bar` = `dailyBar.t` is the trade date;
`on_volume` = that bar's `v` (0 when the bar is another date); `on_dollar = on_volume × (vw or close or price)`;
`on_trades` = `n` when `on_bar`. Every float through `trading.safety_floor._f` (NaN / inf → None); a row with no `pct` is
dropped. Timestamps are parsed by `scan.parse_ts` (RFC3339, `Z`, up to 9 fraction digits truncated to 6 — py3.9-safe).
Wire symbols go through `symbols.for_massive` (dot form: `BRK-B` → `BRK.B` → served back as `BRK-B`). Alpaca headers
come from env; every logged or stored error string goes through `trading.broker_alpaca._scrub`.

### Leverage tag (served, the FE types no rule)

`scan.fund_flags(name, type_)` parses the fund's own name from the Massive reference list
(`sepa.levered_etf.fetch_reference`), reusing `FUND_TYPES`, `STOCK_TYPES`, `MIN_FACTOR_EXCLUSIVE`, `FACTOR_RE`,
`SHORT_WORDS`, `TOKEN_STRIP` by name:

- A type outside `FUND_TYPES` → not leveraged (a CS named "Ultra Clean Holdings" is never classified); type None →
  unknown (`leveraged None`).
- Leveraged = the largest stated multiple above `MIN_FACTOR_EXCLUSIVE` (1×) — including a multiple glued to a word
  (e.g. "2xLeveraged") — else the words Leveraged / Double / Triple, else stacked exposure stated as
  "\d+% … AND … \d+%", else Ultra / UltraPro / UltraShort. "Ultra" counts **only on ProShares names**.
- Inverse = a negative multiple or a short word **only when a multiple is stated**; without one: Bear, Inverse,
  "ProShares (Ultra / UltraPro) Short", or UltraShort. "Short" is inverse only when it is not a duration word (Term,
  Duration, Maturity, Treasury, Bond…) — so "iShares Short Treasury Bond ETF" and "PIMCO Enhanced Short Maturity" are
  NOT inverse.
- `lev_label` = "3× ETF", "−3× ETF", "UltraPro ETF", "−UltraPro ETF", "inverse ETF", "3× ETN".
- 1× inverse funds (SH, PSQ) ARE tagged "inverse ETF" here, unlike the High Beta tags (HIS CALL #15).
- When the reference list could not be read completely, `leveraged` is None on every row and the served leverage
  sentence says so.

### Floors (each a constant he can change)

| Constant | Value | Mark |
|---|---|---|
| `scan.UNIVERSE_MIN_PRICE` | `MIN_SHARE_PRICE` ($2, house floor, by name from `trading/safety_floor.py`) | house |
| `scan.UNIVERSE_MIN_DOLLAR_VOL` | 1,000,000 — base-session close × volume | MINE |
| `scan.BOARD_MIN_ON_DOLLAR` | 25,000 — rows stored and listed; thinner names counted | MINE |
| `scan.REF_SYMBOLS` | ("SPY", "QQQ", "IWM", "DIA") — served first, in this order, regardless of any floor | — |
| `scan.QUOTE_FRESH_SEC` | 300 — quote age ceiling for the mid | MINE (A1) |
| `scan.QUOTE_SPREAD_MAX` | 0.015 — spread / mid ceiling for the mid | MINE (A1) |
| `scan.PASS_BUDGET_SEC` | 240 — batches past it skipped and counted | MINE |
| `scan.REF_BUDGET_SEC` | 120 — reference pull budget at pin time | MINE |
| `scan.KEEP_SESSIONS` | 2 — reads / base docs older than the 2 newest trade dates pruned | MINE |
| `scan.BASE_PIN_LATEST_ET` | 03:30 — Massive snapshot reset (OPEN O2) | doc |
| `scan.CADENCE_SEC` | 600 — == the crontab `*/10` step (test-pinned) | brief |
| `scan.ALPACA_BATCH` / `ALPACA_TIMEOUT_SEC` / `RETRY_SLEEP_SEC` | 200 / 30 / 3 (one retry on 429, Retry-After capped 10 s) | transport |
| `board.REFRESH_OPEN_SEC` | 300 | MINE |
| `board.REFRESH_CLOSED_SEC` | 1800 — == `chart_maps/drop10_tab.CLOSED_TTL_SEC` by name | Cheetah default |
| `board.STALE_SEC` | `2 × CADENCE_SEC + 300` = 1,500 | MINE |

Universe = base rows passing both floors, and — when the reference list is complete — `type` in `STOCK_TYPES +
FUND_TYPES`; when incomplete, the probe's fallback (drop symbols with `.`, drop 5-letter symbols ending W/U/R).

### Pass order (`scan.read_once`)

1. `session_for(now)`; closed → `{ran: False, reason}` and **no HTTP at all**.
2. `load_base(td) or pin_base(...)`; no base → pass doc `{ok: False, reason}`, nothing stored.
3. `alpaca_snapshots(universe)`; 401/403 → abort "Alpaca overnight feed refused (HTTP 403)", nothing stored; 429 →
   one retry; a batch that fails twice is counted, the others kept, `complete False`.
4. `build_read`.
5. `store` only when `counts.priced > 0` (the ☀️ "refuse a non-live block" rule), then prune to `KEEP_SESSIONS`.
6. Pass doc `_id "latest"` written on every pass that ran, ok or not.

CLI: `python -m overnight.scan [--dry-run] [--json]` (dry-run writes nothing).

## Collections and keys

- **`overnight_base`** — `_id` = trade date: `{trade_date, base_date, pinned_at (ISO ET), snapshot: {http, wall_s, n},
  ref: {complete, calls, types_incomplete}, n_universe, rows: {SYM: {c, v, pc, t, n, lev, ll}}}` (≈ 570 KB).
- **`overnight_reads`** — `_id` = `f"{td}T{HHMM}"` (ET wall clock of the pass): `{trade_date, base_date, as_of (ISO ET),
  as_of_ts (epoch), as_of_et, session_open, complete, reason, counts, refs: [row…], rows: [row… on_dollar ≥
  BOARD_MIN_ON_DOLLAR], secs}`. Index `(trade_date, as_of_ts)`. **Ordered by `as_of_ts`, never `_id`** —
  `"2026-10-19T2350" > "2026-10-19T0100"` lexicographically although 00:01 comes later.
- **`overnight_pass`** — `_id "latest"`: `{as_of, as_of_ts, as_of_et, trade_date, ran, ok, stored_id, reason, counts}`.
- **`overnight_push`** — the push claim, `_id` = trade date: `{claimed_at, state (claimed | pushed | no_target |
  failed), read_id, names, result}`.

**Row keys (served):** `symbol, name, type, base_close, base_date, price, src, price_time (ISO ET), price_time_et
("Mon 0:47 ET"), price_age_sec, spread_pct, pct, on_volume, on_dollar, on_trades, on_bar, prior_pct, prior_dollar_vol,
leveraged, lev_label, ref`. (`prior_*`, not `fri_*`: the base is Friday only on Sunday nights.)

**Counts keys:** `universe, ref_complete, batches, batches_failed, batches_skipped, calls, retries, not_on_feed,
no_price, no_base, priced, on_trade, on_quote, listed, thin, leveraged_tagged, lev_unknown, trade_age_median_sec`.

## The route

`GET /overnight/session?sort=&hide_lev=` in the existing `backend/overnight/api.py` router →
`asyncio.to_thread(board.board_payload, sort=sort, hide_lev=hide_lev)` — Mongo only, in a thread (the async-route freeze
of 2026-10-05); it never calls Alpaca, Massive or `scan.read_once`. Sorts (`board.SORTS`): `gainers` "📈 Top gainers"
(default), `losers` "📉 Top losers", `dollar` "💵 Most $ traded overnight"; ties by symbol; an unknown sort → the
default, echoed in `read.sort`. `hide_lev` drops `leveraged is True` only (None kept, counted in `lev_unknown`); `refs`
are never filtered. `json.dumps(payload, allow_nan=False)` must pass.

**Payload keys:**

```
session:   {open, trade_date, opens_at, closes_at, next_open, line}
read:      null | {trade_date, base_date, as_of, as_of_et, current, complete, reason, counts, refs, rows,
                   sort, hide_leveraged, n_hidden_leveraged, n_listed}
last_pass: null | {as_of, as_of_et, ok, reason, stale, line}
sorts:     [{key, label}]          lines: {counts, price_rule, leveraged, unmeasured, empty, read_old}
refresh_sec: int                   disclaimer: str
```

The served read is the latest stored doc: `current` = its trade date is the open session's; when closed, the most
recent doc is served with `current False` and `lines.read_old`. Every sentence is a `board.py` constant (`LINE_OPEN`,
`LINE_CLOSED`, `LINE_LAST` + its late form, `LINE_READ_OLD`, `LINE_COUNTS`, `LINE_PRICE`, `LINE_LEV`,
`LINE_UNMEASURED`, `LINE_EMPTY`); `$` figures, clock words and minutes are rendered from the constants. The FE
(`frontend/src/components/OvernightSessionBoard.tsx`, `frontend/src/lib/overnightSession.ts`) prints them verbatim and
types no threshold, clock or `$` literal. ⭐ marks names on his in-app watchlist (`useWatchlist`, `GET /watchlist`); the
StockTwits names are not typed anywhere (HIS CALL #10). A row click opens the Support tab (the Gappers precedent).

## Crontab — three lines

`backend/crontab`, appended after the 🚩 Gajjala block:

```
*/10   20-23 *    *    0-4  /usr/local/bin/python -m overnight.scan
*/10   0-3   *    *    1-5  /usr/local/bin/python -m overnight.scan
45     6     *    *    1-5  /usr/local/bin/python -m market_hours.gate overnight.push
```

- The two scan lines are **NOT** wrapped in `market_hours.gate`: the gate reads TODAY and Sunday 20:00 is a weekend, so
  it would skip the Sunday-night session. The module gates itself on the SESSION's trade date (holiday eves closed).
- The push line IS wrapped: 06:45 is on the trade date.
- A python module, never a curl to the api.
- The crontab is container-local ET and host-bind-mounted read-only: **a deploy does NOT install these lines.**

### Host install — HIS step (AMENDMENTS16 A5)

This edits the MAIN checkout's `backend/crontab`, so it is Ajay's step (or his explicit word), after the branch is on
main. Order: deploy `api frontend cron` FIRST — the image must carry `overnight/` before the host crontab names it —
THEN the install.

```bash
./deploy-cheetah-main.sh api frontend cron
```

```bash
cd /Users/ajay/clinet-test/cheetah-market-app
git fetch origin
git diff origin/main -- backend/crontab
git show origin/main:backend/crontab > backend/crontab
docker compose restart -t 120 cron
docker compose exec -T cron grep -c "overnight.scan" /app/crontab
docker compose exec -T cron grep -c "overnight.push" /app/crontab
```

Expect `2` then `1`. If HIS CALL #1 becomes ON, run this between the deploy and the install:

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply --apply
```

Host sleep skips cron slots (2026-10-11: asleep ~00:15–09:59 ET); the board's late line and the push's read time say so.
Keeping the host awake 20:00–06:45 is his (HIS CALL #13).

## The push — `overnight_movers`, ships OFF

`backend/overnight/push.py`, kind `KIND = "overnight_movers"`, owner-only, at most one per session at `SLOT_ET` =
06:45 ET on trading days. **Ships OFF** (AMENDMENTS16 A2, HIS CALL #1): `push/subs.default_prefs` False and NOT in
`OWNER_KEEP_SET` — he asked for a scan, not an alert. The toggle lives at /notifications. While OFF it still runs, logs
its would-be push on /alerts (a history row reaching 0 devices, listing every passed name) and records why it was quiet.

**Window** (`push.window_reason`): a closed day (the ONE calendar) → its reason; before 06:45 → "before 06:45 ET"; at or
after the regular 9:30 open (`daytrading.data.ET_RTH_OPEN`, reused by name and imported lazily) → "the regular session
opened at 9:30 ET" (the clock words rendered from that constant). It reports the session that ended at 04:00 ET — its last stored read (`scan.load_latest(today)`), timed in the push. No read for today, or a
read of another session → reason, no send.

**Gate** (`push.gate_rows`), every condition must pass, ordered by pct desc then symbol, top `PUSH_TOP_N` = 5 (brief):

| Condition | Constant | Mark |
|---|---|---|
| up overnight (`pct > 0`) | — | gainers only |
| price ≥ $2 | `PUSH_MIN_PRICE = MIN_SHARE_PRICE` | house |
| ≥ $250K traded overnight (`on_dollar`) | `PUSH_MIN_ON_DOLLAR = 250_000` | MINE |
| not a leveraged or inverse ETF | `leveraged is False`; **None (unknown) fails closed** | MINE |

Zero passed → "no name passed the gate", no push (never an index-only push). A second run the same session → "already
pushed for the {td} session" (claim `insert_one` in `overnight_push`, duplicate key). Result counts: `candidates, passed,
pushed, skipped_price, skipped_thin, skipped_leveraged, skipped_lev_unknown, skipped_not_up, no_target`, recorded by
`alert_status.record_result`; `DAILY_PASS_KINDS` carries the kind and `schedule_map()` reads `push.SLOT_ET` lazily →
"06:45 ET, trading days".

**Payload**: title "🌙 Overnight movers — " + the first 3 as `SYM +x.x%` (+ "+n more"); body = the index line (SPY · QQQ
· IWM · DIA against the base close, "—" when a ref is missing, with the read time), up to 5 name lines (pct, price,
overnight $, prior session %, " · q" on a quote-mid price), "+k more on the board", and "UNMEASURED — what moved
overnight, not what to buy. Not advice." `url` `/chart-maps?tab=overnight&on_sub=session`, `tag`
`overnight_movers:{td}`, `tickers` = the ≤ 5 symbols, `items` = every passed name ≤ `ITEMS_MAX` = 25 (MINE; logged on
/alerts, never sent to a device). A passed name's /alerts link opens its Support tab
(`push/recent.ITEM_URL_BY_KIND`).

Registries: `push/subs.default_prefs` (False), `push/hooks.notify_overnight_movers` → `sender.send_to_user(owner,
payload, kind="overnight_movers")`, `market_hours/gate.MARKET_ALERT_KINDS` (silent on closed days), `push/recent`,
`supply_demand/alert_status`; FE `lib/alertKinds.ts`, `pages/Alerts.tsx` (daily strip + skip chips, chip right after
🎚️ tape_control), `pages/Notifications.tsx` (the toggle, default off; the Essentials preset does not turn it on),
`hooks/useNotificationPrefs.ts`. A device with quiet hours on (default window 22:00–08:00) silences a 06:45 ring
(OPEN O6).

## UNMEASURED

Nothing here is measured as a signal. The board lists what moved in the overnight session against the last regular
close; the push names the top movers that pass a liquidity and fund-type gate. Neither says what to buy, and neither is
ranked on any outcome. The gainers list is crowded by 2×/3× funds whose overnight move often reverses the prior
session's drop — a reversal on the tape, tagged and one tap hidden, not an edge. Overnight % includes the prior
evening's after-hours leg (HIS CALL #17). Not advice.

## HIS CALL (nothing decided by him yet; defaults are MINE unless said)

1. **The 06:45 push ON for his phone?** Default **OFF** (`default_prefs` False, not in `OWNER_KEEP_SET`) — he asked for a
   scan. ON = one line in `OWNER_KEEP_SET` + 3 keep-set pins + Essentials + `owner_prefs_apply --apply`.
2. Push time **06:45 ET** and the **09:30** last-ring cut (`daytrading.data.ET_RTH_OPEN`; it reports the session that
   ended 04:00).
3. Push gate: $2 (house floor), **$250K** overnight $ vol, top **5**, leveraged excluded, **unknown leverage excluded
   (fail-closed)**, gainers only.
4. A morning with no passing name: **no push** (vs an index-only push).
5. Universe floor: last regular close ≥ $2 on ≥ **$1M** traded.
6. Board floor **$25K** overnight $ vol; thinner names counted, not listed (vs listing all ~6,100).
7. Price rule: delayed indicative trade first (brief) vs the live quote mid first — **the main session chose quote mid
   first (AMENDMENTS16 A1, MINE: `QUOTE_FRESH_SEC` 300, `QUOTE_SPREAD_MAX` 0.015)**; his to override.
8. Default sub **🌙 Overnight session** (vs Gappers); tab label stays "Overnight".
9. "Hide leveraged ETFs" default **off**.
10. StockTwits names: flagged only through his ★ watchlist — add TWLO INTC HPE MRVL VICR PENG VSTL BEX AAOI BE XELB XLAB
    to ★?
11. No 🚀 / 🧨 / 🎪 / 🪜 chips on 🌙 rows (the Gappers sub keeps them).
12. Cadence 10 min (brief); `KEEP_SESSIONS` 2; `refresh_sec` 300 open / 1800 closed; `STALE_SEC` 1,500.
13. Keeping the host awake 20:00–06:45 (system settings are his).
14. Relying on the free Alpaca plan's overnight feed (the doc says paid).
15. 1× inverse funds tagged "inverse ETF" here (levered_etf's High Beta tags skip 1×).
16. 🌙 emoji (collides with Gajjala K10 post-market) and the Gappers "O⁄N" label meaning after-hours.
17. A "since 20:00" column (vs the after-hours last print) — not built; overnight % includes the after-hours leg.

## OPEN (not verified tonight)

- O1 Alpaca free-plan `feed=overnight` entitlement durability (the doc says paid). A 403 aborts the pass with words.
- O2 Massive snapshot reset time (03:30 ET per Polygon docs) — the first live 03:40 pass logs it.
- O3 `day.v` slightly exceeds the daily agg volume (TSLA 62.42M vs 62.07M) — the $1M universe floor uses `day.v`;
  immaterial at the floor, unmeasured beyond 5 names.
- O4 Fund names that state "Daily"/"Bull" with no multiple — count unknown; the first pin can log them.
- O5 Universe size under the type filter vs the probe heuristic (expected ±10% of 6,267).
- O6 Whether his devices have quiet hours enabled (not probed).
- O7 Blue Ocean coverage of class shares beyond BRK.B.

## Tests

`backend/tests/test_overnight_session.py`, `test_overnight_scan.py`, `test_overnight_board.py`,
`test_overnight_cron.py`, `test_overnight_push.py`, `test_overnight_movers_kind.py`; FE
`frontend/src/lib/overnightSession.test.ts`, `src/hooks/useOvernightSession.test.tsx`,
`src/components/OvernightTab.test.tsx`, `src/components/OvernightSessionBoard.test.tsx`,
`src/pages/Notifications.overnight.test.tsx`, `src/pages/Alerts.test.tsx`, `src/lib/alertKinds.test.ts`,
`src/lib/chartMaps.test.ts`. Contracts: `frontend/scripts/contracts.mjs` "🌙 overnight session + overnight_movers
(2026-10-19)".
