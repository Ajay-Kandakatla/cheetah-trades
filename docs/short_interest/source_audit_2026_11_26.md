# 🧮 Float and share-count source audit — nightly, and the re-runnable dry run (2026-11-26)

Ajay 2026-11-26 ~21:20 ET, verbatim: "Also the Float share count issue and SI discrepancy happened too many times need to do something about it".

Spec: floatguard rev 2 §3.6 / §3.7, package `be-audit`. Module `backend/short_interest/source_audit.py`. Display only: no rule, gate, sort, push or lane reads it. What two data providers say — neither was checked against a filing. Not a signal. UNMEASURED. Not advice.

## 2026-11-26 — what was built

### What runs, and when

The 20:15 ET nightly (`chart_maps.gajjala.nightly`, `grade` step) runs it after the 🏁 SI track record, in its own fence, through `high_si.source_audit_night(now)` -> `source_audit.audit_night(now)`. The log line holds its answer under `gajjala_si_audit`. A raise lands under `gajjala_si_audit.error` (`audit: <Type>`), never in GG5's `errors` and never in the exit code; a broken module is fenced too. `STEPS` and the crontab are unchanged.

One night, in order:

1. **Names.** Three groups, each read in its own try (a group that cannot be read is empty and named in `faults`; the others stand):
   - 🩳 `listed` — the symbols of tonight's 🏁 session doc (`si_track.session_doc(st, si_track.tonight(now), strict=True)`);
   - 🔭 `followed` — `si_follow.tracked` (pins included);
   - 👀 `watch` — `gajjala_watch.run_rules.watch_names(db, now)`.
   Spelled once (upper, de-duplicated, order = listed, followed, watch).
2. **Second float, in bulk.** For EVERY `share_basis.checked_symbols(db)` name: `share_basis.fetch_mfloats` one chunk of `SB_MFLOAT_CHUNK` names per GET, `SI_BULK_SLEEP_SEC` between GETs, at most `max_refresh()` GETs; stored by `share_basis.store_mfloats`. Skipped when `SB_MFLOAT_WHEN` is not `on`.
3. **One budget of outside reads** (`max_refresh()` = `GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS`, read at call time; this job's own instance), tonight's names first:
   - `share_basis.refresh_symbol(sym, db)` for tonight's names that `share_basis.is_due` (a name with no basis doc and a usable record is due; a `no_record` name is never refreshed — the share_basis rule). Its SEC pacer and 403 / 429 stop are its own.
   - `share_basis.widen_splits(sym, db)` for every checked name whose second float is older than its splits window (`share_basis.needs_window`).
   - Names past the budget are counted `deferred` (names, not reads — 2026-11-27) and wait for the next night. `SI_BULK_SLEEP_SEC` between these reads too.
4. **Blocks** through THE engine: `read.si_map` (which runs `source_check.compare` / `apply` inside `si_block`) in chunks of `MAP_MAX_SYMBOLS`.
5. **Rows**: one `source_check.audit_row(block, basis_doc, groups)` per name. A name with no chip is state `no_si` with no numbers (never 0).
6. **One write**: `st.set_state("si_source_audit|<session>", doc)`, read back fault-aware (the store's upsert swallows a raise), then the pointer `si_source_audit_latest` = `{"date", "at"}`. A failed write is the fault `write` and the pointer is not moved.

### The log shape (gajjala_state)

```
si_source_audit|YYYY-MM-DD = {"date", "at", "version": 1,
  "names": {"listed": [...], "followed": [...], "watch": [...]},
  "rows": [audit_row …],                     # the three groups' rows only
  "texts": {SYM: "the Share counts sentence" | None},
  "counts": {"n", "compared", "differ", "contested", "held", "window", "states": {state: n}},
  "calls": {"float_gets", "refreshed", "widened", "deferred"},
  "modes": {"contest", "contest_by", "min_rel", "mfloat"},
  "faults": [...]}
si_source_audit_latest = {"date", "at"}
```

`audit_night` returns `NIGHT_KEYS` = `session, names (counts per group), rows, differ, contested, held, window, float_gets, refreshed, widened, deferred, written, faults`. Under pytest a night with no store or db injected returns `faults: ["no_store"]` at once (no Mongo, no call); a seam left None makes no call (the share_basis `kick` guard shape).

### The 🩳 fold

`high_si.block` serves `si_audit` = `source_audit.served_block(st, session, now)` in its own fence, right after `si_track`; a read fault serves `{"fault_text": high_si.SIA_FAULT_TEXT}` and the cards stand. It lives inside the 🩳 sub's closed ⓘ fold (`GgSiAuditSection`) — nothing new above the cards.

Served: title `🧮 Float and share-count sources · checked nightly`; summary `🧮 Sources · {c} EXTREME contested · {d} of {n} compared floats differ · {w} not compared yet`; the table (Ticker · Listed on · Float we use · Second float · Apart · Shares out we use · Share counts on file · Chip word), contested rows first, then the widest spread, then the symbol, cut at `GC.LEDGER_ROWS_MAX` with the shown line; the rule fold and the honesty line. No night on file -> `🧮 Sources · nothing checked yet` and the empty line, not a fault.

### 🏁 SI track record — one definition of "EXTREME vs High"

`si_track.record_session` stores the row's `tier` through `_ladder_tier(b)`: `basis.extreme_contest.from` when it is a house tier, else the block's own tier. Under the built default (`EXTREME_CONTEST = "flag"`) `from == to == tier`, so no stored row changes — a contested row differs from its no-second-float row in `flag_shorts` only (`⚠️ sources disagree` added). Under `hold` (his call #1) the chip says High but the 🏁 row keeps EXTREME, so the `tier_extreme` pattern keeps ONE definition.

### Budget and cost

About 8 float GETs a night for ~800 checked names, plus at most `max_refresh()` (120) refresh / splits reads, tonight's names first.

**Measured 2026-11-27 01:26 ET, read-only** (the 11-27 review: `share_basis.is_due` over the three groups' names, against the stored basis docs and SI records; no outside call, nothing written). Not a typed estimate — except the window row, which is NOT from that read (see below):

| | count |
|---|---|
| group names (🩳 + 🔭 + 👀, de-duplicated) | 92 |
| of them `is_due` | 92 (32 have no basis doc) |
| checked names whose second float predates their splits window — **the 11-26 probe, 124 of 693 names (frozen fixture `si_float_probe_rows_2026_11_26.json`), not re-read on 11-27** | 124 |
| the one budget (`max_refresh()` = `GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS`) | 120 |

Why the window row is the 11-26 count: a name needs the window read only when it holds an `ok` second float (`mfloat` sub), and on 11-27 ~01:55 ET the live store held **792 checked basis docs, 0 with a second float** — so over the stored docs the window count is 0 until the first deployed night writes second floats. The 124 is the 11-26 planner probe (the `693 569 124` line the [float accuracy guard](float_accuracy_guard_2026_11_26.md) re-run block prints).

Refreshes go first (`audit_night` step 4), so the arithmetic is: 92 full refreshes take 92 of the 120 reads, about **28 splits reads** are left a night, and — arithmetic on that 11-26 count of 124, not a measured 11-27 number — about **96 of the 124** window names are `deferred` the first night. While every group name stays due, about 92 full refreshes repeat every night and the window names drain at about 28 a night. The cap is NOT changed here. A separate budget for the widen (splits) step is **his call #14**.

## 2026-11-27 — review fixes

- **No 🏁 session doc is a fault.** `names` used to read a missing session doc as `{}`, so `listed` was 0 with no fault; if `si_track.record_night` had failed, the night wrote and moved the pointer with no 🩳 names and nothing said so. Now a missing doc (or one with no `rows` list) is the fault `listed`, in the returned faults and in the written doc's `faults`; the 🔭 / 👀 groups still stand and the pointer moves with the fault on record. A recorded session whose `rows` is an empty list is no fault (the 🩳 sub listed nobody). A CLI probe run before tonight's 20:15 ET record also shows `listed` — true, the doc is not there yet.
- **Float we use, with no second-float sub.** `source_check.audit_row` took `used` only from `float_sources`, which exist only when a `mfloat` sub is on file — the cell was blank for every such name (92 of 92 in the live `--stored` run). It now falls back to the block's own `float_shares` / `float_asof` / `pct_of_float` when `headline_basis` is `float`, through `source_check._float_used` — the same test `compare` step 1 uses (one definition). A stored `used` row still wins. The served block changed for CLRO in the frozen capture (no basis doc on file: its float cell now reads `888,130 · Yahoo, read 11/17 · 35.8%`), so the golden was regenerated for that one cell.
- **`deferred` counts names.** A due name past the budget whose splits read was also past it counted twice; it is now one name.
- The budget numbers above are now the measured 01:26 ET counts, not a typed "a few" — except the window row (124), which is the frozen 11-26 probe: 792 docs are checked now and 0 hold a second float until the first deployed night (re-checked read-only ~01:55 ET).

## The CLI — the re-runnable probe

```
python -m short_interest.source_audit [--dry | --stored] [--all] [--widen] [--symbols A,B] [--cuts] [--rows-out PATH]
```

- no flag: a real night (writes, like the nightly).
- `--dry`: the outside reads are made, NOTHING is written — the fetched second floats (and with `--widen` the wider splits reads) are laid over the stored docs in memory (`read.si_map(basis_over=…)`, built by `share_basis.mfloat_sub`, the same builder the store uses).
- `--stored`: no outside call and nothing written — the table over the docs as stored.
- `--all`: every checked name, not only the three groups (stored rows stay the groups' rows).
- `--cuts`: prints `source_check.cut_table(rows)` after the table.
- `--rows-out PATH`: writes `{"at", "scope", "modes", "rows"}` as JSON — a scratch or eod-audits path; a path inside the backend tree is refused (exit 2, nothing read).
- `--symbols`: narrows the rows printed, not the reads.
- The last line is `attempted writes: N` (every collection write method and every `set_state` asked, counted) — 0 under `--dry` / `--stored`.

## Re-run block (spec §5)

Read-only probe before deploy (the api container runs main, not the branch — never `docker cp` into it). Outside 09:30-16:00 ET, one container at a time:

```bash
docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 --env-file <600-mode key file> -v /Users/ajay/clinet-test/.wt-sishares/backend:/app:ro -v <scratch folder>:/out cheetah-api:latest python -m short_interest.source_audit --dry --all --widen --cuts --rows-out /out/audit_rows_dry.json
```

After the first 20:15 ET night on the deployed build:

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m short_interest.source_audit --stored
```

## Tests

- `backend/tests/test_si_source_audit_2026_11_26.py` — (2026-11-27: the missing-session-doc fault, the `used` fallback, `deferred` by name — each with NEGATIVES) the written night, the dry run (incl. `--widen` turning DKI from `window` to `contested` with zero writes), the CLI, the served block against the frozen golden `backend/tests/fixtures/si_source_audit_block_golden_2026_11_26.json`, the nightly fence, `card_pct` through `read.pct_of`, the 🏁 ladder tier; every NEGATIVE of spec §4.4.
- `backend/tests/test_si_source_audit_guards_2026_11_26.py` — display-only imports, no division, only high_si imports it, writes only through `set_state` and share_basis's writers, nightly S10 words, high_si's one `si_map`, si_track's import set — each with a planted NEGATIVE.

## NOT done here

- `backend/tests/test_gajjala_si_track_guards_2026_11_26.py` `IMPORTERS` must gain `short_interest/source_audit.py` (predicted pin move — main session).
- No ✨ entry (main session). No contracts.mjs block (main session).
- No word, tier, sort, gate or push changes: the audit only reads and logs.

## 2026-11-27 — the 🚩 group (spec sicheck rev 2 §3.3, package si-io)

Ajay 2026-11-27: "Anytime something is in our Gajjalas we need to initiate a flow checking these values". A fourth group, `entered` (word 🚩), is LAST in `GROUPS = ("listed", "followed", "watch", "entered")`: the names the 🚩 pass checked on entry that day, `short_interest.entry_check.entered(session, source=entry_check.SRC_GAJJALA, strict=True)`, read in its own try (a read fault is named `entered` in `faults`; the other three stand). A row queued only by 👀 Watch is never listed under 🚩; a row both sources queued is. Being last, the night's `max_refresh()` budget falls on it first. `RULE_HEAD` names the fourth list. Each built row gains `flagged` = the chip carries `source_check.SHORT_SOURCES`; `_word` and `_sort_key` treat `flagged` like `contested`. No new state: `WHY` and `source_check.STATES` are unchanged. With no entry rows the three groups are exactly as before. Display only; not a signal; UNMEASURED. The entry flow itself: `docs/short_interest/entry_check_flow_2026_11_27.md`.
