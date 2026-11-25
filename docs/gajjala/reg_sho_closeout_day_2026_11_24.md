# 🔒 Reg SHO close-out day on the "Hard to borrow" tag (2026-11-24)

The existing 🔒 tag (`docs/gajjala/hard_to_borrow_reg_sho_2026_11_22.md`) now also counts how many settlement days in
a row a name has been on its exchange's Reg SHO threshold list, and prints the date of day 13. **Display only. PAPER
only. UNMEASURED.** Same four served strings, same placements, no frontend production change.

## The ask, verbatim

Ajay 2026-11-23/24 ~23:30 ET, in order:

> "Also is there a better way to check short trading expiry? I do see that many in reversal squeeze tab have been bounding by EOD today.. Like MSS, GMEX, AKAN to some degree. SMTK seems imminent.. I would like to guess when that would be"

The main session answered in chat: shorts have no expiry; the one DATED mechanism is Reg SHO Rule 203(b)(3).
**That answer was incomplete** — Rule 204 and the Rule 144 leg are dated too (below). The sentence stays here as the
record of what he was told. Then:

> "I need to know when it would like to Potentially squeeze.."

> "Add a tag with date in it.."

## Three corrections to what he was told in chat

1. **GMEX's day 13 is Fri 11/27, not Wed 11/25.** Bank holidays are not settlement days (Veterans Day 11-11 does not
   count). Counted the other way (from the open at which each list takes effect) it is Mon 11/30 — HIS CALL #2.
   SMTK: day 18 on the 11/20 list, day 13 was Fri 11/13 (the chat said day 19, ~11/12).
2. **The date is the Rule 203(b)(3) backstop, not the day buying happens.** Rule 204 comes first: a fail in any stock
   is due for close-out 1 to 3 settlement days after settlement, and the SEC staff say fails generally do not reach
   13 consecutive settlement days. "The one dated mechanism" was incomplete.
3. **The tag gives a future date for GMEX and AKAN only.** SMTK's date (Fri 11/13) is past; MSS is on no list read, so
   it has no tag at all.

## What the tag now says

Six states, decided by the backend from the per-date list docs it already keeps (`run.state`):

| `run.state` | When | `chip` / `label` tail | `short` |
|---|---|---|---|
| `counting` | on the list `n` straight settlement days, `n` < 13, run start known | ` · day n of 13 · close-out day <date> if it stays on` | `🔒 close-out <date> · day n of 13` |
| `reached` | `n` == 13 — day 13 is this list's own date | ` · day 13 of 13 · close-out day <date>` | `🔒 close-out <date> · day 13 of 13` |
| `passed` | `n` > 13, run start known | chip ` · day n · close-out day passed <date> · still on`; label ends `· still on the list` | `🔒 close-out passed <date> · day n` |
| `passed_open` | at least 13 days for sure, first day not known (on every list in the window, or a hole after ≥ 13 counted) | chip ` · day n+ · close-out day passed · still on`; label ends `· still on the list` | `🔒 close-out passed · day n+` |
| `unknown` | a day's list was not read before the run ended or reached 13 (also `n` == 0) | ` · day count unknown` | **today's `short`, unchanged** (`🔒 Hard to borrow · 11/20`) |

A stale list still appends ` · stale` LAST on chip, short and label, and the title still ends with the stale sentence.
The `short` form leads with the date, so the desktop 👀 Watch ellipsis cuts the day count, never the date. The card
chip and the 🎾 label carry `if it stays on` because the phone has no hover (HIS CALL #5).

The title = today's title sentence (byte-identical, as the prefix) + a tail by state. Every dated tail ends with the
same four sentences: the Rule 204 sentence, `Fails to deliver only, not every short position.`,
`A rule date — it says nothing about price.`, `Not advice.` The `unknown` tail ends with `Not advice.` only.

### Worked strings — the contract (Nasdaq list of 2026-11-20, history read)

Computed on the host venv from the worktree's own calendar and words, not typed. Character counts in brackets.

**GMEX — `counting`, day 9**

- chip [100] `🔒 Hard to borrow · threshold security · 11/20 · day 9 of 13 · close-out day Fri 11/27 if it stays on`
- short [35] `🔒 close-out Fri 11/27 · day 9 of 13`
- label [124] `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 9 of 13 · close-out day Fri 11/27 if it stays on`
- title tail [670] ` On the list 9 straight settlement days since 11/9. Day 13 = Fri 11/27 if it stays on (Mon 11/30 if counted from each list's next open). After day 13, Rule 203(b)(3) makes a clearing firm buy shares to close out a fail to deliver it carried on every one of those days; the buying may come from day 11 (Tue 11/24) and must start by the next open (SEC staff FAQ 6.5, 6.7). Rule 204 already requires a fail in any stock to be closed out 1 to 3 settlement days after settlement, so fails generally do not last 13 (SEC staff); for a Rule 144 sale the count is 35, not 13. Fails to deliver only, not every short position. A rule date — it says nothing about price. Not advice.`

**SMTK — `passed`, day 18**

- chip [98] `🔒 Hard to borrow · threshold security · 11/20 · day 18 · close-out day passed Fri 11/13 · still on`
- short [37] `🔒 close-out passed Fri 11/13 · day 18`
- label [131] `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 18 · close-out day passed Fri 11/13 · still on the list`
- title tail [781] ` On the list 18 straight settlement days since 10/27. Day 13 was Fri 11/13 (Mon 11/16 if counted from each list's next open); it is still on the list 5 settlement days later. After day 13, Rule 203(b)(3) makes a clearing firm buy shares to close out a fail to deliver it carried on every one of those days. Staying listed means the total of fails is still over the level, not that any one fail is that old — a name leaves a list only after 5 straight settlement days back under it. Rule 204 already requires a fail in any stock to be closed out 1 to 3 settlement days after settlement, so fails generally do not last 13 (SEC staff); for a Rule 144 sale the count is 35, not 13. Fails to deliver only, not every short position. A rule date — it says nothing about price. Not advice.`

**AKAN — `counting`, day 1**

- chip [99] `🔒 Hard to borrow · threshold security · 11/20 · day 1 of 13 · close-out day Wed 12/9 if it stays on`
- short [34] `🔒 close-out Wed 12/9 · day 1 of 13`
- label [123] `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 1 of 13 · close-out day Wed 12/9 if it stays on`
- title tail [668] ` On the list 1 straight settlement day since 11/20. Day 13 = Wed 12/9 if it stays on (Thu 12/10 if counted from each list's next open). After day 13, Rule 203(b)(3) makes a clearing firm buy shares to close out a fail to deliver it carried on every one of those days; the buying may come from day 11 (Mon 12/7) and must start by the next open (SEC staff FAQ 6.5, 6.7). Rule 204 already requires a fail in any stock to be closed out 1 to 3 settlement days after settlement, so fails generally do not last 13 (SEC staff); for a Rule 144 sale the count is 35, not 13. Fails to deliver only, not every short position. A rule date — it says nothing about price. Not advice.`

**`unknown`** (GMEX with the 11/18 list not read → `days` 2, `missing` 2026-11-18)

- chip [65] `🔒 Hard to borrow · threshold security · 11/20 · day count unknown`
- short [24] `🔒 Hard to borrow · 11/20`
- label [89] `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day count unknown`
- title tail [87] ` Days on the list: not known — the Nasdaq list for 11/18 has not been read. Not advice.`

**`passed_open`, on every list of the window** (30 settlement days, back to 10/8)

- chip `🔒 Hard to borrow · threshold security · 11/20 · day 30+ · close-out day passed · still on`
- short `🔒 close-out passed · day 30+`
- label `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 30+ · close-out day passed · still on the list`
- title tail ` On every list read for the last 30 settlement days (back to 10/8), so day 13 has passed; its date is not known. After day 13, Rule 203(b)(3) makes a clearing firm buy shares to close out a fail to deliver it carried on every one of those days.` + the four tail sentences.

**`passed_open`, a hole after ≥ 13 counted** (SMTK with the 10/28 list not read → `days` 16)

- chip [89] `🔒 Hard to borrow · threshold security · 11/20 · day 16+ · close-out day passed · still on`
- short [28] `🔒 close-out passed · day 16+`
- title tail starts ` On the list at least 16 straight settlement days, so day 13 has passed; its date is not known — the Nasdaq list for 10/28 has not been read.` then the rule sentence and the four tail sentences.

**`reached`** (a synthetic run of exactly 13 ending 11/20, started 11/3)

- chip `🔒 Hard to borrow · threshold security · 11/20 · day 13 of 13 · close-out day Fri 11/20`
- short `🔒 close-out Fri 11/20 · day 13 of 13`
- label `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 13 of 13 · close-out day Fri 11/20`
- title tail starts ` On the list 13 straight settlement days since 11/3. Day 13 = Fri 11/20, this list's date (Mon 11/23 if counted from each list's next open). After day 13, …` (the buying window names Wed 11/18).

Lengths, measured on the worked set: the longest served title is **1,280** characters (SMTK `passed` + the stale
sentence); GMEX is 1,084 (1,169 stale). The test bound `TITLE_MAX = 1350` is a regression bound, not an engine
constant. Whether a native browser tooltip shows 1,280 characters whole is NOT verified (checked before deploy, below).

## What the date is — and what it is not

### The rule, its sources, and how each was read

| Source | What it says | Read |
|---|---|---|
| **17 CFR 242.204(a)** | A fail in **any equity security**, long or short sale: close out "by no later than the beginning of regular trading hours on the settlement day following the settlement date … by borrowing or purchasing". | A |
| **17 CFR 242.204(a)(1), (a)(3)** | A long sale, or bona fide market making: "the third consecutive settlement day following the settlement date". | A |
| **17 CFR 242.204(a)(2)** | A deemed-to-own sale (restrictions on delivery): "the thirty-fifth consecutive calendar day following the trade date". | A |
| **SEC staff FAQ, the note at the head of section 6** | "Although as a result of compliance with Rule 204" … "generally fail to deliver positions will not remain for 13 consecutive settlement days" … "the requirement to close-out such position under Rule 203(b)(3) remains in effect". | B |
| 17 CFR 242.203(b)(3) | A clearing-agency participant with a fail to deliver "in a threshold security for thirteen consecutive settlement days … shall immediately thereafter close out the fail to deliver position by purchasing securities of like kind and quantity". | A |
| **17 CFR 242.203(b)(3)(ii)** | A threshold-security fail "that was sold pursuant to § 230.144 … for thirty-five consecutive settlement days" → the same duty at 35, not 13. | A |
| 17 CFR 242.203(c)(5) | Settlement day = "any business day on which deliveries of securities and payments of money may be made through the facilities of a registered clearing agency". | A |
| 17 CFR 242.203(c)(6)(iii) | A security "shall cease to be a threshold security if the aggregate fail to deliver position … does not exceed the level … for five consecutive settlement days". | A |
| SEC staff FAQ 6.1 | Lists are public at or before midnight each trading day; "these threshold lists are in effect for the open of trading immediately following the posting". | B |
| FAQ 6.3 | "The close-out and pre-borrow requirements of Rule 203(b)(3) are based on settlement days, not trade days"; they "apply if a security is a threshold security for 13 consecutive settlement days" and the participant has open fails on each of those days. Off the list before day 13 → no duty. | B |
| FAQ 6.5 | The close-out "must be initiated no later than the beginning of trading on the trading day following the 13th" consecutive settlement day. | B |
| FAQ 6.7 | A purchase counts on its execution day only if "the purchase is executed on settlement day 11, 12 or 13"; the reading "does not apply to purchases made on settlement day 10 or earlier". | B |
| FAQ 6.8 (worked example) | Settlement day 1 is the day of the participant's "initial increase in its fail to deliver position" — the count runs **per firm, from its own fail**. | B |
| FAQ 7.3 | "NSCC does not have the authority to execute buy-ins on behalf of its members." → the rule's word is **close-out**. | B |

How read. **A** = the law.cornell.edu pages of 17 CFR 242.203 and 242.204, saved and re-extracted on 2026-11-23; the
quotes are copied from that text. **B** = `sec.gov/divisions/marketreg/mrfaqregsho1204.htm`, read on 2026-11-23
through a summarising fetch (an anonymous client was answered 403): the quoted fragments are verbatim, each under 125
characters; everything outside quotes is paraphrase; the page reads "Last Reviewed or Updated: Nov. 17, 2026".
The hover cites "SEC staff FAQ 6.5, 6.7" and "(SEC staff)", so the main session opens that page in a browser and
checks 6.1, 6.5, 6.7 and the section-6 note by eye before the words ship.

### Three limits, each served or a HIS CALL

1. **Rule 204 comes first.** A fail in any stock is due for close-out — by borrowing OR buying — 1 to 3 settlement days
   after its settlement date. Rule 203(b)(3) is what remains for a fail that is still open on day 13 anyway; by the
   staff's own note, generally none is. A name can sit on a list for weeks with no single fail that old, because the
   list measures the TOTAL of all firms' fails each day. So day 13 is a **backstop date**. A Rule 144 sale gets 35
   settlement days, not 13.
2. **The app sees the list, never the fails.** The 13 days run per firm, with a fail open on each day (FAQ 6.3, 6.8).
   Day 13 of the list run is the first day a Rule 203(b)(3) duty CAN exist in this run — never a day on which buying
   must occur. Buying that counts may come on day 11, 12 or 13 (FAQ 6.7), or not at all.
3. **Day 1 is a convention.** Built: the list dated D counts as day D. By FAQ 6.1 that list takes effect at the next
   open, so the count may run one settlement day later. Nothing read settles it → the hover prints both dates
   (`day13` and `day13_late`) and the choice is HIS CALL #2.

## Settlement days are not trading days (this changes the dates)

**MEASURED.** Veterans Day (Wed 2026-11-11) and Columbus Day (Mon 2026-10-12): the exchanges trade, banks are closed.
By Rule 203(c)(5) a settlement day needs payments of money to be possible.

- Outside sources, read as SEARCH SNIPPETS on 11-23 (the notices themselves were not opened): a DTCC notice for
  Columbus Day 2020 — "Monday, October 12 is not a valid settlement date"; FINRA Notice 99-88 on Veterans Day — "it
  will not be a settlement date because many of the nation's banking institutions will be closed". Caveat: DTCC's
  2026 schedule lists NSCC as open on both days with a service-restriction footnote; no 2026 notice saying "not a
  settlement date" was found. The measured files below carry the decision.
- **NYSE published no list** for 10-12 and 11-11 (all three NYSE 11-11 fixtures are header + trailer, zero rows).
- **Nasdaq's 11-11 file carries exactly the 11-10 names** (`backend/tests/fixtures/reg_sho/nasdaq_20261110.txt` /
  `nasdaq_20261111.txt`: 76 = 76, symmetric difference empty), and **its 10-12 file carries exactly the 10-09 names**
  (two single GETs on 11-23: 72 = 72, identical; trailers `20261009230024` / `20261012230005`). A normal day moves
  names (11-19 → 11-20: +AKAN, +ACONW).
- Re-checked independently on the host venv on 11-23: same counts, same empty difference.
- Consequence: counting TRADING days (the build brief's wording, and what the chat did) counts 11-11 as a day. It is
  not one. It would also leave every NYSE-listed name "unknown" for ever across 10-12 / 11-11 (no list exists there).

Settlement days = house business days (the ONE holiday list, `market_hours.reminder.ALL_HOLIDAYS`, read through
`short_interest.read.is_business_day`) minus the two bank holidays on which the market trades. The two are fixed rules,
never typed dates: the second Monday of October; November 11, moved to Monday when it falls on a Sunday and dropped
when it falls on a Saturday. The half day Fri 11-27 is a business day → it counts. Thanksgiving 11-26 is closed → it
does not.

### The worked table that corrects the chat

Computed from the Nasdaq files 10-13 … 11-20 (DERIVED fixture
`backend/tests/fixtures/reg_sho_history/nasdaq_membership_2026_10_13_to_11_20.json`: membership of 3 names read from
the real files, not a verbatim file).

| Name | Run starts | Settlement days through 11/20 | Day 11 | **Day 13 (as built)** | Day 13 counted from each list's next open | What the chat said (trading days) |
|---|---|---|---|---|---|---|
| SMTK | 10-27 | **18** | Tue 11/10 | **Fri 11/13** | Mon 11/16 | 19 days, day 13 ≈ 11/12 |
| GMEX | 11-09 (on 10-26…10-30, OFF 11-02…11-06, back 11-09) | **9** | Tue 11/24 | **Fri 11/27** | Mon 11/30 | 10 days, day 13 = **Wed 11/25** |
| AKAN | 11-20 | 1 | Mon 12/7 | Wed 12/9 | Thu 12/10 | day 13 = Wed 12/9 (same) |
| MSS | — | on no list read: Nasdaq 28 days; absent from the NYSE / Cboe fixtures of 11-10, 11-19, 11-20 | — | — | — | — |

GMEX's earlier stretch (10-26…10-30) is NOT added: a read list without the name ends the run.

### Which of his four names the tag answers

**GMEX (Fri 11/27) and AKAN (Wed 12/9) get a future date.** SMTK's date (Fri 11/13) is ten days past — the tag says
`close-out day passed Fri 11/13 · still on`. MSS is on no list read → no tag at all.

### "Still listed past day 13" proves nothing

List membership cannot show whether any close-out happened. By Rule 203(c)(6)(iii) a name stays listed at least 5
more settlement days even after every old fail is closed, and under Rule 204 new fails can replace old ones every day.
So no served string claims that a name passed its date with or without a move, and no count of "names past their
date and still listed" is served (it would be survivorship: a name that left after its date is invisible). A price
claim needs price data and a pre-registered study (HIS CALL #9).

## The history

The per-date list docs already existed and are never purged (`reg_sho_threshold`, one doc per market per trade date).
What was missing was the older dates and any read of them. No second collection.

- **Window**: `RS_HIST_SETTLEMENT_DAYS` = 30 settlement days of lists, behind and including the newest one, per market.
  Behind the 11/20 list the window ends 10/8. If the newest Nasdaq file is dated a bank holiday (Nasdaq publishes one),
  the count runs through the settlement day before it.
- **A day whose list was not read is never counted either way**: not as on, not as off. A run that reaches an unread
  day before it ends reads `unknown` (or `passed_open` when ≥ 13 days were already counted). Unread = never fetched,
  a recorded hole, an unreadable doc, or a zero-row list not yet confirmed by its second read.
- **Backfilled once, by the same single worker**, right AFTER the latest-list round (`refresh_due` then
  `backfill_history`, each in its own `try`; `refresh_due` itself is untouched, so a refresh round still asks exactly
  the five pinned URLs). The api never fetches inline; the read only kicks the worker. Outside calls go only through
  the engine's own `fetch_source` / `fetch_market` (the existing URLs, `HTTP_HEADERS`, `RS_HTTP_TIMEOUT_SEC`,
  `allow_redirects=False`). Bank holidays and closed days are never in the window, so no URL for 10-12, 11-11 or 11-26
  is ever built by the backfill.
- **Order**: newest date first, registry order inside a date, every fetch before every confirm; a never-asked item
  always sorts before a re-ask, so one bad date cannot starve the rest of its source.
- **`backfilled: true` = NOT point-in-time.** A backfilled list doc's `fetched_at` is the backfill time, days after the
  trade date. A later study must exclude these docs or treat them as hindsight. The backfill never overwrites an
  existing list doc (`fetched_at` of a held doc stays the first write).
- **Zero-row history lists** follow the 11-22 two-read rule: believed only after a second read at least `RS_RETRY_MIN`
  later (one confirm GET for that market and date). Until then that day is unread for the count.

### Hole docs

```
fetch hole   : {_id: "nolist|<source>|<YYYY-MM-DD>",         kind: "nolist", op: "fetch",   source, market: None,
                trade_date, result: "missing" | "error", error, tries, asked_at}
confirm hole : {_id: "nolist|confirm|<market>|<YYYY-MM-DD>", kind: "nolist", op: "confirm", source, market,
                trade_date, result: "error", error, tries, asked_at}
```

A `missing` answer (one of the three measured "no list" answers) writes a `missing` fetch hole; an error writes an
`error` fetch hole; a confirm re-read that does not come back `found` writes a confirm hole. No delete anywhere.

### The one retry rule (fetches and confirms alike)

- No hole → due. An unreadable `asked_at` → due. A non-int `tries` reads as 0.
- `error`: due after `RS_RETRY_MIN` (30 min) while `tries` < `RS_HIST_MAX_TRIES` (3); after that, due every
  `RS_HIST_REASK_MIN` (1440 min, daily). **Never final** — a blocked hour costs a day, not six weeks.
- `missing`: due every `RS_HIST_REASK_MIN` while `tries` < `RS_HIST_MAX_TRIES`; after that final (three "no file"
  answers a day apart).

### Cool-down, pacing, breaker

- **Cool-down**: a source with ANY `error` hole (fetch or confirm) asked less than `RS_RETRY_MIN` ago contributes
  nothing to the todo — no fetch and no confirm.
- **One failing item per source per round**: an error (fetch or confirm) puts that source in the round's skip set,
  so a round makes at most one failing item per source (≤ 3 GETs for the NYSE group).
- **Pacing**: a round starts no further item once `RS_HIST_MAX_GETS` (40) outside calls are made (overshoot ≤ 2: one
  NYSE group) or `RS_HIST_BUDGET_SEC` (45 s) has passed; `RS_HIST_PAUSE_SEC` (0.25 s) between two items; worker starts
  stay `RS_KICK_MIN_SEC` (60 s) apart.
- **Breaker**: a Mongo write that raises (list, hole or confirmation) ends the round and stops the history for
  `RS_RETRY_MIN` (in-process; reset by an api restart). Without it a `found` answer whose write fails would be
  re-fetched every round with no end.
- **No endless re-read**: `refreshing` is true while only the history is pending ONLY when a worker is running or
  starting or its floor is waiting; `retry_after_sec` is then `RS_RETRY_AFTER_SEC` (20 s) when the read started or
  sees a worker, and `RS_KICK_MIN_SEC` (60 s) only when the floor refused it (one re-read per worker round). With
  every remaining hole final or waiting, the breaker set, or a thread that cannot start, it serves `refreshing: false`.

### Size — an ESTIMATE

29 dates × (Nasdaq 1 + NYSE 3 + Cboe 1) ≈ **145 fetch GETs once** (87 of them to nyse.com), about 4 rounds, **plus one
confirm GET per zero-row market-day** 30 minutes later (the NYSE market had 0 rows on 11-10; how many such days sit in
the window is not known until the first real run). The critic read the 30th window day (2026-10-08) once per source
through `fetch_source`: Nasdaq 77, NYSE 2 / 2 / 18, Cboe 48 — all parse, so the window is fetchable. After the
backfill: nothing but the one new file a night the latest path already fetches, and the due re-asks of open holes.
`backfill_history` returns `calls`, `found`, `confirmed`, `holes`, `seconds` per round.

**MEASURED:** … (filled by the main session from the pre-deploy real run)

## The guards

- **A history failure reads `day count unknown`, never a missing tag.** `load_history` + `history_todo` run inside one
  `try`; `run_for` runs inside a `try` per item; `tag_block` rebuilds with the `unknown` run on any exception. A window
  doc with `symbols: None` reads as "not read"; a hole doc with a non-int `tries` does not raise. The worst case is
  every tag reading `day count unknown` with `closeout.ok: false`; the tags, the fault line, `sources` and `check` are
  untouched, and the route never answers the fault payload because of the history.
- The fault line keeps reading the latest-list `refreshing` only; the history never raises it.
- No served string contains the words the tests ban: the old `FORBIDDEN` list (squeeze, fee, predict, …) and the new
  one (no word that promises a price move, no "buy-in", no claim the date is a first possible day). The word
  "squeeze" stays banned on this tag's served text (HIS CALL #8).

## Payload keys (additive; nothing renamed or removed)

- Each item: `"run"` = `{"state", "days", "start", "through", "window_from", "day11", "day13", "day13_late",
  "start_by", "missing", "rule_days", "first_buy_day"}` — str / int / None only. For `passed_open` and `unknown`,
  `days` is a floor ("at least") and the four dates are None.
- Top level: `"closeout"` = `{"rule": "SEC Regulation SHO Rule 203(b)(3)", "rule_days": 13, "first_buy_day": 11,
  "ok": bool, "history": {"window_days": 30, "read": {mkt: int}, "not_read": {mkt: [iso, … newest first, at most
  RS_HIST_NOT_READ_MAX]}, "pending": bool}}`; `"history": null` when `ok` is false. No `text`, `past_n` or `counted_n`.
- `fault_payload()`: `"closeout": null`.
- `refreshing` may now be true while only the history is being read; `retry_after_sec` is then `RS_RETRY_AFTER_SEC`
  (20 s) when the read started or sees a worker, `RS_KICK_MIN_SEC` (60 s) when the floor refused it. `check`, `sources`, `fault_text`, `complete`, `as_of`, `n`, `note` unchanged.
- The frontend's `parseRegSho` drops `run` and `closeout` (unknown keys); it prints the four served strings only.

## ℹ️ Rules

Folded into the existing 🔒 pick (the 🩳 section is at its cap of 8), built from the constants:

> The tag also counts the straight settlement days a name has been on its list and dates day 13: after it, SEC Regulation SHO Rule 203(b)(3) makes a clearing firm buy shares to close out a fail to deliver it carried on every one of those days (the buying may come from day 11). Rule 204 already requires a fail in any stock to be closed out 1 to 3 settlement days after settlement, so fails generally do not last 13 (SEC staff); for a Rule 144 sale the count is 35, not 13. Bank holidays (Columbus Day and Veterans Day) are not settlement days (Rule 203(c)(5)). A list takes effect at the next open, so the date can be one settlement day later. A rule date — it says nothing about price.

The pick stays last; 8 picks stay 8; the whole pick is ~1,500 characters.

## Constants

The code is the source; if this table and `backend/short_interest/reg_sho_runs.py` / `backend/short_interest/reg_sho.py`
ever disagree, the code wins. **MINE** = a number or word I chose; none is a trading threshold. Only
`REG_SHO_CLOSEOUT_SETTLEMENT_DAYS` and `REG_SHO_CLOSEOUT_BUY_WINDOW_DAYS` feed the date math; the Rule 204 / Rule 144
numbers are described in served sentences, never compared. No bare 13, 11, 5, 3, 35 or 30 in `reg_sho.py`.

`backend/short_interest/reg_sho_runs.py` (pure: no Mongo, no HTTP, no display words):

| Constant | Value | Whose |
|---|---|---|
| `REG_SHO_NAME` | `SEC Regulation SHO` | the SEC's name |
| `REG_SHO_CLOSEOUT_RULE` | `Rule 203(b)(3)` | SEC |
| `REG_SHO_CLOSEOUT_SETTLEMENT_DAYS` | 13 | SEC Rule 203(b)(3) — feeds the date math |
| `REG_SHO_CLOSEOUT_BUY_WINDOW_DAYS` | 3 | SEC staff FAQ 6.7 (days 11, 12, 13) — `first_buy_day()` = 13 − 3 + 1 = 11, derived |
| `REG_SHO_STAFF_FAQ` | `SEC staff FAQ 6.5, 6.7` | citation |
| `REG_SHO_SETTLEMENT_DAY_RULE` | `Rule 203(c)(5)` | SEC |
| `REG_SHO_204_RULE` | `Rule 204` | SEC |
| `REG_SHO_204_SETTLEMENT_DAYS` | 1 | SEC Rule 204(a) — described, never compared |
| `REG_SHO_204_LONG_MM_SETTLEMENT_DAYS` | 3 | SEC Rule 204(a)(1), (a)(3) — described, never compared |
| `REG_SHO_144_RULE` | `Rule 144` | SEC |
| `REG_SHO_144_SETTLEMENT_DAYS` | 35 | SEC Rule 203(b)(3)(ii) — described, never compared |
| `BANK_HOLIDAYS_OPEN_MARKET` | `Columbus Day`, `Veterans Day` | Rule 203(c)(5) + the measured files; **MINE** reading (HIS CALL #3) |
| day 1 = the list's own date (`day13_late` = one settlement day later) | — | **MINE** default (HIS CALL #2) |

`backend/short_interest/reg_sho.py` — engineering, **all MINE**, none a trading threshold:

| Constant | Value | Meaning |
|---|---|---|
| `RS_HIST_SETTLEMENT_DAYS` | 30 | **MINE** — settlement days of lists read per market (HIS CALL #11) |
| `RS_HIST_MAX_GETS` | 40 | **MINE** — outside calls after which a round starts no further item |
| `RS_HIST_BUDGET_SEC` | 45 | **MINE** — wall budget of one backfill round |
| `RS_HIST_PAUSE_SEC` | 0.25 | **MINE** — pause between two backfill items |
| `RS_HIST_MAX_TRIES` | 3 | **MINE** — asks of one hole at the short spacing |
| `RS_HIST_REASK_MIN` | 1440 | **MINE** — minutes between asks of a `missing` hole, and of an `error` hole past the tries |
| `RS_HIST_NOT_READ_MAX` | 10 | **MINE** — unread dates listed per market in `closeout.history.not_read` |
| `HOLE_KIND` | `nolist` | **MINE** — doc kind of a recorded hole |
| `RS_RETRY_MIN` (reused) | 30 | **MINE** (11-22) — error spacing, source cool-down, write-failure breaker |
| `RS_KICK_MIN_SEC` (reused) | 60 | **MINE** (11-22) — served retry while only the history is pending and the floor refused the read's kick |

Words (served; the frontend types none): `CLOSEOUT_WORD` = `close-out` (the rule's own word; HIS CALL #6), `IF_STAYS`
= `if it stays on` (**MINE**; HIS CALL #5), `NOT_A_PRICE_READ` = `A rule date — it says nothing about price.`
(**MINE**; HIS CALL #8), `FTD_ONLY`, `NOT_ADVICE`, the run / title templates and the date word (`Fri 11/27`, from a
fixed day-name tuple, never the locale). Test bound `TITLE_MAX = 1350` (**MINE**, tests only).

## What it never does

No push, no keep-set kind, no gate, sort, filter, rank, A+ input, lane, threshold, crontab line or broker key reads it.
Unchanged: `refresh_due`, `is_due`, `market_view`, `state_for`, `check`, the fault line, the five source lines, the
route, the conftest seam, `borrow.py`, `read.py`, every file under `backend/chart_maps/`, `backend/push/`,
`backend/trading/` (a test pins that no file there names `reg_sho`, which covers `reg_sho_runs`). The two-read rule for
a zero-row list is unchanged. No frontend production file changed. No colour, bold or alarm look in the day 11–13
window.

## UNMEASURED

Nothing in the repo measures the threshold list, or days on it, against outcomes. No study of "day 11–13 on the
threshold list × forward return" exists. This tag is a **rule date** with no edge claim. Adjacent studies (SI ×
cradle 11-17, big movers 11-09, the AKAN autopsy 11-23, the extreme-SI study pre-registered 11-23 and not read out) are
not about this list and are never to be quoted as support.

## HIS CALL — built to a default, or not built; none decided for him

1. **A date on the tag at all, given what the rule is.** Default: built as he asked, with the limits in the words. The
   day-13 date is a backstop — Rule 204 already requires fails to be closed out 1 to 3 settlement days after
   settlement, and the SEC staff say fails generally do not last 13 days. The cautious alternative is `day 9 on the
   list` with no date.
2. **How day 1 is counted.** Default: the list dated D is day D → GMEX **Fri 11/27**. The other reading (each list
   takes effect at the next open, FAQ 6.1) → **Mon 11/30**. The hover prints both; the chip prints the default. One
   line in `closeout_dates`.
3. **Settlement days, not trading days.** Default: bank holidays (Columbus Day, Veterans Day) do not count — the SEC's
   definition and both exchanges' own files. It moves GMEX from the Wed 11/25 he was told. Counting trading days
   instead is a one-line change, with NYSE names then unreadable across those two days.
4. **Which date the tag prints.** Default: day 13 of the list run. Alternatives: the first day buying counts (day 11,
   FAQ 6.7 — GMEX Tue 11/24), the latest start (the next open, FAQ 6.5 — GMEX Mon 11/30), or a window `11/24–11/30`.
5. **How much the card chip says on the phone.** Default: `… · day 9 of 13 · close-out day Fri 11/27 if it stays on`
   — 100 characters (was 45), because the phone has no hover and a bare date reads like a promise. Options: drop
   `if it stays on` (85, bare date); or print the short form on cards (35 — drops his words "threshold security").
   The 👀 Watch tile and the 📋 cell already print the short form, with a bare date.
6. **The word.** Default "close-out" (the rule's word). The brief's "buy-in due" is one constant away
   (`CLOSEOUT_WORD`); the SEC staff say NSCC cannot execute buy-ins, and the new words test bans "buy-in" until he says
   otherwise.
7. **His tag name on the short form.** On the 👀 Watch tile and the 📋 cell a dated tag reads `🔒 close-out Fri 11/27 ·
   day 9 of 13` — "Hard to borrow" is dropped there to fit and to keep the date clear of the ellipsis. Cards and the 🎾
   label keep his words.
8. **His word "squeeze" in the hover.** A standing negative test bans it on every served string of this tag. Default:
   "A rule date — it says nothing about price." Using his word means relaxing that pin for one negated sentence.
9. **"Passed its date and nothing happened."** NOT served, and no count of names past their date is served
   (survivorship). A pre-registered study of the day 11–13 window against forward returns (Rule #10, with placebo)
   only on his word.
10. **Anything beyond a tag**: a colour or bold in the day 11–13 window, a sort or filter by close-out date, a push when
    a board or Watch name reaches day 11 or 13 (a new keep-set kind). Not built.
11. **Lookback 30 settlement days** (mine). A name on every one of them reads `day 30+ · close-out day passed` with no
    date. A longer lookback = more one-time fetches.
12. **`day count unknown` on the chip and label** when a day's list was not read (the short form then stays today's
    text). Hiding it, or printing "at least N", is his call.
13. **More on the 👀 Watch.** He asked on 11-22 for less info there; the short form gets longer. Behind ⋯ is his call
    (standing HIS CALL #4 of the 11-22 doc).
14. **Backfill pacing and retry numbers** (40 per round, 0.25 s, 3 tries 30 minutes apart, then daily) — mine,
    engineering only.
15. **Sources unchanged**: FINRA's OTC threshold list and the other NYSE venues are still not read (standing HIS CALL
    #7 of the 11-22 doc).
16. **ℹ️ home**: folded into the 🔒 pick because the 🩳 section is full (standing HIS CALL #11); the pick is now
    ~1,500 characters.
17. **The 📋 🩳 column width**: the cell is `nowrap`; the dated `short` is ~11 characters longer than today's. Wrap the
    cell, shorten the short form, or accept.

## How to check

Before deploy (the container runs `origin/main`; none of this is loaded there):

- Open `sec.gov/divisions/marketreg/mrfaqregsho1204.htm` in a browser and confirm the section-6 note on Rule 204,
  6.1, 6.5 and 6.7 as quoted above. If any differs, STOP: the hover cites them.
- Re-run the worked table from the worktree on the DERIVED fixture: `RUNS.run_for` for SMTK / GMEX / AKAN must equal
  the table above (SMTK `passed` 18, day13 11-13; GMEX `counting` 9, day13 11-27, day13_late 11-30; AKAN `counting` 1).
- One real backfill from the worktree with the in-memory stand-in (host venv, outside pytest, evening, never during
  RTH, never the live api): one `refresh_due` + two `backfill_history` rounds; print each round's return and the
  total; confirm no URL for 2026-11-11 was asked; count the zero-row market-days seen. The numbers go in the
  MEASURED line above.
- Desktop Chrome and Safari: hover the SMTK chip and see whether the last sentence ("Not advice.") shows.

After deploy, single reads (authed; replace the email with the owner's), at least 60 s apart, at most six, never a
loop:

```bash
rtk proxy curl -s -H "X-User-Email: OWNER_EMAIL" "http://127.0.0.1:8000/short-interest/reg-sho?check=SMTK,GMEX,AKAN"
```

- The first reads say `refreshing: true`, `retry_after_sec: 20` (the read started or sees a worker; 60 only when the
  floor refused the kick) and several `day count unknown`;
  `closeout.history.read` grows each round. That is by design while the history loads.
- **The loop is closed**: once `closeout.history.pending` is false, one more read 60 s later must say
  `refreshing: false`. If it still says true after six reads, that is a defect.
- Expected, if the name is still listed (a name that left the list has no tag — that is the answer):

| Newest Nasdaq list | GMEX | SMTK | AKAN |
|---|---|---|---|
| 11/20 | day 9 of 13 · Fri 11/27 | day 18 · passed Fri 11/13 | day 1 of 13 · Wed 12/9 |
| 11/23 | day 10 of 13 | day 19 | day 2 of 13 |
| 11/24 | day 11 of 13 | day 20 | day 3 of 13 |
| 11/25 | day 12 of 13 | day 21 | day 4 of 13 |
| 11/27 | day 13 of 13 (`reached`) | day 22 | day 5 of 13 |
| 11/30 | day 14 · passed Fri 11/27 | day 23 | day 6 of 13 |

The real payload through the real component:

```bash
REG_SHO_LIVE_PAYLOAD=/abs/path/to/payload.json rtk proxy npx vitest run src/components/GgHardToBorrow.payload.test.tsx
```

On https://pounce.ajaykandakatla.dev → 🚩 Gajjala → 🎾 Reversal Squeeze: a carded listed name shows the dated label
under its 🩳 line; another card the dated chip; the 👀 Watch tile and the 📋 table the short form.

Tests: `backend/tests/test_reg_sho_closeout_day_2026_11_24.py` (calendar, runs, backfill, holes, words, NEGATIVES),
`backend/tests/test_reg_sho_threshold_2026_11_22.py` (the moved AKAN pins and golden),
`frontend/src/components/GgHardToBorrow.closeout.test.tsx` (the six worked items through the real component).

**MEASURED 2026-11-23 23:09 ET (worktree, in-memory store, real sources):** refresh_due 5 GETs (4.6 s); backfill round 1 = 40 GETs / 24 found / 0 confirmed / 0 holes (41.0 s), round 2 the same (42.3 s); 85 GETs, all 200 (Nasdaq 17, NYSE 51, Cboe 17); no 2026-11-11 URL asked; 12 zero-row NYSE main-market days (10-30 → 11-17) each still owe one confirm GET → a full backfill is about 150 GETs plus confirms. After two rounds SMTK reads `day 17+ · close-out day passed · still on` (the run is a floor until 10-26/10-27 are read in round 3). Card chip: 2 lines on a 430 px card; 📋 🩳 cell 154 → 203–242 px inside its own scroll.

## 2026-11-24 (late) — `past_closeout_text`: the 🔒 words for a name still on its list past its close-out day

Ajay 2026-11-24 ~23:35 ET: "Days past little bit like AKAN is what I am mainly looking for many were so confident on
SSR..". NEW `reg_sho.past_closeout_text(run)` turns a `reg_sho_runs.run_for` block into the source tag the 🚩 pass
(sissr WP be-pass) prints: `passed` → "🔒 day 6 past close-out" (19 settlement days on the list −
`RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS`, read by name at call time); `passed_open` (the run's first day not known) →
"🔒 day 17+ past close-out" (30 days read); counting / reached / unknown / junk / no day past → None. Never raises.
The close-out day is a backstop of the rule, a rule date only — it says nothing about price. Tests:
`backend/tests/test_reg_sho_past_closeout_2026_11_24.py` (the constant monkeypatched to 12 moves it to "day 7"; no bare
rule number in the function; negatives marked `NEGATIVE`).
