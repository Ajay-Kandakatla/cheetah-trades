# 🏁 Luk's — an ended trade leaves the cards he reads as live, in real time (2026-11-12)

**Display only. UNMEASURED**, as the whole 🥇 tab is. Nothing here changes what rings, the A+ rule, the 🏁 grading, the
stop-R fix, a gate, a threshold, a push or the crontab. PAPER only. Spec: `lukend` r2 (session scratchpad), WP-A
(backend). The FE half (WP-B) and the re-read skip (WP-C) are recorded by the main session.

## His words

Ajay 2026-11-12 ~17:10 ET, about a 🥇 Luk card for MSTR (trigger 114.31 broke on the 1-minute candle closing 09:36 ET,
stop 112.32, Last 114.31, daily 9 EMA 129.37), verbatim (his spelling):

> "Is this still good ro enter? From Luks" → "I shouldn't be seeing this" → "I want it to be realtime"

## What is built (backend)

`luk/ledger.py` gains ONE read-only function, `card_trades(store, session)` — `{(SYM, setup): {state, exit_text,
fill_t, through_date}}` from the 🏁's own `rows_for` + `ledger_docs` + `state_of` / `cells`. It fails CLOSED: an
unreadable claim or ledger collection → `{}` → no card folds by the 🏁. Nothing else in `ledger.py` moved (a test pins
the top-level defs = HEAD ∪ `card_trades`).

`luk/tab.py` — `fold_of(doc, setup, read, ctx)` per card, first match wins:

| rule | when | served |
|---|---|---|
| 1 | the read says `stopped` (the detector's own `_stop_touched_after`) | ended, `ended_why` "stop", "🏁 ended — a closed bar after the trigger traded at or under the stop {stop} (Luk's exit)" (+ " · 🏁 {exit}" when the 🏁 graded an exit) |
| 2 | ctx given, the read is a trade (`aplus` / `triggered`), the 🏁 graded its exit (stop or `ema9_close`) | ended, "🏁 ended — {exit} (Luk's exit, as graded on the 🏁 Track record)" — a `listed` / `forming` card with a 🏁 row never folds (C5) |
| 3 | **OFF** — `CARD_CLOSE_EXIT_ON = False`, HIS CALL #1 | when ON: the card's 15:55–16:00 bar closed under the prior close's daily 9 EMA, after the close + `GC.BAR_SETTLE_SEC`, unless the 🏁 already walked the official close of this session open |
| 4 | else | not ended; `live_fold` {kind `VS_KINDS[1]`, session "rth", until_epoch = the regular close, text} on a trade card of today before the close; `trade_text` on a `triggered` card after his window |

- `live_fold` is the rule the FE's house 30 s card poll folds by — no pass, no GET. `chart_maps.live_card` is imported
  ONLY inside that branch, after the ctx check (C6): the pass's re-read names (`ctx` None) never import it.
- Window words: "entry window closed 10:30 ET — not an entry" (↩️ / 🔔: the read carries the detectors' `in_window`
  criterion → `_open_plus(LUK_TRIGGER_WINDOW_END_MIN)`; strict `>`); 📦 inside day = the regular close (13:00 on a half
  day). An `aplus` card never gets them. "open trade since HH:MM ET, not a new entry" only from a 🏁-graded open trade.
- `live_tiles(tiles)` = THE split (build, and run's re-read names under WP-C). `build` keeps the cut and the re-read
  partition on the live cards exactly as before (ORDER_VARIANT A line byte-identical); `resolve_sub` still sees every
  card (a focus on an ended card picks its sub and opens the fold).
- `ended_block` → top-level `ended` on every SETUP sub (n 0 included — the FE needs the head words for a live fold);
  `None` on screens / 📓 / 🏁 and in `fault_payload` (C4). Sub chip `n` = live cards; its title gains " · N ended —
  folded under the cards". The counts line is untouched (it counts reads — HIS CALL #12).

## Why rule 3 ships OFF — the identity is exact for the EMA, NOT for the close (C1)

`ema` uses `adjust=False`: ema_d − close_d = 0.8·(ema_{d−1} − close_d), so for one close value **close < ema_d ⟺ close <
ema_{d−1}** — the prior close's 9 EMA (`facts.ema9`) answers the walk's `ema9_close` test exactly (test 12: 200 seeds,
two year-long frames ≥ 30 sessions apart, like `load_prices(sym, "1y")`). What is NOT the 🏁's test is the close
SOURCE: the card has only the minute-built 15:55–16:00 bar; the 🏁 uses Luk's own post-close daily fetch (the official
close). Measured tonight, read-only, every luk_reads card's "16:00" bar vs `luk_daily facts.close` of that date
(probe `/private/tmp/claude-501/-Users-ajay-clinet-test/2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/lukend/probe_close.py`):

| pairs | exactly equal | median abs diff | max abs diff | judgeable (prior 9 EMA) | answer flips |
|---|---|---|---|---|---|
| 59 | 12 (20 %) | 0.10 % | 4.30 % (NRDY 11-09: 6.68 vs 6.98) | 36 | 1 (ARRY 11-10) |

ARRY 11-10: card 4.725 < ema 4.725080181218225 → the card test folds; official 4.73 > ema → the 🏁 calls it OPEN. When
ON, the words name the bar and say so, and both numbers print apart where they would print the same (`_px_apart`, C2):
"closed 4.7250 under the daily 9 EMA (4.7251 at the prior close; the official close can differ)".

**Consequence, plainly:** by default MSTR does NOT fold tonight — the only post-close pass graded 7 of today's 18 A+
rows (`LUK_GRADE_MAX_LOADS` 60 spent), MSTR not among them. It stays live carrying "entry window closed 10:30 ET — not
an entry" (the answer to "Is this still good ro enter?"). It folds tonight only if he flips #1, or when the 🏁 grades it.

## Golden diff (`LUK_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_luk_tab.py -q -k golden -p no:cacheprovider`)

Key for key, nothing else moved:
- `default.ended` = the n 0 block (head "ended today — stopped or closed below the daily 9 EMA (Luk's exit)");
  `premarket.ended` / `track_record.ended` = null.
- `default.tiles[0..2]` + `ended`, `ended_why`, `ended_text`, `trade_text`, `live_fold`: AAA (aplus, 10:12 ET, stop
  11.98) `live_fold` = {under_stop, rth, until 16:00 ET, "🏁 ended — the live price traded at or under the stop 11.98
  (Luk's exit) · the next pass reads it on the closed bar"}; BBB / CCC (listed) all null / false.
- `subs[opening_range_high].n` 3 → 2 and its title + " · 1 ended — folded under the cards" (in all three payloads).

Pins moved (predicted by the spec): `test_luk_tab.py` ORH order (+ the ORH `n` in the sub-count dict, same fact),
`test_luk_tab_realtime_2026_11_12.py` CCC read from `ended.tiles`, `test_luk_not_reread_2026_11_11.py` tile keys ∪
`FOLD_KEYS`. The three `set(fault_payload()) == set(PAYLOAD_KEYS)` pins stay green through `"ended": None`.

## Tests

`backend/tests/test_luk_ended_fold_2026_11_12.py` — spec tests 1–20 with NEGATIVES (MSTR default stays; ARRY words;
200 near-tie pairs never print equal; C5 listed / forming with a 🏁 row; C6 blocked import bites in `build`, not without
ctx; C8 identity; switch pinned OFF; card_trades fails closed; zero store writes). Mutations each turned a named test
red: `<` → `<=`, drop the `as_of` check, the switch ON in the file, drop the rule-2 state guard, the live_card import at
the top of `fold_of`, `"ended": None` removed from `fault_payload`.

## HIS CALLs (none decided by this build)

1. **The card-close test** — built, shipped OFF. Keep OFF, or ON? (table above)
2. Sub-chip counts = live cards only (built).
3. Fold triggered cards at the window end? Built as words only.
4. "open trade since" in-session (an in-session fill read in the pass) — not built.
5. 🏁 coverage after the close (grade today first / raise `LUK_GRADE_MAX_LOADS` / a later post-close pass).
6. Faster Luk push (a 1-minute loop) — not built.
7. A "stopped" push kind — not built.
8. Listed cards whose stop traded — fold them too?
9. Grid rounding for the live fold (house `live_vs` grid vs strictly under the stop).
10. Forming cards after the window — fold or label?
11. The ✨ and fold wording.
12. The counts line ("· N ended")?

## Deploy

```bash
./deploy-cheetah-main.sh api frontend
```

(+ `cron` when WP-C's run.py change ships.)
