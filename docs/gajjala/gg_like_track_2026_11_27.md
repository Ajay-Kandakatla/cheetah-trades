# 🧘 GG-like — tracking the rings (2026-11-27, WP `be-track`)

Ajay 2026-11-27 ~00:15 ET: "Continue to track the runners we might evolve and find patterns in the current runners too but
I want to make sure we are finding similar setups to Gajjala". Spec: `scratchpad/gglike/spec.md` rev 2 §3.6–§3.7.

**UNMEASURED accounting — not a test.** The 🧘 check is observed on GG's example charts, not his rule (`gg_like.py`,
`docs/gajjala/gg_like_2026_11_27.md`). Nothing here gates, rings, sorts or hides anything.

## What is recorded, and where

| piece | file | what |
|---|---|---|
| ring stamp → 🏁 row | `ledger.py` `_gg_like_stamp` (in `alert_of`, beside the 📶 stamp) | `push.gg_like` (🧠) / `gg_like` (A+ claim) → `row["gg_like"]`, only when `gg_like.from_stamp` accepts it. A ⏪ replay row never. No stamp → the row is byte-equal to before. |
| 🏁 row chip + fold | `ledger.py` `_gg_like_post` (GG5 `served_block` only) | `days[].rows[].gg_like` = `gg_like.row_chip(block, source)`; block key `gg_like_split` = `gg_like_track.split_block(facts)`, `None` on a fault. Computed first, assigned after — a fault leaves every row as before. GG1 / 🧪 blocks get no key. |
| ledger note | `store.py` `LEDGER_NOTE_KEYS` = {`gg_like`, `win30`}, `annotate_ledger` | ONE `update_one({_id}, {$set})`, **never an upsert**: "matched" / "unmatched" (no doc created) / "refused" (a key outside the note keys) / "error". `LEDGER_KEYS` and `upsert_ledger` are unchanged. |
| nightly record | `gg_like_track.record_night` (one fence in `nightly.py` between 🩳 and 📅) | see below |
| 📅 rings | `runseat.aplus_rings` (passthrough `gg_like`) → `runtrack._aplus_of` | every item of an OPEN record doc gains `gg_like` (verdict or None), `gg_like_source` ("ring" / "computed_later" / None), `win30` (True / False / None — None unless the source is "ring"). Closed docs are never rewritten. |
| 📅 line | `runtrack.payload()` → `gg_like_text` | ONE counts line over every doc's rings, de-duplicated by ring id; no R, no rate; None with no ring. |

## Two sources, never mixed [C2]

- **"ring"** — the block frozen on the claim / push WHEN IT RANG. Only these enter the +30% counts and the R sums.
- **"computed later"** — for an older A+ ring with no stamp, the ONE-TIME record run (not the nightly — the nightly passes later=False; see the refix note below) re-judges its stored end-of-day read, but only
  when that read still describes the claim (broke, same entry bar, frame, trigger, stop). A name that kept moving had its
  read overwritten (32 of 51 A+ rings of the 11-27 window, the runners among them), so the rings left are the ones that
  did NOT move on — a biased sample. They get a chip on the row and ONE counts-only line; no result is ever printed for
  them and `win30` is never measured for them.

## The 🏁 fold `gg_like_split` [C6]

Lines per kind (🎯 A+, then 🧠 armed) × setup (GC.SETUPS order) × group (GG-like / not / can't tell), ring-stamped and
counted (de-duplicated) rings only: rings · "w of m ran +30% from the trigger" (A+ only; m = measured days) · fills, wins
(+1R), stops, open · the R sum before AND after costs · the median stop width. Then "No check on file: a A+ · b 🧠", then
the "computed later" counts line. **No mean, no rate, no rank, no line that adds two setups together** — the stop width
differs by setup and costs in R (cost% ÷ stop%) grow as the stop tightens. A cell with no ring prints nothing; with no
ring stamp at all the fold prints "No ring carries a frozen check yet …".

R = GG's trade math on the same-session column: fill → the target (win), the stop (loss) or the close (open), ÷ R. After
costs = `divergence.net_pct` (the ONE in-app cost function; `DIVERGENCE_COST_BPS` 0.10% + `DIVERGENCE_SLIP_USD` $0.01 a
share per side). None without a final fill (no entry, split, provisional, thin R, no plan / no risk).

**2026-11-27 refix — the 1m/5m 🏁 parity pin.** `tests/test_gajjala_track_parity_2026_11_05.py` allows no block-key
difference between the 1-minute and the 5-minute 🏁 (Ajay 2026-11-05: both track records "similar"). So a GG1 block
serves `gg_like_split: None` — never a split, never read, the tracker is never called — and its rows carry no `gg_like`.
The 🧪 audited block still carries no new key. Side effect: the 1-minute golden
`frontend/src/components/__fixtures__/gajjala_1m_board_2026_10_27.json` gains that one `null` leaf (main-session regen).
Latent and NOT fixed here: the parity pin's `COND_ROW_KEYS` does not list `gg_like`, so a ring-stamped GG5 row would
break its "row keys" check if a fixture ever carried one (none does today) — his call whether to list it.

## `record_night` (the 20:15 nightly, GG5)

Window = the ledger's own (`history_window(next_market_day(today), LEDGER_GRADE_LOOKBACK_SESSIONS)`), or `--sessions N`.
Per A+ row (live / shadow):
0. no graded ledger doc → `no_ledger_doc`, nothing read or written (the grade files it first — DKI / TOPP of 11-25 rang
   after the close and have none yet) [C8];
1. ONLY with `later=True` (see below): no ring stamp and no note → the stored read; a match → `gg_like` with
   `source: "computed_later"`, `computed_at`;
2. a RING-STAMPED row with no `win30` dict, once its play day ended (`runseat.measure_end` + settle): the split guard as
   `runseat._judge` runs it (a day fetched on or before the ring date needs no look; an unanswered look is retried; a
   split is FINAL `{"measured": False, "why": "split"}`), the ledger's loader (capped by `LEDGER_BACKFILL_MAX_SYMBOL_DAYS`,
   a failure retried), `runseat.from_trigger` → `win30` = its `FROM_TRIGGER_KEYS` + `min_pct` (= `RUNNERS_SEAT_APLUS_PCT`)
   + `at`. Any stored `win30` dict is final;
3. one `annotate_ledger` per row with something to write.
🧠 rows: nothing is written (the +30% rule names the A+ trigger — HIS CALL #9). A second run the same night writes 0 and
loads 0. Counts: `rows, no_ledger_doc, later, later_no_match, win30, win30_split, split_unchecked, not_due, load_failed,
deferred_cap, written, write_failed, read_fault, dry, later_on, loads`.

**2026-11-27 refix — the "computed later" pass is a switch, OFF every night (HIS CALL #11).** The nightly fence calls
`record_night(now, later=False)`, so the 20:15 run measures `win30` on ring-stamped rows only and never reads a stored
read or writes a "computed later" block. That block is written only by the one-time run `--once --later` (`later` must be
a literal `True`), on his go. With no go the 🏁 record starts clean with the ring stamps — the "skip it" option now exists
in code. Pinned by `test_NEGATIVE_the_nightly_never_passes_the_computed_later_switch`,
`test_NEGATIVE_the_nightly_default_never_writes_a_computed_later_block`,
`test_NEGATIVE_only_a_literal_true_turns_the_computed_later_pass_on`.

Dry look (writes nothing):

```bash
docker exec -w /app cheetah-market-app-api-1 python -m chart_maps.gajjala.gg_like_track --once --later --dry-run
```

The one-time "computed later" write (after the deploy, ONLY on his go — HIS CALL #11):

```bash
docker exec -w /app cheetah-market-app-api-1 python -m chart_maps.gajjala.gg_like_track --once --later
```

Tests: `backend/tests/test_gajjala_gg_like_track_2026_11_27.py`.

**2026-11-27 — refix, open pin (HIS CALL).** `gg_like_track.py` names the Watch package (inside functions only):
`gajjala_watch.constants.RUNNERS_SEAT_APLUS_PCT` and `gajjala_watch.runseat` (`from_trigger`, `FROM_TRIGGER_KEYS`,
`split_look`, `_default_cached_at`, `play_day`, `measure_end`, `fetched_on`) — the one +30% engine and its split guard.
That keeps `tests/test_gajjala_watch_hook_2026_11_15.py::test_only_gajjala_run_py_names_the_watch` red: its list says
"nothing else may join (owner's note)". It is NOT widened here. If he says yes, the widening is one entry
(`"gg_like_track.py"`) plus a dated comment; the surface is already fixed by
`test_NEGATIVE_gg_like_track_names_the_watch_only_for_the_pct_cut_and_the_runseat_engine` and
`test_NEGATIVE_the_watch_imports_of_gg_like_track_stay_inside_functions`. The runtrack ring-item pin
(`test_gajjala_watch_runtrack_2026_11_26.py`) gains the three keys of step 6 as None.
