# 🔗 Leveraged-ETF tags on 🎢 High Beta (2026-10-14)

**The ask, verbatim (Ajay 2026-10-14):** "Can you add a short tag on these stocks for their Leverage equivalents like
IRE for IREN, VSTL for VST"

"These stocks" = the names on the 🎢 High Beta tab (rows + cards). Display only — the tag sorts, filters, gates and
pushes nothing (`high_beta_watch`, `rank`, the boxes and the tape kinds are unchanged; pinned by
`tests/test_high_beta_levered.py::test_06`).

## His two examples resolve — from DATA, never a typed map

| ticker | Massive reference name | type | 10-14 $ volume |
|---|---|---|---|
| **IRE** | Defiance Daily Target 2X Long IREN ETF | **ETS** | $187M |
| **VSTL** | Defiance Daily Target 2X Long VST ETF | ETF | $6.4M |

- **The ETS trap.** Massive files IRE under type **ETS**, not ETF. A `type=ETF`-only pull (5,533 funds) does not
  contain IRE, which is why one probe reported "IRE does not exist". `GET /v3/reference/tickers/IRE` returns 200,
  active, listed 2025-10-20 on ARCX. `FUND_TYPES = ("ETF", "ETS", "ETN", "ETV")`; the negative test
  `test_01b_NEG_an_etf_only_pull_misses_IRE_the_trap_that_hid_it` pins the trap.
- **IRNX does not exist** (`/v3/reference/tickers/IRNX` → 404). It appears in no module, fixture or payload (pinned).
- No fund ticker is a literal in `sepa/levered_etf.py` (AST-pinned): every tag comes from the reference list.
- **Rule #1:** a fund is served only if it was ACTIVE in the reference read (`active=true` pull) AND printed on the last
  closed session (one grouped-daily read). Otherwise it gets no tag and is counted.

## The rules (`backend/sepa/levered_etf.py`, PURE `parse_name` / `build_rows`)

A fund is tagged only when its NAME states all three: the leverage, the direction and the stock. The first rule that
fires decides:

1. No `NX` factor → not a leveraged fund (no row, no count).
2. Two different factors ("2x and 3x") → `multi_factor`.
3. Direction: Long / Bull → long; Short / Bear / Inverse / a negative factor → short. Neither → `no_direction`
   (Corgi's "IREN 2x Daily", unless HIS CALL #1 lists the issuer). Both → `both_directions`.
4. Factor ≤ `MIN_FACTOR_EXCLUSIVE` (1×) → `one_x` (AMDD "AMD Bear 1X").
5. **Ticker slot** (skipped when the name has no lower-case letter — the UGLD "DIREXION DAILY GOLD BULL" trap): the
   token right after Long / Short / Inverse or right before Bull / Bear; upper-case ticker shape; never the fund's own
   ticker; never one of `NEVER_TICKER_WORDS` (AND, ETF, DAILY, LONG, SHORT, TARGET, INVERSE…); must be an active CS /
   ADRC. One → tagged by ticker, more → `ambiguous_ticker`.
6. **Company-name slot**: the words after the direction word up to a grammar word / factor (or before Bull / Bear) must
   EQUAL exactly one stock's `core_name` (the reference name with trailing corporate forms stripped: Inc, Corp, Ltd,
   plc, Class A, Common Stock, ADS …; never "group" / "holdings" / "american"). More → `ambiguous_name` (GOOX
   "Alphabet" = GOOG + GOOGL), none → `no_us_underlying`. Never prefix, substring or fuzzy.
7. No print on the last session → `no_print`.

Order per stock: long first, then factor desc, then last-session $ volume desc, then ticker.
Chip: `🔗 2× IRE · IREX · IREG +1` (at most `SHOW_MAX` = 3 tickers; the "+n" title lists the rest).

**Issuer patterns covered by tests:** Tradr ("Tradr 2X Long IREN Daily ETF"), Leverage Shares, GraniteShares, Defiance,
Direxion ("Direxion Daily SOFI Bull 2X ETF", ticker before Bull), T-Rex by company name ("T-REX 2X Long Tesla Daily
Target ETF" → TSLA, "NVIDIA" → NVDA), Corgi (untagged by default; tagged long when HIS CALL #1 says so), 1.25×,
−3× inverse ETNs, single-letter tickers (U, P), class shares (BRK.B → BRK-B), ETS funds.

### Counts on the real 10-14 list (planner's probe, re-run against this module)

| | |
|---|---|
| funds read (ETF 5,533 · ETS 107 · ETV 91 · ETN 45) | **5,776** |
| with a leverage factor | 677 |
| **tagged** | **365 funds on 222 stocks** (352 by ticker, 13 by company name) |
| not tagged, counted | 157 `no_direction` · 119 `no_us_underlying` · 23 `one_x` · 12 `no_slot` · 1 `ambiguous_name` · 0 `no_print` |
| with Corgi as long (HIS CALL #1, not on) | 453 funds on 235 stocks |

The test fixture (`backend/tests/fixtures/levered_etf_reference_2026_10_14.json`, 49 real funds, 22 real stocks, the
10-14 prints, no key) gives **31 tagged on 14 stocks**: IREN → IRE, IREX, IREG, IREZ · VST → VSTL · NBIS → NBIL,
NBIG, NEBX, NBIZ · TSLA 8 funds.

False positives caught while designing, each now a pinned negative: UGLD → GOLD (all-caps name), "Bitcoin" → ABTC,
"Financial" → AFG, "Technology" → PAR, "Sui" → SUIG (loose company-name matching).

## Cadence, cache, staleness

- ONE Mongo doc `levered_etf_map` / `_id: "latest"` (rows, counts, `as_of`, `grouped_day`). Only a COMPLETE read (every
  type complete, the grouped read ok, ≥ 1 tag, inside `REFRESH_BUDGET_SEC` = 180 s) replaces it. A partial read keeps
  the previous map and stamps `last_error_at` + `last_partial`.
- The 🎢 build (its warm thread, never a request) calls `LE.load()`: one doc read, memoised `MAP_MEMO_SEC` = 600 s.
  When the doc is not today's (ET), `load` claims the day atomically in Mongo and starts ONE daemon-thread refresh;
  a failed attempt is retried at most every `RETRY_SEC` = 3600 s. No cron line. The tape-burst cron's 09:32 watch GET
  warms the tab each market day, so the map is fresh by ~09:33.
- Fallback when Massive fails: the last complete map, served with its own "as of" date in the board line; every tag
  hides past `STALE_DAYS` = 7 days ("Leveraged-ETF tags hidden — … last read MM-DD").
- Transport per refresh: `PAGE_LIMIT` = 1000 (= gajjala `TYPES_PAGE_LIMIT`), ≤ `MAX_PAGES_PER_TYPE` = 12 per type;
  16 reference pages + 1 grouped call on 10-14. The key is never logged, raised or stored (pinned).

## Served surfaces

- Row (`rows[i]`) and card (`tile.high_beta`): `levered = [{etf, factor, direction}]`, `levered_chip = {text, parts,
  shown, more, rest}` (each etf part carries the fund name as `title`).
- Card: `badges[1]` = the chip (identity line, after the 🎢 pill; no link — the card is a link); the full list is the
  `Leveraged ETFs` stat under ▸ more.
- Table: the `Leveraged ETFs` column right after Symbol; each ticker links `/sepa/{etf}?tab=tape` (the symbol route
  serves ETFs; probed 200 for IRE, VSTL, MSTX). Badge title = the served legend (daily-reset caveat).
- Board: `high_beta_board.levered = {state, as_of, age_days, grouped_day, n_etfs, n_underlyings, n_on, line, legend}`,
  the line printed under the categories line.
- ℹ️ Rules: one sentence on the 🎢 section's σ line (`rules_info._hb_levered_line`, every number from LE).

## Ops / probe recipe

```bash
python -m sepa.levered_etf refresh --dry-run --json /tmp/lev.json
```

Prints the counts and the IREN / VST / NBIS chip lines; never the key; `--dry-run` writes nothing. Run it in a
throwaway container (never the live api), outside 09:00–16:30 ET. **Wall time of a real refresh: NOT YET TIMED**
(the 2026-10-14 executor did not run it — no container access in that package).

### 2026-10-14 review fixes

- **Coin funds fail closed.** A crypto coin whose symbol or name is also a US stock's (`COIN_SYMBOLS`: LINK =
  Interlink, TRX = TRX Gold, SUI = Sun Communities, LTC = LTC Properties, SEI = Solaris, ATOM = Atomera, APT = Alpha
  Pro Tech, TRON = Tron Inc., BONK = Bonk Inc./BNKK) is blocked in BOTH the ticker slot and the name slot and counted
  `no_us_underlying`. The 10-14 list had zero such tags (all 365 checked), but 21Shares already lists coin funds, so one
  new listing would have put a wrong 2× tag on a real-money surface. Closed set: a new colliding coin is a new line,
  never a fuzzy rule. Each name is a pinned negative (`test_02h_*`).
- **The ready line now counts every untagged fund.** Its three parts are `no_direction`, `one_x` and
  `untagged_other()` = every other `SKIP_REASONS` count (no_us_underlying, no_slot, ambiguous_*, multi_factor,
  both_directions, no_print); they sum to with_factor − tagged (10-14: 157 + 23 + 132 = 312, was 299). Pinned by
  `test_02i_*`.
- **"Direxion Daily S&P 500 Bull/Bear 3X"** → no stock (`no_us_underlying`, never S = SentinelOne), pinned in `test_02`.
- `sepa/levered_etf.py` joins the key-levels import allow-list (`tests/test_key_levels.py` `ALLOWED`): display only,
  it reuses `ET`, `prev_market_day` and `_day_mmdd`.
- Not changed, HIS CALL #5: when Massive fails the last complete map keeps serving up to `STALE_DAYS` = 7 days (a fund
  delisted inside that window can still show); the as-of date is on the board line and the table chip title, not on
  the card badge. Options: `STALE_DAYS` = 1, or keep 7 and add the as-of date to the card stat.

## HIS CALLS (defaults in brackets; none changes a gate, a sort or a lane)

1. Corgi "X 2x Daily" funds (124, e.g. IREC) as 2× long? [not tagged, counted]
2. Inverse funds shown? [yes, after the longs]
3. 1× inverse funds (23, e.g. AMDD)? [not tagged]
4. Chip cap [3 tickers + "+n"]
5. Staleness [hide past 7 days]
6. Tie order [most traded on the last session first]
7. A $ volume floor for thin funds? [none; thin funds sit last]
8. Glyph / slot [🔗; column right after Symbol; card identity line]
9. Scope [🎢 High Beta only]
10. Exact company-name matches [on; GOOX "Alphabet" stays untagged as ambiguous]
11. Refresh [first use each ET day inside the api; no cron line]
