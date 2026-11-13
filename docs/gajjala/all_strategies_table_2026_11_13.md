# 📋 All strategies — the ranked table on 🚩 Gajjala's tab (2026-11-13)

## The ask, verbatim
Ajay 2026-11-13: "Hey can you build be a table like track record on Gajjals landing page.. Call all strategies. I want this
table to rank based how gajjals sees them.. He watches 18 stocks simultaneously I am unable to see that view with car and
tab lay out I will use this table format but I need tha track record like graph thoouhg So A+'s on top and potental next
and others close to strategies next liek EMA near kiss first, horizontal fade 9 EM Anad 25 EMA merge second and VCP next
reversal potental next with categories showing in the table"

## What ships (backend, WP-A)
- `constants.SUBS` gains `("all_strategies", "📋", "All strategies")` **FIRST** (one string-literal tuple — the contracts
  regex reads it); `TABLE_SUB = SUBS[0][0]`; `TABLE_SETUP_ORDER = (kiss_fly, horizontal_fade, intraday_vcp,
  reversal_squeeze, bull_flag)`; `GG_WATCH_N = 18`. `DEFAULT_SUB` stays `bull_flag`.
- `chart_maps/gajjala/all_table.py` (pure — no store, no fetch, no clock): `tier_of`, `spark_bars`, `spark_of`, `row_of`,
  `block`, `attach_live`. Every word the table prints is typed there (TITLE, ORDER_TEXT, TIER_WORDS, HEADS, WATCH_TEXT,
  EMPTY / MORE / FAULT texts, HONESTY).
- `tab.build(sub="all_strategies")` (GG5 only) builds every setup's cards with the setup subs' own `setup_tile` (each on its
  own sub's default frame: ➖ `v.slow`, the rest `v.primary`, the read's frame first) and serves `out["table"]` through
  `_soft`; a raising block → `table: null` + `empty_note = TABLE_FAULT_TEXT`. `tiles` stays `[]` (no focus, no order note).
  The 📋 chip count = the sum of the five setup subs' card counts (`n_tiles`), on every sub. `resolve_sub` resolves the
  sub to the default on GG1 / 🧪, whose strips never list it.
- 🚫 / 📌 / 🎪 walks tag the table rows; `entry_marks.apply` gives a row its setup's ✨ mark, else the name's 🧠 mark.
- `GET /chart-maps/gajjala?sub=all_strategies`: ONE more `board._live_snapshot` over the rows → `live_price` +
  `live_price_text` (`board._snapshot_print`, `tab._px`). The route `limit` does not cut the table.

## The rank rule (display order only — UNMEASURED)
1. Tiers: 🎯 A+ (`entry_marks.BREAK_STATES` — aplus, triggered; `tab._state_key`: aplus before triggered, newest entry bar
   first) → 🧠 potential (`potential.order_key`: armed before building, volume ↓, float ↑, SETUPS order, symbol) → forming,
   close to a setup (`TABLE_SETUP_ORDER`, each setup in its own sub's served order verbatim — 💋 rel volume then 9 EMA
   distance, ➖ 9/21 EMA gap, the rest volume ↓ then float ↑) → a rule failed / stopped (same order).
2. Concatenate, then cut at `TILE_LIMIT_MAX` (`tab._capped`) **first**; then his 🚫 names go last **in their tier inside the
   cut** (`tab.broker_bottom`). Why: partition-then-cut could push a flagged name past row 80 on a busy day — the 11-09
   invariant says the list only reorders, never drops.
3. Rank 1..N; `in_watch` = the row's symbol is among the first `GG_WATCH_N` DISTINCT names of the final order (a name on
   two setups counts once, listed twice); `watch = {n, rows, text}`.
4. A raising row is skipped and counted (`faults_n`, `fault_text`), never silent.

## Payload keys
`table = {title, heads[{key,label}], order_text, watch{n,rows,text}, rows[], n, more_n, more_text, faults_n, fault_text,
empty_text, honesty, tape_head}`. Row: rank, tier, tier_key, tier_label, symbol, name, setup, setup_emoji, setup_label,
state, state_word (the tile's variant / grade label first, else `potential.state_word`), state_label, category_text, kind,
kind_label, href (`chart_href`), card_href (`potential.deep_link`), tf, price, price_text, change_pct, change_text, volume,
volume_text, rvol_text, float_text, trigger, stop, risk_pct, plan_text, dist_pct, dist_text, entry_plan, in_watch,
vol_dried, spark, (+ broker_text, trader_text, promo_text, new_mark, live_price, live_price_text). No "_" key, no bars /
curves. `spark` = `tape.LITE_KEYS`: TODAY's frame only (`tab._tile_frame(doc, tf, v)`, never the 🎾 wide frame), `t` = the
ET wall clock as epoch ms, `s` = `support._SESSION_FLAG` inverted (pre → premarket, ah → afterhours, none → rth), strided by
`promo_tape.lite_payload`; one `alert` rule at the entry bar on a break, else none; tone up / dn vs the trigger.

## Frontend (WP-B, summary)
`GgAllTable.tsx` prints the served heads, rows, divider after the last `in_watch` row, and the 🏁 mini from the preset
spark (no per-row fetch); the price cell prints the route's `live_price_text`, else the pass's `price_text`; the 30-s live poll is OFF on this sub (its `now.label` is a word, never a price), so prices move with each board refresh. The
pre-board fallback strip shows 📋 on 🚩 only.

## Tests
`backend/tests/test_gajjala_all_table_2026_11_13.py` (T1–T16, 37 tests, NEGATIVES: cut-then-partition, dated-today spark,
three session words, long-flag word, GG1/🧪 fail-open, no fetch, no private key, NaN, faults, live). Mutation-checked
(bytecode purged): wide frame, partition-before-cut, raw session flag, dropped variant label — each turns one test red.
Re-pinned by design: test_gajjala_constants (order + contracts-regex copy), counts_legend (11 / "other ten"), gg5 identity
(11 subs). Goldens regenerated with the recipe — only the 📋 `subs` entry and the identity file's `all_strategies` boards
moved; the WRITES golden is byte-identical.

**Full backend suite, 2026-11-13 (re-run, reproducible).** The skill's verbatim command aborts at COLLECTION on the
host venv (Python 3.9.6): `tests/test_holdings_loop_stall.py` imports `portfolio/api.py`, whose `portfolio_delete` route (line 184) uses
`str | None` in a FastAPI signature (unchanged on main since da54f678, 2026-10-06; this change does not touch `portfolio/`).
Pre-existing, main's, HIS CALL. The run that produced the count adds one ignore:
`cd backend && rm -rf ~/Library/Caches/com.apple.python; /usr/bin/find . -name __pycache__ -type d -prune -exec rm -rf {} + ;
.venv/bin/python -m pytest tests/ -q --ignore=tests/test_portfolio_eq_risk.py --ignore=tests/test_accumulation.py
--ignore=tests/test_holdings_loop_stall.py -p no:cacheprovider` →
**12 failed, 20,278 passed, 18 skipped, 1 xfailed** (317 s). The 12 reds are all outside this change's files, none touched:
test_accumulation_share_basis_2026_10_06 (split lookup) · test_ath_tab 02f · test_crontab_entrypoints ×7 (L403, L409,
L334 portfolio.alerts, L468 portfolio.supply_watch, L839–L841 portfolio.diagnosis) · test_gajjala_verified_rules
used_by pin (`K11_MIN_SESSION_VOLUME`, added on main fd66595e 10-21) · test_hermes_bridge env · test_ollama_chat env.

## HIS CALL
1. "/" opens 📋 instead of 🚩 Bull Flag? [stays bull_flag; 📋 first in the strip]
2. "25 EMA": GG's merge is the 9/21 EMA (`EMA_SLOW = 21`). [21 kept]
3. 🚩 Bull Flag's place in the forming tier. [last]
4. `triggered` shares tier 1 with a fresh A+. [yes; fresh A+ first]
5. Tier 4 below tier 3 vs one folded tier (splits the ➖ pre-break bucket). [split]
6. 🧠 rows per (symbol, setup) vs one per symbol. [per setup]
7. 🚫 names last in THEIR tier vs the whole table bottom. [their tier]
8. "GG's 18" = a divider vs a hard cap. [divider]
9. Transport cap 80 rows + "N more" line; the route `limit` ignored on the table.
10. 1-minute page, 🧪 Audited, 🥇 Luk: not built (GG5 only).
11. Phone: nine columns scroll sideways. [all nine]
12. Live prices via the route's fan-out + the cards' 30-s poll; no "vs trigger" live words.
13. 📈 full-tape toggle on rows that rang — not built (mini only).
14. Strip position first vs after 🏁. [first]
15. 🧭 stages / ⏸ no-breakout / 💧 as columns — only 💧 rides under Category.
16. The served words (TITLE, ORDER_TEXT, TIER_WORDS, WATCH_TEXT, HEADS) — his wording wins (a golden regen).
17. Tier-2 order = `potential.order_key` verbatim vs his setup order as tie-break; tier 1 newest break first vs his order.
18. "GG's 18" counts distinct names vs 18 rows. [distinct; both numbers printed]
19. 🎾 spark = today's bars only vs the wide frame shaded. [today only]
