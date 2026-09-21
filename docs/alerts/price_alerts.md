# 🔔 Price alerts — one fire per crossing (latch), 2026-09-21

Engine: `backend/sepa/price_alerts.py`. Tests: `backend/tests/test_price_alerts_latch.py`,
`backend/tests/test_price_alert_delivery.py`. Cron: `backend/crontab:319-320`
(`*/5 9-15 * * 1-5 python -m sepa.cli alerts`, plus `0,5,…,30 16 * * 1-5`).

## The ask, verbatim

> "these are wrong alerts check the numbers please"
> "Yes please stop them why I am getting such older alerts these are supposed to be realtime"

— Ajay, 2026-09-21 15:05 ET, screenshot of `/alerts`: PRICE ALERT rows stamped 15:00 ET reading
`MKSI ↓ hit 256.1493 (alert ≤ 306.18)`, `ARM dropped -18.5% to 321.3 (from 394.17)` twice,
`BB dropped -9.2% to 8.385 (from 9.23)`, `ON dropped -39.6% to 71.2651 (from 118.0)` twice —
every row "not delivered — no device targeted".

His answer to "delete the presets, or keep them and stop the repeat?" was **stop the repeat**.
Nothing is deleted.

**The numbers were right. The repeat and the wording were wrong.** ARM 321.3 vs its set price
394.17 really is −18.49%; MKSI 256.1493 vs 331.39 is −22.7%; ON 71.2651 vs 118.0 is −39.61%.
What made them read as "older alerts" is that the presets were set in **May and June** and the
text carried no set date, no today figure and no `$`.

## The four kinds and the one line: `_threshold`

| kind | fires when |
|---|---|
| `below` | `last <= level` |
| `above` | `last >= level` |
| `drop_pct` | `last <= created_price * (1 - level/100)` |
| `rise_pct` | `last >= created_price * (1 + level/100)` |

`_threshold(alert, last)` is the single place that line is computed; `_hit()` only compares the
print against it. `_threshold` returns `None` — and `_hit` therefore `False` — for an unknown or
missing kind, a non-numeric `level`, or a pct kind with neither a `created_price` nor a live
print. It never raises. The comparison itself is **unchanged** by this work; only the re-fire was
wrong.

## The latch state machine

Every doc carries `armed`. `live` = the print came from a `prices.bulk_live_prices` snapshot row
(a real quote), not from the `last_trade_price` fallback.

| `armed` | hit | `last_fired_at` | `live` | action | what happens |
|---|---|---|---|---|---|
| missing | True | > 0 | any | `latch_legacy` | silent migrate: `armed False`, `triggered_at = last_fired_at`, `triggered_price None`, `triggered_ref`, `migrated_at`. No push, no fires row, no SSE |
| missing | True | 0 | any | `fire` | fires once, today |
| missing | False | any | **True** | `arm_legacy` | silent migrate: `armed True`, `rearmed_at None`, `migrated_at` |
| missing | False | any | **False** | `noop` | stays legacy until a live print evaluates it |
| False | True | any | any | `hold` | nothing, however many runs — **this is the fix** |
| False | False | any | **True** | `rearm` | silent: `armed True`, `rearmed_at = now` |
| False | False | any | **False** | `hold` | a cached close never re-arms |
| True | False | any | any | `noop` | nothing |
| True | True | any | any | `fire` | subject to `ALERT_COOLDOWN_SEC` (unchanged) |

`_transition(alert, last, now, live)` is pure — it returns `(action, $set patch)` and never
mutates the doc. The cooldown stays where it was, inside `check_alerts`, and applies only to the
`fire` action: inside the window the doc is left untouched, stays armed, and fires on the first
run after the window.

New doc keys (additive, nothing renamed or removed):
`armed`, `triggered_at`, `triggered_price`, `triggered_ref`, `rearmed_at`, `migrated_at`.
`create()` writes `armed: True` and the four `None`s **at birth**, so a preset tapped after this
deploy is never treated as legacy and never takes a migration branch (no `migrated_at`).
The `price_alert_fires` row shape and the SSE `alert.fired` payload are **unchanged**.

## Legacy migration

Idempotent, in the loop, no operator step and no one-shot script. On the first
`sepa.cli alerts` run after deploy every existing doc takes `latch_legacy` (already past its
line → goes quiet) or `arm_legacy` (not past its line → armed and ready), and on every later tick
the counters read `latched_legacy=0 armed_legacy=0`. After that run **the stale presets stay
quiet until price crosses back over the line and then crosses it again**.

The legacy latch deliberately carries **no price**. `last_fired_at` is the moment of the LAST
re-fire (15:00:01 ET on 2026-09-21 for the stale set), while the migrating run's print is a
different moment — pairing them would be a fabricated pair. The price of every fire already
lives in `price_alert_fires` (`min`/`max` `fired_at` per `alert_id`). So the served line reads
`triggered Sep 21 — re-arms when price crosses back above the line`, with no `at $`.
`triggered_at` is also the LAST re-fire, not the original June crossing (§HIS CALL 4).

A symbol absent from the bulk call that run stays legacy; it migrates on a later tick. Logged as
`fallback_prints` / `skipped_no_print`, not a bug.

## The cached-close rule

`prices.last_trade_price` (`prices.py:262-265`) **falls back to the cached daily close** on any
Massive failure. That is a real-looking number that may sit on the far side of a line the live
print has not crossed. Rule:

> A fallback print may **fire** and may **latch** (today's behaviour, unchanged). It may
> **never re-arm** a latched doc and **never arm** a legacy one.

Without that rule one provider outage during a run would re-arm every latched doc whose stale
close happened to sit across its line, and the next real print would re-fire the whole set — a
new failure mode this change would otherwise have introduced. Whether a fallback print should be
allowed to fire at all is a semantic change → §HIS CALL 9.

A `bulk_live_prices` row can also exist with **only** `prev_day_close` (a closed day).
`_live_print` reads `last_trade_price` then `price` and treats `0`/`None` as no print
(the `prices.extended_print` convention) — a previous close is never a stand-in for a quote.

## Wording

Rebuilt from the doc's OWN `created_price` / `created_at` plus the SAME snapshot row's
`prev_day_close`. One arithmetic on one print, consistent with the printed `now $`.

```
ARM -18.5% vs $394.17 when you set it (Jun 1) · today +16.6% · now $321.30
MKSI ↓ $256.15 crossed your ≤ $306.18 line (set Jun 2 at $331.39)
```

- `today` is `(last / prev_day_close - 1) * 100`. **No previous close → the segment is omitted
  entirely**, never printed as `+0.0%`.
- No set date on record → `when you set it` with no parenthetical; no set price → `(set Jun 2)`;
  neither → no parenthetical.
- `Note: …` second line, the `🎯 {sym} · {head[:80]}` title and the body are unchanged.
- `today ±x%` is built for the pct kinds only, per the ask's wording → §HIS CALL 6.

## One bulk call per run

`check_alerts` makes exactly **one** `prices.bulk_live_prices(sorted(symbols))` call, and calls
`prices.last_trade_price` only for symbols that call missed (or for all of them if it raised).
Before this it was one HTTPS `/v2/last/trade` per symbol per five-minute tick.

Return keys: `checked`, `fired`, `details` (unchanged) plus `latched_legacy`, `armed_legacy`,
`rearmed`, `held`, `skipped_no_print`, `fallback_prints`. `cli.py` reads `fired`/`checked` only;
`main.py` is untouched.

## Served state: `list_active()` and the FE line

Every row served by `GET /sepa/alerts/price` now carries `armed` (True/False/**None** = not yet
evaluated since deploy), `triggered_at`, `triggered_price`, `triggered_ref`, `rearmed_at`, and a
server-built `state_line`. `_state_line` returns `None` unless the doc is latched AND its kind is
known, and **never raises** — `list_active` serves every doc raw, and one malformed doc must not
500 the whole GET. The Active-alerts list under a ticker's 🔔 prints that string verbatim and
composes nothing itself (no date math, no `$`).

## The measured spam

Read-only Mongo probes, 2026-09-21 15:20-15:30 ET.

| | |
|---|---|
| `price_alerts` docs | **52** (14 symbols in the re-fire set) |
| `price_alert_fires` rows | **2,776** total, **857** in 30 days (17 of those are `vcp_watch` rows) |
| `push_history` `kind=price_alert` | **2,022** rows, **`sent > 0`: 0** |
| docs stamped `last_fired_at = 1790017201` (15:00:01 ET) | **18** |
| classification the first post-deploy run would apply (15:20 ET) | **20 `latch_legacy` / 32 `arm_legacy` / 0 `fire` / 0 `skipped_no_print`** |

Per symbol `push_history`: GFS 257, WDC 237, BB 211, MU 197, ARM 194, ON 190, SNDK 176, MKSI 123,
ASTS 100, TWLO 100, CORZ 98, RNG 68, NUE 53, DINO 18.

Root cause confirmed: the first in-session run at 09:00 fires, `ALERT_COOLDOWN_SEC = 6h` puts the
next one at 15:00 — 395 + 260 of the 857 fires in 30 days sit in exactly those two buckets.

Duplicates in the live set (not touched): WDC has 4 exact duplicate docs, MU has 6 docs at three
different `created_price` values, 25 docs have no `user_email` (house-owner fallback), one doc
belongs to `karthikganduri07@gmail.com`.

## Whipsaw caveat — this fix is NOT "quiet by construction"

Re-arm is plain `not _hit` — the exact inverse of the fire condition, with no band, because a
band would be a new number (Rule #1). Five live docs sit within ~1.3% of their own line
(2026-09-21 15:20 ET):

| doc | distance to its line |
|---|---|
| WDC `drop_pct 8` | −0.92% |
| WDC `drop_pct 10` ×2 (exact duplicates) | +1.28% |
| BB `drop_pct 10` | +1.06% |
| BB `rise_pct 5` | +1.08% |
| NUE `below 240.59` | +1.08% |

While price chatters through the line these can still print **up to 2 rows/day/doc** (×2 for the
WDC duplicates) — cross, re-arm, re-cross, fire, cooldown. WDC's 30-day fires at
09:45/10:00/10:10/10:50/11:35/14:45 are that chatter, not the cooldown bucket. This is stated,
not gated → §HIS CALL 8.

## The two silent-drop chokepoints (UNCHANGED)

The phone was quiet while the page was loud, and it still will be:

1. `backend/push/subs.py:24-28` `_RETIRED_2026_06_13` contains `"price_alert"` →
   `DISABLED_ALERT_KINDS` → `list_subscriptions` returns `[]` before the prefs query.
   A global kill-switch, his 2026-06-24 call.
2. His `push_subscriptions.prefs.price_alert = False` on both devices.

`push/history.py:107-150` writes a `push_history` row on **every** send attempt, `sent=0 total=0`
when zero devices — that is what `/alerts` renders. So each re-fire was one page row.
**This change makes the page honest and the rules latch; it does not make the phone ring.**
Un-retiring the kind and flipping the pref is §HIS CALL 1 — never flipped here.

## What is NOT changed

- `ALERT_COOLDOWN_SEC` (6 h), `KINDS`, `_target_email`, `delete`, `recent_fires`.
- The `price_alert_fires` row shape and the SSE `alert.fired` payload.
- `GET /sepa/alerts/price` / `GET /sepa/alerts/recent` handlers (`main.py`), `cli.py`.
- The `/alerts` page and its 2,022 historic rows — history is not hidden (§HIS CALL 2).
- `notify.send_alert(..., user_email=_target_email(a))` stays **lexically inside**
  `check_alerts`: `test_price_alert_delivery.py:41-49` pins that source, because moving the send
  into a helper is how the 2026-06-02 silent-drop bug got in.
- No doc deleted, no duplicate pruned, no push pref or kill-switch touched.

## Traps

- A real re-crossing inside the 6 h window is dropped with no trace: fire 09:00 → back over 09:30
  (`rearm`) → re-cross 10:00 (blocked, doc stays armed, no row) → back over 12:00 (`noop`) — that
  crossing is gone. If price instead stays past the line it fires at 15:00 with a 15:00 `now $`,
  a bounded 6 h "older alert". §HIS CALL 5.
- `price_alert_fires` has **two writers**: `check_alerts` (`alert_id` = ObjectId) and
  `sepa/vcp_watch.py` (`alert_id: None`, extra `meta`). Never pin "every row" in that collection.
- Title cap is `[:80]`. The longest realistic new head is 79 chars; a symbol priced ≥ $10,000
  would truncate the `· now $…` tail. None exists today. §HIS CALL 7.
- `time.time` must be monkeypatched at `price_alerts.time.time` — the module does `import time`.
- Purge the macOS bytecode caches before every pytest run; stale bytecode has defeated mutation
  tests in this repo.
- `list_active` is unscoped and lists every user's docs (pre-existing). Not changed here.

## HIS CALL — not decided, not built

1. **Un-retire `price_alert`** from `push/subs.DISABLED_ALERT_KINDS` and flip his device pref ON,
   so a real crossing reaches the phone. Both chokepoints drop it today; "supposed to be
   realtime" may mean he expects it on the phone. A pref is never flipped without him.
2. **Collapse the 2,022 historic `price_alert` rows on `/alerts`** (one row per alert per day, or
   hide `sent 0` re-fires older than today). Page untouched now.
3. **Dedupe / prune the 52 docs** — WDC ×4 duplicates, MU ×6 at three set prices, 25 ownerless,
   one Karthik's.
4. **Legacy `triggered_price`** is `None` by design. Alternative: backfill from the last
   `price_alert_fires.price` per `alert_id` (≤20 one-time reads) so the line shows the number he
   saw at 15:00. Also whether `triggered_at` should be the ORIGINAL crossing (`min fired_at`).
5. **Cooldown vs re-crossing** — dropping or shortening `ALERT_COOLDOWN_SEC`, or exempting a
   re-cross after a re-arm from the window, is a threshold change.
6. **`today ±x%` on `below`/`above` heads** too (built for the pct kinds only).
7. **Title cap 80 → 120** so the `· now $…` tail can never be cut.
8. **The five whipsaw docs** — (a) a hysteresis band on re-arm (a NEW number, Rule #1),
   (b) delete/dedupe them, (c) accept the chatter. Built: (c), stated.
9. **Firing on the cached-close fallback** — kept as today's behaviour (it can no longer
   re-arm). Whether a fallback print should fire at all is a semantic change.
