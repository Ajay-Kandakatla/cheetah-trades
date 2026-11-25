# 🔕 Clean Gajjala alerts — the 9 × 21 EMA cross pushes are off (2026-11-24)

## His words (verbatim)
- 2026-11-24 ~22:15 ET: "ok remove EMA entry alerts and divergence alerts. Keep Gajjals clean entries when we find new
  potentials with all the rules getting satisfied.." then "and then A+ entries..".
- Earlier that night: "Instead of EMA cross over I need to look at volume dry out to enter.. Those should be my entries".
- ~22:20 ET: "Honestly The potenail alerts are not bad.." · "BENF and LVWR very good potential entries" · "ONFO too I think'".

## What changed
Three existing mode constants flipped from `"live"` to their existing fail-closed word `"off"`. Each mode line carries
his words and the date in its comment; `"live"` again is one word.

| push | constant | was | now |
|---|---|---|---|
| ➖ Horizontal Fade 🔀 9 / 21 cross | `chart_maps/gajjala/constants.py` `FADE_CROSS_PUSH_MODE` | live (2026-11-15) | off |
| 👀 Watch 🔀 1-min 9 / 21 cross | `chart_maps/gajjala_watch/constants.py` `PUSH_MODE` | live (2026-11-15) | off |
| 🩳 High SI 🔀 5- / 15-min 9 / 21 cross | `chart_maps/gajjala/constants.py` `HIGH_SI_CROSS_PUSH_MODE` | live (2026-11-23) | off |

New constants (gajjala/constants.py, above `FADE_CROSS_PUSH_MODES`): `CLEAN_ALERTS_CALL = "24 Nov"`,
`CLEAN_ALERTS_WORDS` (his first two sentences, verbatim), `CLEAN_ALERTS_SHORT` (derived: the first sentence, never
retyped). No gate reads them; they only fill the 🔕 sentences. No ISO date is served from the backend — the switch
date lives only in the frontend's `alertKinds.GAJJALA_CROSS_PUSH_OFF_SINCE`.

**Still ringing (unchanged):** 🎯 A+ (`gajjala_setup`, `GAJJALA_PUSH_MODE` live), 🧠 potential (`gajjala_potential`
from potential.py — untouched), 💧 volume dried (`gajjala_vol_dried`, `VOL_DRIED_PUSH_MODE` live).
**Already silent (no change):** ⚡ break (shadow), 🤖 auto-added names (`AUTO_PUSH_MODE` off), the retired 1-minute
page, 🧪 Audited. Divergence (🧨 / 🌱) never rang — it is display and record only.

## What "off" does
Each engine counts the cross as `off` and `continue`s BEFORE the claim and BEFORE the send: no `GGX:` / `GGW:` / `GGS:`
doc, no sender call. Every cross is still drawn on the cards, the 👀 tiles and the 🩳 cards; boards, sorts, seating
and the keep-set are unchanged. A junk mode value fails closed to `off`.

**The fade note.** The ➖ Fade 🔀 push had no shadow state; with it off the ➖ cards keep marking every cross over /
under, nothing rings, and the 🧠 potential for the same ➖ name still rings on its own rules.

## The 🔕 sentences (built at call time from the constants)
- ℹ️ Fade clause (`alerts.fade_cross_rules_line`): "No cross rings your phone — off since your call of 24 Nov
  (“ok remove EMA entry alerts and divergence alerts”)."
- ℹ️ 👀 Watch clause (`cross_alerts.rules_line`) — the ONE backend place his full words are served.
- 🩳 card push line (`high_si.PUSH_OFF_TEXT` via `push_text`): the switched-off sentence + "Off since your call of 24 Nov
  (“…first sentence…”)".
- 👀 tile chip for an auto-added name (`payload.held_text("suppressed_auto")`): reads the "off" words while the watch
  push is off — "(your names do)" would be false. Display only; loop.py / auto.py still hold it as `suppressed_auto`.

## The three names he praised — first ring of 2026-11-24 (push_history, ET)
| name | 🔀 👀 Watch cross | 🧠 potential | 🎯 A+ | 🧠 lag after 🔀 |
|---|---|---|---|---|
| BENF | 10:06 | 10:56 | 12:11 | 50 min |
| ONFO | 10:18 | 13:26 | 13:31 | 3 h 08 min |
| LVWR | — | 14:26 | 14:36 | — |

For BENF and ONFO the first ring was the 🔀 Watch cross, which rode the `gajjala_potential` kind (so it showed under
the 🧠 chip on /alerts). With it off, all three names still ring 🧠 and 🎯 the same day — later. **HIS CALL #1:** want
the 👀 Watch cross back? One word, one constant (`gajjala_watch/constants.py` `PUSH_MODE`).

## 🏁 track record
Untouched. 🏁 rows come only from "GG:" / "SHADOW:" A+ claims and 🧠 tracker docs; the cross claims were never ledger
input and are no longer written. Proved by a chained test that runs all three muted engines into the ledger's own
store and re-reads `ledger.rows_for` (same row ids), with a live-mode bite that shows the same chain writing the cross
docs.

## Tests
- `backend/tests/test_gajjala_clean_alerts_2026_11_24.py` — modes + his words in each mode line; keep pins (A+ / 💧
  live, 🧠 kind, ⚡ shadow, 🤖 off, 1-min retired, the TEN keep-set kinds); 🧠 / 🎯 / 💧 still send once; NEGATIVES: the
  three muted senders never called, junk modes ("LIVE", None, 1, "shadow") fail closed; reversibility (each "live"
  rings once); the chained 🏁 test + bite; the words (no "rings once", no ISO date, full quote once); the two ℹ️
  clauses.
- Re-pinned with an explicit `"live"` monkeypatch (tests that prove the live path, never weakened): the 👀 cross,
  ➖ fade cross, REST re-read, fixes, loop, frames golden and 1-min-retired HARD KEEP files; the default literal pins
  (watch runners, fade constants) now read `MODES[0]`; the cross_alerts code-digest pin now strips `rules_line` (digest
  computed on 5dec3c6b — the engine is otherwise main's code); the 🩳 off-text pin carries the call / short words.

UNMEASURED — a mute, not a signal. Not advice.
