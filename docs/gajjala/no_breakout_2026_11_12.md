# ⏸ "No breakout" line on Gajjala's cards, 🧠 potentials and 📈 Track rows (2026-11-12)

## The ask (verbatim)

Ajay 2026-11-12 ~14:45 ET: "Most of our potentials are not having breakout, please write that on them that.. I need for an additonal break out from the triggers Usually after that run up to tirgger point they are mostly just sitting there"

GG's words behind it: C3 "The volume will dry up during the entries of all my setups and it picks up if the setup works." (read off `verified_rules.json`, never typed); X5 CGC "breakout on good volume"; E3 "a breakout back into its range = out" — an exit word, **not printed** (his 2026-11-06 call "keep it"). GG gives **no number** for "good volume" on the break.

**Display only — no alert, A+, rule, order or grade reads it. UNMEASURED.**

## What it is

One served module, `backend/chart_maps/gajjala/breakout_state.py`, computed at **serve time** from the read on the card and the stored tile bars of the **read's own frame** (never the drawn frame, never the 🎾 wide frame), cut at the read's `as_of_bar_t`. Attached by ONE post-walk call in `tab.build`, right after the 🧭 stages walk:

```python
from chart_maps.gajjala import breakout_state as BS
_soft("breakout lines", BS.tag, out, reads_by, v=v, pots=pot_docs)
```

A raise serves the board without the key (every block computed first, then all assigned). It never reorders, drops or gates a card or a row. Nothing in the pass (run, run_1m, alerts, potential, break_watch, ledger, detectors, stages, audited_*, live_*) imports it — the GG5 WRITES golden is byte-identical.

Payload: `tile.gajjala.breakout` and `track.today.rows[i].breakout` = `{state, head, detail, text, hint}` (strings only); absent when there is no line.

## Definitions (structural, no threshold — Cheetah default, not his)

- **Trigger bar** = the read's own break bar (`entry_bar_t`, only when `broke is True`) — the detector's strict `high > trigger` (one engine).
- **Breakout** = a later closed bar closing above the highest high from the trigger bar through the bar before it.
- **Volume louder** = that bar's volume, rounded as the K3 row prints it, above the busiest base bar parsed off the card's own K3 row (`detectors.K3_VOL_KEY`) — no ratio.
- **Traded under the stop** = the first bar from the trigger bar on (the trigger bar counts) whose low is under the read's stop — the engine's strict `<` (`detectors.stopped_after`); nothing at or after it is read as a breakout.
- **Back under** = the latest closed bar closed under the trigger (a close equal to the trigger is not under).
- **The latest closed bar decides**: 🔊/🔇/⤴️ only when it is itself the breakout; otherwise ⏸ "no new breakout since the HH:MM bar" with the earlier breakout's volume word in the detail.
- **No breakout yet** (🧠) = a potential read (forming with a base): by construction no bar traded over its trigger.

## Precedence (broke reads)

1. Trigger bar = the latest bar (a fresh A+ / break) → **no line** (the pill already says "A+ on the HH:MM bar").
2. A bar traded under the stop → ✖️ `traded under the stop {S} on the {HH:MM} bar` (an earlier breakout named).
3. Last close under the trigger → ↩️ `back under the trigger {T} since the {HH:MM} bar`.
4. The latest bar is a breakout → 🔊 louder / 🔇 not louder / ⤴️ volume not judged (base volume not on file).
5. Else ⏸ `no breakout since the trigger` / `no new breakout since the {HH:MM} bar` + "needs a close above {level}".

Every detail prints `last close X (±y% vs the trigger T)` (percent = `potential._pct_move`, the tracker's own engine) and the minutes since the trigger bar.

Off the chart (1-minute page, trigger bar older than the 192 served bars): `⏸ trigger bar HH:MM is off the chart — breakout not read`.

## Who gets a line

- **Cards**: broke reads (`broke is True`) in `aplus` / `triggered` / `partial` / 🧪 `aplus_held` — never `stopped` / `invalid` / `none` (the stopped pill already says "then traded under {S}"). A `partial` whose stop traded later says ✖️ (the engine only runs `stopped_after` on the all-pass path — the asymmetry is the engine's).
- **🧠 potential cards** (forming, `potential_kind` not None): `⏸ no breakout yet · last close … · N min since first seen (HH:MM bar)` — minutes from the tracker's `first_bar_t` to the latest closed bar, same date only.
- **📈 Track rows — TODAY only** (the board session's reads; never "yesterday"): the card's block; a read that never broke and is not `stopped` → `⏸ no breakout over {T}` (`⏸ no breakout` when no trigger). The row word describes the current read only — never "never broke" (the tracker path carries no `broke`).

## Surfaces, phone order

Same walk ⇒ 🚩 5-minute page, 🚩 1-minute page, 🧪 Audited page. Luk untouched.

Phone (430 px, one column, `.gg-line` wraps): chart → pills → plan → **⏸/🔊/🔇/⤴️/↩️/✖️ line** → 🎾 SI → 🔴 live → criteria → chips → ☀️/🌙 lines → 🧠 words → 🧭 stages. 📈 row: … → ⚡ word → **⏸ word** → timeline.

## Today on his surface — ONE session, descriptive, NOT a rate

~15:00 ET 2026-11-12, 42 broke cards (41 `partial`, 1 `triggered`), planner replica of this rule: **27 ✖️ traded under the stop · 10 ⏸ (8 after an earlier breakout) · 4 ↩️ · 1 🔊 on the latest bar.** Never quote as a rate before the study's placebo row is in.

## Study numbers

Pending — main session appends.

## HIS CALL (not decided here)

1. Which surface did you mean — the 🧠 cards before the trigger, the cards after it, or both? Built: both, plus today's 📈 Track rows. Every 🧠 card's ⏸ line is the same word (only the numbers differ) — strike it if it is clutter.
2. "Trigger bar" = the detector's own break (high STRICTLY above the trigger), not "high ≥ trigger".
3. "Volume louder" = above the busiest bar of the quiet base (K3 row), no multiple — MINE. On a read that passed K3 that bar is ≤ half the run's mean by construction, so most ordinary bars clear it. A multiple (BF4 "twice, thrice") or vs the run-up bars instead?
4. The latest closed bar decides the line — MINE.
5. Stopped cards get no line — MINE. A `partial` whose stop traded says "✖️ traded under the stop" (a fact, no exit word) — MINE.
6. "Broke — not A+" (partial) cards DO get the line — MINE (41 of today's 42 broke cards are partial).
7. ↩️ / ✖️ print the fact only; GG E3 "back into its range = out" would be an exit word — not printed.
8. 1-minute page: a trigger older than the 192 served bars says "off the chart — breakout not read" — MINE.
9. Any push / alert on 🔊, ↩️ or ✖️ (a new keep-set kind) — NOT built.
10. The ⤴️ state (breakout, base volume unknown) — MINE.
11. A fresh break (trigger bar = latest bar) gets no line — MINE.
12. A "N of M broke out" count in the 📈 Track title — NOT built (a rate before the study).

## Tests

`backend/tests/test_gajjala_breakout_state_2026_11_12.py` (73 cases): exact words per state, the far-above / fresh-break / stale-breakout / stop-printed (with `stopped_after` parity) / off-chart / NaN negatives, eligibility, 🧠 minutes, today-only rows, the read's frame, the K3 round trip, build integration on the real pass (GG5 / GG1 / 🧪), a raising engine, order unchanged, engine isolation, the 0/1 literal guard, the wording guard and the GG5 WRITES golden unchanged.

Goldens that move (only `gajjala.breakout` on tiles and `breakout` on today's 📈 rows added): GG5 board, GG1 board, 🧠 potential, on_open; the 🎾 squeeze guard passes again once the potential golden is regenerated. Four more tests read the same GG5 board golden and go red with it, and green again once it is regenerated (re-run them after the regen): `test_gajjala_audited_pass.py::test_gg5_writes_and_board_stay_byte_identical_with_the_overlay_active`, `::test_identity_world_every_aplus_is_held_by_t4_and_the_goldens_stand`, `test_gajjala_audited_tab.py::test_gg5_and_gg1_serve_no_audit_key_and_the_gg5_board_golden_holds`, `test_gajjala_audited_k3s_track_2026_11_09.py::test_NEGATIVE_the_gg5_board_golden_holds`. Checked 2026-11-12: with every `breakout` key (20 on the GG5 board) stripped, the served board equals the golden exactly.
