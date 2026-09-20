# The owner keep-set — 2026-09-20

**2026-09-20.** Two asks, one day, opposite directions.

> "Default on for any change of todays features Bondes or Potus or explosive
> growth or Earnings I wanna see all of them."

> "Remove volleyball and learning of stocks I do dont wanna see them they are
> spamming too much."

And on the his-call list the same day: **"Yes for #1"** — 🏛️ `potus_investment`
ships ON.

This page is what changed, what it did NOT change, and the one command that has
to be run against his already-registered devices.

---

## The eight

`backend/push/subs.py` → `OWNER_KEEP_SET`. These are the kinds a newly
registered OWNER device starts with (`prefs_for()` → `owner_prefs()`); every
other kind starts muted for him and untouched for everyone else.

| kind | surface | honest record |
| --- | --- | --- |
| `hot_pullback_alert` 🔥 | flush-and-turn board | +0.100R, CI includes zero |
| `pattern_alert` 📐 | named bullish reversals | not one pattern beats a 50% placebo |
| `demand_alert` 🧲 | same-day arrival at a tested band | ~52%, a coin flip |
| `position_alert` 💼 | stop / supply on stocks he owns | n/a — it reports his own book |
| `potus_investment` 🏛️ | federal-stake headline | HEURISTIC, no measured record |
| `growth_demand_alert` 🚀 | 100/100 growth name at demand | the screen has never been measured forward |
| `earnings_reaction` 📣 | beat + institutional buying | NOT MEASURED |
| `board_arrival` ✨ | new name on 📈 Bonde / 🚀 Explosive Growth | Bonde's rule measured INVERTED (−3.11pp) |

**This widened WHICH KINDS reach him. It loosened NO gate.** Every kind still
has to clear exactly what it had to clear yesterday — the ≥5% room and ≤1%
proximity gates on the S/D kinds, the `intact` band gate, the equity-stake +
named-agency + stated-size headline gate on 🏛️. Adding a kind to the keep-set
is a routing decision, not a rule change.

Why `growth_demand_alert` is on the list even though it was already delivering:
`prefs_for()` hands a RE-REGISTERING owner device `owner_prefs()`, which turns
on the keep-set and nothing else. A kind that is True on his phones today but
missing from the keep-set goes dark the next time a device re-subscribes. That
is exactly how the 2026-09-08 spam happened, in reverse.

## The four retired

`RETIRED_2026_09_20` in the same file, folded into `DISABLED_ALERT_KINDS`:

`minervini_flashcards`, `vb_workout`, `vb_supplement`, `vb_education`.

Four things had to happen together, or the kind comes back through whichever
door was left open:

1. **The crons are deleted** (`backend/crontab`) — the hourly flash card was
   `0 * * * *`, every hour of every day.
2. **The kinds leave `default_prefs()`** — no toggle, no stored pref.
3. **The kinds enter `DISABLED_ALERT_KINDS`** — `list_subscriptions()` and
   `list_mac_device_ids()` return empty *before opening Mongo*, so a device
   whose stored pref is still `True` cannot be reached.
4. **The modules guard themselves.** `flashcards.flashcards.main()`,
   `flashcards.chart_quiz.main()` and `volleyball.reminders.main()` check
   their own kind against `DISABLED_ALERT_KINDS` FIRST and return `0` in
   silence. This matters because **the crontab is bind-mounted from the host
   tree — a deploy does not ship a crontab change.** Until the cron container
   re-reads it, those lines still fire; now they exit 0 and write no
   `push_history` row.

They also left `market_hours.gate.PERSONAL_KINDS` — there is nothing left to
classify.

**The labels deliberately STAY** in `frontend/src/lib/alertKinds.ts`. 1,712
`minervini_flashcards` rows and ~215 `vb_*` rows are still in `push_history`
under its 90-day TTL, and they render in the 🔔 bell and the /notifications
panel whatever his prefs say (broadcast rows are visible to everyone). Without
the label they would render as a raw id. Purging those rows is a data write and
is on the his-call list below.

The nav entries `learn`, `learning` and `volleyball` left
`access/store.py FEATURE_CATALOG` (and the ⌘K synonym rows left
`frontend/src/lib/navSearch.ts`). **`chart-school` stays** — it is the
chart-reading quiz, not the flash-card feed he muted.

## The device state this was written against

Read off the live container 2026-09-20 (read-only probe):

- **Three** owner devices in `push_subscriptions`, all `web`; no `kind: "mac"`
  row today. All three carried hot_pullback / pattern / demand / position True,
  `growth_demand_alert` **True**, `potus_investment` **False**, and the four
  retired kinds **False**.
- `push_history`: `growth_demand_alert` 6 rows / 18 deliveries since
  2026-09-11 — the 🚀 kind IS reaching him. `minervini_flashcards` 1,712 rows,
  `vb_education` 74, `vb_workout` 70, `vb_supplement` 71.

So the code change alone leaves his phones exactly as they were: 🏛️ off, 📣 and
✨ absent, the retired four still stored. Which is what the next section is for.

## Running the apply script

`backend/scripts/owner_prefs_apply.py` is **dry by default**.

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply --apply
```

What it does: for every `push_subscriptions` document whose `user_email` is the
owner's (web **and** `kind: "mac"`), set every kind in `OWNER_KEEP_SET` to True
and every kind in `RETIRED_2026_09_20` to False. It reads both lists from
`push.subs` — they are never retyped here. Non-owner documents are counted and
never read past their `user_email`; the summary prints
`untouched (not the owner): N`.

It refuses with exit 2, before reading a single device, when
`OWNER_EMAIL` / `DEFAULT_USER_EMAIL` and `growth.alerts.OWNER` disagree — the
one place the address lives. It is idempotent: a second `--apply` prints
`no change` for every device.

**Re-run it after any new device registers** only if that device was registered
*before* this change shipped. A device that subscribes afterwards gets the
eight from `prefs_for()` automatically, and the script will report `no change`
for it — which is the cheapest way to confirm.

## HIS CALL — not decided here

1. **`board_arrival` on a closed day.** It ships as a MARKET kind, so a Sunday
   growth arrival rings the next trading morning at 08:08 ET. The alternative
   is a PERSONAL kind that pushes Sunday right after the 09:00 build.
2. **First-run backfill.** The first arrival pass records the baseline and
   pushes nothing — he is told about what is NEW, not about the 1,054 names
   already on Bonde. The alternative is one digest of every arrival since the
   ledgers began (bonde 2026-09-14, growth 2026-09-12).
3. **Delete, not just retire.** Still in the tree: `backend/flashcards/`,
   `backend/volleyball/`, their routers in `main.py`, and the `/learn`,
   `/learning`, `/volleyball` pages and routes (`/chart-school` stays). And the
   1,712 + ~215 old `push_history` rows keep showing in the bell and the
   panel until their 90-day TTL expires — purging them is a data write.

## Tests

- `backend/tests/test_retired_kinds_2026_09_20.py` — the registry, the
  chokepoint, the crontab negative, the three module guards (each returns the
  int `0` with every sender monkeypatched to raise and `history.record` never
  called), and the positive control that lifting the kill switch lets the send
  path run again.
- `backend/tests/test_owner_prefs_apply.py` — dry by default, owner-scoped,
  idempotent, refuses on an owner mismatch, no address literal in the source.
- `backend/tests/test_push_owner_keepset.py`, `test_new_alert_kinds.py`,
  `test_alert_kill_switch.py`, `test_market_hours_gate.py` — the pins that
  moved deliberately.
- `frontend/src/pages/Notifications.keepset.test.tsx` — the three new toggles,
  the four missing ones, and the page never saying "OFF BY DEFAULT" again.
