# ❌ Gajjala's losers study — every 🏁 loser in pre-declared classes (2026-10-16)

Code: `backend/scripts/gajjala_losers.py` (NEW, offline, outside the source guard; reads only, writes only `--out`).
Engine: `backend/chart_maps/gajjala/ledger.py` — `bucket_of`, `loss_facts`, `loss_text`, `fill_facts` (the ONE engine
the 🏁 Track record serves from; the script imports them, never a second copy). Thresholds:
`backend/chart_maps/gajjala/constants.py` `LEDGER_LOSS_*`. CI: `backend/tests/test_gajjala_losers_script.py` on the
SYNTHETIC fixture `backend/tests/fixtures/gajjala/losers_ledger_2026_10_16.json`. Spec: `BUILD_SPEC11.md` §3.16 +
`AMENDMENTS11.md` F1 / F2 / F4 / F5 / F14 + `DECISIONS11.md` D11–D13 (session scratchpad `gg_charts/`). The ✅ / ❌
categories and the served loss facts: `docs/gajjala/entry_timeline_2026_10_16.md` → "✅ / ❌ categories and loss facts".

## READ THIS FIRST

1. **Descriptive — a class is a question for Gajjala's rules, not a finding.** The study lists every loser and counts
   it into classes declared BEFORE the count. It measures nothing: **no win rate, no expectancy, no verdict**, no CI, no
   placebo, no ratio of losers to winners. A class count is a fact about the rows on file, never a rule.
2. **The 2026-10-14 study read NULL** — no setup of the five showed an edge over a risk- and hour-matched placebo
   (`docs/gajjala/study_2026_10_13.md`). This study does not change that and is not a second study of edge.
3. **Rule #9 (Ajay 2026-09-03)**: one feedback line per loser; **≥3 of the same class → propose a rule WITH the numbers
   and wait for his sign-off** — never change a rule, a gate or a threshold from this list. A flagged class prints
   "≥3 → candidate rule — HIS CALL" (the 3 = `LEDGER_LOSS_CLASS_FLAG_N`); the proposal and the decision are HIS CALL.
4. **Small n + survivor bias.** Four sessions of records (2026-10-13 … 2026-10-16), five setups, two lines; the A+ rows
   exist only after surviving their entry bar. A name that rang on two setups (or as a 🧠 and its 🎯) is one trade on
   several rows — the classes count TRADES, the rows sit beside them (AMENDMENTS11 F1).
5. **Replayed rows (⏪, never rang) are EXCLUDED by default**; `--include-replayed` adds them as a separate run.

## The ask (Ajay, 2026-10-16 ~22:45 ET, verbatim)

> "I want winners and losers category in his track record and would like us to study the losers"

## Method (BUILD_SPEC11 §3.16 as amended)

**Input.**
- `--mongo`: `store.ledger_docs(store.ledger_dates())` — every graded `gajjala_ledger` doc (the app's own Mongo
  settings); with `--include-replayed` also `store.replay_rows(store.replay_dates())`. A read fault (`ledger_dates()`,
  `ledger_docs()` or, with the flag, `replay_rows()` answering None) → prints `ledger unreadable — nothing written` and
  exits 2, no file written (AMENDMENTS11 F5) — a fault is never "no loser on file".
- `--from-json FILE`: a JSON list of `gajjala_ledger` docs and / or §3.12 replay docs.
- Default lines: live + shadow, both kinds (🧠 potential and A+). A `REPLAY:` doc is kept ONLY with
  `--include-replayed`.

**Rows.** A ledger doc → the `alert_of`-shaped row (date, symbol, setup, kind, line + the stored alert block's trigger,
stop, r, thin, rang, plan, the alert time); a replay doc → `LG.alert_of(doc, "aplus")`. Each column's state =
`LG._state_of(col)` when the column is a dict, else "pending" (a doc with no `next` yet — every 2026-10-16 doc until the
2026-10-19 nightly; AMENDMENTS11 F4).

**The bucket rule** = `LG.bucket_of(same_state, next_state, next_due)` — the one the 🏁 chips serve: the next column
win / loss → that; else the same column win / loss → that; else next "flat" → "flat"; else same "open" while the next
column is still due → "open"; else "out" (AMENDMENTS11 F7). A row is a **loser** when its bucket is `loss`; its facts =
`LG.loss_facts(row, the loss column)` (next when its state is loss, else same) — stored grade fields only, never a
regrade, never a bar read.

**Trades.** Loser rows are grouped into trades by `(date, symbol, trigger, stop)`; classes C1–C7 count and flag
DISTINCT trades, with the row count printed beside: `"C2 last 30 min of RTH · 7 trades (9 rows)"` (AMENDMENTS11 F1).

**The pre-declared classes** (one tag per dimension — no others, no fishing):

| class | the fact (from `LG.loss_facts`) | constant |
|---|---|---|
| C1 | rang AH → filled next morning (`next_morning`) | — (the stored `rang` = ah, the fill's ET date ≠ the alert date) |
| C2 | fill in the last 30 min of RTH (`late_rth`) | `LEDGER_LOSS_LATE_RTH_MIN` = 30 |
| C3 | fill ≥60 min after the ring (`stale`) — never a next-morning fill (AMENDMENTS11 F2: a C1 trade is not C3) | `LEDGER_LOSS_STALE_FILL_MIN` = 60 |
| C4 | stopped ≤5 min after the fill (`fast`) | `LEDGER_LOSS_FAST_MIN` = 5 |
| C5 | high < +0.3R before the stop (`no_progress`) | `LEDGER_LOSS_NO_PROGRESS_R` = 0.3 |
| C6 | high ≥ +0.8R, then stopped (`gave_back`) | `LEDGER_LOSS_GAVE_BACK_R` = 0.8 |
| C7 | thin R (`thin`) | — (the stored alert block's `thin`) |
| C8 | one trade on ≥2 setups — ≥2 loser rows with the same date, symbol, trigger and stop (the trades, and the rows they cover) | — |
| C9 | per setup — one count per setup (a split, never flagged) | — |
| C10 | per rang bucket — pre / rth / ah (a split, never flagged) | — |

The five thresholds are TRANSPORT — MINE (HIS CALL Q13 of `docs/gajjala/entry_timeline_2026_10_16.md`); the R is the
alert's own trigger − stop (`r`); the high is `best_to_exit_pct` through the stop minute (AMENDMENTS11 F17).

**The flag count.** A class among C1–C8 with ≥ `LEDGER_LOSS_CLASS_FLAG_N` (3, Ajay 2026-09-03, Rule #9) TRADES is marked
`"≥3 → candidate rule — HIS CALL"`. C9 and C10 are reported as splits and NEVER flagged (AMENDMENTS11 F14). Beside each
of C1–C7's loser count the md prints the count of the same fact among WINNER trades (`bucket == "win"`, the same fields
through `LG.fill_facts`) — counts only, no %, no ratio: `"C1 rang AH → filled next morning · 5 loser trades (9 rows) ·
3 winner trades"`.

**Out** (only under `--out`):
- `losers.csv` — one row per loser: date, symbol, setup, kind, line, rang, trigger, stop, the facts, the C1–C8 flags,
  `loss_text`.
- `losers.md` — a header (the source, the row count, "descriptive — a class is a question for Gajjala's rules, not a
  finding", the 2026-10-14 study NULL); ONE line per loser (Rule #9) = `"{date} {SYM} {setup_label} · {loss_text}"`
  — `loss_text` is `LG.loss_text`, byte-equal to the 🏁 row's served sub-line; the class table C1–C10; the flags. No
  number followed by a percent sign, no causal word. An empty list still writes both files and says "no loser on file".
- Exit 0 (2 on a read fault, above).

## How to re-run

On the throwaway api `cheetah-tmp-gr-api` (`scratchpad/gg_charts/gr_tmp_api.sh`: the worktree backend at `/app`, ONE
output mount `/replay_out` — AMENDMENTS11 F18), after the D6 replay run, outside 09:30–16:00 ET. READS ONLY — the two
counts must be equal before and after.

```bash
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'printjson({ledger: db.gajjala_ledger.countDocuments({}), replay: db.gajjala_replay.countDocuments({})})'
docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_losers --mongo --out /replay_out/losers
docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_losers --mongo --out /replay_out/losers_with_replay --include-replayed
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'printjson({ledger: db.gajjala_ledger.countDocuments({}), replay: db.gajjala_replay.countDocuments({})})'
```

The outputs land in the session scratchpad `gg_charts/replay_out/losers/` and `gg_charts/replay_out/losers_with_replay/`.
Check: the default run's loser count vs the live ledger's loss rows on lines live + shadow (the coordinator read 38 rows
with a loss in same or next on 2026-10-13 … 2026-10-16 at 22:45 ET; the later-column rule may differ — report both
numbers, never reconcile by hand); the counts unchanged after.

The CI (hermetic, no network):

```bash
/usr/bin/find /Users/ajay/clinet-test/wt-ggcharts/backend -name __pycache__ -type d -prune -exec rm -rf {} +
docker run --rm --network none --name cheetah-tmp-pytest-gr-e-1 -v /Users/ajay/clinet-test/wt-ggcharts:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_losers_script.py
```

## Run log (main session — tonight's class counts, pasted after the run)

### Default run (lines live + shadow, replayed EXCLUDED) — `/replay_out/losers/losers.md`

Run 2026-10-17 ~00:55 ET on the throwaway api `cheetah-tmp-gr-api` (branch 60aeae5a, reads only), after the D6 replay write.

| | value |
|---|---|
| ledger docs read | 119 (2026-10-13 … 2026-10-16; lines live + shadow, both kinds) |
| loser rows / loser trades | 38 rows / 33 trades (winner rows 29) |
| `gajjala_ledger` / `gajjala_replay` counts before → after | 119 / 7 → 119 / 7 (the script wrote nothing) |

Class table (C1–C10, trades (rows), winner trades beside C1–C4 and C7 (C5 / C6 are loss-only facts — a winner has no stop to measure the high against); flagged classes marked) — `/replay_out/losers/losers.md`, verbatim:

- C1 rang AH → filled next morning · 8 loser trades (9 rows) · 6 winner trades · ≥3 → candidate rule — HIS CALL
- C2 fill in the last 30 min of RTH · 7 loser trades (9 rows) · 6 winner trades · ≥3 → candidate rule — HIS CALL
- C3 fill ≥60 min after the ring (next-morning fills not counted) · 7 loser trades (8 rows) · 3 winner trades · ≥3 → candidate rule — HIS CALL
- C4 stopped ≤5 min after the fill · 15 loser trades (16 rows) · 15 winner trades at +1R ≤5 min · ≥3 → candidate rule — HIS CALL
- C5 high under +0.3R through the stop minute (no progress) · 13 loser trades (14 rows) · ≥3 → candidate rule — HIS CALL
- C6 high ≥ +0.8R through the stop minute, then stopped (gave back) · 9 loser trades (9 rows) · ≥3 → candidate rule — HIS CALL
- C7 thin R · 3 loser trades (3 rows) · 0 winner trades · ≥3 → candidate rule — HIS CALL
- C8 one trade on two or more setups (same date, symbol, trigger and stop) · 5 loser trades (10 rows) · ≥3 → candidate rule — HIS CALL
- C9 setup · ➖ Horizontal Fade 5 (5) · 🌀 Intraday VCP 15 (15) · 💋 EMA Kiss & Fly 5 (6) · 🎾 Reversal Squeeze 9 (12)
- C10 rang · AH 8 (9) · pre 2 (2) · RTH 23 (27)

Reading (counts only, four sessions, 33 loser trades — every class clears the ≥3 flag at this n, so the flag alone says little;
the winner column beside each class is the context): C4 (stopped within 5 minutes) has as many winner trades that reached +1R
within 5 minutes as loser trades stopped within 5 minutes — a fast resolution either way, not a loser pattern. C1 (rang after
hours, filled next morning) and C2 (filled in the last 30 minutes) carry nearly as many winners as losers. C3 (filled an hour or
more after the ring, next-morning fills excluded) carries 7 losers to 3 winners — the one lopsided class besides C7 (thin R, 3 to
0, already out of the %). The 38 loser lines above hold the per-loser facts for his read.

### With `--include-replayed` — `/replay_out/losers_with_replay/losers.md`

Docs read 126 (119 ledger + 7 replay) · loser rows 38 +3 ⏪ · loser trades 33 +3 ⏪ · winner rows 29 +2 ⏪. The three
replayed losers (10-09 WFF 🌀, 10-12 SKYA 🌀, 10-12 YMAT 🎾) print with the ⏪ chip and sit outside every count and flag:
C1 … 6 winner trades +2 ⏪ · C4 … 15 winner trades +2 ⏪ · C5 13 (14) +1 ⏪ · C6 9 (9) +1 ⏪ · C9 🌀 15 (15) +2 ⏪ · 🎾 9 (12) +1 ⏪
· C10 RTH 23 (27) +3 ⏪; every other line equal to the default run.

## HIS CALL (nothing here is decided for him; nothing changes a gate tonight)

- **Any rule drawn from a flagged class** (e.g. "no A+ fills in the last 30 min", "skip after-hours rings") is HIS
  CALL — proposed with the class's numbers (trades, rows, the winner trades with the same fact), never applied without
  his sign-off (Rule #1 / #9 / #10).
- **The thresholds** `LEDGER_LOSS_FAST_MIN` 5, `LEDGER_LOSS_LATE_RTH_MIN` 30, `LEDGER_LOSS_STALE_FILL_MIN` 60,
  `LEDGER_LOSS_NO_PROGRESS_R` 0.3, `LEDGER_LOSS_GAVE_BACK_R` 0.8 are MINE (DEFAULT) — his to change; the flag count 3 is
  his Rule #9 (entry timeline doc Q13).
- **C9 / C10 never flag** (setup and rang are splits — AMENDMENTS11 F14, MINE; DEFAULT) vs flagging them like C1–C8
  (entry timeline doc Q15).
- **Replayed rows excluded by default** (they never rang; DEFAULT) vs in the default run.
