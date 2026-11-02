# 🧪 Gajjala · Audited (2026-11-01)

Spec: BUILD_SPEC gg-audited, revision 2. Tab `gajjala_audited` on Chart Maps, right after 🚩 Gajjala's. Variant `GGA`.
Claim prefix `GGA:`. **UNMEASURED.** Every rule on this tab read TOO SMALL in the 2026-10-30 replay. The 2026-10-14 study
of the 5-minute setups read NULL (`docs/gajjala/study_2026_10_13.md`). The tab makes no claim that it wins. Its 🏁 Track
record is operational accounting, not a backtest. **Every audited alert is recorded in shadow and never sent.**

**2026-11-01 (later the same day): the eight modifications ON + the per-rule track record.** Ajay: *"Yes make the
changes in audited please"* and *"But keep a track record too to see the winners and loster"*. The registry now holds
12 entries (G1–G4 + T1 T2 A1 H1 T4 A2 T3 T5), `AUDIT_VERSION` is 2, 🧪 judges only the bars 🚩 would ring (the Scope
rule below), and the 🏁 compare serves ONE per-rule table (`per_rule`) in place of `by_rule`. The entries, their
conventions, the T5 walk and HIS CALLs #16–#25 are in `docs/gajjala/audited_modifications_2026_11_01.md`. All eight
are UNMEASURED.

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
rule, params, source, GG's words, verdict, verdict_source, changes and note, plus two trailing fields added 2026-11-01:
`kind` (`filter` / `exit`, default `filter`) and `prereg` (the frozen file the entry's numbers come from, default the
10-30 prereg). `validate()` refuses an ON rule with `applies=False` and a `kind` outside `KINDS`. `registry_rows()` serves the words. The FE
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
- The 2026-11-01 prereg (T1 T2 A1 H1 T4 A2 T3 T5):
  `/Users/ajay/clinet-test/eod-audits/research/2026-11-01_gajjala_audited_modifications_prereg.md`.
  - Its sha256 is pinned as `PREREG2_SHA256`; `PREREG_SHA_BY_PATH` maps each prereg path to its hash, and
    `registry_rows()` serves the first 12 characters of the entry's own prereg hash in `source_text`.
  - A byte copy is kept at `backend/tests/fixtures/gajjala/audited_modifications_prereg_2026_11_01.md`, and a test
    hashes it.
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
| T1 | daily entry cap (filter, judged LAST) | **ON** | at most `T1_DAILY_CAP` audited A+ a day; slots in claim order, then 🚩's ring order within a pass (`alerts._candidates`: entry bar, setup order, symbol); a same-bar tie is flagged `tie` | prereg2 row T1; REPORT §6 T1; podcast 10pHBNVi4Jc 1:28:10 "one trade a day, two max" | none on file (`gg = ()`) | UNMEASURED |
| T2 | first-hour block | **ON** | not A+ when the break bar STARTS before `T2_FIRST_HOUR_END_ET` (10:30 passes) | prereg2 row T2; REPORT §6 T2 | `topics[3].verified[9]` (T9, GG X 1753343067846058314) | UNMEASURED |
| A1 | time cut | **ON** | not A+ when the break bar STARTS after `A1_LAST_ENTRY_ET` (11:55 passes, 12:00 fails); the float < 100M half is a no-op (`GC.K8_MAX_FLOAT`) | prereg2 row A1; SYNTHESIS §A3 #1 | none on file (`gg = ()`) | UNMEASURED |
| H1 | regular hours only | **ON** | not A+ when the break bar STARTS outside `H1_OPEN_ET`–`H1_CLOSE_ET` (= `ET_RTH_OPEN` / `ET_RTH_CLOSE` by name; the regular close on a half day) | prereg2 row H1; re-look 10-29 causes (8) | `topics[1].verified[5]` (R5) | UNMEASURED |
| T4 | regime gate | **ON** | not A+ when the day's top scanner runner (`strip.best_change_pct`) is ≤ `T4_QUIET_TOP_PCT` (= `GC.SA_QUIET_BEST_PCT` by name); served `fired` / `fired alone` | prereg2 row T4; REPORT §6 T4, **unverified overflow** | none on file (`gg = ()`) | UNMEASURED |
| A2 | volume-spike skip | **ON** | not A+ when the break bar's volume ≥ `A2_SPIKE_MULT` × the prior bar's, on the read's own frame | prereg2 row A2; SYNTHESIS §A3 #2 | `topics[5].verified[3]` (BF4) | UNMEASURED |
| T3 | fixed target on the Intraday VCP (exit) | **ON** | exit grade on `T3_SETUPS` rows at each of `T3_R_MULTS` (2R primary, 3R second), `ledger.grade(..., r_mult=k)` | prereg2 row T3; REPORT §6 T3 | none on file (`gg = ()`) | UNMEASURED |
| T5 | 21 EMA trail (exit) | **ON** | exit grade on every setup: first 5-minute close strictly under the `T5_EMA` (= `GC.EMA_SLOW`) EMA of the GG5 frame; the stop first | prereg2 row T5; REPORT §6 T5, claim_only | `topics[11].verified[9]` (E10, status contradicted) | UNMEASURED |

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

The ON filter rules are judged together. `judge()` runs the stateless ones (`judge_rules()` = G1 G2 G4 T2 A1 H1 T4
A2) per read; T1 is judged LAST in `audited_pass.run_step` over the pass's survivors (`with_t1`), because it needs the
day's claims and the ring order. An A+ survives only when every ON filter passes. A held A+ carries `held_by` (every
rule it failed, each with its why). The exit rules (`exit_rules()` = T3 T5) never touch the read: they are graded the
night after the session (see Costs). `on_rules()` = the 11 ON ids (all but G3).

## The Scope rule (2026-11-01): 🧪 judges only the bars 🚩 would ring

`run_step` asks `alerts.refusal(...)` for every A+ read. `refusal` is ONE mechanical extraction of `run_pass`'s own
refusal chain (`not_aplus_variant`, `no_risk`, `claimed_before` / `late`, `suppressed_closed`, the window, the extra
suppression), and `run_pass` itself calls it, so 🚩's behaviour is byte-identical (`test_gajjala_alerts.py` and the
goldens pin it). A read `refusal` refuses, or a (symbol, setup) already claimed today, is NOT judged: no overlay entry,
no `#held` marker, no T1 slot; it passes through as 🚩 treats it, and the state doc counts it in `n_unjudged`.

So T2's record is the 09:45–10:29 bars and H1's the after-hours bars; the premarket bars are HIS CALL #23. Every 🧪
record is matched to 🚩's entry by (date, symbol, setup, entry bar), and the first `#held` marker of a (date, symbol,
setup) sits on 🚩's claim bar by construction (proof in the modifications doc).

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

No push kind is registered in `push/subs`, and `OWNER_KEEP_SET` gains nothing from this tab (exactly seven since
2026-11-01, the seventh being 🥇 `luk_setup`). `/notifications` gets no new toggle.

The "recorded, not sent" surface has two parts:

- **The GGA 🏁 record.**
- **One `/alerts` PASS-HEALTH row** (`alert_status.GAJJALA_AUDITED_KIND = "gajjala_audited_setup"`). It is not a push
  kind. Its cadence is derived from 🚩's line. It sits under its OWN eyebrow ("recorded in shadow, never sent"), never
  under the 1-minute "they ring your phone" block.

Going live is HIS CALL #1. It means both locks plus a kind registration.

## Collections

GGA **writes** only these five collections:

- `gajjala_audited_overlay`: the audit per (session, symbol). It is written only for names with an A+ read or an ARMED
  🎾 read on that pass, and only when the setups are non-empty or the frozen 🎾 stops changed. Its TTL is
  `READS_TTL_DAYS`.
- `gajjala_audited_alerts`: the shadow claims (`SHADOW:GGA:{date}|SYM|setup`) and the held markers
  (`GGA:{date}|SYM|setup#held`, idempotent). Since 2026-11-01 both carry `audit = {passed, failed, values, version,
  frame, rules}`: the marker on insert, the claim settled once when it has none (never overwritten; an on-demand
  `push_dry` pass settles nothing).
- `gajjala_audited_state`: `audit_latest`, the per-pass summary (n read, A+ on the original, A+ audited, held, ok or
  error). Since 2026-11-01 it also carries `rules` (the filter ids), `exit_rules` ([T3, T5]), `version`,
  `best_change_pct`, `t1_slots_used`, `n_t4_fired_pass`, `t4_session = {fired, fired_alone}` (counted from the durable
  `#held` markers; a read fault serves `read_fault: True`) and `n_unjudged` (the `refusal` histogram).
- `gajjala_audited_ledger`: the nightly copied columns and the residual grades.
- `gajjala_audited_exits` (logical `gajjala_exits`, 2026-11-01): the alternative-exit grades, one doc per 🏁 row id,
  keys `EXITS_KEYS` (`date, symbol, setup, kind, alert, graded_at, version`) plus the columns `T3_2R`, `T3_3R`, `T5`
  (`AUD.EXIT_COLS`). Written only by the GGA store (`upsert_exits` refuses any other variant, any other key, an empty
  id); kept, no TTL. GG5 and GG1 never index or write it (the OVERLAY guard pattern), and `store.ALL[-1]` is still
  `REPLAY`.

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
- **The NIGHTLY exits step (2026-11-01): one night later, warm cache only.** `grade_audited` then runs
  `audited_exits.grade_exits` in its own inner try (a fault serves `"exits": {"error": "exits: Type"}`; copy and grade
  stay intact; the outer `{"error": "grade: Type"}` shape is unchanged).
  - `load_intraday` never caches today and fetches a cold past day (`data.py:241-253`), so a row dated today is
    `deferred_today`.
  - A row needs its session and the prior market day (the EMA warm-up). Both are probed in `intraday_cache` first
    (`dt_data._mongo_get_day`, a read). Either cold → `deferred_cold`: nothing loaded, nothing fetched, retried the next
    night (HIS CALL #21).
  - Warm rows load through `load_intraday` with no force, memoized per `(symbol, day)`, bounded by
    `LEDGER_BACKFILL_MAX_SYMBOL_DAYS` (`deferred_cap`). Expected provider calls: **0**, pinned by a test through the
    real `load_intraday`.
  - Served as `gajjala_audited.exits` (`rows, graded, written, not_due, deferred_today, deferred_cold, deferred_cap,
    load_failed, no_bars, faulted, loads, read_fault, dry, sessions`).
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
- **`per_rule`** (2026-11-01, replaces `by_rule`): ONE table, one row per ON rule in registry order (G3 excluded, T3
  twice), 12 rows: G1 G2 G4 T1 T2 A1 H1 T4 A2 T3_2R T3_3R T5. `per_rule_title` sits above it.
  - Attribution is by (id, entry bar), read from the alert docs on BOTH stores (`ledger.alert_of` carries no
    `entry_bar_t` and drops `audit`).
  - A filter row serves "with the rule" vs "held by the rule — what the original did", both scored by the 🚩
    original's same-session grade, plus "removed {w} and {l} · {u} never filled". T1's held side reads "held — cap
    reached" with `tie_held`; T4's serves `fired` and `fired_alone`.
  - An exit row serves the modified exit (from `gajjala_audited_exits`) vs "GG's math on the same rows" (the 🧪
    ledger's `same` column); an ungraded row is "not graded yet".
  - `not_judged` (no record on the bar, or a record from before the rule joined) and `no_original` (a 🧪 record on a
    bar no original has) are counted, never scored.
  - Counts, not verdicts. Full semantics: `docs/gajjala/audited_modifications_2026_11_01.md`.
  - `by_rule_note` stays as the footnote: a held A+ counts under EVERY rule it failed, so the held column can sum past
    the held total.
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

`supply_demand/rules_info._gg_audited_clause()` returns `" " + audited_rules.rules_clause()`. Since 2026-11-01 the
clause names the ON filters (T1 included) and then, under "Exit grades on its 🏁 beside GG's math", T3 and T5 (HIS CALL
#25). It is appended to the 🚩
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

Added 2026-11-01 with the eight modifications (full text in `docs/gajjala/audited_modifications_2026_11_01.md`):

16. **T1 cap = 2** vs 1, and the same-bar tie rule (built = 🚩's ring order, flagged and counted as `tie_held`).
17. **T3 primary = +2R**; +3R is the second column.
18. **T4 boundary**: "≤ +40% fails" (pinned) vs the strip's strict `<` `quiet` flag.
19. **A2 on the read's own frame** (#14 carried over).
20. **T5 on the 5-minute frame for every setup**, the Fade included.
21. **Exit grades one night later from warm cache only**; a cold row is never fetched.
22. **After-hours window on 🚩**: keep or cut. H1 lives on 🧪 only.
23. **Scope = the bars 🚩 would ring**: premarket / first-15 / late / closed / suppressed A+ are never judged. Judging
    the premarket bars too is his.
24. RETIRED by #23 (the first `#held` marker is 🚩's claim bar by construction).
25. **The ℹ️ clause names 12 rules**: keep, fold, or trim to the ON filters.

## Verification

The suites run before hand-off:

```
cd backend && rm -rf ~/Library/Caches/com.apple.python; /usr/bin/find . -path ./.venv -prune -o -name __pycache__ -type d -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/ -q --ignore=tests/test_portfolio_eq_risk.py --ignore=tests/test_accumulation.py --ignore=tests/test_holdings_loop_stall.py -p no:cacheprovider --deselect tests/test_hermes_bridge.py --deselect tests/test_ollama_chat.py
cd frontend && npx vitest run --reporter=dot && npx tsc --noEmit -p tsconfig.json && node scripts/contracts.mjs
```

These must NOT move:

- the three goldens (GG5 writes and board, 🏁, 1-minute)
- `test_gajjala_run_1m_2026_10_27.py:444`
- `test_gajjala_only_pushes_2026_10_29.py` (exactly SEVEN kinds since 2026-11-01)
- the K and GG values in `test_gajjala_constants.py`
- `test_gajjala_source_guard.py` over the three new modules

The cost proof:

- **The pass** is the counter test (overlay on vs off: equal provider calls). The dry run's log line names only
  `gajjala_audited_*`, and its JSON summary has no new key.
- **The nightly** is `test_gajjala_audited_nightly.py`: `load_day` is called 0 times when every GGA row has a graded 🚩
  original.
- **The exits** are `test_gajjala_audited_exits.py`: through the real `load_intraday`, both days warm → 0 fetches and
  `_mongo_put_day` never called; the prior day cold → `deferred_cold`, 0 loads, 0 fetches.

On his surface, after the deploy (the first live overlay is the 04:01 ET pass of Monday 2026-11-03):

- `https://pounce.ajaykandakatla.dev/chart-maps?tab=gajjala_audited` shows:
  - the strip, folded, with 12 registry rows (G1 G2 G3 G4 T1 T2 A1 H1 T4 A2 T3 T5; G3 lane only, T3 / T5 marked as exit
    grades), the lane-only line and the UNMEASURED sentence
  - cards that read as 🚩's
  - on 🏁, the GGA title and the compare block (zeros until the first night's grades), with ONE per-rule table of 12
    rows: zeros / "no A+ judged on this rule yet" until 11-03, exit rows "not graded yet" until the 11-04 nightly, and
    the T4 row reading "fired on 0 rung bars · alone on 0".
- Single checks only, never a load:
  - `curl -s -H "X-User-Email: ajaykandakatla@gmail.com" https://pounce.ajaykandakatla.dev/chart-maps/gajjala-audited | jq '.tab, .variant.title, [.audited.registry[].id], .audited.pass.text, .audited.unaudited, (.held.rows|length), .push.mode'`
  - It should print `"gajjala_audited"`, the title, the 12 ids
    `["G1","G2","G3","G4","T1","T2","A1","H1","T4","A2","T3","T5"]`, the pass line, `{n: 0, text: null}`, a count and
    `"shadow"`. `.audited.on_ids` has 11 ids (all but G3).
  - `curl … "/chart-maps/gajjala-audited?sub=track_record&span=5d" | jq '(.audited_compare.per_rule|length), [.audited_compare.per_rule[].key], .audited_compare.by_rule'`
    → `12`, the keys, `null`.
- NEGATIVE on 🚩: `curl … /chart-maps/gajjala | jq 'tostring | test("audit|aplus_held|per_rule")'` → `false`. The same check on
  `/chart-maps/gajjala-1m` → `false`.
- A read-only container probe after 11-03 04:05 ET should show:
  - `gajjala_audited_state.audit_latest.at` == the `at` of the latest `gajjala_passes` doc
  - the overlay count ≤ the reads count
  - the GG5 pass doc's key set unchanged
  - ZERO `push_history` rows of kind `gajjala_audited_setup`
  - every audited claim starting `SHADOW:GGA:` or carrying `#`
  - `audit_latest.version == 2`, `rules` = the 9 filter ids, `exit_rules == ["T3","T5"]`, `t1_slots_used ≤ 2`,
    `t4_session.fired ≥ t4_session.fired_alone`, `n_unjudged` keys ⊆ run_pass's refusal states
  - every `#held` marker's `entry_bar_t` equal to the 🚩 `GG:` claim's of the same (date, symbol, setup) when that claim
    exists, and no marker before 09:45 ET
- `/alerts`: the 🧪 pass row sits under its own eyebrow. `/notifications`: NO new toggle.
- After the 11-03 20:15 ET nightly:
  - `gajjala_audited_ledger` holds a `same` grade for every 11-03 claim, with `copied_from: "gajjala_ledger"` where the
    🚩 original was graded.
  - `gajjala_audited.copy.residual` in the nightly JSON says how many were not.
  - `gajjala_audited.exits.deferred_today` == the number of 11-03 rows, `exits.loads == 0`, and `gajjala_audited_exits`
    holds 0 docs (deferred by design).
- After the 11-04 20:15 ET nightly: `exits.loads ≤ 2 × rows`, `exits.deferred_cold` a number, one
  `gajjala_audited_exits` doc per warm 11-03 audited A+ row (`T5`, plus `T3_2R` / `T3_3R` on 🌀 rows), and no Massive
  minute fetch logged for `gajjala_audited` between 20:15 and 20:20.
