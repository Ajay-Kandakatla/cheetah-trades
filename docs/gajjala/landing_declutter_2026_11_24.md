# 🧹 🚩 Gajjala landing declutter — the board (2026-11-24)

Spec: `ggclean` rev 2 (§3.3 header fold, §3.5 sub folds). Companion docs: `landing_fold_store_2026_11_24.md` (the store
and the ⓘ components), `landing_declutter_panels_2026_11_24.md` (the 🧨 / 🌱 / 🩳 / 📋 state lines),
`landing_declutter_page_2026_11_24.md` (the Chart Maps page rows). **FE only — no served word changed, no backend file.**

## His words (2026-11-24, three messages with screenshots)

1. "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages anymor"
2. "Add all of this too" (the 📲 / 🧠 / ⚡ boxes)
3. "Collapse all of this too" (the 🩳 High SI panel text down to the tally and its ⓘ)

## What is visible by default on 🚩 (owner), top to bottom

page title · 📅 runners · ✨ arrivals · the tab strip → **[🔄 scan now] [🧾 log trade] … [ⓘ]** → (only when served: a
fault line · the answer to HIS 🔄 tap · the ⚠️ over-trade line · ⏳ first 15 min · ⏰ time window) → sub strip → 🎯 A+
line → (only when served: `gg-error` · `gg-awaiting`) → the controls row with its ⓘ → (only when served: the panel state
lines) → 🧠 strip / 🌙 recap / 🌅 rows → cards. The answer to the scan ON OPEN is not on this list.

A non-owner sees the same, minus 🔄 and 🧾: the row holds the ⓘ only.

## The two folds and their keys

| fold | key (`localStorage`) | toggle | what it holds |
|---|---|---|---|
| header | `gg-fold:header` | `gg-head-toggle`, right end of `gg-actions` | segment A `gg-head-body`: the page's WHY / ℹ️ Rules ×2 / 🎯 Enterable rows (through `GgHeadPageContext`), the strip (runners text, 📌 lines, RTH badge, session label, as-of stamp, live footer, feed word), the 🚫 editor · segment B `gg-head-body-b`: 🌫️ Day read, the 🧾 sentence (slot `gg-my-day-slot`, a portal), the answer to the scan on open · segment C `gg-head-body-c`: 📲 / 🧠 / ⚡ push lines |
| sub | `gg-fold:sub:<sub>` | `gg-sub-toggle`, right end of the controls row (📋: beside the table title) | `gg-sub-body`: order note, 🌀 list note, the 🧨 / 🌱 / 🩳 panel, the tally + ⓘ legend + 🪦 lines · on the same key: 🌅 Day-2 note (`gg-sub-body-day2`), 🔝 Focus head (`gg-sub-body-focus`), 📋 order text (`gg-sub-body-table`) |

Both default CLOSED; absent / junk / blocked storage reads closed. The text stays mounted and is hidden with the
`hidden` attribute on a `GgFoldBody` wrapper (never on a classed element). Each sub remembers its own fold — opening
🩳 does not open bull_flag, and opening the header does not unroll any sub. 📓 Playbook and 🏁 Track record draw no
sub toggle and fold nothing. Every ⓘ open is counted (`trackFeature('gg-fold:<key>')`).

## Faults stay outside (built as the spec's HIS CALL #1 default)

| visible while closed | served field | testid |
|---|---|---|
| stale | `pass.stale` + `stale_text` | `gg-stale` |
| warming | `pass.warming` + `warming_text` | `gg-warming` |
| the answer to HIS 🔄 tap (scanning / reused / closed / waiting) | POST `text`, `scan.scanning_text` | `gg-scanning` / `gg-scan-reused` |
| refused (incl. the store error) — from his tap OR the scan on open | POST `text` | `gg-scan-refused` |
| a non-ok POST `detail` — from his tap OR the scan on open | POST `detail` | `gg-scan-err` |
| partial pass | `scan.note` | `gg-scan-note` |
| 🚫 list fault (the strip is folded) | `broker_flags.fault_text` | `gg-head-broker-fault` |
| failed 🚫 write (the strip is folded) | write `detail` | `gg-head-broker-err` |
| board read error | the GET failed | `gg-error` |
| a name missing from the cards | `faults_text`, `chartless[]`, `empty_text` on 🧨 🌱 🩳 | `gg-substate*` |
| ⛔ SSR list could not be read | `high_si.ssr_new.fault_text` | `gg-substate-fault-ssr` |
| already outside, unchanged | `awaiting[]`, `empty_note`, `postmarket.unchecked_text`, 🔒 / ⛔ card-tag faults, 🧨 🏁 fault, 📋 `fault_text` / `si_fault_text` | |

[C4] The 🚫 fault and a failed write print as **two** nodes outside while the header is closed (both can be served at
once); open, the strip shows them in place and the outside nodes go — never twice on screen. The panel state lines
likewise print only while their sub fold is closed.

Built as NOT a fault (inside the fold): the answer to the scan on open when it is started / waiting / reused / closed;
the feed word in every state ("📡 Reconnecting", "Paused", "Live stream down (…)" — the same served field); the ⚡ break
push line; 🌫️ Day read "not read yet"; the SSR partial / faults lines; the Reg SHO tail of the 🩳 order line.

## [C1] The scan on open folds, his tap's answer does not

The mount effect tags its POST (`scanOnOpen` ref, read and cleared at the start of `startScan`, before the await). An
answer whose served state is one of `GG_FOLD_SCAN_ON_OPEN` (`started`, `waiting`, `reused`, `closed` — lib/ggFold) and
that answers the page opening sets `scanFromOpen`; the two answer lines (`gg-scanning`, `gg-scan-reused`) then render
inside segment B. Any tap sets it back to false, so the tap's answer prints outside, visible. `refused`, a non-ok
`detail`, an unknown state and `scan.note` never fold. While the on-open answer is folded, the 🔄 button still pulses
(`data-scanning`) and its title carries the served scanning / closed line. The two lines render in exactly one place
(a tap after an on-open answer moves the line out — a remount of a stateless `<div>`).

## [C3] The sub text now opens UNDER the controls row (his call §7 #13)

| | order above the cards |
|---|---|
| before (and still on 🧪 / 1-min) | 🎯 A+ → order / list notes → `gg-error` → panel → tally → `gg-awaiting` → controls row → 🧠 strip |
| now on 🚩 | 🎯 A+ → `gg-error` → `gg-awaiting` → controls row (… ⓘ) → [fold body: notes → panel → tally] → state lines → 🧠 strip |

Pinned on purpose in `GajjalaBoard.fold_2026_11_24.test.tsx` (test 10 [C3]); the 🧪 / 1-min old order is pinned in
test 8.

## [C6] A closed day: owner and non-owner alike

On a closed market the strip's "last session YYYY-MM-DD" and the "as of {pass time}" stamp fold with the strip, and
the scan-on-open "market closed — no scan on open; last pass …" line folds too. So on a weekend **nothing on the default
view says the board is not today's — for the owner AND the non-owner.** The owner's only trace is the 🔄 tooltip, which
carries the served "market closed — last pass …" (`rescanTitle`, the closed `scan.as_of_text`). A non-owner has no 🔄
and so nothing. Rule #7 (`feedback_check_data_asof_dates.md`) is a source-cadence check, not a display rule; a one-word
marker beside the buttons is HIS CALL (#4 / #5 below).

## 🧾 MyDayLine bare mode

`MyDayLine` gained one optional prop, `textTo`. Undefined (every older caller): today's markup, byte for byte. On 🚩 the
board passes its slot element: the section is `display: contents` (no dashed box) so the 🧾 button is an item of
`.gg-actions`; the sentence block (`my-day-line` → text, quiet, footer) portals into segment B; the ⚠️ `next_text` stays
OUTSIDE the fold right after the button. [C2] The ⚠️ line and the open sheet carry `flex-basis: 100%; order: 1`, so line
one is always 🔄 · 🧾 · ⓘ and they take the lines under it; the ⓘ never jumps when the 🧾 button lands after its GET.
The keyboard order (🧾 → ⚠️ / sheet → ⓘ) differs from the visual order — acceptable for a disclosure toggle. One GET:
the slot arriving is a prop change, never a remount.

## The variants

🧪 Gajjala · Audited and the retired 1-minute page: `headKey` and `subKey` are null — no action row, no ⓘ, `GgFoldBody`
is a bare fragment, the 🔄 button is the strip's last child, the answer lines print where they always did, panels and
tally stay before the controls row. DOM as before (test 8).

## HIS CALL (built as the stated default; none decided for him)

1. Which served lines count as a fault (the table above).
2. ⚠️ `my_day.next_text` stays visible under the buttons — the only warning BEFORE a trade. Hide it with the rest?
3. 🎯 Enterable only: folded, no marker (it hides no 🚩 card). A tiny "🎯 on" marker beside ⓘ?
4. Closed market: nothing on the default view says the board is not today's (owner and non-owner). A one-word marker
   from the served `session.label` / closed `as_of_text`?
5. The as-of stamp folds. Keep a compact as-of beside the buttons?
6. ⛔ SSR (new today) folds with the 🩳 text. Keep its title visible as its own fold?
7. 🔝 Focus header and 🌅 Day-2 note fold. Keep either?
8. 🪦 graveyard lines fold with the tally. Keep them visible?
9. Not changed: 🧪 / 1-min, 🥇 Luk, 👀 Watch, every other Chart Maps tab, the 🎯 A+ line, ⏳ / ⏰, the 🧠 / 🌙 titles,
   the 📋 title, 🏁, 📓, the bottom ℹ️ Rules pill and the UNMEASURED note.
10. Every viewer gets the folds (default closed). Owner only?
11. Delete instead of hide, later, on the `gg-fold:*` open counts.
12. The scan-on-open answer folds. Keep it visible?
13. The sub text opens under the controls row. Open it above instead (costs a row for the ⓘ)?

## Preview measurements (430 px + desktop)

Owed by the main session (spec §5.2) — the executor ran no preview. vitest cannot see a stylesheet (`css: false`), so
the real-browser checks of the `[hidden]` twin, the one-row 430 px layout and the ⓘ staying on line one live there.

## Tests

`frontend/src/components/GajjalaBoard.fold_2026_11_24.test.tsx` (spec board tests 1–16 incl. negatives) and the
dated `WIDENED 2026-11-24 (ggclean)` assertions in the existing board tests (§5.3).
