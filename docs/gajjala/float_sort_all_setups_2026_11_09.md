# 🎾 float key on every Gajjala setup sub — 2026-11-09

**Display order only.** No gate, rule, threshold, push or data change. No probability is claimed — there is none.

## His words

- Ajay 2026-11-09 ~09:35 ET: "Are the reversal squeeze tickers sorted by high probability can you update other tabs in the same way I like how they are realtime updating the prices of now"
- then: "When I say all tabs with in Gajjalas only"
- Binding earlier calls: Ajay 2026-10-18 "for the float lower the better is what I wanna follow so sort it by lowest on top" (DECISIONS13 D3, `GC.RS_FLOAT_SORT`); Ajay 2026-11-07 "I need a ranking in horizontal fade when the stock 9 EMA and 21 EMA are converging or close to converge on all tabs" (`GC.HF_EMA_SORT`).
- Context only (descriptive, never a gate or a probability): the 2026-11-09 big-movers study found float ≤ 10M at listing the one separator of big squeezes.

## What changed

`constants.FLOAT_SORT_SETUPS = tuple(SETUPS)` — every setup sub the board shows: `bull_flag`, `kiss_fly`, `horizontal_fade`, `intraday_vcp`, `reversal_squeeze`. `RS_FLOAT_SORT` (name kept) is the ONE mode knob for all of them.

`tab.order_key` (GC.RS_FLOAT_SORT = "within_state", GC.HF_EMA_SORT = "pre_break", both shipped):

| Sub | Before | After |
|---|---|---|
| 🚩 Bull Flag, 💋 Kiss & Fly, 🌀 Intraday VCP | state rank, today's key | state rank, **float ↑ (unknown last)**, today's key |
| 🎾 Reversal Squeeze | state rank, float ↑, today's key | unchanged (byte-identical) |
| ➖ Horizontal Fade — forming / partial | pre-break bucket, EMA gap ↑, today's key | pre-break bucket, EMA gap ↑, **float ↑**, today's key |
| ➖ Horizontal Fade — A+ / held / triggered / stopped | today's key | state rank, **float ↑**, today's key |
| ☀️ Premarket, 🌙 Post-market | volume / change; AH gain | unchanged |
| 🧠 Potential | potential.order_key (already float ↑ after armed/building) | unchanged |

Other modes: `RS_FLOAT_SORT = "global"` puts the float above the state rank for every setup in the tuple (➖: only its rung cards; a pre-break ➖ card keeps the gap first). `HF_EMA_SORT` "within_state" / "global": gap, then float, then today's key.

The 🧪 Audited and 1-minute pages use the same `tab.order_key` / `setup_tile` — they follow with no special case (tested).

## The float source (ONE source, no new fetch)

`setup_tile` stashes `_float_shares = _float_shares_of(_float_read(doc, daily))` — the same read the card's float chip prints (`_chips` → `_float_chip`): the pass's `ctx.float` first, the 🎾 daily doc only on 🎾 (as before). Non-🎾 cards add **zero** `get_daily` reads (tested). A suspect float under `FLOAT_SUSPECT_POLICY` "ineligible" sorts as unknown (last), as on 🎾. The stash is popped by `_strip_private` — never served.

## What did NOT change

Served keys, gates, K-lines, pushes, alerts, writes, the 🧠 / ☀️ / 🌙 orders, the focus pick (builds its key without the stash), the `order_note` text (still served on 🎾 and ➖ only).

## Golden moved by design

`frontend/src/components/__fixtures__/gajjala_potential_golden_2026_10_15.json` — the bull_flag board's card order only (GGG above JJJ); regenerated with `GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_potential_tab.py -k golden`. GG5 identity goldens (writes + board) did not move.

Tests: `backend/tests/test_gajjala_float_sort_all_setups_2026_11_09.py`.
