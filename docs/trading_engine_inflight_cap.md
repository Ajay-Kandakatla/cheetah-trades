# Auto-Pilot in-flight cap, one lane per name, one entry per minute

**Why (the 2026-09-27 Auto-Pilot autopsy):** the paper account was **−$11,061 since 06-12**, and **−$12,732 came from two opening-bell fan-outs** (9 entries sent within 61 seconds on 09-09, 5 on 07-06). On those days the engine broke its own written caps:

| finding | what happened | autopsy cut |
|---|---|---|
| **C1** the position cap ignores in-flight orders | `_evaluate` counted `len(broker.positions())` only, so a sent-but-unfilled entry was invisible. Peak 10 concurrent against `risk_rules.MAX_POSITIONS = 5` | a1, in send order, would have refused **8 entries, −$7,259** |
| **C3** every lane fans out in the same minute | the tick runs the lanes one after another, each checking only its own caps, and names first seen pre-market all fire at 09:30 | d1, a concentration limit |

These are **rule enforcement and a concentration limit, not a measured gain**: n = 2 bad days, and fan-out on 09-04 made +$838. Never quote the counterfactual as an EV.

Code: `backend/trading/program_caps.py` (`inflight`, `check`, `minute_taken`, `claim`, `set_tick_minute`), called from `backend/trading/entries.py` (`enter`, `_evaluate`) for every stock buy, and from `zero_dte_lane` / `options_lane` before they submit. Part of the Chart Maps program: [`trading_chart_maps_lanes.md`](trading_chart_maps_lanes.md). Supersedes the autopsy branch's P1 (`entries.py` a1 + d1), which is built here only.

**These four rules apply in every mode, with the Chart Maps master switch ON or OFF**, from the deploy on.

---

## 1. The in-flight open cap (a1)

`program_caps.inflight(broker)` returns `{positions, pending_buys, pending_notional}`, keyed by broker symbol (a stock ticker or an OCC string):

| counted | rule |
|---|---|
| positions | every row of `broker.positions()`, **stocks and options**; a filled 2-leg spread is 2 rows |
| a pending stock or single-leg option buy | a top-level `open_orders()` row with `side == "buy"`, status in `PENDING_BUY_STATUSES` (`OPEN_STATUSES` minus `held`), and `position_intent` not `buy_to_close` |
| a pending spread | any open `order_class == "mleg"` row, or any leg with `position_intent` in `OPEN_INTENTS` (`buy_to_open`, `sell_to_open`): **every such leg's OCC counts**, so a pending 2-leg spread counts 2, the same as once it fills (HIS CALL #1) |
| not counted | SELL legs (stop / target), `held` legs, `buy_to_close` legs |

The cap is the **union** `|positions ∪ pending_buys|` against `program_caps.open_cap(cfg, mode)`: `PROGRAM_MAX_OPEN` (15) when the program is ON in paper/sim, otherwise `risk_rules.MAX_POSITIONS` (5, untouched). A `partially_filled` buy of a symbol already held counts once.

Refusals (a `program-wait:` prefix means transient, retried next tick):

- `program-wait: portfolio full: N positions + P pending entries / CAP` (only when the symbol is not already held);
- `program-wait: entry already pending for SYM`;
- `broker error: open orders unreadable — entry refused (in-flight cap fails closed)`: **a broker read error refuses**, never allows.

Example: 4 positions + 1 unfilled buy → the next entry is refused with the program OFF (cap 5). 13 positions + a pending 2-leg spread → the next buy is refused with the program ON (cap 15).

## 2. One lane per name

A roster (Chart Maps lane) tag never buys a name that is already held, by any lane:
`program-cap: SYM already held (one lane per name)`.

Why: `hot_pullback_entry`'s exit calls `broker.close_position(sym)`, which sells the whole merged position, including another lane's shares. Non-roster tags (Minervini pyramids, manual) keep today's add-when-in-profit rule (`risk_rules.may_add_to_position`). Residue: a Minervini pyramid into a hot_pullback name, then hot_pullback's close, sells both; Minervini `auto_entry` is OFF.

## 3. One new entry per ET minute (d1)

One new entry per **ET minute bucket** across every lane, stocks and options, program ON or OFF. **Manual entries are exempt** from the claim (they still count in the open cap).

- `minute_key(now)` is the ET minute `"YYYY-MM-DDTHH:MM"`. The engine tick pins it with `set_tick_minute(<tick start>)`, so every claim in one tick uses the tick's own minute.
- **The peek, before any broker read.** `enter()` first calls `minute_taken()`. If another lane already has this minute, it raises `program-wait: one entry per minute (taken by SID SYM at HH:MM:SS ET)` **before `_evaluate`**, so a lane that cannot win makes no broker, quote or earnings reads. A Mongo error on the peek counts as taken (fail closed).
- **The claim, atomic.** After `_evaluate` passes and before `submit_bracket`: one `find_one_and_update` on `program_state` `_id "entry_clock"` with `{"minute": {"$lt": key}}`, upsert. A `DuplicateKeyError` means the minute is taken → refused. Any other Mongo error → `program-wait: entry clock unreadable`, refused.
- Keys are ISO strings, so `$lt` is monotonic: a slow tick can never claim a minute older than one already claimed.
- A claimed minute whose submit then fails stays claimed. That fails closed: nothing else enters that minute.
- With the program ON, the dispatcher runs lanes in usage order and stops dispatching new entries once the minute is taken, so **the higher-usage lane wins the minute**.

Rejected: rev 1's 60-second gap since the last entry (`PROGRAM_MIN_ENTRY_GAP_SEC`, removed and locked absent by contract). A late lower-ranked lane in one tick could beat an early higher-ranked lane in the next, and every refused lane ran `_evaluate` first.

**Residue:** a tick that overruns its minute can still claim its own older minute before the next tick claims the new one, so two entries can land seconds apart across a boundary. There is no tick lock (autopsy #20; the tick telemetry measures overlap first).

## 4. Check order at the chokepoint

`entries.enter`: minute peek → `_evaluate` → `claim` → `submit_bracket` → `program_caps.record_entry` (`program_entries`: sid, tag, symbol, asset, OCC, day, order and client order ids).

`_evaluate`: configured → armed → **in-flight open cap (positions + pending buys, option spreads included), one lane per name, one entry per minute** (the program-ON strategy switch and per-strategy caps join here) → safety floors ($2 / $700M) → absolute stop within `risk_rules.ABS_MAX_STOP_PCT` → never average down → earnings shield → sizing (`risk_rules.position_size`, then the program's 0.25% risk budget by `min()` when ON) → gross cap when ON.

The literal `STRATEGIES = (...)` tuple in `entries.py` stays (a contract pin); `STRATEGIES_ALL` adds the program tags, `zero_dte` and `options_zone`, which fixes `hot_pullback` and `quick_bounce` being journaled as `manual`.

## What he sees

- A refused lane logs its reason to `cm_lane_log`; the 🗺️ Chart Maps view on `/trading?view=strategies` shows the top skip reasons per strategy, existing lanes included.
- `/trading/status` → `chart_maps_program`: open count "N / CAP (P pending)", this minute's claim `{key, sid, symbol, at}`.
- A zone-edge band vetoed with a `program-wait:` reason is cleared, not blocked for the day, so a lost minute never burns the band.

## Verify after deploy (first RTH session)

- No two non-manual ledger `entry` rows (or `options_entry` / `zero_dte_entry` rows) share an ET minute.
- `/trading/status.chart_maps_program.open.n` ≤ the cap, counting pending entries and spread legs.
- No zone-edge band marked blocked with a `program-wait:` reason.
