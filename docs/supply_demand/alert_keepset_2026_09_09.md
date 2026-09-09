# The alert keep-set — 2026-09-09

**Ajay:**

> Can you give me hot pull back alerts and chart pattern Alerts and also Sameday
> deman alerts please... Kill all other.. I just wanna these alerts.
>
> Default turn these on from tomorrow.

Asked whether the **stop alerts on stocks he owns** counted as "other", he chose
to keep those and drop the todo reminders.

## The four

| kind | what fires | when |
|---|---|---|
| 🔥 `hot_pullback_alert` | a HOT name takes one hard flush into a tested demand band and turns the same day | 08:15 ET weekdays |
| 📐 `pattern_alert` | a named bullish reversal pattern **confirms** on the daily frame | 08:15 ET weekdays |
| 🧲 `demand_alert` | a **same-day arrival** at a tested demand band | every 5 min, 09:33–16:00 ET |
| 💼 `position_alert` | stop hit / supply reached on a stock he **owns** | existing cadence |

**Killed:** `zone_bounce_alert`, `supply_break_alert`, `todo_reminder`,
`promo_alert`, `pivot_alert` and everything else.

## Said plainly: these are the three coin flips

He was shown these numbers before choosing, and asked for them anyway as a
watchlist. Nothing in the code is allowed to imply more.

| | measured | placebo / baseline |
|---|---|---|
| 🔥 Hot Pullback | **51.8% win**, n=83, expectancy +0.10R, **95% interval −0.19R to +0.41R includes zero** | — |
| 📐 Chart patterns | cup-with-handle **45%**, double bottom **43%**, triple bottom **37%**, inv H&S **10%** | **50% placebo**, n=659 |
| 🧲 Same-day demand | **52% up** (2026-09-08 autopsy of 286 pushes) | coin flip |

**Every push carries its own record.** The hot-pullback body says *"INCLUDES
ZERO"* and *"Watchlist, not an edge"*; the pattern body prints the pattern's own
rate beside the placebo and the words *"does NOT beat chance"*. A contract test
fails if either is dropped, and another fails if any pattern in the table ever
rises above the placebo without someone promoting it deliberately.

## Same-day was already implemented — and is NOT restated

`demand_alerts.read()` already carries the rule:

> `prev_close` given = arrivals only: the tier fires only if yesterday's close
> was still OUTSIDE that tier's ring

A resident gets **no tier at all**, so it never becomes a candidate. `prev_close`
is mandatory in the pass (`if not prev: unknown_prev += 1; continue`), so it
cannot be bypassed.

A second `same_day_gate` was written and then **deleted** — two copies of one
rule drift. The behaviour is pinned by a test where the rule actually lives.

## What kills an alert is the PREF, not the cron

`zone_bounce_alerts` still runs every 5 minutes. Its pass maintains the bounce
state that the boards and the 🔔 *alerted-today* chips read, so switching the
cron off would break screens he still uses to see what he is no longer being
pushed. The **pref** is the control surface.

## The registry trap

A kind missing from `push/subs.default_prefs()` sends to **zero devices,
silently** — the failure mode that once cost a week of "alerts are broken".
Both new kinds are registered there, in `OWNER_KEEP_SET`, in
`market_hours.gate.MARKET_ALERT_KINDS` (so closed days stay quiet), on the
Notifications page (a kind the page cannot show is a kind he cannot turn back
on), and in the `NotificationPrefs` type. Tests pin every one of those.

## Applied

Both of his registered devices were rewritten to exactly these four; every other
boolean pref set to `false`. `owner_prefs()` and the **Essentials** preset now
mirror the same set, so a re-subscribe or a preset tap lands on it too.

## Files

- `supply_demand/hot_pullback_alerts.py` (new), `patterns/pattern_alerts.py` (new)
- `push/subs.py` — `OWNER_KEEP_SET`, both kinds in `default_prefs()`
- `market_hours/gate.py` — both kinds are MARKET kinds
- `crontab` — two 08:15 ET entries behind the holiday gate
- `frontend/src/pages/Notifications.tsx`, `frontend/src/hooks/useNotificationPrefs.ts`
- `tests/test_new_alert_kinds.py` (new), `frontend/scripts/contracts.mjs`
