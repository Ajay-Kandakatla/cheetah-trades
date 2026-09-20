# 🏛️ POTUS / federal-stake watch — a HEURISTIC, not a signal

**Nothing in this document is measured.** The watch is a regular expression over
news headline *titles*. It has no backtest, no expectancy, no win rate, and it
never claims one. It fills a candidate list a human reads.

*Added 2026-09-20. Ajay: "Anytime POTUS does new investments show me those."*

---

## 2026-09-20 — one source for the list, and a daily watch over it

Before today the curated political list lived in
`frontend/src/lib/politicalDisclosures.ts` and nowhere else. That is fine for a
chip and impossible for a cron: **a cron container cannot read TypeScript**, so a
watch had no way to know that MP and INTC were already on the list and would have
re-proposed every row of it, every day, forever.

So the list moved:

| Layer | File | Role |
|---|---|---|
| Source | `backend/political/disclosures.json` | The 44 rows. **Edit this one.** |
| Loader | `backend/political/disclosures.py` | `entries()`, `by_ticker()`, `validate()`, `is_new()` |
| Generator | `backend/scripts/gen_political_ts.py` | writes the TS + a byte-equal JSON copy |
| Frontend | `frontend/src/lib/politicalDisclosures.ts` | **GENERATED — do not edit** |
| Frontend | `frontend/src/lib/politicalDisclosures.generated.json` | the copy the contract test diffs against |

The rows were transcribed row-for-row from the TS; nothing was added, removed or
reworded. The count is still 44, the eight 2026-09-19 critical-minerals rows
still carry `addedOn: '2026-09-19'`, and GLND / CRML / UUUU are still `inferred`
with `govtStake: null`.

To change the list:

```bash
cd backend
python -m scripts.gen_political_ts
```

`--check` exits 1 when either generated file is stale, so a hand edit to the TS
is caught rather than silently overwritten later.

### `validate` — the one failure this list can actually have

A row that CLAIMS a government equity stake without naming the agency or stating
the size. The 2026-09-19 note says it in words — *"The administration is weighing
a stake" is not a stake* — and GLND is on the list precisely so the chip can say
"we looked, and there is no deal". `validate` rejects:

- a `govtStake` on a row that is not `govt_investment` (an award is not a stake);
- a `govtStake` with no agency token (`DoD`, `Commerce`, `DOE`, `Treasury`, …);
- a `govtStake` with no `%`;
- a duplicate ticker, an unknown category, a date that is not `YYYY-MM-DD`.

---

## The watch — `backend/political/watch.py`

```bash
python -m political.watch            # the cron
python -m political.watch --dry-run  # classify and print; writes nothing, pushes nothing
```

One pass, once a day:

1. **Seven keyword searches** (`WATCH_QUERIES`) through the shared news routine,
   `window_hours = 24`, relevance off (a keyword query has no ticker to be
   relevant to), audited as `potus_watch`.
2. **Classify the title** against `PATTERNS`, in `PATTERN_ORDER` precedence —
   `equity_stake` → `federal_award` → `potus_family`, **first match wins**.
   "Trump administration takes 10% stake in Intel" is an `equity_stake`, not a
   family row: the administration acting *is* the government investing, and
   filing it under `potus_family` would hide the exact event he asked about.
   `AGENCY_RE` and `SIZE_RE` are case-insensitive, so `$100 Million`, `$100M`,
   `$2.5 billion` and `9.9%` all match; `100 shares` does not.
3. **Resolve a ticker.** Cashtag / exchange tag first, then the company name.
4. **Drop** anything already on the curated list, and **reject** anything whose
   ticker `companies.store.get` cannot name (the stub it returns for an unknown
   symbol carries `refreshed_at: None` — a stub is a reject, not a name).
5. **Store** the candidate, `_id = "{TICKER}|{url}"`, `$setOnInsert first_seen`.
6. **Push** only the tightest class, and nothing looser.

### Why there is a company-name index at all

**Measured 2026-09-20 over 377 titles from these queries: 4 carried a cashtag or
an exchange tag — 1.1%.** Two of the headlines that matter most that day —
*"Ranking Member Lofgren Raises Alarm Over … Commerce Department Equity Stake in
USA Rare Earth"* and *"Rigetti Computing Finalizes $100 Million CHIPS Act Award
with U.S. Department of Commerce"* — carry neither. A tag-only extractor would
have answered his ask with nothing.

So `_name_index()` builds a reverse index from
`sepa.company_names.all_names()` ∩ `universe.load_universe("full")`: each name
lower-cased, punctuation stripped, trailing corporate suffixes (`inc`, `corp`,
`holdings`, …) dropped, sorted **longest first**, matched **whole-phrase**.

Two parser rules, neither of them a threshold on a signal:

- **A one-word name is indexed only at ≥ 6 characters** (`MIN_ONE_WORD_NAME`).
  "Apple", "Visa" and "IonQ" are ordinary English or ordinary noise before they
  are tickers. *Open item for Ajay:* "Target" is exactly six characters, so it
  clears the floor — a `Target raises guidance` headline would resolve to TGT if
  it ever classified. It could never push (the push gate needs an equity stake
  plus an agency plus a size), but raising the floor to 7, or replacing the
  index with a curated alias list beside `disclosures.json`, is his call.
- **`all_names()` is cache-only.** `bulk_warm` is never called on this path, so a
  cold name cache simply *shrinks* the index and more headlines land as
  `unnamed`. That is the intended failure direction: fewer rows, never a wrong
  ticker.

### Unnamed candidates

A headline that classifies but resolves to no ticker is **still stored**, with
`ticker: null`, `resolution: "unnamed"` and `_id = "|{url}"`. The board prints it
as *"unnamed — needs a ticker"*. It is never pushed. "We saw this and could not
name it" is the honest row; a guessed ticker is the alternative.

### The push gate

`is_pushable` is `pattern == "equity_stake"` **and** a named agency **and** a
stated size **and** a resolved ticker. Nothing looser reaches a phone:

| Headline | Stored | Pushed |
|---|---|---|
| "Commerce Department takes 10% equity stake in X ($X)" | ✅ | ✅ |
| "Trump administration takes 10% stake in Intel (NASDAQ: INTC)" | already on the list | ❌ (no agency, and INTC is listed) |
| "Rigetti … $100 Million CHIPS Act Award with … Commerce" | ✅ by name | ❌ (an award is not a stake) |
| "Government weighing stake in Critical Metals" | ✅ | ❌ (no agency, no size) |
| "$ABC wins $400M Pentagon contract" | ✅ | ❌ (an award is not a stake) |
| "…Commerce Department Equity Stake in USA Rare Earth" (name not in the index) | ✅ unnamed | ❌ |

**Dedupe is on `(ticker, url)`.** A rejected candidate is therefore only
re-evaluated when a NEW url names it — a rate-limited day rejects rather than
inventing a company, and the same story under a different headline gets a second
look tomorrow.

---

## The fifth phone kind — registered, and OFF

`kind = "potus_investment"`.

His **standing keep-set is four phone kinds** (hot pullback, chart patterns,
reversal at demand, portfolio — memory `cheetah_push_silent_drops`). This is a
fifth, so it ships:

- **registered** — `push.subs.default_prefs()["potus_investment"]`. A kind
  missing from that dict silently drops for every device (the 2026-06-24
  chokepoint), which makes the cron look healthy while the phone stays dark.
- **`False`** — the **first and only `False` in that dict**.
  `list_subscriptions` targets only `prefs.{kind} == True`, so **nothing reaches
  a phone until he flips the 🏛️ toggle at `/notifications`**. No deploy, no code
  change, his switch. The board shows every candidate either way.
- a **PERSONAL kind** in `market_hours.gate` — it is computed from a headline,
  not from a price, so a weekend or an NYSE holiday does not make it stale. The
  government announces on the days it announces. It is **not** in
  `MARKET_ALERT_KINDS` and **not** in `DISABLED_ALERT_KINDS`.

Until he flips it, `subs.list_subscriptions(filter_kind="potus_investment")`
returns `[]`, and `push.sender` reports `total_targets: 0` — which the watch
treats as terminal (nobody targeted is a fact the sender reports, not a failure),
so it does not retry the same headline forever.

---

## Endpoints

| Route | Payload |
|---|---|
| `GET /political/disclosures` | `{n, entries, new_days}` — the curated rows |
| `GET /political/board` | `{as_of, new_days, entries[+is_new], groups, candidates, watch}` |

`groups` counts a two-category row in **both** groups — INTC is family-disclosed
*and* a government investment — so the group counts sum to 47 over 44 rows.
Neither endpoint runs the watch; the board renders what the cron stored.

`watch.note` is served verbatim and the board prints it as the section header:

> Headline classifier — a regex over titles, NOT a measured signal. A push needs
> a named agency AND a stated size in the same headline.

---

## Cron — does NOT ship with a deploy

```
35 6 * * * /usr/local/bin/python -m political.watch
```

Every day, **no `market_hours.gate`** (headline-driven, weekends included, his
ask), after the 06:20 sector day-tags. The crontab mount is the **host tree**: a
main deploy does not ship a crontab change. After Ajay places the line, verify
in-container:

```bash
docker exec cheetah-market-app-cron-1 crontab -l | grep political
```

---

## What this never does

- It **never edits `disclosures.json`.** Promoting a candidate onto the curated
  list is a human edit of the JSON plus a re-run of the generator — and the row
  only qualifies as `govt_investment` if it carries a named agency and a stated
  percentage, which `validate` enforces.
- It never ranks, scores or sorts by return.
- It never claims the disclosure caused the move.
