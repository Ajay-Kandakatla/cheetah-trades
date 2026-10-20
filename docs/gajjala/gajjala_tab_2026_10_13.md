# 🚩 Gajjala's tab — the method, the endpoint, the 📓 Playbook and the ℹ️ panel (WP5a, 2026-10-13)

Ajay 2026-10-13: *"Name the Tab Gajjala's he has multiple strategies..around this. He is volume and price action based
traded with short squeeze. He also has premarket and post market analysis."* and *"Implement his full stategy do not assume
anything."*

**UNMEASURED.** Nothing on this tab is a measured edge. His own 2023 numbers give −0.11% per trade for the full year and
+0.76% for the second half (computed from HIS TraderSync figures, `verified_rules.json`); on 2024-10-11 he wrote that he no
longer sees his setups for long stretches and their probability "drastically reduced". Nothing here trades, enters a lane or
sizes a position. Not SEPA: no other method's gate, import or citation (source guard).

Binding order used: DECISIONS "ROUND A/B/C ANSWERS" > FIRST_HAND (his words) > BUILD_SPEC §3/§4 > STRATEGY_SPEC deltas.

## Sources
| Key | What | Used for |
|---|---|---|
| S8 | IBD Northern Virginia webinar, `CI7mNvEQyms` (FIRST_HAND Part 1) | his words, timestamps |
| S9 | TraderLion podcast, `10pHBNVi4Jc` (FIRST_HAND Part 2; 1:54:46–2:02:40 is HERE, not S8) | his words, timestamps |
| S11 | his X posts | 0.25% start risk, red closes, "mostly pass", $0.10 floor, decay |
| S1 | the substack link Ajay gave — a THIRD-PARTY write-up | nothing is taken from it; its claims that his own words contradict are listed |
| S1–S18 | the verified set (`backend/chart_maps/gajjala/verified_rules.json`, WP7) | the 📓 sources table + "Contradicted / not used" |

The FIRST_HAND notes are committed as `backend/tests/fixtures/gajjala/first_hand_2026_10_13.md` (byte copy) so the tests
can prove every served quote is his.

## The five setups (5-minute bars; the Fade 15-minute first) and his common rule
"good demand, very shallow pullback with low volume … if it takes the previous highs — enter; stop loss would be the low of
the base" (S8 34:45). Entry = the break of the prior bar's high; stop = that bar's / the base's low.

| Sub | His words | Numbers (all in `constants.py`) |
|---|---|---|
| 🚩 Bull Flag | S8 21:45–24:37, S9 1:59:24 | leg ≥ `BF_LEG_MIN_BARS` (his 2); pullback `K4_BF_PULL_MIN`–`K4_BF_PULL_MAX`; up to `K4_BF_LONG_FLAG_MAX` = "long flag" (K4a, never A+). WIDENED 2026-10-18 (DECISIONS13 D1): pullback 1–5 = A+, > 5 invalid; `K4_BF_LONG_FLAG_MAX` None = the "long flag" band is empty |
| 💋 EMA Kiss & Fly | S8 31:33–32:41, S9 1:55:28 | `K5_*`; every pullback close ≥ 9 EMA (K5a); ≤ `K4_KF_PULL_MAX`; no kiss = "near-kiss" (never A+) |
| ➖ Horizontal Fade | S8 32:49–33:50, 1:20:08, S9 1:56:08 (1:57:33 is HIS Fade line, not a VCP rule) | `K6_*`, base `K4_HF_BASE_MIN`–`MAX`, trigger = the base high (round C) |
| 🌀 Intraday VCP | S8 33:50–34:37 | `K7_*`, ≥ `K4_VCP_MIN_CYCLES`; one miss of two = "B — imperfect" (round C, never pushed) |
| 🎾 Reversal Squeeze | S8 35:02–35:56, 36:12; S9 2:00:32–2:02:40 | `K8_*`, H1 2/8, H2 distinct, H4 ≥1 bar; float ≤ `K8_MAX_FLOAT` |
| ☀️ Premarket | S8 13:21–14:34, 1:21:56, 1:23:30 | K9 — WP2 `context.premarket_list` |
| 🌙 Post-market | S8 1:26:48, 59:24, S9 1:16:13 | K10 — WP2 `context.postmarket_confirm` (rows stored by the pass) |
| 📓 Playbook | everything above + management, risk, avoids | text only |

H1–H5 are answered (DECISIONS round C) and written in `constants.py`; any constant set back to None prints "waiting for your
number (Hn)" on the ℹ️ panel, the knob table and the board's `awaiting[]` — never "None".

## States (served label; every one says UNMEASURED)
`aplus` "A+ — every rule met, entry bar closed" · `triggered` "triggered n bars ago" · `forming` (ready: "the next bar over
X") · `partial` ("partial — missed: …", or "broke — not A+ · missed: …" / "· not judgeable: 9 EMA warming up", HIS CALL 21) ·
`stopped` · `invalid` / `none` = counted, never tiled. Variant / grade pills: "long flag", "near-kiss", "B — imperfect".
WIDENED 2026-10-18 (DECISIONS13 D1): the "long flag" pill no longer occurs under the shipped setting (band empty while
`K4_BF_LONG_FLAG_MAX` is None; 4–5 bar flags read A+); the pill word stays for a configured band and older payloads.

### ℹ️ The served legend — `counts_legend` (2026-10-18, DECISIONS15 D1)

Ajay 2026-10-18, verbatim: "Ok Forming is still Criteria not met.. Potential is all the gajjalas criteria met. may be add
an info tag for them explicitly.. To tell me what athey are". Both readings are the other way round: "forming" = no rule
has failed yet ("criteria not met" is **partial**), and "potential" = forming + the quiet base begun + the plain setup
("all criteria met" is **A+**). Every board payload now serves `counts_legend: [{key, word, text}]` from
`tab.count_legend()` (keys `LEGEND_KEYS` = the seven `COUNT_STATES` + `awaiting_answer`, `listed`, `potential`, `track`,
in that order), and `subs[].title` = the potential row's text on the 🧠 sub (None on the other nine). The FE prints these
words as hover titles and ONE folded ⓘ under the counts line — it types no definition. Words only: `COUNT_STATES` and the
served `counts` are unchanged; no methodology change.

| word | means — verbatim (generated from tab.count_legend(); keep in sync) |
|---|---|
| A+ | every rule of the setup met and the bar that traded through the trigger closed on the name's latest closed bar at the pass; it rings only when that bar is fresh and inside the A+ window, once per name and setup a day |
| forming | no rule has failed yet and the break has not printed — “ready” means the next bar over the trigger would be the entry |
| partial | a rule failed — the card says which (“missed: …”); a break that was not A+ reads here too |
| triggered | every rule met and the break printed earlier — the entry has passed; the stop has not printed |
| stopped | the break printed and then the stop printed |
| invalid | the structure died — the entry bar traded under the stop first, too many pullback bars, the base broke, or the trigger would equal the stop (a reference bar with no range — no risk) |
| none | no structure of this setup on the bars, or a judged read blanked by the 🎾 float rule or an unknown float, or a detector error |
| awaiting your number | held by a rule whose number you have not given |
| listed | the names his scanner listed for the session — every count above is read on these |
| 🧠 Potential | 🧠 Potential = a setup read still forming — the setup's own rules decide forming vs partial — with its quiet sideways part begun (“building”) or complete (“trigger armed”), and the reclaim of the highs not yet printed. The base must hold at least one sideways bar — a demand leg alone is not a potential (Cheetah default, not his). Counted per symbol, not per setup. |
| 📈 Track | every symbol-and-setup that was a potential at any point that session, with what became of it since — a record, not a list to act on |

Under the shipped settings. The 🧠 Potential row's middle sentence is `potential.defaults_clauses()[0]`'s base clause and follows `POTENTIAL_NEEDS_BASE`;
the test `test_the_tab_doc_carries_every_served_legend_text_verbatim` fails when this table drifts from the served words.

Tests: `backend/tests/test_gajjala_counts_legend_2026_10_18.py` (NEGATIVE: forming never "criteria not met", potential
never "every rule met", the nine other subs' title None, the `counts` keys unchanged). The three Gajjala goldens were
regenerated by their recipes (two keys added, nothing else moved). 2026-10-18 critic fix (words only): the A+ text no
longer says every A+ rings (the push gate refuses a late or repeated A+), the none text names the held reads (a 🎾
read over the float rule reads none), and the potential text carries the base clause; goldens regenerated again.

## Endpoint — `GET /chart-maps/gajjala?sub=&tf=&focus=&sort=&limit=`
`chart_maps/api.py` → `chart_maps/gajjala/tab.py:build()`. **Reads Mongo only** (never scans, never fetches a bar); the route
adds ONE live fan-out for the shown tiles' now-line (`board._live_snapshot` + `attach_live_now`, the Support pattern) and
`_scrub`s NaN. Every argument is coerced (a direct call receives `Query` objects).

- **Session**: today ET from `PASS_OPEN_ET` on a market day; before it or on a closed day, the last market day ("last
  session YYYY-MM-DD", `refresh_sec` 0). In window (`PASS_OPEN_ET`–`PASS_CLOSE_ET`) `refresh_sec` = `PASS_CADENCE_SEC`.
  Tape = `scanner.pass_tape_session` (the pass's own clock). `first15` = 09:30 ≤ now < 09:30 + `NO_TRADE_AFTER_OPEN_MIN`.
- **Pass**: the session's newest `gajjala_passes` doc. `warming` = in window, none this session; `stale` = in window and
  older than `STALE_AFTER_SEC` (900 s, the /alerts rule).
- **Sub resolution** (push deep links): an explicit known sub wins; unknown → `bull_flag`; empty sub + `focus` → today's
  newest `gajjala_alerts` claim for that name in state `pushed` or `shadow` (ids `GG:` / `SHADOW:GG:{date}|SYM|setup`) →
  else the setup whose read ranks best → else ☀️ / 🌙 when listed there → else the default. Served as `sub_resolved_from`.
- **Order** (setup subs): aplus 0 · triggered 1 · forming-ready 2 · forming 3 · partial 4 · stopped 5; A+/triggered/stopped
  newest entry bar first; ready forming by (trigger − last)/last; forming by bars to go; partial by fewest misses then biggest
  change; ties by symbol. ☀️ by volume (his ToS sort) or `sort=change`, the carry after today's names; 🌙 by after-hours gain.
- **Chips** (strings only): float / shares out (+ suspect), 🔄 rotation, ⏸ halts, 🧱 $1/$5/$10 within `PSY_NEAR_PCT`
  (Cheetah default), red closes > `RED_CLOSES_WAIT` (R2-5, chip only), "stopped earlier today (entered HH:MM, stopped)" (R2-6), "flag #k today",
  "type unknown", outside-RTH limit-orders line, 🎾 squeeze history (🎾 only). WP2's engines are reused
  (`context.psych_chips`, `red_closes_chip`, `rotation`, `premarket_list`, `unchecked_text`).
- **🌙 recap** (R2-7 yes): today's reads in aplus / triggered / stopped — states only, no win/loss maths.
- **Push block**: `GAJJALA_PUSH_MODE` "shadow" → "A+ pushes are in SHADOW — … no A+ reaches your phone until the
  `STUDY_SESSIONS`-session study reads and you flip it to live."

### What the pass must store for this board (WP4 interface)
| Where | Field | Read by |
|---|---|---|
| `gajjala_reads` | `setups{setup: Read}`, `tile{bars5,bars15,curves5,curves15,vol_avg5,vol_avg15}`, `ctx{float, rotation, halts, psych, float_suspect, squeeze_history}` | tiles + chips |
| `gajjala_reads` | `stopped_today{setup: entry_bar_t}` (kept across passes) | "stopped earlier today" chip |
| `gajjala_passes` | `strip`, `status`, `premarket.pm_levels{SYM: lv}` | strip; ☀️ 1-minute premarket volume |
| `gajjala_passes` | `postmarket{rows: postmarket_confirm rows, unchecked_n}` | 🌙 list + unchecked line |
Missing fields degrade to "nothing printed", never an error (☀️ falls back to the scanner's own premarket number).

## 📓 Playbook (`chart_maps/gajjala/playbook.py`)
Sections: Who he is · The scanner · Chart · Routine · What every setup shares · the five setups · Entry · Risk (his
discretion — NOT computed; 0.25% = his OWN starting risk; the S8 1:47:23 "5% to 10%" basis is ambiguous) · His stats (quoted)
· **Not built** (R2-14 + R2-8 journal: text only, each would need Ajay's numbers) — plus `management`, `avoids`,
`contradicted` (the verified set's contradicted rules + F4VS's "require a catalyst"), `knobs` (built FROM constants with
"Ajay 2026-10-13" / "Cheetah default"), `sources`. Every item is `{text, ts, source ∈ S8|S9, verbatim}`; GG's b-word quotes
are served as "[reverses]" / "[reversal]" / "[reversing]". The one other trader's name served is his own S8 9:45
self-description, verbatim.

## ℹ️ panel — `rules_info.SECTION_KEYS` "gajjala" (right before "fallen")
Picks: scanner + listing (Cheetah default) + strip; K1–K3; one line per setup; ☀️/🌙. Stops: entry/stop + ⏳ first 15
minutes; 🧱 psych (Cheetah default band); chips-never-rules. Alerts: the SHADOW line. Built from `constants.py` and the
`daytrading.data` session clock — the section source carries no numeric literal (AST test).

### 2026-10-13 — five served-payload fixes (WP5a minors)
- **Frame per card.** With no `tf` in the URL each card draws the frame its own read was taken on (`read.frame`, else the
  sub default) — a ➖ Fade that fell back to a 5-minute read now serves 5-minute bars, not the 15-minute ones. Each tile
  carries the frame it served as `tile.tf`; the payload's `tf` stays the sub default (15m on ➖, else 5m). On an explicit
  `tf` (the toggle), and on the empty-frame fallback, an A+ marker whose stamp is not one of the served bars is dropped —
  the read, its BUY/STOP lines and `entry_bar_t` are still served.
- **Quiet line** built from `SA_QUIET_BEST_PCT` ("best runner under 40%"), his S8 44:37 words kept as a quoted aside; the
  09:30 open is `daytrading.data.ET_RTH_OPEN`, imported, never retyped.
- **Knob table = ℹ️ panel**: K10 renders "top 30% of the day's range" (`K10_CLOSE_TOP_FRAC` × 100, "%g%%") and the scanner
  floor "$0.10" ("%.2f"), exactly as `rules_info` prints them; a test holds the two surfaces together.
- **Counts**: a read held by an unanswered placeholder (or carrying an "awaiting" reason) counts in `awaiting_answer`,
  never also in `none`.
- **Badge**: from the last pass (`PASS_CLOSE_ET`) to midnight on a session day the label is "today" and the badge "closed"
  (not "closed · last session"). The R2-6 chip reads "stopped earlier today on this setup (entered HH:MM, stopped)" —
  `stopped_today` holds the ENTRY bar's stamp, not the stop's.

## Tests
`backend/tests/test_gajjala_tab.py` · `test_gajjala_playbook.py` · `test_rules_info_gajjala.py` ·
`test_gajjala_source_guard.py` (no other method's import / served name except his verbatim line; no b-word anywhere in
`chart_maps/gajjala/*.py`).

## HIS CALLs still open
None introduced here. Display-only defaults kept as the spec wrote them: R2-3 halts = chip only (`HALT_CALM_BARS` off), R2-4
after-hours exhaustion = shown only (`AH_EXHAUSTION_MAX_PCT` off), R2-9 house chips kept, R2-10 "[reverses]" brackets.

## 📱 Phone layout (2026-10-19)
Ajay, with an iPhone 14 Pro Max screenshot of a TCRT card: "On the phone Gajjalas looks wierd and cut off can you fix
the UX issues I use an Iphone 14 pro max". Measured in the browser at that screen's width (430 px): the card is a
`.cm-grid` item, and a grid item's default `min-width: auto` lets its unbreakable content set the column's minimum. One
served chip under the card — the `flag_k` house badge "flag #1 today · Business Insider: he plays the first and second,
usually skips the third (one third-party source)", 549 px with the house `.cm-badge { white-space: nowrap }` — set the
card's minimum, so the grid's single `1fr` column grew to 552 px inside a 386 px board and the chart, the K-rule lines
and the chip row ran off the right edge. Only this tab serves a chip that long, which is why only this tab showed it.

Two rules in `frontend/src/styles/gajjala.css` fix it, nothing served changes:
- `.gg-card { min-width: 0; max-width: 100% }` — the card can never be wider than its column.
- `.gg-chip-row .cm-badge, .gg-pot-tells .cm-badge, .cm-tile-chips .cm-badge { white-space: normal; overflow-wrap:
  anywhere }` and `overflow-wrap: anywhere` on the pills, the plan line, the K-rule lines and the served lines — every
  served string on the card wraps instead of widening it.

After the fix at 430 px: column 386 px, card 386 px, the flag chip 383 × 35 px on two lines, no element of the board past
the viewport. The sub-tab strip still scrolls sideways on a phone — the house `.cat-tabs` rule at narrow widths
(`flex-wrap: nowrap !important; overflow-x: auto`), the same as every Catalysts-style tab; wrapping it into two rows is
HIS CALL. Guards: `frontend/src/components/GajjalaBoard.phone.test.tsx` (source guards incl. NEGATIVES on the pre-fix
stylesheet) and the contracts block "📱 gajjala phone layout (2026-10-19)". ✨ `chart-maps-gajjala-phone-layout-2026-10-19`.

## 🔄 Scan now answers every tap (2026-10-20)
Ajay, with a screenshot of the 🔄 button: "This can button has been unresponsive for me". The api log for that morning
shows every tap answered `200` (24 `POST /chart-maps/gajjala/scan` since the open), so the server was never the problem;
the board was. `GajjalaBoard.startScan` printed something for three of the five answers only: `started` / `waiting` (the
scanning line and a poll), `refused` (its error line) and `reused` for a pass NEWER than the one on screen (one re-read,
the served line meanwhile). The two answers a tap gets most often printed nothing: `reused` for the pass already on
screen (any tap within `ON_DEMAND_REUSE_SEC` of a pass — and the scan on open had just run one) and `closed`. A non-ok
answer and a network error printed nothing either. Right after open the button is `disabled` while the on-open pass runs
(up to `ON_DEMAND_WAIT_MAX_SEC`), so a tap then sends nothing — the scanning line says so; the button only dims.
Measured at 430 px before the fix: the button is 98 × 38 px, so the tap target was never the problem.

What changed (frontend only — nothing served, scanned, counted or gated changed):
- Every plan-less answer (`reused` for the pass on screen, `closed`, or a plan the server did not send) prints its SERVED
  `text` under the strip (the same `gg-scan-reused` line). It lives until the first board read that STARTS after the
  answer lands (`seq` at the answer, cleared once `boardSeq` passes it — a read already in flight never clears it) or
  until the next tap replaces it. No FE timer, no FE number, no FE word; `refused` keeps its own error line.
- While the POST is out the button is `disabled` and `aria-busy="true"`; `.gg-rescan[aria-busy="true"]` pulses, still
  under `prefers-reduced-motion`.
- A non-ok answer prints the served `detail` when it is a string (`gg-scan-err`, the error class); `404` prints nothing,
  as the broker-tag writes do; a network error prints nothing — the button is idle again either way.

Guards: `frontend/src/components/GajjalaBoard.scan.test.tsx` (the describe "🔄 scan now answers every tap", incl.
NEGATIVES, and the three earlier reused tests updated) and the contracts block "🔄 Gajjala scan-now answers every tap
(2026-10-20)". ✨ `chart-maps-gajjala-scan-now-2026-10-20`.

## 🚫 A no-risk A+ never rings · one price grid (2026-10-20)
Finding (measured in the live Mongo, `gajjala_alerts`): the pushed A+ `GG:2026-10-20|MMA|kiss_fly` (entry bar 11:00 ET)
carried `trigger 0.31`, `stop 0.31`, `risk_pct 0.0`, `price 0.3101`. The premise that the builder rounds sub-dollar levels to
two decimals is **false**: nothing in `chart_maps/gajjala/*`, the minute loader (`daytrading.data`), the resampler or the
store rounds a level, and the same day's other sub-dollar alerts kept their decimals (PLAG 0.5888 / 0.5668, REED 0.44495 /
0.4325, SGRX 0.4608 / 0.44015). MMA is a one-print name: its 1-minute bars that morning each hold a single trade (170–564
shares). The kiss bar (10:45–10:50 ET) was one print at 0.31 — high = low — so the Kiss & Fly's trigger (its high) equalled
its stop (its low); the "break" was one 170-share print at 0.3101, a hundredth of a cent above. The 🏁 grader already
treated that alert correctly (plan `no_risk`, AMENDMENTS9 E4 — listed as "1 no risk", never a win or a loss, out of the %);
the 🚩 paper lane refused it (`no_risk`). What was wrong: the detector called it A+ and the push rang with trigger = stop.

What changed:
- `detectors._resolve_break` (every setup's break goes through it): the plan first — `ledger.plan_of(trigger, stop)` must
  be `ok` (trigger above the stop). `no_risk` (trigger == stop) → the read is **invalid**, reason `NO_RISK_REASON` ("no
  risk — the trigger and the stop print the same price (a bar with no range)"); `no_plan` (stop above the trigger) →
  `NO_PLAN_REASON`. The levels and the bar stay on the card; never A+, never a push candidate, never a 🏁 row. One rule,
  the ledger's own words — no new number.
- `alerts.run_pass`: the second lock — an A+ read whose plan is not `ok` is `no_risk`: recorded `GG:{date}|SYM|setup#no_risk`,
  counted (`COUNT_KEYS` "no_risk", right before "broker_flagged"), never sent, in live and in shadow. `/alerts` words it:
  "n A+ held: trigger = stop (no risk), never sent".
- `tab._px` — the ONE price formatter of the card text, the push, the 🏁 Track record and the 🚩 lane — now sits on the
  broker's grid: `trading.broker.round_price` / `price_decimals` (Alpaca: `SUB_DOLLAR_DECIMALS` under `SUB_DOLLAR_LINE`,
  `DOLLAR_DECIMALS` at or over; half-up on the price's own decimal text). Sub-dollar prices drop trailing zeros ("0.31",
  "0.3101", "0.295"); a dollar price keeps its two ("4.46", "1.00"). The rule is typed once, in `trading/broker_alpaca.py`.
  The detectors' criteria values that are prices (the 9 / 21 EMA, VCP cycle lows and ranges) print through it too, so a
  sub-dollar name's EMAs no longer read "0.31 · 0.31".
- The card: `GajjalaBoard` printed the plan line through the house `pxText` (three decimals under a dollar — the S&D card
  ladder's rule), so a served 0.3101 read "0.310" next to a push that said 0.3101. `lib/gajjala.ggPx` mirrors the broker
  grid (`GG_PX_GRID`, pinned to the broker constants by the contracts) and the plan line prints through it. `pxText`
  itself is untouched (another surface — HIS CALL).
- Words: the ℹ️ legend's "invalid" text names the new cause; the ℹ️ Rules panel's entry/stop line says a reference bar
  with no range is invalid, never A+, never pushed. The three Gajjala goldens were regenerated by their recipes.

Re-grade: nothing to re-grade. `gajjala_ledger` holds no 2026-10-20 rows yet (the nightly at 20:15 ET writes them); the
live `today_read` at 17:12 ET graded 65 filled rows (25 wins · 38 losses · 0 "no risk") and did not grade the MMA A+ at all
(plan `no_risk` is skipped before the walk). The two MMA 🧠 potential rows (`first_trigger 0.3101`, `first_stop 0.31`, R =
one tick = 0.03 % of the trigger) are **thin** (`LEDGER_MIN_R_PCT`) — graded as losses in that read and kept out of the %
by the existing rule. Before = after. The stored MMA alert doc is left as it is (history; its plan is computed at read time).

HIS CALLs (unchanged, flagged): (1) 🧠 potentials still ring on a forming read whose last bar has no range (trigger = stop
at first sight: AMRO, EVTL, XHG today; 27 rows all-time) — a potential is not an entry, so the detector rule does not
reach `_resolve_forming`; one line in `potential.py` would refuse them. (2) Thin-R rows (R under `LEDGER_MIN_R_PCT` of the
trigger) are graded and kept out of the % — Q16 stands. (3) A one-print name's liquidity (170 shares on the entry bar)
is not a rule anywhere; `SCAN_MIN_VOLUME` is a daily count. (4) The house `pxText` three-decimal rule on the other
Chart Maps cards.

Guards: `backend/tests/test_gajjala_no_risk_2026_10_20.py` (detector, gate, formatter, ledger, words — NEGATIVES: a $4.46
level prints two decimals; a 0.3101 / 0.2950 alert keeps R = 0.0151 and rings with both numbers; a kiss bar with a range
still reads A+), `frontend/src/lib/gajjala.test.ts` ("ggPx — the broker price grid"), `GajjalaBoard.test.tsx` (the
sub-dollar plan line), `Alerts.test.tsx` (the no-risk chip) and the contracts block "🚫 Gajjala no-risk A+ · one price grid
(2026-10-20)". ✨ `chart-maps-gajjala-no-risk-price-grid-2026-10-20`.
