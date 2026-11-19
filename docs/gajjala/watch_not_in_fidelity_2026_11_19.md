# 👀 Gajjala's Watch × 🚫 not eligible at the broker (2026-11-19, spec watchfid)

## READ THIS FIRST

Ajay 2026-11-19, verbatim: "Add a button to say not in fidelity, AZI and CHSN are not in fidelity don't add them to watch list"

**What is built (the 👀 Watch only):**
1. **The 🤖 auto list never gives a NEW seat** (🧠 potential or 🎯 A+) to a name on his ONE 🚫 list
   (`gajjala.store.broker_flags`, "." == "-"). A flagged potential is never promoted to A+ in place.
2. **A seated 🧠 potential that joins the list leaves at the next minute** (reason `not_eligible`, the served word as its
   line). `gajjala_watch.constants.AUTO_NOT_ELIGIBLE_REMOVES = True`.
3. **A seated 🎯 A+ STAYS until his ×** (his 11-17 call kept): `AUTO_NOT_ELIGIBLE_REMOVES_APLUS = False`.
4. **Every Watch tile has a ONE-WAY 🚫 button, first in its button group** (🚫 ⤢ ↗ ✕). One tap POSTs the name to the
   existing `/chart-maps/gajjala/broker-flags` route, then calls the existing DELETE
   `/chart-maps/gajjala-watch/symbols/{symbol}` (his name leaves his list; a 🤖 name is dismissed for today). It is lit from
   the SERVED row word. There is no unflag on the Watch: the undo is the 🚩 strip ✕ or the 🚩 card toggle.
5. **Every Watch row serves `broker_text`** (one list read per GET), so the chip and the button state are right for
   names that are not carded on today's 🚩 board too.
6. **His own typed adds are NOT blocked.** The add answer carries " · " + the served word.
7. The ℹ️ auto clause, the ℹ️ 🚫 line and the 🤖 hover hint all say the Watch exception, from ONE phrase:
   `gajjala_watch.auto.broker_words()`.

AZI and CHSN were already on his 🚫 list at 10:19 ET (no list write was needed for his two names). CHSN was not on his
Watch list; he had × dismissed it from the 🤖 auto list that session only. The gate is what keeps it out from the next
session on.

**What is NOT built:**
- Every other Gajjala surface (🚩 / 🧪 / 🥇 boards, 🧠 / 🎯 A+ pushes, 🏁, the 1-min cross push on his names) still only
  TAGS these names (Q1 / Q4 of `broker_flags_2026_10_17.md`). Nothing is hidden there.
- 🎯 A+ seats on the Watch are not removed by default (HIS CALL #3).
- No confirm on the 🚫 tap (HIS CALL #8). No on/off toggle on the Watch (HIS CALL #4).
- No rule-based pre-screen from the broker's published restrictions (HIS CALL #9).

Display / selection only. UNMEASURED. Not advice.

## Served keys (owner GET only)

A non-owner gets exactly `owner_only`; nothing is read for them, and no `broker` key or 🚫 is in the body.

| key | type | source |
|-----|------|--------|
| `rows[i].broker_text` | str \| null | `tab.broker_text_for(sym, flags)`; null when the name is not on the list or the list could not be read (never the seed guess) |
| `broker` | object \| null | `gajjala_watch/broker.py` `board_block`; null only when the broker module itself fails |
| `broker.toggle` | str | `tab.BROKER_FLAG_ICON` |
| `broker.text` | str | `tab.BROKER_FLAG_TEXT` |
| `broker.title` | str | `broker.MARK_TITLE_TEXT` over `tab.BROKER_FLAG_TEXT` |
| `broker.editable` | bool | False on a list-read fault (the FE then shows no button) |
| `broker.fault_text` | str \| null | "🚫 " + `tab.BROKER_FAULT_TEXT`, only on a fault |
| `broker.auto_text` | str \| null | the loop state doc of THIS session, `auto.not_eligible` names ("🚫 not seated by 🤖 auto — on your list: AZI, CHSN") |
| `broker.auto_fault_text` | str \| null | the loop state doc of THIS session, `auto.broker_fault` True |
| `auto.hint` | str (existing key) | gains `broker_words()` as one sentence before its final "UNMEASURED."; the auto block's key set is unchanged |

The add answer (`POST /chart-maps/gajjala-watch/symbols/{symbol}`) keeps its keys; for a listed name in state
`added` / `replaced` / `already` its `text` gains " · " + `tab.BROKER_FLAG_TEXT`.

Code: `backend/chart_maps/gajjala_watch/broker.py` (new; the code types neither the broker's name nor the word),
`payload.py` (`BROKER_MODULE`, `_broker_section`, one call before the pending check), `api.py` (`_broker_note`).
The engine: `gajjala_watch/auto.py` (`broker_gate`, `broker_words`, reasons / skipped key `not_eligible`, state keys
`not_eligible` / `broker_fault`), `gajjala_watch/constants.py`, `gajjala_watch/loop.py`, `supply_demand/rules_info.py`.
FE: `lib/ggwBroker.ts`, `components/GgwBrokerMark.tsx`, `GajjalaWatchTile.tsx` (`actions` prop), `GajjalaWatchBoard.tsx`,
`GajjalaWatchTags.tsx`, `styles/gajjalaWatch.css` (scoped `.ggw-broker-mark`).

## HIS CALL

1. His OWN adds (typed box, 🚩 card ➕, POST symbols/{symbol}) of a 🚫 name are NOT blocked; the answer carries the word.
   At his cap of 18 such an add REPLACES his oldest non-A+ name (`gajjala_watch/store.py`). Options: block every add of a
   🚫 name, or block only the replace at the cap.
2. A seated 🧠 potential that joins his 🚫 list leaves at the next minute (`AUTO_NOT_ELIGIBLE_REMOVES = True`). False =
   only new seats are refused. Confirm.
3. A seated 🎯 A+ that joins his 🚫 list STAYS until his × (`AUTO_NOT_ELIGIBLE_REMOVES_APLUS = False`). True = it leaves
   at the next minute too. Flip only on his word.
4. The Watch 🚫 is ONE-WAY (mark + take off). Un-marking stays on the 🚩 strip ✕ / card toggle. An on/off toggle on the
   Watch = his call.
5. Every other Gajjala surface still TAGS only (Q1 / Q4). Hiding there too = his call.
6. A list-read fault seats as before (fail OPEN), except that a name removed today for 🚫 stays out (at most one seat
   per name per day), and the board says so. Freezing ALL 🤖 adds on a fault minute (fail closed) = his call.
7. The ℹ️ Rules 🚫 line now carries " On 👀 Gajjala's Watch, by your word, a name on your 🚫 list never takes a 🤖 auto
   seat, …". The exact words are his call.
8. No confirm on the Watch 🚫 (the 🚩 card toggle has none either). It sits first in the button group, away from ✕. A
   confirm or a two-tap arm = his call.
9. A rule-based pre-screen from the broker's published restrictions (Q2) is still not built.
10. Muting the 🎯 A+ / 🧠 pushes of a 🚫 name (Q4) stays NO.

## Verification

- Backend: `backend/tests/test_gajjala_watch_not_eligible_served_2026_11_19.py` (served words, one read per GET, fold,
  fault never the seed, board block keys, auto lines of this session only, hint sentence once, add note, non-owner,
  stealth 404 on the broker routes, strict JSON, a raising broker module, source guards) and
  `backend/tests/test_gajjala_watch_not_eligible_auto_2026_11_19.py` (the gate). Pin moved:
  `test_gajjala_watch_aplus_2026_11_17.py` row key set + `broker_text`.
- His surface after deploy (api + frontend + cron; the minute loop runs in the cron container): the state doc
  `gajjala_watch_state.latest.auto` carries `not_eligible` + `broker_fault`; the 🧠 seats ∩ his 🚫 list is empty; one
  owner GET shows `broker_text` on every row, `broker.editable` true, and the hint sentence once. Never click the live 🚫
  (it writes his list; that is his tap).
