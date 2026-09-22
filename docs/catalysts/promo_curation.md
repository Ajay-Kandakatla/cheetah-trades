# 🎪 Promo-circuit curation — putting the board's names into the scan universe (2026-09-21)

> Ajay: *"We have this page that pull data from social media and chatter the
> keeps pulling new stocks.. Can you please check if we can use them and make
> sure to do some research and add them to our list as they come through
> please?"*
> (`/chart-maps?tab=catalysts&show=all&sub=promo`)

> **Measured:** the forward record of a promo tag is the separate study package
> — `docs/catalysts/promo_tag_study_2026_09_21.md`. Nothing on this page is a
> claim about whether a tag works. This lane answers a smaller question: *is the
> name even VISIBLE to the app?*

**An add means the app can SEE the name.** It does not mean the app likes it,
and no lane trades off this list. A promo-origin name then passes every
**existing** downstream gate — the $700M known-cap floor in `zone_store`, the
`safety_floor` price/cap floors at `trading/entries._evaluate`, the SEPA
qualifier's $20M liquidity gate — exactly like a Russell micro-cap. No new gate,
no exemption, no push.

## Why a gate and not a loop

`promo_circuit_tags` holds 3,448 docs over 1,561 distinct tickers; **1,012 of
them are outside `full`**. Inside the board's 14-day window and after the
shotgun prune, **374 tagged outsiders** were measured on 2026-09-21:

Each test applied **independently** to all 374 (not in pipeline order — the
pipeline's own split is in the dry run at the bottom of this page):

| | count |
|---|---|
| tagged outsiders in the window (after the shotgun prune) | **374** |
| trade under **$2** | 170 |
| median 50-day dollar volume under **$5M** | 121 |
| clear both floors | 54 |
| …of which **ETF / ETV / foreign ADR** | **24** — BIL, GDX, EWY, MCHI, SIL, REMX, ETHA, BCS, NOK, NVO, PBR, SHEL, SFTBY, BAESY… |
| **pass every gate** | **30** |

A job that added what the board showed would have put index funds and
OTC-quoted ADRs into the universe every scan, zone store, demand board and paper
lane runs on. **Being tagged is the INPUT, never the test.**

## The three populations, and the reference pin

The security type comes from **one** Massive reference call per ticker,
`GET /v3/reference/tickers/{sym}` (`massive_keys.stocks_key()`). Probed
2026-09-21:

| ticker | `type` | `primary_exchange` | verdict |
|---|---|---|---|
| BCS, BAK, BABA, TSM | `ADRC` | `XNYS` | **adr** — refused |
| ADDYY, BAESY | `ADRC` | `OTC Link` | **adr** — refused |
| ADYEN | *404* | — | **unknown** — refused (fail closed) |
| ADBT, AEMD, AEHL, AIFU, FBGL | `CS` | `XNAS` | candidate |
| TOPS | `CS` | `XASE` | candidate |
| MNDY, DRTS, PHVS, STLA | `CS` | `XNAS`/`XNYS` | candidate — **foreign-domiciled ordinaries are typed CS and are NOT refused** |

Two tests that look obvious and are wrong, both rejected here:

- **the 5-letter "Y" suffix** — catches ADDYY/BAESY, misses BCS/BAK/BABA/TSM.
- **`locale`** — reads `us` for every ADR probed. Useless.

`type` is the pin. `ADD_TYPES = {"CS"}`; `LISTING_EXCHANGES` is
`universe.MAJOR_EXCHANGES` (`XNYS/XNAS/ARCX/BATS/XASE`), so `OTC Link` is out.

**The lookup fails CLOSED.** A non-200, a 404 or an exception is class
`unknown` and the name is **refused** — a Massive outage costs a day of adds,
never "unknown type, add it anyway". `_EXPECTED_COUNTS["promo"]`'s lower bound
of 0 is what keeps a zero-add day from logging as a broken parse.

## The gate ORDER is itself the design

| # | gate | constant | cost |
|---|---|---|---|
| 1 | already in the universe | `BASE_COMPONENTS` | **no fetch of any kind** |
| 2 | index / volatility / crypto cashtag | `traders.curate.NEVER_ADD` | **no fetch of any kind** |
| 3 | reference `type` / `primary_exchange` | `ADD_TYPES`, `universe.MAJOR_EXCHANGES` | one HTTP GET |
| 4 | resolves — bars, live, not renamed/delisted | `traders.curate.validate` (`MIN_BARS` 60, `MAX_STALE_DAYS` 10) | 2y bars, **writes `price_cache` on a miss** |
| 5 | last close ≥ $2 | `safety_floor.MIN_SHARE_PRICE` | free (same frame) |
| 6 | median 50-day dollar volume ≥ $5M | `hot_pullback.MIN_DOLLAR_VOL_USD` | free (same frame) |

**Step 2 is the same refusal step 4 already made**, moved earlier (2026-09-21).
`curate.validate` checks `NEVER_ADD` before it loads a single bar, so asking it
here costs nothing — and it lands `$SPX` / `$NDX` in the **permanent** class
`never_add` instead of the transient `unknown`, which the outage rule below
would otherwise re-check on every run forever. Same set, same sentence (the
reason string is read back from `curate.validate`, not retyped), only the order
changed: nothing that was admitted before is refused now, and nothing that was
refused is admitted. `DXY`, `TNX`, `TYX` and `STOXX` are **not** in `NEVER_ADD`
and still cost one reference call a morning each — extending that set is a rule
change and therefore **his call**.

**An ETF therefore never triggers a bar load.** That is not cosmetic: 24 of the
54 floor-passers are refusable on one reference call, and step 3 writes Mongo
and parquet on a cache miss. The order was the critique's finding, and the test
`test_NEGATIVE_an_ETF_never_triggers_a_BAR_LOAD` pins it — the ETF stub records
zero loader calls, a sub-$2 common stock records exactly one.

Every floor is an **imported object**, pinned by identity, never a retyped
number (`test_every_floor_and_window_is_an_IMPORTED_constant_not_a_new_number`).

> A price/liquidity floor **at the universe gate is a NEW semantic** — no other
> universe component applies one today; the floors live downstream. It was put to
> him as exactly that on 2026-09-21 and he **ratified it** ("Yes"), so $2
> (`safety_floor.MIN_SHARE_PRICE`) and $5M median-50d
> (`hot_pullback.MIN_DOLLAR_VOL_USD`) are the gate's floors by his decision, not
> by default. Both remain imported objects; neither is a number this lane owns,
> and changing either changes it everywhere it already applies.

## Rejected rows are not re-checked forever

A row with `status == "rejected"` is skipped when either:

- its `reason_class` is in `PERMANENT_REJECTS` = `{adr, not_common, otc,
  never_add, renamed}` — a reference type does not change overnight; **or**
- no new tag landed since the last check (`last_tagged_at <= checked_at`).

Everything transient (`price`, `liquidity`, `stale`, `short`) is re-validated as
soon as a **new** tag arrives after `checked_at`. Without this the same ~300
refusals would burn a reference call and a 2y bar fetch every morning.
`--recheck` ignores the skip for one run.

**`unknown` is the one exception, and it is exempt from the tag test**
(2026-09-21). That class is not a verdict about the NAME, it is a verdict about
the RUN: the reference call did not answer. On a Massive outage morning all ~374
candidates are stamped `unknown` at once, and any of them that nobody tags again
would otherwise stay refused for the rest of its 14-day window — a provider
hiccup silently costing the lane a fortnight. So `reason_class == "unknown"` is
re-checked on the **next run**, tag or no tag
(`test_NEGATIVE_a_Massive_OUTAGE_day_does_not_refuse_the_whole_WINDOW`,
`test_an_UNKNOWN_reject_from_an_OUTAGE_is_re_validated_on_the_NEXT_run`).

## One pruned, resolved tag set

`_live_tags(now)` is the **single** set both `candidates()` and `age_out()`
read:

1. docs whose `last_tagged_at` is inside `CANDIDATE_WINDOW_DAYS`
   (`promo_circuit.TAG_WINDOW_DAYS` = 14 — while the board still shows it);
2. through the board's own `prune_shotgun_tags` (an account tagging more than
   `SHOTGUN_DISTINCT_TAGS` names keeps only what it repeated);
3. `symbols.resolve` applied — **DOOO → DOO**. This matters: `curate.validate`
   *refuses* a renamed ticker and points at its successor, so resolving first is
   how the successor gets checked instead of the tag being thrown away;
4. `symbols.is_delisted` dropped.

Because it is one set, a name whose only surviving mention is a shotgun drive-by
is not a candidate **and** is not "still tagged" — it ages out.

## Cap and age-out

- **`MAX_ADDS_PER_RUN = 12`**, imported from `traders.curate`. The overflow is
  **reported** (`"over the per-run cap"`) and **counted** as `queue_remaining`,
  never dropped; it is picked up next run. At the measured flow — 30 passers on
  day one, then ~2 new passers a day — day one drains in three runs and the
  steady-state queue sits far under 12, so no tier starves. `queue_remaining` on
  the audit endpoint is the tell if that ever changes. The stored summary counts
  a capped name **once**, as `capped` / `queue_remaining`, and never also as a
  rejection — it would otherwise report the same name twice and make the lane
  read as stricter than it is. The RETURNED list still carries it so `--dry`
  prints it (`test_NEGATIVE_the_summary_never_counts_a_QUEUED_name_as_REJECTED`).
- **`AGE_OUT_DAYS = 14`** = `promo_circuit.RETAG_RESET_DAYS`, the sweep's own
  "campaign over". An add with no roster tag for that long is flipped to
  `aged_out` and leaves the universe on the next scan with no code change; so is
  one that stops resolving (the SDIG case). A later tag restarts the cycle —
  the ticker is a candidate again and is re-validated, counted against the cap.
- **`uni` is `full` MINUS this lane** (`BASE_COMPONENTS`). Otherwise a name this
  lane added would read back as `in_universe` forever and could never age out.

## The universe wiring, and a bug fixed on the way

```python
"full": ("russell3000", "sp1500", "curated", "themes", "traders", "promo")
```

`fetch_promo_adds()` **fails EMPTY, never raising** — it sits inside `full`, and
a Mongo blip must cost the handful of curated adds, never the ~2,700-name
universe every scan and board runs on. Band `_EXPECTED_COUNTS["promo"] = (0, 200)`:
zero is the legitimate starting state, and the upper bound (12/run × 14 days =
168 steady state) is the real guard.

**Bug fixed:** `fetch_trader_adds` shipped with a `(0, 200)` band in 2026-09-12
and was never added to the `_count_guarded` list at the bottom of `universe.py`
— so `LAST_COUNTS["traders"]` had **never been written** and that band was
documentation, not enforcement. Both curation fetchers are now wrapped.
`_record_count` records and logs ERROR outside the band; it **never rejects**,
so the fail-EMPTY contract and the universe size are unchanged. Observability
only. The negative test pins it: a 201-name source logs ERROR, records
`ok: False`, and still returns all 201 names.

**Bug fixed:** `traders.curate._warm_cap` imported `supply_demand.shares_cache`,
which does not exist. The `ModuleNotFoundError` was swallowed and **every trader
add landed with `market_cap: None`** — so a fresh add sat in `full` looking
covered while `zone_store` (KNOWN cap over `MIN_CAP_USD`) skipped it. It now
calls the real engine, `sepa.cap_warm.warm`, and reads the cap back. The promo
lane uses the same `warm_cap`.

**2026-09-21 — a failed warm no longer erases a cap the lane already had.** The
Massive reference call at gate 2 returns `market_cap`, and it lands on the added
row. `warm_cap` returns `None` whenever Massive or the shares collection is
unreachable, and the stored row used to take that `None` verbatim — a name the
reference had already sized went back to reading as *unknown cap*, which
`zone_store`'s `MIN_CAP_USD` gate treats as "no bands". The warmed cap still
wins when it exists; the reference cap is the fallback; neither present stays
`None`, never a guess. Pinned by
`test_NEGATIVE_a_FAILED_cap_warm_never_ERASES_the_reference_cap`,
`test_a_SUCCESSFUL_cap_warm_WINS_over_the_reference_cap` and
`test_NEGATIVE_no_cap_anywhere_stays_None_it_is_never_INVENTED`.

**2026-09-21 — an unreadable tag collection now stands the lane DOWN instead of
ageing out every add.** `_live_tags()` returned `[]` when `promo_circuit_tags`
was missing or its `find` raised. `run()` handed that empty set to `age_out()`,
which reads "not in the live set" as *campaign over* — so one Mongo blip on the
tag collection wrote `aged_out` over **every** added row and emptied the promo
component out of `full` with a real write. `_live_tags()` now returns `None` for
unreadable (an empty list stays a real answer: nothing is tagged right now), and
`run()` returns `{"error": "tags unavailable"}` without touching the collection
— the same fail-CLOSED shape the unreadable-universe branch already had. Pinned
by `test_NEGATIVE_an_unreadable_tag_collection_returns_None_not_an_EMPTY_set`,
`test_NEGATIVE_a_MISSING_tag_collection_returns_None_not_an_EMPTY_set`,
`test_NEGATIVE_it_stands_down_when_the_TAGS_cannot_be_read`,
`test_NEGATIVE_a_MISSING_tag_collection_also_stands_down` and — the other side —
`test_an_EMPTY_but_READABLE_tag_collection_still_ages_out`.

## Endpoints

| route | what |
|---|---|
| `GET /catalysts/promo-curate?limit=` | every row newest-first, plus cumulative `added` / `rejected` / `aged_out` from the rows, and `queue_remaining` / `populations` / `last_run_at` / `last_run` from the LAST RUN's summary doc, plus `measured` |
| `GET /catalysts/promo-curate/tags` | `{SYM: {accounts, tier, first_tagged_at, added_at}}` for the 🎪 origin chip, plus `measured` |

`MEASURED` is `None` until the study's `--emit-measured` JSON is pasted in; the
chip reads *"measurement pending"* until then, which is the truth.

**2026-09-21 — `queue_remaining` and `populations` come from the RUN, not the
rows.** Both counters were rebuilt at the endpoint by counting stored rows with
`reason_class == "capped"` / `"in_universe"` — and `run()` writes neither. A
name already in the universe is *counted and never written* (writing it would
invent an add it never made), and a name over the per-run cap is *queued, not
refused* — it gets its row on the run that actually admits it. So the endpoint
served **0 forever**, whatever the lane did, and `queue_remaining` is precisely
the number the spec named as the tell for tier starvation. A live run now writes
one summary doc to `promo_curate_runs` (`at`, the four counts, `universe_before`,
the `populations` split, `added_symbols`), `promo_curate.last_run()` reads the
newest, and the endpoint serves `queue_remaining` / `populations` /
`last_run_at` / `last_run` from it. Before any live run the answer is `null` and
`{}` — a `0` would read as a drained queue. A dry run records nothing; a failed
summary write never breaks the run (curating the universe is the job, the audit
counter is not worth an exception out of the cron). Pinned by
`test_a_live_run_PERSISTS_one_summary_doc_carrying_queue_remaining`,
`test_NEGATIVE_the_ROWS_can_never_reconstruct_queue_remaining_or_in_universe`,
`test_NEGATIVE_a_DRY_run_records_no_summary_and_no_row`,
`test_NEGATIVE_a_summary_write_failure_never_breaks_the_run`,
`test_the_rows_endpoint_serves_queue_remaining_from_the_LAST_RUN` and
`test_NEGATIVE_the_endpoint_serves_NULL_not_ZERO_before_any_run`.

## Running it

```bash
python -m catalysts.promo_curate --dry
python -m catalysts.promo_curate --recheck
```

`--dry` writes nothing and prints exactly what a live run would add, refuse, age
out and skip, with the population split.

The cron line runs at 08:10 ET, ten minutes after `traders.curate`, so the two
never race the universe read.

**INSTALLED 2026-09-21** on his "Yes". A deploy does not ship a crontab change —
the cron container bind-mounts `cheetah-market-app/backend/crontab` from the host
tree, which sits on its own branch and diverges from the repo copy — so the line
was appended to that host file directly (backup:
`backend/crontab.crontab.bak-2026-09-21`) and the cron container was recreated so
supercronic re-read it. Verified in-container the same evening: the line is at
`/app/crontab`, supercronic parsed the file with **0 errors**, and
`catalysts.promo_curate` imports inside the cron image with its MEASURED verdict
attached. The first live run is 08:10 ET on 2026-09-22.

Until that run lands the lane contributes **0 names** and the audit endpoint
serves `queue_remaining: null` and `populations: {}` — "never ran", not "nothing
qualified".

## Dry run — 2026-09-21 (read-only, in the api container)

The module was piped to `/tmp` in `cheetah-market-app-api-1`,
`sepa.prices.load_prices` was replaced with a `price_cache`-only reader (no
fetch, no write) and the collection stub refused every write.

```
checked            374   tagged outsiders in the window, after the shotgun prune
universe_before  2,706   `full` MINUS this lane
added               12   ANGX BMNR BRUN EROC FCEL FPS GEMI HELP KEEL NUAI SNAP SWMR
queue_remaining     18   passed every gate, over the per-run cap — next run
aged_out             0   nothing added yet
skipped_rejected     0   no stored rejects yet
seconds          243.6   374 reference calls + 609 price_cache reads
```

| population | n | examples |
|---|---|---|
| `in_universe` | **187** | never fetched, never written |
| `adr` | 30 | NVO, NOK, SFTBY, BCS, VWAGY, PBR, SCNI, TURB, SKHY, ALAR |
| `not_common` | 17 | USO, VOO, VTI, SOXL, SOXX, TLT, GDX, EWY, MCHI, REMX, ETHA |
| `otc` | 1 | ADTX |
| `unknown` (fail closed) | 12 | SPX, NDX, TNX, TYX, DXY, STOXX, TZ_F — index/futures strings the board picked up. Since the step-2 reorder, `SPX`/`NDX` read `never_add` instead and cost no call; the rest still do |
| `inactive` | 0 | |
| reached the floors | 314 | of which… |
| → refused on **$2** | **153** | PFSA, ZCMD, NIVF, GLND, YCBD, GDC, TOPS, CUPR, WLDS, GNS |
| → refused on **$5M median-50d** | **112** | FTFT, KIDZ, HKIT, VMAR, GRML, VEEE, SPRU, XBIO, CPOP, CUE |
| → refused by `curate.validate` | 19 | QNME, USDE, SECZ, MEDS, HOST, PAAI, ADBT, NXAT |
| → **passed every gate** | **30** | 12 added, 18 queued |

The 30 passers are the critic's 30-name list, reproduced end to end. Three of
them are tiny and will be **blind downstream** (DFNS $7.7M, SKYQ $24M, XHLD
$118M — under `zone_store.MIN_CAP_USD`), and six are large names simply absent
from the index lists (UBS, STLA, MNDY, SNAP, CHYM, CBRS). Whether a big name
belongs in a promo-origin bucket at all is **his call**; the lane admits them
today and the chip says how they entered.

**The gate order paid for itself**: 60 of the 374 (ADR + ETF/ETV + OTC +
unknown) were refused on one reference call each and cost **zero** bar loads.
The `capped` rows are counted only AFTER validation — `traders.curate.run`'s own
order — so the 153 sub-$2 names cannot starve the handful that resolve
(`test_NEGATIVE_a_name_that_would_be_REFUSED_never_eats_a_cap_SLOT`).

Raw log: `scratchpad/promo-curation/dry_run_2026_09_21.log`.

## What this does NOT do

- It does not decide that a promo tag is worth trading. That is the study.
- It does not push, gate an alert, or enter. The module's AST guard pins that it
  imports no `notifications` / `push` / `alert_gates` / `entries`;
  `trading.safety_floor` is the one allowed name under `trading`, a pure
  constants module holding the $2 floor. That exception is itself pinned
  (2026-09-21): `trading/__init__.py` is empty and `safety_floor` imports only
  stdlib, so nothing broker-side loads with it — a test fails the moment either
  changes. Whether the lane may import under `trading` at all is his call; the
  spec's §3.2 wording is "never imports trading".
- It does not apply the reference-type gate to `traders.curate` — which would
  have refused IGV/XLE/JETS/SMH, four ETFs that lane added. Changing that lane's
  rule is his call.
- It does not refuse the large names the lane admits (UBS, STLA, MNDY, SNAP,
  CHYM, CBRS are simply absent from the index lists). Refusing them would be a
  NEW gate; today the lane admits them and the chip says how they entered.
