# 🔒 "Hard to borrow" tag — Reg SHO threshold security on the 🚩 Gajjala surfaces (2026-11-22)

## The ask, verbatim

Ajay 2026-11-22:

> "Can you do something for me for reversal squeezes can you also tell me if something is under when it's on our list.. i want to check if people are finding it hard to get stocks like AkAN now has that issue.. add a tag to stocks tickers like short interest, name the tag " hard to borrow" threshold security"

He attached a screenshot of the Nasdaq Reg SHO Threshold List page (trade date Fri 2026-11-20, 76 names, AKAN listed).

## What the tag is

A **display-only** tag, named with his words, drawn in the slots where the 🩳 short-interest label / chip already
draws on the 🚩 Gajjala surfaces. It shows only when the ticker is on the latest exchange **Reg SHO threshold list**.

The rule behind the list (SEC Regulation SHO Rule 203(c)(6), as quoted on Nasdaq's Reg SHO page): aggregate fails to
deliver of **at least 10,000 shares** and **at least 0.5 % of total shares outstanding**, for **5 consecutive
settlement days**. These are the SEC's numbers, enforced by the exchanges. The app **describes** them
(`REG_SHO_MIN_FTD_SHARES`, `REG_SHO_MIN_PCT_SHARES_OUT`, `REG_SHO_CONSEC_SETTLEMENT_DAYS`); it never compares
anything against them. The exchange decides who is on the list; the app only reads the list.

**The honesty line** (served as `HONESTY_NOTE`, verbatim):

> The threshold list measures persistent fails to deliver, not a broker's borrow rate — a broker's own hard-to-borrow list can differ.

His name "Hard to borrow" is kept. The data underneath is a fails-to-deliver list, not a borrow fee, not borrow
availability. The honesty line rides the hover, the ℹ️ Rules pick and this doc. On the phone there is no hover, so
the list's date rides the chip text itself.

### The words (served; the frontend types none)

Worked example, AKAN on the Nasdaq list of 2026-11-20 — these four strings are the contract:

| Field | Where it draws | Text |
|---|---|---|
| `chip` | non-🎾 cards, head chip row | `🔒 Hard to borrow · threshold security · 11/20` |
| `short` | 📋 table 🩳 cell, 👀 Watch tile head | `🔒 Hard to borrow · 11/20` |
| `label` | 🎾 Reversal Squeeze card, under the 🩳 line | `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20` |
| `title` | hover on all of the above | `🔒 Hard to borrow — AKAN is a Reg SHO threshold security on the Nasdaq list for 2026-11-20: fails to deliver of at least 10,000 shares and at least 0.5% of shares outstanding for 5 straight settlement days (SEC Regulation SHO Rule 203(c)(6)). The threshold list measures persistent fails to deliver, not a broker's borrow rate — a broker's own hard-to-borrow list can differ. A data label, not a signal. UNMEASURED.` |

A tag from a list that could not be refreshed keeps drawing with its date and ` · stale` appended (the 🩳 chip's own
word), and a greyed look. No served string says borrow fee, a borrow rate as a number, "cannot be borrowed",
"impossible", a squeeze promise or a prediction — a test pins that.

**2026-11-24 — the words grew.** The four strings above are the tag as built on 11-22. Since 11-24 each one also
carries the run of consecutive settlement days on the list and the Rule 203(b)(3) close-out day (e.g. AKAN on the
11/20 list: `🔒 close-out Wed 12/9 · day 1 of 13`), or ` · day count unknown` when a day's list was not read. The
six states, the worked strings, what the date is and is not, and the history behind it live in
`docs/gajjala/reg_sho_closeout_day_2026_11_24.md`. The test file pins the current strings.

## The three sources (five exchanges)

All three are keyless public files. Every fact below was measured with single GETs on 2026-11-22 (Sunday), the
verbatim files are kept in `backend/tests/fixtures/reg_sho/`.

| Source | URL | Exchanges (markets) | File shape |
|---|---|---|---|
| Nasdaq | `https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth{YYYYMMDD}.txt` | Nasdaq | header `Symbol\|Security Name\|Market Category\|Reg SHO Threshold Flag\|Rule 3210\|Filler`, CRLF on every line, trailer = 14-digit file stamp |
| NYSE group | `https://www.nyse.com/api/regulatory/threshold-securities/download?selectedDate=YYYY-MM-DD&market={NYSE\|NYSE American\|NYSE Arca}` | NYSE, NYSE American, NYSE Arca (one GET each) | header `Symbol\|Security Name\|Market Category\|Reg SHO Threshold Flag\|Filler\|Filler`, column 3 = the market name; header and rows end LF, the trailer alone ends CRLF |
| Cboe BZX | `https://cdn.cboe.com/resources/us/equities/market-statistics/reg-sho-threshold/bzx_equities_reg_sho_threshold_{YYYYMMDD}.txt` | Cboe BZX | header `Symbol\|CompanyName` (every row is on the list), CRLF, trailer = file stamp. Found in the Cboe page's own script; the old `/csv/` path is dead |

On the fixture set (Nasdaq + NYSE group for 11-20, Cboe for 11-19): Nasdaq 76, NYSE 1 (HAWK), NYSE American 2 (OPTT,
POAS), NYSE Arca 24, Cboe BZX 57 — **160 distinct names, zero overlaps**. AKAN and ACONW are on the Nasdaq 11-20 file
and NOT on 11-19: AKAN joined the list on Friday's file.

### The traps (measured)

- **Nasdaq "no file" is HTTP 302** with `Location: /Trader.aspx?id=http404` (an HTML page) — never a 404. Following
  the redirect would read an HTML page; every request passes `allow_redirects=False`.
- **Nasdaq on a bank holiday with the market open** (Veterans Day 11-11, Columbus Day 10-12): a file IS published,
  the same names as the day before, its own trailer date.
- **NYSE answers 200 with zero rows for everything it does not have**: a weekend date, a future date, a bank holiday
  (11-11 and 10-12: American 0 / Arca 0 while the days around them carried 2 / 14-17) and a bogus market name. The
  trailer is synthetic (`…220201` when rows exist, `…210500` when none) and carries no information.
- **A genuinely empty NYSE market is ordinary**: 11-10 had NYSE **0**, NYSE American 3, Arca 14.
- **The NYSE market value is case-sensitive**: `market=NYSE%20American` → 2 rows; `market=nyse%20american` → 200,
  same header, 0 rows, trailer `…210500` — byte-identical to a genuine empty list. `+` and `%20` both work for the
  space.
- **Cboe "no file" is HTTP 403** with an XML body containing `<Code>AccessDenied</Code>`.
- **Not one symbol in the 19 list files is non-alphanumeric**: the class-share / suffix path is typed, never seen.
- **Half the names are funds**: Cboe BZX 57 of 57 and NYSE Arca 24 of 24 are funds (81 of 160). The Gajjala scan
  (`SCAN_INSTRUMENT_TYPES = {"CS", "ADRC"}`) can hold none of them; only a ticker he types on the 👀 Watch can.

Not read, on purpose: FINRA's OTC threshold list (OTC names are not on the scan), NYSE National / Chicago / Texas.

### Measured vs typed

| Item | Status | Cost if wrong |
|---|---|---|
| Nasdaq "no file" = 302 → `id=http404` | measured (two dates) | — |
| Cboe "no file" = 403 `AccessDenied` | measured (two dates) | — |
| NYSE "no file" = all three markets empty | measured (weekend, future, two bank holidays) | — |
| Nasdaq plain 404, Cboe 404 `NoSuchKey` | NEVER SEEN → treated as an ERROR (`unseen_404`), not "no list" | a slower recovery, never a false "not listed" |
| Nasdaq publish clock 23:15 ET on the trade date | one `Last-Modified` (23:00:06 ET) | a retry every `RS_RETRY_MIN` until the file lands |
| NYSE publish clock 23:15 ET on the trade date | TYPED — NYSE's stamp is synthetic | same: 3 GETs per retry until it lands |
| Cboe publish clock next business day 03:30 ET | one `Last-Modified` (03:04 ET) | same: 1 GET per retry |
| partial late publication of ONE NYSE market | unmeasured | covered by the zero-row confirming re-read (below) |

A wrong clock never produces a wrong tag: it only delays a new list by `RS_RETRY_MIN` per try. The first `found` times
of the NYSE and Cboe lists after the first weekday night bound the two unmeasured clocks; they are to be written here
once read (not yet observed at the time of writing).

## Trade date and publish clocks

- `publish_dt`: the trade date at the source's publish time (ET), or — for Cboe — the NEXT business day at its time.
- `expected_trade_date` (E): start at the previous-or-same business day, step back one business day at a time until
  "now" is past that day's publish time. Business days come from the ONE house calendar
  (`market_hours.reminder.ALL_HOLIDAYS`, read through `short_interest.read.is_business_day` /
  `prev_business_day` / `add_business_days`); no second calendar.
- Worked: Sun 11-22 20:42 ET → Nasdaq 11-20, NYSE 11-20, Cboe BZX 11-19. Mon 11-23 10:00 → 11-20 for all three.
  Fri 11-27 10:00 (the day after Thanksgiving) → Nasdaq 11-25, never 11-26.
- **The list is one session behind by construction.** Friday's file lands ~23:00 ET Friday, so during Friday's session
  the app shows Thursday's list. AKAN joined on the 11-20 file — it could not have been tagged during Friday's session.
- When the newest file is missing, the reader walks back at most `RS_WALKBACK_BDAYS` business days to the newest
  list that exists, and stops early at the newest list it already holds.

## The tri-state: on / off / unknown

Every name is one of:

- **on** — the symbol is on ANY held list. Only these names are served in `items` (and only these draw a tag).
- **off** — on none of the lists AND all five markets read `ok`.
- **unknown** — anything else. A missing, unreadable or not-yet-confirmed list is **never** read as "off".

`?check=A,B` answers this tri-state per name. `check` is strict over all five markets on purpose; the fault LINE is
the scoped one (next sections).

Anything that is not one of the three measured "no list" answers — a timeout, an exception, any other status (a
plain 404 and a `NoSuchKey` body included), a 302 or 403 with any other body, a parse failure — is an **error**,
never "no list" and never an empty list.

## An empty list is believed only after two reads

Because an empty NYSE answer is indistinguishable from "no file" or a wrong market value, any list with **zero rows**
(any source) is written with `confirmed_at: null` and is **not yet believed**. A later refresh round, at least
`RS_RETRY_MIN` after the first read, re-reads THAT market for THAT date (one GET):

- zero rows again → `confirmed_at` is set; the market reads `ok`;
- rows now → the list is replaced, `revised_at` and `confirmed_at` are set;
- an error → left unconfirmed, retried the next round.

Until then the market reads `pending` and its source line says `… · 0 names (re-reading to confirm)`, so a name
absent from it is `unknown`, never `off`. A list with rows is believed at its first read.

**NYSE group rule:** the three NYSE markets are fetched together for a date. Any error → the whole group is an error
and nothing is written for that date. All three valid with zero rows in total → "no list" (walk back). Otherwise the
group is found, and a single empty market goes through the two-read rule above.

**The case-sensitive market value**: the three NYSE names live in ONE constant, `NYSE_MARKETS`, spelled exactly
`NYSE`, `NYSE American`, `NYSE Arca`, and every URL is built by ONE function, `source_url`. A test pins the three
exact URLs for 2026-11-20; lower-casing one name turns that test red.

**Residual, NOT closed:** if NYSE renames a market value on its side, that market reads empty twice and is believed —
a false "off" for its names, visible only as "0 names" on that source's served line.

## The fault line — which lists raise it, and why the fund lists do not

When a **stock** list cannot be read, one served line says so, so a missing tag never silently reads as "not listed":

- `🔒 Hard to borrow tags may be missing or out of date: <the faulting lists>.`
- If the read itself raised: `🔒 Hard to borrow tags could not be read — a missing tag does not mean the name is off the list.`

Only **Nasdaq, NYSE and NYSE American** (`faults: True`) can raise the line. **NYSE Arca and Cboe BZX**
(`faults: False`) report in the served `sources` list only — their own tags still say ` · stale`, and `complete` still
goes false, but they never raise the line. Why: on the fixtures every one of their 81 names is a fund, and the Gajjala
scan holds no fund (`SCAN_INSTRUMENT_TYPES = {"CS", "ADRC"}`). A fund-list outage would put a red line over a 🚩 card
grid that cannot contain a single name from those lists. The price: a fund he types on his 👀 Watch can lose its tag
with no red line while those lists are unreadable (HIS CALL #7).

The line draws when a stock list is (a) `failed`, or (b) `pending` with nothing held while no refresh is running
(never read, Mongo down, the worker could not start or died). It does NOT draw while a refresh is running and the
first answer comes back.

One error is not a failure: with a held list inside the grace, one error reads `pending` (tags not stale, no line),
the first retry comes after `RS_ERROR_RETRY_MIN`; `RS_ERROR_STRIKES` errors in a row, a list beyond
`RS_BEHIND_GRACE_BDAYS`, or an error with nothing held reads `failed`. So the line can stay quiet for up to
`RS_ERROR_RETRY_MIN` after the first error.

Where it draws: above the 🚩 / 🧪 card grid, above the 📋 All strategies table, and as a line in the 👀 Watch head.

A transport failure (the api down, a proxy fault, an api older than the frontend) with NOTHING held yet draws
**nothing** from this feature — no tag and no line. A failure AFTER a good read keeps the last list (tags and line
stay) and retries after `RS_RETRY_MS` (useRegSho.ts). Deploy `api` before `frontend`.

## Skipped rows

A row whose symbol cell does not look like a ticker (`^[A-Z0-9][A-Z0-9 ./\-+$^=#]{0,14}$`, compared as served, NOT
upper-cased) is **skipped and counted** — never fatal, never rewritten into another ticker. Upper-casing would turn a
preferred like `ABCpA` into `ABCPA`, a different possible ticker, and tag the wrong name. The count is served per
source (`skipped`) and the source line ends ` · N not read`. More than `RS_MAX_SKIPPED_ROWS` skipped rows = the file
is malformed (a shifted column must not read as a short list) → error.

Everything else that is wrong is fatal for that file → error, never an empty list: a wrong header, no trailer or a
trailer for another date (truncated or wrong-day file), a flag other than `Y` / `N` (a Nasdaq / NYSE row flagged `N`
is not on the list), a NYSE row whose market column is another market, an oversize body, an HTML body.

Symbol spellings: separators (space . / -) are normalised to `.` and the tag is served under both house spellings
(`BRK.B` and `BRK-B`); the lookup is an exact upper-case key match — AKAN listed does not tag AKANW, ACONW listed does
not tag ACON.

## The Mongo docs — never purged

Collection `reg_sho_threshold` (new). The only operations used: `find_one` with a sort, `find({"kind": "state"})`,
`replace_one(…, upsert=True)`, and one best-effort `create_index`. **No delete anywhere.** Since 2026-11-24 the
history read adds exactly two more `find` filters, both bounded by the 30-settlement-day window:
`find({"kind": "list", "trade_date": {"$gte": "<YYYY-MM-DD>"}})` and
`find({"kind": "nolist", "trade_date": {"$gte": "<YYYY-MM-DD>"}})`.

```
list         : {_id: "list|<mkt>|<YYYY-MM-DD>", kind: "list", source, market, exchange, trade_date, symbols: [...], n,
                skipped, file_stamp, url, fetched_at, confirmed_at, revised_at}
               a backfilled one (2026-11-24) also carries "backfilled": true
state        : {_id: "state|<source>", kind: "state", source, attempt_at, attempt_for, result: "running" | "found" |
                "missing_walked" | "error", error, errors, good_date, checked_at}
fetch hole   : {_id: "nolist|<source>|<YYYY-MM-DD>",         kind: "nolist", op: "fetch",   source, market: None,
                trade_date, result: "missing" | "error", error, tries, asked_at}                       (2026-11-24)
confirm hole : {_id: "nolist|confirm|<market>|<YYYY-MM-DD>", kind: "nolist", op: "confirm", source, market,
                trade_date, result: "error", error, tries, asked_at}                                   (2026-11-24)
```

- **Never purged — `fetched_at` is the point-in-time record a later study would need.** It is the FIRST write time
  and is never overwritten (a confirming re-read sets `confirmed_at` / `revised_at`, not `fetched_at`). About five
  small docs per trading day (~10 KB/day, ~2.5 MB/year).
- **`backfilled: true` is NOT point-in-time.** A list doc written by the 11-24 history backfill has `fetched_at` =
  the backfill time, days after its trade date. A later study must exclude those docs or treat them as hindsight.
  The backfill never overwrites a held list doc.
- The hole docs record a date whose list could not be read (a "no file" answer, an error, or a failed confirming
  re-read), so the one retry rule can space the next ask. The rule, the cool-down and the breaker:
  `docs/gajjala/reg_sho_closeout_day_2026_11_24.md`.
- **Corrected 2026-11-24:** the read no longer loads only the newest list. It loads the newest list doc per market
  (five `find_one`) plus the three state docs, and — when any market holds a list — the list and hole docs of the
  30-settlement-day window (the two `find` filters above, ≤ ~155 small docs), to count each name's run of days on
  its list. The read still never fetches.
- The state doc is written with `result: "running"` BEFORE the first outside call and overwritten in a `finally`, so
  a worker that dies mid-round still throttles the next one.

## How it refreshes

- The api **never fetches inline**. `GET /short-interest/reg-sho` reads Mongo only; when a list is due it kicks ONE
  single-flight daemon worker (the house lazy-worker shape: one at a time under a lock, the flag reset when the thread
  cannot start), with an in-process floor of `RS_KICK_MIN_SEC` between worker starts.
- Calendar-aware: when the newest held list is already the expected one and nothing waits for a confirming re-read,
  the source is never due → **0 outside calls**. Attempts for one source are spaced by `RS_RETRY_MIN`.
  (2026-11-24: the same worker then runs the paced history backfill and the due re-asks of open holes — see
  `docs/gajjala/reg_sho_closeout_day_2026_11_24.md`; once the window is read and no hole is due it adds 0 calls.)
- While a refresh runs the payload says `refreshing: true` with `retry_after_sec` = `RS_RETRY_AFTER_SEC`; the
  frontend hook makes at most `RS_FOLLOWUP_MAX` follow-up GETs and keeps a still-`refreshing` answer only
  `RS_RETRY_MS`, not the full `RS_TTL_MS`.
- One GET per page: the hook fetches the whole list once (module cache, single flight) and every chip looks its
  ticker up in it.
- Tests never reach the three hosts: the outside call goes through one module seam (`_http`), refused for the whole
  session in `backend/tests/conftest.py`.

## Where it draws

| Surface | What | Form |
|---|---|---|
| 🎾 Reversal Squeeze card (🚩 5-min and 🧪 Audited) | a line directly under the 🩳 SI label | `label` |
| every other Gajjala card | a chip in the head chip row, after the 🩳 chip | `chip` |
| 👀 Watch tile head (his rows and 🤖 auto rows) | a chip beside the 🩳 EXTREME slot | `short` |
| 📋 All strategies table | inside the 🩳 cell, after the SI text | `short` |
| above the card grid, above the 📋 table, 👀 Watch head | the fault line, only when a stock list cannot be read | served text |
| directly after the 🔒 on Gajjala cards and in the 📋 table (NOT the 👀 Watch) | the 💸 Borrow read (IBKR fee + shares available) — its own engine and doc: `docs/gajjala/borrow_fee_ibkr_2026_11_22.md` | 💸 `label` / `chip` / `short` |

One tag per card / tile / row. The tag is independent of the 🩳 read: a listed name with no SI record still shows it.
Nothing draws — no wrapper, no space — when the name is not on a list. The look is neutral: it does not borrow the
🩳 EXTREME alarm look (amber + bold).

## What it never does

No gate, sort, filter, rank, push, A+ grade, lane input, threshold, crontab line, notification pref or broker key
reads it. No edit under `backend/chart_maps/`, `backend/push/`, `backend/trading/` (a test pins that no file there
names `reg_sho`). It never hides a card. GG's verified rule U10 stands: no short-interest threshold or filter
anywhere — this tag is not one.

## Constants

The code is the source; if this table and `backend/short_interest/reg_sho.py` / `frontend/src/hooks/useRegSho.ts`
ever disagree, the code wins. **MINE** = a number or word I chose; none is a trading threshold.

| Constant | Value | Whose |
|---|---|---|
| `TAG_WORDS` | `Hard to borrow` | **HIS** (verbatim) |
| `GLYPH` | 🔒 | **MINE** |
| `REG_SHO_MIN_FTD_SHARES` | 10,000 | SEC Rule 203(c)(6) — described, never compared |
| `REG_SHO_MIN_PCT_SHARES_OUT` | 0.5 % | SEC Rule 203(c)(6) — described, never compared |
| `REG_SHO_CONSEC_SETTLEMENT_DAYS` | 5 | SEC Rule 203(c)(6) — described, never compared |
| `NYSE_MARKETS` | `NYSE`, `NYSE American`, `NYSE Arca` (exact case) | NYSE's own values (measured) |
| `RS_HTTP_TIMEOUT_SEC` | 6 | **MINE** |
| `RS_REFRESH_BUDGET_SEC` | 45 | **MINE** |
| `RS_RETRY_MIN` | 30 | **MINE** — also the wait before an empty list is re-read |
| `RS_ERROR_RETRY_MIN` | 5 | **MINE** |
| `RS_ERROR_STRIKES` | 2 | **MINE** |
| `RS_KICK_MIN_SEC` | 60 | **MINE** |
| `RS_WALKBACK_BDAYS` | 5 | **MINE** |
| `RS_BEHIND_GRACE_BDAYS` | 2 | **MINE** |
| `RS_RETRY_AFTER_SEC` | 20 | **MINE** |
| `RS_CHECK_MAX` | 50 | **MINE** |
| `RS_MAX_BYTES` / `RS_MAX_ROWS` | 2,000,000 / 5,000 | **MINE** |
| `RS_MAX_SKIPPED_ROWS` | 10 | **MINE** |
| publish clocks | Nasdaq / NYSE 23:15 ET; Cboe next business day 03:30 ET | **MINE** (Nasdaq and Cboe from one `Last-Modified` each; NYSE typed) |
| FE `RS_TTL_MS` / `RS_RETRY_MS` | 600000 / 60000 | **MINE** (the 🩳 hook's own values) |
| FE `RS_FOLLOWUP_MAX` / `RS_FOLLOWUP_MIN_MS` / `RS_FOLLOWUP_MAX_MS` | 2 / 5000 / 120000 | **MINE** |
| `RS_HIST_SETTLEMENT_DAYS` | 30 | **MINE** (2026-11-24) — settlement days of lists read behind the newest one, per market |
| `RS_HIST_MAX_GETS` | 40 | **MINE** (2026-11-24) — outside calls after which a backfill round starts no further item |
| `RS_HIST_BUDGET_SEC` | 45 | **MINE** (2026-11-24) — wall budget of one backfill round |
| `RS_HIST_PAUSE_SEC` | 0.25 | **MINE** (2026-11-24) — pause between two backfill items |
| `RS_HIST_MAX_TRIES` | 3 | **MINE** (2026-11-24) — asks of one hole at the short spacing |
| `RS_HIST_REASK_MIN` | 1440 | **MINE** (2026-11-24) — minutes between asks of a `missing` hole, and of an `error` hole past the tries |
| `RS_HIST_NOT_READ_MAX` | 10 | **MINE** (2026-11-24) — unread dates listed per market in the payload |
| `HOLE_KIND` | `nolist` | **MINE** (2026-11-24) — doc kind of a recorded hole |
| `RS_RUN_START_MAX_SETTLEMENT_DAYS` | 250 | **MINE** (2026-11-26) — walk-back bound per asked name, about one year of settlement days (HIS CALL #11 of sitrack) |
| `RUNSTART_KIND` | `runstart` | **MINE** (2026-11-26) — doc kind of an asked name's walked-back run start |

The Rule 203(b)(3) / Rule 204 / Rule 144 constants of the close-out day live in `backend/short_interest/reg_sho_runs.py`;
their table is in `docs/gajjala/reg_sho_closeout_day_2026_11_24.md`.

## ℹ️ Rules

One pick, appended LAST in the 🩳 section (built by `reg_sho.rules_pick()` from the constants above, never retyped).
**The ℹ️ 🩳 section is at its cap of 8 picks** (`tests/test_rules_info.py`), and the pick sits under the 🩳 title
"Short interest — FINRA's count…". The next 🩳 line must fold into an existing pick, or the tag moves to its own ℹ️
section (HIS CALL #11).

## UNMEASURED

Nothing in the repo measures the threshold list or borrow difficulty against outcomes. This tag carries **no edge
claim** — it is a data label. Adjacent studies (SI × cradle 11-17, low-float × 🎾 × SI 11-21) are about short
interest, not this list, and are never to be quoted as support. The lists are kept from day one so a pre-registered,
point-in-time study is possible later — only on his word.

## HIS CALL — built to a default, or not built

1. **Wording and glyph.** Default chip `🔒 Hard to borrow · threshold security · 11/20`, 🎾 label
   `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20`, short form `🔒 Hard to borrow · 11/20` on
   the 📋 table and the 👀 tile (the full sentence on hover). The 🔒 is mine; shorter or different words are his.
2. **Scope.** Gajjala cards, 👀 Watch tiles, 📋 table only. Every other Chart Maps board and the ticker page: not built.
3. **Any use beyond a tag** — sort, filter, a "🔒 only" toggle, a push when a board or Watch name joins the list (a new
   push kind = a keep-set change), an A+ or lane input: not built.
4. **Watch placement.** Default: in the tile head, visible, short form. He asked on 11-22 for less info on the Watch —
   behind ⋯ instead is his call.
5. **Stale handling and the engine numbers — all mine.** A tag from a list that could not be refreshed keeps drawing
   with ` · stale` and its date, with no cut-off; a list more than 2 business days behind reads stale / failed; one
   error waits 5 min quietly and 2 errors in a row raise the line; an empty list is believed after a second read
   30 min later.
6. **Real borrow data.** The threshold list is a fails-to-deliver list, not borrow availability or a fee.
   **Answered 11-22, built as 💸** — his word "yes i need that please": Interactive Brokers' public shortable-shares
   file (no key), one broker's indicative fee and shares available, drawn beside this tag. See
   `docs/gajjala/borrow_fee_ibkr_2026_11_22.md`.
7. **Sources.** Nasdaq, NYSE, NYSE American, NYSE Arca, Cboe BZX. Default: the two fund lists are read and tag a fund
   on his Watch, but never raise the line. Dropping them, or letting them raise it, is his. FINRA's OTC list and the
   other NYSE venues: not read.
8. **Fault line.** Default: ONE line, only when a stock list could not be read — above the 🚩 / 🧪 card grid, above
   the 📋 table and in the 👀 Watch head. Taking it off the Watch is his call.
9. **"Tell me".** Built as the tag. A summary line ("on the threshold list today: AKAN, …") is not built.
10. **Measurement.** UNMEASURED. A pre-registered study of threshold-list names × 🎾 outcomes only on his word.
11. **ℹ️ home.** Default: pick 8 of the 🩳 section (now full). Its own ℹ️ section is his call.
12. **Look.** Default: neutral — no amber, no heavy bold; the 🩳 EXTREME alarm look stays EXTREME's alone.
13. **The close-out day on the tag (2026-11-24).** Its own HIS CALL list — a date at all, how day 1 is counted,
    settlement vs trading days, which date, the phone chip, the word — is in
    `docs/gajjala/reg_sho_closeout_day_2026_11_24.md`.

## How to check

One read of the served list (authed; replace the email with the owner's):

```bash
rtk proxy curl -s -H "X-User-Email: OWNER_EMAIL" "http://127.0.0.1:8000/short-interest/reg-sho?check=AKAN,AKANW"
```

- `check` → `AKAN: "on"`, `AKANW: "off"` when all five sources are `ok` (`unknown` while any list is unread or an
  empty list is waiting for its second read — that is by design, not a failure).
- `sources[].text` — five lines, one per market, each with its list date and name count.
- `fault_text` — null unless a stock list cannot be read.
- The first read after a deploy may say `refreshing: true` with empty `items`; one more read ~20 s later carries the
  lists.

The real payload through the real component:

```bash
REG_SHO_LIVE_PAYLOAD=/abs/path/to/payload.json rtk proxy npx vitest run src/components/GgHardToBorrow.payload.test.tsx
```

On https://pounce.ajaykandakatla.dev → 🚩 Gajjala: a 🎾 Reversal Squeeze card whose name is in `items` shows the
label under its 🩳 line; another card shows the chip; the 👀 Watch tile and the 📋 table likewise.

Tests: `backend/tests/test_reg_sho_threshold_2026_11_22.py` (engine, route, NEGATIVES), the `GgHardToBorrow*`,
`useRegSho`, `regSho` and `*.htb.test.tsx` suites in `frontend/src/`.
