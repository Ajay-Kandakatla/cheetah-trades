# 🧭 Setup stages — the setups a stock passed through, on every Gajjala card (2026-11-11)

**Display only.** No gate, rule, threshold, number, push, order change, write or fetch. History, not a signal:
nothing here claims an edge. UNMEASURED, as every Gajjala read is.

## His words

- Ajay 2026-11-11 ~08:39 ET: *"Another big thing I need is what stages a stock has crossed in the past like
  Bullflag -> EMA Kiss and Fly -> and Horizontal -Fade so I know their stages may be add them like tags or some UI to
  show me stages with time stamps if its same day"*

Read of the ask: a "stage" = one of GG's five setups the stock was in (🚩 → 💋 → ➖ …), in time order, as tags; each tag
says how far that setup got (🧠 potential / 🎯 A+ / triggered / stopped); a clock ONLY when the session is today
("time stamps if its same day"), the date only otherwise.

## 1. What a stage is — fold + merge

Engine: `backend/chart_maps/gajjala/stages.py` — a pure view (no store, clock, I/O or datetime parsing; imports only
`constants`). Two sources, both already on file:

1. **The 🧠 tracker's own `state_path`** (`potential.track`, the ONE engine that records a setup's states through a
   session). Each entry is stamped with the PASS clock that first saw it (`at_et`, "HH:MM" ET).
2. **The live A+ alerts that RANG** — `tab._entry_times` (`store.alert_rows` + `ledger.alert_of`, line "live" = a `GG:`
   claim in state pushed). Merged ONLY where the tracker path has no A+ step.

| `state_path` entry | Stage |
|---|---|
| `forming` + kind `building` or `armed` | 🧠 potential |
| `aplus` | 🎯 A+ |
| `triggered` | triggered |
| `stopped` | stopped |
| partial · invalid · none · 🪦 graveyard · forming with no base · malformed | never a step (and never breaks a fold) |

- **Fold:** consecutive equal stages print once, at the FIRST time (building → armed = one "potential"; potential →
  partial → potential = one). A second leg (… stopped → potential → A+) is kept.
- **Merge:** a rang A+ the path lacks goes in at its own clock, before the first later step (one session = one ET day,
  so "HH:MM" strings order); else at the end. A path that already has its A+ is never changed (measured: the two
  clocks agree 37 of 37 where both exist).
- **Never invented:** a triggered / stopped with no A+ step and no rang live claim stays as seen.

Real chains (read-only probes, §Probe recipe):

| Chain | Tag |
|---|---|
| HUHU 2026-11-05 🎾 — rang 14:46, path armed 17:01 → partial 18:01 → graveyard 04:01 (it became a potential only after hours) | "🎾 Reversal Squeeze · 🎯 A+ 14:46 · 🧠 potential 17:01" (that day; date only on later days) |
| PMAX 2026-11-04 | "🌀 … potential 13:36 · stopped 14:21 → 💋 … potential 15:01 → ➖ … potential 15:46" (that day) — its "stopped" has no A+ and no claim rang: no A+ invented |
| CHSN 2026-11-06 | "🌀 … potential 05:27 → ➖ … potential 10:16 → 🎾 … potential 11:41 · 🎯 A+ 11:46 · triggered 11:51 · stopped 12:06" |

## 2. Span and reads

- **Span** = the listing window `SC._window(session)` — the board's session + `GC.STAY_LISTED_SESSIONS` (2) before it
  (GG S9 1:17:32 "a couple of days"; the window that keeps a name on his list). No new number.
- **Reads per board: +1** `st.potentials` (the window's third session — today and prev are already read by `build`)
  and **+1** `st.alert_rows` (inside `_entry_times`, over the window). **Zero per card** (`potential_docs_for_symbol` is
  never called). 🏁 / 📓 have no tiles → `_stage_tag` returns before any read.
- Wiring: `tab._stage_tag(out, st, session, have, *, is_today, v)`, called once in `build` after `_promo_tag` and
  before `_strip_private`, inside `_soft("setup stages", …)`. Every block is computed FIRST, then all are assigned —
  a raise anywhere → no card has the key, the board serves. Order, cut, 🚫 partition, counts, subs, legend: untouched.
- Faults: one session's tracker read fails → that session shows no tracker tag; the claim read fails (`_entry_times`
  → None) → tracker only.
- **2026-11-11 review fix — ONE `alert_rows` read per build (D10 kept).** The +1 above broke the defects spec's "at
  most ONE `st.alert_rows` read per build" (a setup sub with cards read twice: the D10 words read over
  `[session, prev]` and the stages read over the window). `build` now makes ONE read over `SC._window(session)` (a
  superset of `[session, prev]`), memoised and only when a consumer needs it, and hands it to the setup-sub words,
  the 🧠 entries, the 🌙 recap and `_stage_tag(…, entries=)`. Safe: every consumer looks up `(date_iso, SYM, setup)`,
  so the older window day is never matched by the `[session, prev]` words. 🧪 keeps its separate `st.shared` read.
  A ☀️ board reads it once only when it has a card (the 🧭 tag needs the claims); with no card it reads nothing. Moves (main session): the two count pins
  (`test_gajjala_defects_k11_words_2026_11_11.py` `c == [S, PREV]`, `test_gajjala_potential_tab.py`
  `calls == [[S, PREV]]`) now see the window as the read's argument; the count stays 1.

## 3. Served payload + words

Per card, **absent** when the symbol has no tag (never null):

```
tiles[i].gajjala.stages = {"title", "hint", "sep", "text",
  "groups": [{"date", "label", "clock",
              "tags": [{"setup", "emoji", "label", "here", "steps": [{"stage", "word", "at_et"}], "text"}]}]}
```

- Groups oldest session first; tags inside a group by their first step's ET clock (no clock last), then GG's SETUPS
  order. `here` = the card's own setup in the board session (☀️ / 🌙 cards: none).
- `clock` = (group date == board session AND the board session is today). Otherwise `label` = "Mon 11-10"
  (`ledger._dow_md`, pinned) and every `at_et` is null.
- Every viewer gets the same `stages` (a fact about the board); the 2026-10-17 owner/non-owner invariant holds.

| Constant (`stages.py`) | Served word |
|---|---|
| `TITLE` | "🧭 Setup stages" (his "stages" + "Setup", so it never reads as a 1–4 stage count) |
| `STAGE_WORDS` | "🧠 potential", "🎯 A+", "triggered", "stopped" — each milestone's last word == the first word of the card pill (`tab.state_label`) on the same card, pinned by a test |
| `STEP_SEP` / `TAG_SEP` | " · " between steps · " → " between tags (his arrow) |
| `TODAY_LABEL` | "today" |
| `HINT` | "The setups this stock passed through on his list, oldest first. Today's steps show the {n}-minute pass time (ET) …" (n = the variant's cadence) |
| `BORROWED_TEXT` | " On this tab the steps are 🚩 Gajjala's own reads and alerts (shared), before the audit." (🧪 only) |

## 4. Variants

| Page | Tracker | Claims merged | Hint |
|---|---|---|---|
| 🚩 Gajjala's (GG5) | `gajjala_potentials` | GG5's live claims | 5-minute |
| 1-minute (GG1) | its own `gajjala_1m_potentials` | its own live claims | 1-minute |
| 🧪 Audited (GGA) | GG5's (borrowed) | 🚩's live claims through `st.shared` (GGA's own claims are shadow — never merged); no `shared` → no merge | 5-minute + `BORROWED_TEXT` |

A 🧪 card held by the audit keeps `aplus_held` as its state while its tag can say "🎯 A+" — the split the sentence
states.

## 5. Known gaps

- **Pass-order window.** `run.py` writes the card's read (`upsert_read`), then claims + sends + settles the A+
  (`alerts.run_pass`), then writes the tracker (`potential.run_pass`). A GET between the read write and the claim
  settling shows an A+ pill with no A+ step yet; between the settle and the tracker write the merged claim already
  supplies it. Nothing is invented in that window (test-pinned).
- **Pass clock, not bar time.** A step's time is the pass that first saw it (≤ one cadence + the settle after the bar
  closed) — the same clock as the 📈 Track and the claim's `at`. `bar_t` (the bar's left edge) is not used.
- **A step can be missing:** a skipped pass, a host-sleep gap, or a pass that saw the break only as "stopped".
- **On-demand passes run DRY** (never write the tracker or a claim): a step seen only on-open shows at the next cron
  pass's time.
- **Live claims only:** a shadow or refused A+ is not merged (0 shadow rows in 6 sessions).
- **Setups that were only partial / invalid all session** have no tracker doc and no claim → not stages.
- **A fault looks like no history** (logged, not served).

## Measured before the build (read-only, api container, 2026-11-04 → 2026-11-11, 11-11 partial)

| | GG5 (🚩 5-min) | GG1 (1-min) |
|---|---|---|
| tracker docs (6 sessions) | 398 | 302 |
| A+ claim / refusal keys with NO tracker doc | 0 of 15 | 0 of 29 |
| live A+ that RANG with an A+ step in the folded path | 13 of 14 | 24 of 24 |
| … with the claim merge | 14 of 14 | 24 of 24 |
| tracker A+ clock == claim clock, where both exist | 13 of 13 | 24 of 24 |
| shadow A+ rows | 0 | 0 |
| raw `state_path` length p50 / p90 / max | 2–6 / 6–17 / 26 | 4–8 / 11–25 / 72 |
| steps per tag after the fold (n docs) | 1: 378 · 2: 7 · 3: 5 · 4: 7 · 8: 1 | 1: 271 · 2: 5 · 3: 4 · 4: 21 · 5: 1 |
| tags per card, the card's own session | 1: 203 · 2: 63 · 3: 19 · 4: 3 | 1: 105 · 2: 54 · 3: 15 · 4: 11 |
| tags per card over the 3-session window | max 11, 1–4 on 169 of 190 | max 9 |

Probe recipe (read-only; never during a heavy replay):

```bash
docker exec -i -w /app cheetah-market-app-api-1 python - < probe3.py
```

(`probe1.py` / `probe2.py` / `probe3.py` live in the 2026-11-11 session scratchpad `four/stages/`.)

## Goldens moved by design

Only an added `tiles[*].gajjala.stages` on cards whose symbol has a tracker doc or a rang live A+ in the window — no
tile moves, no other key moves (checked leaf by leaf with the engine on vs off: identity BOARD 520 stage leaves, 🧠
potential golden 167, on-open 62, 1-minute 92; 0 other leaves). Regenerated ONCE by the main session:
`gg5_board_2026_10_27.json`, `gajjala_potential_golden_2026_10_15.json`, `gajjala_on_open_golden_2026_10_15.json`,
`gajjala_1m_board_2026_10_27.json`. The GG5 WRITES golden must NOT move from this change (the pass is untouched).

## Tests

`backend/tests/test_gajjala_stages_2026_11_11.py` — the engine (stage_of, clock_of, fold, merge incl. the HUHU / PMAX
replicas, tag, sort with naive/aware first_seen, by_symbol, for_tile), the pins (MARKED_STATES, `_dow_md`, the card
pill's first word, imports), a real `potential.track` contract run, and the wiring on `tab.build`: 3 groups over the
window, the live-claim merge and its NEGATIVES (shadow / claimed / failed / `#` refusal), nothing invented (C6), O(1)
reads as a delta at 1 and 30 cards, no fetch, the span constant, nothing else moves on any sub, all-or-nothing assign,
every viewer, faults, 🏁 / 📓, GG1 / GGA, the 🧪 held A+.

## HIS CALL

0. Provenance — confirmed by the main session before the build.
1. **Span = the listing window** (today + 2 sessions). Alternatives: today + last session only, or
   `LEDGER_SPAN_SESSIONS` (5, the 🏁 picker).
2. **Sources = the 🧠 tracker + the live A+ alerts that rang.** Alternative A: tracker only (HUHU 11-05 would read
   "🧠 potential" though its A+ rang). Alternative B: also partial-only setups — needs a new per-pass write.
3. **Fold:** potential · A+ · triggered · stopped, repeats folded; building and trigger armed both "potential".
   Alternatives: "trigger armed" as its own step, or end each tag with its last state.
4. **🧪 shows 🚩's history** with one served sentence. Alternatives: no stages row on 🧪, or steps from the audit
   overlay (a new write).
5. **Clock = today only** ("time stamps if its same day"). Alternative: clocks on the card's own session even when it
   is not today.
6. **No cap; earlier sessions shown** (one card reached 11 tags). Alternative: fold earlier sessions behind one tap.
7. **Cards only** — the 🏁 and 📈 Track rows get no stages row.
8. **The title "🧭 Setup stages".** Alternative: "🧭 Stages".
9. **Tag words** match the card pill ("triggered"); the 📈 Track keeps "A+ (triggered)". Alternative: the long words in
   the tag too.
