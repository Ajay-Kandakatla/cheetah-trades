# 📊 Highest volume on top + 🚫 his names at the bottom — every Gajjala card board (2026-11-09)

**Display order only.** No gate, rule, threshold, push, count or data change. Nothing is hidden. UNMEASURED, as every
Gajjala read is.

## His words

- Ajay 2026-11-09 ~10:25 ET: *"Ok sort any stocks by volume on all Gajjala's charts"*
- Ajay 2026-11-09 ~10:30 ET, with a 🚫-chipped 🎾 card: *"The ones I am reporting they are not on Fidelity put them at
  the bottom"*
- Earlier, still binding as the NEXT keys: 2026-10-18 *"for the float lower the better is what I wanna follow so sort it
  by lowest on top"* (`GC.RS_FLOAT_SORT`, every sub since the morning of 2026-11-09 —
  `docs/gajjala/float_sort_all_setups_2026_11_09.md`); 2026-11-07 the ➖ 9/21 EMA-gap rank (`GC.HF_EMA_SORT`).
- GG on volume: S8 1:21:56 *"I sort by volume"* (his ToS scan), S8 1:32:02 *"the more the better"* (the 1M floor).

## 1. The volume key

`constants.VOLUME_SORT_SETUPS = FLOAT_SORT_SETUPS` (= every setup sub: 🚩 💋 ➖ 🌀 🎾). `tab.setup_tile` stashes
`_volume` = **the card's own Volume number** (`chips.volume` ← the scanner row the pass stored — the same figure the
card's "Volume" stat prints; no new read). `tab.order_key` builds the sort slot

```
sk = (volume DESCENDING, unknown last) + (float ASCENDING, unknown last)
```

and places it by `GC.RS_FLOAT_SORT` ("within_state" built: right after the state rank; "global": above it). ➖ keeps its
gap first and takes the slot right after it. Today's key (newest A+ first, nearest trigger, bars to go, fewest misses,
change, symbol) still breaks ties.

| Sub | Order inside a state (A+ › triggered › forming › partial › stopped) |
|---|---|
| 🚩 Bull Flag, 💋 Kiss & Fly, 🌀 Intraday VCP, 🎾 Reversal Squeeze | **volume ↓**, float ↑, today's key |
| ➖ Horizontal Fade — pre-break (forming / partial) | EMA gap ↑, **volume ↓**, float ↑, today's key |
| ➖ Horizontal Fade — A+ / triggered / stopped | state rank, **volume ↓**, float ↑, today's key |
| 🧠 Potential (`potential.order_key`) | trigger armed › building, **volume ↓**, float ↑, SETUPS order, symbol |
| ☀️ Premarket | unchanged — his ToS sort (volume, % change toggle) |
| 🌙 Post-market | unchanged — after-hours gain |

Served words (the FE prints them, types none): `order_note` on every setup sub — `VOL_ORDER_TEXT`
"📊 highest volume on top · then lowest float" (🚩 💋 🌀), `RS_ORDER_TEXT` "🎾 highest volume on top · then lowest
float", `HF_ORDER_TEXT` "➖ 9 and 21 EMA closest to merged on top · then highest volume" — and on the 🧠 sub
`POT_ORDER_TEXT` "🧠 trigger armed first · then highest volume". ☀️ / 🌙 / 📓 serve none (☀️ has its sort toggle).
Amended 2026-11-11: 💋 no longer serves `VOL_ORDER_TEXT` — its slot is relative volume ↓, then the 9 EMA distance ↑,
AHEAD of (volume ↓, float ↑), and its `order_note` is `KF_ORDER_TEXT` (`docs/gajjala/kiss_rvol_sort_2026_11_11.md`).

The 🧪 Audited and 1-minute pages share `tab.order_key` / `setup_tile` and follow with no special case (tested).

## 2. His 🚫 names at the bottom

`tab.broker_bottom(rows, flags)` — a **stable partition**: the rows whose symbol is on his list (`store.broker_flags`,
"." / "-" folded like the tag) move to the END in the same relative order; everything else keeps the board's own order.
It runs on every card board AFTER its own order and AFTER the limit cut — the cards shown are the same set as without
the list; only their order moves (critic 2026-11-09: a partition BEFORE the cut would have DROPPED his names past 24
cards, and the 🎾 board passed 24 on 4 of the last 6 sessions): the five setup subs, 🧠, ☀️, 🌙 — and the 🧠 strip rows
under each setup sub (never cut by limit). The 🏁 Track record is a ledger of what rang — never reordered, only tagged.
The ℹ️ Rules panel's 🚫 line says so, built from `tab.BROKER_BOTTOM_TEXT`.

The ORDER is the same for every viewer: `build` now reads his list for everyone (`order_flags`); the WORDS stay
owner-only (`flags = order_flags if owner is True else None`), so the 2026-10-17 invariant still holds — the owner payload
minus `broker_text` / `broker_flags` / `graveyard_broker_text` equals the non-owner payload byte for byte. A list read
fault falls back to the seed (empty) → nothing moves, the strip says so.

Served word for the owner strip: `broker_flags.order_text` = `BROKER_BOTTOM_TEXT` "your 🚫 names sit at the bottom of
every card board" (FE `GajjalaBoard.tsx` prints it under the strip's text, `data-testid="gg-broker-order"`). The
ordering words (`order_note`) print BELOW the 🎯 A+ banner, so the A+ line stays right under the sub strip.

What did NOT change: the tag itself, the pushes (they still ring and carry the tag), `alerts.COUNT_KEYS`, the counts, the
graveyard line, the editor routes, `BROKER_FLAG_SEED` (empty).

## Goldens moved by design (verified key for key)

- `frontend/src/components/__fixtures__/gajjala_potential_golden_2026_10_15.json`, `gajjala_on_open_golden_2026_10_15.json`,
  `gajjala_1m_board_2026_10_27.json`, `gajjala_track_record_golden_2026_10_16.json`: only `broker_flags.order_text` (owner
  boards) and `order_note` (bull_flag → `VOL_ORDER_TEXT`; 🧠 → `POT_ORDER_TEXT`). No tile moved.
- `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json` (the GG5 identity BOARD golden): 20 `order_text` adds + 12
  `order_note` words, nothing else; the WRITES golden is byte-identical. Dated in the test's docstring.

Recipes: `GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_potential_tab.py tests/test_gajjala_on_open.py
tests/test_gajjala_1m_page_2026_10_27.py tests/test_gajjala_track_record_tab.py -k golden` and
`GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_variant_gg5_identity.py`.

## Tests

`backend/tests/test_gajjala_volume_sort_2026_11_09.py` (the slot, the stash = the card's number, ➖ gap first, 🧠 swap,
every variant, the partition on every card board incl. ☀️ / 🌙 / 🧠 and the 🧠 strip rows, the cut-first rule (never a
card dropped), the invariant, the words; NEGATIVES:
no stash → the float-only key byte-identical, a setup outside the tuple, a lower state never rising on volume, no `_`
key served, a non-owner gets the same order and null words, an empty / faulting list moves nothing, the 🏁 never
partitions, no banned word). Re-pinned: `test_gajjala_tab.py` (order_note on every card sub), `test_gajjala_potential.py`
(the swap), `test_gajjala_fade_ema_rank_2026_11_08.py` (the ➖ word), `test_gajjala_broker_flags.py` (the flagged name last
for every reader; the two ℹ️ Rules-panel pins now find the 🚫 line by prefix — they read the LAST stop line, which the 🔴
live line took on 2026-10-16: a pre-existing red on main, fixed here). FE: `GajjalaBoard.broker.test.tsx` (the served
order_text line + NEGATIVE), `GajjalaBoard.order_note.test.tsx` (clone word). Contracts block "📊 volume on top + 🚫 at the
bottom (2026-11-09)"; the "🚩 float order on every Gajjala sub (2026-11-09)" block follows the new slot.

## HIS CALL (not decided here)

1. ➖ Fade: the EMA-gap rank stays FIRST there (his 2026-11-07 word), volume next. Say the word and volume goes first on
   ➖ too.
2. 🌙 Post-market stays on after-hours gain; ☀️ already sorts by volume (his ToS sort). Volume on 🌙 = his word.
3. The bottom partition applies to every viewer's board (one order for the household); an owner-only order would break
   the "same rows for every reader" rule. Flip = his word.
