# 🧾 My trades vs GG — a GG journal + an over-trade warning (2026-11-23)

Spec: `accountability` revision 2 (§0–§9; §9 = his question-card answers, binding). **Words and records only.**
The app never trades, never blocks a broker, never hides a ticker or a card, never changes a gate and sends no push.
**UNMEASURED. Not advice.** Nothing here claims edge and nothing is ranked.

## His words

Ajay 2026-11-23, verbatim:

> "Do not remove the other tickers please. Keep them on the board still.."
>
> "I think I am going outside Gajjalas now.. Please create a rule to warn me to not over trade and hold me accountable
> if I am missing out any gajjalas rules"
>
> "All of this is to help me augment gajjals rules and build confidence is my goal so make sure I am going to far our
> and seeking something that is not useful"

His question-card answers (spec §9):

| # | question | his answer |
|---|---|---|
| 1 | the journal / v1 | **"Build it (Recommended)"** |
| 2 | over-trade line | **"Before trade #3 (Recommended)"** — before #2 on a quiet day; BOTH GG quotes printed; the number is labelled MINE / his pick, never GG's |
| — | which broker he trades Gajjala names in | **"Fidelity"** — the Plaid reconcile (#11) stays NOT BUILT; the 🧾 tap is the record |
| 3–10, 12 | everything else | the stated default (see "HIS CALLs" below) |

## Data truth — what the app can and cannot see

- **The app cannot see his trades.** Alpaca is the PAPER lane, not his money. Plaid sees Fidelity only, gives dates
  only (no times) and arrives T+1 at best; many Gajjala names carry the 🚫 "not eligible at Fidelity" tag. **His tap on
  the 🧾 sheet is the ONLY same-day record of his trades.**
- **Times are his TAP times, not fill times.** Every surface says so (`MY_FOOTER_TEXT`, `MY_DATA_TEXT`).
- If he stops tapping, the line says `MY_NONE_TEXT`. Nothing is guessed, nothing is inferred from a broker.
- 🟢 / 🟡 depend on the app's 🎯 A+ detector. Its K-rule numbers are Ajay's / mine (formulas audit 11-10), not GG's.
  On 11-04/05 all 9 stored 🎾 breaks were missed only by K3. The 🟡 words say "the app's detector, not GG's".
- The over-trade warning lands after a trade is logged. The prevention is the `next_text` pre-warning on the board,
  printed BEFORE the next trade.
- Prior measurements: none on journaling or over-trading. A+ = coin flip (entries study 11-11). No 🚩 lane is net
  positive since 07-13.

## What GG said (every quote with its cite — read from code, never retyped)

Sources: S8 = GG's long interview (YouTube), S9 = his second interview, VR = `backend/chart_maps/gajjala/verified_rules.json`,
first-hand = `backend/tests/fixtures/gajjala/first_hand_2026_10_13.md`. Quote strings are served from the `playbook.py`
items by (source, ts), or from `accountability.QUOTES` for the three lines that are not in `playbook.py`.

| id | GG's words | cite | where in code |
|---|---|---|---|
| first 15 min | "I don't take trades for the first 15 minutes after the market opens …" | S8 14:41 | `playbook.py` ROUTINE; `NO_TRADE_AFTER_OPEN_MIN` |
| outside RTH | "limit orders only … slippage … I trade with less size after and pre-market." | S8 1:16:35 | `playbook.py` ROUTINE; VR R5 (pre-market allowed, at less size) |
| quiet day | "… I don't look at the screens, I take the day off." | S8 15:32 | `playbook.py` ROUTINE |
| quiet runners | "On a very bad day the maximum runners would be 30%–40% …" | S8 43:39–44:37 | `playbook.py` ROUTINE; `SA_QUIET_BEST_PCT` |
| good-day count | "if the market is good on average two, three, four trades per day" | S8 49:48 | `playbook.py` ROUTINE |
| recent count | "last six months I take one trade per day, two trades maximum." | S9 1:28:10 | first-hand fixture only → `accountability.QUOTES` |
| A+ rate | A+ setups "one or two every week." | S9 1:29:16 | first-hand fixture only → `accountability.QUOTES` |
| A+ rate (paraphrase) | "A+ setups: 1–2 a week in bad markets, ~1 a day in good ones." | VR M4 (quotes empty — **a paraphrase**, labelled so) | VR |
| re-entry | "if it stops me out I won't re-enter right then … I need at least a couple of bars to see whether the action is good." | S8 1:17:12; VR X7 | `playbook.py` ENTRY |
| prove it | "I don't want to be the first one in; I want the price and volume to prove it." | S9 1:03:33 | `playbook.py` ENTRY |
| loss cut | "if $2,000 is the loss in one trade, next trade I cut to $1,000 … then $500" | S8 46:47–48:12 | `playbook.py` RISK; `GG_LOSS_RISK_CUT` |
| entry | "No hard rule, will depend on the strength and candle size." | VR E1 (S11, X post) | VR |
| stop | "most of my exits [stops] are below the low of the previous bar, always" — the stop is known before entry | S8 32:27; VR E3 | `playbook.py` ENTRY |
| journal | "I took this trade, I grade the setup A+ or B, why I'm taking a B, my patience level, was I patient enough or an impulse trade, my discipline … how I peeled off" | S8 15:57–17:03; VR R8 (quotes empty) | first-hand fixture only → `accountability.QUOTES` |

**Things GG never said** (an earlier draft printed them as his; all dropped):
- VR T8b is `status: contradicted` and is about a FOMO entry at a $5.05 level — not a missing alert. Not quoted.
- VR U14 is about WATCHING ("at a time I'll be watching closely four or five stocks", S8 1:26:03; "four to five active
  stocks", S9 25:42). It says nothing about open positions. "(1–2 in poor markets)" has no quote. No open-position cap.
- `FOCUS_N = 5` is Ajay's 11-11 proposal #9, and the lane's `GAJJALA_MAX_OPEN = 3` is MINE (lane HIS CALL #17). Neither is used.
- VR E8: he STARTS at 0.25% and moves it with monthly performance; A+ up to double; "all in in those setups" (S9 13:49).
  A size check would be a hard line GG never drew → not built; every line ends "size not checked".

**Two "Not built" rows this touches** (left word-for-word):
- `playbook.py` NOT_BUILT "A post-market journal with his own fields (your answer R2-8: not now)." — he said "not now"
  before; his 11-23 ask and his §9 answer #1 mean now. The 📓 row text stays as is (pinned in
  `gg5_board_2026_10_27.json` and `gajjala_on_open_golden_2026_10_15.json`); editing it = HIS CALL #1, not done.
- `playbook.py` NOT_BUILT "A trades-per-day cap." — the line built here is a WARNING, never a cap. The lane keeps
  `GAJJALA_MAX_ENTRIES_PER_DAY = None` ("GG has no day cap").

## The build

v1 = GG's own journal plus ONE served line:
1. A 🧾 sheet on the 🚩 tab (GG5 5-min tab only; not 🧪, not 1-min). His tap stores GG's journal fields.
2. A pure grader (`backend/chart_maps/gajjala/accountability.py`) checks each logged trade against GG's rules at read time.
3. ONE owner `my_day` line right under 🌫️ Day read. It warns BEFORE trade #N, not only after.
4. A nightly "🧾 Your trades vs GG" section in the champions EOD report (main session; read-only, no POST, ever).

It touches none of `tab.py`, the 👀 Watch, the 🎯 A+ banner or Plaid. The 🚩 GG5 payload is byte-identical (the
`my_day` line is served from its own GET, so the GG5 identity golden does not move).

### Store — `owner_trade_log` (one doc per tap, index `(owner, date)`)

Fields: `owner`, `date` (ET), `sym`, `alert_id` (matched live `GG:` 🎯 A+ claim key or null), `entry` (required,
typed — no prefill; the app's last price is a placeholder hint only), `stop` / `stop_src` (`typed` | `alert` (one
explicit tap on "use the alert's stop") | `none`), `shares`, `grade` (`A+` | `B`), `why_b`, `patience`
(`patient` | `impulse`), `discipline` (`kept` | `broke`), `tap_ts` (UTC, set by the server), `quiet_at_tap`, `add_to`,
`warned_at_tap`, `exit_px` / `exit_ts` / `exit_note` (GG's "how I peeled off"), `void` / `void_ts`.

- Code never rewrites the facts. Checks are NOT stored — re-graded at read time over the full log. `warned_at_tap`
  is the one exception: it records what the sheet showed him at the tap.
- Same symbol already open today → stored as an add (`add_to`). An add is not a new trade (GG adds the second half,
  VR E4), so a double tap cannot inflate the count.
- Void keeps the doc; voided rows drop out of every count and are listed as "voided".
- Open = same ET date only. Yesterday's trade with no exit tap prints `exit not logged` and is never open today.
- Closed day (`is_market_day` False) → HTTP 409 "market closed {date} — nothing logged", nothing stored.

### Checks — `accountability.checks(trade, day_log, ctx)`

Each item `{id, kind: hard|soft|info, state: ok|flag|unknown, words, rule, quote_ref}`. UNKNOWN never flags.

| id | check | kind | GG source | number |
|---|---|---|---|---|
| A1 | a live `GG:` 🎯 A+ claim for this SYM, today, at or before the tap | soft | the app's detector; words cite "price and volume to prove it" (S9 1:03:33) | — |
| A2 | tap in [09:30, 09:45) ET on a market day | hard | S8 14:41 | `NO_TRADE_AFTER_OPEN_MIN` (GG) |
| A3 | tap before 09:30 or at/after 16:00 ET → "limit orders only, less size" | soft | S8 1:16:35 | — |
| A4 | no stop, or stop ≥ entry | hard | VR E3 | `ledger.plan_of(entry, stop)` |
| A5 | entry R past the alert's trigger | info | VR E1 "No hard rule …" | `ledger.r_past(trigger, stop, entry)`; no alert → no line |
| A7 | after a losing logged trade, this $ risk ≤ `risk_after(1.0, prev_pnl)` × previous $ risk | hard | S8 46:47 | `GG_LOSS_RISK_CUT` via `gajjala_entry.risk_after` |
| A8 | same SYM re-entered within `MY_REENTRY_MIN` of a stop-out (exit ≤ typed stop) | hard | S8 1:17:12 / VR X7 | `MY_REENTRY_MIN` (MINE) |
| A9 | grade B with an empty why-B | soft | VR R8 | — |
| A10 | patience = impulse | hard | VR R8 | — |
| A11 | discipline = broke | hard | VR R8 "my discipline" | — |
| O2 | today's non-void, non-add entries ≥ the line | soft warning | S9 1:28:10 + S8 49:48, both printed | `MY_DAY_CAP` / `MY_DAY_CAP_QUIET` (MINE) |
| O3 | entries this week (nightly only) | soft | S9 1:29:16 + VR M4 (paraphrase, labelled) | words only |
| O4 | an entry on a quiet strip day | soft | S8 15:32 + S8 43:39–44:37 | the strip's own `quiet` at the tap |

- A7 $ risk = (entry − stop) × shares; any missing input → unknown. The ONE engine `risk_after` halves on any loss.
- A8: no exit tap → unknown; an exit tapped after this entry is never a prior stop-out; no tick buffer (an invented number).
- Quiet = the strip's `quiet` read at the tap. `None` (before the first pass) → normal line; O4 silent.

**Verdict** (`accountability.verdict`), three states:
- 🟠 **GG rule missed** — any hard flag; each missed rule is named with its quote.
- 🟡 **GG rules kept · not an app 🎯 A+** — no hard flag, A1 not ok ("the app's detector, not GG's — your read of the setup").
- 🟢 **GG rules kept on an app 🎯 A+** — no hard flag, A1 ok. Plain words, no praise, always ends "size not checked".

A1 can never make a trade 🟠.

### Endpoints (owner = the primary admin only, `is_primary_admin`; never a co-owner)

- `GET /chart-maps/gajjala/my-trades?date=YYYY-MM-DD` → `{state:"ok", date, my_day, trades[], voided[], totals,
  week, tally_10d, aplus_today[]}`. Non-owner → exactly `owner_only_payload()`. Never writes.
- `POST /chart-maps/gajjala/my-trades` `{sym, entry, stop?, stop_src, shares?, grade, why_b?, patience, discipline}`
  → `{doc, checks, verdict_text, warn_lines[]}`.
- `POST …/{id}/exit` `{exit_px, exit_note?}` · `POST …/{id}/void`.
- Non-owner POST → 404 before the body is read · bad body → 422 · unknown id → 404 · second exit → 409 ·
  `exit_px` ≤ 0 → 422 · closed day → 409.
- A tap never calls Alpaca, a `trading/*` order path, Plaid or any push sender.

### Served words (templates in `constants.py`, the FE prints them verbatim and composes no count or quote)

`MY_DAY_TEXT`, `MY_DAY_NEXT_TEXT` (before the next trade, when n + 1 ≥ the line: "⚠️ next trade = #{k} today — GG, last
six months: "one trade per day, two trades maximum" (S9 1:28:10); good market: "two, three, four trades per day"
(S8 49:48). Your line = {cap} (MINE)."), `MY_DAY_QUIET_TEXT`, `MY_A1_TEXT`, `MY_A2_TEXT`, `MY_A3_TEXT`, `MY_A5_TEXT`,
`MY_A7_TEXT`, `MY_A8_TEXT`, `MY_NONE_TEXT`, `MY_YESTERDAY_TEXT`, `MY_KEPT_TEXT`, `MY_FOOTER_TEXT` ("words only · the app
never trades or blocks your broker · times = your taps, not fills"), `MY_DATA_TEXT`.

### ℹ️ Rules panel

One list "🧾 your journal checks (GG)" in the Gajjala section of `supply_demand/rules_info.py` (A1–A11, O2–O4, each
with its quote ref), every number read from the constants; MINE lines say "MINE — HIS CALL #n".

## MINE (numbers GG never gave — each one is his call)

| constant | value | provenance |
|---|---|---|
| `MY_DAY_CAP` | 3 | MINE — HIS CALL #2; his §9 pick "Before trade #3". GG: no cap; `playbook.py` NOT_BUILT "A trades-per-day cap" |
| `MY_DAY_CAP_QUIET` | 2 | MINE — HIS CALL #2; his §9 pick (before #2 on a quiet day) |
| `MY_REENTRY_BARS` | 2 | MINE — HIS CALL #3; GG "a couple of bars" (S8 1:17:12) |
| `MY_REENTRY_MIN` | `MY_REENTRY_BARS × RUN_BASE_FRAME` minutes = 10 | derived, no typed 5; `RUN_BASE_FRAME = "5m"` (GG "I concluded on the five minute") |
| stop-out | exit ≤ typed stop | MINE — HIS CALL #3 |
| 🟢 needs a 🎯 A+, not a 🧠 armed potential | — | MINE — HIS CALL #4 |
| A7 win reset to full risk | `risk_after` | lane HIS CALL #18 (MINE), reused as the ONE engine — HIS CALL #12 |
| the line lives on the 🚩 tab only | — | MINE — HIS CALL #6 |

GG's own numbers used: `NO_TRADE_AFTER_OPEN_MIN` (15, S8 14:41), `GG_LOSS_RISK_CUT` (S8 46:47), the strip's
`quiet` (`SA_QUIET_BEST_PCT`, S8 43:39–44:37).

NOT added on purpose: `U14_POOR_N` (no quote), `MY_CHASE_R` (GG E1 "No hard rule"), `MY_EQUITY_SOURCE` (no size check).

## Outside GG's playbook — words only (nothing parked, no ticker removed — his first line)

| feature | why it is outside GG |
|---|---|
| 🥇 Luk tab + `luk_setup` push | another trader |
| 🩳 SI tiers, High SI sub, `gajjala_si_cross` push, 🔒 Reg SHO, 💸 borrow | GG has no SI rule (VR U10, status unsupported); the 9/21 cross is not his setup |
| 👀 Watch 1-min cross push | GG: "I concluded on the five minute" (S8 1:40:07); the 1-min charts stay (his 11-18 word) |
| 📈 VWAP on Watch | GG: "I don't have VWAP or ADRs" (S9 24:42, `playbook.py`) |
| 🟩 daily S&D zones on Watch | the app's engine; GG draws S/R only |
| 🧨 Divergence / 🌱 Diverging subs | not GG setups |
| 💋 RVOL sort | VR U5: no RVOL multiple anywhere |
| 📌 algo888 + 🎪 promo ADD names | not GG's ONE scan (VR U1) |
| 🧠 building potentials | K-rule reads; armed-only since 11-11 |

Inside GG (no call needed): 🎬 Replays, 📶 base count, 👀 Watch of 18 (U14 "up to 18 charts"), the first-15 mute, the
runner read, 📓 AVOIDS.

**Default for every row = KEEP** (HIS CALL #10, his first line: "Do not remove the other tickers please"). No ✋ tag,
no ℹ️ "Outside GG" list, nothing served — this table lives in this doc only.

## Rejected

- Plaid transactions for same-day warnings — date-only, T+1, Fidelity only, may cost a fee, false "not journaled" rows
  on SEPA / basket buys. Alpaca fills — paper lane, not his money.
- Adding `my_day` into the 🚩 tab payload — moves the GG5 golden.
- A chip on the 🎯 A+ banner and a 👀 Watch line — two more surfaces for one line on a dense board (Rule #5).
- A size check, an open-positions cap, a hard chase line — GG drew none of them.
- Blocking or hiding anything — his first line; boards list everything.

## HIS CALLs (defaults in force; nothing below is decided by code)

1. **The journal** — ANSWERED "Build it". The 📓 "Not built" journal row stays word-for-word until he says so (editing it moves two goldens).
2. **Over-trade line** — ANSWERED "Before trade #3" (#2 on a quiet strip day). Both GG quotes printed; the number is MINE.
3. **"A couple of bars"** before a re-entry after a stop-out — default 2 five-min bars = 10 min; stop-out = exit at or under the typed stop.
4. **🧠 armed potential counts as an app A+ for 🟢?** — default no, 🎯 A+ only.
5. **Chase** — default: print the R past the trigger, no line (GG E1). Option: flag past the lane's 1.0R (MINE, lane #9).
6. **Where the line lives** — default 🚩 tab only. Option: the 👀 Watch header too.
7. **Open-positions warning** — default not built (GG gives none). Option: the lane's 3 (MINE, lane #17).
8. **Size check** — default not built; every line says "size not checked".
9. **Push on a warning** — default no push, no new kind.
10. **Outside-GG features** — default keep every row and every ticker.
11. **Plaid reconcile** — ANSWERED "Fidelity": not built in v1 (T+1, possible fee); the 🧾 tap is the record.
12. **Loss-cut reset** — A7 uses the lane's engine (a win puts risk back to full, lane HIS CALL #18).

## Files

- Backend: `backend/chart_maps/gajjala/accountability.py`, `accountability_store.py`, `accountability_api.py`;
  `constants.py` (the `MY_*` constants and templates); `ledger.py` (`r_past`, additive); `main.py` (one router);
  `supply_demand/rules_info.py` (the 🧾 list).
- Frontend: `frontend/src/components/MyDayLine.tsx`, `MyTradeSheet.tsx`; `GajjalaBoard.tsx` mounts `<MyDayLine>`
  under `<DayReadLine>` on the GG5 tab only when the served `broker_flags` is present (owner).
- Tests: `backend/tests/test_gajjala_accountability_2026_11_23.py`, `test_gajjala_accountability_api_2026_11_23.py`,
  `test_rules_info_accountability_2026_11_23.py`; `MyTradeSheet.test.tsx`, `MyDayLine.test.tsx`.
- Goldens: none moved (`tab.py` untouched; `test_gajjala_variant_gg5_identity.py` passes with no regen).
