# 🧠 Potential · 📈 Track · 🔔 `gajjala_potential` on Gajjala's tab (2026-10-15)

**UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs.** Nobody has measured potentials;
the study of his A+ setups read NULL (2026-10-14, `docs/gajjala/study_2026_10_13.md`).

> UPDATE 2026-10-16 (evening): A+ entries went live 2026-10-16; the 🧠 Track row shows "🎯 entry sent HH:MM ET"; the 🏁 ledger counts live A+ entries as "🎯 A+ entry" on their own 🎯 line (not pooled into the 🧠 %), shadow-period rows stay on the shadow line. Ajay's call ("you alert me when that happens"), not a measurement —
> docs/gajjala/entry_live_2026_10_16.md. This 🧠 kind, its window and its gate are unchanged.

## The ask (Ajay 2026-10-15, verbatim)

1. "In Gajjalas setup I wanna find potential stocks this shows me what has happened I am trying to setup for this tab
   to act like Gajjalas brain. So create a potential category in this section."
2. "In all the sub tab and add a track and alert to show me new potential is added everyday."
3. "Give me an alert all continous tracker on these specifically when I get alert I will jump on to ride the wave"

His knob answers (AskUserQuestion 2026-10-15):

| Knob | His answer |
|---|---|
| K1 what a potential is | "Structure forming, any gate still open" — the detector read's state `forming`; `ready` True = "trigger armed", else "building". `partial` is NOT a potential; `aplus` / `triggered` are "what has happened". |
| K2 alert hours | his routine: 04:00–20:00 ET, the first 15 minutes after the open muted (09:30–09:45, GG S8 14:41 "I don't take trades for the first 15 minutes" = `constants.NO_TRADE_AFTER_OPEN_MIN`). |
| K3 cap | none: every FIRST appearance of (symbol, setup) on a session pushes once; everything also lands on /alerts and in the tab's tracker. |

He will act on this alert: a NEW kind, LIVE (not shadow), owner-only, ON for his devices. The A+ kind
`gajjala_setup` stays SHADOW, untouched.

> UPDATE 2026-10-16 (evening): A+ entries went live 2026-10-16; the 🧠 Track row shows "🎯 entry sent HH:MM ET"; the 🏁 ledger counts live A+ entries as "🎯 A+ entry" on their own 🎯 line (not pooled into the 🧠 %), shadow-period rows stay on the shadow line.

## What a potential is (`potential.potential_kind`)

GG's common concept (S9 1:54:53): "strong demand, goes sideways at the top of the bars, volume subsides in those bars,
and if it reclaims the highs — this is the concept of all the moves." A potential = the first two clauses present, the
reclaim not yet.

- The ONE engine is the detectors' own read (`detectors.py`, the K1–K10 / H1–H5 criteria in `constants.py`). A
  criterion that failed makes the read `partial` — never a potential. `forming` means no rule failed and no break yet.
- `armed` = `ready is True` (the bool; a truthy value is "building"). `building` = forming, not ready.
- Never a potential (no code needed, they are `partial` / `none` by construction): the long flag (4–5 bars), the
  near-kiss, the VCP "B — imperfect", a 🎾 read with an unknown / suspect / too-large float.
  WIDENED 2026-10-18 (DECISIONS13 D1): a 4–5 bar forming Bull Flag IS a potential candidate now (K4 = 1–5, the long-flag
  band empty while `K4_BF_LONG_FLAG_MAX` is None); near-kiss, "B" and the 🎾 float cases unchanged.

Per setup, the forming read the potential reuses (trigger / stop it already carries):

| Setup | trigger / stop while forming | building reason (served) |
|---|---|---|
| 🚩 Bull Flag | the latest bar's high / low | "waiting for the pullback bar" (no base → not a potential) |
| 💋 EMA Kiss & Fly | the latest bar's high / low | "x% above the 9 EMA — waiting for the kiss" |
| ➖ Horizontal Fade | the base high (`HF_TRIGGER = "base_high"`) / the prior bar's low | "base n of 6 bars" |
| 🌀 Intraday VCP | the last cycle high / low | "n of 2 cycles" / "the last cycle is still making its low" |
| 🎾 Reversal Squeeze | the top bar's high / the base low | "squeezing back — the quiet base has not started" |

## The Cheetah defaults (MINE, not his — HIS CALLS)

All four are served as "Cheetah default, not his" on the ℹ️ panel (`potential.rules_lines`), the strip text
(`potential.defaults_sentence`), the tab's push line (`potential.push_note`) and Notifications.

| # | Constant | Default | What it does | Why |
|---|---|---|---|---|
| P0 | `POTENTIAL_NEEDS_BASE` | True | the base must hold ≥ 1 sideways bar — a demand leg alone is not a potential | DECISIONS4 "first two clauses present"; stops leg-only spam |
| P1 | `POTENTIAL_DEFER_REFUSED` | True | a first sighting held by the mute or a missing print rings at the next pass while still a potential AND every state since its first sighting was `forming` (AMENDMENTS4 D3) | the A+ precedent: a refusal never consumes the day's claim |
| P2 | `POTENTIAL_FRESH_TAPE` | True | a push waits for a print in the 5-minute bar that just closed (`alerts.MAX_ENTRY_AGE_SEC`, reused) | a forming read with no print is not "a wave" |
| P12 | the JOIN RULE (permanent, no constant — AMENDMENTS4 D9) | on | the first pass after a break in the 5-minute pass chain (a deploy, a cron restart, a host sleep) with the 📈 Track still empty after 09:45 tracks what is already forming as `first_seen_mode: "joined"`, held `joined_midsession` — it NEVER rings | a mid-session restart must not ring every forming name in one burst |

The three constants are listed in `constants.CHEETAH_DEFAULTS`; their comments start "Cheetah default (MINE, not GG —
HIS CALL Px)" (the provenance test). The only new number is TRANSPORT: `PASS_MINUTE_OFFSET = 1` (= the crontab minute
field `1-56/5`, test-pinned), used only to print the pass schedule.

**The join rule — the executor's reading (HIS CALL P12).** D9 says "a pass where the tracker holds ZERO docs for the
session AND the pass clock is past the mute end". Read literally, a quiet morning (no potential at all before 09:45)
would also hold zero docs at 10:06, so the day's first genuine sightings would never ring — against K3 and against
D9's own "a normal day … is unaffected". The engine therefore joins only when, in addition, the IMMEDIATELY previous
pass did not run the potential gate: no pass doc of the session in `gajjala_passes` stamped within `PASS_CADENCE_SEC +
LEASE_SEC` (300 + 280 s, both existing TRANSPORT constants — no new number) before the pass clock carries a `potential`
block. Any break in the chain re-joins — a host sleep, a cron restart, a deploy, or a pass doc written before this
build. The read is `store.recent_passes` (that window only, projected to `{at, potential}`); a read fault joins (fail
closed: tracked, not rung). D9's three tests hold: zero docs + 04:01 rings; zero docs + 10:06 with no previous gate pass
joins; one existing doc + 10:06 rings. A quiet morning with an unbroken chain rings
(`test_D9_NEGATIVE_a_quiet_morning_is_not_a_join…`); early empty passes, a 3-hour gap, then 11:01 joins
(`test_D9_NEGATIVE_early_empty_passes_then_a_3_hour_gap…`). Literal D9 (drop the previous-pass clause) remains HIS
CALL P12.

**Fix round 1 (2026-10-15).** Review findings resolved in the engine: (1) the join rule's earlier-pass clause counted
ANY earlier pass of the session, so a gap after quiet early passes rang every forming name in one pass (probe: six
sends at 11:01 after passes at 04:01 / 04:06 / 07:56) — it now reads only the immediately previous pass (above); (2) a
doc first seen by a join pass never rings even when its `joined_midsession` hold write was lost (`eligible` reads
`first_seen_mode`, written in the same upsert that creates the doc); (3) D3 continuity now needs every `state_path`
entry to be a POTENTIAL (`forming` AND kind armed / building) — a base-less `forming` read is a new leg, so a muted hold
never re-rings across it; (4) a tracker read fault on a doc the pass already saw on file skips that name for the pass
(counted `failed`) instead of re-creating its timeline and move; (5) the previous-pass read is windowed and projected,
never the session's whole pass bodies.

**Fix round 2 (2026-10-15, final critic).** (1) The join rule's previous-pass clause now needs a COMPLETE count: a pass
doc whose `potential` block is run.py's `{}` (the gate raised) or a join pass whose writes were all lost (`joined` > 0,
`tracked_today` 0) does not count as "the gate ran", so the next pass joins again instead of ringing every forming name
(`potential._gate_block_ok`; `test_NEGATIVE_D9_a_join_pass_with_every_write_lost…`). (2) D3 continuity runs before the
store-fault and no-hold shortcuts: a RULE hold (alone or beside `claim_error`) and a doc with no hold at all (its hold
write may be the lost one) ring only while every `state_path` entry is a potential; a `claim_error`-only doc is still
retried as the spec says. (3) /alerts maps the pass counter `joined` (was the held reason `joined_midsession`, so the
chip never showed). **What the join rule does NOT cover (HIS CALL P12):** a gap that ends before 09:45 with the tracker
empty (that pass is no join pass), and a gap of any length while the tracker already holds docs for the session — names
first seen after such a gap ring as normal first sightings. Joining on any break in the 5-minute chain (dropping the
"tracker empty" condition) is the alternative; not built.

## GG's tells — badges and order, never gates (`tell_values` / `tells` / `order_key`)

| Badge | From | Cite |
|---|---|---|
| float (`Float 3.1M`) | the read doc's `ctx.float` (a suspect float under `FLOAT_SUSPECT_POLICY = "ineligible"` is unknown) | S8 21:04 "the lower the float the better" |
| 🔄 float rotation | `ctx.rotation` (None with an unknown float) | S8 1:15:24 "the float is rotating" |
| ⏸ halts today | `ctx.halts` | S9 2:00:32 "a halt is nothing but too much demand in a very short time" |
| 🌙 after-hours mover last session | the previous session's ☀️ carry doc | S8 13:21–14:34 "after hours moves from the past day, I'll keep them as well" |
| 📅 on his scanner the session before | the previous session's `gajjala_scan` doc | S9 2:02:47 "previous-day strength" |
| 🧩 also forming | the other setups of the same name that are a potential this pass | S9 1:59:01 "two or three setups mixed together … the certainty of the move is higher" |
| ↻ also a potential last session (tab only) | a tracker doc for (previous session, SYM, setup) | S9 1:17:32 "stay a couple of days, make noise a couple of days" |

An unknown value yields no badge (never "0", "None" or "unknown"). Order (HIS CALL P4): trigger armed before building,
then float ascending (unknown last, by a flag — never coerced to 0), then volume descending, then the SETUPS order, then
the symbol.

## 📈 The tracker — Mongo `gajjala_potentials` (`store.POTENTIALS`)

One doc per (session, symbol, setup), `_id = "{date}|{SYM}|{setup}"`, written ONLY by `potential.track()` inside the
5-minute pass. Created at the FIRST pass whose read is a potential; after that it follows every state of that read for
the session (forming → aplus / triggered / stopped / partial / invalid / none / 🪦 graveyard), appended to `state_path`
only when (state, kind) changes — a replayed pass rewrites a byte-identical doc.

- Identity + first sighting (`$setOnInsert`): `date, symbol, setup, frame, first_seen (UTC, the pass clock),
  first_seen_et, first_seen_mode ("normal" | "joined"), first_kind, first_px, first_trigger, first_stop,
  first_risk_pct, first_bar_t, first_reason, first_tells`.
- Every pass (`$set`): `last {at, at_et, state, ready, kind, trigger, stop, px, bar_t, reason}`, `state_path`,
  `move_pct`, `vs_trigger_pct`, `line` (the latest potential's W5 line — what /alerts lists), `url`, `updated_at`, `at`.
- Guarded fields, never written by `track()`: `push {state, at, at_et, kind_at_push, result}`, `held [{at_et,
  reason}]` (one entry per distinct reason), `graveyard_on`.
- Price (AMENDMENTS4 D2): the 5-minute frame's latest CLOSED close first; the scanner row's price only when the row is
  THIS pass's (a qualifier or the live snapshot), never the stored row.
- Every stamp is the pass clock — `potential.py` never reads the wall clock (an AST test).
- Retention: KEPT, no TTL (the study's data spine, HIS CALL P7). Indexes `(date, symbol)` and `(symbol, date desc)`.

Write rules (two overlapping passes can never wipe a claim): `track()` makes ONE `update_one` upsert with disjoint
`$setOnInsert` / `$set` key sets and refuses a clash or a guarded field; the claim (`claim_potential_push`), the hold
(`hold_potential`) and the graveyard mark (`mark_potential_graveyard`) are guarded `update_one`s (`push` /
`graveyard_on` absent); the settle (`settle_potential_push`) is a dotted `$set` of `push.state` / `push.result` /
`push.at_et` only. There is no whole-doc replace on this collection and no `put_potential`. Every store method
soft-fails (a read answers its empty value, a write answers False / "error").

## 🔔 The push gate (`potential.run_pass`, called by `run.run_pass` after the A+ gate)

For every (SYM, setup) potential of the pass, in `order_key` order:

1. `track()` the read; count `potential` / `armed` / `building` / `new`.
2. Eligible to ring: never claimed (`push` absent — K3) AND one of: a first sighting; no hold at all (it never rang); a
   STORE hold (`claim_error` — always retried, whatever P1 says); P1 on, a RULE hold and every state since the first
   sighting a potential — `forming` with kind armed / building (D3). A doc with `first_seen_mode: "joined"` or a
   `joined_midsession` hold never rings. A tracker read that misses a doc already on file skips the name that pass
   (`failed`), never re-creating it. A tracker that cannot be read AT ALL (`store.potentials` None — no handle, or the
   find raised) skips the whole gate for the pass: nothing tracked, claimed or sent, the potentials seen counted
   `failed`, `tracked_today` left out so the next pass reads it as a gate that did not run (D9 fails closed). Final
   critic 2026-10-15: read as an empty tracker, every joined doc would have rung in one burst. Second guard: the claim
   itself (`store.claim_potential_push`) never lands on a doc first seen by a join pass (`first_seen_mode: joined`).
3. Refusals, in order, each recorded once on `held`, never consuming the claim: `joined_midsession` (the join rule) →
   `closed_day` (`market_hours.gate`, weekends + NYSE holidays) → `outside_hours` / `muted` (`window_reason`) →
   `stale_tape` (P2).
4. `dry` → counted, nothing written or sent.
5. Claim: `claimed` → send; `taken` → re-read: it has `push` → `claimed_before` (another pass owns it), else `failed` +
   `claim_error` (the doc was never written); `error` → `failed` + `claim_error`. A store fault costs one pass, never the
   session.
6. Send (`push.hooks.notify_gajjala_potential`, owner-only): raised → `failed` (never retried); `sent > 0` → `pushed`;
   `total_targets == 0` → `no_target` (toggle off, quiet hours or none registered); else `failed`.
7. After the loop: the graveyard mark (`scanner.graveyard_today`, GG S9 1:17:32) and `tracked_today`.

It never touches `gajjala_alerts`, never calls the A+ sender, never reads `GAJJALA_PUSH_MODE`. The A+ gate and the
potential gate run in their own `try` (AMENDMENTS4 D1): one raising never silences the other; each /alerts row carries
its own reason (`run._record_potential_status`, kind from `constants.POTENTIAL_PUSH_KIND`).

### The window and its intersection with the pass schedule

`window_reason` is judged on the PASS clock (HIS CALL P3): `outside_hours` before `ET_PREMARKET_OPEN` (04:00) or after
the extended close (20:00; 17:00 on a NYSE half day), `muted` from `ET_RTH_OPEN` (09:30) for `NO_TRADE_AFTER_OPEN_MIN`
(to 09:45). The pass runs at minutes 1, 6, … 56 from 04:01 to 20:01 (`run.py`, the crontab `1-56/5 4-20 * * 1-5`), so
the ringing passes are 04:01 … 09:26 and 09:46 … 19:56 ET (16:56 on a half day); 09:31 / 09:36 / 09:41 are muted (a
first sighting there rings at 09:46 if still a potential, P1); the 20:01 pass never rings. The 04:01 pass has no closed
5-minute bar of the session yet and cannot find a potential, so the copy says "passes from 04:01", never "first possible
ring" (`pass_times` builds both times from the constants).

### The copy (exact)

- Title: `🧠 {SYM} · {emoji} {label} — {trigger armed | building} · UNMEASURED` (D8: UNMEASURED in the title).
- Body: armed `trigger {T} · stop {S} (−r%)`; building `{reason} · trigger {T} (not armed yet) · stop {S} (−r%)`; then
  the tail `UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs` right after the trigger / stop
  clause (so the lock screen shows it); then the session badge (pre-market / after-hours), `first seen HH:MM ET`, the
  float and rotation badges last.
- `url = /chart-maps?tab=gajjala&sub=<setup>&focus=<SYM>`, `tag = gg-pot-<setup>-<SYM>`, `kind = gajjala_potential`,
  `items = [{symbol, text: the W5 line}]`.
- Never the b-word, never a forecast word (`high_beta_tab.FORBIDDEN_WORDS`, checked in the TEST only), never another
  method's name.

## The served contract (§3.9 — owned by this engine)

Every served key the tab (WP-B) and the board (WP-D) rely on comes from `potential.py`: `potential_kind`, `tells`,
`tell_values`, `order_key`, `row_text`, `line`, `state_word`, `push_note`, `rules_lines`, `pass_times`,
`defaults_sentence`, `KIND_LABEL`, `HELD_WORDS`, `CONCEPT`, `AGAIN_TEXT`, `TAIL`.

### Render order on the 🧠 sub (2026-10-18)

Ajay, on a screenshot of the sub after Friday's close: "this view is confusing are there 2 potential here?" → "Oh I think
we should bring them to the top of the view". The board draws, in order: the 🎯 A+ line, the counts line (board-wide, all
five setups — "forming" there counts reads, not potentials), the LIVE potential tiles (the sub's number = distinct symbols
with a potential at the last pass), then the 📈 Track (that session's first sightings and what became of them), then the 👀
watch line. Before 2026-10-18 the Track and the watch line came before the tiles. Served contents unchanged; FE tests
"the live tiles come first" pin the order (NEGATIVE: the empty note also precedes the Track; setup subs unchanged).

## Push volume — UNKNOWN until the replay reads

A dry run cannot dedupe a day. The scratchpad replay (`scratchpad/gajjala/probe/potential_volume_replay.py`, never the
repo) runs every pass clock of the last 3 sessions through the real branch pass with an in-memory tracker, the snapshot
stubbed, the list filtered by `first_qualified_at` (no look-ahead) and every other collection a recorder. The main
session runs it off-RTH in the throwaway container and tells him the count per day before the deploy. It is an
operational count on past bars — not a forecast, not an edge claim.

## The later study (data spine — NOT built)

Only on his ask, with a pre-registration: `backend/scripts/gajjala_potential_study.py` + its test + a dated doc. Event
= a tracker doc's first sighting (pass clock, `first_px`, `first_kind`); outcomes from the 1-minute bars (reached A+ /
triggered / stopped; R from `first_trigger` / `first_stop`); placebo = same-session listed names with no potential;
expectancy and the stop-out rate beside any win rate; clustered CI. Until it reads, every surface says UNMEASURED.

## HIS CALL (each ships with the default shown)

- P0 what counts: forming WITH its sideways part begun (default) vs every forming read incl. leg-only.
- P1 a held first sighting rings on the next eligible pass while still forming (default) vs never that session.
- P2 the fresh-print wait: on (default) vs off.
- P3 the 09:30–09:45 mute on the pass clock (default) vs the A+ rule (the bar's start).
- P4 order inside a group: lowest float first, then volume (default) vs rotation vs nearest to its trigger.
- P5 a second push when building turns trigger armed: no (default, K3) vs yes.
- P6 one push per (name, setup) — a name forming in three setups rings three times (default, K3) vs once per name.
- P7 tracker retention: kept (default) vs 30 days.
- P8 the 🧠 sub position: last in the row (default) vs first / the default sub.
- P9 the 👀 "on his watch list, no structure yet" line: shown (default) vs hidden.
- P10 a chip for `partial` names: not built (default off).
- P11 the Notifications text names the A+ study's NULL read (default) — keep or drop.
- P12 the join rule after a mid-session deploy: tracked, never rung (default, permanent) — and the executor's
  "no earlier gate pass" reading of it, above.

## Tests

`backend/tests/test_gajjala_potential.py` (the engine), `test_gajjala_store.py` (the guarded writes),
`test_gajjala_constants.py` (the values and the Cheetah-default labels), `test_gajjala_run.py` (the pass end to end, D1 /
D2 / D9). Hermetic, in the api image:

```bash
docker run --rm --network none --name cheetah-tmp-pytest-wpa -v /Users/ajay/clinet-test/wt-highbeta:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_potential.py tests/test_gajjala_constants.py tests/test_gajjala_store.py tests/test_gajjala_run.py tests/test_gajjala_source_guard.py tests/test_gajjala_alerts.py
```

2026-10-16 — every 🧠 push that rang is now graded win / loss by GG's trade math on the 🏁 Track record sub: `docs/gajjala/track_record_2026_10_16.md`.
