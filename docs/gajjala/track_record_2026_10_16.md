# 🏁 Gajjala's Track record — every alert that rang, graded by GG's trade math (2026-10-16)

> 2026-10-16 (night): 🕰️ entries timeline + ⏪ replayed line — docs/gajjala/entry_timeline_2026_10_16.md.

Code: `backend/chart_maps/gajjala/ledger.py` (rows, grader, nightly step, today read, every served string), numbers in
`backend/chart_maps/gajjala/constants.py` (the `LEDGER_*` block), storage `gajjala_ledger` (`store.py`), the sub in
`tab.py`, the `span` param in `chart_maps/api.py`, the panel `TrackRecordPanel` in `frontend/src/components/GajjalaBoard.tsx`.
Spec: `BUILD_SPEC9.md` + `AMENDMENTS9.md` E1–E10 + `DECISIONS9.md` (scratchpad `gg_ledger/`). Contracts:
`frontend/scripts/contracts.mjs` "🏁 Gajjala track record (2026-10-16)". SPECS: "### Chart Maps — 🏁 Gajjala's Track
record". **UNMEASURED — a ledger of the alerts as sent, not a backtest and not a study. Not SEPA.**

> UPDATE 2026-10-16 (evening): A+ entries went live 2026-10-16; the 🧠 Track row shows "🎯 entry sent HH:MM ET"; the 🏁 ledger counts live A+
> entries as "🎯 A+ entry" on their own 🎯 line (`counts["entry"]`, `entries_text` — not pooled into the 🧠 %, AMENDMENTS10
> F3), shadow-period rows stay on the shadow line. Ajay's call ("you alert me when that happens"), not a
> measurement — docs/gajjala/entry_live_2026_10_16.md. The quoted words below are the 2026-10-16 morning build; W3 and
> W7 changed (see the note under the served-words table).

## The ask (Ajay, verbatim, 2026-10-16 ~11:20 ET)

> "also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To see a percentage and the ticker.
>
> We are not looking for winners just in time but when they got in to our alerts if they made it or not. Like XLAB today
> was a winner I made good money on it"

## His knob answers (verbatim)

| Knob | His answer | What it set |
|---|---|---|
| Win rule (~11:25 ET) | **"GG's trade math"** | entry = the alert's trigger; WIN = +1R (trigger − stop) before the stop; never triggered = no entry, listed, not counted; the % = the best move from the fill |
| Horizon (~11:25 ET) | **"Both columns"** | same session AND through the next session, side by side |
| Q0 (~13:00 ET) | **"Keep GG's math"** | the stop is a touch (`low ≤ stop`); +1R before the stop; the % shown = best move from the fill |
| Fill window (~13:10 ET) | **"From 09:45 ET only"** | fills count 09:45–16:00 ET only (09:30 + GG's `NO_TRADE_AFTER_OPEN_MIN`) |

## READ THIS FIRST — XLAB = three alerts, and the fill window decides them

XLAB rang **three** 🧠 alerts, not two (AMENDMENTS9 E2). By the rule as shipped (his four answers, the 09:45 window):

| Alert | Rang | Trigger / stop | Fill | +1R | Same session | Note |
|---|---|---|---|---|---|---|
| 2026-10-15 🌀 intraday_vcp | 15:11 ET (regular hours) | 1.22 / 1.16 | 15:21 @ 1.22 (same session) | 1.28 at 15:22 | **WIN** | next-session best ≈ +215% (high 3.8399 on 10-16) |
| 2026-10-16 ➖ horizontal_fade | 08:51 ET (pre-market) | 1.81 / 1.70 | 09:45 @ 1.89 | 2.00 at 09:49 | **WIN** | the golden: "WIN · best +103.2% so far" on the 11:11 read |
| 2026-10-16 🌀 intraday_vcp | 09:01 ET (pre-market) | 1.85 / 1.75 | 09:45 @ 1.89 | 1.99 at 09:48 | **WIN** | the golden: "WIN · best +103.2% so far" on the 11:11 read |

Under the other window — "any print 04:00–20:00" (BUILD_SPEC9's first draft) — the two 10-16 alerts would have been two
**LOSSES**: ➖ filled 08:52 @ 1.85 and was stopped 09:07 (low 1.69 under 1.70); 🌀 filled 09:18 @ 1.85 and was stopped
09:23 (low 1.75 = the stop, a touch counts). His "From 09:45 ET only" answer is what makes them wins; the stop rule did
not change.

What the alerts on file look like (read-only, 2026-10-16):
- **51 of 95** pushes on file rang outside regular hours — 32 after 16:00 on 10-15, 19 before 09:00 on 10-16. Every row
  carries its own chip: "rang pre" / "rang RTH" / "rang AH".
- **12 of 95** pushes had trigger = stop → state `no_risk` ("trigger = stop on the alert — no risk to size"), listed,
  never counted. **4 more** had R under 0.5% of the trigger → "thin R": graded, kept out of the headline %.
- The 2026-10-13 A+ shadow docs carry only `claimed_at` (no `at`) → the E3 fallback: alert time = `at` → else
  `claimed_at` → else the row is "no alert time" (not counted).
  > UPDATE 2026-10-16 (evening): a live A+ claim (since 2026-10-16) carries `at` (written with the claim).

## The rule (served as `rule_text`, verbatim from `ledger.rule_text()`)

> GG's trade math (your answer, 2026-10-16). Entry = the trigger the alert gave: the first 1-minute bar from 09:45 ET to
> 16:00 ET (your answer: from 09:45 ET only) that starts 30 s or more after the alert and trades at or above the trigger
> fills — at the trigger, or at that bar's open when it opened above it (a gap fills at the open). WIN = a later 1-minute
> high reaches the fill +1R (R = trigger − stop, as the alert gave them) before any low touches the stop. LOSS = the stop
> is touched first; a bar that touches both counts as a loss, and so does a stop touched in the fill minute. Same session
> = through 16:00 ET on the alert's day (an alert at or after 16:00 ET: through 16:00 ET of the next market day, its first
> regular session); through next session = the same walk to 16:00 ET of the market day after that, after-hours and
> pre-market prints included. The % is the best high after the fill against the fill; the small % is the column's last
> close against the fill. No entry and no plan are listed, never counted; a thin R (under 0.5% of the trigger) is graded
> and kept out of the %.

Every number in it is read from a constant: 09:45 = `LEDGER_FILL_FROM_ET` (built as `ET_RTH_OPEN` +
`NO_TRADE_AFTER_OPEN_MIN`, never typed), 16:00 = `LEDGER_FILL_TO_ET` / `ET_RTH_CLOSE`, 30 s = `BAR_SETTLE_SEC`, +1R =
`LEDGER_R_MULT` (`# Ajay 2026-10-16`), 0.5% = `LEDGER_MIN_R_PCT` (`# MINE`, HIS CALL Q16).

## Rows (what is graded)

- 🧠 live: every `gajjala_potentials` doc whose push RANG (`push.state` "pushed"). Joined / muted / never-pushed potentials
  are not rows — they never reached his phone. These rows are the headline %.
- A+ shadow: every `gajjala_alerts` claim in state shadow ("A+ shadow — never sent") — its own counts line, never in the %.
  > UPDATE 2026-10-16 (evening): A+ entries went live 2026-10-16; the 🧠 Track row shows "🎯 entry sent HH:MM ET"; the 🏁 ledger counts live A+
  > entries as "🎯 A+ entry" on their own 🎯 line (`counts["entry"]`, `entries_text` — not pooled into the 🧠 %, AMENDMENTS10
  > F3), shadow-period rows stay on the shadow line.
- One row per alert (`_id` `"{date}|{SYM}|{setup}|{kind}"`): XLAB = 3 rows over two days.

## The served words (verbatim from `ledger.py` / `tab.py`)

| # | Where | Exact text (`{…}` computed) |
|---|---|---|
| W1 | `TITLE` | `🏁 Track record — every Gajjala alert that rang, graded by GG's trade math · UNMEASURED` |
| W2a | `RULE_LABEL` | `ⓘ how each alert is graded` |
| W2 | `rule_text()` | the rule quoted above |
| W3 | `HONESTY` | `A ledger of the alerts as sent, graded by GG's own trade math — not a backtest of a strategy, and small n early. The A+ line was never sent (shadow) and stays out of the %. The 2026-10-14 study of the five setups read NULL — no edge over a matched placebo (docs/gajjala/study_2026_10_13.md); this record does not change that.` |
| W4 | counts, same | `Same session: {w} win(s) · {l} loss(es) · {p}% won · {ne} no entry · {o} open` + ` · {k} no plan` / ` · {k} no risk` / ` · {k} no alert time` / ` · {k} thin R (not in the %)` / ` · {k} not graded yet` (each when > 0) + ` · today not final` (a provisional cell); no win and no loss → `no graded entry yet` in place of `{p}% won` |
| W4n | counts, next | `Through next session: {w} win(s) · {l} loss(es) · {p}% won · {ne} no entry · {f} flat` + ` · {k} split` and the W4 extras |
| W5 | `shadow_text` | `A+ shadow (never sent, not in the %): same session {w} win(s) · {l} loss(es) · {p}% won · {ne} no entry · {o} open{extras}; through next session {w} win(s) · {l} loss(es) · {p}% won · {f} flat{extras}` — null when the span has no shadow row |
| W6 | `today_text` | `Today · through {HH:MM} ET · not final` (+ ` · {k} name(s) not read on this open — graded tonight 20:15 ET`); no read: `Today · not read on this open — graded tonight 20:15 ET` |
| W7 | `KIND_TEXT` | `🧠 live` · `A+ shadow — never sent` · `A+ live` |
| W8 | `at_text` | `{HH:MM} ET`, else `no alert time` |
| E1 | `RANG_TEXT` | `rang pre` · `rang RTH` · `rang AH` |
| E4 | `THIN_TEXT` | `thin R` |
| W9 | `plan_text` | filled: `trigger {T} → fill {F} at {when} · stop {S} · +1R {TG}`; not filled: `trigger {T} · stop {S}`; `NO_PLAN_TEXT` `no trigger or stop on the alert`; `NO_RISK_TEXT` `trigger = stop on the alert — no risk to size` |
| W9b | `note` | `trigger as first seen {first_seen_et} ET (the ring was {at_et} ET)` |
| W10 | cells | see "The state words" below |
| W11 | `HEADS` | Ticker · Setup · Alert · Kind · Trigger → fill · stop · Same session · Through next session |
| W12 | spans | `Today` · `Yesterday` · `Last 5 sessions` · `All` |
| W13 | day label | `{Dow} {YYYY-MM-DD}` (+ ` · today`) |
| W14 | `more_text` | `+{k} more rows — the counts above cover all {N}` |
| W15 | `empty_text` | `No Gajjala alert has rung yet this session.` · `No Gajjala alert rang on {date}.` · `No Gajjala alert rang in the last 5 sessions.` · `No Gajjala alert on file yet.` |
| W16 | `tab.TRACK_RECORD_FAULT` | `🏁 The alert record could not be read this time — the next re-read tries again.` |

> UPDATE 2026-10-16 (evening): A+ entries went live 2026-10-16; the 🧠 Track row shows "🎯 entry sent HH:MM ET"; the 🏁 ledger counts live A+
> entries as "🎯 A+ entry" on their own 🎯 line (`counts["entry"]`, `entries_text` — not pooled into the 🧠 %, AMENDMENTS10
> F3), shadow-period rows stay on the shadow line. W3 `HONESTY` is now: `A ledger of the alerts as sent,
> graded by GG's own trade math — not a backtest of a strategy, and small n early. A+ rows from the shadow period (never
> sent) stay out of the %; A+ entries sent live are counted on their own 🎯 line, not pooled with the 🧠 pushes — an A+
> exists only once the trade survived its entry bar. The 2026-10-14 study of the five setups read NULL — no edge over a
> matched placebo (docs/gajjala/study_2026_10_13.md); this record does not change that.` W5 `shadow_text` is unchanged
> (still true for the shadow-period rows). W7 `KIND_TEXT` is now `🧠 live` · `A+ shadow — never sent` · `🎯 A+ entry`.
> New: `entries_text` = `🎯 A+ entries sent (their own line, not pooled with the 🧠 %): same session … ; through next
> session …` (null when the span has no live A+ row).

## The state words (cells, `ledger._cell`)

| State | Cell text | Small text |
|---|---|---|
| `win` | `WIN · best {B}` | `+1R at {when} · close {C}` |
| `loss` | `LOSS · best {B}` | `stop at {when} · close {C}` (or `stop in the fill minute {when} · close {C}`) |
| `open` (same column) | `open · best {B}` | `close {C}` |
| `flat` (next column) | `flat · best {B}` | `close {C} at the {Dow MM-DD} close` |
| `no_entry` | `no entry` | `the trigger never traded 09:45–16:00 ET after the alert` |
| `no_plan` | `no plan` | — |
| `no_risk` | `no risk` | `trigger = stop on the alert — no risk to size` |
| `no_time` | `no alert time` | — |
| `split` | `split` | `split on {date} — not graded` |
| `pending` | `not graded yet` / `not read yet` / `after today's close` / `after {Dow MM-DD}'s close` | `graded nightly at 20:15 ET` / `graded tonight 20:15 ET` / `graded {Dow MM-DD} 20:15 ET` |
| provisional (today's read) | `WIN · best {B} so far` · `LOSS · best {B} so far` · `open · best {B} so far` · `no entry yet` | `+1R at {when} · not final` · `stop at {when} · not final` · `close {C} so far` · `not final` |

Counted in the %: `win` and `loss` only, live line only, 🧠 rows only — live A+ entries are counted on their own 🎯
line (counts["entry"], AMENDMENTS10 F3). Listed, never counted: no entry, open / flat, no plan, no risk, no alert time,
thin R, pending, split.

## The split guard

Prices across a split are not comparable, so no walk crosses one:
- A split between the alert day and a column's end → that column is `split` ("split on {date} — not graded").
- An after-close alert (E1) is graded on the next session's bars, so its SAME column is guarded over (alert day, same
  session]; the today read holds such a name out ("not read on this open — graded tonight") unless the split check
  answers "no split".
- A trade already decided (win / loss) in the same session keeps its outcome in the next column, with its best and
  close kept through the same session (the small text says so).
- An unread split check leaves the column absent — retried the next night, never graded on rescaled bars.

## Cost

- Nightly (`grade`, the LAST step of the existing 20:15 ET `chart_maps.gajjala.nightly` line — no new crontab line):
  re-reads the last `LEDGER_GRADE_LOOKBACK_SESSIONS` 10 market days; at most `LEDGER_BACKFILL_MAX_SYMBOL_DAYS` 120
  symbol-day 1-minute loads a run (completed days come from `intraday_cache`; the rest wait a night as "not graded
  yet"); one split lookup per name; each row in its own try. A column is written only once its horizon has ended.
- On open (🏁 only — the one Gajjala GET that fetches bars): at most `LEDGER_TODAY_MAX` 60 names, one
  `load_intraday(…, force=True)` each, `LEDGER_TODAY_BUDGET_SEC` 15 s from the start, memo `LEDGER_TODAY_MEMO_SEC` 300 s
  per (session, symbol); never writes. Every other sub stays Mongo-only.

## Verification recipe (no comment lines in any shell block)

Backend, hermetic, the api image:

```bash
docker run --rm --network none --name cheetah-tmp-pytest-gl-check -v /Users/ajay/clinet-test/wt-ggledger:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_ledger.py tests/test_gajjala_ledger_pins.py tests/test_gajjala_store.py tests/test_gajjala_nightly.py tests/test_gajjala_potential.py tests/test_gajjala_constants.py tests/test_gajjala_tab.py tests/test_gajjala_track_record_tab.py tests/test_gajjala_potential_tab.py tests/test_gajjala_on_open.py tests/test_gajjala_source_guard.py
```

Frontend:

```bash
cd /Users/ajay/clinet-test/wt-ggledger/frontend && rtk proxy npx vitest run --reporter=dot && rtk proxy npx tsc --noEmit -p tsconfig.json && rtk proxy node scripts/contracts.mjs
```

Throwaway api on :8005, the live DB, read-only (the doji recipe with the name `cheetah-tmp-gl-api`, the ggledger mount,
and the on-open scan stubbed so the preview's mount POST never starts a pass):

```bash
cd /Users/ajay/clinet-test/cheetah-market-app
docker rm -f cheetah-tmp-gl-api >/dev/null 2>&1 || true
docker compose run -d --rm --no-deps --name cheetah-tmp-gl-api -p 127.0.0.1:8005:8000 -e PYTHONDONTWRITEBYTECODE=1 -e MASSIVE_WS_ENABLED=false -e FINNHUB_POLLER_ENABLED=false -e MAC_OUTBOX_POLL_MS=3600000 -v /Users/ajay/clinet-test/wt-ggledger/backend:/app api python -c 'import push.mac_stream as m; m._drain_started = True; import chart_maps.gajjala.on_demand as od; od.request = lambda *a, **k: {"state": "refused", "text": "throwaway api — no scan on open"}; import uvicorn; uvicorn.run("main:app", host="0.0.0.0", port=8000)' >/dev/null
n=0; until [ $n -ge 24 ]; do code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8005/health" 2>/dev/null || true); [ "$code" = "200" ] && break; n=$((n+1)); sleep 5; done; echo "health=$code"
```

Read it (the first call fetches today's 1-minute bars for today's alerted names; the second within 5 minutes is the memo):

```bash
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.gajjala_ledger.countDocuments({})'
curl -s -o /tmp/gl_5d.json -w '%{time_total}\n' -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8005/chart-maps/gajjala?sub=track_record&span=5d"
python3 -c 'import json; b=json.load(open("/tmp/gl_5d.json"))["track_record"]; print(b["counts_text"]); print(b["shadow_text"]); print(b["today_text"]); [print(d["date"], r["symbol"], r["setup"], r["at_text"], r.get("rang_text"), r["plan_text"], "|", r["same"]["text"], "|", r["next"]["text"]) for d in b["days"] for r in d["rows"] if r["symbol"] == "XLAB"]'
curl -s -o /dev/null -w '%{time_total}\n' -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8005/chart-maps/gajjala?sub=track_record&span=5d"
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.gajjala_ledger.countDocuments({})'
docker logs cheetah-tmp-gl-api 2>&1 | grep -i "traceback\|error" | head
```

Expect the three XLAB rows of READ THIS FIRST (10-16 cells "… so far · not final" until tonight's grade), the ledger
count unchanged by the GETs.

His surface: the Vite preview `ggledger-frontend-8005` on :5177 (proxy `/api` → `http://localhost:8005` with the owner
header, `/api/features/*` and `/api/usage/*` bypassed so the preview never marks his ✨ seen) →
`/chart-maps?tab=gajjala&sub=track_record`: 🏁 chip last, the span buttons, the counts lines, the XLAB rows with their
"rang pre" / "rang RTH" chips. Cleanup by exact name only:

```bash
docker rm -f cheetah-tmp-gl-api
```

## HIS CALLS (each ships with the default shown; nothing here is decided for him)

- **Q0 — answered.** He kept GG's math ("Keep GG's math": touch = stop, +1R before the stop, the % = best move from the
  fill) AND chose the 09:45 window ("From 09:45 ET only") → **XLAB = 3 WINS** (10-15 🌀 15:11, 10-16 ➖ 08:51, 10-16 🌀
  09:01). Still open if he wants it: (a) the stop counts only when price trades UNDER it (the detectors' own rule);
  (b) a 2R / 3R target; (c) lead with the best % and show win / loss second.
- Q1 Scope: the 🧠 pushes that reached his phone are the rows and the %; A+ is a separate "shadow — never sent" line
  (DEFAULT). Alternatives: drop the shadow line; count every first sighting (muted / joined) too.
  > UPDATE 2026-10-16 (evening): A+ entries went live 2026-10-16; the 🧠 Track row shows "🎯 entry sent HH:MM ET"; the 🏁 ledger counts live A+
  > entries as "🎯 A+ entry" on their own 🎯 line (`counts["entry"]`, `entries_text` — not pooled into the 🧠 %, AMENDMENTS10
  > F3), shadow-period rows stay on the shadow line. Pool vs own line = HIS CALL Q4 of
  > docs/gajjala/entry_live_2026_10_16.md.
- Q2 The "today so far" read: on opening 🏁, one 1-minute fetch per name alerted today (≤ 60, 15 s budget, 5-minute
  memo, never written) — the only Gajjala GET that fetches bars (DEFAULT). Alternatives: grade inside the 5-minute pass
  from the bars it already loaded; no live read (graded at 20:15 only); extend it to yesterday's next-session column.
- Q3 A bar opening above the trigger fills at its open (+1R stays trigger − stop) — DEFAULT; vs fill at the trigger always.
- Q4 Ties: a bar touching both +1R and the stop = LOSS; a stop touched in the fill minute = LOSS; a touch of the stop
  (≤) = LOSS; a touch of the trigger (≥) fills (DEFAULT); vs "through" on both (> / <).
- Q5 — answered by "From 09:45 ET only": fills count 09:45–16:00 ET. Open: an alert at or after 16:00 ET uses the NEXT
  session as its same-session column (DEFAULT, MINE — item (e) below).
- Q6 Nightly limits: re-reads 10 market days, at most 120 symbol-day loads a night (AMENDMENTS9 E9; the rest wait a
  night) — MINE.
- Q7 The name and slot: "🏁 Track record", the LAST (10th) sub — MINE.
- Q8 "open" / "flat" rows stay out of the % (DEFAULT); vs counted as half / as a loss.
- Q9 The day picker: Today · Yesterday · Last 5 sessions · All, default **Last 5 sessions** (AMENDMENTS9 E2, so
  yesterday's XLAB alert sits beside today's) — MINE.
- Q10 The best % runs through the column's end even after a LOSS (DEFAULT); vs stop at the exit (stored already — a
  display flip, no re-grade).
- Q11 After-hours and pre-market prints are inside the next-session walk (DEFAULT); vs regular-session prints only.
- Q12 A fill after the structure died (the card says invalid) still counts (DEFAULT); vs no entry.
- Q13 Counted per alert (XLAB = 3 rows over two days, DEFAULT); vs per ticker per day (the first alert only).
- Q14 A push that reached no device (`no_target`) or failed is not a row (DEFAULT).
- Q15 The next-session column ends at the next market day's 16:00 ET (DEFAULT); vs a fixed N-minute / N-session window.
- **Q16 The R floor** (AMENDMENTS9 E4, MINE): R under `LEDGER_MIN_R_PCT` 0.5% of the trigger = "thin R" — graded,
  shown with the chip, kept out of the headline % (4 of the 95 pushes on file). Alternatives: count them; drop the floor; a
  different floor.

Carried from the critics (defaults as shipped):
- (a) A stop touched BEFORE the 09:45 fill does not make the row "no entry" — the walk starts at the fill. His call
  whether a pre-window stop touch should void the entry.
- (b) A decided same column (win / loss) is walked again for the next column — the trade is copied, only the best %
  and the close run on to the next session's end.
- (c) The counts line has no 'split' key for the same column: a split same column shows on its row only (the next
  column's counts line carries ` · {k} split`).
- (d) The 🏁 chip count = today's rows graded so far (`ledger.count_today`); None (no count) on a tracker read fault.
- (e) After-hours alerts (rang at or after 16:00 ET) use the next session as their same-session column, and the
  session after that as their next-session column.

## 🎯 A+ filter + the win/loss charts (2026-10-26)

BUILD_SPEC25 (+ AMENDMENT A1). Ajay, verbatim (the double space after "a" is his):

- 2026-10-26 ~20:30 ET: "Once done can you give me a  A+ filter in the track record I wanna see how many of the A+ were successful draw some charts to show the winning vs losing percentages of A+ trades please"
- 2026-10-26 ~20:55 ET: "I need these charts on Track Record page" — this ANSWERS H2: the 🎯 A+ block and its three
  charts are drawn on the 🏁 list view ALWAYS (filter on or off) whenever `track_record.aplus` is served. The 🕰️
  timeline view draws none of it.

**UNMEASURED.** A ledger of the A+ alerts graded by GG's own trade math, not a backtest. The 2026-10-14 study of the
five setups read NULL — no edge over a matched placebo (`docs/gajjala/study_2026_10_13.md`); this block does not
change that. Small n: 28 decided (same session, 10d, 2026-10-26) — a 95% interval is roughly 39%–73%.

What is served (`ledger.served_block`, the GET never carries `kind`; `tab.py` / `api.py` unchanged):

- `kinds` — the two chips 📋 every alert · 🎯 A+ only, the ROW count inside the served text (`_kind_text`; ⏪ replayed
  rows counted apart " +r ⏪" on "all"), never a %. `kind_param` = `kind`; `kind_empty_text`.
- `categories_aplus` — the ✅ / ❌ chips over the A+ rows only (`_categories`), printed while 🎯 is on.
- `aplus` — always served: `title`, `total`, `n_sent`, `n_shadow`, the **pooled** `counts` (sent + shadow-period A+,
  one %, tallied by the headline's own thin rule `_tally_into`; % = `_win_pct`), `counts_text` (lead
  `APLUS_LEADS`), `split_text`, `replayed_note`, `more_text`, `empty_text`, `honesty`, `horizons`, `horizon_default`,
  `charts`, and its OWN rows `days`.
- The 🧠 headline (`counts`, `counts_text`, the shadow / entries / ⏪ lines, `days`, `categories`) is byte-identical to
  4d4058c9 (`PRE_SHA` in `tests/test_gajjala_aplus_filter_2026_10_26.py`); the golden regen was proved additive.

What each chart shows (every label, number and % in them is served; the browser only sizes rectangles):

- **🎯 A+ wins vs losses** (`outcomes`) — one bar per horizon (Same session · Through next session). A bar spans EVERY
  A+ row of the span (wins, losses, open / flat, no entry, other); its % is of the **decided** rows only (wins /
  (wins + losses)); `loss_pct` = 100 − pct (one rounding). No entry, open, flat, no risk, thin R and not graded yet are
  listed in the legend, never in the %.
- **By setup** (`by_setup`) — one bar per setup that has an A+ row, in `GC.SETUPS` order (never ordered by %), all bars
  on one scale (the largest served total of the picked horizon).
- **By alert day** (`by_day`) — one column per alert day, oldest first (a time axis), inside its own scroll box.
- One served horizon toggle (default `same`) switches by setup + by alert day; local state, never the URL, no fetch.
- A same-session `split` A+ is in no same count (the existing rule, carried item (c)) — that bar's `total` can be one
  under the row count; `total` = Σ the counts by design.

The served words (frozen in `ledger.py`, beside the ✅ / ❌ block):

| Name | Served text |
|---|---|
| `KIND_PARAM` | `kind` |
| `KIND_KEYS` | `all` · `aplus` (first = off) |
| `KIND_LABELS` | 📋 every alert · 🎯 A+ only |
| `KIND_EMPTY_TEXT` | No 🎯 A+ alert on this span. |
| `APLUS_LINES` | `live` · `shadow` (⏪ `replayed` out) |
| `APLUS_TITLE` | 🎯 A+ only — every A+ alert, sent or shadow, graded by GG's trade math · UNMEASURED |
| `APLUS_LEADS` | A+ same session · A+ through next session |
| `APLUS_SENT_TEXT` | {n} sent to your phone |
| `APLUS_SHADOW_TEXT` | {n} from the shadow period (never sent) |
| `APLUS_REPLAYED_NOTE` | ⏪ Replayed rows are not in the 🎯 A+ filter, its counts or its charts — they never rang. |
| `APLUS_HONESTY` | Pooled: the A+ alerts sent to your phone and the shadow-period A+ (never sent) in one %, on its own line — the 🧠 headline % is unchanged. An A+ exists only once the trade survived its entry bar. Small n, a ledger graded by GG's own trade math — not a backtest of a strategy. The 2026-10-14 study of the five setups read NULL — no edge over a matched placebo (docs/gajjala/study_2026_10_13.md); this record does not change that. |
| `APLUS_CHART_TITLES` | 🎯 A+ wins vs losses · By setup · By alert day |
| `APLUS_ITEM_LABELS` | wins · losses · open · flat · no entry · other |
| `NO_DECIDED_TEXT` | no graded entry yet |

Horizon labels = `dict(HEADS)` (never retyped). The honesty sentence is folded under the ⓘ glyph (A1.2) because the
block now sits on the page in every state.

**The `aplus.days` cap.** On 10d the main list hits `LEDGER_ROWS_MAX` (400, MINE) inside 10-15, so a filter over
`days` alone would drop 12 of the 42 A+ rows of 2026-10-26. `aplus.days` is the A+ rows grouped by the same
`_group_days` and cut by the same cap on their own — 42 fit; when rows are cut `more_text` says
"+k more A+ rows — the counts above cover all N". The counts and the charts always cover every A+ row of the span.

The served read on the live DB, 2026-10-26 ~20:25 ET, span 10d (the served rule; expect it until the 10-27 20:15 grade
moves NCPL / AUID, both rang after hours and are `pending`):

- 42 A+ rows — 22 sent to your phone · 20 from the shadow period (never sent).
- Same session 16 wins · 12 losses · 57% won · 7 no entry · 2 open · 1 no risk · 2 thin R (not in the %) · 2 not
  graded yet. Through next session 17 – 13, 57%.
- Raw Mongo reads 16 W / 14 L — the two thin-R rows (GP 10-16 💋 shadow, AMRO 10-19 🌀 live, both losses) are out of the
  % by the existing rule (Q16). Never quote 53%.

Verification recipe (no comment lines in any shell block). Backend, hermetic:

```bash
/usr/bin/find /Users/ajay/clinet-test/wt-ggaplus/backend -name __pycache__ -type d -prune -exec rm -rf {} +
docker run --rm --network none --name cheetah-tmp-pytest-ap -v /Users/ajay/clinet-test/wt-ggaplus:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_aplus_filter_2026_10_26.py tests/test_gajjala_ledger.py tests/test_gajjala_ledger_categories.py tests/test_gajjala_ledger_replay.py tests/test_gajjala_ledger_pins.py tests/test_gajjala_broker_flags.py tests/test_gajjala_entry_tape.py tests/test_gajjala_tab.py tests/test_gajjala_source_guard.py tests/test_gajjala_track_record_tab.py
```

Frontend:

```bash
cd /Users/ajay/clinet-test/wt-ggaplus/frontend && rtk proxy npx vitest run --reporter=dot && rtk proxy npx tsc --noEmit -p . && rtk proxy node scripts/contracts.mjs
```

Throwaway api on :8005, the live DB, read-only, outside RTH (the 🏁 GET fetches today's 1-minute bars):

```bash
cd /Users/ajay/clinet-test/cheetah-market-app
docker rm -f cheetah-tmp-ap-api >/dev/null 2>&1 || true
docker compose run -d --rm --no-deps --name cheetah-tmp-ap-api -p 127.0.0.1:8005:8000 -e PYTHONDONTWRITEBYTECODE=1 -e MASSIVE_WS_ENABLED=false -e FINNHUB_POLLER_ENABLED=false -e MAC_OUTBOX_POLL_MS=3600000 -v /Users/ajay/clinet-test/wt-ggaplus/backend:/app api python -c 'import push.mac_stream as m; m._drain_started = True; import chart_maps.gajjala.on_demand as od; od.request = lambda *a, **k: {"state": "refused", "text": "throwaway api — no scan on open"}; import uvicorn; uvicorn.run("main:app", host="0.0.0.0", port=8000)' >/dev/null
n=0; until [ $n -ge 24 ]; do code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8005/health" 2>/dev/null || true); [ "$code" = "200" ] && break; n=$((n+1)); sleep 5; done; echo "health=$code"
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.gajjala_ledger.countDocuments({})'
curl -s -o /tmp/ap_10d.json -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8005/chart-maps/gajjala?sub=track_record&span=10d"
curl -s -o /tmp/ap_5d.json -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8005/chart-maps/gajjala?sub=track_record&span=5d"
curl -s -o /tmp/ap_all.json -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8005/chart-maps/gajjala?sub=track_record&span=all"
python3 - /tmp/ap_10d.json /tmp/ap_5d.json /tmp/ap_all.json <<'EOF'
import json, sys
for p in sys.argv[1:]:
    tr = json.load(open(p))["track_record"]
    ap = tr["aplus"]
    print(p, [k["text"] for k in tr["kinds"]])
    print(" ", ap["counts_text"], "|", ap["split_text"])
    for h in ("same", "next"):
        for k, v in ap["counts"][h].items():
            if k != "pct":
                assert v == tr["counts"]["shadow"][h].get(k, 0) + tr["counts"]["entry"][h].get(k, 0), (p, h, k)
    rows = [r for d in ap["days"] for r in d["rows"]]
    assert tr["kinds"][1]["n"] == len(rows), p
    assert not [r for r in rows if r["id"].startswith("REPLAY:")], p
    ch = {c["key"]: c for c in ap["charts"]}
    for h in ("same", "next"):
        o = next(b for b in ch["outcomes"]["bars"] if b["key"] == h) if ch else None
        if o:
            for name, groups in (("by_setup", ch["by_setup"]["rows"]), ("by_day", ch["by_day"]["cols"])):
                for k in ("win", "loss"):
                    got = sum(i["n"] for g in groups for i in g[h]["items"] if i["key"] == k)
                    want = sum(i["n"] for i in o["items"] if i["key"] == k)
                    assert got == want, (p, name, h, k, got, want)
    print("  ok")
EOF
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.gajjala_ledger.countDocuments({})'
```

Expect the 2026-10-26 read above until the 10-27 grade; the ledger count unchanged by the GETs. His surface: the
worktree Vite preview on :5174 (`/api` → :8005, `/api/features/*` + `/api/usage/*` bypassed so his ✨ stays unseen) at
430 px → `/chart-maps?tab=gajjala&sub=track_record&span=10d`: the A+ block and its three charts under the today line
with the filter off; tap 🎯 A+ only → zero new GETs, 42 rows, the 🧠 lines hide; ∧ ❌ losers composes; only the
by-day chart scrolls inside itself. Cleanup by exact name only:

```bash
docker rm -f cheetah-tmp-ap-api
```

HIS CALLS (defaults shipped; nothing decided for him):

- **H2 — ANSWERED** 2026-10-26 ~20:55 ET, "I need these charts on Track Record page": the block + charts are drawn
  ALWAYS on the list view (A1), not only while 🎯 is on. Rule #5: on a phone that is about two screens of charts before
  the first day table — fold behind the 🎯 chip vs always = his to flip back.
- H1 Pool sent + shadow in the A+ % (DEFAULT) vs sent-only. 10d same, 2026-10-26: pooled 16–12 **57%** · sent 10–5
  **67%** · shadow 6–7 **46%** (the 🎯 entries + shadow lines keep showing the split).
- H3 Three charts (DEFAULT) vs fewer / more; by setup + by alert day one horizon at a time via the served toggle,
  default "same" (MINE) vs both side by side.
- H4 The % = wins / (wins + losses); open, flat, no entry, no risk, not graded yet listed, never in it (existing
  rule); the outcome bar spans EVERY A+ row while its % is of the decided ones.
- H5 ⏪ replayed rows out of the filter, counts and charts (DEFAULT) vs a third chip.
- H6 Thin R out of the % (existing Q16): 2 of the 42 (GP 10-16, AMRO 10-19 — both losses); counting them → same
  16–14 (53%).
- H7 A per-ticker drill later (not built).
- H8 A 95% interval beside the % (not built; 16 of 28 → about 39%–73%).
- H9 Rule #5: three 📋 chip rows now stack (views / kinds / cats) — fold "🎯 A+ only" into the views toggle as a third
  view instead?
- H10 The 🧠 headline lines, the ⏪ lines and the list's "+N more rows" hide while 🎯 is on (DEFAULT, the timeline's
  precedent) vs kept.
- H11 The 🕰️ timeline ignores `kind` — it already lists A+ only, ⏪ included (DEFAULT).
- H12 `LEDGER_ROWS_MAX` 400 (MINE) cuts the oldest rows of the unfiltered list and the 🕰️ timeline on 10d / all; the A+
  list is not cut (`aplus.days`). Exempt A+ / raise the cap = his call.
- H13 Wording "📋 every alert" / "🎯 A+ only" / "🎯 A+ wins vs losses" / "By alert day" / "{w}W {l}L" (MINE).

## ✅ wins first + row flags (2026-10-27)

Ajay, verbatim (his spelling kept), 2026-10-27 ~17:45 ET: "Can you sort the winds in Gajjals I can't seem to tell the difference in that tab or show some greed flags on the wins rows". This ANSWERS HIS CALL Q11 above (AMENDMENTS11 F13 —
the hidden per-row chip — was the planner's default, not his).

What is served (`ledger.served_block`; the GET never carries `sort` on the 🏁 sub; `tab.py` / the route unchanged):

- each row: `flag_text` = `BUCKET_TEXT[bucket]` ("✅ winner" / "❌ loser") on the rows whose bucket is in
  `FLAG_BUCKETS` (`win`, `loss`); `None` on every other row. `bucket` / `bucket_text` are unchanged.
- the block: `sorts` = one chip per `SORT_KEYS` key — `{"key", "label", "bucket_sort"}` (`SORT_LABELS`: ✅ wins first ·
  🕰️ as rang; `SORT_BY_BUCKET`: only "wins" sorts); `sort_param` = `SORT_PARAM` ("sort" — the board's own URL param; a
  sub click drops it); `sort_default` = `SORT_KEYS[0]` = "wins" (his ask: the wins on top); `bucket_order` = `BUCKETS`
  (win · loss · open · flat · out) — the order the FE sorts by.
- the server NEVER reorders a row: the ledger stays chronological, as rang (the golden pins an "out" row before a win on
  2026-10-16 — `tests/test_gajjala_track_record_sort_2026_10_27.py`). The 1-minute page serves the same block
  (`_variant_words` leaves it alone).

What the FE does (`lib/gajjala.ts` `ggTrSort` / `ggSortRows` / `ggTrRowClass`; `GajjalaBoard.tsx` `GgTrSorts`):

- the chip in force = the URL `sort` when it is a served key, else the chip whose key is the served default; no served
  chips (an older API) → no chip row and the served order. The FE types no sort key — the served `bucket_sort` boolean
  decides whether a chip sorts.
- a bucket sort = a STABLE sort of each served day's rows by the row's served `bucket` position in `bucket_order` (a
  missing / unknown bucket sinks last; the served order is kept inside a bucket). The day grouping, the counts, the
  categories and the 🎯 A+ chips never change; the ❌ loss sub-line stays glued under its row. The 🕰️ timeline sorts
  the same way.
- a chip click rewrites the URL only (`sort=rang`; the default clears the param) — `sort` never rides the 🏁 GET, so a
  click fetches nothing. Every other sub keeps its served tile sort on the query.
- the row: `className="gg-tr-row gg-tr-row-<bucket>"` (a CSS hook — `gajjala.css` tints win green with a green left
  edge, loss red); the flag: `<span class="gg-tr-flag gg-tr-flag-<bucket>" data-testid="gg-tr-flag-<key>">` right after
  the ticker, the served text only.
- the Auto-Pilot 🚩 lane rows (`GajjalaLaneTab.tsx`) take the same tint from the SIGN of their served `pnl_usd` on
  CLOSED rows only (`data-outcome` win / loss); an open row, a flat close or a row without a number carries none.

HIS CALLS (defaults built): wins first is the DEFAULT on every 🏁 open (vs as rang by default with the chip to flip);
the flag words are the served `BUCKET_TEXT` ("✅ winner" / "❌ loser", the same words as the category chips) rather than
a 🟢 glyph; the loss rows are tinted red too (he asked for green on wins only — the red makes "the difference" he could
not tell); the tint is a translucent wash so dark mode keeps it; open / flat / out rows stay untinted; the lane tab
tints CLOSED rows only.

Tests: BE `tests/test_gajjala_track_record_sort_2026_10_27.py` (words frozen + exported, the block, win / loss flags
only — NEGATIVE: no flag elsewhere, NEGATIVE: the server never reorders, the 1-minute variant keeps the block, kinds /
categories / heads untouched); FE `GajjalaBoard.wins_sort.test.tsx` (chips, default in force, the order, the flags,
the glued loss line, ONE GET without `sort`; the 🕰️ click → served order, `?sort=rang`, no refetch; NEGATIVE: an unknown
`?sort` → the default; NEGATIVE: no served chips → no chips + served order; NEGATIVE: a default naming no chip; the
category filter composes; the three helpers' edge cases), `GajjalaBoard.track_record.test.tsx` (the golden's rows draw
their served flags; the order = the served order under the served default chip), `GajjalaLaneTab.test.tsx` (the tint;
NEGATIVE: open / flat / number-less rows). Goldens regenerated (`GG_WRITE_GOLDEN=1`: the 🏁 golden, the 1-minute golden,
the GG5 identity fixtures) because the served block gained keys. ✨ `chart-maps-gajjala-wins-sort-flags-2026-10-27`
(FIRST). Contracts: "✅ wins first + row flags on the 🏁 Track record (2026-10-27)". UNMEASURED — a tint and an order,
not a read.
