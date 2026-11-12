# Shadow day tags — GD3w, GD4, GD6b, GD7, LD3i, LD9 recorded forward, one record per session (2026-11-11)

**Record only.** Nothing is served: no page, no word, no column, no gate, no mute, no push reads these files. No Mongo
write, no broker import, no provider fetch. Prior on every tag = **NULL** (the in-sample study, below).

## His words

Relayed 2026-11-11: Ajay said "Do your receommendations" to "say yes to 1, 5 and 7 now". Proposal 5 of
`eod-audits/research/2026-11-11_track_record_patterns/REPORT.md`: no day word on any surface yet; record the six tags
forward as shadow day tags under a prereg; re-read at 30 weeks.

## What it records

One line per closed market session in an append-only store, eight tag-forms each. Formulas = the study's
(`STUDY/day_indicators.py`, sha256 `9bef2f1b…0dcbc`), function for function; pinned on all 22 study sessions × 8 forms
against `STUDY/days.csv` (`backend/tests/fixtures/gajjala/shadow_day_tags_days_2026_11_11.csv`).

| form | ON when | read time | THEIRS / MINE (the study's note) |
|---|---|---|---|
| GD3w_pre | Pop & Drop failed share > 50 % over the prior 5 sessions | prior sessions | 5 sessions + 50 % MINE |
| GD4_pre | GG's halving below 1 (A+ losses since the last win) | exits strictly before **09:30** (= `ET_RTH_OPEN`) | halving THEIRS; win reset MINE (lane HIS CALL #18) |
| GD4_by1030 | the same | exits strictly before 10:30 (`T2_FIRST_HOUR_END_ET`) | halving THEIRS; win reset MINE |
| GD6b_pre | strip population below the UPPER median of ≤ 10 prior sessions | last pass at or before **09:29** | median + window MINE |
| GD6b_by1030 | the same | last pass at or before 10:30 | median + window MINE |
| GD7_by1030 | QQQ and IWM both red, open → 10:30 | bars closed by 10:30 | both red MINE |
| LD3i_pre | IWM 9 EMA under 21 at the previous close | prior session | 9/21 THEIRS |
| LD9_pre | ≥ 4 of 8 mega-cap pillars under 9 & 21, 9 falling | prior session | 9/21 THEIRS; list + 4 MINE |

Two "before the open" cuts, kept exactly as the study: GD4_pre folds exits strictly before 09:30; GD6b_pre reads the
last strip pass at or before 09:29. "Median" = `sorted(h)[len(h) // 2]` — the upper middle on an even count; ON is
strict (`v < median`). The MINE numbers (5 / 10 sessions, 30-minute staleness, 50 %, the 8-name list and its 4, "both
red", the history floor 5, the 6-pillar floor) are RECORDED as the study had them; recording is not approving them as
rules (HIS CALL #5). No repo constant holds any of them (grepped 2026-11-12: `LEDGER_SPAN_SESSIONS` 5 / `_LONG` 10 are
the 🏁 day-picker spans, a different meaning, never used by the study).

## MISSING, never False

A tag is `{"status": "ok" | "missing", "on", "value", "detail", "why", "asof"}`; MISSING carries `on: null` and a
`why`. GD3w — fewer than 5 prior sessions, or held + failed == 0, or the GG5 rows unread. GD4 — the GG5 rows unread.
GD6b — no pass at or before the read time, a pass older than 30 minutes, no `n_population`, or fewer than 5 history
values. GD7 — QQQ or IWM bars absent. LD3i — no IWM daily bar for the previous session. LD9 — fewer than 6 pillars with
a row. A non-finite value reads MISSING.

**GD7 is BEST-EFFORT.** The QQQ / IWM minute bars land in `intraday_cache` only when some reader asks for that symbol-
day (`daytrading/data.py:227` → `_mongo_put_day`); no scheduled job is known to ask. 11-10 and 11-11 were still absent
on 11-12. GD7 is recorded MISSING and filled by a later run's `missing_retry` when the bars land. Warming them daily =
a provider fetch on a schedule = HIS CALL #7.

## How it runs

- `backend/scripts/shadow_day_tags_probe.py` — container side, read-only, piped on stdin (never copied into `/app`).
  Prints the raw inputs: the GG5 🏁 rows exactly as the study's `dump_rows.py` builds them, the last strip pass at
  09:29 and 10:30 per session, QQQ / IWM rth minute bars closed by 10:30, the IWM daily frame (house cache) with EMAs
  9 / 21, the eight pillars with EMAs 9 / 21 / 50, the market days since 2026-10-13 (`is_market_day`, holiday-aware:
  2026-11-26 is never a session), `last_closed_session` (16:00 ET + `ledger.SETTLE`), and every constant by name
  (`GG_LOSS_RISK_CUT`, `ET_RTH_OPEN` read with `ast`, no import of `trading` / `daytrading`). **2026-11-12
  refix:** the probe sends NO `create_index` to the live Mongo. `main()` pre-sets `portfolio.store._db` and
  `sepa.prices._mongo_coll` to its own handle (as `track_record_snapshot_probe.py` does), so `_get_db`
  (portfolio_holdings) and `_get_mongo` (price_cache) return early; the IWM frame is read with the probe's own
  `price_cache.find_one` and reshaped by `cached_frame_meta`'s own helpers (`_cut_foreign_head`,
  `_drop_phantom_tail`, imported), pinned equal to `cached_frame_meta` by a test.
- `backend/scripts/shadow_day_tags_lib.py` — stdlib only, Python 3.9: the formulas, the store.
- `backend/scripts/shadow_day_tags.py` — the host CLI; ONE `docker exec` per run; prints one JSON summary line.

```
python3 backend/scripts/shadow_day_tags.py
python3 backend/scripts/shadow_day_tags.py --out DIR --recompute 2026-10-13..2026-11-11
```

Flags: `--session D` (default: the probe's last closed session; a later one is refused), `--out DIR` (default
`/Users/ajay/clinet-test/eod-audits/shadow-day-tags`), `--from-json FILE` (no probe), `--recompute A..B`,
`--container NAME`, `--dry-run`. Exit **0** ok, **2** refused (corrupt store, unclosed or closed-market session, probe
failure). **The scheduled task must surface an exit 2** — a refused run blocks until a human reads it.

## The store

- `day_tags.jsonl` — one line per record or revision: `schema, session, rev, recorded_at_utc, in_sample (session <
  2026-11-12), late (session < the run's target), tags {8 forms}, changed [forms] | null, constants, source_tags,
  inputs_sha256, inputs_file, probe_generated_utc`. Never rewritten: every write is temp file + `os.replace` of the old
  bytes + the new lines, so the old bytes stay a prefix.
- `inputs/<run date>.json.gz` — the probe blob (sorted keys, gzip mtime 0), written only when a line is appended,
  BEFORE the JSONL. An inputs file no line references is the orphan of a killed run: never read, never overwritten,
  listed as `orphan_inputs`; the run takes the next free name `<run date>.r2.json.gz`, `.r3…`.
- Revisions: the first compute of a session = `rev` 0. A re-run equal on (status, on, value) for all eight forms → no
  line. On the run's target, any change is a new `rev` EXCEPT ok → missing (the old ok stays — passes expire at 30
  days). Under `--recompute` every change is a revision, ok → missing included, with its `why`.
- **Gaps / late** [C3]: each run computes its target plus every market day from 2026-11-12 up to it with NO record (a
  host sleep, a skipped slot) as `rev` 0 with `late: true`, and re-reads every earlier forward session whose latest
  record still has a MISSING form (`missing_retry`) — there only missing → ok is taken (judgement call: a retry never
  moves an already-ok form). A gap older than the 30-day pass TTL records GD6b MISSING honestly. A late record reads
  data stored after its session: GD4 / GD6b / GD7 read by timestamp ≤ the cut (as-of safe); GD3w reads prior grades,
  which may be FINAL on a late run and still settling on time. `late` is recorded so the read can report it.
- A line that does not parse, a cut last line, or a rev gap → `StoreCorrupt`, exit 2, nothing written.

## The read

Pre-registered in `backend/tests/fixtures/gajjala/shadow_day_tags_prereg_2026_11_11.md` (+ `.sha256`): forward only
from 2026-11-12, ON = worse, two placebos (free day shuffle + run-order permutation, 20,000 draws each, both must pass),
Bonferroni over the (tag-form, page) reads, ONE read date when every page holds `MEASURE_FLOOR_WEEKS` entry weeks. A
positive read ships nothing: a PAPER variant is HIS CALL. **2026-11-12: the prereg is FROZEN** (sha256 in the
`.sha256` beside it), before the first forward record (session 2026-11-12). Read count settled by the main session:
**20 reads** (6 GD forms × gg5 / gg1 + 2 LD forms × luk / lukx / gg5 / gg1 = the study's IND rows = the lib's `READS`),
**alpha = 0.05 / 20 = 0.0025** — the spec's "18" (0.0028) miscounted the GD forms. The circular-shift placebo stays
rejected: its floor 1 / n ≈ 0.0067 at 30 weeks is above 0.0025.

## In-sample prior (STUDY/REPORT.md, 22 sessions, EXPLORATORY)

GD3w ON 5 / OFF 12 days, +0.05R vs −0.16R, p 0.18, inverted; GD4 pre 5 / 15, +0.02R vs −0.17R, p 0.16; GD6b pre 7 / 6,
+0.07R vs −0.26R, gap +0.34 [+0.14, +0.55], p 0.005, INVERTED (the one read that beat the placebo; fails Bonferroni);
GD7 5 / 13, +0.04R vs −0.27R, p 0.10, inverted; LD3i 3 / 4, too few days; LD9 5 / 2, too few days.

## Live proof (2026-11-12, after the close — read-only, scratch dir only)

Run against `cheetah-market-app-api-1` (origin/main) at 16:31 ET, probe `generated_utc` 2026-11-12T21:31:29Z,
`last_closed_session` 2026-11-12. The real default dir was NOT written: both runs went to the scratch dir, so
neither is a forward record. Re-run once more at 16:34 ET with the probe as it stands after the prereg freeze
(probe sha256 `6838c056…`, lib `5f363a9c…`, CLI `ed54673b…`): every tag identical.

```
python3 backend/scripts/shadow_day_tags.py --out /private/tmp/claude-501/-Users-ajay-clinet-test/2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/rec157/day-tags-test --recompute 2026-10-13..2026-11-11
python3 backend/scripts/shadow_day_tags.py --out /private/tmp/claude-501/-Users-ajay-clinet-test/2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/rec157/day-tags-test
```

Run 1 (`--recompute`): exit 0, 22 lines appended (`rev` 0, `late: true`, `in_sample: true`), inputs
`inputs/2026-11-12.json.gz`, `gap_sessions` [], `orphan_inputs` [].

**Live vs `days.csv`: 176 of 176 cells equal, 0 differences** (status, `_value`, `_on`; compare script
`rec157/day_tags_compare.py` in the scratch dir).

| form | equal to days.csv | ON days | OFF days | MISSING |
|---|---|---|---|---|
| GD3w_pre | 22 / 22 | 5 | 12 | 5 |
| GD4_pre | 22 / 22 | 5 | 17 | 0 |
| GD4_by1030 | 22 / 22 | 5 | 17 | 0 |
| GD6b_pre | 22 / 22 | 7 | 6 | 9 |
| GD6b_by1030 | 22 / 22 | 6 | 6 | 10 |
| GD7_by1030 | 22 / 22 | 6 | 14 | 2 |
| LD3i_pre | 22 / 22 | 15 | 6 | 1 |
| LD9_pre | 22 / 22 | 14 | 7 | 1 |

Why the expected differences did not appear: GD6b on 10-13 was already MISSING in the study (no pass stored at or
before 09:29 / 10:30 that day), so its pass TTL changes nothing; the later sessions' passes have not expired yet (a
`--recompute` after their 30 days CAN move GD6b ok → MISSING, recorded as a revision). GD7 on 11-10 / 11-11 is still
MISSING live: the IWM minute bars have since landed in `intraday_cache`, the QQQ ones have not (probe `asof`:
`qqq_last_date` 2026-11-09). No GD3w / GD4 grade moved since the study's dump.

Run 2 (plain, target 11-12): exit 0, appended **11-12 only** (`rev` 0, `late: false`, `in_sample: false`),
`gap_sessions` [], `missing_retry` [] (in-sample sessions are never retried), inputs `inputs/2026-11-12.r2.json.gz`
(the run-1 file is referenced, so never overwritten), the run-1 bytes kept as a prefix. 11-12 read: GD3w 0.45 off,
GD4 0.25 on (both cuts), GD6b_pre 55 off, GD6b_by1030 357 on, GD7 MISSING (QQQ / IWM bars absent), LD3i 0.5 off,
LD9 2/8 off. This is a SCRATCH record, not a forward record.

## Tests

`backend/tests/test_shadow_day_tags_2026_11_11.py`: the 22 × 8 pin, both read times, the upper median, every MISSING
rule and its NEGATIVE, the store (equal → one line, change → rev 1 byte-kept, missing → ok retry, ok → missing only
under `--recompute`, corrupt → exit 2 bytes unchanged, unclosed refused, dry run), gaps / late / Thanksgiving, the
killed run (orphan listed, `.r2`, orphan bytes kept), the market-day walk = `key_levels.prev_market_day` over 2026, the
copied `risk_after` = the lane's over a grid, `trade_of` = the study's, and the source guards (nothing outside
`scripts/` and `tests/` imports the package, the probe holds no Mongo write and no `trading` / `daytrading` / provider
import, lib + CLI parse as Python 3.9 and import the stdlib only, the crontab names none of the files). The prereg pins
skip until it is frozen. The live-proof sequence is replayed hermetically on the fixture (recompute then plain run: the
target only, `.r2` inputs, prefix kept; NEGATIVE an in-sample MISSING is never retried and an equal re-run writes
nothing).
