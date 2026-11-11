# ⚡ Enter at the break — the card's plan line + the intrabar break watch (2026-11-11)

**Built SHADOW.** `GC.GAJJALA_BREAK_PUSH_MODE = "shadow"`: a break of an armed 🧠 plan is **recorded on /alerts, nothing
is sent to the phone**. No gate, threshold, A+ push, lane rule or order changed. UNMEASURED — nothing here was measured;
an intrabar break of the armed plan is not a buy signal.

## His words

- Ajay 2026-11-11 ~08:28 ET, with four NotebookLM screenshots of GG's entry (pole → shallow pullback → base bar → buy
  "right as the next candle breaks above the high of the pullback bar … without waiting for the candle to close"):
  *"Here is how he enters please tell me to enter based on this"*
- Read as two things: (a) the card prints the live plan plainly, (b) an owner alert at the INTRABAR break of an ARMED
  plan — ahead of the A+ push, which still waits for the bar close.

## 1. The card's plan line (served, the FE composes none of it)

`tab.plan_text(read)` → served as `gajjala.plan_text` on every card built by `tab.setup_tile` (GG5, the 1-minute page,
🧪 Audited):

| Read | Line |
|---|---|
| an entry read (`tab._is_entry_read`: A+, or forming with `ready` True) **and** a plan with risk (`ledger.plan_of(trigger, stop)` is `ledger.PLANS[0]`, "ok": trigger above the stop) | `PLAN_ENTRY_HEAD` "Entry above {T} · stop {S} · risk {r}%" |
| every other read with a trigger — partial, not ready, triggered earlier, stopped, **and** an entry read with no risk (trigger == stop, stop above the trigger, no stop) | `PLAN_LEVEL_HEAD` "trigger {T} · stop {S} · risk {r}%" |
| no trigger | nothing (`None`, no `gg-plan` div) |

`{T}` / `{S}` = `tab._px` (the broker grid — the same text as the chart's BUY / STOP labels); `{r}` = the read's own
`risk_pct`, one decimal. A missing part is dropped. The levels are the read's own bar high / low — GG's ±1 cent is NOT
applied (HIS CALL list of the spec, #8). FE: `GajjalaBoard.tsx` prints `read.plan_text` verbatim in `data-testid="gg-plan"`.

## 2. How the ⚡ break watch decides (`backend/chart_maps/gajjala/break_watch.py`, the ONE engine)

**Plans.** On every GG5 pass-pointer change, and on the first poll of an ET day, `live_hub` calls
`break_watch.request_refresh` — NON-BLOCKING; `refresh` runs on break_watch's OWN single worker "gg-brk", never behind a
lane order on the hub's worker. ONE store read, `store.break_watch_docs(day)`: today's 🧠 tracker docs still forming
(`POTENTIAL_STATE`), not break-claimed (`brk` absent), not first seen by a join pass, not in the graveyard. Only FRESH
docs count (the doc's live bar — `last.bar_t` + one bar of its frame, `alerts.FRAME_MINUTES` — is still open).
`plan_of_doc`: a plan = an **armed** doc (`last.kind == POTENTIAL_KINDS[0]`) whose trigger is over its stop
(`ledger.plan_of` "ok"). Building docs are watched for coverage, never plans. The watch list = armed names first, then
`last.session_volume` descending, at most `break_watch.WATCH_MAX` (= `GC.TILE_LIMIT_MAX`, the same derivation as
`live_hub.INTEREST_MAX`); the excess is counted `refused_cap`, never silently cut.

**The bar window.** The armed bar's close = the live bar's open (`open_t`); `close_t` = `open_t` + the frame's minutes.
The window is LEFT-closed **[open, close)**, like the buckets and the detector's minutes: a print stamped exactly at
the close belongs to the NEXT bar (2026-11-11 review fix).

**Coverage.** A symbol is "covered" from its first print seen since the latest socket authentication
(`live_feed.authed_since`) AND since it (re-)joined the watch list. A re-auth, leaving the list, or a new ET day clears
it. The memo keeps the last `BUCKETS_KEEP` buckets of `BUCKET_SEC` per symbol: new highs from ROUND lots only
(`ODD_LOT_CONDITION` never makes a high — the bar high the detector reads), new lows from EVERY regular print (fail
closed toward "stopped").

**`decide(plan, ups, downs, covered_from, t)`** — pure, the strict compares of `detectors.entry_event`:

1. `t >= close_t` → **expired** — the live bar closed; the pass decides (A+ or a new plan). Nothing written.
2. coverage starts after `open_t` (or none) → **blind**.
3. the first round-lot print over the trigger and the first print (any lot) under the stop inside [open, close).
4. a stop print at or before the break print → **stopped_first** (one timestamp doing both = stopped).
5. a break print → **break**; else **wait**.

Judged on every print of the symbol and once when the plan lands (a break earlier in the bar rings at once, with its
own print time). The plan lands at the pass, so a break early in the live bar is recorded after its print; the body
carries the print's own time.

**The ring** (the "gg-brk" worker). `mode()` "off" → nothing. Then, each refusal written ONCE per (plan, bar) to
`brk_held` and counted — never the day's claim:

`closed_day` (`alerts._closed_reason`) → the A+'s own window on the LIVE bar's start (`alerts.window_reason`:
`suppressed_premarket` / `suppressed_first15` / `suppressed_window` — the mute runs to `NO_TRADE_AFTER_OPEN_MIN` after
the open) → the halt / exhaustion suppressions ONLY while `HALT_CALM_BARS` or `AH_EXHAUSTION_MAX_PCT` is not None (both
None today; a doc without their ctx → `suppressed_unknown`, fail closed; else `alerts.extra_suppression`) → GG's session
floor `K11_MIN_SESSION_VOLUME` (no volume read → `floor_unknown`; under → `under_floor`) → `blind` / `stopped_first`.

**One claim per plan.** `store.claim_potential_break` claims `brk` once per (date, symbol, setup) — the A+'s claim key;
taken → `claimed_before`. `upsert_potential` can never clobber `brk` / `brk_held` (`store.POTENTIAL_GUARDED`), and
`potential.track` preserves them.

**Shadow vs live.** Shadow (built): `brk.state` "shadow" + `result.would_push` = the payload; the sender is never
called. Live: the sender of `GAJJALA_BREAK_PUSH_KIND` → `pushed` / `no_target` / `failed` (the A+ settle rule); a kind
with no sender raises before `push.hooks` is touched.

**The live hub print order.** `live_hub.on_print` applies ONE print filter (`PRINT_KINDS`) before every consumer, then
calls them in this order, each fenced: **lane → break → screen** (`trading.gajjala_stream` → `break_watch.on_print` →
`live_events`). A print of a symbol not on break_watch's OWN list is ignored (the hub's copy can lag one poll). The
watch set = lane ∪ today's A+ ∪ live interest ∪ `break_watch.symbols()`.

**The payload** (`compose`, numbers first): title "⚡ {SYM} · {setup} — traded over the armed trigger {T}" (+ 🚫 when on
his broker list); body = the print price and ET time, the last price vs the trigger, the stop and risk %, the setup's
`alerts.entry_words`, "the {frame} bar has not closed — the A+ push still waits for the close", `alerts.AH_TAG` after the
close, the broker text, and `break_watch.TAIL` "UNMEASURED — an intrabar break of the armed plan, not a buy signal". Tag
`TAG_PREFIX`-{setup}-{SYM} — never the 🧠 "gg-pot-" tag, so it never replaces the armed ring on the lock screen.

## 3. The mode switch and the kind

| Constant | Value | Meaning |
|---|---|---|
| `GAJJALA_BREAK_PUSH_MODES` | ("off", "shadow", "live") | the three states; anything else reads "off" (fail closed) |
| `GAJJALA_BREAK_PUSH_MODE` | "shadow" | **recorded on /alerts, nothing sent to the phone** |
| `GAJJALA_BREAK_PUSH_KIND` | = `POTENTIAL_PUSH_KIND` | rides the 🧠 kind and its toggle — no 8th `OWNER_KEEP_SET` kind |

Served status: `tab.push_break_block()` → `push_break` {mode, text} on GG5 boards beside `push_potential`;
`break_watch.TEXTS[mode]` (+ the feed's `live_feed.state_word` when the feed is not live). FE `data-testid="gg-push-break"`.
The process counters (watching / plans / rang / shadow / refused) are NOT served — they reset on an api restart; the
docs are the record. ℹ️ Rules panel: `break_watch.rules_line()` (every number from the constants at call time), read by
`supply_demand/rules_info.py`.

## 4. What /alerts shows

`supply_demand/alert_status.py`: each 🧠 row whose tracker doc has a `brk` dict gains `brk_state` (one of `BRK_STATES`
"claimed", "pushed", "no_target", "failed", "shadow") and `brk_text` = `break_watch.track_text(doc)` — `TRACK_TEXTS`
"⚡ break rang {HH:MM:SS} ET" (pushed) or "⚡ break seen {HH:MM:SS} ET (shadow)". The 🧠 pass strip gains `brk_summary` =
`break_watch.summary_text` ("⚡ break pushes today: {n} sent · {m} recorded in shadow"; zero parts dropped; the "your
phone's 🧠 count" clause only when one was actually sent) ONLY when some row has a state. A doc without `brk` keeps its
row byte for byte; an absent / raising break_watch serves no ⚡ key. FE `Alerts.tsx` prints them verbatim
(`data-testid="gg-pot-brk-summary"`). The 🧠 Track row on the tab carries the same word as `brk_text`
(`data-testid="gg-track-brk-{id}"`). `/notifications` (Notifications.tsx, the 🧠 toggle's detail) gains one sentence: ⚡
break pushes ride this toggle — recorded on /alerts, not sent, until his word.

## What did NOT change

- The GG5 A+ push: same pass, same bar-close rule, same bytes (`alerts.compose` on GG5 unchanged). It stays the backstop.
- Every gate: `K11_MIN_SESSION_VOLUME`, the window (`NO_TRADE_AFTER_OPEN_MIN`), the suppression switches (still None),
  the detectors' outputs, the 🧠 board's listing and order.
- The paper lane and orders: break_watch imports no `trading.*` module, writes no order; `trading/gajjala_stream.py`
  ("at or over" the trigger) is untouched — the break watch is the detector's strict "over".
- `OWNER_KEEP_SET` (the ⚡ rides the 🧠 kind), the crontab, the push toggles.
- `tab._tile_lines` — the chart labels (see HIS CALL 6).

## Tests

`backend/tests/test_gajjala_break_watch_2026_11_11.py` (pure `decide` / `compose`, the print memo, the [open, close)
edge, refresh = fresh docs only + the leave-diff that clears coverage, the cap, the ring chain against an in-memory
store, the store guards, the status texts per mode, the ℹ️ line; NEGATIVES: expired, blind, stopped_first, odd-lot
highs, a re-auth, a symbol that left and came back, a stale plan, "off" or an unknown mode, every refusal leaves `brk` free, a second claim → claimed_before, shadow
never calls the sender). `test_live_hub_break_2026_11_11.py` (non-blocking refresh on the GG5 pointer change and the
first poll of a day, the watch-set union, lane → break → screen, each fenced). `test_alert_status_gajjala_break_2026_11_11.py`
(rows / strip words served from the engine; a doc without `brk` byte-identical; absent / raising engine → no key).
`test_gajjala_card_plan_focus_day2_2026_11_11.py` T1 / T5 (plan_text both heads + the no-risk NEGATIVE, `push_break`,
`brk_text`). FE: `GajjalaBoard.entry_2026_11_11.test.tsx`, `Alerts.gajjala_break_2026_11_11.test.tsx`.

## HIS CALL (not decided here)

1. **Shadow → live is his word.** Built: `GAJJALA_BREAK_PUSH_MODE = "shadow"` (recorded, never sent). "live" rings his
   phone. UNMEASURED.
2. **Scope.** Built: all five setups (`GC.SETUPS`), the 5-minute page only. Options: bull flag only; also the 1-minute
   page; also 🧪.
3. **Socket load.** The watch adds up to `break_watch.WATCH_MAX` (= `GC.TILE_LIMIT_MAX`) extra symbols to the ONE live
   Massive socket, even in shadow (the record needs the prints). Fine in shadow, or watch nothing until "live"?
4. **/notifications wording.** The 🧠 toggle's new ⚡ sentence ("ride this toggle — recorded on /alerts, not sent, until
   your word") is mine. Rename freely.
5. **Risk % rounding.** The plan line and the ⚡ body print risk to one decimal (`.1f`, the FE's old `riskText`). Keep, or
   two decimals on sub-$1 names.
6. **"BUY >" on a no-risk ready card.** A ready card whose trigger equals its stop now says "trigger …" in `plan_text`,
   but its chart label still says "BUY > {T}" — `tab._tile_lines` keys on `_is_entry_read` alone. Pre-existing, NOT
   changed here.
