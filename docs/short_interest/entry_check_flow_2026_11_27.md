# 🩳 On-entry source check + the ✂️ 6-K split-word read (2026-11-27)

Ajay 2026-11-27, verbatim: "Anytime something is in our Gajjalas we need to initiate a flow checking these values" · "Can you double check short interest for these two please?"

Spec: sicheck rev 2 §3.2 + §3.3 + §4.2, package `si-io`. Modules: `backend/short_interest/entry_check.py` (NEW), `sec_fts.py`, `share_basis.py`, `source_audit.py`. Display and data quality only: no alert gate, rung, count, sort, push trigger, lane or trade reads anything here. Not a signal. UNMEASURED.

## What is built

### 1. The entry check (`entry_check.py`)

- **Queue.** `enqueue(symbols, session, source)` — `source` = `SRC_GAJJALA` (🚩 pass, every listed name) or `SRC_WATCH` (👀 minute loop, every Watch name; the hooks are package `entry-hooks`). One row per (session, symbol), `_id` = `"<session>|<SYM>"`, in `si_entry_checks` (`EC_COLL`). ONE skip read first (a row that already lists this source gets no write — the 👀 loop calls every minute), then ONE atomic upsert per remaining row (`$setOnInsert` + `$addToSet sources`; a DuplicateKeyError from two racing upserts → that one update again, once). A row is checked once a session: a second source only adds its word.
- **Spawn.** When a row of the session is `queued` or `running` (a child marks all its rows `running` up front, so a killed child leaves them `running`; a live child holds the lease and nothing spawns): ONE claim on the lease doc (`_id` `lease`) — free lease AND no spawn inside `EC_SPAWN_GAP_SEC` (= `EC_LEASE_SEC` = `share_basis.SB_ERROR_RETRY_MIN` × 60). A DuplicateKeyError = a child holds the lease, or one was spawned inside the gap → no spawn. Claimed → ONE detached child, `ARGV_CHILD` = `python -m short_interest.entry_check --child` (fixed argv), through `chart_maps.gajjala.run_1m._popen`.
- **Child.** `run_child()` claims the lease (`find_one_and_update` + upsert; no lease doc → created and held), reads the `queued` + `running` rows once: a row of an earlier ET session → `failed` (`old_session`); a `running` row (left by a killed child) → `queued` again and run. At most `EC_MAX_PER_RUN` (= `share_basis.SB_QUEUE_MAX`) names, heartbeat after every name (a taken-over lease stops the run; its rows stay `running` for the next claim). Three phases over the EXISTING share-basis steps:
  - A. no usable SI record → `no_record` (no outside call); `share_basis.is_due` → `share_basis.refresh_symbol` (`ran`, or `failed` when `ref` / `sec` / `splits` / `sec.fts` holds an error or is failed / blocked — named in `failed_subs`); not due → `held`.
  - B. ONE bulk second-float read for the names whose `mfloat` is not fresh (`share_basis.fetch_mfloats`, `SB_MFLOAT_CHUNK` names a GET, `client.SI_BULK_SLEEP_SEC` between GETs, then `store_mfloats`): `off` (`SB_MFLOAT_WHEN`) · `held` (fresh) · `ran` · `failed`.
  - C. `share_basis.widen_splits` when `needs_window` (`ran` / `failed` / `held`); `share_basis.fts_split_step` (`stored` → `ran`, `failed`, `off`, else `held`; a split-word read written by phase A's refresh also counts `ran`); then the block through THE engine (`read.si_map`) → `result` = `source_check.audit_row(...)` + `flags` (the flag keys). Status `done`, or `failed` + the exception TYPE (never its text).
  - The lease is released in a `finally` (a clean exit allows the next spawn at once).
- **The sentence** `words(row)` (pure), built from `steps`; an `off` step is never named; a `done` sentence ALWAYS ends "Yahoo's float is not re-read by this check." (`TEXT_YAHOO` — a forced Yahoo re-read is HIS CALL #13):
  - done — `checked 11/27 10:00 ET when it listed on 🚩 — re-read now: …; held from an earlier read: …; failed, the earlier read stands: … (sec). Yahoo's float is not re-read by this check.`
  - queued / running — `queued 11/27 10:00 ET when it listed on 👀 — not checked yet.`
  - failed — `check failed 11/27 10:00 ET (ValueError) — the chip shows the last stored read.`
  - no_record / junk → None.
- **Read API** (K-2): `load(symbols, session)` (ONE `$in` find, `{}` on any failure), `entered(session, source=None)` (sorted; `[]` on any failure; `strict=True` raises — the nightly audit names a read fault; judgement call: a keyword-only addition to K-2), `words(row)`.
- **Switch:** `EC_WHEN = "on"` (`EC_MODES`; HIS CALL #14 — any other word: nothing queued, nothing spawned).
- **Mongo operators:** only `$or / $and / $ne / $lte / $exists / $in` in a filter and `$set / $setOnInsert / $addToSet` in an update (the test fake refuses every other). TTL `GC.LEDGER_TTL_DAYS` days on `at` (best-effort, the `bar_close.ensure_index` shape); the lease doc has no `at`.
- **CLI:** `python -m short_interest.entry_check --child` · `--show [--session D] [--symbols A,B]` (prints rows + their sentence, writes nothing) · `--enqueue --symbols A,B --source gajjala|watch`.

### 2. The ✂️ 6-K split-word read (`sec_fts.read_split`, stored as `sec.fts_split` — K-1)

- A SIBLING of `sec.fts`: `sec.fts`, `FTS_ISSUANCE_PHRASES` and `read_issuance` are unchanged.
- `FTS_SPLIT_PHRASES = ("share consolidation", "reverse stock split")` (MINE, chosen by the probe gate below), `FTS_SPLIT_DOC_TYPES = ("6-K", "EX-99")` (MINE — a hit counts only on the report itself or an EX-99 exhibit; a contract or instrument exhibit carries adjustment boilerplate), `split_doc_ok(file_type)`. The raw hits are filtered by `split_doc_ok` BEFORE `by_accession`. Switch `FTS_SPLIT_WHEN = "on"` (HIS CALL #11; any other word = no call, status `off`).
- Window `since` = min(`sec.since`, the held ok second float's date). The 6-K listing for it comes from the SAME submissions answer (`fetch_filings(wide_since=)`, no extra SEC call). ONE extra efts GET per refresh, only when the held answer does not hold (newest 6-K, window, `sec_fts.holds`). The efts stop `state|fts` is honoured; a 403 / 429 sets it and never stops data.sec.gov. A refresh with no listing read carries the held `fts_split`. Status rule as every SEC sub-doc.
- `share_basis.fts_split_step(sym)` — the same read outside a refresh (phase C): `off` · `test` · `no_doc` · `held` (no call) · `stored` · `failed`. A needed read is ONE data.sec.gov listing GET + at most ONE efts GET; the write is `$set sec.fts_split` on a checked doc, never an upsert.
- `share_basis.py:837` and `client.py` are NOT touched; share_basis keeps its two `basis_math` import lines.

#### The probe gate (2026-11-27 ~10:15 ET)

9 efts GETs (3 candidates × BDMD / POM / NXAT, forms 6-K, generic User-Agent, 1 s apart; windows BDMD / NXAT since 2025-12-31, POM since 2026-03-31). All 9 answered 200. RAW answers: `backend/tests/fixtures/sec_6k_split_probe_2026_11_27.json` (no value typed). The hit table after `split_doc_ok`:

| phrase | BDMD | POM | NXAT | must-NOT hit | admitted |
|---|---|---|---|---|---|
| "share consolidation" | 11-16 | 10-19, 10-02, 09-04 | 11-23, 11-13, 07-10, 05-27 | none (BDMD 09-30 matches only in EX-10.1 / EX-10.2 → dropped) | yes |
| "reverse stock split" | none (09-30 EX-10.2 dropped) | 10-09 | 11-17, 01-09 | none | yes |
| "reverse share split" | none (09-30 EX-10.1 dropped) | none | **10-05 (EX-99.2, warrant exchange)**, 03-17 | NXAT 10-05 | **no** |

Must-hits met: BDMD 11-16 (`0001104659-26-128404`), POM 10-19 (`0001213900-26-110501`), NXAT 11-13 (`0001829126-26-012418`). Must-NOTs (BDMD 09-30, POM 09-29, POM 11-04, NXAT 10-05, NXAT 09-11) hit by no admitted phrase. → `FTS_SPLIT_WHEN = "on"`. The gate differs from the spec's expectation in one way: "reverse stock split" is admitted too (the rule is mechanical; it adds POM 10-09 and NXAT 11-17 / 01-09). Re-run: each saved answer carries its exact `url` (9 GETs, ≥ 0.8 s apart, the same User-Agent); `tests/test_si_split_filings_2026_11_27.py` rebuilds the table above from the saved answers through `parse_hits` → `split_doc_ok` → `by_accession`.

The search finds MENTIONS: a proposal, a vote notice (BDMD 11-16, NXAT 11-13 / 11-23) and an executed split read the same, and so can a later filing that only recalls an old split (NXAT 01-09 / 05-27 / 07-10). Precision is UNMEASURED beyond these three filers.

### 3. The audit's 🚩 group

`source_audit.GROUPS` gains `entered` (🚩) — see `docs/short_interest/source_audit_2026_11_26.md` (2026-11-27 paragraph).

## Tests

- `backend/tests/test_si_entry_check_2026_11_27.py` — enqueue (one row, the skip read, the other source, the interleaved race, junk, pytest guard, switch, spawn gap, held lease, clean release), run_child (no lease doc, held lease, re-queue, phase order, chunking, no_record, a raising step, old session, take-over, release on every path, the cap, operator refusal), steps + words, load / entered, imports, CLI, the audit group.
- `backend/tests/test_si_split_filings_2026_11_27.py` — the gate from the RAW answers, `split_doc_ok`, `read_split`, K-1 exact shape through `refresh_symbol`, held / re-asked, switch off, `sec.fts` byte-identical, 403 / 500, `fts_split_step`.
- Pins moved (PIN MOVED 2026-11-27 comments): `test_si_sec_fts_2026_11_26.py` (one more efts GET; the fake routes the split query), `test_si_share_basis_2026_11_24.py` (`sec` keys + `fts_split`), `test_si_mfloat_2026_11_26.py` (`fts_split.since` reaches the second float), `test_si_source_audit_2026_11_26.py` (four groups; `rule_text` pinned to the live builder).

**2026-11-27 refix (stuck `running`).** The child marks all its rows `running` before the first name, so a child killed after that mark (SIGKILL / deploy) left no `queued` row and the spawn step never fired again: the names read "not checked yet" for the rest of the session. The spawn step now looks for `queued` OR `running` rows of the session; the lease (a live child holds it) and `EC_SPAWN_GAP_SEC` still stop a second child. Pinned by `test_a_child_killed_after_marking_its_rows_running_is_spawned_again_once_its_lease_runs_out` and its three negatives.

**2026-11-27 refix (critic crit3).** (1) The SEC pace was per process only, so the cron entry-check child and the api's on-view worker could each start a data.sec.gov GET at the same moment. `share_basis._sec_wait` now also claims a host-wide slot in ONE atomic `find_one_and_update` on `si_share_basis` `state|sec_pace` (`next_at = max(now, next_at) + SB_SEC_MIN_INTERVAL_SEC`, wall clock) and sleeps until it; the in-process lock and gap stay. Any Mongo fault or junk answer → the in-process pace alone, never a raise; a slot more than `SB_HTTP_TIMEOUT_SEC` ahead is a broken doc — reset by compare-and-set, never slept. The 403 / 429 stop (`state|sec`) is unchanged. (2) Phase C no longer asks `fts_split_step` (one SEC listing GET) when phase A's refresh ran and its `sec.fts_split` is good, error-free and for the same window (`SB.split_since`): the step reads `held` (`ran` when the refresh wrote a fresh read). Pinned by `backend/tests/test_si_crit3_fixes_2026_11_27.py` (two real processes, the fault / junk / far-slot / 403 negatives, refresh-not-ran / failed / moved-window negatives).

## NOT done here

The chip / hover use of `fts_split` and the entry sentence (`read.py`, package si-pure); the two entry hooks and the watchdog list (package entry-hooks). A name queued while no pass or loop runs waits for the next `enqueue` call (R3). Yahoo's float is not re-read (HIS CALL #13).
