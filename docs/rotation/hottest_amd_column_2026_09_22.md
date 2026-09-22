# 🌀 The AMD column on the 🔥 Hottest board — backend, 2026-09-22

## The ask, verbatim

Ajay, 2026-09-22, with a screenshot of the 🔥 Hottest tab showing the Defense
roster expanded (KRMN, RCAT, LASR, KTOS, ONDS, BBAI):

> "Add an AMD tag for these. like a column for me to see which one are getting
>  manipulated. Also give me toggle option to open them app on one click in
>  stead of clicking on the carets"

This page covers the **backend half**: where the read comes from, what it is
worth, and every refusal it carries. The column's placement, the em-dash and
the ⊞ Expand-all control are written up in
`docs/rotation/hottest_expand_all_2026_09_22.md`.

## What it is: a cached READ, never a computation

`backend/rotation/hottest_amd.py` hangs one `amd` cell on every NAME row of
`GET /rotation/hottest`, and one `amd_summary` block on the board.

The verdict is **not computed here**. It is read out of the document the
nightly sweep already wrote — Mongo `turning_bullish`, `_id: latest`, written
by `supply_demand.turning_bullish.warm` at **17:20 ET on weekdays**
(`backend/crontab`) — the *same* document the 🌀 AMD tab in Chart Maps draws.
`turning_bullish` forbids the request path in its own words: both verdicts need
a 500-bar frame per name, and "loading 2,800 of those while he waits is how a
tab times out at the open". Every word in a cell comes from
`TB.verdict_text("amd", v)`, the one wording table, so this column and the 🌀
tab can never disagree about a name.

### Measured cost of the read (re-measured, not transcribed)

In the api container, 2026-09-22 00:58 ET, one **fresh python process per
read** (import + connect + `find_one`), document 2.54 MB / 2,682 rows:

| read | wall |
|---|---|
| cold (fresh process) | **0.14 s** |
| first warm | **0.01 s** |
| steady (3 reads) | **0.007 / 0.008 / 0.012 s** |

**The 5.73 s cold figure quoted when this was specced did not reproduce.** The
TTL cache still ships — it is sized to the endpoint's own existing window
(`_AMD_TTL_SEC == rotation.api._MEMBERS_TTL_SEC`, 5 min, pinned equal by test)
and its real job is to avoid re-indexing 2,682 rows on every request — but it
is a cheap guard, not a rescue from a slow read, and this page says so rather
than repeating a number it could not measure. **His call** whether the cache is
worth keeping at all now (§ His call, item 5).

### The live-compute alternative, and why it was still rejected

Computing `amd_verdict` on the request was re-measured here (in-container,
2026-09-22, for this page only) over the board's own 1,476 names:
`prices.bulk_cached_frames` **1.05 s** + `amd_verdict` **0.72 s**, 1,476
verdicts, **0 errors**. Cheap is not the point: a second computation
is a second engine, and the 🔥 column and the 🌀 tab would drift the first time
one of them changed. The store read is shared bytes.

## What the read is worth: MEASURED INVERTED on its own claim

From `supply_demand/turning_bullish.py`'s own docstring, re-measured
**2026-09-14** on **3,712 names / 1,592,057 bars**:

* fires on **15.1% of bars**;
* forward returns negative at every horizon — 5d −0.36% [−0.77, −0.06],
  10d −0.48% [−1.07, −0.02], 21d −0.41% [−1.11, +0.15];
* like-for-like against a bar inside its OWN live base at the same distance
  below the top, it reaches the base top **less** often: **51.9% vs 56.1%,
  −4.2pp [−6.92, −1.89]**, negative in all seven distance buckets;
* the board's own freshest cut is **worse**: −5.6pp [−8.97, −2.69].

Re-runnable: `backend/scripts/turning_bullish_amd_study.py`. Written up in
`docs/supply_demand/turning_bullish.md`.

Every one of those strings lives in `AMD_MEASURED` and is **pinned against
`TB.__doc__`** by `tests/test_hottest_amd.py` — none of them is retyped onto a
surface, and the frontend composes no sentence of its own: it prints
`honesty`, `head_title`, `coverage_note`, `group_note`, `no_sort_reason`,
`no_colour_reason` and `reason_text` verbatim.

**Therefore this column sorts nothing, filters nothing, orders nothing, colours
nothing and gates nothing.** Rule #10: no gate, rule or threshold moved here.

## Coverage, re-probed on the live board (2026-09-22)

Probed in the api container against the persisted rotation build, on the pure
close-basis build (`H.build`), **after** the symbol-resolution fix — before it,
a rename is indistinguishable from a legitimate miss.

| | |
|---|---|
| unique names on the board | **1,476** |
| read | **1,469** |
| blank | **7** |
| `no_verdict` (in the sweep, ungradeable) | **0** |

Per grade, over this board's unique names:

| grade | n |
|---|---|
| failed | 527 |
| basing | 392 |
| marked up | 260 |
| raided | 168 |
| raid stale | 122 |
| no cycle | 0 |

Sum 1,469 = `n_known`; 1,469 + 7 = 1,476 = `n`. **Both invariants are asserted
on every request's own counts**, and the served `coverage_note` is built from
them — no figure on any surface is transcribed from this page or from the spec.

The seven names the sweep does not carry, named:

    BELFA · BH · FCEL · FEIM · HYMC · PSNL · QMCO

Each renders blank with a worded reason that explicitly says **unknown**, not
"clean" and not "no cycle" — those are the words of a real read
(`TB.AMD_TEXT["none"]`), and a blank may never wear them.

## The decisions, and the refusals

**Group rows show nothing.** A cycle phase has no median, and a count over the
25 names a group carries would describe a different population from the medians
beside it (those are the full membership). The board-level counts ride in one
sentence under the table. Served as `group_note`.

**The column does not sort.** `"amd"` is never added to
`rotation.hottest.SORT_KEYS`; a `sort=amd` request is demoted at
`hottest.py:980` to `DEFAULT_SORT` (pinned). Ranking the board on a read
measured −4.2pp against its own placebo would order names by something measured
to go the wrong way. Served as `no_sort_reason`.

**The column carries no colour.** The 🌀 AMD tab paints `raided` green; that is
the exact state the measurement is about. A green cell read at a glance down
600 rows *is* a ranking. The served `tone` still rides in the payload for
fidelity (and for the 🌀 tab), and the frontend deliberately does not paint with
it. Served as `no_colour_reason`.

**A missing document drops the column** and prints one served line
(`unavailable_note`); 1,476 em-dashes are furniture, and silence is a lie.
`TB.stored()` returns `{}` on any failure and never raises, so "no document"
and "Mongo down" arrive identically — both serve `store_unavailable`, and the
module does not pretend to tell them apart.

**A broken import must not 500 the board.** `rotation/api.py` binds
`HA` at **module scope**; an alias bound inside a `try` in the handler would be
unbound in its own `except` and would raise `NameError` out of the handler,
taking the whole 🔥 tab down. Pinned both ways: `HA = None` → 200 with no
`amd_summary`; `HA.attach` raising → 200 with `available: false`.

**The member-table-unavailable early return** (`api.py`) never reaches the
attach block, so that response carries no `amd_summary` at all and the column
simply does not draw — no em-dash furniture on an empty board. Pinned.

## Staleness: the last DUE sweep, on an ET clock

Two traps, both pinned by frozen-clock tests:

1. `chart_maps.board._session_day` has **no time-of-day test** — it returns
   today from midnight — while the sweep writes at 17:20 ET. A naive
   `built_at_date < last_session` is therefore True every weekday morning,
   which is exactly when he reads this board. `_due_session` rolls back to the
   previous session before 17:20 ET.
2. `warm()` stamps **UTC**, not ET. A manual re-warm after 20:00 ET carries the
   next UTC date; compared on a UTC clock it would print a date that has not
   happened in his timezone and pin `stale` False forever. `built_at_date` is
   the stamp converted to `chart_maps.board.ET` first.

| clock | sweep stamped | `due_session` | `stale` |
|---|---|---|---|
| Tue 10:00 ET | Mon | Mon | **False** |
| Tue 18:00 ET | Mon | Tue | **True** |
| Tue 10:00 ET | prev Fri | Mon | **True** |
| Sat 11:00 ET | Fri | Fri | **False** |
| Mon 20:10 ET | `2026-09-22T00:10Z` | Mon | **False** (dated 2026-09-21 ET) |

If `chart_maps.board` cannot be imported at all, `last_session`, `due_session`,
`stale` and `stale_note` all serve **None** — labelled unknown, never guessed.

The sweep clock itself (`SWEEP_ET_HOUR`, `SWEEP_ET_MINUTE`) is **parsed out of
`backend/crontab` by a test**, read-only. The crontab is host-mounted and is
never edited from here.

## Symbol fates

`_index` stores every sweep row under its own symbol **and** under
`sepa.symbols.resolve(sym)` when that differs; a lookup tries the board's
symbol first, then its resolved form. The alias never overwrites a direct hit.
Without this a renamed ticker is indistinguishable from a legitimate miss —
which is why the coverage figures above were re-probed only after the fix.

## The short form (2026-09-22)

> *"last column is hidded"* — Ajay, 2026-09-22, with a screenshot of the 🔥
> Hottest board scrolled to the Crypto-equities roster: the header read
> **🌀 A** and the cells read **AM**.

He is right, and part of the reason was ours. Measured on the live
`GET /rotation/hottest` payload the same morning (1,476 distinct symbols,
1,930 rendered name rows, 1,922 of them carrying a visible read):

* **every single visible cell opened with the literal `"AMD "`** — zero
  exceptions in 1,922 — while the column header already says **🌀 AMD**. Four
  characters of pure duplication, ~1,900 times.
* longest cell **26 chars** (`AMD base failed · 367d ago`), median 23, **124
  distinct strings**.
* strip the prefix and the longest becomes **22**, median 19, shortest 6
  (`basing`) — and still **124 distinct strings**, because the prefix carries
  no information at all.

So the cell now prints `short` and the hover keeps `text`. Per grade, from
`TB.AMD_GRADES`:

| grade | long (`text`, the hover) | short (`short`, the cell) |
|---|---|---|
| `marked_up` | `AMD marked up · 124d ago` | `marked up · 124d ago` |
| `raided` | `AMD raided · 2d ago` | `raided · 2d ago` |
| `stale` | `AMD raid stale · 19d ago` | `raid stale · 19d ago` |
| `failed` | `AMD base failed · 367d ago` | `base failed · 367d ago` |
| `basing` | `AMD basing` | `basing` |
| `none` | `AMD no cycle` | `no cycle` |

**One table, one age rule.** The short is not a second wording engine and it
is not the frontend cutting four characters off a served sentence. The
derivation moved *into* the engine: `turning_bullish.grade_label(kind, grade)`
takes the base word out of the one table minus `VERDICT_PREFIX[kind]`, and
`verdict_short` assembles `grade_label + _suffix` — where `_suffix` is the
**same function** `verdict_text` now calls for the age. Which age belongs
beside which word was decided on 2026-09-14 and is untouched: the raid dates a
raid (fresh or stale), the failure bar dates a failure, the markup dates a
markup, and a bare base or "no cycle" carries none. `rotation/hottest_amd.py`'s
own `_grade_label` is now a one-line delegate to `grade_label`, so the coverage
histogram and the cell beside it cannot drift apart.

**The long form is byte-for-byte what it was.** `verdict_text` was refactored
to share `_suffix`, so every AMD and Keltner sentence it can build is pinned
explicitly in `tests/test_turning_bullish.py` (`AMD_SENTENCES`, `KC_SENTENCES`)
— typed out, not derived, because a derived expectation only proves the code
agrees with itself. The 🌀 AMD tab in Chart Maps and this column's hover read
`text` and see no change.

**The age suffix was NOT shortened.** `19d ago` → `19d` would save three more
characters, but it is built in `turning_bullish._suffix`, which the 🌀 AMD tab
shares, and `today` has no `d ago` to strip — so it is not one table-driven
edit and it changes a surface he reads. Left verbatim. His call if he wants it.

**What this does not do: it does not make the table fit.** Four characters off
the widest cell in one of twelve columns shortens the sideways scroll; it does
not end it. **No estimated px figure is quoted for how much.** The draft
written with the change carried an arithmetic width model — a before and after
width for this column, and a share of the overflow it recovered — built from
measured character counts and *assumed* per-character advances, with no browser
ever opened, and Rule #1 does not take a model for a measurement. Those figures
are gone, and none is repeated here for a skimmer to pick up. What is measured
stands above: 26 characters to 22, on every one of 1,922 cells. The other half
of the fix is the move, below.

### The other half: the column moved out of last place

Shipped the same day. `visibleCols()` now reads
`[🌀 AMD?] + [☀️ Pre-mkt?] + HS_COLS`, so the column sits **immediately after
Sector / Name**.

**Why there.** 🌀 AMD is a **state about the name**, and the Sector / Name cell
already carries this row's other per-name state chips (floor-held, at-band,
🚀, 🎪). A state belongs beside the thing it describes. It also keeps the
ranked numeric legs — Pre-mkt | Today | 5 days | 21 days — contiguous and in
order, which they are not when a state column is wedged in after them. Pre-mkt
still leads the ranked legs; `HS_COLS` is untouched.

**Be plain about what the move buys.** It costs nothing in width and it does
**not** make the table fit. What it changes is the **scroll position**: the
state is now the first thing right of the name, where he reads it without
moving anything. The table still runs off the right edge of a narrow window —
`.hs-table` floors at `min-width: 900px` (760px under the 720px media block)
across up to twelve columns — and it did before 🌀 shipped too.

**Which column gives way is HIS call and it is open.** An earlier draft of this
page nominated Next ER as the expendable one. That was a reviewer deciding
one of his columns for him; the sentence is gone, and the
question is item 8 of § His call in
`docs/rotation/hottest_expand_all_2026_09_22.md`. Read it with one source fact
in hand: the day column is at its **widest** exactly when he reads this board
before the open, because `d1Label()` prints `Last close YYYY-MM-DD` whenever
`d1.live` is false and `rotation/hottest.py` sets that on every closed-session
path — including the ☀️ `basis=premarket` board.

**On a phone** the move pushes every ranked leg one column further right, since
🌀 now sits between the name and them. Nothing here picks a phone layout; the
options are item 9 of the same list.

`visibleCols()` feeds only the `<thead>`; every `<tbody>` cell is a JSX literal
in fixed order, so the header and five render sites moved in lockstep. The full
placement argument, the render-site list and the group-row trap (`hs-spacer`
keeps the cell count right even when the order is wrong) live in
`docs/rotation/hottest_expand_all_2026_09_22.md`, which also closes §7.2.

**Nothing else moved.** The column still sorts nothing (`amd` is still absent
from `rotation.hottest.SORT_KEYS`), is still colourless, group rows still
carry an em-dash and the served `group_note`, a blank is still UNKNOWN and
still names its refusal, and the board still costs one cached Mongo read.

## Payload shape

Per NAME row, `amd`, always all eleven keys:

    known · grade · phase · text · short · tone · title · bars_ago ·
    base_bars · reason · reason_text

`short` is the **board cell's** wording and `text` is the **hover's**. Both
come out of the one table `TB.AMD_TEXT` through `TB.grade_label`, and both
date a read through the one `TB._suffix`, so the two forms cannot name or date
the same row differently. A blank carries `short: None` — a refusal has no
wording of its own to shorten — and still prints the em-dash with its served
reason. See *The short form* below.

`known` is `bool(text) and grade in TB.AMD_GRADES`. That membership gate
matters: `verdict_text` does `table.get(grade) or table["none"]`, so an
ungradeable row would be handed the words of a real read ("AMD no cycle") —
and the live sweep shows `counts.amd["none"] == 0`, i.e. that grade never
legitimately occurs, so any such cell would be a fallback wearing a verdict's
clothes.

`bars_ago` is read off the **same branch `verdict_text` uses** (raid age for
`raided`/`stale`, failure age for `failed`, markup age for `marked_up`, nothing
for `basing`/`none`), never recomputed. Every number passes `_num` — NaN and
±inf become None **in the cell**, not at the endpoint's `_scrub`, because a NaN
passes every `<=` comparison and the endpoint scrub runs far too late to
protect anything that sorts.

Board block `amd_summary`: `available · n · n_known · n_blank ·
blank_reasons · grades · grade_order · grade_labels · built_at ·
built_at_utc · built_at_et · built_at_date · last_session · due_session ·
stale · stale_note · n_scanned · n_rows · source · cron · measured · honesty ·
head_title · group_note · no_sort_reason · sortable · no_colour_reason ·
coloured · coverage_note · unavailable_note · label`.

(`built_at_utc` was served from the start and was missing from this list —
corrected 2026-09-22. It is the marker that rides *with* the raw stamp so a
consumer reading `built_at` and not `built_at_et` cannot take it as local.)

`grade_labels` is `{grade: short word}` over `grade_order`, served so that
nothing downstream types the six words a second time — the same words the
cell's `short` opens with and the same words the coverage histogram counts
("raided 198 · base failed 651"). It is present on the `unavailable()` block
too, so a consumer never meets a missing key on the failure path.

`built_at` and `built_at_et` are always **ISO strings** via `TB._iso` — a BSON
`datetime` in a JSON payload is a 500, not a missing field (caught in-container
2026-09-13).

## Tests

`backend/tests/test_hottest_amd.py` — 95 tests, all green. The negatives are
the point: a name the sweep never saw; a verdict with no grade and one graded
`"wat"`; an empty document; a `stored()` that raises; `HA = None` and a
throwing `attach` on the live handler; NaN and inf; the six frozen staleness
clocks and the missing session calendar; `sort=amd`; the no-member-table
branch; the rename that must not masquerade as a miss; the arithmetic
invariants; and the cache-call counts (one read per attach, one per TTL window,
a miss never cached, `doc=` never touching the cache).

## His call

1. **Sorting** — shipped: does **not** sort. The board's own caption says
   "click any column header". Make it sortable, knowing it would rank on
   −4.2pp [−6.92, −1.89]?
2. **Group rows** — shipped: blank with a served reason, counts in one line
   under the table. Alternative he floated: a per-state count per group row.
3. **Colour** — shipped: colourless. Turning it on would paint `raided` green.
4. **Stale document** — shipped: the column still draws and the line carries
   the sweep's date. Alternative: grey the column when stale.
5. **The cache** — the 5.73 s cold read did not reproduce (0.14 s measured).
   Keep the 5-minute TTL, drop it, or lengthen it (the document changes once a
   weekday)? No number here was invented either way.
6. **"Make manipulation better"** — still **UNANSWERED** from 2026-09-21.
   Nothing here guesses at it.
7. **Other boards** — not built and not proposed: the read is measured
   inverted, so it earns no second surface.

## Unrelated, noticed while running the suites

`tests/test_rotation_members.py` followed by `tests/test_amd_chips_2026_09_21.py`
errors 11 tests at collection: `sepa/insider.py` builds an `asyncio.Lock()` at
import time, which needs a current event loop, and by then there is none.
Reproduces with those two files alone and **predates this change** (it does not
involve `hottest_amd.py` at all). Not touched here.
