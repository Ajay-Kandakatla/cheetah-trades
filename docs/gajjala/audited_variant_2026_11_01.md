# 🧪 Gajjala · Audited (2026-11-01)

Spec: BUILD_SPEC gg-audited, revision 2. Tab `gajjala_audited` on Chart Maps, right after 🚩 Gajjala's. Variant `GGA`.
Claim prefix `GGA:`. **UNMEASURED.** Every rule on this tab read TOO SMALL in the 2026-10-30 replay. The 2026-10-14 study
of the 5-minute setups read NULL (`docs/gajjala/study_2026_10_13.md`). The tab makes no claim that it wins. Its 🏁 Track
record is operational accounting, not a backtest. **Every audited alert is recorded in shadow and never sent.**

## The ask, verbatim

Ajay, 2026-11-01:

> "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
>
> Gajjals-Audited
>
> So we can keep track of improvements on this tab"

## What it is: an overlay, not a pipeline

The audited tab has **no pass of its own, no scan, no cron line and no provider call.** It rides 🚩 Gajjala's 5-minute
pass (`run.run_pass`). After GG5 has read and stored every name, a fenced step (`audited_pass.run_step`) does the
following:

1. It takes the reads that pass just made, using the same Frames and the same detectors.
2. It judges every **A+** read against the ON rules of the registry (`audited_rules.py`).
3. It hands the surviving A+ reads to the same A+ gate (`alerts.run_pass`) on the audited store, with `mode="shadow"`.
   A read an ON rule removed is served as `aplus_held` (the word "A+ on the original, held here by the audit"). It is
   never hidden.
4. It writes **only** `gajjala_audited_*` collections.

GG5 and GG1 stay byte-identical. The step adds no key to GG5's pass doc or to `run_pass`'s return dict, and never
appends to `out["errors"]`. A failure inside the step is logged and goes no further. The three goldens are not
regenerated.

The board is the same `tab.build(…, variant=GGA)`, rendered by the same `GajjalaBoard` with `variant="gajjala_audited"`.
The audited tab adds these keys to the board:

- `audited`: the strip.
- `held`: the held-A+ section.
- `audited_compare`: on 🏁 only.
- `counts.aplus_held` and the legend row `aplus_held`.
- the tile's `gajjala.audit`.

The audit touches the A+ read only. 🧠 potentials, 📈 track and the 🧠 rows of 🏁 stay 🚩's. They are shown for
context and none is recorded on this tab (HIS CALL #6).

## The registry: `chart_maps/gajjala/audited_rules.py`

Each entry is a frozen `Rule` with these fields: id, name, date_added, status (`on` / `off` / `lane_only`), applies,
rule, params, source, GG's words, verdict, verdict_source, changes and note. `registry_rows()` serves the words. The FE
composes nothing. `rules_clause()` feeds the ℹ️ panel (see "The ℹ️ panel" below).

The frozen sources: the rule numbers below come from these files. They are read, never retyped.

- The prereg: `/Users/ajay/clinet-test/eod-audits/research/2026-10-30_gajjala_gates_prereg.md`.
  - Its sha256 is `4ebc30d20e7f3eb19aa6df5fbe2b620d9c19e0e22144ae6620e66ca7bf8d14b6` (report.md:5).
  - A byte copy is kept at `backend/tests/fixtures/gajjala/gates_prereg_2026_10_30.md`.
- The picks, from two files. Every row there reads **TOO SMALL (= UNMEASURED)**: out-of-sample 4–5 trades in one entry
  week, against a baseline out-of-sample of −0.664 R.
  - `/Users/ajay/clinet-test/eod-audits/research/LEDGER.md:21-25`
  - `/Users/ajay/clinet-test/eod-audits/research/gajjala_gates_2026_10_30/report.md:14-20`. A copy is kept at
    `backend/tests/fixtures/gajjala/gates_report_2026_10_30.md`.
- The gate math, ported verbatim: `wt-gggates/backend/scripts/gajjala_gates_study_2026_10_30.py:198-258` and
  `:411-425`.
  - The ported bytes are the file at worktree HEAD `0678034f`, with sha256 `20bb1970b5c5c9a59921a01afcfd570787ddc65c5c25bc5f8c16ff4ba08b2798`.
  - A byte copy is kept at `backend/tests/fixtures/gajjala/gates_study_2026_10_30.py.txt`, and a test hashes it.
  - report.md:5 cites `e308ab74…dfff08`, which is the RUN-2 bytes. report.md:47 says the file was then "edited only to
    print a one-week CI as 'no interval' and to re-render these files from `results.json` (`--render-only`, no data
    read)".

| id | name | status | rule (built) | source | GG's words | verdict |
|----|------|--------|--------------|--------|------------|---------|
| G1 | break-bar proof | **ON** | A+ only when the break bar CLOSES above the trigger AND its volume ≥ `G1_K` × the mean volume of the base bars | prereg row G1 (`k ∈ {1.0, 1.5, 2.0}`); pick k = 2 (LEDGER.md row "gates G1") | first_hand_2026_10_13.md:222 "… to prove it."; verified_rules.json `topics[0].verified[7]` "I just trade the price and volume action" | UNMEASURED: TOO SMALL, out-of-sample 4 trades in 1 entry week |
| G2 | red closes | **ON** | not A+ when the base's LAST run has more than `G2_MAX_RED` (= `GC.RED_CLOSES_WAIT`, GG's own number) consecutive red closes | prereg row G2 ("> 3 … No variants (GG's own number)") | verified_rules.json `topics[10].verified[5]` (X6 "more than 3 red closes is red flag to me => wait more") | UNMEASURED |
| G3 | ring age at the tick | **lane_only** | no lane entry when the ring is older than `G3_MAX_AGE_MIN` minutes at the tick, or the tick is past trigger + `G3_MISSED_R` × R | prereg row G3 (`m ∈ {10, 20, 30}`, `MISSED_R ∈ {0.5, 1.0}`); picks m = 30, 0.5 | none | UNMEASURED. Applied nowhere. |
| G4 | stop-distance cap | **ON** | not A+ when (trigger − stop)/trigger > `G4_MAX_RISK_PCT`. On 🎾 the stop is frozen at the first armed read with the alert's trigger. | prereg row G4 (`c ∈ {8 %, 10 %, 12 %}`); pick c = 10 (the app's own ABS_MAX_STOP_PCT 10) | verified_rules.json `topics[11].verified[2]` (S8 32:27 "The stop is known before entry … a breakout back into its range = out") | UNMEASURED |

Notes on the entries:

- **G1 with no base bars** reads "no proof" and FAILS (report.md:54). Every rule fails closed. A rule that cannot be
  read lands in `failed` with its `NONE_WHY` sentence. The word "None" is never served.
- **G2's reading (HIS CALL #2).** The built reading is the prereg's "the base's LAST run" (`G2_RUN = "last"`). The
  10-30 replay MEASURED the detectors' LONGEST run, which is the chip number. The two readings disagree on 4 of 26
  replay trades. One word flips it.
- **The Horizontal Fade's frame (HIS CALL #14).** G1 and G2 are judged on the read's OWN frame: 5-minute for Bull Flag,
  Kiss & Fly, Intraday VCP and 🎾, and 15-minute for the Horizontal Fade. The Fade reads the 15-minute frame first
  (`detectors.read_all`). The prereg rows say "5-min break bar" and "red 5-min closes".
  - Every audit block serves `frame`, and the G1 and G2 registry notes name it.
  - The options are: keep the read's own frame (built), exempt the Fade from G1/G2, or judge the Fade's break on the
    5-minute frame at the same bar time.
- **G4 on 🎾.** The stop is the one frozen at the first ARMED read whose trigger equals the alert's trigger. With no
  match, G4 reads the alert's stop. The card serves `values.G4.frozen_reason`, which says why. A stop cap or a frozen
  stop on 🚩 itself stays NOT built (HIS CALL #13). This tab is the only place G4 lives.
- **G3** is a PAPER-LANE entry gate, not a read. It is listed on the strip and applied nowhere. `trading/` is
  unchanged, and the lane trades 🚩 Gajjala's A+ only (HIS CALL #8).

The four rules are judged together. An A+ survives only when every ON rule passes. A held A+ carries `held_by` (every
rule it failed, each with its why).

## The process for a future audit

Each nightly Auto-Pilot EOD audit (`/Users/ajay/clinet-test/eod-audits/`) can propose a modification. It reaches this
tab only this way:

1. **It becomes a new registry entry** in `audited_rules.py`. The entry carries its eod-audits source (file and line),
   its GG words if any, its date and a frozen number with its source line.
2. **Its status is OFF until HIS CALL.** An OFF entry is listed on the strip, which is the default built (HIS CALL #7).
3. **On his word it goes ON on this tab only.** The 🚩 tab is never the target, and neither is any lane.
4. **A verdict later** is a LEDGER row in `eod-audits/research/LEDGER.md` (out-of-sample + placebo, the lab's floor)
   plus an update to the entry's `verdict` / `verdict_source`. The words never flip on a count (see
   "The 🏁 compare" below).

`AUDIT_VERSION` is stored on every audit block. Bump it whenever `judge()` changes.

## Shadow pushes: nothing rings

There are two locks. The first is `GAJJALA_AUDITED_PUSH_MODE = "shadow"` in constants.py. The second is that
`audited_pass` passes `mode="shadow"` explicitly to `alerts.run_pass`. The variant has no sender (`send_setup` /
`send_potential` are `""`). If the sender is ever reached, `_default_send` raises `NEVER_SENDS`
("the audited variant never sends — recorded only").

No push kind is registered in `push/subs`, and `OWNER_KEEP_SET` stays exactly six. `/notifications` gets no new toggle.

The "recorded, not sent" surface has two parts:

- **The GGA 🏁 record.**
- **One `/alerts` PASS-HEALTH row** (`alert_status.GAJJALA_AUDITED_KIND = "gajjala_audited_setup"`). It is not a push
  kind. Its cadence is derived from 🚩's line. It sits under its OWN eyebrow ("recorded in shadow, never sent"), never
  under the 1-minute "they ring your phone" block.

Going live is HIS CALL #1. It means both locks plus a kind registration.

## Collections

GGA **writes** only these four collections:

- `gajjala_audited_overlay`: the audit per (session, symbol). It is written only for names with an A+ read or an ARMED
  🎾 read on that pass, and only when the setups are non-empty or the frozen 🎾 stops changed. Its TTL is
  `READS_TTL_DAYS`.
- `gajjala_audited_alerts`: the shadow claims (`SHADOW:GGA:{date}|SYM|setup`) and the held markers
  (`GGA:{date}|SYM|setup#held`, idempotent).
- `gajjala_audited_state`: `audit_latest`, the per-pass summary (n read, A+ on the original, A+ audited, held, the ON
  rule ids, ok or error).
- `gajjala_audited_ledger`: the nightly copied columns and the residual grades.

GGA **reads** from GG5 through `Variant.borrows`: reads, potentials, passes and replay. It also reads every SHARED name,
including the ONE broker list. A variant store never builds indexes on a borrowed name.

## Costs, per job

- **The PASS: zero provider calls.** The step reads the Frames and reads this pass already holds.
  `test_gajjala_audited_pass.py` counts every provider dependency call with the overlay on and with it off, and the two
  counts are EQUAL.
  - On a `--dry-run`, the only observable is the log line `gajjala audit overlay dry writes: [...]`, which names only
    `gajjala_audited_*`.
  - Mongo cost is about one overlay op per name with an A+ or an armed 🎾 per pass, plus one state op, plus a claim or
    held marker per audited or held A+.
- **The NIGHTLY: copy-first.** `nightly.grade_audited` runs AFTER GG5's and GG1's grades.
  - **The copy.** `copy_original_grades` runs first. A GGA row whose 🚩 original has the same id, the same stamp
    (`at_utc`, the pass clock on both claims), the same trigger, stop and plan is the same read at the same stamp
    through the ONE engine. So it is the same grade, and GG5's graded columns are COPIED from `gajjala_ledger`.
    Provenance lives inside each column (`copied_from: "gajjala_ledger"`, `copied_at`), because `LEDGER_KEYS` is closed.
  - **The residual.** `grade_step` then runs, and it skips every copied column without a fetch. Its loads are the
    **RESIDUAL** only: a GGA row whose original's send `failed` / `no_target` (so there is no 🚩 row), or whose 🚩 grade
    was deferred or failed that night. That is the only new provider fetch. It is bounded by
    `LEDGER_BACKFILL_MAX_SYMBOL_DAYS` like every store, and it is expected to be 0 most nights.
  - **What the summary serves.** It serves `residual` in `out["gajjala_audited"]["copy"]` (with `rows`, `matched`,
    `copied_cols`, `faulted`). A raise serves `{"error": "grade: Type"}` and is never re-raised.
  - Re-grading every row with its own fetch instead is HIS CALL #15.
- **A 🏁 open.** It makes one bounded read of today's audited names (`ledger.today_read` over the audited store), which
  are a subset of GG5's. GG5's 🏁 already pays this page-open cost, so the pass pays nothing.

## The 🏁 compare (`audited_compare`) and what each counter means

The 🏁 compare uses the same sessions (the GGA 🏁's own span, clipped to `GGA_RECORD_FROM` = 2026-11-01) and the same
trade math (`ledger._cell`, `same` horizon).

- **`sides`**:
  - `original` = 🚩's A+ rows on those sessions (live + shadow lines) with their grades.
  - `audited` = the GGA A+ rows with theirs.
  - Each side serves n, filled, win, loss, open_flat, unfilled, `mean_r` and `win_pct`. `mean_r` is computed over
    DECIDED rows only: +`LEDGER_R_MULT` R for a win and −1 R for a loss. It is gross, by the 🏁's own math, with no cost
    line (HIS CALL #9). `win_pct` is computed over W + L.
- **`held`**: the A+ an ON rule removed. Each row's COUNTERFACTUAL outcome is the original row's same-session grade,
  so the rule's effect shows day by day. A held row with no original row serves `no_original` ("no original row — the
  original's send failed").
- **`recon`**: reconciles original n = audited n + held n + `original_only` − `audited_only` − `both`, by
  construction.
  - **`original_only`**: A+ on the original with neither an audited nor a held row. The overlay did not run on that
    pass, and its fence logged it.
  - **`audited_only`**: an audited OR held row with no original row. GG5's claim settled `failed` / `no_target`, so
    `alert_of` drops it. The read was the same. A held row with no original also serves `no_original` on `held`.
  - **`both`**: one id that is audited AND held — held on one pass, audited A+ on a later pass the same day. It is
    counted once on each side, so the identity subtracts it once.
  - `recon.text` serves `original_only` and `audited_only` in one sentence; `both` is served as a count only. (2026-11-01)
- **`by_rule`**: held rows per rule. A held A+ counts under EVERY rule it failed, so these rows can sum past the held
  total, as `by_rule_note` says.
- **`by_day`**: original, audited and held n / win / loss per session.
- **`entry_weeks`, `floor_weeks` (= `MEASURE_FLOOR_WEEKS`, 30), `floor_reached`**: a COUNT, never a verdict. The words
  stay UNMEASURED until the lab's out-of-sample + placebo read. When the floor is reached, the served sentence says
  "still UNMEASURED … nothing flips by count" (HIS CALL #10).

On the board, the strip's `unaudited` line counts the A+ reads served with NO fresh matching overlay entry. These are
shown as the original reads them. An overlay entry attaches to a read only when all three of these hold:

1. The read is `aplus`.
2. The entry's `entry_bar_t` equals the read's `entry_bar_t`.
3. The overlay's `pass_at` is at least as recent as the read's `updated_at`.

`stale_text` is served when the audit state doc is older than 🚩's latest pass.

## Routes (`backend/chart_maps/api.py`)

- `GET /chart-maps/gajjala-audited` serves `tab.build(…, variant=GGA)` from Mongo, plus the same live now-line fan-out.
  On 🏁 only, it calls `ledger.today_read(None, span=…, store=ST.for_variant(GGA))`.
- `POST /chart-maps/gajjala-audited/scan` is OWNER-ONLY (`auth.is_admin_email`); anyone else gets the stealth 404. It
  calls `on_demand.request()` with NO variant. That is 🚩 Gajjala's own on-open pass in GG5's child slot, and the
  overlay rides it. There is no audited child slot.
- `GET /chart-maps/gajjala-audited/entry-tape` calls `tape.entry_tape(id, lite=, store=ST.for_variant(GGA))`. An unknown
  id is a 404 with the served words. A raising build serves 200 with `fault_payload(…, variant=GGA)`.

The broker flags stay under `/chart-maps/gajjala/…`, as ONE list. The 🚩 and 1-minute routes are untouched.

## The ℹ️ panel

`supply_demand/rules_info._gg_audited_clause()` returns `" " + audited_rules.rules_clause()`. It is appended to the 🚩
Gajjala section note right after the one-minute clause. It returns `""` when the module cannot load or the clause raises,
and the panel still serves. The clause's source holds no numeric literal: every number is formatted from the registry's
constants (`tests/test_rules_info_gajjala_audited.py`, plus the section-wide AST guard in
`tests/test_rules_info_gajjala.py`).

## Frontend

- `GajjalaBoard variant="gajjala_audited"` is mounted with `key="gajjala_audited"`. The key is load-bearing, because it
  forces the remount. The tab slot is right after `gajjala` (HIS CALL #3).
- The label is `🧪 Gajjala · Audited` (HIS CALL #5).
- `GG_VARIANT_BASE.gajjala_audited` == variant.py `GGA.api_base`.
- New components:
  - `GgAuditedStrip` is FOLDED by default (Rule #5, HIS CALL #12).
  - `GgAuditedHeld` sits right after the A+ banner.
  - `GgAuditedCompare` sits above the 🏁 panel.
- `/alerts` gets its own `gga-passes` strip.
- The FE types no rule, number or sentence of the audit. Everything prints the served words.

## HIS CALL (defaults built; none decided for him)

1. **Going live** for audited A+ pushes. There are two locks today (the constant and the explicit `mode="shadow"`), and
   no kind exists in push/subs yet. Registering one is part of the same call.
2. **G2's reading**: built = the prereg's LAST run. The 10-30 replay measured the LONGEST run, and the two disagree on 4
   of 26 trades.
3. **Tab slot**: right after `gajjala`.
4. **Record start**: `GGA_RECORD_FROM = "2026-11-01"` (his ask date; the first market session is 11-03), or the deploy
   session.
5. **Label**: `🧪 Gajjala · Audited`, or his words "Gajjals-Audited".
6. **Scope of the filter**: the A+ read only. Removing held names from the 🧠 surfaces too is his call.
7. **Process rule**: an OFF entry is listed on the strip (built), or hidden until ON.
8. **G3 as a lane gate**: registered `lane_only` and applied nowhere. Any lane change is his call.
9. **Compare R accounting**: gross ±1 R by the 🏁 outcome, with no cost line.
10. **Measurement floor**: `floor_reached` (30 entry weeks) is a count and flips no word. A different floor, or the words
    once it is reached, is his number and his words.
11. **The /alerts pass-health row**: built under its own "never sent" eyebrow. Drop it if it reads as noise.
12. **Density**: the strip folds by default. Open by default is his call.
13. **Stop cap / frozen stop on 🚩 itself**: NOT built. This tab is the only place G4 lives.
14. **G1 / G2 on the Horizontal Fade**: built = the read's own 15-minute frame. The alternatives are to exempt the Fade,
    or to judge its break on the 5-minute frame at the same bar time. One constant either way.
15. **The nightly copy rule**: copy the 🚩 original's grade when id, stamp, trigger, stop and plan match (built), or
    re-grade every GGA row with its own fetch.

## Verification

The suites run before hand-off:

```
cd backend && rm -rf ~/Library/Caches/com.apple.python; /usr/bin/find . -path ./.venv -prune -o -name __pycache__ -type d -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/ -q --ignore=tests/test_portfolio_eq_risk.py --ignore=tests/test_accumulation.py --ignore=tests/test_holdings_loop_stall.py -p no:cacheprovider --deselect tests/test_hermes_bridge.py --deselect tests/test_ollama_chat.py
cd frontend && npx vitest run --reporter=dot && npx tsc --noEmit -p tsconfig.json && node scripts/contracts.mjs
```

These must NOT move:

- the three goldens (GG5 writes and board, 🏁, 1-minute)
- `test_gajjala_run_1m_2026_10_27.py:444`
- `test_gajjala_only_pushes_2026_10_29.py:45` (exactly six)
- the K and GG values in `test_gajjala_constants.py`
- `test_gajjala_source_guard.py` over the three new modules

The cost proof:

- **The pass** is the counter test (overlay on vs off: equal provider calls). The dry run's log line names only
  `gajjala_audited_*`, and its JSON summary has no new key.
- **The nightly** is `test_gajjala_audited_nightly.py`: `load_day` is called 0 times when every GGA row has a graded 🚩
  original.

On his surface, after the deploy (the first live overlay is the 04:01 ET pass of Monday 2026-11-03):

- `https://pounce.ajaykandakatla.dev/chart-maps?tab=gajjala_audited` shows:
  - the strip, folded, with 4 registry rows, the lane-only line and the UNMEASURED sentence
  - cards that read as 🚩's
  - on 🏁, the GGA title and the compare block (zeros until the first night's grades)
- Single checks only, never a load:
  - `curl -s -H "X-User-Email: ajaykandakatla@gmail.com" https://pounce.ajaykandakatla.dev/chart-maps/gajjala-audited | jq '.tab, .variant.title, [.audited.registry[].id], .audited.pass.text, .audited.unaudited, (.held.rows|length), .push.mode'`
  - It should print `"gajjala_audited"`, the title, `["G1","G2","G3","G4"]`, the pass line, `{n: 0, text: null}`, a
    count and `"shadow"`.
- NEGATIVE on 🚩: `curl … /chart-maps/gajjala | jq 'tostring | test("audit|aplus_held")'` → `false`. The same check on
  `/chart-maps/gajjala-1m` → `false`.
- A read-only container probe after 11-03 04:05 ET should show:
  - `gajjala_audited_state.audit_latest.at` == the `at` of the latest `gajjala_passes` doc
  - the overlay count ≤ the reads count
  - the GG5 pass doc's key set unchanged
  - ZERO `push_history` rows of kind `gajjala_audited_setup`
  - every audited claim starting `SHADOW:GGA:` or carrying `#`
- `/alerts`: the 🧪 pass row sits under its own eyebrow. `/notifications`: NO new toggle.
- After the 11-03 20:15 ET nightly:
  - `gajjala_audited_ledger` holds a `same` grade for every 11-03 claim, with `copied_from: "gajjala_ledger"` where the
    🚩 original was graded.
  - `gajjala_audited.copy.residual` in the nightly JSON says how many were not.
