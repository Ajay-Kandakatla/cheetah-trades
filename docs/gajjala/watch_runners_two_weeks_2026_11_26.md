# 📅 Runners kept on the 👀 Watch for two weeks — the seat (2026-11-26)

Ajay 2026-11-26 ~21:40 ET: "Ok then add them to our watch list and track them please.. I know he tracks them for two
weeks sometimes.. before he discards them.. Can you do that please" · ~21:50 ET: "Make it 30% please after A+".

Spec: watchrun rev 2 §3.1–§3.3, work package `be-seat`. Engine: `backend/chart_maps/gajjala_watch/runseat.py` (one
engine, a fourth doc `{_id: "runners"}` in `gajjala_watch_list`). The nightly record is a separate package
(`runtrack.py`, its own doc). Display and tracking only — never a push, a gate, a cap or an eviction. **UNMEASURED.**

## The rule (the live reading, `C.RUNNERS_SEAT_READING` = `"after_aplus"`)

- **No 🚩 A+ that session** → `runners.ran_of` at `C.RUNNERS_SEAT_DAY_PCT` (= `C.RAN_MIN_PCT`, +40%): the 09:30–20:00
  ET high vs the prior close, the peak not premarket.
- **A 🚩 A+** (5-minute page or the retired 1-minute page, `C.RUNNERS_SEAT_PAGES`) → only a 1-minute high at or over
  trigger × (1 + `C.RUNNERS_SEAT_APLUS_PCT`/100) — his 30 — between max(ring + 30 s, 09:45 ET) and 20:00 ET of the
  session the Track record grades the ring on. A ring after the regular close plays on the next session.
- `runseat.from_trigger` is the app twin of the 🎬 pipeline's `replay_win30.measure`; a test imports the pipeline from
  the host folder and pins equal output on six synthetic cases (pass, under, exact bar, premarket spike, ring after the
  close, no bar). The split guard is app-only (HIS CALL #18).

### The three readings — one line, `C.RUNNERS_SEAT_READING` (HIS CALL #1)

| Reading | What seats | Probe, next step 2026-11-27 (splits asked) |
|---|---|---|
| `after_aplus` (shipped) | no A+ → +40% day rule; an A+ name → ONLY +30% above its trigger | **142 run-days · 114 names** |
| `seat_cut` | every name at +30% vs the prior close, A+ or not; the A+ rule off | 208 run-days · 164 names |
| `either` | the +40% day rule for every name, AND an A+ name also at +30% above its trigger | **157 run-days · 126 names** |

`processed` is keyed by reading: a flip re-reads every session of the window still on file and only ADDS.

## The guards (no new number)

- **A+ split guard [C1]** — a split in (ring date, the ET date the cached 1-minute day was fetched] → `aplus_split`,
  never measured, never seated. The window ends at the FETCH date: a completed day is cached on a later date and is
  re-based by a split in between (SRTM 11-20: 1-for-9 on 2026-11-23, cached 11-23 14:51 UTC, "+838%" on the app's own
  cache vs the pipeline's +4.2%). A day with no stamp (loaded this step) → today = the widest window.
- **Day guards [C2]**, only for a name already over the cut: (a) a listed split that day — the scanner's stored check
  "ok" answers free; anything else goes to the house lookup (`ledger._default_split_lookup`) → `split_day` /
  `split_unchecked` (pending); (b) the scanner's stored daily record: `daily_ok` False → `no_prior_bar`, record
  missing → `prior_unknown`. HZN 11-16 (prior close 1.76, first bar 88.0, no split listed, check "ok") and ANT 11-19
  are a first session under the ticker → not seated.

## Provider budget [C8]

The step runs at the END of the Watch loop's minute (after the frames, every tile write and the `latest` state write),
on what is left of `GC.GG1M_MINUTE_BUDGET_SEC`; the no-names path hands it the whole budget. Per step: at most
`C.RUNNERS_SEAT_PROVIDER_MAX` started provider reads (split checks + cold 1-minute days; TRANSPORT, borrowed by name),
none after the deadline, stop at the first failure, the module's own breaker. A failed item is asked again only on a
later session; a deferred one the next minute. Cached days and stored checks are free. A provider failure is pending,
never "no bars".

## Window, the doc, his ×

- Kept `C.RUNNERS_KEEP_SESSIONS` = 10 sessions, the run day = day 1; day 10 kept, day 11 "aged". A new qualifying day
  restarts the count (`C.RUNNERS_SEAT_RESTART`).
- Each completed session is judged at a later session's first minute steps (≈ 04:00 ET); a session with an open item
  is re-read the next minute (stored reads 5–9 ms). A session whose scan names lost their reads is `partial` and the
  count is served.
- **Two ×.** The roster's × (`DELETE C.API_RUNSEAT_PATH`) calls ONLY `runseat.dismiss`: blocks that run day and that
  session in this doc only, never the owner / 🤖 / ✅ docs. The plain tile × is unchanged and never touches this doc;
  its pairs (✅ doc, 🤖 doc) block a run of the SAME day, and that run is written to `removed` with reason "blocked"
  so the record still follows it (DOGZ 11-25).
- `removed` is pruned by the entry's run day: a ×'d or blocked run stays until its own 10 sessions end; an aged run's
  window is over when it leaves.

## Served

- Board key `runners` (absent when nothing is seated): one row per seated runner — `day_text` "📅 day N of 10", the seat
  chip ("+176% day" / "🎯 +34% from A+"), 🚫 last, `on_watch`, `remove_title` on every row; the hint states the live
  reading's sentence + the not-seated / pending / partial counts. A row with a tile gets `runner` (absent otherwise).
- `GET C.API_RUNTRACK_PATH` — the nightly record (owner only, `runtrack.payload`, imported lazily).
- ℹ️ `rules_info._gg_watch_runseat_clause()` = `runseat.rules_line()` (every number from the constants at call time).
- The step's last result: `gajjala_watch_state` doc `runners` (with its own `wall_s`); the `latest` doc gains no key.

## Numbers (spec §1.3, read-only probes 2026-11-26 night, market closed)

Stored reads reach back to 2026-11-13 (14-day TTL per doc). 158 +40% runner-days / 129 names in 9 sessions; 72 of 158
peaked at or after 16:00. Daily record present 158 of 158, `daily_ok` False on 2 (HZN 11-16, ANT 11-19). Scanner split
checks: 398 "ok", 3 held, 0 "failed" of 401. Watch loop 4.5 s of 35 s for 52 names; board 5.59 MB raw / 1.44 MB gzip.

## The probe — `backend/scripts/gajjala_watch_runseat_probe.py` (read-only)

Re-implements the judging piece for the container (origin/main has no runseat); `tests/test_gajjala_watch_runseat_probe_2026_11_26.py`
pins probe == engine on fixtures under all three readings. Default = stored reads only (no provider read; an A+ whose
split window is not on file prints "split check not asked"). `--splits` (refused 09:30–16:00 ET) asks each item once
through the house lookup with a pause.

Run 2026-11-27 03:51 UTC with `--splits` (next step session 2026-11-27, window 11-13 → 11-27, 79 A+ rings), reading
`after_aplus`:

- **A+ seats (10, 5-minute page):** GLXG 11-25, LVWR 11-24, MRM 11-24, SCAG 11-23, MPU 11-19, RAYA 11-19, CENN 11-17,
  GIPR 11-16, GP 11-16, AIMD 11-13 (day 10). AKAN seats by the day rule on 11-24 (5 runs).
- **BGLC** day rule 11-25 (day 2) · **POM** day rule 11-25 (day 2) · **NCPL** day rule 11-19 (day 6).
- **Not seated:** HZN 11-16 and ANT 11-19 `no_prior_bar`; SRTM 11-20 `aplus_split`; ran +40% but the A+ under +30%:
  BZFD 11-13, CRDF / GDHG / SMX / VIVK 11-17, AZI 11-18, NUR 11-19, AKAN / LABT / POAS 11-20, BENF 11-24, FFAI / TWG
  11-25; DOGZ 11-25 blocked by his × (written to `removed`).
- **Pending:** PLCE 11-16, BENF 11-25, RMSG 11-25 (1-minute day not cached — loaded at the first step); TOPP / DKI rang
  11-25 after the close → play on 11-27, pending until it is over.
- Under `either`: SRTM seats by the day rule (its 5-minute reads are on one share count); GLXG 11-24, TOPP, TWG and DOGZ
  stay off by his ×.

Raw outputs: the session scratchpad `watchrun/runseat_probe.out` (stored only) and `watchrun/runseat_probe_splits.out`.

## Not done here (HIS CALL)

The reading (#1); live tiles for every runner (#2); the existing 📅 strip and the 🎬 pipeline keep their missing guards
(#17, #18); seating a first-session pop (#16).

**2026-11-26 refix: whole-% floor.** An A+ run used to store `run_pct` rounded to 1 decimal, and the chip, the title and the Track record then floored that rounded number. A high of 1.3496 on a 1.00 trigger is +34.96%. It was stored as 35.0 and printed "🎯 +35% from A+", which reads as more than the stock actually did. The run now stores the value at the house rounding (`RAN_PCT_ROUND`, 4 decimals), and every print floors that value: "🎯 +34% from A+" and "+34.9%" in the title. The 0.90 → 1.17 case still stores 30.0. `from_trigger`'s 1-decimal `run_pct` key (the replay_win30 parity pin) is unchanged.
