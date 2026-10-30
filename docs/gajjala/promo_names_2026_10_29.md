# 🎪 Promo-circuit names on 🚩 Gajjala's list — 2026-10-29

Module: `backend/chart_maps/gajjala/promo_names.py` (BUILD_SPEC32 D1–D4, D7).
Tests: `backend/tests/test_gajjala_promo_names_2026_10_29.py`.
The 📌 pattern it mirrors: `docs/gajjala/trader_names_2026_10_27.md`.

## The ask, verbatim

Ajay, 2026-10-29 ~20:05 ET (spelling kept):

"Also I see a some of stocks we see are also in Gajjalas page. Don't see some should we pull stocks from PROMO circuit by default every day they are having some good catched but I do wanna run them against Gajjalas strategies"

## INVERTED / UNMEASURED — read this first

The 🎪 Promo circuit's first tags read **INVERTED** in this app's own study (−4.78pp, CI [−7.19, −3.41],
`docs/catalysts/promo_tag_study_2026_09_21.md`). Nothing has measured GG's setups on these names: **UNMEASURED**. The add
is a WATCHLIST feed for GG's rules, not an edge. Every served sentence (the strip line, the legend row, the ℹ️ clause)
says so in words; no number from the study is served.

## The measured gap (read-only probe 2026-10-29)

The Promo circuit tags 150–200 names a day (`promo_circuit_tags`, names tagged on the day):

| Day   | 10-23 | 10-26 | 10-27 | 10-28 | 10-29 |
|-------|-------|-------|-------|-------|-------|
| Names | 114   | 151   | 155   | 125   | 170   |

Most of Gajjala's listed names are already Promo names (10-29: 22 of 27). The reverse is not — of 170 Promo names on
10-29, 148 were not on Gajjala's list:

| Why not on GG's list (10-29)                         | Names |
|------------------------------------------------------|-------|
| in the price band, over 1M volume, under GG's +25%   | 76    |
| outside the 0.10–100 price band (AON, APO, CAT, COIN…) | 38  |
| under 1M volume and under +25%                       | 29    |
| over +25% but under 1M volume                        | 4     |
| not in the snapshot                                  | 1     |
| **total**                                            | **148** |

## D1 — what joins

- **Source** `promo` (`SOURCE`), tag 🎪 (`GC.PROMO_TAG`). The session's Promo names = the tickers with a tag on the
  session's ET date — a first tag or a later one (the page's "today" rule: `PromoCircuit.tsx` reads the ET date of the
  doc's last tag). A doc counts when one of its stamps (`first_tagged_at`, `last_tagged_at`, a kept post's `at`) falls
  on the session's ET date and is not after the pass clock. `first tag HH:MM ET` on the chip = the earliest such stamp.
- **Stored tags only** — `promo_names.default_tags` is ONE Mongo read of `promo_circuit_tags` (last tag inside the
  page's `TAG_WINDOW_DAYS` 14); the pass never sweeps and never fetches StockTwits.
- **Roster + shotgun**: roster accounts only (the live `PROMO_ACCOUNTS`, its tier wins over the stored snapshot), then
  `promo_circuit.prune_shotgun_tags` over the SAME 14-day window the page uses (an account with more than
  `SHOTGUN_DISTINCT_TAGS` tickers in the window keeps only repeats) — never over today's slice alone.
- **One name per ticker**: the named account = the best tier (S, A, B), then the earliest tag that day; every account
  that tagged it is listed in the block.
- **The add check** = the 📌 one, `trader_names.candidate_row` (shared, the 📌 bytes unchanged): in today's snapshot,
  a print dated the session, a prior regular close, the instrument rule (`scanner.type_verdict`), GG's 0.10–100 price
  band. **No change floor and no volume floor for the ADD** — that is the add.
- **Order + cap (HIS CALL #1)**: the names that pass are ordered by today's % change, highest first (then symbol), and
  the first `PROMO_NAMES_MAX` = 25 join (Cheetah default, MINE, in `CHEETAH_DEFAULTS`). The rest are skipped
  `over_cap` and COUNTED (`promo_over_cap`), never silently dropped.
- **The cap is a SESSION cap (2026-10-29, critic F3).** It bounds the 🎪 adds LISTED today, not each pass's adds:
  `promo_names.listed_today` reads the session's `gajjala_scan` docs whose `last.source` is `promo` (written by an
  earlier pass), and each holds a slot. Such a name is re-read first (it passes the add check → re-added) or stays
  listed off its stored doc (`kept` in the block — it fails this pass's check, e.g. no snapshot row); it is never
  `over_cap` and never a skip. A new name only fills the room left (`PROMO_NAMES_MAX` minus the kept slots; a kept
  name that GG's own scanner now lists is tagged and frees its slot). A name `scanner.listed_symbols` already lists
  that is not a row this pass (e.g. that freed name once GG's scanner drops it) stays listed off its stored doc
  (`kept`) and is never a candidate, never `over_cap` and never a cap slot, so the cap counts today's 🎪 adds that are
  actually listed (verifier L1, `test_NEGATIVE_flip_back_name_is_kept_never_over_cap_and_cap_holds`). Before this, every pass re-ranked the day's names
  and wrote whichever 25 were on top, so over a day the listed set grew toward every in-band Promo name (about 109
  on 10-29) — the critic's two-pass churn is `test_NEGATIVE_the_cap_bounds_the_sessions_listed_promo_names_not_each_pass`.
  The strip's "added" counts every 🎪 add of today's names on the list (re-read + kept).
- **Already listed** (GG's qualifier or a 📌 add): TAGGED in place (`promo` True + `promo_text`), never a second row and
  never counted against the cap. A name both 📌 and 🎪 keeps `trader` / `trader_text` AND gains `promo` / `promo_text`
  (two chips).
- **Served words**: `promo_text` = `🎪 promo · first tag HH:MM ET · @handle · tier S` on the scan row (`last`), the read
  doc's ctx, the A+ claim, the 🧠 tracker doc (insert only), the 🏁 ledger row, every tile and row. The A+ and 🧠 push
  bodies carry it right after the 📌 clause; the titles are unchanged.

## D2 — the floors stay on every push; the counts appear only when the source ran

- The 🧠 push of a 🎪 ADD is HELD while the session volume the pass read is under `GC.SCAN_MIN_VOLUME` — the 📌 hold's
  ONE mechanism (`potential.run_pass`, `add_hold`), its own reason `promo_under_floor` (`PT.PROMO_HELD`) and its own
  words `PROMO_HOLD_TEXT` ("held: 🎪 under GG's 1M volume floor — listed and read, not rung"). A 🎪-tagged GG qualifier
  is never held (it passed his floors). The A+ is K11, unchanged.
- Pass-doc counts `promo_added` / `promo_tagged` / `promo_skipped` / `promo_over_cap` / `promo_failed` and the `promo`
  block appear ONLY when the source ran. An unwired source, a failed snapshot, or a session with no Promo name tagged
  yet adds NO key — the GG5 identity fixture (`tests/test_gajjala_variant_gg5_identity.py`) passes unchanged.
- The 🧠 counts gain `promo_held` LAST, and only when the pass handed a promo map (`COUNT_KEYS` itself is unchanged).

## D3 — wiring

- `run.run_pass`: the step runs right after the 📌 step, before `scanner.record_scan`, in the same fence — a raise adds
  nothing, counts `promo_failed` 1 and never breaks the pass. The `Deps.promo_tags` hook is the stored reader (tests
  inject one); `main()` passes `promo_names.default_tags` on the cron and on-open paths; dry runs and replays do not.
- `PN.recount` keeps `qualifiers` GG-only after the split hold-out; `PN.trim_block` follows it.
- The 🚩 1-minute page inherits through `scanner.listed_symbols` — no change to its list. Its `GG1M_MAX_NAMES` 60 cut by
  % change applies: a 🎪 name with a small move today mostly falls under that cut (HIS CALL #5). On the 1-minute page
  the 🎪 tag rides GG5's stored ctx and the same 1M hold binds a 🎪 add's 🧠 push.
- The scan universe `full` is NOT touched.

## D4 — surfaces (backend half)

- Tiles, 🧠 / 🎯 rows, 📈 track rows, 👀 watch, 🌙 recap: `promo_text` only on a tagged row (no key otherwise).
- Strip: `promo_text` ("🎪 n of today's N Promo-circuit names on this pass's list (a added, t already listed) — …") and
  `promo_skip_text` (the names that did not join, COUNTED by reason — about 150 a day, so no list), both keys only on a
  pass that ran the source.
- Counts legend: `tab.LEGEND_KEYS_PROMO` = `LEGEND_KEYS` + "promo" (last), served only when the board's pass ran the
  source or a 🎪 tag is on the list; otherwise the legend is byte for byte as before.
- ℹ️ Rules: `rules_info._gg_promo_clause` in the section note (before the 1-minute clause), built from
  `promo_names.rules_clause()`; the scanner pick keeps its 📌 clause last and picks stay eight.
- `/alerts/status`: the 🚩 row's counts carry `promo_added` when the source ran; the 🧠 row carries `promo_held` and
  `promo_held_text`, and a held 🧠 item carries `held_text` = `PROMO_HOLD_TEXT`.

## The Massive cost

Restated 2026-10-29 after critic F3 (not timed here):

- **2 bar loads per listed name per pass.** `bars.frames_for` loads the prior market day (the 1-minute cache after its
  first load) and today (`force=True`, a Massive minute fetch) for every listed name, on `board.BAR_WORKERS` 8 workers.
- **1 split check per new name per session.** `scanner.hold_out_splits` checks each name the session has not decided yet,
  serially, before the bars (decided names are never re-fetched that session).
- **The list is bounded.** At most `PROMO_NAMES_MAX` 25 🎪 adds are listed per session (the session cap above); a name
  added stays listed `STAY_LISTED_SESSIONS` 2 more sessions, so at worst 25 × 3 = 75 🎪 names are carried, on top of
  GG's own names and the 📌 adds.
- **Over-budget names get NO read that pass.** `frames_for` skips every name that would start past the deadline
  (`PASS_BUDGET_SEC` 240 on a cron pass, `ON_DEMAND_BUDGET_SEC` 45 on an open; counted `bars.over_budget`). Since
  2026-10-29 `run.py` hands `frames_for` GG's own names FIRST and the 📌 / 🎪 adds last (a stable sort; with no add the
  order is `sorted(listed)` exactly), so a deadline skips adds before GG's names; every later step still runs in
  `sorted(listed)` order.
- The tag read itself is one Mongo query, no provider call.

## HIS CALL (shipped as stated; none decided here)

1. HIS CALL #1 — the cap 25 a session (an earlier pass's add keeps its slot) and the order by today's % change
   (highest first). Another cap, or another order?
2. HIS CALL #2 — today-only (the page's rule) versus a 2-session window like the 📌 names.
3. HIS CALL #3 — include names over $100? GG's band says no (38 names on 10-29: AON, APO, CAT, COIN…).
4. HIS CALL #4 — ETFs and large caps: the instrument rule drops ETFs; large caps inside the band join. Exclude them?
5. HIS CALL #5 — the 1-minute page's `GG1M_MAX_NAMES` 60 cut by % change mostly drops the 🎪 names. Lift it for them?
6. HIS CALL #6 — put algo888 on the 🎪 Promo roster (the 📌 doc's HIS CALL #8)? Not done.

## Verification recipe

Hermetic, bytecode purged first:

```bash
cd /Users/ajay/clinet-test/cheetah-market-app/backend
/usr/bin/find . -name __pycache__ -type d -prune -exec rm -rf {} +
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_gajjala_promo_names_2026_10_29.py tests/test_gajjala_trader_names_2026_10_27.py tests/test_gajjala_variant_gg5_identity.py
```

After the deploy, on his surface: a 🎪 chip on a Gajjala's card, the `promo_*` counts in the newest pass doc, and the
`promo_held` count on `/alerts/status`.
