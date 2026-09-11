# Sector member popover — the stocks behind a Hot-sectors chip

Shipped 2026-09-10. Ajay: *"I would like to click on the sector category and
see the related stocks list in a pop over to see which ones are gaining
traction"*.

Every chip on the Hot sectors strip is now a button. Clicking one opens the
group's **full liquidity-filtered membership**, one row per stock, ranked by a
backend-owned traction measure, with a demand-zone marker read through the same
`bounce_room` the rest of the app uses.

Measurement of what already moved — not a forecast, not a buy signal, not
advice. The rotation backtest's finding still stands: acting on the leaders did
not beat owning the market (`/rotation/backtest`).

## Two populations, printed side by side and never reconciled

This is the one thing about this feature that could mislead him, so it is the
first thing the panel says.

| | population | measured against |
|---|---|---|
| the number **on the chip** | a deterministic **stride sample** — `COHORT_SAMPLE` / `INDUSTRY_SAMPLE` = 25, `sample_per_group` = 40 for the sector grid | RSP (`rel_21d`) |
| the rows **in the popover** | the **full** liquidity-filtered membership | that group's own median (`vs_group_21`) |

Measured 2026-09-10, `rotation.tracker._sector_members(20e6, 10.0)`: **2,174**
symbol/sector/industry triples across **11 sectors** and **140 industries** —
Technology 348, Healthcare 343, Industrials 327; Biotechnology 146 and Banks -
Regional 117 are the largest industries. The Technology chip's median is
therefore measured on **25 of 348** names. A popover that listed those 25 would
read as "the stocks in Technology" and be wrong for 93% of the sector.

So the sampled median is left **exactly** as it was — no number already on a
screen moves — and the table ships its own `median_21d_full` beside it plus one
sentence saying they are different sets:

* `tracker.MEMBER_NOTE` — the standing sentence, in every payload;
* `median_note` — per group, with both counts, e.g.
  *"Median above = the rotation grid's 25-name sample · this table = all 348
  members (its own 21d median -1.2%)"*;
* the panel renders `sampleVsFullLine(...)` as its **second line** — body copy,
  not a tooltip and not a footnote.

They are not reconciled anywhere, in either direction. The chip is not
restated from the table, and the table's median is never written back onto the
chip.

Cost of the full membership, measured on the live scan 2026-09-10: the union
over all four grains is 1,712 symbols against the 1,480 the sampled grid
already loads, so **one** `_load` over the union adds 251 fetches / **+6.4 s**
to a build that already takes ~29.5 s cold. The member table rides that same
load — a second pass would be duplicate provider work and could hand the two
views a different last bar for the same name.

## "Gaining traction" — the measure, in full

Two legs, both printed on every row, both with their constant:

```
pace_5      = ret_5d  / WINDOW_FAST     (= 5)    percent per session, last week
pace_21     = ret_21d / WINDOW_SHORT    (= 21)   percent per session, last month
traction    = pace_5 - pace_21                   percentage points per session
vs_group_21 = ret_21d - the group's published median_21d

gaining     = traction    > TRACTION_MIN_ACCEL_PP     (= 0.0)
          AND vs_group_21 > TRACTION_MIN_VS_GROUP_PP  (= 0.0)
```

Sort: `gaining desc, traction desc, vs_group_21 desc, symbol asc`
(`tracker.traction_sort_key`). A `None` sorts **last** in every position — a
name whose frame was too short to measure must never rank above one that was
measured and won.

**Why two legs.** Either alone lies. A name can accelerate while its whole
group runs harder — it is being carried, not leading. And a name can lead a
dead group while decelerating — it led *last* month. Traction is the name
pulling ahead of its own group *and* doing it faster this week than it managed
over the month.

Both thresholds are **0.0 by definition** ("faster than its own month", "ahead
of its own group"), not a level anyone measured. Nothing here is a tested edge,
and `TRACTION_SPEC["not_a_signal"]` says so in the payload. The whole spec —
formula, both constants, the sort — ships with every response, so the popover
prints a definition it does not own (his standing rule: a per-name measure on a
board he trades ships its definition).

Everything unknown fails closed: no 5-day frame, no 21-day frame, or no group
median leaves `traction` / `vs_group_21` `None` and `gaining` `False`. A NaN
passes any `<=` gate on this project, so unmeasurable is never "hot".

## Fail closed, and count what was dropped

Dead and stale series are dropped, not read as flat (tracker decision 4: MRO's
last bar is 2024-11-21, HES's 2025-07-17 — a naive return off either is exactly
0.0%). The drop is **counted and named**, never silently absent:

* per group: `n_full`, `priced`, `unpriced`, `unpriced_symbols` (first 8);
* per build: `coverage.symbols / priced / unpriced`;
* a group where nothing could be priced answers with those counts **and** a
  `reason` — *"none of the 12 members could be priced"* — rather than an empty
  list that reads as a sector with no stocks.

## The demand marker's provenance

`tracker._zone_marks` imports `supply_demand.bounce_room` and reads:

* `bounce_room.load_docs(symbols, day)` — the stored zone bands for the latest
  store day (`zone_store.latest_store_day()`);
* `bounce_room.in_demand_read(close, doc)` — the ONE shared definition of
  "the print is standing inside an eligible demand band", the same read behind
  the SEPA 🪃 chip, the Back-in-Demand board and the phone's zone kinds.

No second geometry, no new threshold, no gate: **the marker is context**.
Nothing is dropped, ranked or filtered for lacking a zone.

The column's whole vocabulary is **◧ = the print is inside an eligible band**,
and blank. There is deliberately **no 🪃 here**: `bounce_read` (the reversal)
is never computed on this path, and an earlier draft rendered a 🪃 off a
nested `demand.bounce` object the endpoint has never sent — dead in production
and, worse, claiming a read we do not make. Blank means the zone store has no
doc for that name — *never looked*, not *not at demand*.

* the price is the member's own **last closed bar** — the same bar the returns
  beside it are measured to, so the two can never describe different sessions
  (the live-bar trap, 2026-09-03);
* **no coverage ⇒ `at_demand: null`**, never `false`. A tombstone doc (one
  `load_docs` returns carrying `error`) is not coverage either. `zone_unmarked`
  counts them per group — 556 of 1,731 priced names on 2026-09-10;
* a zone-store failure degrades the **marker only**: every name unmarked,
  `zone.source: "unavailable"` and `zone.error` saying why, and the member list
  comes back intact.

## The endpoint never builds

`GET /rotation/members?grain=<sector|cohort|industry|theme>&group=<label>&limit=`

A cold `tracker.build()` is ~29.5 s and one sector's full member load alone
measured **7.82 s** at `WORKERS=8` — neither belongs behind a click. So the
endpoint only ever *reads*:

1. this worker's `_cache` (warm only if it already served `/rotation`);
2. the persisted scan doc (`scan_context` `_id: rotation`), held for
   `_MEMBERS_TTL_SEC` = 5 min in a cache of its own.

The persisted doc is read with **no freshness cut** and is deliberately not
written into `_cache` — `/rotation` and `/rotation/hot` keep their own 20-hour
rule, and a popover read must not widen it for them. A day-old table is worth
showing *with its age*, so `age_sec` / `built_at_iso` / `stale` ride in the
payload.

Nothing to serve answers **200 with a `reason`**, never a 503 the strip
swallows: *"no persisted rotation build yet — the member table is written by
the scan's context refresh"*, or *"the persisted rotation build predates the
member table"*. An unknown grain or a blank group is a 400 with the same shape.

`/rotation` strips the whole table (`_public`) and ships only `members_index`,
so no page pays ~350 KB for a popover nobody opened.

## Re-running the counts

Membership, the number the popover covers:

```bash
docker compose exec api python -c "
from rotation import tracker as T
s = T._sector_members(20_000_000.0, 10.0)
rows = s.pop('_rows'); s.pop('_unmapped')
print('triples   ', len(rows))
print('sectors   ', len(s))
print('industries', len({i for _, _, i in rows if i}))
for name, syms in sorted(s.items(), key=lambda kv: -len(kv[1]))[:3]:
    print('  %-22s %d' % (name, len(syms)))
"
```

Sample vs full for one group, and what the popover would rank:

```bash
docker compose exec api python -c "
from sepa import context_refresh as MC
from rotation import tracker as T
t = (MC.load_doc(MC.ROTATION_ID) or {}).get('payload', {}).get(T.MEMBERS_KEY) or {}
g = t['groups']['sector']['Technology']
print('chip population', g['n_population'], 'kept', g['n_measured'],
      'median', g['median_21d'])
print('full table ', g['n_full'], 'median', g['median_21d_full'])
print('priced', g['priced'], 'unpriced', g['unpriced'], g['unpriced_symbols'])
print('at demand', g['at_demand'], 'unmarked', g['zone_unmarked'])
rows = sorted((T.traction_row(s, t['by_symbol'].get(s), g['median_21d'])
               for s in g['symbols']), key=T.traction_sort_key)
print('gaining', sum(1 for r in rows if r['gaining']), 'of', len(rows))
for r in rows[:5]:
    print('  %-6s 5d %-7s 21d %-7s traction %-7s vs group %s' %
          (r['symbol'], r['ret_5d'], r['ret_21d'], r['traction'], r['vs_group_21']))
"
```

Zone coverage on the same build:

```bash
docker compose exec api python -c "
from sepa import context_refresh as MC
from rotation import tracker as T
t = (MC.load_doc(MC.ROTATION_ID) or {}).get('payload', {}).get(T.MEMBERS_KEY) or {}
print(t['zone'])
print(t['coverage'])
"
```

The endpoint itself, without a browser:

```bash
docker compose exec api curl -s \
  'http://localhost:8000/rotation/members?grain=cohort&group=Technology%20%C2%B7%20large%20caps&limit=5' \
  | python -m json.tool | head -40
```

## Tests

```bash
docker compose exec api python -m pytest tests/test_rotation_members.py \
                                         tests/test_rotation_tracker.py -v

cd frontend && npx vitest run src/components/HotSectors.members.test.tsx \
                             src/components/SectorMembersModal.test.tsx \
                             src/lib/rotationMembers.test.ts
```

`tests/test_rotation_members.py` pins, in order: the table spans the full
membership while the chip keeps its sample; every rendered chip has a table and
no orphan table rides along; both traction legs are load-bearing and every
unknown fails closed; `vs_group_21` is measured against the group that was
opened (the same name reads +5 and gaining in its cohort, -4 and not in a
hotter industry); unpriceable names are counted and named; the endpoint never
calls `build` / `_load` / `_member_table` on any path, including a missing
doc, a stale doc, a dead Mongo, an unknown group and an unknown grain; and a
zone-store outage unmarks every name while the member list survives.

Its last two tests are **source guards** over `frontend/src`: the query keys
`membersUrl` sends must all be parameters `rotation_members` accepts, and every
field the popover's own types declare must be a key the endpoint sends. They
fail for as long as the two sides disagree — that is their job. FastAPI ignores
an unknown query parameter, so a rename on one side does not error: it silently
answers about the default grain, and a mismatched payload key renders as an em
dash under a sector he clicked, with nothing on screen saying it failed.


## `sampled` is a stride, not a survivor count (2026-09-10)

`sampled` was first computed as `n_measured < n_full`. `n_measured` is the
published row's **survivors** (`group_row`'s `n`), so a single dead series in a
group that was never strided made it true, and the popover then announced a
sample that was never taken — on a **theme**, which is built from the whole
roster, it claimed a "19-name sample" of a 19-name group and disclaimed a
reconciliation that is exact.

The test is now the published row's **population**: `n_population = n + dropped`,
compared with `n_full`. When it says not sampled, the panel says the two
populations *agree* instead of inventing a discrepancy — and an absent payload
(a failed read) knows neither, so it falls through to the conservative wording
rather than asserting an agreement it cannot verify.


## Same day (2026-09-10)

Ajay: *"Can you also check for same day sector too please?"* / *"Instead of 5
days"*.

`WINDOW_DAY = 1` — the member's last close against the one before it.

| where | field | population |
| --- | --- | --- |
| each member row, **leading column** | `rel_1d` (raw `ret_1d`, rebased) | that name |
| the group line in the header | `median_1d_full` | the **full** membership |
| beside it | `up_today` | how many of `priced` are green |

Two deliberate choices:

* **The group number is RAW, not rebased.** "What is this sector doing today"
  is a plain question; restating it against RSP answers a different one. The
  per-name column *is* rebased, because it sits in a row of rebased legs.
* **The 5d column stays.** `traction = pace_5 - pace_21`, so removing that leg
  would hide the sort key the panel prints a definition for.

**Same day does not feed `traction`.** Over one session a single gap would flag
a name as gaining traction, and the standing instruction is that signals get
more accurate, never noisier. `test_the_traction_definition_travels_with_the_table`
asserts `pace_1` / `ret_1d` are absent from the formula so this cannot drift in
later. Moving the flag onto same-day is his call, not a default.

## The stylesheet is pinned too (2026-09-10)

The panel shipped once with **no CSS at all** — the component was right, every
test passed, and `src/styles.css` simply was not in the commit, so all 20
`hsm-*` classes resolved to nothing and the popover rendered as raw full-width
page text. jsdom does not load stylesheets, so no render test can see this: the
DOM is identical either way. A frontend contract now reads the classes the
component uses and fails when any of them has no rule in `styles.css`.
