# 💸 Borrow read — Interactive Brokers' shortable-shares file beside the 🔒 tag on the 🚩 Gajjala surfaces (2026-11-22)

## The ask, verbatim

Ajay 2026-11-22:

> "What is short borrow fee? Is that a real time value I saw AKAN has a high short borrow fee"

I explained it and offered "a borrow fee + shares-available line next to the 🔒" from Interactive Brokers' file. He
answered:

> "yes i need that please"

**Read this first: AKAN — the name in his sentence — is NOT in IBKR's file today.** On a 🎾 card it reads
`💸 not in IBKR's borrow file`; under the built default every other surface shows nothing for it. 50 of the 160 🔒
threshold names are in the same place (coverage below, HIS CALL #1).

## What it is — and what it is NOT

A **display-only** read of ONE broker's public file: per US ticker, the yearly borrow fee rate and the number of
shares Interactive Brokers (IBKR) shows available to lend. It draws as a 💸 line / chip directly after the 🔒 "Hard
to borrow" tag (`hard_to_borrow_reg_sho_2026_11_22.md`), in the same slots.

What it is NOT:

- **Not the fee he would pay.** It is one broker's *indicative* rate (IBKR's own word for it). The real fee is set by
  his own broker at the moment he borrows. It is not Fidelity's rate and not Fidelity's locate list.
- **Not real time.** IBKR regenerates the file about every 15 minutes (PROVISIONAL, see below); the app re-reads it
  at most once every 15 minutes, and only while a Gajjala page is open.
- **Not a signal.** No gate, sort, push, A+ or lane reads it. UNMEASURED.
- **Not a zero when a name is missing.** A name IBKR does not list has no number; the app never prints one for it.

**The honesty line** (served as `HONESTY_NOTE`, verbatim, in every listed hover):

> One broker's indicative rate — your broker sets its own fee when you borrow.

An absent name's hover carries `ONE_BROKER_NOTE` instead:

> One broker's file — your own broker keeps its own list.

## The source

| Item | Value |
|---|---|
| Host | `ftp2.interactivebrokers.com`, port 21 — the ONLY host; no fallback list |
| User / password | `shortstock` / empty password (anonymous, shared by everyone who reads it) |
| Files | `usa.txt` + `usa.txt.md5` |
| One fetch | ONE FTP session, three downloads in order: `usa.txt.md5`, `usa.txt`, `usa.txt.md5` (the md5 before AND after the file) |
| Timing | from the host: whole session 7–10 s, the 1.8 MB download 3.7–3.8 s; from INSIDE `cheetah-market-app-api-1` (Python 3.11.16): connect 0.7 s, whole session 6.2 s |
| Not used | `ftp3.` and `ftp.` time out on port 21 from this network |

IBKR publishes this for anonymous download: its knowledge-base article **"Monitoring Stock Loan Availability"** names
this host, the `shortstock` user and the empty password, and describes the columns (symbol, currency, name, contract
ids, rebate and fee rates, shares available), and calls its rates "indicative". **IBKR's pages refused our fetch
(HTTP 403) — those statements are quoted from search snippets, not from the page itself.** The day-count IBKR uses to
bill a borrow was NOT established (HIS CALL #7).

## The file (measured)

- Line 1 `#BOF|2026.11.22|22:57:25`; line 2 the header `#SYM|CUR|NAME|CON|ISIN|REBATERATE|FEERATE|AVAILABLE|FIGI|`;
  rows of exactly 10 `|`-cells (19,845 of 19,845); the last line `#EOF|19845` = the data-row count. CRLF line ends,
  pure ASCII, no control byte besides CR / LF, 1,802,339 bytes.
- Currencies: USD 19,814 · EUR 23 · CAD 8. Only USD rows are ever served; a CAD `ATN` row exists with no USD `ATN`
  row, so `ATN` reads absent.
- FEERATE and REBATERATE are `NA` on 174 rows (always together) → `fee n/a`.
- AVAILABLE `>10000000` on 791 rows — a LOWER BOUND, printed `>10M` / `more than 10,000,000`, never `10M`.
- **No row had AVAILABLE 0** (min 1; 1,804 USD rows at 1,000 shares or fewer).
- No duplicate symbol, also after the house normaliser. Fee: min 0.0000, median 1.22, p90 18.2, p99 149.8, max
  1018.7495 (RZAI); 4 decimals.
- Symbols: 428 carry a SPACE (`BRK B`, `BF A`, `PCG PRB`, `AAC U`), 279 a dot (`BFIT.OLD`), max 9 characters, all
  upper case. `BRK B`, `BRK.B` and `BRK-B` read one row (the 🔒 engine's `norm_symbol`, reused).
- Two consecutive files differed in 10 of 19,845 rows — every fetch is a changed file, even on a Sunday night.

### The md5 trap (3 of 3 files)

`usa.txt.md5` is 32 hex characters with no newline, and it equals the md5 of the file **with CRLF turned into LF**.
The md5 of the bytes as downloaded NEVER matches. The engine hashes the LF form. A file regenerated between the first
md5 and the download is matched by the second md5. Both md5 answers wrong → the fetch is an error (`md5`) and the
held file stays; no md5 readable at all → the file is accepted with `md5_ok: null`.

### The stamp's clock

The file names no time zone. On 11-22 the stamp tracked US Eastern wall-clock (also at 23:34 ET). Daylight-saving
behaviour is unverified, so **the stamp is printed VERBATIM and the engine never does arithmetic on it.** Every age
the app prints is measured on OUR clock, from the moment we first saw that stamp (`stamp_seen_at`).

### The NAME cell

Never empty, up to **60** characters (33 longer than 40), **HTML-escaped** (`&amp;` × 851, `&lt;` × 6 — e.g.
`PACIFIC GAS &amp; ELEC CO: PCG PRB`), no `|`. The engine unescapes it (`PACIFIC GAS & ELEC CO: PCG PRB`), turns any
control byte or `|` into a space and keeps 60 characters. 155 names contain a word such as HIGH or LOW (`BNY MELLON
HIGH YIELD ETF`) — that is IBKR's text, quoted only inside the hover; our own words never say "high". Names did not
change between two consecutive files.

The parser splits the BYTES on `\n` — never `str.splitlines()`, which also splits on `\x0b`, `\x0c` and `\x1c`–`\x1e`
and would turn one odd byte in a NAME into a "count" rejection of a whole good file.

### Dead rows

IBKR keeps lines for dead tickers: 847 USD rows with a plain 1–5 letter ticker and an EMPTY FIGI; a fee of exactly
0.0000 on 8 names (ADER = `26 CAPITAL ACQUISITION COR-A`, AVGR, PIXY, RVLT, CNEP, DNK, FTNW, WRNT). Some are renamed
`<SYM>.OLD` (`BFIT.OLD`), not all. **Nothing filters them** — such a row prints as IBKR lists it, and the hover names
IBKR's company (`IBKR's row: …`) so a wrong row can be seen. Flagging or hiding one is a rule = HIS CALL #15.

## Measured on ONE Sunday night only — PROVISIONAL

**Everything above was measured on one Sunday night only (2026-11-22, 22:57–23:35 ET).**

- **Cadence — PROVISIONAL.** "About every 15 minutes" rests on three intervals in one hour: stamps `22:57:25` →
  `23:13:02` → `23:28:44` (15 min 37 s, 15 min 42 s). Three reads between 23:04 and 23:10 ET all saw the 22:57:25
  file. No IBKR sentence about the cadence was found.
- **What "absent" means — PROVISIONAL.** The Sunday file had no AVAILABLE 0 row, so IBKR MAY drop a name that has
  nothing to lend. That is an inference from one file. It is **never printed** — the words say only "not in IBKR's
  borrow file".
- **Not measured (weekday RTH):** whether AVAILABLE 0 rows appear, the absent rate, the row churn between two files,
  any connection limit on the shared `shortstock` user.

**A weekday read is owed — once, the first weekday inside RTH after the deploy.** It costs no extra FTP session: one
read-only container probe over the two newest `snap` docs and the `state` doc prints `zero` (rows with AVAILABLE 0),
`n`, the rows that changed between the two files, both stamps, and `state.error` / `state.errors`; the coverage reads
below run the same hour. Then ONE dated line here replaces "PROVISIONAL" for the cadence and for "absent":
`zero > 0` proves a name with nothing to lend can still be listed; `zero == 0` leaves "absent may mean nothing to
lend" an inference.

## Coverage — how many of HIS names the file lists

One saved read each of `/short-interest/reg-sho`, `/chart-maps/gajjala` and `/chart-maps/gajjala-watch` (23:2x ET,
11-22) against the file stamped 22:57:25, with the engine's lookup rule (exact match after the normaliser — no prefix,
no suffix strip):

| Set | n | In IBKR's file | Absent |
|---|---|---|---|
| 🔒 threshold names (the live list, as of 11-20) | 160 | 110 | **50 (31%)** |
| 👀 Watch tiles | 12 | 6 | **6 (50%)** — AKAN, BRNX, INHD, MRM, MSS, SVRE |
| 🚩 board tiles (that one read) | 7 | 5 | 2 — LVWR, NXAT |
| board tiles + Watch tiles | 18 | 10 | **8 (44%)** |
| every `symbol` key in both payloads (strips included) | 29 | 15 | 14 (48%) |
| AKAN, DBGI, LABT, XXII (the 🔒 Watch names at the first 🔒 read) | 4 | 2 | **2 — AKAN, XXII** |

- The 110 listed 🔒 names: median fee 20.1%, only 9 under 5%.
- No name read "unknown" (none of his names carries a separator).
- Worked rows from the same file: DBGI fee 196.2308 / rebate −192.3508 / 100,000 shares; LABT 346.8824 / −343.0024 /
  150,000; WETO 10.0419 / −6.1619 / 350,000; AAPL 0.2500 / 3.6300 / >10,000,000. AKAN, AKANW, DBGIW, XXII: absent.

**How to re-read it** — three single reads on the live engine (after the deploy). `S` is any scratch folder; replace
the email with the owner's:

```bash
S=/tmp/borrow_cover && mkdir -p "$S"
curl -s -H "X-User-Email: OWNER_EMAIL" "http://127.0.0.1:8000/short-interest/reg-sho" -o "$S/rs.json"
python3 -c "import json,sys,urllib.parse; print(urllib.parse.quote(','.join(list(json.load(open(sys.argv[1]))['items'])[:200])))" "$S/rs.json" > "$S/rs_syms.txt"
curl -s -H "X-User-Email: OWNER_EMAIL" "http://127.0.0.1:8000/short-interest/borrow?symbols=$(cat "$S/rs_syms.txt")" | python3 -c "import json,sys,collections; p=json.load(sys.stdin); print(p['status'], p['asked'], dict(collections.Counter(i['state'] for i in p['items'].values())))"
```

Compare listed / absent with the 🔒 row above (110 / 50 on 11-22); do the same with his Watch names. Under the built
default `BR_ABSENT_FORMS` an absent name IS served (label only), so the count of `absent` items is the absent count.

## The four states

Every asked name is one of:

- **listed** — the file has a USD row for it. Fee, rebate and shares are served. **A row with 0 shares available is
  LISTED** and prints `0 avail` — never "absent", never hidden.
- **absent** — no row, and the symbol is plain letters / digits (`^[A-Z0-9]{1,9}$`). **Absent is not zero**: no
  count and no fee are shown. How it draws is `BR_ABSENT_FORMS` (below).
- **unread** — nothing is held (the file could not be read yet, or Mongo is down). The 🎾 label says so; nothing
  else draws.
- **unknown** — the key is ambiguous (two rows normalise to it) or a spelling with a separator misses (`PCG-PB`).
  Omitted — nothing draws. A class / unit / preferred spelling that misses is never "absent".

Exact match only: DBGI listed does not tag DBGIW; `DBG` and `DBGIX` are absent; a CAD or EUR row never stands for a
US ticker. An item is served under the ASKED spelling (`BRK-B`), never IBKR's (`BRK B`).

## The words (served; the frontend types none)

Worked strings from the trimmed fixture (`backend/tests/fixtures/ibkr_borrow/usa_2026-11-22_trimmed.txt`, 22 US
names), read at 2026-11-22 23:04 ET — the contract:

| Name | `chip` (other Gajjala cards) | `short` (📋 table) | `label` (🎾 card) |
|---|---|---|---|
| DBGI | `💸 Borrow 196% · 100K avail` | `💸 196%` | `💸 Borrow 196% a year · 100K shares available · IBKR file 2026.11.22 22:57:25` |
| LABT | `💸 Borrow 347% · 150K avail` | `💸 347%` | `💸 Borrow 347% a year · 150K shares available · IBKR file 2026.11.22 22:57:25` |
| WETO | `💸 Borrow 10% · 350K avail` | `💸 10%` | `💸 Borrow 10% a year · 350K shares available · IBKR file 2026.11.22 22:57:25` |
| AAPL | `💸 Borrow 0.25% · >10M avail` | `💸 0.25%` | `💸 Borrow 0.25% a year · >10M shares available · IBKR file 2026.11.22 22:57:25` |
| RZAI | `💸 Borrow 1,019% · 30K avail` | `💸 1,019%` | (same shape) |
| ADER (fee 0.0000, a dead row) | `💸 Borrow 0% · 300K avail` | `💸 0%` | (same shape) |
| AESG (fee NA) | `💸 Borrow fee n/a · 90 avail` | nothing | `💸 Borrow fee n/a · 90 shares available · IBKR file 2026.11.22 22:57:25` |
| BRK-B (file: `BRK B`) | `💸 Borrow 0.25% · 9.2M avail` | `💸 0.25%` | (same shape) |
| SYNTHETIC zero row (85%, 0 shares) | `💸 Borrow 85% · 0 avail` | `💸 85%` | `💸 Borrow 85% a year · 0 shares available · IBKR file 2026.11.22 22:57:25` |
| AKAN (absent, built default) | nothing | nothing | `💸 not in IBKR's borrow file` |
| AKAN (absent, all three forms) | `💸 not in IBKR's file` | `💸 not in file` | `💸 not in IBKR's borrow file` |
| any name, nothing held | nothing | nothing | `💸 IBKR's borrow file could not be read` |
| DBGI, file 195 min old | `💸 Borrow 196% · 100K avail · file 3h old` | `💸 196% · file 3h old` | `… · IBKR file 2026.11.22 22:57:25 · file 3h old` |

**The hover (`title`)** names IBKR's company — `IBKR's row: <name>` — so a dead or wrong row can be seen:

- DBGI: `Interactive Brokers borrow fee for DBGI (IBKR's row: DIGITAL BRANDS GROUP INC): 196.23% a year (≈ 0.54% a
  day, the yearly rate ÷ 365), 100,000 shares available to borrow, IBKR file stamped 2026.11.22 22:57:25, read 11/22
  23:04 ET. One broker's indicative rate — your broker sets its own fee when you borrow. A data label, not a signal.
  UNMEASURED.`
- ADER carries `(IBKR's row: 26 CAPITAL ACQUISITION COR-A)` — the dead-row case the company name is there for.
- PCG-PRB: `(IBKR's row: PACIFIC GAS & ELEC CO: PCG PRB)` — a real `&`, unescaped.
- AESG: `Interactive Brokers lists AESG (IBKR's row: HARBOR ALPHAEDGE CAP GRW ETF) with 90 shares available to borrow
  and no fee rate (the file says NA), …`
- AKAN: `AKAN is not in IBKR's borrow file stamped 2026.11.22 22:57:25 (read 11/22 23:04 ET, 22 US names). Not in the
  file is not a number — no count is shown. One broker's file — your own broker keeps its own list. A data label, not
  a signal. UNMEASURED.` (On the live file the count is ≈ 19,814 US names.)
- The per-day clause is the yearly rate ÷ 365, plain arithmetic with the divisor in the words; it is omitted when it
  would print 0.00% (AAPL).
- No names doc held → the same titles without the bracket.
- A stale file adds: ` This is the file first read <time> (<age> old) — a newer one could not be read or has not been
  published.`

Formats: a fee under 10% prints with up to two decimals, trailing zeros trimmed (`0.25%`, `0%`); from 10% up it prints
whole with a thousands comma (`196%`, `1,019%`). Shares use the 🩳 formatter (`100K`, `9.2M`, `98`, `0`), `>` in front
for a lower bound. Ages: `N min`, `Nh`, `Nd`.

No tier word, no colour by value, no "high", no "cannot be borrowed", no squeeze promise, no prediction anywhere in
our words — a test pins a FORBIDDEN pattern over every served string and over the fixture's names. The look is
neutral; a stale string is greyed.

## `BR_ABSENT_FORMS` — how an absent name draws (HIS CALL #1)

ONE server constant in `backend/short_interest/borrow.py`. For an absent name each form (`label`, `chip`, `short`) is
served only when it is in `BR_ABSENT_FORMS`; otherwise it is `null` and that surface draws nothing. An empty value
omits the absent item altogether.

| Value | Result |
|---|---|
| `("label",)` — **built default** | `💸 not in IBKR's borrow file` on 🎾 cards only; nothing on other cards or the 📋 table |
| `("label", "chip", "short")` — my recommendation, his word | also `💸 not in IBKR's file` on the other cards and `💸 not in file` in the 📋 table |
| `()` | an absent name draws nothing anywhere |

The price of the default: a missing 💸 on a non-🎾 card can mean "not in the file" OR "not loaded yet".

**The flip is one constant plus one command** — the frontend prints whatever is served and needs no change. Edit
`BR_ABSENT_FORMS`, then regenerate the payload golden and run the suites:

```bash
cd backend && IBKR_BORROW_REGEN_GOLDEN=1 .venv/bin/python -m pytest tests/test_ibkr_borrow_2026_11_22.py -q -p no:cacheprovider
```

The ℹ️ Rules sentence moves with it (built from the constant). The unread state is label-only whatever the value
(HIS CALL #14).

## How it refreshes

- The api **never fetches inline**. `GET /short-interest/borrow?symbols=A,B,C` (first 200 read) reads Mongo only;
  when the file is due it kicks ONE single-flight daemon worker (thread `ibkr-borrow-refresh`, the 🔒 engine's
  shape), with an in-process floor of `BR_KICK_MIN_SEC` between starts. A read that raises answers the unread block
  for every asked name — never a 500.
- **Throttle:** at most one FTP session per `BR_REFRESH_MIN` (15 min). After a first error there is ONE retry
  `BR_ERROR_RETRY_MIN` (5 min) later (`errors < BR_ERROR_STRIKES`, 2); after a second error it is back to every 15 min. A refused connection on
  the shared `shortstock` user is an ordinary error.
- **No page open → no fetch.** The first read after a quiet spell serves the held file with its true age
  (` · file 14h old`) for ~20 s until the follow-up lands — by design.
- The state doc is written with `result: "running"` BEFORE the outside call, and that pre-write CARRIES every held
  key (`good_id`, `good_digest`, `names_id`, `stamp`, `stamp_seen_at`, `checked_at`, `n`, `skipped`, `errors`). While
  a file is held the status never reads `result`, so a read during the 6–10 s of a fetch — or after a failed final
  write — serves exactly what it served before. `errors` goes back to 0 after a good round.

### Status, stale and `keep_sec`

The age is `now − stamp_seen_at` (our clock, the first time we saw the stamp we hold).

| status | when | items | `file` | `keep_sec` | `retry_after_sec` |
|---|---|---|---|---|---|
| `ok` | a file held, age ≤ `BR_STALE_MIN` (60 min) | listed + absent blocks; unknown omitted | the file block | `max(1, 3600 − age in s)` — the seconds until these words would read stale | 20 while refreshing, else null |
| `stale` | a file held, older | the same, every string ending ` · file <age> old`, every title with the stale sentence | the file block | 3600 | the same |
| `pending` | nothing held, no error | `{}` | null | null | 20 while refreshing, else 300 |
| `failed` | nothing held + Mongo down or the last attempt an error; or the read raised | the unread block for every asked name | null | null | as `pending` |

The page (`useBorrow`): ONE borrow GET per page for every mounted chip (flushed on a microtask, chunks of 200), a
symbol already in flight is never re-queued, a cache life of at most 10 min, and an `ok` answer is re-asked at the
moment it would turn stale (its `keep_sec`). A failed re-ask keeps the last read only while inside the served
`keep_sec`; past it the read is dropped and nothing draws — the frontend never prints a "may be old" word of its own.
A failed GET is retried after 60 s. A timer exists only while a valid answer says `refreshing: true` (at most 2
follow-ups).

## The Mongo docs — never purged

Collection `ibkr_borrow` (new). The only operations: `find_one({"_id": …})`, `replace_one(…, upsert=True)` and one
best-effort `create_index([("kind", 1), ("fetched_at", -1)])`. **No delete anywhere.**

```
snap  : {_id: "snap|<fetched_at UTC iso>|<digest[:12]>", kind: "snap", fetched_at, stamp, eof_n, n, skipped, non_usd, na, floor, zero,
         dups, digest, md5_ok, names_id, blob}
names : {_id: "names|<names digest[:16]>", kind: "names", digest, n, first_seen_at, blob}
state : {_id: "state", kind: "state", attempt_at, result: "running"|"found"|"unchanged"|"error", error, errors,
         good_id, good_digest, names_id, stamp, stamp_seen_at, checked_at, n, skipped}
```

- `snap.blob` = zlib of one `SYM|FEE|REBATE|AVAIL` line per USD key, sorted. NAME, CON, ISIN and FIGI are never in it.
- `names` = zlib of `SYM|NAME` lines, content-addressed: written only when a name changes. CON, ISIN and FIGI are
  stored nowhere.
- A new snap is written only when the rows' digest changes; otherwise the round reads `unchanged`. A file whose rows
  match but whose stamp moved updates `stamp` / `stamp_seen_at` only.

**Storage budget (measured).** One snapshot = the four kept fields for 19,814 rows: 523 KB of text → **187 KB**
zlib. The names doc: 564 KB → **208 KB**, only when a name changes (NAME inside every snapshot would have been 367 KB
each). The de-dup rarely fires — every Sunday file differed — so in practice it is **one snapshot per fetch**: at most
96 a day = ≤ 18 MB/day; a 04:00–20:00 session ≈ 12 MB/day ≈ 3 GB a year, never purged (HIS CALL #9).
`fetched_at` is the point-in-time record; history is only as dense as the pages were open, so a later study reads
`fetched_at` and never assumes 15 minutes.

## Where it draws

| Surface | What | Form |
|---|---|---|
| 🎾 Reversal Squeeze card (🚩 5-min and 🧪 Audited) | a line directly after the 🔒 label (directly under the 🩳 label when the name has no 🔒) | `label` |
| every other Gajjala card | a chip in the head chip row, directly after the 🔒 chip (after the 🩳 chip when there is no 🔒) | `chip` |
| 📋 All strategies table | inside the 🩳 cell, after the 🔒 short form | `short` |
| **👀 Watch** | **nothing — by design** | — |

Order on a surface: 🩳 → 🔒 → 💸. One 💸 per card / row. No fault line anywhere — the unread state prints on the 🎾
label only (HIS CALL #14).

**NOT on the 👀 Watch** — his 11-22 word on the Watch was "less info" there, so no Watch file is edited and a source
guard pins it. Turning it on (HIS CALL #2) is exactly this and nothing else, a follow-up change:

- `GajjalaWatchTile.tsx`: the `GgBorrow` import, and after the 🔒 short chip
  ``{siNote ? <GgBorrowChip symbol={row.symbol} testid={`ggw-brw-${row.symbol}`} className="ggw-chip" form="short" /> : null}``;
- `ggBorrow.css`: `@media (min-width: 641px) { .ggw-grid--fit .ggw-chip.gg-brw { flex: 0 1 auto; min-width: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } }`;
- tests `GajjalaWatchTile.borrow.test.tsx` + `GajjalaWatchBoard.borrow.test.tsx`; the "no Watch file names GgBorrow"
  guard flips; `BR_SURFACES_TEXT` gains the Watch. The Watch reads the `short` form, so an absent name follows the
  📋 table's switch there.

## What it never does

No gate, sort, filter, rank, push, A+ grade, lane input, threshold, tier, colour by value, crontab line, notification
pref or broker key reads it. No edit under `backend/chart_maps/`, `backend/push/`, `backend/trading/` (a test pins
that no file there names `ibkr_borrow` or `short_interest.borrow`); `backend/crontab` has no `borrow`. It never hides a
card. It never prints a zero for a name IBKR does not list. GG's verified rule U10 stands: no short-interest
threshold or filter anywhere — this read is not one. Tests never reach IBKR: the one outside call goes through the
module seam `borrow._ftp`, refused for the whole session in `backend/tests/conftest.py`.

## Constants

The code is the source; if this table and `backend/short_interest/borrow.py` / `frontend/src/hooks/useBorrow.ts`
ever disagree, the code wins. **MINE** = a number or word I chose; none is a trading threshold.

| Constant | Value | Whose |
|---|---|---|
| `GLYPH` / `WORD` | 💸 / `Borrow` | **MINE** (HIS CALL #5) |
| `SOURCE_NAME` / `SOURCE_SHORT` | `Interactive Brokers` / `IBKR` | the source's name |
| `KIND` / `BR_COLL` / `API_PATH` | `ibkr_borrow` / `ibkr_borrow` / `/short-interest/borrow` | **MINE** |
| `BR_FTP_HOST` / `BR_FTP_PORT` | `ftp2.interactivebrokers.com` / 21 | IBKR's (published) |
| `BR_FTP_USER` / `BR_FTP_PASSWORD` | `shortstock` / empty | IBKR's (published) |
| `BR_FILE` / `BR_MD5_FILE` | `usa.txt` / `usa.txt.md5` | IBKR's |
| `BR_FETCH_NAMES` | md5, file, md5 (one session) | **MINE** |
| `BR_HEADER` | `#SYM\|CUR\|NAME\|CON\|ISIN\|REBATERATE\|FEERATE\|AVAILABLE\|FIGI\|` | IBKR's (measured) |
| `BR_CURRENCY` | `USD` | **MINE** |
| `BR_REFRESH_MIN` | 15 | **MINE** |
| `BR_ERROR_RETRY_MIN` / `BR_ERROR_STRIKES` | 5 / 2 | **MINE** |
| `BR_KICK_MIN_SEC` | 60 | **MINE** |
| `BR_FTP_TIMEOUT_SEC` / `BR_FETCH_BUDGET_SEC` | 25 / 60 | **MINE** |
| `BR_STALE_MIN` | 60 | **MINE** |
| `BR_RETRY_AFTER_SEC` | 20 | **MINE** |
| `BR_MAX_BYTES` / `BR_MAX_ROWS` | 8,000,000 / 60,000 | **MINE** |
| `BR_MIN_ROWS` / `BR_MAX_SKIPPED_ROWS` | 5,000 / 200 | **MINE** |
| `BR_NAME_MAX` | 60 | IBKR's NAME cell, measured max |
| `BR_FEE_WHOLE_FROM` | 10.0 | **MINE** — a display format break only |
| `BR_DAYS_PER_YEAR` | 365 | **MINE** — plain arithmetic, printed in the words (HIS CALL #7) |
| `BR_FORMS` | `label`, `chip`, `short` | **MINE** |
| `BR_ABSENT_FORMS` | `("label",)` | **MINE** default — HIS CALL #1 |
| `BR_SURFACES_TEXT` | `Gajjala cards and the 📋 All strategies table` | **MINE** (no Watch — HIS CALL #2) |
| `MAP_MAX_SYMBOLS` | 200 (= `read.MAP_MAX_SYMBOLS`, imported) | the 🩳 cap, reused |
| FE `BR_CHUNK` | 200 (must equal the served `max_symbols`) | **MINE** |
| FE `BR_TTL_MS` / `BR_RETRY_MS` | 600000 / 60000 | **MINE** (the 🩳 / 🔒 hooks' values) |
| FE `BR_FOLLOWUP_MAX` / `BR_FOLLOWUP_MIN_MS` / `BR_FOLLOWUP_MAX_MS` | 2 / 5000 / 120000 | **MINE** |

## ℹ️ Rules

The ℹ️ 🩳 section is at its cap of 8 picks, so the 💸 sentence **folds into the "Short VOLUME …" pick** (index 6),
before the 🔒 pick (which stays last). It is built by `borrow.rules_pick()` from the constants above, never retyped;
a failure leaves the pick as it was. The default text:

> 💸 Borrow = Interactive Brokers' public shortable-shares file: the yearly borrow fee rate and the shares it shows
> available to lend, per US ticker. Re-read at most once every 15 minutes while a Gajjala page is open; the hover
> carries IBKR's file stamp, the time it was read and the company name on IBKR's row, and the chip says how old the
> file is once it is more than 60 minutes old. A name that is not in the file reads '💸 not in IBKR's borrow file' on
> 🎾 cards only — never a zero. One broker's indicative rate — your broker sets its own fee when you borrow. Tags
> Gajjala cards and the 📋 All strategies table only; it gates, sorts and pushes nothing. UNMEASURED.

With all three absent forms the absent sentence reads `… on 🎾 cards, the other Gajjala cards and the 📋 table —
never a zero.` Its own ℹ️ section is HIS CALL #12.

## UNMEASURED

Nothing in the repo measures borrow fee or shares available against outcomes. The 11-18 multi-day runners report
listed "borrow fee / shares available to short" as NOT AVAILABLE; `docs/research/swing_entry_exit_signals_2026-05-29.md`
is a literature note, not a measurement. Adjacent nulls (SI × cradle 11-17, 🔎 big movers 11-09) are never to be
quoted as support. The prior on borrow fee as a signal is null → **this ships as a data label, UNMEASURED.** The
snapshots are kept from day one so a pre-registered, point-in-time study is possible later — only on his word.

## HIS CALL — built to a default, or not built

1. **Names IBKR does not list — AKAN is one.** Measured 11-22: 50 of 160 🔒 names, 6 of his 12 Watch tiles, AKAN and
   XXII among them. Built default: `💸 not in IBKR's borrow file` on the 🎾 card label only, nothing elsewhere — so a
   missing 💸 can mean "not in the file" OR "not loaded". My recommendation: show it everywhere the 💸 draws
   (`💸 not in IBKR's file` on cards, `💸 not in file` in the 📋 table). One constant, `BR_ABSENT_FORMS`. The words
   are his.
2. **👀 Watch.** Built default: NO 💸 on the Watch (his 11-22 word: less info there). Yes = the Watch section above,
   `💸 196%` in the tile head: 6 of 12 tiles would carry a number today, the other 6 nothing unless #1 = everywhere.
3. **"Last listed <stamp> at N%"** for a name that has dropped out of the file, read from the stored history. Not
   built.
4. **Which names.** Default: every name on these surfaces. Only names that carry 🔒 (or 🩳) is his call.
5. **Words and glyph.** 💸, "Borrow", `avail`, the absent sentences, `IBKR's row: <company>` in the hover; the chip
   does not name IBKR (the hover does) — `💸 IBKR borrow 196%` is his call.
6. **Any tier, colour or "high" word, any threshold** — an invented number; and any sort, filter, push, A+ or lane
   input. Not built.
7. **The per-day figure.** Default: yearly rate ÷ 365, printed as plain arithmetic with the divisor in the words.
   IBKR's own billing day-count is unverified — drop it or change the divisor on his word.
8. **Engine numbers — all mine:** refresh 15 min, stale past 60 min, one error retry after 5 min, 25 s timeout.
9. **History.** Default: one snapshot per fetch (the de-dup rarely fires), never purged — about 12 MB per open
   session day, ≤ 18 MB/day, ≈ 3 GB a year. Hourly snapshots or a purge window is his call.
10. **A scheduled refresh** (so history has no gaps and the first read is never stale) = a crontab line = his step.
    Not built.
11. **Scope.** Gajjala cards and the 📋 table only. The ticker page, other boards, the rebate rate, non-US files: not
    built.
12. **ℹ️ home.** Default: folded into the 🩳 section's short-volume pick. Its own ℹ️ section is his call.
13. **Measurement.** UNMEASURED. A pre-registered study of borrow fee × 🎾 outcomes only on his word.
14. **No fault line** on the boards (the unread state prints on the 🎾 label only). A line above the grid is his call.
15. **Dead rows.** A row IBKR still lists for a dead ticker (no FIGI, fee exactly 0) prints as IBKR lists it; the
    hover names the company. Flagging or hiding such rows is a rule, so it is his call. Not built.

## How to check

One read of the served payload (authed; replace the email with the owner's). The first answer after a deploy may say
`refreshing: true` with no items; ONE more read ~20 s later carries them:

```bash
rtk proxy curl -s -H "X-User-Email: OWNER_EMAIL" "http://127.0.0.1:8000/short-interest/borrow?symbols=DBGI,LABT,WETO,AAPL,AKAN,DBGIW"
```

- `status: "ok"`, `file.stamp` (IBKR's, verbatim), `file.names` ≈ 19.8K, `keep_sec`, and DBGI's `name`.
- AKAN and DBGIW: `state: "absent"`, `fee_pct` / `available` null — never 0.
- A third read inside 15 minutes: `state.attempt_at` in Mongo has not moved (no second FTP session).

The real payload through the real component (save the JSON first):

```bash
IBKR_BORROW_LIVE_PAYLOAD=/abs/path/to/payload.json rtk proxy npx vitest run src/components/GgBorrow.payload.test.tsx
```

Coverage: the three reads under "Coverage" above. The weekday read: the section "Measured on ONE Sunday night only".

On https://pounce.ajaykandakatla.dev → 🚩 Gajjala: a 🎾 card shows the 💸 line under its 🔒 / 🩳 line (a name IBKR
does not list: `💸 not in IBKR's borrow file`); another card shows the chip, and its hover names IBKR's company; the
📋 table's 🩳 cell shows the short form. **The 👀 Watch shows NO 💸 — by design until his word (HIS CALL #2).**

Tests: `backend/tests/test_ibkr_borrow_2026_11_22.py` (engine, route, ℹ️ fold, NEGATIVES; golden
`backend/tests/fixtures/ibkr_borrow_payload_2026_11_22.json`), the `borrow`, `useBorrow`, `GgBorrow*`,
`GajjalaBoard.borrow` and `GgAllTable.borrow` suites in `frontend/src/`.
