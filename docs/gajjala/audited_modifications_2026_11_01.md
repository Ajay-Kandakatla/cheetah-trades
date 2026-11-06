# 🧪 Gajjala · Audited — the eight 2026-11-01 modifications + the per-rule track record

Spec: BUILD_SPEC gg-audited-mods, revision 2. Branch `feat/gajjala-audited-modifications-2026-11-01`. This page covers
the eight new registry entries on the 🧪 tab and the per-rule table on its 🏁. The tab itself (overlay, store, shadow
locks, routes) is described in `docs/gajjala/audited_variant_2026_11_01.md`.

**UNMEASURED.** None of the eight has been measured on this lane. The 10-30 cohort holds 26 filled A+, which is TOO
SMALL for any of them, so no replay was run. The per-rule table on the 🧪 🏁 IS the measurement until the lab's floor
(30 out-of-sample entry weeks, placebo, Deflated Sharpe). **Shadow only.** 🧪 still rings nothing and trades nothing.
🚩 Gajjala's tab is untouched.

## The ask, verbatim

Ajay, 2026-11-01:

> "Yes make the changes in audited please"

> "But keep a track record too to see the winners and loster"

What he said yes to (my words to him, 2026-11-01): "Which modifications to pre-register and test as 🧪 entries (OFF
until you say): the five from tonight's sweep — daily entry cap of 1–2, no entries before 10:30 ET, fixed 2R/3R on VCPs,
stand down when the day's top runner is ≤ +40%, 21 EMA trail — plus the 11:59 cut + float <100M and the 10× volume-spike
skip. Pick which; I run the lab, nothing ships without it." and "After-hours window: 4 of 5 unfilled A+ rang after
hours. Keep or cut."

His "yes" is the word the process rule waits for: every entry below is **ON on the 🧪 tab only**. No lane and no 🚩 rule
changes.

## The frozen sources

- **The prereg**, written before any code:
  `/Users/ajay/clinet-test/eod-audits/research/2026-11-01_gajjala_audited_modifications_prereg.md`.
  - Its sha256 is pinned in `audited_rules.py` as `PREREG2_SHA256`, beside the 10-30 prereg's `PREREG_SHA256`
    (`PREREG_SHA_BY_PATH` maps each path to its hash).
  - A byte copy is kept at `backend/tests/fixtures/gajjala/audited_modifications_prereg_2026_11_01.md`. A test hashes
    it, and the host file, when present, must equal the fixture bytes.
  - Every new rule's `source[0]` quote is a substring of that file (a test).
- **The research**:
  - `/Users/ajay/clinet-test/eod-audits/research/gg_modifications_2026_11_01/REPORT.md` §6 table (T1–T5) and §3 row 12
    (the podcast line).
  - `/Users/ajay/clinet-test/eod-audits/research/champions_2026_11_01/SYNTHESIS.md` §A3 #1 (the 11:59 cut + float) and
    #2 (the 10× volume spike).
  - The 10-29 re-look (`gajjala_relook_2026_10_29`): 4 of the 5 never-filled A+ rang after hours.
- **LEDGER.md**: eight rows dated 2026-11-01, trial `none`, n 0, DSR "none (N unchanged)", verdict "UNMEASURED —
  forward-recorded on 🧪 from 2026-11-01; the 10-30 cohort (26 filled A+) is TOO SMALL for any of them".

## The Scope rule: 🧪 judges only the bars 🚩 would ring

🧪 judges ONLY the A+ bars 🚩 would ring on the same pass. The test is `alerts.refusal(...)`, ONE function extracted
from `run_pass`'s own refusal chain, which `run_pass` itself now calls. A bar is judged when `refusal` is None:

- it has a plan (not `no_risk`),
- it is the latest closed bar of its own frame (not `late`),
- the market is open (not `suppressed_closed`),
- it is inside 🚩's window (not `premarket`, not `first15`, not an extra suppression),
- and the (symbol, setup) is not already claimed today (not `claimed_before`).

A bar 🚩 refuses is neither judged nor recorded. It passes through unchanged, exactly as 🚩 treats it. The pass counts
these reads by refusal reason in the state doc (`n_unjudged`).

What this means for two of the rules:

- **T2's record is the 09:45–10:29 bars only.** 🚩 never rings a bar before 09:45 (its own first-15 window), so those
  bars never reach 🧪.
- **H1's record is the after-hours bars only.** Premarket bars never reach 🧪 either.

Judging the premarket bars too is a different question, with no 🚩 outcome to score against. That is HIS CALL #23.

Every 🧪 record is matched to 🚩's entry by (date, symbol, setup, **entry bar**). Why the stored record sits on 🚩's
bar: 🚩 claims the FIRST claimable bar B1 of a (date, symbol, setup). 🧪 judges exactly those bars. On B1 it either
shadow-claims B1 or writes the `#held` marker on B1 (first write wins, `$setOnInsert`). A later claimable bar B2 is
`claimed_before` on 🚩; if 🧪 held B1 it judges B2, and a pass there shadow-claims B2 (the recon's "different bar"
case). So the marker, when it exists, is on 🚩's bar. A later re-hold of the same (symbol, setup) on a later bar is
**not** recorded: the first audit stays.

## The eight entries

Common to all eight: `date_added` 2026-11-01, status **ON on 🧪 only**, `applies` True, verdict **UNMEASURED**,
`verdict_source` = the LEDGER.md row of 2026-11-01, `prereg` = the 2026-11-01 prereg. Every number is a named constant in
`audited_rules.py` and cites its prereg row; GG's own numbers are read BY NAME, never retyped.

Times are judged by the bar's **START**: start = the bar's close stamp (`alerts.bar_close_et`) minus the frame's minutes
(`alerts.FRAME_MINUTES`). This is `alerts.window_reason`'s own convention.

### Filter rules (they change the A+; a removed A+ is served `aplus_held`, listed, never hidden)

| id | rule | parameter (frozen) | source line | GG's words on file | how it is judged | boundary convention (pinned by test) |
|----|------|--------------------|-------------|--------------------|------------------|--------------------------------------|
| **T1** | daily entry cap | `T1_DAILY_CAP` = 2; `T1_ORDER` = "ring" | REPORT §6 T1; GG podcast 10pHBNVi4Jc 1:28:10–1:28:17 "one trade a day, two max" | none in this repo (`gg = ()`) | judged LAST in `audited_pass.run_step`, only on reads that passed every other ON filter, against today's 🧪 claims | the third claimable survivor of a day is held; an A+ claimed earlier today keeps its slot without taking a new one |
| **T2** | first-hour block | `T2_FIRST_HOUR_END_ET` = 10:30 | REPORT §6 T2 | VR T9: "Most profitable hours in 2023: 11 AM and 5 PM ET; the first hour was the worst" (GG X 1753343067846058314) | not A+ when the break bar STARTS before 10:30 ET | a start of exactly 10:30:00 passes, 10:25 fails (a 5m bar closing 10:35 passes, closing 10:30 fails) |
| **A1** | time cut | `A1_LAST_ENTRY_ET` = 11:59 | SYNTHESIS §A3 #1 (F4VS MIL) | none in this repo (`gg = ()`) | not A+ when the break bar STARTS after 11:59 ET | a start of 11:55 is the last 5-minute bar to pass; 12:00 fails (close 12:00 passes, close 12:05 fails) |
| **H1** | regular hours only | `H1_OPEN_ET`, `H1_CLOSE_ET` = `daytrading.data.ET_RTH_OPEN` / `ET_RTH_CLOSE` by name | re-look 10-29 causes (8) | VR R5: "Very little premarket trading; outside regular hours: limit orders only, less size." | not A+ when the break bar STARTS outside the regular session; the close comes from `alerts.is_after_hours_bar` / `alerts._closes` (13:00 on a half day) | 09:25 fails, 15:55 passes, 16:00 fails; on the half day 2026-11-27, 12:55 passes and 13:00 fails |
| **T4** | regime gate | `T4_QUIET_TOP_PCT` = `GC.SA_QUIET_BEST_PCT` (40.0, GG S8 44:37) by name | REPORT §6 T4 | none in this repo (`gg = ()`) | not A+ when the day's top scanner runner at the ring (the pass's own `strip.best_change_pct`) is ≤ +40% | 40.0 fails, 40.01 passes; no number on the pass → fail-closed |
| **A2** | volume-spike skip | `A2_SPIKE_MULT` = 10.0 | SYNTHESIS §A3 #2 (F4VS "skip a 10x prior-candle volume spike; 2-3x is fine") | VR BF4: "Volume step: \"twice, thrice\" the previous candle is fine, ~10× = climax / invalid" | not A+ when the break bar's volume ≥ 10 × the prior bar's volume, on the read's OWN frame | exactly 10× fails, 9.9× passes; no prior bar, or a prior volume of 0 → fail-closed |

### Exit rules (they change the GRADE, not the A+; the read, the claim and the push are untouched)

| id | rule | parameter (frozen) | source line | GG's words on file | how it is graded | convention |
|----|------|--------------------|-------------|--------------------|------------------|------------|
| **T3** | fixed target on the Intraday VCP | `T3_SETUPS` = ("intraday_vcp",); `T3_R_MULTS` = (2.0, 3.0), primary = the first | REPORT §6 T3; @78_nazmi 1844819691304305095 "2R–3R" | none in this repo (`gg = ()`) | 🌀 Intraday VCP rows only: `ledger.grade(..., r_mult=k)` for k = 2R and 3R — the 🏁's ONE engine with one keyword; the default stays byte-identical | the 🏁's fill rule and stop-touch rule; the fill minute's high never counts toward the win; a bar with both = loss; win = +k R, loss = −1 R |
| **T5** | 21 EMA trail | `T5_EMA` = `GC.EMA_SLOW` (21) by name; `T5_FRAME` = `GG5.primary` ("5m") | REPORT §6 T5; Dollar Wisdom uG8CzABsIPM, claim_only | VR E10: "Dollar Wisdom's \"exit everything on a close below the 21 EMA, 3 setups\" — never implemented." (status contradicted) | every setup: after the fill, exit at the first 5-minute CLOSE strictly under the 21 EMA of the GG5 5-minute frame; the stop still first | see "The T5 walk" below |

`EXIT_COLS` = ("T3_2R", "T3_3R", "T5"), built from `T3_R_MULTS` + `exit_col_key`, never typed (a test rebuilds it with
a mutated `T3_R_MULTS`).

### Notes on the entries

- **Fail-closed.** A rule that cannot be read lands in `failed` with its own `NONE_WHY` sentence. The word "None" is
  never served:
  - T1: "not judgeable — today's audited entries could not be read"
  - T2 / A1 / H1: "not judgeable — the break bar has no clock"
  - T4: "not judgeable — the pass holds no top runner"
  - A2: "not judgeable — no prior bar to compare"
- **T1: the order is 🚩's own ring order.** Slots go in claim order: an A+ claimed on an earlier pass keeps its slot.
  Within one pass the order is `alerts._candidates`'s key (entry bar, then the setup's order in `SETUPS`, then symbol).
  That is literally the order the pushes leave the pass and ring his phone. `audited_rules.ring_order` uses that one
  key (a test runs both on the same reads and compares the sequence). Only a bar 🚩 would ring takes a slot, so a
  `no_risk` read takes none.
  - **The tie.** Every 5-minute A+ of one pass sits on the same latest closed bar (`detectors.py:306`), so
    "chronology within a pass" does not exist. Two A+ on ONE bar are a TIE, broken by setup order then symbol. When
    the tie straddles the cap line (one took the last slot, one was held), the held read carries `values.T1.tie = True`
    and its why ends "— tied on one bar, 🚩's ring order broke it". The 🏁 counts these as `tie_held`. The tie rule
    itself is HIS CALL #16.
  - cap 2 = his ceiling "two max"; 1 is the floor (HIS CALL #16). REPORT §3 row 12 records that "A+ only" does not
    hold and that GG said 2–4 trades a day in a good market (CI7mNvEQyms 49:48–50:13).
  - T1 is the only modification with a before/after record: GG's own H2-2023 change (REPORT §2). That is a record of
    HIS trading, not a test of the rule.
- **T4: provenance and caution, verbatim.** The registry note carries both:
  - "unverified overflow (REPORT §6 T4: GG webinar CI7mNvEQyms ~43:15–45:30)"
  - "Ross audit Q5: a ≥50% mover existed by 10:00 on 501 of 504 days, so this gate may almost never fire. Count how
    often it fires before anything else."
  - So the 🏁 serves the count first: **`fired`** = holds where T4 failed, **`fired alone`** = holds where ONLY T4
    failed, both over the bars 🚩 rang. The day's numbers come from the durable `#held` markers
    (`gga.held_rows([session])`) into the state doc as `t4_session = {fired, fired_alone}`. They are idempotent per
    (date, symbol, setup), so a repeated pass never double-counts.
  - The number is the pass's own `strip.best_change_pct` (his scanner population, `scanner.py:186-194`), handed to
    `run_step` by one new `strip` kwarg. Not `alert_ctx`'s `reg_gain_pct`, which covers listed names only.
  - GG's VERIFIED good-day numbers are `GC.SA_BIG_RUNNER_PCT` 100 and `GC.SA_RUNNER_PCT` 80 (S8 43:39). The bad-day
    number 40 is `GC.SA_QUIET_BEST_PCT` by name.
  - The strip's own `quiet` flag uses a strict `<`; this rule uses "≤ fails" (REPORT §6's words). The equality case is
    HIS CALL #18.
  - The identity test world has the top runner at exactly +40.0, so T4 holds every A+ there. The fixture is not changed.
- **A1: the float < 100M half is a NO-OP.** 🚩's K8 already caps the universe at `GC.K8_MAX_FLOAT` 10,000,000 shares
  (`context.py:194-206`), and a suspect float is ineligible (`FLOAT_SUSPECT_POLICY`). Verified, not built. The registry
  note says so.
- **A2 on the read's own frame.** The Horizontal Fade's read compares 15-minute volumes (HIS CALL #14 carries over as
  #19).
- **H1 lives on 🧪 only.** 🚩's own after-hours window is untouched. Keep or cut there is HIS CALL #22.
- **T5 contradicts GG.** GG's own exit is the 9 EMA trail (VR 11.4; the 21 only on Kiss & Fly). T5 is a true
  modification, not GG. It runs on the 5-minute frame for every setup, the Fade included (HIS CALL #20).
- **T3's primary is 2R**, the lower bound, stated first (HIS CALL #17). REPORT §5 records adminapius Strategy R with a
  fixed 2R: 178 trades, −0.142R, on a different lane.
- `AUDIT_VERSION` is now **2** (`judge()` changed: it takes `ctx` and judges T2 A1 H1 T4 A2). Every audit block carries
  `version`, `rules`, `passed`, `failed`, `values` and `frame`.

## The per-rule track record ("see the winners and losers")

On the 🧪 🏁, `audited_compare.per_rule` is ONE table with one row per ON rule, in registry order. G3 is excluded
(lane only) and T3 has two rows (2R, 3R). That makes 12 rows: 9 filter rows (G1 G2 G4 T1 T2 A1 H1 T4 A2) and 3 exit rows (T3_2R T3_3R T5). It REPLACES the
old held-only `by_rule` (one table, not two — Rule #5). `per_rule_title` sits above it and `by_rule_note` stays below
it. `sides`, `held`, `recon`, `by_day` and the floor counters are unchanged.

**Counts, not verdicts.** Every cell is a served sentence with counts. The FE prints it and composes nothing. Every row
ends in UNMEASURED. `floor_reached` flips no word (HIS CALL #10).

### Attribution: by (id, entry bar)

The universe of a filter row is the 🚩 originals in the span. For each original, the 🧪 record on ITS bar is:

1. the `#held` marker whose `entry_bar_t` equals the original's, else
2. the audited claim whose `entry_bar_t` equals the original's, else
3. when the original has no `entry_bar_t` (rows older than the key): the marker, then the claim.

The bars come from the alert docs themselves (`alert_rows` on BOTH stores). `ledger.alert_of` carries no `entry_bar_t`
and drops the `audit` key, so it cannot do this match. The audit on a claim is written once, when the shadow claim is
settled (`AL._settle(..., {"audit": …})`), and never overwritten by a later pass.

- **`not_judged`**: no 🧪 record on the original's bar, or a record whose audit does not list this rule (recorded
  before the rule joined, or T1 never judged because another rule held the read). A claim with no `audit` is
  `not_judged` for every rule.
- **`no_original`**: a 🧪 record (claim or marker) whose bar matches NO original of the same id. Counted once on the
  row; the recon already lists the "different bar" case.
- **🔁 One count per stock per day (2026-11-02).** Each side (🚩 original, 🧪 audited) dedupes over its OWN rows
  with the ledger's engine (`ledger.dedupe_trades`, partition date / symbol / count line). A duplicate original is
  neither with- nor held-scored on any rule row (its record is still marked taken, so it never becomes a false
  `no_original`). The HELD side dedupes over ITS OWN rows, reading each held row's facts from its ORIGINAL row (a held
  doc carries no ring time or plan) — never inherited from the original side: a stock-day held once is counted once
  on the held side whatever the original side decided; a `no_original` held row is never a duplicate. `_tally` is the
  one filter point (`n` = counted rows, `n_dup` served on every side, held and per-rule side); `recon` stays id-set
  arithmetic over ALL ids, so the identity reads `o.n + o.n_dup == a.n + a.n_dup + held.n + held.n_dup +
  original_only − audited_only − both`. `compare_honesty` ends with the rule.

### Filter rows (G1 G2 G4 T1 T2 A1 H1 T4 A2)

- **with the rule**: the originals whose 🧪 record lists the rule in `passed`, scored by the 🚩 ORIGINAL's same-session
  grade: n · W / L · no entry · open or flat · mean R.
- **held by the rule — what the original did**: the originals whose record lists the rule in `failed`, scored the same
  way.
- **delta**: "removed {w} and {l} · {u} never filled".
- R is the 🏁's own: +`LEDGER_R_MULT` for a win, −1 for a loss, over decided rows only.
- A held A+ counts under EVERY rule it failed, so the held column can sum past the held total (`by_rule_note`).
- **T1's row** reads like a filter row. Its held side is labelled "held — cap reached — what the original did", and
  `tie_held` (holds with `values.T1.tie` true) is printed inside the served text: "{n} held on a tied bar — 🚩's ring
  order broke the tie".
- **T4's row**: the held side's n is `fired`; `fired_alone` (failed ids == [T4]) is served beside it: "fired on {fired}
  rung bars · alone on {alone}". Every other row serves `fired_alone` as null.

### Exit rows (T3_2R, T3_3R, T5)

- **with the rule**: the audited 🧪 rows (T3: 🌀 Intraday VCP only) graded by the modified exit, read from
  `gajjala_audited_exits`: n · W / L · open · mean R (the mean of the stored R over decided rows).
- **GG's math on the same rows**: the same ids by the 🏁's existing `same` column on the 🧪 ledger.
- **delta**: "{rule}: {ww} W / {wl} L · GG's math: {gw} W / {gl} L on the same {n}".
- A row with no exits doc yet is `pending`. When every row is pending, the delta reads "not graded yet — exit grades
  land the night after the session".

## The T5 walk

`audited_exits.t5_grade(row, bars_1m, bounds, frame5)`:

1. `g = ledger.grade(row, bars_1m, bounds, "same")`. Not filled → the entry word (`no_entry` / `no_time` / `no_plan` /
   `no_risk`), no outcome.
2. Filled: `fill` = `g.fill_px`, `R = trigger − stop`. The 1-minute bars are the ones `grade` walked
   (`fill_from ≤ t < same_end`).
3. The 5-minute closes are the GG5 frame's TODAY bars, built by `bars.build_frames(..., variant=GG5)` with the prior
   cached day as the EMA warm-up (the pass's own builder and masking), whose close is after the fill minute and at or
   before the regular close. The bucket holding the fill minute counts when it closes after the fill.
4. For each 5-minute close C: first every unseen 1-minute bar before C — a `low ≤ stop` is a **loss at −1R** (reason
   `stop`, or `stop_fill_minute` on the fill bar). Then, if the bar's `ema21` is not None and its close is **strictly
   under** it, **exit at that close**: R = (close − fill) / (trigger − stop); `win` if R > 0, else `loss`; reason
   `ema21_close`.
5. After the last close, the remaining minutes are checked for the stop only.
6. Neither by the regular close → **`open`**, R = None, with `close_r` (the last close's R) served as "so far".

Conventions: a close EXACTLY at the EMA is not under. An EMA warm-up value of None means no exit from that bar. The stop
always wins a tie inside one minute (the 🏁's own rule). The horizon end uses the house calendar (13:00 on a half day).

## Costs

- **The pass: 0 provider calls.** `refusal`'s `_exists`, `gga.alert_rows` and `gga.held_rows` are Mongo reads on the
  🧪 store. T4's number is already in memory (`result["strip"]`). The on-vs-off provider counter test stays EQUAL, and
  the dry-run log line still names only `gajjala_audited_*`.
- **The exits: one night later, warm cache only.** `nightly.grade_audited` runs `audited_exits.grade_exits` after the
  copy and the grade, in its own inner try (a fault serves `"exits": {"error": "exits: Type"}` and never hides copy or
  grade).
  - **Why one night later.** `daytrading.data.load_intraday` NEVER caches today and FETCHES a cold past day from
    Massive (`data.py:241-253`). Same-night exit grades would be one minute fetch per audited symbol. So a row dated
    today is `deferred_today` and graded the next night.
  - **The warm probe.** A row needs two symbol-days: its session and the prior market day (the EMA warm-up). Both are
    probed with `dt_data._mongo_get_day` first, a READ of `intraday_cache`. Either one cold → **`deferred_cold`**:
    nothing is loaded, nothing is fetched, the row is counted, served and retried the next night. A cold row is never
    fetched (HIS CALL #21).
  - Only then the loads, through `load_intraday` with no force, memoized per `(symbol, day)` for the run (2 symbol-days
    per row at most), bounded by `GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS` → `deferred_cap`.
  - Pinned by test through the REAL `load_intraday`: with both days warm, the fetch counter is 0 and `_mongo_put_day` is
    never called; with the prior day cold, `deferred_cold == 1`, 0 loads, 0 fetches.
  - The summary serves `rows, graded, written, not_due, deferred_today, deferred_cold, deferred_cap, load_failed,
    no_bars, faulted, loads, read_fault, dry, sessions`.
  - The honest line: what warms the cache is 🚩's 04:01 pass (`bars.frames_for`), and it skips names on budget or
    failure and only covers still-listed names. A name that fell off the list early can stay `deferred_cold`.
- **Storage.** A NEW 🧪-only collection `gajjala_exits` (physical `gajjala_audited_exits`), one doc per 🏁 row id, closed
  keys (`EXITS_KEYS` + the exit columns), versioned (`EXITS_VERSION`), no TTL. `LEDGER_KEYS` is closed and the shared
  ledger schema does not change; `upsert_ledger` never receives a new key.

## What was NOT built, and why

- **The float < 100M half of A1**: a no-op. K8 already caps the universe at 10,000,000 shares.
- **🧠 armed-only**: potentials are outside 🧪's A+ scope, and 🧪 never rings (HIS CALL #6).
- **G2 last-vs-longest**: unchanged, one word pending (HIS CALL #2).
- **Live 🧪 pushes**: still shadow, both locks (HIS CALL #1).
- **Any stop cap on 🚩** (HIS CALL #13) and the **K1–K10 audit items**.
- **No replay now**: 26 filled A+ would read TOO SMALL by construction.
- **No per-bar marker id** (`#held@{bar}`): under the Scope rule the first marker already sits on 🚩's claim bar, so a
  second id form would add a reader branch for no record.
- **The premarket bars**: never judged (HIS CALL #23).
- **No lane change.** G3 and every T rule stay off every lane until the lab's floor.

## HIS CALL (defaults built; nothing decided for him)

These continue the 15 in `docs/gajjala/audited_variant_2026_11_01.md`.

16. **T1 cap = 2** (his "two max", the ceiling) vs **1** (the floor). And the SAME-BAR TIE rule: built = 🚩's own ring
    order (setup order, then symbol — the order his phone already rings them), flagged and counted as `tie_held`. The
    alternatives are to hold the whole tie, admit the whole tie, or a ranking he names (REPORT §6 T1: "no ranking
    invented").
17. **T3 primary = +2R** (the lower bound, stated first); +3R is the second served column.
18. **T4 boundary**: "≤ +40% fails" (REPORT §6's words, pinned) vs the strip's `quiet` flag (strict <). One equality
    case; the number itself is `SA_QUIET_BEST_PCT` by name.
19. **A2 on the read's own frame** (the Fade's 15-minute volumes). HIS CALL #14 carried over.
20. **T5 on the 5-minute frame for every setup**, the Horizontal Fade included (the source says 5-min; the Fade reads
    15-min).
21. **Exit grades one night later from warm cache only** (0 provider calls, pinned). A row whose symbol-day is cold is
    `deferred_cold` and NEVER fetched; it stays ungraded and counted. Allowing ONE Massive minute fetch per cold row
    (what 🚩's own grade pays for its residual), or same-night grading at one fetch per audited symbol, is his.
22. **After-hours window on 🚩**: keep or cut (re-look 10-29: 4 of 5 unfilled A+ rang after hours). H1 lives on 🧪
    only; 🚩 is untouched here.
23. **Scope = the bars 🚩 would ring.** 🧪 never judges a premarket, first-15, late, closed or suppressed A+, because 🚩
    refuses them and there is no original to compare against. So T2's record is the 09:45–10:29 bars and H1's the
    after-hours bars. Judging the premarket bars too is a different question, with no 🚩 outcome to score against, and
    it is his.
24. RETIRED by #23. The `#held` marker's first audit is 🚩's claim bar by construction, so no idempotency change is
    needed.
25. **The ℹ️ panel clause now names 12 rules**: keep (built), fold, or trim to the ON filters.

Out of scope, unchanged, still his: #1 live 🧪 pushes, #2 G2 last vs longest, #6 🧠 armed-only, #13 any stop cap on
🚩, the K1–K10 audit items, and anything on the paper lane.

## 🏁 rows on the 🧪 Track record (2026-11-05)

Ajay 2026-11-05, verbatim: "Can you make both Gajjala's track record and Gajjalas 1 min and Gajjalas AUDIT HAVE similar
track record. It looks like our Gajjals 5 min had better win yesterday and today... I would like you to audit but its
hard to tell which ones won in Gajjlas Audit page". The trigger: "Why are the other winners not having charts?"

**The answer to the trigger, in one line.** The 🧪 🏁 listed ONLY an A+ that passed every ON audit rule. None has
since 11-01 (all 10 🚩 originals on 11-02…11-05 were HELD), so its A+ block had 0 rows and no chart. The "winners" on
that page were text lines in the compare's held list, not rows, so nothing was drawn for them. Now the 🧪 🏁 lists 🚩's
own A+ rows, and their charts come back through the same `aplus.charts`. Nothing new is drawn.

**What the rows are.** `audited_tab.track_block` serves 🚩's own served 🏁 block, `ledger.served_block(st.shared, …,
variant=V.GGA)`. That gives 🚩's rows, 🚩's grades from the ONE ledger (`gajjala_ledger`), 🚩's dedupe, and GGA's clip
(no session before `GC.GGA_RECORD_FROM`), words and `tab=gajjala_audited` links. The block adds ONE served column,
`audit` ("🧪 Audit"), right after the Ticker, so the FE's Tape splice keeps it third on the phone. Each row's ✅ / ❌ is
🚩's grade of the original. The `same` / `next` cells, `flag_text`, `bucket` and `dup_of` are byte-equal to 🚩's own 🏁
(pinned). No 🧠 row is listed (`GGA.ledger_push_states = ()`). The 🧠 zero lines (`counts_text`) and the 🎯 kind chips are
served null on this tab.

**The audit column's words** (`audited_tab.row_audits` → `_audit_cell`). Each call reads the 🧪 record on the row's own
bar, through the SAME `_record_of` the per-rule table scores with (extracted from `_attribute`; per_rule pinned
unchanged):

- "🧪 held by G1, G4": the rule ids only. The reason per rule stays in the compare's held list below, one place each
  (HIS CALL #31).
- "🧪 passed every rule": the verdict is the stored `aplus` boolean (`audited_rules._finish`). A claim judged while
  every rule was OFF reads "🧪 passed every rule" plus "no rule was on when it was judged". A passed row with a nightly
  exit doc gets the T3 / T5 exit grades as its sub-line, for example "T3 +2R: ✅ winner +2.0R · T3 +3R: not graded yet ·
  T5 21 EMA trail: ❌ loser -1.0R". The labels come from `AUD.T3_R_MULTS` / `AUD.T5_EMA`. The state words come from
  `EXIT_STATE_TEXT`, which has a word for every `ledger.CELL_STATES` member (no_plan / no_risk / split are pinned equal to
  the ledger's own `_cell` text).
- "🧪 not judged" plus "no audit record on this bar": no record on the row's bar, a record on another bar, or a record
  with no verdict (written before the audit key).
- "🧪 audit not read this time — the next re-read tries again": the audit read failed (below).

**ONE read, fail-visible.** The tab reads the audit ONCE per 🏁 build (`audited_tab.read_span`) and hands that dict
to both blocks. `track_block` never reads the audit itself. If the read raises (a LedgerReadError, or a malformed
stored grade), 🚩's rows are still listed, each with the "not read" cell, and `audited_compare` is served null. The
read is never re-run inside a block. If the row cells alone fail, the rows keep "not read" cells and the compare is
still served. If the SHARED ledger fails, the 🏁 serves `TRACK_RECORD_FAULT`, as before. A "not read" cell on the live
page means a read fault to chase.

**No today read.** The GGA route no longer calls `ledger.today_read` on any sub. A row of today reads the ledger's own
"not read yet · graded tonight `GC.LEDGER_GRADE_AT_ET` ET", and `today_text` is the ledger's W6 sentence. A today read
over the SHARED store would be 🚩's whole today read (🧠 + A+ names): up to `GC.LEDGER_TODAY_MAX` = 60 minute loads and
`GC.LEDGER_TODAY_BUDGET_SEC` = 15 s per cold GET. Its memo, `GC.LEDGER_TODAY_MEMO_SEC` = 300 s, equals the board's
refresh cadence, so an open 🧪 tab would re-pay that read beside 🚩's own on every refresh (HIS CALL #28).

**The "all"-span sessions.** `read_span` reads the sessions served_block reads over the SHARED store (every 🚩 A+
session ≥ the record start), together with the GGA store's own claim / marker dates. On today / yesterday / 5d / 10d
both are the same calendar window. On "all", a 🚩 A+ on a session where the overlay wrote nothing now counts
`recon.original_only` instead of dropping out. That is a correction, not a rule change, and the compare's other keys
are unchanged.

UNMEASURED: the rows measure nothing, and no rule, gate, threshold or registry default moved. Tests:
`backend/tests/test_gajjala_audited_track_2026_11_05.py`.

### HIS CALL (defaults built; nothing decided for him), continuing #25

26. **🧠 rows on the 🧪 🏁**: NOT listed by default (`GGA.ledger_push_states = ()`; 🚩's 🧠 rows are outside the
    audit's A+ scope). Listing them = flip that tuple.
27. **Audited-only rows** (a 🧪 claim with no 🚩 row, because the original's send failed; `recon.audited_only`, 0 on
    11-05): NOT listed as rows by default; the recon sentence counts them.
28. **Today's rows on the 🧪 🏁**: no live read by default (`today=None`). A row of today reads "not read yet — graded
    tonight `GC.LEDGER_GRADE_AT_ET` ET" until the nightly grades it, and the page loads nothing. The alternatives, with
    their cost: (a) `today_read` over the SHARED store, which is 🚩's whole today read (🧠 + A+ names, ≤ 60 minute loads
    / 15 s per cold GET; memo 300 s = the board's refresh, so an open 🧪 tab re-pays it every refresh beside 🚩's own);
    (b) a `kinds=` filter on `ledger.today_read` for A+ names only, which changes a shared-engine signature and needs its
    own spec. Either one is a single route line in api.py.
29. **The 🧠 zero lines (`counts_text`) and the 🎯 kind chips**: dropped on the 🧪 🏁 by default (served null, since no
    🧠 row exists on this tab), vs kept as served_block gives them.
30. **The rows mount BEFORE the compare / per-rule / by-day tables**: rows first by default (his "hard to tell which ones
    won"); the tables keep their internal order.
31. **Where the per-rule WHY sentences live**: by default the row's 🧪 cell carries the rule ids only ("🧪 held by G1,
    A1") and the compare's held list keeps the sentences. Up to 4 sentences per row in the third column at 430 px is
    clutter. The alternatives: put the sentences in the cell's sub_text (the held list then repeats them), or fold the
    held list away and keep the sentences only in the cell.
32. **The ✅ / ❌ flag, the categories and the charts on the 🧪 🏁 are 🚩's grade of the original** (the ONE ledger),
    never the T3 / T5 exit grade; the exit words are a sub-line on a passed row only. Grading the 🧪 list by an exit
    rule is a semantic change.
33. **The audit call as a COLUMN after the Ticker** (default; the FE's Tape splice keeps it third) vs a chip inside the
    Ticker cell.
34. **The 🏁 sub chip count on 🧪** stays `count_today` over 🧠 rows (0), unchanged. Counting 🚩's A+ graded today
    there is a semantic change.
35. **Wording (MINE)**: "🧪 passed every rule" · "🧪 held by {ids}" · "🧪 not judged" · "🧪 audit not read this time" ·
    "T3 +{k}R" / "T5 {ema} EMA trail". A claim judged while every rule was OFF reads "🧪 passed every rule · no rule was
    on when it was judged", because the stored `aplus` is the verdict. The alternative is "🧪 not judged".

Out of scope unless he asks: today's 🧠 rows showing "—" in the Tape column (the tape.py cost rule, AMENDMENTS11 F8,
lite_today), and #1 live 🧪 pushes, #2 G2 last vs longest, #16–#25 as listed above.
