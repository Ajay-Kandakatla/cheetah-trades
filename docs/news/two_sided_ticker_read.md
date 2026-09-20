# ⚖️ Per-ticker bull / bear read, and the 🏛️ POTUS tab

**2026-09-20.** Ajay, verbatim: *"I would like it to be in individual tickers
but also in to the potus page in chart maps"* and *"Anytime POTUS does new
investments show me those"*.

Nothing on either surface is a measurement. The ticker read is written by an
LLM and every result carries `measured: false` and `read_by`. The POTUS watch
candidates are a **regex over headlines** and every row says so. Neither
pushes, gates, sizes, orders or enters anything.

---

## ⚖️ The per-ticker read

`backend/news_search/two_sided.py`, mounted on the ticker page's **Catalyst**
tab beside 📰 *What's the news say?* (`TwoSidedNewsButton.tsx`, label
"⚖️ Bull / bear read").

### It is the sector day-tag, pointed at one name

Everything that decides what the model is told and what counts as an answer is
**imported** from `rotation/sector_news_tags.py`, never restated:

| imported | what it decides |
|---|---|
| `_SYSTEM` | the prompt — the hard rules, the JSON shape, "say reversal, never bounce" |
| `_ask_model` | local model first, hosted second, `read_by` recorded |
| `_usable` | both sides written, ≥ 40 characters each, or there is no read |
| `MIN_HEADLINES` | 2 — one loose headline is not a story |
| `MAX_HEADLINES_TO_MODEL` | 6 — how many headlines the model is shown, and how many are stored beside the answer |
| `today_et` | the ET session date, not UTC |

A second prompt for the ticker page is the thing this module exists to avoid.
Two prompts drift, and the day they drift the same company reads bullish on its
sector tile and bearish on its own page off the same six headlines, with
nothing on either surface to say why. `test_two_sided_news.py` pins the prompt
by **object identity**, so a copy cannot be introduced without a red test.

The news leg is `news_search.core.search(ticker=…)` on
`core.DEFAULT_WINDOW_HOURS` (36h) — the one window, audited under
`two_sided` in `news_search_audit`.

### The app owns every number

`facts_for(symbol)` builds the FACTS block from what the app already computed:

| fact | source |
|---|---|
| `last_close` | the latest scan row (`sepa.scanner.load_latest`) |
| `sales_growth_yoy_pct`, `sales_prior_yoy_pct`, `sales_tier`, `sales_accelerating` | `sepa.research.decision_snapshot` → `fundamentals.sales` |
| `eps_growth_yoy_pct` | `decision_snapshot` → `q_eps_growth_pct` |
| `net_margin_pct` | `earnings_quality.components.npm_latest_pct` |
| `next_earnings` | `sepa.earnings_watch.next_event` |
| `company` | the scan row, else `sepa.company_names.name_for` |

Rule 1 of `_SYSTEM` forbids the model from stating a number that is not in that
block, and `TwoSidedNewsButton` renders the numbers **from `facts`**, never
parsed back out of the prose. Same division of labour as `desk.report` and the
sector tags: the app owns every number, the model owns only prose.

A key whose value is missing is **dropped**, so the model is never handed a
`None` to hallucinate around.

### The adjacency guard rides here too

`sepa.qoq.period_ok(periods)` is the app's one answer to "are these
year-over-year pairs actually four quarters apart?" — Massive omits a quarter it
does not have rather than leaving a placeholder, so list *position* is not
quarter adjacency. It checks **both** pairs the block prints, `Q.HEADLINE_PAIR`
(0,4) behind `sales_growth_yoy_pct` / `eps_growth_yoy_pct` and `Q.PRIOR_PAIR`
(1,5) behind `sales_prior_yoy_pct` and the acceleration flag, and it answers a
tri-state: `True` checked and adjacent, `False` checked and not, `None`
unverifiable.

**Only a `False` blanks.** When it does, `facts_for` **blanks every leg
computed off either pair**: the growth number, the prior-year number, the tier
derived from the growth number, the acceleration flag derived from the prior,
and the EPS year-over-year. `net_margin_pct` is a level, not a pair, so it
stays. The block then carries `yoy_pair_comparable: false` rather than going
quiet, so the model can write "the growth figures are not comparable this
quarter" instead of inventing one.

**2026-09-20 — the prior-year leg was unguarded.** Until this date `facts_for`
checked `_adjacent(periods, 0, 4, gap=4)` alone, so a document whose (0,4) pair
was clean and whose (1,5) pair was not — periods `[8106, 8105, 8104, 8103,
8102, 8100]`, where slot 5 is five quarters behind slot 1 — handed
`sales_prior_yoy_pct` and `sales_accelerating` to the model on exactly the rows
📈 Bonde holds out of its tiers, 🔥 Hottest blanks and the 🚀 growth board
refuses. The ticker page could therefore call a name accelerating off a quarter
no board would print. It now calls `Q.period_ok`, which is `Q.yoy_pairs_ok`
over `Q.YOY_PAIRS`, so the page and the boards blank the same documents off the
same filed quarter. Pinned by
`test_a_mismatched_PRIOR_pair_blanks_the_legs_too`, which fails on the old
code.

**The residual, stated plainly:** an *unverifiable* pair — a cached document
with no period keys, or a `None` slot — answers `None` and is **accepted**,
never blanked, because refusing the 682 of 3,754 research documents that carry
no `q_period_series` would empty the block rather than improve it, and because
📈 Bonde and 🔥 Hottest accept the same documents. So `yoy_pair_comparable:
true` means "checked and adjacent, **or** not checkable", never "checked".
This module inherits that and does not fix it; the data-spine audit
(`docs/sepa/data_spine_audit_2026_09_20.md`) is where the counts live.

### Every way it refuses

| what happened | what comes back |
|---|---|
| fewer than `MIN_HEADLINES` in 36h | `ok: false`, the reason names the floor and the window, the headlines found are still returned and stored |
| the model is off / the call raised | `ok: false`, `reason: "model unavailable"` |
| one side missing or under 40 chars | `ok: false`, `reason: "the model did not write both sides"` — **never half a read**, because a bull case with an empty bear case reads as a recommendation |
| the news provider raised | `ok: false`, empty headlines, nothing propagates |
| Mongo down | the read still works, it is simply not stored |

Half a read is the failure mode this whole design is built around. The frontend
mirrors it: the two columns are the **same class** (`.tsn__case`), so neither
side can be given more room than the other, and a `vitest` case pins the
equality.

### Once a day, and the split between POST and GET

Stored in Mongo `news_two_sided`, `_id = "{SYMBOL}|{ET date}"`. **Every**
result is stored, including the failures — the news cache rolls within hours,
so a day later a claim in the prose cannot be traced back to the headline that
produced it unless the headlines were kept beside it (the lesson the sector
tags learned auditing CAG's "$13.00 price target").

```
POST /news/two-sided/{symbol}[?force=true]   may call the model; serves today's
                                             stored read back with cached: true
GET  /news/two-sided/{symbol}                NEVER calls the model — the stored
                                             doc, or {"ok": false,
                                             "reason": "not read today"}
```

A GET that could trigger a model call is a GET a page-load, a prefetch or a bot
can run a bill up on. The button mounts cold; nothing happens until he clicks.

---

## 🏛️ The POTUS tab

`frontend/src/components/PotusBoard.tsx`, reading `GET /political/board`. Two
sections, and they are **not the same kind of thing**.

### 1. The list

The curated disclosures from `backend/political/disclosures.json`. A row is
there because a filing or a named report put it there; nothing automatic ever
adds one. Grouped in a **fixed** order with the group's count in the header:

1. 🇺🇸 `govt_investment` — U.S. government equity stake
2. 🛠️ `govt_contractor` — contractor / program participant
3. 🏛️ `potus_family` — POTUS family disclosed
4. 🔍 `inferred` — not directly disclosed

The order is editorial, not a ranking: a disclosed federal equity stake is a
harder fact than a contractor relationship, which is harder than a family
disclosure, which is harder than a row this app merely inferred. **It is never
re-sorted by anything on the tile**, and a `vitest` case pins that the served
order inside a group survives.

A ticker with two categories is in **both** groups (INTC is both a family
disclosure and a federal stake), so the header counts sum to more than the
number of names. That is the truth about the row.

One Support-tab tile per name off the same `/chart-maps/support` payload the
Support tab draws — the HoldingsBoard pattern, so the bands and the AMD /
Keltner reads cannot differ between the two surfaces. Each tile carries the
political chip, 🚀 GrowthChip, 🧨 ExplosiveChip, 🎯 EnterableChip and a
`+ Signals` button, and prints the row's `govtStake`, disclosure band and
**notes** as readable text rather than a tooltip — the notes are the part that
says a row is *not* what its group header implies ("no government agreement
announced" on the inferred names).

One bounce-room POST covers every name on screen; the chips read that one map
rather than firing a request per tile.

### 2. The watch candidates — a regex, not a signal

`backend/political/watch.py` classifies headlines and the board prints them in
a table: ticker, how it resolved (cashtag / company name / unnamed), the
headline as a link, source, published (ET), the matched pattern, the agency,
the stated size, when it was first seen, and whether it was pushed.

The heuristic sentence at the top of the section is **served**
(`watch.note`) and printed verbatim. A sentence written in the component could
drift from the gate that actually decides what gets pushed; this way it cannot.

**A candidate whose headline names no resolvable ticker is still shown**, as
`unnamed — needs a ticker`, with no link on the ticker cell and em-dashes where
the agency and size would be. Dropping those rows would hide exactly the
stories his ask is about — the reporting that names a company in prose and
never prints a cashtag. Only 1.1% of these titles carry a tag.

Zero candidates renders one line saying so, sized off the served
`watch.window_hours`.

---

## Files

| file | what it is |
|---|---|
| `backend/news_search/two_sided.py` | `facts_for`, `read`, `cached`, the Mongo store |
| `backend/news_search/api.py` | the POST / GET split |
| `backend/tests/test_two_sided_news.py` | 40 cases; the prompt identity pin, the adjacency guard on BOTH yoy pairs, the unverifiable-accepts cases, every refusal |
| `frontend/src/components/TwoSidedNewsButton.tsx` | the ⚖️ button, equal columns, the facts block |
| `frontend/src/components/PotusBoard.tsx` | the 🏛️ tab |
| `frontend/src/components/PotusBoard.test.tsx` | 12 cases; fixed group order, the unnamed candidate, the served-order pin |
| `frontend/src/components/TwoSidedNewsButton.test.tsx` | 10 cases; equal columns, facts-only numbers, every failure surface |

## Not done here, and whose call it is

* `potus_investment` push registration, the classifier itself and
  `/political/board` are `backend/political/` (a separate package) — see
  `docs/political/potus_watch.md`.
* The tab slot (`potus` after `gnt`) and the enterable bucket for it are the
  main session's wiring and remain **his call** (spec §7.5, §7.6).
* The ⚖️ read is not measured and no study of it is proposed. If it ever wants
  to be more than a briefing, it needs a cohort, a placebo and a CI first.
