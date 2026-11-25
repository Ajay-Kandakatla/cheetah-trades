# 💧 "Armed, volume dried" — push + forward tracker on 🚩 Gajjala (GG5) — 2026-11-24

## The ask, verbatim

Ajay 2026-11-24: "Can you track something for me how many times have the stocks bumped right after volume dried up.. I
noticed that the best entries so far have been after volume dried up.. after all the other rules. Can you send me
notification of volume dried please.."

"Volume dried" is GG's own K3 row (`detectors.K3_VOL_KEY`); `K3_VOL_FRAC` is Ajay's number. GG S9 1:57:33: "volume
completely dried out and the price is not going down … then it makes a big move." No new number is added.

Code: `backend/chart_maps/gajjala/vol_dried.py` (engine), wired in `run.py` (after the 🧠 step), `nightly.py` (`main`,
after 🧨), `tab.py` (`push_vol_dried`, GG5 only) and `supply_demand/rules_info.py` (the ℹ️ clause after 🔀).
Tests: `backend/tests/test_gajjala_vol_dried_2026_11_24.py`.

## The finding he must hear BEFORE the deploy

On today's rules, "every rule but the break + volume dried" IS the 🧠 "trigger armed" moment: K3 is a hard row on all
five setups, so a K3 miss makes a card `partial`, never "armed but not dried" (the invariant test pins it over the
detector fixtures). Inside one structure K3 never goes ✗→✓; an armed turn is set off by whichever OTHER row completes
last. So the 💧 ring mostly lands on the same pass as a 🧠 armed ring of the same name and setup.

Probe A (planner, read-only, 8 stored sessions; first armed entry inside the 🧠 window, not muted, not joined; no K11,
no stale tape, no vol_row — an UPPER bound, frequency only, never an edge):

| Session | 💧 would ring | same pass as a 🧠 claim | 🧠 pushed |
|---|---|---|---|
| 11-13 | 31 | 22 | 22 |
| 11-16 | 19 | 15 | 15 |
| 11-17 | 27 | 20 | 20 |
| 11-18 | 21 | 17 | 17 |
| 11-19 | 25 | 21 | 21 |
| 11-20 | 22 | 20 | 21 |
| 11-23 | 22 | 22 | 21 |
| 11-24 | 32 | 27 | 28 |
| **8 sessions** | **199** | **164 (82%)** | 165 |

Probe C (where the 204 first-arms fall, incl. the muted) — the losses the upper bound cannot replay:

| When (ET) | First-arms | What happens to them |
|---|---|---|
| pre-09:30 | 29 | likely under the 1M K11 floor → held; a held turn never rings later (HIS CALL #2) |
| 09:30–09:45 | 5 | muted; 3 were still armed at 09:45 — the 🧠 defer-rings them, the 💧 never |
| 16:00–20:00 | 59 | rings after the close; graded on the ring evening + the next session |

Re-runnable count script (read-only, **UPPER bound — cannot replay vol_row, K11 or stale tape (the tracker stores
none)**; it calls `entry_marks.ready_since` on each prefix of `state_path`, the same function the ring calls; a re-arm
after a muted / outside first arm counts, so it may read above 199):

```bash
docker exec -i -w /app <scratch container on the branch> python -m scripts.gajjala_vol_dried_count --sessions 8 --json
```

## The gate (order; every refusal COUNTED, never written, never consuming the claim)

| # | Check | Count key |
|---|---|---|
| a | `potential_kind(read) == "armed"` (forming + ready, base ≥ 1, no variant / grade) | skipped, uncounted |
| b | its own K3 row met (`tab.vol_dried_text`, the 💧 chip's engine) | `no_vol_row` |
| c | the 🧠 tracker doc on file, and `entry_marks.ready_since(doc) == potential._utc(now)` (turned THIS pass) | `no_tracker` / `steady` |
| d | `ledger.plan_of(trigger, stop)` is "ok" | `no_risk` |
| e | not a closed day (`alerts._closed_reason`) | `closed_day` |
| f | the 🧠 window (04:00–20:00 ET, 17:00 on a half day; never 09:30–09:45) | `outside_hours` / `muted` |
| g | a print in the 5-minute bar that just closed (`POTENTIAL_FRESH_TAPE`) | `stale_tape` |
| h | GG's K11 session floor (`K11_MIN_SESSION_VOLUME` on the pass's own volume; unknown → held) | `under_floor` |
| i | not dry; an alert collection | `dry` / `no_store` |
| j | the insert-only claim `GGD:{date}\|{SYM}\|{setup}` (BEFORE the send) | `claimed_before` |
| k | mode "off" → recorded `dried_shadow`, the sender NEVER called | `shadow` |
| l | live: the owner-scoped send → settle | `pushed` / `no_target` / `failed` |

Once per (session, symbol, setup). A second setup of a name rings too (HIS CALL #12). A held transition never rings
later (HIS CALL #2). run.py hands the SAME `now` to the 🧠 step and this one — that is what makes the equality hold; the
step runs only when the 🧠 gate completed this pass (`tracked_today` in its counts), never on an open, a dry run or
`Deps()`, in its own try (never `out["errors"]`, never a key of `out` — the WRITES golden is byte-identical).

## The payload

- title `💧 Armed, volume dried · {SYM} · {emoji} {label}` (+ ` · 🚫` on his broker list)
- body `trigger $x · stop $y (−r%) · {K3 row label} ({value}) · [📌] · [🎪] · [🚫 text] · UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs`
- tag `gg-dry-{setup}-{SYM}` (never `gg-pot`, so the 🧠 notification is not replaced) · url = the card on its sub ·
  kind `gajjala_vol_dried` · no `items`

## The tracker (the claim doc IS the record)

`gajjala_alerts`, `_id` `GGD:{date}|{SYM}|{setup}`: date, symbol, setup, frame, bar_t, trigger, stop, risk_pct, price
(the 5-minute close), kind, mode, state, at (pass clock), at_et, transition_at (the ready_since stamp), vol_row
{label, value, need}, + trader / promo only when tagged.

States (all `dried_`, never a ledger word): `dried_claimed` (in flight) → `dried_pushed` / `dried_no_target` /
`dried_failed`; `dried_shadow` with the mode off. RECORDED = every state but `dried_claimed` — graded and counted, so a
no-target or failed ring stays in the record.

**Claim fault (fail-open, bounded).** `demand_alerts.claim_key` reads True on a WRITE error (the house helper the A+ /
🔀 / 🩳 pushes share). That pass sends ONCE with no record (the settle likely fails too). It is bounded to ONE send:
the transition holds for one pass only, so the next pass reads `steady`. A test pins it.

## The grade (20:15 ET nightly, `vol_dried.grade_night`, under `gajjala_vol_dried`)

Every RECORDED GGD doc of the ledger's lookback (`LEDGER_GRADE_LOOKBACK_SESSIONS`) whose same session ended
(`now ≥ same_end + ledger.SETTLE`), not yet graded at `GRADE_VERSION`:

- `ledger.grade` (the ONE trade-math engine), same column: triggered (fill from 09:45 ET), `won` = outcome "win"
  (+`LEDGER_R_MULT` R before the stop)
- `stop_first`: the first eligible minute touching the stop is before the fill (or there is no fill); a same-minute
  fill + stop is False (ledger's "stop_fill_minute" loss)
- `max_high`: the best high of the eligible minutes BEFORE the first stop-touch minute (that minute excluded — its order
  inside the minute is unknown); vs the ring price and the trigger in %, and `r_max` = `ledger.r_past`
- **After-close ring**: loads the ring date AND its same session (merged), so a stop-out on the ring evening counts in
  stop_first and max_high; fills stay on 09:45–16:00 of the same session, so triggered / won are unchanged. The split
  guard is ledger's (True/iso → `split`; unread → retried).
- Loads capped at `LEDGER_BACKFILL_MAX_SYMBOL_DAYS` (the rest `deferred_cap`); a failed load of either day is retried,
  never written. A failure lands under `gajjala_vol_dried.error` — never in `errors`, never in the exit code.

## The count line (`push_vol_dried`, GG5 boards only, inside the ⓘ fold)

Over the last `LEDGER_SPAN_SESSIONS_LONG` (10) sessions:

- none: `💧 Volume dried: none in the last 10 sessions · UNMEASURED`
- some: `💧 [N recorded · ]M rang · T triggered · W hit +1R · S stop-first — last 10 sessions[ · K not graded yet][ · pushes off now, recording only] · UNMEASURED`

"N recorded · " shows only when it differs from "rang". Ints only; a stored NaN / "yes" / 1 never counts. A read fault
serves `null` (tab `_soft`). Absent on 🧪 / 1-minute boards.

**Golden.** BOARD regenerated by the RECIPE (`GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_variant_gg5_identity.py
-k test_gg5_board_is_byte_identical`): 56 leaves ADDED, 0 changed, 0 removed — `push_vol_dried` {mode "live", text the
"none" line} on all 28 boards (the recording fake's alerts coll answers the find). WRITES byte-identical (sha1
7d857dc9…). The three FE fixtures built from GG5 boards moved the same way by their own `-k golden` recipes (on_open +6,
potential +4, track_record +6, `push_vol_dried` only).

## Isolation

- States are disjoint from `store.LEDGER_ALERT_STATES` and `alerts.FADE_CROSS_STATES`: a GGD doc is never a
  `ledger.rows_for` row and never in `store.alert_rows` (the 🏁 never reads it).
- Prefix "GGD:" never "GG:": the 🚩 lane (`trading/gajjala_entry.py`) and the stream (`trading/gajjala_stream.py`)
  never read it (a source guard pins neither names the kind nor the prefix).
- A non-GG5 store (GG1 / 🧪 GGA / 🥇) returns zero counts and never imports the sender.

## Runbook (order)

1. HIS CALL #1 (the twin buzz) BEFORE the deploy.
2. `./deploy-cheetah-main.sh api`
3. The owner prefs data write (existing phones get the new kind ON):

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply --apply
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply
```

4. `./deploy-cheetah-main.sh cron frontend`

If step 3 is missed, the rings settle `dried_no_target`: still recorded and graded, shown as "N recorded · M rang".

## HIS CALLs (none decided here)

1. Keep the 💧 push live given it twins the 🧠 "trigger armed" push (82% same pass)? (a) live as built · (b) mode "off"
   (recording only) · (c) live 💧, mute 🧠 · (d) a different "volume dried" event (needs his / GG's number) · (e) give 💧
   the 🧠 tag so it replaces the 🧠 card.
2. A held transition (first 15 minutes, no fresh print, under the floor) never rings later — or defer like the 🧠?
3. The K11 1M floor on every 💧 ring vs the 🧠's holds on 📌 / 🎪 adds only.
4. The tap opens the card on its sub (the 🧠 deep link), not the 👀 Watch.
5. Rings outside RTH (04:00–09:30, 16:00–20:00) — the 🧠 window — vs the A+ window.
6. What "bumped" means: served "triggered" and "hit +1R" beside stop-first; best high and r_max are stored, not served.
7. The count span = `LEDGER_SPAN_SESSIONS_LONG` (10).
8. The owner keep-set becomes TEN.
9. No /alerts pass strip for 💧 (counts in the pass log only).
10. Pre-existing: the card's 💧 chip shows on cards with no pullback yet (vacuous K3).
11. The live-since day (2026-11-25, Thanksgiving week).
12. One ring per name: apply his 11-11 `POTENTIAL_ONE_RING_PER_NAME` to 💧 too?

UNMEASURED — a description, not an entry. Not a recommendation.
