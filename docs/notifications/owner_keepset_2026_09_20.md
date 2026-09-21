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
4. **The modules guard themselves.** `volleyball.reminders.main()` checks
   its own kinds against `DISABLED_ALERT_KINDS` FIRST and returns `0` in
   silence. (`flashcards.flashcards.main()` and `flashcards.chart_quiz.main()`
   did the same until the module was deleted later the same day — see the
   2026-09-20 update below.) This matters because **the crontab is bind-mounted from the host
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
`frontend/src/lib/navSearch.ts`). `chart-school` left with them on the DELETE
later the same day — see the update below.

## 2026-09-20 (update) — flashcards DELETED, not just retired

> "Delete Flashcards please"

Retiring the kind stopped the phone. He then asked for the feature itself gone,
so it is out of the tree:

**Deleted:** `backend/flashcards/` (`__init__.py`, `api.py`, `chart_quiz.py`,
`flashcards.py`), `backend/tests/test_chart_quiz.py`,
`frontend/src/pages/Learn.tsx` (the card bank UI, `GET /flashcards/all`) and
`frontend/src/pages/ChartSchool.tsx` (its daily quiz, `GET
/flashcards/chart-quiz`). The router include left `backend/main.py`; the
`chart-school` entry left `FEATURE_CATALOG`; the `/learn` and `/chart-school`
routes and their lazy imports left `frontend/src/App.tsx`; the `chart-school`
synonym row left `navSearch.ts`.

**Kept, deliberately:**

* `minervini_flashcards` in `RETIRED_2026_09_20` / `DISABLED_ALERT_KINDS`.
  Nothing can fire it any more, but ~1,712 rows carrying it are still in
  `push_history` and `push/recent.py`'s serve-time filter keys on **this set**
  to hide them. Removing the literal would put every one of them back in the
  🔔 bell.
* Its label in `frontend/src/lib/alertKinds.ts`, for the same rows.
* **Volleyball**, retired and dark: crons deleted, toggles gone, kinds
  hard-stopped, module unlinked from the nav — but still in the tree and still
  importable. It never imported anything from `flashcards/` (only a docstring
  pointed at it; that was reworded), and a test pins that independence.
* `frontend/src/pages/LearningPath.tsx` (`/learning`, his study plan). A
  different page that calls no flashcards API — not part of this delete.

**Comments that listed a deleted kind were reworded**, not left to lie:
`market_hours/gate.py`, `supply_demand/rules_info.py` (the closed-day line now
reads "todos, household, sign-ins"), `push/subs.py`, `push/recent.py`,
`push/history.py`, `volleyball/education.py`, `volleyball/reminders.py`,
`main.py`, `NotificationBell.tsx`, `PushHistoryPanel.tsx`, and the
`holiday-quiet` (2026-09-07) ✨ entry, which had listed flashcards among the
kinds that still deliver on a closed day.

## 2026-09-21 (update) — 🔔 `price_alert` joins the keep-set

Asked *"Price alerts are retired in the push switch and off in your
Notifications, so even a real crossing will not reach your phone. Turn them
back on?"*, Ajay said **"Yes to all.."**. The set is now **nine**: the eight
below plus `price_alert`, the one kind that is not a scan — it is a line HE
drew on a ticker page. It also left `push.subs._RETIRED_2026_06_13` the same
day, so the code kill switch no longer swallows it; what it fires on (the
latch, `ALERT_COOLDOWN_SEC`, `_threshold`) is untouched. Full write-up:
`docs/alerts/price_alerts.md` → "The two silent-drop chokepoints — OPENED
2026-09-21". **The apply-script instructions below are unchanged** — the script
reads `OWNER_KEEP_SET`, so the same dry-then-`--apply` run now flips
`price_alert False→True` on his three devices and nothing else. Pinned in
`backend/tests/test_price_alert_unpause_2026_09_21.py`, which also guards the
`contracts.mjs` parser trap: never name the set in a comment above its
definition in `subs.py`.

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
3. ~~**Delete, not just retire.**~~ **ANSWERED 2026-09-20: "Delete Flashcards
   please".** `backend/flashcards/` and the `/learn` + `/chart-school` pages
   are gone (see the update above). `backend/volleyball/`, its router and the
   `/volleyball` and `/learning` pages **stay in the tree, dark** — he asked
   for the pings, not the pages. Still open: the 1,712 + ~215 old
   `push_history` rows, which `push/recent.py` now HIDES at serve time but
   does not purge (purging is a data write, and his call).

## Tests

- `backend/tests/test_retired_kinds_2026_09_20.py` — the registry, the
  chokepoint, the crontab negative, the volleyball module guard (returns the
  int `0` with every sender monkeypatched to raise and `history.record` never
  called), the positive control that lifting the kill switch lets the send path
  run again, and — added 2026-09-20 with the DELETE — the absence tests:
  `flashcards` has no import spec, no submodule imports, no source file is left
  on disk, no module declares a `/flashcards` route, both pages are gone from
  `App.tsx` while `/learning` still routes, `chart-school` is out of the
  catalog, volleyball imports nothing from the deleted module, the kept label
  still reads "Flash card", and no non-test frontend source links `/learn` or
  `/chart-school`.
- `frontend/scripts/contracts.mjs` — the same contract now asserts the
  ABSENCE of the deleted files, routes and router include.
- `backend/tests/test_owner_prefs_apply.py` — dry by default, owner-scoped,
  idempotent, refuses on an owner mismatch, no address literal in the source.
- `backend/tests/test_push_owner_keepset.py`, `test_new_alert_kinds.py`,
  `test_alert_kill_switch.py`, `test_market_hours_gate.py` — the pins that
  moved deliberately.
- `frontend/src/pages/Notifications.keepset.test.tsx` — the three new toggles,
  the four missing ones, and the page never saying "OFF BY DEFAULT" again.
